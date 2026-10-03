"""The one shared GitHub REST client keeps every element it was merged from (Decision 0100).

One test per element named in the lineage amendment on #353: each fails if its element
is removed. The provider is a local HTTP server, so redirects, dripping bytes, oversized
bodies and request counts are real network behaviour rather than a stub's assumption.
"""

from __future__ import annotations

import contextlib
import email.utils
import gc
import http.server
import io
import json
import socket
import threading
import time
import traceback
import unittest
import urllib.error
import urllib.request
import warnings
from collections.abc import Callable
from typing import Any
from unittest import mock

from tools import github_rest

Route = Callable[[http.server.BaseHTTPRequestHandler], None]


class _Provider:
    """A local provider whose routes a test scripts, counting what it received."""

    def __init__(self, routes: dict[str, Route]) -> None:
        self.routes = routes
        self.seen: list[tuple[str, str, str]] = []
        self.log: list[str] = []
        provider = self

        class Handler(http.server.BaseHTTPRequestHandler):
            """Answer each request from the scripted routes."""

            def log_message(self, format: str, *args: Any) -> None:
                """Keep the test output quiet: retain the log, print nothing."""
                provider.log.append(format % args)

            def _answer(self) -> None:
                provider.seen.append(
                    (self.command, self.path, self.headers.get("Authorization", ""))
                )
                route = provider.routes.get(self.path.split("?")[0])
                if route is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                route(self)

            do_GET = _answer
            do_POST = _answer

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.root = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        """Stop serving."""
        self.server.shutdown()
        self.server.server_close()


def _json(status: int, document: Any, headers: dict[str, str] | None = None) -> Route:
    """Return a route answering ``document`` with ``status``."""

    def route(handler: http.server.BaseHTTPRequestHandler) -> None:
        """Send the scripted answer."""
        body = json.dumps(document).encode("utf-8")
        handler.send_response(status)
        for name, value in (headers or {}).items():
            handler.send_header(name, value)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    return route


def _http_error(
    code: int, headers: dict[str, str], body: bytes = b""
) -> urllib.error.HTTPError:
    """Return an HTTPError as urllib raises it."""
    message = email.message_from_string(
        "".join(f"{k}: {v}\n" for k, v in headers.items())
    )
    return urllib.error.HTTPError(
        "https://api.github.com/x", code, "x", message, io.BytesIO(body)
    )


class SharedGitHubClientTests(unittest.TestCase):
    """Each merged element, held by a test that fails without it."""

    def setUp(self) -> None:
        self.providers: list[_Provider] = []

    def tearDown(self) -> None:
        for provider in self.providers:
            provider.close()

    def _provider(self, routes: dict[str, Route]) -> _Provider:
        provider = _Provider(routes)
        self.providers.append(provider)
        return provider

    def test_requests_stay_on_the_admitted_origin(self) -> None:
        """Origin pinning (L1, analyzer readback): scheme, host, port, no userinfo or
        fragment -- checked before any request is built."""
        root = github_rest.API_ROOT
        self.assertEqual(
            f"{root}/repos/o/r", github_rest.validate_url(f"{root}/repos/o/r", root)
        )
        for outside in (
            "https://api.github.com.evil.example/x",
            "http://api.github.com/x",
            "https://user:pw@api.github.com/x",  # pragma: allowlist secret -- a fake userinfo the origin check must refuse
            "https://api.github.com/x#fragment",
            "https://api.github.com:8443/x",
        ):
            with (
                self.subTest(url=outside),
                self.assertRaises(github_rest.GitHubReadError),
            ):
                github_rest.validate_url(outside, root)
        client = github_rest.GitHubRestClient("t")
        with self.assertRaises(github_rest.GitHubReadError):
            client.build_request("GET", "https://evil.example/x")

    def test_redirects_are_refused_unless_same_origin_following_is_chosen(self) -> None:
        """Redirects (collector, L1): refused by default; followed on the origin only
        when chosen, the credential re-added there and never sent anywhere else."""
        other = self._provider({"/elsewhere": _json(200, {"leak": True})})

        def to(location: str) -> Route:
            def route(handler: http.server.BaseHTTPRequestHandler) -> None:
                handler.send_response(302)
                handler.send_header("Location", location)
                handler.end_headers()

            return route

        provider = self._provider(
            {
                "/a": to("/b"),
                "/b": _json(200, {"ok": 1}),
                "/off": to(f"{other.root.replace('127.0.0.1', 'localhost')}/elsewhere"),
            }
        )
        strict = github_rest.GitHubRestClient("tok", api_root=provider.root)
        with self.assertRaises(github_rest.UnsafeRedirect):
            strict.get(f"{provider.root}/a")
        following = github_rest.GitHubRestClient(
            "tok", api_root=provider.root, follow_same_origin_redirects=True
        )
        document, _ = following.get(f"{provider.root}/a")
        self.assertEqual({"ok": 1}, document)
        self.assertEqual(("GET", "/b", "Bearer tok"), provider.seen[-1])
        with self.assertRaises(github_rest.GitHubReadError):
            following.get(f"{provider.root}/off")
        self.assertEqual([], other.seen)

    def test_a_dripping_provider_cannot_outlive_the_exchange_bound(self) -> None:
        """The whole-exchange bound (collector, admission): a byte before each socket
        timeout, in the headers or the body, cannot keep a read alive past it."""

        def drip_body(handler: http.server.BaseHTTPRequestHandler) -> None:
            handler.send_response(200)
            handler.send_header("Content-Length", "100")
            handler.end_headers()
            with contextlib.suppress(OSError):  # the client hangs up, as it should
                for _ in range(100):
                    handler.wfile.write(b" ")
                    handler.wfile.flush()
                    time.sleep(0.2)

        def drip_headers(handler: http.server.BaseHTTPRequestHandler) -> None:
            with contextlib.suppress(OSError):  # the client hangs up, as it should
                handler.wfile.write(b"HTTP/1.1 200 OK\r\n")
                for _ in range(100):
                    handler.wfile.write(b"X")
                    handler.wfile.flush()
                    time.sleep(0.2)

        provider = self._provider({"/body": drip_body, "/headers": drip_headers})
        policy = github_rest.Policy(timeout_seconds=1.0, attempts=1)
        client = github_rest.GitHubRestClient(
            "t", api_root=provider.root, policy=policy
        )
        for path in ("/body", "/headers"):
            with self.subTest(path=path):
                started = time.monotonic()
                with self.assertRaises(github_rest.GitHubReadError):
                    client.read_json(f"{provider.root}{path}")
                self.assertLess(time.monotonic() - started, 4.0)

    def test_bodies_are_bounded(self) -> None:
        """Bounded sizes (all): a body past the cap is refused, not accumulated."""
        provider = self._provider({"/big": _json(200, ["x" * 2000])})
        policy = github_rest.Policy(max_response_bytes=1000, attempts=1)
        client = github_rest.GitHubRestClient(
            "t", api_root=provider.root, policy=policy
        )
        with self.assertRaisesRegex(github_rest.GitHubReadError, "exceeded"):
            client.read_json(f"{provider.root}/big")

    def test_rate_limits_are_recognised_and_waited_out(self) -> None:
        """Rate limits (L1, collector): a limit is not a refusal, and the wait honours
        the provider's hint within the cap."""
        policy = github_rest.Policy()
        for label, error, limited in (
            ("primary", _http_error(403, {"x-ratelimit-remaining": "0"}), True),
            ("secondary", _http_error(403, {"retry-after": "3"}), True),
            (
                "by message",
                _http_error(403, {}, b"You have exceeded a secondary rate limit"),
                True,
            ),
            ("refusal", _http_error(403, {}, b"Resource not accessible"), False),
            ("429", _http_error(429, {}), True),
            ("5xx", _http_error(502, {}), False),
        ):
            with self.subTest(case=label):
                self.assertIs(limited, github_rest.is_rate_limited(error, None, policy))
        now = 1_000_000.0
        date = email.utils.formatdate(now + 30, usegmt=True)
        for label, error, expected in (
            ("seconds", _http_error(429, {"retry-after": "7"}), 7.0),
            ("date", _http_error(429, {"retry-after": date}), 30.0),
            (
                "reset",
                _http_error(
                    403,
                    {
                        "x-ratelimit-remaining": "0",
                        "x-ratelimit-reset": str(int(now) + 20),
                    },
                ),
                20.0,
            ),
            ("unhinted", _http_error(403, {}, b"API rate limit exceeded"), 60.0),
            ("capped", _http_error(429, {"retry-after": "999"}), 60.0),
            ("transient", _http_error(502, {}), 10.0),
        ):
            with self.subTest(pause=label):
                pause = github_rest.rate_limit_pause(error, 1, now=now, policy=policy)
                self.assertAlmostEqual(expected, pause, delta=1.0)

    def test_only_idempotent_reads_are_retried(self) -> None:
        """Retries (collector, poster): a read is retried after a 5xx; a write is made
        exactly once, its outcome left for the caller to read back."""
        answers = iter([502, 200])

        def flaky(handler: http.server.BaseHTTPRequestHandler) -> None:
            _json(next(answers, 200), {"ok": 2})(handler)

        provider = self._provider({"/flaky": flaky, "/down": _json(502, {})})
        policy = github_rest.Policy(retry_sleep_seconds=0)
        client = github_rest.GitHubRestClient(
            "t", api_root=provider.root, policy=policy
        )
        self.assertEqual({"ok": 2}, client.read_json(f"{provider.root}/flaky"))
        self.assertEqual(2, sum(path == "/flaky" for _, path, _ in provider.seen))
        with self.assertRaises(github_rest.GitHubWriteError) as caught:
            client.post(f"{provider.root}/down", {"body": "x"})
        self.assertEqual(502, caught.exception.status)
        self.assertEqual(1, sum(path == "/down" for _, path, _ in provider.seen))

    def test_a_failed_exchange_releases_its_connection(self) -> None:
        """An HTTP error carries the open response, and its socket with it. Classified
        and retried, or reported, it is closed here rather than left for the garbage
        collector -- one open connection per error, and a warning in someone else's
        output when it is finally collected."""
        answers = iter([502, 200])

        def flaky(handler: http.server.BaseHTTPRequestHandler) -> None:
            _json(next(answers, 200), {"ok": 4})(handler)

        provider = self._provider({"/flaky": flaky, "/gone": _json(410, {})})
        policy = github_rest.Policy(retry_sleep_seconds=0, attempts=2)
        client = github_rest.GitHubRestClient(
            "t", api_root=provider.root, policy=policy
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            self.assertEqual({"ok": 4}, client.read_json(f"{provider.root}/flaky"))
            with self.assertRaises(github_rest.GitHubReadError):
                client.get(f"{provider.root}/gone")
            gc.collect()
        leaked = [
            str(item.message) for item in caught if item.category is ResourceWarning
        ]
        self.assertEqual([], leaked)

    def test_the_credential_is_one_printable_token_never_echoed(self) -> None:
        """The credential (analyzer readback): refused unless printable, and no error
        message carries it."""
        for token in ("", "two words", "line\nbreak", "tab\tbed"):
            with self.subTest(token=repr(token)):
                with self.assertRaises(github_rest.GitHubError) as caught:
                    github_rest.GitHubRestClient(token)
                if token:
                    self.assertNotIn(token, str(caught.exception))

    def test_a_validation_error_never_carries_the_credential(self) -> None:
        """The credential (analyzer readback): header validation can quote it, so a
        `ValueError` from the exchange is never chained into what a caller formats --
        whether it surfaces from one attempt or from the last retry."""
        secret = "sk-test-credential-value"  # pragma: allowlist secret -- a fake credential the test must not see leak
        opener = mock.MagicMock()
        opener.open.side_effect = ValueError(f"header {secret}")
        with mock.patch.object(urllib.request, "build_opener", return_value=opener):
            client = github_rest.GitHubRestClient(
                secret, policy=github_rest.Policy(retry_sleep_seconds=0)
            )
            for attempt in (
                lambda: client.get(f"{github_rest.API_ROOT}/x"),
                lambda: client.read_json(f"{github_rest.API_ROOT}/x"),
            ):
                with self.assertRaises(github_rest.GitHubReadError) as caught:
                    attempt()
                self.assertNotIn(
                    secret, "".join(traceback.format_exception(caught.exception))
                )

    def test_one_consumers_stalled_workers_cannot_starve_another(self) -> None:
        """The abandoned-worker cap (collector) is per consumer: a client whose provider
        stalls fills only its own registry, and another client still reads."""
        release = threading.Event()
        self.addCleanup(release.set)

        def stalled(handler: http.server.BaseHTTPRequestHandler) -> None:
            # A header byte inside each receive's timeout, so no single receive times
            # out while the exchange as a whole outlives its bound.
            with contextlib.suppress(OSError):
                handler.wfile.write(b"HTTP/1.1 200 OK\r\n")
                while not release.wait(0.05):
                    handler.wfile.write(b"X")
                    handler.wfile.flush()

        provider = self._provider({"/stall": stalled, "/ok": _json(200, {"ok": 3})})
        tight = github_rest.Policy(timeout_seconds=0.2, attempts=1, max_abandoned=1)
        stuck = github_rest.GitHubRestClient("t", api_root=provider.root, policy=tight)
        with self.assertRaisesRegex(github_rest.GitHubReadError, "timed out"):
            stuck.read_json(f"{provider.root}/stall")
        with self.assertRaisesRegex(github_rest.GitHubReadError, "still running"):
            stuck.read_json(f"{provider.root}/stall")
        other = github_rest.GitHubRestClient("t", api_root=provider.root, policy=tight)
        self.assertEqual({"ok": 3}, other.read_json(f"{provider.root}/ok"))

    def test_a_malformed_body_is_named_whichever_layer_noticed(self) -> None:
        """Decoding (collector): a decode error reaching the retry loop raw is still
        reported as a malformed body, never under its exception's type name."""
        request = github_rest.GitHubRestClient("t").build_request(
            "GET", f"{github_rest.API_ROOT}/x"
        )

        def raw_decode_failure(*_args: Any) -> Any:
            raise json.JSONDecodeError("Expecting value", "", 0)

        with self.assertRaisesRegex(
            github_rest.GitHubReadError, "malformed provider body"
        ):
            github_rest.read_with_retries(
                f"{github_rest.API_ROOT}/x",
                request,
                raw_decode_failure,
                policy=github_rest.Policy(retry_sleep_seconds=0),
            )

    def test_unusable_bodies_are_the_providers_answer(self) -> None:
        """Decoding (collector): any decode failure is an unusable answer, and `null`
        is refused rather than read as not-found."""
        for raw in (b"null", b"[" * 100000, b"\xff\xfe", b"{"):
            with (
                self.subTest(raw=raw[:8]),
                self.assertRaises(github_rest.GitHubReadError),
            ):
                github_rest.decode_json(raw, "u")

    def test_failures_are_reported_by_kind_with_their_status(self) -> None:
        """Errors (L1): reads and writes fail as distinct types; a rate-limited 403 is
        reported as 429."""

        def garbled(handler: http.server.BaseHTTPRequestHandler) -> None:
            handler.send_response(201)
            handler.send_header("Content-Length", "8")
            handler.end_headers()
            handler.wfile.write(b"not json")

        provider = self._provider(
            {
                "/limited": _json(403, {}, {"x-ratelimit-remaining": "0"}),
                "/gone": _json(410, {}),
                "/garbled": garbled,
            }
        )
        policy = github_rest.Policy(attempts=1)
        client = github_rest.GitHubRestClient(
            "t", api_root=provider.root, policy=policy
        )
        with self.assertRaises(github_rest.GitHubReadError) as read:
            client.get(f"{provider.root}/limited")
        self.assertEqual(429, read.exception.status)
        with self.assertRaises(github_rest.GitHubWriteError) as write:
            client.post(f"{provider.root}/limited", {})
        self.assertEqual(429, write.exception.status)
        with self.assertRaises(github_rest.GitHubReadError) as gone:
            client.get(f"{provider.root}/gone")
        self.assertEqual(410, gone.exception.status)
        # A write whose answer cannot be used may still have landed: it is a write
        # failure, for the caller to read back, never a read failure.
        with self.assertRaises(github_rest.GitHubWriteError) as garbled_write:
            client.post(f"{provider.root}/garbled", {})
        self.assertIsNone(garbled_write.exception.status)
        # And so is one that never reached the provider: a transport failure.
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
        closed.close()
        unreachable = github_rest.GitHubRestClient(
            "t", api_root=f"http://127.0.0.1:{port}", policy=policy
        )
        with self.assertRaises(github_rest.GitHubWriteError) as transport:
            unreachable.post(f"http://127.0.0.1:{port}/x", {})
        self.assertIsNone(transport.exception.status)

    def test_pagination_follows_only_links_on_the_origin(self) -> None:
        """Pagination (L1, poster): the next page is read from the Link header and must
        stay on the admitted origin."""
        root = github_rest.API_ROOT
        self.assertEqual(
            f"{root}/x?page=2",
            github_rest.next_url({"link": f'<{root}/x?page=2>; rel="next"'}, root),
        )
        self.assertIsNone(
            github_rest.next_url({"link": f'<{root}/x?page=1>; rel="prev"'}, root)
        )
        self.assertIsNone(github_rest.next_url({}, root))
        with self.assertRaises(github_rest.GitHubReadError):
            github_rest.next_url({"link": '<https://evil.example/x>; rel="next"'}, root)


if __name__ == "__main__":
    unittest.main()
