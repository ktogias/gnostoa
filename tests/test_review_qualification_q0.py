from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.review_check import FORMAT_CHECKER
from tools.review_model import canonical_digest
from tools.review_policy import resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
SCHEMA_PATH = ROOT / "schemas" / "review-protected-authority-bundle.schema.json"
POLICY_PATH = ROOT / "policy" / "review-policy.yaml"

Q0_AUTHORITY = "https://github.com/ktogias/gnostoa/issues/10#issuecomment-5771806967"
Q0_OBSERVED_AT = "2026-09-22T05:50:00Z"
Q0_SNAPSHOT_ID = "gnostoa-r2a-qualification-q0-5771806967"
Q0_REVISION = "5771806967"

Q0_ENTRIES = [
    {
        "reviewer_id": "coderabbitai[bot]",
        "source_id": "retained-review-evidence",
        "independence_domain_id": "github-app:coderabbitai",
        "capability_ids": ["semantic-review"],
        "status": "established",
        "observed_at": Q0_OBSERVED_AT,
        "owner_relation": "non_owner",
        "scope": {"repository": "https://github.com/ktogias/gnostoa"},
        "provenance": {
            "basis": "q0-source-bound-reviewer-execution",
            "evidence": [
                "https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765178931",
                "https://github.com/ktogias/gnostoa/pull/297#pullrequestreview-5273613065",
            ],
            "independence_axes": [
                "authenticated-external-github-app-principal",
                "provider-controlled-review-execution",
                "read-only-review-role-for-qualified-evidence",
                "exact-head-attribution",
            ],
            "limitations": ["model-runtime-diversity-unestablished"],
        },
    },
    {
        "reviewer_id": "gitar-bot[bot]",
        "source_id": "retained-review-evidence",
        "independence_domain_id": "github-app:gitar-bot",
        "capability_ids": ["semantic-review"],
        "status": "established",
        "observed_at": Q0_OBSERVED_AT,
        "owner_relation": "non_owner",
        "scope": {"repository": "https://github.com/ktogias/gnostoa"},
        "provenance": {
            "basis": "q0-source-bound-reviewer-execution",
            "evidence": [
                "https://github.com/ktogias/gnostoa/pull/297#issuecomment-5771584848",
                "https://github.com/ktogias/gnostoa/pull/297#issuecomment-5771632564",
                "https://github.com/ktogias/gnostoa/pull/297#pullrequestreview-5273039133",
            ],
            "independence_axes": [
                "authenticated-external-github-app-principal",
                "provider-controlled-review-execution",
                "read-only-review-role-for-qualified-evidence",
                "exact-head-attribution",
            ],
            "limitations": ["model-runtime-diversity-unestablished"],
        },
    },
]


def _bundle() -> dict[str, object]:
    value = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("protected review-authority bundle must be an object")
    return value


class ReviewerQualificationQ0Tests(unittest.TestCase):
    def test_q0_protected_snapshot_establishes_exact_minimal_two_domain_cohort(
        self,
    ) -> None:
        bundle = _bundle()
        qualification = bundle["qualification_snapshot"]
        self.assertEqual(
            {
                "snapshot_id": Q0_SNAPSHOT_ID,
                "revision": Q0_REVISION,
                "qualifying_authority": Q0_AUTHORITY,
                "observed_at": Q0_OBSERVED_AT,
                "entries": Q0_ENTRIES,
            },
            qualification,
        )
        authority = bundle["authority"]
        self.assertEqual(
            canonical_digest(qualification),
            authority["qualification_snapshot_digest"],
        )
        self.assertEqual(
            {"github-app:coderabbitai", "github-app:gitar-bot"},
            {entry["independence_domain_id"] for entry in qualification["entries"]},
        )
        self.assertTrue(
            all(
                entry["owner_relation"] == "non_owner"
                for entry in qualification["entries"]
            )
        )

    def test_q0_activates_closed_existing_v1_qualification_entry_shape(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
        bundle = _bundle()
        self.assertEqual([], list(validator.iter_errors(bundle)))

        unknown = copy.deepcopy(bundle)
        qualification = unknown["qualification_snapshot"]
        qualification["entries"][0]["provider_brand_grants_independence"] = True
        self.assertNotEqual([], list(validator.iter_errors(unknown)))

        missing_domain = copy.deepcopy(bundle)
        qualification = missing_domain["qualification_snapshot"]
        qualification["entries"][0].pop("independence_domain_id")
        self.assertNotEqual([], list(validator.iter_errors(missing_domain)))

    def test_q0_keeps_quorum_and_owner_exclusion_but_removes_daily_qualification_rewrite(
        self,
    ) -> None:
        bundle = _bundle()
        protected_policy = bundle["policy"]
        self.assertEqual(
            resolve_project_policy(POLICY_PATH, "critical"), protected_policy
        )
        self.assertEqual(
            ["semantic-review"],
            protected_policy["qualification"]["required_capabilities"],
        )
        self.assertFalse(protected_policy["qualification"]["owner_reviews_count"])
        self.assertEqual(
            {"mode": "not_age_sensitive"},
            protected_policy["qualification"]["snapshot_freshness"],
        )
        self.assertEqual(2, protected_policy["quorum"]["minimum_distinct_domains"])
        self.assertEqual(
            ["APPROVE"], protected_policy["quorum"]["acceptable_recommendations"]
        )
        self.assertEqual(
            canonical_digest(protected_policy),
            bundle["authority"]["policy_digest"],
        )


if __name__ == "__main__":
    unittest.main()
