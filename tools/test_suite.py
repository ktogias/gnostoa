"""How the repository's test suite runs: in parallel processes, one test module per
task, through unittest-parallel (Decision 0109).

`ci/verify fast`, `knowledge self-check` and the coverage run of `extended` all take
the command from here, so they cannot drift apart.
"""

from __future__ import annotations

import os
import signal
import subprocess  # nosec B404 -- the argv below is literal, with this interpreter
import sys
from pathlib import Path

RUNNER = "unittest_parallel"
# A suite that runs longer than this has hung; the bound stops it rather than the
# hooks or CI waiting forever (Kody on #392).
TIMEOUT_SECONDS = 3600
# The exit status of a run stopped at the bound, as timeout(1) reports it.
TIMED_OUT = 124


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


def run(root: Path) -> int:
    """Run the suite of the repository at ``root`` with this interpreter; its exit
    status, or `TIMED_OUT` when it runs past `TIMEOUT_SECONDS`. The runner starts a
    session of its own, so a stop ends its worker processes too, not only it."""
    with subprocess.Popen(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        command(sys.executable), cwd=root, start_new_session=True
    ) as process:
        try:
            return process.wait(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            print(
                f"ERROR: the test suite ran past {TIMEOUT_SECONDS} s and was stopped",
                file=sys.stderr,
            )
            return TIMED_OUT


def main() -> int:
    """Run the suite of the repository in the working directory."""
    return run(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main())
