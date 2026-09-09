"""Regression contract for qualification process/report completeness."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.capsule.qualification import (
    INFRASTRUCTURE,
    MATCH,
    _classify,
    _parse_pytest_report,
    _run_local_python,
)


class PytestReportCompletionTests(unittest.TestCase):
    def classify_base(self, stdout: str, exit_code: int):
        return _classify(
            "base",
            _parse_pytest_report(stdout, exit_code),
            {"failed": 1, "passed": 0},
            expected_failing=("test_discriminates",),
        )

    def classify_reference(self, stdout: str, exit_code: int):
        return _classify(
            "reference",
            _parse_pytest_report(stdout, exit_code),
            {"failed": 0, "passed": 1},
            expected_failing=(),
        )

    def test_internal_error_cannot_satisfy_matching_base_failure(self) -> None:
        outcome = self.classify_base(
            "oracle.py::test_discriminates FAILED\n",
            3,
        )

        self.assertEqual(outcome.classification, INFRASTRUCTURE)
        self.assertIn("exit 3", outcome.detail)

    def test_internal_error_cannot_satisfy_matching_reference_success(self) -> None:
        outcome = self.classify_reference(
            "oracle.py::test_discriminates PASSED\n",
            3,
        )

        self.assertEqual(outcome.classification, INFRASTRUCTURE)
        self.assertIn("exit 3", outcome.detail)

    def test_non_completed_pytest_exit_codes_fail_closed_with_case_output(self) -> None:
        for exit_code in (2, 3, 4, 5, 6, 137, -9):
            with self.subTest(exit_code=exit_code):
                outcome = self.classify_base(
                    "oracle.py::test_discriminates FAILED\n",
                    exit_code,
                )
                self.assertEqual(outcome.classification, INFRASTRUCTURE)
                self.assertIn(f"exit {exit_code}", outcome.detail)

    def test_pytest_error_outcome_is_not_inferred_as_assertion_failure(self) -> None:
        outcome = self.classify_base(
            "oracle.py::test_discriminates ERROR\n",
            1,
        )

        self.assertEqual(outcome.classification, INFRASTRUCTURE)
        self.assertIn("ERROR", outcome.detail)

    def test_exit_zero_with_failed_case_is_infrastructure(self) -> None:
        outcome = self.classify_base(
            "oracle.py::test_discriminates FAILED\n",
            0,
        )

        self.assertEqual(outcome.classification, INFRASTRUCTURE)
        self.assertIn("exit 0", outcome.detail)

    def test_exit_one_with_only_passed_cases_is_infrastructure(self) -> None:
        outcome = self.classify_reference(
            "oracle.py::test_discriminates PASSED\n",
            1,
        )

        self.assertEqual(outcome.classification, INFRASTRUCTURE)
        self.assertIn("exit 1", outcome.detail)

    def test_completed_base_assertion_failure_remains_a_match(self) -> None:
        outcome = self.classify_base(
            "oracle.py::test_discriminates FAILED\n",
            1,
        )

        self.assertEqual(outcome.classification, MATCH)

    def test_completed_reference_success_remains_a_match(self) -> None:
        outcome = self.classify_reference(
            "oracle.py::test_discriminates PASSED\n",
            0,
        )

        self.assertEqual(outcome.classification, MATCH)


class LocalHarnessCompletionTests(unittest.TestCase):
    @staticmethod
    def valid_report() -> str:
        return json.dumps(
            {
                "collected": True,
                "cases": {
                    "test_discriminates": {
                        "outcome": "passed",
                        "error_type": None,
                        "message": "",
                    }
                },
                "error": None,
            }
        )

    def run_local_with(self, completed: subprocess.CompletedProcess[str]):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            subject = root / "subject"
            subject.mkdir()
            oracle = root / "oracle.py"
            oracle.write_text("def test_discriminates():\n    pass\n", encoding="utf-8")
            with patch(
                "tools.capsule.qualification.subprocess.run",
                return_value=completed,
            ):
                return _run_local_python(subject, oracle, ())

    def test_nonzero_local_process_cannot_supply_valid_looking_report(self) -> None:
        report = self.run_local_with(
            subprocess.CompletedProcess(
                args=("python",),
                returncode=7,
                stdout=self.valid_report() + "\n",
                stderr="local harness crashed",
            )
        )

        self.assertIs(report["collected"], False)
        self.assertIn("exit 7", str(report["error"]))

    def test_signalled_local_process_cannot_supply_valid_looking_report(self) -> None:
        report = self.run_local_with(
            subprocess.CompletedProcess(
                args=("python",),
                returncode=-9,
                stdout=self.valid_report() + "\n",
                stderr="",
            )
        )

        self.assertIs(report["collected"], False)
        self.assertIn("exit -9", str(report["error"]))

    def test_zero_exit_local_process_preserves_valid_report(self) -> None:
        report = self.run_local_with(
            subprocess.CompletedProcess(
                args=("python",),
                returncode=0,
                stdout=self.valid_report() + "\n",
                stderr="",
            )
        )

        self.assertIs(report["collected"], True)

    def test_local_timeout_fails_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            subject = root / "subject"
            subject.mkdir()
            oracle = root / "oracle.py"
            oracle.write_text("def test_discriminates():\n    pass\n", encoding="utf-8")
            with patch(
                "tools.capsule.qualification.subprocess.run",
                side_effect=subprocess.TimeoutExpired(("python",), 120),
            ):
                report = _run_local_python(subject, oracle, ())

        self.assertIs(report["collected"], False)
        self.assertIn("timed out", str(report["error"]))

    def test_local_non_object_json_fails_closed(self) -> None:
        report = self.run_local_with(
            subprocess.CompletedProcess(
                args=("python",),
                returncode=0,
                stdout="[]\n",
                stderr="",
            )
        )

        self.assertIs(report["collected"], False)
        self.assertIn("object", str(report["error"]))


if __name__ == "__main__":
    unittest.main()
