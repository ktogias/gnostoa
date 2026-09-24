from __future__ import annotations

import http.client
import json
import os
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
    normalize_repository,
)

_API_ROOT = "https://app.codacy.com"
_API_V3 = f"{_API_ROOT}/api/v3"
_TOKEN_ENV = "CODACY_API_TOKEN"  # nosec B105 -- environment variable name, not a credential
_TIMEOUT_SECONDS = 30
_MAX_RESPONSE_BYTES = 4_194_304
_MAX_PAGES = 100


class ProviderReadFailure(RuntimeError):
    def __init__(self, kind: str, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.status = status


class JsonReader(Protocol):
    def get(self, url: str) -> Mapping[str, Any]: ...


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_api_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ProviderReadFailure(
            "ERROR", "Codacy API URL has an invalid port"
        ) from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "app.codacy.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ProviderReadFailure(
            "ERROR", "Codacy API URL is outside the admitted origin"
        )
    return url


class _CodacyRedirectHandler(urllib.request.HTTPRedirectHandler):
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
        token = next(
            (value for key, value in req.header_items() if key.lower() == "api-token"),
            None,
        )
        redirected = super().redirect_request(req, fp, code, msg, headers, admitted)
        if redirected is not None and token is not None:
            redirected.add_unredirected_header("api-token", token)
        return redirected


class CodacyRestClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise ProviderReadFailure("AUTH", "Codacy authentication unavailable")
        if any(not "!" <= char <= "~" for char in token):
            raise ProviderReadFailure("AUTH", "Codacy credential is malformed")
        self._token = token
        self._opener = urllib.request.build_opener(_CodacyRedirectHandler())

    @classmethod
    def from_environment(cls) -> CodacyRestClient:
        return cls(os.environ.get(_TOKEN_ENV, ""))

    def get(self, url: str) -> Mapping[str, Any]:
        request = urllib.request.Request(
            _validate_api_url(url),
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "gnostoa-analyzer-readback",
            },
        )
        request.add_unredirected_header("api-token", self._token)
        try:
            with self._opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderReadFailure(
                    "AUTH", "Codacy authentication unavailable", status=exc.code
                ) from exc
            if exc.code in {429, 503, 504}:
                raise ProviderReadFailure(
                    "RATE_LIMIT",
                    "Codacy API rate limited or unavailable",
                    status=exc.code,
                ) from exc
            raise ProviderReadFailure(
                "UNAVAILABLE", f"Codacy API HTTP {exc.code}", status=exc.code
            ) from exc
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise ProviderReadFailure("UNAVAILABLE", "Codacy API unavailable") from exc
        except ValueError:
            # HTTP header validation can include credential bytes in its error.
            raise ProviderReadFailure(
                "ERROR", "Codacy request failed validation"
            ) from None
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ProviderReadFailure(
                "ERROR", "Codacy API response exceeds bounded size"
            )
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderReadFailure(
                "ERROR", "Codacy API returned invalid JSON"
            ) from exc
        if not isinstance(document, Mapping):
            raise ProviderReadFailure("ERROR", "Codacy API response must be an object")
        return document


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderReadFailure("ERROR", f"Codacy {label} is malformed")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProviderReadFailure("ERROR", f"Codacy {label} is malformed")
    return value


def _integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ProviderReadFailure("ERROR", f"Codacy {label} is malformed")
    return value


def _failure_coverage(
    error: ProviderReadFailure, *, pages: int, count: int
) -> dict[str, Any]:
    if error.kind == "RATE_LIMIT":
        status = "RATE_LIMITED"
        reason = "RATE_LIMITED"
    elif error.kind == "AUTH":
        status = "UNAVAILABLE"
        reason = "AUTH_UNAVAILABLE"
    elif error.kind == "UNAVAILABLE":
        status = "UNAVAILABLE"
        reason = "READBACK_UNAVAILABLE"
    else:
        status = "ERROR"
        reason = "PROVIDER_ERROR"
    return coverage(status, pages=pages, count=count, reason=reason)


def _failure_completeness(error: ProviderReadFailure) -> str:
    return "AUTH_UNAVAILABLE" if error.kind == "AUTH" else "READBACK_UNAVAILABLE"


def _root(repository: str, provider: str) -> tuple[str, str, str]:
    try:
        normalized = normalize_repository(repository)
    except AnalyzerReadbackError as exc:
        raise ProviderReadFailure("ERROR", "repository identity is unsafe") from exc
    owner, name = normalized.split("/", 1)
    encoded_owner = urllib.parse.quote(owner, safe="")
    encoded_name = urllib.parse.quote(name, safe="")
    encoded_provider = urllib.parse.quote(provider, safe="")
    return (
        owner,
        name,
        f"{_API_V3}/analysis/organizations/{encoded_provider}/{encoded_owner}/repositories/{encoded_name}",
    )


def _pull_subject(
    document: Mapping[str, Any],
    *,
    owner: str,
    name: str,
    pull_number: int,
) -> tuple[str, bool]:
    pull = _mapping(document.get("pullRequest"), "pullRequest")
    if pull.get("number") != pull_number:
        raise ProviderReadFailure("ERROR", "Codacy Pull Request identity changed")
    if pull.get("repository") != name:
        raise ProviderReadFailure("ERROR", "Codacy repository identity changed")
    head = _text(pull.get("headCommitSha"), "pullRequest.headCommitSha")
    href = _text(pull.get("gitHref"), "pullRequest.gitHref")
    expected_href = f"https://github.com/{owner}/{name}/pull/{pull_number}"
    if href.rstrip("/") != expected_href:
        raise ProviderReadFailure(
            "ERROR", "Codacy Git provider Pull Request identity changed"
        )
    is_analysing = document.get("isAnalysing")
    if type(is_analysing) is not bool:
        raise ProviderReadFailure("ERROR", "Codacy analysis state is malformed")
    return head, is_analysing


def _issue_finding(item: Mapping[str, Any]) -> dict[str, Any]:
    commit_issue = _mapping(item.get("commitIssue"), "pull request issue.commitIssue")
    pattern = _mapping(
        commit_issue.get("patternInfo"), "pull request issue.patternInfo"
    )
    issue_id = item.get("issueId") or commit_issue.get("issueId")
    if not isinstance(issue_id, str) or not issue_id:
        raise ProviderReadFailure(
            "ERROR", "Codacy pull request issue identity is unavailable"
        )
    result_data_id = commit_issue.get("resultDataId")
    if result_data_id is not None and (
        type(result_data_id) is not int or result_data_id < 0
    ):
        raise ProviderReadFailure(
            "ERROR", "Codacy pull request resultDataId is malformed"
        )
    message = commit_issue.get("message") or pattern.get("title") or pattern.get("id")
    delta_type = _text(item.get("deltaType"), "pull request issue.deltaType")
    native: dict[str, Any] = {"issue_id": issue_id}
    if result_data_id is not None:
        native["result_data_id"] = result_data_id
    finding: dict[str, Any] = {
        "id": issue_id,
        "message": _text(message, "pull request issue message"),
        "rule": _text(pattern.get("id"), "pull request issue pattern id"),
        "native_ref": issue_id,
        "state": delta_type.lower(),
        "provenance": [{"surface": "codacy-api-v3", "reference": issue_id}],
        "native": native,
    }
    for source, target in (("severityLevel", "severity"), ("category", "category")):
        value = pattern.get(source)
        if isinstance(value, str) and value:
            finding[target] = value
    path = commit_issue.get("filePath")
    if isinstance(path, str) and path:
        finding["path"] = path
    line = commit_issue.get("lineNumber")
    if type(line) is int and line > 0:
        finding["range"] = {"start_line": line, "end_line": line}
    tool = commit_issue.get("toolInfo")
    if isinstance(tool, Mapping):
        tool_name = tool.get("name")
        tool_uuid = tool.get("uuid")
        if isinstance(tool_name, str) and tool_name:
            native["tool_name"] = tool_name
        if isinstance(tool_uuid, str) and tool_uuid:
            native["tool_uuid"] = tool_uuid
        tool_id = (
            tool_uuid
            if isinstance(tool_uuid, str) and tool_uuid
            else tool_name
            if isinstance(tool_name, str) and tool_name
            else None
        )
        if tool_id is not None:
            normalized_tool = {"id": tool_id}
            if isinstance(tool_name, str) and tool_name:
                normalized_tool["name"] = tool_name
            finding["tool"] = normalized_tool
    return finding


def _merge_issue_findings(values: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse Codacy's overlapping potential/all issue surfaces by native ID."""

    by_id: dict[str, dict[str, Any]] = {}
    comparable: dict[str, dict[str, Any]] = {}
    for value in values:
        finding = dict(value)
        identity = finding.get("id")
        if not isinstance(identity, str) or not identity:
            raise AnalyzerReadbackError("Codacy finding identity is unavailable")
        native = dict(finding.get("native", {}))
        potential = native.pop("potential", False)
        comparison = dict(finding)
        comparison["native"] = native
        existing = by_id.get(identity)
        if existing is None:
            retained = dict(finding)
            retained_native = dict(retained.get("native", {}))
            retained_native["potential"] = bool(potential)
            retained["native"] = retained_native
            by_id[identity] = retained
            comparable[identity] = comparison
            continue
        if comparable[identity] != comparison:
            raise AnalyzerReadbackError(
                f"Codacy finding identity {identity!r} is conflicting"
            )
        retained_native = dict(existing.get("native", {}))
        retained_native["potential"] = bool(
            retained_native.get("potential") or potential
        )
        existing["native"] = retained_native
    return [by_id[key] for key in sorted(by_id)]


def _read_pull_request(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_at: str | None = None,
    provider: str = "gh",
) -> dict[str, Any]:
    observed = observed_at or _now()
    owner, name, root = _root(repository, provider)
    pages = 0
    try:
        pr_document = client.get(f"{root}/pull-requests/{pull_number}")
        pages += 1
        head, _initial_analysing = _pull_subject(
            pr_document,
            owner=owner,
            name=name,
            pull_number=pull_number,
        )
    except ProviderReadFailure as exc:
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=None,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness=_failure_completeness(exc),
            native_mode="PULL_REQUEST",
            observed_at=observed,
            run_state="UNKNOWN",
            coverage_record=_failure_coverage(exc, pages=pages, count=0),
            findings=[],
        )
    if head != requested_head:
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=head,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness="AMBIGUOUS",
            native_mode="PULL_REQUEST",
            observed_at=observed,
            run_state="ANALYZING" if _initial_analysing else "OBSERVED",
            coverage_record=coverage(
                "INCOMPLETE", pages=pages, count=0, reason="SUBJECT_MISMATCH"
            ),
            findings=[],
        )

    findings: list[Mapping[str, Any]] = []
    surface_totals: dict[str, int] = {}
    try:
        for only_potential in (False, True):
            cursor: str | None = None
            surface_total: int | None = None
            surface_count = 0
            for _ in range(_MAX_PAGES):
                query = {
                    "status": "new",
                    "onlyPotential": "true" if only_potential else "false",
                }
                if cursor is not None:
                    query["cursor"] = cursor
                url = (
                    f"{root}/pull-requests/{pull_number}/issues?"
                    f"{urllib.parse.urlencode(query)}"
                )
                document = client.get(url)
                pages += 1
                analyzed = document.get("analyzed")
                if type(analyzed) is not bool:
                    raise ProviderReadFailure(
                        "ERROR", "Codacy analyzed flag is malformed"
                    )
                if not analyzed:
                    retained = _merge_issue_findings(findings)
                    return build_readback(
                        provider="codacy",
                        adapter="codacy-api-v3/v1",
                        repository=repository,
                        pull_number=pull_number,
                        requested_head=requested_head,
                        observed_head=head,
                        analysis_id=f"pr:{pull_number}",
                        scope="DIFF",
                        completeness="READBACK_UNAVAILABLE",
                        native_mode="PULL_REQUEST",
                        observed_at=observed,
                        run_state="ANALYZING",
                        coverage_record=coverage(
                            "PARTIAL",
                            pages=pages,
                            count=len(retained),
                            reason="LATEST_COMMIT_NOT_ANALYZED",
                        ),
                        findings=retained,
                    )
                data = document.get("data")
                if not isinstance(data, list):
                    raise ProviderReadFailure(
                        "ERROR", "Codacy issue page data is malformed"
                    )
                page_findings = [
                    _issue_finding(_mapping(item, "pull request issue"))
                    for item in data
                ]
                for finding in page_findings:
                    native = dict(finding.get("native", {}))
                    native["potential"] = only_potential
                    finding["native"] = native
                findings.extend(page_findings)
                surface_count += len(page_findings)

                raw_pagination = document.get("pagination")
                pagination = (
                    {}
                    if raw_pagination is None
                    else _mapping(raw_pagination, "pagination")
                )
                raw_total = pagination.get("total")
                if raw_total is not None:
                    total = _integer(raw_total, "pagination.total")
                    if surface_total is None:
                        surface_total = total
                    elif total != surface_total:
                        raise ProviderReadFailure(
                            "ERROR",
                            "Codacy issue total changed during pagination",
                        )
                next_cursor = pagination.get("cursor")
                if next_cursor is None:
                    cursor = None
                    break
                cursor = _text(next_cursor, "pagination.cursor")
            else:
                raise ProviderReadFailure(
                    "ERROR", "Codacy issue pagination exceeded bound"
                )

            if surface_total is not None:
                if surface_count != surface_total:
                    retained = _merge_issue_findings(findings)
                    return build_readback(
                        provider="codacy",
                        adapter="codacy-api-v3/v1",
                        repository=repository,
                        pull_number=pull_number,
                        requested_head=requested_head,
                        observed_head=head,
                        analysis_id=f"pr:{pull_number}",
                        scope="DIFF",
                        completeness="READBACK_UNAVAILABLE",
                        native_mode="PULL_REQUEST",
                        observed_at=observed,
                        run_state="OBSERVED",
                        coverage_record=coverage(
                            "ERROR",
                            pages=pages,
                            count=len(retained),
                            reason="COUNT_TOTAL_MISMATCH",
                        ),
                        findings=retained,
                    )
                surface_totals["potential" if only_potential else "all"] = surface_total
    except ProviderReadFailure as exc:
        retained = _merge_issue_findings(findings)
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=head,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness=_failure_completeness(exc),
            native_mode="PULL_REQUEST",
            observed_at=observed,
            run_state="OBSERVED",
            coverage_record=_failure_coverage(exc, pages=pages, count=len(retained)),
            findings=retained,
        )
    try:
        final_pr_document = client.get(f"{root}/pull-requests/{pull_number}")
        pages += 1
        final_head, final_analysing = _pull_subject(
            final_pr_document,
            owner=owner,
            name=name,
            pull_number=pull_number,
        )
    except ProviderReadFailure as exc:
        retained = _merge_issue_findings(findings)
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=head,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness=_failure_completeness(exc),
            native_mode="PULL_REQUEST",
            observed_at=observed,
            run_state="OBSERVED",
            coverage_record=_failure_coverage(exc, pages=pages, count=len(retained)),
            findings=retained,
        )
    if final_head != head:
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=final_head,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness="AMBIGUOUS",
            native_mode="PULL_REQUEST",
            observed_at=observed,
            run_state="ANALYZING" if final_analysing else "OBSERVED",
            coverage_record=coverage(
                "INCOMPLETE",
                pages=pages,
                count=0,
                reason="SUBJECT_CHANGED_DURING_READBACK",
            ),
            findings=[],
        )
    if _initial_analysing or final_analysing:
        retained = _merge_issue_findings(findings)
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=final_head,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness="READBACK_UNAVAILABLE",
            native_mode="PULL_REQUEST",
            observed_at=observed,
            run_state="ANALYZING",
            coverage_record=coverage(
                "PARTIAL",
                pages=pages,
                count=len(retained),
                reason="ANALYSIS_IN_PROGRESS",
            ),
            findings=retained,
        )

    retained = _merge_issue_findings(findings)
    complete = coverage(
        "COMPLETE",
        pages=pages,
        count=len(retained),
    )
    return build_readback(
        provider="codacy",
        adapter="codacy-api-v3/v1",
        repository=repository,
        pull_number=pull_number,
        requested_head=requested_head,
        observed_head=head,
        analysis_id=f"pr:{pull_number}",
        scope="DIFF",
        completeness="FULL_RUN",
        native_mode="PULL_REQUEST",
        observed_at=observed,
        run_state="COMPLETE",
        coverage_record=complete,
        findings=retained,
        native={
            "is_up_to_standards": final_pr_document.get("isUpToStandards"),
            "issue_surface_totals": dict(sorted(surface_totals.items())),
        },
    )


def read_pull_request(
    client: JsonReader,
    *,
    repository: str,
    pull_number: int,
    requested_head: str,
    observed_at: str | None = None,
    provider: str = "gh",
) -> dict[str, Any]:
    """Read one Codacy PR without letting normalization conflicts abort the bundle."""

    try:
        return _read_pull_request(
            client,
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_at=observed_at,
            provider=provider,
        )
    except AnalyzerReadbackError:
        observed = observed_at or _now()
        return build_readback(
            provider="codacy",
            adapter="codacy-api-v3/v1",
            repository=repository,
            pull_number=pull_number,
            requested_head=requested_head,
            observed_head=None,
            analysis_id=f"pr:{pull_number}",
            scope="DIFF",
            completeness="READBACK_UNAVAILABLE",
            native_mode="PULL_REQUEST",
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
