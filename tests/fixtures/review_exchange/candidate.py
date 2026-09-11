"""Experimental result view enumerated from independently frozen assignments."""

from pathlib import Path

from storage import read


def view(workspace: Path) -> dict:
    ids = read(workspace / "roster.json")["eligible_job_ids"]
    active = read(workspace / "active.json")
    records = read(workspace / "dispositions.json")
    original_records, artifacts = {}, {}
    reviews, current, pending, stale, unknown, errors = {}, [], [], [], [], []
    unresolved, never = [], []
    for job_id in ids:
        job = workspace / "jobs" / job_id
        artifacts[job_id] = [
            str(path.relative_to(workspace))
            for path in (job / "stdout.bin", job / "stderr.bin", job / "receipt.json")
            if path.is_file()
        ]
        if not (job / "intent.json").exists():
            never.append(job_id)
            pending.append(job_id)
            continue
        if not (job / "receipt.json").exists():
            unknown.append(job_id)
        if (job / "normalization-error.json").exists():
            errors.append(job_id)
        if not (job / "review.json").exists():
            pending.append(job_id)
            continue
        original, intent = read(job / "review.json"), read(job / "intent.json")
        original_records[job_id] = original
        reviews[job_id] = {k: original[k] for k in ("recommendation", "findings")}
        bucket = (
            current
            if (
                intent["subject"] == active["subject"]
                and intent["assignment_sha256"] == active["assignments"][job_id]
            )
            else stale
        )
        bucket.append(job_id)
        for finding in original["findings"]:
            if finding["material"]:
                unresolved.append(finding["id"])
    result = {
        "eligible_count": len(ids),
        "current_ids": current,
        "pending_ids": pending,
        "stale_ids": stale,
        "unknown_dispatch_ids": unknown,
        "never_dispatched_ids": never,
        "original_reviews": reviews,
        "original_review_records": original_records,
        "executor_dispositions": records,
        "native_artifact_paths": artifacts,
        "normalization_error_ids": errors,
        "unresolved_material_finding_ids": unresolved,
        "executor_disposition_count": len(records),
        "automatic_retry_count": 0,
        "independent_review_claim": False,
        "human_approval": False,
        "real_provider_portability": "UNESTABLISHED",
    }
    if len(records) == 1:
        result["executor_disposition"] = next(iter(records.values()))
    return result
