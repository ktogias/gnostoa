"""The merge-admission relay's publication (#407, MA0 slice 1b.4; Decision 0112 item 5).

The relay runs only from protected main. It never decides admission: it publishes
the existing verdict as the `merge-admission` check run on the exact evaluated
head, and only while the evidence the verdict rests on is still current.
"""

from __future__ import annotations

import copy
import functools
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

from test_merge_evidence_github import _evidence, _snapshot

from tools import assurance_completeness, github_rest, merge_admission

ROOT = Path(__file__).resolve().parents[1]
RELAY_PATH = ROOT / "ci" / "merge_admission_relay.py"
REPOSITORY = "ktogias/gnostoa"
HEAD = "a" * 40
OTHER = "f" * 40
CHECK_RUNS = f"https://api.github.com/repos/{REPOSITORY}/check-runs"
# The dedicated App's credential variable, by name only.
TOKEN_ENV = "GNOSTOA_MA0_TOKEN"


@functools.cache
def _relay() -> Any:
    """The relay, loaded once, so its exception classes are the ones it raises."""
    spec = importlib.util.spec_from_file_location(
        "gnostoa_merge_admission_relay", RELAY_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("merge-admission relay is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verdict(evidence: dict[str, Any]) -> dict[str, Any]:
    return merge_admission.evaluate(
        evidence,
        declaration=assurance_completeness.load_declaration(
            ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
        ),
        change_policy=merge_admission.load_policy(
            ROOT / "policy" / "change-control.yaml", project_root=ROOT
        ),
    )


def _allowing() -> tuple[dict[str, Any], dict[str, Any]]:
    """Evidence and an ALLOW verdict over it, the verdict forced for the plan's
    tests: the relay never recomputes or second-guesses the verdict's criteria."""

    evidence = _evidence(_snapshot())
    verdict = _verdict(evidence)
    verdict["status"] = "ALLOW"
    verdict["criteria"] = [
        {**c, "status": "PASS", "reasons": []} for c in verdict["criteria"]
    ]
    return evidence, verdict


class _FakeClient:
    """Answers only what it was given; every write is recorded."""

    def __init__(self, gets: dict[str, Any] | None = None, post: Any = None) -> None:
        self.gets = gets or {}
        self.post_answer = post
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.reads: list[str] = []

    def url(self, path: str) -> str:
        return f"https://api.github.com/{path.lstrip('/')}"

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.reads.append(url)
        if url not in self.gets:
            raise AssertionError(f"unexpected read {url}")
        answer = self.gets[url]
        if isinstance(answer, BaseException):
            raise answer
        return answer, {}

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        self.posts.append((url, copy.deepcopy(payload)))
        if isinstance(self.post_answer, BaseException):
            raise self.post_answer
        return self.post_answer


def _posted(planned: dict[str, Any], run_id: int = 77) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": "merge-admission",
        "head_sha": planned["head_sha"],
        "status": "completed",
        "conclusion": planned["conclusion"],
        "external_id": planned["external_id"],
        "app": {"slug": "gnostoa-ma0"},
    }


class PublicationPlanTests(unittest.TestCase):
    """What is published, decided from the evaluated and the current evidence."""

    def test_an_allow_verdict_on_current_evidence_publishes_success(self) -> None:
        evidence, verdict = _allowing()
        planned = _relay().plan(evidence, copy.deepcopy(evidence), verdict, 0)
        self.assertEqual("PUBLISH", planned["action"])
        self.assertEqual("success", planned["conclusion"])
        self.assertEqual(HEAD, planned["head_sha"])

    def test_a_deny_verdict_publishes_failure_naming_its_criteria(self) -> None:
        evidence = _evidence(_snapshot())
        verdict = _verdict(evidence)
        failing = [c["id"] for c in verdict["criteria"] if c["status"] == "FAIL"]
        self.assertEqual("DENY", verdict["status"])
        self.assertTrue(failing)
        planned = _relay().plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertEqual("PUBLISH", planned["action"])
        self.assertEqual("failure", planned["conclusion"])
        for criterion in failing:
            self.assertIn(criterion, planned["title"])

    def test_only_a_consistent_allow_is_ever_success(self) -> None:
        """A failed run, a missing or malformed verdict, a verdict for another
        subject, and an ALLOW the command did not exit 0 for, all publish failure."""

        relay = _relay()
        evidence, verdict = _allowing()
        other_subject = copy.deepcopy(verdict)
        other_subject["subject"]["head_commit"] = OTHER
        other_pull = copy.deepcopy(verdict)
        other_pull["subject"]["change_request"]["id"] = "301"
        for name, document, code in (
            ("the command failed", verdict, 2),
            ("an allow with a deny exit", verdict, 1),
            ("no verdict", None, 2),
            ("not a verdict", {"status": "ALLOW"}, 0),
            (
                "a verdict without its schema",
                {k: v for k, v in verdict.items() if k != "schema"},
                0,
            ),
            ("another head's verdict", other_subject, 0),
            ("another pull request's verdict", other_pull, 0),
        ):
            with self.subTest(name):
                planned = relay.plan(evidence, copy.deepcopy(evidence), document, code)
                self.assertEqual("PUBLISH", planned["action"])
                self.assertEqual("failure", planned["conclusion"])

    def test_changed_evidence_supersedes_the_verdict(self) -> None:
        """The head-move invariant (d), and an edit with the head unchanged: the
        evaluated verdict is never published once its evidence has changed."""

        relay = _relay()
        evidence, verdict = _allowing()
        moved = copy.deepcopy(evidence)
        moved["subject"]["head_commit"] = OTHER
        body_edited = copy.deepcopy(evidence)
        body_edited["links"] = {"work_items": ["#407"], "decisions": []}
        unapproved = copy.deepcopy(evidence)
        unapproved["reviews"] = []
        for name, current in (
            ("the head moved", moved),
            ("the description's links changed", body_edited),
            ("the approval went away", unapproved),
        ):
            with self.subTest(name):
                planned = relay.plan(evidence, current, verdict, 0)
                self.assertEqual("SUPERSEDED", planned["action"])

    def test_observation_times_alone_do_not_supersede(self) -> None:
        relay = _relay()
        evidence, verdict = _allowing()
        current = copy.deepcopy(evidence)
        for receipt in current["receipts"]:
            receipt["observed_at"] = "2026-10-12T18:00:00Z"
        self.assertEqual("PUBLISH", relay.plan(evidence, current, verdict, 0)["action"])

    def test_the_external_id_names_exactly_what_was_evaluated(self) -> None:
        relay = _relay()
        evidence, verdict = _allowing()
        first = relay.plan(evidence, copy.deepcopy(evidence), verdict, 0)
        again = relay.plan(copy.deepcopy(evidence), copy.deepcopy(evidence), verdict, 0)
        self.assertEqual(first["external_id"], again["external_id"])
        self.assertRegex(first["external_id"], r"^[0-9a-f]{64}$")
        denied = relay.plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertNotEqual(first["external_id"], denied["external_id"])

    def test_the_summary_is_bounded(self) -> None:
        relay = _relay()
        evidence = _evidence(_snapshot())
        verdict = _verdict(evidence)
        # A failing criterion's reasons are what the summary lists.
        failing = next(c for c in verdict["criteria"] if c["status"] == "FAIL")
        failing["reasons"] = ["x" * 1000] * 200
        planned = relay.plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertLessEqual(len(planned["summary"]), 60_000)
        self.assertLessEqual(len(planned["title"]), 255)


class PublishTests(unittest.TestCase):
    """The check run is written once, then read back."""

    def _planned(self, conclusion: str = "success") -> dict[str, Any]:
        evidence, verdict = _allowing()
        code = 0 if conclusion == "success" else 1
        if conclusion != "success":
            verdict["status"] = "DENY"
        return _relay().plan(evidence, copy.deepcopy(evidence), verdict, code)

    def test_it_posts_one_completed_check_run_on_the_exact_head(self) -> None:
        planned = self._planned()
        client = _FakeClient(
            gets={f"{CHECK_RUNS}/77": _posted(planned)}, post=_posted(planned)
        )
        result = _relay().publish(client, repository=REPOSITORY, planned=planned)
        self.assertEqual("PUBLISHED", result["result"])
        self.assertEqual(77, result["check_run_id"])
        self.assertEqual(1, len(client.posts))
        url, payload = client.posts[0]
        self.assertEqual(CHECK_RUNS, url)
        self.assertEqual(
            {
                "name": "merge-admission",
                "head_sha": HEAD,
                "status": "completed",
                "conclusion": "success",
                "external_id": planned["external_id"],
            },
            {
                k: payload[k]
                for k in ("name", "head_sha", "status", "conclusion", "external_id")
            },
        )
        self.assertEqual(planned["title"], payload["output"]["title"])
        self.assertIn(f"{CHECK_RUNS}/77", client.reads)

    def test_a_read_back_that_differs_is_a_failure(self) -> None:
        planned = self._planned()
        for field, value in (
            ("head_sha", OTHER),
            ("conclusion", "failure"),
            ("external_id", "0" * 64),
            ("name", "merge-admission-x"),
            ("status", "in_progress"),
        ):
            with self.subTest(field):
                read = {**_posted(planned), field: value}
                client = _FakeClient(
                    gets={f"{CHECK_RUNS}/77": read}, post=_posted(planned)
                )
                with self.assertRaises(_relay().PublicationError) as raised:
                    _relay().publish(client, repository=REPOSITORY, planned=planned)
                self.assertEqual("MISMATCH", raised.exception.kind)

    def test_an_unknown_outcome_is_read_back_never_reposted(self) -> None:
        planned = self._planned()
        lost = github_rest.GitHubWriteError(
            "GitHub API HTTP 502", status=502, outcome_unknown=True
        )
        listing = (
            f"https://api.github.com/repos/{REPOSITORY}/commits/{HEAD}/check-runs"
            "?check_name=merge-admission&filter=all&per_page=100"
        )
        found = _FakeClient(
            gets={listing: {"total_count": 1, "check_runs": [_posted(planned, 78)]}},
            post=lost,
        )
        result = _relay().publish(found, repository=REPOSITORY, planned=planned)
        self.assertEqual("PUBLISHED", result["result"])
        self.assertEqual(78, result["check_run_id"])
        self.assertEqual(1, len(found.posts))
        absent = _FakeClient(
            gets={listing: {"total_count": 0, "check_runs": []}}, post=lost
        )
        with self.assertRaises(_relay().PublicationError) as raised:
            _relay().publish(absent, repository=REPOSITORY, planned=planned)
        self.assertEqual("UNKNOWN", raised.exception.kind)
        self.assertEqual(1, len(absent.posts))

    def test_a_listing_past_one_page_is_not_trusted(self) -> None:
        """After an unknown outcome, a listing that does not hold every run cannot
        show the posted one is absent, nor that it is present."""
        planned = self._planned()
        lost = github_rest.GitHubWriteError(
            "GitHub API HTTP 502", status=502, outcome_unknown=True
        )
        listing = (
            f"https://api.github.com/repos/{REPOSITORY}/commits/{HEAD}/check-runs"
            "?check_name=merge-admission&filter=all&per_page=100"
        )
        client = _FakeClient(
            gets={listing: {"total_count": 101, "check_runs": [_posted(planned, 78)]}},
            post=lost,
        )
        with self.assertRaises(_relay().PublicationError) as raised:
            _relay().publish(client, repository=REPOSITORY, planned=planned)
        self.assertEqual("UNKNOWN", raised.exception.kind)

    def test_a_refused_write_is_not_retried(self) -> None:
        planned = self._planned()
        client = _FakeClient(
            post=github_rest.GitHubWriteError("GitHub API HTTP 403", status=403)
        )
        with self.assertRaises(_relay().PublicationError) as raised:
            _relay().publish(client, repository=REPOSITORY, planned=planned)
        self.assertEqual("REFUSED", raised.exception.kind)
        self.assertEqual(1, len(client.posts))

    def test_superseded_is_never_written(self) -> None:
        evidence, verdict = _allowing()
        moved = copy.deepcopy(evidence)
        moved["subject"]["head_commit"] = OTHER
        planned = _relay().plan(evidence, moved, verdict, 0)
        client = _FakeClient()
        result = _relay().publish(client, repository=REPOSITORY, planned=planned)
        self.assertEqual("SUPERSEDED", result["result"])
        self.assertEqual([], client.posts)


class CommandTests(unittest.TestCase):
    """The command reads files written by the workflow's own steps."""

    def _files(self, directory: Path, *, code: int = 0) -> list[str]:
        evidence, verdict = _allowing()
        (directory / "evaluated.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        (directory / "current.json").write_text(json.dumps(evidence), encoding="utf-8")
        (directory / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
        return [
            "--repository",
            REPOSITORY,
            "--evaluated",
            str(directory / "evaluated.json"),
            "--current",
            str(directory / "current.json"),
            "--verdict",
            str(directory / "verdict.json"),
            "--verdict-exit",
            str(code),
            "--output",
            str(directory / "result.json"),
        ]

    def test_without_the_app_token_it_publishes_nothing(self) -> None:
        """Shadow mode: before `gnostoa-ma0` exists, the run records its verdict
        and its plan, and constructs no client."""

        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            with (
                mock.patch.dict(os.environ, {TOKEN_ENV: ""}),
                mock.patch.object(
                    relay.github_rest,
                    "GitHubRestClient",
                    side_effect=AssertionError("no client"),
                ),
                redirect_stdout(io.StringIO()),
            ):
                code = relay.main(argv)
            self.assertEqual(0, code)
            result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            self.assertEqual("SHADOW", result["result"])
            self.assertEqual("success", result["planned"]["conclusion"])

    def test_a_publication_failure_fails_the_run(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            refusing = _FakeClient(
                post=github_rest.GitHubWriteError("GitHub API HTTP 403", status=403)
            )
            with (
                mock.patch.dict(os.environ, {TOKEN_ENV: "x" * 40}),
                mock.patch.object(relay, "_client", return_value=refusing),
                redirect_stdout(io.StringIO()),
            ):
                code = relay.main(argv)
            self.assertEqual(1, code)


if __name__ == "__main__":
    unittest.main()
