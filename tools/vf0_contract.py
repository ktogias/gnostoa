"""Private VF0 relation checks over normalized, untrusted data.

MATCH is neither authenticated acquisition nor preparation eligibility. A protected
composition boundary must supply those separately. This module does no provider,
filesystem or process I/O and cannot grant compliance, human approval or activation.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, cast
from urllib.parse import urlsplit

MAX_BYTES = 262_144
MAX_DEPTH = 12
MAX_NODES = 8192
SCHEMA = "gnostoa-vf0-relation-input/v1"
RESULT_SCHEMA = "gnostoa-vf0-relation-result/v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MODES = {"RED", "CHARACTERIZATION", "STRUCTURAL", "EMERGENCY_POST_EVENT"}
_CLASSES = {"mechanical", "normal", "normative", "critical", "emergency"}
_GUARANTEES = {
    "request_binding",
    "record_coverage",
    "attempt_identity",
    "latest_attempt",
    "source_revalidation",
    "protection_revalidation",
    "credential_separation",
}
_REF_FIELDS = {"provider", "instance", "repository", "opaque_id"}
_MATERIAL_FIELDS = {
    "parent_commit",
    "parent_tree",
    "evidence_tree",
    "evidence_patch_sha256",
    "production_sha256",
    "command_sha256",
    "oracle_sha256",
    "evidence_files",
}


class _Invalid(ValueError):
    """Static non-secret failure code; never carries raw input material."""


def _need(condition: object, code: str) -> None:
    if not condition:
        raise _Invalid(code)


def _copy_json(value: object) -> Any:
    """Bound Python inputs before encoding; reject aliases that exceed the budget."""
    nodes = 0
    text_bytes = 0

    def visit(item: object, depth: int) -> Any:
        nonlocal nodes, text_bytes
        nodes += 1
        _need(nodes <= MAX_NODES and depth <= MAX_DEPTH, "INPUT_COMPLEXITY")
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _need(-(2**63) <= item < 2**63, "INTEGER_BOUND")
            return item
        if type(item) is str:
            _need(len(item) <= 4096, "STRING_BOUND")
            text_bytes += len(item.encode("utf-8", errors="strict"))
            _need(text_bytes <= MAX_BYTES, "INPUT_SIZE")
            return item
        if type(item) is list:
            _need(len(item) <= MAX_NODES, "INPUT_COMPLEXITY")
            return [visit(child, depth + 1) for child in item]
        if type(item) is dict:
            _need(len(item) <= MAX_NODES, "INPUT_COMPLEXITY")
            result = {}
            for key, child in item.items():
                _need(type(key) is str and len(key) <= 512, "OBJECT_KEY")
                visit(key, depth + 1)
                result[key] = visit(child, depth + 1)
            return result
        raise _Invalid("JSON_TYPE")

    result = visit(value, 0)
    _need(len(_canonical(result)) <= MAX_BYTES, "INPUT_SIZE")
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _mapping(value: Any, fields: set[str]) -> dict[str, Any]:
    _need(type(value) is dict and set(value) == fields, "OBJECT_FIELDS")
    return cast(dict[str, Any], value)


def _text(value: Any, limit: int = 256) -> str:
    _need(type(value) is str and 0 < len(value) <= limit, "TEXT_IDENTITY")
    _need(
        value == value.strip() and all(ord(c) >= 32 and ord(c) != 127 for c in value),
        "TEXT_IDENTITY",
    )
    return cast(str, value)


def _sha(value: Any) -> str:
    _need(type(value) is str and _DIGEST.fullmatch(value), "DIGEST_FORMAT")
    return cast(str, value)


def _time(value: Any) -> int:
    _need(type(value) is int and 0 <= value <= 253_402_300_799, "TIME_FORMAT")
    return cast(int, value)


def _reference(value: Any) -> dict[str, str]:
    result = _mapping(value, _REF_FIELDS)
    for key in sorted(_REF_FIELDS):
        _text(result[key])
    return result


def _namespace(reference: dict[str, str]) -> tuple[str, str, str]:
    return reference["provider"], reference["instance"], reference["repository"]


def _path(value: Any) -> str:
    path = _text(value, 512)
    _need("\\" not in path and all(ord(c) >= 33 for c in path), "PATH_FORMAT")
    _need(
        all(part not in {"", ".", "..", ".git"} for part in path.split("/")),
        "PATH_FORMAT",
    )
    return path


def _paths(value: Any) -> set[str]:
    _need(type(value) is list and 0 < len(value) <= 256, "PATH_SET")
    paths = [_path(path) for path in value]
    _need(len(paths) == len(set(paths)), "DUPLICATE_PATH")
    return set(paths)


def _files(value: Any) -> dict[str, str]:
    _need(type(value) is dict and len(value) <= 256, "FILE_MANIFEST")
    for path, sha in value.items():
        _path(path)
        _sha(sha)
    return cast(dict[str, str], value)


def _material(value: Any) -> dict[str, Any]:
    material = _mapping(value, _MATERIAL_FIELDS)
    for key in ("parent_commit", "parent_tree", "evidence_tree"):
        _text(material[key])
    for key in (
        "evidence_patch_sha256",
        "production_sha256",
        "command_sha256",
        "oracle_sha256",
    ):
        _sha(material[key])
    _files(material["evidence_files"])
    return material


def _outcome(value: Any) -> tuple[int, dict[str, tuple[str, str]]]:
    outcome = _mapping(value, {"exit_code", "cases"})
    exit_code = outcome["exit_code"]
    _need(type(exit_code) is int and -255 <= exit_code <= 255, "EXIT_CODE")
    cases = outcome["cases"]
    _need(type(cases) is list and len(cases) <= 256, "CASE_SET")
    by_id: dict[str, tuple[str, str]] = {}
    for item in cases:
        case = _mapping(item, {"id", "result", "cause"})
        case_id = _text(case["id"])
        _need(case_id not in by_id, "DUPLICATE_CASE")
        _need(case["result"] in {"PASS", "FAIL", "ERROR", "SKIP"}, "CASE_RESULT")
        cause = _text(case["cause"])
        by_id[case_id] = (case["result"], cause)
    return exit_code, by_id


def _guarantees(value: Any, required: set[str]) -> None:
    _need(type(value) is dict and len(value) <= 32, "GUARANTEE_SET")
    _need(required <= set(value), "MISSING_GUARANTEE")
    for name in sorted(value):
        _text(name, 80)
        item = _mapping(value[name], {"state", "records"})
        _need(
            item["state"] in {"VERIFIED", "UNKNOWN", "UNSUPPORTED", "CONTRADICTED"},
            "GUARANTEE_STATE",
        )
        records = item["records"]
        _need(type(records) is list and len(records) <= 32, "GUARANTEE_RECORDS")
        for record in records:
            _sha(record)
        _need(len(set(records)) == len(records), "DUPLICATE_GUARANTEE_RECORD")
        if name in required:
            _need(item["state"] == "VERIFIED" and records, "UNPROVEN_GUARANTEE")


def _policy(value: Any) -> tuple[dict[str, Any], set[str]]:
    policy = _mapping(value, {"id", "modes", "required_guarantees", "max_age_seconds"})
    _text(policy["id"])
    modes = _mapping(policy["modes"], _CLASSES)
    for name in sorted(modes):
        choices = modes[name]
        _need(type(choices) is list and 0 < len(choices) <= len(_MODES), "POLICY_MODES")
        _need(
            all(type(mode) is str and mode in _MODES for mode in choices),
            "POLICY_MODES",
        )
        _need(len(set(choices)) == len(choices), "POLICY_MODES")
    required = policy["required_guarantees"]
    _need(type(required) is list and 0 < len(required) <= 32, "POLICY_GUARANTEES")
    for name in required:
        _text(name, 80)
    _need(
        len(set(required)) == len(required) and _GUARANTEES <= set(required),
        "POLICY_GUARANTEES",
    )
    age = policy["max_age_seconds"]
    _need(type(age) is int and 0 < age <= 604_800, "POLICY_FRESHNESS")
    return policy, set(required)


def _request(value: Any, policy: dict[str, Any]) -> dict[str, Any]:
    request = _mapping(
        value,
        {
            "identity",
            "work_item",
            "decision",
            "policy_sha256",
            "change_class",
            "mode",
            "criterion",
            "candidate_paths",
            "material",
            "outcome",
            "valid_from",
            "valid_until",
            "follow_up",
        },
    )
    for field in ("identity", "work_item", "decision"):
        _reference(request[field])
    _need(_sha(request["policy_sha256"]) == _digest(policy), "POLICY_BINDING")
    change_class, mode = request["change_class"], request["mode"]
    _need(type(change_class) is str and change_class in _CLASSES, "CHANGE_CLASS")
    _need(type(mode) is str and mode in _MODES, "EVIDENCE_MODE")
    _need(mode in policy["modes"][change_class], "MODE_NOT_ADMITTED")
    _need(request["criterion"] in {"EXECUTABLE", "NON_EXECUTABLE"}, "CRITERION_KIND")
    allowed = _paths(request["candidate_paths"])
    material = _material(request["material"])
    _need(set(material["evidence_files"]) <= allowed, "EVIDENCE_PATH_SCOPE")
    _outcome(request["outcome"])
    _need(
        _time(request["valid_from"]) < _time(request["valid_until"]), "REQUEST_INTERVAL"
    )
    if request["follow_up"] is not None:
        _reference(request["follow_up"])
    return request


def _admission(
    value: Any, request: dict[str, Any], required: set[str]
) -> dict[str, Any]:
    admission = _mapping(
        value,
        {
            "request_sha256",
            "record",
            "record_sha256",
            "principal",
            "disposition",
            "observed_at",
            "guarantees",
        },
    )
    _need(_sha(admission["request_sha256"]) == _digest(request), "ADMISSION_BINDING")
    _reference(admission["record"])
    _reference(admission["principal"])
    _sha(admission["record_sha256"])
    _need(admission["disposition"] == "APPROVED", "ADMISSION_DISPOSITION")
    _time(admission["observed_at"])
    _guarantees(admission["guarantees"], required)
    return admission


def _evidence(
    value: Any, request: dict[str, Any], admission: dict[str, Any], required: set[str]
) -> dict[str, Any]:
    evidence = _mapping(
        value,
        {
            "request_sha256",
            "admission_sha256",
            "material",
            "mode",
            "chronology",
            "execution",
            "attempt",
            "latest_attempt",
            "publisher",
            "artifact",
            "source_sha256",
            "archive_sha256",
            "status",
            "coverage",
            "started_at",
            "completed_at",
            "expires_at",
            "outcome",
            "accountable_review",
            "guarantees",
        },
    )
    _need(
        _sha(evidence["request_sha256"]) == _digest(request), "EVIDENCE_REQUEST_BINDING"
    )
    _need(
        _sha(evidence["admission_sha256"]) == _digest(admission),
        "EVIDENCE_ADMISSION_BINDING",
    )
    _need(
        _material(evidence["material"]) == request["material"],
        "EVIDENCE_MATERIAL_BINDING",
    )
    _need(evidence["mode"] == request["mode"], "EVIDENCE_MODE_BINDING")
    _need(type(evidence["chronology"]) is str, "CHRONOLOGY")
    namespace = _namespace(request["identity"])
    for name in ("execution", "publisher", "artifact"):
        _need(
            _namespace(_reference(evidence[name])) == namespace, "EXECUTION_NAMESPACE"
        )
    _need(
        _text(evidence["attempt"]) == _text(evidence["latest_attempt"]),
        "ATTEMPT_NOT_CURRENT",
    )
    for name in ("source_sha256", "archive_sha256"):
        _sha(evidence[name])
    _need(
        evidence["status"] == "COMPLETED" and evidence["coverage"] == "COMPLETE",
        "INCOMPLETE_EVIDENCE",
    )
    for name in ("started_at", "completed_at", "expires_at"):
        _time(evidence[name])
    if evidence["accountable_review"] is not None:
        _reference(evidence["accountable_review"])
    _outcome(evidence["outcome"])
    _guarantees(evidence["guarantees"], required)
    return evidence


def _candidate(value: Any, request: dict[str, Any]) -> dict[str, Any]:
    candidate = _mapping(
        value,
        {
            "parent_commit",
            "parent_tree",
            "tree",
            "observed_at",
            "changed_paths",
            "evidence_files",
        },
    )
    for key in ("parent_commit", "parent_tree"):
        _need(
            _text(candidate[key]) == request["material"][key],
            "CANDIDATE_PARENT_BINDING",
        )
    tree = _text(candidate["tree"])
    _time(candidate["observed_at"])
    changed = _paths(candidate["changed_paths"])
    if changed:
        _need(tree != request["material"]["parent_tree"], "CANDIDATE_TREE_UNCHANGED")
    _need(changed <= set(request["candidate_paths"]), "CANDIDATE_PATH_SCOPE")
    evidence_files = _files(candidate["evidence_files"])
    _need(
        evidence_files == request["material"]["evidence_files"],
        "CANDIDATE_EVIDENCE_BINDING",
    )
    # These files describe the admitted evidence delta, not every test already
    # present in the parent. The final diff must carry that same retained delta.
    _need(set(evidence_files) <= changed, "CANDIDATE_EVIDENCE_DELTA_MISSING")
    return candidate


def _mode_relation(request: dict[str, Any], evidence: dict[str, Any]) -> None:
    mode = request["mode"]
    expected, actual = _outcome(request["outcome"]), _outcome(evidence["outcome"])
    _need(expected == actual, "ORACLE_RESULT_MISMATCH")
    exit_code, cases = actual
    if mode == "STRUCTURAL":
        _need(
            request["criterion"] == "NON_EXECUTABLE" and exit_code == 0 and not cases,
            "STRUCTURAL_NOT_EXECUTABLE",
        )
        _need(evidence["accountable_review"] is not None, "ACCOUNTABLE_REVIEW_REQUIRED")
    else:
        _need(
            request["criterion"] == "EXECUTABLE"
            and cases
            and request["material"]["evidence_files"],
            "NONVACUITY_REQUIRED",
        )
        for outcome, cause in cases.values():
            _need(
                (outcome == "PASS" and cause == "NONE")
                or (
                    outcome == "FAIL"
                    and cause in {"ASSERTION_FAILURE", "EXPLICIT_FAILURE"}
                ),
                "NON_BEHAVIORAL_RESULT",
            )
        failures = sum(outcome == "FAIL" for outcome, _ in cases.values())
        if mode == "CHARACTERIZATION":
            _need(exit_code == 0 and failures == 0, "CHARACTERIZATION_REQUIRES_SUCCESS")
        elif mode == "RED":
            _need(exit_code == 1 and failures > 0, "RED_REQUIRES_FAILURE")
        else:
            _need(exit_code == (1 if failures else 0), "EMERGENCY_RESULT")
    if mode == "EMERGENCY_POST_EVENT":
        _need(
            request["change_class"] == "emergency"
            and request["follow_up"] is not None
            and evidence["chronology"] == "EMERGENCY_POST_EVENT",
            "EMERGENCY_ADMISSION",
        )
    else:
        _need(
            request["change_class"] != "emergency"
            and evidence["chronology"] == "PRE_CHANGE",
            "PRE_CHANGE_REQUIRED",
        )


def _time_relation(
    now: int,
    policy: dict[str, Any],
    request: dict[str, Any],
    admission: dict[str, Any],
    evidence: dict[str, Any],
    candidate: dict[str, Any],
) -> None:
    _need(
        request["valid_from"]
        <= admission["observed_at"]
        <= evidence["started_at"]
        <= evidence["completed_at"]
        <= now
        < request["valid_until"],
        "OBSERVATION_ORDER",
    )
    _need(now < evidence["expires_at"], "EVIDENCE_EXPIRED")
    _need(now - evidence["completed_at"] <= policy["max_age_seconds"], "EVIDENCE_STALE")
    _need(request["valid_from"] <= candidate["observed_at"] <= now, "CANDIDATE_TIME")
    if request["mode"] != "EMERGENCY_POST_EVENT":
        _need(
            evidence["completed_at"] <= candidate["observed_at"],
            "EVIDENCE_AFTER_CANDIDATE",
        )


def _result(
    status: str, reasons: list[str], request_sha256: str | None = None
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "status": status,
        "reasons": reasons,
        "request_sha256": request_sha256,
        "authentication": "NOT_ESTABLISHED",
        "compliance": False,
        "vf0_active": False,
    }


def evaluate(document: object) -> dict[str, Any]:
    """Check a supplied relation; MATCH must never be used as authentication."""
    try:
        data = _mapping(
            _copy_json(document),
            {
                "schema",
                "now",
                "policy",
                "request",
                "admission",
                "evidence",
                "candidate",
            },
        )
        _need(data["schema"] == SCHEMA, "SCHEMA")
        now = _time(data["now"])
        policy, required = _policy(data["policy"])
        request = _request(data["request"], policy)
        admission = _admission(data["admission"], request, required)
        evidence = _evidence(data["evidence"], request, admission, required)
        candidate = _candidate(data["candidate"], request)
        _mode_relation(request, evidence)
        _time_relation(now, policy, request, admission, evidence, candidate)
        return _result("MATCH", [], _digest(request))
    except _Invalid as exc:
        return _result("REJECTED", [str(exc)])
    except (RecursionError, ValueError, TypeError, OverflowError):
        return _result("REJECTED", ["MALFORMED_INPUT"])


def evaluate_json(raw: bytes) -> dict[str, Any]:
    """Parse bounded closed JSON data, never an authenticated observation."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out = {}
        for key, value in items:
            _need(key not in out, "DUPLICATE_JSON_KEY")
            out[key] = value
        return out

    def unsupported_number(value: str) -> Any:
        raise _Invalid("UNSUPPORTED_JSON_NUMBER")

    try:
        _need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "INPUT_SIZE")
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=unsupported_number,
            parse_float=unsupported_number,
        )
        return evaluate(value)
    except _Invalid as exc:
        return _result("REJECTED", [str(exc)])
    except (RecursionError, ValueError, TypeError, OverflowError):
        return _result("REJECTED", ["MALFORMED_JSON"])


def resolve_links(
    subject: object, links: object
) -> tuple[list[dict[str, Any]], list[str]]:
    """Filter navigation independently; query-bearing URLs are not retained."""
    retained: list[dict[str, Any]] = []
    rejected: list[str] = []
    try:
        expected = _reference(_copy_json(subject))
        values = _copy_json(links)
        _need(type(values) is list and len(values) <= 32, "LINK_SET")
        for value in values:
            try:
                link = _mapping(value, {"subject", "label", "relation", "url"})
                _need(_reference(link["subject"]) == expected, "LINK_SUBJECT")
                label = _text(link["label"], 80)
                _need(all(c.isalnum() or c in " .:_()/-" for c in label), "LINK_LABEL")
                _need(
                    link["relation"] in {"run", "review", "approve", "report"},
                    "LINK_RELATION",
                )
                url = _text(link["url"], 2048)
                _need(
                    all(32 < ord(c) < 127 for c in url) and "\\" not in url, "LINK_URL"
                )
                parts = urlsplit(url)
                _need(
                    parts.scheme == "https"
                    and parts.hostname
                    and not parts.username
                    and not parts.password
                    and not parts.query
                    and parts.port in {None, 443},
                    "LINK_URL",
                )
                retained.append(link)
            except _Invalid as exc:
                rejected.append(str(exc))
            except (ValueError, TypeError):
                rejected.append("LINK_URL")
        return retained, rejected
    except _Invalid as exc:
        return [], [str(exc)]
    except (RecursionError, ValueError, TypeError, OverflowError):
        return [], ["MALFORMED_LINKS"]
