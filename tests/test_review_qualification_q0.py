from __future__ import annotations

import copy
import json
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

from tools import review_check, review_outer
from tools.review_check import FORMAT_CHECKER
from tools.review_model import canonical_digest, canonical_json
from tools.review_policy import resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
CONSUMER_AUTHORITY_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "review-protected-authority-bundle.schema.json"
BASELINE_PATH = (
    ROOT / "knowledge" / "assessments" / "10-q0-reviewer-qualification-baseline.json"
)
POLICY_PATH = ROOT / "policy" / "review-policy.yaml"
REVIEW_CASES_PATH = ROOT / "tests" / "fixtures" / "review_check" / "cases.json"

Q0_AUTHORITY = "https://github.com/ktogias/gnostoa/issues/10#issuecomment-5771806967"
Q0_OBSERVED_AT = "2026-09-22T05:50:00Z"
Q0_SNAPSHOT_ID = "gnostoa-r2a-qualification-q0-5771806967"
Q0_REVISION = "5771806967"
CURRENT_OUTER_RUNTIME_BINDING = (
    "tasks/issue-11-r2a-current-advisory-consumer.json:"
    "expected_consumer.source_revision"
)
OUTER_TRANSPORT_CATALOG_BINDING = (
    "tools/review_outer.py:_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES"
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


def _review_case_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = _load(REVIEW_CASES_PATH)
    base = fixture["base"]
    if not isinstance(base, dict):
        raise AssertionError("review-assurance fixture base must be an object")
    input_document = copy.deepcopy(base["input"])
    policy_document = copy.deepcopy(base["policy"])
    if not isinstance(input_document, dict) or not isinstance(policy_document, dict):
        raise AssertionError("review-assurance base documents must be objects")
    context = input_document.get("evaluation_context")
    if isinstance(context, dict) and context.get("mode") == "historical_replay":
        context["fixture_only"] = True
    return input_document, policy_document


def _qualification_entries(
    input_document: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    qualification = input_document["qualification_snapshot"]
    if not isinstance(qualification, dict):
        raise AssertionError("qualification_snapshot must be an object")
    entries_value = qualification["entries"]
    if not isinstance(entries_value, list):
        raise AssertionError("qualification entries must be an array")
    if not all(isinstance(entry, dict) for entry in entries_value):
        raise AssertionError("qualification entries must be objects")
    return qualification, cast(list[dict[str, Any]], entries_value)


def _refresh_qualification_digest(input_document: dict[str, Any]) -> None:
    qualification = input_document["qualification_snapshot"]
    if not isinstance(qualification, dict):
        raise AssertionError("qualification_snapshot must be an object")
    authority = input_document["authority"]
    if not isinstance(authority, dict):
        raise AssertionError("authority must be an object")
    authority["qualification_snapshot_digest"] = canonical_digest(qualification)


def _stale_qualification(
    entries: list[dict[str, Any]],
    qualification: dict[str, Any],
) -> None:
    qualification["observed_at"] = "2026-09-10T00:00:00Z"
    for entry in entries:
        entry["observed_at"] = "2026-09-10T00:00:00Z"


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
        entries_value = baseline["qualification_snapshot"]["entries"]
        self.assertIsInstance(entries_value, list)
        entries = cast(list[object], entries_value)
        self.assertEqual(
            {"github-app:coderabbitai", "github-app:gitar-bot"},
            {
                entry["independence_domain_id"]
                for entry in entries
                if isinstance(entry, dict)
            },
        )
        live_bundle = _load(BUNDLE_PATH)
        self.assertIsInstance(
            live_bundle["authority"]["expected_judge"]["source_revision"], str
        )
        self.assertEqual(
            CURRENT_OUTER_RUNTIME_BINDING,
            baseline["activation"]["current_outer_runtime_binding"],
        )

        self.assertEqual(
            {
                "state": "BLOCKED_PENDING_PRIOR_INTEGRATED_RUNTIME_PROMOTION",
                "protected_bundle": "tasks/issue-11-r2a-current-advisory.json",
                "current_outer_runtime_binding": CURRENT_OUTER_RUNTIME_BINDING,
                "required_transport_catalog": OUTER_TRANSPORT_CATALOG_BINDING,
                "target_snapshot_freshness": {"mode": "not_age_sensitive"},
            },
            baseline["activation"],
        )
        progression = baseline["assurance_progression"]
        self.assertEqual("APPROVE", progression["acceptable_recommendation"])
        surfaces_value = progression["observed_formal_review_surfaces"]
        self.assertIsInstance(surfaces_value, list)
        surfaces = cast(list[object], surfaces_value)
        advancing = [
            item
            for item in surfaces
            if isinstance(item, dict) and item.get("currently_quorum_advancing") is True
        ]
        self.assertEqual([], advancing)
        approval_capable = [
            item
            for item in surfaces
            if isinstance(item, dict) and item.get("recommendation_acceptable") is True
        ]
        self.assertEqual(1, len(approval_capable))
        self.assertEqual("bito-code-review[bot]", approval_capable[0]["reviewer_id"])
        self.assertFalse(approval_capable[0]["qualified_in_candidate_snapshot"])
        self.assertFalse(approval_capable[0]["currently_quorum_advancing"])
        self.assertEqual(
            "POLICY_ACCEPTABLE_TWO_DOMAIN_QUALIFIED_COHORT_UNESTABLISHED",
            progression["current_result"],
        )

    def test_q0_activation_binding_targets_outer_consumer_not_inner_judge(
        self,
    ) -> None:
        baseline = _load(BASELINE_PATH)
        live_bundle = _load(BUNDLE_PATH)
        consumer_authority = _load(CONSUMER_AUTHORITY_PATH)

        expected_consumer = consumer_authority["expected_consumer"]
        acquired_consumer = consumer_authority["acquired_consumer"]
        self.assertEqual(expected_consumer, acquired_consumer)
        # skipcq: PYL-W0212 -- intentional white-box Q0 transport-authority test
        transport_catalog = review_outer._HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES
        self.assertIn(canonical_json(expected_consumer), transport_catalog)
        self.assertEqual(
            "current_advisory_outer_consumer",
            expected_consumer["role"],
        )
        self.assertNotEqual(
            live_bundle["authority"]["expected_judge"]["source_revision"],
            expected_consumer["source_revision"],
        )
        self.assertEqual(
            CURRENT_OUTER_RUNTIME_BINDING,
            baseline["activation"]["current_outer_runtime_binding"],
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

        empty_capabilities = copy.deepcopy(future)
        empty_capabilities["qualification_snapshot"]["entries"][0][
            "capability_ids"
        ] = []
        self.assertNotEqual([], list(validator.iter_errors(empty_capabilities)))

        missing_scope_repository = copy.deepcopy(future)
        missing_scope_repository["qualification_snapshot"]["entries"][0]["scope"].pop(
            "repository"
        )
        self.assertNotEqual([], list(validator.iter_errors(missing_scope_repository)))

        missing_provenance_basis = copy.deepcopy(future)
        missing_provenance_basis["qualification_snapshot"]["entries"][0][
            "provenance"
        ].pop("basis")
        self.assertNotEqual([], list(validator.iter_errors(missing_provenance_basis)))

        missing_provenance_evidence = copy.deepcopy(future)
        missing_provenance_evidence["qualification_snapshot"]["entries"][0][
            "provenance"
        ].pop("evidence")
        self.assertNotEqual(
            [], list(validator.iter_errors(missing_provenance_evidence))
        )

        empty_provenance_evidence = copy.deepcopy(future)
        empty_provenance_evidence["qualification_snapshot"]["entries"][0]["provenance"][
            "evidence"
        ] = []
        self.assertNotEqual([], list(validator.iter_errors(empty_provenance_evidence)))

        missing_independence_axes = copy.deepcopy(future)
        missing_independence_axes["qualification_snapshot"]["entries"][0][
            "provenance"
        ].pop("independence_axes")
        self.assertNotEqual([], list(validator.iter_errors(missing_independence_axes)))

        empty_independence_axes = copy.deepcopy(future)
        empty_independence_axes["qualification_snapshot"]["entries"][0]["provenance"][
            "independence_axes"
        ] = []
        self.assertNotEqual([], list(validator.iter_errors(empty_independence_axes)))

        unknown_scope_field = copy.deepcopy(future)
        unknown_scope_field["qualification_snapshot"]["entries"][0]["scope"][
            "provider_brand"
        ] = "must-not-grant-scope"
        self.assertNotEqual([], list(validator.iter_errors(unknown_scope_field)))

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

    def test_q0_fail_closed_semantics_preserve_owner_scope_status_and_freshness_gates(
        self,
    ) -> None:
        cases: list[
            tuple[
                str,
                Callable[[list[dict[str, Any]], dict[str, Any]], None],
            ]
        ] = [
            (
                "owner-excluded",
                lambda entries, qualification: entries[0].update(
                    owner_relation="owner"
                ),
            ),
            (
                "unknown-owner-relation",
                lambda entries, _qualification: entries[0].update(
                    owner_relation="unknown"
                ),
            ),
            (
                "scope-mismatch",
                lambda entries, qualification: entries[0].update(
                    scope={"repository": "other/repository"}
                ),
            ),
            (
                "revoked",
                lambda entries, qualification: entries[0].update(status="revoked"),
            ),
            (
                "unestablished",
                lambda entries, qualification: entries[0].update(
                    status="unestablished"
                ),
            ),
            ("stale-snapshot", _stale_qualification),
        ]

        for name, mutate in cases:
            input_document, policy_document = _review_case_documents()
            qualification, entries = _qualification_entries(input_document)
            mutate(entries, qualification)
            _refresh_qualification_digest(input_document)

            code, payload = review_check.evaluate_documents(
                input_document, policy_document
            )

            with self.subTest(case=name):
                self.assertEqual(3, code)
                self.assertEqual("INCOMPLETE", payload["outcome"])
                self.assertEqual("QUORUM_UNMET", payload["reason"])

    def test_q0_unknown_owner_relation_never_qualifies(
        self,
    ) -> None:
        input_document, policy_document = _review_case_documents()
        _, entries = _qualification_entries(input_document)
        entries[0]["owner_relation"] = "unknown"
        policy_document["qualification"]["owner_reviews_count"] = True
        input_document["authority"]["policy_digest"] = canonical_digest(policy_document)
        _refresh_qualification_digest(input_document)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("QUORUM_UNMET", payload["reason"])

    def test_q0_duplicate_or_conflicting_qualification_identity_fails_closed(
        self,
    ) -> None:
        for conflicting in (False, True):
            input_document, policy_document = _review_case_documents()
            _, entries = _qualification_entries(input_document)
            duplicate = copy.deepcopy(entries[0])
            if conflicting:
                duplicate["status"] = "revoked"
            entries.append(duplicate)
            _refresh_qualification_digest(input_document)

            code, payload = review_check.evaluate_documents(
                input_document, policy_document
            )

            with self.subTest(conflicting=conflicting):
                self.assertEqual(2, code)
                self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
