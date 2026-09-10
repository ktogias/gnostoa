"""Bounded acceptance control for cooperative scripted fixtures only."""

from typing import Any

from services import FixtureServices


def _result(
    disposition: str, reconciliation: str, worker_check: str, reason: str
) -> dict[str, str]:
    return {
        "disposition": disposition,
        "reconciliation": reconciliation,
        "worker_check": worker_check,
        "reason": reason,
    }


def _worker_check(case: dict[str, Any], services: FixtureServices) -> str:
    if not services.worker_started:
        return "NOT_STARTED"
    if services.worker_request_observed:
        return "REQUESTED"
    if case["assigned_checker"] != "worker":
        return "NOT_REQUIRED"
    if case["invocation_observation_complete"] and services.worker_terminal is not None:
        return "OMITTED"
    return "UNKNOWN"


def run(case: dict[str, Any], services: FixtureServices) -> dict[str, str]:
    required = set(case["required_capabilities"])
    if any(case["capability_evidence"].get(name) != "supported" for name in required):
        return _result("PENDING", "PENDING", "NOT_STARTED", "capability-unestablished")

    guarantees_available = True
    evidence: list[dict[str, Any]] = []
    for event in services.start_worker():
        if event["kind"] == "runtime-guarantee-lost":
            if event["capability"] in required:
                guarantees_available = False
        elif event["kind"] == "dispatch-requested":
            if guarantees_available:
                services.dispatch()
        elif event["kind"] == "worker-check-requested":
            if guarantees_available and case["check_plan"] == "worker-request":
                evidence.append(services.check("worker-request"))

    worker_check = _worker_check(case, services)
    if not guarantees_available:
        return _result("PENDING", "PENDING", worker_check, "required-guarantee-lost")
    if services.worker_terminal != "completed":
        return _result("PENDING", "PENDING", worker_check, "worker-not-completed")

    check_plan = case["check_plan"]
    if check_plan in {"planned", "finalization"} and (
        case["assigned_checker"] == "supervisor"
        or case["allow_supervisor_substitution"]
    ):
        evidence.append(services.check(check_plan))

    if not evidence:
        return _result("PENDING", "PENDING", worker_check, "verification-missing")
    if any(not check["labels_match"] for check in evidence):
        return _result("REFUSED", "REFUSED", worker_check, "labels-contradict-scope")
    if case["separate_worker_request_required"] and worker_check != "REQUESTED":
        return _result("PENDING", "ACCEPTED", worker_check, "worker-request-missing")
    return _result("ACCEPTED", "ACCEPTED", worker_check, "verified-reconciliation")
