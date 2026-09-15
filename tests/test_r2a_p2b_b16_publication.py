from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2b-b16-oci.yml"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md"
)
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
SOURCE_COMMIT = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- public source revision
SOURCE_TREE = "ff38abe5718ebc550054ea6af18a73d0aef8e514"  # pragma: allowlist secret -- public source tree
AUTHORIZED_BEFORE_COMMIT = SOURCE_COMMIT
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
SETUP_PYTHON_ACTION = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
ATTEST_ACTION = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
B15_SMOKE = "ci/review_b15_runtime_smoke.py"
B16_SMOKE = "ci/review_b16_entrypoint_smoke.py"
B16_ENTRYPOINT = "tools/review_live_entrypoint.py"
B16_RUNTIME_LOCK = "b16-source/requirements/runtime.lock"


def _load_workflow() -> dict[str, object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("B1.6 publication workflow must be a YAML mapping")
    return workflow


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

        self.assertIn(f"SOURCE_COMMIT: {SOURCE_COMMIT}", workflow_text)
        self.assertIn(f"SOURCE_TREE: {SOURCE_TREE}", workflow_text)
        self.assertIn(
            f"AUTHORIZED_BEFORE_COMMIT: {AUTHORIZED_BEFORE_COMMIT}", workflow_text
        )
        self.assertIn("IMAGE_NAME: ghcr.io/ktogias/gnostoa", workflow_text)
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
        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn("--metadata-file", workflow_text)
        self.assertIn('metadata["containerimage.digest"]', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${registry_digest}"', workflow_text)
        self.assertIn('digest_ref="${IMAGE_NAME}@${REGISTRY_DIGEST}"', workflow_text)
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
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, workflow_text)

    def test_b16_host_smoke_uses_exact_source_runtime_dependencies(self) -> None:
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

        source_checkout_index = next(
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("uses") == CHECKOUT_ACTION
            and isinstance(step.get("with"), dict)
            and step["with"].get("path") == "b16-source"
        )
        setup_indices = [
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict) and step.get("uses") == SETUP_PYTHON_ACTION
        ]
        self.assertEqual(1, len(setup_indices))
        setup_index = setup_indices[0]
        setup_step = steps[setup_index]
        assert isinstance(setup_step, dict)
        self.assertEqual(
            {
                "python-version": "3.12",
                "cache": "pip",
                "cache-dependency-path": B16_RUNTIME_LOCK,
            },
            setup_step["with"],
        )

        install_indices = [
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("name") == "Install exact B1.6 source runtime dependencies"
        ]
        self.assertEqual(1, len(install_indices))
        install_index = install_indices[0]
        install_step = steps[install_index]
        assert isinstance(install_step, dict)
        install_run = install_step.get("run")
        self.assertIsInstance(install_run, str)
        assert isinstance(install_run, str)
        for required in (
            "python -m pip install",
            "--only-binary=:all:",
            "--require-hashes",
            f"-r {B16_RUNTIME_LOCK}",
        ):
            self.assertIn(required, install_run)

        local_verify_index = next(
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict)
            and step.get("name")
            == "Build and verify exact B1.6 consumer locally before any registry effect"
        )
        self.assertLess(source_checkout_index, setup_index)
        self.assertLess(setup_index, install_index)
        self.assertLess(install_index, local_verify_index)

    def test_b16_materialization_reproves_b15_and_b16_runtime_at_all_three_cuts(
        self,
    ) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_B16_PUBLISHER_UNAVAILABLE",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        for required_source in (B15_SMOKE, B16_SMOKE, B16_ENTRYPOINT):
            self.assertIn(
                f'grep -Fx "{required_source}" /opt/gnostoa/.gnostoa-source-files',
                workflow_text,
            )

        local_b15 = (
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
            f"python b16-source/{B15_SMOKE}"
        )
        local_b16 = (
            'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${local_image}" '
            f"python b16-source/{B16_SMOKE}"
        )
        digest_b16 = (
            'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
            f"python b16-source/{B16_SMOKE}"
        )
        self.assertIn(local_b15, workflow_text)
        self.assertIn(local_b16, workflow_text)
        self.assertEqual(
            2,
            workflow_text.count(digest_b16),
            "authenticated and anonymous B1.6 smoke cuts must import from the exact source checkout",
        )
        self.assertGreaterEqual(
            workflow_text.count(f"python b16-source/{B15_SMOKE}"),
            3,
            "B1.5 Docker-client/no-daemon capability must be re-proved at all cuts",
        )
        self.assertEqual(
            3,
            workflow_text.count(f"python b16-source/{B16_SMOKE}"),
            "B1.6 input-only module/daemonless capability must be re-proved at exactly all three cuts",
        )
        login_index = workflow_text.index("docker login ghcr.io")
        self.assertLess(workflow_text.index(local_b15), login_index)
        self.assertLess(workflow_text.index(local_b16), login_index)
        self.assertNotIn("/var/run/docker.sock", workflow_text)

    def test_digest_readback_is_uniform_and_anonymous_reacquisition_is_not_cached(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        digest_uid_check = (
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -u)" = "10001"'
        )
        digest_gid_check = (
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -g)" = "10001"'
        )
        self.assertGreaterEqual(
            workflow_text.count(digest_uid_check),
            2,
            "authenticated digest readback and anonymous reacquisition must both prove uid 10001",
        )
        self.assertGreaterEqual(
            workflow_text.count(digest_gid_check),
            2,
            "authenticated digest readback and anonymous reacquisition must both prove gid 10001",
        )

        anonymous_block = workflow_text.split(
            "- name: Verify attestation and anonymous digest acquisition", 1
        )[1]
        permissive_rm = 'docker image rm "${digest_ref}" >/dev/null 2>&1 || true'
        strict_rm = 'docker image rm "${digest_ref}" >/dev/null'
        absence_probe = 'if docker image inspect "${digest_ref}" >/dev/null 2>&1; then'
        anonymous_pull = (
            'DOCKER_CONFIG="${anonymous_config}" docker pull "${digest_ref}"'
        )
        self.assertNotIn(permissive_rm, anonymous_block)
        self.assertIn(strict_rm, anonymous_block)
        self.assertIn(absence_probe, anonymous_block)
        self.assertLess(
            anonymous_block.index(strict_rm), anonymous_block.index(absence_probe)
        )
        self.assertLess(
            anonymous_block.index(absence_probe), anonymous_block.index(anonymous_pull)
        )

    def test_b16_materialization_is_governed_and_declared(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B16_MATERIALIZATION_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        for required in (
            "Decision 0072",
            "Decision 0073",
            "Decision 0074",
            "5671332574",
            SOURCE_COMMIT,
            SOURCE_TREE,
            "digest-only",
            "no blind rerun",
            "prior-effective",
            "P2b-B2",
            "not a release",
            "host Docker socket",
            "review_live_entrypoint",
            "candidate-injected",
        ):
            self.assertIn(required, decision)

        guardrails = GUARDRAILS_PATH.read_text(encoding="utf-8")
        immutable_section = guardrails.split(
            "  - id: immutable-provider-ci-adapters", 1
        )[1].split("\n  - id:", 1)[0]
        self.assertIn(WORKFLOW_RELATIVE_PATH, immutable_section)
        self.assertIn(
            "tests/test_r2a_p2b_b16_publication.py::"
            "R2AP2bB16PublicationTests."
            "test_b16_materialization_is_governed_and_declared",
            immutable_section,
        )


if __name__ == "__main__":
    unittest.main()
