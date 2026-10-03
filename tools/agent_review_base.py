"""Collect a change's exact base revision for the reviewer (Decisions 0094, 0100).

Writes ``commits.log``, ``diff.stat``, ``no-patch.txt``, ``assembled.diff``,
``base.manifest`` and ``base/`` from one comparison, read through a base source.

``base/`` matters most. The bounded reviewer reads the repository's default branch
for its entry route and general context, and that tree is deliberately **not** the
change's base: the branch may have advanced, or the change may target another branch.
Unchanged code read from it can therefore come from a revision the candidate never
saw, which produces interaction findings that are not real. So the exact pre-change
bytes of the changed files this collection could fetch are written here, and every
file it could not is named in ``base.manifest`` with its reason -- for the files the
provider listed. A comparison past the provider's changed-file cap never sends the
later paths at all, so they can be neither fetched nor named; the manifest states that
instead of leaving the omission to look like completeness.

Four properties of that collection are load-bearing, and each exists because getting
it wrong would hand the reviewer something false rather than something missing:

* the revision fetched is the **merge base**, not the base branch tip, because a
  three-dot comparison is computed from the merge base and mixing the two would
  describe two different pre-change states;
* a **renamed** entry is fetched under its previous path, since that is where the base
  holds it, and fetching the new path could return an unrelated file that a swap or
  overwrite rename happens to have replaced;
* bytes that are not an ordinary file's -- a symlink resolved to its target, a blob
  the source would not serve -- are recorded as unavailable rather than written,
  because resolved or empty bytes presented as the exact base are worse than an
  acknowledged gap;
* every path the provider listed and this collection did not write is named in
  ``base.manifest`` with the reason, and a capped comparison says that the paths
  beyond the cap are absent from the manifest entirely.

Bytes are written, never a checkout: no mode, symlink or directory entry from either
side reaches the runner. Provider-supplied names are refused rather than sanitised
when absolute, empty, traversing, or carrying a backslash or NUL, because a name that
should not occur is a reason to stop instead of to guess. The manifest lives outside
``base/`` so it cannot collide with a repository path.

The rules are here; the vocabulary is not. A provider's adapter translates its
comparison into ``ChangedFile`` entries and serves its base revision through the
``BaseSource`` role, whose listings and contents it translates into ``Listing`` and
``Contents``. Blob identity is Git's, which every source of a Git repository shares.
"""

from __future__ import annotations

import base64
import errno
import hashlib
import os
import pathlib
import tempfile
import time
from collections.abc import Callable
from typing import Any, NamedTuple, Protocol, TypeGuard

from tools.agent_review_model import CONTINUATION

MANIFEST = "base.manifest"
# Where every write is staged before its rename: beside base/, never inside it, so an
# interrupted write is absent rather than partial. The step sweeps this same name.
STAGING = ".base-staging"
# The errors a type collision between two changed paths raises: a file where a
# directory goes, or a directory where a file goes.
_COLLISION_ERRNOS = frozenset({errno.EEXIST, errno.ENOTDIR, errno.EISDIR})
# Validated on the raw string. PurePosixPath normalises "a//b" and "." away, so
# inspecting its parts would accept names that should never have been produced.
_REFUSED_COMPONENTS = frozenset({"", ".", ".."})
# A Git object id: the identity a listing's blob and the fetched bytes are checked by.
_HEX = frozenset("0123456789abcdef")
# The listing kinds whose blob is a blob id. A directory's is a tree and a submodule's
# a commit; an absent or unknown kind establishes no identity at all.
_BLOB_KINDS = frozenset({"file", "symlink"})
# The kinds that are facts about the repository when a listing declares them.
_NOT_A_FILE = frozenset({"dir", "symlink", "submodule"})


def is_object_id(value: Any) -> TypeGuard[str]:
    """Return whether ``value`` is an exact Git object id: forty lowercase hex digits."""
    return isinstance(value, str) and len(value) == 40 and set(value) <= _HEX


# ---------------------------------------------------------------------------------
# The vocabulary


class ChangedFile(NamedTuple):
    """One changed file of the comparison, every field as the provider gave it.

    A field the provider gave in the wrong type is None, which every reader handles:
    the adapter names it as the provider's error where it translated the entry.
    """

    path: str
    # One of the comparison statuses: added, removed, modified, renamed, copied,
    # changed or unchanged.
    status: str
    # Where the base holds a renamed or copied file; None for any other status, or
    # when the provider gave none.
    previous_path: str | None
    # The file's hunks, or None when the comparison carried none.
    patch: str | None
    additions: int | None
    deletions: int | None
    # The head side's blob id, as given; checked before it is compared.
    blob: str | None


class BaseRecord(NamedTuple):
    """The base revision's record of one name in its directory, bounded."""

    name: str
    # "file", "dir", "symlink", "submodule", or "" for an undeclared or unknown kind.
    kind: str
    # The declared size, or None for no usable size.
    size: int | None
    # The blob id when it is an exact object id, "" otherwise.
    blob: str


class Listing(NamedTuple):
    """A directory of the base revision, reduced to the names the change needs."""

    # The records kept, or None when the provider answered not-found.
    records: tuple[BaseRecord, ...] | None
    # How many records the provider sent, which the cap notice depends on.
    total: int
    # The answer was not a listing at all: the collection never got to look.
    malformed: bool


class Contents(NamedTuple):
    """One file's base-revision bytes, or why they are not usable."""

    data: bytes | None
    # When ``data`` is None: "not-a-plain-file", or "provider-error: <detail>".
    reason: str
    # False when the provider answered not-found for a path its listing holds.
    found: bool


class Comparison(NamedTuple):
    """A comparison as the collection acts on it, translated by the adapter."""

    # The entries the collection can act on.
    files: list[ChangedFile]
    # How many entries the provider sent, before any was dropped.
    delivered: int
    # The merge base's exact commit, or "" when the comparison carried none.
    merge_base: str
    # Notices about the comparison itself, for the manifest.
    notices: list[str]
    # Manifest lines for paths the comparison named but described too badly to use.
    refused: list[str]
    # Whether the comparison listed its files: unparseable, not an object, without a
    # file list, or listing only unusable entries is not a listing.
    listed: bool


class SourceFailure(RuntimeError):
    """The base source could not answer for one path.

    ``kind`` is "deadline" when the collection's budget ran out before a request,
    "redirect" for a refused redirect, and "provider" for any other failure.
    """

    def __init__(self, message: str, *, kind: str = "provider") -> None:
        super().__init__(message)
        self.kind = kind


class BaseSource(Protocol):
    """The base-source role: a directory's listing and a file's bytes, at one revision.

    Each method raises ``SourceFailure`` when the provider could not answer, and
    ``ValueError`` for a path it will not request.
    """

    # The most records a listing can hold; one that reached it may be capped.
    listing_cap: int

    def listing(self, directory: str, needed: set[str], deadline: float) -> Listing:
        """Return ``directory``'s records for ``needed`` names, before ``deadline``."""
        raise NotImplementedError

    def contents(self, path: str, deadline: float) -> Contents:
        """Return ``path``'s bytes at the base revision, before ``deadline``."""
        raise NotImplementedError


# ---------------------------------------------------------------------------------
# Names, quoting and exact writes


def safe_relative_path(name: str) -> pathlib.PurePosixPath:
    """Return ``name`` as a relative path, refusing anything that could escape."""
    if not name or name.startswith("/") or name.endswith("/"):
        raise ValueError(f"refusing a non-relative path: {name!r}")
    if "\\" in name or "\x00" in name:
        raise ValueError(f"refusing a path with a backslash or NUL: {name!r}")
    components = name.split("/")
    if any(component in _REFUSED_COMPONENTS for component in components):
        raise ValueError(f"refusing a degenerate or traversing path: {name!r}")
    return pathlib.PurePosixPath(*components)


_C_ESCAPES = {
    0x07: "\\a",
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0B: "\\v",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}

# Git's own rule is not sufficient here. `git -c core.quotePath=false` prints U+0085,
# U+2028 and U+2029 raw, because Git orients on bytes -- but these artefacts are read by
# a Unicode-aware reader, and Python's ``str.splitlines`` treats all three as line
# breaks. A name carrying one would recreate exactly the forged-record problem that
# escaping the C0 controls closed.
_UNICODE_BREAKS = frozenset("\u0085\u2028\u2029")


def _must_escape(ch: str) -> bool:
    """Return whether ``ch`` could end a line, or fail to encode, in these artefacts.

    A lone surrogate is valid JSON (`"\\ud800"`) and no UTF-8 writer can encode it: the
    first summary write raised before the per-file isolation existed, so one such name
    cost the whole collection.
    """
    code = ord(ch)
    return (
        code < 0x20 or code == 0x7F or ch in _UNICODE_BREAKS or 0xD800 <= code <= 0xDFFF
    )


def quote_path(name: str) -> str:
    """Return ``name`` the way ``git -c core.quotePath=false`` would print it.

    Git permits a newline in a pathname and the comparison carries it through, but
    every artefact this writes is read line by line. A name interpolated verbatim could
    therefore add a `+++ b/other.py` header, a diff line or an extra summary record, and
    a reviewer with no git and no candidate tree has nothing to check that against.
    Quoting is used rather than refusal because such a name is a legal path: dropping
    the file would hide a real change.

    Control characters, a double quote and a backslash are C-quoted; UTF-8 is left
    alone, exactly as Git does with `core.quotePath=false`. A legitimate international
    filename is not a line-injection risk, and quoting it would only make the artefacts
    harder to read.
    """
    if not any(_must_escape(ch) or ch in '"\\' for ch in name):
        return name
    out = ['"']
    for ch in name:
        code = ord(ch)
        if code in _C_ESCAPES:
            out.append(_C_ESCAPES[code])
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\{code:03o}")
        elif _must_escape(ch):
            # Octal of the UTF-8 bytes, which is how `git -c core.quotePath=true`
            # renders a non-ASCII byte -- so the escape stays in Git's own vocabulary
            # even though Git itself does not escape these.
            # A surrogate has no UTF-8 bytes; its surrogatepass bytes stand in for it.
            out.extend(f"\\{byte:03o}" for byte in ch.encode("utf-8", "surrogatepass"))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _wrap_point(record: bytes, room: int) -> int:
    """Return how many bytes of an oversized record fit on one line without splitting."""
    end = room
    while end > 0 and (record[end] & 0xC0) == 0x80:
        end -= 1
    return end or room


def wrap_records(data: bytes, line_cap: int) -> tuple[bytes, int, int]:
    """Hard-wrap records longer than the reader's ``line_cap``.

    The reader truncates a physical line past its cap and offsets into a file by line,
    so a single very long record would leave its tail unreachable even though the bytes
    are present. Only newlines are inserted, each continuation marked with
    ``CONTINUATION``: no byte is removed or reordered.

    Returns the wrapped text, how many records were wrapped, and how many continuation
    lines were introduced. Each continuation costs exactly two bytes -- one newline and
    one marker -- which is what lets a test assert that nothing else changed.
    """
    out = bytearray()
    wrapped = 0
    continuations = 0
    for record in data.split(b"\n"):
        if len(record) <= line_cap:
            out += record + b"\n"
            continue
        wrapped += 1
        offset = 0
        first = True
        while offset < len(record):
            room = line_cap if first else line_cap - len(CONTINUATION)
            remaining = len(record) - offset
            take = (
                remaining if remaining <= room else _wrap_point(record[offset:], room)
            )
            if not first:
                out += CONTINUATION
                continuations += 1
            out += record[offset : offset + take] + b"\n"
            offset += take
            first = False
    # One trailing newline too many, always: every path through the loop above ends by
    # appending one, and `split()` yields at least one record. Keeping the test rather
    # than deleting outright is deliberate: it is the actual precondition, so if a later
    # change stops the loop terminating records this removes nothing instead of
    # silently eating a byte of content.
    if out.endswith(b"\n"):
        del out[-1:]
    return bytes(out), wrapped, continuations


def write_exact(
    destination: pathlib.Path,
    content: bytes,
    writer: Any = None,
    *,
    staging: pathlib.Path,
) -> None:
    """Write ``content`` so that a failure leaves nothing behind.

    The manifest names a file it could not obtain, and the prompt calls ``base/`` the
    exact pre-change revision. A half-written file satisfies neither: it would sit there
    looking exact while the manifest said the file was unavailable. The bytes go to a
    temporary name and are renamed into place only once they are all there; anything
    left over is removed on the way out.

    The temporary name lives in ``staging``, outside ``base/``. It used to sit beside
    its destination, and the sweep that removes an interrupted write after a hard stop
    then had to recognise staging files by name inside ``base/``. No name can be told
    apart from a real one -- any filename is a legal Git path, and a rename lets the
    candidate choose the destination name -- so a real file in the staging shape was
    deleted while ``Written:`` still counted it. A separate directory needs no
    recognising: the step removes it whole. Required, so no caller can stage beside a
    real file by omission.
    """
    staging.mkdir(parents=True, exist_ok=True)
    # A unique name, because `<name>.partial` is itself a legal pathname: a change
    # touching both `x.partial` and `x` would have the second write overwrite the first
    # file and then rename it away, leaving a silent gap that the manifest never records
    # and `Written:` still counts. A short digest of the name, not the name itself:
    # copying a basename that approaches NAME_MAX and then adding punctuation,
    # randomness and ".partial" overflows it, and mkstemp raises ENAMETOOLONG -- losing
    # a file the collection could otherwise deliver, to the staging mechanism.
    stem = hashlib.sha256(destination.name.encode()).hexdigest()[:16]
    handle, staged = tempfile.mkstemp(
        dir=staging, prefix=f".{stem}.", suffix=".partial"
    )
    os.close(handle)
    scratch = pathlib.Path(staged)
    try:
        if writer is None:
            scratch.write_bytes(content)
        else:
            writer(scratch, content)
        scratch.replace(destination)
    finally:
        scratch.unlink(missing_ok=True)


def write_artefact(
    context: pathlib.Path,
    name: str,
    text: str,
    *,
    line_cap: int,
    encoding: str = "utf-8",
) -> None:
    """Write a top-level artefact whole or not at all, through ``write_exact``.

    After a failure the step creates only the artefacts that are *missing*, so an
    artefact left half-written was kept as if it were whole. Rendered first and renamed
    into place complete, an interrupted artefact is absent instead, which the step
    reports for what it is. Every record here begins with a status word, so a line
    beginning with the continuation marker can only continue the one above.
    """
    # Total over provider text: a lone surrogate in a patch is written as its escape
    # rather than raising before the manifest exists. Names are already quoted.
    data = text.encode(encoding, "backslashreplace")
    data, _, _ = wrap_records(data, line_cap)
    write_exact(context / name, data, staging=context / STAGING)


def write_streamed(
    context: pathlib.Path, name: str, render: Callable[[Any], None]
) -> None:
    """Write a top-level artefact whole or not at all, rendered into its staging file.

    For an artefact as large as the change itself. Rendering it into memory first held
    the fallback diff three times over -- the resident patches, the rendered string and
    its encoding -- and a large change could exhaust the runner before `base.manifest`
    was written.
    """

    def stream(path: pathlib.Path, _content: bytes) -> None:
        """Render the artefact into the staging file ``write_exact`` hands over."""
        with path.open("w", encoding="utf-8", errors="backslashreplace") as handle:
            render(handle)

    write_exact(context / name, b"", stream, staging=context / STAGING)


def blob_id(content: bytes) -> str:
    """Return Git's object id for ``content`` as a blob.

    Git defines it as the SHA-1 of ``blob <length>\\0`` followed by the bytes, which was
    confirmed against ``git hash-object``. SHA-1 appears here because that is what the
    identity being checked *is*, not as a security primitive: it is compared against a
    value the provider supplies, never used to authenticate anything, which
    `usedforsecurity=False` states to the runtime as well as to a reader.
    """
    return hashlib.sha1(  # nosec B324  # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
        b"blob %d\0" % len(content) + content,
        usedforsecurity=False,
    ).hexdigest()


# ---------------------------------------------------------------------------------
# The summaries and the fallback diff


def _count(value: int | None) -> str:
    """Return a line count as the provider gave it, or "?" when it gave none.

    Rendering an absent or mistyped count as 0 asserted a number the provider never
    established.
    """
    return "?" if value is None else str(value)


def _short_blob(value: str | None) -> str:
    """Return a blob id's first nine characters, or "?" when it is not a blob id.

    `no-patch.txt` is read line by line, and the provider's blob id was printed as
    given, so one carrying a newline added a record of its own.
    """
    return value[:9] if is_object_id(value) else "?"


def _mapped(changed: ChangedFile) -> bool:
    """Return whether ``changed`` came from another path the base holds."""
    return changed.status in ("renamed", "copied") and bool(changed.previous_path)


def _named(changed: ChangedFile) -> str:
    """Return ``changed``'s quoted name, with its source when it was moved or copied.

    A rename's old path is part of what changed. Emitting only the new name leaves the
    reviewer unable to say where the file came from, which matters most in the swap and
    overwrite cases where another file already occupied the new path.
    """
    if _mapped(changed):
        return f"{quote_path(str(changed.previous_path))} -> {quote_path(changed.path)}"
    return quote_path(changed.path)


def base_path_of(changed: ChangedFile) -> str:
    """Return the path the base revision holds this entry under."""
    if changed.status in ("renamed", "copied"):
        # A copy carries its source exactly as a rename does, and the source is the one
        # thing a copy is about: without it the fallback claims the destination existed
        # on the base side and no summary says where the content came from.
        if not changed.previous_path:
            raise ValueError(f"a {changed.status} entry carries no previous path")
        return changed.previous_path
    return changed.path


def old_side(changed: ChangedFile) -> str:
    """Return the diff header's left side, or /dev/null when there was no left side.

    Unified diff names the nonexistent side `/dev/null`. Writing `--- a/<name>` for an
    added file tells a reviewer with no tree and no base that the file existed before
    the change, and on the assembled fallback that header is the only description of it
    the reviewer gets.
    """
    if changed.status == "added":
        return "/dev/null"
    try:
        return quote_path("a/" + base_path_of(changed))
    except ValueError:
        # A renamed or copied entry with no previous path. `/dev/null` would assert the
        # candidate added it, and inventing a path would assert a base-side name the
        # comparison never gave -- so the header says it is unresolved, which is a token
        # no pathname can be.
        return "(unresolved: the comparison gave no previous path)"


def new_side(changed: ChangedFile) -> str:
    """Return the diff header's right side, or /dev/null for a removal."""
    if changed.status == "removed":
        return "/dev/null"
    return quote_path("b/" + changed.path)


def write_assembled(handle: Any, files: list[ChangedFile]) -> None:
    """Write the per-file fallback diff one entry at a time.

    Every patch string used to be concatenated into a single value before being written,
    which held the whole fallback diff a second time. Writing per entry removes that
    copy.
    """
    for changed in files:
        handle.write(f"--- {old_side(changed)}\n+++ {new_side(changed)}\n")
        if changed.patch is not None:
            handle.write(f"{changed.patch}\n")
        else:
            # A metadata-only change has no hunks, and dropping it here would have
            # removed a reviewable change from the fallback entirely.
            handle.write(f"[no hunks: {changed.status}; see no-patch.txt]\n")


_NO_PATCH_HEADER = (
    "Changed files for which the comparison carried no hunks. This means\n"
    "either a binary or oversized blob, whose bytes are in neither the\n"
    "diff nor the checkout, or a metadata-only change such as a mode bit,\n"
    "an empty file or a pure rename. The status below does NOT distinguish\n"
    "them: a binary content change and a mode-only change both arrive as\n"
    "'modified' with no hunks. A real unified diff does, by its mode lines\n"
    "and its binary notice, and base.manifest classifies by blob identity.\n"
    "If patches-source is present the diff was assembled per file and\n"
    "carries neither, so report such an entry as not examined.\n"
    "\n"
)


def write_summaries(
    context: pathlib.Path,
    files: list[ChangedFile],
    delivered: int,
    *,
    file_cap: int,
    line_cap: int,
) -> None:
    """Write diff.stat and no-patch.txt from the comparison's usable entries.

    ``delivered`` is how many entries the provider actually sent, which the cap notice
    depends on and a reduced list can no longer report. Counting the usable entries
    dropped the notice whenever one of a capped list was unusable, and a truncated
    change read as complete.
    """
    lines = [
        f"{changed.status} +{_count(changed.additions)} "
        f"-{_count(changed.deletions)} {_named(changed)}"
        for changed in files
    ]
    if delivered >= file_cap:
        # The provider caps this list and does not paginate it, so a list that reached
        # the cap must not be allowed to read as the whole change. Counted from what
        # the provider *sent*, before unusable entries are dropped. What is established
        # is that the list *reached* the maximum -- not that anything was dropped: a
        # change of exactly that many files is complete and indistinguishable from a
        # truncated one. The condition observed is stated, not the conclusion it only
        # permits.
        lines.append(
            f"[the changed-file list reached the provider's maximum of {file_cap} "
            "and is not paginated, so this summary may be incomplete; nothing here "
            "says whether a further file exists]"
        )
    write_artefact(
        context, "diff.stat", "".join(f"{line}\n" for line in lines), line_cap=line_cap
    )
    # A missing per-file patch is a neutral fact, not a file type. It happens for a
    # binary or oversized blob, and equally for a metadata-only change -- a mode bit, an
    # empty file, a rename with no textual edit -- which is perfectly reviewable.
    without_patch = [changed for changed in files if changed.patch is None]
    write_artefact(
        context,
        "no-patch.txt",
        _NO_PATCH_HEADER
        + "".join(
            f"{changed.status} {_short_blob(changed.blob)} {_named(changed)}\n"
            for changed in without_patch
        ),
        line_cap=line_cap,
    )


def write_commits(context: pathlib.Path, *, line_cap: int) -> None:
    """Render commits.log from the base64-carried subjects the step collected.

    A commit subject is candidate-controlled text and this artefact is read line by
    line, so it is escaped exactly as a pathname is. Splitting a message on "\\n" leaves
    a Unicode line separator intact, and the subject could then add a standalone fake
    commit, or a fake provider-cap notice, to a file the reviewer trusts.
    """
    source = context / "commits.b64"
    if not source.exists():
        return
    records = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sha, _, encoded = line.partition(" ")
        try:
            raw = base64.b64decode(encoded, validate=True) if encoded else b""
        except ValueError:
            # `binascii.Error` is a `ValueError`. One unreadable subject is that
            # commit's gap, not the step's; saying so keeps the record count honest,
            # which is what the cap notice counts.
            records.append(f"{sha} [subject unavailable]\n")
            continue
        records.append(f"{sha} {quote_path(raw.decode('utf-8', 'replace'))}\n")
    write_artefact(context, "commits.log", "".join(records), line_cap=line_cap)
    source.unlink()


# ---------------------------------------------------------------------------------
# Classifying a change without hunks


def hunkless_label(changed: ChangedFile, record: BaseRecord, name: str) -> str:
    """Classify a change the comparison gave no hunks for.

    ``status`` cannot distinguish a mode-only change from a binary content change:
    both arrive as ``modified`` with no hunks. Blob identity can -- except for a
    removal, where the comparison's blob *is* the deleted base-side blob and so always
    equals the listing's. Comparing them there would label a deleted file
    ``metadata-only`` and have the reviewer treat a deletion as reviewable metadata. A
    copy is the same trap from the other side: it is fetched under its previous path,
    so an exact copy makes the ids equal at a path that held nothing before.
    """
    if changed.status == "removed":
        return f"removed-without-hunks {quote_path(name)}"
    if record.kind not in _BLOB_KINDS:
        # Compared anyway, an equal blob on a record of no blob kind read as
        # metadata-only while the fetch refused the same record.
        return f"unclassified-without-blob-identity {quote_path(name)}"
    base_blob = record.blob
    head_blob = changed.blob
    if (
        changed.status == "copied"
        and is_object_id(base_blob)
        and head_blob == base_blob
    ):
        # An *exact* copy. It is fetched under its previous path, so the two blob ids are
        # equal -- and metadata-only, which the prompt defines as "the content is the
        # same", would be said about a path that held no content at all before. A whole
        # file appeared. A rename is not this case: the file moved rather than
        # multiplied, and the manifest lists that mapping separately. An *edited* copy
        # falls through and is labelled `content-changed-without-hunks`, which the
        # prompt already requires the reviewer to report as not examined.
        return f"copied-without-hunks {quote_path(name)}"
    if not (is_object_id(base_blob) and is_object_id(head_blob)):
        # Equality of two *malformed* values is not evidence of identical content.
        return f"unclassified-without-blob-identity {quote_path(name)}"
    if base_blob == head_blob:
        return f"metadata-only {quote_path(name)}"
    return f"content-changed-without-hunks {quote_path(name)}"


# ---------------------------------------------------------------------------------
# The collection


class _Collection:
    """What one collection carries from one changed file to the next."""

    def __init__(
        self,
        context: pathlib.Path,
        source: BaseSource,
        merge_base: str,
        budget: int,
    ) -> None:
        self.context = context
        self.source = source
        self.merge_base = merge_base
        self.remaining = budget
        self.deadline = 0.0
        # Which names each directory is consulted for, known up front because the
        # comparison names every changed path. Retention is then bounded by the number
        # of changed files rather than by the size of the directories they live in.
        self.needed_names: dict[str, set[str]] = {}
        self.listings: dict[str, Listing] = {}
        self.unavailable: list[str] = []
        # Notices about the collection rather than about a file. They belong in the
        # manifest and not in `Unavailable:`, which counts paths.
        self.classified: list[str] = []
        self.written = 0


def _parent(path: str) -> str:
    """Return ``path``'s directory, "" for the repository's root."""
    parent = str(pathlib.PurePosixPath(path).parent)
    return "" if parent == "." else parent


def _without_merge_base(state: _Collection, ordered: list[ChangedFile]) -> None:
    """Name every changed path when the comparison carried no exact merge base."""
    for changed in ordered:
        quoted = quote_path(changed.path)
        hunkless = changed.patch is None
        if changed.status == "added":
            # Settled by the comparison alone: an added file has no base-side path to
            # fetch, needs no revision and would have made no request.
            state.unavailable.append(f"added-by-candidate {quoted}")
            if hunkless:
                state.classified.append(f"added-without-hunks {quoted}")
        else:
            # Named individually: `base.manifest` promises provenance per path.
            state.unavailable.append(
                f"provider-error {quoted}: no exact merge base revision in the "
                "comparison"
            )
            if hunkless:
                state.classified.append(f"unclassified-no-base-record {quoted}")


def _needed_names(ordered: list[ChangedFile]) -> dict[str, set[str]]:
    """Return, per base directory, the names the changed files need from it."""
    needed: dict[str, set[str]] = {}
    for changed in ordered:
        if changed.status == "added":
            continue
        try:
            source = base_path_of(changed)
            safe_relative_path(source)
        except ValueError:
            # Left to the per-file handler, which records it as `unsupported-path` and
            # costs that one file: raising here would cost the whole review.
            continue
        needed.setdefault(_parent(source), set()).add(
            pathlib.PurePosixPath(source).name
        )
    return needed


def _base_record(state: _Collection, source: str) -> BaseRecord | None:
    """Return the parent listing's record for ``source``, or name the gap and None.

    The parent listing declares the entry's real type. Asking for the contents alone
    cannot: a provider can answer a symlink to a regular file with the target's bytes
    under an ordinary file type, so accepting that response would write unrelated
    content and call it the exact pre-change state.
    """
    directory = _parent(source)
    if directory not in state.listings:
        state.listings[directory] = state.source.listing(
            directory, state.needed_names.get(directory, set()), state.deadline
        )
    listing = state.listings[directory]
    name = pathlib.PurePosixPath(source).name
    records = [record for record in listing.records or () if record.name == name]
    if len(records) > 1:
        # A listing naming a path twice contradicts itself. Taking the first record let
        # record order choose the type and blob id.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: the directory listing holds "
            f"{len(records)} records for it"
        )
        return None
    if records:
        return records[0]
    if listing.malformed:
        # The collection never got to look: recording it as absent attributed a
        # provider failure to the repository.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: directory listing was not an array"
        )
    elif listing.records is not None and listing.total >= state.source.listing_cap:
        # The listing reached the provider's maximum, so the name may lie beyond it --
        # or the listing may be complete and contradict the comparison. Neither
        # "absent" nor "truncated" is established; the label says only what was seen.
        state.unavailable.append(f"listing-at-cap {quote_path(source)}")
    else:
        # Not absence either. The comparison has already placed this non-added source
        # at this same merge base, so a directory not-found, or a listing that does not
        # hold the name, contradicts the comparison.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: "
            "the comparison places it at the merge base "
            "but the listing does not"
        )
    return None


def _content_gap(
    state: _Collection, source: str, record: BaseRecord, content: bytes
) -> str | None:
    """Return the manifest line refusing ``content`` for ``source``, or None.

    A truncated or corrupted payload that still decodes cleanly would be written as the
    exact pre-change file with no gap recorded -- and "exact" is the whole claim base/
    makes. The listing already carries Git's blob id, so the bytes are checked against
    it rather than assumed.
    """
    if not is_object_id(record.blob):
        # Without the listing's blob id there is nothing to check the bytes against,
        # and base/ promises exactness.
        return f"blob-unverifiable {quote_path(source)}"
    if blob_id(content) != record.blob:
        return f"blob-mismatch {quote_path(source)}"
    if len(content) > state.remaining:
        # Backstop for a listing that reported no size.
        return f"over-budget {quote_path(source)}"
    return None


def _write_failure(error: OSError, name: str) -> str:
    """Return the manifest line for a write into ``base/`` that raised ``error``."""
    if error.errno in _COLLISION_ERRNOS:
        # Replacing a file with a directory is an ordinary change: a change can remove
        # `cfg` and rename something to `cfg/x.py`. Every entry is written under its
        # post-change name, so one of the two writes meets the other as the wrong type.
        return f"path-collision {quote_path(name)}"
    # Anything else -- a full disk, an I/O error -- says nothing about the repository.
    cause = errno.errorcode.get(error.errno or 0, type(error).__name__)
    return f"write-failed {quote_path(name)}: {cause}"


def _fetch_and_write(
    state: _Collection, name: str, source: str, record: BaseRecord
) -> None:
    """Fetch the listed file's pre-change bytes, verify them, and write them."""
    if record.kind != "file":
        # Only a recognised non-file kind is a fact about the repository. A missing or
        # unknown kind says only that the listing was malformed.
        if record.kind in _NOT_A_FILE:
            state.unavailable.append(f"not-a-plain-file {quote_path(source)}")
        else:
            state.unavailable.append(
                f"provider-error {quote_path(source)}: its directory listing "
                "declared no recognised type"
            )
        return
    # Checked against the size the listing reports, so a file the budget will reject
    # costs no request at all: a large change full of binaries otherwise issued an
    # avoidable request per file, and a rate limit there would fail the step.
    if record.size is not None and record.size > state.remaining:
        state.unavailable.append(f"over-budget {quote_path(source)}")
        return
    contents = state.source.contents(source, state.deadline)
    if not contents.found:
        # Not absence. The listing at this same merge base already said the file is
        # there, and the merge base is immutable -- so a not-found for the same path at
        # the same revision is the provider contradicting itself.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: "
            "listed at the merge base but its contents were not found"
        )
        return
    if contents.data is None:
        # The reason travels from where it is known. `not-a-plain-file` is a statement
        # about the repository, recorded only where the answer supports one.
        if contents.reason.startswith("provider-error"):
            detail = contents.reason.split(":", 1)[1].strip()
            state.unavailable.append(f"provider-error {quote_path(source)}: {detail}")
        else:
            state.unavailable.append(f"{contents.reason} {quote_path(source)}")
        return
    gap = _content_gap(state, source, record, contents.data)
    if gap is not None:
        state.unavailable.append(gap)
        return
    destination = state.context / "base" / safe_relative_path(name)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_exact(destination, contents.data, staging=state.context / STAGING)
    except OSError as error:
        # Losing one file's pre-change bytes is a gap the manifest records; letting the
        # error escape would fail the whole step and leave no review at all.
        state.unavailable.append(_write_failure(error, name))
        return
    state.remaining -= len(contents.data)
    state.written += 1


def _failure_line(failure: Exception, name: str) -> str:
    """Return the manifest line for a per-file failure, most specific cause first."""
    if isinstance(failure, SourceFailure):
        if failure.kind == "deadline":
            return f"deadline-reached {quote_path(name)}"
        if failure.kind == "redirect":
            return f"unsafe-redirect {quote_path(name)}: {failure}"
        # The provider could not answer for this path, which is not the same as the
        # path being one this collection will not write.
        return f"provider-error {quote_path(name)}: {failure}"
    # Every refusal raised in here says "this path cannot be handled": a name this
    # collection will not write, or a record that contradicts its own contract. It
    # costs that one file rather than the whole review.
    return f"unsupported-path {quote_path(name)}: {failure}"


def _visit(state: _Collection, changed: ChangedFile) -> None:
    """Collect one changed file's pre-change bytes, or name why they are absent."""
    name = changed.path
    hunkless = changed.patch is None
    classified_here = False
    if changed.status == "added":
        # Settled by the comparison alone, so before the deadline: an added file has no
        # base side and costs no request.
        state.unavailable.append(f"added-by-candidate {quote_path(name)}")
        if hunkless:
            state.classified.append(f"added-without-hunks {quote_path(name)}")
        return
    if time.monotonic() >= state.deadline:
        if hunkless:
            # A no-hunk change gets a verdict whatever else happens: the reviewer is sent
            # to base.manifest for it, and these entries are ordered last, so on a large
            # change they are the first the deadline reaches.
            state.classified.append(f"unclassified-no-base-record {quote_path(name)}")
        # Each file costs a listing and a contents request, each retried: the worst case
        # ran past the job's own timeout, and a job the runner kills produces no review.
        state.unavailable.append(f"deadline-reached {quote_path(name)}")
        return
    try:
        source = base_path_of(changed)
        # Validated as given, before any lookup: `a//x` normalised to the real entry
        # `a/x`, which classified the path from that record before the fetch refused it.
        safe_relative_path(source)
        record = _base_record(state, source)
        if record is None:
            if hunkless:
                state.classified.append(
                    f"unclassified-no-base-record {quote_path(name)}"
                )
            return
        if hunkless:
            # Classified before the contents fetch and whether or not the bytes are
            # written, so a budget rejection or a decode failure cannot leave the
            # reviewer without a verdict on whether content changed.
            state.classified.append(hunkless_label(changed, record, name))
            classified_here = True
        _fetch_and_write(state, name, source, record)
    except (SourceFailure, ValueError) as failure:
        state.unavailable.append(_failure_line(failure, name))
        if hunkless and not classified_here:
            state.classified.append(f"unclassified-no-base-record {quote_path(name)}")


_MANIFEST_HEAD = (
    "Every path the provider listed and this collection could not fetch is named",
    "below with its reason. A renamed or",
    "copied file is fetched under its previous path and written under its new one,",
    "so the mapping is listed here: the bytes under a new name came from the old.",
    "A record too long for one readable line continues on lines that begin with",
    "'>', here and in diff.stat, no-patch.txt and commits.log.",
)
_MANIFEST_CLASSES = (
    "",
    "A change the comparison gave no hunks for is classified below by blob",
    "identity, because its status cannot distinguish the cases: identical blobs",
    "mean a metadata-only change, while differing blobs mean content changed that",
    "no artefact here can show. metadata-only says only that the content is the",
    "same; *which* metadata changed -- 100644 -> 100755, or another transition --",
    "is carried by the unified diff's mode lines and by nothing else here. An",
    "entry whose blob ids are missing or malformed is listed as",
    "unclassified-without-blob-identity: no classification was established for",
    "it, and equal-but-malformed ids are not read as identical content. If",
    "patches-source is present the diff was assembled per file and those lines are",
    "absent, so a metadata-only entry is then not examined either.",
    "",
)


def _manifest_lines(
    state: _Collection, comparison: Comparison, file_cap: int
) -> list[str]:
    """Return the lines of ``base.manifest`` for a finished collection."""
    mapped = [changed for changed in comparison.files if _mapped(changed)]
    renames = [f"{changed.status} {_named(changed)}" for changed in mapped]
    # Counted apart: reporting the list's length as `Renamed:` told the reviewer a file
    # had moved when it had been duplicated and the original is still there.
    copied = sum(1 for changed in mapped if changed.status == "copied")
    merge_base = state.merge_base if is_object_id(state.merge_base) else "unknown"
    capped = (
        [
            f"The changed-file list reached the provider's maximum of {file_cap}"
            " and is not",
            "paginated, so this may not be the whole change: any path beyond the",
            "maximum would be absent from this manifest and not examined, and",
            "nothing here says whether one exists.",
        ]
        # The counts and the inventory cover the paths the provider listed, and a
        # capped list omits the rest entirely: the qualification has to be here too,
        # since the prompt sends the reviewer here for provenance.
        if comparison.delivered >= file_cap
        else []
    )
    return [
        # Not of every changed file: an added path has none, and an unavailable one is
        # named below instead.
        "Exact pre-change bytes of the changed files this collection could fetch,",
        f"taken at the merge base ({merge_base}).",
        *_MANIFEST_HEAD,
        f"Written: {state.written}. Unavailable: {len(state.unavailable)}. "
        f"Renamed: {len(renames) - copied}. Copied: {copied}.",
        *capped,
        *_MANIFEST_CLASSES,
        *state.classified,
        *renames,
        *state.unavailable,
        *comparison.notices,
    ]


def collect(
    context: pathlib.Path,
    comparison: Comparison,
    source: BaseSource,
    *,
    budget: int,
    file_cap: int,
    deadline_seconds: float,
    line_cap: int,
) -> tuple[int, list[str], bool]:
    """Write the context's summaries, fallback diff and base revision.

    Returns the number of files written, one manifest line per file that is not, and
    whether the comparison listed its files. ``file_cap`` is the provider's cap on a
    comparison's files; ``line_cap`` is the reader's line budget.
    """
    write_commits(context, line_cap=line_cap)
    write_summaries(
        context,
        comparison.files,
        comparison.delivered,
        file_cap=file_cap,
        line_cap=line_cap,
    )
    # Per-file patches, so a provider that refuses the whole diff still leaves the
    # changed content reachable.
    write_streamed(
        context,
        "assembled.diff",
        lambda handle: write_assembled(handle, comparison.files),
    )
    (context / "base").mkdir(exist_ok=True)
    state = _Collection(context, source, comparison.merge_base, budget)
    state.unavailable.extend(comparison.refused)
    notices = list(comparison.notices)
    # Files with hunks are fetched first so that a large binary cannot consume the
    # budget ahead of a textual change. Entries without hunks are not skipped: a mode
    # change or a pure rename of a text file has pre-change bytes, and those bytes are
    # exactly what the reviewer is told to read from base/.
    ordered = sorted(comparison.files, key=lambda changed: changed.patch is None)
    if not is_object_id(comparison.merge_base):
        # Checked once, before any request: without the revision there is nothing to ask
        # for, so no request is made rather than one refusal per file.
        notices.append(
            "provider-error comparison.json: the comparison carried no exact merge "
            f"base revision ({comparison.merge_base or 'absent'!r}), so no pre-change "
            "bytes could be fetched for any path"
        )
        _without_merge_base(state, ordered)
        ordered = []
    state.needed_names = _needed_names(ordered)
    state.deadline = time.monotonic() + deadline_seconds
    for changed in ordered:
        _visit(state, changed)
    lines = _manifest_lines(state, comparison._replace(notices=notices), file_cap)
    write_artefact(
        context, MANIFEST, "".join(f"{line}\n" for line in lines), line_cap=line_cap
    )
    # Every staged write was renamed or removed, so the staging area is empty; it is not
    # part of the context. A hard stop that leaves it behind is the step's to sweep.
    try:
        (context / STAGING).rmdir()
    except OSError:
        pass
    return state.written, state.unavailable, comparison.listed
