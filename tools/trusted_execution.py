"""Single Python owner for isolated Git execution (#368)."""

from __future__ import annotations

import os
import subprocess  # nosec B404 -- spawns trusted git executable with isolated_git_env and bounded_process.drain
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from tools import bounded_process
from tools.trusted_path import TRUSTED_PATH, trusted_executable

_PROTECTED_ENV_KEYS = frozenset(
    {
        "PATH",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_KEY_0",
        "GIT_CONFIG_VALUE_0",
        "GIT_CONFIG_KEY_1",
        "GIT_CONFIG_VALUE_1",
        "GIT_CONFIG_KEY_2",
        "GIT_CONFIG_VALUE_2",
    }
)

_DEFAULT_TIMEOUT_SECONDS = 60.0
_DEFAULT_OUTPUT_CAP_BYTES = 10 * 1024 * 1024


def git_executable() -> str:
    """Return the absolute path to git on TRUSTED_PATH."""
    return trusted_executable("git")


def isolated_git_env(
    base_env: Mapping[str, str] | None = None,
    *,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an isolated Git environment from an explicit allowlist, free of caller overrides."""
    _ = base_env
    env: dict[str, str] = {
        "PATH": TRUSTED_PATH,
        "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_CONFIG_COUNT": "3",
        "GIT_CONFIG_KEY_0": "core.hooksPath",
        "GIT_CONFIG_VALUE_0": os.devnull,
        "GIT_CONFIG_KEY_1": "core.fsmonitor",
        "GIT_CONFIG_VALUE_1": "false",
        "GIT_CONFIG_KEY_2": "core.attributesFile",
        "GIT_CONFIG_VALUE_2": os.devnull,
    }
    if extra:
        for key, value in extra.items():
            if key in _PROTECTED_ENV_KEYS:
                raise ValueError(
                    f"cannot override protected isolated Git env key: {key}"
                )
            env[key] = value
    return env


def run_isolated_git(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    extra_env: Mapping[str, str] | None = None,
    check: bool = True,
    text: bool = True,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
    cap: int = _DEFAULT_OUTPUT_CAP_BYTES,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Execute git from TRUSTED_PATH with an isolated Git environment and bounded drain."""
    cmd = [git_executable(), *args]
    process = subprocess.Popen(  # nosec B603 -- cmd[0] is resolved via TRUSTED_PATH; env is isolated_git_env
        cmd,
        cwd=cwd,
        env=isolated_git_env(extra=extra_env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    chunks: dict[str, list[bytes]] = {"stdout": [], "stderr": []}
    streams = {}
    if process.stdout is not None:
        streams["stdout"] = process.stdout
    if process.stderr is not None:
        streams["stderr"] = process.stderr

    def _sink(name: str, data: bytes) -> None:
        chunks[name].append(data)

    try:
        drained = bounded_process.drain(
            process,
            streams,
            _sink,
            deadline=time.monotonic() + timeout,
            cap=cap,
        )
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()

    stdout_bytes = b"".join(chunks["stdout"])
    stderr_bytes = b"".join(chunks["stderr"])
    stdout: str | bytes = (
        stdout_bytes.decode("utf-8", errors="replace") if text else stdout_bytes
    )
    stderr: str | bytes = (
        stderr_bytes.decode("utf-8", errors="replace") if text else stderr_bytes
    )

    if drained.outcome != "exited":
        process.kill()
        process.wait()
        if drained.outcome == "deadline":
            raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)
        raise RuntimeError(f"isolated git execution failed: {drained.outcome}")

    returncode = drained.returncode if drained.returncode is not None else 1
    if check and returncode != 0:
        raise subprocess.CalledProcessError(
            returncode, cmd, output=stdout, stderr=stderr
        )
    if text:
        return subprocess.CompletedProcess(
            cmd,
            returncode,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )
    return subprocess.CompletedProcess(
        cmd, returncode, stdout=stdout_bytes, stderr=stderr_bytes
    )
