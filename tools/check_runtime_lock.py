from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator

from .knowledge_common import (
    KnowledgeFormatError,
    load_profile,
    load_yaml,
    toolkit_root,
)
from .repository_scope import SOURCE_MANIFEST, RepositoryScopeError, candidate_paths

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
# Generated state that is never public source. Each entry is here because it was
# measured drifting the digest, not because it looked like a cache.
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}

ObservationStatus = Literal["PASS", "FAIL", "UNKNOWN"]


@dataclass(frozen=True)
class RuntimeImageObservation:
    status: ObservationStatus
    declared_image: str | None
    observed_image: str | None


@dataclass(frozen=True)
class RuntimeLockEvaluation:
    declaration_issues: tuple[str, ...]
    image_observation: RuntimeImageObservation

    @property
    def issues(self) -> tuple[str, ...]:
        issues = list(self.declaration_issues)
        observation = self.image_observation
        if observation.status == "FAIL":
            issues.append(
                f"locked runtime image {observation.declared_image!r} does not match "
                f"executing image reference {observation.observed_image!r}"
            )
        return tuple(sorted(set(issues)))


def _runtime_image_observation(
    runtime: object,
    expected_image: str | None,
) -> RuntimeImageObservation:
    observed = (
        expected_image
        if expected_image is not None
        else os.environ.get("KNOWLEDGE_KIT_IMAGE", "")
    )
    declared = runtime.get("image") if isinstance(runtime, dict) else None
    declared_image = declared if isinstance(declared, str) else None
    observed_image = observed if observed else None
    if observed_image is None or declared_image is None:
        return RuntimeImageObservation(
            status="UNKNOWN",
            declared_image=declared_image,
            observed_image=observed_image,
        )
    return RuntimeImageObservation(
        status="PASS" if declared_image == observed_image else "FAIL",
        declared_image=declared_image,
        observed_image=observed_image,
    )


def _schema(path: Path) -> dict[str, Any]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise KnowledgeFormatError(f"Schema must be a mapping in {path}")
    return schema


def _declares_candidate(root: Path) -> bool:
    """Report whether the root declares an authoritative candidate.

    Presence is decided by the marker alone, never by whether reading it
    succeeds. A marker that is present but unusable is a broken authoritative
    source, and must fail rather than be mistaken for a metadata-free one.
    """

    for marker in (".git", SOURCE_MANIFEST):
        try:
            (root / marker).lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise KnowledgeFormatError(
                f"Cannot inspect toolkit source authority {root / marker}: {exc}"
            ) from exc
        return True
    return False


def _within_public_surface(relative: Path) -> bool:
    posix = relative.as_posix()
    return any(
        posix == reference or posix.startswith(f"{reference}/")
        for reference in PUBLIC_SURFACE_PATHS
    )


def _declared_surface_paths(root: Path) -> list[Path]:
    """Public-surface membership taken from the declared candidate."""

    try:
        declared = candidate_paths(root)
    except RepositoryScopeError as exc:
        raise KnowledgeFormatError(
            f"Cannot read the declared toolkit source candidate in {root}: {exc}"
        ) from exc
    return [relative for relative in declared if _within_public_surface(relative)]


def _physical_surface_paths(root: Path) -> list[Path]:
    """Public-surface membership taken from the extracted files themselves.

    Used only when the root declares no candidate. Nothing then distinguishes an
    original release member from a later local file, so every non-ignored file
    under the declared public surface counts as source presented for validation.
    """

    files: list[Path] = []
    for reference in PUBLIC_SURFACE_PATHS:
        path = root / reference
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                candidate for candidate in path.rglob("*") if candidate.is_file()
            )
    return [path.relative_to(root) for path in files]


def public_surface_digest(root: Path) -> str:
    root = root.resolve()
    declared = _declares_candidate(root)
    selected = (
        _declared_surface_paths(root) if declared else _physical_surface_paths(root)
    )

    digest = hashlib.sha256()
    included = 0
    for relative in sorted(set(selected), key=lambda item: item.as_posix()):
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if relative.suffix.casefold() in IGNORED_SUFFIXES:
            continue
        path = root / relative
        if declared and not path.is_file():
            # The candidate says this path is public source. Digesting the rest
            # under the same identity would assert a source that is not present.
            raise KnowledgeFormatError(
                f"Declared toolkit public-surface path is missing or unreadable: "
                f"{relative.as_posix()}"
            )
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


def evaluate_runtime_lock(
    lock_path: Path,
    project_root: Path,
    expected_revision: str | None = None,
    expected_image: str | None = None,
    schema_path: Path | None = None,
    runtime_root: Path | None = None,
) -> RuntimeLockEvaluation:
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
    image_observation = _runtime_image_observation(runtime, expected_image)
    if not isinstance(toolkit, dict) or not isinstance(runtime, dict):
        return RuntimeLockEvaluation(tuple(sorted(set(issues))), image_observation)

    toolkit_revision = toolkit.get("revision")
    locked_surface_digest = toolkit.get("public_surface_digest")
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

    source_reference = toolkit.get("source")
    source: Path | None = None
    if isinstance(source_reference, str):
        source = (root / source_reference).resolve()
        try:
            source.relative_to(root)
        except ValueError:
            issues.append(f"toolkit.source escapes project root: {source_reference!r}")
            source = None
        else:
            if not source.is_dir():
                issues.append(f"toolkit.source does not exist: {source_reference!r}")
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
                issues.append(f"toolkit.profile does not exist: {profile_reference!r}")
            else:
                try:
                    load_profile(profile, project_root=root)
                except KnowledgeFormatError as exc:
                    issues.append(f"toolkit.profile is invalid: {exc}")

    if source is not None:
        executing_root = runtime_root.resolve() if runtime_root else toolkit_root()
        try:
            source_digest = public_surface_digest(source)
            runtime_digest = public_surface_digest(executing_root)
        except (KnowledgeFormatError, OSError) as exc:
            issues.append(f"cannot compare toolkit public surfaces: {exc}")
        else:
            if (
                isinstance(locked_surface_digest, str)
                and source_digest != locked_surface_digest
            ):
                issues.append(
                    "mounted toolkit public surface does not match locked "
                    f"digest: {source_digest} != {locked_surface_digest}"
                )
            if source_digest != runtime_digest:
                issues.append(
                    "mounted toolkit public surface does not match executing "
                    f"runtime: {source_digest} != {runtime_digest}"
                )

    return RuntimeLockEvaluation(tuple(sorted(set(issues))), image_observation)


def check_runtime_lock(
    lock_path: Path,
    project_root: Path,
    expected_revision: str | None = None,
    expected_image: str | None = None,
    schema_path: Path | None = None,
    runtime_root: Path | None = None,
) -> list[str]:
    evaluation = evaluate_runtime_lock(
        lock_path,
        project_root,
        expected_revision,
        expected_image,
        schema_path,
        runtime_root,
    )
    return list(evaluation.issues)


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


def _digest_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute the deterministic toolkit public-surface digest."
    )
    parser.add_argument("--root", type=Path, required=True)
    return parser


def surface_digest_main(argv: list[str] | None = None) -> int:
    args = _digest_parser().parse_args(argv)
    try:
        print(public_surface_digest(args.root))
    except (KnowledgeFormatError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evaluation = evaluate_runtime_lock(
            args.lock,
            args.project_root,
            args.expected_revision,
            args.expected_image,
            args.schema,
        )
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for issue in evaluation.declaration_issues:
        print(f"ERROR: {issue}")
    if not evaluation.declaration_issues:
        print(
            f"PASS: runtime-lock declaration and source binding are valid ({args.lock})"
        )

    observation = evaluation.image_observation
    if observation.status == "PASS":
        print(
            "PASS: observed runtime image matches declared runtime.image "
            f"({observation.observed_image})"
        )
    elif observation.status == "FAIL":
        print(
            "FAIL: observed runtime image does not match declared runtime.image: "
            f"{observation.observed_image!r} != {observation.declared_image!r}"
        )
    else:
        print(
            "UNKNOWN: runtime image observation was not supplied; "
            f"runtime.image is declaration only ({observation.declared_image})"
        )

    if evaluation.declaration_issues or observation.status == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
