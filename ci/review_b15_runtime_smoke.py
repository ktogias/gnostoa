from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

DOCKER_CLI_VERSION = "26.1.5+dfsg1-9+deb13u1"
MAX_OUTPUT_BYTES = 65_536
TIMEOUT_SECONDS = 30


def _docker() -> str:
    executable = shutil.which("docker", path=os.defpath)
    if executable is None:
        raise RuntimeError("Docker CLI is unavailable for B1.5 runtime smoke")
    return executable


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
        command = [
            _docker(),
            "run",
            "--rm",
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
        completed = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            env=environment,
        )

    if (
        len(completed.stdout) > MAX_OUTPUT_BYTES
        or len(completed.stderr) > MAX_OUTPUT_BYTES
    ):
        raise RuntimeError("B1.5 runtime smoke output exceeded its bound")
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or "B1.5 runtime smoke failed")

    version = completed.stdout.decode("utf-8", errors="strict").strip()
    if not version.startswith("Docker version 26.1.5"):
        raise RuntimeError(f"unexpected Docker client version output: {version!r}")

    print(
        "B1.5 runtime smoke passed: exact docker-cli package is present, "
        "dockerd is absent, and the runtime remains non-root"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
