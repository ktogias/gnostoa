"""The frozen run plan.

The lock does not merely carry arm and assignment metadata; it carries the exact
list of runs those metadata imply. `execute` consumes that list rather than
re-deriving it, so what runs is fixed at execution freeze.

Each entry selects exactly one arm. An entry never carries the sibling arm's packet,
and the executor capsule it describes never admits the reference, oracle, key or
qualification workspace.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tools.capsule.identity import digest_of

PLAN_SCHEMA = "gnostoa-experiment-run-plan/v1"


@dataclass(frozen=True, slots=True)
class RunEntry:
    id: str
    task: str
    arm: str
    repetition: int
    arm_inputs: tuple[Mapping[str, str], ...] = ()

    def as_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "task": self.task,
            "arm": self.arm,
            "repetition": self.repetition,
            "arm_inputs": [dict(item) for item in self.arm_inputs],
        }


@dataclass(frozen=True, slots=True)
class RunPlan:
    entries: tuple[RunEntry, ...]

    @property
    def identity(self) -> str:
        return digest_of(self.as_json())

    def __len__(self) -> int:
        return len(self.entries)

    def as_json(self) -> dict[str, object]:
        return {
            "schema": PLAN_SCHEMA,
            "runs": [entry.as_json() for entry in self.entries],
            "count": len(self.entries),
        }


def compile_plan(
    *,
    task_ids: Sequence[str],
    arms: Sequence[str],
    repetitions: int,
    arm_inputs: Mapping[str, Sequence[Mapping[str, str]]],
) -> RunPlan:
    """Expand task x repetition x arm into an explicit, ordered list of runs."""
    entries: list[RunEntry] = []
    selected_arms = list(arms) if arms else ["default"]
    for task in task_ids:
        for repetition in range(1, repetitions + 1):
            for arm in selected_arms:
                entries.append(
                    RunEntry(
                        id=f"{task}/r{repetition}/{arm}",
                        task=task,
                        arm=arm,
                        repetition=repetition,
                        # Only this arm's packet. The sibling arm is never attached.
                        arm_inputs=tuple(
                            dict(item) for item in arm_inputs.get(arm, ())
                        ),
                    )
                )
    return RunPlan(entries=tuple(entries))
