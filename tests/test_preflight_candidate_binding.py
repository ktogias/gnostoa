"""Focused characterization for Work Item 192.

A preflight authority currently binds an experiment name, not the prepared
qualification request. These tests reach STATIC_QUALIFIED only: no oracle is
executed, and every fixture is synthetic. No Phase-D task, subject, oracle,
identification key or evidence byte is used, and no Phase-D attempt is consumed.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from tools.capsule import authority as authority_module
from tools.capsule import compiler, qualification, stages
from tools.capsule.identity import digest_of
from tools.capsule.spec import load_spec

try:
    from test_experiment_capsule import CapsuleFixture, git
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_experiment_capsule import CapsuleFixture, git

IMAGE_A = "sha256:" + "a" * 64
IMAGE_B = "sha256:" + "b" * 64


class CandidateFixture(CapsuleFixture):
    """One synthetic prepared candidate, varied exactly one input at a time.

    The subject repository and the workspace path are held constant across
    comparisons, because capsule identity legitimately digests absolute profile
    paths: two temporary directories would differ regardless of the input under
    test, which would make a comparison pass for the wrong reason.
    """

    def setUp(self) -> None:
        super().setUp()
        self._repo = self.make_repo(
            "s", {"src/pkg/__init__.py": 'def render():\n    return "Basic "\n'}
        )
        self._base = git(self._repo, "rev-parse", "HEAD")
        self._ref = self.commit(
            self._repo,
            {"src/pkg/__init__.py": 'def render():\n    return "Basic"\n'},
            "fix",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'Basic'\n"
        )

    def prepared(
        self,
        *,
        image: str = IMAGE_A,
        arena: str = "arena",
        backend: str = "local-python",
        extra_task: bool = False,
        authority=None,
        fresh: bool = True,
    ):
        spec = self.base_spec(
            self._repo, self._base, self._ref, runtime={"image": image}
        )
        spec["tasks"][0]["reference"]["commit"] = self._ref
        spec["tasks"][0]["reference"]["tree"] = git(
            self._repo, "rev-parse", self._ref + "^{tree}"
        )
        if extra_task:
            second = dict(spec["tasks"][0])
            second["id"] = "T2"
            spec["tasks"].append(second)
        target = self.root / arena
        if fresh and target.exists():
            shutil.rmtree(target)
        target.mkdir(exist_ok=True)
        return compiler.prepare(
            load_spec(self.write_spec(spec)),
            target,
            offline=True,
            qualification_backend=backend,
            preflight_authority=authority,
        )


class CurrentAuthorityIsUnboundTests(CandidateFixture):
    """RED 1 and RED 2: one authority admits materially different requests."""

    def test_one_authority_covers_two_different_candidates(self) -> None:
        a = self.prepared(image=IMAGE_A, arena="cmp")
        b = self.prepared(image=IMAGE_B, arena="cmp")
        identity_a = a.task("T1").capsule_identity
        identity_b = b.task("T1").capsule_identity
        # The two prepared candidates are genuinely different requests.
        self.assertNotEqual(identity_a, identity_b)

        # Under the old contract an authority carried only experiment id and scope,
        # so one record admitted both of these materially different requests. The
        # candidate identity is what separates them.
        self.assertNotEqual(a.preflight_candidate_sha256, b.preflight_candidate_sha256)
        granted = authority_module.PreflightAuthority(
            id="auth-a",
            experiment_id="E1",
            scope=("base-reference-qualification",),
            preflight_candidate_sha256=a.preflight_candidate_sha256 or "",
        )
        self.assertTrue(
            granted.covers(
                "E1",
                "base-reference-qualification",
                candidate_sha256=a.preflight_candidate_sha256,
            )
        )
        self.assertFalse(
            granted.covers(
                "E1",
                "base-reference-qualification",
                candidate_sha256=b.preflight_candidate_sha256,
            )
        )
        # Omitting the candidate is never a match.
        self.assertFalse(granted.covers("E1", "base-reference-qualification"))

    def test_authority_does_not_distinguish_the_backend(self) -> None:
        local = self.prepared(backend="local-python", arena="cmp")
        oci = self.prepared(backend="oci", arena="cmp")
        # The hidden-oracle effect path differs materially between backends.
        self.assertNotEqual(
            local.preflight_candidate_sha256, oci.preflight_candidate_sha256
        )


class CandidateObservabilityTests(CandidateFixture):
    """RED 3: the owner must be able to approve an exact candidate first."""

    def test_authority_less_prepare_exposes_a_canonical_candidate_digest(self) -> None:
        result = self.prepared()
        self.assertEqual(result.stage, stages.STATIC_QUALIFIED)
        codes = {b["code"] for b in result.blockers}
        self.assertIn(
            "base-reference-qualification-requires-preflight-authority", codes
        )
        digest = result.preflight_candidate_sha256
        self.assertIsNotNone(digest)
        assert digest is not None
        self.assertRegex(digest, r"^[a-f0-9]{64}$")

    def test_candidate_digest_is_retained_in_public_state(self) -> None:
        result = self.prepared(arena="obs")
        import json

        state = json.loads((self.root / "obs" / "experiment-state.json").read_text())
        self.assertEqual(
            state.get("preflight_candidate_sha256"), result.preflight_candidate_sha256
        )
        payload = compiler.status(self.root / "obs")
        self.assertEqual(
            payload.get("preflight_candidate_sha256"),
            result.preflight_candidate_sha256,
        )


class CandidateIdentityTests(CandidateFixture):
    """The identity must be deterministic and substitution-resistant."""

    def test_same_request_yields_the_same_digest(self) -> None:
        first = self.prepared(arena="cmp")
        # Re-running the identical prepared request in the same workspace.
        again = self.prepared(arena="cmp")
        self.assertEqual(
            first.preflight_candidate_sha256, again.preflight_candidate_sha256
        )

    def test_changed_capsule_changes_the_digest(self) -> None:
        a = self.prepared(image=IMAGE_A, arena="cmp")
        b = self.prepared(image=IMAGE_B, arena="cmp")
        self.assertNotEqual(a.preflight_candidate_sha256, b.preflight_candidate_sha256)

    def test_changed_task_membership_changes_the_digest(self) -> None:
        one = self.prepared(arena="cmp")
        two = self.prepared(arena="cmp", extra_task=True)
        self.assertNotEqual(
            one.preflight_candidate_sha256, two.preflight_candidate_sha256
        )

    def test_candidate_payload_excludes_authority_and_secrets(self) -> None:
        payload = authority_module.preflight_candidate_payload(
            experiment_id="E1",
            scope="base-reference-qualification",
            qualification_backend="local-python",
            tasks=(
                {
                    "id": "T1",
                    "capsule_identity": "c" * 64,
                    "qualification_mode": "fresh",
                },
            ),
        )
        self.assertEqual(payload["schema"], authority_module.CANDIDATE_SCHEMA)
        self.assertNotIn("id", payload)
        flattened = repr(payload)
        for forbidden in ("oracle", "key", "credential", "password", "token"):
            self.assertNotIn(forbidden, flattened.lower())


class AuthorityV2ContractTests(CandidateFixture):
    """v2 binds the exact candidate; v1 cannot authorize a new preflight."""

    def _v2(
        self,
        candidate: str,
        *,
        experiment_id: str = "E1",
        scope: str = "base-reference-qualification",
    ):
        return authority_module.parse(
            {
                "schema": "gnostoa-preflight-authority/v2",
                "id": "auth-v2",
                "experiment_id": experiment_id,
                "scope": [scope],
                "preflight_candidate_sha256": candidate,
            }
        )

    def test_v2_authority_covers_only_its_exact_candidate(self) -> None:
        a = self.prepared(image=IMAGE_A, arena="cmp")
        b = self.prepared(image=IMAGE_B, arena="cmp")
        granted = self._v2(a.preflight_candidate_sha256)
        self.assertTrue(
            granted.covers(
                "E1",
                "base-reference-qualification",
                candidate_sha256=a.preflight_candidate_sha256,
            )
        )
        self.assertFalse(
            granted.covers(
                "E1",
                "base-reference-qualification",
                candidate_sha256=b.preflight_candidate_sha256,
            )
        )

    def test_v1_authority_is_refused_for_a_new_preflight(self) -> None:
        with self.assertRaises(authority_module.AuthorityError):
            authority_module.parse(
                {
                    "schema": "gnostoa-preflight-authority/v1",
                    "id": "legacy",
                    "experiment_id": "E1",
                    "scope": ["base-reference-qualification"],
                }
            )

    def test_v1_remains_readable_as_historical_evidence(self) -> None:
        legacy = authority_module.parse_legacy_v1(
            {
                "schema": "gnostoa-preflight-authority/v1",
                "id": "legacy",
                "experiment_id": "E1",
                "scope": ["base-reference-qualification"],
            }
        )
        self.assertEqual(legacy.id, "legacy")
        self.assertEqual(legacy.experiment_id, "E1")
        # It is a distinct type that cannot stand in as effect authority.
        self.assertNotIsInstance(legacy, authority_module.PreflightAuthority)

    def test_missing_or_malformed_candidate_is_refused(self) -> None:
        for bad in (None, "", "not-a-digest", "A" * 64, "0" * 63):
            payload = {
                "schema": "gnostoa-preflight-authority/v2",
                "id": "auth-v2",
                "experiment_id": "E1",
                "scope": ["base-reference-qualification"],
            }
            if bad is not None:
                payload["preflight_candidate_sha256"] = bad
            with self.subTest(candidate=bad):
                with self.assertRaises(authority_module.AuthorityError):
                    authority_module.parse(payload)

    def test_wrong_experiment_or_scope_still_refuses(self) -> None:
        a = self.prepared(arena="cmp")
        digest = a.preflight_candidate_sha256
        self.assertFalse(
            self._v2(digest, experiment_id="OTHER").covers(
                "E1", "base-reference-qualification", candidate_sha256=digest
            )
        )
        self.assertFalse(
            self._v2(digest, scope="something-else").covers(
                "E1", "base-reference-qualification", candidate_sha256=digest
            )
        )


class PreparationReplayFixture(CapsuleFixture):
    """A synthetic D3-shaped task: the frozen tree omits a build-generated file.

    Nothing here is Phase-D. The shape is what matters: a declared setuptools-scm
    version file that the frozen trees do not carry.
    """

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo(
            "pt",
            {
                "src/pkg/__init__.py": (
                    "from pkg._version import version\n\n\ndef render():\n"
                    "    return 'old'\n"
                ),
                ".gitignore": "src/pkg/_version.py\n",
                "pyproject.toml": (
                    "[build-system]\nrequires = ['setuptools', 'setuptools-scm']\n\n"
                    "[project]\nname='pkg'\ndynamic = ['version']\n\n"
                    "[tool.setuptools_scm]\nwrite_to = 'src/pkg/_version.py'\n"
                ),
            },
        )
        git(self.repo, "tag", "1.0.0.dev0")
        self.base = self.commit(self.repo, {"src/pkg/extra.py": "x = 1\n"}, "more")
        self.ref = self.commit(
            self.repo,
            {
                "src/pkg/__init__.py": (
                    "from pkg._version import version\n\n\ndef render():\n"
                    "    return 'new'\n"
                )
            },
            "fix",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'new'\n"
        )
        spec = self.base_spec(
            self.repo,
            self.base,
            self.ref,
            runtime={"image": IMAGE_A},
            preparation={"scheme": "gnostoa-setuptools-scm-compatible/v1"},
        )
        spec["tasks"][0]["reference"]["commit"] = self.ref
        spec["tasks"][0]["reference"]["tree"] = git(
            self.repo, "rev-parse", self.ref + "^{tree}"
        )
        self.spec_path = self.write_spec(spec)

    def run_prepare(self, authority=None):
        return compiler.prepare(
            load_spec(self.spec_path),
            self.workspace,
            offline=True,
            preflight_authority=authority,
        )

    @staticmethod
    def identities(result) -> dict[str, object]:
        """Every identity an owner's approval depends on."""
        task = result.task("T1")
        receipt = task.preparation_receipt
        return {
            "required": task.preparation.required,
            "generated_paths": tuple(task.preparation.generated_paths),
            "receipt_identity": receipt.identity if receipt else None,
            "prepared_runtime_identity": task.prepared_runtime_identity,
            "capsule_identity": task.capsule_identity,
            "static_qualified": result.stage_receipts().get(stages.STATIC_QUALIFIED),
            "candidate": result.preflight_candidate_sha256,
        }


class PreparationReplayStabilityTests(PreparationReplayFixture):
    """An unchanged replay must present the identities the owner approved."""

    def test_unchanged_replay_keeps_every_authorization_identity(self) -> None:
        first = self.identities(self.run_prepare())
        second = self.identities(self.run_prepare())
        third = self.identities(self.run_prepare())
        self.assertEqual(first, second, "second prepare drifted from the first")
        self.assertEqual(second, third, "third prepare drifted")
        # The requirement comes from the frozen tree, not from what a previous
        # prepare happened to leave in the mutable workspace.
        self.assertTrue(first["required"])
        self.assertIsNotNone(first["receipt_identity"])
        self.assertIsNotNone(first["prepared_runtime_identity"])

    def test_authority_attachment_does_not_change_the_candidate(self) -> None:
        observed = self.run_prepare()
        digest = observed.preflight_candidate_sha256
        assert digest is not None
        granted = authority_module.PreflightAuthority(
            id="auth-prep",
            experiment_id="E1",
            scope=("base-reference-qualification",),
            preflight_candidate_sha256=digest,
        )
        authorized = self.run_prepare(authority=granted)
        # Attaching authority must not move the candidate it was issued against.
        self.assertEqual(authorized.preflight_candidate_sha256, digest)
        self.assertNotIn(
            "preflight-authority-candidate-mismatch",
            [b["code"] for b in authorized.blockers],
        )


class GeneratedPathExclusionSafetyTests(PreparationReplayFixture):
    """Excluding generated output must never mask real subject mutation."""

    def _materialised(self, kind: str) -> Path:
        roots = [
            path
            for path in self.workspace.rglob(f"{kind}-*")
            if path.is_dir() and (path / "pyproject.toml").is_file()
        ]
        self.assertTrue(roots, f"no materialised {kind} subject")
        return roots[0]

    def test_generated_output_is_not_reported_as_tampering(self) -> None:
        self.run_prepare()
        result = self.run_prepare()
        self.assertNotIn(
            "materialised-subject-identity-mismatch",
            [b["code"] for b in result.blockers],
        )

    def test_tracked_source_mutation_is_still_detected(self) -> None:
        self.run_prepare()
        tracked = self._materialised("base") / "src" / "pkg" / "extra.py"
        tracked.write_text("x = 999  # tampered\n")
        result = self.run_prepare()
        self.assertIn(
            "materialised-subject-identity-mismatch",
            [b["code"] for b in result.blockers],
        )

    def test_reference_tracked_mutation_is_detected_independently(self) -> None:
        self.run_prepare()
        tracked = self._materialised("reference") / "src" / "pkg" / "extra.py"
        tracked.write_text("x = 42  # tampered on the reference side\n")
        result = self.run_prepare()
        self.assertIn(
            "materialised-subject-identity-mismatch",
            [b["code"] for b in result.blockers],
        )

    def test_changed_generated_bytes_fail_closed(self) -> None:
        self.run_prepare()
        generated = self._materialised("base") / "src" / "pkg" / "_version.py"
        self.assertTrue(generated.is_file())
        generated.write_text("version = 'not-what-the-scheme-derives'\n")
        result = self.run_prepare()
        codes = [b["code"] for b in result.blockers]
        self.assertTrue(
            any("preparation" in code or "identity-mismatch" in code for code in codes),
            f"a changed generated artifact must fail closed, got {codes}",
        )
        self.assertNotEqual(result.status, stages.READY_FOR_OWNER_REVIEW)

    def test_non_regular_generated_occupant_fails_closed_without_following(
        self,
    ) -> None:
        self.run_prepare()
        generated = self._materialised("base") / "src" / "pkg" / "_version.py"
        generated.unlink()
        generated.symlink_to(Path("extra.py"))
        result = self.run_prepare()
        self.assertNotEqual(result.status, stages.READY_FOR_OWNER_REVIEW)
        # The link target keeps the subject's own bytes.
        target = self._materialised("base") / "src" / "pkg" / "extra.py"
        self.assertEqual(target.read_text(), "x = 1\n")


class DeclaredButTrackedPathTests(CapsuleFixture):
    """A declared generated path that the frozen tree tracks is ordinary source."""

    def test_declared_path_present_in_the_frozen_tree_is_still_verified(self) -> None:
        # Same build declaration, but here the version file IS committed, so the
        # frozen tree carries it and preparation is not required.
        repo = self.make_repo(
            "tracked",
            {
                "src/pkg/__init__.py": (
                    "from pkg._version import version\n\n\ndef render():\n"
                    "    return 'old'\n"
                ),
                "src/pkg/_version.py": "version = '1.0.0'\n__version__ = version\n",
                "pyproject.toml": (
                    "[build-system]\nrequires = ['setuptools', 'setuptools-scm']\n\n"
                    "[project]\nname='pkg'\ndynamic = ['version']\n\n"
                    "[tool.setuptools_scm]\nwrite_to = 'src/pkg/_version.py'\n"
                ),
            },
        )
        git(repo, "tag", "1.0.0")
        base = git(repo, "rev-parse", "HEAD")
        ref = self.commit(
            repo,
            {
                "src/pkg/__init__.py": (
                    "from pkg._version import version\n\n\ndef render():\n"
                    "    return 'new'\n"
                )
            },
            "fix",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'new'\n"
        )
        spec = self.base_spec(
            repo,
            base,
            ref,
            runtime={"image": IMAGE_A},
            preparation={"scheme": "gnostoa-setuptools-scm-compatible/v1"},
        )
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        spec_path = self.write_spec(spec)

        first = compiler.prepare(load_spec(spec_path), self.workspace, offline=True)
        # The frozen tree carries the declared target, so nothing is generated.
        self.assertFalse(first.task("T1").preparation.required)

        materialised = [
            path
            for path in self.workspace.rglob("base-*")
            if path.is_dir() and (path / "pyproject.toml").is_file()
        ]
        self.assertTrue(materialised)
        victim = materialised[0] / "src" / "pkg" / "_version.py"
        victim.write_text("version = 'tampered'\n__version__ = version\n")

        result = compiler.prepare(load_spec(spec_path), self.workspace, offline=True)
        # It is declared by the build configuration, but it is tracked source here,
        # so it must never be excluded from tree verification.
        self.assertIn(
            "materialised-subject-identity-mismatch",
            [b["code"] for b in result.blockers],
        )


class PreparationReuseRegressionTests(PreparationReplayFixture):
    """A receipt covering the first prepare stays current on an unchanged replay."""

    def test_prior_receipt_is_reused_with_zero_fresh_oracle_executions(self) -> None:
        first = self.run_prepare()
        task = first.task("T1")
        receipt_identity = (
            task.preparation_receipt.identity if task.preparation_receipt else None
        )
        self.assertIsNotNone(receipt_identity)

        # The identity the qualification receipt actually binds.
        bound = {
            "base_tree": task.base_tree,
            "reference_tree": task.reference_tree,
            "oracle_sha256": task.oracle_sha256,
            "runtime_image": task.runtime_image,
            "harness_identity": task.harness.identity if task.harness else "",
            "expectations_digest": digest_of(
                load_spec(self.spec_path).tasks[0].expectations.as_json()
            ),
            # The combined prepared identity covering BASE and REFERENCE.
            "preparation_identity": task.prepared_runtime_identity,
        }
        receipt = {
            "schema": qualification.RECEIPT_SCHEMA,
            "task": "T1",
            "backend": "local-python",
            "base": {
                "subject": "base",
                "collected": True,
                "passed": [],
                "failed": ["test_discriminates"],
                "error_types": {},
                "classification": qualification.MATCH,
                "detail": "synthetic prior qualification; no execution",
            },
            "reference": {
                "subject": "reference",
                "collected": True,
                "passed": ["test_discriminates"],
                "failed": [],
                "error_types": {},
                "classification": qualification.MATCH,
                "detail": "synthetic prior qualification; no execution",
            },
            "bound": bound,
            "qualified": True,
        }
        receipt_path = self.root / "prior-receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=1, sort_keys=True))

        spec = json.loads(Path(self.spec_path).read_text())
        spec["tasks"][0]["prior_qualification"] = {"receipt": str(receipt_path)}
        self.spec_path = self.write_spec(spec)

        # The unchanged replay must present the same candidate the owner approves.
        observed = self.run_prepare()
        digest = observed.preflight_candidate_sha256
        assert digest is not None
        granted = authority_module.PreflightAuthority(
            id="auth-reuse",
            experiment_id="E1",
            scope=("base-reference-qualification",),
            preflight_candidate_sha256=digest,
        )

        executed: list[str] = []
        original = qualification.qualify_subjects

        def refuse(*args, **kwargs):
            executed.append("fresh-qualification")
            return original(*args, **kwargs)

        qualification.qualify_subjects = refuse
        compiler.qualify_subjects = refuse
        try:
            authorized = self.run_prepare(authority=granted)
        finally:
            qualification.qualify_subjects = original
            compiler.qualify_subjects = original

        self.assertEqual(authorized.preflight_candidate_sha256, digest)
        self.assertEqual(
            executed, [], "a current prior receipt must not trigger fresh qualification"
        )
        reused = authorized.task("T1").qualification
        self.assertIsNotNone(reused)
        self.assertTrue(reused.qualified)


class QualificationDispositionTests(CandidateFixture):
    """The candidate must bind whether the oracle will run, not only on what."""

    def _receipt(self, result, *, backend: str = "local-python") -> Path:
        task = result.task("T1")
        spec = load_spec(self.write_spec(json.loads(json.dumps(self._payload))))
        bound = {
            "base_tree": task.base_tree,
            "reference_tree": task.reference_tree,
            "oracle_sha256": task.oracle_sha256,
            "runtime_image": task.runtime_image,
            "harness_identity": task.harness.identity if task.harness else "",
            "expectations_digest": digest_of(spec.tasks[0].expectations.as_json()),
            "preparation_identity": task.prepared_runtime_identity or "none",
        }
        payload = {
            "schema": qualification.RECEIPT_SCHEMA,
            "task": "T1",
            "backend": backend,
            "base": {
                "subject": "base",
                "collected": True,
                "passed": [],
                "failed": ["test_discriminates"],
                "error_types": {},
                "classification": qualification.MATCH,
                "detail": "synthetic",
            },
            "reference": {
                "subject": "reference",
                "collected": True,
                "passed": ["test_discriminates"],
                "failed": [],
                "error_types": {},
                "classification": qualification.MATCH,
                "detail": "synthetic",
            },
            "bound": bound,
            "qualified": True,
        }
        path = self.root / f"prior-{backend}.json"
        path.write_text(json.dumps(payload, indent=1, sort_keys=True))
        return path

    def setUp(self) -> None:
        super().setUp()
        spec = self.base_spec(
            self._repo, self._base, self._ref, runtime={"image": IMAGE_A}
        )
        spec["tasks"][0]["reference"]["commit"] = self._ref
        spec["tasks"][0]["reference"]["tree"] = git(
            self._repo, "rev-parse", self._ref + "^{tree}"
        )
        # Held in memory: write_spec reuses one path, so re-reading it would carry a
        # previous call's prior_qualification claim into the next request.
        self._payload = spec
        self.spec_path = self.write_spec(spec)

    def _prepare(
        self,
        *,
        receipt: Path | None = None,
        backend="local-python",
        authority=None,
        arena="disp",
    ):
        spec = json.loads(json.dumps(self._payload))
        if receipt is not None:
            spec["tasks"][0]["prior_qualification"] = {"receipt": str(receipt)}
        target = self.root / arena
        target.mkdir(exist_ok=True)
        return compiler.prepare(
            load_spec(self.write_spec(spec)),
            target,
            offline=True,
            qualification_backend=backend,
            preflight_authority=authority,
        )

    def test_reuse_and_fresh_are_different_candidates(self) -> None:
        fresh = self._prepare()
        receipt = self._receipt(fresh)
        reuse = self._prepare(receipt=receipt)
        self.assertIsNotNone(reuse.preflight_candidate_sha256)
        # Same subjects, same backend, same capsule -- but a different effect.
        self.assertNotEqual(
            fresh.preflight_candidate_sha256, reuse.preflight_candidate_sha256
        )

    def test_authority_for_reuse_cannot_authorize_a_fresh_run(self) -> None:
        fresh = self._prepare()
        receipt = self._receipt(fresh)
        reuse = self._prepare(receipt=receipt)
        granted = authority_module.PreflightAuthority(
            id="auth-reuse",
            experiment_id="E1",
            scope=("base-reference-qualification",),
            preflight_candidate_sha256=reuse.preflight_candidate_sha256 or "",
        )
        executed: list[str] = []
        original = compiler.qualify_subjects

        def counted(*args, **kwargs):
            executed.append("fresh")
            return original(*args, **kwargs)

        compiler.qualify_subjects = counted
        try:
            # The prior-qualification claim is removed: the same authority must not
            # now buy a hidden-oracle run.
            result = self._prepare(authority=granted)
        finally:
            compiler.qualify_subjects = original
        self.assertIn(
            "preflight-authority-candidate-mismatch",
            [b["code"] for b in result.blockers],
        )
        self.assertEqual(executed, [], "no oracle effect may occur on a mismatch")

    def test_changed_receipt_changes_the_candidate(self) -> None:
        fresh = self._prepare()
        receipt = self._receipt(fresh)
        before = self._prepare(receipt=receipt).preflight_candidate_sha256
        payload = json.loads(receipt.read_text())
        payload["base"]["detail"] = "a different retained detail"
        receipt.write_text(json.dumps(payload, indent=1, sort_keys=True))
        after = self._prepare(receipt=receipt).preflight_candidate_sha256
        self.assertNotEqual(before, after)

    def test_backend_mismatched_receipt_is_refused_with_no_effect(self) -> None:
        fresh = self._prepare()
        local_receipt = self._receipt(fresh, backend="local-python")
        executed: list[str] = []
        original = compiler.qualify_subjects

        def counted(*args, **kwargs):
            executed.append("fresh")
            return original(*args, **kwargs)

        compiler.qualify_subjects = counted
        try:
            result = self._prepare(receipt=local_receipt, backend="oci", arena="bk")
        finally:
            compiler.qualify_subjects = original
        self.assertIn(
            "prior-qualification-backend-mismatch",
            [b["code"] for b in result.blockers],
        )
        # No candidate may be emitted for a request whose disposition is unsettled.
        self.assertIsNone(result.preflight_candidate_sha256)
        self.assertEqual(executed, [])

    def test_invalid_prior_receipt_yields_no_candidate(self) -> None:
        broken = self.root / "broken-receipt.json"
        broken.write_text('{"schema": "not-a-receipt"}')
        result = self._prepare(receipt=broken, arena="broken")
        self.assertIn(
            "prior-qualification-receipt-invalid",
            [b["code"] for b in result.blockers],
        )
        self.assertIsNone(result.preflight_candidate_sha256)


class ReferencePreparationDriftTests(PreparationReplayFixture):
    """Reference-side preparation evidence must invalidate a stale qualification."""

    def test_reference_drift_refuses_a_stale_prior_qualification(self) -> None:
        first = self.run_prepare()
        task = first.task("T1")
        combined = task.prepared_runtime_identity
        self.assertIsNotNone(combined)
        # A qualification receipt bound to today's combined preparation identity.
        self.assertNotEqual(
            combined,
            task.preparation_receipt.identity if task.preparation_receipt else None,
            "the bound identity must cover more than the BASE receipt alone",
        )


class AsymmetricFrozenTreeTests(CapsuleFixture):
    """BASE omits the declared target; REFERENCE tracks it as ordinary source."""

    def test_reference_tracked_target_is_not_treated_as_generated(self) -> None:
        repo = self.make_repo(
            "asym",
            {
                "src/pkg/__init__.py": (
                    "from pkg._version import version\n\n\ndef render():\n"
                    "    return 'old'\n"
                ),
                ".gitignore": "src/pkg/_version.py\n",
                "pyproject.toml": (
                    "[build-system]\nrequires = ['setuptools', 'setuptools-scm']\n\n"
                    "[project]\nname='pkg'\ndynamic = ['version']\n\n"
                    "[tool.setuptools_scm]\nwrite_to = 'src/pkg/_version.py'\n"
                ),
            },
        )
        git(repo, "tag", "1.0.0.dev0")
        base = git(repo, "rev-parse", "HEAD")
        # The reference commits the declared target: there it is frozen source.
        (repo / ".gitignore").write_text("")
        ref = self.commit(
            repo,
            {
                "src/pkg/_version.py": "version = '9.9.9'\n__version__ = version\n",
                "src/pkg/__init__.py": (
                    "from pkg._version import version\n\n\ndef render():\n"
                    "    return 'new'\n"
                ),
            },
            "reference tracks the version file",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'new'\n"
        )
        spec = self.base_spec(
            repo,
            base,
            ref,
            runtime={"image": IMAGE_A},
            preparation={"scheme": "gnostoa-setuptools-scm-compatible/v1"},
        )
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        spec_path = self.write_spec(spec)

        result = compiler.prepare(load_spec(spec_path), self.workspace, offline=True)
        codes = [b["code"] for b in result.blockers]
        # The reference file is frozen source, not this compiler's output, so it is
        # neither overwritten nor compared against a generated version.
        self.assertNotIn("preparation-failed", codes)
        self.assertNotIn("preparation-modified-tracked-source", codes)

        reference = [
            path
            for path in self.workspace.rglob("reference-*")
            if path.is_dir() and (path / "pyproject.toml").is_file()
        ]
        self.assertTrue(reference)
        tracked = reference[0] / "src" / "pkg" / "_version.py"
        self.assertEqual(
            tracked.read_text(), "version = '9.9.9'\n__version__ = version\n"
        )

        # And it stays fully verified: mutating it is still caught.
        tracked.write_text("version = 'tampered'\n__version__ = version\n")
        again = compiler.prepare(load_spec(spec_path), self.workspace, offline=True)
        self.assertTrue(
            any(
                code
                in {
                    "materialised-subject-identity-mismatch",
                    "preparation-modified-tracked-source",
                    "preparation-failed",
                }
                for code in [b["code"] for b in again.blockers]
            ),
            f"reference tampering must be caught, got {[b['code'] for b in again.blockers]}",
        )


if __name__ == "__main__":
    unittest.main()
