from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = (
    ".github/workflows/verify-r2a-current-advisory-restoration-runtime.yml"
)
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
SMOKE_RELATIVE_PATH = "ci/review_current_advisory_restoration_smoke.py"
SMOKE_PATH = ROOT / SMOKE_RELATIVE_PATH
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/"
    "0083-qualify-integrated-current-advisory-restoration-runtime.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH

SOURCE_COMMIT = "315487e7a67635ebf3ec3f70f666ef41646102e1"  # pragma: allowlist secret -- public integrated source
SOURCE_TREE = "ea3fdebc6afa9bf5a4c2d0691199beca4dcece81"  # pragma: allowlist secret -- public integrated tree


class CurrentAdvisoryRestorationRuntimeTests(unittest.TestCase):
    def test_r2_has_verification_only_qualification_surface(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "R2_RESTORATION_DECISION_UNAVAILABLE",
        )
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "R2_RUNTIME_QUALIFICATION_UNAVAILABLE: no verification-only "
            "restoration runtime workflow exists",
        )
        self.assertTrue(
            SMOKE_PATH.is_file(),
            "R2_RUNTIME_SMOKE_UNAVAILABLE: no layered candidate transport "
            "qualification exists",
        )

        workflow = yaml.load(
            WORKFLOW_PATH.read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)
        self.assertEqual(
            "Verify current-advisory restoration runtime",
            workflow["name"],
        )
        self.assertEqual({"contents": "read"}, workflow["permissions"])

        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(SOURCE_COMMIT, text)
        self.assertIn(SOURCE_TREE, text)
        self.assertIn(SMOKE_RELATIVE_PATH, text)
        self.assertNotIn("packages: write", text)
        self.assertNotIn("id-token: write", text)
        self.assertNotIn("docker login", text)
        self.assertNotIn("--push-by-digest", text)
        self.assertNotIn("actions/attest", text)
        smoke = SMOKE_PATH.read_text(encoding="utf-8")
        self.assertIn("host_backed_shared_tmp_sentinel_absent", smoke)

    def test_decision_keeps_publication_and_promotion_outside_r2(self) -> None:
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn(SOURCE_TREE, decision)
        self.assertIn("does **not** authorize GHCR", decision)
        self.assertIn("human semantic review", decision)
        self.assertIn("R3 requires separate owner authorization", decision)

    def test_r2_surface_is_owned_by_security_and_semantic_guardrails(self) -> None:
        guardrails = (ROOT / "policy" / "guardrails.yaml").read_text(
            encoding="utf-8"
        )
        for required in (
            WORKFLOW_RELATIVE_PATH,
            SMOKE_RELATIVE_PATH,
            DECISION_RELATIVE_PATH,
            "tests/test_current_advisory_restoration_runtime.py",
        ):
            self.assertIn(required, guardrails)


if __name__ == "__main__":
    unittest.main()
