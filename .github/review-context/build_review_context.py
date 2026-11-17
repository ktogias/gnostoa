"""Collect the base revision for review: the GitHub composition of the base core.

Decisions 0094 and 0100. Every rule about what the reviewer is shown of the base
revision -- the merge base, the rename source, the blob check, the budget, the
deadline, the per-path manifest -- is the neutral core's (`tools/agent_review_base.py`).
The comparison's schema and the contents API are the GitHub adapter's
(`tools/agent_review_github.py`). What stays here is this collector's binding of the
shared client: its bounds, its pinned origin and its one bounded attempt, which the
adapter's base source reads through.

There is no subprocess here. The request is an ordinary HTTPS GET whose URL is matched
against a pattern pinning scheme, host and shape, so no argument can be mistaken for a
flag and no other origin is representable.

Invoked by the collection entrypoint, from the protected checkout, so this file is not
candidate-supplied.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
import threading
import urllib.error
import urllib.request
from typing import Any

from tools import agent_review_base as base
from tools import agent_review_claude_code as claude_code
from tools import agent_review_github as github
from tools import github_rest
from tools.agent_review_paths import within

API_ROOT = "https://api.github.com"
FILE_CAP = github.FILE_CAP
ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 5
DEADLINE_SECONDS = 600
MAX_RATE_LIMIT_WAIT = 60
# What GitHub documents waiting when a secondary-limit response carries no timing
# header at all. The ordinary transient backoff -- 5 seconds, then 10 -- kept all three
# attempts inside the same window, so files that were retrievable were recorded as
# `provider-error`; GitHub also warns that requests made during a secondary limit can
# extend it, which makes the short backoff worse than not retrying.
UNHINTED_RATE_LIMIT_WAIT = 60
READ_CHUNK_BYTES = 65536
# The contents API returns at most this many entries for a directory and does not
# paginate it. A changed file in a larger directory is simply missing from the listing,
# which must not be reported as "the base did not hold this".
LISTING_CAP = github.LISTING_CAP
# A body larger than this is refused rather than accumulated. Time was bounded and
# size was not, so a provider answering with an endless body filled the runner's
# memory while every deadline was still in the future, and the collection's own byte
# budget -- 512 KiB for all of `base/` -- is only checked after the decode. The two
# legitimate shapes are a listing of at most `LISTING_CAP` entries and a contents
# response carrying base64 of a file, whose payload cannot usefully exceed that whole
# budget: both fit inside a megabyte, so this leaves an order of magnitude spare while
# still bounding what one request can hold.
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
# The prefix of an error body consulted when classifying a 403, matching the bound
# `ci/review_github_current_state.py` already uses for the same job.
ERROR_DETAIL_BYTES = 4096
# And bounded in time, for the same reason the response body is. `error.read(n)` keeps
# receiving until it has n bytes -- which is why the response loop uses `read1` -- so a
# body arriving one byte before each socket timeout held the main thread for up to
# `ERROR_DETAIL_BYTES` receives, past the request bound and the collection deadline
# alike.
ERROR_DETAIL_SECONDS = 5.0
TIMEOUT_SECONDS = 30
# The smallest timeout a request is given, and therefore the amount by which the
# collection deadline can be crossed: a request beginning in the last instant of the
# budget still gets this. The deadline is a bound the collection crosses by at most this
# much, not one it never crosses, and saying otherwise made a false claim of the record.
MIN_REQUEST_SECONDS = 0.1

SHA_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")


# The transport is the shared GitHub client's engine (Decision 0100), merged from this
# collector's and four others. These names are this collector's view of it.
#
# A provider failure is deliberately not a ``ValueError``: the per-file handler records
# an unusable *pathname* by catching that, and a truncated or malformed body filed under
# that label would tell the reviewer a wrong cause, which is worse than a missing file.
ProviderError = github_rest.GitHubReadError
# The collection's wall-clock budget ran out before a request.
DeadlineReached = github_rest.DeadlineReached
# A refused redirect. Every redirect is refused: the scheme and host are pinned, so a
# safe redirect would have to be the same URL, and GitHub's redirect of a renamed or
# transferred repository is refused too -- the collection records `unsafe-redirect`
# rather than bytes whose origin it cannot state.
UnsafeRedirect = github_rest.UnsafeRedirect
pinned_redirect_handler = github_rest.refusing_redirects


# The comparison's schema and the contents API are the adapter's; the names this
# collector's callers and tests have always read are bound here to the one definition.
usable_files = github.usable_files
reduce_listing = github.reduce_listing
decoded_file = github.decoded_file
base_endpoint = github.base_endpoint
listing_endpoint = github.listing_endpoint
PROVIDER_URL = github.PROVIDER_URL
quote_path = base.quote_path
safe_relative_path = base.safe_relative_path
write_exact = base.write_exact
blob_id = base.blob_id


def _authorization() -> dict[str, str]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _policy() -> github_rest.Policy:
    """This collector's bounds, read when used, so a test can tighten one here."""
    return github_rest.Policy(
        timeout_seconds=TIMEOUT_SECONDS,
        attempts=ATTEMPTS,
        retry_sleep_seconds=RETRY_SLEEP_SECONDS,
        max_response_bytes=MAX_RESPONSE_BYTES,
        max_rate_limit_wait=MAX_RATE_LIMIT_WAIT,
        unhinted_rate_limit_wait=UNHINTED_RATE_LIMIT_WAIT,
        error_detail_bytes=ERROR_DETAIL_BYTES,
        error_detail_seconds=ERROR_DETAIL_SECONDS,
        min_request_seconds=MIN_REQUEST_SECONDS,
        read_chunk_bytes=READ_CHUNK_BYTES,
        max_abandoned=MAX_ABANDONED,
        workers=_ABANDONED,
    )


def rate_limit_pause(
    error: urllib.error.HTTPError,
    attempt: int,
    now: float | None = None,
    detail_deadline: float | None = None,
) -> float:
    """Return how long to wait before retrying ``error``, under this policy."""
    return github_rest.rate_limit_pause(error, attempt, now, detail_deadline, _policy())


def is_rate_limited(
    error: urllib.error.HTTPError, detail_deadline: float | None = None
) -> bool:
    """Return whether a 4xx is GitHub reporting a rate limit rather than a refusal."""
    return github_rest.is_rate_limited(error, detail_deadline, _policy())


def request_timeout(deadline: float | None) -> float:
    """Return the timeout for one request, never longer than the budget that remains."""
    return github_rest.request_timeout(deadline, _policy())


def provider_json(url: str, deadline: float | None = None) -> Any:
    """Return the provider's JSON for ``url``, or the transport sentinel on 404.

    `None` is the internal transport sentinel for "the provider answered not-found" and
    nothing else: it settles no question about the repository. What the base does or
    does not hold is settled by the comparison.

    A **transient** failure is retried instead of propagating: the collection makes one
    listing request per changed directory plus one contents request per changed file,
    so a single 502 or timeout anywhere in that sequence would otherwise cost the whole
    review. Server errors, rate limits and transport failures are retried within the
    collection deadline; everything else propagates on the first attempt.
    """
    # Checked here, at the point of use, and before any environment lookup. The value
    # that reaches the request is what matters, and trusting it because an earlier
    # function was careful is how the first version of this validation came to accept a
    # leading dash.
    if not PROVIDER_URL.match(url):
        raise ValueError(f"refusing an unexpected provider URL: {url!r}")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": github_rest.JSON_MEDIA_TYPE,
            "X-GitHub-Api-Version": github_rest.API_VERSION,
            **_authorization(),
        },
        method="GET",
    )
    # `fetch_json` is resolved when called, so this module's one attempt is the one used.
    return github_rest.read_with_retries(
        url,
        request,
        lambda target, prepared, timeout: fetch_json(target, prepared, timeout),
        deadline=deadline,
        missing_ok=True,
        policy=_policy(),
    )


# At most this many of this collector's abandoned workers may still be running. Each
# keeps its socket until its receive ends or the process does, and the deadline alone
# bounded them only by the time each cost: about 20 request workers, and up to about
# 120 if every error body stalled its read. Past the cap a request fails at once
# instead. (CodeAnt)
MAX_ABANDONED = 16
# This collector's abandoned workers; pruned before each new one is counted.
_ABANDONED: list[threading.Thread] = []


def fetch_json(
    url: str,
    request: urllib.request.Request,
    timeout: float | None = None,
) -> Any:
    """Perform one request, bounded as a whole. The sentinel is produced only above."""
    limit = float(TIMEOUT_SECONDS if timeout is None else timeout)
    # `_read_json` is resolved when called: it is the one attempt this bound encloses.
    return github_rest.abandon_after(
        limit, url, lambda: _read_json(url, request, limit), _policy()
    )


def _read_json(url: str, request: urllib.request.Request, limit: float) -> Any:
    """Perform the request itself, bounded between receives, and decode it."""
    opener = urllib.request.build_opener(pinned_redirect_handler())
    raw, _ = github_rest.exchange_once(opener, request, limit, _policy())
    return github_rest.decode_json(raw, url)


def collect(
    context: pathlib.Path, repository: str, budget: int
) -> tuple[int, list[str]]:
    """Write pre-change revisions under ``base/``.

    Returns the number of files written and one manifest line per file that is not.
    """
    written, unavailable, _ = collect_listing(context, repository, budget)
    return written, unavailable


def collect_listing(
    context: pathlib.Path, repository: str, budget: int
) -> tuple[int, list[str], bool]:
    """Collect as ``collect`` does, and say whether the comparison listed its files.

    The bounds are this module's, read when called: a test can tighten one here.
    """
    comparison = github.read_comparison(context / "comparison.json")

    def read(url: str, deadline: float | None = None) -> Any:
        """Read through this module's reader, looked up when called: a test can stand
        in for the provider here."""
        return provider_json(url, deadline)

    source = github.ContentsSource(
        repository, comparison.merge_base, read, api_root=API_ROOT
    )
    source.listing_cap = LISTING_CAP
    return base.collect(
        context,
        comparison,
        source,
        budget=budget,
        file_cap=FILE_CAP,
        deadline_seconds=DEADLINE_SECONDS,
        line_cap=claude_code.READ_LINE_CAP,
    )


def main(argv: list[str]) -> int:
    """Collect pre-change revisions for ``<context-dir> <repository> <budget-bytes>``."""
    if len(argv) != 4:
        print(
            f"usage: {argv[0]} <context-dir> <repository> <budget-bytes>",
            file=sys.stderr,
        )
        return 2
    _, _, listed = collect_listing(
        within(argv[1], "GITHUB_WORKSPACE", must_exist=True), argv[2], int(argv[3])
    )
    # 3: finished, but the comparison named no file list, so an empty fallback diff
    # later in the step is not an empty change. Decision 0094 rule 37.
    return 0 if listed else 3


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
