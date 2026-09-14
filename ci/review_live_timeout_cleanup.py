from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tools import review_current

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"


def main() -> int:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise RuntimeError("integrated P2b-A authority bundle must be a JSON object")
    judge = bundle.get("acquired_judge")
    if not isinstance(judge, dict):
        raise RuntimeError("integrated P2b-A acquired judge must be an object")
    image = judge.get("runtime_image")
    if not isinstance(image, str):
        raise RuntimeError("integrated P2b-A judge must name a runtime image")

    container_name = f"gnostoa-r2a-timeout-cleanup-{os.getpid()}"
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-r2a-timeout-cleanup-", dir="/tmp"
    ) as directory:
        config_dir = Path(directory) / "docker-config"
        config_dir.mkdir(mode=0o700)
        review_current._checked_output(
            ["pull", image],
            config_dir=config_dir,
            description="cannot reacquire protected prior-integrated judge image",
        )

        try:
            review_current._run_docker(
                [
                    "run",
                    "--name",
                    container_name,
                    "--rm",
                    "--pull=never",
                    "--entrypoint",
                    "python",
                    image,
                    "-c",
                    "import time; time.sleep(30)",
                ],
                config_dir=config_dir,
                timeout=1,
            )
        except review_current.ProtectedJudgeUnavailable as exc:
            if "timed out" not in str(exc):
                raise RuntimeError(
                    f"protected Docker run failed for the wrong reason: {exc}"
                ) from exc
        else:
            raise RuntimeError(
                "protected Docker timeout discriminator did not time out"
            )

        inspected = review_current._run_docker(
            ["container", "inspect", container_name],
            config_dir=config_dir,
            timeout=10,
        )
        if inspected.returncode == 0:
            cleanup = review_current._run_docker(
                ["rm", "-f", container_name],
                config_dir=config_dir,
                timeout=10,
            )
            if cleanup.returncode != 0:
                raise RuntimeError(
                    "timed-out protected Docker run left a container and emergency cleanup failed"
                )
            raise RuntimeError(
                "timed-out protected Docker run left the judge container running"
            )

    print("timed-out protected Docker run left no container")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
