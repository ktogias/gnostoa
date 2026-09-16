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
HISTORICAL_PROMOTION_DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0073-promote-r2a-b15-outer-consumer-authority.md"
)
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0076-promote-r2a-b16-outer-consumer-authority.md"
)
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
FOCUSED_TEST_PATH = "tests/test_review_assurance_p2b_consumer_authority_red.py"
HISTORICAL_MATERIALIZATION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md"
)
HISTORICAL_PROMOTION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0073-promote-r2a-b15-outer-consumer-authority.md"
)
MATERIALIZATION_DECISION_PATH = (
    "knowledge/decisions/0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md"
)
PROMOTION_DECISION_PATH = (
    "knowledge/decisions/0076-promote-r2a-b16-outer-consumer-authority.md"
)

B16_SOURCE_REVISION = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- public source revision
B16_SOURCE_TREE = "ff38abe5718ebc550054ea6af18a73d0aef8e514"  # pragma: allowlist secret -- public source tree
B16_PUBLIC_SURFACE_DIGEST = "sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57"  # pragma: allowlist secret -- public surface digest
B16_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867"  # pragma: allowlist secret -- public OCI digest
)
MATERIALIZATION_MAIN_REVISION = "f8aac5159c36a0ff8cb9a22dcc933285c6b52b81"  # pragma: allowlist secret -- public protected-main revision
MATERIALIZATION_RUN = "35058782405"
ATTESTATION_ID = "47823269"
REKOR_LOG_INDEX = "2855771710"
RECEIPT_COMMENT = "5692487663"
CONTAINMENT_RECEIPT_COMMENT = "5694072707"
REVALIDATION_RECEIPT_COMMENT = "5694179373"

EXPECTED_CONSUMER = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": B16_SOURCE_REVISION,
    "source_tree": B16_SOURCE_TREE,
    "public_surface_digest": B16_PUBLIC_SURFACE_DIGEST,
    "runtime_image": B16_OCI_IMAGE,
    "runtime_revision": B16_SOURCE_REVISION,
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

    def test_outer_consumer_authority_binds_exact_materialized_b16(self) -> None:
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
        self.assertIsInstance(runtime_image, str)
        assert isinstance(runtime_image, str)
        self.assertIsNotNone(
            re.fullmatch(r"ghcr\.io/ktogias/gnostoa@sha256:[0-9a-f]{64}", runtime_image)
        )
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
            authority.get("materialization"),
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

    def test_b15_promotion_decision_remains_historical_evidence(self) -> None:
        self.assertTrue(HISTORICAL_PROMOTION_DECISION_PATH.is_file())
        decision = HISTORICAL_PROMOTION_DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("B1.5", decision)
        self.assertIn(
            "ghcr.io/ktogias/gnostoa@sha256:"
            "821b523d2ebe80d0194cfc366ff70c59e90b99c5524dd82df8e866ccfa00e1c3",
            decision,
        )
        self.assertIn("does not activate", decision.lower())

    def test_b16_outer_consumer_authority_has_durable_promotion_decision(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B16_OUTER_CONSUMER_AUTHORITY_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        for required in (
            "Decision 0070",
            "Decision 0073",
            "Decision 0074",
            "Decision 0075",
            B16_SOURCE_REVISION,
            B16_SOURCE_TREE,
            B16_PUBLIC_SURFACE_DIGEST,
            B16_OCI_IMAGE,
            MATERIALIZATION_MAIN_REVISION,
            MATERIALIZATION_RUN,
            ATTESTATION_ID,
            REKOR_LOG_INDEX,
            RECEIPT_COMMENT,
            CONTAINMENT_RECEIPT_COMMENT,
            REVALIDATION_RECEIPT_COMMENT,
            "target: /decisions/0073-promote-r2a-b15-outer-consumer-authority.md",
            "B1.6",
            "P2b-B2",
            "knowledge/index.md",
            "semantic-review-assurance",
            "dedicated R2A",
        ):
            self.assertIn(required, decision)
        self.assertIn("outer consumer", decision.lower())
        self.assertIn("inner semantic", decision.lower())
        self.assertIn("closed v1", decision.lower())
        self.assertIn("does not activate", decision.lower())
        self.assertIn("navigation-only", decision.lower())
        self.assertIn("index-only", decision.lower())

    def test_dedicated_workflow_covers_b16_outer_consumer_authority(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        for protected_path in (
            "tasks/issue-11-r2a-current-advisory-consumer.json",
            HISTORICAL_MATERIALIZATION_DECISION_FILTER_PATH,
            HISTORICAL_PROMOTION_DECISION_FILTER_PATH,
            MATERIALIZATION_DECISION_PATH,
            PROMOTION_DECISION_PATH,
            FOCUSED_TEST_PATH,
        ):
            self.assertIn(f'- "{protected_path}"', workflow)
        self.assertNotIn('- "knowledge/index.md"', workflow)
        self.assertIn("python -m ruff format --check \\\n", workflow)
        self.assertGreaterEqual(workflow.count(FOCUSED_TEST_PATH), 4)
        self.assertIn(f"PYTHONPATH=. python {FOCUSED_TEST_PATH}", workflow)

    def test_semantic_review_guardrail_declares_b16_outer_consumer_authority(
        self,
    ) -> None:
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
                "knowledge/decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md",
                MATERIALIZATION_DECISION_PATH,
                PROMOTION_DECISION_PATH,
            },
            set(implementation),
        )
        self.assertNotIn("knowledge/index.md", implementation)
        self.assertIn(FOCUSED_TEST_PATH, tests)


if __name__ == "__main__":
    unittest.main()
