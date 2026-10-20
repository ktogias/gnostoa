from __future__ import annotations

import hashlib
import http.client
import inspect
import io
import json
import time
import unittest
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, cast
from unittest.mock import patch

from tools import analyzer_codacy, analyzer_deepsource, analyzer_readback, github_rest

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
RUN_UID = "0c29b163-9e8e-43be-bd8b-a93254aa2748"
OBSERVED = "2026-09-23T13:30:00Z"


class _DeepSourceFake:
    def __init__(self, responses: dict[tuple[str, str | None], Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def graphql(self, query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        variables_dict = dict(variables)
        self.calls.append((query, variables_dict))
        if "AnalyzerRun" in query:
            key = ("run", variables_dict.get("cursor"))
        else:
            key = (str(variables_dict.get("id")), variables_dict.get("cursor"))
        value = self.responses[key]
        if isinstance(value, BaseException):
            raise value
        return value


class _CodacyFake:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> Mapping[str, Any]:
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, list):
            if not value:
                raise RuntimeError(f"no remaining fake responses for {url}")
            value = value.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value


def _run_page(
    *,
    head: str = HEAD,
    cursor: str | None = None,
    run_status: str = "FAILURE",
    check_status: str = "FAILURE",
) -> dict[str, Any]:
    return {
        "data": {
            "run": {
                "id": "run-node",
                "runUid": RUN_UID,
                "commitOid": head,
                "baseOid": "c" * 40,
                "status": run_status,
                "repository": {
                    "name": "gnostoa",
                    "account": {"login": "ktogias", "vcsProvider": "GITHUB"},
                },
                "checks": {
                    "totalCount": 1,
                    "edges": [
                        {
                            "node": {
                                "id": "check-python",
                                "status": check_status,
                                "analyzer": {"shortcode": "python"},
                            }
                        }
                    ],
                    "pageInfo": {
                        "hasNextPage": cursor is not None,
                        "endCursor": cursor,
                    },
                },
            }
        }
    }


def _issue(issue_id: str, line: int) -> dict[str, Any]:
    return {
        "id": issue_id,
        "path": "tools/example.py",
        "severity": "MAJOR",
        "category": "TYPECHECK",
        "title": f"Issue {issue_id}",
        "explanation": "Details",
        "isSuppressed": False,
        "beginLine": line,
        "beginColumn": 1,
        "endLine": line,
        "endColumn": 4,
        "shortcode": "PY-TYPE",
        "issue": {
            "shortcode": "PY-TYPE",
            "title": "Type issue",
            "severity": "MAJOR",
            "category": "TYPECHECK",
        },
    }


def _check_page(
    issues: list[dict[str, Any]],
    *,
    total: int,
    cursor: str | None,
    status: str = "FAILURE",
) -> dict[str, Any]:
    return {
        "data": {
            "node": {
                "id": "check-python",
                "status": status,
                "analyzer": {"shortcode": "python"},
                "issues": {
                    "totalCount": total,
                    "edges": [{"node": item} for item in issues],
                    "pageInfo": {
                        "hasNextPage": cursor is not None,
                        "endCursor": cursor,
                    },
                },
            }
        }
    }


def _codacy_root() -> str:
    return (
        "https://app.codacy.com/api/v3/analysis/organizations/gh/ktogias/"
        "repositories/gnostoa"
    )


def _codacy_issues_url(*, potential: bool, cursor: str | None = None) -> str:
    query = f"status=new&onlyPotential={'true' if potential else 'false'}"
    if cursor is not None:
        query += f"&cursor={cursor}"
    return f"{_codacy_root()}/pull-requests/312/issues?{query}"


def _codacy_pr(head: str = HEAD) -> dict[str, Any]:
    return {
        "isUpToStandards": False,
        "isAnalysing": False,
        "pullRequest": {
            "number": 312,
            "repository": "gnostoa",
            "headCommitSha": head,
            "gitHref": "https://github.com/ktogias/gnostoa/pull/312",
        },
    }


def _codacy_issue(issue_id: str, line: int) -> dict[str, Any]:
    return {
        "deltaType": "Added",
        "commitIssue": {
            "issueId": issue_id,
            "resultDataId": line * 100,
            "patternInfo": {
                "id": "RUF001",
                "category": "CodeStyle",
                "level": "Warning",
                "severityLevel": "High",
                "title": "Formatting issue",
            },
            "filePath": "tools/example.py",
            "lineNumber": line,
            "message": f"Codacy {issue_id}",
            "language": "Python",
            "toolInfo": {"name": "Ruff", "uuid": "ruff-tool"},
        },
    }


class AnalyzerReadbackModelTests(unittest.TestCase):
    def test_finding_rejects_reversed_same_line_columns(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError, "ends before it starts"
        ):
            analyzer_readback.normalize_finding(
                {
                    "id": "synthetic-range",
                    "message": "synthetic location",
                    "range": {
                        "start_line": 12,
                        "end_line": 12,
                        "start_column": 9,
                        "end_column": 3,
                    },
                }
            )

    def test_finding_preserves_nonreversed_and_partial_ranges(self) -> None:
        locations = [
            {"start_line": 12, "end_line": 12, "start_column": 3, "end_column": 9},
            {"start_line": 12, "end_line": 12, "start_column": 3, "end_column": 3},
            {"start_line": 12, "end_line": 13, "start_column": 9, "end_column": 3},
            {"start_line": 12, "end_line": 12, "start_column": 9},
            {"start_line": 12, "end_line": 12, "end_column": 3},
            {"start_line": 12, "end_line": 12},
            {"start_line": 12, "start_column": 9, "end_column": 3},
            {"end_line": 12, "start_column": 9, "end_column": 3},
            {"start_column": 9, "end_column": 3},
        ]
        for location in locations:
            with self.subTest(location=location):
                finding = analyzer_readback.normalize_finding(
                    {
                        "id": "synthetic-range",
                        "message": "synthetic location",
                        "range": location,
                    }
                )
                self.assertEqual(location, finding["range"])

    def test_requested_head_must_be_exact_sha(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "requested head must be an exact 40-character SHA",
        ):
            analyzer_readback.build_readback(
                provider="synthetic",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=1,
                requested_head="abc",
                observed_head=None,
                analysis_id=None,
                scope="FULL",
                completeness="READBACK_UNAVAILABLE",
                native_mode="FULL_RUN",
                observed_at=OBSERVED,
                run_state="UNKNOWN",
                coverage_record=analyzer_readback.coverage(
                    "UNAVAILABLE", pages=0, count=0, reason="FIXTURE"
                ),
                findings=[],
            )

    def test_complete_coverage_rejects_provider_total_disagreement(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "coverage count disagrees with provider total",
        ):
            analyzer_readback.coverage("COMPLETE", pages=1, count=1, total=2)

    def test_duplicate_provider_identity_collapses_and_retains_provenance(self) -> None:
        common = {
            "id": "provider-1",
            "message": "same issue",
            "path": "a.py",
            "range": {"start_line": 1, "end_line": 1},
        }
        findings = analyzer_readback.deduplicate_findings(
            [
                {
                    **common,
                    "provenance": [
                        {"surface": "github-inline", "reference": "comment:1"}
                    ],
                },
                {
                    **common,
                    "provenance": [{"surface": "provider-api", "reference": "issue:1"}],
                },
            ]
        )
        self.assertEqual(1, len(findings))
        self.assertEqual(
            ["github-inline", "provider-api"],
            [item["surface"] for item in findings[0]["provenance"]],
        )

    def test_build_readback_derives_count_after_deduplication(self) -> None:
        common = {
            "id": "provider-1",
            "message": "same issue",
            "path": "a.py",
        }
        document = analyzer_readback.build_readback(
            provider="synthetic-analyzer",
            adapter="fixture/v1",
            repository="example/project",
            pull_number=9,
            requested_head=HEAD,
            observed_head=HEAD,
            analysis_id="run-9",
            scope="FULL",
            completeness="FULL_RUN",
            native_mode="COMPLETE_SCAN",
            observed_at=OBSERVED,
            run_state="SUCCESS",
            coverage_record=analyzer_readback.coverage("COMPLETE", pages=1, count=1),
            findings=[
                {
                    **common,
                    "provenance": [{"surface": "provider-a", "reference": "finding:1"}],
                },
                {
                    **common,
                    "provenance": [{"surface": "provider-b", "reference": "finding:1"}],
                },
            ],
        )
        self.assertEqual(1, document["coverage"]["count"])
        self.assertEqual(1, len(document["findings"]))

    def test_complete_coverage_rejects_count_above_retained_without_total(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "complete coverage count must match retained finding population",
        ):
            analyzer_readback.build_readback(
                provider="synthetic-analyzer",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=9,
                requested_head=HEAD,
                observed_head=HEAD,
                analysis_id="run-9",
                scope="FULL",
                completeness="FULL_RUN",
                native_mode="COMPLETE_SCAN",
                observed_at=OBSERVED,
                run_state="SUCCESS",
                coverage_record=analyzer_readback.coverage(
                    "COMPLETE", pages=1, count=2
                ),
                findings=[{"id": "provider-1", "message": "retained issue"}],
            )

    def test_build_readback_keeps_provider_total_strict_after_deduplication(
        self,
    ) -> None:
        common = {"id": "provider-1", "message": "same issue"}
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "coverage count disagrees with provider total",
        ):
            analyzer_readback.build_readback(
                provider="synthetic-analyzer",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=9,
                requested_head=HEAD,
                observed_head=HEAD,
                analysis_id="run-9",
                scope="FULL",
                completeness="FULL_RUN",
                native_mode="COMPLETE_SCAN",
                observed_at=OBSERVED,
                run_state="SUCCESS",
                coverage_record={
                    "status": "COMPLETE",
                    "pages": 1,
                    "count": 1,
                    "total": 2,
                },
                findings=[common, common],
            )

    def test_repository_identity_rejects_path_and_query_segments(self) -> None:
        for repository in (
            "owner/../repo",
            "owner/repo?tab=issues",
            "owner/repo#fragment",
            "owner/repo%2Fother",
        ):
            with (
                self.subTest(repository=repository),
                self.assertRaises(analyzer_readback.AnalyzerReadbackError),
            ):
                analyzer_readback.normalize_repository(repository)

    def test_build_readback_counts_deduplicated_retained_findings(self) -> None:
        common = {
            "id": "provider-1",
            "message": "same issue",
            "path": "a.py",
        }
        document = analyzer_readback.build_readback(
            provider="synthetic",
            adapter="fixture/v1",
            repository="example/project",
            pull_number=1,
            requested_head=HEAD,
            observed_head=HEAD,
            analysis_id="run",
            scope="FULL",
            completeness="FULL_RUN",
            native_mode="COMPLETE_SCAN",
            observed_at=OBSERVED,
            run_state="SUCCESS",
            coverage_record={
                "status": "COMPLETE",
                "pages": 1,
                "count": 1,
                "total": 1,
            },
            findings=[
                {
                    **common,
                    "provenance": [
                        {"surface": "provider-page-1", "reference": "issue:1"}
                    ],
                },
                {
                    **common,
                    "provenance": [
                        {"surface": "provider-page-2", "reference": "issue:1"}
                    ],
                },
            ],
        )
        self.assertEqual(1, document["coverage"]["count"])
        self.assertEqual(1, document["coverage"]["total"])
        self.assertEqual(1, len(document["findings"]))
        self.assertEqual(
            ["provider-page-1", "provider-page-2"],
            [item["surface"] for item in document["findings"][0]["provenance"]],
        )

    def test_synthetic_third_provider_uses_common_model_without_provider_branch(
        self,
    ) -> None:
        document = analyzer_readback.build_readback(
            provider="synthetic-analyzer",
            adapter="fixture/v1",
            repository="example/project",
            pull_number=9,
            requested_head=HEAD,
            observed_head=HEAD,
            analysis_id="run-9",
            scope="FULL",
            completeness="FULL_RUN",
            native_mode="COMPLETE_SCAN",
            observed_at=OBSERVED,
            run_state="SUCCESS",
            coverage_record=analyzer_readback.coverage(
                "COMPLETE", pages=1, count=1, total=1
            ),
            findings=[{"id": "x", "message": "fixture"}],
        )
        self.assertEqual("synthetic-analyzer", document["provider"])
        source = inspect.getsource(analyzer_readback)
        self.assertNotIn('provider == "deepsource"', source)
        self.assertNotIn('provider == "codacy"', source)

    def test_common_model_retains_provider_scoped_tool_identity(self) -> None:
        document = analyzer_readback.build_readback(
            provider="synthetic-analyzer",
            adapter="fixture/v1",
            repository="example/project",
            pull_number=9,
            requested_head=HEAD,
            observed_head=HEAD,
            analysis_id="run-9",
            scope="FULL",
            completeness="FULL_RUN",
            native_mode="COMPLETE_SCAN",
            observed_at=OBSERVED,
            run_state="SUCCESS",
            coverage_record=analyzer_readback.coverage(
                "COMPLETE", pages=1, count=1, total=1
            ),
            findings=[
                {
                    "id": "finding-1",
                    "message": "fixture",
                    "tool": {"id": "fixture-tool", "name": "Fixture Tool"},
                }
            ],
        )
        self.assertEqual(
            {"id": "fixture-tool", "name": "Fixture Tool"},
            document["findings"][0]["tool"],
        )

    def test_common_model_rejects_unknown_tool_identity_fields(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "finding tool identity has unknown fields",
        ):
            analyzer_readback.build_readback(
                provider="synthetic-analyzer",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=9,
                requested_head=HEAD,
                observed_head=HEAD,
                analysis_id="run-9",
                scope="FULL",
                completeness="FULL_RUN",
                native_mode="COMPLETE_SCAN",
                observed_at=OBSERVED,
                run_state="SUCCESS",
                coverage_record=analyzer_readback.coverage(
                    "COMPLETE", pages=1, count=1, total=1
                ),
                findings=[
                    {
                        "id": "finding-1",
                        "message": "fixture",
                        "tool": {"id": "fixture-tool", "provider": "synthetic"},
                    }
                ],
            )

    def test_full_run_completeness_requires_complete_coverage(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "FULL_RUN requires COMPLETE coverage",
        ):
            analyzer_readback.build_readback(
                provider="synthetic",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=1,
                requested_head=HEAD,
                observed_head=HEAD,
                analysis_id="run",
                scope="FULL",
                completeness="FULL_RUN",
                native_mode="COMPLETE_SCAN",
                observed_at=OBSERVED,
                run_state="SUCCESS",
                coverage_record=analyzer_readback.coverage(
                    "PARTIAL", pages=1, count=0, reason="TRUNCATED"
                ),
                findings=[],
            )

    def test_ambiguous_completeness_requires_incomplete_subject_coverage(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "AMBIGUOUS requires INCOMPLETE coverage",
        ):
            analyzer_readback.build_readback(
                provider="synthetic",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=1,
                requested_head=HEAD,
                observed_head=OTHER_HEAD,
                analysis_id="run",
                scope="FULL",
                completeness="AMBIGUOUS",
                native_mode="COMPLETE_SCAN",
                observed_at=OBSERVED,
                run_state="SUCCESS",
                coverage_record=analyzer_readback.coverage(
                    "ERROR", pages=1, count=0, reason="MISMATCH"
                ),
                findings=[],
            )

    def test_incomplete_coverage_requires_ambiguous_completeness(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "INCOMPLETE coverage requires AMBIGUOUS completeness",
        ):
            analyzer_readback.build_readback(
                provider="synthetic",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=1,
                requested_head=HEAD,
                observed_head=HEAD,
                analysis_id="run",
                scope="DIFF",
                completeness="DIFF_LOCAL",
                native_mode="DIFF_LOCAL",
                observed_at=OBSERVED,
                run_state="UNKNOWN",
                coverage_record=analyzer_readback.coverage(
                    "INCOMPLETE", pages=1, count=0, reason="SUBJECT_UNCERTAIN"
                ),
                findings=[],
            )

    def test_auth_unavailable_completeness_rejects_complete_coverage(self) -> None:
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError,
            "AUTH_UNAVAILABLE requires UNAVAILABLE coverage",
        ):
            analyzer_readback.build_readback(
                provider="synthetic",
                adapter="fixture/v1",
                repository="example/project",
                pull_number=1,
                requested_head=HEAD,
                observed_head=HEAD,
                analysis_id="run",
                scope="FULL",
                completeness="AUTH_UNAVAILABLE",
                native_mode="COMPLETE_SCAN",
                observed_at=OBSERVED,
                run_state="SUCCESS",
                coverage_record=analyzer_readback.coverage(
                    "COMPLETE", pages=1, count=0, total=0
                ),
                findings=[],
            )


class DeepSourceAnalyzerReadbackTests(unittest.TestCase):
    def test_full_run_uses_exact_run_and_complete_issue_pagination(self) -> None:
        client = _DeepSourceFake(
            {
                ("run", None): _run_page(),
                ("check-python", None): _check_page(
                    [_issue("issue-1", 10)], total=2, cursor="next"
                ),
                ("check-python", "next"): _check_page(
                    [_issue("issue-2", 20)], total=2, cursor=None
                ),
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("FULL", document["scope"])
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("FULL_RUN", document["native_mode"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(2, document["coverage"]["count"])
        self.assertEqual(2, document["coverage"]["total"])
        self.assertEqual(3, document["coverage"]["pages"])
        self.assertEqual(
            ["issue-1", "issue-2"], [x["id"] for x in document["findings"]]
        )
        self.assertEqual(
            [{"id": "python"}, {"id": "python"}],
            [x["tool"] for x in document["findings"]],
        )

    def test_full_run_deduplicates_overlapping_check_findings(self) -> None:
        run_page = _run_page()
        run_page["data"]["run"]["checks"]["totalCount"] = 2
        second_check = {
            "id": "check-python-secondary",
            "status": "FAILURE",
            "analyzer": {"shortcode": "python"},
        }
        run_page["data"]["run"]["checks"]["edges"].append({"node": second_check})
        first_page = _check_page([_issue("issue-shared", 10)], total=1, cursor=None)
        second_page = _check_page([_issue("issue-shared", 10)], total=1, cursor=None)
        second_page["data"]["node"]["id"] = "check-python-secondary"
        client = _DeepSourceFake(
            {
                ("run", None): run_page,
                ("check-python", None): first_page,
                ("check-python-secondary", None): second_page,
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(1, document["coverage"]["count"])
        self.assertNotIn("total", document["coverage"])
        self.assertEqual(
            ["issue-shared"], [item["id"] for item in document["findings"]]
        )
        self.assertEqual(2, document["native"]["raw_issue_count"])
        self.assertEqual(2, document["native"]["provider_total"])
        self.assertEqual(
            ["check-python", "check-python-secondary"],
            [item["reference"] for item in document["findings"][0]["provenance"]],
        )

    def test_full_run_accepts_exhausted_relay_pages_without_total_count(self) -> None:
        run_page = _run_page()
        run_page["data"]["run"]["checks"]["totalCount"] = None
        issue_page = _check_page([_issue("issue-1", 10)], total=1, cursor=None)
        issue_page["data"]["node"]["issues"]["totalCount"] = None
        client = _DeepSourceFake(
            {
                ("run", None): run_page,
                ("check-python", None): issue_page,
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(1, document["coverage"]["count"])
        self.assertNotIn("total", document["coverage"])
        self.assertEqual(["issue-1"], [item["id"] for item in document["findings"]])

    def test_full_run_without_analyzer_checks_is_partial(self) -> None:
        run_page = _run_page(run_status="SUCCESS")
        checks = run_page["data"]["run"]["checks"]
        checks["totalCount"] = 0
        checks["edges"] = []
        client = _DeepSourceFake({("run", None): run_page})
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("NO_ANALYZER_CHECKS", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_full_run_pending_analysis_is_not_complete(self) -> None:
        client = _DeepSourceFake(
            {
                ("run", None): _run_page(run_status="PENDING"),
                ("check-python", None): _check_page([], total=0, cursor=None),
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("ANALYSIS_RUN_NOT_COMPLETE", document["coverage"]["reason"])
        self.assertEqual("PENDING", document["run_state"])
        self.assertEqual([], document["findings"])

    def test_full_run_ready_check_is_not_complete(self) -> None:
        client = _DeepSourceFake(
            {
                ("run", None): _run_page(check_status="READY"),
                ("check-python", None): _check_page(
                    [], total=0, cursor=None, status="READY"
                ),
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("ANALYZER_CHECK_NOT_COMPLETE", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_full_run_malformed_check_subject_fails_closed(self) -> None:
        run_page = _run_page()
        del run_page["data"]["run"]["checks"]["edges"][0]["node"]["status"]
        client = _DeepSourceFake({("run", None): run_page})
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)
        self.assertEqual([], document["findings"])

    def test_full_run_rejects_malformed_check_analyzer_without_issues(self) -> None:
        run_page = _run_page(run_status="SUCCESS", check_status="SUCCESS")
        run_page["data"]["run"]["checks"]["edges"][0]["node"]["analyzer"] = None
        client = _DeepSourceFake({("run", None): run_page})

        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )

        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_full_run_rejects_check_metadata_drift_without_issues(self) -> None:
        cases: tuple[tuple[str, dict[str, Any]], ...] = (
            ("missing-analyzer", {"status": "SUCCESS", "analyzer": None}),
            (
                "changed-status",
                {"status": "PENDING", "analyzer": {"shortcode": "python"}},
            ),
        )
        for label, replacement in cases:
            with self.subTest(label=label):
                check_page = _check_page([], total=0, cursor=None, status="SUCCESS")
                check_page["data"]["node"].update(replacement)
                client = _DeepSourceFake(
                    {
                        ("run", None): _run_page(
                            run_status="SUCCESS", check_status="SUCCESS"
                        ),
                        ("check-python", None): check_page,
                    }
                )
                document = analyzer_deepsource.read_full_run(
                    client,
                    repository="ktogias/gnostoa",
                    pull_number=312,
                    requested_head=HEAD,
                    run_uid=RUN_UID,
                    observed_at=OBSERVED,
                )
                self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
                self.assertEqual("ERROR", document["coverage"]["status"])
                self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
                self.assertEqual([], document["findings"])

    def test_full_run_rejects_malformed_suppression_state(self) -> None:
        issue = _issue("issue-bad-suppression", 10)
        issue["isSuppressed"] = "false"
        client = _DeepSourceFake(
            {
                ("run", None): _run_page(),
                ("check-python", None): _check_page([issue], total=1, cursor=None),
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_full_run_malformed_provider_head_fallback_does_not_bind_head(
        self,
    ) -> None:
        client = _DeepSourceFake({("run", None): _run_page(head="short")})
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("NORMALIZATION_ERROR", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)

    def test_full_run_missing_run_is_ambiguous_not_unavailable(self) -> None:
        client = _DeepSourceFake({("run", None): {"data": {"run": None}}})
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)
        self.assertEqual([], document["findings"])

    def test_full_run_rejects_stale_returned_commit(self) -> None:
        client = _DeepSourceFake({("run", None): _run_page(head=OTHER_HEAD)})
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("SUBJECT_MISMATCH", document["coverage"]["reason"])
        self.assertEqual(OTHER_HEAD, document["observed_head"])
        self.assertEqual([], document["findings"])

    def test_second_issue_page_failure_is_not_promoted_to_full_complete(self) -> None:
        client = _DeepSourceFake(
            {
                ("run", None): _run_page(),
                ("check-python", None): _check_page(
                    [_issue("issue-1", 10)], total=2, cursor="next"
                ),
                ("check-python", "next"): analyzer_deepsource.ProviderReadFailure(
                    "UNAVAILABLE", "network unavailable"
                ),
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("UNAVAILABLE", document["coverage"]["status"])
        self.assertEqual("READBACK_UNAVAILABLE", document["coverage"]["reason"])
        self.assertEqual(1, document["coverage"]["count"])
        self.assertEqual("FULL_RUN", document["native_mode"])

    def test_github_native_projection_rejects_stale_status_subject(self) -> None:
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=OTHER_HEAD,
            statuses=[],
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("SUBJECT_MISMATCH", document["coverage"]["reason"])
        self.assertEqual(OTHER_HEAD, document["observed_head"])

    def test_github_native_projection_remains_diff_local(self) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "failure",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            }
        ]
        comments = [
            {
                "body": (
                    "<!-- DeepSource: id=Q2hlY2tJc3N1ZTp0ZXN0 -->\n"
                    "<h3><picture></picture>Function is missing a return type annotation</h3>\n"
                    "severity_major.svg category_typecheck.svg"
                ),
                "path": "tools/example.py",
                "line": 7,
                "commit_id": HEAD,
                "original_commit_id": HEAD,
                "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_r1",
                "author_login": "deepsource-io[bot]",
                "author_type": "Bot",
            }
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=comments,
            observed_at=OBSERVED,
        )
        self.assertEqual("DIFF", document["scope"])
        self.assertEqual("DIFF_LOCAL", document["completeness"])
        self.assertEqual("DIFF_LOCAL", document["native_mode"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(RUN_UID, document["analysis_id"])
        self.assertEqual("TYPECHECK", document["findings"][0]["category"])
        self.assertEqual("MAJOR", document["findings"][0]["severity"])

    def test_github_native_projection_keeps_latest_status_per_analyzer(self) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            },
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "pending",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("SUCCESS", document["run_state"])
        self.assertEqual({"python": "success"}, document["native"]["analyzers"])

    def test_github_native_projection_excludes_stale_inline_comments(self) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            }
        ]
        comments = [
            {
                "body": "<!-- DeepSource: id=stale -->\n<h3>Stale issue</h3>",
                "path": "tools/old.py",
                "line": 3,
                "commit_id": OTHER_HEAD,
                "original_commit_id": OTHER_HEAD,
                "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_stale",
                "author_login": "deepsource-io[bot]",
                "author_type": "Bot",
            }
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=comments,
            observed_at=OBSERVED,
        )
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual([], document["findings"])

    def test_github_native_projection_excludes_comment_retargeted_from_old_head(
        self,
    ) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            }
        ]
        comments = [
            {
                "body": "<!-- DeepSource: id=stale-retargeted -->\n<h3>Old issue</h3>",
                "path": "tools/old.py",
                "line": 3,
                "commit_id": HEAD,
                "original_commit_id": OTHER_HEAD,
                "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_retargeted",
                "author_login": "deepsource-io[bot]",
                "author_type": "Bot",
            }
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=comments,
            observed_at=OBSERVED,
        )
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual(
            "CARRIED_FORWARD_COMMENTS_EXCLUDED",
            document["coverage"]["reason"],
        )
        self.assertEqual(1, document["native"]["carried_forward_comments_excluded"])
        self.assertEqual([], document["findings"])

    def test_github_native_projection_rejects_spoofed_run_status_producer(self) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
                "source_kind": "commit_status",
                "creator_login": "attacker",
                "creator_type": "User",
            }
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])
        self.assertNotIn("analysis_id", document)

    def test_github_native_projection_rejects_spoofed_inline_comment_producer(
        self,
    ) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
            }
        ]
        comments = [
            {
                "body": (
                    "<!-- DeepSource: id=spoofed -->\n"
                    "<h3><picture></picture>Forged DeepSource finding</h3>"
                ),
                "path": "tools/example.py",
                "line": 7,
                "commit_id": HEAD,
                "original_commit_id": HEAD,
                "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_spoofed",
                "author_login": "attacker",
                "author_type": "User",
            }
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=comments,
            observed_at=OBSERVED,
        )
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual([], document["findings"])

    def test_diff_local_malformed_observed_head_fallback_does_not_bind_head(
        self,
    ) -> None:
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head="short",
            statuses=[],
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("NORMALIZATION_ERROR", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)

    def test_diff_local_normalization_error_preserves_unique_run_association(
        self,
    ) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            }
        ]
        comments = [
            {
                "body": "<!-- DeepSource: id=conflict -->\n<h3>First title</h3>",
                "path": "tools/example.py",
                "line": 7,
                "commit_id": HEAD,
                "original_commit_id": HEAD,
                "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_1",
                "author_login": "deepsource-io[bot]",
                "author_type": "Bot",
            },
            {
                "body": "<!-- DeepSource: id=conflict -->\n<h3>Different title</h3>",
                "path": "tools/other.py",
                "line": 7,
                "commit_id": HEAD,
                "original_commit_id": HEAD,
                "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_2",
                "author_login": "deepsource-io[bot]",
                "author_type": "Bot",
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=comments,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("NORMALIZATION_ERROR", document["coverage"]["reason"])
        self.assertEqual(RUN_UID, document["analysis_id"])

    def test_newest_github_run_status_wins_for_same_analyzer(self) -> None:
        older_run = "11111111-1111-1111-1111-111111111111"
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            },
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "failure",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{older_run}/python/"
                ),
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("DIFF_LOCAL", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(RUN_UID, document["analysis_id"])
        self.assertEqual("SUCCESS", document["run_state"])

    def test_unbound_newest_commit_status_does_not_fall_back_to_older_run(
        self,
    ) -> None:
        older_run = "11111111-1111-1111-1111-111111111111"
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "pending",
                "target_url": None,
            },
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{older_run}/python/"
                ),
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])
        self.assertNotIn("analysis_id", document)

    def test_commit_status_and_check_run_disagreement_is_ambiguous(self) -> None:
        check_run = "11111111-1111-1111-1111-111111111111"
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            },
            {
                "context": "DeepSource: Python",
                "source_kind": "check_run",
                "app_slug": "deepsource-io",
                "state": "failure",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{check_run}/python/"
                ),
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])
        self.assertNotIn("analysis_id", document)

    def test_multiple_check_run_ids_for_same_analyzer_are_ambiguous(self) -> None:
        other_run = "22222222-2222-2222-2222-222222222222"
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "check_run",
                "app_slug": "deepsource-io",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            },
            {
                "context": "DeepSource: Python",
                "source_kind": "check_run",
                "app_slug": "deepsource-io",
                "state": "failure",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{other_run}/python/"
                ),
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])
        self.assertNotIn("analysis_id", document)

    def test_multiple_latest_github_run_ids_across_analyzers_are_ambiguous(
        self,
    ) -> None:
        other_run = "11111111-1111-1111-1111-111111111111"
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            },
            {
                "context": "DeepSource: JavaScript",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "success",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{other_run}/javascript/"
                ),
            },
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", document["coverage"]["reason"])

    def test_pending_or_error_github_analyzer_state_is_partial(self) -> None:
        for state, run_state in (("pending", "PENDING"), ("error", "FAILURE")):
            with self.subTest(state=state):
                statuses = [
                    {
                        "context": "DeepSource: Python",
                        "source_kind": "commit_status",
                        "creator_login": "deepsource-io[bot]",
                        "creator_type": "Bot",
                        "state": state,
                        "target_url": (
                            "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                            f"{RUN_UID}/python/"
                        ),
                    }
                ]
                document = analyzer_deepsource.diff_local_from_github(
                    repository="ktogias/gnostoa",
                    pull_number=312,
                    requested_head=HEAD,
                    observed_head=HEAD,
                    statuses=statuses,
                    comments=[],
                    observed_at=OBSERVED,
                )
                self.assertEqual("DIFF_LOCAL", document["completeness"])
                self.assertEqual("PARTIAL", document["coverage"]["status"])
                self.assertEqual(
                    "ANALYZER_STATE_UNAVAILABLE", document["coverage"]["reason"]
                )
                self.assertEqual(run_state, document["run_state"])
                self.assertEqual([], document["findings"])

    def test_unknown_github_analyzer_state_is_partial_not_success(self) -> None:
        statuses = [
            {
                "context": "DeepSource: Python",
                "source_kind": "commit_status",
                "creator_login": "deepsource-io[bot]",
                "creator_type": "Bot",
                "state": "neutral",
                "target_url": (
                    "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                    f"{RUN_UID}/python/"
                ),
            }
        ]
        document = analyzer_deepsource.diff_local_from_github(
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_head=HEAD,
            statuses=statuses,
            comments=[],
            observed_at=OBSERVED,
        )
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("ANALYZER_STATE_UNAVAILABLE", document["coverage"]["reason"])
        self.assertEqual("UNKNOWN", document["run_state"])

    def test_deepsource_api_url_rejects_non_default_and_malformed_ports(self) -> None:
        for url in (
            "https://api.deepsource.com:8443/graphql/",
            "https://api.deepsource.com:not-a-port/graphql/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(analyzer_deepsource.ProviderReadFailure):
                    analyzer_deepsource._validate_api_url(url)

    def test_deepsource_redirect_reauthenticates_only_same_origin(self) -> None:
        handler = analyzer_deepsource._DeepSourceRedirectHandler()
        request = urllib.request.Request("https://api.deepsource.com/graphql/")
        request.add_unredirected_header("Authorization", "Bearer secret-value")
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://api.deepsource.com/graphql/?page=2",
        )
        if redirected is None:
            self.fail("same-origin redirect was unexpectedly refused")
        self.assertEqual("Bearer secret-value", redirected.get_header("Authorization"))

    def test_deepsource_redirect_cannot_leak_authorization_off_origin(self) -> None:
        handler = analyzer_deepsource._DeepSourceRedirectHandler()
        request = urllib.request.Request("https://api.deepsource.com/graphql/")
        request.add_unredirected_header("Authorization", "Bearer secret-value")
        with self.assertRaises(analyzer_deepsource.ProviderReadFailure):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://example.invalid/steal",
            )

    def test_deepsource_missing_token_is_explicit_and_secret_never_serializes(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            analyzer_deepsource.ProviderReadFailure,
            "authentication unavailable",
        ) as raised:
            analyzer_deepsource.DeepSourceGraphQLClient("")
        self.assertNotIn("token", str(raised.exception).lower())


class PaginationProgressTests(unittest.TestCase):
    def test_deepsource_check_cursor_must_advance(self) -> None:
        page = _run_page(cursor="same")
        client = _DeepSourceFake({("run", None): page, ("run", "same"): page})
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual(2, len(client.calls))

    def test_deepsource_issue_cursor_must_advance(self) -> None:
        page = _check_page([], total=0, cursor="same")
        client = _DeepSourceFake(
            {
                ("run", None): _run_page(),
                ("check-python", None): page,
                ("check-python", "same"): page,
            }
        )
        document = analyzer_deepsource.read_full_run(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual(3, len(client.calls))

    def test_codacy_issue_cursor_must_advance(self) -> None:
        page = {"analyzed": True, "data": [], "pagination": {"cursor": "same"}}
        client = _CodacyFake(
            {
                f"{_codacy_root()}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): page,
                _codacy_issues_url(potential=False, cursor="same"): page,
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual(3, len(client.calls))


class CodacyAnalyzerReadbackTests(unittest.TestCase):
    def test_codacy_exact_head_and_cursor_pagination_are_complete(self) -> None:
        root = _codacy_root()
        confirmed_first = _codacy_issues_url(potential=False)
        confirmed_second = _codacy_issues_url(potential=False, cursor="next")
        potential = _codacy_issues_url(potential=True)
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                confirmed_first: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-1", 4)],
                    "pagination": {"cursor": "next", "limit": 1000, "total": 2},
                },
                confirmed_second: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-2", 8)],
                    "pagination": {"limit": 1000, "total": 2},
                },
                potential: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-p1", 12)],
                    "pagination": {"limit": 1000, "total": 1},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(3, document["coverage"]["count"])
        self.assertEqual(5, document["coverage"]["pages"])
        self.assertEqual(
            ["codacy-1", "codacy-2", "codacy-p1"],
            [x["id"] for x in document["findings"]],
        )
        self.assertIn(confirmed_first, client.calls)
        self.assertIn(potential, client.calls)
        potential_finding = next(
            item for item in document["findings"] if item["id"] == "codacy-p1"
        )
        self.assertTrue(potential_finding["native"]["potential"])

    def test_codacy_current_api_origin_and_native_issue_identities_are_retained(
        self,
    ) -> None:
        root = _codacy_root()
        self.assertTrue(root.startswith("https://app.codacy.com/api/v3/"))
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): {
                    "analyzed": True,
                    "data": [_codacy_issue("issue-uuid-1", 4)],
                    "pagination": {"total": 1},
                },
                _codacy_issues_url(potential=True): {
                    "analyzed": True,
                    "data": [],
                    "pagination": {"total": 0},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual(len(client.calls), document["coverage"]["pages"])
        finding = document["findings"][0]
        self.assertEqual("issue-uuid-1", finding["id"])
        self.assertEqual("issue-uuid-1", finding["native"]["issue_id"])
        self.assertEqual(400, finding["native"]["result_data_id"])
        self.assertEqual("Ruff", finding["native"]["tool_name"])
        self.assertEqual("ruff-tool", finding["native"]["tool_uuid"])
        self.assertEqual(
            {"id": "ruff-tool", "name": "Ruff"},
            finding["tool"],
        )

    def test_codacy_overlapping_potential_surface_collapses_by_native_id(self) -> None:
        root = _codacy_root()
        issue = _codacy_issue("codacy-potential", 14)
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): {
                    "analyzed": True,
                    "data": [issue],
                    "pagination": {"total": 1},
                },
                _codacy_issues_url(potential=True): {
                    "analyzed": True,
                    "data": [issue],
                    "pagination": {"total": 1},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(1, document["coverage"]["count"])
        self.assertEqual(1, len(document["findings"]))
        self.assertTrue(document["findings"][0]["native"]["potential"])
        self.assertEqual(
            {"all": 1, "potential": 1},
            document["native"]["issue_surface_totals"],
        )

    def test_codacy_conflicting_duplicate_identity_fails_closed(self) -> None:
        root = _codacy_root()
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): {
                    "analyzed": True,
                    "data": [_codacy_issue("same-id", 14)],
                    "pagination": {"total": 1},
                },
                _codacy_issues_url(potential=True): {
                    "analyzed": True,
                    "data": [_codacy_issue("same-id", 15)],
                    "pagination": {"total": 1},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("NORMALIZATION_ERROR", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)
        self.assertEqual([], document["findings"])

    def test_codacy_malformed_provider_head_fallback_does_not_bind_head(self) -> None:
        root = _codacy_root()
        client = _CodacyFake({f"{root}/pull-requests/312": _codacy_pr(head="short")})
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("NORMALIZATION_ERROR", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)
        self.assertEqual([], document["findings"])

    def test_codacy_rejects_malformed_delta_type(self) -> None:
        root = _codacy_root()
        issue = _codacy_issue("codacy-bad-delta", 4)
        issue["deltaType"] = {"unexpected": True}
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): {
                    "analyzed": True,
                    "data": [issue],
                    "pagination": {"total": 1},
                },
                _codacy_issues_url(potential=True): {
                    "analyzed": True,
                    "data": [],
                    "pagination": {"total": 0},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_codacy_single_page_without_pagination_is_complete(self) -> None:
        root = _codacy_root()
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): {
                    "analyzed": True,
                    "data": [],
                },
                _codacy_issues_url(potential=True): {
                    "analyzed": True,
                    "data": [],
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("FULL_RUN", document["completeness"])
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertEqual(0, document["coverage"]["count"])

    def test_codacy_cursor_exhaustion_can_establish_completeness_without_total(
        self,
    ) -> None:
        root = _codacy_root()
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                _codacy_issues_url(potential=False): {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-1", 4)],
                    "pagination": {},
                },
                _codacy_issues_url(potential=True): {
                    "analyzed": True,
                    "data": [],
                    "pagination": {},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("COMPLETE", document["coverage"]["status"])
        self.assertNotIn("total", document["coverage"])
        self.assertEqual(["codacy-1"], [item["id"] for item in document["findings"]])

    def test_codacy_head_change_during_readback_discards_unbound_findings(self) -> None:
        root = _codacy_root()
        confirmed = _codacy_issues_url(potential=False)
        potential = _codacy_issues_url(potential=True)
        pr_url = f"{root}/pull-requests/312"
        client = _CodacyFake(
            {
                pr_url: [_codacy_pr(), _codacy_pr(OTHER_HEAD)],
                confirmed: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-1", 4)],
                    "pagination": {"limit": 1000, "total": 1},
                },
                potential: {
                    "analyzed": True,
                    "data": [],
                    "pagination": {"limit": 1000, "total": 0},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual(
            "SUBJECT_CHANGED_DURING_READBACK", document["coverage"]["reason"]
        )
        self.assertEqual(OTHER_HEAD, document["observed_head"])
        self.assertEqual([], document["findings"])

    def test_codacy_missing_git_href_fails_closed(self) -> None:
        root = _codacy_root()
        pr = _codacy_pr()
        del pr["pullRequest"]["gitHref"]
        client = _CodacyFake({f"{root}/pull-requests/312": pr})
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("PROVIDER_ERROR", document["coverage"]["reason"])
        self.assertNotIn("observed_head", document)
        self.assertEqual([], document["findings"])

    def test_codacy_stale_pr_head_is_incomplete_without_guessing_findings(self) -> None:
        root = _codacy_root()
        client = _CodacyFake({f"{root}/pull-requests/312": _codacy_pr(OTHER_HEAD)})
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("AMBIGUOUS", document["completeness"])
        self.assertEqual("INCOMPLETE", document["coverage"]["status"])
        self.assertEqual("SUBJECT_MISMATCH", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_codacy_unanalyzed_latest_commit_is_partial_not_clean(self) -> None:
        root = _codacy_root()
        confirmed = _codacy_issues_url(potential=False)
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                confirmed: {
                    "analyzed": False,
                    "data": [],
                    "pagination": {"total": 0},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("LATEST_COMMIT_NOT_ANALYZED", document["coverage"]["reason"])

    def test_codacy_analysis_starting_during_readback_is_partial(self) -> None:
        root = _codacy_root()
        confirmed = _codacy_issues_url(potential=False)
        potential = _codacy_issues_url(potential=True)
        pr_url = f"{root}/pull-requests/312"
        final_pr = _codacy_pr()
        final_pr["isAnalysing"] = True
        client = _CodacyFake(
            {
                pr_url: [_codacy_pr(), final_pr],
                confirmed: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-1", 4)],
                    "pagination": {"limit": 1000, "total": 1},
                },
                potential: {
                    "analyzed": True,
                    "data": [],
                    "pagination": {"limit": 1000, "total": 0},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("ANALYSIS_IN_PROGRESS", document["coverage"]["reason"])
        self.assertEqual(1, document["coverage"]["count"])

    def test_codacy_analysis_active_at_start_is_partial_even_if_it_finishes(
        self,
    ) -> None:
        root = _codacy_root()
        confirmed = _codacy_issues_url(potential=False)
        potential = _codacy_issues_url(potential=True)
        pr_url = f"{root}/pull-requests/312"
        initial_pr = _codacy_pr()
        initial_pr["isAnalysing"] = True
        client = _CodacyFake(
            {
                pr_url: [initial_pr, _codacy_pr()],
                confirmed: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-1", 4)],
                    "pagination": {"limit": 1000, "total": 1},
                },
                potential: {
                    "analyzed": True,
                    "data": [],
                    "pagination": {"limit": 1000, "total": 0},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("PARTIAL", document["coverage"]["status"])
        self.assertEqual("ANALYSIS_IN_PROGRESS", document["coverage"]["reason"])
        self.assertEqual(1, document["coverage"]["count"])

    def test_codacy_total_mismatch_is_explicit_error(self) -> None:
        root = _codacy_root()
        confirmed = _codacy_issues_url(potential=False)
        client = _CodacyFake(
            {
                f"{root}/pull-requests/312": _codacy_pr(),
                confirmed: {
                    "analyzed": True,
                    "data": [_codacy_issue("codacy-1", 4)],
                    "pagination": {"limit": 1000, "total": 2},
                },
            }
        )
        document = analyzer_codacy.read_pull_request(
            client,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            observed_at=OBSERVED,
        )
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("COUNT_TOTAL_MISMATCH", document["coverage"]["reason"])
        self.assertEqual(1, document["coverage"]["count"])

    def test_codacy_api_url_rejects_non_default_and_malformed_ports(self) -> None:
        for url in (
            "https://api.codacy.com/api/v3/user",
            "https://app.codacy.com:8443/api/v3/user",
            "https://app.codacy.com:not-a-port/api/v3/user",
        ):
            with self.subTest(url=url):
                with self.assertRaises(analyzer_codacy.ProviderReadFailure):
                    analyzer_codacy._validate_api_url(url)

    def test_codacy_redirect_reauthenticates_only_same_origin(self) -> None:
        handler = analyzer_codacy._CodacyRedirectHandler()
        request = urllib.request.Request("https://app.codacy.com/api/v3/user")
        request.add_unredirected_header("api-token", "secret-value")
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://app.codacy.com/api/v3/user?cursor=next",
        )
        if redirected is None:
            self.fail("same-origin redirect was unexpectedly refused")
        self.assertEqual("secret-value", redirected.get_header("Api-token"))

    def test_codacy_redirect_cannot_leak_token_off_origin(self) -> None:
        handler = analyzer_codacy._CodacyRedirectHandler()
        request = urllib.request.Request("https://app.codacy.com/api/v3/user")
        request.add_unredirected_header("api-token", "secret-value")
        with self.assertRaises(analyzer_codacy.ProviderReadFailure):
            handler.redirect_request(
                request,
                None,
                302,
                "Found",
                {},
                "https://example.invalid/steal",
            )

    def test_codacy_missing_token_is_explicit_and_not_echoed(self) -> None:
        with self.assertRaisesRegex(
            analyzer_codacy.ProviderReadFailure,
            "authentication unavailable",
        ) as raised:
            analyzer_codacy.CodacyRestClient("")
        self.assertNotIn("api-token", str(raised.exception).lower())

    def test_provider_clients_map_http_protocol_failures_to_unavailable(self) -> None:
        class _IncompleteReadOpener:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise http.client.IncompleteRead(b"")

        deep = analyzer_deepsource.DeepSourceGraphQLClient("test-token")
        deep._opener = _IncompleteReadOpener()  # type: ignore[assignment]
        with self.assertRaises(analyzer_deepsource.ProviderReadFailure) as deep_error:
            deep.graphql(
                analyzer_deepsource._RUN_QUERY,
                {"runUid": RUN_UID, "cursor": None},
            )
        self.assertEqual("UNAVAILABLE", deep_error.exception.kind)

        codacy = analyzer_codacy.CodacyRestClient("test-token")
        codacy._opener = _IncompleteReadOpener()  # type: ignore[assignment]
        with self.assertRaises(analyzer_codacy.ProviderReadFailure) as codacy_error:
            codacy.get("https://app.codacy.com/api/v3/user")
        self.assertEqual("UNAVAILABLE", codacy_error.exception.kind)

    def test_adapters_expose_no_provider_mutation_methods(self) -> None:
        for cls in (
            analyzer_codacy.CodacyRestClient,
            analyzer_deepsource.DeepSourceGraphQLClient,
        ):
            public = {
                name
                for name, _ in inspect.getmembers(cls, inspect.isfunction)
                if not name.startswith("_")
            }
            self.assertTrue(public <= {"get", "graphql", "from_environment"})
            self.assertFalse(
                public & {"post", "patch", "delete", "trigger", "ignore", "autofix"}
            )

    def test_live_deepsource_client_rejects_unadmitted_graphql_operation(self) -> None:
        client = analyzer_deepsource.DeepSourceGraphQLClient("test-token")

        class _FailOpener:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise AssertionError(
                    "network must not be reached for an unadmitted query"
                )

        client._opener = _FailOpener()  # type: ignore[assignment]
        with self.assertRaisesRegex(
            analyzer_deepsource.ProviderReadFailure,
            "unsupported GraphQL read operation",
        ):
            client.graphql(
                'mutation Dangerous { dismissIssue(id: "1") { id } }',
                {},
            )

    def test_token_shaped_values_do_not_enter_normalized_evidence(self) -> None:
        sentinel = "opaque-provider-fixture-value"
        client = analyzer_deepsource.DeepSourceGraphQLClient(sentinel)

        class _HttpErrorOpener:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise urllib.error.HTTPError(
                    "https://api.deepsource.com/graphql/",
                    500,
                    "provider failure",
                    {},
                    io.BytesIO(sentinel.encode("utf-8")),
                )

        client._opener = _HttpErrorOpener()  # type: ignore[assignment]
        with self.assertRaises(analyzer_deepsource.ProviderReadFailure) as raised:
            client.graphql(
                analyzer_deepsource._RUN_QUERY,
                {"runUid": RUN_UID, "cursor": None},
            )
        self.assertNotIn(sentinel, str(raised.exception))

        document = analyzer_deepsource.read_full_run(
            client,
            repository="example/project",
            pull_number=1,
            requested_head=HEAD,
            run_uid=RUN_UID,
            observed_at=OBSERVED,
        )
        serialized = analyzer_readback.canonical_json(document)
        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("UNAVAILABLE", document["coverage"]["status"])
        self.assertNotIn(sentinel, serialized)
        self.assertNotIn("DEEPSOURCE_API_TOKEN", json.dumps(document))
        self.assertNotIn("CODACY_API_TOKEN", json.dumps(document))


# #389 F3 R0: the capability discovery, relocated from the RED module
# test_analyzer_deepsource_capability.py (#389 6267244226, fence 992192d7...) as the
# Router chose (6267325366).
REPOSITORY = "ktogias/gnostoa"
_KINDS = ("RepositoryAnalyzers", "RepositoryIgnoreRules", "AnalyzerCatalogue")
_QUERIES = (
    "_REPOSITORY_ANALYZERS_QUERY",
    "_REPOSITORY_IGNORE_RULES_QUERY",
    "_ANALYZER_CATALOGUE_QUERY",
)


class CapabilityFake:
    """Answers the three discovery queries by (kind, key, cursor). A list value is
    consumed one call at a time, so a second pass can see a changed state; an
    exception value is raised."""

    def __init__(self, responses: Mapping[tuple[str, str, str | None], Any]) -> None:
        self.responses = {
            k: (list(v) if isinstance(v, list) else v) for k, v in responses.items()
        }
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.deadlines: list[float | None] = []
        # A clock to move per answer, so a request can take time (Router 6267325366).
        self.clock: list[float] | None = None
        self.cost = 0.0

    def graphql(
        self,
        query: str,
        variables: Mapping[str, Any],
        *,
        deadline: float | None = None,
    ) -> Mapping[str, Any]:
        values = dict(variables)
        # As the real client refuses an unadmitted query, the fake refuses one it does
        # not answer, by name (Amazon Q on #441).
        kind = next((k for k in _KINDS if k in query), None)
        if kind is None:
            raise AssertionError(f"the fake answers no such query: {query[:60]!r}")
        if kind != "AnalyzerCatalogue" and values.get("login") != "ktogias":
            # A reader asking for another account gets no answer (Cubic on #441).
            raise AssertionError(f"the fake answers no account {values.get('login')!r}")
        self.calls.append((kind, values))
        self.deadlines.append(deadline)
        if self.clock is not None:
            self.clock[0] += self.cost
        key = (
            values.get("shortcode")
            if kind == "AnalyzerCatalogue"
            else values.get("name")
        )
        answer = self.responses[(kind, str(key), values.get("cursor"))]
        if isinstance(answer, list):
            # One answer per request: a read that asks more than the test gave fails
            # (Amazon Q on #441), never silently reusing the last.
            if not answer:
                raise AssertionError(f"the fake has no more answers for {kind} {key!r}")
            answer = answer.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer


def _connection(
    nodes: list[dict[str, Any]], total: int | None, has_next: bool, cursor: str | None
) -> dict[str, Any]:
    return {
        "totalCount": total,
        "edges": [{"node": node} for node in nodes],
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
    }


def analyzers_page(
    analyzers: list[dict[str, Any]] | None = None,
    *,
    total: int | None = None,
    has_next: bool = False,
    cursor: str | None = None,
    config: Any = None,
    name: str = "gnostoa",
    login: str = "ktogias",
) -> dict[str, Any]:
    nodes = [analyzer()] if analyzers is None else analyzers
    return {
        "data": {
            "repository": {
                "name": name,
                "isActivated": True,
                "configJson": {"version": 1, "analyzers": [{"name": "python"}]}
                if config is None
                else config,
                "account": {"login": login, "vcsProvider": "GITHUB"},
                "enabledAnalyzers": _connection(
                    nodes, len(nodes) if total is None else total, has_next, cursor
                ),
            }
        }
    }


def ignore_page(
    rules: list[dict[str, Any]] | None = None,
    *,
    total: int | None = None,
    has_next: bool = False,
    cursor: str | None = None,
    name: str = "gnostoa",
) -> dict[str, Any]:
    nodes = [] if rules is None else rules
    return {
        "data": {
            "repository": {
                "name": name,
                "account": {"login": "ktogias", "vcsProvider": "GITHUB"},
                "ignoreRules": _connection(
                    nodes, len(nodes) if total is None else total, has_next, cursor
                ),
            }
        }
    }


def catalogue_page(
    issues: list[dict[str, Any]],
    *,
    shortcode: str = "python",
    version: str | None = "1.0.0",
    num_issues: int | None = None,
    total: int | None = None,
    has_next: bool = False,
    cursor: str | None = None,
) -> dict[str, Any]:
    return {
        "data": {
            "analyzer": {
                "shortcode": shortcode,
                "version": version,
                "numIssues": len(issues) if num_issues is None else num_issues,
                "issues": _connection(
                    issues, len(issues) if total is None else total, has_next, cursor
                ),
            }
        }
    }


def analyzer(
    shortcode: str = "python", version: str | None = "1.0.0", num_issues: int = 3
) -> dict[str, Any]:
    return {"shortcode": shortcode, "version": version, "numIssues": num_issues}


def catalogue_issue(shortcode: str) -> dict[str, Any]:
    return {
        "shortcode": shortcode,
        "title": f"Issue {shortcode}",
        "category": "BUG_RISK",
        "severity": "MAJOR",
        "isRecommended": True,
        "tags": ["python"],
    }


def ignore_rule(identifier: str, issue: str = "PYL-W0212") -> dict[str, Any]:
    return {
        "id": identifier,
        "level": "REPOSITORY",
        "type": "FOREVER",
        "filePath": None,
        "globPattern": None,
        "issue": {"shortcode": issue},
    }


def stable(
    overrides: Mapping[tuple[str, str, str | None], Any] | None = None,
) -> dict[tuple[str, str, str | None], Any]:
    """One analyzer with a three-issue catalogue over two pages and one ignore rule,
    the same on both passes."""
    responses: dict[tuple[str, str, str | None], Any] = {
        ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(),
        ("RepositoryIgnoreRules", "gnostoa", None): ignore_page(
            [ignore_rule("rule-1")]
        ),
        ("AnalyzerCatalogue", "python", None): catalogue_page(
            [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
            num_issues=3,
            total=3,
            has_next=True,
            cursor="c1",
        ),
        ("AnalyzerCatalogue", "python", "c1"): catalogue_page(
            [catalogue_issue("PTC-W0063")], num_issues=3, total=3
        ),
    }
    responses.update(overrides or {})
    return responses


class DeepSourceCapabilityDiscoveryTests(unittest.TestCase):
    """#389 F3 R0: the capability discovery (Router 6266752276, 6267131349 and
    6267325366; PAO 6267150750). It is CURRENT_NOT_RUN_BOUND, never a past run's
    capability, and its effective configuration stays UNPROVEN."""

    def _read(self, fake: CapabilityFake, **kwargs: Any) -> dict[str, Any]:
        reader = getattr(analyzer_deepsource, "read_capability_discovery", None)
        if reader is None:
            self.fail("no capability discovery read exists in analyzer_deepsource")
        result: dict[str, Any] = reader(fake, REPOSITORY, **kwargs)
        return result

    def test_the_three_queries_are_admitted_read_only_literals(self) -> None:
        for name in _QUERIES:
            with self.subTest(query=name):
                query = getattr(analyzer_deepsource, name, None)
                self.assertIsInstance(query, str, f"{name} is not defined")
                self.assertIn(query, analyzer_deepsource._ADMITTED_GRAPHQL_READ_QUERIES)
                self.assertTrue(query.lstrip().startswith("query "))
                self.assertNotIn("mutation", query)
                # Exact-literal admission: a variant is still refused.
                client = analyzer_deepsource.DeepSourceGraphQLClient("test-token")
                with self.assertRaisesRegex(
                    analyzer_deepsource.ProviderReadFailure,
                    "unsupported GraphQL read operation",
                ):
                    client.graphql(query + " ", {})

    def test_a_stable_complete_read(self) -> None:
        fake = CapabilityFake(stable())
        receipt = self._read(fake)
        self.assertEqual(
            {
                "schema",
                "binding",
                "repository",
                "observed_at",
                "coverage",
                "configuration",
                "analyzers",
                "ignore_rules",
                "activated",
                "enabled_analyzers",
                "catalogue_partial",
                "effective_configuration",
                "unknown",
            },
            set(receipt),
        )
        self.assertEqual("CURRENT_NOT_RUN_BOUND", receipt["binding"])
        self.assertEqual("UNPROVEN", receipt["effective_configuration"])
        self.assertTrue(receipt["unknown"])
        self.assertEqual("COMPLETE", receipt["coverage"]["status"])
        self.assertEqual(REPOSITORY, receipt["repository"])
        [entry] = receipt["analyzers"]
        self.assertEqual(
            ("python", "1.0.0", 3),
            (entry["shortcode"], entry["version"], entry["num_issues"]),
        )
        self.assertEqual(
            ["PTC-W0063", "PYL-W0212", "TYP-050"],
            sorted(issue["shortcode"] for issue in entry["catalogue"]),
        )
        self.assertEqual(["rule-1"], [rule["id"] for rule in receipt["ignore_rules"]])
        config = {"version": 1, "analyzers": [{"name": "python"}]}
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual("PRESENT", receipt["configuration"]["state"])
        self.assertEqual(
            "sha256:" + hashlib.sha256(canonical).hexdigest(),
            receipt["configuration"]["digest"],
        )
        # The repository state is read twice: before and after the catalogues.
        kinds = [kind for kind, _ in fake.calls]
        self.assertEqual(2, kinds.count("RepositoryAnalyzers"))
        self.assertEqual(2, kinds.count("RepositoryIgnoreRules"))
        self.assertGreater(
            max(i for i, k in enumerate(kinds) if k == "RepositoryAnalyzers"),
            max(i for i, k in enumerate(kinds) if k == "AnalyzerCatalogue"),
        )

    def test_an_absent_configuration_is_never_an_empty_one(self) -> None:
        page = analyzers_page()
        page["data"]["repository"]["configJson"] = None
        receipt = self._read(
            CapabilityFake(stable({("RepositoryAnalyzers", "gnostoa", None): page}))
        )
        self.assertEqual({"state": "ABSENT"}, receipt["configuration"])
        self.assertEqual("UNPROVEN", receipt["effective_configuration"])

    def test_a_short_or_mismatched_catalogue_is_incomplete(self) -> None:
        cases = {
            "fewer collected than totalCount": catalogue_page(
                [catalogue_issue("PTC-W0063")], num_issues=3, total=4
            ),
            "numIssues disagrees with totalCount": catalogue_page(
                [catalogue_issue("PTC-W0063")], num_issues=5, total=3
            ),
        }
        for label, last in cases.items():
            with self.subTest(case=label):
                responses = stable({("AnalyzerCatalogue", "python", "c1"): last})
                if label == "fewer collected than totalCount":
                    responses[("AnalyzerCatalogue", "python", None)] = catalogue_page(
                        [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
                        num_issues=3,
                        total=4,
                        has_next=True,
                        cursor="c1",
                    )
                receipt = self._read(CapabilityFake(responses))
                self.assertNotEqual("COMPLETE", receipt["coverage"]["status"])

    def test_a_missing_total_is_incomplete(self) -> None:
        page = catalogue_page([catalogue_issue("PTC-W0063")], num_issues=3)
        page["data"]["analyzer"]["issues"]["totalCount"] = None
        first = catalogue_page(
            [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
            num_issues=3,
            has_next=True,
            cursor="c1",
        )
        first["data"]["analyzer"]["issues"]["totalCount"] = None
        receipt = self._read(
            CapabilityFake(
                stable(
                    {
                        ("AnalyzerCatalogue", "python", None): first,
                        ("AnalyzerCatalogue", "python", "c1"): page,
                    }
                )
            )
        )
        self.assertEqual("INCOMPLETE", receipt["coverage"]["status"])

    def test_an_analyzer_version_change_within_the_catalogue_is_refused(self) -> None:
        last = catalogue_page(
            [catalogue_issue("PTC-W0063")], version="1.0.1", num_issues=3, total=3
        )
        receipt = self._read(
            CapabilityFake(stable({("AnalyzerCatalogue", "python", "c1"): last}))
        )
        self.assertNotEqual("COMPLETE", receipt["coverage"]["status"])

    def test_a_changed_enabled_analyzer_set_on_the_second_pass_is_incomplete(
        self,
    ) -> None:
        # PAO R0-SNAP-01: version and configJson stay the same.
        second = analyzers_page([analyzer(), analyzer("shell", num_issues=0)])
        receipt = self._read(
            CapabilityFake(
                stable(
                    {
                        ("RepositoryAnalyzers", "gnostoa", None): [
                            analyzers_page(),
                            second,
                        ]
                    }
                )
            )
        )
        self.assertEqual("INCOMPLETE", receipt["coverage"]["status"])

    def test_a_changed_ignore_rule_set_on_the_second_pass_is_incomplete(self) -> None:
        # PAO R0-SNAP-01: version and configJson stay the same.
        receipt = self._read(
            CapabilityFake(
                stable(
                    {
                        ("RepositoryIgnoreRules", "gnostoa", None): [
                            ignore_page([ignore_rule("rule-1")]),
                            ignore_page(
                                [
                                    ignore_rule("rule-1"),
                                    ignore_rule("rule-2", "TYP-050"),
                                ]
                            ),
                        ]
                    }
                )
            )
        )
        self.assertEqual("INCOMPLETE", receipt["coverage"]["status"])

    def test_duplicate_identities_are_refused(self) -> None:
        cases = {
            "issue": {
                ("AnalyzerCatalogue", "python", "c1"): catalogue_page(
                    [catalogue_issue("TYP-050")], num_issues=3, total=3
                )
            },
            "ignore rule": {
                ("RepositoryIgnoreRules", "gnostoa", None): ignore_page(
                    [ignore_rule("rule-1"), ignore_rule("rule-1", "TYP-050")]
                )
            },
            "analyzer": {
                ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                    [analyzer(), analyzer()]
                )
            },
        }
        for label, override in cases.items():
            with self.subTest(duplicate=label):
                receipt = self._read(CapabilityFake(stable(override)))
                self.assertEqual("ERROR", receipt["coverage"]["status"])

    def test_pagination_that_does_not_advance_or_never_ends_is_refused(self) -> None:
        loop = catalogue_page(
            [catalogue_issue("PTC-W0063")],
            num_issues=3,
            total=3,
            has_next=True,
            cursor="c1",
        )
        receipt = self._read(
            CapabilityFake(stable({("AnalyzerCatalogue", "python", "c1"): loop}))
        )
        self.assertEqual("ERROR", receipt["coverage"]["status"])

    def test_a_graphql_error_or_an_unavailable_provider_is_never_complete(self) -> None:
        for kind, expected in (
            ("ERROR", "ERROR"),
            ("AUTH", "UNAVAILABLE"),
            ("RATE_LIMIT", "RATE_LIMITED"),
        ):
            with self.subTest(kind=kind):
                failure = analyzer_deepsource.ProviderReadFailure(
                    kind, "DeepSource GraphQL returned errors"
                )
                receipt = self._read(
                    CapabilityFake(
                        stable({("AnalyzerCatalogue", "python", "c1"): failure})
                    )
                )
                self.assertEqual(expected, receipt["coverage"]["status"])

    def test_another_repository_in_the_answer_is_refused(self) -> None:
        receipt = self._read(
            CapabilityFake(
                stable(
                    {
                        ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                            name="other"
                        )
                    }
                )
            )
        )
        self.assertEqual("ERROR", receipt["coverage"]["status"])

    def test_an_enabled_analyzer_without_a_catalogue_is_refused(self) -> None:
        receipt = self._read(
            CapabilityFake(
                stable(
                    {
                        ("AnalyzerCatalogue", "python", None): {
                            "data": {"analyzer": None}
                        }
                    }
                )
            )
        )
        self.assertEqual("ERROR", receipt["coverage"]["status"])

    def test_a_spent_deadline_reads_no_further_page(self) -> None:
        fake = CapabilityFake(stable())
        ticks = iter([0.0, 0.0, 1000.0] + [1000.0] * 50)
        with patch("time.monotonic", side_effect=ticks):
            receipt = self._read(fake, deadline_seconds=10.0)
        self.assertEqual("INCOMPLETE", receipt["coverage"]["status"])
        self.assertEqual("DEADLINE", receipt["coverage"]["reason"])
        self.assertLessEqual(len(fake.calls), 2)
        # The first repository page was read before the deadline stopped the read,
        # so what it returned is kept (CodeAnt on #441), with coverage INCOMPLETE.
        self.assertEqual("PRESENT", receipt["configuration"]["state"])
        self.assertIs(True, receipt["activated"])

    def test_a_read_stopped_before_any_page_keeps_nothing(self) -> None:
        fake = CapabilityFake(stable())
        ticks = iter([0.0] + [1000.0] * 50)
        with patch("time.monotonic", side_effect=ticks):
            receipt = self._read(fake, deadline_seconds=10.0)
        self.assertEqual([], fake.calls)
        self.assertEqual("DEADLINE", receipt["coverage"]["reason"])
        # Nothing was read, so the configuration is neither present nor absent.
        self.assertEqual({"state": "UNREAD"}, receipt["configuration"])
        self.assertIsNone(receipt["activated"])

    def test_the_deadline_reaches_every_request_and_stops_a_slow_read(self) -> None:
        # Router 6267325366: the whole-read deadline covers each request's own work,
        # so every request is given it, and a read whose requests take the budget
        # stops with no request after it.
        fake = CapabilityFake(stable())
        clock = [0.0]
        fake.clock, fake.cost = clock, 6.0
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            receipt = self._read(fake, deadline_seconds=10.0)
        self.assertEqual([10.0] * len(fake.calls), fake.deadlines)
        self.assertEqual("INCOMPLETE", receipt["coverage"]["status"])
        self.assertEqual("DEADLINE", receipt["coverage"]["reason"])
        self.assertEqual(2, len(fake.calls))

    def _status(
        self, overrides: Mapping[tuple[str, str, str | None], Any]
    ) -> dict[str, Any]:
        coverage_record: dict[str, Any] = self._read(CapabilityFake(stable(overrides)))[
            "coverage"
        ]
        return coverage_record

    def test_a_cursor_that_does_not_advance_stops_at_once(self) -> None:
        stuck = catalogue_page([], num_issues=3, total=3, has_next=True, cursor="c1")
        fake = CapabilityFake(stable({("AnalyzerCatalogue", "python", "c1"): stuck}))
        receipt = self._read(fake)
        self.assertEqual("ERROR", receipt["coverage"]["status"])
        self.assertEqual(2, [kind for kind, _ in fake.calls].count("AnalyzerCatalogue"))

    def test_a_missing_total_is_named(self) -> None:
        page = analyzers_page()
        page["data"]["repository"]["enabledAnalyzers"]["totalCount"] = None
        record = self._status({("RepositoryAnalyzers", "gnostoa", None): page})
        self.assertEqual(
            ("INCOMPLETE", "TOTAL_UNAVAILABLE"), (record["status"], record["reason"])
        )

    def test_a_connection_past_the_page_bound_is_refused(self) -> None:
        bound = analyzer_deepsource._MAX_PAGES
        overrides: dict[tuple[str, str, str | None], Any] = {}
        for index in range(bound + 1):
            cursor = None if index == 0 else f"c{index}"
            overrides[("AnalyzerCatalogue", "python", cursor)] = catalogue_page(
                [catalogue_issue(f"PY-{index}")],
                num_issues=bound + 2,
                total=bound + 2,
                has_next=True,
                cursor=f"c{index + 1}",
            )
        fake = CapabilityFake(stable(overrides))
        receipt = self._read(fake)
        self.assertEqual("ERROR", receipt["coverage"]["status"])
        self.assertEqual(
            bound, [kind for kind, _ in fake.calls].count("AnalyzerCatalogue")
        )

    def test_another_account_or_provider_in_the_answer_is_refused(self) -> None:
        for field, value in (("login", "other"), ("vcsProvider", "GITLAB")):
            with self.subTest(field=field):
                page = analyzers_page()
                page["data"]["repository"]["account"][field] = value
                record = self._status({("RepositoryAnalyzers", "gnostoa", None): page})
                self.assertEqual("ERROR", record["status"])

    def test_a_malformed_activation_flag_is_refused(self) -> None:
        page = analyzers_page()
        page["data"]["repository"]["isActivated"] = "yes"
        self.assertEqual(
            "ERROR",
            self._status({("RepositoryAnalyzers", "gnostoa", None): page})["status"],
        )

    def test_a_catalogue_for_another_analyzer_is_refused(self) -> None:
        other = catalogue_page(
            [catalogue_issue("SH-1")], shortcode="shell", num_issues=3, total=3
        )
        self.assertEqual(
            "ERROR",
            self._status({("AnalyzerCatalogue", "python", None): other})["status"],
        )

    def test_an_unknown_analyzer_version_is_incomplete(self) -> None:
        unknown = analyzers_page([analyzer(version=None)])
        overrides: dict[tuple[str, str, str | None], Any] = {
            ("RepositoryAnalyzers", "gnostoa", None): unknown,
            ("AnalyzerCatalogue", "python", None): catalogue_page(
                [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
                version=None,
                num_issues=3,
                total=3,
                has_next=True,
                cursor="c1",
            ),
            ("AnalyzerCatalogue", "python", "c1"): catalogue_page(
                [catalogue_issue("PTC-W0063")], version=None, num_issues=3, total=3
            ),
        }
        record = self._status(overrides)
        self.assertEqual(
            ("INCOMPLETE", "ANALYZER_IDENTITY_UNAVAILABLE"),
            (record["status"], record["reason"]),
        )

    def test_a_catalogue_of_unknown_identity_is_incomplete(self) -> None:
        # The enabled side is known, so the catalogue reaches the read; its own
        # unknown version or size still cannot be bound (the pre-check covers only
        # the enabled side, Router 6275423919).
        for field in ("version", "numIssues"):
            with self.subTest(field=field):
                pages = []
                for page in (
                    catalogue_page(
                        [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
                        num_issues=3,
                        total=3,
                        has_next=True,
                        cursor="c1",
                    ),
                    catalogue_page(
                        [catalogue_issue("PTC-W0063")], num_issues=3, total=3
                    ),
                ):
                    page["data"]["analyzer"][field] = None
                    pages.append(page)
                record = self._status(
                    {
                        ("AnalyzerCatalogue", "python", None): pages[0],
                        ("AnalyzerCatalogue", "python", "c1"): pages[1],
                    }
                )
                self.assertEqual(
                    ("INCOMPLETE", "ANALYZER_IDENTITY_UNAVAILABLE"),
                    (record["status"], record["reason"]),
                )

    def test_a_catalogue_at_another_version_than_enabled_is_incomplete(self) -> None:
        overrides: dict[tuple[str, str, str | None], Any] = {
            ("AnalyzerCatalogue", "python", None): catalogue_page(
                [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
                version="2.0.0",
                num_issues=3,
                total=3,
                has_next=True,
                cursor="c1",
            ),
            ("AnalyzerCatalogue", "python", "c1"): catalogue_page(
                [catalogue_issue("PTC-W0063")], version="2.0.0", num_issues=3, total=3
            ),
        }
        record = self._status(overrides)
        self.assertEqual(
            ("INCOMPLETE", "CAPABILITY_STATE_CHANGED"),
            (record["status"], record["reason"]),
        )

    def test_a_catalogue_shorter_than_its_analyzer_size_is_incomplete(self) -> None:
        # The connection's total is met, but the analyzer says it has four issues.
        overrides: dict[tuple[str, str, str | None], Any] = {
            ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                [analyzer(num_issues=4)]
            ),
            ("AnalyzerCatalogue", "python", None): catalogue_page(
                [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
                num_issues=4,
                total=3,
                has_next=True,
                cursor="c1",
            ),
            ("AnalyzerCatalogue", "python", "c1"): catalogue_page(
                [catalogue_issue("PTC-W0063")], num_issues=4, total=3
            ),
        }
        record = self._status(overrides)
        self.assertEqual(
            ("INCOMPLETE", "TOTAL_MISMATCH"), (record["status"], record["reason"])
        )

    def test_a_client_deadline_stop_is_incomplete_not_an_error(self) -> None:
        stopped = analyzer_deepsource.ProviderReadFailure(
            "DEADLINE", "DeepSource read deadline passed"
        )
        record = self._status({("AnalyzerCatalogue", "python", "c1"): stopped})
        self.assertEqual(
            ("INCOMPLETE", "DEADLINE"), (record["status"], record["reason"])
        )

    def test_a_malformed_catalogue_entry_is_refused(self) -> None:
        for field, value in (("isRecommended", "yes"), ("tags", "python")):
            with self.subTest(field=field):
                entry = catalogue_issue("PTC-W0063")
                entry[field] = value
                last = catalogue_page([entry], num_issues=3, total=3)
                self.assertEqual(
                    "ERROR",
                    self._status({("AnalyzerCatalogue", "python", "c1"): last})[
                        "status"
                    ],
                )

    def test_the_fake_refuses_a_query_it_does_not_answer(self) -> None:
        fake = CapabilityFake(stable())
        with self.assertRaisesRegex(AssertionError, "answers no such query"):
            fake.graphql(analyzer_deepsource._RUN_QUERY, {})

    def test_a_deadline_that_is_not_a_finite_positive_number_is_refused(self) -> None:
        # Amazon Q on #441: a non-positive budget; and NaN or an infinite one would
        # never stop a read, since no comparison with NaN is true.
        for value in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(deadline_seconds=value):
                fake = CapabilityFake(stable())
                with self.assertRaises(ValueError):
                    self._read(fake, deadline_seconds=value)
                self.assertEqual([], fake.calls)

    def test_a_late_last_request_is_never_complete(self) -> None:
        # Sourcery on #441: every request starts in the budget, the last ends past it.
        fake = CapabilityFake(stable())
        clock = [0.0]
        fake.clock, fake.cost = clock, 1.9
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            receipt = self._read(fake, deadline_seconds=10.0)
        self.assertEqual(6, len(fake.calls))
        self.assertEqual(
            ("INCOMPLETE", "DEADLINE"),
            (receipt["coverage"]["status"], receipt["coverage"].get("reason")),
        )

    def test_a_total_that_appears_on_a_later_page_is_refused(self) -> None:
        # Sourcery on #441: a total missing from the first page and given later.
        first = catalogue_page(
            [catalogue_issue("PYL-W0212"), catalogue_issue("TYP-050")],
            num_issues=3,
            has_next=True,
            cursor="c1",
        )
        first["data"]["analyzer"]["issues"]["totalCount"] = None
        record = self._status({("AnalyzerCatalogue", "python", None): first})
        self.assertEqual("ERROR", record["status"])

    def test_an_omitted_selected_field_is_refused(self) -> None:
        # Sourcery on #441: an omitted field is no explicit null.
        def without(page: dict[str, Any], *path: str) -> dict[str, Any]:
            node: Any = page
            for key in path[:-1]:
                node = node[int(key)] if isinstance(node, list) else node[key]
            del node[path[-1]]
            return page

        repo = ("data", "repository")
        cases: dict[str, dict[tuple[str, str, str | None], Any]] = {
            "configJson": {
                ("RepositoryAnalyzers", "gnostoa", None): without(
                    analyzers_page(), *repo, "configJson"
                )
            },
            "an analyzer's version": {
                ("RepositoryAnalyzers", "gnostoa", None): without(
                    analyzers_page(),
                    *repo,
                    "enabledAnalyzers",
                    "edges",
                    "0",
                    "node",
                    "version",
                )
            },
            "an ignore rule's filePath": {
                ("RepositoryIgnoreRules", "gnostoa", None): ignore_page(
                    [
                        {
                            k: v
                            for k, v in ignore_rule("rule-1").items()
                            if k != "filePath"
                        }
                    ]
                )
            },
        }
        for label, override in cases.items():
            with self.subTest(field=label):
                self.assertEqual("ERROR", self._status(override)["status"])

    def test_catalogues_read_before_a_failure_are_kept(self) -> None:
        # Codex and Sourcery on #441: a later failure keeps what was read whole.
        failure = analyzer_deepsource.ProviderReadFailure("ERROR", "malformed")
        overrides: dict[tuple[str, str, str | None], Any] = {
            ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                [analyzer(), analyzer("shell", num_issues=1)]
            ),
            ("AnalyzerCatalogue", "shell", None): failure,
        }
        receipt = self._read(CapabilityFake(stable(overrides)))
        self.assertEqual("ERROR", receipt["coverage"]["status"])
        self.assertEqual(["python"], [a["shortcode"] for a in receipt["analyzers"]])
        self.assertEqual(3, len(receipt["analyzers"][0]["catalogue"]))
        self.assertEqual(3, receipt["coverage"]["count"])

    def test_a_catalogue_that_fails_conversion_counts_nothing(self) -> None:
        entry = catalogue_issue("PTC-W0063")
        entry["isRecommended"] = "yes"
        last = catalogue_page([entry], num_issues=3, total=3)
        record = self._status({("AnalyzerCatalogue", "python", "c1"): last})
        self.assertEqual(("ERROR", 0), (record["status"], record["count"]))

    def test_the_activation_state_is_reported(self) -> None:
        self.assertIs(
            True, self._read(CapabilityFake(stable())).get("activated", "no key")
        )
        page = analyzers_page()
        page["data"]["repository"]["isActivated"] = False
        receipt = self._read(
            CapabilityFake(stable({("RepositoryAnalyzers", "gnostoa", None): page}))
        )
        self.assertIs(False, receipt.get("activated", "no key"))

    def test_the_missing_snapshot_is_named_as_unknown(self) -> None:
        # Sourcery on #441: the API has no snapshot or generation token, so a
        # catalogue changed within one version and size cannot be detected.
        unknown = self._read(CapabilityFake(stable()))["unknown"]
        self.assertTrue(any("snapshot" in item for item in unknown), unknown)

    def test_the_catalogue_entries_are_bounded(self) -> None:
        # CodeAnt on #441: bounds per connection alone allow a huge result.
        with patch.object(
            analyzer_deepsource, "_MAX_CATALOGUE_ENTRIES", 2, create=True
        ):
            record = self._read(CapabilityFake(stable()))["coverage"]
        self.assertEqual(
            ("INCOMPLETE", "BUDGET"), (record["status"], record.get("reason"))
        )

    def test_the_fake_refuses_another_account(self) -> None:
        fake = CapabilityFake(stable())
        with self.assertRaisesRegex(AssertionError, "answers no account"):
            fake.graphql(
                analyzer_deepsource._REPOSITORY_ANALYZERS_QUERY,
                {"name": "gnostoa", "login": "other", "cursor": None},
            )

    def test_what_the_first_repository_page_gave_is_kept_on_a_later_failure(
        self,
    ) -> None:
        # CodeAnt on #441: a failure after the first enabled-analyzers page kept
        # nothing it had returned, and reported the configuration as UNREAD.
        failure = analyzer_deepsource.ProviderReadFailure("ERROR", "malformed")
        overrides: dict[tuple[str, str, str | None], Any] = {
            ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                [analyzer()], total=2, has_next=True, cursor="a1"
            ),
            ("RepositoryAnalyzers", "gnostoa", "a1"): failure,
        }
        receipt = self._read(CapabilityFake(stable(overrides)))
        self.assertEqual("ERROR", receipt["coverage"]["status"])
        config = {"version": 1, "analyzers": [{"name": "python"}]}
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(
            {
                "state": "PRESENT",
                "digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
                "json": config,
            },
            receipt["configuration"],
        )
        self.assertIs(True, receipt["activated"])
        # The enabled analyzers were not read whole, so they are null, never empty.
        self.assertIsNone(receipt["analyzers"])

    def test_the_configuration_digest_is_the_shared_canonical_one(self) -> None:
        # revix on #441 (rule canonical-json-digests): canonical JSON and digests come
        # from the shared helpers, never ad hoc.
        from tools import review_model

        receipt = self._read(CapabilityFake(stable()))
        config = {"version": 1, "analyzers": [{"name": "python"}]}
        self.assertEqual(
            {
                "state": "PRESENT",
                "digest": review_model.canonical_digest(config),
                "json": config,
            },
            receipt["configuration"],
        )

    def test_a_configuration_with_a_non_finite_number_is_refused(self) -> None:
        # The shared canonical JSON refuses NaN and infinities (allow_nan=False); the
        # read reports it rather than crashing.
        page = analyzers_page()
        page["data"]["repository"]["configJson"] = {"limit": float("nan")}
        record = self._status({("RepositoryAnalyzers", "gnostoa", None): page})
        self.assertEqual("ERROR", record["status"])

    def _paged_configuration(self, later: Mapping[str, Any]) -> dict[str, Any]:
        """Two enabled-analyzer pages whose first has an explicit null configuration,
        the same on both passes."""
        first = analyzers_page([analyzer()], total=2, has_next=True, cursor="a1")
        first["data"]["repository"]["configJson"] = None
        return self._read(
            CapabilityFake(
                stable(
                    {
                        ("RepositoryAnalyzers", "gnostoa", None): first,
                        ("RepositoryAnalyzers", "gnostoa", "a1"): later,
                        ("AnalyzerCatalogue", "javascript", None): catalogue_page(
                            [catalogue_issue("JS-0001")],
                            shortcode="javascript",
                            num_issues=1,
                            total=1,
                        ),
                    }
                )
            )
        )

    def test_a_later_page_that_omits_the_configuration_is_refused(self) -> None:
        # Codex on #441 (4316925987): a later page that omits configJson is never the
        # explicit null of the first, so the receipt is not COMPLETE with ABSENT.
        later = analyzers_page([analyzer("javascript", num_issues=1)], total=2)
        del later["data"]["repository"]["configJson"]
        receipt = self._paged_configuration(later)
        self.assertEqual("ERROR", receipt["coverage"]["status"])

    def test_an_explicit_null_on_every_page_is_an_absent_configuration(self) -> None:
        later = analyzers_page([analyzer("javascript", num_issues=1)], total=2)
        later["data"]["repository"]["configJson"] = None
        receipt = self._paged_configuration(later)
        self.assertEqual("COMPLETE", receipt["coverage"]["status"])
        self.assertEqual({"state": "ABSENT"}, receipt["configuration"])

    def test_a_configuration_that_is_not_an_object_is_refused(self) -> None:
        # Codex on #441 (4317067622): DeepSource documents configJson as the
        # .deepsource.toml "represented as a JSON object", so a scalar or an array is
        # malformed, never a present configuration.
        for value in ([{"name": "python"}], "version = 1", 1, True):
            with self.subTest(value=value):
                page = analyzers_page(config=value)
                record = self._status({("RepositoryAnalyzers", "gnostoa", None): page})
                self.assertEqual("ERROR", record["status"])

    def test_lists_the_read_never_reached_are_null_not_empty(self) -> None:
        # revix on #441 (4317057984, rule fail-closed-unknown-evidence): an unread list
        # is never an empty one.
        ticks = iter([0.0] + [1000.0] * 50)
        with patch("time.monotonic", side_effect=ticks):
            stopped = self._read(CapabilityFake(stable()), deadline_seconds=10.0)
        failure = analyzer_deepsource.ProviderReadFailure("ERROR", "malformed")
        later = self._read(
            CapabilityFake(
                stable(
                    {
                        ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                            [analyzer()], total=2, has_next=True, cursor="a1"
                        ),
                        ("RepositoryAnalyzers", "gnostoa", "a1"): failure,
                    }
                )
            )
        )
        for receipt in (stopped, later):
            with self.subTest(reason=receipt["coverage"].get("reason")):
                self.assertIsNone(receipt["analyzers"])
                self.assertIsNone(receipt["ignore_rules"])

    def test_the_discovery_stop_is_a_domain_error(self) -> None:
        # revix on #441 (4317057997, rule domain-exception-per-module): the module's
        # errors derive from RuntimeError, as ProviderReadFailure does.
        self.assertTrue(
            issubclass(analyzer_deepsource._DiscoveryIncomplete, RuntimeError)
        )

    def test_the_fake_refuses_a_request_its_answers_do_not_cover(self) -> None:
        # Amazon Q on #441 (4317793141): a list answer is consumed one per request,
        # so a read that makes more requests than the test gave fails, instead of
        # silently reusing the last answer.
        page = analyzers_page()
        fake = CapabilityFake({("RepositoryAnalyzers", "gnostoa", None): [page]})
        variables = {"name": "gnostoa", "login": "ktogias", "cursor": None}
        query = analyzer_deepsource._REPOSITORY_ANALYZERS_QUERY
        self.assertIs(page, fake.graphql(query, variables))
        with self.assertRaisesRegex(AssertionError, "no more answers"):
            fake.graphql(query, variables)

    def _catalogue_calls(self, fake: CapabilityFake) -> list[str]:
        return [str(v["shortcode"]) for k, v in fake.calls if k == "AnalyzerCatalogue"]

    def test_an_enabled_analyzer_of_unknown_identity_is_named_so(self) -> None:
        # revix on #441 (4317819965), Router 6275423919: an enabled analyzer whose
        # version or size is unknown cannot be bound to a catalogue, which is not a
        # state change, and its catalogue is never requested.
        for enabled in (analyzer(version=None), {**analyzer(), "numIssues": None}):
            with self.subTest(enabled=enabled):
                fake = CapabilityFake(
                    stable(
                        {
                            ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                                [enabled]
                            )
                        }
                    )
                )
                record = self._read(fake)["coverage"]
                self.assertEqual("INCOMPLETE", record["status"])
                self.assertEqual("ANALYZER_IDENTITY_UNAVAILABLE", record["reason"])
                self.assertEqual([], self._catalogue_calls(fake))

    def _two_catalogues(self, ruby_size: int) -> CapabilityFake:
        """python (3 entries, from `stable`) then ruby, declaring `ruby_size`."""
        ruby = catalogue_page(
            [catalogue_issue(f"RB-{i}") for i in range(ruby_size)],
            shortcode="ruby",
            num_issues=ruby_size,
            total=ruby_size,
        )
        return CapabilityFake(
            stable(
                {
                    ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                        [analyzer(), analyzer("ruby", num_issues=ruby_size)]
                    ),
                    ("AnalyzerCatalogue", "ruby", None): ruby,
                }
            )
        )

    def test_a_catalogue_that_cannot_fit_is_never_requested(self) -> None:
        # revix on #441 (4317819958), Router 6275423919: a COMPLETE catalogue must
        # equal its declared size, so one that cannot fit is refused unread.
        fake = CapabilityFake(stable())
        with patch.object(analyzer_deepsource, "_MAX_CATALOGUE_ENTRIES", 2):
            record = self._read(fake)["coverage"]
        self.assertEqual("BUDGET", record["reason"])
        self.assertEqual([], self._catalogue_calls(fake))

    def test_a_later_catalogue_that_cannot_fit_keeps_the_earlier_one(self) -> None:
        fake = self._two_catalogues(3)
        with patch.object(analyzer_deepsource, "_MAX_CATALOGUE_ENTRIES", 5):
            receipt = self._read(fake)
        self.assertEqual("BUDGET", receipt["coverage"]["reason"])
        self.assertNotIn("ruby", self._catalogue_calls(fake))
        self.assertEqual(["python"], [a["shortcode"] for a in receipt["analyzers"]])
        self.assertEqual(3, receipt["coverage"]["count"])

    def test_a_catalogue_that_fills_the_budget_exactly_is_read(self) -> None:
        fake = self._two_catalogues(2)
        with patch.object(analyzer_deepsource, "_MAX_CATALOGUE_ENTRIES", 5):
            receipt = self._read(fake)
        self.assertEqual("COMPLETE", receipt["coverage"]["status"])
        self.assertEqual(
            ["python", "ruby"], [a["shortcode"] for a in receipt["analyzers"]]
        )
        self.assertEqual(5, receipt["coverage"]["count"])


def _analyzers_pages(
    shortcodes: Sequence[str], *, num_issues: int = 3
) -> dict[tuple[str, str, str | None], Any]:
    """The enabled-analyzer connection for `shortcodes`, 100 a page, as answers."""
    nodes = [analyzer(s, num_issues=num_issues) for s in shortcodes]
    if len(nodes) <= 100:
        return {("RepositoryAnalyzers", "gnostoa", None): analyzers_page(nodes)}
    return {
        ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
            nodes[:100], total=len(nodes), has_next=True, cursor="e1"
        ),
        ("RepositoryAnalyzers", "gnostoa", "e1"): analyzers_page(
            nodes[100:], total=len(nodes)
        ),
    }


class _OffsetRestFake:
    """A test-only provider of a materially different native shape (#285 RCA, Router
    6269272533): offset pages rather than cursors, opaque non-numeric identities, a
    rule count named apart from the rules, and exclusions rather than ignore rules.
    `fail` names a path whose page at `fail_offset` raises."""

    def __init__(
        self,
        tools: Sequence[Mapping[str, Any]],
        rules: Mapping[str, Sequence[Mapping[str, Any]]],
        exclusions: Sequence[Mapping[str, Any]] = (),
        *,
        limit: int = 2,
        fail: str | None = None,
        fail_offset: int = 0,
    ) -> None:
        self.collections: dict[str, list[Mapping[str, Any]]] = {
            "/tools": list(tools),
            "/exclusions": list(exclusions),
        }
        for ref, entries in rules.items():
            self.collections[f"/tools/{ref}/rules"] = list(entries)
        self.limit = limit
        self.fail = fail
        self.fail_offset = fail_offset
        self.calls: list[tuple[str, int]] = []

    def get(self, path: str, *, offset: int) -> Mapping[str, Any]:
        self.calls.append((path, offset))
        if path == self.fail and offset == self.fail_offset:
            raise RuntimeError(f"offset provider failed at {path}")
        items = self.collections[path]
        return {
            "items": items[offset : offset + self.limit],
            "offset": offset,
            "total": len(items),
        }


class _OffsetRead:
    __slots__ = ("pages",)

    def __init__(self) -> None:
        self.pages = 0


def _offset_all(
    fake: _OffsetRestFake, read: _OffsetRead, path: str
) -> list[Mapping[str, Any]]:
    offset, items = 0, []
    while True:
        page = fake.get(path, offset=offset)
        read.pages += 1
        if not page["items"] and offset < page["total"]:
            # A short read is the fixture's failure, never a smaller inventory
            # (Amazon Q on #444).
            raise AssertionError(
                "the offset provider gave an empty page before its total"
            )
        items.extend(page["items"])
        offset += len(page["items"])
        if offset >= page["total"]:
            return items


def _offset_capability(fake: _OffsetRestFake) -> dict[str, Any]:
    """The test-only translator: the offset provider's native answers, written into the
    neutral capability record. Nothing here is shared with the DeepSource adapter."""

    build = getattr(analyzer_readback, "build_capability", None)
    if build is None:
        raise AssertionError("missing capability: analyzer_readback.build_capability")
    read = _OffsetRead()
    enabled: list[dict[str, Any]] | None = None
    catalogues: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] | None = None
    entries = 0
    record: dict[str, Any]
    try:
        tools = _offset_all(fake, read, "/tools")
        enabled = [
            {
                "id": str(t["label"]),
                "version": t.get("release"),
                "declared_entries": t.get("rule_total"),
            }
            for t in tools
        ]
        catalogues = [
            {
                "analyzer": e["id"],
                "state": "UNREAD",
                "version": e["version"],
                "entries": None,
            }
            for e in enabled
        ]
        for tool, slot in zip(tools, catalogues, strict=True):
            slot["state"] = "PARTIAL"
            native = _offset_all(fake, read, f"/tools/{tool['ref']}/rules")
            slot["entries"] = [
                {"id": str(r["key"]), "title": r.get("summary")} for r in native
            ]
            slot["state"] = "COMPLETE"
            entries += len(native)
        rules = [
            {
                "id": str(x["ref"]),
                "rule": str(x["rule_key"]),
                "path": None,
                "glob": x.get("path_glob"),
            }
            for x in _offset_all(fake, read, "/exclusions")
        ]
        record = analyzer_readback.coverage("COMPLETE", pages=read.pages, count=entries)
    except RuntimeError:
        for slot in catalogues:
            if slot["state"] == "PARTIAL":
                slot["entries"] = None
        record = analyzer_readback.coverage(
            "ERROR", pages=read.pages, count=entries, reason="PROVIDER_ERROR"
        )
    result: dict[str, Any] = build(
        provider="offset-rest-test",
        adapter="test-offset-rest/v1",
        repository=REPOSITORY,
        observed_at=OBSERVED,
        binding="CURRENT_NOT_RUN_BOUND",
        coverage=record,
        configuration={"state": "UNSUPPORTED"},
        activated=None,
        enabled={
            "status": "COMPLETE" if enabled is not None else "UNREAD",
            "analyzers": enabled,
        },
        catalogues=catalogues,
        ignore_rules={
            "status": "COMPLETE" if rules is not None else "UNREAD",
            "rules": rules,
        },
        unknown=["how this provider's configuration selects its rules"],
    )
    return result


def _rest_tools() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """The offset provider's view of `stable()`: python 1.0.0 with its three issues,
    under opaque identities and other field names."""
    tools = [
        {"ref": "tl_7Qx-python", "label": "python", "release": "1.0.0", "rule_total": 3}
    ]
    rules = {
        "tl_7Qx-python": [
            {"key": "TYP-050", "summary": "Issue TYP-050"},
            {"key": "PYL-W0212", "summary": "Issue PYL-W0212"},
            {"key": "PTC-W0063", "summary": "Issue PTC-W0063"},
        ]
    }
    return tools, rules


class CapabilityContractTests(unittest.TestCase):
    """#389 F3 R0b (Router 6269272533, entry 6292521425): one private neutral
    capability contract in analyzer_readback, fed by the DeepSource adapter and by a
    materially different test-only translator, and read by one unchanged consumer.
    Enabled descriptors are retained apart from catalogues (Router 6280406609)."""

    def _discover(self, fake: CapabilityFake) -> dict[str, Any]:
        result: dict[str, Any] = analyzer_deepsource.read_capability_discovery(
            fake, REPOSITORY
        )
        return result

    def _api(self, module: Any, name: str) -> Any:
        found = getattr(module, name, None)
        if found is None:
            self.fail(f"missing capability: {module.__name__}.{name}")
        return found

    def _inventory(self, record: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self._api(analyzer_readback, "catalogue_inventory")(
            record
        )
        return result

    def _neutral(self, discovery: Mapping[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = self._api(analyzer_deepsource, "capability_record")(
            discovery
        )
        return result

    # L6: enabled descriptors read whole survive a later failure.

    def test_enabled_analyzers_read_whole_survive_an_ignore_rule_failure(self) -> None:
        failure = analyzer_deepsource.ProviderReadFailure("ERROR", "malformed")
        for n in (0, 3, 101):
            with self.subTest(enabled=n):
                names = [f"an{i:03d}" for i in range(n)]
                overrides = {
                    **_analyzers_pages(names),
                    ("RepositoryIgnoreRules", "gnostoa", None): failure,
                }
                fake = CapabilityFake(stable(overrides))
                receipt = self._discover(fake)
                self.assertEqual("ERROR", receipt["coverage"]["status"])
                self.assertEqual(
                    names,
                    [a["shortcode"] for a in receipt.get("enabled_analyzers") or []]
                    if receipt.get("enabled_analyzers") is not None
                    else None,
                    "the enabled descriptors read whole are lost",
                )
                # No catalogue was reached, and none is invented empty.
                self.assertIsNone(receipt["analyzers"])
                self.assertEqual(
                    [], [k for k, _ in fake.calls if k == "AnalyzerCatalogue"]
                )
                neutral = self._neutral(receipt)
                inventory = self._inventory(neutral)
                self.assertEqual("COMPLETE", inventory["enabled"])
                self.assertEqual(
                    [(name, "UNREAD") for name in names],
                    [(a["id"], a["state"]) for a in inventory["analyzers"]],
                )
                self.assertFalse(inventory["complete"])

    def test_an_enabled_list_never_read_is_unknown_not_empty(self) -> None:
        failure = analyzer_deepsource.ProviderReadFailure("ERROR", "malformed")
        unread = self._discover(
            CapabilityFake(stable({("RepositoryAnalyzers", "gnostoa", None): failure}))
        )
        empty = self._discover(
            CapabilityFake(
                stable(
                    {
                        **_analyzers_pages([]),
                        ("RepositoryIgnoreRules", "gnostoa", None): failure,
                    }
                )
            )
        )
        self.assertIsNone(unread.get("enabled_analyzers", "no key"))
        self.assertEqual([], empty.get("enabled_analyzers", "no key"))
        self.assertEqual("UNREAD", self._inventory(self._neutral(unread))["enabled"])
        self.assertEqual("COMPLETE", self._inventory(self._neutral(empty))["enabled"])

    # L8: catalogue state, and the original reason kept.

    def test_a_failed_catalogue_is_partly_read_and_later_ones_unread(self) -> None:
        failure = analyzer_deepsource.ProviderReadFailure("ERROR", "malformed")
        overrides: dict[tuple[str, str, str | None], Any] = {
            **_analyzers_pages(["python", "shell", "zsh"], num_issues=3),
            ("AnalyzerCatalogue", "shell", None): catalogue_page(
                [catalogue_issue("SH-1"), catalogue_issue("SH-2")],
                shortcode="shell",
                num_issues=3,
                total=3,
                has_next=True,
                cursor="s1",
            ),
            ("AnalyzerCatalogue", "shell", "s1"): failure,
        }
        fake = CapabilityFake(stable(overrides))
        receipt = self._discover(fake)
        self.assertEqual(
            ("ERROR", "PROVIDER_ERROR"),
            (receipt["coverage"]["status"], receipt["coverage"]["reason"]),
        )
        self.assertEqual(["python"], [a["shortcode"] for a in receipt["analyzers"]])
        self.assertEqual(
            "shell",
            receipt.get("catalogue_partial"),
            "a partly read catalogue is indistinguishable from one never reached",
        )
        inventory = self._inventory(self._neutral(receipt))
        self.assertEqual(
            [("python", "COMPLETE"), ("shell", "PARTIAL"), ("zsh", "UNREAD")],
            [(a["id"], a["state"]) for a in inventory["analyzers"]],
        )
        self.assertEqual(
            ["PTC-W0063", "PYL-W0212", "TYP-050"], inventory["analyzers"][0]["entries"]
        )
        self.assertIsNone(inventory["analyzers"][1]["entries"])
        self.assertEqual("PROVIDER_ERROR", inventory["reason"])

    def test_a_catalogue_refused_unread_is_not_partly_read(self) -> None:
        overrides = {
            ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(
                [analyzer(), analyzer("ruby", version=None)]
            )
        }
        receipt = self._discover(CapabilityFake(stable(overrides)))
        self.assertEqual("ANALYZER_IDENTITY_UNAVAILABLE", receipt["coverage"]["reason"])
        self.assertIsNone(receipt.get("catalogue_partial", "no key"))
        inventory = self._inventory(self._neutral(receipt))
        self.assertEqual(
            [("python", "COMPLETE"), ("ruby", "UNREAD")],
            [(a["id"], a["state"]) for a in inventory["analyzers"]],
        )

    # L4, L10: two native shapes, one unchanged consumer.

    def test_both_providers_feed_one_unchanged_inventory(self) -> None:
        deepsource = self._inventory(
            self._neutral(self._discover(CapabilityFake(stable())))
        )
        tools, rules = _rest_tools()
        exclusions = [{"ref": "ex_a1", "rule_key": "PYL-W0212", "path_glob": None}]
        offset = self._inventory(
            _offset_capability(_OffsetRestFake(tools, rules, exclusions))
        )
        self.assertTrue(deepsource["complete"])
        self.assertEqual(deepsource, offset)

    def test_reordering_and_opaque_renaming_do_not_change_the_inventory(self) -> None:
        tools, rules = _rest_tools()
        renamed = [{**tools[0], "ref": "zz_Op4que"}]
        reordered = {"zz_Op4que": list(reversed(rules["tl_7Qx-python"]))}
        first = self._inventory(_offset_capability(_OffsetRestFake(tools, rules)))
        second = self._inventory(
            _offset_capability(_OffsetRestFake(renamed, reordered, limit=1))
        )
        self.assertEqual(first, second)

    def test_the_offset_provider_keeps_partial_and_unread_states(self) -> None:
        tools = [
            {"ref": "tl_a", "label": "go", "release": "2.1", "rule_total": 2},
            {"ref": "tl_b", "label": "rust", "release": "0.9", "rule_total": 2},
        ]
        rules = {
            "tl_a": [{"key": "GO-1"}, {"key": "GO-2"}],
            "tl_b": [{"key": "RS-1"}, {"key": "RS-2"}],
        }
        record = _offset_capability(
            _OffsetRestFake(
                tools, rules, limit=1, fail="/tools/tl_b/rules", fail_offset=1
            )
        )
        inventory = self._inventory(record)
        self.assertEqual(
            [("go", "COMPLETE"), ("rust", "PARTIAL")],
            [(a["id"], a["state"]) for a in inventory["analyzers"]],
        )
        self.assertFalse(inventory["complete"])
        self.assertEqual("PROVIDER_ERROR", inventory["reason"])

    # L5: binding.

    def test_an_analysis_id_alone_never_makes_a_record_run_bound(self) -> None:
        build = self._api(analyzer_readback, "build_capability")
        tools, rules = _rest_tools()
        fields = {**self._fields(_offset_capability(_OffsetRestFake(tools, rules)))}
        fields["binding"] = "RUN_BOUND"
        fields["native"] = {"analysis_id": "an_8Hk2"}
        with self.assertRaises(analyzer_readback.AnalyzerReadbackError):
            build(**fields)

    # L3, L2: a closed record that agrees with its coverage.

    def _fields(self, record: Mapping[str, Any]) -> dict[str, Any]:
        return {
            k: v
            for k, v in record.items()
            if k not in {"schema", "effective_configuration"}
        }

    def test_the_capability_record_is_closed(self) -> None:
        parse = self._api(analyzer_readback, "parse_capability")
        tools, rules = _rest_tools()
        record = _offset_capability(_OffsetRestFake(tools, rules))
        self.assertEqual("gnostoa-analyzer-capability/v1", record["schema"])
        self.assertEqual("UNPROVEN", record["effective_configuration"])
        self.assertEqual(record, parse(json.loads(json.dumps(record))))
        with self.assertRaises(analyzer_readback.AnalyzerReadbackError):
            parse({**record, "extra": 1})
        missing = dict(record)
        del missing["enabled"]
        with self.assertRaises(analyzer_readback.AnalyzerReadbackError):
            parse(missing)

    def test_complete_coverage_with_an_unread_catalogue_is_refused(self) -> None:
        build = self._api(analyzer_readback, "build_capability")
        tools, rules = _rest_tools()
        fields = self._fields(_offset_capability(_OffsetRestFake(tools, rules)))
        fields["catalogues"] = [
            {**fields["catalogues"][0], "state": "UNREAD", "entries": None}
        ]
        with self.assertRaises(analyzer_readback.AnalyzerReadbackError):
            build(**fields)

    def test_the_record_refuses_each_contradiction(self) -> None:
        # Each case breaks exactly one rule of a valid record, so each guard is held
        # by its own case.
        build = self._api(analyzer_readback, "build_capability")
        parse = self._api(analyzer_readback, "parse_capability")
        tools, rules = _rest_tools()
        record = _offset_capability(_OffsetRestFake(tools, rules))
        base = self._fields(record)
        [descriptor] = base["enabled"]["analyzers"]
        [catalogue] = base["catalogues"]
        failed = {"status": "ERROR", "pages": 1, "count": 0, "reason": "PROVIDER_ERROR"}
        cases: dict[str, tuple[dict[str, Any], str]] = {
            "a digest on an absent configuration": (
                {"configuration": {"state": "ABSENT", "digest": "sha256:" + "0" * 64}},
                "only a present configuration",
            ),
            "a digest that is not sha256": (
                {"configuration": {"state": "PRESENT", "digest": "md5:abc"}},
                "not sha256",
            ),
            "analyzers on an enabled list not read whole": (
                {
                    "enabled": {"status": "UNREAD", "analyzers": [descriptor]},
                    "catalogues": [],
                    "coverage": failed,
                },
                "not read whole has no analyzers",
            ),
            "a catalogue at another version": (
                {"catalogues": [{**catalogue, "version": "9.9"}]},
                "version is not its analyzer's",
            ),
            "entries on a partly read catalogue": (
                {
                    "catalogues": [{**catalogue, "state": "PARTIAL"}],
                    "coverage": failed,
                },
                "only a catalogue read whole has entries",
            ),
            "a complete catalogue of unknown size": (
                {
                    "enabled": {
                        "status": "COMPLETE",
                        "analyzers": [{**descriptor, "declared_entries": None}],
                    }
                },
                "unknown size",
            ),
            "a complete catalogue short of its size": (
                {
                    "enabled": {
                        "status": "COMPLETE",
                        "analyzers": [{**descriptor, "declared_entries": 4}],
                    }
                },
                "disagrees with its declared size",
            ),
            "rules on ignore rules not read whole": (
                {
                    "ignore_rules": {"status": "UNREAD", "rules": []},
                    "coverage": {**failed, "count": 3},
                },
                "ignore rules not read whole",
            ),
            "an enabled analyzer without a catalogue state": (
                {"catalogues": [], "coverage": failed},
                "one per enabled analyzer",
            ),
            "a count that is not the entries read whole": (
                {"coverage": {**failed, "count": 2}},
                "count is not its catalogue entries",
            ),
            "complete coverage over unread ignore rules": (
                {"ignore_rules": {"status": "UNREAD", "rules": None}},
                "complete capability coverage has an unread part",
            ),
            "a provider-native field in a neutral descriptor": (
                {
                    "enabled": {
                        "status": "COMPLETE",
                        "analyzers": [{**descriptor, "shortcode": "python"}],
                    }
                },
                "missing or unknown fields",
            ),
            "a repeated enabled analyzer": (
                {
                    "enabled": {
                        "status": "COMPLETE",
                        "analyzers": [descriptor, dict(descriptor)],
                    }
                },
                "repeats the identity",
            ),
        }
        for label, (change, message) in cases.items():
            with self.subTest(case=label):
                with self.assertRaisesRegex(
                    analyzer_readback.AnalyzerReadbackError, message
                ):
                    build(**{**base, **change})
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError, "never proves"
        ):
            parse({**record, "effective_configuration": "PROVEN"})
        unsorted = json.loads(json.dumps(record))
        unsorted["catalogues"][0]["entries"].reverse()
        with self.assertRaisesRegex(
            analyzer_readback.AnalyzerReadbackError, "not what its contract builds"
        ):
            parse(unsorted)

    # Review round 1 (Amazon Q on #444).

    def test_an_ignore_rule_keeps_both_its_path_and_glob(self) -> None:
        # Amazon Q 4326119611: a rule with both a file path and a glob kept only one.
        both = {
            **ignore_rule("rule-1"),
            "filePath": "tools/a.py",
            "globPattern": "tools/**",
        }
        receipt = self._discover(
            CapabilityFake(
                stable(
                    {("RepositoryIgnoreRules", "gnostoa", None): ignore_page([both])}
                )
            )
        )
        [rule] = self._neutral(receipt)["ignore_rules"]["rules"]
        self.assertEqual(
            ("tools/a.py", "tools/**"),
            (rule.get("path"), rule.get("glob")),
            "an ignore rule's path or glob is dropped",
        )

    def test_a_record_that_is_not_json_is_refused_by_contract(self) -> None:
        # Amazon Q 4326119628: a value JSON cannot hold is a contract refusal, never a
        # raw ValueError or TypeError.
        build = self._api(analyzer_readback, "build_capability")
        tools, rules = _rest_tools()
        fields = self._fields(_offset_capability(_OffsetRestFake(tools, rules)))
        for value in (float("nan"), {1, 2}):
            with self.subTest(native=type(value).__name__):
                with self.assertRaises(analyzer_readback.AnalyzerReadbackError):
                    build(**{**fields, "native": {"value": value}})

    def test_the_offset_fixture_refuses_a_short_read(self) -> None:
        # Amazon Q 4326119660: an empty page before its total is a fixture failure, so
        # the test-only translator never under-reads silently.
        class _Short(_OffsetRestFake):
            def get(self, path: str, *, offset: int) -> Mapping[str, Any]:
                answer = dict(super().get(path, offset=offset))
                if path == "/tools":
                    answer["total"] = 5
                return answer

        tools, rules = _rest_tools()
        with self.assertRaisesRegex(AssertionError, "empty page before its total"):
            _offset_capability(_Short(tools, rules, limit=5))

    # Review round 2 (Codex 4326137385 and Sourcery 4326145486 / 4326145497 on #444).

    def test_a_catalogue_whose_first_request_fails_is_partly_read(self) -> None:
        # A request was sent and failed before any page came back: it was attempted,
        # so the catalogue is PARTIAL, never UNREAD.
        failure = analyzer_deepsource.ProviderReadFailure("UNAVAILABLE", "down")
        overrides: dict[tuple[str, str, str | None], Any] = {
            **_analyzers_pages(["python", "shell"], num_issues=3),
            ("AnalyzerCatalogue", "shell", None): failure,
        }
        receipt = self._discover(CapabilityFake(stable(overrides)))
        self.assertEqual(
            "shell",
            receipt.get("catalogue_partial"),
            "a catalogue whose first request failed is reported never requested",
        )
        inventory = self._inventory(self._neutral(receipt))
        self.assertEqual(
            [("python", "COMPLETE"), ("shell", "PARTIAL")],
            [(a["id"], a["state"]) for a in inventory["analyzers"]],
        )

    def test_an_ignore_rule_keeps_its_native_attributes(self) -> None:
        # A rule's level and type are kept as the provider's own attributes, which the
        # neutral contract carries and never interprets.
        rule = {**ignore_rule("rule-1"), "level": "FILE", "type": "TEMPORARY"}
        receipt = self._discover(
            CapabilityFake(
                stable(
                    {("RepositoryIgnoreRules", "gnostoa", None): ignore_page([rule])}
                )
            )
        )
        [neutral] = self._neutral(receipt)["ignore_rules"]["rules"]
        self.assertEqual(
            {"level": "FILE", "type": "TEMPORARY"},
            neutral.get("native"),
            "an ignore rule's level and type are dropped",
        )

    # L11: characterized as they are, with no cap selected (Router 6276781659).

    def test_whole_read_calls_count_every_page_of_both_snapshots(self) -> None:
        for n in (0, 5, 101):
            with self.subTest(enabled=n):
                names = [f"an{i:03d}" for i in range(n)]
                overrides: dict[tuple[str, str, str | None], Any] = {
                    **_analyzers_pages(names, num_issues=0)
                }
                for name in names:
                    overrides[("AnalyzerCatalogue", name, None)] = catalogue_page(
                        [], shortcode=name, num_issues=0, total=0
                    )
                fake = CapabilityFake(stable(overrides))
                receipt = self._discover(fake)
                enabled_pages = 2 if n > 100 else 1
                self.assertEqual("COMPLETE", receipt["coverage"]["status"])
                # Two snapshots of the enabled and ignore-rule connections, and one
                # request per empty catalogue, though it converts no entry.
                self.assertEqual(2 * (enabled_pages + 1) + n, len(fake.calls))
                self.assertEqual(len(fake.calls), receipt["coverage"]["pages"])
                self.assertEqual(0, receipt["coverage"]["count"])

    def test_a_page_larger_than_requested_is_materialized_whole(self) -> None:
        # The streaming residual (Router 6275423919): a page is kept whole before its
        # connection's total is checked, so an under-declared page size is not
        # refused. Characterized, not changed, in R0b.
        names = [f"an{i:03d}" for i in range(150)]
        nodes = [analyzer(s, num_issues=0) for s in names]
        overrides: dict[tuple[str, str, str | None], Any] = {
            ("RepositoryAnalyzers", "gnostoa", None): analyzers_page(nodes, total=150)
        }
        for name in names:
            overrides[("AnalyzerCatalogue", name, None)] = catalogue_page(
                [], shortcode=name, num_issues=0, total=0
            )
        receipt = self._discover(CapabilityFake(stable(overrides)))
        self.assertEqual("COMPLETE", receipt["coverage"]["status"])
        self.assertEqual(150, len(receipt["analyzers"]))


class _TimedResponse:
    """A response whose body arrives in pieces, each moving the clock."""

    def __init__(
        self, pieces: Sequence[bytes], clock: list[float], cost: float
    ) -> None:
        self.pieces = list(pieces)
        self.clock = clock
        self.cost = cost
        self.given = 0

    def __enter__(self) -> _TimedResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def _next(self, size: int = -1) -> bytes:
        self.clock[0] += self.cost
        if not self.pieces:
            return b""
        piece = self.pieces.pop(0)
        if 0 <= size < len(piece):
            piece, rest = piece[:size], piece[size:]
            self.pieces.insert(0, rest)
        self.given += len(piece)
        return piece

    def read(self, _size: int = -1) -> bytes:
        return b"".join(iter(self._next, b""))

    def read1(self, size: int = -1) -> bytes:
        return self._next(size)


class _TimedOpener:
    def __init__(self, response: _TimedResponse) -> None:
        self.response = response
        self.timeouts: list[float] = []

    def open(self, _request: object, timeout: float) -> _TimedResponse:
        self.timeouts.append(timeout)
        return self.response


class _DripRaw(io.RawIOBase):
    """One byte per receive, after a real pause from byte `slow_from` on."""

    def __init__(self, data: bytes, slow_from: int, delay: float) -> None:
        self.data, self.position = data, 0
        self.slow_from, self.delay = slow_from, delay

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        if self.position >= len(self.data):
            return 0
        if self.position >= self.slow_from:
            time.sleep(self.delay)
        buffer[0] = self.data[self.position]
        self.position += 1
        return 1


class _DripSocket:
    def __init__(self, data: bytes, slow_from: int, delay: float) -> None:
        self.raw = _DripRaw(data, slow_from, delay)

    def makefile(self, *_args: object, **_kwargs: object) -> io.BufferedReader:
        return io.BufferedReader(self.raw)


class _ParsingOpener:
    """A real http.client parser over a dripping socket, inside `open()` as urllib
    has it: the status line and headers are parsed before `open()` returns."""

    def __init__(self, data: bytes, slow_from: int, delay: float) -> None:
        self.data, self.slow_from, self.delay = data, slow_from, delay

    def open(self, _request: object, timeout: float) -> http.client.HTTPResponse:
        # A test double: HTTPResponse uses only the socket's makefile() (M13 on #441).
        sock = cast(Any, _DripSocket(self.data, self.slow_from, self.delay))
        response = http.client.HTTPResponse(sock)
        response.begin()
        return response


class DeepSourceClientDeadlineTests(unittest.TestCase):
    """The client's optional deadline (#389 F3 R0, Router 6267325366): absent, every
    existing read is unchanged; given, it bounds the connection and the body."""

    _BODY = (b'{"data": ', b'{"run": null}}')

    def _client(self, opener: object) -> analyzer_deepsource.DeepSourceGraphQLClient:
        client = analyzer_deepsource.DeepSourceGraphQLClient("test-token")
        # A test double in place of the opener (M13 on #441).
        client._opener = cast(urllib.request.OpenerDirector, opener)
        return client

    def _graphql(
        self, client: analyzer_deepsource.DeepSourceGraphQLClient, deadline: float
    ) -> Mapping[str, Any]:
        return client.graphql(
            analyzer_deepsource._RUN_QUERY,
            {"runUid": "x", "cursor": None},
            deadline=deadline,
        )

    def _refusal(
        self, opener: object, deadline: float
    ) -> analyzer_deepsource.ProviderReadFailure:
        """The client's refusal, with one call inside the expectation (Sonar S5778)."""
        client = self._client(opener)
        with self.assertRaises(analyzer_deepsource.ProviderReadFailure) as raised:
            self._graphql(client, deadline)
        return raised.exception

    def test_without_a_deadline_the_timeout_is_unchanged(self) -> None:
        clock = [0.0]
        opener = _TimedOpener(_TimedResponse(self._BODY, clock, 0.0))
        client = self._client(opener)
        client.graphql(analyzer_deepsource._RUN_QUERY, {"runUid": "x", "cursor": None})
        self.assertEqual([30], opener.timeouts)

    def test_a_spent_deadline_opens_no_connection(self) -> None:
        class _FailOpener:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise AssertionError("no connection may open after the deadline")

        with patch("time.monotonic", return_value=100.0):
            refusal = self._refusal(_FailOpener(), 50.0)
        self.assertEqual("DEADLINE", refusal.kind)

    def test_the_connection_timeout_never_exceeds_the_budget_left(self) -> None:
        clock = [0.0]
        opener = _TimedOpener(_TimedResponse(self._BODY, clock, 0.0))
        client = self._client(opener)
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            self._graphql(client, 5.0)
        # The shared exchange gives each receive half the budget left (Decision 0100).
        [timeout] = opener.timeouts
        self.assertLessEqual(timeout, 5.0)
        self.assertGreater(timeout, 0.0)

    def test_a_body_that_arrives_past_the_deadline_is_refused(self) -> None:
        clock = [0.0]
        opener = _TimedOpener(_TimedResponse(self._BODY, clock, 3.0))
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            refusal = self._refusal(opener, 5.0)
        self.assertEqual("DEADLINE", refusal.kind)

    def test_a_deadline_bound_body_reads_no_more_than_its_size_bound(self) -> None:
        clock = [0.0]
        limit = analyzer_deepsource._MAX_RESPONSE_BYTES
        response = _TimedResponse([b"x" * (1 << 20)] * 6, clock, 0.0)
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            client = self._client(_TimedOpener(response))
            with self.assertRaisesRegex(
                analyzer_deepsource.ProviderReadFailure, "exceeds bounded size"
            ):
                self._graphql(client, 50.0)
        # The shared exchange refuses once one chunk takes the body past the cap.
        self.assertLessEqual(
            response.given,
            limit + analyzer_deepsource._EXCHANGE_POLICY.read_chunk_bytes,
        )

    def test_a_timeout_at_the_deadline_is_the_deadline(self) -> None:
        clock = [0.0]

        class _SlowOpener:
            def open(self, _request: object, timeout: float) -> object:
                clock[0] += timeout
                raise TimeoutError("timed out")

        with patch("time.monotonic", side_effect=lambda: clock[0]):
            refusal = self._refusal(_SlowOpener(), 5.0)
        self.assertEqual("DEADLINE", refusal.kind)

    def test_a_deadline_that_is_not_finite_opens_no_connection(self) -> None:
        class _FailOpener:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise AssertionError("no connection may open without a finite deadline")

        for value in (float("nan"), float("inf")):
            with self.subTest(deadline=value):
                refusal = self._refusal(_FailOpener(), value)
                self.assertEqual("ERROR", refusal.kind)

    def _elapsed_until_refused(self, opener: object) -> tuple[float, str]:
        client = self._client(opener)
        started = time.monotonic()
        with self.assertRaises(analyzer_deepsource.ProviderReadFailure) as raised:
            self._graphql(client, started + 0.3)
        return time.monotonic() - started, raised.exception.kind

    def test_slow_headers_are_bounded_by_the_deadline(self) -> None:
        # PAO R0-DEADLINE-01 (6267919955): the status line and headers drip inside
        # open(), one byte per receive, each well inside its socket timeout.
        data = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}"
        elapsed, kind = self._elapsed_until_refused(_ParsingOpener(data, 0, 0.03))
        self.assertEqual("DEADLINE", kind)
        self.assertLess(elapsed, 1.0)

    def test_slow_chunk_framing_is_bounded_by_the_deadline(self) -> None:
        # PAO R0-DEADLINE-01: a chunk-size extension drips inside one read1.
        head = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
        data = head + b"2;" + b"x" * 40 + b"\r\n{}\r\n0\r\n\r\n"
        elapsed, kind = self._elapsed_until_refused(
            _ParsingOpener(data, len(head), 0.03)
        )
        self.assertEqual("DEADLINE", kind)
        self.assertLess(elapsed, 1.0)

    def test_an_answer_finished_after_the_deadline_is_refused(self) -> None:
        # Sourcery and CodeAnt on #441: the exchange ends, but past the deadline.
        clock = [0.0]

        class _LateHeaders(_TimedResponse):
            @property
            def headers(self) -> dict[str, str]:
                clock[0] += 10.0
                return {}

        opener = _TimedOpener(_LateHeaders(self._BODY, clock, 0.0))
        with patch("time.monotonic", side_effect=lambda: clock[0]):
            refusal = self._refusal(opener, 5.0)
        self.assertEqual("DEADLINE", refusal.kind)

    def test_a_wrapped_timeout_is_the_deadline(self) -> None:
        class _WrappedTimeout:
            def open(self, _request: object, timeout: float) -> object:
                raise urllib.error.URLError(TimeoutError("timed out"))

        deadline = time.monotonic() + 5.0
        refusal = self._refusal(_WrappedTimeout(), deadline)
        self.assertEqual("DEADLINE", refusal.kind)

    def test_a_request_the_exchange_did_not_send_is_unavailable(self) -> None:
        refused = analyzer_deepsource.github_rest.NotSent("16 earlier requests")
        with patch.object(
            analyzer_deepsource.github_rest, "exchange", side_effect=refused
        ):
            deadline = time.monotonic() + 5.0
            refusal = self._refusal(object(), deadline)
        self.assertEqual("UNAVAILABLE", refusal.kind)

    def test_a_graphql_errors_answer_is_refused(self) -> None:
        # A partial answer, data with errors, is no read, with or without a deadline
        # (round-3 mutant: the decode helper's refusal had no test of its own).
        body = (b'{"data": {"run": null}, "errors": [{"message": "partial"}]}',)
        for deadline in (None, time.monotonic() + 5.0):
            with self.subTest(deadline=deadline):
                client = self._client(_TimedOpener(_TimedResponse(body, [0.0], 0.0)))
                with self.assertRaisesRegex(
                    analyzer_deepsource.ProviderReadFailure, "returned errors"
                ):
                    client.graphql(
                        analyzer_deepsource._RUN_QUERY,
                        {"runUid": "x", "cursor": None},
                        deadline=deadline,
                    )

    def test_an_undecodable_answer_is_an_error_not_a_crash(self) -> None:
        # CodeAnt on #441: json.loads can also raise RecursionError (deep nesting) or a
        # plain ValueError (the integer-digit limit). Each is an unusable answer.
        bodies = {
            "deep nesting": (b"[" * 100_000 + b"]" * 100_000,),
            "an integer past the digit limit": (b'{"data": ' + b"9" * 5_000 + b"}",),
        }
        for label, body in bodies.items():
            for deadline in (None, time.monotonic() + 5.0):
                with self.subTest(body=label, deadline=deadline):
                    client = self._client(
                        _TimedOpener(_TimedResponse(body, [0.0], 0.0))
                    )
                    with self.assertRaises(
                        analyzer_deepsource.ProviderReadFailure
                    ) as raised:
                        client.graphql(
                            analyzer_deepsource._RUN_QUERY,
                            {"runUid": "x", "cursor": None},
                            deadline=deadline,
                        )
                    self.assertEqual("ERROR", raised.exception.kind)


class DeepSourceRequestCeilingTests(unittest.TestCase):
    """CodeAnt 4317340803 on #441, Router 6274471644: under the read deadline each
    request is bounded by the shared owner's `request_timeout`, at most the 30 s
    ceiling and at most the budget left, with no floor. A timeout is `DEADLINE` when
    the budget set the bound, and `UNAVAILABLE` when the ceiling set it and the
    deadline has not passed."""

    _BODY = b'{"data": {"run": null}}'

    def _client(self) -> analyzer_deepsource.DeepSourceGraphQLClient:
        client = analyzer_deepsource.DeepSourceGraphQLClient("test-token")
        client._opener = cast(urllib.request.OpenerDirector, object())
        return client

    def _call(
        self, deadline: float, clock: list[float], answer: Any
    ) -> tuple[Any, analyzer_deepsource.ProviderReadFailure | None]:
        """Run one deadline-bound read with the shared exchange replaced by `answer`
        (a callable taking the limit), on the patched clock. Returns the exchange
        stand-in and the refusal, if any."""
        refusal: analyzer_deepsource.ProviderReadFailure | None = None
        with (
            patch("time.monotonic", side_effect=lambda: clock[0]),
            patch.object(
                github_rest,
                "exchange",
                side_effect=lambda _opener, _request, limit, _policy: answer(limit),
            ) as exchange,
        ):
            try:
                self._client().graphql(
                    analyzer_deepsource._RUN_QUERY,
                    {"runUid": "x", "cursor": None},
                    deadline=deadline,
                )
            except analyzer_deepsource.ProviderReadFailure as failure:
                refusal = failure
        return exchange, refusal

    def _limit(self, budget: float) -> float:
        _exchange, refusal = self._call(budget, [0.0], lambda _limit: (self._BODY, {}))
        self.assertIsNone(refusal)
        limit: float = _exchange.call_args.args[2]
        return limit

    def test_a_long_budget_still_caps_each_request_at_thirty_seconds(self) -> None:
        for budget in (300.0, 45.0):
            with self.subTest(budget=budget):
                self.assertEqual(30.0, self._limit(budget))

    def test_a_short_budget_bounds_the_request_by_what_remains(self) -> None:
        # No floor: a request is never given more than the budget left.
        for budget, expected in ((10.0, 10.0), (30.0, 30.0), (0.05, 0.05)):
            with self.subTest(budget=budget):
                self.assertAlmostEqual(expected, self._limit(budget), places=9)

    def test_the_limit_comes_from_the_shared_owner(self) -> None:
        # The limit and its governing bound come from the shared owner's one
        # observation (#441 R3, Decision 0100 addendum).
        with patch.object(
            github_rest, "request_limit", wraps=github_rest.request_limit
        ) as owner:
            self._limit(300.0)
        owner.assert_called_once_with(300.0, analyzer_deepsource._EXCHANGE_POLICY)

    def test_no_exchange_starts_without_budget(self) -> None:
        for deadline, kind in (
            (0.0, "DEADLINE"),
            (-1.0, "DEADLINE"),
            (float("nan"), "ERROR"),
            (float("inf"), "ERROR"),
        ):
            with self.subTest(deadline=deadline):
                exchange, refusal = self._call(deadline, [0.0], lambda _limit: None)
                if refusal is None:
                    self.fail("the read was not refused")
                self.assertEqual(kind, refusal.kind)
                exchange.assert_not_called()

    def test_a_limit_spent_before_the_exchange_starts_none(self) -> None:
        # The budget is checked, then time passes before the limit is chosen.
        ticks = iter([0.0] + [10.0] * 20)
        client = self._client()
        with (
            patch("time.monotonic", side_effect=lambda: next(ticks)),
            patch.object(
                github_rest, "exchange", return_value=(self._BODY, {})
            ) as exchange,
        ):
            # One call inside the expectation (Sonar S5778).
            with self.assertRaises(analyzer_deepsource.ProviderReadFailure) as raised:
                client.graphql(
                    analyzer_deepsource._RUN_QUERY,
                    {"runUid": "x", "cursor": None},
                    deadline=5.0,
                )
        self.assertEqual("DEADLINE", raised.exception.kind)
        exchange.assert_not_called()

    def _failing(self, error: BaseException, *, at: float | None = None) -> Any:
        """An exchange that fails with `error`, after moving the clock to `at`."""

        def fail(_limit: float) -> None:
            if at is not None:
                self._clock[0] = at
            raise error

        return fail

    def _kind(
        self, deadline: float, error: BaseException, *, at: float | None = None
    ) -> str:
        self._clock = [0.0]
        _exchange, refusal = self._call(
            deadline, self._clock, self._failing(error, at=at)
        )
        if refusal is None:
            self.fail("the read was not refused")
        return refusal.kind

    def test_a_timeout_the_ceiling_set_before_the_deadline_is_unavailable(
        self,
    ) -> None:
        for error in (
            github_rest.GitHubReadError("timed out", in_flight=True),
            TimeoutError("timed out"),
            urllib.error.URLError(TimeoutError("timed out")),
        ):
            with self.subTest(error=type(error).__name__):
                self.assertEqual("UNAVAILABLE", self._kind(300.0, error))

    def test_a_timeout_the_budget_set_is_the_deadline(self) -> None:
        # Including one observed before the absolute instant: the shared exchange's
        # half-budget receive and body stop end early by design (Decision 0100).
        for budget in (10.0, 30.0):
            for error in (
                github_rest.GitHubReadError("timed out", in_flight=True),
                TimeoutError("timed out"),
                urllib.error.URLError(TimeoutError("timed out")),
            ):
                with self.subTest(budget=budget, error=type(error).__name__):
                    self.assertEqual("DEADLINE", self._kind(budget, error))

    def test_a_ceiling_timeout_seen_after_the_deadline_is_the_deadline(self) -> None:
        for error in (
            github_rest.GitHubReadError("timed out", in_flight=True),
            TimeoutError("timed out"),
        ):
            with self.subTest(error=type(error).__name__):
                self.assertEqual("DEADLINE", self._kind(300.0, error, at=301.0))

    def test_other_failures_keep_their_kind(self) -> None:
        for error, kind in (
            (github_rest.NotSent("16 earlier requests"), "UNAVAILABLE"),
            (github_rest.ResponseTooLarge("too large"), "ERROR"),
            (ConnectionResetError("reset"), "UNAVAILABLE"),
        ):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(kind, self._kind(300.0, error))

    def _kind_on(
        self, deadline: float, ticks: list[float], error: BaseException
    ) -> str:
        """The refusal's kind on a clock that reads `ticks` in turn, then holds."""
        reads = iter(ticks)
        last = [ticks[-1]]

        def now() -> float:
            last[0] = next(reads, last[0])
            return last[0]

        refusal: analyzer_deepsource.ProviderReadFailure | None = None
        with (
            patch("time.monotonic", side_effect=now),
            patch.object(github_rest, "exchange", side_effect=error),
        ):
            try:
                self._client().graphql(
                    analyzer_deepsource._RUN_QUERY,
                    {"runUid": "x", "cursor": None},
                    deadline=deadline,
                )
            except analyzer_deepsource.ProviderReadFailure as failure:
                refusal = failure
        if refusal is None:
            self.fail("the read was not refused")
        return refusal.kind

    def test_the_bound_is_the_one_in_force_when_the_limit_was_chosen(self) -> None:
        # Cubic on #441 (4317833156): more than 30 s remained when the limit was
        # chosen, so the ceiling set it, even if less remains a moment later.
        timeout = github_rest.GitHubReadError("timed out", in_flight=True)
        self.assertEqual(
            "UNAVAILABLE", self._kind_on(30.0001, [0.0, 0.00005, 0.0002], timeout)
        )

    def test_a_moving_tie_is_the_budgets(self) -> None:
        # PAO R0-BOUND-SOURCE-01: 30.001 s remained at the adapter's own read, exactly
        # 30.000 at the shared owner's, so the budget set the limit (a tie), and a
        # timeout seen before the deadline is DEADLINE (Router 6274471644).
        for error in (
            github_rest.GitHubReadError("timed out", in_flight=True),
            TimeoutError("timed out"),
            urllib.error.URLError(TimeoutError("timed out")),
        ):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(
                    "DEADLINE", self._kind_on(100.0, [69.999, 70.000, 85.1], error)
                )

    def test_time_passing_while_the_limit_is_chosen_keeps_the_budget_bound(
        self,
    ) -> None:
        # Less than 30 s remained, so the budget set the limit, although the limit
        # is then a little less than the budget first measured.
        timeout = github_rest.GitHubReadError("timed out", in_flight=True)
        self.assertEqual("DEADLINE", self._kind_on(10.0, [0.0, 1.0, 1.0], timeout))

    def test_a_non_timeout_failure_keeps_its_kind_after_the_deadline(self) -> None:
        # Claude on #441 (6275394096, finding 1), Router 6274471644 ("no blanket
        # rewriting of provider errors into timeouts"): a connection failure seen
        # after the deadline is still the transport failing, not the budget.
        for budget, at in ((300.0, 301.0), (10.0, 11.0)):
            for error in (
                ConnectionResetError("reset"),
                http.client.BadStatusLine("garbled"),
            ):
                with self.subTest(budget=budget, error=type(error).__name__):
                    self.assertEqual("UNAVAILABLE", self._kind(budget, error, at=at))


if __name__ == "__main__":
    unittest.main()
