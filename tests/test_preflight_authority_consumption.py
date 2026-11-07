"""Focused authority-consumption tests for Work Item #197.

Every fixture is synthetic. No Phase-D subject, oracle, key or retained evidence byte
is used. The tests patch the qualification effect path so no real hidden oracle or
runner/container execution occurs.
"""

from __future__ import annotations

import unittest
from unittest import mock

from tests.preflight_authority_consumption_support import ConsumptionFixture
from tools.capsule import compiler, effect_claim, qualification, stages

CONSUMED_CODE = "preflight-candidate-already-consumed"


class SyntheticAbort(RuntimeError):
    """Marks the point after the compiler has opened the qualification effect path."""


class FreshAuthorityConsumptionRedTests(ConsumptionFixture):
    def test_same_fresh_candidate_and_authority_cannot_open_effect_path_twice(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        granted = self.consumption_authority(candidate)

        effects: list[str] = []

        def reached(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("qualify_subjects")
            return [
                {
                    "task": "T1",
                    "code": "synthetic-stop-after-effect-entry",
                    "detail": "focused #197 RED",
                }
            ]

        with mock.patch.object(compiler, "qualify_subjects", side_effect=reached):
            first = self.prepare(authority=granted)
            second = self.prepare(authority=granted)

        self.assertEqual(first.preflight_candidate_sha256, candidate)
        self.assertEqual(second.preflight_candidate_sha256, candidate)
        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "one fresh candidate/authority must open at most one qualification transaction",
        )
        self.assertIn(CONSUMED_CODE, [b["code"] for b in second.blockers])

    def test_abort_after_first_effect_makes_same_candidate_non_replayable(self) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        granted = self.consumption_authority(candidate)

        effects: list[str] = []

        def abort_then_probe(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("qualify_subjects")
            if len(effects) == 1:
                raise SyntheticAbort("synthetic crash after effect path opens")
            return [
                {
                    "task": "T1",
                    "code": "synthetic-second-effect",
                    "detail": "the replay should never get here",
                }
            ]

        with mock.patch.object(
            compiler, "qualify_subjects", side_effect=abort_then_probe
        ):
            with self.assertRaises(SyntheticAbort):
                self.prepare(authority=granted)
            replay = self.prepare(authority=granted)

        self.assertEqual(replay.preflight_candidate_sha256, candidate)
        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "a crash/exception after the first effect must leave durable consumption state",
        )
        self.assertIn(CONSUMED_CODE, [b["code"] for b in replay.blockers])


class ReviewBlockerRedTests(ConsumptionFixture):
    def test_completed_identical_rerun_preserves_retained_success_without_new_effect(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        granted = self.consumption_authority(candidate)
        retained = qualification.load_receipt(self.prior_receipt(observed))
        effects: list[str] = []

        def qualify_once(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("qualify_subjects")
            return retained

        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify_once):
            first = self.prepare(authority=granted)
            first_state = compiler.status(self.workspace)
            second = self.prepare(authority=granted)
            second_state = compiler.status(self.workspace)

        self.assertEqual(first.status, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(first.stage, stages.READY_FOR_OWNER_REVIEW)
        self.assertIsNotNone(first.lock_identity)
        self.assertEqual(second.status, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(second.stage, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(second.lock_identity, first.lock_identity)
        self.assertEqual(second_state["lock_sha256"], first_state["lock_sha256"])
        self.assertIsNotNone(second_state["tasks"]["T1"]["qualification"])
        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "an unchanged completed rerun must reuse retained qualification",
        )

    def test_deterministic_unsupported_fresh_adapter_does_not_burn_claim(self) -> None:
        self.payload["tasks"][0]["adapter"] = "generic-command"
        self.payload["tasks"][0]["harness"] = {"extra_argv": ["true"]}
        observed = self.prepare(qualification_backend=qualification.OCI)
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None

        effects: list[str] = []

        def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("unexpected")
            raise AssertionError("deterministic unsupported adapter reached effect")

        with mock.patch.object(compiler, "qualify_subjects", side_effect=forbidden):
            result = self.prepare(
                authority=self.consumption_authority(candidate),
                qualification_backend=qualification.OCI,
            )

        self.assertIn(
            "oci-qualification-unsupported-for-adapter",
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertEqual(effects, [])
        claim = self.workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json"
        self.assertFalse(
            claim.exists(), "a deterministic zero-effect refusal must not consume"
        )

    def test_unknown_future_zero_effect_refusal_does_not_burn_claim(self) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        refusal = {
            "task": "T1",
            "code": "synthetic-future-pre-effect-refusal",
            "detail": "a future deterministic refusal unknown to today's code list",
        }
        effects: list[str] = []

        def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("unexpected")
            raise AssertionError("future zero-effect refusal reached qualification")

        with (
            mock.patch.object(
                compiler, "_deterministic_pre_effect_blocker", return_value=refusal
            ),
            mock.patch.object(compiler, "qualify_subjects", side_effect=forbidden),
        ):
            result = self.prepare(authority=self.consumption_authority(candidate))

        self.assertIn(
            "synthetic-future-pre-effect-refusal",
            [blocker["code"] for blocker in result.blockers],
        )
        self.assertEqual(effects, [])
        claim = self.workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json"
        self.assertFalse(
            claim.exists(),
            "any zero-effect refusal before the first effect must not consume",
        )


class ConsumptionBoundaryGuards(ConsumptionFixture):
    def test_authority_less_prepare_remains_effect_free_and_replayable(self) -> None:
        effects: list[str] = []

        def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("unexpected")
            raise AssertionError("authority-less prepare reached qualification")

        with mock.patch.object(compiler, "qualify_subjects", side_effect=forbidden):
            first = self.prepare()
            second = self.prepare()

        self.assertEqual(first.stage, stages.STATIC_QUALIFIED)
        self.assertEqual(
            first.preflight_candidate_sha256, second.preflight_candidate_sha256
        )
        self.assertEqual(effects, [])
        self.assertIn(
            "base-reference-qualification-requires-preflight-authority",
            [b["code"] for b in second.blockers],
        )

    def test_all_reuse_candidate_is_zero_effect_and_distinct_from_fresh(self) -> None:
        fresh = self.prepare()
        fresh_candidate = fresh.preflight_candidate_sha256
        self.assertIsNotNone(fresh_candidate)
        receipt = self.prior_receipt(fresh)

        reuse = self.prepare(receipt=receipt)
        reuse_candidate = reuse.preflight_candidate_sha256
        self.assertIsNotNone(reuse_candidate)
        self.assertNotEqual(fresh_candidate, reuse_candidate)
        assert reuse_candidate is not None
        granted = self.consumption_authority(reuse_candidate)

        effects: list[str] = []

        def forbidden(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("unexpected")
            raise AssertionError("all-reuse candidate reached fresh qualification")

        with mock.patch.object(compiler, "qualify_subjects", side_effect=forbidden):
            result = self.prepare(authority=granted, receipt=receipt)

        self.assertEqual(result.preflight_candidate_sha256, reuse_candidate)
        self.assertEqual(effects, [])
        self.assertTrue(result.task("T1").qualification_reused)


if __name__ == "__main__":
    unittest.main()
