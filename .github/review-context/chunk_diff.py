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
    """Return how many bytes of ``buffer`` the next part may hold."""
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
    return end or limit


def split_diff(context: pathlib.Path, limit: int) -> int:
    """Write ``diff.full`` as bounded parts and return how many were written."""
    if limit < 1:
        raise ValueError("the byte bound must be positive")
    data, wrapped, continuations = wrap_long_records(
        (context / "diff.full").read_bytes()
    )
    parts = context / "patches"
    parts.mkdir(exist_ok=True)
    if wrapped:
        (parts / "README").write_text(
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
            "number is approximate rather than computing one from this text.\n",
            encoding="utf-8",
        )
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
    overview = (parts / "part-0001").read_bytes() if index else b""
    notices = []
    if index > 1:
        notices.append(
            f"[bounded at {limit} bytes of {len(data)}; the whole diff is in "
            "patches/, read in name order]"
        )
    if wrapped:
        # Disclosed whenever wrapping happened, not only when the size bound was also
        # crossed. A diff holding one very long record can fit in a single part, and
        # then diff.patch carried inserted newlines and continuation markers with
        # nothing saying they are synthetic -- the reviewer reads them as real diff
        # content and computes line numbers from them. The bound notice is also what
        # sends it to patches/README, so without this it never learns the rule.
        notices.append(
            f"[{wrapped} long record(s) hard-wrapped over {continuations} "
            f"continuation line(s) beginning {_CONTINUATION.decode()!r}; no byte was "
            "removed or reordered, but a line number inside a wrapped record is "
            "approximate -- see patches/README]"
        )
    if notices:
        overview += ("\n" + "\n".join(notices) + "\n").encode()
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
