"""Assemble a review's bounded context from a change source (Decisions 0094, 0100).

The context is what the reviewer reads instead of a checkout: the comparison's commit
log, its file summaries, the base revision's bytes, the unified diff in bounded parts,
and -- wherever any of that is missing or degraded -- a notice saying which, in the
artefact the reviewer is told to read for it. Every rule about *what is published
when something is missing* is here; how the comparison is read is the change source's,
and how the base bytes are fetched is the collector's.

Three steps are composed rather than performed here, each by the caller:

* a change source reads the comparison, its commits and its unified diff;
* the collector turns the comparison into the commit log, the summaries, the per-file
  patches and the base bytes, in its own process, and reports how far it got;
* the chunker splits the unified diff into bounded parts.

Refusal is the default for anything this module cannot establish: a comparison that is
not one, or an unreadable answer, ends the assembly; only the provider's explicit
refusal to render the unified diff reaches the lossy per-file fallback.
"""

from __future__ import annotations

import base64
import json
import pathlib
import shutil
from collections.abc import Callable, Iterable
from typing import NamedTuple, Protocol

# How far the collector got, by its exit status. 3 is its own: the collection finished
# but the comparison could not be read as a whole, so no changed file was named.
COLLECTED = "collected"
UNLISTED = "unlisted"
FAILED = "failed"
_UNLISTED_STATUS = 3

FAILED_COLLECTION_NOTICE = (
    "provider-error base-context: the collection did not finish, so\n"
    "base/ holds only the subset fetched before it stopped. Each file\n"
    "present is complete, because each is renamed into place whole,\n"
    "but the set is partial and this manifest does not name which\n"
    "paths were expected. A changed file absent from base/ is not\n"
    "examined: its absence is this failure, not the base revision.\n"
    "The step log carries the reason.\n"
)
_REFUSED_DIFF = (
    "NOTE: the provider refused the unified diff for this comparison.\n"
    "These hunks come from the per-file patches instead, so context\n"
    "outside each hunk is absent and capped files may be missing.\n"
    "Per-file hunks carry no file modes: a mode change, such as a script\n"
    "losing its executable bit, cannot be seen; report modes as not examined.\n"
)
_LISTED_NOTHING_BUT_CHANGED = (
    "provider-error changed-content: the comparison listed no files, but\n"
    "the unified diff is not empty: the files it shows have no base bytes\n"
    "and no entry above.\n"
)
_NOT_EXAMINED = (
    "No changed content is present here. Treat every changed file as\nnot examined.\n"
)
_EMPTY_DIFF_CAUSE = {
    (True, COLLECTED): (
        "the provider refused the unified diff,\n"
        "and the per-file patches carried no hunks. Each changed file\n"
        "without hunks is listed in no-patch.txt and classified in\n"
        "base.manifest.\n"
    ),
    (True, FAILED): (
        "the provider refused the unified diff,\n"
        "and the per-file patches were unavailable because the base\n"
        "context collection failed.\n"
    ),
    (True, UNLISTED): (
        "the provider refused the unified diff,\n"
        "and the per-file patches were unavailable because the\n"
        "comparison could not be read.\n"
    ),
    (False, COLLECTED): (
        "the provider returned an empty unified diff,\n"
        "but its comparison listed changed files (diff.stat): the two\n"
        "answers contradict.\n"
    ),
    (False, FAILED): (
        "the provider returned an empty unified diff,\n"
        "but the base context collection failed, so the comparison was\n"
        "not checked for changed files.\n"
    ),
    (False, UNLISTED): (
        "the provider returned an empty unified diff,\n"
        "but the comparison could not be read, so it was not checked\n"
        "for changed files.\n"
    ),
}


class Unavailable(RuntimeError):
    """Something the context cannot be assembled without could not be read."""


class DiffRefused(RuntimeError):
    """The provider declined to render the unified diff: the one lossy fallback."""


class Commit(NamedTuple):
    """One commit of the comparison: its short id and the first line of its message."""

    short_id: str
    subject: str


class ChangeSource(Protocol):
    """The change-source role: a comparison, its commits and its unified diff.

    Each method raises ``Unavailable`` for an answer it could not read;
    ``unified_diff`` raises ``DiffRefused`` only for the provider's explicit refusal.
    """

    def comparison(self) -> bytes:
        """Return the comparison document, as the provider answered it."""
        raise NotImplementedError

    def commits(self) -> Iterable[Commit]:
        """Return the comparison's commits, as many as the provider lists."""
        raise NotImplementedError

    def unified_diff(self) -> bytes:
        """Return the comparison's unified diff."""
        raise NotImplementedError


class Vocabulary(NamedTuple):
    """What the reader calls a change request on this provider."""

    change_request: str


def total_commits(comparison: bytes) -> int:
    """Return the number of commits the comparison says it has, or refuse.

    A comparison that is not an object, or whose count is not a whole number, is not
    one: the count is what tells a capped commit list from a complete one.
    """
    try:
        document = json.loads(comparison)
    except ValueError as error:
        raise Unavailable("the comparison is not a JSON document") from error
    if not isinstance(document, dict):
        raise Unavailable("the comparison is not an object")
    count = document.get("total_commits") or 0
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise Unavailable("the comparison's commit count is not a whole number")
    return count


def write_commits(target: pathlib.Path, commits: Iterable[Commit]) -> None:
    """Write the commits as the collector reads them: an id and a base64 subject.

    Encoded, so no subject reaches a line-oriented artefact as text: the collector
    decodes each and neutralises every line separator it carries.
    """
    with target.open("w", encoding="utf-8") as handle:
        for commit in commits:
            subject = base64.b64encode(commit.subject.encode("utf-8")).decode("ascii")
            handle.write(f"{commit.short_id} {subject}\n")


def _non_empty(path: pathlib.Path) -> bool:
    """Return whether ``path`` is a file with content."""
    return path.is_file() and path.stat().st_size > 0


def _append(path: pathlib.Path, text: str) -> None:
    """Append ``text`` to ``path``, creating it."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def collection_state(status: int) -> str:
    """Return how far the collector got, from its exit status."""
    if status == 0:
        return COLLECTED
    if status == _UNLISTED_STATUS:
        return UNLISTED
    return FAILED


def _after_a_failed_collection(context: pathlib.Path) -> bool:
    """Keep what the collector wrote, create only what it did not, and say so.

    The collector writes the commit log, the summaries, the assembled per-file diff and
    the base bytes before its per-file fetch loop, where a late failure is most likely,
    so by then each is already correct. Only the missing are created: creating them
    unconditionally destroyed exactly the degraded context this exists to preserve.
    Returns whether the commit log had to be made here.
    """
    (context / "base").mkdir(exist_ok=True)
    for name in ("diff.stat", "no-patch.txt", "assembled.diff"):
        (context / name).touch(exist_ok=True)
    log = context / "commits.log"
    made = not log.exists()
    log.touch(exist_ok=True)
    # The staging area holds only half-written files; nothing in base/ is touched,
    # since no name there can be told apart from a repository file's.
    shutil.rmtree(context / ".base-staging", ignore_errors=True)
    _append(context / "base.manifest", FAILED_COLLECTION_NOTICE)
    return made


def _note_the_commit_count(context: pathlib.Path, total: int, made: bool) -> None:
    """Say when the commit log is not the whole list, and whose shortfall it is."""
    log = context / "commits.log"
    if made:
        # The zero is the step's own, not a truncation the provider performed.
        _append(log, "[commit log unavailable: the base-context collection failed]\n")
        return
    if not log.is_file():
        return
    with log.open(encoding="utf-8", errors="replace") as handle:
        listed = sum(1 for line in handle if not line.startswith(">"))
    if total > listed:
        _append(log, f"[provider listed {listed} of {total} commits]\n")


def _unified_diff(context: pathlib.Path, source: ChangeSource) -> bool:
    """Write the unified diff, or the per-file fallback on a refusal; True if refused."""
    full = context / "diff.full"
    assembled = context / "assembled.diff"
    try:
        full.write_bytes(source.unified_diff())
    except DiffRefused:
        if not assembled.is_file():
            raise Unavailable(
                "the provider refused the unified diff and no per-file diff exists"
            ) from None
        assembled.replace(full)
        (context / "patches-source").write_text(_REFUSED_DIFF, encoding="utf-8")
        return True
    assembled.unlink(missing_ok=True)
    return False


def _publish_the_diff(
    context: pathlib.Path,
    state: str,
    refused: bool,
    chunk: Callable[[pathlib.Path], None],
    vocabulary: Vocabulary,
) -> None:
    """Publish the diff in parts, or say exactly why there is none to publish.

    "No changes" needs all three: no refusal, a comparison that was read, and an empty
    file list. Anything less leaves the change unestablished, and the reviewer is told
    to treat every changed file as not examined.
    """
    full_bytes = (context / "diff.full").stat().st_size
    listed = _non_empty(context / "diff.stat")
    if full_bytes > 0 and state == COLLECTED and not listed:
        _append(context / "base.manifest", _LISTED_NOTHING_BUT_CHANGED)
    patch = context / "diff.patch"
    if full_bytes == 0 and not refused and state == COLLECTED and not listed:
        patch.write_text(
            f"No changes between base and head for this {vocabulary.change_request}.\n",
            encoding="utf-8",
        )
    elif full_bytes == 0:
        patch.write_text(
            "provider-error changed-content: "
            + _EMPTY_DIFF_CAUSE[(refused, state)]
            + _NOT_EXAMINED,
            encoding="utf-8",
        )
    else:
        chunk(context)


def prepare(context: pathlib.Path, request: pathlib.Path) -> None:
    """Start the context afresh, with the admitted request's artefacts in it."""
    shutil.rmtree(context, ignore_errors=True)
    context.mkdir(parents=True)
    shutil.copytree(request, context / "request", symlinks=True)


def assemble(
    context: pathlib.Path,
    source: ChangeSource,
    *,
    collect: Callable[[pathlib.Path], int],
    chunk: Callable[[pathlib.Path], None],
    vocabulary: Vocabulary,
) -> str:
    """Assemble the context for one change request; return how far collection got.

    ``collect`` runs the collector over ``context`` and returns its exit status;
    ``chunk`` splits ``context/diff.full`` into parts. Raises ``Unavailable`` for an
    answer the context cannot do without.
    """
    comparison = source.comparison()
    (context / "comparison.json").write_bytes(comparison)
    total = total_commits(comparison)
    write_commits(context / "commits.b64", source.commits())
    # The collector runs before the unified diff is read, so its failure must not end
    # the assembly: that would take the diff with it and leave the reviewer nothing at
    # all rather than a degraded context.
    state = collection_state(collect(context))
    made = _after_a_failed_collection(context) if state == FAILED else False
    _note_the_commit_count(context, total, made)
    refused = _unified_diff(context, source)
    _publish_the_diff(context, state, refused, chunk, vocabulary)
    for spent in ("diff.full", "comparison.json"):
        (context / spent).unlink(missing_ok=True)
    return state
