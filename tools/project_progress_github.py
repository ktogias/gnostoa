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
from typing import Any

from tools.agent_review_model import Ref
from tools.project_progress import Citation, Observation, Read

_TARGET = re.compile(r"(?:issue:[1-9][0-9]*/)?pr:([1-9][0-9]*)")
_ISSUE = re.compile(r"issue:([1-9][0-9]*)")
_HEAD = re.compile(r"[0-9a-f]{40}")
_ATTRIBUTES = (
    "source_binding_sha256",
    "updated_at",
    "author_id",
    "owner_verified",
    "head_sha",
    "base_sha",
    "state",
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
    if not number.isdigit():
        match = re.search(
            r"/(?:issues|pull)/([1-9][0-9]*)(?:[#?].*)?$",
            str(held.get("url") or pointer),
        )
        number = match[1] if match else ""
    kind = held.get("kind")
    return Ref(str(kind), number) if number and isinstance(kind, str) else None


def observation(value: Any) -> Observation:
    return value if isinstance(value, (str, int, float)) or value is None else None


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


def closed_targets(sources: Any) -> tuple[Ref, ...]:
    return tuple(
        Ref("pr", str(s["pr_number"]))
        for s in sources
        if isinstance(s, dict)
        and s.get("kind") == "pr"
        and type(s.get("pr_number")) is int
        and (
            s.get("state") == "closed"
            or s.get("merged") is True
            or s.get("merge_commit_sha")
        )
    )


def valid_subject(subject: Mapping[str, Any]) -> bool:
    return (
        type(subject.get("pr_number")) is int
        and _HEAD.fullmatch(str(subject.get("head_sha") or "")) is not None
    )


def subject_ref(subject: Mapping[str, Any]) -> Ref:
    return Ref("pr", str(subject["pr_number"]))
