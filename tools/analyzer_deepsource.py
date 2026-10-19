from __future__ import annotations

import html
import http.client
import json
import math
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from . import github_rest
from .analyzer_readback import (
    AnalyzerReadbackError,
    build_readback,
    coverage,
    deduplicate_findings,
    normalize_repository,
)
from .review_model import canonical_digest, canonical_json

_API_ROOT = "https://api.deepsource.com"
_GRAPHQL_URL = f"{_API_ROOT}/graphql/"
_TOKEN_ENV = "DEEPSOURCE_API_TOKEN"  # nosec B105 -- environment variable name, not a credential
_TIMEOUT_SECONDS = 30
_MAX_RESPONSE_BYTES = 4_194_304
_MAX_PAGES = 100
# A deadline-bound read runs through the shared bounded exchange (Decision 0100):
# a socket timeout bounds one receive, never the exchange, so the caller stops
# waiting at the deadline (PAO R0-DEADLINE-01, 6267919955). Its abandoned workers
# are this adapter's own, so a stalling DeepSource cannot exhaust another's cap.
_EXCHANGE_WORKERS: list[threading.Thread] = []
_DEADLINE_PASSED = "DeepSource read deadline passed"
_DEADLINE_BUDGET = "DeepSource read did not finish within its deadline budget"
_API_UNAVAILABLE = "DeepSource API unavailable"
_RESPONSE_TOO_LARGE = "DeepSource API response exceeds bounded size"
_EXCHANGE_POLICY = github_rest.Policy(
    timeout_seconds=_TIMEOUT_SECONDS,
    max_response_bytes=_MAX_RESPONSE_BYTES,
    # No floor: a deadline-bound request is never given more than the budget left;
    # the shared default of 0.1 s could cross the deadline (Router 6274471644).
    min_request_seconds=0.0,
    workers=_EXCHANGE_WORKERS,
)
_COMPLETED_RUN_STATUSES = frozenset({"SUCCESS", "FAILURE"})
_COMPLETED_CHECK_STATUSES = frozenset({"SUCCESS", "FAILURE", "NEUTRAL"})
_DEEPSOURCE_STATUS = re.compile(r"^DeepSource: (?P<analyzer>[^/]+)$")
_RUN_URL = re.compile(
    r"^https://app\.deepsource\.com/gh/(?P<owner>[^/]+)/(?P<repo>[^/]+)/"
    r"run/(?P<run>[0-9a-f-]{36})/(?P<analyzer>[^/?#]+)/?$"
)
_ISSUE_MARKER = re.compile(r"<!--\s*DeepSource:\s*id=(?P<id>[^\s]+)\s*-->")
_H3_AFTER_PICTURE = re.compile(
    r"</picture>(?P<title>.*?)</h3>", re.DOTALL | re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")
_SEVERITY = re.compile(r"severity_(?P<value>[a-z_]+)\.svg", re.IGNORECASE)
_CATEGORY = re.compile(r"category_(?P<value>[a-z_]+)\.svg", re.IGNORECASE)
_GITHUB_BOT_LOGIN = "deepsource-io[bot]"
_GITHUB_BOT_TYPE = "Bot"
_GITHUB_APP_SLUG = "deepsource-io"

_RUN_QUERY = """
query AnalyzerRun($runUid: UUID!, $cursor: String) {
  run(runUid: $runUid) {
    id
    runUid
    commitOid
    baseOid
    status
    repository {
      name
      account {
        login
        vcsProvider
      }
    }
    checks(first: 100, after: $cursor) {
      totalCount
      edges {
        node {
          id
          status
          analyzer { shortcode }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

_CHECK_QUERY = """
query AnalyzerCheckIssues($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on Check {
      id
      status
      analyzer { shortcode }
      issues(first: 100, after: $cursor) {
        totalCount
        edges {
          node {
            id
            path
            severity
            category
            title
            explanation
            isSuppressed
            beginLine
            beginColumn
            endLine
            endColumn
            shortcode
            issue {
              shortcode
              title
              severity
              category
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


# The capability discovery's three reads (#389 F3 R0): the repository's current
# configuration and enabled analyzers, its ignore rules, and one analyzer's issue
# catalogue. Each pages one connection, so every connection is bound on its own (PAO
# 6267150750, R0-SNAP-01).
_REPOSITORY_ANALYZERS_QUERY = """
query RepositoryAnalyzers($name: String!, $login: String!, $cursor: String) {
  repository(name: $name, login: $login, vcsProvider: GITHUB) {
    name
    isActivated
    configJson
    account {
      login
      vcsProvider
    }
    enabledAnalyzers(first: 100, after: $cursor) {
      totalCount
      edges {
        node {
          shortcode
          version
          numIssues
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

_REPOSITORY_IGNORE_RULES_QUERY = """
query RepositoryIgnoreRules($name: String!, $login: String!, $cursor: String) {
  repository(name: $name, login: $login, vcsProvider: GITHUB) {
    name
    account {
      login
      vcsProvider
    }
    ignoreRules(first: 100, after: $cursor) {
      totalCount
      edges {
        node {
          id
          level
          type
          filePath
          globPattern
          issue { shortcode }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

_ANALYZER_CATALOGUE_QUERY = """
query AnalyzerCatalogue($shortcode: String!, $cursor: String) {
  analyzer(shortcode: $shortcode) {
    shortcode
    version
    numIssues
    issues(first: 100, after: $cursor) {
      totalCount
      edges {
        node {
          shortcode
          title
          category
          severity
          isRecommended
          tags
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


_ADMITTED_GRAPHQL_READ_QUERIES = frozenset(
    {
        _RUN_QUERY,
        _CHECK_QUERY,
        _REPOSITORY_ANALYZERS_QUERY,
        _REPOSITORY_IGNORE_RULES_QUERY,
        _ANALYZER_CATALOGUE_QUERY,
    }
)


class ProviderReadFailure(RuntimeError):
    def __init__(self, kind: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class GraphQLReader(Protocol):
    def graphql(
        self, query: str, variables: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


class DeadlineGraphQLReader(Protocol):
    """A reader that bounds each request's own work by an absolute deadline."""

    def graphql(
        self,
        query: str,
        variables: Mapping[str, Any],
        *,
        deadline: float | None = None,
    ) -> Mapping[str, Any]: ...


def _remaining(deadline: float) -> float:
    """The budget left before `deadline`, on the monotonic clock; none left stops the
    read."""

    # No comparison with NaN is true, so a NaN or an infinite deadline would never
    # stop a read: it is refused (Amazon Q on #441).
    if not math.isfinite(deadline):
        raise ProviderReadFailure("ERROR", "DeepSource read deadline is not finite")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _deadline_passed()
    return remaining


def _deadline_passed() -> ProviderReadFailure:
    return ProviderReadFailure("DEADLINE", _DEADLINE_PASSED)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProviderReadFailure(
            "ERROR", "DeepSource API URL has an invalid port"
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.deepsource.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ProviderReadFailure(
            "ERROR", "DeepSource API URL is outside the admitted origin"
        )
    return url


class _DeepSourceRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        admitted = _validate_api_url(newurl)
        authorization = req.get_header("Authorization")
        redirected = super().redirect_request(req, fp, code, msg, headers, admitted)
        if redirected is not None and authorization is not None:
            redirected.add_unredirected_header("Authorization", authorization)
        return redirected


class DeepSourceGraphQLClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise ProviderReadFailure("AUTH", "DeepSource authentication unavailable")
        if any(not "!" <= char <= "~" for char in token):
            raise ProviderReadFailure("AUTH", "DeepSource credential is malformed")
        self._token = token
        self._opener = urllib.request.build_opener(_DeepSourceRedirectHandler())

    @classmethod
    def from_environment(cls) -> DeepSourceGraphQLClient:
        return cls(os.environ.get(_TOKEN_ENV, ""))

    def graphql(
        self,
        query: str,
        variables: Mapping[str, Any],
        *,
        deadline: float | None = None,
    ) -> Mapping[str, Any]:
        """One admitted read. Without `deadline`, as every existing read has it. With
        one, no request starts after it, the whole exchange runs through the shared
        bounded exchange that the caller stops waiting for at the deadline, and an
        answer finished after it is refused (#389 F3 R0; Router 6267325366, PAO
        6267919955)."""

        if query not in _ADMITTED_GRAPHQL_READ_QUERIES:
            raise ProviderReadFailure(
                "ERROR", "DeepSource unsupported GraphQL read operation"
            )
        document = _graphql_document(
            self._exchange(self._request(query, variables), deadline)
        )
        if deadline is not None and time.monotonic() >= deadline:
            # An answer finished after the deadline is no read within it (Sourcery
            # and CodeAnt on #441).
            raise _deadline_passed()
        return document

    def _request(
        self, query: str, variables: Mapping[str, Any]
    ) -> urllib.request.Request:
        payload = json.dumps(
            {"query": query, "variables": dict(variables)},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            _validate_api_url(_GRAPHQL_URL),
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "gnostoa-analyzer-readback",
            },
        )
        request.add_unredirected_header("Authorization", f"Bearer {self._token}")
        return request

    def _exchange(
        self, request: urllib.request.Request, deadline: float | None
    ) -> bytes:
        """The answer's bytes, each transport failure reported as its kind."""

        ceiling = False
        try:
            if deadline is None:
                with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                    raw: bytes = response.read(_MAX_RESPONSE_BYTES + 1)
            else:
                # Each request's limit comes from the shared owner: at most the 30 s
                # ceiling and at most the budget left, and none starts without
                # budget. Which of the two set it decides what a timeout means; a
                # tie is the budget's (CodeAnt 4317340803, Router 6274471644).
                _remaining(deadline)
                limit = github_rest.request_timeout(deadline, _EXCHANGE_POLICY)
                if limit <= 0:
                    raise _deadline_passed()
                ceiling = limit < deadline - time.monotonic()
                raw, _headers = github_rest.exchange(
                    self._opener, request, limit, _EXCHANGE_POLICY
                )
        except urllib.error.HTTPError as exc:
            raise _http_failure(exc) from exc
        except github_rest.ResponseTooLarge as exc:
            raise ProviderReadFailure("ERROR", _RESPONSE_TOO_LARGE) from exc
        except github_rest.NotSent as exc:
            # Earlier stalled exchanges still hold the cap: nothing was sent.
            raise ProviderReadFailure("UNAVAILABLE", _API_UNAVAILABLE) from exc
        except github_rest.GitHubReadError as exc:
            # The shared exchange's own bound: its wait for the whole limit, or its
            # stop at half of it, which keeps the receive that straddles the stop
            # inside the limit (Decision 0100). Set by the budget, it is the read not
            # finishing within its deadline (CodeAnt on #441); set by the ceiling
            # while the deadline holds, it is the provider not answering in time.
            if deadline is not None and ceiling and time.monotonic() < deadline:
                raise ProviderReadFailure("UNAVAILABLE", _API_UNAVAILABLE) from exc
            raise ProviderReadFailure("DEADLINE", _DEADLINE_BUDGET) from exc
        # URLError is an OSError.
        except (OSError, http.client.HTTPException) as exc:
            raise _transport_failure(exc, deadline, ceiling) from exc
        except ValueError:
            # HTTP header validation can include credential bytes in its error.
            raise ProviderReadFailure(
                "ERROR", "DeepSource request failed validation"
            ) from None
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ProviderReadFailure("ERROR", _RESPONSE_TOO_LARGE)
        return raw


def _http_failure(exc: urllib.error.HTTPError) -> ProviderReadFailure:
    if exc.code in {401, 403}:
        return ProviderReadFailure(
            "AUTH", "DeepSource authentication unavailable", status=exc.code
        )
    if exc.code == 429:
        return ProviderReadFailure(
            "RATE_LIMIT", "DeepSource API rate limited", status=exc.code
        )
    return ProviderReadFailure(
        "UNAVAILABLE", f"DeepSource API HTTP {exc.code}", status=exc.code
    )


def _transport_failure(
    exc: OSError | http.client.HTTPException,
    deadline: float | None,
    ceiling: bool = False,
) -> ProviderReadFailure:
    timed_out = isinstance(exc, TimeoutError) or isinstance(
        getattr(exc, "reason", None), TimeoutError
    )
    if deadline is not None and (
        (timed_out and not ceiling) or time.monotonic() >= deadline
    ):
        # A timeout the budget set is the deadline, not an outage: the exchange
        # gives each receive half the limit (Decision 0100). One the 30 s ceiling
        # set, before the deadline, is the provider not answering (Router
        # 6274471644).
        return _deadline_passed()
    return ProviderReadFailure("UNAVAILABLE", _API_UNAVAILABLE)


def _graphql_document(raw: bytes) -> Mapping[str, Any]:
    # The shared decode names every failure as one unusable answer: a non-UTF-8 body,
    # deep nesting's RecursionError and the integer-digit limit's ValueError among
    # them, and a `null` body (Decision 0100; CodeAnt on #441).
    try:
        document = github_rest.decode_json(raw, _GRAPHQL_URL)
    except github_rest.MalformedAnswer as exc:
        raise ProviderReadFailure(
            "ERROR", "DeepSource API returned invalid JSON"
        ) from exc
    if not isinstance(document, Mapping):
        raise ProviderReadFailure(
            "ERROR", "DeepSource GraphQL response must be an object"
        )
    if document.get("errors"):
        raise ProviderReadFailure("ERROR", "DeepSource GraphQL returned errors")
    return document


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderReadFailure("ERROR", f"DeepSource {label} is malformed")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProviderReadFailure("ERROR", f"DeepSource {label} is malformed")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ProviderReadFailure("ERROR", f"DeepSource {label} is malformed")
    return value


def _page(
    connection: object, label: str
) -> tuple[list[Mapping[str, Any]], int | None, bool, str | None]:
    value = _mapping(connection, label)
    edges = value.get("edges")
    if not isinstance(edges, list):
        raise ProviderReadFailure("ERROR", f"DeepSource {label}.edges is malformed")
    nodes: list[Mapping[str, Any]] = []
    for edge in edges:
        nodes.append(
            _mapping(_mapping(edge, f"{label}.edge").get("node"), f"{label}.node")
        )
    raw_total = value.get("totalCount")
    total = None if raw_total is None else _integer(raw_total, f"{label}.totalCount")
    info = _mapping(value.get("pageInfo"), f"{label}.pageInfo")
    has_next = info.get("hasNextPage")
    if type(has_next) is not bool:
        raise ProviderReadFailure(
            "ERROR", f"DeepSource {label}.hasNextPage is malformed"
        )
    cursor = info.get("endCursor")
    if cursor is not None and not isinstance(cursor, str):
        raise ProviderReadFailure("ERROR", f"DeepSource {label}.endCursor is malformed")
    if has_next and not cursor:
        raise ProviderReadFailure(
            "ERROR", f"DeepSource {label} pagination cursor is missing"
        )
    return nodes, total, has_next, cursor


def _failure_coverage(
    error: ProviderReadFailure, *, pages: int, count: int, reason: str | None = None
) -> dict[str, Any]:
    if error.kind == "RATE_LIMIT":
        status = "RATE_LIMITED"
    elif error.kind in {"AUTH", "UNAVAILABLE"}:
        status = "UNAVAILABLE"
    else:
        status = "ERROR"
    return coverage(
        status,
        pages=pages,
        count=count,
        reason=reason
        or {
            "AUTH": "AUTH_UNAVAILABLE",
            "RATE_LIMIT": "RATE_LIMITED",
            "UNAVAILABLE": "READBACK_UNAVAILABLE",
        }.get(error.kind, "PROVIDER_ERROR"),
    )


def _failure_completeness(error: ProviderReadFailure) -> str:
    return "AUTH_UNAVAILABLE" if error.kind == "AUTH" else "READBACK_UNAVAILABLE"


def _run_subject(run: Mapping[str, Any]) -> tuple[str, str, str, str]:
    run_uid = _text(run.get("runUid"), "runUid")
    commit = _text(run.get("commitOid"), "commitOid")
    state = _text(run.get("status"), "run.status")
    repository = _mapping(run.get("repository"), "run.repository")
    account = _mapping(repository.get("account"), "run.repository.account")
    login = _text(account.get("login"), "repository account login")
    name = _text(repository.get("name"), "repository name")
    provider = _text(account.get("vcsProvider"), "repository provider")
    if provider != "GITHUB":
        raise ProviderReadFailure("ERROR", "DeepSource run is not bound to GitHub")
    return run_uid, commit, state, f"{login}/{name}"


def _issue_finding(
    check: Mapping[str, Any], issue: Mapping[str, Any]
) -> dict[str, Any]:
    analyzer = _mapping(check.get("analyzer"), "check.analyzer")
    analyzer_id = _text(analyzer.get("shortcode"), "analyzer.shortcode")
    definition = issue.get("issue")
    definition_map = (
        _mapping(definition, "issue.definition") if definition is not None else {}
    )
    rule = issue.get("shortcode") or definition_map.get("shortcode")
    title = (
        issue.get("title") or definition_map.get("title") or rule or "DeepSource issue"
    )
    is_suppressed = issue.get("isSuppressed")
    if type(is_suppressed) is not bool:
        raise ProviderReadFailure("ERROR", "DeepSource issue.isSuppressed is malformed")
    finding: dict[str, Any] = {
        "id": _text(issue.get("id"), "issue.id"),
        "message": _text(title, "issue.title"),
        "tool": {"id": analyzer_id},
        "severity": _text(issue.get("severity"), "issue.severity"),
        "category": _text(issue.get("category"), "issue.category"),
        "path": _text(issue.get("path"), "issue.path"),
        "state": "suppressed" if is_suppressed else "open",
        "native_ref": _text(issue.get("id"), "issue.id"),
        "provenance": [
            {
                "surface": "deepsource-graphql",
                "reference": _text(check.get("id"), "check.id"),
            }
        ],
        "native": {
            "analyzer": analyzer_id,
            "check_status": _text(check.get("status"), "check.status"),
        },
    }
    if isinstance(rule, str) and rule:
        finding["rule"] = rule
    begin_line = issue.get("beginLine")
    end_line = issue.get("endLine")
    begin_column = issue.get("beginColumn")
    end_column = issue.get("endColumn")
    finding["range"] = {
        "start_line": begin_line,
        "start_column": _model_column(begin_column),
        "end_line": end_line,
        "end_column": _model_column(end_column),
    }
    return finding


def _model_column(value: object) -> object:
    """DeepSource counts columns from 0 and the readback's model from 1 (#309,
    6103702467). Only a non-negative integer is converted; any other value reaches
    the model unchanged. An absent (`None`) column stays absent, and the model's own
    validation refuses every other value."""

    if type(value) is int and value >= 0:
        return value + 1
    return value


class _Pages:
    """The provider pages a read has fetched, shared with its helpers so a
    failure's readback still counts them."""

    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count = 0


class _RunRead:
    __slots__ = ("checks", "run", "total", "total_seen")

    def __init__(
        self,
        run: Mapping[str, Any] | None,
        checks: list[Mapping[str, Any]],
        total: int | None,
        total_seen: bool,
    ) -> None:
        self.run = run
        self.checks = checks
        self.total = total
        self.total_seen = total_seen


def _full_readback(
    common: Mapping[str, Any],
    *,
    completeness: str,
    observed_head: str | None,
    analysis_id: str,
    run_state: str,
    coverage_record: Mapping[str, Any],
    findings: Iterable[Mapping[str, Any]] = (),
    native: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_readback(
        provider="deepsource",
        adapter="deepsource-graphql/v1",
        repository=common["repository"],
        pull_number=common["pull_number"],
        requested_head=common["requested_head"],
        observed_head=observed_head,
        analysis_id=analysis_id,
        scope="FULL",
        completeness=completeness,
        native_mode="FULL_RUN",
        observed_at=common["observed_at"],
        run_state=run_state,
        coverage_record=coverage_record,
        findings=findings,
        native=native,
    )


def _tracked_total(
    total: int | None, expected: int | None, seen: bool, label: str
) -> tuple[int | None, bool]:
    """A paginated connection's total must not change, nor appear or vanish."""

    if total is not None:
        if not seen:
            return total, True
        if total != expected:
            raise ProviderReadFailure(
                "ERROR", f"DeepSource {label} total changed during pagination"
            )
        return expected, seen
    if seen:
        raise ProviderReadFailure(
            "ERROR",
            f"DeepSource {label} total availability changed during pagination",
        )
    return expected, seen


def _read_run_pages(client: GraphQLReader, run_uid: str, pages: _Pages) -> _RunRead:
    """The run and all of its checks; a run the provider does not return gives a
    read without one."""

    checks: list[Mapping[str, Any]] = []
    run_record: Mapping[str, Any] | None = None
    cursor: str | None = None
    expected: int | None = None
    total_seen = False
    for _ in range(_MAX_PAGES):
        page = client.graphql(_RUN_QUERY, {"runUid": run_uid, "cursor": cursor})
        pages.count += 1
        raw_run = _mapping(page.get("data"), "data").get("run")
        if raw_run is None:
            return _RunRead(None, checks, expected, total_seen)
        run = _mapping(raw_run, "run")
        subject = _run_subject(run)
        if run_record is None:
            run_record = run
        elif subject != _run_subject(run_record):
            raise ProviderReadFailure(
                "ERROR", "DeepSource run changed during pagination"
            )
        previous = cursor
        page_checks, total, has_next, cursor = _page(run.get("checks"), "run.checks")
        if has_next and cursor == previous:
            raise ProviderReadFailure(
                "ERROR", "DeepSource check pagination did not advance"
            )
        expected, total_seen = _tracked_total(total, expected, total_seen, "check")
        checks.extend(page_checks)
        for check in page_checks:
            _text(check.get("id"), "check.id")
            _text(check.get("status"), "check.status")
            analyzer = _mapping(check.get("analyzer"), "check.analyzer")
            _text(analyzer.get("shortcode"), "analyzer.shortcode")
        if not has_next:
            return _RunRead(run_record, checks, expected, total_seen)
    raise ProviderReadFailure("ERROR", "DeepSource check pagination exceeded bound")


def _unusable_run(
    common: Mapping[str, Any],
    read: _RunRead,
    run_uid: str,
    subject: tuple[str, str, str, str],
    pages: int,
) -> dict[str, Any] | None:
    """The readback for a run that cannot be read further, or None."""

    actual_uid, commit, run_state, actual_repository = subject
    mismatch = None
    if actual_uid != run_uid:
        mismatch = "RUN_UID_MISMATCH"
    elif actual_repository != common["repository"]:
        mismatch = "REPOSITORY_MISMATCH"
    elif commit != common["requested_head"]:
        mismatch = "SUBJECT_MISMATCH"
    if mismatch is not None:
        return _full_readback(
            common,
            completeness="AMBIGUOUS",
            observed_head=commit,
            analysis_id=actual_uid if mismatch == "RUN_UID_MISMATCH" else run_uid,
            run_state=run_state,
            coverage_record=coverage(
                "INCOMPLETE", pages=pages, count=0, reason=mismatch
            ),
        )
    unavailable = None
    native = None
    if run_state not in _COMPLETED_RUN_STATUSES:
        unavailable = "ANALYSIS_RUN_NOT_COMPLETE"
    elif not read.checks:
        unavailable = "NO_ANALYZER_CHECKS"
    else:
        check_states = {
            _text(check.get("id"), "check.id"): _text(
                check.get("status"), "check.status"
            )
            for check in read.checks
        }
        if any(
            state not in _COMPLETED_CHECK_STATUSES for state in check_states.values()
        ):
            unavailable = "ANALYZER_CHECK_NOT_COMPLETE"
            native = {"check_states": check_states}
        elif read.total_seen and len(read.checks) != read.total:
            unavailable = "CHECK_PAGINATION_INCOMPLETE"
    if unavailable is None:
        return None
    return _full_readback(
        common,
        completeness="READBACK_UNAVAILABLE",
        observed_head=commit,
        analysis_id=run_uid,
        run_state=run_state,
        coverage_record=coverage("PARTIAL", pages=pages, count=0, reason=unavailable),
        native=native,
    )


def _read_check_issues(
    client: GraphQLReader,
    check: Mapping[str, Any],
    pages: _Pages,
    findings: list[Mapping[str, Any]],
) -> int | None:
    """One check's issues, appended to `findings`; its total, or None when the
    provider gives none."""

    check_id = _text(check.get("id"), "check.id")
    expected_status = _text(check.get("status"), "check.status")
    expected_analyzer = _text(
        _mapping(check.get("analyzer"), "check.analyzer").get("shortcode"),
        "analyzer.shortcode",
    )
    cursor: str | None = None
    check_total: int | None = None
    total_seen = False
    seen = 0
    for _ in range(_MAX_PAGES):
        page = client.graphql(_CHECK_QUERY, {"id": check_id, "cursor": cursor})
        pages.count += 1
        node = _mapping(_mapping(page.get("data"), "data").get("node"), "check node")
        node_id = _text(node.get("id"), "check.id")
        node_status = _text(node.get("status"), "check.status")
        node_analyzer = _text(
            _mapping(node.get("analyzer"), "check.analyzer").get("shortcode"),
            "analyzer.shortcode",
        )
        if (
            node_id != check_id
            or node_status != expected_status
            or node_analyzer != expected_analyzer
        ):
            raise ProviderReadFailure(
                "ERROR", "DeepSource check metadata changed during pagination"
            )
        previous = cursor
        issue_nodes, total, has_next, cursor = _page(node.get("issues"), "check.issues")
        if has_next and cursor == previous:
            raise ProviderReadFailure(
                "ERROR", "DeepSource issue pagination did not advance"
            )
        check_total, total_seen = _tracked_total(
            total, check_total, total_seen, "issue"
        )
        findings.extend(_issue_finding(node, issue) for issue in issue_nodes)
        seen += len(issue_nodes)
        if not has_next:
            break
    else:
        raise ProviderReadFailure("ERROR", "DeepSource issue pagination exceeded bound")
    if total_seen and seen != check_total:
        raise ProviderReadFailure("ERROR", "DeepSource issue pagination is incomplete")
    if not total_seen:
        return None
    if check_total is None:
        raise ProviderReadFailure("ERROR", "DeepSource issue total invariant failed")
    return check_total


def _classified_full_read(
    common: Mapping[str, Any],
    run_uid: str,
    observed: tuple[str, str],
    checks: int,
    findings: list[Mapping[str, Any]],
    provider_total: int | None,
    pages: int,
) -> dict[str, Any]:
    commit, run_state = observed
    raw_issue_count = len(findings)
    if provider_total is not None and provider_total != raw_issue_count:
        return _full_readback(
            common,
            completeness="READBACK_UNAVAILABLE",
            observed_head=commit,
            analysis_id=run_uid,
            run_state=run_state,
            coverage_record=coverage(
                "ERROR", pages=pages, count=0, reason="COUNT_TOTAL_MISMATCH"
            ),
            native={
                "checks": checks,
                "raw_issue_count": raw_issue_count,
                "provider_total": provider_total,
            },
        )
    retained = deduplicate_findings(findings)
    native: dict[str, Any] = {"checks": checks, "raw_issue_count": raw_issue_count}
    if provider_total is not None:
        native["provider_total"] = provider_total
    normalized_total = (
        provider_total
        if provider_total is not None and provider_total == len(retained)
        else None
    )
    return _full_readback(
        common,
        completeness="FULL_RUN",
        observed_head=commit,
        analysis_id=run_uid,
        run_state=run_state,
        coverage_record=coverage(
            "COMPLETE", pages=pages, count=len(retained), total=normalized_total
        ),
        findings=retained,
        native=native,
    )


def _read_full_run(
    client: GraphQLReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    run_uid: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    common: dict[str, Any] = {
        "repository": normalize_repository(repository),
        "pull_number": pull_number,
        "requested_head": requested_head,
        "observed_at": observed_at or _now(),
    }
    pages = _Pages()
    try:
        read = _read_run_pages(client, run_uid, pages)
    except ProviderReadFailure as exc:
        return _full_readback(
            common,
            completeness=_failure_completeness(exc),
            observed_head=None,
            analysis_id=run_uid,
            run_state="UNKNOWN",
            coverage_record=_failure_coverage(exc, pages=pages.count, count=0),
        )
    if read.run is None:
        return _full_readback(
            common,
            completeness="AMBIGUOUS",
            observed_head=None,
            analysis_id=run_uid,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "INCOMPLETE",
                pages=pages.count,
                count=0,
                reason="RUN_ASSOCIATION_AMBIGUOUS",
            ),
        )
    subject = _run_subject(read.run)
    unusable = _unusable_run(common, read, run_uid, subject, pages.count)
    if unusable is not None:
        return unusable
    _, commit, run_state, _ = subject
    findings: list[Mapping[str, Any]] = []
    provider_total: int | None = 0
    try:
        for check in read.checks:
            total = _read_check_issues(client, check, pages, findings)
            if total is None:
                provider_total = None
            elif provider_total is not None:
                provider_total += total
    except ProviderReadFailure as exc:
        return _full_readback(
            common,
            completeness=_failure_completeness(exc),
            observed_head=commit,
            analysis_id=run_uid,
            run_state=run_state,
            coverage_record=_failure_coverage(
                exc, pages=pages.count, count=len(findings)
            ),
            findings=findings,
        )
    return _classified_full_read(
        common,
        run_uid,
        (commit, run_state),
        len(read.checks),
        findings,
        provider_total,
        pages.count,
    )


def _comment_title(body: str) -> str:
    match = _H3_AFTER_PICTURE.search(body)
    if match is None:
        return "DeepSource issue"
    text = html.unescape(_TAG.sub("", match.group("title"))).strip()
    return " ".join(text.split()) or "DeepSource issue"


def _trusted_github_status(value: Mapping[str, Any]) -> bool:
    source_kind = value.get("source_kind")
    if source_kind == "commit_status":
        return (
            value.get("creator_login") == _GITHUB_BOT_LOGIN
            and value.get("creator_type") == _GITHUB_BOT_TYPE
        )
    if source_kind == "check_run":
        return value.get("app_slug") == _GITHUB_APP_SLUG
    return False


def _trusted_github_comment(value: Mapping[str, Any]) -> bool:
    return (
        value.get("author_login") == _GITHUB_BOT_LOGIN
        and value.get("author_type") == _GITHUB_BOT_TYPE
    )


def _github_status_summary(
    repository: str, statuses: Sequence[Mapping[str, Any]]
) -> tuple[set[str], dict[str, str]]:
    normalized = normalize_repository(repository)
    owner, name = normalized.split("/", 1)
    run_ids: set[str] = set()
    analyzer_states: dict[str, str] = {}
    seen_sources: set[tuple[str, ...]] = set()
    for status in statuses:
        if not _trusted_github_status(status):
            continue
        context = status.get("context")
        target = status.get("target_url")
        state = status.get("state")
        if not isinstance(context, str):
            continue
        context_match = _DEEPSOURCE_STATUS.fullmatch(context)
        if context_match is None:
            continue
        source_kind = str(status.get("source_kind"))
        is_commit_status = source_kind == "commit_status"
        if is_commit_status:
            # GitHub commit statuses are newest-first. Fence off the analyzer
            # before run-URL validation so an unusable newest status cannot
            # silently fall back to an older status for the same context.
            commit_status_key = ("commit_status_context", context)
            if commit_status_key in seen_sources:
                continue
            seen_sources.add(commit_status_key)
        if not isinstance(target, str):
            if is_commit_status:
                analyzer_states.setdefault(
                    context_match.group("analyzer").lower(), "unbound"
                )
            continue
        match = _RUN_URL.fullmatch(target)
        if (
            match is None
            or match.group("owner") != owner
            or match.group("repo") != name
        ):
            if is_commit_status:
                analyzer_states.setdefault(
                    context_match.group("analyzer").lower(), "unbound"
                )
            continue
        analyzer = match.group("analyzer")
        run_id = match.group("run")
        # Check-run reads request GitHub's latest filter, but multiple distinct
        # latest runs still make exact association ambiguous.
        if not is_commit_status:
            check_run_key = (source_kind, analyzer, run_id)
            if check_run_key in seen_sources:
                continue
            seen_sources.add(check_run_key)
        run_ids.add(run_id)
        analyzer_states.setdefault(analyzer, str(state))
    return run_ids, analyzer_states


def _diff_readback(
    common: Mapping[str, Any],
    *,
    completeness: str,
    observed_head: str,
    analysis_id: str | None,
    run_state: str,
    coverage_record: Mapping[str, Any],
    findings: Iterable[Mapping[str, Any]] = (),
    native: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_readback(
        provider="deepsource",
        adapter="deepsource-github/v1",
        repository=common["repository"],
        pull_number=common["pull_number"],
        requested_head=common["requested_head"],
        observed_head=observed_head,
        analysis_id=analysis_id,
        scope="DIFF",
        completeness=completeness,
        native_mode="DIFF_LOCAL",
        observed_at=common["observed_at"],
        run_state=run_state,
        coverage_record=coverage_record,
        findings=findings,
        native=native,
    )


def _comment_finding(
    comment: Mapping[str, Any], body: str, marker: str
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "id": marker,
        "message": _comment_title(body),
        "state": "open",
        "native_ref": marker,
        "provenance": [
            {
                "surface": "github-inline",
                "reference": str(comment.get("url", "")) or marker,
            }
        ],
    }
    path = comment.get("path")
    if isinstance(path, str) and path:
        finding["path"] = path
    line = comment.get("line")
    if type(line) is int and line > 0:
        finding["range"] = {"start_line": line, "end_line": line}
    severity = _SEVERITY.search(body)
    if severity is not None:
        finding["severity"] = severity.group("value").upper()
    category = _CATEGORY.search(body)
    if category is not None:
        finding["category"] = category.group("value").upper()
    return finding


def _comment_findings(
    comments: Sequence[Mapping[str, Any]], requested_head: str
) -> tuple[list[dict[str, Any]], int]:
    """The trusted, marked comments on the exact head, and how many were carried
    forward from another head and so excluded."""

    findings: list[dict[str, Any]] = []
    carried_forward = 0
    for comment in comments:
        if not _trusted_github_comment(comment):
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        marker = _ISSUE_MARKER.search(body)
        if marker is None or comment.get("commit_id") != requested_head:
            continue
        if comment.get("original_commit_id") != requested_head:
            carried_forward += 1
            continue
        findings.append(_comment_finding(comment, body, marker.group("id")))
    return findings, carried_forward


def _diff_local_from_github(
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_head: str,
    statuses: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    common: dict[str, Any] = {
        "repository": normalize_repository(repository),
        "pull_number": pull_number,
        "requested_head": requested_head,
        "observed_at": observed_at,
    }
    if observed_head != requested_head:
        return _diff_readback(
            common,
            completeness="AMBIGUOUS",
            observed_head=observed_head,
            analysis_id=None,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "INCOMPLETE", pages=1, count=0, reason="SUBJECT_MISMATCH"
            ),
        )
    run_ids, analyzer_states = _github_status_summary(common["repository"], statuses)
    if len(run_ids) != 1:
        return _diff_readback(
            common,
            completeness="AMBIGUOUS",
            observed_head=requested_head,
            analysis_id=None,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "INCOMPLETE", pages=1, count=0, reason="RUN_ASSOCIATION_AMBIGUOUS"
            ),
        )
    findings, carried_forward = _comment_findings(comments, requested_head)
    state_values = {value.lower() for value in analyzer_states.values()}
    retained = deduplicate_findings(findings)
    run_id = next(iter(run_ids))
    analyzers = {"analyzers": dict(sorted(analyzer_states.items()))}
    if not state_values or not state_values <= {
        "success",
        "failure",
        "pending",
        "error",
    }:
        return _diff_readback(
            common,
            completeness="DIFF_LOCAL",
            observed_head=requested_head,
            analysis_id=run_id,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "PARTIAL",
                pages=1,
                count=len(retained),
                reason="ANALYZER_STATE_UNAVAILABLE",
            ),
            findings=retained,
            native=analyzers,
        )
    if state_values & {"failure", "error"}:
        run_state = "FAILURE"
    elif "pending" in state_values:
        run_state = "PENDING"
    else:
        run_state = "SUCCESS"
    native: dict[str, Any] = dict(analyzers)
    if carried_forward:
        native["carried_forward_comments_excluded"] = carried_forward
    partial = None
    if state_values & {"pending", "error"}:
        partial = "ANALYZER_STATE_UNAVAILABLE"
    elif carried_forward:
        partial = "CARRIED_FORWARD_COMMENTS_EXCLUDED"
    coverage_record = (
        coverage("COMPLETE", pages=1, count=len(retained), total=len(retained))
        if partial is None
        else coverage("PARTIAL", pages=1, count=len(retained), reason=partial)
    )
    return _diff_readback(
        common,
        completeness="DIFF_LOCAL",
        observed_head=requested_head,
        analysis_id=run_id,
        run_state=run_state,
        coverage_record=coverage_record,
        findings=retained,
        native=native,
    )


# The validator's messages a full read's normalization failure may name in its
# readback (#309, slice A1). Each is fixed text, or a code-composed label and fixed
# text; nothing else passes, so provider content never reaches the readback.
NORMALIZATION_RULES = frozenset(
    {
        "AMBIGUOUS requires INCOMPLETE coverage",
        "AUTH_UNAVAILABLE requires UNAVAILABLE coverage",
        "FULL_RUN requires COMPLETE coverage",
        "INCOMPLETE coverage requires AMBIGUOUS completeness",
        "READBACK_UNAVAILABLE requires unavailable or incomplete read coverage",
        "complete coverage cannot carry a failure reason",
        "complete coverage count disagrees with provider total",
        "complete coverage count must match retained finding population",
        "complete coverage must retain at least one page",
        "complete readback must bind the requested exact head",
        "completeness state is unsupported",
        "coverage count is smaller than retained finding population",
        "coverage status is unsupported",
        "finding native provenance must be an object",
        "finding population exceeds bounded capacity",
        "finding provenance items must be objects",
        "finding provenance must be an array",
        "finding range ends before it starts",
        "finding range has unknown fields",
        "finding range must be an object",
        "finding tool identity has unknown fields",
        "finding tool identity must be an object",
        "native provenance must be an object",
        "non-complete coverage requires a reason",
        "readback scope is unsupported",
        "repository must use owner/name form",
        "repository name contains an unsafe path segment",
        "repository owner contains an unsafe path segment",
    }
)
NORMALIZATION_LABELLED_RULES = (
    " must be a non-empty string",
    " must be a non-negative integer",
    " must be a positive integer",
    " must be an exact 40-character SHA",
)
_LABELLED_RULE = re.compile(
    "[a-z][a-z_ ]{0,60}(?:"
    + "|".join(re.escape(suffix) for suffix in NORMALIZATION_LABELLED_RULES)
    + ")"
)
# The one message that interpolates a provider value: only its fixed text is kept.
_CONFLICTING_IDENTITY = re.compile(
    r"provider-native finding identity .+ is conflicting"
)
_CONFLICTING_IDENTITY_RULE = "a provider-native finding identity is conflicting"
_UNCLASSIFIED_RULE = "unclassified normalization failure"


def _normalization_rule(error: AnalyzerReadbackError) -> str:
    message = str(error)
    if message in NORMALIZATION_RULES or _LABELLED_RULE.fullmatch(message):
        return message
    if _CONFLICTING_IDENTITY.fullmatch(message):
        return _CONFLICTING_IDENTITY_RULE
    return _UNCLASSIFIED_RULE


def read_full_run(
    client: GraphQLReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    run_uid: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Read one DeepSource run without letting normalization conflicts abort peers."""

    try:
        return _read_full_run(
            client,
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            run_uid=run_uid,
            observed_at=observed_at,
        )
    except AnalyzerReadbackError as exc:
        observed = observed_at or _now()
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=None,
            analysis_id=run_uid,
            scope="FULL",
            completeness="READBACK_UNAVAILABLE",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "ERROR",
                pages=0,
                count=0,
                reason="NORMALIZATION_ERROR",
            ),
            findings=[],
            native={"normalization_error": _normalization_rule(exc)},
        )


def diff_local_from_github(
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_head: str,
    statuses: Sequence[Mapping[str, Any]],
    comments: Sequence[Mapping[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    """Project GitHub DeepSource evidence without surfacing model conflicts."""

    try:
        return _diff_local_from_github(
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=observed_head,
            statuses=statuses,
            comments=comments,
            observed_at=observed_at,
        )
    except AnalyzerReadbackError:
        try:
            run_ids, _ = _github_status_summary(repository, statuses)
        except AnalyzerReadbackError:
            run_ids = set()
        run_uid = next(iter(run_ids)) if len(run_ids) == 1 else None
        return build_readback(
            provider="deepsource",
            adapter="deepsource-github/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=None,
            analysis_id=run_uid,
            scope="DIFF",
            completeness="READBACK_UNAVAILABLE",
            native_mode="DIFF_LOCAL",
            observed_at=observed_at,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "ERROR",
                pages=0,
                count=0,
                reason="NORMALIZATION_ERROR",
            ),
            findings=[],
        )


# The capability discovery (#389 F3 R0; Router 6266752276 and 6267131349, PAO
# 6267150750). It is the repository's state when read: the API exposes no run's own
# configuration, analyzer versions or rules, so the receipt is never a past run's
# capability, and how the configuration selects issues stays unproven.
_DISCOVERY_SCHEMA = "gnostoa.deepsource-capability-discovery/v1"
_DISCOVERY_BINDING = "CURRENT_NOT_RUN_BOUND"
_DISCOVERY_DEADLINE_SECONDS = 300.0
_ANALYZER_VERSION = "analyzer.version"
_ANALYZER_NUM_ISSUES = "analyzer.numIssues"
# A value the read never reached, distinct from any the provider gave.
_UNREAD: object = object()
_DISCOVERY_UNKNOWN = (
    "how the configuration and each analyzer's meta options select its issues",
    "the configuration, analyzer versions and rules that any past run used",
    "repository settings that the API does not expose",
    "catalogue entries changed within one analyzer version and size: the API offers "
    "no snapshot or generation token",
)
# At most this many catalogue entries in one receipt, across every enabled analyzer
# (CodeAnt on #441).
_MAX_CATALOGUE_ENTRIES = 20_000


class _DiscoveryIncomplete(RuntimeError):
    """A read that stopped short of a provable answer, by its named reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _DiscoveryRead:
    __slots__ = ("count", "deadline", "login", "name", "pages")

    def __init__(self, login: str, name: str, deadline: float) -> None:
        self.login = login
        self.name = name
        self.deadline = deadline
        self.pages = _Pages()
        self.count = 0


def _discovery_page(
    client: DeadlineGraphQLReader,
    read: _DiscoveryRead,
    query: str,
    variables: Mapping[str, Any],
) -> Mapping[str, Any]:
    # A spent deadline reads no further page.
    if time.monotonic() >= read.deadline:
        raise _DiscoveryIncomplete("DEADLINE")
    page = client.graphql(query, variables, deadline=read.deadline)
    read.pages.count += 1
    return page


class _ConnectionPages:
    """One paginated connection, read page by page: the owner must not change between
    pages, the cursor must advance, a total must be given or missing from the first
    page on, a node's identity must not repeat, and the provider's total must be given
    and met."""

    def __init__(
        self,
        label: str,
        owner: Callable[[Mapping[str, Any]], object],
        identity: Callable[[Mapping[str, Any]], str],
    ) -> None:
        self.label = label
        self.owner = owner
        self.identity = identity
        self.nodes: list[Mapping[str, Any]] = []
        self.seen: set[str] = set()
        self.cursor: str | None = None
        self.expected: int | None = None
        self.total_seen = False
        self.first: object = _UNREAD
        self.first_total: bool | None = None

    def take(self, record: Mapping[str, Any], connection: object) -> bool:
        """Check one page and keep its nodes; whether another page follows."""

        self._check_owner(record)
        previous = self.cursor
        page_nodes, total, has_next, self.cursor = _page(connection, self.label)
        if has_next and self.cursor == previous:
            raise ProviderReadFailure(
                "ERROR", f"DeepSource {self.label} pagination did not advance"
            )
        self._check_total(total)
        for node in page_nodes:
            self._keep(node)
        return has_next

    def _check_owner(self, record: Mapping[str, Any]) -> None:
        current = self.owner(record)
        if self.first is _UNREAD:
            self.first = current
        elif current != self.first:
            raise ProviderReadFailure(
                "ERROR", f"DeepSource {self.label} owner changed during pagination"
            )

    def _check_total(self, total: int | None) -> None:
        if self.first_total is None:
            self.first_total = total is not None
        elif (total is not None) != self.first_total:
            # A total missing from the first page and given later is a change too
            # (Sourcery on #441).
            raise ProviderReadFailure(
                "ERROR", f"DeepSource {self.label} total availability changed"
            )
        self.expected, self.total_seen = _tracked_total(
            total, self.expected, self.total_seen, self.label
        )

    def _keep(self, node: Mapping[str, Any]) -> None:
        key = self.identity(node)
        if key in self.seen:
            raise ProviderReadFailure(
                "ERROR", f"DeepSource {self.label} repeats the identity {key}"
            )
        self.seen.add(key)
        self.nodes.append(node)

    def finish(self) -> list[Mapping[str, Any]]:
        if not self.total_seen:
            raise _DiscoveryIncomplete("TOTAL_UNAVAILABLE")
        if self.expected != len(self.nodes):
            raise _DiscoveryIncomplete("TOTAL_MISMATCH")
        return self.nodes


def _connection_nodes(
    fetch: Callable[[str | None], tuple[Mapping[str, Any], object]],
    label: str,
    owner: Callable[[Mapping[str, Any]], object],
    identity: Callable[[Mapping[str, Any]], str],
) -> list[Mapping[str, Any]]:
    """Every node of one paginated connection, at most `_MAX_PAGES` pages of it.
    `fetch(cursor)` gives the page's owning record and its connection."""

    pages = _ConnectionPages(label, owner, identity)
    for _ in range(_MAX_PAGES):
        record, connection = fetch(pages.cursor)
        if not pages.take(record, connection):
            return pages.finish()
    raise ProviderReadFailure("ERROR", f"DeepSource {label} pagination exceeded bound")


def _discovery_repository(
    page: Mapping[str, Any], read: _DiscoveryRead
) -> Mapping[str, Any]:
    repository = _mapping(
        _mapping(page.get("data"), "data").get("repository"), "repository"
    )
    account = _mapping(repository.get("account"), "repository.account")
    if (
        _text(repository.get("name"), "repository name") != read.name
        or _text(account.get("login"), "repository account login") != read.login
        or _text(account.get("vcsProvider"), "repository provider") != "GITHUB"
    ):
        raise ProviderReadFailure("ERROR", "DeepSource answered for another repository")
    return repository


def _selected(record: Mapping[str, Any], key: str, label: str) -> object:
    """A selected field's value. GraphQL returns every selected field, null or not,
    so an omitted one is a malformed answer, never a null (Sourcery on #441)."""

    if key not in record:
        raise ProviderReadFailure("ERROR", f"DeepSource {label} is missing")
    return record[key]


def _optional_text(value: object, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _optional_integer(value: object, label: str) -> int | None:
    return None if value is None else _integer(value, label)


def _canonical(value: object) -> str:
    """The shared canonical JSON (revix on #441). A value it cannot encode, such as
    a non-finite number, is a malformed answer, never a crash."""

    try:
        return canonical_json(value)
    except ValueError as error:
        raise ProviderReadFailure(
            "ERROR", "DeepSource configJson is not canonical JSON"
        ) from error


def _repository_state(
    client: DeadlineGraphQLReader,
    read: _DiscoveryRead,
    observed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The repository's configuration, enabled analyzers and ignore rules, read
    whole. What the first page returns is also given to `observed` at once, so a
    later failure keeps it (CodeAnt on #441)."""

    variables = {"name": read.name, "login": read.login}
    settings: dict[str, Any] = {}

    def analyzers_page(cursor: str | None) -> tuple[Mapping[str, Any], object]:
        page = _discovery_page(
            client, read, _REPOSITORY_ANALYZERS_QUERY, {**variables, "cursor": cursor}
        )
        repository = _discovery_repository(page, read)
        activated = _selected(repository, "isActivated", "repository.isActivated")
        if type(activated) is not bool:
            raise ProviderReadFailure(
                "ERROR", "DeepSource repository.isActivated is malformed"
            )
        if not settings:
            configuration = _selected(repository, "configJson", "repository.configJson")
            # DeepSource documents it as the .deepsource.toml "represented as a JSON
            # object", nullable (Codex on #441).
            if configuration is not None and type(configuration) is not dict:
                raise ProviderReadFailure(
                    "ERROR", "DeepSource repository.configJson is not an object"
                )
            _canonical(configuration)
            settings["activated"] = activated
            settings["configuration"] = configuration
            if observed is not None:
                observed.update(settings)
        return repository, repository.get("enabledAnalyzers")

    analyzers = _connection_nodes(
        analyzers_page,
        "enabledAnalyzers",
        # Every page selects both fields, so an omitted one is never the first
        # page's null (Codex on #441).
        lambda r: (
            _selected(r, "isActivated", "repository.isActivated"),
            _canonical(_selected(r, "configJson", "repository.configJson")),
        ),
        lambda node: _text(node.get("shortcode"), "analyzer.shortcode"),
    )

    def ignore_page(cursor: str | None) -> tuple[Mapping[str, Any], object]:
        page = _discovery_page(
            client,
            read,
            _REPOSITORY_IGNORE_RULES_QUERY,
            {**variables, "cursor": cursor},
        )
        repository = _discovery_repository(page, read)
        return repository, repository.get("ignoreRules")

    rules = _connection_nodes(
        ignore_page,
        "ignoreRules",
        lambda _r: None,
        lambda node: _text(node.get("id"), "ignoreRule.id"),
    )
    return {
        "activated": settings["activated"],
        "configuration": settings["configuration"],
        "analyzers": sorted(
            (
                {
                    "shortcode": _text(node.get("shortcode"), "analyzer.shortcode"),
                    "version": _optional_text(
                        _selected(node, "version", _ANALYZER_VERSION),
                        _ANALYZER_VERSION,
                    ),
                    "num_issues": _optional_integer(
                        _selected(node, "numIssues", _ANALYZER_NUM_ISSUES),
                        _ANALYZER_NUM_ISSUES,
                    ),
                }
                for node in analyzers
            ),
            key=lambda entry: entry["shortcode"],
        ),
        "ignore_rules": sorted(
            (
                {
                    "id": _text(node.get("id"), "ignoreRule.id"),
                    "level": _text(node.get("level"), "ignoreRule.level"),
                    "type": _text(node.get("type"), "ignoreRule.type"),
                    "issue": _text(
                        _mapping(node.get("issue"), "ignoreRule.issue").get(
                            "shortcode"
                        ),
                        "ignoreRule.issue.shortcode",
                    ),
                    "file_path": _optional_text(
                        _selected(node, "filePath", "ignoreRule.filePath"),
                        "ignoreRule.filePath",
                    ),
                    "glob_pattern": _optional_text(
                        _selected(node, "globPattern", "ignoreRule.globPattern"),
                        "ignoreRule.globPattern",
                    ),
                }
                for node in rules
            ),
            key=lambda entry: entry["id"],
        ),
    }


def _catalogue_issue(node: Mapping[str, Any]) -> dict[str, Any]:
    recommended = node.get("isRecommended")
    if type(recommended) is not bool:
        raise ProviderReadFailure(
            "ERROR", "DeepSource issue.isRecommended is malformed"
        )
    tags = node.get("tags")
    if not isinstance(tags, list):
        raise ProviderReadFailure("ERROR", "DeepSource issue.tags is malformed")
    return {
        "shortcode": _text(node.get("shortcode"), "issue.shortcode"),
        "title": _text(node.get("title"), "issue.title"),
        "category": _text(node.get("category"), "issue.category"),
        "severity": _text(node.get("severity"), "issue.severity"),
        "is_recommended": recommended,
        "tags": [_text(tag, "issue.tag") for tag in tags],
    }


def _analyzer_catalogue(
    client: DeadlineGraphQLReader, read: _DiscoveryRead, enabled: Mapping[str, Any]
) -> dict[str, Any]:
    """One enabled analyzer's whole catalogue, at the version and size the
    repository state gave it."""

    shortcode = enabled["shortcode"]

    def catalogue_page(cursor: str | None) -> tuple[Mapping[str, Any], object]:
        page = _discovery_page(
            client,
            read,
            _ANALYZER_CATALOGUE_QUERY,
            {"shortcode": shortcode, "cursor": cursor},
        )
        # An enabled analyzer with no catalogue (a null) is malformed, as any
        # non-object is.
        analyzer = _mapping(
            _mapping(page.get("data"), "data").get("analyzer"), "analyzer"
        )
        if _text(analyzer.get("shortcode"), "analyzer.shortcode") != shortcode:
            raise ProviderReadFailure(
                "ERROR", "DeepSource answered for another analyzer"
            )
        return analyzer, analyzer.get("issues")

    observed: dict[str, Any] = {}

    def owner(analyzer: Mapping[str, Any]) -> tuple[object, object]:
        identity = (
            _optional_text(
                _selected(analyzer, "version", _ANALYZER_VERSION), _ANALYZER_VERSION
            ),
            _optional_integer(
                _selected(analyzer, "numIssues", _ANALYZER_NUM_ISSUES),
                _ANALYZER_NUM_ISSUES,
            ),
        )
        observed.setdefault("identity", identity)
        return identity

    nodes = _connection_nodes(
        catalogue_page,
        "analyzer.issues",
        owner,
        lambda node: _text(node.get("shortcode"), "issue.shortcode"),
    )
    version, num_issues = observed["identity"]
    if version is None or num_issues is None:
        raise _DiscoveryIncomplete("ANALYZER_IDENTITY_UNAVAILABLE")
    if (version, num_issues) != (enabled["version"], enabled["num_issues"]):
        raise _DiscoveryIncomplete("CAPABILITY_STATE_CHANGED")
    if num_issues != len(nodes):
        raise _DiscoveryIncomplete("TOTAL_MISMATCH")
    if read.count + len(nodes) > _MAX_CATALOGUE_ENTRIES:
        raise _DiscoveryIncomplete("BUDGET")
    # Converted before it is counted, so a malformed entry counts nothing (Codex and
    # Sourcery on #441).
    catalogue = sorted(
        (_catalogue_issue(node) for node in nodes),
        key=lambda entry: entry["shortcode"],
    )
    read.count += len(catalogue)
    return {**enabled, "catalogue": catalogue}


def _configuration(value: object) -> dict[str, Any]:
    """The configuration as the API gave it. An absent one is never an empty one,
    and one the read never reached is neither."""

    if value is _UNREAD:
        return {"state": "UNREAD"}
    if value is None:
        return {"state": "ABSENT"}
    return {
        "state": "PRESENT",
        "digest": canonical_digest(value),
        "json": value,
    }


def read_capability_discovery(
    client: DeadlineGraphQLReader,
    repository: str,
    *,
    deadline_seconds: float = _DISCOVERY_DEADLINE_SECONDS,
) -> dict[str, Any]:
    """The repository's current DeepSource capability: its configuration, enabled
    analyzers and ignore rules, read before and after every enabled analyzer's issue
    catalogue. COMPLETE only when each connection is read whole and the two
    repository reads agree; it stays CURRENT_NOT_RUN_BOUND, and the effective
    configuration UNPROVEN."""

    if not math.isfinite(deadline_seconds) or deadline_seconds <= 0:
        # A budget that is spent, NaN or infinite reads nothing (Amazon Q on #441).
        raise ValueError("deadline_seconds must be a finite positive number")
    name = normalize_repository(repository)
    login, short = name.split("/")
    read = _DiscoveryRead(login, short, time.monotonic() + deadline_seconds)
    observed_at = _now()
    # What the read never reached is null, never an empty list (revix on #441).
    state: dict[str, Any] = {
        "activated": None,
        "configuration": _UNREAD,
        "analyzers": None,
        "ignore_rules": None,
    }
    try:
        first = _repository_state(client, read, state)
        state = {**first, "analyzers": []}
        # Each catalogue is kept as soon as it is read whole, so a later failure keeps
        # what was read (Codex and Sourcery on #441).
        for enabled in first["analyzers"]:
            state["analyzers"].append(_analyzer_catalogue(client, read, enabled))
        again = _repository_state(client, read)
        before = (
            state["activated"],
            _canonical(state["configuration"]),
            [
                (a["shortcode"], a["version"], a["num_issues"])
                for a in state["analyzers"]
            ],
            state["ignore_rules"],
        )
        after = (
            again["activated"],
            _canonical(again["configuration"]),
            [
                (a["shortcode"], a["version"], a["num_issues"])
                for a in again["analyzers"]
            ],
            again["ignore_rules"],
        )
        if before != after:
            raise _DiscoveryIncomplete("CAPABILITY_STATE_CHANGED")
        if time.monotonic() >= read.deadline:
            # Read whole, but not within the budget (Sourcery on #441).
            raise _DiscoveryIncomplete("DEADLINE")
        record = coverage("COMPLETE", pages=read.pages.count, count=read.count)
    except _DiscoveryIncomplete as stopped:
        record = coverage(
            "INCOMPLETE",
            pages=read.pages.count,
            count=read.count,
            reason=stopped.reason,
        )
    except ProviderReadFailure as failure:
        record = (
            coverage(
                "INCOMPLETE",
                pages=read.pages.count,
                count=read.count,
                reason="DEADLINE",
            )
            if failure.kind == "DEADLINE"
            else _failure_coverage(failure, pages=read.pages.count, count=read.count)
        )
    return {
        "schema": _DISCOVERY_SCHEMA,
        "binding": _DISCOVERY_BINDING,
        "repository": name,
        "observed_at": observed_at,
        "coverage": record,
        "configuration": _configuration(state["configuration"]),
        "analyzers": state["analyzers"],
        "ignore_rules": state["ignore_rules"],
        "activated": state["activated"],
        "effective_configuration": "UNPROVEN",
        "unknown": list(_DISCOVERY_UNKNOWN),
    }
