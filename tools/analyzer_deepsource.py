from __future__ import annotations

import html
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

from .analyzer_readback import (
    AnalyzerReadbackError,
    build_readback,
    coverage,
    deduplicate_findings,
    normalize_repository,
)

_API_ROOT = "https://api.deepsource.com"
_GRAPHQL_URL = f"{_API_ROOT}/graphql/"
_TOKEN_ENV = "DEEPSOURCE_API_TOKEN"  # nosec B105 -- environment variable name, not a credential
_TIMEOUT_SECONDS = 30
_MAX_RESPONSE_BYTES = 4_194_304
_MAX_PAGES = 100
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


_ADMITTED_GRAPHQL_READ_QUERIES = frozenset({_RUN_QUERY, _CHECK_QUERY})


class ProviderReadFailure(RuntimeError):
    def __init__(self, kind: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class GraphQLReader(Protocol):
    def graphql(
        self, query: str, variables: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...


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

    def graphql(self, query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        if query not in _ADMITTED_GRAPHQL_READ_QUERIES:
            raise ProviderReadFailure(
                "ERROR", "DeepSource unsupported GraphQL read operation"
            )
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
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderReadFailure(
                    "AUTH", "DeepSource authentication unavailable", status=exc.code
                ) from exc
            if exc.code == 429:
                raise ProviderReadFailure(
                    "RATE_LIMIT", "DeepSource API rate limited", status=exc.code
                ) from exc
            raise ProviderReadFailure(
                "UNAVAILABLE", f"DeepSource API HTTP {exc.code}", status=exc.code
            ) from exc
        # URLError is an OSError.
        except (OSError, http.client.HTTPException) as exc:
            raise ProviderReadFailure(
                "UNAVAILABLE", "DeepSource API unavailable"
            ) from exc
        except ValueError:
            # HTTP header validation can include credential bytes in its error.
            raise ProviderReadFailure(
                "ERROR", "DeepSource request failed validation"
            ) from None
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ProviderReadFailure(
                "ERROR", "DeepSource API response exceeds bounded size"
            )
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderReadFailure(
                "ERROR", "DeepSource API returned invalid JSON"
            ) from exc
        if not isinstance(document, Mapping):
            raise ProviderReadFailure(
                "ERROR", "DeepSource GraphQL response must be an object"
            )
        errors = document.get("errors")
        if errors:
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
    except AnalyzerReadbackError:
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
