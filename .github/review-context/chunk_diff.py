"""Split a diff into bounded parts without cutting a UTF-8 character in half.

The bounded reviewer of Decision 0094 has no git and no candidate working tree, so
`patches/` is the only place a removed file's old content exists. Line boundaries are
preferred, but a single line longer than the bound must still be cut, and `split -C`
cuts such a record by bytes -- which halves a multibyte character and leaves two parts
a text reader cannot decode.

This file is invoked from `.github/workflows/claude.yml`, which for the mention
triggers runs from the repository's default branch, so it is not candidate-supplied.
"""

from __future__ import annotations

import pathlib
import sys

from review_context_paths import within

_MAX_PARTS = 9999
# The reviewer's Read tool truncates a physical line beyond roughly this length and
# offsets into a file by line, so a single very long record -- a minified bundle, a
# generated lockfile -- would leave its tail unreachable even though the bytes are
# present. Such records are therefore hard-wrapped at a reader-visible boundary. Only
# newlines are inserted: no byte of the diff is removed or reordered.
_LINE_CAP = 1900
# A wrapped continuation carries no diff prefix, so a segment beginning with "-", "+",
# "@@" or "+++ b/" would read as a deletion, an addition or a new hunk or file header
# and be attributed to the wrong side of the change. Continuations are therefore marked
# with a byte that never begins a line of unified diff output.
_CONTINUATION = b">"


def _wrap_point(record: bytes, room: int) -> int:
    """Return how many bytes of an oversized record fit on one line without splitting."""
    end = room
    while end > 0 and (record[end] & 0xC0) == 0x80:
        end -= 1
    return end or room


_EMBEDDED_BREAKS = {
    b"\r": b"\\015",
    "\u0085".encode(): b"\\302\\205",
    "\u2028".encode(): b"\\342\\200\\250",
    "\u2029".encode(): b"\\342\\200\\251",
}


def escape_embedded_breaks(data: bytes) -> tuple[bytes, int]:
    """Return ``data`` with non-LF line separators escaped, and how many were found.

    A diff record may legally contain a byte sequence a Unicode-aware reader treats as a
    line break -- a lone CR, or U+0085/U+2028/U+2029 -- while this splitter, and Git
    itself, orient on LF. Left raw, a changed line carrying `+++ b/forged.py` after one
    of them appears to the reviewer as a standalone file header, and the reviewer has no
    git with which to check. They are escaped to their octal UTF-8 bytes, the form
    `git -c core.quotePath=true` uses and the form pathnames already get here.

    A CR immediately before an LF is a Windows line ending rather than a separator of
    its own, and is left alone: rewriting it would alter every record of a CRLF-authored
    file for no gain.
    """
    out = data.replace(b"\r\n", b"\x00CRLF\x00")
    found = 0
    for raw, escaped in _EMBEDDED_BREAKS.items():
        count = out.count(raw)
        if count:
            found += count
            out = out.replace(raw, escaped)
    return out.replace(b"\x00CRLF\x00", b"\r\n"), found


def wrap_long_records(data: bytes) -> tuple[bytes, int, int]:
    """Hard-wrap records longer than the readable cap.

    Returns the wrapped text, how many records were wrapped, and how many continuation
    lines were introduced. Each continuation costs exactly two bytes -- one newline and
    one marker -- which is what lets a test assert that nothing else changed.
    """
    out = bytearray()
    wrapped = 0
    continuations = 0
    for record in data.split(b"\n"):
        if len(record) <= _LINE_CAP:
            out += record + b"\n"
            continue
        wrapped += 1
        offset = 0
        first = True
        while offset < len(record):
            room = _LINE_CAP if first else _LINE_CAP - len(_CONTINUATION)
            remaining = len(record) - offset
            take = (
                remaining if remaining <= room else _wrap_point(record[offset:], room)
            )
            if not first:
                out += _CONTINUATION
                continuations += 1
            out += record[offset : offset + take] + b"\n"
            offset += take
            first = False
    if data.endswith(b"\n"):
        # split() produced a trailing empty record, which added one newline too many.
        del out[-1:]
    elif out.endswith(b"\n"):
        del out[-1:]
    return bytes(out), wrapped, continuations


def next_cut(buffer: bytes, limit: int) -> int:
    """Return how many bytes of ``buffer`` the next part may hold.

    A non-positive limit means there is no room at all, which the overview asks for
    when its notices already fill the bound. That is an empty answer, not an error.
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


def split_diff(context: pathlib.Path, limit: int) -> int:
    """Write ``diff.full`` as bounded parts and return how many were written."""
    if limit < 1:
        raise ValueError("the byte bound must be positive")
    data, escaped = escape_embedded_breaks((context / "diff.full").read_bytes())
    data, wrapped, continuations = wrap_long_records(data)
    parts = context / "patches"
    parts.mkdir(exist_ok=True)
    notes = ""
    if escaped:
        notes += (
            f"{escaped} non-LF line separator(s) -- a lone CR, or U+0085, U+2028 or\n"
            "U+2029 -- were escaped to their octal UTF-8 bytes. A reader that treats\n"
            "those as line breaks would otherwise see the text after one of them as a\n"
            "record of its own, so candidate content could pose as a file header.\n"
            "\n"
        )
    if wrapped:
        notes += (
            f"{wrapped} diff record(s) exceeded {_LINE_CAP} bytes on one line and were\n"
            f"hard-wrapped over {continuations} continuation line(s) so a line-oriented\n"
            "reader can reach all of them. No byte of the diff was removed or\n"
            f"reordered. Each continuation begins with {_CONTINUATION.decode()!r},\n"
            "which never begins a line of unified diff output: without it a segment\n"
            "starting with '-' or '+' would read as a deletion or an addition.\n"
            "\n"
            "A wrapped record occupies several displayed lines, so counting lines\n"
            "within its hunk no longer matches the file's own numbering. For a\n"
            "finding inside a wrapped record, cite the hunk header and say the line\n"
            "number is approximate rather than computing one from this text.\n"
        )
    if notes:
        (parts / "README").write_text(notes, encoding="utf-8")
    offset = 0
    index = 0
    while offset < len(data):
        take = next_cut(data[offset:], limit)
        index += 1
        if index > _MAX_PARTS:
            raise ValueError("diff needs more parts than the naming allows")
        (parts / f"part-{index:04d}").write_bytes(data[offset : offset + take])
        offset += take
    # The overview and its notice are written here rather than by the caller, because
    # only this function knows how many parts exist. Deciding from the *input* size
    # would miss a diff that fits the bound until wrapping pushes it past: the
    # reviewer would then read part one with nothing saying a tail exists.
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
            f"continuation line(s) beginning {_CONTINUATION.decode()!r}; no byte was "
            "removed or reordered, but a line number inside a wrapped record is "
            "approximate -- see patches/README]\n"
        ).encode()
    bound_notice = (
        f"\n[bounded at {limit} bytes of {len(data)}; the whole diff is in "
        "patches/, read in name order]\n"
    ).encode()
    # The notices are part of diff.patch, so their room comes out of the same bound.
    # Taking a whole part and appending afterwards let the file exceed the very number
    # it prints -- an artefact asserting something false about itself. The overview is
    # therefore a line-boundary prefix sized with the notices, rather than part one
    # verbatim; it is still whole lines, so it still decodes as text.
    body = data[: next_cut(data, max(0, limit - len(wrap_notice)))]
    if index > 1 or len(body) < len(data):
        body = data[
            : next_cut(data, max(0, limit - len(wrap_notice) - len(bound_notice)))
        ]
        overview = body + bound_notice + wrap_notice
    else:
        overview = body + wrap_notice
    (context / "diff.patch").write_bytes(overview)
    return index


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <context-dir> <max-bytes>", file=sys.stderr)
        return 2
    split_diff(within(argv[1], "GITHUB_WORKSPACE", must_exist=True), int(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
