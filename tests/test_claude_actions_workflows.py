from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.knowledge_common import load_yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REVIEW_WORKFLOW = WORKFLOWS / "claude-code-review.yml"
MENTION_WORKFLOW = WORKFLOWS / "claude.yml"

_PINNED_USES = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$")
_TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
_ASSOCIATION_FIELDS = (
    "github.event.comment.author_association",
    "github.event.review.author_association",
    "github.event.issue.author_association",
)
# Decision 0094: agent mode fetches no GitHub data, so every context byte the
# reviewer receives is interpolated here. Only sources whose size is independent
# of the discussion length are admitted.
_BOUNDED_PROMPT_SOURCES = frozenset(
    {
        "github.repository",
        "github.event.issue.number",
        "github.event.pull_request.number",
        "github.event.pull_request.head.sha",
        "github.event.pull_request.base.sha",
        "github.event.pull_request.body",
        "github.event.comment.body",
        "github.event.issue.body",
        "github.event.review.body",
        "steps.review_head.outputs.base_sha",
        "steps.review_head.outputs.head_sha",
        "github.event.comment.path",
        "github.event.comment.line",
        "github.event.comment.diff_hunk",
        "github.event.issue.title",
    }
)
_PROMPT_EXPRESSION = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")
_MAX_STATIC_PROMPT_BYTES = 4096


def _workflow_paths(directory: Path) -> list[Path]:
    # GitHub Actions loads both extensions from .github/workflows.
    return sorted(
        path for pattern in ("*.yml", "*.yaml") for path in directory.glob(pattern)
    )


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def _action_references(workflow: dict[str, Any]) -> list[str]:
    references = [job["uses"] for job in workflow["jobs"].values() if "uses" in job]
    references.extend(step["uses"] for step in _steps(workflow) if "uses" in step)
    return references


def _claude_step(workflow: dict[str, Any]) -> dict[str, Any]:
    return next(
        step
        for step in _steps(workflow)
        if step.get("uses", "").startswith("anthropics/claude-code-action@")
    )


def _single_job(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = list(workflow["jobs"].values())
    if len(jobs) != 1:
        raise AssertionError(f"expected exactly one job, found {len(jobs)}")
    return jobs[0]


class WorkflowEnumerationTests(unittest.TestCase):
    def test_workflow_paths_cover_both_github_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a.yml", "b.yaml", "c.json"):
                (root / name).write_text("", encoding="utf-8")
            self.assertEqual(
                ["a.yml", "b.yaml"],
                [path.name for path in _workflow_paths(root)],
            )

    def test_action_references_include_reusable_workflow_jobs(self) -> None:
        workflow = {
            "jobs": {
                "call": {"uses": "owner/repo/.github/workflows/x.yml@main"},
                "run": {"steps": [{"uses": "owner/action@v1"}, {"run": "true"}]},
            }
        }
        self.assertEqual(
            ["owner/repo/.github/workflows/x.yml@main", "owner/action@v1"],
            _action_references(workflow),
        )


class ClaudeActionsWorkflowTests(unittest.TestCase):
    def test_every_workflow_action_is_pinned_to_a_full_commit_sha(self) -> None:
        for path in _workflow_paths(WORKFLOWS):
            for uses in _action_references(load_yaml(path)):
                if uses.startswith("./"):
                    continue
                with self.subTest(workflow=path.name, uses=uses):
                    self.assertRegex(uses, _PINNED_USES)

    def test_claude_checkouts_do_not_persist_credentials(self) -> None:
        for path in (REVIEW_WORKFLOW, MENTION_WORKFLOW):
            checkouts = [
                step
                for step in _steps(load_yaml(path))
                if step.get("uses", "").startswith("actions/checkout@")
            ]
            self.assertTrue(checkouts, path.name)
            for step in checkouts:
                with self.subTest(workflow=path.name, step=step.get("name")):
                    self.assertIs(
                        False, step.get("with", {}).get("persist-credentials")
                    )

    def test_claude_workflows_keep_minimal_token_permissions(self) -> None:
        expected = {
            REVIEW_WORKFLOW: {
                "contents": "read",
                "pull-requests": "read",
                "issues": "read",
                "id-token": "write",
            },
            MENTION_WORKFLOW: {
                "contents": "read",
                "pull-requests": "read",
                "issues": "read",
                "id-token": "write",
                "actions": "read",
            },
        }
        for path, permissions in expected.items():
            with self.subTest(workflow=path.name):
                workflow = load_yaml(path)
                self.assertNotIn("permissions", workflow)
                self.assertEqual(permissions, _single_job(workflow)["permissions"])

    def test_review_job_skips_forks_and_drafts_and_cancels_stale_runs(self) -> None:
        workflow = load_yaml(REVIEW_WORKFLOW)
        job = _single_job(workflow)
        condition = " ".join(job["if"].split())
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            condition,
        )
        self.assertIn("!github.event.pull_request.draft", condition)
        self.assertEqual(
            {
                "group": "claude-code-review-${{ github.event.pull_request.number }}",
                "cancel-in-progress": True,
            },
            workflow["concurrency"],
        )
        self.assertIsInstance(job.get("timeout-minutes"), int)

    def test_review_plugin_marketplace_is_a_pinned_local_checkout(self) -> None:
        steps = _steps(load_yaml(REVIEW_WORKFLOW))
        marketplace_checkouts = [
            step
            for step in steps
            if step.get("uses", "").startswith("actions/checkout@")
            and step.get("with", {}).get("repository") == "anthropics/claude-code"
        ]
        self.assertEqual(1, len(marketplace_checkouts))
        checkout = marketplace_checkouts[0]["with"]
        self.assertRegex(str(checkout.get("ref")), r"^[0-9a-f]{40}$")
        claude = next(
            step
            for step in steps
            if step.get("uses", "").startswith("anthropics/claude-code-action@")
        )
        marketplace = claude["with"]["plugin_marketplaces"]
        self.assertNotIn("://", marketplace)
        self.assertEqual(
            "${{ github.workspace }}/" + checkout["path"], marketplace.strip()
        )

    def test_mention_job_requires_trusted_author_association(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        job = _single_job(workflow)
        condition = " ".join(job["if"].split())
        for field in _ASSOCIATION_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, condition)
        for association in _TRUSTED_ASSOCIATIONS:
            self.assertIn(association, condition)
        self.assertIsInstance(job.get("timeout-minutes"), int)
        # A shared group would let an unrelated comment replace a pending request.
        self.assertNotIn("concurrency", workflow)
        self.assertNotIn("concurrency", job)

    def test_mention_job_runs_in_bounded_agent_mode(self) -> None:
        # src/modes/detector.ts selects agent mode when a prompt input is present,
        # including on comment events; src/modes/agent/index.ts then fetches no
        # GitHub data. Tag mode instead retrieves every comment and review with no
        # cap, which is what exhausted the request on a large Pull Request.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        prompt = claude["with"].get("prompt")
        self.assertIsInstance(
            prompt, str, "mention job must supply a prompt to select agent mode"
        )
        self.assertTrue(prompt.strip())

    def test_mention_prompt_interpolates_only_bounded_sources(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        used = {match.group(1).strip() for match in _PROMPT_EXPRESSION.finditer(prompt)}
        unbounded = used - _BOUNDED_PROMPT_SOURCES
        self.assertEqual(
            set(),
            unbounded,
            "prompt interpolates sources whose size grows with the discussion",
        )

    def test_mention_prompt_carries_the_triggering_request(self) -> None:
        # Agent mode ignores the comment body unless the template forwards it,
        # so an unforwarded mention would silently review nothing.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("github.event.comment.body", prompt)

    def test_mention_prompt_is_statically_bounded(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertLessEqual(len(prompt.encode("utf-8")), _MAX_STATIC_PROMPT_BYTES)

    def test_mention_job_replaces_the_tag_mode_tracking_comment(self) -> None:
        # Agent mode sets claudeCommentId to undefined, so results need an
        # explicit delivery path rather than the tag-mode tracking comment.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        self.assertEqual("true", str(claude["with"].get("display_report")).lower())

    def test_mention_checkout_binds_the_reviewed_pull_request_head(self) -> None:
        # Agent mode does no PR resolution of its own. On a comment event the
        # default checkout lands on the default branch, so an unbound ref would
        # make the reviewer diff main against itself and report nothing.
        workflow = load_yaml(MENTION_WORKFLOW)
        checkout = next(
            step
            for step in _steps(workflow)
            if step.get("uses", "").startswith("actions/checkout@")
        )
        ref = " ".join(str(checkout["with"]["ref"]).split())
        # Superseded by the same-repository guard: the head is resolved with the
        # read-only token rather than taken from the event payload, so the
        # assertion is on the binding, not on a particular payload field.
        self.assertIn("steps.review_head.outputs.head_sha", ref)
        resolve = next(
            step for step in _steps(workflow) if step.get("id") == "review_head"
        )
        run = str(resolve["run"])
        self.assertIn("PULL_NUMBER", run)
        self.assertIn("GITHUB_OUTPUT", run)
        self.assertEqual(0, str(checkout["with"]["fetch-depth"]).count("1"))

    def test_mention_prompt_covers_every_admitted_trigger_payload(self) -> None:
        # issue_comment carries github.event.issue.*; the review triggers carry
        # github.event.pull_request.*; issues:opened may put the mention in the
        # title alone. A template that reads only one shape silently loses the
        # other two.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        for expression in (
            "github.event.issue.number",
            "github.event.pull_request.number",
            "github.event.issue.body",
            "github.event.pull_request.body",
            "github.event.issue.title",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, prompt)

    def test_mention_job_never_checks_out_a_fork_controlled_head(self) -> None:
        # Binding the checkout to a Pull Request head puts contributor-controlled
        # code in the job that holds the Claude credential. Decision 0093 rule 5
        # already restricts the automatic review to same-repository heads; the
        # mention job must reach the same boundary, and its author-association
        # gate does not, because it constrains who comments rather than whose code
        # is checked out.
        workflow = load_yaml(MENTION_WORKFLOW)
        text = MENTION_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.repository", text)
        guard = [
            step
            for step in _steps(workflow)
            if "full_name" in str(step.get("run", "")) + str(step.get("if", ""))
        ]
        self.assertTrue(
            guard, "mention job needs an explicit same-repository head guard"
        )
        checkout = next(
            step
            for step in _steps(workflow)
            if step.get("uses", "").startswith("actions/checkout@")
        )
        ref = str(checkout["with"]["ref"])
        # The ref must come from the guarded resolution, not straight from the
        # untrusted event payload.
        self.assertIn("steps.review_head.outputs", ref)
        self.assertNotIn("refs/pull/", ref)

    def test_mention_prompt_names_the_declared_entry_route(self) -> None:
        # AGENTS.md itself begins "Start with README.md"; sending the reviewer
        # somewhere else skips the router the repository declares.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("README.md", prompt)

    def test_mention_prompt_diffs_against_the_resolved_base(self) -> None:
        # A hardcoded branch is wrong for any Pull Request that does not target it.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("steps.review_head.outputs.base_sha", prompt)
        self.assertNotIn("origin/main", prompt)

    def test_mention_job_grants_the_read_only_git_tools_the_prompt_requires(
        self,
    ) -> None:
        # The pinned action disables Bash by default, so a prompt that tells the
        # reviewer to run git would leave it with a checkout it cannot inspect.
        # Only read-only git verbs are granted: a broad Bash(git:*) would admit
        # push, commit and reset.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        args = str(claude["with"].get("claude_args", ""))
        self.assertIn("--allowedTools", args)
        for verb in ("git diff", "git log", "git show"):
            with self.subTest(verb=verb):
                self.assertIn(f"Bash({verb}:*)", args)
        for forbidden in ("git push", "git commit", "git reset", "Bash(git:*)"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, args)

    def test_mention_prompt_handles_a_request_with_no_pull_request(self) -> None:
        # issues:opened is an admitted trigger and Decision 0093 rule 7 keeps it.
        # With no Pull Request the resolved base equals the head, so a diff-shaped
        # instruction would have nothing to compare.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        self.assertIn("no Pull Request", prompt)
        # The instruction is only actionable if both sides are actually shown.
        self.assertIn("steps.review_head.outputs.head_sha", prompt)

    def test_mention_prompt_forwards_inline_review_location(self) -> None:
        # On pull_request_review_comment the request's meaning often lives in the
        # comment's path, line and hunk rather than its body.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        for expression in (
            "github.event.comment.path",
            "github.event.comment.line",
            "github.event.comment.diff_hunk",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, prompt)

    def test_decision_0094_rules_are_numbered_in_order(self) -> None:
        decision = (
            ROOT / "knowledge" / "decisions" / "0094-bound-claude-review-context.md"
        ).read_text(encoding="utf-8")
        numbers = [
            int(match.group(1))
            for match in re.finditer(r"^(\d+)\. ", decision, re.MULTILINE)
        ]
        self.assertEqual(sorted(numbers), numbers)
        self.assertEqual(list(range(1, len(numbers) + 1)), numbers)

    def test_decision_0094_records_its_partial_supersession_of_0093(self) -> None:
        # The read-only git grant overrides the tool clause of Decision 0093
        # rule 8. Leaving both records asserting their own version would give an
        # auditor two contradictory security contracts.
        path = ROOT / "knowledge" / "decisions" / "0094-bound-claude-review-context.md"
        decision = path.read_text(encoding="utf-8")
        self.assertIn("supersedes", decision)
        self.assertIn(
            "0093-harden-claude-code-github-actions-workflows.md",
            decision,
        )
        normalised = " ".join(decision.split())
        self.assertIn("rule 8", normalised)
        # The superseded claim must be gone, not merely contradicted later.
        self.assertNotIn("Decision 0093's eight hardening rules", normalised)
        self.assertNotIn("its eight hardening rules and", normalised)

    def test_mention_workflow_has_no_unconfigured_assignment_trigger(self) -> None:
        # Without an assignee_trigger input the action never runs Claude for
        # `issues: assigned`; the trigger would only start an idle job.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = next(
            step
            for step in _steps(workflow)
            if step.get("uses", "").startswith("anthropics/claude-code-action@")
        )
        self.assertNotIn("assignee_trigger", claude["with"])
        self.assertEqual({"types": ["opened"]}, workflow[True]["issues"])

    def test_guardrail_owns_claude_workflows_and_their_test(self) -> None:
        guardrails = load_yaml(ROOT / "policy" / "guardrails.yaml")
        entry = next(
            item
            for item in guardrails["guardrails"]
            if item["id"] == "immutable-provider-ci-adapters"
        )
        for path in (
            ".github/workflows/claude-code-review.yml",
            ".github/workflows/claude.yml",
            "knowledge/decisions/0093-harden-claude-code-github-actions-workflows.md",
            "knowledge/decisions/0094-bound-claude-review-context.md",
        ):
            self.assertIn(path, entry["implementation"])
        self.assertIn("tests/test_claude_actions_workflows.py", entry["tests"])


if __name__ == "__main__":
    unittest.main()
