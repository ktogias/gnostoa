"""Deliver an agent's review into the thread it was requested in (Decision 0100).

Provider- and agent-neutral. A provider adapter supplies a ``CommentSink`` -- how to
create a comment, and how to find one this pipeline already created -- and the
credential shapes its own platform issues; an agent adapter supplies the reviewer's
name and its credential shapes. Everything else is here, the same for every pair:
rendering, sanitising and the post-once algorithm (Decisions 0094 rule 22, 0098 rules
5 and 6).

What reaches a public thread is model output shaped by untrusted content, so it is
treated as untrusted:

- **Kept literal.** The text is placed in a fenced block that no line in it can close.
  Over-long backtick runs are capped first, so the fence stays short and the body stays
  within the comment limit.
- **Mentions neutralised.** The at-sign of a mention becomes U+FF20 FULLWIDTH
  COMMERCIAL AT, so no person is pinged and no bot -- this repository's own relay
  included -- acts on a raw-text match.
- **Invisible characters made visible.** Bidirectional controls, zero-width characters
  and other control characters are written as backslash-u escapes.
- **Credentials redacted.** A comment, unlike a masked log, is not masked. Anything
  shaped like a credential is redacted, and the redaction is stated. Shapes are matched
  across invisible characters and run on to the end of their word, so a token split by
  one, or two written back to back, are still redacted. This catches disclosure, not a
  deliberate encoder: text that spells a secret out evades any pattern. The control
  against that is that the reviewer can reach no secret (Decision 0098 rule 1).
- **Bounded.** The whole body stays under a 65,536-character comment limit, counted in
  UTF-16 code units, the strictest reading of "characters".

Only trusted facts sit outside the fence: the provenance the composition supplies and
the notices written here.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Callable, Iterable
from typing import Protocol

from tools.agent_review_report import AgentReport

COMMENT_LIMIT = 65536
_TEXT_BUDGET = 60000
_LONGEST_BACKTICK_RUN = 8
_ATTEMPTS = 3
# The longest a provider's own retry hint is honoured for.
_MAX_HINT_SECONDS = 60.0
_FULLWIDTH_AT = "\uff20"
_DELIVERY_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_BACKTICKS = re.compile(f"`{{{_LONGEST_BACKTICK_RUN + 1},}}")
_MENTION = re.compile(r"@(?=[A-Za-z0-9])")
# What a credential is made of, for running a match on to the end of its word.
_TOKEN_CHARACTER = re.compile(r"[A-Za-z0-9_-]")
# What counts as invisible is decided by category, not by a list: an enumerated class
# missed tag characters, the soft hyphen and others, and a token split by one survived
# redaction (a review finding on #353). Every control, format, surrogate, private-use and
# unassigned code point, and the line and paragraph separators, except a newline and a
# tab. These categories hold no character a review needs to show as itself.
_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
# And the invisible characters whose category is a visible one: the combining grapheme
# joiner, Hangul fillers, Khmer inherent vowels, Mongolian free variation selectors and
# the variation selectors.
_INVISIBLE_EXTRA = frozenset(
    {"\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u3164", "\uffa0"}
    | {chr(code) for code in range(0x180B, 0x1810)}
    | {chr(code) for code in range(0xFE00, 0xFE10)}
    | {chr(code) for code in range(0xE0100, 0xE01F0)}
)
_KEPT = frozenset("\n\t")


def _invisible(character: str) -> bool:
    """Return whether ``character`` cannot be seen as itself in a public comment."""
    if character in _KEPT:
        return False
    return (
        character in _INVISIBLE_EXTRA
        or unicodedata.category(character) in _INVISIBLE_CATEGORIES
    )


def _escaped(character: str) -> str:
    """Return ``character`` as a visible escape, or itself if it can be seen."""
    if not _invisible(character):
        return character
    code = ord(character)
    return f"\\u{code:04x}" if code <= 0xFFFF else f"\\U{code:08x}"


SecretPattern = tuple[re.Pattern[str], str]

# Credential shapes no single platform owns. Each adapter adds the shapes its own
# platform issues, so a new provider or agent brings its tokens without a core change.
GENERIC_SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    (re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"), "AWS key id"),
    (re.compile(r"xox[abpsr]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (
        re.compile(
            r"eyJ[A-Za-z0-9_-]{10,2000}\.eyJ[A-Za-z0-9_-]{10,4000}\.[A-Za-z0-9_-]{10,2000}"
        ),
        "JWT",
    ),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        "private key",
    ),
)


class DeliveryRefused(RuntimeError):
    """The provider refused the comment. That is its answer, and it is not retried."""


class DeliveryUncertain(RuntimeError):
    """The comment may or may not exist: the request failed in a way that cannot tell.

    A sink raises this from ``create`` for a timeout, an outage, a lost answer, a rate
    limit or a failure to connect, and from ``find`` for any failure to read back. When
    the provider said when to try again, ``retry_after`` carries it. ``in_flight`` says
    the attempt was abandoned rather than ended, so it may still create the comment.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: float | None = None,
        in_flight: bool = False,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.in_flight = in_flight


class DeliveryUnconfirmed(RuntimeError):
    """A retry was owed, but whether the first attempt landed could not be read back."""


class CommentSink(Protocol):
    """Where a provider adapter delivers comments. Two roles, nothing more.

    ``find`` must count only comments this pipeline's own identity created: anyone may
    write a copy of a marker, and one that suppressed the real review would be a cheap
    denial. It raises ``DeliveryUncertain`` when it cannot read back completely.
    """

    def create(self, body: str) -> str:
        """Create a comment with ``body`` and return where it is."""
        raise NotImplementedError

    def find(self, marker: str) -> str | None:
        """Return where this pipeline's comment starting with ``marker`` is, if any."""
        raise NotImplementedError


def delivery_marker(delivery_id: str) -> str:
    """Return the trusted first line of a delivery, unique to ``delivery_id``.

    The composition chooses the id -- one run attempt, say -- so a rerun is a new
    delivery and posts anew, while a retry within one delivery finds its own comment.
    """
    if not _DELIVERY_ID.match(delivery_id):
        raise ValueError(
            f"refusing a delivery id that is not a plain token: {delivery_id!r}"
        )
    return f"<!-- gnostoa:agent-review:{delivery_id} -->"


def _units(text: str) -> int:
    """Return the length of ``text`` in UTF-16 code units."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def _widened(pattern: re.Pattern[str], skeleton: str) -> list[tuple[int, int]]:
    """Return ``pattern``'s matches in ``skeleton``, each run on to the end of its word.

    A greedy match can stop inside a credential: two tokens written back to back
    matched as one that ended at the second's underscore, and left its secret part in
    view (#353). So a match that ends on a token character is widened over every token
    character that follows. A match inside a span already widened is skipped, which
    keeps the walk linear in the text however many matches a long run holds.
    """
    spans = []
    reach = -1
    for match in pattern.finditer(skeleton):
        start, end = match.span()
        if end <= start or end <= reach:
            continue
        if _TOKEN_CHARACTER.match(skeleton[end - 1]):
            while end < len(skeleton) and _TOKEN_CHARACTER.match(skeleton[end]):
                end += 1
        reach = end
        spans.append((start, end))
    return spans


def _redacted(text: str, patterns: Iterable[SecretPattern]) -> tuple[str, int]:
    """Return ``text`` with every credential shape redacted, and how many were.

    Matched on the text with invisible characters removed, then applied to the text as
    written, so a token split by one is still redacted rather than escaped into view.
    """
    kept = [index for index, character in enumerate(text) if not _invisible(character)]
    skeleton = "".join(text[index] for index in kept)
    spans = sorted(
        (kept[start], kept[end - 1] + 1, kind)
        for pattern, kind in patterns
        for start, end in _widened(pattern, skeleton)
    )
    parts: list[str] = []
    position = 0
    count = 0
    for start, end, kind in spans:
        if start < position:
            # Overlaps a span already redacted: widen it rather than expose the tail.
            position = max(position, end)
            continue
        parts.extend((text[position:start], f"[redacted: {kind}]"))
        position = end
        count += 1
    parts.append(text[position:])
    return "".join(parts), count


def sanitise(
    text: str, secret_patterns: Iterable[SecretPattern] = ()
) -> tuple[str, int]:
    """Return ``text`` safe to place in a public fence, and how much was redacted.

    ``secret_patterns`` are the adapters' credential shapes, used together with the
    generic ones.
    """
    text, redacted = _redacted(text, (*GENERIC_SECRET_PATTERNS, *secret_patterns))
    text = "".join(_escaped(character) for character in text)
    text = _MENTION.sub(_FULLWIDTH_AT, text)
    text = _BACKTICKS.sub(
        lambda match: (
            "`" * _LONGEST_BACKTICK_RUN
            + f"[+{len(match.group()) - _LONGEST_BACKTICK_RUN} backticks]"
        ),
        text,
    )
    return text, redacted


def _bounded(text: str) -> tuple[str, bool]:
    """Return ``text`` cut to the fence budget, and whether it was cut."""
    if _units(text) <= _TEXT_BUDGET:
        return text, False
    kept: list[str] = []
    used = 0
    for character in text:
        used += _units(character)
        if used > _TEXT_BUDGET:
            break
        kept.append(character)
    return "".join(kept), True


def _fenced(text: str) -> str:
    """Return ``text`` in a backtick fence no line of it can close."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def render_comment(
    report: AgentReport,
    *,
    reviewer: str,
    poster: str,
    provenance: str,
    secret_patterns: Iterable[SecretPattern],
    failed: bool = False,
) -> str:
    """Return the comment body for ``report`` from ``reviewer``.

    ``poster`` says, in the composition's own words, what posted the comment;
    ``provenance`` is the composition's trusted line saying which run reviewed which
    revision. ``failed`` says the reviewing job itself failed, whatever it handed over.
    """
    if failed or report.status == "unavailable":
        reason = (
            "The review did not complete."
            if failed
            else "The review finished, but its report is unavailable."
        )
        return (
            f"### {reviewer} review unavailable\n\n{reason} The run's log holds the "
            f"reason.\n\n{provenance}\n"
        )
    advisory = (
        f"_Advisory review by {reviewer}, posted by {poster}. It is not an approval "
        "and carries no merge authority._"
    )
    safe, redacted = sanitise(report.text, secret_patterns)
    safe, truncated = _bounded(safe)
    notices = []
    if report.cut and not truncated:
        notices.append(
            "The report was truncated before it was handed over; the rest was not "
            "posted."
        )
    if truncated:
        notices.append(
            f"The report was truncated at {_TEXT_BUDGET} characters; the rest was not "
            "posted."
        )
    if redacted:
        notices.append(
            f"{redacted} value(s) shaped like a credential were redacted from the report."
        )
    notices.append(
        f"Mentions in the report are neutralised ({_FULLWIDTH_AT}), so they ping no one "
        "and trigger no bot."
    )
    complete = report.status == "complete"
    heading = f"{reviewer} review" if complete else f"{reviewer} review incomplete"
    caveat = (
        ""
        if complete
        else (
            "The reviewer did not finish. What follows is the last text it produced, "
            "which may be a diagnostic rather than findings. Treat the change as not "
            "reviewed.\n\n"
        )
    )
    notes = "".join(f"- {notice}\n" for notice in notices)
    return (
        f"### {heading}\n\n{advisory}\n\n{provenance}\n\n{notes}\n{caveat}"
        f"{_fenced(safe)}\n"
    )


def post_once(
    sink: CommentSink,
    body: str,
    marker_line: str,
    *,
    attempts: int = _ATTEMPTS,
    pause: Callable[[float], object] | None = None,
) -> str:
    """Create ``body`` through ``sink`` once, retrying only what cannot duplicate it.

    Creating a comment is not idempotent: an uncertain failure can arrive after the
    provider created it. So before every create -- the first one too, since a rerun of
    the delivery is a new process with the same marker (a review finding on #353) --
    the sink is asked for this delivery's own comment, found by ``marker_line``, which
    starts the body. When that read-back fails, delivery stops rather than risk
    posting the review twice: a missing comment is visible as a failed job; a
    duplicate is not.

    An attempt still in flight ends delivery too. A read-back finding nothing proves
    only that the comment does not exist yet, and an abandoned attempt can still create
    it after a second one was sent (a review finding on #353).
    """
    if not body.startswith(marker_line):
        raise ValueError("the body must start with its delivery marker")
    # Resolved per call, not bound at definition, so the clock can be replaced.
    wait = time.sleep if pause is None else pause
    hint = 0.0
    for attempt in range(attempts):
        if attempt:
            # The provider's own word on when to try again, when it gave one: retrying
            # inside a rate-limit window can extend it.
            wait(max(5.0 * attempt, min(hint, _MAX_HINT_SECONDS)))
        try:
            existing = sink.find(marker_line)
        except DeliveryUncertain as error:
            raise DeliveryUnconfirmed(
                "could not confirm whether the review was delivered, so it was "
                f"not delivered again: {error}"
            ) from error
        if existing is not None:
            return existing
        try:
            return sink.create(body)
        except DeliveryUncertain as error:
            if error.in_flight:
                raise DeliveryUnconfirmed(
                    "an attempt to deliver the review may still be running, so it was "
                    f"not delivered again: {error}"
                ) from error
            if attempt == attempts - 1:
                raise
            hint = error.retry_after or 0.0
    raise AssertionError("unreachable")  # pragma: no cover
