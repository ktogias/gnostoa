from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from tools import analyzer_codacy, analyzer_deepsource, github_events, github_rest
from tools.analyzer_readback import (
    AnalyzerReadbackError,
    build_readback,
    canonical_json,
    coverage,
    normalize_repository,
)

BUNDLE_SCHEMA = "gnostoa-analyzer-readback-bundle/v1"
_API_ROOT = "https://api.github.com"
_API_VERSION = "2022-11-28"
_TIMEOUT_SECONDS = 30
_MAX_RESPONSE_BYTES = 4_194_304
_MAX_PAGES = 40
_MAX_ITEMS = 10_000
_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class RunnerError(RuntimeError):
    pass


class GitHubReader(Protocol):
    def get(self, url: str) -> tuple[Any, Mapping[str, str]]: ...


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runner_message(error: github_rest.GitHubError) -> str:
    """Return this runner's message for a shared-client failure, by its cause."""
    if isinstance(error, github_rest.ResponseTooLarge):
        return "GitHub API response exceeds bounded size"
    if isinstance(error, github_rest.MalformedAnswer):
        return "GitHub API returned invalid JSON"
    if isinstance(error, github_rest.OutsideOrigin):
        return "GitHub API URL is outside the admitted origin"
    if error.status is not None:
        return f"GitHub API HTTP {error.status}"
    if str(error) == "GitHub request failed validation":
        return str(error)
    return "GitHub API unavailable"


def _validate_github_url(url: str) -> str:
    """Return ``url`` if it stays on the API origin, or raise this runner's error."""
    try:
        return github_rest.validate_url(url)
    except github_rest.GitHubError as error:
        raise RunnerError(_runner_message(error)) from None


# The client is the shared one (`tools/github_rest.py`, Decision 0100), merged from this
# runner's and four others: same-origin redirects with the credential re-added there
# only, a bound on the whole exchange and the body, and a credential refused unless it
# is one printable token -- never echoed into an error.
class _GitHubRedirectHandler(github_rest.SameOriginRedirects):
    """Follow same-origin redirects only, failing as this runner's error."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Follow the redirect if it stays on the origin, carrying the credential."""
        try:
            return super().redirect_request(req, fp, code, msg, headers, newurl)
        except github_rest.GitHubError as error:
            raise RunnerError(_runner_message(error)) from None


class GitHubReadClient(github_rest.GitHubRestClient):
    """The shared client for this runner's reads, failing as this runner's error."""

    same_origin_redirects = _GitHubRedirectHandler

    def __init__(self, token: str) -> None:
        try:
            super().__init__(
                token,
                follow_same_origin_redirects=True,
                user_agent="gnostoa-analyzer-readback",
            )
        except github_rest.GitHubError:
            raise RunnerError(
                "GitHub read credential is malformed"
                if token
                else "GitHub read token is unavailable"
            ) from None

    @property
    def policy(self) -> github_rest.Policy:
        """Return this runner's bounds, read per call so the current ones apply."""
        return github_rest.Policy(
            timeout_seconds=_TIMEOUT_SECONDS,
            attempts=1,
            max_response_bytes=_MAX_RESPONSE_BYTES,
            workers=self._workers,
        )

    @classmethod
    def from_environment(cls, **_options: Any) -> GitHubReadClient:
        """Return a client for the job's token; this runner takes no other options."""
        return cls(os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", ""))

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        """Return one GET's document and headers, failing as this runner's error."""
        try:
            return super().get(url)
        except github_rest.GitHubError as error:
            raise RunnerError(_runner_message(error)) from error


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RunnerError(f"{label} is malformed")
    return value


def _exact_head(value: object, label: str) -> str:
    """The shared exact-SHA check, refused as this runner's error (Claude on
    #388)."""
    try:
        return github_events.exact_sha(value, label)
    except ValueError as exc:
        raise RunnerError(f"{label} must be an exact 40-character SHA") from exc


def _repository(value: str) -> tuple[str, str]:
    try:
        normalized = normalize_repository(value)
    except AnalyzerReadbackError as exc:
        raise RunnerError("repository must use safe owner/name segments") from exc
    parts = normalized.split("/")
    return parts[0], parts[1]


def _next_url(headers: Mapping[str, str]) -> str | None:
    link = headers.get("link")
    if not link:
        return None
    match = _NEXT_LINK.search(link)
    if match is None:
        return None
    return _validate_github_url(match.group(1))


def _collect_pages(
    client: GitHubReader,
    first_url: str,
    *,
    extract: Any,
) -> list[Mapping[str, Any]]:
    url: str | None = first_url
    items: list[Mapping[str, Any]] = []
    pages = 0
    while url is not None:
        if pages >= _MAX_PAGES:
            raise RunnerError("GitHub pagination exceeded bounded page count")
        payload, headers = client.get(url)
        raw_items = extract(payload)
        if not isinstance(raw_items, list):
            raise RunnerError("GitHub paginated payload is malformed")
        for item in raw_items:
            items.append(_mapping(item, "GitHub item"))
        if len(items) > _MAX_ITEMS:
            raise RunnerError("GitHub item population exceeds bounded capacity")
        pages += 1
        url = _next_url(headers)
    return items


def _list_payload(payload: object) -> list[Any]:
    if not isinstance(payload, list):
        raise RunnerError("GitHub list response is malformed")
    return payload


def _check_runs_payload(payload: object) -> list[Any]:
    document = _mapping(payload, "GitHub check-runs response")
    runs = document.get("check_runs")
    if not isinstance(runs, list):
        raise RunnerError("GitHub check-runs response is malformed")
    return runs


def _pull_head(client: GitHubReader, repository: str, pull_number: int) -> str:
    document, _ = client.get(f"{_API_ROOT}/repos/{repository}/pulls/{pull_number}")
    pull = _mapping(document, "GitHub Pull Request")
    head = _mapping(pull.get("head"), "GitHub Pull Request head")
    return _exact_head(head.get("sha"), "GitHub Pull Request head")


def _statuses(
    client: GitHubReader, repository: str, head: str
) -> list[Mapping[str, Any]]:
    return _collect_pages(
        client,
        f"{_API_ROOT}/repos/{repository}/commits/{head}/statuses?per_page=100",
        extract=_list_payload,
    )


def _check_runs(
    client: GitHubReader, repository: str, head: str
) -> list[Mapping[str, Any]]:
    return _collect_pages(
        client,
        f"{_API_ROOT}/repos/{repository}/commits/{head}/check-runs?per_page=100",
        extract=_check_runs_payload,
    )


def _review_comments(
    client: GitHubReader,
    repository: str,
    pull_number: int,
) -> list[Mapping[str, Any]]:
    return _collect_pages(
        client,
        f"{_API_ROOT}/repos/{repository}/pulls/{pull_number}/comments?per_page=50",
        extract=_list_payload,
    )


def _deepsource_status_projection(
    statuses: list[Mapping[str, Any]],
    checks: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    projected: list[Mapping[str, Any]] = []
    for item in statuses:
        creator = item.get("creator")
        creator_map = creator if isinstance(creator, Mapping) else {}
        projected.append(
            {
                "context": item.get("context"),
                "state": item.get("state"),
                "target_url": item.get("target_url"),
                "source_kind": "commit_status",
                "creator_login": creator_map.get("login"),
                "creator_type": creator_map.get("type"),
            }
        )
    for check in checks:
        name = check.get("name")
        details = check.get("details_url")
        if not isinstance(name, str) or not name.startswith("DeepSource:"):
            continue
        if not isinstance(details, str) or not details:
            continue
        conclusion = check.get("conclusion")
        status = check.get("status")
        state = conclusion if isinstance(conclusion, str) and conclusion else status
        app = check.get("app")
        app_map = app if isinstance(app, Mapping) else {}
        projected.append(
            {
                "context": name,
                "state": state or "pending",
                "target_url": details,
                "source_kind": "check_run",
                "app_slug": app_map.get("slug"),
            }
        )
    return projected


def _deepsource_comments(
    comments: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for comment in comments:
        result.append(
            {
                "body": comment.get("body"),
                "path": comment.get("path"),
                "line": comment.get("line") or comment.get("original_line"),
                "commit_id": comment.get("commit_id"),
                "original_commit_id": comment.get("original_commit_id"),
                "url": comment.get("html_url") or comment.get("url"),
                "author_login": (
                    comment.get("user", {}).get("login")
                    if isinstance(comment.get("user"), Mapping)
                    else None
                ),
                "author_type": (
                    comment.get("user", {}).get("type")
                    if isinstance(comment.get("user"), Mapping)
                    else None
                ),
            }
        )
    return result


def _unavailable_readback(
    *,
    provider: str,
    adapter: str,
    repository: str,
    pull_number: int,
    requested_head: str,
    analysis_id: str | None,
    scope: str,
    native_mode: str,
    completeness: str,
    observed_at: str,
    reason: str,
) -> dict[str, Any]:
    return build_readback(
        provider=provider,
        adapter=adapter,
        repository=repository,
        pull_number=pull_number,
        requested_head=requested_head,
        observed_head=None,
        analysis_id=analysis_id,
        scope=scope,
        completeness=completeness,
        native_mode=native_mode,
        observed_at=observed_at,
        run_state="UNKNOWN",
        coverage_record=coverage(
            "UNAVAILABLE",
            pages=0,
            count=0,
            reason=reason,
        ),
        findings=[],
    )


def collect_bundle(
    github: GitHubReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    deepsource: analyzer_deepsource.GraphQLReader | None,
    codacy: analyzer_codacy.JsonReader | None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    _repository(repository)
    requested = _exact_head(requested_head, "requested head")
    observed = observed_at or _now()
    initial_head = _pull_head(github, repository, pull_number)
    if initial_head != requested:
        return {
            "schema": BUNDLE_SCHEMA,
            "repository": repository,
            "pull_number": pull_number,
            "requested_head": requested,
            "observed_head": initial_head,
            "observed_at": observed,
            "subject_binding": "INCOMPLETE",
            "reason": "GITHUB_SUBJECT_MISMATCH",
            "readbacks": [],
        }

    statuses = _statuses(github, repository, requested)
    checks = _check_runs(github, repository, requested)
    comments = _review_comments(github, repository, pull_number)
    diff_local = analyzer_deepsource.diff_local_from_github(
        repository=repository,
        pull_number=pull_number,
        requested_head=requested,
        observed_head=initial_head,
        statuses=_deepsource_status_projection(statuses, checks),
        comments=_deepsource_comments(comments),
        observed_at=observed,
    )

    run_uid = diff_local.get("analysis_id")
    if deepsource is None:
        full = _unavailable_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested,
            analysis_id=run_uid if isinstance(run_uid, str) else None,
            scope="FULL",
            native_mode="FULL_RUN",
            completeness="AUTH_UNAVAILABLE",
            observed_at=observed,
            reason="AUTH_UNAVAILABLE",
        )
    elif not isinstance(run_uid, str):
        full = build_readback(
            provider="deepsource",
            adapter="deepsource-graphql/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested,
            observed_head=None,
            analysis_id=None,
            scope="FULL",
            completeness="AMBIGUOUS",
            native_mode="FULL_RUN",
            observed_at=observed,
            run_state="UNKNOWN",
            coverage_record=coverage(
                "INCOMPLETE",
                pages=0,
                count=0,
                reason="RUN_ASSOCIATION_AMBIGUOUS",
            ),
            findings=[],
        )
    else:
        full = analyzer_deepsource.read_full_run(
            deepsource,
            repository=repository,
            pull_number=pull_number,
            requested_head=requested,
            run_uid=run_uid,
            observed_at=observed,
        )

    if codacy is None:
        codacy_readback = _unavailable_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            native_mode="PULL_REQUEST",
            completeness="AUTH_UNAVAILABLE",
            observed_at=observed,
            reason="AUTH_UNAVAILABLE",
        )
    else:
        codacy_readback = analyzer_codacy.read_pull_request(
            codacy,
            repository=repository,
            pull_number=pull_number,
            requested_head=requested,
            observed_at=observed,
        )

    final_head = _pull_head(github, repository, pull_number)
    if final_head != requested:
        return {
            "schema": BUNDLE_SCHEMA,
            "repository": repository,
            "pull_number": pull_number,
            "requested_head": requested,
            "observed_head": final_head,
            "observed_at": observed,
            "subject_binding": "INCOMPLETE",
            "reason": "GITHUB_SUBJECT_CHANGED_DURING_READBACK",
            "readbacks": [],
        }

    return {
        "schema": BUNDLE_SCHEMA,
        "repository": repository,
        "pull_number": pull_number,
        "requested_head": requested,
        "observed_head": final_head,
        "observed_at": observed,
        "subject_binding": "BOUND",
        "github_projection": {
            "statuses": len(statuses),
            "check_runs": len(checks),
            "review_comments": len(comments),
        },
        "readbacks": [diff_local, full, codacy_readback],
    }


def _assert_secret_free(serialized: str, secrets: list[str]) -> None:
    for secret in secrets:
        if secret and secret in serialized:
            raise RunnerError("serialized analyzer readback contains credential bytes")


def _write_create_only(path: Path, serialized: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.write("\n")
    except FileExistsError as exc:
        raise RunnerError("output path already exists") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-number", type=int, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.pull_number <= 0:
        print("ERROR: pull number must be positive", file=sys.stderr)
        return 2
    try:
        github = GitHubReadClient.from_environment()
        try:
            deepsource: analyzer_deepsource.GraphQLReader | None = (
                analyzer_deepsource.DeepSourceGraphQLClient.from_environment()
            )
        except analyzer_deepsource.ProviderReadFailure:
            deepsource = None
        try:
            codacy: analyzer_codacy.JsonReader | None = (
                analyzer_codacy.CodacyRestClient.from_environment()
            )
        except analyzer_codacy.ProviderReadFailure:
            codacy = None
        bundle = collect_bundle(
            github,
            repository=args.repository,
            pull_number=args.pull_number,
            requested_head=args.head,
            deepsource=deepsource,
            codacy=codacy,
        )
        serialized = canonical_json(bundle)
        _assert_secret_free(
            serialized,
            [
                os.environ.get("GITHUB_TOKEN", ""),
                os.environ.get("GH_TOKEN", ""),
                os.environ.get("DEEPSOURCE_API_TOKEN", ""),
                os.environ.get("CODACY_API_TOKEN", ""),
            ],
        )
        _write_create_only(args.output, serialized)
    except (RunnerError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return _bound_status(bundle)


def _bound_status(bundle: dict[str, Any]) -> int:
    """0 when ``bundle`` binds the exact requested head, else 1: a green run without
    exact-head evidence would make missing evidence look like a clean producer
    (#389). The receipt is written either way, so its reason stays readable."""
    if bundle["subject_binding"] == "BOUND":
        return 0
    print(
        f"ERROR: the readback binds no exact head ({bundle['reason']});"
        " its receipt records why",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
