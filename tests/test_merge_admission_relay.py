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
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

from test_merge_evidence_github import _evidence, _snapshot

from tools import assurance_completeness, github_rest, merge_admission
from tools.review_check import MAX_REVIEW_DOCUMENT_DEPTH
from tools.verdict_cli import MAX_INPUT_BYTES

ROOT = Path(__file__).resolve().parents[1]
RELAY_PATH = ROOT / "ci" / "merge_admission_relay.py"
REPOSITORY = "ktogias/gnostoa"
HEAD = "a" * 40
OTHER = "f" * 40
CHECK_RUNS = f"https://api.github.com/repos/{REPOSITORY}/check-runs"
# The dedicated App's credential variable, by name only, and the App's id.
MA0_ENV = "GNOSTOA_MA0_TOKEN"
MA0_APP = 4242
OTHER_APP = 15368


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

    @staticmethod
    def url(path: str) -> str:
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
        "app": {"id": MA0_APP, "slug": "gnostoa-ma0"},
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
        failing = [c for c in verdict["criteria"] if c["status"] == "FAIL"]
        self.assertTrue(failing)
        failing[0]["reasons"] = ["x" * 1000] * 200
        planned = relay.plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertLessEqual(len(planned["summary"]), 60_000)
        self.assertLessEqual(len(planned["title"]), 255)


LATEST = (
    f"https://api.github.com/repos/{REPOSITORY}/commits/{HEAD}/check-runs"
    "?check_name=merge-admission&filter=latest&per_page=100"
)
EMPTY = {"total_count": 0, "check_runs": []}


class PublishTests(unittest.TestCase):
    """The check run is written at most once, as the dedicated App, then read back."""

    @staticmethod
    def _planned(conclusion: str = "success") -> dict[str, Any]:
        evidence, verdict = _allowing()
        code = 0 if conclusion == "success" else 1
        if conclusion != "success":
            verdict["status"] = "DENY"
        return _relay().plan(evidence, copy.deepcopy(evidence), verdict, code)

    def test_it_posts_one_completed_check_run_on_the_exact_head(self) -> None:
        planned = self._planned()
        client = _FakeClient(
            gets={LATEST: EMPTY, f"{CHECK_RUNS}/77": _posted(planned)},
            post=_posted(planned),
        )
        result = _relay().publish(
            client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
        )
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
        self.assertEqual(planned["summary"], payload["output"]["summary"])
        self.assertIn(f"{CHECK_RUNS}/77", client.reads)

    def test_a_read_back_that_differs_is_a_failure(self) -> None:
        relay = _relay()
        planned = self._planned()
        error = relay.PublicationError
        for field, value in (
            ("head_sha", OTHER),
            ("conclusion", "failure"),
            ("external_id", "0" * 64),
            ("name", "merge-admission-x"),
            ("status", "in_progress"),
            ("app", {"id": OTHER_APP}),
        ):
            with self.subTest(field):
                read = {**_posted(planned), field: value}
                client = _FakeClient(
                    gets={LATEST: EMPTY, f"{CHECK_RUNS}/77": read},
                    post=_posted(planned),
                )
                with self.assertRaises(error) as raised:
                    relay.publish(
                        client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
                    )
                self.assertEqual("MISMATCH", raised.exception.kind)
                self.assertEqual(1, len(client.posts))

    def test_an_unknown_outcome_is_read_back_never_reposted(self) -> None:
        relay = _relay()
        planned = self._planned()
        lost = github_rest.GitHubWriteError(
            "GitHub API HTTP 502", status=502, outcome_unknown=True
        )

        class _Written(_FakeClient):
            """The run appears in the latest view only after the lost write."""

            def get(self, url: str) -> tuple[Any, dict[str, str]]:
                if url == LATEST and self.posts:
                    self.reads.append(url)
                    return {"total_count": 1, "check_runs": [_posted(planned, 78)]}, {}
                return super().get(url)

        found = _Written(gets={LATEST: EMPTY}, post=lost)
        result = relay.publish(
            found, repository=REPOSITORY, planned=planned, app_id=MA0_APP
        )
        self.assertEqual(("PUBLISHED", 78), (result["result"], result["check_run_id"]))
        self.assertEqual(1, len(found.posts))
        absent = _FakeClient(gets={LATEST: EMPTY}, post=lost)
        error = relay.PublicationError
        with self.assertRaises(error) as raised:
            relay.publish(
                absent, repository=REPOSITORY, planned=planned, app_id=MA0_APP
            )
        self.assertEqual("UNKNOWN", raised.exception.kind)
        self.assertEqual(1, len(absent.posts))

    def test_a_listing_past_one_page_is_not_trusted(self) -> None:
        """A latest view that does not hold every run it counts cannot show the
        posted one is absent, nor that it is present."""
        relay = _relay()
        planned = self._planned()
        client = _FakeClient(
            gets={LATEST: {"total_count": 2, "check_runs": [_posted(planned, 78)]}}
        )
        error = relay.PublicationError
        with self.assertRaises(error) as raised:
            relay.publish(
                client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
            )
        self.assertEqual("UNKNOWN", raised.exception.kind)
        self.assertEqual([], client.posts)

    def test_a_refused_write_is_not_retried(self) -> None:
        relay = _relay()
        planned = self._planned()
        client = _FakeClient(
            gets={LATEST: EMPTY},
            post=github_rest.GitHubWriteError("GitHub API HTTP 403", status=403),
        )
        error = relay.PublicationError
        with self.assertRaises(error) as raised:
            relay.publish(
                client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
            )
        self.assertEqual("REFUSED", raised.exception.kind)
        self.assertEqual(1, len(client.posts))

    def test_superseded_is_never_written(self) -> None:
        evidence, verdict = _allowing()
        moved = copy.deepcopy(evidence)
        moved["subject"]["head_commit"] = OTHER
        planned = _relay().plan(evidence, moved, verdict, 0)
        client = _FakeClient()
        result = _relay().publish(
            client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
        )
        self.assertEqual("SUPERSEDED", result["result"])
        self.assertEqual([], client.posts)


class IdempotentPublicationTests(unittest.TestCase):
    """Round 1 (Claude, Octopus and CodeAnt on #426): a verdict already published
    by the dedicated App as the head's latest run is not posted again, and a run is
    ours only when the dedicated App posted it."""

    @staticmethod
    def _planned() -> dict[str, Any]:
        evidence, verdict = _allowing()
        return _relay().plan(evidence, copy.deepcopy(evidence), verdict, 0)

    @staticmethod
    def _run(planned: dict[str, Any], run_id: int, app: int) -> dict[str, Any]:
        return {**_posted(planned, run_id), "app": {"id": app, "slug": "x"}}

    def test_the_same_verdict_already_latest_is_not_posted_again(self) -> None:
        planned = self._planned()
        mine = self._run(planned, 90, MA0_APP)
        client = _FakeClient(gets={LATEST: {"total_count": 1, "check_runs": [mine]}})
        result = _relay().publish(
            client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
        )
        self.assertEqual(("PUBLISHED", 90), (result["result"], result["check_run_id"]))
        self.assertEqual([], client.posts)

    def test_another_app_s_run_is_not_ours(self) -> None:
        planned = self._planned()
        foreign = self._run(planned, 91, OTHER_APP)
        posted = self._run(planned, 92, MA0_APP)
        client = _FakeClient(
            gets={
                LATEST: {"total_count": 1, "check_runs": [foreign]},
                f"{CHECK_RUNS}/92": posted,
            },
            post=posted,
        )
        result = _relay().publish(
            client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
        )
        self.assertEqual(92, result["check_run_id"])
        self.assertEqual(1, len(client.posts))

    def test_a_read_back_from_another_app_is_a_mismatch(self) -> None:
        relay = _relay()
        planned = self._planned()
        client = _FakeClient(
            gets={LATEST: EMPTY, f"{CHECK_RUNS}/93": self._run(planned, 93, OTHER_APP)},
            post=self._run(planned, 93, OTHER_APP),
        )
        error = relay.PublicationError
        with self.assertRaises(error) as raised:
            relay.publish(
                client, repository=REPOSITORY, planned=planned, app_id=MA0_APP
            )
        self.assertEqual("MISMATCH", raised.exception.kind)
        self.assertEqual(1, len(client.posts))

    def test_a_head_other_than_the_subject_s_supersedes(self) -> None:
        """Octopus on #426: a push between selecting the subject and evaluating it
        moves both snapshots to the new head, while the readback covered the old
        one, so the evaluation is not the subject's."""
        evidence, verdict = _allowing()
        planned = _relay().plan(
            evidence, copy.deepcopy(evidence), verdict, 0, expected_head=OTHER
        )
        self.assertEqual("SUPERSEDED", planned["action"])
        same = _relay().plan(
            evidence, copy.deepcopy(evidence), verdict, 0, expected_head=HEAD
        )
        self.assertEqual("PUBLISH", same["action"])


class CommandTests(unittest.TestCase):
    """The command reads files written by the workflow's own steps, in its work
    directory."""

    @staticmethod
    def _files(directory: Path, *, code: int = 0) -> list[str]:
        evidence, verdict = _allowing()
        (directory / "evaluated.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        (directory / "current.json").write_text(json.dumps(evidence), encoding="utf-8")
        (directory / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
        return [
            "--repository",
            REPOSITORY,
            "--work-dir",
            str(directory),
            "--expected-head",
            HEAD,
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

    @staticmethod
    def _main(relay: Any, argv: list[str], credential: str, **patches: Any) -> int:
        with (
            mock.patch.dict(os.environ, {MA0_ENV: credential}),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            if not patches:
                return int(relay.main(argv))
            with mock.patch.multiple(relay, **patches):
                return int(relay.main(argv))

    def test_without_the_app_s_credential_it_publishes_nothing(self) -> None:
        """Shadow mode: before `gnostoa-ma0` exists, the run records its verdict
        and its plan, and constructs no client."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            with mock.patch.object(
                relay.github_rest,
                "GitHubRestClient",
                side_effect=AssertionError("no client"),
            ):
                code = self._main(relay, argv, "")
            self.assertEqual(0, code)
            result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            self.assertEqual("SHADOW", result["result"])
            self.assertEqual("success", result["planned"]["conclusion"])

    def test_publishing_needs_the_app_s_id(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            code = self._main(relay, self._files(directory), "x" * 40)
            self.assertEqual(2, code)
            self.assertFalse((directory / "result.json").exists())

    def test_a_publication_failure_fails_the_run(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [*self._files(directory), "--app-id", str(MA0_APP)]
            refusing = _FakeClient(
                gets={LATEST: EMPTY},
                post=github_rest.GitHubWriteError("GitHub API HTTP 403", status=403),
            )
            code = self._main(
                relay, argv, "x" * 40, _client=mock.Mock(return_value=refusing)
            )
            self.assertEqual(1, code)

    def test_inputs_outside_the_work_directory_are_refused(self) -> None:
        """SonarCloud S8707 on #426: every file the command reads or writes is
        confined to its work directory."""
        relay = _relay()
        files = {
            "--evaluated": "evaluated.json",
            "--current": "current.json",
            "--verdict": "verdict.json",
            "--output": "result.json",
        }
        for flag, name in files.items():
            with self.subTest(flag=flag):
                with (
                    tempfile.TemporaryDirectory() as raw,
                    tempfile.TemporaryDirectory() as other,
                ):
                    directory = Path(raw)
                    argv = self._files(directory)
                    outside = Path(other) / name
                    if flag != "--output":
                        outside.write_bytes((directory / name).read_bytes())
                    argv[argv.index(flag) + 1] = str(outside)
                    code = self._main(relay, argv, "")
                    self.assertEqual(2, code)
                    self.assertFalse((directory / "result.json").exists())
                    if flag == "--output":
                        self.assertFalse(outside.exists())

    def test_an_unreadable_evidence_file_fails_closed(self) -> None:
        """cubic on #426: a missing, unparsable, non-object or over-bound evidence
        file stops the command before any plan, publication or result."""
        relay = _relay()
        corruptions: dict[str, bytes | None] = {
            "missing": None,
            "not json": b"{",
            "not an object": b"[]",
            "over its bound": b" " * (MAX_INPUT_BYTES + 1),
        }
        for label in ("evaluated", "current"):
            for name, content in corruptions.items():
                with self.subTest(file=label, corruption=name):
                    with tempfile.TemporaryDirectory() as raw:
                        directory = Path(raw)
                        argv = self._files(directory)
                        path = directory / f"{label}.json"
                        if content is None:
                            path.unlink()
                        else:
                            path.write_bytes(content)
                        self.assertEqual(2, self._main(relay, argv, ""))
                        self.assertFalse((directory / "result.json").exists())

    def test_evidence_is_read_under_the_owned_input_rules(self) -> None:
        """The evidence is read as every verdict command reads its input
        (`tools.verdict_cli.read_json_file`): a duplicated field, or a document past
        the depth bound, is refused as `knowledge merge-admission` refuses it."""
        relay = _relay()
        evidence, _ = _allowing()
        text = json.dumps(evidence)
        duplicated = text[:-1] + ', "subject": ' + json.dumps(evidence["subject"]) + "}"
        deep = copy.deepcopy(evidence)
        level: list[Any] = []
        deep["nested"] = level
        for _ in range(MAX_REVIEW_DOCUMENT_DEPTH + 1):
            inner: list[Any] = []
            level.append(inner)
            level = inner
        documents = {
            "a duplicated field": duplicated,
            "past the depth bound": json.dumps(deep),
        }
        for label in ("evaluated", "current"):
            for name, content in documents.items():
                with self.subTest(file=label, document=name):
                    with tempfile.TemporaryDirectory() as raw:
                        directory = Path(raw)
                        argv = self._files(directory)
                        (directory / f"{label}.json").write_text(
                            content, encoding="utf-8"
                        )
                        self.assertEqual(2, self._main(relay, argv, ""))
                        self.assertFalse((directory / "result.json").exists())

    def test_a_verdict_with_a_duplicated_field_is_no_verdict(self) -> None:
        """Read under the same rules, a verdict whose `status` is given twice is no
        verdict: the plan fails, and never allows."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            path = directory / "verdict.json"
            text = path.read_text(encoding="utf-8")
            path.write_text(text[:-1] + ', "status": "ALLOW"}', encoding="utf-8")
            self.assertEqual(0, self._main(relay, argv, ""))
            result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            self.assertEqual("failure", result["planned"]["conclusion"])

    def test_a_moved_current_head_supersedes_through_the_command(self) -> None:
        """The command reads the current evidence it is given: a head that moved
        between the two snapshots supersedes the verdict."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            path = directory / "current.json"
            evidence = json.loads(path.read_text(encoding="utf-8"))
            evidence["subject"]["head_commit"] = OTHER
            path.write_text(json.dumps(evidence), encoding="utf-8")
            self.assertEqual(0, self._main(relay, argv, ""))
            result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            self.assertEqual("SUPERSEDED", result["planned"]["action"])

    def test_an_expected_head_that_is_no_exact_sha_is_refused(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            argv[argv.index("--expected-head") + 1] = "abc"
            self.assertEqual(2, self._main(relay, argv, ""))
            self.assertFalse((directory / "result.json").exists())

    def test_an_evidence_head_that_is_no_exact_sha_is_refused(self) -> None:
        """Claude on #426: the head is checked where it is read, as L1 checks it."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            path = directory / "evaluated.json"
            evidence = json.loads(path.read_text(encoding="utf-8"))
            evidence["subject"]["head_commit"] = "abc"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            self.assertEqual(2, self._main(relay, argv, ""))


if __name__ == "__main__":
    unittest.main()
