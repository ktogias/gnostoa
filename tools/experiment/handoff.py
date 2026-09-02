from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .evidence import (
    EvidenceError,
    InputIdentity,
    canonical_json_bytes,
    configuration_digest,
    parse_identity_mappings,
    parse_input_identities,
    producer_record,
    require_sha256,
    sha256_bytes,
)

HANDOFF_SCHEMA = "gnostoa-experiment-handoff/v1"
HANDOFF_RESULT_SCHEMA = "gnostoa-experiment-handoff-result/v1"
HANDOFF_PRODUCER_ID = "gnostoa-experiment-handoff"
HANDOFF_PRODUCER_VERSION = "1"
SNAPSHOT_ROOT_NAME = "tree"
MANIFEST_NAME = "handoff.json"
_CHUNK_SIZE = 1024 * 1024
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class HandoffError(RuntimeError):
    """Raised when a frozen handoff cannot be created or verified."""


@dataclass(frozen=True, slots=True)
class VerifiedHandoff:
    manifest_path: Path
    bundle_root: Path
    snapshot_root: Path
    manifest_sha256: str
    tree_sha256: str
    members: tuple[dict[str, object], ...]
    inputs: tuple[InputIdentity, ...]


def _emit(payload: Mapping[str, object]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")))


def _same_stat_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _lexical_resolved_directory(path: Path, label: str) -> Path:
    lexical = Path(os.path.abspath(path))
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise HandoffError(f"{label}-unavailable:{exc}") from exc
    if resolved != lexical or not resolved.is_dir():
        raise HandoffError(f"{label}-must-be-resolved-directory")
    return resolved


def _resolved_parent(path: Path, label: str) -> Path:
    lexical = Path(os.path.abspath(path.parent))
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise HandoffError(f"{label}-parent-unavailable:{exc}") from exc
    if resolved != lexical or not resolved.is_dir():
        raise HandoffError(f"{label}-parent-must-be-resolved-directory")
    return resolved


def _is_within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _portable_name(name: str) -> bytes:
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise HandoffError("source-name-not-portable-utf8") from exc
    if not name or name in {".", ".."} or "/" in name or "\x00" in name:
        raise HandoffError("source-name-not-portable")
    return encoded


def _normalized_mode(mode: int) -> int:
    if stat.S_ISDIR(mode):
        return 0o755
    if stat.S_ISREG(mode):
        return 0o755 if mode & 0o111 else 0o644
    if stat.S_ISLNK(mode):
        return 0o777
    raise HandoffError("unsupported-source-entry-type")


def _hash_copy_file(
    source_fd: int,
    destination: Path,
    expected: os.stat_result,
) -> tuple[str, int]:
    import hashlib

    digest = hashlib.sha256()
    total = 0
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if _O_NOFOLLOW:
        flags |= _O_NOFOLLOW
    destination_fd = os.open(destination, flags, 0o600)
    try:
        with (
            os.fdopen(os.dup(source_fd), "rb", closefd=True) as source,
            os.fdopen(destination_fd, "wb", closefd=True) as target,
        ):
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                target.write(chunk)
                total += len(chunk)
            target.flush()
            os.fsync(target.fileno())
    except BaseException:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise
    current = os.fstat(source_fd)
    if not _same_stat_identity(expected, current):
        raise HandoffError("source-entry-changed-during-freeze")
    return digest.hexdigest(), total


def _source_members_and_copy(
    source_root: Path,
    snapshot_root: Path,
) -> list[dict[str, object]]:
    root_flags = os.O_RDONLY | _O_DIRECTORY
    if _O_NOFOLLOW:
        root_flags |= _O_NOFOLLOW
    root_fd = os.open(source_root, root_flags)
    members: list[dict[str, object]] = []

    def walk(directory_fd: int, destination: Path, prefix: str) -> None:
        before_directory = os.fstat(directory_fd)
        try:
            names = sorted(os.listdir(directory_fd), key=_portable_name)
        except OSError as exc:
            raise HandoffError(f"cannot-list-source:{prefix or '.'}:{exc}") from exc

        for name in names:
            _portable_name(name)
            relative = f"{prefix}/{name}" if prefix else name
            try:
                observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            except OSError as exc:
                raise HandoffError(f"cannot-stat-source:{relative}:{exc}") from exc
            mode = _normalized_mode(observed.st_mode)
            destination_path = destination / name

            if stat.S_ISDIR(observed.st_mode):
                os.mkdir(destination_path, 0o700)
                flags = os.O_RDONLY | _O_DIRECTORY
                if _O_NOFOLLOW:
                    flags |= _O_NOFOLLOW
                try:
                    child_fd = os.open(name, flags, dir_fd=directory_fd)
                except OSError as exc:
                    raise HandoffError(
                        f"cannot-open-source-directory:{relative}:{exc}"
                    ) from exc
                try:
                    opened = os.fstat(child_fd)
                    if not _same_stat_identity(observed, opened):
                        raise HandoffError(f"source-entry-changed:{relative}")
                    members.append(
                        {"path": relative, "type": "directory", "mode": mode}
                    )
                    walk(child_fd, destination_path, relative)
                    after_child = os.fstat(child_fd)
                    if not _same_stat_identity(opened, after_child):
                        raise HandoffError(f"source-directory-changed:{relative}")
                finally:
                    os.close(child_fd)
                os.chmod(destination_path, mode, follow_symlinks=False)
                continue

            if stat.S_ISREG(observed.st_mode):
                flags = os.O_RDONLY
                if _O_NOFOLLOW:
                    flags |= _O_NOFOLLOW
                try:
                    source_fd = os.open(name, flags, dir_fd=directory_fd)
                except OSError as exc:
                    raise HandoffError(f"cannot-open-source-file:{relative}:{exc}") from exc
                try:
                    opened = os.fstat(source_fd)
                    if not _same_stat_identity(observed, opened):
                        raise HandoffError(f"source-entry-changed:{relative}")
                    digest, size = _hash_copy_file(source_fd, destination_path, opened)
                    post_path = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    if not _same_stat_identity(opened, post_path):
                        raise HandoffError(f"source-entry-changed:{relative}")
                finally:
                    os.close(source_fd)
                os.chmod(destination_path, mode, follow_symlinks=False)
                members.append(
                    {
                        "path": relative,
                        "type": "file",
                        "mode": mode,
                        "bytes": size,
                        "sha256": digest,
                    }
                )
                continue

            if stat.S_ISLNK(observed.st_mode):
                try:
                    target = os.readlink(name, dir_fd=directory_fd)
                    post_path = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise HandoffError(
                        f"cannot-read-source-symlink:{relative}:{exc}"
                    ) from exc
                if not _same_stat_identity(observed, post_path):
                    raise HandoffError(f"source-entry-changed:{relative}")
                os.symlink(target, destination_path)
                members.append(
                    {
                        "path": relative,
                        "type": "symlink",
                        "mode": mode,
                        "target": target,
                    }
                )
                continue

            raise HandoffError(f"unsupported-source-entry:{relative}")

        after_directory = os.fstat(directory_fd)
        if not _same_stat_identity(before_directory, after_directory):
            raise HandoffError(f"source-directory-changed:{prefix or '.'}")

    try:
        walk(root_fd, snapshot_root, "")
    finally:
        os.close(root_fd)
    return members


def _snapshot_members(snapshot_root: Path) -> list[dict[str, object]]:
    import hashlib

    root_flags = os.O_RDONLY | _O_DIRECTORY
    if _O_NOFOLLOW:
        root_flags |= _O_NOFOLLOW
    root_fd = os.open(snapshot_root, root_flags)
    members: list[dict[str, object]] = []

    def walk(directory_fd: int, prefix: str) -> None:
        try:
            names = sorted(os.listdir(directory_fd), key=_portable_name)
        except OSError as exc:
            raise HandoffError(f"cannot-list-snapshot:{prefix or '.'}:{exc}") from exc
        for name in names:
            _portable_name(name)
            relative = f"{prefix}/{name}" if prefix else name
            observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            mode = _normalized_mode(observed.st_mode)
            if stat.S_ISDIR(observed.st_mode):
                members.append(
                    {"path": relative, "type": "directory", "mode": mode}
                )
                flags = os.O_RDONLY | _O_DIRECTORY
                if _O_NOFOLLOW:
                    flags |= _O_NOFOLLOW
                child_fd = os.open(name, flags, dir_fd=directory_fd)
                try:
                    opened = os.fstat(child_fd)
                    if not _same_stat_identity(observed, opened):
                        raise HandoffError(f"snapshot-entry-changed:{relative}")
                    walk(child_fd, relative)
                finally:
                    os.close(child_fd)
                continue
            if stat.S_ISREG(observed.st_mode):
                flags = os.O_RDONLY
                if _O_NOFOLLOW:
                    flags |= _O_NOFOLLOW
                source_fd = os.open(name, flags, dir_fd=directory_fd)
                try:
                    opened = os.fstat(source_fd)
                    if not _same_stat_identity(observed, opened):
                        raise HandoffError(f"snapshot-entry-changed:{relative}")
                    digest = hashlib.sha256()
                    total = 0
                    with os.fdopen(os.dup(source_fd), "rb") as source:
                        while True:
                            chunk = source.read(_CHUNK_SIZE)
                            if not chunk:
                                break
                            digest.update(chunk)
                            total += len(chunk)
                    after = os.fstat(source_fd)
                    if not _same_stat_identity(opened, after):
                        raise HandoffError(f"snapshot-entry-changed:{relative}")
                finally:
                    os.close(source_fd)
                members.append(
                    {
                        "path": relative,
                        "type": "file",
                        "mode": mode,
                        "bytes": total,
                        "sha256": digest.hexdigest(),
                    }
                )
                continue
            if stat.S_ISLNK(observed.st_mode):
                target = os.readlink(name, dir_fd=directory_fd)
                after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if not _same_stat_identity(observed, after):
                    raise HandoffError(f"snapshot-entry-changed:{relative}")
                members.append(
                    {
                        "path": relative,
                        "type": "symlink",
                        "mode": mode,
                        "target": target,
                    }
                )
                continue
            raise HandoffError(f"unsupported-snapshot-entry:{relative}")

    try:
        walk(root_fd, "")
    finally:
        os.close(root_fd)
    return members


def _handoff_config_digest() -> str:
    return configuration_digest(
        {
            "snapshot": "copy-descriptor-bound-v1",
            "membership": "portable-utf8-byte-order-depth-first-v1",
            "regular_files": "o-nofollow-fstat-copy-hash-v1",
            "symlinks": "preserve-without-dereference-v1",
            "manifest": "canonical-json-path-neutral-v1",
        }
    )


def _build_manifest(
    members: Sequence[dict[str, object]],
    inputs: Sequence[InputIdentity],
) -> dict[str, object]:
    member_list = [dict(member) for member in members]
    tree_sha256 = sha256_bytes(canonical_json_bytes(member_list))
    return {
        "schema": HANDOFF_SCHEMA,
        "snapshot": SNAPSHOT_ROOT_NAME,
        "tree_sha256": tree_sha256,
        "members": member_list,
        "producer": producer_record(
            HANDOFF_PRODUCER_ID,
            HANDOFF_PRODUCER_VERSION,
            _handoff_config_digest(),
        ),
        "inputs": [item.as_dict() for item in inputs],
    }


def freeze_handoff(
    source: Path,
    bundle: Path,
    input_values: Sequence[str],
) -> tuple[int, dict[str, object]]:
    try:
        inputs = parse_input_identities(
            input_values,
            require_nonempty=True,
            reserved=frozenset({"handoff"}),
        )
        source_root = _lexical_resolved_directory(source, "source-root")
        bundle_parent = _resolved_parent(bundle, "bundle")
        bundle_path = bundle_parent / bundle.name
        if _is_within(source_root, bundle_path):
            raise HandoffError("bundle-inside-source-root")
        if bundle_path.exists() or bundle_path.is_symlink():
            raise HandoffError("bundle-already-exists")
    except (EvidenceError, HandoffError) as exc:
        return 2, {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "BLOCKED",
            "reasons": [str(exc)],
        }

    created = False
    try:
        os.mkdir(bundle_path, 0o700)
        created = True
        snapshot_root = bundle_path / SNAPSHOT_ROOT_NAME
        os.mkdir(snapshot_root, 0o700)
        members = _source_members_and_copy(source_root, snapshot_root)
        manifest = _build_manifest(members, inputs)
        manifest_bytes = canonical_json_bytes(manifest)
        manifest_path = bundle_path / MANIFEST_NAME
        with manifest_path.open("xb") as output:
            output.write(manifest_bytes)
            output.flush()
            os.fsync(output.fileno())
        return 0, {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "FROZEN",
            "handoff_sha256": sha256_bytes(manifest_bytes),
            "tree_sha256": cast(str, manifest["tree_sha256"]),
            "members": len(members),
        }
    except (OSError, EvidenceError, HandoffError) as exc:
        if created:
            try:
                shutil.rmtree(bundle_path)
            except OSError:
                pass
        return 2, {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "BLOCKED",
            "reasons": [f"{type(exc).__name__}:{exc}"],
        }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HandoffError(f"duplicate-manifest-key:{key}")
        result[key] = value
    return result


def _load_manifest(path: Path) -> tuple[dict[str, object], bytes]:
    lexical = Path(os.path.abspath(path))
    try:
        resolved = lexical.resolve(strict=True)
    except OSError as exc:
        raise HandoffError(f"handoff-unavailable:{exc}") from exc
    if resolved != lexical or not resolved.is_file():
        raise HandoffError("handoff-must-be-resolved-regular-file")
    raw = resolved.read_bytes()
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HandoffError(f"handoff-json-invalid:{exc}") from exc
    if not isinstance(parsed, dict):
        raise HandoffError("handoff-must-be-a-mapping")
    manifest = cast(dict[str, object], parsed)
    if raw != canonical_json_bytes(manifest):
        raise HandoffError("handoff-not-canonical")
    return manifest, raw


def load_verified_handoff(path: Path) -> VerifiedHandoff:
    manifest, raw = _load_manifest(path)
    if manifest.get("schema") != HANDOFF_SCHEMA:
        raise HandoffError("unsupported-handoff-schema")
    if manifest.get("snapshot") != SNAPSHOT_ROOT_NAME:
        raise HandoffError("unsupported-handoff-snapshot")

    raw_members = manifest.get("members")
    if not isinstance(raw_members, list) or not all(
        isinstance(item, dict) for item in raw_members
    ):
        raise HandoffError("handoff-members-invalid")
    members = tuple(dict(cast(dict[str, object], item)) for item in raw_members)
    raw_tree_sha = manifest.get("tree_sha256")
    if not isinstance(raw_tree_sha, str):
        raise HandoffError("handoff-tree-sha256-invalid")
    require_sha256(raw_tree_sha, field="tree-sha256")
    if sha256_bytes(canonical_json_bytes(list(members))) != raw_tree_sha:
        raise HandoffError("handoff-member-list-digest-mismatch")

    producer = manifest.get("producer")
    if not isinstance(producer, dict):
        raise HandoffError("handoff-producer-invalid")
    producer_map = cast(dict[str, object], producer)
    if (
        producer_map.get("id") != HANDOFF_PRODUCER_ID
        or producer_map.get("version") != HANDOFF_PRODUCER_VERSION
        or producer_map.get("config_sha256") != _handoff_config_digest()
    ):
        raise HandoffError("handoff-producer-mismatch")

    inputs = tuple(parse_identity_mappings(manifest.get("inputs")))
    bundle_root = path.parent.resolve(strict=True)
    snapshot_root = bundle_root / SNAPSHOT_ROOT_NAME
    if not snapshot_root.is_dir() or snapshot_root.is_symlink():
        raise HandoffError("handoff-snapshot-unavailable")
    observed_members = _snapshot_members(snapshot_root)
    if observed_members != list(members):
        raise HandoffError("handoff-snapshot-mismatch")

    return VerifiedHandoff(
        manifest_path=path.resolve(strict=True),
        bundle_root=bundle_root,
        snapshot_root=snapshot_root,
        manifest_sha256=sha256_bytes(raw),
        tree_sha256=raw_tree_sha,
        members=members,
        inputs=inputs,
    )


def verify_handoff(path: Path) -> tuple[int, dict[str, object]]:
    try:
        verified = load_verified_handoff(path)
    except (OSError, EvidenceError, HandoffError) as exc:
        return 2, {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "BLOCKED",
            "reasons": [f"{type(exc).__name__}:{exc}"],
        }
    return 0, {
        "schema": HANDOFF_RESULT_SCHEMA,
        "status": "VERIFIED",
        "handoff_sha256": verified.manifest_sha256,
        "tree_sha256": verified.tree_sha256,
        "members": len(verified.members),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experiment_handoff.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--root", required=True)
    freeze.add_argument("--bundle", required=True)
    freeze.add_argument("--input", action="append", default=[])
    verify = subparsers.add_parser("verify")
    verify.add_argument("--handoff", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "freeze":
        exit_code, payload = freeze_handoff(
            Path(cast(str, args.root)),
            Path(cast(str, args.bundle)),
            cast(list[str], args.input),
        )
    else:
        exit_code, payload = verify_handoff(Path(cast(str, args.handoff)))
    _emit(payload)
    return exit_code
