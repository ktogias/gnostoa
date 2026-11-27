"""Single Python owner for isolated Git execution (#368)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from tools.trusted_path import TRUSTED_PATH, trusted_executable


def git_executable() -> str:
    """Return the absolute path to git on TRUSTED_PATH."""
    return trusted_executable("git")


def isolated_git_env(
    base_env: Mapping[str, str] | None = None,
    *,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an isolated Git environment free of caller Git overrides and untrusted PATH."""
    source = os.environ if base_env is None else base_env
    env = {k: v for k, v in source.items() if not k.startswith("GIT_")}
    env["PATH"] = TRUSTED_PATH
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_ATTR_NOSYSTEM"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "3"
    env["GIT_CONFIG_KEY_0"] = "core.hooksPath"
    env["GIT_CONFIG_VALUE_0"] = os.devnull
    env["GIT_CONFIG_KEY_1"] = "core.fsmonitor"
    env["GIT_CONFIG_VALUE_1"] = "false"
    env["GIT_CONFIG_KEY_2"] = "core.attributesFile"
    env["GIT_CONFIG_VALUE_2"] = os.devnull
    if extra:
        env.update(extra)
    return env


def run_isolated_git(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    extra_env: Mapping[str, str] | None = None,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Execute git from TRUSTED_PATH with an isolated Git environment."""
    return subprocess.run(
        [git_executable(), *args],
        cwd=cwd,
        env=isolated_git_env(extra=extra_env),
        capture_output=True,
        text=text,
        check=check,
    )
