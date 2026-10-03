"""Split a unified diff into bounded parts the reader can reach whole (Decision 0094).

The bounded reviewer has no git and no candidate working tree, so `patches/` is the only
place a removed file's old content exists. Line boundaries are preferred, but a single
line longer than the bound must still be cut, and `split -C` cuts such a record by bytes
-- which halves a multibyte character and leaves two parts a text reader cannot decode.

Every rewrite made for the reader -- escaped line separators, escaped invalid UTF-8,
doubled backslashes, wrapped records -- is disclosed in the overview and in
`patches/README`, because a rewrite nobody counts is a rewrite nobody discloses. The
reader's line budget is the agent adapter's (Decision 0100), so this names none.
"""

from __future__ import annotations

import pathlib
import re

from tools.agent_review_base import wrap_records
from tools.agent_review_model import CONTINUATION

_MAX_PARTS = 9999
# A byte that is not valid UTF-8, as `surrogateescape` decodes it.
_INVALID_OCTET = re.compile("[\udc80-\udcff]")
# Taken from what the reader actually breaks on rather than from the obvious few:
# Python's ``str.splitlines`` -- which is what the reviewer's tools use -- treats the
# vertical tab, form feed and the file/group/record separators as boundaries as well as
# CR and the Unicode separators. An earlier pass covered four of these and left five,
# so `+safe\x0b+++ b/forged.py` still reached the reviewer as a standalone header.
_EMBEDDED_BREAKS = {
    b"\x0b": b"\\013",
    b"\x0c": b"\\014",
    b"\x1c": b"\\034",
    b"\x1d": b"\\035",
    b"\x1e": b"\\036",
    b"\r": b"\\015",
    "\u0085".encode(): b"\\302\\205",
    "\u2028".encode(): b"\\342\\200\\250",
    "\u2029".encode(): b"\\342\\200\\251",
}


_ESCAPED_LABELS = (
    (b"\\013", "VT, the vertical tab"),
    (b"\\014", "FF, the form feed"),
    (b"\\034", "FS, the file separator"),
    (b"\\035", "GS, the group separator"),
    (b"\\036", "RS, the record separator"),
    (b"\\015", "CR, a carriage return not followed by a line feed"),
    (b"\\302\\205", "U+0085, the next-line character"),
    (b"\\342\\200\\250", "U+2028, the line separator"),
    (b"\\342\\200\\251", "U+2029, the paragraph separator"),
)


def _escape_invalid_utf8(data: bytes) -> tuple[bytes, int]:
    """Return ``data`` with every byte that is not valid UTF-8 escaped, and a count.

    One pass: `surrogateescape` turns each such byte into a lone surrogate, which no
    valid UTF-8 can decode to, so every surrogate found is exactly one invalid byte.
    """
    text = data.decode("utf-8", "surrogateescape")
    text, count = _INVALID_OCTET.subn(
        lambda match: "\\%03o" % (ord(match.group()) - 0xDC00), text
    )
    return text.encode("utf-8"), count


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def escape_embedded_breaks(data: bytes) -> tuple[bytes, int, int, int]:
    """Return ``data`` with non-LF line separators escaped, and three counts.

    A diff record may legally contain a byte sequence a Unicode-aware reader treats as a
    line break -- a lone CR, or U+0085/U+2028/U+2029 -- while this splitter, and Git
    itself, orient on LF. Left raw, a changed line carrying `+++ b/forged.py` after one
    of them appears to the reviewer as a standalone file header, and the reviewer has no
    git with which to check. They are escaped to their octal UTF-8 bytes, the form
    `git -c core.quotePath=true` uses and the form pathnames already get here.

    A CR immediately before an LF is a Windows line ending rather than a separator of
    its own, and is left alone: rewriting it would alter every record of a CRLF-authored
    file for no gain.

    The escape output is ordinary ASCII, so the encoding has to say which backslashes
    it introduced. Two attempts failed before this one, and both failures are the same
    mistake -- an encoding that is *nearly* unambiguous:

    * escaping separators alone made a literal `\\342\\200\\250` in the source produce
      bytes identical to an escaped U+2028;
    * pre-escaping the literal *body* fixed that case and left a worse one, because a
      candidate backslash sitting immediately before a **raw** separator still produced
      those same bytes -- so a real separator read as ordinary text, on purpose if the
      candidate chose, while the notice claimed the transformation was reversible.

    So the encoding is the one Git already uses for pathnames: **every** backslash is
    doubled first, and only then are separators escaped. A single backslash in the
    output can therefore only be one this function introduced, and `\\\\` is one literal
    backslash from the source. There is no clever case left to get wrong.

    Bytes that are not valid UTF-8 -- a Latin-1 source file, say -- are escaped the same
    way, to their octal value. Left raw they made every part holding them undecodable,
    so with no candidate tree the hunk could not be read at all, while the prompt said
    the whole diff was reachable. Because every escape here is one byte as `\\ooo` and
    every literal backslash is doubled, one reversal undoes all of them.

    Doubling is skipped entirely when there is nothing to escape, so an ordinary diff
    is passed through byte for byte and the reviewer sees the source as written. The
    second count reports how many backslashes were doubled, because a rewrite nobody
    counts is a rewrite nobody discloses -- the notices key on these counts, and the
    previous version rewrote literals without incrementing either.
    """
    separators = [raw for raw in _EMBEDDED_BREAKS if raw != b"\r"]
    # A lone CR only: a CR before an LF is a Windows line ending, not a separator.
    lone_cr = re.compile(rb"\r(?!\n)")
    if (
        not lone_cr.search(data)
        and not any(raw in data for raw in separators)
        and _is_utf8(data)
    ):
        # Nothing to escape, so nothing is rewritten and nothing has to be explained.
        return data, 0, 0, 0
    doubled = data.count(b"\\")
    out = data.replace(b"\\", b"\\\\")
    # A function, not a replacement string: `re` reads `\015` in a replacement as an
    # octal escape and would turn it straight back into the CR being escaped.
    out, found = lone_cr.subn(lambda _match: _EMBEDDED_BREAKS[b"\r"], out)
    for raw, escaped in _EMBEDDED_BREAKS.items():
        if raw == b"\r":
            continue
        count = out.count(raw)
        if count:
            found += count
            out = out.replace(raw, escaped)
    # After the separators: those are valid UTF-8 and become ASCII, and ASCII never
    # completes a broken sequence, so what is invalid here was invalid in the input.
    out, octets = _escape_invalid_utf8(out)
    return out, found, doubled, octets


def next_cut(buffer: bytes, limit: int) -> int:
    """Return how many bytes of ``buffer`` the next part may hold.

    A non-positive limit means there is no room at all, which the overview asks for
    when its notices already fill the bound. That is an empty answer, not an error;
    the overview itself then refuses if the notices alone exceed the bound.
    """
    if limit <= 0:
        return 0
    if len(buffer) <= limit:
        return len(buffer)
    newline = buffer.rfind(b"\n", 0, limit)
    if newline != -1:
        return newline + 1
    # One oversized line. Retreat off any UTF-8 continuation byte so that no
    # character is split across two parts.
    end = limit
    while end > 0 and (buffer[end] & 0xC0) == 0x80:
        end -= 1
    if end == 0:
        # Falling back to the raw limit here split the character this retreat exists to
        # keep whole, and did it silently. A bound that cannot hold one character is a
        # configuration error, not something to paper over.
        raise ValueError("the byte bound is smaller than one character")
    return end


def _readme_notes(
    escaped: int,
    doubled: int,
    octets: int,
    wrapped: int,
    continuations: int,
    line_cap: int,
) -> str:
    """Explain, for patches/README, every rewrite the parts carry."""
    notes = ""
    # Keyed on either count, never on the separators alone. The doubling rewrites bytes
    # too, and a diff holding a literal `\\015` with no real separator was rewritten
    # with nothing saying so -- the reviewer then reads the extra backslash as the
    # candidate's own source and may report it as a defect. A rewrite nobody counts is
    # a rewrite nobody discloses.
    if escaped or doubled or octets:
        notes += (
            f"{escaped} non-LF line separator(s) were escaped to their octal UTF-8\n"
            f"bytes, and {doubled} backslash(es) were doubled to make that reversible.\n"
            "A reader that treats those separators as line breaks would otherwise see\n"
            "the text after one as a record of its own, so candidate content could pose\n"
            "as a file header. Every backslash in this diff is doubled, so a single\n"
            "backslash is one this collection introduced and \\\\ is one literal\n"
            "backslash from the source. The escaped forms, and what each stands for:\n"
            + "".join(
                f"  {escape.decode()} for {label}\n"
                for escape, label in _ESCAPED_LABELS
            )
            + "A CR directly before an LF is a line ending, not a separator, and is\n"
            "left as it is.\n"
            "\n"
        )
    if octets:
        notes += (
            f"{octets} byte(s) in this diff were not valid UTF-8 -- a source file in\n"
            "another encoding, for example -- and were escaped to their octal value,\n"
            "\\ooo, so that every part decodes as text. They are recoverable exactly by\n"
            "the same rule as the separators above; the file's real encoding is not\n"
            "known here, so do not read the escapes as characters.\n"
            "\n"
        )
    if wrapped:
        notes += (
            f"{wrapped} diff record(s) exceeded {line_cap} bytes on one line and were\n"
            f"hard-wrapped over {continuations} continuation line(s) so a line-oriented\n"
            "reader can reach all of them. No byte of the diff was removed or\n"
            f"reordered. Each continuation begins with {CONTINUATION.decode()!r},\n"
            "which never begins a line of unified diff output: without it a segment\n"
            "starting with '-' or '+' would read as a deletion or an addition.\n"
            "\n"
            "A wrapped record occupies several displayed lines, so counting lines\n"
            "within its hunk no longer matches the file's own numbering. For a\n"
            "finding inside a wrapped record, cite the hunk header and say the line\n"
            "number is approximate rather than computing one from this text.\n"
        )
    return notes


def _write_parts(parts: pathlib.Path, data: bytes, limit: int) -> int:
    """Write ``data`` as bounded parts in name order, and return how many."""
    offset = 0
    index = 0
    while offset < len(data):
        take = next_cut(data[offset:], limit)
        index += 1
        if index > _MAX_PARTS:
            raise ValueError("diff needs more parts than the naming allows")
        (parts / f"part-{index:04d}").write_bytes(data[offset : offset + take])
        offset += take
    return index


def _overview_notices(
    escaped: int, doubled: int, octets: int, wrapped: int, continuations: int
) -> bytes:
    """The wrap and escape notices diff.patch carries, in the order it shows them."""
    escape_notice = b""
    if escaped or doubled or octets:
        # Disclosed in the overview too, not only in patches/README. The README is
        # reached through a notice, and tying that notice to wrapping meant a small
        # single-part diff was rewritten with nothing saying so -- the octal text then
        # reads as the candidate's own source. The same reasoning covers the doubling,
        # which rewrites bytes whether or not a separator was present.
        escape_notice = (
            f"\n[{escaped} non-LF line separator(s) in the diff were escaped to octal"
            f" UTF-8 bytes so they cannot start a record, {octets} byte(s) that were"
            f" not valid UTF-8 were escaped to octal so every part decodes, and"
            f" {doubled} backslash(es) were doubled so the escaping is reversible;"
            " see patches/README]\n"
        ).encode()
    wrap_notice = b""
    if wrapped:
        # Disclosed whenever wrapping happened, not only when the size bound was also
        # crossed. A diff holding one very long record can fit in a single part, and
        # then diff.patch carried inserted newlines and continuation markers with
        # nothing saying they are synthetic -- the reviewer reads them as real diff
        # content and computes line numbers from them. The bound notice is also what
        # sends it to patches/README, so without this it never learns the rule.
        wrap_notice = (
            f"\n[{wrapped} long record(s) hard-wrapped over {continuations} "
            f"continuation line(s) beginning {CONTINUATION.decode()!r}; no byte was "
            "removed or reordered, but a line number inside a wrapped record is "
            "approximate -- see patches/README]\n"
        ).encode()
    return wrap_notice + escape_notice


def split_diff(context: pathlib.Path, limit: int, *, line_cap: int) -> int:
    """Write ``diff.full`` as bounded parts and return how many were written.

    ``line_cap`` is the reader's own line budget, which its adapter declares: a single
    very long record -- a minified bundle, a generated lockfile -- would otherwise leave
    its tail unreachable even though the bytes are present.
    """
    if limit < 1:
        raise ValueError("the byte bound must be positive")
    data, escaped, doubled, octets = escape_embedded_breaks(
        (context / "diff.full").read_bytes()
    )
    data, wrapped, continuations = wrap_records(data, line_cap)
    parts = context / "patches"
    parts.mkdir(exist_ok=True)
    notes = _readme_notes(escaped, doubled, octets, wrapped, continuations, line_cap)
    if notes:
        (parts / "README").write_text(notes, encoding="utf-8")
    index = _write_parts(parts, data, limit)
    # The overview and its notice are written here rather than by the caller, because
    # only this function knows how many parts exist. Deciding from the *input* size
    # would miss a diff that fits the bound until wrapping pushes it past: the
    # reviewer would then read part one with nothing saying a tail exists.
    bound_notice = (
        # "All of this diff", never "the whole diff": on the provider's refusal this
        # diff is assembled per-file hunks, which can omit files, and the prompt says
        # when that is so.
        f"\n[bounded at {limit} bytes of {len(data)}; all of this diff is in "
        "patches/, read in name order]\n"
    ).encode()
    # The notices are part of diff.patch, so their room comes out of the same bound.
    # Taking a whole part and appending afterwards let the file exceed the very number
    # it prints -- an artefact asserting something false about itself. The overview is
    # therefore a line-boundary prefix sized with the notices, rather than part one
    # verbatim; it is still whole lines, so it still decodes as text.
    trailer = _overview_notices(escaped, doubled, octets, wrapped, continuations)
    body = data[: next_cut(data, max(0, limit - len(trailer)))]
    if index > 1 or len(body) < len(data):
        body = data[: next_cut(data, max(0, limit - len(trailer) - len(bound_notice)))]
        overview = body + bound_notice + trailer
    else:
        overview = body + trailer
    if len(overview) > limit:
        # Only a bound smaller than the notices themselves reaches this: the body is
        # already empty. Cutting the notices would drop the disclosures the reviewer
        # needs, and writing them would let the file exceed the number it prints.
        raise ValueError(
            f"a {limit}-byte bound cannot hold the overview's own notices"
            f" ({len(overview)} bytes)"
        )
    (context / "diff.patch").write_bytes(overview)
    return index
