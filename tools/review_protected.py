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

from .review_model import (
    ERROR_EXIT_CODE,
    SEMANTIC_EXIT_CODES,
    canonical_digest,
    canonical_json,
    error_payload,
    parse_rfc3339,
)

_GNOSTOA_SELF_REPOSITORY = "https://github.com/ktogias/gnostoa.git"
_GNOSTOA_SELF_BUNDLE_PATH = "tasks/issue-11-r2a-current-advisory.json"
_GNOSTOA_SELF_BUNDLE_SCHEMA_PATH = (
    "schemas/review-protected-authority-bundle.schema.json"
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_PINNED_OCI = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
_GIT_TIMEOUT_SECONDS = 20
_DOCKER_PULL_TIMEOUT_SECONDS = 120
_DOCKER_RUN_TIMEOUT_SECONDS = 30
_MAX_PROTECTED_DOCUMENT_BYTES = 2_097_152
_MAX_JUDGE_OUTPUT_BYTES = 2_097_152
_PROTECTED_FORMAT_CHECKER = FormatChecker()


@_PROTECTED_FORMAT_CHECKER.checks("date-time")
def _is_strict_rfc3339(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parse_rfc3339(value)
    except ValueError:
        return False
    return True


class ProtectedAcquisitionUnavailable(RuntimeError):
    """Raised when protected-main authority cannot be acquired exactly."""


class ProtectedJudgeUnavailable(RuntimeError):
    """Raised when the authority-bound OCI judge cannot be executed."""


class ProtectedJudgeBindingMismatch(RuntimeError):
    """Raised when observed OCI identity disagrees with protected authority."""


@dataclass(frozen=True)
class ProtectedMainDocument:
    protected_main_revision: str
    document: dict[str, Any]


@dataclass(frozen=True)
class ProtectedCurrentAdvisoryAuthority:
    protected_main_revision: str
    document: dict[str, Any]
    schema: dict[str, Any]


def _git_executable() -> str:
    executable = shutil.which("git", path=os.defpath)
    if executable is None:
        raise ProtectedAcquisitionUnavailable(
            "Git is unavailable on the bounded protected-main acquisition path"
        )
    return executable


def _git_environment() -> dict[str, str]:
    # Do not inherit caller-controlled Git configuration, repository selectors,
    # credential helpers or URL rewrite rules. The protected route is public,
    # read-only GitHub HTTPS and therefore needs no caller credentials.
    return {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }


def _run_git(
    arguments: list[str],
    *,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [_git_executable(), *arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            env=_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedAcquisitionUnavailable(
            f"protected Git read-back failed: {exc}"
        ) from exc


def _git_output(
    arguments: list[str],
    *,
    cwd: Path,
    description: str,
) -> bytes:
    result = _run_git(arguments, cwd=cwd)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedAcquisitionUnavailable(detail or description)
    return result.stdout


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtectedAcquisitionUnavailable(
                f"protected authority document repeats field {key!r}"
            )
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise ProtectedAcquisitionUnavailable(
        f"protected authority document contains non-finite JSON number {value!r}"
    )


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtectedAcquisitionUnavailable(
            f"protected authority document contains non-finite JSON number {value!r}"
        )
    return parsed


def _prepare_protected_repository(repository: Path, repository_url: str) -> str:
    init = _run_git(["init", "-q", str(repository)])
    if init.returncode != 0:
        raise ProtectedAcquisitionUnavailable(
            "cannot create bounded protected-main Git read-back workspace"
        )
    _git_output(
        [
            "fetch",
            "--quiet",
            "--no-tags",
            "--depth=1",
            repository_url,
            "+refs/heads/main:refs/remotes/protected/main",
        ],
        cwd=repository,
        description="cannot fetch protected main",
    )
    protected_main_revision = (
        _git_output(
            ["rev-parse", "refs/remotes/protected/main"],
            cwd=repository,
            description="cannot resolve protected main",
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if not _SHA40.fullmatch(protected_main_revision):
        raise ProtectedAcquisitionUnavailable(
            "protected main did not resolve to an exact Git commit"
        )
    return protected_main_revision


def _read_protected_json_object(
    repository: Path,
    protected_main_revision: str,
    path: str,
    *,
    description: str,
) -> dict[str, Any]:
    object_spec = f"{protected_main_revision}:{path}"
    encoded_size = _git_output(
        ["cat-file", "-s", object_spec],
        cwd=repository,
        description=f"{description} is unavailable",
    )
    try:
        object_size = int(encoded_size.decode("ascii", errors="strict").strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtectedAcquisitionUnavailable(f"{description} size is invalid") from exc
    if object_size > _MAX_PROTECTED_DOCUMENT_BYTES:
        raise ProtectedAcquisitionUnavailable(f"{description} exceeds the bounded size")

    raw = _git_output(
        ["show", object_spec],
        cwd=repository,
        description=f"{description} is unavailable",
    )
    if len(raw) != object_size:
        raise ProtectedAcquisitionUnavailable(f"{description} size changed during read-back")
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtectedAcquisitionUnavailable(f"{description} is invalid: {exc}") from exc
    if not isinstance(document, dict):
        raise ProtectedAcquisitionUnavailable(f"{description} must be an object")
    return document


def _acquire_from_repository(
    repository_url: str,
    bundle_path: str,
) -> ProtectedMainDocument:
    """Test seam for the fixed production read-back route.

    Production does not expose these selectors; callers of the public acquisition
    function cannot replace the Gnostoa repository, protected branch or bundle path.
    """

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-protected-") as directory:
        repository = Path(directory)
        protected_main_revision = _prepare_protected_repository(repository, repository_url)
        document = _read_protected_json_object(
            repository,
            protected_main_revision,
            bundle_path,
            description="protected current-advisory authority document",
        )

    return ProtectedMainDocument(
        protected_main_revision=protected_main_revision,
        document=document,
    )


def _acquire_authority_from_repository(
    repository_url: str,
    bundle_path: str,
    schema_path: str,
) -> ProtectedCurrentAdvisoryAuthority:
    """Test seam that acquires authority data and schema from one protected cut."""

    with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-protected-") as directory:
        repository = Path(directory)
        protected_main_revision = _prepare_protected_repository(repository, repository_url)
        document = _read_protected_json_object(
            repository,
            protected_main_revision,
            bundle_path,
            description="protected current-advisory authority document",
        )
        schema = _read_protected_json_object(
            repository,
            protected_main_revision,
            schema_path,
            description="protected current-advisory authority schema",
        )

    return ProtectedCurrentAdvisoryAuthority(
        protected_main_revision=protected_main_revision,
        document=document,
        schema=schema,
    )


def acquire_gnostoa_current_advisory_bundle() -> ProtectedMainDocument:
    """Read the Gnostoa-self authority document from protected main only.

    P2a deliberately establishes provider acquisition, not execution identity and
    not semantic activation. The repository, branch and document path are fixed,
    and Git runs with a minimal configuration-free environment. P2b must
    independently bind a digest-pinned prior-integrated OCI execution identity
    before it may connect this provider record to current-advisory evaluation.
    """

    return _acquire_from_repository(
        _GNOSTOA_SELF_REPOSITORY,
        _GNOSTOA_SELF_BUNDLE_PATH,
    )


def acquire_gnostoa_current_advisory_authority() -> ProtectedCurrentAdvisoryAuthority:
    """Read the authority bundle and its schema from one protected-main revision."""

    return _acquire_authority_from_repository(
        _GNOSTOA_SELF_REPOSITORY,
        _GNOSTOA_SELF_BUNDLE_PATH,
        _GNOSTOA_SELF_BUNDLE_SCHEMA_PATH,
    )


def _authority_parts(
    protected: ProtectedCurrentAdvisoryAuthority,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        Draft202012Validator.check_schema(protected.schema)
    except SchemaError as exc:
        raise ProtectedAcquisitionUnavailable(
            f"protected current-advisory authority schema is invalid: {exc}"
        ) from exc
    errors = sorted(
        Draft202012Validator(
            protected.schema,
            format_checker=_PROTECTED_FORMAT_CHECKER,
        ).iter_errors(protected.document),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ProtectedAcquisitionUnavailable(
            f"protected current-advisory authority violates its schema: {rendered}"
        )

    authority = protected.document.get("authority")
    policy = protected.document.get("policy")
    qualification = protected.document.get("qualification_snapshot")
    judge = protected.document.get("acquired_judge")
    if not all(
        isinstance(value, dict) for value in (authority, policy, qualification, judge)
    ):
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory authority components must be objects"
        )
    assert isinstance(authority, dict)
    assert isinstance(policy, dict)
    assert isinstance(qualification, dict)
    assert isinstance(judge, dict)

    if authority.get("subject") != {
        "kind": "gnostoa-protected-main-record",
        "value": f"{_GNOSTOA_SELF_BUNDLE_PATH}:v1",
    }:
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory authority subject is not the admitted v1 record"
        )
    if authority.get("policy_digest") != canonical_digest(policy):
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory policy digest does not match its authority binding"
        )
    if authority.get("qualification_snapshot_digest") != canonical_digest(qualification):
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory qualification digest does not match its authority binding"
        )
    if authority.get("expected_judge") != judge:
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory expected and acquired judge bindings disagree"
        )
    if (
        judge.get("status") != "accepted"
        or judge.get("acquisition") != "oci"
        or judge.get("source_revision") != judge.get("runtime_revision")
    ):
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory judge is not an accepted prior-integrated OCI binding"
        )
    if protected.document.get("schema_version") != "1.0":
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory authority schema_version is unsupported"
        )
    supported = judge.get("supported_input_schema_versions")
    if not isinstance(supported, list) or "1.0" not in supported:
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory judge does not support input schema 1.0"
        )
    image = judge.get("runtime_image")
    if not isinstance(image, str) or _DIGEST_PINNED_OCI.fullmatch(image) is None:
        raise ProtectedAcquisitionUnavailable(
            "protected current-advisory judge runtime image is not digest-pinned"
        )
    return authority, policy, qualification, judge


def _docker_executable() -> str:
    executable = shutil.which("docker", path=os.defpath)
    if executable is None:
        raise ProtectedJudgeUnavailable(
            "Docker is unavailable for the prior-integrated OCI judge route"
        )
    return executable


def _docker_environment(config: Path) -> dict[str, str]:
    return {
        "DOCKER_CONFIG": str(config),
        "HOME": str(config),
        "LC_ALL": "C",
        "PATH": os.defpath,
    }


def _run_docker(
    arguments: list[str],
    *,
    config: Path,
    timeout: int,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            [_docker_executable(), *arguments],
            check=False,
            capture_output=True,
            timeout=timeout,
            env=_docker_environment(config),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedJudgeUnavailable(
            f"protected OCI judge invocation failed: {exc}"
        ) from exc
    if (
        len(result.stdout) > _MAX_JUDGE_OUTPUT_BYTES
        or len(result.stderr) > _MAX_JUDGE_OUTPUT_BYTES
    ):
        raise ProtectedJudgeUnavailable(
            "protected OCI judge emitted output larger than the bounded limit"
        )
    return result


def _docker_text(
    arguments: list[str],
    *,
    config: Path,
    description: str,
    timeout: int = _DOCKER_RUN_TIMEOUT_SECONDS,
) -> str:
    result = _run_docker(arguments, config=config, timeout=timeout)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedJudgeUnavailable(detail or description)
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ProtectedJudgeUnavailable(
            f"{description} returned non-UTF-8 output"
        ) from exc


def _verify_authority_bound_oci(
    judge: dict[str, Any],
    *,
    config: Path,
) -> str:
    image = judge["runtime_image"]
    assert isinstance(image, str)
    pull = _run_docker(
        ["pull", "--platform", "linux/amd64", image],
        config=config,
        timeout=_DOCKER_PULL_TIMEOUT_SECONDS,
    )
    if pull.returncode != 0:
        detail = pull.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedJudgeUnavailable(
            detail or "cannot anonymously acquire the authority-bound OCI judge"
        )

    repo_digests_text = _docker_text(
        ["image", "inspect", "--format", "{{json .RepoDigests}}", image],
        config=config,
        description="cannot observe prior-integrated OCI manifest identity",
    )
    try:
        repo_digests = json.loads(repo_digests_text)
    except json.JSONDecodeError as exc:
        raise ProtectedJudgeBindingMismatch(
            "observed OCI RepoDigests are not valid JSON"
        ) from exc
    if not isinstance(repo_digests, list) or image not in repo_digests:
        raise ProtectedJudgeBindingMismatch(
            "observed OCI manifest identity does not contain the authority-bound digest"
        )

    platform = _docker_text(
        ["image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", image],
        config=config,
        description="cannot observe prior-integrated OCI platform",
    )
    if platform != "linux/amd64":
        raise ProtectedJudgeBindingMismatch(
            f"authority-bound OCI platform mismatch: {platform!r}"
        )
    user = _docker_text(
        ["image", "inspect", "--format", "{{.Config.User}}", image],
        config=config,
        description="cannot observe prior-integrated OCI user",
    )
    if user != "kit":
        raise ProtectedJudgeBindingMismatch(
            f"authority-bound OCI runtime user mismatch: {user!r}"
        )
    revision = _docker_text(
        [
            "image",
            "inspect",
            "--format",
            "{{index .Config.Labels \"org.opencontainers.image.revision\"}}",
            image,
        ],
        config=config,
        description="cannot observe prior-integrated OCI source revision",
    )
    if revision != judge["source_revision"]:
        raise ProtectedJudgeBindingMismatch(
            "authority-bound OCI source revision does not match protected authority"
        )

    surface = _docker_text(
        [
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            image,
            "surface-digest",
            "--root",
            "/opt/gnostoa",
        ],
        config=config,
        description="cannot observe prior-integrated OCI public surface",
    )
    if surface != judge["public_surface_digest"]:
        raise ProtectedJudgeBindingMismatch(
            "authority-bound OCI public surface does not match protected authority"
        )
    return image


def _write_private_json(path: Path, value: object) -> None:
    encoded = (canonical_json(value) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)


def _parse_judge_payload(raw: bytes) -> dict[str, Any]:
    if len(raw) > _MAX_JUDGE_OUTPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected OCI judge result exceeds the bounded output limit"
        )
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtectedJudgeUnavailable(
            f"protected OCI judge returned invalid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ProtectedJudgeUnavailable(
            "protected OCI judge result must be a JSON object"
        )
    return payload


def _live_evaluation_context(as_of: str) -> dict[str, Any]:
    return {
        "mode": "current_advisory",
        "as_of": as_of,
        "judge_relation": "prior_integrated",
        "fixture_only": False,
    }


def _historical_evaluation_context(as_of: str) -> dict[str, Any]:
    return {
        "mode": "historical_replay",
        "as_of": as_of,
        "judge_relation": "prior_integrated",
        "fixture_only": False,
    }


def _now_rfc3339() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _policy_summary(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": policy.get("id"),
        "version": policy.get("version"),
        "change_class": policy.get("change_class"),
        "review_requirement": policy.get("review_requirement"),
    }


def _incomplete_live_result(
    *,
    input_document: dict[str, Any],
    authority: dict[str, Any],
    policy: dict[str, Any],
    judge: dict[str, Any],
    as_of: str,
    reason: str,
    diagnostics: list[str],
) -> dict[str, Any]:
    return {
        "outcome": "INCOMPLETE",
        "reason": reason,
        "binding": False,
        "evaluation_context": _live_evaluation_context(as_of),
        "subject": copy.deepcopy(input_document.get("subject", {})),
        "authority": copy.deepcopy(authority),
        "judge": copy.deepcopy(judge),
        "policy": _policy_summary(policy),
        "collection": {},
        "qualification": {},
        "quorum": {},
        "blockers": [],
        "conflicts": [],
        "exclusions": [],
        "diagnostics": diagnostics,
        "assessments": [],
    }


def _invoke_authority_bound_judge(
    *,
    image: str,
    input_document: dict[str, Any],
    policy: dict[str, Any],
    config: Path,
    payload_root: Path,
) -> tuple[int, dict[str, Any]]:
    input_path = payload_root / "input.json"
    policy_path = payload_root / "policy.json"
    _write_private_json(input_path, input_document)
    _write_private_json(policy_path, policy)
    mount = f"type=bind,source={payload_root},target=/gnostoa-r2a-input,readonly"
    result = _run_docker(
        [
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--mount",
            mount,
            image,
            "review-check",
            "--input",
            "/gnostoa-r2a-input/input.json",
            "--policy",
            "/gnostoa-r2a-input/policy.json",
        ],
        config=config,
        timeout=_DOCKER_RUN_TIMEOUT_SECONDS,
    )
    payload = _parse_judge_payload(result.stdout)
    if result.returncode == ERROR_EXIT_CODE:
        return ERROR_EXIT_CODE, payload
    outcome = payload.get("outcome")
    expected_exit = SEMANTIC_EXIT_CODES.get(outcome) if isinstance(outcome, str) else None
    if expected_exit is None or result.returncode != expected_exit:
        raise ProtectedJudgeBindingMismatch(
            "protected OCI judge exit code does not match its semantic outcome"
        )
    return result.returncode, payload


def evaluate_gnostoa_current_advisory(
    input_document: object,
) -> tuple[int, dict[str, Any]]:
    """Evaluate live Gnostoa-self current advisory through protected prior state.

    The only argument is untrusted review input. Repository, protected branch,
    authority/schema location, policy, qualification, judge image and evaluation
    clock are selected internally. The substantive predicates execute inside the
    authority-bound prior-integrated OCI judge through non-fixture historical
    replay; only its verified semantic result is projected back to the live
    current-advisory context.
    """

    if not isinstance(input_document, dict):
        return ERROR_EXIT_CODE, error_payload(
            "MALFORMED_INVOCATION",
            "current_advisory protected input must be an object",
        )
    context = input_document.get("evaluation_context")
    if not isinstance(context, dict):
        return ERROR_EXIT_CODE, error_payload(
            "MALFORMED_INVOCATION",
            "current_advisory evaluation_context must be an object",
        )
    if context.get("mode") != "current_advisory":
        return ERROR_EXIT_CODE, error_payload(
            "CONFIGURATION_ERROR",
            "protected Gnostoa current-advisory route requires mode current_advisory",
        )
    if context.get("judge_relation") != "prior_integrated":
        return ERROR_EXIT_CODE, error_payload(
            "CONFIGURATION_ERROR",
            "protected Gnostoa current-advisory route requires prior_integrated judge relation",
        )
    if context.get("fixture_only", False) is not False:
        return ERROR_EXIT_CODE, error_payload(
            "CONFIGURATION_ERROR",
            "protected Gnostoa current_advisory cannot be fixture-only",
        )

    try:
        protected = acquire_gnostoa_current_advisory_authority()
        authority, policy, qualification, judge = _authority_parts(protected)
    except ProtectedAcquisitionUnavailable as exc:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            f"protected current-advisory authority acquisition failed: {exc}",
        )

    for field, expected in (
        ("authority", authority),
        ("acquired_judge", judge),
        ("qualification_snapshot", qualification),
    ):
        if input_document.get(field) != expected:
            return ERROR_EXIT_CODE, error_payload(
                "CONFIGURATION_ERROR",
                f"caller {field} does not match protected current-advisory state",
            )

    schema_version = input_document.get("schema_version")
    supported = judge.get("supported_input_schema_versions")
    if not isinstance(schema_version, str) or not isinstance(supported, list):
        return ERROR_EXIT_CODE, error_payload(
            "UNSUPPORTED_INPUT",
            "current-advisory input schema version is not usable by the protected judge",
        )
    if schema_version not in supported:
        return ERROR_EXIT_CODE, error_payload(
            "UNSUPPORTED_INPUT",
            "current-advisory input schema version is unsupported by the protected judge",
        )

    as_of = _now_rfc3339()
    historical_input = copy.deepcopy(input_document)
    historical_input["authority"] = copy.deepcopy(authority)
    historical_input["acquired_judge"] = copy.deepcopy(judge)
    historical_input["qualification_snapshot"] = copy.deepcopy(qualification)
    historical_context = _historical_evaluation_context(as_of)
    historical_input["evaluation_context"] = historical_context

    try:
        with tempfile.TemporaryDirectory(prefix="gnostoa-r2a-live-", dir="/tmp") as directory:
            root = Path(directory)
            docker_config = root / "docker"
            payload_root = root / "payload"
            docker_config.mkdir(mode=0o700)
            payload_root.mkdir(mode=0o700)
            image = _verify_authority_bound_oci(judge, config=docker_config)
            code, payload = _invoke_authority_bound_judge(
                image=image,
                input_document=historical_input,
                policy=policy,
                config=docker_config,
                payload_root=payload_root,
            )
    except ProtectedJudgeBindingMismatch as exc:
        return 3, _incomplete_live_result(
            input_document=input_document,
            authority=authority,
            policy=policy,
            judge=judge,
            as_of=as_of,
            reason="JUDGE_BINDING_UNRESOLVED",
            diagnostics=[str(exc)],
        )
    except ProtectedJudgeUnavailable as exc:
        return 3, _incomplete_live_result(
            input_document=input_document,
            authority=authority,
            policy=policy,
            judge=judge,
            as_of=as_of,
            reason="JUDGE_UNAVAILABLE",
            diagnostics=[str(exc)],
        )
    except OSError as exc:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            f"protected current-advisory workspace failed: {exc}",
        )

    if code == ERROR_EXIT_CODE:
        return code, payload
    if payload.get("binding") is not False:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected OCI judge returned a result with non-advisory binding",
        )
    if payload.get("evaluation_context") != historical_context:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected OCI judge changed the internally selected historical evaluation context",
        )
    if payload.get("subject") != historical_input.get("subject"):
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected OCI judge result subject does not match the requested subject",
        )
    if payload.get("authority") != authority or payload.get("judge") != judge:
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected OCI judge result does not preserve protected authority/judge binding",
        )
    if payload.get("policy") != _policy_summary(policy):
        return ERROR_EXIT_CODE, error_payload(
            "TOOL_ERROR",
            "protected OCI judge result policy does not match protected authority",
        )

    projected = copy.deepcopy(payload)
    projected["evaluation_context"] = _live_evaluation_context(as_of)
    return code, projected
