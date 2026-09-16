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


class R2AP2bIntegratedMaterializationTests(unittest.TestCase):
    def test_exact_integrated_p2b_has_one_shot_digest_only_materializer(self) -> None:
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            "P2B_OCI_PUBLISHER_UNAVAILABLE: exact integrated P2b has no "
            "protected-main one-shot digest-only OCI materializer",
        )
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
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

        self.assertEqual(
            2,
            workflow_text.count('test "${GITHUB_RUN_ATTEMPT}" = "1"'),
            "both authorization and effect-capable publication must refuse reruns",
        )
        self.assertIn(
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"',
            workflow_text,
        )
        self.assertIn("pulls/${AUTHORIZED_PR_NUMBER}", workflow_text)
        self.assertIn("merge_commit_sha", workflow_text)
        self.assertLess(
            workflow_text.index("Refuse rerun at the effect-capable publication job"),
            workflow_text.index("Authenticate to GHCR for the single digest-only effect"),
        )

        checkout_steps = [
            step
            for step in publish["steps"]
            if isinstance(step, dict) and step.get("uses") == CHECKOUT_ACTION
        ]
        self.assertEqual(2, len(checkout_steps))
        self.assertEqual("${{ env.SOURCE_COMMIT }}", checkout_steps[1]["with"]["ref"])
        self.assertEqual("p2b-source", checkout_steps[1]["with"]["path"])

        attest_steps = [
            step
            for step in publish["steps"]
            if isinstance(step, dict) and step.get("uses") == ATTEST_ACTION
        ]
        self.assertEqual(1, len(attest_steps))
        self.assertIn("--push-by-digest", workflow_text)
        self.assertIn('docker run --rm "${local_image}" self-check', workflow_text)
        self.assertGreaterEqual(workflow_text.count("self-check"), 3)
        self.assertIn("tools/review_outer.py", workflow_text)
        self.assertIn("ci/review_outer_smoke.py", workflow_text)
        self.assertIn(
            "knowledge/decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md",
            workflow_text,
        )
        self.assertIn("DOCKER_CONFIG", workflow_text)
        self.assertIn("anonymous reacquisition", workflow_text)
        self.assertIn("Reconcile and clean post-publication state", workflow_text)
        self.assertIn("do not rerun blindly", workflow_text)
        self.assertNotIn("docker push ", workflow_text)
        self.assertNotIn("gh release create", workflow_text)
        self.assertNotIn("workflow_dispatch", workflow_text)

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
