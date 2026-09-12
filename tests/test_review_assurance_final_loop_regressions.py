from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from tools import review_check
from tools.review_evaluate import ReviewInputError, evaluate
from tools.review_model import canonical_digest
from tools.review_policy import effective_policy_issues

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "review_check"


def _documents() -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = json.loads((FIX / "cases.json").read_text(encoding="utf-8"))
    base = fixture["base"]
    input_document = copy.deepcopy(base["input"])
    policy_document = copy.deepcopy(base["policy"])
    context = input_document["evaluation_context"]
    context["fixture_only"] = True
    return input_document, policy_document


def _error_code(payload: dict[str, Any]) -> object:
    error = payload.get("error")
    return error.get("code") if isinstance(error, dict) else None


class ReviewAssuranceFinalLoopRegressions(unittest.TestCase):
    def test_duplicate_observation_compares_json_values_not_python_equality(
        self,
    ) -> None:
        input_document, policy_document = _documents()
        observations = input_document["evidence_set"]["observations"]
        duplicate = copy.deepcopy(observations[0])
        duplicate["native"]["revision"] = True
        observations.append(duplicate)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(2, code)
        self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))

    def test_duplicate_source_compares_json_values_not_python_equality(self) -> None:
        input_document, policy_document = _documents()
        sources = input_document["evidence_set"]["sources"]
        sources[0]["limits"] = {"page": 1}
        duplicate = copy.deepcopy(sources[0])
        duplicate["limits"] = {"page": True}
        sources.append(duplicate)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(2, code)
        self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))

    def test_revision_lineage_is_qualified_by_source(self) -> None:
        input_document, policy_document = _documents()
        evidence_set = input_document["evidence_set"]
        observations = evidence_set["observations"]
        observations[0]["native"]["object_id"] = "shared-provider-scoped-id"
        observations[1]["native"]["object_id"] = "shared-provider-scoped-id"
        observations[1]["source_id"] = "optional-review-evidence"
        evidence_set["sources"].append(
            {
                "source_id": "optional-review-evidence",
                "status": "COMPLETE",
                "observed_at": "2026-09-12T00:00:00Z",
            }
        )
        qualification = input_document["qualification_snapshot"]
        qualification["entries"][1]["source_id"] = "optional-review-evidence"
        input_document["authority"]["qualification_snapshot_digest"] = canonical_digest(
            qualification
        )

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        self.assertEqual(2, payload["quorum"]["distinct_domains"])

    def test_stale_subject_precedes_blocker_semantics(self) -> None:
        input_document, policy_document = _documents()
        input_document["subject"]["observed_at"] = "2026-09-11T23:40:00Z"
        input_document["evidence_set"]["observations"][0]["native"][
            "recommendation_state"
        ] = "CHANGES_REQUESTED"

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("SUBJECT_NOT_CURRENT", payload["reason"])
        self.assertEqual([], payload["blockers"])
        self.assertIn("subject freshness requirement is unmet", payload["diagnostics"])

    def test_direct_evaluator_rejects_invalid_result_policy_provenance(self) -> None:
        for field, value in (("id", None), ("version", "")):
            input_document, policy_document = _documents()
            policy_document[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ReviewInputError) as caught:
                    evaluate(input_document, policy_document)
                self.assertEqual("CONFIGURATION_ERROR", caught.exception.code)

    def test_effective_policy_validation_requires_id_and_version(self) -> None:
        _, policy_document = _documents()
        for field in ("id", "version"):
            mutated = copy.deepcopy(policy_document)
            mutated[field] = ""
            with self.subTest(field=field):
                self.assertIn(
                    f"policy {field} is unresolved",
                    effective_policy_issues(mutated),
                )

    def test_judge_status_and_acquisition_vocabularies_are_separate(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "review-check-input.schema.json").read_text(
                encoding="utf-8"
            )
        )
        judge = schema["$defs"]["judge"]["properties"]
        self.assertEqual(
            ["accepted", "revoked", "deprecated", "unknown"],
            judge["status"]["enum"],
        )
        self.assertEqual(
            ["oci", "native", "unavailable", "partial"],
            judge["acquisition"]["enum"],
        )

    def test_result_policy_provenance_has_closed_scalar_constraints(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "review-gate-result.schema.json").read_text(
                encoding="utf-8"
            )
        )
        policy = schema["properties"]["policy"]["properties"]
        self.assertEqual({"type": "string", "minLength": 1}, policy["id"])
        self.assertEqual({"type": "string", "minLength": 1}, policy["version"])
        self.assertEqual(
            ["none", "required"],
            policy["review_requirement"]["enum"],
        )


if __name__ == "__main__":
    unittest.main()
