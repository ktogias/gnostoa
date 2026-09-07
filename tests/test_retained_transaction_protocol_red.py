"""RED protocol packet for the retained-transaction model at ccacddc5.

The reservation model closed the five effect/liveness invariants of
``test_preflight_transaction_red``, but four protocol properties it claims are not
yet held. Each is stated as an observable workspace outcome so that any correct
protocol satisfies it:

  * a reservation must be taken against the snapshot that is current when it is
    taken, not one that has since been superseded;
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

At head ccacddc5de8feba1614d96713863129fbea062fc these are expected to be RED.
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


class ProtocolFixture(ConsumptionFixture):
    def committed_generation(self) -> int | None:
        path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        if not path.is_file():
            return None
        payload: dict[str, Any] = json.loads(path.read_text())
        generation = payload["generation"]
        assert isinstance(generation, int)
        return generation

    def authorised_candidate(self) -> Any:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        return self.authority(candidate)


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
        waiter_reached_candidate = threading.Event()
        effects: list[str] = []
        results: dict[str, Any] = {}
        roles: dict[int, str] = {}
        threads: dict[str, threading.Thread] = {}

        real_identity = compiler.preflight_candidate_identity

        def role_of() -> str:
            return roles.get(threading.get_ident(), "unattributed")

        def identity_seam(**kwargs: object) -> Any:
            value = real_identity(**kwargs)
            # Signalled by the waiter itself, from a point that proves it has
            # computed the same candidate while the owner still holds the
            # transaction.
            if role_of() == "waiter":
                waiter_reached_candidate.set()
            return value

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append(role_of())
            if role_of() == "owner":
                owner_in_effect.set()
                waiter_reached_candidate.wait(timeout=15)
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
                compiler, "preflight_candidate_identity", side_effect=identity_seam
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
            reached = waiter_reached_candidate.wait(timeout=15)
            overlapped = reached or threads["waiter"].is_alive()
            waiter_reached_candidate.set()
            for thread in threads.values():
                thread.join(timeout=60)

        for name, thread in threads.items():
            self.assertFalse(thread.is_alive(), f"{name} did not finish")
        self.assertTrue(overlapped, "the waiter never overlapped the owner")
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


if __name__ == "__main__":
    unittest.main()
