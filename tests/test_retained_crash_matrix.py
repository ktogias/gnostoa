"""Crash at every durable write of an authorised prepare, one boundary at a time.

Hand-written crash cases pick the two or three boundaries their author thought of.
This walks all of them: every durable write the retained transaction performs --
the workspace-root metadata files and the staged members alike -- is failed in turn,
and the workspace is then driven forward twice more with the same authority.

The contract is not "every crash recovers". It is:

    never a second effect
    recover where the provenance is sufficient
    otherwise preserve and fail closed

The middle and last clauses are both intended outcomes. A transaction that dies after
its effect and before the reservation is sealed has staged output that nothing
outside the staging directory vouches for, and the protocol deliberately keeps those
bytes without publishing them; the effect claim remains the fence. That case is
asserted explicitly rather than allowed to look like a failure to recover.

The fixture is synthetic and the qualification effect is patched and counted; no
Phase-D material, hidden oracle, runner or container effect participates.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from tools.capsule import compiler, qualification, retained_commit

try:
    from test_preflight_authority_consumption import ConsumptionFixture
except ImportError:  # invoked as tests.<module> from the repository root
    from tests.test_preflight_authority_consumption import ConsumptionFixture


def _receipt(task_id: str, bound: dict[str, str]) -> qualification.QualificationReceipt:
    def outcome(subject: str, passed: tuple[str, ...], failed: tuple[str, ...]) -> Any:
        return qualification.SubjectOutcome(
            subject=subject,
            collected=True,
            passed=passed,
            failed=failed,
            error_types={},
            classification=qualification.MATCH,
            detail="synthetic",
        )

    return qualification.QualificationReceipt(
        task=task_id,
        backend="local-python",
        base=outcome("base", (), ("test_discriminates",)),
        reference=outcome("reference", ("test_discriminates",), ()),
        bound=bound,
    )


class Outcome:
    """What one injected crash produced."""

    def __init__(self, name: str, effects: int, first: str, second: str) -> None:
        self.name = name
        self.effects = effects
        self.first = first
        self.second = second
        self.blockers: list[str] = []


class RetainedDurableWriteCrashMatrixTests(ConsumptionFixture):
    def _patched_effect(self, effects: list[str]) -> Any:
        def qualify(*args: object, **kwargs: object) -> Any:
            del args
            effects.append("effect")
            task_id = kwargs.get("task_id", "T1")
            bound = kwargs.get("bound") or {}
            assert isinstance(task_id, str)
            assert isinstance(bound, dict)
            return _receipt(task_id, dict(bound))

        return mock.patch.object(compiler, "qualify_subjects", side_effect=qualify)

    def _durable_writes(self) -> list[str]:
        """Every durable write a clean authorised prepare performs, in order."""
        self.setUp()
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        seen: list[str] = []
        real = retained_commit._write_at

        def record(directory_fd: int, name: str, payload: bytes) -> None:
            seen.append(name)
            return real(directory_fd, name, payload)

        with self._patched_effect([]):
            with mock.patch.object(retained_commit, "_write_at", side_effect=record):
                self.prepare(authority=self.authority(candidate))
        return seen

    def _crash_at(self, index: int, *, keep_blockers: bool = False) -> Outcome:
        """Fail the index-th durable write, then drive the workspace forward twice."""
        self.setUp()
        observed = self.prepare()
        candidate = observed.preflight_candidate_sha256
        assert candidate is not None
        authority = self.authority(candidate)
        effects: list[str] = []
        seen: list[str] = []
        real = retained_commit._write_at

        def crash(directory_fd: int, name: str, payload: bytes) -> None:
            seen.append(name)
            if len(seen) == index:
                raise RuntimeError(f"crash at durable write {index} ({name})")
            return real(directory_fd, name, payload)

        with self._patched_effect(effects):
            with mock.patch.object(retained_commit, "_write_at", side_effect=crash):
                with self.assertRaises(RuntimeError):
                    self.prepare(authority=authority)
            first = self.prepare(authority=authority)
            second = self.prepare(authority=authority)
        outcome = Outcome(seen[index - 1], len(effects), first.status, second.status)
        if keep_blockers:
            outcome.blockers = [str(blocker["code"]) for blocker in first.blockers]
        return outcome

    def test_no_durable_write_boundary_permits_a_second_effect(self) -> None:
        """The #197 guarantee, walked over every boundary rather than a chosen few."""
        boundaries = self._durable_writes()
        self.assertGreaterEqual(
            len(boundaries), 8, "the transaction should perform several durable writes"
        )
        for index in range(1, len(boundaries) + 1):
            with self.subTest(boundary=index, name=boundaries[index - 1]):
                outcome = self._crash_at(index)
                self.assertLessEqual(
                    outcome.effects,
                    1,
                    "an interrupted transaction must never permit a second effect",
                )
                self.assertIn(
                    outcome.first,
                    ("READY_FOR_OWNER_REVIEW", "BLOCKED"),
                    "a retry must either recover or refuse, never anything else",
                )
                self.assertEqual(
                    outcome.first,
                    outcome.second,
                    "a settled workspace must not change on being asked again",
                )

    def test_a_crash_before_the_seal_keeps_the_staged_result(self) -> None:
        """The one boundary that deliberately does not recover.

        Between the output being staged and the reservation being sealed to it,
        nothing outside the staging directory vouches for those bytes. The protocol
        keeps them and refuses to publish, and the effect claim keeps the candidate
        consumed. Asserted here so the accepted limitation cannot be mistaken for a
        regression, and cannot be quietly removed either.
        """
        boundaries = self._durable_writes()
        seal = [
            index
            for index, name in enumerate(boundaries, start=1)
            if name == retained_commit.RESERVATION_FILENAME
        ]
        self.assertEqual(
            len(seal), 2, "the reservation is written once to install and once to seal"
        )

        outcome = self._crash_at(seal[1], keep_blockers=True)
        self.assertEqual(outcome.effects, 1, "the effect ran exactly once")
        # The refusal must come from the effect claim, which is what the protocol
        # nominates as the fence here. A workspace left permanently inconsistent
        # instead would also read as BLOCKED, and is a different -- worse -- outcome.
        self.assertIn(
            "preflight-candidate-already-consumed",
            outcome.blockers,
            "the consumed candidate must be what refuses the retry",
        )
        self.assertNotIn(retained_commit.INCONSISTENT_STATE, outcome.blockers)
        self.assertEqual(
            outcome.first,
            "BLOCKED",
            "output the reservation was never sealed to must not be published",
        )
        self.assertEqual(outcome.second, "BLOCKED")

        staging = self.workspace / retained_commit.STAGING_DIRECTORY
        staged_manifests = (
            sorted(
                entry.name for entry in staging.rglob(retained_commit.MANIFEST_FILENAME)
            )
            if staging.is_dir()
            else []
        )
        self.assertEqual(
            staged_manifests,
            [retained_commit.MANIFEST_FILENAME],
            "the completed result must be kept even though it cannot be published",
        )

    def test_a_crash_installing_the_reservation_still_recovers(self) -> None:
        """The mirror case: nothing irreversible happened, so the candidate survives."""
        boundaries = self._durable_writes()
        first_reservation = next(
            index
            for index, name in enumerate(boundaries, start=1)
            if name == retained_commit.RESERVATION_FILENAME
        )
        outcome = self._crash_at(first_reservation)
        self.assertLessEqual(outcome.effects, 1)
        self.assertEqual(
            outcome.first,
            "READY_FOR_OWNER_REVIEW",
            "a transaction that died before crossing the boundary must be runnable",
        )


if __name__ == "__main__":
    unittest.main()
