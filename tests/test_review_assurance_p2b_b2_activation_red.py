from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_CHECK = ROOT / "tools" / "review_check.py"
REVIEW_PROTECTED = ROOT / "tools" / "review_protected.py"
REVIEW_OUTER = ROOT / "tools" / "review_outer.py"
DEDICATED_WORKFLOW = (
    ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
)

DIND_IMAGE = (
    "docker.io/library/docker@"
    "sha256:77759fdec1efef224ba7110ef7b5b3c6af6164ffaef5441d3beba059bde8b857"
)


class ReviewAssuranceP2bB2ActivationRedTests(unittest.TestCase):
    def test_candidate_cli_delegates_the_entire_protected_result_to_prior_effective_outer_runtime(
        self,
    ) -> None:
        text = REVIEW_CHECK.read_text(encoding="utf-8")
        self.assertIn(
            "from .review_outer import run_prior_effective_current_advisory",
            text,
            "P2B_B2_CLI_OUTER_DELEGATION_UNAVAILABLE",
        )
        self.assertNotIn("from .review_live import", text)
        self.assertNotIn("evaluate_gnostoa_current_advisory", text)
        self.assertNotIn(
            "dormant outer consumer must become prior-effective before activation",
            text,
        )
        self.assertIn("sys.stdout.buffer.write(raw_result)", text)

    def test_outer_runtime_is_selected_only_from_protected_consumer_authority(
        self,
    ) -> None:
        self.assertTrue(
            REVIEW_OUTER.is_file(),
            "P2B_B2_PRIOR_EFFECTIVE_OUTER_RUNTIME_UNAVAILABLE",
        )
        outer = REVIEW_OUTER.read_text(encoding="utf-8")
        protected = REVIEW_PROTECTED.read_text(encoding="utf-8")
        self.assertIn("acquire_gnostoa_current_advisory_consumer", protected)
        self.assertIn("acquire_gnostoa_current_advisory_consumer", outer)
        self.assertIn("review-protected-consumer-authority.schema.json", outer)
        self.assertIn('consumer.get("runtime_image")', outer)
        self.assertNotIn("from .review_live import", outer)
        self.assertNotIn("evaluate_gnostoa_current_advisory", outer)

    def test_outer_runtime_uses_a_dedicated_digest_pinned_nested_daemon(self) -> None:
        self.assertTrue(
            REVIEW_OUTER.is_file(),
            "P2B_B2_PRIOR_EFFECTIVE_OUTER_RUNTIME_UNAVAILABLE",
        )
        text = REVIEW_OUTER.read_text(encoding="utf-8")
        self.assertIn(DIND_IMAGE, text)
        self.assertIn('"--privileged"', text)
        self.assertIn("shared-tmp", text)
        self.assertIn("shared-run", text)
        self.assertIn('"/var/run"', text)
        self.assertIn('"/tmp"', text)
        self.assertNotIn("src=/var/run/docker.sock", text)
        self.assertNotIn("source=/var/run/docker.sock", text)
        self.assertIn("--read-only", text)
        self.assertIn("no-new-privileges", text)
        self.assertIn("cap-drop", text)

    def test_dedicated_verification_covers_the_b2_bridge_and_real_smoke(self) -> None:
        workflow = DEDICATED_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            '- "tests/test_review_assurance_p2b_b2_activation_red.py"', workflow
        )
        self.assertIn('- "tools/review_outer.py"', workflow)
        self.assertIn('- "ci/review_outer_smoke.py"', workflow)
        self.assertIn(
            "PYTHONPATH=. python tests/test_review_assurance_p2b_b2_activation_red.py",
            workflow,
        )
        self.assertIn("PYTHONPATH=. python ci/review_outer_smoke.py", workflow)


if __name__ == "__main__":
    unittest.main()
