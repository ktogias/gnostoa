from __future__ import annotations

import argparse
import functools
import hashlib
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple, Protocol

from tools import (
    analyzer_codacy,
    analyzer_deepsource,
    analyzer_sonarcloud,
    github_events,
    github_rest,
)
from tools.analyzer_readback import (
    AnalyzerReadbackError,
    build_readback,
    canonical_json,
    coverage,
    normalize_repository,
    parse_readback,
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


def _pull(client: GitHubReader, repository: str, pull_number: int) -> Mapping[str, Any]:
    document, _ = client.get(f"{_API_ROOT}/repos/{repository}/pulls/{pull_number}")
    return _mapping(document, "GitHub Pull Request")


def _pull_side(pull: Mapping[str, Any], side: str) -> str:
    """The exact commit of the Pull Request's `side`, "head" or "base"."""
    label = f"GitHub Pull Request {side}"
    return _exact_head(_mapping(pull.get(side), label).get("sha"), label)


def _pull_head(client: GitHubReader, repository: str, pull_number: int) -> str:
    return _pull_side(_pull(client, repository, pull_number), "head")


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


def _sonarcloud_checks(
    client: GitHubReader, repository: str, head: str
) -> list[Mapping[str, Any]]:
    """Every SonarCloud check run on the head, not only the latest: a commit carries
    the runs of every pull request analysed on it, and each must be finished
    (1b.3c). The collection is complete only when it holds GitHub's total, the
    same on every page."""

    query = urllib.parse.urlencode(
        {
            "app_id": analyzer_sonarcloud.CHECK_APP_ID,
            "check_name": analyzer_sonarcloud.CHECK_NAME,
            "filter": "all",
            "per_page": 100,
        }
    )
    totals: set[int] = set()

    def runs(payload: object) -> list[Any]:
        total = _mapping(payload, "GitHub check-runs response").get("total_count")
        # A count, never a boolean or a list (CodeAnt on #424).
        if type(total) is not int or total < 0:
            raise RunnerError("GitHub's SonarCloud check-run total is malformed")
        totals.add(total)
        return _check_runs_payload(payload)

    collected = _collect_pages(
        client,
        f"{_API_ROOT}/repos/{repository}/commits/{head}/check-runs?{query}",
        extract=runs,
    )
    if totals != {len(collected)}:
        raise RunnerError("GitHub's SonarCloud check runs are incomplete")
    return collected


def _sonarcloud_check_reader(
    client: GitHubReader, repository: str, head: str
) -> Callable[[], list[Mapping[str, Any]]]:
    """A read of the head's SonarCloud check runs that the adapter can repeat,
    failing as the adapter's own provider failure."""

    def read() -> list[Mapping[str, Any]]:
        try:
            return _sonarcloud_checks(client, repository, head)
        except RunnerError as exc:
            raise analyzer_sonarcloud.ProviderReadFailure(
                _failure_kind(exc), str(exc)
            ) from exc

    return read


def _failure_kind(error: RunnerError) -> str:
    """The adapter's kind for a failed GitHub read, from the shared client's cause:
    a refused credential is authentication, a rate limit stays one and an
    unavailable provider stays unavailable, while an unusable answer, or a
    collection that does not add up, is an error (Claude and cubic on #424)."""

    cause = error.__cause__
    if not isinstance(cause, github_rest.GitHubError):
        return "ERROR"
    # The adapter's one classification of the shared client's failures (Octopus
    # on #424); a rate-limited 403 arrives as 429 (cubic on #424).
    return analyzer_sonarcloud.failure_kind(cause)


def _sonarcloud_readback(
    github: GitHubReader,
    sonarcloud: analyzer_sonarcloud.JsonReader | None,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_at: str,
) -> dict[str, Any]:
    """SonarCloud's inventory of the head, or why it is unread: without the
    readback's own credential nothing is read, although the project is public."""

    if sonarcloud is None:
        return _unavailable_readback(
            provider="sonarcloud",
            adapter="sonarcloud-web-api/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            analysis_id=None,
            scope="DIFF",
            native_mode="PULL_REQUEST",
            completeness="AUTH_UNAVAILABLE",
            observed_at=observed_at,
            reason="AUTH_UNAVAILABLE",
        )
    return analyzer_sonarcloud.read_pull_request(
        sonarcloud,
        repository=repository,
        pull_number=pull_number,
        requested_head=requested_head,
        check_runs=_sonarcloud_check_reader(github, repository, requested_head),
        observed_at=observed_at,
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


class InventoryInput(NamedTuple):
    """The same run's inventory, as the readback job receives it (#389 A0-MP1 slice
    3): the downloaded document, if the workflow names one, and the inventory job's
    trusted outputs, the document's SHA-256, the job's result and the attempt it ran
    in, with this run's own attempt."""

    document: Path | None
    expected_sha256: str | None
    result: str | None
    attempt: str | None
    run_attempt: str | None


def _commit_tree(github: GitHubReader, repository: str, head: str) -> str:
    """The head commit's tree, as GitHub reads it: the inventory's tree is checked
    against this, never against the document's own claim."""

    document, _ = github.get(f"{_API_ROOT}/repos/{repository}/commits/{head}")
    commit = _mapping(_mapping(document, "the commit").get("commit"), "the commit")
    tree = _mapping(commit.get("tree"), "the commit's tree").get("sha")
    return _exact_head(tree, "the commit's tree")


def collect_bundle(
    github: GitHubReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    deepsource: analyzer_deepsource.GraphQLReader | None,
    codacy: analyzer_codacy.JsonReader | None,
    sonarcloud: analyzer_sonarcloud.JsonReader | None,
    observed_at: str | None = None,
    inventory: InventoryInput | None = None,
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

    sonarcloud_readback = _sonarcloud_readback(
        github,
        sonarcloud,
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
        "readbacks": [
            diff_local,
            full,
            codacy_readback,
            sonarcloud_readback,
            # The project's own inventory, when the workflow gives it, bound to its
            # job's outputs (#389 A0-MP1 slice 3). The workflow always does.
            *(
                []
                if inventory is None
                else inventory_bundle_readbacks(
                    inventory.document,
                    expected_sha256=inventory.expected_sha256,
                    result=inventory.result,
                    attempt=inventory.attempt,
                    run_attempt=inventory.run_attempt,
                    repository=repository,
                    pull_number=pull_number,
                    requested_head=requested,
                    tree=functools.partial(_commit_tree, github, repository, requested),
                    observed_at=observed,
                )
            ),
        ],
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
    # The same run's inventory and its job's trusted outputs (#389 A0-MP1 slice 3).
    parser.add_argument("--inventory-document", type=Path)
    parser.add_argument("--inventory-sha256")
    parser.add_argument("--inventory-result")
    parser.add_argument("--inventory-attempt")
    parser.add_argument("--run-attempt")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] == ["inventory"]:
        return _inventory_main(arguments[1:])
    args = _parser().parse_args(arguments)
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
        try:
            sonarcloud: analyzer_sonarcloud.JsonReader | None = (
                analyzer_sonarcloud.SonarCloudRestClient.from_environment()
            )
        except analyzer_sonarcloud.ProviderReadFailure:
            sonarcloud = None
        bundle = collect_bundle(
            github,
            repository=args.repository,
            pull_number=args.pull_number,
            requested_head=args.head,
            deepsource=deepsource,
            codacy=codacy,
            sonarcloud=sonarcloud,
            inventory=(
                None
                if args.inventory_result is None
                else InventoryInput(
                    args.inventory_document,
                    args.inventory_sha256,
                    args.inventory_result,
                    args.inventory_attempt,
                    args.run_attempt,
                )
            ),
        )
        serialized = canonical_json(bundle)
        _assert_secret_free(
            serialized,
            [
                os.environ.get("GITHUB_TOKEN", ""),
                os.environ.get("GH_TOKEN", ""),
                os.environ.get("DEEPSOURCE_API_TOKEN", ""),
                os.environ.get("CODACY_API_TOKEN", ""),
                os.environ.get("SONAR_TOKEN", ""),
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


# The diagnostic inventory's shadow readback (Decision 0118; #389 A0-MP1 slice 2): this
# runner's `inventory` command, which the readback workflow's no-secret `inventory`
# job runs from protected main's checkout with main's hash-locked tools. The head's
# objects are fetched into that checkout as data, and the inventory analyzes the
# head's own tree: nothing in the head selects the code, the tools or the profile, and
# nothing in it runs (P5', #389 6381812211). Since slice 3 (Decision 0119) the
# readback adds that document to its bundle, bound to the inventory job's outputs, by
# `inventory_bundle_readbacks`, the readback command's only use of the inventory's
# modules; it imports them only when the workflow names an inventory (Cubic on #461).
INVENTORY_SCHEMA = "gnostoa-inventory-readback/v1"
# Where `collect` writes, under the process's temporary directory (the workflow sets
# TMPDIR to the runner's): never a path a caller supplies (SonarCloud
# pythonsecurity:S8707 on #460).
INVENTORY_DIRECTORY = "gnostoa-inventory"
# What the job publishes beside the document, as its upload step names it: the
# collector's inventory in its run directory, and nothing else under the directory
# (Decision 0118). Neither the producers' raw reports nor a staged source the collector
# could not remove is published (CodeAnt on #460).
INVENTORY_UPLOAD = "diagnostic-*/diagnostic-inventory.json"
# The collector's own report bound (`DiagnosticLimits.max_report_bytes`).
_INVENTORY_MAX_BYTES = 64 * 1024 * 1024
INVENTORY_DOCUMENT = "gnostoa-inventory-readback.json"


def inventory_base(
    client: GitHubReader, *, repository: str, pull_number: int, requested_head: str
) -> tuple[str, str]:
    """The Pull Request's base branch tip and its merge base with the requested head,
    once the Pull Request still has that head (Decisions 0091 and 0107). A comparison
    that names no merge base is refused."""
    pull = _pull(client, repository, pull_number)
    head = _pull_side(pull, "head")
    if head != requested_head:
        raise RunnerError("the Pull Request's head is no longer the requested head")
    tip = _pull_side(pull, "base")
    document, _ = client.get(
        f"{_API_ROOT}/repos/{repository}/compare/{tip}...{head}?per_page=1"
    )
    merge_base = _mapping(
        _mapping(document, "GitHub comparison").get("merge_base_commit"),
        "GitHub comparison merge base",
    )
    return tip, _exact_head(merge_base.get("sha"), "GitHub comparison merge base")


def inventory_collect(
    root: Path,
    output_directory: Path,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    base_tip: str,
    base: str,
    observed_at: str | None = None,
) -> Path:
    """Inventory `requested_head` against `base` under `output_directory`, and write,
    create-only, the document that records it: the subject, both bases, the
    inventory file's SHA-256 and its two readbacks. A refused inventory is recorded
    by its type alone, with unavailable readbacks."""
    from tools import analyzer_inventory, quality_evidence
    from tools.review_check import assert_document_depth, strict_json_loads

    # The directory the job uploads exists from the start, so the scan always lists
    # it, a refused inventory's included.
    output_directory.mkdir(parents=True, exist_ok=True)
    path = output_directory / INVENTORY_DOCUMENT
    if path.exists():
        raise RunnerError("output path already exists")
    observed = observed_at or _now()
    subject = {
        "repository": repository,
        "pull_number": pull_number,
        "requested_head": requested_head,
        "observed_at": observed,
    }
    inventory: dict[str, str] | None = None
    try:
        written = quality_evidence.collect_diagnostic_inventory(
            root, output_directory, base=base, expected_revision=requested_head
        )
        # Bounded, and strictly parsed: the record carries the head's text (Revix on
        # #460, strict-bounded-json-parsing).
        # Named and digested first, streamed: the file is uploaded whatever its size,
        # so the document names it even when the bound below refuses it (CodeAnt on
        # #460).
        inventory = {
            "file": written.relative_to(output_directory.resolve()).as_posix(),
            "sha256": _file_sha256(written),
        }
        raw = _read_bounded(written)
        record = strict_json_loads(raw.decode("utf-8"), label="the inventory")
        assert_document_depth(record, "the inventory")
        readbacks = analyzer_inventory.readbacks(
            record,
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_at=observed,
        )
    except (quality_evidence.QualityEvidenceError, OSError, ValueError) as exc:
        # A refusal, or a written inventory that cannot be read back (the adapter's
        # AnalyzerReadbackError and a JSON error are ValueErrors; Q on #460), by its
        # type alone: its text may name local paths.
        readbacks = analyzer_inventory.unavailable(
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_at=observed,
            reason=type(exc).__name__,
        )
    serialized = canonical_json(
        {
            "schema": INVENTORY_SCHEMA,
            **subject,
            "base_tip": base_tip,
            "base": base,
            "inventory": inventory,
            "readbacks": readbacks,
        }
    )
    # The boundary is the workflow's: its collect step holds no token at all, so it
    # has none to leak (cubic on #460). A run whose environment does hold one, by
    # hand or from another step, is refused if any uploaded file or the document
    # holds it; with no token in the environment there is nothing to check.
    secrets = [os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GH_TOKEN", "")]
    # What the upload step's pattern matches is exactly the inventory the document
    # names, or nothing when it names none.
    named = (
        [] if inventory is None else [output_directory.resolve() / inventory["file"]]
    )
    if _uploaded_files(output_directory) != named:
        raise RunnerError(
            "the upload would publish an inventory the document does not name"
        )
    _assert_uploads_secret_free(output_directory, secrets)
    _assert_secret_free(serialized, secrets)
    _write_create_only(path, serialized)
    return path


class _InventoryRefused(Exception):
    """One reason this run's inventory document cannot reach the bundle; its text is
    the reason both project readbacks record."""


# What the inventory's binding can raise beyond its own refusals: a file system call,
# a parse, a GitHub read, the profile's load, or a module its helpers import. Each is
# a refusal of the project readbacks, never of the bundle.
_INVENTORY_PATH_FAILURES: tuple[type[BaseException], ...] = (
    OSError,
    ValueError,
    ImportError,
    RunnerError,
)


def _inventory_bytes(
    document: Path | None,
    expected_sha256: str | None,
    result: str | None,
    attempt: str | None,
    run_attempt: str | None,
) -> bytes:
    """The document's bytes, once the inventory job's trusted outputs name it as this
    attempt's: the job succeeded, in this attempt, and wrote exactly these bytes."""

    if result != "success":
        raise _InventoryRefused(f"INVENTORY_JOB_{(result or 'absent').upper()}")
    if (
        document is None
        or not expected_sha256
        or not document.is_file()
        or document.is_symlink()
    ):
        raise _InventoryRefused("INVENTORY_DOCUMENT_MISSING")
    if not attempt or attempt != run_attempt:
        raise _InventoryRefused("INVENTORY_ATTEMPT_STALE")
    try:
        raw = _read_bounded(document)
    except (OSError, ValueError) as exc:
        raise _InventoryRefused(type(exc).__name__) from None
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise _InventoryRefused("DIGEST_MISMATCH")
    return raw


def _inventory_readback_list(raw: bytes, subject: tuple[str, int, str]) -> list[Any]:
    """The document's two readbacks, read strictly, once it names this subject."""

    from tools.review_check import assert_document_depth, strict_json_loads

    label = "the inventory document"
    try:
        loaded = _mapping(strict_json_loads(raw.decode("utf-8"), label=label), label)
        assert_document_depth(loaded, label)
    except (ValueError, RunnerError) as exc:
        raise _InventoryRefused(type(exc).__name__) from None
    named = (
        loaded.get("repository"),
        loaded.get("pull_number"),
        loaded.get("requested_head"),
    )
    if named != subject:
        raise _InventoryRefused("WRONG_SUBJECT")
    readbacks = loaded.get("readbacks")
    if not isinstance(readbacks, list) or len(readbacks) != 2:
        raise _InventoryRefused("MALFORMED_READBACKS")
    return readbacks


def _protected_profile_digest() -> str:
    """The protected profile's digest, computed again from main's checkout. A profile
    that cannot be loaded refuses the project readbacks alone, so the vendors'
    readbacks never depend on it (Revix on #461): with the document's and the tree's
    reads, every external read of this binding is contained."""

    from tools import quality_evidence
    from tools.review_model import canonical_digest

    try:
        return canonical_digest(quality_evidence.load_diagnostic_profile())
    except (quality_evidence.QualityEvidenceError, OSError, ValueError):
        raise _InventoryRefused("PROFILE_UNAVAILABLE") from None


def _check_inventory_readback(
    readback: object, *, scope: str, requested_head: str, tree: str, profile: str
) -> None:
    """One readback: the inventory's own at `scope`, for the requested head, and,
    unless it is UNAVAILABLE, of the head's tree under the protected profile."""

    from tools import analyzer_inventory

    try:
        parsed = parse_readback(readback)
    except ValueError as exc:
        raise _InventoryRefused(type(exc).__name__) from None
    if (parsed["provider"], parsed["scope"]) != (analyzer_inventory.PROVIDER, scope):
        raise _InventoryRefused("MALFORMED_READBACKS")
    if parsed["requested_head"] != requested_head:
        raise _InventoryRefused("WRONG_SUBJECT")
    if parsed["completeness"] == "READBACK_UNAVAILABLE":
        return
    native = parsed.get("native") or {}
    if native.get("tree") != tree:
        raise _InventoryRefused("WRONG_TREE")
    if native.get("profile") != profile:
        raise _InventoryRefused("FOREIGN_PROFILE")


def inventory_bundle_readbacks(
    document: Path | None,
    *,
    expected_sha256: str | None,
    result: str | None,
    attempt: str | None,
    run_attempt: str | None,
    repository: str,
    pull_number: int,
    requested_head: str,
    tree: Callable[[], str],
    observed_at: str,
) -> list[dict[str, Any]]:
    """The project inventory's two readbacks for the bundle (#389 A0-MP1 slice 3; r4
    6399931352): this run attempt's inventory document, bound to the inventory job's
    trusted outputs (its `result`, its attempt, and the SHA-256 main's runner
    computed of the document), to the subject and its tree, and to the protected
    profile. Any refusal gives both readbacks UNAVAILABLE with its reason, so the
    project items deny; a prior document or attempt is never read in its place. The
    head's tree is read only once the document is bound, and a read that fails is a
    refusal, so the vendors' readbacks never depend on it (Revix, CodeAnt, Kilo and
    Cubic on #461)."""

    try:
        from tools import analyzer_inventory
    except ImportError:
        # The adapter builds the refusal itself, so without it there is no project
        # readback to give: the project items are MISSING, which denies as
        # UNAVAILABLE does, and the vendors' readbacks stay (Revix on #461).
        return []
    try:
        raw = _inventory_bytes(document, expected_sha256, result, attempt, run_attempt)
        readbacks = _inventory_readback_list(
            raw, (repository, pull_number, requested_head)
        )
        try:
            head_tree = tree()
        except RunnerError:
            raise _InventoryRefused("TREE_UNAVAILABLE") from None
        profile = _protected_profile_digest()
        for scope, readback in zip(("DIFF", "FULL"), readbacks, strict=True):
            _check_inventory_readback(
                readback,
                scope=scope,
                requested_head=requested_head,
                tree=head_tree,
                profile=profile,
            )
    except _InventoryRefused as refusal:
        reason = str(refusal)
    except _INVENTORY_PATH_FAILURES as exc:
        # The shape, not one more instance (Claude on #461, after the tree's and the
        # profile's reads): any other failure of this path is refused here, by its
        # type alone, so the vendors' readbacks never depend on it.
        reason = type(exc).__name__
    else:
        return readbacks
    return analyzer_inventory.unavailable(
        repository=repository,
        pull_number=pull_number,
        requested_head=requested_head,
        observed_at=observed_at,
        reason=reason,
    )


_SCAN_CHUNK_BYTES = 1_048_576


def _file_sha256(path: Path) -> str:
    """`path`'s SHA-256, read in bounded chunks, so no file is held whole."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(_SCAN_CHUNK_BYTES):
            digest.update(block)
    return digest.hexdigest()


def _read_bounded(path: Path) -> bytes:
    """`path`'s bytes, refused past the collector's own report bound: the inventory
    and its document are read only this way (Revix on #460,
    strict-bounded-json-parsing)."""
    with path.open("rb") as handle:
        raw = handle.read(_INVENTORY_MAX_BYTES + 1)
    if len(raw) > _INVENTORY_MAX_BYTES:
        raise ValueError("the file exceeds its byte bound")
    return raw


def _uploaded_files(directory: Path) -> list[Path]:
    """The files the upload step publishes beside the document: its pattern's matches
    under `directory`, each a regular file reached through no link, which the pinned
    upload-artifact would follow (`followSymbolicLinks: true`; Claude on #460)."""
    files = sorted(directory.resolve().glob(INVENTORY_UPLOAD))
    for path in files:
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            raise RunnerError("an uploaded file is reached through a link")
    return files


def _holds_any(path: Path, needles: list[bytes], chunk: int) -> bool:
    """Whether `path` holds any needle, read in bounded chunks, each searched with
    the end of the one before, so no file is ever held whole (cubic on #460)."""
    if not needles:
        return False
    keep = max(len(needle) for needle in needles) - 1
    tail = b""
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            window = tail + block
            if any(needle in window for needle in needles):
                return True
            tail = window[-keep:] if keep else b""
    return False


def _assert_uploads_secret_free(
    directory: Path, secrets: list[str], *, chunk: int = _SCAN_CHUNK_BYTES
) -> None:
    """Refuse an upload from `directory` that would publish what this did not read: a
    link, or an uploaded file that holds a secret's bytes; the document is checked as
    it is serialized."""
    files = _uploaded_files(directory)
    needles = [secret.encode("utf-8") for secret in secrets if secret]
    if needles and any(_holds_any(path, needles, chunk) for path in files):
        raise RunnerError("an uploaded file contains credential bytes")


def _inventory_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="analyzer_readback.py inventory")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("base", "collect"):
        command = commands.add_parser(name)
        command.add_argument("--repository", required=True)
        command.add_argument("--pull-number", type=int, required=True)
        command.add_argument("--head", required=True)
        if name == "collect":
            command.add_argument("--base-tip", required=True)
            command.add_argument("--base", required=True)
    return parser


def _inventory_main(argv: list[str]) -> int:
    """`base` prints the step outputs `base_tip` and `base`; `collect` writes the
    document, and fails when it records a refused inventory."""
    args = _inventory_parser().parse_args(argv)
    try:
        _repository(args.repository)
        if args.pull_number <= 0:
            raise RunnerError("pull number must be positive")
        head = _exact_head(args.head, "head")
        if args.command == "base":
            tip, merge_base = inventory_base(
                GitHubReadClient.from_environment(),
                repository=args.repository,
                pull_number=args.pull_number,
                requested_head=head,
            )
            print(f"base_tip={tip}")
            print(f"base={merge_base}")
            return 0
        path = inventory_collect(
            Path.cwd(),
            Path(tempfile.gettempdir()) / INVENTORY_DIRECTORY,
            repository=args.repository,
            pull_number=args.pull_number,
            requested_head=head,
            base_tip=_exact_head(args.base_tip, "base tip"),
            base=_exact_head(args.base, "base"),
        )
        # Read back inside the handlers, so its failure is reported by type too
        # (Claude on #460).
        from tools.review_check import assert_document_depth, strict_json_loads

        label = "the inventory document"
        document = strict_json_loads(_read_bounded(path).decode("utf-8"), label=label)
        assert_document_depth(document, label)
        readbacks = _mapping(document, label).get("readbacks")
        if not isinstance(readbacks, list):
            raise RunnerError("the inventory document's readbacks are malformed")
        refused = any(
            _mapping(r, "an inventory readback").get("completeness")
            == "READBACK_UNAVAILABLE"
            for r in readbacks
        )
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        # By its type alone: its text can name local paths (Revix on #460).
        print(f"ERROR: {type(exc).__name__}", file=sys.stderr)
        return 2
    if refused:
        print(
            "ERROR: the inventory was not read back; its document records why",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
