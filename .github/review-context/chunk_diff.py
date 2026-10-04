"""Split the review context's diff into bounded parts: the core, bound to the reader.

Decisions 0094 and 0100. Every rule -- the character-safe cut, the separator and
encoding escapes, the wrapped records, the overview and its disclosures -- is the
neutral core's (`tools/agent_review_diff.py`). The reader's line budget is the Claude
Code adapter's; this binds the two and confines the context directory.

This file is invoked from the collection entrypoint, from the protected checkout, so it
is not candidate-supplied.
"""

from __future__ import annotations

import pathlib
import sys

from tools import agent_review_diff as diff
from tools.agent_review_base import wrap_records
from tools.agent_review_claude_code import READ_LINE_CAP as LINE_CAP
from tools.agent_review_model import CONTINUATION
from tools.agent_review_paths import within

__all__ = [
    "CONTINUATION",
    "LINE_CAP",
    "escape_embedded_breaks",
    "next_cut",
    "split_diff",
    "wrap_long_records",
]

escape_embedded_breaks = diff.escape_embedded_breaks
next_cut = diff.next_cut


def wrap_long_records(data: bytes) -> tuple[bytes, int, int]:
    """Hard-wrap records longer than the reader's line budget (the core's rule)."""
    return wrap_records(data, LINE_CAP)


def split_diff(context: pathlib.Path, limit: int) -> int:
    """Write ``diff.full`` as bounded parts for this reader; return how many."""
    return diff.split_diff(context, limit, line_cap=LINE_CAP)


def main(argv: list[str]) -> int:
    """Split the diff in the context directory named by ``argv`` into bounded parts."""
    if len(argv) != 3:
        print(f"usage: {argv[0]} <context-dir> <max-bytes>", file=sys.stderr)
        return 2
    split_diff(within(argv[1], "GITHUB_WORKSPACE", must_exist=True), int(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
