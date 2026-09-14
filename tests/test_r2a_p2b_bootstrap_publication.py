from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-r2a-p2a-bootstrap-oci.yml"
SOURCE_COMMIT = "d66d1830d724d759db6ec87e1f8d5dcc0847f221"
SOURCE_TREE = "384df86fec31208a02371b63722f903e63404134"
PUBLIC_DIGEST = (
    "sha256:ee2418fccd7e8907b8b8f60b0e0c7663e93c3e9abb66d9496efd1c3666ca1845"
)
BOOTSTRAP_TAG = f"r2a-p2a-{SOURCE_COMMIT}"


class R2AP2bBootstrapPublicationTests(unittest.TestCase):
    def test_one_shot_p2a_bootstrap_publication_contract(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_BOOTSTRAP_PUBLISHER_UNAVAILABLE: no protected-main one-shot "
            "publisher exists for the exact integrated P2a source",
        )
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("name: Publish R2A P2a bootstrap OCI judge", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("branches:", workflow)
        self.assertIn("- main", workflow)
        self.assertIn(
            '- ".github/workflows/publish-r2a-p2a-bootstrap-oci.yml"',
            workflow,
        )
        self.assertNotIn("workflow_dispatch", workflow)
        self.assertIn("permissions: {}", workflow)
        self.assertIn("packages: write", workflow)
        self.assertIn("id-token: write", workflow)
        self.assertIn("attestations: write", workflow)

        self.assertIn(f"SOURCE_COMMIT: {SOURCE_COMMIT}", workflow)
        self.assertIn(f"SOURCE_TREE: {SOURCE_TREE}", workflow)
        self.assertIn(f"PUBLIC_DIGEST: {PUBLIC_DIGEST}", workflow)
        self.assertIn(f"IMAGE_TAG: {BOOTSTRAP_TAG}", workflow)
        self.assertIn("IMAGE_NAME: ghcr.io/ktogias/gnostoa", workflow)
        self.assertIn("ref: ${{ env.SOURCE_COMMIT }}", workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"', workflow)
        self.assertIn(
            'test "$(git rev-parse \'HEAD^{tree}\')" = "${SOURCE_TREE}"',
            workflow,
        )

        self.assertGreaterEqual(workflow.count("assert_tag_absent"), 3)
        self.assertIn('docker push "${IMAGE_REF}"', workflow)
        self.assertIn("registry_digest=", workflow)
        self.assertIn('digest_ref="${IMAGE_NAME}@${registry_digest}"', workflow)
        self.assertIn('"org.opencontainers.image.revision"', workflow)
        self.assertIn('test "${actual}" = "${PUBLIC_DIGEST}"', workflow)
        self.assertIn("actions/attest@", workflow)
        self.assertIn("gh attestation verify", workflow)
        self.assertIn("anonymous_config=", workflow)
        self.assertIn('docker pull "${IMAGE_NAME}@${REGISTRY_DIGEST}"', workflow)

        self.assertNotIn("refs/tags/", workflow)
        self.assertNotIn("gh release", workflow)
        self.assertNotIn("git tag", workflow)
        self.assertNotIn(":latest", workflow)
        self.assertNotIn("RELEASE_VERSION", workflow)


if __name__ == "__main__":
    unittest.main()
