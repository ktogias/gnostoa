from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest import mock

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from tests.review_reconcile_l1_support import (
    GUARDRAILS_PATH,
    ROOT,
    reducer_fixture,
    snapshot_fixture,
)
from tests.review_reconcile_l1_support import (
    PagedFake as _PagedFake,
)
from tests.review_reconcile_l1_support import (
    adapter as _adapter,
)
from tests.review_reconcile_l1_support import (
    bundle as _bundle,
)
from tests.review_reconcile_l1_support import (
    complete_replies as _complete_replies,
)
from tests.review_reconcile_l1_support import (
    complete_replies_without_review_comments as _complete_replies_without_review_comments,
)
from tests.review_reconcile_l1_support import (
    reducer as _reducer,
)
from tests.review_reconcile_l1_support import (
    snapshot as _snapshot,
)
from tests.review_reconcile_l1_support import (
    valid_incomplete_result as _valid_incomplete_result,
)

WORKFLOW_PATH = ROOT / ".github" / "workflows" / "review-current-state.yml"


def _consumer_document() -> dict[str, Any]:
    path = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("protected consumer fixture must be an object")
    return loaded


def _run_adapter_main(
    adapter: ModuleType, client: Any, directory: Path, argv: list[str]
) -> int:
    """Run the adapter's command line against ``client``, its step summary kept in
    ``directory``."""
    with (
        mock.patch.object(adapter, "GitHubRestClient", return_value=client),
        mock.patch.dict(
            os.environ, {"GITHUB_STEP_SUMMARY": str(directory / "summary.md")}
        ),
    ):
        return int(adapter.main(argv))


def _collected_entry(
    adapter: ModuleType, client: Any, directory: Path, *, run_id: int
) -> dict[str, Any]:
    """The one entry the adapter's ``collect`` mode writes for Pull Request 300."""
    output = directory / "payload.json"
    code = _run_adapter_main(
        adapter,
        client,
        directory,
        [
            "--mode",
            "collect",
            "--repository",
            "ktogias/gnostoa",
            "--pull-number",
            "300",
            "--run-id",
            str(run_id),
            "--run-attempt",
            "1",
            "--output",
            str(output),
        ],
    )
    entries = json.loads(output.read_text(encoding="utf-8"))
    if code != 0 or not isinstance(entries, list) or len(entries) != 1:
        raise AssertionError(f"collect did not write one entry: {code} {entries!r}")
    entry = entries[0]
    if not isinstance(entry, dict) or entry.get("pull_number") != 300:
        raise AssertionError(f"collect wrote another entry: {entry!r}")
    if "body" not in entry:
        raise AssertionError(f"collect wrote no projection: {entry!r}")
    return entry


def _issue_comment(comment_id: int, author: str, body: str) -> dict[str, Any]:
    """One Pull Request conversation comment as GitHub's REST API returns it."""
    return {
        "id": comment_id,
        "user": {"login": author},
        "created_at": "2026-09-19T16:44:00Z",
        "updated_at": "2026-09-19T16:44:00Z",
        "body": body,
    }


def _publication_client(comments: list[dict[str, Any]]) -> Any:
    """A client for Pull Request 300 at its fixture subject whose conversation is
    exactly ``comments``, refusing any read it was not given."""
    root = "https://api.github.com/repos/ktogias/gnostoa"
    replies = _complete_replies(root)
    replies[f"{root}/issues/300/comments?per_page=100"] = (comments, {})
    replies.pop("https://api.github.com/page2/issues", None)
    return mock.Mock(get=_PagedFake(replies).get)


def _publication_entry(body: str) -> dict[str, Any]:
    """The collected entry for Pull Request 300 at its fixture head."""
    return {"pull_number": 300, "head_sha": "a" * 40, "body": body}


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
        base_subject: dict[str, Any] = {
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
        reducer = _reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        compare = f"{root}/compare/{'b' * 40}...{'a' * 40}"
        conversation = f"{root}/issues/300/comments?per_page=100"
        moved: tuple[Any, dict[str, str]] = (
            {"merge_base_commit": {"sha": "d" * 40}},
            {},
        )
        entry = _publication_entry(
            reducer.render_projection(
                reducer.build_projection(
                    _snapshot(),
                    protected_main_revision=None,
                    outer_consumer=None,
                    r2a_result={
                        "outcome": "INCOMPLETE",
                        "reason": "QUORUM_UNMET",
                        "binding": False,
                    },
                    execution={
                        "execution_id": "github-actions:150:1",
                        "observed_at": "2026-09-19T16:41:10Z",
                    },
                )
            )
        )

        def publish(moves: str | None) -> tuple[dict[str, Any], _PagedFake, Any]:
            """Publish the entry while the merge base moves when ``moves`` is read:
            at the first compare, or once the conversation has been read back."""
            fake = _PagedFake(_complete_replies(root))
            if moves == compare:
                fake.replies[compare] = moved

            def get(url: str) -> tuple[Any, dict[str, str]]:
                reply = fake.get(url)
                if moves == conversation and url == conversation:
                    fake.replies[compare] = moved
                return reply

            client = mock.Mock(get=get)
            result = adapter.publish_entry(
                client, repository="ktogias/gnostoa", entry=entry
            )
            return result, fake, client

        # The open state, head and base the Pull Request reports, and the merge base
        # its compare reports, are re-read before the read-back and again before the
        # write: a merge base that moves before either read refuses the write.
        for moves, expected in (
            (None, {"published": True, "reason": "CREATED"}),
            (compare, {"published": False, "reason": "STALE_COMPARISON"}),
            (conversation, {"published": False, "reason": "STALE_COMPARISON"}),
        ):
            with self.subTest(moves=moves):
                result, fake, client = publish(moves)

                self.assertEqual({"pull_number": 300, **expected}, result)
                self.assertIn(compare, fake.calls)
                self.assertEqual(
                    1 if moves == compare else 2, fake.calls.count(compare)
                )
                if expected["published"]:
                    client.post.assert_called_once_with(
                        f"{root}/issues/300/comments", {"body": entry["body"]}
                    )
                else:
                    client.post.assert_not_called()
                client.patch.assert_not_called()

    def test_scheduled_population_is_fully_enumerated_before_batch_selection(
        self,
    ) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        pulls: list[dict[str, Any]] = [
            {
                "number": number,
                "state": "open",
                "html_url": f"https://github.com/ktogias/gnostoa/pull/{number}",
                "head": {"sha": f"{number:040x}"[-40:]},
                "base": {"sha": "b" * 40},
            }
            for number in range(1, 12)
        ]
        listing = f"{root}/pulls?state=open&per_page=100"
        replies: dict[str, tuple[Any, dict[str, str]]] = {
            listing: (
                pulls[:6],
                {"link": '<https://api.github.com/page2/pulls>; rel="next"'},
            ),
            "https://api.github.com/page2/pulls": (pulls[6:], {}),
            **{f"{root}/pulls/{pull['number']}": (pull, {}) for pull in pulls},
        }
        heads = {pull["number"]: pull["head"]["sha"] for pull in pulls}

        # Eleven open Pull Requests over two listing pages exceed one scheduled batch:
        # the hour selects the batch, and the later hour's batch is the remainder of
        # the whole enumeration, which a listing cut to one batch would never reach.
        for observed_at, expected in (
            ("2026-09-19T22:00:00Z", list(range(1, 9))),
            ("2026-09-19T23:00:00Z", [9, 10, 11]),
        ):
            with (
                self.subTest(observed_at=observed_at),
                tempfile.TemporaryDirectory() as directory,
                mock.patch.object(adapter, "_now", return_value=observed_at),
            ):
                output = Path(directory) / "subjects.json"
                code = _run_adapter_main(
                    adapter,
                    _PagedFake(replies),
                    Path(directory),
                    [
                        "--mode",
                        "subjects",
                        "--repository",
                        "ktogias/gnostoa",
                        "--output",
                        str(output),
                    ],
                )

                self.assertEqual(0, code)
                self.assertEqual(
                    [
                        {"pull_number": number, "head": heads[number]}
                        for number in expected
                    ],
                    json.loads(output.read_text(encoding="utf-8")),
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

        # A candidate newer than both and without protected authority, which would
        # be written at once were the two owned comments not refused as ambiguous.
        candidate = reducer.build_projection(
            snapshot,
            protected_main_revision=None,
            outer_consumer=None,
            r2a_result={
                "outcome": "INCOMPLETE",
                "reason": "QUORUM_UNMET",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:132:1",
                "observed_at": "2026-09-19T16:43:10Z",
            },
        )
        client = _publication_client(
            [
                _issue_comment(
                    1, "github-actions[bot]", reducer.render_projection(first)
                ),
                _issue_comment(
                    2, "github-actions[bot]", reducer.render_projection(second)
                ),
            ]
        )
        with self.assertRaisesRegex(
            adapter.ProviderWriteError,
            "multiple valid owned L1 projection comments",
        ):
            adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry=_publication_entry(reducer.render_projection(candidate)),
            )
        client.post.assert_not_called()
        client.patch.assert_not_called()

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

        candidate = reducer.build_projection(
            _snapshot(),
            protected_main_revision=None,
            outer_consumer=None,
            r2a_result={
                "outcome": "INCOMPLETE",
                "reason": "QUORUM_UNMET",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:138:1",
                "observed_at": "2026-09-19T16:44:10Z",
            },
        )
        body = reducer.render_projection(candidate)
        client = _publication_client(
            [
                _issue_comment(
                    1, "github-actions[bot]", reducer.render_projection(legitimate)
                ),
                _issue_comment(2, "mallory", reducer.render_projection(forged_later)),
                _issue_comment(
                    3, "github-actions[bot]", reducer.render_projection(wrong_subject)
                ),
            ]
        )

        result = adapter.publish_entry(
            client,
            repository="ktogias/gnostoa",
            entry=_publication_entry(body),
        )

        # The one owned projection for this subject is the comment updated in place;
        # the forged and wrong-subject comments are neither ambiguity nor its owner.
        self.assertEqual(
            {"pull_number": 300, "published": True, "reason": "UPDATED"}, result
        )
        client.patch.assert_called_once_with(
            "https://api.github.com/repos/ktogias/gnostoa/issues/comments/1",
            {"body": body},
        )
        client.post.assert_not_called()

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
            input_document: dict[str, Any],
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
            tempfile.TemporaryDirectory() as directory,
        ):
            entry = _collected_entry(
                adapter,
                _PagedFake(_complete_replies_without_review_comments(root)),
                Path(directory),
                run_id=139,
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

        with (
            mock.patch.object(
                adapter,
                "_protected_state",
                side_effect=adapter.ProviderReadError("protected state unavailable"),
            ),
            tempfile.TemporaryDirectory() as directory,
        ):
            entry = _collected_entry(adapter, fake, Path(directory), run_id=140)

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
            # One byte over the publication payload's 300,000-byte bound, and not
            # JSON: a bound applied only after decoding fails with another error.
            path.write_bytes(b"x" * 300_001)
            client = mock.Mock()
            with self.assertRaisesRegex(
                ValueError,
                "publication payload exceeds bounded size",
            ):
                _run_adapter_main(
                    adapter,
                    client,
                    Path(directory),
                    [
                        "--mode",
                        "publish",
                        "--repository",
                        "ktogias/gnostoa",
                        "--payload",
                        str(path),
                    ],
                )
            self.assertEqual([], client.method_calls)

    def test_workflow_run_preserves_all_associated_pull_requests(self) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        listing = f"{root}/pulls?state=open&per_page=100"
        replies: dict[str, tuple[Any, dict[str, str]]] = {listing: ([], {})}
        for number in (301, 302):
            replies[f"{root}/pulls/{number}"] = (
                {
                    "number": number,
                    "state": "open",
                    "html_url": f"https://github.com/ktogias/gnostoa/pull/{number}",
                    "head": {"sha": f"{number:040x}"},
                    "base": {"sha": "b" * 40},
                },
                {},
            )
        payload = json.dumps(
            [
                {"number": 301},
                {"number": 302},
                {"number": 301},
            ]
        )

        # Each value the adapter's own field reader returns is recorded, through the
        # patch factory that receives the reader as its spec, so its once-each order
        # is seen before the run's merge of its sources could mask it.
        parsed: list[list[int]] = []

        def recorder(*, spec: Callable[[str], list[int]]) -> Callable[[str], list[int]]:
            def recording(raw: str) -> list[int]:
                result = spec(raw)
                parsed.append(list(result))
                return result

            return recording

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "subjects.json"

            def subjects(raw: str, *argv: str) -> tuple[list[int], list[str]]:
                """The subjects a run with this ``workflow_run.pull_requests`` field
                and these further arguments selects, and the reads it made."""
                parsed.clear()
                fake = _PagedFake(replies)
                with mock.patch.object(
                    adapter,
                    "_workflow_run_pull_numbers",
                    spec=True,
                    new_callable=recorder,
                ):
                    code = _run_adapter_main(
                        adapter,
                        fake,
                        Path(directory),
                        [
                            "--mode",
                            "subjects",
                            "--repository",
                            "ktogias/gnostoa",
                            "--workflow-run-pulls-json",
                            raw,
                            *argv,
                            "--output",
                            str(output),
                        ],
                    )
                self.assertEqual(0, code)
                selected = json.loads(output.read_text(encoding="utf-8"))
                return [item["pull_number"] for item in selected], fake.calls

            both = ([301, 302], [f"{root}/pulls/301", f"{root}/pulls/302"])
            self.assertEqual(both, subjects(payload))
            self.assertEqual([[301, 302]], parsed)
            # A number hinted on the command line that the field also names is one
            # subject: the run merges its two sources once each, in order, on the
            # scheduled path and on an event's.
            for event in ((), ("--event",)):
                with self.subTest(event=bool(event)):
                    self.assertEqual(
                        both,
                        subjects(
                            json.dumps([{"number": 301}, {"number": 302}]),
                            "--pull-number",
                            "301",
                            *event,
                        ),
                    )
                    self.assertEqual([[301, 302]], parsed)
            # An empty or null field names no Pull Request, so the run falls back to
            # the open population, here empty.
            for raw in ("", "null"):
                with self.subTest(raw=raw):
                    self.assertEqual(([], [listing]), subjects(raw))
                    self.assertEqual([[]], parsed)
            # A number no Pull Request has is refused before any read.
            malformed = json.dumps([{"number": 0}])
            with self.assertRaisesRegex(
                SystemExit,
                "workflow_run.pull_requests",
            ) as refused:
                subjects(malformed)
            self.assertEqual([], parsed)
            self.assertIsInstance(
                refused.exception.__cause__, adapter.ProviderReadError
            )

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
        assert isinstance(l1, dict)
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
        assert isinstance(semantic, dict)
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
        assert isinstance(upload, dict)
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
        assert isinstance(download, dict)
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
            assert isinstance(checkout, dict)
            checkout_with = checkout.get("with")
            self.assertIsInstance(checkout_with, dict)
            assert isinstance(checkout_with, dict)
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
