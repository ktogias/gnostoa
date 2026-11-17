"""Resolve the analyzer readback's subject from the event that started it (#387).

A secret-free workflow step runs this before any analyzer credential is injected.
It reads the triggering event's fields from its environment and prints one validated
subject, a Pull Request number and an exact head, as step outputs. When it can bind
none, it fails: a run that finished green without a receipt would make missing
evidence look like a clean producer (#389).

Each field is an identifier only. The runner re-reads the Pull Request from the
provider, and refuses a head that does not match (Decisions 0091 and 0107). Every
value is validated before it is printed, so no field can add an output of its own.

- `workflow_dispatch`: `DISPATCH_PULL`, `DISPATCH_HEAD`, from the owner's inputs.
- `workflow_call`: the same, from the merge-admission run's call, which re-reads
  the inventory at the admission point (#407, slice 1b.4).
- `repository_dispatch`: `REQUEST_PULL`, `REQUEST_HEAD`, from the request's payload.
- `workflow_run`: `RUN_PULLS`, the run's `pull_requests` as JSON, and `RUN_HEAD`. A
  run with no Pull Request, as a fork's, or with more than one binds none.

It also prints the artifact's name, `artifact`: Decision 0107's
`gnostoa-analyzer-readback-<pull>-<head>`, and for the merge-admission run's call its
run attempt too (`RUN_ATTEMPT`), since a re-run keeps the run and an artifact's name
cannot be reused within it (Codex on #426).
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping

from tools import github_events

_PULL_NUMBER = re.compile(r"[1-9]\d{0,9}", re.ASCII)


def _pull_number(value: str) -> int:
    if _PULL_NUMBER.fullmatch(value) is None:
        raise ValueError("pull number must be a positive decimal integer")
    return int(value)


def resolve(environ: Mapping[str, str]) -> dict[str, str]:
    """The subject the event names, as step outputs; ``ValueError`` when it names
    none, or a field is no identifier."""
    event = environ.get("EVENT_NAME", "")
    if event == "workflow_run":
        numbers = github_events.workflow_run_pull_numbers(environ.get("RUN_PULLS", ""))
        head = github_events.exact_sha(environ.get("RUN_HEAD", ""), "workflow_run head")
        if len(numbers) != 1:
            raise ValueError(
                f"the run names {len(numbers)} Pull Requests, not one: "
                "no exact-head readback can be bound"
            )
        return {"pull_number": str(numbers[0]), "head": head}
    fields = {
        "workflow_dispatch": ("DISPATCH_PULL", "DISPATCH_HEAD"),
        "workflow_call": ("DISPATCH_PULL", "DISPATCH_HEAD"),
        "repository_dispatch": ("REQUEST_PULL", "REQUEST_HEAD"),
    }.get(event)
    if fields is None:
        raise ValueError(f"no readback subject for event {event!r}")
    pull = _pull_number(environ.get(fields[0], ""))
    head = github_events.exact_sha(environ.get(fields[1], ""), "head")
    return {"pull_number": str(pull), "head": head}


def artifact(environ: Mapping[str, str], subject: Mapping[str, str]) -> str:
    """The readback artifact's name for ``subject``: the merge-admission run's call
    names its run attempt, so a re-run's upload never collides with an earlier
    attempt's, and the admission reads only its own attempt's readback."""
    name = f"gnostoa-analyzer-readback-{subject['pull_number']}-{subject['head']}"
    if environ.get("EVENT_NAME", "") != "workflow_call":
        return name
    attempt = environ.get("RUN_ATTEMPT", "")
    if _PULL_NUMBER.fullmatch(attempt) is None:
        raise ValueError("the call's run attempt must be a positive decimal integer")
    return f"{name}-{attempt}"


def main() -> int:
    try:
        subject = resolve(os.environ)
        outputs = {**subject, "artifact": artifact(os.environ, subject)}
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for key, value in outputs.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
