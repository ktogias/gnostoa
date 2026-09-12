from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from jsonschema.exceptions import SchemaError

from tools import review_check
from tools.review_model import canonical_digest
from tools.review_policy import default_project_policy_path, resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "review_check" / "cases.json").read_text(
            encoding="utf-8"
        )
    )
    base = fixture.get("base")
    if isinstance(base, dict):
        input_document = base.get("input")
        if isinstance(input_document, dict):
            context = input_document.get("evaluation_context")
            if isinstance(context, dict) and context.get("mode") == "historical_replay":
                context.setdefault("fixture_only", True)
    return fixture


def _error_code(payload: dict[str, object]) -> object:
    error = payload.get("error")
    return error.get("code") if isinstance(error, dict) else None


class ReviewAssuranceIntegrationTests(unittest.TestCase):
    def test_candidate_binding_extends_historical_sb2_boundary(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text(
            encoding="utf-8"
        )
        binding = workflow.split("- name: Bind the exact PR executable candidate", 1)[1]
        historical = 'test "$(wc -l < "${sb2_paths_file}")" -eq 14'
        final = 'test "$(wc -l < "${sb2_paths_file}")" -eq 19'
        review_paths = (
            "tools/review_adapter_file.py",
            "tools/review_check.py",
            "tools/review_evaluate.py",
            "tools/review_model.py",
            "tools/review_policy.py",
        )
        self.assertIn(historical, binding)
        self.assertIn(final, binding)
        self.assertLess(binding.index(historical), binding.index(review_paths[0]))
        self.assertLess(binding.index(review_paths[-1]), binding.index(final))
        for path in review_paths:
            with self.subTest(path=path):
                self.assertEqual(1, binding.count(path))
        self.assertIn("sb2.membership=19", binding)

    def test_fast_suite_runs_the_pre_registered_review_assurance_oracle(self) -> None:
        verify = (ROOT / "ci" / "verify").read_text(encoding="utf-8")
        fast = verify.split("  fast)", 1)[1].split("    ;;", 1)[0]
        self.assertIn("python -m unittest discover -s tests -v", fast)
        self.assertIn("python tests/test_review_assurance.py", fast)

    def test_malformed_evaluator_result_fails_closed(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = base["input"]
        policy_document = base["policy"]
        with mock.patch.object(
            review_check,
            "evaluate",
            return_value={"outcome": "PASS"},
        ):
            code, payload = review_check.evaluate_documents(
                input_document,
                policy_document,
            )
        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn("public result schema", payload["error"]["message"])

    def test_invalid_installed_schema_uses_canonical_configuration_error(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        with mock.patch.object(
            review_check,
            "_schema",
            side_effect=SchemaError("invalid installed schema"),
        ):
            code, payload = review_check.evaluate_documents(
                base["input"],
                base["policy"],
            )
        self.assertEqual(2, code)
        self.assertEqual("CONFIGURATION_ERROR", payload["error"]["code"])
        self.assertIn("installed review-assurance schema", payload["error"]["message"])

    def test_current_advisory_bootstrap_rejects_self_authorizing_inputs(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = copy.deepcopy(base["input"])
        self.assertIsInstance(input_document, dict)
        context = input_document["evaluation_context"]
        self.assertIsInstance(context, dict)
        context.update(
            {
                "mode": "current_advisory",
                "fixture_only": False,
                "judge_relation": "prior_integrated",
            }
        )

        policy_issue = review_check._current_advisory_bootstrap_issue(
            input_document,
            Path("candidate-weakened-policy.yaml"),
        )
        self.assertIsNotNone(policy_issue)
        self.assertIn("caller-selected --policy", str(policy_issue))

        authority_issue = review_check._current_advisory_bootstrap_issue(
            input_document,
            None,
        )
        self.assertIsNotNone(authority_issue)
        self.assertIn("prior-integrated authority acquisition", str(authority_issue))

        context["judge_relation"] = "candidate_under_test"
        self.assertIsNone(
            review_check._current_advisory_bootstrap_issue(input_document, None)
        )

    def test_shared_evaluator_cannot_self_authorize_current_advisory_pass(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = copy.deepcopy(base["input"])
        self.assertIsInstance(input_document, dict)
        context = input_document["evaluation_context"]
        self.assertIsInstance(context, dict)
        context.update(
            {
                "mode": "current_advisory",
                "fixture_only": False,
                "judge_relation": "prior_integrated",
            }
        )
        code, payload = review_check.evaluate_documents(
            input_document,
            base["policy"],
        )
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE", payload["reason"])
        self.assertIs(payload["binding"], False)

    def test_exact_duplicate_observation_is_idempotent(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = copy.deepcopy(base["input"])
        policy_document = copy.deepcopy(base["policy"])
        baseline_code, baseline = review_check.evaluate_documents(
            copy.deepcopy(input_document),
            copy.deepcopy(policy_document),
        )
        evidence_set = input_document["evidence_set"]
        self.assertIsInstance(evidence_set, dict)
        observations = evidence_set["observations"]
        self.assertIsInstance(observations, list)
        observations.append(copy.deepcopy(observations[0]))

        duplicate_code, duplicate = review_check.evaluate_documents(
            input_document,
            policy_document,
        )

        self.assertEqual(0, baseline_code)
        self.assertEqual(baseline_code, duplicate_code)
        self.assertEqual(baseline, duplicate)

    def test_conflicting_duplicate_observation_is_order_independent_error(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        for reverse in (False, True):
            input_document = copy.deepcopy(base["input"])
            policy_document = copy.deepcopy(base["policy"])
            evidence_set = input_document["evidence_set"]
            self.assertIsInstance(evidence_set, dict)
            observations = evidence_set["observations"]
            self.assertIsInstance(observations, list)
            original = copy.deepcopy(observations[0])
            conflict = copy.deepcopy(original)
            native = conflict["native"]
            self.assertIsInstance(native, dict)
            native["recommendation_state"] = "CHANGES_REQUESTED"
            other = copy.deepcopy(observations[1])
            observations[:] = (
                [conflict, original, other] if reverse else [original, conflict, other]
            )

            code, payload = review_check.evaluate_documents(
                input_document,
                policy_document,
            )

            with self.subTest(reverse=reverse):
                self.assertEqual(2, code)
                self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))

    def test_conflicting_duplicate_source_is_order_independent_error(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        for reverse in (False, True):
            input_document = copy.deepcopy(base["input"])
            policy_document = copy.deepcopy(base["policy"])
            evidence_set = input_document["evidence_set"]
            self.assertIsInstance(evidence_set, dict)
            sources = evidence_set["sources"]
            self.assertIsInstance(sources, list)
            original = copy.deepcopy(sources[0])
            conflict = copy.deepcopy(original)
            conflict["status"] = "ERROR"
            sources[:] = [conflict, original] if reverse else [original, conflict]

            code, payload = review_check.evaluate_documents(
                input_document,
                policy_document,
            )

            with self.subTest(reverse=reverse):
                self.assertEqual(2, code)
                self.assertEqual("CONFIGURATION_ERROR", _error_code(payload))

    def test_policy_exemption_precedes_blocker_and_conflict_semantics(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = copy.deepcopy(base["input"])
        policy_document = copy.deepcopy(base["policy"])
        policy_document["review_requirement"] = "none"
        evidence_set = input_document["evidence_set"]
        self.assertIsInstance(evidence_set, dict)
        observations = evidence_set["observations"]
        self.assertIsInstance(observations, list)
        native = observations[0]["native"]
        self.assertIsInstance(native, dict)
        native["recommendation_state"] = "CHANGES_REQUESTED"
        authority = input_document["authority"]
        self.assertIsInstance(authority, dict)
        authority["policy_digest"] = canonical_digest(policy_document)

        code, payload = review_check.evaluate_documents(
            input_document,
            policy_document,
        )

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        self.assertEqual("POLICY_EXEMPT", payload["reason"])
        self.assertEqual([], payload["blockers"])
        self.assertEqual([], payload["conflicts"])

    def test_mechanical_specialization_replaces_requirement_lists(self) -> None:
        policy = resolve_project_policy(default_project_policy_path(), "mechanical")

        self.assertEqual("none", policy["review_requirement"])
        collection = policy["collection"]
        qualification = policy["qualification"]
        quorum = policy["quorum"]
        self.assertIsInstance(collection, dict)
        self.assertIsInstance(qualification, dict)
        self.assertIsInstance(quorum, dict)
        self.assertEqual([], collection["required_sources"])
        self.assertEqual([], qualification["required_capabilities"])
        self.assertEqual(0, quorum["minimum_distinct_domains"])

    def test_current_advisory_reason_precedes_caller_judge_mismatch(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = copy.deepcopy(base["input"])
        policy_document = copy.deepcopy(base["policy"])
        context = input_document["evaluation_context"]
        self.assertIsInstance(context, dict)
        context.update(
            {
                "mode": "current_advisory",
                "judge_relation": "candidate_under_test",
                "fixture_only": False,
            }
        )
        acquired = input_document["acquired_judge"]
        self.assertIsInstance(acquired, dict)
        acquired["source_revision"] = "f" * 40

        code, payload = review_check.evaluate_documents(
            input_document,
            policy_document,
        )

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual(
            "BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE",
            payload["reason"],
        )

    def test_unproven_real_revision_lineage_cannot_gain_authority(self) -> None:
        fixture = _fixture()
        base = fixture["base"]
        self.assertIsInstance(base, dict)
        input_document = copy.deepcopy(base["input"])
        policy_document = copy.deepcopy(base["policy"])
        context = input_document["evaluation_context"]
        self.assertIsInstance(context, dict)
        context["fixture_only"] = False

        qualification = input_document["qualification_snapshot"]
        self.assertIsInstance(qualification, dict)
        qualification["qualifying_authority"] = "external-test-authority"
        entries = qualification["entries"]
        self.assertIsInstance(entries, list)
        for entry in entries:
            self.assertIsInstance(entry, dict)
            entry["provenance"] = {"basis": "external-established"}
        authority = input_document["authority"]
        self.assertIsInstance(authority, dict)
        authority["qualification_snapshot_digest"] = canonical_digest(qualification)

        evidence_set = input_document["evidence_set"]
        self.assertIsInstance(evidence_set, dict)
        observations = evidence_set["observations"]
        self.assertIsInstance(observations, list)
        newer = copy.deepcopy(observations[0])
        newer["observation_id"] = "obs-a-newer-unproven"
        native = newer["native"]
        self.assertIsInstance(native, dict)
        native["revision"] = 2
        observations.append(newer)

        code, payload = review_check.evaluate_documents(
            input_document,
            policy_document,
        )

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("QUORUM_UNMET", payload["reason"])
        excluded: dict[str, set[str]] = {}
        for item in payload["assessments"]:
            observation_id = item.get("observation_id")
            if observation_id not in {"obs-a", "obs-a-newer-unproven"}:
                continue
            reasons = item.get("exclusion_reasons", [])
            self.assertIsInstance(observation_id, str)
            self.assertIsInstance(reasons, list)
            excluded[observation_id] = {str(reason) for reason in reasons}
        self.assertEqual(
            {
                "obs-a": {"revision_lineage_unproven"},
                "obs-a-newer-unproven": {"revision_lineage_unproven"},
            },
            excluded,
        )


if __name__ == "__main__":
    unittest.main()
