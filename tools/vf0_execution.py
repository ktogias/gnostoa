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
_MAX_EVIDENCE_FILES = 32
_MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
_MAX_SNAPSHOT_ENTRIES = 65_536
_LOCAL_CONTAINMENT_EXECUTABLE = "/usr/bin/unshare"
_CONTAINER_TMP = "/tmp"  # nosec B108 -- isolated container tmpfs, never a host temp path
_CONTAINER_CLEANUP_LABEL = "gnostoa.vf0.cleanup-token"
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


class ExecutionRejected(RuntimeError):
    """Stable fail-closed refusal for the private execution boundary."""


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise ExecutionRejected(reason)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _git_sha1(value: str, reason: str) -> str:
    _need(_GIT_SHA1_RE.fullmatch(value) is not None, reason)
    return value


def _evidence_path(value: str) -> str:
    _need(bool(value) and "\\" not in value and "\0" not in value, "EVIDENCE_PATH")
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
        _need(self.mode in {"100644", "100755"}, "EVIDENCE_MODE")
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
        _need(0.05 <= self.timeout_seconds <= 300.0, "TIMEOUT_BOUND")
        _need(1 <= self.output_bytes <= 4 * 1024 * 1024, "OUTPUT_BOUND")
        _need(
            32 * 1024 * 1024 <= self.memory_bytes <= 4 * 1024 * 1024 * 1024,
            "MEMORY_BOUND",
        )
        _need(0.1 <= self.cpus <= 8.0, "CPU_BOUND")
        _need(8 <= self.pids <= 4096, "PIDS_BOUND")
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

    ``subject_unchanged`` is true only when the selected controller backend
    declares that it enforces subject immutability throughout execution and the
    before/after manifests also match. Snapshot equality alone is insufficient.
    """

    subject: GitSubject
    evidence_sha256: tuple[tuple[str, str], ...]
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
            env=_CLEAN_ENV,
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
                env=_CLEAN_ENV,
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
                    env=_CLEAN_ENV,
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
    resolved = repo.resolve(strict=True)
    top = Path(
        _trusted_git(resolved, "rev-parse", "--show-toplevel").decode().strip()
    ).resolve(strict=True)
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
    expected: dict[str, _MaterialFile] = {}
    total = 0
    _normalize_subject_directory(target, exist_ok=False)
    for entry in entries:
        try:
            meta, raw_name = entry.split(b"\t", 1)
            mode, kind, oid, raw_size = meta.decode("ascii").split()
            name = raw_name.decode("utf-8")
            size = int(raw_size)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExecutionRejected("SUBJECT_TREE_ENTRY") from exc
        _need(mode in {"100644", "100755"} and kind == "blob", "SUBJECT_FILE_TYPE")
        path = PurePosixPath(name)
        _need(not path.is_absolute() and ".." not in path.parts, "SUBJECT_PATH")
        _need(all(part.casefold() != ".git" for part in path.parts), "SUBJECT_PATH")
        _need(name not in expected, "SUBJECT_PATH_DUPLICATE")
        _need(0 <= size <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
        total += size
        _need(total <= _MAX_SUBJECT_BYTES, "SUBJECT_TOTAL_BOUND")
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


def _snapshot(root: Path) -> tuple[dict[str, _MaterialFile], dict[str, str]]:
    files: dict[str, _MaterialFile] = {}
    root_mode = root.lstat().st_mode
    _need(stat.S_ISDIR(root_mode), "SUBJECT_SNAPSHOT")
    directories = {".": _directory_mode(root_mode)}
    total = 0
    observed_entries = 0
    pending = [root]
    try:
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    observed_entries += 1
                    _need(
                        observed_entries <= _MAX_SNAPSHOT_ENTRIES, "SUBJECT_ENTRY_BOUND"
                    )
                    metadata = entry.stat(follow_symlinks=False)
                    mode = metadata.st_mode
                    _need(not stat.S_ISLNK(mode), "SUBJECT_SYMLINK")
                    item = Path(entry.path)
                    name = item.relative_to(root).as_posix()
                    if stat.S_ISDIR(mode):
                        directories[name] = _directory_mode(mode)
                        pending.append(item)
                        continue
                    _need(stat.S_ISREG(mode), "SUBJECT_SPECIAL_FILE")
                    _need(metadata.st_size <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
                    with item.open("rb") as stream:
                        raw = stream.read(_MAX_FILE_BYTES + 1)
                    _need(len(raw) <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
                    total += len(raw)
                    _need(
                        total <= _MAX_SUBJECT_BYTES + _MAX_EVIDENCE_BYTES,
                        "SUBJECT_TOTAL_BOUND",
                    )
                    files[name] = _MaterialFile(
                        mode=_file_mode(mode),
                        sha256=_sha256(raw),
                        size=len(raw),
                    )
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
) -> UntrustedCapture:
    _validate_command(argv)
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
    if process_stdout is None or process_stderr is None:
        _kill_process_group(process)
        raise ExecutionRejected("BACKEND_PIPES")

    stdout = bytearray()
    stderr = bytearray()
    observed = 0
    termination = "completed"
    deadline = time.monotonic() + limits.timeout_seconds
    selector = selectors.DefaultSelector()
    selector.register(process_stdout, selectors.EVENT_READ, stdout)
    selector.register(process_stderr, selectors.EVENT_READ, stderr)
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                termination = "timeout"
                _kill_process_group(process)
                break
            for key, _ in selector.select(timeout=min(0.05, remaining)):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                observed += len(chunk)
                room = limits.output_bytes - len(stdout) - len(stderr)
                if room > 0:
                    key.data.extend(chunk[:room])
                if len(chunk) > room:
                    termination = "output_limit"
                    _kill_process_group(process)
                    break
            if termination != "completed":
                break
        if termination == "completed" and not _wait_for_exit_without_reap(
            process, deadline
        ):
            termination = "timeout"
        # Observe normal leader exit without reaping it, then clear the owned
        # session while that PID is still reserved. This prevents PID reuse from
        # redirecting a later killpg to unrelated same-user work.
        _kill_process_group(process)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired as exc:
            raise ExecutionRejected("BACKEND_REAP_FAILED") from exc
    finally:
        selector.close()
        process_stdout.close()
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

    subject_immutable_during_execution = False

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
        return _capture_process(
            _local_containment_argv(command), cwd=root, limits=limits
        )


class DockerBackend:
    """Linux/amd64 OCI specialization with a read-only, network-free subject."""

    subject_immutable_during_execution = True

    def __init__(self, image: str, docker_executable: str = "/usr/bin/docker") -> None:
        _need(_IMAGE_RE.fullmatch(image) is not None, "OCI_IMAGE_PIN")
        _need(docker_executable == "/usr/bin/docker", "DOCKER_EXECUTABLE")
        self.image = image
        self.docker_executable = docker_executable

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

    def _inspect_image(self) -> None:
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

    def _validate_container(
        self,
        container_id: str,
        root: Path,
        limits: ExecutionLimits,
        cleanup_nonce: str,
        subject: GitSubject,
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
        environment = config.get("Env") or []
        _need(isinstance(labels, dict) and isinstance(environment, list), "OCI_INSPECT")
        protected_environment: dict[str, str] = {}
        for item in environment:
            _need(isinstance(item, str) and "=" in item, "OCI_INSPECT")
            key, value = item.split("=", 1)
            if key in {"KNOWLEDGE_KIT_ROOT", "KNOWLEDGE_KIT_REVISION", "PYTHONPATH"}:
                _need(key not in protected_environment, "OCI_ENV_CONTRACT")
                protected_environment[key] = value
        _need(
            protected_environment
            == {
                "KNOWLEDGE_KIT_ROOT": "/workspace",
                "KNOWLEDGE_KIT_REVISION": subject.commit,
                "PYTHONPATH": "/workspace",
            },
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

    def _cleanup_presence(self, container_id: str, cleanup_nonce: str) -> bool | None:
        try:
            inspected = self._command("inspect", container_id, timeout=15)
        except ExecutionRejected:
            return None
        message = (inspected.stderr + b"\n" + inspected.stdout).lower()
        if inspected.returncode != 0:
            _need(b"no such" in message, "OCI_CLEANUP_UNVERIFIED")
            return False
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
            try:
                retry = self._command("rm", "--force", container_id, timeout=15)
            except ExecutionRejected:
                retry = None
            if retry is not None and retry.returncode != 0:
                message = (retry.stderr + b"\n" + retry.stdout).lower()
                if b"no such" in message:
                    return
                raise ExecutionRejected("OCI_CLEANUP_REMOVE")
            time.sleep(min(_UNCERTAIN_REMOVE_POLL_SECONDS, remaining))

    def _remove_and_verify(self, container_id: str, cleanup_nonce: str) -> None:
        try:
            result = self._command("rm", "--force", container_id, timeout=15)
        except ExecutionRejected:
            self._reconcile_uncertain_remove(container_id, cleanup_nonce)
            return
        if result.returncode != 0:
            message = (result.stderr + b"\n" + result.stdout).lower()
            if b"no such" not in message:
                raise ExecutionRejected("OCI_CLEANUP_REMOVE")
        self._reconcile_uncertain_remove(container_id, cleanup_nonce)

    def _cleanup_uncertain_create(
        self, container_name: str, cleanup_nonce: str
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
            message = (inspected.stderr + b"\n" + inspected.stdout).lower()
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
            _need(b"no such" in message, "OCI_CLEANUP_UNVERIFIED")
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
        self._inspect_image()
        cleanup_nonce = uuid.uuid4().hex
        container_name = f"gnostoa-vf0-{cleanup_nonce}"
        create = [
            "create",
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
            "--env",
            f"HOME={_CONTAINER_TMP}",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "KNOWLEDGE_KIT_ROOT=/workspace",
            "--env",
            f"KNOWLEDGE_KIT_REVISION={subject.commit}",
            "--env",
            "PYTHONPATH=/workspace",
            "--mount",
            f"type=bind,source={root},target=/workspace,readonly",
            "--workdir",
            "/workspace",
            "--entrypoint",
            command[0],
            self.image,
            *command[1:],
        ]
        container_id: str | None = None
        attachment_finished = False
        try:
            observed_id = self._checked(*create).decode().strip().lower()
            _need(_DOCKER_ID_RE.fullmatch(observed_id) is not None, "OCI_CONTAINER_ID")
            container_id = observed_id
            self._validate_container(container_id, root, limits, cleanup_nonce, subject)
            capture = _capture_process(
                [self.docker_executable, "start", "--attach", container_id],
                cwd=None,
                limits=limits,
            )
            attachment_finished = True
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
                    isinstance(state, dict) and state.get("Running") is False,
                    "OCI_EXIT_STATE",
                )
                exit_code = state.get("ExitCode")
                _need(
                    isinstance(exit_code, int) and not isinstance(exit_code, bool),
                    "OCI_EXIT_STATE",
                )
                capture = replace(capture, exit_code=exit_code)
            return capture
        finally:
            # _capture_process closes/reaps the attachment group before this point.
            # Even preflight/client failures still remove and independently verify
            # absence of the owned container.
            try:
                if container_id is None:
                    self._cleanup_uncertain_create(container_name, cleanup_nonce)
                else:
                    self._remove_and_verify(container_id, cleanup_nonce)
            except ExecutionRejected:
                if attachment_finished:
                    raise
                raise


def _snapshot_evidence(
    evidence: Sequence[EvidenceFile],
) -> tuple[EvidenceFile, ...]:
    snapshot: list[EvidenceFile] = []
    iterator = iter(evidence)
    for _ in range(_MAX_EVIDENCE_FILES + 1):
        try:
            snapshot.append(next(iterator))
        except StopIteration:
            break
    _need(1 <= len(snapshot) <= _MAX_EVIDENCE_FILES, "EVIDENCE_COUNT")
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
    command_snapshot = tuple(command)
    _need(
        bool(command_snapshot)
        and all(isinstance(part, str) and part for part in command_snapshot),
        "COMMAND",
    )
    evidence_snapshot = _snapshot_evidence(evidence)
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
            before_manifest_sha256=before_digest,
            after_manifest_sha256=after_digest,
            capture=capture,
            subject_unchanged=(
                getattr(backend, "subject_immutable_during_execution", False) is True
            ),
        )
