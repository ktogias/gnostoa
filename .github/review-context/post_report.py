"""Post a finished review into its thread: the GitHub Actions composition (Decision 0100).

The reviewer job runs the model on untrusted content and holds no write-capable token.
It hands its report over as an artifact, and a separate job with one write scope -- and
no environment, no secret and no model -- posts it with this script, as
`github-actions[bot]`. A comment made with `GITHUB_TOKEN` starts no workflow run, so a
posted review cannot re-trigger the relay (Decision 0098).

The rules are the neutral core's (`tools/agent_review_delivery.py`: rendering,
sanitising and post-once; `tools/agent_review_report.py`: the handoff). This file wires
them to GitHub and Claude: the issue-comments sink, both adapters' credential shapes,
the reviewer's name, and the identities the workflow passes, each validated before
anything is posted.

Invoked from `.github/workflows/claude.yml`, which runs from the repository's default
branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import os
import pathlib
import re
import sys
from typing import Any

from tools import agent_review_claude_code as claude
from tools import agent_review_delivery as delivery
from tools import agent_review_github as github
from tools.agent_review_paths import within
from tools.agent_review_report import AgentReport
from tools.agent_review_report import read_handoff as read_report

_REPOSITORY = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+\Z")
_ITEM = re.compile(r"\A[1-9][0-9]{0,9}\Z")
_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
# The run's start, as GitHub records `workflow_run.created_at`.
_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_SECRETS = github.SECRET_PATTERNS + claude.SECRET_PATTERNS


def sanitise(text: str) -> tuple[str, int]:
    """Return ``text`` safe for a public fence here, with GitHub's and Claude's shapes."""
    return delivery.sanitise(text, _SECRETS)


def render_comment(
    kind: str, text: str, *, run_url: str, head_sha: str, cut: bool = False
) -> str:
    """Return the comment body for a review of ``kind`` from this run.

    ``kind`` is one of ``complete``, ``incomplete``, ``unavailable`` or ``failed``.
    """
    failed = kind == "failed"
    report = AgentReport("unavailable" if failed else kind, text, cut)
    return delivery.render_comment(
        report,
        reviewer=claude.REVIEWER_NAME,
        provenance=f"Run: {run_url} · Reviewed revision: `{head_sha}`",
        secret_patterns=_SECRETS,
        failed=failed,
    )


def handoff_directory(raw: str) -> pathlib.Path | None:
    """Return the handoff directory confined to ``RUNNER_TEMP``, or None if absent.

    Confined by the shared `within`, which resolves the path and refuses one outside the
    runner's temporary area. A link in its place is refused as well. The files in it
    are then opened relative to it without following links, so nothing in it can point
    elsewhere. An absent directory is the normal case of a reviewer job that ended before
    it handed anything over.
    """
    if not raw or not os.path.lexists(raw):
        return None
    if os.path.islink(raw):
        raise ValueError(f"refusing a handoff directory that is a link: {raw!r}")
    return within(raw, "RUNNER_TEMP", must_exist=True)


def read_handoff(directory: pathlib.Path) -> tuple[str, str, bool]:
    """Return the handed-over status, text and cut."""
    report = read_report(directory)
    return report.status, report.text, report.cut


def post_comment(url: str, payload: dict[str, Any], marker: str, since: str) -> str:
    """Deliver ``payload`` to the issue-comments ``url`` once (core post-once), reading
    back every comment since ``since``."""
    try:
        sink = github.IssueCommentSink(url, since=since)
        return delivery.post_once(sink, payload["body"], marker)
    except (
        delivery.DeliveryRefused,
        delivery.DeliveryUncertain,
        delivery.DeliveryUnconfirmed,
    ) as error:
        raise RuntimeError(str(error)) from error


def _identity() -> tuple[str, str, str, str, str] | None:
    """Return the validated repository, item, revision, outcome and run URL."""
    repository = os.environ.get("REPOSITORY", "")
    item = os.environ.get("ITEM_NUMBER", "")
    head_sha = os.environ.get("HEAD_SHA", "")
    outcome = os.environ.get("REVIEW_OUTCOME", "")
    run_url = os.environ.get("RUN_URL", "")
    if not _REPOSITORY.match(repository) or ".." in repository:
        return None
    run = re.compile(
        rf"\Ahttps://github\.com/{re.escape(repository)}/actions/runs/[0-9]+\Z"
    )
    if not (_ITEM.match(item) and _SHA.match(head_sha) and run.match(run_url)):
        return None
    return repository, item, head_sha, outcome, run_url


def main(argv: list[str]) -> int:
    """Post the review handed over in ``argv[1]`` to the admitted item."""
    if len(argv) != 2:
        print(f"usage: {argv[0]} <handoff-directory>", file=sys.stderr)
        return 2
    identity = _identity()
    if identity is None:
        print(
            "refusing to post: an identity from the workflow did not validate",
            file=sys.stderr,
        )
        return 2
    repository, item, head_sha, outcome, run_url = identity
    attempt = os.environ.get("RUN_ATTEMPT", "1")
    if not _ITEM.match(attempt):
        print("refusing to post: RUN_ATTEMPT did not validate", file=sys.stderr)
        return 2
    since = os.environ.get("DELIVERY_SINCE", "")
    if not _INSTANT.match(since):
        print("refusing to post: DELIVERY_SINCE did not validate", file=sys.stderr)
        return 2
    # Trusted, first in the body, and unique to the attempt that wrote the report: what
    # a retry, or a rerun of only this job, looks for. A rerun of the review is a new
    # report and posts anew.
    marker = delivery.delivery_marker(f"{run_url.rsplit('/', 1)[1]}.{attempt}")
    try:
        directory = handoff_directory(argv[1])
    except ValueError as error:
        print(f"refusing to post: {error}", file=sys.stderr)
        return 2
    if outcome == "success" and directory is None and os.environ.get("REPORT_ARTIFACT"):
        # The reviewing job handed a report over and it did not arrive here: a failed
        # download, not a review that never finished. Posting the unavailable notice
        # would commit this delivery's marker, and a rerun that then received the real
        # report would find it and post nothing (Codex on #353).
        print(
            "refusing to post: the reviewing job handed a report over, but it was not "
            "received; rerun this job to deliver it",
            file=sys.stderr,
        )
        return 1
    if outcome != "success":
        kind, text, cut = "failed", "", False
    elif directory is None:
        kind, text, cut = "unavailable", "", False
    else:
        kind, text, cut = read_handoff(directory)
    rendered = render_comment(kind, text, run_url=run_url, head_sha=head_sha, cut=cut)
    body = f"{marker}\n{rendered}"
    url = f"{github.API}/repos/{repository}/issues/{item}/comments"
    try:
        posted = post_comment(url, {"body": body}, marker, since)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"posted {posted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
