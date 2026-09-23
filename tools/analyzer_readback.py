from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

SCHEMA = "gnostoa-analyzer-readback/v1"
COVERAGE_STATUSES = frozenset(
    {"COMPLETE", "INCOMPLETE", "PARTIAL", "RATE_LIMITED", "UNAVAILABLE", "ERROR"}
)
COMPLETENESS_STATES = frozenset(
    {"DIFF_LOCAL", "FULL_RUN", "AUTH_UNAVAILABLE", "READBACK_UNAVAILABLE", "AMBIGUOUS"}
)
_READBACK_UNAVAILABLE_COVERAGE = frozenset(
    {"PARTIAL", "RATE_LIMITED", "UNAVAILABLE", "ERROR"}
)
SCOPES = frozenset({"DIFF", "FULL"})
MAX_FINDINGS = 10_000
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_OWNER_SEGMENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
_REPOSITORY_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


class AnalyzerReadbackError(ValueError):
    """Normalized analyzer evidence violates the closed readback contract."""


def _required_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AnalyzerReadbackError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, label)


def _nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise AnalyzerReadbackError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise AnalyzerReadbackError(f"{label} must be a positive integer")
    return value


def _sha(value: object, label: str) -> str:
    text = _required_text(value, label)
    if _SHA40.fullmatch(text) is None:
        raise AnalyzerReadbackError(f"{label} must be an exact 40-character SHA")
    return text


def normalize_repository(value: object) -> str:
    text = _required_text(value, "repository")
    parts = text.split("/")
    if len(parts) != 2 or not all(parts):
        raise AnalyzerReadbackError("repository must use owner/name form")
    owner, name = parts
    if _OWNER_SEGMENT.fullmatch(owner) is None:
        raise AnalyzerReadbackError("repository owner contains an unsafe path segment")
    if name in {".", ".."} or _REPOSITORY_SEGMENT.fullmatch(name) is None:
        raise AnalyzerReadbackError("repository name contains an unsafe path segment")
    return text


def _range(value: object) -> dict[str, int] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise AnalyzerReadbackError("finding range must be an object")
    allowed = {"start_line", "start_column", "end_line", "end_column"}
    unknown = set(value) - allowed
    if unknown:
        raise AnalyzerReadbackError("finding range has unknown fields")
    result: dict[str, int] = {}
    for key in allowed:
        if key not in value or value[key] is None:
            continue
        result[key] = _positive_int(value[key], f"finding range {key}")
    if not result:
        return None
    start_line = result.get("start_line")
    end_line = result.get("end_line")
    if start_line is not None and end_line is not None and end_line < start_line:
        raise AnalyzerReadbackError("finding range ends before it starts")
    return result


def _provenance(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AnalyzerReadbackError("finding provenance must be an array")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str | None]] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise AnalyzerReadbackError("finding provenance items must be objects")
        surface = _required_text(item.get("surface"), "finding provenance surface")
        reference = _optional_text(
            item.get("reference"), "finding provenance reference"
        )
        key = (surface, reference)
        if key in seen:
            continue
        seen.add(key)
        record = {"surface": surface}
        if reference is not None:
            record["reference"] = reference
        result.append(record)
    result.sort(key=lambda item: (item["surface"], item.get("reference", "")))
    return result


def normalize_finding(value: Mapping[str, Any]) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "id": _required_text(value.get("id"), "finding id"),
        "message": _required_text(value.get("message"), "finding message"),
    }
    for key in ("rule", "severity", "category", "path", "state", "native_ref"):
        normalized = _optional_text(value.get(key), f"finding {key}")
        if normalized is not None:
            finding[key] = normalized
    location = _range(value.get("range"))
    if location is not None:
        finding["range"] = location
    provenance = _provenance(value.get("provenance"))
    if provenance:
        finding["provenance"] = provenance
    native = value.get("native")
    if native is not None:
        if not isinstance(native, Mapping):
            raise AnalyzerReadbackError("finding native provenance must be an object")
        finding["native"] = dict(native)
    return finding


def _without_provenance(finding: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in finding.items() if key != "provenance"}


def deduplicate_findings(values: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in values:
        finding = normalize_finding(raw)
        identity = finding["id"]
        existing = by_id.get(identity)
        if existing is None:
            by_id[identity] = finding
            continue
        if _without_provenance(existing) != _without_provenance(finding):
            raise AnalyzerReadbackError(
                f"provider-native finding identity {identity!r} is conflicting"
            )
        merged = _provenance(
            [
                *existing.get("provenance", []),
                *finding.get("provenance", []),
            ]
        )
        if merged:
            existing["provenance"] = merged
    if len(by_id) > MAX_FINDINGS:
        raise AnalyzerReadbackError("finding population exceeds bounded capacity")
    return [by_id[key] for key in sorted(by_id)]


def coverage(
    status: str,
    *,
    pages: int,
    count: int,
    total: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if status not in COVERAGE_STATUSES:
        raise AnalyzerReadbackError("coverage status is unsupported")
    result: dict[str, Any] = {
        "status": status,
        "pages": _nonnegative_int(pages, "coverage pages"),
        "count": _nonnegative_int(count, "coverage count"),
    }
    if total is not None:
        result["total"] = _nonnegative_int(total, "coverage total")
    if reason is not None:
        result["reason"] = _required_text(reason, "coverage reason")
    if status == "COMPLETE":
        if result["pages"] <= 0:
            raise AnalyzerReadbackError(
                "complete coverage must retain at least one page"
            )
        if total is not None and total != count:
            raise AnalyzerReadbackError(
                "complete coverage count disagrees with provider total"
            )
        if reason is not None:
            raise AnalyzerReadbackError(
                "complete coverage cannot carry a failure reason"
            )
    elif reason is None:
        raise AnalyzerReadbackError("non-complete coverage requires a reason")
    return result


def build_readback(
    *,
    provider: str,
    adapter: str,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_head: str | None,
    analysis_id: str | None,
    scope: str,
    completeness: str,
    native_mode: str,
    observed_at: str,
    run_state: str,
    coverage_record: Mapping[str, Any],
    findings: Iterable[Mapping[str, Any]],
    native: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if scope not in SCOPES:
        raise AnalyzerReadbackError("readback scope is unsupported")
    normalized_findings = deduplicate_findings(findings)
    retained_count = len(normalized_findings)
    observed_count = _nonnegative_int(coverage_record.get("count"), "coverage count")
    if observed_count < retained_count:
        raise AnalyzerReadbackError(
            "coverage count is smaller than retained finding population"
        )
    normalized_coverage = coverage(
        _required_text(coverage_record.get("status"), "coverage status"),
        pages=_nonnegative_int(coverage_record.get("pages"), "coverage pages"),
        count=retained_count,
        total=(
            None
            if coverage_record.get("total") is None
            else _nonnegative_int(coverage_record.get("total"), "coverage total")
        ),
        reason=(
            None
            if coverage_record.get("reason") is None
            else _required_text(coverage_record.get("reason"), "coverage reason")
        ),
    )
    normalized_completeness = _required_text(completeness, "completeness")
    if normalized_completeness not in COMPLETENESS_STATES:
        raise AnalyzerReadbackError("completeness state is unsupported")
    coverage_status = normalized_coverage["status"]
    if normalized_completeness == "FULL_RUN" and coverage_status != "COMPLETE":
        raise AnalyzerReadbackError("FULL_RUN requires COMPLETE coverage")
    if normalized_completeness == "AMBIGUOUS" and coverage_status != "INCOMPLETE":
        raise AnalyzerReadbackError("AMBIGUOUS requires INCOMPLETE coverage")
    if (
        normalized_completeness == "AUTH_UNAVAILABLE"
        and coverage_status != "UNAVAILABLE"
    ):
        raise AnalyzerReadbackError("AUTH_UNAVAILABLE requires UNAVAILABLE coverage")
    if (
        normalized_completeness == "READBACK_UNAVAILABLE"
        and coverage_status not in _READBACK_UNAVAILABLE_COVERAGE
    ):
        raise AnalyzerReadbackError(
            "READBACK_UNAVAILABLE requires unavailable or incomplete read coverage"
        )
    requested = _sha(requested_head, "requested head")
    observed = None if observed_head is None else _sha(observed_head, "observed head")
    if normalized_coverage["status"] == "COMPLETE" and observed != requested:
        raise AnalyzerReadbackError(
            "complete readback must bind the requested exact head"
        )
    document: dict[str, Any] = {
        "schema": SCHEMA,
        "provider": _required_text(provider, "provider"),
        "adapter": _required_text(adapter, "adapter"),
        "repository": normalize_repository(repository),
        "pull_number": _positive_int(pull_number, "pull number"),
        "requested_head": requested,
        "scope": scope,
        "completeness": normalized_completeness,
        "native_mode": _required_text(native_mode, "native mode"),
        "observed_at": _required_text(observed_at, "observed at"),
        "run_state": _required_text(run_state, "run state"),
        "coverage": normalized_coverage,
        "findings": normalized_findings,
    }
    if observed is not None:
        document["observed_head"] = observed
    analysis = _optional_text(analysis_id, "analysis id")
    if analysis is not None:
        document["analysis_id"] = analysis
    if native is not None:
        if not isinstance(native, Mapping):
            raise AnalyzerReadbackError("native provenance must be an object")
        document["native"] = dict(native)
    return document


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
