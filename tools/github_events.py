"""Fields of a GitHub event that a workflow hands a script (#387).

A workflow passes an event's fields to a script through its environment. They are
identifiers only, never authority: a caller re-reads whatever they name from the
provider. The useful-L1 reconciler (Decision 0086) and the analyzer readback
(Decision 0107) share this module, so `workflow_run.pull_requests` is parsed once.
"""

from __future__ import annotations

import json


def workflow_run_pull_numbers(raw: str) -> list[int]:
    """The Pull Request numbers in ``workflow_run.pull_requests``, once each, in order.

    GitHub leaves the list empty for a fork's run, so an empty or null list is no
    error. Anything that is not a list of objects with a positive integer ``number``
    is refused with ``ValueError``.
    """
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("workflow_run.pull_requests is invalid JSON") from exc
    if loaded is None:
        return []
    if not isinstance(loaded, list):
        raise ValueError("workflow_run.pull_requests must be an array")
    numbers: list[int] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise ValueError("workflow_run.pull_requests items must be objects")
        number = item.get("number")
        if type(number) is not int or number <= 0:
            raise ValueError(
                "workflow_run.pull_requests contains an invalid Pull Request number"
            )
        if number not in numbers:
            numbers.append(number)
    return numbers
