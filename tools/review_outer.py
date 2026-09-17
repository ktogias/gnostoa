from __future__ import annotations

import json
import math
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, NoReturn

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from .knowledge_common import toolkit_root
from .review_current import ProtectedJudgeUnavailable, _checked_output, _run_docker
from .review_model import (
    ERROR_EXIT_CODE,
    SEMANTIC_EXIT_CODES,
    canonical_json,
    error_payload,
    parse_rfc3339,
)
from .review_protected import (
    ProtectedAcquisitionUnavailable,
    acquire_gnostoa_current_advisory_consumer,
)

_DAEMON_IMAGE = (
    "docker.io/library/docker@"
    "sha256:76cd6bbc3ab600fced21a7e1bea77ac00cb7c545eb95d5767e4ec4ffbcb242dc"
)
_DIGEST_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+"
    r"@sha256:[0-9a-f]{64}$"
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_RESOURCE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")
_MAX_RESULT_BYTES = 2_097_152
_DAEMON_READY_SECONDS = 30
_DOCKER_STEP_SECONDS = 120
_OUTER_RUNTIME_SECONDS = 180
_CLEANUP_ATTEMPTS = 3
_CLEANUP_BACKOFF_SECONDS = 0.25
_FORMAT_CHECKER = FormatChecker()
_PUBLIC_ERROR_CODES = {
    "MALFORMED_INVOCATION",
    "UNSUPPORTED_INPUT",
    "CONFIGURATION_ERROR",
    "TOOL_ERROR",
}


@_FORMAT_CHECKER.checks("date-time")
def _is_strict_rfc3339(value: object) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parse_rfc3339(value)
    except ValueError:
        return False
    return True


class PriorEffectiveOuterUnavailable(RuntimeError):
    """Raised when the protected prior-effective outer runtime cannot run safely."""


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PriorEffectiveOuterUnavailable(
                f"prior-effective outer result repeats field {key!r}"
            )
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise PriorEffectiveOuterUnavailable(
        f"prior-effective outer result contains non-finite JSON number {value!r}"
    )


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise PriorEffectiveOuterUnavailable(
            f"prior-effective outer result contains non-finite JSON number {value!r}"
        )
    return parsed


def _schema_errors(document: object, schema_name: str) -> list[str]:
    path = toolkit_root() / "schemas" / schema_name
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PriorEffectiveOuterUnavailable(
            f"installed schema must be an object: {path}"
        )
    Draft202012Validator.check_schema(loaded)
    validator = Draft202012Validator(loaded, format_checker=_FORMAT_CHECKER)
    errors = sorted(
        validator.iter_errors(document), key=lambda item: list(item.absolute_path)
    )
    return [
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def _validate_consumer_authority(document: object) -> dict[str, Any]:
    issues = _schema_errors(
        document,
        "review-protected-consumer-authority.schema.json",
    )
    if issues:
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer authority violates its closed schema: "
            + "; ".join(issues)
        )
    if not isinstance(document, dict):
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer authority must be an object"
        )
    expected = document.get("expected_consumer")
    acquired = document.get("acquired_consumer")
    if not isinstance(expected, dict) or not isinstance(acquired, dict):
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer authority has invalid consumer members"
        )
    if expected != acquired:
        raise PriorEffectiveOuterUnavailable(
            "protected expected/acquired outer-consumer identities conflict"
        )
    if acquired.get("acquisition") != "oci" or acquired.get("status") != "accepted":
        raise PriorEffectiveOuterUnavailable(
            "protected outer consumer is not an accepted OCI identity"
        )
    runtime_image = acquired.get("runtime_image")
    runtime_revision = acquired.get("runtime_revision")
    source_revision = acquired.get("source_revision")
    public_surface_digest = acquired.get("public_surface_digest")
    if (
        not isinstance(runtime_image, str)
        or _DIGEST_IMAGE.fullmatch(runtime_image) is None
    ):
        raise PriorEffectiveOuterUnavailable(
            "protected outer consumer is not digest-pinned"
        )
    if (
        not isinstance(runtime_revision, str)
        or _SHA40.fullmatch(runtime_revision) is None
    ):
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer runtime revision is invalid"
        )
    if source_revision != runtime_revision:
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer source/runtime revisions disagree"
        )
    if (
        not isinstance(public_surface_digest, str)
        or _SHA256.fullmatch(public_surface_digest) is None
    ):
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer public-surface digest is invalid"
        )
    supported = acquired.get("supported_input_schema_versions")
    if not isinstance(supported, list) or "1.0" not in supported:
        raise PriorEffectiveOuterUnavailable(
            "protected outer consumer does not support input schema 1.0"
        )
    return acquired


def _new_resource_name(role: str) -> str:
    name = f"gnostoa-r2a-{role}-{uuid.uuid4().hex}"
    if _RESOURCE_NAME.fullmatch(name) is None:
        raise PriorEffectiveOuterUnavailable(
            "generated Docker resource name is invalid"
        )
    return name


def _volume_create(
    name: str,
    config_dir: Path,
    owned_volumes: list[str],
) -> str:
    if _RESOURCE_NAME.fullmatch(name) is None:
        raise PriorEffectiveOuterUnavailable("isolated-volume name is invalid")
    # Register the exact predeclared name before the effect-capable Docker call.
    # A timeout or transport failure can be ambiguous after Docker has created
    # the object; final cleanup can therefore reconcile this name either way.
    owned_volumes.append(name)
    raw = _checked_output(
        ["volume", "create", name],
        config_dir=config_dir,
        description="cannot create isolated R2A volume",
        timeout=30,
    )
    observed = raw.decode("ascii", errors="strict").strip()
    if observed != name:
        raise PriorEffectiveOuterUnavailable(
            "Docker returned a malformed isolated-volume identity"
        )
    return name


def _container_create(
    arguments: list[str],
    name: str,
    config_dir: Path,
    owned_containers: list[str],
) -> str:
    if _RESOURCE_NAME.fullmatch(name) is None:
        raise PriorEffectiveOuterUnavailable("isolated-container name is invalid")
    # Preserve cleanup authority before the create call for the same ambiguous
    # timeout/transport-failure window as volumes. Removing a name that was not
    # created is explicitly treated as successful reconciliation.
    owned_containers.append(name)
    raw = _checked_output(
        ["create", "--name", name, *arguments],
        config_dir=config_dir,
        description="cannot create isolated R2A container",
        timeout=30,
    )
    container_id = raw.decode("ascii", errors="strict").strip()
    if _CONTAINER_ID.fullmatch(container_id) is None:
        raise PriorEffectiveOuterUnavailable(
            "Docker returned a malformed isolated-container identity"
        )
    return name


def _remove_container(container_name: str, config_dir: Path) -> str | None:
    last_issue = f"cannot remove owned container {container_name}"
    for attempt in range(_CLEANUP_ATTEMPTS):
        try:
            result = _run_docker(
                ["rm", "-f", container_name],
                config_dir=config_dir,
                timeout=30,
            )
        except ProtectedJudgeUnavailable as exc:
            last_issue = str(exc)
        else:
            if result.returncode == 0:
                return None
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            if "no such container" in detail.lower():
                return None
            last_issue = detail or f"cannot remove owned container {container_name}"
        if attempt + 1 < _CLEANUP_ATTEMPTS:
            time.sleep(_CLEANUP_BACKOFF_SECONDS * (attempt + 1))
    return f"cannot remove owned container {container_name}: {last_issue}"


def _remove_volume(volume_name: str, config_dir: Path) -> str | None:
    last_issue = f"cannot remove owned volume {volume_name}"
    for attempt in range(_CLEANUP_ATTEMPTS):
        try:
            result = _run_docker(
                ["volume", "rm", volume_name],
                config_dir=config_dir,
                timeout=30,
            )
        except ProtectedJudgeUnavailable as exc:
            last_issue = str(exc)
        else:
            if result.returncode == 0:
                return None
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            if "no such volume" in detail.lower():
                return None
            last_issue = detail or f"cannot remove owned volume {volume_name}"
        if attempt + 1 < _CLEANUP_ATTEMPTS:
            time.sleep(_CLEANUP_BACKOFF_SECONDS * (attempt + 1))
    return f"cannot remove owned volume {volume_name}: {last_issue}"


def _initialize_tmp_volume(
    *,
    tmp_volume: str,
    config_dir: Path,
    owned_containers: list[str],
) -> None:
    helper_name = _new_resource_name("tmp-init")
    container_name = _container_create(
        [
            "--volume",
            f"{tmp_volume}:/tmp",
            "--entrypoint",
            "sh",
            _DAEMON_IMAGE,
            "-c",
            "chmod 1777 /tmp",
        ],
        helper_name,
        config_dir,
        owned_containers,
    )
    primary_issue: str | None = None
    try:
        result = _run_docker(
            ["start", "--attach", container_name],
            config_dir=config_dir,
            timeout=30,
        )
        if result.returncode != 0:
            primary_issue = "cannot initialize isolated R2A /tmp volume"
    except ProtectedJudgeUnavailable as exc:
        primary_issue = str(exc)

    cleanup_issue = _remove_container(container_name, config_dir)
    if cleanup_issue is None:
        owned_containers.remove(container_name)
    issues = [item for item in (primary_issue, cleanup_issue) if item]
    if issues:
        raise PriorEffectiveOuterUnavailable("; ".join(issues))


def _build_isolated_execution_plan(
    *,
    consumer: dict[str, Any],
    input_dir: Path,
    socket_volume: str,
    tmp_volume: str,
    daemon_name: str,
    outer_name: str,
) -> dict[str, object]:
    """Build the fixed B2 topology without exposing any public trust selector."""

    image = consumer.get("runtime_image")
    if not isinstance(image, str) or _DIGEST_IMAGE.fullmatch(image) is None:
        raise PriorEffectiveOuterUnavailable("outer runtime image is not digest-pinned")

    daemon = [
        "--label",
        f"gnostoa.r2a.role={daemon_name}",
        "--log-driver",
        "none",
        "--privileged",
        "--env",
        "DOCKER_TLS_CERTDIR=",
        "--volume",
        f"{socket_volume}:/gnostoa-docker",
        "--volume",
        f"{tmp_volume}:/tmp",
        _DAEMON_IMAGE,
        "dockerd",
        "--host=unix:///gnostoa-docker/docker.sock",
        "--group=10001",
        "--log-driver=none",
    ]
    outer = [
        "--label",
        f"gnostoa.r2a.role={outer_name}",
        "--log-driver",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--volume",
        f"{socket_volume}:/var/run",
        "--volume",
        f"{tmp_volume}:/tmp",
        "--mount",
        f"type=bind,src={input_dir},dst=/gnostoa-input,readonly",
        "--entrypoint",
        "python",
        image,
        "-m",
        "tools.review_live_entrypoint",
        "--input",
        "/gnostoa-input/input.json",
    ]
    return {
        "daemon_image": _DAEMON_IMAGE,
        "daemon": daemon,
        "outer": outer,
    }


def _wait_for_daemon(container_name: str, config_dir: Path) -> None:
    deadline = time.monotonic() + _DAEMON_READY_SECONDS
    while time.monotonic() < deadline:
        result = _run_docker(
            [
                "exec",
                container_name,
                "docker",
                "--host",
                "unix:///gnostoa-docker/docker.sock",
                "info",
            ],
            config_dir=config_dir,
            timeout=5,
        )
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise PriorEffectiveOuterUnavailable("isolated Docker daemon did not become ready")


def _listening_tcp_ports(raw: bytes) -> set[int]:
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise PriorEffectiveOuterUnavailable(
            "isolated Docker daemon socket table is not ASCII"
        ) from exc

    valid_headers = {
        ("sl", "local_address", "rem_address", "st"),
        ("sl", "local_address", "remote_address", "st"),
    }
    saw_header = False
    listening: set[int] = set()
    for line in text.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "sl":
            if tuple(fields[:4]) not in valid_headers:
                raise PriorEffectiveOuterUnavailable(
                    "isolated Docker daemon socket table is malformed"
                )
            saw_header = True
            continue
        if not saw_header:
            raise PriorEffectiveOuterUnavailable(
                "isolated Docker daemon socket table is malformed"
            )
        if not fields[0].endswith(":") or not fields[0][:-1].isdigit():
            raise PriorEffectiveOuterUnavailable(
                "isolated Docker daemon socket table is malformed"
            )
        if len(fields) < 4:
            raise PriorEffectiveOuterUnavailable(
                "isolated Docker daemon socket table is malformed"
            )
        local_address = fields[1]
        remote_address = fields[2]
        state = fields[3].upper()
        for address in (local_address, remote_address):
            parts = address.split(":")
            if len(parts) != 2:
                raise PriorEffectiveOuterUnavailable(
                    "isolated Docker daemon socket table is malformed"
                )
            host_hex, port_hex = parts
            if len(host_hex) not in {8, 32} or len(port_hex) != 4:
                raise PriorEffectiveOuterUnavailable(
                    "isolated Docker daemon socket table is malformed"
                )
            try:
                int(host_hex, 16)
                int(port_hex, 16)
            except ValueError as exc:
                raise PriorEffectiveOuterUnavailable(
                    "isolated Docker daemon socket table is malformed"
                ) from exc
        if len(state) != 2:
            raise PriorEffectiveOuterUnavailable(
                "isolated Docker daemon socket table is malformed"
            )
        try:
            int(state, 16)
            port = int(local_address.rsplit(":", 1)[1], 16)
        except ValueError as exc:
            raise PriorEffectiveOuterUnavailable(
                "isolated Docker daemon socket table is malformed"
            ) from exc
        if state == "0A":
            listening.add(port)
    if not saw_header:
        raise PriorEffectiveOuterUnavailable(
            "isolated Docker daemon socket table is malformed"
        )
    return listening


def _verify_daemon_control_plane(container_name: str, config_dir: Path) -> None:
    result = _run_docker(
        [
            "exec",
            container_name,
            "sh",
            "-ec",
            "cat /proc/1/net/tcp; [ ! -r /proc/1/net/tcp6 ] || cat /proc/1/net/tcp6",
        ],
        config_dir=config_dir,
        timeout=5,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise PriorEffectiveOuterUnavailable(
            "cannot inspect isolated Docker daemon listening sockets"
            + (f": {detail}" if detail else "")
        )
    forbidden = sorted({2375, 2376} & _listening_tcp_ports(result.stdout))
    if forbidden:
        ports = ", ".join(str(port) for port in forbidden)
        raise PriorEffectiveOuterUnavailable(
            f"isolated Docker daemon unexpectedly exposes TCP control plane on {ports}"
        )


def _verify_outer_image(consumer: dict[str, Any], config_dir: Path) -> None:
    image = consumer["runtime_image"]
    runtime_revision = consumer["runtime_revision"]
    public_surface_digest = consumer["public_surface_digest"]
    assert isinstance(image, str)
    assert isinstance(runtime_revision, str)
    assert isinstance(public_surface_digest, str)

    _checked_output(
        ["pull", image],
        config_dir=config_dir,
        description="cannot reacquire protected outer-consumer image",
        timeout=_DOCKER_STEP_SECONDS,
    )
    repo_digests_raw = _checked_output(
        ["image", "inspect", "--format", "{{json .RepoDigests}}", image],
        config_dir=config_dir,
        description="cannot inspect protected outer-consumer repo digests",
        timeout=30,
    )
    try:
        repo_digests = json.loads(repo_digests_raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer repo-digest observation is malformed"
        ) from exc
    if not isinstance(repo_digests, list) or image not in repo_digests:
        raise PriorEffectiveOuterUnavailable(
            "protected outer consumer does not report the authority-bound digest"
        )

    observed = (
        _checked_output(
            [
                "image",
                "inspect",
                "--format",
                '{{.Os}}|{{.Architecture}}|{{.Config.User}}|{{index .Config.Labels "org.opencontainers.image.revision"}}',
                image,
            ],
            config_dir=config_dir,
            description="cannot inspect protected outer-consumer identity",
            timeout=30,
        )
        .decode("utf-8", errors="strict")
        .strip()
    )
    if observed.split("|") != ["linux", "amd64", "kit", runtime_revision]:
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer runtime identity does not match authority"
        )

    effective_ids = (
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
                image,
                "-ec",
                "id -u; id -g",
            ],
            config_dir=config_dir,
            description="cannot verify protected outer-consumer runtime uid/gid",
            timeout=30,
        )
        .decode("ascii", errors="strict")
        .splitlines()
    )
    if effective_ids != ["10001", "10001"]:
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer runtime uid/gid do not match Docker socket ownership contract"
        )

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
                image,
                "-m",
                "tools.cli",
                "surface-digest",
                "--root",
                "/opt/gnostoa",
            ],
            config_dir=config_dir,
            description="cannot measure protected outer-consumer public surface",
            timeout=60,
        )
        .decode("ascii", errors="strict")
        .strip()
    )
    if surface != public_surface_digest:
        raise PriorEffectiveOuterUnavailable(
            "protected outer-consumer public surface does not match authority"
        )


def _decode_outer_result(exit_code: int, raw: bytes) -> dict[str, Any]:
    if len(raw) > _MAX_RESULT_BYTES:
        raise PriorEffectiveOuterUnavailable(
            "prior-effective outer result exceeds the bounded size"
        )
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PriorEffectiveOuterUnavailable(
            f"prior-effective outer result is invalid JSON: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise PriorEffectiveOuterUnavailable(
            "prior-effective outer result must be an object"
        )
    canonical = (canonical_json(document) + "\n").encode("utf-8")
    if raw != canonical:
        raise PriorEffectiveOuterUnavailable(
            "prior-effective outer result is not canonical JSON"
        )

    outcome = document.get("outcome")
    if isinstance(outcome, str):
        issues = _schema_errors(document, "review-gate-result.schema.json")
        if issues:
            raise PriorEffectiveOuterUnavailable(
                "prior-effective outer semantic result violates the public schema: "
                + "; ".join(issues)
            )
        expected_exit = SEMANTIC_EXIT_CODES.get(outcome)
        if expected_exit is None or exit_code != expected_exit:
            raise PriorEffectiveOuterUnavailable(
                "prior-effective outer exit does not match semantic outcome"
            )
        if document.get("binding") is not False:
            raise PriorEffectiveOuterUnavailable(
                "prior-effective outer runtime attempted a binding result"
            )
        return document

    error = document.get("error")
    if (
        exit_code != ERROR_EXIT_CODE
        or set(document) != {"error"}
        or not isinstance(error, dict)
        or set(error) != {"code", "message", "details"}
    ):
        raise PriorEffectiveOuterUnavailable(
            "prior-effective outer error envelope is malformed"
        )
    code = error.get("code")
    message = error.get("message")
    details = error.get("details")
    if (
        not isinstance(code, str)
        or code not in _PUBLIC_ERROR_CODES
        or not isinstance(message, str)
        or not isinstance(details, dict)
    ):
        raise PriorEffectiveOuterUnavailable(
            "prior-effective outer error envelope is malformed"
        )
    return document


def _operational_error(message: str) -> tuple[int, bytes]:
    payload = error_payload(
        "TOOL_ERROR",
        "protected prior-effective outer consumer is unavailable",
        details={"error": message},
    )
    return ERROR_EXIT_CODE, (canonical_json(payload) + "\n").encode("utf-8")


def run_prior_effective_current_advisory(
    input_document: object,
) -> tuple[int, bytes]:
    """Run current-advisory through the protected outer runtime and an isolated daemon.

    Public callers provide only untrusted review input. Protected main selects the
    outer runtime. The host Docker daemon owns bounded lifecycle orchestration only;
    it is never mounted into the protected outer runtime. The outer runtime receives
    a Unix socket from an isolated nested daemon and returns the canonical result.
    """

    owned_containers: list[str] = []
    owned_volumes: list[str] = []
    primary_error: str | None = None
    result: tuple[int, bytes] | None = None

    try:
        protected = acquire_gnostoa_current_advisory_consumer()
        consumer = _validate_consumer_authority(protected.document)
    except (
        json.JSONDecodeError,
        OSError,
        ProtectedAcquisitionUnavailable,
        PriorEffectiveOuterUnavailable,
        RecursionError,
        SchemaError,
        TypeError,
        ValueError,
    ) as exc:
        return _operational_error(str(exc))

    try:
        with tempfile.TemporaryDirectory(
            prefix="gnostoa-r2a-outer-", dir="/tmp"
        ) as directory:
            root = Path(directory)
            config_dir = root / "docker-config"
            input_dir = root / "input"
            config_dir.mkdir(mode=0o700)
            input_dir.mkdir(mode=0o755)
            input_path = input_dir / "input.json"
            try:
                input_path.write_text(
                    canonical_json(input_document) + "\n",
                    encoding="utf-8",
                )
                input_path.chmod(0o444)

                _verify_outer_image(consumer, config_dir)
                _checked_output(
                    ["pull", _DAEMON_IMAGE],
                    config_dir=config_dir,
                    description="cannot reacquire isolated Docker daemon image",
                    timeout=_DOCKER_STEP_SECONDS,
                )

                socket_volume = _new_resource_name("socket")
                _volume_create(socket_volume, config_dir, owned_volumes)
                tmp_volume = _new_resource_name("tmp")
                _volume_create(tmp_volume, config_dir, owned_volumes)
                _initialize_tmp_volume(
                    tmp_volume=tmp_volume,
                    config_dir=config_dir,
                    owned_containers=owned_containers,
                )

                daemon_name = _new_resource_name("daemon")
                outer_name = _new_resource_name("outer")
                plan = _build_isolated_execution_plan(
                    consumer=consumer,
                    input_dir=input_dir,
                    socket_volume=socket_volume,
                    tmp_volume=tmp_volume,
                    daemon_name=daemon_name,
                    outer_name=outer_name,
                )
                daemon_args = plan["daemon"]
                outer_args = plan["outer"]
                assert isinstance(daemon_args, list)
                assert isinstance(outer_args, list)

                daemon_container = _container_create(
                    [str(item) for item in daemon_args],
                    daemon_name,
                    config_dir,
                    owned_containers,
                )
                daemon_start = _run_docker(
                    ["start", daemon_container],
                    config_dir=config_dir,
                    timeout=30,
                )
                if daemon_start.returncode != 0:
                    raise PriorEffectiveOuterUnavailable(
                        "cannot start isolated Docker daemon"
                    )
                _wait_for_daemon(daemon_container, config_dir)
                _verify_daemon_control_plane(daemon_container, config_dir)

                outer_container = _container_create(
                    [str(item) for item in outer_args],
                    outer_name,
                    config_dir,
                    owned_containers,
                )
                outer_result = _run_docker(
                    ["start", "--attach", outer_container],
                    config_dir=config_dir,
                    timeout=_OUTER_RUNTIME_SECONDS,
                )
                if outer_result.stderr:
                    raise PriorEffectiveOuterUnavailable(
                        "prior-effective outer runtime emitted unexpected stderr"
                    )
                _decode_outer_result(outer_result.returncode, outer_result.stdout)
                result = (outer_result.returncode, outer_result.stdout)
            except (
                OSError,
                ProtectedJudgeUnavailable,
                PriorEffectiveOuterUnavailable,
                RecursionError,
                SchemaError,
                TypeError,
                ValueError,
            ) as exc:
                primary_error = str(exc)
            finally:
                cleanup_issues: list[str] = []
                for container_name in reversed(owned_containers):
                    issue = _remove_container(container_name, config_dir)
                    if issue is not None:
                        cleanup_issues.append(issue)
                for volume_name in reversed(owned_volumes):
                    issue = _remove_volume(volume_name, config_dir)
                    if issue is not None:
                        cleanup_issues.append(issue)
                if cleanup_issues:
                    primary_error = "; ".join(
                        [item for item in (primary_error, *cleanup_issues) if item]
                    )
    except (
        OSError,
        ProtectedJudgeUnavailable,
        PriorEffectiveOuterUnavailable,
        RecursionError,
        SchemaError,
        TypeError,
        ValueError,
    ) as exc:
        return _operational_error(str(exc))

    if primary_error is not None:
        return _operational_error(primary_error)
    if result is None:
        return _operational_error("prior-effective outer runtime produced no result")
    return result
