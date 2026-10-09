from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tools import assurance_completeness, merge_admission
from tools.check_change_policy import load_change_policy

ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40
PREVIOUS = "b" * 40
SUBJECT = {
    "repository": "https://github.com/example/project",
    "change_request": {"kind": "github-pull-request", "id": "7"},
    "head_commit": HEAD,
}
DECLARATION = {
    "schema_version": "1.0",
    "id": "example.required-evidence",
    "version": "0.1.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The required checks ran on the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["fast", "smoke"],
        }
    ],
}
POLICY = {
    "change_classes": {
        "mechanical": {},
        "normal": {"work_item": "required", "decision_record": True},
        "normative": {"work_item": "required", "decision_record": True},
        "critical": {"work_item": "required", "decision_record": True},
        "emergency": {},
    }
}


def _receipt(subject: dict[str, Any], coverage: list[str]) -> dict[str, Any]:
    return {
        "schema": "gnostoa-evidence-receipt/v1",
        "requirement": "verification-checks",
        "subject": subject,
        "producer": "checks",
        "observed_at": "2026-10-09T08:00:00Z",
        "status": "COMPLETE",
        "coverage": coverage,
    }


def _evidence(subject: dict[str, Any] | None = None) -> dict[str, Any]:
    exact = copy.deepcopy(SUBJECT if subject is None else subject)
    return {
        "subject": exact,
        "lifecycle": {
            "state": "open",
            "draft": False,
            "target": "main",
            "protected_target": "main",
        },
        "change_class": "normal",
        "links": {"work_items": ["#407"], "decisions": ["0112"]},
        "declared_candidate": {"declarer": "agent-app", "head_commit": HEAD},
        "authorities": {"declarer": "agent-app", "required_approvers": ["owner"]},
        "reviews": [
            {
                "reviewer": "owner",
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:00:00Z",
            }
        ],
        "threads": {"coverage": "COMPLETE", "unresolved": 0},
        "closing_references": {"coverage": "COMPLETE", "found": []},
        "suppressions": [],
        "trust_root_changes": [],
        "receipts": [_receipt(exact, ["fast", "smoke"])],
    }


def _verdict(evidence: dict[str, Any]) -> dict[str, Any]:
    declaration = assurance_completeness.parse_declaration(DECLARATION)
    return merge_admission.evaluate(
        evidence, declaration=declaration, change_policy=POLICY
    )


def _failed(verdict: dict[str, Any]) -> dict[str, list[str]]:
    return {c["id"]: c["reasons"] for c in verdict["criteria"] if c["status"] == "FAIL"}


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
        evidence["suppressions"] = [justified]
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual([justified], verdict["for_approval"]["suppressions"])
        evidence["suppressions"].append(unjustified)
        self.assertDenied(evidence, "M13")

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
        evidence["trust_root_changes"] = [".github/workflows/verification.yml"]
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual(
            [".github/workflows/verification.yml"],
            verdict["for_approval"]["trust_root_changes"],
        )

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


def _run(text: str, *, declaration: object | None = DECLARATION) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "policy").mkdir()
        if declaration is not None:
            (root / "policy" / "assurance-evidence.yaml").write_text(
                json.dumps(declaration), encoding="utf-8"
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
        code, output = _run(json.dumps(_evidence()), declaration=None)
        self.assertEqual(2, code)
        self.assertIn("assurance", output.lower())

    def test_invalid_input_exits_two(self) -> None:
        for text in ("[]", "not json", json.dumps({"subject": SUBJECT})):
            with self.subTest(text=text):
                self.assertEqual(2, _run(text)[0])

    def test_the_knowledge_cli_routes_merge_admission(self) -> None:
        from tools import cli

        self.assertIs(merge_admission.main, cli.COMMANDS["merge-admission"][1])


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


if __name__ == "__main__":
    unittest.main()
