"""RED regressions for retained consumption evidence after completed qualification.

All fixtures are synthetic. No Phase-D subject, oracle, key, evidence, runner or
container effect is used; ``qualify_subjects`` is patched to a synthetic receipt.
"""

from __future__ import annotations

import json
import unittest
from unittest import mock

from tools.capsule import authority as authority_module
from tools.capsule import compiler, effect_claim, qualification, stages
from tools.capsule.identity import digest_of
from tools.experiment.evidence import canonical_json_bytes

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


class RetainedConsumptionReviewRedTests(ConsumptionFixture):
    def _complete_once(self):  # type: ignore[no-untyped-def]
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        authority = self.authority(candidate)
        retained = qualification.load_receipt(self.prior_receipt(observed))
        effects: list[str] = []

        def qualify_once(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("qualify_subjects")
            return retained

        patcher = mock.patch.object(
            compiler, "qualify_subjects", side_effect=qualify_once
        )
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        del patched
        first = self.prepare(authority=authority)
        self.assertEqual(first.status, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(first.stage, stages.READY_FOR_OWNER_REVIEW)
        self.assertIsNotNone(first.lock_identity)
        return candidate, authority, effects

    def _retained_snapshot(self) -> tuple[dict[str, object], str, str, str]:
        state = compiler.status(self.workspace)
        state_bytes = (self.workspace / compiler.STATE_FILENAME).read_text()
        stages_bytes = (self.workspace / "stages.json").read_text()
        lock_bytes = (self.workspace / "experiment.lock").read_text()
        return state, state_bytes, stages_bytes, lock_bytes

    def _assert_retained_success_preserved(
        self,
        before: tuple[dict[str, object], str, str, str],
    ) -> None:
        before_state, before_state_bytes, before_stages, before_lock = before
        after_state = compiler.status(self.workspace)
        self.assertEqual(after_state["status"], before_state["status"])
        self.assertEqual(after_state["stage"], before_state["stage"])
        self.assertEqual(after_state["lock_sha256"], before_state["lock_sha256"])
        self.assertEqual(after_state["stage_receipts"], before_state["stage_receipts"])
        self.assertEqual(
            after_state["tasks"]["T1"]["qualification"],
            before_state["tasks"]["T1"]["qualification"],
        )
        self.assertEqual(
            (self.workspace / compiler.STATE_FILENAME).read_text(), before_state_bytes
        )
        self.assertEqual((self.workspace / "stages.json").read_text(), before_stages)
        self.assertEqual((self.workspace / "experiment.lock").read_text(), before_lock)

    def _assert_correct_authority_still_recovers(
        self,
        authority: authority_module.PreflightAuthority,
        effects: list[str],
    ) -> None:
        recovered = self.prepare(authority=authority)
        self.assertEqual(recovered.status, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(recovered.stage, stages.READY_FOR_OWNER_REVIEW)
        self.assertIsNotNone(recovered.lock_identity)
        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "a refusal after completed success must not force another qualification effect",
        )

    def test_completed_candidate_replay_under_second_authority_is_non_destructive(
        self,
    ) -> None:
        candidate, _, effects = self._complete_once()
        before = self._retained_snapshot()
        second_authority = authority_module.PreflightAuthority(
            id="auth-197-second-completed",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

        replay = self.prepare(authority=second_authority)

        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "a differently named authority must not reopen a completed candidate",
        )
        self.assertIn(
            effect_claim.ALREADY_CONSUMED,
            [blocker["code"] for blocker in replay.blockers],
        )
        self._assert_retained_success_preserved(before)

    def test_completed_fresh_qualification_requires_retained_claim(self) -> None:
        candidate, authority, effects = self._complete_once()
        before = self._retained_snapshot()
        claim = self.workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json"
        self.assertTrue(claim.is_file())
        claim.unlink()

        replay = self.prepare(authority=authority)

        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "missing consumption evidence must not reopen qualification",
        )
        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            effect_claim.INVALID_CLAIM,
            [blocker["code"] for blocker in replay.blockers],
        )
        self._assert_retained_success_preserved(before)

    def test_completed_fresh_qualification_rejects_tampered_retained_claim(
        self,
    ) -> None:
        candidate, authority, effects = self._complete_once()
        before = self._retained_snapshot()
        claim = self.workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json"
        payload = json.loads(claim.read_text())
        payload["authority_sha256"] = "0" * 64
        claim.write_bytes(canonical_json_bytes(payload))

        replay = self.prepare(authority=authority)

        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "tampered consumption evidence must not reopen qualification",
        )
        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            effect_claim.INVALID_CLAIM,
            [blocker["code"] for blocker in replay.blockers],
        )
        self._assert_retained_success_preserved(before)

    def test_completed_fresh_qualification_rejects_claim_authority_substitution(
        self,
    ) -> None:
        candidate, _, effects = self._complete_once()
        before = self._retained_snapshot()
        claim = self.workspace / effect_claim.CLAIM_DIRECTORY / f"{candidate}.json"
        replacement = authority_module.PreflightAuthority(
            id="auth-197-substituted",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )
        payload = json.loads(claim.read_text())
        replacement_payload = replacement.as_json()
        payload["authority"] = replacement_payload
        payload["authority_sha256"] = digest_of(replacement_payload)
        claim.write_bytes(canonical_json_bytes(payload))

        replay = self.prepare(authority=replacement)

        self.assertEqual(
            effects,
            ["qualify_subjects"],
            "self-consistent claim substitution must not reopen qualification",
        )
        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            effect_claim.INVALID_CLAIM,
            [blocker["code"] for blocker in replay.blockers],
        )
        self._assert_retained_success_preserved(before)

    def test_completed_success_survives_authority_less_prepare(self) -> None:
        _, authority, effects = self._complete_once()
        before = self._retained_snapshot()

        replay = self.prepare()

        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            "base-reference-qualification-requires-preflight-authority",
            [blocker["code"] for blocker in replay.blockers],
        )
        self.assertEqual(effects, ["qualify_subjects"])
        self._assert_retained_success_preserved(before)
        self._assert_correct_authority_still_recovers(authority, effects)

    def test_authority_refusal_does_not_preserve_ready_after_question_drift(
        self,
    ) -> None:
        candidate, _, effects = self._complete_once()
        before = compiler.status(self.workspace)
        self.assertEqual(before["status"], stages.READY_FOR_OWNER_REVIEW)
        self.assertIsNotNone(before["lock_sha256"])
        self.payload["experiment"]["question"] = "changed downstream question"

        replay = self.prepare()

        self.assertEqual(replay.preflight_candidate_sha256, candidate)
        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            "base-reference-qualification-requires-preflight-authority",
            [blocker["code"] for blocker in replay.blockers],
        )
        self.assertEqual(effects, ["qualify_subjects"])
        current = compiler.status(self.workspace)
        self.assertEqual(
            current["status"],
            "BLOCKED",
            "same preflight candidate must not make an old lock current after question drift",
        )
        self.assertEqual(current["stage"], stages.STATIC_QUALIFIED)
        self.assertIsNone(current["lock_sha256"])

    def test_completed_success_survives_out_of_scope_authority(self) -> None:
        candidate, authority, effects = self._complete_once()
        before = self._retained_snapshot()
        wrong_authority = authority_module.PreflightAuthority(
            id="auth-197-wrong-experiment-after-completion",
            experiment_id="OTHER",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

        replay = self.prepare(authority=wrong_authority)

        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            "preflight-authority-out-of-scope",
            [blocker["code"] for blocker in replay.blockers],
        )
        self.assertEqual(effects, ["qualify_subjects"])
        self._assert_retained_success_preserved(before)
        self._assert_correct_authority_still_recovers(authority, effects)

    def test_completed_success_survives_candidate_mismatch_authority(self) -> None:
        candidate, authority, effects = self._complete_once()
        before = self._retained_snapshot()
        wrong_authority = authority_module.PreflightAuthority(
            id="auth-197-wrong-candidate-after-completion",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256="0" * 64,
        )
        self.assertNotEqual(wrong_authority.preflight_candidate_sha256, candidate)

        replay = self.prepare(authority=wrong_authority)

        self.assertEqual(replay.status, "BLOCKED")
        self.assertIn(
            "preflight-authority-candidate-mismatch",
            [blocker["code"] for blocker in replay.blockers],
        )
        self.assertEqual(effects, ["qualify_subjects"])
        self._assert_retained_success_preserved(before)
        self._assert_correct_authority_still_recovers(authority, effects)


if __name__ == "__main__":
    unittest.main()
