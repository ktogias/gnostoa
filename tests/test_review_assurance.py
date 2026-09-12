from __future__ import annotations

import ast
import copy
import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "review_check"
CASES = FIX / "cases.json"
EXPECTED = FIX / "expected.json"
RETAINED = FIX / "red-observed-output.json"
CONTRACT = ROOT / "knowledge" / "assessments" / "11-review-assurance-red-contract.md"
CLI = ROOT / "tools" / "cli.py"
PRODUCTION = (
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
RID = tuple(f"R{i:02d}" for i in range(1, 46))
MAX_BYTES = 65536


def canon(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode()


def digest(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load(path: Path):
    return json.loads(path.read_text())


def parent_at(root, path):
    cur = root
    for part in path[:-1]:
        cur = cur[int(part)] if isinstance(cur, list) else cur[str(part)]
    return cur, path[-1]


def mutate(doc, spec):
    name, op = str(spec["target"]), str(spec["op"])
    if op == "replace_root":
        doc[name] = copy.deepcopy(spec["value"])
        return
    target, path = doc[name], list(spec["path"])
    if op == "append":
        cur = target
        for part in path:
            cur = cur[int(part)] if isinstance(cur, list) else cur[str(part)]
        cur.append(copy.deepcopy(spec["value"]))
        return
    parent, key = parent_at(target, path)
    key = int(key) if isinstance(parent, list) else str(key)
    if op == "set":
        parent[key] = copy.deepcopy(spec["value"])
    elif op == "delete":
        if isinstance(parent, list):
            del parent[key]
        else:
            parent.pop(key, None)
    else:
        raise AssertionError(f"unsupported fixture mutation {op!r}")


def documents(cases, case):
    bound = copy.deepcopy(cases["base"])
    for spec in case.get("mutations", []):
        mutate(bound, spec)
    inp, policy = bound["input"], bound["policy"]
    flags = case.get("flags", {})
    if isinstance(inp, dict):
        ctx = inp.get("evaluation_context")
        if isinstance(ctx, dict) and ctx.get("mode") == "historical_replay":
            ctx.setdefault("fixture_only", True)
    if isinstance(inp, dict) and isinstance(policy, dict):
        if not flags.get("freeze_policy_digest"):
            inp["authority"]["policy_digest"] = digest(policy)
        if not flags.get("freeze_qualification_digest"):
            inp["authority"]["qualification_snapshot_digest"] = digest(
                inp["qualification_snapshot"]
            )
    return inp, policy


def refresh_qualification(inp):
    inp["authority"]["qualification_snapshot_digest"] = digest(
        inp["qualification_snapshot"]
    )


def variants(case_id, inp, policy):
    out = [("default", inp, policy)]
    if not isinstance(inp, dict):
        return out
    if case_id == "R04":
        weakened = copy.deepcopy(policy)
        weakened["review_requirement"] = "none"
        out.append(("weakened_policy_digest_mismatch", copy.deepcopy(inp), weakened))
    elif case_id == "R08":
        collection = copy.deepcopy(inp)
        collection["evidence_set"]["observations"][0]["observed_at"] = (
            "2026-09-12T00:00:00Z"
        )
        collection["evidence_set"]["sources"][0]["observed_at"] = "2026-09-12T00:11:00Z"
        qualification = copy.deepcopy(inp)
        qualification["evidence_set"]["observations"][0]["observed_at"] = (
            "2026-09-12T00:00:00Z"
        )
        qualification["qualification_snapshot"]["observed_at"] = "2026-09-12T00:11:00Z"
        for entry in qualification["qualification_snapshot"]["entries"]:
            entry["observed_at"] = "2026-09-12T00:11:00Z"
        refresh_qualification(qualification)
        out += [
            ("future_required_collection", collection, policy),
            ("future_qualification", qualification, policy),
        ]
    elif case_id == "R10":
        candidate = copy.deepcopy(inp)
        candidate["acquired_judge"]["source_revision"] = candidate["authority"][
            "expected_judge"
        ]["source_revision"]
        candidate["evaluation_context"].pop("fixture_only", None)
        out.append(("fixture_marker_missing", candidate, policy))
    elif case_id == "R12":
        for status in ("RATE_LIMITED", "UNAVAILABLE", "ERROR"):
            candidate = copy.deepcopy(inp)
            candidate["evidence_set"]["sources"][0]["status"] = status
            out.append((f"required_{status.lower()}", candidate, policy))
    elif case_id == "R18":
        unestablished = copy.deepcopy(inp)
        for entry in unestablished["qualification_snapshot"]["entries"]:
            entry["status"] = "unestablished"
        refresh_qualification(unestablished)
        expired = copy.deepcopy(inp)
        expired["qualification_snapshot"]["observed_at"] = "2026-09-10T00:00:00Z"
        for entry in expired["qualification_snapshot"]["entries"]:
            entry.update(status="established", observed_at="2026-09-10T00:00:00Z")
        refresh_qualification(expired)
        out += [
            ("unestablished", unestablished, policy),
            ("freshness_expired", expired, policy),
        ]
    elif case_id == "R36":
        for status in ("deprecated", "unknown"):
            candidate = copy.deepcopy(inp)
            candidate["acquired_judge"]["status"] = status
            out.append((f"judge_{status}", candidate, policy))
    elif case_id == "R38":
        changes = (
            ("runtime_image", "ghcr.io/ktogias/gnostoa@sha256:" + "3" * 64),
            ("public_surface_digest", "sha256:" + "4" * 64),
            ("supported_input_schema_versions", ["9.9"]),
        )
        for field, value in changes:
            candidate = copy.deepcopy(inp)
            candidate["acquired_judge"] = copy.deepcopy(
                candidate["authority"]["expected_judge"]
            )
            candidate["acquired_judge"][field] = value
            out.append((f"judge_{field}_mismatch", candidate, policy))
    return out


def wanted(expected, name):
    selected = expected.get("variants", {}).get(name)
    return selected if isinstance(selected, dict) else expected


def cli_has_route(text: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and any(
            isinstance(key, ast.Constant) and key.value == "review-check"
            for key in node.keys
        ):
            return True
        if isinstance(node, ast.alias) and node.name == "review_check":
            return True
        if isinstance(node, ast.Name) and node.id == "review_check":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "review_check":
            return True
    return False


def production_absent() -> bool:
    if any((ROOT / path).exists() for path in PRODUCTION):
        return False
    try:
        return not cli_has_route(CLI.read_text())
    except OSError:
        return False


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def receipt_fields() -> dict[str, str]:
    try:
        text = CONTRACT.read_text()
    except OSError:
        return {}
    heading = "### RED receipt — must be completed before production handoff"
    if heading not in text:
        return {}
    tail = text.split(heading, 1)[1]
    start = tail.find("```text")
    end = tail.find("```", start + 7)
    if start < 0 or end < 0:
        return {}
    fields = {}
    for line in tail[start + 7 : end].splitlines():
        if line and not line[0].isspace() and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.split("#", 1)[0].strip()
    return fields


def receipt_payload(ok: bool, errors: list[str]) -> bytes:
    return canon(
        {
            "schema": "gnostoa-review-assurance-red-receipt-check/v1",
            "ok": ok,
            "errors": sorted(errors),
        }
    )


def verify_receipt() -> int:
    fields = receipt_fields()
    required = (
        "red_commit",
        "command",
        "exit_code",
        "stdout_bytes",
        "bounded_output_sha256",
        "red_output_artifact",
        "stderr_bytes",
        "red_harness_blob",
        "red_cases_blob",
        "red_expected_blob",
        "red_output_blob",
    )
    errors = [
        f"receipt:{key}:pending"
        for key in required
        if not fields.get(key) or fields[key] == "PENDING"
    ]
    if errors:
        sys.stdout.buffer.write(receipt_payload(False, errors))
        return 2
    if fields["command"] != "python tests/test_review_assurance.py":
        errors.append("receipt:command")
    if fields["red_output_artifact"] != (
        "tests/fixtures/review_check/red-observed-output.json"
    ):
        errors.append("receipt:red-output-artifact")
    if len(fields["red_commit"]) != 40 or any(
        c not in "0123456789abcdef" for c in fields["red_commit"]
    ):
        errors.append("receipt:red-commit")
    blobs = {
        "red_harness_blob": ROOT / "tests" / "test_review_assurance.py",
        "red_cases_blob": CASES,
        "red_expected_blob": EXPECTED,
        "red_output_blob": RETAINED,
    }
    for key, path in blobs.items():
        try:
            if git_blob(path) != fields[key]:
                errors.append(f"receipt:{key}:mismatch")
        except OSError:
            errors.append(f"receipt:{key}:missing")
    try:
        expected_exit, stdout_bytes, stderr_bytes = map(
            int,
            (fields["exit_code"], fields["stdout_bytes"], fields["stderr_bytes"]),
        )
    except ValueError:
        expected_exit, stdout_bytes, stderr_bytes = -999, -1, -1
        errors.append("receipt:numeric-field")
    run = subprocess.run(
        ["python", "tests/test_review_assurance.py"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if run.returncode != expected_exit:
        errors.append("observed:exit-code")
    if len(run.stdout) != stdout_bytes:
        errors.append("observed:stdout-bytes")
    if len(run.stderr) != stderr_bytes or run.stderr:
        errors.append("observed:stderr")
    if len(run.stdout) > MAX_BYTES:
        errors.append("observed:stdout-limit")
    try:
        retained = RETAINED.read_bytes()
    except OSError:
        retained = b""
        errors.append("observed:retained-output-missing")
    if run.stdout != retained:
        errors.append("observed:retained-output-mismatch")
    if (
        "sha256:" + hashlib.sha256(run.stdout).hexdigest()
        != fields["bounded_output_sha256"]
    ):
        errors.append("observed:sha256")
    try:
        report = json.loads(run.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append("observed:report-json")
    else:
        if report.get("phase") != "RED":
            errors.append("observed:phase")
        if report.get("production_paths_absent") is not True:
            errors.append("observed:production-paths")
        if sorted(report.get("required_case_ids", [])) != sorted(RID):
            errors.append("observed:required-case-ids")
    sys.stdout.buffer.write(receipt_payload(not errors, errors))
    return 0 if not errors else 2


def assert_result(case_id, expected, code, payload):
    problems = []
    if code != expected["exit_code"]:
        problems.append(f"{case_id}:exit")
    if "error_code" in expected:
        if (
            not isinstance(payload, dict)
            or payload.get("error", {}).get("code") != expected["error_code"]
        ):
            problems.append(f"{case_id}:error-code")
        return problems
    if "outcome" in expected and (
        not isinstance(payload, dict) or payload.get("outcome") != expected["outcome"]
    ):
        problems.append(f"{case_id}:outcome")
    if "reason" in expected and (
        not isinstance(payload, dict) or payload.get("reason") != expected["reason"]
    ):
        problems.append(f"{case_id}:reason")
    checks = expected.get("assertions", {})
    if isinstance(payload, dict):
        if "binding" in checks and payload.get("binding") is not checks["binding"]:
            problems.append(f"{case_id}:binding")
        for field in checks.get("absent_fields", []):
            if field in payload:
                problems.append(f"{case_id}:unexpected-{field}")
        if (
            "distinct_domains" in checks
            and payload.get("quorum", {}).get("distinct_domains")
            != checks["distinct_domains"]
        ):
            problems.append(f"{case_id}:domains")
        if (
            "minimum_assessments" in checks
            and len(payload.get("assessments", [])) < checks["minimum_assessments"]
        ):
            problems.append(f"{case_id}:assessments")
        if "assessment_ids" in checks:
            seen = {
                item.get("observation_id") for item in payload.get("assessments", [])
            }
            if not set(checks["assessment_ids"]).issubset(seen):
                problems.append(f"{case_id}:assessment-ids")
    return problems


def run_green(cases, expected):
    from tools import review_check

    by_id = {case["id"]: case for case in cases["cases"]}
    problems = []
    for case_id in RID:
        case = by_id[case_id]
        if case.get("flags", {}).get("special") == "exit_mapping":
            for source, code in {
                "R02": 0,
                "R24": 1,
                "R44": 2,
                "R01": 3,
                "R28": 4,
            }.items():
                inp, policy = documents(cases, by_id[source])
                got, _ = review_check.evaluate_documents(inp, policy)
                if got != code:
                    problems.append(f"R41:{source}")
            continue
        inp, policy = documents(cases, case)
        for name, variant_inp, variant_policy in variants(case_id, inp, policy):
            if case.get("flags", {}).get("special") == "no_network":
                with mock.patch.object(
                    socket,
                    "socket",
                    side_effect=AssertionError("network access forbidden"),
                ):
                    code, payload = review_check.evaluate_documents(
                        variant_inp, variant_policy
                    )
            else:
                code, payload = review_check.evaluate_documents(
                    variant_inp, variant_policy
                )
            label = case_id if name == "default" else f"{case_id}:{name}"
            problems += assert_result(
                label, wanted(expected[case_id], name), code, payload
            )
            if case.get("flags", {}).get("special") == "canonical_json":
                canonical = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                if review_check.canonical_json(payload) != canonical:
                    problems.append(f"{label}:canonical-json")
    return sorted(set(problems))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--verify-receipt"]:
        return verify_receipt()
    if args:
        sys.stdout.buffer.write(
            receipt_payload(False, ["invocation:unsupported-arguments"])
        )
        return 2
    cases, expected_doc = load(CASES), load(EXPECTED)
    case_ids = {case["id"] for case in cases["cases"]}
    expected_ids = set(expected_doc["expected"])
    missing = sorted((set(RID) - case_ids) | (set(RID) - expected_ids))
    extras = sorted((case_ids | expected_ids) - set(RID))
    absent = production_absent()
    if missing or extras:
        failing = list(RID)
        unexpected = [f"FIXTURE:{x}" for x in missing + extras]
        phase = "RED" if absent else "GREEN"
    elif absent:
        failing, unexpected, phase = list(RID), [], "RED"
    else:
        failing = run_green(cases, expected_doc["expected"])
        unexpected = []
        phase = "GREEN"
    output = canon(
        {
            "schema": "gnostoa-review-assurance-red/v1",
            "phase": phase,
            "required_case_ids": list(RID),
            "failing_case_ids": failing,
            "unexpected_case_ids": unexpected,
            "production_paths_absent": absent,
        }
    )
    if len(output) > MAX_BYTES:
        return 2
    sys.stdout.buffer.write(output)
    sys.stdout.flush()
    return 1 if failing or unexpected or absent else 0


if __name__ == "__main__":
    raise SystemExit(main())
