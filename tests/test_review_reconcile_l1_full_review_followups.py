from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import yaml


def _fixtures() -> Any:
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location("l1_full_review_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UsefulL1IndependentReviewRegressions(unittest.TestCase):
    def test_confirming_pass_never_claims_cut_after_unseen_late_review(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = copy.deepcopy(fixtures._complete_replies(root))
        reader = fixtures._PagedFake(replies)
        original_get = reader.get
        pull_url = f"{root}/pulls/300"
        review_comments_url = f"{root}/pulls/300/comments?per_page=100"
        review_url = f"{root}/pulls/300/reviews?per_page=100"
        pass_number = 0
        injected = False

        def read(url: str) -> Any:
            nonlocal pass_number, injected
            if url == pull_url:
                pass_number += 1
            if pass_number == 2 and url == review_comments_url and not injected:
                injected = True
                replies[review_url][0].append(
                    {
                        "id": 99,
                        "user": {"login": "late-reviewer"},
                        "state": "CHANGES_REQUESTED",
                        "submitted_at": "2026-09-19T16:41:25Z",
                        "commit_id": "a" * 40,
                        "html_url": "https://example.invalid/review/99",
                    }
                )
            return original_get(url)

        times = iter(
            (
                "2026-09-19T16:41:10Z",
                "2026-09-19T16:41:20Z",
                "2026-09-19T16:41:30Z",
                "2026-09-19T16:41:40Z",
                "2026-09-19T16:41:50Z",
                "2026-09-19T16:42:00Z",
            )
        )
        with (
            mock.patch.object(reader, "get", side_effect=read),
            mock.patch.object(adapter, "_now", side_effect=lambda: next(times)),
        ):
            snapshot = adapter.collect_snapshot(
                reader,
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:41:00Z",
            )

        retained_ids = {item["observation_id"] for item in snapshot["reviews"]}
        late_review_retained = "github-review-99" in retained_ids
        cut_precedes_unseen_review = adapter.parse_rfc3339(
            snapshot["observed_at"]
        ) < adapter.parse_rfc3339("2026-09-19T16:41:25Z")
        incomplete = snapshot["coverage"]["reviews"]["status"] != "COMPLETE"
        self.assertTrue(
            late_review_retained or cut_precedes_unseen_review or incomplete,
            "stable read-back claimed a cut after review evidence it never reread",
        )

    def test_github_adapter_collects_commit_statuses_as_check_signals(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = copy.deepcopy(fixtures._complete_replies(root))
        replies[f"{root}/commits/{'a' * 40}/statuses?per_page=100"] = (
            [
                {
                    "id": 77,
                    "state": "pending",
                    "context": "external-review",
                    "created_at": "2026-09-19T16:40:10Z",
                    "updated_at": "2026-09-19T16:40:11Z",
                    "target_url": "https://example.invalid/status/77",
                }
            ],
            {},
        )

        snapshot = adapter._collect_snapshot_once(
            fixtures._PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )

        self.assertTrue(
            any(item["name"] == "external-review" for item in snapshot["checks"])
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["checks"]["status"])

    def test_same_name_check_signals_from_distinct_integrations_do_not_collapse(
        self,
    ) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
        snapshot["checks"] = [
            {
                "id": "signal-a",
                "key": "provider-check:integration-a:shared",
                "name": "shared",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:40:00Z",
                "status": "completed",
                "conclusion": "failure",
            },
            {
                "id": "signal-b",
                "key": "provider-check:integration-b:shared",
                "name": "shared",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "success",
            },
        ]
        snapshot["coverage"]["checks"]["count"] = 2

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
                "execution_id": "github-actions:500:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )

        self.assertTrue(projection["checks"]["non_success"])
        self.assertEqual(
            "RECONCILE_PROVIDER_CHECKS",
            projection["next_permitted_action"],
        )

    def test_latest_opinionated_review_supersedes_older_same_reviewer_opinion(
        self,
    ) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        replies = copy.deepcopy(fixtures._complete_replies(root))
        replies[f"{root}/pulls/300/reviews?per_page=100"][0][0].update(
            {
                "user": {"login": "one"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2026-09-19T16:40:02Z",
            }
        )
        replies["https://api.github.com/page2/reviews"][0][0].update(
            {
                "user": {"login": "one"},
                "state": "APPROVED",
                "submitted_at": "2026-09-19T16:40:03Z",
            }
        )

        snapshot = adapter._collect_snapshot_once(
            fixtures._PagedFake(replies),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )
        review_input = reducer.build_review_input(snapshot, fixtures._bundle())
        opinions = [
            item["native"]["recommendation_state"]
            for item in review_input["evidence_set"]["observations"]
            if item["reviewer_id"] == "one"
        ]

        self.assertEqual(["APPROVED"], opinions)

    def test_publish_refuses_projection_from_superseded_protected_main(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        projection = reducer.build_projection(
            fixtures._snapshot(),
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
                "execution_id": "github-actions:501:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        entry = {
            "pull_number": 300,
            "head_sha": "a" * 40,
            "body": reducer.render_projection(projection),
        }
        current_pr = {
            "state": "open",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "merge_base_sha": "c" * 40,
        }
        protected = SimpleNamespace(protected_main_revision="f" * 40, document={})
        client = mock.Mock()

        with (
            mock.patch.object(adapter, "_current_pr", return_value=current_pr),
            mock.patch.object(
                adapter,
                "_collect_pages",
                return_value=([], {"status": "COMPLETE", "pages": 1, "count": 0}),
            ),
            mock.patch.object(
                adapter,
                "_protected_state",
                return_value=(protected, protected),
            ),
        ):
            result = adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry=entry,
            )

        self.assertEqual(
            {
                "pull_number": 300,
                "published": False,
                "reason": "STALE_PROTECTED_AUTHORITY",
            },
            result,
        )
        client.post.assert_not_called()
        client.patch.assert_not_called()

    def test_github_publication_rejects_unorderable_candidate_before_provider_io(
        self,
    ) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        projection = reducer.build_projection(
            fixtures._snapshot(),
            protected_main_revision=None,
            outer_consumer=None,
            r2a_result={"reason": "TEST_UNAVAILABLE"},
            execution={
                "execution_id": "opaque-direct-call",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        client = mock.Mock()

        with self.assertRaises(adapter.ProviderWriteError):
            adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry={
                    "pull_number": 300,
                    "head_sha": "a" * 40,
                    "body": reducer.render_projection(projection),
                },
            )

        client.get.assert_not_called()
        client.post.assert_not_called()
        client.patch.assert_not_called()

    def test_useful_l1_guardrail_lists_all_material_focused_test_modules(self) -> None:
        fixtures = _fixtures()
        guardrails = yaml.safe_load(
            fixtures.GUARDRAILS_PATH.read_text(encoding="utf-8")
        )
        entry = next(
            item
            for item in guardrails["guardrails"]
            if item["id"] == "useful-l1-current-state-reconciliation"
        )

        self.assertIn(
            "tests/test_review_reconcile_l1_thread_state.py",
            entry["tests"],
        )
        self.assertIn(
            "tests/test_review_reconcile_l1_render_compat.py",
            entry["tests"],
        )
        self.assertIn(
            "tests/test_review_reconcile_l1_full_review_followups.py",
            entry["tests"],
        )


if __name__ == "__main__":
    unittest.main()
