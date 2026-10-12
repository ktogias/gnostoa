"""The `merge-admission` check run's identity rules (#407, MA0 slice 1b.4).

Decision 0112 item 5 publishes the verdict as one check run, posted by the dedicated
App `gnostoa-ma0`. Two protected programs read those runs: the relay that publishes
them (`ci/merge_admission_relay.py`) and the guard the merge procedure runs after
activation (`ci/merge_admission_guard.py`, F1 part 3 on #426). They read a run the
same way, from this module:

- a run is the App's only when its App id says so;
- the App's latest run on a head is GitHub's `filter=latest` view, which keeps one run
  per App and name, and a view that does not hold every run it counts is refused;
- a run records the workflow run, attempt and protected revision that wrote it, the
  nonce of the guarded merge that dispatched it, if one did (G1), and the digest of
  the evidence that evaluation rebuilt without the analyzer bundle, once there is
  one, in one fenced block of its text.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

from tools import github_rest
from tools.review_check import strict_json_loads

CHECK_NAME = "merge-admission"
MAX_LISTED_RUNS = 100
CORRELATION_MARKER = "<!-- gnostoa:merge-admission:correlation:v1 -->"
_CORRELATION_FIELDS = frozenset(
    {
        "workflow_run_id",
        "run_attempt",
        "protected_revision",
        "nonce",
        "unbundled_evidence_sha256",
    }
)
NONCE = re.compile(r"[0-9a-f]{32}")
_CORRELATION_BLOCK = re.compile(
    re.escape(CORRELATION_MARKER) + r"\n```json\n(\{[^\n]*\})\n```"
)
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class PublicationError(RuntimeError):
    """A check run that was refused, could not be read back, or reads back as
    something other than what was written."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def comparable(value: Any) -> Any:
    """The evidence as the verdict reads it: every observation time dropped, at any
    depth, since a re-read observes again without changing what it found."""

    if isinstance(value, Mapping):
        return {
            key: comparable(item) for key, item in value.items() if key != "observed_at"
        }
    if isinstance(value, list):
        return [comparable(item) for item in value]
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    """The digest of a document as the verdict reads it."""

    return hashlib.sha256(canonical(comparable(value))).hexdigest()


def ours(run: object, app_id: int) -> bool:
    app = run.get("app") if isinstance(run, Mapping) else None
    return isinstance(app, Mapping) and app.get("id") == app_id


def run_id(run: object) -> int | None:
    identifier = run.get("id") if isinstance(run, Mapping) else None
    return identifier if type(identifier) is int else None


def app_latest(
    client: Any, repository: str, head: str, app_id: int
) -> Mapping[str, Any] | None:
    """The dedicated App's latest run of the check on the head, or None."""

    url = client.url(
        f"repos/{repository}/commits/{head}/check-runs"
        f"?check_name={CHECK_NAME}&filter=latest&per_page={MAX_LISTED_RUNS}"
    )
    try:
        document, _ = client.get(url)
    except github_rest.GitHubError as exc:
        raise PublicationError("UNKNOWN", "the check runs could not be read") from exc
    runs = document.get("check_runs") if isinstance(document, Mapping) else None
    total = document.get("total_count") if isinstance(document, Mapping) else None
    if not isinstance(runs, list) or type(total) is not int or total > len(runs):
        raise PublicationError("UNKNOWN", "the check runs read back incompletely")
    mine = [run for run in runs if ours(run, app_id)]
    if len(mine) > 1:
        raise PublicationError(
            "UNKNOWN", "the latest view holds more than one of the App's runs"
        )
    if mine and run_id(mine[0]) is None:
        raise PublicationError("UNKNOWN", "the App's latest run has no id")
    return mine[0] if mine else None


def read_run(client: Any, repository: str, identifier: int) -> Mapping[str, Any]:
    """One check run, read natively by its id."""

    try:
        run, _ = client.get(client.url(f"repos/{repository}/check-runs/{identifier}"))
    except github_rest.GitHubError as exc:
        raise PublicationError(
            "UNKNOWN", "the check run could not be read back"
        ) from exc
    if not isinstance(run, Mapping):
        raise PublicationError("MISMATCH", "the check run reads back as no run")
    return run


def correlation_text(correlation: Mapping[str, Any]) -> str:
    """The block a run's text holds, naming what wrote it."""

    body = json.dumps(
        {field: correlation[field] for field in sorted(_CORRELATION_FIELDS)},
        sort_keys=True,
    )
    return f"{CORRELATION_MARKER}\n```json\n{body}\n```"


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def correlation_of(run: object) -> dict[str, Any] | None:
    """What a run's text says wrote it, or None when it says nothing exact."""

    output = run.get("output") if isinstance(run, Mapping) else None
    text = output.get("text") if isinstance(output, Mapping) else None
    if not isinstance(text, str):
        return None
    found = _CORRELATION_BLOCK.search(text)
    if found is None:
        return None
    try:
        value = strict_json_loads(found.group(1), label="the check run's correlation")
    except ValueError:
        return None
    if (
        not isinstance(value, dict)
        or set(value) != _CORRELATION_FIELDS
        or not _positive(value["workflow_run_id"])
        or not _positive(value["run_attempt"])
        or not isinstance(value["protected_revision"], str)
        or _SHA40.fullmatch(value["protected_revision"]) is None
        or not _optional(value["nonce"], NONCE)
        or not _optional(value["unbundled_evidence_sha256"], _SHA256)
    ):
        return None
    return value


def _optional(value: object, pattern: re.Pattern[str]) -> bool:
    """None, or a string the pattern matches whole."""

    return value is None or (
        isinstance(value, str) and pattern.fullmatch(value) is not None
    )
