"""Commit-record integrity invariants for the retained-workspace transaction model.

These are the three properties the generation-marker invariants of
``test_preflight_transaction_red`` state, expressed against the committed record
that replaced the counter. They are deliberately written as observable workspace
outcomes rather than against any particular recording mechanism: missing, valid and
inconsistent retained state are three states, a crash between publishing files and
recording them must not read back as an older valid version, and a caller holding a
snapshot taken before another transaction landed must not overwrite it.

The fixture is synthetic and the qualification effect is patched, so no Phase-D
material, hidden oracle, runner or container effect participates.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from unittest import mock

from tools.capsule import compiler, qualification, retained_commit

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


def _receipt(task_id: str, bound: dict[str, str]) -> qualification.QualificationReceipt:
    outcome = qualification.SubjectOutcome(
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
        base=outcome,
        reference=reference,
        bound=bound,
    )


def _patched_effect() -> mock._patch[mock.MagicMock]:
    return mock.patch.object(
        compiler,
        "qualify_subjects",
        side_effect=lambda *a, **k: _receipt(
            k.get("task_id", "T1"), dict(k.get("bound") or {})
        ),
    )


class CommitRecordIntegrityTests(ConsumptionFixture):
    def _codes(self, result: compiler.PrepareResult) -> list[object]:
        return [blocker["code"] for blocker in result.blockers]

    def _committed_generation(self) -> int | None:
        path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        if not path.is_file():
            return None
        generation = json.loads(path.read_text())["generation"]
        assert isinstance(generation, int)
        return generation

    def test_an_unreadable_record_is_not_the_initial_state(self) -> None:
        """Missing, valid and inconsistent are three states, not two.

        Collapsing an unreadable record onto "never committed" is what lets a
        damaged workspace be rewritten as though it were empty.
        """
        self.prepare()
        record = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        damaged = "{ not valid json"
        record.write_text(damaged)

        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)

        result = self.prepare()
        self.assertIn(retained_commit.INCONSISTENT_STATE, self._codes(result))
        self.assertEqual(
            record.read_text(),
            damaged,
            "an inconsistent workspace is evidence and must not be repaired in place",
        )

    def test_a_crash_before_the_record_lands_is_not_an_older_valid_version(
        self,
    ) -> None:
        """The record is written last, so a torn commit fails closed.

        If the files could move forward while the record still described the older
        version, that older version would read back as valid and a writer holding it
        would legitimately overwrite state newer than it ever saw.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        before = (self.workspace / "experiment-state.json").read_text()
        real_write = retained_commit._write_atomic

        def crash_before_recording(path, payload):  # type: ignore[no-untyped-def]
            if path.name == retained_commit.COMMIT_RECORD_FILENAME:
                raise RuntimeError("crash between publishing and recording")
            return real_write(path, payload)

        with (
            _patched_effect(),
            mock.patch.object(
                retained_commit, "_write_atomic", side_effect=crash_before_recording
            ),
        ):
            with self.assertRaises(RuntimeError):
                self.prepare(authority=self.authority(candidate))

        self.assertNotEqual(
            (self.workspace / "experiment-state.json").read_text(),
            before,
            "the interrupted transaction must genuinely have moved the files forward",
        )
        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)

        after = (self.workspace / "experiment-state.json").read_text()

        # A later invocation finishes the interrupted transaction forward from its own
        # durable staging rather than refusing it -- see ForwardRecoveryTests -- but
        # what it publishes must be that transaction's bytes and nothing else. An
        # implementation free to invent content here would satisfy "recovered" while
        # rewriting evidence it never produced.
        self.prepare()
        self.assertEqual(
            (self.workspace / "experiment-state.json").read_text(),
            after,
            "recovery must publish the interrupted transaction's own output",
        )
        restored = retained_commit.read_committed(self.workspace)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(
            restored.state_sha256,
            hashlib.sha256(after.encode()).hexdigest(),
            "the restored record must describe the recovered bytes",
        )

    def test_a_snapshot_taken_before_a_completion_cannot_overwrite_it(self) -> None:
        """Coherence is a property of the pair, not of the token alone.

        The caller loads a pre-completion workspace and the completed one lands
        underneath it. Whatever it holds, it must not replace successful evidence
        with a view that predates it.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        old_snapshot = self.root / "snapshot-before-completion"
        shutil.copytree(self.workspace, old_snapshot)

        with _patched_effect():
            self.prepare(authority=self.authority(candidate))
        winner = compiler.status(self.workspace)
        self.assertEqual(winner["status"], "READY_FOR_OWNER_REVIEW")
        winner_generation = self._committed_generation()
        completed_snapshot = self.root / "snapshot-after-completion"
        shutil.copytree(self.workspace, completed_snapshot)

        shutil.rmtree(self.workspace)
        shutil.copytree(old_snapshot, self.workspace)

        torn: list[str] = []
        real_identity = compiler.preflight_candidate_identity

        def land_the_completion_underneath(**kwargs):  # type: ignore[no-untyped-def]
            # The caller has already taken its snapshot of the retained workspace;
            # the completed transaction becomes visible only now.
            if not torn:
                torn.append("torn")
                shutil.rmtree(self.workspace)
                shutil.copytree(completed_snapshot, self.workspace)
            return real_identity(**kwargs)

        with mock.patch.object(
            compiler,
            "preflight_candidate_identity",
            side_effect=land_the_completion_underneath,
        ):
            stale = self.prepare()

        self.assertEqual(torn, ["torn"])
        # Non-vacuity: the stale caller ran to completion on a workspace that had
        # moved underneath it and published nothing. Asserting only that the winner
        # survived would also pass if the caller had returned early for an unrelated
        # reason, so the committed history is asserted not to have advanced.
        self.assertNotEqual(stale.status, "READY_FOR_OWNER_REVIEW")
        self.assertEqual(
            self._committed_generation(),
            winner_generation,
            "a caller holding a superseded snapshot must not advance the committed "
            "history",
        )
        current = compiler.status(self.workspace)
        self.assertEqual(
            current["status"],
            "READY_FOR_OWNER_REVIEW",
            "a stale snapshot must not authorise overwriting newer committed state",
        )
        self.assertEqual(current["lock_sha256"], winner["lock_sha256"])


if __name__ == "__main__":
    unittest.main()
