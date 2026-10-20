"""The one owner of a Git tree's exact bytes on disk, and of a directory's tree
identity (#389 F3 S2 A; the owner's Option A 6268025835, Router 6297725852).

`materialize` writes a tree's blobs as the object database holds them: no archive, no
attribute, no filter and no configured driver ever touches them. `observed_tree`
computes a directory's tree identity in this process, from its bytes and modes, so no
Git command and no driver runs on that path either. `verify_tracked` checks a reused
directory against the tree's tracked paths only. Every Git child runs under one
absolute deadline, through the shared bounded drain (#365), with an environment built
here and never inherited. Each consumer keeps its own wording, errors and outputs.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import posixpath
import shutil
import stat
import subprocess  # nosec B404 -- a fixed git argv, no shell, a trusted environment
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import IO

from tools import bounded_process

DEFAULT_SECONDS = 600.0
DEFAULT_MAX_FILES = 200_000
DEFAULT_MAX_BYTES = 4 << 30

_REAP_SECONDS = 5.0
_LISTING_BYTES_PER_FILE = 4_352
_HEADER_BYTES_PER_OBJECT = 160
_FILE = "100644"
_EXECUTABLE = "100755"
_LINK = "120000"
_TREE = "40000"
_BLOB_MODES = frozenset({_FILE, _EXECUTABLE, _LINK})
# Built here, never inherited: no caller GIT_DIR, index, config, attribute source or
# replacement object reaches a child (S2-A3-01).
_GIT_ENV = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_ATTR_NOSYSTEM": "1",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_TERMINAL_PROMPT": "0",
}
_GIT_OVERRIDES = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null")


class ExactTreeError(RuntimeError):
    """A tree that cannot be represented exactly within the bounds. `code` names the
    reason for the consumer, which words it."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Limits:
    """One absolute deadline (`time.monotonic()`) and the file and byte caps of one
    operation, materialization and identity together."""

    deadline: float
    max_files: int
    max_bytes: int

    def __post_init__(self) -> None:
        for name in ("max_files", "max_bytes"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

    @classmethod
    def within(
        cls,
        seconds: float = DEFAULT_SECONDS,
        *,
        max_files: int = DEFAULT_MAX_FILES,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> Limits:
        return cls(time.monotonic() + seconds, max_files, max_bytes)


@dataclasses.dataclass(frozen=True)
class Materialized:
    tree: str
    files: int
    bytes: int


@dataclasses.dataclass(frozen=True)
class _Entry:
    mode: str
    oid: str
    path: str


def _check_deadline(limits: Limits) -> None:
    if time.monotonic() >= limits.deadline:
        raise ExactTreeError("deadline", "the operation's deadline has passed")


def _git(
    repo: Path,
    args: list[str],
    *,
    limits: Limits,
    cap: int,
    sink: Callable[[bytes], None] | None = None,
    stdin: int | None = None,
) -> bytes:
    """One bounded Git child under the operation's deadline. Its stdout goes to `sink`
    when given, else is returned; stderr is kept for the failure only."""

    _check_deadline(limits)
    out = bytearray()
    err = bytearray()

    def receive(stream: str, chunk: bytes) -> None:
        if stream == "stderr":
            err.extend(chunk)
        elif sink is not None:
            sink(chunk)
        else:
            out.extend(chunk)

    try:
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- fixed git argv, no shell
        process = subprocess.Popen(
            ["git", "-C", str(repo), *_GIT_OVERRIDES, *args],
            shell=False,
            env=_GIT_ENV,
            stdin=subprocess.DEVNULL if stdin is None else stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
    except OSError as exc:
        raise ExactTreeError(
            "git-failed", f"cannot start git ({type(exc).__name__})"
        ) from exc
    finally:
        if stdin is not None:
            os.close(stdin)
    if process.stdout is None or process.stderr is None:
        bounded_process.reap(process, timeout=_REAP_SECONDS)
        raise ExactTreeError("git-failed", f"git {args[0]} pipes are unavailable")
    streams: Mapping[str, IO[bytes]] = {
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    try:
        drained = bounded_process.drain(
            process, streams, receive, deadline=limits.deadline, cap=cap
        )
    finally:
        bounded_process.reap(process, timeout=_REAP_SECONDS)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
    if drained.outcome == "unexpected" and isinstance(
        drained.exception, ExactTreeError
    ):
        # The sink's own refusal (an escaping link, a blob that is not its id): the
        # child is reaped above, and the refusal keeps its code.
        raise drained.exception
    if drained.outcome == "deadline":
        raise ExactTreeError("deadline", f"git {args[0]} did not finish in time")
    if drained.outcome == "cap":
        raise ExactTreeError("cap-bytes", f"git {args[0]} output exceeds the bound")
    if drained.outcome != "exited" or drained.returncode != 0:
        raise ExactTreeError(
            "git-failed",
            f"git {args[0]} failed ({drained.outcome}, {drained.returncode})",
        )
    return bytes(out)


def _valid_path(path: str) -> bool:
    if not path or path.startswith("/") or "\0" in path:
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") and part.lower() != ".git" for part in parts)


def _entries(repo: Path, tree: str, limits: Limits) -> list[_Entry]:
    listing = _git(
        repo,
        ["ls-tree", "-r", "-z", "--full-tree", tree],
        limits=limits,
        cap=(limits.max_files + 1) * _LISTING_BYTES_PER_FILE,
    )
    entries: list[_Entry] = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        mode, kind, oid = meta.decode("ascii").split(" ")
        path = os.fsdecode(raw_path)
        if kind != "blob" or mode not in _BLOB_MODES or not _valid_path(path):
            raise ExactTreeError("unsupported-entry", f"{mode} {kind} entry {path!r}")
        entries.append(_Entry(mode, oid, path))
        if len(entries) > limits.max_files:
            raise ExactTreeError("cap-files", f"more than {limits.max_files} files")
    return entries


def tree_paths(repo: Path, tree: str, *, limits: Limits) -> frozenset[str]:
    """Every path the tree tracks: the source of truth about absence."""

    return frozenset(entry.path for entry in _entries(repo, tree, limits))


def _algorithm(oid: str) -> str:
    if len(oid) == 40:
        return "sha1"
    if len(oid) == 64:
        return "sha256"
    raise ExactTreeError("unsupported-entry", f"object id {oid!r} has no known format")


def _object_id(algorithm: str, kind: str, body: bytes) -> str:
    digest = hashlib.new(algorithm)
    digest.update(f"{kind} {len(body)}\0".encode("ascii"))
    digest.update(body)
    return digest.hexdigest()


def _escapes(path: str, target: str) -> bool:
    if not target or target.startswith("/"):
        return True
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    return resolved == ".." or resolved.startswith("../")


class _BatchWriter:
    """Writes `git cat-file --batch` output, streamed, into the destination: each
    object's bytes go to its entry's file as they arrive."""

    def __init__(self, root: Path, entries: list[_Entry], algorithm: str) -> None:
        self._root = root
        self._pending = iter(entries)
        self._algorithm = algorithm
        self._buffer = bytearray()
        self._entry: _Entry | None = None
        self._remaining = 0
        self._handle: int | None = None
        self._digest: hashlib._Hash | None = None
        self._link = bytearray()
        self.files = 0
        self.bytes = 0

    def __call__(self, chunk: bytes) -> None:
        self._buffer.extend(chunk)
        while self._buffer:
            if self._entry is None:
                end = self._buffer.find(b"\n")
                if end < 0:
                    return
                self._begin(bytes(self._buffer[:end]))
                del self._buffer[: end + 1]
            elif self._remaining:
                part = bytes(self._buffer[: self._remaining])
                del self._buffer[: len(part)]
                self._write(part)
            else:
                if not self._buffer.startswith(b"\n"):
                    raise ExactTreeError("git-failed", "malformed cat-file output")
                del self._buffer[:1]
                self._finish()

    def _begin(self, header: bytes) -> None:
        entry = next(self._pending, None)
        oid, kind, size = header.decode("ascii").split(" ")
        if entry is None or oid != entry.oid or kind != "blob":
            raise ExactTreeError("git-failed", "cat-file answered another object")
        self._entry, self._remaining = entry, int(size)
        self._digest = hashlib.new(self._algorithm)
        self._digest.update(f"blob {size}\0".encode("ascii"))
        if entry.mode != _LINK:
            target = self._root / entry.path
            target.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            mode = 0o755 if entry.mode == _EXECUTABLE else 0o644
            self._handle = os.open(target, flags, mode)
            os.fchmod(self._handle, mode)

    def _write(self, part: bytes) -> None:
        assert self._digest is not None and self._entry is not None
        self._digest.update(part)
        self._remaining -= len(part)
        if self._handle is None:
            self._link.extend(part)
            return
        view = memoryview(part)
        while view:
            written = os.write(self._handle, view)
            view = view[written:]

    def _finish(self) -> None:
        assert self._digest is not None and self._entry is not None
        entry = self._entry
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None
        if self._digest.hexdigest() != entry.oid:
            raise ExactTreeError("tree-mismatch", f"{entry.path!r} is not its blob")
        if entry.mode == _LINK:
            target = os.fsdecode(bytes(self._link))
            if _escapes(entry.path, target):
                raise ExactTreeError("escaping-link", f"{entry.path!r} -> {target!r}")
            link = self._root / entry.path
            link.parent.mkdir(parents=True, exist_ok=True)
            os.symlink(target, link)
            self._link.clear()
        self.files += 1
        self._entry, self._digest = None, None

    def close(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None

    def done(self) -> bool:
        return (
            self._entry is None
            and not self._buffer
            and next(self._pending, None) is None
        )


def _object_list(entries: Iterable[_Entry]) -> int:
    """The object ids as an unlinked temporary file, for a child's stdin. The returned
    descriptor is the only one left open; `_git` closes it once the child has it."""

    with tempfile.TemporaryFile() as handle:
        handle.write("".join(f"{entry.oid}\n" for entry in entries).encode("ascii"))
        handle.flush()
        handle.seek(0)
        return os.dup(handle.fileno())


def materialize(
    repo: Path, tree: str, destination: Path, *, limits: Limits
) -> Materialized:
    """Write `tree`'s exact bytes into `destination`, which must be absent or empty,
    and prove it by its independently computed identity. On any refusal the
    destination is left as it was found."""

    _check_deadline(limits)
    created = not destination.exists()
    if not created and (not destination.is_dir() or any(destination.iterdir())):
        raise ExactTreeError("destination-not-empty", str(destination))
    destination.mkdir(parents=True, exist_ok=True)
    try:
        return _materialize(repo, tree, destination, limits)
    except BaseException:
        _restore(destination, created)
        raise


def _restore(destination: Path, created: bool) -> None:
    if created:
        shutil.rmtree(destination, ignore_errors=True)
        return
    for child in destination.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def _materialize(
    repo: Path, tree: str, destination: Path, limits: Limits
) -> Materialized:
    algorithm = _algorithm(tree)
    entries = _entries(repo, tree, limits)
    sizes = _git(
        repo,
        ["cat-file", "--batch-check=%(objectsize)"],
        limits=limits,
        cap=(len(entries) + 1) * 32,
        stdin=_object_list(entries),
    ).split()
    if len(sizes) != len(entries) or not all(size.isdigit() for size in sizes):
        raise ExactTreeError("git-failed", "cat-file did not size every object")
    total = sum(int(size) for size in sizes)
    if total > limits.max_bytes:
        raise ExactTreeError("cap-bytes", f"{total} bytes exceed {limits.max_bytes}")
    writer = _BatchWriter(destination, entries, algorithm)
    try:
        _git(
            repo,
            ["cat-file", "--batch"],
            limits=limits,
            cap=total + (len(entries) + 1) * _HEADER_BYTES_PER_OBJECT,
            sink=writer,
            stdin=_object_list(entries),
        )
    finally:
        writer.close()
    if not writer.done():
        raise ExactTreeError("git-failed", "cat-file stopped before every object")
    observed = _observed(destination, algorithm, limits, frozenset())
    if observed != tree:
        raise ExactTreeError(
            "tree-mismatch", f"materialized {observed}, expected {tree}"
        )
    return Materialized(tree, writer.files, total)


def observed_tree(
    repo: Path, root: Path, *, limits: Limits, ignore: Iterable[str] = ()
) -> str:
    """The tree identity of `root`'s files, computed here from their bytes and modes:
    no Git command and no driver runs. `ignore` names relative paths, and the
    subtrees under them, that the identity leaves out."""

    _check_deadline(limits)
    output = _git(repo, ["rev-parse", "--show-object-format"], limits=limits, cap=64)
    name = output.decode("ascii").strip()
    algorithm = {"sha1": "sha1", "sha256": "sha256"}.get(name)
    if algorithm is None:
        raise ExactTreeError("unsupported-entry", f"object format {name!r}")
    return _observed(root, algorithm, limits, frozenset(ignore))


class _Budget:
    def __init__(self, limits: Limits) -> None:
        self.limits = limits
        self.files = 0
        self.bytes = 0

    def take(self, size: int) -> None:
        _check_deadline(self.limits)
        self.files += 1
        self.bytes += size
        if self.files > self.limits.max_files:
            raise ExactTreeError(
                "cap-files", f"more than {self.limits.max_files} files"
            )
        if self.bytes > self.limits.max_bytes:
            raise ExactTreeError(
                "cap-bytes", f"more than {self.limits.max_bytes} bytes"
            )


def _observed(
    root: Path, algorithm: str, limits: Limits, ignore: frozenset[str]
) -> str:
    oid = _observed_dir(root, "", algorithm, _Budget(limits), ignore)
    return oid if oid is not None else _object_id(algorithm, "tree", b"")


def _observed_dir(
    directory: Path,
    prefix: str,
    algorithm: str,
    budget: _Budget,
    ignore: frozenset[str],
) -> str | None:
    rows: list[tuple[bytes, bytes]] = []
    with os.scandir(directory) as listing:
        children = sorted(listing, key=lambda item: os.fsencode(item.name))
    for child in children:
        relative = f"{prefix}{child.name}"
        if relative in ignore:
            continue
        if child.name.lower() == ".git":
            raise ExactTreeError("unsupported-entry", f"{relative!r} is Git metadata")
        info = child.stat(follow_symlinks=False)
        name = os.fsencode(child.name)
        if stat.S_ISLNK(info.st_mode):
            target = os.fsencode(os.readlink(child.path))
            budget.take(len(target))
            rows.append(
                (name, _row(_LINK, name, _object_id(algorithm, "blob", target)))
            )
        elif stat.S_ISREG(info.st_mode):
            budget.take(info.st_size)
            mode = _EXECUTABLE if info.st_mode & stat.S_IXUSR else _FILE
            rows.append((name, _row(mode, name, _blob_id(child.path, algorithm))))
        elif stat.S_ISDIR(info.st_mode):
            sub = _observed_dir(
                Path(child.path), f"{relative}/", algorithm, budget, ignore
            )
            if sub is not None:
                rows.append((name + b"/", _row(_TREE, name, sub)))
        else:
            raise ExactTreeError("unsupported-entry", f"{relative!r} is not a file")
    if not rows:
        return None
    body = b"".join(row for _, row in sorted(rows, key=lambda item: item[0]))
    return _object_id(algorithm, "tree", body)


def _row(mode: str, name: bytes, oid: str) -> bytes:
    return mode.encode("ascii") + b" " + name + b"\0" + bytes.fromhex(oid)


def _blob_id(path: str, algorithm: str) -> str:
    size = os.lstat(path).st_size
    digest = hashlib.new(algorithm)
    digest.update(f"blob {size}\0".encode("ascii"))
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        while chunk := os.read(descriptor, 1 << 20):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def verify_tracked(
    repo: Path, tree: str, root: Path, *, limits: Limits, ignore: Iterable[str] = ()
) -> None:
    """Refuse `root` unless every path `tree` tracks, outside `ignore`, is present with
    its exact bytes and mode. Paths the tree does not track are not checked: a reused
    directory keeps its run's outputs (S2-A3-02)."""

    algorithm = _algorithm(tree)
    skipped = frozenset(ignore)
    budget = _Budget(limits)
    for entry in _entries(repo, tree, limits):
        if entry.path in skipped:
            continue
        path = root / entry.path
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            raise ExactTreeError(
                "tree-mismatch", f"{entry.path!r} is missing"
            ) from None
        if entry.mode == _LINK:
            if not stat.S_ISLNK(info.st_mode):
                raise ExactTreeError("tree-mismatch", f"{entry.path!r} is not a link")
            target = os.fsencode(os.readlink(path))
            budget.take(len(target))
            oid = _object_id(algorithm, "blob", target)
        else:
            if not stat.S_ISREG(info.st_mode):
                raise ExactTreeError("tree-mismatch", f"{entry.path!r} is not a file")
            mode = _EXECUTABLE if info.st_mode & stat.S_IXUSR else _FILE
            if mode != entry.mode:
                raise ExactTreeError("tree-mismatch", f"{entry.path!r} changed mode")
            budget.take(info.st_size)
            oid = _blob_id(str(path), algorithm)
        if oid != entry.oid:
            raise ExactTreeError("tree-mismatch", f"{entry.path!r} changed")
