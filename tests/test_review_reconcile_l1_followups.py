from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock


_NONEMPTY_TEST_VALUE = "fixture-value"


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
    def test_malformed_native_commit_bindings_make_source_incomplete(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"

        cases = (
            (
                "reviews",
                f"{root}/pulls/300/reviews?per_page=100",
                False,
                "commit_id",
            ),
            (
                "review_threads",
                f"{root}/pulls/300/comments?per_page=100",
                False,
                "commit_id",
            ),
        )
        for source, url, wrapped, field in cases:
            with self.subTest(source=source):
                replies = copy.deepcopy(fixtures._complete_replies(root))
                payload = replies[url][0]
                items = payload["check_runs"] if wrapped else payload
                items[0][field] = "not-an-exact-git-commit"
                snapshot = adapter.collect_snapshot(
                    fixtures._PagedFake(replies),
                    repository="ktogias/gnostoa",
                    pull_number=300,
                    observed_at="2026-09-19T16:41:00Z",
                )
                self.assertNotEqual(
                    "COMPLETE",
                    snapshot["coverage"][source]["status"],
                )
                self.assertEqual([], snapshot[source])

    def test_graphql_resolution_makes_thread_coverage_complete(
        self,
    ) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        snapshot = adapter.collect_snapshot(
            fixtures._PagedFake(fixtures._complete_replies(root)),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["review_threads"]["status"])
        self.assertTrue(snapshot["review_threads"])
        self.assertEqual(
            {"resolved"},
            {item["state"] for item in snapshot["review_threads"]},
        )

    def test_malformed_semantic_result_becomes_unavailable(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        malformed = (
            {"outcome": "PASS"},
            {"outcome": "PASS", "reason": "QUORUM_SATISFIED"},
            {
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": True,
            },
        )
        for payload in malformed:
            with self.subTest(payload=payload):
                result = adapter._semantic_result(
                    0,
                    json.dumps(payload).encode("utf-8"),
                )
                self.assertEqual(
                    {"reason": "INVALID_R2A_RESULT"},
                    result,
                )

    def test_malformed_protected_consumer_is_projected_unavailable(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        bundle = SimpleNamespace(
            protected_main_revision="e" * 40,
            document=fixtures._bundle(),
        )
        consumer = SimpleNamespace(
            protected_main_revision="e" * 40,
            document={
                "acquired_consumer": {
                    "runtime_image": ("ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64),
                }
            },
        )

        def valid_result(
            input_document: object,
            *,
            acquire_consumer: Any,
        ) -> tuple[int, bytes]:
            self.assertIs(consumer, acquire_consumer())
            self.assertIsInstance(input_document, dict)
            return fixtures._valid_incomplete_result(input_document)

        with (
            mock.patch.object(
                adapter, "_protected_state", return_value=(bundle, consumer)
            ),
            mock.patch(
                "tools.review_outer._run_prior_effective_current_advisory_with_acquisition",
                side_effect=valid_result,
            ),
        ):
            entry = adapter._collect_entry(
                fixtures._PagedFake(
                    fixtures._complete_replies_without_review_comments(root)
                ),
                "ktogias/gnostoa",
                300,
                run_id=141,
                run_attempt=1,
            )

        projection = reducer.parse_projection_comment(entry["body"])
        self.assertIsInstance(projection, dict)
        self.assertEqual("PARTIAL", projection["protected"]["status"])
        self.assertEqual("UNAVAILABLE", projection["r2a"]["outcome"])
        self.assertEqual(
            "WAIT_FOR_PROTECTED_CAPABILITY",
            projection["next_permitted_action"],
        )

    def test_hourly_recovery_rotates_bounded_open_pull_batches(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
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
        reader = fixtures._PagedFake(
            {
                f"{root}/pulls?state=open&per_page=100": (pulls, {}),
            }
        )

        enumerated = adapter._open_pull_numbers(reader, "ktogias/gnostoa")
        first = adapter._select_scheduled_pull_batch(
            enumerated,
            "2026-09-19T22:00:00Z",
        )
        second = adapter._select_scheduled_pull_batch(
            enumerated,
            "2026-09-19T23:00:00Z",
        )

        self.assertEqual(list(range(1, 12)), enumerated)
        self.assertLessEqual(len(first), adapter._MAX_OPEN_PULLS)
        self.assertLessEqual(len(second), adapter._MAX_OPEN_PULLS)
        self.assertEqual(set(enumerated), set(first) | set(second))
        self.assertNotEqual(first, second)

    def test_explicit_event_population_over_capacity_fails_closed(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        workflow_pulls = json.dumps(
            [{"number": number} for number in range(1, adapter._MAX_OPEN_PULLS + 2)]
        )

        with (
            mock.patch.dict(adapter.os.environ, {"GH_TOKEN": _NONEMPTY_TEST_VALUE}),
            self.assertRaisesRegex(
                SystemExit,
                "selected Pull Request population exceeds bounded reconciliation capacity",
            ),
        ):
            adapter.main(
                [
                    "--mode",
                    "collect",
                    "--repository",
                    "ktogias/gnostoa",
                    "--workflow-run-pulls-json",
                    workflow_pulls,
                    "--output",
                    "unused.json",
                    "--run-id",
                    "999",
                ]
            )

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
                        "--run-id",
                        "999",
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
                        "app": {"id": 1001},
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
                "execution_id": "synthetic-execution::250",
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

    def test_publication_rejects_wrong_pull_identity_before_write(self) -> None:
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
                "execution_id": "github-actions:259:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        entry = {
            "pull_number": 300,
            "head_sha": "a" * 40,
            "body": reducer.render_projection(projection),
        }
        client = mock.Mock()
        client.get.return_value = (
            {
                "number": 999,
                "state": "open",
                "html_url": "https://github.com/ktogias/gnostoa/pull/999",
                "title": "wrong subject",
                "body": "",
                "head": {"sha": "a" * 40},
                "base": {"sha": "b" * 40},
            },
            {},
        )

        with self.assertRaisesRegex(
            adapter.ProviderReadError,
            "Pull Request identity changed during publication",
        ):
            adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry=entry,
            )

        client.post.assert_not_called()
        client.patch.assert_not_called()

    def test_publication_rejects_stale_collected_lifecycle(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
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
                "execution_id": "github-actions:272:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )

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
            existing_projection=None,
            candidate_projection=projection,
        )

        self.assertIs(False, allowed)
        self.assertEqual("STALE_LIFECYCLE", reason)

    def test_publication_rechecks_exact_subject_after_comment_readback(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
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
                "execution_id": "github-actions:260:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        entry = {
            "pull_number": 300,
            "head_sha": "a" * 40,
            "body": reducer.render_projection(projection),
        }
        initial = {
            "state": "open",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "merge_base_sha": "c" * 40,
        }
        drifted = {
            "state": "open",
            "head_sha": "a" * 40,
            "base_sha": "d" * 40,
            "merge_base_sha": "e" * 40,
        }
        client = mock.Mock()

        with (
            mock.patch.object(
                adapter,
                "_current_pr",
                side_effect=[initial, drifted],
            ) as current,
            mock.patch.object(
                adapter,
                "_collect_pages",
                return_value=(
                    [],
                    {"status": "COMPLETE", "pages": 1, "count": 0},
                ),
            ),
        ):
            result = adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry=entry,
            )

        self.assertEqual(2, current.call_count)
        self.assertIs(False, result["published"])
        self.assertEqual("STALE_COMPARISON", result["reason"])
        client.post.assert_not_called()
        client.patch.assert_not_called()

    def test_normalized_source_payload_shapes_and_counts_fail_closed(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()

        for source in ("conversation", "reviews", "review_threads", "checks"):
            for mutation in ("missing_payload", "count_mismatch"):
                with self.subTest(source=source, mutation=mutation):
                    snapshot = fixtures._snapshot()
                    if mutation == "missing_payload":
                        snapshot[source] = None
                    else:
                        snapshot["coverage"][source]["count"] += 1

                    with self.assertRaises(reducer.ReconciliationInputError):
                        reducer.build_review_input(snapshot, fixtures._bundle())

                    with self.assertRaises(reducer.ReconciliationInputError):
                        reducer.build_projection(
                            snapshot,
                            protected_main_revision="e" * 40,
                            outer_consumer={
                                "runtime_image": (
                                    "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64
                                ),
                                "runtime_revision": "9" * 40,
                            },
                            r2a_result={
                                "outcome": "PASS",
                                "reason": "QUORUM_SATISFIED",
                                "binding": False,
                            },
                            execution={
                                "execution_id": "github-actions:270:1",
                                "observed_at": "2026-09-19T16:41:10Z",
                            },
                        )

    def test_publication_rejects_semantically_unsafe_projection_artifacts(
        self,
    ) -> None:
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
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:271:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )

        mutations = {
            "canonical_claim": lambda item: item.__setitem__("non_canonical", False),
            "binding_claim": lambda item: item["r2a"].__setitem__("binding", True),
            "incomplete_current_claim": lambda item: item["coverage"][
                "conversation"
            ].__setitem__("status", "PARTIAL"),
            "omitted_ambiguous_claim": lambda item: item["checks"].__setitem__(
                "omitted_ambiguous",
                1,
            ),
            "omitted_pending_claim": lambda item: item["checks"].__setitem__(
                "omitted_pending",
                1,
            ),
            "omitted_non_success_claim": lambda item: item["checks"].__setitem__(
                "omitted_non_success",
                1,
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                unsafe = copy.deepcopy(projection)
                mutate(unsafe)
                body = (
                    "<!-- gnostoa:l1-current-state:v1:"
                    + reducer._encode_projection(unsafe)
                    + " -->"
                )
                entry = {
                    "pull_number": 300,
                    "head_sha": "a" * 40,
                    "body": body,
                }
                client = mock.Mock()

                with (
                    mock.patch.object(
                        adapter,
                        "_current_pr",
                        side_effect=AssertionError(
                            "unsafe projection reached provider read"
                        ),
                    ) as current,
                    self.assertRaisesRegex(
                        adapter.ProviderWriteError,
                        "publication payload has no valid L1 projection",
                    ),
                ):
                    adapter.publish_entry(
                        client,
                        repository="ktogias/gnostoa",
                        entry=entry,
                    )

                current.assert_not_called()
                client.get.assert_not_called()
                client.post.assert_not_called()
                client.patch.assert_not_called()

    def test_noncanonical_candidate_rejected_but_owned_prior_render_accepted(
        self,
    ) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        projection = reducer.build_projection(
            fixtures._snapshot(),
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": ("ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64),
                "runtime_revision": "9" * 40,
            },
            r2a_result={
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:272:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        canonical = reducer.render_projection(projection)
        unsafe = canonical + "\n## Review result\n\n**PASS — safe to merge**\n"
        entry = {
            "pull_number": 300,
            "head_sha": "a" * 40,
            "body": unsafe,
        }
        client = mock.Mock()

        with (
            mock.patch.object(
                adapter,
                "_current_pr",
                side_effect=AssertionError(
                    "non-canonical projection reached provider read"
                ),
            ) as current,
            self.assertRaisesRegex(
                adapter.ProviderWriteError,
                "canonical L1 projection",
            ),
        ):
            adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry=entry,
            )

        current.assert_not_called()
        client.get.assert_not_called()
        client.post.assert_not_called()
        client.patch.assert_not_called()

        comments = [
            {
                "id": 77,
                "author": adapter._PROJECTION_AUTHOR,
                "body": unsafe,
            }
        ]
        existing = adapter._existing_projection(
            comments,
            repository="ktogias/gnostoa",
            pull_number=300,
        )
        self.assertIsNotNone(existing)
        self.assertEqual(77, existing[0])
        self.assertEqual(projection, existing[1])

    def test_materially_different_native_translator_reuses_core_unchanged(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        native = {
            "engine": "nebula-review",
            "project_key": "opaque-project::7",
            "proposal": {
                "native_ref": "proposal::alpha/42",
                "phase": "active",
                "tip": "a" * 40,
                "parent": "b" * 40,
                "fork_point": "c" * 40,
                "locator": "urn:nebula:proposal:alpha-42",
            },
            "decisions": [
                {
                    "native_ref": "decision::opaque-Z9",
                    "actor": "reviewer::opaque-A",
                    "verdict": "accept",
                    "when": "2026-09-19T16:40:30Z",
                    "revision": "a" * 40,
                },
                {
                    "native_ref": "decision::opaque-Q2",
                    "actor": "reviewer::opaque-B",
                    "verdict": "note",
                    "when": "2026-09-19T16:39:30Z",
                    "revision": "d" * 40,
                },
            ],
            "threads": [],
        }

        def translate(document: dict[str, Any]) -> dict[str, Any]:
            proposal = document["proposal"]
            verdict_map = {
                "accept": "APPROVED",
                "note": "COMMENTED",
            }
            signals = document.get("signals")
            checks_available = isinstance(signals, list)
            native_checks = signals if checks_available else []
            return {
                "schema_version": reducer.PROVIDER_STATE_SCHEMA_VERSION,
                "provider": {
                    "id": document["engine"],
                    "adapter": "test.nebula-native/v1",
                },
                "observed_at": "2026-09-19T16:41:00Z",
                "subject": {
                    "repository": f"urn:nebula:project:{document['project_key']}",
                    "change_request": {
                        "kind": "proposal",
                        "id": proposal["native_ref"],
                    },
                    "state": "open" if proposal["phase"] == "active" else "closed",
                    "head_commit": proposal["tip"],
                    "base_commit": proposal["parent"],
                    "comparison": {
                        "kind": "merge_base",
                        "commit_sha": proposal["fork_point"],
                    },
                    "source_url": proposal["locator"],
                    "title": "Opaque native proposal",
                },
                "coverage": {
                    "subject": {"status": "COMPLETE", "pages": 1, "count": 1},
                    "conversation": {"status": "COMPLETE", "pages": 1, "count": 0},
                    "reviews": {
                        "status": "COMPLETE",
                        "pages": 1,
                        "count": len(document["decisions"]),
                    },
                    "review_threads": {"status": "COMPLETE", "pages": 1, "count": 0},
                    "checks": {
                        "status": "COMPLETE" if checks_available else "UNAVAILABLE",
                        "pages": 1 if checks_available else 0,
                        "count": len(native_checks),
                    },
                },
                "conversation": [],
                "reviews": [
                    {
                        "observation_id": item["native_ref"],
                        "reviewer_id": item["actor"],
                        "recommendation_state": verdict_map.get(
                            item["verdict"],
                            "UNKNOWN",
                        ),
                        "observed_at": item["when"],
                        "head_commit": item["revision"],
                        "source_url": f"urn:nebula:{item['native_ref']}",
                    }
                    for item in document["decisions"]
                ],
                "review_threads": [],
                "checks": [
                    {
                        "id": item["native_ref"],
                        "key": f"nebula-signal:{item['label']}",
                        "name": item["label"],
                        "head_commit": item["revision"],
                        "observed_at": item["when"],
                        "status": "completed" if item["phase"] == "done" else "queued",
                        "conclusion": (
                            "success"
                            if item["result"] == "ok"
                            else "failure"
                            if item["result"] == "error"
                            else None
                        ),
                        "source_url": f"urn:nebula:{item['native_ref']}",
                    }
                    for item in native_checks
                ],
            }

        snapshot = translate(native)
        review_input = reducer.build_review_input(snapshot, fixtures._bundle())
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
                "execution_id": "pipeline-ref::sha256:opaque-7f",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )

        self.assertEqual("proposal", review_input["subject"]["change_request"]["kind"])
        self.assertEqual(
            "proposal::alpha/42",
            review_input["subject"]["change_request"]["id"],
        )
        self.assertEqual(
            "pipeline-ref::sha256:opaque-7f",
            projection["observation"]["execution_id"],
        )
        self.assertNotIn("run_id", projection["observation"])
        self.assertNotIn("run_attempt", projection["observation"])
        self.assertEqual("INCOMPLETE_AT_OBSERVATION", projection["currentness"])
        self.assertEqual("UNAVAILABLE", projection["r2a"]["outcome"])
        self.assertEqual(
            "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE",
            projection["next_permitted_action"],
        )

        full_native = copy.deepcopy(native)
        full_native["signals"] = [
            {
                "native_ref": "signal::opaque-91",
                "label": "fast",
                "revision": "a" * 40,
                "when": "2026-09-19T16:40:40Z",
                "phase": "done",
                "result": "ok",
            }
        ]
        native_full = translate(full_native)
        reference = fixtures._snapshot(
            provider_id="reference-provider",
            repository="urn:reference:project:7",
            change_kind="proposal",
            change_id="reference::42",
            source_url="urn:reference:proposal:42",
        )
        reference["review_threads"] = []
        reference["coverage"]["review_threads"]["count"] = 0
        native_input = reducer.build_review_input(native_full, fixtures._bundle())
        reference_input = reducer.build_review_input(reference, fixtures._bundle())

        def binding_semantics(document: dict[str, Any]) -> list[tuple[str, str]]:
            return sorted(
                (
                    item["native"]["recommendation_state"],
                    item["subject_binding"]["status"],
                )
                for item in document["evidence_set"]["observations"]
            )

        self.assertEqual(
            binding_semantics(reference_input),
            binding_semantics(native_input),
        )
        self.assertEqual(
            {"accept", "note"},
            {item["verdict"] for item in full_native["decisions"]},
        )
        self.assertEqual(
            {"APPROVED", "COMMENTED"},
            {
                item["native"]["recommendation_state"]
                for item in native_input["evidence_set"]["observations"]
            },
        )

        from tools.review_adapter_file import normalize_observation

        self.assertEqual(
            sorted(
                normalize_observation(item)[0]["normalized_recommendation"]
                for item in reference_input["evidence_set"]["observations"]
            ),
            sorted(
                normalize_observation(item)[0]["normalized_recommendation"]
                for item in native_input["evidence_set"]["observations"]
            ),
        )

        common_result = {
            "outcome": "PASS",
            "reason": "QUORUM_SATISFIED",
            "binding": False,
        }
        native_projection = reducer.build_projection(
            native_full,
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result=common_result,
            execution={
                "execution_id": "nebula-pipeline::opaque-generation",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        reference_projection = reducer.build_projection(
            reference,
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result=common_result,
            execution={
                "execution_id": "reference-exec::different-native-ref",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        self.assertEqual(
            reference_projection["currentness"],
            native_projection["currentness"],
        )
        self.assertEqual(
            reference_projection["next_permitted_action"],
            native_projection["next_permitted_action"],
        )
        self.assertEqual(
            reference_projection["r2a"],
            native_projection["r2a"],
        )
        for key in ("ambiguous", "pending", "non_success"):
            self.assertEqual(
                reference_projection["checks"][key],
                native_projection["checks"][key],
            )

    def test_native_id_ordering_mutant_is_rejected_by_ambiguity_semantics(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        base = fixtures._snapshot(provider_id="nebula-review")
        signals = [
            {
                "id": "opaque-Z-success",
                "key": "native-signal",
                "name": "native-signal",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "success",
            },
            {
                "id": "opaque-A-failure",
                "key": "native-signal",
                "name": "native-signal",
                "head_commit": "a" * 40,
                "observed_at": "2026-09-19T16:41:00Z",
                "status": "completed",
                "conclusion": "failure",
            },
        ]

        for ordered in (signals, list(reversed(signals))):
            snapshot = copy.deepcopy(base)
            snapshot["checks"] = ordered
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
                    "execution_id": "opaque-exec::same-time-replay",
                    "observed_at": "2026-09-19T16:41:10Z",
                },
            )
            self.assertEqual(["native-signal"], projection["checks"]["ambiguous"])
            self.assertEqual(
                "RECONCILE_PROVIDER_CHECKS",
                projection["next_permitted_action"],
            )


if __name__ == "__main__":
    unittest.main()
