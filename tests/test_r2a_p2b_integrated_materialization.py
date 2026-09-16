from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2b-oci.yml"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
SOURCE_COMMIT = "2aa1ed3217c42819155b8ff36385b000720ba4f8"  # pragma: allowlist secret -- public source revision
SOURCE_TREE = "4cda4e4a704cb518f56201423e313d4dd9db5e24"  # pragma: allowlist secret -- public source tree


class R2AP2bIntegratedMaterializationTests(unittest.TestCase):
    def test_exact_integrated_p2b_has_digest_only_materializer(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_OCI_PUBLISHER_UNAVAILABLE: exact integrated P2b has no "
            "protected-main one-shot digest-only OCI materializer",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)

        self.assertIn(SOURCE_COMMIT, workflow_text)
        self.assertIn(SOURCE_TREE, workflow_text)
        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn("actions/attest@", workflow_text)
        self.assertIn('test "${GITHUB_RUN_ATTEMPT}" = "1"', workflow_text)
        self.assertIn("merge_commit_sha", workflow_text)
        self.assertIn("self-check", workflow_text)
        self.assertIn("DOCKER_CONFIG", workflow_text)
        self.assertNotIn("docker push ", workflow_text)
        self.assertNotIn("gh release create", workflow_text)

    def test_materialization_has_durable_decision(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_MATERIALIZATION_DECISION_UNAVAILABLE: post-B2 rolling-trust "
            "materialization has no durable Decision 0078",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision", decision)
        self.assertIn("0078", DECISION_PATH.name)
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn(SOURCE_TREE, decision)
        self.assertIn("digest-only", decision)
        self.assertIn("attest", decision.lower())
        self.assertIn("reacquir", decision.lower())
        self.assertIn("Decision 0077", decision)


if __name__ == "__main__":
    unittest.main()
