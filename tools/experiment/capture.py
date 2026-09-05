from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path

from .backend import docker_executable
from .evidence import ATTEST_SCHEMA, parse_input_identity_mapping, sha256_file
from .profile import RunnerError, is_same_or_parent

SIZE_SCHEMA = "gnostoa-path-size-check/v1"
_CHUNK_SIZE = 1024 * 1024
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def open_bound_directory(path: Path, label: str) -> tuple[int, os.stat_result]:
    descriptor = os.open(path, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW)
    identity = os.fstat(descriptor)
    if not stat.S_ISDIR(identity.st_mode):
        os.close(descriptor)
        raise RunnerError(f"{label}-not-directory")
    try:
        assert_visible_directory(path, identity, label)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, identity


def assert_visible_directory(
    path: Path,
    expected: os.stat_result,
    label: str,
) -> None:
    try:
        observed = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise RunnerError(f"{label}-namespace-changed:{exc}") from exc
    if not stat.S_ISDIR(observed.st_mode) or not _same_object(expected, observed):
        raise RunnerError(f"{label}-namespace-changed")


def ensure_directory_names_absent(
    directory_fd: int,
    names: Sequence[str],
    *,
    label: str,
) -> None:
    for name in names:
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise RunnerError(f"{label}-already-exists:{name}")


def _open_create_only_file(directory_fd: int, name: str, label: str) -> int:
    try:
        return os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
    except FileExistsError as exc:
        raise RunnerError(f"{label}-already-exists:{name}") from exc


def publish_captured_file_at(
    source: Path,
    directory_fd: int,
    name: str,
    *,
    label: str = "evidence-output",
) -> None:
    destination_fd = _open_create_only_file(directory_fd, name, label)
    try:
        with source.open("rb") as captured:
            while True:
                chunk = captured.read(_CHUNK_SIZE)
                if not chunk:
                    break
                view = memoryview(chunk)
                while view:
                    written = os.write(destination_fd, view)
                    if written <= 0:
                        raise RunnerError("short-evidence-write")
                    view = view[written:]
        os.fsync(destination_fd)
    finally:
        os.close(destination_fd)


def publish_bytes_at(
    data: bytes,
    directory_fd: int,
    name: str,
    *,
    label: str = "evidence-output",
) -> None:
    destination_fd = _open_create_only_file(directory_fd, name, label)
    try:
        view = memoryview(data)
        while view:
            written = os.write(destination_fd, view)
            if written <= 0:
                raise RunnerError("short-evidence-write")
            view = view[written:]
        os.fsync(destination_fd)
    finally:
        os.close(destination_fd)


def attest_payload(
    artifact: Path,
    producer_id: str,
    producer_version: str,
    config_sha256: str,
    inputs: Sequence[str],
) -> dict[str, object]:
    if not _SHA256_RE.fullmatch(config_sha256):
        raise RunnerError("invalid-config-sha256")
    digest, size = sha256_file(artifact)
    return {
        "schema": ATTEST_SCHEMA,
        "sha256": digest,
        "bytes": size,
        "producer": {
            "id": producer_id,
            "version": producer_version,
            "config_sha256": config_sha256,
        },
        "inputs": [parse_input_identity_mapping(value) for value in inputs],
    }


def _directory_total(root: Path) -> int:
    """Total the bytes a directory tree occupies without ever consulting a target.

    Traversal is explicit rather than os.walk: os.walk classifies entries through
    DirEntry.is_dir(), which follows symlinks by default, so even with
    followlinks=False a target metadata lookup can occur. Every decision here comes
    from one stat taken with follow_symlinks=False, so a link's target is never
    stat-followed, opened or entered.

    A link contributes only the bytes it occupies itself. Refusing it instead would
    discard a completed run's evidence over a file the subject's own frozen tree
    legitimately carries. Recursion enters only real directories, so a link cycle
    cannot recur.
    """
    total = 0
    pending = [root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                item = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(item.st_mode):
                    total += item.st_size
                elif stat.S_ISDIR(item.st_mode):
                    pending.append(Path(entry.path))
                elif stat.S_ISREG(item.st_mode):
                    total += item.st_size
    return total


def measured_path_size(path: Path) -> tuple[int, str]:
    stat_result = path.lstat()
    if path.is_symlink():
        raise RunnerError("size-check-refuses-symlink")
    if path.is_file():
        return stat_result.st_size, "lstat-size-v1"
    if not path.is_dir():
        raise RunnerError("size-check-supports-regular-file-or-directory")
    return _directory_total(path), "recursive-lstat-size-v2"


def run_configuration_digest(
    profile_path: Path,
    backend_requested: str,
    backend_resolved: str,
    command: Sequence[str],
) -> str:
    profile_digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    material = json.dumps(
        {
            "backend_requested": backend_requested,
            "backend_resolved": backend_resolved,
            "command": list(command),
            "profile_sha256": profile_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def stream_container_logs(container: str, output: Path) -> None:
    with output.open("xb") as target:
        result = subprocess.run(
            [docker_executable(), "logs", container],
            check=False,
            stdout=target,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    if result.returncode != 0:
        raise RunnerError("relay-log-capture-failed")


def ensure_private_capture_root(
    capture_root: Path,
    mounted_roots: Sequence[str],
) -> None:
    resolved_capture = capture_root.resolve(strict=True)
    for root_text in mounted_roots:
        resolved_root = Path(root_text).resolve(strict=True)
        if is_same_or_parent(resolved_root, resolved_capture) or is_same_or_parent(
            resolved_capture, resolved_root
        ):
            raise RunnerError("coordinator-capture-overlaps-admitted-surface")


def publish_captured_file(source: Path, destination: Path) -> None:
    with source.open("rb") as captured, destination.open("xb") as retained:
        shutil.copyfileobj(captured, retained, length=_CHUNK_SIZE)


def applied_control_count(
    read_roots: Sequence[str],
    temporary_roots: Sequence[str],
    network_mode: str,
) -> int:
    base_controls = 6
    mount_controls = len(read_roots) + len(temporary_roots) + 2
    network_controls = 2 if network_mode == "restricted" else 1
    return base_controls + mount_controls + network_controls
