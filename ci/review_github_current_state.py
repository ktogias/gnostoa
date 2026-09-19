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
from tools.review_reconcile import parse_projection_comment

_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_MAX_RESPONSE_BYTES = 4_194_304
_MAX_BODY_BYTES = 65_536
_MAX_PAGES = 20
_MAX_ITEMS = 5_000
_MAX_OPEN_PULLS = 10
_TIMEOUT_SECONDS = 30
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class ProviderReadError(RuntimeError):
    """A bounded GitHub provider read failed."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ProviderWriteError(RuntimeError):
    """A bounded GitHub provider write failed."""


class JsonReader(Protocol):
    def get(self, url: str) -> tuple[Any, dict[str, str]]: ...


def _validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ProviderReadError("GitHub API URL is outside the admitted host")
    return url


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

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
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
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": _API_VERSION,
                "User-Agent": "gnostoa-useful-l1",
                **({"Content-Type": "application/json"} if encoded is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(raw) > _MAX_RESPONSE_BYTES:
                    raise ProviderReadError("GitHub API response exceeds bounded size")
                headers = {key.lower(): value for key, value in response.headers.items()}
                return _decode_json(raw, "GitHub API"), headers
        except urllib.error.HTTPError as exc:
            detail = exc.read(4_096).decode("utf-8", errors="replace")
            message = f"GitHub API HTTP {exc.code}"
            if detail:
                message += f": {' '.join(detail.split())[:512]}"
            if method == "GET":
                raise ProviderReadError(message, status=exc.code) from exc
            raise ProviderWriteError(message) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if method == "GET":
                raise ProviderReadError("GitHub API transport failed") from exc
            raise ProviderWriteError("GitHub API transport failed") from exc

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        return self._request("GET", url)

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        document, _ = self._request("POST", url, payload)
        return document

    def patch(self, url: str, payload: dict[str, Any]) -> Any:
        document, _ = self._request("PATCH", url, payload)
        return document


def _next_url(headers: dict[str, str]) -> str | None:
    link = headers.get("link")
    if not link:
        return None
    match = _NEXT_LINK.search(link)
    if match is None:
        return None
    return _validate_api_url(match.group(1))


def _error_status(error: ProviderReadError, pages: int) -> str:
    if error.status in {403, 429}:
        return "RATE_LIMITED"
    return "PARTIAL" if pages else "ERROR"


def _list_page(payload: Any) -> list[Any]:
    if not isinstance(payload, list):
        raise ProviderReadError("GitHub paginated source did not return an array")
    return payload


def _check_page(payload: Any) -> list[Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("check_runs"), list):
        raise ProviderReadError("GitHub check-runs source has invalid shape")
    return payload["check_runs"]


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
            normalized = [normalize(item) for item in raw_items]
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


def _sha(value: Any, label: str) -> str:
    rendered = _text(value, label)
    if _SHA40.fullmatch(rendered) is None:
        raise ProviderReadError(f"{label} must be an exact Git commit")
    return rendered


def _login(value: Any, label: str) -> str:
    user = _mapping(value, label)
    return _text(user.get("login"), f"{label}.login")


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
        "author": _login(item.get("user"), "issue_comment.user"),
        "created_at": _text(item.get("created_at"), "issue_comment.created_at"),
        "updated_at": _text(item.get("updated_at"), "issue_comment.updated_at"),
        "body": body,
        "body_truncated": truncated,
    }


def _normalize_review(value: Any) -> dict[str, Any]:
    item = _mapping(value, "review")
    return {
        "id": _integer(item.get("id"), "review.id"),
        "author": _login(item.get("user"), "review.user"),
        "state": _text(item.get("state"), "review.state"),
        "submitted_at": _text(item.get("submitted_at"), "review.submitted_at"),
        "commit_id": _optional_text(item.get("commit_id")),
        "html_url": _optional_text(item.get("html_url")),
    }


def _normalize_review_comment(value: Any) -> dict[str, Any]:
    item = _mapping(value, "review comment")
    body, truncated = _bounded_body(item.get("body"))
    return {
        "id": _integer(item.get("id"), "review_comment.id"),
        "pull_request_review_id": _integer(
            item.get("pull_request_review_id"),
            "review_comment.pull_request_review_id",
        ),
        "author": _login(item.get("user"), "review_comment.user"),
        "created_at": _text(item.get("created_at"), "review_comment.created_at"),
        "updated_at": _text(item.get("updated_at"), "review_comment.updated_at"),
        "commit_id": _optional_text(item.get("commit_id")),
        "body": body,
        "body_truncated": truncated,
        "html_url": _optional_text(item.get("html_url")),
    }


def _normalize_check(value: Any) -> dict[str, Any]:
    item = _mapping(value, "check run")
    return {
        "id": _integer(item.get("id"), "check_run.id"),
        "name": _text(item.get("name"), "check_run.name"),
        "head_sha": _sha(item.get("head_sha"), "check_run.head_sha"),
        "status": _text(item.get("status"), "check_run.status"),
        "conclusion": _optional_text(item.get("conclusion")),
        "details_url": _optional_text(item.get("details_url")),
    }


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


def collect_snapshot(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    observed_at: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ProviderReadError("repository must be owner/name")
    parse_rfc3339(observed_at)
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
    review_comments, review_comment_coverage = _collect_pages(
        client,
        f"{root}/pulls/{pull_number}/comments?per_page=100",
        normalize=_normalize_review_comment,
    )
    check_runs, check_coverage = _collect_pages(
        client,
        f"{root}/commits/{pull['head_sha']}/check-runs?per_page=100",
        page_items=_check_page,
        normalize=_normalize_check,
    )

    return {
        "schema_version": 1,
        "provider": "github",
        "repository": repository,
        "pull_number": pull_number,
        "observed_at": observed_at,
        "subject": {
            "state": pull["state"],
            "head_sha": pull["head_sha"],
            "base_sha": pull["base_sha"],
            "merge_base_sha": merge_base_sha,
            "html_url": pull["html_url"],
            "title": pull["title"],
        },
        "coverage": {
            "pull": {"status": "COMPLETE", "pages": 1, "count": 1},
            "issue_comments": issue_coverage,
            "reviews": review_coverage,
            "review_comments": review_comment_coverage,
            "check_runs": check_coverage,
        },
        "issue_comments": issue_comments,
        "reviews": reviews,
        "review_comments": review_comments,
        "check_runs": check_runs,
    }


def _projection_key(projection: dict[str, Any]) -> tuple[Any, int, int]:
    observation = projection.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("projection observation is unavailable")
    observed_at = observation.get("observed_at")
    run_id = observation.get("run_id")
    run_attempt = observation.get("run_attempt")
    if not isinstance(observed_at, str):
        raise ValueError("projection observed_at is unavailable")
    if type(run_id) is not int or type(run_attempt) is not int:
        raise ValueError("projection execution generation is unavailable")
    return parse_rfc3339(observed_at), run_id, run_attempt


def publication_decision(
    *,
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
    if (
        not isinstance(candidate_subject, dict)
        or candidate_subject.get("head_sha") != collected_head
    ):
        return False, "CANDIDATE_SUBJECT_MISMATCH"
    if existing_projection is not None:
        existing_subject = existing_projection.get("subject")
        if (
            isinstance(existing_subject, dict)
            and existing_subject.get("head_sha") == collected_head
            and _projection_key(existing_projection) >= _projection_key(
                candidate_projection
            )
        ):
            return False, "SUPERSEDED_PROJECTION"
    return True, "PUBLISH"


def _existing_projection(
    comments: list[dict[str, Any]],
) -> tuple[int, dict[str, Any]] | None:
    candidates: list[tuple[tuple[Any, int, int], int, dict[str, Any]]] = []
    for comment in comments:
        comment_id = comment.get("id")
        projection = parse_projection_comment(comment.get("body"))
        if type(comment_id) is not int or projection is None:
            continue
        try:
            key = _projection_key(projection)
        except ValueError:
            continue
        candidates.append((key, comment_id, projection))
    if not candidates:
        return None
    _, comment_id, projection = max(candidates, key=lambda item: (item[0], item[1]))
    return comment_id, projection


def _current_pr(client: JsonReader, repository: str, pull_number: int) -> dict[str, Any]:
    payload, _ = client.get(f"{_API_ROOT}/repos/{repository}/pulls/{pull_number}")
    pull = _normalize_pull(payload)
    return {"state": pull["state"], "head_sha": pull["head_sha"]}


def publish_entry(
    client: GitHubRestClient,
    *,
    repository: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    pull_number = _integer(entry.get("pull_number"), "entry.pull_number")
    collected_head = _sha(entry.get("head_sha"), "entry.head_sha")
    body = _text(entry.get("body"), "entry.body")
    candidate_projection = parse_projection_comment(body)
    if candidate_projection is None:
        raise ProviderWriteError("publication payload has no valid L1 projection")

    current = _current_pr(client, repository, pull_number)
    comments, coverage = _collect_pages(
        client,
        f"{_API_ROOT}/repos/{repository}/issues/{pull_number}/comments?per_page=100",
        normalize=_normalize_issue_comment,
    )
    if coverage["status"] != "COMPLETE":
        raise ProviderWriteError(
            "cannot publish without complete current projection-comment read-back"
        )
    existing = _existing_projection(comments)
    allowed, reason = publication_decision(
        current_pr=current,
        collected_head=collected_head,
        existing_projection=existing[1] if existing else None,
        candidate_projection=candidate_projection,
    )
    if not allowed:
        return {"pull_number": pull_number, "published": False, "reason": reason}

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
    return [item["number"] for item in pulls[:_MAX_OPEN_PULLS]]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _semantic_result(code: int, raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"reason": f"TOOL_ERROR_EXIT_{code}"}
    if not isinstance(payload, dict):
        return {"reason": f"TOOL_ERROR_EXIT_{code}"}
    if payload.get("outcome") in {"PASS", "BLOCKED", "INCOMPLETE", "CONFLICTING"}:
        return payload
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return {"reason": error["code"]}
    return {"reason": f"TOOL_ERROR_EXIT_{code}"}


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
    raise ProviderReadError("protected-main authority changed during bounded acquisition")


def _collect_entry(
    client: GitHubRestClient,
    repository: str,
    pull_number: int,
    *,
    run_id: int,
    run_attempt: int,
) -> dict[str, Any]:
    from tools.review_outer import run_prior_effective_current_advisory
    from tools.review_reconcile import (
        build_projection,
        build_review_input,
        render_projection,
    )

    observed_at = _now()
    snapshot = collect_snapshot(
        client,
        repository=repository,
        pull_number=pull_number,
        observed_at=observed_at,
    )
    bundle, consumer = _protected_state()
    review_input = build_review_input(snapshot, bundle.document)
    code, raw = run_prior_effective_current_advisory(review_input)
    semantic = _semantic_result(code, raw)
    outer = consumer.document.get("acquired_consumer")
    if not isinstance(outer, dict):
        raise ProviderReadError("protected outer-consumer authority is malformed")
    projection = build_projection(
        snapshot,
        protected_main_revision=bundle.protected_main_revision,
        outer_consumer=outer,
        r2a_result=semantic,
        execution={
            "run_id": run_id,
            "run_attempt": run_attempt,
            "observed_at": _now(),
        },
    )
    return {
        "pull_number": pull_number,
        "head_sha": snapshot["subject"]["head_sha"],
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
    path.write_bytes(encoded)


def _load_payload(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("publication payload must be an array")
    entries = [item for item in loaded if isinstance(item, dict)]
    if len(entries) != len(loaded):
        raise ValueError("publication payload entries must be objects")
    if len(entries) > _MAX_OPEN_PULLS:
        raise ValueError("publication payload exceeds Pull Request bound")
    return entries


def _summary(lines: list[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("collect", "publish"), required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-number", type=int, action="append", default=[])
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
        pulls = list(dict.fromkeys(args.pull_number))
        if not pulls:
            pulls = _open_pull_numbers(client, args.repository)
        entries = [
            _collect_entry(
                client,
                args.repository,
                number,
                run_id=args.run_id,
                run_attempt=args.run_attempt,
            )
            for number in pulls[:_MAX_OPEN_PULLS]
        ]
        _write_payload(args.output, entries)
        _summary(
            [
                "## Gnostoa useful L1 collection",
                "",
                f"- Pull Requests reconciled: {len(entries)}",
                "- Projection is non-canonical and binding remains false.",
            ]
        )
        return 0

    if args.payload is None:
        raise SystemExit("--payload is required for publish")
    entries = _load_payload(args.payload)
    results = [
        publish_entry(client, repository=args.repository, entry=entry)
        for entry in entries
    ]
    _summary(
        [
            "## Gnostoa useful L1 publication",
            "",
            *[
                f"- PR #{item['pull_number']}: {item['reason']}"
                for item in results
            ],
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
