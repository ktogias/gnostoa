from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import cast

from .backend import (
    container_exit_code,
    docker_checked,
    docker_executable,
    ensure_container_absent,
    probe_backend,
    require_docker_object_id,
    safe_remove_container,
    safe_remove_network,
    unique_name,
    wait_for_log,
)
from .evidence import ATTEST_SCHEMA, sha256_file
from .profile import RunnerError

SMOKE_SCHEMA = "gnostoa-experiment-runner-smoke/v1"


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


def blocked_smoke(reasons: list[str]) -> dict[str, object]:
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


def _created_id(output: str, label: str) -> str:
    return require_docker_object_id(output, label)


def run_smoke_oci(image: str, relay_image: str) -> dict[str, object]:
    probe = probe_backend("oci", image=image)
    if probe.status != "AVAILABLE":
        return blocked_smoke(probe.reasons)
    internal_name = unique_name("gnostoa-smoke-int")
    external_name = unique_name("gnostoa-smoke-ext")
    target_name = unique_name("gnostoa-smoke-target")
    relay_name = unique_name("gnostoa-smoke-relay")
    internal_id = ""
    external_id = ""
    target_id = ""
    relay_id = ""
    probe_id = ""
    try:
        internal_id = _created_id(
            docker_checked("network", "create", "--internal", internal_name),
            "smoke-internal-network",
        )
        external_id = _created_id(
            docker_checked("network", "create", external_name),
            "smoke-external-network",
        )
        target_id = _created_id(
            docker_checked(
                "run",
                "-d",
                "--name",
                target_name,
                "--network",
                external_id,
                "--network-alias",
                "target",
                "--entrypoint",
                "python",
                image,
                "-c",
                target_script(),
            ),
            "smoke-target-container",
        )
        wait_for_log(target_id, "READY")
        relay_id = _created_id(
            docker_checked(
                "run",
                "-d",
                "--name",
                relay_name,
                "--network",
                external_id,
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
            ),
            "smoke-relay-container",
        )
        wait_for_log(relay_id, '"event": "READY"')
        docker_checked("network", "connect", "--alias", "relay", internal_id, relay_id)
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
            probe_id = _created_id(
                docker_checked(
                    "create",
                    "--network",
                    internal_id,
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
                ),
                "smoke-probe-container",
            )
            try:
                result = subprocess.run(
                    [docker_executable(), "start", "--attach", probe_id],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                )
                probe_exit_code = container_exit_code(probe_id)
            finally:
                ensure_container_absent(probe_id)
                probe_id = ""
            if probe_exit_code != 0:
                return failed_smoke(
                    "experiment_probe_execution",
                    stderr=result.stderr,
                )
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
        if probe_id:
            safe_remove_container(probe_id)
        if relay_id:
            safe_remove_container(relay_id)
        if target_id:
            safe_remove_container(target_id)
        if internal_id:
            safe_remove_network(internal_id)
        if external_id:
            safe_remove_network(external_id)
