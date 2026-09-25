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
import subprocess
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Protocol

_GIT_SHA1_RE = re.compile(r"[0-9a-f]{40}")
_DOCKER_ID_RE = re.compile(r"[0-9a-f]{64}")
_IMAGE_RE = re.compile(r"(?:[a-z0-9][a-z0-9._/-]*@)?sha256:[0-9a-f]{64}")
_MAX_SUBJECT_BYTES = 64 * 1024 * 1024
_MAX_FILE_BYTES = 32 * 1024 * 1024
_MAX_EVIDENCE_FILES = 32
_MAX_EVIDENCE_BYTES = 2 * 1024 * 1024
_CLEAN_ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp",
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


def _git_blob_sha1(raw: bytes) -> str:
    framed = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    return hashlib.sha1(framed).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _git_sha1(value: str, reason: str) -> str:
    _need(_GIT_SHA1_RE.fullmatch(value) is not None, reason)
    return value


def _evidence_path(value: str) -> str:
    _need(bool(value) and "\\" not in value, "EVIDENCE_PATH")
    raw_parts = value.split("/")
    _need(all(part not in {"", ".", ".."} for part in raw_parts), "EVIDENCE_PATH")
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
        _need(len(self.content) <= _MAX_EVIDENCE_BYTES, "EVIDENCE_FILE_BOUND")


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
    """Provider-neutral observation; deliberately contains no approval/compliance fields."""

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
    ) -> UntrustedCapture: ...


@dataclass(frozen=True)
class _MaterialFile:
    mode: str
    sha256: str
    size: int


def _trusted_git(repo: Path, *args: str) -> bytes:
    argv = ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args]
    try:
        result = subprocess.run(
            argv,
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

    entries = _trusted_git(
        root, "ls-tree", "-rzl", "--full-tree", subject.commit
    ).split(b"\0")
    expected: dict[str, _MaterialFile] = {}
    total = 0
    target.mkdir(mode=0o755, parents=False, exist_ok=False)
    for entry in filter(None, entries):
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
        _need(name not in expected, "SUBJECT_PATH_DUPLICATE")
        _need(0 <= size <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
        total += size
        _need(total <= _MAX_SUBJECT_BYTES, "SUBJECT_TOTAL_BOUND")
        payload = _trusted_git(root, "cat-file", "blob", oid)
        _need(
            len(payload) == size and _git_blob_sha1(payload) == oid,
            "SUBJECT_BLOB_MISMATCH",
        )
        destination = target / name
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        destination.write_bytes(payload)
        destination.chmod(0o755 if mode == "100755" else 0o644)
        expected[name] = _MaterialFile(mode=mode, sha256=_sha256(payload), size=size)
    return expected


def _snapshot(root: Path) -> dict[str, _MaterialFile]:
    files: dict[str, _MaterialFile] = {}
    total = 0
    for item in sorted(root.rglob("*")):
        mode = item.lstat().st_mode
        _need(not stat.S_ISLNK(mode), "SUBJECT_SYMLINK")
        if stat.S_ISDIR(mode):
            continue
        _need(stat.S_ISREG(mode), "SUBJECT_SPECIAL_FILE")
        raw = item.read_bytes()
        _need(len(raw) <= _MAX_FILE_BYTES, "SUBJECT_FILE_BOUND")
        total += len(raw)
        _need(total <= _MAX_SUBJECT_BYTES + _MAX_EVIDENCE_BYTES, "SUBJECT_TOTAL_BOUND")
        name = item.relative_to(root).as_posix()
        files[name] = _MaterialFile(
            mode="100755" if mode & 0o111 else "100644",
            sha256=_sha256(raw),
            size=len(raw),
        )
    return files


def _manifest_digest(manifest: dict[str, _MaterialFile]) -> str:
    serial = {
        path: {"mode": item.mode, "sha256": item.sha256, "size": item.size}
        for path, item in sorted(manifest.items())
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
        destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        destination.write_bytes(item.content)
        destination.chmod(0o755 if item.mode == "100755" else 0o644)
        expected[item.path] = _MaterialFile(
            mode=item.mode,
            sha256=_sha256(item.content),
            size=len(item.content),
        )
    return expected


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except OSError:
        process.kill()


def _capture_process(
    argv: Sequence[str],
    *,
    cwd: Path | None,
    limits: ExecutionLimits,
) -> UntrustedCapture:
    _need(
        bool(argv) and all(isinstance(part, str) and part for part in argv), "COMMAND"
    )
    try:
        process = subprocess.Popen(
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
        if termination == "completed":
            remaining = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                termination = "timeout"
                _kill_process_group(process)
        if process.poll() is None:
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


class SubprocessBackend:
    """Finite local backend used for conformance tests; it is not an OS sandbox."""

    def run(
        self,
        root: Path,
        command: Sequence[str],
        limits: ExecutionLimits,
    ) -> UntrustedCapture:
        return _capture_process(command, cwd=root, limits=limits)


class DockerBackend:
    """Linux/amd64 OCI specialization with a read-only, network-free subject."""

    def __init__(self, image: str, docker_executable: str = "/usr/bin/docker") -> None:
        _need(_IMAGE_RE.fullmatch(image) is not None, "OCI_IMAGE_PIN")
        _need(Path(docker_executable).is_absolute(), "DOCKER_EXECUTABLE")
        self.image = image
        self.docker_executable = docker_executable

    def _command(
        self, *args: str, timeout: float = 30
    ) -> subprocess.CompletedProcess[bytes]:
        try:
            return subprocess.run(
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
        self, container_id: str, root: Path, limits: ExecutionLimits
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
        binds = [m for m in mounts if isinstance(m, dict) and m.get("Type") == "bind"]
        _need(
            len(binds) == 1
            and binds[0].get("Source") == str(root)
            and binds[0].get("Destination") == "/workspace"
            and binds[0].get("RW") is False,
            "OCI_MOUNT_CONTRACT",
        )
        security = host.get("SecurityOpt") or []
        _need(
            host.get("ReadonlyRootfs") is True
            and host.get("NetworkMode") == "none"
            and host.get("IpcMode") == "none"
            and host.get("Privileged") is False
            and host.get("CapDrop") == ["ALL"]
            and "no-new-privileges" in security
            and config.get("User") == "10001:10001"
            and host.get("PidsLimit") == limits.pids
            and host.get("Memory") == limits.memory_bytes
            and host.get("MemorySwap") == limits.memory_bytes
            and host.get("NanoCpus") == int(limits.cpus * 1_000_000_000),
            "OCI_CONTRACT",
        )

    def _remove_and_verify(self, container_id: str) -> None:
        result = self._command("rm", "--force", container_id, timeout=15)
        _need(result.returncode == 0, "OCI_CLEANUP_REMOVE")
        gone = self._command("container", "inspect", container_id, timeout=15)
        message = (gone.stderr + b"\n" + gone.stdout).lower()
        _need(gone.returncode != 0 and b"no such" in message, "OCI_CLEANUP_UNVERIFIED")

    def run(
        self,
        root: Path,
        command: Sequence[str],
        limits: ExecutionLimits,
    ) -> UntrustedCapture:
        _need(
            bool(command) and all(isinstance(part, str) and part for part in command),
            "COMMAND",
        )
        self._inspect_image()
        create = [
            "create",
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
            f"/tmp:rw,nosuid,nodev,noexec,mode=1777,size={limits.tmpfs_bytes}",
            "--env",
            "HOME=/tmp",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--mount",
            f"type=bind,source={root},target=/workspace,readonly",
            "--workdir",
            "/workspace",
            "--entrypoint",
            command[0],
            self.image,
            *command[1:],
        ]
        container_id = self._checked(*create).decode().strip().lower()
        _need(_DOCKER_ID_RE.fullmatch(container_id) is not None, "OCI_CONTAINER_ID")
        attachment_finished = False
        try:
            self._validate_container(container_id, root, limits)
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
                self._remove_and_verify(container_id)
            except ExecutionRejected:
                if attachment_finished:
                    raise
                raise


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
    _need(
        bool(command) and all(isinstance(part, str) and part for part in command),
        "COMMAND",
    )
    with tempfile.TemporaryDirectory(prefix="gnostoa-vf0-execution-") as temporary:
        temp = Path(temporary)
        root = temp / "subject"
        baseline = _materialize_subject(repository, subject, root)
        expected = _overlay_evidence(root, baseline, evidence)
        before = _snapshot(root)
        _need(before == expected, "SUBJECT_BEFORE_EXECUTION")
        before_digest = _manifest_digest(before)
        capture = backend.run(root, tuple(command), chosen_limits)
        after = _snapshot(root)
        _need(after == expected, "SUBJECT_MUTATED")
        after_digest = _manifest_digest(after)
        _need(before_digest == after_digest, "SUBJECT_MUTATED")
        evidence_digests = tuple(
            sorted((item.path, _sha256(item.content)) for item in evidence)
        )
        return ExecutionObservation(
            subject=subject,
            evidence_sha256=evidence_digests,
            before_manifest_sha256=before_digest,
            after_manifest_sha256=after_digest,
            capture=capture,
            subject_unchanged=True,
        )
