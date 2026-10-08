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
    def _r_main(self) -> dict[str, list[dict[str, object]]]:
        text = RUNBOOK.read_text(encoding="utf-8")
        block = re.search(r"```json\n(\{.*?\})\n```", text, re.S)
        if block is None:
            self.fail("the runbook records R-main as JSON")
        return cast(dict[str, list[dict[str, object]]], json.loads(block.group(1)))

    def _rules(self) -> dict[str, dict[str, object]]:
        return {
            str(rule["type"]): cast(dict[str, object], rule.get("parameters", {}))
            for rule in self._r_main()["rules"]
        }

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

    def test_only_break_glass_bypasses_r_main(self) -> None:
        """R-main's bypass list is pinned: break glass alone, in pull-request mode
        (Sourcery on #400)."""
        self.assertEqual(
            [
                {
                    "actor_id": 5230732,
                    "actor_type": "Integration",
                    "bypass_mode": "pull_request",
                }
            ],
            self._r_main()["bypass_actors"],
        )

    def test_only_the_code_owner_approves(self) -> None:
        """Every active CODEOWNERS entry names the owner alone, so no path-specific
        rule lets another reviewer's approval count (cubic, Sourcery, CodeAnt and
        Codex on #400)."""
        owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        entries = [
            line.split()
            for line in owners.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertIn(["*", "@ktogias"], entries)
        for entry in entries:
            with self.subTest(pattern=entry[0]):
                self.assertEqual(["@ktogias"], entry[1:])

    def test_agents_are_routed_to_the_runbook(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("knowledge/runbooks/operate-the-merge-gate.md", agents)
        self.assertIn("never with `--admin`", agents)

    def test_no_command_carries_a_token_or_a_bare_helper(self) -> None:
        """A token reaches `gh` only through `$(...)`, never as a literal in a
        command or its history; each helper and the token file are named by their
        full path (cubic, Sourcery and CodeAnt on #400)."""
        text = RUNBOOK.read_text(encoding="utf-8")
        # Each token comes from a known minting command, run by its absolute path
        # (cubic and CodeAnt on #400).
        minted = {
            "$(~/.config/gnostoa-agent/bin/agent-token.sh)",
            "$(cat ~/.config/gnostoa-agent/machine-user-token)",
            "$(~/break-glass/break-glass-token.sh)",
        }
        assigned = re.findall(r"GH_TOKEN=(\$\([^)]*\)|\S*)", text)
        self.assertTrue(assigned)
        for value in assigned:
            with self.subTest(assignment=value):
                self.assertIn(value.rstrip("`"), minted)
        for literal in (
            r"--token\b",
            r"[Aa]uthorization:",
            r"x-access-token:",
            r"\bgh[opsur]_[A-Za-z0-9]{8,}",
            r"github_pat_",
        ):
            with self.subTest(literal=literal):
                self.assertIsNone(re.search(literal, text))
        for name in (
            "bin/agent-token.sh",
            "bin/agent-git.sh",
            "bin/agent-jwt.sh",
            "machine-user-token",
        ):
            base = name.rsplit("/", 1)[-1]
            for match in re.finditer(rf"(\S*?){re.escape(base)}", text):
                with self.subTest(name=base, at=match.start()):
                    self.assertTrue(
                        match.group(0).endswith(f"~/.config/gnostoa-agent/{name}"),
                        match.group(0),
                    )

    def test_break_glass_is_named_as_the_exception_and_closed_after(self) -> None:
        """The guarantee names break glass as its one exception (cubic and CodeAnt on
        #400). Its follow-up has a Work Item and a Decision (Greptile on #400); an
        exposed key's installation is suspended first (Codex on #400); a protection
        changed temporarily is restored and read back (CodeAnt on #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        decision = " ".join(DECISION.read_text(encoding="utf-8").split())
        for text in (runbook, decision):
            self.assertIn("except through break glass", text)
        for phrase in (
            "the emergency follow-up Work Item and Decision",
            "Suspend the installation of `gnostoa-break-glass`",
            "Suspend the installation of `gnostoa-agent`",
            "Restore the protection",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_the_pre_merge_check_is_named_with_what_it_checks(self) -> None:
        """The convergence step names the pre-merge check, where it lives, and what
        it checks, so a fresh environment can perform it (Codex on #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        for phrase in (
            "`premerge-check.sh`",
            "not yet versioned",
            "the seal names the exact head",
            "every required check",
            "every other check run and status",
            "every review thread",
            "no closing keyword",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_every_decision_cited_exists(self) -> None:
        """A Decision is cited by number only when it is in the repository; #384's
        unmerged proposal is cited by its PR (Claude on #400)."""
        decisions = {
            path.name[:4] for path in (ROOT / "knowledge" / "decisions").iterdir()
        }
        for path in (RUNBOOK, DECISION):
            for number in re.findall(
                r"Decision (\d{4})", path.read_text(encoding="utf-8")
            ):
                with self.subTest(source=path.name, decision=number):
                    self.assertIn(number, decisions)

    def test_the_decision_and_runbook_link_each_other_and_are_indexed(self) -> None:
        self.assertIn(DECISION.name, RUNBOOK.read_text(encoding="utf-8"))
        self.assertIn(RUNBOOK.name, DECISION.read_text(encoding="utf-8"))
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")
        self.assertIn(f"decisions/{DECISION.name}", index)
        self.assertIn(f"runbooks/{RUNBOOK.name}", index)


if __name__ == "__main__":
    unittest.main()
