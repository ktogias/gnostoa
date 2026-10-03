"""The GitHub provider adapter for the agent review pipeline (Decision 0100).

Translates between GitHub's native vocabulary and the neutral core's: here, the issue
comments a review is delivered as, the identity that authors them, and the credential
shapes GitHub issues. Further roles are added as the pipeline's other stages move
behind the core.
"""

from __future__ import annotations

import re
import time

from tools import github_rest
from tools.agent_review_delivery import (
    DeliveryRefused,
    DeliveryUncertain,
    SecretPattern,
)

API = "https://api.github.com"
# The identity a GITHUB_TOKEN comment is authored by.
COMMENT_AUTHOR = "github-actions[bot]"
_LISTING_PAGES = 10
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

    ``find`` reads every page of comments updated since shortly before this sink was
    made, following the provider's own `Link` pages within a bound, and counts only those
    authored by the job's own identity. A thread flooded past the bound cannot be read
    back whole, which is a reason to stop rather than to post again (CodeAnt on #353).
    Every exchange is the shared client's: bounded as a whole and in size (CodeRabbit on
    #353), with a rate-limited create reported as uncertain, its wait honoured (Codex on
    #353).
    """

    def __init__(
        self, comments_url: str, client: github_rest.GitHubRestClient | None = None
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
        self.since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 300))

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
        try:
            for _ in range(_LISTING_PAGES):
                assert url is not None
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
