from __future__ import annotations

import json
import math
import os
import re
import selectors
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

from .review_model import canonical_json

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_RESOURCE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")
_DIGEST_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+"
    r"@sha256:[0-9a-f]{64}$"
)
_DOCKER_TIMEOUT_SECONDS = 90
_DOCKER_CLEANUP_TIMEOUT_SECONDS = 10
_DOCKER_CLEANUP_ATTEMPTS = 3
_MAX_CLEANUP_DIAGNOSTIC_BYTES = 4_096
_ABSENT_CONTAINER_DIAGNOSTIC = "no such container"
_PROCESS_REAP_TIMEOUT_SECONDS = 5
_MAX_RUNTIME_INPUT_BYTES = 4_194_304
_MAX_RUNTIME_OUTPUT_BYTES = 2_097_152
_READ_CHUNK_BYTES = 65_536
_WRITE_CHUNK_BYTES = 65_536
_DOCKER_RUN_FLAG_OPTIONS = frozenset({"--interactive", "--read-only", "--rm", "-i"})
_DOCKER_RUN_VALUE_OPTIONS = frozenset(
    {
        "--cap-drop",
        "--entrypoint",
        "--log-driver",
        "--mount",
        "--network",
        "--pull",
        "--security-opt",
        "--tmpfs",
    }
)
_DOCKER_RUN_IDENTITY_OPTIONS = frozenset({"--cidfile", "--name"})

_CONTAINER_PAYLOAD_BRIDGE = f"""
import json
import os
import sys

limit = {_MAX_RUNTIME_INPUT_BYTES}
raw = bytearray()
while len(raw) <= limit:
    remaining = limit + 1 - len(raw)
    chunk = sys.stdin.buffer.read(min(65_536, remaining))
    if not chunk:
        break
    raw.extend(chunk)
if len(raw) > limit:
    raise SystemExit("protected payload envelope exceeds the bounded size")
try:
    envelope = json.loads(raw.decode("utf-8"))
except (UnicodeDecodeError, json.JSONDecodeError):
    raise SystemExit("protected payload envelope is invalid") from None
if not isinstance(envelope, dict) or set(envelope) != {{"input", "policy"}}:
    raise SystemExit("protected payload envelope has the wrong shape")
if not isinstance(envelope["input"], dict) or not isinstance(envelope["policy"], dict):
    raise SystemExit("protected payload envelope members must be objects")

os.umask(0o077)
paths = {{
    "input": "/tmp/gnostoa-review-input.json",
    "policy": "/tmp/gnostoa-review-policy.json",
}}
for name, path in paths.items():
    data = json.dumps(
        envelope[name],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8") + b"\\n"
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o400,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)

os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "tools.cli",
        "review-check",
        "--input",
        paths["input"],
        "--policy",
        paths["policy"],
    ],
)
""".strip()


class ProtectedJudgeUnavailable(RuntimeError):
    """Raised when the exact prior-integrated OCI judge cannot be used safely."""


@dataclass(frozen=True)
class _ContainerRunIdentity:
    name: str
    cidfile: Path
    executable: str | None = None


@dataclass(frozen=True)
class _AbortOutcome:
    """Bounded secondary context for one abort, plus its cleanup verdict.

    ``cleanup_confirmed`` reports container removal only. A client reap failure
    is reported in ``detail`` without withdrawing that confirmation, so a reaped
    identity is still discarded and no recovery identity is advertised for an
    already removed container.
    """

    detail: str | None
    cleanup_confirmed: bool


def _docker_executable() -> str:
    executable = shutil.which("docker", path=os.defpath)
    if executable is None:
        raise ProtectedJudgeUnavailable("Docker CLI is unavailable")
    return executable


def _docker_environment(config_dir: Path) -> dict[str, str]:
    # Do not inherit caller-controlled daemon/context/config/credential selectors.
    # The authority-bound bootstrap image is public and digest-pinned, so the
    # protected route needs no caller Docker credentials or configuration.
    return {
        "DOCKER_CONFIG": str(config_dir),
        "HOME": str(config_dir),
        "LC_ALL": "C",
        "PATH": os.defpath,
    }


def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=_PROCESS_REAP_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedJudgeUnavailable(
            "protected Docker client reap could not be confirmed within the bound"
        ) from exc


def _validate_docker_run_options(arguments: list[str]) -> None:
    index = 1
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            if index + 1 >= len(arguments):
                raise ProtectedJudgeUnavailable(
                    "protected Docker run has no image argument"
                )
            return
        option, separator, value = token.partition("=")
        if option in _DOCKER_RUN_IDENTITY_OPTIONS:
            raise ProtectedJudgeUnavailable(
                "protected Docker run contains a caller-owned cleanup identity option"
            )
        if token in _DOCKER_RUN_FLAG_OPTIONS:
            index += 1
            continue
        if option in _DOCKER_RUN_VALUE_OPTIONS:
            if separator:
                if not value:
                    raise ProtectedJudgeUnavailable(
                        "protected Docker run option has no value"
                    )
                index += 1
                continue
            if index + 1 >= len(arguments) or not arguments[index + 1]:
                raise ProtectedJudgeUnavailable(
                    "protected Docker run option has no value"
                )
            index += 2
            continue
        if token.startswith("-"):
            raise ProtectedJudgeUnavailable(
                "protected Docker run contains an unsupported option"
            )
        return
    raise ProtectedJudgeUnavailable("protected Docker run has no image argument")


def _run_identity(
    arguments: list[str],
    config_dir: Path,
    *,
    executable: str | None = None,
    requested_name: str | None = None,
) -> _ContainerRunIdentity | None:
    if not arguments or arguments[0] != "run":
        if requested_name is not None:
            raise ProtectedJudgeUnavailable(
                "a protected Docker run name is valid only for a run command"
            )
        return None
    _validate_docker_run_options(arguments)
    if requested_name is not None and _RESOURCE_NAME.fullmatch(requested_name) is None:
        raise ProtectedJudgeUnavailable("protected Docker run name is invalid")
    nonce = f"{os.getpid()}-{time.monotonic_ns()}"
    name = requested_name or f"gnostoa-protected-{nonce}"
    return _ContainerRunIdentity(
        name=name,
        cidfile=config_dir / f"protected-run-{nonce}.cid",
        executable=executable,
    )


def _bounded_diagnostic(raw: bytes | None) -> str:
    """Return one bounded, single-line rendering of a cleanup diagnostic."""

    if not raw:
        return ""
    decoded = raw[:_MAX_CLEANUP_DIAGNOSTIC_BYTES].decode("utf-8", errors="replace")
    return " ".join(decoded.split())


def _discard_cidfile(identity: _ContainerRunIdentity | None) -> str | None:
    """Remove the predeclared cleanup identity file without ever raising.

    Discarding the identity file is subordinate to whatever failure is being
    reported, so a filesystem problem here is returned as bounded secondary
    context instead of replacing the caller's primary diagnostic.
    """

    if identity is None:
        return None
    try:
        identity.cidfile.unlink(missing_ok=True)
    except OSError as exc:
        return f"protected Docker cleanup identity file could not be removed: {exc}"
    return None


def _cleanup_diagnostic(
    command: list[str],
    *,
    config_dir: Path,
) -> tuple[int | None, str]:
    """Run one cleanup command, reading only a bounded stderr prefix.

    The child is stopped as soon as the diagnostic bound is reached, so a noisy
    or malfunctioning cleanup client cannot buffer an unbounded stream. Returns
    the exit status, or ``None`` when the command could not be run or did not
    complete, together with the bounded diagnostic.
    """

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=_docker_environment(config_dir),
        )
    except OSError as exc:
        return None, str(exc) or exc.__class__.__name__

    diagnostic = bytearray()
    overflowed = False
    issue = ""
    returncode: int | None = None
    stream = process.stderr
    selector: selectors.BaseSelector | None = None
    deadline = time.monotonic() + _DOCKER_CLEANUP_TIMEOUT_SECONDS
    try:
        if stream is None:
            raise OSError("protected Docker cleanup stderr is unavailable")
        selector = selectors.DefaultSelector()
        selector.register(stream, selectors.EVENT_READ)
        while selector.get_map() and not overflowed:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise subprocess.TimeoutExpired(
                    command,
                    _DOCKER_CLEANUP_TIMEOUT_SECONDS,
                )
            wanted = _MAX_CLEANUP_DIAGNOSTIC_BYTES + 1 - len(diagnostic)
            chunk = os.read(
                stream.fileno(),
                max(1, min(_READ_CHUNK_BYTES, wanted)),
            )
            if not chunk:
                selector.unregister(stream)
                continue
            diagnostic.extend(chunk)
            overflowed = len(diagnostic) > _MAX_CLEANUP_DIAGNOSTIC_BYTES
        if overflowed:
            issue = "protected Docker cleanup diagnostic exceeds the bounded size"
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(
                    command,
                    _DOCKER_CLEANUP_TIMEOUT_SECONDS,
                )
            returncode = process.wait(timeout=remaining)
    except (OSError, subprocess.TimeoutExpired) as exc:
        issue = str(exc) or exc.__class__.__name__
    finally:
        if selector is not None:
            selector.close()
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=_PROCESS_REAP_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if stream is not None:
            stream.close()

    detail = _bounded_diagnostic(bytes(diagnostic))
    if returncode is None:
        return None, issue or detail or "protected Docker cleanup did not complete"
    return returncode, detail


def _cleanup_container(
    identity: _ContainerRunIdentity | None,
    config_dir: Path,
) -> str | None:
    """Reconcile the predeclared container identity.

    Returns ``None`` when cleanup is confirmed, which includes the bounded
    already-absent response a container removed by ``--rm`` produces, and a
    bounded issue description for every other outcome. Cleanup never raises, so
    it can never replace the caller's primary execution failure.
    """

    if identity is None:
        return None
    cleanup_target = identity.name
    try:
        container_id = identity.cidfile.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        pass
    else:
        if _CONTAINER_ID.fullmatch(container_id) is not None:
            cleanup_target = container_id

    try:
        executable = identity.executable or _docker_executable()
    except ProtectedJudgeUnavailable as exc:
        return (
            "protected Docker container cleanup could not resolve the retained "
            f"executable: {exc}; recovery identity: {identity.name}"
        )

    last_issue = "no cleanup attempt completed"
    for _attempt in range(_DOCKER_CLEANUP_ATTEMPTS):
        returncode, detail = _cleanup_diagnostic(
            [executable, "rm", "-f", cleanup_target],
            config_dir=config_dir,
        )
        if returncode == 0:
            return None
        if returncode is not None and _ABSENT_CONTAINER_DIAGNOSTIC in detail.casefold():
            return None
        if returncode is not None:
            last_issue = detail or f"status {returncode}"
        else:
            last_issue = detail or "protected Docker cleanup did not complete"
    return (
        f"protected Docker container cleanup failed after retries: {last_issue}; "
        f"recovery identity: {identity.name}"
    )


def _abort_docker_run(
    process: subprocess.Popen[bytes],
    identity: _ContainerRunIdentity | None,
    config_dir: Path,
) -> _AbortOutcome:
    """Abort one protected Docker run and report bounded secondary context.

    The abort itself never raises: reap and cleanup problems are returned so the
    caller can keep the triggering timeout, bounded-size or I/O failure as the
    primary diagnostic and attach this detail as secondary context. Container
    cleanup is reported separately from reaping, because only an unconfirmed
    removal leaves a container behind to recover.
    """

    issues: list[str] = []
    try:
        _kill_and_reap(process)
    except ProtectedJudgeUnavailable as exc:
        issues.append(str(exc))
    cleanup_issue = _cleanup_container(identity, config_dir)
    if cleanup_issue is not None:
        issues.append(cleanup_issue)
    return _AbortOutcome(
        detail="; ".join(issues) if issues else None,
        cleanup_confirmed=cleanup_issue is None,
    )


def _with_secondary(primary: str, secondary: str | None) -> str:
    """Keep the primary failure first and append bounded secondary context."""

    return primary if secondary is None else f"{primary}; {secondary}"


def _joined_details(*details: str | None) -> str | None:
    """Join bounded secondary details, or return ``None`` when there are none."""

    present = [detail for detail in details if detail]
    return "; ".join(present) if present else None


def _close_pipes(process: subprocess.Popen[bytes]) -> None:
    """Release every pipe the run did open.

    A partial pipe set still holds descriptors, and abandoning them leaks one
    per failed run. Closing runs after a primary failure is already known, so a
    close problem is never allowed to surface in its place.
    """

    for handle in (process.stdin, process.stdout, process.stderr):
        if handle is None:
            continue
        try:
            handle.close()
        except OSError:
            continue


def _abort_and_discard(
    process: subprocess.Popen[bytes],
    identity: _ContainerRunIdentity | None,
    config_dir: Path,
) -> str | None:
    """Abort one run and discard its cleanup identity, reporting both problems.

    The identity file is discarded only once container cleanup is confirmed, so
    an unconfirmed cleanup still leaves the recovery identity behind. Every
    problem observed here is bounded secondary context for the caller's primary
    failure and is never raised.
    """

    outcome = _abort_docker_run(process, identity, config_dir)
    discard_detail = _discard_cidfile(identity) if outcome.cleanup_confirmed else None
    return _joined_details(outcome.detail, discard_detail)


def _run_docker(
    arguments: list[str],
    *,
    config_dir: Path,
    timeout: int = _DOCKER_TIMEOUT_SECONDS,
    input_bytes: bytes | None = None,
    run_name: str | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if input_bytes is not None and len(input_bytes) > _MAX_RUNTIME_INPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected Docker input exceeds the bounded size"
        )
    docker_executable = _docker_executable()
    identity = _run_identity(
        arguments,
        config_dir,
        executable=docker_executable,
        requested_name=run_name,
    )
    docker_arguments = arguments
    if identity is not None:
        docker_arguments = [
            "run",
            "--name",
            identity.name,
            "--cidfile",
            str(identity.cidfile),
            *arguments[1:],
        ]
    command = [docker_executable, *docker_arguments]
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_docker_environment(config_dir),
        )
    except OSError as exc:
        raise ProtectedJudgeUnavailable(
            f"protected Docker execution failed: {exc}"
        ) from exc

    cleanup_attempted = False
    if (
        process.stdout is None
        or process.stderr is None
        or (input_bytes is not None and process.stdin is None)
    ):
        cleanup_attempted = True
        detail = _abort_and_discard(process, identity, config_dir)
        _close_pipes(process)
        raise ProtectedJudgeUnavailable(
            _with_secondary(
                "protected Docker output pipes are unavailable",
                detail,
            )
        )

    outputs = {
        "stdout": bytearray(),
        "stderr": bytearray(),
    }
    selector: selectors.BaseSelector | None = None
    input_view: memoryview | None = None
    input_offset = 0
    deadline = time.monotonic() + timeout

    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        if input_bytes is not None:
            assert process.stdin is not None
            if input_bytes:
                input_view = memoryview(input_bytes)
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            else:
                process.stdin.close()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            events = selector.select(remaining)
            if not events:
                raise subprocess.TimeoutExpired(command, timeout)
            for key, _ in events:
                label = str(key.data)
                if label == "stdin":
                    assert input_view is not None
                    try:
                        written = os.write(
                            key.fd,
                            input_view[
                                input_offset : input_offset + _WRITE_CHUNK_BYTES
                            ],
                        )
                    except BrokenPipeError:
                        written = 0
                    if written > 0:
                        input_offset += written
                    if written == 0 or input_offset == len(input_view):
                        selector.unregister(key.fileobj)
                        assert process.stdin is not None
                        process.stdin.close()
                    continue
                buffer = outputs[label]
                remaining_bound = _MAX_RUNTIME_OUTPUT_BYTES + 1 - len(buffer)
                read_size = min(_READ_CHUNK_BYTES, max(1, remaining_bound))
                chunk = os.read(key.fd, read_size)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer.extend(chunk)
                if len(buffer) > _MAX_RUNTIME_OUTPUT_BYTES:
                    cleanup_attempted = True
                    raise ProtectedJudgeUnavailable(
                        _with_secondary(
                            f"protected Docker {label} exceeds the bounded size",
                            _abort_and_discard(process, identity, config_dir),
                        )
                    )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        cleanup_attempted = True
        raise ProtectedJudgeUnavailable(
            _with_secondary(
                f"protected Docker execution failed: {exc}",
                _abort_and_discard(process, identity, config_dir),
            )
        ) from exc
    except OSError as exc:
        cleanup_attempted = True
        raise ProtectedJudgeUnavailable(
            _with_secondary(
                f"protected Docker execution failed: {exc}",
                _abort_and_discard(process, identity, config_dir),
            )
        ) from exc
    finally:
        if selector is not None:
            selector.close()
        process.stdout.close()
        process.stderr.close()
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if input_view is not None:
            input_view.release()
        if identity is not None and not cleanup_attempted:
            # The run completed, so there is no primary failure to attach a
            # discard problem to; every abort path reports its own.
            _discard_cidfile(identity)

    return subprocess.CompletedProcess(
        command,
        returncode,
        bytes(outputs["stdout"]),
        bytes(outputs["stderr"]),
    )


def _checked_output(
    arguments: list[str],
    *,
    config_dir: Path,
    description: str,
    timeout: int = _DOCKER_TIMEOUT_SECONDS,
) -> bytes:
    result = _run_docker(arguments, config_dir=config_dir, timeout=timeout)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ProtectedJudgeUnavailable(detail or description)
    return result.stdout


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtectedJudgeUnavailable(
                f"prior-integrated judge result repeats field {key!r}"
            )
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise ProtectedJudgeUnavailable(
        f"prior-integrated judge result contains non-finite JSON number {value!r}"
    )


def _parse_finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtectedJudgeUnavailable(
            f"prior-integrated judge result contains non-finite JSON number {value!r}"
        )
    return parsed


def _decode_result(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object_without_duplicate_fields,
            parse_constant=_reject_non_finite_constant,
            parse_float=_parse_finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtectedJudgeUnavailable(
            f"prior-integrated judge returned invalid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ProtectedJudgeUnavailable(
            "prior-integrated judge result must be an object"
        )
    return value


def _security_arguments() -> list[str]:
    return [
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=16m",
    ]


def run_prior_integrated_judge(
    *,
    image: str,
    input_document: dict[str, Any],
    policy_document: dict[str, Any],
    expected_revision: str,
    expected_surface_digest: str,
) -> tuple[int, dict[str, Any]]:
    """Execute the exact protected authority-bound OCI(P2a) semantic judge.

    The image, revision and public-surface digest come from protected-main
    authority. Production exposes no repository, image, Docker context, daemon,
    credential, policy or runtime selector. The one network-capable Docker action
    is anonymous acquisition of the immutable digest; judge execution itself is
    network-none and receives one bounded stdin envelope. The compatibility files
    required by the immutable judge exist only in the container's bounded tmpfs.
    """

    if _DIGEST_IMAGE.fullmatch(image) is None:
        raise ProtectedJudgeUnavailable("protected judge image is not digest-pinned")
    if _SHA40.fullmatch(expected_revision) is None:
        raise ProtectedJudgeUnavailable(
            "protected judge revision is not an exact Git commit"
        )
    if _SHA256.fullmatch(expected_surface_digest) is None:
        raise ProtectedJudgeUnavailable(
            "protected judge public-surface digest is invalid"
        )

    envelope = (
        canonical_json({"input": input_document, "policy": policy_document}) + "\n"
    ).encode("utf-8")
    if len(envelope) > _MAX_RUNTIME_INPUT_BYTES:
        raise ProtectedJudgeUnavailable(
            "protected Docker input exceeds the bounded size"
        )

    # Use a fixed system temporary root instead of caller-controlled TMPDIR so the
    # bind-mount grammar cannot be redirected through a caller-selected path.
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-r2a-judge-", dir="/tmp"
    ) as directory:
        root = Path(directory)
        config_dir = root / "docker-config"
        config_dir.mkdir(mode=0o700)

        _checked_output(
            ["pull", image],
            config_dir=config_dir,
            description="cannot reacquire protected prior-integrated judge image",
        )

        repo_digests_raw = _checked_output(
            ["image", "inspect", "--format", "{{json .RepoDigests}}", image],
            config_dir=config_dir,
            description="cannot inspect protected prior-integrated judge repo digests",
        )
        try:
            repo_digests = json.loads(repo_digests_raw.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtectedJudgeUnavailable(
                "protected judge repo-digest observation is malformed"
            ) from exc
        if not isinstance(repo_digests, list) or image not in repo_digests:
            raise ProtectedJudgeUnavailable(
                "protected judge does not report the authority-bound OCI digest"
            )

        image_id = (
            _checked_output(
                ["image", "inspect", "--format", "{{.Id}}", image],
                config_dir=config_dir,
                description="cannot inspect protected prior-integrated judge image id",
            )
            .decode("ascii", errors="strict")
            .strip()
        )
        if _IMAGE_ID.fullmatch(image_id) is None:
            raise ProtectedJudgeUnavailable(
                "protected judge did not resolve to an immutable image id"
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
                description="cannot inspect protected prior-integrated judge image",
            )
            .decode("utf-8", errors="strict")
            .strip()
        )
        parts = observed.split("|")
        if parts != ["linux", "amd64", "kit", expected_revision]:
            raise ProtectedJudgeUnavailable(
                "protected judge runtime identity does not match the authority binding"
            )

        surface = (
            _checked_output(
                [
                    "run",
                    "--rm",
                    "--pull=never",
                    *_security_arguments(),
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
                description="cannot measure protected judge public surface",
            )
            .decode("ascii", errors="strict")
            .strip()
        )
        if surface != expected_surface_digest:
            raise ProtectedJudgeUnavailable(
                "protected judge public surface does not match the authority binding"
            )

        result = _run_docker(
            [
                "run",
                "--rm",
                "--log-driver=none",
                "--pull=never",
                "-i",
                *_security_arguments(),
                "--entrypoint",
                "python",
                image,
                "-c",
                _CONTAINER_PAYLOAD_BRIDGE,
            ],
            config_dir=config_dir,
            input_bytes=envelope,
        )
        payload = _decode_result(result.stdout)
        return result.returncode, payload
