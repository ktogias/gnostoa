"""RED for canonical lock validity at the retained reporting boundary, at 830a248d.

The READY provenance chain establishes that every retained reference names the same
lock identity string. It does not establish that the lock has that identity.
``read_committed`` reaches the lock through ``_published_lock_identity``, which reads
the ``lock_sha256`` field and returns it; the canonical contract recomputes the digest
over the payload and refuses a mismatch, and only ``execute`` and the currentness
check use it.

A lock whose payload is altered while its recorded identity is left intact, with the
commit record re-sealed over the new bytes, therefore satisfies every check the
retained transaction layer makes -- and ``status`` reports the workspace ready for
owner review while execution would refuse the lock it names.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head 830a248d18bc9afbeb861b02df550a9b78562383 the first two are expected to be
RED, and the third is a guard that must stay green.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from typing import Any
from unittest import mock

from tools.capsule import compiler, qualification, retained_commit
from tools.capsule import lock as lock_module

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


class CanonicallyInvalidLockTests(ConsumptionFixture):
    """A lock that declares an identity it does not carry is not a valid lock."""

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

    def _ready_then_invalidate_the_lock(self, effects: list[str]) -> dict[str, bytes]:
        """Reach READY, then make the lock declare an identity it does not carry.

        Only the payload changes; the recorded ``lock_sha256`` is left alone and the
        commit record is re-sealed over the new bytes, so every digest the retained
        transaction layer compares still agrees.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect(effects):
            self.prepare(authority=self.authority(candidate))
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )

        lock_path = self.workspace / retained_commit.LOCK_FILENAME
        payload = json.loads(lock_path.read_text())
        declared = payload["lock_sha256"]
        payload["artifact_store"] = "/somewhere/else"
        payload["lock_sha256"] = declared
        lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        record["lock_file_sha256"] = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

        # The canonical contract execution uses already refuses this lock.
        with self.assertRaises(lock_module.LockError):
            lock_module.load(lock_path)

        return {
            name: (self.workspace / name).read_bytes()
            for name in (
                retained_commit.STATE_FILENAME,
                retained_commit.LEDGER_FILENAME,
                retained_commit.LOCK_FILENAME,
            )
        }

    def test_read_committed_refuses_a_canonically_invalid_lock(self) -> None:
        """Naming an identity and carrying it are different claims."""
        self._ready_then_invalidate_the_lock([])
        with self.assertRaises(retained_commit.RetainedTransactionError) as raised:
            retained_commit.read_committed(self.workspace)
        self.assertEqual(raised.exception.code, retained_commit.INCONSISTENT_STATE)

    def test_status_does_not_report_ready_for_a_lock_execution_would_refuse(
        self,
    ) -> None:
        """status is the surface an operator reads, so it must not say ready here."""
        self._ready_then_invalidate_the_lock([])
        reported = compiler.status(self.workspace)
        self.assertEqual(
            reported["status"],
            "BLOCKED",
            "a workspace whose lock the canonical loader rejects is not ready",
        )
        self.assertIn(
            retained_commit.INCONSISTENT_STATE,
            [blocker["code"] for blocker in reported["blockers"]],
        )

    def test_preparing_against_it_runs_no_effect_and_rewrites_nothing(self) -> None:
        """Guard: the refusal must not become a reason to rebuild over the evidence."""
        effects: list[str] = []
        before = self._ready_then_invalidate_the_lock(effects)
        with self.patched_effect(effects):
            refused = self.prepare()
        self.assertEqual(effects, ["effect"], "no new effect may run")
        self.assertNotEqual(refused.status, "READY_FOR_OWNER_REVIEW")
        for name, contents in before.items():
            self.assertEqual(
                (self.workspace / name).read_bytes(),
                contents,
                f"retained {name} must survive byte for byte",
            )


if __name__ == "__main__":
    unittest.main()
