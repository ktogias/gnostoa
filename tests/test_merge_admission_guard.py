"""The guarded merge's own admission (#407, MA0 slice 1b.4; F1 part 3, the Decisions
Router on #426, 6130207025).

After the owner's exact-head approval and step 8's other reads, the guard dispatches
the protected admission for the approved head and correlates the result through the
workflow run the dispatch returns, never through time. It checks that run's identity,
reads the pinned App's check natively and re-reads the subject, comparing it with
what was evaluated. It never merges: step 8's `--match-head-commit` merge follows it.
"""

from __future__ import annotations

import copy
import functools
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess  # nosec B404 -- the test's own git repository
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

from tools import github_rest, merge_admission_checks

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "ci" / "merge_admission_guard.py"
REPOSITORY = "ktogias/gnostoa"
# The guard's credential variable, by name only.
GUARD_CREDENTIAL = "GH_TOKEN"
API = f"https://api.github.com/repos/{REPOSITORY}"
HEAD = "a" * 40
MAIN = "b" * 40
OTHER = "f" * 40
PULL = 426
RUN = 9001
CHECK = 77
MA0_APP = 4242
OTHER_APP = 15368
EVIDENCE = {
    "subject": {
        "repository": f"https://github.com/{REPOSITORY}",
        "change_request": {"kind": "github-pull-request", "id": str(PULL)},
        "head_commit": HEAD,
    },
    "links": {"work_items": ["#407"], "decisions": ["0112"]},
    "receipts": [{"requirement": "x", "observed_at": "2026-10-12T19:00:00Z"}],
}
# The open population at the last read: this pull request alone at its head (H1).
POPULATION = {
    "coverage": "COMPLETE",
    "pulls": [{"pull_number": 1, "head": OTHER}, {"pull_number": PULL, "head": HEAD}],
}


@functools.cache
def _guard() -> Any:
    spec = importlib.util.spec_from_file_location(
        "gnostoa_merge_admission_guard", GUARD_PATH
    )
    if spec is None or spec.loader is None:
        raise AssertionError("merge-admission guard is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The guard's nonce in these tests, and another dispatch's.
NONCE = "ab" * 16
FOREIGN = "cd" * 16
DISPATCHES = f"{API}/dispatches"
LATEST = f"{API}/commits/{HEAD}/check-runs?check_name=merge-admission&filter=latest&per_page=100"


def _check(
    identifier: int,
    *,
    nonce: str | None = NONCE,
    status: str = "completed",
    conclusion: str | None = "success",
    run: int = RUN,
    attempt: int = 1,
    revision: str = MAIN,
    digest: str | None = None,
    app: int = MA0_APP,
    head: str = HEAD,
) -> dict[str, Any]:
    """A run of the check as the pinned App writes it, with its correlation block."""
    recorded = (
        merge_admission_checks.digest(EVIDENCE)
        if digest is None and status == "completed"
        else digest
    )
    correlation = {
        "workflow_run_id": run,
        "run_attempt": attempt,
        "protected_revision": revision,
        "nonce": nonce,
        "unbundled_evidence_sha256": recorded,
    }
    return {
        "id": identifier,
        "name": "merge-admission",
        "head_sha": head,
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "external_id": "e" * 64,
        "app": {"id": app, "slug": "gnostoa-ma0"},
        "output": {
            "title": "merge-admission",
            "summary": "s",
            "text": merge_admission_checks.correlation_text(correlation),
        },
    }


class _GitHub:
    """The provider as the guard reads it. A repository dispatch answers with no body,
    as GitHub's `204` does, so no run id is ever handed back. The pinned App's latest
    run on the head moves along `timeline`, one state per read, the last one kept. It
    has no merge, so a guard that tried to merge would fail."""

    def __init__(self) -> None:
        self.pull = {
            "number": PULL,
            "state": "open",
            "head": {"sha": HEAD},
            "base": {"ref": "main"},
        }
        self.main = MAIN
        # An older success with no nonce, then this dispatch's pending run, then its
        # completed success.
        self.timeline: list[dict[str, Any] | None] = [
            _check(CHECK - 7, nonce=None),
            _check(CHECK, status="in_progress", conclusion=None),
            _check(CHECK),
        ]
        self.position = -1
        self.run = {
            "id": RUN,
            "path": ".github/workflows/merge-admission.yml",
            "event": "repository_dispatch",
            "head_branch": "main",
            "head_sha": MAIN,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
            "repository": {"full_name": REPOSITORY},
        }
        self.running_reads = 0
        self.dispatch_error: BaseException | None = None
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.reads: list[str] = []
        self.after_dispatch: list[Any] = []
        self.read_as: dict[str, Any] = {}

    @staticmethod
    def url(path: str) -> str:
        return f"https://api.github.com/{path.lstrip('/')}"

    def _current(self) -> dict[str, Any] | None:
        return self.timeline[max(0, min(self.position, len(self.timeline) - 1))]

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.reads.append(url)
        if url == f"{API}/pulls/{PULL}":
            return copy.deepcopy(self.pull), {}
        if url == f"{API}/branches/main":
            return {"name": "main", "commit": {"sha": self.main}}, {}
        if url == f"{API}/actions/runs/{self.run['id']}":
            if self.running_reads:
                self.running_reads -= 1
                return {**self.run, "status": "in_progress", "conclusion": None}, {}
            return copy.deepcopy(self.run), {}
        if url == LATEST:
            self.position += 1
            current = self._current()
            runs = [] if current is None else [copy.deepcopy(current)]
            return {"total_count": len(runs), "check_runs": runs}, {}
        current = self._current()
        if current is not None and url == f"{API}/check-runs/{current['id']}":
            return {**copy.deepcopy(current), **self.read_as}, {}
        raise AssertionError(f"unexpected read {url}")

    def post_accepted(self, url: str, payload: dict[str, Any]) -> None:
        self.posts.append((url, copy.deepcopy(payload)))
        if url != DISPATCHES:
            raise AssertionError(f"unexpected write {url}")
        for change in self.after_dispatch:
            change(self)
        if self.dispatch_error is not None:
            raise self.dispatch_error


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _run_guard(
    github: _GitHub,
    *,
    rebuilt: Any = None,
    revision: str = MAIN,
    population: Any = None,
) -> Any:
    clock = _Clock()
    return _guard().guard(
        github,
        repository=REPOSITORY,
        pull_number=PULL,
        approved=HEAD,
        app_id=MA0_APP,
        checkout_revision=revision,
        rebuild=lambda: copy.deepcopy(EVIDENCE if rebuilt is None else rebuilt),
        population=lambda: copy.deepcopy(
            POPULATION if population is None else population
        ),
        nonce=NONCE,
        sleep=clock.sleep,
        clock=clock,
        poll_seconds=15.0,
        deadline_seconds=600.0,
    )


class GuardTests(unittest.TestCase):
    def assertRefused(self, github: _GitHub, needle: str, **options: Any) -> None:
        with self.assertRaises(_guard().Refused) as raised:
            _run_guard(github, **options)
        self.assertIn(needle, str(raised.exception))

    def test_a_correlated_current_success_proceeds(self) -> None:
        github = _GitHub()
        github.running_reads = 2
        result = _run_guard(github)
        self.assertEqual(
            {
                "result": "PROCEED",
                "workflow_run_id": RUN,
                "check_run_id": CHECK,
                "protected_revision": MAIN,
            },
            result,
        )
        self.assertEqual(1, len(github.posts))
        url, payload = github.posts[0]
        self.assertEqual(DISPATCHES, url)
        self.assertEqual(
            {
                "event_type": "gnostoa-merge-admission",
                "client_payload": {"pull_number": PULL, "nonce": NONCE},
            },
            payload,
        )
        # The last reads are the subject and protected main, after the comparison.
        self.assertEqual(
            [f"{API}/pulls/{PULL}", f"{API}/branches/main"], github.reads[-2:]
        )

    def test_each_guard_dispatches_its_own_fresh_nonce(self) -> None:
        guard = _guard()
        nonces = {guard.fresh_nonce() for _ in range(8)}
        self.assertEqual(8, len(nonces))
        for nonce in nonces:
            self.assertRegex(nonce, r"^[0-9a-f]{32}$")

    def test_it_runs_only_from_protected_main_s_checkout(self) -> None:
        github = _GitHub()
        self.assertRefused(github, "checkout", revision=OTHER)
        self.assertEqual([], github.posts)

    def test_only_the_approved_open_head_is_guarded(self) -> None:
        for name, change in (
            ("another head", {"head": {"sha": OTHER}}),
            ("closed", {"state": "closed"}),
            ("another base", {"base": {"ref": "release"}}),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.pull.update(change)
                self.assertRefused(github, "pull request")
                self.assertEqual([], github.posts)

    def test_a_refused_dispatch_is_refused(self) -> None:
        github = _GitHub()
        github.dispatch_error = github_rest.GitHubWriteError(
            "GitHub API HTTP 403", status=403
        )
        self.assertRefused(github, "dispatch")
        self.assertEqual([], [url for url in github.reads if url == LATEST])

    def test_a_lost_dispatch_answer_is_reconciled_by_its_nonce_never_resent(
        self,
    ) -> None:
        github = _GitHub()
        github.dispatch_error = github_rest.GitHubWriteError(
            "GitHub API HTTP 502", status=502, outcome_unknown=True
        )
        self.assertEqual("PROCEED", _run_guard(github)["result"])
        self.assertEqual(1, len(github.posts))

    def test_a_record_with_another_or_no_nonce_never_substitutes(self) -> None:
        """An older success, another dispatch's run or a scheduled run carries no
        record of this nonce, and is never accepted, even while it is the latest."""
        cases: tuple[tuple[str, list[dict[str, Any] | None]], ...] = (
            ("an older success", [_check(CHECK - 7, nonce=None)]),
            ("another dispatch's success", [_check(CHECK + 1, nonce=FOREIGN)]),
            ("no run at all", [None]),
        )
        for name, timeline in cases:
            with self.subTest(name):
                github = _GitHub()
                github.timeline = timeline
                self.assertRefused(github, "no record of this dispatch")

    def test_a_newer_record_overtaking_this_dispatch_s_refuses(self) -> None:
        """Concurrent dispatches: once this nonce's run has been seen, a newer run
        without it means this one no longer stands. Nothing falls back to it."""
        github = _GitHub()
        github.timeline = [
            _check(CHECK, status="in_progress", conclusion=None),
            _check(CHECK + 1, nonce=FOREIGN),
            _check(CHECK),
        ]
        self.assertRefused(github, "overtaken")

    def test_a_duplicate_delivery_counts_only_by_its_latest_complete_record(
        self,
    ) -> None:
        """Two runs for one nonce (a duplicate delivery or a re-run): only the latest
        record counts, and its own run and attempt must match it."""
        github = _GitHub()
        github.timeline = [
            _check(CHECK - 1, run=RUN - 1, status="in_progress", conclusion=None),
            _check(CHECK, attempt=2),
        ]
        github.run = {**github.run, "run_attempt": 2}
        self.assertEqual("PROCEED", _run_guard(github)["result"])
        stale = _GitHub()
        stale.timeline = [_check(CHECK, attempt=2)]
        self.assertRefused(stale, "run")

    def test_a_record_that_changed_after_the_run_was_read_refuses(self) -> None:
        """The record is re-read after its run: a newer attempt for this nonce, or
        another dispatch's record, is not the run that was checked."""
        for name, later in (
            ("a newer attempt", _check(CHECK + 1, attempt=2)),
            ("another dispatch's record", _check(CHECK + 1, nonce=FOREIGN)),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.timeline = [_check(CHECK), later]
                self.assertRefused(github, "does not correlate")

    def test_only_the_protected_admission_run_counts(self) -> None:
        for name, change in (
            ("another workflow", {"path": ".github/workflows/verification.yml"}),
            ("another event", {"event": "workflow_dispatch"}),
            ("another branch", {"head_branch": "feature"}),
            ("another revision", {"head_sha": OTHER}),
            ("another repository", {"repository": {"full_name": "someone/else"}}),
            ("another attempt", {"run_attempt": 3}),
            ("a failed run", {"conclusion": "failure"}),
            ("a cancelled run", {"conclusion": "cancelled"}),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.run.update(change)
                self.assertRefused(github, "run")

    def test_a_run_or_record_that_does_not_finish_in_time_is_refused(self) -> None:
        running = _GitHub()
        running.running_reads = 10_000
        self.assertRefused(running, "did not complete")
        pending = _GitHub()
        pending.timeline = [_check(CHECK, status="in_progress", conclusion=None)]
        self.assertRefused(pending, "did not complete")

    def test_only_the_pinned_app_s_complete_success_counts(self) -> None:
        for name, change in (
            ("a failure", {"conclusion": "failure"}),
            ("a neutral", {"conclusion": "neutral"}),
            ("another head", {"head_sha": OTHER}),
            ("another check", {"name": "merge-admission-x"}),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.timeline = [{**_check(CHECK), **change}]
                self.assertRefused(github, "check")
        foreign = _GitHub()
        foreign.timeline = [_check(CHECK, app=OTHER_APP)]
        self.assertRefused(foreign, "no record of this dispatch")
        undigested = _GitHub()
        undigested.timeline = [
            {**_check(CHECK), "output": _check(CHECK, status="in_progress")["output"]}
        ]
        self.assertRefused(undigested, "check")

    def test_the_check_read_by_its_id_is_checked_again(self) -> None:
        """The run the latest view names is read natively by its id, and that read is
        what is checked: an App other than the pinned one refuses there too."""
        for name, change in (
            ("another App", {"app": {"id": OTHER_APP}}),
            ("a failure", {"conclusion": "failure"}),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.read_as = change
                self.assertRefused(github, "check")

    def test_a_subject_changed_since_the_evaluation_is_refused(self) -> None:
        """The untriggered change the Router names: a required-evidence change no
        event reported, between the evaluation and the merge."""
        changed = copy.deepcopy(EVIDENCE)
        changed["links"] = {"work_items": [], "decisions": []}
        self.assertRefused(_GitHub(), "changed", rebuilt=changed)
        observed_later = copy.deepcopy(EVIDENCE)
        observed_later["receipts"][0]["observed_at"] = "2026-10-12T19:30:00Z"
        self.assertEqual(
            "PROCEED", _run_guard(_GitHub(), rebuilt=observed_later)["result"]
        )

    def test_a_rebuilt_evidence_for_another_subject_is_refused(self) -> None:
        other = copy.deepcopy(EVIDENCE)
        other["subject"]["head_commit"] = OTHER
        self.assertRefused(_GitHub(), "subject", rebuilt=other)

    def test_a_shared_or_contradicted_head_is_refused_at_the_last_read(self) -> None:
        """H1 (#426 6131149850): a peer at the approved head, found at the guard's own
        last read, refuses, as does a population that does not show this pull
        request at that head, or one not completely read."""
        for name, population, needle in (
            (
                "a peer at the head",
                {
                    **POPULATION,
                    "pulls": [*POPULATION["pulls"], {"pull_number": 2, "head": HEAD}],
                },
                "shared",
            ),
            (
                "this pull request missing",
                {**POPULATION, "pulls": POPULATION["pulls"][:1]},
                "population",
            ),
            (
                "this pull request elsewhere",
                {
                    "coverage": "COMPLETE",
                    "pulls": [{"pull_number": PULL, "head": OTHER}],
                },
                "population",
            ),
            ("not complete", {**POPULATION, "coverage": "PARTIAL"}, "population"),
        ):
            with self.subTest(name):
                self.assertRefused(_GitHub(), needle, population=population)

    def test_a_re_read_that_fails_refuses_with_its_reason(self) -> None:
        """Kilo on #426: a provider or evidence error while re-reading the subject or
        the population refuses, with its reason, never escapes as a traceback."""
        guard = _guard()

        def unreadable() -> Any:
            raise github_rest.GitHubReadError("GitHub API HTTP 502")

        def invalid() -> Any:
            raise ValueError("the snapshot is invalid")

        def unopenable() -> Any:
            raise OSError("policy/merge-authorities.yaml is unreadable")

        for name, options in (
            ("the subject unreadable", {"rebuild": unreadable}),
            ("the subject invalid", {"rebuild": invalid}),
            ("the population unreadable", {"population": unreadable}),
            ("a policy file unreadable", {"rebuild": unopenable}),
        ):
            with self.subTest(name):
                clock = _Clock()
                arguments: dict[str, Any] = {
                    "repository": REPOSITORY,
                    "pull_number": PULL,
                    "approved": HEAD,
                    "app_id": MA0_APP,
                    "checkout_revision": MAIN,
                    "rebuild": lambda: copy.deepcopy(EVIDENCE),
                    "population": lambda: copy.deepcopy(POPULATION),
                    "nonce": NONCE,
                    "sleep": clock.sleep,
                    "clock": clock,
                }
                arguments.update(options)
                github = _GitHub()
                with self.assertRaises(guard.Refused) as raised:
                    guard.guard(github, **arguments)
                self.assertIn("could not be re-read", str(raised.exception))

    def test_a_move_after_the_dispatch_is_refused(self) -> None:
        for name, change in (
            ("main moved", lambda g: setattr(g, "main", OTHER)),
            ("the head moved", lambda g: g.pull.update({"head": {"sha": OTHER}})),
            ("the pull request closed", lambda g: g.pull.update({"state": "closed"})),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.after_dispatch.append(change)
                with self.assertRaises(_guard().Refused):
                    _run_guard(github)

    def test_it_never_merges(self) -> None:
        github = _GitHub()
        _run_guard(github)
        self.assertEqual([DISPATCHES], [url for url, _ in github.posts])
        self.assertFalse(hasattr(github, "put"))
        self.assertFalse(hasattr(github, "post"))


class RebuilderTests(unittest.TestCase):
    """CodeAnt and Kilo on #426: the re-reads are built as L1's own command builds its
    client, from the token alone, and call L1's snapshot, the shared evidence
    function and L1's one population enumeration."""

    def test_the_re_readers_are_l1_s_own(self) -> None:
        guard = _guard()
        rebuild, population = guard.rebuilders("x" * 40, REPOSITORY, PULL, ROOT)
        l1 = sys.modules["review_github_current_state"]
        listed = [{"number": PULL, "head_sha": HEAD}, {"number": 1, "head_sha": OTHER}]
        with mock.patch.object(l1, "_open_pulls", return_value=listed) as pulls:
            self.assertEqual(
                {
                    "coverage": "COMPLETE",
                    "pulls": [
                        {"pull_number": PULL, "head": HEAD},
                        {"pull_number": 1, "head": OTHER},
                    ],
                },
                population(),
            )
        reader = pulls.call_args.args[0]
        self.assertIsInstance(reader, l1.GitHubRestClient)
        self.assertEqual(REPOSITORY, pulls.call_args.args[1])
        from tools import merge_evidence_github

        with (
            mock.patch.object(
                l1, "collect_snapshot", return_value={"s": 1}
            ) as snapshot,
            mock.patch.object(
                merge_evidence_github, "evidence_for", return_value=EVIDENCE
            ) as evidence,
        ):
            self.assertEqual(EVIDENCE, rebuild())
        self.assertEqual(
            {
                "repository": REPOSITORY,
                "pull_number": PULL,
                "observed_at": None,
                "merge_evidence": True,
            },
            snapshot.call_args.kwargs,
        )
        self.assertIs(reader, snapshot.call_args.args[0])
        evidence.assert_called_once_with({"s": 1}, project_root=ROOT)


class CheckoutRevisionTests(unittest.TestCase):
    """The checkout's revision is read by git alone, found on a fixed trusted path
    and run by its absolute name, never by a bare name the caller's PATH resolves
    (DeepSource and Codacy on #426, the preparation helper's precedent)."""

    def test_git_runs_by_its_absolute_trusted_path(self) -> None:
        guard = _guard()
        calls: list[list[str]] = []

        def run(argv: list[str], **options: Any) -> Any:
            calls.append(list(argv))
            self.assertNotIn("GIT_DIR", options["env"])
            out = MAIN + "\n" if "rev-parse" in argv else ""
            return mock.Mock(stdout=out, returncode=0)

        with (
            mock.patch.dict(os.environ, {"GIT_DIR": "/elsewhere"}),
            mock.patch.object(
                guard.shutil, "which", return_value="/usr/bin/git"
            ) as which,
            mock.patch.object(guard.subprocess, "run", side_effect=run),
        ):
            self.assertEqual(MAIN, guard.read_checkout_revision(ROOT))
        which.assert_called_with("git", path=guard.TRUSTED_PATH)
        self.assertEqual({"/usr/bin/git"}, {argv[0] for argv in calls})

    def test_an_untracked_file_in_the_checkout_refuses(self) -> None:
        """CodeAnt on #426: an untracked file is not protected main's either. A
        stray decision changes what the rebuild reads, so a checkout with one is not
        the protected revision, however clean its tracked files are."""
        guard = _guard()
        git = shutil.which("git", path=guard.TRUSTED_PATH)
        if git is None:
            self.skipTest("git is unavailable")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

        def run(directory: str, *arguments: str) -> None:
            subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                [git, "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
                cwd=directory,
                env=environment,
                check=True,
                capture_output=True,
            )

        with tempfile.TemporaryDirectory() as raw:
            run(raw, "init", "-q")
            (Path(raw) / "tracked.txt").write_text("x", encoding="utf-8")
            run(raw, "add", "tracked.txt")
            run(raw, "commit", "-q", "-m", "x")
            self.assertRegex(guard.read_checkout_revision(Path(raw)), r"^[0-9a-f]{40}$")
            (Path(raw) / "sitecustomize.py").write_text("", encoding="utf-8")
            with self.assertRaises(guard.Refused):
                guard.read_checkout_revision(Path(raw))

    def test_an_ignored_file_in_the_checkout_refuses(self) -> None:
        """Codex and CodeAnt on #426: an ignored file, such as a `*.pyc` the
        repository ignores, is not protected main's either."""
        guard = _guard()
        git = shutil.which("git", path=guard.TRUSTED_PATH)
        if git is None:
            self.skipTest("git is unavailable")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory() as raw:
            for arguments in (
                ["init", "-q"],
                ["add", "."],
                ["commit", "-q", "-m", "x"],
            ):
                if arguments[0] == "add":
                    (Path(raw) / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
                subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                    [git, "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
                    cwd=raw,
                    env=environment,
                    check=True,
                    capture_output=True,
                )
            self.assertRegex(guard.read_checkout_revision(Path(raw)), r"^[0-9a-f]{40}$")
            (Path(raw) / "sitecustomize.pyc").write_bytes(b"x")
            with self.assertRaises(guard.Refused):
                guard.read_checkout_revision(Path(raw))

    def test_git_runs_no_configured_program_and_sees_no_credential(self) -> None:
        """Codex on #426: a `core.fsmonitor` in the checkout's or the user's Git
        configuration would run with the guard's credential in reach. The guard's
        git loads no global or system configuration, disables the monitor and hooks,
        and is never handed a credential."""
        guard = _guard()
        git = shutil.which("git", path=guard.TRUSTED_PATH)
        if git is None:
            self.skipTest("git is unavailable")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            checkout, home = root / "checkout", root / "home"
            checkout.mkdir()
            home.mkdir()
            monitor = root / "monitor.sh"
            marker = root / "monitor-ran"
            monitor.write_text(
                f'#!/bin/sh\necho "$GH_TOKEN" >> {marker}\n', encoding="utf-8"
            )
            monitor.chmod(0o700)
            environment = {"PATH": guard.TRUSTED_PATH, "HOME": str(home)}
            for arguments in (
                ["init", "-q"],
                ["commit", "-q", "--allow-empty", "-m", "x"],
                ["config", "core.fsmonitor", str(monitor)],
            ):
                subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                    [git, "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
                    cwd=checkout,
                    env=environment,
                    check=True,
                    capture_output=True,
                )
            (home / ".gitconfig").write_text(
                f"[core]\n\tfsmonitor = {monitor}\n", encoding="utf-8"
            )
            with mock.patch.dict(
                os.environ, {**environment, "GH_TOKEN": "credential-1"}, clear=True
            ):
                self.assertRegex(
                    guard.read_checkout_revision(checkout), r"^[0-9a-f]{40}$"
                )
            self.assertFalse(marker.exists())

    def test_without_git_on_the_trusted_path_it_refuses(self) -> None:
        guard = _guard()
        with (
            mock.patch.object(guard.shutil, "which", return_value=None),
            self.assertRaises(guard.Refused),
        ):
            guard.read_checkout_revision(ROOT)


RUNBOOK = ROOT / "knowledge" / "runbooks" / "operate-the-merge-gate.md"
# The stand-ins the launch runs: a guard that records that it ran and whether it holds
# the minted credential, and a startup module that records what it could reach.
_STUB_GUARD = (
    "import os, pathlib, sys\n"
    "pathlib.Path(os.environ['HOME'], 'guard-ran').write_text(\n"
    "    os.environ.get('GH_TOKEN', '') + ' ' + ' '.join(sys.argv[1:])\n"
    ")\n"
    'print(\'{"result": "PROCEED"}\')\n'
)
_STARTUP_MODULE = (
    "import os, pathlib\n"
    "pathlib.Path(os.environ.get('HOME', '/nonexistent'), 'reached').write_text(\n"
    "    os.environ.get('GH_TOKEN', '')\n"
    ")\n"
)
_MINT = "#!/bin/sh\n: > \"$HOME/minted\"\nprintf 'credential-%s' 1\n"


class GuardLaunchTests(unittest.TestCase):
    """The PAO (6132349006), Codex and CodeAnt on #426: the runbook's launch checks
    the checkout by a git read that must succeed, ignored files included, before any
    credential exists, and starts the interpreter isolated, so no file of the
    checkout runs at startup with the credential present. Run as the runbook writes
    it, against real checkouts."""

    @staticmethod
    def _launch() -> str:
        text = RUNBOOK.read_text(encoding="utf-8")
        found = re.search(r"\n  guard_merge\(\) \{\n.*?\n  \}\n", text, re.S)
        if found is None:
            raise AssertionError("the runbook defines no guard_merge launch")
        return found.group(0)

    @staticmethod
    def _git(directory: Path, *arguments: str) -> None:
        git = shutil.which("git", path=_guard().TRUSTED_PATH)
        assert git is not None  # nosec B101 -- a test precondition
        subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [git, "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
            cwd=directory,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            check=True,
            capture_output=True,
        )

    def _checkout(self, root: Path, *, tracked_startup: bool = False) -> Path:
        checkout = root / "checkout"
        (checkout / "ci").mkdir(parents=True)
        (checkout / "ci" / "merge_admission_guard.py").write_text(
            _STUB_GUARD, encoding="utf-8"
        )
        (checkout / ".gitignore").write_text(
            "ignored-startup/\n*.pyc\n", encoding="utf-8"
        )
        if tracked_startup:
            (checkout / "sitecustomize.py").write_text(
                _STARTUP_MODULE, encoding="utf-8"
            )
        self._git(checkout, "init", "-q")
        self._git(checkout, "add", ".")
        self._git(checkout, "commit", "-q", "-m", "x")
        return checkout

    def _run(self, root: Path, cwd: Path, **environment: str) -> int:
        home = root / "home"
        helper = home / ".config" / "gnostoa-agent" / "bin"
        helper.mkdir(parents=True, exist_ok=True)
        (helper / "agent-token.sh").write_text(_MINT, encoding="utf-8")
        (helper / "agent-token.sh").chmod(0o700)
        shell = shutil.which("bash", path=_guard().TRUSTED_PATH)
        assert shell is not None  # nosec B101 -- a test precondition
        script = self._launch() + "guard_merge --repository r --pull-number 1\n"
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [shell, "-c", script],
            cwd=cwd,
            env={
                "HOME": str(home),
                "PATH": _guard().TRUSTED_PATH,
                "PYTHONPATH": str(cwd),
                **environment,
            },
            capture_output=True,
            check=False,
        )
        return completed.returncode

    @staticmethod
    def _results(root: Path) -> tuple[bool, bool, bool]:
        home = root / "home"
        return (
            (home / "minted").exists(),
            (home / "guard-ran").exists(),
            (home / "reached").exists(),
        )

    def test_a_clean_checkout_runs_the_guard_with_its_credential(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            checkout = self._checkout(root)
            self.assertEqual(0, self._run(root, checkout))
            self.assertEqual((True, True, False), self._results(root))
            ran = (root / "home" / "guard-ran").read_text(encoding="utf-8")
            self.assertTrue(ran.startswith("credential-1 "))

    def test_no_startup_module_runs_beside_the_credential(self) -> None:
        """Neither protected main's own `sitecustomize.py`, which the caller's
        `PYTHONPATH` would reach, nor a `usercustomize.py` in the user site of the
        `HOME` the fresh shell keeps: the interpreter is isolated, and the checkout
        joins its path only after startup."""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            checkout = self._checkout(root, tracked_startup=True)
            version = f"python{sys.version_info.major}.{sys.version_info.minor}"
            user_site = root / "home" / ".local" / "lib" / version / "site-packages"
            user_site.mkdir(parents=True)
            (user_site / "usercustomize.py").write_text(
                _STARTUP_MODULE, encoding="utf-8"
            )
            self.assertEqual(0, self._run(root, checkout))
            self.assertEqual((True, True, False), self._results(root))

    def test_a_checkout_that_is_not_exactly_its_revision_stops_before_the_credential(
        self,
    ) -> None:
        for name, plant in (
            ("an untracked startup module", "sitecustomize.py"),
            ("an ignored startup module", "ignored-startup/sitecustomize.py"),
            ("an ignored bytecode file", "sitecustomize.pyc"),
        ):
            with self.subTest(name), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                checkout = self._checkout(root)
                target = checkout / plant
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(_STARTUP_MODULE, encoding="utf-8")
                self.assertNotEqual(0, self._run(root, checkout))
                self.assertEqual((False, False, False), self._results(root))

    def test_the_launch_s_git_read_runs_no_configured_program(self) -> None:
        """Codex on #426: the read before the mint loads no global or system
        configuration and disables the checkout's `core.fsmonitor`, so no program
        the configuration names runs at all."""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            checkout = self._checkout(root)
            marker = root / "monitor-ran"
            monitor = root / "monitor.sh"
            monitor.write_text(f"#!/bin/sh\n: > {marker}\n", encoding="utf-8")
            monitor.chmod(0o700)
            self._git(checkout, "config", "core.fsmonitor", str(monitor))
            self.assertEqual(0, self._run(root, checkout))
            self.assertEqual((True, True, False), self._results(root))
            self.assertFalse(marker.exists())

    def test_the_guard_imports_under_an_isolated_interpreter(self) -> None:
        """Run as `guard_merge` runs it: `python3 -I`, no `PYTHONPATH`. The guard adds
        its checkout to the path itself, after startup."""
        python = shutil.which("python3", path=_guard().TRUSTED_PATH)
        assert python is not None  # nosec B101 -- a test precondition
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [python, "-I", "-B", str(GUARD_PATH), "--help"],
            cwd="/",
            env={"PATH": _guard().TRUSTED_PATH},
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_a_failed_git_read_stops_before_the_credential(self) -> None:
        """The PAO's falsifier: no checkout to read, and the caller's Git routing
        pointing at another, clean one. The read fails, so nothing starts."""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            elsewhere = self._checkout(root)
            plain = root / "plain"
            plain.mkdir()
            (plain / "sitecustomize.py").write_text(_STARTUP_MODULE, encoding="utf-8")
            (plain / "ci").mkdir()
            (plain / "ci" / "merge_admission_guard.py").write_text(
                _STUB_GUARD, encoding="utf-8"
            )
            code = self._run(
                root,
                plain,
                GIT_DIR=str(elsewhere / ".git"),
                GIT_WORK_TREE=str(elsewhere),
            )
            self.assertNotEqual(0, code)
            self.assertEqual((False, False, False), self._results(root))


class GuardCommandTests(unittest.TestCase):
    @staticmethod
    def _main(
        argv: list[str], environment: dict[str, str], **patches: Any
    ) -> tuple[int, str]:
        guard = _guard()
        out = io.StringIO()
        with (
            mock.patch.dict(os.environ, environment),
            redirect_stdout(out),
            redirect_stderr(io.StringIO()),
            mock.patch.multiple(guard, **patches),
        ):
            code = int(guard.main(argv))
        return code, out.getvalue()

    ARGV = (
        "--repository",
        REPOSITORY,
        "--pull-number",
        str(PULL),
        "--approved",
        HEAD,
        "--app-id",
        str(MA0_APP),
    )

    def test_proceed_exits_zero_and_a_refusal_one(self) -> None:
        proceed = {"result": "PROCEED", "workflow_run_id": RUN}
        code, out = self._main(
            list(self.ARGV),
            {GUARD_CREDENTIAL: "x" * 40},
            guard=mock.Mock(return_value=proceed),
            _client=mock.Mock(),
            read_checkout_revision=mock.Mock(return_value=MAIN),
            rebuilders=mock.Mock(return_value=(mock.Mock(), mock.Mock())),
        )
        self.assertEqual((0, proceed), (code, json.loads(out)))
        code, out = self._main(
            list(self.ARGV),
            {GUARD_CREDENTIAL: "x" * 40},
            guard=mock.Mock(side_effect=_guard().Refused("the check is another App's")),
            _client=mock.Mock(),
            read_checkout_revision=mock.Mock(return_value=MAIN),
            rebuilders=mock.Mock(return_value=(mock.Mock(), mock.Mock())),
        )
        self.assertEqual(1, code)
        self.assertEqual("REFUSED", json.loads(out)["result"])

    def test_without_a_token_or_an_exact_head_it_does_not_start(self) -> None:
        started = mock.Mock(side_effect=AssertionError("no guard"))
        self.assertEqual(
            2,
            self._main(
                list(self.ARGV),
                {GUARD_CREDENTIAL: ""},
                guard=started,
                _client=mock.Mock(),
            )[0],
        )
        argv = list(self.ARGV)
        argv[argv.index("--approved") + 1] = "abc"
        self.assertEqual(
            2,
            self._main(
                argv, {GUARD_CREDENTIAL: "x" * 40}, guard=started, _client=mock.Mock()
            )[0],
        )


if __name__ == "__main__":
    unittest.main()
