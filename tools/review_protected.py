from __future__ import annotations

import json
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from tools import trusted_execution

_GNOSTOA_SELF_REPOSITORY = "https://github.com/ktogias/gnostoa.git"
_GNOSTOA_SELF_BUNDLE_PATH = "tasks/issue-11-r2a-current-advisory.json"
_GNOSTOA_SELF_CONSUMER_PATH = "tasks/issue-11-r2a-current-advisory-consumer.json"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_GIT_TIMEOUT_SECONDS = 20
_MAX_PROTECTED_DOCUMENT_BYTES = 2_097_152


class ProtectedAcquisitionUnavailable(RuntimeError):
    """Raised when protected-main authority cannot be acquired exactly."""


@dataclass(frozen=True)
class ProtectedMainDocument:
    protected_main_revision: str
    document: dict[str, Any]


def _git_environment(arguments: list[str]) -> dict[str, str]:
    # Do not inherit caller-controlled Git configuration, repository selectors,
    # credential helpers or URL rewrite rules. The protected route is public,
    # read-only GitHub HTTPS and therefore needs no caller credentials. Nor does it
    # take the caller's proxy or certificates, which could counterfeit it (Decision
    # 0102; Codex on #369), nor follow a redirect over another transport (CodeAnt on
    # #369).
    return trusted_execution.git_environment(transports=_transports(arguments))


def _transports(arguments: list[str]) -> tuple[str, ...]:
    """The one transport a call needs: a fetch's own, HTTPS for the fixed route and
    the file transport for a local repository, as tests use; none for a local call."""
    if not arguments or arguments[0] != "fetch":
        return ()
    source = next((a for a in arguments[1:] if not a.startswith("-")), "")
    return ("https",) if source.startswith("https://") else ("file",)


def _run_git(
    arguments: list[str],
    *,
    cwd: Path,
    description: str,
) -> bytes:
    """Run Git through the owner (Decision 0102; Codex on #369) and return its
    output; any failure is the protected route being unavailable."""
    try:
        return trusted_execution.run_git(
            arguments,
            cwd=cwd,
            environment=_git_environment(arguments),
            timeout=_GIT_TIMEOUT_SECONDS,
        ).stdout
    except trusted_execution.GitFailure as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedAcquisitionUnavailable(detail or description) from exc
    except trusted_execution.TrustedExecutionError as exc:
        raise ProtectedAcquisitionUnavailable(
            f"protected Git read-back failed: {exc}"
        ) from exc


def _git_output(
    arguments: list[str],
    *,
    cwd: Path,
    description: str,
) -> bytes:
    return _run_git(arguments, cwd=cwd, description=description)


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
        _run_git(
            ["init", "-q", str(repository)],
            cwd=repository,
            description="cannot create bounded protected-main Git read-back workspace",
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
    """Read the Gnostoa-self inner semantic authority from protected main only."""

    return _acquire_from_repository(
        _GNOSTOA_SELF_REPOSITORY,
        _GNOSTOA_SELF_BUNDLE_PATH,
    )


def acquire_gnostoa_current_advisory_consumer() -> ProtectedMainDocument:
    """Read the Gnostoa-self outer-consumer authority from protected main only."""

    return _acquire_from_repository(
        _GNOSTOA_SELF_REPOSITORY,
        _GNOSTOA_SELF_CONSUMER_PATH,
    )
