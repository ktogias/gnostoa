"""Focused RED for Work Item #206 candidate-wide pre-effect viability.

Every fixture is synthetic. No Phase-D subject, hidden oracle, identification key,
runner/container or real experiment effect is used. The qualification effect path is
patched so the test can observe whether the compiler crosses the irreversible
candidate boundary before all fresh tasks' deterministic viability is settled.
"""

from __future__ import annotations

import unittest
from unittest import mock

try:
    from test_experiment_capsule import CapsuleFixture, git
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_experiment_capsule import CapsuleFixture, git

from tools.capsule import compiler, effect_claim, qualification
from tools.capsule.spec import load_spec


class WholeCandidatePreEffectViabilityTests(CapsuleFixture):
    def _two_fresh_tasks(self, *, blocker_first: bool) -> dict:
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
        first = spec["tasks"][0]
        second = dict(first)
        second["id"] = "T2"

        if blocker_first:
            first["adapter"] = "node-vitest"
            second["adapter"] = "python-pytest"
        else:
            first["adapter"] = "python-pytest"
            second["adapter"] = "node-vitest"

        spec["tasks"].append(second)
        return spec

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
                detail="synthetic #206 qualification",
            ),
            reference=qualification.SubjectOutcome(
                subject="reference",
                collected=True,
                passed=("test_discriminates",),
                failed=(),
                error_types={},
                classification=qualification.MATCH,
                detail="synthetic #206 qualification",
            ),
            bound=bound,
        )

    def _run(self, *, blocker_first: bool):
        loaded = load_spec(
            self.write_spec(self._two_fresh_tasks(blocker_first=blocker_first))
        )
        workspace = self.workspace / (
            "blocker-first" if blocker_first else "blocker-later"
        )

        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate, observed.blockers)
        assert candidate is not None
        authority = self.authority(candidate=candidate)

        effects: list[str] = []

        def synthetic_qualification(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args
            task_id = kwargs["task_id"]
            effects.append(task_id)
            return self._qualified_receipt(
                task_id=task_id,
                backend=kwargs["backend"],
                bound=kwargs["bound"],
            )

        with mock.patch.object(
            compiler, "qualify_subjects", side_effect=synthetic_qualification
        ):
            result = compiler.prepare(
                loaded,
                workspace,
                offline=True,
                preflight_authority=authority,
                qualification_backend=qualification.OCI,
            )

        claim = workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json"
        return result, effects, claim.exists()

    def test_later_deterministic_fresh_refusal_blocks_whole_candidate_before_effect(
        self,
    ) -> None:
        result, effects, claimed = self._run(blocker_first=False)

        self.assertIn(
            "oci-qualification-unsupported-for-adapter",
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertEqual(
            effects,
            [],
            "a later deterministic fresh-task refusal must be settled before any effect",
        )
        self.assertFalse(
            claimed,
            "a candidate-wide claim must not be consumed when any fresh task is known blocked",
        )

    def test_reversing_task_order_has_the_same_zero_effect_refusal(self) -> None:
        result, effects, claimed = self._run(blocker_first=True)

        self.assertIn(
            "oci-qualification-unsupported-for-adapter",
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertEqual(effects, [])
        self.assertFalse(claimed)


if __name__ == "__main__":
    unittest.main()
