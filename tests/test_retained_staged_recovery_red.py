"""RED for the crash window between staging and a durable publication intent.

The intent makes an interrupted publication discoverable, but it is written inside
publish(), after the transaction's output is already complete and durable. There is
therefore a legitimate crash state the intent cannot describe:

    the effect happened, the claim is consumed,
    the reservation is installed,
    the staged output is complete and valid,
    and no publication intent exists yet

The existing forward-recovery coverage crashes while the commit record is written,
by which point the intent is durable. It proves that an intent plus staged evidence
is recoverable; it does not prove that a reservation plus staged evidence is. This
states the second, which is the contract already agreed: a dead reservation with a
complete valid staged transaction is finished forward with no new effect.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.

At head 6d210f02272157845d54064f4b874f6a82bf03f6 this is expected to be RED.
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


class StagedWithoutIntentRecoveryTests(ConsumptionFixture):
    """A transaction that died before it could say it was publishing."""

    def test_complete_staging_under_a_dead_reservation_is_finished_forward(
        self,
    ) -> None:
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

        # The effect patch spans the retry, so an effect opened during recovery is
        # counted rather than escaping to the real implementation.
        with mock.patch.object(compiler, "qualify_subjects", side_effect=qualify):
            with mock.patch.object(
                retained_commit,
                "_write_publication_intent",
                side_effect=RuntimeError("died before the intent became durable"),
            ):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)

            # Exactly the retained state the intent cannot describe.
            reservation = retained_commit.read_reservation(self.workspace)
            self.assertIsNotNone(reservation, "the reservation must still be there")
            assert reservation is not None
            self.assertIsNone(
                retained_commit.read_publication_intent(self.workspace),
                "the transaction died before any intent became durable",
            )
            staged = retained_commit.read_staged(
                self.workspace, reservation.transaction_id
            )
            self.assertIsNotNone(
                staged, "its output must be complete and durable on disk"
            )
            self.assertEqual(effects, ["effect"], "the oracle ran exactly once")

            recovered = self.prepare(authority=authority)

        self.assertEqual(
            effects,
            ["effect"],
            "recovery must never repeat an irreversible effect that already ran",
        )
        self.assertEqual(
            recovered.status,
            "READY_FOR_OWNER_REVIEW",
            "a dead reservation with complete valid staged output must be finished "
            "forward, not swept away while its effect claim keeps the candidate "
            "consumed",
        )
        record = json.loads(
            (self.workspace / retained_commit.COMMIT_RECORD_FILENAME).read_text()
        )
        self.assertEqual(
            record["transaction_id"],
            reservation.transaction_id,
            "the staged transaction itself must become the committed one",
        )
        self.assertEqual(
            compiler.status(self.workspace)["status"], "READY_FOR_OWNER_REVIEW"
        )


if __name__ == "__main__":
    unittest.main()
