from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, NoReturn

from .review_model import canonical_json

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_DIGEST_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+"
    r"@sha256:[0-9a-f]{64}$"
)
_DOCKER_TIMEOUT_SECONDS = 90
_MAX_RUNTIME_OUTPUT_BYTES = 2_097_152


class ProtectedJudgeUnavailable(RuntimeError):
    """Raised when the exact prior-integrated OCI judge cannot be used safely."""


def _docker_executable() -> str:
    executable = shutil.which("docker", path=os.defpath)
    if executable is None:
        raise ProtectedJudgeUnavailable("Docker CLI is unavailable")
    return executable


def _docker_environment(config_dir: Path) -> dict[str, str]:
    # Do not inherit caller-controlled daemon/context/config/credential selectors.
    # The authority-bound bootstrap image is public and digest-pinned, so the
    # protected route needs no caller Docker credentials or configuration.
    return {
        "DOCKER_CONFIG": str(config_dir),
        "HOME": str(config_dir),
        "LC_ALL": "C",
        "PATH": os.defpath,
    }


def _run_docker(
    arguments: list[str],
    *,
    config_dir: Path,
    timeout: int = _DOCKER_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            [_docker_executable(), *arguments],
            check=False,
            capture_output=True,
            timeout=timeout,
            env=_docker_environment(config_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedJudgeUnavailable(
            f"protected Docker execution failed: {exc}"
        ) from exc
    if len(result.stdout) > _MAX_RUNTIME_OUTPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected Docker stdout exceeds the bounded size"
        )
    if len(result.stderr) > _MAX_RUNTIME_OUTPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected Docker stderr exceeds the bounded size"
        )
    return result


def _checked_output(
    arguments: list[str],
    *,
    config_dir: Path,
    description: str,
    timeout: int = _DOCKER_TIMEOUT_SECONDS,
) -> bytes:
    result = _run_docker(arguments, config_dir=config_dir, timeout=timeout)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedJudgeUnavailable(detail or description)
    return result.stdout


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtectedJudgeUnavailable(
                f"prior-integrated judge result repeats field {key!r}"
            )
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise ProtectedJudgeUnavailable(
        f"prior-integrated judge result contains non-finite JSON number {value!r}"
    )


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtectedJudgeUnavailable(
            f"prior-integrated judge result contains non-finite JSON number {value!r}"
        )
    return parsed


def _decode_result(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtectedJudgeUnavailable(
            f"prior-integrated judge returned invalid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ProtectedJudgeUnavailable(
            "prior-integrated judge result must be an object"
        )
    return value


def _security_arguments() -> list[str]:
    return [
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m",
    ]


def run_prior_integrated_judge(
    *,
    image: str,
    input_document: dict[str, Any],
    policy_document: dict[str, Any],
    expected_revision: str,
    expected_surface_digest: str,
) -> tuple[int, dict[str, Any]]:
    """Execute the exact protected authority-bound OCI(P2a) semantic judge.

    The image, revision and public-surface digest come from protected-main
    authority. Production exposes no repository, image, Docker context, daemon,
    credential, policy or runtime selector. The one network-capable Docker action
    is anonymous acquisition of the immutable digest; judge execution itself is
    network-none and receives only two read-only JSON files.
    """

    if _DIGEST_IMAGE.fullmatch(image) is None:
        raise ProtectedJudgeUnavailable("protected judge image is not digest-pinned")
    if _SHA40.fullmatch(expected_revision) is None:
        raise ProtectedJudgeUnavailable(
            "protected judge revision is not an exact Git commit"
        )
    if _SHA256.fullmatch(expected_surface_digest) is None:
        raise ProtectedJudgeUnavailable(
            "protected judge public-surface digest is invalid"
        )

    # Use a fixed system temporary root instead of caller-controlled TMPDIR so the
    # bind-mount grammar cannot be redirected through a caller-selected path.
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-r2a-judge-", dir="/tmp"
    ) as directory:
        root = Path(directory)
        config_dir = root / "docker-config"
        payload_dir = root / "input"
        config_dir.mkdir(mode=0o700)
        payload_dir.mkdir(mode=0o755)

        input_path = payload_dir / "input.json"
        policy_path = payload_dir / "policy.json"
        input_path.write_text(canonical_json(input_document) + "\n", encoding="utf-8")
        policy_path.write_text(canonical_json(policy_document) + "\n", encoding="utf-8")
        input_path.chmod(0o444)
        policy_path.chmod(0o444)

        _checked_output(
            ["pull", image],
            config_dir=config_dir,
            description="cannot reacquire protected prior-integrated judge image",
        )

        repo_digests_raw = _checked_output(
            ["image", "inspect", "--format", "{{json .RepoDigests}}", image],
            config_dir=config_dir,
            description="cannot inspect protected prior-integrated judge repo digests",
        )
        try:
            repo_digests = json.loads(repo_digests_raw.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtectedJudgeUnavailable(
                "protected judge repo-digest observation is malformed"
            ) from exc
        if not isinstance(repo_digests, list) or image not in repo_digests:
            raise ProtectedJudgeUnavailable(
                "protected judge does not report the authority-bound OCI digest"
            )

        image_id = _checked_output(
            ["image", "inspect", "--format", "{{.Id}}", image],
            config_dir=config_dir,
            description="cannot inspect protected prior-integrated judge image id",
        ).decode("ascii", errors="strict").strip()
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise ProtectedJudgeUnavailable(
                "protected judge did not resolve to an immutable image id"
            )

        observed = (
            _checked_output(
                [
                    "image",
                    "inspect",
                    "--format",
                    '{{.Os}}|{{.Architecture}}|{{.Config.User}}|{{index .Config.Labels "org.opencontainers.image.revision"}}',
                    image,
                ],
                config_dir=config_dir,
                description="cannot inspect protected prior-integrated judge image",
            )
            .decode("utf-8", errors="strict")
            .strip()
        )
        parts = observed.split("|")
        if parts != ["linux", "amd64", "kit", expected_revision]:
            raise ProtectedJudgeUnavailable(
                "protected judge runtime identity does not match the authority binding"
            )

        surface = (
            _checked_output(
                [
                    "run",
                    "--rm",
                    "--pull=never",
                    *_security_arguments(),
                    "--entrypoint",
                    "python",
                    image,
                    "-m",
                    "tools.cli",
                    "surface-digest",
                    "--root",
                    "/opt/gnostoa",
                ],
                config_dir=config_dir,
                description="cannot measure protected judge public surface",
            )
            .decode("ascii", errors="strict")
            .strip()
        )
        if surface != expected_surface_digest:
            raise ProtectedJudgeUnavailable(
                "protected judge public surface does not match the authority binding"
            )

        mount = f"type=bind,src={payload_dir},dst=/gnostoa-input,readonly"
        result = _run_docker(
            [
                "run",
                "--rm",
                "--pull=never",
                *_security_arguments(),
                "--mount",
                mount,
                image,
                "review-check",
                "--input",
                "/gnostoa-input/input.json",
                "--policy",
                "/gnostoa-input/policy.json",
            ],
            config_dir=config_dir,
        )
        payload = _decode_result(result.stdout)
        return result.returncode, payload
