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

_MAX_PARTS = 9999


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
    data = (context / "diff.full").read_bytes()
    parts = context / "patches"
    parts.mkdir(exist_ok=True)
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


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <context-dir> <max-bytes>", file=sys.stderr)
        return 2
    split_diff(pathlib.Path(argv[1]), int(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
