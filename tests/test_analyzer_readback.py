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
from typing import Any
from unittest.mock import patch

from tools import analyzer_codacy, analyzer_deepsource, analyzer_readback

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
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
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
            hashlib.sha256(canonical).hexdigest(), receipt["configuration"]["sha256"]
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
        # The repository state was never read whole, so its configuration is
        # neither present nor absent.
        self.assertEqual({"state": "UNREAD"}, receipt["configuration"])

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
        response = http.client.HTTPResponse(
            _DripSocket(self.data, self.slow_from, self.delay)  # type: ignore[arg-type]
        )
        response.begin()
        return response


class DeepSourceClientDeadlineTests(unittest.TestCase):
    """The client's optional deadline (#389 F3 R0, Router 6267325366): absent, every
    existing read is unchanged; given, it bounds the connection and the body."""

    _BODY = (b'{"data": ', b'{"run": null}}')

    def _client(self, opener: object) -> analyzer_deepsource.DeepSourceGraphQLClient:
        client = analyzer_deepsource.DeepSourceGraphQLClient("test-token")
        client._opener = opener  # type: ignore[assignment]
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


if __name__ == "__main__":
    unittest.main()
