from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

from tools.review_outer import run_prior_effective_current_advisory

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(bundle, dict):
        raise RuntimeError("integrated inner semantic authority must be a JSON object")
    now = _now()
    input_document = {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "pull_request", "id": "p2b-b2-outer-smoke"},
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

    code, raw = run_prior_effective_current_advisory(input_document)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"isolated B2 smoke returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("isolated B2 smoke result must be an object")
    if code != 3:
        raise RuntimeError(
            f"isolated B2 smoke expected exit 3, got {code}: {payload}"
        )
    if (
        payload.get("outcome") != "INCOMPLETE"
        or payload.get("reason") != "QUORUM_UNMET"
    ):
        raise RuntimeError(f"isolated B2 smoke expected QUORUM_UNMET: {payload}")
    if payload.get("binding") is not False:
        raise RuntimeError(f"isolated B2 smoke must remain advisory: {payload}")
    context = payload.get("evaluation_context")
    if not isinstance(context, dict):
        raise RuntimeError(f"isolated B2 smoke returned no live context: {payload}")
    if (
        context.get("mode") != "current_advisory"
        or context.get("judge_relation") != "prior_integrated"
        or context.get("fixture_only") is not False
    ):
        raise RuntimeError(f"isolated B2 smoke returned wrong live context: {payload}")
    if context.get("as_of") == input_document["evaluation_context"]["as_of"]:
        raise RuntimeError("isolated B2 smoke trusted the caller-selected evaluation cut")
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list) or not any(
        "protected prior-integrated OCI" in item
        for item in diagnostics
        if isinstance(item, str)
    ):
        raise RuntimeError(
            f"isolated B2 smoke lost protected OCI provenance diagnostics: {payload}"
        )

    print(raw.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
