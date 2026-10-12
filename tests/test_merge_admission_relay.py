"""The merge-admission relay's publication (#407, MA0 slice 1b.4; Decision 0112 item 5).

The relay runs only from protected main. It never decides admission: it publishes
the existing verdict as the `merge-admission` check run on the exact evaluated
head, and only while the evidence the verdict rests on is still current.
"""

from __future__ import annotations

import contextlib
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
        planned = _plan(evidence, copy.deepcopy(evidence), verdict, 0)
        self.assertEqual("PUBLISH", planned["action"])
        self.assertEqual("success", planned["conclusion"])
        self.assertEqual(HEAD, planned["head_sha"])

    def test_a_deny_verdict_publishes_failure_naming_its_criteria(self) -> None:
        evidence = _evidence(_snapshot())
        verdict = _verdict(evidence)
        failing = [c["id"] for c in verdict["criteria"] if c["status"] == "FAIL"]
        self.assertEqual("DENY", verdict["status"])
        self.assertTrue(failing)
        planned = _plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertEqual("PUBLISH", planned["action"])
        self.assertEqual("failure", planned["conclusion"])
        for criterion in failing:
            self.assertIn(criterion, planned["title"])

    def test_only_a_consistent_allow_is_ever_success(self) -> None:
        """A failed run, a missing or malformed verdict, a verdict for another
        subject, and an ALLOW the command did not exit 0 for, all publish failure."""

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
                planned = _plan(evidence, copy.deepcopy(evidence), document, code)
                self.assertEqual("PUBLISH", planned["action"])
                self.assertEqual("failure", planned["conclusion"])

    def test_changed_evidence_supersedes_the_verdict(self) -> None:
        """The head-move invariant (d), and an edit with the head unchanged: the
        evaluated verdict is never published once its evidence has changed."""

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
                planned = _plan(evidence, current, verdict, 0)
                self.assertEqual("SUPERSEDED", planned["action"])

    def test_observation_times_alone_do_not_supersede(self) -> None:
        evidence, verdict = _allowing()
        current = copy.deepcopy(evidence)
        for receipt in current["receipts"]:
            receipt["observed_at"] = "2026-10-12T18:00:00Z"
        self.assertEqual("PUBLISH", _plan(evidence, current, verdict, 0)["action"])

    def test_the_external_id_names_exactly_what_was_evaluated(self) -> None:
        evidence, verdict = _allowing()
        first = _plan(evidence, copy.deepcopy(evidence), verdict, 0)
        again = _plan(copy.deepcopy(evidence), copy.deepcopy(evidence), verdict, 0)
        self.assertEqual(first["external_id"], again["external_id"])
        self.assertRegex(first["external_id"], r"^[0-9a-f]{64}$")
        denied = _plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertNotEqual(first["external_id"], denied["external_id"])

    def test_the_summary_is_bounded(self) -> None:
        evidence = _evidence(_snapshot())
        verdict = _verdict(evidence)
        # A failing criterion's reasons are what the summary lists.
        failing = [c for c in verdict["criteria"] if c["status"] == "FAIL"]
        self.assertTrue(failing)
        failing[0]["reasons"] = ["x" * 1000] * 200
        planned = _plan(evidence, copy.deepcopy(evidence), verdict, 1)
        self.assertLessEqual(len(planned["summary"]), 60_000)
        self.assertLessEqual(len(planned["title"]), 255)


LATEST = (
    f"https://api.github.com/repos/{REPOSITORY}/commits/{HEAD}/check-runs"
    "?check_name=merge-admission&filter=latest&per_page=100"
)
EMPTY = {"total_count": 0, "check_runs": []}
# This workflow run, as the runner names it: the protected facts a run correlates by.
RUN_ID = 901
MAIN = "b" * 40
# The guard's nonce, when a guarded merge dispatched the run (G1, #426 6132395441).
NONCE = "ab" * 16
CORRELATION = {
    "workflow_run_id": RUN_ID,
    "run_attempt": 1,
    "protected_revision": MAIN,
    "nonce": NONCE,
    "unbundled_evidence_sha256": "c" * 64,
}
PENDING_ID = "pending:901:1"


POPULATION = {
    "coverage": "COMPLETE",
    "pulls": [{"pull_number": 300, "head": HEAD}, {"pull_number": 301, "head": OTHER}],
}


def _plan(
    evaluated: dict[str, Any],
    current: dict[str, Any],
    verdict: object,
    code: int,
    *,
    evaluated_population: Any = None,
    current_population: Any = None,
    **options: Any,
) -> dict[str, Any]:
    """The relay's plan, both snapshots observing the same unique population unless a
    test says otherwise."""
    planned: dict[str, Any] = _relay().plan(
        evaluated,
        current,
        verdict,
        code,
        evaluated_population=copy.deepcopy(
            POPULATION if evaluated_population is None else evaluated_population
        ),
        current_population=copy.deepcopy(
            POPULATION if current_population is None else current_population
        ),
        **options,
    )
    return planned


def _with(*pulls: tuple[int, str]) -> dict[str, Any]:
    return {
        "coverage": "COMPLETE",
        "pulls": [{"pull_number": number, "head": head} for number, head in pulls],
    }


class SharedHeadTests(unittest.TestCase):
    """H1 (the Decisions Router on #426, 6131149850): a check run belongs to a commit,
    so a success is published only when the complete open population shows this
    pull request alone at its exact head. The neutral verdict is unchanged."""

    def test_a_unique_head_with_an_allow_is_a_success(self) -> None:
        evidence, verdict = _allowing()
        planned = _plan(evidence, copy.deepcopy(evidence), verdict, 0)
        self.assertEqual(
            ("PUBLISH", "success"), (planned["action"], planned["conclusion"])
        )

    def test_a_shared_head_never_borrows_a_success(self) -> None:
        evidence, verdict = _allowing()
        shared = _with((300, HEAD), (302, HEAD), (301, OTHER))
        planned = _plan(
            evidence,
            copy.deepcopy(evidence),
            verdict,
            0,
            evaluated_population=shared,
            current_population=shared,
        )
        self.assertEqual(
            ("PUBLISH", "failure"), (planned["action"], planned["conclusion"])
        )
        self.assertIn("#300", planned["title"])
        self.assertIn("#302", planned["title"])
        self.assertNotIn("#301", planned["title"])

    def test_a_population_that_contradicts_the_subject_is_no_success(self) -> None:
        evidence, verdict = _allowing()
        for name, population in (
            ("this pull request missing", _with((301, OTHER))),
            ("listed at another head", _with((300, OTHER))),
        ):
            with self.subTest(name):
                planned = _plan(
                    evidence,
                    copy.deepcopy(evidence),
                    verdict,
                    0,
                    evaluated_population=population,
                    current_population=population,
                )
                self.assertEqual("failure", planned["conclusion"])
                self.assertIn("do not show this one at its head", planned["title"])

    def test_a_head_other_than_the_subject_s_supersedes(self) -> None:
        """Octopus on #426: a push between selecting the subject and evaluating it
        moves both snapshots to the new head, while the readback covered the old
        one, so the evaluation is not the subject's."""
        evidence, verdict = _allowing()
        planned = _plan(
            evidence, copy.deepcopy(evidence), verdict, 0, expected_head=OTHER
        )
        self.assertEqual("SUPERSEDED", planned["action"])
        same = _plan(evidence, copy.deepcopy(evidence), verdict, 0, expected_head=HEAD)
        self.assertEqual("PUBLISH", same["action"])

    def test_a_population_that_changes_between_the_snapshots_supersedes(self) -> None:
        evidence, verdict = _allowing()
        for name, current in (
            ("a peer added", _with((300, HEAD), (301, OTHER), (302, HEAD))),
            ("a peer moved to the head", _with((300, HEAD), (301, HEAD))),
            ("a peer closed", _with((300, HEAD))),
        ):
            with self.subTest(name):
                planned = _plan(
                    evidence,
                    copy.deepcopy(evidence),
                    verdict,
                    0,
                    current_population=current,
                )
                self.assertEqual("SUPERSEDED", planned["action"])

    def test_recovery_follows_a_fresh_unique_population(self) -> None:
        evidence, verdict = _allowing()
        shared = _with((300, HEAD), (302, HEAD))
        blocked = _plan(
            evidence,
            copy.deepcopy(evidence),
            verdict,
            0,
            evaluated_population=shared,
            current_population=shared,
        )
        recovered = _plan(evidence, copy.deepcopy(evidence), verdict, 0)
        self.assertEqual(
            ("failure", "success"), (blocked["conclusion"], recovered["conclusion"])
        )
        self.assertNotEqual(blocked["external_id"], recovered["external_id"])


class _Provider(_FakeClient):
    """A provider whose latest view follows the runs it holds, so a write changes what
    the next read sees, as GitHub's does. Every write is recorded."""

    def __init__(self, runs: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self.runs = [copy.deepcopy(run) for run in runs or []]
        self.patches: list[tuple[str, dict[str, Any]]] = []
        self.next_id = 500
        self.lose_write = False
        self.drop_write = False
        self.refuse_write = False
        self.reads_as: dict[int, dict[str, Any]] = {}

    def latest_view(self) -> dict[str, Any]:
        latest: dict[int, dict[str, Any]] = {}
        for run in self.runs:
            if run["head_sha"] != HEAD or run["name"] != "merge-admission":
                continue
            app = run["app"]["id"]
            if app not in latest or run["id"] > latest[app]["id"]:
                latest[app] = run
        runs = sorted(latest.values(), key=lambda run: run["id"])
        return {"total_count": len(runs), "check_runs": copy.deepcopy(runs)}

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.reads.append(url)
        if url == LATEST:
            return self.latest_view(), {}
        for run in self.runs:
            if url == f"{CHECK_RUNS}/{run['id']}":
                return {**copy.deepcopy(run), **self.reads_as.get(run["id"], {})}, {}
        raise AssertionError(f"unexpected read {url}")

    def _fail(self) -> None:
        if self.refuse_write:
            raise github_rest.GitHubWriteError("GitHub API HTTP 403", status=403)

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        self.posts.append((url, copy.deepcopy(payload)))
        if url != CHECK_RUNS:
            raise AssertionError(f"unexpected write {url}")
        self._fail()
        if self.drop_write:
            raise github_rest.GitHubWriteError(
                "GitHub API HTTP 502", status=502, outcome_unknown=True
            )
        self.next_id += 1
        run = {
            "id": self.next_id,
            "app": {"id": MA0_APP, "slug": "gnostoa-ma0"},
            "conclusion": None,
            **copy.deepcopy(payload),
        }
        self.runs.append(run)
        if self.lose_write:
            raise github_rest.GitHubWriteError(
                "GitHub API HTTP 502", status=502, outcome_unknown=True
            )
        return copy.deepcopy(run)

    def patch(self, url: str, payload: dict[str, Any]) -> Any:
        self.patches.append((url, copy.deepcopy(payload)))
        self._fail()
        for run in self.runs:
            if url == f"{CHECK_RUNS}/{run['id']}":
                run.update(copy.deepcopy(payload))
                if self.lose_write:
                    raise github_rest.GitHubWriteError(
                        "GitHub API HTTP 502", status=502, outcome_unknown=True
                    )
                return copy.deepcopy(run)
        raise AssertionError(f"unexpected write {url}")


def _run(
    run_id: int,
    *,
    conclusion: str | None = "success",
    app: int = MA0_APP,
    external_id: str = "e" * 64,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": "merge-admission",
        "head_sha": HEAD,
        "status": "completed" if conclusion else "in_progress",
        "conclusion": conclusion,
        "external_id": external_id,
        "app": {"id": app, "slug": "x"},
        "output": {"title": "t", "summary": "s", "text": ""},
    }


def _planned(conclusion: str = "success", action: str = "PUBLISH") -> dict[str, Any]:
    evidence, verdict = _allowing()
    code = 0
    if conclusion != "success":
        verdict["status"] = "DENY"
        code = 1
    planned = _plan(evidence, copy.deepcopy(evidence), verdict, code)
    planned["action"] = action
    return planned


def _publish(
    provider: _Provider, planned: dict[str, Any], record: dict[str, Any] | None
) -> dict[str, Any]:
    result: dict[str, Any] = _relay().publish(
        provider,
        repository=REPOSITORY,
        planned=planned,
        app_id=MA0_APP,
        record=record,
        correlation=CORRELATION,
    )
    return result


class InvalidationTests(unittest.TestCase):
    """F1 part 2 (the Decisions Router on #426, 6130207025): before anything is
    acquired again, a success the dedicated App published on the head stops
    standing. A pending run of the App replaces it until this run completes."""

    @staticmethod
    def _invalidate(provider: _Provider) -> dict[str, Any]:
        record: dict[str, Any] = _relay().invalidate(
            provider,
            repository=REPOSITORY,
            head=HEAD,
            app_id=MA0_APP,
            correlation=CORRELATION,
        )
        return record

    def test_a_standing_success_is_replaced_by_a_pending_run(self) -> None:
        provider = _Provider([_run(90)])
        record = self._invalidate(provider)
        self.assertEqual("PENDING", record["result"])
        self.assertEqual(90, record["observed"])
        self.assertEqual(1, len(provider.posts))
        _, payload = provider.posts[0]
        self.assertEqual("in_progress", payload["status"])
        self.assertEqual(PENDING_ID, payload["external_id"])
        self.assertEqual(HEAD, payload["head_sha"])
        self.assertNotIn("conclusion", payload)
        # The pending run names the run and the nonce, so a guard can find it (G1).
        self.assertEqual(
            {**CORRELATION, "unbundled_evidence_sha256": None},
            _checks().correlation_of({"output": payload["output"]}),
        )
        latest = provider.latest_view()["check_runs"][-1]
        self.assertEqual(record["pending"], latest["id"])
        self.assertEqual("in_progress", latest["status"])

    def test_nothing_is_pending_when_no_success_stands(self) -> None:
        for name, runs, observed in (
            ("a failure stands", [_run(91, conclusion="failure")], 91),
            ("no run at all", [], None),
            ("a pending run already stands", [_run(92, conclusion=None)], 92),
            ("only another App's success", [_run(93, app=OTHER_APP)], None),
        ):
            with self.subTest(name):
                provider = _Provider(runs)
                record = self._invalidate(provider)
                self.assertEqual("NOT_NEEDED", record["result"])
                self.assertIsNone(record["pending"])
                self.assertEqual(observed, record["observed"])
                self.assertEqual([], provider.posts)

    def test_an_unknown_outcome_is_found_never_reposted(self) -> None:
        provider = _Provider([_run(90)])
        provider.lose_write = True
        record = self._invalidate(provider)
        self.assertEqual("PENDING", record["result"])
        self.assertEqual(1, len(provider.posts))

    def test_a_lost_write_that_did_not_land_is_unknown(self) -> None:
        """The App's latest run after an unknown outcome is the older success, not a
        run with this external id: nothing was found, so nothing is claimed."""
        relay = _relay()
        provider = _Provider([_run(90)])
        provider.drop_write = True
        with self.assertRaises(relay.PublicationError) as raised:
            self._invalidate(provider)
        self.assertEqual("UNKNOWN", raised.exception.kind)
        self.assertEqual(1, len(provider.posts))

    def test_a_refused_or_unread_invalidation_fails(self) -> None:
        relay = _relay()
        error = relay.PublicationError
        refused = _Provider([_run(90)])
        refused.refuse_write = True
        with self.assertRaises(error) as raised:
            self._invalidate(refused)
        self.assertEqual("REFUSED", raised.exception.kind)
        doubled = _Provider()
        doubled.runs = [_run(94), {**_run(95), "app": {"id": MA0_APP}}]

        def listing(_url: str) -> tuple[Any, dict[str, str]]:
            return {"total_count": 2, "check_runs": copy.deepcopy(doubled.runs)}, {}

        with (
            mock.patch.object(doubled, "get", side_effect=listing),
            self.assertRaises(error) as raised,
        ):
            self._invalidate(doubled)
        self.assertEqual("UNKNOWN", raised.exception.kind)
        self.assertEqual([], doubled.posts)


class CompletionTests(unittest.TestCase):
    """F1 part 2: the run completes the pending run it created while that run is the
    App's latest. Without one, a success is written only when the latest is still
    the run observed at invalidation. Superseded, denied, incomplete and failed
    evaluations never end as a success, and never leave an older one standing."""

    @staticmethod
    def _pending(provider: _Provider) -> dict[str, Any]:
        record: dict[str, Any] = _relay().invalidate(
            provider,
            repository=REPOSITORY,
            head=HEAD,
            app_id=MA0_APP,
            correlation=CORRELATION,
        )
        return record

    def test_the_pending_run_is_completed_with_the_verdict(self) -> None:
        provider = _Provider([_run(90)])
        record = self._pending(provider)
        planned = _planned()
        result = _publish(provider, planned, record)
        self.assertEqual("COMPLETED", result["result"])
        self.assertEqual(record["pending"], result["check_run_id"])
        self.assertEqual(1, len(provider.posts))
        self.assertEqual(1, len(provider.patches))
        url, payload = provider.patches[0]
        self.assertEqual(f"{CHECK_RUNS}/{record['pending']}", url)
        self.assertEqual("completed", payload["status"])
        self.assertEqual("success", payload["conclusion"])
        self.assertEqual(planned["external_id"], payload["external_id"])
        checks = _checks()
        self.assertEqual(
            CORRELATION, checks.correlation_of({"output": payload["output"]})
        )

    def test_a_superseded_or_incomplete_evaluation_completes_it_as_failure(
        self,
    ) -> None:
        for action in ("SUPERSEDED", "INCOMPLETE"):
            with self.subTest(action):
                provider = _Provider([_run(90)])
                record = self._pending(provider)
                result = _publish(provider, _planned(action=action), record)
                self.assertEqual("COMPLETED", result["result"])
                self.assertEqual(1, len(provider.patches))
                _, payload = provider.patches[0]
                self.assertEqual("failure", payload["conclusion"])
                latest = provider.latest_view()["check_runs"][-1]
                self.assertEqual("failure", latest["conclusion"])

    def test_without_a_pending_run_a_superseded_success_is_invalidated(self) -> None:
        """Codex r4251432507 and cubic r4251147639 on #426: a superseded run never
        leaves the App's older success standing, even when no pending run was made."""
        provider = _Provider([_run(90)])
        record = {"result": "FAILED", "pending": None, "observed": None}
        result = _publish(provider, _planned(action="SUPERSEDED"), record)
        self.assertEqual("INVALIDATED", result["result"])
        self.assertEqual(1, len(provider.posts))
        _, payload = provider.posts[0]
        self.assertEqual("completed", payload["status"])
        self.assertEqual("failure", payload["conclusion"])
        self.assertEqual(
            "failure", provider.latest_view()["check_runs"][-1]["conclusion"]
        )

    def test_a_superseded_run_over_no_success_writes_nothing(self) -> None:
        provider = _Provider([_run(91, conclusion="failure")])
        record = {"result": "NOT_NEEDED", "pending": None, "observed": 91}
        result = _publish(provider, _planned(action="SUPERSEDED"), record)
        self.assertEqual("SUPERSEDED", result["result"])
        self.assertEqual(([], []), (provider.posts, provider.patches))

    def test_an_older_worker_never_restores_a_success(self) -> None:
        """A run whose pending run is no longer the App's latest, or whose observed
        latest has since been replaced, writes no success over the newer run."""
        provider = _Provider([_run(90)])
        record = self._pending(provider)
        provider.runs.append(_run(700, conclusion="failure"))
        result = _publish(provider, _planned(), record)
        self.assertEqual("OVERTAKEN", result["result"])
        latest = provider.latest_view()["check_runs"][-1]
        self.assertEqual((700, "failure"), (latest["id"], latest["conclusion"]))
        self.assertEqual(1, len(provider.patches))
        _, closed = provider.patches[0]
        self.assertEqual("failure", closed["conclusion"])
        observed = _Provider(
            [_run(91, conclusion="failure"), _run(701, conclusion="failure")]
        )
        record = {"result": "NOT_NEEDED", "pending": None, "observed": 91}
        result = _publish(observed, _planned(), record)
        self.assertEqual("OVERTAKEN", result["result"])
        self.assertEqual(([], []), (observed.posts, observed.patches))

    def test_a_success_without_its_record_is_never_written(self) -> None:
        provider = _Provider([_run(91, conclusion="failure")])
        result = _publish(provider, _planned(), None)
        self.assertEqual("OVERTAKEN", result["result"])
        self.assertEqual(([], []), (provider.posts, provider.patches))

    def test_with_no_success_standing_the_verdict_is_posted_once(self) -> None:
        provider = _Provider([_run(91, conclusion="failure")])
        record = {"result": "NOT_NEEDED", "pending": None, "observed": 91}
        planned = _planned()
        result = _publish(provider, planned, record)
        self.assertEqual("PUBLISHED", result["result"])
        self.assertEqual(1, len(provider.posts))
        url, payload = provider.posts[0]
        self.assertEqual(CHECK_RUNS, url)
        self.assertEqual(
            ("completed", "success", planned["external_id"]),
            (payload["status"], payload["conclusion"], payload["external_id"]),
        )
        self.assertEqual(planned["summary"], payload["output"]["summary"])
        self.assertEqual(
            CORRELATION, _checks().correlation_of({"output": payload["output"]})
        )

    def test_a_denial_already_latest_is_not_posted_again(self) -> None:
        planned = _planned("failure")
        provider = _Provider(
            [_run(92, conclusion="failure", external_id=planned["external_id"])]
        )
        record = {"result": "NOT_NEEDED", "pending": None, "observed": 92}
        result = _publish(provider, planned, record)
        self.assertEqual(("PUBLISHED", 92), (result["result"], result["check_run_id"]))
        self.assertEqual(([], []), (provider.posts, provider.patches))

    def test_an_unknown_completion_is_read_back_never_rewritten(self) -> None:
        provider = _Provider([_run(90)])
        record = self._pending(provider)
        provider.lose_write = True
        result = _publish(provider, _planned(), record)
        self.assertEqual("COMPLETED", result["result"])
        self.assertEqual(1, len(provider.patches))

    def test_a_completion_that_reads_back_otherwise_fails(self) -> None:
        relay = _relay()
        provider = _Provider([_run(90)])
        record = self._pending(provider)
        original = provider.patch

        def wrong(url: str, payload: dict[str, Any]) -> Any:
            return original(url, {**payload, "conclusion": "neutral"})

        planned = _planned()
        with (
            mock.patch.object(provider, "patch", side_effect=wrong),
            self.assertRaises(relay.PublicationError) as raised,
        ):
            _publish(provider, planned, record)
        self.assertEqual("MISMATCH", raised.exception.kind)

    def test_a_post_that_reads_back_otherwise_fails_once(self) -> None:
        """A posted run is verified as read back, by its App, head, state, conclusion
        and external id, and a mismatch is never answered with another post."""
        relay = _relay()
        for field, value in (
            ("conclusion", "neutral"),
            ("app", {"id": OTHER_APP}),
            ("external_id", "0" * 64),
            ("status", "in_progress"),
            ("head_sha", OTHER),
        ):
            with self.subTest(field):
                provider = _Provider([_run(91, conclusion="failure")])
                provider.reads_as[501] = {field: value}
                record = {"result": "NOT_NEEDED", "pending": None, "observed": 91}
                planned = _planned()
                with self.assertRaises(relay.PublicationError) as raised:
                    _publish(provider, planned, record)
                self.assertEqual("MISMATCH", raised.exception.kind)
                self.assertEqual(1, len(provider.posts))

    def test_another_app_s_runs_are_never_ours(self) -> None:
        planned = _planned("failure")
        provider = _Provider(
            [
                _run(
                    93,
                    app=OTHER_APP,
                    conclusion="failure",
                    external_id=planned["external_id"],
                )
            ]
        )
        record = {"result": "NOT_NEEDED", "pending": None, "observed": None}
        result = _publish(provider, planned, record)
        self.assertEqual("PUBLISHED", result["result"])
        self.assertEqual(1, len(provider.posts))


@functools.cache
def _checks() -> Any:
    from tools import merge_admission_checks

    return merge_admission_checks


class CorrelationTests(unittest.TestCase):
    """The check run carries what the guarded merge correlates it by, so the run the
    pinned App wrote is the record, never an artifact."""

    def test_the_record_reads_back_exactly(self) -> None:
        checks = _checks()
        text = checks.correlation_text(CORRELATION)
        self.assertEqual(CORRELATION, checks.correlation_of({"output": {"text": text}}))

    def test_a_record_without_a_nonce_or_a_digest_reads_back_exactly(self) -> None:
        """A scheduled or manual run has no nonce, and a pending or incomplete run no
        digest: both stay well-defined records (G1)."""
        checks = _checks()
        for record in (
            {**CORRELATION, "nonce": None},
            {**CORRELATION, "unbundled_evidence_sha256": None},
        ):
            with self.subTest(record=record):
                text = checks.correlation_text(record)
                self.assertEqual(
                    record, checks.correlation_of({"output": {"text": text}})
                )

    def test_a_malformed_nonce_is_no_correlation(self) -> None:
        checks = _checks()
        for nonce in ("AB" * 16, "ab" * 15, "ab" * 17, "zz" * 16, 7, True):
            with self.subTest(nonce=nonce):
                text = checks.correlation_text({**CORRELATION, "nonce": nonce})
                self.assertIsNone(checks.correlation_of({"output": {"text": text}}))

    def test_anything_else_is_no_correlation(self) -> None:
        checks = _checks()
        text = checks.correlation_text(CORRELATION)
        for name, run in (
            ("no output", {}),
            ("no text", {"output": {"text": None}}),
            ("no marker", {"output": {"text": text.split("\n", 1)[1]}}),
            ("an extra field", {"output": {"text": text.replace("{", '{"x": 1, ', 1)}}),
            ("a short digest", {"output": {"text": text.replace("c" * 64, "c" * 63)}}),
            ("a boolean run", {"output": {"text": text.replace("901", "true")}}),
            (
                "a duplicated field",
                {"output": {"text": text.replace("{", '{"run_attempt": 1, ', 1)}},
            ),
            ("no record", {"output": {"text": "no record"}}),
        ):
            with self.subTest(name):
                self.assertIsNone(checks.correlation_of(run))
        changed = checks.correlation_of(
            {"output": {"text": text.replace("901", "902")}}
        )
        self.assertEqual({**CORRELATION, "workflow_run_id": 902}, changed)

    def test_a_latest_view_short_of_its_count_is_unknown(self) -> None:
        checks = _checks()
        provider = _Provider()
        provider.runs = [_run(90)]
        with (
            mock.patch.object(
                provider,
                "get",
                return_value=({"total_count": 2, "check_runs": [_run(90)]}, {}),
            ),
            self.assertRaises(checks.PublicationError) as raised,
        ):
            checks.app_latest(provider, REPOSITORY, HEAD, MA0_APP)
        self.assertEqual("UNKNOWN", raised.exception.kind)

    def test_the_digest_drops_observation_times(self) -> None:
        checks = _checks()
        evidence, _ = _allowing()
        later = copy.deepcopy(evidence)
        for receipt in later["receipts"]:
            receipt["observed_at"] = "2026-10-12T19:00:00Z"
        self.assertEqual(checks.digest(evidence), checks.digest(later))
        later["links"] = {"work_items": [], "decisions": []}
        self.assertNotEqual(checks.digest(evidence), checks.digest(later))
        self.assertRegex(checks.digest(evidence), r"^[0-9a-f]{64}$")


def _env(directory: Path, **changes: str) -> dict[str, str]:
    """The runner's environment: its temporary directory, and the run's identity."""
    environment = {
        "RUNNER_TEMP": str(directory),
        "GITHUB_RUN_ID": str(RUN_ID),
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": MAIN,
        MA0_ENV: "",
    }
    environment.update(changes)
    return environment


def _work(directory: Path) -> Path:
    work = directory / "gnostoa-merge-admission"
    work.mkdir(exist_ok=True)
    return work


class CommandTests(unittest.TestCase):
    """The commands read and write fixed names under the runner's temporary directory
    alone: no path reaches a file operation from the command line (SonarCloud S8707
    on #426, and the precedent of `admit_mention.py`)."""

    @staticmethod
    def _files(directory: Path, *, code: int = 0) -> list[str]:
        evidence, verdict = _allowing()
        work = _work(directory)
        (work / "evaluated-evidence.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        (work / "current-evidence.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        (work / "current-unbundled-evidence.json").write_text(
            json.dumps(evidence), encoding="utf-8"
        )
        (work / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
        for label in ("evaluated", "current"):
            (work / f"{label}-population.json").write_text(
                json.dumps(POPULATION), encoding="utf-8"
            )
        (work / "pending.json").write_text(
            json.dumps({"result": "SHADOW", "pending": None, "observed": None}),
            encoding="utf-8",
        )
        return [
            "publish",
            "--repository",
            REPOSITORY,
            "--expected-head",
            HEAD,
            "--verdict-exit",
            str(code),
        ]

    @staticmethod
    def _main(
        relay: Any, argv: list[str], environment: dict[str, str], **patches: Any
    ) -> int:
        with (
            mock.patch.dict(os.environ, environment),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            if not patches:
                return int(relay.main(argv))
            with mock.patch.multiple(relay, **patches):
                return int(relay.main(argv))

    @staticmethod
    def _result(directory: Path) -> dict[str, Any]:
        path = directory / "gnostoa-merge-admission" / "result.json"
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return document

    def test_without_the_app_s_credential_it_publishes_nothing(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            with mock.patch.object(
                relay.github_rest,
                "GitHubRestClient",
                side_effect=AssertionError("no client"),
            ):
                code = self._main(relay, argv, _env(directory))
            self.assertEqual(0, code)
            result = self._result(directory)
            self.assertEqual("SHADOW", result["result"])
            self.assertEqual("success", result["planned"]["conclusion"])

    def test_no_option_takes_a_path(self) -> None:
        """The shape, not the instance: no command accepts a path at all."""
        relay = _relay()
        for argv in (
            ["publish", "--work-dir", "/x"],
            ["publish", "--evaluated", "/x"],
            ["publish", "--output", "/x"],
        ):
            parsing = relay.parser()
            with (
                self.subTest(argv=argv),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as raised,
            ):
                parsing.parse_args(argv)
            self.assertEqual(2, raised.exception.code)
        # Every command, given every option it takes, holds no path in what it parsed.
        for argv in (
            ["hint"],
            [
                "invalidate",
                "--repository",
                REPOSITORY,
                "--expected-head",
                HEAD,
                "--app-id",
                "1",
            ],
            [
                "publish",
                "--repository",
                REPOSITORY,
                "--expected-head",
                HEAD,
                "--app-id",
                "1",
                "--verdict-exit",
                "0",
            ],
        ):
            with self.subTest(argv=argv):
                parsed = vars(relay.parser().parse_args(argv))
                self.assertFalse([v for v in parsed.values() if isinstance(v, Path)])

    def test_the_runner_s_directory_and_identity_are_required(self) -> None:
        """Without them the command stops before it writes anything anywhere, the
        working directory included."""
        relay = _relay()
        for missing in (
            "RUNNER_TEMP",
            "GITHUB_RUN_ID",
            "GITHUB_RUN_ATTEMPT",
            "GITHUB_SHA",
        ):
            with (
                self.subTest(missing),
                tempfile.TemporaryDirectory() as raw,
                tempfile.TemporaryDirectory() as elsewhere,
                contextlib.chdir(elsewhere),
            ):
                directory = Path(raw)
                argv = self._files(directory)
                environment = _env(directory)
                del environment[missing]
                with mock.patch.dict(os.environ, {}, clear=False):
                    os.environ.pop(missing, None)
                    code = self._main(relay, argv, environment)
                self.assertEqual(2, code)
                self.assertEqual([], sorted(Path(elsewhere).iterdir()))
                self.assertFalse((_work(directory) / "result.json").exists())

    def test_publishing_needs_the_app_s_id(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            code = self._main(
                relay, self._files(directory), _env(directory, **{MA0_ENV: "x" * 40})
            )
            self.assertEqual(2, code)

    def test_a_publication_failure_fails_the_run(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [*self._files(directory), "--app-id", str(MA0_APP)]
            (_work(directory) / "pending.json").write_text(
                json.dumps({"result": "NOT_NEEDED", "pending": None, "observed": None}),
                encoding="utf-8",
            )
            refusing = _Provider()
            refusing.refuse_write = True
            code = self._main(
                relay,
                argv,
                _env(directory, **{MA0_ENV: "x" * 40}),
                _client=mock.Mock(return_value=refusing),
            )
            self.assertEqual(1, code)

    def test_an_unreadable_evidence_file_still_completes_as_incomplete(self) -> None:
        """A failed evaluation (cubic r4251147766 on #426) stops before any verdict is
        planned on it, and the run's record says INCOMPLETE: a pending run is
        completed as a failure, never left to look like an evaluation."""
        relay = _relay()
        corruptions: dict[str, bytes | None] = {
            "missing": None,
            "not json": b"{",
            "not an object": b"[]",
            "over its bound": b" " * (MAX_INPUT_BYTES + 1),
        }
        corruptions["a repeated number"] = json.dumps(
            _with((300, HEAD), (300, OTHER))
        ).encode()
        corruptions["not complete"] = json.dumps(
            {**POPULATION, "coverage": "PARTIAL"}
        ).encode()
        names = [
            *(
                f"{label}-evidence.json"
                for label in ("evaluated", "current", "current-unbundled")
            ),
            "evaluated-population.json",
            "current-population.json",
        ]
        for file_name in names:
            for name, content in corruptions.items():
                if (
                    name in ("a repeated number", "not complete")
                    and "population" not in file_name
                ):
                    continue
                with (
                    self.subTest(file=file_name, corruption=name),
                    tempfile.TemporaryDirectory() as raw,
                ):
                    directory = Path(raw)
                    argv = self._files(directory)
                    path = _work(directory) / file_name
                    if content is None:
                        path.unlink()
                    else:
                        path.write_bytes(content)
                    self.assertEqual(2, self._main(relay, argv, _env(directory)))
                    result = self._result(directory)
                    self.assertEqual("INCOMPLETE", result["planned"]["action"])
                    self.assertEqual("failure", result["planned"]["conclusion"])

    def test_evidence_is_read_under_the_owned_input_rules(self) -> None:
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
                with (
                    self.subTest(file=label, document=name),
                    tempfile.TemporaryDirectory() as raw,
                ):
                    directory = Path(raw)
                    argv = self._files(directory)
                    (_work(directory) / f"{label}-evidence.json").write_text(
                        content, encoding="utf-8"
                    )
                    self.assertEqual(2, self._main(relay, argv, _env(directory)))
                    self.assertEqual(
                        "INCOMPLETE", self._result(directory)["planned"]["action"]
                    )

    def test_a_verdict_with_a_duplicated_field_is_no_verdict(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            path = _work(directory) / "verdict.json"
            text = path.read_text(encoding="utf-8")
            path.write_text(text[:-1] + ', "status": "ALLOW"}', encoding="utf-8")
            self.assertEqual(0, self._main(relay, argv, _env(directory)))
            self.assertEqual(
                "failure", self._result(directory)["planned"]["conclusion"]
            )

    def test_a_moved_current_head_supersedes_through_the_command(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            path = _work(directory) / "current-evidence.json"
            evidence = json.loads(path.read_text(encoding="utf-8"))
            evidence["subject"]["head_commit"] = OTHER
            path.write_text(json.dumps(evidence), encoding="utf-8")
            self.assertEqual(0, self._main(relay, argv, _env(directory)))
            self.assertEqual("SUPERSEDED", self._result(directory)["planned"]["action"])

    def test_the_published_digest_is_the_unbundled_evidence_s(self) -> None:
        """The guarded merge rebuilds the evidence without the analyzer bundle it
        cannot re-read, so the run records that document's digest."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [*self._files(directory), "--app-id", str(MA0_APP)]
            (_work(directory) / "pending.json").write_text(
                json.dumps({"result": "NOT_NEEDED", "pending": None, "observed": None}),
                encoding="utf-8",
            )
            unbundled, _ = _allowing()
            unbundled["receipts"] = []
            (_work(directory) / "current-unbundled-evidence.json").write_text(
                json.dumps(unbundled), encoding="utf-8"
            )
            provider = _Provider()
            code = self._main(
                relay,
                argv,
                _env(directory, **{MA0_ENV: "x" * 40}),
                _client=mock.Mock(return_value=provider),
            )
            self.assertEqual(0, code)
            self.assertEqual(1, len(provider.posts))
            _, payload = provider.posts[0]
            found = _checks().correlation_of({"output": payload["output"]})
            self.assertEqual(
                {
                    "workflow_run_id": RUN_ID,
                    "run_attempt": 1,
                    "protected_revision": MAIN,
                    "nonce": None,
                    "unbundled_evidence_sha256": _checks().digest(unbundled),
                },
                found,
            )

    def test_the_dispatch_nonce_is_recorded_once_validated(self) -> None:
        """The nonce reaches the publishing job as data from its own protected
        `subjects` job, and is recorded only when it is exactly 128 bits of hex."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [*self._files(directory), "--app-id", str(MA0_APP)]
            (_work(directory) / "pending.json").write_text(
                json.dumps({"result": "NOT_NEEDED", "pending": None, "observed": None}),
                encoding="utf-8",
            )
            provider = _Provider()
            code = self._main(
                relay,
                argv,
                _env(directory, **{MA0_ENV: "x" * 40, "DISPATCH_NONCE": NONCE}),
                _client=mock.Mock(return_value=provider),
            )
            self.assertEqual(0, code)
            _, payload = provider.posts[0]
            found = _checks().correlation_of({"output": payload["output"]})
            self.assertEqual(NONCE, (found or {}).get("nonce"))
        for bad in ("AB" * 16, "ab" * 15, "not hex at all, 32 characters!!"):
            with self.subTest(nonce=bad), tempfile.TemporaryDirectory() as raw:
                directory = Path(raw)
                code = self._main(
                    relay, self._files(directory), _env(directory, DISPATCH_NONCE=bad)
                )
                self.assertEqual(2, code)

    def test_an_expected_head_that_is_no_exact_sha_is_refused(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            argv[argv.index("--expected-head") + 1] = "abc"
            self.assertEqual(2, self._main(relay, argv, _env(directory)))

    def test_an_evidence_head_that_is_no_exact_sha_is_incomplete(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = self._files(directory)
            path = _work(directory) / "evaluated-evidence.json"
            evidence = json.loads(path.read_text(encoding="utf-8"))
            evidence["subject"]["head_commit"] = "abc"
            path.write_text(json.dumps(evidence), encoding="utf-8")
            self.assertEqual(2, self._main(relay, argv, _env(directory)))
            self.assertEqual("INCOMPLETE", self._result(directory)["planned"]["action"])

    def test_invalidate_writes_its_record_for_the_completing_job(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [
                "invalidate",
                "--repository",
                REPOSITORY,
                "--expected-head",
                HEAD,
                "--app-id",
                str(MA0_APP),
            ]
            provider = _Provider([_run(90)])
            code = self._main(
                relay,
                argv,
                _env(directory, **{MA0_ENV: "x" * 40}),
                _client=mock.Mock(return_value=provider),
            )
            self.assertEqual(0, code)
            record = json.loads(
                (directory / "gnostoa-merge-admission" / "pending.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("PENDING", record["result"])
            self.assertEqual(90, record["observed"])
            self.assertEqual(provider.runs[-1]["id"], record["pending"])

    def test_a_failed_invalidation_fails_its_job_and_records_it(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [
                "invalidate",
                "--repository",
                REPOSITORY,
                "--expected-head",
                HEAD,
                "--app-id",
                str(MA0_APP),
            ]
            provider = _Provider([_run(90)])
            provider.refuse_write = True
            code = self._main(
                relay,
                argv,
                _env(directory, **{MA0_ENV: "x" * 40}),
                _client=mock.Mock(return_value=provider),
            )
            self.assertEqual(1, code)
            record = json.loads(
                (_work(directory) / "pending.json").read_text(encoding="utf-8")
            )
            self.assertEqual(("FAILED", None), (record["result"], record["pending"]))

    def test_a_failed_or_shadow_invalidation_is_no_observation(self) -> None:
        """Octopus on #426: a record that observed nothing, because the invalidation
        failed or ran without the App, is no observation. With the App's latest view
        empty, its `observed: null` must not read as "the latest is unchanged"."""
        relay = _relay()
        for result in ("FAILED", "SHADOW"):
            with self.subTest(result), tempfile.TemporaryDirectory() as raw:
                directory = Path(raw)
                argv = [*self._files(directory), "--app-id", str(MA0_APP)]
                (_work(directory) / "pending.json").write_text(
                    json.dumps(
                        {
                            "result": result,
                            "pending": None,
                            "observed": None,
                            "head": HEAD,
                        }
                    ),
                    encoding="utf-8",
                )
                provider = _Provider()
                code = self._main(
                    relay,
                    argv,
                    _env(directory, **{MA0_ENV: "x" * 40}),
                    _client=mock.Mock(return_value=provider),
                )
                self.assertEqual(0, code)
                self.assertEqual("OVERTAKEN", self._result(directory)["result"])
                self.assertEqual([], provider.posts)

    def test_another_head_s_record_is_no_record(self) -> None:
        """A record the invalidation wrote for another head says nothing about what
        this run observed, so no success is written on it."""
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = [*self._files(directory), "--app-id", str(MA0_APP)]
            (_work(directory) / "pending.json").write_text(
                json.dumps(
                    {
                        "result": "NOT_NEEDED",
                        "pending": None,
                        "observed": None,
                        "head": OTHER,
                    }
                ),
                encoding="utf-8",
            )
            provider = _Provider()
            code = self._main(
                relay,
                argv,
                _env(directory, **{MA0_ENV: "x" * 40}),
                _client=mock.Mock(return_value=provider),
            )
            self.assertEqual(0, code)
            self.assertEqual("OVERTAKEN", self._result(directory)["result"])
            self.assertEqual([], provider.posts)

    def test_invalidate_in_shadow_writes_nothing_to_the_provider(self) -> None:
        relay = _relay()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            argv = ["invalidate", "--repository", REPOSITORY, "--expected-head", HEAD]
            with mock.patch.object(
                relay.github_rest,
                "GitHubRestClient",
                side_effect=AssertionError("no client"),
            ):
                self.assertEqual(0, self._main(relay, argv, _env(directory)))
            record = json.loads(
                (directory / "gnostoa-merge-admission" / "pending.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("SHADOW", record["result"])


class DispatchHintTests(unittest.TestCase):
    """G1: a guarded merge's `repository_dispatch` names its pull request and its
    nonce, as data. The event is the runner's own file; its payload must be exactly
    those two, well-typed, or the selection refuses, never falling back to the
    sweep."""

    @staticmethod
    def _hint(directory: Path, event: object) -> tuple[int, str]:
        relay = _relay()
        path = directory / "event.json"
        if event is not None:
            path.write_text(json.dumps(event), encoding="utf-8")
        out = io.StringIO()
        with (
            mock.patch.dict(
                os.environ, {**_env(directory), "GITHUB_EVENT_PATH": str(path)}
            ),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
        ):
            code = int(relay.main(["dispatch-hint"]))
        return code, out.getvalue().strip()

    @staticmethod
    def _event(**payload: object) -> dict[str, object]:
        return {"action": "gnostoa-merge-admission", "client_payload": payload}

    def test_a_well_formed_dispatch_names_its_pull_request_and_nonce(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(
                (0, f"426 {NONCE}"),
                self._hint(Path(raw), self._event(pull_number=426, nonce=NONCE)),
            )

    def test_anything_else_refuses(self) -> None:
        for name, event in (
            ("no event file", None),
            (
                "another type",
                {
                    "action": "other",
                    "client_payload": {"pull_number": 426, "nonce": NONCE},
                },
            ),
            ("no payload", {"action": "gnostoa-merge-admission"}),
            ("no nonce", self._event(pull_number=426)),
            ("no pull request", self._event(nonce=NONCE)),
            ("an extra field", self._event(pull_number=426, nonce=NONCE, head=HEAD)),
            ("a string number", self._event(pull_number="426", nonce=NONCE)),
            ("a boolean number", self._event(pull_number=True, nonce=NONCE)),
            ("zero", self._event(pull_number=0, nonce=NONCE)),
            ("an upper-case nonce", self._event(pull_number=426, nonce="AB" * 16)),
            ("a short nonce", self._event(pull_number=426, nonce="ab" * 15)),
            ("a list nonce", self._event(pull_number=426, nonce=[NONCE])),
        ):
            with self.subTest(name), tempfile.TemporaryDirectory() as raw:
                self.assertEqual((2, ""), self._hint(Path(raw), event))


class HintTests(unittest.TestCase):
    """F1 part 1: a relayed PR conversation comment names its pull request only as a
    hint, derived in protected code from the event GitHub delivered."""

    @staticmethod
    def _hint(directory: Path, content: bytes | None) -> tuple[int, str]:
        relay = _relay()
        relayed = directory / "gnostoa-merge-admission-relay"
        relayed.mkdir()
        if content is not None:
            (relayed / "event.json").write_bytes(content)
        out = io.StringIO()
        with (
            mock.patch.dict(os.environ, _env(directory)),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
        ):
            code = int(relay.main(["hint"]))
        return code, out.getvalue().strip()

    def test_a_pull_request_comment_names_its_pull_request(self) -> None:
        event = {"action": "deleted", "issue": {"number": 426, "pull_request": {}}}
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(
                (0, "426"), self._hint(Path(raw), json.dumps(event).encode())
            )

    def test_an_issue_comment_names_nothing(self) -> None:
        event = {"action": "created", "issue": {"number": 407}}
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual((0, ""), self._hint(Path(raw), json.dumps(event).encode()))

    def test_a_missing_malformed_or_unbounded_event_fails(self) -> None:
        from tools.agent_review_github import DELIVERED_EVENT_BYTES

        for name, content in (
            ("missing", None),
            ("not json", b"{"),
            ("no issue", b"{}"),
            ("a boolean number", b'{"issue": {"number": true, "pull_request": {}}}'),
            # Valid JSON past the delivered-event bound, so only the bound refuses it.
            (
                "over its bound",
                b'{"issue": {"number": 426, "pull_request": {}}}'
                + b" " * DELIVERED_EVENT_BYTES,
            ),
        ):
            with self.subTest(name), tempfile.TemporaryDirectory() as raw:
                code, out = self._hint(Path(raw), content)
                self.assertEqual((2, ""), (code, out))


if __name__ == "__main__":
    unittest.main()
