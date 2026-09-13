from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

from tools import cli, review_check
from tools.review_check import MAX_REVIEW_INPUT_BYTES
from tools.review_evaluate import ReviewInputError, evaluate
from tools.review_model import canonical_digest, canonical_json
from tools.review_policy import effective_policy_issues
from tools.task_envelope import render_current_projection, validate_task_envelope

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

    def test_fixture_revision_lineage_cannot_cross_subject_binding(self) -> None:
        input_document, policy_document = _documents()
        observations = input_document["evidence_set"]["observations"]
        current = observations[0]
        current["native"]["object_id"] = "cross-subject-provider-object"
        current["native"]["revision"] = 1
        foreign = copy.deepcopy(current)
        foreign["observation_id"] = "foreign-subject-higher-revision"
        foreign["native"]["revision"] = 2
        foreign["subject_binding"]["head_commit"] = "f" * 40
        observations.append(foreign)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        assessments = {
            assessment["observation_id"]: assessment
            for assessment in payload["assessments"]
        }
        self.assertIs(assessments[current["observation_id"]]["eligible"], True)
        self.assertIs(assessments[foreign["observation_id"]]["eligible"], False)
        self.assertIn(
            "subject_not_exact",
            assessments[foreign["observation_id"]]["exclusion_reasons"],
        )

    def test_fixture_equivalent_subject_bindings_share_revision_lineage(self) -> None:
        input_document, policy_document = _documents()
        observations = input_document["evidence_set"]["observations"]
        older = observations[0]
        older["native"]["object_id"] = "equivalent-subject-provider-object"
        older["native"]["revision"] = 1
        older["native"]["recommendation_state"] = "CHANGES_REQUESTED"
        older["subject_binding"].pop("repository", None)
        older["subject_binding"].pop("change_request", None)

        newer = copy.deepcopy(older)
        newer["observation_id"] = "equivalent-subject-higher-revision"
        newer["native"]["revision"] = 2
        newer["native"]["recommendation_state"] = "APPROVED"
        newer["subject_binding"]["repository"] = input_document["subject"]["repository"]
        newer["subject_binding"]["change_request"] = input_document["subject"][
            "change_request"
        ]
        observations.append(newer)

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(0, code)
        self.assertEqual("PASS", payload["outcome"])
        assessments = {
            assessment["observation_id"]: assessment
            for assessment in payload["assessments"]
        }
        self.assertIs(assessments[older["observation_id"]]["eligible"], False)
        self.assertIn(
            "superseded_revision",
            assessments[older["observation_id"]]["exclusion_reasons"],
        )
        self.assertIs(assessments[newer["observation_id"]]["eligible"], True)

    def test_d11_task_envelope_remains_schema_and_projection_bounded(self) -> None:
        envelope_path = ROOT / "tasks" / "issue-11-r2a-p1.yaml"
        envelope, issues = validate_task_envelope(envelope_path, ROOT)

        self.assertEqual([], issues)
        projection = render_current_projection(
            envelope,
            "git:" + ("0" * 40),
        )
        self.assertLessEqual(
            len(projection),
            envelope["review"]["projection_characters"],
        )

    def test_parser_hostile_json_returns_canonical_public_cli_error(self) -> None:
        _, policy_document = _documents()
        hostile = '{"nested":' * 2_000 + "0" + "}" * 2_000
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "hostile.json"
            policy_path = root / "policy.json"
            input_path.write_text(hostile, encoding="utf-8")
            policy_path.write_text(json.dumps(policy_document), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                code = cli.main(
                    [
                        "review-check",
                        "--input",
                        str(input_path),
                        "--policy",
                        str(policy_path),
                    ]
                )

        self.assertEqual(2, code)
        payload = json.loads(output.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", _error_code(payload))
        self.assertIn("nest", payload["error"]["message"].lower())

    def test_oversized_file_mode_input_fails_before_unbounded_read(self) -> None:
        _, policy_document = _documents()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "oversized.json"
            policy_path = root / "policy.json"
            input_path.write_bytes(b" " * (MAX_REVIEW_INPUT_BYTES + 1))
            policy_path.write_text(json.dumps(policy_document), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                code = cli.main(
                    [
                        "review-check",
                        "--input",
                        str(input_path),
                        "--policy",
                        str(policy_path),
                    ]
                )

        self.assertEqual(2, code)
        payload = json.loads(output.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", _error_code(payload))
        self.assertIn("byte operational bound", payload["error"]["message"])

    def test_input_schema_recursion_fails_closed_as_malformed(self) -> None:
        input_document, policy_document = _documents()
        with mock.patch(
            "tools.review_check._schema_errors",
            side_effect=RecursionError("synthetic schema traversal exhaustion"),
        ):
            code, payload = review_check.evaluate_documents(
                input_document,
                policy_document,
            )

        self.assertEqual(2, code)
        self.assertEqual("MALFORMED_INVOCATION", _error_code(payload))
        self.assertIn("schema validation", payload["error"]["message"])

    def test_duplicate_json_fields_fail_closed_before_schema_evaluation(
        self,
    ) -> None:
        _, policy_document = _documents()
        raw_input = '{"schema_version":"1.0","schema_version":"1.0"}'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "duplicate.json"
            policy_path = root / "policy.json"
            input_path.write_text(raw_input, encoding="utf-8")
            policy_path.write_text(json.dumps(policy_document), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                code = cli.main(
                    [
                        "review-check",
                        "--input",
                        str(input_path),
                        "--policy",
                        str(policy_path),
                    ]
                )

        self.assertEqual(2, code)
        payload = json.loads(output.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", _error_code(payload))
        self.assertIn("repeats JSON object field", payload["error"]["message"])

    def test_overflowing_json_number_fails_closed_before_schema_evaluation(
        self,
    ) -> None:
        _, policy_document = _documents()
        raw_input = '{"schema_version":"1.0","native_value":1e9999}'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "nonfinite.json"
            policy_path = root / "policy.json"
            input_path.write_text(raw_input, encoding="utf-8")
            policy_path.write_text(json.dumps(policy_document), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                code = cli.main(
                    [
                        "review-check",
                        "--input",
                        str(input_path),
                        "--policy",
                        str(policy_path),
                    ]
                )

        self.assertEqual(2, code)
        payload = json.loads(output.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", _error_code(payload))
        self.assertIn("non-finite JSON number", payload["error"]["message"])

    def test_programmatic_non_finite_input_fails_closed(self) -> None:
        input_document, policy_document = _documents()
        input_document["evidence_set"]["observations"][0]["native"][
            "overflow"
        ] = float("inf")

        code, payload = review_check.evaluate_documents(input_document, policy_document)

        self.assertEqual(2, code)
        self.assertEqual("MALFORMED_INVOCATION", _error_code(payload))
        self.assertIn("non-finite number", payload["error"]["message"])

    def test_canonical_json_rejects_non_finite_numbers(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json({"overflow": float("inf")})

    def test_shared_alias_fanout_is_traversed_by_identity(self) -> None:
        class CountingDict(dict[str, Any]):
            visits = 0

            def values(self) -> Any:
                type(self).visits += 1
                return super().values()

        shared: dict[str, Any] = {"leaf": True}
        for _ in range(10):
            shared = CountingDict({"left": shared, "right": shared})

        review_check._assert_document_depth(shared, "review policy")

        self.assertLessEqual(CountingDict.visits, 10)

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
