"""How the repository's test suite runs: in parallel processes, one test module per
task, through unittest-parallel (Decision 0109).

`ci/verify fast`, `knowledge self-check` and the coverage run of `extended` all take
the command from here, so they cannot drift apart.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess  # nosec B404 -- the argv below is literal, with this interpreter
import sys
from collections.abc import Mapping
from pathlib import Path

RUNNER = "unittest_parallel"
# A suite that runs longer than this has hung; the bound stops it rather than the
# hooks or CI waiting forever (Kody on #392).
TIMEOUT_SECONDS = 3600
# The exit status of a run stopped at the bound, as timeout(1) reports it.
TIMED_OUT = 124
# How long an interrupted runner has to end its own workers before it is killed.
GRACE_SECONDS = 10


def command(
    python: str, tests: str = "tests", *, coverage_source: str | None = None
) -> list[str]:
    """The suite's command: every test module under ``tests``, each a task of its
    own, across one process per CPU. With ``coverage_source``, branch coverage of that
    package is measured in each process and combined, as `coverage run --branch
    --source` measured it in one."""
    argv = [python, "-m", RUNNER, "--start-directory", tests, "--level", "module"]
    if coverage_source is not None:
        argv += [
            "--coverage",
            "--coverage-branch",
            "--coverage-source",
            coverage_source,
        ]
    return argv


def run(
    root: Path,
    *,
    coverage_source: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> int:
    """Run the suite of the repository at ``root`` with this interpreter; its exit
    status, or `TIMED_OUT` when it runs past `TIMEOUT_SECONDS`.

    The runner and its workers stay in the caller's process group, so the caller's
    own containment reaches them all: preparation's kill of its focused group (Codex
    on #392), a CI job's end, a terminal's Ctrl+C. Past the bound, or on any error
    while waiting, this owner stops the runner and its workers, and the error is
    raised again (Amazon Q and CodeReviewBot.ai on #392).
    """
    with subprocess.Popen(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        command(sys.executable, coverage_source=coverage_source),
        cwd=root,
        env=None if environment is None else dict(environment),
    ) as process:
        try:
            return process.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _stop(process, interrupt=True)
            print(
                f"ERROR: the test suite ran past {TIMEOUT_SECONDS} s and was stopped",
                file=sys.stderr,
            )
            return TIMED_OUT
        except BaseException as error:
            # A terminal's Ctrl+C reached the runner too; a second interrupt could cut
            # its pool's cleanup short.
            _stop(process, interrupt=not isinstance(error, KeyboardInterrupt))
            raise


def _stop(process: subprocess.Popen[bytes], *, interrupt: bool) -> None:
    """Stop the runner and its workers, and reap it.

    Interrupted, the runner's pool ends its own workers, on every system (Codex and
    CodeAnt on #392). A runner still running after `GRACE_SECONDS` is killed, after
    the descendants the system records, deepest first. A process may have ended
    before its kill.
    """
    if interrupt:
        process.send_signal(signal.SIGINT)
    try:
        process.wait(timeout=GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    for pid in [*_descendants(process.pid), process.pid]:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
    process.wait()


def _descendants(pid: int) -> list[int]:
    """The processes under ``pid``, deepest first. None where the system keeps no
    record of a process's children: the caller's containment then stops them."""
    found: list[int] = []
    pending = [pid]
    while pending:
        children = _children(pending.pop())
        found.extend(children)
        pending.extend(children)
    return found[::-1]


def _children(pid: int) -> list[int]:
    """The children of ``pid``, as Linux records them for each of its threads."""
    try:
        tasks = os.listdir(f"/proc/{pid}/task")
    except OSError:
        return []
    children: list[int] = []
    for task in tasks:
        # A process id and a thread id that /proc itself listed: the path cannot
        # leave /proc (DeepSource on #392).
        record = f"/proc/{pid}/task/{task}/children"
        try:
            with open(record, encoding="ascii") as handle:  # skipcq: PTC-W6004
                children.extend(int(word) for word in handle.read().split())
        except (OSError, ValueError):
            continue
    return children


def main() -> int:
    """Run the suite of the repository in the working directory."""
    return run(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main())
