"""The optional-report slice's acceptance tests (#389: the owner's 6652941418 and 6659619541; Ariadne #14
6652945562; PAO 6657812185 §2.1): written RED on main 794a1eee, before any implementation.

An optional provider's read is recorded, never required: missing or failed, it leaves every declared aspect to
the qualified evidence that covers it. Complete for the exact head, its findings, report-only ones included,
are listed for disposition like any other analyzer finding. A fix at the head closes one; an evidence-backed
dismissal goes through the protected debt ledger (#480) and is pinned once that lands."""

from __future__ import annotations

import unittest
from typing import Any

from tests.test_merge_evidence_github import (
    FINDING,
    HEAD,
    SONAR,
    _admitted,
    _bundle,
    _inventory,
    _readback,
    _section_c_declaration,
)
from tools import analyzer_readback

# A finding that only the provider's full report shows: no inline comment carries it. It lies
# in a file the change request changes (the fixture's FILES), so it applies (PAO 6662582106).
REPORT_ONLY = {**FINDING, "id": "report-only-1", "path": "tools/merge_admission.py"}
# The same kind of finding in a file the change request does not change.
UNTOUCHED = {**FINDING, "id": "report-only-untouched", "path": "tools/x.py"}
# What the fixture's other gates leave failed (DeepSourceRetirementTests' own baseline).
BASELINE = {"M13", "M15"}


def _required() -> dict[str, Any]:
    """The bundle of the declared items alone, each complete with no finding."""
    return _bundle(
        _readback("codacy", "DIFF"),
        _readback(*SONAR),
        _inventory("DIFF"),
        _inventory("FULL"),
    )


def _failed_run() -> dict[str, Any]:
    """DeepSource's full read for the head, whose run failed: no report was obtained."""
    return analyzer_readback.build_readback(
        provider="deepsource",
        adapter="deepsource-fake/v1",
        repository="ktogias/gnostoa",
        pull_number=300,
        requested_head=HEAD,
        observed_head=HEAD,
        analysis_id=None,
        scope="FULL",
        completeness="READBACK_UNAVAILABLE",
        native_mode="FULL_RUN",
        observed_at="2026-09-19T16:40:50Z",
        run_state="FAILURE",
        coverage_record={
            "status": "ERROR",
            "pages": 0,
            "count": 0,
            "reason": "RUN_FAILED",
        },
        findings=(),
    )


def _with_optional(readback: dict[str, Any]) -> dict[str, Any]:
    bundle = _required()
    bundle["readbacks"].insert(0, readback)
    return bundle


class OptionalSourceCoverageTests(unittest.TestCase):
    """D1: an unavailable optional source, its aspects covered by qualified evidence."""

    def test_an_unavailable_optional_source_leaves_its_aspects_covered(self) -> None:
        missing = _readback(
            "deepsource", "FULL", status="UNAVAILABLE", completeness="AUTH_UNAVAILABLE"
        )
        evidence, failed = _admitted(_section_c_declaration(), _with_optional(missing))
        self.assertEqual(BASELINE, set(failed))
        self.assertEqual(
            [("deepsource", "FULL", "UNAVAILABLE")],
            [
                (o["provider"], o["scope"], o["coverage"])
                for o in evidence["analyzer_optional"]
            ],
        )


class ReportOnlyFindingTests(unittest.TestCase):
    """D3 and D4: a report-only finding enters review and stays open until fixed."""

    def test_a_report_only_finding_on_the_exact_head_denies_and_is_listed(self) -> None:
        report = _readback("deepsource", "FULL", REPORT_ONLY)
        evidence, failed = _admitted(_section_c_declaration(), _with_optional(report))
        self.assertIn("M17", failed)
        self.assertEqual(
            ["report-only-1"],
            [
                f["id"]
                for f in evidence["analyzer_findings"]["findings"]
                if f["id"] == "report-only-1"
            ],
        )

    def test_it_closes_when_the_head_s_report_no_longer_lists_it(self) -> None:
        fixed = _readback("deepsource", "FULL")
        _, failed = _admitted(_section_c_declaration(), _with_optional(fixed))
        self.assertEqual(BASELINE, set(failed))

    def test_a_report_for_another_head_contributes_no_finding(self) -> None:
        """D6: a stale report is recorded as stale, never read as the head's."""
        stale = _readback("deepsource", "FULL", REPORT_ONLY, head="0" * 40)
        evidence, failed = _admitted(_section_c_declaration(), _with_optional(stale))
        self.assertEqual(BASELINE, set(failed))
        self.assertEqual(
            ["STALE"],
            [o["coverage"] for o in evidence["analyzer_optional"]],
        )


class MandatoryCoverageTests(unittest.TestCase):
    """D2: an optional report never stands in for a required item that is missing."""

    def test_a_complete_optional_report_never_covers_a_missing_required_item(
        self,
    ) -> None:
        bundle = _bundle(
            _readback("deepsource", "FULL"),
            _readback(
                "codacy", "DIFF", status="UNAVAILABLE", completeness="AUTH_UNAVAILABLE"
            ),
            _readback(*SONAR),
            _inventory("DIFF"),
            _inventory("FULL"),
        )
        evidence, failed = _admitted(_section_c_declaration(), bundle)
        self.assertLessEqual({"M2-M8", "M17"}, set(failed))
        self.assertEqual(
            [("deepsource", "COMPLETE")],
            [(o["provider"], o["coverage"]) for o in evidence["analyzer_optional"]],
        )


class FailedOptionalRunTests(unittest.TestCase):
    """D5: a red optional run is classified by its run: a failure is not a finding."""

    def test_an_optional_run_that_failed_is_recorded_as_failed_and_finds_nothing(
        self,
    ) -> None:
        failed_run = _failed_run()
        evidence, failed = _admitted(
            _section_c_declaration(), _with_optional(failed_run)
        )
        self.assertEqual(BASELINE, set(failed))
        self.assertEqual(
            [("deepsource", "FULL", "ERROR")],
            [
                (o["provider"], o["scope"], o["coverage"])
                for o in evidence["analyzer_optional"]
            ],
        )

    def test_a_findings_bearing_run_is_a_finding_not_a_failure(self) -> None:
        report = _readback("deepsource", "FULL", REPORT_ONLY)
        evidence, failed = _admitted(_section_c_declaration(), _with_optional(report))
        self.assertIn("M17", failed)
        self.assertEqual(
            ["COMPLETE"], [o["coverage"] for o in evidence["analyzer_optional"]]
        )


class ApplicabilityTests(unittest.TestCase):
    """PAO 6662582106: only a finding in a changed file enters the verdict."""

    def test_a_report_finding_on_an_untouched_file_stays_out_of_the_verdict(
        self,
    ) -> None:
        report = _readback("deepsource", "FULL", UNTOUCHED)
        evidence, failed = _admitted(_section_c_declaration(), _with_optional(report))
        self.assertEqual(BASELINE, set(failed))
        self.assertNotIn(
            "report-only-untouched",
            [f["id"] for f in evidence["analyzer_findings"]["findings"]],
        )
        self.assertEqual(
            ["deepsource"], [o["provider"] for o in evidence["analyzer_optional"]]
        )


if __name__ == "__main__":
    unittest.main()
