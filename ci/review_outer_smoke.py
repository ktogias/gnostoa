from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest import mock

from tools import review_check, review_outer, review_protected
from tools.review_model import canonical_json
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
CONSUMER_AUTHORITY_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
P2B_SOURCE_REVISION = "2aa1ed3217c42819155b8ff36385b000720ba4f8"  # pragma: allowlist secret -- public source revision
P2B_SOURCE_TREE = "4cda4e4a704cb518f56201423e313d4dd9db5e24"  # pragma: allowlist secret -- public source tree
P2B_PUBLIC_SURFACE_DIGEST = "sha256:b69f11e1efe181f959a14310fed0a35d3533114d734de584790a85cba7bdb565"  # pragma: allowlist secret -- public surface digest
P2B_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281"  # pragma: allowlist secret -- public OCI digest
)
B16_SOURCE_REVISION = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- historical public source revision
B16_SOURCE_TREE = "ff38abe5718ebc550054ea6af18a73d0aef8e514"  # pragma: allowlist secret -- historical public source tree
B16_PUBLIC_SURFACE_DIGEST = "sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57"  # pragma: allowlist secret -- historical public surface digest
B16_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867"  # pragma: allowlist secret -- historical public OCI digest
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")

EXPECTED_CONSUMER: dict[str, object] = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": P2B_SOURCE_REVISION,
    "source_tree": P2B_SOURCE_TREE,
    "public_surface_digest": P2B_PUBLIC_SURFACE_DIGEST,
    "runtime_image": P2B_OCI_IMAGE,
    "runtime_revision": P2B_SOURCE_REVISION,
    "supported_input_schema_versions": ["1.0"],
    "status": "accepted",
}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _stale_b16_authority() -> dict[str, Any]:
    authority = copy.deepcopy(_load_json(CONSUMER_AUTHORITY_PATH))
    stale_consumer = copy.deepcopy(EXPECTED_CONSUMER)
    stale_consumer.update(
        {
            "source_revision": B16_SOURCE_REVISION,
            "source_tree": B16_SOURCE_TREE,
            "public_surface_digest": B16_PUBLIC_SURFACE_DIGEST,
            "runtime_image": B16_OCI_IMAGE,
            "runtime_revision": B16_SOURCE_REVISION,
        }
    )
    authority["expected_consumer"] = stale_consumer
    authority["acquired_consumer"] = copy.deepcopy(stale_consumer)
    return authority


def _assert_promoted_readback(
    protected: ProtectedMainDocument,
    expected_protected_main: str,
) -> dict[str, Any]:
    if _SHA40.fullmatch(expected_protected_main) is None:
        raise RuntimeError("expected protected main revision is not an exact commit")
    if protected.protected_main_revision != expected_protected_main:
        raise RuntimeError(
            "protected main revision changed before the P2b read-back: "
            f"expected {expected_protected_main}, got "
            f"{protected.protected_main_revision}"
        )
    consumer = review_outer._validate_consumer_authority(protected.document)
    if consumer != EXPECTED_CONSUMER:
        raise RuntimeError(
            "protected outer-consumer authority is not the exact promoted OCI(P2b)"
        )
    return consumer


def _acquire_under_candidate_poison(
    *,
    expected_protected_main: str,
    candidate_image: str,
) -> tuple[ProtectedMainDocument, dict[str, Any]]:
    if not candidate_image or candidate_image in {P2B_OCI_IMAGE, B16_OCI_IMAGE}:
        raise RuntimeError(
            "candidate runtime selector is not independently identifiable"
        )

    with tempfile.TemporaryDirectory(
        prefix="gnostoa-r2a-candidate-poison-"
    ) as directory:
        candidate_root = Path(directory)
        stale_path = (
            candidate_root / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
        )
        stale_path.parent.mkdir(parents=True)
        stale_path.write_text(
            canonical_json(_stale_b16_authority()) + "\n",
            encoding="utf-8",
        )
        with mock.patch.dict(
            os.environ,
            {
                "KNOWLEDGE_KIT_ROOT": str(candidate_root),
                "GNOSTOA_R2A_CANDIDATE_IMAGE": candidate_image,
            },
            clear=False,
        ):
            protected = review_protected.acquire_gnostoa_current_advisory_consumer()

    consumer = _assert_promoted_readback(protected, expected_protected_main)
    return protected, consumer


def _assert_promoted_outer_plan(
    plan: dict[str, object],
    candidate_image: str,
) -> dict[str, object]:
    outer = plan.get("outer")
    if not isinstance(outer, list) or not all(isinstance(item, str) for item in outer):
        raise RuntimeError("protected outer execution plan is malformed")
    try:
        entrypoint_index = outer.index("--entrypoint")
        selected_image = outer[entrypoint_index + 2]
    except (IndexError, ValueError) as exc:
        raise RuntimeError("protected outer execution plan has no fixed image") from exc
    if selected_image != P2B_OCI_IMAGE:
        raise RuntimeError(
            "protected outer execution plan did not select exact promoted OCI(P2b)"
        )
    if candidate_image in outer or B16_OCI_IMAGE in outer:
        raise RuntimeError(
            "protected outer execution plan retained candidate or stale B1.x runtime"
        )
    return {
        "selected_runtime_image": selected_image,
        "candidate_runtime_rejected": True,
        "stale_b1x_runtime_rejected": True,
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exercise the promoted protected OCI(P2b) outer consumer"
    )
    parser.add_argument("--expected-protected-main", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    candidate_image = os.environ.get("GNOSTOA_R2A_CANDIDATE_IMAGE", "").strip()
    if not candidate_image:
        raise RuntimeError("GNOSTOA_R2A_CANDIDATE_IMAGE is required")
    protected, promoted_consumer = _acquire_under_candidate_poison(
        expected_protected_main=args.expected_protected_main,
        candidate_image=candidate_image,
    )

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

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-b2-smoke-") as directory:
        input_path = Path(directory) / "input.json"
        input_path.write_text(json.dumps(input_document), encoding="utf-8")
        output_bytes = io.BytesIO()
        stdout = io.TextIOWrapper(output_bytes, encoding="utf-8", write_through=True)
        selected_plan_receipts: list[dict[str, object]] = []
        original_build_plan = review_outer._build_isolated_execution_plan

        def capture_plan(
            *,
            consumer: dict[str, Any],
            socket_volume: str,
            tmp_volume: str,
            daemon_name: str,
            outer_name: str,
        ) -> dict[str, object]:
            plan = original_build_plan(
                consumer=consumer,
                socket_volume=socket_volume,
                tmp_volume=tmp_volume,
                daemon_name=daemon_name,
                outer_name=outer_name,
            )
            selected_plan_receipts.append(
                _assert_promoted_outer_plan(plan, candidate_image)
            )
            return plan

        with (
            mock.patch.object(
                review_outer,
                "acquire_gnostoa_current_advisory_consumer",
                return_value=protected,
            ),
            mock.patch.object(
                review_outer,
                "_build_isolated_execution_plan",
                side_effect=capture_plan,
            ),
            contextlib.redirect_stdout(stdout),
        ):
            code = review_check.main(["--input", str(input_path)])
        stdout.flush()
        raw = output_bytes.getvalue()

    if len(selected_plan_receipts) != 1:
        raise RuntimeError(
            "promoted outer smoke did not construct exactly one protected execution plan"
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"isolated B2 smoke returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("isolated B2 smoke result must be an object")
    if code != 3:
        raise RuntimeError(f"isolated B2 smoke expected exit 3, got {code}: {payload}")
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
        raise RuntimeError(
            "isolated B2 smoke trusted the caller-selected evaluation cut"
        )
    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list) or not any(
        "protected prior-integrated OCI" in item
        for item in diagnostics
        if isinstance(item, str)
    ):
        raise RuntimeError(
            f"isolated B2 smoke lost protected OCI provenance diagnostics: {payload}"
        )

    readback_receipt = {
        "candidate_runtime_image": candidate_image,
        "candidate_runtime_rejected": True,
        "event": "r2a_p2b_subsequent_candidate_negative_readback",
        "protected_main_revision": protected.protected_main_revision,
        "public_surface_digest": promoted_consumer["public_surface_digest"],
        "selected_runtime_image": selected_plan_receipts[0]["selected_runtime_image"],
        "source_revision": promoted_consumer["source_revision"],
        "source_tree": promoted_consumer["source_tree"],
        "stale_b1x_runtime_image": B16_OCI_IMAGE,
        "stale_b1x_runtime_rejected": True,
    }
    print(canonical_json(readback_receipt), file=sys.stderr)
    print(raw.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
