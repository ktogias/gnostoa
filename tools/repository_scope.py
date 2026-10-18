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


def _git_output(
    root: Path, arguments: list[str], *, timeout: float | None, purpose: str
) -> bytes:
    """One Git read of `root`, classified: GIT_TIMEOUT past `timeout`, GIT_IO when Git
    cannot run, and GIT_FAILED on a non-zero exit."""
    try:
        result = subprocess.run(
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

    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryScopeError(
            message or f"cannot {purpose} in {root}",
            category="GIT_FAILED",
        )
    return result.stdout


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
    is left of it, and a spent one starts no Git (Codex, the Router's I-b on #436)."""
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
    remaining = None if end is None else end - time.monotonic()
    if remaining is not None and remaining <= 0:
        raise RepositoryScopeError(
            f"cannot confirm the Git top level in {root} within {timeout} seconds",
            category="GIT_TIMEOUT",
        )
    output = _git_output(
        root,
        ["rev-parse", "--show-toplevel"],
        timeout=remaining,
        purpose="confirm the Git top level",
    )
    # Exactly Git's one terminator, so a root whose name ends in a newline keeps it
    # (CodeAnt on #436).
    top = os.fsdecode(output[:-1] if output.endswith(b"\n") else output)
    # Git's top level is absolute, so the root is resolved before the comparison
    # (cubic, the Router's I-b on #436).
    if not top or Path(top) != root.resolve():
        raise RepositoryScopeError(
            f"Git metadata at {git_metadata} belongs to another work tree",
            category="UNSAFE_PATH",
        )
    return True


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
        remaining = None if end is None else end - time.monotonic()
        if remaining is not None and remaining <= 0:
            raise RepositoryScopeError(
                f"cannot enumerate Git-tracked candidate files in {root} within "
                f"{timeout} seconds",
                category="GIT_TIMEOUT",
            )
        return _git_candidate_paths(root, timeout=remaining)

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
