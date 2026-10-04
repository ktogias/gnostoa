"""Decide whether a relayed request is owed a review, from the provider alone.

Decisions 0094, 0096 and 0100. A relay hands over a payload that a candidate can
produce, so that payload is a *pointer* and nothing more: an event kind, the id of the
object that carried the request, and the digest of the request text the provider
delivered. Two kinds of fact decide admission, and neither comes from the payload:

* **What the provider recorded about the triggering run** -- its event, the origin
  that defined it and the actor that triggered it. A candidate cannot forge these.
* **What the provider answers when the named object is read back** -- the text, its
  author, the author's standing, the item and change request it belongs to, and the
  change's live head and base.

The payload is bound to the first and replaced by the second. Refusal is the default:
a payload that is missing, malformed, disagrees with what the provider recorded, or
names something that cannot be read back is refused, because an unavailable answer is
not an admission.

The rules are here; the vocabulary is not. A request source translates its provider's
native objects into a ``Request``, and ``Rules`` carries the tokens, the trusted
standings, the trigger's origin and the admitted events, which are configuration of
the adapter and the agent rather than constants of the core.
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
from collections.abc import Mapping
from typing import Any, NamedTuple, Protocol

from tools.agent_review_model import CONTINUATION, Provider, Ref, ReviewSubject

_DIGEST = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"\A[0-9a-f]{40}\Z")
# Each forwarded text is written as its own bounded artefact rather than interpolated
# into the prompt. Decision 0094 rule 3 bounds the *static* prompt; candidate text used
# to reach it with no bound of its own.
_FORWARD_BYTES = 8192
# The relay payload is a few short fields; a real one is about 150 bytes.
_PAYLOAD_BYTES = 4096
NOT_A_REGULAR_FILE = "the relay payload is not a regular file"
# A provider creates a run seconds after its event: three were measured on this
# repository (review comment 4153694312 at 09:06:07Z, its trigger run at 09:06:10Z).
# The window leaves wide room for a slow provider; a request older than it is not the
# occurrence that started the run.
_OCCURRENCE_WINDOW_SECONDS = 15 * 60
# Both instants are the provider's, so this is tolerance for rounding, not for clocks.
_OCCURRENCE_SKEW_SECONDS = 60
_WITHHELD = "(withheld: the author is not a trusted association)"


class Refused(RuntimeError):
    """The relayed event is not owed a review, with the reason it was refused."""


class Rules(NamedTuple):
    """What the adapter and the agent configure: none of it is a core constant."""

    # Matched as a case-insensitive substring, as the trigger's own filter matches, so
    # admission neither widens nor narrows the request.
    mention_tokens: tuple[str, ...]
    # The author standings, in the provider's own vocabulary, that are trusted.
    trusted: tuple[str, ...]
    # The one origin -- a trigger definition -- whose runs may relay a request.
    origin: str
    # The events whose trigger the provider runs from the protected revision.
    events: tuple[str, ...]


class Trigger(NamedTuple):
    """What the provider recorded about the triggering run, which a candidate cannot
    forge, and the revision this run executes."""

    event: str
    origin: str
    actor: str
    created_at: str
    revision: str


class Request(NamedTuple):
    """The relayed object re-read from the provider. Every field is its answer."""

    author: str
    association: Any
    # The text the mention must be in, and whose digest the relay recorded.
    mention_text: str
    item: Ref
    change_request: Ref | None
    # When the provider says this object came to be: the event the relay claims.
    occurred_at: str
    # The forwarded text: the request itself, and the item's own title and body.
    request_text: Any
    title: Any
    body: Any
    # The item author's standing, which decides whether its text is forwarded.
    item_association: Any


class Revisions(NamedTuple):
    """A change request's live revisions, and the repository its head belongs to."""

    head_repository: Any
    head_commit: Any
    base_commit: Any


class RequestSource(Protocol):
    """The request-source role: re-read the relayed object and a change's revisions.

    ``read_request`` refuses an event it has no reader for and an object it cannot
    read back; ``revisions`` refuses a change request it cannot read. Both raise
    ``Refused``, never anything a caller has to tell apart from it.
    """

    provider: Provider

    def read_request(self, event: str, pointer: Mapping[str, Any]) -> Request:
        """Return the object ``pointer`` names, as the provider answers it."""
        raise NotImplementedError

    def revisions(self, change_request: Ref) -> Revisions:
        """Return ``change_request``'s live head and base."""
        raise NotImplementedError


class Admission(NamedTuple):
    """An admitted request: who and what it is of, and the text to forward.

    Two values rather than one: the subject is resolved identity a caller acts on, the
    forwarded text is candidate-controlled and only ever written to artefacts. They are
    kept apart so the text can never be mistaken for identity.
    """

    subject: ReviewSubject
    forwarded: dict[str, Any]


def trusted(value: Any, rules: Rules) -> bool:
    """Return whether ``value`` is a standing ``rules`` trusts."""
    return isinstance(value, str) and value in rules.trusted


def mentions(text: Any, rules: Rules) -> bool:
    """Return whether ``text`` carries one of the mention tokens.

    A case-insensitive substring, as the trigger's filter is, so admission neither
    widens nor narrows the request. This was once documented as case-sensitive, and
    admission then refused a capitalised mention after the privileged run had started.
    """
    if not isinstance(text, str):
        return False
    folded = text.lower()
    return any(token.lower() in folded for token in rules.mention_tokens)


def request_sha256(text: str) -> str:
    """Return the digest of a request's text: the one digest the relay binds to."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _forwarded(request: Request, rules: Rules) -> dict[str, Any]:
    """Return the text to forward, the item's own withheld for an untrusted author.

    Decision 0094 rule 15: externally authored item text is withheld. The item's author
    is not the request's author -- a trusted collaborator asking for a review of an
    outside contributor's change must not thereby forward that contributor's text into
    a credential-bearing job that publishes publicly. Withholding is stated rather than
    silent, so the reviewer cannot mistake absence for an empty description.
    """
    if trusted(request.item_association, rules):
        title, body = request.title, request.body
    else:
        title = _WITHHELD if request.title else ""
        body = _WITHHELD if request.body else ""
    return {"request": request.request_text, "title": title, "item": body}


def bind_to_trigger(pointer: Mapping[str, Any], trigger: Trigger, rules: Rules) -> None:
    """Refuse unless the pointer agrees with what the provider recorded about the run.

    Without this binding the relay has a spoofing gap. A collaborator can add a trigger
    definition carrying the trigger's *name*, have it hand over a payload naming
    someone else's earlier request, and so start a review nobody asked for now. Binding
    the event kind and the trigger's origin closes the first half; binding the
    request's author to the triggering actor closes the second. What is left -- a
    person relaying their own earlier request -- is equivalent to asking again, which
    they are already permitted to do.
    """
    if trigger.origin != rules.origin:
        raise Refused(
            f"the triggering run came from {trigger.origin!r}, not the trigger"
        )
    if trigger.event not in rules.events:
        raise Refused(
            f"the provider recorded {trigger.event!r}, not an admitted trigger"
        )
    if pointer.get("event_name") != trigger.event:
        raise Refused(
            f"the payload names {pointer.get('event_name')!r} but the provider "
            f"recorded {trigger.event!r} for the triggering run"
        )
    if not trigger.actor:
        raise Refused("the provider recorded no triggering actor for the run")


def _check_requester(request: Request, trigger: Trigger, rules: Rules) -> None:
    """Refuse unless the triggering actor wrote a trusted mention."""
    if request.author != trigger.actor:
        raise Refused(
            f"the mention was written by {request.author!r} but the run was "
            f"triggered by {trigger.actor!r}"
        )
    if not mentions(request.mention_text, rules):
        raise Refused("the re-read text does not carry the mention")
    if not trusted(request.association, rules):
        raise Refused(f"author association {request.association!r} is not admitted")


def _check_unedited(request: Request, pointer: Mapping[str, Any]) -> None:
    """Refuse a request whose re-read text differs from the text the provider delivered.

    A re-read alone records no history, so an edit between the event and this re-read
    changed what was reviewed while every occurrence check still passed. Anyone with
    write access can edit a request. A forged digest can only refuse: one that matches
    admits exactly what was re-read.
    """
    recorded = pointer.get("request_sha256")
    if not isinstance(recorded, str) or not _DIGEST.fullmatch(recorded):
        raise Refused(
            "the relay recorded no digest of the request the provider delivered"
        )
    if not hmac.compare_digest(recorded, request_sha256(request.mention_text)):
        raise Refused(
            "the request was edited after it triggered the run; ask again in a new "
            "comment"
        )


def _instant(value: str, label: str) -> datetime.datetime:
    """Return ``value`` as an aware instant, or refuse."""
    try:
        moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise Refused(f"{label} is not an ISO 8601 instant: {value!r}") from error
    if moment.tzinfo is None:
        raise Refused(f"{label} carries no time zone: {value!r}")
    return moment


def _check_occurrence(occurred_at: str, run_created_at: str) -> None:
    """Refuse an object that is not the occurrence that triggered the run.

    It was written against a candidate-controlled trigger relaying an old request. Both
    admitted events now run their trigger from the protected revision (Decision 0096
    rule 13), so it guards a stale relay rather than a hostile one. Both instants are
    the provider's, and a rerun keeps the run's original creation time -- so a rerun by
    the request's author passes here, and `_check_requester` refuses anyone else's.
    """
    event = _instant(occurred_at, "the relayed object's time")
    run = _instant(run_created_at, "the triggering run's creation time")
    gap = (run - event).total_seconds()
    if gap < -_OCCURRENCE_SKEW_SECONDS or gap > _OCCURRENCE_WINDOW_SECONDS:
        raise Refused(
            f"the relayed object ({occurred_at}) is not the occurrence that"
            f" triggered the run ({run_created_at})"
        )


def _live(source: RequestSource, repository: str, change: Ref) -> tuple[str, str]:
    """Return the change's live head and base, refusing a fork-controlled head."""
    revisions = source.revisions(change)
    if revisions.head_repository != repository:
        # Decision 0094 rule 9: a fork-controlled head is refused outright, and the
        # check is on the provider's answer, not the relay's.
        raise Refused(
            f"refusing a fork-controlled head ({revisions.head_repository!r})"
        )
    for label, value in (
        ("head", revisions.head_commit),
        ("base", revisions.base_commit),
    ):
        if not isinstance(value, str) or not _COMMIT.match(value):
            raise Refused(f"the change request's {label} revision is not an exact SHA")
    return str(revisions.head_commit), str(revisions.base_commit)


def admit(
    source: RequestSource,
    repository: str,
    pointer: Mapping[str, Any],
    trigger: Trigger,
    rules: Rules,
) -> Admission:
    """Return the admitted subject and the text to forward, or raise ``Refused``."""
    bind_to_trigger(pointer, trigger, rules)
    request = source.read_request(trigger.event, pointer)
    _check_requester(request, trigger, rules)
    _check_unedited(request, pointer)
    _check_occurrence(request.occurred_at, trigger.created_at)
    if request.change_request is None:
        # No change request: the request concerns the item itself, answered from the
        # repository. Decision 0094 rule 13 shows both revisions, equal, so that is
        # observable: the protected revision the job checked out.
        if not _COMMIT.match(trigger.revision):
            raise Refused(
                "the provider supplied no exact protected revision for this run"
            )
        head = base = trigger.revision
    else:
        # The admitted events happen on the conversation, not on a revision, so the
        # comparison is the change request as it stands.
        head, base = _live(source, repository, request.change_request)
    subject = ReviewSubject(
        provider=source.provider,
        repository=repository,
        item=request.item,
        change_request=request.change_request,
        head_commit=head,
        base_commit=base,
    )
    return Admission(subject, _forwarded(request, rules))


# ---------------------------------------------------------------------------------
# The relay payload and the request artefacts


def read_payload(path: str, limit: int = _PAYLOAD_BYTES) -> Any:
    """Read the relay payload as a bounded regular file, refusing anything else.

    ``limit`` is the adapter's: a pointer fits the default, and an adapter that relays
    the provider's delivered event declares a bound sized for one (#356).

    It arrives in an archive extracted inside the job that holds the credentials. The
    pinned extractor is past the zip-slip fix (CVE-2024-42471), but admission does not
    rest on one extractor's correctness: a symlink would make it read a file of the
    candidate's choosing, a FIFO would hang it, and an unbounded read would let a large
    payload exhaust it.
    """
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise Refused(NOT_A_REGULAR_FILE) from error
        raise
    # Checked on the descriptor, before wrapping it: a directory opens read-only but
    # cannot become a file object, and the refusal should say why. Closed on every way
    # out of the check, including `fstat` itself failing.
    try:
        regular = stat.S_ISREG(os.fstat(descriptor).st_mode)
    except BaseException:
        os.close(descriptor)
        raise
    if not regular:
        os.close(descriptor)
        raise Refused(NOT_A_REGULAR_FILE)
    with os.fdopen(descriptor, "rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise Refused(f"the relay payload exceeds {limit} bytes")
    return json.loads(raw.decode("utf-8"))


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


def _segments(line: str, line_cap: int) -> list[str]:
    """Return ``line`` as pieces each short enough to read once marked, never mid-character.

    The first piece holds ``line_cap`` bytes and every later one a marker fewer.
    """
    raw = line.encode("utf-8", "backslashreplace")
    if len(raw) <= line_cap:
        return [raw.decode("utf-8")]
    pieces = []
    room = line_cap
    while raw:
        end = min(room, len(raw))
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1  # not inside a UTF-8 sequence
        pieces.append(raw[:end].decode("utf-8"))
        raw = raw[end:]
        room = line_cap - len(CONTINUATION)
    return pieces


def _readable(text: str, line_cap: int) -> str:
    """Return ``text`` with every physical line short enough for the reviewer to read.

    The reviewer's reader truncates a line past ``line_cap`` and offsets by line, so a
    request on one long line hid its tail though every byte was present. Long lines are
    hard-wrapped, each continuation marked as the diff's are. A marker alone cannot say
    which lines continue, since a quoted reply begins with `>` too, so a note at the end
    names them by line number and the request reconstructs exactly.
    """
    physical: list[str] = []
    joins: list[str] = []
    for line in text.split("\n"):
        pieces = _segments(line, line_cap)
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


def _whole(text: Any, line_cap: int) -> str:
    """Return the request as written: it is the one artefact that is not cut.

    Every slice of an oversized request dropped the ask somewhere: a prefix lost a
    mention after pasted logs, a slice from the mention lost a question after them, and
    a first-and-last-half slice lost one in the middle. No bounded slice can be shown
    to keep it. The request is bounded where it is written -- the provider limits the
    size of the object that carries it -- and admission reads the provider's answer
    within its read bound. Its long lines are wrapped so that every byte can be read.
    """
    return _readable(text, line_cap) if isinstance(text, str) else ""


def write_request(
    target: pathlib.Path, forwarded: Mapping[str, Any], *, line_cap: int
) -> None:
    """Write the forwarded text as bounded artefacts under ``target``.

    The text comes from the read-back, never from the relay, and as files it is bounded
    and kept out of the prompt, the one input the reviewer cannot treat as material
    under review. ``line_cap`` is the reviewer's own line budget, which the agent
    adapter supplies.

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
        value = forwarded.get(name)
        text = _whole(value, line_cap) if name == "request" else _bounded(value)
        descriptor = os.open(target / name, flags, 0o644)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
