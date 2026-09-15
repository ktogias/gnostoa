from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from tools import review_current

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _input_document() -> dict[str, object]:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise RuntimeError("integrated P2b-A authority bundle must be a JSON object")

    now = _now()
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "pull_request", "id": "p2b-b16-oci-smoke"},
            "head_commit": "cccccccccccccccccccccccccccccccccccccccc",  # pragma: allowlist secret -- synthetic public smoke commit
            "comparison": {
                "kind": "merge_base",
                "commit_sha": "dddddddddddddddddddddddddddddddddddddddd",  # pragma: allowlist secret -- synthetic public smoke merge base
            },
            "observed_at": now,
        },
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": "2000-01-01T00:00:00Z",
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "authority": copy.deepcopy(bundle["authority"]),
        "acquired_judge": copy.deepcopy(bundle["acquired_judge"]),
        "evidence_set": {
            "observed_at": now,
            "sources": [
                {
                    "source_id": "retained-review-evidence",
                    "status": "COMPLETE",
                    "observed_at": now,
                }
            ],
            "observations": [],
        },
        "qualification_snapshot": copy.deepcopy(bundle["qualification_snapshot"]),
    }


def main() -> int:
    image = os.environ.get("GNOSTOA_R2A_CANDIDATE_IMAGE", "").strip()
    if not image:
        raise RuntimeError("GNOSTOA_R2A_CANDIDATE_IMAGE is required")

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-b16-smoke-") as directory:
        root = Path(directory)
        config_dir = root / "docker-config"
        config_dir.mkdir(mode=0o700)
        input_dir = root / "input"
        input_dir.mkdir(mode=0o755)
        input_path = input_dir / "input.json"
        input_path.write_text(
            json.dumps(_input_document(), sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        input_path.chmod(0o444)

        mount = f"type=bind,src={input_dir},dst=/gnostoa-input,readonly"
        result = review_current._run_docker(
            [
                "run",
                "--rm",
                "--pull=never",
                "--network",
                "bridge",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,nodev,size=32m",
                "--mount",
                mount,
                "--entrypoint",
                "python",
                image,
                "-m",
                "tools.review_live_entrypoint",
                "--input",
                "/gnostoa-input/input.json",
            ],
            config_dir=config_dir,
            timeout=90,
        )

    if result.returncode != 3:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"dormant B1.6 entrypoint expected exit 3, got {result.returncode}: {detail}"
        )
    try:
        payload = json.loads(result.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("dormant B1.6 entrypoint returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("dormant B1.6 entrypoint result must be an object")
    if (
        payload.get("outcome") != "INCOMPLETE"
        or payload.get("reason") != "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE"
        or payload.get("binding") is not False
    ):
        raise RuntimeError(
            "dormant B1.6 entrypoint unexpectedly activated a trusted nested judge: "
            f"{payload}"
        )

    print(
        "B1.6 entrypoint smoke passed: the exact runtime accepts bounded live input, "
        "remains advisory, and fails closed without any injected Docker daemon"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
