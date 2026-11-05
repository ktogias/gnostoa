"""What other test modules share from tests/test_review_reconcile_l1.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import importlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


ADAPTER_PATH = ROOT / "ci" / "review_github_current_state.py"


GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"


def reducer() -> ModuleType:
    spec = importlib.util.find_spec("tools.review_reconcile")
    if spec is None:
        raise AssertionError("L1_REDUCER_UNAVAILABLE")
    return importlib.import_module("tools.review_reconcile")


def reducer_fixture() -> ModuleType:
    """Public test-only access to the shared provider-neutral reducer fixture."""
    return reducer()


def snapshot_fixture() -> dict[str, Any]:
    """Public test-only access to the shared normalized provider snapshot."""
    return snapshot()


def adapter() -> ModuleType:
    if not ADAPTER_PATH.is_file():
        raise AssertionError("L1_GITHUB_ADAPTER_UNAVAILABLE")
    spec = importlib.util.spec_from_file_location(
        "gnostoa_l1_github_adapter", ADAPTER_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("L1_GITHUB_ADAPTER_UNLOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def adapter_fixture() -> ModuleType:
    """Public test-only access to the shared GitHub adapter fixture."""
    return adapter()


def bundle() -> dict[str, Any]:
    path = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("protected authority fixture must be an object")
    return loaded


def valid_incomplete_result(input_document: dict[str, Any]) -> tuple[int, bytes]:
    """A valid outer result for ``input_document``: the public evaluator's own
    non-binding INCOMPLETE answer for current advisory, exit 3, canonically encoded
    as the protected outer runtime returns it."""
    from tools import review_check
    from tools.review_model import canonical_json

    code, payload = review_check.evaluate_documents(input_document, bundle()["policy"])
    if (
        code != 3
        or payload.get("outcome") != "INCOMPLETE"
        or payload.get("binding") is not False
    ):
        raise AssertionError(
            "fixture evaluation is not a non-binding INCOMPLETE: "
            f"{code} {payload.get('outcome')!r}"
        )
    return code, (canonical_json(payload) + "\n").encode("utf-8")


def snapshot(
    *,
    provider_id: str = "github",
    repository: str = "https://github.com/ktogias/gnostoa",
    change_kind: str = "github-pull-request",
    change_id: str = "300",
    source_url: str = "https://github.com/ktogias/gnostoa/pull/300",
) -> dict[str, Any]:
    return {
        "schema_version": "gnostoa-review-provider-state/v1",
        "provider": {
            "id": provider_id,
            "adapter": f"{provider_id}-fixture/v1",
        },
        "observed_at": "2026-09-19T16:41:00Z",
        "subject": {
            "repository": repository,
            "change_request": {
                "kind": change_kind,
                "id": change_id,
            },
            "state": "open",
            "head_commit": "a" * 40,
            "base_commit": "b" * 40,
            "comparison": {
                "kind": "merge_base",
                "commit_sha": "c" * 40,
            },
            "source_url": source_url,
            "title": "Useful L1 fixture",
        },
        "coverage": {
            "subject": {"status": "COMPLETE", "pages": 1, "count": 1},
            "conversation": {"status": "COMPLETE", "pages": 2, "count": 1},
            "reviews": {"status": "COMPLETE", "pages": 2, "count": 2},
            "review_threads": {"status": "COMPLETE", "pages": 1, "count": 1},
            "checks": {"status": "COMPLETE", "pages": 1, "count": 1},
        },
        "conversation": [
            {
                "id": "conversation-1",
                "author": "review-bot",
                "observed_at": "2026-09-19T16:40:20Z",
                "body": "raw provider text that must not be rendered",
            }
        ],
        "reviews": [
            {
                "observation_id": "provider-review-10",
                "reviewer_id": "qodo-code-review[bot]",
                "recommendation_state": "APPROVED",
                "observed_at": "2026-09-19T16:40:30Z",
                "head_commit": "a" * 40,
                "source_url": source_url + "#review-10",
            },
            {
                "observation_id": "provider-review-11",
                "reviewer_id": "older-reviewer",
                "recommendation_state": "COMMENTED",
                "observed_at": "2026-09-19T16:39:30Z",
                "head_commit": "d" * 40,
                "source_url": source_url + "#review-11",
            },
        ],
        "review_threads": [
            {
                "id": "provider-thread-20",
                "review_observation_id": "provider-review-10",
                "reviewer_id": "qodo-code-review[bot]",
                "observed_at": "2026-09-19T16:40:31Z",
                "head_commit": "a" * 40,
                "body": "inline raw finding",
                "source_url": source_url + "#thread-20",
                "state": "unresolved",
            }
        ],
        "checks": [
            {
                "id": "provider-check-00000000000000000030",
                "key": "provider-check:fast",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:40:40Z",
                "status": "completed",
                "conclusion": "success",
            }
        ],
    }


class PagedFake:
    def __init__(self, replies: dict[str, tuple[Any, dict[str, str]]]) -> None:
        self.replies = replies
        self.calls: list[str] = []

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.calls.append(url)
        if url not in self.replies:
            raise RuntimeError(f"unexpected URL: {url}")
        return self.replies[url]

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        cursor = variables.get("cursor")
        # The merge-evidence connections are served only from an explicit reply
        # for their cursor (#413 rounds 5 and 10).
        for marker, name in (
            ("lastEditedAt", "comments"),
            ("closingIssuesReferences", "closingIssuesReferences"),
        ):
            if marker in query:
                payload, _ = self.get(f"graphql:{name}:{cursor or 'first'}")
                return payload
        if "reviewThreads" not in query:
            raise RuntimeError("unexpected GraphQL query")
        # skipcq: PTC-W0063 -- explicit default prevents StopIteration
        first_url = next(
            (
                url
                for url in self.replies
                if url.endswith("/pulls/300/comments?per_page=100")
            ),
            None,
        )
        if first_url is None:
            raise RuntimeError("review comment fixture is unavailable")
        if cursor is None:
            url = first_url
        elif cursor == "page-2":
            url = "https://api.github.com/page2/review-comments"
        else:
            raise RuntimeError(f"unexpected GraphQL cursor: {cursor!r}")
        payload, headers = self.get(url)
        nodes = [
            {
                "id": f"PRRT_fixture_{item['id']}",
                "isResolved": True,
                "isOutdated": False,
                "comments": {
                    "nodes": [
                        {
                            "databaseId": item["id"],
                            "url": item.get("html_url"),
                        }
                    ]
                },
            }
            for item in payload
        ]
        has_next = 'rel="next"' in headers.get("link", "")
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "nodes": nodes,
                            "pageInfo": {
                                "hasNextPage": has_next,
                                "endCursor": "page-2" if has_next else None,
                            },
                        }
                    }
                }
            }
        }


def complete_replies(root: str) -> dict[str, tuple[Any, dict[str, str]]]:
    return {
        f"{root}/pulls/300": (
            {
                "number": 300,
                "state": "open",
                "html_url": "https://github.com/ktogias/gnostoa/pull/300",
                "head": {"sha": "a" * 40},
                "base": {"sha": "b" * 40},
            },
            {},
        ),
        f"{root}/compare/{'b' * 40}...{'a' * 40}": (
            {"merge_base_commit": {"sha": "c" * 40}},
            {},
        ),
        f"{root}/issues/300/comments?per_page=100": (
            [
                {
                    "id": 1,
                    "user": {"login": "one"},
                    "created_at": "2026-09-19T16:40:00Z",
                    "updated_at": "2026-09-19T16:40:00Z",
                    "body": "one",
                }
            ],
            {"link": '<https://api.github.com/page2/issues>; rel="next"'},
        ),
        "https://api.github.com/page2/issues": (
            [
                {
                    "id": 2,
                    "user": {"login": "two"},
                    "created_at": "2026-09-19T16:40:01Z",
                    "updated_at": "2026-09-19T16:40:01Z",
                    "body": "two",
                }
            ],
            {},
        ),
        f"{root}/pulls/300/reviews?per_page=100": (
            [
                {
                    "id": 10,
                    "user": {"login": "one"},
                    "state": "APPROVED",
                    "submitted_at": "2026-09-19T16:40:02Z",
                    "commit_id": "a" * 40,
                    "html_url": "https://example.invalid/review/10",
                }
            ],
            {"link": '<https://api.github.com/page2/reviews>; rel="next"'},
        ),
        "https://api.github.com/page2/reviews": (
            [
                {
                    "id": 11,
                    "user": {"login": "two"},
                    "state": "COMMENTED",
                    "submitted_at": "2026-09-19T16:40:03Z",
                    "commit_id": "a" * 40,
                    "html_url": "https://example.invalid/review/11",
                }
            ],
            {},
        ),
        f"{root}/pulls/300/comments?per_page=100": (
            [
                {
                    "id": 20,
                    "pull_request_review_id": 10,
                    "user": {"login": "one"},
                    "created_at": "2026-09-19T16:40:04Z",
                    "updated_at": "2026-09-19T16:40:04Z",
                    "commit_id": "a" * 40,
                    "body": "inline one",
                    "html_url": "https://example.invalid/comment/20",
                }
            ],
            {"link": '<https://api.github.com/page2/review-comments>; rel="next"'},
        ),
        "https://api.github.com/page2/review-comments": (
            [
                {
                    "id": 21,
                    "pull_request_review_id": 11,
                    "user": {"login": "two"},
                    "created_at": "2026-09-19T16:40:05Z",
                    "updated_at": "2026-09-19T16:40:05Z",
                    "commit_id": "a" * 40,
                    "body": "inline two",
                    "html_url": "https://example.invalid/comment/21",
                }
            ],
            {},
        ),
        f"{root}/commits/{'a' * 40}/check-runs?per_page=100": (
            {
                "check_runs": [
                    {
                        "id": 30,
                        "name": "fast",
                        "app": {"id": 1001},
                        "head_sha": "a" * 40,
                        "started_at": "2026-09-19T16:40:06Z",
                        "completed_at": "2026-09-19T16:40:07Z",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            },
            {"link": '<https://api.github.com/page2/check-runs>; rel="next"'},
        ),
        "https://api.github.com/page2/check-runs": (
            {
                "check_runs": [
                    {
                        "id": 31,
                        "name": "policy",
                        "app": {"id": 1001},
                        "head_sha": "a" * 40,
                        "started_at": "2026-09-19T16:40:08Z",
                        "completed_at": "2026-09-19T16:40:09Z",
                        "status": "completed",
                        "conclusion": "success",
                    }
                ]
            },
            {},
        ),
        f"{root}/commits/{'a' * 40}/statuses?per_page=100": ([], {}),
    }


def complete_replies_without_review_comments(
    root: str,
) -> dict[str, tuple[Any, dict[str, str]]]:
    replies = complete_replies(root)
    replies[f"{root}/pulls/300/comments?per_page=100"] = ([], {})
    replies.pop("https://api.github.com/page2/review-comments", None)
    return replies


def paged_fake_fixture(replies: dict[str, tuple[Any, dict[str, str]]]) -> Any:
    """Public test-only access to the fake provider, which refuses any URL it was
    not given (#407, slice 1b.3a)."""
    return PagedFake(replies)


def complete_replies_fixture(root: str) -> dict[str, tuple[Any, dict[str, str]]]:
    """Public test-only access to the complete provider replies for PR 300."""
    return complete_replies(root)
