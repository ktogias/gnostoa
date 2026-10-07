"""Resolve the analyzer readback's subject from the event that started it (#387).

A secret-free workflow step runs this before any analyzer credential is injected.
It reads the triggering event's fields from its environment and prints one validated
subject, a Pull Request number and an exact head, as step outputs, or nothing.

Each field is an identifier only. The runner re-reads the Pull Request from the
provider, and refuses a head that does not match (Decisions 0091 and 0107). Every
value is validated before it is printed, so no field can add an output of its own.

- `workflow_dispatch`: `DISPATCH_PULL`, `DISPATCH_HEAD`, from the owner's inputs.
- `repository_dispatch`: `REQUEST_PULL`, `REQUEST_HEAD`, from the request's payload.
- `workflow_run`: `RUN_PULLS`, the run's `pull_requests` as JSON, and `RUN_HEAD`. A
  run with no Pull Request, as a fork's, or with more than one reads nothing.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping

from tools import github_events
from tools.analyzer_readback import exact_sha

_PULL_NUMBER = re.compile(r"[1-9][0-9]{0,9}")


def _pull_number(value: str) -> int:
    if _PULL_NUMBER.fullmatch(value) is None:
        raise ValueError("pull number must be a positive decimal integer")
    return int(value)


def resolve(environ: Mapping[str, str]) -> dict[str, str]:
    """The subject the event names, as step outputs; empty when it names none."""
    event = environ.get("EVENT_NAME", "")
    if event == "workflow_run":
        numbers = github_events.workflow_run_pull_numbers(environ.get("RUN_PULLS", ""))
        head = exact_sha(environ.get("RUN_HEAD", ""), "workflow_run head")
        if len(numbers) != 1:
            return {}
        return {"pull_number": str(numbers[0]), "head": head}
    fields = {
        "workflow_dispatch": ("DISPATCH_PULL", "DISPATCH_HEAD"),
        "repository_dispatch": ("REQUEST_PULL", "REQUEST_HEAD"),
    }.get(event)
    if fields is None:
        raise ValueError(f"no readback subject for event {event!r}")
    pull = _pull_number(environ.get(fields[0], ""))
    head = exact_sha(environ.get(fields[1], ""), "head")
    return {"pull_number": str(pull), "head": head}


def main() -> int:
    try:
        subject = resolve(os.environ)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not subject:
        print("No single Pull Request to read for this event.", file=sys.stderr)
    for key, value in subject.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
