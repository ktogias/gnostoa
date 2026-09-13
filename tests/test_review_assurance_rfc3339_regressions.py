from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools import cli, review_check
from tools.review_model import parse_rfc3339

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "review_check" / "cases.json"


class ReviewAssuranceRfc3339Regressions(unittest.TestCase):
    def test_programmatic_timestamp_rejects_space_separator(self) -> None:
        with self.assertRaises(ValueError):
            parse_rfc3339("2026-09-12 00:00:00+00:00")

    def test_public_schema_rejects_non_rfc3339_timestamp_format(self) -> None:
        fixture = json.loads(FIX.read_text(encoding="utf-8"))
        input_document = copy.deepcopy(fixture["base"]["input"])
        input_document["evaluation_context"]["as_of"] = "2026-09-12 00:10:00+00:00"

        errors = review_check._schema_errors(
            input_document,
            "review-check-input.schema.json",
        )

        self.assertTrue(errors)
        self.assertTrue(any("date-time" in error for error in errors))

    def test_public_cli_rejects_non_rfc3339_timestamp(self) -> None:
        fixture = json.loads(FIX.read_text(encoding="utf-8"))
        input_document = copy.deepcopy(fixture["base"]["input"])
        policy_document = copy.deepcopy(fixture["base"]["policy"])
        input_document["subject"]["observed_at"] = "2026-09-12 00:00:00+00:00"

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            policy_path = root / "policy.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
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
        self.assertEqual("MALFORMED_INVOCATION", payload["error"]["code"])
        self.assertTrue(payload["error"]["details"]["issues"])


if __name__ == "__main__":
    unittest.main()
