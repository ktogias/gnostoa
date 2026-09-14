from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2b-b1-oci.yml"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md"
)
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
SOURCE_COMMIT = "0dfd7e5e28e8ccb87e687e0be9dfe846b644c9c3"
SOURCE_TREE = "23a5f083f26f40a8287bc2a724bcd5282a9afa5e"
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
ATTEST_ACTION = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"


def _load_workflow() -> dict[str, object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("B1 publication workflow must be a YAML mapping")
    return workflow


class R2AP2bB1PublicationTests(unittest.TestCase):
    def test_exact_integrated_b1_has_one_shot_digest_only_publisher(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_B1_PUBLISHER_UNAVAILABLE: exact integrated B1 has no protected-main "
            "one-shot OCI materializer",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = _load_workflow()

        self.assertEqual(
            "Publish R2A P2b-B1 prior-effective OCI consumer", workflow["name"]
        )
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

        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        checkout_steps = [
            step
            for step in steps
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
                "path": "b1-source",
            },
            source_checkout["with"],
        )

        attest_steps = [
            step
            for step in steps
            if isinstance(step, dict) and step.get("uses") == ATTEST_ACTION
        ]
        self.assertEqual(1, len(attest_steps))

        self.assertIn(f"SOURCE_COMMIT: {SOURCE_COMMIT}", workflow_text)
        self.assertIn(f"SOURCE_TREE: {SOURCE_TREE}", workflow_text)
        self.assertIn("IMAGE_NAME: ghcr.io/ktogias/gnostoa", workflow_text)
        self.assertIn("EVENT_BEFORE: ${{ github.event.before }}", workflow_text)
        self.assertIn('test "${EVENT_BEFORE}" = "${SOURCE_COMMIT}"', workflow_text)
        self.assertIn('test "${GITHUB_RUN_ATTEMPT}" = "1"', workflow_text)
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"', workflow_text
        )
        self.assertIn(
            'test "$(git rev-parse \'HEAD^{tree}\')" = "${SOURCE_TREE}"',
            workflow_text,
        )

        self.assertIn("surface-digest --root .", workflow_text)
        self.assertIn("public_digest=", workflow_text)
        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn("--metadata-file", workflow_text)
        self.assertIn('metadata["containerimage.digest"]', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${registry_digest}"', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${REGISTRY_DIGEST}"', workflow_text)
        self.assertIn('"org.opencontainers.image.revision"', workflow_text)
        self.assertIn('test "${actual}" = "${PUBLIC_DIGEST}"', workflow_text)
        self.assertIn(
            'grep -Fx "tools/review_live.py" /opt/gnostoa/.gnostoa-source-files',
            workflow_text,
        )
        self.assertIn(
            'grep -Fx "tools/review_current.py" /opt/gnostoa/.gnostoa-source-files',
            workflow_text,
        )
        self.assertIn("gh attestation verify", workflow_text)
        self.assertIn("anonymous_config=", workflow_text)

        for forbidden in (
            "workflow_dispatch",
            "docker push",
            "refs/tags/",
            "gh release",
            "git tag",
            ":latest",
            "RELEASE_VERSION",
            "IMAGE_TAG:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, workflow_text)

    def test_b1_materialization_is_governed_and_declared(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B1_MATERIALIZATION_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision 0068", decision)
        self.assertIn("5663169718", decision)
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn("digest-only", decision)
        self.assertIn("no blind rerun", decision)
        self.assertIn("prior-effective", decision)
        self.assertIn("P2b-B2", decision)
        self.assertIn("not a release", decision)

        guardrails = GUARDRAILS_PATH.read_text(encoding="utf-8")
        immutable_section = guardrails.split(
            "  - id: immutable-provider-ci-adapters", 1
        )[1].split("\n  - id:", 1)[0]
        self.assertIn(WORKFLOW_RELATIVE_PATH, immutable_section)
        self.assertIn(
            "tests/test_r2a_p2b_b1_publication.py::"
            "R2AP2bB1PublicationTests."
            "test_b1_materialization_is_governed_and_declared",
            immutable_section,
        )


if __name__ == "__main__":
    unittest.main()
