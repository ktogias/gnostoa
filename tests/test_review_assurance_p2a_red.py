from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools import review_check
from tools.review_model import ERROR_EXIT_CODE, canonical_digest

ROOT = Path(__file__).resolve().parents[1]


def _current_advisory_fixture() -> tuple[dict[str, object], dict[str, object]]:
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "review_check" / "cases.json").read_text(
            encoding="utf-8"
        )
    )
    base = fixture["base"]
    input_document = copy.deepcopy(base["input"])
    policy_document = copy.deepcopy(base["policy"])
    context = input_document["evaluation_context"]
    context.update(
        {
            "mode": "current_advisory",
            "fixture_only": False,
            "judge_relation": "prior_integrated",
        }
    )
    for observation in input_document["evidence_set"]["observations"]:
        binding = observation["subject_binding"]
        binding["repository"] = input_document["subject"]["repository"]
        binding["change_request"] = copy.deepcopy(
            input_document["subject"]["change_request"]
        )
    return input_document, policy_document


def _protected_assurance(
    input_document: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    protected_authority = copy.deepcopy(input_document["authority"])
    protected_judge = copy.deepcopy(input_document["acquired_judge"])
    protected_qualification = copy.deepcopy(input_document["qualification_snapshot"])
    protected_qualification["qualifying_authority"] = "protected-authority"
    for entry in protected_qualification["entries"]:
        entry["provenance"]["basis"] = "protected-observation"
    protected_authority["qualification_snapshot_digest"] = canonical_digest(
        protected_qualification
    )
    return protected_authority, protected_judge, protected_qualification


class ReviewAssuranceP2aRedTests(unittest.TestCase):
    def test_protected_internal_route_replaces_caller_assurance_and_only_it_can_activate(
        self,
    ) -> None:
        input_document, protected_policy = _current_advisory_fixture()
        protected_authority, protected_judge, protected_qualification = (
            _protected_assurance(input_document)
        )

        # Caller-controlled assurance claims deliberately conflict with the protected set.
        caller_input = copy.deepcopy(input_document)
        caller_input["authority"]["policy_digest"] = "sha256:" + "0" * 64
        caller_input["acquired_judge"]["status"] = "revoked"
        caller_input["qualification_snapshot"]["qualifying_authority"] = (
            "caller-controlled"
        )

        direct_code, direct_payload = review_check.evaluate_documents(
            caller_input,
            protected_policy,
        )
        self.assertEqual(3, direct_code)
        self.assertEqual("INCOMPLETE", direct_payload["outcome"])
        self.assertEqual(
            "BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE",
            direct_payload["reason"],
        )

        self.assertTrue(
            hasattr(review_check, "_evaluate_protected_current_advisory_documents"),
            "P2a requires a non-CLI internal route for protected prior-integrated inputs",
        )
        protected_evaluate = review_check._evaluate_protected_current_advisory_documents
        code, payload = protected_evaluate(
            caller_input,
            protected_policy,
            protected_authority=protected_authority,
            protected_judge=protected_judge,
            protected_qualification=protected_qualification,
        )

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        self.assertEqual("REQUIREMENTS_SATISFIED", payload["reason"])
        self.assertEqual(protected_authority, payload["authority"])
        self.assertEqual(protected_judge, payload["judge"])
        self.assertTrue(payload["qualification"]["snapshot_current"])
        self.assertEqual(
            ["obs-a", "obs-b"], payload["qualification"]["qualifying_observations"]
        )

        # The protected route must not mutate caller-owned input or turn the ordinary
        # public/direct evaluator into an activation path.
        self.assertEqual("revoked", caller_input["acquired_judge"]["status"])
        after_code, after_payload = review_check.evaluate_documents(
            input_document,
            protected_policy,
        )
        self.assertEqual(3, after_code)
        self.assertEqual(
            "BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE",
            after_payload["reason"],
        )

    def test_protected_internal_route_rejects_non_activation_contexts(self) -> None:
        input_document, protected_policy = _current_advisory_fixture()
        protected_authority, protected_judge, protected_qualification = (
            _protected_assurance(input_document)
        )
        cases = (
            ("mode", "historical_replay"),
            ("judge_relation", "candidate_under_test"),
            ("fixture_only", True),
        )
        for field, value in cases:
            with self.subTest(field=field):
                candidate = copy.deepcopy(input_document)
                candidate["evaluation_context"][field] = value
                code, payload = (
                    review_check._evaluate_protected_current_advisory_documents(
                        candidate,
                        protected_policy,
                        protected_authority=protected_authority,
                        protected_judge=protected_judge,
                        protected_qualification=protected_qualification,
                    )
                )
                self.assertEqual(ERROR_EXIT_CODE, code)
                self.assertEqual("CONFIGURATION_ERROR", payload["error"]["code"])


if __name__ == "__main__":
    unittest.main()
