"""Fields of a GitHub event that a workflow hands a script (#387).

A workflow passes an event's fields to a script through its environment, or relays
the event GitHub delivered. They are identifiers only, never authority: a caller
re-reads whatever they name from the provider. The useful-L1 reconciler (Decision
0086), the analyzer readback (Decision 0107) and the merge-admission relay (#407,
1b.4) share this module, so each field is parsed once.
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


def delivered_comment_pull_number(event: object) -> int | None:
    """The pull request a relayed `issue_comment` event names, or None for an
    issue's comment. GitHub delivers a pull request's conversation comment on its
    issue, marked by a `pull_request` object (#426, F1 part 1). Anything else is
    refused with ``ValueError``; a boolean is no number."""
    if not isinstance(event, dict):
        raise ValueError("the delivered event is not an object")
    issue = event.get("issue")
    if not isinstance(issue, dict):
        raise ValueError("the delivered event names no issue")
    number = issue.get("number")
    if type(number) is not int or number <= 0:
        raise ValueError("the delivered event's issue number is invalid")
    marker = issue.get("pull_request")
    if marker is None:
        return None
    if not isinstance(marker, dict):
        raise ValueError("the delivered event's pull request marker is invalid")
    return number
