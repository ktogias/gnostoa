"""The one owner of a Git tree's exact bytes on disk, and of a directory's tree
identity (#389 F3 S2 A; the owner's Option A 6268025835, Router 6297725852).

`materialize` writes a tree's blobs as the object database holds them: no archive, no
attribute, no filter and no configured driver ever touches them. It writes into a
private directory beside the destination and renames it into place, so a refusal never
touches what is already there. Every path below the caller's own parent is opened
relative to a directory descriptor and never followed: a link the tree carries is
created only after the whole tree's links are shown to stay inside it.
`observed_tree` computes a directory's tree identity in this process, from its bytes
and modes: no Git command reads the directory and no driver runs. Its one Git child,
`rev-parse --show-object-format`, reads only the object format. `verify_tracked`
checks a reused directory against the tree's tracked paths only, and
`materialize_or_verify` reuses only the very directory that was published for the
same tree.
Every Git child runs under one absolute deadline, through the shared bounded drain
(#365), with an environment built here and never inherited. A refusal names its
`code`; each consumer keeps its own wording, errors and outputs.
"""

from __future__ import annotations

import collections
import contextlib
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
from typing import IO, Protocol

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
# Required, never defaulted: a platform without one refuses the module rather than
# running it without the no-follow, directory or non-blocking guarantee (Q 4338237790).
_O_NOFOLLOW = os.O_NOFOLLOW
_O_DIRECTORY = os.O_DIRECTORY
_O_NONBLOCK = os.O_NONBLOCK
_DIRECTORY_FLAGS = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW
# The same flags, for a caller that opens this owner's directories the same way (#389 H-PYSEC-2).
DIRECTORY_FLAGS = _DIRECTORY_FLAGS
_RECORD_SUFFIX = ".exact-tree"
# The record's one format: its version, the tree, and the published directory's device
# and inode (Router #389 6319318065, G2 I). Anything else binds nothing.
_RECORD_VERSION = "gnostoa-exact-tree-record/v2"
_RECORD_FORMAT = re.compile(
    re.escape(_RECORD_VERSION)
    + r" ([0-9a-f]{40}|[0-9a-f]{64}) (0|[1-9][0-9]{0,19}) (0|[1-9][0-9]{0,19})\n"
)
_RECORD_BYTES = 256
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
    # A read never takes an optional lock (Revix 4335174132). No safe.directory is
    # pinned: it is an allowlist that disables the ownership check, which applies at
    # its strictest while no global or system configuration is read (#389 6312793333).
    "GIT_OPTIONAL_LOCKS": "0",
    # No child fetches a missing object: a promisor remote in the repository's own
    # configuration could otherwise run its command (CodeAnt 4337243054, measured).
    # The empty allow-list refuses every transport before any protocol configuration
    # is read, the repository's own `protocol.<name>.allow` included (PAO 6317385619);
    # the lazy-fetch flag stops the fetch itself where Git honours it.
    "GIT_ALLOW_PROTOCOL": "",
    "GIT_NO_LAZY_FETCH": "1",
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


_EXHAUSTED = frozenset({errno.EMFILE, errno.ENFILE})


def _filesystem(exc: OSError) -> ExactTreeError:
    """The refusal for a filesystem failure. Running out of descriptors is named: the
    descriptors held grow with the tree's depth, one per level (Revix 4335451516)."""

    if exc.errno in _EXHAUSTED:
        return ExactTreeError("cap-descriptors", type(exc).__name__)
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
    when given, else is returned. Its stderr is drained and discarded: a refusal names
    its code and outcome only, so no child text reaches a blocker. `stdin`, when
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
    """Git runs in the repository as its working directory, as `-C` would place it,
    so its argv holds only fixed tokens and canonical object ids (S6350)."""

    argv = [_git_executable(), *_GIT_OVERRIDES, *args]
    try:
        return subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- a fixed git argv, no shell, a trusted environment
            argv,
            shell=False,
            cwd=repo,
            env=_GIT_ENV,
            stdin=subprocess.DEVNULL if stdin is None else stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
    except OSError as exc:
        if exc.errno in _EXHAUSTED:
            raise _filesystem(exc) from exc
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
    if drained.outcome == "unexpected" and isinstance(
        drained.exception, ExactTreeError
    ):
        # The sink's own refusal (an object that is not its id, a malformed header,
        # a failed write, which the sink converts itself) keeps its code; the child
        # is already reaped. The drain files any OSError under "error".
        raise drained.exception
    if drained.outcome == "error" and drained.error is not None:
        if drained.error.errno in _EXHAUSTED:
            raise _filesystem(drained.error) from drained.error
    if drained.outcome == "deadline":
        raise ExactTreeError("deadline", f"git {name} did not finish in time")
    if drained.outcome == "cap":
        raise ExactTreeError("cap-bytes", f"git {name} output exceeds the bound")
    if drained.outcome != "exited" or drained.returncode != 0:
        raise ExactTreeError(
            "git-failed", f"git {name} failed ({drained.outcome}, {drained.returncode})"
        )


_HEX_DIGITS = {"sha1": 40, "sha256": 64}


def _canonical(oid: str, algorithm: str) -> str:
    """A checked object id rendered again from its numeric value: a plain `str`
    holding only lowercase hexadecimal digits, whatever object the caller passed."""

    return format(int(oid, 16), f"0{_HEX_DIGITS[algorithm]}x")


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
    except ValueError as exc:  # UnicodeDecodeError included
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


class _Listing:
    """`ls-tree -z` records parsed as they stream, refused at the first entry past the
    file cap: the listing is never held as one buffer (Revix 4336441481)."""

    def __init__(self, algorithm: str, max_files: int) -> None:
        self._algorithm = algorithm
        self._max_files = max_files
        self._buffer = bytearray()
        self.entries: list[_Entry] = []

    def __call__(self, chunk: bytes) -> None:
        self._buffer.extend(chunk)
        while (end := self._buffer.find(b"\0")) >= 0:
            record = bytes(self._buffer[:end])
            del self._buffer[: end + 1]
            if not record:
                continue
            self.entries.append(_entry(record, self._algorithm))
            if len(self.entries) > self._max_files:
                raise ExactTreeError("cap-files", f"more than {self._max_files} files")

    def finish(self) -> list[_Entry]:
        if self._buffer:
            raise ExactTreeError("git-failed", "malformed ls-tree record")
        return self.entries


def _entries(repo: Path, tree: str, limits: Limits) -> list[_Entry]:
    algorithm = _algorithm(tree)
    listing = _Listing(algorithm, limits.max_files)
    _git(
        repo,
        [
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            "--end-of-options",
            _canonical(tree, algorithm),
        ],
        limits=limits,
        cap=(limits.max_files + 1) * _LISTING_BYTES_PER_FILE,
        sink=listing,
    )
    return listing.finish()


def tree_paths(repo: Path, tree: str, *, limits: Limits) -> frozenset[str]:
    """Every path the tree tracks: the source of truth about absence."""

    return frozenset(entry.path for entry in _entries(repo, tree, limits))


def _object_id(algorithm: str, kind: str, body: bytes) -> str:
    digest = hashlib.new(algorithm)
    digest.update(f"{kind} {len(body)}\0".encode("ascii"))
    digest.update(body)
    return digest.hexdigest()


class _Cursor(Protocol):
    """Where a link resolution stands: `up` steps to the parent, refusing above the
    root; `enter` names a component's kind ("dir", "link" with its target, or "end"
    when nothing below it can be reached) and moves into a directory."""

    def up(self) -> bool: ...

    def enter(self, name: str) -> tuple[str, str]: ...


def _resolve(cursor: _Cursor, target: str, limits: Limits | None) -> bool:
    """Whether `target`, resolved from the cursor's position as the kernel would,
    stays inside: component by component, through every link the cursor meets, within
    `_LINK_HOPS`, never above the root and never to an absolute target. A lexical
    check is not enough: `d/l -> ..` with `m -> d/l/..` reaches the parent."""

    if not target or target.startswith("/"):
        return False
    pending = collections.deque(target.split("/"))
    hops = 1
    while pending:
        if limits is not None:
            _check_deadline(limits)
        outcome, through = _step(cursor, pending.popleft())
        if outcome == "next":
            continue
        if outcome != "link":
            return outcome == "inside"
        hops += 1
        if hops > _LINK_HOPS or not through or through.startswith("/"):
            return False
        pending.extendleft(reversed(through.split("/")))
    return True


def _step(cursor: _Cursor, part: str) -> tuple[str, str]:
    """One component of a resolution: "next" to go on, "inside" or "outside" when it
    ends there, or "link" with the target to resolve in its place."""

    if part in ("", "."):
        return "next", ""
    if part == "..":
        return ("next", "") if cursor.up() else ("outside", "")
    kind, through = cursor.enter(part)
    if kind == "end":
        return "inside", ""
    if kind == "dir":
        return "next", ""
    return "link", through


class _TreeCursor:
    """The immutable tree as written: a component is a link or a directory when the
    tree has one at that path; otherwise the walk ends there, at a tracked file or at
    nothing, as the kernel resolves the written tree (Router #389 6319318065, G1 W). A
    component created later is the disk check's to find on reuse."""

    def __init__(
        self, links: Mapping[str, str], directories: frozenset[str], parts: list[str]
    ) -> None:
        self._links = links
        self._directories = directories
        self._parts = parts

    def up(self) -> bool:
        if not self._parts:
            return False
        self._parts.pop()
        return True

    def enter(self, name: str) -> tuple[str, str]:
        self._parts.append(name)
        path = "/".join(self._parts)
        through = self._links.get(path)
        if through is not None:
            self._parts.pop()
            return "link", through
        return ("dir", "") if path in self._directories else ("end", "")


class _DiskCursor:
    """The components actually on disk below the root's descriptor (Router #389
    6313854024). Each real directory is opened relative to its parent without
    following, so `..` is the physical parent; a link, tracked or untracked, is read
    where it is met. Only a missing in-root component ends a resolution as reaching
    nothing; every other failure is raised, never taken for containment."""

    def __init__(self, root_fd: int) -> None:
        self._root = root_fd
        self._held: list[int] = []

    def _here(self) -> int:
        return self._held[-1] if self._held else self._root

    def descend(self, name: str) -> None:
        self._held.append(os.open(name, _DIRECTORY_FLAGS, dir_fd=self._here()))

    def up(self) -> bool:
        if not self._held:
            return False
        os.close(self._held.pop())
        return True

    def enter(self, name: str) -> tuple[str, str]:
        try:
            info = os.stat(name, dir_fd=self._here(), follow_symlinks=False)
        except FileNotFoundError:
            return "end", ""
        if stat.S_ISLNK(info.st_mode):
            return "link", os.readlink(name, dir_fd=self._here())
        if stat.S_ISDIR(info.st_mode):
            self.descend(name)
            return "dir", ""
        return "end", ""

    def close(self) -> None:
        while self._held:
            os.close(self._held.pop())


def _stays_inside(
    path: str,
    links: Mapping[str, str],
    directories: frozenset[str],
    limits: Limits | None = None,
) -> bool:
    """Whether the link at `path` resolves inside the tree as written, through the
    tree's own links and directories."""

    return _resolve(
        _TreeCursor(links, directories, path.split("/")[:-1]), links[path], limits
    )


def _resolves_on_disk(root_fd: int, path: str, target: str, limits: Limits) -> bool:
    """Whether the checked tracked link at `path`, with its checked `target` bytes,
    resolves inside the root through the components on disk at verification time,
    untracked links included. Its parent directories must still be real directories.
    This is verification-time evidence, not a lock against links created later."""

    cursor = _DiskCursor(root_fd)
    try:
        for name in path.split("/")[:-1]:
            _check_deadline(limits)
            cursor.descend(name)
        return _resolve(cursor, target, limits)
    finally:
        cursor.close()


def _check_links(
    links: Mapping[str, str], directories: frozenset[str], limits: Limits | None = None
) -> None:
    for path in sorted(links):
        if not _stays_inside(path, links, directories, limits):
            raise ExactTreeError("escaping-link", "a link resolves outside the tree")


def _tree_directories(entries: Iterable[_Entry]) -> frozenset[str]:
    """Every directory the tree has: each proper prefix of a path it tracks."""

    return frozenset(
        "/".join(parts[:end])
        for parts in (entry.path.split("/") for entry in entries)
        for end in range(1, len(parts))
    )


class _Directories:
    """Directory descriptors below one root, each opened relative to its parent and
    never through a link: a symlinked component is refused, not followed. Only the
    chain to the latest directory stays open, so the descriptors held are bounded by
    the depth, never by the number of directories. Entries arrive in Git's
    depth-first order, and a directory left behind is opened again if needed."""

    def __init__(self, root_fd: int) -> None:
        self._root: int | None = root_fd
        self._chain: list[tuple[str, int]] = []

    def at(self, relative: str, *, create: bool) -> int:
        if self._root is None:
            raise ExactTreeError("filesystem", "the directories are closed")
        parts = relative.split("/") if relative else []
        keep = 0
        while (
            keep < min(len(parts), len(self._chain))
            and self._chain[keep][0] == parts[keep]
        ):
            keep += 1
        self._release(keep)
        descriptor = self._chain[-1][1] if self._chain else self._root
        for name in parts[keep:]:
            if create:
                try:
                    os.mkdir(name, 0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
            descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
            self._chain.append((name, descriptor))
        return descriptor

    def _release(self, keep: int) -> None:
        while len(self._chain) > keep:
            os.close(self._chain.pop()[1])

    def close(self) -> None:
        self._release(0)
        if self._root is not None:
            os.close(self._root)
            self._root = None


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
        """Take one chunk of the batch output. A filesystem failure while writing is
        converted here, so it keeps its meaning past the drain (Revix 4335451516)."""

        try:
            self._take(chunk)
        except OSError as exc:
            raise _filesystem(exc) from exc

    def _take(self, chunk: bytes) -> None:
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
        except ValueError as exc:  # UnicodeDecodeError included
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
        _write_all(self._handle, part)

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
            if b"\0" in self._link:
                # No link can hold a NUL, so the tree cannot be written exactly.
                raise ExactTreeError("unsupported-entry", "a link target holds a NUL")
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


def _write_all(descriptor: int, data: bytes) -> None:
    """Write all of `data`: `os.write` may write short without raising."""

    view = memoryview(data)
    while view:
        view = view[os.write(descriptor, view) :]


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

    return _materialize(repo, tree, destination, limits, None)


def _materialize(
    repo: Path,
    tree: str,
    destination: Path,
    limits: Limits,
    accept: Callable[[_Record], None] | None,
) -> Materialized:
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
        return _publish(
            repo, tree, algorithm, parent_fd, destination.name, limits, accept
        )
    finally:
        os.close(parent_fd)


def _publish(
    repo: Path,
    tree: str,
    algorithm: str,
    parent_fd: int,
    name: str,
    limits: Limits,
    accept: Callable[[_Record], None] | None,
) -> Materialized:
    staging = f".{name}.{secrets.token_hex(8)}.staging"
    try:
        # Owner-only while the tree is written into it (cubic 4336433759); once its
        # identity is proved it gets the nested directories' mode (Revix 4336200044).
        os.mkdir(staging, 0o700, dir_fd=parent_fd)
    except OSError as exc:
        raise _filesystem(exc) from exc
    held: list[int] = []
    record: _Record | None = None
    try:
        directories = _Directories(os.open(staging, _DIRECTORY_FLAGS, dir_fd=parent_fd))
        try:
            result = _write_tree(repo, tree, algorithm, directories, limits)
            root_fd = directories.at("", create=False)
            os.fchmod(root_fd, _directory_mode(root_fd))
            if accept is not None:
                # Held open until its record is accepted, so the identity read here,
                # before the rename, is never recycled for another directory
                # meanwhile (Router #389 6319318065, G2 I).
                held.append(os.dup(root_fd))
                record = _Record(tree, *_identity(held[0]))
        finally:
            directories.close()
        os.rename(staging, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    except OSError as exc:
        _release(held)
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
        _release(held)
        _discard(parent_fd, staging)
        raise
    try:
        if accept is not None and record is not None:
            accept(record)
    finally:
        _release(held)
    return result


def _release(held: list[int]) -> None:
    while held:
        os.close(held.pop())


def _identity(descriptor: int) -> tuple[int, int]:
    """The open directory's device and inode. A filesystem that gives it no inode is
    refused: a record could not name the directory there (Router #389 6319318065)."""

    info = os.fstat(descriptor)
    if not info.st_ino:
        raise ExactTreeError("identity-unavailable", "the directory has no inode")
    return info.st_dev, info.st_ino


def _directory_mode(dir_fd: int) -> int:
    """The mode a new directory gets here, 0o755 under the process umask. It is read
    from a probe made inside the private directory, so the umask is never changed."""

    probe = f".mode-{secrets.token_hex(8)}"
    os.mkdir(probe, 0o755, dir_fd=dir_fd)
    try:
        return stat.S_IMODE(
            os.stat(probe, dir_fd=dir_fd, follow_symlinks=False).st_mode
        )
    finally:
        os.rmdir(probe, dir_fd=dir_fd)


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
    _check_links(writer.links, _tree_directories(entries), limits)
    for path, target in sorted(writer.links.items()):
        _check_deadline(limits)
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
    no Git command reads the directory and no driver runs; the one child,
    `rev-parse --show-object-format`, reads only the object format. `ignore` names
    relative paths, and the subtrees under them, that the identity leaves out."""

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
        self.listed = 0

    def list(self, name: str) -> None:
        """Charge one listed name, whatever it turns out to be, against the bound
        materialization already puts on a tree's listing. Every non-empty
        directory's name is a component of a file path beneath it, so a tree within
        that bound is never refused here; a flood of entries is, while listed."""

        _check_deadline(self.limits)
        self.listed += len(os.fsencode(name)) + 1
        if self.listed > (self.limits.max_files + 1) * _LISTING_BYTES_PER_FILE:
            raise ExactTreeError("cap-bytes", "the listing exceeds the bound")

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


@dataclasses.dataclass
class _Level:
    """One directory of the walk: its descriptor, its names still to visit (the last
    is next) and the tree rows of those already visited."""

    fd: int
    prefix: str
    raw: bytes
    pending: list[str]
    rows: list[tuple[bytes, bytes]] = dataclasses.field(default_factory=list)


def _observed(
    root_fd: int, algorithm: str, limits: Limits, ignore: frozenset[str]
) -> str:
    """The walk is iterative: the depth holds one descriptor per level and never a
    Python frame, so a deep tree is a bounded walk, not a recursion error."""

    budget = _Budget(limits)
    stack = [_Level(root_fd, "", b"", _pending(root_fd, budget))]
    try:
        while len(stack) > 1 or stack[0].pending:
            if stack[-1].pending:
                _descend(stack, algorithm, budget, ignore)
            else:
                _ascend(stack, algorithm)
    finally:
        for level in stack[1:]:
            os.close(level.fd)
    oid = _tree_of(stack[0].rows, algorithm)
    return oid if oid is not None else _object_id(algorithm, "tree", b"")


def _descend(
    stack: list[_Level], algorithm: str, budget: _Budget, ignore: frozenset[str]
) -> None:
    level = stack[-1]
    step = _observed_row(level, level.pending.pop(), algorithm, budget, ignore)
    if isinstance(step, _Level):
        stack.append(step)
    elif step is not None:
        level.rows.append(step)


def _ascend(stack: list[_Level], algorithm: str) -> None:
    """Close a finished directory and give its parent its tree row."""

    level = stack.pop()
    os.close(level.fd)
    oid = _tree_of(level.rows, algorithm)
    if oid is not None:
        stack[-1].rows.append((level.raw + b"/", _row(_TREE, level.raw, oid)))


def _tree_of(rows: list[tuple[bytes, bytes]], algorithm: str) -> str | None:
    if not rows:
        return None
    body = b"".join(row for _, row in sorted(rows, key=lambda item: item[0]))
    return _object_id(algorithm, "tree", body)


def _pending(dir_fd: int, budget: _Budget) -> list[str]:
    """A directory's names, last to visit first. They are listed through a fresh
    descriptor opened relative to the held one, since a long-held directory
    descriptor can serve a stale listing: measured on #446, a scan of it missed
    entries created after it was opened. Each name is charged as it is listed."""

    fresh = os.open(".", os.O_RDONLY | _O_DIRECTORY, dir_fd=dir_fd)
    try:
        names: list[str] = []
        with os.scandir(fresh) as listing:
            for entry in listing:
                budget.list(entry.name)
                names.append(entry.name)
    finally:
        os.close(fresh)
    return sorted(names, key=os.fsencode, reverse=True)


def _observed_row(
    level: _Level,
    name: str,
    algorithm: str,
    budget: _Budget,
    ignore: frozenset[str],
) -> tuple[bytes, bytes] | _Level | None:
    relative = f"{level.prefix}{name}"
    if relative in ignore:
        return None
    if name.lower() == ".git":
        raise ExactTreeError("unsupported-entry", "Git metadata in the directory")
    info = os.stat(name, dir_fd=level.fd, follow_symlinks=False)
    raw = os.fsencode(name)
    if stat.S_ISLNK(info.st_mode):
        target = os.fsencode(os.readlink(name, dir_fd=level.fd))
        budget.take(len(target))
        return raw, _row(_LINK, raw, _object_id(algorithm, "blob", target))
    if stat.S_ISREG(info.st_mode):
        budget.take(info.st_size)
        mode = _EXECUTABLE if info.st_mode & stat.S_IXUSR else _FILE
        oid = _blob_id_at(level.fd, name, info.st_size, algorithm, budget.limits)
        return raw, _row(mode, raw, oid)
    if stat.S_ISDIR(info.st_mode):
        child = os.open(name, _DIRECTORY_FLAGS, dir_fd=level.fd)
        try:
            return _Level(child, f"{relative}/", raw, _pending(child, budget))
        except BaseException:
            os.close(child)
            raise
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
    # Non-blocking, so a FIFO swapped in after the caller's stat is never waited on;
    # the opened descriptor itself must be a regular file (Revix 4336200032).
    descriptor = os.open(name, os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK, dir_fd=dir_fd)
    total = 0
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ExactTreeError("tree-mismatch", "a file changed while it was read")
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
    """Refuse `root` unless every path `tree` tracks, outside `ignore` (a named path
    and the subtree under it, as for `observed_tree`), is present with its exact bytes
    and mode, reached without following any link, and unless its
    tracked links stay inside. Paths the tree does not track are not checked: a
    reused directory keeps its run's outputs (S2-A3-02)."""

    _algorithm(tree)
    directories = _Directories(_open_root(root))
    try:
        _verify_in(repo, tree, directories, limits, frozenset(ignore))
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        directories.close()


def _verify_in(
    repo: Path,
    tree: str,
    directories: _Directories,
    limits: Limits,
    skipped: frozenset[str],
) -> None:
    """`verify_tracked` within the root `directories` already holds, so a caller that
    checked that descriptor verifies the very directory it checked."""

    algorithm = _algorithm(tree)
    entries = _entries(repo, tree, limits)
    links: dict[str, str] = {}
    budget = _Budget(limits)
    for entry in entries:
        if not _ignored(entry.path, skipped) and (
            _tracked_oid(directories, entry, algorithm, budget, links) != entry.oid
        ):
            raise ExactTreeError("tree-mismatch", "a tracked path changed")
    # The root's descriptor is held through both checks: the tree's own links,
    # then the components actually on disk, which a run may have changed.
    _check_links(links, _tree_directories(entries), limits)
    root_fd = directories.at("", create=False)
    for path in sorted(links):
        if not _resolves_on_disk(root_fd, path, links[path], limits):
            raise ExactTreeError(
                "escaping-link", "a link resolves outside the root on disk"
            )


def _ignored(path: str, ignore: frozenset[str]) -> bool:
    """Whether `path` is an ignored path or lies beneath one, by whole components."""

    parts = path.split("/")
    return any("/".join(parts[:end]) in ignore for end in range(1, len(parts) + 1))


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


@dataclasses.dataclass(frozen=True)
class _Record:
    """The tree a destination was written for and the directory published for it,
    by device and inode (Router #389 6319318065, G2 I)."""

    tree: str
    device: int
    inode: int

    def line(self) -> bytes:
        return f"{_RECORD_VERSION} {self.tree} {self.device} {self.inode}\n".encode()


def _bound_tree(destination: Path) -> _Record | None:
    """The destination's sibling record, or None without one. A record that is not
    exactly one current record, old, malformed or oversized, binds nothing."""

    try:
        parent_fd = os.open(destination.parent, os.O_RDONLY | _O_DIRECTORY)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _filesystem(exc) from exc
    try:
        # Non-blocking, so a FIFO planted in the record's place is never waited on;
        # the opened descriptor itself must be a regular file (Revix 4336631529).
        descriptor = os.open(
            _record_name(destination),
            os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        os.close(parent_fd)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ExactTreeError("unsafe-path", "the tree record is not a file")
        data = _read_bounded(descriptor, _RECORD_BYTES)
    finally:
        os.close(descriptor)
    text = data.decode("ascii", errors="replace") if data is not None else ""
    matched = _RECORD_FORMAT.fullmatch(text)
    if matched is None:
        raise ExactTreeError("tree-mismatch", "the record is not one current record")
    return _Record(matched[1], int(matched[2]), int(matched[3]))


def _read_bounded(descriptor: int, limit: int) -> bytes | None:
    """The file's bytes to its end, or None past `limit` of them."""

    data = bytearray()
    while chunk := os.read(descriptor, limit + 1 - len(data)):
        data += chunk
        if len(data) > limit:
            return None
    return bytes(data)


# The same bounded read, for a caller that reads an opened file within a cap (#389 H-PYSEC-2, Revix on #470).
read_bounded = _read_bounded


def _bind(destination: Path, record: _Record) -> None:
    """Record, beside the destination, the tree it was written for and the directory
    published for it. The record is published create-only: one another process wrote
    is refused and kept, never replaced (Revix 4336850409)."""

    try:
        parent_fd = os.open(destination.parent, os.O_RDONLY | _O_DIRECTORY)
    except OSError as exc:
        raise _filesystem(exc) from exc
    temporary = f"{_record_name(destination)}.{secrets.token_hex(8)}"
    created = False
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
            0o644,
            dir_fd=parent_fd,
        )
        created = True
        try:
            _write_all(descriptor, record.line())
        finally:
            os.close(descriptor)
        os.link(
            temporary,
            _record_name(destination),
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        raise ExactTreeError("tree-mismatch", "a record is already there") from exc
    except OSError as exc:
        raise _filesystem(exc) from exc
    finally:
        # Only the temporary name this call created is removed, on every path, and a
        # failure to remove it never replaces the refusal (Revix 4336200053).
        if created:
            with contextlib.suppress(OSError):
                os.unlink(temporary, dir_fd=parent_fd)
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
    tree and to the directory published for it, or reuse a destination whose record
    names the same tree and the very directory now there, after checking its tracked
    paths through that same descriptor. A destination written for another tree, or
    another directory put in its place, is refused: a file that tree tracked, and this
    one dropped, would otherwise survive the reuse. A record is never removed or reset:
    one beside an absent or emptied destination that does not bind it refuses (Router
    #389 6321735932, U0). The identity is a check on a supported local filesystem at
    that moment, not a lock on the name."""

    _algorithm(tree)
    try:
        occupied = _occupied(destination)
        present = occupied or os.path.lexists(destination)
    except OSError as exc:
        raise _filesystem(exc) from exc
    fresh = not present and _bound_tree(destination) is None
    if present:
        directories = _Directories(_open_root(destination))
        try:
            # The record is checked against the descriptor then verified, never
            # against a second opening of the path (Router #389 6319318065, G2 I). An
            # empty directory with no record is written afresh; one its record binds
            # is reused as it is, outputs or none.
            root_fd = directories.at("", create=False)
            bound = _bound_tree(destination)
            fresh = bound is None and not occupied
            if not fresh:
                if bound != _Record(tree, *_identity(root_fd)):
                    raise ExactTreeError(
                        "tree-mismatch", "the destination was written for another tree"
                    )
                _verify_in(repo, tree, directories, limits, frozenset(ignore))
        except OSError as exc:
            raise _filesystem(exc) from exc
        finally:
            directories.close()
    elif not fresh:
        raise ExactTreeError(
            "tree-mismatch", "a record survives without its destination"
        )
    if fresh:
        _materialize(
            repo, tree, destination, limits, lambda record: _accept(destination, record)
        )


def _still_published(destination: Path, record: _Record) -> None:
    """Refuse unless `destination`, unfollowed, is the directory `record` names."""

    try:
        info = os.lstat(destination)
    except OSError as exc:
        raise _filesystem(exc) from exc
    if (info.st_dev, info.st_ino) != (record.device, record.inode):
        raise ExactTreeError(
            "tree-mismatch", "another directory was published in its place"
        )


def _accept(destination: Path, record: _Record) -> None:
    """Bind the directory just published at `destination`, while it is held open. A
    writer whose directory another rename replaced is refused, before its bind and
    again after it: it is never blessed (Router #389 6319318065, G2 I). The bind is
    create-only and nothing is removed first, so any record already there, stale or
    another publisher's, is kept and this writer refuses (Router 6321735932, U0)."""

    _still_published(destination, record)
    _bind(destination, record)
    _still_published(destination, record)
