from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass

from .profile import RunnerError

PROBE_SCHEMA = "gnostoa-experiment-runner-probe/v1"


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


def wait_for_log(container: str, marker: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = docker_command("logs", container, timeout=5)
        if marker in result.stdout:
            return
        time.sleep(0.1)
    raise RunnerError(f"container-not-ready:{container}:{marker}")


def safe_remove_container(name: str) -> None:
    try:
        docker_command("rm", "-f", name, timeout=10)
    except (RunnerError, subprocess.TimeoutExpired):
        pass


def safe_remove_network(name: str) -> None:
    try:
        docker_command("network", "rm", name, timeout=10)
    except (RunnerError, subprocess.TimeoutExpired):
        pass


def unique_name(prefix: str) -> str:
    return f"{prefix}-{os.getpid()}-{time.time_ns():x}"


def create_restricted_network(
    relay_image: str,
    allow: Sequence[str],
) -> tuple[str, str, str]:
    internal = unique_name("gnostoa-run-int")
    external = unique_name("gnostoa-run-ext")
    relay = unique_name("gnostoa-run-relay")
    try:
        docker_checked("network", "create", "--internal", internal)
        docker_checked("network", "create", external)
        relay_args = [
            "run",
            "-d",
            "--name",
            relay,
            "--network",
            external,
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
        docker_checked(*relay_args)
        wait_for_log(relay, '"event": "READY"')
        docker_checked("network", "connect", "--alias", "relay", internal, relay)
        return internal, external, relay
    except (RunnerError, subprocess.TimeoutExpired):
        safe_remove_container(relay)
        safe_remove_network(internal)
        safe_remove_network(external)
        raise
