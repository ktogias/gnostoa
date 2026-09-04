"""Explicit, resumable preparation stages.

Each stage binds a digest over its complete declared inputs and records whether it
was merely entered or actually completed. Only a COMPLETE record with an unchanged
input digest may be reused, so an interrupted or failed stage can never be mistaken
for a qualified one. Any change invalidates the whole downstream closure.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tools.capsule.identity import digest_of

DISCOVERED = "DISCOVERED"
SEMANTIC_FROZEN = "SEMANTIC_FROZEN"
RUNTIME_PREPARED = "RUNTIME_PREPARED"
STATIC_QUALIFIED = "STATIC_QUALIFIED"
BASE_REFERENCE_QUALIFIED = "BASE_REFERENCE_QUALIFIED"
BOUNDARY_QUALIFIED = "BOUNDARY_QUALIFIED"
EXECUTION_FROZEN = "EXECUTION_FROZEN"
READY_FOR_OWNER_REVIEW = "READY_FOR_OWNER_REVIEW"

ORDER = [
    DISCOVERED,
    SEMANTIC_FROZEN,
    RUNTIME_PREPARED,
    STATIC_QUALIFIED,
    BASE_REFERENCE_QUALIFIED,
    BOUNDARY_QUALIFIED,
    EXECUTION_FROZEN,
    READY_FOR_OWNER_REVIEW,
]

# Readiness is impossible until each of these carries a COMPLETE receipt.
REQUIRED_FOR_READINESS = [
    DISCOVERED,
    SEMANTIC_FROZEN,
    RUNTIME_PREPARED,
    STATIC_QUALIFIED,
    BASE_REFERENCE_QUALIFIED,
    BOUNDARY_QUALIFIED,
    EXECUTION_FROZEN,
]

ENTERED = "ENTERED"
COMPLETE = "COMPLETE"


def is_before(left: str, right: str) -> bool:
    return ORDER.index(left) < ORDER.index(right)


@dataclass(frozen=True, slots=True)
class StageRecord:
    stage: str
    inputs_sha256: str
    status: str
    outputs: Mapping[str, object]
    receipt_sha256: str | None = None

    @property
    def complete(self) -> bool:
        return self.status == COMPLETE

    def as_json(self) -> dict[str, object]:
        return {
            "schema": "gnostoa-capsule-stage/v1",
            "stage": self.stage,
            "inputs_sha256": self.inputs_sha256,
            "status": self.status,
            "receipt_sha256": self.receipt_sha256,
            "outputs": dict(self.outputs),
        }


@dataclass
class StageLedger:
    """Retained, resumable stage state. State lives in files, never in memory alone."""

    root: Path
    records: dict[str, StageRecord] = field(default_factory=dict)
    reused: list[str] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return self.root / "stages.json"

    def load(self) -> None:
        if not self.path.is_file():
            return
        raw = json.loads(self.path.read_text())
        for stage, payload in raw.get("records", {}).items():
            self.records[stage] = StageRecord(
                stage=stage,
                inputs_sha256=payload["inputs_sha256"],
                status=payload.get("status", ENTERED),
                outputs=payload.get("outputs", {}),
                receipt_sha256=payload.get("receipt_sha256"),
            )

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "gnostoa-capsule-stage-ledger/v1",
            "records": {
                stage: record.as_json() for stage, record in self.records.items()
            },
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def enter(
        self, stage: str, inputs: Mapping[str, object]
    ) -> tuple[StageRecord, bool]:
        """Return the record for `stage`, reusing it only when COMPLETE and unchanged."""
        digest = digest_of(dict(inputs))
        existing = self.records.get(stage)
        if (
            existing is not None
            and existing.inputs_sha256 == digest
            and existing.complete
        ):
            self.reused.append(stage)
            return existing, True
        if existing is not None:
            self.invalidate_from(stage)
        record = StageRecord(
            stage=stage, inputs_sha256=digest, status=ENTERED, outputs={}
        )
        self.records[stage] = record
        return record, False

    def complete(self, stage: str, outputs: Mapping[str, object]) -> StageRecord:
        record = self.records[stage]
        completed = StageRecord(
            stage=stage,
            inputs_sha256=record.inputs_sha256,
            status=COMPLETE,
            outputs=dict(outputs),
            receipt_sha256=digest_of(
                {
                    "stage": stage,
                    "inputs_sha256": record.inputs_sha256,
                    "outputs": dict(outputs),
                }
            ),
        )
        self.records[stage] = completed
        return completed

    def invalidate_from(self, stage: str) -> None:
        """Drop `stage` and every stage after it."""
        index = ORDER.index(stage)
        for later in ORDER[index:]:
            self.records.pop(later, None)
            if later in self.reused:
                self.reused.remove(later)

    def identities(self) -> dict[str, str]:
        return {stage: record.inputs_sha256 for stage, record in self.records.items()}

    def receipts(self) -> dict[str, str]:
        return {
            stage: record.receipt_sha256
            for stage, record in self.records.items()
            if record.complete and record.receipt_sha256 is not None
        }

    def completed(self) -> list[str]:
        return [
            stage
            for stage in ORDER
            if stage in self.records and self.records[stage].complete
        ]

    def missing_for_readiness(self) -> list[str]:
        done = set(self.completed())
        return [stage for stage in REQUIRED_FOR_READINESS if stage not in done]

    def highest(self) -> str:
        done = self.completed()
        return done[-1] if done else DISCOVERED
