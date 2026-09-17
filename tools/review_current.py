from __future__ import annotations

import json
import math
import os
import re
import selectors
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, NoReturn

from .review_model import canonical_json

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+"
    r"@sha256:[0-9a-f]{64}$"
)
_DOCKER_TIMEOUT_SECONDS = 90
_DOCKER_CLEANUP_TIMEOUT_SECONDS = 10
_MAX_RUNTIME_INPUT_BYTES = 4_194_304
_MAX_RUNTIME_OUTPUT_BYTES = 2_097_152
_READ_CHUNK_BYTES = 65_536
_WRITE_CHUNK_BYTES = 65_536

_CONTAINER_PAYLOAD_BRIDGE = f"""
import json
import os
import sys

limit = {_MAX_RUNTIME_INPUT_BYTES}
raw = sys.stdin.buffer.read(limit + 1)
if len(raw) > limit:
    raise SystemExit("protected payload envelope exceeds the bounded size")
try:
    envelope = json.loads(raw.decode("utf-8"))
except (UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit("protected payload envelope is invalid") from None
if not isinstance(envelope, dict) or set(envelope) != {{"input", "policy"}}:
    raise SystemExit("protected payload envelope has the wrong shape")
if not isinstance(envelope["input"], dict) or not isinstance(envelope["policy"], dict):
    raise SystemExit("protected payload envelope members must be objects")

os.umask(0o077)
paths = {{
    "input": "/tmp/gnostoa-review-input.json",
    "policy": "/tmp/gnostoa-review-policy.json",
}}
for name, path in paths.items():
    data = json.dumps(
        envelope[name],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8") + b"\\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o400,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)

os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "tools.cli",
        "review-check",
        "--input",
        paths["input"],
        "--policy",
        paths["policy"],
    ],
)
""".strip()


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


def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait()
    except OSError:
        pass


def _run_cidfile(arguments: list[str], config_dir: Path) -> Path | None:
    if not arguments or arguments[0] != "run":
        return None
    return config_dir / f"protected-run-{os.getpid()}-{time.monotonic_ns()}.cid"


def _cleanup_container(cidfile: Path | None, config_dir: Path) -> None:
    if cidfile is None:
        return
    try:
        container_id = cidfile.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProtectedJudgeUnavailable(
            f"protected Docker container cleanup identity is unavailable: {exc}"
        ) from exc
    if _CONTAINER_ID.fullmatch(container_id) is None:
        raise ProtectedJudgeUnavailable(
            "protected Docker container cleanup identity is malformed"
        )
    try:
        completed = subprocess.run(
            [_docker_executable(), "rm", "-f", container_id],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=_DOCKER_CLEANUP_TIMEOUT_SECONDS,
            env=_docker_environment(config_dir),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedJudgeUnavailable(
            f"protected Docker container cleanup failed: {exc}"
        ) from exc
    if completed.returncode != 0:
        raise ProtectedJudgeUnavailable(
            "protected Docker container cleanup returned a non-zero status"
        )


def _abort_docker_run(
    process: subprocess.Popen[bytes],
    cidfile: Path | None,
    config_dir: Path,
) -> None:
    _kill_and_reap(process)
    _cleanup_container(cidfile, config_dir)


def _run_docker(
    arguments: list[str],
    *,
    config_dir: Path,
    timeout: int = _DOCKER_TIMEOUT_SECONDS,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if input_bytes is not None and len(input_bytes) > _MAX_RUNTIME_INPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected Docker input exceeds the bounded size"
        )
    cidfile = _run_cidfile(arguments, config_dir)
    docker_arguments = arguments
    if cidfile is not None:
        docker_arguments = ["run", "--cidfile", str(cidfile), *arguments[1:]]
    command = [_docker_executable(), *docker_arguments]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_docker_environment(config_dir),
        )
    except OSError as exc:
        raise ProtectedJudgeUnavailable(
            f"protected Docker execution failed: {exc}"
        ) from exc

    if (
        process.stdout is None
        or process.stderr is None
        or (input_bytes is not None and process.stdin is None)
    ):
        try:
            _abort_docker_run(process, cidfile, config_dir)
        finally:
            if cidfile is not None:
                cidfile.unlink(missing_ok=True)
        raise ProtectedJudgeUnavailable("protected Docker output pipes are unavailable")

    outputs = {
        "stdout": bytearray(),
        "stderr": bytearray(),
    }
    selector: selectors.BaseSelector | None = None
    input_view: memoryview | None = None
    input_offset = 0
    deadline = time.monotonic() + timeout

    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        if input_bytes is not None:
            assert process.stdin is not None
            if input_bytes:
                input_view = memoryview(input_bytes)
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                process.stdin.close()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            events = selector.select(remaining)
            if not events:
                raise subprocess.TimeoutExpired(command, timeout)
            for key, _ in events:
                label = str(key.data)
                if label == "stdin":
                    assert input_view is not None
                    try:
                        written = os.write(
                            key.fd,
                            input_view[
                                input_offset : input_offset + _WRITE_CHUNK_BYTES
                            ],
                        )
                    except BrokenPipeError:
                        written = 0
                    if written > 0:
                        input_offset += written
                    if written == 0 or input_offset == len(input_view):
                        selector.unregister(key.fileobj)
                        assert process.stdin is not None
                        process.stdin.close()
                    continue
                buffer = outputs[label]
                remaining_bound = _MAX_RUNTIME_OUTPUT_BYTES + 1 - len(buffer)
                read_size = min(_READ_CHUNK_BYTES, max(1, remaining_bound))
                chunk = os.read(key.fd, read_size)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer.extend(chunk)
                if len(buffer) > _MAX_RUNTIME_OUTPUT_BYTES:
                    _abort_docker_run(process, cidfile, config_dir)
                    raise ProtectedJudgeUnavailable(
                        f"protected Docker {label} exceeds the bounded size"
                    )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        _abort_docker_run(process, cidfile, config_dir)
        raise ProtectedJudgeUnavailable(
            f"protected Docker execution failed: {exc}"
        ) from exc
    except OSError as exc:
        _abort_docker_run(process, cidfile, config_dir)
        raise ProtectedJudgeUnavailable(
            f"protected Docker execution failed: {exc}"
        ) from exc
    finally:
        if selector is not None:
            selector.close()
        process.stdout.close()
        process.stderr.close()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if input_view is not None:
            input_view.release()
        if cidfile is not None:
            cidfile.unlink(missing_ok=True)

    return subprocess.CompletedProcess(
        command,
        returncode,
        bytes(outputs["stdout"]),
        bytes(outputs["stderr"]),
    )


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
    network-none and receives one bounded stdin envelope. The compatibility files
    required by the immutable judge exist only in the container's bounded tmpfs.
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

    envelope = (
        canonical_json({"input": input_document, "policy": policy_document}) + "\n"
    ).encode("utf-8")
    if len(envelope) > _MAX_RUNTIME_INPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected Docker input exceeds the bounded size"
        )

    # Use a fixed system temporary root instead of caller-controlled TMPDIR so the
    # bind-mount grammar cannot be redirected through a caller-selected path.
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-r2a-judge-", dir="/tmp"
    ) as directory:
        root = Path(directory)
        config_dir = root / "docker-config"
        config_dir.mkdir(mode=0o700)

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

        image_id = (
            _checked_output(
                ["image", "inspect", "--format", "{{.Id}}", image],
                config_dir=config_dir,
                description="cannot inspect protected prior-integrated judge image id",
            )
            .decode("ascii", errors="strict")
            .strip()
        )
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

        result = _run_docker(
            [
                "run",
                "--rm",
                "--pull=never",
                "-i",
                *_security_arguments(),
                "--entrypoint",
                "python",
                image,
                "-c",
                _CONTAINER_PAYLOAD_BRIDGE,
            ],
            config_dir=config_dir,
            input_bytes=envelope,
        )
        payload = _decode_result(result.stdout)
        return result.returncode, payload
