"""Admit a relayed mention: the GitHub Actions composition of the admission core.

Decisions 0096 and 0100. The mention reviewer runs from a `workflow_run` relay so that
no admitted trigger can supply the workflow or the scripts it executes. The relay hands
over a payload produced by a workflow a candidate can supply, so that payload is a
*pointer* and nothing more.

Every rule -- binding to the run, the requester's trust, the digest, the occurrence
window, the fork check and the withholding of untrusted text -- is the neutral core's
(`tools/agent_review_admission.py`). GitHub's vocabulary is its adapter's
(`tools/agent_review_github.py`), and the mention and the reader's line budget are the
Claude Code adapter's. This entrypoint reads what GitHub recorded about the
triggering run from the environment, reads the provider through the shared client,
composes the three, and writes the step outputs.

This script is trusted input: the checkout is the protected revision, so these bytes
come from the default branch and not from the candidate.
"""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Any

from tools import agent_review_admission as admission
from tools import agent_review_claude_code as claude_code
from tools import agent_review_github as github
from tools import github_rest
from tools.agent_review_paths import within

_TRIGGER_PATH = ".github/workflows/claude-mention-trigger.yml"
# Owner decision on #339 (Decision 0096 rule 13): the two review events are withdrawn.
# Their trigger ran from the candidate's branch, so its author chose the object it
# named; both events that remain run their trigger from the default branch.
_EVENTS = ("issue_comment", "issues")
_ATTEMPTS = 3
_RETRY_SECONDS = 5
_TIMEOUT_SECONDS = 30
# Provider answers carry candidate-controlled text, so every read is bounded, as every
# other provider read in this directory is.
MAX_BYTES = 1 << 20

# The core's rules, configured for this deployment: the trigger and its events are
# this repository's, the trusted associations GitHub's, the mention the agent's. The
# trigger's own filter matches the mention with `contains()`, which is
# case-insensitive, and admission matches it the same way.
RULES = admission.Rules(
    mention_tokens=(claude_code.MENTION,),
    trusted=github.TRUSTED_ASSOCIATIONS,
    origin=_TRIGGER_PATH,
    events=_EVENTS,
)

Refused = admission.Refused
read_payload = admission.read_payload


def _policy() -> github_rest.Policy:
    """Admission's bounds, read when used, so a test can tighten them on this module."""
    return github_rest.Policy(
        timeout_seconds=_TIMEOUT_SECONDS,
        attempts=_ATTEMPTS,
        retry_sleep_seconds=_RETRY_SECONDS,
        max_response_bytes=MAX_BYTES,
    )


def provider_get(path: str) -> Any:
    """Return the provider's JSON for ``path``, retried and bounded, or refuse.

    Read through the shared client (Decision 0100): bounded as a whole -- a provider
    sending a byte before each socket timeout cannot hold the credential-bearing job --
    and in size; retried, because one transient failure must not decide whether a review
    happens, with a rate limit waited out rather than spent. Exhausting the attempts, or
    any refusal, refuses rather than admits.
    """
    try:
        client = github_rest.GitHubRestClient.from_environment(
            user_agent="gnostoa-admit-mention", policy=_policy()
        )
    except github_rest.GitHubError as error:
        raise Refused(
            "no usable provider token is available to re-read the event"
        ) from error
    try:
        return client.read_json(client.url(path))
    except github_rest.GitHubError as error:
        if error.status is not None:
            raise Refused(f"HTTP {error.status} reading {path!r}") from error
        raise Refused(f"{error} reading {path!r}") from error


def admit(
    repository: str, payload: dict[str, Any], trigger: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return the admitted step outputs and the text to forward, or raise ``Refused``.

    Two values rather than one: the first is resolved identity the workflow reads as
    step outputs, the second is candidate-controlled text written to artefacts.
    """
    # Looked up when called, so a test can stand in for the provider on this module.
    source = github.IssueRequests(repository, lambda path: provider_get(path))
    recorded = admission.Trigger(
        event=str(trigger.get("event") or ""),
        origin=str(trigger.get("path") or ""),
        actor=str(trigger.get("actor") or ""),
        created_at=str(trigger.get("created_at") or ""),
        revision=str(trigger.get("revision") or ""),
    )
    admitted = admission.admit(source, repository, payload, recorded, RULES)
    return github.step_outputs(admitted.subject), admitted.forwarded


def write_request(target: pathlib.Path, forwarded: dict[str, Any]) -> None:
    """Write the forwarded text as artefacts, wrapped to the reviewer's line budget."""
    admission.write_request(target, forwarded, line_cap=claude_code.READ_LINE_CAP)


def _confined(path: str, *, must_exist: bool) -> pathlib.Path:
    """Return ``path`` resolved inside RUNNER_TEMP, through the shared check.

    The returned path is the one used. Checking one value and opening another left the
    two agreeing only by construction, and every file operation fed the unchecked one.
    """
    try:
        return within(path, "RUNNER_TEMP", must_exist=must_exist)
    except ValueError as error:
        raise Refused(str(error)) from error


def main(argv: list[str]) -> int:
    """Admit the relayed event named by ``argv``, writing the outputs and request."""
    if len(argv) != 4:
        print(
            f"usage: {argv[0]} <repository> <relay-payload> <request-dir>",
            file=sys.stderr,
        )
        return 2
    repository, payload_path, request_dir = argv[1:]
    # Recorded by GitHub on the workflow_run event and passed in by the protected
    # workflow: the facts a candidate cannot forge.
    trigger = {
        "event": os.environ.get("TRIGGER_EVENT", ""),
        "path": os.environ.get("TRIGGER_PATH", ""),
        "actor": os.environ.get("TRIGGER_ACTOR", ""),
        "created_at": os.environ.get("TRIGGER_CREATED_AT", ""),
        # The revision this run executes, which the job checked out: GitHub's, not
        # anything a trigger wrote.
        "revision": os.environ.get("PROTECTED_REVISION", ""),
    }
    try:
        # Decision 0094 rule 23: every review-context script confines its paths
        # through the one shared check, and uses the path it returns. A link in the
        # payload's place is refused first, since confinement resolves it. Anything
        # already in the request directory's place is refused as existing before
        # confinement, which would misreport it as a misplaced directory.
        if os.path.islink(payload_path):
            # Refused before anything resolves it: resolving would follow the link
            # and read a file of the candidate's choosing.
            raise Refused(admission.NOT_A_REGULAR_FILE)
        payload_file = _confined(payload_path, must_exist=True)
        if os.path.lexists(request_dir):
            raise Refused(f"the request directory {request_dir} already exists")
        request_target = _confined(request_dir, must_exist=False)
        payload = read_payload(str(payload_file))
        if not isinstance(payload, dict):
            raise Refused("the relay payload was not an object")
        resolved, forwarded = admit(repository, payload, trigger)
        write_request(request_target, forwarded)
    except Refused as refusal:
        # One line naming the reason. The operator needs to tell "not a review" from
        # "could not tell", and neither may collapse into silence.
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"REFUSED: unreadable relay payload ({error})", file=sys.stderr)
        return 1

    lines = "".join(f"{key}={value}\n" for key, value in sorted(resolved.items()))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        # Not pinned to a root, as the publisher's summary path is not: where the
        # runner keeps it is its own detail. Still resolved, absolute, not a directory.
        try:
            output = str(within(output, "", must_exist=False))
        except ValueError as error:
            print(f"REFUSED: {error}", file=sys.stderr)
            return 1
        try:
            with open(output, "a", encoding="utf-8") as handle:
                handle.write(lines)
        except OSError as error:
            # Inside the refusal path like every other failure: one line, with the
            # reason, rather than a traceback. (CodeAnt)
            print(
                f"REFUSED: could not write the step outputs ({error})", file=sys.stderr
            )
            return 1
    print(lines, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
