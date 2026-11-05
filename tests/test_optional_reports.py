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
    SONAR,
    _admitted,
    _bundle,
    _inventory,
    _readback,
    _section_c_declaration,
)

# A finding that only the provider's full report shows: no inline comment carries it.
REPORT_ONLY = {**FINDING, "id": "report-only-1", "path": "tools/x.py"}
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


if __name__ == "__main__":
    unittest.main()
