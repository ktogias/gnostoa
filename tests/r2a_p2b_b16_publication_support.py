"""What other test modules share from tests/test_r2a_p2b_b16_publication.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import re

_HEREDOC_RE = re.compile(r"(?<!<)(<<-?)(?!<)\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?")


def _has_direct_top_level_shell_sequence(
    script: str, sequence: tuple[str, ...]
) -> bool:
    lines = script.splitlines()
    width = len(sequence)
    starts = [
        index
        for index in range(len(lines) - width + 1)
        if tuple(lines[index : index + width]) == sequence
    ]
    if len(starts) != 1:
        return False

    stack: list[str] = []
    heredoc: tuple[str, bool] | None = None
    for raw_line in lines[: starts[0]]:
        stripped = raw_line.strip()
        if heredoc is not None:
            delimiter, strip_tabs = heredoc
            candidate = raw_line.lstrip("\t") if strip_tabs else raw_line
            if candidate == delimiter:
                heredoc = None
            continue
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith(")") and stack and stack[-1] == "cmdsub":
            stack.pop()
            continue

        closers = {
            "fi": "fi",
            "done": "done",
            "esac": "esac",
            ")": ")",
            "}": "}",
        }
        if stripped in closers:
            expected = closers[stripped]
            if not stack or stack[-1] != expected:
                return False
            stack.pop()
            continue

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

        heredoc_matches = list(_HEREDOC_RE.finditer(stripped))
        if len(heredoc_matches) > 1:
            return False
        if heredoc_matches:
            operator, delimiter = heredoc_matches[0].groups()
            heredoc = (delimiter, operator == "<<-")

    return heredoc is None and not stack
