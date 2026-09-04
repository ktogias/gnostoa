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
from typing import cast

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
    schedule_source: str = "none"
    schedule_sha256: str | None = None

    @property
    def identity(self) -> str:
        return digest_of(self.as_json())

    def __len__(self) -> int:
        return len(self.entries)

    def as_json(self) -> dict[str, object]:
        return {
            "schema": PLAN_SCHEMA,
            "schedule_source": self.schedule_source,
            "schedule_sha256": self.schedule_sha256,
            "runs": [entry.as_json() for entry in self.entries],
            "count": len(self.entries),
        }


def compile_plan(
    *,
    schedule: Sequence[Mapping[str, object]],
    arm_inputs: Mapping[str, Sequence[Mapping[str, str]]],
    schedule_source: str,
    schedule_sha256: str | None,
) -> RunPlan:
    """Expand the preregistered schedule verbatim, preserving its exact order.

    The compiler does not choose an order. Assignment order is experiment material,
    so it is declared and frozen; re-deriving or re-randomising it here would silently
    replace preregistered material with a default.
    """
    entries = tuple(
        RunEntry(
            id=f"{item['task']}/r{item['repetition']}/{item['arm']}",
            task=str(item["task"]),
            arm=str(item["arm"]),
            repetition=int(cast(int, item["repetition"])),
            # Only this arm's packet. The sibling arm is never attached.
            arm_inputs=tuple(
                dict(entry) for entry in arm_inputs.get(str(item["arm"]), ())
            ),
        )
        for item in schedule
    )
    return RunPlan(
        entries=entries,
        schedule_source=schedule_source,
        schedule_sha256=schedule_sha256,
    )
