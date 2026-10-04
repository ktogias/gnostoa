"""One hardened GitHub REST client for every GitHub adapter here (Decision 0100).

Merged from five that each guarded a different part of the same exchange: the
useful-L1 adapter's (Decision 0086), analyzer readback's (Decision 0091), and the agent
review pipeline's admission reader, context collector and comment poster (Decisions
0094, 0096 and 0098). Each element is kept from whichever had it strongest:

- **Origin pinning** (L1, analyzer readback): every request, and every redirect
  target, stays on the admitted origin -- scheme, host and port -- with no userinfo
  and no fragment.
- **Redirects** (collector, L1): refused by default, because a redirect can change
  the subject a read is about and no redirect can prove it kept it. A consumer whose
  reads are not subject-bound opts into same-origin following, and the credential is
  then an unredirected header, re-added only to an admitted target.
- **A bound on the whole exchange** (collector, admission): a socket timeout bounds
  one receive, not the exchange, so a provider sending a byte before each expiry --
  in the headers or the body -- kept a read alive past every stated deadline. The
  exchange runs on a daemon thread the caller stops waiting for, and at most
  ``MAX_ABANDONED`` may be left running; past that a request fails at once.
- **Bounded sizes** (all): the body is read in single receives against a byte cap, and
  an error body's prefix is bounded in bytes and in time.
- **Rate limits** (L1, collector): a 403 with the remaining count at zero, a
  ``Retry-After`` header or a "rate limit" message is a limit, not a refusal; the wait
  honours ``Retry-After`` (seconds or an HTTP-date) or ``X-RateLimit-Reset``, bounded,
  and an unhinted limit waits GitHub's documented minute rather than spending every
  attempt inside the window.
- **Retries** (collector, poster): idempotent reads only. A write is made once; whether
  it landed is for the caller to read back.
- **The credential** (analyzer readback): one printable token, refused otherwise, and
  never carried into an error message, even by header validation.
- **Decoding** (collector): any failure to decode is the provider's answer being
  unusable, and a ``null`` body is refused rather than read as "not found".
- **Errors** (L1): read and write failures are distinct types carrying the status, and
  a rate-limited 403 is reported as 429.
"""

from __future__ import annotations

import contextlib
import email.utils
import http.client
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from typing import Any, NamedTuple

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
JSON_MEDIA_TYPE = "application/vnd.github+json"
DIFF_MEDIA_TYPE = "application/vnd.github.v3.diff"
# Longer than any delay or epoch a caller could honour. Bounding the digits keeps
# `int()` inside Python's integer-string limit, which a provider header could exceed.
HINT_DIGITS = 12
# At most this many abandoned workers may still be running for one consumer. Each
# keeps its socket until its receive ends or the process does. (CodeAnt)
MAX_ABANDONED = 16
# The registry a policy uses when it names none of its own.
_ABANDONED: list[threading.Thread] = []
# Guards every registry: a check and the count it checks are one step.
_REGISTRY_LOCK = threading.Lock()


class Policy(NamedTuple):
    """The bounds one consumer reads under. Every field is a ceiling, not a target."""

    timeout_seconds: float = 30.0
    attempts: int = 3
    retry_sleep_seconds: float = 5.0
    max_response_bytes: int = 8 * 1024 * 1024
    max_rate_limit_wait: float = 60.0
    # What GitHub documents waiting when a secondary-limit response carries no timing
    # header at all.
    unhinted_rate_limit_wait: float = 60.0
    error_detail_bytes: int = 4096
    error_detail_seconds: float = 5.0
    # The smallest timeout a request is given, and so the amount by which a deadline
    # can be crossed: a request beginning in the budget's last instant still gets this.
    min_request_seconds: float = 0.1
    read_chunk_bytes: int = 65536
    max_abandoned: int = MAX_ABANDONED
    # The consumer's own registry of abandoned workers, so one consumer's stalled
    # requests cannot exhaust another's cap. A client gets its own when it names none.
    workers: list[threading.Thread] | None = None


DEFAULT_POLICY = Policy()


class GitHubError(RuntimeError):
    """A GitHub exchange that could not be used, with its HTTP status when it had one."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: float | None = None,
        in_flight: bool = False,
        outcome_unknown: bool = False,
        accepted_permissions: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        # The permission sets the route said it accepts (`X-Accepted-GitHub-Permissions`),
        # so a refusal can be read as "this token lacks that grant" (Decision 0101).
        self.accepted_permissions = accepted_permissions
        # When the provider said when to try again, bounded by the policy.
        self.retry_after = retry_after
        # The exchange was abandoned at its bound, not stopped: it may still reach the
        # provider. A write in flight must not be retried, since it can still land.
        self.in_flight = in_flight
        # A write that reached the provider and was not refused may have been applied:
        # a server error, a broken transport, an answer that could not be read. Only a
        # refusal, or a request never sent, says it was not (CodeAnt on #353).
        self.outcome_unknown = outcome_unknown or in_flight


class GitHubReadError(GitHubError):
    """A bounded read failed."""


class NotSent(GitHubReadError):
    """The request was refused before it was sent, so nothing reached the provider."""


class GitHubWriteError(GitHubError):
    """A write failed. Whether it nevertheless landed is the caller's to read back."""


class DeadlineReached(GitHubReadError):
    """The caller's wall-clock budget ran out before this request."""


class UnsafeRedirect(GitHubReadError):
    """A redirect that was refused. Retrying cannot make it allowed."""


class OutsideOrigin(GitHubReadError):
    """A URL, or a redirect target, outside the admitted origin."""


class ResponseTooLarge(GitHubReadError):
    """A body past the policy's byte cap, refused rather than accumulated."""


class MalformedAnswer(GitHubReadError):
    """A body that could not be decoded, or a `null` one."""


class TooManyPages(GitHubReadError):
    """A paged listing with more pages than its bound: read in part, it is not read."""


class InvalidRepository(ValueError):
    """A repository or owner name that is not safe to place in an API path."""


# ---------------------------------------------------------------------------------
# Origin and credential


def origin_of(root: str) -> tuple[str, str, int]:
    """Return the (scheme, host, port) a root URL admits."""
    try:
        parsed = urllib.parse.urlparse(root)
        port = parsed.port
    except ValueError as exc:
        # An unclosed IPv6 host or an invalid port, refused under the client's own
        # error rather than escaping as a raw ValueError (CodeAnt on #353).
        raise GitHubError("the API root is not a valid URL") from exc
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise GitHubError("the API root is not an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        # Refused here rather than at the first request, which every request built from
        # such a root would be (CodeAnt on #353).
        raise GitHubError("the API root carries credentials")
    if parsed.fragment or parsed.query:
        raise GitHubError("the API root carries a query or a fragment")
    default = 443 if parsed.scheme == "https" else 80
    return parsed.scheme, parsed.hostname, port or default


def validate_url(url: str, root: str = API_ROOT) -> str:
    """Return ``url`` if it stays on ``root``'s origin, or raise ``GitHubReadError``."""
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError as exc:
        # A malformed host -- an unclosed or invalid IPv6 literal -- raises before any
        # check here, and the URL can be a provider's `Link` header (CodeAnt on #353).
        raise GitHubReadError("GitHub API URL is malformed") from exc
    try:
        port = parsed.port
    except ValueError as exc:
        raise GitHubReadError("GitHub API URL has an invalid port") from exc
    scheme, host, admitted_port = origin_of(root)
    default = 443 if parsed.scheme == "https" else 80
    if (
        parsed.scheme != scheme
        or parsed.hostname != host
        or (port or default) != admitted_port
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise OutsideOrigin("GitHub API URL is outside the admitted origin")
    return url


# GitHub's owner and repository characters. An owner begins and ends with an
# alphanumeric; a name may not be `.` or `..`, which a path would read as itself or its
# parent. The rule is `analyzer_readback`'s, taken as the owner's here (#365).
_OWNER_SEGMENT = re.compile(r"\A[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\Z")
_REPOSITORY_SEGMENT = re.compile(r"\A[A-Za-z0-9_.-]+\Z")


def owner_name(value: str) -> str:
    """Return ``value`` if it is an owner name safe in an API path, else raise."""
    if _OWNER_SEGMENT.match(value) is None:
        raise InvalidRepository("repository owner contains an unsafe path segment")
    return value


def repository_name(value: str) -> str:
    """Return ``value`` if it is an `owner/name` safe in an API path, else raise.

    Interpolated into `repos/{owner}/{name}/...`, a query, a fragment, a third segment
    or a `..` would send the request somewhere its caller did not name.
    """
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise InvalidRepository("repository must use owner/name form")
    owner, name = parts
    owner_name(owner)
    if name in {".", ".."} or _REPOSITORY_SEGMENT.match(name) is None:
        raise InvalidRepository("repository name contains an unsafe path segment")
    return value


def path_segment(value: str) -> str:
    """Return ``value`` encoded as exactly one path segment, or raise ``ValueError``.

    For a name the provider supplies, such as an environment's: a slash, query or
    fragment cannot address another endpoint, and `.` or `..`, which quoting leaves
    alone, are refused because a path would read them as itself or its parent.
    """
    if value in {"", ".", ".."}:
        raise ValueError(f"{value!r} cannot be a path segment")
    return urllib.parse.quote(value, safe="")


def environment_token() -> str:
    """Return the token a job carries: `GH_TOKEN`, else `GITHUB_TOKEN`, else ""."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _checked_token(token: str) -> str:
    """Return ``token`` if it is one printable credential, without ever echoing it."""
    if not token:
        raise GitHubError("GitHub token is unavailable")
    if any(not "!" <= char <= "~" for char in token):
        raise GitHubError("GitHub credential is malformed")
    return token


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: none can be verified to keep the read's subject.

    The stdlib handler drops only ``content-length`` and ``content-type`` when it builds
    the next request, so an ``Authorization`` header travels to wherever a redirect
    points. Even a same-origin redirect can name another owner, repository, revision or
    file; the bytes would then be attributed to the subject that was asked about.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Refuse the redirect."""
        raise UnsafeRedirect(f"refusing a redirect from {req.full_url!r} to {newurl!r}")


class SameOriginRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only on the admitted origin, re-adding the credential to it."""

    def __init__(self, root: str = API_ROOT) -> None:
        super().__init__()
        self.root = root

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
        admitted = validate_url(newurl, self.root)
        authorization = req.get_header("Authorization")
        redirected = super().redirect_request(req, fp, code, msg, headers, admitted)
        if redirected is not None and authorization is not None:
            redirected.add_unredirected_header("Authorization", authorization)
        return redirected


def refusing_redirects() -> urllib.request.HTTPRedirectHandler:
    """Return the handler that refuses every redirect."""
    return RefuseRedirects()


# ---------------------------------------------------------------------------------
# The bounded exchange


def abandon_after(
    seconds: float,
    label: str,
    work: Callable[[], Any],
    policy: Policy = DEFAULT_POLICY,
) -> Any:
    """Run ``work`` on a daemon thread and stop waiting for it after ``seconds``.

    The read loop cannot bound the part of a request that happens inside ``open()``:
    CPython reads the status line and headers as many lines, and every byte may arrive
    in its own receive, each bounded by the socket timeout and by nothing else. So the
    caller has to stop waiting. The abandoned thread keeps its socket until its receive
    ends or the process does; past ``MAX_ABANDONED`` running at once, a request fails at
    once, so a stalling provider cannot accumulate workers without bound. The registry
    and its cap are the policy's: one per consumer.

    A worker is counted from its start, not from its abandonment, and the check, the
    count and the start are one step under a lock. Counted only once abandoned,
    concurrent requests could all pass the check before any was counted (CodeAnt on
    #353). A request that finishes in time is uncounted again.
    """
    workers = _ABANDONED if policy.workers is None else policy.workers
    finished = threading.Event()
    outcome: dict[str, Any] = {}

    def run() -> None:
        """Record what ``work`` returned or raised, then signal that it finished."""
        try:
            outcome["value"] = work()
        except Exception as error:
            outcome["error"] = error
        finally:
            finished.set()

    worker = threading.Thread(target=run, daemon=True)
    with _REGISTRY_LOCK:
        workers[:] = [running for running in workers if running.is_alive()]
        if len(workers) >= policy.max_abandoned:
            raise NotSent(
                f"not requesting {label!r}: {len(workers)} earlier requests are still "
                "running"
            )
        # Started inside the lock: a registered worker not yet started is not alive,
        # and another caller's pruning would uncount it.
        workers.append(worker)
        worker.start()
    if not finished.wait(seconds):
        raise GitHubReadError(f"timed out while requesting {label!r}", in_flight=True)
    with _REGISTRY_LOCK, contextlib.suppress(ValueError):
        workers.remove(worker)
    error = outcome.get("error")
    if error is not None:
        # Re-raised as itself: HTTPError carries the status the retry logic reads.
        raise error
    if "value" not in outcome:
        raise GitHubReadError(f"request for {label!r} ended without a result")
    return outcome["value"]


def _read_body(response: Any, url: str, stop_at: float, policy: Policy) -> bytes:
    """Return ``response``'s body, bounded in bytes and against ``stop_at``.

    In single receives whenever the response's type offers them: `read(n)` may perform
    several receives while trying to fill n, so a dripping provider stays inside one call
    past every deadline, while `read1` returns after one.
    """
    if getattr(type(response), "read1", None) is None:
        # A type with no single-receive read: one bounded read is all it offers.
        raw = response.read(policy.max_response_bytes + 1)
        if len(raw) > policy.max_response_bytes:
            raise ResponseTooLarge(
                f"provider body exceeded {policy.max_response_bytes} bytes for {url!r}"
            )
        return bytes(raw)
    chunks = bytearray()
    while True:
        # Checked before the receive as well as after it: `open()` consumed part of
        # the same budget, so a request whose stop has passed would otherwise be
        # granted one more full receive on top of it.
        if time.monotonic() >= stop_at:
            raise GitHubReadError(f"timed out while reading {url!r}")
        # `read1` returns after a single underlying receive, which is what makes the
        # check between chunks a bound rather than a hope.
        chunk = response.read1(policy.read_chunk_bytes)
        if not chunk:
            return bytes(chunks)
        chunks += chunk
        if len(chunks) > policy.max_response_bytes:
            raise ResponseTooLarge(
                f"provider body exceeded {policy.max_response_bytes} bytes for {url!r}"
            )
        if time.monotonic() >= stop_at:
            raise GitHubReadError(f"timed out while reading {url!r}")


def exchange_once(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    limit: float,
    policy: Policy = DEFAULT_POLICY,
) -> tuple[bytes, dict[str, str]]:
    """Make one request, bounded between receives, on the calling thread.

    Half the budget goes to the stop and half to the single receive that may straddle
    it, which makes ``limit`` a bound the read cannot exceed. It cannot bound what
    happens inside ``open()`` -- ``exchange`` does that. An HTTP error is raised as
    itself, for the caller to classify.
    """
    url = request.full_url
    per_receive = limit / 2
    stop_at = time.monotonic() + (limit - per_receive)
    with opener.open(request, timeout=per_receive) as response:  # nosec B310 -- the origin is pinned before any request is built
        raw = _read_body(response, url, stop_at, policy)
        headers = getattr(response, "headers", None) or {}
        return raw, {key.lower(): value for key, value in headers.items()}


def exchange(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    limit: float,
    policy: Policy = DEFAULT_POLICY,
) -> tuple[bytes, dict[str, str]]:
    """Make one request, bounded as a whole by ``limit`` seconds."""
    result: tuple[bytes, dict[str, str]] = abandon_after(
        limit,
        request.full_url,
        lambda: exchange_once(opener, request, limit, policy),
        policy,
    )
    return result


def decode_json(raw: bytes, url: str) -> Any:
    """Return the JSON in ``raw``, or raise: any failure means an unusable answer.

    Enumerating what a decode can raise failed four times (a non-UTF-8 body, the
    integer-string limit, a `RecursionError` from deep nesting); every failure means the
    same thing, so the guard names that directly. A `null` body is refused: it would
    otherwise read as "not found".
    """
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as error:
        raise MalformedAnswer(f"malformed provider body for {url!r}") from error
    if payload is None:
        raise MalformedAnswer(f"provider body was null for {url!r}")
    return payload


# ---------------------------------------------------------------------------------
# Rate limits and retries


def header_number(value: str) -> int | None:
    """Return ``value`` as a non-negative integer, or None if it is not one.

    Only bounded ASCII digits count: `str.isdigit()` accepts digits `int()` rejects,
    and a value past the integer-string limit raises too. (CodeRabbit)
    """
    if value.isascii() and value.isdigit() and len(value) <= HINT_DIGITS:
        return int(value)
    return None


def retry_after_seconds(value: str, now: float | None) -> float | None:
    """Return the wait a ``Retry-After`` value names (RFC 9110), or None."""
    seconds = header_number(value)
    if seconds is not None:
        return float(seconds)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        return None
    return when.timestamp() - (time.time() if now is None else now)


def error_detail(
    error: urllib.error.HTTPError,
    deadline: float | None = None,
    policy: Policy = DEFAULT_POLICY,
) -> str:
    """Return a bounded prefix of ``error``'s body, read at most once.

    Reading it is destructive and the classification runs twice for one error, so the
    prefix is cached on the error and the two calls cannot disagree. The read is
    bounded in time as well as bytes, and an unreadable body yields an empty prefix.
    """
    cached = getattr(error, "gnostoa_error_detail", None)
    if cached is not None:
        return str(cached)
    allowed = policy.error_detail_seconds
    if deadline is not None:
        allowed = min(allowed, deadline - time.monotonic())
    detail = ""
    if allowed > 0:
        try:
            detail = abandon_after(
                allowed,
                "error body",
                lambda: error.read(policy.error_detail_bytes),
                policy,
            ).decode("utf-8", errors="replace")
        except (OSError, http.client.HTTPException, ValueError, GitHubError):
            # Base classes: deciding what an error was may never be what fails.
            detail = ""
    try:
        error.gnostoa_error_detail = detail  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover -- HTTPError accepts attributes
        pass
    return detail


def is_rate_limited(
    error: urllib.error.HTTPError,
    detail_deadline: float | None = None,
    policy: Policy = DEFAULT_POLICY,
) -> bool:
    """Return whether an HTTP error is GitHub reporting a rate limit, not a refusal.

    A primary limit is 403 with the remaining count at zero; a secondary one is 403 or
    429 with `retry-after`, or -- as GitHub documents -- with neither header and only
    its message, so a bounded prefix of the body is read as well.
    """
    if error.code == 429:
        return True
    if error.code != 403:
        return False
    headers: Any = error.headers or {}
    remaining = str(headers.get("x-ratelimit-remaining", "")).strip()
    if remaining == "0" or bool(str(headers.get("retry-after", "")).strip()):
        return True
    return "rate limit" in error_detail(error, detail_deadline, policy).lower()


def rate_limit_pause(
    error: urllib.error.HTTPError,
    attempt: int,
    now: float | None = None,
    detail_deadline: float | None = None,
    policy: Policy = DEFAULT_POLICY,
) -> float:
    """Return how long to wait before retrying ``error``.

    The provider says when the next request is permitted; that is honoured, bounded by
    what the caller can afford. A plain 5xx gets the ordinary backoff: GitHub sends
    `X-RateLimit-*` on ordinary responses too, and consulting them for a transient blip
    made it wait the cap.
    """
    if not is_rate_limited(error, detail_deadline, policy):
        return float(policy.retry_sleep_seconds * (attempt + 1))
    headers: Any = error.headers or {}
    hinted = retry_after_seconds(str(headers.get("retry-after", "")).strip(), now)
    if hinted is None:
        reset = header_number(str(headers.get("x-ratelimit-reset", "")).strip())
        if reset is not None:
            hinted = float(reset - (time.time() if now is None else now))
    if hinted is None:
        # A recognised limit with nothing to say when it lifts: the documented wait,
        # not the transient backoff that spends every attempt inside the window.
        return float(min(policy.unhinted_rate_limit_wait, policy.max_rate_limit_wait))
    return float(max(0.0, min(hinted, policy.max_rate_limit_wait)))


def release(error: urllib.error.HTTPError) -> None:
    """Close the response an HTTP error carries, and the connection under it.

    Called once the error is classified -- its bounded detail is read and cached first --
    so a retried or reported error does not hold a socket until the garbage collector
    finds it, one connection per error.
    """
    with contextlib.suppress(Exception):
        error.close()


def request_timeout(deadline: float | None, policy: Policy = DEFAULT_POLICY) -> float:
    """Return one request's timeout, never longer than the budget that remains."""
    if deadline is None:
        return float(policy.timeout_seconds)
    return max(
        policy.min_request_seconds,
        min(float(policy.timeout_seconds), deadline - time.monotonic()),
    )


def bounded_pause(seconds: float, deadline: float | None) -> float:
    """Never sleep past the caller's deadline."""
    if deadline is None:
        return seconds
    return max(0.0, min(seconds, deadline - time.monotonic()))


def retry_pause(
    error: Exception,
    url: str,
    attempt: int,
    attempt_deadline: float,
    deadline: float | None,
    policy: Policy = DEFAULT_POLICY,
) -> float:
    """Return how long to wait before retrying after ``error``, or raise it as final."""
    final = attempt == policy.attempts - 1
    if isinstance(error, urllib.error.HTTPError):
        if error.code < 500 and not is_rate_limited(error, attempt_deadline, policy):
            # A genuine refusal stops at once: retrying only delays the same answer.
            raise GitHubReadError(
                f"HTTP {error.code} for {url!r}", status=error.code
            ) from error
        if final:
            status = 429 if error.code == 403 else error.code
            raise GitHubReadError(
                f"HTTP {error.code} for {url!r}", status=status
            ) from error
        return bounded_pause(
            rate_limit_pause(
                error, attempt, detail_deadline=attempt_deadline, policy=policy
            ),
            deadline,
        )
    if final and isinstance(error, GitHubError):
        # It already named its own cause; a slow provider is not a corrupt one.
        raise error
    if final and isinstance(error, (json.JSONDecodeError, UnicodeDecodeError)):
        # A malformed body is named as one, whichever layer noticed it: reaching a
        # caller's own handler as a bare ValueError would file a provider problem as
        # something else.
        raise MalformedAnswer(f"malformed provider body for {url!r}") from error
    if final and isinstance(error, ValueError):
        # Request validation, which can quote the credential: never chained.
        raise GitHubReadError(f"request failed validation for {url!r}") from None
    if final:
        # `OSError` and `HTTPException` between them are every way a request can fail
        # below the protocol; naming members missed one four times in a row.
        raise GitHubReadError(f"{type(error).__name__} for {url!r}") from error
    return bounded_pause(policy.retry_sleep_seconds * (attempt + 1), deadline)


Fetch = Callable[[str, urllib.request.Request, float], Any]


def read_with_retries(
    url: str,
    request: urllib.request.Request,
    fetch: Fetch,
    *,
    deadline: float | None = None,
    missing_ok: bool = False,
    policy: Policy = DEFAULT_POLICY,
) -> Any:
    """Return what ``fetch`` yields for an idempotent read, retried within bounds.

    Server errors, rate limits, transport failures and unusable bodies are retried; a
    refusal is not, nor a refused redirect. With ``missing_ok`` a 404 returns None --
    the transport's "not found", which settles no other question. ``fetch`` is the one
    bounded attempt, so a composition can bind its own.
    """
    for attempt in range(policy.attempts):
        if deadline is not None and time.monotonic() >= deadline:
            raise DeadlineReached(f"deadline reached before {url!r}")
        # Fixed before the request, so it still means "this attempt" once the request
        # has consumed it: reading an error body is part of that exchange.
        timeout = request_timeout(deadline, policy)
        attempt_deadline = time.monotonic() + timeout
        pause = 0.0
        try:
            return fetch(url, request, timeout)
        except urllib.error.HTTPError as error:
            try:
                if error.code == 404 and missing_ok:
                    return None
                pause = retry_pause(
                    error, url, attempt, attempt_deadline, deadline, policy
                )
            finally:
                release(error)
        except (UnsafeRedirect, NotSent):
            # A refused redirect, or a request the cap refused before sending: past the
            # cap a request fails at once, and retrying would only wait out pauses while
            # the workers that filled it kept stalling (CodeAnt on #353).
            raise
        except (GitHubError, OSError, http.client.HTTPException, ValueError) as error:
            pause = retry_pause(error, url, attempt, attempt_deadline, deadline, policy)
        time.sleep(pause)
    raise AssertionError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------------
# The client


class GitHubRestClient:
    """A GitHub REST and GraphQL client under one consumer's ``Policy``.

    Reads that are subject-bound keep the default, which refuses every redirect; a
    consumer whose reads are not passes ``follow_same_origin_redirects``, and may name
    its own handler for that case.
    """

    same_origin_redirects: type[SameOriginRedirects] = SameOriginRedirects

    def __init__(
        self,
        token: str,
        *,
        api_root: str = API_ROOT,
        follow_same_origin_redirects: bool = False,
        user_agent: str = "gnostoa",
        policy: Policy = DEFAULT_POLICY,
    ) -> None:
        self._token = _checked_token(token)
        self.api_root = api_root.rstrip("/")
        origin_of(self.api_root)
        self.user_agent = user_agent
        # Each client its own registry of abandoned workers, unless the policy names one.
        self._workers: list[threading.Thread] = (
            policy.workers if policy.workers is not None else []
        )
        self._policy = policy._replace(workers=self._workers)
        handler: urllib.request.HTTPRedirectHandler = (
            self.same_origin_redirects(self.api_root)
            if follow_same_origin_redirects
            else RefuseRedirects()
        )
        self._opener = urllib.request.build_opener(handler)

    @property
    def policy(self) -> Policy:
        """The bounds this client reads under. A consumer may compute them per call."""
        return self._policy

    @classmethod
    def from_environment(cls, **options: Any) -> GitHubRestClient:
        """Return a client for the job's token, from `GH_TOKEN` or `GITHUB_TOKEN`."""
        return cls(environment_token(), **options)

    def url(self, path: str) -> str:
        """Return the API URL for ``path`` on this client's root."""
        return f"{self.api_root}/{path.lstrip('/')}"

    def build_request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        accept: str = JSON_MEDIA_TYPE,
    ) -> urllib.request.Request:
        """Return a request for ``url`` on the admitted origin, carrying the credential."""
        encoded = None
        if payload is not None:
            encoded = json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        try:
            request = urllib.request.Request(
                validate_url(url, self.api_root),
                data=encoded,
                method=method,
                headers={
                    "Accept": accept,
                    "X-GitHub-Api-Version": API_VERSION,
                    "User-Agent": self.user_agent,
                    **(
                        {"Content-Type": "application/json"}
                        if encoded is not None
                        else {}
                    ),
                },
            )
            request.add_unredirected_header("Authorization", f"Bearer {self._token}")
        except ValueError:
            # Header validation can quote the credential in its error.
            raise GitHubError("GitHub request failed validation") from None
        return request

    def fetch(
        self, _url: str, request: urllib.request.Request, timeout: float
    ) -> tuple[bytes, dict[str, str]]:
        """Make one bounded attempt, returning the raw body and headers.

        The URL is the request's own; the parameter keeps the shape every attempt
        shares, so a composition can bind its own attempt in this one's place.
        """
        return exchange(self._opener, request, timeout, self.policy)

    def read_json(
        self,
        url: str,
        *,
        deadline: float | None = None,
        missing_ok: bool = False,
        fetch: Fetch | None = None,
    ) -> Any:
        """Return the JSON at ``url``, retried as an idempotent read within the policy."""
        request = self.build_request("GET", url)
        attempt = fetch or (lambda u, r, t: decode_json(self.fetch(u, r, t)[0], u))
        return read_with_retries(
            url,
            request,
            attempt,
            deadline=deadline,
            missing_ok=missing_ok,
            policy=self.policy,
        )

    def read_page(
        self, url: str, *, deadline: float | None = None
    ) -> tuple[Any, dict[str, str]]:
        """Return a GET's document and headers, retried as an idempotent read.

        For a paged listing, whose `Link` header names the next page: ``read_json``
        keeps only the document, and ``get`` makes one attempt.
        """
        request = self.build_request("GET", url)

        def attempt(
            target: str, built: urllib.request.Request, limit: float
        ) -> tuple[Any, dict[str, str]]:
            raw, headers = self.fetch(target, built, limit)
            return decode_json(raw, target), headers

        page: tuple[Any, dict[str, str]] = read_with_retries(
            url, request, attempt, deadline=deadline, policy=self.policy
        )
        return page

    def read_bytes(
        self,
        url: str,
        *,
        accept: str,
        deadline: float | None = None,
    ) -> bytes:
        """Return the raw body at ``url`` in media type ``accept``, retried, bounded."""
        request = self.build_request("GET", url, accept=accept)
        result: bytes = read_with_retries(
            url,
            request,
            lambda u, r, t: self.fetch(u, r, t)[0],
            deadline=deadline,
            policy=self.policy,
        )
        return result

    def _classified(self, error: urllib.error.HTTPError, write: bool) -> GitHubError:
        """Return the error type and status a failed exchange is reported as."""
        detail = error_detail(error, None, self.policy)
        message = f"GitHub API HTTP {error.code}"
        if detail:
            message += f": {' '.join(detail.split())[:512]}"
        limited = is_rate_limited(error, None, self.policy)
        status = 429 if error.code == 403 and limited else error.code
        hint = rate_limit_pause(error, 0, policy=self.policy) if limited else None
        kind = GitHubWriteError if write else GitHubReadError
        # A server error is the provider failing after it received the request, so a
        # write may have been applied; a 4xx, a rate limit included, refused it.
        reached = write and error.code >= 500
        headers = error.headers
        accepted = (
            None if headers is None else headers.get("X-Accepted-GitHub-Permissions")
        )
        return kind(
            message,
            status=status,
            retry_after=hint,
            outcome_unknown=reached,
            accepted_permissions=None if accepted is None else str(accepted)[:256],
        )

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        read: bool = False,
    ) -> tuple[Any, dict[str, str]]:
        """Make one attempt and decode it, reporting failures by kind.

        A GET, or a POST marked ``read`` (GraphQL), fails as a read; any other method
        fails as a write.
        """
        write = not read and method != "GET"
        request = self.build_request(method, url, payload)
        failure: type[GitHubError] = GitHubWriteError if write else GitHubReadError
        try:
            raw, headers = self.fetch(url, request, self.policy.timeout_seconds)
        except urllib.error.HTTPError as error:
            try:
                classified = self._classified(error, write)
            finally:
                release(error)
            raise classified from error
        except UnsafeRedirect:
            raise
        except GitHubError as error:
            # A read keeps its cause's own type; a write becomes a write failure, for
            # the caller to read back.
            if write and not isinstance(error, GitHubWriteError):
                raise GitHubWriteError(
                    str(error),
                    status=error.status,
                    in_flight=error.in_flight,
                    outcome_unknown=not isinstance(error, NotSent),
                ) from error
            raise
        except ValueError:
            # Header validation can quote the credential in its error, so it is never
            # chained: not here, and not in any traceback a caller formats.
            raise failure("GitHub request failed validation") from None
        except (OSError, http.client.HTTPException) as error:
            raise failure(
                "GitHub API transport failed", outcome_unknown=write
            ) from error
        try:
            return decode_json(raw, url), headers
        except GitHubReadError as error:
            if write:
                # The provider answered, and its answer could not be read: the write may
                # well have been applied.
                raise GitHubWriteError(str(error), outcome_unknown=True) from error
            raise

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        """Return one GET's document and headers, in one attempt."""
        return self._request("GET", url)

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        """Return a GraphQL document, reporting a rate-limited answer as 429."""
        document, headers = self._request(
            "POST",
            self.url("graphql"),
            {"query": query, "variables": variables},
            read=True,
        )
        if not isinstance(document, dict):
            raise GitHubReadError("GitHub GraphQL returned invalid shape")
        errors = document.get("errors")
        if errors:
            rate_limited = (
                headers.get("x-ratelimit-remaining") == "0"
                or bool(headers.get("retry-after"))
                or graphql_errors_indicate_rate_limit(errors)
            )
            raise GitHubReadError(
                "GitHub GraphQL returned errors", status=429 if rate_limited else None
            )
        return document

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        """POST ``payload`` once and return the provider's document."""
        document, _ = self._request("POST", url, payload)
        return document

    def patch(self, url: str, payload: dict[str, Any]) -> Any:
        """PATCH ``payload`` once and return the provider's document."""
        document, _ = self._request("PATCH", url, payload)
        return document

    def put(self, url: str, payload: dict[str, Any]) -> Any:
        """PUT ``payload`` once and return the provider's document."""
        document, _ = self._request("PUT", url, payload)
        return document


_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


def next_url(headers: Any, root: str = API_ROOT) -> str | None:
    """Return the next page's URL from a `Link` header, pinned to ``root``'s origin."""
    link = headers.get("link") if headers else None
    if not link:
        return None
    match = _NEXT_LINK.search(str(link))
    if match is None:
        return None
    return validate_url(match.group(1), root)


def follow_pages(
    read: Callable[[str], tuple[Any, Mapping[str, str]]],
    url: str,
    *,
    max_pages: int,
    root: str = API_ROOT,
) -> Iterator[Any]:
    """Yield each page's document of a paged listing, following its `Link` header.

    ``read`` makes one page's request and returns its document and headers, so any
    transport can follow a listing through this one loop. Each next link must stay on
    ``root``'s origin. Past ``max_pages`` it raises ``TooManyPages``: a listing read in
    part is not read, and its caller must not judge what it did read.
    """
    if max_pages < 1:
        raise ValueError("max_pages must be at least 1")
    following = url
    for _ in range(max_pages):
        document, headers = read(following)
        yield document
        named = next_url(headers, root)
        if named is None:
            return
        following = named
    raise TooManyPages(f"the listing has more than {max_pages} pages")


def graphql_errors_indicate_rate_limit(errors: Any) -> bool:
    """Return whether GraphQL ``errors`` say the request was rate-limited."""
    if not isinstance(errors, list):
        return False
    for raw_error in errors:
        if not isinstance(raw_error, dict):
            continue
        message = raw_error.get("message")
        if isinstance(message, str) and "rate limit" in message.lower():
            return True
    return False
