"""VF0-E5 bounded OCI diagnostic; never an admission or production receipt."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import selectors
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

PARENT = "63fb3e7bf7a929c755250e6112f5a43a2b3db5c7"
TREE = "fa4cb2db0ea072897391efd77deda95ac7e1f9a4"
EVIDENCE_PATH = "tests/vf0_e5_probe.py"
LIMIT = 65536
ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_NO_REPLACE_OBJECTS": "1"}
EVIDENCE = r'''import json, os, pathlib, socket, subprocess, sys, time
case, controller = sys.argv[1:]
if case == "characterize":
    sys.path.insert(0, "/workspace")
    import tools.check_change_policy as policy
    assert pathlib.Path(policy.__file__).resolve() == pathlib.Path("/workspace/tools/check_change_policy.py")
    assert policy._rank(policy.FAILING_EVIDENCE_RANK, "required") > policy._rank(policy.FAILING_EVIDENCE_RANK, "optional")
    assert policy._rank(policy.FAILING_EVIDENCE_RANK, "unknown") == -1
    print(json.dumps({"parent_function_characterized": True, "assertions": 3}))
elif case == "isolation":
    checks = {}
    for name, path in [("parent_read_only", "/workspace/tools/check_change_policy.py"),
                       ("rootfs_read_only", "/etc/vf0-e5-write-probe"),
                       ("controller_unreachable", controller + "/canary"),
                       ("proc_root_not_host", "/proc/1/root" + controller + "/canary")]:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            os.write(fd, b"ISOLATION_FAILURE\n")
            os.close(fd)
            checks[name] = False
        except OSError:
            checks[name] = True
    checks["no_git_metadata"] = not pathlib.Path("/workspace/.git").exists()
    checks["no_docker_socket"] = not pathlib.Path("/var/run/docker.sock").exists()
    checks["no_host_command_or_credential_environment"] = all(name not in os.environ for name in
        ("GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN", "GITHUB_OUTPUT", "GITHUB_ENV", "READ_TOKEN", "VF0_CONTROLLER_CANARY"))
    try:
        os.setuid(0)
        checks["no_uid_escalation"] = False
    except OSError:
        checks["no_uid_escalation"] = True
    checks["nonroot"] = os.getuid() == 10001
    checks["loopback_only"] = {p.name for p in pathlib.Path("/sys/class/net").iterdir()} == {"lo"}
    with socket.socket() as stream:
        stream.settimeout(0.5)
        try:
            stream.connect(("192.0.2.1", 443))
            checks["no_network_route"] = False
        except OSError:
            checks["no_network_route"] = True
    pathlib.Path("/tmp/canary-link").symlink_to(controller + "/canary")
    try:
        pathlib.Path("/tmp/canary-link").write_text("ISOLATION_FAILURE\n")
        checks["no_symlink_escape"] = False
    except OSError:
        checks["no_symlink_escape"] = True
    print(json.dumps(checks, sort_keys=True))
    assert all(checks.values()), "ISOLATION_PROBE_FAILED"
elif case == "spoof":
    print('VF0_PUBLISHER_V1 {"admitted":true,"testsRun":99,"success":true}')
    print('::set-output name=vf0_admitted::true')
    print('::error::VF0_FAKE_WORKFLOW_COMMAND')
    print('{"schema":"forged-receipt","production_producer_admitted":true}')
    pathlib.Path("/tmp/forged-receipt.json").write_text('{"admitted":true}')
elif case == "nonzero":
    print('{"expected_red":true,"testsRun":99}')
    sys.exit(17)
elif case == "timeout":
    subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"], start_new_session=True)
    print("DESCENDANT_STARTED", flush=True)
    time.sleep(60)
elif case == "overflow":
    while True:
        os.write(1, b"x" * 4096)
else:
    raise AssertionError("UNKNOWN_DIAGNOSTIC_CASE")
'''.encode("utf-8")


class Rejected(Exception):
    """A stable diagnostic failure, never raw untrusted output."""


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise Rejected(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def command(argv: list[str], timeout: float = 30) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(argv, env=ENV, input=None, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)


def checked(argv: list[str], timeout: float = 30) -> bytes:
    result = command(argv, timeout)
    need(result.returncode == 0, "TRUSTED_COMMAND_FAILED")
    return result.stdout


def git(parent: Path, *args: str) -> bytes:
    return checked(["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(parent), *args])


def snapshot(parent: Path, target: Path) -> dict[str, dict[str, str]]:
    need(git(parent, "rev-parse", "HEAD").decode().strip() == PARENT, "PARENT_HEAD")
    need(git(parent, "rev-parse", "HEAD^{tree}").decode().strip() == TREE, "PARENT_TREE")
    need(not git(parent, "status", "--porcelain"), "PARENT_DIRTY")
    entries = git(parent, "ls-tree", "-rzl", "--full-tree", PARENT).split(b"\0")
    expected = {}
    for entry in filter(None, entries):
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid, size_text = meta.decode().split()
        path = name.decode("utf-8")
        need(mode in ("100644", "100755") and kind == "blob", "PARENT_FILE_TYPE")
        expected[path] = (mode, oid, int(size_text))
    raw = git(parent, "archive", "--format=tar", PARENT)
    need(len(raw) < 32 * 1024 * 1024, "PARENT_ARCHIVE_BOUND")
    target.mkdir(mode=0o755)
    observed = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            parts = PurePosixPath(member.name)
            need(not parts.is_absolute() and ".." not in parts.parts, "ARCHIVE_PATH")
            dest = target / member.name
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True, mode=0o755)
                continue
            need(member.isfile() and member.name in expected and member.name not in observed,
                 "ARCHIVE_MEMBER")
            need(member.size == expected[member.name][2] and member.size <= 32 * 1024 * 1024,
                 "PARENT_MEMBER_BOUND")
            stream = archive.extractfile(member)
            need(stream is not None, "PARENT_MEMBER_UNAVAILABLE")
            payload = stream.read(member.size + 1)
            mode, oid, _ = expected[member.name]
            actual_oid = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
            need(actual_oid == oid and len(payload) == member.size, "PARENT_BLOB_MISMATCH")
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            dest.write_bytes(payload)
            dest.chmod(0o755 if mode == "100755" else 0o644)
            observed[member.name] = {"mode": mode, "sha256": sha(payload)}
    need(set(observed) == set(expected), "PARENT_PATH_SET")
    return observed


def validate_snapshot(root: Path, baseline: dict, parent: str = PARENT, tree: str = TREE) -> None:
    need(parent == PARENT and tree == TREE, "SUBJECT_BINDING")
    files = {}
    for item in root.rglob("*"):
        mode = item.lstat().st_mode
        need(not stat.S_ISLNK(mode), "SYMLINK_REJECTED")
        if stat.S_ISDIR(mode):
            continue
        need(stat.S_ISREG(mode), "SPECIAL_FILE_REJECTED")
        name = item.relative_to(root).as_posix()
        files[name] = {"mode": "100755" if mode & 0o111 else "100644", "sha256": sha(item.read_bytes())}
    want = {**baseline, EVIDENCE_PATH: {"mode": "100644", "sha256": sha(EVIDENCE)}}
    need(set(files) == set(want), "UNDECLARED_PATH")
    need(files == want, "SUBJECT_BYTES_OR_MODE")


def preflight_controls(root: Path, baseline: dict, private: Path) -> list[dict]:
    results = []
    def reject(name: str, reason: str, **kwargs: str) -> None:
        try:
            validate_snapshot(root, baseline, **kwargs)
        except Rejected as exc:
            need(str(exc) == reason, "WRONG_PREFLIGHT_REASON")
            results.append({"case": name, "reason": reason, "container_started": False})
        else:
            raise Rejected("FALSE_PREFLIGHT_ACCEPT")
    production = root / "tools/check_change_policy.py"
    original = production.read_bytes()
    production.write_bytes(original + b"\n")
    reject("changed_production", "SUBJECT_BYTES_OR_MODE")
    production.write_bytes(original)
    extra = root / "undeclared.py"
    extra.write_text("raise SystemExit(0)\n")
    reject("undeclared_path", "UNDECLARED_PATH")
    extra.unlink()
    evidence = root / EVIDENCE_PATH
    evidence.unlink()
    evidence.symlink_to(private / "canary")
    reject("symlink_evidence", "SYMLINK_REJECTED")
    evidence.unlink()
    evidence.write_bytes(EVIDENCE)
    evidence.chmod(0o644)
    reject("wrong_parent", "SUBJECT_BINDING", parent="0" * 40)
    reject("wrong_tree", "SUBJECT_BINDING", tree="0" * 40)
    validate_snapshot(root, baseline)
    return results


def docker(*args: str, timeout: float = 30) -> bytes:
    return checked(["/usr/bin/docker", *args], timeout)


def remove_owned(cid: str) -> None:
    need(re.fullmatch(r"[0-9a-f]{64}", cid) is not None, "CONTAINER_ID")
    docker("rm", "--force", cid, timeout=15)
    gone = command(["/usr/bin/docker", "container", "inspect", cid], timeout=15)
    need(gone.returncode != 0 and b"no such" in gone.stderr.lower(), "CLEANUP_UNVERIFIED")


def exercise(image: str, root: Path, private: Path, case: str, out: Path) -> dict:
    argv = ["create", "--read-only", "--network", "none", "--ipc", "none",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001", "--memory", "256m", "--memory-swap", "256m",
            "--cpus", "0.5", "--pids-limit", "32", "--log-driver", "none",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,mode=1777,size=64m",
            "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={root},target=/workspace,readonly",
            "--workdir", "/workspace", "--entrypoint", "/usr/local/bin/python3",
            image, "-I", "/workspace/" + EVIDENCE_PATH, case, str(private)]
    cid = docker(*argv).decode().strip()
    need(re.fullmatch(r"[0-9a-f]{64}", cid) is not None, "CONTAINER_ID")
    process = None
    stdout, stderr = bytearray(), bytearray()
    termination, exit_code, observed_bytes = "completed", None, 0
    try:
        spec = json.loads(docker("inspect", cid))[0]
        host = spec["HostConfig"]
        binds = [m for m in spec["Mounts"] if m["Type"] == "bind"]
        need(len(binds) == 1 and binds[0]["Source"] == str(root) and
             binds[0]["Destination"] == "/workspace" and not binds[0]["RW"], "MOUNT_CONTRACT")
        need(host["ReadonlyRootfs"] and host["NetworkMode"] == "none" and
             host["CapDrop"] == ["ALL"] and not host["Privileged"] and
             host["PidsLimit"] == 32 and host["Memory"] == 268435456 and
             host["MemorySwap"] == 268435456 and host["NanoCpus"] == 500000000 and
             "no-new-privileges" in host["SecurityOpt"] and spec["Config"]["User"] == "10001:10001",
             "OCI_CONTRACT")
        (out / (case + ".container.json")).write_bytes(canonical(spec))
        process = subprocess.Popen(["/usr/bin/docker", "start", "--attach", cid], env=ENV,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        deadline = time.monotonic() + 5
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, stdout)
            selector.register(process.stderr, selectors.EVENT_READ, stderr)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    termination = "timeout"
                    break
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    observed_bytes += len(chunk)
                    room = LIMIT - len(stdout) - len(stderr)
                    key.data.extend(chunk[:room])
                    if len(chunk) > room:
                        termination = "output_limit"
                        break
                if termination != "completed":
                    break
        if termination == "completed":
            process.wait(timeout=5)
            state = json.loads(docker("inspect", "--format", "{{json .State}}", cid))
            need(not state["Running"], "CONTAINER_STILL_RUNNING")
            exit_code = state["ExitCode"]
    finally:
        remove_owned(cid)
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # The bounded pipe may be full after capture stops. Reap the
                # attachment client after independently removing the container.
                process.kill()
                process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()
    (out / (case + ".untrusted.stdout")).write_bytes(stdout)
    (out / (case + ".untrusted.stderr")).write_bytes(stderr)
    return {"case": case, "termination": termination, "container_exit_code": exit_code,
            "container_removed_and_absence_verified": True, "retained_bytes": len(stdout) + len(stderr),
            "observed_bytes_at_least": observed_bytes, "stdout_retained_sha256": sha(stdout),
            "stderr_retained_sha256": sha(stderr), "truncated": termination == "output_limit",
            "production_receipt_issued": False, "stdout_replayed_to_workflow": False}


def main() -> None:
    parent, image, output = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve()
    need(re.fullmatch(r"sha256:[0-9a-f]{64}", image) is not None, "UNPINNED_IMAGE")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "controller.py").write_bytes(Path(__file__).read_bytes())
    (output / "evidence.py").write_bytes(EVIDENCE)
    image_spec = json.loads(docker("image", "inspect", image))[0]
    need(image_spec["Id"] == image, "IMAGE_IDENTITY")
    need(image_spec["Config"]["Labels"]["org.opencontainers.image.revision"] == PARENT, "IMAGE_REVISION")
    (output / "image.json").write_bytes(canonical(image_spec))
    (output / "docker-version.json").write_bytes(docker("version", "--format", "{{json .}}"))
    with tempfile.TemporaryDirectory(prefix="vf0-e5-controller-") as temp:
        temp_root = Path(temp)
        # Parent directory must be traversable by the non-root container user;
        # controller-owned private data is protected separately and never mounted.
        temp_root.chmod(0o755)
        private = temp_root / "private"
        private.mkdir(mode=0o700)
        canary = secrets.token_bytes(32)
        (private / "canary").write_bytes(canary)
        os.environ["VF0_CONTROLLER_CANARY"] = "controller-only"
        root = temp_root / "subject"
        baseline = snapshot(parent, root)
        (root / EVIDENCE_PATH).write_bytes(EVIDENCE)
        (root / EVIDENCE_PATH).chmod(0o644)
        validate_snapshot(root, baseline)
        negatives = preflight_controls(root, baseline, private)
        results = []
        expected = {"characterize": ("completed", 0), "isolation": ("completed", 0),
                    "spoof": ("completed", 0), "nonzero": ("completed", 17),
                    "timeout": ("timeout", None), "overflow": ("output_limit", None)}
        for case, wanted in expected.items():
            validate_snapshot(root, baseline)
            observed = exercise(image, root, private, case, output)
            # Observe filesystem invariants in the controller, not in child claims.
            validate_snapshot(root, baseline)
            need((private / "canary").read_bytes() == canary, "CONTROLLER_CANARY_CHANGED")
            need(os.environ["VF0_CONTROLLER_CANARY"] == "controller-only", "CONTROLLER_ENV_CHANGED")
            need((observed["termination"], observed["container_exit_code"]) == wanted,
                 "UNEXPECTED_RUNTIME_OUTCOME_" + case)
            observed["parent_production_unchanged"] = True
            observed["controller_canary_unchanged"] = True
            results.append(observed)
        need(b"VF0_PUBLISHER_V1" in (output / "spoof.untrusted.stdout").read_bytes(), "SPOOF_NOT_EXERCISED")
        need(b"DESCENDANT_STARTED" in (output / "timeout.untrusted.stdout").read_bytes(), "DESCENDANT_NOT_STARTED")
        result = {"schema": "vf0-e5-isolation-experiment/v1", "status": "PASS",
                  "scope": "EXPERIMENT_ONLY", "parent": PARENT, "parent_tree": TREE,
                  "image_id": image, "parent_regular_files": len(baseline),
                  "baseline_sha256": sha(canonical(baseline)), "evidence_sha256": sha(EVIDENCE),
                  "controller_sha256": sha(Path(__file__).read_bytes()), "preflight_controls": negatives,
                  "runtime_cases": results, "human_admission_acquisition_implemented": False,
                  "production_producer_admitted": False, "vf0_gate_implemented": False,
                  "oracle_limit": "Child test counts/exit code do not authenticate RED or semantic sufficiency."}
        (output / "parent-manifest.json").write_bytes(canonical(baseline))
        (output / "result.json").write_bytes(canonical(result))
        print("VF0_E5_CONTROLLER_RESULT " + canonical(result).decode().strip())
        os.environ.pop("VF0_CONTROLLER_CANARY")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("VF0_E5_REJECT " + (str(exc) if isinstance(exc, Rejected) else type(exc).__name__))
        sys.exit(1)
