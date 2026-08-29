from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FindingAdmissionGovernanceTests(unittest.TestCase):
    def test_finding_to_implementation_admission_is_canonical_and_routed(self) -> None:
        requirement_path = (
            ROOT
            / "knowledge"
            / "requirements"
            / "retrospective-findings-require-explicit-admission.md"
        )
        self.assertTrue(
            requirement_path.is_file(),
            "finding-to-implementation admission must be canonical knowledge",
        )

        requirement = requirement_path.read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        runbook = (
            ROOT / "knowledge" / "runbooks" / "deliver-bounded-self-hosted-slice.md"
        ).read_text(encoding="utf-8")
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")

        for marker in (
            "Observation",
            "retrospective finding",
            "focused tracked Work Item",
            "explicit admission condition",
            "implementation only after separate admission",
            "Issue creation is not implementation admission",
        ):
            self.assertIn(marker, requirement)

        self.assertIn("Decision 0053", requirement)
        self.assertIn("resume the existing same-purpose Work Item", requirement)
        self.assertIn("does not automatically become active WIP", requirement)
        self.assertIn("knowledge-only", requirement)

        self.assertIn("unadmitted finding", agents)
        self.assertIn("focused tracked Work Item", agents)
        self.assertIn("finding provenance and admission", runbook)
        self.assertIn(
            "requirements/retrospective-findings-require-explicit-admission.md",
            index,
        )


if __name__ == "__main__":
    unittest.main()
