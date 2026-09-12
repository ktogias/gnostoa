from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

SEMANTIC_EXIT_CODES: dict[str, int] = {
    "PASS": 0,
    "BLOCKED": 1,
    "INCOMPLETE": 3,
    "CONFLICTING": 4,
}
ERROR_EXIT_CODE = 2


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_rfc3339(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp must be a non-empty RFC3339 string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def error_payload(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": {} if details is None else details,
        }
    }


def semantic_result(
    outcome: str,
    reason: str,
    *,
    input_document: dict[str, Any],
    policy_document: dict[str, Any],
    assessments: list[dict[str, Any]],
    collection: dict[str, Any],
    qualification: dict[str, Any],
    quorum: dict[str, Any],
    blockers: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    diagnostics: list[str],
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "reason": reason,
        "binding": False,
        "evaluation_context": input_document.get("evaluation_context", {}),
        "subject": input_document.get("subject", {}),
        "authority": input_document.get("authority", {}),
        "judge": input_document.get("acquired_judge", {}),
        "policy": {
            "id": policy_document.get("id"),
            "version": policy_document.get("version"),
            "change_class": policy_document.get("change_class"),
            "review_requirement": policy_document.get("review_requirement"),
        },
        "collection": collection,
        "qualification": qualification,
        "quorum": quorum,
        "blockers": blockers,
        "conflicts": conflicts,
        "exclusions": exclusions,
        "diagnostics": sorted(set(diagnostics)),
        "assessments": assessments,
    }
