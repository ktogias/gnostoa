from __future__ import annotations

import importlib
import importlib.util
import json
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "ci" / "review_github_current_state.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "review-current-state.yml"


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


def _snapshot() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "provider": "github",
        "repository": "ktogias/gnostoa",
        "pull_number": 300,
        "observed_at": "2026-09-19T16:41:00Z",
        "subject": {
            "state": "open",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "merge_base_sha": "c" * 40,
            "html_url": "https://github.com/ktogias/gnostoa/pull/300",
        },
        "coverage": {
            "pull": {"status": "COMPLETE", "pages": 1},
            "issue_comments": {"status": "COMPLETE", "pages": 2},
            "reviews": {"status": "COMPLETE", "pages": 2},
            "review_comments": {"status": "COMPLETE", "pages": 1},
            "check_runs": {"status": "COMPLETE", "pages": 1},
        },
        "issue_comments": [
            {
                "id": 1,
                "author": "review-bot",
                "created_at": "2026-09-19T16:40:20Z",
                "updated_at": "2026-09-19T16:40:20Z",
                "body": "raw provider text that must not be rendered",
            }
        ],
        "reviews": [
            {
                "id": 10,
                "author": "qodo-code-review[bot]",
                "state": "APPROVED",
                "submitted_at": "2026-09-19T16:40:30Z",
                "commit_id": "a" * 40,
                "html_url": "https://github.com/ktogias/gnostoa/pull/300#pullrequestreview-10",
            },
            {
                "id": 11,
                "author": "older-reviewer",
                "state": "COMMENTED",
                "submitted_at": "2026-09-19T16:39:30Z",
                "commit_id": "d" * 40,
                "html_url": "https://github.com/ktogias/gnostoa/pull/300#pullrequestreview-11",
            },
        ],
        "review_comments": [
            {
                "id": 20,
                "pull_request_review_id": 10,
                "author": "qodo-code-review[bot]",
                "created_at": "2026-09-19T16:40:31Z",
                "updated_at": "2026-09-19T16:40:31Z",
                "commit_id": "a" * 40,
                "body": "inline raw finding",
                "html_url": "https://github.com/ktogias/gnostoa/pull/300#discussion_r20",
            }
        ],
        "check_runs": [
            {
                "id": 30,
                "name": "fast",
                "head_sha": "a" * 40,
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
            "exact", by_id["github-review-10"]["subject_binding"]["status"]
        )
        self.assertEqual(
            "partial", by_id["github-review-11"]["subject_binding"]["status"]
        )
        self.assertEqual(
            "APPROVED",
            by_id["github-review-10"]["native"]["recommendation_state"],
        )

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
        self.assertIn("binding: false", rendered)
        self.assertNotIn("raw provider text", rendered)
        self.assertNotIn("inline raw finding", rendered)
        self.assertLess(len(rendered.encode("utf-8")), 32_768)

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
            ("issue_comments", "issue_comments"),
            ("reviews", "reviews"),
            ("review_comments", "review_comments"),
            ("check_runs", "check_runs"),
        ):
            with self.subTest(source=source):
                self.assertEqual(2, len(snapshot[payload_key]))
                self.assertEqual(2, snapshot["coverage"][source]["pages"])
                self.assertEqual(2, snapshot["coverage"][source]["count"])
                self.assertEqual("COMPLETE", snapshot["coverage"][source]["status"])

    def test_adapter_reports_partial_collection_for_each_source_page_error(
        self,
    ) -> None:
        adapter = _adapter()
        root = "https://api.github.com/repos/ktogias/gnostoa"
        cases = {
            "issue_comments": "https://api.github.com/page2/issues",
            "reviews": "https://api.github.com/page2/reviews",
            "review_comments": "https://api.github.com/page2/review-comments",
            "check_runs": "https://api.github.com/page2/check-runs",
        }

        for source, fail_url in cases.items():
            class PartialFake(_PagedFake):
                def get(self, url: str) -> tuple[Any, dict[str, str]]:
                    if url == fail_url:
                        raise adapter.ProviderReadError(
                            "simulated second-page failure"
                        )
                    return super().get(url)

            snapshot = adapter.collect_snapshot(
                PartialFake(_complete_replies(root)),
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
            "subject": {"head_sha": "a" * 40, "state": "open"},
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
            "subject": {"head_sha": "a" * 40},
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

    def test_workflow_is_protected_source_and_least_privilege(self) -> None:
        self.assertTrue(WORKFLOW_PATH.is_file(), "L1_WORKFLOW_UNAVAILABLE")
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = yaml.safe_load(text)

        self.assertIsInstance(workflow, dict)
        self.assertIn("workflow_run:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("schedule:", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertEqual({}, workflow.get("permissions"))

        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        collect = jobs.get("collect")
        publish = jobs.get("publish")
        self.assertIsInstance(collect, dict)
        self.assertIsInstance(publish, dict)

        self.assertEqual(
            {
                "contents": "read",
                "actions": "read",
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
            self.assertIn("github.event_name != 'workflow_dispatch'", condition)
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

        self.assertIn("tools/review_github_current_state.py", text)


if __name__ == "__main__":
    unittest.main()
