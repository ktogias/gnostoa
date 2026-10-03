"""Build the bounded review context from one provider comparison payload.

Writes ``diff.stat``, ``no-patch.txt``, ``base.manifest`` and ``base/``. Deriving
them from a single payload keeps the comparison to one request, keeps the workflow step
free of an external ``jq``, and puts the field semantics somewhere the suite can
exercise directly rather than by scraping YAML.

``base/`` matters most. The bounded reviewer of Decision 0094 reads the repository's
default branch for its entry route and general context, and that tree is deliberately
**not** this Pull Request's base: the branch may have advanced, or the Pull Request may
target another branch. Unchanged code read from it can therefore come from a revision
the candidate never saw, which produces interaction findings that are not real. So the
exact pre-change bytes of the changed files this collection could fetch are written
here, and every file it could not is named in ``base.manifest`` with its reason --
for the files the provider listed. A comparison past GitHub's changed-file cap never
sends the later paths at all, so they can be neither fetched nor named; the manifest
states that instead of leaving the omission to look like completeness.

Four properties of that collection are load-bearing, and each exists because getting it
wrong would hand the reviewer something false rather than something missing:

* the revision fetched is the **merge base**, not the base branch tip, because a
  three-dot comparison is computed from the merge base and mixing the two would describe
  two different pre-change states;
* a **renamed** entry is fetched under ``previous_filename``, since that is where the
  base holds it, and fetching the new path could return an unrelated file that a swap or
  overwrite rename happens to have replaced;
* a response that is not an ordinary base64 ``file`` -- a symlink the API resolved to its
  target, or a large file returned with ``encoding: "none"`` -- is recorded as
  unavailable rather than written, because resolved or empty bytes presented as the
  exact base are worse than an acknowledged gap;
* every path the provider listed and this collection did not write is named in
  ``base.manifest`` with the reason, so the reviewer can see which file it cannot rely
  on instead of inferring it from a count -- and a capped comparison says that the
  paths beyond the cap are absent from the manifest entirely.

Bytes are written, never a checkout: no mode, symlink or directory entry from either
side reaches the runner, which is what keeps rule 21 intact. Provider-supplied names are
refused rather than sanitised when absolute, empty, traversing, or carrying a backslash
or NUL, because a name that should not occur is a reason to stop instead of to guess.
The manifest lives outside ``base/`` so it cannot collide with a repository path.

There is no subprocess here. The request is an ordinary HTTPS GET whose URL is matched
against a pattern pinning scheme, host and shape, so no argument can be mistaken for a
flag and no other origin is representable.

Invoked from ``.github/workflows/claude.yml``, which for the mention triggers runs from
the repository's default branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import base64
import errno
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from chunk_diff import wrap_long_records

from tools import github_rest
from tools.agent_review_paths import within

API_ROOT = "https://api.github.com"
FILE_CAP = 300
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
LISTING_CAP = 1000
# The only fields a listing record is read for. The contents API sends `_links`,
# `download_url`, `git_url`, `html_url` and `url` alongside them, and keeping the whole
# record retained all of that for every changed file -- the third route to the same
# exhaustion, after the malformed shapes and the unmatched records.
_LISTING_FIELDS = ("name", "type", "size", "sha")
# Selecting those fields is not enough: their *values* are the provider's, and a valid
# array whose matching record carries a megabyte-long `type` or `sha` reopens the same
# exhaustion. Each is normalised to the representation the code downstream uses -- a
# type it can compare, a size it can subtract, an identity that matches `SHA_PATTERN` -- so
# nothing is retained that the collection would not have used anyway.
_TYPE_LIMIT = 32
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
_MANIFEST = "base.manifest"
# Where every write is staged before its rename: beside base/, never inside it, so an
# interrupted write is absent rather than partial. The workflow sweeps this same name.
_STAGING = ".base-staging"
# The errors a type collision between two changed paths raises: a file where a
# directory goes, or a directory where a file goes.
_COLLISION_ERRNOS = frozenset({errno.EEXIST, errno.ENOTDIR, errno.EISDIR})

# Validated on the raw string. PurePosixPath normalises "a//b" and "." away, so
# inspecting its parts would accept names that should never have been produced.
_REFUSED_COMPONENTS = frozenset({"", ".", ".."})
SHA_PATTERN = re.compile(r"\A[0-9a-f]{40}\Z")
# Each side must begin with an alphanumeric. A leading dash is precisely the shape an
# earlier version of this check accepted, and the reason it is spelled out here.
_REPOSITORY = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")
# Pins scheme, host and shape together, so the request cannot be pointed at another
# origin whatever reaches the fetch.
PROVIDER_URL = re.compile(
    r"\Ahttps://api\.github\.com/repos/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/contents/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*\?ref=[0-9a-f]{40}\Z"
)


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


def safe_relative_path(name: str) -> pathlib.PurePosixPath:
    """Return ``name`` as a relative path, refusing anything that could escape."""
    if not name or name.startswith("/") or name.endswith("/"):
        raise ValueError(f"refusing a non-relative path: {name!r}")
    if "\\" in name or "\x00" in name:
        raise ValueError(f"refusing a path with a backslash or NUL: {name!r}")
    components = name.split("/")
    if any(component in _REFUSED_COMPONENTS for component in components):
        raise ValueError(f"refusing a degenerate or traversing path: {name!r}")
    return pathlib.PurePosixPath(*components)


def base_endpoint(repository: str, path: str, base_sha: str) -> str:
    """Build the contents URL for ``path`` at ``base_sha``."""
    if not _REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not SHA_PATTERN.match(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = urllib.parse.quote(str(safe_relative_path(path)), safe="/")
    return f"{API_ROOT}/repos/{repository}/contents/{encoded}?ref={base_sha}"


def listing_endpoint(repository: str, directory: str, base_sha: str) -> str:
    """Build the contents URL for a directory listing at ``base_sha``."""
    if not _REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not SHA_PATTERN.match(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = (
        urllib.parse.quote(str(safe_relative_path(directory)), safe="/")
        if directory
        else ""
    )
    return f"{API_ROOT}/repos/{repository}/contents/{encoded}?ref={base_sha}"


class _MalformedListing:
    """Stands in for a directory response that was not an array.

    Only the array-shaped responses were reduced at first, so a provider returning a
    large syntactically valid object for each of `FILE_CAP` directories still filled
    the runner while every individual response respected the size cap. A reduction has
    to cover every shape it caches, not the convenient one. This carries no payload and
    still classifies as a shape error, because it is neither `None` -- the not-found
    transport sentinel -- nor a list.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover -- diagnostics only
        return "<malformed directory listing>"


_MALFORMED_LISTING = _MalformedListing()


def _text(value: Any) -> str:
    """Return ``value`` if the provider sent a string, and "" for anything else.

    A provider field is read as the JSON type it arrived as. `str()` turned a null into
    "None" -- a name a changed path can have -- so a listing record with no name matched
    the path `None`, and its type and blob id authorised the write. It turned a 40-digit
    number into something `SHA_PATTERN` accepts, so malformed metadata could make two
    blob ids equal and call a change `metadata-only`. An empty string is what every
    reader here already treats as absent.
    """
    return value if isinstance(value, str) else ""


def reduce_listing(listing: Any, needed: set[str]) -> tuple[Any, int]:
    """Return only the records ``needed`` from ``listing``, and its original length.

    The cache used to hold every parsed directory response until the collection
    finished. A response may approach ``MAX_RESPONSE_BYTES``, so a change touching one
    file in each of many crowded directories retained gigabytes: the per-response bound
    bounds each answer and not their sum, which is the same mistake the read loop made
    with time before its deadline became absolute.

    A directory is consulted for two things -- the records of the names the comparison
    places in it, and whether the provider capped the list -- so those are what is kept.
    The original length is returned separately because the truncation notice depends on
    it and a reduced list can no longer report it. `None` -- the not-found transport
    sentinel -- passes through; anything else that is not a list is replaced by a
    payload-free stand-in that still classifies as a shape error, because retaining a
    large malformed response is the same exhaustion by another route.
    """
    if listing is None:
        return None, 0
    if not isinstance(listing, list):
        return _MALFORMED_LISTING, 0
    kept = [
        _bounded_record(item)
        for item in listing
        if isinstance(item, dict) and _text(item.get("name")) in needed
    ]
    return kept, len(listing)


def _bounded_record(item: dict[str, Any]) -> dict[str, Any]:
    """Return the record as the bounded values the rest of the collection reads."""
    declared = item.get("type")
    size = item.get("size")
    sha = _text(item.get("sha"))
    return {
        # Equal to a name this collection asked for, so already bounded by its own set.
        "name": _text(item.get("name")),
        # Compared against "file"; anything longer than a declared type could be is not
        # one, and an empty string reads as a type this collection will not write.
        "type": declared
        if isinstance(declared, str) and len(declared) <= _TYPE_LIMIT
        else "",
        # Subtracted from the remaining budget. A larger value still says "larger than
        # anything this collection will write" without carrying the digits to say it,
        # and a non-integer is no size at all.
        "size": min(size, MAX_RESPONSE_BYTES + 1)
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0
        else None,
        # Matched against `SHA_PATTERN` before it is compared with real bytes, so a value that
        # cannot match is worth nothing and is not kept.
        "sha": sha if SHA_PATTERN.match(sha) else "",
    }


def listing_entry(listing: Any, name: str) -> dict[str, Any] | None:
    """Return the ``listing`` record for ``name``, or None when it is not there."""
    if not isinstance(listing, list):
        return None
    for item in listing:
        if isinstance(item, dict) and _text(item.get("name")) == name:
            return item
    return None


def _records_named(listing: Any, name: str) -> int:
    """Return how many records in a directory ``listing`` carry ``name``."""
    if not isinstance(listing, list):
        return 0
    return sum(
        1
        for item in listing
        if isinstance(item, dict) and _text(item.get("name")) == name
    )


def entry_type(listing: Any, name: str) -> str | None:
    """Return the declared type of ``name`` within a directory ``listing``."""
    item = listing_entry(listing, name)
    return _text(item.get("type")) if item else None


_C_ESCAPES = {
    0x07: "\\a",
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0B: "\\v",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


# Git's own rule is not sufficient here. `git -c core.quotePath=false` prints U+0085,
# U+2028 and U+2029 raw, because Git orients on bytes -- but these artefacts are read by
# a Unicode-aware reader, and Python's ``str.splitlines`` treats all three as line
# breaks. A name carrying one would recreate exactly the forged-record problem that
# escaping the C0 controls closed.
_UNICODE_BREAKS = frozenset("\u0085\u2028\u2029")


def _must_escape(ch: str) -> bool:
    """Return whether ``ch`` could end a line, or fail to encode, in these artefacts.

    A lone surrogate is valid JSON (`"\\ud800"`) and no UTF-8 writer can encode it: the
    first summary write raised before the per-file isolation existed, so one such name
    cost the whole collection. (Codex)
    """
    code = ord(ch)
    return (
        code < 0x20 or code == 0x7F or ch in _UNICODE_BREAKS or 0xD800 <= code <= 0xDFFF
    )


def quote_path(name: str) -> str:
    """Return ``name`` the way ``git -c core.quotePath=false`` would print it.

    Git permits a newline in a pathname and the comparison carries it through as JSON,
    but every artefact this script writes is read line by line. A name interpolated
    verbatim could therefore add a `+++ b/other.py` header, a diff line or an extra
    summary record, and a reviewer with no git and no candidate tree has nothing to
    check that against. Quoting is used rather than refusal because such a name is a
    legal path: dropping the file would hide a real change.

    Control characters, a double quote and a backslash are C-quoted; UTF-8 is left
    alone, exactly as Git does with `core.quotePath=false`. A legitimate international
    filename is not a line-injection risk, and quoting it would only make the artefacts
    harder to read.
    """
    if not any(_must_escape(ch) or ch in '"\\' for ch in name):
        return name
    out = ['"']
    for ch in name:
        code = ord(ch)
        if code in _C_ESCAPES:
            out.append(_C_ESCAPES[code])
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\{code:03o}")
        elif _must_escape(ch):
            # Octal of the UTF-8 bytes, which is how `git -c core.quotePath=true`
            # renders a non-ASCII byte -- so the escape stays in Git's own vocabulary
            # even though Git itself does not escape these.
            # A surrogate has no UTF-8 bytes; its surrogatepass bytes stand in for it.
            out.extend(f"\\{byte:03o}" for byte in ch.encode("utf-8", "surrogatepass"))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def write_exact(
    destination: pathlib.Path,
    content: bytes,
    writer: Any = None,
    *,
    staging: pathlib.Path,
) -> None:
    """Write ``content`` so that a failure leaves nothing behind.

    The manifest names a file it could not obtain, and the prompt calls ``base/`` the
    exact pre-change revision. A half-written file satisfies neither: it would sit there
    looking exact while the manifest said the file was unavailable. The bytes go to a
    temporary name and are renamed into place only once they are all there; anything
    left over is removed on the way out.

    The temporary name lives in ``staging``, outside ``base/``. It used to sit beside
    its destination, and the sweep that removes an interrupted write after a hard stop
    then had to recognise staging files by name inside ``base/``. No name can be told
    apart from a real one -- any filename is a legal Git path, and a rename lets the
    candidate choose the destination name -- so a real file in the staging shape was
    deleted while ``Written:`` still counted it. A separate directory needs no
    recognising: the workflow removes it whole. Required, so no caller can stage beside
    a real file by omission.
    """
    staging.mkdir(parents=True, exist_ok=True)
    # A unique name, because `<name>.partial` is itself a legal pathname: a Pull
    # Request touching both `x.partial` and `x` would have the second write overwrite
    # the first file and then rename it away, leaving a silent gap that the manifest
    # never records and `Written:` still counts.
    # A short digest of the name, not the name itself: copying a basename that
    # approaches Linux's 255-byte NAME_MAX and then adding punctuation, randomness and
    # ".partial" overflows it, and mkstemp raises ENAMETOOLONG -- losing a file the
    # collection could otherwise deliver, to the staging mechanism.
    stem = hashlib.sha256(destination.name.encode()).hexdigest()[:16]
    handle, staged = tempfile.mkstemp(
        dir=staging, prefix=f".{stem}.", suffix=".partial"
    )
    os.close(handle)
    scratch = pathlib.Path(staged)
    try:
        if writer is None:
            scratch.write_bytes(content)
        else:
            writer(scratch, content)
        scratch.replace(destination)
    finally:
        scratch.unlink(missing_ok=True)


def write_artefact(
    context: pathlib.Path, name: str, text: str, encoding: str = "utf-8"
) -> None:
    """Write a top-level artefact whole or not at all, through ``write_exact``.

    After a failure the workflow creates only the artefacts that are *missing*, so an
    artefact left half-written -- assembled.diff was streamed into place entry by entry
    -- was kept as if it were whole. Rendered first and renamed into place complete, an
    interrupted artefact is absent instead, which the workflow reports for what it is.
    """
    # Total over provider text: a lone surrogate in a `patch` is written as its escape
    # rather than raising before the manifest exists. Names are already quoted.
    data = text.encode(encoding, "backslashreplace")
    # Read line by line, by a reader that truncates a physical line past the chunker's
    # cap and seeks only by line: a long path made its record unreachable at the tail.
    # Wrapped as the diff is. Every record here begins with a status word, so a line
    # beginning with the continuation marker can only continue the one above. (Codex)
    data, _, _ = wrap_long_records(data)
    write_exact(context / name, data, staging=context / _STAGING)


def write_streamed(
    context: pathlib.Path, name: str, render: Callable[[Any], None]
) -> None:
    """Write a top-level artefact whole or not at all, rendered into its staging file.

    For an artefact as large as the change itself. Rendering it into memory first held
    the fallback diff three times over -- the resident patches, the rendered string and
    its encoding -- and a large Pull Request could exhaust the runner before
    `base.manifest` was written.
    """

    def stream(path: pathlib.Path, _content: bytes) -> None:
        """Render the artefact into the staging file ``write_exact`` hands over."""
        with path.open("w", encoding="utf-8", errors="backslashreplace") as handle:
            render(handle)

    write_exact(context / name, b"", stream, staging=context / _STAGING)


def base_path_of(entry: dict[str, Any]) -> str:
    """Return the path the base revision holds this entry under."""
    if entry.get("status") in ("renamed", "copied"):
        # A copy carries previous_filename exactly as a rename does, and the source is
        # the one thing a copy is about: without it the fallback claims the destination
        # existed on the base side and no summary says where the content came from.
        previous = _text(entry.get("previous_filename"))
        if not previous:
            raise ValueError(f"a {entry['status']} entry carries no previous_filename")
        return previous
    return str(entry["filename"])


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


def blob_id(content: bytes) -> str:
    """Return Git's object id for ``content`` as a blob.

    Git defines it as the SHA-1 of ``blob <length>\\0`` followed by the bytes, which
    was confirmed against ``git hash-object``. SHA-1 appears here because that is what
    the identity being checked *is*, not as a security primitive.
    """
    # The algorithm is not a choice here: a Git blob id *is* the SHA-1 of that byte
    # string, so computing anything else would not be the identity being checked. It is
    # used to compare against a value the provider supplies, never to authenticate
    # anything, which `usedforsecurity=False` states to the runtime as well as to a
    # reader.
    return hashlib.sha1(  # nosec B324  # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1
        b"blob %d\0" % len(content) + content,
        usedforsecurity=False,
    ).hexdigest()


def decoded_file(payload: dict[str, Any]) -> tuple[bytes | None, str]:
    """Return the payload's bytes, or ``None`` and the reason they are not usable.

    The response *shape* cannot identify a symlink: the contents API answers a symlink
    to a regular file with the target's content under an ordinary ``type: file``. The
    authoritative check is the parent directory's listing, which declares
    ``type: symlink``; this function only rejects what the response itself rules out.

    The reason is returned rather than left to the caller, because the caller cannot
    recover it. Every failure used to arrive as a bare ``None`` and be recorded as
    ``not-a-plain-file`` -- a claim about the **repository** -- when three of the five
    causes say only that the provider's answer was unusable. `base.manifest` is the
    reviewer's provenance and it has no way to question what it is told, so a response
    this collection could not read must not be published as a fact about the base
    revision. The two genuinely repository-side causes keep the label they earned: a
    declared non-file type, and the ``encoding: "none"`` an oversized blob comes back
    with.
    """
    # A syntactically valid response of the wrong shape -- a list where an object was
    # expected -- reached `.get` and raised AttributeError, which no handler catches, so
    # the collection ended before base.manifest was written. Every other malformed
    # answer is that file's gap; this one took the review.
    if not isinstance(payload, dict):
        return None, "provider-error: its contents response was not an object"
    # Only *declared* metadata is a fact about the repository. The parent listing has
    # already called this entry a file, so an absent type or an absent or unknown
    # encoding says only that the provider's answer was unusable.
    kind = payload.get("type")
    if kind is None:
        return None, "provider-error: its contents response declared no type"
    if kind in ("dir", "symlink", "submodule"):
        return None, "not-a-plain-file"
    if kind != "file":
        # The listing has already called this path a file. An unknown kind, or one
        # that is not a string, contradicts that answer rather than describing the
        # repository, so it is the provider's error, as the listing's own is.
        return None, "provider-error: its contents response declared no recognised type"
    encoding = payload.get("encoding")
    if encoding == "none":
        # Files above roughly 1 MB come back with `encoding: "none"` and empty content.
        return None, "not-a-plain-file"
    if encoding != "base64":
        state = "no" if encoding is None else "an unknown"
        return None, f"provider-error: its contents response carried {state} encoding"
    content = payload.get("content")
    if not isinstance(content, str):
        return None, "provider-error: its contents response carried no base64 string"
    try:
        # The provider wraps its base64 in newlines, so whitespace is removed rather
        # than tolerated: validate=True then rejects anything else. Without it, a
        # corrupt payload decodes to *some* bytes, and those bytes would be written
        # into base/, which the prompt calls the exact pre-change revision. A quiet
        # wrong answer is worse than a recorded gap.
        return base64.b64decode("".join(content.split()), validate=True), ""
    except ValueError:
        # `binascii.Error` *is* a `ValueError`, so naming both said there were two
        # branches here when there is one. This file names base classes rather than
        # members on purpose -- enumerating them missed a member four times -- and
        # listing a base class beside one of its own members is the same mistake
        # wearing the fix's clothes: it reads as coverage that the base already gave.
        return None, "provider-error: its contents response would not base64-decode"


# The listing kinds whose `sha` is a blob id. A directory's is a tree and a submodule's
# a commit; an absent or unknown type establishes no identity at all.
_BLOB_KINDS = frozenset({"file", "symlink"})


def hunkless_label(entry: dict[str, Any], record: dict[str, Any], name: str) -> str:
    """Classify a change the comparison gave no hunks for.

    ``status`` cannot distinguish a mode-only change from a binary content change:
    both arrive as ``modified`` with no hunks. Blob identity can -- except for a
    removal, where the comparison's ``sha`` *is* the deleted base-side blob and so
    always equals the listing's. Comparing them there would label a deleted file
    ``metadata-only`` and have the reviewer treat a deletion as reviewable metadata.
    A copy is the same trap from the other side: it is fetched under its previous
    path, so an exact copy makes the ids equal at a path that held nothing before.
    """
    if entry.get("status") == "removed":
        return f"removed-without-hunks {quote_path(name)}"
    if _text(record.get("type")) not in _BLOB_KINDS:
        # Compared anyway, an equal `sha` on a record of no blob kind read as
        # metadata-only while the fetch refused the same record. (Codex)
        return f"unclassified-without-blob-identity {quote_path(name)}"
    base_blob = _text(record.get("sha"))
    head_blob = _text(entry.get("sha"))
    if (
        entry.get("status") == "copied"
        and SHA_PATTERN.match(base_blob)
        and head_blob == base_blob
    ):
        # An *exact* copy. It is fetched under its previous path, so the two blob ids
        # are equal -- and metadata-only, which the prompt defines as "the content is
        # the same", would be said about a path that held no content at all before. A
        # whole file appeared. A rename is not this case: the file moved rather than
        # multiplied, and the manifest lists that mapping separately.
        #
        # A copy can also be *edited*, which the first version of this branch returned
        # unconditionally and so denied: the provider reports `copied` with a
        # destination blob differing from the source, the bytes collected into base/
        # are the source's, and no artefact showed that the destination content
        # changed. That case falls through to the comparison below and is labelled
        # `content-changed-without-hunks`, which the prompt already requires the
        # reviewer to report as not examined. The copy mapping is listed either way.
        return f"copied-without-hunks {quote_path(name)}"
    if not (SHA_PATTERN.match(base_blob) and SHA_PATTERN.match(head_blob)):
        # Equality of two *malformed* values is not evidence of identical content. A
        # truncated pair passed the old truthiness test and read as metadata-only,
        # while the base/ guard -- which computes the real blob id -- recorded
        # blob-mismatch for the same path, so the manifest said both that nothing
        # changed and that the identity did not check out. `SHA_PATTERN` is the module's own
        # definition of an identity and is applied to both fields.
        return f"unclassified-without-blob-identity {quote_path(name)}"
    if base_blob == head_blob:
        return f"metadata-only {quote_path(name)}"
    return f"content-changed-without-hunks {quote_path(name)}"


def _short_blob(value: Any) -> str:
    """Return a blob id's first nine characters, or "?" when it is not a blob id.

    `no-patch.txt` is read line by line, and the provider's `sha` was printed as given,
    so one carrying a newline added a record of its own.
    """
    text = _text(value)
    return text[:9] if SHA_PATTERN.match(text) else "?"


def _repeated_names(files: list[Any]) -> dict[str, int]:
    """Return every filename the comparison lists more than once, with its count.

    Counted over every named entry, before any is filtered. Both entries were admitted
    and each fetch wrote the same `base/` destination, so the second replaced the first
    while `Written:` counted two; and counting after the status check let a second
    record dropped for its status leave the first admitted alone. A comparison listing
    a path twice contradicts itself, and which entry is right is unknown. (Codex)
    """
    seen: dict[str, int] = {}
    for entry in files:
        name = entry.get("filename") if isinstance(entry, dict) else None
        if isinstance(name, str) and name:
            seen[name] = seen.get(name, 0) + 1
    return {name: count for name, count in seen.items() if count > 1}


def _count(value: Any) -> str:
    """Return a line count as the provider gave it, or "?" when it gave none.

    Rendering an absent or mistyped count as 0 asserted a number the provider never
    established. (Codex)
    """
    known = isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return str(value) if known else "?"


def _reported_status(entry: dict[str, Any]) -> str:
    """Return the entry's status, or a word saying the provider gave none.

    `usable_files` admits only entries with a documented status (Decision 0094 rule
    35), so the fallback is defensive. It is kept because a bare entry once raised
    `KeyError` out of the summary writer before any manifest existed, and a reader
    that indexes is how that returns.
    """
    status = entry.get("status")
    return status if isinstance(status, str) and status else "unstated"


def usable_files(
    comparison: Any, refused: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return the entries this collection can act on, and notices for the rest.

    Per-file isolation covers what happens *inside* the loop. It did not cover the
    comparison itself: a valid JSON document that is not an object, a file list that is
    not an array, an entry that is not an object, or an entry without a filename each
    reached an unguarded index or attribute and ended `collect` before any manifest
    existed. A review is lost either way, but a manifest naming what could not be read
    is the difference between a reported gap and silence.
    """
    notices: list[str] = []
    if not isinstance(comparison, dict):
        notices.append(
            "provider-error comparison.json: the comparison was not an object"
        )
        return [], notices
    files = comparison.get("files")
    if not isinstance(files, list):
        # `None` is not admitted here, though it is this file's transport sentinel for
        # not-found elsewhere. A comparison that omits `files`, or sends it as null, is
        # unreadable, not empty -- and passing it through as an empty change published
        # `Written: 0. Unavailable: 0` with no notice, so a Pull Request whose unified
        # diff still showed hunks had every changed path left without base bytes and
        # without a line saying why. An empty comparison states itself with `[]`.
        notices.append("provider-error comparison.json: its file list was not an array")
        return [], notices
    sink = notices if refused is None else refused
    repeated = _repeated_names(files)
    usable: list[dict[str, Any]] = []
    for position, entry in enumerate(files):
        if not isinstance(entry, dict):
            notices.append(
                f"provider-error comparison.json: entry {position} was not an object"
            )
            continue
        name = entry.get("filename")
        if not isinstance(name, str) or not name:
            notices.append(
                f"provider-error comparison.json: entry {position} carried no filename"
            )
            continue
        if name in repeated:
            continue  # named once below, as the contradiction it is
        status = entry.get("status")
        # A string first: a list or an object is unhashable, and the membership test
        # alone raised TypeError out of here before any manifest existed. (gitar)
        if not isinstance(status, str) or status not in _STATUSES:
            # Every later step decides from the status -- no base side for an added
            # file, `/dev/null` for a removed one, the old name for a rename -- so an
            # entry without a documented one describes nothing reliably. (Codex)
            # Named, so it is about a path: the collector counts it in `Unavailable:`,
            # which said 0 for a provider-listed path that was never fetched. (Codex)
            sink.append(
                f"provider-error {quote_path(name)}: the comparison entry carried no "
                "recognised status, so nothing about it is stated"
            )
            continue
        clean, malformed = _typed_entry(entry)
        notices.extend(
            f"provider-error comparison.json: the entry for {quote_path(name)} "
            f"carried a {field} of the wrong type, so it is treated as absent"
            for field in malformed
        )
        usable.append(clean)
    sink.extend(
        f"provider-error {quote_path(name)}: the comparison listed it {count} times, "
        "so none of its entries is used"
        for name, count in repeated.items()
    )
    return usable, notices


# Every field of a comparison entry this collection reads, with the JSON type it must
# arrive as. Checked once, where the entry is admitted: each reader had been trusted to
# check for itself, and review after review found one that coerced instead.
# The statuses GitHub documents for a comparison entry. Admission requires one of them.
_STATUSES = frozenset(
    {"added", "removed", "modified", "renamed", "copied", "changed", "unchanged"}
)
# The only entry field GitHub's published diff-entry schema marks nullable. A `patch`
# is an optional string that a binary file omits -- a changed PNG on microsoft/vscode
# carried no `patch` key at all -- so a present null is malformed, not an absence.
# Skipping every null read a null `patch` or `previous_filename` as legitimate.
# (CodeAnt)
_NULLABLE_FIELDS = frozenset({"sha"})
_ENTRY_FIELDS: dict[str, type] = {
    "patch": str,
    "sha": str,
    "previous_filename": str,
    "additions": int,
    "deletions": int,
}


def _typed_entry(entry: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return ``entry`` with each field read later in its own type, and the rest named.

    A field of another type becomes absent, which every reader already handles; the
    caller names it, so a malformed provider answer is a stated gap rather than a
    coerced value. A count is a whole number, so a boolean is not one.
    """
    clean = dict(entry)
    # An empty patch is no hunks. Counted as hunks, a refused diff left the file out of
    # no-patch.txt and its blob-identity verdict, with no content and no notice. (Codex)
    if clean.get("patch") == "":
        clean["patch"] = None
    malformed = []
    for field, kind in _ENTRY_FIELDS.items():
        if field not in entry:
            continue  # omitted, which is how GitHub leaves out a patch
        value = entry[field]
        if value is None and field in _NULLABLE_FIELDS:
            continue
        # A count is a non-negative whole number: `-1` rendered as `+-1`, malformed
        # metadata presented as exact provenance. (Codex)
        negative = isinstance(value, int) and value < 0
        if (
            value is None
            or not isinstance(value, kind)
            or isinstance(value, bool)
            or negative
        ):
            clean[field] = None
            malformed.append(field)
    return clean, malformed


def write_assembled(handle: Any, comparison: dict[str, Any]) -> None:
    """Write the per-file fallback diff one entry at a time.

    Every patch string used to be concatenated into a single value before being written,
    which held the whole fallback diff a second time -- the patches are already resident
    from parsing `comparison.json`, so the join was a duplicate of the largest thing in
    memory. Writing per entry removes that copy.
    """
    for entry in comparison.get("files") or []:
        handle.write(f"--- {old_side(entry)}\n+++ {new_side(entry)}\n")
        if entry.get("patch") is not None:
            handle.write(f"{entry['patch']}\n")
        else:
            # A metadata-only change has no hunks, and dropping it here would have
            # removed a reviewable change from the fallback entirely.
            handle.write(f"[no hunks: {_reported_status(entry)}; see no-patch.txt]\n")


def write_summaries(
    context: pathlib.Path, comparison: dict[str, Any], delivered: int
) -> None:
    """Write diff.stat and no-patch.txt from the comparison payload.

    ``delivered`` is how many entries the provider actually sent, which the cap notice
    depends on and a reduced list can no longer report. The comparison reaching here has
    already been narrowed to the entries the collection can act on, so counting its
    length dropped the notice whenever one of a capped 300 was unusable, and a truncated
    change read as complete. The directory listing's truncation notice had the same
    defect and the same fix; this one was introduced one function away from it.
    """
    files = comparison.get("files") or []
    # A rename's old path is part of what changed. Emitting only the new name leaves
    # the reviewer unable to say where the file came from, which matters most in the
    # swap and overwrite cases where another file already occupied the new path.
    lines = [
        f"{_reported_status(entry)} +{_count(entry.get('additions'))} "
        f"-{_count(entry.get('deletions'))} "
        + (
            f"{quote_path(_text(entry.get('previous_filename')))} -> "
            f"{quote_path(str(entry['filename']))}"
            if entry.get("status") in ("renamed", "copied")
            and _text(entry.get("previous_filename"))
            else quote_path(str(entry["filename"]))
        )
        for entry in files
    ]
    if delivered >= FILE_CAP:
        # The provider caps this list and does not paginate it, so a list that reached
        # the cap must not be allowed to read as the whole change. Counted from what
        # the provider *sent*, before unusable entries are dropped, so filtering cannot
        # hide that the cap was reached.
        #
        # What is established is that the list *reached* the maximum -- not that
        # anything was dropped. A change with exactly `FILE_CAP` files is complete and
        # indistinguishable from a truncated one, because the payload carries no total.
        # Saying "is incomplete" turned that into a certainty and the prompt makes the
        # reviewer repeat it, so an exactly-at-cap change was reported as truncated: a
        # false limitation in the review's own output. The condition observed is
        # stated, not the conclusion it merely permits.
        lines.append(
            f"[the changed-file list reached the provider's maximum of {FILE_CAP} "
            "and is not paginated, so this summary may be incomplete; nothing here "
            "says whether a further file exists]"
        )
    write_artefact(
        context, "diff.stat", "".join(f"{line}\n" for line in lines), encoding="utf-8"
    )
    # A missing per-file patch is a neutral fact, not a file type. It happens for a
    # binary or oversized blob, and equally for a metadata-only change -- a mode bit, an
    # empty file, a rename with no textual edit -- which is perfectly reviewable. Saying
    # "binary or oversized" here made the reviewer report a real change as not examined.
    without_patch = [entry for entry in files if entry.get("patch") is None]
    write_artefact(
        context,
        "no-patch.txt",
        "".join(
            [
                "Changed files for which the comparison carried no hunks. This means\n",
                "either a binary or oversized blob, whose bytes are in neither the\n",
                "diff nor the checkout, or a metadata-only change such as a mode bit,\n",
                "an empty file or a pure rename. The status below does NOT distinguish\n",
                "them: a binary content change and a mode-only change both arrive as\n",
                "'modified' with no hunks. A real unified diff does, by its mode lines\n",
                "and its binary notice, and base.manifest classifies by blob identity.\n",
                "If patches-source is present the diff was assembled per file and\n",
                "carries neither, so report such an entry as not examined.\n",
                "\n",
            ]
            + [
                f"{_reported_status(entry)} {_short_blob(entry.get('sha'))} "
                + (
                    f"{quote_path(_text(entry.get('previous_filename')))} -> "
                    f"{quote_path(str(entry['filename']))}\n"
                    if entry.get("status") in ("renamed", "copied")
                    and _text(entry.get("previous_filename"))
                    else f"{quote_path(str(entry['filename']))}\n"
                )
                for entry in without_patch
            ]
        ),
        encoding="utf-8",
    )


def old_side(entry: dict[str, Any]) -> str:
    """Return the diff header's left side, or /dev/null when there was no left side.

    Unified diff names the nonexistent side `/dev/null`. Writing `--- a/<name>` for an
    added file tells a reviewer with no tree and no base that the file existed before
    the change, and on the assembled fallback that header is the only description of it
    the reviewer gets.
    """
    if entry.get("status") == "added":
        return "/dev/null"
    try:
        return quote_path("a/" + base_path_of(entry))
    except ValueError:
        # A renamed or copied entry with no `previous_filename`. `/dev/null` would
        # assert the candidate added it, and inventing a path would assert a base-side
        # name the comparison never gave -- so the header says it is unresolved, which
        # is a token no pathname can be. This escaped `collect` before the manifest was
        # written, so one such entry cost the whole review: the second place the
        # per-file isolation was broken for this input, and the older of the two.
        return "(unresolved: the comparison gave no previous_filename)"


def new_side(entry: dict[str, Any]) -> str:
    """Return the diff header's right side, or /dev/null for a removal."""
    if entry.get("status") == "removed":
        return "/dev/null"
    return quote_path("b/" + str(entry["filename"]))


def write_commits(context: pathlib.Path) -> None:
    """Render commits.log from the base64-carried subjects the step collected.

    A commit subject is candidate-controlled text and this artefact is read line by
    line, so it is escaped exactly as a pathname is. The step cannot do it: splitting a
    message on "\\n" leaves a Unicode line separator intact, and the subject could then
    add a standalone fake commit, or a fake provider-cap notice, to a file the reviewer
    trusts.
    """
    source = context / "commits.b64"
    if not source.exists():
        return
    records = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sha, _, encoded = line.partition(" ")
        try:
            raw = base64.b64decode(encoded, validate=True) if encoded else b""
        except ValueError:
            # `binascii.Error` is a `ValueError`; see the decode guard above for why
            # the base class alone is named.
            # One unreadable subject is that commit's gap, not the step's. Saying so
            # keeps the record count honest, which is what the cap notice counts.
            records.append(f"{sha} [subject unavailable]\n")
            continue
        records.append(f"{sha} {quote_path(raw.decode('utf-8', 'replace'))}\n")
    write_artefact(context, "commits.log", "".join(records))
    source.unlink()


class _Collection:
    """What one collection carries from one changed file to the next.

    Held in one place so each step of the per-file walk can be its own function; the
    walk was a single body of some forty branches.
    """

    def __init__(
        self, context: pathlib.Path, repository: str, merge_base: str, budget: int
    ) -> None:
        self.context = context
        self.repository = repository
        self.merge_base = merge_base
        self.remaining = budget
        self.deadline = 0.0
        # Which names each directory is consulted for, known up front because the
        # comparison names every changed path. Retention is then bounded by the number
        # of changed files rather than by the size of the directories they live in.
        self.needed_names: dict[str, set[str]] = {}
        self.listings: dict[str, Any] = {}
        self.listed_totals: dict[str, int] = {}
        self.unavailable: list[str] = []
        # Notices about the collection rather than about a file. They belong in the
        # manifest and not in `Unavailable:`, which counts paths: appending one here
        # reported five unavailable files for a change that had four, in the line the
        # reviewer is told to trust.
        self.classified: list[str] = []
        self.written = 0


def _read_comparison(
    context: pathlib.Path,
) -> tuple[Any, list[dict[str, Any]], list[str], list[str]]:
    """Return the delivered comparison, its usable entries, notices and refused paths.

    A refused path is one the comparison named but described too badly to act on; the
    collection counts it as unavailable.
    """
    try:
        delivered: Any = json.loads(
            (context / "comparison.json").read_text(encoding="utf-8")
        )
    except Exception as error:
        # The outermost escape, and the last one. Guarding the comparison's *shape*
        # left its *parse* unguarded, so malformed JSON, a body that is not UTF-8, or a
        # file that cannot be read at all raised out of `collect` before any manifest
        # existed: the step failed and the reviewer got nothing, not even a statement of
        # why. Naming the base class rather than its members is the same choice made at
        # the provider decode, for the same reason -- every way this can fail means the
        # comparison is unusable, and four enumerations in this file have each missed a
        # member.
        #
        # The shape check is skipped rather than run against the empty object the parse
        # failure left behind: it would report the missing file list as a second
        # provider error, which is a symptom of the first and not an independent cause.
        return (
            {},
            [],
            [
                f"provider-error comparison.json: it could not be read "
                f"({type(error).__name__}), so no changed file could be named"
            ],
            [],
        )
    refused: list[str] = []
    files, notices = usable_files(delivered, refused)
    return delivered, files, notices, refused


def _without_merge_base(state: _Collection, ordered: list[dict[str, Any]]) -> None:
    """Name every changed path when the comparison carried no exact merge base."""
    for entry in ordered:
        quoted = quote_path(str(entry["filename"]))
        hunkless = entry.get("patch") is None
        if entry.get("status") == "added":
            # Settled by the comparison alone: an added file has no base-side path
            # to fetch, needs no revision and would have made no request. Losing
            # the merge base must not take a verdict this collection already has.
            state.unavailable.append(f"added-by-candidate {quoted}")
            if hunkless:
                state.classified.append(f"added-without-hunks {quoted}")
        else:
            # Named individually. `base.manifest` promises provenance per path, and
            # a single summary record said `Unavailable: 1` for a change where
            # nothing at all was fetched, naming none of the files it happened to.
            state.unavailable.append(
                f"provider-error {quoted}: no exact merge base revision in the "
                "comparison"
            )
            if hunkless:
                state.classified.append(f"unclassified-no-base-record {quoted}")


def _needed_names(ordered: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Return, per base directory, the names the changed files need from it."""
    needed_names: dict[str, set[str]] = {}
    for entry in ordered:
        if entry.get("status") == "added":
            continue
        try:
            source = base_path_of(entry)
            safe_relative_path(source)
        except ValueError:
            # Left to the per-file handler, which records it as `unsupported-path` and
            # costs that one file. Raising here escaped `collect` before any manifest
            # was written, so one malformed comparison entry cost the whole review --
            # the per-file isolation this collection is built around, undone by a
            # pre-pass that only wanted to know which listing records to keep.
            continue
        parent = str(pathlib.PurePosixPath(source).parent)
        parent = "" if parent == "." else parent
        needed_names.setdefault(parent, set()).add(pathlib.PurePosixPath(source).name)
    return needed_names


def _base_record(state: _Collection, source: str) -> dict[str, Any] | None:
    """Return the parent listing's record for ``source``, or name the gap and None."""
    # The parent listing declares the entry's real type. Asking the contents API
    # alone cannot: it answers a symlink to a regular file with the target's bytes
    # under an ordinary `type: file`, so accepting that response would write
    # unrelated content and call it the exact pre-change state.
    directory = str(pathlib.PurePosixPath(source).parent)
    directory = "" if directory == "." else directory
    if directory not in state.listings:
        state.listings[directory], state.listed_totals[directory] = reduce_listing(
            provider_json(
                listing_endpoint(state.repository, directory, state.merge_base),
                state.deadline,
            ),
            state.needed_names.get(directory, set()),
        )
    listing = state.listings[directory]
    name = pathlib.PurePosixPath(source).name
    named = _records_named(listing, name)
    if named > 1:
        # A listing naming a path twice contradicts itself. Taking the first record let
        # record order choose the type and blob id, and bytes matching it were written
        # as exact provenance. (Codex)
        state.unavailable.append(
            f"provider-error {quote_path(source)}: the directory listing holds "
            f"{named} records for it"
        )
        return None
    record = listing_entry(listing, name)
    if record:
        return record
    if listing is not None and not isinstance(listing, list):
        # `None` here is the transport sentinel and nothing else; what
        # the base holds is settled by the comparison. Syntactically valid
        # JSON of the wrong shape means the collection never got to look,
        # and recording it as absent attributed a provider failure to the
        # repository while skipping bytes that were there to be fetched.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: directory listing was not an array"
        )
    elif (
        isinstance(listing, list)
        and state.listed_totals.get(directory, 0) >= LISTING_CAP
    ):
        # The listing reached the provider's maximum, so the name may lie
        # beyond it -- or the listing may be complete and contradict the
        # comparison. Neither "absent" nor "truncated" is established; the
        # label says only what was observed.
        state.unavailable.append(f"listing-at-cap {quote_path(source)}")
    else:
        # Not absence either. Every entry that reaches here is non-added --
        # `added` returns above -- so the comparison has already placed
        # this source at this same merge base. A directory 404, or a
        # listing that does not hold the name, contradicts the comparison
        # exactly as a post-listing contents 404 contradicts the listing.
        # `absent-at-merge-base` is therefore unreachable as a true
        # statement here, and two tests asserted it anyway.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: "
            "the comparison places it at the merge base "
            "but the listing does not"
        )
    return None


def _content_gap(
    state: _Collection, source: str, record: dict[str, Any], content: bytes
) -> str | None:
    """Return the manifest line refusing ``content`` for ``source``, or None."""
    # `validate=True` only says the base64 was well formed. A truncated or
    # corrupted payload that still decodes cleanly would be written as the exact
    # pre-change file with no gap recorded -- and "exact" is the whole claim
    # base/ makes. The listing already carries Git's blob id, so the bytes are
    # checked against it rather than assumed.
    listed_blob = _text(record.get("sha"))
    if not SHA_PATTERN.match(listed_blob):
        # Without the listing's blob id there is nothing to check the bytes
        # against, and base/ promises exactness. Writing them anyway would make
        # that promise on evidence this collection does not have. A malformed
        # id is no more usable than a missing one, so both fail here rather
        # than only the empty case.
        return f"blob-unverifiable {quote_path(source)}"
    if blob_id(content) != listed_blob:
        return f"blob-mismatch {quote_path(source)}"
    if len(content) > state.remaining:
        # Backstop for a listing that reported no size.
        return f"over-budget {quote_path(source)}"
    return None


def _fetch_and_write(
    state: _Collection, name: str, source: str, record: dict[str, Any]
) -> None:
    """Fetch the listed file's pre-change bytes, verify them, and write them."""
    declared = _text(record.get("type"))
    if declared != "file":
        # Only a recognised non-file type is a fact about the repository. A
        # missing, emptied (an overlong value normalises to "") or unknown type
        # says only that the listing was malformed.
        if declared in ("dir", "symlink", "submodule"):
            state.unavailable.append(f"not-a-plain-file {quote_path(source)}")
        else:
            state.unavailable.append(
                f"provider-error {quote_path(source)}: its directory listing "
                "declared no recognised type"
            )
        return
    # The budget is checked against the size the listing already reports, so a file
    # the budget will reject costs no request at all. Fetching first made a large
    # Pull Request full of binaries issue an avoidable request per file, and a
    # rate-limit response there would fail the step -- leaving that Pull Request
    # without a review, which is the failure this Decision exists to remove.
    declared_size = record.get("size")
    if isinstance(declared_size, int) and declared_size > state.remaining:
        state.unavailable.append(f"over-budget {quote_path(source)}")
        return
    payload = provider_json(
        base_endpoint(state.repository, source, state.merge_base), state.deadline
    )
    if payload is None:
        # Not absence. The listing for this directory, at this same merge base,
        # already said the file is there, and the merge base is an immutable
        # revision -- so a 404 on the contents request for the same path at the
        # same revision is the provider contradicting itself. Recording it as
        # absent turned that into repository-state provenance the reviewer has
        # no way to question, while quietly skipping bytes that exist.
        state.unavailable.append(
            f"provider-error {quote_path(source)}: "
            "listed at the merge base but its contents were not found"
        )
        return
    content, reason = decoded_file(payload)
    if content is None:
        # The reason travels from where it is known. `not-a-plain-file` is a
        # statement about the repository, and is recorded only where the
        # response actually supports one.
        if reason.startswith("provider-error"):
            detail = reason.split(":", 1)[1].strip()
            state.unavailable.append(f"provider-error {quote_path(source)}: {detail}")
        else:
            state.unavailable.append(f"{reason} {quote_path(source)}")
        return
    gap = _content_gap(state, source, record, content)
    if gap is not None:
        state.unavailable.append(gap)
        return
    destination = state.context / "base" / safe_relative_path(name)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_exact(destination, content, staging=state.context / _STAGING)
    except OSError as error:
        # Losing one file's pre-change bytes is a gap the manifest records; letting
        # the error escape would fail the whole step and leave the Pull Request with
        # no review at all, which is the failure this collection exists to prevent.
        state.unavailable.append(_write_failure(error, name))
        return
    state.remaining -= len(content)
    state.written += 1


def _write_failure(error: OSError, name: str) -> str:
    """Return the manifest line for a write into ``base/`` that raised ``error``."""
    if error.errno in _COLLISION_ERRNOS:
        # Replacing a file with a directory is an ordinary change: a Pull Request can
        # remove `cfg` and rename something to `cfg/x.py`. Every entry is written under
        # its post-change name, so one of the two writes meets the other as the wrong
        # type.
        return f"path-collision {quote_path(name)}"
    # Anything else -- a full disk, an I/O error -- says nothing about the repository.
    # Recorded as a collision, it gave every remaining file the same false explanation,
    # so it is named as the write failing, with its cause.
    cause = errno.errorcode.get(error.errno or 0, type(error).__name__)
    return f"write-failed {quote_path(name)}: {cause}"


def _failure_line(failure: Exception, name: str) -> str:
    """Return the manifest line for a per-file failure, most specific cause first."""
    if isinstance(failure, DeadlineReached):
        return f"deadline-reached {quote_path(name)}"
    if isinstance(failure, UnsafeRedirect):
        return f"unsafe-redirect {quote_path(name)}: {failure}"
    if isinstance(failure, ProviderError):
        # An accurate cause: the provider could not answer for this path, which is
        # not the same as the path being one this collection will not write.
        return f"provider-error {quote_path(name)}: {failure}"
    # Every refusal raised in here says "this path cannot be handled": a name
    # this collection will not write, or a provider record that contradicts its
    # own contract. Raising it out of the step meant one odd filename anywhere
    # in the Pull Request cost the whole review -- the failure this collection
    # exists to prevent. It costs that one file instead. A backslash is the
    # reachable case: legal in a Git pathname and on the runner, and still not
    # something this collection will spell on disk.
    return f"unsupported-path {quote_path(name)}: {failure}"


def _visit(state: _Collection, entry: dict[str, Any]) -> None:
    """Collect one changed file's pre-change bytes, or name why they are absent."""
    name = str(entry["filename"])
    hunkless = entry.get("patch") is None
    classified_here = False
    if entry.get("status") == "added":
        # Settled by the comparison alone, so before the deadline: an added file has
        # no base side and costs no request. Checked after it, an addition reached
        # once the budget was spent -- a hunkless one sorts last -- was recorded as a
        # collection failure and lost its classification. (Codex)
        state.unavailable.append(f"added-by-candidate {quote_path(name)}")
        if hunkless:
            state.classified.append(f"added-without-hunks {quote_path(name)}")
        return
    if time.monotonic() >= state.deadline:
        if hunkless:
            # A no-hunk change gets a verdict whatever else happens: the reviewer
            # is sent to base.manifest for it, and these entries are ordered last,
            # so on a large Pull Request they are the first the deadline reaches.
            state.classified.append(f"unclassified-no-base-record {quote_path(name)}")
        # Up to 300 files, each with a listing and a contents request, each retried:
        # the worst case ran past the job's own timeout, and a job the runner kills
        # produces no review at all. What was not reached is named instead.
        state.unavailable.append(f"deadline-reached {quote_path(name)}")
        return
    try:
        source = base_path_of(entry)
        # Validated as given, before any lookup: `a//x` normalised to the real entry
        # `a/x`, which classified the path from that record before the fetch refused
        # it -- `metadata-only` beside `unsupported-path`. (Codex)
        safe_relative_path(source)
        record = _base_record(state, source)
        if record is None:
            if hunkless:
                state.classified.append(
                    f"unclassified-no-base-record {quote_path(name)}"
                )
            return
        if hunkless:
            # Classified here, before the contents fetch and regardless of whether
            # the bytes are ultimately written, so a budget rejection or a decode
            # failure cannot leave the reviewer without a verdict on whether content
            # changed.
            state.classified.append(hunkless_label(entry, record, name))
            classified_here = True
        _fetch_and_write(state, name, source, record)
    except (ProviderError, ValueError) as failure:
        state.unavailable.append(_failure_line(failure, name))
        if hunkless and not classified_here:
            state.classified.append(f"unclassified-no-base-record {quote_path(name)}")


def _manifest_lines(
    state: _Collection,
    comparison: dict[str, Any],
    delivered_count: int,
    notices: list[str],
) -> list[str]:
    """Return the lines of ``base.manifest`` for a finished collection."""
    mapped = [
        entry
        for entry in comparison.get("files") or []
        if entry.get("status") in ("renamed", "copied")
        and _text(entry.get("previous_filename"))
    ]
    renames = [
        f"{entry['status']} {quote_path(_text(entry.get('previous_filename')))} -> "
        f"{quote_path(str(entry['filename']))}"
        for entry in mapped
    ]
    # Counted apart. The list holds both, and reporting its length as `Renamed:` told
    # the reviewer a file had moved when a file had been duplicated and the original
    # is still there -- in the summary line the reviewer is told to trust, while the
    # mapping underneath said `copied`.
    copied = sum(1 for entry in mapped if entry.get("status") == "copied")
    merge_base = state.merge_base
    return [
        # Not of every changed file. An added path has none, and an unavailable,
        # oversized, non-plain or unverifiable one is named below instead -- the same
        # universal that was corrected in the module docstring and the Decision, left
        # standing in the artefact the reviewer is actually handed.
        "Exact pre-change bytes of the changed files this collection could fetch,",
        f"taken at the merge base ({merge_base if SHA_PATTERN.match(merge_base) else 'unknown'}).",
        "Every path the provider listed and this collection could not fetch is named",
        "below with its reason. A renamed or",
        "copied file is fetched under its previous path and written under its new one,",
        "so the mapping is listed here: the bytes under a new name came from the old.",
        "A record too long for one readable line continues on lines that begin with",
        "'>', here and in diff.stat, no-patch.txt and commits.log.",
        f"Written: {state.written}. Unavailable: {len(state.unavailable)}. "
        f"Renamed: {len(renames) - copied}. Copied: {copied}.",
        # The counts and the inventory above cover the paths the provider listed, and
        # a capped list omits the rest entirely -- they are never sent, so they are
        # never fetched, never counted and never named. The promise of a complete
        # per-path inventory was therefore false for exactly the large Pull Requests
        # this collection exists to serve. diff.stat carries a cap notice, but the
        # prompt sends the reviewer here for provenance, so the qualification has to
        # be here too.
        *(
            [
                f"The changed-file list reached the provider's maximum of {FILE_CAP}"
                " and is not",
                "paginated, so this may not be the whole change: any path beyond the",
                "maximum would be absent from this manifest and not examined, and",
                "nothing here says whether one exists.",
            ]
            if delivered_count >= FILE_CAP
            else []
        ),
        "",
        "A change the comparison gave no hunks for is classified below by blob",
        "identity, because its status cannot distinguish the cases: identical blobs",
        "mean a metadata-only change, while differing blobs mean content changed that",
        "no artefact here can show. metadata-only says only that the content is the",
        "same; *which* metadata changed -- 100644 -> 100755, or another transition --",
        "is carried by the unified diff's mode lines and by nothing else here. An",
        "entry whose blob ids are missing or malformed is listed as",
        "unclassified-without-blob-identity: no classification was established for",
        "it, and equal-but-malformed ids are not read as identical content. If",
        "patches-source is present the diff was assembled per file and those lines are",
        "absent, so a metadata-only entry is then not examined either.",
        "",
        *state.classified,
        *renames,
        *state.unavailable,
        *notices,
    ]


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

    False when the comparison named no usable file: unparseable, not an object, without
    a file list, or listing only entries that could not be used. The collection still
    finishes, with a manifest saying why. An empty listing is a listing.
    """
    delivered, files, notices, refused = _read_comparison(context)
    listing = delivered.get("files") if isinstance(delivered, dict) else None
    # Entries listed but none usable leave the fallback diff as empty as an unread
    # comparison does, so they say no more that nothing changed. (gitar)
    listed = isinstance(listing, list) and (not listing or bool(files))
    # Everything downstream reads a comparison that has already been reduced to the
    # entries it can act on, so no later step has to guard the shape again.
    comparison: dict[str, Any] = {
        **(delivered if isinstance(delivered, dict) else {}),
        "files": files,
    }
    sent = delivered.get("files") if isinstance(delivered, dict) else None
    # How many entries the provider actually sent, which both the diff.stat cap notice
    # and the manifest's qualification depend on and a reduced list cannot report.
    delivered_count = len(sent) if isinstance(sent, list) else len(files)
    write_commits(context)
    write_summaries(context, comparison, delivered_count)
    # A three-dot comparison is computed from the merge base, so the pre-change content
    # must come from there too. The base branch tip would be a different revision
    # whenever the target branch has advanced since the candidate diverged.
    base_commit = comparison.get("merge_base_commit")
    merge_base = _text(
        (base_commit if isinstance(base_commit, dict) else {}).get("sha")
    )
    # Per-file patches, so a provider that refuses the whole diff still leaves the
    # changed content reachable. Without this, a refusal produced a context with paths
    # and pre-change bytes but nothing about what the candidate actually changed.
    write_streamed(
        context, "assembled.diff", lambda handle: write_assembled(handle, comparison)
    )
    (context / "base").mkdir(exist_ok=True)
    state = _Collection(context, repository, merge_base, budget)
    state.unavailable.extend(refused)
    # Files with hunks are fetched first so that a large binary cannot consume the
    # budget ahead of a textual change. Entries without hunks are not skipped: a mode
    # change or a pure rename of a text file has pre-change bytes, and those bytes are
    # exactly what the reviewer is told to read from base/. Skipping them left the
    # reviewer with no content and no gap recorded for a change it was told to review.
    ordered = sorted(
        comparison.get("files") or [], key=lambda item: item.get("patch") is None
    )
    if not SHA_PATTERN.match(merge_base):
        # Checked once, before any request. `base_endpoint` refuses a non-exact base
        # with a ValueError, and the per-file handler catches ValueError as an unusable
        # *pathname* -- so a comparison that omitted `merge_base_commit.sha` produced a
        # manifest blaming every ordinary filename in the change for a gap that was the
        # provider's. There is also nothing to ask for: without the revision there is no
        # endpoint, so no request is made rather than 300 refusals.
        notices.append(
            "provider-error comparison.json: the comparison carried no exact merge "
            f"base revision ({merge_base or 'absent'!r}), so no pre-change bytes "
            "could be fetched for any path"
        )
        _without_merge_base(state, ordered)
        ordered = []
    state.needed_names = _needed_names(ordered)
    state.deadline = time.monotonic() + DEADLINE_SECONDS
    for entry in ordered:
        _visit(state, entry)
    lines = _manifest_lines(state, comparison, delivered_count, notices)
    write_artefact(
        context, _MANIFEST, "".join(f"{line}\n" for line in lines), encoding="utf-8"
    )
    # Every staged write was renamed or removed, so the staging area is empty; it is
    # not part of the context the reviewer reads. A hard stop that leaves it behind is
    # the workflow's to sweep.
    try:
        (context / _STAGING).rmdir()
    except OSError:
        pass
    return state.written, state.unavailable, listed


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
