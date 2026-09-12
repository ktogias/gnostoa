from __future__ import annotations

from typing import Any

from .review_model import canonical_digest

ADAPTER_ID = "gnostoa.file-review"
ADAPTER_VERSION = "1.0"

_NATIVE_RECOMMENDATIONS = {
    "APPROVED": "APPROVE",
    "CHANGES_REQUESTED": "REQUEST_CHANGES",
    "COMMENTED": "COMMENT_ONLY",
    "COMMENT_ONLY": "COMMENT_ONLY",
    "ABSTAINED": "ABSTAIN",
    "ABSTAIN": "ABSTAIN",
}


def normalize_observation(observation: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    native = observation.get("native")
    native_mapping = native if isinstance(native, dict) else {}
    raw_state = native_mapping.get("recommendation_state")
    normalized = (
        _NATIVE_RECOMMENDATIONS.get(raw_state, "UNKNOWN")
        if isinstance(raw_state, str)
        else "UNKNOWN"
    )
    rule_suffix = raw_state if isinstance(raw_state, str) else "MISSING"
    provenance = {
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "rule_id": f"native.recommendation_state.{rule_suffix}",
        "raw_state_digest": canonical_digest(native_mapping),
    }
    authoritative_admitted = normalized != "UNKNOWN"

    mismatches: list[str] = []
    claims = observation.get("claims")
    if isinstance(claims, dict):
        claimed_normalized = claims.get("normalized_recommendation")
        if claimed_normalized is not None and claimed_normalized != normalized:
            mismatches.append("normalized_recommendation")
        claimed_admitted = claims.get("admitted")
        if claimed_admitted is not None and claimed_admitted is not authoritative_admitted:
            mismatches.append("admitted")
        claimed_adapter_id = claims.get("adapter_id")
        if claimed_adapter_id is not None and claimed_adapter_id != ADAPTER_ID:
            mismatches.append("adapter_id")
        claimed_adapter_version = claims.get("adapter_version")
        if claimed_adapter_version is not None and claimed_adapter_version != ADAPTER_VERSION:
            mismatches.append("adapter_version")
        claimed_rule_id = claims.get("rule_id")
        if claimed_rule_id is not None and claimed_rule_id != provenance["rule_id"]:
            mismatches.append("rule_id")
        claimed_provenance = claims.get("normalization_provenance")
        if isinstance(claimed_provenance, dict):
            for field in (
                "adapter_id",
                "adapter_version",
                "rule_id",
                "raw_state_digest",
            ):
                if field in claimed_provenance and claimed_provenance[field] != provenance[field]:
                    mismatches.append(f"normalization_provenance.{field}")

    assessment = {
        "observation_id": observation.get("observation_id"),
        "reviewer_id": observation.get("reviewer_id"),
        "source_id": observation.get("source_id"),
        "observed_at": observation.get("observed_at"),
        "subject_binding": observation.get("subject_binding"),
        "raw_recommendation": raw_state,
        "normalized_recommendation": normalized,
        "normalization_provenance": provenance,
        "findings": observation.get("findings", []),
        "threads": observation.get("threads", {}),
        "native": native_mapping,
        "eligible": False,
        "exclusion_reasons": [],
    }
    return assessment, sorted(set(mismatches))
