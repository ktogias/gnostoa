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
"""

import hashlib
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


class _Observation:
    """The caps and the first reason the observation stopped, if it did."""

    def __init__(self, caps: dict[str, int]) -> None:
        self.caps = caps
        self.incomplete: str | None = None
        self.read_total = 0

    def stop(self, reason: str) -> None:
        self.incomplete = self.incomplete or reason

    def text(self, value: str) -> str | None:
        if len(os.fsencode(value)) > self.caps["string_bytes"]:
            self.stop("string_bytes")
            return None
        return value

    def digest_of(self, path: str, directory: int | None = None) -> str | None:
        """A regular file's digest, opened without following a link and without
        blocking, as the existing bounded reader treats one
        (adoption_check._read_regular_bounded), and relative to `directory` when one
        is given: anything else is unreadable."""
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
        try:
            return self.digest_of("RECORD", directory)
        finally:
            os.close(directory)


def observe(path: list[str], caps: dict[str, int], format_: str) -> str:
    """The observation of `path`, the interpreter's import path, as one JSON text
    that fits `output_bytes` with its newline."""
    observation = _Observation(caps)
    roots: list[str] = []
    entries: dict[str, list[str]] = {}
    archives: list[list[str | None]] = []
    total = examined = 0
    for entry in path:
        if observation.incomplete:
            break
        # Every entry examined counts, an absent one too (CodeAnt on #452).
        if examined == caps["roots"]:
            observation.stop("roots")
            break
        examined += 1
        if not os.path.exists(entry):
            continue
        root = observation.text(entry)
        if root is None:
            break
        if not os.path.isdir(entry):
            # An archive on the import path, a zip or an egg: its bytes stand for it.
            archives.append([root, observation.digest_of(entry)])
            continue
        names: list[str] = []
        try:
            with os.scandir(entry) as listing:
                for item in listing:
                    if len(names) == caps["entries_per_root"]:
                        observation.stop("entries_per_root")
                        break
                    if total == caps["entries"]:
                        observation.stop("entries")
                        break
                    name = observation.text(item.name)
                    if name is None:
                        break
                    names.append(name)
                    total += 1
        except OSError:
            observation.stop("unreadable")
        roots.append(root)
        entries[root] = sorted(names)
    distributions: list[list[str | None]] = []
    for root in roots:
        for name in entries[root]:
            if observation.incomplete:
                break
            if not name.endswith(".dist-info"):
                continue
            if len(distributions) == caps["distributions"]:
                observation.stop("distributions")
                break
            distributions.append([root, name, observation.record_digest(root, name)])
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
