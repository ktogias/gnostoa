"""What other test modules share from tests/test_review_assurance_p2b_b2_activation_red.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


CONSUMER_PATH = "tasks/issue-11-r2a-current-advisory-consumer.json"


def _consumer_authority() -> dict[str, object]:
    document = json.loads((ROOT / CONSUMER_PATH).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError("protected outer-consumer authority must be an object")
    return document


def _current_advisory_input() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "pull_request", "id": "p2b-b2-red"},
            "head_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # pragma: allowlist secret -- synthetic public test commit
            "comparison": {
                "kind": "merge_base",
                "commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",  # pragma: allowlist secret -- synthetic public test merge base
            },
            "observed_at": "2026-09-16T00:00:00Z",
        },
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": "2026-09-16T00:00:00Z",
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "authority": {},
        "acquired_judge": {},
        "evidence_set": {
            "observed_at": "2026-09-16T00:00:00Z",
            "sources": [],
            "observations": [],
        },
        "qualification_snapshot": {},
    }
