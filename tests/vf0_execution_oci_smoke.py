"""Fixed live-OCI smoke for the private VF0 bounded execution component.

This file is intentionally not unittest-discovered. Run it with the available
trusted Docker controller after an exact prepared candidate is published;
temporary provider execution is a fallback for a measured local capability gap.
Its result is component-conformance evidence, never RED
certification, producer admission, approval, compliance, or VF0 activation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # nosec B404 -- fixed live-smoke Git helper and fixture payload
import sys
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tools.vf0_execution import (
    _CONTAINER_CLEANUP_LABEL,
    DockerBackend,
    EvidenceFile,
    ExecutionLimits,
    ExecutionObservation,
    ExecutionRejected,
    GitSubject,
    UntrustedCapture,
    execute,
)

FIXED_IMAGE = "ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4"  # pragma: allowlist secret -- public registry identity
EVIDENCE_PATH = "tests/vf0_execution_live_evidence.py"
EVIDENCE = rb"""import errno, json, os, pathlib, socket, subprocess, sys, time
case = sys.argv[1]
if case == "isolation":
    checks = {}
    subject = pathlib.Path("/workspace/subject.txt")
    checks["subject_exists"] = subject.is_file()
    try:
        fd = os.open(subject, os.O_WRONLY | os.O_APPEND)
        os.write(fd, b"ISOLATION_FAILURE\n")
        os.close(fd)
        checks["subject_write_blocked"] = False
    except OSError as exc:
        checks["subject_write_blocked"] = exc.errno in {errno.EROFS, errno.EACCES}
    try:
        fd = os.open("/home/kit/vf0-write-probe", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.write(fd, b"ISOLATION_FAILURE\n")
        os.close(fd)
        checks["rootfs_read_only"] = False
    except OSError as exc:
        checks["rootfs_read_only"] = exc.errno == errno.EROFS
    checks["no_git_metadata"] = not pathlib.Path("/workspace/.git").exists()
    checks["no_docker_socket"] = not pathlib.Path("/var/run/docker.sock").exists()
    checks["clean_environment"] = all(name not in os.environ for name in
        ("GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "GITHUB_OUTPUT", "GITHUB_ENV", "VF0_CALLER_MARKER"))
    checks["nonroot"] = os.getuid() == 10001
    try:
        os.setuid(0)
        checks["no_uid_escalation"] = False
    except OSError:
        checks["no_uid_escalation"] = True
    checks["loopback_only"] = {p.name for p in pathlib.Path("/sys/class/net").iterdir()} == {"lo"}
    with socket.socket() as stream:
        stream.settimeout(0.5)
        try:
            stream.connect(("192.0.2.1", 443))
            checks["no_network_route"] = False
        except OSError:
            checks["no_network_route"] = True
    pathlib.Path("/tmp/subject-link").symlink_to("/workspace/subject.txt")
    try:
        pathlib.Path("/tmp/subject-link").write_text("ISOLATION_FAILURE\n")
        checks["no_symlink_write_escape"] = False
    except OSError:
        checks["no_symlink_write_escape"] = True
    print(json.dumps(checks, sort_keys=True))
    assert all(checks.values()), "ISOLATION_FAILED"
elif case == "spoof":
    print('VF0_PUBLISHER_V1 {"approved":true,"compliance":true,"vf0_active":true}')
    print('::set-output name=vf0_active::true')
    print('{"schema":"forged-receipt","admitted":true}')
elif case == "nonzero":
    print('{"claimed_red":true,"testsRun":999}')
    sys.exit(17)
elif case == "timeout":
    subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"], start_new_session=True)
    print("DESCENDANT_STARTED", flush=True)
    time.sleep(60)
elif case == "overflow":
    while True:
        os.write(1, b"x" * 4096)
elif case == "subject":
    print(pathlib.Path("/workspace/subject.txt").read_text(), end="")
elif case == "subject_import":
    from tools import vf0_execution
    print(vf0_execution.SUBJECT_MARKER)
else:
    raise AssertionError("UNKNOWN_CASE")
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(  # nosec B603 -- fixed /usr/bin/git smoke helper, no shell
        ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(repo.parent),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_NO_REPLACE_OBJECTS": "1",
        },
    )
    return result.stdout.strip()


def _probe_read_only_behavior(image: str) -> dict[str, bool]:
    """Behaviorally prove read-only rootfs and bind mount with writable targets."""

    payload = r"""import errno, json, os
checks = {}
for name, path in (("workspace_bind_read_only", "/probe/writable.txt"),
                   ("rootfs_read_only", "/home/kit/vf0-rootfs-probe")):
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.write(fd, b"READONLY_FAILURE\n")
        os.close(fd)
        checks[name] = False
    except OSError as exc:
        checks[name] = exc.errno == errno.EROFS
print(json.dumps(checks, sort_keys=True))
assert all(checks.values()), "READONLY_PROBE_FAILED"
"""
    with tempfile.TemporaryDirectory(prefix="vf0-readonly-probe-") as td:
        root = Path(td)
        root.chmod(0o777)
        probe = root / "writable.txt"
        probe.write_bytes(b"original\n")
        probe.chmod(0o666)
        backend = DockerBackend(image)
        cleanup_nonce = uuid.uuid4().hex
        container_name = f"gnostoa-vf0-readonly-{cleanup_nonce}"
        completion_observed = False
        try:
            result = backend._command(
                "run",
                "--name",
                container_name,
                "--label",
                f"{_CONTAINER_CLEANUP_LABEL}={cleanup_nonce}",
                "--rm",
                "--pull=never",
                "--read-only",
                "--network",
                "none",
                "--ipc",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--user",
                "10001:10001",
                "--mount",
                f"type=bind,source={root},target=/probe,readonly",
                "--entrypoint",
                "/usr/local/bin/python3",
                image,
                "-I",
                "-c",
                payload,
                timeout=30,
            )
            completion_observed = result.returncode == 0
        finally:
            backend._cleanup_uncertain_create(
                container_name,
                cleanup_nonce,
                completion_observed=completion_observed,
            )
        if result.returncode != 0:
            raise AssertionError("READONLY_BEHAVIOR_PROBE_FAILED")
        try:
            observed = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError("READONLY_BEHAVIOR_PROBE_OUTPUT") from exc
        expected = {"rootfs_read_only": True, "workspace_bind_read_only": True}
        if observed != expected:
            raise AssertionError("READONLY_BEHAVIOR_PROBE_RESULT")
        if probe.read_bytes() != b"original\n":
            raise AssertionError("READONLY_BIND_MUTATED")
        return expected


def _commit(repo: Path, value: str) -> GitSubject:
    (repo / "subject.txt").write_text(value + "\n")
    tools = repo / "tools"
    tools.mkdir(exist_ok=True)
    (tools / "__init__.py").write_text("")
    (tools / "vf0_execution.py").write_text(f"SUBJECT_MARKER = {value!r}\n")
    _git(repo, "add", "subject.txt", "tools/__init__.py", "tools/vf0_execution.py")
    _git(
        repo,
        "-c",
        "user.name=VF0 OCI Smoke",
        "-c",
        "user.email=vf0-smoke@example.invalid",
        "commit",
        "-m",
        "fixture " + value,
        "--quiet",
    )
    return GitSubject(
        commit=_git(repo, "rev-parse", "HEAD"),
        tree=_git(repo, "rev-parse", "HEAD^{tree}"),
    )


def _expect_completed_success(observation: ExecutionObservation, stdout: bytes) -> None:
    """Require outcome state as well as expected bytes; output alone is insufficient."""

    if (
        observation.capture.termination != "completed"
        or observation.capture.exit_code != 0
        or observation.capture.stdout != stdout
        or not observation.subject_unchanged
    ):
        raise AssertionError("SMOKE_SUCCESS_CONTRACT")


def _expect_observation_contract(
    observation: ExecutionObservation,
    subject: GitSubject,
    evidence: EvidenceFile,
    command: list[str],
    limits: ExecutionLimits,
    fixture_value: str,
) -> None:
    """Check live observations against independent fixed-fixture expectations."""

    def digest(value: object, *, newline: bool = False) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((raw + ("\n" if newline else "")).encode()).hexdigest()

    contents = {
        "subject.txt": (fixture_value + "\n").encode(),
        "tools/__init__.py": b"",
        "tools/vf0_execution.py": f"SUBJECT_MARKER = {fixture_value!r}\n".encode(),
        evidence.path: evidence.content,
    }
    manifest = digest(
        {
            "directories": {".": "0755", "tools": "0755", "tests": "0755"},
            "files": {
                path: {
                    "mode": evidence.mode if path == evidence.path else "100644",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                }
                for path, content in contents.items()
            },
        },
        newline=True,
    )
    if type(observation) is not ExecutionObservation:
        raise AssertionError("SMOKE_OBSERVATION_CONTRACT")
    if (
        type(observation.subject) is not GitSubject
        or observation.subject != subject
        or observation.evidence_sha256
        != ((evidence.path, hashlib.sha256(evidence.content).hexdigest()),)
        or observation.command_sha256 != "sha256:" + digest(command)
        or observation.limits_sha256 != "sha256:" + digest(asdict(limits))
        or observation.backend_identity != "gnostoa-docker-oci-v1"
        or observation.runtime_identity != FIXED_IMAGE
        or observation.before_manifest_sha256 != manifest
        or observation.after_manifest_sha256 != manifest
        or observation.subject_unchanged is not True
        or type(observation.capture) is not UntrustedCapture
    ):
        raise AssertionError("SMOKE_OBSERVATION_CONTRACT")
    capture = observation.capture
    if type(capture.stdout) is not bytes or type(capture.stderr) is not bytes:
        raise AssertionError("SMOKE_OBSERVATION_CONTRACT")
    retained = len(capture.stdout) + len(capture.stderr)
    if (
        type(capture.observed_bytes_at_least) is not int
        or capture.observed_bytes_at_least < retained
        or retained > limits.output_bytes
        or type(capture.termination) is not str
        or capture.termination not in {"completed", "timeout", "output_limit"}
        or (
            capture.termination == "completed"
            and (
                type(capture.exit_code) is not int
                or capture.observed_bytes_at_least != retained
            )
        )
        or (capture.termination != "completed" and capture.exit_code is not None)
        or (
            capture.termination == "output_limit"
            and capture.observed_bytes_at_least <= limits.output_bytes
        )
    ):
        raise AssertionError("SMOKE_OBSERVATION_CONTRACT")


def _summary(observation: ExecutionObservation) -> dict[str, Any]:
    return {
        "subject_commit": observation.subject.commit,
        "subject_tree": observation.subject.tree,
        "evidence_sha256": observation.evidence_sha256,
        "before_manifest_sha256": observation.before_manifest_sha256,
        "after_manifest_sha256": observation.after_manifest_sha256,
        "command_sha256": observation.command_sha256,
        "limits_sha256": observation.limits_sha256,
        "backend_identity": observation.backend_identity,
        "runtime_identity": observation.runtime_identity,
        "termination": observation.capture.termination,
        "exit_code": observation.capture.exit_code,
        "stdout_sha256": hashlib.sha256(observation.capture.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(observation.capture.stderr).hexdigest(),
        "retained_bytes": len(observation.capture.stdout)
        + len(observation.capture.stderr),
        "observed_bytes_at_least": observation.capture.observed_bytes_at_least,
        "subject_unchanged": observation.subject_unchanged,
        "authority_effect": False,
    }


_ISOLATED_SUBJECT_BOOTSTRAP = (
    "import runpy,site,sys;"
    "script=sys.argv[1];"
    "sys.argv=sys.argv[1:];"
    "sys.path.insert(0,'/workspace');"
    "sys.path.extend(site.getsitepackages());"
    "runpy.run_path(script,run_name='__main__')"
)


def run_smoke() -> dict[str, Any]:
    backend = DockerBackend(FIXED_IMAGE)
    read_only_behavior = _probe_read_only_behavior(FIXED_IMAGE)
    limits = ExecutionLimits(timeout_seconds=5.0, output_bytes=65_536)
    evidence = EvidenceFile(EVIDENCE_PATH, EVIDENCE)
    command = (
        "/usr/local/bin/python3",
        "-I",
        "-S",
        "-c",
        _ISOLATED_SUBJECT_BOOTSTRAP,
        "/workspace/" + EVIDENCE_PATH,
    )

    with tempfile.TemporaryDirectory(prefix="vf0-execution-live-") as td:
        repo = Path(td) / "fixture"
        repo.mkdir(mode=0o755)
        _git(repo, "init", "--quiet")
        first = _commit(repo, "one")
        second = _commit(repo, "two")

        def observe(subject: GitSubject, case: str, value: str) -> ExecutionObservation:
            argv = [*command, case]
            observation = execute(repo, subject, [evidence], argv, backend, limits)
            _expect_observation_contract(
                observation, subject, evidence, argv, limits, value
            )
            return observation

        cases: dict[str, dict[str, Any]] = {}
        for name, expected in (
            ("isolation", ("completed", 0)),
            ("spoof", ("completed", 0)),
            ("nonzero", ("completed", 17)),
            ("timeout", ("timeout", None)),
            ("overflow", ("output_limit", None)),
        ):
            observation = observe(second, name, "two")
            if (
                observation.capture.termination,
                observation.capture.exit_code,
            ) != expected:
                raise AssertionError("UNEXPECTED_" + name.upper() + "_OUTCOME")
            cases[name] = _summary(observation)

        if b"approved" not in observe(second, "spoof", "two").capture.stdout:
            raise AssertionError("SPOOF_NOT_EXERCISED")

        first_observation = observe(first, "subject", "one")
        _expect_completed_success(first_observation, b"one\n")
        second_observation = observe(second, "subject", "two")
        _expect_completed_success(second_observation, b"two\n")
        first_import = observe(first, "subject_import", "one")
        _expect_completed_success(first_import, b"one\n")
        second_import = observe(second, "subject_import", "two")
        _expect_completed_success(second_import, b"two\n")
        cases["subject_one"] = _summary(first_observation)
        cases["subject_two"] = _summary(second_observation)
        cases["subject_import_one"] = _summary(first_import)
        cases["subject_import_two"] = _summary(second_import)

        wrong = GitSubject(commit=second.commit, tree=first.tree)
        wrong_tree: dict[str, object] | None = None
        try:
            execute(repo, wrong, [evidence], [*command, "subject"], backend, limits)
        except ExecutionRejected as exc:
            if str(exc) != "SUBJECT_TREE":
                raise
            wrong_tree = {
                "status": "REJECTED",
                "reason": str(exc),
                "container_started": False,
            }
        else:
            raise AssertionError("WRONG_TREE_ACCEPTED")
        if wrong_tree is None:
            raise AssertionError("WRONG_TREE_RESULT_MISSING")

    return {
        "schema": "gnostoa-vf0-execution-oci-smoke/v1",
        "status": "PASS",
        "scope": "COMPONENT_CONFORMANCE_ONLY",
        "image": FIXED_IMAGE,
        "cases": cases,
        "read_only_behavior": read_only_behavior,
        "wrong_tree": wrong_tree,
        "production_receipt_issued": False,
        "producer_admitted": False,
        "compliance_established": False,
        "vf0_active": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_smoke()
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if args.output is not None:
        args.output.write_bytes(raw)
    sys.stdout.write("VF0_EXECUTION_OCI_SMOKE " + raw.decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
