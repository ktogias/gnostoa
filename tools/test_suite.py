"""How the repository's test suite runs: in parallel processes, one test module per
task, through unittest-parallel (Decision 0109).

`ci/verify fast`, `knowledge self-check` and the coverage run of `extended` all take
the command from here, so they cannot drift apart.
"""

from __future__ import annotations

import subprocess  # nosec B404 -- the argv below is literal, with this interpreter
import sys
from pathlib import Path

RUNNER = "unittest_parallel"


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
    status."""
    return subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        command(sys.executable), cwd=root, check=False
    ).returncode


def main() -> int:
    """Run the suite of the repository in the working directory."""
    return run(Path.cwd())


if __name__ == "__main__":
    raise SystemExit(main())
