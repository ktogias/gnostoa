"""Private, effect-free progress owner (Decision 0136).

Extracted from the project's S52 implementation. This module owns reconciliation
choices, not admission, persistence, transport or execution. References and source
identities are opaque; adapters authenticate and normalize observations.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from tools.agent_review_model import Ref

Observation = float | int | str | None


@dataclass(frozen=True)
class Source:
    category: str
    key: str | None
    fingerprint: str
    generation: str | None = None
    replaces_category: bool = False


def scope_identity(scope: Ref, origin: str | None = None) -> str:
    """Keep bound identity independent of attempts and unresolved origins distinct."""
    value: dict[str, str | None] = {"kind": scope.kind, "ref": scope.id or None}
    if not scope.id:
        value["origin"] = origin
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def merge_sources(
    current: Sequence[Source], additions: Sequence[Source]
) -> tuple[tuple[Source, ...], bool]:
    result = list(current)
    added = False
    for source in additions:
        if source.replaces_category:
            if any(
                s.category == source.category and s.generation == source.generation
                for s in result
            ):
                continue
            result = [s for s in result if s.category != source.category]
        if any(
            (source.key and s.key == source.key and s.category == source.category)
            or s.fingerprint == source.fingerprint
            for s in result
        ):
            continue
        result.append(source)
        added = True
    return tuple(result), added


def opening(status: str | None, added: bool) -> tuple[bool, bool]:
    """Return whether a scope returns/starts and whether new evidence rearms it."""
    created = status is None or status in ("MIGRATED", "SUPERSEDED")
    return created, added and not created


def rearm_status(status: str) -> str:
    return "OPEN" if status == "DISCHARGED" else status


@dataclass(frozen=True)
class RequestStamp:
    key: str
    at: float
    carried: bool = False


def migrate_requests(
    previous: Sequence[RequestStamp], current: Sequence[RequestStamp]
) -> tuple[RequestStamp, ...]:
    carried = (RequestStamp(r.key, r.at, True) for r in previous)
    return tuple(sorted((*carried, *current), key=lambda r: r.at))


def request_budget(
    identity: Sequence[RequestStamp],
    all_requests: Sequence[RequestStamp],
    now: float,
    *,
    per_identity: int = 3,
    window_seconds: float = 86400,
    daily_cap: int = 12,
) -> str | None:
    if sum(now - r.at < window_seconds for r in identity) >= per_identity:
        return "IDENTITY_CAP"
    day = datetime.fromtimestamp(now, UTC).date()
    used = sum(
        not r.carried and datetime.fromtimestamp(r.at, UTC).date() == day
        for r in all_requests
    )
    return "DAILY_CAP" if used >= daily_cap else None


@dataclass(frozen=True)
class Transition:
    open: bool = True
    has_request: bool = False
    intent: bool = False
    changed: bool = False
    fate: str = "HOLD"
    reason: str = "OPENED"
    pending_refreshed: bool | None = None
    source_open: bool = False
    return_open: bool = False
    hold: str | None = None


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


def decide_transition(state: Transition) -> Decision:
    if not state.open:
        return Decision("HOLD", "ACCOUNTED")
    if state.intent:
        return Decision("REEMIT", state.reason)
    ask = not state.has_request
    reason = state.reason if state.has_request else "OPENED"
    if state.has_request:
        if state.fate == "DISCHARGE" and not state.changed:
            return Decision("DISCHARGE", reason)
        if state.fate == "REEMIT":
            return Decision("REEMIT", reason)
        if state.changed and reason == "PENDING_INGRESS":
            if state.pending_refreshed is None:
                return Decision("REFRESH_PENDING", reason)
            if state.pending_refreshed:
                return Decision("REFRESHED", reason)
            ask = True
        else:
            ask = (
                state.fate == "RETRY"
                or (state.changed and state.fate == "DISCHARGE")
                or (state.changed and reason in ("TAKEN", "LOST"))
            )
    if not ask:
        return Decision("HOLD", reason)
    if state.source_open:
        return Decision("HOLD", "SOURCE_OWNER_OPEN")
    if state.return_open:
        return Decision("HOLD", "SOURCE_RETURN_OPEN")
    return Decision("HELD", state.hold) if state.hold else Decision("REQUEST", reason)


@dataclass(frozen=True)
class Citation:
    pointer: str
    digest: str
    observed_at: Observation


@dataclass(frozen=True)
class Read:
    pointer: str
    ref: Ref | None
    digest: str
    observed_at: Observation
    current: bool
    complete: bool
    attributes: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Gate:
    key: str
    owner: str
    waiting: bool


@dataclass(frozen=True)
class Evaluation:
    scope: Ref | None
    reads: tuple[Read, ...]
    targets: tuple[Ref | None, ...]
    closed_targets: tuple[Ref, ...]
    frontier_complete: bool
    context_complete: bool
    gates: tuple[Gate, ...] = ()
    lineage: Citation | None = None


@dataclass(frozen=True)
class Result:
    mode: str
    valid_shape: bool = True
    evidence: tuple[Citation, ...] = ()
    assignment_index: int | None = None
    owner: str = ""
    reason: str = ""
    resume_key: str = ""
    need: tuple[str, ...] = ()


class ProgressError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _cited(
    evaluation: Evaluation, result: Result, *, lineage: bool = False
) -> tuple[Read, ...] | None:
    if not result.evidence:
        return None
    result_reads = []
    held = {read.pointer: read for read in evaluation.reads}
    for citation in result.evidence:
        if (
            lineage
            and evaluation.lineage is not None
            and citation.pointer == evaluation.lineage.pointer
            and citation.digest == evaluation.lineage.digest
        ):
            continue
        read = held.get(citation.pointer)
        if (
            read is None
            or not read.current
            or not read.complete
            or read.digest != citation.digest
            or read.observed_at != citation.observed_at
        ):
            return None
        result_reads.append(read)
    return tuple(result_reads)


def validate_result(evaluation: Evaluation, result: Result) -> None:
    """The same captured-evidence contract is used at intake and before egress."""
    scope_read = evaluation.scope is not None and any(
        r.ref == evaluation.scope and r.current and r.complete for r in evaluation.reads
    )
    covered = (
        scope_read and evaluation.frontier_complete and evaluation.context_complete
    )
    if result.mode == "ASSIGNED":
        index = result.assignment_index
        if (
            not result.valid_shape
            or index is None
            or not 0 <= index < len(evaluation.targets)
        ):
            raise ProgressError("assignment_shape")
        target = evaluation.targets[index]
        if target is not None and target in evaluation.closed_targets:
            raise ProgressError("closed_target")
        cited = _cited(evaluation, result, lineage=True)
        if cited is None:
            raise ProgressError("scope_binding")
        if (
            not covered
            or not any(r.ref == evaluation.scope for r in cited)
            or target is None
            or not any(r.ref == target for r in cited)
        ):
            raise ProgressError("scope_binding")
    elif result.mode == "WAITING":
        gate = next((g for g in evaluation.gates if g.key == result.resume_key), None)
        if (
            not result.valid_shape
            or not result.owner.strip()
            or not result.reason.strip()
            or gate is None
            or not gate.waiting
            or gate.owner != result.owner
        ):
            raise ProgressError("waiting")
    elif result.mode == "REFRESH":
        if (
            not result.valid_shape
            or not result.reason.strip()
            or (covered and not result.need)
        ):
            raise ProgressError("refresh")
    elif result.mode == "QUIESCENT":
        cited = _cited(evaluation, result)
        if (
            not result.valid_shape
            or cited is None
            or not covered
            or not any(r.ref == evaluation.scope for r in cited)
        ):
            raise ProgressError("quiescence")
    else:
        raise ProgressError("result_mode")


def source_changes(
    captured: Sequence[Read], fresh: Sequence[Read]
) -> tuple[str, str] | None:
    current = {r.pointer: r for r in fresh}
    for before in captured:
        after = current.get(before.pointer)
        if after is None or not after.current or not after.complete:
            return "SOURCE_PENDING", before.pointer
        attributes = dict(after.attributes)
        if (
            before.digest != after.digest
            or before.ref != after.ref
            or any(attributes.get(k) != v for k, v in before.attributes)
        ):
            return "REPAIR_PENDING", before.pointer
    return None


@dataclass(frozen=True)
class ResumeGate:
    subject: Ref
    revision: str
    mode: str
    at: float
    sequence: int = 0


@dataclass(frozen=True)
class ResumeFact:
    subject: Ref
    revision: str
    material: str
    observed_at: float
    provider_at: float | None
    sequence: int
    mode: str
    advances: bool


def gate_resume(
    gate: ResumeGate, fact: ResumeFact, now: float, seen: Sequence[str] = ()
) -> bool:
    if (
        not fact.material
        or fact.material in seen
        or fact.subject != gate.subject
        or fact.revision != gate.revision
        or fact.mode != gate.mode
        or not gate.at < fact.observed_at <= now
        or not fact.advances
    ):
        return False
    if gate.mode == "decision":
        return fact.provider_at is not None and gate.at < fact.provider_at <= now
    return gate.mode == "source" and fact.sequence > gate.sequence
