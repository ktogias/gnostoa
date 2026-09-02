from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

PROFILE_SCHEMA = "gnostoa-experiment-runner-profile/v1"
VALIDATION_SCHEMA = "gnostoa-experiment-runner-validation/v1"
PROBE_SCHEMA = "gnostoa-experiment-runner-probe/v1"
SMOKE_SCHEMA = "gnostoa-experiment-runner-smoke/v1"
ATTEST_SCHEMA = "gnostoa-derived-artifact-identity/v1"
SIZE_SCHEMA = "gnostoa-path-size-check/v1"
RUN_SCHEMA = "gnostoa-experiment-runner-result/v1"

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_IMMUTABLE_IMAGE_RE = re.compile(r"^(?:sha256:[a-f0-9]{64}|.+@sha256:[a-f0-9]{64})$")
_MAX_RELAY_HEADER = 16 * 1024
_CHUNK_SIZE = 1024 * 1024


class RunnerError(RuntimeError):
    """Raised when a runner operation cannot satisfy its declared contract."""


@dataclass(frozen=True)
class ProbeResult:
    status: str
    backend: str | None
    reasons: list[str]


Handler = Callable[[argparse.Namespace], int]


def emit(payload: Mapping[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


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
    resolved: dict[str, list[Path]] = {}
    for kind, value in all_named:
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
        if not input_identities:
            reasons.append("input-identities-required-for-run")
        reasons.extend(validate_executor(profile))
        runtime = profile.get("runtime")
        if not isinstance(runtime, dict):
            reasons.append("runtime-must-be-a-mapping")
        else:
            runtime_mapping = cast(dict[str, object], runtime)
            image = runtime_mapping.get("image")
            if not isinstance(image, str) or not _IMMUTABLE_IMAGE_RE.fullmatch(
                cast(str, image)
            ):
                reasons.append("runtime-image-must-be-immutable-digest")
            relay_image = runtime_mapping.get("relay_image")
            if (
                isinstance(network, dict)
                and cast(dict[str, object], network).get("mode") == "restricted"
                and (
                    not isinstance(relay_image, str)
                    or not _IMMUTABLE_IMAGE_RE.fullmatch(cast(str, relay_image))
                )
            ):
                reasons.append("relay-image-must-be-immutable-digest")
    return sorted(set(reasons))


def probe_backend(backend: str, *, image: str | None) -> ProbeResult:
    if backend not in {"auto", "oci", "bwrap"}:
        return ProbeResult("BLOCKED", None, ["unsupported-backend"])

    oci_reasons: list[str] = []
    if backend in {"auto", "oci"}:
        docker = shutil.which("docker")
        if docker is None:
            oci_reasons.append("docker-cli-unavailable")
        else:
            try:
                info = subprocess.run(
                    [docker, "info", "--format", "{{.ServerVersion}}"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except subprocess.TimeoutExpired:
                oci_reasons.append("docker-daemon-timeout")
            else:
                if info.returncode != 0:
                    oci_reasons.append("docker-daemon-unavailable")
                elif image is None:
                    oci_reasons.append("oci-image-not-bound")
                else:
                    try:
                        inspect = subprocess.run(
                            [docker, "image", "inspect", image],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=10,
                        )
                    except subprocess.TimeoutExpired:
                        oci_reasons.append("oci-image-inspect-timeout")
                    else:
                        if inspect.returncode == 0:
                            return ProbeResult("AVAILABLE", "oci", [])
                        oci_reasons.append("oci-image-unavailable")
        if backend == "oci":
            return ProbeResult("BLOCKED", None, oci_reasons)

    if backend in {"auto", "bwrap"}:
        bwrap = shutil.which("bwrap")
        bwrap_reasons = (
            ["bwrap-cli-unavailable"]
            if bwrap is None
            else ["bwrap-backend-not-qualified"]
        )
        return ProbeResult("BLOCKED", None, [*oci_reasons, *bwrap_reasons])

    return ProbeResult("BLOCKED", None, ["no-qualified-backend"])


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


def log_relay(event: str, **fields: object) -> None:
    payload: dict[str, object] = {"event": event, **fields}
    print(json.dumps(payload, sort_keys=True), flush=True)


def recv_header(client: socket.socket) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = client.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > _MAX_RELAY_HEADER:
            raise RunnerError("relay-header-too-large")
    return bytes(data)


def relay_one_way(source: socket.socket, destination: socket.socket) -> None:
    try:
        while True:
            data = source.recv(64 * 1024)
            if not data:
                break
            destination.sendall(data)
    except OSError:
        pass
    finally:
        try:
            destination.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def handle_relay_client(client: socket.socket, allow: frozenset[str]) -> None:
    peer = repr(client.getpeername())
    target = ""
    try:
        client.settimeout(20)
        header = recv_header(client)
        first_line = header.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        parts = first_line.split()
        if len(parts) != 3 or parts[0] != "CONNECT":
            client.sendall(
                b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n"
            )
            log_relay("REFUSED", peer=peer, reason="connect-only")
            return
        target = parts[1]
        if target not in allow:
            client.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            log_relay("REFUSED", peer=peer, target=target, reason="not-allowlisted")
            return
        host, port = split_target(target)
        upstream = socket.create_connection((host, port), timeout=20)
        with upstream:
            client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            log_relay("ADMITTED", peer=peer, target=target)
            client.settimeout(None)
            upstream.settimeout(None)
            outgoing = threading.Thread(
                target=relay_one_way,
                args=(client, upstream),
                daemon=True,
            )
            incoming = threading.Thread(
                target=relay_one_way,
                args=(upstream, client),
                daemon=True,
            )
            outgoing.start()
            incoming.start()
            outgoing.join()
            incoming.join()
            log_relay("CLOSED", peer=peer, target=target)
    except (OSError, RunnerError) as exc:
        log_relay("ERROR", peer=peer, target=target, reason=type(exc).__name__)


def _relay_client_context(client: socket.socket, allow: frozenset[str]) -> None:
    with client:
        handle_relay_client(client, allow)


def relay_server(listen: str, port: int, allow: Sequence[str]) -> int:
    checked = frozenset(allow)
    for target in checked:
        split_target(target)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((listen, port))
        server.listen(32)
        log_relay("READY", listen=listen, port=port, allow=sorted(checked))
        while True:
            client, _ = server.accept()
            thread = threading.Thread(
                target=_relay_client_context,
                args=(client, checked),
                daemon=True,
            )
            thread.start()


def docker_command(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    docker = shutil.which("docker")
    if docker is None:
        raise RunnerError("docker-cli-unavailable")
    return subprocess.run(
        [docker, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def docker_checked(*args: str, timeout: int = 60) -> str:
    result = docker_command(*args, timeout=timeout)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RunnerError(f"docker-command-failed:{message}")
    return result.stdout.strip()


def wait_for_log(container: str, marker: str, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        result = docker_command("logs", container, timeout=5)
        if marker in result.stdout:
            return
        time.sleep(0.1)
    raise RunnerError(f"container-not-ready:{container}:{marker}")


def safe_remove_container(name: str) -> None:
    try:
        docker_command("rm", "-f", name, timeout=10)
    except (RunnerError, subprocess.TimeoutExpired):
        pass


def safe_remove_network(name: str) -> None:
    try:
        docker_command("network", "rm", name, timeout=10)
    except (RunnerError, subprocess.TimeoutExpired):
        pass


def unique_name(prefix: str) -> str:
    return f"{prefix}-{os.getpid()}-{time.time_ns():x}"


def smoke_script() -> str:
    return r"""
import json
import os
import socket
from pathlib import Path

checks = {}
checks["read_admitted_input"] = (
    Path("/inputs/0/input.txt").read_text(encoding="utf-8") == "admitted-input\n"
)
try:
    Path("/inputs/0/input.txt").write_text("mutated", encoding="utf-8")
except OSError:
    checks["deny_write_to_read_only_input"] = True
else:
    checks["deny_write_to_read_only_input"] = False
Path("/workspace/project-write.txt").write_text("project-write\n", encoding="utf-8")
checks["write_project_root"] = Path("/workspace/project-write.txt").is_file()
Path("/evidence/evidence-write.txt").write_text("evidence-write\n", encoding="utf-8")
checks["write_evidence_root"] = Path("/evidence/evidence-write.txt").is_file()
try:
    Path("/gnostoa-outside-write.txt").write_text("escape", encoding="utf-8")
except OSError:
    checks["deny_outside_write"] = True
else:
    checks["deny_outside_write"] = False
try:
    Path("/workspace/excluded-link").read_bytes()
except OSError:
    checks["deny_excluded_read"] = True
else:
    checks["deny_excluded_read"] = False
try:
    Path("/workspace/symlink-escape").read_bytes()
except OSError:
    checks["deny_symlink_escape"] = True
else:
    checks["deny_symlink_escape"] = False
checks["clean_environment"] = "GNOSTOA_UNRELATED_SECRET_SENTINEL" not in os.environ
checks["no_container_control_socket"] = not Path("/var/run/docker.sock").exists()
with socket.create_connection(("relay", 8080), timeout=5) as connection:
    target = "target:9443"
    connection.sendall(
        f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode("ascii")
    )
    response = b""
    while b"\r\n\r\n" not in response:
        response += connection.recv(4096)
    admitted = False
    if response.startswith(b"HTTP/1.1 200"):
        connection.sendall(b"PING")
        admitted = connection.recv(4) == b"PONG"
checks["admit_declared_egress"] = admitted
with socket.create_connection(("relay", 8080), timeout=5) as connection:
    target = "target:9444"
    connection.sendall(
        f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode("ascii")
    )
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = connection.recv(4096)
        if not chunk:
            break
        response += chunk
    refused_proxy = response.startswith(b"HTTP/1.1 403")
direct = socket.socket()
direct.settimeout(1)
try:
    direct.connect(("target", 9443))
except OSError:
    refused_direct = True
else:
    refused_direct = False
finally:
    direct.close()
checks["refuse_undeclared_egress"] = refused_proxy and refused_direct
print(json.dumps(checks, sort_keys=True))
"""


def target_script() -> str:
    return (
        "import socket;"
        "s=socket.socket();"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
        "s.bind(('0.0.0.0',9443));"
        "s.listen(2);"
        "s.settimeout(30);"
        "print('READY',flush=True);"
        "i=0;"
        "\nwhile i < 2:\n"
        " c,_=s.accept(); d=c.recv(4); "
        "c.sendall(b'PONG' if d==b'PING' else b'NOPE'); c.close(); i+=1\n"
        "s.close()"
    )


def blocked_smoke(reasons: Sequence[str]) -> dict[str, object]:
    return {
        "schema": SMOKE_SCHEMA,
        "status": "BLOCKED",
        "backend": None,
        "reasons": list(reasons),
        "failed_checks": [],
        "checks": {},
        "all_required_checks_passed": False,
        "counters": {
            "semantic_owner_interventions": 0,
            "mechanical_boundary_controls": 0,
        },
    }


def failed_smoke(reason: str, *, stderr: str = "") -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": SMOKE_SCHEMA,
        "status": "FAIL",
        "backend": "oci",
        "reasons": [],
        "failed_checks": [reason],
        "checks": {},
        "all_required_checks_passed": False,
        "counters": {
            "semantic_owner_interventions": 0,
            "mechanical_boundary_controls": 0,
        },
    }
    if stderr:
        payload["stderr"] = stderr[-2048:]
    return payload


def run_smoke_oci(image: str, relay_image: str) -> dict[str, object]:
    probe = probe_backend("oci", image=image)
    if probe.status != "AVAILABLE":
        return blocked_smoke(probe.reasons)
    internal = unique_name("gnostoa-smoke-int")
    external = unique_name("gnostoa-smoke-ext")
    target = unique_name("gnostoa-smoke-target")
    relay = unique_name("gnostoa-smoke-relay")
    try:
        docker_checked("network", "create", "--internal", internal)
        docker_checked("network", "create", external)
        docker_checked(
            "run",
            "-d",
            "--name",
            target,
            "--network",
            external,
            "--network-alias",
            "target",
            "--entrypoint",
            "python",
            image,
            "-c",
            target_script(),
        )
        wait_for_log(target, "READY")
        docker_checked(
            "run",
            "-d",
            "--name",
            relay,
            "--network",
            external,
            "--entrypoint",
            "python",
            relay_image,
            "-m",
            "tools.experiment_runner",
            "_relay",
            "--listen",
            "0.0.0.0",
            "--port",
            "8080",
            "--allow",
            "target:9443",
        )
        wait_for_log(relay, '"event": "READY"')
        docker_checked("network", "connect", "--alias", "relay", internal, relay)
        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-smoke-") as raw:
            root = Path(raw)
            admitted = root / "input"
            project = root / "project"
            evidence = root / "evidence"
            excluded = root / "excluded"
            outside = root / "outside"
            for path in (admitted, project, evidence, excluded, outside):
                path.mkdir()
            (admitted / "input.txt").write_text("admitted-input\n", encoding="utf-8")
            (excluded / "secret.txt").write_text("excluded\n", encoding="utf-8")
            (outside / "secret.txt").write_text("outside\n", encoding="utf-8")
            (project / "excluded-link").symlink_to(excluded / "secret.txt")
            (project / "symlink-escape").symlink_to(outside / "secret.txt")
            (project / "smoke_probe.py").write_text(smoke_script(), encoding="utf-8")
            uid = os.getuid() if hasattr(os, "getuid") else 10001
            gid = os.getgid() if hasattr(os, "getgid") else 10001
            env = os.environ.copy()
            env["GNOSTOA_UNRELATED_SECRET_SENTINEL"] = "must-not-be-inherited"
            result = subprocess.run(
                [
                    shutil.which("docker") or "docker",
                    "run",
                    "--rm",
                    "--network",
                    internal,
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--user",
                    f"{uid}:{gid}",
                    "--env",
                    "HOME=/tmp",
                    "--tmpfs",
                    "/tmp:rw,nosuid,nodev,mode=1777,size=64m",
                    "--mount",
                    f"type=bind,source={admitted},target=/inputs/0,readonly",
                    "--mount",
                    f"type=bind,source={project},target=/workspace",
                    "--mount",
                    f"type=bind,source={evidence},target=/evidence",
                    "--workdir",
                    "/workspace",
                    "--entrypoint",
                    "python",
                    image,
                    "/workspace/smoke_probe.py",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            if result.returncode != 0:
                return failed_smoke("experiment_probe_execution", stderr=result.stderr)
            raw_checks = json.loads(result.stdout)
            if not isinstance(raw_checks, dict):
                raise RunnerError("smoke-probe-result-not-mapping")
            checks = {
                str(key): bool(value)
                for key, value in cast(dict[object, object], raw_checks).items()
            }
            evidence_artifact = evidence / "evidence-write.txt"
            digest, size = sha256_file(evidence_artifact)
            checks["producer_bound_evidence"] = bool(digest and size > 0)
            failed = sorted(key for key, value in checks.items() if not value)
            mechanical = sum(
                1
                for key in (
                    "deny_write_to_read_only_input",
                    "deny_outside_write",
                    "deny_excluded_read",
                    "deny_symlink_escape",
                    "no_container_control_socket",
                    "refuse_undeclared_egress",
                )
                if checks.get(key)
            )
            return {
                "schema": SMOKE_SCHEMA,
                "status": "PASS" if not failed else "FAIL",
                "backend": "oci",
                "reasons": [],
                "failed_checks": failed,
                "checks": checks,
                "all_required_checks_passed": not failed,
                "counters": {
                    "semantic_owner_interventions": 0,
                    "mechanical_boundary_controls": mechanical,
                },
                "evidence": {
                    "schema": ATTEST_SCHEMA,
                    "sha256": digest,
                    "bytes": size,
                    "producer": {
                        "id": "gnostoa-experiment-runner-smoke",
                        "version": "1",
                        "config_sha256": hashlib.sha256(
                            f"{image}\n{relay_image}\nrestricted\n".encode()
                        ).hexdigest(),
                    },
                    "inputs": [],
                },
            }
    except (
        RunnerError,
        OSError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        return failed_smoke(f"coordinator_smoke:{type(exc).__name__}:{exc}")
    finally:
        safe_remove_container(relay)
        safe_remove_container(target)
        safe_remove_network(internal)
        safe_remove_network(external)


def parse_input_identity(value: str) -> dict[str, str]:
    identifier, separator, digest = value.partition("=")
    if not separator or not identifier or not _SHA256_RE.fullmatch(digest):
        raise RunnerError(f"invalid-input-identity:{value}")
    return {"id": identifier, "sha256": digest}


def attest_payload(
    artifact: Path,
    producer_id: str,
    producer_version: str,
    config_sha256: str,
    inputs: Sequence[str],
) -> dict[str, object]:
    if not _SHA256_RE.fullmatch(config_sha256):
        raise RunnerError("invalid-config-sha256")
    digest, size = sha256_file(artifact)
    return {
        "schema": ATTEST_SCHEMA,
        "sha256": digest,
        "bytes": size,
        "producer": {
            "id": producer_id,
            "version": producer_version,
            "config_sha256": config_sha256,
        },
        "inputs": [parse_input_identity(value) for value in inputs],
    }


def measured_path_size(path: Path) -> tuple[int, str]:
    stat_result = path.lstat()
    if path.is_symlink():
        raise RunnerError("size-check-refuses-symlink")
    if path.is_file():
        return stat_result.st_size, "lstat-size-v1"
    if not path.is_dir():
        raise RunnerError("size-check-supports-regular-file-or-directory")
    total = 0
    for current, dirnames, filenames in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in [*dirnames, *filenames]:
            candidate = current_path / name
            item = candidate.lstat()
            if candidate.is_symlink():
                raise RunnerError(f"size-check-refuses-symlink:{candidate}")
            if candidate.is_file():
                total += item.st_size
    return total, "recursive-lstat-size-v1"


def command_validate_profile(args: argparse.Namespace) -> int:
    try:
        profile = load_profile(Path(cast(str, args.profile)))
        reasons = validate_profile_data(profile, for_run=False)
    except RunnerError as exc:
        reasons = [str(exc)]
    emit(
        {
            "schema": VALIDATION_SCHEMA,
            "status": "VALID" if not reasons else "INVALID",
            "reasons": reasons,
        }
    )
    return 0 if not reasons else 2


def command_probe(args: argparse.Namespace) -> int:
    image = os.environ.get("GNOSTOA_EXPERIMENT_RUNNER_IMAGE")
    result = probe_backend(cast(str, args.backend), image=image)
    emit(
        {
            "schema": PROBE_SCHEMA,
            "status": result.status,
            "backend": result.backend,
            "reasons": result.reasons,
        }
    )
    return 0


def command_smoke(args: argparse.Namespace) -> int:
    image = os.environ.get("GNOSTOA_EXPERIMENT_RUNNER_IMAGE")
    relay_image = os.environ.get("GNOSTOA_EXPERIMENT_RUNNER_RELAY_IMAGE") or image
    network = cast(str, args.network)
    backend = cast(str, args.backend)
    if network != "restricted":
        emit(blocked_smoke(["only-restricted-smoke-is-qualified"]))
        return 0
    if image is None or relay_image is None:
        emit(blocked_smoke(["oci-image-not-bound"]))
        return 0
    if backend not in {"auto", "oci"}:
        emit(blocked_smoke(["bwrap-backend-not-qualified"]))
        return 0
    emit(run_smoke_oci(image, relay_image))
    return 0


def command_attest(args: argparse.Namespace) -> int:
    try:
        payload = attest_payload(
            Path(cast(str, args.artifact)),
            cast(str, args.producer_id),
            cast(str, args.producer_version),
            cast(str, args.config_sha256),
            cast(list[str], args.input),
        )
    except (OSError, RunnerError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    emit(payload)
    return 0


def command_check_size(args: argparse.Namespace) -> int:
    try:
        observed, method = measured_path_size(Path(cast(str, args.path)))
    except (OSError, RunnerError) as exc:
        emit({"schema": SIZE_SCHEMA, "status": "ERROR", "reasons": [str(exc)]})
        return 2
    maximum = cast(int, args.max_bytes)
    oversize = observed > maximum
    emit(
        {
            "schema": SIZE_SCHEMA,
            "status": "OVERSIZE" if oversize else "WITHIN_LIMIT",
            "bytes": observed,
            "max_bytes": maximum,
            "measurement": method,
        }
    )
    return 2 if oversize else 0


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
    return image, cast(str | None, relay_image)


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


def create_restricted_network(
    relay_image: str,
    allow: Sequence[str],
) -> tuple[str, str, str]:
    internal = unique_name("gnostoa-run-int")
    external = unique_name("gnostoa-run-ext")
    relay = unique_name("gnostoa-run-relay")
    try:
        docker_checked("network", "create", "--internal", internal)
        docker_checked("network", "create", external)
        relay_args = [
            "run",
            "-d",
            "--name",
            relay,
            "--network",
            external,
            "--entrypoint",
            "python",
            relay_image,
            "-m",
            "tools.experiment_runner",
            "_relay",
            "--listen",
            "0.0.0.0",
            "--port",
            "8080",
        ]
        for target in allow:
            relay_args.extend(["--allow", target])
        docker_checked(*relay_args)
        wait_for_log(relay, '"event": "READY"')
        docker_checked("network", "connect", "--alias", "relay", internal, relay)
        return internal, external, relay
    except (RunnerError, subprocess.TimeoutExpired):
        safe_remove_container(relay)
        safe_remove_network(internal)
        safe_remove_network(external)
        raise


def run_configuration_digest(
    profile_path: Path,
    backend: str,
    command: Sequence[str],
) -> str:
    profile_digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    material = json.dumps(
        {
            "backend": backend,
            "command": list(command),
            "profile_sha256": profile_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def executor_provenance(profile: Mapping[str, object]) -> dict[str, object]:
    executor = profile.get("executor")
    if not isinstance(executor, dict):
        raise RunnerError("executor-must-be-a-mapping")
    return dict(cast(dict[str, object], executor))


def stream_container_logs(container: str, output: Path) -> None:
    docker = shutil.which("docker")
    if docker is None:
        raise RunnerError("docker-cli-unavailable")
    with output.open("xb") as target:
        result = subprocess.run(
            [docker, "logs", container],
            check=False,
            stdout=target,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    if result.returncode != 0:
        raise RunnerError("relay-log-capture-failed")


def applied_control_count(
    read_roots: Sequence[str],
    temporary_roots: Sequence[str],
    network_mode: str,
) -> int:
    base_controls = 6
    mount_controls = len(read_roots) + len(temporary_roots) + 2
    network_controls = 2 if network_mode == "restricted" else 1
    return base_controls + mount_controls + network_controls


def run_profile_command(
    profile_path: Path,
    backend: str,
    command: Sequence[str],
) -> tuple[int, dict[str, object]]:
    profile = load_profile(profile_path)
    reasons = validate_profile_data(profile, for_run=True)
    if reasons:
        return 2, {
            "schema": RUN_SCHEMA,
            "status": "BLOCKED",
            "reasons": reasons,
        }
    if not command:
        return 2, {
            "schema": RUN_SCHEMA,
            "status": "BLOCKED",
            "reasons": ["empty-command"],
        }

    image, relay_image = profile_runtime(profile)
    probe = probe_backend(backend, image=image)
    if probe.status != "AVAILABLE" or probe.backend != "oci":
        return 0, {
            "schema": RUN_SCHEMA,
            "status": "BLOCKED",
            "backend": None,
            "reasons": probe.reasons,
        }

    read_roots, project_text, evidence_text, temporary_roots, _ = profile_paths(profile)
    project = Path(project_text)
    evidence = Path(evidence_text)
    evidence.mkdir(parents=True, exist_ok=True)
    stdout_path = evidence / "run-stdout.log"
    stderr_path = evidence / "run-stderr.log"
    relay_log_path = evidence / "run-network.jsonl"
    result_path = evidence / "run-result.json"
    paths_that_must_not_exist = [stdout_path, stderr_path, result_path]
    if profile_network(profile)[0] == "restricted":
        paths_that_must_not_exist.append(relay_log_path)
    if any(path.exists() for path in paths_that_must_not_exist):
        raise RunnerError("evidence-output-already-exists")

    mode, allow = profile_network(profile)
    internal = ""
    external = ""
    relay = ""
    if mode == "none":
        network_args = ["--network", "none"]
    elif mode == "restricted":
        if relay_image is None:
            raise RunnerError("relay-image-missing")
        internal, external, relay = create_restricted_network(relay_image, allow)
        network_args = [
            "--network",
            internal,
            "--env",
            "HTTP_PROXY=http://relay:8080",
            "--env",
            "HTTPS_PROXY=http://relay:8080",
            "--env",
            "ALL_PROXY=http://relay:8080",
            "--env",
            "NO_PROXY=",
        ]
    else:
        raise RunnerError("unsupported-network-mode")

    try:
        env_args, admitted_env_names = clean_environment_args(profile)
        uid = os.getuid() if hasattr(os, "getuid") else 10001
        gid = os.getgid() if hasattr(os, "getgid") else 10001
        docker = shutil.which("docker")
        if docker is None:
            raise RunnerError("docker-cli-unavailable")
        argv = [
            docker,
            "run",
            "--rm",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{uid}:{gid}",
            "--env",
            "HOME=/tmp",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,mode=1777,size=256m",
            *network_args,
            *env_args,
        ]
        for index, root in enumerate(read_roots):
            argv.extend(
                [
                    "--mount",
                    f"type=bind,source={root},target=/inputs/{index},readonly",
                ]
            )
        argv.extend(["--mount", f"type=bind,source={project},target=/workspace"])
        argv.extend(["--mount", f"type=bind,source={evidence},target=/evidence"])
        for index, root in enumerate(temporary_roots):
            argv.extend(["--mount", f"type=bind,source={root},target=/scratch/{index}"])
        argv.extend(["--workdir", "/workspace", image, *command])

        with (
            stdout_path.open("xb") as stdout_file,
            stderr_path.open("xb") as stderr_file,
        ):
            completed = subprocess.run(
                argv,
                check=False,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=60 * 60,
            )

        if relay:
            stream_container_logs(relay, relay_log_path)

        config_digest = run_configuration_digest(profile_path, backend, command)
        input_identities = string_list(
            profile.get("input_identities", []), "input_identities"
        )
        stdout_attestation = attest_payload(
            stdout_path,
            "gnostoa-experiment-runner",
            "1",
            config_digest,
            input_identities,
        )
        stderr_attestation = attest_payload(
            stderr_path,
            "gnostoa-experiment-runner",
            "1",
            config_digest,
            input_identities,
        )
        network_attestation: dict[str, object] | None = None
        if relay:
            network_attestation = attest_payload(
                relay_log_path,
                "gnostoa-experiment-runner-relay",
                "1",
                config_digest,
                input_identities,
            )

        archive_limit = profile.get("archive_limit_bytes")
        workspace_size_observation: dict[str, object] | None = None
        if isinstance(archive_limit, int) and not isinstance(archive_limit, bool):
            observed, method = measured_path_size(project)
            workspace_size_observation = {
                "bytes": observed,
                "configured_archive_limit_bytes": archive_limit,
                "measurement": method,
                "note": "workspace observation is not an archive-size substitute",
            }

        payload: dict[str, object] = {
            "schema": RUN_SCHEMA,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "backend": "oci",
            "exit_code": completed.returncode,
            "network_mode": mode,
            "command_argv": list(command),
            "executor": executor_provenance(profile),
            "run_config_sha256": config_digest,
            "input_identities": [
                parse_input_identity(value) for value in input_identities
            ],
            "admitted_environment_names": admitted_env_names,
            "stdout": stdout_attestation,
            "stderr": stderr_attestation,
            "network_evidence": network_attestation,
            "workspace_size_observation": workspace_size_observation,
            "counters": {
                "semantic_owner_interventions": 0,
                "mechanical_boundary_controls": applied_control_count(
                    read_roots,
                    temporary_roots,
                    mode,
                ),
            },
        }
        encoded = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        with result_path.open("xb") as result_file:
            result_file.write(encoded)
        return completed.returncode, payload
    finally:
        if relay:
            safe_remove_container(relay)
        if internal:
            safe_remove_network(internal)
        if external:
            safe_remove_network(external)


def command_run(args: argparse.Namespace) -> int:
    command = cast(list[str], args.command)
    if command and command[0] == "--":
        command = command[1:]
    try:
        exit_code, payload = run_profile_command(
            Path(cast(str, args.profile)),
            cast(str, args.backend),
            command,
        )
    except (OSError, RunnerError, subprocess.TimeoutExpired) as exc:
        emit(
            {
                "schema": RUN_SCHEMA,
                "status": "BLOCKED",
                "reasons": [f"{type(exc).__name__}:{exc}"],
            }
        )
        return 2
    emit(payload)
    return exit_code


def command_relay(args: argparse.Namespace) -> int:
    return relay_server(
        cast(str, args.listen),
        cast(int, args.port),
        cast(list[str], args.allow),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experiment_runner.py")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    validate = subparsers.add_parser("validate-profile")
    validate.add_argument("--profile", required=True)
    validate.set_defaults(handler=command_validate_profile)

    probe = subparsers.add_parser("probe")
    probe.add_argument(
        "--backend",
        choices=("auto", "oci", "bwrap"),
        default="auto",
    )
    probe.set_defaults(handler=command_probe)

    smoke = subparsers.add_parser("smoke")
    smoke.add_argument(
        "--backend",
        choices=("auto", "oci", "bwrap"),
        default="auto",
    )
    smoke.add_argument(
        "--network",
        choices=("none", "restricted"),
        default="restricted",
    )
    smoke.set_defaults(handler=command_smoke)

    attest = subparsers.add_parser("attest")
    attest.add_argument("--artifact", required=True)
    attest.add_argument("--producer-id", required=True)
    attest.add_argument("--producer-version", required=True)
    attest.add_argument("--config-sha256", required=True)
    attest.add_argument("--input", action="append", default=[])
    attest.set_defaults(handler=command_attest)

    size = subparsers.add_parser("check-size")
    size.add_argument("--path", required=True)
    size.add_argument("--max-bytes", required=True, type=int)
    size.set_defaults(handler=command_check_size)

    run = subparsers.add_parser("run")
    run.add_argument("--profile", required=True)
    run.add_argument(
        "--backend",
        choices=("auto", "oci", "bwrap"),
        default="auto",
    )
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(handler=command_run)

    relay = subparsers.add_parser("_relay")
    relay.add_argument("--listen", default="0.0.0.0")
    relay.add_argument("--port", type=int, default=8080)
    relay.add_argument("--allow", action="append", default=[])
    relay.set_defaults(handler=command_relay)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = cast(Handler, args.handler)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
