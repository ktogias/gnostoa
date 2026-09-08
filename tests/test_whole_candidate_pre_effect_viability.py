"""Focused coverage for Work Item #206 candidate-wide pre-effect viability.

Every fixture is synthetic. No Phase-D subject, hidden oracle, identification key,
runner/container or real experiment effect is used. The qualification effect path is
patched so the tests can observe exactly where the compiler crosses the irreversible
candidate boundary.
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

    def _two_viable_fresh_tasks(self) -> dict:
        spec = self._two_fresh_tasks(blocker_first=False)
        for task in spec["tasks"]:
            task["adapter"] = "python-pytest"
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

    def test_all_viable_fresh_tasks_share_one_claim_and_run_in_order(self) -> None:
        loaded = load_spec(self.write_spec(self._two_viable_fresh_tasks()))
        workspace = self.workspace / "all-viable"
        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate, observed.blockers)
        assert candidate is not None

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
                preflight_authority=self.authority(candidate=candidate),
                qualification_backend=qualification.OCI,
            )

        self.assertEqual(result.status, stages.READY_FOR_OWNER_REVIEW, result.blockers)
        self.assertEqual(effects, ["T1", "T2"])
        claim_dir = workspace / effect_claim.CLAIM_DIRECTORY
        self.assertTrue((claim_dir / f"{candidate}.json").is_file())
        self.assertEqual(len(list(claim_dir.glob("*.json"))), 1)

    def test_mixed_reuse_and_fresh_checks_only_the_fresh_subset(self) -> None:
        spec = self._two_viable_fresh_tasks()
        seed_loaded = load_spec(self.write_spec(spec))
        seed = compiler.prepare(
            seed_loaded,
            self.workspace / "mixed-seed",
            offline=True,
            qualification_backend=qualification.OCI,
        )
        prior = self._qualified_receipt(
            task_id="T1",
            backend=qualification.OCI,
            bound=compiler._qualification_bound(seed_loaded.tasks[0], seed.task("T1")),
        )
        prior_path = self.root / "mixed-prior.json"
        prior_path.write_text(
            json.dumps(prior.as_json(), indent=2, sort_keys=True) + "\n"
        )

        mixed_spec = json.loads(json.dumps(spec))
        mixed_spec["tasks"][0]["prior_qualification"] = {"receipt": str(prior_path)}
        loaded = load_spec(self.write_spec(mixed_spec))
        workspace = self.workspace / "mixed"
        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate, observed.blockers)
        assert candidate is not None
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
                preflight_authority=self.authority(candidate=candidate),
                qualification_backend=qualification.OCI,
            )

        self.assertEqual(result.status, stages.READY_FOR_OWNER_REVIEW, result.blockers)
        self.assertTrue(result.task("T1").qualification_reused)
        self.assertFalse(result.task("T2").qualification_reused)
        self.assertEqual(effects, ["T2"])
        claim_dir = workspace / effect_claim.CLAIM_DIRECTORY
        self.assertTrue((claim_dir / f"{candidate}.json").is_file())
        self.assertEqual(len(list(claim_dir.glob("*.json"))), 1)

    def test_future_deterministic_refusal_is_settled_candidate_wide(self) -> None:
        loaded = load_spec(self.write_spec(self._two_viable_fresh_tasks()))
        workspace = self.workspace / "future-refusal"
        observed = compiler.prepare(
            loaded,
            workspace,
            offline=True,
            qualification_backend=qualification.OCI,
        )
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate, observed.blockers)
        assert candidate is not None
        refusal = {
            "task": "T2",
            "code": "synthetic-future-pre-effect-refusal",
            "detail": "future deterministic refusal known before effect",
        }
        effects: list[str] = []

        def guard(task, current, *, qualification_backend):  # type: ignore[no-untyped-def]
            del current, qualification_backend
            return refusal if task.id == "T2" else None

        def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("unexpected")
            raise AssertionError("future deterministic refusal reached an effect")

        with (
            mock.patch.object(
                compiler, "_deterministic_pre_effect_blocker", side_effect=guard
            ),
            mock.patch.object(compiler, "qualify_subjects", side_effect=forbidden),
        ):
            result = compiler.prepare(
                loaded,
                workspace,
                offline=True,
                preflight_authority=self.authority(candidate=candidate),
                qualification_backend=qualification.OCI,
            )

        self.assertIn(
            "synthetic-future-pre-effect-refusal",
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertEqual(effects, [])
        self.assertFalse(
            (workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json").exists()
        )


if __name__ == "__main__":
    unittest.main()
