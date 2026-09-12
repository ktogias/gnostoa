from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tools import review_check
from tools.review_model import canonical_digest, canonical_json

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "review_check" / "cases.json"


def _documents() -> tuple[dict[str, object], dict[str, object]]:
    fixture = json.loads(CASES.read_text(encoding="utf-8"))
    base = fixture["base"]
    if not isinstance(base, dict):
        raise AssertionError("review-assurance fixture base must be an object")
    input_document = copy.deepcopy(base["input"])
    policy_document = copy.deepcopy(base["policy"])
    if not isinstance(input_document, dict) or not isinstance(policy_document, dict):
        raise AssertionError("review-assurance base documents must be objects")
    context = input_document.get("evaluation_context")
    if isinstance(context, dict) and context.get("mode") == "historical_replay":
        context.setdefault("fixture_only", True)
    return input_document, policy_document


def _error_code(payload: dict[str, object]) -> object:
    error = payload.get("error")
    return error.get("code") if isinstance(error, dict) else None


class ReviewAssurancePropertyRegressionTests(unittest.TestCase):
    def test_r01_policy_resolution_and_zero_evidence_variants_cannot_pass(self) -> None:
        input_document, policy_document = _documents()
        abstract_policy = copy.deepcopy(policy_document)
        abstract_policy["abstract"] = True
        abstract_input = copy.deepcopy(input_document)
        abstract_evidence = abstract_input["evidence_set"]
        self.assertIsInstance(abstract_evidence, dict)
        abstract_evidence["observations"] = []
        abstract_qualification = abstract_input["qualification_snapshot"]
        self.assertIsInstance(abstract_qualification, dict)
        abstract_qualification["entries"] = []
        abstract_authority = abstract_input["authority"]
        self.assertIsInstance(abstract_authority, dict)
        abstract_authority["policy_digest"] = canonical_digest(abstract_policy)
        abstract_authority["qualification_snapshot_digest"] = canonical_digest(
            abstract_qualification
        )

        code, payload = review_check.evaluate_documents(abstract_input, abstract_policy)
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("POLICY_UNRESOLVED", payload["reason"])

        unresolved_policy = copy.deepcopy(policy_document)
        unresolved_policy.pop("review_requirement", None)
        unresolved_input = copy.deepcopy(input_document)
        unresolved_authority = unresolved_input["authority"]
        self.assertIsInstance(unresolved_authority, dict)
        unresolved_authority["policy_digest"] = canonical_digest(unresolved_policy)
        code, payload = review_check.evaluate_documents(
            unresolved_input, unresolved_policy
        )
        self.assertEqual(2, code)
        self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))

        zero_input = copy.deepcopy(input_document)
        zero_evidence = zero_input["evidence_set"]
        self.assertIsInstance(zero_evidence, dict)
        zero_evidence["observations"] = []
        code, payload = review_check.evaluate_documents(zero_input, policy_document)
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("QUORUM_UNMET", payload["reason"])

    def test_r14_optional_unavailable_source_remains_visible_without_blocking(
        self,
    ) -> None:
        input_document, policy_document = _documents()
        evidence_set = input_document["evidence_set"]
        self.assertIsInstance(evidence_set, dict)
        sources = evidence_set["sources"]
        self.assertIsInstance(sources, list)
        sources.append(
            {
                "source_id": "optional-review-evidence",
                "status": "UNAVAILABLE",
                "observed_at": "2026-09-12T00:00:00Z",
            }
        )

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        collection = payload["collection"]
        self.assertIsInstance(collection, dict)
        observed_sources = collection["sources"]
        self.assertIsInstance(observed_sources, list)
        by_id = {
            item["source_id"]: item
            for item in observed_sources
            if isinstance(item, dict) and isinstance(item.get("source_id"), str)
        }
        self.assertEqual("UNAVAILABLE", by_id["optional-review-evidence"]["status"])

    def test_r26_unrecognized_observation_has_no_quorum_blocker_or_conflict_authority(
        self,
    ) -> None:
        for mode in ("quorum", "blocker", "conflict"):
            input_document, policy_document = _documents()
            evidence_set = input_document["evidence_set"]
            self.assertIsInstance(evidence_set, dict)
            observations = evidence_set["observations"]
            self.assertIsInstance(observations, list)
            unsupported = observations[1]
            self.assertIsInstance(unsupported, dict)
            unsupported["source_id"] = "unsupported-review-source"
            native = unsupported["native"]
            self.assertIsInstance(native, dict)
            if mode in {"blocker", "conflict"}:
                native["recommendation_state"] = "CHANGES_REQUESTED"
            if mode == "conflict":
                blockers = policy_document["blockers"]
                self.assertIsInstance(blockers, dict)
                blockers["recommendations"] = []
                authority = input_document["authority"]
                self.assertIsInstance(authority, dict)
                authority["policy_digest"] = canonical_digest(policy_document)

            code, payload = review_check.evaluate_documents(
                input_document, policy_document
            )

            with self.subTest(mode=mode):
                self.assertEqual(3, code)
                self.assertEqual("INCOMPLETE", payload["outcome"])
                self.assertEqual("QUORUM_UNMET", payload["reason"])
                self.assertEqual([], payload["blockers"])
                self.assertEqual([], payload["conflicts"])
                quorum = payload["quorum"]
                self.assertIsInstance(quorum, dict)
                self.assertEqual(1, quorum["distinct_domains"])
                assessment = next(
                    item
                    for item in payload["assessments"]
                    if item.get("observation_id") == "obs-b"
                )
                self.assertIs(assessment["eligible"], False)
                self.assertIn("source_not_recognized", assessment["exclusion_reasons"])

    def test_r31_observation_permutations_and_duplicate_placement_are_invariant(
        self,
    ) -> None:
        input_document, policy_document = _documents()
        baseline_code, baseline = review_check.evaluate_documents(
            copy.deepcopy(input_document), copy.deepcopy(policy_document)
        )
        self.assertEqual(0, baseline_code)

        evidence_set = input_document["evidence_set"]
        self.assertIsInstance(evidence_set, dict)
        observations = evidence_set["observations"]
        self.assertIsInstance(observations, list)
        first = copy.deepcopy(observations[0])
        second = copy.deepcopy(observations[1])
        variants = {
            "reversed": [second, first],
            "duplicate-first-front": [first, first, second],
            "duplicate-second-tail": [first, second, second],
            "duplicate-first-tail": [first, second, first],
            "reversed-with-duplicate": [second, first, first],
        }

        for name, variant in variants.items():
            candidate = copy.deepcopy(input_document)
            candidate_evidence = candidate["evidence_set"]
            self.assertIsInstance(candidate_evidence, dict)
            candidate_evidence["observations"] = copy.deepcopy(variant)

            code, payload = review_check.evaluate_documents(
                candidate, copy.deepcopy(policy_document)
            )

            with self.subTest(name=name):
                self.assertEqual(baseline_code, code)
                self.assertEqual(canonical_json(baseline), canonical_json(payload))

    def test_r32_assessment_preserves_distinct_review_evidence_fields(self) -> None:
        input_document, policy_document = _documents()

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(0, code)
        assessments = {
            item["observation_id"]: item
            for item in payload["assessments"]
            if isinstance(item, dict) and isinstance(item.get("observation_id"), str)
        }
        self.assertEqual({"obs-a", "obs-b"}, set(assessments))
        for observation_id, reviewer_id in (
            ("obs-a", "reviewer-a"),
            ("obs-b", "reviewer-b"),
        ):
            assessment = assessments[observation_id]
            self.assertEqual(reviewer_id, assessment["reviewer_id"])
            self.assertEqual("APPROVED", assessment["raw_recommendation"])
            self.assertEqual("APPROVE", assessment["normalized_recommendation"])
            self.assertEqual([], assessment["findings"])
            provenance = assessment["normalization_provenance"]
            self.assertIsInstance(provenance, dict)
            self.assertEqual("gnostoa.file-review", provenance["adapter_id"])
            self.assertEqual("1.0", provenance["adapter_version"])
            self.assertIn("raw_state_digest", provenance)

    def test_r42_result_fidelity_and_canonicalization_are_explicit(self) -> None:
        input_document, policy_document = _documents()

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        self.assertEqual("REQUIREMENTS_SATISFIED", payload["reason"])
        self.assertIs(payload["binding"], False)
        self.assertEqual(input_document["subject"], payload["subject"])
        self.assertEqual(input_document["authority"], payload["authority"])
        self.assertEqual(input_document["acquired_judge"], payload["judge"])
        encoded = canonical_json(payload)
        self.assertEqual(encoded, canonical_json(json.loads(encoded)))

    def test_r43_file_mode_cli_uses_the_public_path_without_network_effects(
        self,
    ) -> None:
        input_document, policy_document = _documents()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            policy_path = root / "policy.json"
            input_path.write_text(
                json.dumps(input_document, sort_keys=True), encoding="utf-8"
            )
            policy_path.write_text(
                json.dumps(policy_document, sort_keys=True), encoding="utf-8"
            )
            output = io.StringIO()

            with (
                mock.patch(
                    "socket.socket",
                    side_effect=AssertionError("network access is forbidden"),
                ),
                redirect_stdout(output),
            ):
                code = review_check.main(
                    ["--input", str(input_path), "--policy", str(policy_path)]
                )

        self.assertEqual(0, code)
        payload = json.loads(output.getvalue())
        self.assertEqual("PASS", payload["outcome"])
        self.assertEqual("REQUIREMENTS_SATISFIED", payload["reason"])
        self.assertIs(payload["binding"], False)

    def test_r44_error_envelope_is_closed_and_typed(self) -> None:
        input_document, policy_document = _documents()
        evidence_set = input_document["evidence_set"]
        self.assertIsInstance(evidence_set, dict)
        sources = evidence_set["sources"]
        self.assertIsInstance(sources, list)
        conflict = copy.deepcopy(sources[0])
        self.assertIsInstance(conflict, dict)
        conflict["status"] = "ERROR"
        sources.append(conflict)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(2, code)
        self.assertEqual({"error"}, set(payload))
        error = payload["error"]
        self.assertIsInstance(error, dict)
        self.assertEqual({"code", "message", "details"}, set(error))
        self.assertEqual("CONFIGURATION_ERROR", error["code"])
        self.assertIsInstance(error["message"], str)
        self.assertTrue(error["message"])
        self.assertIsInstance(error["details"], dict)

    def test_r45_each_forged_normalization_claim_fails_closed_independently(
        self,
    ) -> None:
        variants: dict[str, dict[str, object]] = {
            "admitted": {"admitted": False},
            "normalized_recommendation": {
                "normalized_recommendation": "REQUEST_CHANGES"
            },
            "adapter_id": {"adapter_id": "forged.adapter"},
            "adapter_version": {"adapter_version": "9.9"},
            "rule_id": {"rule_id": "forged.rule"},
            "raw_state_digest": {
                "normalization_provenance": {"raw_state_digest": "sha256:" + "0" * 64}
            },
        }

        for name, claims in variants.items():
            input_document, policy_document = _documents()
            evidence_set = input_document["evidence_set"]
            self.assertIsInstance(evidence_set, dict)
            observations = evidence_set["observations"]
            self.assertIsInstance(observations, list)
            observation = observations[0]
            self.assertIsInstance(observation, dict)
            observation["claims"] = claims

            code, payload = review_check.evaluate_documents(
                input_document, policy_document
            )

            with self.subTest(field=name):
                self.assertEqual(2, code)
                self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))
                error = payload.get("error")
                self.assertIsInstance(error, dict)
                details = error.get("details")
                self.assertIsInstance(details, dict)
                mismatches = details.get("mismatches")
                self.assertIsInstance(mismatches, list)
                self.assertTrue(mismatches)

    def test_conflicting_duplicate_qualification_identity_is_order_independent_error(
        self,
    ) -> None:
        for reverse in (False, True):
            input_document, policy_document = _documents()
            qualification = input_document["qualification_snapshot"]
            self.assertIsInstance(qualification, dict)
            entries = qualification["entries"]
            self.assertIsInstance(entries, list)
            original = copy.deepcopy(entries[0])
            conflict = copy.deepcopy(original)
            conflict["status"] = "revoked"
            other = copy.deepcopy(entries[1])
            entries[:] = (
                [conflict, original, other] if reverse else [original, conflict, other]
            )
            authority = input_document["authority"]
            self.assertIsInstance(authority, dict)
            authority["qualification_snapshot_digest"] = canonical_digest(qualification)

            code, payload = review_check.evaluate_documents(
                input_document, policy_document
            )

            with self.subTest(reverse=reverse):
                self.assertEqual(2, code)
                self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))

    def test_exact_duplicate_qualification_identity_is_rejected(self) -> None:
        input_document, policy_document = _documents()
        qualification = input_document["qualification_snapshot"]
        self.assertIsInstance(qualification, dict)
        entries = qualification["entries"]
        self.assertIsInstance(entries, list)
        entries.append(copy.deepcopy(entries[0]))
        authority = input_document["authority"]
        self.assertIsInstance(authority, dict)
        authority["qualification_snapshot_digest"] = canonical_digest(qualification)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(2, code)
        self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))


if __name__ == "__main__":
    unittest.main()
