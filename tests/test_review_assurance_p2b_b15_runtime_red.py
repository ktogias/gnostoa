from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
REVIEW_CHECK = ROOT / "tools" / "review_check.py"
DECISION = (
    ROOT / "knowledge" / "decisions" / "0071-add-docker-client-to-r2a-b1-runtime.md"
)
WORKFLOW = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
SMOKE = ROOT / "ci" / "review_b15_runtime_smoke.py"
GUARDRAILS = ROOT / "policy" / "guardrails.yaml"

DOCKER_CLI_VERSION = "26.1.5+dfsg1-9+deb13u1"
FOCUSED_TEST = "tests/test_review_assurance_p2b_b15_runtime_red.py"
SMOKE_PATH = "ci/review_b15_runtime_smoke.py"
DECISION_PATH = "knowledge/decisions/0071-add-docker-client-to-r2a-b1-runtime.md"


class ReviewAssuranceP2bB15RuntimeRedTests(unittest.TestCase):
    def test_runtime_adds_only_the_exact_pinned_docker_client(self) -> None:
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn(f"ARG DOCKER_CLI_VERSION={DOCKER_CLI_VERSION}", dockerfile)
        self.assertIn('"docker-cli=${DOCKER_CLI_VERSION}"', dockerfile)
        self.assertNotIn('"docker.io=${DOCKER_CLI_VERSION}"', dockerfile)
        self.assertNotIn("dockerd", dockerfile)

    def test_b15_keeps_candidate_current_advisory_dormant(self) -> None:
        review_check = REVIEW_CHECK.read_text(encoding="utf-8")
        self.assertIn("candidate-side P2b-B1 CLI", review_check)
        self.assertIn(
            "consumer must become prior-effective before activation", review_check
        )
        self.assertNotIn("run_prior_effective_current_advisory", review_check)

    def test_b15_has_a_durable_runtime_capability_decision(self) -> None:
        self.assertTrue(DECISION.is_file(), "P2B_B15_RUNTIME_DECISION_UNAVAILABLE")
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("Decision 0070", decision)
        self.assertIn("docker-cli", decision)
        self.assertIn(DOCKER_CLI_VERSION, decision)
        self.assertIn("B1.5", decision)
        self.assertIn("does not activate P2b-B2", decision)
        self.assertIn("host Docker socket", decision)

    def test_dedicated_verification_builds_and_smokes_the_b15_runtime(self) -> None:
        self.assertTrue(SMOKE.is_file(), "P2B_B15_RUNTIME_SMOKE_UNAVAILABLE")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f'- "{FOCUSED_TEST}"', workflow)
        self.assertIn(f'- "{SMOKE_PATH}"', workflow)
        self.assertIn(f"PYTHONPATH=. python {FOCUSED_TEST}", workflow)
        self.assertIn(f"PYTHONPATH=. python {SMOKE_PATH}", workflow)

    def test_runtime_smoke_owns_and_confirms_container_cleanup(self) -> None:
        smoke = SMOKE.read_text(encoding="utf-8")
        self.assertIn('"create"', smoke)
        self.assertIn('"start"', smoke)
        self.assertNotIn('"--rm"', smoke)
        self.assertIn("CLEANUP_ATTEMPTS", smoke)
        self.assertIn('f"name=^/{container_name}$"', smoke)
        self.assertIn("OWNER_LABEL", smoke)
        self.assertIn('"--label"', smoke)
        self.assertIn("owner_token", smoke)
        self.assertIn("refusing to clean non-owned B1.5 runtime container", smoke)
        self.assertIn('docker, "rm", "--force", container_id', smoke)
        self.assertIn("B1.5 runtime container cleanup could not be confirmed", smoke)

    def test_semantic_review_guardrail_declares_the_b15_runtime_capability(
        self,
    ) -> None:
        document = yaml.safe_load(GUARDRAILS.read_text(encoding="utf-8"))
        self.assertIsInstance(document, dict)
        guardrails = document.get("guardrails")
        self.assertIsInstance(guardrails, list)
        assert isinstance(guardrails, list)
        guardrail = next(
            entry
            for entry in guardrails
            if isinstance(entry, dict)
            and entry.get("id") == "semantic-review-assurance"
        )
        implementation = guardrail.get("implementation")
        tests = guardrail.get("tests")
        self.assertIsInstance(implementation, list)
        self.assertIsInstance(tests, list)
        assert isinstance(implementation, list)
        assert isinstance(tests, list)
        self.assertLessEqual(
            {"Dockerfile", DECISION_PATH, SMOKE_PATH}, set(implementation)
        )
        self.assertIn(FOCUSED_TEST, tests)
        self.assertIn(SMOKE_PATH, tests)


if __name__ == "__main__":
    unittest.main()
