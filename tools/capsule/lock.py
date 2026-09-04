"""The immutable experiment lock.

`experiment-state.json` is mutable working state. This module produces the separate,
write-once `experiment.lock`: the content-addressed record binding every identity a
later `execute` needs, emitted only at EXECUTION_FROZEN. Writing a different lock to
an existing path is refused rather than silently overwritten.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from tools.capsule.identity import PRODUCER, digest_of

LOCK_SCHEMA = "gnostoa-experiment-lock/v1"
LOCK_FILENAME = "experiment.lock"


class LockError(RuntimeError):
    """The lock cannot be written or is inconsistent with an existing lock."""


@dataclass(frozen=True, slots=True)
class ExperimentLock:
    payload: Mapping[str, object]

    @property
    def identity(self) -> str:
        return digest_of(dict(self.payload))

    def write(self, root: Path) -> Path:
        path = root / LOCK_FILENAME
        serialized = json.dumps(
            {**self.payload, "lock_sha256": self.identity}, indent=2, sort_keys=True
        )
        if path.is_file():
            existing = path.read_text()
            if existing.strip() != serialized.strip():
                raise LockError(
                    "an experiment lock already exists with different content; a lock is "
                    "immutable and is never silently overwritten"
                )
            return path
        path.write_text(serialized + "\n")
        return path


def build(
    *,
    experiment_id: str,
    question: str,
    claim_boundary: str,
    launch: Mapping[str, object],
    tasks: Sequence[Mapping[str, object]],
    capabilities: Sequence[Mapping[str, object]],
    stage_receipts: Mapping[str, str],
    authority: Mapping[str, object],
) -> ExperimentLock:
    """Bind every identity a later execute needs, with no rediscovery."""
    payload: dict[str, object] = {
        "schema": LOCK_SCHEMA,
        "producer": PRODUCER,
        "experiment": {
            "id": experiment_id,
            "question": question,
            "claim_boundary": claim_boundary,
        },
        "authority": dict(authority),
        "launch": dict(launch),
        "capabilities": [dict(item) for item in capabilities],
        "tasks": [dict(task) for task in tasks],
        "stage_receipts": dict(stage_receipts),
    }
    return ExperimentLock(payload=payload)


def load(path: Path) -> Mapping[str, object]:
    payload: Mapping[str, object] = json.loads(path.read_text())
    if payload.get("schema") != LOCK_SCHEMA:
        raise LockError(f"unsupported lock schema {payload.get('schema')!r}")
    recorded = payload.get("lock_sha256")
    recomputed = digest_of({k: v for k, v in payload.items() if k != "lock_sha256"})
    if recorded != recomputed:
        raise LockError("lock digest does not match its content")
    return payload
