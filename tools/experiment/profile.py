from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

PROFILE_SCHEMA = "gnostoa-experiment-runner-profile/v1"
VALIDATION_SCHEMA = "gnostoa-experiment-runner-validation/v1"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_IMMUTABLE_IMAGE_RE = re.compile(r"^(?:sha256:[a-f0-9]{64}|.+@sha256:[a-f0-9]{64})$")


class RunnerError(RuntimeError):
    """Raised when a runner operation cannot satisfy its declared contract."""


def absolute_lexical(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute() or ".." in path.parts:
        raise RunnerError(f"unsafe-path:{path_text}")
    return Path(os.path.abspath(path_text))


def path_has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                return True
        except OSError:
            return True
    return False


def is_same_or_parent(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def load_profile(path: Path) -> dict[str, object]:
    try:
        import yaml
    except ImportError as exc:
        raise RunnerError(
            "PyYAML is required to load experiment-runner profiles"
        ) from exc
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RunnerError(f"cannot-load-profile:{exc}") from exc
    if not isinstance(raw, dict):
        raise RunnerError("profile-must-be-a-mapping")
    return cast(dict[str, object], raw)


def string_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RunnerError(f"{key}-must-be-a-string-list")
    return cast(list[str], value)


def required_string(profile: Mapping[str, object], key: str) -> str:
    value = profile.get(key)
    if not isinstance(value, str) or not value:
        raise RunnerError(f"{key}-must-be-a-nonempty-string")
    return value


def split_target(target: str) -> tuple[str, int]:
    host, separator, port_text = target.rpartition(":")
    if not separator or not host or ":" in host:
        raise RunnerError(f"invalid-target:{target}")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RunnerError(f"invalid-target:{target}") from exc
    if port < 1 or port > 65535:
        raise RunnerError(f"invalid-target:{target}")
    return host, port


def validate_input_identities(values: Sequence[str]) -> list[str]:
    reasons: list[str] = []
    identifiers: set[str] = set()
    for value in values:
        identifier, separator, digest = value.partition("=")
        if (
            not separator
            or not identifier
            or identifier in identifiers
            or not _SHA256_RE.fullmatch(digest)
        ):
            reasons.append("invalid-or-duplicate-input-identity")
            continue
        identifiers.add(identifier)
    return reasons


def validate_executor(profile: Mapping[str, object]) -> list[str]:
    executor = profile.get("executor")
    if not isinstance(executor, dict):
        return ["executor-must-be-a-mapping"]
    mapping = cast(dict[str, object], executor)
    reasons: list[str] = []
    for key in ("id", "version"):
        value = mapping.get(key)
        if not isinstance(value, str) or not value:
            reasons.append(f"executor-{key}-must-be-a-nonempty-string")
    config_sha256 = mapping.get("config_sha256")
    if not isinstance(config_sha256, str) or not _SHA256_RE.fullmatch(config_sha256):
        reasons.append("executor-config-sha256-invalid")
    for key in ("model", "small_model"):
        value = mapping.get(key)
        if value is not None and (not isinstance(value, str) or not value):
            reasons.append(f"executor-{key}-invalid")
    return reasons


def validate_profile_data(profile: Mapping[str, object], *, for_run: bool) -> list[str]:
    reasons: list[str] = []
    if profile.get("schema") != PROFILE_SCHEMA:
        reasons.append("unsupported-profile-schema")

    try:
        read_roots = string_list(profile.get("read_only_roots", []), "read_only_roots")
        temporary_roots = string_list(
            profile.get("temporary_roots", []), "temporary_roots"
        )
        excluded_roots = string_list(
            profile.get("excluded_roots", []), "excluded_roots"
        )
        environment_allowlist = string_list(
            profile.get("environment_allowlist", []), "environment_allowlist"
        )
        credential_environment = string_list(
            profile.get("credential_environment", []), "credential_environment"
        )
        input_identities = string_list(
            profile.get("input_identities", []), "input_identities"
        )
        project_text = required_string(profile, "project_root")
        evidence_text = required_string(profile, "evidence_root")
    except RunnerError as exc:
        reasons.append(str(exc))
        return sorted(set(reasons))

    all_named: list[tuple[str, str]] = [
        *(("read_only_root", value) for value in read_roots),
        ("project_root", project_text),
        ("evidence_root", evidence_text),
        *(("temporary_root", value) for value in temporary_roots),
        *(("excluded_root", value) for value in excluded_roots),
    ]
    mounted_kinds = {
        "read_only_root",
        "project_root",
        "evidence_root",
        "temporary_root",
    }
    resolved: dict[str, list[Path]] = {}
    for kind, value in all_named:
        if kind in mounted_kinds and "," in value:
            reasons.append("mount-source-path-contains-comma")
        try:
            lexical = absolute_lexical(value)
        except RunnerError:
            reasons.append("path-must-be-absolute-without-traversal")
            continue
        if kind == "read_only_root" and lexical == Path("/"):
            reasons.append("broad-read-root-forbidden")
        if path_has_symlink_component(lexical):
            reasons.append("resolved-root-outside-admitted-surface")
            continue
        try:
            real = lexical.resolve(strict=True)
        except OSError:
            reasons.append(f"{kind}-missing")
            continue
        if real != lexical:
            reasons.append("resolved-root-outside-admitted-surface")
            continue
        resolved.setdefault(kind, []).append(real)

    writable = [
        *resolved.get("project_root", []),
        *resolved.get("evidence_root", []),
        *resolved.get("temporary_root", []),
    ]
    for read_only in resolved.get("read_only_root", []):
        for writable_root in writable:
            if is_same_or_parent(read_only, writable_root) or is_same_or_parent(
                writable_root, read_only
            ):
                reasons.append("read-only-root-overlaps-writable-surface")
    for excluded in resolved.get("excluded_root", []):
        for root in writable + resolved.get("read_only_root", []):
            if is_same_or_parent(excluded, root) or is_same_or_parent(root, excluded):
                reasons.append("excluded-root-overlaps-admitted-surface")

    if len(set(environment_allowlist)) != len(environment_allowlist):
        reasons.append("duplicate-environment-allowlist-entry")
    if len(set(credential_environment)) != len(credential_environment):
        reasons.append("duplicate-credential-environment-entry")
    if set(environment_allowlist) & set(credential_environment):
        reasons.append("credential-environment-must-be-separate")
    for name in [*environment_allowlist, *credential_environment]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            reasons.append("invalid-environment-name")

    reasons.extend(validate_input_identities(input_identities))

    network = profile.get("network")
    if not isinstance(network, dict):
        reasons.append("network-must-be-a-mapping")
    else:
        network_mapping = cast(dict[str, object], network)
        mode = network_mapping.get("mode")
        allow = network_mapping.get("allow", [])
        if mode not in {"none", "restricted"}:
            reasons.append("unsupported-network-mode")
        if not isinstance(allow, list) or not all(
            isinstance(item, str) for item in allow
        ):
            reasons.append("network-allow-must-be-a-string-list")
        elif mode == "none" and allow:
            reasons.append("network-none-must-have-empty-allowlist")
        elif mode == "restricted":
            for target in cast(list[str], allow):
                try:
                    split_target(target)
                except RunnerError:
                    reasons.append("invalid-network-allow-target")

    archive_limit = profile.get("archive_limit_bytes")
    if archive_limit is not None and (
        not isinstance(archive_limit, int)
        or isinstance(archive_limit, bool)
        or archive_limit <= 0
    ):
        reasons.append("archive-limit-must-be-positive-integer")

    if for_run:
        timeout_seconds = profile.get("timeout_seconds")
        if (
            not isinstance(timeout_seconds, int)
            or isinstance(timeout_seconds, bool)
            or timeout_seconds <= 0
        ):
            reasons.append("run-timeout-seconds-required")
        if not input_identities:
            reasons.append("input-identities-required-for-run")
        reasons.extend(validate_executor(profile))
        runtime = profile.get("runtime")
        if not isinstance(runtime, dict):
            reasons.append("runtime-must-be-a-mapping")
        else:
            runtime_mapping = cast(dict[str, object], runtime)
            image = runtime_mapping.get("image")
            if not isinstance(image, str) or not _IMMUTABLE_IMAGE_RE.fullmatch(image):
                reasons.append("runtime-image-must-be-immutable-digest")
            relay_image = runtime_mapping.get("relay_image")
            if (
                isinstance(network, dict)
                and cast(dict[str, object], network).get("mode") == "restricted"
                and (
                    not isinstance(relay_image, str)
                    or not _IMMUTABLE_IMAGE_RE.fullmatch(relay_image)
                )
            ):
                reasons.append("relay-image-must-be-immutable-digest")
    return sorted(set(reasons))


def profile_runtime(profile: Mapping[str, object]) -> tuple[str, str | None]:
    runtime = profile.get("runtime")
    if not isinstance(runtime, dict):
        raise RunnerError("runtime-must-be-a-mapping")
    runtime_mapping = cast(dict[str, object], runtime)
    image = runtime_mapping.get("image")
    relay_image = runtime_mapping.get("relay_image")
    if not isinstance(image, str):
        raise RunnerError("runtime-image-missing")
    if relay_image is not None and not isinstance(relay_image, str):
        raise RunnerError("relay-image-invalid")
    return image, relay_image


def profile_network(profile: Mapping[str, object]) -> tuple[str, list[str]]:
    network = profile.get("network")
    if not isinstance(network, dict):
        raise RunnerError("network-must-be-a-mapping")
    network_mapping = cast(dict[str, object], network)
    mode = network_mapping.get("mode")
    allow = network_mapping.get("allow", [])
    if not isinstance(mode, str):
        raise RunnerError("network-mode-invalid")
    return mode, string_list(allow, "network.allow")


def profile_paths(
    profile: Mapping[str, object],
) -> tuple[list[str], str, str, list[str], list[str]]:
    return (
        string_list(profile.get("read_only_roots", []), "read_only_roots"),
        required_string(profile, "project_root"),
        required_string(profile, "evidence_root"),
        string_list(profile.get("temporary_roots", []), "temporary_roots"),
        string_list(profile.get("excluded_roots", []), "excluded_roots"),
    )


def profile_timeout_seconds(profile: Mapping[str, object]) -> int:
    value = profile.get("timeout_seconds")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise RunnerError("run-timeout-seconds-required")
    return value


def clean_environment_args(
    profile: Mapping[str, object],
) -> tuple[list[str], list[str]]:
    allowed = string_list(
        profile.get("environment_allowlist", []), "environment_allowlist"
    )
    credentials = string_list(
        profile.get("credential_environment", []), "credential_environment"
    )
    args: list[str] = []
    admitted_names: list[str] = []
    for name in [*allowed, *credentials]:
        value = os.environ.get(name)
        if value is None:
            if name in credentials:
                raise RunnerError(f"required-credential-environment-missing:{name}")
            continue
        args.extend(["--env", name])
        admitted_names.append(name)
    return args, admitted_names


def executor_provenance(profile: Mapping[str, object]) -> dict[str, object]:
    executor = profile.get("executor")
    if not isinstance(executor, dict):
        raise RunnerError("executor-must-be-a-mapping")
    return dict(cast(dict[str, object], executor))
