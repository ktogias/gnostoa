"""Collect the review context: the GitHub Actions composition of the context core.

Decisions 0094 and 0100. Every rule about what the reviewer is shown when something is
missing or degraded is the neutral core's (`tools/agent_review_context.py`); how a Pull
Request's comparison is read is the GitHub adapter's (`tools/agent_review_github.py`).
This entrypoint reads the admitted identity from the environment, confines its paths,
runs the base collector and the chunker in their own processes, and composes them.

The collector runs in its own process for the reason the step's shell guarded it: its
failure must not end the step, which would take the unified diff with it, and every
escape inside it has been closed one at a time -- the step should not depend on having
found them all.

This script is trusted input: the checkout is the protected revision.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess  # nosec B404 -- fixed argument lists, never a shell
import sys

from tools import agent_review_context as context_core
from tools import agent_review_github as github
from tools.agent_review_paths import within

HERE = pathlib.Path(__file__).resolve().parent
# The protected checkout, which the child processes import the pipeline from.
CHECKOUT = HERE.parents[1]
_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
_ITEM = re.compile(r"\A[1-9][0-9]{0,9}\Z")


def _child_environment() -> dict[str, str]:
    """The step's own environment, with the pipeline importable from the checkout."""
    return {**os.environ, "PYTHONPATH": str(CHECKOUT)}


def run_collector(context: pathlib.Path, repository: str, max_bytes: int) -> int:
    """Run the base collector over ``context`` in its own process; return its status."""
    completed = subprocess.run(  # nosec B603 -- fixed arguments, no shell
        [
            sys.executable,
            str(HERE / "build_review_context.py"),
            str(context),
            repository,
            str(max_bytes),
        ],
        check=False,
        env=_child_environment(),
    )
    return completed.returncode


def run_chunker(context: pathlib.Path, max_bytes: int) -> None:
    """Split ``context/diff.full`` into bounded parts, failing the step if it fails."""
    subprocess.run(  # nosec B603 -- fixed arguments, no shell
        [sys.executable, str(HERE / "chunk_diff.py"), str(context), str(max_bytes)],
        check=True,
        env=_child_environment(),
    )


def change_source(repository: str, base: str, head: str) -> context_core.ChangeSource:
    """Return the change source for the admitted comparison."""
    return github.CompareSource(repository, base, head)


def _identity() -> tuple[str, str, str, str, int] | None:
    """Return the validated repository, change number, base, head and part bound."""
    repository = os.environ.get("REPOSITORY", "")
    pull = os.environ.get("PULL_NUMBER", "")
    base = os.environ.get("BASE_SHA", "")
    head = os.environ.get("HEAD_SHA", "")
    raw_bytes = os.environ.get("MAX_BYTES", "")
    if not github.is_repository(repository) or (pull and not _ITEM.match(pull)):
        return None
    if pull and not (_SHA.match(base) and _SHA.match(head)):
        return None
    if not raw_bytes.isdigit() or int(raw_bytes) <= 0:
        return None
    return repository, pull, base, head, int(raw_bytes)


def main(argv: list[str]) -> int:
    """Collect the review context for the admitted request into ``CONTEXT_DIR``."""
    if len(argv) != 1:
        print(f"usage: {argv[0]}", file=sys.stderr)
        return 2
    identity = _identity()
    if identity is None:
        print("ERROR: an identity from the workflow did not validate", file=sys.stderr)
        return 2
    repository, pull, base, head, max_bytes = identity
    raw_context = os.environ.get("CONTEXT_DIR", "")
    try:
        context = within(
            raw_context, "GITHUB_WORKSPACE", must_exist=os.path.lexists(raw_context)
        )
        request = within(
            str(pathlib.Path(os.environ.get("RUNNER_TEMP", "")) / "claude-request"),
            "RUNNER_TEMP",
            must_exist=True,
        )
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    context_core.prepare(context, request)
    if not pull:
        (context / "README").write_text(github.NO_CHANGE_REQUEST, encoding="utf-8")
        return 0
    try:
        context_core.assemble(
            context,
            change_source(repository, base, head),
            collect=lambda target: run_collector(target, repository, max_bytes),
            chunk=lambda target: run_chunker(target, max_bytes),
            vocabulary=github.VOCABULARY,
        )
    except (context_core.Unavailable, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
