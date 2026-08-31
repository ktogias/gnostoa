import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "behavioral-traceability"
REQUIREMENT = ROOT / "knowledge" / "requirements" / "bounded-behavioral-traceability.md"


def load_fixture(name: str) -> dict[str, object]:
    value = yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"fixture must be a mapping: {name}")
    return value


class BehavioralTraceabilityTests(unittest.TestCase):
    def requirement_text(self) -> str:
        self.assertTrue(
            REQUIREMENT.is_file(),
            "the admitted behavioral-traceability Requirement is not implemented",
        )
        return REQUIREMENT.read_text(encoding="utf-8")

    def test_sanitized_negative_control_exposes_agreeing_but_wrong(self) -> None:
        case = load_fixture("agreeing-but-wrong.yaml")
        serialized = yaml.safe_dump(case).lower()
        for forbidden in ("nextcloud", "mailbox", "movemailbox", "renamemailbox"):
            self.assertNotIn(forbidden, serialized)

        self.assertEqual("REQUIRED", case["case"]["applicability"])
        behavior = case["behaviors"][0]
        self.assertEqual("UNRESOLVED", behavior["contradiction"]["status"])
        self.assertEqual("PASS", behavior["evidence"]["actual_result"])
        self.assertEqual("CONTRADICTS", behavior["evidence"]["alignment"])
        self.assertEqual("READY", behavior["executor_disposition"])
        self.assertEqual("ACCEPT", behavior["reviewer_disposition"])
        self.assertEqual("BLOCKED", case["expected_trace_review"]["disposition"])

    def test_positive_controls_bound_false_block_burden(self) -> None:
        aligned = load_fixture("aligned-nontrivial.yaml")
        trivial = load_fixture("trivial-not-applicable.yaml")

        self.assertEqual("ACCEPT", aligned["expected_trace_review"]["disposition"])
        self.assertTrue(aligned["behaviors"])
        for behavior in aligned["behaviors"]:
            self.assertEqual("NONE", behavior["contradiction"]["status"])
            self.assertEqual("PASS", behavior["evidence"]["actual_result"])
            self.assertEqual("SUPPORTS", behavior["evidence"]["alignment"])

        self.assertEqual("NOT APPLICABLE", trivial["case"]["applicability"])
        self.assertEqual([], trivial["behaviors"])
        self.assertEqual(
            "NOT APPLICABLE", trivial["expected_trace_review"]["disposition"]
        )

    def test_requirement_defines_bounded_blocking_and_oracle_limits(self) -> None:
        requirement = self.requirement_text()
        normalized = " ".join(requirement.split())
        for marker in (
            "multiple material behaviors",
            "contradiction or ambiguity",
            "material correctness risk",
            "before the first semantic production mutation",
            "blocks review-ready",
            "PASS",
            "FAIL",
            "BLOCKED",
            "NOT RUN",
            "SKIPPED",
            "does not establish semantic completeness",
        ):
            self.assertIn(marker, normalized)

    def test_router_and_runbook_make_the_two_checkpoints_discoverable(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        runbook = (
            ROOT / "knowledge" / "runbooks" / "deliver-bounded-self-hosted-slice.md"
        ).read_text(encoding="utf-8")
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")

        self.assertIn("bounded-behavioral-traceability.md", agents)
        self.assertIn("before the first semantic production mutation", runbook)
        self.assertIn("independently reconcile the behavior map", runbook)
        self.assertIn("requirements/bounded-behavioral-traceability.md", index)

    def test_guardrail_binds_the_self_only_contract(self) -> None:
        policy = yaml.safe_load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        )
        matching = [
            item
            for item in policy["guardrails"]
            if item["id"] == "bounded-behavioral-traceability"
        ]
        self.assertEqual(1, len(matching))
        guardrail = matching[0]
        self.assertEqual(["kit"], guardrail["applies_to"])
        for path in (
            "AGENTS.md",
            "knowledge/requirements/bounded-behavioral-traceability.md",
            "knowledge/runbooks/deliver-bounded-self-hosted-slice.md",
        ):
            self.assertIn(path, guardrail["implementation"])


if __name__ == "__main__":
    unittest.main()
