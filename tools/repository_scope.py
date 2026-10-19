from __future__ import annotations

import os
import re
import stat
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

SOURCE_MANIFEST = ".gnostoa-source-files"

REPOSITORY_SCOPE_ERROR_CATEGORIES = frozenset(
    {
        "GIT_FAILED",
        "GIT_IO",
        "GIT_METADATA_IO",
        "GIT_TIMEOUT",
        "MANIFEST_INVALID",
        "MANIFEST_IO",
        "MANIFEST_MISSING",
        "UNSAFE_PATH",
        "UNKNOWN",
    }
)


class RepositoryScopeError(RuntimeError):
    """Raised when the canonical repository candidate cannot be enumerated."""

    def __init__(self, message: str, *, category: str = "UNKNOWN") -> None:
        super().__init__(message)
        self.category = (
            category if category in REPOSITORY_SCOPE_ERROR_CATEGORIES else "UNKNOWN"
        )


def scope_error_detail(prefix: str, exc: RepositoryScopeError) -> str:
    """Describe one scope failure without publishing its exception text.

    Scope failures carry the repository root, manifest paths, unsafe candidate
    paths and raw Git or OSError text, so every consumer must report the
    classified category instead of the message. Reporting goes through this
    one helper so a new consumer cannot silently reintroduce the leak.
    """

    category = (
        exc.category if exc.category in REPOSITORY_SCOPE_ERROR_CATEGORIES else "UNKNOWN"
    )
    return f"{prefix} (scope error: {category})"


def _decode_paths(encoded_paths: bytes, source: str) -> list[Path]:
    paths: list[Path] = []
    for encoded in encoded_paths.split(b"\0"):
        if not encoded:
            continue
        relative = Path(os.fsdecode(encoded))
        if relative == Path(".") or relative.is_absolute() or ".." in relative.parts:
            raise RepositoryScopeError(
                f"{source} returned an unsafe candidate path: {relative}",
                category="UNSAFE_PATH",
            )
        paths.append(relative)
    return sorted(set(paths), key=lambda path: path.as_posix())


# A linked worktree's `gitdir` record holds one path and its terminator: PATH_MAX on
# Linux bounds it, beyond any path Git could open (the owner's N-a on #436).
_WORKTREE_RECORD_BYTES = 4096


def _git_result(
    root: Path, arguments: list[str], *, timeout: float | None, purpose: str
) -> subprocess.CompletedProcess[bytes]:
    """One Git child of `root`, classified: GIT_TIMEOUT past `timeout`, and GIT_IO when
    Git cannot run."""
    try:
        return subprocess.run(
            ["git", "-c", f"safe.directory={root}", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RepositoryScopeError(
            f"cannot {purpose} in {root} within {timeout} seconds",
            category="GIT_TIMEOUT",
        ) from exc
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot {purpose} in {root}: {exc}",
            category="GIT_IO",
        ) from exc


def _git_checked(
    result: subprocess.CompletedProcess[bytes], root: Path, purpose: str
) -> bytes:
    """A Git child's output, or GIT_FAILED on a non-zero exit."""
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryScopeError(
            message or f"cannot {purpose} in {root}",
            category="GIT_FAILED",
        )
    return result.stdout


def _git_output(
    root: Path, arguments: list[str], *, timeout: float | None, purpose: str
) -> bytes:
    """One Git read of `root`, classified: GIT_TIMEOUT past `timeout`, GIT_IO when Git
    cannot run, and GIT_FAILED on a non-zero exit."""
    return _git_checked(
        _git_result(root, arguments, timeout=timeout, purpose=purpose), root, purpose
    )


def _git_answer(
    root: Path, arguments: list[str], *, timeout: float | None, purpose: str
) -> str:
    """Git's one-line answer, less exactly its one terminator, so a name that ends in a
    newline keeps it (CodeAnt on #436)."""
    output = _git_output(root, arguments, timeout=timeout, purpose=purpose)
    return os.fsdecode(output[:-1] if output.endswith(b"\n") else output)


def _budget_left(
    root: Path, end: float | None, timeout: float | None, purpose: str
) -> float | None:
    """What one budget leaves for the next Git read: none once it is spent, so a spent
    budget starts no Git (the Router's I-b on #436)."""
    if end is None:
        return None
    remaining = end - time.monotonic()
    if remaining <= 0:
        raise RepositoryScopeError(
            f"cannot {purpose} in {root} within {timeout} seconds",
            category="GIT_TIMEOUT",
        )
    return remaining


def _git_candidate_paths(root: Path, *, timeout: float | None = None) -> list[Path]:
    output = _git_output(
        root,
        ["ls-files", "--cached", "--deduplicate", "-z"],
        timeout=timeout,
        purpose="enumerate Git-tracked candidate files",
    )
    return _decode_paths(output, "Git")


def _manifest_candidate_paths(root: Path) -> list[Path]:
    manifest = root / SOURCE_MANIFEST
    try:
        mode = manifest.lstat().st_mode
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot read packaged source manifest {manifest}: {exc}",
            category="MANIFEST_IO",
        ) from exc
    if not stat.S_ISREG(mode):
        raise RepositoryScopeError(
            f"packaged source manifest is not a regular file: {manifest}",
            category="MANIFEST_INVALID",
        )

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(manifest, flags)
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot open packaged source manifest {manifest}: {exc}",
            category="MANIFEST_IO",
        ) from exc
    try:
        with os.fdopen(descriptor, "rb") as source:
            encoded_paths = source.read()
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot read packaged source manifest {manifest}: {exc}",
            category="MANIFEST_IO",
        ) from exc
    return _decode_paths(encoded_paths, "packaged source manifest")


def has_git_metadata(root: Path, *, timeout: float | None = None) -> bool:
    """Whether `root/.git` is Git metadata of `root` itself. Its entry is classified by
    `lstat`, never followed: False for a missing entry, with no Git read; a symlink,
    dangling or not, or any other kind than a directory or a regular file is
    UNSAFE_PATH, and an entry that cannot be inspected GIT_METADATA_IO (cubic and
    Claude, the Router's 6239259708 on #436). An accepted entry is True only when
    Git's own `rev-parse --show-toplevel` names `root`: a malformed `.git` directory
    that Git skips for an enclosing checkout is UNSAFE_PATH, and a failed or
    timed-out answer keeps Git's own category (cubic, the Router's I-b on #436). The
    entry's own inspection is inside a finite `timeout`: the Git read gets only what
    is left of it, and a spent one starts no Git (Codex, the Router's I-b on #436).

    A regular-file `.git` binds only through the selected Git directory's own
    declaration (the owner's N-a, 6241486091 on #436): a linked worktree's directory by
    its `gitdir` back-pointer, which must name `root/.git`, and any other by its
    `core.worktree`, which must name `root`. So a `gitdir:` file that borrows another
    checkout's or another worktree's metadata is UNSAFE_PATH, though Git's top level
    still names `root`. So is a separate Git directory that declares no `core.worktree`,
    as `git init --separate-git-dir` leaves it: a supported-layout narrowing the owner
    approved, not a claim that the layout is malformed. It binds once its work tree is
    declared, `git -C <root> config core.worktree <root>`, which is never written here.
    Every Git read shares the one budget."""
    end = None if timeout is None else time.monotonic() + timeout
    git_metadata = root / ".git"
    try:
        mode = git_metadata.lstat().st_mode
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot inspect Git metadata at {git_metadata}: {exc}",
            category="GIT_METADATA_IO",
        ) from exc
    if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
        raise RepositoryScopeError(
            f"Git metadata at {git_metadata} is not a directory or a regular file",
            category="UNSAFE_PATH",
        )
    top = _git_answer(
        root,
        ["rev-parse", "--show-toplevel"],
        timeout=_budget_left(root, end, timeout, "confirm the Git top level"),
        purpose="confirm the Git top level",
    )
    # Git's top level is absolute, so the root is resolved before the comparison
    # (cubic, the Router's I-b on #436).
    if not top or Path(top) != root.resolve():
        raise RepositoryScopeError(
            f"Git metadata at {git_metadata} belongs to another work tree",
            category="UNSAFE_PATH",
        )
    if stat.S_ISREG(mode):
        _bind_gitfile(root, end, timeout)
    return True


def _bind_gitfile(root: Path, end: float | None, timeout: float | None) -> None:
    """Refuse a regular-file `.git` whose selected Git directory does not itself
    declare `root` (has_git_metadata)."""
    git_metadata = root / ".git"

    def located(arguments: list[str], purpose: str) -> Path:
        answer = _git_answer(
            root,
            arguments,
            timeout=_budget_left(root, end, timeout, purpose),
            purpose=purpose,
        )
        if not answer:
            raise RepositoryScopeError(
                f"Git gave no answer to {purpose} in {root}", category="GIT_FAILED"
            )
        # A relative answer is relative to Git's working directory, `root`.
        return Path(root, answer).resolve()

    git_dir = located(["rev-parse", "--absolute-git-dir"], "locate the Git directory")
    common = located(
        ["rev-parse", "--git-common-dir"], "locate the common Git directory"
    )
    if git_dir != common:
        record = located(
            ["rev-parse", "--git-path", "gitdir"], "locate the worktree back-pointer"
        )
        # Trimmed as Git's own reader trims it; a relative record is relative to its
        # worktree directory.
        named = os.fsdecode(_worktree_back_pointer(record, git_metadata).rstrip())
        if Path(git_dir, named).resolve() != root.resolve() / ".git":
            raise RepositoryScopeError(
                f"Git metadata at {git_metadata} selects the worktree directory "
                f"{git_dir}, whose back-pointer names another work tree",
                category="UNSAFE_PATH",
            )
        return
    declared = _declared_work_tree(root, end, timeout)
    if declared is None:
        raise RepositoryScopeError(
            f"Git metadata at {git_metadata} selects the separate Git directory "
            f"{git_dir}, which declares no core.worktree. That is valid Git, but a "
            "separate Git directory binds here only to the work tree it declares (the "
            f"owner's N-a on #436); declare it: git -C {root} config core.worktree "
            f"{root}",
            category="UNSAFE_PATH",
        )
    if Path(git_dir, declared).resolve() != root.resolve():
        raise RepositoryScopeError(
            f"Git metadata at {git_metadata} selects the Git directory {git_dir}, "
            "whose core.worktree names another work tree",
            category="UNSAFE_PATH",
        )


def _worktree_back_pointer(record: Path, git_metadata: Path) -> bytes:
    """A linked worktree's `gitdir` record, read once and bounded: a regular file of at
    most _WORKTREE_RECORD_BYTES, opened without blocking, so a FIFO in its place cannot
    stall the read. A missing, irregular or oversized record is UNSAFE_PATH, never
    absence; one that cannot be read is GIT_METADATA_IO."""
    try:
        descriptor = os.open(
            record,
            os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0),
        )
    except FileNotFoundError:
        raise RepositoryScopeError(
            f"Git metadata at {git_metadata} selects a worktree directory with no "
            f"worktree back-pointer at {record}",
            category="UNSAFE_PATH",
        ) from None
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot read the worktree back-pointer {record}: {exc}",
            category="GIT_METADATA_IO",
        ) from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RepositoryScopeError(
                f"the worktree back-pointer {record} is not a regular file",
                category="UNSAFE_PATH",
            )
        chunks: list[bytes] = []
        room = _WORKTREE_RECORD_BYTES + 1
        while room:
            chunk = os.read(descriptor, room)
            if not chunk:
                break
            chunks.append(chunk)
            room -= len(chunk)
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot read the worktree back-pointer {record}: {exc}",
            category="GIT_METADATA_IO",
        ) from exc
    finally:
        os.close(descriptor)
    content = b"".join(chunks)
    if len(content) > _WORKTREE_RECORD_BYTES:
        raise RepositoryScopeError(
            f"the worktree back-pointer {record} is larger than "
            f"{_WORKTREE_RECORD_BYTES} bytes",
            category="UNSAFE_PATH",
        )
    return content


def _declared_work_tree(
    root: Path, end: float | None, timeout: float | None
) -> str | None:
    """The selected Git directory's own `core.worktree`, as Git's setup takes it
    (measured on Git 2.47.3): from its config, then its config.worktree under
    extensions.worktreeConfig, the last value winning; never from an included file,
    the global or system config, or a `-c`, which setup ignores (the Router's
    6240734250 on #436). None when it declares none; any failure keeps its category."""
    purpose = "read the declared core.worktree"
    result = _git_result(
        root,
        [
            "config",
            "--no-includes",
            "--null",
            "--show-scope",
            "--get-all",
            "core.worktree",
        ],
        timeout=_budget_left(root, end, timeout, purpose),
        purpose=purpose,
    )
    # Git's exit 1 with nothing written: no value in any scope.
    if result.returncode == 1 and not result.stdout and not result.stderr:
        return None
    fields = _git_checked(result, root, purpose).split(b"\0")
    # NUL-terminated scope and value pairs: a value cannot hold a NUL.
    if fields[-1] or len(fields) % 2 == 0:
        raise RepositoryScopeError(
            f"Git's core.worktree answer in {root} is not scope and value pairs",
            category="GIT_FAILED",
        )
    declared = [
        value
        for scope, value in zip(fields[:-1:2], fields[1:-1:2], strict=True)
        if scope in (b"local", b"worktree")
    ]
    return os.fsdecode(declared[-1]) if declared else None


def candidate_paths(
    repository_root: Path, *, timeout: float | None = None
) -> list[Path]:
    """Return the declared candidate paths without scanning local state.

    An optional `timeout`, in seconds, bounds the Git enumeration; past it the
    enumeration is refused as GIT_TIMEOUT. The packaged manifest is a local file
    read and takes none. Without one, nothing changes for existing callers.
    """

    root = repository_root.resolve()
    # One budget for the identity check and the enumeration: the enumeration gets
    # only what is left, and none once it is spent (the Router's I-b on #436).
    end = None if timeout is None else time.monotonic() + timeout
    # The identity check gets what is left of that one budget too, never a fresh one
    # (Codex on #436).
    if has_git_metadata(root, timeout=None if end is None else end - time.monotonic()):
        return _git_candidate_paths(
            root,
            timeout=_budget_left(
                root, end, timeout, "enumerate Git-tracked candidate files"
            ),
        )

    manifest = root / SOURCE_MANIFEST
    try:
        manifest.lstat()
    except FileNotFoundError:
        raise RepositoryScopeError(
            f"{root} has neither Git metadata nor {SOURCE_MANIFEST}",
            category="MANIFEST_MISSING",
        ) from None
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot inspect packaged source manifest {manifest}: {exc}",
            category="MANIFEST_IO",
        ) from exc
    return _manifest_candidate_paths(root)


def _read_candidate_text(root: Path, relative: Path) -> str | None:
    if relative.is_absolute() or ".." in relative.parts:
        raise RepositoryScopeError(
            f"candidate source contains an unsafe candidate path: {relative}",
            category="UNSAFE_PATH",
        )

    current = root
    for part in relative.parts[:-1]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except OSError:
            return None
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            return None

    path = root / relative
    try:
        mode = path.lstat().st_mode
    except OSError:
        return None

    if stat.S_ISLNK(mode):
        try:
            return os.readlink(path)
        except OSError:
            return None
    if not stat.S_ISREG(mode):
        return None

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        with os.fdopen(descriptor, "rb") as candidate:
            content = candidate.read()
    except OSError:
        return None

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def find_text_matches(
    repository_root: Path,
    patterns: Mapping[str, re.Pattern[str]],
) -> list[str]:
    """Find patterns only in the declared repository or packaged candidate."""

    root = repository_root.resolve()
    findings: list[str] = []
    for relative in candidate_paths(root):
        body = _read_candidate_text(root, relative)
        if body is None:
            continue
        for label, pattern in patterns.items():
            if pattern.search(body):
                findings.append(f"{relative.as_posix()}: {label}")
    return findings
