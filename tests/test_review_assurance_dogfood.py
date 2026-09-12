from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.review_adapter_file import normalize_observation
from tools.review_check import evaluate_documents
from tools.review_model import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "review_check"


def _json(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"expected JSON object in {path}")
    return loaded


def _dogfood_observation(record: dict[str, object]) -> dict[str, object]:
    review_id = str(record["github_review_id"])
    return {
        "observation_id": f"github-review-{review_id}",
        "reviewer_id": record["reviewer_id"],
        "source_id": "retained-review-evidence",
        "observed_at": record["submitted_at"],
        "subject_binding": {
            "status": "exact",
            "head_commit": record["reviewed_head_commit"],
            "comparison": {
                "kind": "merge_base",
                "commit_sha": record["reviewed_merge_base_commit"],
            },
        },
        "native": {
            "object_id": f"github-pull-review-{review_id}",
            "revision": 1,
            "provider": record["provider"],
            "source_url": record["source_url"],
            "review_commit_id": record["reviewed_head_commit"],
            "recommendation_state": record["native_recommendation_state"],
        },
        "findings": [],
        "threads": {"state": "unknown"},
    }


def _dogfood_documents() -> tuple[dict[str, object], dict[str, object]]:
    cases = _json(FIX / "cases.json")
    dogfood = _json(FIX / "dogfood-pr239.json")
    base = cases["base"]
    if not isinstance(base, dict):
        raise AssertionError("cases base must be an object")
    input_document = copy.deepcopy(base["input"])
    policy_document = copy.deepcopy(base["policy"])
    if not isinstance(input_document, dict) or not isinstance(policy_document, dict):
        raise AssertionError("base input and policy must be objects")

    subject_record = dogfood["subject"]
    reviews = dogfood["reviews"]
    if not isinstance(subject_record, dict) or not isinstance(reviews, list):
        raise AssertionError("dogfood subject/reviews shape is invalid")
    review_records = [record for record in reviews if isinstance(record, dict)]
    if len(review_records) != len(reviews):
        raise AssertionError("dogfood reviews must all be objects")

    input_document["subject"] = {
        "repository": subject_record["repository"],
        "change_request": subject_record["change_request"],
        "head_commit": subject_record["final_head_commit"],
        "comparison": {
            "kind": "merge_base",
            "commit_sha": subject_record["merge_base_commit"],
        },
        "observed_at": "2026-09-12T00:00:00Z",
    }
    input_document["evidence_set"] = {
        "observed_at": "2026-09-12T00:00:00Z",
        "sources": [
            {
                "source_id": "retained-review-evidence",
                "status": "COMPLETE",
                "observed_at": "2026-09-12T00:00:00Z",
            }
        ],
        "observations": [_dogfood_observation(record) for record in review_records],
    }
    qualification = input_document["qualification_snapshot"]
    if not isinstance(qualification, dict):
        raise AssertionError("qualification snapshot must be an object")
    qualification.update(
        {
            "snapshot_id": "fixture-dogfood-pr239-no-qualification",
            "revision": "1",
            "qualifying_authority": "fixture-dogfood-authority",
            "observed_at": "2026-09-12T00:00:00Z",
            "entries": [],
        }
    )
    context = input_document["evaluation_context"]
    if not isinstance(context, dict):
        raise AssertionError("evaluation context must be an object")
    context.update(
        {
            "mode": "historical_replay",
            "judge_relation": "prior_integrated",
            "fixture_only": True,
            "as_of": "2026-09-12T00:10:00Z",
        }
    )
    authority = input_document["authority"]
    if not isinstance(authority, dict):
        raise AssertionError("authority must be an object")
    authority["policy_digest"] = canonical_digest(policy_document)
    authority["qualification_snapshot_digest"] = canonical_digest(qualification)
    return input_document, policy_document


class ReviewAssuranceDogfoodTests(unittest.TestCase):
    def test_real_pr239_native_reviews_normalize_without_invented_authority(
        self,
    ) -> None:
        dogfood = _json(FIX / "dogfood-pr239.json")
        reviews = dogfood["reviews"]
        self.assertIsInstance(reviews, list)
        expected = {
            "5182705577": ("qodo-code-review[bot]", "COMMENTED", "COMMENT_ONLY"),
            "5182778419": ("sourcery-ai[bot]", "APPROVED", "APPROVE"),
        }
        self.assertEqual(
            set(expected), {str(item["github_review_id"]) for item in reviews}
        )
        for record in reviews:
            self.assertIsInstance(record, dict)
            assessment, mismatches = normalize_observation(_dogfood_observation(record))
            reviewer, raw, normalized = expected[str(record["github_review_id"])]
            with self.subTest(review_id=record["github_review_id"]):
                self.assertEqual([], mismatches)
                self.assertEqual(reviewer, assessment["reviewer_id"])
                self.assertEqual(raw, assessment["raw_recommendation"])
                self.assertEqual(normalized, assessment["normalized_recommendation"])
                self.assertEqual(
                    record["source_url"], assessment["native"]["source_url"]
                )

    def test_pr239_older_head_reviews_stay_visible_but_do_not_count_for_final_head(
        self,
    ) -> None:
        input_document, policy_document = _dogfood_documents()
        code, payload = evaluate_documents(input_document, policy_document)
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("QUORUM_UNMET", payload["reason"])
        self.assertEqual(2, len(payload["assessments"]))
        self.assertEqual(0, payload["quorum"]["distinct_domains"])
        self.assertEqual([], payload["qualification"]["qualifying_observations"])
        for assessment in payload["assessments"]:
            with self.subTest(observation_id=assessment["observation_id"]):
                self.assertIs(assessment["eligible"], False)
                self.assertIn("subject_not_exact", assessment["exclusion_reasons"])

    def test_pr239_current_advisory_dogfood_is_bootstrap_incomplete(self) -> None:
        input_document, policy_document = _dogfood_documents()
        context = input_document["evaluation_context"]
        self.assertIsInstance(context, dict)
        context.update(
            {
                "mode": "current_advisory",
                "judge_relation": "candidate_under_test",
                "fixture_only": False,
            }
        )
        code, payload = evaluate_documents(input_document, policy_document)
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE", payload["reason"])
        self.assertIs(payload["binding"], False)


if __name__ == "__main__":
    unittest.main()
