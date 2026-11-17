"""The architecture-inheritance entrance gate is routed from source (Decision 0099).

The owner made the gate explicit and fail-closed on 2026-09-30 (#15 comment
5919462524), but it lived only in provider comments, so it did not reach the point of
mutation: two Pull Requests proceeded without it (incident addendum,
https://github.com/ktogias/gnostoa/issues/14#issuecomment-5961727761). These tests
pin the routing that makes it reachable: the router names it, the delivery runbook
carries it as part of the existing prior-art and reuse checkpoint, and a guardrail
binds both. They do not, and cannot, check that a given slice applied it -- that
remains review enforcement, as the gate itself says.
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
    ROOT
    / "knowledge"
    / "decisions"
    / "0099-route-the-architecture-inheritance-gate-from-source.md"
)
GATE_SOURCE = "https://github.com/ktogias/gnostoa/issues/15#issuecomment-5919462524"
ANCHOR = "deliver-bounded-self-hosted-slice.md#architecture-inheritance-entrance-gate"
HEADING = "### Architecture-inheritance entrance gate"
TABLE_HEADER = (
    "| responsibility | existing owner | existing implementation/contract "
    "| disposition | proof/falsifier |"
)
DISPOSITIONS = ("consume", "extend", "adapt", "factor", "supersede", "new-residual")


def _gate_section() -> str:
    """Return the runbook's gate subsection, up to the next heading of its level."""
    text = RUNBOOK.read_text(encoding="utf-8")
    start = text.find(HEADING)
    if start < 0:
        raise AssertionError(f"the runbook has no {HEADING!r} subsection")
    following = re.search(r"^#{2,3} ", text[start + len(HEADING) :], re.MULTILINE)
    end = len(text) if following is None else start + len(HEADING) + following.start()
    return text[start:end]


class ArchitectureInheritanceGateTests(unittest.TestCase):
    """The gate is reachable from the router, the runbook and the guardrail policy."""

    def test_router_routes_the_gate_before_the_first_semantic_mutation(self) -> None:
        """An agent following AGENTS.md meets the gate before it mutates anything, and
        is told to read the governing threads incrementally, which is how the gate
        was missed: a route that reads only source and pointed-to comments never sees
        an owner gate posted on #14 or #15.
        """
        text = AGENTS.read_text(encoding="utf-8")
        gate = text.index("Apply the **Architecture-inheritance entrance gate** in")
        # An entrance gate the router reaches only after its implementation routes is
        # not an entrance gate (Sourcery on #354).
        for later in (
            "Before changing normative behavior",
            "Before implementation, follow",
            "Before the first semantic edit",
        ):
            with self.subTest(precedes=later):
                self.assertLess(gate, text.index(later))
        # The routing paragraph itself, to its blank line, rather than a fixed window
        # that an unrelated edit could push a phrase out of (CodeAnt, CodeRabbit).
        end = text.find("\n\n", gate)
        paragraph = " ".join(text[gate : len(text) if end < 0 else end].split())
        self.assertIn(ANCHOR, paragraph)
        self.assertIn("before the first semantic production mutation", paragraph)
        self.assertIn("implementation stops", paragraph)
        self.assertIn("every #14 and #15 entry posted since", paragraph)

    def test_runbook_carries_the_gate_inside_the_prior_art_checkpoint(self) -> None:
        """The gate extends the existing checkpoint rather than standing beside it as
        a second lifecycle, and it carries the owner's rule in substance: the table,
        each disposition's meaning, the fail-closed stop and its source.
        """
        text = RUNBOOK.read_text(encoding="utf-8")
        checkpoint = text.index("## Prior-art and reuse checkpoint")
        procedure = text.index("## Procedure")
        self.assertLess(checkpoint, text.index(HEADING))
        self.assertLess(text.index(HEADING), procedure)
        section = _gate_section()
        flat = " ".join(section.split())
        self.assertIn(TABLE_HEADER, section)
        for disposition in DISPOSITIONS:
            with self.subTest(disposition=disposition):
                self.assertRegex(section, rf"- `{re.escape(disposition)}`: \S")
        for rule in (
            "before the first semantic production mutation",
            "implementation stops before production mutation",
            "A passing local test suite does not waive this gate.",
            "explain why an existing owner or component is insufficient",
            "every #14 and #15 entry posted since",
            "not a software gate",
        ):
            with self.subTest(rule=rule):
                # The rule's presence, wherever a sentence happens to start.
                self.assertIn(rule.lower(), flat.lower())
        self.assertIn(GATE_SOURCE, section)

    def test_runbook_names_when_the_table_is_revisited(self) -> None:
        """A slice that grows by accretion -- many local hardening rounds, logic piling
        up under a provider directory -- changed its responsibilities without anyone
        revisiting them. The runbook names that as a reason to redo the table.
        """
        flat = " ".join(_gate_section().split())
        self.assertIn("third hardening round", flat)
        self.assertIn("provider-specific directory", flat)

    def test_guardrail_binds_the_gate(self) -> None:
        """The gate is guardrail-owned, with exactly these sources and these tests."""
        policy = yaml.safe_load(GUARDRAILS.read_text(encoding="utf-8"))
        matching = [
            item
            for item in policy["guardrails"]
            if item["id"] == "architecture-inheritance-gate"
        ]
        self.assertEqual(1, len(matching))
        guardrail = matching[0]
        self.assertEqual(["kit"], guardrail["applies_to"])
        self.assertEqual("hybrid", guardrail["enforcement"])
        self.assertEqual(
            f"knowledge/runbooks/{ANCHOR}",
            guardrail["guidance"],
        )
        self.assertEqual(
            {
                "AGENTS.md",
                "knowledge/index.md",
                "knowledge/runbooks/deliver-bounded-self-hosted-slice.md",
                "knowledge/decisions/0099-route-the-architecture-inheritance-gate-from-source.md",
            },
            set(guardrail["implementation"]),
        )
        prefix = "tests/test_architecture_inheritance_gate.py::ArchitectureInheritanceGateTests."
        self.assertEqual(
            {
                f"{prefix}{name}"
                for name in dir(self)
                if name.startswith("test_") and callable(getattr(self, name))
            },
            set(guardrail["tests"]),
        )

    def test_decision_records_the_routing_and_is_indexed(self) -> None:
        """Decision 0099 is the change record: draft, citing the owner's gate."""
        text = DECISION.read_text(encoding="utf-8")
        self.assertIn("status: draft", text)
        self.assertIn(GATE_SOURCE, text)
        self.assertIn(
            "decisions/0099-route-the-architecture-inheritance-gate-from-source.md",
            INDEX.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
