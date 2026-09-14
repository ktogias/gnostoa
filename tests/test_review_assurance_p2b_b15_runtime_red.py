from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
REVIEW_CHECK = ROOT / "tools" / "review_check.py"
DECISION = (
    ROOT / "knowledge" / "decisions" / "0071-add-docker-client-to-r2a-b1-runtime.md"
)
WORKFLOW = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
SMOKE = ROOT / "ci" / "review_b15_runtime_smoke.py"

DOCKER_CLI_VERSION = "26.1.5+dfsg1-9+deb13u1"


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
        self.assertIn("consumer must become prior-effective before activation", review_check)
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
        focused_test = "tests/test_review_assurance_p2b_b15_runtime_red.py"
        smoke = "ci/review_b15_runtime_smoke.py"
        self.assertIn(f'- "{focused_test}"', workflow)
        self.assertIn(f'- "{smoke}"', workflow)
        self.assertIn(f"PYTHONPATH=. python {focused_test}", workflow)
        self.assertIn(f"PYTHONPATH=. python {smoke}", workflow)


if __name__ == "__main__":
    unittest.main()
