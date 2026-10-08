"""The merge gate's record states the policy in force, and agents are routed to it
(Decision 0110, #398)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "knowledge" / "runbooks" / "operate-the-merge-gate.md"
DECISION = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md"
)


class MergeGateRecordTests(unittest.TestCase):
    def _rules(self) -> dict[str, dict[str, object]]:
        text = RUNBOOK.read_text(encoding="utf-8")
        block = re.search(r"```json\n(\[.*?\])\n```", text, re.S)
        self.assertIsNotNone(block, "the runbook records R-main's rules as JSON")
        assert block is not None
        rules = json.loads(block.group(1))
        return {rule["type"]: rule.get("parameters", {}) for rule in rules}

    def test_r_main_requires_the_code_owner_s_approval_of_the_exact_head(self) -> None:
        pull_request = self._rules()["pull_request"]
        self.assertEqual(1, pull_request["required_approving_review_count"])
        for flag in (
            "require_code_owner_review",
            "dismiss_stale_reviews_on_push",
            "require_last_push_approval",
            "required_review_thread_resolution",
        ):
            with self.subTest(flag=flag):
                self.assertIs(True, pull_request[flag])
        self.assertEqual(["squash"], pull_request["allowed_merge_methods"])

    def test_r_main_requires_the_four_checks_from_github_actions(self) -> None:
        rules = self._rules()
        checks = rules["required_status_checks"]
        self.assertIs(True, checks["strict_required_status_checks_policy"])
        self.assertEqual(
            {
                ("policy", 15368),
                ("fast", 15368),
                ("regression", 15368),
                ("smoke", 15368),
            },
            {
                (check["context"], check["integration_id"])
                for check in cast(
                    list[dict[str, object]], checks["required_status_checks"]
                )
            },
        )
        for rule in ("deletion", "non_fast_forward", "required_linear_history"):
            with self.subTest(rule=rule):
                self.assertIn(rule, rules)

    def test_only_the_code_owner_approves(self) -> None:
        owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertIn("* @ktogias", owners.splitlines())

    def test_agents_are_routed_to_the_runbook(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("knowledge/runbooks/operate-the-merge-gate.md", agents)
        self.assertIn("never with `--admin`", agents)

    def test_the_decision_and_runbook_link_each_other_and_are_indexed(self) -> None:
        self.assertIn(DECISION.name, RUNBOOK.read_text(encoding="utf-8"))
        self.assertIn(RUNBOOK.name, DECISION.read_text(encoding="utf-8"))
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")
        self.assertIn(f"decisions/{DECISION.name}", index)
        self.assertIn(f"runbooks/{RUNBOOK.name}", index)


if __name__ == "__main__":
    unittest.main()
