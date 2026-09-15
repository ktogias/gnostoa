from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from tools.review_check import FORMAT_CHECKER

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
CONSUMER_AUTHORITY_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
CONSUMER_SCHEMA_PATH = (
    ROOT / "schemas" / "review-protected-consumer-authority.schema.json"
)
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0073-promote-r2a-b15-outer-consumer-authority.md"
)
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
FOCUSED_TEST_PATH = "tests/test_review_assurance_p2b_consumer_authority_red.py"
MATERIALIZATION_DECISION_PATH = (
    "knowledge/decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md"
)

B15_SOURCE_REVISION = "7093fd043f2269e09da74b03ce9d35fb6aece5da"  # pragma: allowlist secret -- public source revision
B15_SOURCE_TREE = "e7a4f2142e72efd52133f4719d8acf9b2dccb89d"  # pragma: allowlist secret -- public source tree
B15_PUBLIC_SURFACE_DIGEST = "sha256:b07aec4907919c0c9a92e4382524db4f7981bd346a5a1292f5ac48e4a1e6238e"  # pragma: allowlist secret -- public surface digest
B15_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:821b523d2ebe80d0194cfc366ff70c59e90b99c5524dd82df8e866ccfa00e1c3"  # pragma: allowlist secret -- public OCI digest
)
MATERIALIZATION_MAIN_REVISION = "8b189f66c92859b4ef75a91d962f4aec38b30408"  # pragma: allowlist secret -- public protected-main revision
MATERIALIZATION_RUN = "34905764252"
ATTESTATION_ID = "47472753"
REKOR_LOG_INDEX = "2835934017"
RECEIPT_COMMENT = "5671868333"

EXPECTED_CONSUMER = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": B15_SOURCE_REVISION,
    "source_tree": B15_SOURCE_TREE,
    "public_surface_digest": B15_PUBLIC_SURFACE_DIGEST,
    "runtime_image": B15_OCI_IMAGE,
    "runtime_revision": B15_SOURCE_REVISION,
    "supported_input_schema_versions": ["1.0"],
    "status": "accepted",
}


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


class ReviewAssuranceP2bConsumerAuthorityRedTests(unittest.TestCase):
    def test_outer_consumer_authority_is_separate_and_schema_closed(self) -> None:
        self.assertTrue(
            CONSUMER_SCHEMA_PATH.is_file(),
            "P2B_OUTER_CONSUMER_AUTHORITY_SCHEMA_UNAVAILABLE",
        )
        self.assertTrue(
            CONSUMER_AUTHORITY_PATH.is_file(),
            "P2B_OUTER_CONSUMER_AUTHORITY_UNAVAILABLE",
        )
        schema = _load(CONSUMER_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        authority = _load(CONSUMER_AUTHORITY_PATH)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
        self.assertEqual([], list(validator.iter_errors(authority)))

        unknown = copy.deepcopy(authority)
        unknown["candidate_claim"] = True
        self.assertNotEqual([], list(validator.iter_errors(unknown)))

    def test_outer_consumer_authority_binds_exact_materialized_b15(self) -> None:
        self.assertTrue(
            CONSUMER_AUTHORITY_PATH.is_file(),
            "P2B_OUTER_CONSUMER_AUTHORITY_UNAVAILABLE",
        )
        authority = _load(CONSUMER_AUTHORITY_PATH)
        self.assertEqual("1.0", authority.get("schema_version"))
        self.assertEqual(
            {
                "kind": "gnostoa-protected-main-consumer-record",
                "value": "tasks/issue-11-r2a-current-advisory-consumer.json:v1",
            },
            authority.get("subject"),
        )
        self.assertEqual(EXPECTED_CONSUMER, authority.get("expected_consumer"))
        self.assertEqual(EXPECTED_CONSUMER, authority.get("acquired_consumer"))

        runtime_image = EXPECTED_CONSUMER["runtime_image"]
        self.assertIsNotNone(
            re.fullmatch(r"ghcr\.io/ktogias/gnostoa@sha256:[0-9a-f]{64}", runtime_image)
        )
        materialization = authority.get("materialization")
        self.assertEqual(
            {
                "protected_main_revision": MATERIALIZATION_MAIN_REVISION,
                "workflow_run": MATERIALIZATION_RUN,
                "attestation_id": ATTESTATION_ID,
                "rekor_log_index": REKOR_LOG_INDEX,
                "receipt": (
                    "https://github.com/ktogias/gnostoa/issues/11#issuecomment-"
                    + RECEIPT_COMMENT
                ),
            },
            materialization,
        )

    def test_inner_semantic_authority_remains_v1_and_consumer_free(self) -> None:
        semantic = _load(SEMANTIC_BUNDLE_PATH)
        self.assertEqual("1.0", semantic.get("schema_version"))
        self.assertEqual(
            {
                "schema_version",
                "authority",
                "policy",
                "qualification_snapshot",
                "acquired_judge",
            },
            set(semantic),
        )
        semantic_authority = semantic["authority"]
        self.assertIsInstance(semantic_authority, dict)
        assert isinstance(semantic_authority, dict)
        self.assertIn("expected_judge", semantic_authority)
        self.assertNotIn("expected_consumer", semantic_authority)
        self.assertNotIn("acquired_consumer", semantic)

    def test_b15_outer_consumer_authority_has_durable_promotion_decision(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B15_OUTER_CONSUMER_AUTHORITY_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision 0070", decision)
        self.assertIn("Decision 0071", decision)
        self.assertIn("Decision 0072", decision)
        self.assertIn(B15_SOURCE_REVISION, decision)
        self.assertIn(B15_SOURCE_TREE, decision)
        self.assertIn(B15_PUBLIC_SURFACE_DIGEST, decision)
        self.assertIn(B15_OCI_IMAGE, decision)
        self.assertIn(MATERIALIZATION_MAIN_REVISION, decision)
        self.assertIn(MATERIALIZATION_RUN, decision)
        self.assertIn(ATTESTATION_ID, decision)
        self.assertIn(REKOR_LOG_INDEX, decision)
        self.assertIn(RECEIPT_COMMENT, decision)
        self.assertIn("B1.5", decision)
        self.assertIn("outer consumer", decision.lower())
        self.assertIn("inner semantic", decision.lower())
        self.assertIn("closed v1", decision.lower())
        self.assertIn("P2b-B2", decision)
        self.assertIn("does not activate", decision.lower())
        self.assertIn("knowledge/index.md", decision)
        self.assertIn("navigation-only", decision.lower())
        self.assertIn("index-only", decision.lower())
        self.assertIn("semantic-review-assurance", decision)
        self.assertIn("dedicated R2A", decision)

    def test_dedicated_workflow_covers_outer_consumer_authority(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn('- "tasks/issue-11-r2a-current-advisory-consumer.json"', workflow)
        self.assertIn(f'- "{MATERIALIZATION_DECISION_PATH}"', workflow)
        self.assertIn(
            '- "knowledge/decisions/0073-promote-r2a-b15-outer-consumer-authority.md"',
            workflow,
        )
        self.assertIn(f'- "{FOCUSED_TEST_PATH}"', workflow)
        self.assertNotIn('- "knowledge/index.md"', workflow)
        self.assertIn("python -m ruff format --check \\\n", workflow)
        self.assertGreaterEqual(workflow.count(FOCUSED_TEST_PATH), 4)
        self.assertIn(f"PYTHONPATH=. python {FOCUSED_TEST_PATH}", workflow)

    def test_semantic_review_guardrail_declares_outer_consumer_authority(self) -> None:
        document = yaml.safe_load(GUARDRAILS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(document, dict)
        guardrails = document.get("guardrails")
        self.assertIsInstance(guardrails, list)
        assert isinstance(guardrails, list)
        guardrail = next(
            entry
            for entry in guardrails
            if isinstance(entry, dict)
            and entry.get("id") == "semantic-review-assurance"
        )
        implementation = guardrail.get("implementation")
        tests = guardrail.get("tests")
        self.assertIsInstance(implementation, list)
        self.assertIsInstance(tests, list)
        assert isinstance(implementation, list)
        assert isinstance(tests, list)
        self.assertLessEqual(
            {
                "schemas/review-protected-consumer-authority.schema.json",
                "tasks/issue-11-r2a-current-advisory-consumer.json",
                "knowledge/decisions/0070-protect-r2a-b1-outer-consumer-authority-separately.md",
                "knowledge/decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md",
                "knowledge/decisions/0073-promote-r2a-b15-outer-consumer-authority.md",
            },
            set(implementation),
        )
        self.assertNotIn("knowledge/index.md", implementation)
        self.assertIn(FOCUSED_TEST_PATH, tests)


if __name__ == "__main__":
    unittest.main()
