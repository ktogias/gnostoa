from __future__ import annotations

import html
import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
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
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise ProviderReadFailure(
                "UNAVAILABLE", "DeepSource API unavailable"
            ) from exc
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
            "analyzer": _text(analyzer.get("shortcode"), "analyzer.shortcode"),
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
        "start_column": begin_column,
        "end_line": end_line,
        "end_column": end_column,
    }
    return finding


def _read_full_run(
    client: GraphQLReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    run_uid: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    repository = normalize_repository(repository)
    observed = observed_at or _now()
    pages = 0
    checks: list[Mapping[str, Any]] = []
    run_record: Mapping[str, Any] | None = None
    check_cursor: str | None = None
    expected_checks_total: int | None = None
    checks_total_seen = False
    try:
        for _ in range(_MAX_PAGES):
            page = client.graphql(
                _RUN_QUERY, {"runUid": run_uid, "cursor": check_cursor}
            )
            pages += 1
            data = _mapping(page.get("data"), "data")
            raw_run = data.get("run")
            if raw_run is None:
                return build_readback(
                    provider="deepsource",
                    adapter="deepsource-graphql/v1",
                    repository=repository,
                    pull_number=pull_number,
                    requested_head=requested_head,
                    observed_head=None,
                    analysis_id=run_uid,
                    scope="FULL",
                    completeness="AMBIGUOUS",
                    native_mode="FULL_RUN",
                    observed_at=observed,
                    run_state="UNKNOWN",
                    coverage_record=coverage(
                        "INCOMPLETE",
                        pages=pages,
                        count=0,
                        reason="RUN_ASSOCIATION_AMBIGUOUS",
                    ),
                    findings=[],
                )
            run = _mapping(raw_run, "run")
            subject = _run_subject(run)
            if run_record is None:
                run_record = run
            elif subject != _run_subject(run_record):
                raise ProviderReadFailure(
                    "ERROR", "DeepSource run changed during pagination"
                )
            page_checks, total, has_next, check_cursor = _page(
                run.get("checks"), "run.checks"
            )
            if total is not None:
                if not checks_total_seen:
                    expected_checks_total = total
                    checks_total_seen = True
                elif total != expected_checks_total:
                    raise ProviderReadFailure(
                        "ERROR", "DeepSource check total changed during pagination"
                    )
            elif checks_total_seen:
                raise ProviderReadFailure(
                    "ERROR",
                    "DeepSource check total availability changed during pagination",
                )
            checks.extend(page_checks)
            for check in page_checks:
                _text(check.get("id"), "check.id")
                _text(check.get("status"), "check.status")
            if not has_next:
                break
        else:
            raise ProviderReadFailure(
                "ERROR", "DeepSource check pagination exceeded bound"
            )
    except ProviderReadFailure as exc:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=None,
            analysis_id=run_uid,
            scope="FULL",
            completeness=_failure_completeness(exc),
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state="UNKNOWN",
            coverage_record=_failure_coverage(exc, pages=pages, count=0),
            findings=[],
        )

    if run_record is None:
        raise AssertionError("unreachable: run pagination produced no record")
    actual_uid, commit, run_state, actual_repository = _run_subject(run_record)
    if actual_uid != run_uid:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=actual_uid,
            scope="FULL",
            completeness="AMBIGUOUS",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "INCOMPLETE", pages=pages, count=0, reason="RUN_UID_MISMATCH"
            ),
            findings=[],
        )
    if actual_repository != repository:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="AMBIGUOUS",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "INCOMPLETE", pages=pages, count=0, reason="REPOSITORY_MISMATCH"
            ),
            findings=[],
        )
    if commit != requested_head:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="AMBIGUOUS",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "INCOMPLETE", pages=pages, count=0, reason="SUBJECT_MISMATCH"
            ),
            findings=[],
        )
    if run_state not in _COMPLETED_RUN_STATUSES:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="READBACK_UNAVAILABLE",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "PARTIAL",
                pages=pages,
                count=0,
                reason="ANALYSIS_RUN_NOT_COMPLETE",
            ),
            findings=[],
        )

    if not checks:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="READBACK_UNAVAILABLE",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "PARTIAL", pages=pages, count=0, reason="NO_ANALYZER_CHECKS"
            ),
            findings=[],
        )

    check_states = {
        _text(check.get("id"), "check.id"): _text(check.get("status"), "check.status")
        for check in checks
    }
    if any(state not in _COMPLETED_CHECK_STATUSES for state in check_states.values()):
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="READBACK_UNAVAILABLE",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "PARTIAL",
                pages=pages,
                count=0,
                reason="ANALYZER_CHECK_NOT_COMPLETE",
            ),
            findings=[],
            native={"check_states": check_states},
        )

    if checks_total_seen and len(checks) != expected_checks_total:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="READBACK_UNAVAILABLE",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "PARTIAL", pages=pages, count=0, reason="CHECK_PAGINATION_INCOMPLETE"
            ),
            findings=[],
        )

    findings: list[Mapping[str, Any]] = []
    provider_total = 0
    provider_total_known = True
    try:
        for check in checks:
            check_id = _text(check.get("id"), "check.id")
            cursor: str | None = None
            check_total: int | None = None
            check_total_seen = False
            seen = 0
            for _ in range(_MAX_PAGES):
                page = client.graphql(_CHECK_QUERY, {"id": check_id, "cursor": cursor})
                pages += 1
                data = _mapping(page.get("data"), "data")
                node = _mapping(data.get("node"), "check node")
                if _text(node.get("id"), "check.id") != check_id:
                    raise ProviderReadFailure(
                        "ERROR", "DeepSource check identity changed during pagination"
                    )
                issue_nodes, total, has_next, cursor = _page(
                    node.get("issues"), "check.issues"
                )
                if total is not None:
                    if not check_total_seen:
                        check_total = total
                        check_total_seen = True
                    elif total != check_total:
                        raise ProviderReadFailure(
                            "ERROR",
                            "DeepSource issue total changed during pagination",
                        )
                elif check_total_seen:
                    raise ProviderReadFailure(
                        "ERROR",
                        "DeepSource issue total availability changed during pagination",
                    )
                findings.extend(_issue_finding(node, issue) for issue in issue_nodes)
                seen += len(issue_nodes)
                if not has_next:
                    break
            else:
                raise ProviderReadFailure(
                    "ERROR", "DeepSource issue pagination exceeded bound"
                )
            if check_total_seen and seen != check_total:
                raise ProviderReadFailure(
                    "ERROR", "DeepSource issue pagination is incomplete"
                )
            if check_total_seen:
                if check_total is None:
                    raise ProviderReadFailure(
                        "ERROR", "DeepSource issue total invariant failed"
                    )
                provider_total += check_total
            else:
                provider_total_known = False
    except ProviderReadFailure as exc:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness=_failure_completeness(exc),
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=_failure_coverage(exc, pages=pages, count=len(findings)),
            findings=findings,
        )

    raw_issue_count = len(findings)
    if provider_total_known and provider_total != raw_issue_count:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=commit,
            analysis_id=run_uid,
            scope="FULL",
            completeness="READBACK_UNAVAILABLE",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state=run_state,
            coverage_record=coverage(
                "ERROR",
                pages=pages,
                count=0,
                reason="COUNT_TOTAL_MISMATCH",
            ),
            findings=[],
            native={
                "checks": len(checks),
                "raw_issue_count": raw_issue_count,
                "provider_total": provider_total,
            },
        )

    retained = deduplicate_findings(findings)
    native = {
        "checks": len(checks),
        "raw_issue_count": raw_issue_count,
    }
    if provider_total_known:
        native["provider_total"] = provider_total
    normalized_total = (
        provider_total
        if provider_total_known and provider_total == len(retained)
        else None
    )
    return build_readback(
        provider="deepsource",
        adapter="deepsource-graphql/v1",
        repository=repository,
        pull_number=pull_number,
        requested_head=requested_head,
        observed_head=commit,
        analysis_id=run_uid,
        scope="FULL",
        completeness="FULL_RUN",
        native_mode="FULL_RUN",
        observed_at=observed,
        run_state=run_state,
        coverage_record=coverage(
            "COMPLETE",
            pages=pages,
            count=len(retained),
            total=normalized_total,
        ),
        findings=retained,
        native=native,
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
    repository: str, statuses: list[Mapping[str, Any]]
) -> tuple[set[str], dict[str, str]]:
    normalized = normalize_repository(repository)
    owner, name = normalized.split("/", 1)
    run_ids: set[str] = set()
    analyzer_states: dict[str, str] = {}
    seen_sources: set[tuple[str, str]] = set()
    for status in statuses:
        if not _trusted_github_status(status):
            continue
        context = status.get("context")
        target = status.get("target_url")
        state = status.get("state")
        if (
            not isinstance(context, str)
            or _DEEPSOURCE_STATUS.fullmatch(context) is None
        ):
            continue
        if not isinstance(target, str):
            continue
        match = _RUN_URL.fullmatch(target)
        if (
            match is None
            or match.group("owner") != owner
            or match.group("repo") != name
        ):
            continue
        analyzer = match.group("analyzer")
        source_key = (str(status.get("source_kind")), analyzer)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        run_ids.add(match.group("run"))
        analyzer_states.setdefault(analyzer, str(state))
    return run_ids, analyzer_states


def _diff_local_from_github(
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_head: str,
    statuses: list[Mapping[str, Any]],
    comments: list[Mapping[str, Any]],
    observed_at: str,
) -> dict[str, Any]:
    repository = normalize_repository(repository)
    if observed_head != requested_head:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-github/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=observed_head,
            analysis_id=None,
            scope="DIFF",
            completeness="AMBIGUOUS",
            native_mode="DIFF_LOCAL",
            observed_at=observed_at,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "INCOMPLETE",
                pages=1,
                count=0,
                reason="SUBJECT_MISMATCH",
            ),
            findings=[],
        )
    run_ids, analyzer_states = _github_status_summary(repository, statuses)
    if len(run_ids) != 1:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-github/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=requested_head,
            analysis_id=None,
            scope="DIFF",
            completeness="AMBIGUOUS",
            native_mode="DIFF_LOCAL",
            observed_at=observed_at,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "INCOMPLETE",
                pages=1,
                count=0,
                reason="RUN_ASSOCIATION_AMBIGUOUS",
            ),
            findings=[],
        )
    findings: list[dict[str, Any]] = []
    carried_forward_comments = 0
    for comment in comments:
        if not _trusted_github_comment(comment):
            continue
        body = comment.get("body")
        if not isinstance(body, str):
            continue
        marker = _ISSUE_MARKER.search(body)
        if marker is None:
            continue
        comment_head = comment.get("commit_id")
        original_comment_head = comment.get("original_commit_id")
        if comment_head != requested_head:
            continue
        if original_comment_head != requested_head:
            carried_forward_comments += 1
            continue
        finding: dict[str, Any] = {
            "id": marker.group("id"),
            "message": _comment_title(body),
            "state": "open",
            "native_ref": marker.group("id"),
            "provenance": [
                {
                    "surface": "github-inline",
                    "reference": str(comment.get("url", "")) or marker.group("id"),
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
        findings.append(finding)
    state_values = {value.lower() for value in analyzer_states.values()}
    retained = deduplicate_findings(findings)
    if not state_values or not state_values <= {
        "success",
        "failure",
        "pending",
        "error",
    }:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-github/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=requested_head,
            analysis_id=next(iter(run_ids)),
            scope="DIFF",
            completeness="DIFF_LOCAL",
            native_mode="DIFF_LOCAL",
            observed_at=observed_at,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "PARTIAL",
                pages=1,
                count=len(retained),
                reason="ANALYZER_STATE_UNAVAILABLE",
            ),
            findings=retained,
            native={"analyzers": dict(sorted(analyzer_states.items()))},
        )
    if state_values & {"failure", "error"}:
        run_state = "FAILURE"
    elif "pending" in state_values:
        run_state = "PENDING"
    else:
        run_state = "SUCCESS"
    native: dict[str, Any] = {"analyzers": dict(sorted(analyzer_states.items()))}
    if carried_forward_comments:
        native["carried_forward_comments_excluded"] = carried_forward_comments
    if state_values & {"pending", "error"}:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-github/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=requested_head,
            analysis_id=next(iter(run_ids)),
            scope="DIFF",
            completeness="DIFF_LOCAL",
            native_mode="DIFF_LOCAL",
            observed_at=observed_at,
            run_state=run_state,
            coverage_record=coverage(
                "PARTIAL",
                pages=1,
                count=len(retained),
                reason="ANALYZER_STATE_UNAVAILABLE",
            ),
            findings=retained,
            native=native,
        )
    if carried_forward_comments:
        return build_readback(
            provider="deepsource",
            adapter="deepsource-github/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=requested_head,
            analysis_id=next(iter(run_ids)),
            scope="DIFF",
            completeness="DIFF_LOCAL",
            native_mode="DIFF_LOCAL",
            observed_at=observed_at,
            run_state=run_state,
            coverage_record=coverage(
                "PARTIAL",
                pages=1,
                count=len(retained),
                reason="CARRIED_FORWARD_COMMENTS_EXCLUDED",
            ),
            findings=retained,
            native=native,
        )
    return build_readback(
        provider="deepsource",
        adapter="deepsource-github/v1",
        repository=repository,
        pull_number=pull_number,
        requested_head=requested_head,
        observed_head=requested_head,
        analysis_id=next(iter(run_ids)),
        scope="DIFF",
        completeness="DIFF_LOCAL",
        native_mode="DIFF_LOCAL",
        observed_at=observed_at,
        run_state=run_state,
        coverage_record=coverage(
            "COMPLETE", pages=1, count=len(retained), total=len(retained)
        ),
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
    statuses: list[Mapping[str, Any]],
    comments: list[Mapping[str, Any]],
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
