from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.review_check import FORMAT_CHECKER
from tools.review_model import canonical_digest
from tools.review_policy import resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
BUNDLE_SCHEMA = ROOT / "schemas" / "review-protected-authority-bundle.schema.json"
POLICY = ROOT / "policy" / "review-policy.yaml"

EXPECTED_REVIEWERS = {
    ("coderabbitai[bot]", "retained-review-evidence"),
    ("qodo-code-review[bot]", "retained-review-evidence"),
}
EXPECTED_DOMAINS = {
    "external-review-principal-coderabbit",
    "external-review-principal-qodo",
}


class Q0ProtectedQualificationRedTests(unittest.TestCase):
    def test_protected_bundle_admits_the_owner_selected_q0_entries(self) -> None:
        bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
        schema = json.loads(BUNDLE_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = list(
            Draft202012Validator(schema, format_checker=FORMAT_CHECKER).iter_errors(
                bundle
            )
        )
        self.assertEqual([], errors)

        qualification = bundle["qualification_snapshot"]
        entries = qualification["entries"]
        self.assertEqual(2, len(entries))
        self.assertEqual(
            EXPECTED_REVIEWERS,
            {(item["reviewer_id"], item["source_id"]) for item in entries},
        )
        self.assertEqual(
            EXPECTED_DOMAINS,
            {item["independence_domain_id"] for item in entries},
        )
        for item in entries:
            self.assertEqual(["semantic-review"], item["capability_ids"])
            self.assertEqual("established", item["status"])
            self.assertEqual("non_owner", item["owner_relation"])
            self.assertEqual({"repository": "ktogias/gnostoa"}, item["scope"])
            provenance = item["provenance"]
            self.assertIn("evidence_urls", provenance)
            self.assertIn("independence_basis", provenance)
            self.assertIn("limitations", provenance)

    def test_q0_keeps_recommendation_and_quorum_semantics_strict(self) -> None:
        effective = resolve_project_policy(POLICY, "critical")
        self.assertEqual("1.1", effective["version"])
        self.assertEqual(
            {"mode": "not_age_sensitive"},
            effective["qualification"]["snapshot_freshness"],
        )
        self.assertEqual(["semantic-review"], effective["qualification"]["required_capabilities"])
        self.assertFalse(effective["qualification"]["owner_reviews_count"])
        self.assertEqual(2, effective["quorum"]["minimum_distinct_domains"])
        self.assertEqual(["APPROVE"], effective["quorum"]["acceptable_recommendations"])
        self.assertEqual({"mode": "max_age", "seconds": 900}, effective["subject"]["freshness"])
        self.assertEqual({"mode": "max_age", "seconds": 900}, effective["collection"]["freshness"])

    def test_q0_authority_binds_policy_and_qualification_exactly(self) -> None:
        bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
        self.assertEqual(
            canonical_digest(bundle["policy"]),
            bundle["authority"]["policy_digest"],
        )
        self.assertEqual(
            canonical_digest(bundle["qualification_snapshot"]),
            bundle["authority"]["qualification_snapshot_digest"],
        )
        self.assertEqual(resolve_project_policy(POLICY, "critical"), bundle["policy"])


if __name__ == "__main__":
    unittest.main()
