"""RED for status coherence and mandatory record digests, at fd7571e.

Two readers that are weaker than the records they read:

  * `status` reads the public state and then validates the commit record, so a
    legitimate concurrent commit can leave it vouching for one snapshot while
    returning the payload of another;
  * the commit-record parser accepts a null ledger or state digest, which no
    transaction this code can produce ever writes. Recovery decides supersession
    from the recorded snapshot's identity, so a nulled digest becomes a different
    valid snapshot and licenses discarding sealed evidence before the canonical
    read ever notices the disagreement.

The fixtures are synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head fd7571e3b23bce43922612278b663bfb78dcf420 these are expected to be RED.
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


class StatusFixture(ConsumptionFixture):
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


class StatusCoherenceTests(StatusFixture):
    """What status vouches for and what status returns must be one observation."""

    def test_status_returns_the_state_of_the_snapshot_it_validated(self) -> None:
        """A concurrent commit is legitimate; reporting across it is not.

        The payload is read first and the record validated afterwards. Another
        invocation committing in between leaves status having checked the provenance
        of one snapshot and returned the contents of an earlier one -- reporting a
        readiness the workspace no longer holds.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect():
            self.prepare(authority=self.authority(candidate))
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )

        real_read_committed = retained_commit.read_committed
        committed: list[str] = []

        def commit_then_validate(root: Path) -> Any:
            # Between the payload being read and the record being validated, another
            # invocation commits. Nothing here is illegitimate: this is an ordinary
            # concurrent prepare.
            if not committed:
                committed.append("committed")
                self.payload["tasks"][0]["id"] = "T9"
                self.prepare()
            return real_read_committed(root)

        with mock.patch.object(
            retained_commit, "read_committed", side_effect=commit_then_validate
        ):
            reported = compiler.status(self.workspace)

        self.assertEqual(committed, ["committed"], "no concurrent commit happened")
        on_disk = json.loads(
            (self.workspace / retained_commit.STATE_FILENAME).read_text()
        )
        self.assertNotEqual(
            on_disk["status"],
            "READY_FOR_OWNER_REVIEW",
            "the concurrent commit must have replaced the readiness, or this proves "
            "nothing",
        )
        self.assertEqual(
            reported["status"],
            on_disk["status"],
            "status must report the state of the snapshot whose record it validated",
        )
        self.assertEqual(reported["stage"], on_disk["stage"])


class MandatoryRecordDigestTests(StatusFixture):
    """A digest no transaction omits must not be optional to read back."""

    def test_a_record_without_its_state_digest_is_refused(self) -> None:
        """Every commit records both member digests, so a null one is not a commit.

        Recovery compares staged output against the recorded snapshot's identity. A
        nulled digest yields a different identity, which reads as "somebody else
        committed since" -- and the sealed evidence of a consumed effect is
        discarded before the canonical read ever reports the disagreement.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        effects: list[str] = []

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
            self.assertIsNotNone(reservation.staged_manifest_sha256)
            before = (self.workspace / "experiment-state.json").read_text()

            record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
            record = json.loads(record_path.read_text())
            self.assertIsNotNone(record["state_sha256"])
            record["state_sha256"] = None
            record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

            refused = self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in refused.blockers],
        )
        self.assertIsNotNone(
            retained_commit.read_reservation(self.workspace),
            "sealed evidence must not be discarded on a malformed record",
        )
        self.assertTrue(
            (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            ).is_file(),
            "the staged output must survive as evidence",
        )
        self.assertEqual((self.workspace / "experiment-state.json").read_text(), before)

    def _sealed_pre_intent(self, effects: list[str]) -> Any:
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
        self.assertIsNotNone(reservation.staged_manifest_sha256)
        return reservation, authority

    def _assert_half_null_lock_is_refused(self, **overrides: Any) -> None:
        """Tamper exactly one of the two lock fields and require a refusal."""
        effects: list[str] = []
        reservation, authority = self._sealed_pre_intent(effects)
        before = (self.workspace / "experiment-state.json").read_text()

        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        self.assertIsNone(record["lock_file_sha256"])
        self.assertIsNone(record["lock_identity"])
        record.update(overrides)
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

        with self.patched_effect(effects):
            refused = self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in refused.blockers],
        )
        self.assertIsNotNone(
            retained_commit.read_reservation(self.workspace),
            "sealed evidence must not be discarded on a malformed record",
        )
        self.assertTrue(
            (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            ).is_file(),
            "the staged output must survive as evidence",
        )
        self.assertEqual((self.workspace / "experiment-state.json").read_text(), before)

    def test_a_valid_but_false_state_digest_is_not_supersession_authority(
        self,
    ) -> None:
        """Structural validity is not agreement with the files it describes.

        With no publication intent, no canonical publication is in flight, so the
        record and the canonical files must agree. Deciding supersession from a
        structurally valid record without checking that agreement lets a digest that
        is simply false discard a sealed reservation and the staged evidence of a
        consumed effect -- the same harm as a nulled digest, arriving through a
        shape the parser cannot reject.
        """
        effects: list[str] = []
        reservation, authority = self._sealed_pre_intent(effects)
        self.assertIsNone(
            retained_commit.read_publication_intent(self.workspace),
            "no publication may be in flight for this branch to be under test",
        )
        before = (self.workspace / "experiment-state.json").read_text()

        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        false_digest = "f" * 64
        self.assertNotEqual(record["state_sha256"], false_digest)
        record["state_sha256"] = false_digest
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

        with self.patched_effect(effects):
            refused = self.prepare(authority=authority)

        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in refused.blockers],
        )
        self.assertIsNotNone(
            retained_commit.read_reservation(self.workspace),
            "a record that disagrees with the files must not discard sealed evidence",
        )
        self.assertTrue(
            (
                retained_commit.staging_directory(
                    self.workspace, reservation.transaction_id
                )
                / retained_commit.MANIFEST_FILENAME
            ).is_file(),
            "the staged output must survive as evidence",
        )
        self.assertEqual((self.workspace / "experiment-state.json").read_text(), before)

    def test_a_record_naming_a_lock_identity_with_no_lock_digest_is_refused(
        self,
    ) -> None:
        """The two lock fields are written together or not at all.

        publish derives the digest from the persisted bytes and the identity from
        what those bytes carry, so exactly one of them being present is a record no
        producer writes. Reading it as a valid snapshot gives it an identity of its
        own, and recovery decides supersession from precisely that.
        """
        self._assert_half_null_lock_is_refused(lock_identity="f" * 64)

    def test_a_record_naming_a_lock_digest_with_no_lock_identity_is_refused(
        self,
    ) -> None:
        self._assert_half_null_lock_is_refused(lock_file_sha256="e" * 64)

    def test_a_record_without_its_ledger_digest_is_refused(self) -> None:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect():
            self.prepare(authority=self.authority(candidate))

        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        self.assertIsNotNone(record["stages_sha256"])
        record["stages_sha256"] = None
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)
        self.assertIn(
            "stages_sha256",
            raised.exception.detail,
            "the refusal must name the digest that is missing, not a file mismatch",
        )


if __name__ == "__main__":
    unittest.main()
