"""RED for a retained lock that becomes uncomparable between two observations.

A lock that is already invalid when a prepare begins is refused by the retained
transaction layer, which validates it canonically -- see
``test_retained_lock_validity_red``. That is the lower layer, and it is the right
place for the check.

It is not the only place the question is asked. Between the committed read at the
start of a prepare and the currentness comparison later in it, the lock is observed
again, and it can stop being comparable in between. These cases damage it exactly
there, from the seam that resolves the retained completion, and require the retained
success to survive whatever the prepare does next.

What they pin is the end-to-end guarantee, not a particular layer, and that
distinction is deliberate. With canonical validation in the transaction layer, the
refusal these cases observe comes from ``finish()`` re-reading the committed
snapshot, which reports ``retained-state-inconsistent``. Disabling the upper-layer
preservation leaves them passing for that reason. The upper layer -- treating a lock
that cannot be compared as ambiguity rather than drift -- is kept as depth, but no
case here isolates it, and no case in this file should be read as evidence that it
does.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.
"""

from __future__ import annotations

import json
import unittest
from typing import Any
from unittest import mock

from tools.capsule import authority as authority_module
from tools.capsule import compiler, qualification, retained_commit, retained_preflight

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


class UncomparableLockRaceTests(ConsumptionFixture):
    """A retained success survives a lock that stops being comparable mid-prepare."""

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

    def _reach_ready(self, effects: list[str]) -> tuple[str, dict[str, bytes]]:
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        with self.patched_effect(effects):
            self.prepare(authority=self.authority(candidate))
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )
        retained = {
            name: (self.workspace / name).read_bytes()
            for name in (
                retained_commit.STATE_FILENAME,
                retained_commit.LEDGER_FILENAME,
            )
        }
        return candidate, retained

    def _invalidate_the_lock(self) -> None:
        """Leave the recorded identity in place so only canonical loading refuses."""
        path = self.workspace / retained_commit.LOCK_FILENAME
        payload = json.loads(path.read_text())
        payload["artifact_store"] = "/somewhere/else"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _damaging_seam(self, damaged: list[str]) -> Any:
        """Damage the lock after the retained completion is resolved.

        That is the statement immediately before the currentness comparison, so the
        prepare has already read and accepted the committed snapshot and everything
        after it is deciding on a workspace that has changed underneath.
        """
        real = retained_preflight.matching_completed_candidate_stage

        def damage_after_matching(root: Any, ledger: Any, **kwargs: Any) -> Any:
            stage = real(root, ledger, **kwargs)
            if not damaged:
                damaged.append("damaged")
                self._invalidate_the_lock()
            return stage

        return mock.patch.object(
            retained_preflight,
            "matching_completed_candidate_stage",
            side_effect=damage_after_matching,
        )

    def _assert_preserved(
        self, damaged: list[str], retained: dict[str, bytes], result: Any
    ) -> None:
        self.assertEqual(damaged, ["damaged"], "the lock never became uncomparable")
        self.assertNotEqual(result.status, "READY_FOR_OWNER_REVIEW")
        for name, contents in retained.items():
            self.assertEqual(
                (self.workspace / name).read_bytes(),
                contents,
                f"retained {name} must survive byte for byte",
            )

    def test_an_authority_less_prepare_preserves_across_the_race(self) -> None:
        effects: list[str] = []
        _, retained = self._reach_ready(effects)
        damaged: list[str] = []
        with self.patched_effect(effects), self._damaging_seam(damaged):
            refused = self.prepare()
        self.assertEqual(effects, ["effect"], "no new effect may run")
        self._assert_preserved(damaged, retained, refused)

    def test_a_non_covering_authority_preserves_across_the_race(self) -> None:
        effects: list[str] = []
        _, retained = self._reach_ready(effects)
        elsewhere = authority_module.PreflightAuthority(
            id="auth-elsewhere",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256="0" * 64,
        )
        damaged: list[str] = []
        with self.patched_effect(effects), self._damaging_seam(damaged):
            refused = self.prepare(authority=elsewhere)
        self.assertEqual(effects, ["effect"], "no new effect may run")
        self._assert_preserved(damaged, retained, refused)

    def test_the_correct_authority_preserves_across_the_race(self) -> None:
        """The same ambiguity reached one step later, through the lock conflict.

        With the correct authority the preparation runs on and rebuilds the lock,
        which no longer reconciles with the damaged one on disk. Whichever refusal
        arrives first, the completed success must still be there afterwards.
        """
        effects: list[str] = []
        candidate, retained = self._reach_ready(effects)
        damaged: list[str] = []
        with self.patched_effect(effects), self._damaging_seam(damaged):
            refused = self.prepare(authority=self.authority(candidate))
        self.assertEqual(effects, ["effect"], "no new effect may run")
        self.assertIn(
            "experiment-lock-conflict",
            [blocker["code"] for blocker in refused.blockers],
        )
        self._assert_preserved(damaged, retained, refused)


if __name__ == "__main__":
    unittest.main()
