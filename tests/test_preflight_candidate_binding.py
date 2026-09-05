"""Focused characterization for Work Item 192.

A preflight authority currently binds an experiment name, not the prepared
qualification request. These tests reach STATIC_QUALIFIED only: no oracle is
executed, and every fixture is synthetic. No Phase-D task, subject, oracle,
identification key or evidence byte is used, and no Phase-D attempt is consumed.
"""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from tools.capsule import authority as authority_module
from tools.capsule import compiler
from tools.capsule import stages
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
            tasks=(("T1", "c" * 64),),
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


if __name__ == "__main__":
    unittest.main()
