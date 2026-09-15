from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import review_check, review_live_entrypoint
from tools.review_model import canonical_json

ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "tools" / "cli.py"
ENTRYPOINT_PATH = ROOT / "tools" / "review_live_entrypoint.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
GUARDRAIL_PATH = ROOT / "policy" / "guardrails.yaml"
SMOKE_PATH = ROOT / "ci" / "review_b16_entrypoint_smoke.py"
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md"
)
FOCUSED_TEST_PATH = "tests/test_review_assurance_p2b_b16_entrypoint_red.py"
ENTRYPOINT_RELATIVE_PATH = "tools/review_live_entrypoint.py"
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md"
)
SMOKE_RELATIVE_PATH = "ci/review_b16_entrypoint_smoke.py"


class ReviewAssuranceP2bB16EntrypointRedTests(unittest.TestCase):
    def test_integrated_runtime_has_input_only_private_live_entrypoint(self) -> None:
        entrypoint = ENTRYPOINT_PATH.read_text(encoding="utf-8")
        self.assertIn("review_live.evaluate_gnostoa_current_advisory", entrypoint)
        self.assertIn('"--input"', entrypoint)
        self.assertIn("canonical_json(payload)", entrypoint)
        for forbidden in (
            '"--policy"',
            '"--change-class"',
            '"--repository"',
            '"--consumer-image"',
            '"--docker-host"',
            '"--docker-context"',
        ):
            self.assertNotIn(forbidden, entrypoint)

        cli = CLI_PATH.read_text(encoding="utf-8")
        self.assertNotIn("review-current-advisory", cli)
        self.assertNotIn("review_live_entrypoint", cli)

    def test_live_entrypoint_transports_the_evaluator_result_without_projection(
        self,
    ) -> None:
        input_document = {"synthetic": "untrusted-input"}
        expected_payload = {
            "outcome": "INCOMPLETE",
            "reason": "SYNTHETIC_PRIOR_EFFECTIVE_RESULT",
            "binding": False,
        }

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live_entrypoint.review_live,
                    "evaluate_gnostoa_current_advisory",
                    return_value=(3, expected_payload),
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_live_entrypoint.main(["--input", str(input_path)])

        self.assertEqual(3, code)
        self.assertEqual(canonical_json(expected_payload) + "\n", stdout.getvalue())
        evaluate.assert_called_once_with(input_document)

    def test_live_entrypoint_rejects_ambiguous_json_before_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text('{"duplicate":1,"duplicate":2}', encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live_entrypoint.review_live,
                    "evaluate_gnostoa_current_advisory",
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_live_entrypoint.main(["--input", str(input_path)])

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        evaluate.assert_not_called()

    def test_live_entrypoint_rejects_oversized_input_before_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_bytes(b" " * (review_check.MAX_REVIEW_INPUT_BYTES + 1))
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live_entrypoint.review_live,
                    "evaluate_gnostoa_current_advisory",
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_live_entrypoint.main(["--input", str(input_path)])

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        evaluate.assert_not_called()

    def test_live_entrypoint_rejects_deep_nesting_before_evaluation(self) -> None:
        depth = review_check.MAX_REVIEW_DOCUMENT_DEPTH + 1
        nested_json = "[" * depth + "null" + "]" * depth
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(nested_json, encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live_entrypoint.review_live,
                    "evaluate_gnostoa_current_advisory",
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_live_entrypoint.main(["--input", str(input_path)])

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        evaluate.assert_not_called()

    def test_live_entrypoint_rejects_non_utf8_input_before_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_bytes(b'{"invalid":"\xff"}')
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live_entrypoint.review_live,
                    "evaluate_gnostoa_current_advisory",
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_live_entrypoint.main(["--input", str(input_path)])

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        evaluate.assert_not_called()

    def test_live_entrypoint_rejects_symlink_loop_as_malformed_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.symlink_to("input.json")
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live_entrypoint.review_live,
                    "evaluate_gnostoa_current_advisory",
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_live_entrypoint.main(["--input", str(input_path)])

        self.assertEqual(2, code)
        payload = json.loads(stdout.getvalue())
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        evaluate.assert_not_called()

    def test_precursor_remains_daemonless_and_is_dedicated_ci_protected(self) -> None:
        self.assertTrue(
            SMOKE_PATH.is_file(),
            "P2B_B16_DAEMONLESS_RUNTIME_SMOKE_UNAVAILABLE",
        )
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_B16_DURABLE_DECISION_UNAVAILABLE",
        )
        smoke = SMOKE_PATH.read_text(encoding="utf-8")
        self.assertIn('"--network",\n                "none"', smoke)
        self.assertNotIn('"bridge"', smoke)
        self.assertIn("acquire_gnostoa_current_advisory_bundle", smoke)
        self.assertIn("review_live_entrypoint.main", smoke)
        self.assertIn('"-m"', smoke)
        self.assertIn('"tools.review_live_entrypoint"', smoke)
        self.assertIn('"--input"', smoke)

        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        for path in (
            FOCUSED_TEST_PATH,
            ENTRYPOINT_RELATIVE_PATH,
            SMOKE_RELATIVE_PATH,
            DECISION_RELATIVE_PATH,
        ):
            self.assertIn(f'- "{path}"', workflow)
        self.assertIn(
            f"PYTHONPATH=. python {FOCUSED_TEST_PATH}",
            workflow,
        )
        self.assertIn(
            f"PYTHONPATH=. python {SMOKE_RELATIVE_PATH}",
            workflow,
        )

        guardrails = GUARDRAIL_PATH.read_text(encoding="utf-8")
        for path in (
            ENTRYPOINT_RELATIVE_PATH,
            SMOKE_RELATIVE_PATH,
            DECISION_RELATIVE_PATH,
            FOCUSED_TEST_PATH,
        ):
            self.assertIn(f"      - {path}", guardrails)


if __name__ == "__main__":
    unittest.main()
