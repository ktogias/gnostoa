"""BASE and REFERENCE qualification, classified by cause rather than by count.

Runs the declared oracle against each materialised subject under explicit preflight
authority and compares the observed per-case outcome against the prospectively
frozen expectation. A collection or import failure can never satisfy a prospective
FAIL, and a base failure caused by something other than the declared discriminator
is a wrong-cause mismatch, not a match -- the Phase-D D1 false-match class.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from tools.capsule.identity import digest_of

MATCH = "MATCH"
COUNT_MISMATCH = "COUNT_MISMATCH"
WRONG_CAUSE = "WRONG_CAUSE"
INFRASTRUCTURE = "INFRASTRUCTURE"

LOCAL_PYTHON = "local-python"
OCI = "oci"
BACKENDS = (LOCAL_PYTHON, OCI)

# Exception types that mean the oracle never exercised the subject behaviour.
_INFRASTRUCTURE_ERRORS = frozenset(
    {
        "ImportError",
        "ModuleNotFoundError",
        "AttributeError",
        "SyntaxError",
        "NameError",
        "FileNotFoundError",
        "TypeError",
        "KeyboardInterrupt",
        "SystemExit",
        "GeneratorExit",
        "MemoryError",
        "RecursionError",
        "OSError",
        "BlockingIOError",
        "ChildProcessError",
        "ConnectionError",
        "BrokenPipeError",
        "ConnectionAbortedError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "FileExistsError",
        "InterruptedError",
        "IsADirectoryError",
        "NotADirectoryError",
        "PermissionError",
        "ProcessLookupError",
        "TimeoutError",
    }
)

_HARNESS = r"""
import importlib.util, json, sys, traceback

oracle_path, module_name = sys.argv[1], "phase_d_oracle"
spec = importlib.util.spec_from_file_location(module_name, oracle_path)
module = importlib.util.module_from_spec(spec)
report = {"collected": False, "cases": {}, "error": None}
try:
    spec.loader.exec_module(module)
except BaseException:
    report["error"] = traceback.format_exception_only(*sys.exc_info()[:2])[-1].strip()
    print(json.dumps(report))
    raise SystemExit(0)

report["collected"] = True
for name in sorted(n for n in dir(module) if n.startswith("test")):
    case = getattr(module, name)
    if not callable(case):
        continue
    try:
        case()
    except AssertionError as exc:
        report["cases"][name] = {"outcome": "failed", "error_type": "AssertionError",
                                 "message": str(exc)[:200]}
    except BaseException as exc:
        # Preserve exception ancestry before reducing the cause to a type name.
        # A caught exit or resource failure is not a completed behavioural test.
        if isinstance(
            exc, (KeyboardInterrupt, SystemExit, GeneratorExit,
                  MemoryError, RecursionError, OSError)
        ):
            report["error"] = type(exc).__name__ + ": " + str(exc)[:200]
            break
        report["cases"][name] = {"outcome": "failed", "error_type": type(exc).__name__,
                                 "message": str(exc)[:200]}
    else:
        report["cases"][name] = {"outcome": "passed", "error_type": None, "message": ""}
print(json.dumps(report))
"""


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_PYTEST_CASE = re.compile(
    r"^(?P<file>\S+)::(?P<case>[\w\[\]-]+)\s+(?P<outcome>PASSED|FAILED|ERROR)"
)
_PYTEST_CAUSE_NAME = (
    r"[A-Za-z_][\w.]*(?:Error|Exception|Warning)"
    r"|Failed|SystemExit|KeyboardInterrupt|GeneratorExit"
)
_PYTEST_ERROR = re.compile(rf"^E\s+(?P<error>{_PYTEST_CAUSE_NAME})\b", re.M)
_PYTEST_SHORT_FAILURE = re.compile(
    r"^FAILED\s+\S+::(?P<case>[\w\[\]-]+)\s+-\s+(?P<detail>.+)$",
    re.M,
)
_PYTEST_CAUSE = re.compile(rf"^(?P<error>{_PYTEST_CAUSE_NAME})\b")
_PYTEST_ASSERTION = re.compile(r"^E\s+assert\b", re.M)
_PYTEST_TERMINAL_SUMMARY = re.compile(
    r"^=+\s+(?P<body>.+?)\s+in\s+\d+(?:\.\d+)?s"
    r"(?:\s+\([^)]*\))?\s+=+$"
)
_PYTEST_SUMMARY_ITEM = re.compile(r"^(?P<count>\d+)\s+(?P<label>[A-Za-z][A-Za-z-]*)$")
_PYTEST_SUMMARY_LABELS = {
    "passed": "passed",
    "failed": "failed",
    "error": "errors",
    "errors": "errors",
    "warning": "warnings",
    "warnings": "warnings",
    "skipped": "skipped",
    "xfailed": "xfailed",
    "xpassed": "xpassed",
    "deselected": "deselected",
}
_UNSUPPORTED_PYTEST_OUTCOMES = frozenset(
    {"errors", "skipped", "xfailed", "xpassed", "deselected"}
)
_COLLECTION_FAILURE = re.compile(
    r"unrecognized arguments|ModuleNotFoundError|ImportError|INTERNALERROR|"
    r"error: unrecognized|no tests ran|ERROR: usage",
    re.I,
)


def _invalid_report(detail: str) -> dict[str, object]:
    return {"collected": False, "cases": {}, "error": detail}


def _parse_pytest_summary(stdout: str) -> tuple[dict[str, int] | None, str | None]:
    """Return the final pytest outcome summary, rejecting ambiguous vocabulary."""
    match = next(
        (
            candidate
            for line in reversed(stdout.splitlines())
            if (candidate := _PYTEST_TERMINAL_SUMMARY.fullmatch(line.strip()))
            is not None
        ),
        None,
    )
    if match is None:
        return None, "pytest terminal summary is missing"

    counts: dict[str, int] = {}
    for part in match["body"].split(","):
        item = _PYTEST_SUMMARY_ITEM.fullmatch(part.strip())
        if item is None:
            return None, f"pytest terminal summary is malformed: {match['body']!r}"
        count = int(item["count"])
        label = _PYTEST_SUMMARY_LABELS.get(item["label"].lower())
        if label is None:
            return None, (
                "pytest terminal summary contains unsupported outcome "
                f"{item['label']!r}"
            )
        if label in counts:
            return None, f"pytest terminal summary duplicates outcome {label!r}"
        counts[label] = count
    return counts, None


def _parse_pytest_report(stdout: str, exit_code: int) -> dict[str, object]:
    """Normalize a complete pytest process result into the local report shape."""
    normalized = _ANSI_ESCAPE.sub("", stdout)
    cases: dict[str, dict[str, str]] = {}
    pytest_errors: list[str] = []
    for line in normalized.splitlines():
        match = _PYTEST_CASE.match(line.strip())
        if match is None:
            continue
        name = match["case"]
        if name in cases:
            return _invalid_report(
                f"pytest reported duplicate outcome for case {name!r}"
            )
        raw_outcome = match["outcome"]
        if raw_outcome == "ERROR":
            pytest_errors.append(name)
            continue
        outcome = "passed" if raw_outcome == "PASSED" else "failed"
        cases[name] = {"outcome": outcome, "error_type": "", "message": ""}

    if pytest_errors:
        return _invalid_report(
            "pytest reported case-level ERROR for "
            f"{sorted(pytest_errors)} (exit {exit_code})"
        )

    if not cases:
        return _invalid_report(
            failure.group(0)
            if (failure := _COLLECTION_FAILURE.search(normalized)) is not None
            else f"no case outcome was collected (exit {exit_code})"
        )

    if exit_code not in {0, 1}:
        return _invalid_report(
            f"pytest process ended with unsupported exit {exit_code}"
        )

    summary, summary_error = _parse_pytest_summary(normalized)
    if summary is None:
        return _invalid_report(summary_error or "pytest terminal summary is invalid")

    unsupported = {
        label: count
        for label, count in summary.items()
        if label in _UNSUPPORTED_PYTEST_OUTCOMES and count
    }
    if unsupported:
        return _invalid_report(
            f"pytest terminal summary contains unsupported outcomes {unsupported}"
        )

    passed_count = sum(case["outcome"] == "passed" for case in cases.values())
    failed_count = sum(case["outcome"] == "failed" for case in cases.values())
    summary_passed = summary.get("passed", 0)
    summary_failed = summary.get("failed", 0)
    if summary_passed != passed_count or summary_failed != failed_count:
        return _invalid_report(
            "pytest terminal summary does not match parsed cases: "
            f"summary={summary_failed} failed/{summary_passed} passed, "
            f"cases={failed_count} failed/{passed_count} passed"
        )
    if exit_code == 0 and failed_count:
        return _invalid_report(
            f"pytest exit 0 contradicts {failed_count} reported failed case(s)"
        )
    if exit_code == 1 and not failed_count:
        return _invalid_report("pytest exit 1 has no reported failed case")

    # Traceback evidence has no case identity. It can conservatively reject a
    # run, but may identify a failure only when exactly one case failed.
    errors = set(_PYTEST_ERROR.findall(normalized))
    if any(error.rsplit(".", 1)[-1] in _INFRASTRUCTURE_ERRORS for error in errors):
        return _invalid_report(
            f"pytest reported infrastructure failure causes {sorted(errors)}"
        )

    causes: dict[str, str] = {}
    for failure in _PYTEST_SHORT_FAILURE.finditer(normalized):
        name = failure["case"]
        if name not in cases or cases[name]["outcome"] != "failed" or name in causes:
            return _invalid_report("pytest failure summary does not match parsed cases")
        detail = failure["detail"]
        cause = _PYTEST_CAUSE.match(detail)
        if cause is not None:
            causes[name] = cause["error"]
        elif re.match(r"assert\b", detail):
            causes[name] = "AssertionError"
        else:
            return _invalid_report(
                f"pytest failed case {name!r} has no recognizable failure cause"
            )

    for name, case in cases.items():
        if case["outcome"] != "failed":
            continue
        cause_name = causes.get(name)
        if cause_name is None and failed_count == 1:
            if len(errors) > 1:
                return _invalid_report(
                    f"pytest reported ambiguous failure causes {sorted(errors)}"
                )
            if errors:
                cause_name = next(iter(errors))
            elif _PYTEST_ASSERTION.search(normalized) is not None:
                cause_name = "AssertionError"
        if cause_name is None:
            return _invalid_report(
                f"pytest failed case {name!r} has no recognizable failure cause"
            )
        case["error_type"] = cause_name
    return {"collected": True, "cases": cases, "error": None}


def _run_oci(profile: Mapping[str, object], argv: Sequence[str]) -> dict[str, object]:
    """Execute the compiled invocation through the existing #164 runner.

    The runner owns OCI isolation, mounts, network mode and evidence capture. This
    backend adds no isolation logic of its own; it supplies a validated profile and
    reads the evidence the runner retains.
    """
    from tools.experiment.execution import run_profile_command

    evidence = Path(str(profile["evidence_root"]))
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(dict(profile), handle)
        profile_path = Path(handle.name)
    try:
        exit_code, payload = run_profile_command(profile_path, OCI, list(argv))
    finally:
        profile_path.unlink(missing_ok=True)

    if payload.get("status") == "BLOCKED":
        return {
            "collected": False,
            "cases": {},
            "error": f"runner blocked: {payload.get('reasons')}",
        }
    stdout_path = evidence / "run-stdout.log"
    stdout = stdout_path.read_text(errors="replace") if stdout_path.is_file() else ""
    return _parse_pytest_report(stdout, exit_code)


@dataclass(frozen=True, slots=True)
class SubjectOutcome:
    subject: str
    collected: bool
    passed: tuple[str, ...]
    failed: tuple[str, ...]
    error_types: Mapping[str, str]
    classification: str
    detail: str

    def as_json(self) -> dict[str, object]:
        return {
            "subject": self.subject,
            "collected": self.collected,
            "passed": list(self.passed),
            "failed": list(self.failed),
            "error_types": dict(self.error_types),
            "classification": self.classification,
            "detail": self.detail,
        }


RECEIPT_SCHEMA = "gnostoa-base-reference-qualification-receipt/v1"

# Identities a receipt must bind before it may stand in for a fresh qualification.
BOUND_IDENTITY_FIELDS = (
    "base_tree",
    "reference_tree",
    "oracle_sha256",
    "runtime_image",
    "harness_identity",
    "expectations_digest",
    "preparation_identity",
)


class ReceiptError(ValueError):
    """The receipt is malformed and must not be trusted."""


@dataclass(frozen=True, slots=True)
class QualificationReceipt:
    task: str
    backend: str
    base: SubjectOutcome
    reference: SubjectOutcome
    bound: Mapping[str, str] = field(default_factory=dict)

    @property
    def qualified(self) -> bool:
        return (
            self.base.classification == MATCH and self.reference.classification == MATCH
        )

    @property
    def identity(self) -> str:
        return digest_of(self.as_json())

    def covers(self, required: Mapping[str, str]) -> tuple[bool, list[str]]:
        """True only when every required identity is bound, equal and qualified."""
        mismatched = [
            name
            for name in BOUND_IDENTITY_FIELDS
            if self.bound.get(name) != required.get(name)
        ]
        return (not mismatched and self.qualified), mismatched

    def as_json(self) -> dict[str, object]:
        return {
            "schema": RECEIPT_SCHEMA,
            "task": self.task,
            "backend": self.backend,
            "base": self.base.as_json(),
            "reference": self.reference.as_json(),
            "bound": dict(self.bound),
            "qualified": self.qualified,
        }


def _outcome_from_json(payload: Mapping[str, object]) -> SubjectOutcome:
    return SubjectOutcome(
        subject=str(payload["subject"]),
        collected=bool(payload["collected"]),
        passed=tuple(
            str(item) for item in cast(Sequence[object], payload.get("passed") or [])
        ),
        failed=tuple(
            str(item) for item in cast(Sequence[object], payload.get("failed") or [])
        ),
        error_types={
            str(k): str(v)
            for k, v in cast(
                Mapping[object, object], payload.get("error_types") or {}
            ).items()
        },
        classification=str(payload["classification"]),
        detail=str(payload.get("detail", "")),
    )


def load_receipt(path: Path) -> QualificationReceipt:
    """Load a prior receipt, refusing anything that does not bind its identities."""
    payload = json.loads(path.read_text())
    if payload.get("schema") != RECEIPT_SCHEMA:
        raise ReceiptError(f"unsupported receipt schema {payload.get('schema')!r}")
    bound = payload.get("bound")
    if not isinstance(bound, dict):
        raise ReceiptError("receipt does not bind identities")
    missing = [name for name in BOUND_IDENTITY_FIELDS if not bound.get(name)]
    if missing:
        raise ReceiptError(f"receipt is missing bound identities: {missing}")
    return QualificationReceipt(
        task=str(payload["task"]),
        backend=str(payload["backend"]),
        base=_outcome_from_json(payload["base"]),
        reference=_outcome_from_json(payload["reference"]),
        bound={str(k): str(v) for k, v in bound.items()},
    )


def _run_local_python(
    subject: Path, oracle: Path, import_roots: Sequence[str]
) -> dict[str, object]:
    paths = [str(subject / root) for root in import_roots] + [str(subject)]
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _HARNESS, str(oracle)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(subject),
            env={
                "PYTHONPATH": ":".join(paths),
                "PATH": "/usr/bin:/bin",
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
    except subprocess.TimeoutExpired:
        return _invalid_report(
            "local qualification harness timed out after 120 seconds"
        )

    if completed.returncode != 0:
        detail = f"local qualification harness exited with exit {completed.returncode}"
        stderr = completed.stderr.strip()[:400]
        return _invalid_report(f"{detail}: {stderr}" if stderr else detail)

    stdout = completed.stdout.strip().splitlines()
    if not stdout:
        return _invalid_report(
            completed.stderr.strip()[:400]
            or "local qualification harness produced no report"
        )
    try:
        parsed: object = json.loads(stdout[-1])
    except json.JSONDecodeError:
        return _invalid_report("unparsable harness output")
    if not isinstance(parsed, dict):
        return _invalid_report("local qualification harness report is not an object")
    return cast(dict[str, object], parsed)


def _infrastructure_outcome(
    subject: str,
    detail: str,
    *,
    collected: bool = False,
    passed: Sequence[str] = (),
    failed: Sequence[str] = (),
    error_types: Mapping[str, str] | None = None,
) -> SubjectOutcome:
    return SubjectOutcome(
        subject=subject,
        collected=collected,
        passed=tuple(passed),
        failed=tuple(failed),
        error_types=dict(error_types or {}),
        classification=INFRASTRUCTURE,
        detail=detail,
    )


def _classify(
    subject: str,
    report: Mapping[str, object],
    expectation: Mapping[str, int],
    *,
    expected_failing: Sequence[str],
) -> SubjectOutcome:
    collected = report.get("collected")
    if collected is not True:
        error = report.get("error")
        detail = (
            error
            if isinstance(error, str) and error
            else "the oracle was never collected"
        )
        return _infrastructure_outcome(subject, detail)

    report_error = report.get("error")
    if report_error is not None and report_error != "":
        detail = (
            report_error
            if isinstance(report_error, str)
            else "qualification report carries a non-string error"
        )
        return _infrastructure_outcome(subject, detail, collected=True)

    raw_cases = report.get("cases")
    if not isinstance(raw_cases, Mapping):
        return _infrastructure_outcome(
            subject,
            "qualification report cases are not a mapping",
            collected=True,
        )
    if not raw_cases:
        return _infrastructure_outcome(
            subject,
            "qualification report collected no cases",
            collected=True,
        )

    cases: dict[str, dict[str, str]] = {}
    for raw_name, raw_case in raw_cases.items():
        if not isinstance(raw_name, str) or not raw_name:
            return _infrastructure_outcome(
                subject,
                "qualification report has an invalid case name",
                collected=True,
            )
        if not isinstance(raw_case, Mapping):
            return _infrastructure_outcome(
                subject,
                f"qualification report case {raw_name!r} is not an object",
                collected=True,
            )
        outcome = raw_case.get("outcome")
        if not isinstance(outcome, str) or outcome not in {"passed", "failed"}:
            return _infrastructure_outcome(
                subject,
                f"qualification report case {raw_name!r} has invalid outcome "
                f"{outcome!r}",
                collected=True,
            )
        raw_error_type = raw_case.get("error_type")
        if raw_error_type is not None and not isinstance(raw_error_type, str):
            return _infrastructure_outcome(
                subject,
                f"qualification report case {raw_name!r} has invalid error type",
                collected=True,
            )
        error_type = raw_error_type or ""
        raw_message = raw_case.get("message")
        if raw_message is not None and not isinstance(raw_message, str):
            return _infrastructure_outcome(
                subject,
                f"qualification report case {raw_name!r} has invalid message",
                collected=True,
            )
        if outcome == "passed" and error_type:
            return _infrastructure_outcome(
                subject,
                f"qualification report passed case {raw_name!r} carries an error",
                collected=True,
            )
        if outcome == "failed" and not error_type:
            return _infrastructure_outcome(
                subject,
                f"qualification report failed case {raw_name!r} has no cause",
                collected=True,
            )
        cases[raw_name] = {
            "outcome": outcome,
            "error_type": error_type,
            "message": raw_message or "",
        }

    passed = tuple(sorted(n for n, c in cases.items() if c["outcome"] == "passed"))
    failed = tuple(sorted(n for n, c in cases.items() if c["outcome"] == "failed"))
    error_types = {n: c["error_type"] for n, c in cases.items() if c["error_type"]}

    infrastructure = {
        n: t
        for n, t in error_types.items()
        if t.rsplit(".", 1)[-1] in _INFRASTRUCTURE_ERRORS
    }
    if infrastructure:
        return _infrastructure_outcome(
            subject,
            (
                f"{sorted(infrastructure)} failed with "
                f"{sorted(set(infrastructure.values()))}, which never exercised "
                "the declared behaviour"
            ),
            collected=True,
            passed=passed,
            failed=failed,
            error_types=error_types,
        )

    want_failed = int(expectation.get("failed", 0))
    want_passed = int(expectation.get("passed", 0))
    if len(failed) != want_failed or len(passed) != want_passed:
        return SubjectOutcome(
            subject=subject,
            collected=True,
            passed=passed,
            failed=failed,
            error_types=error_types,
            classification=COUNT_MISMATCH,
            detail=(
                f"expected {want_failed} failed / {want_passed} passed, "
                f"observed {len(failed)} failed / {len(passed)} passed"
            ),
        )

    expected_set = set(expected_failing)
    if expected_set and set(failed) != expected_set:
        return SubjectOutcome(
            subject=subject,
            collected=True,
            passed=passed,
            failed=failed,
            error_types=error_types,
            classification=WRONG_CAUSE,
            detail=(
                f"counts match but the failing set {sorted(failed)} is not the "
                f"declared discriminating set {sorted(expected_set)}"
            ),
        )

    return SubjectOutcome(
        subject=subject,
        collected=True,
        passed=passed,
        failed=failed,
        error_types=error_types,
        classification=MATCH,
        detail="observed outcome and cause match the prospective expectation",
    )


def qualify_subjects(
    *,
    task_id: str,
    backend: str,
    base_tree: Path,
    reference_tree: Path,
    oracle: Path,
    import_roots: Sequence[str],
    expectations: Mapping[str, Mapping[str, int]],
    discriminator_cases: Sequence[str],
    subject_profiles: Mapping[str, Mapping[str, object]] | None = None,
    argv: Sequence[str] | None = None,
    bound: Mapping[str, str] | None = None,
) -> QualificationReceipt | list[dict[str, object]]:
    """Return a receipt, or structured blockers when the backend cannot qualify."""
    if backend not in BACKENDS:
        return [
            {
                "task": task_id,
                "code": "qualification-backend-unavailable",
                "detail": f"backend {backend!r} is not one of {list(BACKENDS)}",
            }
        ]

    if backend == OCI:
        if not subject_profiles or argv is None:
            return [
                {
                    "task": task_id,
                    "code": "qualification-profiles-missing",
                    "detail": (
                        "the oci backend needs a compiled profile and invocation "
                        "per subject"
                    ),
                }
            ]
        base_report = _run_oci(subject_profiles["base"], argv)
        reference_report = _run_oci(subject_profiles["reference"], argv)
    else:
        base_report = _run_local_python(base_tree, oracle, import_roots)
        reference_report = _run_local_python(reference_tree, oracle, import_roots)
    base = _classify(
        "base", base_report, expectations["base"], expected_failing=discriminator_cases
    )
    reference = _classify(
        "reference", reference_report, expectations["reference"], expected_failing=()
    )
    return QualificationReceipt(
        task=task_id,
        backend=backend,
        base=base,
        reference=reference,
        bound=dict(bound or {}),
    )
