from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

from jsonschema.exceptions import SchemaError

from tools import review_check

ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "tests" / "fixtures" / "review_check" / "cases.json").read_text(
            encoding="utf-8"
        )
    )


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


if __name__ == "__main__":
    unittest.main()
