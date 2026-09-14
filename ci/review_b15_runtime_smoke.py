from __future__ import annotations

import os
import re
import selectors
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

DOCKER_CLI_VERSION = "26.1.5+dfsg1-9+deb13u1"
MAX_OUTPUT_BYTES = 65_536
TIMEOUT_SECONDS = 30
TERMINATE_GRACE_SECONDS = 2
CLEANUP_TIMEOUT_SECONDS = 5
CLEANUP_ATTEMPTS = 3
CLEANUP_RETRY_DELAY_SECONDS = 0.25
CLEANUP_OUTPUT_BYTES = 4_096


def _docker() -> str:
    executable = shutil.which("docker", path=os.defpath)
    if executable is None:
        raise RuntimeError("Docker CLI is unavailable for B1.5 runtime smoke")
    return executable


def _terminate_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        process.wait()
        return

    process.terminate()
    try:
        process.wait(timeout=TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_bounded(
    command: list[str],
    *,
    environment: dict[str, str],
    timeout_seconds: float = TIMEOUT_SECONDS,
    max_output_bytes: int = MAX_OUTPUT_BYTES,
) -> tuple[int, bytes, bytes]:
    deadline = time.monotonic() + timeout_seconds
    process: subprocess.Popen[bytes] = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    selector = selectors.DefaultSelector()
    output = {"stdout": bytearray(), "stderr": bytearray()}
    try:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            events = selector.select(remaining)
            if not events:
                raise subprocess.TimeoutExpired(command, timeout_seconds)

            for key, _mask in events:
                stream_name = key.data
                buffer = output[stream_name]
                read_size = min(8192, max_output_bytes + 1 - len(buffer))
                chunk = os.read(key.fd, read_size)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer.extend(chunk)
                if len(buffer) > max_output_bytes:
                    raise RuntimeError(
                        f"B1.5 runtime smoke {stream_name} exceeded its output bound"
                    )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout_seconds)
        returncode = process.wait(timeout=remaining)
        return returncode, bytes(output["stdout"]), bytes(output["stderr"])
    except Exception:
        _terminate_and_reap(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()


def _container_exists(
    docker: str,
    container_name: str,
    *,
    environment: dict[str, str],
) -> bool:
    returncode, stdout, stderr = _run_bounded(
        [
            docker,
            "ps",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            f"name=^/{container_name}$",
        ],
        environment=environment,
        timeout_seconds=CLEANUP_TIMEOUT_SECONDS,
        max_output_bytes=CLEANUP_OUTPUT_BYTES,
    )
    if returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            message or "B1.5 runtime container cleanup could not be inspected"
        )

    matches = [line for line in stdout.decode("ascii", errors="strict").splitlines() if line]
    if len(matches) > 1:
        raise RuntimeError("B1.5 runtime cleanup matched multiple containers")
    return bool(matches)


def _remove_owned_container(
    docker: str,
    container_name: str,
    *,
    environment: dict[str, str],
) -> None:
    last_error: Exception | None = None
    for attempt in range(CLEANUP_ATTEMPTS):
        try:
            completed = subprocess.run(
                [docker, "rm", "--force", container_name],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=CLEANUP_TIMEOUT_SECONDS,
                env=environment,
            )
            if completed.returncode != 0:
                last_error = RuntimeError(
                    f"docker rm --force exited {completed.returncode}"
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            last_error = exc

        try:
            if not _container_exists(
                docker,
                container_name,
                environment=environment,
            ):
                time.sleep(CLEANUP_RETRY_DELAY_SECONDS)
                if not _container_exists(
                    docker,
                    container_name,
                    environment=environment,
                ):
                    return
        except Exception as exc:
            last_error = exc

        if attempt + 1 < CLEANUP_ATTEMPTS:
            time.sleep(CLEANUP_RETRY_DELAY_SECONDS)

    raise RuntimeError(
        "B1.5 runtime container cleanup could not be confirmed"
    ) from last_error


def _create_container(
    docker: str,
    container_name: str,
    image: str,
    *,
    environment: dict[str, str],
) -> str:
    command = [
        docker,
        "create",
        "--name",
        container_name,
        "--pull=never",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=8m",
        "--entrypoint",
        "/bin/sh",
        image,
        "-c",
        (
            "set -eu; "
            'test "$(id -u)" = "10001"; '
            "command -v docker >/dev/null; "
            "! command -v dockerd >/dev/null; "
            "test \"$(dpkg-query -W -f='${Version}' docker-cli)\" = "
            f'"{DOCKER_CLI_VERSION}"; '
            "docker --version"
        ),
    ]
    returncode, stdout, stderr = _run_bounded(command, environment=environment)
    if returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(message or "B1.5 runtime container creation failed")

    container_id = stdout.decode("ascii", errors="strict").strip()
    if re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise RuntimeError(f"unexpected Docker container id: {container_id!r}")
    return container_id


def main() -> int:
    image = os.environ.get("GNOSTOA_R2A_CANDIDATE_IMAGE", "").strip()
    if not image:
        raise RuntimeError("GNOSTOA_R2A_CANDIDATE_IMAGE is required")

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-b15-smoke-") as directory:
        environment = {
            "DOCKER_CONFIG": directory,
            "HOME": directory,
            "LC_ALL": "C",
            "PATH": os.defpath,
        }
        docker = _docker()
        container_name = Path(directory).name
        try:
            try:
                container_id = _create_container(
                    docker,
                    container_name,
                    image,
                    environment=environment,
                )
                returncode, stdout, stderr = _run_bounded(
                    [docker, "start", "--attach", container_id],
                    environment=environment,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("B1.5 runtime smoke timed out") from exc

            if returncode != 0:
                message = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(message or "B1.5 runtime smoke failed")

            version = stdout.decode("utf-8", errors="strict").strip()
            if not version.startswith("Docker version 26.1.5"):
                raise RuntimeError(
                    f"unexpected Docker client version output: {version!r}"
                )
        finally:
            _remove_owned_container(
                docker,
                container_name,
                environment=environment,
            )

    print(
        "B1.5 runtime smoke passed: exact docker-cli package is present, "
        "dockerd is absent, and the runtime remains non-root"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
