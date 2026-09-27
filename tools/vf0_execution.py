"""Private bounded execution primitives for VF0 evidence observations.

This module deliberately cannot authenticate evidence, admit a producer, issue a
preparation receipt, publish a candidate, or activate VF0.  It materializes an
explicit immutable Git subject plus an admitted tests-only evidence delta, runs
that material through a caller-selected runtime backend, and returns only bounded
untrusted execution observations.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import signal
import stat
import subprocess  # nosec B404 -- intentional bounded list-argv execution boundary
import tempfile
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Protocol, cast

_GIT_SHA1_RE = re.compile(r"[0-9a-f]{40}")
_DOCKER_ID_RE = re.compile(r"[0-9a-f]{64}")
_IMAGE_RE = re.compile(r"(?:[a-z0-9][a-z0-9._/-]*@)?sha256:[0-9a-f]{64}")
_MAX_SUBJECT_BYTES = 64 * 1024 * 1024
_MAX_FILE_BYTES = 32 * 1024 * 1024
_MAX_SUBJECT_FILES = 4096
_MAX_SUBJECT_TREE_LISTING_BYTES = 32 * 1024 * 1024
_MAX_SUBJECT_PATH_BYTES = 4 * 1024
_MAX_SUBJECT_PATH_COMPONENTS = 256
_MAX_EVIDENCE_FILES = 32
_MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
_MAX_EVIDENCE_PATH_BYTES = 4 * 1024
_MAX_EVIDENCE_PATH_COMPONENTS = 256
_MAX_COMMAND_ARGS = 256
_MAX_COMMAND_BYTES = 64 * 1024
_MAX_SNAPSHOT_ENTRIES = 65_536
_MAX_SNAPSHOT_DEPTH = 256
_MAX_SNAPSHOT_TOTAL_PATH_BYTES = _MAX_SUBJECT_TREE_LISTING_BYTES
_SNAPSHOT_READ_BYTES = 64 * 1024
_OPEN_ACCEPTS_DIR_FD = os.open in os.supports_dir_fd
_STAT_ACCEPTS_DIR_FD = os.stat in os.supports_dir_fd
_STAT_ACCEPTS_NOFOLLOW = os.stat in os.supports_follow_symlinks
_SCANDIR_ACCEPTS_FILE_DESCRIPTOR = os.scandir in os.supports_fd
_LOCAL_CONTAINMENT_EXECUTABLE = "/usr/bin/unshare"
_LOCAL_CONTAINMENT_WRAPPER_EXECUTABLE = "/bin/sh"
_LOCAL_CONTAINMENT_READY_SENTINEL = b"\x1eGNOSTOA_LOCAL_READY_V1\x1f"
_LOCAL_CONTAINMENT_WRAPPER_SOURCE = (
    'printf "\\036GNOSTOA_LOCAL_READY_V1\\037" >&2; exec "$@"'
)
_LOCAL_CONTAINMENT_WRAPPER_ARG0 = "gnostoa-local-ready"
_CONTAINER_TMP = "/tmp"  # nosec B108 -- isolated container tmpfs, never a host temp path
_CONTAINER_CLEANUP_LABEL = "gnostoa.vf0.cleanup-token"
_OCI_WRAPPER_EXECUTABLE = "/usr/local/bin/python3"
_OCI_EXIT_SENTINEL_PREFIX = b"\x1eGNOSTOA_VF0_EXIT_V1:"
_OCI_EXIT_SENTINEL_SUFFIX = b"\x1f"
_OCI_EXIT_TRAILER_MAX = (
    len(_OCI_EXIT_SENTINEL_PREFIX) + 3 + len(_OCI_EXIT_SENTINEL_SUFFIX)
)
_OCI_WRAPPER_SOURCE = (
    "import os,subprocess,sys\n"
    "try:\n"
    "    process=subprocess.Popen(sys.argv[1:])\n"
    "    code=process.wait()\n"
    "except FileNotFoundError:\n"
    "    code=127\n"
    "except PermissionError:\n"
    "    code=126\n"
    "code=128-code if code < 0 else code\n"
    "os.write(2,b'\x1eGNOSTOA_VF0_EXIT_V1:'+str(code).encode('ascii')+b'\x1f')\n"
    "raise SystemExit(code)\n"
)
_UNCERTAIN_CREATE_SETTLE_SECONDS = 2.0
_UNCERTAIN_CREATE_POLL_SECONDS = 0.1
_UNCERTAIN_REMOVE_SETTLE_SECONDS = 2.0
_UNCERTAIN_REMOVE_POLL_SECONDS = 0.1
_CLEAN_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/nonexistent",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
}
_GIT_ENV = {**_CLEAN_ENV, "GIT_NO_LAZY_FETCH": "1"}


class ExecutionRejected(RuntimeError):
    """Stable fail-closed refusal for the private execution boundary."""


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise ExecutionRejected(reason)


def _environment_map(value: object, reason: str) -> dict[str, str]:
    if value is None:
        return {}
    _need(type(value) is list, reason)
    environment: dict[str, str] = {}
    for item in cast(list[object], value):
        _need(type(item) is str and "=" in item and "\0" not in item, reason)
        key, value = cast(str, item).split("=", 1)
        _need(bool(key) and key not in environment, reason)
        environment[key] = value
    return environment


def _container_environment(subject: GitSubject) -> dict[str, str]:
    return {
        "HOME": _CONTAINER_TMP,
        "PYTHONDONTWRITEBYTECODE": "1",
        "KNOWLEDGE_KIT_ROOT": "/workspace",
        "KNOWLEDGE_KIT_REVISION": subject.commit,
        "PYTHONPATH": "/workspace",
    }


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _identity_digest(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _git_sha1(value: str, reason: str) -> str:
    _need(type(value) is str and _GIT_SHA1_RE.fullmatch(value) is not None, reason)
    return value


def _evidence_path(value: str) -> str:
    _need(isinstance(value, str) and bool(value), "EVIDENCE_PATH")
    _need(len(value) <= _MAX_EVIDENCE_PATH_BYTES, "EVIDENCE_PATH_BOUND")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ExecutionRejected("EVIDENCE_PATH") from exc
    _need(len(encoded) <= _MAX_EVIDENCE_PATH_BYTES, "EVIDENCE_PATH_BOUND")
    _need(
        value.count("/") + 1 <= _MAX_EVIDENCE_PATH_COMPONENTS,
        "EVIDENCE_PATH_COMPONENT_BOUND",
    )
    _need("\\" not in value and "\0" not in value, "EVIDENCE_PATH")
    raw_parts = value.split("/")
    _need(all(part not in {"", ".", ".."} for part in raw_parts), "EVIDENCE_PATH")
    _need(all(part.casefold() != ".git" for part in raw_parts), "EVIDENCE_PATH")
    path = PurePosixPath(value)
    _need(not path.is_absolute(), "EVIDENCE_PATH")
    _need(
        bool(path.parts) and path.parts[0] == "tests" and len(path.parts) > 1,
        "EVIDENCE_SCOPE",
    )
    return path.as_posix()


@dataclass(frozen=True)
class GitSubject:
    """Exact immutable subject identity; no process-global default is permitted."""

    commit: str
    tree: str

    def __post_init__(self) -> None:
        _git_sha1(self.commit, "SUBJECT_COMMIT")
        _git_sha1(self.tree, "SUBJECT_TREE")


@dataclass(frozen=True)
class EvidenceFile:
    """One admitted tests-only evidence file overlaid on the immutable subject."""

    path: str
    content: bytes
    mode: str = "100644"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _evidence_path(self.path))
        _need(
            type(self.mode) is str and self.mode in {"100644", "100755"},
            "EVIDENCE_MODE",
        )
        raw_content = cast(object, self.content)
        if not isinstance(raw_content, (bytes, bytearray, memoryview)):
            raise ExecutionRejected("EVIDENCE_CONTENT")
        content = bytes(raw_content)
        _need(len(content) <= _MAX_EVIDENCE_BYTES, "EVIDENCE_FILE_BOUND")
        object.__setattr__(self, "content", content)


@dataclass(frozen=True)
class ExecutionLimits:
    """Local observation limits and OCI resource limits."""

    timeout_seconds: float = 5.0
    output_bytes: int = 65_536
    memory_bytes: int = 256 * 1024 * 1024
    cpus: float = 0.5
    pids: int = 32
    tmpfs_bytes: int = 64 * 1024 * 1024

    def __post_init__(self) -> None:
        _need(type(self.timeout_seconds) in {int, float}, "TIMEOUT_BOUND")
        _need(0.05 <= self.timeout_seconds <= 300.0, "TIMEOUT_BOUND")
        _need(type(self.output_bytes) is int, "OUTPUT_BOUND")
        _need(1 <= self.output_bytes <= 4 * 1024 * 1024, "OUTPUT_BOUND")
        _need(type(self.memory_bytes) is int, "MEMORY_BOUND")
        _need(
            32 * 1024 * 1024 <= self.memory_bytes <= 4 * 1024 * 1024 * 1024,
            "MEMORY_BOUND",
        )
        _need(type(self.cpus) in {int, float}, "CPU_BOUND")
        _need(0.1 <= self.cpus <= 8.0, "CPU_BOUND")
        _need(type(self.pids) is int, "PIDS_BOUND")
        _need(8 <= self.pids <= 4096, "PIDS_BOUND")
        _need(type(self.tmpfs_bytes) is int, "TMPFS_BOUND")
        _need(1 * 1024 * 1024 <= self.tmpfs_bytes <= 1024 * 1024 * 1024, "TMPFS_BOUND")


@dataclass(frozen=True)
class UntrustedCapture:
    """Bounded child bytes.  Nothing in this object carries authority."""

    termination: str
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    observed_bytes_at_least: int

    def __post_init__(self) -> None:
        _need(
            self.termination in {"completed", "timeout", "output_limit"},
            "CAPTURE_TERMINATION",
        )
        if self.termination == "completed":
            _need(isinstance(self.exit_code, int), "CAPTURE_EXIT")
        else:
            _need(self.exit_code is None, "CAPTURE_EXIT")
        _need(
            self.observed_bytes_at_least >= len(self.stdout) + len(self.stderr),
            "CAPTURE_BYTES",
        )

    @property
    def truncated(self) -> bool:
        return self.termination == "output_limit"


@dataclass(frozen=True)
class ExecutionObservation:
    """Provider-neutral observation with conservative runtime-immutability signaling.

    ``subject_unchanged`` is true only for the exact built-in Docker backend,
    which enforces subject immutability throughout execution, and when the
    before/after manifests also match. Snapshot equality alone is insufficient.

    Backend/runtime identities are emitted only for exact controller-owned built-in
    backends. Custom protocol implementations remain useful as conformance doubles
    but carry ``None`` identities and cannot claim a bound execution runtime.
    """

    subject: GitSubject
    evidence_sha256: tuple[tuple[str, str], ...]
    command_sha256: str
    limits_sha256: str
    backend_identity: str | None
    runtime_identity: str | None
    before_manifest_sha256: str
    after_manifest_sha256: str
    capture: UntrustedCapture
    subject_unchanged: bool


class ExecutionBackend(Protocol):
    def run(
        self,
        root: Path,
        command: Sequence[str],
        limits: ExecutionLimits,
        *,
        subject: GitSubject,
    ) -> UntrustedCapture: ...


@dataclass(frozen=True)
class _MaterialFile:
    mode: str
    sha256: str
    size: int


def _trusted_git_argv(repo: Path, *args: str) -> list[str]:
    return ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args]


def _trusted_git(repo: Path, *args: str) -> bytes:
    try:
        # Fixed /usr/bin/git, list argv, scrubbed env, no shell: intentional audit boundary.
        result = subprocess.run(  # nosec B603  # nosemgrep
            _trusted_git_argv(repo, *args),
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            env=_GIT_ENV,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutionRejected("GIT_COMMAND_FAILED") from exc
    _need(result.returncode == 0, "GIT_COMMAND_FAILED")
    return result.stdout


def _trusted_git_tree_entries(repo: Path, commit: str) -> list[bytes]:
    """Read a bounded Git tree listing without buffering unbounded provider output."""

    try:
        with tempfile.TemporaryFile() as stderr:
            # Fixed /usr/bin/git, list argv, scrubbed env, no shell: intentional audit boundary.
            process = subprocess.Popen(  # nosec B603  # nosemgrep
                _trusted_git_argv(repo, "ls-tree", "-rzl", "--full-tree", commit),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=stderr,
                env=_GIT_ENV,
            )
            if process.stdout is None:
                process.kill()
                process.wait()
                raise ExecutionRejected("GIT_COMMAND_FAILED")

            selector: selectors.BaseSelector | None = None
            deadline = time.monotonic() + 30.0
            pending = bytearray()
            entries: list[bytes] = []
            observed_bytes = 0
            try:
                selector = selectors.DefaultSelector()
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired("/usr/bin/git ls-tree", 30)
                    events = selector.select(remaining)
                    if not events:
                        raise subprocess.TimeoutExpired("/usr/bin/git ls-tree", 30)
                    for key, _ in events:
                        chunk = os.read(key.fd, 65_536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        observed_bytes += len(chunk)
                        _need(
                            observed_bytes <= _MAX_SUBJECT_TREE_LISTING_BYTES,
                            "SUBJECT_TREE_BOUND",
                        )
                        pending.extend(chunk)
                        while True:
                            end = pending.find(0)
                            if end < 0:
                                break
                            entry = bytes(pending[:end])
                            del pending[: end + 1]
                            if not entry:
                                continue
                            _need(
                                len(entries) < _MAX_SUBJECT_FILES,
                                "SUBJECT_FILE_COUNT",
                            )
                            entries.append(entry)

                remaining = max(0.0, deadline - time.monotonic())
                process.wait(timeout=remaining)
            except Exception:
                if process.poll() is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                process.wait()
                raise
            finally:
                if selector is not None:
                    selector.close()
                process.stdout.close()

            _need(process.returncode == 0, "GIT_COMMAND_FAILED")
            _need(not pending, "SUBJECT_TREE_ENTRY")
            return entries
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExecutionRejected("GIT_COMMAND_FAILED") from exc


def _write_git_blob(
    repo: Path, oid: str, destination: Path, expected_size: int
) -> bytes:
    """Materialize one Git blob directly, then independently verify its object id."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(destination, flags, 0o600)
    except OSError as exc:
        raise ExecutionRejected("SUBJECT_DESTINATION") from exc
    try:
        with os.fdopen(descriptor, "wb") as output:
            try:
                # Fixed /usr/bin/git object read, list argv, scrubbed env, no shell.
                result = subprocess.run(  # nosec B603  # nosemgrep
                    _trusted_git_argv(repo, "cat-file", "blob", oid),
                    check=False,
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    env=_GIT_ENV,
                    timeout=30,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ExecutionRejected("GIT_COMMAND_FAILED") from exc
        _need(result.returncode == 0, "GIT_COMMAND_FAILED")
        _need(destination.stat().st_size == expected_size, "SUBJECT_BLOB_MISMATCH")
        observed_oid = (
            _trusted_git(repo, "hash-object", "--no-filters", "--", str(destination))
            .decode("ascii")
            .strip()
        )
        _need(observed_oid == oid, "SUBJECT_BLOB_MISMATCH")
        return destination.read_bytes()
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _normalize_subject_directory(path: Path, *, exist_ok: bool) -> None:
    """Create/normalize one controller-owned subject directory as traversable."""

    try:
        path.mkdir(mode=0o755, parents=False, exist_ok=exist_ok)
        mode = path.lstat().st_mode
        if not stat.S_ISDIR(mode):
            raise ExecutionRejected("SUBJECT_DIRECTORY")
        path.chmod(0o755)
    except OSError as exc:
        raise ExecutionRejected("SUBJECT_DIRECTORY") from exc


def _normalize_subject_parents(root: Path, destination: Path) -> None:
    """Normalize every controller-created parent below the materialization root."""

    try:
        relative = destination.relative_to(root)
    except ValueError as exc:
        raise ExecutionRejected("SUBJECT_PATH") from exc
    current = root
    for part in relative.parts[:-1]:
        current /= part
        _normalize_subject_directory(current, exist_ok=True)


def _repo_root(repo: Path) -> Path:
    try:
        resolved = repo.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExecutionRejected("REPOSITORY_ROOT") from exc
    top_value = _trusted_git(resolved, "rev-parse", "--show-toplevel").removesuffix(
        b"\n"
    )
    try:
        top = Path(os.fsdecode(top_value)).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ExecutionRejected("REPOSITORY_ROOT") from exc
    _need(top == resolved, "REPOSITORY_ROOT")
    return resolved


def _materialize_subject(
    repo: Path, subject: GitSubject, target: Path
) -> dict[str, _MaterialFile]:
    root = _repo_root(repo)
    commit = (
        _trusted_git(root, "rev-parse", "--verify", f"{subject.commit}^{{commit}}")
        .decode()
        .strip()
    )
    tree = (
        _trusted_git(root, "rev-parse", "--verify", f"{subject.commit}^{{tree}}")
        .decode()
        .strip()
    )
    _need(commit == subject.commit, "SUBJECT_COMMIT")
    _need(tree == subject.tree, "SUBJECT_TREE")

    entries = _trusted_git_tree_entries(root, subject.commit)
    planned: list[tuple[str, str, str, int]] = []
    planned_names: set[str] = set()
    planned_directories: set[tuple[str, ...]] = set()
    total = 0
    for entry in entries:
        try:
            meta, raw_name = entry.split(b"\t", 1)
            mode, kind, oid, raw_size = meta.decode("ascii").split()
            _need(len(raw_name) <= _MAX_SUBJECT_PATH_BYTES, "SUBJECT_PATH_BOUND")
            _need(
                raw_name.count(b"/") + 1 <= _MAX_SUBJECT_PATH_COMPONENTS,
                "SUBJECT_PATH_COMPONENT_BOUND",
            )
            name = raw_name.decode("utf-8")
            size = int(raw_size)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExecutionRejected("SUBJECT_TREE_ENTRY") from exc
        _need(mode in {"100644", "100755"} and kind == "blob", "SUBJECT_FILE_TYPE")
        path = PurePosixPath(name)
        _need(not path.is_absolute() and ".." not in path.parts, "SUBJECT_PATH")
        _need(all(part.casefold() != ".git" for part in path.parts), "SUBJECT_PATH")
        _need(name not in planned_names, "SUBJECT_PATH_DUPLICATE")
        _need(0 <= size <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
        total += size
        _need(total <= _MAX_SUBJECT_BYTES, "SUBJECT_TOTAL_BOUND")
        for depth in range(1, len(path.parts)):
            planned_directories.add(tuple(path.parts[:depth]))
        planned.append((name, mode, oid, size))
        planned_names.add(name)
        _need(
            len(planned_directories) + len(planned) <= _MAX_SNAPSHOT_ENTRIES,
            "SUBJECT_ENTRY_BOUND",
        )

    expected: dict[str, _MaterialFile] = {}
    _normalize_subject_directory(target, exist_ok=False)
    for name, mode, oid, size in planned:
        destination = target / name
        _normalize_subject_parents(target, destination)
        payload = _write_git_blob(root, oid, destination, size)
        destination.chmod(0o755 if mode == "100755" else 0o644)
        expected[name] = _MaterialFile(mode=mode, sha256=_sha256(payload), size=size)
    return expected


def _directory_mode(mode: int) -> str:
    return f"{stat.S_IMODE(mode):04o}"


def _file_mode(mode: int) -> str:
    return f"{stat.S_IFREG | stat.S_IMODE(mode):06o}"


def _same_snapshot_stat(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
        and stat.S_IMODE(left.st_mode) == stat.S_IMODE(right.st_mode)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _snapshot(root: Path) -> tuple[dict[str, _MaterialFile], dict[str, str]]:
    files: dict[str, _MaterialFile] = {}
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    nofollow_flag = getattr(os, "O_NOFOLLOW", 0)
    nonblock_flag = getattr(os, "O_NONBLOCK", 0)
    _need(
        directory_flag != 0
        and nofollow_flag != 0
        and _OPEN_ACCEPTS_DIR_FD
        and _STAT_ACCEPTS_DIR_FD
        and _STAT_ACCEPTS_NOFOLLOW
        and _SCANDIR_ACCEPTS_FILE_DESCRIPTOR,
        "SUBJECT_SNAPSHOT",
    )
    directory_flags = os.O_RDONLY | directory_flag | nofollow_flag
    file_flags = os.O_RDONLY | nofollow_flag | nonblock_flag
    try:
        root_fd = os.open(root, directory_flags)
    except OSError as exc:
        raise ExecutionRejected("SUBJECT_SNAPSHOT") from exc

    try:
        root_metadata = os.fstat(root_fd)
        _need(stat.S_ISDIR(root_metadata.st_mode), "SUBJECT_SNAPSHOT")
        directories = {".": _directory_mode(root_metadata.st_mode)}
        total = 0
        observed_entries = 0
        total_path_bytes = 0

        def walk(directory_fd: int, prefix: str, depth: int, prefix_bytes: int) -> None:
            nonlocal total, observed_entries, total_path_bytes
            before_directory = os.fstat(directory_fd)
            child_directories: list[tuple[str, str, int, int, os.stat_result]] = []
            with os.scandir(directory_fd) as entries:
                for entry in entries:
                    observed_entries += 1
                    _need(
                        observed_entries <= _MAX_SNAPSHOT_ENTRIES,
                        "SUBJECT_ENTRY_BOUND",
                    )
                    child_name = entry.name
                    _need(
                        isinstance(child_name, str)
                        and child_name not in {"", ".", ".."},
                        "SUBJECT_SNAPSHOT",
                    )
                    try:
                        component_bytes = len(os.fsencode(child_name))
                    except UnicodeError as exc:
                        raise ExecutionRejected("SUBJECT_PATH") from exc
                    relative_bytes = (
                        prefix_bytes + (1 if prefix else 0) + component_bytes
                    )
                    _need(
                        relative_bytes <= _MAX_SUBJECT_PATH_BYTES,
                        "SUBJECT_PATH_BOUND",
                    )
                    total_path_bytes += relative_bytes
                    _need(
                        total_path_bytes <= _MAX_SNAPSHOT_TOTAL_PATH_BYTES,
                        "SUBJECT_PATH_TOTAL_BOUND",
                    )
                    relative = f"{prefix}/{child_name}" if prefix else child_name
                    child_depth = depth + 1
                    _need(child_depth <= _MAX_SNAPSHOT_DEPTH, "SUBJECT_PATH_BOUND")
                    metadata = os.stat(
                        child_name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    mode = metadata.st_mode
                    _need(not stat.S_ISLNK(mode), "SUBJECT_SYMLINK")

                    if stat.S_ISDIR(mode):
                        child_directories.append(
                            (
                                child_name,
                                relative,
                                child_depth,
                                relative_bytes,
                                metadata,
                            )
                        )
                        continue

                    _need(stat.S_ISREG(mode), "SUBJECT_SPECIAL_FILE")
                    _need(metadata.st_size <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
                    file_fd = os.open(
                        child_name,
                        file_flags,
                        dir_fd=directory_fd,
                    )
                    try:
                        opened = os.fstat(file_fd)
                        _need(
                            stat.S_ISREG(opened.st_mode)
                            and _same_snapshot_stat(metadata, opened),
                            "SUBJECT_SNAPSHOT",
                        )
                        digest = hashlib.sha256()
                        file_size = 0
                        while True:
                            chunk = os.read(
                                file_fd,
                                min(
                                    _SNAPSHOT_READ_BYTES,
                                    _MAX_FILE_BYTES + 1 - file_size,
                                ),
                            )
                            if not chunk:
                                break
                            file_size += len(chunk)
                            _need(file_size <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
                            total += len(chunk)
                            _need(
                                total <= _MAX_SUBJECT_BYTES + _MAX_EVIDENCE_BYTES,
                                "SUBJECT_TOTAL_BOUND",
                            )
                            digest.update(chunk)
                        after = os.fstat(file_fd)
                        current = os.stat(
                            child_name,
                            dir_fd=directory_fd,
                            follow_symlinks=False,
                        )
                        _need(
                            file_size == opened.st_size
                            and _same_snapshot_stat(opened, after)
                            and _same_snapshot_stat(opened, current),
                            "SUBJECT_SNAPSHOT",
                        )
                        files[relative] = _MaterialFile(
                            mode=_file_mode(opened.st_mode),
                            sha256=digest.hexdigest(),
                            size=file_size,
                        )
                    finally:
                        os.close(file_fd)

            for (
                child_name,
                relative,
                child_depth,
                relative_bytes,
                metadata,
            ) in child_directories:
                child_fd = os.open(
                    child_name,
                    directory_flags,
                    dir_fd=directory_fd,
                )
                try:
                    opened = os.fstat(child_fd)
                    _need(
                        stat.S_ISDIR(opened.st_mode)
                        and _same_snapshot_stat(metadata, opened),
                        "SUBJECT_SNAPSHOT",
                    )
                    directories[relative] = _directory_mode(opened.st_mode)
                    walk(child_fd, relative, child_depth, relative_bytes)
                    after = os.fstat(child_fd)
                    current = os.stat(
                        child_name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    _need(
                        _same_snapshot_stat(opened, after)
                        and _same_snapshot_stat(opened, current),
                        "SUBJECT_SNAPSHOT",
                    )
                finally:
                    os.close(child_fd)

            after_directory = os.fstat(directory_fd)
            _need(
                _same_snapshot_stat(before_directory, after_directory),
                "SUBJECT_SNAPSHOT",
            )

        walk(root_fd, "", 0, 0)
        current_root = os.stat(root, follow_symlinks=False)
        _need(_same_snapshot_stat(root_metadata, current_root), "SUBJECT_SNAPSHOT")
    except (OSError, NotImplementedError, TypeError) as exc:
        raise ExecutionRejected("SUBJECT_SNAPSHOT") from exc
    finally:
        try:
            os.close(root_fd)
        except OSError as exc:
            raise ExecutionRejected("SUBJECT_SNAPSHOT") from exc
    return files, directories


def _manifest_digest(
    files: dict[str, _MaterialFile], directories: dict[str, str]
) -> str:
    serial = {
        "directories": dict(sorted(directories.items())),
        "files": {
            path: {"mode": item.mode, "sha256": item.sha256, "size": item.size}
            for path, item in sorted(files.items())
        },
    }
    return _sha256(_canonical(serial))


def _overlay_evidence(
    root: Path,
    baseline: dict[str, _MaterialFile],
    evidence: Sequence[EvidenceFile],
) -> dict[str, _MaterialFile]:
    _need(1 <= len(evidence) <= _MAX_EVIDENCE_FILES, "EVIDENCE_COUNT")
    expected = dict(baseline)
    observed_paths: set[str] = set()
    total = 0
    for item in evidence:
        _need(item.path not in observed_paths, "EVIDENCE_DUPLICATE")
        observed_paths.add(item.path)
        total += len(item.content)
        _need(total <= _MAX_EVIDENCE_BYTES, "EVIDENCE_TOTAL_BOUND")
        destination = root.joinpath(*PurePosixPath(item.path).parts)
        _normalize_subject_parents(root, destination)
        try:
            existing_mode = destination.lstat().st_mode
        except FileNotFoundError:
            existing_mode = None
        except OSError as exc:
            raise ExecutionRejected("EVIDENCE_DESTINATION") from exc
        if existing_mode is not None:
            _need(stat.S_ISREG(existing_mode), "EVIDENCE_DESTINATION")
        try:
            destination.write_bytes(item.content)
            destination.chmod(0o755 if item.mode == "100755" else 0o644)
        except OSError as exc:
            raise ExecutionRejected("EVIDENCE_DESTINATION") from exc
        expected[item.path] = _MaterialFile(
            mode=item.mode,
            sha256=_sha256(item.content),
            size=len(item.content),
        )
    return expected


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        if process.poll() is None:
            process.kill()


def _validate_command(argv: Sequence[str]) -> None:
    _need(
        bool(argv)
        and all(isinstance(part, str) and part and "\0" not in part for part in argv),
        "COMMAND",
    )
    executable = argv[0]
    path = PurePosixPath(executable)
    _need(
        path.is_absolute() or (executable.startswith("./") and ".." not in path.parts),
        "COMMAND_EXECUTABLE",
    )


def _wait_for_exit_without_reap(
    process: subprocess.Popen[bytes], deadline: float
) -> bool:
    """Observe leader exit while retaining its PID until group cleanup."""

    _need(
        hasattr(os, "waitid") and hasattr(os, "WNOWAIT"),
        "BACKEND_REAP_UNAVAILABLE",
    )
    options = os.WEXITED | os.WNOHANG | os.WNOWAIT
    while True:
        try:
            result = os.waitid(os.P_PID, process.pid, options)
        except (ChildProcessError, OSError) as exc:
            raise ExecutionRejected("BACKEND_REAP_FAILED") from exc
        if result is not None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.01, remaining))


def _capture_process(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    limits: ExecutionLimits,
    output_headroom_bytes: int = 0,
    startup_sentinel: bytes | None = None,
) -> UntrustedCapture:
    _validate_command(argv)
    _need(
        0 <= output_headroom_bytes <= _OCI_EXIT_TRAILER_MAX,
        "OUTPUT_HEADROOM_BOUND",
    )
    if startup_sentinel is not None:
        _need(1 <= len(startup_sentinel) <= 256, "STARTUP_SENTINEL_BOUND")
    capture_output_bytes = limits.output_bytes + output_headroom_bytes
    try:
        # Intentional private execution primitive: validated list argv, no shell, scrubbed env.
        process = subprocess.Popen(  # nosec B603  # nosemgrep
            list(argv),
            cwd=str(cwd) if cwd is not None else None,
            env=_CLEAN_ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        raise ExecutionRejected("BACKEND_START_FAILED") from exc
    process_stdout = process.stdout
    process_stderr = process.stderr
    selector: selectors.BaseSelector | None = None
    stdout = bytearray()
    stderr = bytearray()
    observed = 0
    termination = "completed"
    deadline = time.monotonic() + limits.timeout_seconds
    try:
        try:
            if process_stdout is None or process_stderr is None:
                raise ExecutionRejected("BACKEND_PIPES")
            selector = selectors.DefaultSelector()
            if startup_sentinel is not None:
                selector.register(process_stderr, selectors.EVENT_READ)
                startup = bytearray()
                while len(startup) < len(startup_sentinel):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ExecutionRejected("BACKEND_STARTUP_HANDSHAKE")
                    events = selector.select(timeout=min(0.05, remaining))
                    if not events:
                        continue
                    try:
                        chunk = os.read(
                            process_stderr.fileno(),
                            len(startup_sentinel) - len(startup),
                        )
                    except OSError as exc:
                        raise ExecutionRejected("BACKEND_STARTUP_HANDSHAKE") from exc
                    if not chunk:
                        raise ExecutionRejected("BACKEND_STARTUP_HANDSHAKE")
                    startup.extend(chunk)
                    if not startup_sentinel.startswith(startup):
                        raise ExecutionRejected("BACKEND_STARTUP_HANDSHAKE")
                selector.unregister(process_stderr)
            selector.register(process_stdout, selectors.EVENT_READ, stdout)
            selector.register(process_stderr, selectors.EVENT_READ, stderr)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    termination = "timeout"
                    break
                for key, _ in selector.select(timeout=min(0.05, remaining)):
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    observed += len(chunk)
                    room = capture_output_bytes - len(stdout) - len(stderr)
                    if room > 0:
                        key.data.extend(chunk[:room])
                    if len(chunk) > room:
                        termination = "output_limit"
                        break
                if termination != "completed":
                    break
            if termination == "completed" and not _wait_for_exit_without_reap(
                process, deadline
            ):
                termination = "timeout"
        except OSError as exc:
            raise ExecutionRejected("BACKEND_CAPTURE_FAILED") from exc
    finally:
        # Everything after successful Popen is inside one owned-process cleanup
        # boundary. Selector construction/registration and stream processing may
        # fail, but no such failure may leave the session running or unreaped.
        _kill_process_group(process)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise ExecutionRejected("BACKEND_REAP_FAILED") from exc
        finally:
            if selector is not None:
                selector.close()
            if process_stdout is not None:
                process_stdout.close()
            if process_stderr is not None:
                process_stderr.close()
    exit_code = process.returncode if termination == "completed" else None
    return UntrustedCapture(
        termination=termination,
        exit_code=exit_code,
        stdout=bytes(stdout),
        stderr=bytes(stderr),
        observed_bytes_at_least=observed,
    )


def _local_containment_argv(command: Sequence[str]) -> list[str]:
    return [
        _LOCAL_CONTAINMENT_EXECUTABLE,
        "--user",
        "--map-current-user",
        "--pid",
        "--fork",
        "--kill-child",
        "--",
        *command,
    ]


def _local_containment_launch_argv(command: Sequence[str]) -> list[str]:
    return [
        *_local_containment_argv(()),
        _LOCAL_CONTAINMENT_WRAPPER_EXECUTABLE,
        "-c",
        _LOCAL_CONTAINMENT_WRAPPER_SOURCE,
        _LOCAL_CONTAINMENT_WRAPPER_ARG0,
        *command,
    ]


def _probe_local_containment(root: Path) -> None:
    _need(
        Path(_LOCAL_CONTAINMENT_EXECUTABLE).is_file()
        and os.access(_LOCAL_CONTAINMENT_EXECUTABLE, os.X_OK),
        "LOCAL_CONTAINMENT_UNAVAILABLE",
    )
    try:
        probe = _capture_process(
            _local_containment_argv(("/bin/true",)),
            cwd=root,
            limits=ExecutionLimits(timeout_seconds=5.0, output_bytes=8192),
        )
    except ExecutionRejected as exc:
        raise ExecutionRejected("LOCAL_CONTAINMENT_UNAVAILABLE") from exc
    _need(
        probe.termination == "completed" and probe.exit_code == 0,
        "LOCAL_CONTAINMENT_UNAVAILABLE",
    )


class SubprocessBackend:
    """Finite local backend with PID containment but no immutable subject mount."""

    def run(
        self,
        root: Path,
        command: Sequence[str],
        limits: ExecutionLimits,
        *,
        subject: GitSubject,
    ) -> UntrustedCapture:
        del subject
        _validate_command(command)
        _probe_local_containment(root)
        try:
            return _capture_process(
                _local_containment_launch_argv(command),
                cwd=root,
                limits=limits,
                startup_sentinel=_LOCAL_CONTAINMENT_READY_SENTINEL,
            )
        except ExecutionRejected as exc:
            if str(exc) in {"BACKEND_START_FAILED", "BACKEND_STARTUP_HANDSHAKE"}:
                raise ExecutionRejected("LOCAL_CONTAINMENT_UNAVAILABLE") from exc
            raise


@dataclass(frozen=True, eq=False)
class DockerBackend:
    """Linux/amd64 OCI specialization with a read-only, network-free subject."""

    image: str
    docker_executable: str = "/usr/bin/docker"

    def __post_init__(self) -> None:
        _need(_IMAGE_RE.fullmatch(self.image) is not None, "OCI_IMAGE_PIN")
        _need(self.docker_executable == "/usr/bin/docker", "DOCKER_EXECUTABLE")

    def _command(
        self, *args: str, timeout: float = 30
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            # Fixed /usr/bin/docker, list argv, scrubbed env, no shell: intentional audit boundary.
            return subprocess.run(  # nosec B603  # nosemgrep
                [self.docker_executable, *args],
                check=False,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                env=_CLEAN_ENV,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExecutionRejected("DOCKER_COMMAND_FAILED") from exc

    def _checked(self, *args: str, timeout: float = 30) -> bytes:
        result = self._command(*args, timeout=timeout)
        _need(result.returncode == 0, "DOCKER_COMMAND_FAILED")
        return result.stdout

    def _inspect_image(self) -> tuple[str, dict[str, str]]:
        try:
            spec = json.loads(self._checked("image", "inspect", self.image))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ExecutionRejected("OCI_IMAGE_INSPECT") from exc
        _need(
            isinstance(spec, list) and len(spec) == 1 and isinstance(spec[0], dict),
            "OCI_IMAGE_INSPECT",
        )
        if "@sha256:" in self.image:
            digests = spec[0].get("RepoDigests", [])
            _need(
                isinstance(digests, list) and self.image in digests,
                "OCI_IMAGE_IDENTITY",
            )
        else:
            _need(spec[0].get("Id") == self.image, "OCI_IMAGE_IDENTITY")
        image_id = spec[0].get("Id")
        _need(
            isinstance(image_id, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is not None,
            "OCI_IMAGE_IDENTITY",
        )
        _need(
            spec[0].get("Os") == "linux" and spec[0].get("Architecture") == "amd64",
            "OCI_IMAGE_PLATFORM",
        )
        image_config = spec[0].get("Config")
        _need(isinstance(image_config, dict), "OCI_IMAGE_INSPECT")
        image_environment = _environment_map(
            image_config.get("Env"), "OCI_IMAGE_INSPECT"
        )
        return cast(str, image_id), image_environment

    def _validate_container(
        self,
        container_id: str,
        root: Path,
        limits: ExecutionLimits,
        command: Sequence[str],
        cleanup_nonce: str,
        subject: GitSubject,
        image_id: str,
        image_environment: dict[str, str],
    ) -> None:
        try:
            raw = json.loads(self._checked("inspect", container_id))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ExecutionRejected("OCI_INSPECT") from exc
        _need(
            isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict),
            "OCI_INSPECT",
        )
        spec = raw[0]
        _need(spec.get("Image") == image_id, "OCI_IMAGE_IDENTITY")
        host = spec.get("HostConfig", {})
        config = spec.get("Config", {})
        mounts = spec.get("Mounts", [])
        _need(
            isinstance(host, dict)
            and isinstance(config, dict)
            and isinstance(mounts, list),
            "OCI_INSPECT",
        )
        _need(
            len(mounts) == 1
            and isinstance(mounts[0], dict)
            and mounts[0].get("Type") == "bind"
            and mounts[0].get("Source") == str(root)
            and mounts[0].get("Destination") == "/workspace"
            and mounts[0].get("RW") is False,
            "OCI_MOUNT_CONTRACT",
        )
        security = host.get("SecurityOpt") or []
        labels = config.get("Labels") or {}
        _need(isinstance(labels, dict), "OCI_INSPECT")
        expected_command = ["-I", "-c", _OCI_WRAPPER_SOURCE, *command]
        expected_tmpfs = f"rw,nosuid,nodev,noexec,mode=1777,size={limits.tmpfs_bytes}"
        _need(
            spec.get("Path") == _OCI_WRAPPER_EXECUTABLE
            and spec.get("Args") == expected_command
            and config.get("Entrypoint") == [_OCI_WRAPPER_EXECUTABLE]
            and config.get("Cmd") == expected_command
            and config.get("WorkingDir") == "/workspace"
            and host.get("Tmpfs") == {_CONTAINER_TMP: expected_tmpfs},
            "OCI_CONTAINER_CONFIG",
        )
        environment = _environment_map(config.get("Env"), "OCI_ENV_CONTRACT")
        expected_environment = dict(image_environment)
        expected_environment.update(_container_environment(subject))
        _need(
            environment == expected_environment,
            "OCI_ENV_CONTRACT",
        )
        _need(
            host.get("ReadonlyRootfs") is True
            and host.get("NetworkMode") == "none"
            and host.get("IpcMode") == "none"
            and host.get("Privileged") is False
            and host.get("CapDrop") == ["ALL"]
            and "no-new-privileges" in security
            and config.get("User") == "10001:10001"
            and labels.get(_CONTAINER_CLEANUP_LABEL) == cleanup_nonce
            and host.get("PidsLimit") == limits.pids
            and host.get("Memory") == limits.memory_bytes
            and host.get("MemorySwap") == limits.memory_bytes
            and host.get("NanoCpus") == round(limits.cpus * 1_000_000_000),
            "OCI_CONTRACT",
        )

    @staticmethod
    def _inspect_confirms_absence(
        result: subprocess.CompletedProcess[bytes], container_ref: str
    ) -> bool:
        """Recognize the target-bound missing-object result of Docker inspect."""

        expected = f"error: no such object: {container_ref}".encode("ascii")
        return (
            result.returncode != 0
            and result.stdout.strip() in {b"", b"[]"}
            and result.stderr.strip().lower() == expected
        )

    def _cleanup_presence(self, container_id: str, cleanup_nonce: str) -> bool | None:
        try:
            inspected = self._command("inspect", container_id, timeout=15)
        except ExecutionRejected:
            return None
        if inspected.returncode != 0:
            if self._inspect_confirms_absence(inspected, container_id):
                return False
            return None
        try:
            raw = json.loads(inspected.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ExecutionRejected("OCI_CLEANUP_UNVERIFIED") from exc
        _need(
            isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict),
            "OCI_CLEANUP_UNVERIFIED",
        )
        config = raw[0].get("Config", {})
        labels = config.get("Labels") if isinstance(config, dict) else None
        _need(
            isinstance(labels, dict)
            and labels.get(_CONTAINER_CLEANUP_LABEL) == cleanup_nonce,
            "OCI_CLEANUP_OWNERSHIP",
        )
        return True

    def _reconcile_uncertain_remove(
        self, container_id: str, cleanup_nonce: str
    ) -> None:
        deadline = time.monotonic() + _UNCERTAIN_REMOVE_SETTLE_SECONDS
        while True:
            presence = self._cleanup_presence(container_id, cleanup_nonce)
            if presence is False:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ExecutionRejected("OCI_CLEANUP_UNVERIFIED")
            if presence is True:
                try:
                    self._command(
                        "rm", "--force", "--volumes", container_id, timeout=15
                    )
                except ExecutionRejected:
                    pass
            time.sleep(min(_UNCERTAIN_REMOVE_POLL_SECONDS, remaining))

    def _remove_and_verify(self, container_id: str, cleanup_nonce: str) -> None:
        self._reconcile_uncertain_remove(container_id, cleanup_nonce)

    def _cleanup_uncertain_create(
        self,
        container_name: str,
        cleanup_nonce: str,
        *,
        completion_observed: bool = False,
    ) -> None:
        deadline = time.monotonic() + _UNCERTAIN_CREATE_SETTLE_SECONDS
        while True:
            try:
                inspected = self._command("inspect", container_name, timeout=15)
            except ExecutionRejected:
                inspected = None
            if inspected is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ExecutionRejected("OCI_CLEANUP_UNVERIFIED")
                time.sleep(min(_UNCERTAIN_CREATE_POLL_SECONDS, remaining))
                continue
            if inspected.returncode == 0:
                try:
                    raw = json.loads(inspected.stdout)
                except (json.JSONDecodeError, TypeError) as exc:
                    raise ExecutionRejected("OCI_CLEANUP_UNVERIFIED") from exc
                _need(
                    isinstance(raw, list)
                    and len(raw) == 1
                    and isinstance(raw[0], dict),
                    "OCI_CLEANUP_UNVERIFIED",
                )
                config = raw[0].get("Config", {})
                labels = config.get("Labels") if isinstance(config, dict) else None
                _need(
                    isinstance(labels, dict)
                    and labels.get(_CONTAINER_CLEANUP_LABEL) == cleanup_nonce,
                    "OCI_CLEANUP_OWNERSHIP",
                )
                self._remove_and_verify(container_name, cleanup_nonce)
                return
            _need(
                self._inspect_confirms_absence(inspected, container_name),
                "OCI_CLEANUP_UNVERIFIED",
            )
            if completion_observed:
                return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(_UNCERTAIN_CREATE_POLL_SECONDS, remaining))

    def run(
        self,
        root: Path,
        command: Sequence[str],
        limits: ExecutionLimits,
        *,
        subject: GitSubject,
    ) -> UntrustedCapture:
        _validate_command(command)
        image_id, image_environment = self._inspect_image()
        cleanup_nonce = uuid.uuid4().hex
        container_name = f"gnostoa-vf0-{cleanup_nonce}"
        controller_environment = _container_environment(subject)
        environment_arguments = [
            argument
            for key, value in controller_environment.items()
            for argument in ("--env", f"{key}={value}")
        ]
        create = [
            "create",
            "--platform",
            "linux/amd64",
            "--name",
            container_name,
            "--label",
            f"{_CONTAINER_CLEANUP_LABEL}={cleanup_nonce}",
            "--read-only",
            "--network",
            "none",
            "--ipc",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "10001:10001",
            "--memory",
            str(limits.memory_bytes),
            "--memory-swap",
            str(limits.memory_bytes),
            "--cpus",
            str(limits.cpus),
            "--pids-limit",
            str(limits.pids),
            "--log-driver",
            "none",
            "--tmpfs",
            f"{_CONTAINER_TMP}:rw,nosuid,nodev,noexec,mode=1777,size={limits.tmpfs_bytes}",
            *environment_arguments,
            "--mount",
            f"type=bind,source={root},target=/workspace,readonly",
            "--workdir",
            "/workspace",
            "--entrypoint",
            _OCI_WRAPPER_EXECUTABLE,
            image_id,
            "-I",
            "-c",
            _OCI_WRAPPER_SOURCE,
            *command,
        ]
        container_id: str | None = None
        container_validated = False
        try:
            observed_id = self._checked(*create).decode().strip().lower()
            _need(_DOCKER_ID_RE.fullmatch(observed_id) is not None, "OCI_CONTAINER_ID")
            container_id = observed_id
            self._validate_container(
                container_id,
                root,
                limits,
                command,
                cleanup_nonce,
                subject,
                image_id,
                image_environment,
            )
            container_validated = True
            capture = _capture_process(
                [self.docker_executable, "start", "--attach", container_id],
                cwd=None,
                limits=limits,
                output_headroom_bytes=_OCI_EXIT_TRAILER_MAX,
            )
            if capture.termination == "completed":
                capture = _unwrap_oci_completion(capture)
            capture = _enforce_output_limit(capture, limits.output_bytes)
            if capture.termination == "completed":
                try:
                    state = json.loads(
                        self._checked(
                            "inspect", "--format", "{{json .State}}", container_id
                        )
                    )
                except (json.JSONDecodeError, TypeError) as exc:
                    raise ExecutionRejected("OCI_EXIT_STATE") from exc
                _need(
                    isinstance(state, dict)
                    and state.get("Status") == "exited"
                    and state.get("Running") is False
                    and state.get("OOMKilled") is False,
                    "OCI_EXIT_STATE",
                )
                exit_code = state.get("ExitCode")
                _need(
                    isinstance(exit_code, int) and not isinstance(exit_code, bool),
                    "OCI_EXIT_STATE",
                )
                _need(capture.exit_code == exit_code, "OCI_EXIT_STATE")
            return capture
        finally:
            # _capture_process closes/reaps the attachment group before this point.
            # Even preflight/client failures still remove and independently verify
            # absence of the owned container.
            if container_id is None or not container_validated:
                self._cleanup_uncertain_create(container_name, cleanup_nonce)
            else:
                try:
                    self._remove_and_verify(container_id, cleanup_nonce)
                except ExecutionRejected as exc:
                    if str(exc) not in {
                        "OCI_CLEANUP_OWNERSHIP",
                        "OCI_CLEANUP_UNVERIFIED",
                    }:
                        raise
                    self._cleanup_uncertain_create(container_name, cleanup_nonce)
                else:
                    self._cleanup_uncertain_create(
                        container_name, cleanup_nonce, completion_observed=True
                    )


def _unwrap_oci_completion(capture: UntrustedCapture) -> UntrustedCapture:
    """Require and strip the trusted wrapper's unique final completion trailer."""

    if capture.termination != "completed":
        return capture
    stderr = capture.stderr
    _need(stderr.count(_OCI_EXIT_SENTINEL_PREFIX) == 1, "OCI_ATTACH_STATE")
    marker_start = stderr.find(_OCI_EXIT_SENTINEL_PREFIX)
    _need(
        marker_start >= 0 and stderr.endswith(_OCI_EXIT_SENTINEL_SUFFIX),
        "OCI_ATTACH_STATE",
    )
    raw_code = stderr[
        marker_start + len(_OCI_EXIT_SENTINEL_PREFIX) : -len(_OCI_EXIT_SENTINEL_SUFFIX)
    ]
    _need(1 <= len(raw_code) <= 3 and raw_code.isdigit(), "OCI_ATTACH_STATE")
    exit_code = int(raw_code)
    _need(0 <= exit_code <= 255, "OCI_ATTACH_STATE")
    _need(capture.exit_code in {0, exit_code}, "OCI_ATTACH_STATE")
    trailer_bytes = len(stderr) - marker_start
    _need(capture.observed_bytes_at_least >= trailer_bytes, "OCI_ATTACH_STATE")
    return replace(
        capture,
        exit_code=exit_code,
        stderr=stderr[:marker_start],
        observed_bytes_at_least=capture.observed_bytes_at_least - trailer_bytes,
    )


def _enforce_output_limit(
    capture: UntrustedCapture, output_bytes: int
) -> UntrustedCapture:
    """Apply the caller evidence-byte budget after trusted transport metadata."""

    _need(1 <= output_bytes <= 4 * 1024 * 1024, "OUTPUT_BOUND")
    retained_bytes = len(capture.stdout) + len(capture.stderr)
    if retained_bytes <= output_bytes:
        return capture
    stdout = capture.stdout[:output_bytes]
    stderr_room = output_bytes - len(stdout)
    stderr = capture.stderr[:stderr_room] if stderr_room > 0 else b""
    observed_bytes_at_least = capture.observed_bytes_at_least
    if capture.termination != "completed":
        observed_bytes_at_least = max(
            output_bytes + 1,
            observed_bytes_at_least - _OCI_EXIT_TRAILER_MAX,
        )
    return UntrustedCapture(
        termination="output_limit",
        exit_code=None,
        stdout=stdout,
        stderr=stderr,
        observed_bytes_at_least=max(output_bytes + 1, observed_bytes_at_least),
    )


def _limits_identity(limits: ExecutionLimits) -> str:
    return _identity_digest(
        {
            "timeout_seconds": limits.timeout_seconds,
            "output_bytes": limits.output_bytes,
            "memory_bytes": limits.memory_bytes,
            "cpus": limits.cpus,
            "pids": limits.pids,
            "tmpfs_bytes": limits.tmpfs_bytes,
        }
    )


def _backend_runtime_identities(
    backend: ExecutionBackend,
) -> tuple[str | None, str | None]:
    backend_type = type(backend)
    if backend_type is SubprocessBackend:
        return (
            "gnostoa-local-subprocess-v1",
            _identity_digest(
                {
                    "containment_executable": _LOCAL_CONTAINMENT_EXECUTABLE,
                    "wrapper_executable": _LOCAL_CONTAINMENT_WRAPPER_EXECUTABLE,
                    "wrapper_source": _LOCAL_CONTAINMENT_WRAPPER_SOURCE,
                }
            ),
        )
    if backend_type is DockerBackend:
        docker_backend = cast(DockerBackend, backend)
        return "gnostoa-docker-oci-v1", docker_backend.image
    return None, None


def _snapshot_evidence(
    evidence: Sequence[EvidenceFile],
) -> tuple[EvidenceFile, ...]:
    snapshot: list[EvidenceFile] = []
    observed_paths: set[str] = set()
    total_bytes = 0
    try:
        iterator = iter(evidence)
    except TypeError as exc:
        raise ExecutionRejected("EVIDENCE_CONTENT") from exc
    for index in range(_MAX_EVIDENCE_FILES + 1):
        try:
            item = next(iterator)
        except StopIteration:
            break
        _need(index < _MAX_EVIDENCE_FILES, "EVIDENCE_COUNT")
        _need(type(item) is EvidenceFile, "EVIDENCE_CONTENT")
        frozen = EvidenceFile(path=item.path, content=item.content, mode=item.mode)
        _need(frozen.path not in observed_paths, "EVIDENCE_DUPLICATE")
        observed_paths.add(frozen.path)
        total_bytes += len(frozen.content)
        _need(total_bytes <= _MAX_EVIDENCE_BYTES, "EVIDENCE_TOTAL_BOUND")
        snapshot.append(frozen)
    _need(1 <= len(snapshot) <= _MAX_EVIDENCE_FILES, "EVIDENCE_COUNT")
    return tuple(snapshot)


def _snapshot_command(command: Sequence[str]) -> tuple[str, ...]:
    snapshot: list[str] = []
    total_bytes = 0
    try:
        iterator = iter(command)
    except TypeError as exc:
        raise ExecutionRejected("COMMAND") from exc
    for index in range(_MAX_COMMAND_ARGS + 1):
        try:
            part = next(iterator)
        except StopIteration:
            break
        if index >= _MAX_COMMAND_ARGS:
            raise ExecutionRejected("COMMAND_COUNT_BOUND")
        _need(isinstance(part, str) and bool(part) and "\0" not in part, "COMMAND")
        try:
            encoded = part.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ExecutionRejected("COMMAND") from exc
        total_bytes += len(encoded)
        _need(total_bytes <= _MAX_COMMAND_BYTES, "COMMAND_BYTES_BOUND")
        snapshot.append(part)
    _need(bool(snapshot), "COMMAND")
    return tuple(snapshot)


def execute(
    repository: Path,
    subject: GitSubject,
    evidence: Sequence[EvidenceFile],
    command: Sequence[str],
    backend: ExecutionBackend,
    limits: ExecutionLimits | None = None,
) -> ExecutionObservation:
    """Execute one explicit subject and return only bounded untrusted observations."""

    chosen_limits = limits or ExecutionLimits()
    command_snapshot = _snapshot_command(command)
    evidence_snapshot = _snapshot_evidence(evidence)
    command_sha256 = _identity_digest(list(command_snapshot))
    limits_sha256 = _limits_identity(chosen_limits)
    backend_identity, runtime_identity = _backend_runtime_identities(backend)
    with tempfile.TemporaryDirectory(prefix="gnostoa-vf0-execution-") as temporary:
        temp = Path(temporary)
        root = temp / "subject"
        baseline = _materialize_subject(repository, subject, root)
        expected = _overlay_evidence(root, baseline, evidence_snapshot)
        before_files, before_directories = _snapshot(root)
        _need(before_files == expected, "SUBJECT_BEFORE_EXECUTION")
        before_digest = _manifest_digest(before_files, before_directories)
        capture = backend.run(root, command_snapshot, chosen_limits, subject=subject)
        after_files, after_directories = _snapshot(root)
        _need(after_files == expected, "SUBJECT_MUTATED")
        _need(after_directories == before_directories, "SUBJECT_MUTATED")
        after_digest = _manifest_digest(after_files, after_directories)
        _need(before_digest == after_digest, "SUBJECT_MUTATED")
        evidence_digests = tuple(
            sorted((item.path, _sha256(item.content)) for item in evidence_snapshot)
        )
        return ExecutionObservation(
            subject=subject,
            evidence_sha256=evidence_digests,
            command_sha256=command_sha256,
            limits_sha256=limits_sha256,
            backend_identity=backend_identity,
            runtime_identity=runtime_identity,
            before_manifest_sha256=before_digest,
            after_manifest_sha256=after_digest,
            capture=capture,
            subject_unchanged=(type(backend) is DockerBackend),
        )
