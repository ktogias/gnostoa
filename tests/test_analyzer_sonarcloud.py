from __future__ import annotations

import contextlib
import http.client
import io
import os
import unittest
import urllib.error
import urllib.parse
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any
from unittest import mock

from tools import analyzer_readback, analyzer_sonarcloud

ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40
OTHER_HEAD = "b" * 40
OBSERVED = "2026-10-12T07:30:00Z"
PULL_ID = "882e653f-7208-4ec7-a92e-4a139efba1c8"
ANALYSED = "2026-10-11T23:57:56+0000"
LIST_URL = (
    "https://sonarcloud.io/api/project_pull_requests/list?project=ktogias_gnostoa"
)
ISSUES_PATH = "/api/issues/search"
# SonarCloud's credential variable, by name only (Codacy's Bandit B105 on #424).
SONAR_ENV = "SONAR_TOKEN"
QUEUE_URL = "https://sonarcloud.io/api/ce/component?component=ktogias_gnostoa"
CHECK_ID = 114609123587


def _check(
    *,
    started: str = "2026-10-11T23:57:56Z",
    status: str = "completed",
    conclusion: str | None = "success",
    pull: str = "312",
    app: int = 12526,
    name: str = "SonarCloud Code Analysis",
    check_id: int = CHECK_ID,
) -> dict[str, Any]:
    """SonarCloud's GitHub check run on the head, as GitHub answered for #423's
    (check 114609123587): it starts at the analysis date of the pull request it
    names in its `details_url` (44 of 44 listed pull requests, 2026-10-12)."""

    return {
        "id": check_id,
        "name": name,
        "head_sha": HEAD,
        "status": status,
        "conclusion": conclusion,
        "started_at": started,
        "completed_at": "2026-10-11T23:58:35Z" if status == "completed" else None,
        "details_url": f"https://sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest={pull}",
        "app": {"id": app, "slug": "sonarqubecloud"},
        "output": {"title": "Quality Gate passed"},
    }


def _queue(*tasks: dict[str, Any]) -> dict[str, Any]:
    """`api/ce/component` as SonarCloud answered on 2026-10-12: main's last task
    and the project's queue (anonymous calibration)."""

    return {
        "queue": list(tasks),
        "current": {
            "id": "AaEu5x63UmNMvf-vXplk",
            "type": "REPORT",
            "componentKey": "ktogias_gnostoa",
            "analysisId": "43392b27-595f-4a0b-91c5-65df38a82a9b",
            "status": "SUCCESS",
        },
    }


def _task(status: str = "PENDING", **identity: str) -> dict[str, Any]:
    return {
        "id": "AaTask",
        "type": "REPORT",
        "componentKey": "ktogias_gnostoa",
        "status": status,
        **identity,
    }


def _entry(
    head: str = HEAD,
    *,
    key: str = "312",
    analysed: str = ANALYSED,
    url: str = "https://github.com/ktogias/gnostoa/pull/312",
) -> dict[str, Any]:
    """One `project_pull_requests/list` entry, as SonarCloud answered for #423 on
    2026-10-12 (anonymous calibration)."""

    return {
        "key": key,
        "title": "A change",
        "branch": "a-branch",
        "base": "main",
        "status": {
            "qualityGateStatus": "OK",
            "bugs": 0,
            "vulnerabilities": 0,
            "codeSmells": 0,
        },
        "analysisDate": analysed,
        "url": url,
        "target": "main",
        "commit": {"sha": head, "author": {"name": "Anonymous User"}},
        "pullRequestUuidV1": "AaEsz_5YUmNMvf-vXXzW",
        "pullRequestId": PULL_ID,
    }


def _listing(*entries: dict[str, Any]) -> dict[str, Any]:
    """The whole listing: SonarCloud ignores any filter and returns every pull
    request, so another one is always present."""

    return {"pullRequests": [_entry(OTHER_HEAD, key="311"), *entries]}


def _issue(
    key: str,
    line: int = 4,
    *,
    pull: str = "312",
    status: str = "OPEN",
    component: str = "ktogias_gnostoa:tools/example.py",
    project: str = "ktogias_gnostoa",
) -> dict[str, Any]:
    """One issue as `api/issues/search` answered for #353 (anonymous calibration)."""

    return {
        "key": key,
        "rule": "python:S5778",
        "severity": "MAJOR",
        "component": component,
        "project": project,
        "line": line,
        "hash": "0b1f",
        "textRange": {
            "startLine": line,
            "endLine": line + 3,
            "startOffset": 8,
            "endOffset": 10,
        },
        "flows": [],
        "status": status,
        "message": f"Refactor this code {key}",
        "effort": "5min",
        "debt": "5min",
        "tags": [],
        "creationDate": "2026-10-07T09:51:01+0000",
        "updateDate": "2026-10-07T09:51:01+0000",
        "type": "CODE_SMELL",
        "organization": "ktogias",
        "pullRequest": pull,
        "cleanCodeAttribute": "CLEAR",
        "cleanCodeAttributeCategory": "INTENTIONAL",
        "impacts": [{"softwareQuality": "MAINTAINABILITY", "severity": "MEDIUM"}],
        "issueStatus": status,
        "projectName": "gnostoa",
    }


def _page(
    issues: list[dict[str, Any]], *, total: int, index: int = 1, size: int = 500
) -> dict[str, Any]:
    return {
        "total": total,
        "p": index,
        "ps": size,
        "paging": {"pageIndex": index, "pageSize": size, "total": total},
        "effortTotal": 0,
        "debtTotal": 0,
        "issues": issues,
        "components": [],
        "organizations": [{"key": "ktogias", "name": "Konstantinos Togias"}],
        "facets": [],
    }


class _SonarFake:
    """Answers the listing in order, and each issue page by its index. It refuses
    what SonarCloud refuses: a page size above 500 or a page past the 10,000-result
    window (both 400, measured 2026-10-12)."""

    def __init__(
        self,
        listings: list[Any],
        pages: Mapping[int, Any] | None = None,
        queues: list[Any] | None = None,
    ) -> None:
        self.listings = listings
        self.pages = dict(pages or {})
        self.queues = [_queue(), _queue()] if queues is None else queues
        self.calls: list[str] = []
        self.queries: list[dict[str, str]] = []

    def get(self, url: str) -> Mapping[str, Any]:
        self.calls.append(url)
        if url == LIST_URL:
            if not self.listings:
                raise AssertionError("no remaining listing")
            value = self.listings.pop(0)
        elif url == QUEUE_URL:
            if not self.queues:
                raise AssertionError("no remaining queue")
            value = self.queues.pop(0)
        else:
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme, parsed.netloc, parsed.path) != (
                "https",
                "sonarcloud.io",
                ISSUES_PATH,
            ):
                raise AssertionError(f"unexpected SonarCloud URL: {url}")
            query = dict(urllib.parse.parse_qsl(parsed.query, strict_parsing=True))
            self.queries.append(query)
            size, index = int(query["ps"]), int(query["p"])
            if size > 500 or index * size > 10_000:
                raise analyzer_sonarcloud.ProviderReadFailure(
                    "UNAVAILABLE", "SonarCloud API HTTP 400", status=400
                )
            if (query["componentKeys"], query["pullRequest"]) != (
                "ktogias_gnostoa",
                "312",
            ):
                raise AssertionError(f"another subject: {url}")
            value = self.pages[index]
        if isinstance(value, BaseException):
            raise value
        return value


def _read(client: _SonarFake, *collections: list[dict[str, Any]]) -> dict[str, Any]:
    """The readback, with the exact head's SonarCloud runs read as the first of
    ``collections`` before the pages and as each later one after them; one
    collection, or none (a single finished run), is read both times."""

    remaining = list(collections) or [[_check()]]

    def check_runs() -> list[dict[str, Any]]:
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    return analyzer_sonarcloud.read_pull_request(
        client,
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        check_runs=check_runs,
        observed_at=OBSERVED,
    )


def _issues(prefix: str, count: int) -> list[dict[str, Any]]:
    return [_issue(f"{prefix}-{n:05d}", n + 1) for n in range(count)]


class SonarCloudReadbackTests(unittest.TestCase):
    """MA0 1b.3c (#407 6119460225, lineage 6119607885): SonarCloud's finding
    inventory for one pull request's exact head."""

    def assertBound(self, document: Mapping[str, Any]) -> None:
        """Every observable fact bound the latest observed published report and
        every page was read: COMPLETE under the owner's selection (R1, 6122025441
        on #424), with the unobservable dimension kept in the provenance."""
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(document["coverage"]["total"], document["coverage"]["count"])
        self.assertEqual("UNOBSERVABLE", document["native"]["unfinished_analysis"])
        self.assertEqual(
            "listing+pr-qualified-check-run", document["native"]["binding"]
        )

    def test_an_exact_head_inventory_is_bound_and_complete(self) -> None:
        """C3, C4, C5, C6: the head bound before and after the pages, every page
        read, and each issue normalized: COMPLETE as the latest observed published
        report's (R1), never as an absence of unpublished work."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {1: _page([_issue("AaEDxiUuswWGEwq5tyXk", 396)], total=1)},
        )
        document = _read(client)
        self.assertEqual("sonarcloud", document["provider"])
        self.assertEqual("sonarcloud-web-api/v1", document["adapter"])
        self.assertEqual("DIFF", document["scope"])
        self.assertEqual("PULL_REQUEST", document["native_mode"])
        self.assertBound(document)
        self.assertEqual("COMPLETE", document["run_state"])
        self.assertEqual(HEAD, document["observed_head"])
        # No provider-issued analysis or task id is readable with Browse rights,
        # so none is claimed; the inputs that bound the report are kept.
        self.assertNotIn("analysis_id", document)
        self.assertEqual(
            {
                "pull_request_id": PULL_ID,
                "analysis_date": ANALYSED,
                "check_run": {
                    "id": CHECK_ID,
                    "started_at": "2026-10-11T23:57:56Z",
                    "conclusion": "success",
                },
                "unfinished_analysis": "UNOBSERVABLE",
                "binding": "listing+pr-qualified-check-run",
                "source_limitation": "issue-index-not-analysis-versioned",
            },
            {k: v for k, v in document["native"].items() if k != "acquisition"},
        )
        self.assertEqual(
            {"first_read_at", "last_read_at"}, set(document["native"]["acquisition"])
        )
        self.assertEqual(
            {"status": "COMPLETE", "pages": 5, "count": 1, "total": 1},
            document["coverage"],
        )
        self.assertEqual(
            [
                {
                    "id": "AaEDxiUuswWGEwq5tyXk",
                    "message": "Refactor this code AaEDxiUuswWGEwq5tyXk",
                    "rule": "python:S5778",
                    "severity": "MAJOR",
                    "category": "CODE_SMELL",
                    "path": "tools/example.py",
                    "state": "open",
                    "native_ref": "AaEDxiUuswWGEwq5tyXk",
                    "range": {"start_line": 396, "end_line": 399},
                    "provenance": [
                        {
                            "surface": "sonarcloud-web-api",
                            "reference": "AaEDxiUuswWGEwq5tyXk",
                        }
                    ],
                    "native": {"issue_status": "OPEN"},
                }
            ],
            document["findings"],
        )
        # The head and the queue are read before any issue, and again after the
        # last page.
        self.assertEqual([LIST_URL, QUEUE_URL], client.calls[:2])
        self.assertEqual([LIST_URL, QUEUE_URL], client.calls[-2:])
        self.assertEqual({"1"}, {q["p"] for q in client.queries})
        self.assertEqual({"500"}, {q["ps"] for q in client.queries})
        analyzer_readback.parse_readback(document)

    def test_r1_a_bound_inventory_is_complete_with_its_limits(self) -> None:
        """R1, the owner's selection (6122025441 on #424): the fully enumerated
        PR-scoped inventory of the latest observed published report of this
        repository, pull request and head is COMPLETE. Its provenance says how it
        was bound, what it does not claim, and when it was read."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {1: _page(_issues("open", 3), total=3)},
        )
        with mock.patch.object(
            analyzer_sonarcloud,
            "_now",
            side_effect=["2026-10-12T10:00:01Z", "2026-10-12T10:00:04Z"],
        ):
            document = _read(client)
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["run_state"])
        self.assertEqual(
            {"status": "COMPLETE", "pages": 5, "count": 3, "total": 3},
            document["coverage"],
        )
        self.assertEqual(3, len(document["findings"]))
        self.assertNotIn("analysis_id", document)
        self.assertEqual(
            {
                "pull_request_id": PULL_ID,
                "analysis_date": ANALYSED,
                "check_run": {
                    "id": CHECK_ID,
                    "started_at": "2026-10-11T23:57:56Z",
                    "conclusion": "success",
                },
                "unfinished_analysis": "UNOBSERVABLE",
                "binding": "listing+pr-qualified-check-run",
                "source_limitation": "issue-index-not-analysis-versioned",
                # The reads' own times, before the first and after the last, never
                # the analysis date or the check's start.
                "acquisition": {
                    "first_read_at": "2026-10-12T10:00:01Z",
                    "last_read_at": "2026-10-12T10:00:04Z",
                },
            },
            document["native"],
        )

    def test_r1_the_clean_zero_case_is_complete(self) -> None:
        """R1: a bound, authenticated first page with no issues and a total of 0
        terminates the pagination: COMPLETE, with nothing to deny on."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
        )
        document = _read(client)
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual(
            {"status": "COMPLETE", "pages": 5, "count": 0, "total": 0},
            document["coverage"],
        )
        self.assertEqual([], document["findings"])
        self.assertEqual("UNOBSERVABLE", document["native"]["unfinished_analysis"])

    def test_r1_the_acquisition_spans_every_read(self) -> None:
        """R1: the first time is taken before the listing's first read and the last
        after the final queue read, so the interval covers every bracket read."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
        )
        calls: list[int] = []

        def clock() -> str:
            calls.append(len(client.calls))
            return f"2026-10-12T10:00:0{len(calls)}Z"

        with mock.patch.object(analyzer_sonarcloud, "_now", clock):
            document = _read(client)
        # Before any read, and after all five.
        self.assertEqual([0, 5], calls)
        self.assertEqual(
            {
                "first_read_at": "2026-10-12T10:00:01Z",
                "last_read_at": "2026-10-12T10:00:02Z",
            },
            document["native"]["acquisition"],
        )

    def test_an_observable_unfinished_analysis_is_not_that_case(self) -> None:
        """R1 and R4 alike: an unfinished analysis that is observed stays
        `AMBIGUOUS`; R1 changes only the unobservable case."""
        for name, queues, checks in (
            ("a queued task", [_queue(_task(pullRequest="312"))], [_check()]),
            (
                "an unfinished run",
                None,
                [_check(status="in_progress", conclusion=None)],
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page(_issues("open", 3), total=3)},
                    queues,
                )
                document = _read(client, checks)
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual("ANALYSIS_IN_PROGRESS", document["coverage"]["reason"])

    def test_a_green_gate_with_findings_lists_every_one(self) -> None:
        """C8, #353: its gate passed with 29 open issues. The inventory lists all
        29; nothing about the gate makes it complete or empty."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {1: _page(_issues("open", 29), total=29)},
        )
        document = _read(client)
        self.assertBound(document)
        self.assertEqual(29, document["coverage"]["count"])
        self.assertEqual(29, len(document["findings"]))
        self.assertEqual({"open"}, {f["state"] for f in document["findings"]})

    def test_every_page_is_read_until_the_total(self) -> None:
        """C5: pages of 500, until the count reaches the total."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {
                1: _page(_issues("first", 500), total=501),
                2: _page(_issues("second", 1), total=501, index=2),
            },
        )
        document = _read(client)
        self.assertBound(document)
        self.assertEqual(
            (6, 501), (document["coverage"]["pages"], document["coverage"]["count"])
        )
        self.assertEqual(["1", "2"], [q["p"] for q in client.queries])

    def test_an_empty_inventory_needs_its_analysed_head(self) -> None:
        """C3: an unanalysed pull request's issue search answers 200 with no
        issues (PR 999999, measured), so without its listing entry the
        inventory is never complete, and no issue is read."""
        for name, listing, reason, observed in (
            ("no entry", _listing(), "PULL_REQUEST_NOT_ANALYZED", None),
            (
                "another head",
                _listing(_entry(OTHER_HEAD)),
                "SUBJECT_MISMATCH",
                OTHER_HEAD,
            ),
        ):
            with self.subTest(name):
                client = _SonarFake([listing], {1: _page([], total=0)})
                document = _read(client)
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual(
                    {"status": "INCOMPLETE", "pages": 1, "count": 0, "reason": reason},
                    document["coverage"],
                )
                self.assertEqual([], document["findings"])
                self.assertEqual(observed, document.get("observed_head"))
                self.assertEqual([LIST_URL], client.calls)

    def test_a_listing_that_names_another_subject_is_an_error(self) -> None:
        """C3: the entry must name this repository's pull request, once."""
        for name, listing in (
            (
                "another repository",
                _listing(_entry(url="https://github.com/ktogias/other/pull/312")),
            ),
            ("the entry twice", _listing(_entry(), _entry())),
            ("no list", {"pullRequests": None}),
            ("no commit", _listing({**_entry(), "commit": None})),
            ("no analysis date", _listing({**_entry(), "analysisDate": ""})),
            ("a head that is no SHA", _listing(_entry("A" * 40))),
        ):
            with self.subTest(name):
                client = _SonarFake([listing], {1: _page([], total=0)})
                document = _read(client)
                self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
                self.assertEqual("ERROR", document["coverage"]["status"])
                # The adapter's own refusal, not the envelope's later one.
                self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
                self.assertEqual([], client.queries)

    def test_a_new_analysis_during_the_read_discards_it(self) -> None:
        """C4: the head and the analysis must be the same after the last page."""
        for name, after in (
            ("a new analysis of the head", _entry(analysed="2026-10-12T00:10:00+0000")),
            ("a new head", _entry(OTHER_HEAD)),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(after)],
                    {1: _page(_issues("open", 2), total=2)},
                )
                document = _read(client)
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual("INCOMPLETE", document["coverage"]["status"])
                self.assertEqual(
                    "SUBJECT_CHANGED_DURING_READBACK", document["coverage"]["reason"]
                )
                self.assertEqual([], document["findings"])

    def test_pagination_that_does_not_add_up_is_never_complete(self) -> None:
        """C5: a short or empty page before the total, a total that changes, a
        page that is not the one asked for, or a count that differs from the
        total."""
        repeated = _issues("first", 500)
        for name, pages in (
            (
                "a short page before the total",
                {
                    1: _page(_issues("first", 499), total=501),
                    2: _page(_issues("second", 2), total=501, index=2),
                },
            ),
            (
                "an empty page before the total",
                {
                    1: _page(_issues("first", 500), total=501),
                    2: _page([], total=501, index=2),
                },
            ),
            (
                "a total that changes",
                {
                    1: _page(_issues("first", 500), total=501),
                    2: _page(_issues("second", 2), total=502, index=2),
                },
            ),
            (
                "another page than the one asked for",
                {1: _page(_issues("first", 1), total=1, index=2)},
            ),
            (
                "another page size",
                {1: _page(_issues("first", 1), total=1, size=100)},
            ),
            (
                "a repeated issue in place of a new one",
                {
                    1: _page(repeated, total=501),
                    2: _page([repeated[0]], total=501, index=2),
                },
            ),
            (
                "more issues than the total",
                {1: _page(_issues("first", 3), total=2)},
            ),
        ):
            with self.subTest(name):
                client = _SonarFake([_listing(_entry()), _listing(_entry())], pages)
                document = _read(client)
                self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
                self.assertEqual("ERROR", document["coverage"]["status"])
                # Each is the adapter's own refusal, not the envelope's later one.
                self.assertEqual(
                    "COUNT_TOTAL_MISMATCH"
                    if name.startswith("a repeated")
                    else "PROVIDER_ERROR",
                    document["coverage"]["reason"],
                )

    def test_one_issue_told_two_ways_is_a_normalization_error(self) -> None:
        """cubic on #424: two pages give one issue key with different content. The
        conflict is never resolved by choosing one, and nothing is kept."""
        conflicting = {**_issue("dup", 1), "message": "Another message"}
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {
                1: _page([*_issues("first", 499), _issue("dup", 1)], total=1000),
                2: _page([*_issues("second", 499), conflicting], total=1000, index=2),
            },
        )
        document = _read(client)
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual(
            {
                "status": "ERROR",
                "pages": 0,
                "count": 0,
                "reason": "NORMALIZATION_ERROR",
            },
            document["coverage"],
        )
        self.assertEqual([], document["findings"])

    def test_an_inventory_past_the_provider_window_is_partial(self) -> None:
        """C5: SonarCloud returns at most 10,000 results (a 400 past them,
        measured), so a larger total is PARTIAL, and no page past the window is
        asked for."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {1: _page(_issues("first", 500), total=10_001)},
        )
        document = _read(client)
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("PROVIDER_WINDOW_EXCEEDED", document["coverage"]["reason"])
        self.assertEqual(10_001, document["coverage"]["total"])
        self.assertEqual(["1"], [q["p"] for q in client.queries])

    def test_an_issue_of_another_subject_is_an_error(self) -> None:
        """C6: each issue names this pull request and project, and its component
        is the project's own."""
        for name, issue in (
            ("another pull request", _issue("x", pull="311")),
            ("another project", _issue("x", project="ktogias_other")),
            (
                "a component outside the project",
                _issue("x", component="ktogias_other:tools/example.py"),
            ),
            ("no key", {**_issue("x"), "key": ""}),
            ("no message", {**_issue("x"), "message": None}),
            ("a status that is not one", {**_issue("x"), "issueStatus": 7}),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page([issue], total=1)},
                )
                document = _read(client)
                self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
                self.assertEqual("ERROR", document["coverage"]["status"])
                self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])

    def test_a_provider_failure_keeps_its_kind(self) -> None:
        """C2: authentication, rate limits and other failures stay distinct, and
        none is complete."""
        for kind, completeness, status, reason in (
            ("AUTH", "AUTH_UNAVAILABLE", "UNAVAILABLE", "AUTH_UNAVAILABLE"),
            ("RATE_LIMIT", "READBACK_UNAVAILABLE", "RATE_LIMITED", "RATE_LIMITED"),
            (
                "UNAVAILABLE",
                "READBACK_UNAVAILABLE",
                "UNAVAILABLE",
                "READBACK_UNAVAILABLE",
            ),
            ("ERROR", "READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR"),
        ):
            failure = analyzer_sonarcloud.ProviderReadFailure(kind, "failed")
            for where, client in (
                ("the listing", _SonarFake([failure])),
                (
                    "an issue page",
                    _SonarFake([_listing(_entry()), _listing(_entry())], {1: failure}),
                ),
                (
                    "the second listing",
                    _SonarFake([_listing(_entry()), failure], {1: _page([], total=0)}),
                ),
            ):
                with self.subTest(kind=kind, where=where):
                    document = _read(client)
                    self.assertEqual(completeness, document["completeness"])
                    self.assertEqual(status, document["coverage"]["status"])
                    self.assertEqual(reason, document["coverage"]["reason"])
                    self.assertEqual([], document["findings"])

    def test_every_issue_that_is_not_fixed_is_a_finding(self) -> None:
        """S1 (PAO 6119736075): an acceptance or a false-positive marking in
        SonarCloud is no waiver, so those issues stay findings with their
        state, and the search asks for every state but FIXED, without
        `resolved`."""
        issues = [
            _issue(f"issue-{status.lower()}", n + 1, status=status)
            for n, status in enumerate(
                ("OPEN", "CONFIRMED", "ACCEPTED", "FALSE_POSITIVE")
            )
        ]
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())], {1: _page(issues, total=4)}
        )
        document = _read(client)
        self.assertBound(document)
        self.assertEqual(
            {
                "issue-open": "open",
                "issue-confirmed": "confirmed",
                "issue-accepted": "accepted",
                "issue-false_positive": "false_positive",
            },
            {f["id"]: f["state"] for f in document["findings"]},
        )
        self.assertEqual(1, len(client.queries))
        query = client.queries[0]
        self.assertEqual(
            "OPEN,CONFIRMED,ACCEPTED,FALSE_POSITIVE", query["issueStatuses"]
        )
        self.assertNotIn("resolved", query)

    def test_a_state_that_was_not_asked_for_is_never_dropped(self) -> None:
        """S1: a FIXED issue in the answer, or one without a state, is an error,
        not a silent omission."""
        for name, issue in (
            ("fixed", _issue("x", status="FIXED")),
            ("no state", {k: v for k, v in _issue("x").items() if k != "issueStatus"}),
            ("an unknown state", _issue("x", status="REVIEWED")),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page([issue], total=1)},
                )
                document = _read(client)
                self.assertEqual("ERROR", document["coverage"]["status"])
                # Refused as a state, not merely caught by the count afterwards.
                self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
                self.assertEqual([], document["findings"])

    def test_an_unpublished_report_is_never_complete(self) -> None:
        """C4 (PAO 6119736075): the exact head's SonarCloud run for this pull
        request must be finished, with a gate result, and must start at the
        listing's analysis date. No issue is read otherwise."""
        for name, checks, reason in (
            ("no run", [], "ANALYSIS_NOT_PUBLISHED"),
            (
                "an unfinished run",
                [_check(status="in_progress", conclusion=None)],
                "ANALYSIS_IN_PROGRESS",
            ),
            (
                "an unfinished newer run beside a finished one",
                [
                    _check(),
                    _check(
                        status="queued", conclusion=None, started="2026-10-12T00:10:00Z"
                    ),
                ],
                "ANALYSIS_IN_PROGRESS",
            ),
            *(
                (
                    f"a {conclusion} run",
                    [_check(conclusion=conclusion)],
                    "ANALYSIS_NOT_PUBLISHED",
                )
                for conclusion in (
                    "cancelled",
                    "neutral",
                    "skipped",
                    "timed_out",
                    "action_required",
                    "stale",
                )
            ),
            (
                "a run that starts before the analysis",
                [_check(started="2026-10-11T23:50:00Z")],
                "REPORT_ASSOCIATION_MISMATCH",
            ),
            (
                "a newer run than the listed analysis",
                [_check(), _check(started="2026-10-12T00:10:00Z", check_id=2)],
                "REPORT_ASSOCIATION_MISMATCH",
            ),
            (
                "only another pull request's run on the commit (#394, #395)",
                [_check(pull="311")],
                "ANALYSIS_NOT_PUBLISHED",
            ),
            ("another app's run", [_check(app=15368)], "ANALYSIS_NOT_PUBLISHED"),
            (
                "another check's run",
                [_check(name="SonarCloud")],
                "ANALYSIS_NOT_PUBLISHED",
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page(_issues("open", 2), total=2)},
                )
                document = _read(client, checks)
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual(
                    {"status": "INCOMPLETE", "pages": 1, "count": 0, "reason": reason},
                    document["coverage"],
                )
                self.assertEqual([], client.queries)

    def test_rfc3339_times_with_fractions_are_read(self) -> None:
        """CodeAnt on #424: a valid RFC 3339 time may carry fractional seconds, on
        GitHub's run or SonarCloud's listing; it is read, not an error. The start
        and the analysis date must still be the same instant."""
        for name, started, analysed, bound in (
            ("a fraction on the run", "2026-10-11T23:57:56.000Z", ANALYSED, True),
            (
                "a fraction on both",
                "2026-10-11T23:57:56.250Z",
                "2026-10-11T23:57:56.250+0000",
                True,
            ),
            (
                "a fraction on the run only, a later instant",
                "2026-10-11T23:57:56.250Z",
                ANALYSED,
                False,
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [
                        _listing(_entry(analysed=analysed)),
                        _listing(_entry(analysed=analysed)),
                    ],
                    {1: _page([], total=0)},
                )
                document = _read(client, [_check(started=started)])
                if bound:
                    self.assertBound(document)
                else:
                    self.assertEqual(
                        "REPORT_ASSOCIATION_MISMATCH", document["coverage"]["reason"]
                    )

    def test_a_tie_on_the_latest_start_is_ambiguous(self) -> None:
        """C4b (PAO 6119999041): two runs for the pull request starting at the same
        instant leave the latest publication unknown; neither id decides."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
        )
        document = _read(client, [_check(), _check(check_id=2, conclusion="failure")])
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("REPORT_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])

    def test_a_malformed_details_url_cannot_be_passed_over(self) -> None:
        """C4b: a SonarCloud run whose details name no single pull request or
        branch of the project might be this pull request's, so it makes the
        association ambiguous rather than being skipped."""
        for name, details in (
            (
                "two pull requests",
                "https://sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest=312&pullRequest=313",
            ),
            (
                "another page",
                "https://sonarcloud.io/project/overview?id=ktogias_gnostoa&pullRequest=312",
            ),
            (
                "another host",
                "https://sonarcloud.io.example/dashboard?id=ktogias_gnostoa&pullRequest=312",
            ),
            ("no subject", "https://sonarcloud.io/dashboard?id=ktogias_gnostoa"),
            ("not a URL", "pull request 312"),
            ("none", None),
            # urlsplit raises on it (CodeAnt on #424).
            (
                "an unparsable host",
                "https://[sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest=312",
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
                )
                document = _read(
                    client, [_check(), {**_check(check_id=2), "details_url": details}]
                )
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual(
                    "REPORT_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"]
                )

    def test_a_blank_association_cannot_be_passed_over(self) -> None:
        """The PAO on #424 (6123979691): a run whose details name an empty project,
        pull request or branch is not another analysis's, so beside this pull
        request's own run it leaves the association ambiguous, finished or not."""
        dashboard = "https://sonarcloud.io/dashboard"
        for name, details, unfinished in (
            (
                "an empty pull request",
                f"{dashboard}?id=ktogias_gnostoa&pullRequest=",
                False,
            ),
            (
                "a blank pull request",
                f"{dashboard}?id=ktogias_gnostoa&pullRequest=%20",
                False,
            ),
            ("an empty project", f"{dashboard}?id=&pullRequest=312", False),
            ("an empty branch", f"{dashboard}?id=ktogias_gnostoa&branch=", False),
            (
                "an unfinished run, empty pull request",
                f"{dashboard}?id=ktogias_gnostoa&pullRequest=",
                True,
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
                )
                other = (
                    _check(check_id=2, status="in_progress", conclusion=None)
                    if unfinished
                    else _check(check_id=2)
                )
                document = _read(client, [_check(), {**other, "details_url": details}])
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual(
                    "REPORT_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"]
                )

    def test_a_branch_or_another_project_s_run_is_not_the_pull_request_s(self) -> None:
        for name, details in (
            (
                "a branch analysis",
                "https://sonarcloud.io/dashboard?id=ktogias_gnostoa&branch=main",
            ),
            (
                "another project",
                "https://sonarcloud.io/dashboard?id=ktogias_other&pullRequest=312",
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
                )
                later = {
                    **_check(check_id=2, started="2026-10-12T00:10:00Z"),
                    "details_url": details,
                }
                self.assertBound(_read(client, [_check(), later]))

    def test_the_report_must_be_the_same_after_the_pages(self) -> None:
        """C4b, written after the correction: the runner-level RED is
        `SonarCloudReportBracketTests`."""
        for name, after, reason in (
            (
                "a new start",
                [_check(started="2026-10-12T00:10:00Z")],
                "REPORT_ASSOCIATION_MISMATCH",
            ),
            (
                "another conclusion",
                [_check(conclusion="failure")],
                "REPORT_CHANGED_DURING_READBACK",
            ),
            ("another run id", [_check(check_id=2)], "REPORT_CHANGED_DURING_READBACK"),
            (
                "a newer unfinished run",
                [
                    _check(),
                    _check(
                        check_id=2,
                        status="queued",
                        conclusion=None,
                        started="2026-10-12T00:10:00Z",
                    ),
                ],
                "ANALYSIS_IN_PROGRESS",
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page(_issues("open", 2), total=2)},
                )
                document = _read(client, [_check()], after)
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual(reason, document["coverage"]["reason"])
                self.assertEqual([], document["findings"])

    def test_an_unreadable_run_collection_is_never_complete(self) -> None:
        failure = analyzer_sonarcloud.ProviderReadFailure("ERROR", "incomplete")
        for name, calls in (("before", 1), ("after", 2)):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
                )
                count = 0

                def check_runs(fail_at: int = calls) -> list[dict[str, Any]]:
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise failure
                    return [_check()]

                document = analyzer_sonarcloud.read_pull_request(
                    client,
                    repository="ktogias/gnostoa",
                    pull_number=312,
                    requested_head=HEAD,
                    check_runs=check_runs,
                    observed_at=OBSERVED,
                )
                self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
                self.assertEqual("ERROR", document["coverage"]["status"])

    def test_the_run_is_chosen_by_the_pull_request_it_names(self) -> None:
        """C4: a commit carries the runs of every pull request analysed on it
        (#394 and #395 share `5ef97e5`); another one's later run is not this
        one's."""
        checks = [
            _check(),
            _check(pull="311", started="2026-10-12T00:10:00Z", check_id=2),
        ]
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())], {1: _page([], total=0)}
        )
        document = _read(client, checks)
        self.assertBound(document)
        self.assertEqual(CHECK_ID, document["native"]["check_run"]["id"])

    def test_a_gate_failure_is_still_a_published_report(self) -> None:
        """C4: a failed gate is a finished analysis; its inventory is read."""
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {1: _page(_issues("open", 3), total=3)},
        )
        document = _read(client, [_check(conclusion="failure")])
        self.assertBound(document)
        self.assertEqual(3, len(document["findings"]))

    def test_an_unfinished_task_for_the_pull_request_is_in_progress(self) -> None:
        """C4: an unchanged old analysis beside a newer unfinished task is not
        this head's complete report. The project's queue is read before the
        pages and after them."""
        for name, queues, reads_issues in (
            ("a pending task before", [_queue(_task(pullRequest="312"))], False),
            (
                "an in-progress task before",
                [_queue(_task("IN_PROGRESS", pullRequest="312"))],
                False,
            ),
            (
                "a task that starts during the pages",
                [_queue(), _queue(_task(pullRequest="312"))],
                True,
            ),
            ("a task of unknown identity", [_queue(_task())], False),
            # An empty or blank identity names nothing (cubic on #424).
            (
                "a task of empty identity",
                [_queue(_task(pullRequest="", branch=""))],
                False,
            ),
            (
                "a task of blank identity",
                [_queue(_task(pullRequest=" ", branch="\t"))],
                False,
            ),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page(_issues("open", 2), total=2)},
                    queues,
                )
                document = _read(client)
                self.assertEqual("AMBIGUOUS", document["completeness"])
                self.assertEqual("INCOMPLETE", document["coverage"]["status"])
                self.assertEqual("ANALYSIS_IN_PROGRESS", document["coverage"]["reason"])
                self.assertEqual([], document["findings"])
                self.assertEqual(reads_issues, bool(client.queries))

    def test_a_task_of_the_pull_request_in_current_holds_it(self) -> None:
        """F5 (CodeReviewBot and CodeAnt on #424): `ce/component`'s `current` is the
        project's last task, a pull request's included (#424's own, 2026-10-12).
        One of this pull request's that is unfinished or failed means its newest
        analysis is not the published report, before the pages or after them."""
        for name, current, reason in (
            (
                "running",
                _task("IN_PROGRESS", pullRequest="312"),
                "ANALYSIS_IN_PROGRESS",
            ),
            ("pending", _task("PENDING", pullRequest="312"), "ANALYSIS_IN_PROGRESS"),
            ("failed", _task("FAILED", pullRequest="312"), "ANALYSIS_NOT_PUBLISHED"),
            (
                "cancelled",
                _task("CANCELED", pullRequest="312"),
                "ANALYSIS_NOT_PUBLISHED",
            ),
        ):
            for when, queues in (
                ("before", [{"queue": [], "current": current}, _queue()]),
                ("after", [_queue(), {"queue": [], "current": current}]),
            ):
                with self.subTest(name=name, when=when):
                    client = _SonarFake(
                        [_listing(_entry()), _listing(_entry())],
                        {1: _page(_issues("open", 2), total=2)},
                        queues,
                    )
                    document = _read(client)
                    self.assertEqual("AMBIGUOUS", document["completeness"])
                    self.assertEqual(reason, document["coverage"]["reason"])
                    self.assertEqual([], document["findings"])

    def test_another_current_task_does_not_hold_the_pull_request(self) -> None:
        for name, current in (
            ("main's", {**_task("SUCCESS"), "analysisId": "43392b27"}),
            (
                "another pull request's, running",
                _task("IN_PROGRESS", pullRequest="311"),
            ),
            ("this pull request's, finished", _task("SUCCESS", pullRequest="312")),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page([], total=0)},
                    [{"queue": [], "current": current}] * 2,
                )
                self.assertBound(_read(client))

    def test_a_failure_after_conflicting_pages_is_still_a_readback(self) -> None:
        """F9 (CodeAnt on #424): two pages disagree about one issue, and a later
        page fails. The readback is still built, and is never complete."""
        conflicting = {**_issue("dup", 1), "message": "Another message"}
        client = _SonarFake(
            [_listing(_entry()), _listing(_entry())],
            {
                1: _page([*_issues("first", 499), _issue("dup", 1)], total=1001),
                2: _page([*_issues("second", 499), conflicting], total=1001, index=2),
                3: analyzer_sonarcloud.ProviderReadFailure("UNAVAILABLE", "failed"),
            },
        )
        document = _read(client)
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])

    def test_another_branch_s_task_does_not_hold_the_pull_request(self) -> None:
        for name, task in (
            ("another pull request", _task(pullRequest="311")),
            ("a branch", _task(branch="main", branchType="BRANCH")),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page([], total=0)},
                    [_queue(task), _queue(task)],
                )
                self.assertBound(_read(client))

    def test_a_malformed_queue_is_an_error(self) -> None:
        for name, queue in (
            ("no queue", {"current": {}}),
            ("a queue that is not a list", {"queue": {}}),
            ("a task that is not an object", {"queue": [7]}),
        ):
            with self.subTest(name):
                client = _SonarFake(
                    [_listing(_entry()), _listing(_entry())],
                    {1: _page([], total=0)},
                    [queue, queue],
                )
                document = _read(client)
                self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
                self.assertEqual("ERROR", document["coverage"]["status"])

    def test_the_check_identity_is_the_manifest_s(self) -> None:
        """G1: the run the inventory is associated with is the one whose result
        gives the quality-gate item, so one record names it."""
        from tools import merge_evidence_github

        manifest = merge_evidence_github.load_required_checks(
            ROOT / "policy" / "merge-required-checks.yaml", project_root=ROOT
        )
        self.assertEqual(
            {
                "quality-gate": (
                    f"github-check-run:{analyzer_sonarcloud.CHECK_APP_ID}:"
                    f"{analyzer_sonarcloud.CHECK_NAME}"
                )
            },
            manifest["sonarcloud"],
        )


@contextlib.contextmanager
def _no_network() -> Iterator[mock.MagicMock]:
    with mock.patch.object(
        http.client.HTTPSConnection,
        "connect",
        side_effect=AssertionError("network forbidden"),
    ) as connect:
        yield connect


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://sonarcloud.io/api/issues/search",
        code,
        "failed",
        http.client.HTTPMessage(),
        io.BytesIO(b'{"errors":[{"msg":"failed"}]}'),
    )


class SonarCloudClientTests(unittest.TestCase):
    """C1, C2, C10: the client is the shared GitHub REST transport on
    SonarCloud's origin (Decision 0100), with its own credential and failure
    kinds."""

    def test_a_missing_or_malformed_token_sends_nothing(self) -> None:
        for name, environment in (
            ("no token", {}),
            ("an empty token", {SONAR_ENV: ""}),
            ("a token with a newline", {SONAR_ENV: "synthetic-sonar\n"}),
            ("a token with a space", {SONAR_ENV: "synthetic sonar"}),
        ):
            with (
                self.subTest(name),
                mock.patch.dict(os.environ, environment, clear=True),
                _no_network() as connect,
            ):
                with self.assertRaises(
                    analyzer_sonarcloud.ProviderReadFailure
                ) as raised:
                    analyzer_sonarcloud.SonarCloudRestClient.from_environment()
                self.assertEqual("AUTH", raised.exception.kind)
                self.assertNotIn("synthetic", str(raised.exception))
                connect.assert_not_called()

    def test_an_http_failure_keeps_its_kind(self) -> None:
        client = analyzer_sonarcloud.SonarCloudRestClient("synthetic-sonar-token")
        for code, kind in (
            (401, "AUTH"),
            (403, "AUTH"),
            (429, "RATE_LIMIT"),
            # Only 429 is SonarCloud's rate limit (its Web API documentation);
            # an unavailable server is not one (PAO 6119736075).
            (503, "UNAVAILABLE"),
            (504, "UNAVAILABLE"),
            (400, "UNAVAILABLE"),
            (404, "UNAVAILABLE"),
            (500, "UNAVAILABLE"),
        ):
            with (
                self.subTest(code=code),
                mock.patch("tools.github_rest.exchange", side_effect=_http_error(code)),
                self.assertRaises(analyzer_sonarcloud.ProviderReadFailure) as raised,
            ):
                client.get(LIST_URL)
            self.assertEqual(kind, raised.exception.kind)
            self.assertEqual(code, raised.exception.status)
            self.assertNotIn("synthetic-sonar-token", str(raised.exception))

    def test_an_unusable_answer_is_an_error(self) -> None:
        client = analyzer_sonarcloud.SonarCloudRestClient("synthetic-sonar-token")
        for name, raw in (
            ("not JSON", b"not json"),
            ("not an object", b"[]"),
            ("null", b"null"),
        ):
            with (
                self.subTest(name),
                mock.patch("tools.github_rest.exchange", return_value=(raw, {})),
                self.assertRaises(analyzer_sonarcloud.ProviderReadFailure) as raised,
            ):
                client.get(LIST_URL)
            self.assertEqual("ERROR", raised.exception.kind)

    def test_reads_stay_on_sonarcloud_s_origin(self) -> None:
        client = analyzer_sonarcloud.SonarCloudRestClient("synthetic-sonar-token")
        for url in (
            "https://api.github.com/repos/ktogias/gnostoa",
            "http://sonarcloud.io/api/issues/search",
            "https://sonarcloud.io.example/api/issues/search",
            "https://user@sonarcloud.io/api/issues/search",
        ):
            with (
                self.subTest(url),
                _no_network() as connect,
                self.assertRaises(analyzer_sonarcloud.ProviderReadFailure) as raised,
            ):
                client.get(url)
            self.assertEqual("ERROR", raised.exception.kind)
            connect.assert_not_called()

    def test_the_answer_is_the_document(self) -> None:
        client = analyzer_sonarcloud.SonarCloudRestClient("synthetic-sonar-token")
        with mock.patch(
            "tools.github_rest.exchange", return_value=(b'{"pullRequests": []}', {})
        ) as exchange:
            self.assertEqual({"pullRequests": []}, client.get(LIST_URL))
        request = exchange.call_args.args[1]
        self.assertEqual(LIST_URL, request.full_url)
        self.assertEqual(
            "Bearer synthetic-sonar-token", request.unredirected_hdrs["Authorization"]
        )


if __name__ == "__main__":
    unittest.main()
