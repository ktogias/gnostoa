from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import secrets
import stat
import subprocess
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any

from . import (
    adoption_assurance,
    build_context_pack,
    check_change_policy,
    check_ci_policy,
    validate_bundle,
)
from .check_runtime_lock import (
    evaluate_runtime_lock,
    public_surface_digest,
)
from .knowledge_common import KnowledgeFormatError, load_yaml
from .repository_scope import SOURCE_MANIFEST, RepositoryScopeError, candidate_paths

RESULT_SCHEMA = adoption_assurance.RESULT_SCHEMA
OBSERVATION_SCHEMA = "gnostoa-project-runtime-observation/v1"
MAX_OBSERVATION_BYTES = 65_536
MAX_TEXT = 512
MAX_VERSION = 256
MAX_IDENTITIES = 16
MAX_DISTRIBUTION_FILES = 1_024
MAX_DISTRIBUTION_BYTES = 64 * 1024 * 1024
BUNDLE_COMMITMENT_SCHEMA = "gnostoa-adoption-evidence-bundle/v1"

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BINDING_RE = re.compile(r"^[0-9a-f]{64}$")
SUITE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PLATFORM_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
OCI_MEDIA_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}

ToolMain = Callable[[list[str] | None], int]


class AdoptionCheckError(RuntimeError):
    """Base class for bounded adoption-check failures."""


class UnsafeInvocation(AdoptionCheckError):
    """The caller did not establish a safe invocation boundary."""


class BlockedPrerequisite(AdoptionCheckError):
    """A material prerequisite is unavailable or cannot be observed."""


class ObservationBlocked(AdoptionCheckError):
    """A project runtime observation is missing or mechanically incomplete."""


class ObservationConflict(AdoptionCheckError):
    """A complete actual runtime conflicts with a mandatory declaration."""


@dataclass(frozen=True)
class PathSet:
    project_root: Path
    documentation_root: Path
    toolkit_source: Path
    lock: Path
    change_policy: Path
    ci_policy: Path
    verification: Path
    profile: Path
    bundle: Path
    output: Path
    oci_digest_evidence: Path | None
    overrides: dict[str, str]


@dataclass(frozen=True)
class BoundOutputParent:
    path: Path
    descriptor: int
    device: int
    inode: int


@dataclass(frozen=True)
class RuntimeObservation:
    value: dict[str, Any]
    route_kind: str
    manifest_digest: str | None
    manifest_media_type: str | None


@dataclass(frozen=True)
class EvidenceArtifact:
    path: str
    content: bytes
    byte_length: int
    digest: str
    origin: str

    def metadata(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.digest,
            "bytes": self.byte_length,
            "origin": self.origin,
        }


@dataclass
class EvidenceWriter:
    components: list[dict[str, Any]]
    _artifacts: dict[str, EvidenceArtifact] = field(default_factory=dict, init=False)

    def write_bytes(
        self,
        relative: str,
        content: bytes,
        *,
        origin: str,
    ) -> dict[str, Any]:
        path = _normalize_artifact_path(relative)
        if path in self._artifacts:
            raise UnsafeInvocation(
                f"cannot retain evidence artifact without replacement: {path}"
            )
        if (
            not origin
            or len(origin) > 256
            or any(ord(character) < 32 or ord(character) == 127 for character in origin)
        ):
            raise UnsafeInvocation(f"invalid evidence artifact origin for {path}")
        immutable_content = bytes(content)
        artifact = EvidenceArtifact(
            path=path,
            content=immutable_content,
            byte_length=len(immutable_content),
            digest=_sha256(immutable_content),
            origin=origin,
        )
        self._artifacts[path] = artifact
        return artifact.metadata()

    def write_text(
        self,
        relative: str,
        content: str,
        *,
        origin: str,
    ) -> dict[str, Any]:
        return self.write_bytes(relative, content.encode("utf-8"), origin=origin)

    def artifacts(self) -> tuple[EvidenceArtifact, ...]:
        return tuple(self._artifacts[path] for path in sorted(self._artifacts))

    def manifest(self) -> list[dict[str, Any]]:
        return [artifact.metadata() for artifact in self.artifacts()]

    def component(
        self,
        name: str,
        command: list[str],
        exit_code: int | None,
        result: str,
        stdout: bytes,
        stderr: bytes,
        *,
        detail: str | None = None,
    ) -> dict[str, Any]:
        stdout_path = f"components/{name}.stdout"
        stderr_path = f"components/{name}.stderr"
        origin = f"gnostoa-component:{name}"
        self.write_bytes(stdout_path, stdout, origin=origin)
        self.write_bytes(stderr_path, stderr, origin=origin)
        record: dict[str, Any] = {
            "name": name,
            "command": command,
            "exit_code": exit_code,
            "result": result,
            "stdout": stdout_path,
            "stderr": stderr_path,
        }
        if detail:
            record["detail"] = detail
        self.components.append(record)
        return record


def _sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _normalize_artifact_path(relative: str) -> str:
    if not isinstance(relative, str) or not relative or len(relative) > 1024:
        raise UnsafeInvocation(f"unsafe evidence artifact path: {relative!r}")
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or any(
        part in {"", ".", ".."} for part in candidate.parts
    ):
        raise UnsafeInvocation(f"unsafe evidence artifact path: {relative}")
    if any("\\" in part or "\x00" in part for part in candidate.parts):
        raise UnsafeInvocation(f"unsafe evidence artifact path: {relative}")
    return candidate.as_posix()


def _has_control(value: str) -> bool:
    return any(
        ord(character) < 32 or 127 <= ord(character) <= 159 for character in value
    )


def _bounded_string(
    value: object,
    label: str,
    *,
    maximum: int = MAX_TEXT,
) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ObservationBlocked(
            f"{label} must contain 1--{maximum} Unicode scalar values"
        )
    if _has_control(value) or any(
        0xD800 <= ord(character) <= 0xDFFF for character in value
    ):
        raise ObservationBlocked(f"{label} contains a control or non-scalar character")
    return value


def _exact_members(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObservationBlocked(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        details: list[str] = []
        if unknown:
            details.append(f"unknown members: {', '.join(unknown)}")
        if missing:
            details.append(f"missing members: {', '.join(missing)}")
        raise ObservationBlocked(f"{label} has invalid members ({'; '.join(details)})")
    return value


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ObservationBlocked(f"duplicate JSON member {key!r}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ObservationBlocked(f"unsupported JSON constant {value!r}")


def _decode_observation(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_OBSERVATION_BYTES:
        raise ObservationBlocked(
            f"runtime observation exceeds {MAX_OBSERVATION_BYTES} bytes"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ObservationBlocked("runtime observation is not UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_json_constant,
        )
    except ObservationBlocked:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ObservationBlocked(
            f"runtime observation is not bounded JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ObservationBlocked("runtime observation must be one JSON object")
    return value


def _validate_native_subject(subject: str, label: str) -> None:
    path = Path(subject)
    if not path.is_absolute() or os.path.normpath(subject) != subject:
        raise ObservationBlocked(f"{label} must be a normalized absolute path")


def _validate_lock_subject(subject: str, label: str) -> None:
    path = PurePosixPath(subject)
    if path.is_absolute() or str(path) != subject:
        raise ObservationBlocked(
            f"{label} must be a normalized project-relative POSIX path"
        )
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ObservationBlocked(f"{label} contains an unsafe path component")


def _validate_container_subject(subject: str, label: str) -> None:
    if len(subject) > 256 or any(
        ord(character) < 32 or ord(character) > 126 for character in subject
    ):
        raise ObservationBlocked(f"{label} must be 1--256 printable ASCII characters")


def _validate_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or HASH_RE.fullmatch(value) is None:
        raise ObservationBlocked(
            f"{label} must be sha256:<64 lowercase hexadecimal characters>"
        )
    return value


def validate_runtime_observation(
    raw: bytes,
    *,
    suite: str,
    invocation_binding: str,
    origin_entry: str,
) -> RuntimeObservation:
    """Validate Decision 0048's closed project-reported v1 observation."""

    value = _exact_members(
        _decode_observation(raw),
        {
            "schema",
            "suite",
            "invocation_binding",
            "route_kind",
            "runtime_identity",
            "origin",
        },
        "runtime observation",
    )
    if value["schema"] != OBSERVATION_SCHEMA:
        raise ObservationBlocked("runtime observation has the wrong schema")
    observed_suite = value["suite"]
    if (
        not isinstance(observed_suite, str)
        or SUITE_RE.fullmatch(observed_suite) is None
    ):
        raise ObservationBlocked("runtime observation suite is invalid")
    if observed_suite != suite:
        raise ObservationBlocked(
            f"runtime observation suite {observed_suite!r} does not match {suite!r}"
        )
    binding = value["invocation_binding"]
    if not isinstance(binding, str) or BINDING_RE.fullmatch(binding) is None:
        raise ObservationBlocked("runtime observation invocation binding is invalid")
    if binding != invocation_binding:
        raise ObservationBlocked("runtime observation has the wrong invocation binding")

    route_kind = value["route_kind"]
    if route_kind not in {"native", "container", "service", "composite"}:
        raise ObservationBlocked("runtime observation has an unknown route kind")

    origin = _exact_members(value["origin"], {"kind", "entry"}, "origin")
    if origin["kind"] != "project-adapter":
        raise ObservationBlocked("runtime observation origin is not project-adapter")
    entry = _bounded_string(origin["entry"], "origin.entry")
    if entry != origin_entry:
        raise ObservationBlocked(
            f"runtime observation origin {entry!r} does not match {origin_entry!r}"
        )

    identities = value["runtime_identity"]
    if not isinstance(identities, list) or not 1 <= len(identities) <= MAX_IDENTITIES:
        raise ObservationBlocked(
            f"runtime_identity must contain 1--{MAX_IDENTITIES} items"
        )

    seen: set[tuple[str, str, str]] = set()
    kinds: list[tuple[str, str]] = []
    manifest_digest: str | None = None
    manifest_media_type: str | None = None
    for index, raw_identity in enumerate(identities):
        label = f"runtime_identity[{index}]"
        identity = _exact_members(
            raw_identity,
            {"kind", "role", "subject", "value", "measurement"},
            label,
        )
        kind = _bounded_string(identity["kind"], f"{label}.kind")
        role = _bounded_string(identity["role"], f"{label}.role")
        subject = _bounded_string(identity["subject"], f"{label}.subject")
        key = (kind, role, subject)
        if key in seen:
            raise ObservationBlocked(f"duplicate runtime identity {key!r}")
        seen.add(key)
        kinds.append((kind, role))

        measurement = _exact_members(
            identity["measurement"], {"method"}, f"{label}.measurement"
        )
        method = _bounded_string(measurement["method"], f"{label}.measurement.method")
        identity_value = identity["value"]

        if (kind, role) == ("native-executable", "suite-runtime"):
            _validate_native_subject(subject, f"{label}.subject")
            mapped = _exact_members(
                identity_value, {"sha256", "version"}, f"{label}.value"
            )
            _validate_hash(mapped["sha256"], f"{label}.value.sha256")
            _bounded_string(
                mapped["version"], f"{label}.value.version", maximum=MAX_VERSION
            )
            if method != "executable-sha256-and-version-v1":
                raise ObservationBlocked(f"{label} has an invalid measurement method")
        elif (kind, role) == ("dependency-lock", "suite-lock"):
            _validate_lock_subject(subject, f"{label}.subject")
            mapped = _exact_members(identity_value, {"sha256"}, f"{label}.value")
            _validate_hash(mapped["sha256"], f"{label}.value.sha256")
            if method != "file-sha256-v1":
                raise ObservationBlocked(f"{label} has an invalid measurement method")
        elif (kind, role) == ("oci-platform-manifest", "suite-runtime"):
            _validate_container_subject(subject, f"{label}.subject")
            mapped = _exact_members(
                identity_value,
                {
                    "manifest_digest",
                    "manifest_media_type",
                    "configuration_digest",
                    "platform",
                },
                f"{label}.value",
            )
            manifest_digest = _validate_hash(
                mapped["manifest_digest"], f"{label}.value.manifest_digest"
            )
            _validate_hash(
                mapped["configuration_digest"],
                f"{label}.value.configuration_digest",
            )
            manifest_media_type = mapped["manifest_media_type"]
            if manifest_media_type not in OCI_MEDIA_TYPES:
                raise ObservationBlocked(
                    f"{label}.value.manifest_media_type is not a platform manifest"
                )
            platform = _exact_members(
                mapped["platform"], {"os", "architecture"}, f"{label}.value.platform"
            )
            for member in ("os", "architecture"):
                item = platform[member]
                if not isinstance(item, str) or PLATFORM_RE.fullmatch(item) is None:
                    raise ObservationBlocked(
                        f"{label}.value.platform.{member} is invalid"
                    )
            if method != "entered-container-platform-manifest-config-v1":
                raise ObservationBlocked(f"{label} has an invalid measurement method")
        else:
            raise ObservationBlocked(f"{label} uses an unknown identity profile")

    if route_kind == "native":
        if ("native-executable", "suite-runtime") not in kinds:
            raise ObservationBlocked(
                "native observation has no suite-runtime executable"
            )
        if ("dependency-lock", "suite-lock") not in kinds:
            raise ObservationBlocked(
                "native observation has no applicable dependency lock"
            )
        if any(kind == "oci-platform-manifest" for kind, _ in kinds):
            raise ObservationBlocked("native observation contains a container identity")
    elif route_kind == "container":
        if kinds != [("oci-platform-manifest", "suite-runtime")]:
            raise ObservationBlocked(
                "container observation must contain exactly one platform-manifest identity"
            )
    else:
        raise ObservationBlocked(f"{route_kind} observations are unsupported in v1")

    return RuntimeObservation(value, route_kind, manifest_digest, manifest_media_type)


def _run_bytes(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        timeout=timeout,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )


def _git(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    return _run_bytes(
        ["git", "-c", f"safe.directory={root}", "-C", str(root), *arguments],
        cwd=root,
    )


def _git_required(root: Path, arguments: list[str], label: str) -> bytes:
    try:
        result = _git(root, arguments)
    except OSError as exc:
        raise BlockedPrerequisite(f"cannot execute Git for {label}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise BlockedPrerequisite(detail or f"cannot read Git {label}")
    return result.stdout


def _git_text(root: Path, arguments: list[str], label: str) -> str:
    return (
        _git_required(root, arguments, label).decode("utf-8", errors="replace").strip()
    )


def _git_snapshot(root: Path) -> dict[str, Any]:
    status = _git_required(
        root,
        ["status", "--porcelain=v2", "--branch", "--untracked-files=all"],
        "status",
    )
    patch = _git_required(
        root,
        ["diff", "--cached", "--binary", "--full-index", "--no-ext-diff"],
        "staged candidate",
    )
    ignored = _git_required(
        root,
        ["ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
        "ignored project state",
    )
    staged_index = _git_required(
        root,
        ["ls-files", "--stage", "-z"],
        "staged index identity",
    )
    object_format = _git_text(
        root,
        ["rev-parse", "--show-object-format"],
        "repository object format",
    )
    gitlinks: list[dict[str, str]] = []
    for raw_entry in staged_index.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, raw_path = raw_entry.partition(b"\t")
        try:
            fields = metadata.decode("ascii", errors="strict").split()
        except UnicodeDecodeError as exc:
            raise BlockedPrerequisite(
                "staged index metadata is not canonical ASCII"
            ) from exc
        if (
            separator
            and len(fields) == 3
            and fields[0] == "160000"
            and fields[2] == "0"
        ):
            try:
                path = raw_path.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise BlockedPrerequisite(
                    "staged gitlink path is not canonical UTF-8"
                ) from exc
            gitlinks.append(
                {
                    "path": path,
                    "commit": fields[1],
                }
            )
    return {
        "repository_object_format": object_format,
        "head": _git_text(root, ["rev-parse", "HEAD"], "HEAD"),
        "tree": _git_text(root, ["rev-parse", "HEAD^{tree}"], "HEAD tree"),
        "status": status.decode("utf-8", errors="replace"),
        "status_sha256": _sha256(status),
        "ignored_paths": sorted(
            item.decode("utf-8", errors="replace")
            for item in ignored.split(b"\0")
            if item
        ),
        "ignored_paths_sha256": _sha256(ignored),
        "staged_index_sha256": _sha256(staged_index),
        "staged_index_bytes": len(staged_index),
        "gitlinks": sorted(gitlinks, key=lambda item: item["path"]),
        "candidate_patch_sha256": _sha256(patch),
        "candidate_patch_bytes": len(patch),
        "_patch": patch,
    }


def _relative_within(root: Path, path: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise UnsafeInvocation(f"{label} is outside project root: {path}") from exc
    return relative


def _resolve_project_path(root: Path, supplied: Path, label: str) -> Path:
    candidate = supplied if supplied.is_absolute() else root / supplied
    resolved = candidate.resolve()
    _relative_within(root, resolved, label)
    return resolved


def _path_from_override(
    root: Path,
    supplied: Path | None,
    default: Path,
    label: str,
    overrides: dict[str, str],
) -> Path:
    if supplied is None:
        return _resolve_project_path(root, default, label)
    resolved = _resolve_project_path(root, supplied, label)
    overrides[label] = str(resolved)
    return resolved


def _derive_paths(args: argparse.Namespace) -> PathSet:
    project_root = args.project_root.resolve()
    if not project_root.is_dir():
        raise UnsafeInvocation(f"project root is not a directory: {project_root}")

    output = args.output_dir
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    else:
        output = output.resolve()
    try:
        output.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise UnsafeInvocation("output directory must be outside the project root")
    if not output.parent.is_dir():
        raise UnsafeInvocation(f"output parent does not exist: {output.parent}")
    try:
        output.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise UnsafeInvocation(f"cannot inspect output directory: {exc}") from exc
    else:
        raise UnsafeInvocation(f"output directory already exists: {output}")

    overrides: dict[str, str] = {}
    lock = _path_from_override(
        project_root,
        args.lock,
        Path(".knowledge/kit.lock.yaml"),
        "lock",
        overrides,
    )
    try:
        lock_value = load_yaml(lock)
    except KnowledgeFormatError as exc:
        raise UnsafeInvocation(str(exc)) from exc
    toolkit = lock_value.get("toolkit")
    if not isinstance(toolkit, dict):
        raise UnsafeInvocation("toolkit lock has no toolkit mapping")
    source_value = toolkit.get("source")
    profile_value = toolkit.get("profile")
    if not isinstance(source_value, str) or not source_value:
        raise UnsafeInvocation("toolkit.source is not a non-empty path")
    if not isinstance(profile_value, str) or not profile_value:
        raise UnsafeInvocation("toolkit.profile is not a non-empty path")
    toolkit_source = _resolve_project_path(
        project_root, Path(source_value), "toolkit source"
    )
    profile = _path_from_override(
        project_root,
        args.profile,
        Path(profile_value),
        "profile",
        overrides,
    )
    verification = _path_from_override(
        project_root,
        args.verification,
        Path(".knowledge/verification.yaml"),
        "verification",
        overrides,
    )
    try:
        verification_value = load_yaml(verification)
    except KnowledgeFormatError as exc:
        raise UnsafeInvocation(str(exc)) from exc
    declared_policy = verification_value.get("policy")
    if not isinstance(declared_policy, str) or not declared_policy:
        raise UnsafeInvocation("verification.policy is not a non-empty path")
    ci_default = verification.parent.relative_to(project_root) / declared_policy

    documentation_root = args.documentation_root
    if documentation_root is None:
        documentation = toolkit_source
    else:
        documentation = documentation_root.resolve()
        overrides["documentation-root"] = str(documentation)
    if not documentation.is_dir():
        raise UnsafeInvocation(
            f"documentation root is not a directory: {documentation}"
        )

    oci_evidence = args.oci_digest_evidence
    if oci_evidence is not None:
        oci_evidence = oci_evidence.resolve()
        overrides["oci-digest-evidence"] = str(oci_evidence)

    return PathSet(
        project_root=project_root,
        documentation_root=documentation,
        toolkit_source=toolkit_source,
        lock=lock,
        change_policy=_path_from_override(
            project_root,
            args.change_policy,
            Path(".knowledge/change-control.yaml"),
            "change-policy",
            overrides,
        ),
        ci_policy=_path_from_override(
            project_root,
            args.ci_policy,
            ci_default,
            "ci-policy",
            overrides,
        ),
        verification=verification,
        profile=profile,
        bundle=_path_from_override(
            project_root,
            args.bundle,
            Path("knowledge"),
            "bundle",
            overrides,
        ),
        output=output,
        oci_digest_evidence=oci_evidence,
        overrides=overrides,
    )


def _execution_root() -> Path:
    """Return the source root from which this running module was imported."""

    return Path(__file__).resolve().parent.parent


def _marker_exists(path: Path) -> bool:
    try:
        path.lstat()
    except OSError:
        return False
    return True


def _complete_public_source_root(root: Path) -> bool:
    return all(
        _marker_exists(root / marker)
        for marker in (
            "pyproject.toml",
            "core/profile.yaml",
            "schemas/profile.schema.json",
        )
    )


def _package_paths(root: Path, *, declared: bool) -> list[Path]:
    if declared:
        try:
            candidates = candidate_paths(root)
        except RepositoryScopeError as exc:
            raise BlockedPrerequisite(str(exc)) from exc
    else:
        package = root / "tools"
        if not package.is_dir():
            raise BlockedPrerequisite(
                f"installed Gnostoa tools package is unavailable under {root}"
            )
        candidates = [
            path.relative_to(root) for path in package.rglob("*") if path.is_file()
        ]
    selected = sorted(
        {
            path
            for path in candidates
            if path.parts
            and path.parts[0] == "tools"
            and "__pycache__" not in path.parts
            and path.suffix.casefold() not in {".pyc", ".pyo"}
        },
        key=lambda path: path.as_posix(),
    )
    if len(selected) > MAX_DISTRIBUTION_FILES:
        raise BlockedPrerequisite(
            "Gnostoa package membership exceeds the installed-runtime bound"
        )
    return selected


def _package_payload(
    root: Path,
    paths: list[Path],
    *,
    label: str,
) -> tuple[dict[Path, bytes], str, str]:
    payload: dict[Path, bytes] = {}
    membership = hashlib.sha256()
    content = hashlib.sha256()
    total = 0
    for relative in paths:
        encoded = relative.as_posix().encode("utf-8")
        try:
            value = _read_regular_bounded(
                root / relative,
                8 * 1024 * 1024,
                f"{label} {relative.as_posix()}",
            )
        except ObservationBlocked as exc:
            raise BlockedPrerequisite(str(exc)) from exc
        payload[relative] = value
        total += len(value)
        if total > MAX_DISTRIBUTION_BYTES:
            raise BlockedPrerequisite(f"{label} exceeds the installed-runtime bound")
        membership.update(len(encoded).to_bytes(8, "big"))
        membership.update(encoded)
        content.update(len(encoded).to_bytes(8, "big"))
        content.update(encoded)
        content.update(len(value).to_bytes(8, "big"))
        content.update(value)
    if not payload:
        raise BlockedPrerequisite(f"{label} contains no Gnostoa package files")
    return payload, f"sha256:{membership.hexdigest()}", f"sha256:{content.hexdigest()}"


def _installed_distribution_identity(
    root: Path,
    source_root: Path,
    source_identity: dict[str, Any],
) -> dict[str, Any]:
    resolved = root.resolve()
    source_resolved = source_root.resolve()
    source_declared = _marker_exists(source_resolved / ".git") or _marker_exists(
        source_resolved / SOURCE_MANIFEST
    )
    source_paths = _package_paths(source_resolved, declared=source_declared)
    runtime_paths = _package_paths(resolved, declared=False)
    source_payload, source_membership, source_digest = _package_payload(
        source_resolved,
        source_paths,
        label="pinned toolkit package file",
    )
    runtime_payload, runtime_membership, runtime_digest = _package_payload(
        resolved,
        runtime_paths,
        label="installed Gnostoa package file",
    )
    source_set = set(source_payload)
    runtime_set = set(runtime_payload)
    missing = sorted(
        (path.as_posix() for path in source_set - runtime_set),
    )
    unexpected = sorted(
        (path.as_posix() for path in runtime_set - source_set),
    )
    changed = sorted(
        path.as_posix()
        for path in source_set & runtime_set
        if source_payload[path] != runtime_payload[path]
    )
    result = "PASS" if not (missing or unexpected or changed) else "FAIL"
    try:
        distribution_version = importlib.metadata.version("gnostoa")
    except importlib.metadata.PackageNotFoundError:
        distribution_version = "NOT OBSERVED"
    identity: dict[str, Any] = {
        "root": str(resolved),
        "authority": "installed-python-distribution",
        "revision": None,
        "tree": None,
        "distribution": {
            "name": "gnostoa",
            "version": distribution_version,
        },
        "source_binding": {
            "result": result,
            "method": "installed-package-pinned-source-byte-equality-v1",
            "membership": len(runtime_paths),
            "source_membership_sha256": source_membership,
            "runtime_membership_sha256": runtime_membership,
            "source_payload_sha256": source_digest,
            "runtime_payload_sha256": runtime_digest,
            "missing": missing,
            "unexpected": unexpected,
            "changed": changed,
        },
    }
    if result == "PASS":
        public_digest = source_identity.get("public_surface_digest")
        if not isinstance(public_digest, str):
            raise BlockedPrerequisite(
                "pinned toolkit public surface is unavailable for installed runtime binding"
            )
        identity["public_surface_digest"] = public_digest
        source_revision = source_identity.get("revision")
        if isinstance(source_revision, str):
            identity["revision"] = source_revision
            identity["revision_measurement"] = (
                "installed-package-pinned-source-byte-equality-v1"
            )
        else:
            revision = os.environ.get("KNOWLEDGE_KIT_REVISION", "")
            if revision not in {"", "development", "unknown"}:
                identity["revision"] = revision
                identity["revision_measurement"] = "running-runtime-metadata"
    return identity


def _source_identity(root: Path, *, running: bool = False) -> dict[str, Any]:
    resolved = root.resolve()
    identity: dict[str, Any] = {
        "root": str(resolved),
        "revision": None,
        "tree": None,
    }
    try:
        identity["public_surface_digest"] = public_surface_digest(resolved)
    except (KnowledgeFormatError, OSError) as exc:
        raise BlockedPrerequisite(
            f"cannot measure public surface at {resolved}: {exc}"
        ) from exc

    if _marker_exists(resolved / ".git"):
        identity["authority"] = "git"
        identity["revision"] = _git_text(
            resolved, ["rev-parse", "HEAD"], "source revision"
        )
        identity["tree"] = _git_text(
            resolved, ["rev-parse", "HEAD^{tree}"], "source tree"
        )
        try:
            paths = candidate_paths(resolved)
        except RepositoryScopeError as exc:
            raise BlockedPrerequisite(str(exc)) from exc
        encoded = b"\0".join(path.as_posix().encode("utf-8") for path in paths)
        identity["membership_sha256"] = _sha256(encoded)
        identity["membership"] = len(paths)
    elif _marker_exists(resolved / SOURCE_MANIFEST):
        identity["authority"] = "packaged-source-manifest"
        manifest = (resolved / SOURCE_MANIFEST).read_bytes()
        identity["membership_sha256"] = _sha256(manifest)
        identity["membership"] = len([item for item in manifest.split(b"\0") if item])
        if running:
            revision = os.environ.get("KNOWLEDGE_KIT_REVISION", "")
            if revision not in {"", "development", "unknown"}:
                identity["revision"] = revision
                identity["revision_measurement"] = "running-runtime-metadata"
    else:
        identity["authority"] = "metadata-free-vendored-source"
    return identity


def _execution_identity(
    root: Path,
    source_root: Path,
    source_identity: dict[str, Any],
) -> dict[str, Any]:
    if _complete_public_source_root(root):
        return _source_identity(root, running=True)
    return _installed_distribution_identity(root, source_root, source_identity)


def _call_tool(
    function: ToolMain,
    arguments: list[str],
) -> tuple[int, bytes, bytes]:
    stdout = StringIO()
    stderr = StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = function(arguments)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:  # pragma: no cover - retained as internal evidence
        code = 2
        print(f"ERROR: internal component error: {exc}", file=stderr)
    return code, stdout.getvalue().encode(), stderr.getvalue().encode()


def _tool_versions(project_root: Path) -> dict[str, Any]:
    python_path = Path(sys.executable).resolve()
    python_identity: dict[str, Any] = {
        "version": platform.python_version(),
        "executable": str(python_path),
    }
    try:
        python_identity["sha256"] = _sha256(python_path.read_bytes())
    except OSError as exc:
        python_identity["sha256"] = "NOT OBSERVED"
        python_identity["detail"] = str(exc)

    try:
        git = _git(project_root, ["--version"])
    except OSError:
        git_version = "NOT OBSERVED"
    else:
        git_version = (
            git.stdout.decode("utf-8", errors="replace").strip()
            if git.returncode == 0
            else "NOT OBSERVED"
        )
    try:
        package_version = importlib.metadata.version("gnostoa")
    except importlib.metadata.PackageNotFoundError:
        package_version = "NOT OBSERVED"
    return {
        "gnostoa_distribution": package_version,
        "python": python_identity,
        "git": git_version,
    }


def _component_result(exit_code: int) -> str:
    if exit_code == 0:
        return "PASS"
    if exit_code == 1:
        return "FAIL"
    return "ERROR"


def _runtime_component(
    paths: PathSet,
    runtime_identity: dict[str, Any],
    writer: EvidenceWriter,
) -> dict[str, Any]:
    stdout = StringIO()
    stderr = StringIO()
    try:
        revision = runtime_identity.get("revision")
        runtime_root = _execution_root()
        source_binding = runtime_identity.get("source_binding")
        if (
            runtime_identity.get("authority") == "installed-python-distribution"
            and isinstance(source_binding, dict)
            and source_binding.get("result") == "PASS"
        ):
            runtime_root = paths.toolkit_source
        evaluation = evaluate_runtime_lock(
            paths.lock,
            paths.project_root,
            revision if isinstance(revision, str) else "",
            "",
            runtime_root=runtime_root,
        )
        for issue in evaluation.declaration_issues:
            print(f"ERROR: {issue}", file=stdout)
        if evaluation.declaration_issues:
            code = 1
        else:
            code = 0
            print(
                "PASS: runtime-lock declaration and source binding are valid "
                f"({paths.lock})",
                file=stdout,
            )
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        code = 2
        print(f"ERROR: {exc}", file=stderr)
    return writer.component(
        "runtime-lock",
        ["knowledge", "check-runtime", "--lock", str(paths.lock)],
        code,
        _component_result(code),
        stdout.getvalue().encode(),
        stderr.getvalue().encode(),
    )


def _run_tool_component(
    writer: EvidenceWriter,
    name: str,
    command: list[str],
    function: ToolMain,
    arguments: list[str],
) -> dict[str, Any]:
    code, stdout, stderr = _call_tool(function, arguments)
    return writer.component(
        name,
        command,
        code,
        _component_result(code),
        stdout,
        stderr,
    )


def _index_lines(root: Path, relative: Path) -> list[str]:
    output = _git_required(
        root,
        ["ls-files", "--stage", "--", relative.as_posix()],
        f"index entry for {relative.as_posix()}",
    )
    return [
        line for line in output.decode("utf-8", errors="replace").splitlines() if line
    ]


def _tracked_file_state(root: Path, relative: Path) -> dict[str, Any]:
    lines = _index_lines(root, relative)
    if len(lines) != 1:
        raise AdoptionCheckError(
            f"required target is not represented once in the index: {relative}"
        )
    path = root / relative
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise AdoptionCheckError(f"required target is unreadable: {relative}") from exc
    if not stat.S_ISREG(mode):
        raise AdoptionCheckError(f"required target is not a regular file: {relative}")
    content = path.read_bytes()
    return {
        "path": relative.as_posix(),
        "index": lines[0],
        "worktree_sha256": _sha256(content),
        "bytes": len(content),
    }


def _git_representation(
    paths: PathSet,
    verification: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    root = paths.project_root
    problems: list[str] = []
    suites = verification.get("suites")
    if not isinstance(suites, dict):
        suites = {}

    required: set[Path] = {
        _relative_within(root, paths.lock, "lock"),
        _relative_within(root, paths.change_policy, "change policy"),
        _relative_within(root, paths.ci_policy, "CI policy"),
        _relative_within(root, paths.verification, "verification"),
        _relative_within(root, paths.profile, "profile"),
    }
    try:
        required.update(
            path.relative_to(root)
            for path in paths.bundle.rglob("*.md")
            if path.is_file()
        )
    except OSError as exc:
        problems.append(f"cannot inventory bundle files: {exc}")

    entry_paths: set[Path] = set()
    for suite in ("fast", "regression"):
        declared = suites.get(suite)
        if not isinstance(declared, dict):
            continue
        command = declared.get("command")
        if (
            not isinstance(command, list)
            or not command
            or not isinstance(command[0], str)
        ):
            continue
        entry = Path(command[0])
        if entry.is_absolute():
            problems.append(f"suites.{suite}.command entry is not project-relative")
            continue
        try:
            entry_paths.add(_relative_within(root, root / entry, f"{suite} entry"))
        except UnsafeInvocation as exc:
            problems.append(str(exc))
    required.update(entry_paths)
    if (root / "AGENTS.md").exists():
        required.add(Path("AGENTS.md"))

    target_states: list[dict[str, Any]] = []
    for relative in sorted(required, key=lambda item: item.as_posix()):
        try:
            target_states.append(_tracked_file_state(root, relative))
        except BlockedPrerequisite:
            raise
        except AdoptionCheckError as exc:
            problems.append(str(exc))

    source_relative = _relative_within(root, paths.toolkit_source, "toolkit source")
    source_entries = _index_lines(root, source_relative)
    submodule: dict[str, Any] | None = None
    if len(source_entries) == 1 and source_entries[0].startswith("160000 "):
        fields = source_entries[0].split(maxsplit=3)
        index_revision = fields[1] if len(fields) >= 2 else ""
        worktree_revision = _git_text(
            paths.toolkit_source,
            ["rev-parse", "HEAD"],
            "toolkit worktree revision",
        )
        submodule = {
            "path": source_relative.as_posix(),
            "index_mode": "160000",
            "index_revision": index_revision,
            "worktree_revision": worktree_revision,
            "equal": bool(index_revision and index_revision == worktree_revision),
        }
        if not submodule["equal"]:
            problems.append("staged toolkit gitlink differs from toolkit worktree HEAD")
        if (root / ".gitmodules").is_file():
            try:
                target_states.append(_tracked_file_state(root, Path(".gitmodules")))
            except BlockedPrerequisite:
                raise
            except AdoptionCheckError as exc:
                problems.append(str(exc))
    else:
        vendored = _git_required(
            root,
            ["ls-files", "--", f"{source_relative.as_posix()}/"],
            "vendored toolkit membership",
        )
        members = [item for item in vendored.splitlines() if item]
        if not members:
            problems.append("vendored toolkit source has no tracked members")

    try:
        changed = _git(
            root,
            [
                "diff",
                "--quiet",
                "--",
                *(
                    item.as_posix()
                    for item in sorted(required, key=lambda path: path.as_posix())
                ),
                source_relative.as_posix(),
            ],
        )
    except OSError as exc:
        raise BlockedPrerequisite(
            f"cannot execute Git for required adoption-target comparison: {exc}"
        ) from exc
    if changed.returncode == 1:
        problems.append("required adoption targets differ between index and worktree")
    elif changed.returncode != 0:
        detail = changed.stderr.decode("utf-8", errors="replace").strip()
        raise BlockedPrerequisite(
            detail or "cannot compare required adoption targets with the index"
        )

    try:
        before_agents = _git(root, ["rev-parse", "HEAD:AGENTS.md"])
        staged_agents = _git(root, ["rev-parse", ":AGENTS.md"])
    except OSError as exc:
        raise BlockedPrerequisite(
            f"cannot execute Git for AGENTS.md identity acquisition: {exc}"
        ) from exc
    agents = {
        "head_blob": (
            before_agents.stdout.decode().strip()
            if before_agents.returncode == 0
            else None
        ),
        "index_blob": (
            staged_agents.stdout.decode().strip()
            if staged_agents.returncode == 0
            else None
        ),
    }
    return {
        "required_targets": target_states,
        "agents": agents,
        "submodule": submodule,
        "toolkit_source_mode": "git-submodule" if submodule else "vendored",
    }, problems


def _read_regular_bounded(path: Path, maximum: int, label: str) -> bytes:
    """Bind validation and bounded reading to one no-follow file descriptor.

    The final descriptor cannot establish the producer's historical publication
    method; atomic no-replace publication remains a producer-side obligation.
    """

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ObservationBlocked(
            f"cannot safely read {label}: O_NOFOLLOW is unavailable"
        )
    flags = os.O_RDONLY | nofollow
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ObservationBlocked(
                f"{label} is not a regular non-symlink file"
            ) from exc
        raise ObservationBlocked(f"cannot read {label}: {exc}") from exc
    return _read_opened_regular(descriptor, maximum, label)


def _read_opened_regular(descriptor: int, maximum: int, label: str) -> bytes:
    """Validate, read and close one already-opened candidate regular file."""

    try:
        try:
            mode = os.fstat(descriptor).st_mode
            if not stat.S_ISREG(mode):
                raise ObservationBlocked(f"{label} is not a regular non-symlink file")
            remaining = maximum + 1
            chunks: list[bytes] = []
            while remaining:
                chunk = os.read(descriptor, min(remaining, 65_536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
        except OSError as exc:
            raise ObservationBlocked(f"cannot read {label}: {exc}") from exc
    finally:
        os.close(descriptor)
    if len(content) > maximum:
        raise ObservationBlocked(f"{label} exceeds {maximum} bytes")
    return content


def _open_directory_descriptor(path: Path, label: str) -> int:
    """Open one directory without following its final path component."""

    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ObservationBlocked(
            f"cannot safely acquire {label}: O_NOFOLLOW is unavailable"
        )
    flags = os.O_RDONLY | nofollow
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ObservationBlocked(f"cannot acquire {label}: {exc}") from exc
    try:
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISDIR(mode):
            raise ObservationBlocked(f"{label} is not a non-symlink directory")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _require_absent_at(directory_descriptor: int, name: str, label: str) -> None:
    """Require one basename to be absent through an already-bound directory."""

    try:
        os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ObservationBlocked(f"cannot inspect initial {label}: {exc}") from exc
    raise ObservationBlocked(f"{label} was not initially absent")


def _read_regular_bounded_at(
    directory_descriptor: int,
    name: str,
    maximum: int,
    label: str,
) -> bytes:
    """Read one regular basename relative to a held directory descriptor."""

    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ObservationBlocked(f"cannot safely read {label}: invalid basename")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise ObservationBlocked(
            f"cannot safely read {label}: O_NOFOLLOW is unavailable"
        )
    flags = os.O_RDONLY | nofollow
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptor)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ObservationBlocked(
                f"{label} is not a regular non-symlink file"
            ) from exc
        raise ObservationBlocked(f"cannot read {label}: {exc}") from exc
    return _read_opened_regular(descriptor, maximum, label)


def _adapter_path(root: Path, entry: str) -> Path:
    candidate = Path(entry)
    if candidate.is_absolute():
        raise ObservationBlocked("project adapter entry must be project-relative")
    path = (root / candidate).resolve()
    _relative_within(root, path, "project adapter entry")
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise ObservationBlocked(
            f"project adapter entry is unavailable: {entry}"
        ) from exc
    if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
        raise ObservationBlocked("project adapter entry is not a regular file")
    return path


def _list_bound_directory(descriptor: int, label: str) -> list[str]:
    """List a held directory from its beginning on supported Linux runtimes."""

    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        return os.listdir(descriptor)
    except OSError as exc:
        raise UnsafeInvocation(f"cannot inspect {label}: {exc}") from exc


def _validate_suite_exchange(
    exchange_descriptor: int,
    incoming_descriptor: int,
    suite: str,
) -> None:
    """Require the held suite exchange to contain only its bound sidecar area."""

    exchange_entries = set(
        _list_bound_directory(exchange_descriptor, f"{suite} suite exchange")
    )
    unexpected_exchange = exchange_entries - {"incoming"}
    if unexpected_exchange:
        raise UnsafeInvocation(
            f"{suite} suite created unexpected exchange paths: "
            + ", ".join(sorted(unexpected_exchange))
        )
    if "incoming" not in exchange_entries:
        raise ObservationBlocked(f"{suite} runtime observation directory disappeared")

    try:
        expected = os.fstat(incoming_descriptor)
        observed = os.stat(
            "incoming",
            dir_fd=exchange_descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ObservationBlocked(
            f"cannot reconcile {suite} runtime observation directory: {exc}"
        ) from exc
    if not stat.S_ISDIR(observed.st_mode) or (observed.st_dev, observed.st_ino) != (
        expected.st_dev,
        expected.st_ino,
    ):
        raise ObservationBlocked(f"{suite} runtime observation directory was replaced")

    try:
        incoming_entries = set(
            _list_bound_directory(
                incoming_descriptor, f"{suite} runtime observation directory"
            )
        )
    except UnsafeInvocation as exc:
        raise ObservationBlocked(str(exc)) from exc
    unexpected_incoming = incoming_entries - {"observation.json"}
    if unexpected_incoming:
        raise UnsafeInvocation(
            f"{suite} suite created unexpected incoming paths: "
            + ", ".join(sorted(unexpected_incoming))
        )


def _suite_attempt(
    *,
    suite: str,
    declaration: dict[str, Any],
    verification: dict[str, Any],
    paths: PathSet,
    writer: EvidenceWriter,
    output_parent: BoundOutputParent,
) -> dict[str, Any]:
    command = declaration.get("command")
    timeout_minutes = declaration.get("timeout_minutes")
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(item, str) or not item for item in command)
        or not isinstance(timeout_minutes, int)
        or timeout_minutes < 1
    ):
        return writer.component(
            f"project-{suite}",
            [],
            None,
            "BLOCKED",
            b"",
            b"",
            detail="suite declaration is incomplete",
        )

    entry = command[0]
    try:
        adapter = _adapter_path(paths.project_root, entry)
        adapter_hash = _sha256(adapter.read_bytes())
    except (ObservationBlocked, OSError) as exc:
        return writer.component(
            f"project-{suite}",
            list(command),
            None,
            "BLOCKED",
            b"",
            str(exc).encode(),
            detail="authoritative project entry is unavailable",
        )

    binding = secrets.token_hex(32)
    exchange_name: str | None = None
    exchange_descriptor: int | None = None
    incoming_descriptor: int | None = None
    observation_path: Path | None = None
    try:
        _assert_visible_output_parent(output_parent, f"{suite} suite exchange creation")
        exchange_name, exchange_descriptor = _create_unique_directory_at(
            output_parent.descriptor,
            f".gnostoa-adoption-{suite}-",
            f"{suite} suite exchange",
        )
        os.mkdir("incoming", mode=0o700, dir_fd=exchange_descriptor)
        incoming_descriptor = _open_directory_at(
            exchange_descriptor,
            "incoming",
            f"{suite} runtime observation directory",
        )
        _require_absent_at(
            incoming_descriptor,
            "observation.json",
            f"{suite} runtime observation",
        )
        _validate_suite_exchange(exchange_descriptor, incoming_descriptor, suite)
        observation_path = (
            output_parent.path / exchange_name / "incoming" / "observation.json"
        )
    except (OSError, ObservationBlocked) as exc:
        if incoming_descriptor is not None:
            os.close(incoming_descriptor)
            incoming_descriptor = None
        if exchange_descriptor is not None:
            try:
                if exchange_name is not None:
                    _remove_bound_directory_at(
                        output_parent.descriptor,
                        exchange_descriptor,
                        exchange_name,
                        f"{suite} suite exchange",
                    )
            finally:
                os.close(exchange_descriptor)
                exchange_descriptor = None
        _assert_visible_output_parent(output_parent, f"{suite} suite exchange failure")
        record = writer.component(
            f"project-{suite}",
            list(command),
            None,
            "BLOCKED",
            b"",
            str(exc).encode(),
            detail="runtime observation exchange could not be acquired safely",
        )
        record["adapter_sha256"] = adapter_hash
        record["invocation_binding"] = binding
        return record

    if (
        exchange_name is None
        or exchange_descriptor is None
        or incoming_descriptor is None
        or observation_path is None
    ):
        raise ObservationBlocked("runtime observation exchange was not acquired")
    environment = os.environ.copy()
    environment["GNOSTOA_ADOPTION_OBSERVATION_PATH"] = str(observation_path)
    environment["GNOSTOA_ADOPTION_INVOCATION_BINDING"] = binding

    try:
        try:
            process = _run_bytes(
                list(command),
                cwd=paths.project_root,
                env=environment,
                timeout=timeout_minutes * 60,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            try:
                _validate_suite_exchange(
                    exchange_descriptor, incoming_descriptor, suite
                )
            except ObservationBlocked:
                pass
            record = writer.component(
                f"project-{suite}",
                list(command),
                None,
                "BLOCKED",
                b"",
                str(exc).encode(),
                detail="project entry could not launch",
            )
            record["adapter_sha256"] = adapter_hash
            record["invocation_binding"] = binding
            return record
        except subprocess.TimeoutExpired as exc:
            try:
                _validate_suite_exchange(
                    exchange_descriptor, incoming_descriptor, suite
                )
            except ObservationBlocked:
                pass
            stdout = exc.stdout if isinstance(exc.stdout, bytes) else b""
            stderr = exc.stderr if isinstance(exc.stderr, bytes) else b""
            record = writer.component(
                f"project-{suite}",
                list(command),
                None,
                "FAIL",
                stdout,
                stderr,
                detail="project suite timed out",
            )
            record["adapter_sha256"] = adapter_hash
            record["invocation_binding"] = binding
            return record

        try:
            _validate_suite_exchange(exchange_descriptor, incoming_descriptor, suite)
        except ObservationBlocked as exc:
            retained_layout_observation: dict[str, Any] = {}
            try:
                bound_bytes = _read_regular_bounded_at(
                    incoming_descriptor,
                    observation_path.name,
                    MAX_OBSERVATION_BYTES,
                    f"{suite} runtime observation",
                )
            except ObservationBlocked:
                pass
            else:
                retained_layout_observation = writer.write_bytes(
                    f"runtime-observations/{suite}.json",
                    bound_bytes,
                    origin=f"project-adapter:{suite}",
                )
            record = writer.component(
                f"project-{suite}",
                list(command),
                process.returncode,
                (
                    "PASS"
                    if process.returncode == 0
                    else "BLOCKED"
                    if process.returncode in {126, 127}
                    else "FAIL"
                ),
                process.stdout,
                process.stderr,
            )
            record["adapter_sha256"] = adapter_hash
            record["invocation_binding"] = binding
            record["runtime_observation"] = {
                "result": "BLOCKED",
                "authority": "project-reported",
                "detail": str(exc),
                "independent_attestation": "NOT OBSERVED",
                **retained_layout_observation,
            }
            return record

        if process.returncode == 0:
            suite_result = "PASS"
        elif process.returncode in {126, 127}:
            suite_result = "BLOCKED"
        else:
            suite_result = "FAIL"
        record = writer.component(
            f"project-{suite}",
            list(command),
            process.returncode,
            suite_result,
            process.stdout,
            process.stderr,
        )
        record["adapter_sha256"] = adapter_hash
        record["invocation_binding"] = binding

        retained_observation: dict[str, Any] = {}
        try:
            raw_observation = _read_regular_bounded_at(
                incoming_descriptor,
                observation_path.name,
                MAX_OBSERVATION_BYTES,
                f"{suite} runtime observation",
            )
            retained_observation = writer.write_bytes(
                f"runtime-observations/{suite}.json",
                raw_observation,
                origin=f"project-adapter:{suite}",
            )
            observation = validate_runtime_observation(
                raw_observation,
                suite=suite,
                invocation_binding=binding,
                origin_entry=entry,
            )
            record["runtime_observation"] = {
                "result": "PASS",
                "authority": "project-reported",
                **retained_observation,
                "route_kind": observation.route_kind,
                "independent_attestation": "NOT OBSERVED",
            }

            runtime = verification.get("runtime")
            if isinstance(runtime, dict) and runtime.get("mode") == "project":
                declared_image = runtime.get("image")
                if isinstance(declared_image, str) and "@" in declared_image:
                    declared_digest = declared_image.rsplit("@", 1)[1]
                    if observation.route_kind != "container":
                        raise ObservationConflict(
                            "complete native project runtime conflicts with mandatory image declaration"
                        )
                    if observation.manifest_digest != declared_digest:
                        raise ObservationBlocked(
                            "runtime.image descriptor kind cannot be established from "
                            "the differing observed platform manifest"
                        )
                    record["runtime_observation"]["declared_manifest_coherence"] = (
                        "PASS"
                    )
            record["runtime_observation"]["value"] = observation.value
        except ObservationConflict as exc:
            record["runtime_observation"] = {
                "result": "FAIL",
                "authority": "project-reported",
                "detail": str(exc),
                "independent_attestation": "NOT OBSERVED",
                **retained_observation,
            }
        except ObservationBlocked as exc:
            record["runtime_observation"] = {
                "result": "BLOCKED",
                "authority": "project-reported",
                "detail": str(exc),
                "independent_attestation": "NOT OBSERVED",
                **retained_observation,
            }
        _validate_suite_exchange(exchange_descriptor, incoming_descriptor, suite)
        return record
    finally:
        cleanup_error: AdoptionCheckError | None = None
        if incoming_descriptor is not None:
            os.close(incoming_descriptor)
        if exchange_descriptor is not None:
            try:
                _remove_bound_directory_at(
                    output_parent.descriptor,
                    exchange_descriptor,
                    exchange_name,
                    f"{suite} suite exchange",
                )
            except AdoptionCheckError as exc:
                cleanup_error = exc
            finally:
                os.close(exchange_descriptor)
        _assert_visible_output_parent(output_parent, f"{suite} suite completion")
        if cleanup_error is not None:
            raise cleanup_error


def _identity_result(
    paths: PathSet,
    lock: dict[str, Any],
    execution_route: str,
    writer: EvidenceWriter,
) -> tuple[dict[str, Any], str]:
    measurements: dict[str, Any] = {}
    blocked: list[str] = []
    failed: list[str] = []
    identities = (
        ("documentation", paths.documentation_root),
        ("toolkit_source", paths.toolkit_source),
    )
    for name, root in identities:
        try:
            measurements[name] = _source_identity(root)
        except BlockedPrerequisite as exc:
            measurements[name] = {"root": str(root.resolve()), "result": "NOT OBSERVED"}
            blocked.append(str(exc))
    source_identity = measurements.get("toolkit_source", {})
    try:
        measurements["executing_runtime"] = _execution_identity(
            _execution_root(),
            paths.toolkit_source,
            source_identity,
        )
    except BlockedPrerequisite as exc:
        measurements["executing_runtime"] = {
            "root": str(_execution_root().resolve()),
            "result": "NOT OBSERVED",
        }
        blocked.append(str(exc))

    toolkit = lock.get("toolkit")
    runtime = lock.get("runtime")
    declarations = {
        "toolkit_revision": toolkit.get("revision")
        if isinstance(toolkit, dict)
        else None,
        "toolkit_public_surface_digest": (
            toolkit.get("public_surface_digest") if isinstance(toolkit, dict) else None
        ),
        "runtime_revision": runtime.get("revision")
        if isinstance(runtime, dict)
        else None,
        "runtime_image": runtime.get("image") if isinstance(runtime, dict) else None,
        "execution_route": execution_route,
    }

    documentation = measurements.get("documentation", {})
    source = measurements.get("toolkit_source", {})
    executing = measurements.get("executing_runtime", {})
    source_binding = executing.get("source_binding")
    if isinstance(source_binding, dict) and source_binding.get("result") == "FAIL":
        failed.append(
            "installed Python distribution differs from pinned toolkit source"
        )
    document_digest = documentation.get("public_surface_digest")
    source_digest = source.get("public_surface_digest")
    runtime_digest = executing.get("public_surface_digest")
    if all(isinstance(item, str) for item in (document_digest, source_digest)):
        if document_digest != source_digest:
            blocked.append("documentation and toolkit public surfaces differ")
    if all(isinstance(item, str) for item in (source_digest, runtime_digest)):
        if source_digest != runtime_digest:
            failed.append("toolkit source and executing runtime public surfaces differ")

    source_revision = source.get("revision")
    runtime_revision = executing.get("revision")
    declared_source_revision = declarations["toolkit_revision"]
    declared_runtime_revision = declarations["runtime_revision"]
    if (
        isinstance(source_revision, str)
        and isinstance(declared_source_revision, str)
        and source_revision != declared_source_revision
    ):
        failed.append("measured toolkit revision conflicts with the toolkit lock")
    if (
        isinstance(runtime_revision, str)
        and isinstance(declared_runtime_revision, str)
        and runtime_revision != declared_runtime_revision
    ):
        failed.append("measured runtime revision conflicts with the toolkit lock")
    if isinstance(source_revision, str) and isinstance(runtime_revision, str):
        if source_revision != runtime_revision:
            failed.append("measured toolkit and runtime revisions differ")

    external_oci: dict[str, Any]
    if execution_route == "oci":
        external_oci = {
            "result": "NOT OBSERVED",
            "declaration": declarations["runtime_image"],
            "detail": (
                "no independently verifiable execution-digest profile is selected in v1"
            ),
        }
        if paths.oci_digest_evidence is not None:
            try:
                supplied = _read_regular_bounded(
                    paths.oci_digest_evidence,
                    1_048_576,
                    "OCI digest evidence",
                )
            except ObservationBlocked as exc:
                external_oci["supplied_evidence"] = {
                    "result": "INVALID",
                    "detail": str(exc),
                }
            else:
                artifact = writer.write_bytes(
                    "oci-digest-evidence.bin",
                    supplied,
                    origin="caller-supplied-oci-evidence",
                )
                external_oci["supplied_evidence"] = {
                    "result": "DECLARATION ONLY",
                    **artifact,
                }
        blocked.append("external OCI execution digest is not independently observed")
    else:
        external_oci = {"result": "NOT APPLICABLE"}

    if failed:
        result = "FAIL"
    elif blocked:
        result = "BLOCKED"
    else:
        result = "PASS"
    return {
        "result": result,
        "declarations": declarations,
        "measurements": measurements,
        "external_oci_digest": external_oci,
        "failures": failed,
        "blockers": blocked,
    }, result


def _context_components(
    paths: PathSet,
    seeds: list[str],
    depth: int,
    max_tokens: int,
    writer: EvidenceWriter,
    *,
    bundle_ready: bool,
) -> dict[str, str]:
    if not bundle_ready:
        return {
            "generation": "NOT RUN",
            "determinism": "NOT RUN",
            "retention": "NOT RUN",
        }
    arguments = [
        "--project-root",
        str(paths.project_root),
        "--profile",
        str(paths.profile),
        "--bundle",
        str(paths.bundle),
        "--depth",
        str(depth),
        "--max-tokens",
        str(max_tokens),
    ]
    for seed in seeds:
        arguments.extend(["--seed", seed])
    command = ["knowledge", "context-pack", *arguments]

    first_code, first_stdout, first_stderr = _call_tool(
        build_context_pack.main, arguments
    )
    writer.component(
        "context-pack-first",
        command,
        first_code,
        _component_result(first_code),
        first_stdout,
        first_stderr,
    )
    second_code, second_stdout, second_stderr = _call_tool(
        build_context_pack.main, arguments
    )
    writer.component(
        "context-pack-second",
        command,
        second_code,
        _component_result(second_code),
        second_stdout,
        second_stderr,
    )

    if first_code != 0 or second_code != 0:
        return {
            "generation": "FAIL" if 1 in {first_code, second_code} else "ERROR",
            "determinism": "NOT RUN",
            "retention": "NOT RUN",
        }
    if first_stdout != second_stdout:
        return {
            "generation": "PASS",
            "determinism": "FAIL",
            "retention": "NOT RUN",
        }
    artifact = writer.write_bytes(
        "context-pack.md",
        first_stdout,
        origin="gnostoa-context-generator",
    )
    return {
        "generation": "PASS",
        "determinism": "PASS",
        "retention": "PASS",
        "sha256": artifact["sha256"],
    }


def _subject_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: snapshot[key]
        for key in (
            "head",
            "tree",
            "status_sha256",
            "staged_index_sha256",
            "staged_index_bytes",
            "candidate_patch_sha256",
            "candidate_patch_bytes",
        )
    }


def _snapshot_stability_problems(
    before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    problems: list[str] = []
    if before["head"] != after["head"] or before["tree"] != after["tree"]:
        problems.append("Git HEAD or tree changed during adoption-check")
    if before["status_sha256"] != after["status_sha256"]:
        problems.append("Git status changed during adoption-check")
    if (
        before["staged_index_sha256"] != after["staged_index_sha256"]
        or before["staged_index_bytes"] != after["staged_index_bytes"]
    ):
        problems.append("staged index identity changed during adoption-check")
    if before["repository_object_format"] != after["repository_object_format"]:
        problems.append("repository object format changed during adoption-check")
    if before["gitlinks"] != after["gitlinks"]:
        problems.append("required gitlinks changed during adoption-check")
    if (
        before["candidate_patch_sha256"] != after["candidate_patch_sha256"]
        or before["candidate_patch_bytes"] != after["candidate_patch_bytes"]
    ):
        problems.append("staged candidate changed during adoption-check")
    return problems


def _artifact_reference(writer: EvidenceWriter, path: str) -> dict[str, Any]:
    for artifact in writer.artifacts():
        if artifact.path == path:
            return artifact.metadata()
    raise UnsafeInvocation(f"assurance observation cites missing evidence: {path}")


def _artifact_references(
    writer: EvidenceWriter, paths: list[str]
) -> list[dict[str, Any]]:
    return [_artifact_reference(writer, path) for path in sorted(set(paths))]


def _write_json_evidence(
    writer: EvidenceWriter,
    path: str,
    value: dict[str, Any] | list[dict[str, Any]],
    *,
    origin: str,
) -> dict[str, Any]:
    return writer.write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        origin=origin,
    )


def _observation_outcome(values: list[str]) -> str:
    if any(value == "ERROR" for value in values):
        return "ERROR"
    if any(value == "FAIL" for value in values):
        return "FAIL"
    if any(value == "BLOCKED" for value in values):
        return "BLOCKED"
    if any(value in {"NOT RUN", "NOT OBSERVED", "ABSENT"} for value in values):
        return "NOT RUN"
    if values and all(value in {"PASS", "VALID", "ENTERED"} for value in values):
        return "PASS"
    raise UnsafeInvocation(
        "cannot map assurance observation outcomes: " + ", ".join(values)
    )


def _condition_state(
    outcome: str,
    *,
    failure_reason: str = "ObservedFailure",
    true_reason: str = "Satisfied",
) -> tuple[str, str]:
    if outcome == "PASS":
        return "TRUE", true_reason
    if outcome == "FAIL":
        return "FALSE", failure_reason
    if outcome == "ERROR":
        return "UNKNOWN", "InternalError"
    if outcome == "NOT RUN":
        return "UNKNOWN", "NotRun"
    if outcome == "BLOCKED":
        return "UNKNOWN", "PrerequisiteBlocked"
    raise UnsafeInvocation(f"unsupported observation outcome: {outcome}")


def _public_components(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for record in records:
        item = {
            key: record[key]
            for key in ("name", "command", "exit_code", "result", "stdout", "stderr")
        }
        detail = record.get("detail")
        if isinstance(detail, str):
            item["detail"] = detail
        public.append(item)
    return public


def _component_evidence_paths(records: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for record in records:
        for key in ("stdout", "stderr"):
            value = record.get(key)
            if isinstance(value, str):
                paths.append(value)
    return paths


def _runtime_report_result(record: dict[str, Any]) -> str:
    observation = record.get("runtime_observation")
    if isinstance(observation, dict):
        return str(observation.get("result", "BLOCKED"))
    return "NOT RUN" if record.get("result") == "NOT RUN" else "BLOCKED"


def _build_assurance_result(
    *,
    args: argparse.Namespace,
    paths: PathSet,
    writer: EvidenceWriter,
    result_schema: dict[str, Any],
    schema_artifact: dict[str, Any],
    policy_artifact: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    representation_problems: list[str],
    identity: dict[str, Any],
    runtime_component: dict[str, Any],
    change_component: dict[str, Any],
    ci_component: dict[str, Any],
    bundle_component: dict[str, Any],
    context: dict[str, str],
    suite_records: list[dict[str, Any]],
    stability_outcome: str | None = None,
) -> dict[str, Any]:
    subject = adoption_assurance.build_candidate_subject(
        repository_object_format=str(before["repository_object_format"]),
        base_commit=str(before["head"]),
        staged_index_sha256=str(before["staged_index_sha256"]),
        staged_index_bytes=int(before["staged_index_bytes"]),
        candidate_patch_sha256=str(before["candidate_patch_sha256"]),
        candidate_patch_bytes=int(before["candidate_patch_bytes"]),
        gitlinks=before["gitlinks"],
        before=_subject_snapshot(before),
        after=_subject_snapshot(after),
    )
    subject_id = str(subject["id"])

    git_state_reference = _artifact_reference(writer, "git-state.json")
    candidate_patch_reference = _artifact_reference(writer, "candidate.patch")
    execution_detail = _write_json_evidence(
        writer,
        "observations/execution-subjects.json",
        {
            "identity": identity,
            "runtime_lock": {
                "result": runtime_component["result"],
                "exit_code": runtime_component["exit_code"],
            },
        },
        origin="gnostoa-observation:execution-subjects",
    )
    structural_detail = _write_json_evidence(
        writer,
        "observations/structural-validation.json",
        {
            component["name"]: {
                "result": component["result"],
                "exit_code": component["exit_code"],
            }
            for component in (change_component, ci_component, bundle_component)
        },
        origin="gnostoa-observation:structural-validation",
    )
    context_detail = _write_json_evidence(
        writer,
        "observations/context-determinism.json",
        context,
        origin="gnostoa-observation:context-determinism",
    )
    suite_detail = _write_json_evidence(
        writer,
        "observations/project-suites.json",
        [
            {
                "name": record["name"],
                "command": record["command"],
                "exit_code": record["exit_code"],
                "result": record["result"],
                "adapter_sha256": record.get("adapter_sha256"),
                "invocation_binding": record.get("invocation_binding"),
            }
            for record in suite_records
        ],
        origin="gnostoa-observation:project-suites",
    )
    runtime_detail = _write_json_evidence(
        writer,
        "observations/project-runtime-reports.json",
        [
            {
                "suite": record["name"].removeprefix("project-"),
                "report": record.get(
                    "runtime_observation",
                    {
                        "result": _runtime_report_result(record),
                        "detail": "runtime observation was not acquired or run",
                    },
                ),
            }
            for record in suite_records
        ],
        origin="gnostoa-observation:project-runtime-reports",
    )
    integrity_detail = _write_json_evidence(
        writer,
        "observations/evidence-integrity.json",
        {
            "contract": "authoritative-ledger-and-bound-publication/v1",
            "claim_activation": "complete-publication-and-external-commitment",
            "internal_manifest": "SHA256SUMS",
            "external_commitment_schema": BUNDLE_COMMITMENT_SCHEMA,
        },
        origin="gnostoa-observation:evidence-integrity",
    )

    stable_outcome = stability_outcome or (
        "FAIL" if representation_problems else "PASS"
    )
    execution_outcome = _observation_outcome(
        [str(identity["result"]), str(runtime_component["result"])]
    )
    structural_outcome = _observation_outcome(
        [
            str(change_component["result"]),
            str(ci_component["result"]),
            str(bundle_component["result"]),
        ]
    )
    context_outcome = _observation_outcome(
        [context["generation"], context["determinism"], context["retention"]]
    )
    suite_outcome = _observation_outcome(
        [str(record["result"]) for record in suite_records]
    )
    runtime_outcome = _observation_outcome(
        [_runtime_report_result(record) for record in suite_records]
    )
    candidate_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        {
            "name": "repository-object-format",
            "value": str(before["repository_object_format"]),
        },
    ]
    execution_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        {
            "name": "runtime-lock-command",
            "value": _sha256(
                adoption_assurance.canonical_json_bytes(runtime_component["command"])
            ),
        },
    ]
    structural_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        {
            "name": "structural-command-set",
            "value": _sha256(
                adoption_assurance.canonical_json_bytes(
                    [
                        change_component["command"],
                        ci_component["command"],
                        bundle_component["command"],
                    ]
                )
            ),
        },
    ]
    context_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        {
            "name": "context-arguments",
            "value": _sha256(
                adoption_assurance.canonical_json_bytes(
                    {
                        "seeds": list(args.seed),
                        "depth": args.depth,
                        "max_tokens": args.max_tokens,
                    }
                )
            ),
        },
    ]
    suite_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        *[
            {
                "name": f"suite.{record['name'].removeprefix('project-')}.adapter",
                "value": str(record.get("adapter_sha256", "NOT OBSERVED")),
            }
            for record in suite_records
        ],
        *[
            {
                "name": f"suite.{record['name'].removeprefix('project-')}.command",
                "value": _sha256(
                    adoption_assurance.canonical_json_bytes(record["command"])
                ),
            }
            for record in suite_records
        ],
    ]
    runtime_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        *[
            {
                "name": f"suite.{record['name'].removeprefix('project-')}.report",
                "value": str(
                    record.get("runtime_observation", {}).get("sha256", "NOT OBSERVED")
                ),
            }
            for record in suite_records
        ],
    ]
    policy_configuration = [
        {"name": "candidate-subject", "value": subject_id},
        {"name": "readiness-policy", "value": adoption_assurance.POLICY_SHA256},
    ]
    context_evidence = [context_detail]
    if any(artifact.path == "context-pack.md" for artifact in writer.artifacts()):
        context_evidence.append(_artifact_reference(writer, "context-pack.md"))
    runtime_evidence = [runtime_detail]
    for record in suite_records:
        runtime_observation = record.get("runtime_observation")
        if isinstance(runtime_observation, dict):
            observation_path = runtime_observation.get("path")
            if isinstance(observation_path, str):
                runtime_evidence.append(_artifact_reference(writer, observation_path))

    observations = [
        adoption_assurance.make_observation(
            observation_id="observation.candidate-stability",
            observation_type="candidate-stability",
            subject_id=subject_id,
            outcome=stable_outcome,
            producer="gnostoa-adoption-check",
            configuration=candidate_configuration,
            evidence=[candidate_patch_reference, git_state_reference],
        ),
        adoption_assurance.make_observation(
            observation_id="observation.execution-subject-coherence",
            observation_type="execution-subject-coherence",
            subject_id=subject_id,
            outcome=execution_outcome,
            producer="gnostoa-adoption-check",
            configuration=execution_configuration,
            evidence=[
                execution_detail,
                *_artifact_references(
                    writer, _component_evidence_paths([runtime_component])
                ),
            ],
        ),
        adoption_assurance.make_observation(
            observation_id="observation.structural-validation",
            observation_type="structural-validation",
            subject_id=subject_id,
            outcome=structural_outcome,
            producer="gnostoa-adoption-check",
            configuration=structural_configuration,
            evidence=[
                structural_detail,
                *_artifact_references(
                    writer,
                    _component_evidence_paths(
                        [change_component, ci_component, bundle_component]
                    ),
                ),
            ],
        ),
        adoption_assurance.make_observation(
            observation_id="observation.context-determinism",
            observation_type="context-determinism",
            subject_id=subject_id,
            outcome=context_outcome,
            producer="gnostoa-adoption-check",
            configuration=context_configuration,
            evidence=context_evidence,
        ),
        adoption_assurance.make_observation(
            observation_id="observation.project-suite-process",
            observation_type="project-suite-process",
            subject_id=subject_id,
            outcome=suite_outcome,
            producer="project-adapter",
            configuration=suite_configuration,
            evidence=[
                suite_detail,
                *_artifact_references(writer, _component_evidence_paths(suite_records)),
            ],
        ),
        adoption_assurance.make_observation(
            observation_id="observation.project-runtime-report",
            observation_type="project-runtime-report",
            subject_id=subject_id,
            outcome=runtime_outcome,
            producer="project-adapter",
            configuration=runtime_configuration,
            evidence=runtime_evidence,
        ),
        adoption_assurance.make_observation(
            observation_id="observation.evidence-publication",
            observation_type="evidence-publication",
            subject_id=subject_id,
            outcome="PASS",
            producer="gnostoa-adoption-check",
            configuration=policy_configuration,
            evidence=[integrity_detail, schema_artifact, policy_artifact],
        ),
        adoption_assurance.make_observation(
            observation_id="observation.semantic-review-requirement",
            observation_type="semantic-review-requirement",
            subject_id=subject_id,
            outcome="PASS",
            producer="gnostoa-readiness-policy",
            configuration=policy_configuration,
            evidence=[policy_artifact],
        ),
    ]

    stability_failure_reason = (
        "SubjectChanged"
        if any(
            "changed during adoption-check" in item for item in representation_problems
        )
        else "ObservedFailure"
    )
    condition_inputs = (
        (
            "CandidateStable",
            observations[0],
            stability_failure_reason,
            "Satisfied",
        ),
        (
            "ExecutionSubjectsCoherent",
            observations[1],
            "SubjectIncoherent",
            "Satisfied",
        ),
        ("StructuralValid", observations[2], "ObservedFailure", "Satisfied"),
        ("ContextDeterministic", observations[3], "ObservedFailure", "Satisfied"),
        ("ProjectSuitesPassed", observations[4], "ObservedFailure", "Satisfied"),
        (
            "RuntimeObservationAvailable",
            observations[5],
            "ObservedFailure",
            "Satisfied",
        ),
        (
            "EvidenceIntegrityPreserved",
            observations[6],
            "ObservedFailure",
            "Satisfied",
        ),
        (
            "SemanticReviewRequired",
            observations[7],
            "ObservedFailure",
            "Required",
        ),
    )
    conditions: list[dict[str, Any]] = []
    for condition_type, observation, failure_reason, true_reason in condition_inputs:
        status, reason = _condition_state(
            str(observation["outcome"]),
            failure_reason=failure_reason,
            true_reason=true_reason,
        )
        conditions.append(
            adoption_assurance.make_condition(
                condition_type=condition_type,
                subject_id=subject_id,
                status=status,
                reason=reason,
                observations=[observation],
            )
        )

    readiness = adoption_assurance.evaluate_readiness(subject_id, conditions)
    exit_code = int(readiness["exit_code"])
    outcome = {
        0: "READY FOR ACCOUNTABLE-OWNER REVIEW",
        1: "MECHANICAL CHECK FAILED",
        2: "INVALID OR INTERNAL ERROR",
        3: "BLOCKED",
    }[exit_code]
    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "outcome": outcome,
        "exit_code": exit_code,
        "subject": subject,
        "arguments": {
            "execution_route": args.execution_route,
            "seeds": list(args.seed),
            "depth": args.depth,
            "max_tokens": args.max_tokens,
            "project_root": str(paths.project_root),
            "output_dir": str(paths.output),
            "overrides": paths.overrides,
        },
        "tool_versions": _tool_versions(paths.project_root),
        "components": _public_components(writer.components),
        "observations": observations,
        "conditions": conditions,
        "contracts": {
            "result_schema": {
                "schema": "json-schema-draft-2020-12",
                "id": result_schema["$id"],
                "sha256": schema_artifact["sha256"],
                "evidence": schema_artifact,
            },
            "readiness_policy": {
                "schema": adoption_assurance.POLICY_SCHEMA,
                "id": adoption_assurance.POLICY_ID,
                "sha256": policy_artifact["sha256"],
                "evidence": policy_artifact,
            },
        },
        "readiness": readiness,
        "owner_disposition": {
            "semantic_review": "REQUIRED",
            "durable_adoption": "NOT DETERMINED",
        },
        "artifacts": writer.manifest(),
    }
    try:
        adoption_assurance.validate_result(result, result_schema)
    except adoption_assurance.AssuranceContractError as exc:
        raise UnsafeInvocation(str(exc)) from exc
    return result


def _directory_open_flags() -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise UnsafeInvocation(
            "descriptor-bound evidence materialization requires O_NOFOLLOW and O_DIRECTORY"
        )
    flags = int(os.O_RDONLY | nofollow | directory)
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    return flags


def _safe_basename(name: str, label: str) -> str:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or "\x00" in name
        or len(os.fsencode(name)) > 240
    ):
        raise UnsafeInvocation(f"invalid {label} basename")
    return name


def _acquire_output_parent(output: Path) -> BoundOutputParent:
    parent_path = output.parent
    try:
        descriptor = os.open(parent_path, _directory_open_flags())
    except OSError as exc:
        raise UnsafeInvocation(f"cannot bind output parent: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode):
            raise UnsafeInvocation("output parent is not a non-symlink directory")
        bound = BoundOutputParent(
            path=parent_path,
            descriptor=descriptor,
            device=metadata.st_dev,
            inode=metadata.st_ino,
        )
        _assert_visible_output_parent(bound, "descriptor acquisition")
        output_name = _safe_basename(output.name, "output")
        try:
            os.stat(output_name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise UnsafeInvocation(
                f"cannot inspect output through bound parent: {exc}"
            ) from exc
        else:
            raise UnsafeInvocation(f"output directory already exists: {output}")
    except BaseException:
        os.close(descriptor)
        raise
    return bound


def _assert_visible_output_parent(
    parent: BoundOutputParent,
    phase: str,
) -> None:
    try:
        visible = parent.path.lstat()
    except OSError as exc:
        raise UnsafeInvocation(
            f"output parent became unavailable during {phase}: {exc}"
        ) from exc
    if (
        stat.S_ISLNK(visible.st_mode)
        or not stat.S_ISDIR(visible.st_mode)
        or (visible.st_dev, visible.st_ino) != (parent.device, parent.inode)
    ):
        raise UnsafeInvocation(f"output parent identity changed during {phase}")


def _create_unique_directory_at(
    parent_descriptor: int,
    prefix: str,
    label: str,
) -> tuple[str, int]:
    if not prefix or len(os.fsencode(prefix)) > 160:
        raise UnsafeInvocation(f"invalid {label} prefix")
    for _ in range(32):
        name = _safe_basename(f"{prefix}{secrets.token_hex(16)}", label)
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
        except FileExistsError:
            continue
        except OSError as exc:
            raise UnsafeInvocation(f"cannot create {label}: {exc}") from exc
        try:
            return name, _open_directory_at(parent_descriptor, name, label)
        except BaseException:
            try:
                os.rmdir(name, dir_fd=parent_descriptor)
            except OSError:
                pass
            raise
    raise UnsafeInvocation(f"cannot allocate collision-free {label}")


def _clear_bound_directory(descriptor: int, label: str) -> None:
    for name in _list_bound_directory(descriptor, label):
        _safe_basename(name, f"{label} entry")
        try:
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeInvocation(
                f"cannot inspect {label} entry {name}: {exc}"
            ) from exc
        if stat.S_ISDIR(metadata.st_mode):
            child = _open_directory_at(descriptor, name, f"{label} entry {name}")
            try:
                opened = os.fstat(child)
                if (opened.st_dev, opened.st_ino) != (
                    metadata.st_dev,
                    metadata.st_ino,
                ):
                    raise UnsafeInvocation(
                        f"{label} entry {name} was replaced during cleanup"
                    )
                _clear_bound_directory(child, f"{label}/{name}")
            finally:
                os.close(child)
            try:
                current = os.stat(
                    name,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise UnsafeInvocation(
                    f"cannot reconcile {label} directory {name}: {exc}"
                ) from exc
            if not stat.S_ISDIR(current.st_mode) or (
                current.st_dev,
                current.st_ino,
            ) != (metadata.st_dev, metadata.st_ino):
                raise UnsafeInvocation(
                    f"{label} directory {name} was replaced during cleanup"
                )
            try:
                os.rmdir(name, dir_fd=descriptor)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise UnsafeInvocation(
                    f"cannot remove {label} directory {name}: {exc}"
                ) from exc
        else:
            try:
                os.unlink(name, dir_fd=descriptor)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise UnsafeInvocation(
                    f"cannot remove {label} entry {name}: {exc}"
                ) from exc


def _bound_directory_name(
    parent_descriptor: int,
    descriptor: int,
    preferred_name: str,
    label: str,
) -> str | None:
    expected = os.fstat(descriptor)
    matches: list[str] = []
    names = _list_bound_directory(parent_descriptor, f"{label} parent")
    names.sort(key=lambda name: name != preferred_name)
    for name in names:
        try:
            metadata = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise UnsafeInvocation(
                f"cannot locate bound {label} directory: {exc}"
            ) from exc
        if stat.S_ISDIR(metadata.st_mode) and (
            metadata.st_dev,
            metadata.st_ino,
        ) == (expected.st_dev, expected.st_ino):
            matches.append(name)
    if not matches:
        if expected.st_nlink == 0:
            return None
        raise UnsafeInvocation(f"cannot locate bound {label} directory")
    if len(matches) != 1:
        raise UnsafeInvocation(f"bound {label} directory has ambiguous names")
    return matches[0]


def _remove_bound_directory_at(
    parent_descriptor: int,
    descriptor: int,
    preferred_name: str,
    label: str,
) -> None:
    _clear_bound_directory(descriptor, label)
    name = _bound_directory_name(
        parent_descriptor,
        descriptor,
        preferred_name,
        label,
    )
    if name is None:
        return
    expected = os.fstat(descriptor)
    try:
        visible = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as exc:
        raise UnsafeInvocation(f"cannot reconcile bound {label}: {exc}") from exc
    if not stat.S_ISDIR(visible.st_mode) or (
        visible.st_dev,
        visible.st_ino,
    ) != (expected.st_dev, expected.st_ino):
        raise UnsafeInvocation(f"bound {label} directory was replaced during cleanup")
    try:
        os.rmdir(name, dir_fd=parent_descriptor)
    except OSError as exc:
        raise UnsafeInvocation(f"cannot remove bound {label}: {exc}") from exc


def _open_directory_at(parent_descriptor: int, name: str, label: str) -> int:
    try:
        descriptor = os.open(
            name,
            _directory_open_flags(),
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        raise UnsafeInvocation(f"cannot open {label}: {exc}") from exc
    try:
        mode = os.fstat(descriptor).st_mode
        if not stat.S_ISDIR(mode):
            raise UnsafeInvocation(f"{label} is not a non-symlink directory")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _create_or_open_directory_at(
    parent_descriptor: int,
    name: str,
    label: str,
) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
    except FileExistsError:
        pass
    except OSError as exc:
        raise UnsafeInvocation(f"cannot create {label}: {exc}") from exc
    return _open_directory_at(parent_descriptor, name, label)


def _write_all(descriptor: int, content: bytes, label: str) -> None:
    offset = 0
    try:
        while offset < len(content):
            written = os.write(descriptor, content[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short evidence write")
            offset += written
        os.fsync(descriptor)
    except OSError as exc:
        raise UnsafeInvocation(f"cannot write {label}: {exc}") from exc


def _read_opened_materialized(
    descriptor: int,
    maximum: int,
    label: str,
) -> bytes:
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise UnsafeInvocation(f"{label} is not one singly linked regular file")
        os.lseek(descriptor, 0, os.SEEK_SET)
        remaining = maximum + 1
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(remaining, 65_536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    except OSError as exc:
        raise UnsafeInvocation(f"cannot read {label}: {exc}") from exc
    content = b"".join(chunks)
    if len(content) > maximum:
        raise UnsafeInvocation(f"{label} changed length during reconciliation")
    return content


def _write_artifact_at(root_descriptor: int, artifact: EvidenceArtifact) -> None:
    parts = PurePosixPath(artifact.path).parts
    parent_descriptor = os.dup(root_descriptor)
    try:
        for index, part in enumerate(parts[:-1]):
            child = _create_or_open_directory_at(
                parent_descriptor,
                part,
                f"evidence directory {'/'.join(parts[: index + 1])}",
            )
            os.close(parent_descriptor)
            parent_descriptor = child

        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            raise UnsafeInvocation(
                "descriptor-bound evidence materialization requires O_NOFOLLOW"
            )
        flags |= nofollow
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        try:
            descriptor = os.open(
                parts[-1],
                flags,
                0o600,
                dir_fd=parent_descriptor,
            )
        except OSError as exc:
            raise UnsafeInvocation(
                f"cannot create evidence artifact without replacement: {artifact.path}: {exc}"
            ) from exc
        try:
            _write_all(descriptor, artifact.content, artifact.path)
            retained = _read_opened_materialized(
                descriptor,
                artifact.byte_length,
                artifact.path,
            )
            if retained != artifact.content or _sha256(retained) != artifact.digest:
                raise UnsafeInvocation(
                    f"evidence artifact differs immediately after writing: {artifact.path}"
                )
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_descriptor)


def _read_regular_at_for_reconciliation(
    parent_descriptor: int,
    name: str,
    maximum: int,
    label: str,
) -> bytes:
    flags = os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise UnsafeInvocation(
            "descriptor-bound evidence reconciliation requires O_NOFOLLOW"
        )
    flags |= nofollow
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        raise UnsafeInvocation(f"cannot open {label}: {exc}") from exc
    try:
        return _read_opened_materialized(descriptor, maximum, label)
    finally:
        os.close(descriptor)


def _reconcile_directory(
    descriptor: int,
    prefix: PurePosixPath,
    expected: dict[str, EvidenceArtifact],
    observed: set[str],
) -> None:
    names = sorted(_list_bound_directory(descriptor, "materialized evidence"))
    for name in names:
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            raise UnsafeInvocation("materialized evidence contains an invalid basename")
        relative_path = prefix / name if prefix.parts else PurePosixPath(name)
        relative = relative_path.as_posix()
        try:
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except OSError as exc:
            raise UnsafeInvocation(
                f"cannot inspect materialized evidence path {relative}: {exc}"
            ) from exc
        if stat.S_ISDIR(metadata.st_mode):
            if not any(path.startswith(relative + "/") for path in expected):
                raise UnsafeInvocation(
                    f"unexpected materialized evidence directory: {relative}"
                )
            child = _open_directory_at(
                descriptor,
                name,
                f"materialized evidence directory {relative}",
            )
            try:
                _reconcile_directory(child, relative_path, expected, observed)
            finally:
                os.close(child)
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise UnsafeInvocation(
                f"materialized evidence path is not regular: {relative}"
            )
        artifact = expected.get(relative)
        if artifact is None:
            raise UnsafeInvocation(f"unexpected materialized evidence file: {relative}")
        content = _read_regular_at_for_reconciliation(
            descriptor,
            name,
            artifact.byte_length,
            f"materialized evidence artifact {relative}",
        )
        if (
            content != artifact.content
            or len(content) != artifact.byte_length
            or _sha256(content) != artifact.digest
        ):
            raise UnsafeInvocation(
                f"materialized evidence differs from authoritative ledger: {relative}"
            )
        observed.add(relative)


def _reconcile_materialized(
    root: Path,
    artifacts: tuple[EvidenceArtifact, ...],
) -> None:
    root_descriptor = _open_directory_descriptor(root, "materialized evidence root")
    try:
        _reconcile_materialized_at(root_descriptor, artifacts)
    finally:
        os.close(root_descriptor)


def _reconcile_materialized_at(
    root_descriptor: int,
    artifacts: tuple[EvidenceArtifact, ...],
) -> None:
    expected = {artifact.path: artifact for artifact in artifacts}
    observed: set[str] = set()
    _reconcile_directory(root_descriptor, PurePosixPath(), expected, observed)
    missing = sorted(set(expected) - observed)
    if missing:
        raise UnsafeInvocation(
            "materialized evidence is missing ledger paths: " + ", ".join(missing)
        )


def _commitment_payload(
    entries: list[dict[str, Any]],
) -> bytes:
    payload = [
        {
            "bytes": entry["bytes"],
            "path": entry["path"],
            "sha256": entry["sha256"],
        }
        for entry in sorted(entries, key=lambda item: str(item["path"]))
    ]
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _ledger_bundle_commitment(artifacts: tuple[EvidenceArtifact, ...]) -> str:
    return _sha256(_commitment_payload([item.metadata() for item in artifacts]))


def _materialized_manifest_at(root_descriptor: int) -> list[dict[str, Any]]:
    manifest: list[dict[str, Any]] = []

    def visit(descriptor: int, prefix: PurePosixPath) -> None:
        names = sorted(_list_bound_directory(descriptor, "evidence bundle"))
        for name in names:
            relative_path = prefix / name if prefix.parts else PurePosixPath(name)
            relative = _normalize_artifact_path(relative_path.as_posix())
            try:
                metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as exc:
                raise UnsafeInvocation(
                    f"cannot inspect evidence bundle path {relative}: {exc}"
                ) from exc
            if stat.S_ISDIR(metadata.st_mode):
                child = _open_directory_at(
                    descriptor,
                    name,
                    f"evidence bundle directory {relative}",
                )
                try:
                    visit(child, relative_path)
                finally:
                    os.close(child)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise UnsafeInvocation(
                    f"evidence bundle path is not regular: {relative}"
                )
            content = _read_regular_at_for_reconciliation(
                descriptor,
                name,
                metadata.st_size,
                f"evidence bundle artifact {relative}",
            )
            manifest.append(
                {"path": relative, "bytes": len(content), "sha256": _sha256(content)}
            )

    visit(root_descriptor, PurePosixPath())
    return manifest


def _materialized_manifest(root: Path) -> list[dict[str, Any]]:
    root_descriptor = _open_directory_descriptor(root, "evidence bundle root")
    try:
        return _materialized_manifest_at(root_descriptor)
    finally:
        os.close(root_descriptor)


def _materialized_bundle_commitment(root: Path) -> str:
    return _sha256(_commitment_payload(_materialized_manifest(root)))


def _materialized_bundle_commitment_at(root_descriptor: int) -> str:
    return _sha256(_commitment_payload(_materialized_manifest_at(root_descriptor)))


def _rename_noreplace_at(
    parent_descriptor: int,
    source_name: str,
    target_name: str,
    target_display: Path,
) -> None:
    if sys.platform != "linux":
        raise UnsafeInvocation("atomic no-replace evidence finalization requires Linux")
    _safe_basename(source_name, "staging")
    _safe_basename(target_name, "output")
    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(library, "renameat2", None)
    if renameat2 is None:
        raise UnsafeInvocation("atomic no-replace rename is unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        parent_descriptor,
        os.fsencode(source_name),
        parent_descriptor,
        os.fsencode(target_name),
        1,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise UnsafeInvocation(f"output directory already exists: {target_display}")
    raise UnsafeInvocation(
        f"cannot atomically finalize evidence directory: {os.strerror(error)}"
    )


def _finalize(
    writer: EvidenceWriter,
    output: Path,
    result: dict[str, Any],
    output_parent: BoundOutputParent,
) -> str:
    result["artifacts"] = writer.manifest()
    writer.write_text(
        "adoption-check.json",
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        origin="gnostoa-result",
    )
    manifest = writer.manifest()
    lines = [
        f"{item['sha256'].removeprefix('sha256:')}  {item['path']}" for item in manifest
    ]
    writer.write_text(
        "SHA256SUMS",
        "\n".join(lines) + "\n",
        origin="gnostoa-manifest",
    )
    artifacts = writer.artifacts()
    commitment = _ledger_bundle_commitment(artifacts)

    if output.parent != output_parent.path:
        raise UnsafeInvocation("bound output parent does not match final output")
    _assert_visible_output_parent(output_parent, "materialization")
    staging_name, staging_descriptor = _create_unique_directory_at(
        output_parent.descriptor,
        f".{output.name}.materializing-",
        "evidence materialization root",
    )
    published = False
    try:
        for artifact in artifacts:
            _write_artifact_at(staging_descriptor, artifact)

        _reconcile_materialized_at(staging_descriptor, artifacts)
        if _materialized_bundle_commitment_at(staging_descriptor) != commitment:
            raise UnsafeInvocation(
                "materialized evidence commitment differs from authoritative ledger"
            )
        _reconcile_materialized_at(staging_descriptor, artifacts)
        _assert_visible_output_parent(output_parent, "publication")
        _rename_noreplace_at(
            output_parent.descriptor,
            staging_name,
            output.name,
            output,
        )
        published = True
        try:
            _assert_visible_output_parent(output_parent, "post-publication read-back")
            published_descriptor = _open_directory_at(
                output_parent.descriptor,
                output.name,
                "published evidence bundle",
            )
            try:
                staging_identity = os.fstat(staging_descriptor)
                published_identity = os.fstat(published_descriptor)
                if (
                    staging_identity.st_dev,
                    staging_identity.st_ino,
                ) != (
                    published_identity.st_dev,
                    published_identity.st_ino,
                ):
                    raise UnsafeInvocation(
                        "published evidence does not match held staging identity"
                    )
                _reconcile_materialized_at(published_descriptor, artifacts)
                if (
                    _materialized_bundle_commitment_at(published_descriptor)
                    != commitment
                ):
                    raise UnsafeInvocation(
                        "published evidence commitment differs from authoritative ledger"
                    )
            finally:
                os.close(published_descriptor)
        except BaseException:
            published = False
            _remove_bound_directory_at(
                output_parent.descriptor,
                staging_descriptor,
                output.name,
                "published evidence bundle",
            )
            raise
        return commitment
    finally:
        if not published:
            try:
                _remove_bound_directory_at(
                    output_parent.descriptor,
                    staging_descriptor,
                    staging_name,
                    "evidence materialization root",
                )
            finally:
                os.close(staging_descriptor)
        else:
            os.close(staging_descriptor)


def _execute_bound(
    args: argparse.Namespace,
    paths: PathSet,
    output_parent: BoundOutputParent,
) -> tuple[int, Path, str]:
    writer = EvidenceWriter([])
    prerequisite_stage = "initial Git snapshot"
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    representation: dict[str, Any] | None = None
    representation_problems: list[str] = []
    identity: dict[str, Any] | None = None
    runtime_component: dict[str, Any] | None = None
    change_component: dict[str, Any] | None = None
    ci_component: dict[str, Any] | None = None
    bundle_component: dict[str, Any] | None = None
    context: dict[str, str] | None = None
    suite_records: list[dict[str, Any]] = []
    try:
        schema_bytes = _read_regular_bounded(
            paths.toolkit_source / "schemas" / "adoption-check.schema.json",
            1_048_576,
            "adoption-check result schema",
        )
        try:
            result_schema = adoption_assurance.decode_result_schema(schema_bytes)
        except adoption_assurance.AssuranceContractError as exc:
            raise UnsafeInvocation(str(exc)) from exc
        schema_artifact = writer.write_bytes(
            "contracts/adoption-check.schema.json",
            schema_bytes,
            origin="gnostoa-result-schema",
        )
        policy_artifact = writer.write_bytes(
            "contracts/gnostoa-review-ready-v1.json",
            adoption_assurance.policy_bytes(),
            origin="gnostoa-readiness-policy",
        )
        lock = load_yaml(paths.lock)
        verification = load_yaml(paths.verification)
        before = _git_snapshot(paths.project_root)
        candidate_patch = before.pop("_patch")
        writer.write_bytes(
            "candidate.patch",
            candidate_patch,
            origin="gnostoa-git-snapshot",
        )

        prerequisite_stage = "initial Git representation"
        representation, representation_problems = _git_representation(
            paths, verification
        )
        if not candidate_patch:
            representation_problems.append("staged adoption candidate is empty")

        identity, _ = _identity_result(
            paths,
            lock,
            args.execution_route,
            writer,
        )
        measurements = identity["measurements"]
        source_measured = measurements.get("toolkit_source", {}).get("result") != (
            "NOT OBSERVED"
        )
        runtime_measured = measurements.get("executing_runtime", {}).get("result") != (
            "NOT OBSERVED"
        )
        if source_measured and runtime_measured:
            runtime_component = _runtime_component(
                paths,
                measurements.get("executing_runtime", {}),
                writer,
            )
        else:
            runtime_component = writer.component(
                "runtime-lock",
                ["knowledge", "check-runtime", "--lock", str(paths.lock)],
                None,
                "BLOCKED",
                b"",
                b"",
                detail="toolkit source or executing runtime identity is not observed",
            )

        if runtime_component["result"] == "PASS":
            change_component = _run_tool_component(
                writer,
                "change-policy",
                [
                    "knowledge",
                    "check-change-policy",
                    "--policy",
                    str(paths.change_policy),
                ],
                check_change_policy.main,
                ["--policy", str(paths.change_policy)],
            )
            ci_component = _run_tool_component(
                writer,
                "ci-policy",
                [
                    "knowledge",
                    "check-ci-policy",
                    "--policy",
                    str(paths.ci_policy),
                    "--verification",
                    str(paths.verification),
                ],
                check_ci_policy.main,
                [
                    "--policy",
                    str(paths.ci_policy),
                    "--verification",
                    str(paths.verification),
                ],
            )
            bundle_component = _run_tool_component(
                writer,
                "bundle",
                [
                    "knowledge",
                    "validate",
                    "--profile",
                    str(paths.profile),
                    "--bundle",
                    str(paths.bundle),
                ],
                validate_bundle.main,
                [
                    "--project-root",
                    str(paths.project_root),
                    "--profile",
                    str(paths.profile),
                    "--bundle",
                    str(paths.bundle),
                ],
            )
        else:
            dependency_detail = "runtime-lock validation did not pass"
            change_component = writer.component(
                "change-policy",
                [
                    "knowledge",
                    "check-change-policy",
                    "--policy",
                    str(paths.change_policy),
                ],
                None,
                "NOT RUN",
                b"",
                b"",
                detail=dependency_detail,
            )
            ci_component = writer.component(
                "ci-policy",
                [
                    "knowledge",
                    "check-ci-policy",
                    "--policy",
                    str(paths.ci_policy),
                    "--verification",
                    str(paths.verification),
                ],
                None,
                "NOT RUN",
                b"",
                b"",
                detail=dependency_detail,
            )
            bundle_component = writer.component(
                "bundle",
                [
                    "knowledge",
                    "validate",
                    "--profile",
                    str(paths.profile),
                    "--bundle",
                    str(paths.bundle),
                ],
                None,
                "NOT RUN",
                b"",
                b"",
                detail=dependency_detail,
            )

        context = _context_components(
            paths,
            list(args.seed),
            args.depth,
            args.max_tokens,
            writer,
            bundle_ready=bundle_component["result"] == "PASS",
        )

        suite_records = []
        suites = verification.get("suites")
        if ci_component["result"] == "PASS" and isinstance(suites, dict):
            for suite in ("fast", "regression"):
                declaration = suites.get(suite)
                if isinstance(declaration, dict):
                    suite_records.append(
                        _suite_attempt(
                            suite=suite,
                            declaration=declaration,
                            verification=verification,
                            paths=paths,
                            writer=writer,
                            output_parent=output_parent,
                        )
                    )
                else:
                    suite_records.append(
                        writer.component(
                            f"project-{suite}",
                            [],
                            None,
                            "BLOCKED",
                            b"",
                            b"",
                            detail="required suite is absent",
                        )
                    )
        else:
            for suite in ("fast", "regression"):
                suite_records.append(
                    writer.component(
                        f"project-{suite}",
                        [],
                        None,
                        "BLOCKED",
                        b"",
                        b"",
                        detail="CI policy or verification manifest did not validate",
                    )
                )

        prerequisite_stage = "final Git snapshot"
        after = _git_snapshot(paths.project_root)
        after_patch = after.pop("_patch")
        representation_problems.extend(_snapshot_stability_problems(before, after))
        if candidate_patch != after_patch:
            if "staged candidate changed during adoption-check" not in (
                representation_problems
            ):
                representation_problems.append(
                    "staged candidate changed during adoption-check"
                )
        prerequisite_stage = "final Git representation"
        final_representation, final_problems = _git_representation(paths, verification)
        representation_problems.extend(final_problems)
        if representation != final_representation:
            representation_problems.append(
                "required Git representation changed during adoption-check"
            )

        git_state = {
            "before": before,
            "after": after,
            "representation": final_representation,
            "problems": sorted(set(representation_problems)),
        }
        writer.write_text(
            "git-state.json",
            json.dumps(git_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            origin="gnostoa-git-reconciliation",
        )

        result = _build_assurance_result(
            args=args,
            paths=paths,
            writer=writer,
            result_schema=result_schema,
            schema_artifact=schema_artifact,
            policy_artifact=policy_artifact,
            before=before,
            after=after,
            representation_problems=sorted(set(representation_problems)),
            identity=identity,
            runtime_component=runtime_component,
            change_component=change_component,
            ci_component=ci_component,
            bundle_component=bundle_component,
            context=context,
            suite_records=suite_records,
        )
        exit_code = int(result["exit_code"])
        commitment = _finalize(writer, paths.output, result, output_parent)
        return exit_code, paths.output, commitment
    except BlockedPrerequisite as exc:
        if before is None or (
            after is None and prerequisite_stage == "final Git snapshot"
        ):
            raise BlockedPrerequisite(f"{prerequisite_stage}: {exc}") from exc

        detail = f"{prerequisite_stage}: {exc}"
        writer.component(
            "git-prerequisite",
            [],
            None,
            "BLOCKED",
            b"",
            str(exc).encode("utf-8", errors="replace"),
            detail=detail,
        )

        if after is None:
            after = _git_snapshot(paths.project_root)
            after.pop("_patch")
        observed_stability_problems = [
            *representation_problems,
            *_snapshot_stability_problems(before, after),
        ]
        blocked_problems = sorted(set([*observed_stability_problems, detail]))

        if representation is None:
            representation = {
                "required_targets": [],
                "agents": {"head_blob": None, "index_blob": None},
                "submodule": None,
                "toolkit_source_mode": "NOT OBSERVED",
            }
        git_state = {
            "before": before,
            "after": after,
            "representation": representation,
            "problems": blocked_problems,
        }
        writer.write_text(
            "git-state.json",
            json.dumps(git_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            origin="gnostoa-git-reconciliation",
        )

        if identity is None:
            identity = {
                "result": "BLOCKED",
                "declarations": {},
                "measurements": {},
                "external_oci_digest": {
                    "result": (
                        "NOT OBSERVED"
                        if args.execution_route == "oci"
                        else "NOT APPLICABLE"
                    )
                },
                "failures": [],
                "blockers": [detail],
            }

        def not_run_component(name: str) -> dict[str, Any]:
            return writer.component(
                name,
                [],
                None,
                "NOT RUN",
                b"",
                b"",
                detail=f"not reached because {detail}",
            )

        if runtime_component is None:
            runtime_component = not_run_component("runtime-lock")
        if change_component is None:
            change_component = not_run_component("change-policy")
        if ci_component is None:
            ci_component = not_run_component("ci-policy")
        if bundle_component is None:
            bundle_component = not_run_component("bundle")
        if context is None:
            context = {
                "generation": "NOT RUN",
                "determinism": "NOT RUN",
                "retention": "NOT RUN",
            }
        if not suite_records:
            suite_records = [
                not_run_component("project-fast"),
                not_run_component("project-regression"),
            ]

        result = _build_assurance_result(
            args=args,
            paths=paths,
            writer=writer,
            result_schema=result_schema,
            schema_artifact=schema_artifact,
            policy_artifact=policy_artifact,
            before=before,
            after=after,
            representation_problems=blocked_problems,
            identity=identity,
            runtime_component=runtime_component,
            change_component=change_component,
            ci_component=ci_component,
            bundle_component=bundle_component,
            context=context,
            suite_records=suite_records,
            stability_outcome=("FAIL" if observed_stability_problems else "BLOCKED"),
        )
        commitment = _finalize(writer, paths.output, result, output_parent)
        return int(result["exit_code"]), paths.output, commitment


def _execute(args: argparse.Namespace, paths: PathSet) -> tuple[int, Path, str]:
    output_parent = _acquire_output_parent(paths.output)
    try:
        return _execute_bound(args, paths, output_parent)
    finally:
        os.close(output_parent.descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Produce bounded mechanical adoption evidence before accountable-owner review."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Project runtime observation:\n"
            "  Each validated project-suite command receives "
            "GNOSTOA_ADOPTION_OBSERVATION_PATH and\n"
            "  GNOSTOA_ADOPTION_INVOCATION_BINDING. The same project adapter may "
            "atomically publish\n"
            f"  one closed {OBSERVATION_SCHEMA} JSON sidecar without replacement.\n"
            "  Version 1 accepts a measured native executable plus dependency lock, "
            "or one\n"
            "  entered container bound to a platform manifest and configuration. "
            "Service and\n"
            "  composite routes are blocked. The sidecar is project-reported, not "
            "independent\n"
            "  attestation or semantic acceptance. See the existing-project adoption "
            "workflow.\n\n"
            "Evidence integrity:\n"
            "  Authoritative bytes are ledger-bound while suites run. After atomic "
            "bundle publication,\n"
            f"  stdout emits one {BUNDLE_COMMITMENT_SCHEMA} commitment for separate "
            "retention."
        ),
    )
    parser.add_argument(
        "--execution-route",
        choices=("native", "source-built", "oci"),
        required=True,
    )
    parser.add_argument("--seed", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=1600)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--documentation-root", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--change-policy", type=Path)
    parser.add_argument("--ci-policy", type=Path)
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--oci-digest-evidence", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.depth < 0 or args.max_tokens < 128:
        print(
            "ERROR: depth must be >= 0 and max-tokens must be >= 128",
            file=sys.stderr,
        )
        return 2
    try:
        paths = _derive_paths(args)
        code, output, commitment = _execute(args, paths)
    except BlockedPrerequisite as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 3
    except (
        AdoptionCheckError,
        KnowledgeFormatError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"EVIDENCE BUNDLE COMMITMENT: {BUNDLE_COMMITMENT_SCHEMA} {commitment}")
    readiness = {0: "READY", 1: "FAILED", 2: "ERROR", 3: "BLOCKED"}[code]
    print(f"REVIEW READINESS: {readiness}")
    print("SEMANTIC ADOPTION: NOT DETERMINED")
    print("OWNER DISPOSITION: REQUIRED")
    if code == 0:
        print(f"READY FOR ACCOUNTABLE-OWNER REVIEW: {output}")
    elif code == 1:
        print(f"FAIL: retained adoption evidence at {output}")
    elif code == 3:
        print(f"BLOCKED: retained adoption evidence at {output}")
    else:
        print(f"ERROR: retained adoption evidence at {output}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
