from __future__ import annotations

import copy
import hashlib
import json
import socket
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "review_check"
CASES_PATH = FIXTURES / "cases.json"
EXPECTED_PATH = FIXTURES / "expected.json"

PRODUCTION_PATHS = (
    "schemas/review-check-input.schema.json",
    "schemas/review-policy.schema.json",
    "schemas/review-gate-result.schema.json",
    "core/review-policy.yaml",
    "policy/review-policy.yaml",
    "tools/review_model.py",
    "tools/review_policy.py",
    "tools/review_evaluate.py",
    "tools/review_adapter_file.py",
    "tools/review_check.py",
)
REQUIRED_CASE_IDS = tuple(f"R{i:02d}" for i in range(1, 46))
MAX_REPORT_BYTES = 65536
CLI_PATH = ROOT / "tools" / "cli.py"
CLI_ROUTE_MARKERS = ('"review-check"', "review_check")


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_digest(value: object) -> str:
    data = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _load_fixture(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _navigate(
    root: object,
    path: list[object],
    *,
    parent: bool = False,
) -> tuple[object, object | None]:
    if not path:
        return root, None
    current = root
    limit = len(path) - 1 if parent else len(path)
    for part in path[:limit]:
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[str(part)]
    return current, path[-1] if parent else None


def _apply_mutation(
    document: dict[str, object],
    mutation: dict[str, object],
) -> None:
    target_name = str(mutation["target"])
    operation = str(mutation["op"])
    if operation == "replace_root":
        document[target_name] = copy.deepcopy(mutation["value"])
        return

    target = document[target_name]
    path = list(mutation["path"])
    parent, key = _navigate(target, path, parent=True)
    if operation == "set":
        if isinstance(parent, list):
            parent[int(key)] = copy.deepcopy(mutation["value"])
        else:
            parent[str(key)] = copy.deepcopy(mutation["value"])
    elif operation == "delete":
        if isinstance(parent, list):
            del parent[int(key)]
        else:
            parent.pop(str(key), None)
    elif operation == "append":
        container, _ = _navigate(target, path, parent=False)
        if not isinstance(container, list):
            raise AssertionError(f"append target is not a list: {path!r}")
        container.append(copy.deepcopy(mutation["value"]))
    else:
        raise AssertionError(f"unsupported fixture mutation {operation!r}")


def _documents(
    cases_document: dict[str, object],
    case: dict[str, object],
) -> tuple[object, object]:
    bound = copy.deepcopy(cases_document["base"])
    for mutation in case.get("mutations", []):
        _apply_mutation(bound, mutation)

    input_document = bound["input"]
    policy_document = bound["policy"]
    flags = case.get("flags", {})
    if isinstance(input_document, dict):
        context = input_document.get("evaluation_context")
        if isinstance(context, dict) and context.get("mode") == "historical_replay":
            context.setdefault("fixture_only", True)
    if isinstance(input_document, dict) and isinstance(policy_document, dict):
        if not flags.get("freeze_policy_digest"):
            input_document["authority"]["policy_digest"] = _canonical_digest(
                policy_document
            )
        if not flags.get("freeze_qualification_digest"):
            input_document["authority"]["qualification_snapshot_digest"] = (
                _canonical_digest(input_document["qualification_snapshot"])
            )
    return input_document, policy_document


def _refresh_qualification_digest(input_document: dict[str, object]) -> None:
    input_document["authority"]["qualification_snapshot_digest"] = _canonical_digest(
        input_document["qualification_snapshot"]
    )


def _case_variants(
    case_id: str,
    input_document: object,
    policy_document: object,
) -> list[tuple[str, object, object]]:
    variants: list[tuple[str, object, object]] = [
        ("default", input_document, policy_document)
    ]
    if not isinstance(input_document, dict):
        return variants

    if case_id == "R08":
        collection = copy.deepcopy(input_document)
        collection["evidence_set"]["observations"][0]["observed_at"] = (
            "2026-09-12T00:00:00Z"
        )
        collection["evidence_set"]["sources"][0]["observed_at"] = "2026-09-12T00:11:00Z"
        qualification = copy.deepcopy(input_document)
        qualification["evidence_set"]["observations"][0]["observed_at"] = (
            "2026-09-12T00:00:00Z"
        )
        qualification["qualification_snapshot"]["observed_at"] = "2026-09-12T00:11:00Z"
        for entry in qualification["qualification_snapshot"]["entries"]:
            entry["observed_at"] = "2026-09-12T00:11:00Z"
        _refresh_qualification_digest(qualification)
        variants.extend(
            [
                ("future_required_collection", collection, policy_document),
                ("future_qualification", qualification, policy_document),
            ]
        )
    elif case_id == "R10":
        missing_marker = copy.deepcopy(input_document)
        missing_marker["acquired_judge"]["source_revision"] = missing_marker[
            "authority"
        ]["expected_judge"]["source_revision"]
        missing_marker["evaluation_context"].pop("fixture_only", None)
        variants.append(("fixture_marker_missing", missing_marker, policy_document))
    elif case_id == "R12":
        for status in ("RATE_LIMITED", "UNAVAILABLE", "ERROR"):
            candidate = copy.deepcopy(input_document)
            candidate["evidence_set"]["sources"][0]["status"] = status
            variants.append((f"required_{status.lower()}", candidate, policy_document))
    elif case_id == "R18":
        unestablished = copy.deepcopy(input_document)
        for entry in unestablished["qualification_snapshot"]["entries"]:
            entry["status"] = "unestablished"
        _refresh_qualification_digest(unestablished)

        expired = copy.deepcopy(input_document)
        expired["qualification_snapshot"]["observed_at"] = "2026-09-10T00:00:00Z"
        for entry in expired["qualification_snapshot"]["entries"]:
            entry["status"] = "established"
            entry["observed_at"] = "2026-09-10T00:00:00Z"
        _refresh_qualification_digest(expired)
        variants.extend(
            [
                ("unestablished", unestablished, policy_document),
                ("freshness_expired", expired, policy_document),
            ]
        )
    return variants


def _variant_expected(
    expected: dict[str, object],
    variant: str,
) -> dict[str, object]:
    variant_map = expected.get("variants", {})
    if isinstance(variant_map, dict) and variant in variant_map:
        selected = variant_map[variant]
        if isinstance(selected, dict):
            return selected
    return expected


def _production_surfaces_absent() -> bool:
    if any((ROOT / relative).exists() for relative in PRODUCTION_PATHS):
        return False
    try:
        cli_text = CLI_PATH.read_text(encoding="utf-8")
    except OSError:
        return False
    return not any(marker in cli_text for marker in CLI_ROUTE_MARKERS)


def _assert_common(
    case_id: str,
    expected: dict[str, object],
    exit_code: int,
    payload: object,
) -> list[str]:
    problems: list[str] = []
    if exit_code != expected["exit_code"]:
        problems.append(f"{case_id}:exit")

    if "error_code" in expected:
        if (
            not isinstance(payload, dict)
            or payload.get("error", {}).get("code") != expected["error_code"]
        ):
            problems.append(f"{case_id}:error-code")
        return problems

    if "outcome" in expected:
        if (
            not isinstance(payload, dict)
            or payload.get("outcome") != expected["outcome"]
        ):
            problems.append(f"{case_id}:outcome")
    if "reason" in expected:
        if not isinstance(payload, dict) or payload.get("reason") != expected["reason"]:
            problems.append(f"{case_id}:reason")

    assertions = expected.get("assertions") or {}
    if isinstance(payload, dict):
        if (
            "binding" in assertions
            and payload.get("binding") is not assertions["binding"]
        ):
            problems.append(f"{case_id}:binding")
        for field in assertions.get("absent_fields", []):
            if field in payload:
                problems.append(f"{case_id}:unexpected-{field}")
        if "distinct_domains" in assertions:
            if (
                payload.get("quorum", {}).get("distinct_domains")
                != assertions["distinct_domains"]
            ):
                problems.append(f"{case_id}:domains")
        if "minimum_assessments" in assertions:
            if len(payload.get("assessments", [])) < assertions["minimum_assessments"]:
                problems.append(f"{case_id}:assessments")
        if "assessment_ids" in assertions:
            observed = {
                assessment.get("observation_id")
                for assessment in payload.get("assessments", [])
            }
            if not set(assertions["assessment_ids"]).issubset(observed):
                problems.append(f"{case_id}:assessment-ids")
    return problems


def _run_special(
    review_check: object,
    case_id: str,
    cases_document: dict[str, object],
) -> list[str]:
    if case_id != "R41":
        return []

    mapping = {"R02": 0, "R24": 1, "R44": 2, "R01": 3, "R28": 4}
    problems: list[str] = []
    cases_by_id = {case["id"]: case for case in cases_document["cases"]}
    for source_id, wanted in mapping.items():
        input_document, policy_document = _documents(
            cases_document,
            cases_by_id[source_id],
        )
        got, _payload = review_check.evaluate_documents(
            input_document,
            policy_document,
        )
        if got != wanted:
            problems.append(f"R41:{source_id}")
    return problems


def _run_green(
    cases_document: dict[str, object],
    expected_document: dict[str, object],
) -> list[str]:
    from tools import review_check

    cases = {case["id"]: case for case in cases_document["cases"]}
    expected = expected_document["expected"]
    problems: list[str] = []
    for case_id in REQUIRED_CASE_IDS:
        case = cases[case_id]
        if case.get("flags", {}).get("special") == "exit_mapping":
            problems.extend(_run_special(review_check, case_id, cases_document))
            continue

        input_document, policy_document = _documents(cases_document, case)
        for variant, variant_input, variant_policy in _case_variants(
            case_id, input_document, policy_document
        ):
            if case.get("flags", {}).get("special") == "no_network":
                with mock.patch.object(
                    socket,
                    "socket",
                    side_effect=AssertionError("network access forbidden"),
                ):
                    exit_code, payload = review_check.evaluate_documents(
                        variant_input,
                        variant_policy,
                    )
            else:
                exit_code, payload = review_check.evaluate_documents(
                    variant_input,
                    variant_policy,
                )

            display_id = case_id if variant == "default" else f"{case_id}:{variant}"
            problems.extend(
                _assert_common(
                    display_id,
                    _variant_expected(expected[case_id], variant),
                    exit_code,
                    payload,
                )
            )
            if case.get("flags", {}).get("special") == "canonical_json":
                rendered = review_check.canonical_json(payload)
                wanted = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                if rendered != wanted:
                    problems.append(f"{display_id}:canonical-json")
    return sorted(set(problems))


def main() -> int:
    cases_document = _load_fixture(CASES_PATH)
    expected_document = _load_fixture(EXPECTED_PATH)
    case_ids = sorted(case["id"] for case in cases_document["cases"])
    expected_ids = sorted(expected_document["expected"])
    missing = sorted(
        (set(REQUIRED_CASE_IDS) - set(case_ids))
        | (set(REQUIRED_CASE_IDS) - set(expected_ids))
    )
    extras = sorted((set(case_ids) | set(expected_ids)) - set(REQUIRED_CASE_IDS))
    production_absent = _production_surfaces_absent()

    if missing or extras:
        failing = list(REQUIRED_CASE_IDS)
        unexpected = [f"FIXTURE:{item}" for item in missing + extras]
        phase = "RED" if production_absent else "GREEN"
    elif production_absent:
        failing = list(REQUIRED_CASE_IDS)
        unexpected = []
        phase = "RED"
    else:
        failing = _run_green(cases_document, expected_document)
        unexpected = []
        phase = "GREEN"

    report = {
        "schema": "gnostoa-review-assurance-red/v1",
        "phase": phase,
        "required_case_ids": list(REQUIRED_CASE_IDS),
        "failing_case_ids": failing,
        "unexpected_case_ids": unexpected,
        "production_paths_absent": production_absent,
    }
    output = _canonical_json_bytes(report)
    if len(output) > MAX_REPORT_BYTES:
        return 2
    sys.stdout.buffer.write(output)
    sys.stdout.flush()
    return 1 if failing or unexpected or production_absent else 0


if __name__ == "__main__":
    raise SystemExit(main())
