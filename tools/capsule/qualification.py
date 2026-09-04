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
        report["cases"][name] = {"outcome": "failed", "error_type": type(exc).__name__,
                                 "message": str(exc)[:200]}
    else:
        report["cases"][name] = {"outcome": "passed", "error_type": None, "message": ""}
print(json.dumps(report))
"""


_PYTEST_CASE = re.compile(
    r"^(?P<file>\S+)::(?P<case>[\w\[\]-]+)\s+(?P<outcome>PASSED|FAILED|ERROR)"
)
_PYTEST_ERROR = re.compile(
    r"^E\s+(?P<error>[A-Za-z_][\w.]*(?:Error|Exception|Warning))\b", re.M
)
_COLLECTION_FAILURE = re.compile(
    r"unrecognized arguments|ModuleNotFoundError|ImportError|INTERNALERROR|"
    r"error: unrecognized|no tests ran|ERROR: usage",
    re.I,
)


def _parse_pytest_report(stdout: str, exit_code: int) -> dict[str, object]:
    """Turn retained runner stdout into the same report shape as the local backend."""
    cases: dict[str, dict[str, str]] = {}
    for line in stdout.splitlines():
        match = _PYTEST_CASE.match(line.strip())
        if match is None:
            continue
        outcome = "passed" if match["outcome"] == "PASSED" else "failed"
        cases[match["case"]] = {"outcome": outcome, "error_type": "", "message": ""}

    if not cases:
        return {
            "collected": False,
            "cases": {},
            "error": (
                failure.group(0)
                if (failure := _COLLECTION_FAILURE.search(stdout)) is not None
                else f"no case outcome was collected (exit {exit_code})"
            ),
        }

    # Attribute a non-assertion error class to the whole run when pytest reports one,
    # so an import or attribute failure is never read as a behavioural failure.
    errors = set(_PYTEST_ERROR.findall(stdout))
    non_assertion = {error for error in errors if error != "AssertionError"}
    for case in cases.values():
        if case["outcome"] == "failed":
            case["error_type"] = (
                sorted(non_assertion)[0] if non_assertion else "AssertionError"
            )
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
    stdout = completed.stdout.strip().splitlines()
    if not stdout:
        return {
            "collected": False,
            "cases": {},
            "error": completed.stderr.strip()[:400],
        }
    try:
        parsed: dict[str, object] = json.loads(stdout[-1])
    except json.JSONDecodeError:
        return {"collected": False, "cases": {}, "error": "unparsable harness output"}
    return parsed


def _classify(
    subject: str,
    report: Mapping[str, object],
    expectation: Mapping[str, int],
    *,
    expected_failing: Sequence[str],
) -> SubjectOutcome:
    if not report.get("collected"):
        return SubjectOutcome(
            subject=subject,
            collected=False,
            passed=(),
            failed=(),
            error_types={},
            classification=INFRASTRUCTURE,
            detail=str(report.get("error") or "the oracle was never collected"),
        )

    raw_cases = report.get("cases") or {}
    cases: dict[str, dict[str, str]] = cast(dict[str, dict[str, str]], raw_cases)
    passed = tuple(sorted(n for n, c in cases.items() if c["outcome"] == "passed"))
    failed = tuple(sorted(n for n, c in cases.items() if c["outcome"] == "failed"))
    error_types = {n: c["error_type"] for n, c in cases.items() if c["error_type"]}

    infrastructure = {
        n: t for n, t in error_types.items() if t in _INFRASTRUCTURE_ERRORS
    }
    if infrastructure:
        return SubjectOutcome(
            subject=subject,
            collected=True,
            passed=passed,
            failed=failed,
            error_types=error_types,
            classification=INFRASTRUCTURE,
            detail=(
                f"{sorted(infrastructure)} failed with {sorted(set(infrastructure.values()))}, "
                "which never exercised the declared behaviour"
            ),
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
                f"counts match but the failing set {sorted(failed)} is not the declared "
                f"discriminating set {sorted(expected_set)}"
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
                    "detail": "the oci backend needs a compiled profile and invocation per subject",
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
