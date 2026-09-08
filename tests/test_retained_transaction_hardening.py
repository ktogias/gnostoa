"""Focused coverage for the retained-transaction filesystem and identity surface.

Every check here exists because the alternative behaviour is silently unsafe rather
than merely wrong: a reservation that cannot be read must not be reported as no
reservation, a lock file whose path can be redirected serialises nobody, a
reservation must only be cleared by the transaction that owns it, and staged output
that is not provably complete must never become a recovery source.

The fixtures are synthetic and the qualification effect is patched; no Phase-D
material, hidden oracle, runner or container effect participates.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import unittest
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


def _reservation(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": retained_commit.RESERVATION_SCHEMA,
        "transaction_id": "a" * 32,
        "base_identity": None,
        "experiment_id": "E1",
        "scope": "base-reference-qualification",
        "candidate_sha256": "b" * 64,
        "authority_sha256": "c" * 64,
    }
    payload.update(overrides)
    return payload


class ReservationReadingTests(ConsumptionFixture):
    def _write(self, payload: object) -> Path:
        path = self.workspace / retained_commit.RESERVATION_FILENAME
        self.workspace.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
        return path

    def test_an_uninspectable_reservation_is_not_read_as_absence(self) -> None:
        """A failed stat means "unknown", and unknown must never mean "unreserved".

        The failure is produced by the filesystem rather than by patching a reader,
        so it lands on the existence check itself. ``Path.exists`` answers False for
        a path it cannot stat, which is exactly the reading that must not happen: it
        would report a live reservation as absent and hand away the effect boundary.
        """
        self._write(_reservation())
        original = self.workspace.stat().st_mode
        self.workspace.chmod(0o000)
        try:
            with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
                retained_commit.read_reservation(self.workspace)
        finally:
            self.workspace.chmod(original)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)

    def test_an_unreadable_reservation_is_not_read_as_absence(self) -> None:
        path = self.workspace / retained_commit.RESERVATION_FILENAME
        self.workspace.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not valid json")
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_reservation(self.workspace)

    def test_a_non_regular_reservation_is_refused(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / retained_commit.RESERVATION_FILENAME).mkdir()
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_reservation(self.workspace)

    def test_fields_are_validated_rather_than_coerced(self) -> None:
        """str() on a malformed field manufactures a reservation nobody wrote."""
        for overrides in (
            {"transaction_id": 17},
            {"transaction_id": ""},
            {"candidate_sha256": "not-a-digest"},
            {"candidate_sha256": "B" * 64},
            {"authority_sha256": None},
            {"base_identity": "short"},
            {"experiment_id": {"nested": True}},
            {"scope": 3.5},
        ):
            with self.subTest(overrides=overrides):
                self._write(_reservation(**overrides))
                with self.assertRaises(retained_commit.RetainedTransactionError):
                    retained_commit.read_reservation(self.workspace)

    def test_a_missing_reservation_is_absence(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.assertIsNone(retained_commit.read_reservation(self.workspace))


class ReservationClearingTests(ConsumptionFixture):
    def test_clearing_is_owner_bound(self) -> None:
        """Clearing another transaction's reservation gives away a live right."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        path = self.workspace / retained_commit.RESERVATION_FILENAME
        path.write_text(json.dumps(_reservation(transaction_id="b" * 32)))
        before = path.read_bytes()

        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.clear_reservation(
                self.workspace, expected_transaction_id="a" * 32
            )
        self.assertEqual(path.read_bytes(), before)

        retained_commit.clear_reservation(
            self.workspace, expected_transaction_id="b" * 32
        )
        self.assertFalse(path.exists())

    def test_clearing_an_absent_reservation_is_not_an_error(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        retained_commit.clear_reservation(
            self.workspace, expected_transaction_id="a" * 32
        )


class LockPathTests(ConsumptionFixture):
    def test_a_redirected_coordination_lock_is_refused(self) -> None:
        """A lock reachable through a symlink serialises against somebody else's file."""
        self.workspace.mkdir(parents=True, exist_ok=True)
        elsewhere = self.root / "elsewhere.lock"
        elsewhere.write_text("")
        (self.workspace / retained_commit.COORDINATION_LOCK_FILENAME).symlink_to(
            elsewhere
        )
        with self.assertRaises(retained_commit.RetainedTransactionError):
            with retained_commit.coordination_lock(self.workspace):
                pass

    def test_a_redirected_liveness_lock_is_refused(self) -> None:
        transaction = retained_commit.new_transaction_id()
        path = retained_commit.owner_lock_path(self.workspace, transaction)
        path.parent.mkdir(parents=True, exist_ok=True)
        elsewhere = self.root / "elsewhere-owner.lock"
        elsewhere.write_text("")
        path.symlink_to(elsewhere)
        with self.assertRaises(retained_commit.RetainedTransactionError):
            with retained_commit.owner_liveness(self.workspace, transaction):
                pass

    def test_a_non_regular_lock_path_is_refused(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / retained_commit.COORDINATION_LOCK_FILENAME).mkdir()
        with self.assertRaises(retained_commit.RetainedTransactionError):
            with retained_commit.coordination_lock(self.workspace):
                pass

    def test_without_advisory_locking_nothing_proceeds(self) -> None:
        """No locking means no coordination, and no coordination means no writing."""
        reservation = retained_commit.Reservation(
            transaction_id="a" * 32,
            base_identity=None,
            experiment_id="E1",
            scope="base-reference-qualification",
            candidate_sha256="b" * 64,
            authority_sha256="c" * 64,
        )
        with mock.patch.object(retained_commit, "fcntl", None):
            with self.assertRaises(retained_commit.RetainedTransactionError):
                with retained_commit.coordination_lock(self.workspace):
                    pass
            with self.assertRaises(retained_commit.RetainedTransactionError):
                with retained_commit.owner_liveness(self.workspace, "a" * 32):
                    pass
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.owner_is_live(self.workspace, reservation)
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.wait_for_owner(self.workspace, reservation)


class LivenessInspectionTests(ConsumptionFixture):
    """Liveness is a claim about another process, so unknown must not read as gone."""

    def _reservation(self, transaction: str) -> retained_commit.Reservation:
        return retained_commit.Reservation(
            transaction_id=transaction,
            base_identity=None,
            experiment_id="E1",
            scope="base-reference-qualification",
            candidate_sha256="b" * 64,
            authority_sha256="c" * 64,
        )

    def _uninspectable(self) -> tuple[retained_commit.Reservation, Path, int]:
        """A transaction directory that can be found but whose lock cannot be stat'd.

        The directory itself stays inspectable on purpose, so the failure lands on
        the liveness probe rather than on the containment check above it. ``is_file``
        answers False for a path it cannot inspect, and reading that as "the owner is
        gone" hands away a reservation that may still be held.
        """
        transaction = retained_commit.new_transaction_id()
        directory = self.workspace / retained_commit.STAGING_DIRECTORY / transaction
        directory.mkdir(parents=True)
        (directory / "owner.lock").write_text("")
        original = directory.stat().st_mode
        directory.chmod(0o000)
        return self._reservation(transaction), directory, original

    def test_an_uninspectable_liveness_lock_is_not_reported_as_gone(self) -> None:
        reservation, staging_root, original = self._uninspectable()
        try:
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.owner_is_live(self.workspace, reservation)
        finally:
            staging_root.chmod(original)

    def test_waiting_on_an_uninspectable_liveness_lock_fails_closed(self) -> None:
        reservation, staging_root, original = self._uninspectable()
        try:
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.wait_for_owner(self.workspace, reservation)
        finally:
            staging_root.chmod(original)

    def test_an_absent_liveness_lock_means_the_owner_is_gone(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.assertFalse(
            retained_commit.owner_is_live(
                self.workspace, self._reservation(retained_commit.new_transaction_id())
            )
        )


class TransactionMarkerTests(ConsumptionFixture):
    """A state that cannot be read is not evidence of a pre-transaction workspace."""

    def test_an_unreadable_state_is_not_reported_as_legacy(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "experiment-state.json").write_text("{ not valid json")
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.state_is_transactional(self.workspace)
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_committed(self.workspace)

    def test_an_absent_state_is_not_transactional(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.assertFalse(retained_commit.state_is_transactional(self.workspace))
        self.assertIsNone(retained_commit.read_committed(self.workspace))


class PublicationIntentTests(ConsumptionFixture):
    def test_a_tampered_intent_identifier_is_refused(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / retained_commit.PUBLICATION_FILENAME).write_text(
            json.dumps(
                {
                    "schema": retained_commit.PUBLICATION_SCHEMA,
                    "transaction_id": "../../elsewhere",
                }
            )
        )
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_publication_intent(self.workspace)

    def test_no_intent_means_no_publication_was_in_progress(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.assertIsNone(retained_commit.read_publication_intent(self.workspace))


class CompletedWorkspaceFixture(ConsumptionFixture):
    def complete(self) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=lambda *a, **k: _receipt(
                k.get("task_id", "T1"), dict(k.get("bound") or {})
            ),
        ):
            self.prepare(authority=self.authority(candidate))


class ConcurrentStagingCreationTests(ConsumptionFixture):
    """Two transactions creating the staging root at once must both proceed."""

    def test_simultaneous_first_creation_is_reconciled(self) -> None:
        """mkdir loses to a race exactly once; the loser must reopen, not fail.

        Nothing irreversible has happened at this point, so this is not a #197
        blocker. It is here so the descriptor-chain creation keeps reconciling
        EEXIST rather than surfacing it.
        """
        import threading

        self.workspace.mkdir(parents=True, exist_ok=True)
        transactions = [retained_commit.new_transaction_id() for _ in range(8)]
        start = threading.Barrier(len(transactions))
        failures: list[BaseException] = []

        def stage_one(transaction: str) -> None:
            try:
                start.wait(timeout=30)
                retained_commit.stage(
                    self.workspace,
                    transaction_id=transaction,
                    base_identity=None,
                    candidate_sha256=None,
                    authority_sha256=None,
                    ledger=b'{"records": {}}\n',
                    state=b"{}\n",
                    lock=None,
                    lock_identity=None,
                )
            except BaseException as exc:  # recorded rather than raised across threads
                failures.append(exc)

        threads = [
            threading.Thread(target=stage_one, args=(transaction,))
            for transaction in transactions
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        self.assertEqual(failures, [], "simultaneous creation must reconcile")
        for transaction in transactions:
            self.assertIsNotNone(
                retained_commit.read_staged(self.workspace, transaction)
            )


class CoherentPublicationTests(ConsumptionFixture):
    """Publishing observes one directory; what it publishes is what it validated."""

    def _stage(self, state: bytes = b"{}\n") -> Any:
        return retained_commit.stage(
            self.workspace,
            transaction_id=retained_commit.new_transaction_id(),
            base_identity=None,
            candidate_sha256="b" * 64,
            authority_sha256="c" * 64,
            ledger=b'{"records": {}}\n',
            state=state,
            lock=None,
            lock_identity=None,
        )

    def test_publishing_output_whose_manifest_changed_is_refused(self) -> None:
        staged = self._stage()
        manifest_path = (
            retained_commit.staging_directory(self.workspace, staged.transaction_id)
            / retained_commit.MANIFEST_FILENAME
        )
        manifest = json.loads(manifest_path.read_text())
        manifest["base_identity"] = "a" * 64
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.publish(self.workspace, staged=staged, generation=1)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)
        self.assertFalse(
            (self.workspace / retained_commit.COMMIT_RECORD_FILENAME).is_file(),
            "nothing may be committed from output that changed under the publisher",
        )

    def test_a_reservation_sealed_to_other_output_refuses_the_match(self) -> None:
        """Same request identities, different bytes: the seal is what separates them."""
        first = self._stage(b'{"first": true}\n')
        second = self._stage(b'{"second": true}\n')
        reservation = retained_commit.Reservation(
            transaction_id=second.transaction_id,
            base_identity=None,
            experiment_id="E1",
            scope="base-reference-qualification",
            candidate_sha256="b" * 64,
            authority_sha256="c" * 64,
            staged_manifest_sha256=first.manifest_sha256,
        )
        self.assertFalse(
            retained_commit._matches_reservation(second, reservation),
            "output the reservation was never sealed to must not match it",
        )
        self.assertTrue(
            retained_commit._matches_reservation(
                second,
                dataclasses.replace(
                    reservation, staged_manifest_sha256=second.manifest_sha256
                ),
            )
        )


class StagingRemovalTests(ConsumptionFixture):
    """A name that has moved is not the directory that was emptied."""

    def test_a_swapped_name_is_not_removed_after_the_contents_were_cleared(
        self,
    ) -> None:
        staged = retained_commit.stage(
            self.workspace,
            transaction_id=retained_commit.new_transaction_id(),
            base_identity=None,
            candidate_sha256=None,
            authority_sha256=None,
            ledger=b'{"records": {}}\n',
            state=b"{}\n",
            lock=None,
            lock_identity=None,
        )
        directory = retained_commit.staging_directory(
            self.workspace, staged.transaction_id
        )
        decoy = directory.with_name("decoy")
        decoy.mkdir()
        swapped: list[str] = []
        real_fsync = os.fsync

        def swap_then_fsync(descriptor: int) -> Any:
            result = real_fsync(descriptor)
            if not swapped:
                try:
                    same = os.fstat(descriptor).st_ino == directory.stat().st_ino
                except OSError:  # pragma: no cover - the directory is gone
                    same = False
                if same:
                    # The contents have just been cleared. The name now refers to a
                    # different directory entirely.
                    swapped.append("swapped")
                    directory.rename(directory.with_name("displaced"))
                    decoy.rename(directory)
            return result

        with mock.patch.object(os, "fsync", side_effect=swap_then_fsync):
            retained_commit.discard_staging(self.workspace, staged.transaction_id)

        self.assertEqual(swapped, ["swapped"], "the swap never happened")
        self.assertTrue(
            directory.is_dir(),
            "the directory the name now refers to must not be removed",
        )


class LockIdentityTests(CompletedWorkspaceFixture):
    """The persisted bytes and the identity they carry are two facts, not one."""

    def test_the_commit_record_binds_both_and_confuses_neither(self) -> None:
        self.complete()
        record = json.loads(
            (self.workspace / retained_commit.COMMIT_RECORD_FILENAME).read_text()
        )
        lock_bytes = (self.workspace / "experiment.lock").read_bytes()
        carried = json.loads(lock_bytes)["lock_sha256"]

        self.assertEqual(
            record["lock_file_sha256"], hashlib.sha256(lock_bytes).hexdigest()
        )
        self.assertEqual(record["lock_identity"], carried)
        self.assertNotEqual(
            record["lock_file_sha256"],
            record["lock_identity"],
            "the two are recorded separately precisely because they differ",
        )

    def test_every_recorded_reference_names_the_same_lock(self) -> None:
        self.complete()
        carried = json.loads((self.workspace / "experiment.lock").read_text())[
            "lock_sha256"
        ]
        state = json.loads((self.workspace / "experiment-state.json").read_text())
        ledger = json.loads((self.workspace / "stages.json").read_text())["records"]

        self.assertEqual(state["lock_sha256"], carried)
        self.assertEqual(ledger["EXECUTION_FROZEN"]["outputs"]["lock_sha256"], carried)
        self.assertEqual(
            ledger["READY_FOR_OWNER_REVIEW"]["outputs"]["lock_sha256"], carried
        )

    def test_staging_refuses_output_whose_references_disagree(self) -> None:
        """Agreement is checked before publication, not assumed from having written it."""
        identity = "d" * 64
        lock = json.dumps({"lock_sha256": identity}).encode()
        ledger = json.dumps(
            {
                "records": {
                    stage: {"outputs": {"lock_sha256": identity}}
                    for stage in ("EXECUTION_FROZEN", "READY_FOR_OWNER_REVIEW")
                }
            }
        ).encode()
        state = json.dumps({"lock_sha256": "e" * 64}).encode()
        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.stage(
                self.workspace,
                transaction_id=retained_commit.new_transaction_id(),
                base_identity=None,
                candidate_sha256=None,
                authority_sha256=None,
                ledger=ledger,
                state=state,
                lock=lock,
                lock_identity=identity,
            )
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)

    def test_a_staged_lock_without_its_identity_is_refused(self) -> None:
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.stage(
                self.workspace,
                transaction_id=retained_commit.new_transaction_id(),
                base_identity=None,
                candidate_sha256=None,
                authority_sha256=None,
                ledger=b"{}",
                state=b"{}",
                lock=b"{}",
                lock_identity=None,
            )


class LocklessCommitTests(CompletedWorkspaceFixture):
    """A commit that does not rebuild the lock must not tear the workspace."""

    def test_a_commit_that_stages_no_lock_leaves_the_workspace_consistent(
        self,
    ) -> None:
        """The record describes the workspace, not only the transaction's members.

        Once a lock is published, any later invocation that blocks before rebuilding
        one still commits its state and ledger. If the record then said this
        transaction published no lock, it would contradict the lock sitting on disk
        and every subsequent read would refuse a workspace nothing is wrong with.
        """
        self.complete()
        published = json.loads(
            (self.workspace / retained_commit.COMMIT_RECORD_FILENAME).read_text()
        )
        self.assertIsNotNone(published["lock_file_sha256"])

        # Drift the question so the next prepare blocks well before the lock stage.
        self.payload["experiment"]["question"] = "a materially different question"
        blocked = self.prepare()
        self.assertEqual(blocked.status, "BLOCKED")

        self.assertTrue((self.workspace / "experiment.lock").is_file())
        restored = retained_commit.read_committed(self.workspace)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(
            restored.lock_file_sha256,
            hashlib.sha256(
                (self.workspace / "experiment.lock").read_bytes()
            ).hexdigest(),
            "the record must keep naming the lock that is still published",
        )
        self.assertEqual(
            compiler.status(self.workspace)["status"],
            blocked.status,
            "a consistent workspace must report the state it just committed",
        )


class StagedRecoverySourceTests(CompletedWorkspaceFixture):
    """Staged output is a recovery source only while it is provably complete."""

    def _stage_one(self) -> str:
        transaction = retained_commit.new_transaction_id()
        retained_commit.stage(
            self.workspace,
            transaction_id=transaction,
            base_identity=None,
            candidate_sha256=None,
            authority_sha256=None,
            ledger=b'{"records": {}}\n',
            state=b"{}\n",
            lock=None,
            lock_identity=None,
        )
        self.assertIsNotNone(retained_commit.read_staged(self.workspace, transaction))
        return transaction

    def test_a_missing_manifest_is_not_a_recovery_source(self) -> None:
        transaction = self._stage_one()
        (
            retained_commit.staging_directory(self.workspace, transaction)
            / retained_commit.MANIFEST_FILENAME
        ).unlink()
        self.assertIsNone(retained_commit.read_staged(self.workspace, transaction))

    def test_a_corrupt_manifest_is_not_a_recovery_source(self) -> None:
        transaction = self._stage_one()
        (
            retained_commit.staging_directory(self.workspace, transaction)
            / retained_commit.MANIFEST_FILENAME
        ).write_text("{ not valid json")
        self.assertIsNone(retained_commit.read_staged(self.workspace, transaction))

    def test_a_missing_member_is_not_a_recovery_source(self) -> None:
        transaction = self._stage_one()
        (
            retained_commit.staging_directory(self.workspace, transaction)
            / retained_commit.LEDGER_FILENAME
        ).unlink()
        self.assertIsNone(retained_commit.read_staged(self.workspace, transaction))

    def test_a_modified_member_is_not_a_recovery_source(self) -> None:
        transaction = self._stage_one()
        (
            retained_commit.staging_directory(self.workspace, transaction)
            / retained_commit.STATE_FILENAME
        ).write_text('{"tampered": true}\n')
        self.assertIsNone(retained_commit.read_staged(self.workspace, transaction))

    def test_an_uninspectable_manifest_is_not_read_as_incomplete_staging(
        self,
    ) -> None:
        """Recovery deletes what it decides is incomplete, so unknown must not be it."""
        transaction = self._stage_one()
        directory = retained_commit.staging_directory(self.workspace, transaction)
        original = directory.stat().st_mode
        directory.chmod(0o000)
        try:
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.read_staged(self.workspace, transaction)
        finally:
            directory.chmod(original)

    def test_staged_output_that_does_not_match_its_reservation_is_refused(self) -> None:
        """The fallback recovery path needs provenance too, not only completeness.

        Without a publication intent the reservation is the only thing that says
        which transaction this staged output belongs to. Publishing a complete tree
        that describes a different request would commit, as this transaction, output
        it never produced.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        before = (self.workspace / "experiment-state.json").read_text()
        effects: list[str] = []

        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(
                retained_commit,
                "_write_publication_intent",
                side_effect=RuntimeError("died before the intent became durable"),
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)

            reservation = retained_commit.read_reservation(self.workspace)
            assert reservation is not None
            manifest_path = (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            )
            manifest = json.loads(manifest_path.read_text())
            manifest["candidate_sha256"] = "9" * 64
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )

            refused = self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in refused.blockers],
        )
        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            before,
            "output that does not match its reservation must not be published",
        )
        self.assertTrue(
            manifest_path.is_file(),
            "the mismatched staging must be kept as evidence, not swept away",
        )

    def test_an_interrupted_transaction_with_broken_staging_is_not_recovered(
        self,
    ) -> None:
        """Unrecoverable is refused, never rewritten and never replayed."""
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

        real_write = retained_commit._write_atomic

        def crash_before_recording(path: Path, payload: bytes) -> None:
            if path.name == retained_commit.COMMIT_RECORD_FILENAME:
                raise RuntimeError("crash between staging and recording")
            return real_write(path, payload)

        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(
                retained_commit, "_write_atomic", side_effect=crash_before_recording
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)

            reservation = retained_commit.read_reservation(self.workspace)
            self.assertIsNotNone(reservation)
            assert reservation is not None
            manifest = (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            )
            manifest.write_text("{ not valid json")

            blocked = self.prepare(authority=authority)

        self.assertEqual(
            effects, ["effect"], "an unrecoverable transaction must not be replayed"
        )
        self.assertNotEqual(blocked.status, "READY_FOR_OWNER_REVIEW")


if __name__ == "__main__":
    unittest.main()
