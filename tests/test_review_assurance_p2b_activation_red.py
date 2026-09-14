from __future__ import annotations

import contextlib
import copy
import io
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from tools import review_check

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"


def _timestamp_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _protected_looking_input() -> tuple[dict[str, object], dict[str, object]]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise AssertionError("integrated P2b-A authority bundle must be a JSON object")
    now = _timestamp_now()
    input_document: dict[str, object] = {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "pull_request", "id": "p2b-b-red"},
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
    policy = copy.deepcopy(bundle["policy"])
    if not isinstance(policy, dict):
        raise AssertionError("integrated P2b-A policy must be a JSON object")
    return input_document, policy


class ReviewAssuranceP2bActivationRedTests(unittest.TestCase):
    def test_raw_evaluator_remains_bootstrap_incomplete(self) -> None:
        input_document, policy = _protected_looking_input()
        code, payload = review_check.evaluate_documents(input_document, policy)
        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual(
            "BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE",
            payload["reason"],
        )
        self.assertFalse(payload["binding"])

    def test_live_cli_routes_prior_integrated_current_advisory_to_protected_consumer(
        self,
    ) -> None:
        input_document, _ = _protected_looking_input()
        protected_result = {
            "outcome": "INCOMPLETE",
            "reason": "QUORUM_UNMET",
            "binding": False,
            "evaluation_context": copy.deepcopy(input_document["evaluation_context"]),
            "subject": copy.deepcopy(input_document["subject"]),
            "authority": copy.deepcopy(input_document["authority"]),
            "judge": copy.deepcopy(input_document["acquired_judge"]),
            "policy": {
                "id": "gnostoa-review-assurance",
                "version": "1.0",
                "change_class": "critical",
                "review_requirement": "required",
            },
            "collection": {},
            "qualification": {},
            "quorum": {
                "minimum_distinct_domains": 2,
                "distinct_domains": 0,
                "domain_ids": [],
            },
            "blockers": [],
            "conflicts": [],
            "exclusions": [],
            "diagnostics": [],
            "assessments": [],
        }

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch.object(
                review_check,
                "evaluate_gnostoa_current_advisory",
                autospec=True,
            ) as protected_consumer:
                protected_consumer.return_value = (3, protected_result)
                with contextlib.redirect_stdout(stdout):
                    code = review_check.main(["--input", str(input_path)])

        self.assertEqual(3, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("QUORUM_UNMET", payload["reason"])
        self.assertEqual("current_advisory", payload["evaluation_context"]["mode"])
        self.assertEqual(
            "prior_integrated", payload["evaluation_context"]["judge_relation"]
        )
        protected_consumer.assert_called_once_with(input_document)

    def test_current_advisory_still_rejects_caller_selected_policy(self) -> None:
        input_document, policy = _protected_looking_input()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            policy_path = root / "policy.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = review_check.main(
                    ["--input", str(input_path), "--policy", str(policy_path)]
                )

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("CONFIGURATION_ERROR", payload["error"]["code"])
        self.assertIn("forbids caller-selected --policy", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
