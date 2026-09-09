"""RED/GREEN coverage for qualification process and report validity (#219)."""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile
from unittest import TestCase, main, mock

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


class PytestProcessValidityTests(TestCase):
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
        for exit_code in (2, 3, 4, 5, 6, 17, -2, -9, 137):
            with self.subTest(exit_code=exit_code):
                outcome = self.classify(_PASSED_OUTPUT, exit_code, failed=0, passed=1)
                self.assert_infrastructure(outcome, f"exit {exit_code}")

    def test_unsupported_summary_outcomes_cannot_hide_behind_failed_case(self) -> None:
        for label in ("error", "skipped", "xfailed", "xpassed", "deselected"):
            with self.subTest(label=label):
                output = _FAILED_OUTPUT.replace(
                    "1 failed in", f"1 failed, 1 {label} in"
                )
                outcome = self.classify(
                    output,
                    1,
                    failed=1,
                    passed=0,
                    expected_failing=("test_discriminates",),
                )
                self.assert_infrastructure(outcome, "unsupported outcomes")

    def test_failed_case_without_traceback_cannot_invent_assertion_cause(self) -> None:
        output = (
            "oracle.py::test_discriminates FAILED [100%]\n"
            "=================== 1 failed in 0.01s ===================\n"
        )
        outcome = self.classify(
            output,
            1,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assert_infrastructure(outcome, "no recognizable failure cause")

    def test_unknown_summary_outcomes_cannot_be_silently_ignored(self) -> None:
        for label in ("rerun", "unrecognized-outcome"):
            with self.subTest(label=label):
                output = _FAILED_OUTPUT.replace(
                    "1 failed in", f"1 failed, 3 {label} in"
                )
                outcome = self.classify(
                    output,
                    1,
                    failed=1,
                    passed=0,
                    expected_failing=("test_discriminates",),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_malformed_summary_items_return_infrastructure_without_crashing(
        self,
    ) -> None:
        for item in ("broken", "three failed", "3 rerun!"):
            with self.subTest(item=item):
                output = _FAILED_OUTPUT.replace("1 failed in", f"1 failed, {item} in")
                outcome = self.classify(
                    output,
                    1,
                    failed=1,
                    passed=0,
                    expected_failing=("test_discriminates",),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_ansi_decoration_preserves_valid_outcomes_and_causes(self) -> None:
        for output, failed, passed in ((_FAILED_OUTPUT, 1, 0), (_PASSED_OUTPUT, 0, 1)):
            with self.subTest(failed=failed):
                decorated = "\n".join(
                    f"\x1b[31m{line}\x1b[0m" for line in output.splitlines()
                )
                outcome = self.classify(
                    decorated,
                    int(bool(failed)),
                    failed=failed,
                    passed=passed,
                    expected_failing=("test_discriminates",) if failed else (),
                )
                self.assertEqual(outcome.classification, qualification.MATCH)
                self.assertEqual(
                    outcome.error_types,
                    {"test_discriminates": "AssertionError"} if failed else {},
                )

    def test_ansi_cannot_hide_a_conflicting_infrastructure_traceback(self) -> None:
        # Synthetic contradictory report: no claim that real pytest emits it.
        output = _FAILED_OUTPUT.replace(
            "FAILED [100%]\n",
            "FAILED [100%]\n\x1b[31mE   OSError: unavailable\x1b[0m\n",
        )
        outcome = self.classify(
            output,
            1,
            failed=1,
            passed=0,
            expected_failing=("test_discriminates",),
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_pytest_resource_failures_cannot_match_behavioral_failure(self) -> None:
        for cause in (
            "MemoryError",
            "RecursionError",
            "OSError",
            "PermissionError",
            "TimeoutError",
            "ConnectionError",
        ):
            with self.subTest(cause=cause):
                output = _FAILED_OUTPUT.replace("assert False", f"{cause}: unavailable")
                outcome = self.classify(
                    output,
                    1,
                    failed=1,
                    passed=0,
                    expected_failing=("test_discriminates",),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_each_failed_case_requires_its_own_recognizable_cause(self) -> None:
        for second_cause in ("SystemExit: 0", "Fatal: stopped", None):
            with self.subTest(second_cause=second_cause):
                output = (
                    "oracle.py::test_assertion FAILED [50%]\n"
                    "oracle.py::test_discriminates FAILED [100%]\n"
                    "FAILED oracle.py::test_assertion - assert False\n"
                )
                if second_cause is not None:
                    output += f"FAILED oracle.py::test_discriminates - {second_cause}\n"
                output += "=================== 2 failed in 0.01s ===================\n"
                outcome = self.classify(
                    output,
                    1,
                    failed=2,
                    passed=0,
                    expected_failing=("test_assertion", "test_discriminates"),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_distinct_observed_causes_are_not_copied_between_cases(self) -> None:
        output = (
            "oracle.py::test_assertion FAILED [50%]\n"
            "oracle.py::test_discriminates FAILED [100%]\n"
            "FAILED oracle.py::test_assertion - assert False\n"
            "FAILED oracle.py::test_discriminates - ValueError: invalid value\n"
            "=================== 2 failed in 0.01s ===================\n"
        )
        outcome = self.classify(
            output,
            1,
            failed=2,
            passed=0,
            expected_failing=("test_assertion", "test_discriminates"),
        )
        self.assertEqual(outcome.classification, qualification.MATCH)
        self.assertEqual(
            outcome.error_types,
            {"test_assertion": "AssertionError", "test_discriminates": "ValueError"},
        )

    def test_failure_summary_must_refer_once_to_an_observed_failed_case(self) -> None:
        failure_line = "FAILED oracle.py::test_discriminates - assert False\n"
        variants = (
            (
                "absent case",
                _PASSED_OUTPUT.replace(
                    "PASSED [100%]\n",
                    "PASSED [100%]\nFAILED oracle.py::test_absent - assert False\n",
                ),
                0,
                1,
            ),
            (
                "passed case",
                _PASSED_OUTPUT.replace(
                    "PASSED [100%]\n", "PASSED [100%]\n" + failure_line
                ),
                0,
                1,
            ),
            (
                "duplicate failure summary",
                _FAILED_OUTPUT.replace(failure_line, failure_line * 2),
                1,
                0,
            ),
        )
        for scenario, output, failed, passed in variants:
            with self.subTest(scenario=scenario):
                outcome = self.classify(
                    output,
                    int(bool(failed)),
                    failed=failed,
                    passed=passed,
                    expected_failing=("test_discriminates",) if failed else (),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_qualified_infrastructure_cause_without_traceback_cannot_match(
        self,
    ) -> None:
        for cause in ("builtins.OSError", "builtins.MemoryError"):
            with self.subTest(cause=cause):
                output = _FAILED_OUTPUT.replace("assert False", f"{cause}: unavailable")
                outcome = self.classify(
                    output,
                    1,
                    failed=1,
                    passed=0,
                    expected_failing=("test_discriminates",),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_duplicate_case_outcomes_cannot_collapse_into_matching_counts(self) -> None:
        for output, failed, passed in ((_PASSED_OUTPUT, 0, 1), (_FAILED_OUTPUT, 1, 0)):
            with self.subTest(failed=failed):
                case_line = output.splitlines()[0] + "\n"
                output = output.replace(case_line, case_line * 2)
                outcome = self.classify(
                    output,
                    int(bool(failed)),
                    failed=failed,
                    passed=passed,
                    expected_failing=("test_discriminates",) if failed else (),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_one_traceback_cannot_supply_causes_for_multiple_failed_cases(self) -> None:
        for traceback in (
            "E   assert 0",
            "E   AssertionError: failed",
            "E   ValueError: invalid",
        ):
            with self.subTest(traceback=traceback):
                output = (
                    "oracle.py::test_a FAILED [50%]\n"
                    "oracle.py::test_b FAILED [100%]\n"
                    f"{traceback}\n"
                    "=================== 2 failed in 0.01s ===================\n"
                )
                outcome = self.classify(
                    output, 1, failed=2, passed=0, expected_failing=("test_a", "test_b")
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_infrastructure_traceback_cannot_be_erased_by_assertion_summary(
        self,
    ) -> None:
        output = _FAILED_OUTPUT.replace(
            "FAILED [100%]\n", "FAILED [100%]\nE   OSError: unavailable\n"
        )
        outcome = self.classify(
            output, 1, failed=1, passed=0, expected_failing=("test_discriminates",)
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

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

    def test_explicit_pytest_fail_is_observed_behavioral_evidence(self) -> None:
        output = _FAILED_OUTPUT.replace("assert False", "Failed: behavior was wrong")
        outcome = self.classify(
            output, 1, failed=1, passed=0, expected_failing=("test_discriminates",)
        )
        self.assertEqual(outcome.classification, qualification.MATCH)
        self.assertEqual(outcome.error_types["test_discriminates"], "Failed")

    def test_expected_reference_success_with_exit_zero_can_match(self) -> None:
        outcome = self.classify(_PASSED_OUTPUT, 0, failed=0, passed=1)
        self.assertEqual(outcome.classification, qualification.MATCH)


class NormalizedReportValidityTests(TestCase):
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
        outcome = self.classify({"collected": True, "cases": [], "error": None})
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_nonempty_non_mapping_cases_return_structured_infrastructure(self) -> None:
        for cases in ([{"outcome": "passed"}], "test_discriminates", 1):
            with self.subTest(cases=cases):
                outcome = self.classify(
                    {"collected": True, "cases": cases, "error": None}
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_collection_requires_boolean_true_even_when_cases_match(self) -> None:
        for collection in (
            {},
            {"collected": False},
            {"collected": None},
            {"collected": 1},
            {"collected": "true"},
        ):
            with self.subTest(collection=collection):
                report = {
                    **collection,
                    "cases": {"test_discriminates": {"outcome": "passed"}},
                    "error": None,
                }
                outcome = qualification._classify(
                    "reference",
                    report,
                    {"failed": 0, "passed": 1},
                    expected_failing=(),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_failed_case_requires_a_cause_even_when_counts_and_name_match(self) -> None:
        for cause in ({}, {"error_type": None}, {"error_type": ""}):
            with self.subTest(cause=cause):
                report = {
                    "collected": True,
                    "cases": {"test_discriminates": {"outcome": "failed", **cause}},
                    "error": None,
                }
                outcome = qualification._classify(
                    "base",
                    report,
                    {"failed": 1, "passed": 0},
                    expected_failing=("test_discriminates",),
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


class LocalHarnessCompletionTests(TestCase):
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

    def classify_local(
        self, returncode: int, outcome: str
    ) -> qualification.SubjectOutcome:
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=returncode,
            stdout=self.report_json(outcome) + "\n",
            stderr="local harness failed" if returncode else "",
        )
        with mock.patch.object(qualification.subprocess, "run", return_value=completed):
            report = qualification._run_local_python(
                pathlib.Path("/subject"), pathlib.Path("/oracle.py"), ()
            )
        return qualification._classify(
            "subject",
            report,
            {
                "failed": 1 if outcome == "failed" else 0,
                "passed": 1 if outcome == "passed" else 0,
            },
            expected_failing=(("test_discriminates",) if outcome == "failed" else ()),
        )

    def test_nonzero_local_completion_cannot_yield_match(self) -> None:
        outcome = self.classify_local(3, "failed")
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)
        self.assertIn("exit 3", outcome.detail)

    def test_local_timeout_is_reported_as_infrastructure(self) -> None:
        timeout = subprocess.TimeoutExpired(["python"], 120)
        with mock.patch.object(qualification.subprocess, "run", side_effect=timeout):
            report = qualification._run_local_python(
                pathlib.Path("/subject"), pathlib.Path("/oracle.py"), ()
            )
        outcome = qualification._classify(
            "subject",
            report,
            {"failed": 0, "passed": 1},
            expected_failing=(),
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)
        self.assertIn("timed out", outcome.detail)

    def test_local_launch_errors_return_an_unqualified_receipt(self) -> None:
        errors = (
            FileNotFoundError(2, "unavailable subject directory"),
            PermissionError(13, "process launch denied"),
            BlockingIOError(11, "process resources unavailable"),
            OSError(5, "process launch input/output failure"),
        )
        for subject in ("base", "reference"):
            for error in errors:
                with self.subTest(subject=subject, error=type(error).__name__):
                    completions: list[object] = [
                        subprocess.CompletedProcess(
                            ["python"], 0, self.report_json("failed"), ""
                        ),
                        subprocess.CompletedProcess(
                            ["python"], 0, self.report_json("passed"), ""
                        ),
                    ]
                    completions[0 if subject == "base" else 1] = error
                    with mock.patch.object(
                        qualification.subprocess, "run", side_effect=completions
                    ):
                        receipt = qualification.qualify_subjects(
                            task_id="synthetic-launch-error",
                            backend=qualification.LOCAL_PYTHON,
                            base_tree=pathlib.Path("/base"),
                            reference_tree=pathlib.Path("/reference"),
                            oracle=pathlib.Path("/oracle.py"),
                            import_roots=(),
                            expectations={
                                "base": {"failed": 1, "passed": 0},
                                "reference": {"failed": 0, "passed": 1},
                            },
                            discriminator_cases=("test_discriminates",),
                        )
                    self.assertIsInstance(receipt, qualification.QualificationReceipt)
                    assert isinstance(receipt, qualification.QualificationReceipt)
                    self.assertFalse(receipt.qualified)
                    outcome = getattr(receipt, subject)
                    self.assertEqual(
                        outcome.classification, qualification.INFRASTRUCTURE
                    )
                    self.assertFalse(outcome.collected)
                    self.assertIn(type(error).__name__, outcome.detail)
                    control = receipt.reference if subject == "base" else receipt.base
                    self.assertEqual(control.classification, qualification.MATCH)

    def test_zero_local_completion_with_valid_report_can_match(self) -> None:
        outcome = self.classify_local(0, "passed")
        self.assertEqual(outcome.classification, qualification.MATCH)

    def test_local_failed_report_with_whitespace_only_cause_cannot_match(self) -> None:
        for cause in (" ", "\t\r\n", "\u2003"):
            with self.subTest(cause=cause):
                payload = json.loads(self.report_json("failed"))
                payload["cases"]["test_discriminates"]["error_type"] = cause
                completed = subprocess.CompletedProcess(
                    ["python"], 0, json.dumps(payload) + "\n", ""
                )
                with mock.patch.object(
                    qualification.subprocess, "run", return_value=completed
                ):
                    report = qualification._run_local_python(
                        pathlib.Path("/subject"), pathlib.Path("/oracle.py"), ()
                    )
                outcome = qualification._classify(
                    "base",
                    report,
                    {"failed": 1, "passed": 0},
                    expected_failing=("test_discriminates",),
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def classify_json_cause(
        self, case_outcome: str, cause: object
    ) -> qualification.SubjectOutcome:
        payload = json.loads(self.report_json(case_outcome))
        payload["cases"]["test_discriminates"]["error_type"] = cause
        completed = subprocess.CompletedProcess(
            ["python"], 0, json.dumps(payload) + "\n", ""
        )
        with mock.patch.object(qualification.subprocess, "run", return_value=completed):
            report = qualification._run_local_python(
                pathlib.Path("/subject"), pathlib.Path("/oracle.py"), ()
            )
        failed = case_outcome == "failed"
        return qualification._classify(
            "subject",
            report,
            {"failed": int(failed), "passed": int(not failed)},
            expected_failing=("test_discriminates",) if failed else (),
        )

    def test_local_padded_infrastructure_causes_cannot_match(self) -> None:
        for cause in ("OSError", "builtins.OSError", "MemoryError"):
            for left, right in ((" ", ""), ("", " \n"), ("\u2003", "\t")):
                with self.subTest(cause=cause, left=left, right=right):
                    outcome = self.classify_json_cause("failed", left + cause + right)
                    self.assertEqual(
                        outcome.classification, qualification.INFRASTRUCTURE
                    )
                    self.assertEqual(outcome.error_types, {"test_discriminates": cause})

    def test_local_padded_behavioral_causes_retain_canonical_names(self) -> None:
        for cause in ("AssertionError", "ValueError", "builtins.AssertionError"):
            with self.subTest(cause=cause):
                outcome = self.classify_json_cause("failed", " \t" + cause + "\n\u2003")
                self.assertEqual(outcome.classification, qualification.MATCH)
                self.assertEqual(outcome.error_types, {"test_discriminates": cause})

    def test_local_passed_report_accepts_empty_normalized_cause(self) -> None:
        for cause in (None, "", " \t\r\n", "\u2003"):
            with self.subTest(cause=cause):
                outcome = self.classify_json_cause("passed", cause)
                self.assertEqual(outcome.classification, qualification.MATCH)
                self.assertEqual(outcome.error_types, {})

    def test_cause_normalization_preserves_invalid_report_rejection(self) -> None:
        for case_outcome in ("passed", "failed"):
            for cause in (False, 0, 1, [], {}, ["OSError"], {"type": "OSError"}):
                with self.subTest(case_outcome=case_outcome, cause=cause):
                    outcome = self.classify_json_cause(case_outcome, cause)
                    self.assertEqual(
                        outcome.classification, qualification.INFRASTRUCTURE
                    )
        for cause in ("AssertionError", " \tAssertionError\n", " OSError "):
            with self.subTest(passed_cause=cause):
                outcome = self.classify_json_cause("passed", cause)
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def run_oracle(self, source: str) -> qualification.SubjectOutcome:
        with tempfile.TemporaryDirectory() as temporary:
            subject = pathlib.Path(temporary)
            oracle = subject / "oracle.py"
            oracle.write_text(source)
            report = qualification._run_local_python(subject, oracle, ())
        return qualification._classify(
            "base",
            report,
            {"failed": 1, "passed": 0},
            expected_failing=("test_discriminates",),
        )

    def test_real_local_process_and_resource_exceptions_cannot_match(self) -> None:
        for expression in (
            "KeyboardInterrupt()",
            "SystemExit(0)",
            "SystemExit(1)",
            "GeneratorExit()",
            "MemoryError()",
            "RecursionError()",
            "OSError(28, 'No space left on device')",
            "PermissionError()",
            "TimeoutError()",
            "ConnectionError()",
        ):
            with self.subTest(expression=expression):
                outcome = self.run_oracle(
                    f"def test_discriminates():\n    raise {expression}\n"
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_real_local_resource_exception_subclass_cannot_erase_cause(self) -> None:
        outcome = self.run_oracle(
            "class ResourceUnavailable(OSError):\n    pass\n"
            "def test_discriminates():\n    raise ResourceUnavailable('unavailable')\n"
        )
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)

    def test_real_local_assertion_failure_remains_valid(self) -> None:
        outcome = self.run_oracle("def test_discriminates():\n    assert False\n")
        self.assertEqual(outcome.classification, qualification.MATCH)
        self.assertEqual(outcome.error_types["test_discriminates"], "AssertionError")

    def test_real_local_explicit_failure_signal_retains_observed_type(self) -> None:
        # Test frameworks can signal failure outside Exception (pytest Failed
        # does so). This stdlib fixture characterizes the existing harness
        # contract without adding a pytest dependency or claiming OCI support.
        outcome = self.run_oracle(
            "class Failed(BaseException):\n    pass\n"
            "def test_discriminates():\n    raise Failed('behavior was wrong')\n"
        )
        self.assertEqual(outcome.classification, qualification.MATCH)
        self.assertEqual(outcome.error_types["test_discriminates"], "Failed")

    def test_real_local_collection_failure_remains_infrastructure(self) -> None:
        outcome = self.run_oracle("raise ImportError('missing dependency')\n")
        self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)
        self.assertIn("ImportError", outcome.detail)

    def test_malformed_local_json_is_infrastructure(self) -> None:
        for stdout in ("", "{", "[]", "null", '"report"'):
            with self.subTest(stdout=stdout):
                completed = subprocess.CompletedProcess(["python"], 0, stdout, "")
                with mock.patch.object(
                    qualification.subprocess, "run", return_value=completed
                ):
                    report = qualification._run_local_python(
                        pathlib.Path("/subject"), pathlib.Path("/oracle.py"), ()
                    )
                outcome = qualification._classify(
                    "subject", report, {"failed": 0, "passed": 0}, expected_failing=()
                )
                self.assertEqual(outcome.classification, qualification.INFRASTRUCTURE)


if __name__ == "__main__":
    main()
