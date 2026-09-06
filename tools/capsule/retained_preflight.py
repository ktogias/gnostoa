"""Restore an exact completed BASE/REFERENCE qualification without reopening effects.

The stage ledger proves whether the current qualification-stage inputs are identical to
a completed retained stage. The public state then supplies the typed qualification
receipts needed by the current in-memory task results. Both retained records are
cross-checked before anything is reused.
"""

from __future__ import annotations

import json
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from tools.capsule import stages
from tools.capsule.identity import digest_of
from tools.capsule.qualification import (
    BOUND_IDENTITY_FIELDS,
    RECEIPT_SCHEMA,
    QualificationReceipt,
    ReceiptError,
    SubjectOutcome,
)

STATE_FILENAME = "experiment-state.json"
STATE_SCHEMA = "gnostoa-capsule-state/v1"
INVALID_RETAINED_QUALIFICATION = "retained-qualification-state-invalid"


class RetainedPreflightError(RuntimeError):
    """A completed stage and its public retained state cannot be trusted together."""


def _load_public_state(root: Path) -> dict[str, object]:
    path = root / STATE_FILENAME
    try:
        observed = path.lstat()
    except OSError as exc:
        raise RetainedPreflightError(
            f"retained public state is unavailable: {exc}"
        ) from exc
    if not stat.S_ISREG(observed.st_mode):
        raise RetainedPreflightError("retained public state is not a regular file")
    try:
        decoded = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedPreflightError(
            f"retained public state is unreadable: {exc}"
        ) from exc
    if not isinstance(decoded, dict) or decoded.get("schema") != STATE_SCHEMA:
        raise RetainedPreflightError("retained public state has an unsupported schema")
    return cast(dict[str, object], decoded)


def matching_completed_stage(
    ledger: stages.StageLedger,
    inputs: Mapping[str, object],
) -> stages.StageRecord | None:
    """Return an exact completed qualification stage without mutating the ledger."""
    existing = ledger.records.get(stages.BASE_REFERENCE_QUALIFIED)
    if existing is None or not existing.complete:
        return None
    if existing.inputs_sha256 != digest_of(dict(inputs)):
        return None
    return existing


def matching_completed_candidate_stage(
    root: Path,
    ledger: stages.StageLedger,
    *,
    candidate_sha256: str,
) -> stages.StageRecord | None:
    """Match retained completion by candidate before authority metadata can invalidate it.

    The candidate already binds the backend, ordered task capsules and fresh/reuse
    disposition. A differently named authority for that same candidate must therefore
    be handled as replay against the retained transaction, not as changed qualification
    inputs that first invalidate its evidence.
    """
    existing = ledger.records.get(stages.BASE_REFERENCE_QUALIFIED)
    if existing is None or not existing.complete:
        return None

    payload = _load_public_state(root)
    if payload.get("preflight_candidate_sha256") != candidate_sha256:
        return None

    receipts = payload.get("stage_receipts")
    if not isinstance(receipts, dict):
        raise RetainedPreflightError("retained public state has no stage receipts")
    if receipts.get(stages.BASE_REFERENCE_QUALIFIED) != existing.receipt_sha256:
        raise RetainedPreflightError(
            "retained public state disagrees with the completed qualification receipt"
        )
    return existing


def retained_lock_material_matches(
    root: Path,
    *,
    experiment_id: str,
    question: str,
    claim_boundary: str,
    launch: Mapping[str, object],
    capabilities: Sequence[Mapping[str, object]],
    artifact_store: str,
) -> bool:
    """True when the retained lock still describes today's downstream experiment.

    The preflight candidate covers the qualification transaction only: subjects,
    backend and disposition. ``experiment.lock`` additionally binds downstream
    material -- the question, claim boundary, launch payload, capabilities and
    artifact store -- none of which changes the candidate digest. Preserving a
    completed READY on candidate equality alone would therefore keep presenting an
    old lock as current after that downstream material had drifted.

    Only authority-independent fields are compared. The authority itself, and the
    task and run-plan payloads that depend on qualification outcomes, are excluded:
    the first is exactly what an authority refusal is allowed to differ on, and the
    others are not yet recomputed at the point this decision is taken.

    Read-only. A missing or unreadable lock is not a match, so preservation is never
    granted on the strength of a lock nobody can compare against.
    """
    path = root / "experiment.lock"
    try:
        observed = path.lstat()
    except OSError:
        return False
    if not stat.S_ISREG(observed.st_mode):
        return False
    try:
        retained = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not isinstance(retained, dict):
        return False
    return (
        retained.get("experiment")
        == {
            "id": experiment_id,
            "question": question,
            "claim_boundary": claim_boundary,
        }
        and retained.get("launch") == dict(launch)
        and retained.get("capabilities") == [dict(item) for item in capabilities]
        and retained.get("artifact_store") == artifact_store
    )


def _outcome(payload: object) -> SubjectOutcome:
    if not isinstance(payload, dict):
        raise RetainedPreflightError("retained qualification outcome is not an object")
    data = cast(dict[str, object], payload)
    try:
        return SubjectOutcome(
            subject=str(data["subject"]),
            collected=bool(data["collected"]),
            passed=tuple(
                str(item) for item in cast(Sequence[object], data.get("passed") or [])
            ),
            failed=tuple(
                str(item) for item in cast(Sequence[object], data.get("failed") or [])
            ),
            error_types={
                str(key): str(value)
                for key, value in cast(
                    Mapping[object, object], data.get("error_types") or {}
                ).items()
            },
            classification=str(data["classification"]),
            detail=str(data.get("detail", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RetainedPreflightError(
            f"retained qualification outcome is malformed: {exc}"
        ) from exc


def _receipt(payload: object) -> QualificationReceipt:
    if not isinstance(payload, dict):
        raise RetainedPreflightError("retained qualification receipt is not an object")
    data = cast(dict[str, object], payload)
    if data.get("schema") != RECEIPT_SCHEMA:
        raise RetainedPreflightError(
            f"retained qualification uses unsupported schema {data.get('schema')!r}"
        )
    bound = data.get("bound")
    if not isinstance(bound, dict):
        raise RetainedPreflightError("retained qualification does not bind identities")
    bound_mapping = cast(dict[object, object], bound)
    missing = [name for name in BOUND_IDENTITY_FIELDS if not bound_mapping.get(name)]
    if missing:
        raise RetainedPreflightError(
            f"retained qualification is missing bound identities: {missing}"
        )
    try:
        return QualificationReceipt(
            task=str(data["task"]),
            backend=str(data["backend"]),
            base=_outcome(data["base"]),
            reference=_outcome(data["reference"]),
            bound={str(key): str(value) for key, value in bound_mapping.items()},
        )
    except (KeyError, ReceiptError, TypeError, ValueError) as exc:
        raise RetainedPreflightError(
            f"retained qualification receipt is malformed: {exc}"
        ) from exc


def load_completed_qualifications(
    root: Path,
    *,
    candidate_sha256: str,
    stage_record: stages.StageRecord,
    task_ids: Sequence[str],
) -> dict[str, QualificationReceipt]:
    """Cross-check public state against one exact COMPLETE qualification stage."""
    payload = _load_public_state(root)
    if payload.get("preflight_candidate_sha256") != candidate_sha256:
        raise RetainedPreflightError(
            "retained public state names a different preflight candidate"
        )

    stage = payload.get("stage")
    if not isinstance(stage, str) or stage not in stages.ORDER:
        raise RetainedPreflightError("retained public state has an invalid stage")
    if stages.is_before(stage, stages.BASE_REFERENCE_QUALIFIED):
        raise RetainedPreflightError(
            "retained public state predates the completed qualification stage"
        )

    receipts = payload.get("stage_receipts")
    if not isinstance(receipts, dict):
        raise RetainedPreflightError("retained public state has no stage receipts")
    if receipts.get(stages.BASE_REFERENCE_QUALIFIED) != stage_record.receipt_sha256:
        raise RetainedPreflightError(
            "retained public state disagrees with the completed qualification receipt"
        )

    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        raise RetainedPreflightError("retained public state has no task records")
    outputs = dict(stage_record.outputs)
    if set(outputs) != set(task_ids):
        raise RetainedPreflightError(
            "completed qualification stage does not cover the current task set"
        )

    restored: dict[str, QualificationReceipt] = {}
    for task_id in task_ids:
        raw_task = tasks.get(task_id)
        if not isinstance(raw_task, dict):
            raise RetainedPreflightError(
                f"retained public state has no task record for {task_id!r}"
            )
        receipt = _receipt(raw_task.get("qualification"))
        if receipt.task != task_id:
            raise RetainedPreflightError(
                f"retained qualification names task {receipt.task!r}, not {task_id!r}"
            )
        if receipt.identity != outputs.get(task_id):
            raise RetainedPreflightError(
                f"retained qualification identity for {task_id!r} does not match the stage"
            )
        restored[task_id] = receipt
    return restored
