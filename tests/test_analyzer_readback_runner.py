from __future__ import annotations

import importlib.util
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools.analyzer_readback import canonical_json

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "ci" / "analyzer_readback.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "analyzer-readback.yml"
HEAD = "a" * 40
OTHER = "b" * 40
OBSERVED = "2026-09-23T14:00:00Z"
RUN_UID = "0c29b163-9e8e-43be-bd8b-a93254aa2748"

spec = importlib.util.spec_from_file_location("gnostoa_analyzer_runner", RUNNER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("analyzer readback runner module is unavailable")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class _GitHubFake:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, list) and url.endswith("/pulls/312"):
            if not value:
                raise RuntimeError(f"no remaining fake responses for {url}")
            value = value.pop(0)
        return value, {}


def _pr(head: str = HEAD) -> dict[str, Any]:
    return {"head": {"sha": head}}


def _github_urls() -> dict[str, str]:
    root = "https://api.github.com/repos/ktogias/gnostoa"
    return {
        "pr": f"{root}/pulls/312",
        "statuses": f"{root}/commits/{HEAD}/statuses?per_page=100",
        "checks": f"{root}/commits/{HEAD}/check-runs?per_page=100",
        "comments": f"{root}/pulls/312/comments?per_page=100",
    }


def _deepsource_fake() -> Any:
    class Reader:
        def graphql(
            self, query: str, variables: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            if "AnalyzerRun" in query:
                return {
                    "data": {
                        "run": {
                            "id": "run-node",
                            "runUid": RUN_UID,
                            "commitOid": HEAD,
                            "baseOid": "c" * 40,
                            "status": "SUCCESS",
                            "repository": {
                                "name": "gnostoa",
                                "account": {
                                    "login": "ktogias",
                                    "vcsProvider": "GITHUB",
                                },
                            },
                            "checks": {
                                "totalCount": 0,
                                "edges": [],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            },
                        }
                    }
                }
            raise AssertionError("unexpected DeepSource check query")

    return Reader()


class _CodacyReader:
    def get(self, url: str) -> Mapping[str, Any]:
        if url.endswith("/pull-requests/312"):
            return {
                "isUpToStandards": True,
                "isAnalysing": False,
                "pullRequest": {
                    "number": 312,
                    "repository": "gnostoa",
                    "headCommitSha": HEAD,
                    "gitHref": "https://github.com/ktogias/gnostoa/pull/312",
                },
            }
        if "onlyPotential=false" in url or "onlyPotential=true" in url:
            return {"analyzed": True, "data": [], "pagination": {}}
        raise AssertionError(f"unexpected Codacy URL: {url}")


class AnalyzerReadbackRunnerTests(unittest.TestCase):
    def test_repository_segments_reject_path_and_query_injection(self) -> None:
        class _NoNetwork:
            def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
                raise AssertionError(f"network must not be reached: {url}")

        for repository in (
            "owner/..",
            "owner/%2e%2e",
            "owner/repo?per_page=1",
            "owner/repo#fragment",
        ):
            with (
                self.subTest(repository=repository),
                self.assertRaisesRegex(runner.RunnerError, "repository"),
            ):
                runner.collect_bundle(
                    _NoNetwork(),
                    repository=repository,
                    pull_number=312,
                    requested_head=HEAD,
                    deepsource=None,
                    codacy=None,
                    observed_at=OBSERVED,
                )

    def test_head_movement_discards_provider_evidence(self) -> None:
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr(OTHER)],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
            }
        )
        bundle = runner.collect_bundle(
            github,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            deepsource=None,
            codacy=None,
            observed_at=OBSERVED,
        )
        self.assertEqual("INCOMPLETE", bundle["subject_binding"])
        self.assertEqual("GITHUB_SUBJECT_CHANGED_DURING_READBACK", bundle["reason"])
        self.assertEqual(OTHER, bundle["observed_head"])
        self.assertEqual([], bundle["readbacks"])

    def test_check_run_can_supply_deepsource_run_association(self) -> None:
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {
                    "check_runs": [
                        {
                            "name": "DeepSource: Python",
                            "status": "completed",
                            "conclusion": "success",
                            "details_url": (
                                "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                                f"{RUN_UID}/python/"
                            ),
                            "app": {"slug": "deepsource-io"},
                        }
                    ]
                },
                urls["comments"]: [],
            }
        )
        bundle = runner.collect_bundle(
            github,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            deepsource=_deepsource_fake(),
            codacy=_CodacyReader(),
            observed_at=OBSERVED,
        )
        self.assertEqual("BOUND", bundle["subject_binding"])
        readbacks = {item["adapter"]: item for item in bundle["readbacks"]}
        self.assertEqual(
            RUN_UID,
            readbacks["deepsource-github/v1"]["analysis_id"],
        )
        self.assertEqual(
            "DIFF_LOCAL",
            readbacks["deepsource-github/v1"]["completeness"],
        )
        self.assertEqual(
            "FULL_RUN",
            readbacks["deepsource-graphql/v1"]["completeness"],
        )
        self.assertEqual(
            "COMPLETE",
            readbacks["deepsource-graphql/v1"]["coverage"]["status"],
        )
        self.assertEqual(
            "FULL_RUN",
            readbacks["codacy-api-v3/v1"]["completeness"],
        )

    def test_missing_provider_tokens_are_explicit_not_clean(self) -> None:
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
            }
        )
        bundle = runner.collect_bundle(
            github,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            deepsource=None,
            codacy=None,
            observed_at=OBSERVED,
        )
        self.assertEqual("BOUND", bundle["subject_binding"])
        readbacks = {item["adapter"]: item for item in bundle["readbacks"]}
        self.assertEqual(
            "AUTH_UNAVAILABLE",
            readbacks["deepsource-graphql/v1"]["completeness"],
        )
        self.assertEqual(
            "UNAVAILABLE", readbacks["deepsource-graphql/v1"]["coverage"]["status"]
        )
        self.assertEqual(
            "AUTH_UNAVAILABLE",
            readbacks["deepsource-graphql/v1"]["coverage"]["reason"],
        )
        self.assertEqual(
            "AUTH_UNAVAILABLE",
            readbacks["codacy-api-v3/v1"]["completeness"],
        )
        self.assertEqual(
            "UNAVAILABLE", readbacks["codacy-api-v3/v1"]["coverage"]["status"]
        )
        self.assertNotIn("observed_head", readbacks["deepsource-graphql/v1"])
        self.assertNotIn("observed_head", readbacks["codacy-api-v3/v1"])

    def test_missing_deepsource_run_association_does_not_invent_observed_head(
        self,
    ) -> None:
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
            }
        )
        bundle = runner.collect_bundle(
            github,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            deepsource=_deepsource_fake(),
            codacy=None,
            observed_at=OBSERVED,
        )
        readbacks = {item["adapter"]: item for item in bundle["readbacks"]}
        full = readbacks["deepsource-graphql/v1"]
        self.assertEqual("AMBIGUOUS", full["completeness"])
        self.assertEqual("INCOMPLETE", full["coverage"]["status"])
        self.assertEqual("RUN_ASSOCIATION_AMBIGUOUS", full["coverage"]["reason"])
        self.assertNotIn("observed_head", full)

    def test_secret_sentinel_is_rejected_before_output(self) -> None:
        with self.assertRaisesRegex(runner.RunnerError, "credential bytes"):
            runner._assert_secret_free(
                canonical_json({"value": "prefix-super-secret-suffix"}),
                ["super-secret"],
            )

    def test_output_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "readback.json"
            runner._write_create_only(output, "{}")
            with self.assertRaisesRegex(runner.RunnerError, "already exists"):
                runner._write_create_only(output, "{}")

    def test_guardrail_owns_all_analyzer_readback_surfaces(self) -> None:
        manifest = (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        marker = "  - id: authenticated-analyzer-readback"
        self.assertIn(marker, manifest)
        section = manifest.split(marker, 1)[1].split("\n  - id:", 1)[0]
        for path in (
            "tools/analyzer_readback.py",
            "tools/analyzer_deepsource.py",
            "tools/analyzer_codacy.py",
            "ci/analyzer_readback.py",
            ".github/workflows/analyzer-readback.yml",
            "tests/test_analyzer_readback.py",
            "tests/test_analyzer_readback_runner.py",
        ):
            self.assertIn(path, section)

    def test_workflow_is_manual_read_only_and_secrets_are_step_scoped(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        for permission in (
            "contents: read",
            "pull-requests: read",
            "statuses: read",
            "checks: read",
        ):
            self.assertIn(permission, workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull-requests: write", workflow)
        self.assertIn("timeout-minutes: 15", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(
            "DEEPSOURCE_API_TOKEN: ${{ secrets.DEEPSOURCE_API_TOKEN }}", workflow
        )
        self.assertIn("CODACY_API_TOKEN: ${{ secrets.CODACY_API_TOKEN }}", workflow)
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            workflow,
        )
        self.assertIn("PULL_NUMBER: ${{ inputs.pull_number }}", workflow)
        self.assertIn("REQUESTED_HEAD: ${{ inputs.head }}", workflow)
        self.assertIn('--pull-number "${PULL_NUMBER}"', workflow)
        self.assertIn('--head "${REQUESTED_HEAD}"', workflow)
        self.assertNotIn("--head '${{ inputs.head }}'", workflow)
        self.assertIn("gnostoa-analyzer-readback.json", workflow)


if __name__ == "__main__":
    unittest.main()
