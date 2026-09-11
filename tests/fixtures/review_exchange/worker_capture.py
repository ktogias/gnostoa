"""Capture one explicitly launched process independently of its coordinator."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from storage import digest, read, write, write_bytes


def main() -> None:
    job = Path(sys.argv[1])
    intent = read(job / "intent.json")
    spec = read(job / "spec.json")
    assignment = (job / "assignment.json").read_bytes()
    write(job / "capture-start.json", {"pid": os.getpid(), "time_ns": time.time_ns()})
    started = False
    capture_error = None
    try:
        child = subprocess.Popen(
            spec["argv"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            cwd=spec.get("cwd"),
        )
        started = True
        try:
            out, err = child.communicate(
                assignment, timeout=spec.get("timeout_seconds", 30)
            )
            code = child.returncode
        except subprocess.TimeoutExpired:
            # Bound cooperative descendants in the same group, not escaped workers
            # or already-submitted remote inference/effects.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, err = child.communicate()
            code, capture_error = None, "TimeoutExpired"
    except OSError as exc:
        out, err, code = b"", b"", None
        capture_error = type(exc).__name__
        write(job / "capture-error.json", {"type": capture_error, "message": str(exc)})
    # On spawn failure these are empty placeholders, explicitly marked below;
    # a capture diagnostic must never be attributed to native process stderr.
    write_bytes(job / "stdout.bin", out)
    write_bytes(job / "stderr.bin", err)
    if spec.get("drop_receipt", False):
        write(job / "fault-injected.json", {"kind": "lost-receipt"})
        return
    write(
        job / "receipt.json",
        {
            "assignment_sha256": digest(assignment),
            "subject": intent["subject"],
            "stdout_sha256": digest(out),
            "stderr_sha256": digest(err),
            "returncode": code,
            "capture_pid": os.getpid(),
            "process_started": started,
            "capture_error": capture_error,
        },
    )


if __name__ == "__main__":
    main()
