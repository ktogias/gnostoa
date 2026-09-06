"""RED characterization for concurrent fresh prepares in one retained workspace.

The fixture is synthetic. ``qualify_subjects`` is patched to a retained receipt, so no
Phase-D material, hidden oracle, runner or container effect is used.
"""

from __future__ import annotations

import threading
import unittest
from unittest import mock

from tools.capsule import compiler, effect_claim, qualification, stages

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


class SameWorkspaceConcurrencyRedTests(ConsumptionFixture):
    def test_losing_concurrent_prepare_cannot_overwrite_winner_success(self) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        authority = self.authority(candidate)
        retained = qualification.load_receipt(self.prior_receipt(observed))
        spec = self._spec()

        effect_started = threading.Event()
        release_effect = threading.Event()
        loser_saw_consumed = threading.Event()
        release_loser = threading.Event()
        effects: list[str] = []
        results: dict[str, compiler.PrepareResult] = {}
        errors: dict[str, BaseException] = {}

        original_claim = effect_claim.claim_fresh_candidate

        def controlled_claim(*args, **kwargs):  # type: ignore[no-untyped-def]
            try:
                return original_claim(*args, **kwargs)
            except effect_claim.EffectClaimError as exc:
                if exc.code != effect_claim.ALREADY_CONSUMED:
                    raise
                loser_saw_consumed.set()
                if not release_loser.wait(timeout=20):
                    raise TimeoutError("losing prepare was not released") from exc
                raise

        def qualify_once(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append(threading.current_thread().name)
            effect_started.set()
            if not release_effect.wait(timeout=20):
                raise TimeoutError("winning qualification was not released")
            return retained

        def run_prepare(name: str) -> None:
            try:
                results[name] = compiler.prepare(
                    spec,
                    self.workspace,
                    offline=True,
                    preflight_authority=authority,
                    qualification_backend=qualification.LOCAL_PYTHON,
                )
            except BaseException as exc:  # retain thread failures for the test thread
                errors[name] = exc

        with (
            mock.patch.object(
                effect_claim, "claim_fresh_candidate", side_effect=controlled_claim
            ),
            mock.patch.object(compiler, "qualify_subjects", side_effect=qualify_once),
        ):
            winner_thread = threading.Thread(
                target=run_prepare, args=("winner",), name="winner"
            )
            winner_thread.start()
            self.assertTrue(
                effect_started.wait(timeout=20),
                "winning prepare never crossed the claimed effect boundary",
            )

            loser_thread = threading.Thread(
                target=run_prepare, args=("loser",), name="loser"
            )
            loser_thread.start()
            self.assertTrue(
                loser_saw_consumed.wait(timeout=20),
                "losing prepare never observed the winner's create-only claim",
            )

            # The loser is now paused inside the claim primitive. Let the winner
            # finish and persist successful retained evidence first.
            release_effect.set()
            winner_thread.join(timeout=20)
            self.assertFalse(winner_thread.is_alive(), "winning prepare did not finish")
            if "winner" in errors:
                raise errors["winner"]

            winner = results["winner"]
            self.assertEqual(winner.status, stages.READY_FOR_OWNER_REVIEW)
            self.assertEqual(winner.stage, stages.READY_FOR_OWNER_REVIEW)
            winner_state = compiler.status(self.workspace)
            winner_stages = (self.workspace / "stages.json").read_text()
            winner_lock = (self.workspace / "experiment.lock").read_text()

            # Only now let the stale losing invocation propagate ALREADY_CONSUMED.
            release_loser.set()
            loser_thread.join(timeout=20)
            self.assertFalse(loser_thread.is_alive(), "losing prepare did not finish")
            if "loser" in errors:
                raise errors["loser"]

        loser = results["loser"]
        self.assertEqual(effects, ["winner"], "the loser must never open a second effect")
        self.assertIn(
            effect_claim.ALREADY_CONSUMED,
            [blocker["code"] for blocker in loser.blockers],
        )

        # A losing invocation must not replace the already-persisted successful
        # transaction with its stale/incomplete local snapshot.
        final_state = compiler.status(self.workspace)
        self.assertEqual(final_state["status"], winner_state["status"])
        self.assertEqual(final_state["stage"], winner_state["stage"])
        self.assertEqual(final_state["lock_sha256"], winner_state["lock_sha256"])
        self.assertEqual(final_state["stage_receipts"], winner_state["stage_receipts"])
        self.assertEqual((self.workspace / "stages.json").read_text(), winner_stages)
        self.assertEqual((self.workspace / "experiment.lock").read_text(), winner_lock)


if __name__ == "__main__":
    unittest.main()
