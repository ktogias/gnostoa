from __future__ import annotations

import contextlib
import hashlib
import http.client
import importlib.util
import io
import json
import os
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import tempfile
import traceback
import unittest
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import yaml

from tools import analyzer_readback, github_events
from tools.analyzer_readback import canonical_json

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "ci" / "analyzer_readback.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "analyzer-readback.yml"
HEAD = "a" * 40
OTHER = "b" * 40
OBSERVED = "2026-09-23T14:00:00Z"
# SonarCloud's credential variable, by name only (Codacy's Bandit B105 on #424).
SONAR_ENV = "SONAR_TOKEN"
RUN_UID = "0c29b163-9e8e-43be-bd8b-a93254aa2748"

spec = importlib.util.spec_from_file_location("gnostoa_analyzer_runner", RUNNER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("analyzer readback runner module is unavailable")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

SUBJECT_PATH = ROOT / "ci" / "analyzer_readback_subject.py"
subject_spec = importlib.util.spec_from_file_location(
    "gnostoa_analyzer_readback_subject", SUBJECT_PATH
)
if subject_spec is None or subject_spec.loader is None:
    raise RuntimeError("analyzer readback subject resolver is unavailable")
subject_resolver = importlib.util.module_from_spec(subject_spec)
subject_spec.loader.exec_module(subject_resolver)


class _GitHubFake:
    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
        self.calls.append(url)
        value = self.responses[url]
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, list) and url.endswith("/pulls/312"):
            if not value:
                raise RuntimeError(f"no remaining fake responses for {url}")
            value = value.pop(0)
        return value, {}


def _pr(head: str = HEAD) -> dict[str, Any]:
    return {"head": {"sha": head}}


def _unavailable_inventory_document(
    directory: str,
) -> tuple[Path, str, list[dict[str, Any]]]:
    """A document as the inventory job writes it when its collection failed: its
    path, its SHA-256 and its two UNAVAILABLE readbacks."""
    from tools import analyzer_inventory

    recorded = analyzer_inventory.unavailable(
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        observed_at=OBSERVED,
        reason="QualityEvidenceError",
    )
    document = Path(directory) / "gnostoa-inventory-readback.json"
    document.write_text(
        canonical_json(
            {
                "schema": runner.INVENTORY_SCHEMA,
                "repository": "ktogias/gnostoa",
                "pull_number": 312,
                "requested_head": HEAD,
                "observed_at": OBSERVED,
                "base_tip": OTHER,
                "base": OTHER,
                "inventory": None,
                "readbacks": recorded,
            }
        ),
        encoding="utf-8",
    )
    return document, hashlib.sha256(document.read_bytes()).hexdigest(), recorded


def _github_urls() -> dict[str, str]:
    root = "https://api.github.com/repos/ktogias/gnostoa"
    return {
        "pr": f"{root}/pulls/312",
        "statuses": f"{root}/commits/{HEAD}/statuses?per_page=100",
        "checks": f"{root}/commits/{HEAD}/check-runs?per_page=100",
        "comments": f"{root}/pulls/312/comments?per_page=50",
        # Every SonarCloud run on the head, not only the latest (1b.3c).
        "sonar_checks": (
            f"{root}/commits/{HEAD}/check-runs?app_id=12526"
            "&check_name=SonarCloud+Code+Analysis&filter=all&per_page=100"
        ),
    }


def _deepsource_fake() -> Any:
    class Reader:
        @staticmethod
        def graphql(query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
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
    @staticmethod
    def get(url: str) -> Mapping[str, Any]:
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


# A client factory, the call that drives it, and the error it must fail with: typed, so
# each invocation is a typed call rather than an untyped lambda's (DeepSource TYP-061).
_InvokeCase = tuple[Callable[[str], Any], Callable[[Any], Any], type[Exception]]


class AnalyzerTransportCredentialTests(unittest.TestCase):
    def test_github_redirect_preserves_same_origin_credentials(self) -> None:
        client = runner.GitHubReadClient("synthetic-transport-value")
        handlers = [
            handler
            # skipcq: PYL-W0212 -- white-box test of the runner's internals
            for handler in client._opener.handlers
            # skipcq: PYL-W0212 -- white-box test of the runner's internals
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
                if redirected is None:
                    self.fail("same-origin redirect was refused")
                self.assertEqual(target, redirected.full_url)
                self.assertEqual(
                    "Bearer synthetic-transport-value",
                    redirected.get_header("Authorization"),
                )

    def test_github_redirect_refuses_unsafe_origins(self) -> None:
        # skipcq: PYL-W0212 -- white-box test of the runner's internals
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

    def test_github_client_rejects_oversized_response_after_bounded_read(self) -> None:
        response_limit = 32

        class _OversizedResponse(io.BytesIO):
            def __init__(self) -> None:
                super().__init__(b"x" * (response_limit + 1))
                self.headers: dict[str, str] = {}
                self.requested_read_size: int | None = None
                self.consumed = 0

            def read(self, size: int | None = -1) -> bytes:
                self.requested_read_size = size
                chunk = super().read(size)
                self.consumed += len(chunk)
                return chunk

            def read1(self, size: int | None = -1) -> bytes:
                chunk = super().read1(size)
                self.consumed += len(chunk)
                return chunk

        client = runner.GitHubReadClient("test-token")
        response = _OversizedResponse()
        with (
            patch.object(runner, "_MAX_RESPONSE_BYTES", response_limit),
            # skipcq: PYL-W0212 -- white-box test of the runner's internals
            patch.object(client._opener, "open", return_value=response) as open_request,
            self.assertRaisesRegex(
                runner.RunnerError,
                "GitHub API response exceeds bounded size",
            ),
        ):
            client.get("https://api.github.com/repos/ktogias/gnostoa/pulls/312")

        # Refused, and read no further than one receive past the bound: the shared
        # client reads in single receives (Decision 0100), so the property held here
        # is the bound on what was read, not the size of one call.
        self.assertLessEqual(response.consumed, response_limit + 65536)
        open_request.assert_called_once()

    def test_malformed_credentials_do_not_echo_through_real_http_headers(self) -> None:
        cases: tuple[_InvokeCase, ...] = (
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
                    runner.analyzer_deepsource.RUN_QUERY,
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
                with (
                    self.subTest(client=factory.__name__, value=repr(value)),
                    patch("urllib.request.build_opener") as opener,
                ):
                    with self.assertRaises(error_type) as caught:
                        factory(value)
                    self.assertNotIn(repr(value), str(caught.exception))
                    opener.assert_not_called()
            value = "aZ0._~+/=-!"
            client = factory(value)
            # skipcq: PYL-W0212 -- white-box test of the runner's internals
            self.assertEqual(value, client._token)

    def test_transport_value_errors_have_bounded_non_secret_diagnostics(self) -> None:
        cases: tuple[_InvokeCase, ...] = (
            (
                runner.GitHubReadClient,
                lambda c: c.get("https://api.github.com/start"),
                runner.RunnerError,
            ),
            (
                runner.analyzer_deepsource.DeepSourceGraphQLClient,
                lambda c: c.graphql(
                    runner.analyzer_deepsource.RUN_QUERY,
                    {"runUid": RUN_UID},
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
                    # skipcq: PYL-W0212 -- white-box test of the runner's internals
                    client._opener,
                    "open",
                    side_effect=ValueError("header " + value),
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

    def test_the_readback_step_says_whether_it_wrote_a_receipt(self) -> None:
        """The step keeps the runner's status, and says `receipt=written` only when
        the receipt exists: a runner that fails before writing one leaves nothing
        to upload (Claude on #388)."""
        loaded = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        [step] = [
            step
            for step in loaded["jobs"]["readback"]["steps"]
            if step.get("id") == "readback"
        ]
        for status, writes, said in (
            (0, True, True),
            (1, True, True),
            (2, False, False),
        ):
            with (
                self.subTest(status=status),
                tempfile.TemporaryDirectory() as directory,
            ):
                scratch = Path(directory)
                stubs = scratch / "bin"
                stubs.mkdir()
                stub = stubs / "python"
                touch = 'touch "${RUNNER_TEMP}/gnostoa-analyzer-readback.json"\n'
                stub.write_text(
                    "#!/bin/sh\n" + (touch if writes else "") + f"exit {status}\n",
                    encoding="utf-8",
                )
                stub.chmod(0o755)
                output = scratch / "output"
                output.touch()
                # The script travels on stdin to an absolute shell, as the Claude
                # workflows' step harnesses do, so the argv is static: the step under
                # test is the repository's own committed text, not an input.
                result = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                    ["/bin/sh", "-s"],
                    input=step["run"],
                    cwd=ROOT,
                    env={
                        "PATH": f"{stubs}:/usr/bin:/bin",
                        "RUNNER_TEMP": str(scratch),
                        "GITHUB_OUTPUT": str(output),
                        "GITHUB_REPOSITORY": "ktogias/gnostoa",
                        "PULL_NUMBER": "312",
                        "REQUESTED_HEAD": HEAD,
                        # The inventory job's outputs (#389 A0-MP1 slice 3), and
                        # the attempts the runner compares (Cubic on #461).
                        "INVENTORY_RESULT": "success",
                        "INVENTORY_SHA256": "0" * 64,
                        "INVENTORY_ATTEMPT": "1",
                        "RUN_ATTEMPT": "1",
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                    # A step that blocks fails the test rather than hanging the suite
                    # (Kody on #388).
                    timeout=60,
                )
                self.assertEqual(status, result.returncode, result.stderr)
                self.assertEqual(
                    "receipt=written\n" if said else "",
                    output.read_text(encoding="utf-8"),
                )

    def test_main_fails_visibly_when_the_receipt_binds_no_exact_head(self) -> None:
        """A receipt that binds no exact head is written, so its reason stays
        readable, and fails the run: a green run without exact-head evidence would
        make missing evidence look like a clean producer (Kody on #388, #389)."""
        urls = _github_urls()
        for reason, routes in (
            ("GITHUB_SUBJECT_MISMATCH", {urls["pr"]: [_pr(OTHER)]}),
            (
                "GITHUB_SUBJECT_CHANGED_DURING_READBACK",
                {
                    urls["pr"]: [_pr(), _pr(OTHER)],
                    urls["statuses"]: [],
                    urls["checks"]: {"check_runs": []},
                    urls["comments"]: [],
                },
            ),
        ):
            with (
                self.subTest(reason=reason),
                tempfile.TemporaryDirectory() as directory,
            ):
                output = Path(directory) / "readback.json"
                stderr = io.StringIO()
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(
                        runner.GitHubReadClient,
                        "from_environment",
                        return_value=_GitHubFake(routes),
                    ),
                    patch.object(
                        http.client.HTTPSConnection,
                        "connect",
                        side_effect=AssertionError("network forbidden"),
                    ),
                    contextlib.redirect_stderr(stderr),
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
                self.assertEqual(1, result)
                bundle = json.loads(output.read_text())
                self.assertEqual("INCOMPLETE", bundle["subject_binding"])
                self.assertEqual(reason, bundle["reason"])
                self.assertEqual(
                    f"ERROR: the readback binds no exact head ({reason});"
                    " its receipt records why\n",
                    stderr.getvalue(),
                )

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
                document = json.loads(serialized)
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
    def test_the_bundle_schema_is_the_reader_s(self) -> None:
        self.assertEqual(analyzer_readback.BUNDLE_SCHEMA, runner.BUNDLE_SCHEMA)

    def test_review_comment_pages_fit_bound_and_retain_all_comments(self) -> None:
        endpoint = "https://api.github.com/repos/ktogias/gnostoa/pulls/312/comments"
        total_comments = 234

        class _BoundedReviewCommentPages:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
                self.calls.append(url)
                query = parse_qs(urlsplit(url).query)
                page_size = int(query["per_page"][0])
                page = int(query.get("page", ["1"])[0])
                start = (page - 1) * page_size
                stop = min(start + page_size, total_comments)
                comments = [
                    {"body": "x" * 45_000, "id": comment_id}
                    for comment_id in range(start, stop)
                ]
                response_size = len(json.dumps(comments).encode("utf-8"))
                # skipcq: PYL-W0212 -- the runner's own bound, read by this white-box stub
                if response_size > runner._MAX_RESPONSE_BYTES:
                    raise runner.RunnerError("GitHub API response exceeds bounded size")
                headers: dict[str, str] = {}
                if stop < total_comments:
                    headers["link"] = (
                        f'<{endpoint}?per_page={page_size}&page={page + 1}>; rel="next"'
                    )
                return comments, headers

        client = _BoundedReviewCommentPages()
        # skipcq: PYL-W0212 -- white-box test of the runner's internals
        comments = runner._review_comments(client, "ktogias/gnostoa", 312)

        self.assertEqual(list(range(total_comments)), [item["id"] for item in comments])
        self.assertEqual(5, len(client.calls))
        self.assertTrue(
            all(
                parse_qs(urlsplit(url).query)["per_page"] == ["50"]
                for url in client.calls
            )
        )

    def test_github_client_maps_http_protocol_failure_to_runner_error(self) -> None:
        client = runner.GitHubReadClient("test-token")

        class _IncompleteReadOpener:
            @staticmethod
            def open(*_args: object, **_kwargs: object) -> object:
                raise http.client.IncompleteRead(b"")

        # skipcq: PYL-W0212 -- white-box test of the runner's internals
        client._opener = _IncompleteReadOpener()  # type: ignore[assignment]
        with self.assertRaisesRegex(runner.RunnerError, "GitHub API unavailable"):
            client.get("https://api.github.com/repos/ktogias/gnostoa/pulls/312")

    def test_repository_segments_reject_path_and_query_injection(self) -> None:
        class _NoNetwork:
            @staticmethod
            def get(url: str) -> tuple[Any, Mapping[str, str]]:
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
                    sonarcloud=None,
                    observed_at=OBSERVED,
                )

    def test_a_requested_head_that_is_no_exact_sha_is_refused(self) -> None:
        """The runner refuses before it reads anything, with its own error: one
        exact-SHA check, the readback's, serves it and the resolver (Claude on
        #388)."""

        class _NoNetwork:
            @staticmethod
            def get(url: str) -> tuple[Any, Mapping[str, str]]:
                raise AssertionError(f"network must not be reached: {url}")

        # Built before the assertion, so the readback is its only call (SonarCloud
        # S5778 on #388).
        network = _NoNetwork()
        for head in ("A" * 40, "a" * 39, HEAD + "\n", "", None, 40):
            with (
                self.subTest(head=head),
                self.assertRaisesRegex(runner.RunnerError, "exact 40-character SHA"),
            ):
                runner.collect_bundle(
                    network,
                    repository="ktogias/gnostoa",
                    pull_number=312,
                    requested_head=head,
                    deepsource=None,
                    codacy=None,
                    sonarcloud=None,
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
            sonarcloud=None,
            observed_at=OBSERVED,
        )
        self.assertEqual("INCOMPLETE", bundle["subject_binding"])
        self.assertEqual("GITHUB_SUBJECT_CHANGED_DURING_READBACK", bundle["reason"])
        self.assertEqual(OTHER, bundle["observed_head"])
        self.assertEqual([], bundle["readbacks"])

    def test_deepsource_comment_projection_retains_original_commit_identity(
        self,
    ) -> None:
        # skipcq: PYL-W0212 -- white-box test of the runner's internals
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
            sonarcloud=None,
            observed_at=OBSERVED,
        )
        self.assertEqual("BOUND", bundle["subject_binding"])
        # The merge-evidence reader accepts the producer's own bundle unchanged
        # (1b.3b-2, #407 6101607240).
        recorded = json.loads(canonical_json(bundle))
        self.assertEqual(recorded, analyzer_readback.parse_bundle(recorded))
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
            sonarcloud=None,
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

    def test_the_bundle_carries_the_inventory_s_two_readbacks(self) -> None:
        """#389 A0-MP1 slice 3 (r4, 6399931352): given the inventory job's outputs,
        the bundle adds the document's two project readbacks after the vendors',
        bound to the head's tree as GitHub reads it; a job that did not succeed adds
        both UNAVAILABLE. The merge-evidence reader accepts either bundle."""
        urls = _github_urls()
        commit = f"https://api.github.com/repos/ktogias/gnostoa/commits/{HEAD}"
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr(), _pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
                commit: {"commit": {"tree": {"sha": "d" * 40}}},
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            document, digest, recorded = _unavailable_inventory_document(directory)
            # `success` with this document is a state the workflow never produces:
            # the command exits 1 when a readback it wrote is UNAVAILABLE. It pins
            # the binding's defensive pass-through of a recorded refusal (Amazon Q
            # and CodeAnt on #461). The success path over a complete document is
            # InventoryBundleTests.test_the_bundle_binds_the_document_to_the_tree_github_reads.
            for result in ("success", "skipped"):
                with self.subTest(result=result):
                    bundle = runner.collect_bundle(
                        github,
                        repository="ktogias/gnostoa",
                        pull_number=312,
                        requested_head=HEAD,
                        deepsource=None,
                        codacy=None,
                        sonarcloud=None,
                        observed_at=OBSERVED,
                        inventory=runner.InventoryInput(
                            document, digest, result, "1", "1"
                        ),
                    )
                    tail = bundle["readbacks"][-2:]
                    self.assertEqual(
                        [("gnostoa-inventory", "DIFF"), ("gnostoa-inventory", "FULL")],
                        [(r["provider"], r["scope"]) for r in tail],
                    )
                    if result == "success":
                        self.assertEqual(recorded, tail)
                    else:
                        self.assertEqual(
                            {"INVENTORY_JOB_SKIPPED"},
                            {r["coverage"]["reason"] for r in tail},
                        )
                    shown = json.loads(canonical_json(bundle))
                    self.assertEqual(shown, analyzer_readback.parse_bundle(shown))

    def test_a_failed_tree_read_never_drops_the_vendor_readbacks(self) -> None:
        """RED (Revix, CodeAnt and Kilo on #461): the head's tree is read only once
        the document is bound, so an inventory that did not succeed never reads it,
        and a read that fails refuses the project readbacks alone. The vendors'
        readbacks stay in the bundle."""
        urls = _github_urls()
        commit = f"https://api.github.com/repos/ktogias/gnostoa/commits/{HEAD}"
        with tempfile.TemporaryDirectory() as directory:
            document, digest, _ = _unavailable_inventory_document(directory)
            for result, reason in (
                ("failure", "INVENTORY_JOB_FAILURE"),
                ("success", "TREE_UNAVAILABLE"),
            ):
                with self.subTest(result=result):
                    github = _GitHubFake(
                        {
                            urls["pr"]: [_pr(), _pr()],
                            urls["statuses"]: [],
                            urls["checks"]: {"check_runs": []},
                            urls["comments"]: [],
                            commit: runner.RunnerError("GitHub API HTTP 502"),
                        }
                    )
                    bundle = runner.collect_bundle(
                        github,
                        repository="ktogias/gnostoa",
                        pull_number=312,
                        requested_head=HEAD,
                        deepsource=None,
                        codacy=None,
                        sonarcloud=None,
                        observed_at=OBSERVED,
                        inventory=runner.InventoryInput(
                            document, digest, result, "1", "1"
                        ),
                    )
                    self.assertEqual(
                        [
                            "deepsource",
                            "deepsource",
                            "codacy",
                            "sonarcloud",
                            "gnostoa-inventory",
                            "gnostoa-inventory",
                        ],
                        [r["provider"] for r in bundle["readbacks"]],
                    )
                    self.assertEqual(
                        {reason},
                        {r["coverage"]["reason"] for r in bundle["readbacks"][-2:]},
                    )
                    self.assertEqual(result == "success", commit in github.calls)

    def test_no_failure_of_the_binding_drops_the_vendor_readbacks(self) -> None:
        """RED (Claude on #461, after the tree's and the profile's reads): the shape,
        not one more instance. A failure at any of the binding's external seams, the
        document's stat and read, its strict load, the readback parser, the tree's
        read, the profile's load or an import, refuses both project readbacks alone,
        and the vendors' readbacks stay in the bundle."""
        import builtins

        from tools import quality_evidence

        real_import = builtins.__import__

        def no_review_check(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "tools.review_check":
                raise ModuleNotFoundError("No module named 'jsonschema'")
            return real_import(name, *args, **kwargs)

        def no_adapter(name: str, *args: Any, **kwargs: Any) -> Any:
            fromlist = args[2] if len(args) > 2 else kwargs.get("fromlist") or ()
            if name == "tools" and "analyzer_inventory" in fromlist:
                raise ImportError("cannot import name 'analyzer_inventory'")
            return real_import(name, *args, **kwargs)

        # Each seam with the reason only its own failure gives: the document records
        # UNAVAILABLE readbacks of its own (`QualityEvidenceError`), so a seam that
        # never fires would pass through looking refused (Cubic on #461).
        seams: tuple[tuple[str, Any, str | None], ...] = (
            (
                "the document's stat",
                patch.object(Path, "is_file", side_effect=PermissionError(13, "x")),
                "PermissionError",
            ),
            (
                "the document's read",
                patch.object(runner, "_read_bounded", side_effect=OSError(5, "x")),
                "OSError",
            ),
            (
                "the readback parser",
                patch.object(runner, "parse_readback", side_effect=ValueError("x")),
                "ValueError",
            ),
            (
                "the profile's load",
                patch.object(
                    quality_evidence,
                    "load_diagnostic_profile",
                    side_effect=quality_evidence.QualityEvidenceError("x"),
                ),
                "PROFILE_UNAVAILABLE",
            ),
            (
                "an import",
                patch.object(builtins, "__import__", no_review_check),
                "ModuleNotFoundError",
            ),
            # The adapter builds the refusal itself, so without it there is no
            # project readback to give: the items are MISSING, which denies as
            # UNAVAILABLE does (Revix on #461).
            (
                "the adapter's import",
                patch.object(builtins, "__import__", no_adapter),
                None,
            ),
        )
        urls = _github_urls()
        commit = f"https://api.github.com/repos/ktogias/gnostoa/commits/{HEAD}"
        with tempfile.TemporaryDirectory() as directory:
            document, digest, _ = _unavailable_inventory_document(directory)
            for name, seam, reason in seams:
                github = _GitHubFake(
                    {
                        urls["pr"]: [_pr(), _pr()],
                        urls["statuses"]: [],
                        urls["checks"]: {"check_runs": []},
                        urls["comments"]: [],
                        commit: {"commit": {"tree": {"sha": "d" * 40}}},
                    }
                )
                with self.subTest(seam=name), seam:
                    bundle = runner.collect_bundle(
                        github,
                        repository="ktogias/gnostoa",
                        pull_number=312,
                        requested_head=HEAD,
                        deepsource=None,
                        codacy=None,
                        sonarcloud=None,
                        observed_at=OBSERVED,
                        inventory=runner.InventoryInput(
                            document, digest, "success", "1", "1"
                        ),
                    )
                    vendors = ["deepsource", "deepsource", "codacy", "sonarcloud"]
                    self.assertEqual(
                        vendors, [r["provider"] for r in bundle["readbacks"][:4]]
                    )
                    self.assertEqual(
                        []
                        if reason is None
                        else [
                            ("DIFF", "READBACK_UNAVAILABLE", reason),
                            ("FULL", "READBACK_UNAVAILABLE", reason),
                        ],
                        [
                            (r["scope"], r["completeness"], r["coverage"]["reason"])
                            for r in bundle["readbacks"][4:]
                        ],
                    )

    def test_a_profile_that_cannot_be_loaded_never_drops_the_vendor_readbacks(
        self,
    ) -> None:
        """RED (Revix on #461): the protected profile's load is the binding's last
        external read. One that fails refuses the project readbacks alone, as
        `PROFILE_UNAVAILABLE`; the vendors' readbacks stay in the bundle."""
        from tools import quality_evidence

        urls = _github_urls()
        commit = f"https://api.github.com/repos/ktogias/gnostoa/commits/{HEAD}"
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
                commit: {"commit": {"tree": {"sha": "d" * 40}}},
            }
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(
                quality_evidence,
                "load_diagnostic_profile",
                side_effect=quality_evidence.QualityEvidenceError(
                    "cannot load the diagnostic profile: KnowledgeFormatError"
                ),
            ),
        ):
            document, digest, _ = _unavailable_inventory_document(directory)
            bundle = runner.collect_bundle(
                github,
                repository="ktogias/gnostoa",
                pull_number=312,
                requested_head=HEAD,
                deepsource=None,
                codacy=None,
                sonarcloud=None,
                observed_at=OBSERVED,
                inventory=runner.InventoryInput(document, digest, "success", "1", "1"),
            )
        self.assertEqual(
            ["deepsource", "deepsource", "codacy", "sonarcloud"],
            [r["provider"] for r in bundle["readbacks"][:-2]],
        )
        self.assertEqual(
            {"PROFILE_UNAVAILABLE"},
            {r["coverage"]["reason"] for r in bundle["readbacks"][-2:]},
        )

    def test_the_document_is_never_read_from_the_working_directory(self) -> None:
        """RED (Cubic on #461): without `--inventory-document`, the runner read a
        file of the document's name from whatever directory it ran in. A document
        the workflow does not name is missing, whatever lies there."""
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
                f"https://api.github.com/repos/ktogias/gnostoa/commits/{HEAD}": {
                    "commit": {"tree": {"sha": "d" * 40}}
                },
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            _, digest, _ = _unavailable_inventory_document(directory)
            output = Path(directory) / "readback.json"
            with (
                contextlib.chdir(directory),
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    runner.GitHubReadClient, "from_environment", return_value=github
                ),
                patch.object(
                    http.client.HTTPSConnection,
                    "connect",
                    side_effect=AssertionError("network forbidden"),
                ),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(
                    0,
                    runner.main(
                        [
                            "--repository",
                            "ktogias/gnostoa",
                            "--pull-number",
                            "312",
                            "--head",
                            HEAD,
                            "--output",
                            str(output),
                            "--inventory-sha256",
                            digest,
                            "--inventory-result",
                            "success",
                        ]
                    ),
                )
            readbacks = json.loads(output.read_text(encoding="utf-8"))["readbacks"]
        self.assertEqual(
            {"INVENTORY_DOCUMENT_MISSING"},
            {r["coverage"]["reason"] for r in readbacks[-2:]},
        )

    def test_the_readback_installs_main_s_runtime_dependencies(self) -> None:
        """RED (Codex P1 on #461): the bundle's inventory binding imports
        `tools.review_check` (jsonschema) and loads the protected profile (PyYAML),
        which a clean runner's Python lacks. The job installs main's hash-locked
        runtime lock exactly as `merge-admission.yml`'s jobs do, right after Python
        is set up, before any step that reads a secret; the install holds none."""
        steps = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))["jobs"][
            "readback"
        ]["steps"]
        names = [step.get("name", step.get("uses", "")) for step in steps]
        admission = yaml.safe_load(
            (WORKFLOW_PATH.parent / "merge-admission.yml").read_text(encoding="utf-8")
        )
        # One command, the same in every merge-admission job that installs.
        [command] = {
            step["run"]
            for job in admission["jobs"].values()
            for step in job.get("steps", [])
            if step.get("name") == "Install exact runtime dependencies"
        }
        install = names.index("Install exact runtime dependencies")
        self.assertEqual(command, steps[install]["run"])
        self.assertEqual({"name", "run"}, set(steps[install]))
        self.assertTrue(names[install - 1].startswith("actions/setup-python@"))
        self.assertLess(install, names.index("Read exact-head analyzer evidence"))

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
            sonarcloud=None,
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
            sonarcloud=None,
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
            # skipcq: PYL-W0212 -- white-box test of the runner's internals
            runner._assert_secret_free(
                canonical_json({"value": "prefix-super-secret-suffix"}),
                ["super-secret"],
            )

    def test_output_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "readback.json"
            # skipcq: PYL-W0212 -- white-box test of the runner's internals
            runner._write_create_only(output, "{}")
            with self.assertRaisesRegex(runner.RunnerError, "already exists"):
                # skipcq: PYL-W0212 -- white-box test of the runner's internals
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
            "tools/analyzer_sonarcloud.py",
            "ci/analyzer_readback.py",
            ".github/workflows/analyzer-readback.yml",
            "tests/test_analyzer_readback.py",
            "tests/test_analyzer_readback_runner.py",
            "tests/test_analyzer_sonarcloud.py",
        ):
            self.assertIn(path, section)

    def test_workflow_runs_after_verification_on_request_and_by_hand(self) -> None:
        """The readback runs for every Pull Request head once Gnostoa verification
        completes, on a repository_dispatch request, by hand (#387), and when the
        merge-admission run calls it at the admission point (#407, slice 1b.4). The
        secret step reads only a subject the secret-free step has validated."""
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        loaded = yaml.safe_load(workflow)
        triggers = loaded.get("on", loaded.get(True))
        self.assertEqual(
            {
                "workflow_dispatch",
                "workflow_run",
                "repository_dispatch",
                "workflow_call",
            },
            set(triggers),
        )
        self.assertEqual(
            ["Gnostoa verification"], triggers["workflow_run"]["workflows"]
        )
        self.assertEqual(["completed"], triggers["workflow_run"]["types"])
        self.assertEqual(
            ["gnostoa-analyzer-readback"], triggers["repository_dispatch"]["types"]
        )
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("pull_request_target", workflow)
        # The workflow grants nothing itself, and each job only the reads it needs
        # (SonarCloud githubactions:S8264 on #460, as merge-admission.yml on #426).
        self.assertEqual({}, loaded["permissions"])
        self.assertEqual(
            {
                "contents": "read",
                "pull-requests": "read",
                "statuses": "read",
                "checks": "read",
            },
            loaded["jobs"]["readback"]["permissions"],
        )
        # Readbacks queue, one at a time, and none is cancelled: a flood of requests
        # waits rather than spending the analyzers' rate limits (Amazon Q on #388),
        # as review-current-state.yml's runs do (Decision 0086).
        self.assertEqual(
            {
                "group": "gnostoa-analyzer-readback",
                "cancel-in-progress": False,
                "queue": "max",
            },
            loaded["jobs"]["readback"]["concurrency"],
        )
        # The readback job's slot, never the whole run's (CodeAnt on #460).
        self.assertNotIn("concurrency", loaded)
        job = loaded["jobs"]["readback"]
        # The whole condition is pinned, so no arm can be added, dropped or regrouped
        # unseen (Kody on #388):
        # - `workflow_run` matches a workflow by name, so a same-named workflow on
        #   any branch could start it: only a pull_request run of verification.yml
        #   counts;
        # - each admitted event is named, so a trigger added later is not admitted
        #   by default (Amazon Q on #388);
        # - a run that a later push superseded is cancelled, and its head is no
        #   longer the Pull Request's, so it reads nothing (Kody on #388). A run that
        #   failed or timed out leaves its head the Pull Request's, so it is still
        #   read (CodeAnt on #388). Each admitted conclusion is named;
        # - a call is the merge-admission run's (#407, slice 1b.4), admitted from
        #   protected main only, like every other entry;
        # - it runs after the inventory whatever its result, unless the run is
        #   cancelled, `!cancelled()`, so a failed inventory denies rather than
        #   vanishes (#389 A0-MP1 slice 3), and a cancelled run holds no secret-holding
        #   job or readback slot (Revix on #461); the same admitted-event condition
        #   still gates it.
        self.assertEqual(
            "!cancelled()"
            " && github.ref == 'refs/heads/main'"
            " && (inputs.admission == true"
            " || github.event_name == 'workflow_dispatch'"
            " || github.event_name == 'repository_dispatch'"
            " || (github.event_name == 'workflow_run'"
            " && (github.event.workflow_run.conclusion == 'success'"
            " || github.event.workflow_run.conclusion == 'failure'"
            " || github.event.workflow_run.conclusion == 'timed_out')"
            " && github.event.workflow_run.event == 'pull_request'"
            " && github.event.workflow_run.path"
            " == '.github/workflows/verification.yml'))",
            " ".join(job["if"].split()),
        )
        self.assertEqual("analyzer-readback", job["environment"])
        self.assertEqual(15, job["timeout-minutes"])
        steps = job["steps"]
        names = [step.get("name", step.get("uses", "")) for step in steps]
        bind = names.index("Bind trusted main execution source")
        subject = names.index("Resolve the readback subject")
        read = names.index("Read exact-head analyzer evidence")
        upload = names.index("Upload non-secret analyzer readback")
        self.assertLess(bind, subject)
        self.assertLess(subject, read)
        self.assertLess(read, upload)
        # The checkout takes its event's own revision, main's `github.sha`, which the
        # binding step verifies; naming a ref is what a fork's code would need
        # (SonarCloud S7631 on #388, Decision 0096 rule 11).
        checkout = steps[0]
        self.assertNotIn("ref", checkout["with"])
        self.assertIs(False, checkout["with"]["persist-credentials"])
        resolve = steps[subject]
        self.assertEqual("subject", resolve["id"])
        self.assertNotIn("secrets.", yaml.safe_dump(resolve))
        self.assertIn("python ci/analyzer_readback_subject.py", resolve["run"])
        self.assertIn('>> "${GITHUB_OUTPUT}"', resolve["run"])
        acquire = steps[read]
        expected = (
            ("GITHUB_TOKEN", "github.token"),
            ("DEEPSOURCE_API_TOKEN", "secrets.DEEPSOURCE_API_TOKEN"),
            ("CODACY_API_TOKEN", "secrets.CODACY_API_TOKEN"),
            ("SONAR_TOKEN", "secrets.SONAR_TOKEN"),
            ("PULL_NUMBER", "steps.subject.outputs.pull_number"),
            ("REQUESTED_HEAD", "steps.subject.outputs.head"),
            # The inventory job's own outputs (#389 A0-MP1 slice 3), and this run's
            # attempt (Cubic on #461).
            ("INVENTORY_RESULT", "needs.inventory.result"),
            ("INVENTORY_SHA256", "needs.inventory.outputs.document-sha256"),
            ("INVENTORY_ATTEMPT", "needs.inventory.outputs.attempt"),
            ("RUN_ATTEMPT", "github.run_attempt"),
        )
        self.assertEqual({name for name, _ in expected}, set(acquire["env"]))
        for name, expression in expected:
            self.assertEqual(f"${{{{ {expression} }}}}", acquire["env"][name], name)
        self.assertIn('--pull-number "${PULL_NUMBER}"', acquire["run"])
        self.assertIn('--head "${REQUESTED_HEAD}"', acquire["run"])
        self.assertIn("gnostoa-analyzer-readback.json", acquire["run"])
        # The resolver fails when it binds no subject, so no later step runs without
        # one (#389). A receipt that binds no exact head fails its step, and is
        # uploaded still, so its reason stays readable (Kody on #388); a failure that
        # wrote none uploads nothing, so its own error is the run's only one (Claude
        # on #388).
        self.assertNotIn("if", acquire)
        self.assertEqual("readback", acquire["id"])
        self.assertEqual(
            "${{ !cancelled() && steps.readback.outputs.receipt == 'written' }}",
            steps[upload]["if"],
        )
        self.assertEqual(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            steps[upload]["uses"],
        )
        self.assertEqual(
            "${{ steps.subject.outputs.artifact }}",
            steps[upload]["with"]["name"],
        )
        # An event's own fields reach no step but the secret-free resolver.
        for index, step in enumerate(steps):
            if index != subject:
                text = yaml.safe_dump(step)
                for field in ("inputs.", "client_payload", "workflow_run."):
                    self.assertNotIn(field, text, (names[index], field))
        bind_step = steps[bind]
        self.assertIn('test "${EXECUTOR_REF}" = "refs/heads/main"', bind_step["run"])
        self.assertIn(
            'test "$(git rev-parse HEAD)" = "${EXECUTOR_SHA}"', bind_step["run"]
        )


class _SonarCloudReader:
    """SonarCloud for the runner's tests: the head analysed, no issue. Every read
    is logged in ``events``, beside the GitHub reads, so their order shows."""

    def __init__(self, events: list[str]) -> None:
        self.events = events

    def get(self, url: str) -> Mapping[str, Any]:
        self.events.append(url)
        if url.startswith("https://sonarcloud.io/api/project_pull_requests/list?"):
            return {
                "pullRequests": [
                    {
                        "key": "312",
                        "url": "https://github.com/ktogias/gnostoa/pull/312",
                        "commit": {"sha": HEAD},
                        "analysisDate": "2026-10-11T23:57:56+0000",
                        "pullRequestId": "882e653f-7208-4ec7-a92e-4a139efba1c8",
                    }
                ]
            }
        if url == "https://sonarcloud.io/api/ce/component?component=ktogias_gnostoa":
            return {"queue": []}
        if url.startswith("https://sonarcloud.io/api/issues/search?"):
            return {
                "total": 0,
                "p": 1,
                "ps": 500,
                "paging": {"pageIndex": 1, "pageSize": 500, "total": 0},
                "issues": [],
            }
        raise AssertionError(f"unexpected SonarCloud URL: {url}")


class _OrderedGitHub(_GitHubFake):
    def __init__(self, responses: dict[str, Any], events: list[str]) -> None:
        super().__init__(responses)
        self.events = events

    def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
        self.events.append(url)
        return super().get(url)


def _main(output: Path) -> int:
    return runner.main(
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


class SonarCloudRunnerTests(unittest.TestCase):
    """MA0 1b.3c (#407 6119460225, lineage 6119607885): SonarCloud's readback
    joins the bundle, inside its GitHub head bracket, with its own credential."""

    def test_the_bundle_reads_sonarcloud_inside_the_head_bracket(self) -> None:
        events: list[str] = []
        urls = _github_urls()
        sonar_check = {
            "id": 114609123587,
            "name": "SonarCloud Code Analysis",
            "head_sha": HEAD,
            "status": "completed",
            "conclusion": "success",
            "started_at": "2026-10-11T23:57:56Z",
            "details_url": "https://sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest=312",
            "app": {"id": 12526},
        }
        github = _OrderedGitHub(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
                urls["sonar_checks"]: {"total_count": 1, "check_runs": [sonar_check]},
            },
            events,
        )
        bundle = runner.collect_bundle(
            github,
            repository="ktogias/gnostoa",
            pull_number=312,
            requested_head=HEAD,
            deepsource=None,
            codacy=None,
            sonarcloud=_SonarCloudReader(events),
            observed_at=OBSERVED,
        )
        self.assertEqual("BOUND", bundle["subject_binding"])
        self.assertEqual(4, len(bundle["readbacks"]))
        readback = bundle["readbacks"][-1]
        self.assertEqual("sonarcloud-web-api/v1", readback["adapter"])
        # Read in full and bound: the latest published report's, COMPLETE (R1).
        self.assertEqual("COMPLETE", readback["coverage"]["status"])
        self.assertEqual(114609123587, readback["native"]["check_run"]["id"])
        self.assertIn(urls["sonar_checks"], events)
        # Both halves of the report binding, SonarCloud's reads and the head's
        # SonarCloud runs on GitHub, inside the head bracket (cubic on #424).
        sonar = [
            n
            for n, url in enumerate(events)
            if urlsplit(url).hostname == "sonarcloud.io" or url == urls["sonar_checks"]
        ]
        heads = [n for n, url in enumerate(events) if url == urls["pr"]]
        self.assertEqual(2, len(heads))
        self.assertLess(heads[0], sonar[0])
        self.assertLess(sonar[-1], heads[-1])

    def test_without_a_reader_the_inventory_is_unauthenticated(self) -> None:
        """C1: no reader, no read, and the readback says why."""
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
            sonarcloud=None,
            observed_at=OBSERVED,
        )
        readbacks = {item["adapter"]: item for item in bundle["readbacks"]}
        readback = readbacks["sonarcloud-web-api/v1"]
        self.assertEqual("sonarcloud", readback["provider"])
        self.assertEqual("DIFF", readback["scope"])
        self.assertEqual("AUTH_UNAVAILABLE", readback["completeness"])
        self.assertEqual(
            {
                "status": "UNAVAILABLE",
                "pages": 0,
                "count": 0,
                "reason": "AUTH_UNAVAILABLE",
            },
            readback["coverage"],
        )
        self.assertNotIn("observed_head", readback)

    def test_main_without_a_token_sends_sonarcloud_nothing(self) -> None:
        """C1: SonarCloud's API is public, and still nothing is read from it
        without the readback's own credential."""
        urls = _github_urls()
        github = _GitHubFake(
            {
                urls["pr"]: [_pr(), _pr()],
                urls["statuses"]: [],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
            }
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {}, clear=True),
            patch.object(
                runner.GitHubReadClient, "from_environment", return_value=github
            ),
            patch.object(
                http.client.HTTPSConnection,
                "connect",
                side_effect=AssertionError("network forbidden"),
            ) as connect,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            output = Path(directory) / "readback.json"
            self.assertEqual(0, _main(output))
            document = json.loads(output.read_text())
        readbacks = {item["provider"]: item for item in document["readbacks"]}
        self.assertEqual("AUTH_UNAVAILABLE", readbacks["sonarcloud"]["completeness"])
        connect.assert_not_called()

    def test_a_malformed_token_keeps_the_other_readbacks(self) -> None:
        """C1, C10: Decision 0091's rule for an optional credential, for
        SonarCloud's too."""
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
                        "creator": {"login": "deepsource-io[bot]", "type": "Bot"},
                    }
                ],
                urls["checks"]: {"check_runs": []},
                urls["comments"]: [],
            }
        )
        stderr, stdout = io.StringIO(), io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ, {SONAR_ENV: "synthetic-sonar-credential\n"}, clear=True
            ),
            patch.object(
                runner.GitHubReadClient, "from_environment", return_value=github
            ),
            patch.object(
                runner.analyzer_deepsource.DeepSourceGraphQLClient,
                "from_environment",
                return_value=_deepsource_fake(),
            ),
            patch.object(
                runner.analyzer_codacy.CodacyRestClient,
                "from_environment",
                return_value=_CodacyReader(),
            ),
            patch.object(
                http.client.HTTPSConnection,
                "connect",
                side_effect=AssertionError("network forbidden"),
            ) as connect,
            contextlib.redirect_stderr(stderr),
            contextlib.redirect_stdout(stdout),
        ):
            output = Path(directory) / "readback.json"
            self.assertEqual(0, _main(output))
            serialized = output.read_text()
        self.assertNotIn(
            "synthetic-sonar-credential",
            serialized + stderr.getvalue() + stdout.getvalue(),
        )
        readbacks = {
            item["provider"]: item
            for item in json.loads(serialized)["readbacks"]
            if item["adapter"] != "deepsource-github/v1"
        }
        self.assertEqual("AUTH_UNAVAILABLE", readbacks["sonarcloud"]["completeness"])
        self.assertEqual("FULL_RUN", readbacks["deepsource"]["completeness"])
        self.assertEqual("FULL_RUN", readbacks["codacy"]["completeness"])
        connect.assert_not_called()

    def test_main_reads_with_the_token_s_own_client(self) -> None:
        """C1: with `SONAR_TOKEN` the bundle gets SonarCloud's client, and without
        it none; nothing is sent here."""
        for name, environment, expected in (
            ("a token", {SONAR_ENV: "synthetic-sonar-credential"}, True),
            ("no token", {}, False),
        ):
            with (
                self.subTest(name),
                tempfile.TemporaryDirectory() as directory,
                patch.dict(os.environ, environment, clear=True),
                patch.object(
                    runner.GitHubReadClient,
                    "from_environment",
                    return_value=_GitHubFake({}),
                ),
                patch.object(
                    runner, "collect_bundle", return_value={"subject_binding": "BOUND"}
                ) as collect,
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(0, _main(Path(directory) / "readback.json"))
                client = collect.call_args.kwargs["sonarcloud"]
                self.assertIs(
                    expected,
                    isinstance(client, runner.analyzer_sonarcloud.SonarCloudRestClient),
                )
                if not expected:
                    self.assertIsNone(client)

    def test_the_token_never_reaches_the_receipt(self) -> None:
        """C10: the serialized bundle is refused when it holds SonarCloud's
        credential bytes, as for every other credential."""
        leaked = {"subject_binding": "BOUND", "note": "synthetic-sonar-credential"}
        stderr = io.StringIO()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ, {SONAR_ENV: "synthetic-sonar-credential"}, clear=True
            ),
            patch.object(
                runner.GitHubReadClient,
                "from_environment",
                return_value=_GitHubFake({}),
            ),
            patch.object(runner, "collect_bundle", return_value=leaked),
            contextlib.redirect_stderr(stderr),
        ):
            output = Path(directory) / "readback.json"
            self.assertEqual(2, _main(output))
            self.assertFalse(output.exists())
        self.assertIn("credential bytes", stderr.getvalue())
        self.assertNotIn("synthetic-sonar-credential", stderr.getvalue())


def _sonar_run(
    *,
    run_id: int = 114609123587,
    started: str = "2026-10-11T23:57:56Z",
    status: str = "completed",
    conclusion: str | None = "success",
    pull: str = "312",
) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": "SonarCloud Code Analysis",
        "head_sha": HEAD,
        "status": status,
        "conclusion": conclusion,
        "started_at": started,
        "details_url": f"https://sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest={pull}",
        "app": {"id": 12526},
    }


def _runs(*runs: dict[str, Any], total: int | None = None) -> dict[str, Any]:
    return {
        "total_count": len(runs) if total is None else total,
        "check_runs": list(runs),
    }


class _SequencedGitHub(_GitHubFake):
    """Answers each sequenced URL's responses in order, so a later read can
    differ from an earlier one."""

    def __init__(
        self, responses: dict[str, Any], sequenced: dict[str, list[Any]]
    ) -> None:
        super().__init__(responses)
        self.sequenced = {url: list(values) for url, values in sequenced.items()}

    def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
        if url not in self.sequenced:
            return super().get(url)
        self.calls.append(url)
        if not self.sequenced[url]:
            raise AssertionError(f"no remaining fake responses for {url}")
        value = self.sequenced[url].pop(0)
        if isinstance(value, BaseException):
            raise value
        return value, {}


def _bracketed(
    *collections: dict[str, Any] | BaseException,
) -> tuple[dict[str, Any], _SequencedGitHub]:
    """SonarCloud's readback when the exact head's SonarCloud runs read as
    ``collections``, in order; an exception among them is raised by that read."""

    urls = _github_urls()
    github = _SequencedGitHub(
        {
            urls["pr"]: [_pr(), _pr()],
            urls["statuses"]: [],
            urls["checks"]: {"check_runs": []},
            urls["comments"]: [],
        },
        {urls["sonar_checks"]: list(collections)},
    )
    bundle = runner.collect_bundle(
        github,
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        deepsource=None,
        codacy=None,
        sonarcloud=_SonarCloudReader([]),
        observed_at=OBSERVED,
    )
    readback: dict[str, Any] = bundle["readbacks"][-1]
    return readback, github


class SonarCloudReportBracketTests(unittest.TestCase):
    """C4b (PAO 6119999041 on #407): the exact head's SonarCloud runs are read,
    completely, before the issue pages and again after them, and the published
    report must be the same both times."""

    def test_r1_a_stable_published_report_is_complete(self) -> None:
        """R1 (owner 6122025441 on #424): the stable bracket, read completely,
        gives the latest observed published report's inventory, COMPLETE."""
        readback, github = _bracketed(_runs(_sonar_run()), _runs(_sonar_run()))
        self.assertEqual("FULL_RUN", readback["completeness"])
        self.assertEqual("COMPLETE", readback["coverage"]["status"])
        self.assertEqual("UNOBSERVABLE", readback["native"]["unfinished_analysis"])
        self.assertEqual(2, github.calls.count(_github_urls()["sonar_checks"]))

    def test_a_run_that_starts_between_the_reads_holds_the_inventory(self) -> None:
        """The old published analysis is unchanged, the head too, and a newer run
        for the pull request is unfinished: not this head's complete report."""
        newer = _sonar_run(
            run_id=2,
            status="in_progress",
            conclusion=None,
            started="2026-10-12T00:10:00Z",
        )
        readback, _ = _bracketed(_runs(_sonar_run()), _runs(_sonar_run(), newer))
        self.assertEqual("AMBIGUOUS", readback["completeness"])
        self.assertEqual("INCOMPLETE", readback["coverage"]["status"])
        self.assertEqual("ANALYSIS_IN_PROGRESS", readback["coverage"]["reason"])
        self.assertEqual([], readback["findings"])

    def test_a_changed_publication_is_not_the_report_that_was_read(self) -> None:
        for name, after in (
            ("a new start", _runs(_sonar_run(started="2026-10-12T00:10:00Z"))),
            (
                "a newer finished run",
                _runs(
                    _sonar_run(), _sonar_run(run_id=2, started="2026-10-12T00:10:00Z")
                ),
            ),
            ("another conclusion", _runs(_sonar_run(conclusion="failure"))),
        ):
            with self.subTest(name):
                readback, _ = _bracketed(_runs(_sonar_run()), after)
                self.assertEqual("AMBIGUOUS", readback["completeness"])
                self.assertEqual("INCOMPLETE", readback["coverage"]["status"])
                self.assertEqual([], readback["findings"])

    def test_another_pull_request_s_run_on_the_commit_changes_nothing(self) -> None:
        """#394 and #395 share `5ef97e5`: another one's later run is not this one's."""
        other = _sonar_run(run_id=2, pull="311", started="2026-10-12T00:10:00Z")
        readback, _ = _bracketed(_runs(_sonar_run(), other), _runs(_sonar_run(), other))
        self.assertEqual("COMPLETE", readback["coverage"]["status"])

    def test_a_github_failure_keeps_its_kind(self) -> None:
        """Claude on #424: a failed read of the head's SonarCloud runs keeps its
        kind, as the runner's own client reports it, rather than every failure
        becoming a provider error."""
        from tools import github_rest

        for name, cause, status, reason in (
            (
                "rate limited",
                github_rest.GitHubReadError("GitHub API HTTP 429", status=429),
                "RATE_LIMITED",
                "RATE_LIMITED",
            ),
            (
                "unavailable",
                github_rest.GitHubReadError("GitHub API HTTP 502", status=502),
                "UNAVAILABLE",
                "READBACK_UNAVAILABLE",
            ),
            (
                "unusable",
                github_rest.MalformedAnswer("GitHub API returned invalid JSON"),
                "ERROR",
                "PROVIDER_ERROR",
            ),
            # A refused GitHub credential is an authentication failure (cubic on
            # #424); a rate-limited 403 is already reported as 429.
            (
                "unauthorized",
                github_rest.GitHubReadError("GitHub API HTTP 401", status=401),
                "UNAVAILABLE",
                "AUTH_UNAVAILABLE",
            ),
            (
                "forbidden",
                github_rest.GitHubReadError("GitHub API HTTP 403", status=403),
                "UNAVAILABLE",
                "AUTH_UNAVAILABLE",
            ),
        ):
            with self.subTest(name):
                failure = runner.RunnerError(str(cause))
                failure.__cause__ = cause
                readback, _ = _bracketed(_runs(_sonar_run()), failure)
                self.assertEqual(
                    "AUTH_UNAVAILABLE"
                    if reason == "AUTH_UNAVAILABLE"
                    else "READBACK_UNAVAILABLE",
                    readback["completeness"],
                )
                self.assertEqual(status, readback["coverage"]["status"])
                self.assertEqual(reason, readback["coverage"]["reason"])

    def test_a_client_failure_has_the_adapter_s_kind(self) -> None:
        """Octopus on #424: the runner's read of the head's SonarCloud runs and the
        adapter's own reads fail through the same shared client, so each failure
        has the one kind the adapter gives it."""
        from tools import analyzer_sonarcloud, github_rest

        readback_of = {
            "AUTH": ("UNAVAILABLE", "AUTH_UNAVAILABLE"),
            "RATE_LIMIT": ("RATE_LIMITED", "RATE_LIMITED"),
            "UNAVAILABLE": ("UNAVAILABLE", "READBACK_UNAVAILABLE"),
            "ERROR": ("ERROR", "PROVIDER_ERROR"),
        }
        for name, cause, kind in (
            (
                "a refused redirect",
                github_rest.UnsafeRedirect("GitHub redirect refused"),
                "ERROR",
            ),
            (
                "a request that failed validation",
                github_rest.GitHubError("GitHub request failed validation"),
                "ERROR",
            ),
            (
                "outside the origin",
                github_rest.OutsideOrigin("GitHub URL outside origin"),
                "ERROR",
            ),
            (
                "too large",
                github_rest.ResponseTooLarge("GitHub response too large"),
                "ERROR",
            ),
            ("not sent", github_rest.NotSent("GitHub request not sent"), "UNAVAILABLE"),
            (
                "past the deadline",
                github_rest.DeadlineReached("GitHub deadline reached"),
                "UNAVAILABLE",
            ),
            (
                "a server error",
                github_rest.GitHubReadError("GitHub API HTTP 503", status=503),
                "UNAVAILABLE",
            ),
        ):
            with self.subTest(name):
                # The intended kind, then the runner's agreement with the adapter.
                self.assertEqual(kind, analyzer_sonarcloud.failure_kind(cause))
                failure = runner.RunnerError(str(cause))
                failure.__cause__ = cause
                readback, _ = _bracketed(_runs(_sonar_run()), failure)
                actual = (
                    readback["coverage"]["status"],
                    readback["coverage"]["reason"],
                )
                self.assertEqual(readback_of[kind], actual)

    def test_a_run_total_that_is_no_count_is_never_complete(self) -> None:
        """F6 (CodeAnt on #424): GitHub's `total_count` must be a count. A list
        must not escape the readback, and a boolean is not 1."""
        for name, total in (("a list", [1]), ("a boolean", True), ("text", "1")):
            with self.subTest(name):
                runs = {"total_count": total, "check_runs": [_sonar_run()]}
                readback, _ = _bracketed(runs, runs)
                self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
                self.assertNotEqual("COMPLETE", readback["coverage"]["status"])
                # The failure's own reason: under R4 a stable, read bracket is
                # PARTIAL too, so "not COMPLETE" alone would not tell them apart.
                self.assertEqual("PROVIDER_ERROR", readback["coverage"]["reason"])

    def test_an_unparsable_details_url_is_still_a_readback(self) -> None:
        """F8 (CodeAnt on #424): a run whose details `urlsplit` cannot parse leaves
        the association unknown; the bundle keeps every readback."""
        bad = {
            **_sonar_run(run_id=2),
            "details_url": "https://[sonarcloud.io/dashboard",
        }
        readback, _ = _bracketed(_runs(_sonar_run(), bad), _runs(_sonar_run(), bad))
        self.assertEqual("AMBIGUOUS", readback["completeness"])
        self.assertEqual("REPORT_ASSOCIATION_AMBIGUOUS", readback["coverage"]["reason"])

    def test_an_incomplete_run_collection_is_never_complete(self) -> None:
        for name, before, after in (
            ("before the pages", _runs(_sonar_run(), total=2), _runs(_sonar_run())),
            ("after the pages", _runs(_sonar_run()), _runs(_sonar_run(), total=2)),
        ):
            with self.subTest(name):
                readback, _ = _bracketed(before, after)
                self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
                self.assertNotEqual("COMPLETE", readback["coverage"]["status"])
                # The failure's own reason: under R4 a stable, read bracket is
                # PARTIAL too, so "not COMPLETE" alone would not tell them apart.
                self.assertEqual("PROVIDER_ERROR", readback["coverage"]["reason"])


def _resolve(environ: dict[str, str]) -> dict[str, str]:
    """The resolver's subject, typed: the module is loaded from its path."""
    return cast(dict[str, str], subject_resolver.resolve(environ))


class SubjectResolutionTests(unittest.TestCase):
    """The secret-free step turns the triggering event into one exact subject, or
    none (#387). Every field is an identifier, validated before it is written."""

    def test_each_trigger_yields_its_subject(self) -> None:
        for environ in (
            {
                "EVENT_NAME": "workflow_dispatch",
                "DISPATCH_PULL": "384",
                "DISPATCH_HEAD": HEAD,
            },
            {
                "EVENT_NAME": "repository_dispatch",
                "REQUEST_PULL": "384",
                "REQUEST_HEAD": HEAD,
            },
            {
                "EVENT_NAME": "workflow_run",
                "RUN_PULLS": json.dumps([{"number": 384, "head": {"sha": OTHER}}]),
                "RUN_HEAD": HEAD,
            },
        ):
            with self.subTest(event=environ["EVENT_NAME"]):
                self.assertEqual(
                    {"pull_number": "384", "head": HEAD}, _resolve(environ)
                )

    def test_a_run_without_exactly_one_pull_request_fails_visibly(self) -> None:
        """A fork's run carries no Pull Request; a head shared by two leaves the
        subject ambiguous. Either fails, visibly: a run that finished green without a
        receipt would make missing evidence look like a clean producer (#389). A
        dispatch can still name one."""
        for pulls in ("[]", "null", json.dumps([{"number": 1}, {"number": 2}])):
            with self.subTest(pulls=pulls):
                environ = {
                    "EVENT_NAME": "workflow_run",
                    "RUN_PULLS": pulls,
                    "RUN_HEAD": HEAD,
                }
                with self.assertRaises(ValueError):
                    _resolve(environ)

    def test_a_field_that_is_no_identifier_is_refused(self) -> None:
        bad_heads = ("A" * 40, "a" * 39, HEAD + "\npull_number=1", "", HEAD + " ")
        bad_pulls = (
            "0",
            "-3",
            "1.5",
            "384\nhead=x",
            "",
            " 384",
            "384 ",
            "0x10",
            "1" * 11,
            # An Arabic-Indic digit after an ASCII one, which `int` reads as 12: only
            # ASCII digits count.
            "1٢",
        )
        for head in bad_heads:
            with self.subTest(head=head), self.assertRaises(ValueError):
                _resolve(
                    {
                        "EVENT_NAME": "repository_dispatch",
                        "REQUEST_PULL": "384",
                        "REQUEST_HEAD": head,
                    }
                )
        for pull in bad_pulls:
            with self.subTest(pull=pull), self.assertRaises(ValueError):
                _resolve(
                    {
                        "EVENT_NAME": "workflow_dispatch",
                        "DISPATCH_PULL": pull,
                        "DISPATCH_HEAD": HEAD,
                    }
                )
        for environ in (
            {"EVENT_NAME": "workflow_run", "RUN_PULLS": "{}", "RUN_HEAD": HEAD},
            {
                "EVENT_NAME": "workflow_run",
                "RUN_PULLS": json.dumps([{"number": 7}]),
                "RUN_HEAD": "x",
            },
            {"EVENT_NAME": "push"},
            {},
        ):
            with self.subTest(environ=environ), self.assertRaises(ValueError):
                _resolve(environ)

    def test_the_step_writes_only_validated_outputs(self) -> None:
        for environ, expected, status in (
            (
                {
                    "EVENT_NAME": "repository_dispatch",
                    "REQUEST_PULL": "384",
                    "REQUEST_HEAD": HEAD,
                },
                f"pull_number=384\nhead={HEAD}\n"
                f"artifact=gnostoa-analyzer-readback-384-{HEAD}\n",
                0,
            ),
            (
                {
                    "EVENT_NAME": "workflow_call",
                    "DISPATCH_PULL": "384",
                    "DISPATCH_HEAD": HEAD,
                    "RUN_ATTEMPT": "3",
                },
                f"pull_number=384\nhead={HEAD}\n"
                f"artifact=gnostoa-analyzer-readback-384-{HEAD}-3\n",
                0,
            ),
            (
                {
                    "EVENT_NAME": "workflow_call",
                    "DISPATCH_PULL": "384",
                    "DISPATCH_HEAD": HEAD,
                    "RUN_ATTEMPT": "3\nhead=x",
                },
                "",
                2,
            ),
            (
                {"EVENT_NAME": "workflow_run", "RUN_PULLS": "[]", "RUN_HEAD": HEAD},
                "",
                2,
            ),
            ({"EVENT_NAME": "repository_dispatch", "REQUEST_PULL": "x"}, "", 2),
        ):
            with self.subTest(environ=environ):
                out, err = io.StringIO(), io.StringIO()
                with (
                    patch.dict(os.environ, environ, clear=True),
                    contextlib.redirect_stdout(out),
                    contextlib.redirect_stderr(err),
                ):
                    self.assertEqual(status, subject_resolver.main())
                self.assertEqual(expected, out.getvalue())


class WorkflowRunPullsTests(unittest.TestCase):
    """One parser of `workflow_run.pull_requests`, shared by the L1 reconciler and
    the readback (#387)."""

    def test_numbers_are_kept_once_in_order(self) -> None:
        payload = json.dumps([{"number": 301}, {"number": 302}, {"number": 301}])
        self.assertEqual([301, 302], github_events.workflow_run_pull_numbers(payload))
        for empty in ("", "null", "[]"):
            with self.subTest(empty=empty):
                self.assertEqual([], github_events.workflow_run_pull_numbers(empty))

    def test_an_exact_sha_is_the_only_head(self) -> None:
        """One exact-SHA check for an event's head, which the resolver and the
        runner share (Claude on #388)."""
        self.assertEqual(HEAD, github_events.exact_sha(HEAD, "head"))
        # A number whose digits spell a SHA is still no SHA: JSON may carry one.
        for value in ("A" * 40, "a" * 39, HEAD + "\n", "", None, 40, int("1" * 40)):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "head must be an exact"),
            ):
                github_events.exact_sha(value, "head")

    def test_a_malformed_list_is_refused(self) -> None:
        for raw in (
            "{",
            "{}",
            "[1]",
            json.dumps([{"number": 0}]),
            json.dumps([{"number": True}]),
        ):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                github_events.workflow_run_pull_numbers(raw)


if __name__ == "__main__":
    unittest.main()
