from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .check_runtime_lock import (
    IGNORED_PARTS,
    IGNORED_SUFFIXES,
    PUBLIC_SURFACE_PATHS,
    public_surface_digest,
)
from .knowledge_common import KnowledgeFormatError, toolkit_root

_GNOSTOA_SELF_REPOSITORY = "https://github.com/ktogias/gnostoa.git"
_GNOSTOA_SELF_BUNDLE_PATH = "tasks/issue-11-r2a-current-advisory.json"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_GIT_TIMEOUT_SECONDS = 20
_MAX_PROTECTED_DOCUMENT_BYTES = 2_097_152


class ProtectedAcquisitionUnavailable(RuntimeError):
    """Raised when protected-main authority cannot be established exactly."""


@dataclass(frozen=True)
class ProtectedMainDocument:
    protected_main_revision: str
    runtime_revision: str
    public_surface_digest: str
    document: dict[str, Any]


def _run_git(
    arguments: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedAcquisitionUnavailable(f"protected Git read-back failed: {exc}") from exc


def _git_output(
    arguments: list[str],
    *,
    cwd: Path,
    description: str,
) -> bytes:
    result = _run_git(arguments, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedAcquisitionUnavailable(detail or description)
    return result.stdout


def _git_public_surface_digest(repository: Path, revision: str) -> str:
    encoded_paths = _git_output(
        [
            "ls-tree",
            "-rz",
            "--name-only",
            revision,
            "--",
            *PUBLIC_SURFACE_PATHS,
        ],
        cwd=repository,
        description="cannot enumerate protected-main public surface",
    )
    paths = sorted(
        {
            Path(os.fsdecode(encoded))
            for encoded in encoded_paths.split(b"\0")
            if encoded
        },
        key=lambda item: item.as_posix(),
    )

    digest = hashlib.sha256()
    included = 0
    for relative in paths:
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if relative.suffix.casefold() in IGNORED_SUFFIXES:
            continue
        content = _git_output(
            ["show", f"{revision}:{relative.as_posix()}"],
            cwd=repository,
            description=f"cannot read protected-main source {relative.as_posix()}",
        )
        encoded_path = relative.as_posix().encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
        included += 1

    if included == 0:
        raise ProtectedAcquisitionUnavailable(
            "protected main exposes no Gnostoa public-surface files"
        )
    return f"sha256:{digest.hexdigest()}"


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtectedAcquisitionUnavailable(
                f"protected authority document repeats field {key!r}"
            )
        result[key] = value
    return result


def _acquire_from_repository(
    repository_url: str,
    bundle_path: str,
    runtime_revision: str,
    runtime_root: Path,
) -> ProtectedMainDocument:
    if not _SHA40.fullmatch(runtime_revision):
        raise ProtectedAcquisitionUnavailable(
            "executing runtime revision is not an exact Git commit"
        )

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-protected-") as directory:
        repository = Path(directory)
        init = _run_git(["init", "-q", str(repository)])
        if init.returncode != 0:
            raise ProtectedAcquisitionUnavailable(
                "cannot create bounded protected-main Git read-back workspace"
            )
        _git_output(
            [
                "fetch",
                "--quiet",
                "--no-tags",
                "--depth=1",
                repository_url,
                "+refs/heads/main:refs/remotes/protected/main",
            ],
            cwd=repository,
            description="cannot fetch protected main",
        )
        protected_main_revision = (
            _git_output(
                ["rev-parse", "refs/remotes/protected/main"],
                cwd=repository,
                description="cannot resolve protected main",
            )
            .decode("ascii", errors="strict")
            .strip()
        )
        if runtime_revision != protected_main_revision:
            raise ProtectedAcquisitionUnavailable(
                "executing runtime is not the exact protected-main revision: "
                f"{runtime_revision} != {protected_main_revision}"
            )

        protected_surface = _git_public_surface_digest(
            repository, protected_main_revision
        )
        try:
            executing_surface = public_surface_digest(runtime_root)
        except (KnowledgeFormatError, OSError) as exc:
            raise ProtectedAcquisitionUnavailable(
                f"cannot establish executing public-surface identity: {exc}"
            ) from exc
        if executing_surface != protected_surface:
            raise ProtectedAcquisitionUnavailable(
                "executing public surface does not match protected main: "
                f"{executing_surface} != {protected_surface}"
            )

        raw = _git_output(
            ["show", f"{protected_main_revision}:{bundle_path}"],
            cwd=repository,
            description="protected current-advisory authority document is unavailable",
        )
        if len(raw) > _MAX_PROTECTED_DOCUMENT_BYTES:
            raise ProtectedAcquisitionUnavailable(
                "protected current-advisory authority document exceeds the bounded size"
            )
        try:
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_object_without_duplicate_fields,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ProtectedAcquisitionUnavailable(
                f"protected current-advisory authority document is invalid: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise ProtectedAcquisitionUnavailable(
                "protected current-advisory authority document must be an object"
            )

    return ProtectedMainDocument(
        protected_main_revision=protected_main_revision,
        runtime_revision=runtime_revision,
        public_surface_digest=protected_surface,
        document=document,
    )


def acquire_gnostoa_current_advisory_bundle() -> ProtectedMainDocument:
    """Acquire the self-hosted authority document only from exact protected main.

    The repository, branch and document path are intentionally not caller-selectable.
    P2a does not consume the returned document to bypass the P1 evaluator guard; a
    later separately integrated activation slice must validate its contents and the
    pinned OCI execution identity before any current-advisory semantic evaluation.
    """

    runtime_revision = os.environ.get("KNOWLEDGE_KIT_REVISION", "")
    return _acquire_from_repository(
        _GNOSTOA_SELF_REPOSITORY,
        _GNOSTOA_SELF_BUNDLE_PATH,
        runtime_revision,
        toolkit_root(),
    )
