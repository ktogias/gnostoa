from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import review_live

ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "tools" / "cli.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
SMOKE_PATH = ROOT / "ci" / "review_b16_entrypoint_smoke.py"
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md"
)
FOCUSED_TEST_PATH = "tests/test_review_assurance_p2b_b16_entrypoint_red.py"


class ReviewAssuranceP2bB16EntrypointRedTests(unittest.TestCase):
    def test_installed_cli_exposes_only_the_integrated_live_entrypoint(self) -> None:
        cli = CLI_PATH.read_text(encoding="utf-8")
        self.assertIn("review_live,", cli, "P2B_B16_LIVE_ENTRYPOINT_UNAVAILABLE")
        self.assertIn('"review-current-advisory": (', cli)
        self.assertIn("review_live.main", cli)

        live = (ROOT / "tools" / "review_live.py").read_text(encoding="utf-8")
        self.assertIn("def main(", live)
        self.assertIn('"--input"', live)
        for forbidden in (
            '"--policy"',
            '"--change-class"',
            '"--repository"',
            '"--consumer-image"',
            '"--docker-host"',
            '"--docker-context"',
        ):
            self.assertNotIn(forbidden, live)

    def test_live_entrypoint_transports_the_evaluator_result_without_projection(
        self,
    ) -> None:
        self.assertTrue(
            hasattr(review_live, "main"),
            "P2B_B16_LIVE_ENTRYPOINT_UNAVAILABLE",
        )
        main = review_live.main
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
                    review_live,
                    "evaluate_gnostoa_current_advisory",
                    return_value=(3, expected_payload),
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = main(["--input", str(input_path)])

        self.assertEqual(3, code)
        self.assertEqual(expected_payload, json.loads(stdout.getvalue()))
        evaluate.assert_called_once_with(input_document)

    def test_live_entrypoint_rejects_ambiguous_json_before_evaluation(self) -> None:
        self.assertTrue(
            hasattr(review_live, "main"),
            "P2B_B16_LIVE_ENTRYPOINT_UNAVAILABLE",
        )
        main = review_live.main

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text('{"duplicate":1,"duplicate":2}', encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_live,
                    "evaluate_gnostoa_current_advisory",
                ) as evaluate,
                contextlib.redirect_stdout(stdout),
            ):
                code = main(["--input", str(input_path)])

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
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(f'- "{FOCUSED_TEST_PATH}"', workflow)
        self.assertIn('- "ci/review_b16_entrypoint_smoke.py"', workflow)
        self.assertIn(
            '- "knowledge/decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md"',
            workflow,
        )
        self.assertIn(
            f"PYTHONPATH=. python {FOCUSED_TEST_PATH}",
            workflow,
        )
        self.assertIn(
            "PYTHONPATH=. python ci/review_b16_entrypoint_smoke.py",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
