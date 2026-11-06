"""The optional-report slice's acceptance tests (#389: the owner's 6652941418 and 6659619541; Ariadne #14
6652945562; PAO 6657812185 §2.1): written RED on main 794a1eee, before any implementation, and RED
again on main 6b6c8501.

An optional provider's read is recorded, never required: missing or failed, it leaves every declared aspect to
the qualified evidence that covers it. Complete for the exact head, its findings, report-only ones included,
are listed for disposition like any other analyzer finding. A fix at the head closes one. An evidence-backed
dismissal goes through the protected debt ledger (Decision 0129), which matches only a configuration-bound
finding, so an optional provider's closes only by a fix (PAO 6673563051, Option (a))."""

from __future__ import annotations

import copy
import json
import unittest
from typing import Any

from tests.merge_admission_support import CONFIGURATION, debt_entry, debt_finding
from tests.merge_evidence_github_support import (
    FILES,
    FINDING,
    HEAD,
    LEDGER_DOCUMENT,
    SONAR,
    _admitted,
    _bundle,
    _comparison,
    _complete_bundle,
    _decision,
    _evidence,
    _failed,
    _inventory,
    _policy,
    _readback,
    _section_c_declaration,
    _snapshot,
)
from tools import analyzer_readback, merge_admission, merge_evidence_github
from tools.assurance_completeness import AssuranceCompletenessError, parse_declaration
from tools.review_reconcile import MAX_DISPOSITIONS, parse_dispositions

# A finding that only the provider's full report shows: no inline comment carries it. It lies
# in a file the change request changes (the fixture's FILES), so it applies (PAO 6662582106).
REPORT_ONLY = {**FINDING, "id": "report-only-1", "path": "tools/merge_admission.py"}
# The same kind of finding in a file the change request does not change.
UNTOUCHED = {**FINDING, "id": "report-only-untouched", "path": "tools/x.py"}
# What the fixture's other gates leave failed (DeepSourceRetirementTests' own baseline).
BASELINE = {"M13", "M15"}
# The owner's revision (6676021682) and PAO's rulings (6676228030): the merge base the
# fixture's comparison names, and a file the change modifies, whose patch edits only its
# lines 10 to 12.
MERGE_BASE = _comparison([], [])[0]["merge_base_commit"]["sha"]
LEGACY = "tools/legacy.py"
MODIFIED = [
    *FILES,
    {
        "filename": LEGACY,
        "status": "modified",
        "patch": "@@ -10,2 +10,3 @@\n def g():\n-    return 1\n+    value = 1\n+    return value",
    },
]
# The enclosing scope of an unchanged function, the same at the base and the head; and
# the same function's scope after an edit.
SCOPE = "d" * 64
CHANGED = "e" * 64
# The fixture's pull-request author (`_replies`).
AUTHOR = "gnostoa-agent-user"


def _observed(identity: str, line: int, scope: str, **changes: Any) -> dict[str, Any]:
    """A provider's finding in LEGACY at `line`, in the function whose scope hashes to
    `scope`."""
    return {
        **FINDING,
        "id": identity,
        "path": LEGACY,
        "range": {"start_line": line, "start_column": 1},
        "enclosing": {"kind": "function", "name": "f", "sha256": scope},
        **changes,
    }


def _base(*findings: dict[str, Any], status: str = "COMPLETE") -> dict[str, Any]:
    """The provider's complete read for the merge base (Decision 0132 item 3)."""
    return _readback("deepsource", "BASE", *findings, head=MERGE_BASE, status=status)


def _with_reads(
    head_read: dict[str, Any], base_read: dict[str, Any] | None = None
) -> dict[str, Any]:
    bundle = _with_optional(head_read)
    if base_read is not None:
        bundle["readbacks"].insert(0, base_read)
    return bundle


def _listed(evidence: dict[str, Any], identity: str) -> dict[str, Any]:
    [entry] = [
        f for f in evidence["analyzer_findings"]["findings"] if f["id"] == identity
    ]
    return entry


def _disposition(finding: dict[str, Any], **changes: Any) -> str:
    """A review's text carrying a false-positive disposition of `finding` at the head,
    in the closed block Decision 0132 item 4 names."""
    fields = {
        "provider": "deepsource",
        "native_id": finding["id"],
        "rule": finding["rule"],
        "path": finding["path"],
        "scope_hash": finding["enclosing"]["sha256"],
        "commit_id": HEAD,
        "evidence_ref": "https://github.com/ktogias/gnostoa/pull/300#issuecomment-2",
        **changes,
    }
    block = "".join(f"{key}: {json.dumps(value)}\n" for key, value in fields.items())
    return f"Approved.\n\n<!-- gnostoa:disposition:v1\n{block}-->\n"


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
        """D6: a stale report is recorded as stale, never read as the head's. As the
        DeepSource adapter records one: the head requested, another commit's run
        observed, and the read ambiguous (`SUBJECT_MISMATCH`)."""
        stale = analyzer_readback.build_readback(
            provider="deepsource",
            adapter="deepsource-fake/v1",
            repository="ktogias/gnostoa",
            pull_number=300,
            requested_head=HEAD,
            observed_head="0" * 40,
            analysis_id=None,
            scope="FULL",
            completeness="AMBIGUOUS",
            native_mode="FULL_RUN",
            observed_at="2026-09-19T16:40:50Z",
            run_state="SUCCESS",
            coverage_record={
                "status": "INCOMPLETE",
                "pages": 1,
                "count": 1,
                "reason": "SUBJECT_MISMATCH",
            },
            findings=(REPORT_ONLY,),
        )
        evidence, failed = _admitted(_section_c_declaration(), _with_optional(stale))
        self.assertEqual(BASELINE, set(failed))
        self.assertEqual(
            ["STALE"],
            [o["coverage"] for o in evidence["analyzer_optional"]],
        )


class DuplicateObservationTests(unittest.TestCase):
    """D7: one finding per provider-native identity, across the provider's complete report
    and its inline comment, with both provenances (lineage L6)."""

    def test_a_finding_in_the_report_and_in_an_inline_comment_is_listed_once(
        self,
    ) -> None:
        identity = REPORT_ONLY["id"]
        in_report = {
            **REPORT_ONLY,
            "native_ref": identity,
            "provenance": [{"surface": "deepsource-graphql", "reference": "check-1"}],
        }
        # As the provider's inline comment carries it: its id from the comment's marker,
        # and only the fields a comment states.
        in_comment = {
            "id": identity,
            "message": REPORT_ONLY["message"],
            "state": "open",
            "native_ref": identity,
            "path": REPORT_ONLY["path"],
            "provenance": [
                {
                    "surface": "github-inline",
                    "reference": "https://github.com/ktogias/gnostoa/pull/300#discussion_r1",
                }
            ],
        }
        bundle = _with_optional(_readback("deepsource", "FULL", in_report))
        bundle["readbacks"].insert(0, _readback("deepsource", "DIFF", in_comment))
        evidence, failed = _admitted(_section_c_declaration(), bundle)
        self.assertIn("M17", failed)
        self.assertEqual(
            [identity],
            [
                f["id"]
                for f in evidence["analyzer_findings"]["findings"]
                if f["id"] == identity
            ],
        )


class ConfigurationBoundDismissalTests(unittest.TestCase):
    """D4 under PAO 6673563051's Option (a): beside an optional report, the protected ledger
    dismisses only a configuration-bound finding (Decision 0129). The inventory's is inherited;
    the optional provider's states no run-bound configuration, so it stays open and denies,
    whether an entry names it or not."""

    def test_the_ledger_dismisses_only_a_configuration_bound_finding(self) -> None:
        raw = {
            k: v
            for k, v in debt_finding().items()
            if k not in ("item", "configuration")
        }
        inherited = debt_entry(item="project-full", configuration=CONFIGURATION)
        naming_optional = debt_entry(
            id="debt-optional",
            item="deepsource-full",
            rule=REPORT_ONLY["rule"],
            path=REPORT_ONLY["path"],
            message=REPORT_ONLY["message"],
            severity=REPORT_ONLY["severity"],
        )
        for name, entries in (
            ("the inventory finding's entry", [inherited]),
            ("and an entry naming the optional finding", [inherited, naming_optional]),
        ):
            with self.subTest(name):
                bundle = _complete_bundle(inventory_full=(raw,))
                bundle["readbacks"].insert(
                    0, _readback("deepsource", "FULL", REPORT_ONLY)
                )
                _, failed = _admitted(
                    _section_c_declaration(),
                    bundle,
                    "critical",
                    ledger={**LEDGER_DOCUMENT, "entries": entries},
                )
                self.assertEqual(["1 unresolved analyzer finding"], failed.get("M17"))


class BaselineApplicabilityTests(unittest.TestCase):
    """The owner's 6676021682 item 2: what the change introduces or worsens decides,
    against the merge base. Pre-existing needs a complete base read holding the finding
    in a byte-identical scope (PAO 6676228030, P2); without one it is unknown."""

    def test_a_proven_unchanged_legacy_finding_is_listed_and_does_not_deny(
        self,
    ) -> None:
        legacy = _observed("legacy-1", 300, SCOPE)
        bundle = _with_reads(_readback("deepsource", "FULL", legacy), _base(legacy))
        evidence, failed = _admitted(_section_c_declaration(), bundle, files=MODIFIED)
        self.assertEqual(BASELINE, set(failed))
        entry = _listed(evidence, "legacy-1")
        self.assertEqual("pre_existing", entry["baseline"])
        self.assertEqual("unproven", entry["configuration_provenance"])

    def test_a_regression_outside_the_edited_lines_denies(self) -> None:
        # Line 300 of a file whose patch edits lines 10 to 12, in an unchanged scope,
        # and absent from the merge base's complete read.
        regression = _observed("regression-1", 300, SCOPE)
        bundle = _with_reads(_readback("deepsource", "FULL", regression), _base())
        evidence, failed = _admitted(_section_c_declaration(), bundle, files=MODIFIED)
        self.assertIn("M17", failed)
        self.assertEqual("introduced", _listed(evidence, "regression-1")["baseline"])

    def test_a_base_match_in_a_changed_scope_is_introduced_and_denies(self) -> None:
        head = _observed("legacy-1", 300, CHANGED)
        bundle = _with_reads(
            _readback("deepsource", "FULL", head),
            _base(_observed("legacy-1", 300, SCOPE)),
        )
        evidence, failed = _admitted(_section_c_declaration(), bundle, files=MODIFIED)
        self.assertIn("M17", failed)
        self.assertEqual("introduced", _listed(evidence, "legacy-1")["baseline"])

    def test_an_additional_occurrence_in_a_matching_scope_denies(self) -> None:
        """The owner's 6676472012: one base occurrence never accounts for two at the
        head, so neither is pre-existing and both deny until resolved."""
        base = _base(_observed("legacy-1", 300, SCOPE))
        head = _readback(
            "deepsource",
            "FULL",
            _observed("legacy-1", 300, SCOPE),
            _observed("legacy-2", 304, SCOPE),
        )
        evidence, failed = _admitted(
            _section_c_declaration(), _with_reads(head, base), files=MODIFIED
        )
        self.assertIn("M17", failed)
        self.assertEqual(
            ["introduced", "introduced"],
            [_listed(evidence, i)["baseline"] for i in ("legacy-1", "legacy-2")],
        )

    def test_a_severity_increase_on_a_matched_occurrence_denies(self) -> None:
        """The owner's 6676472012: the same occurrence, worse than at the base, is no
        longer pre-existing and denies until resolved."""
        base = _base(_observed("legacy-1", 300, SCOPE, severity="MAJOR"))
        head = _readback(
            "deepsource", "FULL", _observed("legacy-1", 300, SCOPE, severity="CRITICAL")
        )
        evidence, failed = _admitted(
            _section_c_declaration(), _with_reads(head, base), files=MODIFIED
        )
        self.assertIn("M17", failed)
        self.assertEqual("introduced", _listed(evidence, "legacy-1")["baseline"])

    def test_a_missing_or_incomplete_base_read_leaves_the_finding_unknown(
        self,
    ) -> None:
        legacy = _observed("legacy-1", 300, SCOPE)
        for name, base in (
            ("no base read", None),
            ("an incomplete base read", _base(legacy, status="UNAVAILABLE")),
        ):
            with self.subTest(name):
                bundle = _with_reads(_readback("deepsource", "FULL", legacy), base)
                evidence, failed = _admitted(
                    _section_c_declaration(), bundle, files=MODIFIED
                )
                self.assertIn("M17", failed)
                self.assertEqual("unknown", _listed(evidence, "legacy-1")["baseline"])


class FalsePositiveDispositionTests(unittest.TestCase):
    """The owner's 6676021682 item 1 and PAO's 6676228030 P1: a false-positive
    disposition is a closed block in the latest APPROVED review at the exact head by a
    required approver who is neither declarer nor author. Nothing else disposes."""

    def test_an_independent_approver_s_disposition_at_the_head_closes_its_finding(
        self,
    ) -> None:
        finding = _observed("fp-1", 300, SCOPE)
        _, failed = _admitted(
            _section_c_declaration(),
            _with_reads(_readback("deepsource", "FULL", finding)),
            files=MODIFIED,
            review_body=_disposition(finding),
        )
        self.assertEqual(BASELINE, set(failed))

    def test_a_disposition_by_the_author_is_rejected(self) -> None:
        finding = _observed("fp-1", 300, SCOPE)
        authors = {
            "id": 11,
            "user": {"login": AUTHOR},
            "state": "COMMENTED",
            "submitted_at": "2026-09-19T16:40:03Z",
            "commit_id": HEAD,
            "html_url": "https://example.invalid/review/11",
            "body": _disposition(finding),
        }
        _, failed = _admitted(
            _section_c_declaration(),
            _with_reads(_readback("deepsource", "FULL", finding)),
            files=MODIFIED,
            extra_reviews=(authors,),
        )
        self.assertIn("M17", failed)

    def test_a_disposition_for_another_commit_is_unbound(self) -> None:
        finding = _observed("fp-1", 300, SCOPE)
        _, failed = _admitted(
            _section_c_declaration(),
            _with_reads(_readback("deepsource", "FULL", finding)),
            files=MODIFIED,
            review_body=_disposition(finding, commit_id="0" * 40),
        )
        self.assertIn("M17", failed)

    def test_an_unsupported_ignore_leaves_the_finding_open(self) -> None:
        finding = _observed("fp-1", 300, SCOPE)
        for name, observed, body in (
            ("the provider's suppression", {**finding, "state": "suppressed"}, None),
            ("a false-positive mark", {**finding, "state": "false_positive"}, None),
            ("a disposition of another rule", finding, _disposition(finding, rule="X")),
            (
                "a disposition of another provider",
                finding,
                _disposition(finding, provider="codacy"),
            ),
            (
                "a disposition of another finding",
                finding,
                _disposition(finding, native_id="fp-2"),
            ),
            (
                "a disposition of another path",
                finding,
                _disposition(finding, path="tools/other.py"),
            ),
            (
                "a disposition of another scope",
                finding,
                _disposition(finding, scope_hash=CHANGED),
            ),
            (
                "a disposition of another line",
                finding,
                _disposition(finding).replace(
                    f'scope_hash: "{SCOPE}"\n', "line: 301\n"
                ),
            ),
        ):
            with self.subTest(name):
                _, failed = _admitted(
                    _section_c_declaration(),
                    _with_reads(_readback("deepsource", "FULL", observed)),
                    files=MODIFIED,
                    review_body=body,
                )
                self.assertEqual(["1 unresolved analyzer finding"], failed["M17"])


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


class ClassificationEdgeTests(unittest.TestCase):
    """Decision 0132 item 3 at its edges: a base read for another commit, a severity
    outside the provider's order, a lesser one, and a finding with no scope."""

    def _baseline(self, head: dict[str, Any], base: dict[str, Any]) -> str:
        bundle = _with_reads(_readback("deepsource", "FULL", head), base)
        evidence, _ = _admitted(_section_c_declaration(), bundle, files=MODIFIED)
        baseline: str = _listed(evidence, head["id"])["baseline"]
        return baseline

    def test_a_base_read_for_another_commit_leaves_the_finding_unknown(self) -> None:
        legacy = _observed("legacy-1", 300, SCOPE)
        stale = _readback("deepsource", "BASE", legacy, head="f" * 40)
        self.assertEqual("unknown", self._baseline(legacy, stale))

    def test_only_a_known_severity_no_worse_than_the_base_s_is_pre_existing(
        self,
    ) -> None:
        for name, now, before, expected in (
            ("a lesser severity", "MINOR", "MAJOR", "pre_existing"),
            ("a severity outside the order", "BLOCKER", "MAJOR", "introduced"),
            ("a base severity outside the order", "MAJOR", "BLOCKER", "introduced"),
        ):
            with self.subTest(name):
                head = _observed("legacy-1", 300, SCOPE, severity=now)
                base = _base(_observed("legacy-1", 300, SCOPE, severity=before))
                self.assertEqual(expected, self._baseline(head, base))

    def test_a_finding_with_no_enclosing_scope_is_unknown(self) -> None:
        legacy = {
            k: v
            for k, v in _observed("legacy-1", 300, SCOPE).items()
            if k != "enclosing"
        }
        self.assertEqual("unknown", self._baseline(legacy, _base(legacy)))


class DispositionEdgeTests(unittest.TestCase):
    """Decision 0132 item 4 at its edges: the line locator, a later review that is
    not an approval, a required provider's finding, and the verdict's listing."""

    def test_a_disposition_by_its_line_closes_its_finding_and_is_listed(self) -> None:
        finding = _observed("fp-1", 300, SCOPE)
        body = _disposition(finding).replace(f'scope_hash: "{SCOPE}"\n', "line: 300\n")
        evidence, verdict = _decision(
            _section_c_declaration(),
            _with_reads(_readback("deepsource", "FULL", finding)),
            files=MODIFIED,
            review_body=body,
        )
        self.assertEqual(
            BASELINE, {c["id"] for c in verdict["criteria"] if c["status"] == "FAIL"}
        )
        self.assertEqual(
            [
                {
                    "item": "deepsource-full",
                    "id": "fp-1",
                    "approver": "ktogias",
                    "evidence_ref": (
                        "https://github.com/ktogias/gnostoa/pull/300#issuecomment-2"
                    ),
                }
            ],
            verdict["for_approval"]["disposed_findings"],
        )
        self.assertEqual(
            [{"provider": "deepsource", "scope": "FULL", "coverage": "COMPLETE"}],
            verdict["for_approval"]["optional_analyzers"],
        )
        self.assertEqual(
            ["fp-1"], [d["native_id"] for d in evidence["reviews"][0]["dispositions"]]
        )

    def test_a_disposition_outside_the_latest_approval_is_unbound(self) -> None:
        finding = _observed("fp-1", 300, SCOPE)
        later = {
            "id": 12,
            "user": {"login": "ktogias"},
            "state": "COMMENTED",
            "submitted_at": "2026-09-19T16:41:00Z",
            "commit_id": HEAD,
            "html_url": "https://example.invalid/review/12",
        }
        for name, approval, review in (
            (
                "in an approval its approver later superseded",
                _disposition(finding),
                later,
            ),
            (
                "in the approver's later review, no approval",
                None,
                {**later, "body": _disposition(finding)},
            ),
            (
                "in the approver's later approval of another commit",
                None,
                {
                    **later,
                    "state": "APPROVED",
                    "commit_id": "0" * 40,
                    "body": _disposition(finding),
                },
            ),
            (
                "in the approver's earlier review, before their approval",
                None,
                {
                    **later,
                    "submitted_at": "2026-09-19T16:39:00Z",
                    "body": _disposition(finding),
                },
            ),
        ):
            with self.subTest(name):
                _, failed = _admitted(
                    _section_c_declaration(),
                    _with_reads(_readback("deepsource", "FULL", finding)),
                    files=MODIFIED,
                    review_body=approval,
                    extra_reviews=(review,),
                )
                self.assertEqual(["1 unresolved analyzer finding"], failed["M17"])

    def test_an_approver_who_is_the_author_or_the_declarer_disposes_of_nothing(
        self,
    ) -> None:
        """M16's own exclusion: the same evidence, its approver made the change's
        author or declarer, disposes of nothing."""
        finding = _observed("fp-1", 300, SCOPE)
        evidence, verdict = _decision(
            _section_c_declaration(),
            _with_reads(_readback("deepsource", "FULL", finding)),
            files=MODIFIED,
            review_body=_disposition(finding),
        )
        self.assertEqual(
            BASELINE, {c["id"] for c in verdict["criteria"] if c["status"] == "FAIL"}
        )
        declaration = parse_declaration(_section_c_declaration())
        for party in ("author", "declarer"):
            with self.subTest(party=party):
                changed = copy.deepcopy(evidence)
                changed["authorities"][party] = changed["reviews"][0]["reviewer"]
                verdict = merge_admission.evaluate(
                    changed, declaration=declaration, change_policy=_policy()
                )
                [m17] = [c for c in verdict["criteria"] if c["id"] == "M17"]
                self.assertEqual(["1 unresolved analyzer finding"], m17["reasons"])

    def test_an_incomplete_read_sets_nothing_aside(self) -> None:
        """As the ledger's rule is, only a complete read is matched: under claims
        that are not met, a pre-existing and a disposed finding each still count."""
        legacy = _observed("legacy-1", 300, SCOPE)
        disposed = _observed("fp-1", 310, SCOPE, message="Another finding")
        for name, codacy, expected in (
            ("complete", _readback("codacy", "DIFF"), None),
            (
                "incomplete",
                _readback(
                    "codacy",
                    "DIFF",
                    status="UNAVAILABLE",
                    completeness="AUTH_UNAVAILABLE",
                ),
                "2 unresolved analyzer findings",
            ),
        ):
            with self.subTest(name):
                bundle = _bundle(
                    _base(legacy),
                    _readback("deepsource", "FULL", legacy, disposed),
                    codacy,
                    _readback(*SONAR),
                    _inventory("DIFF"),
                    _inventory("FULL"),
                )
                _, failed = _admitted(
                    _section_c_declaration(),
                    bundle,
                    files=MODIFIED,
                    review_body=_disposition(disposed),
                )
                reasons = failed.get("M17", [])
                self.assertEqual(expected, reasons[-1] if reasons else None)

    def test_a_disposition_never_closes_a_required_provider_s_finding(self) -> None:
        finding = _observed("codacy-1", 300, SCOPE)
        bundle = _bundle(
            _readback("codacy", "DIFF", finding),
            _readback(*SONAR),
            _inventory("DIFF"),
            _inventory("FULL"),
        )
        _, failed = _admitted(
            _section_c_declaration(),
            bundle,
            files=MODIFIED,
            review_body=_disposition(finding, provider="codacy"),
        )
        self.assertEqual(["1 unresolved analyzer finding"], failed["M17"])


class DispositionBlockTests(unittest.TestCase):
    """The closed `gnostoa:disposition:v1` block (Decision 0132 item 4): a malformed
    one disposes of nothing, so it is left out, and a review's text yields at most
    MAX_DISPOSITIONS."""

    _FINDING = _observed("fp-1", 300, SCOPE)

    def test_a_well_formed_block_gives_its_fields(self) -> None:
        self.assertEqual(
            [
                {
                    "provider": "deepsource",
                    "native_id": "fp-1",
                    "rule": FINDING["rule"],
                    "path": LEGACY,
                    "scope_hash": SCOPE,
                    "commit_id": HEAD,
                    "evidence_ref": (
                        "https://github.com/ktogias/gnostoa/pull/300#issuecomment-2"
                    ),
                }
            ],
            parse_dispositions(_disposition(self._FINDING)),
        )

    def test_a_malformed_block_is_left_out(self) -> None:
        block = _disposition(self._FINDING)
        scope = f'scope_hash: "{SCOPE}"\n'
        for name, text in (
            ("an unknown field", block.replace(scope, scope + 'note: "x"\n')),
            ("a missing field", block.replace('provider: "deepsource"\n', "")),
            ("both locators", block.replace(scope, scope + "line: 300\n")),
            ("no locator", block.replace(scope, "")),
            ("a repeated field", block.replace(scope, scope + scope)),
            ("a value that is not JSON", block.replace(scope, "scope_hash: d\n")),
            ("a line that is no field", block.replace(scope, scope + "loose text\n")),
            ("a commit that is not exact", block.replace(HEAD, HEAD[:39])),
            ("a scope that is no digest", block.replace(SCOPE, SCOPE[:63])),
            ("a line of 0", block.replace(scope, "line: 0\n")),
            ("a line as text", block.replace(scope, 'line: "300"\n')),
            ("an empty rule", block.replace(json.dumps(FINDING["rule"]), '""')),
            ("an unterminated block", block.replace("-->\n", "")),
        ):
            with self.subTest(name):
                self.assertEqual([], parse_dispositions(text))

    def test_a_block_written_in_github_s_form_is_read(self) -> None:
        block = _disposition(self._FINDING)
        self.assertEqual(
            parse_dispositions(block),
            parse_dispositions(block.replace("\n", "\r\n")),
        )
        self.assertEqual(1, len(parse_dispositions(block.replace("\n", "\r\n"))))

    def test_a_review_yields_at_most_the_bound(self) -> None:
        text = _disposition(self._FINDING) * (MAX_DISPOSITIONS + 1)
        self.assertEqual(MAX_DISPOSITIONS, len(parse_dispositions(text)))


class OptionalEvidenceContractTests(unittest.TestCase):
    """The verdict's closed contract for what Decision 0132 adds to the evidence: an
    unknown value in an optional finding, an optional read or a disposition is
    corrupt evidence, refused, never read as absent."""

    @staticmethod
    def _evidence() -> dict[str, Any]:
        return _evidence(
            analyzer=_with_optional(_readback("deepsource", "FULL", REPORT_ONLY))
        )

    def test_unknown_optional_values_are_refused(self) -> None:
        def finding(**changes: Any) -> dict[str, Any]:
            evidence = self._evidence()
            [entry] = evidence["analyzer_findings"]["findings"]
            entry.update(changes)
            return evidence

        def read(**changes: Any) -> dict[str, Any]:
            evidence = self._evidence()
            evidence["analyzer_optional"][0].update(changes)
            return evidence

        def review(dispositions: Any) -> dict[str, Any]:
            evidence = self._evidence()
            evidence["reviews"][0]["dispositions"] = dispositions
            return evidence

        valid = parse_dispositions(_disposition(_observed("fp-1", 300, SCOPE)))
        for name, evidence in (
            ("an unknown baseline", finding(baseline="waived")),
            ("an unknown provenance", finding(configuration_provenance="proven")),
            ("a provider that is no text", finding(provider=1)),
            ("an unknown optional coverage", read(coverage="CLEAN")),
            ("an unknown optional field", read(extra="x")),
            ("dispositions that are no array", review({})),
            ("a disposition with both locators", review([{**valid[0], "line": 3}])),
            ("too many dispositions", review(valid * (MAX_DISPOSITIONS + 1))),
        ):
            with self.subTest(name), self.assertRaises(AssuranceCompletenessError):
                _failed(evidence)

    def test_a_snapshot_s_malformed_disposition_is_refused_by_the_verdict(
        self,
    ) -> None:
        """Merge evidence passes a review's dispositions on as L1 read them; the
        verdict, which reads them, refuses a malformed one."""
        snapshot = _snapshot()
        snapshot["reviews"][0]["dispositions"] = [{"provider": "deepsource"}]
        evidence = _evidence(snapshot)
        self.assertEqual(
            [{"provider": "deepsource"}], evidence["reviews"][0]["dispositions"]
        )
        with self.assertRaisesRegex(
            AssuranceCompletenessError, "has missing or unknown fields"
        ):
            _failed(evidence)

    def test_a_repeated_optional_read_is_refused(self) -> None:
        bundle = _with_optional(_readback("deepsource", "FULL"))
        bundle["readbacks"].insert(0, _readback("deepsource", "FULL"))
        with self.assertRaisesRegex(
            merge_evidence_github.MergeEvidenceError,
            "repeats the readback \\('deepsource', 'FULL'\\)",
        ):
            _evidence(analyzer=bundle)

    def test_optional_reads_that_are_no_list_are_refused(self) -> None:
        evidence = self._evidence()
        evidence["analyzer_optional"] = {}
        with self.assertRaisesRegex(
            AssuranceCompletenessError, "analyzer_optional must be a list"
        ):
            _failed(evidence)


if __name__ == "__main__":
    unittest.main()
