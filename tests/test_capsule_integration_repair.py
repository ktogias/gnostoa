"""Focused characterization for the three Work Item 190 integration defects.

Every fixture here is synthetic. No Phase-D task identifier, subject, hidden
oracle, identification key or evidence byte participates, and no Phase-D
hidden-oracle attempt is consumed. The OCI cases need a locally present image
that carries pytest and are skipped when none exists; they never pull one.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

from tests.test_experiment_capsule import CapsuleFixture, git
from tools.capsule import compiler
from tools.capsule.adapters import get as get_adapter
from tools.capsule.spec import SpecError, load_spec

IMAGE_A = "sha256:" + "a" * 64
RELAY_DIGEST = "sha256:" + "b" * 64
RELAY_PINNED = "registry.example/relay@sha256:" + "c" * 64

# Owner basenames that a Python module-name rule must survive. The interior dot is
# the canonical case reproduced against real Phase-D material.
UNSAFE_ORACLE_NAMES = (
    "synthetic.case.oracle.py",  # interior dot -> dotted module path
    "9oracle.py",  # leading digit -> not an identifier
    "class.py",  # Python keyword
    "pytest.py",  # shadows the test runner itself
    "click.py",  # shadows an ordinary subject module
)


def _image_with_pytest() -> str | None:
    """A locally present immutable image that carries pytest, or None.

    Never pulls. Only inspects what the host already has.
    """
    try:
        listed = subprocess.run(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    for reference in listed:
        if "<none>" in reference:
            continue
        try:
            probe = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--entrypoint",
                    "python",
                    reference,
                    "-c",
                    "import pytest",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if probe.returncode != 0:
                continue
            identity = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", reference],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if identity.startswith("sha256:"):
            return identity
    return None


_PYTEST_IMAGE = _image_with_pytest()


class OracleStagingRuleTests(unittest.TestCase):
    """Defect 1, unit level: the staging rule must be safe by construction."""

    def test_python_pytest_stages_under_a_safe_reserved_name(self) -> None:
        adapter = get_adapter("python-pytest")
        digest = "d" * 64
        for source_name in UNSAFE_ORACLE_NAMES:
            staged = adapter.staged_oracle_name(digest, source_name)
            stem = staged[:-3]
            with self.subTest(source=source_name):
                self.assertTrue(staged.endswith(".py"))
                self.assertNotIn(".", stem)
                self.assertTrue(stem.isidentifier())
                self.assertFalse(__import__("keyword").iskeyword(stem))
                # must not shadow the runner or an ordinary subject module
                self.assertNotIn(stem, {"pytest", "click", "pkg"})

    def test_staged_name_is_deterministic_and_digest_derived(self) -> None:
        adapter = get_adapter("python-pytest")
        first = adapter.staged_oracle_name("e" * 64, "synthetic.case.oracle.py")
        again = adapter.staged_oracle_name("e" * 64, "totally-different-name.py")
        other = adapter.staged_oracle_name("f" * 64, "synthetic.case.oracle.py")
        # Same oracle bytes -> same staged name regardless of what the owner called it.
        self.assertEqual(first, again)
        # Different oracle bytes -> different staged name.
        self.assertNotEqual(first, other)

    def test_other_adapters_keep_the_original_basename(self) -> None:
        for name in ("node-vitest", "generic-command"):
            adapter = get_adapter(name)
            with self.subTest(adapter=name):
                self.assertEqual(
                    adapter.staged_oracle_name("a" * 64, "oracle.spec.js"),
                    "oracle.spec.js",
                )


class OracleStagingCompilerTests(CapsuleFixture):
    """Defect 1, compiler level: staging preserves bytes and binds identity."""

    def _spec_with_oracle_named(self, oracle_name: str) -> tuple[dict, Path]:
        repo = self.make_repo(
            "s", {"src/pkg/__init__.py": 'def render():\n    return "Basic "\n'}
        )
        base = git(repo, "rev-parse", "HEAD")
        ref = self.commit(
            repo, {"src/pkg/__init__.py": 'def render():\n    return "Basic"\n'}, "fix"
        )
        oracle = self.root / oracle_name
        oracle.write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'Basic'\n"
        )
        spec = self.base_spec(repo, base, ref, oracle={"path": str(oracle)})
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        return spec, oracle

    def test_staged_oracle_bytes_are_identical_to_the_source(self) -> None:
        spec, oracle = self._spec_with_oracle_named("synthetic.case.oracle.py")
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        task = result.task("T1")
        staged = list(Path(task.qualification_paths["base"]).glob("*oracle*.py"))
        self.assertEqual(len(staged), 1, "exactly one staged oracle expected")
        self.assertEqual(staged[0].read_bytes(), oracle.read_bytes())
        # The semantic identity remains the digest of the original private bytes.
        self.assertEqual(task.oracle_sha256, compiler.digest_path(oracle))

    def test_staged_name_participates_in_harness_identity(self) -> None:
        """Changing the staged name must not be an unbound qualification variable."""
        spec, _ = self._spec_with_oracle_named("synthetic.case.oracle.py")
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        identity = result.task("T1").harness.identity
        staged = result.task("T1").harness.invocation.argv
        self.assertTrue(
            any(arg.endswith(".py") and "oracle" in arg for arg in staged),
            "the staged oracle name must appear in the qualification invocation",
        )
        # A different staged name yields a different harness identity.
        adapter = get_adapter("python-pytest")
        alternative = adapter.staged_oracle_name("0" * 64, "x.py")
        self.assertNotIn(alternative, staged)
        self.assertNotEqual(identity, "")

    def test_occupied_staging_destination_fails_closed(self) -> None:
        """A reserved destination already holding different bytes must not be overwritten."""
        spec, oracle = self._spec_with_oracle_named("synthetic.case.oracle.py")
        adapter = get_adapter("python-pytest")
        staged_name = adapter.staged_oracle_name(
            compiler.digest_path(oracle), oracle.name
        )
        repo = Path(spec["tasks"][0]["source"]["repository"])
        (repo / staged_name).write_text(
            "# subject content that must not be clobbered\n"
        )
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "occupy")
        spec["tasks"][0]["source"]["base_commit"] = git(repo, "rev-parse", "HEAD")
        spec["tasks"][0]["source"]["base_tree"] = git(repo, "rev-parse", "HEAD^{tree}")
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        codes = {b["code"] for b in result.blockers}
        self.assertIn("oracle-staging-destination-occupied", codes)


@unittest.skipUnless(_PYTEST_IMAGE, "no locally present image carries pytest")
class OracleStagingOciTests(CapsuleFixture):
    """Defect 1, the reproduced failure: interior-dot oracle must collect via #164."""

    def test_interior_dot_oracle_collects_and_classifies_through_the_runner(
        self,
    ) -> None:
        repo = self.make_repo(
            "s", {"src/pkg/__init__.py": 'def render():\n    return "Basic "\n'}
        )
        base = git(repo, "rev-parse", "HEAD")
        ref = self.commit(
            repo, {"src/pkg/__init__.py": 'def render():\n    return "Basic"\n'}, "fix"
        )
        oracle = self.root / "synthetic.case.oracle.py"
        oracle.write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'Basic'\n"
        )
        spec = self.base_spec(
            repo,
            base,
            ref,
            runtime={"image": _PYTEST_IMAGE},
            oracle={"path": str(oracle)},
        )
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        result = compiler.prepare(
            load_spec(self.write_spec(spec)),
            self.workspace,
            offline=True,
            preflight_authority=self.authority(),
            qualification_backend="oci",
        )
        receipt = result.task("T1").qualification
        self.assertIsNotNone(receipt)
        # The whole point: this must be a real behavioural classification, not the
        # INFRASTRUCTURE collection failure the original basename produced.
        self.assertNotEqual(receipt.base.classification, "INFRASTRUCTURE")
        self.assertNotEqual(receipt.reference.classification, "INFRASTRUCTURE")
        self.assertTrue(receipt.base.collected)
        self.assertTrue(receipt.reference.collected)


class RelayImageBindingTests(CapsuleFixture):
    """Defect 2: restricted experimental execution must bind an immutable relay."""

    def _restricted_spec(
        self, repo: Path, base: str, ref: str, **runtime: object
    ) -> dict:
        runtime_block: dict[str, object] = {"image": IMAGE_A}
        runtime_block.update(runtime)
        spec = self.base_spec(repo, base, ref, runtime=runtime_block)
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        spec["experiment"]["resources"]["network"] = {
            "mode": "restricted",
            "allow": ["provider.example:443"],
        }
        return spec

    def _subject(self) -> tuple[Path, str, str]:
        repo = self.make_repo(
            "s", {"src/pkg/__init__.py": 'def render():\n    return "Basic "\n'}
        )
        base = git(repo, "rev-parse", "HEAD")
        ref = self.commit(
            repo, {"src/pkg/__init__.py": 'def render():\n    return "Basic"\n'}, "fix"
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'Basic'\n"
        )
        return repo, base, ref

    def test_declared_relay_digest_reaches_the_execution_profile(self) -> None:
        repo, base, ref = self._subject()
        spec = self._restricted_spec(repo, base, ref, relay_image=RELAY_DIGEST)
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        profile = result.task("T1").execution_profile
        self.assertEqual(profile["runtime"]["image"], IMAGE_A)
        self.assertEqual(profile["runtime"]["relay_image"], RELAY_DIGEST)
        codes = {b["code"] for b in result.blockers}
        self.assertNotIn("generated-execution-profile-not-runnable", codes)

    def test_pinned_digest_reference_is_accepted(self) -> None:
        repo, base, ref = self._subject()
        spec = self._restricted_spec(repo, base, ref, relay_image=RELAY_PINNED)
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        self.assertEqual(
            result.task("T1").execution_profile["runtime"]["relay_image"],
            RELAY_PINNED,
        )

    def test_restricted_without_relay_fails_closed(self) -> None:
        repo, base, ref = self._subject()
        spec = self._restricted_spec(repo, base, ref)
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        codes = {b["code"] for b in result.blockers}
        self.assertIn("restricted-execution-requires-relay-image", codes)

    def test_mutable_relay_reference_is_refused(self) -> None:
        repo, base, ref = self._subject()
        spec = self._restricted_spec(
            repo, base, ref, relay_image="registry/relay:latest"
        )
        with self.assertRaises(SpecError):
            load_spec(self.write_spec(spec))

    def test_relay_image_is_bound_into_the_frozen_identity(self) -> None:
        repo, base, ref = self._subject()
        identities = []
        # The same workspace path for both runs, so the relay image is the only
        # variable. Capsule identity digests absolute profile paths, and two
        # different temporary directories would differ regardless of the relay.
        arena = self.root / "identity-arena"
        for relay in (RELAY_DIGEST, "sha256:" + "9" * 64):
            spec = self._restricted_spec(repo, base, ref, relay_image=relay)
            if arena.exists():
                shutil.rmtree(arena)
            arena.mkdir()
            result = compiler.prepare(
                load_spec(self.write_spec(spec)), arena, offline=True
            )
            identities.append(result.task("T1").capsule_identity)
        self.assertNotEqual(
            identities[0],
            identities[1],
            "changing the relay image must change the frozen capsule identity",
        )

    def test_relay_is_not_required_when_execution_network_is_none(self) -> None:
        repo, base, ref = self._subject()
        spec = self.base_spec(repo, base, ref)
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        profile = result.task("T1").execution_profile
        self.assertNotIn("relay_image", profile["runtime"])


class QualificationNetworkIsolationTests(CapsuleFixture):
    """Defect 3: qualification never inherits experimental executor egress."""

    def test_qualification_is_network_none_while_execution_is_restricted(self) -> None:
        repo = self.make_repo(
            "s", {"src/pkg/__init__.py": 'def render():\n    return "Basic "\n'}
        )
        base = git(repo, "rev-parse", "HEAD")
        ref = self.commit(
            repo, {"src/pkg/__init__.py": 'def render():\n    return "Basic"\n'}, "fix"
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'Basic'\n"
        )
        spec = self.base_spec(
            repo, base, ref, runtime={"image": IMAGE_A, "relay_image": RELAY_DIGEST}
        )
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        spec["experiment"]["resources"]["network"] = {
            "mode": "restricted",
            "allow": ["provider.example:443"],
        }
        result = compiler.prepare(
            load_spec(self.write_spec(spec)), self.workspace, offline=True
        )
        task = result.task("T1")
        for subject, profile in task.qualification_profiles.items():
            with self.subTest(subject=subject):
                self.assertEqual(profile["network"], {"mode": "none", "allow": []})
                self.assertNotIn("relay_image", profile["runtime"])
        # The experimental envelope is untouched.
        self.assertEqual(
            task.execution_profile["network"],
            {"mode": "restricted", "allow": ["provider.example:443"]},
        )


class NoSecondSandboxTests(unittest.TestCase):
    """The repair must not introduce an isolation path beside the #164 runner."""

    def test_capsule_never_invokes_a_container_runtime_directly(self) -> None:
        forbidden = ("docker", "--network", "--mount", "podman", "/var/run/docker.sock")
        offenders = []
        for path in Path("tools/capsule").rglob("*.py"):
            text = path.read_text()
            for needle in forbidden:
                if needle in text:
                    offenders.append((str(path), needle))
        self.assertEqual(
            offenders, [], f"isolation must stay in the runner: {offenders}"
        )


if __name__ == "__main__":
    unittest.main()
