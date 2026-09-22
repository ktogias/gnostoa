from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from tools.review_check import FORMAT_CHECKER
from tools.review_model import canonical_digest
from tools.review_policy import resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "review-protected-authority-bundle.schema.json"
BASELINE_PATH = (
    ROOT / "knowledge" / "assessments" / "10-q0-reviewer-qualification-baseline.json"
)
POLICY_PATH = ROOT / "policy" / "review-policy.yaml"

Q0_AUTHORITY = "https://github.com/ktogias/gnostoa/issues/10#issuecomment-5771806967"
Q0_OBSERVED_AT = "2026-09-22T05:50:00Z"
Q0_SNAPSHOT_ID = "gnostoa-r2a-qualification-q0-5771806967"
Q0_REVISION = "5771806967"
CURRENT_OUTER_RUNTIME_REVISION = (
    "315487e7a67635ebf3ec3f70f666ef41646102e1"  # pragma: allowlist secret -- public Git commit identity
)
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


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


class ReviewerQualificationQ0Tests(unittest.TestCase):
    def test_q0_candidate_baseline_names_exact_minimal_two_domain_cohort(
        self,
    ) -> None:
        baseline = _load(BASELINE_PATH)
        self.assertEqual(
            "gnostoa-reviewer-qualification-baseline/v1", baseline["schema_version"]
        )
        self.assertEqual("candidate", baseline["status"])
        self.assertEqual(Q0_AUTHORITY, baseline["qualifying_authority"])
        self.assertEqual(
            {
                "snapshot_id": Q0_SNAPSHOT_ID,
                "revision": Q0_REVISION,
                "qualifying_authority": Q0_AUTHORITY,
                "observed_at": Q0_OBSERVED_AT,
                "entries": Q0_ENTRIES,
            },
            baseline["qualification_snapshot"],
        )
        entries = baseline["qualification_snapshot"]["entries"]
        self.assertIsInstance(entries, list)
        assert isinstance(entries, list)
        self.assertEqual(
            {"github-app:coderabbitai", "github-app:gitar-bot"},
            {
                entry["independence_domain_id"]
                for entry in entries
                if isinstance(entry, dict)
            },
        )
        self.assertEqual(
            {
                "state": "BLOCKED_PENDING_PRIOR_INTEGRATED_RUNTIME_PROMOTION",
                "protected_bundle": "tasks/issue-11-r2a-current-advisory.json",
                "current_outer_runtime_revision": CURRENT_OUTER_RUNTIME_REVISION,
                "_public_identity_note": (
                    "# pragma: allowlist secret -- public Git commit identity "
                    "retained for protected runtime binding"
                ),
                "target_snapshot_freshness": {"mode": "not_age_sensitive"},
            },
            baseline["activation"],
        )
        progression = baseline["assurance_progression"]
        self.assertEqual("APPROVE", progression["acceptable_recommendation"])
        surfaces = progression["observed_formal_review_surfaces"]
        self.assertIsInstance(surfaces, list)
        assert isinstance(surfaces, list)
        advancing = [
            item
            for item in surfaces
            if isinstance(item, dict) and item.get("currently_quorum_advancing") is True
        ]
        self.assertEqual(
            [
                {
                    "reviewer_id": "bito-code-review[bot]",
                    "github_review_state": "APPROVED",
                    "normalized_recommendation": "APPROVE",
                    "currently_quorum_advancing": True,
                    "qualification_status": (
                        "observed_approval_surface_not_in_admitted_q0_snapshot"
                    ),
                }
            ],
            advancing,
        )
        self.assertEqual(
            "SECOND_APPROVAL_CAPABLE_QUALIFIED_DOMAIN_UNESTABLISHED",
            progression["current_result"],
        )

    def test_q0_source_schema_can_validate_future_nonempty_protected_snapshot(
        self,
    ) -> None:
        schema = _load(BUNDLE_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)

        live_bundle = _load(BUNDLE_PATH)
        self.assertEqual([], live_bundle["qualification_snapshot"]["entries"])

        future = copy.deepcopy(live_bundle)
        baseline = _load(BASELINE_PATH)
        future["qualification_snapshot"] = copy.deepcopy(
            baseline["qualification_snapshot"]
        )
        future["authority"]["qualification_snapshot_digest"] = canonical_digest(
            future["qualification_snapshot"]
        )
        self.assertEqual([], list(validator.iter_errors(future)))

        unknown = copy.deepcopy(future)
        unknown["qualification_snapshot"]["entries"][0][
            "provider_brand_grants_independence"
        ] = True
        self.assertNotEqual([], list(validator.iter_errors(unknown)))

        missing_domain = copy.deepcopy(future)
        missing_domain["qualification_snapshot"]["entries"][0].pop(
            "independence_domain_id"
        )
        self.assertNotEqual([], list(validator.iter_errors(missing_domain)))

    def test_q0_does_not_activate_candidate_qualification_before_runtime_promotion(
        self,
    ) -> None:
        live_bundle = _load(BUNDLE_PATH)
        self.assertEqual([], live_bundle["qualification_snapshot"]["entries"])
        self.assertEqual(
            {"mode": "max_age", "seconds": 86400},
            live_bundle["policy"]["qualification"]["snapshot_freshness"],
        )
        self.assertEqual(
            resolve_project_policy(POLICY_PATH, "critical"),
            live_bundle["policy"],
        )
        self.assertFalse(live_bundle["policy"]["qualification"]["owner_reviews_count"])
        self.assertEqual(
            ["APPROVE"], live_bundle["policy"]["quorum"]["acceptable_recommendations"]
        )
        self.assertEqual(2, live_bundle["policy"]["quorum"]["minimum_distinct_domains"])


if __name__ == "__main__":
    unittest.main()
