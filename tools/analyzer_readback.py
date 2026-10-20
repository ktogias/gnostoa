from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from itertools import pairwise
from typing import Any

SCHEMA = "gnostoa-analyzer-readback/v1"
# The bundle the authenticated readback workflow records (ci/analyzer_readback.py).
BUNDLE_SCHEMA = "gnostoa-analyzer-readback-bundle/v1"
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
    if start_line is not None and end_line is not None:
        # Omitted columns cannot establish reversed same-line coordinates.
        start = (start_line, result.get("start_column", 1))
        end = (end_line, result.get("end_column", start[1]))
        if end < start:
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


def _tool_identity(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise AnalyzerReadbackError("finding tool identity must be an object")
    allowed = {"id", "name"}
    unknown = set(value) - allowed
    if unknown:
        raise AnalyzerReadbackError("finding tool identity has unknown fields")
    result = {"id": _required_text(value.get("id"), "finding tool id")}
    name = _optional_text(value.get("name"), "finding tool name")
    if name is not None:
        result["name"] = name
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
    tool = _tool_identity(value.get("tool"))
    if tool is not None:
        finding["tool"] = tool
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


def _check_completeness_pairing(completeness: str, coverage_status: str) -> None:
    """A readback's completeness and its coverage status must agree."""

    if completeness not in COMPLETENESS_STATES:
        raise AnalyzerReadbackError("completeness state is unsupported")
    if completeness == "FULL_RUN" and coverage_status != "COMPLETE":
        raise AnalyzerReadbackError("FULL_RUN requires COMPLETE coverage")
    if completeness == "AMBIGUOUS" and coverage_status != "INCOMPLETE":
        raise AnalyzerReadbackError("AMBIGUOUS requires INCOMPLETE coverage")
    if coverage_status == "INCOMPLETE" and completeness != "AMBIGUOUS":
        raise AnalyzerReadbackError(
            "INCOMPLETE coverage requires AMBIGUOUS completeness"
        )
    if completeness == "AUTH_UNAVAILABLE" and coverage_status != "UNAVAILABLE":
        raise AnalyzerReadbackError("AUTH_UNAVAILABLE requires UNAVAILABLE coverage")
    if (
        completeness == "READBACK_UNAVAILABLE"
        and coverage_status not in _READBACK_UNAVAILABLE_COVERAGE
    ):
        raise AnalyzerReadbackError(
            "READBACK_UNAVAILABLE requires unavailable or incomplete read coverage"
        )


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
    coverage_status = _required_text(coverage_record.get("status"), "coverage status")
    if observed_count < retained_count:
        raise AnalyzerReadbackError(
            "coverage count is smaller than retained finding population"
        )
    if coverage_status == "COMPLETE" and observed_count != retained_count:
        raise AnalyzerReadbackError(
            "complete coverage count must match retained finding population"
        )
    normalized_coverage = coverage(
        coverage_status,
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
    _check_completeness_pairing(normalized_completeness, normalized_coverage["status"])
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


_READBACK_KEYS = frozenset(
    {
        "schema",
        "provider",
        "adapter",
        "repository",
        "pull_number",
        "requested_head",
        "scope",
        "completeness",
        "native_mode",
        "observed_at",
        "run_state",
        "coverage",
        "findings",
    }
)
_READBACK_OPTIONAL_KEYS = frozenset({"observed_head", "analysis_id", "native"})
_BUNDLE_KEYS = frozenset(
    {
        "schema",
        "repository",
        "pull_number",
        "requested_head",
        "observed_head",
        "observed_at",
        "subject_binding",
        "readbacks",
    }
)
_BINDING_KEYS = {
    "BOUND": _BUNDLE_KEYS | {"github_projection"},
    "INCOMPLETE": _BUNDLE_KEYS | {"reason"},
}
_PROJECTION_KEYS = frozenset({"statuses", "check_runs", "review_comments"})


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AnalyzerReadbackError(f"{label} must be an object")
    return value


def parse_readback(value: object) -> dict[str, Any]:
    """A recorded readback, accepted only when `build_readback` rebuilds it
    exactly from its own fields: one contract for writing and reading it
    (#407, slice 1b.3b-2)."""

    readback = _mapping(value, "readback")
    keys = set(readback)
    if not _READBACK_KEYS <= keys or keys - _READBACK_KEYS - _READBACK_OPTIONAL_KEYS:
        raise AnalyzerReadbackError("readback has missing or unknown fields")
    if readback["schema"] != SCHEMA:
        raise AnalyzerReadbackError(f"readback schema must be {SCHEMA!r}")
    findings = readback["findings"]
    if not isinstance(findings, list):
        raise AnalyzerReadbackError("readback findings must be an array")
    for finding in findings:
        _mapping(finding, "readback finding")
    if not isinstance(readback["scope"], str):
        raise AnalyzerReadbackError("readback scope must be text")
    rebuilt = build_readback(
        provider=readback["provider"],
        adapter=readback["adapter"],
        repository=readback["repository"],
        pull_number=readback["pull_number"],
        requested_head=readback["requested_head"],
        observed_head=readback.get("observed_head"),
        analysis_id=readback.get("analysis_id"),
        scope=readback["scope"],
        completeness=readback["completeness"],
        native_mode=readback["native_mode"],
        observed_at=readback["observed_at"],
        run_state=readback["run_state"],
        coverage_record=_mapping(readback["coverage"], "readback coverage"),
        findings=findings,
        native=readback.get("native"),
    )
    if canonical_json(rebuilt) != canonical_json(readback):
        raise AnalyzerReadbackError("readback is not what its contract builds")
    return rebuilt


def parse_bundle(value: object) -> dict[str, Any]:
    """A recorded readback bundle. A `BOUND` one observed its requested head and
    holds only readbacks of its own subject; an `INCOMPLETE` one says why and
    holds none (#407, slice 1b.3b-2)."""

    bundle = _mapping(value, "bundle")
    binding = bundle.get("subject_binding")
    if not isinstance(binding, str) or binding not in _BINDING_KEYS:
        raise AnalyzerReadbackError("bundle subject binding is unsupported")
    if set(bundle) != _BINDING_KEYS[binding]:
        raise AnalyzerReadbackError("bundle has missing or unknown fields")
    if bundle["schema"] != BUNDLE_SCHEMA:
        raise AnalyzerReadbackError(f"bundle schema must be {BUNDLE_SCHEMA!r}")
    subject = (
        normalize_repository(bundle["repository"]),
        _positive_int(bundle["pull_number"], "bundle pull number"),
        _sha(bundle["requested_head"], "bundle requested head"),
    )
    observed = _sha(bundle["observed_head"], "bundle observed head")
    _required_text(bundle["observed_at"], "bundle observed at")
    if not isinstance(bundle["readbacks"], list):
        raise AnalyzerReadbackError("bundle readbacks must be an array")
    readbacks = [parse_readback(item) for item in bundle["readbacks"]]
    if binding == "BOUND":
        _check_bound(bundle, subject, observed, readbacks)
    else:
        _check_incomplete(bundle, readbacks)
    return {**bundle, "readbacks": readbacks}


# The private capability record (#389 F3 R0b; Router 6269272533 and entry
# 6292521425). An analyzer provider's current capability: the analyzers it has
# enabled, each one's rule catalogue, its ignore rules and whether a configuration is
# present. It is not bound to a head, so it is never a readback; its catalogues are an
# observed inventory, never the effective rule selection or an assurance claim. Each
# adapter translates its native discovery into it; nothing here branches on one.
CAPABILITY_SCHEMA = "gnostoa-analyzer-capability/v1"
# An analysis or run id alone never binds a capability to a run (Router 6269272533):
# no provider evidence of that binding is admitted, so RUN_BOUND is not a value.
CAPABILITY_BINDINGS = frozenset({"CURRENT_NOT_RUN_BOUND", "UNKNOWN"})
# A catalogue read whole, one a request was made for but not read whole, or one never
# requested. Unknown is never an empty COMPLETE catalogue (Router 6280406609).
CATALOGUE_STATES = frozenset({"COMPLETE", "PARTIAL", "UNREAD"})
# What a provider said of its configuration: never reached, not offered, none, or one.
CONFIGURATION_STATES = frozenset({"UNREAD", "UNSUPPORTED", "ABSENT", "PRESENT"})
_INVENTORY_STATUSES = COVERAGE_STATUSES | {"UNREAD"}
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_CAPABILITY_KEYS = frozenset(
    {
        "schema",
        "provider",
        "adapter",
        "repository",
        "observed_at",
        "binding",
        "coverage",
        "configuration",
        "activated",
        "enabled",
        "catalogues",
        "ignore_rules",
        "effective_configuration",
        "unknown",
    }
)
_CAPABILITY_OPTIONAL_KEYS = frozenset({"native"})


def _closed(
    value: object,
    label: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> Mapping[str, Any]:
    record = _mapping(value, label)
    keys = set(record)
    if not required <= keys or keys - required - optional:
        raise AnalyzerReadbackError(f"{label} has missing or unknown fields")
    return record


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AnalyzerReadbackError(f"{label} must be an array")
    return value


def _unique_sorted(
    items: list[dict[str, Any]], key: str, label: str
) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: item[key])
    for first, second in pairwise(ordered):
        if first[key] == second[key]:
            raise AnalyzerReadbackError(f"{label} repeats the identity {first[key]!r}")
    return ordered


def _capability_coverage(value: object) -> dict[str, Any]:
    record = _closed(
        value,
        "capability coverage",
        frozenset({"status", "pages", "count"}),
        frozenset({"total", "reason"}),
    )
    status = record["status"]
    if not isinstance(status, str):
        raise AnalyzerReadbackError("coverage status is unsupported")
    return coverage(
        status,
        pages=record["pages"],
        count=record["count"],
        total=record.get("total"),
        reason=record.get("reason"),
    )


def _capability_configuration(value: object) -> dict[str, Any]:
    record = _closed(
        value, "capability configuration", frozenset({"state"}), frozenset({"digest"})
    )
    state = record["state"]
    if not isinstance(state, str) or state not in CONFIGURATION_STATES:
        raise AnalyzerReadbackError("capability configuration state is unsupported")
    if state != "PRESENT":
        if "digest" in record:
            raise AnalyzerReadbackError("only a present configuration has a digest")
        return {"state": state}
    digest = _required_text(record.get("digest"), "capability configuration digest")
    if _DIGEST.fullmatch(digest) is None:
        raise AnalyzerReadbackError("capability configuration digest is not sha256")
    return {"state": state, "digest": digest}


def _inventory_status(value: object, label: str) -> str:
    if not isinstance(value, str) or value not in _INVENTORY_STATUSES:
        raise AnalyzerReadbackError(f"{label} status is unsupported")
    return value


def _enabled(value: object) -> dict[str, Any]:
    record = _closed(value, "capability enabled", frozenset({"status", "analyzers"}))
    status = _inventory_status(record["status"], "capability enabled")
    if status != "COMPLETE":
        # Descriptors not read whole are unknown, never an empty inventory.
        if record["analyzers"] is not None:
            raise AnalyzerReadbackError(
                "an enabled list not read whole has no analyzers"
            )
        return {"status": status, "analyzers": None}
    analyzers = [
        {
            "id": _required_text(item["id"], "enabled analyzer id"),
            "version": _optional_text(item["version"], "enabled analyzer version"),
            "declared_entries": None
            if item["declared_entries"] is None
            else _nonnegative_int(item["declared_entries"], "enabled analyzer entries"),
        }
        for item in (
            _closed(
                entry,
                "enabled analyzer",
                frozenset({"id", "version", "declared_entries"}),
            )
            for entry in _array(record["analyzers"], "capability enabled analyzers")
        )
    ]
    return {
        "status": status,
        "analyzers": _unique_sorted(analyzers, "id", "enabled analyzers"),
    }


def _catalogue(
    value: object, enabled: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    record = _closed(
        value,
        "capability catalogue",
        frozenset({"analyzer", "state", "version", "entries"}),
    )
    analyzer = _required_text(record["analyzer"], "catalogue analyzer")
    descriptor = enabled.get(analyzer)
    if descriptor is None:
        raise AnalyzerReadbackError(
            f"a catalogue names no enabled analyzer: {analyzer!r}"
        )
    state = record["state"]
    if not isinstance(state, str) or state not in CATALOGUE_STATES:
        raise AnalyzerReadbackError("catalogue state is unsupported")
    version = _optional_text(record["version"], "catalogue version")
    if version != descriptor["version"]:
        raise AnalyzerReadbackError("a catalogue's version is not its analyzer's")
    if state != "COMPLETE":
        if record["entries"] is not None:
            raise AnalyzerReadbackError("only a catalogue read whole has entries")
        return {
            "analyzer": analyzer,
            "state": state,
            "version": version,
            "entries": None,
        }
    if descriptor["declared_entries"] is None:
        raise AnalyzerReadbackError("a catalogue of unknown size cannot be complete")
    entries = [
        {
            "id": _required_text(item["id"], "catalogue entry id"),
            "title": _optional_text(item.get("title"), "catalogue entry title"),
        }
        for item in (
            _closed(entry, "catalogue entry", frozenset({"id"}), frozenset({"title"}))
            for entry in _array(record["entries"], "catalogue entries")
        )
    ]
    if len(entries) != descriptor["declared_entries"]:
        raise AnalyzerReadbackError(
            "a complete catalogue disagrees with its declared size"
        )
    return {
        "analyzer": analyzer,
        "state": state,
        "version": version,
        "entries": _unique_sorted(entries, "id", "catalogue entries"),
    }


def _ignore_rules(value: object) -> dict[str, Any]:
    record = _closed(value, "capability ignore rules", frozenset({"status", "rules"}))
    status = _inventory_status(record["status"], "capability ignore rules")
    if status != "COMPLETE":
        if record["rules"] is not None:
            raise AnalyzerReadbackError("ignore rules not read whole are unknown")
        return {"status": status, "rules": None}
    rules = [
        _ignore_rule(
            _closed(
                entry,
                "ignore rule",
                frozenset({"id", "rule", "path", "glob"}),
                frozenset({"native"}),
            )
        )
        for entry in _array(record["rules"], "capability ignore rules")
    ]
    return {"status": status, "rules": _unique_sorted(rules, "id", "ignore rules")}


def _ignore_rule(item: Mapping[str, Any]) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "id": _required_text(item["id"], "ignore rule id"),
        "rule": _required_text(item["rule"], "ignore rule target"),
        # A path and a glob are each kept, never one for the other (Amazon Q on #444).
        "path": _optional_text(item["path"], "ignore rule path"),
        "glob": _optional_text(item["glob"], "ignore rule glob"),
    }
    if "native" in item:
        # A provider's own terms for a rule, such as its level or duration: carried,
        # and never interpreted here (Sourcery on #444).
        rule["native"] = dict(_mapping(item["native"], "ignore rule native"))
    return rule


def build_capability(
    *,
    provider: object,
    adapter: object,
    repository: object,
    observed_at: object,
    binding: object,
    coverage: object,
    configuration: object,
    activated: object,
    enabled: object,
    catalogues: object,
    ignore_rules: object,
    unknown: object,
    native: object = None,
) -> dict[str, Any]:
    """One capability record from an adapter's translation, or a refusal. Its
    coverage is the whole read's: COMPLETE only when every part was read whole, and
    its count is the entries of the catalogues read whole."""

    if not isinstance(binding, str) or binding not in CAPABILITY_BINDINGS:
        raise AnalyzerReadbackError("capability binding is unsupported")
    if activated is not None and type(activated) is not bool:
        raise AnalyzerReadbackError("capability activation must be a boolean or null")
    read = _capability_coverage(coverage)
    inventory = _enabled(enabled)
    descriptors = {item["id"]: item for item in inventory["analyzers"] or []}
    catalogue_list = [
        _catalogue(item, descriptors)
        for item in _array(catalogues, "capability catalogues")
    ]
    catalogue_list = _unique_sorted(catalogue_list, "analyzer", "capability catalogues")
    if [item["analyzer"] for item in catalogue_list] != sorted(descriptors):
        # Each enabled analyzer has one catalogue state, and none is invented.
        raise AnalyzerReadbackError("catalogues are not one per enabled analyzer")
    rules = _ignore_rules(ignore_rules)
    config = _capability_configuration(configuration)
    entries = sum(
        len(item["entries"]) for item in catalogue_list if item["entries"] is not None
    )
    if read["count"] != entries:
        raise AnalyzerReadbackError(
            "capability coverage count is not its catalogue entries"
        )
    if read["status"] == "COMPLETE" and (
        inventory["status"] != "COMPLETE"
        or rules["status"] != "COMPLETE"
        or config["state"] == "UNREAD"
        or any(item["state"] != "COMPLETE" for item in catalogue_list)
    ):
        raise AnalyzerReadbackError("complete capability coverage has an unread part")
    record: dict[str, Any] = {
        "schema": CAPABILITY_SCHEMA,
        "provider": _required_text(provider, "capability provider"),
        "adapter": _required_text(adapter, "capability adapter"),
        "repository": normalize_repository(repository),
        "observed_at": _required_text(observed_at, "capability observed at"),
        "binding": binding,
        "coverage": read,
        "configuration": config,
        "activated": activated,
        "enabled": inventory,
        "catalogues": catalogue_list,
        "ignore_rules": rules,
        # A catalogue inventory never proves which rules a run applies.
        "effective_configuration": "UNPROVEN",
        "unknown": [
            _required_text(item, "capability unknown")
            for item in _array(unknown, "capability unknown")
        ],
    }
    if native is not None:
        record["native"] = dict(_mapping(native, "capability native"))
    try:
        canonical_json(record)
    except (TypeError, ValueError) as exc:
        # A value JSON cannot hold is a contract refusal too (Amazon Q on #444).
        raise AnalyzerReadbackError("capability record is not canonical JSON") from exc
    return record


def parse_capability(value: object) -> dict[str, Any]:
    """A recorded capability, accepted only when `build_capability` rebuilds it
    exactly from its own fields, as `parse_readback` does a readback."""

    record = _closed(value, "capability", _CAPABILITY_KEYS, _CAPABILITY_OPTIONAL_KEYS)
    if record["schema"] != CAPABILITY_SCHEMA:
        raise AnalyzerReadbackError(f"capability schema must be {CAPABILITY_SCHEMA!r}")
    if record["effective_configuration"] != "UNPROVEN":
        raise AnalyzerReadbackError(
            "a capability never proves its effective configuration"
        )
    rebuilt = build_capability(
        provider=record["provider"],
        adapter=record["adapter"],
        repository=record["repository"],
        observed_at=record["observed_at"],
        binding=record["binding"],
        coverage=record["coverage"],
        configuration=record["configuration"],
        activated=record["activated"],
        enabled=record["enabled"],
        catalogues=record["catalogues"],
        ignore_rules=record["ignore_rules"],
        unknown=record["unknown"],
        native=record.get("native"),
    )
    if canonical_json(rebuilt) != canonical_json(record):
        raise AnalyzerReadbackError("capability is not what its contract builds")
    return rebuilt


def catalogue_inventory(value: object) -> dict[str, Any]:
    """The neutral reading of a capability record: whether its enabled list is known,
    and each enabled analyzer's catalogue state and entry identities. It reads only
    the contract's own fields, never a provider's."""

    record = parse_capability(value)
    return {
        "enabled": record["enabled"]["status"],
        "analyzers": [
            {
                "id": item["analyzer"],
                "version": item["version"],
                "state": item["state"],
                "entries": None
                if item["entries"] is None
                else [entry["id"] for entry in item["entries"]],
            }
            for item in record["catalogues"]
        ],
        "complete": record["coverage"]["status"] == "COMPLETE",
        "reason": record["coverage"].get("reason"),
    }


def _check_bound(
    bundle: Mapping[str, Any],
    subject: tuple[str, int, str],
    observed: str,
    readbacks: list[dict[str, Any]],
) -> None:
    if observed != subject[2]:
        raise AnalyzerReadbackError("a bound bundle must observe its requested head")
    projection = _mapping(bundle["github_projection"], "bundle projection")
    if set(projection) != _PROJECTION_KEYS:
        raise AnalyzerReadbackError("bundle projection has missing or unknown fields")
    for key in sorted(projection):
        _nonnegative_int(projection[key], f"bundle projection {key}")
    for readback in readbacks:
        if (
            readback["repository"],
            readback["pull_number"],
            readback["requested_head"],
        ) != subject:
            raise AnalyzerReadbackError("a readback is not the bundle's subject")


def _check_incomplete(
    bundle: Mapping[str, Any], readbacks: list[dict[str, Any]]
) -> None:
    _required_text(bundle["reason"], "bundle reason")
    if readbacks:
        raise AnalyzerReadbackError("an incomplete bundle holds no readbacks")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
