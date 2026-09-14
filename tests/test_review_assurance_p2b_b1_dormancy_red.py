from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import review_check


class ReviewAssuranceP2bB1DormancyRedTests(unittest.TestCase):
    def test_candidate_cli_keeps_prior_integrated_current_advisory_dormant(
        self,
    ) -> None:
        input_document = {
            "evaluation_context": {
                "mode": "current_advisory",
                "judge_relation": "prior_integrated",
                "fixture_only": False,
            }
        }

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


if __name__ == "__main__":
    unittest.main()
