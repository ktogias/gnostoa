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
    def test_candidate_semantic_consumer_stays_dormant_after_b2_activation(
        self,
    ) -> None:
        input_document = {
            "evaluation_context": {
                "mode": "current_advisory",
                "judge_relation": "prior_integrated",
                "fixture_only": False,
            }
        }
        raw_result = (
            b'{"binding":false,"outcome":"INCOMPLETE","reason":"QUORUM_UNMET"}\n'
        )

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            output_bytes = io.BytesIO()
            stdout = io.TextIOWrapper(
                output_bytes, encoding="utf-8", write_through=True
            )
            with (
                mock.patch.object(
                    review_check,
                    "evaluate_gnostoa_current_advisory",
                    create=True,
                ) as candidate_consumer,
                mock.patch.object(
                    review_check,
                    "run_prior_effective_current_advisory",
                    return_value=(3, raw_result),
                ) as prior_effective,
                contextlib.redirect_stdout(stdout),
            ):
                code = review_check.main(["--input", str(input_path)])
            stdout.flush()
            observed = output_bytes.getvalue()

        self.assertEqual(3, code)
        self.assertEqual(raw_result, observed)
        prior_effective.assert_called_once_with(input_document)
        candidate_consumer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
