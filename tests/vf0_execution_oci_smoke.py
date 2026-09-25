"""Fixed live-OCI smoke for the private VF0 bounded execution component.

This file is intentionally not unittest-discovered.  It is executed only by the
predeclared temporary provider smoke after an exact prepared candidate is
published.  Its result is component-conformance evidence, never RED
certification, producer admission, approval, compliance, or VF0 activation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from tools.vf0_execution import (
    DockerBackend,
    EvidenceFile,
    ExecutionLimits,
    ExecutionObservation,
    ExecutionRejected,
    GitSubject,
    execute,
)

FIXED_IMAGE = "ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4"  # pragma: allowlist secret -- public registry identity
EVIDENCE_PATH = "tests/vf0_execution_live_evidence.py"
EVIDENCE = rb"""import json, os, pathlib, socket, subprocess, sys, time
case = sys.argv[1]
if case == "isolation":
    checks = {}
    for name, path in (("subject_read_only", "/workspace/subject.txt"),
                       ("rootfs_read_only", "/etc/vf0-write-probe")):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.write(fd, b"ISOLATION_FAILURE\n")
            os.close(fd)
            checks[name] = False
        except OSError:
            checks[name] = True
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
else:
    raise AssertionError("UNKNOWN_CASE")
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
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


def _commit(repo: Path, value: str) -> GitSubject:
    (repo / "subject.txt").write_text(value + "\n")
    _git(repo, "add", "subject.txt")
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


def _summary(observation: ExecutionObservation) -> dict[str, Any]:
    return {
        "subject_commit": observation.subject.commit,
        "subject_tree": observation.subject.tree,
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


def run_smoke(image: str) -> dict[str, Any]:
    backend = DockerBackend(image)
    limits = ExecutionLimits(timeout_seconds=5.0, output_bytes=65_536)
    evidence = EvidenceFile(EVIDENCE_PATH, EVIDENCE)
    command = ("/usr/local/bin/python3", "-I", "/workspace/" + EVIDENCE_PATH)

    with tempfile.TemporaryDirectory(prefix="vf0-execution-live-") as td:
        repo = Path(td) / "fixture"
        repo.mkdir(mode=0o755)
        _git(repo, "init", "--quiet")
        first = _commit(repo, "one")
        second = _commit(repo, "two")

        cases: dict[str, dict[str, Any]] = {}
        for name, expected in (
            ("isolation", ("completed", 0)),
            ("spoof", ("completed", 0)),
            ("nonzero", ("completed", 17)),
            ("timeout", ("timeout", None)),
            ("overflow", ("output_limit", None)),
        ):
            observation = execute(
                repo,
                second,
                [evidence],
                [*command, name],
                backend,
                limits,
            )
            if (
                observation.capture.termination,
                observation.capture.exit_code,
            ) != expected:
                raise AssertionError("UNEXPECTED_" + name.upper() + "_OUTCOME")
            cases[name] = _summary(observation)

        if (
            b"approved"
            not in execute(
                repo, second, [evidence], [*command, "spoof"], backend, limits
            ).capture.stdout
        ):
            raise AssertionError("SPOOF_NOT_EXERCISED")

        first_observation = execute(
            repo, first, [evidence], [*command, "subject"], backend, limits
        )
        _expect_completed_success(first_observation, b"one\n")
        second_observation = execute(
            repo, second, [evidence], [*command, "subject"], backend, limits
        )
        _expect_completed_success(second_observation, b"two\n")
        cases["subject_one"] = _summary(first_observation)
        cases["subject_two"] = _summary(second_observation)

        wrong = GitSubject(commit=second.commit, tree=first.tree)
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

    return {
        "schema": "gnostoa-vf0-execution-oci-smoke/v1",
        "status": "PASS",
        "scope": "COMPONENT_CONFORMANCE_ONLY",
        "image": image,
        "cases": cases,
        "wrong_tree": wrong_tree,
        "production_receipt_issued": False,
        "producer_admitted": False,
        "compliance_established": False,
        "vf0_active": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default=FIXED_IMAGE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_smoke(args.image)
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if args.output is not None:
        args.output.write_bytes(raw)
    sys.stdout.write("VF0_EXECUTION_OCI_SMOKE " + raw.decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
