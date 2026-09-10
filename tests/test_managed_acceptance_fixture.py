"""D11-F1 frozen observable oracle, shared by baseline and later candidate."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "managed_acceptance"
IMPLEMENTATION = os.environ.get("GNOSTOA_FIXTURE_IMPLEMENTATION", "candidate")
ADAPTER_NAMES = ("tagged", "batched")


class ManagedAcceptanceFixtureTests(unittest.TestCase):
    def assert_observable_subset(
        self, expected: Any, actual: Any, location: str = "result"
    ) -> None:
        if isinstance(expected, dict):
            self.assertIsInstance(actual, dict, location)
            for key, value in expected.items():
                self.assertIn(key, actual, f"{location}.{key}")
                self.assert_observable_subset(value, actual[key], f"{location}.{key}")
        elif isinstance(expected, list):
            self.assertIsInstance(actual, list, location)
            self.assertEqual(len(expected), len(actual), location)
            for index, (wanted, observed) in enumerate(
                zip(expected, actual, strict=False)
            ):
                self.assert_observable_subset(wanted, observed, f"{location}[{index}]")
        else:
            self.assertEqual(expected, actual, location)

    def test_frozen_behavior_at_persisted_result_consumer(self) -> None:
        oracle = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
        self.assertEqual(
            list(oracle["cases"]), [f"F{number:02d}" for number in range(1, 13)]
        )
        with TemporaryDirectory(prefix="gnostoa-f1-oracle-") as directory:
            for case_id, expected in oracle["cases"].items():
                for adapter in ADAPTER_NAMES:
                    with self.subTest(case=case_id, adapter=adapter):
                        path = Path(directory) / f"{case_id}-{adapter}.json"
                        command = [
                            sys.executable,
                            str(FIXTURE / "run_fixture.py"),
                            "--case",
                            case_id,
                            "--adapter",
                            adapter,
                            "--implementation",
                            IMPLEMENTATION,
                            "--output",
                            str(path),
                        ]
                        completed = subprocess.run(
                            command, capture_output=True, text=True, check=False
                        )
                        self.assertEqual(
                            completed.returncode,
                            0,
                            "Fixture infrastructure failed, not behavioral RED:\n"
                            + completed.stderr,
                        )
                        consumed = subprocess.run(
                            [
                                sys.executable,
                                str(FIXTURE / "read_result.py"),
                                str(path),
                            ],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertEqual(consumed.returncode, 0, consumed.stderr)
                        actual = json.loads(consumed.stdout)
                        self.assertEqual(actual, json.loads(completed.stdout))
                        self.assertEqual(actual["case_id"], case_id)
                        self.assertEqual(actual["adapter"], adapter)
                        self.assertEqual(actual["implementation"], IMPLEMENTATION)
                        self.assert_observable_subset(expected, actual)


if __name__ == "__main__":
    unittest.main()
