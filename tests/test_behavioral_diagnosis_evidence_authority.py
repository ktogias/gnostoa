import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "behavioral-traceability"
    / "diagnosis-evidence-authority-v1.yaml"
)
REQUIREMENT = (
    ROOT / "knowledge" / "requirements" / "bounded-behavioral-traceability.md"
)
RUNBOOK = ROOT / "knowledge" / "runbooks" / "deliver-bounded-self-hosted-slice.md"


def load_mapping(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"fixture must be a mapping: {path}")
    return value


class BehavioralDiagnosisEvidenceAuthorityTests(unittest.TestCase):
    def test_fixture_reproduces_the_circular_closure_failure_shape(self) -> None:
        fixture = load_mapping(FIXTURE)
        self.assertEqual(
            "behavioral-diagnosis-evidence-authority/v1", fixture["version"]
        )
        hypotheses = {item["id"]: item for item in fixture["hypotheses"]}
        evidence = {item["id"]: item for item in fixture["evidence"]}

        selected = hypotheses["hypothesis-a"]
        self.assertEqual("CONFIRMED", selected["resolution"])
        self.assertTrue(selected["selected_for_implementation"])

        regression = evidence["evidence-a"]
        self.assertEqual("executor-authored-regression", regression["authority"])
        self.assertEqual("hypothesis-a", regression["derived_from_hypothesis"])
        self.assertEqual("PASS", regression["execution_state"])
        self.assertEqual(
            ["base_reproduction", "candidate_correction"],
            regression["establishes"],
        )
        self.assertEqual(
            ["task_identification"], regression["claimed_to_establish"]
        )

        rejected = hypotheses["hypothesis-b"]
        self.assertEqual("REJECTED", rejected["resolution"])
        self.assertIsNone(rejected["discriminating_evidence"])
        self.assertIn("larger", rejected["rejected_reason"].lower())

        classifier = fixture["suspect_classifier"]
        self.assertTrue(classifier["on_questioned_behavior_path"])
        self.assertFalse(classifier["independently_validated"])
        self.assertTrue(classifier["used_as_correctness_definition"])

        review = fixture["review"]
        self.assertEqual("ACCEPT", review["recommendation"])
        self.assertFalse(review["independent_task_to_code_pass"])

        expected = fixture["expected_contract_outcome"]
        self.assertFalse(expected["review_ready"])
        self.assertEqual("OPEN", expected["hypothesis_a_resolution"])
        self.assertEqual("UNKNOWN", expected["task_identification"])

    def test_requirement_types_evidence_and_forbids_circular_task_identification(
        self,
    ) -> None:
        requirement = REQUIREMENT.read_text(encoding="utf-8").lower()
        for marker in (
            "task obligation",
            "semantic hypothesis",
            "implementation claim",
            "evidence authority",
            "evidence dependency",
            "executor-authored regression",
            "base reproduction",
            "candidate correction",
            "task identification",
        ):
            self.assertIn(marker, requirement)

        self.assertRegex(
            requirement,
            re.compile(
                r"task-semantic hypothesis.{0,240}must not.{0,240}confirmed"
                r".{0,360}same hypothesis",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            requirement,
            re.compile(
                r"task identification.{0,360}(open|unknown)"
                r".{0,360}blocks review-ready",
                re.DOTALL,
            ),
        )

    def test_requirement_keeps_competing_hypotheses_and_suspect_classifiers_reviewable(
        self,
    ) -> None:
        requirement = REQUIREMENT.read_text(encoding="utf-8").lower()
        for marker in (
            "competing hypotheses",
            "discriminating",
            "implementation convenience",
            "behavior-classifying predicate",
            "suspected defect path",
            "independent validation",
        ):
            self.assertIn(marker, requirement)

        self.assertRegex(
            requirement,
            re.compile(
                r"convenience.{0,240}(must not|cannot).{0,240}(evidence|reject)",
                re.DOTALL,
            ),
        )

    def test_runbook_requires_independent_diagnosis_before_map_reconciliation(
        self,
    ) -> None:
        runbook = RUNBOOK.read_text(encoding="utf-8").lower()
        for marker in (
            "independent task-to-code pass",
            "map reconciliation pass",
            "evidence independence",
        ):
            self.assertIn(marker, runbook)
        self.assertRegex(
            runbook,
            re.compile(
                r"different model.{0,240}(not|does not).{0,240}evidence independence",
                re.DOTALL,
            ),
        )


if __name__ == "__main__":
    unittest.main()
