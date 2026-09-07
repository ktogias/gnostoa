"""RED for the crash window between staging and a durable publication intent.

The intent makes an interrupted publication discoverable, but it is written inside
publish(), after the transaction's output is already complete and durable. There is
therefore a legitimate crash state the intent cannot describe:

    the effect happened, the claim is consumed,
    the reservation is installed,
    the staged output is complete and valid,
    and no publication intent exists yet

The existing forward-recovery coverage crashes while the commit record is written,
by which point the intent is durable. It proves that an intent plus staged evidence
is recoverable; it does not prove that a reservation plus staged evidence is. This
states the second, which is the contract already agreed: a dead reservation with a
complete valid staged transaction is finished forward with no new effect.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

It also states the asymmetry the intent path still lacks. A durable publication
intent is a record that a commit was under way. Failing to prove that commit can be
finished is not the same as proving it is safe to throw away: with the effect claim
already consumed, discarding the staged output leaves an effect that happened, no
evidence of it, and no permission to run it again -- the exact failure class the
transaction model exists to prevent. The no-intent fallback already refuses and
preserves in that situation; the intent path must do the same.

At head 6190aac60005afb1f2271c6ff6d98ddc8e52b74d the first case is GREEN and the
unresolved-intent cases are expected to be RED.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock

from tools.capsule import compiler, qualification, retained_commit

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


def _receipt(task_id: str, bound: dict[str, str]) -> qualification.QualificationReceipt:
    base = qualification.SubjectOutcome(
        subject="base",
        collected=True,
        passed=(),
        failed=("test_discriminates",),
        error_types={},
        classification=qualification.MATCH,
        detail="synthetic",
    )
    reference = qualification.SubjectOutcome(
        subject="reference",
        collected=True,
        passed=("test_discriminates",),
        failed=(),
        error_types={},
        classification=qualification.MATCH,
        detail="synthetic",
    )
    return qualification.QualificationReceipt(
        task=task_id,
        backend="local-python",
        base=base,
        reference=reference,
        bound=bound,
    )


class StagedWithoutIntentRecoveryTests(ConsumptionFixture):
    """A transaction that died before it could say it was publishing."""

    def test_complete_staging_under_a_dead_reservation_is_finished_forward(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        effects: list[str] = []

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        # The effect patch spans the retry, so an effect opened during recovery is
        # counted rather than escaping to the real implementation.
        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(
                retained_commit,
                "_write_publication_intent",
                side_effect=RuntimeError("died before the intent became durable"),
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)

            # Exactly the retained state the intent cannot describe.
            reservation = retained_commit.read_reservation(self.workspace)
            self.assertIsNotNone(reservation, "the reservation must still be there")
            assert reservation is not None
            self.assertIsNone(
                retained_commit.read_publication_intent(self.workspace),
                "the transaction died before any intent became durable",
            )
            staged = retained_commit.read_staged(
                self.workspace, reservation.transaction_id
            )
            self.assertIsNotNone(
                staged, "its output must be complete and durable on disk"
            )
            self.assertEqual(effects, ["effect"], "the oracle ran exactly once")

            recovered = self.prepare(authority=authority)

        self.assertEqual(
            effects,
            ["effect"],
            "recovery must never repeat an irreversible effect that already ran",
        )
        self.assertEqual(
            recovered.status,
            "READY_FOR_OWNER_REVIEW",
            "a dead reservation with complete valid staged output must be finished "
            "forward, not swept away while its effect claim keeps the candidate "
            "consumed",
        )
        record = json.loads(
            (self.workspace / retained_commit.COMMIT_RECORD_FILENAME).read_text()
        )
        self.assertEqual(
            record["transaction_id"],
            reservation.transaction_id,
            "the staged transaction itself must become the committed one",
        )
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )


class UnresolvedIntentTests(ConsumptionFixture):
    """A durable intent is never silently abandoned: prove it, or keep it."""

    def _interrupted_before_publishing(self, effects: list[str]) -> Any:
        """Leave a durable intent whose transaction touched no canonical byte."""
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        real_write = retained_commit._write_atomic

        def crash(path: Any, payload: bytes) -> None:
            if (
                path.parent == self.workspace
                and path.name == retained_commit.LEDGER_FILENAME
            ):
                raise RuntimeError("crash after the intent, before publishing")
            return real_write(path, payload)

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(retained_commit, "_write_atomic", side_effect=crash):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)
        intent = retained_commit.read_publication_intent(self.workspace)
        self.assertIsNotNone(intent, "the intent must have become durable")
        assert intent is not None
        self.assertEqual(effects, ["effect"], "the oracle ran exactly once")
        return intent, authority

    def _assert_preserved(self, intent: Any, before: str, effects: list[str]) -> None:
        refused = self.prepare()
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in refused.blockers],
        )
        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertIsNotNone(
            retained_commit.read_publication_intent(self.workspace),
            "the intent must survive as evidence of an unfinished commit",
        )
        self.assertTrue(
            (
                retained_commit.staging_directory(self.workspace, intent.transaction_id)
                / retained_commit.MANIFEST_FILENAME
            ).is_file(),
            "the staged output must survive as evidence",
        )
        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            before,
            "nothing may be published from evidence that cannot be trusted",
        )

    def test_an_intent_whose_staged_output_is_incomplete_is_kept_not_discarded(
        self,
    ) -> None:
        """The manifest still matches; a member it commits to no longer does.

        read_staged rightly reports that as "not a recovery source". Treating that
        as "safe to delete" destroys the only record of a consumed effect.
        """
        effects: list[str] = []
        intent, _ = self._interrupted_before_publishing(effects)
        before = (self.workspace / "experiment-state.json").read_text()

        member = (
            retained_commit.staging_directory(self.workspace, intent.transaction_id)
            / retained_commit.STATE_FILENAME
        )
        member.write_text('{"tampered": true}\n')
        self.assertIsNone(
            retained_commit.read_staged(self.workspace, intent.transaction_id)
        )

        self._assert_preserved(intent, before, effects)

    def test_an_intent_that_cannot_be_resolved_either_way_is_kept_not_discarded(
        self,
    ) -> None:
        """Complete, self-consistent, and based on a workspace that no longer exists.

        The publication can neither be finished -- what it was based on is gone --
        nor shown to have finished, since the committed record names somebody else.
        Discarding it on the strength of "not publishable" is what destroys the
        evidence of an effect that is already consumed.
        """
        effects: list[str] = []
        intent, _ = self._interrupted_before_publishing(effects)
        before = (self.workspace / "experiment-state.json").read_text()

        # Another transaction appears to have committed since. The staged output is
        # untouched and still matches its reservation.
        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        record["transaction_id"] = "e" * 32
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        self.assertIsNotNone(
            retained_commit.read_staged(self.workspace, intent.transaction_id)
        )

        self._assert_preserved(intent, before, effects)

    def test_an_intent_contradicted_by_its_reservation_is_kept_not_discarded(
        self,
    ) -> None:
        """Everything staged is intact; the reservation describes another request."""
        effects: list[str] = []
        intent, _ = self._interrupted_before_publishing(effects)
        before = (self.workspace / "experiment-state.json").read_text()

        path = self.workspace / retained_commit.RESERVATION_FILENAME
        reservation = json.loads(path.read_text())
        reservation["candidate_sha256"] = "7" * 64
        path.write_text(json.dumps(reservation, indent=2, sort_keys=True) + "\n")
        self.assertIsNotNone(
            retained_commit.read_staged(self.workspace, intent.transaction_id),
            "the staged output itself is untouched and complete",
        )

        self._assert_preserved(intent, before, effects)


if __name__ == "__main__":
    unittest.main()
