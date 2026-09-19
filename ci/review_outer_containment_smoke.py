from __future__ import annotations

import argparse
import contextlib
import copy
import importlib.util
import io
import os
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

from tools import review_check, review_outer
from tools.review_model import canonical_json
from tools.review_protected import ProtectedMainDocument


def _load_historical_smoke() -> ModuleType:
    # ci remains a collection of flat CLI scripts. Load only this fixed sibling
    # instead of changing repository-wide package discovery/type-check settings.
    path = Path(__file__).with_name("review_outer_smoke.py")
    spec = importlib.util.spec_from_file_location(
        "gnostoa_historical_outer_smoke", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("historical outer authority probe is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


historical_smoke = _load_historical_smoke()


def _assert_contained_result(code: int, raw: bytes) -> None:
    # Independent expected public contract: neither an arbitrary TOOL_ERROR nor
    # a successful semantic evaluation proves this specific containment.
    expected = {
        "error": {
            "code": "TOOL_ERROR",
            "message": "protected prior-effective outer consumer is unavailable",
            "details": {
                "error": (
                    "protected outer-consumer transport is not admitted as "
                    "host-persistence-free; current_advisory is unavailable"
                )
            },
        }
    }
    if code != 2 or raw != (canonical_json(expected) + "\n").encode("utf-8"):
        raise RuntimeError("public route did not return exact transport containment")


def _synthetic_input() -> dict[str, Any]:
    bundle = historical_smoke._load_json(historical_smoke.BUNDLE_PATH)
    now = historical_smoke._now()
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {
                "kind": "pull_request",
                "id": "protected-transport-containment-smoke",
            },
            "head_commit": "c" * 40,
            "comparison": {"kind": "merge_base", "commit_sha": "d" * 40},
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


def _exercise_containment(
    protected: ProtectedMainDocument,
    input_document: dict[str, Any],
) -> None:
    # This is a public, synthetic test fixture, not retained caller review data.
    # Acquire protected main and create the fixture before arming effect traps.
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-r2a-containment-smoke-"
    ) as directory:
        input_path = Path(directory) / "synthetic-input.json"
        input_path.write_text(canonical_json(input_document), encoding="utf-8")
        stdout = io.StringIO()
        with (
            mock.patch.object(
                review_outer,
                "acquire_gnostoa_current_advisory_consumer",
                return_value=protected,
            ) as acquire,
            mock.patch.object(
                tempfile,
                "TemporaryDirectory",
                side_effect=AssertionError("outer temporary resource attempted"),
            ),
            mock.patch.object(
                review_outer,
                "_verify_outer_image",
                side_effect=AssertionError("outer Docker image acquisition attempted"),
            ),
            mock.patch.object(
                review_outer,
                "_checked_output",
                side_effect=AssertionError("outer Docker command attempted"),
            ),
            mock.patch.object(
                review_outer,
                "_run_docker",
                side_effect=AssertionError("outer Docker execution attempted"),
            ),
            contextlib.redirect_stdout(stdout),
        ):
            # The public CLI and its containment guard are real. Only acquisition
            # is frozen to the independently fetched, validated protected object.
            code = review_check.main(["--input", str(input_path)])
        acquire.assert_called_once_with()
        _assert_contained_result(code, stdout.getvalue().encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify protected transport containment, not live evaluation"
    )
    parser.add_argument("--expected-protected-main", required=True)
    args = parser.parse_args(argv)
    candidate_image = os.environ.get("GNOSTOA_R2A_CANDIDATE_IMAGE", "").strip()
    if not candidate_image:
        raise RuntimeError("GNOSTOA_R2A_CANDIDATE_IMAGE is required")
    # Reuse the real protected-main read-back and candidate/stale-poison probe;
    # do not load execution authority from this candidate checkout.
    protected, consumer = historical_smoke._acquire_under_candidate_poison(
        expected_protected_main=args.expected_protected_main,
        candidate_image=candidate_image,
    )
    _exercise_containment(protected, _synthetic_input())
    print(
        canonical_json(
            {
                "event": "R2A_PROTECTED_TRANSPORT_CONTAINMENT",
                "verification_kind": "containment-only",
                "protected_main_revision": protected.protected_main_revision,
                "acquired_consumer": consumer,
                "candidate_authority_selector_rejected": True,
                "stale_authority_selector_rejected": True,
                "containment_result": "PASS",
                "public_exit_code": 2,
                "current_advisory": "UNAVAILABLE",
                "live_evaluation": "NOT_RUN",
                "outer_docker_effects": "NOT_RUN",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
