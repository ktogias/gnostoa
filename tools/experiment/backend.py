from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass

from .profile import RunnerError

PROBE_SCHEMA = "gnostoa-experiment-runner-probe/v1"
_DOCKER_OBJECT_ID_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: str
    backend: str | None
    reasons: list[str]


def docker_executable() -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise RunnerError("docker-cli-unavailable")
    return docker


def probe_backend(backend: str, *, image: str | None) -> ProbeResult:
    if backend not in {"auto", "oci", "bwrap"}:
        return ProbeResult("BLOCKED", None, ["unsupported-backend"])

    oci_reasons: list[str] = []
    if backend in {"auto", "oci"}:
        docker = shutil.which("docker")
        if docker is None:
            oci_reasons.append("docker-cli-unavailable")
        else:
            try:
                info = subprocess.run(
                    [docker, "info", "--format", "{{.ServerVersion}}"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                oci_reasons.append("docker-daemon-timeout")
            else:
                if info.returncode != 0:
                    oci_reasons.append("docker-daemon-unavailable")
                elif image is None:
                    oci_reasons.append("oci-image-not-bound")
                else:
                    try:
                        inspect = subprocess.run(
                            [docker, "image", "inspect", image],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=10,
                        )
                    except subprocess.TimeoutExpired:
                        oci_reasons.append("oci-image-inspect-timeout")
                    else:
                        if inspect.returncode == 0:
                            return ProbeResult("AVAILABLE", "oci", [])
                        oci_reasons.append("oci-image-unavailable")
        if backend == "oci":
            return ProbeResult("BLOCKED", None, oci_reasons)

    if backend in {"auto", "bwrap"}:
        bwrap = shutil.which("bwrap")
        bwrap_reasons = (
            ["bwrap-cli-unavailable"]
            if bwrap is None
            else ["bwrap-backend-not-qualified"]
        )
        return ProbeResult("BLOCKED", None, [*oci_reasons, *bwrap_reasons])
    return ProbeResult("BLOCKED", None, ["no-qualified-backend"])


def docker_command(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [docker_executable(), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def docker_checked(*args: str, timeout: int = 60) -> str:
    result = docker_command(*args, timeout=timeout)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RunnerError(f"docker-command-failed:{message}")
    return result.stdout.strip()


def require_docker_object_id(value: str, *, label: str) -> str:
    if not _DOCKER_OBJECT_ID_RE.fullmatch(value):
        raise RunnerError(f"{label}-object-id-invalid")
    return value


def docker_created_id(*args: str, timeout: int = 60, label: str) -> str:
    return require_docker_object_id(
        docker_checked(*args, timeout=timeout),
        label=label,
    )


def wait_for_log(container_id: str, marker: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = docker_command("logs", container_id, timeout=5)
        if marker in result.stdout:
            return
        time.sleep(0.1)
    raise RunnerError(f"container-not-ready:{container_id}:{marker}")


def safe_remove_container(container_id: str) -> None:
    try:
        docker_command("rm", "-f", container_id, timeout=10)
    except (RunnerError, subprocess.TimeoutExpired):
        pass


def _docker_reports_missing_object(result: subprocess.CompletedProcess[str]) -> bool:
    message = f"{result.stderr}\n{result.stdout}".lower()
    return "no such container" in message or "no such object" in message


def ensure_container_absent(container_id: str) -> None:
    """Reap a coordinator-owned container ID and verify that it is absent."""

    try:
        observed = docker_command("container", "inspect", container_id, timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("container-absence-check-timeout") from exc
    if observed.returncode != 0:
        if _docker_reports_missing_object(observed):
            return
        message = observed.stderr.strip() or observed.stdout.strip()
        raise RunnerError(f"container-absence-unverified:{message}")

    try:
        removed = docker_command("rm", "-f", container_id, timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("container-reap-timeout") from exc
    if removed.returncode != 0:
        message = removed.stderr.strip() or removed.stdout.strip()
        raise RunnerError(f"container-reap-failed:{message}")

    try:
        verified = docker_command("container", "inspect", container_id, timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("container-absence-check-timeout") from exc
    if verified.returncode == 0:
        raise RunnerError("container-still-present-after-reap")
    if not _docker_reports_missing_object(verified):
        message = verified.stderr.strip() or verified.stdout.strip()
        raise RunnerError(f"container-absence-unverified:{message}")


def _container_running_state(container_id: str) -> bool:
    try:
        observed = docker_command(
            "container",
            "inspect",
            "--format",
            "{{.State.Running}}",
            container_id,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("container-running-state-timeout") from exc
    if observed.returncode != 0:
        message = observed.stderr.strip() or observed.stdout.strip()
        raise RunnerError(f"container-running-state-unverified:{message}")
    state = observed.stdout.strip()
    if state == "true":
        return True
    if state == "false":
        return False
    raise RunnerError(f"container-running-state-invalid:{state}")


def ensure_container_stopped(container_id: str) -> None:
    """Stop a retained coordinator-owned container and verify producer quiescence."""

    if _container_running_state(container_id):
        try:
            stopped = docker_command("stop", "--time", "10", container_id, timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise RunnerError("container-stop-timeout") from exc
        if stopped.returncode != 0:
            message = stopped.stderr.strip() or stopped.stdout.strip()
            raise RunnerError(f"container-stop-failed:{message}")
    if _container_running_state(container_id):
        raise RunnerError("container-still-running-after-stop")


def container_exit_code(container_id: str) -> int:
    try:
        observed = docker_command(
            "container",
            "inspect",
            "--format",
            "{{.State.ExitCode}}",
            container_id,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerError("container-exit-code-timeout") from exc
    if observed.returncode != 0:
        message = observed.stderr.strip() or observed.stdout.strip()
        raise RunnerError(f"container-exit-code-unverified:{message}")
    value = observed.stdout.strip()
    try:
        code = int(value)
    except ValueError as exc:
        raise RunnerError(f"container-exit-code-invalid:{value}") from exc
    if code < 0 or code > 255:
        raise RunnerError(f"container-exit-code-invalid:{value}")
    return code


def safe_remove_network(network_id: str) -> None:
    try:
        docker_command("network", "rm", network_id, timeout=10)
    except (RunnerError, subprocess.TimeoutExpired):
        pass


def unique_name(prefix: str) -> str:
    return f"{prefix}-{os.getpid()}-{time.time_ns():x}"


def create_restricted_network(
    relay_image: str,
    allow: Sequence[str],
) -> tuple[str, str, str]:
    internal_name = unique_name("gnostoa-run-int")
    external_name = unique_name("gnostoa-run-ext")
    relay_name = unique_name("gnostoa-run-relay")
    internal_id = ""
    external_id = ""
    relay_id = ""
    try:
        internal_id = docker_created_id(
            "network",
            "create",
            "--internal",
            internal_name,
            label="internal-network",
        )
        external_id = docker_created_id(
            "network",
            "create",
            external_name,
            label="external-network",
        )
        relay_args = [
            "run",
            "-d",
            "--name",
            relay_name,
            "--network",
            external_id,
            "--entrypoint",
            "python",
            relay_image,
            "-m",
            "tools.experiment_runner",
            "_relay",
            "--listen",
            "0.0.0.0",
            "--port",
            "8080",
        ]
        for target in allow:
            relay_args.extend(["--allow", target])
        relay_id = docker_created_id(*relay_args, label="relay-container")
        wait_for_log(relay_id, '"event": "READY"')
        docker_checked("network", "connect", "--alias", "relay", internal_id, relay_id)
        return internal_id, external_id, relay_id
    except (RunnerError, subprocess.TimeoutExpired):
        if relay_id:
            safe_remove_container(relay_id)
        if internal_id:
            safe_remove_network(internal_id)
        if external_id:
            safe_remove_network(external_id)
        raise
