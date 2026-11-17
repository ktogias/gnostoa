"""Publish the reviewer's report: the GitHub Actions composition (Decision 0100).

The rules are the neutral core's (`tools/agent_review_report.py`: a literal-text
summary, a bounded handoff written status-last) and the Claude Code adapter's
(`tools/agent_review_claude_code.py`: what the execution file says). This file only
wires them to what GitHub Actions supplies: the execution file, the step summary and
the handoff directory under the runner's temporary area.

The pinned action's own `display_report` input warns that it "outputs Claude-authored
content in the GitHub Step Summary" and "should only be used in cases where the action
is used solely with trusted input" -- and this job's input is a candidate Pull Request,
which is untrusted by definition. So the action's rendering is disabled and the report
is published here instead (Decision 0094 rule 22).

Invoked from `.github/workflows/claude.yml`, which runs from the repository's default
branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import os
import pathlib
import sys

from tools import agent_review_claude_code as claude
from tools.agent_review_paths import within
from tools.agent_review_report import (
    for_handoff,
    render_summary,
    unavailable,
)
from tools.agent_review_report import write_handoff as write_report

_NO_EXECUTION = (
    "The reviewer produced no execution output: it failed before writing\n"
    "one, so there is nothing to publish. The job's logs hold the reason."
)


def render(execution_file: pathlib.Path) -> str:
    """Return the publishable summary for ``execution_file``."""
    return render_summary(
        claude.read_report(execution_file), reviewer=claude.REVIEWER_NAME
    )


def handoff(execution_file: pathlib.Path) -> tuple[str, str, bool]:
    """Return the status, text and cut the posting job will receive."""
    bounded = for_handoff(claude.read_report(execution_file))
    return bounded.status, bounded.text, bounded.cut


def write_handoff(execution_file: pathlib.Path, directory: pathlib.Path) -> None:
    """Hand the report in ``execution_file`` over through ``directory``."""
    write_report(claude.read_report(execution_file), directory)


def main(argv: list[str]) -> int:
    """Publish the reviewer's report from the execution file named by ``argv``.

    A fourth argument names a directory to hand the report to the posting job in.
    """
    if len(argv) not in (3, 4):
        print(
            f"usage: {argv[0]} <execution-file> <summary-file> [<handoff-directory>]",
            file=sys.stderr,
        )
        return 2
    # The step no longer gates on the action having produced an execution file, so this
    # has to handle its absence. Confining a path that does not exist, or refusing an
    # empty one, would crash here and publish nothing -- the same silent failure the
    # gate removal was meant to end, one layer down. The adapter already reports an
    # unreadable file, so the path is confined without requiring it to exist.
    raw = argv[1]
    if not raw.strip():
        summary_only = within(argv[2], "", must_exist=False)
        with summary_only.open("a", encoding="utf-8") as handle:
            # The heading every other unavailable case uses. "Claude review report"
            # is reserved for a finished review, and a reader scans headings.
            handle.write(
                render_summary(
                    unavailable(_NO_EXECUTION), reviewer=claude.REVIEWER_NAME
                )
            )
        return 0
    execution = within(raw, "RUNNER_TEMP", must_exist=False)
    # The summary path is not held to a root. GITHUB_STEP_SUMMARY happens to live under
    # RUNNER_TEMP on today's hosted runners, but that is an implementation detail, and
    # refusing the report because the runner moved a file would lose the review over an
    # assumption about its layout. It is still resolved, required to be absolute with an
    # existing parent, and refused if it traverses.
    summary = within(argv[2], "", must_exist=False)
    with summary.open("a", encoding="utf-8") as handle:
        handle.write(render(execution))
    if len(argv) == 4:
        # After the summary, so a handoff that cannot be made never costs the review its
        # first destination. The posting job then reports the review as unavailable.
        try:
            if os.path.lexists(argv[3]):
                raise ValueError(f"the handoff directory {argv[3]} already exists")
            write_handoff(execution, within(argv[3], "RUNNER_TEMP", must_exist=False))
        except (OSError, ValueError) as error:
            print(f"ERROR: could not hand the report over: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
