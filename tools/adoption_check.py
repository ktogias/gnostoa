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
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any

from . import (
    build_context_pack,
    check_change_policy,
    check_ci_policy,
    validate_bundle,
)
from .check_runtime_lock import check_runtime_lock, public_surface_digest
from .knowledge_common import KnowledgeFormatError, load_yaml
from .repository_scope import SOURCE_MANIFEST, RepositoryScopeError, candidate_paths

RESULT_SCHEMA = "gnostoa-adoption-check/v1"
OBSERVATION_SCHEMA = "gnostoa-project-runtime-observation/v1"
MAX_OBSERVATION_BYTES = 65_536
MAX_TEXT = 512
MAX_VERSION = 256
MAX_IDENTITIES = 16
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
    return {
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
        issues = check_runtime_lock(
            paths.lock,
            paths.project_root,
            revision if isinstance(revision, str) else "",
            "",
            runtime_root=_execution_root(),
        )
        for issue in issues:
            print(f"ERROR: {issue}", file=stdout)
        if issues:
            code = 1
        else:
            code = 0
            print(
                f"OK: toolkit source and runtime lock is valid ({paths.lock})",
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


def _discard_incoming(path: Path) -> None:
    """Remove one tool-owned incoming area without following a replacement link."""

    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError:
        return
    if stat.S_ISDIR(mode) and not stat.S_ISLNK(mode):
        shutil.rmtree(path, ignore_errors=True)
        return
    try:
        path.unlink()
    except OSError:
        pass


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
    exchange_root: Path | None = None
    exchange_descriptor: int | None = None
    incoming_descriptor: int | None = None
    observation_path: Path | None = None
    try:
        exchange_root = Path(
            tempfile.mkdtemp(
                prefix=f".gnostoa-adoption-{suite}-",
                dir=paths.output.parent,
            )
        )
        exchange_descriptor = _open_directory_descriptor(
            exchange_root, f"{suite} suite exchange"
        )
        os.mkdir("incoming", mode=0o700, dir_fd=exchange_descriptor)
        incoming_root = exchange_root / "incoming"
        incoming_descriptor = _open_directory_descriptor(
            incoming_root, f"{suite} runtime observation directory"
        )
        _require_absent_at(
            incoming_descriptor,
            "observation.json",
            f"{suite} runtime observation",
        )
        _validate_suite_exchange(exchange_descriptor, incoming_descriptor, suite)
        observation_path = incoming_root / "observation.json"
    except (OSError, ObservationBlocked) as exc:
        if incoming_descriptor is not None:
            os.close(incoming_descriptor)
            incoming_descriptor = None
        if exchange_descriptor is not None:
            os.close(exchange_descriptor)
            exchange_descriptor = None
        if exchange_root is not None:
            _discard_incoming(exchange_root)
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
        exchange_root is None
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
        if incoming_descriptor is not None:
            os.close(incoming_descriptor)
        if exchange_descriptor is not None:
            os.close(exchange_descriptor)
        _discard_incoming(exchange_root)


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
        ("documentation", paths.documentation_root, False),
        ("toolkit_source", paths.toolkit_source, False),
        ("executing_runtime", _execution_root(), True),
    )
    for name, root, running in identities:
        try:
            measurements[name] = _source_identity(root, running=running)
        except BlockedPrerequisite as exc:
            measurements[name] = {"root": str(root.resolve()), "result": "NOT OBSERVED"}
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


def _aggregate(values: list[str]) -> str:
    if any(value in {"FAIL", "ERROR"} for value in values):
        return "FAIL"
    if any(value in {"BLOCKED", "NOT RUN"} for value in values):
        return "BLOCKED"
    return "PASS"


def _project_suite_dimensions(records: list[dict[str, Any]]) -> dict[str, Any]:
    suites: dict[str, str] = {}
    observation_results: list[str] = []
    entry_results: list[str] = []
    route_results: list[str] = []
    for record in records:
        suite = record["name"].removeprefix("project-")
        result = str(record["result"])
        suites[suite] = result
        if "adapter_sha256" in record:
            entry_results.append("VALID")
        else:
            entry_results.append("ABSENT")
        if result == "PASS":
            route_results.append("ENTERED")
        elif result == "FAIL":
            route_results.append("FAIL")
        else:
            route_results.append("BLOCKED")
        observation = record.get("runtime_observation")
        if isinstance(observation, dict):
            observation_results.append(str(observation.get("result", "BLOCKED")))
        else:
            observation_results.append("BLOCKED")

    suite_aggregate = _aggregate(list(suites.values()))
    observation_aggregate = _aggregate(observation_results)
    authoritative = (
        "VALID"
        if entry_results and all(result == "VALID" for result in entry_results)
        else "ABSENT"
    )
    if any(result == "FAIL" for result in route_results):
        route = "FAIL"
    elif route_results and all(result == "ENTERED" for result in route_results):
        route = "ENTERED"
    else:
        route = "BLOCKED"
    project_result = _aggregate(
        [
            suite_aggregate,
            observation_aggregate,
            "PASS" if authoritative == "VALID" else "BLOCKED",
            (
                "PASS"
                if route == "ENTERED"
                else "FAIL"
                if route == "FAIL"
                else "BLOCKED"
            ),
        ]
    )
    return {
        "result": project_result,
        "suite_result": suite_aggregate,
        "suites": suites,
        "authoritative_entry": authoritative,
        "project_owned_route_entry": route,
        "project_runtime_observation": observation_aggregate,
        "toolkit_project_runtime_separation": (
            "PASS" if observation_aggregate == "PASS" else "BLOCKED"
        ),
    }


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
        expected = {artifact.path: artifact for artifact in artifacts}
        observed: set[str] = set()
        _reconcile_directory(root_descriptor, PurePosixPath(), expected, observed)
        missing = sorted(set(expected) - observed)
        if missing:
            raise UnsafeInvocation(
                "materialized evidence is missing ledger paths: " + ", ".join(missing)
            )
    finally:
        os.close(root_descriptor)


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


def _materialized_manifest(root: Path) -> list[dict[str, Any]]:
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

    root_descriptor = _open_directory_descriptor(root, "evidence bundle root")
    try:
        visit(root_descriptor, PurePosixPath())
    finally:
        os.close(root_descriptor)
    return manifest


def _materialized_bundle_commitment(root: Path) -> str:
    return _sha256(_commitment_payload(_materialized_manifest(root)))


def _rename_noreplace(source: Path, target: Path) -> None:
    if sys.platform != "linux":
        raise UnsafeInvocation("atomic no-replace evidence finalization requires Linux")
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
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(target),
        1,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise UnsafeInvocation(f"output directory already exists: {target}")
    raise UnsafeInvocation(
        f"cannot atomically finalize evidence directory: {os.strerror(error)}"
    )


def _finalize(
    writer: EvidenceWriter,
    output: Path,
    result: dict[str, Any],
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

    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.materializing-", dir=output.parent)
    )
    published = False
    try:
        root_descriptor = _open_directory_descriptor(
            staging, "evidence materialization root"
        )
        try:
            for artifact in artifacts:
                _write_artifact_at(root_descriptor, artifact)
        finally:
            os.close(root_descriptor)

        _reconcile_materialized(staging, artifacts)
        if _materialized_bundle_commitment(staging) != commitment:
            raise UnsafeInvocation(
                "materialized evidence commitment differs from authoritative ledger"
            )
        _reconcile_materialized(staging, artifacts)
        _rename_noreplace(staging, output)
        published = True
        return commitment
    finally:
        if not published:
            _discard_incoming(staging)


def _result_exit(
    components: list[dict[str, Any]],
    dimensions: dict[str, Any],
) -> int:
    component_results = [str(component.get("result")) for component in components]
    dimension_results: list[str] = []
    for value in dimensions.values():
        if isinstance(value, str):
            dimension_results.append(value)
        elif isinstance(value, dict) and isinstance(value.get("result"), str):
            dimension_results.append(value["result"])
    if "ERROR" in component_results or "ERROR" in dimension_results:
        return 2
    if "FAIL" in component_results or "FAIL" in dimension_results:
        return 1
    blocked_values = {"BLOCKED", "NOT RUN", "NOT OBSERVED", "ABSENT"}
    if any(value in blocked_values for value in component_results + dimension_results):
        return 3
    return 0


def _blocked_prerequisite_result(
    args: argparse.Namespace,
    paths: PathSet,
    writer: EvidenceWriter,
    *,
    stage: str,
    error: BlockedPrerequisite,
    completed_dimensions: dict[str, Any] | None,
) -> dict[str, Any]:
    detail = f"{stage}: {error}"
    writer.component(
        "git-prerequisite",
        [],
        None,
        "BLOCKED",
        b"",
        str(error).encode("utf-8", errors="replace"),
        detail=detail,
    )
    if completed_dimensions is None:
        not_run = {
            "result": "NOT RUN",
            "detail": f"not reached because {detail}",
        }
        dimensions: dict[str, Any] = {
            "environment": {"result": "BLOCKED", "detail": detail},
            "documentation_toolkit_execution_coherence": dict(not_run),
            "external_oci_digest": {
                "result": (
                    "NOT OBSERVED"
                    if args.execution_route == "oci"
                    else "NOT APPLICABLE"
                )
            },
            "runtime_lock_validation": dict(not_run),
            "change_policy": dict(not_run),
            "ci_policy": dict(not_run),
            "profile_and_bundle": dict(not_run),
            "bounded_context": dict(not_run),
            "project_suites": dict(not_run),
            "git_representability": {"result": "BLOCKED", "detail": detail},
            "evidence_bundle": {"result": "PASS"},
            "semantic_owner_review": "REQUIRED",
            "durable_adoption": "NOT DETERMINED",
        }
    else:
        dimensions = dict(completed_dimensions)
        dimensions["git_representability"] = {
            "result": "BLOCKED",
            "detail": detail,
        }
    return {
        "schema": RESULT_SCHEMA,
        "outcome": "BLOCKED",
        "exit_code": 3,
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
        "components": writer.components,
        "dimensions": dimensions,
        "authority": {
            "mechanical_result_only": True,
            "semantic_owner_review": "REQUIRED",
            "durable_adoption": "NOT DETERMINED",
            "project_runtime_observation": (
                "project-reported, not independently attested"
            ),
        },
    }


def _execute(args: argparse.Namespace, paths: PathSet) -> tuple[int, Path, str]:
    writer = EvidenceWriter([])
    prerequisite_stage = "initial Git snapshot"
    completed_dimensions: dict[str, Any] | None = None
    try:
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

        identity, identity_state = _identity_result(
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

        suite_records: list[dict[str, Any]] = []
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

        project_suites = _project_suite_dimensions(suite_records)
        suite_availability = {
            record["name"].removeprefix("project-"): (
                "BLOCKED" if record["result"] == "BLOCKED" else "PASS"
            )
            for record in suite_records
        }
        if identity_state == "FAIL":
            identity["result"] = "FAIL"
        completed_dimensions = {
            "environment": {
                "result": (
                    "BLOCKED" if "BLOCKED" in suite_availability.values() else "PASS"
                ),
                "required_suite_availability": suite_availability,
            },
            "documentation_toolkit_execution_coherence": identity,
            "external_oci_digest": identity["external_oci_digest"],
            "runtime_lock_validation": {"result": runtime_component["result"]},
            "change_policy": {"result": change_component["result"]},
            "ci_policy": {"result": ci_component["result"]},
            "profile_and_bundle": {"result": bundle_component["result"]},
            "bounded_context": {
                "result": _aggregate(
                    [
                        context["generation"],
                        context["determinism"],
                        context["retention"],
                    ]
                ),
                **context,
            },
            "project_suites": project_suites,
            "git_representability": {
                "result": "NOT RUN",
                "detail": "final Git postcondition has not been acquired",
            },
            "evidence_bundle": {"result": "PASS"},
            "semantic_owner_review": "REQUIRED",
            "durable_adoption": "NOT DETERMINED",
        }

        prerequisite_stage = "final Git snapshot"
        after = _git_snapshot(paths.project_root)
        after_patch = after.pop("_patch")
        if before["head"] != after["head"] or before["tree"] != after["tree"]:
            representation_problems.append(
                "Git HEAD or tree changed during adoption-check"
            )
        if before["status_sha256"] != after["status_sha256"]:
            representation_problems.append("Git status changed during adoption-check")
        if candidate_patch != after_patch:
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

        dimensions = dict(completed_dimensions)
        dimensions["git_representability"] = {
            "result": "FAIL" if representation_problems else "PASS",
            "problems": sorted(set(representation_problems)),
        }

        exit_code = _result_exit(writer.components, dimensions)
        if exit_code == 0:
            outcome = "READY FOR ACCOUNTABLE-OWNER REVIEW"
        elif exit_code == 1:
            outcome = "MECHANICAL CHECK FAILED"
        elif exit_code == 3:
            outcome = "BLOCKED"
        else:
            outcome = "INVALID OR INTERNAL ERROR"
        result: dict[str, Any] = {
            "schema": RESULT_SCHEMA,
            "outcome": outcome,
            "exit_code": exit_code,
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
            "components": writer.components,
            "dimensions": dimensions,
            "authority": {
                "mechanical_result_only": True,
                "semantic_owner_review": "REQUIRED",
                "durable_adoption": "NOT DETERMINED",
                "project_runtime_observation": "project-reported, not independently attested",
            },
        }
        commitment = _finalize(writer, paths.output, result)
        return exit_code, paths.output, commitment
    except BlockedPrerequisite as exc:
        result = _blocked_prerequisite_result(
            args,
            paths,
            writer,
            stage=prerequisite_stage,
            error=exc,
            completed_dimensions=completed_dimensions,
        )
        commitment = _finalize(writer, paths.output, result)
        return 3, paths.output, commitment


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
