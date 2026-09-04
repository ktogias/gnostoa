"""The frozen run plan.

The lock does not merely carry arm and assignment metadata; it carries the exact
list of runs those metadata imply. `execute` consumes that list rather than
re-deriving it, so what runs is fixed at execution freeze.

Each entry selects exactly one arm. An entry never carries the sibling arm's packet,
and the executor capsule it describes never admits the reference, oracle, key or
qualification workspace.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from tools.capsule.identity import digest_of

PLAN_SCHEMA = "gnostoa-experiment-run-plan/v1"


def validate_schedule(
    *,
    schedule: Sequence[Mapping[str, object]],
    task_ids: Sequence[str],
    arms: Sequence[str],
    repetitions: int,
) -> list[str]:
    """Reasons the schedule is not exactly the preregistered set of runs.

    A frozen order is not enough on its own. The schedule must be a permutation of
    tasks x repetitions x arms: an omitted, duplicated or extra entry would silently
    change how many runs the experiment actually performs, and two identical entries
    would additionally collide on one run identity, evidence path and result key.
    """
    expected = Counter(
        (task, repetition, arm)
        for task in task_ids
        for repetition in range(1, repetitions + 1)
        for arm in arms
    )
    observed: Counter[tuple[str, int, str]] = Counter()
    reasons: list[str] = []
    for index, entry in enumerate(schedule):
        try:
            repetition = int(cast(int, entry["repetition"]))
        except (KeyError, TypeError, ValueError):
            reasons.append(f"schedule[{index}] has no usable repetition")
            continue
        if not 1 <= repetition <= repetitions:
            reasons.append(
                f"schedule[{index}] repetition {repetition} is outside 1..{repetitions}"
            )
            continue
        observed[(str(entry["task"]), repetition, str(entry["arm"]))] += 1

    duplicated = sorted(key for key, count in observed.items() if count > 1)
    if duplicated:
        reasons.append(f"duplicate scheduled runs: {duplicated}")
    missing = sorted((expected - observed).elements())
    if missing:
        reasons.append(f"missing scheduled runs: {missing}")
    extra = sorted(key for key in (observed - expected) if key not in set(duplicated))
    if extra:
        reasons.append(f"unexpected scheduled runs: {extra}")
    return reasons


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
    identities = [
        f"{item['task']}/r{item['repetition']}/{item['arm']}" for item in schedule
    ]
    if len(set(identities)) != len(identities):
        collisions = sorted({name for name in identities if identities.count(name) > 1})
        raise ValueError(f"schedule produces colliding run identities: {collisions}")

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
