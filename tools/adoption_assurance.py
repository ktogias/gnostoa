"""Typed assurance contract for adoption-check v2 results."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

RESULT_SCHEMA = "gnostoa-adoption-check/v2"
POLICY_SCHEMA = "gnostoa-readiness-policy/v1"
POLICY_ID = "gnostoa-review-ready/v1"
SUBJECT_TYPE = "git-staged-candidate/v1"

REQUIRED_CONDITIONS = (
    "CandidateStable",
    "ExecutionSubjectsCoherent",
    "StructuralValid",
    "ContextDeterministic",
    "ProjectSuitesPassed",
    "RuntimeObservationAvailable",
    "EvidenceIntegrityPreserved",
)
CONDITION_TYPES = (*REQUIRED_CONDITIONS, "SemanticReviewRequired")

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$")
_OBJECT_ID_RE = {
    "sha1": re.compile(r"^[0-9a-f]{40}$"),
    "sha256": re.compile(r"^[0-9a-f]{64}$"),
}
_OUTCOMES = frozenset({"PASS", "FAIL", "BLOCKED", "NOT RUN", "ERROR"})
_STATUSES = frozenset({"TRUE", "FALSE", "UNKNOWN"})
_REASONS = {
    "TRUE": frozenset({"Satisfied", "Required"}),
    "FALSE": frozenset({"ObservedFailure", "SubjectChanged", "SubjectIncoherent"}),
    "UNKNOWN": frozenset(
        {"PrerequisiteBlocked", "NotRun", "UnsafeBoundary", "InternalError"}
    ),
}
_ERROR_REASONS = frozenset({"UnsafeBoundary", "InternalError"})

_OBSERVATION_PROFILES: dict[str, tuple[str, str, str, str]] = {
    "candidate-stability": (
        "gnostoa",
        "direct-measurement",
        "gnostoa-direct-measurement",
        "gnostoa-adoption-check",
    ),
    "execution-subject-coherence": (
        "gnostoa",
        "direct-measurement",
        "gnostoa-direct-measurement",
        "gnostoa-adoption-check",
    ),
    "structural-validation": (
        "gnostoa",
        "direct-measurement",
        "gnostoa-direct-measurement",
        "gnostoa-adoption-check",
    ),
    "context-determinism": (
        "gnostoa",
        "direct-measurement",
        "gnostoa-direct-measurement",
        "gnostoa-adoption-check",
    ),
    "project-suite-process": (
        "project",
        "project-authoritative-command",
        "gnostoa-observed-project-process",
        "gnostoa-adoption-check",
    ),
    "project-runtime-report": (
        "project",
        "invocation-bound-project-report",
        "invocation-bound-project-report",
        "gnostoa-adoption-check",
    ),
    "evidence-publication": (
        "gnostoa",
        "direct-measurement",
        "gnostoa-direct-measurement",
        "gnostoa-adoption-check",
    ),
    "semantic-review-requirement": (
        "gnostoa-contract",
        "normative-requirement",
        "normative-requirement",
        "gnostoa-readiness-policy",
    ),
    "external-attestation": (
        "external-provider",
        "verified-external-attestation",
        "verified-external-attestation",
        "gnostoa-adoption-check",
    ),
}

_CONDITION_OBSERVATIONS: dict[str, frozenset[str]] = {
    "CandidateStable": frozenset({"candidate-stability"}),
    "ExecutionSubjectsCoherent": frozenset({"execution-subject-coherence"}),
    "StructuralValid": frozenset({"structural-validation"}),
    "ContextDeterministic": frozenset({"context-determinism"}),
    "ProjectSuitesPassed": frozenset({"project-suite-process", "external-attestation"}),
    "RuntimeObservationAvailable": frozenset(
        {"project-runtime-report", "external-attestation"}
    ),
    "EvidenceIntegrityPreserved": frozenset({"evidence-publication"}),
    "SemanticReviewRequired": frozenset({"semantic-review-requirement"}),
}
_FALSE_REASONS: dict[str, frozenset[str]] = {
    "CandidateStable": frozenset({"ObservedFailure", "SubjectChanged"}),
    "ExecutionSubjectsCoherent": frozenset({"SubjectIncoherent"}),
    "StructuralValid": frozenset({"ObservedFailure"}),
    "ContextDeterministic": frozenset({"ObservedFailure"}),
    "ProjectSuitesPassed": frozenset({"ObservedFailure"}),
    "RuntimeObservationAvailable": frozenset({"ObservedFailure"}),
    "EvidenceIntegrityPreserved": frozenset({"ObservedFailure"}),
    "SemanticReviewRequired": frozenset({"ObservedFailure"}),
}


class AssuranceContractError(ValueError):
    """The caller supplied an invalid or ambiguous assurance claim."""


def canonical_json_bytes(value: Mapping[str, Any] | Sequence[Any]) -> bytes:
    """Return the deterministic JSON representation used for identities."""
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise AssuranceContractError(f"value is not canonical JSON: {exc}") from exc
    return rendered.encode("utf-8")


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def policy_document() -> dict[str, Any]:
    """Return the complete closed built-in readiness policy."""
    return {
        "schema": POLICY_SCHEMA,
        "id": POLICY_ID,
        "required_conditions": list(REQUIRED_CONDITIONS),
        "ready_when": "all-required-conditions-true",
        "error_precedence_reasons": sorted(_ERROR_REASONS),
        "results": {
            "READY": 0,
            "FAILED": 1,
            "ERROR": 2,
            "BLOCKED": 3,
        },
    }


def policy_bytes() -> bytes:
    """Return the exact canonical bytes committed as the policy contract."""
    return canonical_json_bytes(policy_document())


def policy_digest() -> str:
    """Return the digest of the complete built-in policy bytes."""
    return _sha256(policy_bytes())


POLICY_SHA256 = (
    "sha256:3af35e2cfed2f32fa0edd9e95faa6c449c086daccd1dd9f499fe519eab3c54fa"
)


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise AssuranceContractError(f"{label} must be a sha256 digest")
    return value


def _require_identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise AssuranceContractError(f"{label} is not a bounded identifier")
    return value


def _require_text(value: object, label: str, *, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise AssuranceContractError(f"{label} is not bounded text")
    return value


def _require_object_id(value: object, object_format: str, label: str) -> str:
    expression = _OBJECT_ID_RE.get(object_format)
    if expression is None:
        raise AssuranceContractError(
            "repository_object_format must be 'sha1' or 'sha256'"
        )
    if not isinstance(value, str) or expression.fullmatch(value) is None:
        raise AssuranceContractError(f"{label} is not a {object_format} Git object id")
    return value


def _require_byte_length(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise AssuranceContractError(f"{label} must be a non-negative integer")
    return value


def _validated_snapshot(
    value: Mapping[str, Any], object_format: str, label: str
) -> dict[str, Any]:
    expected = {
        "head",
        "tree",
        "status_sha256",
        "staged_index_sha256",
        "staged_index_bytes",
        "candidate_patch_sha256",
        "candidate_patch_bytes",
    }
    if set(value) != expected:
        raise AssuranceContractError(f"{label} must contain exactly {sorted(expected)}")
    return {
        "head": _require_object_id(value["head"], object_format, f"{label}.head"),
        "tree": _require_object_id(value["tree"], object_format, f"{label}.tree"),
        "status_sha256": _require_digest(
            value["status_sha256"], f"{label}.status_sha256"
        ),
        "staged_index_sha256": _require_digest(
            value["staged_index_sha256"], f"{label}.staged_index_sha256"
        ),
        "staged_index_bytes": _require_byte_length(
            value["staged_index_bytes"], f"{label}.staged_index_bytes"
        ),
        "candidate_patch_sha256": _require_digest(
            value["candidate_patch_sha256"],
            f"{label}.candidate_patch_sha256",
        ),
        "candidate_patch_bytes": _require_byte_length(
            value["candidate_patch_bytes"], f"{label}.candidate_patch_bytes"
        ),
    }


def _validated_gitlinks(
    values: Sequence[Mapping[str, Any]], object_format: str
) -> list[dict[str, str]]:
    validated: list[dict[str, str]] = []
    observed_paths: set[str] = set()
    for index, value in enumerate(values):
        if set(value) != {"path", "commit"}:
            raise AssuranceContractError(
                f"gitlinks[{index}] must contain exactly path and commit"
            )
        path = value["path"]
        if not isinstance(path, str) or not path or "\\" in path:
            raise AssuranceContractError(f"gitlinks[{index}].path is invalid")
        pure = PurePosixPath(path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise AssuranceContractError(f"gitlinks[{index}].path is unsafe")
        normalized = pure.as_posix()
        if normalized in observed_paths:
            raise AssuranceContractError(f"duplicate gitlink path: {normalized}")
        observed_paths.add(normalized)
        validated.append(
            {
                "path": normalized,
                "commit": _require_object_id(
                    value["commit"], object_format, f"gitlinks[{index}].commit"
                ),
            }
        )
    return sorted(validated, key=lambda item: item["path"])


def build_candidate_subject(
    *,
    repository_object_format: str,
    base_commit: str,
    staged_index_sha256: str,
    staged_index_bytes: int,
    candidate_patch_sha256: str,
    candidate_patch_bytes: int,
    gitlinks: Sequence[Mapping[str, Any]],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a content-addressed subject for one exact staged candidate."""
    base = _require_object_id(base_commit, repository_object_format, "base_commit")
    validated_before = _validated_snapshot(before, repository_object_format, "before")
    validated_after = _validated_snapshot(after, repository_object_format, "after")
    index_digest = _require_digest(staged_index_sha256, "staged_index_sha256")
    index_bytes = _require_byte_length(staged_index_bytes, "staged_index_bytes")
    patch_digest = _require_digest(candidate_patch_sha256, "candidate_patch_sha256")
    patch_bytes = _require_byte_length(candidate_patch_bytes, "candidate_patch_bytes")
    if base != validated_before["head"]:
        raise AssuranceContractError("base_commit must equal the before HEAD")
    if (
        index_digest != validated_before["staged_index_sha256"]
        or index_bytes != validated_before["staged_index_bytes"]
        or patch_digest != validated_before["candidate_patch_sha256"]
        or patch_bytes != validated_before["candidate_patch_bytes"]
    ):
        raise AssuranceContractError(
            "candidate identity must equal the before snapshot identity"
        )
    descriptor: dict[str, Any] = {
        "type": SUBJECT_TYPE,
        "repository_object_format": repository_object_format,
        "base_commit": base,
        "candidate": {
            "staged_index_sha256": index_digest,
            "staged_index_bytes": index_bytes,
            "patch_sha256": patch_digest,
            "patch_bytes": patch_bytes,
            "gitlinks": _validated_gitlinks(gitlinks, repository_object_format),
        },
        "snapshots": {
            "before": validated_before,
            "after": validated_after,
        },
    }
    return {"id": _sha256(canonical_json_bytes(descriptor)), **descriptor}


def _validated_evidence(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if not values:
        raise AssuranceContractError("an observation must cite retained evidence")
    validated: list[dict[str, Any]] = []
    paths: set[str] = set()
    for index, value in enumerate(values):
        expected = {"path", "sha256", "bytes", "origin"}
        if set(value) != expected:
            raise AssuranceContractError(
                f"evidence[{index}] must contain exactly {sorted(expected)}"
            )
        path = value["path"]
        if not isinstance(path, str) or not path or "\\" in path:
            raise AssuranceContractError(f"evidence[{index}].path is invalid")
        pure = PurePosixPath(path)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise AssuranceContractError(f"evidence[{index}].path is unsafe")
        normalized = pure.as_posix()
        if normalized in paths:
            raise AssuranceContractError(f"duplicate evidence path: {normalized}")
        paths.add(normalized)
        validated.append(
            {
                "path": normalized,
                "sha256": _require_digest(value["sha256"], f"evidence[{index}].sha256"),
                "bytes": _require_byte_length(
                    value["bytes"], f"evidence[{index}].bytes"
                ),
                "origin": _require_text(value["origin"], f"evidence[{index}].origin"),
            }
        )
    return sorted(validated, key=lambda item: item["path"])


def _validated_configuration(
    values: Sequence[Mapping[str, Any]] | None, subject_id: str
) -> list[dict[str, str]]:
    supplied = (
        values
        if values is not None
        else ({"name": "candidate-subject", "value": subject_id},)
    )
    if not supplied:
        raise AssuranceContractError(
            "an observation must bind relevant configuration or policy identity"
        )
    validated: list[dict[str, str]] = []
    names: set[str] = set()
    for index, value in enumerate(supplied):
        if set(value) != {"name", "value"}:
            raise AssuranceContractError(
                f"configuration[{index}] must contain exactly name and value"
            )
        name = _require_identifier(value["name"], f"configuration[{index}].name")
        if name in names:
            raise AssuranceContractError(f"duplicate configuration identity: {name}")
        names.add(name)
        validated.append(
            {
                "name": name,
                "value": _require_text(
                    value["value"], f"configuration[{index}].value", maximum=1024
                ),
            }
        )
    return sorted(validated, key=lambda item: item["name"])


def _validated_external_verification(
    value: Mapping[str, Any] | None, subject_id: str
) -> dict[str, str]:
    expected = {
        "verifier",
        "verification_method",
        "attestation_digest",
        "subject_digest",
    }
    if value is None or set(value) != expected:
        raise AssuranceContractError(
            "external verification must bind verifier, method, attestation, and subject"
        )
    subject_digest = _require_digest(value["subject_digest"], "subject_digest")
    if subject_digest != subject_id:
        raise AssuranceContractError("external verification has a stale subject")
    method = value["verification_method"]
    if method != "signature-and-subject-binding-v1":
        raise AssuranceContractError("external verification method is unsupported")
    return {
        "verifier": _require_identifier(value["verifier"], "verifier"),
        "verification_method": method,
        "attestation_digest": _require_digest(
            value["attestation_digest"], "attestation_digest"
        ),
        "subject_digest": subject_digest,
    }


def make_observation(
    *,
    observation_id: str,
    observation_type: str,
    subject_id: str,
    outcome: str,
    producer: str,
    evidence: Sequence[Mapping[str, Any]],
    configuration: Sequence[Mapping[str, Any]] | None = None,
    external_verification: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one typed observation with assurance assigned by the contract."""
    profile = _OBSERVATION_PROFILES.get(observation_type)
    if profile is None:
        raise AssuranceContractError(
            f"unsupported observation type: {observation_type}"
        )
    if outcome not in _OUTCOMES:
        raise AssuranceContractError(f"unsupported observation outcome: {outcome}")
    subject = _require_digest(subject_id, "subject_id")
    authority, basis, assurance, verifier = profile
    result: dict[str, Any] = {
        "id": _require_identifier(observation_id, "observation_id"),
        "type": observation_type,
        "subject": subject,
        "outcome": outcome,
        "producer": _require_identifier(producer, "producer"),
        "verifier": verifier,
        "authority": authority,
        "basis": basis,
        "assurance": assurance,
        "configuration": _validated_configuration(configuration, subject),
        "evidence": _validated_evidence(evidence),
    }
    if observation_type == "external-attestation":
        _validated_external_verification(external_verification, subject)
        raise AssuranceContractError(
            "external attestation ingestion requires a separately selected verifier"
        )
    elif external_verification is not None:
        raise AssuranceContractError(
            "external verification is valid only for external attestations"
        )
    return result


def make_condition(
    *,
    condition_type: str,
    subject_id: str,
    status: str,
    reason: str,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive one condition from typed, subject-bound observations."""
    allowed = _CONDITION_OBSERVATIONS.get(condition_type)
    if allowed is None:
        raise AssuranceContractError(f"unsupported condition type: {condition_type}")
    subject = _require_digest(subject_id, "subject_id")
    if status not in _STATUSES or reason not in _REASONS.get(status, frozenset()):
        raise AssuranceContractError(f"invalid condition state: {status}/{reason}")
    if not observations:
        raise AssuranceContractError("a condition must cite at least one observation")

    identifiers: list[str] = []
    authorities: set[str] = set()
    bases: set[str] = set()
    assurances: set[str] = set()
    verifiers: set[str] = set()
    evidence_by_path: dict[str, dict[str, Any]] = {}
    outcomes: list[str] = []
    for index, observation in enumerate(observations):
        raw_evidence = observation.get("evidence")
        if not isinstance(raw_evidence, list) or any(
            not isinstance(item, dict) for item in raw_evidence
        ):
            raise AssuranceContractError(f"observation[{index}].evidence is incomplete")
        raw_external = observation.get("external_verification")
        if raw_external is not None and not isinstance(raw_external, dict):
            raise AssuranceContractError(
                f"observation[{index}].external_verification is invalid"
            )
        raw_configuration = observation.get("configuration")
        if not isinstance(raw_configuration, list) or any(
            not isinstance(item, dict) for item in raw_configuration
        ):
            raise AssuranceContractError(
                f"observation[{index}].configuration is incomplete"
            )
        rebuilt = make_observation(
            observation_id=str(observation.get("id", "")),
            observation_type=str(observation.get("type", "")),
            subject_id=str(observation.get("subject", "")),
            outcome=str(observation.get("outcome", "")),
            producer=str(observation.get("producer", "")),
            evidence=raw_evidence,
            configuration=raw_configuration,
            external_verification=raw_external,
        )
        if rebuilt != dict(observation):
            raise AssuranceContractError(
                f"observation[{index}] does not match its assigned assurance profile"
            )
        observation_type = observation.get("type")
        if observation_type not in allowed:
            raise AssuranceContractError(
                f"observation[{index}] cannot establish {condition_type}"
            )
        if observation.get("subject") != subject:
            raise AssuranceContractError(
                f"observation[{index}] is bound to a different subject"
            )
        identifier = observation.get("id")
        outcome = observation.get("outcome")
        if not isinstance(identifier, str) or outcome not in _OUTCOMES:
            raise AssuranceContractError(f"observation[{index}] is incomplete")
        identifiers.append(identifier)
        outcomes.append(str(outcome))
        for key, destination in (
            ("authority", authorities),
            ("basis", bases),
            ("assurance", assurances),
            ("verifier", verifiers),
        ):
            value = observation.get(key)
            if not isinstance(value, str):
                raise AssuranceContractError(
                    f"observation[{index}].{key} is incomplete"
                )
            destination.add(value)
        for item in raw_evidence:
            if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                raise AssuranceContractError(
                    f"observation[{index}].evidence is incomplete"
                )
            evidence_by_path[item["path"]] = dict(item)

    if len(set(identifiers)) != len(identifiers):
        raise AssuranceContractError("condition observations must be unique")
    if status == "TRUE" and any(outcome != "PASS" for outcome in outcomes):
        raise AssuranceContractError("TRUE condition requires only PASS observations")
    if status == "FALSE" and "FAIL" not in outcomes:
        raise AssuranceContractError("FALSE condition requires a FAIL observation")
    if status == "UNKNOWN" and all(outcome == "PASS" for outcome in outcomes):
        raise AssuranceContractError(
            "UNKNOWN condition requires a non-PASS observation"
        )
    if status == "TRUE":
        expected_reason = (
            "Required" if condition_type == "SemanticReviewRequired" else "Satisfied"
        )
        if reason != expected_reason:
            raise AssuranceContractError(
                f"{condition_type} TRUE requires reason {expected_reason}"
            )
    elif status == "FALSE" and reason not in _FALSE_REASONS[condition_type]:
        raise AssuranceContractError(f"{condition_type} FALSE has an invalid reason")
    elif status == "UNKNOWN":
        if "ERROR" in outcomes:
            allowed_unknown_reasons = _ERROR_REASONS
        elif "BLOCKED" in outcomes:
            allowed_unknown_reasons = frozenset({"PrerequisiteBlocked"})
        else:
            allowed_unknown_reasons = frozenset({"NotRun"})
        if reason not in allowed_unknown_reasons:
            raise AssuranceContractError(
                f"{condition_type} UNKNOWN has an invalid reason"
            )

    return {
        "type": condition_type,
        "subject": subject,
        "status": status,
        "reason": reason,
        "observation_ids": sorted(identifiers),
        "authorities": sorted(authorities),
        "observation_bases": sorted(bases),
        "assurances": sorted(assurances),
        "verifiers": sorted(verifiers),
        "evidence": [evidence_by_path[path] for path in sorted(evidence_by_path)],
    }


def evaluate_readiness(
    subject_id: str, conditions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Evaluate only the explicit closed policy inputs for an exact subject."""
    subject = _require_digest(subject_id, "subject_id")
    condition_map: dict[str, Mapping[str, Any]] = {}
    problems: list[str] = []
    for index, condition in enumerate(conditions):
        condition_type = condition.get("type")
        if condition_type not in CONDITION_TYPES:
            problems.append(f"conditions[{index}] has an unknown type")
            continue
        if not isinstance(condition_type, str):
            problems.append(f"conditions[{index}] has no type")
            continue
        if condition_type in condition_map:
            problems.append(f"duplicate condition: {condition_type}")
            continue
        condition_map[condition_type] = condition
        if condition.get("subject") != subject:
            problems.append(f"stale condition subject: {condition_type}")
        if condition.get("status") not in _STATUSES:
            problems.append(f"invalid condition status: {condition_type}")
        status = condition.get("status")
        reason = condition.get("reason")
        if isinstance(status, str) and reason not in _REASONS.get(status, frozenset()):
            problems.append(f"invalid condition reason: {condition_type}")

    missing = [name for name in REQUIRED_CONDITIONS if name not in condition_map]
    problems.extend(f"missing required condition: {name}" for name in missing)
    statuses = [
        {
            "type": name,
            "status": condition_map[name].get("status", "UNKNOWN"),
            "reason": condition_map[name].get("reason", "InternalError"),
        }
        for name in CONDITION_TYPES
        if name in condition_map
    ]
    base: dict[str, Any] = {
        "subject": subject,
        "policy": {
            "schema": POLICY_SCHEMA,
            "id": POLICY_ID,
            "sha256": POLICY_SHA256,
        },
        "required_conditions": list(REQUIRED_CONDITIONS),
        "condition_statuses": statuses,
        "problems": sorted(problems),
    }
    if problems:
        return {
            **base,
            "result": "ERROR",
            "exit_code": 2,
            "reason": "InvalidPolicyInput",
        }

    required = [condition_map[name] for name in REQUIRED_CONDITIONS]
    if any(condition.get("reason") in _ERROR_REASONS for condition in required):
        return {
            **base,
            "result": "ERROR",
            "exit_code": 2,
            "reason": "UnsafeOrInternalCondition",
        }
    if any(condition.get("status") == "FALSE" for condition in required):
        return {
            **base,
            "result": "FAILED",
            "exit_code": 1,
            "reason": "RequiredConditionFailed",
        }
    if any(condition.get("status") == "UNKNOWN" for condition in required):
        return {
            **base,
            "result": "BLOCKED",
            "exit_code": 3,
            "reason": "RequiredConditionUnknown",
        }
    return {
        **base,
        "result": "READY",
        "exit_code": 0,
        "reason": "AllRequiredConditionsTrue",
    }


def provider_projection(
    readiness: Mapping[str, Any] | None, expected_subject_id: str
) -> dict[str, str]:
    """Project readiness into a fail-closed provider status."""
    expected = _require_digest(expected_subject_id, "expected_subject_id")
    if readiness is None:
        return {"result": "FAILURE", "reason": "MissingReadiness"}
    if readiness.get("subject") != expected:
        return {"result": "FAILURE", "reason": "StaleSubject"}
    policy = readiness.get("policy")
    if (
        not isinstance(policy, dict)
        or policy.get("id") != POLICY_ID
        or policy.get("schema") != POLICY_SCHEMA
        or policy.get("sha256") != POLICY_SHA256
    ):
        return {"result": "FAILURE", "reason": "StalePolicy"}
    condition_statuses = readiness.get("condition_statuses")
    if not isinstance(condition_statuses, list):
        return {"result": "FAILURE", "reason": "InvalidReadiness"}
    statuses: dict[str, object] = {}
    for item in condition_statuses:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            return {"result": "FAILURE", "reason": "InvalidReadiness"}
        condition_type = item["type"]
        if condition_type in statuses:
            return {"result": "FAILURE", "reason": "InvalidReadiness"}
        statuses[condition_type] = item.get("status")
    exact_ready = (
        readiness.get("required_conditions") == list(REQUIRED_CONDITIONS)
        and set(statuses) == set(CONDITION_TYPES)
        and all(statuses.get(name) == "TRUE" for name in REQUIRED_CONDITIONS)
        and statuses.get("SemanticReviewRequired") == "TRUE"
        and readiness.get("problems") == []
        and readiness.get("reason") == "AllRequiredConditionsTrue"
        and readiness.get("result") == "READY"
        and readiness.get("exit_code") == 0
    )
    if exact_ready:
        return {"result": "SUCCESS", "reason": "ExactReadySubject"}
    return {"result": "FAILURE", "reason": "ReadinessNotSatisfied"}


def decode_result_schema(content: bytes) -> dict[str, Any]:
    """Decode and sanity-check exact retained result-schema bytes."""
    try:

        def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise AssuranceContractError(
                        f"duplicate result-schema member: {key}"
                    )
                value[key] = item
            return value

        def reject_constant(value: str) -> None:
            raise AssuranceContractError(f"unsupported result-schema constant: {value}")

        value: object = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except AssuranceContractError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AssuranceContractError(f"cannot decode result schema: {exc}") from exc
    if not isinstance(value, dict):
        raise AssuranceContractError("result schema root must be an object")
    try:
        Draft202012Validator.check_schema(value)
    except SchemaError as exc:
        raise AssuranceContractError(f"invalid result schema: {exc.message}") from exc
    return value


def load_result_schema(path: Path) -> dict[str, Any]:
    """Load and sanity-check the bundled adoption-check result schema."""
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise AssuranceContractError(f"cannot load result schema: {exc}") from exc
    return decode_result_schema(content)


def validate_result(result: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Reject a result that does not satisfy the closed v2 schema."""
    errors = sorted(
        Draft202012Validator(schema).iter_errors(result),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "root"
        raise AssuranceContractError(
            f"invalid adoption result at {location}: {first.message}"
        )

    value = dict(result)
    subject = dict(value["subject"])
    candidate = dict(subject["candidate"])
    snapshots = dict(subject["snapshots"])
    rebuilt_subject = build_candidate_subject(
        repository_object_format=str(subject["repository_object_format"]),
        base_commit=str(subject["base_commit"]),
        staged_index_sha256=str(candidate["staged_index_sha256"]),
        staged_index_bytes=int(candidate["staged_index_bytes"]),
        candidate_patch_sha256=str(candidate["patch_sha256"]),
        candidate_patch_bytes=int(candidate["patch_bytes"]),
        gitlinks=list(candidate["gitlinks"]),
        before=dict(snapshots["before"]),
        after=dict(snapshots["after"]),
    )
    if rebuilt_subject != subject:
        raise AssuranceContractError("candidate subject identity is not canonical")
    subject_id = str(subject["id"])

    artifact_map: dict[str, dict[str, Any]] = {}
    for artifact in value["artifacts"]:
        item = dict(artifact)
        path = str(item["path"])
        if path in artifact_map:
            raise AssuranceContractError(f"duplicate artifact path: {path}")
        artifact_map[path] = item
    retained_patch = artifact_map.get("candidate.patch")
    if (
        retained_patch is None
        or retained_patch["sha256"] != candidate["patch_sha256"]
        or retained_patch["bytes"] != candidate["patch_bytes"]
    ):
        raise AssuranceContractError(
            "candidate subject does not match the retained staged patch"
        )

    def require_retained(reference: Mapping[str, Any]) -> None:
        path = str(reference.get("path", ""))
        if artifact_map.get(path) != dict(reference):
            raise AssuranceContractError(
                f"evidence reference is stale or unretained: {path}"
            )

    for component in value["components"]:
        for stream in ("stdout", "stderr"):
            path = str(component[stream])
            if path not in artifact_map:
                raise AssuranceContractError(
                    f"component stream is not retained: {path}"
                )

    observations: dict[str, dict[str, Any]] = {}
    for raw_observation in value["observations"]:
        observation = dict(raw_observation)
        identifier = str(observation["id"])
        if identifier in observations:
            raise AssuranceContractError(f"duplicate observation id: {identifier}")
        raw_external = observation.get("external_verification")
        rebuilt_observation = make_observation(
            observation_id=identifier,
            observation_type=str(observation["type"]),
            subject_id=str(observation["subject"]),
            outcome=str(observation["outcome"]),
            producer=str(observation["producer"]),
            evidence=list(observation["evidence"]),
            configuration=list(observation["configuration"]),
            external_verification=(
                dict(raw_external) if isinstance(raw_external, dict) else None
            ),
        )
        if rebuilt_observation != observation:
            raise AssuranceContractError(
                f"observation does not match its assurance profile: {identifier}"
            )
        if observation["subject"] != subject_id:
            raise AssuranceContractError(f"stale observation subject: {identifier}")
        for reference in observation["evidence"]:
            require_retained(reference)
        observations[identifier] = observation

    conditions: list[dict[str, Any]] = []
    observed_condition_types: set[str] = set()
    referenced_observations: set[str] = set()
    for raw_condition in value["conditions"]:
        condition = dict(raw_condition)
        condition_type = str(condition["type"])
        if condition_type in observed_condition_types:
            raise AssuranceContractError(f"duplicate condition type: {condition_type}")
        observed_condition_types.add(condition_type)
        try:
            inputs = [observations[item] for item in condition["observation_ids"]]
        except KeyError as exc:
            raise AssuranceContractError(
                f"condition cites an unknown observation: {condition_type}"
            ) from exc
        referenced_observations.update(condition["observation_ids"])
        rebuilt_condition = make_condition(
            condition_type=condition_type,
            subject_id=str(condition["subject"]),
            status=str(condition["status"]),
            reason=str(condition["reason"]),
            observations=inputs,
        )
        if rebuilt_condition != condition:
            raise AssuranceContractError(
                f"condition is not derived from its observations: {condition_type}"
            )
        conditions.append(condition)
    if referenced_observations != set(observations):
        raise AssuranceContractError(
            "every retained observation must be consumed by one condition"
        )

    readiness = dict(value["readiness"])
    expected_readiness = evaluate_readiness(subject_id, conditions)
    if readiness != expected_readiness:
        raise AssuranceContractError(
            "readiness is not the built-in policy projection of the conditions"
        )

    contracts = dict(value["contracts"])
    result_contract = dict(contracts["result_schema"])
    policy_contract = dict(contracts["readiness_policy"])
    require_retained(result_contract["evidence"])
    require_retained(policy_contract["evidence"])
    if (
        result_contract["id"] != schema.get("$id")
        or result_contract["sha256"] != result_contract["evidence"]["sha256"]
    ):
        raise AssuranceContractError("result-schema contract is inconsistent")
    if (
        policy_contract["schema"] != POLICY_SCHEMA
        or policy_contract["id"] != POLICY_ID
        or policy_contract["sha256"] != POLICY_SHA256
        or policy_contract["sha256"] != policy_contract["evidence"]["sha256"]
        or policy_contract["evidence"]["bytes"] != len(policy_bytes())
    ):
        raise AssuranceContractError("readiness-policy contract is stale")

    expected_outcome = {
        0: "READY FOR ACCOUNTABLE-OWNER REVIEW",
        1: "MECHANICAL CHECK FAILED",
        2: "INVALID OR INTERNAL ERROR",
        3: "BLOCKED",
    }[int(readiness["exit_code"])]
    if (
        value["exit_code"] != readiness["exit_code"]
        or value["outcome"] != expected_outcome
    ):
        raise AssuranceContractError("top-level outcome disagrees with readiness")
