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
HISTORICAL_B15_PROMOTION_DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0073-promote-r2a-b15-outer-consumer-authority.md"
)
HISTORICAL_B16_PROMOTION_DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0076-promote-r2a-b16-outer-consumer-authority.md"
)
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0079-promote-r2a-p2b-outer-consumer-authority.md"
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
B16_MATERIALIZATION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md"
)
B16_PROMOTION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0076-promote-r2a-b16-outer-consumer-authority.md"
)
P2B_ACTIVATION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md"
)
P2B_MATERIALIZATION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md"
)
P2B_PROMOTION_DECISION_FILTER_PATH = (
    "knowledge/decisions/0079-promote-r2a-p2b-outer-consumer-authority.md"
)

P2B_SOURCE_REVISION = "2aa1ed3217c42819155b8ff36385b000720ba4f8"  # pragma: allowlist secret -- public source revision
P2B_SOURCE_TREE = "4cda4e4a704cb518f56201423e313d4dd9db5e24"  # pragma: allowlist secret -- public source tree
P2B_PUBLIC_SURFACE_DIGEST = "sha256:b69f11e1efe181f959a14310fed0a35d3533114d734de584790a85cba7bdb565"  # pragma: allowlist secret -- public surface digest
P2B_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281"  # pragma: allowlist secret -- public OCI digest
)
MATERIALIZATION_MAIN_REVISION = "8feeb816d01ebda267e79ef57d5da7c0ccf61207"  # pragma: allowlist secret -- public protected-main revision
MATERIALIZATION_RUN = "35136892751"
ATTESTATION_ID = "47999464"
REKOR_LOG_INDEX = "2866053656"
RECEIPT_COMMENT = "5703489461"
HISTORICAL_B16_CONTAINMENT_RECEIPT_COMMENT = "5694072707"
HISTORICAL_B16_REVALIDATION_RECEIPT_COMMENT = "5694179373"

EXPECTED_CONSUMER = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": P2B_SOURCE_REVISION,
    "source_tree": P2B_SOURCE_TREE,
    "public_surface_digest": P2B_PUBLIC_SURFACE_DIGEST,
    "runtime_image": P2B_OCI_IMAGE,
    "runtime_revision": P2B_SOURCE_REVISION,
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

    def test_outer_consumer_authority_binds_exact_materialized_p2b(self) -> None:
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
        self.assertTrue(HISTORICAL_B15_PROMOTION_DECISION_PATH.is_file())
        decision = HISTORICAL_B15_PROMOTION_DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("B1.5", decision)
        self.assertIn(
            "ghcr.io/ktogias/gnostoa@sha256:"
            "821b523d2ebe80d0194cfc366ff70c59e90b99c5524dd82df8e866ccfa00e1c3",  # pragma: allowlist secret -- historical public OCI digest
            decision,
        )
        self.assertIn("does not activate", decision.lower())

    def test_b16_promotion_decision_remains_historical_evidence(self) -> None:
        self.assertTrue(HISTORICAL_B16_PROMOTION_DECISION_PATH.is_file())
        decision = HISTORICAL_B16_PROMOTION_DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("B1.6", decision)
        self.assertIn(
            "ghcr.io/ktogias/gnostoa@sha256:"
            "d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867",  # pragma: allowlist secret -- historical public OCI digest
            decision,
        )
        self.assertIn(HISTORICAL_B16_CONTAINMENT_RECEIPT_COMMENT, decision)
        self.assertIn(HISTORICAL_B16_REVALIDATION_RECEIPT_COMMENT, decision)
        self.assertIn("does not activate", decision.lower())

    def test_p2b_outer_consumer_authority_has_durable_promotion_decision(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_OUTER_CONSUMER_AUTHORITY_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        for required in (
            "Decision 0070",
            "Decision 0076",
            "Decision 0077",
            "Decision 0078",
            P2B_SOURCE_REVISION,
            P2B_SOURCE_TREE,
            P2B_PUBLIC_SURFACE_DIGEST,
            P2B_OCI_IMAGE,
            MATERIALIZATION_MAIN_REVISION,
            MATERIALIZATION_RUN,
            ATTESTATION_ID,
            REKOR_LOG_INDEX,
            RECEIPT_COMMENT,
            "target: /decisions/0076-promote-r2a-b16-outer-consumer-authority.md",
            "OCI(P2b)",
            "subsequent candidate",
            "negative read-back",
            "stale B1.x",
            "knowledge/index.md",
            "semantic-review-assurance",
            "dedicated R2A",
        ):
            self.assertIn(required, decision)
        self.assertIn("outer consumer", decision.lower())
        self.assertIn("inner semantic", decision.lower())
        self.assertIn("closed v1", decision.lower())
        self.assertIn("does not claim", decision.lower())
        self.assertIn("navigation-only", decision.lower())
        self.assertIn("index-only", decision.lower())

    def test_dedicated_workflow_covers_p2b_outer_consumer_authority(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        for protected_path in (
            "tasks/issue-11-r2a-current-advisory-consumer.json",
            HISTORICAL_MATERIALIZATION_DECISION_FILTER_PATH,
            HISTORICAL_PROMOTION_DECISION_FILTER_PATH,
            B16_MATERIALIZATION_DECISION_FILTER_PATH,
            B16_PROMOTION_DECISION_FILTER_PATH,
            P2B_ACTIVATION_DECISION_FILTER_PATH,
            P2B_MATERIALIZATION_DECISION_FILTER_PATH,
            P2B_PROMOTION_DECISION_FILTER_PATH,
            FOCUSED_TEST_PATH,
        ):
            self.assertIn(f'- "{protected_path}"', workflow)
        self.assertNotIn('- "knowledge/index.md"', workflow)
        self.assertIn("python -m ruff format --check \\\n", workflow)
        self.assertGreaterEqual(workflow.count(FOCUSED_TEST_PATH), 4)
        self.assertIn(f"PYTHONPATH=. python {FOCUSED_TEST_PATH}", workflow)

    def test_semantic_review_guardrail_declares_p2b_outer_consumer_authority(
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
                B16_MATERIALIZATION_DECISION_FILTER_PATH,
                B16_PROMOTION_DECISION_FILTER_PATH,
                P2B_ACTIVATION_DECISION_FILTER_PATH,
                P2B_MATERIALIZATION_DECISION_FILTER_PATH,
                P2B_PROMOTION_DECISION_FILTER_PATH,
            },
            set(implementation),
        )
        self.assertNotIn("knowledge/index.md", implementation)
        self.assertIn(FOCUSED_TEST_PATH, tests)


if __name__ == "__main__":
    unittest.main()
