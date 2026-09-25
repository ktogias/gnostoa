from __future__ import annotations

import re
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


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def _single_job(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = list(workflow["jobs"].values())
    assert len(jobs) == 1
    return jobs[0]


class ClaudeActionsWorkflowTests(unittest.TestCase):
    def test_every_workflow_action_is_pinned_to_a_full_commit_sha(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            for step in _steps(load_yaml(path)):
                uses = step.get("uses")
                if uses is None or uses.startswith("./"):
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
        ):
            self.assertIn(path, entry["implementation"])
        self.assertIn("tests/test_claude_actions_workflows.py", entry["tests"])


if __name__ == "__main__":
    unittest.main()
