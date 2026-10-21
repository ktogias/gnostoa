"""The one owner of a Git tree's exact bytes on disk, and of a directory's tree
identity (#389 F3 S2 A; the owner's Option A 6268025835, Router 6297725852).

`materialize` writes a tree's blobs as the object database holds them: no archive, no
attribute, no filter and no configured driver ever touches them. It writes into a
private directory beside the destination and renames it into place, so a refusal never
touches what is already there. Every path below the caller's own parent is opened
relative to a directory descriptor and never followed: a link the tree carries is
created only after the whole tree's links are shown to stay inside it.
`observed_tree` computes a directory's tree identity in this process, from its bytes
and modes, so no Git command and no driver runs on that path either. `verify_tracked`
checks a reused directory against the tree's tracked paths only, and
`materialize_or_verify` reuses only a directory that was written for the same tree.
Every Git child runs under one absolute deadline, through the shared bounded drain
(#365), with an environment built here and never inherited. A refusal names its
`code`; each consumer keeps its own wording, errors and outputs.
"""

from __future__ import annotations

import collections
import dataclasses
import errno
import hashlib
import os
import re
import secrets
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
_CHUNK = 1 << 20
_LINK_HOPS = 40
_FILE = "100644"
_EXECUTABLE = "100755"
_LINK = "120000"
_TREE = "40000"
_BLOB_MODES = frozenset({_FILE, _EXECUTABLE, _LINK})
_OBJECT_IDS = {
    "sha1": re.compile(r"\A[0-9a-f]{40}\Z"),
    "sha256": re.compile(r"\A[0-9a-f]{64}\Z"),
}
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_DIRECTORY_FLAGS = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW
_RECORD_SUFFIX = ".exact-tree"
# The repository's trusted executable lookup (AGENTS.md, ci/prepare-candidate).
_TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
# Built here, never inherited: no caller GIT_DIR, index, config, attribute source or
# replacement object reaches a child (S2-A3-01).
_GIT_ENV = {
    "PATH": _TRUSTED_PATH,
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
            if type(value) is not int or value < 0:
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


def _filesystem(exc: OSError) -> ExactTreeError:
    return ExactTreeError("filesystem", type(exc).__name__)


def _git_executable() -> str:
    found = shutil.which("git", path=_TRUSTED_PATH)
    if found is None or not os.path.isabs(found):
        raise ExactTreeError("git-failed", "git is not on the trusted lookup")
    return found


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
    when given, else is returned; stderr is kept for the failure only. `stdin`, when
    given, is closed here on every path, the early deadline exit included."""

    try:
        _check_deadline(limits)
        process = _start(repo, args, stdin)
    finally:
        if stdin is not None:
            os.close(stdin)
    out = bytearray()

    def receive(stream: str, chunk: bytes) -> None:
        if stream == "stdout":
            if sink is not None:
                sink(chunk)
            else:
                out.extend(chunk)

    drained = _drain(process, receive, limits, cap)
    _raise_for(drained, args[0])
    return bytes(out)


def _start(repo: Path, args: list[str], stdin: int | None) -> subprocess.Popen[bytes]:
    executable = _git_executable()
    argv = [executable, "-C", str(repo), *_GIT_OVERRIDES, *args]
    try:
        # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit -- fixed git argv, no shell
        return subprocess.Popen(  # nosec B603 -- fixed git argv, no shell, trusted env
            argv,
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


def _drain(
    process: subprocess.Popen[bytes],
    receive: Callable[[str, bytes], None],
    limits: Limits,
    cap: int,
) -> bounded_process.Drained:
    try:
        if process.stdout is None or process.stderr is None:
            raise ExactTreeError("git-failed", "git pipes are unavailable")
        streams: Mapping[str, IO[bytes]] = {
            "stdout": process.stdout,
            "stderr": process.stderr,
        }
        return bounded_process.drain(
            process, streams, receive, deadline=limits.deadline, cap=cap
        )
    finally:
        bounded_process.reap(process, timeout=_REAP_SECONDS)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def _raise_for(drained: bounded_process.Drained, name: str) -> None:
    if drained.outcome == "unexpected":
        # The sink's own refusal (an object that is not its id, a malformed header,
        # a failed write) keeps its code; the child is already reaped.
        if isinstance(drained.exception, ExactTreeError):
            raise drained.exception
        if isinstance(drained.exception, OSError):
            raise _filesystem(drained.exception) from drained.exception
    if drained.outcome == "deadline":
        raise ExactTreeError("deadline", f"git {name} did not finish in time")
    if drained.outcome == "cap":
        raise ExactTreeError("cap-bytes", f"git {name} output exceeds the bound")
    if drained.outcome != "exited" or drained.returncode != 0:
        raise ExactTreeError(
            "git-failed", f"git {name} failed ({drained.outcome}, {drained.returncode})"
        )


def _algorithm(oid: object) -> str:
    """The object format of a full, lowercase Git object id. Anything else, an
    option-shaped value included, is refused before it can reach a Git argv."""

    for name, pattern in _OBJECT_IDS.items():
        if isinstance(oid, str) and pattern.fullmatch(oid):
            return name
    raise ExactTreeError("unsupported-entry", "the id is not a Git object id")


def _valid_path(path: str) -> bool:
    if not path or path.startswith("/") or "\0" in path:
        return False
    parts = path.split("/")
    return all(part not in ("", ".", "..") and part.lower() != ".git" for part in parts)


def _entry(record: bytes, algorithm: str) -> _Entry:
    meta, tab, raw_path = record.partition(b"\t")
    try:
        mode, kind, oid = meta.decode("ascii").split(" ")
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExactTreeError("git-failed", "malformed ls-tree record") from exc
    path = os.fsdecode(raw_path)
    if (
        not tab
        or kind != "blob"
        or mode not in _BLOB_MODES
        or not _valid_path(path)
        or not _OBJECT_IDS[algorithm].fullmatch(oid)
    ):
        raise ExactTreeError("unsupported-entry", f"a {mode} {kind} entry")
    return _Entry(mode, oid, path)


def _entries(repo: Path, tree: str, limits: Limits) -> list[_Entry]:
    algorithm = _algorithm(tree)
    listing = _git(
        repo,
        ["ls-tree", "-r", "-z", "--full-tree", "--end-of-options", tree],
        limits=limits,
        cap=(limits.max_files + 1) * _LISTING_BYTES_PER_FILE,
    )
    entries: list[_Entry] = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        entries.append(_entry(record, algorithm))
        if len(entries) > limits.max_files:
            raise ExactTreeError("cap-files", f"more than {limits.max_files} files")
    return entries


def tree_paths(repo: Path, tree: str, *, limits: Limits) -> frozenset[str]:
    """Every path the tree tracks: the source of truth about absence."""

    return frozenset(entry.path for entry in _entries(repo, tree, limits))


def _object_id(algorithm: str, kind: str, body: bytes) -> str:
    digest = hashlib.new(algorithm)
    digest.update(f"{kind} {len(body)}\0".encode("ascii"))
    digest.update(body)
    return digest.hexdigest()


def _stays_inside(path: str, links: Mapping[str, str]) -> bool:
    """Whether the link at `path` resolves inside the tree, following the tree's own
    links as the kernel would, component by component and within `_LINK_HOPS`. A
    lexical check is not enough: `d/l -> ..` with `m -> d/l/..` reaches the parent."""

    target = links[path]
    if not target or target.startswith("/"):
        return False
    parts = path.split("/")[:-1]
    pending = collections.deque(target.split("/"))
    hops = 1
    while pending:
        part = pending.popleft()
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return False
            parts.pop()
            continue
        parts.append(part)
        through = links.get("/".join(parts))
        if through is None:
            continue
        hops += 1
        if hops > _LINK_HOPS or not through or through.startswith("/"):
            return False
        parts.pop()
        pending.extendleft(reversed(through.split("/")))
    return True


def _check_links(links: Mapping[str, str]) -> None:
    for path in sorted(links):
        if not _stays_inside(path, links):
            raise ExactTreeError("escaping-link", "a link resolves outside the tree")


class _Directories:
    """Directory descriptors below one root, each opened relative to its parent and
    never through a link: a symlinked component is refused, not followed."""

    def __init__(self, root_fd: int) -> None:
        self._open: dict[str, int] = {"": root_fd}

    def at(self, relative: str, *, create: bool) -> int:
        if relative in self._open:
            return self._open[relative]
        parent, _, name = relative.rpartition("/")
        parent_fd = self.at(parent, create=create)
        if create:
            try:
                os.mkdir(name, 0o755, dir_fd=parent_fd)
            except FileExistsError:
                pass
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
        self._open[relative] = descriptor
        return descriptor

    def close(self) -> None:
        for descriptor in self._open.values():
            os.close(descriptor)
        self._open.clear()


class _BatchWriter:
    """Writes `git cat-file --batch` output, streamed, beneath the directories: each
    object's bytes go to its entry's file as they arrive. Links are only collected
    here; they are created once the whole tree's links are shown to stay inside."""

    def __init__(self, root: object, entries: list[_Entry], algorithm: str) -> None:
        self._root = root
        self._pending = iter(entries)
        self._algorithm = algorithm
        self._buffer = bytearray()
        self._entry: _Entry | None = None
        self._remaining = 0
        self._handle: int | None = None
        self._digest: hashlib._Hash | None = None
        self._link = bytearray()
        self.links: dict[str, str] = {}
        self.files = 0

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
        try:
            oid, kind, size_text = header.decode("ascii").split(" ")
            size = int(size_text)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ExactTreeError("git-failed", "malformed cat-file header") from exc
        entry = next(self._pending, None)
        if entry is None or oid != entry.oid or kind != "blob" or size < 0:
            raise ExactTreeError("git-failed", "cat-file answered another object")
        self._entry, self._remaining = entry, size
        self._digest = hashlib.new(self._algorithm)
        self._digest.update(f"blob {size}\0".encode("ascii"))
        if entry.mode != _LINK:
            if not isinstance(self._root, _Directories):
                raise ExactTreeError("git-failed", "no destination to write into")
            parent, _, name = entry.path.rpartition("/")
            parent_fd = self._root.at(parent, create=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW
            mode = 0o755 if entry.mode == _EXECUTABLE else 0o644
            self._handle = os.open(name, flags, mode, dir_fd=parent_fd)
            os.fchmod(self._handle, mode)

    def _write(self, part: bytes) -> None:
        if self._digest is None:
            raise ExactTreeError("git-failed", "cat-file bytes before a header")
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
        entry, digest = self._entry, self._digest
        if entry is None or digest is None:
            raise ExactTreeError(
                "git-failed", "cat-file ended an object it never began"
            )
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None
        if digest.hexdigest() != entry.oid:
            raise ExactTreeError("tree-mismatch", "an object is not its blob")
        if entry.mode == _LINK:
            self.links[entry.path] = os.fsdecode(bytes(self._link))
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


def _occupied(destination: Path) -> bool:
    """Whether `destination` holds anything. It must be absent or an empty real
    directory; a link in its place is refused, never followed."""

    try:
        info = os.lstat(destination)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(info.st_mode):
        raise ExactTreeError("unsafe-path", "the destination is a link")
    if not stat.S_ISDIR(info.st_mode):
        raise ExactTreeError("destination-not-empty", "the destination is a file")
    descriptor = os.open(destination, _DIRECTORY_FLAGS)
    try:
        with os.scandir(descriptor) as listing:
            return any(True for _ in listing)
    finally:
        os.close(descriptor)


def materialize(
    repo: Path, tree: str, destination: Path, *, limits: Limits
) -> Materialized:
    """Write `tree`'s exact bytes into `destination`, which must be absent or empty,
    and prove it by its independently computed identity. The bytes are written into a
    private directory beside it and renamed into place; on any refusal only that
    private directory is removed, so the destination is left as it was found."""

    _check_deadline(limits)
    algorithm = _algorithm(tree)
    try:
        if _occupied(destination):
            raise ExactTreeError("destination-not-empty", "the destination holds files")
        destination.parent.mkdir(parents=True, exist_ok=True)
        parent_fd = os.open(destination.parent, os.O_RDONLY | _O_DIRECTORY)
    except OSError as exc:
        raise _filesystem(exc) from exc
    try:
        return _publish(repo, tree, algorithm, parent_fd, destination.name, limits)
    finally:
        os.close(parent_fd)


def _publish(
    repo: Path, tree: str, algorithm: str, parent_fd: int, name: str, limits: Limits
) -> Materialized:
    staging = f".{name}.{secrets.token_hex(8)}.staging"
    try:
        os.mkdir(staging, 0o700, dir_fd=parent_fd)
    except OSError as exc:
        raise _filesystem(exc) from exc
    try:
        directories = _Directories(os.open(staging, _DIRECTORY_FLAGS, dir_fd=parent_fd))
        try:
            result = _write_tree(repo, tree, algorithm, directories, limits)
        finally:
            directories.close()
        os.rename(staging, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except OSError as exc:
        _discard(parent_fd, staging)
        if exc.errno in (errno.ENOTEMPTY, errno.EEXIST):
            raise ExactTreeError(
                "destination-not-empty", "the destination filled"
            ) from exc
        if exc.errno == errno.ENOTDIR:
            raise ExactTreeError(
                "unsafe-path", "the destination is not a directory"
            ) from exc
        raise _filesystem(exc) from exc
    except BaseException:
        _discard(parent_fd, staging)
        raise
    return result


def _discard(parent_fd: int, staging: str) -> None:
    """Remove the private directory. A failure here never replaces the refusal being
    raised, and it cannot leave bytes at the destination, which was never written."""

    try:
        shutil.rmtree(staging, dir_fd=parent_fd)
    except OSError:
        pass


def _write_tree(
    repo: Path, tree: str, algorithm: str, directories: _Directories, limits: Limits
) -> Materialized:
    entries = _entries(repo, tree, limits)
    total = _total_size(repo, entries, limits)
    writer = _BatchWriter(directories, entries, algorithm)
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
    _check_links(writer.links)
    for path, target in sorted(writer.links.items()):
        parent, _, name = path.rpartition("/")
        os.symlink(target, name, dir_fd=directories.at(parent, create=True))
    observed = _observed(
        directories.at("", create=False), algorithm, limits, frozenset()
    )
    if observed != tree:
        raise ExactTreeError(
            "tree-mismatch", f"materialized {observed}, expected {tree}"
        )
    return Materialized(tree, writer.files, total)


def _total_size(repo: Path, entries: list[_Entry], limits: Limits) -> int:
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
    return total


def _open_root(root: Path) -> int:
    try:
        return os.open(root, _DIRECTORY_FLAGS)
    except OSError as exc:
        if exc.errno in (errno.ELOOP, errno.ENOTDIR):
            raise ExactTreeError("unsafe-path", "the root is not a directory") from exc
        raise _filesystem(exc) from exc


def observed_tree(
    repo: Path, root: Path, *, limits: Limits, ignore: Iterable[str] = ()
) -> str:
    """The tree identity of `root`'s files, computed here from their bytes and modes:
    no Git command and no driver runs. `ignore` names relative paths, and the
    subtrees under them, that the identity leaves out."""

    _check_deadline(limits)
    output = _git(repo, ["rev-parse", "--show-object-format"], limits=limits, cap=64)
    name = output.decode("ascii", errors="replace").strip()
    if name not in _OBJECT_IDS:
        raise ExactTreeError("unsupported-entry", "an unknown object format")
    root_fd = _open_root(root)
    try:
        return _observed(root_fd, name, limits, frozenset(ignore))
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        os.close(root_fd)


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
    root_fd: int, algorithm: str, limits: Limits, ignore: frozenset[str]
) -> str:
    oid = _observed_dir(root_fd, "", algorithm, _Budget(limits), ignore)
    return oid if oid is not None else _object_id(algorithm, "tree", b"")


def _names(dir_fd: int) -> list[str]:
    """A directory's entries, listed through a fresh descriptor opened relative to the
    held one. A long-held directory descriptor can serve a stale listing: measured on
    #446, a scan of it missed entries created after it was opened."""

    fresh = os.open(".", os.O_RDONLY | _O_DIRECTORY, dir_fd=dir_fd)
    try:
        with os.scandir(fresh) as listing:
            return [entry.name for entry in listing]
    finally:
        os.close(fresh)


def _observed_dir(
    dir_fd: int, prefix: str, algorithm: str, budget: _Budget, ignore: frozenset[str]
) -> str | None:
    names = sorted(_names(dir_fd), key=os.fsencode)
    rows = [
        row
        for name in names
        if (row := _observed_row(dir_fd, name, prefix, algorithm, budget, ignore))
    ]
    if not rows:
        return None
    body = b"".join(row for _, row in sorted(rows, key=lambda item: item[0]))
    return _object_id(algorithm, "tree", body)


def _observed_row(
    dir_fd: int,
    name: str,
    prefix: str,
    algorithm: str,
    budget: _Budget,
    ignore: frozenset[str],
) -> tuple[bytes, bytes] | None:
    relative = f"{prefix}{name}"
    if relative in ignore:
        return None
    if name.lower() == ".git":
        raise ExactTreeError("unsupported-entry", "Git metadata in the directory")
    info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    raw = os.fsencode(name)
    if stat.S_ISLNK(info.st_mode):
        target = os.fsencode(os.readlink(name, dir_fd=dir_fd))
        budget.take(len(target))
        return raw, _row(_LINK, raw, _object_id(algorithm, "blob", target))
    if stat.S_ISREG(info.st_mode):
        budget.take(info.st_size)
        mode = _EXECUTABLE if info.st_mode & stat.S_IXUSR else _FILE
        oid = _blob_id_at(dir_fd, name, info.st_size, algorithm, budget.limits)
        return raw, _row(mode, raw, oid)
    if stat.S_ISDIR(info.st_mode):
        child = os.open(name, _DIRECTORY_FLAGS, dir_fd=dir_fd)
        try:
            sub = _observed_dir(child, f"{relative}/", algorithm, budget, ignore)
        finally:
            os.close(child)
        return None if sub is None else (raw + b"/", _row(_TREE, raw, sub))
    raise ExactTreeError("unsupported-entry", "an entry that is not a file")


def _row(mode: str, name: bytes, oid: str) -> bytes:
    return mode.encode("ascii") + b" " + name + b"\0" + bytes.fromhex(oid)


def _blob_id_at(
    dir_fd: int, name: str, size: int, algorithm: str, limits: Limits
) -> str:
    """The blob id of a file of the recorded `size`. It reads at most one byte past
    that size, checks the deadline before every read, and refuses a file whose size
    changed while it was read."""

    digest = hashlib.new(algorithm)
    digest.update(f"blob {size}\0".encode("ascii"))
    descriptor = os.open(name, os.O_RDONLY | _O_NOFOLLOW, dir_fd=dir_fd)
    total = 0
    try:
        while total <= size:
            _check_deadline(limits)
            chunk = os.read(descriptor, min(_CHUNK, size + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total <= size:
                digest.update(chunk)
    finally:
        os.close(descriptor)
    if total != size:
        raise ExactTreeError("tree-mismatch", "a file changed while it was read")
    return digest.hexdigest()


def verify_tracked(
    repo: Path, tree: str, root: Path, *, limits: Limits, ignore: Iterable[str] = ()
) -> None:
    """Refuse `root` unless every path `tree` tracks, outside `ignore`, is present with
    its exact bytes and mode, reached without following any link, and unless its
    tracked links stay inside. Paths the tree does not track are not checked: a
    reused directory keeps its run's outputs (S2-A3-02)."""

    algorithm = _algorithm(tree)
    skipped = frozenset(ignore)
    entries = _entries(repo, tree, limits)
    directories = _Directories(_open_root(root))
    links: dict[str, str] = {}
    try:
        budget = _Budget(limits)
        for entry in entries:
            if entry.path not in skipped and (
                _tracked_oid(directories, entry, algorithm, budget, links) != entry.oid
            ):
                raise ExactTreeError("tree-mismatch", "a tracked path changed")
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        directories.close()
    _check_links(links)


def _tracked_oid(
    directories: _Directories,
    entry: _Entry,
    algorithm: str,
    budget: _Budget,
    links: dict[str, str],
) -> str:
    parent, _, name = entry.path.rpartition("/")
    try:
        dir_fd = directories.at(parent, create=False)
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            raise ExactTreeError("tree-mismatch", "a tracked path is missing") from exc
        raise
    if entry.mode == _LINK:
        if not stat.S_ISLNK(info.st_mode):
            raise ExactTreeError("tree-mismatch", "a tracked link is not a link")
        target = os.readlink(name, dir_fd=dir_fd)
        budget.take(len(os.fsencode(target)))
        links[entry.path] = target
        return _object_id(algorithm, "blob", os.fsencode(target))
    if not stat.S_ISREG(info.st_mode):
        raise ExactTreeError("tree-mismatch", "a tracked file is not a file")
    mode = _EXECUTABLE if info.st_mode & stat.S_IXUSR else _FILE
    if mode != entry.mode:
        raise ExactTreeError("tree-mismatch", "a tracked file changed mode")
    budget.take(info.st_size)
    return _blob_id_at(dir_fd, name, info.st_size, algorithm, budget.limits)


def _record_name(destination: Path) -> str:
    return f".{destination.name}{_RECORD_SUFFIX}"


def _bound_tree(destination: Path) -> str | None:
    """The tree a destination was written for, from its sibling record."""

    try:
        parent_fd = os.open(destination.parent, os.O_RDONLY | _O_DIRECTORY)
    except OSError as exc:
        raise _filesystem(exc) from exc
    try:
        descriptor = os.open(
            _record_name(destination), os.O_RDONLY | _O_NOFOLLOW, dir_fd=parent_fd
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        os.close(parent_fd)
    try:
        return os.read(descriptor, 130).decode("ascii", errors="replace").strip()
    finally:
        os.close(descriptor)


def _bind(destination: Path, tree: str) -> None:
    """Record which tree the destination was written for, atomically, beside it."""

    try:
        parent_fd = os.open(destination.parent, os.O_RDONLY | _O_DIRECTORY)
    except OSError as exc:
        raise _filesystem(exc) from exc
    temporary = f"{_record_name(destination)}.{secrets.token_hex(8)}"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
            0o644,
            dir_fd=parent_fd,
        )
        try:
            os.write(descriptor, f"{tree}\n".encode("ascii"))
        finally:
            os.close(descriptor)
        os.rename(
            temporary,
            _record_name(destination),
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        os.close(parent_fd)


def materialize_or_verify(
    repo: Path,
    tree: str,
    destination: Path,
    *,
    limits: Limits,
    ignore: Iterable[str] = (),
) -> None:
    """Materialize `tree` into an absent or empty `destination` and bind it to that
    tree, or reuse a destination already bound to the same tree, after checking its
    tracked paths. A destination written for another tree is refused: a file that
    tree tracked, and this one dropped, would otherwise survive the reuse."""

    _algorithm(tree)
    try:
        occupied = _occupied(destination)
    except OSError as exc:
        raise _filesystem(exc) from exc
    if not occupied:
        materialize(repo, tree, destination, limits=limits)
        _bind(destination, tree)
        return
    if _bound_tree(destination) != tree:
        raise ExactTreeError(
            "tree-mismatch", "the destination was written for another tree"
        )
    verify_tracked(repo, tree, destination, limits=limits, ignore=ignore)
