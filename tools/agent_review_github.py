"""The GitHub provider adapter for the agent review pipeline (Decision 0100).

Translates between GitHub's native vocabulary and the neutral core's: the issue
comments, issues and Pull Requests a request is re-read from, the trusted
`author_association` values, a Pull Request's comparison, commits and unified diff,
the issue comments a review is delivered as, the identity that authors them, and the
credential shapes GitHub issues.
"""

from __future__ import annotations

import base64
import json
import pathlib
import re
import time
import urllib.parse
from collections.abc import Callable, Mapping
from typing import Any

from tools import github_rest
from tools.agent_review_admission import Refused, Request, Revisions
from tools.agent_review_base import (
    BaseRecord,
    ChangedFile,
    Comparison,
    Contents,
    Listing,
    SourceFailure,
    is_object_id,
    quote_path,
    safe_relative_path,
)
from tools.agent_review_context import Commit, DiffRefused, Unavailable, Vocabulary
from tools.agent_review_delivery import (
    DeliveryRefused,
    DeliveryUncertain,
    SecretPattern,
)
from tools.agent_review_model import Provider, Ref, ReviewSubject

API = "https://api.github.com"
# What posts a review here, in the reader's words: a GitHub Actions workflow.
POSTED_BY = "this repository's workflow"
# The identity a GITHUB_TOKEN comment is authored by.
COMMENT_AUTHOR = "github-actions[bot]"
_LISTING_PAGES = 10
_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
# Reads are retried, as idempotent reads: one transient failure reading back must not
# end a delivery (CodeAnt on #353). A create is never retried by the client, whatever
# the policy: post-once owns that decision.
_POLICY = github_rest.Policy(attempts=3, max_response_bytes=4 << 20)
# GitHub's token shapes, after the pinned action's own sanitiser
# (`src/github/utils/sanitizer.ts`, MIT), plus the forms this repository's jobs handle:
# an App installation token (`ghs_`) and a token carried in a remote URL. No word
# boundaries and no upper bound: two tokens written back to back are one word (#353).
SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"), "GitHub token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "GitHub token"),
    (re.compile(r"x-access-token:[^@\s]+@"), "GitHub token"),
)


class IssueCommentSink:
    """Deliver comments to one issue or Pull Request through its issue-comments API.

    ``find`` reads every page of comments updated since ``since`` -- the start of the
    run, when the caller knows it, so a rerun still finds an earlier attempt's comment
    (Codex on #353); otherwise shortly before this sink was made -- following the
    provider's own `Link` pages within a bound, and counts only those authored by the
    job's own identity. A thread flooded past the bound cannot be read
    back whole, which is a reason to stop rather than to post again (CodeAnt on #353).
    Every exchange is the shared client's: bounded as a whole and in size (CodeRabbit on
    #353), with a rate-limited create reported as uncertain, its wait honoured (Codex on
    #353).
    """

    def __init__(
        self,
        comments_url: str,
        client: github_rest.GitHubRestClient | None = None,
        *,
        since: str | None = None,
    ) -> None:
        try:
            self.client = client or github_rest.GitHubRestClient.from_environment(
                user_agent="gnostoa-post-report", policy=_POLICY
            )
        except github_rest.GitHubError as error:
            raise DeliveryRefused(
                "no usable token is available to deliver the comment"
            ) from error
        self.comments_url = comments_url
        if since is None:
            since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 300))
        elif not _INSTANT.match(since):
            # It reaches the listing URL, so only an exact instant is accepted.
            raise DeliveryRefused("the read-back window is not an exact UTC instant")
        self.since = since

    def create(self, body: str) -> str:
        """Create a comment, mapping GitHub's failures onto the core's two kinds."""
        try:
            answer = self.client.post(self.comments_url, {"body": body})
        except github_rest.GitHubWriteError as error:
            # A refusal is the answer; an outage, a rate limit or a lost answer may not be.
            if error.status is not None and error.status < 500 and error.status != 429:
                raise DeliveryRefused(
                    f"HTTP {error.status} posting to {self.comments_url}"
                ) from error
            raise DeliveryUncertain(
                f"could not post to {self.comments_url}: {error}",
                retry_after=error.retry_after,
                in_flight=error.in_flight,
            ) from error
        except github_rest.GitHubError as error:
            # Refused before anything was sent, or a redirect the client would not
            # follow: either way the comment was not created.
            raise DeliveryRefused(
                f"refused posting to {self.comments_url}: {error}"
            ) from error
        location = answer.get("html_url") if isinstance(answer, dict) else None
        if not isinstance(location, str) or not location:
            # Accepted, but with no comment's location: whether it was made is not
            # established, so delivery reads back for it (CodeAnt on #353).
            raise DeliveryUncertain(
                f"posting to {self.comments_url} was answered without the comment's "
                "location"
            )
        return location

    def find(self, marker: str) -> str | None:
        """Return this job's comment that starts with ``marker``, if GitHub has it."""
        url: str | None = f"{self.comments_url}?since={self.since}&per_page=100"
        pages = 0
        try:
            # Narrowed by an explicit check, not an assert: an assert is stripped under
            # `python -O`, and a bound is not something to compile away (Codacy, B101).
            while url is not None and pages < _LISTING_PAGES:
                pages += 1
                listing, headers = self.client.read_page(url)
                if not isinstance(listing, list):
                    raise DeliveryUncertain(
                        "the provider's comment listing was not a list"
                    )
                for comment in listing:
                    if not isinstance(comment, dict):
                        continue
                    author = comment.get("user")
                    if (
                        isinstance(author, dict)
                        and author.get("login") == COMMENT_AUTHOR
                        and str(comment.get("body", "")).startswith(marker)
                    ):
                        location = comment.get("html_url")
                        if not isinstance(location, str) or not location:
                            # This delivery's comment, listed without its location:
                            # not a confirmed delivery (CodeAnt on #353).
                            raise DeliveryUncertain(
                                "the provider listed this delivery's comment without "
                                "its location"
                            )
                        return location
                url = github_rest.next_url(headers, self.client.api_root)
            if url is None:
                return None
        except github_rest.GitHubError as error:
            raise DeliveryUncertain(str(error)) from error
        raise DeliveryUncertain(
            f"more than {_LISTING_PAGES} pages of comments since {self.since}, too many "
            "to read back"
        )


# ---------------------------------------------------------------------------------
# The request source: re-reading a relayed request from GitHub

PROVIDER = Provider("github", "agent_review_github")
# The `author_association` values this project trusts.
TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
ITEM_KIND = "issue"
CHANGE_KIND = "pull_request"
_REPOSITORY = re.compile(r"\A[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")


def is_repository(name: str) -> bool:
    """Return whether ``name`` is a repository in GitHub's owner/name form."""
    return bool(_REPOSITORY.match(name))


def _mapping(value: Any, label: str) -> dict[str, Any]:
    """Return ``value`` when it is an object, or refuse."""
    if not isinstance(value, dict):
        raise Refused(f"{label} was not an object")
    return value


def _identifier(value: Any, label: str) -> int:
    """Return a positive integer identifier, refusing anything else.

    The relay supplies these, so they are validated before they reach a URL: a string,
    a float, a boolean, a negative number or a crafted path fragment is refused.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise Refused(f"{label} is not a positive integer")
    return value


def _trailing_number(url: Any, label: str) -> int:
    """Return the item number a provider URL ends with, from the provider's answer."""
    if not isinstance(url, str):
        raise Refused(f"{label} is missing")
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    if not tail.isdigit() or int(tail) <= 0:
        raise Refused(f"{label} does not end in an item number")
    return int(tail)


def _login(value: Any) -> str:
    """Return the author login of a provider object, or "" when it carries none."""
    user = value.get("user") if isinstance(value, dict) else None
    login = user.get("login") if isinstance(user, dict) else None
    return login if isinstance(login, str) else ""


def _change(number: int, item: Mapping[str, Any]) -> Ref | None:
    """Return the item's Pull Request, which on GitHub shares the issue's number."""
    if isinstance(item.get("pull_request"), dict):
        return Ref(CHANGE_KIND, str(number))
    return None


class IssueRequests:
    """Re-read a relayed request from GitHub's issues and Pull Requests.

    ``read`` returns the provider's JSON for a path under the API root, or raises
    ``Refused``; the entrypoint supplies it, bounded and retried by the shared client.
    The relay's pointer contributes ids only, each validated before it reaches a URL;
    every fact in the returned request is GitHub's answer.
    """

    provider = PROVIDER

    def __init__(self, repository: str, read: Callable[[str], Any]) -> None:
        if not _REPOSITORY.match(repository):
            raise Refused("the repository name is not in owner/name form")
        self.root = f"repos/{repository}"
        self.read = read

    def read_request(self, event: str, pointer: Mapping[str, Any]) -> Request:
        """Re-read the object ``pointer`` names for ``event``."""
        if event == "issue_comment":
            return self._issue_comment(pointer)
        if event == "issues":
            return self._issue(pointer)
        raise Refused(f"event {event!r} is not an admitted trigger")

    def _issue_comment(self, pointer: Mapping[str, Any]) -> Request:
        """Re-read an issue comment and the item it belongs to."""
        comment_id = _identifier(pointer.get("comment_id"), "comment_id")
        comment = _mapping(
            self.read(f"{self.root}/issues/comments/{comment_id}"), "issue comment"
        )
        # The comment's own `issue_url` decides which item it belongs to; the relay's
        # claim about that is not used. A comment on a plain issue has no Pull Request.
        number = _trailing_number(comment.get("issue_url"), "issue comment issue_url")
        item = _mapping(self.read(f"{self.root}/issues/{number}"), "issue")
        return Request(
            author=_login(comment),
            association=comment.get("author_association"),
            mention_text=str(comment.get("body") or ""),
            item=Ref(ITEM_KIND, str(number)),
            change_request=_change(number, item),
            occurred_at=str(comment.get("created_at") or ""),
            request_text=comment.get("body"),
            title=item.get("title"),
            body=item.get("body"),
            item_association=item.get("author_association"),
        )

    def _issue(self, pointer: Mapping[str, Any]) -> Request:
        """Re-read an opened issue, which is itself the request."""
        number = _identifier(pointer.get("issue_number"), "issue_number")
        issue = _mapping(self.read(f"{self.root}/issues/{number}"), "issue")
        title = str(issue.get("title") or "")
        body = str(issue.get("body") or "")
        return Request(
            author=_login(issue),
            association=issue.get("author_association"),
            # The issues trigger admits the mention in the title as well.
            mention_text=f"{title}\n{body}",
            item=Ref(ITEM_KIND, str(number)),
            change_request=_change(number, issue),
            occurred_at=str(issue.get("created_at") or ""),
            # The issue *is* the request, and its mention may be in the title alone,
            # so the request artefact carries both. Forwarding only the body would
            # leave the file the reviewer is told to read first without the ask.
            request_text=f"{title}\n{body}",
            title=issue.get("title"),
            body=issue.get("body"),
            item_association=issue.get("author_association"),
        )

    def revisions(self, change_request: Ref) -> Revisions:
        """Read a Pull Request's live head, base and head repository."""
        number = _identifier(int(change_request.id), "pull request number")
        pull = _mapping(self.read(f"{self.root}/pulls/{number}"), "pull request")
        head = _mapping(pull.get("head"), "pull.head")
        head_repo = _mapping(head.get("repo"), "pull.head.repo").get("full_name")
        base = _mapping(pull.get("base"), "pull.base")
        return Revisions(
            head_repository=head_repo,
            head_commit=head.get("sha"),
            base_commit=base.get("sha"),
        )


def step_outputs(subject: ReviewSubject) -> dict[str, str]:
    """Return an admitted subject as the workflow's step outputs."""
    change = subject.change_request
    return {
        "item_number": subject.item.id,
        "pull_number": "" if change is None else change.id,
        "head_sha": subject.head_commit,
        "base_sha": subject.base_commit,
    }


# ---------------------------------------------------------------------------------
# The change source: a Pull Request's comparison, commits and unified diff

# What the reader calls a change request here, and what it reads when there is none.
VOCABULARY = Vocabulary(change_request="Pull Request")
NO_CHANGE_REQUEST = "No Pull Request: this request concerns the issue itself.\n"
DIFF_MEDIA_TYPE = "application/vnd.github.v3.diff"
# The most pages of a comparison's commits read, 100 commits each. Past it the list is
# refused rather than cut: a cut list would pass for the provider's own cap (Codex on
# #353), and the core states the refusal instead.
COMMIT_PAGE_BOUND = 100
_CONTEXT_POLICY = github_rest.Policy(
    attempts=3, retry_sleep_seconds=5, max_response_bytes=8 << 20
)
# The unified diff of a large change is large and slow to render, so it has a longer
# whole-exchange bound and a larger size bound. Past either the step fails: only the
# provider's refusal reaches the lossy per-file fallback.
_DIFF_POLICY = github_rest.Policy(
    attempts=3, retry_sleep_seconds=5, timeout_seconds=120, max_response_bytes=256 << 20
)
_SHA = re.compile(r"\A[0-9a-f]{40}\Z")


class CompareSource:
    """Read a Pull Request's comparison of its exact base and head.

    The revisions are admission's, never a relay's or the candidate's, and each is
    validated before it reaches a URL. Every read is the shared client's: bounded,
    retried as an idempotent read, rate limits waited out.
    """

    def __init__(
        self,
        repository: str,
        base: str,
        head: str,
        *,
        client: github_rest.GitHubRestClient | None = None,
        diff_client: github_rest.GitHubRestClient | None = None,
    ) -> None:
        if not _REPOSITORY.match(repository):
            raise Unavailable("the repository name is not in owner/name form")
        if not (_SHA.match(base) and _SHA.match(head)):
            raise Unavailable("the comparison's revisions are not exact SHAs")
        try:
            self.client = client or github_rest.GitHubRestClient.from_environment(
                user_agent="gnostoa-review-context", policy=_CONTEXT_POLICY
            )
            self.diff_client = (
                diff_client
                or github_rest.GitHubRestClient.from_environment(
                    user_agent="gnostoa-review-context", policy=_DIFF_POLICY
                )
            )
        except github_rest.GitHubError as error:
            raise Unavailable(
                "no usable token is available to read the change"
            ) from error
        self.url = self.client.url(f"repos/{repository}/compare/{base}...{head}")

    def comparison(self) -> bytes:
        """Return the comparison document."""
        try:
            return self.client.read_bytes(self.url, accept=github_rest.JSON_MEDIA_TYPE)
        except github_rest.GitHubError as error:
            raise Unavailable(f"the comparison could not be read: {error}") from error

    def commits(self) -> list[Commit]:
        """Return the comparison's commits, following its pages within a bound."""
        url: str | None = f"{self.url}?per_page=100"
        listed: list[Commit] = []
        pages = 0
        try:
            while url is not None and pages < COMMIT_PAGE_BOUND:
                pages += 1
                page, headers = self.client.read_page(url)
                listed.extend(_commits_of(page))
                url = github_rest.next_url(headers, self.client.api_root)
        except github_rest.GitHubError as error:
            raise Unavailable("the commit list could not be read") from error
        if url is not None:
            raise Unavailable(
                f"the comparison has more than {COMMIT_PAGE_BOUND} pages of commits"
            )
        return listed

    def unified_diff(self) -> bytes:
        """Return the comparison's unified diff, or raise ``DiffRefused`` on a 406."""
        try:
            return self.diff_client.read_bytes(self.url, accept=DIFF_MEDIA_TYPE)
        except github_rest.GitHubError as error:
            # The provider's refusal to render a diff too large to generate, and that
            # status alone: an authentication error, a permission error or an outage
            # presented as a refusal would publish an incomplete review as complete.
            if error.status == 406:
                raise DiffRefused(str(error)) from error
            raise Unavailable(f"the unified diff could not be read: {error}") from error


def _commits_of(page: Any) -> list[Commit]:
    """Return one comparison page's commits: a short id and a first line each."""
    if not isinstance(page, dict):
        raise Unavailable("a page of the comparison was not an object")
    # Absent or null is a page without commits; any other value that is not a list is a
    # malformed page, not an empty one (CodeAnt on #353).
    commits = page.get("commits")
    if commits is None:
        commits = []
    if not isinstance(commits, list):
        raise Unavailable("the comparison's commits were not a list")
    listed = []
    for entry in commits:
        sha = entry.get("sha") if isinstance(entry, dict) else None
        commit = entry.get("commit") if isinstance(entry, dict) else None
        message = commit.get("message") if isinstance(commit, dict) else None
        if not is_object_id(sha) or not isinstance(message, str):
            # The id reaches a line-oriented log, so it is an exact object id or the
            # commit is malformed (CodeAnt on #353).
            raise Unavailable("a commit of the comparison is malformed")
        # Split on "\n" alone, as the provider's own tools do; every other line
        # separator is neutralised where the log is rendered.
        listed.append(Commit(sha[:9], message.split("\n", 1)[0]))
    return listed


# ---------------------------------------------------------------------------------
# The base source: a comparison's files and the base revision's contents

# The contents API returns at most this many entries for a directory and does not
# paginate it. A changed file in a larger directory is simply missing from the listing,
# which must not be reported as "the base did not hold this".
LISTING_CAP = 1000
# The comparison's changed-file list holds at most this many entries and is not
# paginated.
FILE_CAP = 300
# The only fields a listing record is read for. The contents API sends `_links`,
# `download_url`, `git_url`, `html_url` and `url` alongside them, and keeping the whole
# record retained all of that for every changed file.
_LISTING_FIELDS = ("name", "type", "size", "sha")
# Selecting those fields is not enough: their *values* are the provider's, and a valid
# array whose matching record carries a megabyte-long `type` or `sha` reopens the same
# exhaustion. Each is normalised to the representation the code downstream uses.
_TYPE_LIMIT = 32
# A declared size above any response this collection reads still says "larger than
# anything it will write" without carrying the digits to say it.
_SIZE_CEILING = 8 * 1024 * 1024 + 1
# Each side must begin with an alphanumeric. A leading dash is precisely the shape an
# earlier version of this check accepted, and the reason it is spelled out here.
_CONTENTS_REPOSITORY = re.compile(
    r"\A[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z"
)
# Pins scheme, host and shape together, so the request cannot be pointed at another
# origin whatever reaches the fetch.
PROVIDER_URL = re.compile(
    r"\Ahttps://api\.github\.com/repos/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/contents/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*\?ref=[0-9a-f]{40}\Z"
)


def base_endpoint(repository: str, path: str, base_sha: str, root: str = API) -> str:
    """Build the contents URL for ``path`` at ``base_sha``, under ``root``."""
    if not _CONTENTS_REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not is_object_id(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = urllib.parse.quote(str(safe_relative_path(path)), safe="/")
    return f"{root}/repos/{repository}/contents/{encoded}?ref={base_sha}"


def listing_endpoint(
    repository: str, directory: str, base_sha: str, root: str = API
) -> str:
    """Build the contents URL for a directory listing at ``base_sha``, under ``root``."""
    if not _CONTENTS_REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not is_object_id(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = (
        urllib.parse.quote(str(safe_relative_path(directory)), safe="/")
        if directory
        else ""
    )
    return f"{root}/repos/{repository}/contents/{encoded}?ref={base_sha}"


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
    number into something the object-id check accepts, so malformed metadata could make two
    blob ids equal and call a change `metadata-only`. An empty string is what every
    reader here already treats as absent.
    """
    return value if isinstance(value, str) else ""


def reduce_listing(listing: Any, needed: set[str]) -> tuple[Any, int]:
    """Return only the records ``needed`` from ``listing``, and its original length.

    The cache used to hold every parsed directory response until the collection
    finished. A response may approach the collector's response bound, so a change touching one
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
        "size": min(size, _SIZE_CEILING)
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0
        else None,
        # Checked as an object id before it is compared with real bytes, so a value that
        # cannot match is worth nothing and is not kept.
        "sha": sha if is_object_id(sha) else "",
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


def changed_file(entry: dict[str, Any]) -> ChangedFile:
    """Translate one admitted comparison entry into the core's vocabulary."""
    previous = _text(entry.get("previous_filename"))
    additions = entry.get("additions")
    deletions = entry.get("deletions")
    patch = entry.get("patch")
    blob = entry.get("sha")
    return ChangedFile(
        path=str(entry["filename"]),
        status=str(entry["status"]),
        previous_path=previous or None,
        patch=patch if isinstance(patch, str) else None,
        additions=additions if isinstance(additions, int) else None,
        deletions=deletions if isinstance(deletions, int) else None,
        blob=blob if isinstance(blob, str) else None,
    )


def base_record(record: dict[str, Any]) -> BaseRecord:
    """Translate one bounded listing record into the core's vocabulary."""
    size = record.get("size")
    return BaseRecord(
        name=_text(record.get("name")),
        kind=_text(record.get("type")),
        size=size if isinstance(size, int) and not isinstance(size, bool) else None,
        blob=_text(record.get("sha")),
    )


def read_comparison(path: pathlib.Path) -> Comparison:
    """Read a comparison document into the core's vocabulary, naming what is unusable."""
    try:
        delivered: Any = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        # The outermost escape, and the last one. Guarding the comparison's *shape* left
        # its *parse* unguarded, so malformed JSON, a body that is not UTF-8, or a file
        # that cannot be read at all raised before any manifest existed. Naming the base
        # class is deliberate: every way this can fail means the comparison is unusable,
        # and enumerations here have each missed a member. The shape check is skipped
        # rather than run against nothing, which would report a second, derived error.
        return Comparison(
            files=[],
            delivered=0,
            merge_base="",
            notices=[
                f"provider-error comparison.json: it could not be read "
                f"({type(error).__name__}), so no changed file could be named"
            ],
            refused=[],
            listed=False,
        )
    refused: list[str] = []
    files, notices = usable_files(delivered, refused)
    sent = delivered.get("files") if isinstance(delivered, dict) else None
    # Entries listed but none usable leave the fallback diff as empty as an unread
    # comparison does, so they say no more that nothing changed.
    listed = isinstance(sent, list) and (not sent or bool(files))
    base_commit = (
        delivered.get("merge_base_commit") if isinstance(delivered, dict) else None
    )
    merge_base = _text(
        (base_commit if isinstance(base_commit, dict) else {}).get("sha")
    )
    return Comparison(
        files=[changed_file(entry) for entry in files],
        delivered=len(sent) if isinstance(sent, list) else len(files),
        merge_base=merge_base,
        notices=notices,
        refused=refused,
        listed=listed,
    )


class ContentsSource:
    """The base revision at ``merge_base``, read through GitHub's contents API.

    ``read`` returns the provider's JSON for a contents URL, or None for not-found; the
    entrypoint supplies it, bounded and retried by the shared client. Every failure is
    translated into the core's ``SourceFailure``, by kind.
    """

    listing_cap = LISTING_CAP

    def __init__(
        self,
        repository: str,
        merge_base: str,
        read: Callable[[str, float | None], Any],
        *,
        api_root: str = API,
    ) -> None:
        self.repository = repository
        self.merge_base = merge_base
        self.read = read
        self.api_root = api_root

    def _answer(self, url: str, deadline: float) -> Any:
        """Read ``url``, translating the client's failures into the core's."""
        try:
            return self.read(url, deadline)
        except github_rest.DeadlineReached as error:
            raise SourceFailure(str(error), kind="deadline") from error
        except github_rest.UnsafeRedirect as error:
            raise SourceFailure(str(error), kind="redirect") from error
        except github_rest.GitHubReadError as error:
            raise SourceFailure(str(error)) from error

    def listing(self, directory: str, needed: set[str], deadline: float) -> Listing:
        """Return ``directory``'s records for ``needed`` names, reduced as they arrive."""
        url = listing_endpoint(
            self.repository, directory, self.merge_base, self.api_root
        )
        kept, total = reduce_listing(self._answer(url, deadline), needed)
        if kept is None:
            return Listing(records=None, total=0, malformed=False)
        if not isinstance(kept, list):
            return Listing(records=(), total=0, malformed=True)
        return Listing(
            records=tuple(base_record(record) for record in kept),
            total=total,
            malformed=False,
        )

    def contents(self, path: str, deadline: float) -> Contents:
        """Return ``path``'s base-revision bytes, or why they are not usable."""
        payload = self._answer(
            base_endpoint(self.repository, path, self.merge_base, self.api_root),
            deadline,
        )
        if payload is None:
            return Contents(data=None, reason="", found=False)
        data, reason = decoded_file(payload)
        return Contents(data=data, reason=reason, found=True)
