from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

_GNOSTOA_SELF_REPOSITORY = "https://github.com/ktogias/gnostoa.git"
_GNOSTOA_SELF_BUNDLE_PATH = "tasks/issue-11-r2a-current-advisory.json"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_GIT_TIMEOUT_SECONDS = 20
_MAX_PROTECTED_DOCUMENT_BYTES = 2_097_152


class ProtectedAcquisitionUnavailable(RuntimeError):
    """Raised when protected-main authority cannot be acquired exactly."""


@dataclass(frozen=True)
class ProtectedMainDocument:
    protected_main_revision: str
    document: dict[str, Any]


def _git_executable() -> str:
    executable = shutil.which("git", path=os.defpath)
    if executable is None:
        raise ProtectedAcquisitionUnavailable(
            "Git is unavailable on the bounded protected-main acquisition path"
        )
    return executable


def _git_environment() -> dict[str, str]:
    # Do not inherit caller-controlled Git configuration, repository selectors,
    # credential helpers or URL rewrite rules. The protected route is public,
    # read-only GitHub HTTPS and therefore needs no caller credentials.
    return {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }


def _run_git(
    arguments: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [_git_executable(), *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedAcquisitionUnavailable(
            f"protected Git read-back failed: {exc}"
        ) from exc


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


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise ProtectedAcquisitionUnavailable(
        f"protected authority document contains non-finite JSON number {value!r}"
    )


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtectedAcquisitionUnavailable(
            f"protected authority document contains non-finite JSON number {value!r}"
        )
    return parsed


def _acquire_from_repository(
    repository_url: str,
    bundle_path: str,
) -> ProtectedMainDocument:
    """Test seam for the fixed production read-back route.

    Production does not expose these selectors; callers of the public acquisition
    function cannot replace the Gnostoa repository, protected branch or bundle path.
    """

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
        if not _SHA40.fullmatch(protected_main_revision):
            raise ProtectedAcquisitionUnavailable(
                "protected main did not resolve to an exact Git commit"
            )

        object_spec = f"{protected_main_revision}:{bundle_path}"
        encoded_size = _git_output(
            ["cat-file", "-s", object_spec],
            cwd=repository,
            description="protected current-advisory authority document is unavailable",
        )
        try:
            object_size = int(encoded_size.decode("ascii", errors="strict").strip())
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProtectedAcquisitionUnavailable(
                "protected current-advisory authority document size is invalid"
            ) from exc
        if object_size > _MAX_PROTECTED_DOCUMENT_BYTES:
            raise ProtectedAcquisitionUnavailable(
                "protected current-advisory authority document exceeds the bounded size"
            )

        raw = _git_output(
            ["show", object_spec],
            cwd=repository,
            description="protected current-advisory authority document is unavailable",
        )
        if len(raw) != object_size:
            raise ProtectedAcquisitionUnavailable(
                "protected current-advisory authority document size changed during read-back"
            )
        try:
            document = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_object_without_duplicate_fields,
                parse_constant=_reject_non_finite_constant,
                parse_float=_parse_finite_float,
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
        document=document,
    )


def acquire_gnostoa_current_advisory_bundle() -> ProtectedMainDocument:
    """Read the Gnostoa-self authority document from protected main only.

    P2a deliberately establishes provider acquisition, not execution identity and
    not semantic activation. The repository, branch and document path are fixed,
    and Git runs with a minimal configuration-free environment. P2b must
    independently bind a digest-pinned prior-integrated OCI execution identity
    before it may connect this provider record to current-advisory evaluation.
    """

    return _acquire_from_repository(
        _GNOSTOA_SELF_REPOSITORY,
        _GNOSTOA_SELF_BUNDLE_PATH,
    )
