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

The entries no RECORD lists are observed too, in the RECORD-owned directories: each
in-root top-level directory under which some in-root row names a file, walked whole
without following a link (D-U, H-out: #389 F3-S2-DU-HOUT-FINAL-PROOF, Router 6373641379).
Each such entry is reported with its kind: a regular file with its digest, a link with
its target, never followed, and anything else alone, never opened. A file a RECORD lists
without a hash is listed, so its bytes stay unobserved. Each root is opened once, and
its listing, its RECORDs and the walk all read that one directory (PAO 6373356762).
Every directory is charged when it is listed, before it is opened, so open descriptors
never exceed the walk's depth.
"""

import base64
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
# The held root's listing and the walk list a directory by its descriptor and read a link
# relative to one: without either, the observation stops as unreadable.
_LISTS_BY_DESCRIPTOR = (
    os.scandir in os.supports_fd and os.readlink in os.supports_dir_fd
)


# The longest RECORD size admitted: the digits of 2**64, more than any file can hold.
# A size is bounded before anything reads its file, so its conversion never reaches
# Python's integer-conversion limit (owner 6364237541; Revix on #453).
_SIZE_DIGITS = len(str(2**64))


# The longest RECORD line, in characters, that can hold a row the CSV reader accepts:
# three fields at its field limit, each doubled by escaped quotes, with their quotes,
# separators and line end. A longer line is refused before it is held.
_RECORD_LINE_CHARACTERS = 6 * csv.field_size_limit() + 16


def _record_lines(chunks: list[bytes]) -> Iterator[str]:
    """A RECORD's text, line by line as `io.StringIO` gives it, decoded strictly from
    the bytes its digest names. The bytes are held once, as they were read, and
    `chunks` is emptied as its lines are parsed; neither the whole text nor all the
    rows are ever held, so a RECORD at the per-file cap costs about its own size
    (Router #389 6364506650; Revix on #453). A line longer than
    _RECORD_LINE_CHARACTERS is refused before it is held."""
    decoder = codecs.getincrementaldecoder("utf-8")()
    pending: list[str] = []
    held = 0
    chunks.reverse()
    while chunks:
        text = decoder.decode(chunks.pop())
        start = 0
        while (end := text.find("\n", start)) != -1:
            if held + end + 1 - start > _RECORD_LINE_CHARACTERS:
                # Refused before it is joined (CodeAnt on #453).
                raise csv.Error("a RECORD line longer than any row")
            yield "".join(pending) + text[start : end + 1]
            pending.clear()
            held = 0
            start = end + 1
        held += len(text) - start
        if held > _RECORD_LINE_CHARACTERS:
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
    except ValueError:
        # binascii.Error is a ValueError, and a claim that is not ASCII raises a plain
        # one (Sonar python:S5713 on #453).
        return None
    if len(raw) != 32 or base64.urlsafe_b64encode(raw).rstrip(b"=") != encoded.encode():
        return None
    return raw.hex()


def _within_any(bases: set[str], target: str) -> bool:
    """Whether `target` is one of `bases` or lies under one, component by component and
    without the filesystem: the standard-library primitive that knowledge_common's and
    validate_bundle's `_within` use, which this stdlib-only `python -I` observer cannot
    import (owner 6364237541 item 6)."""
    # Exact for normalized paths: the base's components begin the target's and no `..`
    # follows them, since a relative base such as `.` has no components at all (cubic
    # on #453).
    path = PurePosixPath(target)
    return any(
        path.is_relative_to(base)
        and ".." not in path.parts[len(PurePosixPath(base).parts) :]
        for base in bases
    )


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


def _path_key(parts: list[str]) -> bytes:
    """A root-relative path as the walk and the RECORD rows both name it, kept as a
    digest so that a kept row costs the same whatever its path's length."""
    return hashlib.sha256(os.fsencode("/".join(parts))).digest()


class _Observation:
    """The caps and the first reason the observation stopped, if it did."""

    def __init__(self, caps: dict[str, int]) -> None:
        self.caps = caps
        self.incomplete: str | None = None
        self.read_total = 0
        self.entries_total = 0
        # Each import root opened once, its top-level names and the in-root RECORD paths
        # and owned directories found in it, and the walk's own counts (D-U).
        self.bases: dict[str, tuple[int, str]] = {}
        self.names: dict[str, set[str]] = {}
        self.listed: dict[str, set[bytes]] = {}
        self.tops: dict[str, set[str]] = {}
        self.root = ""
        self.rows = 0
        self.directories = 0
        self.walked = 0
        self.unlisted = 0
        self.unlisted_bytes = 0

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

    def base(self, root: str) -> tuple[int, str] | None:
        """`root` opened once for the whole observation, with its real path, so that its
        listing, its RECORDs and its walk read one directory (PAO 6373356762). Every use
        checks that the real path still names that very directory; once it does not,
        the observation stops as unreadable."""
        held = self.bases.get(root)
        if held is None:
            if _DIRECTORY_OPEN is None or not _LISTS_BY_DESCRIPTOR:
                self.stop("unreadable")
                return None
            # The real path is taken before the open, so that every row is classified
            # against the root whose files it names (CodeAnt on #453).
            real = os.path.realpath(root)
            try:
                # The import root itself is followed, as the interpreter follows it;
                # nothing under it is.
                held = (os.open(root, _DIRECTORY_OPEN & ~os.O_NOFOLLOW), real)
            except OSError:
                self.stop("unreadable")
                return None
            self.bases[root] = held
        try:
            if os.path.samestat(os.fstat(held[0]), os.stat(held[1])):
                return held
        except OSError:
            pass
        self.stop("unreadable")
        return None

    def close(self) -> None:
        """Close every root opened."""
        for descriptor, _ in self.bases.values():
            os.close(descriptor)
        self.bases.clear()

    def record_digest(self, root: str, name: str) -> str | None:
        """The digest of a distribution's RECORD, opened relative to its `*.dist-info`
        directory, itself opened without following a link relative to the import root
        opened once. The RECORD's rows are checked against that same root, so a RECORD
        and the files it names always come from one directory (Q on #453)."""
        held = self.base(root)
        if held is None or _DIRECTORY_OPEN is None:
            return None
        self.root = root
        base, real = held
        bases = {os.path.normpath(root), real}
        return self.record_under(bases, real, base, name, _DIRECTORY_OPEN)

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

    def verify_record(self, bases: set[str], root: int, chunks: list[bytes]) -> None:
        """Every hashed row of a RECORD, read once, against the file it names under
        the opened root `root`. A row without a hash stays outside the check."""
        try:
            # Strict, so that quoting a lenient reader would repair is malformed (CodeAnt
            # on #453).
            rows = csv.reader(_record_lines(chunks), strict=True)
            for row in rows:
                if self.incomplete:
                    return
                if row:
                    self.verify_row(bases, root, row)
        except (UnicodeDecodeError, csv.Error):
            self.stop("record_malformed")

    def verify_row(self, bases: set[str], root: int, row: list[str]) -> None:
        """One RECORD row: its sha256 claim against the bytes of the file it names."""
        if len(row) != 3:
            self.stop("record_malformed")
            return
        path, claim, size = row
        kind, parts = self.list_row(bases, path)
        if not claim or self.incomplete:
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
        if kind == "outside":
            return
        if parts is None:
            self.stop("record_ambiguous_path")
            return
        found = self.digest_listed(root, parts)
        if found is None:
            return
        digest, length = found
        if digest != wanted or (size and int(size) != length):
            # The digest or the size the row claims disagrees with the bytes read. The
            # size is a base-ten byte count, padded or not (Router 6368854931 on #453);
            # it was bounded at _SIZE_DIGITS ASCII digits above, so `int` cannot reach
            # Python's conversion limit (Revix on #453).
            self.stop("record_mismatch")

    def list_row(self, bases: set[str], path: str) -> tuple[str, list[str] | None]:
        """A row's place, hashed or not: an in-root path is kept as a digest, so that the
        walk never takes a listed file for an unlisted one, and charged to record_rows;
        its first component, when the root lists it, names an owned directory."""
        kind, parts = _record_path(bases, path)
        if kind == "inside" and parts:
            self.rows += 1
            if self.rows > self.caps["record_rows"]:
                self.stop("record_rows")
                return kind, parts
            self.listed.setdefault(self.root, set()).add(_path_key(parts))
            if len(parts) > 1 and parts[0] in self.names.get(self.root, ()):
                self.tops.setdefault(self.root, set()).add(parts[0])
        return kind, parts

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
        what was listed before a stop, as the directory gives them, listed from the root
        opened once."""
        names: list[str] = []
        held = self.base(root)
        if held is None:
            return names
        try:
            with os.scandir(held[0]) as listing:
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
        self.names[root] = set(names)
        return names

    def unlisted_entries(self, roots: list[str]) -> list[list[str | None]]:
        """Every entry of each root's owned directories that no in-root RECORD row lists:
        each owned directory charged as one directory and walked from the root opened
        once."""
        found: list[list[str | None]] = []
        for root in roots:
            for top in sorted(self.tops.get(root, ())):
                held = self.base(root) if not self.incomplete else None
                if held is None:
                    return found
                self.directories += 1
                if self.directories > self.caps["tree_directories"]:
                    self.stop("tree_directories")
                    return found
                self.walk(root, held[0], [top], found)
        return found

    def walk(
        self, root: str, parent: int, parts: list[str], found: list[list[str | None]]
    ) -> None:
        """The owned directory `parts`, already charged, opened relative to `parent`
        without following a link and listed; then each subdirectory it lists, once the
        listing is closed. At most the walk's depth is open at once."""
        if _DIRECTORY_OPEN is None:
            self.stop("unreadable")
            return
        try:
            directory = os.open(parts[-1], _DIRECTORY_OPEN, dir_fd=parent)
        except OSError:
            self.stop("unreadable")
            return
        try:
            for name in self.scan(root, directory, parts, found):
                if self.incomplete:
                    return
                self.walk(root, directory, [*parts, name], found)
        finally:
            os.close(directory)

    def scan(
        self, root: str, directory: int, parts: list[str], found: list[list[str | None]]
    ) -> list[str]:
        """The opened `directory`'s entries, each counted as it is listed: a subdirectory
        charged and its depth checked before it is kept, and an unlisted entry recorded
        while the listing is open. Returns the subdirectories, walked after it closes."""
        subdirectories: list[str] = []
        listed = self.listed.get(root, set())
        try:
            with os.scandir(directory) as listing:
                for item in listing:
                    self.walked += 1
                    if self.walked > self.caps["tree_entries"]:
                        self.stop("tree_entries")
                        break
                    name = self.text(item.name)
                    if name is None:
                        break
                    mode = item.stat(follow_symlinks=False).st_mode
                    path = [*parts, name]
                    if stat.S_ISDIR(mode):
                        self.directories += 1
                        if self.directories > self.caps["tree_directories"]:
                            self.stop("tree_directories")
                        elif len(path) > self.caps["tree_depth"]:
                            self.stop("tree_depth")
                        else:
                            subdirectories.append(name)
                    elif _path_key(path) not in listed:
                        self.record(root, directory, path, mode, found)
                    if self.incomplete:
                        break
        except OSError:
            self.stop("unreadable")
        return subdirectories

    def record(
        self,
        root: str,
        directory: int,
        path: list[str],
        mode: int,
        found: list[list[str | None]],
    ) -> None:
        """One unlisted entry of the opened `directory`: a regular file with its digest,
        a link with its target, never followed, anything else alone, never opened. Each
        is charged as it will be written, so that what the walk keeps never passes the
        output cap (Router 6373641379 item 2)."""
        self.unlisted += 1
        if self.unlisted > self.caps["unlisted"]:
            self.stop("unlisted")
            return
        text = self.text("/".join(path))
        if text is None:
            return
        value: str | None = None
        if stat.S_ISREG(mode):
            kind, value = "file", self.digest_of(path[-1], directory)
        elif stat.S_ISLNK(mode):
            kind = "link"
            try:
                value = self.text(os.readlink(path[-1], dir_fd=directory))
            except OSError:
                self.stop("unreadable")
        else:
            kind = "other"
        if self.incomplete:
            return
        entry = [root, text, kind, value]
        self.unlisted_bytes += len(json.dumps(entry)) + 2
        if self.unlisted_bytes > self.caps["output_bytes"]:
            self.stop("output_bytes")
            return
        found.append(entry)


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
    try:
        roots, entries, archives = _import_roots(observation, path)
        distributions = _distributions(observation, roots, entries)
        unlisted = [] if observation.incomplete else observation.unlisted_entries(roots)
    finally:
        observation.close()
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
            "unlisted": sorted(unlisted, key=lambda entry: (entry[0], entry[1])),
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
