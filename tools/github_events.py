"""Fields of a GitHub event that a workflow hands a script (#387).

A workflow passes an event's fields to a script through its environment. They are
identifiers only, never authority: a caller re-reads whatever they name from the
provider. The useful-L1 reconciler (Decision 0086) and the analyzer readback
(Decision 0107) share this module, so `workflow_run.pull_requests` is parsed once.
"""

from __future__ import annotations

import json
import re

_SHA40 = re.compile(r"[0-9a-f]{40}")


def exact_sha(value: object, label: str) -> str:
    """``value`` if it is an exact 40-character lowercase commit SHA; otherwise
    ``ValueError``. The analyzer readback's resolver and runner share it (Claude on
    #388)."""
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise ValueError(f"{label} must be an exact 40-character SHA")
    return value


def workflow_run_pull_numbers(raw: str) -> list[int]:
    """The Pull Request numbers in ``workflow_run.pull_requests``, once each, in order.

    GitHub leaves the list empty for a fork's run, so an empty or null list is no
    error. Anything that is not a list of objects with a positive integer ``number``
    is refused with ``ValueError``.
    """
    # Kept once each, in order, in linear time (Amazon Q on #388).
    return list(dict.fromkeys(_pull_number(item) for item in _items(raw)))


def _items(raw: str) -> list[object]:
    """The list ``raw`` holds; empty for an empty or null field."""
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
    return loaded


def _pull_number(item: object) -> int:
    """One item's positive integer ``number``; a boolean is no number."""
    if not isinstance(item, dict):
        raise ValueError("workflow_run.pull_requests items must be objects")
    number = item.get("number")
    if type(number) is not int or number <= 0:
        raise ValueError(
            "workflow_run.pull_requests contains an invalid Pull Request number"
        )
    return number
