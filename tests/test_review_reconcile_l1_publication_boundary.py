"""L1's publication and snapshot boundaries (#389, owner B).

A #425 mutation run over `main`'s own L1 code left twelve behaviours that no test pinned:
the review-comment metadata gap on the thread coverage, the observations that move the
snapshot's cut, the candidate subject's head and base, supersession, the unavailable
reason, both protected revisions, and the skip for a projection without protected
authority. Each test calls L1's public functions and the shared fixture module's public
accessors; some also patch L1's module-level seams (`_now`, `_MAX_PAGES`,
`_projection_key`, `_current_pr`, `_collect_pages`, `_protected_state`) to steer them.
"""

from __future__ import annotations

import contextlib
import importlib.util
import unittest
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock


def _fixtures() -> Any:
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location(
        "l1_publication_boundary_fixtures", path
    )
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ROOT = "https://api.github.com/repos/ktogias/gnostoa"
_SUBJECT = {
    "provider_id": "github",
    "repository": "https://github.com/ktogias/gnostoa",
    "change_request": {"kind": "github-pull-request", "id": "300"},
    "head_commit": "a" * 40,
    "base_commit": "b" * 40,
    "merge_base_commit": "c" * 40,
    "state": "open",
}
_CURRENT_PR = {
    "state": "open",
    "head_sha": "a" * 40,
    "base_sha": "b" * 40,
    "merge_base_sha": "c" * 40,
}


class L1PublicationAndSnapshotBoundaryTests(unittest.TestCase):
    """Behaviour that no other test pinned, each through L1's public functions."""

    def _snapshot_with(
        self,
        mutate: Callable[[dict[str, Any]], None] | None = None,
        *,
        failing: frozenset[str] = frozenset(),
        max_pages: int | None = None,
    ) -> dict[str, Any]:
        fixtures = _fixtures()
        adapter = fixtures.adapter_fixture()
        replies = fixtures.complete_replies_fixture(_ROOT)
        if mutate is not None:
            mutate(replies)

        fake = fixtures.paged_fake_fixture(replies)
        read = fake.get

        def get(url: str) -> tuple[Any, dict[str, str]]:
            # The fake's own GraphQL reads go through `get` too, so a failing page
            # fails on both routes, as a provider read would.
            if url in failing:
                raise adapter.ProviderReadError(f"read failed: {url}")
            reply: tuple[Any, dict[str, str]] = read(url)
            return reply

        fake.get = get
        with contextlib.ExitStack() as stack:
            # L1 stamps some observations with its own clock; fixed before the
            # fixture's late items, so the cut shows which observations move it.
            stack.enter_context(
                mock.patch.object(adapter, "_now", return_value="2026-09-19T16:41:30Z")
            )
            if max_pages is not None:
                stack.enter_context(mock.patch.object(adapter, "_MAX_PAGES", max_pages))
            snapshot: dict[str, Any] = adapter.collect_snapshot(
                fake,
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:41:00Z",
            )
        return snapshot

    def test_a_failed_review_comment_read_is_reported_on_the_thread_coverage(
        self,
    ) -> None:
        failing = frozenset({"https://api.github.com/page2/review-comments"})
        coverage = self._snapshot_with(failing=failing)["coverage"]["review_threads"]

        self.assertEqual("PARTIAL", coverage["metadata_status"])
        self.assertEqual(1, coverage["metadata_pages"])
        self.assertEqual(
            "read failed: https://api.github.com/page2/review-comments",
            coverage["metadata_reason"],
        )

    def test_a_page_limited_review_comment_read_names_the_metadata_gap(self) -> None:
        coverage = self._snapshot_with(max_pages=1)["coverage"]["review_threads"]

        self.assertEqual("PARTIAL", coverage["metadata_status"])
        self.assertEqual(
            "review_comment_metadata_incomplete", coverage["metadata_reason"]
        )

    def test_the_cut_is_the_latest_comment_or_check_observation(self) -> None:
        def late_comment(replies: dict[str, Any]) -> None:
            comments = replies[f"{_ROOT}/issues/300/comments?per_page=100"][0]
            comments[0]["updated_at"] = "2026-09-19T16:59:00Z"

        def late_check(replies: dict[str, Any]) -> None:
            for url, (payload, _headers) in replies.items():
                if "/check-runs" in url and isinstance(payload, dict):
                    for run in payload["check_runs"]:
                        run["completed_at"] = "2026-09-19T16:58:00Z"

        for mutate, expected in (
            (late_comment, "2026-09-19T16:59:00Z"),
            (late_check, "2026-09-19T16:58:00Z"),
        ):
            with self.subTest(source=mutate.__name__):
                self.assertEqual(expected, self._snapshot_with(mutate)["observed_at"])

    def _decision(
        self,
        subject: dict[str, Any],
        existing: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        adapter = _fixtures().adapter_fixture()
        with mock.patch.object(
            adapter, "_projection_key", side_effect=lambda projection: projection["key"]
        ):
            decision: tuple[bool, str] = adapter.publication_decision(
                repository="ktogias/gnostoa",
                pull_number=300,
                current_pr=dict(_CURRENT_PR),
                collected_head="a" * 40,
                existing_projection=existing,
                candidate_projection={"subject": subject, "key": 5},
            )
        return decision

    def test_a_candidate_naming_another_head_or_no_base_is_a_mismatch(self) -> None:
        for field, value in (("head_commit", "d" * 40), ("base_commit", None)):
            with self.subTest(field=field):
                self.assertEqual(
                    (False, "CANDIDATE_SUBJECT_MISMATCH"),
                    self._decision({**_SUBJECT, field: value}),
                )

    def test_only_a_projection_at_the_head_and_not_older_supersedes(self) -> None:
        at_head = {"subject": {"head_commit": "a" * 40}, "key": 5}
        older_at_head = {"subject": {"head_commit": "a" * 40}, "key": 4}
        elsewhere = {"subject": {"head_commit": "d" * 40}, "key": 9}

        self.assertEqual(
            (False, "SUPERSEDED_PROJECTION"), self._decision(_SUBJECT, at_head)
        )
        self.assertEqual((True, "PUBLISH"), self._decision(_SUBJECT, older_at_head))
        self.assertEqual((True, "PUBLISH"), self._decision(_SUBJECT, elsewhere))

    def test_an_empty_unavailable_reason_is_the_provider_s(self) -> None:
        adapter = _fixtures().adapter_fixture()

        self.assertEqual(
            {
                "pull_number": 300,
                "published": False,
                "reason": "PROVIDER_SUBJECT_UNAVAILABLE",
            },
            adapter.publish_entry(
                mock.Mock(),
                repository="ktogias/gnostoa",
                entry={
                    "pull_number": 300,
                    "collection_status": "UNAVAILABLE",
                    "reason": "",
                },
            ),
        )

    def _publish(
        self, protected_main_revision: str | None, state: tuple[str, str]
    ) -> tuple[dict[str, Any], Any, Any]:
        fixtures = _fixtures()
        adapter = fixtures.adapter_fixture()
        reducer = fixtures.reducer_fixture()
        projection = reducer.build_projection(
            fixtures.snapshot_fixture(),
            protected_main_revision=protected_main_revision,
            outer_consumer=(
                {
                    "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                    "runtime_revision": "9" * 40,
                }
                if protected_main_revision is not None
                else None
            ),
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
        bundle = SimpleNamespace(protected_main_revision=state[0], document={})
        consumer = SimpleNamespace(protected_main_revision=state[1], document={})
        client = mock.Mock()
        with (
            mock.patch.object(adapter, "_current_pr", return_value=dict(_CURRENT_PR)),
            mock.patch.object(
                adapter,
                "_collect_pages",
                return_value=([], {"status": "COMPLETE", "pages": 1, "count": 0}),
            ),
            mock.patch.object(
                adapter, "_protected_state", return_value=(bundle, consumer)
            ) as acquired,
        ):
            result: dict[str, Any] = adapter.publish_entry(
                client, repository="ktogias/gnostoa", entry=entry
            )
        return result, client, acquired

    def test_both_protected_documents_must_name_the_projection_s_revision(self) -> None:
        for state in (("e" * 40, "f" * 40), ("f" * 40, "e" * 40)):
            with self.subTest(bundle=state[0][:1], consumer=state[1][:1]):
                result, client, _acquired = self._publish("e" * 40, state)

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

    def test_a_projection_without_protected_authority_skips_the_protected_check(
        self,
    ) -> None:
        result, client, acquired = self._publish(None, ("f" * 40, "f" * 40))

        self.assertEqual(
            {"pull_number": 300, "published": True, "reason": "CREATED"}, result
        )
        acquired.assert_not_called()
        client.post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
