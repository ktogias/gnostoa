from __future__ import annotations

import argparse
import hashlib
import json
import os
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


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def _same_stat_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        _same_object(left, right)
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


def _directory_flags() -> int:
    return os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW


def _open_directory(path: Path) -> int:
    return os.open(path, _directory_flags())


def _assert_visible_directory(path: Path, expected: os.stat_result, label: str) -> None:
    try:
        current = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise HandoffError(f"{label}-namespace-changed:{exc}") from exc
    if not stat.S_ISDIR(current.st_mode) or not _same_object(expected, current):
        raise HandoffError(f"{label}-namespace-changed")


def _assert_named_entry(
    parent_fd: int,
    name: str,
    expected: os.stat_result,
    label: str,
) -> None:
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise HandoffError(f"{label}-entry-changed:{exc}") from exc
    if not _same_object(expected, current):
        raise HandoffError(f"{label}-entry-changed")


def _hash_copy_file_fd(
    source_fd: int,
    destination_parent_fd: int,
    destination_name: str,
    expected: os.stat_result,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW
    destination_fd = os.open(
        destination_name,
        flags,
        0o600,
        dir_fd=destination_parent_fd,
    )
    try:
        with os.fdopen(os.dup(source_fd), "rb", closefd=True) as source:
            while True:
                chunk = source.read(_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(destination_fd, view)
                    if written <= 0:
                        raise HandoffError("short-snapshot-write")
                    view = view[written:]
                total += len(chunk)
        os.fsync(destination_fd)
        os.fchmod(destination_fd, _normalized_mode(expected.st_mode))
    except BaseException:
        os.close(destination_fd)
        try:
            os.unlink(destination_name, dir_fd=destination_parent_fd)
        except FileNotFoundError:
            pass
        raise
    else:
        os.close(destination_fd)

    current = os.fstat(source_fd)
    if not _same_stat_identity(expected, current):
        raise HandoffError("source-entry-changed-during-freeze")
    return digest.hexdigest(), total


def _source_members_and_copy_fd(
    source_root: Path, snapshot_fd: int
) -> list[dict[str, object]]:
    root_fd = _open_directory(source_root)
    members: list[dict[str, object]] = []

    def walk(source_dir_fd: int, destination_dir_fd: int, prefix: str) -> None:
        before_directory = os.fstat(source_dir_fd)
        try:
            names = sorted(os.listdir(source_dir_fd), key=_portable_name)
        except OSError as exc:
            raise HandoffError(f"cannot-list-source:{prefix or '.'}:{exc}") from exc

        for name in names:
            _portable_name(name)
            relative = f"{prefix}/{name}" if prefix else name
            try:
                observed = os.stat(name, dir_fd=source_dir_fd, follow_symlinks=False)
            except OSError as exc:
                raise HandoffError(f"cannot-stat-source:{relative}:{exc}") from exc
            mode = _normalized_mode(observed.st_mode)

            if stat.S_ISDIR(observed.st_mode):
                os.mkdir(name, 0o700, dir_fd=destination_dir_fd)
                source_child_fd = os.open(name, _directory_flags(), dir_fd=source_dir_fd)
                destination_child_fd = os.open(
                    name, _directory_flags(), dir_fd=destination_dir_fd
                )
                try:
                    opened = os.fstat(source_child_fd)
                    if not _same_stat_identity(observed, opened):
                        raise HandoffError(f"source-entry-changed:{relative}")
                    members.append(
                        {"path": relative, "type": "directory", "mode": mode}
                    )
                    walk(source_child_fd, destination_child_fd, relative)
                    after_child = os.fstat(source_child_fd)
                    if not _same_stat_identity(opened, after_child):
                        raise HandoffError(f"source-directory-changed:{relative}")
                    os.fchmod(destination_child_fd, mode)
                    os.fsync(destination_child_fd)
                finally:
                    os.close(destination_child_fd)
                    os.close(source_child_fd)
                continue

            if stat.S_ISREG(observed.st_mode):
                source_fd = os.open(
                    name,
                    os.O_RDONLY | _O_NOFOLLOW,
                    dir_fd=source_dir_fd,
                )
                try:
                    opened = os.fstat(source_fd)
                    if not _same_stat_identity(observed, opened):
                        raise HandoffError(f"source-entry-changed:{relative}")
                    digest, size = _hash_copy_file_fd(
                        source_fd,
                        destination_dir_fd,
                        name,
                        opened,
                    )
                    post_path = os.stat(
                        name,
                        dir_fd=source_dir_fd,
                        follow_symlinks=False,
                    )
                    if not _same_stat_identity(opened, post_path):
                        raise HandoffError(f"source-entry-changed:{relative}")
                finally:
                    os.close(source_fd)
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
                    target = os.readlink(name, dir_fd=source_dir_fd)
                    post_path = os.stat(
                        name,
                        dir_fd=source_dir_fd,
                        follow_symlinks=False,
                    )
                except OSError as exc:
                    raise HandoffError(
                        f"cannot-read-source-symlink:{relative}:{exc}"
                    ) from exc
                if not _same_stat_identity(observed, post_path):
                    raise HandoffError(f"source-entry-changed:{relative}")
                os.symlink(target, name, dir_fd=destination_dir_fd)
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

        after_directory = os.fstat(source_dir_fd)
        if not _same_stat_identity(before_directory, after_directory):
            raise HandoffError(f"source-directory-changed:{prefix or '.'}")

    try:
        walk(root_fd, snapshot_fd, "")
    finally:
        os.close(root_fd)
    return members


def _snapshot_members(snapshot_root: Path) -> list[dict[str, object]]:
    root_fd = _open_directory(snapshot_root)
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
                members.append({"path": relative, "type": "directory", "mode": mode})
                child_fd = os.open(name, _directory_flags(), dir_fd=directory_fd)
                try:
                    opened = os.fstat(child_fd)
                    if not _same_object(observed, opened):
                        raise HandoffError(f"snapshot-entry-changed:{relative}")
                    walk(child_fd, relative)
                finally:
                    os.close(child_fd)
                continue
            if stat.S_ISREG(observed.st_mode):
                source_fd = os.open(
                    name,
                    os.O_RDONLY | _O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                try:
                    opened = os.fstat(source_fd)
                    if not _same_object(observed, opened):
                        raise HandoffError(f"snapshot-entry-changed:{relative}")
                    digest = hashlib.sha256()
                    total = 0
                    with os.fdopen(os.dup(source_fd), "rb", closefd=True) as source:
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


def _clear_directory_fd(directory_fd: int) -> None:
    for name in os.listdir(directory_fd):
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(observed.st_mode):
            child_fd = os.open(name, _directory_flags(), dir_fd=directory_fd)
            try:
                _clear_directory_fd(child_fd)
            finally:
                os.close(child_fd)
            os.rmdir(name, dir_fd=directory_fd)
        else:
            os.unlink(name, dir_fd=directory_fd)


def _remove_created_bundle(parent_fd: int, bundle_name: str) -> None:
    try:
        bundle_fd = os.open(bundle_name, _directory_flags(), dir_fd=parent_fd)
    except FileNotFoundError:
        return
    try:
        _clear_directory_fd(bundle_fd)
    finally:
        os.close(bundle_fd)
    try:
        os.rmdir(bundle_name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


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
    parent_fd = -1
    bundle_fd = -1
    snapshot_fd = -1
    created = False
    try:
        inputs = parse_input_identities(
            input_values,
            require_nonempty=True,
            reserved=frozenset({"handoff"}),
        )
        source_root = _lexical_resolved_directory(source, "source-root")
        bundle_parent = _resolved_parent(bundle, "bundle")
        _portable_name(bundle.name)
        bundle_path = bundle_parent / bundle.name
        if _is_within(source_root, bundle_path):
            raise HandoffError("bundle-inside-source-root")

        parent_fd = _open_directory(bundle_parent)
        parent_identity = os.fstat(parent_fd)
        _assert_visible_directory(bundle_parent, parent_identity, "bundle-parent")
        try:
            os.stat(bundle.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise HandoffError("bundle-already-exists")

        os.mkdir(bundle.name, 0o700, dir_fd=parent_fd)
        created = True
        _assert_visible_directory(bundle_parent, parent_identity, "bundle-parent")

        bundle_fd = os.open(bundle.name, _directory_flags(), dir_fd=parent_fd)
        bundle_identity = os.fstat(bundle_fd)
        _assert_named_entry(parent_fd, bundle.name, bundle_identity, "bundle")

        os.mkdir(SNAPSHOT_ROOT_NAME, 0o700, dir_fd=bundle_fd)
        snapshot_fd = os.open(SNAPSHOT_ROOT_NAME, _directory_flags(), dir_fd=bundle_fd)
        members = _source_members_and_copy_fd(source_root, snapshot_fd)
        os.fsync(snapshot_fd)

        manifest = _build_manifest(members, inputs)
        manifest_bytes = canonical_json_bytes(manifest)

        _assert_visible_directory(bundle_parent, parent_identity, "bundle-parent")
        _assert_named_entry(parent_fd, bundle.name, bundle_identity, "bundle")

        manifest_fd = os.open(
            MANIFEST_NAME,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
            0o600,
            dir_fd=bundle_fd,
        )
        try:
            view = memoryview(manifest_bytes)
            while view:
                written = os.write(manifest_fd, view)
                if written <= 0:
                    raise HandoffError("short-manifest-write")
                view = view[written:]
            os.fsync(manifest_fd)
        finally:
            os.close(manifest_fd)
        os.fsync(bundle_fd)
        os.fsync(parent_fd)

        _assert_visible_directory(bundle_parent, parent_identity, "bundle-parent")
        _assert_named_entry(parent_fd, bundle.name, bundle_identity, "bundle")

        return 0, {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "FROZEN",
            "handoff_sha256": sha256_bytes(manifest_bytes),
            "tree_sha256": cast(str, manifest["tree_sha256"]),
            "members": len(members),
        }
    except (OSError, EvidenceError, HandoffError) as exc:
        if created and parent_fd >= 0:
            try:
                if snapshot_fd >= 0:
                    os.close(snapshot_fd)
                    snapshot_fd = -1
                if bundle_fd >= 0:
                    os.close(bundle_fd)
                    bundle_fd = -1
                _remove_created_bundle(parent_fd, bundle.name)
            except OSError:
                pass
        return 2, {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "BLOCKED",
            "reasons": [f"{type(exc).__name__}:{exc}"],
        }
    finally:
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        if bundle_fd >= 0:
            os.close(bundle_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HandoffError(f"duplicate-manifest-key:{key}")
        result[key] = value
    return result


def _load_manifest_bytes(path: Path) -> tuple[bytes, dict[str, object]]:
    lexical = Path(os.path.abspath(path))
    if lexical.name != MANIFEST_NAME:
        raise HandoffError("handoff-manifest-name-invalid")
    if path.is_symlink():
        raise HandoffError("handoff-manifest-symlink-forbidden")
    try:
        raw = lexical.read_bytes()
    except OSError as exc:
        raise HandoffError(f"cannot-read-handoff:{exc}") from exc
    try:
        parsed = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HandoffError(f"cannot-parse-handoff:{exc}") from exc
    if not isinstance(parsed, dict):
        raise HandoffError("handoff-must-be-a-mapping")
    return raw, cast(dict[str, object], parsed)


def _validate_member_shape(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise HandoffError("handoff-members-must-be-a-list")
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise HandoffError("handoff-member-must-be-a-mapping")
        member = cast(dict[str, object], item)
        path = member.get("path")
        kind = member.get("type")
        mode = member.get("mode")
        if not isinstance(path, str) or not path or path.startswith("/"):
            raise HandoffError("handoff-member-path-invalid")
        parts = path.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise HandoffError("handoff-member-path-invalid")
        for part in parts:
            _portable_name(part)
        if path in seen:
            raise HandoffError("handoff-member-path-duplicate")
        seen.add(path)
        if kind not in {"directory", "file", "symlink"}:
            raise HandoffError("handoff-member-type-invalid")
        if not isinstance(mode, int) or isinstance(mode, bool):
            raise HandoffError("handoff-member-mode-invalid")
        if kind == "file":
            size = member.get("bytes")
            digest = member.get("sha256")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise HandoffError("handoff-member-bytes-invalid")
            if not isinstance(digest, str):
                raise HandoffError("handoff-member-sha256-invalid")
            require_sha256(digest, field="handoff-member-sha256")
        elif kind == "symlink":
            if not isinstance(member.get("target"), str):
                raise HandoffError("handoff-member-target-invalid")
        result.append(dict(member))
    paths = [cast(str, item["path"]) for item in result]
    if paths != sorted(paths, key=lambda value: value.encode("utf-8")):
        # Depth-first ordering places a directory before its children; exact
        # equality with byte sort is not required. Recompute below is authority.
        pass
    return tuple(result)


def load_verified_handoff(path: Path) -> VerifiedHandoff:
    raw, manifest = _load_manifest_bytes(path)
    if manifest.get("schema") != HANDOFF_SCHEMA:
        raise HandoffError("unsupported-handoff-schema")
    if manifest.get("snapshot") != SNAPSHOT_ROOT_NAME:
        raise HandoffError("unsupported-handoff-snapshot")
    tree_sha256 = manifest.get("tree_sha256")
    if not isinstance(tree_sha256, str):
        raise HandoffError("handoff-tree-sha256-invalid")
    require_sha256(tree_sha256, field="handoff-tree-sha256")
    members = _validate_member_shape(manifest.get("members"))

    producer = manifest.get("producer")
    if not isinstance(producer, dict):
        raise HandoffError("handoff-producer-invalid")
    producer_map = cast(dict[str, object], producer)
    if producer_map.get("id") != HANDOFF_PRODUCER_ID:
        raise HandoffError("handoff-producer-id-invalid")
    if producer_map.get("version") != HANDOFF_PRODUCER_VERSION:
        raise HandoffError("handoff-producer-version-invalid")
    config_sha = producer_map.get("config_sha256")
    if not isinstance(config_sha, str):
        raise HandoffError("handoff-producer-config-invalid")
    require_sha256(config_sha, field="handoff-producer-config")
    if config_sha != _handoff_config_digest():
        raise HandoffError("handoff-producer-config-mismatch")

    try:
        inputs = parse_identity_mappings(
            manifest.get("inputs"),
            require_nonempty=True,
        )
        if any(item.id == "handoff" for item in inputs):
            raise HandoffError("reserved-input-identity")
    except EvidenceError as exc:
        raise HandoffError(str(exc)) from exc

    manifest_path = Path(os.path.abspath(path))
    bundle_root = manifest_path.parent
    snapshot_root = bundle_root / SNAPSHOT_ROOT_NAME
    try:
        observed_members = _snapshot_members(snapshot_root)
    except OSError as exc:
        raise HandoffError(f"snapshot-unavailable:{exc}") from exc
    if observed_members != list(members):
        raise HandoffError("handoff-snapshot-members-mismatch")
    observed_tree_sha = sha256_bytes(canonical_json_bytes(observed_members))
    if observed_tree_sha != tree_sha256:
        raise HandoffError("handoff-tree-sha256-mismatch")

    return VerifiedHandoff(
        manifest_path=manifest_path,
        bundle_root=bundle_root,
        snapshot_root=snapshot_root,
        manifest_sha256=sha256_bytes(raw),
        tree_sha256=tree_sha256,
        members=members,
        inputs=inputs,
    )


def command_freeze(args: argparse.Namespace) -> int:
    code, payload = freeze_handoff(
        Path(cast(str, args.root)),
        Path(cast(str, args.bundle)),
        cast(list[str], args.input),
    )
    _emit(payload)
    return code


def command_verify(args: argparse.Namespace) -> int:
    try:
        verified = load_verified_handoff(Path(cast(str, args.handoff)))
    except (OSError, EvidenceError, HandoffError) as exc:
        _emit(
            {
                "schema": HANDOFF_RESULT_SCHEMA,
                "status": "BLOCKED",
                "reasons": [f"{type(exc).__name__}:{exc}"],
            }
        )
        return 2
    _emit(
        {
            "schema": HANDOFF_RESULT_SCHEMA,
            "status": "VERIFIED",
            "handoff_sha256": verified.manifest_sha256,
            "tree_sha256": verified.tree_sha256,
            "members": len(verified.members),
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experiment_handoff.py")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--root", required=True)
    freeze.add_argument("--bundle", required=True)
    freeze.add_argument("--input", action="append", default=[])
    freeze.set_defaults(handler=command_freeze)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--handoff", required=True)
    verify.set_defaults(handler=command_verify)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = cast(object, getattr(args, "handler"))
    if not callable(handler):
        raise HandoffError("handoff-handler-invalid")
    return cast(int, handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
