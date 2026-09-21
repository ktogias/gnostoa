from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest import mock

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "ci" / "review_github_current_state.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "review-current-state.yml"
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"


def _reducer() -> ModuleType:
    spec = importlib.util.find_spec("tools.review_reconcile")
    if spec is None:
        raise AssertionError("L1_REDUCER_UNAVAILABLE")
    return importlib.import_module("tools.review_reconcile")


def reducer_fixture() -> ModuleType:
    """Public test-only access to the shared provider-neutral reducer fixture."""
    return _reducer()


def snapshot_fixture() -> dict[str, Any]:
    """Public test-only access to the shared normalized provider snapshot."""
    return _snapshot()


def _adapter() -> ModuleType:
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
    return _adapter()


def _bundle() -> dict[str, Any]:
    path = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("protected authority fixture must be an object")
    return loaded


def _consumer_document() -> dict[str, Any]:
    path = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("protected consumer fixture must be an object")
    return loaded


def _valid_incomplete_result(input_document: dict[str, Any]) -> tuple[int, bytes]:
    from tools import review_live
    from tools.review_model import canonical_json

    trusted_cut = input_document["evaluation_context"]["as_of"]
    if not isinstance(trusted_cut, str):
        raise AssertionError("evaluation cut must be a string")
    # skipcq: PYL-W0212 -- intentional white-box L1 test
    code, payload = review_live._semantic_incomplete(
        input_document,
        _bundle(),
        trusted_cut,
        "QUORUM_UNMET",
        "fixture semantic incomplete",
    )
    return code, (canonical_json(payload) + "\n").encode("utf-8")


def _snapshot(
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


class _PagedFake:
    def __init__(self, replies: dict[str, tuple[Any, dict[str, str]]]) -> None:
        self.replies = replies
        self.calls: list[str] = []

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.calls.append(url)
        if url not in self.replies:
            raise RuntimeError(f"unexpected URL: {url}")
        return self.replies[url]

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        del query
        cursor = variables.get("cursor")
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


def _complete_replies(root: str) -> dict[str, tuple[Any, dict[str, str]]]:
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


def _complete_replies_without_review_comments(
    root: str,
) -> dict[str, tuple[Any, dict[str, str]]]:
    replies = _complete_replies(root)
    replies[f"{root}/pulls/300/comments?per_page=100"] = ([], {})
    replies.pop("https://api.github.com/page2/review-comments", None)
    return replies


class UsefulL1RedContractTests(unittest.TestCase):
    def test_reducer_binds_exact_subject_and_preserves_existing_r2a_semantics(
        self,
    ) -> None:
        reducer = _reducer()
        review_input = reducer.build_review_input(_snapshot(), _bundle())

        self.assertEqual("a" * 40, review_input["subject"]["head_commit"])
        self.assertEqual("c" * 40, review_input["subject"]["comparison"]["commit_sha"])
        self.assertEqual("current_advisory", review_input["evaluation_context"]["mode"])
        self.assertEqual(
            _bundle()["authority"],
            review_input["authority"],
        )
        self.assertEqual(
            _bundle()["qualification_snapshot"],
            review_input["qualification_snapshot"],
        )

        observations = review_input["evidence_set"]["observations"]
        self.assertEqual(3, len(observations))
        by_id = {item["observation_id"]: item for item in observations}
        self.assertEqual(
            "exact", by_id["provider-review-10"]["subject_binding"]["status"]
        )
        self.assertEqual(
            "partial", by_id["provider-review-11"]["subject_binding"]["status"]
        )
        self.assertEqual(
            "APPROVED",
            by_id["provider-review-10"]["native"]["recommendation_state"],
        )
        thread_only = by_id["gnostoa-thread-evidence::provider-review-10"]
        self.assertEqual("COMMENT_ONLY", thread_only["native"]["recommendation_state"])
        self.assertEqual("exact", thread_only["subject_binding"]["status"])
        self.assertEqual("unresolved", thread_only["threads"]["state"])

    def test_reducer_core_is_provider_neutral_and_accepts_second_adapter_shape(
        self,
    ) -> None:
        reducer = _reducer()
        gitlab_snapshot = _snapshot(
            provider_id="gitlab",
            repository="https://gitlab.example/acme/widget",
            change_kind="merge-request",
            change_id="42",
            source_url="https://gitlab.example/acme/widget/-/merge_requests/42",
        )

        review_input = reducer.build_review_input(gitlab_snapshot, _bundle())
        projection = reducer.build_projection(
            gitlab_snapshot,
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
                "execution_id": "github-actions:124:1",
                "observed_at": "2026-09-19T16:41:11Z",
            },
        )

        self.assertEqual(
            "https://gitlab.example/acme/widget",
            review_input["subject"]["repository"],
        )
        self.assertEqual(
            {"kind": "merge-request", "id": "42"},
            review_input["subject"]["change_request"],
        )
        self.assertEqual("gitlab", projection["subject"]["provider_id"])
        self.assertEqual(
            reducer.PROVIDER_STATE_SCHEMA_VERSION,
            gitlab_snapshot["schema_version"],
        )

        reducer_source = (
            (ROOT / "tools" / "review_reconcile.py").read_text(encoding="utf-8").lower()
        )
        self.assertNotIn("github", reducer_source)

    def test_projection_is_bounded_and_does_not_copy_raw_provider_bodies(self) -> None:
        reducer = _reducer()
        result = {
            "outcome": "INCOMPLETE",
            "reason": "QUORUM_UNMET",
            "binding": False,
        }
        projection = reducer.build_projection(
            _snapshot(),
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result=result,
            execution={
                "execution_id": "github-actions:123:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        rendered = reducer.render_projection(projection)

        self.assertIn("INCOMPLETE", rendered)
        self.assertIn("QUORUM_UNMET", rendered)
        self.assertEqual("draft", projection["status"])
        self.assertIn("binding: false", rendered)
        self.assertIn("Intent summary: `Useful L1 fixture`", rendered)
        self.assertNotIn("raw provider text", rendered)
        self.assertNotIn("inline raw finding", rendered)
        self.assertLess(len(rendered.encode("utf-8")), 32_768)

    def test_projection_semantic_outcomes_keep_current_action_mapping(self) -> None:
        reducer = _reducer()
        cases = {
            "PASS": ("SEMANTIC_RESULT", "CONTINUE_EXISTING_WORKFLOW"),
            "BLOCKED": ("SEMANTIC_RESULT", "RECONCILE_REVIEW_EVIDENCE"),
            "CONFLICTING": ("SEMANTIC_RESULT", "RECONCILE_REVIEW_EVIDENCE"),
            "INCOMPLETE": (
                "SEMANTIC_RESULT",
                "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE",
            ),
            "UNAVAILABLE": ("UNAVAILABLE", "WAIT_FOR_PROTECTED_CAPABILITY"),
        }

        for outcome, (expected_status, expected_action) in cases.items():
            with self.subTest(outcome=outcome):
                projection = reducer.build_projection(
                    _snapshot(),
                    protected_main_revision="e" * 40,
                    outer_consumer={
                        "runtime_image": ("ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64),
                        "runtime_revision": "9" * 40,
                    },
                    r2a_result={
                        "outcome": outcome,
                        "reason": (
                            "NOT_RUN"
                            if outcome == "UNAVAILABLE"
                            else f"{outcome}_FIXTURE"
                        ),
                        "binding": False,
                    },
                    execution={
                        "execution_id": "github-actions:124:1",
                        "observed_at": "2026-09-19T16:41:11Z",
                    },
                )

                self.assertEqual(expected_status, projection["r2a"]["status"])
                self.assertEqual(outcome, projection["r2a"]["outcome"])
                self.assertEqual(
                    expected_action,
                    projection["next_permitted_action"],
                )
                rendered = reducer.render_projection(projection)
                self.assertEqual(
                    projection,
                    reducer.parse_projection_comment(rendered),
                )

    def test_pass_cannot_continue_with_incomplete_or_closed_provider_state(
        self,
    ) -> None:
        reducer = _reducer()
        for mutate in ("partial_reviews", "partial_checks", "closed"):
            snapshot = _snapshot()
            if mutate == "partial_reviews":
                snapshot["coverage"]["reviews"]["status"] = "PARTIAL"
            elif mutate == "partial_checks":
                snapshot["coverage"]["checks"]["status"] = "PARTIAL"
            else:
                snapshot["subject"]["state"] = "closed"

            projection = reducer.build_projection(
                snapshot,
                protected_main_revision="e" * 40,
                outer_consumer={
                    "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                    "runtime_revision": "9" * 40,
                },
                r2a_result={
                    "outcome": "PASS",
                    "reason": "QUORUM_SATISFIED",
                    "binding": False,
                },
                execution={
                    "execution_id": "github-actions:126:1",
                    "observed_at": "2026-09-19T16:41:12Z",
                },
            )

            with self.subTest(mutate=mutate):
                self.assertEqual(
                    "INCOMPLETE_AT_OBSERVATION",
                    projection["currentness"],
                )
                self.assertEqual(
                    "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE",
                    projection["next_permitted_action"],
                )
                self.assertEqual("NON_CURRENT", projection["r2a"]["status"])
                self.assertEqual("UNAVAILABLE", projection["r2a"]["outcome"])
                self.assertEqual(
                    "PROVIDER_STATE_INCOMPLETE",
                    projection["r2a"]["reason"],
                )
                self.assertEqual(
                    {
                        "status": "SEMANTIC_RESULT",
                        "outcome": "PASS",
                        "reason": "QUORUM_SATISFIED",
                        "binding": False,
                    },
                    projection["r2a"]["observed"],
                )
                rendered = reducer.render_projection(projection)
                self.assertNotIn("R2A: **PASS", rendered)

    def test_pass_cannot_continue_with_partial_protected_capability(self) -> None:
        reducer = _reducer()
        projection = reducer.build_projection(
            _snapshot(),
            protected_main_revision="e" * 40,
            outer_consumer=None,
            r2a_result={
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:127:1",
                "observed_at": "2026-09-19T16:41:13Z",
            },
        )

        self.assertEqual("PARTIAL", projection["protected"]["status"])
        self.assertEqual(
            "WAIT_FOR_PROTECTED_CAPABILITY",
            projection["next_permitted_action"],
        )

    def test_equal_timestamp_conflicting_checks_are_ambiguous(self) -> None:
        reducer = _reducer()
        snapshot = _snapshot()
        snapshot["checks"] = [
            {
                "id": "provider-a",
                "key": "provider-check:fast",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "success",
            },
            {
                "id": "provider-z",
                "key": "provider-check:fast",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "failure",
            },
        ]
        snapshot["coverage"]["checks"]["count"] = len(snapshot["checks"])

        projection = reducer.build_projection(
            snapshot,
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result={
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:128:1",
                "observed_at": "2026-09-19T16:41:14Z",
            },
        )

        self.assertEqual(["fast"], projection["checks"]["ambiguous"])
        self.assertEqual(
            "RECONCILE_PROVIDER_CHECKS",
            projection["next_permitted_action"],
        )

    def test_check_projection_orders_by_observed_at_not_provider_native_id(
        self,
    ) -> None:
        reducer = _reducer()
        snapshot = _snapshot()
        snapshot["checks"] = [
            {
                "id": "z-earlier-provider-id",
                "key": "provider-check:fast",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:40:00Z",
                "status": "completed",
                "conclusion": "failure",
            },
            {
                "id": "a-later-provider-id",
                "key": "provider-check:fast",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "success",
            },
        ]
        snapshot["coverage"]["checks"]["count"] = len(snapshot["checks"])

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
                "execution_id": "github-actions:125:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )

        self.assertEqual([], projection["checks"]["pending"])
        self.assertEqual([], projection["checks"]["non_success"])

    def test_provider_observation_cut_cannot_precede_collected_evidence(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        with mock.patch.object(
            adapter,
            "_now",
            side_effect=[
                "2026-09-19T16:40:10Z",
                "2026-09-19T16:40:20Z",
                "2026-09-19T16:40:30Z",
                "2026-09-19T16:40:40Z",
            ],
        ):
            snapshot = adapter.collect_snapshot(
                _PagedFake(_complete_replies(root)),
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:40:00Z",
            )

        self.assertEqual("2026-09-19T16:40:20Z", snapshot["observed_at"])
        self.assertEqual(
            "2026-09-19T16:40:40Z",
            snapshot["collection"]["confirming_read_completed_at"],
        )

    def test_deleted_commenter_is_unavailable_not_provider_failure(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = _complete_replies(root)
        replies[f"{root}/issues/300/comments?per_page=100"] = (
            [
                {
                    "id": 1,
                    "user": None,
                    "created_at": "2026-09-19T16:40:00Z",
                    "updated_at": "2026-09-19T16:40:00Z",
                    "body": "historical comment",
                }
            ],
            {},
        )

        snapshot = adapter.collect_snapshot(
            _PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        self.assertEqual("COMPLETE", snapshot["coverage"]["conversation"]["status"])
        self.assertEqual("UNAVAILABLE", snapshot["conversation"][0]["author"])

    def test_deleted_review_actor_marks_review_coverage_partial_but_keeps_threads_complete(
        self,
    ) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = _complete_replies(root)
        replies[f"{root}/pulls/300/reviews?per_page=100"][0][0]["user"] = None
        replies[f"{root}/pulls/300/reviews?per_page=100"][0][0]["state"] = (
            "CHANGES_REQUESTED"
        )
        replies[f"{root}/pulls/300/comments?per_page=100"][0][0]["user"] = None

        snapshot = adapter.collect_snapshot(
            _PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        fallback = "github-unavailable-reviewer:10"
        self.assertEqual("PARTIAL", snapshot["coverage"]["reviews"]["status"])
        self.assertEqual(
            "unavailable_reviewer_identity",
            snapshot["coverage"]["reviews"]["reason"],
        )
        self.assertEqual(
            1,
            snapshot["coverage"]["reviews"]["unavailable_opinionated_reviews"],
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["review_threads"]["status"])
        self.assertEqual(fallback, snapshot["reviews"][0]["reviewer_id"])
        self.assertFalse(snapshot["reviews"][0]["effective"])
        review_input = _reducer().build_review_input(snapshot, _bundle())
        self.assertNotIn(
            "github-review-10",
            {
                item["observation_id"]
                for item in review_input["evidence_set"]["observations"]
            },
        )
        first_threads = [
            item
            for item in snapshot["review_threads"]
            if item["review_observation_id"] == "github-review-10"
        ]
        self.assertEqual(1, len(first_threads))
        self.assertEqual(fallback, first_threads[0]["reviewer_id"])

    def test_missing_review_identity_stays_fail_closed(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = _complete_replies(root)
        replies[f"{root}/pulls/300/comments?per_page=100"][0][0][
            "pull_request_review_id"
        ] = None

        snapshot = adapter.collect_snapshot(
            _PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        self.assertNotEqual(
            "COMPLETE",
            snapshot["coverage"]["review_threads"]["status"],
        )

    def test_adapter_follows_pagination_and_marks_each_source_complete(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        fake = _PagedFake(_complete_replies(root))

        snapshot = adapter.collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        for source, payload_key, expected_pages in (
            ("conversation", "conversation", 2),
            ("reviews", "reviews", 2),
            ("checks", "checks", 3),
        ):
            with self.subTest(source=source):
                self.assertEqual(2, len(snapshot[payload_key]))
                self.assertEqual(
                    expected_pages,
                    snapshot["coverage"][source]["pages"],
                )
                self.assertEqual(2, snapshot["coverage"][source]["count"])
                self.assertEqual("COMPLETE", snapshot["coverage"][source]["status"])

        self.assertEqual(2, len(snapshot["review_threads"]))
        self.assertEqual(2, snapshot["coverage"]["review_threads"]["pages"])
        self.assertEqual(2, snapshot["coverage"]["review_threads"]["count"])
        self.assertEqual(
            "COMPLETE",
            snapshot["coverage"]["review_threads"]["status"],
        )
        self.assertEqual(
            ["resolved", "resolved"],
            [item["state"] for item in snapshot["review_threads"]],
        )

    def test_pending_github_review_is_omitted_and_marks_coverage_partial(
        self,
    ) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = _complete_replies(root)
        replies[f"{root}/pulls/300/reviews?per_page=100"] = (
            [
                {
                    "id": 10,
                    "user": {"login": "submitted"},
                    "state": "APPROVED",
                    "submitted_at": "2026-09-19T16:40:02Z",
                    "commit_id": "a" * 40,
                    "html_url": "https://example.invalid/review/10",
                },
                {
                    "id": 12,
                    "user": {"login": "pending"},
                    "state": "PENDING",
                    "submitted_at": None,
                    "commit_id": "a" * 40,
                    "html_url": "https://example.invalid/review/12",
                },
            ],
            {},
        )

        snapshot = adapter.collect_snapshot(
            _PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        self.assertEqual(1, len(snapshot["reviews"]))
        self.assertEqual(
            "github-review-10",
            snapshot["reviews"][0]["observation_id"],
        )
        self.assertEqual("PARTIAL", snapshot["coverage"]["reviews"]["status"])
        self.assertEqual(1, snapshot["coverage"]["reviews"]["omitted"])
        self.assertEqual(
            "unsubmitted_provider_items",
            snapshot["coverage"]["reviews"]["reason"],
        )

    def test_adapter_reports_partial_collection_for_each_source_page_error(
        self,
    ) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        cases = {
            "conversation": "https://api.github.com/page2/issues",
            "reviews": "https://api.github.com/page2/reviews",
            "review_threads": "https://api.github.com/page2/review-comments",
            "checks": "https://api.github.com/page2/check-runs",
        }

        class PartialFake(_PagedFake):
            def __init__(
                self,
                replies: dict[str, tuple[Any, dict[str, str]]],
                failing_url: str,
            ) -> None:
                super().__init__(replies)
                self.failing_url = failing_url

            def get(self, url: str) -> tuple[Any, dict[str, str]]:
                if url == self.failing_url:
                    raise adapter.ProviderReadError("simulated second-page failure")
                return super().get(url)

        for source, fail_url in cases.items():
            snapshot = adapter.collect_snapshot(
                PartialFake(_complete_replies(root), fail_url),
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:41:00Z",
            )
            with self.subTest(source=source):
                self.assertEqual("PARTIAL", snapshot["coverage"][source]["status"])
                expected_pages = 2 if source == "checks" else 1
                self.assertEqual(
                    expected_pages,
                    snapshot["coverage"][source]["pages"],
                )
                self.assertEqual(1, snapshot["coverage"][source]["count"])
                self.assertEqual(1, len(snapshot[source]))

    def test_publication_refuses_stale_head_and_later_same_head_projection(
        self,
    ) -> None:
        adapter = _adapter()
        candidate = {
            "subject": {
                "provider_id": "github",
                "repository": "https://github.com/ktogias/gnostoa",
                "change_request": {"kind": "github-pull-request", "id": "300"},
                "head_commit": "a" * 40,
                "base_commit": "b" * 40,
                "merge_base_commit": "c" * 40,
                "state": "open",
            },
            "observation": {
                "observed_at": "2026-09-19T16:41:00Z",
                "execution_id": "github-actions:100:1",
            },
        }
        allowed, reason = adapter.publication_decision(
            repository="ktogias/gnostoa",
            pull_number=300,
            current_pr={
                "state": "open",
                "head_sha": "b" * 40,
                "base_sha": "b" * 40,
                "merge_base_sha": "c" * 40,
            },
            collected_head="a" * 40,
            existing_projection=None,
            candidate_projection=candidate,
        )
        self.assertFalse(allowed)
        self.assertEqual("STALE_HEAD", reason)

        existing = {
            "subject": {
                "provider_id": "github",
                "repository": "https://github.com/ktogias/gnostoa",
                "change_request": {"kind": "github-pull-request", "id": "300"},
                "head_commit": "a" * 40,
            },
            "observation": {
                "observed_at": "2026-09-19T16:42:00Z",
                "execution_id": "github-actions:101:1",
            },
        }
        allowed, reason = adapter.publication_decision(
            repository="ktogias/gnostoa",
            pull_number=300,
            current_pr={
                "state": "open",
                "head_sha": "a" * 40,
                "base_sha": "b" * 40,
                "merge_base_sha": "c" * 40,
            },
            collected_head="a" * 40,
            existing_projection=existing,
            candidate_projection=candidate,
        )
        self.assertFalse(allowed)
        self.assertEqual("SUPERSEDED_PROJECTION", reason)

    def test_publication_refuses_same_head_projection_for_wrong_subject(
        self,
    ) -> None:
        adapter = _adapter()
        base_subject = {
            "provider_id": "github",
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "github-pull-request", "id": "300"},
            "head_commit": "a" * 40,
            "base_commit": "b" * 40,
            "merge_base_commit": "c" * 40,
            "state": "open",
        }
        for mutation in ("provider", "repository", "pull"):
            subject = dict(base_subject)
            subject["change_request"] = dict(base_subject["change_request"])
            if mutation == "provider":
                subject["provider_id"] = "gitlab"
            elif mutation == "repository":
                subject["repository"] = "https://github.com/ktogias/other"
            else:
                subject["change_request"]["id"] = "301"
            candidate = {
                "subject": subject,
                "observation": {
                    "observed_at": "2026-09-19T16:41:00Z",
                    "execution_id": "github-actions:102:1",
                },
            }
            allowed, reason = adapter.publication_decision(
                repository="ktogias/gnostoa",
                pull_number=300,
                current_pr={"state": "open", "head_sha": "a" * 40},
                collected_head="a" * 40,
                existing_projection=None,
                candidate_projection=candidate,
            )
            with self.subTest(mutation=mutation):
                self.assertFalse(allowed)
                self.assertEqual("CANDIDATE_SUBJECT_MISMATCH", reason)

    def test_publication_refuses_same_head_when_base_or_merge_base_changes(
        self,
    ) -> None:
        adapter = _adapter()
        candidate = {
            "subject": {
                "provider_id": "github",
                "repository": "https://github.com/ktogias/gnostoa",
                "change_request": {"kind": "github-pull-request", "id": "300"},
                "head_commit": "a" * 40,
                "base_commit": "b" * 40,
                "merge_base_commit": "c" * 40,
                "state": "open",
            },
            "observation": {
                "observed_at": "2026-09-19T16:41:00Z",
                "execution_id": "github-actions:103:1",
            },
        }

        for mutation in ("base", "merge_base"):
            current = {
                "state": "open",
                "head_sha": "a" * 40,
                "base_sha": "b" * 40,
                "merge_base_sha": "c" * 40,
            }
            if mutation == "base":
                current["base_sha"] = "d" * 40
            else:
                current["merge_base_sha"] = "e" * 40

            allowed, reason = adapter.publication_decision(
                repository="ktogias/gnostoa",
                pull_number=300,
                current_pr=current,
                collected_head="a" * 40,
                existing_projection=None,
                candidate_projection=candidate,
            )
            with self.subTest(mutation=mutation):
                self.assertFalse(allowed)
                self.assertEqual("STALE_COMPARISON", reason)

    def test_current_pr_recomputes_merge_base_for_prewrite_subject(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        fake = _PagedFake(_complete_replies(root))

        # skipcq: PYL-W0212 -- intentional white-box L1 test
        current = adapter._current_pr(fake, "ktogias/gnostoa", 300)

        self.assertEqual(
            {
                "state": "open",
                "head_sha": "a" * 40,
                "base_sha": "b" * 40,
                "merge_base_sha": "c" * 40,
            },
            current,
        )
        self.assertIn(
            f"{root}/compare/{'b' * 40}...{'a' * 40}",
            fake.calls,
        )

    def test_scheduled_population_is_fully_enumerated_before_batch_selection(
        self,
    ) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        pulls = [
            {
                "number": number,
                "state": "open",
                "html_url": f"https://github.com/ktogias/gnostoa/pull/{number}",
                "head": {"sha": f"{number:040x}"[-40:]},
                "base": {"sha": "b" * 40},
            }
            for number in range(1, 12)
        ]
        fake = _PagedFake(
            {
                f"{root}/pulls?state=open&per_page=100": (pulls, {}),
            }
        )

        self.assertEqual(
            list(range(1, 12)),
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            adapter._open_pull_numbers(fake, "ktogias/gnostoa"),
        )

    def test_duplicate_projection_comments_fail_closed(self) -> None:
        adapter = _adapter()
        reducer = _reducer()
        snapshot = _snapshot()

        first = reducer.build_projection(
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
                "execution_id": "github-actions:130:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        second = reducer.build_projection(
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
                "execution_id": "github-actions:131:1",
                "observed_at": "2026-09-19T16:42:10Z",
            },
        )

        comments = [
            {
                "id": 1,
                "author": "github-actions[bot]",
                "body": reducer.render_projection(first),
            },
            {
                "id": 2,
                "author": "github-actions[bot]",
                "body": reducer.render_projection(second),
            },
        ]
        with self.assertRaisesRegex(
            adapter.ProviderWriteError,
            "multiple valid owned L1 projection comments",
        ):
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            adapter._existing_projection(
                comments,
                repository="ktogias/gnostoa",
                pull_number=300,
            )

    def test_projection_ownership_ignores_forged_or_wrong_subject_comments(
        self,
    ) -> None:
        adapter = _adapter()
        reducer = _reducer()

        legitimate = reducer.build_projection(
            _snapshot(),
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
                "execution_id": "github-actions:135:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        forged_later = reducer.build_projection(
            _snapshot(),
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result={
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:136:1",
                "observed_at": "2026-09-19T16:42:10Z",
            },
        )
        wrong_subject = reducer.build_projection(
            _snapshot(change_id="999"),
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
                "execution_id": "github-actions:137:1",
                "observed_at": "2026-09-19T16:43:10Z",
            },
        )

        # skipcq: PYL-W0212 -- intentional white-box L1 test
        existing = adapter._existing_projection(
            [
                {
                    "id": 1,
                    "author": "github-actions[bot]",
                    "body": reducer.render_projection(legitimate),
                },
                {
                    "id": 2,
                    "author": "mallory",
                    "body": reducer.render_projection(forged_later),
                },
                {
                    "id": 3,
                    "author": "github-actions[bot]",
                    "body": reducer.render_projection(wrong_subject),
                },
            ],
            repository="ktogias/gnostoa",
            pull_number=300,
        )

        self.assertIsNotNone(existing)
        self.assertEqual(1, existing[0])

    def test_semantic_execution_uses_same_acquired_protected_consumer(self) -> None:
        adapter = _adapter()
        reducer = _reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        bundle = SimpleNamespace(
            protected_main_revision="e" * 40,
            document=_bundle(),
        )
        consumer = SimpleNamespace(
            protected_main_revision="e" * 40,
            document=_consumer_document(),
        )

        def run_bound(
            input_document: object,
            *,
            acquire_consumer: Any,
        ) -> tuple[int, bytes]:
            self.assertIs(consumer, acquire_consumer())
            self.assertIsInstance(input_document, dict)
            return _valid_incomplete_result(input_document)

        with (
            mock.patch.object(
                adapter,
                "_protected_state",
                return_value=(bundle, consumer),
            ),
            mock.patch(
                "tools.review_outer._run_prior_effective_current_advisory_with_acquisition",
                side_effect=run_bound,
            ) as runner,
        ):
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            entry = adapter._collect_entry(
                _PagedFake(_complete_replies_without_review_comments(root)),
                "ktogias/gnostoa",
                300,
                run_id=139,
                run_attempt=1,
            )

        runner.assert_called_once()
        projection = reducer.parse_projection_comment(entry["body"])
        self.assertIsInstance(projection, dict)
        self.assertEqual("e" * 40, projection["protected"]["main_revision"])
        self.assertEqual("INCOMPLETE", projection["r2a"]["outcome"])

    def test_protected_capability_unavailability_is_projected_not_fabricated(
        self,
    ) -> None:
        adapter = _adapter()
        reducer = _reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        fake = _PagedFake(_complete_replies_without_review_comments(root))

        with mock.patch.object(
            adapter,
            "_protected_state",
            side_effect=adapter.ProviderReadError("protected state unavailable"),
        ):
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            entry = adapter._collect_entry(
                fake,
                "ktogias/gnostoa",
                300,
                run_id=140,
                run_attempt=1,
            )

        projection = reducer.parse_projection_comment(entry["body"])
        self.assertIsInstance(projection, dict)
        self.assertEqual("UNAVAILABLE", projection["protected"]["status"])
        self.assertIsNone(projection["protected"]["main_revision"])
        self.assertIsNone(projection["protected"]["outer_runtime_image"])
        self.assertEqual("UNAVAILABLE", projection["r2a"]["outcome"])
        self.assertIs(projection["r2a"]["binding"], False)
        self.assertEqual(
            "WAIT_FOR_PROTECTED_CAPABILITY",
            projection["next_permitted_action"],
        )

    def test_publication_payload_read_is_bounded_before_json_decode(self) -> None:
        adapter = _adapter()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.json"
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            path.write_bytes(b"x" * (adapter._MAX_PUBLICATION_PAYLOAD_BYTES + 1))
            with self.assertRaisesRegex(
                ValueError,
                "publication payload exceeds bounded size",
            ):
                # skipcq: PYL-W0212 -- intentional white-box L1 test
                adapter._load_payload(path)

    def test_workflow_run_preserves_all_associated_pull_requests(self) -> None:
        adapter = _adapter()
        payload = json.dumps(
            [
                {"number": 301},
                {"number": 302},
                {"number": 301},
            ]
        )
        self.assertEqual(
            [301, 302],
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            adapter._workflow_run_pull_numbers(payload),
        )
        # skipcq: PYL-W0212 -- intentional white-box L1 test
        self.assertEqual([], adapter._workflow_run_pull_numbers(""))
        # skipcq: PYL-W0212 -- intentional white-box L1 test
        self.assertEqual([], adapter._workflow_run_pull_numbers("null"))
        with self.assertRaisesRegex(
            adapter.ProviderReadError,
            "workflow_run.pull_requests",
        ):
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            adapter._workflow_run_pull_numbers(json.dumps([{"number": 0}]))

    def test_l1_has_separate_guardrail_from_historical_r2a_promotion(self) -> None:
        loaded = yaml.safe_load(GUARDRAILS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(loaded, dict)
        entries = loaded.get("guardrails")
        self.assertIsInstance(entries, list)
        # skipcq: PTC-W0063 -- explicit default prevents StopIteration
        l1 = next(
            (
                item
                for item in entries
                if isinstance(item, dict)
                and item.get("id") == "useful-l1-current-state-reconciliation"
            ),
            None,
        )
        self.assertIsInstance(l1, dict)
        self.assertIn("tools/review_reconcile.py", l1.get("implementation", []))
        self.assertIn(
            "ci/review_github_current_state.py",
            l1.get("implementation", []),
        )
        self.assertIn(
            ".github/workflows/review-current-state.yml",
            l1.get("implementation", []),
        )
        self.assertIn("tests/test_review_reconcile_l1.py", l1.get("tests", []))

        # skipcq: PTC-W0063 -- explicit default prevents StopIteration
        semantic = next(
            (
                item
                for item in entries
                if isinstance(item, dict)
                and item.get("id") == "semantic-review-assurance"
            ),
            None,
        )
        self.assertIsInstance(semantic, dict)
        self.assertNotIn(
            "ci/review_github_current_state.py",
            semantic.get("implementation", []),
        )
        self.assertNotIn(
            ".github/workflows/review-current-state.yml",
            semantic.get("implementation", []),
        )

    def test_workflow_is_protected_source_and_least_privilege(self) -> None:
        self.assertTrue(WORKFLOW_PATH.is_file(), "L1_WORKFLOW_UNAVAILABLE")
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = yaml.safe_load(text)

        self.assertIsInstance(workflow, dict)
        self.assertIn("workflow_run:", text)
        self.assertIn("repository_dispatch:", text)
        self.assertNotIn("workflow_dispatch:", text)
        self.assertIn("schedule:", text)
        self.assertNotIn("workflow_run.pull_requests[0]", text)
        self.assertNotIn("workflow_run.pull_requests[0]", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertNotIn("PAYLOAD_B64", text)
        self.assertNotIn("needs.collect.outputs.payload", text)
        self.assertNotIn("base64", text)
        self.assertNotIn("GITHUB_OUTPUT", text)
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            text,
        )
        self.assertIn(
            "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0",
            text,
        )
        self.assertIn("retention-days: 1", text)
        self.assertEqual({}, workflow.get("permissions"))

        concurrency = workflow.get("concurrency")
        self.assertIsInstance(concurrency, dict)
        self.assertEqual("gnostoa-review-current-state", concurrency.get("group"))
        self.assertIs(False, concurrency.get("cancel-in-progress"))
        self.assertNotIn("pull_requests[0]", text)
        self.assertIn(
            "toJSON(github.event.workflow_run.pull_requests)",
            text,
        )
        self.assertIn("--workflow-run-pulls-json", text)

        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        collect = jobs.get("collect")
        publish = jobs.get("publish")
        self.assertIsInstance(collect, dict)
        self.assertIsInstance(publish, dict)
        self.assertNotIn("outputs", collect)

        collect_steps = collect.get("steps")
        publish_steps = publish.get("steps")
        self.assertIsInstance(collect_steps, list)
        self.assertIsInstance(publish_steps, list)
        # skipcq: PTC-W0063 -- explicit default prevents StopIteration
        upload = next(
            (
                item
                for item in collect_steps
                if isinstance(item, dict)
                and str(item.get("uses", "")).startswith("actions/upload-artifact@")
            ),
            None,
        )
        self.assertIsInstance(upload, dict)
        # skipcq: PTC-W0063 -- explicit default prevents StopIteration
        download = next(
            (
                item
                for item in publish_steps
                if isinstance(item, dict)
                and str(item.get("uses", "")).startswith("actions/download-artifact@")
            ),
            None,
        )
        self.assertIsInstance(download, dict)
        self.assertEqual(1, upload.get("with", {}).get("retention-days"))
        self.assertEqual(
            "gnostoa-l1-publication",
            upload.get("with", {}).get("name"),
        )
        self.assertEqual(
            "gnostoa-l1-publication",
            download.get("with", {}).get("name"),
        )

        self.assertEqual(
            {
                "contents": "read",
                "checks": "read",
                "statuses": "read",
                "pull-requests": "read",
                "issues": "read",
            },
            collect.get("permissions"),
        )
        self.assertEqual(
            {
                "contents": "read",
                "pull-requests": "write",
                "issues": "read",
            },
            publish.get("permissions"),
        )

        for job in (collect, publish):
            condition = str(job.get("if", ""))
            self.assertIn("github.ref == 'refs/heads/main'", condition)
            steps = job.get("steps")
            self.assertIsInstance(steps, list)
            # skipcq: PTC-W0063 -- explicit default prevents StopIteration
            checkout = next(
                (
                    item
                    for item in steps
                    if isinstance(item, dict)
                    and str(item.get("uses", "")).startswith("actions/checkout@")
                ),
                None,
            )
            self.assertIsInstance(checkout, dict)
            checkout_with = checkout.get("with")
            self.assertIsInstance(checkout_with, dict)
            self.assertEqual("main", checkout_with.get("ref"))
            self.assertIs(False, checkout_with.get("persist-credentials"))

        self.assertIn("ci/review_github_current_state.py", text)


class UsefulL1IdentityCollisionTests(unittest.TestCase):
    def test_provider_review_id_may_equal_legacy_thread_evidence_id(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()

        self.assertGreaterEqual(len(snapshot["reviews"]), 2)
        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_thread_id = f"gnostoa-thread-evidence::{origin_id}"
        snapshot["reviews"][1]["observation_id"] = legacy_thread_id

        review_input = reducer.build_review_input(snapshot, _bundle())
        observations = review_input["evidence_set"]["observations"]
        observation_ids = {item["observation_id"] for item in observations}

        self.assertIn(origin_id, observation_ids)
        self.assertIn(legacy_thread_id, observation_ids)

        thread_only = [
            item
            for item in observations
            if item["native"].get("thread_evidence_only") is True
        ]
        self.assertEqual(1, len(thread_only))
        self.assertNotEqual(legacy_thread_id, thread_only[0]["observation_id"])
        self.assertEqual(
            origin_id,
            thread_only[0]["native"]["origin_review_observation_id"],
        )

    def test_non_colliding_thread_evidence_id_keeps_legacy_identity(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()

        origin_id = snapshot["reviews"][0]["observation_id"]
        review_input = reducer.build_review_input(snapshot, _bundle())
        thread_only = [
            item
            for item in review_input["evidence_set"]["observations"]
            if item["native"].get("thread_evidence_only") is True
        ]

        self.assertEqual(1, len(thread_only))
        self.assertEqual(
            f"gnostoa-thread-evidence::{origin_id}",
            thread_only[0]["observation_id"],
        )

    def test_ineffective_review_id_does_not_displace_legacy_thread_evidence_id(
        self,
    ) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()

        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_thread_id = f"gnostoa-thread-evidence::{origin_id}"
        snapshot["reviews"][1]["observation_id"] = legacy_thread_id
        snapshot["reviews"][1]["effective"] = False

        review_input = reducer.build_review_input(snapshot, _bundle())
        observations = review_input["evidence_set"]["observations"]
        thread_only = [
            item
            for item in observations
            if item["native"].get("thread_evidence_only") is True
        ]

        self.assertEqual(1, len(thread_only))
        self.assertEqual(legacy_thread_id, thread_only[0]["observation_id"])
        self.assertFalse(
            any(
                item["observation_id"] == legacy_thread_id
                and item["native"].get("thread_evidence_only") is not True
                for item in observations
            )
        )

    def test_collision_fallback_identity_is_bounded_for_large_provider_id(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()

        large_origin_id = "x" * 16_384
        snapshot["reviews"][0]["observation_id"] = large_origin_id
        snapshot["review_threads"][0]["review_observation_id"] = large_origin_id
        snapshot["reviews"][1]["observation_id"] = (
            f"gnostoa-thread-evidence::{large_origin_id}"
        )

        review_input = reducer.build_review_input(snapshot, _bundle())
        thread_only = [
            item
            for item in review_input["evidence_set"]["observations"]
            if item["native"].get("thread_evidence_only") is True
        ]

        self.assertEqual(1, len(thread_only))
        fallback_id = thread_only[0]["observation_id"]
        expected_fallback = (
            "gnostoa-thread-evidence:v2:sha256:"
            + hashlib.sha256(large_origin_id.encode("utf-8")).hexdigest()
        )
        self.assertEqual(expected_fallback, fallback_id)
        self.assertLessEqual(len(fallback_id.encode("utf-8")), 128)
        self.assertEqual(
            large_origin_id,
            thread_only[0]["native"]["origin_review_observation_id"],
        )

    def test_fallback_probes_past_a_second_provider_collision(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()

        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_thread_id = f"gnostoa-thread-evidence::{origin_id}"
        origin_digest = hashlib.sha256(origin_id.encode("utf-8")).hexdigest()
        first_fallback = f"gnostoa-thread-evidence:v2:sha256:{origin_digest}"

        snapshot["reviews"][1]["observation_id"] = legacy_thread_id
        snapshot["reviews"].append(
            {
                "observation_id": first_fallback,
                "reviewer_id": "collision-fixture",
                "recommendation_state": "COMMENTED",
                "observed_at": "2026-09-19T16:39:00Z",
                "head_commit": "d" * 40,
                "source_url": snapshot["subject"]["source_url"] + "#collision-fixture",
            }
        )
        snapshot["coverage"]["reviews"]["count"] = 3

        review_input = reducer.build_review_input(snapshot, _bundle())
        observations = review_input["evidence_set"]["observations"]
        thread_only = [
            item
            for item in observations
            if item["native"].get("thread_evidence_only") is True
        ]

        self.assertEqual(1, len(thread_only))
        second_fallback = f"{first_fallback}:p{1:016x}"
        self.assertEqual(second_fallback, thread_only[0]["observation_id"])
        self.assertLessEqual(len(second_fallback.encode("utf-8")), 128)
        self.assertIn(
            first_fallback,
            {item["observation_id"] for item in observations},
        )

    def test_probe_cardinality_boundary_checks_available_candidate(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()
        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_id = f"gnostoa-thread-evidence::{origin_id}"
        origin_digest = hashlib.sha256(origin_id.encode("utf-8")).hexdigest()
        stem = f"gnostoa-thread-evidence:v2:sha256:{origin_digest}"
        probes = [f"{stem}:p{probe:016x}" for probe in range(1, 4)]

        snapshot["reviews"][1]["observation_id"] = legacy_id
        for index, observation_id in enumerate([stem, *probes[:2]], start=1):
            snapshot["reviews"].append(
                {
                    "observation_id": observation_id,
                    "reviewer_id": f"boundary-collision-{index}",
                    "recommendation_state": "COMMENTED",
                    "observed_at": "2026-09-19T16:39:00Z",
                    "head_commit": "d" * 40,
                    "source_url": (
                        snapshot["subject"]["source_url"]
                        + f"#boundary-collision-{index}"
                    ),
                }
            )
        snapshot["coverage"]["reviews"]["count"] = len(snapshot["reviews"])

        with mock.patch.object(reducer, "_THREAD_EVIDENCE_MAX_PROBE", 3):
            review_input = reducer.build_review_input(snapshot, _bundle())

        thread_only = [
            item
            for item in review_input["evidence_set"]["observations"]
            if item["native"].get("thread_evidence_only") is True
        ]
        self.assertEqual(1, len(thread_only))
        self.assertEqual(probes[2], thread_only[0]["observation_id"])

    def test_probe_space_exhaustion_fails_closed(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()
        origin_id = snapshot["reviews"][0]["observation_id"]
        legacy_id = f"gnostoa-thread-evidence::{origin_id}"
        origin_digest = hashlib.sha256(origin_id.encode("utf-8")).hexdigest()
        stem = f"gnostoa-thread-evidence:v2:sha256:{origin_digest}"
        probes = [f"{stem}:p{probe:016x}" for probe in range(1, 4)]

        snapshot["reviews"][1]["observation_id"] = legacy_id
        for index, observation_id in enumerate([stem, *probes], start=1):
            snapshot["reviews"].append(
                {
                    "observation_id": observation_id,
                    "reviewer_id": f"exhaustion-collision-{index}",
                    "recommendation_state": "COMMENTED",
                    "observed_at": "2026-09-19T16:39:00Z",
                    "head_commit": "d" * 40,
                    "source_url": (
                        snapshot["subject"]["source_url"]
                        + f"#exhaustion-collision-{index}"
                    ),
                }
            )
        snapshot["coverage"]["reviews"]["count"] = len(snapshot["reviews"])

        with (
            mock.patch.object(
                reducer,
                "_THREAD_EVIDENCE_MAX_PROBE",
                3,
            ),
            self.assertRaisesRegex(
                reducer.ReconciliationInputError,
                "unable to allocate a collision-free thread evidence observation ID",
            ),
        ):
            reducer.build_review_input(snapshot, _bundle())

    def test_collision_fallback_is_independent_of_provider_review_order(self) -> None:
        reducer = reducer_fixture()

        def thread_id(reverse: bool) -> str:
            snapshot = snapshot_fixture()
            origin_id = snapshot["reviews"][0]["observation_id"]
            snapshot["reviews"][1]["observation_id"] = (
                f"gnostoa-thread-evidence::{origin_id}"
            )
            if reverse:
                snapshot["reviews"].reverse()
            review_input = reducer.build_review_input(
                snapshot,
                _bundle(),
            )
            thread_only = [
                item
                for item in review_input["evidence_set"]["observations"]
                if item["native"].get("thread_evidence_only") is True
            ]
            self.assertEqual(1, len(thread_only))
            return thread_only[0]["observation_id"]

        self.assertEqual(thread_id(False), thread_id(True))

    def test_collision_fallback_remains_valid_r2a_input(self) -> None:
        reducer = reducer_fixture()
        snapshot = snapshot_fixture()

        self.assertGreaterEqual(len(snapshot["reviews"]), 2)
        origin_id = snapshot["reviews"][0]["observation_id"]
        snapshot["reviews"][1]["observation_id"] = (
            f"gnostoa-thread-evidence::{origin_id}"
        )
        review_input = reducer.build_review_input(snapshot, _bundle())

        schema_path = ROOT / "schemas" / "review-check-input.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(review_input)


if __name__ == "__main__":
    unittest.main()
