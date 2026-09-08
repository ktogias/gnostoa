"""RED storage packet for the retained-transaction model at 11c0fa3.

The state machine holds; these are the filesystem primitives underneath it. Each
one is a way for a workspace to end up claiming something the bytes on disk do not
support, without any state-machine rule being broken:

  * a short write must never be reported as a completed write, or a truncated
    commit record is published as a finished transaction;
  * staged output must carry a commitment made outside the staging directory before
    it can be a recovery source, so a self-consistent rewrite of a member cannot be
    finished forward under an untouched reservation;
  * the temporary file a transaction writes through must not be a name an attacker
    can pre-create, since O_NOFOLLOW does not protect against a hardlink;
  * a commit record that cannot be read is unknown, never absent, and must never
    authorise discarding the evidence of a consumed effect;
  * an identical waiter must converge even when the owner dies mid-publication --
    that is the case recovery exists for, and the waiter is the caller standing
    closest to it.

All fixtures are synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates. The
containment cases assert that a sentinel outside the workspace, but inside the
test's own temporary tree, is left untouched.

At head 11c0fa3115d4846978cea7d2836b742f1bdd1e2e these are expected to be RED.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
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


class StorageFixture(ConsumptionFixture):
    def patched_effect(self, effects: list[str] | None = None) -> Any:
        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            if effects is not None:
                effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        return mock.patch.object(compiler, "qualify_subjects", side_effect=qualify)

    def interrupted_before_the_intent(self, effects: list[str]) -> Any:
        """Complete staged output under a live reservation, with no intent yet."""
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        with self.patched_effect(effects):
            with mock.patch.object(
                retained_commit,
                "_write_publication_intent",
                side_effect=RuntimeError("died before the intent became durable"),
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)
        reservation = retained_commit.read_reservation(self.workspace)
        self.assertIsNotNone(reservation)
        assert reservation is not None
        self.assertIsNone(retained_commit.read_publication_intent(self.workspace))
        self.assertEqual(effects, ["effect"])
        return reservation, authority


class ShortWriteTests(StorageFixture):
    """A write that wrote less than it was given did not write the payload."""

    def test_a_short_write_is_not_reported_as_a_completed_write(self) -> None:
        """POSIX write may succeed having written fewer bytes than requested.

        Ignoring the returned count publishes a truncated commit record as a
        finished transaction: the intent is then cleared, the reservation released
        and the staging discarded, all on the strength of a file that was never
        fully written.
        """
        self.workspace.mkdir(parents=True, exist_ok=True)
        target = self.workspace / "short-write-probe.json"
        payload = (json.dumps({"padding": "x" * 4096}) + "\n").encode()
        real_write = os.write

        def short_write(descriptor: int, data: Any) -> int:
            return real_write(descriptor, bytes(data)[: max(1, len(data) // 4)])

        with mock.patch("os.write", side_effect=short_write):
            retained_commit._write_atomic(target, payload)

        self.assertEqual(
            target.read_bytes(),
            payload,
            "a partial write must be completed or refused, never accepted",
        )


class TemporaryFileContainmentTests(StorageFixture):
    """The file a transaction writes through must not be a name someone else chose."""

    def test_a_pre_created_temporary_name_cannot_redirect_a_write(self) -> None:
        """O_NOFOLLOW does not protect against a hardlink.

        A deterministic temporary name opened with O_TRUNC can be pre-created as a
        hardlink to any file on the same filesystem, and the transaction then
        truncates it.
        """
        victim = self.root / "outside-the-workspace" / "victim.json"
        victim.parent.mkdir(parents=True, exist_ok=True)
        contents = "someone else's evidence\n"
        victim.write_text(contents)

        transaction = retained_commit.new_transaction_id()
        directory = self.workspace / retained_commit.STAGING_DIRECTORY / transaction
        directory.mkdir(parents=True)
        os.link(victim, directory / f"{retained_commit.LEDGER_FILENAME}.partial")

        try:
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
        except retained_commit.RetainedTransactionError:
            pass  # refusing is a correct outcome; truncating the victim is not

        self.assertEqual(
            victim.read_text(),
            contents,
            "a transaction must not write through a temporary name it did not create",
        )


class StagedAuthenticityTests(StorageFixture):
    """Before an intent exists, nothing outside the staging tree vouches for it."""

    def test_a_self_consistently_rewritten_member_is_not_recoverable(self) -> None:
        """The manifest seals the tree; nothing seals the manifest.

        A member can be rewritten and its digest updated in the manifest, leaving
        the transaction id, base, candidate and authority untouched. Reservation
        provenance therefore still matches, and the substituted bytes are published
        as the interrupted transaction's commit.
        """
        effects: list[str] = []
        reservation, authority = self.interrupted_before_the_intent(effects)
        before = (self.workspace / "experiment-state.json").read_text()

        directory = retained_commit.staging_directory(
            self.workspace, reservation.transaction_id
        )
        substituted = '{"substituted": true}\n'
        (directory / retained_commit.STATE_FILENAME).write_text(substituted)
        manifest_path = directory / retained_commit.MANIFEST_FILENAME
        manifest = json.loads(manifest_path.read_text())
        manifest["state_file_sha256"] = hashlib.sha256(substituted.encode()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        with self.patched_effect(effects):
            self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(
            (self.workspace / "experiment-state.json").read_text(),
            substituted,
            "staged output rewritten after the fact must not be finished forward",
        )
        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            before,
            "a workspace that cannot be recovered safely must be left as it was",
        )


class UnknownRecordedSnapshotTests(StorageFixture):
    """Unknown is not absent, in recovery as everywhere else."""

    def test_an_unreadable_commit_record_does_not_authorise_discarding_evidence(
        self,
    ) -> None:
        """Recovery compares staged output against what is committed.

        If the committed record cannot be read, the comparison has no answer. Taking
        the absent-workspace answer instead makes every staged transaction look
        superseded, and the evidence of a consumed effect is deleted on the strength
        of a question that was never answered.
        """
        effects: list[str] = []
        reservation, authority = self.interrupted_before_the_intent(effects)
        record = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record.write_text("{ not valid json")

        with self.patched_effect(effects):
            refused = self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIsNotNone(
            retained_commit.read_reservation(self.workspace),
            "the reservation must not be released on an unanswered question",
        )
        self.assertTrue(
            (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            ).is_file(),
            "the staged evidence must not be discarded on an unanswered question",
        )


class WaiterRecoversOwnerDeathTests(StorageFixture):
    """The waiter is the caller standing closest to a mid-publication death."""

    def test_an_identical_waiter_converges_when_the_owner_dies_publishing(
        self,
    ) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)

        owner_in_effect = threading.Event()
        waiter_observed_owner = threading.Event()
        observed_by: list[str] = []
        effects: list[str] = []
        results: dict[str, Any] = {}
        roles: dict[int, str] = {}
        threads: dict[str, threading.Thread] = {}

        real_wait_for_owner = retained_commit.wait_for_owner
        real_write = retained_commit._write_atomic

        def role_of() -> str:
            return roles.get(threading.get_ident(), "unattributed")

        def waiting_seam(root: Path, reservation: Any) -> Any:
            # Released only once the waiter has committed to waiting for this owner.
            # Signalling when it merely observed the reservation lets the owner die
            # first, after which the waiter never takes the wait path at all and the
            # interleaving under test is decided by the scheduler.
            if role_of() == "waiter":
                if not observed_by:
                    observed_by.append("waiter")
                waiter_observed_owner.set()
            return real_wait_for_owner(root, reservation)

        def die_mid_publication(path: Path, payload: bytes) -> None:
            # The owner has already moved a canonical file; the commit record is the
            # last write, and it never lands.
            if (
                role_of() == "owner"
                and path.name == retained_commit.COMMIT_RECORD_FILENAME
            ):
                raise RuntimeError("owner died mid-publication")
            return real_write(path, payload)

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
                retained_commit, "wait_for_owner", side_effect=waiting_seam
            ),
            mock.patch.object(
                retained_commit, "_write_atomic", side_effect=die_mid_publication
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
            waiter_observed_owner.set()
            for thread in threads.values():
                thread.join(timeout=60)

        for name, thread in threads.items():
            self.assertFalse(thread.is_alive(), f"{name} did not finish")
        self.assertEqual(
            observed_by,
            ["waiter"],
            "the waiter never waited for the owner, so no overlap was exercised",
        )
        self.assertIn("owner_error", results, "the owner must have died publishing")
        self.assertEqual(
            effects, ["owner"], "exactly one effect, and it is the owner's"
        )
        self.assertEqual(
            results["waiter"].status,
            "READY_FOR_OWNER_REVIEW",
            "an identical waiter must finish the owner's interrupted publication "
            "forward rather than meet the inconsistency it was waiting through",
        )
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )


if __name__ == "__main__":
    unittest.main()
