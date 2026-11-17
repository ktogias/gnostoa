"""What other test modules share from tests/test_r2a_p2b_b16_publication.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import re

_HEREDOC_RE = re.compile(r"(?<!<)(<<-?)(?!<)\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?")


def _single_start(lines: list[str], sequence: tuple[str, ...]) -> int | None:
    """The one index at which `sequence` starts in `lines`; None when it starts at none or at several."""
    width = len(sequence)
    starts = [
        index
        for index in range(len(lines) - width + 1)
        if tuple(lines[index : index + width]) == sequence
    ]
    if len(starts) != 1:
        return None
    return starts[0]


def _heredoc_ends(raw_line: str, heredoc: tuple[str, bool]) -> bool:
    """Whether `raw_line` is the open heredoc's delimiter, its leading tabs stripped for `<<-`."""
    delimiter, strip_tabs = heredoc
    candidate = raw_line.lstrip("\t") if strip_tabs else raw_line
    return candidate == delimiter


def _close_line(stripped: str, stack: list[str]) -> bool | None:
    """A closing line: True once it closed the innermost open command substitution or block,
    False when it closes nothing open or another block; None when the line closes nothing."""
    if stripped.startswith(")") and stack and stack[-1] == "cmdsub":
        stack.pop()
        return True

    closers = {
        "fi": "fi",
        "done": "done",
        "esac": "esac",
        ")": ")",
        "}": "}",
    }
    if stripped not in closers:
        return None
    expected = closers[stripped]
    if not stack or stack[-1] != expected:
        return False
    stack.pop()
    return True


def _open_line(stripped: str, stack: list[str]) -> None:
    """The block, and any command substitution left open, that `stripped` opens, pushed on `stack`."""
    if stripped.startswith("if "):
        stack.append("fi")
    elif stripped.startswith(("for ", "while ", "until ", "select ")):
        stack.append("done")
    elif stripped.startswith("case "):
        stack.append("esac")
    elif stripped == "(":
        stack.append(")")
    elif stripped.endswith("{"):
        stack.append("}")

    last_command_sub = stripped.rfind("$(")
    if last_command_sub >= 0 and ")" not in stripped[last_command_sub + 2 :]:
        stack.append("cmdsub")


def _heredoc_start(stripped: str) -> tuple[bool, tuple[str, bool] | None]:
    """Whether the line is acceptable, and the heredoc it opens: two on one line are refused."""
    heredoc_matches = list(_HEREDOC_RE.finditer(stripped))
    if len(heredoc_matches) > 1:
        return False, None
    if not heredoc_matches:
        return True, None
    operator, delimiter = heredoc_matches[0].groups()
    return True, (delimiter, operator == "<<-")


def _has_direct_top_level_shell_sequence(
    script: str, sequence: tuple[str, ...]
) -> bool:
    lines = script.splitlines()
    start = _single_start(lines, sequence)
    if start is None:
        return False

    stack: list[str] = []
    heredoc: tuple[str, bool] | None = None
    for raw_line in lines[:start]:
        stripped = raw_line.strip()
        if heredoc is not None:
            if _heredoc_ends(raw_line, heredoc):
                heredoc = None
            continue
        if not stripped or stripped.startswith("#"):
            continue

        closed = _close_line(stripped, stack)
        if closed is False:
            return False
        if closed:
            continue

        _open_line(stripped, stack)
        accepted, heredoc = _heredoc_start(stripped)
        if not accepted:
            return False

    return heredoc is None and not stack
