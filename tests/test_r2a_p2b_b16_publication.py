from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2b-b16-oci.yml"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
SOURCE_COMMIT = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- public protected-main source revision
SOURCE_TREE = "ff38abe5718ebc550054ea6af18a73d0aef8e514"  # pragma: allowlist secret -- public protected-main source tree
AUTHORIZED_BEFORE_COMMIT = SOURCE_COMMIT
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
ATTEST_ACTION = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
B15_SMOKE = "ci/review_b15_runtime_smoke.py"
B16_SMOKE = "ci/review_b16_entrypoint_smoke.py"
B16_ENTRYPOINT = "tools/review_live_entrypoint.py"


def _load_workflow() -> dict[str, object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("B1.6 publication workflow must be a YAML mapping")
    return workflow


def _load_guardrails() -> dict[str, object]:
    document = yaml.load(
        GUARDRAILS_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(document, dict):
        raise AssertionError("guardrails must be a YAML mapping")
    return document


class R2AP2bB16PublicationTests(unittest.TestCase):
    def test_exact_integrated_b16_has_one_shot_digest_only_publisher(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_B16_PUBLISHER_UNAVAILABLE: exact integrated B1.6 has no "
            "protected-main one-shot OCI materializer",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = _load_workflow()

        self.assertEqual(
            "Publish R2A P2b-B1.6 prior-effective OCI consumer", workflow["name"]
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
        self.assertEqual(
            {
                "KIT_VERSION": "0.2.0",
                "IMAGE_NAME": "ghcr.io/ktogias/gnostoa",
                "SOURCE_COMMIT": SOURCE_COMMIT,
                "SOURCE_TREE": SOURCE_TREE,
                "AUTHORIZED_BEFORE_COMMIT": AUTHORIZED_BEFORE_COMMIT,
            },
            workflow["env"],
        )

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
                "path": "b16-source",
            },
            source_checkout["with"],
        )

        attest_steps = [
            step
            for step in steps
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

        self.assertIn("EVENT_BEFORE: ${{ github.event.before }}", workflow_text)
        self.assertIn(
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"', workflow_text
        )
        self.assertIn('test "${GITHUB_RUN_ATTEMPT}" = "1"', workflow_text)
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"', workflow_text
        )
        self.assertIn(
            'test "$(git rev-parse \'HEAD^{tree}\')" = "${SOURCE_TREE}"',
            workflow_text,
        )
        self.assertIn("surface-digest --root /opt/gnostoa", workflow_text)
        self.assertIn(
            '[[ "${public_digest}" =~ ^sha256:[0-9a-f]{64}$ ]]', workflow_text
        )
        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn("--metadata-file", workflow_text)
        self.assertIn('metadata["containerimage.digest"]', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${registry_digest}"', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${REGISTRY_DIGEST}"', workflow_text)
        self.assertIn('"org.opencontainers.image.revision"', workflow_text)
        self.assertIn('test "${actual}" = "${PUBLIC_DIGEST}"', workflow_text)
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
            "/var/run/docker.sock",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, workflow_text)

    def test_b16_materialization_reproves_exact_entrypoint_before_and_after_write(
        self,
    ) -> None:
        workflow = _load_workflow()
        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs["publish"]
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)
        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        step_runs = {
            step["name"]: step["run"]
            for step in steps
            if isinstance(step, dict)
            and isinstance(step.get("name"), str)
            and isinstance(step.get("run"), str)
        }

        local_run = step_runs[
            "Build and verify exact B1.6 consumer locally before any registry effect"
        ]
        authenticated_run = step_runs[
            "Publish exact B1.6 consumer without a remote tag and read back digest"
        ]
        anonymous_run = step_runs["Verify attestation and anonymous digest acquisition"]

        packaged_paths = (B16_ENTRYPOINT, B15_SMOKE, B16_SMOKE)
        for cut_name, cut_run in (
            ("local", local_run),
            ("authenticated", authenticated_run),
            ("anonymous", anonymous_run),
        ):
            with self.subTest(cut=cut_name):
                for packaged_path in packaged_paths:
                    self.assertIn(
                        f'grep -Fx "{packaged_path}" /opt/gnostoa/.gnostoa-source-files',
                        cut_run,
                    )

        local_b15 = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
            f"python b16-source/{B15_SMOKE}"
        )
        local_b16 = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
            f"python b16-source/{B16_SMOKE}"
        )
        digest_b15 = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
            f"python b16-source/{B15_SMOKE}"
        )
        digest_b16 = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
            f"python b16-source/{B16_SMOKE}"
        )
        self.assertEqual(1, local_run.count(local_b15))
        self.assertEqual(1, local_run.count(local_b16))
        self.assertEqual(1, authenticated_run.count(digest_b15))
        self.assertEqual(1, authenticated_run.count(digest_b16))
        self.assertEqual(1, anonymous_run.count(digest_b15))
        self.assertEqual(1, anonymous_run.count(digest_b16))

        authenticated_pull = 'docker pull "${digest_ref}"'
        self.assertLess(
            authenticated_run.index(authenticated_pull),
            authenticated_run.index(digest_b15),
        )
        self.assertLess(
            authenticated_run.index(authenticated_pull),
            authenticated_run.index(digest_b16),
        )
        anonymous_pull = (
            'DOCKER_CONFIG="${anonymous_config}" docker pull "${digest_ref}"'
        )
        self.assertLess(
            anonymous_run.index(anonymous_pull), anonymous_run.index(digest_b15)
        )
        self.assertLess(
            anonymous_run.index(anonymous_pull), anonymous_run.index(digest_b16)
        )

    def test_b16_materialization_is_governed_and_declared(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B16_MATERIALIZATION_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision 0072", decision)
        self.assertIn("Decision 0074", decision)
        self.assertIn("5671332574", decision)
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn(SOURCE_TREE, decision)
        self.assertIn("digest-only", decision)
        self.assertIn("no blind rerun", decision)
        self.assertIn("prior-effective", decision)
        self.assertIn("P2b-B2", decision)
        self.assertIn("not a release", decision)
        self.assertIn("host Docker socket", decision)
        self.assertIn("input-only", decision)

        document = _load_guardrails()
        guardrails = document["guardrails"]
        self.assertIsInstance(guardrails, list)
        assert isinstance(guardrails, list)
        immutable_entries = [
            entry
            for entry in guardrails
            if isinstance(entry, dict)
            and entry.get("id") == "immutable-provider-ci-adapters"
        ]
        semantic_entries = [
            entry
            for entry in guardrails
            if isinstance(entry, dict)
            and entry.get("id") == "semantic-review-assurance"
        ]
        self.assertEqual(1, len(immutable_entries))
        self.assertEqual(1, len(semantic_entries))
        immutable = immutable_entries[0]
        semantic = semantic_entries[0]
        self.assertIn(WORKFLOW_RELATIVE_PATH, immutable["implementation"])
        self.assertIn(
            "tests/test_r2a_p2b_b16_publication.py::"
            "R2AP2bB16PublicationTests."
            "test_b16_materialization_is_governed_and_declared",
            immutable["tests"],
        )
        self.assertIn(DECISION_RELATIVE_PATH, semantic["implementation"])


if __name__ == "__main__":
    unittest.main()
