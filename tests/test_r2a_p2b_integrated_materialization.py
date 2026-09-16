from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_RELATIVE_PATH = ".github/workflows/publish-r2a-p2b-oci.yml"
WORKFLOW_PATH = ROOT / WORKFLOW_RELATIVE_PATH
R2A_WORKFLOW_RELATIVE_PATH = ".github/workflows/r2a-protected-current-advisory.yml"
R2A_WORKFLOW_PATH = ROOT / R2A_WORKFLOW_RELATIVE_PATH
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
INDEX_PATH = ROOT / "knowledge" / "index.md"
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
SOURCE_COMMIT = "2aa1ed3217c42819155b8ff36385b000720ba4f8"  # pragma: allowlist secret -- public source revision
SOURCE_TREE = "4cda4e4a704cb518f56201423e313d4dd9db5e24"  # pragma: allowlist secret -- public source tree
AUTHORIZED_PR_NUMBER = "267"
AUTHORIZED_PR_HEAD_REF = "r2a-p2b-materialization"
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
ATTEST_ACTION = "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"


def _load_workflow() -> dict[str, object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("P2b publication workflow must be a YAML mapping")
    return workflow


def _guardrail_section(text: str, guardrail_id: str) -> str:
    marker = f"  - id: {guardrail_id}"
    return text.split(marker, 1)[1].split("\n  - id:", 1)[0]


def _job_steps(job: dict[str, object], job_name: str) -> list[dict[str, object]]:
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise AssertionError(f"{job_name} must expose structured steps")
    return steps


def _named_step(
    steps: list[dict[str, object]], step_name: str
) -> tuple[int, dict[str, object]]:
    matches = [
        (index, step)
        for index, step in enumerate(steps)
        if step.get("name") == step_name
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one step named {step_name!r}, found {len(matches)}"
        )
    return matches[0]


def _step_run(step: dict[str, object], step_name: str) -> str:
    run = step.get("run")
    if not isinstance(run, str):
        raise AssertionError(f"{step_name} must be an executable run step")
    return run


class R2AP2bIntegratedMaterializationTests(unittest.TestCase):
    def test_exact_integrated_p2b_has_one_shot_digest_only_materializer(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_OCI_PUBLISHER_UNAVAILABLE: exact integrated P2b has no "
            "protected-main one-shot digest-only OCI materializer",
        )
        workflow = _load_workflow()

        self.assertEqual(
            "Publish integrated R2A P2b prior-effective OCI runtime", workflow["name"]
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
        env = workflow["env"]
        self.assertIsInstance(env, dict)
        assert isinstance(env, dict)
        self.assertEqual(SOURCE_COMMIT, env["SOURCE_COMMIT"])
        self.assertEqual(SOURCE_TREE, env["SOURCE_TREE"])
        self.assertEqual(SOURCE_COMMIT, env["AUTHORIZED_BEFORE_COMMIT"])
        self.assertEqual(AUTHORIZED_PR_NUMBER, env["AUTHORIZED_PR_NUMBER"])
        self.assertEqual(AUTHORIZED_PR_HEAD_REF, env["AUTHORIZED_PR_HEAD_REF"])

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
        self.assertEqual({"pull-requests": "read"}, authorize["permissions"])
        self.assertEqual(
            {
                "contents": "read",
                "packages": "write",
                "id-token": "write",
                "attestations": "write",
            },
            publish["permissions"],
        )

        authorize_steps = _job_steps(authorize, "authorize")
        publish_steps = _job_steps(publish, "publish")

        _, authorize_guard = _named_step(
            authorize_steps, "Refuse any context outside the admitted one-shot boundary"
        )
        authorize_guard_run = _step_run(authorize_guard, "authorization guard")
        for required in (
            'test "${GITHUB_REPOSITORY}" = "ktogias/gnostoa"',
            'test "${GITHUB_EVENT_NAME}" = "push"',
            'test "${GITHUB_REF}" = "refs/heads/main"',
            'test "${GITHUB_ACTOR}" = "ktogias"',
            'test "${GITHUB_TRIGGERING_ACTOR}" = "ktogias"',
            'test "${GITHUB_RUN_ATTEMPT}" = "1"',
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"',
        ):
            self.assertIn(required, authorize_guard_run)

        _, pr_binding = _named_step(
            authorize_steps, "Bind the pushed commit to merged PR 267"
        )
        pr_binding_run = _step_run(pr_binding, "PR landing binding")
        for required in (
            "pulls/${AUTHORIZED_PR_NUMBER}",
            "merge_commit_sha",
            'pr.get("base", {}).get("ref") == "main"',
            'pr.get("head", {}).get("ref") == expected_head_ref',
        ):
            self.assertIn(required, pr_binding_run)

        publish_guard_index, publish_guard = _named_step(
            publish_steps, "Refuse rerun at the effect-capable publication job"
        )
        publish_guard_run = _step_run(publish_guard, "effect-capable rerun guard")
        for required in (
            'test "${GITHUB_RUN_ATTEMPT}" = "1"',
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"',
            'test "${GITHUB_EVENT_NAME}" = "push"',
            'test "${GITHUB_REF}" = "refs/heads/main"',
        ):
            self.assertIn(required, publish_guard_run)

        authenticate_index, _ = _named_step(
            publish_steps, "Authenticate to GHCR for the single digest-only effect"
        )
        self.assertLess(publish_guard_index, authenticate_index)

        checkout_steps = [
            step for step in publish_steps if step.get("uses") == CHECKOUT_ACTION
        ]
        self.assertEqual(2, len(checkout_steps))
        source_checkout = checkout_steps[1]
        source_checkout_with = source_checkout.get("with")
        self.assertIsInstance(source_checkout_with, dict)
        assert isinstance(source_checkout_with, dict)
        self.assertEqual("${{ env.SOURCE_COMMIT }}", source_checkout_with["ref"])
        self.assertEqual("p2b-source", source_checkout_with["path"])

        _, local_verify = _named_step(
            publish_steps,
            "Build and verify exact integrated P2b runtime before any registry effect",
        )
        local_verify_run = _step_run(local_verify, "local P2b verification")
        for required in (
            'test "$(docker run --rm --entrypoint id "${local_image}" -u)" = "10001"',
            'test "$(docker run --rm --entrypoint id "${local_image}" -g)" = "10001"',
            'docker run --rm "${local_image}" self-check',
            "tools/review_outer.py",
            "ci/review_outer_smoke.py",
            "knowledge/decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md",
        ):
            self.assertIn(required, local_verify_run)

        _, publication = _named_step(
            publish_steps,
            "Publish exact integrated P2b runtime without a remote tag and read back digest",
        )
        publication_run = _step_run(publication, "digest-only publication")
        for required in (
            '--push-by-digest "${IMAGE_NAME}"',
            '--metadata-file "${metadata_file}"',
            'echo "registry_digest=${registry_digest}" >> "${GITHUB_OUTPUT}"',
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -u)" = "10001"',
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -g)" = "10001"',
            'docker run --rm "${digest_ref}" self-check',
        ):
            self.assertIn(required, publication_run)
        self.assertNotIn("docker push ", publication_run)

        attest_steps = [
            step for step in publish_steps if step.get("uses") == ATTEST_ACTION
        ]
        self.assertEqual(1, len(attest_steps))
        attest_with = attest_steps[0].get("with")
        self.assertIsInstance(attest_with, dict)
        assert isinstance(attest_with, dict)
        self.assertEqual("${{ env.IMAGE_NAME }}", attest_with["subject-name"])
        self.assertEqual(
            "${{ steps.publish.outputs.registry_digest }}",
            attest_with["subject-digest"],
        )
        self.assertEqual("true", attest_with["push-to-registry"])

        _, reacquisition = _named_step(
            publish_steps,
            "Verify attestation and anonymously reacquire exact P2b digest",
        )
        reacquisition_run = _step_run(reacquisition, "anonymous digest reacquisition")
        for required in (
            "gh attestation verify",
            '"oci://${digest_ref}" --repo "${GITHUB_REPOSITORY}"',
            'docker image rm "${digest_ref}" >/dev/null',
            "digest image remained cached before anonymous reacquisition",
            'DOCKER_CONFIG="${anonymous_config}"',
            'docker pull --quiet "${digest_ref}"',
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -u)" = "10001"',
            'test "$(docker run --rm --entrypoint id "${digest_ref}" -g)" = "10001"',
            'docker run --rm "${digest_ref}" self-check',
        ):
            self.assertIn(required, reacquisition_run)

        _, reconciliation = _named_step(
            publish_steps, "Reconcile and clean post-publication state"
        )
        reconciliation_run = _step_run(reconciliation, "post-write reconciliation")
        for required in (
            "post-write outcome is ambiguous and no exact digest is available; do not rerun blindly",
            "cleanup_status=0",
            'docker image rm "${digest_ref}" >/dev/null 2>&1 || cleanup_status=1',
            "digest image remained cached before reconciliation reacquisition",
            'DOCKER_CONFIG="${reconcile_config}"',
            'docker pull --quiet "${digest_ref}"',
        ):
            self.assertIn(required, reconciliation_run)

        all_run_text = "\n".join(
            _step_run(step, str(step.get("name", "unnamed step")))
            for step in authorize_steps + publish_steps
            if "run" in step
        )
        self.assertNotIn("docker push ", all_run_text)
        self.assertNotIn("gh release create", all_run_text)

    def test_materialization_has_durable_decision(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_MATERIALIZATION_DECISION_UNAVAILABLE: post-B2 rolling-trust "
            "materialization has no durable Decision 0078",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn(SOURCE_COMMIT, decision)
        self.assertIn(SOURCE_TREE, decision)
        self.assertIn("Decision 0077", decision)
        self.assertIn("digest-only", decision)
        self.assertIn("attest", decision.lower())
        self.assertIn("reacquir", decision.lower())
        self.assertIn("run_attempt", decision)
        self.assertIn("no rerun authority", decision)
        self.assertIn("not a release or promotion", decision.lower())

    def test_materialization_is_governed_and_routed(self) -> None:
        index = INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn(DECISION_RELATIVE_PATH.removeprefix("knowledge/"), index)

        guardrails = GUARDRAILS_PATH.read_text(encoding="utf-8")
        immutable_section = _guardrail_section(
            guardrails, "immutable-provider-ci-adapters"
        )
        self.assertIn(WORKFLOW_RELATIVE_PATH, immutable_section)
        self.assertIn(
            "tests/test_r2a_p2b_integrated_materialization.py", immutable_section
        )
        semantic_section = _guardrail_section(guardrails, "semantic-review-assurance")
        self.assertIn(DECISION_RELATIVE_PATH, semantic_section)
        self.assertIn(WORKFLOW_RELATIVE_PATH, semantic_section)
        self.assertIn(
            "tests/test_r2a_p2b_integrated_materialization.py", semantic_section
        )

        r2a_workflow = R2A_WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(WORKFLOW_RELATIVE_PATH, r2a_workflow)
        self.assertIn(DECISION_RELATIVE_PATH, r2a_workflow)
        self.assertGreaterEqual(
            r2a_workflow.count("tests/test_r2a_p2b_integrated_materialization.py"), 3
        )


if __name__ == "__main__":
    unittest.main()
