from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any
from unittest import mock

from tools import review_outer, review_protected
from tools.knowledge_common import toolkit_root
from tools.review_model import canonical_json
from tools.review_protected import ProtectedMainDocument


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _synthetic_input(protected_bundle: ProtectedMainDocument) -> dict[str, Any]:
    bundle = protected_bundle.document
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {
                "kind": "pull_request",
                "id": "r4-current-advisory-promotion-proof",
            },
            "head_commit": "c" * 40,
            "comparison": {"kind": "merge_base", "commit_sha": "d" * 40},
            "observed_at": "2026-09-19T00:00:00Z",
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
            "observed_at": "2026-09-19T00:00:00Z",
            "sources": [
                {
                    "source_id": "retained-review-evidence",
                    "status": "COMPLETE",
                    "observed_at": "2026-09-19T00:00:00Z",
                }
            ],
            "observations": [],
        },
        "qualification_snapshot": copy.deepcopy(bundle["qualification_snapshot"]),
    }


def _assert_semantic_result(code: int, raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("R4 promotion proof returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("R4 promotion proof result must be an object")
    if code != 3:
        detail = payload.get("error", payload.get("reason"))
        raise RuntimeError(
            f"R4 promotion proof expected semantic exit 3, got {code}: {detail}"
        )
    if (
        payload.get("outcome") != "INCOMPLETE"
        or payload.get("reason") != "QUORUM_UNMET"
    ):
        raise RuntimeError(
            "R4 promotion proof did not execute the expected live semantic path"
        )
    if payload.get("binding") is not False:
        raise RuntimeError("R4 promotion proof attempted a binding result")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exercise the exact promoted current-advisory outer identity"
    )
    parser.add_argument(
        "--mode",
        choices=("candidate", "protected"),
        required=True,
    )
    parser.add_argument("--expected-protected-main", required=True)
    args = parser.parse_args(argv)

    inner = review_protected.acquire_gnostoa_current_advisory_bundle()
    if inner.protected_main_revision != args.expected_protected_main:
        raise RuntimeError("protected main changed before R4 promotion proof")

    authority_path = (
        toolkit_root() / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
    )

    if args.mode == "candidate":
        authority = _load_json(authority_path)
        protected_consumer = ProtectedMainDocument(
            protected_main_revision=args.expected_protected_main,
            document=authority,
        )
        with mock.patch.object(
            review_outer,
            "acquire_gnostoa_current_advisory_consumer",
            return_value=protected_consumer,
        ):
            code, raw = review_outer.run_prior_effective_current_advisory(
                _synthetic_input(inner)
            )
        authority_source = "candidate-test-local"
        acquired = authority.get("acquired_consumer")
    else:
        protected_consumer = (
            review_protected.acquire_gnostoa_current_advisory_consumer()
        )
        if protected_consumer.protected_main_revision != args.expected_protected_main:
            raise RuntimeError(
                "protected consumer authority changed before R5 public-route proof"
            )
        code, raw = review_outer.run_prior_effective_current_advisory(
            _synthetic_input(inner)
        )
        authority_source = "protected-main"
        acquired = protected_consumer.document.get("acquired_consumer")

    payload = _assert_semantic_result(code, raw)
    if not isinstance(acquired, dict):
        raise RuntimeError("R4 promoted consumer identity is unavailable")
    runtime_image = acquired.get("runtime_image")
    if not isinstance(runtime_image, str):
        raise RuntimeError("R4 promoted runtime image is unavailable")

    receipt = {
        "event": "R4_CURRENT_ADVISORY_PROMOTION_LIVE_PROOF",
        "mode": args.mode,
        "authority_source": authority_source,
        "protected_main_revision": args.expected_protected_main,
        "runtime_image": runtime_image,
        "consumer_identity": canonical_json(acquired),
        "semantic_outcome": payload["outcome"],
        "semantic_reason": payload["reason"],
        "binding": payload["binding"],
        "registry_publication": "NOT_PERFORMED",
    }
    print(canonical_json(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
