from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "ci" / "review_github_current_state.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "review-current-state.yml"
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"


def _reducer() -> ModuleType:
    spec = importlib.util.find_spec("tools.review_reconcile")
    if spec is None:
        raise AssertionError("L1_REDUCER_UNAVAILABLE")
    return importlib.import_module("tools.review_reconcile")


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


def _bundle() -> dict[str, Any]:
    path = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("protected authority fixture must be an object")
    return loaded


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
            }
        ],
        "checks": [
            {
                "id": "provider-check-00000000000000000030",
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
    }


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
        self.assertEqual(2, len(observations))
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
                "run_id": 124,
                "run_attempt": 1,
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
                "run_id": 123,
                "run_attempt": 1,
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        rendered = reducer.render_projection(projection)

        self.assertIn("INCOMPLETE", rendered)
        self.assertIn("QUORUM_UNMET", rendered)
        self.assertEqual("draft", projection["status"])
        self.assertIn("binding: false", rendered)
        self.assertIn("Intent summary: Useful L1 fixture", rendered)
        self.assertNotIn("raw provider text", rendered)
        self.assertNotIn("inline raw finding", rendered)
        self.assertLess(len(rendered.encode("utf-8")), 32_768)

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
                    "run_id": 126,
                    "run_attempt": 1,
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
                "run_id": 127,
                "run_attempt": 1,
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
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "success",
            },
            {
                "id": "provider-z",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "failure",
            },
        ]

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
                "run_id": 128,
                "run_attempt": 1,
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
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:40:00Z",
                "status": "completed",
                "conclusion": "failure",
            },
            {
                "id": "a-later-provider-id",
                "name": "fast",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "success",
            },
        ]

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
                "run_id": 125,
                "run_attempt": 1,
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )

        self.assertEqual([], projection["checks"]["pending"])
        self.assertEqual([], projection["checks"]["non_success"])

    def test_provider_observation_cut_cannot_precede_collected_evidence(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        snapshot = adapter.collect_snapshot(
            _PagedFake(_complete_replies(root)),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:40:00Z",
        )

        self.assertEqual("2026-09-19T16:40:09Z", snapshot["observed_at"])

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

        for source, payload_key in (
            ("conversation", "conversation"),
            ("reviews", "reviews"),
            ("review_threads", "review_threads"),
            ("checks", "checks"),
        ):
            with self.subTest(source=source):
                self.assertEqual(2, len(snapshot[payload_key]))
                self.assertEqual(2, snapshot["coverage"][source]["pages"])
                self.assertEqual(2, snapshot["coverage"][source]["count"])
                self.assertEqual("COMPLETE", snapshot["coverage"][source]["status"])

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
                self.assertEqual(1, snapshot["coverage"][source]["pages"])
                self.assertEqual(1, snapshot["coverage"][source]["count"])
                self.assertEqual(1, len(snapshot[source]))

    def test_publication_refuses_stale_head_and_later_same_head_projection(
        self,
    ) -> None:
        adapter = _adapter()
        candidate = {
            "subject": {"head_commit": "a" * 40, "state": "open"},
            "observation": {
                "observed_at": "2026-09-19T16:41:00Z",
                "run_id": 100,
                "run_attempt": 1,
            },
        }
        allowed, reason = adapter.publication_decision(
            current_pr={"state": "open", "head_sha": "b" * 40},
            collected_head="a" * 40,
            existing_projection=None,
            candidate_projection=candidate,
        )
        self.assertFalse(allowed)
        self.assertEqual("STALE_HEAD", reason)

        existing = {
            "subject": {"head_commit": "a" * 40},
            "observation": {
                "observed_at": "2026-09-19T16:42:00Z",
                "run_id": 101,
                "run_attempt": 1,
            },
        }
        allowed, reason = adapter.publication_decision(
            current_pr={"state": "open", "head_sha": "a" * 40},
            collected_head="a" * 40,
            existing_projection=existing,
            candidate_projection=candidate,
        )
        self.assertFalse(allowed)
        self.assertEqual("SUPERSEDED_PROJECTION", reason)

    def test_scheduled_population_refuses_silent_open_pr_truncation(self) -> None:
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

        with self.assertRaisesRegex(
            adapter.ProviderReadError,
            "exceeds the bounded reconciliation capacity",
        ):
            adapter._open_pull_numbers(fake, "ktogias/gnostoa")

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
                "run_id": 130,
                "run_attempt": 1,
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
                "run_id": 131,
                "run_attempt": 1,
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
                "run_id": 135,
                "run_attempt": 1,
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
                "run_id": 136,
                "run_attempt": 1,
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
                "run_id": 137,
                "run_attempt": 1,
                "observed_at": "2026-09-19T16:43:10Z",
            },
        )

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
            document={
                "acquired_consumer": {
                    "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                    "runtime_revision": "9" * 40,
                }
            },
        )

        def run_bound(
            input_document: object,
            *,
            acquire_consumer: Any,
        ) -> tuple[int, bytes]:
            self.assertIs(consumer, acquire_consumer())
            self.assertIsInstance(input_document, dict)
            return (
                0,
                b'{"binding":false,"outcome":"INCOMPLETE","reason":"QUORUM_UNMET"}',
            )

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
            entry = adapter._collect_entry(
                _PagedFake(_complete_replies(root)),
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
        fake = _PagedFake(_complete_replies(root))

        with mock.patch.object(
            adapter,
            "_protected_state",
            side_effect=adapter.ProviderReadError("protected state unavailable"),
        ):
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
            path.write_bytes(b"x" * (adapter._MAX_PUBLICATION_PAYLOAD_BYTES + 1))
            with self.assertRaisesRegex(
                ValueError,
                "publication payload exceeds bounded size",
            ):
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
            adapter._workflow_run_pull_numbers(payload),
        )
        self.assertEqual([], adapter._workflow_run_pull_numbers(""))
        self.assertEqual([], adapter._workflow_run_pull_numbers("null"))
        with self.assertRaisesRegex(
            adapter.ProviderReadError,
            "workflow_run.pull_requests",
        ):
            adapter._workflow_run_pull_numbers(json.dumps([{"number": 0}]))

    def test_l1_has_separate_guardrail_from_historical_r2a_promotion(self) -> None:
        loaded = yaml.safe_load(GUARDRAILS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(loaded, dict)
        entries = loaded.get("guardrails")
        self.assertIsInstance(entries, list)
        l1 = next(
            item
            for item in entries
            if isinstance(item, dict)
            and item.get("id") == "useful-l1-current-state-reconciliation"
        )
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

        semantic = next(
            item
            for item in entries
            if isinstance(item, dict) and item.get("id") == "semantic-review-assurance"
        )
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
        self.assertIn("300_000", text)
        self.assertNotIn("600_000", text)
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

        self.assertEqual(
            {
                "contents": "read",
                "checks": "read",
                "pull-requests": "read",
                "issues": "read",
            },
            collect.get("permissions"),
        )
        self.assertEqual(
            {
                "contents": "read",
                "pull-requests": "read",
                "issues": "write",
            },
            publish.get("permissions"),
        )

        for job in (collect, publish):
            condition = str(job.get("if", ""))
            self.assertIn("github.ref == 'refs/heads/main'", condition)
            steps = job.get("steps")
            self.assertIsInstance(steps, list)
            checkout = next(
                item
                for item in steps
                if isinstance(item, dict)
                and str(item.get("uses", "")).startswith("actions/checkout@")
            )
            checkout_with = checkout.get("with")
            self.assertIsInstance(checkout_with, dict)
            self.assertEqual("main", checkout_with.get("ref"))
            self.assertIs(False, checkout_with.get("persist-credentials"))

        self.assertIn("ci/review_github_current_state.py", text)


if __name__ == "__main__":
    unittest.main()
