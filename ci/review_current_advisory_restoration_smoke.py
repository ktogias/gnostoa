from __future__ import annotations

import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest import mock

from tools import review_outer, review_protected
from tools.review_current import _checked_output, _run_docker
from tools.review_model import canonical_json
from tools.review_protected import ProtectedMainDocument

_SENTINEL = "GNOSTOA_R2_PROTECTED_INPUT_SENTINEL_2f74c97d"
_SYNTHETIC_RECEIPT = "https://github.com/ktogias/gnostoa/issues/11#issuecomment-1"


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _candidate_consumer(
    *,
    source_revision: str,
    source_tree: str,
    public_surface_digest: str,
    image_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not image_id.startswith("sha256:"):
        raise RuntimeError("candidate image id is not content-addressed")
    synthetic_runtime_image = f"ghcr.io/ktogias/gnostoa@{image_id}"
    consumer: dict[str, Any] = {
        "role": "current_advisory_outer_consumer",
        "acquisition": "oci",
        "source_revision": source_revision,
        "source_tree": source_tree,
        "public_surface_digest": public_surface_digest,
        "runtime_image": synthetic_runtime_image,
        "runtime_revision": source_revision,
        "supported_input_schema_versions": ["1.0"],
        "status": "accepted",
    }
    authority: dict[str, Any] = {
        "schema_version": "1.0",
        "subject": {
            "kind": "gnostoa-protected-main-consumer-record",
            "value": "tasks/issue-11-r2a-current-advisory-consumer.json:v1",
        },
        "expected_consumer": copy.deepcopy(consumer),
        "acquired_consumer": copy.deepcopy(consumer),
        "materialization": {
            "protected_main_revision": source_revision,
            "workflow_run": "0",
            "attestation_id": "0",
            "rekor_log_index": "0",
            "receipt": _SYNTHETIC_RECEIPT,
        },
    }
    return consumer, authority


def _live_input(protected: ProtectedMainDocument) -> dict[str, Any]:
    bundle = protected.document
    now = _now()
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {
                "kind": "pull_request",
                "id": "r2-restoration-runtime-qualification",
            },
            "head_commit": "c" * 40,
            "comparison": {
                "kind": "merge_base",
                "commit_sha": "d" * 40,
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
        "candidate_claims": {"marker": _SENTINEL},
    }


def _verify_local_candidate(
    *,
    candidate_image: str,
    expected_image_id: str,
    expected_revision: str,
    expected_surface_digest: str,
    consumer: dict[str, Any],
    config_dir: Path,
) -> None:
    if consumer["runtime_revision"] != expected_revision:
        raise RuntimeError("synthetic candidate identity changed revision")
    observed_id = (
        _checked_output(
            ["image", "inspect", "--format", "{{.Id}}", candidate_image],
            config_dir=config_dir,
            description="cannot inspect local R2 candidate image id",
            timeout=30,
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if observed_id != expected_image_id:
        raise RuntimeError("local R2 candidate image id changed")

    observed = (
        _checked_output(
            [
                "image",
                "inspect",
                "--format",
                (
                    "{{.Os}}|{{.Architecture}}|{{.Config.User}}|"
                    '{{index .Config.Labels "org.opencontainers.image.revision"}}'
                ),
                candidate_image,
            ],
            config_dir=config_dir,
            description="cannot inspect local R2 candidate identity",
            timeout=30,
        )
        .decode("utf-8", errors="strict")
        .strip()
    )
    if observed.split("|") != ["linux", "amd64", "kit", expected_revision]:
        raise RuntimeError("local R2 candidate runtime identity changed")

    ids = (
        _checked_output(
            [
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
                "--entrypoint",
                "sh",
                candidate_image,
                "-ec",
                "id -u; id -g",
            ],
            config_dir=config_dir,
            description="cannot verify local R2 candidate uid/gid",
            timeout=30,
        )
        .decode("ascii", errors="strict")
        .splitlines()
    )
    if ids != ["10001", "10001"]:
        raise RuntimeError("local R2 candidate uid/gid changed")

    surface = (
        _checked_output(
            [
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
                "/tmp:rw,noexec,nosuid,nodev,size=16m",
                "--entrypoint",
                "python",
                candidate_image,
                "-m",
                "tools.cli",
                "surface-digest",
                "--root",
                "/opt/gnostoa",
            ],
            config_dir=config_dir,
            description="cannot measure local R2 candidate public surface",
            timeout=60,
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if surface != expected_surface_digest:
        raise RuntimeError("local R2 candidate public surface changed")


def main() -> int:
    candidate_image = _required_environment("GNOSTOA_R2A_CANDIDATE_IMAGE")
    source_revision = _required_environment("GNOSTOA_R2_EXPECTED_SOURCE_REVISION")
    source_tree = _required_environment("GNOSTOA_R2_EXPECTED_SOURCE_TREE")
    expected_image_id = _required_environment("GNOSTOA_R2_EXPECTED_IMAGE_ID")
    expected_surface_digest = _required_environment(
        "GNOSTOA_R2_EXPECTED_PUBLIC_SURFACE_DIGEST"
    )
    expected_protected_main = _required_environment(
        "GNOSTOA_R2_EXPECTED_PROTECTED_MAIN"
    )

    protected_bundle = review_protected.acquire_gnostoa_current_advisory_bundle()
    if protected_bundle.protected_main_revision != expected_protected_main:
        raise RuntimeError(
            "protected main changed before R2 layered transport qualification"
        )

    consumer, authority = _candidate_consumer(
        source_revision=source_revision,
        source_tree=source_tree,
        public_surface_digest=expected_surface_digest,
        image_id=expected_image_id,
    )
    protected_consumer = ProtectedMainDocument(
        protected_main_revision=expected_protected_main,
        document=authority,
    )
    synthetic_runtime_image = str(consumer["runtime_image"])
    admitted_identity = canonical_json(consumer)
    input_document = _live_input(protected_bundle)

    original_plan = review_outer._build_isolated_execution_plan
    original_remove_volume = review_outer._remove_volume
    tmp_volume_checked = False
    sentinel_absent = False

    def build_candidate_plan(
        *,
        consumer: dict[str, Any],
        socket_volume: str,
        tmp_volume: str,
        daemon_name: str,
        outer_name: str,
    ) -> dict[str, object]:
        plan = original_plan(
            consumer=consumer,
            socket_volume=socket_volume,
            tmp_volume=tmp_volume,
            daemon_name=daemon_name,
            outer_name=outer_name,
        )
        outer = plan.get("outer")
        if not isinstance(outer, list):
            raise RuntimeError("R2 outer execution plan is malformed")
        replacements = sum(item == synthetic_runtime_image for item in outer)
        if replacements != 1:
            raise RuntimeError("R2 outer plan did not bind one candidate image")
        plan["outer"] = [
            candidate_image if item == synthetic_runtime_image else item
            for item in outer
        ]
        return plan

    def verify_candidate(consumer: dict[str, Any], config_dir: Path) -> None:
        _verify_local_candidate(
            candidate_image=candidate_image,
            expected_image_id=expected_image_id,
            expected_revision=source_revision,
            expected_surface_digest=expected_surface_digest,
            consumer=consumer,
            config_dir=config_dir,
        )

    def inspect_then_remove(volume_name: str, config_dir: Path) -> str | None:
        nonlocal tmp_volume_checked, sentinel_absent
        probe_issue: str | None = None
        if "-tmp-" in volume_name:
            tmp_volume_checked = True
            try:
                probe = _run_docker(
                    [
                        "run",
                        "--rm",
                        "--interactive",
                        "--pull=never",
                        "--network",
                        "none",
                        "--read-only",
                        "--cap-drop",
                        "ALL",
                        "--security-opt",
                        "no-new-privileges",
                        "--mount",
                        f"type=volume,source={volume_name},target=/probe,readonly",
                        "--entrypoint",
                        "sh",
                        review_outer._DAEMON_IMAGE,
                        "-ec",
                        (
                            "set +e; "
                            "grep -R -F -q -f /dev/stdin /probe 2>/dev/null; "
                            "status=$?; "
                            'case "$status" in 0) exit 42 ;; '
                            "1) exit 0 ;; *) exit 43 ;; esac"
                        ),
                    ],
                    config_dir=config_dir,
                    timeout=30,
                    input_bytes=(_SENTINEL + "\n").encode("utf-8"),
                    reject_incomplete_input=True,
                )
            except Exception as exc:
                probe_issue = (
                    f"R2 shared tmp residue inspection failed ({type(exc).__name__})"
                )
            else:
                if probe.returncode == 0:
                    sentinel_absent = True
                elif probe.returncode == 42:
                    probe_issue = (
                        "R2 candidate persisted protected input in host-backed "
                        "shared tmp storage"
                    )
                else:
                    probe_issue = "R2 shared tmp residue inspection did not complete"

        cleanup_issue = original_remove_volume(volume_name, config_dir)
        issues = [issue for issue in (probe_issue, cleanup_issue) if issue]
        return "; ".join(issues) if issues else None

    with (
        mock.patch.object(
            review_outer,
            "acquire_gnostoa_current_advisory_consumer",
            return_value=protected_consumer,
        ),
        mock.patch.object(
            review_outer,
            "_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES",
            frozenset({admitted_identity}),
        ),
        mock.patch.object(
            review_outer,
            "_verify_outer_image",
            side_effect=verify_candidate,
        ),
        mock.patch.object(
            review_outer,
            "_build_isolated_execution_plan",
            side_effect=build_candidate_plan,
        ),
        mock.patch.object(
            review_outer,
            "_remove_volume",
            side_effect=inspect_then_remove,
        ),
    ):
        code, raw = review_outer.run_prior_effective_current_advisory(input_document)

    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("R2 layered candidate returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("R2 layered candidate result must be an object")
    if code != 3:
        detail = payload.get("error", payload.get("reason"))
        raise RuntimeError(
            f"R2 layered candidate expected semantic exit 3, got {code}: {detail}"
        )
    if (
        payload.get("outcome") != "INCOMPLETE"
        or payload.get("reason") != "QUORUM_UNMET"
    ):
        raise RuntimeError(
            "R2 layered candidate did not execute the expected live semantic path"
        )
    if payload.get("binding") is not False:
        raise RuntimeError("R2 layered candidate attempted a binding result")
    if not tmp_volume_checked or not sentinel_absent:
        raise RuntimeError("R2 shared tmp residue proof was not completed")

    receipt = {
        "event": "R2_CURRENT_ADVISORY_RESTORATION_RUNTIME_QUALIFICATION",
        "source_revision": source_revision,
        "source_tree": source_tree,
        "local_image_id": expected_image_id,
        "public_surface_digest": expected_surface_digest,
        "protected_main_revision": protected_bundle.protected_main_revision,
        "semantic_outcome": payload["outcome"],
        "semantic_reason": payload["reason"],
        "host_backed_shared_tmp_sentinel_absent": True,
        "registry_publication": "NOT_PERFORMED",
        "production_authority_promotion": "NOT_PERFORMED",
    }
    rendered = canonical_json(receipt)
    if _SENTINEL in rendered:
        raise RuntimeError("R2 receipt contains protected input sentinel")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
