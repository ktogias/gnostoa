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
    / "0070-protect-r2a-b1-outer-consumer-authority-separately.md"
)
WORKFLOW_PATH = (
    ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
)
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
FOCUSED_TEST_PATH = "tests/test_review_assurance_p2b_consumer_authority_red.py"

B1_SOURCE_REVISION = "0dfd7e5e28e8ccb87e687e0be9dfe846b644c9c3"
B1_SOURCE_TREE = "23a5f083f26f40a8287bc2a724bcd5282a9afa5e"
B1_PUBLIC_SURFACE_DIGEST = (
    "sha256:72df7bfe999db7c84c199ff26424a434197865aaf95b3a5ae9e4e1026d8f5d45"
)
B1_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:fcefee5af6deb089e4b1cbe09e1a0d2f4820a56ac0a6be18faa4dd11b2ab01b0"
)
MATERIALIZATION_MAIN_REVISION = "28cc416480a5f101b3031a8de15ac7d4edb234ea"
MATERIALIZATION_RUN = "34847802228"
ATTESTATION_ID = "47345171"
REKOR_LOG_INDEX = "2831113296"
RECEIPT_COMMENT = "5664611991"

EXPECTED_CONSUMER = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": B1_SOURCE_REVISION,
    "source_tree": B1_SOURCE_TREE,
    "public_surface_digest": B1_PUBLIC_SURFACE_DIGEST,
    "runtime_image": B1_OCI_IMAGE,
    "runtime_revision": B1_SOURCE_REVISION,
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

    def test_outer_consumer_authority_binds_exact_materialized_b1(self) -> None:
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

    def test_separate_outer_consumer_authority_has_durable_decision(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_OUTER_CONSUMER_AUTHORITY_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision 0067", decision)
        self.assertIn("Decision 0069", decision)
        self.assertIn(B1_OCI_IMAGE, decision)
        self.assertIn("outer consumer", decision.lower())
        self.assertIn("inner semantic", decision.lower())
        self.assertIn("closed v1", decision.lower())
        self.assertIn("P2b-B2", decision)
        self.assertIn("does not activate", decision.lower())

    def test_dedicated_workflow_covers_outer_consumer_authority(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '- "tasks/issue-11-r2a-current-advisory-consumer.json"', workflow
        )
        self.assertIn(f'- "{FOCUSED_TEST_PATH}"', workflow)
        self.assertIn(f"python -m ruff format --check \\\n", workflow)
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
            },
            set(implementation),
        )
        self.assertIn(FOCUSED_TEST_PATH, tests)


if __name__ == "__main__":
    unittest.main()
