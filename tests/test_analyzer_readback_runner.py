from __future__ import annotations

import contextlib
import http.client
import importlib.util
import io
import os
import tempfile
import traceback
import unittest
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
                                "totalCount": 1,
                                "edges": [
                                    {
                                        "node": {
                                            "id": "check-python",
                                            "status": "SUCCESS",
                                            "analyzer": {"shortcode": "python"},
                                        }
                                    }
                                ],
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "endCursor": None,
                                },
                            },
                        }
                    }
                }
            if "AnalyzerCheckIssues" in query:
                return {
                    "data": {
                        "node": {
                            "id": "check-python",
                            "status": "SUCCESS",
                            "analyzer": {"shortcode": "python"},
                            "issues": {
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


class AnalyzerTransportCredentialTests(unittest.TestCase):
    def test_github_redirect_preserves_same_origin_credentials(self) -> None:
        client = runner.GitHubReadClient("synthetic-transport-value")
        handlers = [
            handler
            for handler in client._opener.handlers
            if isinstance(handler, runner._GitHubRedirectHandler)
        ]
        self.assertEqual(1, len(handlers))
        request = urllib.request.Request("https://api.github.com/start")
        request.add_unredirected_header(
            "Authorization", "Bearer synthetic-transport-value"
        )
        for target in (
            "https://api.github.com/next",
            "https://api.github.com:443/next",
            "https://API.GITHUB.COM/next",
        ):
            with self.subTest(target=target):
                redirected = handlers[0].redirect_request(
                    request, None, 302, "Found", {}, target
                )
                self.assertIsNotNone(redirected)
                assert redirected is not None
                self.assertEqual(target, redirected.full_url)
                self.assertEqual(
                    "Bearer synthetic-transport-value",
                    redirected.get_header("Authorization"),
                )

    def test_github_redirect_refuses_unsafe_origins(self) -> None:
        handler = runner._GitHubRedirectHandler()
        request = urllib.request.Request("https://api.github.com/start")
        request.add_unredirected_header(
            "Authorization", "Bearer synthetic-transport-value"
        )
        for target in (
            "https://example.invalid/next",
            "https://api.github.com.evil.example/next",
            "https://api.github.com@evil.example/next",
            "http://api.github.com/next",
            "https://api.github.com:8443/next",
            "https://api.github.com:not-a-port/next",
            "https://api.github.com/next#fragment",
            "https://u:p@api.github.com/next",
        ):
            with self.subTest(target=target), self.assertRaises(runner.RunnerError):
                handler.redirect_request(request, None, 302, "Found", {}, target)

    def test_malformed_credentials_do_not_echo_through_real_http_headers(self) -> None:
        cases = (
            (
                runner.GitHubReadClient,
                lambda c: c.get(
                    "https://api.github.com/repos/ktogias/gnostoa/pulls/312"
                ),
                runner.RunnerError,
            ),
            (
                runner.analyzer_deepsource.DeepSourceGraphQLClient,
                lambda c: c.graphql(
                    runner.analyzer_deepsource._RUN_QUERY,
                    {"runUid": RUN_UID, "cursor": None},
                ),
                runner.analyzer_deepsource.ProviderReadFailure,
            ),
            (
                runner.analyzer_codacy.CodacyRestClient,
                lambda c: c.get(
                    "https://app.codacy.com/api/v3/analysis/organizations/gh/ktogias/repositories/gnostoa/pull-requests/312"
                ),
                runner.analyzer_codacy.ProviderReadFailure,
            ),
        )
        for factory, invoke, error_type in cases:
            for suffix in ("\n", "\r"):
                with self.subTest(client=factory.__name__, suffix=repr(suffix)):
                    value = "synthetic-malformed-credential" + suffix
                    with (
                        patch.dict(os.environ, {}, clear=True),
                        patch.object(
                            http.client.HTTPSConnection,
                            "connect",
                            side_effect=AssertionError("network forbidden"),
                        ) as connect,
                    ):
                        try:
                            invoke(factory(value))
                        except Exception as exc:
                            rendered = "".join(traceback.format_exception(exc))
                            self.assertNotIn("synthetic-malformed-credential", rendered)
                            self.assertIsInstance(exc, error_type)
                        else:
                            self.fail("malformed credential was accepted")
                        connect.assert_not_called()

    def test_credential_validation_rejects_without_trimming_or_opener(self) -> None:
        for factory, error_type in (
            (runner.GitHubReadClient, runner.RunnerError),
            (
                runner.analyzer_deepsource.DeepSourceGraphQLClient,
                runner.analyzer_deepsource.ProviderReadFailure,
            ),
            (
                runner.analyzer_codacy.CodacyRestClient,
                runner.analyzer_codacy.ProviderReadFailure,
            ),
        ):
            for value in (
                " x",
                "x ",
                "x\ty",
                "x\x00y",
                "x\x7fy",
                "x\xffy",
                "x\u2603y",
                "x\ud800y",
            ):
                with self.subTest(client=factory.__name__, value=repr(value)):
                    with patch("urllib.request.build_opener") as opener:
                        with self.assertRaises(error_type) as caught:
                            factory(value)
                        self.assertNotIn(repr(value), str(caught.exception))
                        opener.assert_not_called()
            value = "aZ0._~+/=-!"
            client = factory(value)
            self.assertEqual(value, client._token)

    def test_transport_value_errors_have_bounded_non_secret_diagnostics(self) -> None:
        cases = (
            (
                runner.GitHubReadClient,
                lambda c: c.get("https://api.github.com/start"),
                runner.RunnerError,
            ),
            (
                runner.analyzer_deepsource.DeepSourceGraphQLClient,
                lambda c: c.graphql(
                    runner.analyzer_deepsource._RUN_QUERY, {"runUid": RUN_UID}
                ),
                runner.analyzer_deepsource.ProviderReadFailure,
            ),
            (
                runner.analyzer_codacy.CodacyRestClient,
                lambda c: c.get("https://app.codacy.com/api/v3/start"),
                runner.analyzer_codacy.ProviderReadFailure,
            ),
        )
        for factory, invoke, error_type in cases:
            with self.subTest(client=factory.__name__):
                value = "synthetic-transport-credential"
                client = factory(value)
                with patch.object(
                    client._opener, "open", side_effect=ValueError("header " + value)
                ):
                    try:
                        invoke(client)
                    except Exception as exc:
                        self.assertNotIn(
                            value, "".join(traceback.format_exception(exc))
                        )
                        self.assertIsInstance(exc, error_type)
                    else:
                        self.fail("transport failure was accepted")

    def test_main_malformed_github_credentials_do_not_enter_stderr(self) -> None:
        for name in ("GITHUB_TOKEN", "GH_TOKEN"):
            for suffix in ("\n", "\r"):
                with (
                    self.subTest(name=name, suffix=repr(suffix)),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    output = Path(directory) / "readback.json"
                    stderr, stdout = io.StringIO(), io.StringIO()
                    with (
                        patch.dict(
                            os.environ,
                            {name: "synthetic-main-credential" + suffix},
                            clear=True,
                        ),
                        patch.object(
                            http.client.HTTPSConnection,
                            "connect",
                            side_effect=AssertionError("network forbidden"),
                        ) as connect,
                        contextlib.redirect_stderr(stderr),
                        contextlib.redirect_stdout(stdout),
                    ):
                        result = runner.main(
                            [
                                "--repository",
                                "ktogias/gnostoa",
                                "--pull-number",
                                "312",
                                "--head",
                                HEAD,
                                "--output",
                                str(output),
                            ]
                        )
                    self.assertEqual(2, result)
                    self.assertFalse(output.exists())
                    self.assertNotIn(
                        "synthetic-main-credential",
                        stderr.getvalue() + stdout.getvalue(),
                    )
                    self.assertTrue(stderr.getvalue().startswith("ERROR: "))
                    connect.assert_not_called()

    def test_malformed_optional_credential_keeps_valid_peer_readback(self) -> None:
        for provider, token_name, peer_type, peer in (
            (
                "deepsource",
                "DEEPSOURCE_API_TOKEN",
                runner.analyzer_codacy.CodacyRestClient,
                _CodacyReader(),
            ),
            (
                "codacy",
                "CODACY_API_TOKEN",
                runner.analyzer_deepsource.DeepSourceGraphQLClient,
                _deepsource_fake(),
            ),
        ):
            with (
                self.subTest(provider=provider),
                tempfile.TemporaryDirectory() as directory,
            ):
                urls = _github_urls()
                github = _GitHubFake(
                    {
                        urls["pr"]: [_pr(), _pr()],
                        urls["statuses"]: [
                            {
                                "context": "DeepSource: Python",
                                "state": "success",
                                "target_url": "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                                + RUN_UID
                                + "/python/",
                                "creator": {
                                    "login": "deepsource-io[bot]",
                                    "type": "Bot",
                                },
                            }
                        ],
                        urls["checks"]: {"check_runs": []},
                        urls["comments"]: [],
                    }
                )
                output = Path(directory) / "readback.json"
                stderr, stdout = io.StringIO(), io.StringIO()
                with (
                    patch.dict(
                        os.environ,
                        {token_name: "synthetic-optional-credential\n"},
                        clear=True,
                    ),
                    patch.object(
                        runner.GitHubReadClient, "from_environment", return_value=github
                    ),
                    patch.object(peer_type, "from_environment", return_value=peer),
                    patch.object(
                        http.client.HTTPSConnection,
                        "connect",
                        side_effect=AssertionError("network forbidden"),
                    ) as connect,
                    contextlib.redirect_stderr(stderr),
                    contextlib.redirect_stdout(stdout),
                ):
                    result = runner.main(
                        [
                            "--repository",
                            "ktogias/gnostoa",
                            "--pull-number",
                            "312",
                            "--head",
                            HEAD,
                            "--output",
                            str(output),
                        ]
                    )
                self.assertEqual(0, result)
                serialized = output.read_text()
                self.assertNotIn(
                    "synthetic-optional-credential",
                    serialized + stderr.getvalue() + stdout.getvalue(),
                )
                document = runner.json.loads(serialized)
                self.assertEqual("BOUND", document["subject_binding"])
                readbacks = {
                    item["provider"]: item
                    for item in document["readbacks"]
                    if item["adapter"] != "deepsource-github/v1"
                }
                self.assertEqual(
                    "AUTH_UNAVAILABLE", readbacks[provider]["completeness"]
                )
                other = "codacy" if provider == "deepsource" else "deepsource"
                self.assertEqual("FULL_RUN", readbacks[other]["completeness"])
                connect.assert_not_called()


class AnalyzerReadbackRunnerTests(unittest.TestCase):
    def test_github_client_maps_http_protocol_failure_to_runner_error(self) -> None:
        client = runner.GitHubReadClient("test-token")

        class _IncompleteReadOpener:
            def open(self, *_args: object, **_kwargs: object) -> object:
                raise http.client.IncompleteRead(b"")

        client._opener = _IncompleteReadOpener()  # type: ignore[assignment]
        with self.assertRaisesRegex(runner.RunnerError, "GitHub API unavailable"):
            client.get("https://api.github.com/repos/ktogias/gnostoa/pulls/312")

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

    def test_deepsource_comment_projection_retains_original_commit_identity(
        self,
    ) -> None:
        projected = runner._deepsource_comments(
            [
                {
                    "body": "finding",
                    "path": "tools/example.py",
                    "line": 7,
                    "commit_id": HEAD,
                    "original_commit_id": OTHER,
                    "html_url": "https://github.com/ktogias/gnostoa/pull/312#discussion",
                    "user": {"login": "deepsource-io[bot]", "type": "Bot"},
                }
            ]
        )
        self.assertEqual(HEAD, projected[0]["commit_id"])
        self.assertEqual(OTHER, projected[0]["original_commit_id"])

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

    def test_projection_normalization_failure_still_drives_full_run_readback(
        self,
    ) -> None:
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [
                    {
                        "context": "DeepSource: Python",
                        "state": "success",
                        "target_url": (
                            "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
                            f"{RUN_UID}/python/"
                        ),
                        "creator": {
                            "login": "deepsource-io[bot]",
                            "type": "Bot",
                        },
                    }
                ],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [
                    {
                        "body": "<!-- DeepSource: id=conflict -->\n<h3>First title</h3>",
                        "path": "tools/example.py",
                        "line": 7,
                        "commit_id": HEAD,
                        "original_commit_id": HEAD,
                        "html_url": "https://github.com/ktogias/gnostoa/pull/312#discussion_1",
                        "user": {"login": "deepsource-io[bot]", "type": "Bot"},
                    },
                    {
                        "body": "<!-- DeepSource: id=conflict -->\n<h3>Different title</h3>",
                        "path": "tools/other.py",
                        "line": 7,
                        "commit_id": HEAD,
                        "original_commit_id": HEAD,
                        "html_url": "https://github.com/ktogias/gnostoa/pull/312#discussion_2",
                        "user": {"login": "deepsource-io[bot]", "type": "Bot"},
                    },
                ],
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
        readbacks = {item["adapter"]: item for item in bundle["readbacks"]}
        diff_local = readbacks["deepsource-github/v1"]
        full = readbacks["deepsource-graphql/v1"]
        self.assertEqual("READBACK_UNAVAILABLE", diff_local["completeness"])
        self.assertEqual("NORMALIZATION_ERROR", diff_local["coverage"]["reason"])
        self.assertEqual(RUN_UID, diff_local["analysis_id"])
        self.assertEqual("FULL_RUN", full["completeness"])
        self.assertEqual("COMPLETE", full["coverage"]["status"])

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
        self.assertIn("if: github.ref == 'refs/heads/main'", workflow)
        self.assertIn("environment: analyzer-readback", workflow)
        self.assertIn("ref: ${{ github.sha }}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("Bind trusted main execution source", workflow)
        self.assertIn("EXECUTOR_REF: ${{ github.ref }}", workflow)
        self.assertIn("EXECUTOR_SHA: ${{ github.sha }}", workflow)
        self.assertIn('test "${EXECUTOR_REF}" = "refs/heads/main"', workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "${EXECUTOR_SHA}"', workflow)
        bind = workflow.index("Bind trusted main execution source")
        secrets = workflow.index("DEEPSOURCE_API_TOKEN")
        self.assertLess(bind, secrets)
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
