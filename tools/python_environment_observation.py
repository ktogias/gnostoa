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
sha256 that disagrees is `record_mismatch`; an unsupported algorithm, a malformed row, a
row naming a path outside its root, or a listed file that cannot be read stops the
observation too. A RECORD that agrees is not installed-content identity: rows without a
hash, files no RECORD lists and import resolution stay unobserved.
"""

import base64
import binascii
import csv
import hashlib
import io
import json
import os
import stat
import sys

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


def _sha256_claim(encoded: str) -> str | None:
    """A RECORD's sha256 claim, urlsafe base64 without padding, as hex; None unless it
    is exactly a well-formed 32-byte digest."""
    try:
        raw = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4), b"-_", validate=True
        )
    except (binascii.Error, ValueError):
        return None
    return raw.hex() if len(raw) == 32 else None


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
    ) -> str | None:
        """A regular file's digest, opened without following a link and without
        blocking, as the existing bounded reader treats one
        (adoption_check._read_regular_bounded), and relative to `directory` when one
        is given: anything else is unreadable. With `chunks`, the bytes digested are
        kept there too, so that a caller parses the very bytes the digest names."""
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
        return digest.hexdigest()

    def record_digest(self, root: str, name: str) -> str | None:
        """The digest of a distribution's RECORD, opened relative to its `*.dist-info`
        directory, which is itself opened without following a link."""
        if _DIRECTORY_OPEN is None:
            self.stop("unreadable")
            return None
        try:
            directory = os.open(os.path.join(root, name), _DIRECTORY_OPEN)
        except OSError:
            self.stop("unreadable")
            return None
        chunks: list[bytes] = []
        try:
            digest = self.digest_of("RECORD", directory, chunks)
        finally:
            os.close(directory)
        if digest is not None:
            self.verify_record(root, b"".join(chunks))
        return digest

    def verify_record(self, root: str, content: bytes) -> None:
        """Every hashed row of a RECORD, read once, against the file it names in
        `root`. A row without a hash stays outside the check."""
        try:
            directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        except OSError:
            self.stop("unreadable")
            return
        try:
            for row in csv.reader(io.StringIO(content.decode("utf-8"))):
                if self.incomplete:
                    return
                if row:
                    self.verify_row(directory, row)
        except (UnicodeDecodeError, csv.Error):
            self.stop("record_malformed")
        finally:
            os.close(directory)

    def verify_row(self, directory: int, row: list[str]) -> None:
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
        if wanted is None or (size and not size.isdigit()):
            self.stop("record_malformed")
            return
        parts = path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            # An absolute path, or one leaving its root: never opened, never verified.
            self.stop("record_outside_root")
            return
        found = self.digest_listed(directory, parts)
        if found is not None and found != wanted:
            self.stop("record_mismatch")

    def digest_listed(self, root: int, parts: list[str]) -> str | None:
        """The digest of a RECORD-listed file, reached from its root's descriptor one
        component at a time without following a link, so that a row never widens
        what the observer reads."""
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
            return self.digest_of(parts[-1], directory)
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
