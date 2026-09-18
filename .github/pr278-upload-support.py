"""Temporary PR278 Git-object transfer; never a product or merge-gate component."""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

REPO = "ktogias/gnostoa"
BASE = "a744776795a4e083b4df45c49016c25a2aa2071a"
BASE_TREE = "e52fa6f76c0da7296deac7cab31cdd030c850fcc"
EXPECTED_TREE = "5fdde305526b6acf7e305165d2242ede1609b5e3"
TRANSMITTED_BLOB = "158358e307dd67a5b05856975ac3530f5261506b"
GZIP_SHA256 = "91af94f2b2ec08a2b002920edb30d488047a73ad850d02bc2557172dc3aa56f8"
PATCH_SHA256 = "b8d6084d9990ce8813a47b36f1b243e71e22beb4fc568c95cf24fbec372565b5"
FILES = {
    ".github/workflows/r2a-protected-current-advisory.yml": "bba39b61faed1ef21a64c7d9aae5dee753ab4953",
    ".github/workflows/verification.yml": "7d4136952851b7d39284a4290d6797feabe44c1a",
    "ci/review_outer_containment_smoke.py": "3e670b299e71781f2fff5cf6016ee89a5845eb64",
    "knowledge/decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md": "6b5077fca62b368e30c9f361f861b43f53ae44e8",
    "policy/guardrails.yaml": "9b2fc621d038a910da80e8fa823f4730f9140569",
    "tests/test_review_assurance_p2b_b2_activation_red.py": "12407f88adcabdda444e9cef9ff804015662f3d2",
    "tests/test_review_assurance_p2b_exit_readback_red.py": "0a9dc1e3c8c7c09abb55528b1c1e593aff4643e1",
    "tests/test_review_outer_containment.py": "41f566eb88e0f11d7db98085158091a31e2acc70",
    "tests/test_tools.py": "6ba9687ce9657afa9a44ffc0ca9a4d6736be7eca",
    "tools/review_outer.py": "0ba3df389e82d0e8ab8277fb5f7f4c75d60049ab",
}


def api(method, suffix, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{suffix}",
        data=body,
        method=method,
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise RuntimeError("support API response exceeded its bound")
    return json.loads(raw)


def git(root, *args, data=None):
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", *args],
        input=data,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8").strip()


def prepare(root):
    if git(root, "rev-parse", "HEAD") != BASE:
        raise RuntimeError("wrong baseline checkout")
    if git(root, "status", "--porcelain"):
        raise RuntimeError("support reconstruction requires a clean baseline")
    blob = api("GET", f"git/blobs/{TRANSMITTED_BLOB}")
    if blob.get("sha") != TRANSMITTED_BLOB or blob.get("encoding") != "base64":
        raise RuntimeError("wrong transmitted object")
    encoded = "".join(blob["content"].split())
    # This one transport blob had a two-character transcription fault. Repair
    # only that known fault, then require BOTH original pre-transfer digests.
    # The repair is not a product change and cannot relax source identity.
    if len(encoded) != 18308 or encoded.count("P22ruJuJuJh0") != 1:
        raise RuntimeError("unexpected transport encoding")
    encoded = encoded.replace("P22ruJuJuJh0", "P22ruJuJh0").rstrip("=")
    encoded += "=" * (-len(encoded) % 4)
    compressed = base64.b64decode(encoded, validate=True)
    if hashlib.sha256(compressed).hexdigest() != GZIP_SHA256:
        raise RuntimeError("compressed transfer identity mismatch")
    patch = gzip.decompress(compressed)
    if len(patch) != 50942 or hashlib.sha256(patch).hexdigest() != PATCH_SHA256:
        raise RuntimeError("patch transfer identity mismatch")
    git(root, "apply", "--index", "--whitespace=error-all", "-", data=patch)
    if git(root, "diff", "--cached", "--name-only").splitlines() != sorted(FILES):
        raise RuntimeError("unexpected product path set")
    if git(root, "write-tree") != EXPECTED_TREE:
        raise RuntimeError("reconstructed source tree mismatch")
    contents = {}
    for path, expected in FILES.items():
        entry = git(root, "ls-files", "--stage", "--", path)
        if not entry.startswith(f"100644 {expected} 0\t"):
            raise RuntimeError("source blob or mode mismatch")
        raw = (root / path).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != expected or len(raw) > 250_000:
            raise RuntimeError("source content mismatch or size overflow")
        contents[path] = raw.decode("utf-8")
    return contents


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in {"prepare", "upload"}:
        raise RuntimeError("expected checkout directory and prepare/upload mode")
    root = Path(sys.argv[1]).resolve()
    contents = prepare(root)
    if sys.argv[2] == "upload":
        # No candidate code is executed in this job. Store only Git objects;
        # commits, refs, PR changes and publication are not API operations here.
        entries = []
        for path, content in contents.items():
            result = api("POST", "git/blobs", {"content": content, "encoding": "utf-8"})
            if result.get("sha") != FILES[path]:
                raise RuntimeError("uploaded blob identity mismatch")
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": result["sha"]})
        result = api("POST", "git/trees", {"base_tree": BASE_TREE, "tree": entries})
        if result.get("sha") != EXPECTED_TREE:
            raise RuntimeError("uploaded tree identity mismatch")
    print(json.dumps({"mode": sys.argv[2], "tree": EXPECTED_TREE, "files": FILES}, sort_keys=True))


if __name__ == "__main__":
    main()
