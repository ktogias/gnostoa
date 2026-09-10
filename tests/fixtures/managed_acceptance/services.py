"""Observable local fixture actions, not runtime isolation or provider access."""

from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from adapters import ADAPTERS


class FixtureServices:
    def __init__(self, case: dict[str, Any], adapter: str) -> None:
        self.case = deepcopy(case)
        self.adapter = adapter
        self.worker_started = False
        self.dispatch_count = 0
        self.worker_request_observed = False
        self.worker_terminal: str | None = None
        self.events: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []

    def start_worker(self) -> Iterator[dict[str, Any]]:
        if self.worker_started:
            raise RuntimeError("The scripted worker can only start once")
        self.worker_started = True
        return self._observe_events()

    def _observe_events(self) -> Iterator[dict[str, Any]]:
        stream = self.case["native_streams"][self.adapter]
        for event in ADAPTERS[self.adapter](stream):
            self.events.append(deepcopy(event))
            if event["kind"] == "worker-check-requested":
                self.worker_request_observed = True
            elif event["kind"] == "completed":
                self.worker_terminal = event["status"]
            yield event

    def dispatch(self) -> None:
        """Record a simulated dispatch; deliberately supply no capability guard."""
        if not self.worker_started:
            raise RuntimeError("Dispatch before worker start")
        self.dispatch_count += 1

    def check(self, trigger: str) -> dict[str, Any]:
        """Compare the frozen synthetic snapshot, independently of worker prose."""
        if trigger not in {"planned", "finalization", "worker-request"}:
            raise ValueError(f"Unknown fixture check trigger: {trigger}")
        target = self.case["target"]
        labels = set(target["labels"])
        labels_match = set(self.case["required_present"]) <= labels and not (
            set(self.case["required_absent"]) & labels
        )
        evidence = {
            "producer": "fixture-checker",
            "requester": "worker" if trigger == "worker-request" else "supervisor",
            "trigger": trigger,
            "evidence_id": f"{self.case['id']}:snapshot-1",
            "target_id": target["id"],
            "observation_cut": self.case["observation_cut"],
            "labels_match": labels_match,
            "target_state": target["state"],
            "labels": list(target["labels"]),
        }
        self.checks.append(deepcopy(evidence))
        return evidence

    def observations(self) -> dict[str, Any]:
        return {
            "worker_started": self.worker_started,
            "worker_terminal": self.worker_terminal,
            "dispatch_count": self.dispatch_count,
            "worker_request_observed": self.worker_request_observed,
            "assigned_checker": self.case["assigned_checker"],
            "invocation_observation_complete": self.case[
                "invocation_observation_complete"
            ],
            "separate_worker_request_required": self.case[
                "separate_worker_request_required"
            ],
            "events": deepcopy(self.events),
            "checks": deepcopy(self.checks),
        }
