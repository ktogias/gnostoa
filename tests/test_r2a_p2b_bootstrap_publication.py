from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-r2a-p2a-bootstrap-oci.yml"
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0068-materialize-r2a-p2a-as-a-one-shot-digest-only-oci-judge.md"
)
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
SOURCE_COMMIT = "d66d1830d724d759db6ec87e1f8d5dcc0847f221"
SOURCE_TREE = "384df86fec31208a02371b63722f903e63404134"
PUBLIC_DIGEST = (
    "sha256:ee2418fccd7e8907b8b8f60b0e0c7663e93c3e9abb66d9496efd1c3666ca1845"
)
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2a-bootstrap-oci.yml"
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
ATTEST_ACTION = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"


class R2AP2bBootstrapPublicationTests(unittest.TestCase):
    def test_one_shot_p2a_bootstrap_publication_contract(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_BOOTSTRAP_PUBLISHER_UNAVAILABLE: no protected-main one-shot "
            "publisher exists for the exact integrated P2a source",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)

        self.assertEqual("Publish R2A P2a bootstrap OCI judge", workflow["name"])
        self.assertEqual(
            {
                "push": {
                    "branches": ["main"],
                    "paths": [WORKFLOW_RELATIVE_PATH],
                }
            },
            workflow["on"],
        )
        self.assertEqual({}, workflow["permissions"])

        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        self.assertEqual({"authorize", "publish"}, set(jobs))

        authorize = jobs["authorize"]
        publish = jobs["publish"]
        self.assertIsInstance(authorize, dict)
        self.assertIsInstance(publish, dict)
        assert isinstance(authorize, dict)
        assert isinstance(publish, dict)
        self.assertNotIn("permissions", authorize)
        self.assertEqual("authorize", publish["needs"])
        self.assertEqual(
            {
                "contents": "read",
                "packages": "write",
                "id-token": "write",
                "attestations": "write",
            },
            publish["permissions"],
        )

        publish_steps = publish["steps"]
        self.assertIsInstance(publish_steps, list)
        assert isinstance(publish_steps, list)
        checkout_steps = [
            step
            for step in publish_steps
            if isinstance(step, dict) and step.get("uses") == CHECKOUT_ACTION
        ]
        self.assertEqual(2, len(checkout_steps))
        publisher_checkout, source_checkout = checkout_steps
        self.assertEqual(
            {"persist-credentials": "false", "fetch-depth": "1"},
            publisher_checkout["with"],
        )
        self.assertEqual(
            {
                "persist-credentials": "false",
                "fetch-depth": "1",
                "ref": "${{ env.SOURCE_COMMIT }}",
                "path": "p2a-source",
            },
            source_checkout["with"],
        )

        attest_steps = [
            step
            for step in publish_steps
            if isinstance(step, dict) and step.get("uses") == ATTEST_ACTION
        ]
        self.assertEqual(1, len(attest_steps))
        self.assertEqual(
            {
                "subject-name": "${{ env.IMAGE_NAME }}",
                "subject-digest": "${{ steps.publish.outputs.registry_digest }}",
                "push-to-registry": "true",
            },
            attest_steps[0]["with"],
        )

        # Shell-level effect and identity assertions remain textual because the
        # YAML parser can establish the workflow structure but cannot interpret
        # the embedded shell program.
        self.assertIn(f"SOURCE_COMMIT: {SOURCE_COMMIT}", workflow_text)
        self.assertIn(f"SOURCE_TREE: {SOURCE_TREE}", workflow_text)
        self.assertIn(f"PUBLIC_DIGEST: {PUBLIC_DIGEST}", workflow_text)
        self.assertIn("IMAGE_NAME: ghcr.io/ktogias/gnostoa", workflow_text)
        self.assertNotIn("IMAGE_TAG:", workflow_text)
        self.assertNotIn("IMAGE_REF:", workflow_text)
        self.assertIn("EVENT_BEFORE: ${{ github.event.before }}", workflow_text)
        self.assertIn('test "${EVENT_BEFORE}" = "${SOURCE_COMMIT}"', workflow_text)
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"', workflow_text
        )
        self.assertIn(
            'test "$(git rev-parse \'HEAD^{tree}\')" = "${SOURCE_TREE}"',
            workflow_text,
        )

        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn("--metadata-file", workflow_text)
        self.assertIn('metadata["containerimage.digest"]', workflow_text)
        self.assertIn("registry_digest=", workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${registry_digest}"', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${REGISTRY_DIGEST}"', workflow_text)
        self.assertIn('"org.opencontainers.image.revision"', workflow_text)
        self.assertIn('test "${actual}" = "${PUBLIC_DIGEST}"', workflow_text)
        self.assertIn("gh attestation verify", workflow_text)
        self.assertIn("anonymous_config=", workflow_text)
        self.assertIn('docker pull "${digest_ref}"', workflow_text)

        self.assertNotIn("assert_tag_absent", workflow_text)
        self.assertNotIn("docker push", workflow_text)
        self.assertNotIn("refs/tags/", workflow_text)
        self.assertNotIn("gh release", workflow_text)
        self.assertNotIn("git tag", workflow_text)
        self.assertNotIn(":latest", workflow_text)
        self.assertNotIn("RELEASE_VERSION", workflow_text)
        self.assertNotIn("workflow_dispatch", workflow_text)

    def test_bootstrap_publication_has_decision_and_guardrail_ownership(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_BOOTSTRAP_DECISION_UNAVAILABLE: privileged one-shot publication "
            "must have a durable decision record",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision 0067", decision)
        self.assertIn("5658009912", decision)
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn("digest-only", decision)
        self.assertIn("no blind rerun", decision)
        self.assertIn("read-only provider-state reconciliation", decision)
        self.assertIn("not a release", decision)

        guardrails = GUARDRAILS_PATH.read_text(encoding="utf-8")
        immutable_section = guardrails.split(
            "  - id: immutable-provider-ci-adapters", 1
        )[1].split("\n  - id:", 1)[0]
        self.assertIn(WORKFLOW_RELATIVE_PATH, immutable_section)
        self.assertIn(
            "tests/test_r2a_p2b_bootstrap_publication.py::"
            "R2AP2bBootstrapPublicationTests."
            "test_bootstrap_publication_has_decision_and_guardrail_ownership",
            immutable_section,
        )


if __name__ == "__main__":
    unittest.main()
