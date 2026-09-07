"""RED namespace packet for the retained-transaction storage layer at 5e55b4b.

Three ways a workspace can still lose evidence or write outside itself, none of
which breaks a transaction rule:

  * a reservation sealed to its staged output is durable proof that a complete
    transaction once existed there, so staging that can no longer reproduce that
    seal is a damaged commit, not an absent one;
  * a commit record that parses but is structurally invalid must not read back as
    a different valid snapshot, because "different" is what recovery treats as
    superseded;
  * anchoring on a descriptor only helps if the descriptor was reached without
    following a path someone can change underneath it.

All fixtures are synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates. The
containment case asserts that a tree outside the workspace, but inside the test's
own temporary directory, is never written to or emptied.

At head 5e55b4ba4f5f3aa075c24b71f171ddb3c373e1fa these are expected to be RED.
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


class SealedTransactionFixture(ConsumptionFixture):
    def patched_effect(self, effects: list[str]) -> Any:
        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        return mock.patch.object(compiler, "qualify_subjects", side_effect=qualify)

    def sealed_but_unpublished(self, effects: list[str]) -> Any:
        """A sealed reservation over complete staging, with no intent recorded."""
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
        self.assertIsNotNone(
            reservation.staged_manifest_sha256,
            "the reservation must have been sealed to its staged output",
        )
        self.assertIsNone(retained_commit.read_publication_intent(self.workspace))
        self.assertEqual(effects, ["effect"])
        return reservation, authority

    def assert_preserved(self, reservation: Any, effects: list[str]) -> None:
        before = (self.workspace / "experiment-state.json").read_text()
        with self.patched_effect(effects):
            refused = self.prepare(
                authority=self.authority(reservation.candidate_sha256)
            )
        self.assertEqual(effects, ["effect"], "nothing may be re-run here")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in refused.blockers],
        )
        self.assertIsNotNone(
            retained_commit.read_reservation(self.workspace),
            "a sealed reservation must survive as evidence",
        )
        self.assertTrue(
            retained_commit.staging_directory(
                self.workspace, reservation.transaction_id
            ).is_dir(),
            "the staged output must survive as evidence",
        )
        self.assertEqual((self.workspace / "experiment-state.json").read_text(), before)


class SealedDamagedStagingTests(SealedTransactionFixture):
    """A seal is proof a complete transaction existed, so damage is not absence."""

    def test_damaged_staging_under_a_sealed_reservation_is_not_swept_away(
        self,
    ) -> None:
        """read_staged rightly answers "not a recovery source"; that is not "absent".

        Once the reservation is sealed, a staging tree that can no longer reproduce
        the sealed manifest is a damaged commit. Clearing it is the same mistake the
        publication intent already refuses to make, one record earlier.
        """
        effects: list[str] = []
        reservation, _ = self.sealed_but_unpublished(effects)
        (
            retained_commit.staging_directory(
                self.workspace, reservation.transaction_id
            )
            / retained_commit.LEDGER_FILENAME
        ).unlink()
        self.assertIsNone(
            retained_commit.read_staged(self.workspace, reservation.transaction_id)
        )
        self.assert_preserved(reservation, effects)


class MalformedRecordedSnapshotTests(SealedTransactionFixture):
    """Structurally invalid is a third answer, not a different valid one."""

    def test_a_structurally_invalid_record_is_not_a_superseding_snapshot(
        self,
    ) -> None:
        """A digest field that is not a digest changes the snapshot's identity.

        Recovery compares staged output against that identity, so a malformed
        record reads as "somebody else committed since" and the staged evidence is
        discarded as obsolete.
        """
        effects: list[str] = []
        reservation, _ = self.sealed_but_unpublished(effects)
        path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(path.read_text())
        record["state_sha256"] = "x"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        self.assert_preserved(reservation, effects)

    def test_a_non_canonical_transaction_id_in_the_record_is_refused(self) -> None:
        effects: list[str] = []
        reservation, _ = self.sealed_but_unpublished(effects)
        path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(path.read_text())
        record["transaction_id"] = "../../elsewhere"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        self.assert_preserved(reservation, effects)


class StagingRootSwapTests(ConsumptionFixture):
    """A descriptor helps only if the path to it could not change on the way."""

    def test_swapping_the_staging_root_after_validation_redirects_nothing(
        self,
    ) -> None:
        """O_NOFOLLOW guards the last component; the ones above it are still a path.

        The transaction directory itself is a real directory in the attacker's tree,
        so nothing the final open sees is a symlink. The kernel has already followed
        the intermediate component by then, and every descriptor-relative write that
        follows is anchored to the wrong directory.

        The swap is driven from the seam that resolves the staging root, which is
        the only moment it can be exercised deterministically. The assertions are
        about the tree outside the workspace, not about which function ran.
        """
        outside = self.root / "outside-the-workspace"
        transaction = retained_commit.new_transaction_id()
        (outside / transaction).mkdir(parents=True)
        (outside / transaction / "evidence.json").write_text("someone else's file\n")
        before = sorted(entry.name for entry in (outside / transaction).iterdir())

        real_resolver = retained_commit._open_child_directory
        swapped: list[str] = []

        def swap_after_resolving(parent_fd: int, name: str, *, create: bool) -> Any:
            resolved = real_resolver(parent_fd, name, create=create)
            if name == retained_commit.STAGING_DIRECTORY and not swapped:
                swapped.append("swapped")
                # The staging root has just been resolved. It is now renamed away
                # and replaced by a symlink into somebody else's tree, before the
                # transaction directory beneath it is reached.
                staging = self.workspace / retained_commit.STAGING_DIRECTORY
                staging.rename(staging.with_name("real-staging"))
                staging.symlink_to(outside, target_is_directory=True)
            return resolved

        with mock.patch.object(
            retained_commit, "_open_child_directory", side_effect=swap_after_resolving
        ):
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
                pass  # refusing is a correct outcome; writing outside is not

        self.assertEqual(swapped, ["swapped"], "the swap never happened")
        self.assertEqual(
            sorted(entry.name for entry in (outside / transaction).iterdir()),
            before,
            "a swapped intermediate component must not redirect a write outside "
            "the retained workspace",
        )


if __name__ == "__main__":
    unittest.main()
