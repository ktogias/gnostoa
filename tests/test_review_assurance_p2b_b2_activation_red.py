from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_CHECK = ROOT / "tools" / "review_check.py"
REVIEW_PROTECTED = ROOT / "tools" / "review_protected.py"
REVIEW_OUTER = ROOT / "tools" / "review_outer.py"
DEDICATED_WORKFLOW = (
    ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
)


def _imports_candidate_review_live(path: Path) -> bool:
    if not path.is_file():
        return False
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == "review_live"
        for node in ast.walk(tree)
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
        self.assertFalse(_imports_candidate_review_live(REVIEW_CHECK))
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
        self.assertIn('consumer.get("runtime_revision")', outer)
        self.assertIn('consumer.get("public_surface_digest")', outer)
        self.assertFalse(_imports_candidate_review_live(REVIEW_OUTER))

    def test_only_prior_effective_b1_receives_the_host_docker_execution_substrate(
        self,
    ) -> None:
        self.assertTrue(
            REVIEW_OUTER.is_file(),
            "P2B_B2_PRIOR_EFFECTIVE_OUTER_RUNTIME_UNAVAILABLE",
        )
        text = REVIEW_OUTER.read_text(encoding="utf-8")
        self.assertIn("_docker_executable()", text)
        self.assertIn("/var/run/docker.sock", text)
        self.assertIn('dst=/usr/bin/docker,readonly', text)
        self.assertIn('src=/tmp,dst=/tmp', text)
        self.assertIn('"--group-add"', text)
        self.assertIn('"--read-only"', text)
        self.assertIn('"--cap-drop"', text)
        self.assertIn('"ALL"', text)
        self.assertIn('"no-new-privileges"', text)
        self.assertNotIn('"--privileged"', text)
        self.assertNotIn("GNOSTOA_R2A_CANDIDATE_IMAGE", text)

    def test_outer_result_is_validated_but_returned_byte_for_byte(self) -> None:
        self.assertTrue(
            REVIEW_OUTER.is_file(),
            "P2B_B2_PRIOR_EFFECTIVE_OUTER_RUNTIME_UNAVAILABLE",
        )
        text = REVIEW_OUTER.read_text(encoding="utf-8")
        self.assertIn("review-gate-result.schema.json", text)
        self.assertIn("canonical_json", text)
        self.assertIn("raw_result", text)
        self.assertIn("return result.returncode, raw_result", text)

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
