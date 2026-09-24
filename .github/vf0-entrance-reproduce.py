"""Evidence-only VF0 entrance test; never implements or enables the new gate."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SOURCE = Path(os.environ.get("VF0_SOURCE", "/workspace"))
OUTPUT = Path(os.environ.get("VF0_OUTPUT", "/evidence"))
PARENT = os.environ["VF0_PARENT"]
TREE = os.environ["VF0_TREE"]
PROBE_PATH = "tools/vf0_missing_evidence_probe.py"
PROBE = b'def normalize(value: int) -> int:\n    return max(0, value)\n'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def environment() -> dict[str, str]:
    # This test receives no credential values or provider write permission.
    keep = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"}
    keep.update({"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
                 "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_COUNT": "0",
                 "GIT_NO_REPLACE_OBJECTS": "1", "PYTHONNOUSERSITE": "1"})
    return keep


def command(argv: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(argv, cwd=cwd, env=environment(), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=1000, check=False)
    require(len(result.stdout) < 2_000_000 and len(result.stderr) < 2_000_000,
            "unexpected diagnostic volume")
    if check and result.returncode:
        detail = (result.stderr + result.stdout)[-4096:].decode("utf-8", errors="replace")
        raise RuntimeError(f"command failed ({result.returncode}): {detail}")
    return result


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return command(["/usr/bin/git", "-c", "core.hooksPath=/dev/null", *args], cwd, check=check)


def text(cwd: Path, *args: str) -> str:
    return git(cwd, *args).stdout.decode("utf-8").strip()


def main() -> None:
    require(re.fullmatch(r"[0-9a-f]{40}", PARENT) is not None, "invalid exact parent")
    require(re.fullmatch(r"[0-9a-f]{40}", TREE) is not None, "invalid exact tree")
    require(text(SOURCE, "rev-parse", "HEAD") == PARENT, "source parent mismatch")
    require(text(SOURCE, "rev-parse", "HEAD^{tree}") == TREE, "source tree mismatch")
    require(not text(SOURCE, "status", "--porcelain"), "source must be clean")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    require(not (OUTPUT / "result.json").exists(), "refuse to replace evidence")
    authority_paths = ("ci/prepare-candidate", "tools/candidate_prepare.py", "ci/style", "ci/verify")
    authority = {path: hashlib.sha256(git(SOURCE, "show", f"{PARENT}:{path}").stdout).hexdigest()
                 for path in authority_paths}

    with tempfile.TemporaryDirectory(prefix="gnostoa-vf0-entrance-") as directory:
        scratch = Path(directory)
        work = scratch / "candidate"
        git(scratch, "clone", "--no-hardlinks", "--no-checkout", str(SOURCE), str(work))
        git(work, "checkout", "--quiet", "--detach", PARENT)
        require(text(work, "rev-parse", "HEAD^{tree}") == TREE, "clone tree mismatch")
        # Retrieve integrated authority from exact Git objects, not mutable worktree bytes.
        wrapper = scratch / "parent-wrapper.sh"
        wrapper.write_bytes(git(work, "show", f"{PARENT}:ci/prepare-candidate").stdout)
        receipt = OUTPUT / "existing-preparation-receipt.json"
        def prepare(parent: str, destination: Path) -> subprocess.CompletedProcess[bytes]:
            return command(["/bin/sh", str(wrapper), "prepare", "--parent", parent,
                            "--receipt", str(destination), "--focused-profile", "smoke"],
                           work, check=False)

        empty_destination = scratch / "empty-receipt.json"
        empty = prepare(PARENT, empty_destination)
        require(empty.returncode != 0 and not empty_destination.exists(), "empty candidate control failed")
        require(b"candidate has no changes" in empty.stderr, "empty control failed for another reason")

        target = work / PROBE_PATH
        require(not target.exists(), "probe path already exists")
        target.write_bytes(PROBE)
        # Parent production is unchanged. The synthetic module is only a gate input.
        require(not text(work, "diff", "--name-only", PARENT), "parent tracked production was changed")
        require(text(work, "ls-files", "--others", "--exclude-standard") == PROBE_PATH,
                "unexpected evidence candidate paths")
        ancestor = text(work, "rev-parse", "HEAD^")
        stale_destination = scratch / "stale-receipt.json"
        stale = prepare(ancestor, stale_destination)
        require(stale.returncode != 0 and not stale_destination.exists(), "stale parent control failed")
        require(b"parent" in stale.stderr.lower(), "stale control failed for another reason")

        # No pre-implementation receipt, digest, provenance or admission is supplied.
        actual = prepare(PARENT, receipt)
        (OUTPUT / "prepare.stdout.txt").write_bytes(actual.stdout)
        (OUTPUT / "prepare.stderr.txt").write_bytes(actual.stderr)
        require(actual.returncode == 0, "current bypass not reproduced; inspect actual failure")
        payload = json.loads(receipt.read_bytes())
        require(payload["parent_commit"] == PARENT and payload["parent_tree"] == TREE,
                "existing receipt subject mismatch")
        require(payload["changed_paths"] == [PROBE_PATH], "unexpected prepared delta")
        require(payload["checks"] == {"style_fix": 0, "focused_verification": 0,
                                       "style_check": 0, "diff_check": 0}, "preparation did not run checks")
        prepared = payload["prepared_tree"]
        require(git(work, "show", f"{prepared}:{PROBE_PATH}").stdout == PROBE,
                "prepared module is not the intended gate input")
        require(text(work, "diff", "--name-only", PARENT, prepared) == PROBE_PATH,
                "prepared tree changed parent production")
        verify = command(["/bin/sh", str(wrapper), "verify", "--parent", PARENT,
                          "--tree", prepared, "--receipt", str(receipt),
                          "--receipt-sha256", payload["receipt_sha256"]], work)
        require(verify.returncode == 0, "existing receipt verifier did not accept")

        class MissingEvidenceGate(unittest.TestCase):
            def test_semantic_candidate_requires_prior_evidence(self) -> None:
                self.assertNotEqual(0, actual.returncode,
                                    "VF0_MISSING_PRE_EVIDENCE_WAS_ACCEPTED")
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(MissingEvidenceGate))
        (OUTPUT / "red-test.txt").write_text(stream.getvalue(), encoding="utf-8")
        require(result.testsRun == 1 and len(result.failures) == 1 and not result.errors
                and not result.skipped, "expected one non-vacuous assertion failure")
        require("VF0_MISSING_PRE_EVIDENCE_WAS_ACCEPTED" in result.failures[0][1],
                "wrong RED oracle")
        require(all(hashlib.sha256(git(work, "show", f"{PARENT}:{path}").stdout).hexdigest() == digest
                    for path, digest in authority.items()), "authority changed")
        summary = {"schema": "gnostoa-vf0-entrance-observation/v1",
                   "parent": PARENT, "parent_tree": TREE, "authority_sha256": authority,
                   "test_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "expected": "REJECT_MISSING_PRE_IMPLEMENTATION_EVIDENCE",
                   "observed": "PREPARED_WITHOUT_PRE_IMPLEMENTATION_EVIDENCE",
                   "execution": "RED", "tests_run": result.testsRun, "failures": len(result.failures),
                   "errors": len(result.errors), "skipped": len(result.skipped),
                   "empty_candidate_rejected": True, "stale_parent_rejected": True,
                   "parent_tracked_production_unchanged": True, "probe_path": PROBE_PATH,
                   "probe_sha256": hashlib.sha256(PROBE).hexdigest(),
                   "prepared_tree": prepared, "preparation_checks": payload["checks"],
                   "preparation_receipt_sha256": payload["receipt_sha256"],
                   "existing_receipt_verification": "PASS",
                   "claim": "Exact integrated authority accepts a synthetic semantic candidate without prior evidence; not a live production change or editor-chronology proof."}
        raw = (json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        (OUTPUT / "result.json").write_bytes(raw)
        (OUTPUT / "probe.py.txt").write_bytes(PROBE)
        command(["/bin/sh", str(wrapper), "release", "--parent", PARENT,
                 "--tree", prepared, "--receipt", str(receipt),
                 "--receipt-sha256", payload["receipt_sha256"]], work)
        print(stream.getvalue())
        print("VF0_EXPECTED_RED_CAPTURED sha256:" + hashlib.sha256(raw).hexdigest())
    require(text(SOURCE, "rev-parse", "HEAD") == PARENT and not text(SOURCE, "status", "--porcelain"),
            "source drift after characterization")


if __name__ == "__main__":
    main()
