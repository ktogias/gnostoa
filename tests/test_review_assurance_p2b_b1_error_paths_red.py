from __future__ import annotations

import copy
import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from jsonschema.exceptions import SchemaError

from tools import review_live
from tools.knowledge_common import KnowledgeFormatError
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bundle() -> dict[str, object]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise AssertionError("integrated P2b-A authority bundle must be a JSON object")
    return bundle


def _live_input() -> dict[str, object]:
    bundle = _bundle()
    now = _now()
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "pull_request", "id": "p2b-b1-error-red"},
            "head_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # pragma: allowlist secret -- synthetic public test commit
            "comparison": {
                "kind": "merge_base",
                "commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",  # pragma: allowlist secret -- synthetic public test merge base
            },
            "observed_at": now,
        },
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": now,
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "authority": copy.deepcopy(bundle["authority"]),
        "acquired_judge": copy.deepcopy(bundle["acquired_judge"]),
        "evidence_set": {
            "observed_at": now,
            "sources": [
                {
                    "source_id": "retained-review-evidence",
                    "status": "COMPLETE",
                    "observed_at": now,
                }
            ],
            "observations": [],
        },
        "qualification_snapshot": copy.deepcopy(bundle["qualification_snapshot"]),
    }


def _protected_document() -> ProtectedMainDocument:
    return ProtectedMainDocument(
        protected_main_revision="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",  # pragma: allowlist secret -- synthetic protected-main revision
        document=copy.deepcopy(_bundle()),
    )


def _valid_incomplete_result(
    input_document: dict[str, object], trusted_cut: str
) -> dict[str, object]:
    bundle = _bundle()
    code, payload = review_live._semantic_incomplete(
        input_document,
        bundle,
        trusted_cut,
        "QUORUM_UNMET",
        "synthetic valid incomplete result",
    )
    if code != 3:
        raise AssertionError("synthetic incomplete result must use semantic exit 3")
    return payload


class ReviewAssuranceP2bB1ErrorPathRedTests(unittest.TestCase):
    def test_installed_knowledge_format_error_is_tool_error(self) -> None:
        with (
            mock.patch.object(
                review_live,
                "_schema_errors",
                side_effect=KnowledgeFormatError(
                    "synthetic installed knowledge failure"
                ),
            ),
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
            ) as acquire,
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory({})

        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn(
            "protected current-advisory authority is invalid",
            payload["error"]["message"],
        )
        acquire.assert_not_called()

    def test_delegated_result_validation_failure_is_controlled_tool_error(self) -> None:
        input_document = _live_input()
        protected = _protected_document()
        subject = input_document["subject"]
        assert isinstance(subject, dict)
        trusted_cut = subject["observed_at"]
        assert isinstance(trusted_cut, str)
        original_schema_errors = review_live._schema_errors

        def schema_errors(document: object, schema_name: str) -> list[str]:
            if schema_name == "review-gate-result.schema.json":
                raise SchemaError("synthetic delegated result validation failure")
            return original_schema_errors(document, schema_name)

        with (
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
                return_value=protected,
            ),
            mock.patch.object(review_live, "_trusted_cut", return_value=trusted_cut),
            mock.patch.object(
                review_live,
                "run_prior_integrated_judge",
                return_value=(3, {}),
            ),
            mock.patch.object(review_live, "_schema_errors", side_effect=schema_errors),
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn(
            "protected current-advisory runtime validation failed",
            payload["error"]["message"],
        )

    def test_incomplete_projection_validation_failure_is_controlled_tool_error(
        self,
    ) -> None:
        input_document = _live_input()
        protected = _protected_document()
        subject = input_document["subject"]
        assert isinstance(subject, dict)
        trusted_cut = subject["observed_at"]
        assert isinstance(trusted_cut, str)
        original_schema_errors = review_live._schema_errors

        def schema_errors(document: object, schema_name: str) -> list[str]:
            if schema_name == "review-gate-result.schema.json":
                raise SchemaError("synthetic incomplete projection validation failure")
            return original_schema_errors(document, schema_name)

        with (
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
                return_value=protected,
            ),
            mock.patch.object(review_live, "_trusted_cut", return_value=trusted_cut),
            mock.patch.object(
                review_live,
                "_execute_semantic_review",
                side_effect=review_live.ProtectedRuntimeError(
                    "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
                    "synthetic protected runtime failure",
                ),
            ),
            mock.patch.object(review_live, "_schema_errors", side_effect=schema_errors),
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn(
            "protected current-advisory runtime validation failed",
            payload["error"]["message"],
        )

    def test_final_projection_validation_failure_is_controlled_tool_error(self) -> None:
        input_document = _live_input()
        protected = _protected_document()
        subject = input_document["subject"]
        assert isinstance(subject, dict)
        trusted_cut = subject["observed_at"]
        assert isinstance(trusted_cut, str)
        result = _valid_incomplete_result(input_document, trusted_cut)
        original_schema_errors = review_live._schema_errors

        def schema_errors(document: object, schema_name: str) -> list[str]:
            if schema_name == "review-gate-result.schema.json":
                raise SchemaError("synthetic final projection validation failure")
            return original_schema_errors(document, schema_name)

        with (
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
                return_value=protected,
            ),
            mock.patch.object(review_live, "_trusted_cut", return_value=trusted_cut),
            mock.patch.object(
                review_live,
                "_execute_semantic_review",
                return_value=(3, result),
            ),
            mock.patch.object(review_live, "_schema_errors", side_effect=schema_errors),
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn(
            "protected current-advisory runtime validation failed",
            payload["error"]["message"],
        )


if __name__ == "__main__":
    unittest.main()
