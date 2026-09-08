"""RED containment packet for the retained-transaction model at af9b4144.

The transaction protocol works along its intended path. These state what the
retained *records* must not be able to do when they are not what the protocol
assumed, because every one of them is read back from a workspace that another
process, or a tampering hand, may have written:

  * a torn publication must be recoverable whether or not its publisher held an
    effect reservation -- discovery of an interrupted commit cannot depend on a
    record that only reserving callers create;
  * a transaction identifier read from a retained record must never address a path
    outside the workspace, and must never cause a deletion outside it;
  * a staging directory replaced by a symlink must not redirect writes or deletions;
  * a commit record must not be able to name a lock identity that the lock it
    binds does not carry;
  * staged output must not be finished forward as some other transaction's commit
    merely because it is complete and carries the right identifier.

All fixtures are synthetic and the qualification effect is patched; no Phase-D
material, hidden oracle, runner or container effect participates. Nothing here
writes outside the test's own temporary tree -- the escape cases assert that a
sentinel *outside* the workspace but inside that tree is left untouched.

At head af9b414496f46cc20a344442f665bfaf99fad87f these are expected to be RED.
"""

from __future__ import annotations

import json
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


class ContainmentFixture(ConsumptionFixture):
    def patched_effect(self) -> Any:
        return mock.patch.object(
            compiler,
            "qualify_subjects",
            side_effect=lambda *a, **k: _receipt(
                k.get("task_id", "T1"), dict(k.get("bound") or {})
            ),
        )

    def crash_writing(self, filename: str) -> Any:
        """Patch the atomic writer to die when it reaches one canonical file."""
        real_write = retained_commit._write_atomic

        def crash(path: Path, payload: bytes) -> None:
            if path.name == filename and path.parent == self.workspace:
                raise RuntimeError(f"crash while writing {filename}")
            return real_write(path, payload)

        return mock.patch.object(retained_commit, "_write_atomic", side_effect=crash)

    def outside(self, name: str) -> Path:
        """A sentinel next to the workspace, never inside it."""
        target = self.root / "outside-the-workspace" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def tamper_reservation(self, **overrides: Any) -> None:
        path = self.workspace / retained_commit.RESERVATION_FILENAME
        payload = json.loads(path.read_text())
        payload.update(overrides)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


class NonReservingTornPublicationTests(ContainmentFixture):
    """Discovery of an interrupted commit cannot depend on an effect reservation."""

    def test_a_torn_publication_without_a_reservation_is_finished_forward(
        self,
    ) -> None:
        """Publishing and reserving are different acts, and both callers publish.

        An invocation with no authority never reserves -- it can never cross the
        effect boundary -- but it still writes canonical files. If a crash between
        publishing them and recording the commit is only discoverable through a
        reservation, that workspace is stranded inconsistent with a complete staged
        commit sitting next to it that nothing knows how to finish.
        """
        with self.crash_writing(retained_commit.COMMIT_RECORD_FILENAME):
            with self.assertRaises(RuntimeError):
                self.prepare()

        self.assertIsNone(
            retained_commit.read_reservation(self.workspace),
            "an authority-less invocation must not have reserved",
        )
        torn = (self.workspace / "experiment-state.json").read_text()
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_committed(self.workspace)

        self.prepare()

        restored = retained_commit.read_committed(self.workspace)
        self.assertIsNotNone(
            restored,
            "a torn publication must be finishable forward without a reservation",
        )
        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            torn,
            "recovery must publish the interrupted transaction's own output",
        )


class TransactionIdentifierContainmentTests(ContainmentFixture):
    """An identifier read from a retained record is untrusted input, not a path."""

    def test_an_absolute_identifier_cannot_reach_outside_the_workspace(self) -> None:
        sentinel = self.outside("absolute-victim")
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        escaped = self.root / "outside-the-workspace" / "escaped-transaction"
        escaped.mkdir(parents=True, exist_ok=True)
        (escaped / "evidence.json").write_text("someone else's file\n")

        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect():
            with self.crash_writing(retained_commit.COMMIT_RECORD_FILENAME):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=self.authority(candidate))

        self.tamper_reservation(transaction_id=str(escaped))
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_reservation(self.workspace)

        with retained_commit.coordination_lock(self.workspace):
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.recover(self.workspace)

        self.assertTrue(
            (escaped / "evidence.json").is_file(),
            "a tampered identifier must never cause a deletion outside the workspace",
        )

    def test_a_traversing_identifier_cannot_reach_outside_the_workspace(self) -> None:
        escaped = self.root / "outside-the-workspace" / "traversed"
        escaped.mkdir(parents=True, exist_ok=True)
        (escaped / "evidence.json").write_text("someone else's file\n")

        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect():
            with self.crash_writing(retained_commit.COMMIT_RECORD_FILENAME):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=self.authority(candidate))

        relative = "../../outside-the-workspace/traversed"
        self.tamper_reservation(transaction_id=relative)
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.read_reservation(self.workspace)

        with retained_commit.coordination_lock(self.workspace):
            with self.assertRaises(retained_commit.RetainedTransactionError):
                retained_commit.recover(self.workspace)

        self.assertTrue(
            (escaped / "evidence.json").is_file(),
            "a traversing identifier must never cause a deletion outside the workspace",
        )

    def test_staging_paths_stay_inside_the_workspace_for_any_identifier(self) -> None:
        """Refused or contained, but never resolving outside the retained workspace."""
        for identifier in ("/tmp/victim", "../../escape", "..", "a/b"):
            with self.subTest(identifier=identifier):
                try:
                    directory = retained_commit.staging_directory(
                        self.workspace, identifier
                    )
                except retained_commit.RetainedTransactionError:
                    continue
                self.assertTrue(
                    self.workspace.resolve() in directory.resolve().parents,
                    f"{identifier!r} resolved to {directory} outside the workspace",
                )


class StagingDirectoryRedirectionTests(ContainmentFixture):
    """O_NOFOLLOW on the lock file does not protect the directories above it."""

    def test_a_symlinked_staging_directory_is_not_followed(self) -> None:
        elsewhere = self.root / "outside-the-workspace" / "redirect-target"
        elsewhere.mkdir(parents=True, exist_ok=True)
        (elsewhere / "evidence.json").write_text("someone else's file\n")

        transaction = retained_commit.new_transaction_id()
        staging_root = self.workspace / retained_commit.STAGING_DIRECTORY
        staging_root.mkdir(parents=True, exist_ok=True)
        (staging_root / transaction).symlink_to(elsewhere, target_is_directory=True)

        with self.assertRaises(retained_commit.RetainedTransactionError):
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
        self.assertEqual(
            sorted(entry.name for entry in elsewhere.iterdir()),
            ["evidence.json"],
            "a redirected staging directory must not receive writes",
        )

        # Refusing and ignoring are both acceptable; deleting through the symlink
        # is not. The property is that nothing outside the workspace is touched.
        with self.assertRaises(retained_commit.RetainedTransactionError):
            retained_commit.discard_staging(self.workspace, transaction)
        self.assertTrue(
            (elsewhere / "evidence.json").is_file(),
            "a redirected staging directory must not have its contents deleted",
        )


class CommitRecordLockProvenanceTests(ContainmentFixture):
    """Agreement when written is not agreement when read."""

    def test_a_commit_record_cannot_name_a_lock_identity_the_lock_does_not_carry(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect():
            self.prepare(authority=self.authority(candidate))
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )

        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        lock_bytes = (self.workspace / "experiment.lock").read_bytes()
        record["lock_identity"] = "f" * 64
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

        # Nothing else is touched: the lock, the state and the ledger are the ones
        # the successful transaction wrote.
        self.assertEqual((self.workspace / "experiment.lock").read_bytes(), lock_bytes)

        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)
        self.assertEqual(
            compiler.status(self.workspace)["status"],
            "BLOCKED",
            "a record naming a lock identity nothing carries must not prove READY",
        )


class RecoveryBindingTests(ContainmentFixture):
    """Recovery must publish the reserved transaction's output, not any complete tree."""

    def test_staging_that_is_not_the_reserved_transactions_output_is_not_published(
        self,
    ) -> None:
        """Completeness is not provenance.

        A staged tree can be complete, self-consistent and carry the right
        identifier while describing a different request entirely. Finishing it
        forward would publish, as this transaction's commit, evidence it never
        produced.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        before = (self.workspace / "experiment-state.json").read_text()

        with self.patched_effect():
            # Dies before any canonical file moves, so what recovery does next is
            # visible in the canonical state rather than already applied.
            with self.crash_writing(retained_commit.LEDGER_FILENAME):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=self.authority(candidate))

            reservation = retained_commit.read_reservation(self.workspace)
            self.assertIsNotNone(reservation)
            assert reservation is not None
            manifest_path = (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            )
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(manifest["candidate_sha256"], candidate)
            manifest["candidate_sha256"] = "9" * 64
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )

            self.prepare()

        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            before,
            "staged output that does not match the reservation it is recovered "
            "under must not be published",
        )


if __name__ == "__main__":
    unittest.main()
