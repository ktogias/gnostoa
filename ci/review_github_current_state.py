from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from tools.review_model import parse_rfc3339
from tools.review_reconcile import (
    PROVIDER_STATE_SCHEMA_VERSION,
    parse_projection_comment,
    render_projection,
)

_API_ROOT = "https://api.github.com"
_GRAPHQL_ROOT = f"{_API_ROOT}/graphql"
_API_VERSION = "2022-11-28"
_REVIEW_THREADS_QUERY = """
query ReviewThreads(
  $owner: String!
  $name: String!
  $number: Int!
  $cursor: String
) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes {
          id
          isResolved
          isOutdated
          comments(first: 1) {
            nodes {
              databaseId
              url
              replyTo {
                databaseId
                url
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""
_MAX_RESPONSE_BYTES = 4_194_304
_MAX_BODY_BYTES = 65_536
_MAX_PAGES = 20
_MAX_ITEMS = 5_000
_MAX_OPEN_PULLS = 8
_MAX_PUBLICATION_PAYLOAD_BYTES = 300_000
_MAX_COLLECTION_PASSES = 3
_PROJECTION_AUTHOR = "github-actions[bot]"
_TIMEOUT_SECONDS = 30
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')
_GITHUB_EXECUTION_ID = re.compile(r"^github-actions:([1-9][0-9]*):([1-9][0-9]*)$")


class ProviderReadError(RuntimeError):
    """A bounded GitHub provider read failed."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ProviderWriteError(RuntimeError):
    """A bounded GitHub provider write failed."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class JsonReader(Protocol):
    def get(self, url: str) -> tuple[Any, dict[str, str]]: ...

    def graphql(self, query: str, variables: dict[str, Any]) -> Any: ...


def _validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProviderReadError("GitHub API URL has an invalid port") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ProviderReadError("GitHub API URL is outside the admitted host")
    return url


class _GitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep every authenticated redirect inside the admitted GitHub API origin."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        admitted_url = _validate_api_url(newurl)
        authorization = req.get_header("Authorization")
        redirected = super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            admitted_url,
        )
        if redirected is not None and authorization is not None:
            redirected.add_unredirected_header("Authorization", authorization)
        return redirected


def _decode_json(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderReadError(f"{label} returned invalid JSON") from exc


class GitHubRestClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("GitHub token is required")
        self._token = token
        self._opener = urllib.request.build_opener(_GitHubRedirectHandler())

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        read: bool = False,
    ) -> tuple[Any, dict[str, str]]:
        encoded = None
        if payload is not None:
            encoded = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        request = urllib.request.Request(
            _validate_api_url(url),
            data=encoded,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
                "User-Agent": "gnostoa-useful-l1",
                **({"Content-Type": "application/json"} if encoded is not None else {}),
            },
        )
        request.add_unredirected_header(
            "Authorization",
            f"Bearer {self._token}",
        )
        try:
            # The request and every redirect target are restricted to HTTPS
            # api.github.com on the default/443 port before credentials are sent.
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected
            with self._opener.open(
                request,
                timeout=_TIMEOUT_SECONDS,
            ) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    raise ProviderReadError("GitHub API response exceeds bounded size")
                headers = {
                    key.lower(): value for key, value in response.headers.items()
                }
                return _decode_json(raw, "GitHub API"), headers
        except urllib.error.HTTPError as exc:
            detail = exc.read(4_096).decode("utf-8", errors="replace")
            headers = {key.lower(): value for key, value in (exc.headers or {}).items()}
            message = f"GitHub API HTTP {exc.code}"
            if detail:
                message += f": {' '.join(detail.split())[:512]}"
            if method == "GET" or read:
                status = exc.code
                if exc.code == 403 and _http_error_indicates_rate_limit(
                    headers,
                    detail,
                ):
                    status = 429
                raise ProviderReadError(message, status=status) from exc
            raise ProviderWriteError(
                f"GitHub API write rejected with HTTP {exc.code}",
                status=exc.code,
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if method == "GET" or read:
                raise ProviderReadError("GitHub API transport failed") from exc
            raise ProviderWriteError("GitHub API transport failed") from exc

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        return self._request("GET", url)

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        document, headers = self._request(
            "POST",
            _GRAPHQL_ROOT,
            {"query": query, "variables": variables},
            read=True,
        )
        if not isinstance(document, dict):
            raise ProviderReadError("GitHub GraphQL returned invalid shape")
        errors = document.get("errors")
        if errors:
            rate_limited = (
                headers.get("x-ratelimit-remaining") == "0"
                or bool(headers.get("retry-after"))
                or _graphql_errors_indicate_rate_limit(errors)
            )
            raise ProviderReadError(
                "GitHub GraphQL returned errors",
                status=429 if rate_limited else None,
            )
        return document

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        document, _ = self._request("POST", url, payload)
        return document

    def patch(self, url: str, payload: dict[str, Any]) -> Any:
        document, _ = self._request("PATCH", url, payload)
        return document


def _http_error_indicates_rate_limit(
    headers: dict[str, str],
    detail: str,
) -> bool:
    return (
        headers.get("x-ratelimit-remaining") == "0"
        or bool(headers.get("retry-after"))
        or "rate limit" in detail.lower()
    )


def _graphql_errors_indicate_rate_limit(errors: Any) -> bool:
    if not isinstance(errors, list):
        return False
    for raw_error in errors:
        if not isinstance(raw_error, dict):
            continue
        message = raw_error.get("message")
        if isinstance(message, str) and "rate limit" in message.lower():
            return True
    return False


def _next_url(headers: dict[str, str]) -> str | None:
    link = headers.get("link")
    if not link:
        return None
    match = _NEXT_LINK.search(link)
    if match is None:
        return None
    return _validate_api_url(match.group(1))


def _error_status(error: ProviderReadError, pages: int) -> str:
    if error.status == 429:
        return "RATE_LIMITED"
    return "PARTIAL" if pages else "ERROR"


def _list_page(payload: Any) -> list[Any]:
    if not isinstance(payload, list):
        raise ProviderReadError("GitHub paginated source did not return an array")
    return payload


def _check_page(payload: Any) -> list[Any]:
    if not isinstance(payload, dict):
        raise ProviderReadError("GitHub check-runs source has invalid shape")
    checks = payload.get("check_runs")
    if not isinstance(checks, list):
        raise ProviderReadError("GitHub check-runs source has invalid shape")
    return checks


def _collect_pages(
    client: JsonReader,
    first_url: str,
    *,
    page_items: Any = _list_page,
    normalize: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url: str | None = first_url
    items: list[dict[str, Any]] = []
    pages = 0
    omitted_total = 0
    while url is not None:
        if pages >= _MAX_PAGES:
            return items, {
                "status": "PARTIAL",
                "pages": pages,
                "count": len(items),
                "limit": "page_limit",
            }
        try:
            payload, headers = client.get(url)
            raw_items = page_items(payload)
            normalized: list[dict[str, Any]] = []
            for item in raw_items:
                value = normalize(item)
                if value is None:
                    omitted_total += 1
                    continue
                normalized.append(value)
        except ProviderReadError as exc:
            return items, {
                "status": _error_status(exc, pages),
                "pages": pages,
                "count": len(items),
                "error": str(exc),
            }
        if len(items) + len(normalized) > _MAX_ITEMS:
            remaining = max(0, _MAX_ITEMS - len(items))
            items.extend(normalized[:remaining])
            return items, {
                "status": "PARTIAL",
                "pages": pages + 1,
                "count": len(items),
                "limit": "item_limit",
            }
        items.extend(normalized)
        pages += 1
        url = _next_url(headers)
    if omitted_total:
        return items, {
            "status": "PARTIAL",
            "pages": pages,
            "count": len(items),
            "omitted": omitted_total,
            "reason": "unsubmitted_provider_items",
        }
    return items, {"status": "COMPLETE", "pages": pages, "count": len(items)}


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ProviderReadError(f"{label} must be a boolean")
    return value


def _combined_coverage_status(*coverages: dict[str, Any]) -> str:
    statuses = {item.get("status") for item in coverages}
    for status in ("ERROR", "UNAVAILABLE", "RATE_LIMITED", "PARTIAL"):
        if status in statuses:
            return status
    return "COMPLETE"


def _collect_review_threads(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    review_comments: list[dict[str, Any]],
    review_observation_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    owner, name = repository.split("/", 1)
    comments_by_id = {
        item["id"]: item for item in review_comments if isinstance(item.get("id"), str)
    }
    cursor: str | None = None
    items: list[dict[str, Any]] = []
    pages = 0
    omitted_roots = 0
    omitted_reviews = 0

    while True:
        if pages >= _MAX_PAGES:
            return items, {
                "status": "PARTIAL",
                "pages": pages,
                "count": len(items),
                "limit": "page_limit",
            }
        try:
            payload = client.graphql(
                _REVIEW_THREADS_QUERY,
                {
                    "owner": owner,
                    "name": name,
                    "number": pull_number,
                    "cursor": cursor,
                },
            )
            graphql_payload = _mapping(payload, "graphql response")
            data = _mapping(graphql_payload.get("data"), "graphql.data")
            repository_payload = _mapping(
                data.get("repository"),
                "graphql.data.repository",
            )
            pull_payload = _mapping(
                repository_payload.get("pullRequest"),
                "graphql.data.repository.pullRequest",
            )
            connection = _mapping(
                pull_payload.get("reviewThreads"),
                "graphql.reviewThreads",
            )
            nodes = connection.get("nodes")
            if not isinstance(nodes, list):
                raise ProviderReadError("GitHub reviewThreads.nodes must be an array")
            page_info = _mapping(
                connection.get("pageInfo"),
                "graphql.reviewThreads.pageInfo",
            )
            has_next = _boolean(
                page_info.get("hasNextPage"),
                "graphql.reviewThreads.pageInfo.hasNextPage",
            )
            end_cursor = page_info.get("endCursor")

            normalized: list[dict[str, Any]] = []
            for raw_node in nodes:
                node = _mapping(raw_node, "graphql.reviewThread")
                thread_id = _text(node.get("id"), "graphql.reviewThread.id")
                resolved = _boolean(
                    node.get("isResolved"),
                    "graphql.reviewThread.isResolved",
                )
                outdated = _boolean(
                    node.get("isOutdated"),
                    "graphql.reviewThread.isOutdated",
                )
                comments = _mapping(
                    node.get("comments"),
                    "graphql.reviewThread.comments",
                ).get("nodes")
                if not isinstance(comments, list) or not comments:
                    omitted_roots += 1
                    continue
                root_comment = _mapping(
                    comments[0],
                    "graphql.reviewThread.comments[0]",
                )
                reply_to = root_comment.get("replyTo")
                identity_comment = (
                    _mapping(
                        reply_to,
                        "graphql.reviewThread.comments[0].replyTo",
                    )
                    if reply_to is not None
                    else root_comment
                )
                database_id = _integer(
                    identity_comment.get("databaseId"),
                    "graphql.reviewThread.rootComment.databaseId",
                )
                retained = comments_by_id.get(f"github-review-comment-{database_id}")
                if retained is None:
                    omitted_roots += 1
                    continue
                if retained["review_observation_id"] not in review_observation_ids:
                    omitted_reviews += 1
                    continue
                normalized.append(
                    {
                        "id": f"github-review-thread-{thread_id}",
                        "review_observation_id": retained["review_observation_id"],
                        "reviewer_id": retained["reviewer_id"],
                        "observed_at": retained["observed_at"],
                        "head_commit": retained["head_commit"],
                        "body": retained["body"],
                        "body_truncated": retained["body_truncated"],
                        "source_url": (
                            _optional_text(identity_comment.get("url"))
                            or retained["source_url"]
                        ),
                        "state": "resolved" if resolved else "unresolved",
                        "outdated": outdated,
                    }
                )
        except ProviderReadError as exc:
            return items, {
                "status": _error_status(exc, pages),
                "pages": pages,
                "count": len(items),
                "error": str(exc),
            }

        if len(items) + len(normalized) > _MAX_ITEMS:
            remaining = max(0, _MAX_ITEMS - len(items))
            items.extend(normalized[:remaining])
            return items, {
                "status": "PARTIAL",
                "pages": pages + 1,
                "count": len(items),
                "limit": "item_limit",
            }
        items.extend(normalized)
        pages += 1

        if has_next:
            if not isinstance(end_cursor, str) or not end_cursor:
                return items, {
                    "status": "PARTIAL",
                    "pages": pages,
                    "count": len(items),
                    "reason": "missing_graphql_cursor",
                }
            cursor = end_cursor
            continue
        break

    if omitted_reviews:
        return items, {
            "status": "PARTIAL",
            "pages": pages,
            "count": len(items),
            "omitted": omitted_reviews + omitted_roots,
            "unmapped_reviews": omitted_reviews,
            "unmapped_roots": omitted_roots,
            "reason": "unmapped_thread_review_observation",
        }
    if omitted_roots:
        return items, {
            "status": "PARTIAL",
            "pages": pages,
            "count": len(items),
            "omitted": omitted_roots,
            "reason": "unmapped_thread_root_comment",
        }
    return items, {"status": "COMPLETE", "pages": pages, "count": len(items)}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProviderReadError(f"{label} must be an object")
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ProviderReadError(f"{label} must be a positive integer")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProviderReadError(f"{label} must be a non-empty string")
    return value


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _timestamp(value: Any, label: str) -> str:
    rendered = _text(value, label)
    try:
        parse_rfc3339(rendered)
    except ValueError as exc:
        raise ProviderReadError(f"{label} must be a valid RFC3339 timestamp") from exc
    return rendered


def _optional_timestamp(value: Any, label: str) -> str | None:
    return None if value is None else _timestamp(value, label)


def _sha(value: Any, label: str) -> str:
    rendered = _text(value, label)
    if _SHA40.fullmatch(rendered) is None:
        raise ProviderReadError(f"{label} must be an exact Git commit")
    return rendered


def _optional_sha(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _sha(value, label)


def _login(value: Any, label: str) -> str:
    user = _mapping(value, label)
    return _text(user.get("login"), f"{label}.login")


def _reviewer_id(value: Any, label: str, review_id: int) -> str:
    if value is None:
        return f"github-unavailable-reviewer:{review_id}"
    return _login(value, label)


def _comment_author(value: Any) -> str:
    if value is None:
        return "UNAVAILABLE"
    if not isinstance(value, dict):
        return "UNAVAILABLE"
    login = value.get("login")
    return login if isinstance(login, str) and login else "UNAVAILABLE"


def _bounded_body(value: Any) -> tuple[str, bool]:
    if not isinstance(value, str):
        return "", False
    raw = value.encode("utf-8")
    if len(raw) <= _MAX_BODY_BYTES:
        return value, False
    bounded = raw[:_MAX_BODY_BYTES].decode("utf-8", errors="ignore")
    return bounded, True


def _normalize_issue_comment(value: Any) -> dict[str, Any]:
    item = _mapping(value, "issue comment")
    body, truncated = _bounded_body(item.get("body"))
    return {
        "id": _integer(item.get("id"), "issue_comment.id"),
        "author": _comment_author(item.get("user")),
        "created_at": _timestamp(item.get("created_at"), "issue_comment.created_at"),
        "updated_at": _timestamp(item.get("updated_at"), "issue_comment.updated_at"),
        "body": body,
        "body_truncated": truncated,
    }


def _normalize_review(value: Any) -> dict[str, Any] | None:
    item = _mapping(value, "review")
    review_id = _integer(item.get("id"), "review.id")
    state = _text(item.get("state"), "review.state")
    submitted_at = _optional_timestamp(item.get("submitted_at"), "review.submitted_at")
    if state.upper() == "PENDING" and submitted_at is None:
        return None
    if submitted_at is None:
        raise ProviderReadError("submitted GitHub review has no submitted_at")
    return {
        "observation_id": f"github-review-{review_id}",
        "reviewer_id": _reviewer_id(item.get("user"), "review.user", review_id),
        "recommendation_state": state,
        "observed_at": submitted_at,
        "head_commit": _optional_sha(item.get("commit_id"), "review.commit_id"),
        "source_url": _optional_text(item.get("html_url")),
    }


def _mark_effective_reviews(
    reviews: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    marked = [dict(item) for item in reviews]
    opinionated: dict[str, list[tuple[Any, int, str]]] = {}
    unavailable_opinionated_reviews = 0
    for index, review in enumerate(marked):
        reviewer_id = _text(review.get("reviewer_id"), "review.reviewer_id")
        state = _text(
            review.get("recommendation_state"),
            "review.recommendation_state",
        ).upper()
        if state == "DISMISSED":
            review["effective"] = False
            continue
        if reviewer_id.startswith("github-unavailable-reviewer:") and state in {
            "APPROVED",
            "CHANGES_REQUESTED",
        }:
            review["effective"] = False
            unavailable_opinionated_reviews += 1
            continue
        if state in {"APPROVED", "CHANGES_REQUESTED"}:
            observed = parse_rfc3339(
                _timestamp(review.get("observed_at"), "review.observed_at")
            )
            opinionated.setdefault(reviewer_id, []).append((observed, index, state))
            review["effective"] = False
            continue
        review["effective"] = True

    ambiguities = 0
    for rows in opinionated.values():
        latest_cut = max(item[0] for item in rows)
        latest = [item for item in rows if item[0] == latest_cut]
        if len({item[2] for item in latest}) != 1:
            ambiguities += 1
            continue
        for _, index, _ in latest:
            marked[index]["effective"] = True
    return marked, ambiguities, unavailable_opinionated_reviews


def _normalize_review_comment(value: Any) -> dict[str, Any]:
    item = _mapping(value, "review comment")
    comment_id = _integer(item.get("id"), "review_comment.id")
    review_id = _integer(
        item.get("pull_request_review_id"),
        "review_comment.pull_request_review_id",
    )
    _timestamp(item.get("created_at"), "review_comment.created_at")
    body, truncated = _bounded_body(item.get("body"))
    return {
        "id": f"github-review-comment-{comment_id}",
        "review_observation_id": f"github-review-{review_id}",
        "reviewer_id": _reviewer_id(
            item.get("user"),
            "review_comment.user",
            review_id,
        ),
        "observed_at": _timestamp(item.get("updated_at"), "review_comment.updated_at"),
        "head_commit": _optional_sha(
            item.get("commit_id"),
            "review_comment.commit_id",
        ),
        "body": body,
        "body_truncated": truncated,
        "source_url": _optional_text(item.get("html_url")),
    }


def _normalize_check(
    value: Any,
    *,
    fallback_observed_at: str | None = None,
) -> dict[str, Any]:
    item = _mapping(value, "check run")
    check_id = _integer(item.get("id"), "check_run.id")
    name = _text(item.get("name"), "check_run.name")
    app = _mapping(item.get("app"), "check_run.app")
    app_id = _integer(app.get("id"), "check_run.app.id")
    started_at = _optional_timestamp(item.get("started_at"), "check_run.started_at")
    completed_at = _optional_timestamp(
        item.get("completed_at"), "check_run.completed_at"
    )
    observed_at = completed_at or started_at
    if observed_at is None:
        if fallback_observed_at is None:
            raise ProviderReadError("check run has no observation timestamp")
        observed_at = _timestamp(
            fallback_observed_at,
            "check_run.collection_observed_at",
        )
    return {
        "id": f"github-check-{check_id}",
        "key": f"github-check-run:{app_id}:{name}",
        "name": name,
        "head_commit": _sha(item.get("head_sha"), "check_run.head_sha"),
        "observed_at": observed_at,
        "status": _text(item.get("status"), "check_run.status"),
        "conclusion": _optional_text(item.get("conclusion")),
        "source_url": _optional_text(item.get("details_url")),
    }


def _normalize_commit_status(
    value: Any,
    *,
    head_commit: str,
) -> dict[str, Any]:
    item = _mapping(value, "commit status")
    status_id = _integer(item.get("id"), "commit_status.id")
    context = _text(item.get("context"), "commit_status.context")
    state = _text(item.get("state"), "commit_status.state").lower()
    if state not in {"pending", "success", "failure", "error"}:
        raise ProviderReadError("commit_status.state is unsupported")
    observed_at = _timestamp(
        item.get("updated_at") or item.get("created_at"),
        "commit_status.updated_at",
    )
    return {
        "id": f"github-status-{status_id}",
        "key": f"github-commit-status:{context}",
        "name": context,
        "head_commit": _sha(head_commit, "commit_status.head_commit"),
        "observed_at": observed_at,
        "status": "queued" if state == "pending" else "completed",
        "conclusion": None if state == "pending" else state,
        "source_url": _optional_text(item.get("target_url")),
    }


def _combined_check_coverage(
    check_runs: dict[str, Any],
    commit_statuses: dict[str, Any],
    *,
    count: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": _combined_coverage_status(check_runs, commit_statuses),
        "pages": int(check_runs.get("pages", 0)) + int(commit_statuses.get("pages", 0)),
        "count": count,
        "check_runs_status": check_runs.get("status"),
        "commit_statuses_status": commit_statuses.get("status"),
    }
    for label, coverage in (
        ("check_runs", check_runs),
        ("commit_statuses", commit_statuses),
    ):
        if coverage.get("status") != "COMPLETE":
            result[f"{label}_reason"] = coverage.get(
                "reason",
                coverage.get("error", "provider_check_source_incomplete"),
            )
    return result


def _normalize_pull(value: Any) -> dict[str, Any]:
    item = _mapping(value, "pull request")
    head = _mapping(item.get("head"), "pull.head")
    base = _mapping(item.get("base"), "pull.base")
    return {
        "number": _integer(item.get("number"), "pull.number"),
        "state": _text(item.get("state"), "pull.state"),
        "html_url": _text(item.get("html_url"), "pull.html_url"),
        "title": _optional_text(item.get("title")),
        "body": _optional_text(item.get("body")),
        "head_sha": _sha(head.get("sha"), "pull.head.sha"),
        "base_sha": _sha(base.get("sha"), "pull.base.sha"),
    }


def _collect_snapshot_once(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    observed_at: str | None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ProviderReadError("repository must be owner/name")
    collection_cut = observed_at or _now()
    try:
        parse_rfc3339(collection_cut)
    except ValueError as exc:
        raise ProviderReadError(
            "collection observation cut must be a valid RFC3339 timestamp"
        ) from exc
    root = f"{_API_ROOT}/repos/{repository}"
    pull_payload, _ = client.get(f"{root}/pulls/{pull_number}")
    pull = _normalize_pull(pull_payload)
    if pull["number"] != pull_number:
        raise ProviderReadError("Pull Request identity changed during collection")

    compare_payload, _ = client.get(
        f"{root}/compare/{pull['base_sha']}...{pull['head_sha']}"
    )
    compare = _mapping(compare_payload, "compare")
    merge_base = _mapping(compare.get("merge_base_commit"), "compare.merge_base")
    merge_base_sha = _sha(merge_base.get("sha"), "compare.merge_base.sha")

    issue_comments, issue_coverage = _collect_pages(
        client,
        f"{root}/issues/{pull_number}/comments?per_page=100",
        normalize=_normalize_issue_comment,
    )
    reviews, review_coverage = _collect_pages(
        client,
        f"{root}/pulls/{pull_number}/reviews?per_page=100",
        normalize=_normalize_review,
    )
    (
        reviews,
        opinion_ambiguities,
        unavailable_opinionated_reviews,
    ) = _mark_effective_reviews(reviews)
    if opinion_ambiguities or unavailable_opinionated_reviews:
        review_coverage = dict(review_coverage)
        if opinion_ambiguities:
            review_coverage["effective_opinion_ambiguities"] = opinion_ambiguities
        if unavailable_opinionated_reviews:
            review_coverage["unavailable_opinionated_reviews"] = (
                unavailable_opinionated_reviews
            )
        if review_coverage.get("status") == "COMPLETE":
            review_coverage["status"] = "PARTIAL"
            review_coverage["reason"] = (
                "unavailable_reviewer_identity"
                if unavailable_opinionated_reviews
                else "ambiguous_latest_reviewer_opinion"
            )
    review_comments, review_comment_coverage = _collect_pages(
        client,
        f"{root}/pulls/{pull_number}/comments?per_page=100",
        normalize=_normalize_review_comment,
    )
    review_threads, review_thread_coverage = _collect_review_threads(
        client,
        repository=repository,
        pull_number=pull_number,
        review_comments=review_comments,
        review_observation_ids={
            item["observation_id"]
            for item in reviews
            if isinstance(item.get("observation_id"), str)
        },
    )
    metadata_status = review_comment_coverage.get("status")
    combined_status = _combined_coverage_status(
        review_comment_coverage,
        review_thread_coverage,
    )
    if combined_status != review_thread_coverage.get("status"):
        review_thread_coverage = dict(review_thread_coverage)
        review_thread_coverage["status"] = combined_status
    if metadata_status != "COMPLETE":
        review_thread_coverage["metadata_status"] = metadata_status
        review_thread_coverage["metadata_pages"] = review_comment_coverage.get("pages")
        review_thread_coverage["metadata_count"] = review_comment_coverage.get("count")
        review_thread_coverage["metadata_reason"] = review_comment_coverage.get(
            "reason",
            review_comment_coverage.get("error", "review_comment_metadata_incomplete"),
        )
    check_runs, check_run_coverage = _collect_pages(
        client,
        f"{root}/commits/{pull['head_sha']}/check-runs?per_page=100",
        page_items=_check_page,
        normalize=lambda item: _normalize_check(
            item,
            fallback_observed_at=collection_cut,
        ),
    )
    commit_statuses, commit_status_coverage = _collect_pages(
        client,
        f"{root}/commits/{pull['head_sha']}/statuses?per_page=100",
        normalize=lambda item: _normalize_commit_status(
            item,
            head_commit=pull["head_sha"],
        ),
    )
    checks = [*check_runs, *commit_statuses]
    check_coverage = _combined_check_coverage(
        check_run_coverage,
        commit_status_coverage,
        count=len(checks),
    )

    cut_candidates = [collection_cut]
    cut_candidates.extend(
        item["updated_at"]
        for item in issue_comments
        if isinstance(item.get("updated_at"), str)
    )
    cut_candidates.extend(
        item["observed_at"]
        for item in reviews
        if isinstance(item.get("observed_at"), str)
    )
    cut_candidates.extend(
        item["observed_at"]
        for item in review_threads
        if isinstance(item.get("observed_at"), str)
    )
    cut_candidates.extend(
        item["observed_at"]
        for item in checks
        if isinstance(item.get("observed_at"), str)
    )
    effective_observed_at = max(cut_candidates, key=parse_rfc3339)

    return {
        "schema_version": PROVIDER_STATE_SCHEMA_VERSION,
        "provider": {
            "id": "github",
            "adapter": "gnostoa.github-rest-graphql-current-state/v1",
        },
        "observed_at": effective_observed_at,
        "subject": {
            "repository": f"https://github.com/{repository}",
            "change_request": {
                "kind": "github-pull-request",
                "id": str(pull_number),
            },
            "state": pull["state"],
            "head_commit": pull["head_sha"],
            "base_commit": pull["base_sha"],
            "comparison": {
                "kind": "merge_base",
                "commit_sha": merge_base_sha,
            },
            "source_url": pull["html_url"],
            "title": pull["title"],
        },
        "coverage": {
            "subject": {"status": "COMPLETE", "pages": 1, "count": 1},
            "conversation": issue_coverage,
            "reviews": review_coverage,
            "review_threads": review_thread_coverage,
            "checks": check_coverage,
        },
        "conversation": issue_comments,
        "reviews": reviews,
        "review_threads": review_threads,
        "checks": checks,
    }


def collect_snapshot(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    observed_at: str | None,
) -> dict[str, Any]:
    """Confirm a cut that is covered by a subsequent full provider reread."""
    previous: dict[str, Any] | None = None
    previous_cut: str | None = None
    snapshot: dict[str, Any] = {}
    for attempt in range(1, _MAX_COLLECTION_PASSES + 1):
        read_started_at = _now()
        snapshot = _collect_snapshot_once(
            client,
            repository=repository,
            pull_number=pull_number,
            observed_at=observed_at,
        )
        read_completed_at = _now()
        if parse_rfc3339(read_completed_at) < parse_rfc3339(read_started_at):
            previous = snapshot
            previous_cut = None
            observed_at = snapshot["observed_at"]
            continue
        if (
            previous is not None
            and previous_cut is not None
            and snapshot == previous
            and parse_rfc3339(read_started_at) >= parse_rfc3339(previous_cut)
        ):
            snapshot["observed_at"] = previous_cut
            snapshot["collection"] = {
                "status": "STABLE_READBACK",
                "passes": attempt,
                "certified_cut": previous_cut,
                "confirming_read_started_at": read_started_at,
                "confirming_read_completed_at": read_completed_at,
            }
            return snapshot
        raw_cut = snapshot["observed_at"]
        previous_cut = (
            raw_cut
            if parse_rfc3339(raw_cut) > parse_rfc3339(read_completed_at)
            else read_completed_at
        )
        previous = snapshot
        observed_at = raw_cut

    for coverage in snapshot["coverage"].values():
        if coverage["status"] == "COMPLETE":
            coverage["status"] = "PARTIAL"
            coverage["reason"] = "unstable_observation_cut"
    snapshot["collection"] = {
        "status": "UNSTABLE_READBACK",
        "passes": _MAX_COLLECTION_PASSES,
    }
    return snapshot


def _projection_key(projection: dict[str, Any]) -> tuple[Any, int, int]:
    observation = projection.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("projection observation is unavailable")
    observed_at = observation.get("observed_at")
    execution_id = observation.get("execution_id")
    if not isinstance(observed_at, str):
        raise ValueError("projection observed_at is unavailable")
    if not isinstance(execution_id, str):
        raise ValueError("projection execution identity is unavailable")
    match = _GITHUB_EXECUTION_ID.fullmatch(execution_id)
    if match is None:
        raise ValueError("projection execution identity is not GitHub-orderable")
    run_id = int(match.group(1))
    run_attempt = int(match.group(2))
    return parse_rfc3339(observed_at), run_id, run_attempt


def _parse_canonical_projection_body(body: object) -> dict[str, Any] | None:
    projection = parse_projection_comment(body)
    if projection is None:
        return None
    if not isinstance(body, str) or render_projection(projection) != body:
        raise ProviderWriteError("publication payload is not a canonical L1 projection")
    return projection


def publication_decision(
    *,
    repository: str,
    pull_number: int,
    current_pr: dict[str, Any],
    collected_head: str,
    existing_projection: dict[str, Any] | None,
    candidate_projection: dict[str, Any],
) -> tuple[bool, str]:
    if current_pr.get("state") != "open":
        return False, "PULL_NOT_OPEN"
    current_head = current_pr.get("head_sha")
    if current_head != collected_head:
        return False, "STALE_HEAD"
    candidate_subject = candidate_projection.get("subject")
    expected_repository = f"https://github.com/{repository}"
    expected_change_request = {
        "kind": "github-pull-request",
        "id": str(pull_number),
    }
    if (
        not isinstance(candidate_subject, dict)
        or candidate_subject.get("provider_id") != "github"
        or candidate_subject.get("repository") != expected_repository
        or candidate_subject.get("change_request") != expected_change_request
        or candidate_subject.get("head_commit") != collected_head
        or not isinstance(candidate_subject.get("base_commit"), str)
        or not isinstance(candidate_subject.get("merge_base_commit"), str)
    ):
        return False, "CANDIDATE_SUBJECT_MISMATCH"
    if candidate_subject.get("state") != current_pr.get("state"):
        return False, "STALE_LIFECYCLE"
    if (
        current_pr.get("base_sha") != candidate_subject["base_commit"]
        or current_pr.get("merge_base_sha") != candidate_subject["merge_base_commit"]
    ):
        return False, "STALE_COMPARISON"
    if existing_projection is not None:
        existing_subject = existing_projection.get("subject")
        if (
            isinstance(existing_subject, dict)
            and existing_subject.get("head_commit") == collected_head
            and _projection_key(existing_projection)
            >= _projection_key(candidate_projection)
        ):
            return False, "SUPERSEDED_PROJECTION"
    return True, "PUBLISH"


def _existing_projection(
    comments: list[dict[str, Any]],
    *,
    repository: str,
    pull_number: int,
) -> tuple[int, dict[str, Any]] | None:
    expected_repository = f"https://github.com/{repository}"
    expected_change = {
        "kind": "github-pull-request",
        "id": str(pull_number),
    }
    candidates: list[tuple[tuple[Any, int, int], int, dict[str, Any]]] = []
    for comment in comments:
        if comment.get("author") != _PROJECTION_AUTHOR:
            continue
        comment_id = comment.get("id")
        # Retained workflow-owned comments are identified by their validated
        # embedded semantics. Their visible Markdown is a disposable rendering
        # that may have been produced by an older same-schema renderer.
        projection = parse_projection_comment(
            comment.get("body"),
            allow_legacy_check_bounds=True,
        )
        if type(comment_id) is not int or projection is None:
            continue
        subject = projection.get("subject")
        if not isinstance(subject, dict):
            continue
        if subject.get("provider_id") != "github":
            continue
        if subject.get("repository") != expected_repository:
            continue
        if subject.get("change_request") != expected_change:
            continue
        try:
            key = _projection_key(projection)
        except ValueError as exc:
            raise ProviderWriteError(
                "workflow-owned projection execution identity is not GitHub-orderable"
            ) from exc
        candidates.append((key, comment_id, projection))
    if not candidates:
        return None
    if len(candidates) > 1:
        raise ProviderWriteError(
            "multiple valid owned L1 projection comments exist; refusing ambiguous write"
        )
    _, comment_id, projection = candidates[0]
    return comment_id, projection


def _protected_positive_projection_freshness_seconds(
    document: object,
) -> int | None:
    if not isinstance(document, dict):
        raise ProviderWriteError("protected authority document is malformed")
    policy = document.get("policy")
    if not isinstance(policy, dict):
        raise ProviderWriteError("protected review policy is unavailable")

    bounds: list[int] = []
    for section_name in ("subject", "collection"):
        section = policy.get(section_name)
        if not isinstance(section, dict):
            raise ProviderWriteError(
                f"protected review policy {section_name} section is unavailable"
            )
        freshness = section.get("freshness")
        if not isinstance(freshness, dict):
            raise ProviderWriteError(
                f"protected review policy {section_name} freshness is unavailable"
            )
        mode = freshness.get("mode")
        if mode == "not_age_sensitive":
            continue
        if mode != "max_age":
            raise ProviderWriteError(
                f"protected review policy {section_name} freshness is unsupported"
            )
        seconds = freshness.get("seconds")
        if type(seconds) is not int or seconds < 0:
            raise ProviderWriteError(
                f"protected review policy {section_name} freshness bound is invalid"
            )
        bounds.append(seconds)
    return min(bounds) if bounds else None


def _positive_projection_is_fresh(
    projection: dict[str, Any],
    *,
    protected_bundle: object,
    observed_now: str,
) -> bool:
    if projection.get("next_permitted_action") != "CONTINUE_EXISTING_WORKFLOW":
        return True
    if not hasattr(protected_bundle, "document"):
        raise ProviderWriteError("protected authority document is unavailable")
    observation = projection.get("observation")
    if not isinstance(observation, dict):
        raise ProviderWriteError("projection observation is unavailable")
    observed_at = observation.get("observed_at")
    if not isinstance(observed_at, str):
        raise ProviderWriteError("projection observation cut is unavailable")
    try:
        cut = parse_rfc3339(observed_at)
        now = parse_rfc3339(observed_now)
    except ValueError as exc:
        raise ProviderWriteError("projection publication time is invalid") from exc

    max_age = _protected_positive_projection_freshness_seconds(
        protected_bundle.document
    )
    return max_age is None or now.is_within_seconds_after(cut, max_age)


def _current_pr(
    client: JsonReader, repository: str, pull_number: int
) -> dict[str, Any]:
    root = f"{_API_ROOT}/repos/{repository}"
    payload, _ = client.get(f"{root}/pulls/{pull_number}")
    pull = _normalize_pull(payload)
    if pull["number"] != pull_number:
        raise ProviderReadError("Pull Request identity changed during publication")
    compare_payload, _ = client.get(
        f"{root}/compare/{pull['base_sha']}...{pull['head_sha']}"
    )
    compare = _mapping(compare_payload, "compare")
    merge_base = _mapping(compare.get("merge_base_commit"), "compare.merge_base")
    merge_base_sha = _sha(merge_base.get("sha"), "compare.merge_base.sha")
    return {
        "state": pull["state"],
        "head_sha": pull["head_sha"],
        "base_sha": pull["base_sha"],
        "merge_base_sha": merge_base_sha,
    }


def publish_entry(
    client: GitHubRestClient,
    *,
    repository: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    pull_number = _integer(entry.get("pull_number"), "entry.pull_number")
    if entry.get("collection_status") == "UNAVAILABLE":
        raw_reason = entry.get("reason")
        reason = (
            raw_reason
            if isinstance(raw_reason, str) and raw_reason
            else "PROVIDER_SUBJECT_UNAVAILABLE"
        )
        return {
            "pull_number": pull_number,
            "published": False,
            "reason": reason,
        }
    collected_head = _sha(entry.get("head_sha"), "entry.head_sha")
    body = _text(entry.get("body"), "entry.body")
    candidate_projection = _parse_canonical_projection_body(body)
    if candidate_projection is None:
        raise ProviderWriteError("publication payload has no valid L1 projection")
    try:
        _projection_key(candidate_projection)
    except ValueError as exc:
        raise ProviderWriteError(
            "publication candidate execution identity is not GitHub-orderable"
        ) from exc

    initial_current = _current_pr(client, repository, pull_number)
    allowed, reason = publication_decision(
        repository=repository,
        pull_number=pull_number,
        current_pr=initial_current,
        collected_head=collected_head,
        existing_projection=None,
        candidate_projection=candidate_projection,
    )
    if not allowed:
        return {"pull_number": pull_number, "published": False, "reason": reason}

    comments, coverage = _collect_pages(
        client,
        f"{_API_ROOT}/repos/{repository}/issues/{pull_number}/comments?per_page=100",
        normalize=_normalize_issue_comment,
    )
    if coverage["status"] != "COMPLETE":
        raise ProviderWriteError(
            "cannot publish without complete current projection-comment read-back"
        )
    existing = _existing_projection(
        comments,
        repository=repository,
        pull_number=pull_number,
    )
    final_current = _current_pr(client, repository, pull_number)
    allowed, reason = publication_decision(
        repository=repository,
        pull_number=pull_number,
        current_pr=final_current,
        collected_head=collected_head,
        existing_projection=existing[1] if existing else None,
        candidate_projection=candidate_projection,
    )
    if not allowed:
        return {"pull_number": pull_number, "published": False, "reason": reason}

    protected = candidate_projection.get("protected")
    if isinstance(protected, dict) and protected.get("status") == "AVAILABLE":
        candidate_protected_revision = protected.get("main_revision")
        bundle, consumer = _protected_state()
        if (
            not isinstance(candidate_protected_revision, str)
            or bundle.protected_main_revision != candidate_protected_revision
            or consumer.protected_main_revision != candidate_protected_revision
        ):
            return {
                "pull_number": pull_number,
                "published": False,
                "reason": "STALE_PROTECTED_AUTHORITY",
            }
        if not _positive_projection_is_fresh(
            candidate_projection,
            protected_bundle=bundle,
            observed_now=_now(),
        ):
            return {
                "pull_number": pull_number,
                "published": False,
                "reason": "STALE_PROVIDER_OBSERVATION",
            }

    if existing is None:
        client.post(
            f"{_API_ROOT}/repos/{repository}/issues/{pull_number}/comments",
            {"body": body},
        )
        action = "CREATED"
    else:
        client.patch(
            f"{_API_ROOT}/repos/{repository}/issues/comments/{existing[0]}",
            {"body": body},
        )
        action = "UPDATED"
    return {"pull_number": pull_number, "published": True, "reason": action}


def _workflow_run_pull_numbers(raw: str) -> list[int]:
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderReadError("workflow_run.pull_requests is invalid JSON") from exc
    if loaded is None:
        return []
    if not isinstance(loaded, list):
        raise ProviderReadError("workflow_run.pull_requests must be an array")

    numbers: list[int] = []
    for item in loaded:
        if not isinstance(item, dict):
            raise ProviderReadError("workflow_run.pull_requests items must be objects")
        number = item.get("number")
        if type(number) is not int or number <= 0:
            raise ProviderReadError(
                "workflow_run.pull_requests contains an invalid Pull Request number"
            )
        if number not in numbers:
            numbers.append(number)
    return numbers


def _open_pull_numbers(
    client: JsonReader,
    repository: str,
) -> list[int]:
    root = f"{_API_ROOT}/repos/{repository}"
    pulls, coverage = _collect_pages(
        client,
        f"{root}/pulls?state=open&per_page=100",
        normalize=lambda item: {"number": _normalize_pull(item)["number"]},
    )
    if coverage["status"] != "COMPLETE":
        raise ProviderReadError("open Pull Request enumeration is incomplete")
    return sorted({item["number"] for item in pulls})


def _select_scheduled_pull_batch(
    pull_numbers: list[int],
    observed_at: str,
) -> list[int]:
    try:
        observed = parse_rfc3339(observed_at)
    except ValueError as exc:
        raise ProviderReadError(
            "scheduled reconciliation time must be valid RFC3339"
        ) from exc

    numbers = sorted(set(pull_numbers))
    if not numbers:
        return []
    if any(type(number) is not int or number <= 0 for number in numbers):
        raise ProviderReadError("scheduled Pull Request population is invalid")
    if len(numbers) <= _MAX_OPEN_PULLS:
        return numbers

    batch_count = (len(numbers) + _MAX_OPEN_PULLS - 1) // _MAX_OPEN_PULLS
    batch_index = (observed.timeline_seconds // 3_600) % batch_count
    start = batch_index * _MAX_OPEN_PULLS
    return numbers[start : start + _MAX_OPEN_PULLS]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _semantic_result(code: int, raw: bytes) -> dict[str, Any]:
    from tools import review_outer

    try:
        payload = review_outer._decode_outer_result(code, raw)
    except (RuntimeError, TypeError, ValueError):
        return {"reason": "INVALID_R2A_RESULT"}

    outcome = payload.get("outcome")
    if outcome in {"PASS", "BLOCKED", "INCOMPLETE", "CONFLICTING"}:
        return payload
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return {"reason": error["code"]}
    return {"reason": "INVALID_R2A_RESULT"}


def _protected_state() -> tuple[Any, Any]:
    from tools.review_protected import (
        acquire_gnostoa_current_advisory_bundle,
        acquire_gnostoa_current_advisory_consumer,
    )

    for _ in range(3):
        bundle = acquire_gnostoa_current_advisory_bundle()
        consumer = acquire_gnostoa_current_advisory_consumer()
        if bundle.protected_main_revision == consumer.protected_main_revision:
            return bundle, consumer
    raise ProviderReadError(
        "protected-main authority changed during bounded acquisition"
    )


def _collect_entry(
    client: GitHubRestClient,
    repository: str,
    pull_number: int,
    *,
    run_id: int,
    run_attempt: int,
) -> dict[str, Any]:
    from tools import review_outer
    from tools.review_reconcile import (
        build_projection,
        build_review_input,
    )

    try:
        snapshot = collect_snapshot(
            client,
            repository=repository,
            pull_number=pull_number,
            observed_at=None,
        )
    except ProviderReadError as exc:
        return {
            "pull_number": pull_number,
            "collection_status": "UNAVAILABLE",
            "reason": "PROVIDER_SUBJECT_UNAVAILABLE",
            "coverage": {
                "subject": {
                    "status": _error_status(exc, 0),
                    "pages": 0,
                    "count": 0,
                }
            },
        }
    protected_revision: str | None = None
    outer: dict[str, Any] | None = None
    try:
        bundle, consumer = _protected_state()
        protected_revision = bundle.protected_main_revision
        review_input = build_review_input(snapshot, bundle.document)
        code, raw = review_outer._run_prior_effective_current_advisory_with_acquisition(
            review_input,
            acquire_consumer=lambda: consumer,
        )
        semantic = _semantic_result(code, raw)
        acquired = consumer.document.get("acquired_consumer")
        if not isinstance(acquired, dict):
            raise ProviderReadError("protected outer-consumer authority is malformed")
        review_outer._require_transport_compatible_consumer(acquired)
        outer = acquired
    except (OSError, RuntimeError, ValueError) as exc:
        semantic = {"reason": type(exc).__name__}

    projection = build_projection(
        snapshot,
        protected_main_revision=protected_revision,
        outer_consumer=outer,
        r2a_result=semantic,
        execution={
            "execution_id": f"github-actions:{run_id}:{run_attempt}",
            "observed_at": _now(),
        },
    )
    return {
        "pull_number": pull_number,
        "head_sha": snapshot["subject"]["head_commit"],
        "body": render_projection(projection),
    }


def _write_payload(path: Path, entries: list[dict[str, Any]]) -> None:
    encoded = json.dumps(
        entries,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > _MAX_PUBLICATION_PAYLOAD_BYTES:
        raise ValueError("publication payload exceeds bounded size")
    path.write_bytes(encoded)


def _load_payload(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if len(raw) > _MAX_PUBLICATION_PAYLOAD_BYTES:
        raise ValueError("publication payload exceeds bounded size")
    loaded = json.loads(raw.decode("utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("publication payload must be an array")
    entries = [item for item in loaded if isinstance(item, dict)]
    if len(entries) != len(loaded):
        raise ValueError("publication payload entries must be objects")
    if len(entries) > _MAX_OPEN_PULLS:
        raise ValueError("publication payload exceeds Pull Request bound")
    return entries


def _summary(lines: list[str]) -> None:
    rendered = "\n".join(lines)
    print(rendered)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(rendered + "\n")


def _bounded_error_status(error: BaseException) -> int | None:
    status = getattr(error, "status", None)
    if type(status) is int and 100 <= status <= 599:
        return status
    return None


def _publication_result_summary(item: dict[str, Any]) -> str:
    suffix = ""
    error_type = item.get("error_type")
    if isinstance(error_type, str):
        suffix = f" ({error_type}"
        error_status = item.get("error_status")
        if type(error_status) is int:
            suffix += f"; HTTP {error_status}"
        suffix += ")"
    return f"- PR #{item['pull_number']}: {item['reason']}{suffix}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("collect", "publish"), required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-number", type=int, action="append", default=[])
    parser.add_argument("--workflow-run-pulls-json", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--run-id", type=int, default=0)
    parser.add_argument("--run-attempt", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    client = GitHubRestClient(token)

    if args.mode == "collect":
        if args.output is None:
            raise SystemExit("--output is required for collect")
        if args.run_id <= 0 or args.run_attempt <= 0:
            raise SystemExit("--run-id and --run-attempt must be positive for collect")
        pulls = list(
            dict.fromkeys(
                [
                    *args.pull_number,
                    *_workflow_run_pull_numbers(args.workflow_run_pulls_json),
                ]
            )
        )
        if not pulls:
            pulls = _select_scheduled_pull_batch(
                _open_pull_numbers(client, args.repository),
                _now(),
            )
        if len(pulls) > _MAX_OPEN_PULLS:
            raise SystemExit(
                "selected Pull Request population exceeds bounded reconciliation capacity"
            )
        entries = []
        for number in pulls:
            try:
                entry = _collect_entry(
                    client,
                    args.repository,
                    number,
                    run_id=args.run_id,
                    run_attempt=args.run_attempt,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                entry = {
                    "pull_number": number,
                    "collection_status": "UNAVAILABLE",
                    "reason": "RECONCILIATION_ENTRY_UNAVAILABLE",
                    "error_type": type(exc).__name__,
                }
            entries.append(entry)
        _write_payload(args.output, entries)
        _summary(
            [
                "## Gnostoa useful L1 collection",
                "",
                f"- Pull Requests attempted: {len(entries)}",
                *[
                    f"- PR #{item['pull_number']}: "
                    + (
                        f"UNAVAILABLE ({item.get('reason', 'UNKNOWN')}); no projection"
                        if item.get("collection_status") == "UNAVAILABLE"
                        else "projection collected; inspect its coverage and R2A state"
                    )
                    for item in entries
                ],
                "- Projection is non-canonical and binding remains false.",
            ]
        )
        return 0

    if args.payload is None:
        raise SystemExit("--payload is required for publish")
    entries = _load_payload(args.payload)
    results = []
    for entry in entries:
        try:
            result = publish_entry(
                client,
                repository=args.repository,
                entry=entry,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            pull_number = entry.get("pull_number")
            error_status = _bounded_error_status(exc)
            result = {
                "pull_number": (
                    pull_number
                    if type(pull_number) is int and pull_number > 0
                    else "UNKNOWN"
                ),
                "published": False,
                "reason": "PUBLICATION_ENTRY_UNAVAILABLE",
                "error_type": type(exc).__name__,
                **(
                    {"error_status": error_status}
                    if error_status is not None
                    else {}
                ),
            }
        results.append(result)
    _summary(
        [
            "## Gnostoa useful L1 publication",
            "",
            *[_publication_result_summary(item) for item in results],
        ]
    )
    return (
        1
        if any(
            item.get("reason") == "PUBLICATION_ENTRY_UNAVAILABLE"
            for item in results
        )
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
