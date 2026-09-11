"""Disposable experiment commands; not the supported Gnostoa CLI or a gate."""

import argparse
import fcntl
import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from storage import digest, normalize, read, write, write_bytes

HERE = Path(__file__).resolve().parent


def init(workspace: Path, source: Path) -> dict:
    if (workspace / "roster.json").exists():
        raise ValueError("Existing roster: resume it instead of overwriting")
    roster = read(source)
    ids = roster["eligible_job_ids"]
    if not ids or len(ids) > 2 or len(set(ids)) != len(ids):
        raise ValueError("Trial requires one or two distinct eligible jobs")
    bindings = {}
    for job_id in ids:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", job_id):
            raise ValueError("Invalid job ID")
        data = (source.parent / roster["assignments"][job_id]).read_bytes()
        assignment = json.loads(data)
        if assignment["job_id"] != job_id or assignment["subject"] != roster["subject"]:
            raise ValueError("Assignment does not match frozen roster")
        write_bytes(workspace / "assignments" / f"{job_id}.json", data)
        bindings[job_id] = digest(data)
    write_bytes(workspace / "roster.json", source.read_bytes())
    write(
        workspace / "active.json",
        {"subject": roster["subject"], "assignments": bindings},
    )
    write(workspace / "dispositions.json", {})
    return {"eligible_count": len(ids)}


def dispatch(workspace: Path, job_id: str, spec_path: Path) -> dict:
    roster = read(workspace / "roster.json")
    if job_id not in roster["eligible_job_ids"]:
        raise ValueError("Job is outside the independent eligible roster")
    job = workspace / "jobs" / job_id
    if job.exists():
        raise ValueError("Dispatch already recorded; reconcile, never blindly retry")
    spec = read(spec_path)
    if not isinstance(spec.get("argv"), list) or not spec["argv"]:
        raise ValueError("Explicit bounded worker argv required")
    if not 0 < spec.get("timeout_seconds", 30) <= 2700:
        raise ValueError("Worker deadline exceeds live trial limit")
    if spec.get("normalizer") not in {"plain", "codex-jsonl", "claude-jsonl"}:
        raise ValueError("Unqualified normalizer")
    active = read(workspace / "active.json")
    assignment = (workspace / "assignments" / f"{job_id}.json").read_bytes()
    if digest(assignment) != active["assignments"][job_id]:
        raise ValueError("Original assignment differs from active assignment")
    if (
        read(workspace / "assignments" / f"{job_id}.json")["subject"]
        != active["subject"]
    ):
        raise ValueError("Assignment subject is stale")
    job.mkdir(parents=True)
    write_bytes(job / "assignment.json", assignment)
    write(job / "spec.json", spec)
    write(
        job / "intent.json",
        {
            "assignment_sha256": digest(assignment),
            "subject": active["subject"],
            "recorded_ns": time.time_ns(),
        },
    )
    child = subprocess.Popen(
        [sys.executable, str(HERE / "worker_capture.py"), str(job)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # Loss of this acknowledgement cannot make the persisted intent disappear.
    write(job / "launch.json", {"pid": child.pid})
    return {"job": job_id, "pid": child.pid}


def collect(workspace: Path) -> dict:
    collected = []
    for job in sorted((workspace / "jobs").glob("*")):
        if not (job / "receipt.json").exists():
            continue
        if (job / "review.json").exists():
            continue
        try:
            receipt, intent = read(job / "receipt.json"), read(job / "intent.json")
            out, err = (
                (job / "stdout.bin").read_bytes(),
                (job / "stderr.bin").read_bytes(),
            )
            if (
                receipt["assignment_sha256"] != intent["assignment_sha256"]
                or receipt["subject"] != intent["subject"]
                or receipt["stdout_sha256"] != digest(out)
                or receipt["stderr_sha256"] != digest(err)
                or receipt["returncode"] != 0
            ):
                raise ValueError("Receipt does not establish this completed capture")
            review = normalize(out, read(job / "spec.json")["normalizer"])
            write(job / "review.json", review)
            collected.append(job.name)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            write(job / "normalization-error.json", {"error": str(exc)})
    return {"collected": collected}


def disposition(workspace: Path, args: argparse.Namespace) -> dict:
    if args.job not in read(workspace / "roster.json")["eligible_job_ids"]:
        raise ValueError("Unknown job")
    review = read(workspace / "jobs" / args.job / "review.json")
    if args.finding not in [row["id"] for row in review["findings"]]:
        raise ValueError("Unknown original finding")
    records = read(workspace / "dispositions.json")
    key = args.job + ":" + args.finding
    entry = {
        "finding_id": args.finding,
        "disposition": args.value,
        "reason": args.reason,
    }
    if key in records and records[key] != entry:
        raise ValueError("Existing disposition differs; preserve it before revision")
    records[key] = entry
    write(workspace / "dispositions.json", records)
    return entry


def revise(workspace: Path, args: argparse.Namespace) -> dict:
    active = read(workspace / "active.json")
    if args.commit:
        if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
            raise ValueError("An exact commit is required")
        active["subject"] = {"commit": args.commit}
    else:
        if args.job not in active["assignments"] or not args.assignment:
            raise ValueError("Known job and revised assignment required")
        data = Path(args.assignment).read_bytes()
        # Original bytes stay untouched, including the prior assignment.
        write_bytes(workspace / "revisions" / f"{digest(data)}.json", data)
        active["assignments"][args.job] = digest(data)
    write(workspace / "active.json", active)
    return active


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("init").add_argument("--roster", type=Path, required=True)
    dispatch_parser = commands.add_parser("dispatch")
    dispatch_parser.add_argument("--job", required=True)
    dispatch_parser.add_argument("--spec", type=Path, required=True)
    commands.add_parser("collect")
    commands.add_parser("view")
    revised = commands.add_parser("revise")
    revised.add_argument("--job")
    revised.add_argument("--assignment")
    revised.add_argument("--commit")
    disp = commands.add_parser("disposition")
    disp.add_argument("--job", required=True)
    disp.add_argument("--finding", required=True)
    disp.add_argument("--value", required=True)
    disp.add_argument("--reason", required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    with (workspace / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.operation == "init":
            result = init(workspace, args.roster)
        elif args.operation == "dispatch":
            result = dispatch(workspace, args.job, args.spec)
        elif args.operation == "collect":
            result = collect(workspace)
        elif args.operation == "disposition":
            result = disposition(workspace, args)
        elif args.operation == "revise":
            result = revise(workspace, args)
        else:
            implementation = os.environ.get(
                "GNOSTOA_EXCHANGE_IMPLEMENTATION", "candidate"
            )
            if implementation not in {"candidate", "baseline"}:
                raise ValueError("Unknown implementation")
            result = importlib.import_module(implementation).view(workspace)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
