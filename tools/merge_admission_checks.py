"""The `merge-admission` check run's identity rules (#407, MA0 slice 1b.4).

Decision 0112 item 5 publishes the verdict as one check run, posted by the dedicated
App `gnostoa-ma0`. Three protected programs read those runs: the relay that publishes
them (`ci/merge_admission_relay.py`), the guard the merge procedure runs after
activation (`ci/merge_admission_guard.py`, F1 part 3 on #426), and L1's subject
selection (`ci/review_github_current_state.py`). They read a run the same way, from
this module:

- a run is the App's only when its App id says so;
- the App's latest run on a head is GitHub's `filter=latest` view, which keeps one run
  per App and name, and a view that does not hold every run it counts is refused;
- a run records the workflow run, attempt and protected revision that wrote it, the
  nonce of the guarded merge that dispatched it, if one did (G1), and the digest of
  the evidence that evaluation rebuilt without the analyzer bundle, once there is
  one, in one fenced block of its text.

The guard's predicates over such a record live here as well, so the selection proves
an equivalent routine request by the rules the guarded merge refuses by (#407's queue
correction, Decision 0133): the pinned App's completed success on the head, the
evidence rebuilt now without the bundle under the digest it records, and the pull
request alone at its head.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, TypeVar

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
# The pauses before each try again (Decision 0135): fixed, since one head's publication
# runs in one lock (Decision 0133), so there are at most four tries. A rate limit waits
# at least the client's own bounded hint instead (Decision 0100).
READ_BACK_PAUSES_SECONDS = (0.5, 1.5, 3.5)
_T = TypeVar("_T")
_REFUSED_READS = (
    github_rest.NotSent,
    github_rest.DeadlineReached,
    github_rest.UnsafeRedirect,
    github_rest.OutsideOrigin,
)


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


def matches(document: object, expected: Mapping[str, Any]) -> bool:
    """Every expected field holds exactly the expected value, of the same type: a
    provider's `true` never stands for an id or attempt of 1, as Python's
    `True == 1` would let it (CodeAnt on #426)."""

    return isinstance(document, Mapping) and all(
        field in document
        and type(document[field]) is type(value)
        and document[field] == value
        for field, value in expected.items()
    )


def ours(run: object, app_id: int) -> bool:
    app = run.get("app") if isinstance(run, Mapping) else None
    return matches(app, {"id": app_id})


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


def _transient(error: github_rest.GitHubError) -> bool:
    """Whether a read may answer otherwise in a moment: no status (the transport, a
    bound, an unusable body), 404 while the provider's index lags its write, 429 or a
    server error. A refusal, a request never sent, the caller's spent deadline and a
    refused redirect or origin answer the same again (Decision 0135)."""

    if isinstance(error, _REFUSED_READS):
        return False
    status = error.status
    return status is None or status in (404, 429) or status >= 500


def within_bound(
    call: Callable[[], _T], again: Callable[[github_rest.GitHubError], bool]
) -> _T:
    """`call`'s answer, tried again after each of `READ_BACK_PAUSES_SECONDS` while
    `again` says its failure may pass, so at most four tries (Decision 0135). A pause
    is at least the failure's own bounded rate-limit hint, so a rate limit is waited
    out rather than spent inside its window (Decision 0100). The last failure is
    raised."""

    pauses = iter(READ_BACK_PAUSES_SECONDS)
    while True:
        try:
            return call()
        except github_rest.GitHubError as exc:
            pause = next(pauses, None) if again(exc) else None
            if pause is None:
                raise
            time.sleep(max(pause, exc.retry_after or 0.0))


def read_run(client: Any, repository: str, identifier: int) -> Mapping[str, Any]:
    """One check run, read natively by its id, a transient failure within the bound
    (Decision 0135)."""

    url = client.url(f"repos/{repository}/check-runs/{identifier}")
    try:
        run, _ = within_bound(lambda: client.get(url), _transient)
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


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def not_a_success(check: object, app_id: int, head: str, **fields: Any) -> str | None:
    """Why the run is not the pinned App's completed success of the check on the
    head, with any further fields exactly as given, or None when it is."""

    expected = {
        "name": CHECK_NAME,
        "head_sha": head,
        "status": "completed",
        "conclusion": "success",
        **fields,
    }
    if not ours(check, app_id) or not matches(check, expected):
        return "the check is not the pinned App's completed success on the head"
    return None


def recorded_digest(correlation: Mapping[str, Any]) -> str | None:
    """The digest of the evidence the run's evaluation rebuilt without the analyzer
    bundle, or None when the run records none."""

    value = correlation.get("unbundled_evidence_sha256")
    return value if isinstance(value, str) else None


def changed(
    rebuilt: Any, recorded: str, repository: str, number: int, head: str
) -> str | None:
    """Why the evidence rebuilt now is not the one the run's evaluation recorded, or
    None when it names this subject and has the recorded digest."""

    subject = _mapping(_mapping(rebuilt).get("subject"))
    request = _mapping(subject.get("change_request"))
    if (
        request.get("id") != str(number)
        or subject.get("head_commit") != head
        or subject.get("repository") != f"https://github.com/{repository}"
    ):
        return "the rebuilt evidence names another subject"
    if digest(rebuilt) != recorded:
        return "the subject changed since the evaluation"
    return None


def not_alone(observed: Any, number: int, head: str) -> str | None:
    """Why the complete open population does not show the pull request alone at its
    head (H1), or None when it does."""

    pulls = observed.get("pulls") if isinstance(observed, Mapping) else None
    if not isinstance(pulls, list) or observed.get("coverage") != "COMPLETE":
        return "the open population is not complete"
    heads = {
        item.get("pull_number"): item.get("head")
        for item in pulls
        if isinstance(item, Mapping)
    }
    if heads.get(number) != head:
        return "the open population does not show this pull request at its head"
    sharing = sorted(str(pull) for pull, at in heads.items() if at == head)
    if len(sharing) != 1:
        return f"the head is shared by #{', #'.join(sharing)}"
    return None


def open_population(pulls: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """The complete open population as the relay and the guard read it, from L1's
    enumeration of each open pull request with its head."""

    return {
        "coverage": "COMPLETE",
        "pulls": [
            {"pull_number": item["number"], "head": item["head_sha"]} for item in pulls
        ],
    }


def unbundled_evidence(
    collect: Callable[..., Any],
    reader: Any,
    *,
    repository: str,
    number: int,
    root: Path,
) -> Any:
    """The subject's evidence rebuilt now without the analyzer bundle: L1's snapshot
    with merge evidence, through the function `knowledge merge-evidence` calls, so
    its digest is comparable with the one the relay records."""

    # Imported here: the adapter needs the runtime lock (PyYAML, jsonschema), which
    # the importers of this module do not all install.
    from tools import merge_evidence_github

    snapshot = collect(
        reader,
        repository=repository,
        pull_number=number,
        observed_at=None,
        merge_evidence=True,
    )
    return merge_evidence_github.evidence_for(snapshot, project_root=root)


def authoritative(run: Mapping[str, Any]) -> bool:
    """Whether the run's external id is a verdict's, the digest of what the relay
    evaluated, never a pending, superseded, overtaken or incomplete run's."""

    external = run.get("external_id")
    return isinstance(external, str) and _SHA256.fullmatch(external) is not None


def _standing_digest(
    latest: Mapping[str, Any], app_id: int, head: str, revision: str
) -> str | None:
    """The digest the pinned App's completed authoritative success on the head
    records, when the protected revision given wrote it, else None."""

    if not_a_success(latest, app_id, head) is not None or not authoritative(latest):
        return None
    recorded = correlation_of(latest)
    if recorded is None or recorded["protected_revision"] != revision:
        return None
    return recorded_digest(recorded)


def equivalent(
    client: Any,
    repository: str,
    number: int,
    head: str,
    *,
    app_id: int,
    revision: str,
    rebuild: Callable[[], Any],
    observe: Callable[[], Any],
) -> bool:
    """Whether a fresh evaluation of the pull request at the head would repeat the
    pinned App's latest record there (Decision 0133): a completed authoritative
    success written from the protected revision given, recording the digest of the
    evidence rebuilt now, while the complete open population shows the pull request
    alone at its head. The head alone never proves it, nor a run of another App or a
    record without a digest. A latest view that cannot be read whole raises, as the
    reads do, and the caller evaluates."""

    latest = app_latest(client, repository, head, app_id)
    if latest is None:
        return False
    expected = _standing_digest(latest, app_id, head, revision)
    # The population before the rebuild: it is one listing, the rebuild many reads.
    if expected is None or not_alone(observe(), number, head) is not None:
        return False
    return changed(rebuild(), expected, repository, number, head) is None
