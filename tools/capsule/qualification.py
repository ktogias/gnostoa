"""BASE and REFERENCE qualification, classified by cause rather than by count.

Runs the declared oracle against each materialised subject under explicit preflight
authority and compares the observed per-case outcome against the prospectively
frozen expectation. A collection or import failure can never satisfy a prospective
FAIL, and a base failure caused by something other than the declared discriminator
is a wrong-cause mismatch, not a match -- the Phase-D D1 false-match class.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tools.capsule.identity import digest_of

MATCH = "MATCH"
COUNT_MISMATCH = "COUNT_MISMATCH"
WRONG_CAUSE = "WRONG_CAUSE"
INFRASTRUCTURE = "INFRASTRUCTURE"

LOCAL_PYTHON = "local-python"
CONTAINER = "container"

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


@dataclass(frozen=True, slots=True)
class QualificationReceipt:
    task: str
    backend: str
    base: SubjectOutcome
    reference: SubjectOutcome

    @property
    def qualified(self) -> bool:
        return (
            self.base.classification == MATCH and self.reference.classification == MATCH
        )

    @property
    def identity(self) -> str:
        return digest_of(self.as_json())

    def as_json(self) -> dict[str, object]:
        return {
            "task": self.task,
            "backend": self.backend,
            "base": self.base.as_json(),
            "reference": self.reference.as_json(),
            "qualified": self.qualified,
        }


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
) -> QualificationReceipt | list[dict[str, object]]:
    """Return a receipt, or structured blockers when the backend cannot qualify."""
    if backend != LOCAL_PYTHON:
        return [
            {
                "task": task_id,
                "code": "qualification-backend-unavailable",
                "detail": (
                    f"backend {backend!r} is declared but not implemented in v1; only "
                    f"{LOCAL_PYTHON!r} can qualify without widening the runner boundary"
                ),
            }
        ]

    base_report = _run_local_python(base_tree, oracle, import_roots)
    reference_report = _run_local_python(reference_tree, oracle, import_roots)
    base = _classify(
        "base", base_report, expectations["base"], expected_failing=discriminator_cases
    )
    reference = _classify(
        "reference", reference_report, expectations["reference"], expected_failing=()
    )
    return QualificationReceipt(
        task=task_id, backend=backend, base=base, reference=reference
    )
