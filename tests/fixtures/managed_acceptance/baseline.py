"""Intentionally defective completion-only counterexample; retain for RED replay."""

from typing import Any

from services import FixtureServices


def run(case: dict[str, Any], services: FixtureServices) -> dict[str, str]:
    """Ignore admission, verification and loss; wrongly trust normal completion."""
    completed = False
    for event in services.start_worker():
        if event["kind"] == "dispatch-requested":
            services.dispatch()
        elif event["kind"] == "completed":
            completed = event["status"] == "completed"
    disposition = "ACCEPTED" if completed else "PENDING"
    return {
        "disposition": disposition,
        "reconciliation": disposition,
        "worker_check": (
            "REQUESTED" if services.worker_request_observed else "NOT_REQUIRED"
        ),
        "reason": "intentionally-defective-worker-completion-only",
    }
