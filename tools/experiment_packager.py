from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
import tempfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import BinaryIO

PACKAGE_SCHEMA = "gnostoa-experiment-package/v1"
PACKAGE_FORMAT = "pax-tar-v1"
PRODUCER_ID = "gnostoa-experiment-packager"
PRODUCER_VERSION = "1"
_CHUNK_SIZE = 1024 * 1024
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class PackageError(RuntimeError):
    """Raised when a package cannot satisfy the declared boundary."""


class ArchiveLimitExceeded(PackageError):
    """Raised before an archive write would exceed the configured byte limit."""


class BoundedWriter:
    def __init__(self, target: BinaryIO, max_bytes: int) -> None:
        self.target = target
        self.max_bytes = max_bytes
        self.bytes_written = 0

    def write(self, data: bytes) -> int:
        next_size = self.bytes_written + len(data)
        if next_size > self.max_bytes:
            raise ArchiveLimitExceeded("archive-limit-exceeded")
        written = self.target.write(data)
        if written != len(data):
            raise PackageError("short-archive-write")
        self.bytes_written = next_size
        return written

    def flush(self) -> None:
        self.target.flush()


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def parse_input_identity(value: str) -> dict[str, str]:
    identifier, separator, digest = value.partition("=")
    if not separator or not identifier or not _SHA256_RE.fullmatch(digest):
        raise PackageError(f"invalid-input-identity:{value}")
    return {"id": identifier, "sha256": digest}


def validate_input_identities(values: Sequence[str]) -> list[dict[str, str]]:
    if not values:
        raise PackageError("input-identities-required")
    parsed = [parse_input_identity(value) for value in values]
    identifiers = [item["id"] for item in parsed]
    if len(set(identifiers)) != len(identifiers):
        raise PackageError("duplicate-input-identity")
    return parsed


def lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def validate_paths(root: Path, output: Path) -> tuple[Path, Path]:
    lexical_root = lexical_absolute(root)
    try:
        resolved_root = lexical_root.resolve(strict=True)
    except OSError as exc:
        raise PackageError(f"source-root-unavailable:{exc}") from exc
    if resolved_root != lexical_root or not resolved_root.is_dir():
        raise PackageError("source-root-must-be-resolved-directory")

    lexical_parent = lexical_absolute(output.parent)
    try:
        resolved_parent = lexical_parent.resolve(strict=True)
    except OSError as exc:
        raise PackageError(f"output-parent-unavailable:{exc}") from exc
    if resolved_parent != lexical_parent or not resolved_parent.is_dir():
        raise PackageError("output-parent-must-be-resolved-directory")

    resolved_output = resolved_parent / output.name
    if resolved_output.exists() or resolved_output.is_symlink():
        raise PackageError("output-already-exists")
    try:
        resolved_output.relative_to(resolved_root)
    except ValueError:
        pass
    else:
        raise PackageError("output-inside-source-root")
    return resolved_root, resolved_output


def iter_entries(root: Path) -> Iterator[tuple[Path, str, os.stat_result]]:
    def walk(directory: Path, prefix: str) -> Iterator[tuple[Path, str, os.stat_result]]:
        try:
            with os.scandir(directory) as scan:
                entries = sorted(scan, key=lambda entry: os.fsencode(entry.name))
        except OSError as exc:
            raise PackageError(f"cannot-scan-source:{directory}:{exc}") from exc

        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            path = directory / entry.name
            try:
                observed = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise PackageError(f"cannot-stat-source:{relative}:{exc}") from exc
            yield path, relative, observed
            if stat.S_ISDIR(observed.st_mode):
                yield from walk(path, relative)

    yield from walk(root, "")


def normalized_info(relative: str, observed: os.stat_result) -> tarfile.TarInfo:
    info = tarfile.TarInfo(relative)
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    info.pax_headers = {}

    if stat.S_ISDIR(observed.st_mode):
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.size = 0
    elif stat.S_ISREG(observed.st_mode):
        info.type = tarfile.REGTYPE
        info.mode = 0o755 if observed.st_mode & 0o111 else 0o644
        info.size = observed.st_size
    elif stat.S_ISLNK(observed.st_mode):
        info.type = tarfile.SYMTYPE
        info.mode = 0o777
        info.size = 0
    else:
        raise PackageError(f"unsupported-source-entry:{relative}")
    return info


def add_regular_file(
    archive: tarfile.TarFile,
    path: Path,
    info: tarfile.TarInfo,
    observed: os.stat_result,
) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PackageError(f"cannot-open-source-file:{info.name}:{exc}") from exc
    with os.fdopen(descriptor, "rb") as source:
        current = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_dev != observed.st_dev
            or current.st_ino != observed.st_ino
            or current.st_size != observed.st_size
        ):
            raise PackageError(f"source-entry-changed:{info.name}")
        archive.addfile(info, source)


def add_entry(
    archive: tarfile.TarFile,
    path: Path,
    relative: str,
    observed: os.stat_result,
) -> None:
    info = normalized_info(relative, observed)
    if info.isreg():
        add_regular_file(archive, path, info, observed)
        return
    if info.issym():
        try:
            info.linkname = os.readlink(path)
            current = path.lstat()
        except OSError as exc:
            raise PackageError(f"cannot-read-symlink:{relative}:{exc}") from exc
        if (
            not stat.S_ISLNK(current.st_mode)
            or current.st_dev != observed.st_dev
            or current.st_ino != observed.st_ino
        ):
            raise PackageError(f"source-entry-changed:{relative}")
    archive.addfile(info)


def package_configuration_digest(max_bytes: int) -> str:
    material = json.dumps(
        {
            "format": PACKAGE_FORMAT,
            "limit": "stream-hard-ceiling-v1",
            "max_bytes": max_bytes,
            "metadata": "uid-gid-zero-names-empty-mtime-zero-mode-normalized-v1",
            "ordering": "filesystem-bytes-lexicographic-v1",
            "symlinks": "preserve-without-dereference-v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def create_package(
    root: Path,
    output: Path,
    max_bytes: int,
    input_identities: Sequence[str],
) -> tuple[int, dict[str, object]]:
    if max_bytes <= 0:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "BLOCKED",
            "reasons": ["max-bytes-must-be-positive"],
        }
    try:
        parsed_inputs = validate_input_identities(input_identities)
        source_root, output_path = validate_paths(root, output)
        entries = list(iter_entries(source_root))
        for _, relative, observed in entries:
            normalized_info(relative, observed)
    except PackageError as exc:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "BLOCKED",
            "reasons": [str(exc)],
        }

    descriptor, staged_name = tempfile.mkstemp(
        prefix=".gnostoa-package-",
        suffix=".tmp",
        dir=output_path.parent,
    )
    staged = Path(staged_name)
    archive: tarfile.TarFile | None = None
    published = False
    try:
        with os.fdopen(descriptor, "wb") as raw:
            bounded = BoundedWriter(raw, max_bytes)
            archive = tarfile.open(
                fileobj=bounded,
                mode="w|",
                format=tarfile.PAX_FORMAT,
            )
            for path, relative, observed in entries:
                add_entry(archive, path, relative, observed)
            archive.close()
            archive = None
            bounded.flush()
            os.fsync(raw.fileno())

        digest, size = sha256_file(staged)
        if size > max_bytes:
            raise PackageError("archive-size-exceeds-configured-limit")
        try:
            os.link(staged, output_path)
        except FileExistsError as exc:
            raise PackageError("output-already-exists") from exc
        published = True
        payload: dict[str, object] = {
            "schema": PACKAGE_SCHEMA,
            "status": "PACKAGED",
            "format": PACKAGE_FORMAT,
            "sha256": digest,
            "bytes": size,
            "max_bytes": max_bytes,
            "entries": len(entries),
            "producer": {
                "id": PRODUCER_ID,
                "version": PRODUCER_VERSION,
                "config_sha256": package_configuration_digest(max_bytes),
            },
            "inputs": parsed_inputs,
        }
        return 0, payload
    except ArchiveLimitExceeded:
        return 2, {
            "schema": PACKAGE_SCHEMA,
            "status": "OVERSIZE",
            "format": PACKAGE_FORMAT,
            "max_bytes": max_bytes,
            "reasons": ["archive-limit-exceeded"],
        }
    except (OSError, PackageError, tarfile.TarError) as exc:
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
        try:
            staged.unlink()
        except FileNotFoundError:
            pass
        if not published:
            try:
                output_path.unlink()
            except FileNotFoundError:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experiment_packager.py")
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-bytes", required=True, type=int)
    parser.add_argument("--input", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    exit_code, payload = create_package(
        Path(args.root),
        Path(args.output),
        args.max_bytes,
        args.input,
    )
    emit(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
