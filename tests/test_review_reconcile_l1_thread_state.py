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
