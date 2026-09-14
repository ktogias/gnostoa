from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .knowledge_common import KnowledgeFormatError, toolkit_root
from .review_model import (
    ERROR_EXIT_CODE,
    SEMANTIC_EXIT_CODES,
    canonical_digest,
    canonical_json,
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
_MAX_RUNTIME_OUTPUT_BYTES = 2_097_152
_MAX_DOCKER_CONTROL_OUTPUT_BYTES = 8_388_608
_DOCKER_CONTROL_TIMEOUT_SECONDS = 120
_DOCKER_REVIEW_TIMEOUT_SECONDS = 180
_OCI_DIGEST = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_CONTAINER_ID = re.compile(r"^[0-9a-f]{12,64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
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
    """A fail-closed prior-integrated runtime observation or execution failure."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class _RuntimeExecution:
    exit_code: int
    stdout: bytes
    stderr: bytes


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


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtectedRuntimeError(
                "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
                f"prior-integrated judge result repeats field {key!r}",
            )
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise ProtectedRuntimeError(
        "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
        f"prior-integrated judge result contains non-finite JSON number {value!r}",
    )


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            f"prior-integrated judge result contains non-finite JSON number {value!r}",
        )
    return parsed


def _trusted_cut() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _docker_executable() -> str:
    executable = shutil.which("docker", path=os.defpath)
    if executable is None:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
            "Docker is unavailable on the protected current-advisory execution path",
        )
    return executable


def _docker_environment(config_directory: Path) -> dict[str, str]:
    return {
        "DOCKER_CONFIG": str(config_directory),
        "HOME": str(config_directory),
        "LANG": "C",
        "LC_ALL": "C",
    }


def _run_docker(
    arguments: list[str],
    *,
    environment: dict[str, str],
    timeout_seconds: int = _DOCKER_CONTROL_TIMEOUT_SECONDS,
    output_limit: int = _MAX_DOCKER_CONTROL_OUTPUT_BYTES,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            [_docker_executable(), *arguments],
            check=False,
            capture_output=True,
            timeout=timeout_seconds,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
            f"protected OCI execution failed: {exc}",
        ) from exc
    if len(result.stdout) + len(result.stderr) > output_limit:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "protected OCI execution exceeded its bounded output",
        )
    return result


def _docker_text(
    arguments: list[str],
    *,
    environment: dict[str, str],
    description: str,
) -> str:
    result = _run_docker(arguments, environment=environment)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
            detail or description,
        )
    try:
        return result.stdout.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            f"{description} returned non-UTF-8 output",
        ) from exc


def _pull_and_observe_image(
    image: str,
    expected_revision: str,
    *,
    environment: dict[str, str],
) -> str:
    if _OCI_DIGEST.fullmatch(image) is None:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "protected authority runtime_image is not digest-pinned OCI identity",
        )
    pull = _run_docker(["pull", image], environment=environment)
    if pull.returncode != 0:
        detail = pull.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
            detail or "cannot acquire the protected prior-integrated OCI judge",
        )

    repo_digests_text = _docker_text(
        ["image", "inspect", "--format", "{{json .RepoDigests}}", image],
        environment=environment,
        description="cannot inspect prior-integrated OCI repo digests",
    )
    try:
        repo_digests = json.loads(repo_digests_text)
    except json.JSONDecodeError as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "prior-integrated OCI repo-digest observation is malformed",
        ) from exc
    if not isinstance(repo_digests, list) or image not in repo_digests:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "pulled OCI image does not report the protected authority digest",
        )

    revision = _docker_text(
        [
            "image",
            "inspect",
            "--format",
            '{{index .Config.Labels "org.opencontainers.image.revision"}}',
            image,
        ],
        environment=environment,
        description="cannot inspect prior-integrated OCI revision label",
    )
    if revision != expected_revision:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "prior-integrated OCI revision label does not match protected authority",
        )

    image_id = _docker_text(
        ["image", "inspect", "--format", "{{.Id}}", image],
        environment=environment,
        description="cannot inspect prior-integrated OCI image id",
    )
    if _IMAGE_ID.fullmatch(image_id) is None:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "prior-integrated OCI image did not resolve to an immutable image id",
        )
    return image_id


def _execute_container(
    image: str,
    image_id: str,
    command: list[str],
    *,
    environment: dict[str, str],
    mount_source: Path | None = None,
) -> _RuntimeExecution:
    create_arguments = [
        "create",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "128",
        "--memory",
        "512m",
        "--user",
        "10001:10001",
    ]
    if mount_source is not None:
        rendered_source = str(mount_source)
        if "," in rendered_source:
            raise ProtectedRuntimeError(
                "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
                "protected review-input mount path is not Docker-mount safe",
            )
        create_arguments.extend(
            [
                "--mount",
                f"type=bind,source={rendered_source},target=/review-input,readonly",
            ]
        )
    create_arguments.extend([image, *command])
    created = _run_docker(create_arguments, environment=environment)
    if created.returncode != 0:
        detail = created.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
            detail or "cannot create prior-integrated OCI judge container",
        )
    try:
        container_id = created.stdout.decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "OCI runtime returned a non-ASCII container identifier",
        ) from exc
    if _CONTAINER_ID.fullmatch(container_id) is None:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "OCI runtime returned a malformed container identifier",
        )

    try:
        observed_image = _docker_text(
            ["container", "inspect", "--format", "{{.Config.Image}}", container_id],
            environment=environment,
            description="cannot inspect prior-integrated judge container image reference",
        )
        observed_image_id = _docker_text(
            ["container", "inspect", "--format", "{{.Image}}", container_id],
            environment=environment,
            description="cannot inspect prior-integrated judge container image id",
        )
        if observed_image != image or observed_image_id != image_id:
            raise ProtectedRuntimeError(
                "PRIOR_INTEGRATED_JUDGE_MISMATCH",
                "created judge container does not bind to the protected OCI identity",
            )

        attached = _run_docker(
            ["start", "--attach", container_id],
            environment=environment,
            timeout_seconds=_DOCKER_REVIEW_TIMEOUT_SECONDS,
            output_limit=_MAX_RUNTIME_OUTPUT_BYTES,
        )
        state = _docker_text(
            [
                "container",
                "inspect",
                "--format",
                "{{.State.Status}} {{.State.ExitCode}}",
                container_id,
            ],
            environment=environment,
            description="cannot inspect completed prior-integrated judge state",
        )
        pieces = state.split()
        if len(pieces) != 2 or pieces[0] != "exited":
            raise ProtectedRuntimeError(
                "PRIOR_INTEGRATED_JUDGE_UNAVAILABLE",
                "prior-integrated judge container did not reach a completed state",
            )
        try:
            exit_code = int(pieces[1])
        except ValueError as exc:
            raise ProtectedRuntimeError(
                "PRIOR_INTEGRATED_JUDGE_MISMATCH",
                "prior-integrated judge container exit status is malformed",
            ) from exc
        return _RuntimeExecution(
            exit_code=exit_code,
            stdout=attached.stdout,
            stderr=attached.stderr,
        )
    finally:
        _run_docker(
            ["rm", "--force", container_id],
            environment=environment,
            timeout_seconds=_DOCKER_CONTROL_TIMEOUT_SECONDS,
        )


def _observe_public_surface(
    image: str,
    image_id: str,
    expected_digest: str,
    *,
    environment: dict[str, str],
) -> None:
    execution = _execute_container(
        image,
        image_id,
        ["surface-digest", "--root", "/opt/gnostoa"],
        environment=environment,
    )
    if execution.exit_code != 0:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "prior-integrated judge cannot reproduce its protected public-surface digest",
        )
    try:
        observed = execution.stdout.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "prior-integrated public-surface observation is not UTF-8",
        ) from exc
    if observed != expected_digest:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_MISMATCH",
            "prior-integrated judge public surface does not match protected authority",
        )


def _parse_result(raw: bytes) -> dict[str, Any]:
    if len(raw) > _MAX_RUNTIME_OUTPUT_BYTES:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result exceeds its bounded size",
        )
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result is not UTF-8",
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            f"prior-integrated judge result is not canonical JSON: {exc}",
        ) from exc
    if not isinstance(value, dict):
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result must be a JSON object",
        )
    _assert_document_depth(value, "prior-integrated judge result")
    return value


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
    if not all(isinstance(value, dict) for value in (authority, policy, qualification, judge)):
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
    if canonical_digest(qualification) != authority.get("qualification_snapshot_digest"):
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
    if not isinstance(runtime_image, str) or _OCI_DIGEST.fullmatch(runtime_image) is None:
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
            "review-check input does not satisfy its public schema: " + "; ".join(issues)
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
            "protected current-advisory route requires current_advisory, prior_integrated, fixture_only=false"
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
    delegated["qualification_snapshot"] = copy.deepcopy(bundle["qualification_snapshot"])
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
        "policy": {
            "id": policy.get("id"),
            "version": policy.get("version"),
            "change_class": policy.get("change_class"),
            "review_requirement": policy.get("review_requirement"),
        },
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
    runtime_image = judge["runtime_image"]
    runtime_revision = judge["runtime_revision"]
    public_surface_digest = judge["public_surface_digest"]
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

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-live-") as directory:
        workspace = Path(directory)
        docker_config = workspace / "docker-config"
        review_input = workspace / "review-input"
        docker_config.mkdir(mode=0o700)
        review_input.mkdir(mode=0o755)
        environment = _docker_environment(docker_config)

        image_id = _pull_and_observe_image(
            runtime_image,
            runtime_revision,
            environment=environment,
        )
        _observe_public_surface(
            runtime_image,
            image_id,
            public_surface_digest,
            environment=environment,
        )

        input_path = review_input / "input.json"
        policy_path = review_input / "policy.json"
        input_path.write_text(canonical_json(delegated_input) + "\n", encoding="utf-8")
        policy_path.write_text(canonical_json(policy) + "\n", encoding="utf-8")
        input_path.chmod(0o444)
        policy_path.chmod(0o444)

        execution = _execute_container(
            runtime_image,
            image_id,
            [
                "review-check",
                "--input",
                "/review-input/input.json",
                "--policy",
                "/review-input/policy.json",
            ],
            environment=environment,
            mount_source=review_input,
        )

    result = _parse_result(execution.stdout)
    result_issues = _schema_errors(result, "review-gate-result.schema.json")
    if result_issues:
        raise ProtectedRuntimeError(
            "PRIOR_INTEGRATED_JUDGE_INVALID_RESULT",
            "prior-integrated judge result violates the public schema: "
            + "; ".join(result_issues),
        )
    outcome = result.get("outcome")
    expected_exit = SEMANTIC_EXIT_CODES.get(outcome) if isinstance(outcome, str) else None
    if expected_exit is None or execution.exit_code != expected_exit:
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
