"""RED for the difference between a lock proved different and a lock not comparable.

``retained_lock_material_matches`` answers a single False for both, and its caller
reads that as downstream drift: the retained READY is treated as stale and an
authority refusal publishes over it. Those are not the same answer.

    the lock loads and differs        the retained READY is genuinely stale
    the lock cannot be loaded at all  nothing is known about whether it is stale

Only the first justifies replacing a completed success. The second is ambiguous
retained evidence, which everywhere else in this model is preserved and reported
rather than overwritten.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head 88828bb63e0893d4066c63340506dbc847def436 these are expected to be RED.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from typing import Any
from unittest import mock

from tools.capsule import authority as authority_module
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


class UncomparableLockTests(ConsumptionFixture):
    """Ambiguous retained evidence must be preserved, not replaced."""

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

    def _ready_with_an_uncomparable_lock(self, effects: list[str]) -> dict[str, bytes]:
        """A legitimately READY workspace whose lock no longer loads canonically.

        The commit record is re-sealed over the altered bytes, so the workspace stays
        internally coherent: this is not the accidental-damage case, which the
        transaction layer already refuses at read_committed.
        """
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect(effects):
            self.prepare(authority=self.authority(candidate))
        return self._damage_the_lock()

    def _damage_the_lock(self) -> dict[str, bytes]:
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )

        lock_path = self.workspace / retained_commit.LOCK_FILENAME
        payload = json.loads(lock_path.read_text())
        payload["artifact_store"] = "/somewhere/else"
        lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        record_path = self.workspace / retained_commit.COMMIT_RECORD_FILENAME
        record = json.loads(record_path.read_text())
        record["lock_file_sha256"] = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

        # The workspace vouches for itself, and the lock still cannot be compared.
        retained_commit.read_committed(self.workspace)
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

    def _assert_intact(self, before: dict[str, bytes], result: Any) -> None:
        self.assertNotEqual(result.status, "READY_FOR_OWNER_REVIEW")
        for name, contents in before.items():
            self.assertEqual(
                (self.workspace / name).read_bytes(),
                contents,
                f"retained {name} must survive byte for byte",
            )

    def test_an_authority_less_prepare_does_not_replace_an_uncomparable_ready(
        self,
    ) -> None:
        effects: list[str] = []
        before = self._ready_with_an_uncomparable_lock(effects)
        with self.patched_effect(effects):
            refused = self.prepare()
        self.assertEqual(effects, ["effect"], "no new effect may run")
        self._assert_intact(before, refused)

    def test_a_non_covering_authority_does_not_replace_an_uncomparable_ready(
        self,
    ) -> None:
        effects: list[str] = []
        before = self._ready_with_an_uncomparable_lock(effects)
        elsewhere = authority_module.PreflightAuthority(
            id="auth-elsewhere",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256="0" * 64,
        )
        with self.patched_effect(effects):
            refused = self.prepare(authority=elsewhere)
        self.assertEqual(effects, ["effect"], "no new effect may run")
        self._assert_intact(before, refused)

    def test_the_correct_authority_does_not_replace_an_uncomparable_ready(
        self,
    ) -> None:
        """The same ambiguity one step later, reached by the authorised caller.

        With the correct authority the preparation runs on to rebuild the lock and
        meets the retained one, which it cannot reconcile with. The conflict says
        the two differ; it does not say the retained success is obsolete.
        """
        effects: list[str] = []
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect(effects):
            self.prepare(authority=self.authority(candidate))
        before = self._damage_the_lock()

        with self.patched_effect(effects):
            refused = self.prepare(authority=self.authority(candidate))

        self.assertEqual(effects, ["effect"], "no new effect may run")
        self.assertIn(
            "experiment-lock-conflict",
            [blocker["code"] for blocker in refused.blockers],
        )
        self._assert_intact(before, refused)


if __name__ == "__main__":
    unittest.main()
