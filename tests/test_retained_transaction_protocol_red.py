"""RED protocol packet for the retained-transaction model at ccacddc5.

The reservation model closed the five effect/liveness invariants of
``test_preflight_transaction_red``, but five protocol properties it claims are not
yet held. Each is stated as an observable workspace outcome so that any correct
protocol satisfies it:

  * a reservation must be taken against the snapshot that is current when it is
    taken, not one that has since been superseded;
  * a reservation that became live between a contender's observation and its
    acquisition must not be replaced by that contender;
  * a transaction interrupted after its irreversible effect must be finishable
    forward from durable staged evidence, without repeating the effect;
  * a workspace that has committed transactionally must not read back as one that
    never had a transaction record when that record is removed;
  * an identical authorised waiter must converge onto the winner's committed
    transaction rather than commit a second, no-effect one of its own.

The safety cases are driven from deterministic seams inside the first invocation.
The convergence case needs genuine concurrency, because the waiter's required
behaviour is to still be waiting while the owner holds the transaction; it is
ordered by events signalled from inside the waiter and asserts outcomes, never
timings. All fixtures are synthetic and the qualification effect is patched and
counted; no Phase-D material and no hidden oracle participates.

An abandoned pre-claim reservation is also guarded here. It holds already, and is
stated so that the recovery work cannot quietly turn a recoverable abandonment into
a permanently consumed candidate.

At head ccacddc5de8feba1614d96713863129fbea062fc the five properties above are
expected to be RED and the abandonment guard green.
"""

from __future__ import annotations

import contextlib
import json
import threading
import unittest
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock

from tools.capsule import authority as authority_module
from tools.capsule import compiler, effect_claim, qualification, retained_commit

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


class ProtocolFixture(ConsumptionFixture):
    def committed_generation(self) -> int | None:
        path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        if not path.is_file():
            return None
        payload: dict[str, Any] = json.loads(path.read_text())
        generation = payload["generation"]
        assert isinstance(generation, int)
        return generation

    def prepared_candidate(self) -> str:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        return candidate

    def authorised_candidate(self) -> Any:
        return self.authority(self.prepared_candidate())

    @staticmethod
    def second_approval(candidate: str) -> authority_module.PreflightAuthority:
        """A different owner approval of the same prepared candidate."""
        return authority_module.PreflightAuthority(
            id="auth-197-second-approval",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

    def retained_reservation(self) -> dict[str, Any] | None:
        path = self.workspace / retained_commit.RESERVATION_FILENAME
        if not path.is_file():
            return None
        payload: dict[str, Any] = json.loads(path.read_text())
        return payload


class ReservationAtomicityTests(ProtocolFixture):
    """A reservation is a claim on a specific committed state, not on a name."""

    def test_a_reservation_names_the_snapshot_that_is_current_when_taken(self) -> None:
        """Observing "no reservation" and taking one are not one decision.

        Between the two, another transaction can commit. A reservation created
        blindly afterwards is anchored to a snapshot that no longer exists, and its
        holder then skips the stale-snapshot check on the strength of holding it.
        """
        authority = self.authorised_candidate()
        intervened: list[str] = []
        observed_pairs: list[tuple[str | None, str | None]] = []

        real_liveness = retained_commit.owner_liveness

        @contextlib.contextmanager
        def liveness_then_let_another_transaction_commit(
            root: Path, transaction_id: str
        ) -> Iterator[None]:
            with real_liveness(root, transaction_id):
                if not intervened:
                    intervened.append("committed")
                    # A zero-effect invocation commits in the window between the
                    # reserving caller's observation and its own reservation.
                    self.prepare()
                yield

        real_write = retained_commit.write_reservation

        def record_what_it_was_based_on(
            root: Path, reservation: retained_commit.Reservation
        ) -> None:
            current = retained_commit.read_committed(root)
            observed_pairs.append(
                (reservation.base_identity, current.identity if current else None)
            )
            return real_write(root, reservation)

        with (
            mock.patch.object(
                compiler,
                "qualify_subjects",
                side_effect=lambda *a, **k: _receipt(
                    k.get("task_id", "T1"), dict(k.get("bound") or {})
                ),
            ),
            mock.patch.object(
                retained_commit,
                "owner_liveness",
                liveness_then_let_another_transaction_commit,
            ),
            mock.patch.object(
                retained_commit,
                "write_reservation",
                side_effect=record_what_it_was_based_on,
            ),
        ):
            self.prepare(authority=authority)

        self.assertEqual(
            intervened, ["committed"], "the intervening commit never happened"
        )
        self.assertEqual(len(observed_pairs), 1)
        based_on, current = observed_pairs[0]
        self.assertEqual(
            based_on,
            current,
            "a reservation must be created against the committed snapshot that is "
            "current at that moment, revalidated under the coordination lock, not "
            "against one the caller observed earlier and that has since advanced",
        )


class ForwardRecoveryTests(ProtocolFixture):
    """Recovery after the effect boundary is forward-only -- and must be possible."""

    def test_an_interrupted_transaction_finishes_forward_without_a_second_effect(
        self,
    ) -> None:
        """Fail-closed detection is not recoverability.

        A crash after the irreversible qualification and after the transaction's
        output was staged leaves evidence that exists and can never be produced
        again. An identical authorised caller must be able to complete that
        transaction from what was staged, opening no new effect.
        """
        authority = self.authorised_candidate()
        effects: list[str] = []

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        real_write = retained_commit._write_atomic

        def crash_before_recording(path: Path, payload: bytes) -> None:
            if path.name == retained_commit.COMMIT_RECORD_FILENAME:
                raise RuntimeError("crash between staging and recording the commit")
            return real_write(path, payload)

        # The effect patch spans the recovery attempt, so a second effect opened
        # during recovery is counted rather than escaping to the real implementation.
        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(
                retained_commit, "_write_atomic", side_effect=crash_before_recording
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)
            recovered = self.prepare(authority=authority)

        self.assertEqual(
            effects,
            ["effect"],
            "recovery must never repeat an irreversible effect that already ran",
        )
        self.assertEqual(
            recovered.status,
            "READY_FOR_OWNER_REVIEW",
            "a transaction interrupted after its effect must be finishable forward "
            "from durable staged evidence rather than left permanently unusable",
        )
        current = compiler.status(self.workspace)
        self.assertEqual(current["status"], "READY_FOR_OWNER_REVIEW")
        self.assertEqual(current["lock_sha256"], recovered.lock_identity)


class CommitRecordProvenanceTests(ProtocolFixture):
    """Absence of a record means "never transactional", which must be provable."""

    def test_a_transactional_workspace_cannot_lose_its_record_and_read_as_legacy(
        self,
    ) -> None:
        """Removing the record must not restore trust in the state it described.

        A missing record is indistinguishable from a workspace that predates the
        transaction model unless the canonical state itself says it was written
        under one.
        """
        authority = self.authorised_candidate()
        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=lambda *a, **k: _receipt(
                k.get("task_id", "T1"), dict(k.get("bound") or {})
            ),
        ):
            self.prepare(authority=authority)
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )

        (self.workspace / retained_commit.COMMIT_RECORD_FILENAME).unlink()

        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)
        self.assertEqual(
            compiler.status(self.workspace)["status"],
            "BLOCKED",
            "a workspace that has committed transactionally must not read back as "
            "one that never had a record once that record is removed",
        )

    def test_a_workspace_with_no_transaction_history_still_reads_as_before(
        self,
    ) -> None:
        """Backward compatibility guard, green now and required to stay green.

        Retained evidence produced before the transaction model has no record and
        never will. Making a missing record inconsistent must not reclassify it.
        """
        legacy = self.root / "legacy-workspace"
        legacy.mkdir()
        (legacy / "experiment-state.json").write_text(
            json.dumps(
                {
                    "schema": "gnostoa-capsule-state/v1",
                    "producer": compiler.PRODUCER,
                    "status": "READY_FOR_OWNER_REVIEW",
                    "stage": "READY_FOR_OWNER_REVIEW",
                    "blockers": [],
                    "reused_certificates": [],
                    "stage_receipts": {},
                    "lock_sha256": "0" * 64,
                    "preflight_candidate_sha256": None,
                    "tasks": {},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        self.assertEqual(
            compiler.status(legacy)["status"],
            "READY_FOR_OWNER_REVIEW",
            "a workspace with no transaction history must read exactly as it did "
            "before the transaction model existed",
        )


class SingleCommittedTransactionTests(ProtocolFixture):
    """Converging on the same content is not converging on the same transaction."""

    def test_an_identical_waiter_does_not_commit_a_second_transaction(self) -> None:
        """One authorised effect must produce exactly one committed transaction.

        A waiter that reproduces byte-identical output and then publishes it under
        its own transaction advances the committed history for work it did not do.
        Asserting equal locks and equal receipts cannot see that; asserting how many
        times the committed state advanced can.
        """
        authority = self.authorised_candidate()

        owner_in_effect = threading.Event()
        waiter_observed_owner = threading.Event()
        observed_by: list[str] = []
        effects: list[str] = []
        results: dict[str, Any] = {}
        roles: dict[int, str] = {}
        threads: dict[str, threading.Thread] = {}

        real_read_reservation = retained_commit.read_reservation

        def role_of() -> str:
            return roles.get(threading.get_ident(), "unattributed")

        def observation_seam(root: Path) -> Any:
            reservation = real_read_reservation(root)
            # The owner is released only once the waiter has observed its live
            # reservation. Signalling earlier -- at the candidate computation, say --
            # lets the owner finish and clear the reservation before the waiter looks,
            # after which the waiter holds a pre-completion snapshot and is refused.
            # That is a real defect, but a different one, and the interleaving under
            # test must be pinned rather than decided by the scheduler.
            if role_of() == "waiter" and reservation is not None:
                if not observed_by:
                    observed_by.append("waiter")
                waiter_observed_owner.set()
            return reservation

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append(role_of())
            if role_of() == "owner":
                owner_in_effect.set()
                waiter_observed_owner.wait(timeout=30)
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        shared_spec = self._spec()
        before = self.committed_generation()
        self.assertIsNotNone(before)
        assert before is not None

        def run(role: str) -> None:
            roles[threading.get_ident()] = role
            try:
                results[role] = compiler.prepare(
                    shared_spec,
                    self.workspace,
                    offline=True,
                    preflight_authority=authority,
                )
            except Exception as exc:  # recorded rather than raised across threads
                results[f"{role}_error"] = exc

        with (
            mock.patch.object(
                retained_commit, "read_reservation", side_effect=observation_seam
            ),
            mock.patch.object(compiler, "qualify_subjects", side_effect=qualify),
        ):
            threads["owner"] = threading.Thread(target=run, args=("owner",))
            threads["owner"].start()
            self.assertTrue(
                owner_in_effect.wait(timeout=30), "the owner never entered its effect"
            )
            threads["waiter"] = threading.Thread(target=run, args=("waiter",))
            threads["waiter"].start()
            waiter_observed_owner.wait(timeout=30)
            # Fallback release so a protocol that never observes cannot hang the
            # owner. It cannot fake the requirement below: only the waiter appends
            # to observed_by.
            waiter_observed_owner.set()
            for thread in threads.values():
                thread.join(timeout=60)

        for name, thread in threads.items():
            self.assertFalse(thread.is_alive(), f"{name} did not finish")
        self.assertEqual(
            observed_by,
            ["waiter"],
            "the waiter never observed the owner's live transaction, so no overlap "
            "was exercised",
        )
        self.assertNotIn("owner_error", results)
        self.assertNotIn("waiter_error", results)
        self.assertEqual(effects, ["owner"], "exactly one effect may run")

        # Both must still reconcile: a protocol that satisfies the count below by
        # refusing the waiter outright fails here.
        self.assertEqual(results["owner"].status, "READY_FOR_OWNER_REVIEW")
        self.assertEqual(results["waiter"].status, "READY_FOR_OWNER_REVIEW")
        self.assertEqual(
            results["waiter"].lock_identity, results["owner"].lock_identity
        )

        self.assertEqual(
            self.committed_generation(),
            before + 1,
            "an identical authorised pair must advance the committed state exactly "
            "once; a waiter that republishes identical content under its own "
            "transaction has committed work it did not perform",
        )


class ReservationRaceGapTests(ProtocolFixture):
    """Observing that nobody has reserved is not the same as still being first."""

    def test_a_reservation_that_became_live_in_the_gap_is_not_replaced(self) -> None:
        """The other half of atomic acquisition.

        A observes no reservation, B establishes a live one before A can act on that
        observation, and A then proceeds on a fact that has expired. Whether the
        correct protocol waits, refuses or reloads depends on whether A and B are the
        same authorised request; what may not happen is A replacing a live
        reservation on the strength of an observation taken before it existed.

        A is a differently authorised caller here, so a correct protocol refuses it
        rather than parking it behind B, and the outcome can be observed while B is
        still holding the transaction.
        """
        candidate = self.prepared_candidate()
        winner_authority = self.authority(candidate)
        contender_authority = self.second_approval(candidate)

        contender_reaching_reserve = threading.Event()
        winner_reserved = threading.Event()
        winner_in_effect = threading.Event()
        release_winner = threading.Event()
        effects: list[str] = []
        reserved_by: dict[str, str] = {}
        results: dict[str, Any] = {}
        roles: dict[int, str] = {}
        threads: dict[str, threading.Thread] = {}

        def role_of() -> str:
            return roles.get(threading.get_ident(), "unattributed")

        real_liveness = retained_commit.owner_liveness

        @contextlib.contextmanager
        def liveness_after_the_gap_has_opened(
            root: Path, transaction_id: str
        ) -> Iterator[None]:
            # Entered at the start of acquisition, before any coordination lock is
            # held, so parking here cannot deadlock the transaction it waits for.
            if role_of() == "contender":
                contender_reaching_reserve.set()
                winner_reserved.wait(timeout=30)
            with real_liveness(root, transaction_id):
                yield

        real_write = retained_commit.write_reservation

        def record_reservation(
            root: Path, reservation: retained_commit.Reservation
        ) -> None:
            reserved_by.setdefault(role_of(), reservation.transaction_id)
            real_write(root, reservation)
            if role_of() == "winner":
                winner_reserved.set()

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append(role_of())
            if role_of() == "winner":
                winner_in_effect.set()
                release_winner.wait(timeout=30)
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        shared_spec = self._spec()

        def run(role: str, authority: Any) -> None:
            roles[threading.get_ident()] = role
            try:
                results[role] = compiler.prepare(
                    shared_spec,
                    self.workspace,
                    offline=True,
                    preflight_authority=authority,
                )
            except Exception as exc:  # recorded rather than raised across threads
                results[f"{role}_error"] = exc

        with (
            mock.patch.object(
                retained_commit, "owner_liveness", liveness_after_the_gap_has_opened
            ),
            mock.patch.object(
                retained_commit, "write_reservation", side_effect=record_reservation
            ),
            mock.patch.object(compiler, "qualify_subjects", side_effect=qualify),
        ):
            threads["contender"] = threading.Thread(
                target=run, args=("contender", contender_authority)
            )
            threads["contender"].start()
            self.assertTrue(
                contender_reaching_reserve.wait(timeout=30),
                "the contender never reached the point of reserving",
            )

            # Only now does the winner reserve: strictly inside the window between
            # the contender's observation and its own acquisition.
            threads["winner"] = threading.Thread(
                target=run, args=("winner", winner_authority)
            )
            threads["winner"].start()
            self.assertTrue(
                winner_in_effect.wait(timeout=30),
                "the winner never established a live reservation and entered its "
                "effect",
            )
            winner_reserved.set()

            threads["contender"].join(timeout=60)
            self.assertFalse(
                threads["contender"].is_alive(),
                "the contender must not be parked behind a transaction it is not "
                "identical to",
            )
            # Observed while the winner is still holding its live transaction.
            held = self.retained_reservation()

            release_winner.set()
            threads["winner"].join(timeout=60)

        self.assertFalse(threads["winner"].is_alive(), "the winner did not finish")
        self.assertNotIn("winner_error", results)
        self.assertNotIn("contender_error", results)
        self.assertIn("winner", reserved_by)
        self.assertEqual(effects, ["winner"], "the stale contender must open no effect")
        self.assertEqual(results["winner"].status, "READY_FOR_OWNER_REVIEW")
        self.assertNotEqual(results["contender"].status, "READY_FOR_OWNER_REVIEW")

        self.assertIsNotNone(held, "the winner's reservation was removed entirely")
        assert held is not None
        self.assertEqual(
            held["transaction_id"],
            reserved_by["winner"],
            "a reservation that became live between a contender's observation and "
            "its acquisition must not be replaced by that contender; deciding and "
            "creating belong in one coordination critical section",
        )


class AbandonedReservationTests(ProtocolFixture):
    """Green guard: a reservation with no claim behind it proves no effect."""

    def test_an_abandoned_pre_claim_reservation_does_not_kill_the_candidate(
        self,
    ) -> None:
        """Reserved-but-dead with no claim means nothing irreversible happened.

        The candidate is therefore still legitimately runnable. This is expected to
        be green already; it is here so the recovery work cannot quietly turn a
        recoverable abandonment into a permanently consumed candidate.
        """
        authority = self.authorised_candidate()
        effects: list[str] = []

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        class AbandonedTransaction(RuntimeError):
            """Death after reserving and before claiming."""

        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(
                effect_claim,
                "claim_fresh_candidate",
                side_effect=AbandonedTransaction("died before claiming"),
            ):
                with self.assertRaises(AbandonedTransaction):
                    self.prepare(authority=authority)

            self.assertEqual(
                effects, [], "the abandoned transaction must not have run an effect"
            )
            self.assertIsNotNone(
                self.retained_reservation(),
                "the abandoned transaction must genuinely have left a reservation",
            )

            recovered = self.prepare(authority=authority)

        self.assertEqual(
            effects,
            ["effect"],
            "the recovered transaction must run exactly one fresh effect",
        )
        self.assertEqual(
            recovered.status,
            "READY_FOR_OWNER_REVIEW",
            "an abandoned reservation with no claim behind it proves no irreversible "
            "effect, so it must not permanently consume the candidate",
        )
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )
        self.assertIsNone(
            self.retained_reservation(),
            "a completed transaction must leave no reservation behind",
        )


if __name__ == "__main__":
    unittest.main()
