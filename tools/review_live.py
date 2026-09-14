from __future__ import annotations

import copy
import json
import math
from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .knowledge_common import KnowledgeFormatError, toolkit_root
from .review_current import ProtectedJudgeUnavailable, run_prior_integrated_judge
from .review_model import (
    ERROR_EXIT_CODE,
    SEMANTIC_EXIT_CODES,
    canonical_digest,
    error_payload,
    parse_rfc3339,
)
from .review_policy import effective_policy_issues
from .review_protected import (
    ProtectedAcquisitionUnavailable,
    ProtectedMainDocument,
    acquire_gnostoa_current_advisory_bundle,
)

_MAX_DOCUMENT_DEPTH = 64
_OCI_DIGEST_PREFIX = "@sha256:"
_GNOSTOA_SELF_REPOSITORY = "https://github.com/ktogias/gnostoa"
_AUTHORITY_SUBJECT = {
    "kind": "gnostoa-protected-main-record",
    "value": "tasks/issue-11-r2a-current-advisory.json:v1",
}

_FORMAT_CHECKER = FormatChecker()


@_FORMAT_CHECKER.checks("date-time")
def _is_strict_rfc3339(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parse_rfc3339(value)
    except ValueError:
        return False
    return True


class ProtectedEvaluationUnavailable(RuntimeError):
    """Raised when protected state cannot establish a trustworthy live route."""


class ProtectedRuntimeError(RuntimeError):
    """A fail-closed prior-integrated runtime or result failure."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _schema(name: str) -> dict[str, Any]:
    path = toolkit_root() / "schemas" / name
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ProtectedEvaluationUnavailable(f"schema must be an object: {path}")
    Draft202012Validator.check_schema(loaded)
    return loaded


def _schema_errors(document: object, schema_name: str) -> list[str]:
    validator = Draft202012Validator(
        _schema(schema_name),
        format_checker=_FORMAT_CHECKER,
    )
    errors = sorted(
        validator.iter_errors(document), key=lambda item: list(item.absolute_path)
    )
    rendered: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{location}: {error.message}")
    return rendered


def _assert_document_depth(document: object, label: str) -> None:
    pending: list[tuple[object, int]] = [(document, 1)]
    processed_depth: dict[int, int] = {}
    while pending:
        value, depth = pending.pop()
        if depth > _MAX_DOCUMENT_DEPTH:
            raise ValueError(
                f"{label} nests deeper than the {_MAX_DOCUMENT_DEPTH}-level operational bound"
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{label} contains a non-finite number")
        if not isinstance(value, (dict, list)):
            continue
        identity = id(value)
        previous_depth = processed_depth.get(identity)
        if previous_depth is not None and depth <= previous_depth:
            continue
        processed_depth[identity] = depth
        children = value.values() if isinstance(value, dict) else value
        pending.extend((child, depth + 1) for child in children)


def _trusted_cut() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _policy_projection(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": policy.get("id"),
        "version": policy.get("version"),
        "change_class": policy.get("change_class"),
        "review_requirement": policy.get("review_requirement"),
    }


def _validate_protected_bundle(protected: ProtectedMainDocument) -> dict[str, Any]:
    document = protected.document
    issues = _schema_errors(document, "review-protected-authority-bundle.schema.json")
    if issues:
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory authority does not satisfy its closed schema: "
            + "; ".join(issues)
        )
    authority = document.get("authority")
    policy = document.get("policy")
    qualification = document.get("qualification_snapshot")
    judge = document.get("acquired_judge")
    if not all(
        isinstance(value, dict) for value in (authority, policy, qualification, judge)
    ):
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory authority has invalid object members"
        )
    assert isinstance(authority, dict)
    assert isinstance(policy, dict)
    assert isinstance(qualification, dict)
    assert isinstance(judge, dict)
    if authority.get("subject") != _AUTHORITY_SUBJECT:
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory authority names an unexpected authority subject"
        )
    if authority.get("expected_judge") != judge:
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory authority judge identities conflict"
        )
    if canonical_digest(policy) != authority.get("policy_digest"):
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory policy digest does not match authority"
        )
    if canonical_digest(qualification) != authority.get(
        "qualification_snapshot_digest"
    ):
        raise ProtectedEvaluationUnavailable(
            "protected qualification snapshot digest does not match authority"
        )
    policy_issues = effective_policy_issues(policy)
    if policy_issues:
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory policy is not an effective policy: "
            + "; ".join(policy_issues)
        )
    if judge.get("acquisition") != "oci" or judge.get("status") != "accepted":
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory judge is not an accepted OCI judge"
        )
    if judge.get("source_revision") != judge.get("runtime_revision"):
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory judge source/runtime revisions disagree"
        )
    supported = judge.get("supported_input_schema_versions")
    if not isinstance(supported, list) or "1.0" not in supported:
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory judge does not support input schema 1.0"
        )
    runtime_image = judge.get("runtime_image")
    if (
        not isinstance(runtime_image, str)
        or _OCI_DIGEST_PREFIX not in runtime_image
        or not runtime_image.rsplit(_OCI_DIGEST_PREFIX, 1)[-1]
    ):
        raise ProtectedEvaluationUnavailable(
            "protected current-advisory judge does not name a digest-pinned OCI image"
        )
    return document


def _validate_live_input(input_document: object) -> dict[str, Any]:
    if not isinstance(input_document, dict):
        raise ValueError("review-check input must be an object")
    _assert_document_depth(input_document, "review-check input")
    issues = _schema_errors(input_document, "review-check-input.schema.json")
    if issues:
        raise ValueError(
            "review-check input does not satisfy its public schema: "
            + "; ".join(issues)
        )
    subject = input_document.get("subject")
    if (
        not isinstance(subject, dict)
        or subject.get("repository") != _GNOSTOA_SELF_REPOSITORY
    ):
        raise ValueError(
            "protected current-advisory route requires the Gnostoa-self repository"
        )
    context = input_document.get("evaluation_context")
    if not isinstance(context, dict):
        raise ValueError("current-advisory evaluation_context must be an object")
    if (
        context.get("mode") != "current_advisory"
        or context.get("judge_relation") != "prior_integrated"
        or context.get("fixture_only") is not False
    ):
        raise ValueError(
            "protected current-advisory route requires current_advisory, "
            "prior_integrated, fixture_only=false"
        )
    return input_document


def _trusted_live_input(
    input_document: dict[str, Any],
    bundle: dict[str, Any],
    trusted_cut: str,
) -> dict[str, Any]:
    for field, protected_field in (
        ("authority", "authority"),
        ("acquired_judge", "acquired_judge"),
        ("qualification_snapshot", "qualification_snapshot"),
    ):
        if input_document.get(field) != bundle.get(protected_field):
            raise ValueError(
                f"caller {field} does not match protected current-advisory authority"
            )
    delegated = copy.deepcopy(input_document)
    delegated["authority"] = copy.deepcopy(bundle["authority"])
    delegated["acquired_judge"] = copy.deepcopy(bundle["acquired_judge"])
    delegated["qualification_snapshot"] = copy.deepcopy(
        bundle["qualification_snapshot"]
    )
    delegated["evaluation_context"] = {
        "mode": "historical_replay",
        "as_of": trusted_cut,
        "judge_relation": "prior_integrated",
        "fixture_only": False,
    }
    return delegated


def _semantic_incomplete(
    input_document: dict[str, Any],
    bundle: dict[str, Any],
    trusted_cut: str,
    reason: str,
    diagnostic: str,
) -> tuple[int, dict[str, Any]]:
    policy = bundle["policy"]
    judge = bundle["acquired_judge"]
    authority = bundle["authority"]
    assert isinstance(policy, dict)
    assert isinstance(judge, dict)
    assert isinstance(authority, dict)
    payload: dict[str, Any] = {
        "outcome": "INCOMPLETE",
        "reason": reason,
        "binding": False,
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": trusted_cut,
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "subject": copy.deepcopy(input_document.get("subject", {})),
        "authority": copy.deepcopy(authority),
        "judge": copy.deepcopy(judge),
        "policy": _policy_projection(policy),
        "collection": {},
        "qualification": {},
        "quorum": {},
        "blockers": [],
        "conflicts": [],
        "exclusions": [],
        "diagnostics": [diagnostic],
        "assessments": [],
    }
    result_issues = _schema_errors(payload, "review-gate-result.schema.json")
    if result_issues:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected current-advisory incomplete result violates the public schema",
            details={"issues": result_issues},
        )
    return SEMANTIC_EXIT_CODES["INCOMPLETE"], payload


def _execute_semantic_review(
    delegated_input: dict[str, Any],
    bundle: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    judge = bundle["acquired_judge"]
    policy = bundle["policy"]
    assert isinstance(judge, dict)
    assert isinstance(policy, dict)
    runtime_image = judge.get("runtime_image")
    runtime_revision = judge.get("runtime_revision")
    public_surface_digest = judge.get("public_surface_digest")
    if not all(
        isinstance(value, str)
        for value in (runtime_image, runtime_revision, public_surface_digest)
    ):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "protected judge runtime identity is malformed",
        )
    assert isinstance(runtime_image, str)
    assert isinstance(runtime_revision, str)
    assert isinstance(public_surface_digest, str)

    try:
        exit_code, result = run_prior_integrated_judge(
            image=runtime_image,
            input_document=delegated_input,
            policy_document=policy,
            expected_revision=runtime_revision,
            expected_surface_digest=public_surface_digest,
        )
    except ProtectedJudgeUnavailable as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
            str(exc),
        ) from exc

    result_issues = _schema_errors(result, "review-gate-result.schema.json")
    if result_issues:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result violates the public schema: "
            + "; ".join(result_issues),
        )
    outcome = result.get("outcome")
    expected_exit = (
        SEMANTIC_EXIT_CODES.get(outcome) if isinstance(outcome, str) else None
    )
    if expected_exit is None or exit_code != expected_exit:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge process exit does not match semantic outcome",
        )
    if result.get("evaluation_context") != delegated_input.get("evaluation_context"):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge changed the delegated evaluation context",
        )
    if result.get("subject") != delegated_input.get("subject"):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge changed the delegated subject",
        )
    if result.get("authority") != bundle.get("authority"):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result authority does not match protected state",
        )
    if result.get("judge") != bundle.get("acquired_judge"):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result identity does not match protected state",
        )
    if result.get("policy") != _policy_projection(policy):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result policy does not match protected state",
        )
    if result.get("binding") is not False:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge attempted to return a binding result",
        )
    return expected_exit, result


def evaluate_gnostoa_current_advisory(
    input_document: object,
) -> tuple[int, dict[str, Any]]:
    """Evaluate Gnostoa-self current advisory through protected prior-integrated OCI.

    The caller supplies only untrusted review input. Repository, branch, authority,
    policy, judge, runtime image, Docker context and evaluation-cut authority are
    selected internally from protected state and fixed production rules.
    """

    try:
        live_input = _validate_live_input(input_document)
        protected = acquire_gnostoa_current_advisory_bundle()
        bundle = _validate_protected_bundle(protected)
        trusted_cut = _trusted_cut()
        delegated = _trusted_live_input(live_input, bundle, trusted_cut)
    except ValueError as exc:
        return ERROR_EXIT_CODE, error_payload("MALFORMED_INVOCATION", str(exc))
    except ProtectedAcquisitionUnavailable as exc:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected current-advisory authority is unavailable",
            details={"error": str(exc)},
        )
    except (
        ProtectedEvaluationUnavailable,
        KnowledgeFormatError,
        OSError,
        SchemaError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
    ) as exc:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected current-advisory authority is invalid",
            details={"error": str(exc)},
        )

    try:
        _, result = _execute_semantic_review(delegated, bundle)
    except ProtectedRuntimeError as exc:
        return _semantic_incomplete(
            live_input,
            bundle,
            trusted_cut,
            exc.reason,
            str(exc),
        )

    projected = copy.deepcopy(result)
    projected["evaluation_context"] = {
        "mode": "current_advisory",
        "as_of": trusted_cut,
        "judge_relation": "prior_integrated",
        "fixture_only": False,
    }
    projected["binding"] = False
    diagnostics = projected.get("diagnostics")
    if not isinstance(diagnostics, list) or not all(
        isinstance(item, str) for item in diagnostics
    ):
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "prior-integrated judge returned malformed diagnostics",
        )
    projected["diagnostics"] = sorted(
        set(
            [
                *diagnostics,
                "semantic predicates executed by protected prior-integrated OCI using non-fixture historical-replay delegation",
                f"protected authority read from main revision {protected.protected_main_revision}",
            ]
        )
    )
    result_issues = _schema_errors(projected, "review-gate-result.schema.json")
    if result_issues:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "projected current-advisory result violates the public schema",
            details={"issues": result_issues},
        )
    outcome = projected.get("outcome")
    exit_code = SEMANTIC_EXIT_CODES.get(outcome) if isinstance(outcome, str) else None
    if exit_code is None:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "projected current-advisory result has unsupported outcome",
        )
    return exit_code, projected