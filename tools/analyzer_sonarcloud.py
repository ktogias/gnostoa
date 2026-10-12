"""SonarCloud's finding inventory for one pull request's exact head (MA0 1b.3c,
#407; Decisions 0091 and 0112).

SonarCloud's issue search names no commit, and answers a pull request it never
analysed with an empty inventory (200, `total: 0`, measured 2026-10-12). So the
inventory is bound to a published report of the requested head before any issue
is read, and the binding is read again after the last page:

- SonarCloud's pull-request listing names the analysed head and its analysis
  date, the same both times;
- SonarCloud's own GitHub check runs for this pull request on the exact head,
  read completely, are all finished; the latest has a gate result, starts at
  that analysis date (as it did for all 44 listed pull requests on 2026-10-12),
  and is the same run, unchanged, both times;
- the project's Compute Engine tasks hold none of this pull request's that is
  queued, unfinished or failed, both times.

Whether those sources can show a newer, unfinished analysis of the same head is
not established. Before SonarCloud submits an analysis there is no task to see
(#424's took 28 s to submit), and a calibration sampled every 5 s missed its
3-second processing. So their silence is never what proves an analysis
finished. Under the owner's selection (R1), a fully read, bound inventory is
`COMPLETE` as the latest observed published report's, over the reads' own
interval, and its provenance keeps `unfinished_analysis: "UNOBSERVABLE"`, how it
was bound, and that the issue index is not versioned by analysis.

A task naming the pull request, with an analysis id, can be read in the project's
`current` task, but its association with the exact head's report is not
established, so no analysis id is claimed; the inputs that bound the report are
kept.

Every page is read until the count reaches the provider's total, and
SonarCloud's own bounds -- 500 issues a page, the first 10,000 results of a
search -- make a larger inventory `PARTIAL`. Nothing here proves that SonarCloud
indexed every issue of the report before the pages were read, nor that no other
computation ran meanwhile: only that the bound descriptors stayed the same.

The transport is the shared GitHub REST client on SonarCloud's origin (Decision
0100): its origin pin, redirect refusal, bounded exchange and credential
hygiene. The credential is the readback's own, `SONAR_TOKEN`; without it nothing
is read, although the project is public.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, NamedTuple, Protocol

from . import github_rest, sonarcloud_scope
from .analyzer_readback import (
    AnalyzerReadbackError,
    build_readback,
    coverage,
    deduplicate_findings,
    normalize_repository,
)
from .review_model import RFC3339Timestamp, parse_rfc3339

_API_ROOT = "https://sonarcloud.io"
_TOKEN_ENV = "SONAR_TOKEN"  # nosec B105 -- environment variable name, not a credential
_POLICY = github_rest.Policy(
    timeout_seconds=30, attempts=1, max_response_bytes=4_194_304
)
_PAGE_SIZE = 500
_WINDOW = 10_000
# Every issue that is not fixed: an acceptance or a false-positive marking in
# SonarCloud is not a waiver of M17 (the GUIDANCE_REQUEST on #407, 6119610829).
_ISSUE_STATUSES = ("OPEN", "CONFIRMED", "ACCEPTED", "FALSE_POSITIVE")
_PROVIDER = "sonarcloud"
_ADAPTER = "sonarcloud-web-api/v1"
_SURFACE = "sonarcloud-web-api"
_SHA40 = re.compile(r"[0-9a-f]{40}")
# SonarCloud's GitHub check run, whose result is also the quality-gate item's
# (policy/merge-required-checks.yaml; G1 and Q-a, #424).
CHECK_APP_ID = sonarcloud_scope.CHECK_APP_ID
CHECK_NAME = sonarcloud_scope.CHECK_NAME
# A finished analysis has a gate result; any other conclusion is no report.
_PUBLISHED = frozenset({"success", "failure"})
# Whether a newer, unfinished analysis of the same head can be observed: no source
# read here is established to show one -- SonarCloud posts its check run only once
# finished, no task exists before an analysis is submitted, and only a task's
# seconds of processing showed in the queue (#424's own) -- so it cannot, and the
# provenance says UNOBSERVABLE (the PAO's escalation on #424, 6120941468).
_UNFINISHED_ANALYSIS_OBSERVABLE = False
# R1, the owner's selection (6122025441 on #424): COMPLETE covers the fully
# enumerated, PR-scoped inventory of the latest observed published report of this
# repository, pull request and head, over the reads' own interval. It does not
# make unfinished work observable -- that stays False above, and UNOBSERVABLE in
# the provenance -- claims no snapshot versioned by an analysis id, and is no
# freshness lease.
_COMPLETE_FOR_LATEST_PUBLISHED_REPORT = True


class ProviderReadFailure(RuntimeError):
    def __init__(self, kind: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class JsonReader(Protocol):
    def get(self, url: str) -> Mapping[str, Any]: ...


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _failure(error: github_rest.GitHubError) -> ProviderReadFailure:
    """The shared client's failure, as SonarCloud's kind of failure."""
    status = error.status
    if status in {401, 403}:
        return ProviderReadFailure(
            "AUTH", "SonarCloud authentication unavailable", status=status
        )
    if status == 429:
        return ProviderReadFailure(
            "RATE_LIMIT", "SonarCloud API rate limited", status=status
        )
    if status is not None:
        return ProviderReadFailure(
            "UNAVAILABLE", f"SonarCloud API HTTP {status}", status=status
        )
    if (
        isinstance(
            error,
            (
                github_rest.MalformedAnswer,
                github_rest.ResponseTooLarge,
                github_rest.OutsideOrigin,
                github_rest.UnsafeRedirect,
            ),
        )
        or str(error) == "GitHub request failed validation"
    ):
        return ProviderReadFailure("ERROR", "SonarCloud API answer is unusable")
    return ProviderReadFailure("UNAVAILABLE", "SonarCloud API unavailable")


class SonarCloudRestClient:
    """The shared GitHub REST client on SonarCloud's origin, failing with
    SonarCloud's kinds."""

    def __init__(self, token: str) -> None:
        try:
            self._client = github_rest.GitHubRestClient(
                token,
                api_root=_API_ROOT,
                user_agent="gnostoa-analyzer-readback",
                policy=_POLICY,
            )
        except github_rest.GitHubError:
            raise ProviderReadFailure(
                "AUTH",
                "SonarCloud credential is malformed"
                if token
                else "SonarCloud authentication unavailable",
            ) from None

    @classmethod
    def from_environment(cls) -> SonarCloudRestClient:
        return cls(os.environ.get(_TOKEN_ENV, ""))

    def get(self, url: str) -> Mapping[str, Any]:
        try:
            document, _ = self._client.get(url)
        except github_rest.GitHubError as error:
            raise _failure(error) from error
        if not isinstance(document, Mapping):
            raise ProviderReadFailure(
                "ERROR", "SonarCloud API response must be an object"
            )
        return document


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderReadFailure("ERROR", f"SonarCloud {label} is malformed")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProviderReadFailure("ERROR", f"SonarCloud {label} is malformed")
    return value


def _count(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ProviderReadFailure("ERROR", f"SonarCloud {label} is malformed")
    return value


class _Analysis(NamedTuple):
    """The pull request's analysed head, as SonarCloud's listing names it."""

    head: str
    date: str
    pull_request_id: str


class _Subject(NamedTuple):
    project: str
    pull: str
    href: str


def _subject(repository: str, pull_number: int) -> _Subject:
    try:
        normalized = normalize_repository(repository)
    except AnalyzerReadbackError as exc:
        raise ProviderReadFailure("ERROR", "repository identity is unsafe") from exc
    owner, name = normalized.split("/", 1)
    # SonarCloud's key for an imported GitHub repository; the listing's URL then
    # proves it is this repository's.
    return _Subject(
        sonarcloud_scope.project_key(f"{owner}/{name}"),
        str(pull_number),
        f"https://github.com/{normalized}/pull/{pull_number}",
    )


def _listing_url(subject: _Subject) -> str:
    query = urllib.parse.urlencode({"project": subject.project})
    return f"{_API_ROOT}/api/project_pull_requests/list?{query}"


def _issues_url(subject: _Subject, page: int) -> str:
    query = urllib.parse.urlencode(
        {
            "componentKeys": subject.project,
            "pullRequest": subject.pull,
            "issueStatuses": ",".join(_ISSUE_STATUSES),
            "ps": _PAGE_SIZE,
            "p": page,
        }
    )
    return f"{_API_ROOT}/api/issues/search?{query}"


def _analysis(document: Mapping[str, Any], subject: _Subject) -> _Analysis | None:
    """The listing's one entry for the pull request, or None when SonarCloud has
    not analysed it. The listing ignores any filter, so the entry is chosen here."""

    entries = document.get("pullRequests")
    if not isinstance(entries, list):
        raise ProviderReadFailure(
            "ERROR", "SonarCloud pull request listing is malformed"
        )
    matches = [
        entry
        for entry in (_mapping(item, "pull request entry") for item in entries)
        if entry.get("key") == subject.pull
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise ProviderReadFailure("ERROR", "SonarCloud lists the pull request twice")
    entry = matches[0]
    if _text(entry.get("url"), "pull request URL").rstrip("/") != subject.href:
        raise ProviderReadFailure(
            "ERROR", "SonarCloud's pull request is not this repository's"
        )
    head = _text(
        _mapping(entry.get("commit"), "pull request commit").get("sha"), "head"
    )
    if _SHA40.fullmatch(head) is None:
        raise ProviderReadFailure("ERROR", "SonarCloud head is malformed")
    return _Analysis(
        head,
        _text(entry.get("analysisDate"), "analysis date"),
        _text(entry.get("pullRequestId"), "pull request id"),
    )


def _finding(item: Mapping[str, Any], subject: _Subject) -> dict[str, Any]:
    key = _text(item.get("key"), "issue key")
    if (
        item.get("pullRequest") != subject.pull
        or item.get("project") != subject.project
    ):
        raise ProviderReadFailure("ERROR", "SonarCloud issue is another subject's")
    prefix = f"{subject.project}:"
    component = _text(item.get("component"), "issue component")
    if not component.startswith(prefix) or component == prefix:
        raise ProviderReadFailure("ERROR", "SonarCloud issue is outside the project")
    status = _text(item.get("issueStatus"), "issue status")
    if status not in _ISSUE_STATUSES:
        raise ProviderReadFailure("ERROR", "SonarCloud issue status was not asked for")
    finding: dict[str, Any] = {
        "id": key,
        "message": _text(item.get("message"), "issue message"),
        "path": component[len(prefix) :],
        "state": status.lower(),
        "native_ref": key,
        "provenance": [{"surface": _SURFACE, "reference": key}],
        "native": {"issue_status": status},
    }
    for source, target in (
        ("rule", "rule"),
        ("severity", "severity"),
        ("type", "category"),
    ):
        value = item.get(source)
        if isinstance(value, str) and value:
            finding[target] = value
    text_range = item.get("textRange")
    if isinstance(text_range, Mapping):
        lines = {
            target: text_range.get(source)
            for source, target in (("startLine", "start_line"), ("endLine", "end_line"))
        }
        location = {k: v for k, v in lines.items() if type(v) is int and v > 0}
        if location:
            finding["range"] = location
    return finding


class _Pages:
    """What the issue pages gave: their findings, their count and the total."""

    def __init__(self) -> None:
        self.findings: list[dict[str, Any]] = []
        self.count = 0
        self.total: int | None = None
        self.read = 0
        self.head: str | None = None


def _page(
    document: Mapping[str, Any], index: int, pages: _Pages, subject: _Subject
) -> list[Any]:
    """One page's issues, after its echo and its total are checked."""

    paging = _mapping(document.get("paging"), "paging")
    if paging.get("pageIndex") != index or paging.get("pageSize") != _PAGE_SIZE:
        raise ProviderReadFailure("ERROR", "SonarCloud answered another page")
    total = _count(paging.get("total"), "paging total")
    if pages.total is not None and total != pages.total:
        raise ProviderReadFailure(
            "ERROR", "SonarCloud issue total changed during pagination"
        )
    pages.total = total
    issues = document.get("issues")
    if not isinstance(issues, list):
        raise ProviderReadFailure("ERROR", "SonarCloud issue page is malformed")
    pages.findings.extend(_finding(_mapping(i, "issue"), subject) for i in issues)
    return issues


def _read_pages(client: JsonReader, subject: _Subject, pages: _Pages) -> None:
    """Every page, until the count reaches the total. A short page before it, or
    a count past it, is an error; a total past SonarCloud's window stops after
    the first page."""

    for index in range(1, _WINDOW // _PAGE_SIZE + 1):
        issues = _page(client.get(_issues_url(subject, index)), index, pages, subject)
        pages.read += 1
        pages.count += len(issues)
        total = pages.total
        if total is None or total > _WINDOW or pages.count == total:
            return
        if pages.count > total or len(issues) < _PAGE_SIZE:
            raise ProviderReadFailure("ERROR", "SonarCloud issue pages do not add up")
    raise ProviderReadFailure(
        "ERROR", "SonarCloud issue pagination exceeded its window"
    )


class _Read(NamedTuple):
    """One readback's subject and observation time, for the documents built from it."""

    repository: str
    pull_number: int
    requested_head: str
    observed_at: str


def _document(
    read: _Read,
    *,
    completeness: str,
    run_state: str,
    coverage_record: Mapping[str, Any],
    findings: list[dict[str, Any]] | None = None,
    observed_head: str | None = None,
    native: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_readback(
        provider=_PROVIDER,
        adapter=_ADAPTER,
        repository=read.repository,
        pull_number=read.pull_number,
        requested_head=read.requested_head,
        observed_head=observed_head,
        analysis_id=None,
        scope="DIFF",
        completeness=completeness,
        native_mode="PULL_REQUEST",
        observed_at=read.observed_at,
        run_state=run_state,
        coverage_record=coverage_record,
        findings=findings or [],
        native=native,
    )


def _failed(
    read: _Read,
    error: ProviderReadFailure,
    *,
    pages: int,
    findings: list[dict[str, Any]],
    observed_head: str | None,
) -> dict[str, Any]:
    retained = deduplicate_findings(findings)
    if error.kind == "RATE_LIMIT":
        status, reason = "RATE_LIMITED", "RATE_LIMITED"
    elif error.kind == "AUTH":
        status, reason = "UNAVAILABLE", "AUTH_UNAVAILABLE"
    elif error.kind == "UNAVAILABLE":
        status, reason = "UNAVAILABLE", "READBACK_UNAVAILABLE"
    else:
        status, reason = "ERROR", "PROVIDER_ERROR"
    return _document(
        read,
        completeness="AUTH_UNAVAILABLE"
        if error.kind == "AUTH"
        else "READBACK_UNAVAILABLE",
        run_state="OBSERVED" if observed_head else "UNKNOWN",
        coverage_record=coverage(
            status, pages=pages, count=len(retained), reason=reason
        ),
        findings=retained,
        observed_head=observed_head,
    )


def _ambiguous(
    read: _Read, reason: str, *, pages: int, observed_head: str | None
) -> dict[str, Any]:
    return _document(
        read,
        completeness="AMBIGUOUS",
        run_state="OBSERVED" if observed_head else "UNKNOWN",
        coverage_record=coverage("INCOMPLETE", pages=pages, count=0, reason=reason),
        observed_head=observed_head,
    )


def _inventory(
    read: _Read,
    analysis: _Analysis,
    report: Mapping[str, Any],
    pages: _Pages,
    acquisition: tuple[str, str, int],
) -> dict[str, Any]:
    """The pages' inventory, once its report stayed bound: never more than PARTIAL
    unless its unique issues are exactly the provider's total. Then it is COMPLETE
    as the latest observed published report's (R1), with how it was bound, what it
    does not claim, and when it was read; without R1 it would be PARTIAL (R4)."""

    first_read_at, last_read_at, reads = acquisition
    retained = deduplicate_findings(pages.findings)
    total = pages.total if pages.total is not None else 0
    native: dict[str, Any] = {
        "pull_request_id": analysis.pull_request_id,
        "analysis_date": analysis.date,
        "check_run": {
            "id": report.get("id"),
            "started_at": report.get("started_at"),
            "conclusion": report.get("conclusion"),
        },
    }
    if not _UNFINISHED_ANALYSIS_OBSERVABLE:
        native["unfinished_analysis"] = "UNOBSERVABLE"
    if total > _WINDOW:
        status, reason = "PARTIAL", "PROVIDER_WINDOW_EXCEEDED"
    elif len(retained) != total:
        status, reason = "ERROR", "COUNT_TOTAL_MISMATCH"
    elif not (_UNFINISHED_ANALYSIS_OBSERVABLE or _COMPLETE_FOR_LATEST_PUBLISHED_REPORT):
        status, reason = "PARTIAL", "UNFINISHED_ANALYSIS_UNOBSERVABLE"
    else:
        native["binding"] = "listing+pr-qualified-check-run"
        native["source_limitation"] = "issue-index-not-analysis-versioned"
        native["acquisition"] = {
            "first_read_at": first_read_at,
            "last_read_at": last_read_at,
        }
        return _document(
            read,
            completeness="FULL_RUN",
            run_state="COMPLETE",
            coverage_record=coverage(
                "COMPLETE", pages=reads, count=len(retained), total=total
            ),
            findings=retained,
            observed_head=analysis.head,
            native=native,
        )
    return _document(
        read,
        completeness="READBACK_UNAVAILABLE",
        run_state="OBSERVED",
        coverage_record=coverage(
            status, pages=reads, count=len(retained), total=total, reason=reason
        ),
        findings=retained,
        observed_head=analysis.head,
        native=native if reason == "UNFINISHED_ANALYSIS_UNOBSERVABLE" else None,
    )


class _Counted:
    """The reader, counting the reads that answered, for the coverage's pages."""

    def __init__(self, client: JsonReader) -> None:
        self._client = client
        self.reads = 0

    def get(self, url: str) -> Mapping[str, Any]:
        document = self._client.get(url)
        self.reads += 1
        return document


def _queue_url(subject: _Subject) -> str:
    query = urllib.parse.urlencode({"component": subject.project})
    return f"{_API_ROOT}/api/ce/component?{query}"


# SonarCloud writes its offset in the basic form, `+0000`; GitHub writes RFC 3339.
_BASIC_OFFSET = re.compile(r"([+-]\d{2})(\d{2})\Z")


def _instant(value: object, label: str) -> RFC3339Timestamp:
    """An exact instant, its fraction at any precision (CodeAnt and cubic on
    #424), read by the review model's RFC 3339 parser."""

    try:
        return parse_rfc3339(_BASIC_OFFSET.sub(r"\1:\2", _text(value, label)))
    except ValueError as exc:
        raise ProviderReadFailure("ERROR", f"SonarCloud {label} is malformed") from exc


def _scope(run: Mapping[str, Any], subject: _Subject) -> str | None:
    """Which analysis a SonarCloud check run names (`sonarcloud_scope`), or None
    for a run that is not SonarCloud's check."""

    app = run.get("app")
    if not isinstance(app, Mapping) or app.get("id") != CHECK_APP_ID:
        return None
    if run.get("name") != CHECK_NAME:
        return None
    return sonarcloud_scope.details_scope(
        run.get("details_url"), project=subject.project, pull=subject.pull
    )


def _runs_of(
    check_runs: Sequence[object], subject: _Subject
) -> list[Mapping[str, Any]] | str:
    """This pull request's SonarCloud runs, or why they cannot be told apart: a run
    whose details are malformed might be this pull request's."""

    scoped = [
        (_scope(run, subject), run)
        for run in (_mapping(item, "check run") for item in check_runs)
    ]
    if any(scope == "malformed" for scope, _ in scoped):
        return "REPORT_ASSOCIATION_AMBIGUOUS"
    return [run for scope, run in scoped if scope == "ours"]


def _report(
    check_runs: Sequence[object], subject: _Subject, analysis: _Analysis
) -> Mapping[str, Any] | str:
    """The exact head's finished SonarCloud run for this pull request that started
    at the listed analysis, or the reason there is none. Every one of its runs
    must be finished, as every current run must pass for a check item, and a tie
    on the latest start leaves the association unknown: no id decides it (PAO
    6119999041 on #407)."""

    runs = _runs_of(check_runs, subject)
    if isinstance(runs, str):
        return runs
    if not runs:
        return "ANALYSIS_NOT_PUBLISHED"
    if any(run.get("status") != "completed" for run in runs):
        return "ANALYSIS_IN_PROGRESS"
    starts = [(_instant(run.get("started_at"), "check run start"), run) for run in runs]
    latest_start = max(start for start, _ in starts)
    latest = [run for start, run in starts if start == latest_start]
    if len(latest) > 1:
        return "REPORT_ASSOCIATION_AMBIGUOUS"
    if latest[0].get("conclusion") not in _PUBLISHED:
        return "ANALYSIS_NOT_PUBLISHED"
    if latest_start != _instant(analysis.date, "analysis date"):
        return "REPORT_ASSOCIATION_MISMATCH"
    return latest[0]


def _identity(value: object) -> str | None:
    """A task's pull request or branch, or None when it names none: an empty or
    blank value names nothing (cubic on #424)."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return str(value)


def _unfinished(document: Mapping[str, Any], subject: _Subject) -> str | None:
    """Why the project's tasks say this pull request's newest analysis may not be
    its published report, or None. A queued task may be its own, or name neither a
    branch nor a pull request. `current` is the project's last task, a pull
    request's included (#424's own, 2026-10-12), so only one naming this pull
    request counts: unfinished, or failed or cancelled (CodeReviewBot and CodeAnt
    on #424)."""

    queue = document.get("queue")
    if not isinstance(queue, list):
        raise ProviderReadFailure("ERROR", "SonarCloud task queue is malformed")
    for item in queue:
        task = _mapping(item, "queued task")
        pull, branch = _identity(task.get("pullRequest")), _identity(task.get("branch"))
        if pull == subject.pull or (pull is None and branch is None):
            return "ANALYSIS_IN_PROGRESS"
    current = document.get("current")
    if current is None:
        return None
    task = _mapping(current, "current task")
    pull = _identity(task.get("pullRequest"))
    if pull != subject.pull or task.get("status") == "SUCCESS":
        return None
    if task.get("status") in {"PENDING", "IN_PROGRESS"}:
        return "ANALYSIS_IN_PROGRESS"
    return "ANALYSIS_NOT_PUBLISHED"


def _bound(
    reader: _Counted,
    read: _Read,
    check_runs: Callable[[], Sequence[object]],
    pages: _Pages,
) -> dict[str, Any]:
    """The inventory of the requested head's published report: bound by the
    listing, the check runs and the queue before the pages, and by all three again
    after them."""

    subject = _subject(read.repository, read.pull_number)
    listing, queue = _listing_url(subject), _queue_url(subject)
    # The reads' own interval, before the first and after the last (R1).
    first_read_at = _now()
    before = _analysis(reader.get(listing), subject)
    if before is None:
        return _ambiguous(
            read, "PULL_REQUEST_NOT_ANALYZED", pages=reader.reads, observed_head=None
        )
    if before.head != read.requested_head:
        return _ambiguous(
            read, "SUBJECT_MISMATCH", pages=reader.reads, observed_head=before.head
        )
    pages.head = before.head
    report = _report(check_runs(), subject, before)
    if isinstance(report, str):
        return _ambiguous(read, report, pages=reader.reads, observed_head=before.head)
    unfinished = _unfinished(reader.get(queue), subject)
    if unfinished is not None:
        return _ambiguous(
            read, unfinished, pages=reader.reads, observed_head=before.head
        )
    _read_pages(reader, subject, pages)
    after = _analysis(reader.get(listing), subject)
    if after != before:
        return _ambiguous(
            read,
            "SUBJECT_CHANGED_DURING_READBACK",
            pages=reader.reads,
            observed_head=None if after is None else after.head,
        )
    published = _report(check_runs(), subject, before)
    if isinstance(published, str):
        return _ambiguous(
            read, published, pages=reader.reads, observed_head=before.head
        )
    if published != report:
        return _ambiguous(
            read,
            "REPORT_CHANGED_DURING_READBACK",
            pages=reader.reads,
            observed_head=before.head,
        )
    unfinished = _unfinished(reader.get(queue), subject)
    if unfinished is not None:
        return _ambiguous(
            read, unfinished, pages=reader.reads, observed_head=before.head
        )
    last_read_at = _now()
    return _inventory(
        read, before, report, pages, (first_read_at, last_read_at, reader.reads)
    )


def read_pull_request(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    check_runs: Callable[[], Sequence[Mapping[str, Any]]],
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Read one pull request's SonarCloud inventory, without letting a provider
    failure or a normalization conflict abort the bundle. ``check_runs`` reads
    every SonarCloud check run on the requested head, completely: it is called
    before the issue pages and again after them, and raises
    ``ProviderReadFailure`` when it cannot."""

    read = _Read(repository, pull_number, requested_head, observed_at or _now())
    reader, pages = _Counted(client), _Pages()
    try:
        try:
            return _bound(reader, read, check_runs, pages)
        except ProviderReadFailure as exc:
            # Recording the failure normalizes what was read, which can conflict
            # too, so it is guarded as the read is (CodeAnt on #424).
            return _failed(
                read,
                exc,
                pages=reader.reads,
                findings=pages.findings,
                observed_head=pages.head,
            )
    except AnalyzerReadbackError:
        return _document(
            read,
            completeness="READBACK_UNAVAILABLE",
            run_state="UNKNOWN",
            coverage_record=coverage(
                "ERROR", pages=0, count=0, reason="NORMALIZATION_ERROR"
            ),
        )
