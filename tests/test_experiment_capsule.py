"""Characterization suite for the Experiment Capsule preparation system (#187).

These tests describe the abstraction that Phase-D (#183) was missing. Each Phase-D
preparation failure class becomes a property of the compiler rather than a one-off
repair. Fixtures are synthetic analogues of the frozen Phase-D shapes: no hidden
oracle or identification-key content from #183 is reproduced here.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.capsule import certificates, compiler, stages
from tools.capsule.spec import SpecError, load_spec

IMAGE_A = "sha256:" + "a" * 64
IMAGE_B = "sha256:" + "b" * 64


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "PATH": "/usr/bin:/bin",
        },
    ).stdout.strip()


class CapsuleFixture(unittest.TestCase):
    """Builds a tiny offline Git subject and a minimal spec around it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def make_repo(self, name: str, files: dict[str, str]) -> Path:
        repo = self.root / name
        (repo / "src").mkdir(parents=True)
        git(repo.parent, "init", "-q", "-b", "main", str(repo))
        for rel, text in files.items():
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        return repo

    def commit(self, repo: Path, files: dict[str, str], message: str) -> str:
        for rel, text in files.items():
            target = repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", message)
        return git(repo, "rev-parse", "HEAD")

    def write_spec(self, payload: dict) -> Path:
        path = self.root / "experiment.json"
        path.write_text(json.dumps(payload, indent=2))
        return path

    def base_spec(self, repo: Path, base: str, ref: str, **task: object) -> dict:
        entry: dict[str, object] = {
            "id": "T1",
            "adapter": "python-pytest",
            "source": {
                "repository": str(repo),
                "base_commit": base,
                "base_tree": git(repo, "rev-parse", base + "^{tree}"),
            },
            "reference": {
                "kind": "accepted-merge-commit",
                "commit": ref,
                "tree": git(repo, "rev-parse", ref + "^{tree}"),
            },
            "runtime": {"image": IMAGE_A},
            "oracle": {"path": str(self.root / "oracle.py")},
            "semantics": {
                "requirement": "subject must not regress",
                "discriminator": {"cases": ["test_discriminates"]},
                "controls": [],
            },
            "expectations": {
                "base": {"failed": 1, "passed": 0},
                "reference": {"failed": 0, "passed": 1},
            },
        }
        entry.update(task)
        return {
            "schema": "gnostoa-experiment-spec/v1",
            "experiment": {"id": "E1", "question": "q", "claim_boundary": "bounded"},
            "tasks": [entry],
        }


class SpecContractTests(CapsuleFixture):
    def test_unknown_schema_is_rejected_rather_than_guessed(self) -> None:
        path = self.write_spec({"schema": "nope/v9", "experiment": {}, "tasks": []})
        with self.assertRaises(SpecError):
            load_spec(path)

    def test_ambiguous_adapter_is_rejected_not_inferred(self) -> None:
        repo = self.make_repo("s", {"src/m.py": "x = 1\n"})
        base = git(repo, "rev-parse", "HEAD")
        spec = self.base_spec(repo, base, base)
        del spec["tasks"][0]["adapter"]
        with self.assertRaises(SpecError):
            load_spec(self.write_spec(spec))


class D1PreloadTests(CapsuleFixture):
    """D1: a declarative mechanical preload, with no oracle/runtime/source change."""

    def test_declared_preload_is_compiled_into_the_harness(self) -> None:
        repo = self.make_repo("click", {"src/pkg/__init__.py": "", "src/pkg/_impl.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(repo, base, base, harness={"preload_modules": ["pkg._impl"]})
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)

        harness = result.task("T1").harness
        self.assertIn("pkg._impl", harness.preload_modules)
        self.assertTrue(
            any("import pkg._impl" in f.content for f in harness.generated_files),
            "declared preload must appear in a generated harness file",
        )

    def test_preload_changes_no_oracle_runtime_or_source_identity(self) -> None:
        repo = self.make_repo("click", {"src/pkg/__init__.py": "", "src/pkg/_impl.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        plain = self.base_spec(repo, base, base)
        preloaded = self.base_spec(repo, base, base, harness={"preload_modules": ["pkg._impl"]})

        a = compiler.prepare(load_spec(self.write_spec(plain)), self.workspace / "a", offline=True)
        b = compiler.prepare(
            load_spec(self.write_spec(preloaded)), self.workspace / "b", offline=True
        )
        for field in ("oracle_sha256", "runtime_image", "base_tree", "reference_tree"):
            self.assertEqual(
                getattr(a.task("T1"), field),
                getattr(b.task("T1"), field),
                f"{field} must not change when only a mechanical preload is declared",
            )
        self.assertNotEqual(a.task("T1").harness.identity, b.task("T1").harness.identity)


class D2ConfigIsolationTests(CapsuleFixture):
    """D2: test-config isolation without installing an unrelated plugin."""

    def test_repository_addopts_requiring_absent_plugin_are_isolated(self) -> None:
        repo = self.make_repo(
            "pyd",
            {
                "src/pkg/__init__.py": "",
                "pyproject.toml": (
                    "[project]\nname='pkg'\nversion='1'\n\n"
                    "[tool.pytest]\naddopts = ['--benchmark-disable']\n"
                ),
            },
        )
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(
            repo,
            base,
            base,
            runtime={"image": IMAGE_A, "available_plugins": ["pytest"]},
            harness={"isolate_test_config": True},
        )
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)
        task = result.task("T1")

        self.assertIn("-c", task.invocation.argv)
        joined = " ".join(task.invocation.argv)
        self.assertNotIn("--benchmark", joined)
        self.assertEqual(task.runtime_image, IMAGE_A, "isolation must not change the image")
        self.assertEqual(task.added_runtime_packages, [])

    def test_unisolated_unsatisfiable_addopts_are_a_structured_blocker(self) -> None:
        repo = self.make_repo(
            "pyd",
            {
                "src/pkg/__init__.py": "",
                "pyproject.toml": (
                    "[project]\nname='pkg'\nversion='1'\n\n"
                    "[tool.pytest]\naddopts = ['--benchmark-disable']\n"
                ),
            },
        )
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(
            repo, base, base, runtime={"image": IMAGE_A, "available_plugins": ["pytest"]}
        )
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn(
            "test-config-requires-absent-plugin", [b["code"] for b in result.blockers]
        )


class D3PreparationTests(CapsuleFixture):
    """D3: build-generated subject artifacts detected before any oracle execution."""

    def _scm_repo(self) -> tuple[Path, str]:
        repo = self.make_repo(
            "pt",
            {
                "src/pkg/__init__.py": "from pkg._version import version\n",
                ".gitignore": "src/pkg/_version.py\n",
                "pyproject.toml": (
                    "[build-system]\nrequires = ['setuptools', 'setuptools-scm']\n\n"
                    "[project]\nname='pkg'\ndynamic = ['version']\n\n"
                    "[tool.setuptools_scm]\nwrite_to = 'src/pkg/_version.py'\n"
                ),
            },
        )
        return repo, git(repo, "rev-parse", "HEAD")

    def test_generated_version_requirement_is_detected_before_qualification(self) -> None:
        repo, base = self._scm_repo()
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(repo, base, base)
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)

        prep = result.task("T1").preparation
        self.assertTrue(prep.required, "setuptools_scm write_to must be detected")
        self.assertIn("src/pkg/_version.py", prep.generated_paths)
        self.assertLess(
            stages.ORDER.index(result.stage),
            stages.ORDER.index(stages.BASE_REFERENCE_QUALIFIED),
            "detection must happen before any oracle execution stage",
        )

    def test_preparation_requires_a_new_runtime_identity(self) -> None:
        repo, base = self._scm_repo()
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(
            repo,
            base,
            base,
            runtime={
                "image": IMAGE_A,
                "preparation_tools": [
                    {"name": "setuptools-scm", "artifact": str(self.root / "scm.whl")}
                ],
            },
        )
        (self.root / "scm.whl").write_bytes(b"wheel")
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)
        task = result.task("T1")
        self.assertTrue(task.preparation.required)
        self.assertNotEqual(
            task.prepared_runtime_identity,
            IMAGE_A,
            "a preparation tool must yield a new runtime identity",
        )
        self.assertEqual(task.runtime_image, IMAGE_A, "the frozen base image is unchanged")

    def test_missing_offline_preparation_tool_blocks_without_acquisition(self) -> None:
        repo, base = self._scm_repo()
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(
            repo,
            base,
            base,
            runtime={
                "image": IMAGE_A,
                "preparation_tools": [
                    {"name": "setuptools-scm", "artifact": str(self.root / "absent.whl")}
                ],
            },
        )
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)
        self.assertEqual(result.status, "BLOCKED")
        codes = [b["code"] for b in result.blockers]
        self.assertIn("preparation-artifact-unavailable-offline", codes)


class D4SemanticPrequalificationTests(CapsuleFixture):
    """D4: an over-strong control is blocked before execution freeze."""

    def _werkzeug_like(self) -> tuple[Path, str]:
        repo = self.make_repo(
            "wz",
            {
                "src/pkg/__init__.py": "",
                "tests/test_http.py": (
                    'def test_upstream():\n'
                    '    assert build("basic", {"realm": "abc"}) == "Basic realm=abc"\n'
                ),
            },
        )
        return repo, git(repo, "rev-parse", "HEAD")

    def _spec_with_control(self, repo: Path, base: str, literal: str) -> dict:
        (self.root / "oracle.py").write_text(
            "def test_discriminates():\n"
            "    assert render() == 'Basic'\n\n"
            "def test_control_keeps_parameters():\n"
            f"    assert render_params() == {literal!r}\n"
        )
        return self.base_spec(
            repo,
            base,
            base,
            semantics={
                "requirement": "no trailing separator when there are no parameters",
                "discriminator": {"cases": ["test_discriminates"]},
                "controls": [
                    {
                        "case": "test_control_keeps_parameters",
                        "corroboration": {
                            "path": "tests/test_http.py",
                            "value_substitutions": {"phase-d": "abc"},
                        },
                    }
                ],
            },
        )

    def test_uncorroborated_control_blocks_before_execution_freeze(self) -> None:
        repo, base = self._werkzeug_like()
        spec = self._spec_with_control(repo, base, 'Basic realm="phase-d"')
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)

        self.assertEqual(result.status, "BLOCKED")
        self.assertIn(
            "oracle-control-not-corroborated", [b["code"] for b in result.blockers]
        )
        self.assertLess(
            stages.ORDER.index(result.stage),
            stages.ORDER.index(stages.EXECUTION_FROZEN),
            "the block must precede execution freeze",
        )

    def test_corroborated_control_passes_prequalification(self) -> None:
        repo, base = self._werkzeug_like()
        spec = self._spec_with_control(repo, base, "Basic realm=phase-d")
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)
        self.assertNotIn(
            "oracle-control-not-corroborated", [b["code"] for b in result.blockers]
        )

    def test_oracle_case_missing_from_semantics_is_blocked(self) -> None:
        repo, base = self._werkzeug_like()
        spec = self._spec_with_control(repo, base, "Basic realm=phase-d")
        spec["tasks"][0]["semantics"]["controls"] = []
        result = compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("oracle-case-undeclared", [b["code"] for b in result.blockers])


class CertificateTests(CapsuleFixture):
    """D0: reuse an exact, current capability certificate instead of requalifying."""

    def _certificate(self, *, max_bytes: int) -> dict:
        return {
            "schema": "gnostoa-capability-certificate/v1",
            "capability": "sealed-sink",
            "implementation_sha256": "c" * 64,
            "runtime_identity": IMAGE_A,
            "configuration_sha256": "d" * 64,
            "bounds": {"max_plaintext_bytes": max_bytes, "min_hold_seconds": 1800},
            "evidence_sha256": "e" * 64,
        }

    def test_exact_certificate_within_bounds_is_reused(self) -> None:
        cert = certificates.load(self._certificate(max_bytes=805306368))
        self.assertTrue(
            cert.satisfies(
                capability="sealed-sink",
                runtime_identity=IMAGE_A,
                implementation_sha256="c" * 64,
                configuration_sha256="d" * 64,
                requested={"max_plaintext_bytes": 67108864, "min_hold_seconds": 1800},
            )
        )

    def test_request_exceeding_certified_bounds_is_not_reused(self) -> None:
        cert = certificates.load(self._certificate(max_bytes=67108864))
        self.assertFalse(
            cert.satisfies(
                capability="sealed-sink",
                runtime_identity=IMAGE_A,
                implementation_sha256="c" * 64,
                configuration_sha256="d" * 64,
                requested={"max_plaintext_bytes": 805306368, "min_hold_seconds": 1800},
            )
        )

    def test_identity_drift_is_not_reused(self) -> None:
        cert = certificates.load(self._certificate(max_bytes=805306368))
        self.assertFalse(
            cert.satisfies(
                capability="sealed-sink",
                runtime_identity=IMAGE_B,
                implementation_sha256="c" * 64,
                configuration_sha256="d" * 64,
                requested={"max_plaintext_bytes": 1024, "min_hold_seconds": 1},
            )
        )


class StageResumeTests(CapsuleFixture):
    """Preparation resumes from retained artifacts and invalidates downstream on change."""

    def _prepare(self, spec: dict) -> compiler.PrepareResult:
        return compiler.prepare(load_spec(self.write_spec(spec)), self.workspace, offline=True)

    def test_unchanged_inputs_reuse_retained_stage_records(self) -> None:
        repo = self.make_repo("s", {"src/pkg/__init__.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(repo, base, base)
        first = self._prepare(spec)
        second = self._prepare(spec)
        self.assertEqual(first.stage_identities(), second.stage_identities())
        self.assertTrue(second.reused_stages, "an unchanged rerun must reuse stage records")

    def test_changed_input_invalidates_the_downstream_closure(self) -> None:
        repo = self.make_repo("s", {"src/pkg/__init__.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        spec = self.base_spec(repo, base, base)
        first = self._prepare(spec)

        changed = self.base_spec(repo, base, base, harness={"preload_modules": ["pkg"]})
        second = self._prepare(changed)
        self.assertNotEqual(
            first.stage_identities()[stages.STATIC_QUALIFIED],
            second.stage_identities()[stages.STATIC_QUALIFIED],
            "a changed harness input must invalidate downstream stage identities",
        )
        self.assertEqual(
            first.stage_identities()[stages.SEMANTIC_FROZEN],
            second.stage_identities()[stages.SEMANTIC_FROZEN],
            "semantic freeze must be independent of harness mechanics",
        )

    def test_status_reports_stage_from_retained_state_alone(self) -> None:
        repo = self.make_repo("s", {"src/pkg/__init__.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        self._prepare(self.base_spec(repo, base, base))
        reported = compiler.status(self.workspace)
        self.assertIn(reported["stage"], stages.ORDER)
        self.assertIn("tasks", reported)


class GeneratedArtifactTests(CapsuleFixture):
    """The Phase-D path must not require a handwritten per-task Dockerfile."""

    def test_runtime_artifacts_are_generated_with_producer_provenance(self) -> None:
        repo = self.make_repo("s", {"src/pkg/__init__.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        result = compiler.prepare(
            load_spec(self.write_spec(self.base_spec(repo, base, base))),
            self.workspace,
            offline=True,
        )
        for generated in result.generated_artifacts():
            self.assertIn("producer", generated.provenance)
            self.assertIn("inputs_sha256", generated.provenance)

    def test_generated_runner_profile_satisfies_the_existing_runner_validator(self) -> None:
        from tools.experiment.profile import PROFILE_SCHEMA, validate_profile_data

        repo = self.make_repo("s", {"src/pkg/__init__.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        result = compiler.prepare(
            load_spec(self.write_spec(self.base_spec(repo, base, base))),
            self.workspace,
            offline=True,
        )
        profile = result.task("T1").runner_profile
        self.assertEqual(profile["schema"], PROFILE_SCHEMA)
        self.assertEqual(validate_profile_data(profile, for_run=False), [])


class OfflineTests(CapsuleFixture):
    def test_offline_mode_never_reports_an_acquisition(self) -> None:
        repo = self.make_repo("s", {"src/pkg/__init__.py": ""})
        base = git(repo, "rev-parse", "HEAD")
        (self.root / "oracle.py").write_text("def test_discriminates():\n    assert True\n")
        result = compiler.prepare(
            load_spec(self.write_spec(self.base_spec(repo, base, base))),
            self.workspace,
            offline=True,
        )
        self.assertEqual(result.acquisitions, [])


if __name__ == "__main__":
    unittest.main()
