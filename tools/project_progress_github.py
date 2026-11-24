"""GitHub shape translation for private progress evidence, without I/O or policy.

The existing authenticated reader owns acquisition, bounds and identity. CURRENT
means retrieved evidence, never semantic admission. Native dictionaries are the
explicit Any boundary; the neutral owner receives typed opaque references/reads.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from tools.agent_review_model import Ref
from tools.project_progress import Citation, Observation, Read

# re.ASCII keeps \d to the ASCII digits 0-9: a provider number is never another script's.
_TARGET = re.compile(r"(?:issue:[1-9]\d*/)?pr:([1-9]\d*)", re.ASCII)
_ISSUE = re.compile(r"issue:([1-9]\d*)", re.ASCII)
_URL_NUMBER = re.compile(r"/(?:issues|pull)/([1-9]\d*)(?:[#?].*)?$", re.ASCII)
_NUMBER = re.compile(r"[1-9]\d*", re.ASCII)
_HEAD = re.compile(r"[0-9a-f]{40}")
_ATTRIBUTES = (
    "source_binding_sha256",
    "updated_at",
    "author_id",
    "owner_verified",
    "head_sha",
    "base_sha",
    "state",
    "merged",
    "repository",
    "kind",
)


def scope_ref(scope: Mapping[str, Any]) -> Ref | None:
    match = _ISSUE.fullmatch(str(scope.get("ref") or ""))
    return Ref("work_item", match[1]) if match else None


def target_ref(target: object) -> Ref | None:
    text = str(target or "")
    issue, change = _ISSUE.fullmatch(text), _TARGET.fullmatch(text)
    if issue:
        return Ref("work_item", issue[1])
    return Ref("pr", change[1]) if change else None


def read_ref(pointer: str, held: Mapping[str, Any]) -> Ref | None:
    number = str(held.get("number") or "")
    if _NUMBER.fullmatch(number) is None:
        match = _URL_NUMBER.search(str(held.get("url") or pointer))
        number = match[1] if match else ""
    kind = held.get("kind")
    return Ref(str(kind), number) if number and isinstance(kind, str) else None


def observation(value: Any) -> Observation:
    return value if type(value) in (str, int, float) else None


def resume_event_time(kind: object, item: Mapping[str, Any]) -> float | None:
    """Project the GitHub event time for the shared resume policy."""
    if kind == "review":
        value = item.get("submitted_at")
    elif kind == "check_verdict":
        # Retain compatibility with archived facts that lack a completion field.
        value = item.get("completed_at", item.get("updated_at"))
    else:
        value = item.get("updated_at")
    if not isinstance(value, str):
        return None
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return instant.timestamp() if instant.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def read_source(pointer: str, held: Mapping[str, Any]) -> Read:
    digest = held.get("body_sha256")
    observed = held.get("observed_at")
    valid_observed = type(observed) is int or (
        isinstance(observed, float) and math.isfinite(observed)
    )
    return Read(
        pointer,
        read_ref(pointer, held),
        digest if isinstance(digest, str) else "",
        observation(observed),
        held.get("coverage") == "CURRENT"
        and isinstance(digest, str)
        and bool(digest)
        and valid_observed,
        held.get("body_complete") is True,
        tuple(
            (k, json.dumps(held[k], sort_keys=True)) for k in _ATTRIBUTES if k in held
        ),
    )


def citations(evidence: Any) -> tuple[tuple[Citation, ...], bool]:
    if not isinstance(evidence, list) or not evidence:
        return (), False
    result = []
    for entry in evidence:
        if (
            not isinstance(entry, dict)
            or set(entry) != {"source", "digest", "observed_at"}
            or not isinstance(entry["source"], str)
            or not isinstance(entry["digest"], str)
            or type(entry["observed_at"]) is bool
        ):
            return (), False
        result.append(
            Citation(
                entry["source"], entry["digest"], observation(entry["observed_at"])
            )
        )
    return tuple(result), True


def pr_closed(value: Mapping[str, Any]) -> bool:
    """The one closed-PR rule, for a retained source and for a captured read.

    A merge commit alone proves nothing: the provider sets a test-merge commit on
    an open PR too.
    """
    return (
        str(value.get("state") or "").lower() in ("closed", "merged")
        or value.get("merged") is True
    )


def closed_targets(sources: Any) -> tuple[Ref, ...]:
    return tuple(
        Ref("pr", str(s["pr_number"]))
        for s in sources
        if isinstance(s, dict)
        and s.get("kind") == "pr"
        and type(s.get("pr_number")) is int
        and pr_closed(s)
    )


def closed_reads(context: Mapping[str, Any]) -> tuple[Ref, ...]:
    """A captured PR read closes its target unless it reports a state that is open.

    A read that carries no state proves nothing about the PR, so it fails closed.
    """
    result = []
    for pointer, held in context.items():
        if (
            pointer.startswith("_")
            or not isinstance(held, dict)
            or held.get("kind") != "pr"
        ):
            continue
        ref = read_ref(pointer, held)
        state = held.get("state")
        is_open = isinstance(state, str) and state.lower() == "open"
        if ref is not None and (not is_open or pr_closed(held)):
            result.append(ref)
    return tuple(result)


def valid_subject(subject: Mapping[str, Any]) -> bool:
    number = subject.get("pr_number")
    return (
        type(number) is int
        and number > 0
        and _HEAD.fullmatch(str(subject.get("head_sha") or "")) is not None
    )


def subject_ref(subject: Mapping[str, Any]) -> Ref:
    return Ref("pr", str(subject["pr_number"]))
