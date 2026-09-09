"""RED/GREEN coverage for qualification process and report validity (#219)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from tools.capsule import qualification


_FAILED_OUTPUT = """\
oracle.py::test_discriminates FAILED [100%]
=========================== short test summary info ============================
FAILED oracle.py::test_discriminates - assert False
============================== 1 failed in 0.01s ===============================
"""

_PASSED_OUTPUT = """\
oracle.py::test_discriminates PASSED [100%]
============================== 1 passed in 0.01s ===============================
"""


class PytestProcessValidityTests(unittest.TestCase):
    """Terminal process state must remain part of qualification evidence."""

    def classify(
        self,
        stdout: str,
        exit_code: int,
        *,
        failed: int,
        passed: int,
        expected_failing: tuple[str, ...] = (),
    ) -> qualification.SubjectOutcome:
        report = qualification._parse_pytest_report(stdout, exit_code)
        return qualification._classify(
            "subject",
            report,
            {"failed": failed, "passed": passed},
            expected_failing=expected_failing,
        )

    def assert_infrastructure(
        self, outcome: qualification.SubjectOutcome, marker: str
    ) -> None:
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)
        self.assertIn(marker, outcome.detail)

    def test_internal_error_after_failed_case_cannot_match_base(self) -> None:
        output = (
            "oracle.py::test_discriminates FAILED [100%]\n"
            "INTERNALERROR> RuntimeError: reporter crashed\n"
        )
        outcome = self.classify(
            output,
            3,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assert_infrastructure(outcome, "exit 3")

    def test_internal_error_after_passed_case_cannot_match_reference(self) -> None:
        output = (
            "oracle.py::test_discriminates PASSED [100%]\n"
            "INTERNALERROR> RuntimeError: reporter crashed\n"
        )
        outcome = self.classify(output, 3, failed=0, passed=1)
        self.assert_infrastructure(outcome, "exit 3")

    def test_case_error_is_not_relabelled_as_assertion_failure(self) -> None:
        output = """\
oracle.py::test_discriminates ERROR [100%]
==================================== ERRORS ====================================
E RuntimeError: setup failed
=============================== 1 error in 0.01s ===============================
"""
        outcome = self.classify(
            output,
            1,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assert_infrastructure(outcome, "ERROR")
        self.assertNotEqual(
            outcome.error_types.get("test_discriminates"),
            "AssertionError",
        )

    def test_truncated_case_output_without_terminal_summary_is_invalid(self) -> None:
        outcome = self.classify(
            "oracle.py::test_discriminates FAILED [100%]\n",
            1,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assert_infrastructure(outcome, "terminal summary")

    def test_failed_case_with_success_exit_is_contradictory(self) -> None:
        outcome = self.classify(
            _FAILED_OUTPUT,
            0,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assert_infrastructure(outcome, "exit 0")

    def test_passed_case_with_test_failure_exit_is_contradictory(self) -> None:
        outcome = self.classify(_PASSED_OUTPUT, 1, failed=0, passed=1)
        self.assert_infrastructure(outcome, "exit 1")

    def test_no_tests_exit_cannot_be_hidden_by_case_output(self) -> None:
        outcome = self.classify(_PASSED_OUTPUT, 5, failed=0, passed=1)
        self.assert_infrastructure(outcome, "exit 5")

    def test_unknown_terminal_status_fails_closed(self) -> None:
        outcome = self.classify(_PASSED_OUTPUT, 17, failed=0, passed=1)
        self.assert_infrastructure(outcome, "exit 17")

    def test_terminal_summary_must_match_observed_cases(self) -> None:
        output = _FAILED_OUTPUT.replace("1 failed", "2 failed")
        outcome = self.classify(
            output,
            1,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assert_infrastructure(outcome, "summary")

    def test_expected_base_assertion_failure_with_exit_one_can_match(self) -> None:
        outcome = self.classify(
            _FAILED_OUTPUT,
            1,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assertEqual(outcome.classification, qualification.MATCH)

    def test_expected_reference_success_with_exit_zero_can_match(self) -> None:
        outcome = self.classify(_PASSED_OUTPUT, 0, failed=0, passed=1)
        self.assertEqual(outcome.classification, qualification.MATCH)


class NormalizedReportValidityTests(unittest.TestCase):
    """Malformed or self-contradictory reports must not satisfy zero counts."""

    def classify(self, report: object) -> qualification.SubjectOutcome:
        return qualification._classify(
            "subject",
            report,  # type: ignore[arg-type]
            {"failed": 0, "passed": 0},
            expected_failing=(),
        )

    def test_collected_report_with_no_cases_is_invalid(self) -> None:
        outcome = self.classify({"collected": True, "cases": {}, "error": None})
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_report_error_is_not_ignored_when_cases_exist(self) -> None:
        report = {
            "collected": True,
            "cases": {
                "test_discriminates": {
                    "outcome": "passed",
                    "error_type": "",
                    "message": "",
                }
            },
            "error": "incomplete report",
        }
        outcome = qualification._classify(
            "subject",
            report,
            {"failed": 0, "passed": 1},
            expected_failing=(),
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)
        self.assertIn("incomplete report", outcome.detail)

    def test_non_mapping_cases_are_rejected_without_crashing(self) -> None:
        outcome = self.classify(
            {"collected": True, "cases": [], "error": None}
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_unknown_case_outcome_cannot_match_zero_counts(self) -> None:
        outcome = self.classify(
            {
                "collected": True,
                "cases": {
                    "test_discriminates": {
                        "outcome": "unknown",
                        "error_type": "",
                        "message": "",
                    }
                },
                "error": None,
            }
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)


class LocalHarnessCompletionTests(unittest.TestCase):
    """A parseable JSON line cannot erase local subprocess failure."""

    def report_json(self, outcome: str) -> str:
        return json.dumps(
            {
                "collected": True,
                "cases": {
                    "test_discriminates": {
                        "outcome": outcome,
                        "error_type": (
                            "AssertionError" if outcome == "failed" else None
                        ),
                        "message": "expected" if outcome == "failed" else "",
                    }
                },
                "error": None,
            }
        )

    def classify_local(self, returncode: int, outcome: str) -> qualification.SubjectOutcome:
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=returncode,
            stdout=self.report_json(outcome) + "\n",
            stderr="local harness failed" if returncode else "",
        )
        with mock.patch.object(qualification.subprocess, "run", return_value=completed):
            report = qualification._run_local_python(
                Path("/subject"), Path("/oracle.py"), ()
            )
        return qualification._classify(
            "subject",
            report,
            {
                "failed": 1 if outcome == "failed" else 0,
                "passed": 1 if outcome == "passed" else 0,
            },
            expected_failing=(
                ("test_discriminates",) if outcome == "failed" else ()
            ),
        )

    def test_nonzero_local_completion_cannot_yield_match(self) -> None:
        outcome = self.classify_local(3, "failed")
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)
        self.assertIn("exit 3", outcome.detail)

    def test_zero_local_completion_with_valid_report_can_match(self) -> None:
        outcome = self.classify_local(0, "passed")
        self.assertEqual(outcome.classification, qualification.MATCH)


if __name__ == "__main__":
    unittest.main()
