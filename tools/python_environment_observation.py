"""The diagnostic producers' interpreter environment, as that interpreter resolves it
under -I (#389 F3 S2-C).

tools.quality_evidence runs this file by its own path beside the collector, as
`python -I <this file> <caps> <format>`, through its bounded launcher and under the
inventory's deadline (Router 6351766731 R1). Under -I neither the working directory nor
this file's directory is on the import path, so it imports the standard library only.

It prints one JSON object: the interpreter, its import roots and their top-level
entries, any archive on the path with a digest of its bytes, and each `*.dist-info`
with a digest of the RECORD bytes read. That is metadata, not installed content: a
RECORD digest attests that file's bytes, not the files it lists. A cap that stops it,
or a root, RECORD or archive it cannot read, makes the observation incomplete, and so no
identity (Sourcery and cubic on #452). Each cap is enforced while it enumerates or
reads, before anything is sorted, and a file read counts against both file caps.

Each RECORD's hashed rows are also checked against the files they name, from the same
RECORD bytes its digest names (#389 F3-S2-RECORD-GUARD, Router 6361147179). A computed
sha256 that disagrees is `record_mismatch`; an unsupported algorithm, a malformed row, an
ambiguous path or a listed file that cannot be read stops the observation too. A valid
row naming a path outside its import root, a console script or data file, is outside
the check: classified lexically, never accessed and never verified (E1, Router #389
6361519666). A RECORD that agrees is not installed-content identity: rows without a hash,
rows outside the root, files no RECORD lists and import resolution stay unobserved.
"""

import base64
import binascii
import codecs
import csv
import hashlib
import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import PurePosixPath

# A safe open needs both flags: without either the observation stops as unreadable,
# never following a link or waiting for a writer (Codex and cubic on #452), as the
# existing bounded reader refuses without O_NOFOLLOW (adoption_check._read_regular_bounded).
_SAFE_OPEN = (
    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_NONBLOCK")
    else None
)
# A *.dist-info directory is opened the same way, and its RECORD relative to it, so that
# no component of the RECORD's path is followed (cubic on #452).
_DIRECTORY_OPEN = (
    _SAFE_OPEN | os.O_DIRECTORY
    if _SAFE_OPEN is not None
    and hasattr(os, "O_DIRECTORY")
    and os.open in os.supports_dir_fd
    else None
)


# The longest RECORD size admitted: the digits of 2**64, more than any file can hold.
# A size is bounded before anything reads its file and is never converted, so no size
# reaches Python's integer-conversion limit (owner 6364237541; Revix on #453).
_SIZE_DIGITS = len(str(2**64))


def _record_lines(chunks: list[bytes]) -> Iterator[str]:
    """A RECORD's text, line by line as `io.StringIO` gives it, decoded strictly from
    the bytes its digest names, emptying `chunks` as it goes: the bytes, the text and
    the rows are never all held at once, so a RECORD at the per-file cap costs about
    its own size (Router #389 6364506650). A line longer than any row the CSV reader
    accepts is refused before it is held."""
    longest = 6 * csv.field_size_limit() + 16
    decoder = codecs.getincrementaldecoder("utf-8")()
    pending: list[str] = []
    held = 0
    chunks.reverse()
    while chunks:
        text = decoder.decode(chunks.pop())
        start = 0
        while (end := text.find("\n", start)) != -1:
            yield "".join(pending) + text[start : end + 1]
            pending.clear()
            held = 0
            start = end + 1
        held += len(text) - start
        if held > longest:
            raise csv.Error("a RECORD line longer than any row")
        pending.append(text[start:])
    tail = "".join(pending) + decoder.decode(b"", final=True)
    if tail:
        yield tail


def _sha256_claim(encoded: str) -> str | None:
    """A RECORD's sha256 claim, urlsafe base64 without padding, as hex; None unless it
    is exactly the canonical encoding of a 32-byte digest: the standard alphabet,
    padding and unused bits set are refused (Sourcery and Codex on #453)."""
    try:
        raw = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4), b"-_", validate=True
        )
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).rstrip(b"=") != encoded.encode():
        return None
    return raw.hex()


def _within_any(bases: set[str], target: str) -> bool:
    """Whether `target` is one of `bases` or lies under one, component by component and
    without the filesystem: the standard-library primitive that knowledge_common's and
    validate_bundle's `_within` use, which this stdlib-only `python -I` observer cannot
    import (owner 6364237541 item 6)."""
    return any(PurePosixPath(target).is_relative_to(base) for base in bases)


def _record_path(bases: set[str], path: str) -> tuple[str, list[str] | None]:
    """How a RECORD row's path relates to its import root, given as `bases`, the root
    as given and the real path of the very directory opened, lexically and before any
    access: ("inside", components) for plain components under the root; ("outside",
    None) for one written as leading `..` components or as an absolute path that
    normalizes outside both bases; ("ambiguous", None)
    for anything else, an alias back into the root included (E1, Router #389
    6361519666). The row's own path is never resolved, since E1 allows no access
    outside the root: a row reaching the root through a link outside it is classified
    outside, a declared residual (Revix on #453)."""
    if "\x00" in path or path.startswith("//"):
        # A NUL names no file, and a doubled leading slash is implementation-defined
        # (Sourcery and Codex on #453): neither is unambiguously anywhere.
        return "ambiguous", None
    if os.path.isabs(path):
        return (
            ("ambiguous", None)
            if _within_any(bases, os.path.normpath(path))
            else ("outside", None)
        )
    parts = path.split("/")
    up = 0
    while up < len(parts) and parts[up] == "..":
        up += 1
    rest = parts[up:]
    if not rest or any(part in ("", ".", "..") for part in rest):
        return "ambiguous", None
    if up == 0:
        return "inside", rest
    targets = {os.path.normpath(os.path.join(base, path)) for base in bases}
    if any(_within_any(bases, target) for target in targets):
        return "ambiguous", None
    return "outside", None


class _Observation:
    """The caps and the first reason the observation stopped, if it did."""

    def __init__(self, caps: dict[str, int]) -> None:
        self.caps = caps
        self.incomplete: str | None = None
        self.read_total = 0
        self.entries_total = 0

    def stop(self, reason: str) -> None:
        self.incomplete = self.incomplete or reason

    def text(self, value: str) -> str | None:
        if len(os.fsencode(value)) > self.caps["string_bytes"]:
            self.stop("string_bytes")
            return None
        return value

    def digest_of(
        self,
        path: str,
        directory: int | None = None,
        chunks: list[bytes] | None = None,
        lengths: list[int] | None = None,
    ) -> str | None:
        """A regular file's digest, opened without following a link and without
        blocking, as the existing bounded reader treats one
        (adoption_check._read_regular_bounded), and relative to `directory` when one
        is given: anything else is unreadable. With `chunks`, the bytes digested are
        kept there too, so that a caller parses the very bytes the digest names; with
        `lengths`, their count."""
        if _SAFE_OPEN is None:
            self.stop("unreadable")
            return None
        try:
            descriptor = os.open(path, _SAFE_OPEN, dir_fd=directory)
        except OSError:
            self.stop("unreadable")
            return None
        digest, size = hashlib.sha256(), 0
        # Unbuffered, so that a read consumes no more than it asks for.
        with os.fdopen(descriptor, "rb", buffering=0) as stream:
            try:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    self.stop("unreadable")
                    return None
                # At most what is left of both caps, and one byte more to see an
                # overflow (cubic on #452).
                while chunk := stream.read(
                    min(
                        65536,
                        self.caps["file_bytes"] - size + 1,
                        self.caps["file_bytes_total"] - self.read_total + 1,
                    )
                ):
                    size += len(chunk)
                    self.read_total += len(chunk)
                    if size > self.caps["file_bytes"]:
                        self.stop("file_bytes")
                        return None
                    if self.read_total > self.caps["file_bytes_total"]:
                        self.stop("file_bytes_total")
                        return None
                    digest.update(chunk)
                    if chunks is not None:
                        chunks.append(chunk)
            except OSError:
                self.stop("unreadable")
                return None
        if lengths is not None:
            lengths.append(size)
        return digest.hexdigest()

    def record_digest(self, root: str, name: str) -> str | None:
        """The digest of a distribution's RECORD, opened relative to its `*.dist-info`
        directory, itself opened without following a link relative to the import root
        opened once. The RECORD's rows are checked against that same root, so a RECORD
        and the files it names always come from one directory (Q on #453)."""
        if _DIRECTORY_OPEN is None:
            self.stop("unreadable")
            return None
        flags = _DIRECTORY_OPEN
        # The root's real path is taken before its open, and checked to name the very
        # directory opened, so that every row is classified against the root whose
        # files it names (CodeAnt on #453).
        real = os.path.realpath(root)
        try:
            # The import root itself is followed, as the interpreter and the listing
            # follow it; nothing under it is.
            base = os.open(root, flags & ~os.O_NOFOLLOW)
        except OSError:
            self.stop("unreadable")
            return None
        try:
            bases = {os.path.normpath(root), real}
            return self.record_under(bases, real, base, name, flags)
        finally:
            os.close(base)

    def record_under(
        self, bases: set[str], real: str, base: int, name: str, flags: int
    ) -> str | None:
        """The RECORD of `name` under the opened import root `base`, once `real` is
        shown to name that very directory."""
        try:
            opened, named = os.fstat(base), os.stat(real)
            if not os.path.samestat(opened, named):
                # The root changed while it was being opened.
                self.stop("unreadable")
                return None
            directory = os.open(name, flags, dir_fd=base)
        except OSError:
            self.stop("unreadable")
            return None
        try:
            return self.record_in(bases, base, directory)
        finally:
            os.close(directory)

    def record_in(self, bases: set[str], base: int, directory: int) -> str | None:
        """The digest of the RECORD in the opened `*.dist-info` `directory`, and the
        check of its rows against the opened import root `base`."""
        chunks: list[bytes] = []
        digest = self.digest_of("RECORD", directory, chunks)
        if digest is not None:
            self.verify_record(bases, base, chunks)
        return digest

    def verify_record(
        self, bases: set[str], directory: int, chunks: list[bytes]
    ) -> None:
        """Every hashed row of a RECORD, read once, against the file it names under
        the opened root `directory`. A row without a hash stays outside the check."""
        try:
            # Strict, so that quoting a lenient reader would repair is malformed (CodeAnt
            # on #453).
            rows = csv.reader(_record_lines(chunks), strict=True)
            for row in rows:
                if self.incomplete:
                    return
                if row:
                    self.verify_row(bases, directory, row)
        except (UnicodeDecodeError, csv.Error):
            self.stop("record_malformed")

    def verify_row(self, bases: set[str], directory: int, row: list[str]) -> None:
        """One RECORD row: its sha256 claim against the bytes of the file it names."""
        if len(row) != 3:
            self.stop("record_malformed")
            return
        path, claim, size = row
        if not claim:
            return
        algorithm, _, encoded = claim.partition("=")
        if algorithm != "sha256":
            self.stop("record_unsupported")
            return
        wanted = _sha256_claim(encoded)
        # ASCII digits only, `isdigit` alone admitting digits `int` refuses or rereads,
        # and at most _SIZE_DIGITS of them.
        decimal = size.isascii() and size.isdigit() and len(size) <= _SIZE_DIGITS
        if wanted is None or (size and not decimal):
            self.stop("record_malformed")
            return
        kind, parts = _record_path(bases, path)
        if kind == "outside":
            return
        if parts is None:
            self.stop("record_ambiguous_path")
            return
        found = self.digest_listed(directory, parts)
        if found is None:
            return
        digest, length = found
        if digest != wanted or (size and size != str(length)):
            # The digest or the size the row claims disagrees with the bytes read. The
            # size is compared as the canonical decimal, never converted: a long size
            # would make `int` raise (Revix on #453).
            self.stop("record_mismatch")

    def digest_listed(self, root: int, parts: list[str]) -> tuple[str, int] | None:
        """The digest and length of a RECORD-listed file, reached from its root's
        descriptor one component at a time without following a link, so that a row
        never widens what the observer reads."""
        if _DIRECTORY_OPEN is None:
            self.stop("unreadable")
            return None
        directory = root
        try:
            for part in parts[:-1]:
                try:
                    opened = os.open(part, _DIRECTORY_OPEN, dir_fd=directory)
                except OSError:
                    self.stop("unreadable")
                    return None
                if directory != root:
                    os.close(directory)
                directory = opened
            lengths: list[int] = []
            digest = self.digest_of(parts[-1], directory, lengths=lengths)
            return None if digest is None else (digest, lengths[0])
        finally:
            if directory != root:
                os.close(directory)

    def listing(self, root: str) -> list[str]:
        """`root`'s top-level entry names, within the per-root and total entry caps:
        what was listed before a stop, as the directory gives them."""
        names: list[str] = []
        try:
            with os.scandir(root) as listing:
                for item in listing:
                    if len(names) == self.caps["entries_per_root"]:
                        self.stop("entries_per_root")
                        break
                    if self.entries_total == self.caps["entries"]:
                        self.stop("entries")
                        break
                    name = self.text(item.name)
                    if name is None:
                        break
                    names.append(name)
                    self.entries_total += 1
        except OSError:
            self.stop("unreadable")
        return names


def _import_roots(
    observation: _Observation, path: list[str]
) -> tuple[list[str], dict[str, list[str]], list[list[str | None]]]:
    """The import path's directories with their sorted entries, and its archives
    with their digests, within the caps."""
    roots: list[str] = []
    entries: dict[str, list[str]] = {}
    archives: list[list[str | None]] = []
    examined = 0
    for entry in path:
        if observation.incomplete:
            break
        # Every entry examined counts, an absent one too (CodeAnt on #452).
        if examined == observation.caps["roots"]:
            observation.stop("roots")
            break
        examined += 1
        # Only an entry that is absent is skipped: one that exists but cannot be
        # examined stops the observation (PAO 6353587922 on #452).
        try:
            mode = os.stat(entry).st_mode
        except (FileNotFoundError, NotADirectoryError):
            continue
        except (OSError, ValueError):
            observation.stop("unreadable")
            break
        root = observation.text(entry)
        if root is None:
            break
        if not stat.S_ISDIR(mode):
            # An archive on the import path, a zip or an egg: its bytes stand for it.
            archives.append([root, observation.digest_of(entry)])
            continue
        roots.append(root)
        entries[root] = sorted(observation.listing(entry))
    return roots, entries, archives


def _distributions(
    observation: _Observation, roots: list[str], entries: dict[str, list[str]]
) -> list[list[str | None]]:
    """Each root's `*.dist-info` entries, with the digest of their RECORD, within
    the distributions cap."""
    distributions: list[list[str | None]] = []
    for root in roots:
        for name in entries[root]:
            if observation.incomplete:
                break
            if not name.endswith(".dist-info"):
                continue
            if len(distributions) == observation.caps["distributions"]:
                observation.stop("distributions")
                break
            distributions.append([root, name, observation.record_digest(root, name)])
    return distributions


def observe(path: list[str], caps: dict[str, int], format_: str) -> str:
    """The observation of `path`, the interpreter's import path, as one JSON text
    that fits `output_bytes` with its newline."""
    observation = _Observation(caps)
    roots, entries, archives = _import_roots(observation, path)
    distributions = _distributions(observation, roots, entries)
    interpreter = {
        "executable": observation.text(os.path.realpath(sys.executable)),
        "version": observation.text(sys.version),
    }
    output = json.dumps(
        {
            "format": format_,
            "incomplete": observation.incomplete,
            "interpreter": interpreter,
            "roots": roots,
            "entries": entries,
            "archives": archives,
            "distributions": distributions,
        },
        sort_keys=True,
    )
    # print adds a newline, which counts against the cap too (Sourcery on #452).
    if len(output.encode()) + 1 > caps["output_bytes"]:
        output = json.dumps(
            {"format": format_, "incomplete": "output_bytes"}, sort_keys=True
        )
    return output


def main(argv: list[str]) -> int:
    """`argv` is the observer's own: its caps as JSON, then its format."""
    print(observe(sys.path, json.loads(argv[1]), argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
