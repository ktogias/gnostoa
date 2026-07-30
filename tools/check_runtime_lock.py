from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_common import (
    KnowledgeFormatError,
    load_profile,
    load_yaml,
    toolkit_root,
)


UNENFORCED_REVISIONS = {"", "development", "unknown"}
PUBLIC_SURFACE_PATHS = (
    ".devcontainer",
    "ci",
    "core",
    "guidance",
    "policy",
    "requirements",
    "schemas",
    "templates",
    "tools",
    "Dockerfile",
    "pyproject.toml",
)
IGNORED_PARTS = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def public_surface_digest(root: Path) -> str:
    root = root.resolve()
    files: list[Path] = []
    for reference in PUBLIC_SURFACE_PATHS:
        path = root / reference
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*") if candidate.is_file())

    digest = hashlib.sha256()
    included = 0
    for path in sorted(set(files), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.suffix.casefold() in IGNORED_SUFFIXES:
            continue
        encoded_path = relative.as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        included += 1

    if included == 0:
        raise KnowledgeFormatError(
            f"No toolkit public-surface files found under {root}"
        )
    return f"sha256:{digest.hexdigest()}"


def check_runtime_lock(
    lock_path: Path,
    project_root: Path,
    expected_revision: str | None = None,
    expected_image: str | None = None,
    schema_path: Path | None = None,
    runtime_root: Path | None = None,
) -> list[str]:
    root = project_root.resolve()
    lock = load_yaml(lock_path.resolve())
    schema = (
        schema_path.resolve()
        if schema_path
        else toolkit_root() / "schemas" / "toolkit-lock.schema.json"
    )
    issues: list[str] = []

    errors = sorted(
        Draft202012Validator(_schema(schema)).iter_errors(lock),
        key=lambda error: list(error.absolute_path),
    )
    for error in errors:
        location = ".".join(str(item) for item in error.absolute_path) or "<root>"
        issues.append(f"{location}: {error.message}")

    toolkit = lock.get("toolkit", {})
    runtime = lock.get("runtime", {})
    if not isinstance(toolkit, dict) or not isinstance(runtime, dict):
        return sorted(set(issues))

    toolkit_revision = toolkit.get("revision")
    runtime_revision = runtime.get("revision")
    if (
        isinstance(toolkit_revision, str)
        and isinstance(runtime_revision, str)
        and toolkit_revision != runtime_revision
    ):
        issues.append(
            "toolkit.revision and runtime.revision do not match: "
            f"{toolkit_revision!r} != {runtime_revision!r}"
        )

    expected = (
        expected_revision
        if expected_revision is not None
        else os.environ.get("KNOWLEDGE_KIT_REVISION", "")
    )
    if (
        expected not in UNENFORCED_REVISIONS
        and isinstance(runtime_revision, str)
        and runtime_revision != expected
    ):
        issues.append(
            f"runtime revision {runtime_revision!r} does not match "
            f"executing image revision {expected!r}"
        )

    executing_image = (
        expected_image
        if expected_image is not None
        else os.environ.get("KNOWLEDGE_KIT_IMAGE", "")
    )
    locked_image = runtime.get("image")
    if (
        executing_image
        and isinstance(locked_image, str)
        and locked_image != executing_image
    ):
        issues.append(
            f"locked runtime image {locked_image!r} does not match "
            f"executing image reference {executing_image!r}"
        )

    source_reference = toolkit.get("source")
    source: Path | None = None
    if isinstance(source_reference, str):
        source = (root / source_reference).resolve()
        try:
            source.relative_to(root)
        except ValueError:
            issues.append(
                f"toolkit.source escapes project root: {source_reference!r}"
            )
            source = None
        else:
            if not source.is_dir():
                issues.append(
                    f"toolkit.source does not exist: {source_reference!r}"
                )
                source = None

    profile_reference = toolkit.get("profile")
    if isinstance(profile_reference, str):
        profile = (root / profile_reference).resolve()
        try:
            profile.relative_to(root)
        except ValueError:
            issues.append(
                f"toolkit.profile escapes project root: {profile_reference!r}"
            )
        else:
            if not profile.is_file():
                issues.append(
                    f"toolkit.profile does not exist: {profile_reference!r}"
                )
            else:
                try:
                    load_profile(profile)
                except KnowledgeFormatError as exc:
                    issues.append(f"toolkit.profile is invalid: {exc}")

    if source is not None:
        executing_root = (
            runtime_root.resolve() if runtime_root else toolkit_root()
        )
        try:
            source_digest = public_surface_digest(source)
            runtime_digest = public_surface_digest(executing_root)
        except (KnowledgeFormatError, OSError) as exc:
            issues.append(f"cannot compare toolkit public surfaces: {exc}")
        else:
            if source_digest != runtime_digest:
                issues.append(
                    "mounted toolkit public surface does not match executing "
                    f"runtime: {source_digest} != {runtime_digest}"
                )

    return sorted(set(issues))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the pinned toolkit source/profile and runtime lock."
    )
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-revision")
    parser.add_argument("--expected-image")
    parser.add_argument("--schema", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        issues = check_runtime_lock(
            args.lock,
            args.project_root,
            args.expected_revision,
            args.expected_image,
            args.schema,
        )
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for issue in issues:
        print(f"ERROR: {issue}")
    if issues:
        return 1

    print(f"OK: toolkit source and runtime lock is valid ({args.lock})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
