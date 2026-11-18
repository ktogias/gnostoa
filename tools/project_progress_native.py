"""Adapt the S52 native journal shapes to the private progress owner.

Raw dictionaries are the documented Any boundary: they belong to the host's
existing schemas, storage and authenticated acquisition. No file access, provider
client, queue, admission evaluator or effect is implemented here. The neutral
core owns validation and transition choices; the host retains their effects.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, TypedDict, Unpack, cast

from tools import project_progress as p
from tools import project_progress_github as provider
from tools.agent_review_model import Ref

Native = dict[str, Any]


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _source_fingerprint(value: Mapping[str, Any]) -> str:
    return _digest({key: item for key, item in value.items() if key != "observed"})


def _iso(now: float) -> str:
    return datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(value: Any) -> float:
    at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if at.tzinfo is None:
        raise ValueError("a provider time must carry its timezone")
    return at.timestamp()


def scope_identity(scope: Mapping[str, Any], origin: str | None = None) -> str:
    return p.scope_identity(
        Ref(str(scope.get("kind")), str(scope.get("ref") or "")), origin
    )


def progress_row(
    scope: Native,
    sources: Iterable[Native],
    chains: Native | None = None,
    *,
    origin: str | None = None,
) -> Native:
    """An unresolved scope is told apart by its origin, as its obligation is."""
    values = list(sources)
    identity: Native = {"kind": scope.get("kind"), "ref": scope.get("ref")}
    if not scope.get("ref") and origin is not None:
        identity["origin"] = origin
    row: Native = {
        "kind": "PROJECT_PROGRESS",
        "source_kind": "controller_progress",
        "scope": copy.deepcopy(scope),
        "sources": copy.deepcopy(values),
        "source_key": "progress:" + _digest(identity),
        "source_sha256": _digest(values),
    }
    if chains:
        row["chains"] = copy.deepcopy(chains)
    row["id"] = _digest(row)
    return row


def _source(value: Native) -> p.Source:
    key = value.get("delivery_key") or value.get("key")
    # A present null generation is an absent one, never the text "None".
    generation = value.get("generation")
    observed = value.get("observed")
    order: p.ObservationOrder = None
    if isinstance(observed, Mapping):
        epoch, sequence = observed.get("epoch"), observed.get("seq")
        if isinstance(epoch, str) and epoch and type(sequence) is int and sequence >= 0:
            order = (epoch, sequence)
    return p.Source(
        str(value.get("kind")),
        str(key) if key else None,
        _source_fingerprint(value),
        str(generation) if generation is not None else None,
        value.get("kind") == "scope",
        order,
    )


def merge_sources(obligation: Native, sources: Iterable[Native]) -> tuple[bool, bool]:
    before = list(obligation["sources"])
    added = list(sources)
    raw: dict[str, list[Native]] = {}
    for value in before + added:
        raw.setdefault(_source_fingerprint(value), []).append(value)
    merged, changed, refresh = p.merge_sources(
        tuple(_source(v) for v in before), tuple(_source(v) for v in added)
    )
    retained = []
    for source in merged:
        candidates = raw[source.fingerprint]
        retained.append(
            next(
                (
                    value
                    for value in candidates
                    if _source(value).observed == source.observed
                ),
                candidates[0],
            )
        )
    obligation["sources"] = retained
    return changed, refresh


def new_obligation(oid: str, scope: Native, now: float) -> Native:
    return {
        "version": 1,
        "id": oid,
        "kind": "PROJECT_PROGRESS",
        "status": "OPEN",
        "scope": scope,
        "sources": [],
        "requests": [],
        "created_at": _iso(now),
    }


def reopen(obligation: Native, now: float, why: str) -> None:
    obligation["rearmed_at"] = _iso(now)
    status = p.rearm_status(str(obligation["status"]))
    if status != obligation["status"]:
        obligation.update(status=status, reopened_at=_iso(now), reopened_by=why)


def _merge_chains(bound: Native, chains: Native) -> None:
    for name, chain in chains.items():
        current = bound.setdefault("chains", {}).setdefault(name, {"waits": []})
        current["waits"] = sorted(
            set(current.get("waits", [])) | set(chain.get("waits", []))
        )


def open_obligation(
    obligations: Native,
    scope: Native,
    sources: Iterable[Native],
    origin: str | None,
    now: float,
    chains: Native | None = None,
) -> tuple[Native, bool, str | None]:
    oid = scope_identity(scope, origin)
    obligation = obligations.get(oid)
    previous = str(obligation["status"]) if obligation is not None else None
    if obligation is None:
        obligation = obligations[oid] = new_obligation(oid, scope, now)
    elif previous == "MIGRATED":
        successor_id = obligation.get("superseded_by")
        successor = (
            obligations.get(str(successor_id)) if successor_id is not None else None
        )
        if successor is None or successor.get("status") == "MIGRATED":
            return obligation, False, "SOURCE_PENDING/REFRESH"
        return _absorb(successor, str(successor["status"]), sources, now, chains)
    return _absorb(obligation, previous, sources, now, chains)


def _absorb(
    obligation: Native,
    previous: str | None,
    sources: Iterable[Native],
    now: float,
    chains: Native | None,
) -> tuple[Native, bool, str | None]:
    added, refresh = merge_sources(obligation, sources)
    created, rearmed = p.opening(previous, added)
    if created and previous is not None:
        obligation.update(
            status="OPEN", reopened_at=_iso(now), reopened_by="SCOPE_RETURNED"
        )
    _merge_chains(obligation, chains or {})
    if rearmed:
        reopen(obligation, now, "NEW_SOURCE")
    return (
        obligation,
        created or added,
        "SOURCE_PENDING/REFRESH" if refresh else None,
    )


def request_stamp(request: Native) -> p.RequestStamp:
    """A request's key and timezone-aware time, or one named refusal.

    The journal record is never rewritten or dropped here: an invalid one holds
    the caller before any intent, so budget history cannot be silently reset.
    """
    try:
        if not isinstance(request, Mapping):
            raise TypeError("a request record must be a mapping")
        key, raw = request["key"], request["at"]
        if not isinstance(key, str) or not key or not isinstance(raw, str):
            raise TypeError("a request key and time must be non-empty text")
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if at.tzinfo is None:
            raise ValueError("a request time must carry its timezone")
        return p.RequestStamp(key, at.timestamp(), bool(request.get("carried_from")))
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise ValueError(
            "PROJECT_PROGRESS a request record needs its key and a timezone-aware ISO time"
        ) from error


def _history(obligation: object) -> tuple[p.RequestStamp, ...]:
    """Every request stamp of one obligation, read-only, or one named refusal."""
    requests = obligation.get("requests") if isinstance(obligation, Mapping) else None
    if not isinstance(requests, list):
        raise ValueError("PROJECT_PROGRESS a request record list is missing or invalid")
    return tuple(request_stamp(r) for r in requests)


def _targets(decoded: Native) -> tuple[Ref | None, ...]:
    if not isinstance(decoded, Mapping):
        raise ValueError("PROJECT_PROGRESS the decoded result must be a mapping")
    assignments = decoded.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("PROJECT_PROGRESS assignments must be a list")
    targets: list[Ref | None] = []
    for assignment in assignments:
        operation = (
            assignment.get("operation") if isinstance(assignment, Mapping) else None
        )
        if not isinstance(operation, Mapping):
            raise ValueError("PROJECT_PROGRESS each assignment needs its operation")
        target = provider.target_ref(operation.get("operation_target"))
        if target is None:
            raise ValueError(
                "PROJECT_PROGRESS each assignment needs a supported operation_target"
            )
        targets.append(target)
    return tuple(targets)


def _carry_requests(bound: Native, unbound: Native) -> None:
    carried = [dict(r, carried_from=unbound["id"]) for r in unbound["requests"]]
    # Native serialization retains every original request field and stable key.
    ordered = p.migrate_requests(
        tuple(request_stamp(r) for r in carried),
        tuple(request_stamp(r) for r in bound["requests"]),
    )
    remaining = [(request_stamp(r), r) for r in carried + bound["requests"]]
    preserved = []
    for stamp in ordered:
        index = next(
            (i for i, (candidate, _) in enumerate(remaining) if candidate == stamp),
            None,
        )
        if index is None:
            raise ValueError(
                "PROJECT_PROGRESS migration ordered a request it was not given"
            )
        _, raw = remaining.pop(index)
        preserved.append(raw)
    bound["requests"] = preserved
    bound.setdefault("migrated_from", []).append(unbound["id"])


def migrate(obligations: Native, unbound: Native, scope: Native, now: float) -> Native:
    oid = scope_identity(scope)
    # Validate every carried and bound request before the first mutation.
    _history(unbound)
    if obligations.get(oid):
        _history(obligations[oid])
    bound = obligations.get(oid) or new_obligation(oid, scope, now)
    obligations[oid] = bound
    binding = {
        "kind": "scope_binding",
        "key": "binding-resolved:" + unbound["id"],
        "from": unbound["id"],
        "scope_ref": scope.get("ref"),
    }
    carried_before = unbound["id"] in bound.get("migrated_from", [])
    if carried_before and binding in bound["sources"]:
        # The bound record survived a crash before the old tombstone. Its input
        # and complete request history are already durable; finish only the tombstone.
        unbound.update(status="MIGRATED", superseded_by=oid, migrated_at=_iso(now))
        return bound
    added, _ = merge_sources(bound, unbound["sources"])
    created, rearmed = p.opening(str(bound["status"]), added)
    if created:
        bound["status"] = "OPEN"
    _merge_chains(bound, unbound.get("chains") or {})
    if not carried_before:
        _carry_requests(bound, unbound)
    if unbound["status"] == "OPEN":
        merge_sources(bound, [binding])
        reopen(bound, now, "BINDING_RESOLVED")
    elif rearmed:
        reopen(bound, now, "NEW_SOURCE")
    else:
        bound["rearmed_at"] = _iso(now)
    unbound.update(status="MIGRATED", superseded_by=oid, migrated_at=_iso(now))
    return bound


class BudgetLimits(TypedDict, total=False):
    """The request budget's keyword limits, as `request_budget` names them."""

    per_identity: int
    window_seconds: float
    daily_cap: int


def request_budget(
    obligations: Native,
    obligation: Native,
    now: float,
    *,
    per_identity: int = 3,
    window_seconds: float = 86400,
    daily_cap: int = 12,
) -> str | None:
    identity = _history(obligation)
    everyone = tuple(s for o in obligations.values() for s in _history(o))
    return p.request_budget(
        identity,
        everyone,
        now,
        per_identity=per_identity,
        window_seconds=window_seconds,
        daily_cap=daily_cap,
    )


def controller_decision(
    obligation: Native,
    *,
    fate: str | None,
    reason: str,
    touched: bool,
    linked_open: bool,
    source_router_open: bool,
    now: float,
    obligations: Native,
    current_input: str | None,
    last_input: str | None,
    pending_refreshed: bool | None = None,
    **limits: Unpack[BudgetLimits],
) -> tuple[str, str]:
    raw = obligation.get("requests")
    requests = raw if isinstance(raw, list) else []
    last = requests[-1] if requests else None
    decision = p.decide_transition(
        p.Transition(
            open=obligation["status"] == "OPEN",
            has_request=bool(requests),
            intent=isinstance(last, Mapping) and last.get("state") == "INTENT",
            changed=touched or (bool(requests) and current_input != last_input),
            fate=fate or "HOLD",
            reason=reason,
            pending_refreshed=pending_refreshed,
            source_open=source_router_open,
            return_open=linked_open,
            hold=request_budget(obligations, obligation, now, **limits),
        )
    )
    reason_map = {
        "SOURCE_OWNER_OPEN": "SOURCE_ROUTER_OPEN",
        "SOURCE_RETURN_OPEN": "NATIVE_RETURN_OPEN",
    }
    return decision.action, reason_map.get(decision.reason, decision.reason)


_GATE = "gate:"
_GATE_KINDS = ("HUMAN_MERGE", "TECHNICAL", "UNFINISHED", "SOURCE_RECOVERY")


def _text(value: object) -> str:
    return str(value or "")


# The one shape table for nested native fields read before a core call: the
# expected type of each and its empty value when the field is absent or falsy.
_BOUNDARY_SHAPES: dict[str, tuple[type, Callable[[], Any]]] = {
    "continuation_contract": (Mapping, dict),
    "scope": (Mapping, dict),
    "sources": (list, list),
}


def _boundary(owner: Native, field: str) -> Any:
    """A native field in its table shape; a truthy wrong shape is one named refusal."""
    expected, empty = _BOUNDARY_SHAPES[field]
    value = owner.get(field)
    if not value:
        return empty()
    if not isinstance(value, expected):
        raise ValueError(
            f"PROJECT_PROGRESS the native {field} must be a {expected.__name__.lower()}"
        )
    return value


def _frontier_rows(frontier: object) -> list[Native]:
    """The captured frontier's rows, or one named refusal: never an empty frontier."""
    rows = frontier.get("rows") if isinstance(frontier, Mapping) else None
    if (
        not isinstance(rows, list)
        or not rows
        or not all(
            isinstance(item, Mapping)
            and _non_empty_str(item.get("id"))
            and _non_empty_str(item.get("kind"))
            for item in rows
        )
    ):
        raise ValueError(
            "PROJECT_PROGRESS the captured frontier must be a mapping with a non-empty "
            "list of rows, each a mapping with its id and kind"
        )
    return rows


def _gates(rows: list[Native], row: Native, claims: list[Native]) -> tuple[p.Gate, ...]:
    gates = []
    for gate in rows:
        claim = next(
            (c for c in claims if isinstance(c, dict) and c.get("id") == gate["id"]), {}
        )
        if gate is not row and gate.get("kind") in _GATE_KINDS:
            gates.append(
                p.Gate(
                    _GATE + gate["id"],
                    _text(claim.get("owner")),
                    claim.get("disposition") == "WAITING",
                )
            )
    return tuple(gates)


def _evaluation(
    job: Native, frontier: Native, row: Native, decoded: Native, claims: list[Native]
) -> p.Evaluation:
    raw_context = job.get("authority_context")
    context: Native = raw_context if isinstance(raw_context, dict) else {}
    reads = tuple(
        provider.read_source(source, held)
        for source, held in context.items()
        if not source.startswith("_") and isinstance(held, dict)
    )
    gates = _gates(_frontier_rows(frontier), row, claims)
    contract = _boundary(job, "continuation_contract")
    return p.Evaluation(
        provider.scope_ref(_boundary(row, "scope")),
        reads,
        _targets(decoded),
        provider.closed_targets(_boundary(row, "sources"))
        + provider.closed_reads(context),
        frontier.get("coverage") == "COMPLETE",
        isinstance(job.get("authority_context"), dict)
        and isinstance(context.get("_coverage"), dict)
        and context["_coverage"].get("coverage") == "COMPLETE"
        and all(
            isinstance(held, dict)
            for source, held in context.items()
            if not source.startswith("_")
        ),
        gates,
        p.Citation(
            "frontier:" + row["id"],
            str(contract.get("frontier_sha256") or ""),
            None,
        ),
    )


_WAITING_BASE = frozenset({"id", "disposition", "owner", "reason", "resume_event"})


def _non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _progress_pointer(claim: Native, row: Native) -> bool:
    """A PROJECT_PROGRESS row waiting on a `gate:<row id>` pointer of its own."""
    resume = claim.get("resume_event")
    return (
        row.get("kind") == "PROJECT_PROGRESS"
        and claim.get("id") == row.get("id")
        and isinstance(resume, str)
        and resume.startswith(_GATE)
        and bool(resume[len(_GATE) :])
    )


def _progress_wait(claim: Native, row: Native) -> bool:
    return set(claim) == _WAITING_BASE and _progress_pointer(claim, row)


def _waiting_shape(claim: Native, progress_wait: bool) -> bool:
    keys = set(claim)
    evidence = _non_empty_str(claim.get("evidence_sha256"))
    plain = keys == _WAITING_BASE | {"evidence_sha256"} and evidence
    dependency = (
        keys
        == _WAITING_BASE
        | {"evidence_sha256", "dependency_pr_number", "dependency_head_sha"}
        and evidence
        and _positive_int(claim.get("dependency_pr_number"))
        and isinstance(claim.get("dependency_head_sha"), str)
    )
    check = (
        keys == _WAITING_BASE | {"evidence_sha256", "check_run_id"}
        and evidence
        and _positive_int(claim.get("check_run_id"))
    )
    return (
        (
            progress_wait
            or (_non_empty_str(claim.get("id")) and (plain or dependency or check))
        )
        and isinstance(claim.get("owner"), str)
        and isinstance(claim.get("reason"), str)
    )


def _assigned_shape(claim: Native, evidence_valid: bool) -> bool:
    return (
        set(claim) == {"id", "disposition", "assignment_index", "evidence"}
        and type(claim.get("assignment_index")) is int
        and evidence_valid
    )


def _refresh_shape(claim: Native) -> bool:
    need = claim.get("need", [])
    return (
        set(claim) - {"need"} == {"id", "disposition", "reason"}
        and isinstance(claim.get("reason"), str)
        and isinstance(need, list)
        and len(need) <= 4
        and all(type(n) is int and n > 0 for n in need)
    )


def _quiescent_shape(claim: Native, evidence_valid: bool) -> bool:
    return set(claim) == {"id", "disposition", "evidence"} and evidence_valid


def _resume_key(claim: Native, mode: str, progress_wait: bool) -> str:
    if mode == "WAITING" and not progress_wait:
        return _GATE + _text(claim.get("id"))
    return _text(claim.get("resume_event"))


def _result(claim: Native, row: Native) -> p.Result:
    mode = _text(claim.get("disposition"))
    row_id = _text(row.get("id"))
    identity_valid = bool(row_id) and claim.get("id") == row_id
    evidence, evidence_valid = provider.citations(claim.get("evidence"))
    index = claim.get("assignment_index")
    need = claim.get("need", [])
    progress_wait = identity_valid and _progress_wait(claim, row)
    shapes = {
        "ASSIGNED": identity_valid and _assigned_shape(claim, evidence_valid),
        "WAITING": _waiting_shape(claim, progress_wait),
        "REFRESH": identity_valid and _refresh_shape(claim),
        "QUIESCENT": identity_valid and _quiescent_shape(claim, evidence_valid),
    }
    return p.Result(
        mode,
        shapes.get(mode, False),
        evidence,
        index if type(index) is int else None,
        _text(claim.get("owner")),
        _text(claim.get("reason")),
        _resume_key(claim, mode, progress_wait),
        tuple(str(n) for n in need) if isinstance(need, list) else (),
    )


_ERRORS = {
    "assignment_shape": "assignment needs assignment_index and evidence",
    "closed_target": "never dispatches a closed PR; it is source evidence only",
    "scope_binding": "assignment must bind its scope (its CURRENT complete Work Item read) and the operation's own captured CURRENT target read",
    "waiting": "wait needs a supported exact gate binding captured by this frontier and owned by the named owner",
    "refresh": "refresh is lawful while the scope's own read is not CURRENT or COMPLETE, or naming (need: up to 4 Work Item numbers) the reads it still needs",
    "quiescence": "quiescence needs its own Work Item's CURRENT read, under COMPLETE coverage; other fresh evidence proves no-work for nothing",
    "result_mode": "needs one typed result (ASSIGNED, WAITING, REFRESH or QUIESCENT); prose or another state cannot resolve it",
}


def validate_progress(
    job: Native,
    frontier: Native,
    row: Native,
    claim: Native,
    decoded: Native,
    claims: list[Native],
) -> None:
    try:
        if claim.get("disposition") in ("ASSIGNED", "QUIESCENT") and not any(
            item == row for item in _frontier_rows(frontier)
        ):
            raise ValueError(
                "PROJECT_PROGRESS the captured frontier does not hold this row"
            )
        p.validate_result(
            _evaluation(job, frontier, row, decoded, claims),
            _result(claim, row),
        )
        if claim.get("disposition") == "WAITING":
            binding_id = (
                _text(claim.get("resume_event"))[len(_GATE) :]
                if _progress_pointer(claim, row)
                else _text(claim.get("id"))
            )
            binding_rows = [
                item
                for item in _frontier_rows(frontier)
                if item.get("id") == binding_id
            ]
            binding_claims = [
                item
                for item in claims
                if isinstance(item, dict) and item.get("id") == binding_id
            ]
            if (
                len(binding_rows) != 1
                or len(binding_claims) != 1
                or gate_binding(job, binding_rows[0], binding_claims[0]) is None
            ):
                raise ValueError("PROJECT_PROGRESS " + _ERRORS["waiting"])
    except p.ProgressError as error:
        # A code without a message still names itself and keeps the kind prefix.
        message = _ERRORS.get(error.code, error.code)
        raise ValueError("PROJECT_PROGRESS " + message) from error


_INCOMPLETE = "captured source is missing or incomplete: "


def source_changes(
    held: Native, fresh: Native, pointers: Iterable[str]
) -> tuple[str, str] | None:
    sources = tuple(pointers)
    for pointer in sources:
        if pointer not in held:
            return "SOURCE_PENDING", _INCOMPLETE + pointer
        if not isinstance(held[pointer], Mapping) or (
            pointer in fresh and not isinstance(fresh[pointer], Mapping)
        ):
            return "SOURCE_PENDING", _INCOMPLETE + pointer
    result = p.source_changes(
        tuple(provider.read_source(k, held[k]) for k in sources),
        tuple(provider.read_source(k, fresh[k]) for k in sources if k in fresh),
    )
    if result is None:
        return None
    status, pointer = result
    detail = "captured source changed: " if status == "REPAIR_PENDING" else _INCOMPLETE
    return status, detail + pointer


def _mapping(value: object) -> Native:
    """A mapping value, else an empty one: a malformed shape binds nothing."""
    return cast("Native", value) if isinstance(value, Mapping) else {}


def _held_gate_sources(job: Native, key: str) -> list[Native] | None:
    """The job's held frontier entries under one key, or None for a damaged table.

    An absent table holds nothing. A table that is not a list, or that holds any
    non-mapping entry, is damaged authority: it never filters down to an owner.
    """
    items = _mapping(job.get("continuation_frontier")).get(key)
    if items is None:
        return []
    if not isinstance(items, list) or not all(isinstance(i, Mapping) for i in items):
        return None
    return cast("list[Native]", items)


def _owner_review_gate(
    job: Native, row: Native, claim: Native, at: Native
) -> tuple[Native, Native] | None:
    canonical = _mapping(row.get("canonical"))
    if (
        row.get("kind") == "HUMAN_MERGE"
        and row.get("source_kind") == "canonical_criterion"
        and canonical.get("criterion") == "M16"
        and claim.get("evidence_sha256") == row.get("source_sha256")
    ):
        return at, canonical
    if row.get("kind") not in ("TECHNICAL", "UNFINISHED"):
        return None
    dependency = {
        "pr_number": claim.get("dependency_pr_number"),
        "head_sha": claim.get("dependency_head_sha"),
    }
    held_waits = _held_gate_sources(job, "dependency_waits")
    if held_waits is None:
        return None
    waits = [
        wait
        for wait in held_waits
        if wait.get("subject") == at
        and wait.get("dependency") == dependency
        and wait.get("evidence_sha256") == claim.get("evidence_sha256")
        and wait.get("evidence_sha256") == row.get("source_sha256")
    ]
    if len(waits) != 1:
        return None
    return dependency, {
        key: waits[0][key]
        for key in ("check_run_id", "protected_revision")
        if key in waits[0]
    }


def _check_run_row(candidate: Native, claim: Native, at: Native) -> bool:
    """A technical canonical criterion row carrying the claim's digest and check run."""
    return (
        candidate.get("source_kind") == "canonical_criterion"
        and candidate.get("kind") == "TECHNICAL"
        and candidate.get("subject") == at
        and candidate.get("source_sha256") == claim.get("evidence_sha256")
        and _same_check_run(
            _mapping(candidate.get("canonical")).get("check_run_id"),
            claim.get("check_run_id"),
        )
    )


def _same_check_run(held: object, claimed: object) -> bool:
    """Equal check-run ids only when both are real ints (`True` and `1.0` are not `1`)."""
    return type(held) is int and type(claimed) is int and held == claimed


def _provider_gate(
    job: Native, row: Native, claim: Native, at: Native
) -> tuple[Native, Native] | None:
    """Bind the one held check-run row, or a native row a held provider wait owns."""
    if type(claim.get("check_run_id")) is not int:
        return None
    rows = _held_gate_sources(job, "rows")
    if rows is None:
        return None
    held = [candidate for candidate in rows if _check_run_row(candidate, claim, at)]
    if len(held) != 1:
        return None
    gate = held[0]
    if not _is_gate_row(row, gate) and not _native_wait_owns(job, row, gate, claim, at):
        return None
    return at, _mapping(gate.get("canonical"))


_GATE_ROW_FIELDS = (
    "id",
    "kind",
    "source_kind",
    "source_key",
    "source_sha256",
    "subject",
    "canonical",
)


def _is_gate_row(row: Native, gate: Native) -> bool:
    """The frontier row is the held gate itself: every identity and canonical field.

    A missing field must be missing on both sides, so a row cannot borrow the held
    canonical record while differing in source kind, source key or canonical content.
    """
    return all(
        (field in row) == (field in gate) and row.get(field) == gate.get(field)
        for field in _GATE_ROW_FIELDS
    )


def _native_wait_owns(
    job: Native, row: Native, gate: Native, claim: Native, at: Native
) -> bool:
    """An unfinished native row is owned by exactly one held provider wait on the gate."""
    if row.get("kind") != "UNFINISHED" or row.get("source_kind") != "native_outcome":
        return False
    key, digest = row.get("source_key"), row.get("source_sha256")
    if not (isinstance(key, str) and key and isinstance(digest, str) and digest):
        return False
    held_waits = _held_gate_sources(job, "provider_waits")
    if held_waits is None:
        return False
    waits = [
        wait
        for wait in held_waits
        if wait.get("subject") == at
        and wait.get("source_key") == key
        and wait.get("source_sha256") == digest
        and isinstance(wait.get("obligation_ids"), list)
        and gate.get("id") in wait["obligation_ids"]
        and _same_check_run(
            wait.get("observed_check_run_id"), claim.get("check_run_id")
        )
    ]
    return len(waits) == 1


def gate_binding(job: Native, row: Native, claim: Native) -> Native | None:
    """Translate only a supported, already-validated native gate; never approve it."""
    at = _mapping(row.get("subject"))
    if (
        claim.get("disposition") != "WAITING"
        or claim.get("id") != row.get("id")
        or not provider.valid_subject(at)
    ):
        return None
    selector, owner = claim.get("resume_event"), claim.get("owner")
    resolved: tuple[Native, Native] | None
    if selector == "native_exact_head_review" and owner == "human:ktogias":
        resolved = _owner_review_gate(job, row, claim, at)
    elif selector == "provider_source_changed" and owner == "provider:canonical-gate":
        resolved = _provider_gate(job, row, claim, at)
    else:
        return None
    if resolved is None:
        return None
    resume, canonical = resolved
    if not provider.valid_subject(resume):
        return None
    return {
        "row": row["id"],
        "kind": row.get("kind"),
        "pr_number": at["pr_number"],
        "head_sha": at["head_sha"],
        "owner": owner,
        "resume_event": selector,
        "resume_subject": copy.deepcopy(resume),
        "source_key": row.get("source_key"),
        "source_sha256": row.get("source_sha256"),
        "canonical": copy.deepcopy(canonical),
        "claim": copy.deepcopy(claim),
    }


def _provider_at(item: Native, review: bool) -> float | None:
    """A review counts from its submission; a later edit never moves that time."""
    field = "submitted_at" if review else "updated_at"
    if field not in item:
        return None
    try:
        return _ts(item[field])
    except (ValueError, TypeError, OverflowError):
        return None


def _resume_selector(
    gate: Native, record: Native, item: Native, *, changed: bool, owner_review: bool
) -> tuple[str, str, bool] | None:
    """The supported selector's mode and reason, and whether this record advances it."""
    head = gate["resume_subject"]["head_sha"]
    selector = gate.get("resume_event")
    if selector == "native_exact_head_review":
        return (
            "decision",
            "OWNER_REVIEW",
            owner_review
            and record.get("kind") == "review"
            and item.get("commit_id") == head,
        )
    if selector == "provider_source_changed":
        return (
            "source",
            "MERGE_ADMISSION_CHANGE",
            changed
            and record.get("kind") == "check_verdict"
            and item.get("head_sha") == head,
        )
    return None


def _resume_gate(gate: Native, mode: str) -> p.ResumeGate:
    resume = gate["resume_subject"]
    baseline = _mapping(gate.get("canonical")).get("check_run_id")
    return p.ResumeGate(
        provider.subject_ref(resume),
        str(resume["head_sha"]),
        mode,
        float(gate["at"]),
        baseline if type(baseline) is int else 0,
    )


def gate_resume(
    gate: Native,
    record: Native,
    fact: Native,
    now: float,
    *,
    seen: Iterable[str] = (),
    changed: bool = False,
    owner_review: bool = False,
) -> str | None:
    """Use authenticated archive facts and the existing classifier's outcome.

    Archive identity/authenticity and latest-verdict ordering remain with that
    existing observer. Exact subject, time, sequence and consumed-material checks
    are the neutral owner's common resume decision.
    """
    resume = _mapping(gate.get("resume_subject"))
    observed = record.get("observed_at")
    payload = record.get("payload")
    if (
        not provider.valid_subject(resume)
        or type(observed) not in (int, float)
        or type(gate.get("at")) not in (int, float)
        or (payload and not isinstance(payload, Mapping))
        or (gate.get("canonical") and not isinstance(gate["canonical"], Mapping))
    ):
        return None
    item = _mapping(_mapping(payload).get("item"))
    selected = _resume_selector(
        gate, record, item, changed=changed, owner_review=owner_review
    )
    if selected is None:
        return None
    mode, reason, advances = selected
    sequence = fact.get("provider_id")
    if mode == "source" and type(sequence) is not int:
        return None
    normalized_fact = p.ResumeFact(
        Ref("pr", str(record.get("number"))),
        _text(fact.get("head")),
        _text(record.get("material_id")),
        float(cast(float, observed)),
        _provider_at(item, record.get("kind") == "review"),
        sequence if type(sequence) is int else 0,
        mode,
        advances,
    )
    resumes = p.gate_resume(_resume_gate(gate, mode), normalized_fact, now, tuple(seen))
    return reason if resumes else None
