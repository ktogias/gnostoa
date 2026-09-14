from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

from tools import review_check, review_current, review_live
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"


def _timestamp_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _bundle() -> dict[str, object]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise AssertionError("integrated P2b-A authority bundle must be a JSON object")
    return bundle


def _protected_looking_input() -> tuple[dict[str, object], dict[str, object]]:
    bundle = _bundle()
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


def _protected_document() -> ProtectedMainDocument:
    return ProtectedMainDocument(
        protected_main_revision="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",  # pragma: allowlist secret -- synthetic protected-main revision
        document=copy.deepcopy(_bundle()),
    )


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

    def test_protected_consumer_has_no_caller_selectable_trust_inputs(self) -> None:
        self.assertEqual(
            ["input_document"],
            list(
                inspect.signature(
                    review_live.evaluate_gnostoa_current_advisory
                ).parameters
            ),
        )

    def test_live_consumer_rejects_non_gnostoa_subject_before_protected_acquisition(
        self,
    ) -> None:
        input_document, _ = _protected_looking_input()
        subject = input_document["subject"]
        assert isinstance(subject, dict)
        subject["repository"] = "https://github.com/example/not-gnostoa"
        trusted_cut = subject["observed_at"]
        assert isinstance(trusted_cut, str)
        protected = _protected_document()

        def execute(
            delegated: dict[str, object], bundle: dict[str, object]
        ) -> tuple[int, dict[str, object]]:
            policy = bundle["policy"]
            assert isinstance(policy, dict)
            return review_check.evaluate_documents(delegated, policy)

        with (
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
                return_value=protected,
            ) as acquire,
            mock.patch.object(review_live, "_trusted_cut", return_value=trusted_cut),
            mock.patch.object(
                review_live,
                "_execute_semantic_review",
                side_effect=execute,
            ) as execute_review,
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(2, code)
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        self.assertIn("Gnostoa-self repository", payload["error"]["message"])
        acquire.assert_not_called()
        execute_review.assert_not_called()

    def test_dormant_b1_consumer_is_not_wired_into_candidate_cli(self) -> None:
        input_document, _ = _protected_looking_input()
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            stdout = io.StringIO()
            with mock.patch.object(
                review_check,
                "evaluate_gnostoa_current_advisory",
                create=True,
            ) as candidate_consumer:
                candidate_consumer.return_value = (
                    3,
                    {
                        "outcome": "INCOMPLETE",
                        "reason": "SYNTHETIC_CANDIDATE_CONSUMER",
                        "binding": False,
                    },
                )
                with contextlib.redirect_stdout(stdout):
                    code = review_check.main(["--input", str(input_path)])

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("CONFIGURATION_ERROR", payload["error"]["code"])
        self.assertIn(
            "prior-integrated authority acquisition is not available",
            payload["error"]["message"],
        )
        candidate_consumer.assert_not_called()

    def test_live_consumer_replaces_caller_cut_and_preserves_truthful_quorum_unmet(
        self,
    ) -> None:
        input_document, _ = _protected_looking_input()
        context = input_document["evaluation_context"]
        assert isinstance(context, dict)
        context["as_of"] = "2000-01-01T00:00:00Z"
        subject = input_document["subject"]
        assert isinstance(subject, dict)
        trusted_cut = subject["observed_at"]
        assert isinstance(trusted_cut, str)
        protected = _protected_document()

        def execute(
            delegated: dict[str, object], bundle: dict[str, object]
        ) -> tuple[int, dict[str, object]]:
            delegated_context = delegated["evaluation_context"]
            assert isinstance(delegated_context, dict)
            self.assertEqual("historical_replay", delegated_context["mode"])
            self.assertEqual(trusted_cut, delegated_context["as_of"])
            self.assertEqual("prior_integrated", delegated_context["judge_relation"])
            self.assertFalse(delegated_context["fixture_only"])
            self.assertEqual(bundle["authority"], delegated["authority"])
            self.assertEqual(bundle["acquired_judge"], delegated["acquired_judge"])
            self.assertEqual(
                bundle["qualification_snapshot"], delegated["qualification_snapshot"]
            )
            policy = bundle["policy"]
            assert isinstance(policy, dict)
            return review_check.evaluate_documents(delegated, policy)

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
                side_effect=execute,
            ),
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("QUORUM_UNMET", payload["reason"])
        self.assertFalse(payload["binding"])
        projected_context = payload["evaluation_context"]
        self.assertEqual("current_advisory", projected_context["mode"])
        self.assertEqual(trusted_cut, projected_context["as_of"])
        self.assertNotEqual(context["as_of"], projected_context["as_of"])
        self.assertTrue(
            any(
                "protected prior-integrated OCI" in diagnostic
                for diagnostic in payload["diagnostics"]
            )
        )

    def test_live_consumer_rejects_caller_authority_drift_before_runtime(self) -> None:
        input_document, _ = _protected_looking_input()
        authority = input_document["authority"]
        assert isinstance(authority, dict)
        authority["policy_digest"] = "sha256:" + (
            "0" * 64
        )  # pragma: allowlist secret -- synthetic mismatch digest
        protected = _protected_document()

        with (
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
                return_value=protected,
            ),
            mock.patch.object(review_live, "_execute_semantic_review") as execute,
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(2, code)
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        self.assertIn("does not match protected", payload["error"]["message"])
        execute.assert_not_called()

    def test_bound_runtime_unavailable_is_trusted_incomplete_not_pass(self) -> None:
        input_document, _ = _protected_looking_input()
        protected = _protected_document()
        subject = input_document["subject"]
        assert isinstance(subject, dict)
        trusted_cut = subject["observed_at"]
        assert isinstance(trusted_cut, str)

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
                    "synthetic unavailable runtime",
                ),
            ),
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual("PRIOR_INTEGRATED_JUDGE_UNAVAILABLE", payload["reason"])
        self.assertFalse(payload["binding"])
        self.assertEqual(protected.document["authority"], payload["authority"])
        self.assertEqual(protected.document["acquired_judge"], payload["judge"])

    def test_docker_runtime_selection_does_not_inherit_caller_context(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            with mock.patch.dict(
                os.environ,
                {
                    "DOCKER_HOST": "tcp://attacker.invalid:2375",
                    "DOCKER_CONTEXT": "attacker",
                    "DOCKER_CONFIG": "/attacker/config",
                    "PATH": "/attacker/bin",
                },
                clear=False,
            ):
                environment = review_current._docker_environment(config)
                self.assertEqual(
                    {
                        "DOCKER_CONFIG": str(config),
                        "HOME": str(config),
                        "LC_ALL": "C",
                        "PATH": os.defpath,
                    },
                    environment,
                )
                with mock.patch.object(
                    review_current.shutil,
                    "which",
                    return_value="/usr/bin/docker",
                ) as which:
                    self.assertEqual(
                        "/usr/bin/docker", review_current._docker_executable()
                    )
                    which.assert_called_once_with("docker", path=os.defpath)

    def test_docker_output_bound_terminates_before_process_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            script = (
                "import sys,time;"
                f"sys.stdout.buffer.write(b'x'*{review_current._MAX_RUNTIME_OUTPUT_BYTES + 1});"
                "sys.stdout.flush();"
                "time.sleep(5)"
            )
            with mock.patch.object(
                review_current,
                "_docker_executable",
                return_value=sys.executable,
            ):
                with self.assertRaisesRegex(
                    review_current.ProtectedJudgeUnavailable,
                    "stdout exceeds the bounded size",
                ):
                    review_current._run_docker(
                        ["-c", script],
                        config_dir=config,
                        timeout=1,
                    )

    def test_malformed_installed_schema_is_tool_error(self) -> None:
        input_document, _ = _protected_looking_input()
        malformed = json.JSONDecodeError("synthetic malformed schema", "{", 0)
        with (
            mock.patch.object(review_live, "_schema_errors", side_effect=malformed),
            mock.patch.object(
                review_live,
                "acquire_gnostoa_current_advisory_bundle",
            ) as acquire,
        ):
            code, payload = review_live.evaluate_gnostoa_current_advisory(
                input_document
            )

        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn(
            "protected current-advisory authority is invalid",
            payload["error"]["message"],
        )
        acquire.assert_not_called()

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

    def test_protected_current_advisory_rejects_caller_change_class(self) -> None:
        input_document, _ = _protected_looking_input()
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = review_check.main(
                    ["--input", str(input_path), "--change-class", "critical"]
                )

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("CONFIGURATION_ERROR", payload["error"]["code"])
        self.assertIn(
            "forbids caller-selected --change-class", payload["error"]["message"]
        )


if __name__ == "__main__":
    unittest.main()
