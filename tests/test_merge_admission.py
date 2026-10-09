from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from tools import assurance_completeness, merge_admission, verdict_cli
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
_APPROVED_BY_ONE_INDEPENDENT_HUMAN = {
    "minimum_approvals": 1,
    "independent_approval": True,
    "human_approval": True,
    "code_owner_approval": True,
}
POLICY = {
    "change_classes": {
        "mechanical": {
            "work_item": "optional",
            "decision_record": False,
            **_APPROVED_BY_ONE_INDEPENDENT_HUMAN,
        },
        **{
            name: {
                "work_item": "required",
                "decision_record": True,
                **_APPROVED_BY_ONE_INDEPENDENT_HUMAN,
            }
            for name in ("normal", "normative", "critical")
        },
        "emergency": {
            "work_item": "required-follow-up",
            "decision_record": True,
            "minimum_approvals": 0,
            "independent_approval": False,
            "human_approval": False,
            "code_owner_approval": False,
        },
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
        "authorities": {
            "declarer": "agent-app",
            "author": "agent-user",
            "required_approvers": ["owner"],
        },
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
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    merge_admission.evaluate(
                        _evidence(), declaration=declaration, change_policy=policy
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

    def test_m16_the_class_minimum_of_approvals_applies(self) -> None:
        policy = copy.deepcopy(POLICY)
        policy["change_classes"]["normal"]["minimum_approvals"] = 2
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        verdict = merge_admission.evaluate(
            _evidence(), declaration=declaration, change_policy=policy
        )
        self.assertEqual("DENY", verdict["status"])
        self.assertIn("M16", _failed(verdict))

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


if __name__ == "__main__":
    unittest.main()
