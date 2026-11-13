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
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any, cast

from tools import project_progress as p
from tools import project_progress_github as provider
from tools.agent_review_model import Ref

Native = dict[str, Any]


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _iso(now: float) -> str:
    return datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(value: Any) -> float:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()


def scope_identity(scope: Mapping[str, Any], origin: str | None = None) -> str:
    return p.scope_identity(
        Ref(str(scope.get("kind")), str(scope.get("ref") or "")), origin
    )


def progress_row(
    scope: Native, sources: Iterable[Native], chains: Native | None = None
) -> Native:
    values = list(sources)
    row: Native = {
        "kind": "PROJECT_PROGRESS",
        "source_kind": "controller_progress",
        "scope": copy.deepcopy(scope),
        "sources": copy.deepcopy(values),
        "source_key": "progress:"
        + _digest({"kind": scope.get("kind"), "ref": scope.get("ref")}),
        "source_sha256": _digest(values),
    }
    if chains:
        row["chains"] = copy.deepcopy(chains)
    row["id"] = _digest(row)
    return row


def _source(value: Native) -> p.Source:
    key = value.get("delivery_key") or value.get("key")
    return p.Source(
        str(value.get("kind")),
        str(key) if key else None,
        _digest(value),
        str(value.get("generation")) if "generation" in value else None,
        value.get("kind") == "scope",
    )


def merge_sources(obligation: Native, sources: Iterable[Native]) -> bool:
    before = list(obligation["sources"])
    added = list(sources)
    raw = {_digest(v): v for v in before + added}
    merged, changed = p.merge_sources(
        tuple(_source(v) for v in before), tuple(_source(v) for v in added)
    )
    obligation["sources"] = [raw[s.fingerprint] for s in merged]
    return changed


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
) -> tuple[Native, bool]:
    oid = scope_identity(scope, origin)
    obligation = obligations.get(oid)
    previous = str(obligation["status"]) if obligation is not None else None
    if obligation is None:
        obligation = obligations[oid] = new_obligation(oid, scope, now)
    added = merge_sources(obligation, sources)
    created, rearmed = p.opening(previous, added)
    if created and previous is not None:
        obligation.update(
            status="OPEN", reopened_at=_iso(now), reopened_by="SCOPE_RETURNED"
        )
    _merge_chains(obligation, chains or {})
    if rearmed:
        reopen(obligation, now, "NEW_SOURCE")
    return obligation, created or added


def _stamp(request: Native) -> p.RequestStamp:
    return p.RequestStamp(
        str(request["key"]), _ts(request["at"]), bool(request.get("carried_from"))
    )


def migrate(obligations: Native, unbound: Native, scope: Native, now: float) -> Native:
    oid = scope_identity(scope)
    bound = obligations.get(oid) or new_obligation(oid, scope, now)
    obligations[oid] = bound
    created, _ = p.opening(str(bound["status"]), False)
    if created:
        bound["status"] = "OPEN"
    merge_sources(bound, unbound["sources"])
    _merge_chains(bound, unbound.get("chains") or {})
    carried = [dict(r, carried_from=unbound["id"]) for r in unbound["requests"]]
    # Native serialization retains every original request field and stable key.
    ordered = p.migrate_requests(
        tuple(_stamp(r) for r in carried), tuple(_stamp(r) for r in bound["requests"])
    )
    remaining = [(_stamp(r), r) for r in carried + bound["requests"]]
    preserved = []
    for stamp in ordered:
        index = next(
            i for i, (candidate, _) in enumerate(remaining) if candidate == stamp
        )
        _, raw = remaining.pop(index)
        preserved.append(raw)
    bound["requests"] = preserved
    bound.setdefault("migrated_from", []).append(unbound["id"])
    bound["rearmed_at"] = _iso(now)
    unbound.update(status="MIGRATED", superseded_by=oid, migrated_at=_iso(now))
    return bound


def request_budget(
    obligations: Native,
    obligation: Native,
    now: float,
    *,
    per_identity: int = 3,
    window_seconds: float = 86400,
    daily_cap: int = 12,
) -> str | None:
    return p.request_budget(
        tuple(_stamp(r) for r in obligation["requests"]),
        tuple(_stamp(r) for o in obligations.values() for r in o["requests"]),
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
    per_identity: int = 3,
    window_seconds: float = 86400,
    daily_cap: int = 12,
    pending_refreshed: bool | None = None,
) -> tuple[str, str]:
    requests = obligation["requests"]
    decision = p.decide_transition(
        p.Transition(
            open=obligation["status"] == "OPEN",
            has_request=bool(requests),
            intent=bool(requests and requests[-1].get("state") == "INTENT"),
            changed=touched or (bool(requests) and current_input != last_input),
            fate=fate or "HOLD",
            reason=reason,
            pending_refreshed=pending_refreshed,
            source_open=source_router_open,
            return_open=linked_open,
            hold=request_budget(
                obligations,
                obligation,
                now,
                per_identity=per_identity,
                window_seconds=window_seconds,
                daily_cap=daily_cap,
            ),
        )
    )
    reason_map = {
        "SOURCE_OWNER_OPEN": "SOURCE_ROUTER_OPEN",
        "SOURCE_RETURN_OPEN": "NATIVE_RETURN_OPEN",
    }
    return decision.action, reason_map.get(decision.reason, decision.reason)


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
    gates = []
    for gate in frontier["rows"]:
        claim = next(
            (c for c in claims if isinstance(c, dict) and c.get("id") == gate["id"]), {}
        )
        if gate is not row and gate.get("kind") in (
            "HUMAN_MERGE",
            "TECHNICAL",
            "UNFINISHED",
            "SOURCE_RECOVERY",
        ):
            gates.append(
                p.Gate(
                    "gate:" + gate["id"],
                    str(claim.get("owner") or ""),
                    claim.get("disposition") == "WAITING",
                )
            )
    return p.Evaluation(
        provider.scope_ref(row.get("scope") or {}),
        reads,
        tuple(
            provider.target_ref(a["operation"].get("operation_target"))
            for a in decoded["assignments"]
        ),
        provider.closed_targets(row.get("sources") or []),
        frontier.get("coverage") == "COMPLETE",
        isinstance(job.get("authority_context"), dict)
        and (context.get("_coverage") or {}).get("coverage", "COMPLETE") == "COMPLETE",
        tuple(gates),
        p.Citation(
            "frontier:" + row["id"],
            str((job.get("continuation_contract") or {}).get("frontier_sha256") or ""),
            None,
        ),
    )


def _result(claim: Native) -> p.Result:
    mode = str(claim.get("disposition") or "")
    evidence, evidence_valid = provider.citations(claim.get("evidence"))
    index = claim.get("assignment_index")
    need = claim.get("need", [])
    shapes = {
        "ASSIGNED": set(claim) == {"id", "disposition", "assignment_index", "evidence"}
        and type(index) is int
        and evidence_valid,
        "WAITING": set(claim)
        == {"id", "disposition", "owner", "reason", "resume_event"}
        and isinstance(claim.get("owner"), str)
        and isinstance(claim.get("reason"), str),
        "REFRESH": set(claim) - {"need"} == {"id", "disposition", "reason"}
        and isinstance(claim.get("reason"), str)
        and isinstance(need, list)
        and len(need) <= 4
        and all(type(n) is int and n > 0 for n in need),
        "QUIESCENT": set(claim) == {"id", "disposition", "evidence"} and evidence_valid,
    }
    return p.Result(
        mode,
        shapes.get(mode, False),
        evidence,
        index if type(index) is int else None,
        str(claim.get("owner") or ""),
        str(claim.get("reason") or ""),
        str(claim.get("resume_event") or ""),
        tuple(str(n) for n in need) if isinstance(need, list) else (),
    )


_ERRORS = {
    "assignment_shape": "assignment needs assignment_index and evidence",
    "closed_target": "never dispatches a closed PR; it is source evidence only",
    "scope_binding": "assignment must bind its scope (its CURRENT complete Work Item read) and the operation's own captured CURRENT target read",
    "waiting": "wait needs an owner, a reason and resume_event gate:<id> of a real gate this frontier captured, whose own typed wait names the same owner",
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
        p.validate_result(
            _evaluation(job, frontier, row, decoded, claims), _result(claim)
        )
    except p.ProgressError as error:
        raise ValueError("PROJECT_PROGRESS " + _ERRORS[error.code]) from error


def source_changes(
    held: Native, fresh: Native, pointers: Iterable[str]
) -> tuple[str, str] | None:
    sources = tuple(pointers)
    result = p.source_changes(
        tuple(provider.read_source(k, held[k]) for k in sources),
        tuple(provider.read_source(k, fresh[k]) for k in sources if k in fresh),
    )
    if result is None:
        return None
    status, pointer = result
    detail = (
        "captured source changed: "
        if status == "REPAIR_PENDING"
        else "captured source is missing or incomplete: "
    )
    return status, detail + pointer


def gate_binding(job: Native, row: Native, claim: Native) -> Native | None:
    """Translate only a supported, already-validated native gate; never approve it."""
    at = row.get("subject") or {}
    if (
        claim.get("disposition") != "WAITING"
        or claim.get("id") != row.get("id")
        or not provider.valid_subject(at)
    ):
        return None
    selector, owner = claim.get("resume_event"), claim.get("owner")
    resume = at
    canonical = row.get("canonical") or {}
    if selector == "native_exact_head_review" and owner == "human:ktogias":
        if (
            row.get("kind") == "HUMAN_MERGE"
            and row.get("source_kind") == "canonical_criterion"
            and canonical.get("criterion") == "M16"
            and claim.get("evidence_sha256") == row.get("source_sha256")
        ):
            pass
        elif row.get("kind") in ("TECHNICAL", "UNFINISHED"):
            dependency = {
                "pr_number": claim.get("dependency_pr_number"),
                "head_sha": claim.get("dependency_head_sha"),
            }
            waits = [
                wait
                for wait in (job.get("continuation_frontier") or {}).get(
                    "dependency_waits", []
                )
                if wait.get("subject") == at
                and wait.get("dependency") == dependency
                and wait.get("evidence_sha256") == claim.get("evidence_sha256")
            ]
            if len(waits) != 1:
                return None
            resume = dependency
            canonical = {
                key: waits[0][key]
                for key in ("check_run_id", "protected_revision")
                if key in waits[0]
            }
        else:
            return None
    elif selector == "provider_source_changed" and owner == "provider:canonical-gate":
        candidates = [
            r
            for r in (job.get("continuation_frontier") or {}).get("rows", [])
            if r.get("source_kind") == "canonical_criterion"
            and r.get("kind") == "TECHNICAL"
            and r.get("subject") == at
            and r.get("source_sha256") == claim.get("evidence_sha256")
            and type(claim.get("check_run_id")) is int
            and (r.get("canonical") or {}).get("check_run_id") == claim["check_run_id"]
        ]
        if not candidates:
            return None
        canonical = candidates[0]["canonical"]
    else:
        return None
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


def _provider_at(item: Native) -> float | None:
    fields = (
        ("updated_at", "submitted_at") if "submitted_at" in item else ("updated_at",)
    )
    stamps = []
    try:
        for field in fields:
            if field in item:
                stamps.append(_ts(item[field]))
    except (ValueError, TypeError, OverflowError):
        return None
    return max(stamps) if stamps else None


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
    resume = gate.get("resume_subject") or {}
    observed = record.get("observed_at")
    if not provider.valid_subject(resume) or type(observed) not in (int, float):
        return None
    item = (record.get("payload") or {}).get("item") or {}
    selector = gate.get("resume_event")
    if selector == "native_exact_head_review":
        mode, reason = "decision", "OWNER_REVIEW"
        advances = (
            owner_review
            and record.get("kind") == "review"
            and item.get("commit_id") == resume["head_sha"]
        )
    elif selector == "provider_source_changed":
        mode, reason = "source", "MERGE_ADMISSION_CHANGE"
        advances = (
            changed
            and record.get("kind") == "check_verdict"
            and item.get("head_sha") == resume["head_sha"]
        )
    else:
        return None
    sequence = fact.get("provider_id")
    if mode == "source" and type(sequence) is not int:
        return None
    baseline = (gate.get("canonical") or {}).get("check_run_id")
    subject = Ref("pr", str(record.get("number")))
    normalized_gate = p.ResumeGate(
        provider.subject_ref(resume),
        str(resume["head_sha"]),
        mode,
        float(gate["at"]),
        baseline if type(baseline) is int else 0,
    )
    normalized_fact = p.ResumeFact(
        subject,
        str(fact.get("head") or ""),
        str(record.get("material_id") or ""),
        float(cast(float, observed)),
        _provider_at(item),
        sequence if type(sequence) is int else 0,
        mode,
        advances,
    )
    return (
        reason
        if p.gate_resume(normalized_gate, normalized_fact, now, tuple(seen))
        else None
    )
