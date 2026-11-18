from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from tests.merge_admission_support import (
    _SCOPE,
    CONFIGURATION,
    DECLARATION,
    HEAD,
    POLICY,
    SUBJECT,
    _evidence,
    _failed,
    _receipt,
    _verdict,
    debt_entry,
    debt_finding,
)
from tests.quality_evidence_profile_support import _original
from tools import (
    assurance_completeness,
    check_change_policy,
    merge_admission,
    quality_evidence,
    verdict_cli,
)
from tools.check_change_policy import load_change_policy
from tools.knowledge_common import KnowledgeFormatError

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "b" * 40


def _verdict_steps(reviewers: int) -> tuple[int, dict[str, Any]]:
    """The line events the verdict's own module executes for `reviewers` distinct
    reviewers, a deterministic measure of its work unlike a clock, and the
    verdict."""

    evidence = _evidence()
    evidence["reviews"] += [
        {
            "reviewer": f"reviewer-{index}",
            "state": "COMMENTED",
            "commit_id": HEAD,
            "submitted_at": "2026-10-09T09:00:00Z",
        }
        for index in range(reviewers)
    ]
    target = merge_admission.__file__
    steps = 0

    def local(_frame: Any, event: str, _arg: Any) -> Any:
        nonlocal steps
        if event == "line":
            steps += 1
        return local

    def tracer(frame: Any, _event: str, _arg: Any) -> Any:
        return local if frame.f_code.co_filename == target else None

    previous = sys.gettrace()
    sys.settrace(tracer)
    try:
        verdict = _verdict(evidence)
    finally:
        # Restored, so a coverage tracer keeps measuring the rest of the suite.
        sys.settrace(previous)
    return steps, verdict


class MergeAdmissionTests(unittest.TestCase):
    def assertDenied(self, evidence: dict[str, Any], criterion: str) -> None:
        verdict = _verdict(evidence)
        self.assertEqual("DENY", verdict["status"])
        self.assertIn(criterion, _failed(verdict))

    def test_a_converged_change_is_allowed(self) -> None:
        verdict = _verdict(_evidence())
        self.assertEqual("ALLOW", verdict["status"], _failed(verdict))
        self.assertEqual({}, _failed(verdict))
        self.assertEqual("gnostoa-merge-admission/v1", verdict["schema"])
        self.assertEqual("COMPLETE", verdict["completeness"]["status"])

    # The owner's safety invariants (#398, 6061573600).

    def test_a_an_approval_of_the_previous_head_denies(self) -> None:
        """(a) A new head whose diff is unchanged keeps the provider's approval;
        the verdict reads the approval's commit, not the provider's flag."""
        evidence = _evidence()
        evidence["reviews"][0]["commit_id"] = PREVIOUS
        self.assertDenied(evidence, "M16")

    def test_b_incomplete_evidence_denies(self) -> None:
        evidence = _evidence()
        evidence["receipts"] = []
        self.assertDenied(evidence, "M2-M8")

    def test_c_unknown_coverage_denies(self) -> None:
        for field, criterion in (("threads", "M10"), ("closing_references", "M12")):
            for coverage in ("PARTIAL", "UNAVAILABLE", "ERROR", "RATE_LIMITED"):
                with self.subTest(field=field, coverage=coverage):
                    evidence = _evidence()
                    evidence[field]["coverage"] = coverage
                    self.assertDenied(evidence, criterion)

    def test_e_an_emergency_is_never_allowed(self) -> None:
        """Break glass bypasses R-main; it is never this verdict's ALLOW."""
        evidence = _evidence()
        evidence["change_class"] = "emergency"
        self.assertDenied(evidence, "M14")

    def test_f_equivalent_evidence_gets_the_same_verdict_on_any_provider(
        self,
    ) -> None:
        other = {
            "repository": "https://gitlab.example/group/project",
            "change_request": {"kind": "gitlab-merge-request", "id": "7"},
            "head_commit": HEAD,
        }
        github, gitlab = _verdict(_evidence()), _verdict(_evidence(other))
        self.assertEqual(github["status"], gitlab["status"])
        self.assertEqual(github["criteria"], gitlab["criteria"])
        evidence = _evidence(other)
        evidence["reviews"][0]["commit_id"] = PREVIOUS
        self.assertEqual("DENY", _verdict(evidence)["status"])

    # The merge criteria.

    def test_e_an_emergency_s_evidence_is_still_validated(self) -> None:
        """Codex on #410: the emergency denial returned before the links were
        parsed, so corrupt evidence exited 1 instead of failing the run."""
        evidence = _evidence()
        evidence["change_class"] = "emergency"
        evidence["links"] = None
        with self.assertRaises(assurance_completeness.AssuranceCompletenessError):
            _verdict(evidence)

    def test_m1_a_draft_closed_or_retargeted_change_denies(self) -> None:
        for field, value in (
            ("draft", True),
            ("state", "closed"),
            ("state", "merged"),
            ("target", "release"),
        ):
            with self.subTest(field=field, value=value):
                evidence = _evidence()
                evidence["lifecycle"][field] = value
                self.assertDenied(evidence, "M1")

    def test_m9_the_seal_must_name_the_head_from_the_declarer(self) -> None:
        for change in (
            {"head_commit": PREVIOUS},
            {"declarer": "someone-else"},
        ):
            with self.subTest(change=change):
                evidence = _evidence()
                evidence["declared_candidate"].update(change)
                self.assertDenied(evidence, "M9")
        evidence = _evidence()
        evidence["declared_candidate"] = None
        self.assertDenied(evidence, "M9")

    def test_m10_an_unresolved_thread_denies(self) -> None:
        evidence = _evidence()
        evidence["threads"]["unresolved"] = 1
        self.assertDenied(evidence, "M10")

    def test_m11_an_effective_request_for_changes_denies(self) -> None:
        """Any reviewer's latest opinion, ignoring comments and dismissals."""
        evidence = _evidence()
        evidence["reviews"] += [
            {
                "reviewer": "bot-reviewer",
                "state": "CHANGES_REQUESTED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:10:00Z",
            },
            {
                "reviewer": "bot-reviewer",
                "state": "COMMENTED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:20:00Z",
            },
        ]
        self.assertDenied(evidence, "M11")
        evidence["reviews"].append(
            {
                "reviewer": "bot-reviewer",
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:30:00Z",
            }
        )
        self.assertNotIn("M11", _failed(_verdict(evidence)))

    def test_m11_a_dismissed_request_for_changes_no_longer_counts(self) -> None:
        """Claude on #410: a dismissal changes the review's own state to DISMISSED,
        as GitHub records it, so the earlier opinion is the reviewer's last."""
        evidence = _evidence()
        evidence["reviews"] += [
            {
                "reviewer": "bot-reviewer",
                "state": "APPROVED",
                "commit_id": PREVIOUS,
                "submitted_at": "2026-10-09T08:10:00Z",
            },
            {
                "reviewer": "bot-reviewer",
                "state": "DISMISSED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:10:00Z",
            },
        ]
        self.assertNotIn("M11", _failed(_verdict(evidence)))

    def test_m12_a_closing_reference_denies(self) -> None:
        evidence = _evidence()
        evidence["closing_references"]["found"] = [
            {"surface": "commit-message", "reference": "#407"}
        ]
        self.assertDenied(evidence, "M12")

    def test_m13_an_unjustified_suppression_denies_and_justified_ones_are_listed(
        self,
    ) -> None:
        justified = {"path": "tests/x.py", "marker": "nosec B603", "justified": True}
        unjustified = {"path": "tools/y.py", "marker": "noqa", "justified": False}
        evidence = _evidence()
        evidence["suppressions"]["found"] = [justified]
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual([justified], verdict["for_approval"]["suppressions"])
        evidence["suppressions"]["found"].append(unjustified)
        self.assertDenied(evidence, "M13")

    def test_m13_and_m15_deny_unless_their_evidence_was_read_completely(
        self,
    ) -> None:
        """#407 slice 1b.3a: a bare list could not say "not read", so an adapter
        that has not read the diff yet passed M13 and M15 vacuously."""
        for field, criterion in (
            ("suppressions", "M13"),
            ("trust_root_changes", "M15"),
        ):
            for coverage in (
                "UNAVAILABLE",
                "PARTIAL",
                "ERROR",
                "RATE_LIMITED",
                "SKIPPED",
            ):
                with self.subTest(field=field, coverage=coverage):
                    evidence = _evidence()
                    evidence[field]["coverage"] = coverage
                    self.assertDenied(evidence, criterion)

    def test_m14_the_class_needs_its_work_item_and_decision(self) -> None:
        for field in ("work_items", "decisions"):
            with self.subTest(missing=field):
                evidence = _evidence()
                evidence["links"][field] = []
                self.assertDenied(evidence, "M14")
        evidence = _evidence()
        evidence["change_class"] = "mechanical"
        evidence["links"] = {"work_items": [], "decisions": []}
        self.assertNotIn("M14", _failed(_verdict(evidence)))

    def test_m15_trust_root_changes_are_listed_for_the_approval(self) -> None:
        evidence = _evidence()
        evidence["trust_root_changes"]["paths"] = [".github/workflows/verification.yml"]
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual(
            [".github/workflows/verification.yml"],
            verdict["for_approval"]["trust_root_changes"],
        )
        self.assertIn("M15", [c["id"] for c in verdict["criteria"]])

    def test_m17_an_unresolved_analyzer_finding_denies_and_is_listed(self) -> None:
        """The owner's rule (#407, 6096770145 and 6101607240): every listed
        finding is unresolved, a suppressed one included, with no waiver."""
        finding = {"item": "deepsource-full", "id": "issue-1", "message": "Reimport"}
        suppressed = {**finding, "id": "issue-2", "state": "suppressed"}
        # The owner's re-admission (#417 6107601240): the readback's normalized
        # disposition fields are listed as they are.
        rich = {
            **finding,
            "id": "issue-3",
            "category": "antipattern",
            "tool": {"id": "python", "name": "Python"},
            "range": {
                "start_line": 3,
                "start_column": 1,
                "end_line": 3,
                "end_column": 9,
            },
            "native_ref": "https://app.deepsource.com/gh/ktogias/gnostoa/run/x",
        }
        for findings, reason in (
            ([finding], "1 unresolved analyzer finding"),
            ([finding, suppressed], "2 unresolved analyzer findings"),
            ([suppressed], "1 unresolved analyzer finding"),
            ([rich], "1 unresolved analyzer finding"),
        ):
            with self.subTest(reason=reason, ids=[f["id"] for f in findings]):
                evidence = _evidence()
                evidence["analyzer_findings"]["findings"] = copy.deepcopy(findings)
                verdict = _verdict(evidence)
                self.assertEqual("DENY", verdict["status"])
                self.assertEqual({"M17": [reason]}, _failed(verdict))
                self.assertEqual(findings, verdict["for_approval"]["analyzer_findings"])

    def test_m17_denies_unless_the_findings_were_read_completely(self) -> None:
        for coverage in (
            "UNAVAILABLE",
            "INCOMPLETE",
            "PARTIAL",
            "RATE_LIMITED",
            "ERROR",
            "SKIPPED",
        ):
            with self.subTest(coverage=coverage):
                evidence = _evidence()
                evidence["analyzer_findings"]["coverage"] = coverage
                self.assertEqual(
                    {"M17": [f"analyzer finding coverage is {coverage}"]},
                    _failed(_verdict(evidence)),
                )

    def test_m17_the_findings_have_a_closed_contract(self) -> None:
        finding = {"item": "codacy", "id": "issue-1", "message": "x"}
        for name, value in (
            ("no record", None),
            ("an unknown coverage", {"coverage": "DONE", "findings": []}),
            ("an unknown field", {"coverage": "COMPLETE", "findings": [], "x": 1}),
            ("findings that are not a list", {"coverage": "COMPLETE", "findings": {}}),
            (
                "a finding with an unknown field",
                {"coverage": "COMPLETE", "findings": [{**finding, "x": "y"}]},
            ),
            (
                "a finding without an id",
                {
                    "coverage": "COMPLETE",
                    "findings": [{"item": "codacy", "message": "x"}],
                },
            ),
            (
                "a finding with an empty field",
                {"coverage": "COMPLETE", "findings": [{**finding, "rule": ""}]},
            ),
            *(
                (name, {"coverage": "COMPLETE", "findings": [{**finding, **change}]})
                for name, change in (
                    ("a tool that is not an object", {"tool": "python"}),
                    ("a tool with an unknown field", {"tool": {"id": "py", "x": "y"}}),
                    ("a range that is not one-based", {"range": {"start_line": 0}}),
                    (
                        "a range that ends before it starts",
                        {"range": {"start_line": 5, "end_line": 3}},
                    ),
                    ("an empty range", {"range": {}}),
                    ("an empty native reference", {"native_ref": ""}),
                    ("a field that is null", {"tool": None}),
                    ("the finding's provenance", {"provenance": [{"surface": "x"}]}),
                    ("the finding's native metadata", {"native": {}}),
                    ("an item that is not text", {"item": 1}),
                )
            ),
        ):
            with self.subTest(name):
                evidence = _evidence()
                if value is None:
                    del evidence["analyzer_findings"]
                else:
                    evidence["analyzer_findings"] = value
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _verdict(evidence)

    def test_m16_the_latest_review_of_any_state_must_approve_the_head(self) -> None:
        """Runbook step 8: a comment after the approval is the latest review."""
        evidence = _evidence()
        evidence["reviews"].append(
            {
                "reviewer": "owner",
                "state": "COMMENTED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:05:00Z",
            }
        )
        self.assertDenied(evidence, "M16")

    def test_m16_an_approval_by_someone_else_denies(self) -> None:
        evidence = _evidence()
        evidence["reviews"][0]["reviewer"] = "another-writer"
        self.assertDenied(evidence, "M16")

    def test_reviews_in_the_same_second_have_no_order_and_deny(self) -> None:
        """Review timestamps have second resolution, so a tie with different
        opinions is ambiguous, whatever order the list gives (M11 and M16)."""
        for first, second in (("APPROVED", "COMMENTED"), ("COMMENTED", "APPROVED")):
            with self.subTest(owner=(first, second)):
                evidence = _evidence()
                evidence["reviews"] = [
                    {**evidence["reviews"][0], "state": state}
                    for state in (first, second)
                ]
                self.assertDenied(evidence, "M16")
        for first, second in (
            ("CHANGES_REQUESTED", "APPROVED"),
            ("APPROVED", "CHANGES_REQUESTED"),
        ):
            with self.subTest(bot=(first, second)):
                evidence = _evidence()
                evidence["reviews"] += [
                    {
                        "reviewer": "bot-reviewer",
                        "state": state,
                        "commit_id": HEAD,
                        "submitted_at": "2026-10-09T09:10:00Z",
                    }
                    for state in (first, second)
                ]
                self.assertDenied(evidence, "M11")

    def test_a_pending_review_is_not_submitted_and_is_ignored(self) -> None:
        """Sourcery on #410: GitHub returns the reader's own pending review with
        no `submitted_at`, and it is no one's opinion yet."""
        for submitted_at in (None, "2026-10-09T09:30:00Z"):
            with self.subTest(submitted_at=submitted_at):
                evidence = _evidence()
                evidence["reviews"].append(
                    {
                        "reviewer": "owner",
                        "state": "PENDING",
                        "commit_id": HEAD,
                        "submitted_at": submitted_at,
                    }
                )
                self.assertEqual("ALLOW", _verdict(evidence)["status"])
        evidence = _evidence()
        evidence["reviews"][0]["submitted_at"] = None
        with self.assertRaises(assurance_completeness.AssuranceCompletenessError):
            _verdict(evidence)

    def test_a_tie_is_judged_by_what_each_criterion_reads(self) -> None:
        """cubic on #410: M11 reads the opinion, M16 also its commit. Approvals of
        two commits in one second are no request for changes, but they leave the
        head's approval unordered."""
        approvals = [
            {
                "reviewer": reviewer,
                "state": "APPROVED",
                "commit_id": commit,
                "submitted_at": "2026-10-09T09:10:00Z",
            }
            for reviewer in ("bot-reviewer", "owner")
            for commit in (HEAD, PREVIOUS)
        ]
        evidence = _evidence()
        evidence["reviews"] = approvals
        failed = _failed(_verdict(evidence))
        self.assertNotIn("M11", failed)
        self.assertIn("M16", failed)

    def test_a_pending_review_is_still_validated(self) -> None:
        """Codex on #410: only its absent timestamp is special; a malformed
        record is corrupt evidence."""
        for change in (
            {"reviewer": None},
            {"commit_id": 7},
            {"submitted_at": "not a time"},
        ):
            with self.subTest(change=change):
                evidence = _evidence()
                evidence["reviews"].append(
                    {
                        "reviewer": "owner",
                        "state": "PENDING",
                        "commit_id": HEAD,
                        "submitted_at": None,
                        **change,
                    }
                )
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _verdict(evidence)

    def test_a_review_of_a_commit_that_no_longer_exists_is_valid(self) -> None:
        """CodeAnt on #410: GitHub's `commit_id` is null when the commit was
        garbage-collected or force-deleted. Such a review is valid evidence, and
        it approves no head."""
        evidence = _evidence()
        evidence["reviews"].append(
            {
                "reviewer": "bot-reviewer",
                "state": "COMMENTED",
                "commit_id": None,
                "submitted_at": "2026-10-09T09:10:00Z",
            }
        )
        self.assertEqual("ALLOW", _verdict(evidence)["status"])
        evidence["reviews"][0]["commit_id"] = None
        self.assertDenied(evidence, "M16")

    def test_a_commit_is_an_exact_sha_or_null(self) -> None:
        """Codex on #410: any non-empty string passed as a review's commit, or as
        the declared candidate's, though the subject's must be an exact SHA."""
        for commit in ("not-a-sha", "A" * 40, "a" * 39):
            with self.subTest(review_commit=commit):
                evidence = _evidence()
                evidence["reviews"].append(
                    {
                        "reviewer": "bot-reviewer",
                        "state": "COMMENTED",
                        "commit_id": commit,
                        "submitted_at": "2026-10-09T09:10:00Z",
                    }
                )
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _verdict(evidence)
            with self.subTest(declared_commit=commit):
                evidence = _evidence()
                evidence["declared_candidate"]["head_commit"] = commit
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _verdict(evidence)

    def test_a_tie_is_the_same_second_whatever_its_fraction(self) -> None:
        """CodeAnt on #410: fractions ordered two opinions inside one second,
        which the rule says have no order."""
        evidence = _evidence()
        evidence["reviews"] = [
            {**evidence["reviews"][0], "submitted_at": "2026-10-09T09:10:00.900Z"},
            {
                **evidence["reviews"][0],
                "state": "COMMENTED",
                "submitted_at": "2026-10-09T09:10:00.100Z",
            },
        ]
        self.assertDenied(evidence, "M16")

    def test_many_reviewers_are_evaluated_in_linear_time(self) -> None:
        """CodeAnt on #410: each reviewer rescanned every review, which took about
        two minutes at the input bound. cubic on #410: a wall-clock bound is not
        deterministic, so the work is counted instead. Four times the reviewers
        must cost about four times the steps, not sixteen."""
        (small, few), (large, many) = _verdict_steps(250), _verdict_steps(1_000)
        self.assertLess(large / small, 6, (small, large))
        # The work counted is the work of a correct verdict (cubic on #410).
        for verdict in (few, many):
            self.assertEqual("ALLOW", verdict["status"], _failed(verdict))

    def test_the_same_review_repeated_in_one_second_is_not_ambiguous(self) -> None:
        evidence = _evidence()
        evidence["reviews"].append(dict(evidence["reviews"][0]))
        self.assertEqual("ALLOW", _verdict(evidence)["status"])

    def test_links_are_validated_whatever_the_class_requires(self) -> None:
        """Codex on #410: a mechanical change's links were never parsed."""
        cases: tuple[dict[str, object], ...] = (
            {"work_items": None, "decisions": []},
            {"work_items": [], "decisions": 7},
        )
        for links in cases:
            with self.subTest(links=links):
                evidence = _evidence()
                evidence["change_class"] = "mechanical"
                evidence["links"] = links
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _verdict(evidence)

    def test_a_class_requirement_outside_the_schema_is_refused(self) -> None:
        """cubic on #410: `decision_record: "true"` read as false."""
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        for field, value in (
            ("decision_record", "true"),
            ("work_item", "always"),
            ("minimum_approvals", "1"),
            ("minimum_approvals", -1),
            ("minimum_approvals", True),
            ("independent_approval", "yes"),
        ):
            with self.subTest(field=field, value=value):
                policy = copy.deepcopy(POLICY)
                policy["change_classes"]["normal"][field] = value
                evidence = _evidence()
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    merge_admission.evaluate(
                        evidence, declaration=declaration, change_policy=policy
                    )

    def test_m16_the_declarer_or_the_author_cannot_approve_an_independent_class(
        self,
    ) -> None:
        """CodeAnt on #410: the approver list came from the input unchecked, so
        the agent's own approval could admit its change."""
        for identity in ("agent-app", "agent-user"):
            with self.subTest(approver=identity):
                evidence = _evidence()
                evidence["authorities"]["required_approvers"] = [identity]
                evidence["reviews"][0]["reviewer"] = identity
                self.assertDenied(evidence, "M16")

    def test_m16_a_self_approval_denies_even_when_it_is_not_required(
        self,
    ) -> None:
        """cubic on #410: the declarer's or author's approval was ignored unless
        they were a required approver; the policy forbids it outright
        (`may_approve_own_change: false`)."""
        for identity in ("agent-app", "agent-user"):
            with self.subTest(approver=identity):
                evidence = _evidence()
                evidence["reviews"].append(
                    {**evidence["reviews"][0], "reviewer": identity}
                )
                self.assertDenied(evidence, "M16")

    def test_m16_the_class_minimum_of_approvals_applies(self) -> None:
        policy = copy.deepcopy(POLICY)
        policy["change_classes"]["normal"]["minimum_approvals"] = 2
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        verdict = merge_admission.evaluate(
            _evidence(), declaration=declaration, change_policy=policy
        )
        self.assertEqual("DENY", verdict["status"])
        self.assertIn("M16", _failed(verdict))

    def test_m16_a_class_that_requires_no_approval_needs_no_approver(
        self,
    ) -> None:
        """Codex on #410: the core policy requires zero approvals for every class,
        and an empty approver list denied regardless."""
        core = load_change_policy(ROOT / "core" / "change-control.yaml")
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        evidence = _evidence()
        evidence["authorities"]["required_approvers"] = []
        evidence["reviews"] = []
        verdict = merge_admission.evaluate(
            evidence, declaration=declaration, change_policy=core
        )
        self.assertNotIn("M16", _failed(verdict))
        self.assertEqual("ALLOW", verdict["status"], _failed(verdict))

    def test_m16_a_repeated_required_approver_is_refused(self) -> None:
        """Codex on #410: each repeat rescanned the approver's reviews, which is
        quadratic, and a repeated identity is corrupt evidence."""
        evidence = _evidence()
        evidence["authorities"]["required_approvers"] = ["owner", "owner"]
        with self.assertRaises(assurance_completeness.AssuranceCompletenessError):
            _verdict(evidence)

    def test_m16_no_required_approver_denies(self) -> None:
        evidence = _evidence()
        evidence["authorities"]["required_approvers"] = []
        self.assertDenied(evidence, "M16")

    def test_an_evidence_document_that_breaks_the_contract_is_refused(self) -> None:
        for change in (
            {"extra": 1},
            {"change_class": ["normal"]},
            {"threads": {"coverage": "COMPLETE", "unresolved": -1}},
            {"threads": {"coverage": "COMPLETE", "unresolved": True}},
            {"reviews": [{"reviewer": "owner"}]},
        ):
            with self.subTest(change=change):
                evidence = _evidence()
                evidence.update(change)
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _verdict(evidence)


def _run(text: str, *, with_declaration: bool = True) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "policy").mkdir()
        if with_declaration:
            (root / "policy" / "assurance-evidence.yaml").write_text(
                json.dumps(DECLARATION), encoding="utf-8"
            )
        (root / "policy" / "change-control.yaml").write_text(
            (ROOT / "policy" / "change-control.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "core").mkdir()
        (root / "core" / "change-control.yaml").write_text(
            (ROOT / "core" / "change-control.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdin", stdin), redirect_stdout(out), redirect_stderr(err):
            code = merge_admission.main(["--project-root", str(root)])
        return code, out.getvalue() + err.getvalue()


class CommandTests(unittest.TestCase):
    def test_allow_exits_zero_and_deny_exits_one(self) -> None:
        code, output = _run(json.dumps(_evidence()))
        self.assertEqual(0, code, output)
        self.assertEqual("ALLOW", json.loads(output)["status"])
        evidence = _evidence()
        evidence["threads"]["unresolved"] = 2
        code, output = _run(json.dumps(evidence))
        self.assertEqual(1, code)
        self.assertEqual("DENY", json.loads(output)["status"])

    def test_g_a_missing_declaration_is_a_failed_run_not_an_allow(self) -> None:
        """(g) A missing owner is never replaced locally."""
        code, output = _run(json.dumps(_evidence()), with_declaration=False)
        self.assertEqual(2, code)
        self.assertIn("assurance", output.lower())

    def test_invalid_input_exits_two(self) -> None:
        for text in ("[]", "not json", json.dumps({"subject": SUBJECT})):
            with self.subTest(text=text):
                self.assertEqual(2, _run(text)[0])

    def test_an_input_past_the_nesting_bound_is_named_as_such(self) -> None:
        """cubic on #410: valid JSON past the bound was reported as invalid JSON."""
        nested: dict[str, Any] = {}
        for _ in range(80):
            nested = {"next": nested}
        evidence = _evidence()
        evidence["subject"] = nested
        code, output = _run(json.dumps(evidence))
        self.assertEqual(2, code)
        self.assertIn("nests deeper than the 64-level operational bound", output)
        self.assertNotIn("not valid JSON", output)

    def test_a_failing_exit_predicate_is_a_failed_run(self) -> None:
        """cubic on #410: the predicate ran outside the guard, so its exception
        escaped, and Python's exit 1 would read as a negative verdict."""
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = verdict_cli.run(
                "example",
                dict,
                positive=lambda verdict: verdict["status"] == "ALLOW",
                input_errors=(ValueError,),
            )
        self.assertEqual(2, code)
        self.assertIn("KeyError", err.getvalue())

    def test_the_knowledge_cli_routes_merge_admission(self) -> None:
        from tools import cli

        self.assertIs(merge_admission.main, cli.COMMANDS["merge-admission"][1])


def _core_policy() -> dict[str, Any]:
    policy: dict[str, Any] = yaml.safe_load(
        (ROOT / "core" / "change-control.yaml").read_text(encoding="utf-8")
    )
    return policy


def _policy_project(base: Path, extends: list[str]) -> Path:
    """A project whose policy is the core policy, extending `extends`."""

    project = base / "project"
    (project / "policy").mkdir(parents=True)
    child = {**_core_policy(), "id": "example.child", "extends": extends}
    (project / "policy" / "change-control.yaml").write_text(
        yaml.safe_dump(child), encoding="utf-8"
    )
    return project


class PolicyLoadingTests(unittest.TestCase):
    """The effective policy is the candidate's own and is schema-valid (#410)."""

    def test_an_inherited_policy_outside_the_project_root_is_refused(self) -> None:
        """Codex and cubic on #410: only the entry path was confined."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "outside.yaml").write_text(
                yaml.safe_dump({**_core_policy(), "id": "example.outside"}),
                encoding="utf-8",
            )
            for name, extends in (
                ("traversal", ["../../outside.yaml"]),
                ("absolute", [str(base / "outside.yaml")]),
                ("symlink", ["../core.yaml"]),
            ):
                with self.subTest(name), tempfile.TemporaryDirectory(dir=base) as case:
                    project = _policy_project(Path(case), extends)
                    if name == "traversal":
                        (Path(case) / "outside.yaml").write_text(
                            (base / "outside.yaml").read_text(encoding="utf-8"),
                            encoding="utf-8",
                        )
                    os.symlink(base / "outside.yaml", project / "core.yaml")
                    with self.assertRaisesRegex(
                        assurance_completeness.AssuranceCompletenessError,
                        "relative|escapes",
                    ):
                        merge_admission.load_policy(
                            project / "policy" / "change-control.yaml",
                            project_root=project,
                        )

    def test_an_absolute_parent_reference_is_refused_even_inside_the_root(
        self,
    ) -> None:
        """Decision 0033 F: a parent reference is relative, wherever it points."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = _policy_project(base, [str(base / "project" / "core.yaml")])
            (project / "core.yaml").write_text(
                yaml.safe_dump({**_core_policy(), "id": "example.parent"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                assurance_completeness.AssuranceCompletenessError, "must be relative"
            ):
                merge_admission.load_policy(
                    project / "policy" / "change-control.yaml", project_root=project
                )

    def test_a_policy_outside_the_project_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = _policy_project(base, [])
            (base / "elsewhere").mkdir()
            with self.assertRaisesRegex(
                assurance_completeness.AssuranceCompletenessError,
                "outside the project root",
            ):
                merge_admission.load_policy(
                    project / "policy" / "change-control.yaml",
                    project_root=base / "elsewhere",
                )

    def test_an_inherited_policy_inside_the_project_root_is_followed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _policy_project(Path(directory), ["../core.yaml"])
            (project / "core.yaml").write_text(
                yaml.safe_dump({**_core_policy(), "id": "example.parent"}),
                encoding="utf-8",
            )
            policy = merge_admission.load_policy(
                project / "policy" / "change-control.yaml", project_root=project
            )
            self.assertEqual("example.child", policy["id"])

    def test_an_inheritance_chain_past_the_bound_is_refused(self) -> None:
        """CodeAnt on #410: an in-root chain was unbounded, so a long one reached
        the interpreter's recursion limit. One parent per policy means a real
        chain is a few levels deep."""
        with tempfile.TemporaryDirectory() as directory:
            project = _policy_project(Path(directory), ["../level-1.yaml"])
            depth = check_change_policy.MAX_INHERITANCE_DEPTH + 2
            for level in range(1, depth):
                parent = [f"level-{level + 1}.yaml"] if level + 1 < depth else []
                (project / f"level-{level}.yaml").write_text(
                    yaml.safe_dump(
                        {
                            **_core_policy(),
                            "id": f"example.level-{level}",
                            "extends": parent,
                        }
                    ),
                    encoding="utf-8",
                )
            with self.assertRaisesRegex(
                assurance_completeness.AssuranceCompletenessError, "deeper than"
            ):
                merge_admission.load_policy(
                    project / "policy" / "change-control.yaml", project_root=project
                )

    def test_the_inheritance_bound_is_exact(self) -> None:
        """Claude on #410: a chain of exactly the bound loads, one more file does
        not, so an off-by-one in the bound fails a test."""
        bound = check_change_policy.MAX_INHERITANCE_DEPTH
        for files, refused in ((bound, False), (bound + 1, True)):
            with self.subTest(files=files), tempfile.TemporaryDirectory() as directory:
                project = Path(directory)
                for level in range(files):
                    parent = [f"level-{level + 1}.yaml"] if level + 1 < files else []
                    (project / f"level-{level}.yaml").write_text(
                        yaml.safe_dump(
                            {
                                **_core_policy(),
                                "id": f"example.level-{level}",
                                "extends": parent,
                            }
                        ),
                        encoding="utf-8",
                    )
                entry = project / "level-0.yaml"
                if refused:
                    with self.assertRaisesRegex(KnowledgeFormatError, "deeper than"):
                        load_change_policy(entry, project_root=project)
                else:
                    policy = load_change_policy(entry, project_root=project)
                    self.assertEqual("example.level-0", policy["id"])

    def test_a_policy_outside_the_schema_is_refused(self) -> None:
        """cubic on #410: a malformed policy could disable required links."""
        with tempfile.TemporaryDirectory() as directory:
            project = _policy_project(Path(directory), [])
            path = project / "policy" / "change-control.yaml"
            policy = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy["change_classes"]["normal"]["decision_record"] = "true"
            path.write_text(yaml.safe_dump(policy), encoding="utf-8")
            with self.assertRaisesRegex(
                assurance_completeness.AssuranceCompletenessError, "decision_record"
            ):
                merge_admission.load_policy(path, project_root=project)


class GuardrailRegistrationTests(unittest.TestCase):
    def test_every_test_in_this_module_is_registered_in_its_guardrail(self) -> None:
        """cubic on #410: the CLI routing test was missing from the guardrail."""
        manifest = yaml.safe_load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        )
        (entry,) = [
            g for g in manifest["guardrails"] if g["id"] == "merge-admission-verdict"
        ]
        prefix = "tests/test_merge_admission.py::"
        registered = {t[len(prefix) :] for t in entry["tests"] if t.startswith(prefix)}
        defined = {
            f"{name}.{method}"
            for name, case in globals().items()
            if isinstance(case, type) and issubclass(case, unittest.TestCase)
            for method in unittest.defaultTestLoader.getTestCaseNames(case)
        }
        self.assertEqual(set(), defined - registered)


class GnostoaPolicyTests(unittest.TestCase):
    def test_gnostoa_s_effective_policy_drives_the_class_criterion(self) -> None:
        policy = load_change_policy(ROOT / "policy" / "change-control.yaml")
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        for change_class, needs_links in (
            ("normal", True),
            ("normative", True),
            ("critical", True),
        ):
            with self.subTest(change_class=change_class):
                evidence = _evidence()
                evidence["change_class"] = change_class
                evidence["links"] = {"work_items": [], "decisions": []}
                verdict = merge_admission.evaluate(
                    evidence, declaration=declaration, change_policy=policy
                )
                self.assertEqual(needs_links, "M14" in _failed(verdict))


# #389 F2 (the Router's exact-base continuation, 6192443314): under a 1.1
# declaration, M17's positive coverage is the completeness verdict the admission
# computes once; under 1.0 it stays the findings' own coverage.
CLAIMS_DECLARATION = {
    "schema_version": "1.1",
    "id": "example.required-evidence",
    "version": "0.2.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The required checks ran on the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["fast", "smoke"],
            "domains": {"fast": "ci", "smoke": "ci"},
        }
    ],
    "claims": [
        {
            "id": f"{item}-tests",
            "title": f"The {item} tests ran",
            "evidence": [{"requirement": "verification-checks", "item": item}],
            "independent_domains": dict.fromkeys(
                ["mechanical", "normal", "normative", "critical"], 1
            ),
        }
        for item in ("fast", "smoke")
    ],
}


def _claims_verdict(evidence: dict[str, Any]) -> dict[str, Any]:
    declaration = assurance_completeness.parse_declaration(CLAIMS_DECLARATION)
    return merge_admission.evaluate(
        evidence, declaration=declaration, change_policy=POLICY
    )


class ClaimsM17Tests(unittest.TestCase):
    def test_m17_s_coverage_is_the_verdict_under_1_1(self) -> None:
        """RED: a source the declaration does not require reads INCOMPLETE; its
        state stays in the evidence, and M17 follows the met claims."""
        for coverage in ("UNAVAILABLE", "INCOMPLETE", "PARTIAL"):
            with self.subTest(coverage=coverage):
                evidence = _evidence()
                evidence["analyzer_findings"]["coverage"] = coverage
                verdict = _claims_verdict(evidence)
                self.assertEqual("COMPLETE", verdict["completeness"]["status"])
                self.assertEqual({}, _failed(verdict))

    def test_m17_still_lists_and_vetoes_every_finding_under_1_1(self) -> None:
        """RED for the reasons: the findings are M17's only reason."""
        evidence = _evidence()
        evidence["analyzer_findings"] = {
            "coverage": "INCOMPLETE",
            "findings": [{"item": "deepsource-full", "id": "issue-1", "message": "x"}],
        }
        verdict = _claims_verdict(evidence)
        self.assertEqual({"M17": ["1 unresolved analyzer finding"]}, _failed(verdict))
        self.assertEqual(
            evidence["analyzer_findings"]["findings"],
            verdict["for_approval"]["analyzer_findings"],
        )

    def test_m17_holds_when_a_claim_is_not_met_under_1_1(self) -> None:
        """RED: a missing claim proof fails M2-M8, and today M17 passes on the
        findings' own coverage instead of the verdict."""
        evidence = _evidence()
        evidence["receipts"] = [_receipt(evidence["subject"], ["fast"])]
        failed = _failed(_claims_verdict(evidence))
        self.assertIn("M2-M8", failed)
        self.assertIn("M17", failed)

    def test_m17_keeps_its_1_0_rule(self) -> None:
        """Characterization: under 1.0 the findings' own coverage still gates M17,
        as `test_m17_denies_unless_the_findings_were_read_completely` pins."""
        evidence = _evidence()
        evidence["analyzer_findings"]["coverage"] = "INCOMPLETE"
        self.assertEqual(
            {"M17": ["analyzer finding coverage is INCOMPLETE"]},
            _failed(_verdict(evidence)),
        )


class DebtLedgerM17Tests(unittest.TestCase):
    """M17 with the protected target's debt ledger (#389, 6614843940): a finding that
    matches an entry exactly, by its item, rule, path, message and enclosing scope,
    is inherited debt, listed but not unresolved; anything else counts as before."""

    @staticmethod
    def _verdict(
        findings: list[dict[str, Any]], entries: list[dict[str, Any]]
    ) -> dict[str, Any]:
        evidence = _evidence()
        evidence["analyzer_findings"] = {"coverage": "COMPLETE", "findings": findings}
        evidence["analyzer_debt"] = {"coverage": "COMPLETE", "entries": entries}
        return _claims_verdict(evidence)

    def test_a_finding_matching_an_entry_is_inherited_and_still_listed(self) -> None:
        verdict = self._verdict([debt_finding()], [debt_entry()])
        self.assertEqual({}, _failed(verdict))
        self.assertEqual([debt_finding()], verdict["for_approval"]["analyzer_findings"])
        self.assertEqual(
            [{"item": "deepsource-full", "id": "issue-1", "ledger_entry": "debt-1"}],
            verdict["for_approval"]["inherited_findings"],
        )
        self.assertEqual([], verdict["for_approval"]["resolved_debt"])

    def test_any_other_identity_is_unresolved_and_only_a_finding_gone_resolves(
        self,
    ) -> None:
        """An entry is resolved only when no unmatched finding is left at its item,
        rule and path: one whose finding changed in place is not, since that finding
        still counts (Revix on #480)."""
        other_scope = {"kind": "function", "name": "f", "sha256": "e" * 64}
        # The finding moved away from the entry's item, rule or path.
        moved_away = {
            "another item",
            "another rule",
            "another path",
            "a scope but no rule",
        }
        for name, finding in (
            ("another item", debt_finding(item="codacy")),
            ("another rule", debt_finding(rule="PY-R1001")),
            ("another path", debt_finding(path="tools/y.py")),
            (
                "a worse measure",
                debt_finding(message="`f` has a cyclomatic complexity of 17"),
            ),
            ("a changed scope", debt_finding(enclosing=other_scope)),
            # The analyzer's identity at the entry's proof (PAO P2, 6614901388).
            ("another tool", debt_finding(tool={"id": "mypy"})),
            ("a named tool", debt_finding(tool={"id": "python", "name": "Python"})),
            ("no tool", {k: v for k, v in debt_finding().items() if k != "tool"}),
            # Owner 6620829215 §1: the baseline severity, exactly.
            ("a raised severity", debt_finding(severity="CRITICAL")),
            ("a lowered severity", debt_finding(severity="INFO")),
            (
                "no severity",
                {k: v for k, v in debt_finding().items() if k != "severity"},
            ),
            # §2: the run-bound configuration identity, exactly.
            (
                "another configuration",
                debt_finding(configuration=CONFIGURATION[:-1] + "c"),
            ),
            (
                "no configuration",
                {k: v for k, v in debt_finding().items() if k != "configuration"},
            ),
            (
                "no scope",
                {k: v for k, v in debt_finding().items() if k != "enclosing"},
            ),
            (
                "a scope but no rule",
                {k: v for k, v in debt_finding().items() if k != "rule"},
            ),
        ):
            with self.subTest(name):
                verdict = self._verdict([finding], [debt_entry()])
                self.assertEqual(
                    {"M17": ["1 unresolved analyzer finding"]}, _failed(verdict)
                )
                self.assertEqual([], verdict["for_approval"]["inherited_findings"])
                self.assertEqual(
                    ["debt-1"] if name in moved_away else [],
                    verdict["for_approval"]["resolved_debt"],
                )

    def test_a_matched_finding_leaves_another_entry_at_its_path_resolved(self) -> None:
        """A finding one entry absorbed does not answer for a second entry at the same
        item, rule and path whose own finding is gone (Revix on #480)."""
        second = debt_entry(
            id="debt-2", message="`f` has a cyclomatic complexity of 18"
        )
        verdict = self._verdict([debt_finding()], [debt_entry(), second])
        self.assertEqual({}, _failed(verdict))
        self.assertEqual(["debt-2"], verdict["for_approval"]["resolved_debt"])

    def test_a_repeated_finding_id_still_keeps_another_entry_unresolved(self) -> None:
        """Ids may repeat, so only the very finding an entry absorbed is set aside: a
        second finding with that id, at another entry's item, rule and path, still
        keeps that entry unresolved (cubic on #480)."""
        moved = debt_finding(path="tools/y.py")
        second = debt_entry(
            id="debt-2",
            path="tools/y.py",
            message="`f` has a cyclomatic complexity of 18",
        )
        verdict = self._verdict([debt_finding(), moved], [debt_entry(), second])
        self.assertEqual({"M17": ["1 unresolved analyzer finding"]}, _failed(verdict))
        self.assertEqual(
            [{"item": "deepsource-full", "id": "issue-1", "ledger_entry": "debt-1"}],
            verdict["for_approval"]["inherited_findings"],
        )
        self.assertEqual([], verdict["for_approval"]["resolved_debt"])

    def test_an_entry_without_a_tool_matches_only_a_finding_without_one(self) -> None:
        entry = {k: v for k, v in debt_entry().items() if k != "tool"}
        finding = {k: v for k, v in debt_finding().items() if k != "tool"}
        self.assertEqual({}, _failed(self._verdict([finding], [entry])))
        self.assertEqual(
            {"M17": ["1 unresolved analyzer finding"]},
            _failed(self._verdict([debt_finding()], [entry])),
        )

    def test_an_entry_recorded_without_severity_needs_a_finding_without_one(
        self,
    ) -> None:
        """A provider that states no severity: an explicit null matches only a
        finding without one, so a severity that appears unmatches it."""
        entry = debt_entry(severity=None)
        finding = {k: v for k, v in debt_finding().items() if k != "severity"}
        self.assertEqual({}, _failed(self._verdict([finding], [entry])))
        self.assertEqual(
            {"M17": ["1 unresolved analyzer finding"]},
            _failed(self._verdict([debt_finding()], [entry])),
        )

    def test_a_security_finding_is_never_inherited(self) -> None:
        """Whatever its entry says (PAO 6614901388): each provider's own security
        category, in any case, is repaired, never ledgered."""
        for category in ("SECURITY", "Security", "VULNERABILITY", "SECURITY_HOTSPOT"):
            with self.subTest(category):
                verdict = self._verdict(
                    [debt_finding(category=category)], [debt_entry()]
                )
                self.assertEqual(
                    {"M17": ["1 unresolved analyzer finding"]}, _failed(verdict)
                )
                self.assertEqual([], verdict["for_approval"]["inherited_findings"])
        self.assertEqual(
            {},
            _failed(
                self._verdict([debt_finding(category="PERFORMANCE")], [debt_entry()])
            ),
        )

    def test_an_inventory_security_rule_is_never_inherited(self) -> None:
        """Codex on #480: the project inventory's own security rules, such as
        unsafe-calls' S307, carry the producer's security category, so an exact entry
        that calls itself `correctness` still absorbs nothing."""
        produced = _original(quality_evidence, "_diagnostic_finding")(
            "ruff", "S307", "tools/x.py", (3, 1, 3, 9), "eval", {}
        )
        category = {"category": produced["category"]} if "category" in produced else {}
        finding = debt_finding(rule="S307", tool={"id": "ruff"}, **category)
        entry = debt_entry(rule="S307", tool={"id": "ruff"}, aspect="correctness")
        verdict = self._verdict([finding], [entry])
        self.assertEqual({"M17": ["1 unresolved analyzer finding"]}, _failed(verdict))
        self.assertEqual([], verdict["for_approval"]["inherited_findings"])

    def test_an_entry_absorbs_one_finding(self) -> None:
        verdict = self._verdict(
            [debt_finding(), debt_finding(id="issue-2")], [debt_entry()]
        )
        self.assertEqual({"M17": ["1 unresolved analyzer finding"]}, _failed(verdict))
        self.assertEqual(1, len(verdict["for_approval"]["inherited_findings"]))

    def test_without_complete_required_evidence_nothing_is_matched(self) -> None:
        evidence = _evidence()
        evidence["analyzer_findings"] = {
            "coverage": "COMPLETE",
            "findings": [debt_finding()],
        }
        # The second entry's finding is gone, so a complete read would resolve it.
        gone = debt_entry(id="debt-2", path="tools/gone.py")
        evidence["analyzer_debt"] = {
            "coverage": "COMPLETE",
            "entries": [debt_entry(), gone],
        }
        evidence["receipts"] = [_receipt(evidence["subject"], ["fast"])]
        verdict = _claims_verdict(evidence)
        self.assertIn("1 unresolved analyzer finding", _failed(verdict)["M17"])
        self.assertEqual([], verdict["for_approval"]["inherited_findings"])
        # And no entry is called resolved on a read that is not complete.
        self.assertEqual([], verdict["for_approval"]["resolved_debt"])

    def test_without_a_ledger_m17_is_as_it_was(self) -> None:
        for name, debt in (
            ("no record", None),
            ("no ledger on the target", {"coverage": "UNAVAILABLE", "entries": []}),
            ("an empty ledger", {"coverage": "COMPLETE", "entries": []}),
        ):
            with self.subTest(name):
                evidence = _evidence()
                evidence["analyzer_findings"] = {
                    "coverage": "COMPLETE",
                    "findings": [debt_finding()],
                }
                if debt is not None:
                    evidence["analyzer_debt"] = debt
                self.assertEqual(
                    {"M17": ["1 unresolved analyzer finding"]},
                    _failed(_claims_verdict(evidence)),
                )

    def test_the_analyzer_debt_has_a_closed_contract(self) -> None:
        entry = debt_entry()
        for name, debt in (
            ("an unknown field", {"coverage": "COMPLETE", "entries": [], "x": 1}),
            ("an unknown coverage", {"coverage": "PARTIAL", "entries": []}),
            # Claude and cubic on #480: refused, not an unhashable TypeError.
            ("a coverage that is not text", {"coverage": ["COMPLETE"], "entries": []}),
            (
                "entries without a ledger",
                {"coverage": "UNAVAILABLE", "entries": [entry]},
            ),
            ("entries that are not a list", {"coverage": "COMPLETE", "entries": {}}),
            *(
                (name, {"coverage": "COMPLETE", "entries": [value]})
                for name, value in (
                    (
                        "an entry missing its rule",
                        {k: v for k, v in entry.items() if k != "rule"},
                    ),
                    ("an entry with an unknown field", {**entry, "x": "y"}),
                    ("an empty message", {**entry, "message": ""}),
                    (
                        "a scope that is not a digest",
                        {**entry, "enclosing_sha256": "C" * 64},
                    ),
                    ("an unknown aspect", {**entry, "aspect": "taste"}),
                    ("an aspect that is not text", {**entry, "aspect": ["complexity"]}),
                    ("a tool that is not an object", {**entry, "tool": "python"}),
                    ("a tool without its id", {**entry, "tool": {"name": "Python"}}),
                    (
                        "a tool with an unknown field",
                        {**entry, "tool": {"id": "py", "x": "y"}},
                    ),
                    ("a tool that is null", {**entry, "tool": None}),
                    (
                        "an entry missing its severity",
                        {k: v for k, v in entry.items() if k != "severity"},
                    ),
                    ("a severity that is not text", {**entry, "severity": 7}),
                    ("an empty severity", {**entry, "severity": ""}),
                    (
                        "an entry missing its configuration",
                        {k: v for k, v in entry.items() if k != "configuration"},
                    ),
                    ("an empty configuration", {**entry, "configuration": ""}),
                    ("a configuration that is null", {**entry, "configuration": None}),
                    ("a tool with an empty id", {**entry, "tool": {"id": ""}}),
                    (
                        "a tool name that is not text",
                        {**entry, "tool": {"id": "python", "name": 7}},
                    ),
                    ("a security finding", {**entry, "aspect": "security"}),
                    (
                        "a commit that is not exact",
                        {
                            **entry,
                            "provenance": {**entry["provenance"], "commit": "d" * 39},
                        },
                    ),
                    (
                        "provenance with an unknown field",
                        {**entry, "provenance": {**entry["provenance"], "x": "y"}},
                    ),
                )
            ),
            (
                "two entries with one id",
                {"coverage": "COMPLETE", "entries": [entry, entry]},
            ),
        ):
            evidence = _evidence()
            evidence["analyzer_debt"] = debt
            with (
                self.subTest(name),
                self.assertRaises(assurance_completeness.AssuranceCompletenessError),
            ):
                _claims_verdict(evidence)

    def test_a_finding_s_configuration_is_text(self) -> None:
        for name, value in (("empty", ""), ("not text", 7), ("null", None)):
            evidence = _evidence()
            evidence["analyzer_findings"] = {
                "coverage": "COMPLETE",
                "findings": [debt_finding(configuration=value)],
            }
            with (
                self.subTest(name),
                self.assertRaises(assurance_completeness.AssuranceCompletenessError),
            ):
                _claims_verdict(evidence)

    def test_a_finding_s_enclosing_scope_is_closed(self) -> None:
        scope = {"kind": "function", "name": "f", "sha256": _SCOPE}
        for name, value in (
            ("an unknown kind", {**scope, "kind": "module"}),
            ("an unknown field", {**scope, "x": "y"}),
            ("a digest that is not one", {**scope, "sha256": "x"}),
            ("not an object", "f"),
        ):
            evidence = _evidence()
            evidence["analyzer_findings"] = {
                "coverage": "COMPLETE",
                "findings": [debt_finding(enclosing=value)],
            }
            with (
                self.subTest(name),
                self.assertRaises(assurance_completeness.AssuranceCompletenessError),
            ):
                _claims_verdict(evidence)


# The 1.0 items the parity guard enumerates, by their 1.0 names.
_PARITY_DEEPSOURCE = frozenset(
    {
        ("analyzer-readback", "deepsource-diff"),
        ("analyzer-readback", "deepsource-full"),
    }
)
_PARITY_ANALYZERS = frozenset(
    {
        ("analyzer-readback", "deepsource-diff"),
        ("analyzer-readback", "deepsource-full"),
        ("analyzer-readback", "codacy"),
        ("sonarcloud", "issue-inventory"),
    }
)


def _parity_evidence(
    change_class: str, items: list[tuple[str, str]], down: set[tuple[str, str]]
) -> dict[str, Any]:
    """A converged change of the class, with one receipt per item: unavailable
    when `down` names it, and the findings' coverage as the readback gives it."""

    evidence = _evidence()
    evidence["change_class"] = change_class
    evidence["receipts"] = [
        {
            **_receipt(evidence["subject"], [item]),
            "requirement": requirement,
            "status": "UNAVAILABLE" if (requirement, item) in down else "COMPLETE",
        }
        for requirement, item in items
    ]
    evidence["analyzer_findings"]["coverage"] = (
        "INCOMPLETE" if down & _PARITY_ANALYZERS else "COMPLETE"
    )
    return evidence


def _successor(evidence: dict[str, Any]) -> dict[str, Any]:
    """The same evidence under Decision 0130's declaration: DeepSource, retired as
    merge evidence, gives no receipt, and the project's two inventory receipts are
    complete."""

    receipts = [
        receipt
        for receipt in evidence["receipts"]
        if (receipt["requirement"], receipt["coverage"][0]) not in _PARITY_DEEPSOURCE
    ]
    receipts += [
        {
            **_receipt(evidence["subject"], [item]),
            "requirement": "project-risk-readback",
            "status": "COMPLETE",
        }
        for item in ("project-diff", "project-full")
    ]
    return {**evidence, "receipts": receipts}


class AnalyzerRetirementTests(unittest.TestCase):
    """The DeepSource exit (#389, Decision 0130): the evidence names each provider it
    retires, and the verdict lists them for the approver, so a retired provider is
    never read as an unavailable one."""

    def test_the_verdict_lists_each_retired_provider(self) -> None:
        evidence = _evidence()
        evidence["analyzer_retired"] = [{"provider": "deepsource", "decision": "0130"}]
        verdict = _claims_verdict(evidence)
        self.assertEqual(
            [{"provider": "deepsource", "decision": "0130"}],
            verdict["for_approval"]["retired_analyzers"],
        )

    def test_the_retirement_has_a_closed_contract(self) -> None:
        for name, value in (
            ("not a list", {"provider": "deepsource", "decision": "0130"}),
            (
                "an unknown key",
                [{"provider": "deepsource", "decision": "0130", "x": 1}],
            ),
            ("no decision", [{"provider": "deepsource"}]),
            ("an empty provider", [{"provider": "", "decision": "0130"}]),
            ("an empty decision", [{"provider": "deepsource", "decision": " "}]),
            (
                "a repeated provider",
                [{"provider": "deepsource", "decision": "0130"}] * 2,
            ),
        ):
            with self.subTest(name):
                evidence = _evidence()
                evidence["analyzer_retired"] = value
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _claims_verdict(evidence)
        # And the record is required, though it may name none.
        evidence = _evidence()
        del evidence["analyzer_retired"]
        with self.assertRaisesRegex(
            assurance_completeness.AssuranceCompletenessError, "analyzer_retired"
        ):
            _claims_verdict(evidence)
        evidence = _evidence()
        evidence["analyzer_retired"] = []
        self.assertEqual(
            [], _claims_verdict(evidence)["for_approval"]["retired_analyzers"]
        )


class GnostoaDecisionParityTests(unittest.TestCase):
    def test_the_real_policy_keeps_every_merge_decision(self) -> None:
        """Guard for F2's singleton migration: over every combination of complete
        and unavailable items, for every merging class, the real declaration gives
        the decision its 1.0 form (main 935ea6c) gave. M17 may add only its
        coverage reason, and only where M2-M8 already fails.

        Every class diverges by design, as NORMAL already did under section C (#389
        A0-MP1 slice 3, 6381812211): DeepSource is no class's required coverage evidence
        (Decision 0130; since Decision 0132 an optional provider, read for findings
        only), so with the project's inventory complete
        each class gets 1.0's decision as if DeepSource were complete. The project's
        items are therefore
        not in the 1.0 enumeration, which has no such item (Amazon Q on #461): this
        guard holds only the decisions that must not change. A class with the
        inventory missing or partial is denied by
        `test_merge_evidence_github.DeepSourceRetirementTests`."""
        from tests.assurance_completeness_support import GNOSTOA_1_0

        baseline = assurance_completeness.parse_declaration(GNOSTOA_1_0)
        current = assurance_completeness.load_declaration(
            ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
        )
        items = [
            (requirement["id"], item)
            for requirement in GNOSTOA_1_0["requirements"]
            for item in requirement["coverage"]
        ]
        wrong = []
        decisions: dict[tuple[int, str], tuple[str, str]] = {}
        for mask in range(2 ** len(items)):
            down = {pair for index, pair in enumerate(items) if mask >> index & 1}
            for change_class in ("mechanical", "normal", "normative", "critical"):
                old_down = down - _PARITY_DEEPSOURCE
                old = merge_admission.evaluate(
                    _parity_evidence(change_class, items, old_down),
                    declaration=baseline,
                    change_policy=POLICY,
                )
                new = merge_admission.evaluate(
                    _successor(_parity_evidence(change_class, items, down)),
                    declaration=current,
                    change_policy=POLICY,
                )
                old_failed, new_failed = set(_failed(old)), set(_failed(new))
                extra = {"M17"} if "M2-M8" in old_failed else set()
                if old["status"] != new["status"] or not (
                    old_failed <= new_failed <= old_failed | extra
                ):
                    wrong.append((change_class, sorted(down), old_failed, new_failed))
                decisions[(mask, change_class)] = (old["status"], new["status"])
        self.assertEqual([], wrong)
        # The guard's positive control (the Router's 6192773699): with every other
        # criterion valid, all ten items complete ALLOW in each class, and any one
        # missing item DENYs, so the comparison above is never vacuous. A missing
        # DeepSource item no longer DENYs any class: DeepSource is retired.
        for change_class in ("mechanical", "normal", "normative", "critical"):
            with self.subTest(change_class=change_class):
                self.assertEqual(("ALLOW", "ALLOW"), decisions[(0, change_class)])
                for index, pair in enumerate(items):
                    expected = (
                        ("ALLOW", "ALLOW")
                        if pair in _PARITY_DEEPSOURCE
                        else ("DENY", "DENY")
                    )
                    self.assertEqual(expected, decisions[(1 << index, change_class)])


if __name__ == "__main__":
    unittest.main()
