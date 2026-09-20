from __future__ import annotations

import importlib.util
import io
import unittest
import urllib.error
from pathlib import Path
from typing import Any
from unittest import mock


def _fixtures() -> Any:
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location("l1_thread_state_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _GraphQLPagedFake:
    def __init__(
        self,
        replies: dict[str, tuple[Any, dict[str, str]]],
        graphql_pages: dict[str | None, Any],
    ) -> None:
        self.replies = replies
        self.graphql_pages = graphql_pages
        self.calls: list[str] = []
        self.graphql_calls: list[dict[str, Any]] = []

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.calls.append(url)
        if url not in self.replies:
            raise RuntimeError(f"unexpected URL: {url}")
        return self.replies[url]

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        del query
        self.graphql_calls.append(dict(variables))
        cursor = variables.get("cursor")
        response = self.graphql_pages.get(cursor)
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise RuntimeError(f"unexpected GraphQL cursor: {cursor!r}")
        return response


def _thread_page(
    *,
    thread_id: str,
    comment_id: int,
    resolved: bool,
    next_cursor: str | None,
) -> dict[str, Any]:
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [
                            {
                                "id": thread_id,
                                "isResolved": resolved,
                                "isOutdated": False,
                                "comments": {
                                    "nodes": [
                                        {
                                            "databaseId": comment_id,
                                            "url": (
                                                "https://github.com/ktogias/gnostoa/"
                                                f"pull/300#discussion_r{comment_id}"
                                            ),
                                        }
                                    ]
                                },
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": next_cursor is not None,
                            "endCursor": next_cursor,
                        },
                    }
                }
            }
        }
    }


class UsefulL1ThreadStateTests(unittest.TestCase):
    def test_graphql_review_threads_are_paginated_and_drive_r2a_thread_state(
        self,
    ) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        client = _GraphQLPagedFake(
            fixtures._complete_replies(root),
            {
                None: _thread_page(
                    thread_id="PRRT_thread_one",
                    comment_id=20,
                    resolved=False,
                    next_cursor="cursor-2",
                ),
                "cursor-2": _thread_page(
                    thread_id="PRRT_thread_two",
                    comment_id=21,
                    resolved=True,
                    next_cursor=None,
                ),
            },
        )

        snapshot = adapter._collect_snapshot_once(
            client,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        self.assertEqual(
            {"status": "COMPLETE", "pages": 2, "count": 2},
            snapshot["coverage"]["review_threads"],
        )
        self.assertEqual(
            ["unresolved", "resolved"],
            [thread["state"] for thread in snapshot["review_threads"]],
        )
        review_input = reducer.build_review_input(snapshot, fixtures._bundle())
        observations = {
            item["observation_id"]: item
            for item in review_input["evidence_set"]["observations"]
        }
        self.assertEqual(
            {
                "state": "unresolved",
                "count": 1,
                "thread_ids": ["github-review-thread-PRRT_thread_one"],
            },
            observations["github-review-10"]["threads"],
        )
        self.assertEqual(
            {
                "state": "resolved",
                "count": 1,
                "thread_ids": ["github-review-thread-PRRT_thread_two"],
            },
            observations["github-review-11"]["threads"],
        )
        self.assertEqual(
            [None, "cursor-2"], [call.get("cursor") for call in client.graphql_calls]
        )

    def test_graphql_second_page_failure_is_partial_not_complete(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        client = _GraphQLPagedFake(
            fixtures._complete_replies(root),
            {
                None: _thread_page(
                    thread_id="PRRT_thread_one",
                    comment_id=20,
                    resolved=False,
                    next_cursor="cursor-2",
                ),
                "cursor-2": adapter.ProviderReadError(
                    "GraphQL page unavailable",
                    status=502,
                ),
            },
        )

        snapshot = adapter._collect_snapshot_once(
            client,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        coverage = snapshot["coverage"]["review_threads"]
        self.assertEqual("PARTIAL", coverage["status"])
        self.assertEqual(1, coverage["pages"])
        self.assertEqual(1, coverage["count"])
        self.assertEqual(1, len(snapshot["review_threads"]))

    def test_malformed_graphql_page_info_is_explicit_thread_error(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        malformed = _thread_page(
            thread_id="PRRT_bad_page_info",
            comment_id=20,
            resolved=True,
            next_cursor=None,
        )
        malformed["data"]["repository"]["pullRequest"]["reviewThreads"]["pageInfo"][
            "hasNextPage"
        ] = "yes"
        client = _GraphQLPagedFake(
            fixtures._complete_replies(root),
            {None: malformed},
        )

        snapshot = adapter._collect_snapshot_once(
            client,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        coverage = snapshot["coverage"]["review_threads"]
        self.assertEqual("ERROR", coverage["status"])
        self.assertEqual(0, coverage["pages"])
        self.assertEqual(0, coverage["count"])
        self.assertEqual([], snapshot["review_threads"])

    def test_unmapped_graphql_thread_root_fails_closed(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        client = _GraphQLPagedFake(
            fixtures._complete_replies(root),
            {
                None: _thread_page(
                    thread_id="PRRT_unmapped",
                    comment_id=999999,
                    resolved=False,
                    next_cursor=None,
                )
            },
        )

        snapshot = adapter._collect_snapshot_once(
            client,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        coverage = snapshot["coverage"]["review_threads"]
        self.assertEqual("PARTIAL", coverage["status"])
        self.assertEqual("unmapped_thread_root_comment", coverage["reason"])
        self.assertEqual([], snapshot["review_threads"])

    def test_publish_mode_isolates_one_entry_failure(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        entries = [{"pull_number": 1}, {"pull_number": 2}]
        second = {"pull_number": 2, "published": True, "reason": "UPDATED"}

        with (
            mock.patch.object(adapter, "_load_payload", return_value=entries),
            mock.patch.object(
                adapter,
                "publish_entry",
                side_effect=[adapter.ProviderWriteError("first failed"), second],
            ) as publish,
            mock.patch.object(adapter, "_summary") as summary,
            mock.patch.dict(adapter.os.environ, {"GH_TOKEN": "test-token"}),
        ):
            code = adapter.main(
                [
                    "--mode",
                    "publish",
                    "--repository",
                    "ktogias/gnostoa",
                    "--payload",
                    "unused.json",
                ]
            )

        self.assertEqual(0, code)
        self.assertEqual(2, publish.call_count)
        rendered = "\n".join(summary.call_args.args[0])
        self.assertIn("PR #1: PUBLICATION_ENTRY_UNAVAILABLE", rendered)
        self.assertIn("PR #2: UPDATED", rendered)

    def test_collect_mode_preserves_per_entry_failure_reason(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        good = {
            "pull_number": 301,
            "head_sha": "a" * 40,
            "body": "projection",
        }

        with (
            mock.patch.object(
                adapter,
                "_collect_entry",
                side_effect=[ValueError("projection too large"), good],
            ) as collect,
            mock.patch.object(adapter, "_write_payload"),
            mock.patch.object(adapter, "_summary") as summary,
            mock.patch.dict(adapter.os.environ, {"GH_TOKEN": "test-token"}),
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
                    "unused.json",
                    "--run-id",
                    "999",
                ]
            )

        self.assertEqual(0, code)
        self.assertEqual(2, collect.call_count)
        rendered = "\n".join(summary.call_args.args[0])
        self.assertIn(
            "PR #300: UNAVAILABLE (RECONCILIATION_ENTRY_UNAVAILABLE)", rendered
        )
        self.assertIn("PR #301: projection collected", rendered)

    def test_unavailable_entry_reason_survives_publish_skip(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        client = mock.Mock()

        result = adapter.publish_entry(
            client,
            repository="ktogias/gnostoa",
            entry={
                "pull_number": 300,
                "collection_status": "UNAVAILABLE",
                "reason": "RECONCILIATION_ENTRY_UNAVAILABLE",
            },
        )

        self.assertEqual("RECONCILIATION_ENTRY_UNAVAILABLE", result["reason"])
        client.get.assert_not_called()
        client.post.assert_not_called()
        client.patch.assert_not_called()

    def test_graphql_http_failure_is_a_provider_read_failure(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        client = adapter.GitHubRestClient("test-token")
        response = io.BytesIO(b'{"message":"temporarily unavailable"}')
        error = urllib.error.HTTPError(
            "https://api.github.com/graphql",
            503,
            "Service Unavailable",
            {},
            response,
        )

        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(adapter.ProviderReadError) as caught:
                client.graphql(
                    "query($cursor:String){viewer{login}}",
                    {"cursor": None},
                )

        self.assertEqual(503, caught.exception.status)


if __name__ == "__main__":
    unittest.main()
