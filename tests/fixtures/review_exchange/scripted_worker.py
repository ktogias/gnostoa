"""Controlled native worker for the admitted review-transport experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--assignment-out", type=Path, required=True)
    parser.add_argument("--intent-path", type=Path, required=True)
    parser.add_argument("--release-file", type=Path)
    args = parser.parse_args()

    assignment = sys.stdin.buffer.read()
    args.assignment_out.parent.mkdir(parents=True, exist_ok=True)
    args.assignment_out.write_bytes(assignment)
    intent = args.intent_path.read_bytes() if args.intent_path.is_file() else None
    observation = {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "observed_at_unix_ns": time.time_ns(),
        "assignment_bytes": len(assignment),
        "assignment_sha256": hashlib.sha256(assignment).hexdigest(),
        "intent_present_before_native_worker_output": intent is not None,
        "intent_sha256": hashlib.sha256(intent).hexdigest() if intent else None,
    }
    args.marker.parent.mkdir(parents=True, exist_ok=True)
    with args.marker.open("ab") as stream:
        stream.write((json.dumps(observation, sort_keys=True) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())

    if args.release_file is not None:
        deadline = time.monotonic() + 25
        while not args.release_file.exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("controlled worker release was not supplied")
            time.sleep(0.02)

    sys.stdout.buffer.write(args.response.read_bytes())
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(args.diagnostic.read_bytes())
    sys.stderr.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
