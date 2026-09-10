import unittest
from pathlib import Path

import yaml

from tools.knowledge_common import headings, markdown_links, parse_markdown

ROOT = Path(__file__).resolve().parents[1]
GUARDRAIL_ID = "supplied-agent-review-dispositions"
RUNBOOK = Path("knowledge/runbooks/deliver-bounded-self-hosted-slice.md")
DECISION = Path(
    "knowledge/decisions/0061-retain-individual-agent-review-dispositions.md"
)
ANCHOR = "supplied-agent-reviews"


class SuppliedAgentReviewCaptureTests(unittest.TestCase):
    """Bind the declaration of the supplied-review capture practice.

    These checks cover the guardrail contract, the router path and the
    Decision/runbook relations. They cannot observe whether a received review
    was actually captured; that remains review-enforced.
    """

    def _guardrail(self) -> dict:
        manifest = yaml.safe_load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        )
        matching = [
            item for item in manifest["guardrails"] if item["id"] == GUARDRAIL_ID
        ]
        self.assertEqual(1, len(matching))
        return matching[0]

    def test_guardrail_declares_the_kit_only_review_contract(self) -> None:
        guardrail = self._guardrail()
        self.assertEqual(["kit"], guardrail["applies_to"])
        self.assertEqual("review", guardrail["enforcement"])
        self.assertEqual(f"{RUNBOOK.as_posix()}#{ANCHOR}", guardrail["guidance"])
        self.assertEqual(
            {
                "AGENTS.md",
                DECISION.as_posix(),
                "knowledge/index.md",
                RUNBOOK.as_posix(),
            },
            set(guardrail["implementation"]),
        )

    def test_router_runbook_and_decision_bind_the_capture_anchor(self) -> None:
        target = f"{RUNBOOK.as_posix()}#{ANCHOR}"
        self.assertIn(
            target,
            markdown_links((ROOT / "AGENTS.md").read_text(encoding="utf-8")),
            "the router must link the capture section",
        )

        runbook = parse_markdown(ROOT / RUNBOOK, ROOT)
        self.assertIn(
            ANCHOR,
            {heading.replace(" ", "-") for heading in headings(runbook.body)},
            "the linked section anchor must exist",
        )

        decision = parse_markdown(ROOT / DECISION, ROOT)
        self.assertIn(
            {"kind": "governs", "target": f"/{RUNBOOK.relative_to('knowledge')}"},
            decision.project_metadata["relations"],
        )
        self.assertIn(
            {
                "kind": "governed-by",
                "target": f"/{DECISION.relative_to('knowledge')}",
            },
            runbook.project_metadata["relations"],
        )
        self.assertIn(
            DECISION.relative_to("knowledge").as_posix(),
            markdown_links(
                (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")
            ),
            "the knowledge index must link the Decision",
        )


if __name__ == "__main__":
    unittest.main()
