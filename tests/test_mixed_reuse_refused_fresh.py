"""Regression coverage for Claude's #206 mixed-candidate review finding.

The fixture is synthetic. It proves that an approved exact-reuse task is not even
consumed in-memory when a peer fresh task is deterministically known to be refused.
No Phase-D material, runner/container or real qualification effect is used.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

try:
    from test_experiment_capsule import CapsuleFixture, git
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_experiment_capsule import CapsuleFixture, git

from tools.capsule import compiler, effect_claim, qualification, stages
from tools.capsule.spec import load_spec


class MixedReuseRefusedFreshTests(CapsuleFixture):
    @staticmethod
    def _qualified_receipt(
        *, task_id: str, backend: str, bound: dict[str, str]
    ) -> qualification.QualificationReceipt:
        return qualification.QualificationReceipt(
            task=task_id,
            backend=backend,
            base=qualification.SubjectOutcome(
                subject="base",
                collected=True,
                passed=(),
                failed=("test_discriminates",),
                error_types={"test_discriminates": "AssertionError"},
                classification=qualification.MATCH,
                detail="synthetic #206 mixed-refusal qualification",
            ),
            reference=qualification.SubjectOutcome(
                subject="reference",
                collected=True,
                passed=("test_discriminates",),
                failed=(),
                error_types={},
                classification=qualification.MATCH,
                detail="synthetic #206 mixed-refusal qualification",
            ),
            bound=bound,
        )

    def test_reuse_is_not_consumed_when_fresh_peer_is_deterministically_refused(
        self,
    ) -> None:
        repo = self.make_repo(
            "subject", {"src/pkg/__init__.py": "def render():\n    return 'old'\n"}
        )
        base = git(repo, "rev-parse", "HEAD")
        reference = self.commit(
            repo,
            {"src/pkg/__init__.py": "def render():\n    return 'new'\n"},
            "reference",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'new'\n"
        )

        spec = self.base_spec(repo, base, reference)
        reuse_task = spec["tasks"][0]
        reuse_task["adapter"] = "python-pytest"
        refused_fresh = dict(reuse_task)
        refused_fresh["id"] = "T2"
        refused_fresh["adapter"] = "node-vitest"
        spec["tasks"].append(refused_fresh)

        seed_loaded = load_spec(self.write_spec(spec))
        seed = compiler.prepare(
            seed_loaded,
            self.workspace / "mixed-refused-seed",
            offline=True,
            qualification_backend=qualification.OCI,
        )
        prior = self._qualified_receipt(
            task_id=reuse_task["id"],
            backend=qualification.OCI,
            bound=compiler._qualification_bound(
                seed_loaded.tasks[0], seed.task(reuse_task["id"])
            ),
        )
        prior_path = self.root / "mixed-refused-prior.json"
        prior_path.write_text(
            json.dumps(prior.as_json(), indent=2, sort_keys=True) + "\n"
        )

        mixed_spec = json.loads(json.dumps(spec))
        mixed_spec["tasks"][0]["prior_qualification"] = {"receipt": str(prior_path)}
        loaded = load_spec(self.write_spec(mixed_spec))
        workspace = self.workspace / "mixed-refused"
        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate, observed.blockers)
        assert candidate is not None

        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=AssertionError(
                "deterministically refused mixed candidate reached a qualification effect"
            ),
        ):
            result = compiler.prepare(
                loaded,
                workspace,
                offline=True,
                preflight_authority=self.authority(candidate=candidate),
                qualification_backend=qualification.OCI,
            )

        self.assertEqual(result.stage, stages.STATIC_QUALIFIED)
        self.assertIn(
            "oci-qualification-unsupported-for-adapter",
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertFalse(result.task(reuse_task["id"]).qualification_reused)
        self.assertIsNone(result.task(reuse_task["id"]).qualification)
        self.assertFalse(result.task("T2").qualification_reused)
        self.assertFalse(
            (workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
