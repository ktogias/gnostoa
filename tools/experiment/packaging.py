from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import BinaryIO, cast

from .evidence import (
    InputIdentity,
    configuration_digest,
    producer_record,
    sha256_file,
)
from .handoff import HandoffError, VerifiedHandoff, load_verified_handoff

PACKAGE_SCHEMA = "gnostoa-experiment-package/v2"
PACKAGE_FORMAT = "pax-tar-v1"
PACKAGE_PRODUCER_ID = "gnostoa-experiment-packager"
PACKAGE_PRODUCER_VERSION = "2"
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class PackageError(RuntimeError):
    """Raised when the deterministic package contract cannot be satisfied."""


class ArchiveLimitExceeded(PackageError):
    """Raised before a streamed archive write would exceed its hard limit."""


class BoundedWriter:
    def __init__(self, target: BinaryIO, max_bytes: int) -> None:
        self._target = target
        self._max_bytes = max_bytes
        self.bytes_written = 0

    def write(self, data: bytes) -> int:
        next_size = self.bytes_written + len(data)
        if next_size > self._max_bytes:
            raise ArchiveLimitExceeded("archive-limit-exceeded")
        written = self._target.write(data)
        if written != len(data):
            raise PackageError("short-archive-write")
        self.bytes_written = next_size
        return written

    def flush(self) -> None:
        self._target.flush()


class VerifyingReader:
    def __init__(
        self,
        source: BinaryIO,
        *,
        expected_sha256: str,
        expected_bytes: int,
    ) -> None:
        self._source = source
        self._digest = hashlib.sha256()
        self._expected_sha256 = expected_sha256
        self._expected_bytes = expected_bytes
        self._observed_bytes = 0

    def read(self, size: int = -1) -> bytes:
        data = self._source.read(size)
        self._digest.update(data)
        self._observed_bytes += len(data)
        return data

    def assert_complete(self) -> None:
        if self._observed_bytes != self._expected_bytes:
            raise PackageError("snapshot-file-byte-count-mismatch")
        if self._digest.hexdigest() != self._expected_sha256:
            raise PackageError("snapshot-file-digest-mismatch")


def _emit(payload: Mapping[str, object]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")))


def _normalized_mode(mode: int) -> int:
    if stat.S_ISDIR(mode):
        return 0o755
    if stat.S_ISREG(mode):
        return 0o755 if mode & 0o111 else 0o644
    if stat.S_ISLNK(mode):
        return 0o777
    raise PackageError("unsupported-snapshot-entry-type")


def _relative_parts(value: str) -> tuple[str, ...]:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(
        part in {"", ".", ".."} for part in path.parts
    ):
        raise PackageError(f"unsafe-member-path:{value}")
    canonical = "/".join(path.parts)
    if canonical != value:
        raise PackageError(f"noncanonical-member-path:{value}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise PackageError(f"member-path-not-portable-utf8:{value}") from exc
    return path.parts


def _open_root(snapshot_root: Path) -> int:
    flags = os.O_RDONLY | _O_DIRECTORY
    if _O_NOFOLLOW:
        flags |= _O_NOFOLLOW
    return os.open(snapshot_root, flags)


def _open_parent(root_fd: int, relative: str) -> tuple[int, str]:
    parts = _relative_parts(relative)
    current = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            flags = os.O_RDONLY | _O_DIRECTORY
            if _O_NOFOLLOW:
                flags |= _O_NOFOLLOW
            next_fd = os.open(part, flags, dir_fd=current)
            os.close(current)
            current = next_fd
        return current, parts[-1]
    except BaseException:
        os.close(current)
        raise


def _member_mode(member: Mapping[str, object]) -> int:
    raw = member.get("mode")
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise PackageError("handoff-member-mode-invalid")
    return raw


def _member_type(member: Mapping[str, object]) -> str:
    raw = member.get("type")
    if not isinstance(raw, str):
        raise PackageError("handoff-member-type-invalid")
    return raw


def _member_path(member: Mapping[str, object]) -> str:
    raw = member.get("path")
    if not isinstance(raw, str):
        raise PackageError("handoff-member-path-invalid")
    _relative_parts(raw)
    return raw


def _tar_info(member: Mapping[str, object]) -> tarfile.TarInfo:
    path = _member_path(member)
    info = tarfile.TarInfo(path)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}
    info.mode = _member_mode(member)

    member_type = _member_type(member)
    if member_type == "directory":
        info.type = tarfile.DIRTYPE
        info.size = 0
    elif member_type == "file":
        raw_size = member.get("bytes")
        if (
            not isinstance(raw_size, int)
            or isinstance(raw_size, bool)
            or raw_size < 0
        ):
            raise PackageError("handoff-file-size-invalid")
        info.type = tarfile.REGTYPE
        info.size = raw_size
    elif member_type == "symlink":
        target = member.get("target")
        if not isinstance(target, str):
            raise PackageError("handoff-symlink-target-invalid")
        info.type = tarfile.SYMTYPE
        info.size = 0
        info.linkname = target
    else:
        raise PackageError(f"handoff-member-type-unsupported:{member_type}")
    return info


def _assert_stat_matches_member(
    observed: os.stat_result,
    member: Mapping[str, object],
) -> None:
    expected_type = _member_type(member)
    if expected_type == "directory" and not stat.S_ISDIR(observed.st_mode):
        raise PackageError("snapshot-entry-type-mismatch")
    if expected_type == "file" and not stat.S_ISREG(observed.st_mode):
        raise PackageError("snapshot-entry-type-mismatch")
    if expected_type == "symlink" and not stat.S_ISLNK(observed.st_mode):
        raise PackageError("snapshot-entry-type-mismatch")
    if _normalized_mode(observed.st_mode) != _member_mode(member):
        raise PackageError("snapshot-entry-mode-mismatch")


def _add_member(
    archive: tarfile.TarFile,
    snapshot_fd: int,
    member: Mapping[str, object],
) -> None:
    relative = _member_path(member)
    parent_fd, name = _open_parent(snapshot_fd, relative)
    try:
        observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        _assert_stat_matches_member(observed, member)
        info = _tar_info(member)
        member_type = _member_type(member)

        if member_type == "directory":
            archive.addfile(info)
            return

        if member_type == "symlink":
            target = os.readlink(name, dir_fd=parent_fd)
            if target != cast(str, member.get("target")):
                raise PackageError("snapshot-symlink-target-mismatch")
            after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                observed.st_dev != after.st_dev
                or observed.st_ino != after.st_ino
                or observed.st_ctime_ns != after.st_ctime_ns
            ):
                raise PackageError("snapshot-symlink-changed")
            archive.addfile(info)
            return

        raw_digest = member.get("sha256")
        raw_bytes = member.get("bytes")
        if not isinstance(raw_digest, str) or not isinstance(raw_bytes, int):
            raise PackageError("handoff-file-identity-invalid")
        flags = os.O_RDONLY
        if _O_NOFOLLOW:
            flags |= _O_NOFOLLOW
        source_fd = os.open(name, flags, dir_fd=parent_fd)
        try:
            opened = os.fstat(source_fd)
            if (
                opened.st_dev != observed.st_dev
                or opened.st_ino != observed.st_ino
                or opened.st_size != observed.st_size
                or opened.st_ctime_ns != observed.st_ctime_ns
            ):
                raise PackageError("snapshot-file-changed-before-read")
            with os.fdopen(os.dup(source_fd), "rb") as source:
                verifying = VerifyingReader(
                    source,
                    expected_sha256=raw_digest,
                    expected_bytes=raw_bytes,
                )
                archive.addfile(info, cast(BinaryIO, verifying))
                verifying.assert_complete()
            after_fd = os.fstat(source_fd)
            after_path = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                after_fd.st_dev != opened.st_dev
                or after_fd.st_ino != opened.st_ino
                or after_fd.st_size != opened.st_size
                or after_fd.st_ctime_ns != opened.st_ctime_ns
                or after_path.st_dev != opened.st_dev
                or after_path.st_ino != opened.st_ino
                or after_path.st_size != opened.st_size
                or after_path.st_ctime_ns != opened.st_ctime_ns
            ):
                raise PackageError("snapshot-file-changed-during-read")
        finally:
            os.close(source_fd)
    finally:
        os.close(parent_fd)


def _package_config_digest(max_bytes: int) -> str:
    return configuration_digest(
        {
            "format": PACKAGE_FORMAT,
            "hard_limit": "stream-before-publication-v1",
            "max_bytes": max_bytes,
            "membership": "verified-handoff-only-v1",
            "metadata": "uid-gid-zero-names-empty-mtime-zero-mode-normalized-v1",
            "ordering": "handoff-member-order-v1",
            "publication": "hardlink-create-only-v1",
        }
    )


def _validated_output(handoff: VerifiedHandoff, output: Path) -> Path:
    parent_lexical = Path(os.path.abspath(output.parent))
    try:
        parent_resolved = parent_lexical.resolve(strict=True)
    except OSError as exc:
        raise PackageError(f"output-parent-unavailable:{exc}") from exc
    if parent_resolved != parent_lexical or not parent_resolved.is_dir():
        raise PackageError("output-parent-must-be-resolved-directory")
    output_path = parent_resolved / output.name
    if output_path.exists() or output_path.is_symlink():
        raise PackageError("output-already-exists")
    try:
        output_path.relative_to(handoff.bundle_root)
    except ValueError:
        pass
    else:
        raise PackageError("output-inside-handoff-bundle")
    return output_path


def _package_inputs(handoff: VerifiedHandoff) -> list[InputIdentity]:
    if any(item.id == "handoff" for item in handoff.inputs):
        raise PackageError("reserved-handoff-input-identity")
    return [
        *handoff.inputs,
        InputIdentity("handoff", handoff.manifest_sha256),
    ]


def create_package(
    handoff_path: Path,
    output: Path,
    max_bytes: int,
) -> tuple[int, dict[str, object]]:
    if max_bytes <= 0:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "BLOCKED",
            "reasons": ["max-bytes-must-be-positive"],
        }
    try:
        handoff = load_verified_handoff(handoff_path)
        output_path = _validated_output(handoff, output)
        inputs = _package_inputs(handoff)
        config_sha256 = _package_config_digest(max_bytes)
    except (OSError, HandoffError, PackageError) as exc:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "BLOCKED",
            "reasons": [f"{type(exc).__name__}:{exc}"],
        }

    descriptor, staged_name = tempfile.mkstemp(
        prefix=".gnostoa-package-",
        suffix=".tmp",
        dir=output_path.parent,
    )
    staged = Path(staged_name)
    archive: tarfile.TarFile | None = None
    snapshot_fd = -1
    try:
        snapshot_fd = _open_root(handoff.snapshot_root)
        with os.fdopen(descriptor, "wb") as raw:
            bounded = BoundedWriter(raw, max_bytes)
            archive = tarfile.open(
                fileobj=cast(BinaryIO, bounded),
                mode="w|",
                format=tarfile.PAX_FORMAT,
            )
            for member in handoff.members:
                _add_member(archive, snapshot_fd, member)
            archive.close()
            archive = None
            bounded.flush()
            os.fsync(raw.fileno())

        after = load_verified_handoff(handoff_path)
        if (
            after.manifest_sha256 != handoff.manifest_sha256
            or after.tree_sha256 != handoff.tree_sha256
        ):
            raise PackageError("handoff-changed-during-packaging")

        digest, size = sha256_file(staged)
        if size > max_bytes:
            raise PackageError("archive-size-exceeds-configured-limit")
        try:
            os.link(staged, output_path)
        except FileExistsError as exc:
            raise PackageError("output-already-exists") from exc

        return 0, {
            "schema": PACKAGE_SCHEMA,
            "status": "PACKAGED",
            "format": PACKAGE_FORMAT,
            "sha256": digest,
            "bytes": size,
            "max_bytes": max_bytes,
            "members": len(handoff.members),
            "producer": producer_record(
                PACKAGE_PRODUCER_ID,
                PACKAGE_PRODUCER_VERSION,
                config_sha256,
            ),
            "inputs": [item.as_dict() for item in inputs],
        }
    except ArchiveLimitExceeded:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "OVERSIZE",
            "format": PACKAGE_FORMAT,
            "max_bytes": max_bytes,
            "reasons": ["archive-limit-exceeded"],
        }
    except (OSError, HandoffError, PackageError, tarfile.TarError) as exc:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "BLOCKED",
            "reasons": [f"{type(exc).__name__}:{exc}"],
        }
    finally:
        if archive is not None:
            try:
                archive.close()
            except (ArchiveLimitExceeded, OSError, tarfile.TarError):
                pass
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        try:
            staged.unlink()
        except FileNotFoundError:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experiment_packager.py")
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-bytes", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code, payload = create_package(
        Path(cast(str, args.handoff)),
        Path(cast(str, args.output)),
        cast(int, args.max_bytes),
    )
    _emit(payload)
    return exit_code
