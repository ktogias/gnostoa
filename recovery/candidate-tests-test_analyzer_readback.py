from __future__ import annotations

import http.client
import inspect
import io
import json
import unittest
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

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


if __name__ == "__main__":
    unittest.main()
