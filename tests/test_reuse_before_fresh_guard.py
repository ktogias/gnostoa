"""Focused regression for Work Item #194 reuse-vs-fresh qualification ordering.

Every fixture is synthetic. No Phase-D subject, hidden oracle, identification key,
receipt or execution is used. The test constructs a current, identity-bound OCI
qualification receipt for a synthetic node-vitest task and proves that approved
reuse consumes that receipt before any fresh-only adapter/backend guard or effect.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

try:
    # unittest discovery puts tests/ itself on sys.path, while repository-root
    # invocation imports the same helper through the tests namespace.
    from test_experiment_capsule import CapsuleFixture, git
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_experiment_capsule import CapsuleFixture, git

from tools.capsule import compiler, effect_claim, qualification, stages
from tools.capsule.spec import load_spec


class ReuseBeforeFreshGuardTests(CapsuleFixture):
    def _node_vitest_spec(self) -> dict:
        repo = self.make_repo(
            "subject", {"src/pkg/__init__.py": 'def render():\n    return "Basic "\n'}
        )
        base = git(repo, "rev-parse", "HEAD")
        ref = self.commit(
            repo,
            {"src/pkg/__init__.py": 'def render():\n    return "Basic"\n'},
            "fix",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n    assert pkg.render() == 'Basic'\n"
        )
        spec = self.base_spec(repo, base, ref, adapter="node-vitest")
        spec["tasks"][0]["reference"]["commit"] = ref
        spec["tasks"][0]["reference"]["tree"] = git(repo, "rev-parse", ref + "^{tree}")
        return spec

    def _current_synthetic_oci_receipt(
        self, spec: dict
    ) -> qualification.QualificationReceipt:
        loaded = load_spec(self.write_spec(spec))
        observed = compiler.prepare(
            loaded,
            self.workspace / "receipt-subject",
            offline=True,
            qualification_backend=qualification.OCI,
        )
        self.assertIsNotNone(observed.preflight_candidate_sha256, observed.blockers)
        self.assertIn(
            "base-reference-qualification-requires-preflight-authority",
            [blocker["code"] for blocker in observed.blockers],
        )

        bound = compiler._qualification_bound(loaded.tasks[0], observed.task("T1"))
        return qualification.QualificationReceipt(
            task="T1",
            backend=qualification.OCI,
            base=qualification.SubjectOutcome(
                subject="base",
                collected=True,
                passed=(),
                failed=("test_discriminates",),
                error_types={"test_discriminates": "AssertionError"},
                classification=qualification.MATCH,
                detail="synthetic current prior receipt",
            ),
            reference=qualification.SubjectOutcome(
                subject="reference",
                collected=True,
                passed=("test_discriminates",),
                failed=(),
                error_types={},
                classification=qualification.MATCH,
                detail="synthetic current prior receipt",
            ),
            bound=bound,
        )

    def test_exact_approved_node_vitest_oci_reuse_precedes_fresh_only_guard(
        self,
    ) -> None:
        spec = self._node_vitest_spec()
        receipt = self._current_synthetic_oci_receipt(spec)
        receipt_path = self.root / "prior-oci-receipt.json"
        receipt_path.write_text(json.dumps(receipt.as_json(), indent=2))
        spec["tasks"][0]["prior_qualification"] = {"receipt": str(receipt_path)}
        loaded = load_spec(self.write_spec(spec))
        workspace = self.workspace / "approved-reuse"

        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        self.assertIsNotNone(observed.preflight_candidate_sha256, observed.blockers)
        self.assertNotIn(
            "prior-qualification-receipt-not-current",
            [blocker["code"] for blocker in observed.blockers],
        )

        authority = self.authority(candidate=observed.preflight_candidate_sha256)
        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=AssertionError("fresh qualification effect was executed"),
        ):
            authorised = compiler.prepare(
                loaded,
                workspace,
                offline=True,
                preflight_authority=authority,
                qualification_backend=qualification.OCI,
            )

        self.assertEqual(
            authorised.status,
            stages.READY_FOR_OWNER_REVIEW,
            authorised.blockers,
        )
        self.assertTrue(authorised.task("T1").qualification_reused)
        self.assertNotIn(
            "oci-qualification-unsupported-for-adapter",
            [blocker["code"] for blocker in authorised.blockers],
        )
        self.assertFalse(
            (workspace / effect_claim.CLAIM_DIRECTORY).exists(),
            "an all-reuse candidate must not consume a fresh-effect claim",
        )

    def test_fresh_node_vitest_oci_remains_fail_closed(self) -> None:
        spec = self._node_vitest_spec()
        loaded = load_spec(self.write_spec(spec))
        workspace = self.workspace / "fresh-node"
        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        authority = self.authority(candidate=observed.preflight_candidate_sha256)

        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=AssertionError("unsupported fresh path reached an effect"),
        ):
            authorised = compiler.prepare(
                loaded,
                workspace,
                offline=True,
                preflight_authority=authority,
                qualification_backend=qualification.OCI,
            )

        self.assertEqual(authorised.status, "BLOCKED")
        self.assertIn(
            "oci-qualification-unsupported-for-adapter",
            [blocker["code"] for blocker in authorised.blockers],
        )
        self.assertFalse((workspace / effect_claim.CLAIM_DIRECTORY).exists())


if __name__ == "__main__":
    unittest.main()
