"""The agent credential check is routed from source (Decision 0101, #362).

The check verifies that the agents' token holds exactly its declared least privilege:
the precondition of the owner's authority channel for MA0. A check an agent is not
routed to is skipped the first time it is not remembered -- the 2026-10-04 incident
on #15 (5977488379) was exactly that. These tests pin the routing: the router names it
before provider writes, the delivery runbook carries its rule, a guardrail binds the
route, the tools, the declaration and the tests, and the Decision is indexed.
"""

from __future__ import annotations

import pathlib
import re
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
RUNBOOK = ROOT / "knowledge" / "runbooks" / "deliver-bounded-self-hosted-slice.md"
GUARDRAILS = ROOT / "policy" / "guardrails.yaml"
INDEX = ROOT / "knowledge" / "index.md"
DECISION = (
    "decisions/0101-verify-agent-provider-credentials-against-a-least-privilege-"
    "declaration.md"
)
HEADING = "### Agent credential check"
COMMAND = "knowledge credential-check"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _section() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    start = text.find(HEADING)
    if start < 0:
        raise AssertionError(f"the runbook has no {HEADING!r} subsection")
    following = re.search(r"^#{2,3} ", text[start + len(HEADING) :], re.MULTILINE)
    end = len(text) if following is None else start + len(HEADING) + following.start()
    return text[start:end]


class AgentCredentialRouteTests(unittest.TestCase):
    """The check is reachable from the router, the runbook and the guardrail policy."""

    def test_router_routes_the_check_before_provider_writes(self) -> None:
        router = _flat(AGENTS.read_text(encoding="utf-8"))
        self.assertIn(COMMAND, router)
        self.assertIn("before the first provider write", router.lower())
        self.assertIn("EXACT", router)
        self.assertIn("policy/agent-credentials.yaml", router)
        self.assertIn(
            "deliver-bounded-self-hosted-slice.md#agent-credential-check", router
        )

    def test_runbook_states_the_rule_for_every_verdict(self) -> None:
        section = _flat(_section())
        for verdict in (
            "EXACT",
            "EXCESS",
            "DEFICIENT",
            "UNVERIFIED",
            "TOKEN_KIND_MISMATCH",
            "LIFETIME_EXCEEDED",
        ):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, section)
        self.assertIn("no provider write", section)
        # It says what the check is not, so it is never mistaken for the boundary.
        self.assertIn("not the credential boundary", section)
        self.assertIn("browser", section)

    def test_procedure_step_one_runs_the_check(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        step = re.search(r"^1\. \*\*Orient.*?(?=^2\. )", text, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(step)
        assert step is not None
        self.assertIn("agent credential check", _flat(step.group(0)).lower())

    def test_guardrail_binds_the_route_tools_declaration_and_tests(self) -> None:
        guardrails = yaml.safe_load(GUARDRAILS.read_text(encoding="utf-8"))[
            "guardrails"
        ]
        guardrail = next(
            (g for g in guardrails if g["id"] == "agent-credential-least-privilege"),
            None,
        )
        self.assertIsNotNone(guardrail, "no guardrail binds the credential check")
        assert guardrail is not None
        for path in (
            "AGENTS.md",
            "knowledge/runbooks/deliver-bounded-self-hosted-slice.md",
            f"knowledge/{DECISION}",
            "policy/agent-credentials.yaml",
            "tools/credential_posture.py",
            "tools/credential_posture_github.py",
            "tools/credential_check.py",
        ):
            with self.subTest(implementation=path):
                self.assertIn(path, guardrail["implementation"])
        tests = " ".join(guardrail["tests"])
        self.assertIn("tests/test_credential_posture.py", tests)
        self.assertIn("tests/test_agent_credential_route.py", tests)

    def test_decision_is_indexed(self) -> None:
        self.assertIn(DECISION, INDEX.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "knowledge" / DECISION).is_file())


if __name__ == "__main__":
    unittest.main()
