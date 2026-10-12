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
import shutil
import subprocess  # nosec B404 -- the test's own git repository
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


class _GitHub:
    """The provider as the guard reads it. It answers the reads it was given and the
    one dispatch; it has no merge, so a guard that tried to merge would fail."""

    def __init__(self) -> None:
        self.pull = {
            "number": PULL,
            "state": "open",
            "head": {"sha": HEAD},
            "base": {"ref": "main"},
        }
        self.main = MAIN
        self.dispatched: dict[str, Any] | None = {
            "workflow_run_id": RUN,
            "run_url": f"{API}/actions/runs/{RUN}",
            "html_url": f"https://github.com/{REPOSITORY}/actions/runs/{RUN}",
        }
        self.run = {
            "id": RUN,
            "path": ".github/workflows/merge-admission.yml",
            "event": "workflow_dispatch",
            "head_branch": "main",
            "head_sha": MAIN,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
        }
        self.running_reads = 0
        correlation = {
            "workflow_run_id": RUN,
            "run_attempt": 1,
            "protected_revision": MAIN,
            "unbundled_evidence_sha256": merge_admission_checks.digest(EVIDENCE),
        }
        self.check = {
            "id": CHECK,
            "name": "merge-admission",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "success",
            "external_id": "e" * 64,
            "app": {"id": MA0_APP, "slug": "gnostoa-ma0"},
            "output": {
                "title": "merge-admission: ALLOW",
                "summary": "s",
                "text": merge_admission_checks.correlation_text(correlation),
            },
        }
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.reads: list[str] = []
        self.after_dispatch: list[Any] = []
        self.read_as: dict[str, Any] = {}

    @staticmethod
    def url(path: str) -> str:
        return f"https://api.github.com/{path.lstrip('/')}"

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        self.reads.append(url)
        latest = (
            f"{API}/commits/{HEAD}/check-runs"
            "?check_name=merge-admission&filter=latest&per_page=100"
        )
        if url == f"{API}/pulls/{PULL}":
            return copy.deepcopy(self.pull), {}
        if url == f"{API}/branches/main":
            return {"name": "main", "commit": {"sha": self.main}}, {}
        if url == f"{API}/actions/runs/{RUN}":
            if self.running_reads:
                self.running_reads -= 1
                return {**self.run, "status": "in_progress", "conclusion": None}, {}
            return copy.deepcopy(self.run), {}
        if url == latest:
            return {"total_count": 1, "check_runs": [copy.deepcopy(self.check)]}, {}
        if url == f"{API}/check-runs/{self.check['id']}":
            return {**copy.deepcopy(self.check), **self.read_as}, {}
        raise AssertionError(f"unexpected read {url}")

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        self.posts.append((url, copy.deepcopy(payload)))
        if url != f"{API}/actions/workflows/merge-admission.yml/dispatches":
            raise AssertionError(f"unexpected write {url}")
        for change in self.after_dispatch:
            change(self)
        return copy.deepcopy(self.dispatched)


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
        github.running_reads = 3
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
        ((_, payload),) = github.posts
        self.assertEqual({"ref": "main", "inputs": {"pull_number": str(PULL)}}, payload)
        # The last reads are the subject and protected main, after the comparison.
        self.assertEqual(
            [f"{API}/pulls/{PULL}", f"{API}/branches/main"], github.reads[-2:]
        )

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

    def test_a_dispatch_that_names_no_run_is_refused(self) -> None:
        """Without the run the dispatch created there is nothing to correlate, and
        time is no substitute."""
        for answer in (
            None,
            {},
            {"workflow_run_id": "9001"},
            {"workflow_run_id": True},
        ):
            with self.subTest(answer=answer):
                github = _GitHub()
                github.dispatched = answer
                self.assertRefused(github, "dispatch")

    def test_only_the_protected_admission_run_counts(self) -> None:
        for name, change in (
            ("another workflow", {"path": ".github/workflows/verification.yml"}),
            ("another event", {"event": "schedule"}),
            ("another branch", {"head_branch": "feature"}),
            ("another revision", {"head_sha": OTHER}),
            ("another run", {"id": RUN + 1}),
            ("a failed run", {"conclusion": "failure"}),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.run.update(change)
                self.assertRefused(github, "run")

    def test_a_run_that_does_not_finish_in_time_is_refused(self) -> None:
        github = _GitHub()
        github.running_reads = 10_000
        self.assertRefused(github, "did not complete")

    def test_only_the_pinned_app_s_latest_success_counts(self) -> None:
        for name, change in (
            ("another App", {"app": {"id": OTHER_APP}}),
            ("a failure", {"conclusion": "failure"}),
            ("a neutral", {"conclusion": "neutral"}),
            ("still pending", {"status": "in_progress", "conclusion": None}),
            ("another head", {"head_sha": OTHER}),
            ("another check", {"name": "merge-admission-x"}),
        ):
            with self.subTest(name):
                github = _GitHub()
                github.check.update(change)
                self.assertRefused(github, "check")

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

    def test_an_old_or_foreign_result_never_substitutes(self) -> None:
        """An earlier success, another dispatch's run or another revision's carries
        another correlation, and is refused even while it is the latest run."""
        for name, field, value in (
            ("another run", "workflow_run_id", RUN - 1),
            ("another attempt", "run_attempt", 2),
            ("another revision", "protected_revision", OTHER),
        ):
            with self.subTest(name):
                github = _GitHub()
                correlation = dict(
                    merge_admission_checks.correlation_of(github.check) or {}
                )
                self.assertTrue(correlation)
                correlation[field] = value
                github.check["output"]["text"] = (
                    merge_admission_checks.correlation_text(correlation)
                )
                self.assertRefused(github, "correlat")
        github = _GitHub()
        github.check["output"]["text"] = "no record"
        self.assertRefused(github, "correlat")

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

        for name, options in (
            ("the subject unreadable", {"rebuild": unreadable}),
            ("the subject invalid", {"rebuild": invalid}),
            ("the population unreadable", {"population": unreadable}),
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
        self.assertEqual(
            [f"{API}/actions/workflows/merge-admission.yml/dispatches"],
            [url for url, _ in github.posts],
        )
        self.assertFalse(hasattr(github, "put"))


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
            self.assertEqual(MAIN, guard._checkout_revision(ROOT))
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
            subprocess.run(  # nosec B603 -- the test's own fixed git arguments
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
            self.assertRegex(guard._checkout_revision(Path(raw)), r"^[0-9a-f]{40}$")
            (Path(raw) / "sitecustomize.py").write_text("", encoding="utf-8")
            with self.assertRaises(guard.Refused):
                guard._checkout_revision(Path(raw))

    def test_without_git_on_the_trusted_path_it_refuses(self) -> None:
        guard = _guard()
        with (
            mock.patch.object(guard.shutil, "which", return_value=None),
            self.assertRaises(guard.Refused),
        ):
            guard._checkout_revision(ROOT)


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
            _checkout_revision=mock.Mock(return_value=MAIN),
            _rebuilders=mock.Mock(return_value=(mock.Mock(), mock.Mock())),
        )
        self.assertEqual((0, proceed), (code, json.loads(out)))
        code, out = self._main(
            list(self.ARGV),
            {GUARD_CREDENTIAL: "x" * 40},
            guard=mock.Mock(side_effect=_guard().Refused("the check is another App's")),
            _client=mock.Mock(),
            _checkout_revision=mock.Mock(return_value=MAIN),
            _rebuilders=mock.Mock(return_value=(mock.Mock(), mock.Mock())),
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
