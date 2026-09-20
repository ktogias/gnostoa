from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _adapter():
    root = Path(__file__).resolve().parents[1]
    path = root / "ci" / "review_github_current_state.py"
    spec = importlib.util.spec_from_file_location("gnostoa_l1_batch_adapter", path)
    if spec is None or spec.loader is None:
        raise AssertionError("L1_GITHUB_ADAPTER_UNLOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UsefulL1BatchIsolationTests(unittest.TestCase):
    def test_publish_failure_isolated_to_one_entry(self) -> None:
        adapter = _adapter()
        entries = [
            {"pull_number": 301},
            {"pull_number": 302},
            {"pull_number": 303},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "payload.json"
            payload.write_text(json.dumps(entries), encoding="utf-8")
            client = mock.Mock()
            with (
                mock.patch.object(adapter, "GitHubRestClient", return_value=client),
                mock.patch.object(
                    adapter,
                    "publish_entry",
                    side_effect=[
                        adapter.ProviderWriteError("one PR unavailable"),
                        {"pull_number": 302, "published": True, "reason": "UPDATED"},
                        {"pull_number": 303, "published": True, "reason": "CREATED"},
                    ],
                ) as publish,
                mock.patch.object(adapter, "_summary") as summary,
            ):
                code = adapter.main(
                    [
                        "--mode",
                        "publish",
                        "--repository",
                        "ktogias/gnostoa",
                        "--payload",
                        str(payload),
                    ]
                )

        self.assertEqual(0, code)
        self.assertEqual(3, publish.call_count)
        rendered = "\n".join(summary.call_args.args[0])
        self.assertIn("PR #301: PUBLICATION_ENTRY_UNAVAILABLE", rendered)
        self.assertIn("PR #302: UPDATED", rendered)
        self.assertIn("PR #303: CREATED", rendered)

    def test_collect_failure_isolated_to_one_entry(self) -> None:
        adapter = _adapter()
        good = {
            "pull_number": 302,
            "head_sha": "a" * 40,
            "body": "bounded projection",
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "payload.json"
            client = mock.Mock()
            with (
                mock.patch.object(adapter, "GitHubRestClient", return_value=client),
                mock.patch.object(
                    adapter,
                    "_collect_entry",
                    side_effect=[ValueError("projection render unavailable"), good],
                ) as collect,
                mock.patch.object(adapter, "_summary"),
            ):
                code = adapter.main(
                    [
                        "--mode",
                        "collect",
                        "--repository",
                        "ktogias/gnostoa",
                        "--pull-number",
                        "301",
                        "--pull-number",
                        "302",
                        "--output",
                        str(output),
                        "--run-id",
                        "1",
                        "--run-attempt",
                        "1",
                    ]
                )

            stored = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, code)
        self.assertEqual(2, collect.call_count)
        self.assertEqual("UNAVAILABLE", stored[0]["collection_status"])
        self.assertEqual("RECONCILIATION_ENTRY_UNAVAILABLE", stored[0]["reason"])
        self.assertEqual(good, stored[1])


if __name__ == "__main__":
    unittest.main()
