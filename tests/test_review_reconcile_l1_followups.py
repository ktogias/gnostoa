from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


def _fixtures() -> Any:
    """Reuse source-bound fixtures independently of discovery's sys.path."""
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location("l1_followup_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UsefulL1FollowupTests(unittest.TestCase):
    def test_invalid_provider_timestamps_are_source_errors(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        sources = (
            (
                "conversation",
                f"{root}/issues/300/comments?per_page=100",
                False,
                ("created_at", "updated_at"),
            ),
            (
                "reviews",
                f"{root}/pulls/300/reviews?per_page=100",
                False,
                ("submitted_at",),
            ),
            (
                "review_threads",
                f"{root}/pulls/300/comments?per_page=100",
                False,
                ("created_at", "updated_at"),
            ),
            (
                "checks",
                f"{root}/commits/{'a' * 40}/check-runs?per_page=100",
                True,
                ("started_at", "completed_at"),
            ),
        )
        for source, url, wrapped, fields in sources:
            for field in fields:
                for value in ("not-a-timestamp", "2026-99-19T16:40:00Z", 123):
                    with self.subTest(source=source, field=field, value=value):
                        replies = copy.deepcopy(fixtures._complete_replies(root))
                        payload = replies[url][0]
                        items = payload["check_runs"] if wrapped else payload
                        items[0][field] = value
                        snapshot = adapter.collect_snapshot(
                            fixtures._PagedFake(replies),
                            repository="ktogias/gnostoa",
                            pull_number=300,
                            observed_at="2026-09-19T16:41:00Z",
                        )
                        self.assertEqual(
                            "ERROR", snapshot["coverage"][source]["status"]
                        )
                        self.assertEqual([], snapshot[source])

    def test_subject_read_failure_is_a_non_publishable_per_pr_diagnostic(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        endpoints = (
            f"{root}/pulls/300",
            f"{root}/compare/{'b' * 40}...{'a' * 40}",
        )
        for endpoint in endpoints:
            for malformed in (False, True):
                with self.subTest(endpoint=endpoint, malformed=malformed):
                    reader = fixtures._PagedFake(fixtures._complete_replies(root))
                    original_get = reader.get

                    def read(
                        url: str,
                        *,
                        failed_url: str = endpoint,
                        bad_shape: bool = malformed,
                        delegate: Any = original_get,
                    ) -> Any:
                        if url == failed_url:
                            if bad_shape:
                                return {"unexpected": "shape"}, {}
                            raise adapter.ProviderReadError(
                                "simulated failure", status=500
                            )
                        return delegate(url)

                    with (
                        mock.patch.object(reader, "get", side_effect=read),
                        mock.patch.object(adapter, "_protected_state") as protected,
                    ):
                        entry = adapter._collect_entry(
                            reader,
                            "ktogias/gnostoa",
                            300,
                            run_id=200,
                            run_attempt=1,
                        )
                    self.assertEqual("UNAVAILABLE", entry["collection_status"])
                    self.assertEqual("ERROR", entry["coverage"]["subject"]["status"])
                    self.assertNotIn("head_sha", entry)
                    self.assertNotIn("body", entry)
                    protected.assert_not_called()
                    publisher = mock.Mock()
                    result = adapter.publish_entry(
                        publisher, repository="ktogias/gnostoa", entry=entry
                    )
                    self.assertIs(False, result["published"])
                    self.assertEqual("PROVIDER_SUBJECT_UNAVAILABLE", result["reason"])
                    self.assertEqual([], publisher.mock_calls)

    def test_collection_keeps_other_prs_and_diagnostic_in_summary(self) -> None:
        adapter = _fixtures()._adapter()
        diagnostic = {
            "pull_number": 300,
            "collection_status": "UNAVAILABLE",
            "reason": "PROVIDER_SUBJECT_UNAVAILABLE",
            "coverage": {"subject": {"status": "ERROR", "pages": 0, "count": 0}},
        }
        good = {"pull_number": 301, "head_sha": "a" * 40, "body": "projection"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "publication.json"
            with (
                mock.patch.object(adapter, "GitHubRestClient"),
                mock.patch.object(
                    adapter, "_collect_entry", side_effect=[diagnostic, good]
                ),
                mock.patch.object(adapter, "_summary") as summary,
            ):
                code = adapter.main(
                    [
                        "--mode",
                        "collect",
                        "--repository",
                        "ktogias/gnostoa",
                        "--pull-number",
                        "300",
                        "--pull-number",
                        "301",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(0, code)
            self.assertEqual([diagnostic, good], json.loads(output.read_text()))
            self.assertIn("UNAVAILABLE", "\n".join(summary.call_args.args[0]))
            self.assertIn("300", "\n".join(summary.call_args.args[0]))

    def test_source_changed_after_read_is_reacquired_or_incomplete(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = fixtures._complete_replies(root)
        reader = fixtures._PagedFake(replies)
        original_get = reader.get
        changed = False

        def read(url: str) -> Any:
            nonlocal changed
            if url == f"{root}/pulls/300/reviews?per_page=100" and not changed:
                changed = True
                replies[f"{root}/issues/300/comments?per_page=100"][0].append(
                    {
                        "id": 99,
                        "user": {"login": "new"},
                        "created_at": "2026-09-19T16:40:08Z",
                        "updated_at": "2026-09-19T16:40:08Z",
                        "body": "late arrival",
                    }
                )
            return original_get(url)

        with mock.patch.object(reader, "get", side_effect=read):
            snapshot = adapter.collect_snapshot(
                reader,
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:40:00Z",
            )
        ids = {item["id"] for item in snapshot["conversation"]}
        self.assertTrue(
            99 in ids or snapshot["coverage"]["conversation"]["status"] != "COMPLETE"
        )

    def test_continuously_changing_source_is_bounded_and_incomplete(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        reader = fixtures._PagedFake(fixtures._complete_replies(root))
        original_get = reader.get
        reads = 0

        def read(url: str) -> Any:
            nonlocal reads
            payload, headers = copy.deepcopy(original_get(url))
            if url == f"{root}/issues/300/comments?per_page=100":
                reads += 1
                payload[0]["body"] = f"changing revision {reads}"
            return payload, headers

        with mock.patch.object(reader, "get", side_effect=read):
            snapshot = adapter.collect_snapshot(
                reader,
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:41:00Z",
            )
        self.assertNotEqual("COMPLETE", snapshot["coverage"]["conversation"]["status"])
        self.assertLessEqual(len(reader.calls), 60)

    def test_queued_check_without_provider_timestamps_uses_collection_cut(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = copy.deepcopy(fixtures._complete_replies(root))
        check_url = f"{root}/commits/{'a' * 40}/check-runs?per_page=100"
        replies[check_url] = (
            {
                "check_runs": [
                    {
                        "id": 88,
                        "name": "queued-check",
                        "head_sha": "a" * 40,
                        "started_at": None,
                        "completed_at": None,
                        "status": "queued",
                        "conclusion": None,
                        "details_url": "https://example.invalid/check/88",
                    }
                ]
            },
            {},
        )
        cut = "2026-09-19T16:41:00Z"
        snapshot = adapter.collect_snapshot(
            fixtures._PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at=cut,
        )

        self.assertEqual("COMPLETE", snapshot["coverage"]["checks"]["status"])
        self.assertEqual(1, len(snapshot["checks"]))
        self.assertEqual(cut, snapshot["checks"][0]["observed_at"])
        projection = reducer.build_projection(
            snapshot,
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result={
                "outcome": "INCOMPLETE",
                "reason": "QUORUM_UNMET",
                "binding": False,
            },
            execution={
                "run_id": 250,
                "run_attempt": 1,
                "observed_at": cut,
            },
        )
        self.assertEqual(["queued-check"], projection["checks"]["pending"])

    def test_publication_batch_bound_matches_admitted_population(self) -> None:
        adapter = _fixtures()._adapter()
        self.assertEqual(8, adapter._MAX_OPEN_PULLS)
        self.assertLessEqual(
            adapter._MAX_OPEN_PULLS * 32_768 + 20_000,
            adapter._MAX_PUBLICATION_PAYLOAD_BYTES,
        )


if __name__ == "__main__":
    unittest.main()
