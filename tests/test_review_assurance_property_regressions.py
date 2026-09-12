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
