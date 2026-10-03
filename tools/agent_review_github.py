"""The GitHub provider adapter for the agent review pipeline (Decision 0100).

Translates between GitHub's native vocabulary and the neutral core's: the issue
comments, issues and Pull Requests a request is re-read from, the trusted
`author_association` values, the issue comments a review is delivered as, the identity
that authors them, and the credential shapes GitHub issues.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from typing import Any

from tools import github_rest
from tools.agent_review_admission import Refused, Request, Revisions
from tools.agent_review_delivery import (
    DeliveryRefused,
    DeliveryUncertain,
    SecretPattern,
)
from tools.agent_review_model import Provider, Ref, ReviewSubject

API = "https://api.github.com"
# The identity a GITHUB_TOKEN comment is authored by.
COMMENT_AUTHOR = "github-actions[bot]"
_LISTING_PAGES = 10
_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
# One attempt per exchange: post-once owns retries, and a create is never retried here.
_POLICY = github_rest.Policy(attempts=1, max_response_bytes=4 << 20)
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
        return str(answer.get("html_url", "")) if isinstance(answer, dict) else ""

    def find(self, marker: str) -> str | None:
        """Return this job's comment that starts with ``marker``, if GitHub has it."""
        url: str | None = f"{self.comments_url}?since={self.since}&per_page=100"
        pages = 0
        try:
            # Narrowed by an explicit check, not an assert: an assert is stripped under
            # `python -O`, and a bound is not something to compile away (Codacy, B101).
            while url is not None and pages < _LISTING_PAGES:
                pages += 1
                listing, headers = self.client.get(url)
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
                        return str(comment.get("html_url", ""))
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
            request=comment.get("body"),
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
            request=f"{title}\n{body}",
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
