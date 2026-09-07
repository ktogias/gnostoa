"""Concurrent prepares in one retained workspace: a loser must not overwrite a winner.

This file originally required the losing invocation to reach the create-only claim
and receive ALREADY_CONSUMED. That was a characterization of the superseded
arrival-order arbitration: under the approved reservation contract an *identical*
authorised caller no longer collides with the claim at all, it waits for the owner
and reconciles onto the committed transaction (see
``test_preflight_transaction_red.ConcurrentReconciliationTests``). The claim
collision is therefore no longer a property to assert.

What survives is the timeless safety statement the file existed for: an invocation
that did not perform the successful transaction must never replace its persisted
evidence with a stale or incomplete local view. It is restated here against a caller
the reservation contract genuinely refuses -- a differently authorised one -- and it
asserts outcomes rather than which primitive refused it.

The fixture is synthetic. ``qualify_subjects`` is patched to a retained receipt, so
no Phase-D material, hidden oracle, runner or container effect is used.
"""

from __future__ import annotations

import unittest
from unittest import mock

from tools.capsule import authority as authority_module
from tools.capsule import compiler, qualification, stages

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


class SameWorkspaceConcurrencyTests(ConsumptionFixture):
    def test_a_differently_authorised_caller_cannot_overwrite_winner_success(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        self.assertIsNotNone(candidate)
        assert candidate is not None
        retained = qualification.load_receipt(self.prior_receipt(observed))

        # Same prepared candidate, a different approval of it. The reservation
        # contract lets an identical authorised caller converge; this one is not
        # identical, so it has no standing to touch a transaction in flight.
        other = authority_module.PreflightAuthority(
            id="auth-197-second-approval",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

        effects: list[str] = []
        results: dict[str, compiler.PrepareResult] = {}

        def qualify_then_let_the_other_caller_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            del args, kwargs
            effects.append("winner")
            # Driven from inside the winner's effect: the other caller runs while
            # the winning transaction is past its irreversible boundary and has not
            # yet published.
            results["other"] = self.prepare(authority=other)
            return retained

        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=qualify_then_let_the_other_caller_run,
        ):
            winner = self.prepare(authority=self.authority(candidate))

        self.assertEqual(
            effects, ["winner"], "the losing caller must never open a second effect"
        )
        self.assertEqual(winner.status, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(winner.stage, stages.READY_FOR_OWNER_REVIEW)
        self.assertEqual(results["other"].status, "BLOCKED")
        # Non-vacuity: the refused caller reached the same prepared candidate, so it
        # was turned away by the transaction it collided with rather than by some
        # earlier static problem that would make this case prove nothing.
        self.assertEqual(results["other"].preflight_candidate_sha256, candidate)

        winner_state = compiler.status(self.workspace)
        self.assertEqual(winner_state["status"], stages.READY_FOR_OWNER_REVIEW)
        self.assertIsNotNone(winner_state["lock_sha256"])
        winner_stages = (self.workspace / "stages.json").read_text()
        winner_lock = (self.workspace / "experiment.lock").read_text()

        # The refused caller runs again after the winner has published. It still has
        # nothing that entitles it to replace successful retained evidence.
        late = self.prepare(authority=other)
        self.assertNotEqual(late.status, stages.READY_FOR_OWNER_REVIEW)

        final_state = compiler.status(self.workspace)
        self.assertEqual(final_state["status"], winner_state["status"])
        self.assertEqual(final_state["stage"], winner_state["stage"])
        self.assertEqual(final_state["lock_sha256"], winner_state["lock_sha256"])
        self.assertEqual(final_state["stage_receipts"], winner_state["stage_receipts"])
        self.assertEqual((self.workspace / "stages.json").read_text(), winner_stages)
        self.assertEqual((self.workspace / "experiment.lock").read_text(), winner_lock)


if __name__ == "__main__":
    unittest.main()
