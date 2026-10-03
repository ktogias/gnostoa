"""Decide whether a relayed mention is owed a review, from the provider alone.

Decision 0096. The mention reviewer runs from a `workflow_run` relay so that no
admitted trigger can supply the workflow or the scripts it executes. The relay hands
over a payload produced by a workflow a candidate can supply, so that payload is a
*pointer* and nothing more: an event kind and the id of a comment, review or issue.

Two kinds of fact decide admission, and neither comes from the payload:

* **What GitHub recorded about the triggering run** -- its `event`, its workflow
  `path` and its `triggering_actor`. These arrive on the `workflow_run` event, which
  this repository's protected workflow receives, so a candidate cannot forge them.
* **What the provider answers when the named object is read back** -- the body, the
  author, the author's association, the Pull Request it belongs to, whether that head
  is a fork, and the head and base revisions.

The payload is bound to the first and replaced by the second. Refusal is the default:
a payload that is missing, malformed, disagrees with what GitHub recorded, or names
something that cannot be read back is refused, because an unavailable answer is not an
admission. That is the same rule the current-state collector applies to coverage.

This script is trusted input: the checkout is the protected revision, so these bytes
come from the default branch and not from the candidate.
"""

from __future__ import annotations

import datetime
import errno
import hashlib
import hmac
import json
import os
import pathlib
import re
import stat
import sys
from typing import Any, NamedTuple

from chunk_diff import CONTINUATION, LINE_CAP

from tools import github_rest
from tools.agent_review_paths import within

_ADMITTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
_MENTION = "@claude"
_DIGEST = re.compile(r"[0-9a-f]{64}")
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
# Each forwarded text is written as its own bounded artefact rather than interpolated
# into the prompt. Decision 0094 rule 3 bounds the *static* prompt; candidate text used
# to reach it through `github.event` interpolation with no bound of its own.
_FORWARD_BYTES = 8192
# The relay payload is five short fields; a real one is about 150 bytes.
_PAYLOAD_BYTES = 4096
_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
_REPOSITORY = re.compile(r"\A[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\Z")


_NOT_A_REGULAR_FILE = "the relay payload is not a regular file"


class Refused(RuntimeError):
    """The relayed event is not owed a review, with the reason it was refused."""


class Subject(NamedTuple):
    """An event re-read from the provider. Every field is the provider's answer.

    A NamedTuple rather than a dataclass: the repository's test harness imports these
    scripts by path without registering them in `sys.modules`, and a dataclass with
    postponed annotations resolves its module through `sys.modules` at class creation.
    """

    author: str
    association: Any
    mention_text: str
    item_number: int
    pull_number: int | None
    forwarded: dict[str, Any]
    # When the provider says this object came to be -- the event the relay claims.
    occurred_at: str = ""


# ---------------------------------------------------------------------------------
# Provider access


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


# ---------------------------------------------------------------------------------
# Validation helpers


def _mapping(value: Any, label: str) -> dict[str, Any]:
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


def admitted_association(value: Any) -> bool:
    """Return whether ``value`` is an association this project admits."""
    return isinstance(value, str) and value in _ADMITTED_ASSOCIATIONS


def mentions_reviewer(text: Any) -> bool:
    """Return whether ``text`` carries the mention.

    A case-insensitive substring, as GitHub's expression `contains()` is -- the gate
    this replaces and the trigger's filter both use it -- so admission neither widens
    nor narrows the request. This docstring once called the old gate case-sensitive,
    and admission then refused "@Claude review" after the privileged run had started.
    """
    return isinstance(text, str) and _MENTION in text.lower()


def _item_text(item: dict[str, Any]) -> dict[str, Any]:
    """Return the item's own title and description, withheld for an untrusted author.

    Decision 0094 rule 15: externally authored item text is withheld. The item's
    author is not the mention's author -- a trusted collaborator asking for a review
    of an outside contributor's Pull Request must not thereby forward that
    contributor's text into a credential-bearing job that publishes publicly.

    Withholding is stated rather than silent, so the reviewer cannot mistake absence
    for an empty description.
    """
    title = item.get("title")
    body = item.get("body")
    if admitted_association(item.get("author_association")):
        return {"title": title, "item": body}
    withheld = "(withheld: the author is not a trusted association)"
    return {
        "title": withheld if title else "",
        "item": withheld if body else "",
    }


# ---------------------------------------------------------------------------------
# Re-reading the relayed object


def read_subject(repository: str, payload: dict[str, Any]) -> Subject:
    """Re-read the object the payload names, and describe it from the provider alone."""
    event = payload.get("event_name")
    reader = _READERS.get(event) if isinstance(event, str) else None
    if reader is None:
        raise Refused(f"event {event!r} is not an admitted trigger")
    return reader(f"repos/{repository}", payload)


def _read_issue_comment(root: str, payload: dict[str, Any]) -> Subject:
    """Re-read an issue comment and the item it belongs to."""
    comment = _mapping(
        provider_get(
            f"{root}/issues/comments/"
            f"{_identifier(payload.get('comment_id'), 'comment_id')}"
        ),
        "issue comment",
    )
    # The comment's own `issue_url` decides which item it belongs to; the relay's
    # claim about that is not used. A comment on a plain issue has no Pull Request.
    number = _trailing_number(comment.get("issue_url"), "issue comment issue_url")
    item = _mapping(provider_get(f"{root}/issues/{number}"), "issue")
    return Subject(
        author=_login(comment),
        occurred_at=str(comment.get("created_at") or ""),
        association=comment.get("author_association"),
        mention_text=str(comment.get("body") or ""),
        item_number=number,
        pull_number=number if isinstance(item.get("pull_request"), dict) else None,
        forwarded={"request": comment.get("body"), **_item_text(item)},
    )


def _read_issue(root: str, payload: dict[str, Any]) -> Subject:
    """Re-read an opened issue, which is itself the request."""
    number = _identifier(payload.get("issue_number"), "issue_number")
    issue = _mapping(provider_get(f"{root}/issues/{number}"), "issue")
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    return Subject(
        author=_login(issue),
        occurred_at=str(issue.get("created_at") or ""),
        association=issue.get("author_association"),
        # The issues trigger admits the mention in the title as well, as the gate
        # did.
        mention_text=f"{title}\n{body}",
        item_number=number,
        pull_number=number if isinstance(issue.get("pull_request"), dict) else None,
        # The issue *is* the request, and its mention may be in the title alone,
        # so the request artefact carries both. Forwarding only the body would
        # leave the file the reviewer is told to read first without the ask.
        forwarded={"request": f"{title}\n{body}", **_item_text(issue)},
    )


_READERS = {
    "issue_comment": _read_issue_comment,
    "issues": _read_issue,
}


# ---------------------------------------------------------------------------------
# Admission


def bind_to_trigger(payload: dict[str, Any], trigger: dict[str, str]) -> None:
    """Refuse unless the payload agrees with what GitHub recorded about the run.

    Without this binding the relay has a spoofing gap. A collaborator can add a
    workflow carrying the trigger's *name* on `push`, have it upload a payload naming
    someone else's earlier mention, and so start a review nobody asked for now.
    Binding the event kind and the trigger's file path closes the first half; binding
    the mention's author to the triggering actor, below, closes the second. What is
    left -- a person relaying their own earlier mention -- is equivalent to posting it
    again, which they are already permitted to do.
    """
    if trigger.get("path") != _TRIGGER_PATH:
        raise Refused(
            f"the triggering run came from {trigger.get('path')!r}, not the trigger"
        )
    if trigger.get("event") not in _EVENTS:
        raise Refused(
            f"GitHub recorded {trigger.get('event')!r}, not an admitted trigger"
        )
    if payload.get("event_name") != trigger.get("event"):
        raise Refused(
            f"the payload names {payload.get('event_name')!r} but GitHub recorded "
            f"{trigger.get('event')!r} for the triggering run"
        )
    if not trigger.get("actor"):
        raise Refused("GitHub recorded no triggering actor for the run")


# GitHub creates a run seconds after its event: three were measured on this
# repository (review comment 4153694312 at 09:06:07Z, its trigger run at 09:06:10Z).
# The window leaves wide room for a slow provider; a mention older than it is not
# the occurrence that started the run.
_OCCURRENCE_WINDOW_SECONDS = 15 * 60
# Both instants are GitHub's, so this is tolerance for rounding, not for clocks.
_OCCURRENCE_SKEW_SECONDS = 60


def _instant(value: str, label: str) -> datetime.datetime:
    try:
        moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise Refused(f"{label} is not an ISO 8601 instant: {value!r}") from error
    if moment.tzinfo is None:
        raise Refused(f"{label} carries no time zone: {value!r}")
    return moment


def _check_occurrence(occurred_at: str, run_created_at: str) -> None:
    """Refuse an object that is not the occurrence that triggered the run.

    It was written against a candidate-controlled trigger relaying an old mention.
    Both admitted events now run their trigger from the default branch (Decision 0096
    rule 13), so it guards a stale relay rather than a hostile one. Both instants are
    the provider's, and a rerun keeps the run's original creation time -- so a rerun by
    the mention's author passes here, and `_check_requester` refuses anyone else's.
    """
    event = _instant(occurred_at, "the relayed object's time")
    run = _instant(run_created_at, "the triggering run's creation time")
    gap = (run - event).total_seconds()
    if gap < -_OCCURRENCE_SKEW_SECONDS or gap > _OCCURRENCE_WINDOW_SECONDS:
        raise Refused(
            f"the relayed object ({occurred_at}) is not the occurrence that"
            f" triggered the run ({run_created_at})"
        )


def admit(
    repository: str, payload: dict[str, Any], trigger: dict[str, Any]
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return the admitted identity and the text to forward, or raise ``Refused``.

    Two values rather than one: the first is resolved identity the workflow reads as
    step outputs, the second is candidate-controlled text written to artefacts. They
    are kept apart so the text can never be mistaken for an output the workflow acts on.
    """
    if not _REPOSITORY.match(repository):
        raise Refused("the repository name is not in owner/name form")
    bind_to_trigger(payload, trigger)
    subject = read_subject(repository, payload)
    _check_requester(subject, trigger)
    _check_unedited(subject, payload)
    _check_occurrence(subject.occurred_at, str(trigger.get("created_at") or ""))

    resolved = {
        "item_number": str(subject.item_number),
        "pull_number": "" if subject.pull_number is None else str(subject.pull_number),
        "head_sha": "",
        "base_sha": "",
    }
    if subject.pull_number is None:
        # No Pull Request: the request concerns the item itself, answered from the
        # repository. Decision 0094 rule 13 shows both revisions, equal, so that is
        # observable: the protected revision the job checked out. (Codex)
        revision = str(trigger.get("revision") or "")
        if not _SHA.match(revision):
            raise Refused("GitHub supplied no exact protected revision for this run")
        resolved["head_sha"] = resolved["base_sha"] = revision
        return resolved, subject.forwarded
    # Both remaining events happen on the conversation, not on a revision, so the
    # comparison is the Pull Request as it stands.
    resolved["head_sha"], resolved["base_sha"] = _live_revisions(
        repository, subject.pull_number
    )
    return resolved, subject.forwarded


def _check_requester(subject: Subject, trigger: dict[str, Any]) -> None:
    """Refuse unless the triggering actor wrote a trusted mention."""
    if subject.author != trigger["actor"]:
        raise Refused(
            f"the mention was written by {subject.author!r} but the run was "
            f"triggered by {trigger['actor']!r}"
        )
    if not mentions_reviewer(subject.mention_text):
        raise Refused("the re-read text does not carry the mention")
    if not admitted_association(subject.association):
        raise Refused(f"author association {subject.association!r} is not admitted")


def request_sha256(text: str) -> str:
    """Return the digest of a request's text, as the trigger records it."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _check_unedited(subject: Subject, payload: dict[str, Any]) -> None:
    """Refuse a request whose re-read text differs from the text GitHub delivered.

    The trigger recorded only identities, so an edit between the event and this re-read
    changed what was reviewed while every occurrence check still passed (CodeAnt). Anyone
    with write access can edit a comment, and so can an app holding `issues: write`. A
    forged digest can only refuse: one that matches admits exactly what was re-read.
    """
    recorded = payload.get("request_sha256")
    if not isinstance(recorded, str) or not _DIGEST.fullmatch(recorded):
        raise Refused("the relay recorded no digest of the request GitHub delivered")
    if not hmac.compare_digest(recorded, request_sha256(subject.mention_text)):
        raise Refused(
            "the request was edited after it triggered the run; ask again in a new "
            "comment"
        )


def _live_revisions(repository: str, number: int) -> tuple[str, str]:
    """Return the Pull Request's live head and base, refusing a fork-controlled head."""
    pull = _mapping(provider_get(f"repos/{repository}/pulls/{number}"), "pull request")
    head = _mapping(pull.get("head"), "pull.head")
    head_repo = _mapping(head.get("repo"), "pull.head.repo").get("full_name")
    if head_repo != repository:
        # Decision 0094 rule 9: a fork-controlled head is refused outright, and the
        # check is on the provider's answer, not the relay's.
        raise Refused(f"refusing a fork-controlled head ({head_repo!r})")
    base = _mapping(pull.get("base"), "pull.base")
    for label, value in (("head", head.get("sha")), ("base", base.get("sha"))):
        if not isinstance(value, str) or not _SHA.match(value):
            raise Refused(f"the pull request's {label} revision is not an exact SHA")
    return str(head["sha"]), str(base["sha"])


# ---------------------------------------------------------------------------------
# Output


def _bounded(text: Any) -> str:
    """Return ``text`` no longer than the forward bound, saying when it was cut."""
    if not isinstance(text, str) or not text:
        return ""
    raw = text.encode("utf-8")
    if len(raw) <= _FORWARD_BYTES:
        return text
    return (
        raw[:_FORWARD_BYTES].decode("utf-8", "ignore")
        + f"\n[truncated at {_FORWARD_BYTES} bytes]"
    )


def _segments(line: str) -> list[str]:
    """Return ``line`` as pieces each short enough to read once marked, never mid-character.

    The first piece holds `LINE_CAP` bytes and every later one a marker fewer.
    """
    raw = line.encode("utf-8", "backslashreplace")
    if len(raw) <= LINE_CAP:
        return [raw.decode("utf-8")]
    pieces = []
    room = LINE_CAP
    while raw:
        end = min(room, len(raw))
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1  # not inside a UTF-8 sequence
        pieces.append(raw[:end].decode("utf-8"))
        raw = raw[end:]
        room = LINE_CAP - len(CONTINUATION)
    return pieces


def _readable(text: str) -> str:
    """Return ``text`` with every physical line short enough for the reviewer to read.

    The reviewer's Read tool truncates a line past `LINE_CAP` and offsets by line, so a
    request on one long line hid its tail though every byte was present (Codex). Long
    lines are hard-wrapped, each continuation marked as the diff's are. A marker alone
    cannot say which lines continue, since a quoted reply begins with `>` too, so a note
    at the end names them by line number and the request reconstructs exactly.
    """
    physical: list[str] = []
    joins: list[str] = []
    for line in text.split("\n"):
        pieces = _segments(line)
        if len(pieces) > 1:
            # Numbered as the file will be: after the one-line header written below.
            first = len(physical) + 2
            joins.append(
                f"[line {first} continues on lines {first + 1} to "
                f"{first + len(pieces) - 1}]"
            )
        physical.append(pieces[0])
        physical.extend(CONTINUATION.decode() + piece for piece in pieces[1:])
    if not joins:
        return text
    header = (
        "[long lines below are hard-wrapped for reading; each continuation begins "
        f"with {CONTINUATION.decode()!r}, which is not part of the request, and the "
        "notes at the end name every one]"
    )
    return "\n".join([header, *physical, *joins])


def _whole(text: Any) -> str:
    """Return the request as written: it is the one artefact that is not cut.

    Every slice of an oversized request dropped the ask somewhere: a prefix lost a
    mention after pasted logs, a slice from the mention lost a question after them, and
    a first-and-last-half slice lost one in the middle (Codex, three times). No bounded
    slice can be shown to keep it. The request is bounded where it is written --
    GitHub limits a comment or an issue body to 65,536 characters -- and admission
    reads the provider's answer within ``MAX_BYTES``. Its long lines are wrapped so that
    every byte can also be read.
    """
    return _readable(text) if isinstance(text, str) else ""


def read_payload(path: str) -> Any:
    """Read the relay payload as a bounded regular file, refusing anything else.

    It arrives in an archive extracted inside the job that holds the credentials. The
    job's own gate now admits only a run of the default branch's trigger, but before
    that gate the candidate could build it, and admission does not rest on the gate. The pinned extractor is past the zip-slip fix
    (CVE-2024-42471), but admission does not rest on one extractor's correctness: a
    symlink would make it read a file of the candidate's choosing, a FIFO would hang it,
    and an unbounded read would let a large payload exhaust it.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise Refused(_NOT_A_REGULAR_FILE) from error
        raise
    # Checked on the descriptor, before wrapping it: a directory opens read-only
    # but cannot become a file object, and the refusal should say why. Closed on
    # every way out of the check, including `fstat` itself failing.
    try:
        regular = stat.S_ISREG(os.fstat(descriptor).st_mode)
    except BaseException:
        os.close(descriptor)
        raise
    if not regular:
        os.close(descriptor)
        raise Refused(_NOT_A_REGULAR_FILE)
    with os.fdopen(descriptor, "rb") as handle:
        raw = handle.read(_PAYLOAD_BYTES + 1)
    if len(raw) > _PAYLOAD_BYTES:
        raise Refused(f"the relay payload exceeds {_PAYLOAD_BYTES} bytes")
    return json.loads(raw.decode("utf-8"))


def write_request(target: pathlib.Path, forwarded: dict[str, Any]) -> None:
    """Write the forwarded text as bounded artefacts under ``target``.

    These used to be interpolated into the prompt from `github.event`. Under the relay
    that payload is not present in the privileged job, so the text has to come from
    the read-back either way -- and as files it is bounded and kept out of the prompt,
    the one input the reviewer cannot treat as material under review.

    Every value here is candidate-controlled; nothing is interpreted, only written.
    Every artefact is written, empty when absent, so the reviewer never has to tell a
    missing file from an empty one.

    The directory is created here, so one that already exists -- or a symlink in its
    place -- was not, and would redirect every artefact; each file is created
    exclusively and never through a link.
    """
    try:
        target.mkdir(parents=True)
    except FileExistsError as error:
        raise Refused(f"the request directory {target} already exists") from error
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    for name in ("request", "title", "item"):
        bound = _whole if name == "request" else _bounded
        descriptor = os.open(target / name, flags, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(bound(forwarded.get(name)) + "\n")


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
            raise Refused(_NOT_A_REGULAR_FILE)
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
