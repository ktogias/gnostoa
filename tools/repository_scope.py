from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import re
import stat
import subprocess


SOURCE_MANIFEST = ".gnostoa-source-files"


class RepositoryScopeError(RuntimeError):
    """Raised when the canonical repository candidate cannot be enumerated."""


def _decode_paths(encoded_paths: bytes, source: str) -> list[Path]:
    paths: list[Path] = []
    for encoded in encoded_paths.split(b"\0"):
        if not encoded:
            continue
        relative = Path(os.fsdecode(encoded))
        if (
            relative == Path(".")
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise RepositoryScopeError(
                f"{source} returned an unsafe candidate path: {relative}"
            )
        paths.append(relative)
    return sorted(set(paths), key=lambda path: path.as_posix())


def _git_candidate_paths(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root}",
                "-C",
                str(root),
                "ls-files",
                "--cached",
                "--deduplicate",
                "-z",
            ],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot enumerate Git-tracked candidate files in {root}: {exc}"
        ) from exc

    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RepositoryScopeError(
            message or f"cannot enumerate Git-tracked candidate files in {root}"
        )
    return _decode_paths(result.stdout, "Git")


def _manifest_candidate_paths(root: Path) -> list[Path]:
    manifest = root / SOURCE_MANIFEST
    try:
        mode = manifest.lstat().st_mode
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot read packaged source manifest {manifest}: {exc}"
        ) from exc
    if not stat.S_ISREG(mode):
        raise RepositoryScopeError(
            f"packaged source manifest is not a regular file: {manifest}"
        )

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(manifest, flags)
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot open packaged source manifest {manifest}: {exc}"
        ) from exc
    try:
        with os.fdopen(descriptor, "rb") as source:
            encoded_paths = source.read()
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot read packaged source manifest {manifest}: {exc}"
        ) from exc
    return _decode_paths(encoded_paths, "packaged source manifest")


def candidate_paths(repository_root: Path) -> list[Path]:
    """Return the declared candidate paths without scanning local state."""

    root = repository_root.resolve()
    git_metadata = root / ".git"
    try:
        git_metadata.lstat()
    except FileNotFoundError:
        git_metadata_exists = False
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot inspect Git metadata at {git_metadata}: {exc}"
        ) from exc
    else:
        git_metadata_exists = True

    if git_metadata_exists:
        return _git_candidate_paths(root)

    manifest = root / SOURCE_MANIFEST
    try:
        manifest.lstat()
    except FileNotFoundError:
        raise RepositoryScopeError(
            f"{root} has neither Git metadata nor {SOURCE_MANIFEST}"
        ) from None
    except OSError as exc:
        raise RepositoryScopeError(
            f"cannot inspect packaged source manifest {manifest}: {exc}"
        ) from exc
    return _manifest_candidate_paths(root)


def _read_candidate_text(root: Path, relative: Path) -> str | None:
    if relative.is_absolute() or ".." in relative.parts:
        raise RepositoryScopeError(
            f"candidate source contains an unsafe candidate path: {relative}"
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
