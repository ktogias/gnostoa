"""The Claude Code agent adapter for the agent review pipeline (Decision 0100).

Translates what the pinned Claude Code action leaves behind -- its execution file, a
JSON list of turns -- into the core's ``AgentReport``, and declares what only this
agent knows: its display name, its mention token and the shape of its own keys. Every
other step is the neutral core's.

Success must be stated, never inferred from the absence of a failure signal. The
native envelope carries `subtype: "success"` with `is_error: false` on a run that
finished. This repository established that in
`knowledge/assessments/native-structured-review-handoff.md`, whose declared
`claude-structured` adapter requires exactly that pair, and which retains a mutant
(`M1-ignore-success-subtype-isolated`) showing that ignoring the success subtype
produces three assertion failures against its oracle.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

from tools.agent_review_delivery import SecretPattern
from tools.agent_review_report import AgentReport, unavailable

REVIEWER_NAME = "Claude"
# What a request must carry to be one for this agent. Matched case-insensitively, as
# the provider's own trigger filter matches it.
MENTION = "@claude"
# The execution file holds every turn, not just the report, so its bound is larger.
MAX_EXECUTION_BYTES = 8 * 1024 * 1024
SECRET_PATTERNS: tuple[SecretPattern, ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic key"),
)


def run_succeeded(turns: list[Any]) -> bool:
    """Return whether the execution stream ends in a successful result envelope.

    The heading a summary publishes is a claim about the run, not only about the text.
    A reviewer that hits the turn limit or errors after emitting text still produces a
    result turn -- carrying ``is_error: true`` or a non-success subtype, and often a
    diagnostic string where the report would be. So an envelope without a subtype is
    *unknown*, not successful: it says no more than no envelope does.
    """
    # Exactly one envelope, as this repository's native adapter requires ("No unique
    # successful Claude result"). With two, the status came from one and the text
    # could come from another, so an error diagnostic followed by an empty success
    # was published as a finished review.
    results = [t for t in turns if isinstance(t, dict) and t.get("type") == "result"]
    if len(results) != 1:
        return False
    (only,) = results
    # And it ends the stream. The pinned action breaks on the first result, so a real
    # execution file never has a turn after it; one that does is not what the action
    # writes, and its status cannot be trusted.
    if turns[-1] is not only:
        return False
    # `is False`, not falsiness: a missing, null or zero flag is the absence of a
    # failure signal, which is exactly what the rule above refuses.
    return only.get("is_error") is False and only.get("subtype") == "success"


def final_report(turns: list[Any]) -> tuple[str, bool]:
    """Return the reviewer's final text, and whether the run that produced it finished.

    The two travel together because the caller cannot recover the second from the
    first: a diagnostic and a report are both non-empty strings.
    """
    complete = run_succeeded(turns)
    for turn in reversed(turns):
        result = _result_text(turn)
        if result:
            return result, complete
    # Fall back to the last assistant text block -- the assistant's, and only its
    # text blocks. Any turn with message text used to qualify, so a user or tool
    # turn's text, which is the reviewer's *input*, could be published as its report.
    for turn in reversed(turns):
        texts = _assistant_texts(turn)
        if texts:
            return "\n".join(texts), complete
    return "", complete


def _result_text(turn: Any) -> str:
    """The non-blank result string of a result turn, or "" for anything else.

    A result turn carrying an empty string is not a report. Returning it shadowed real
    assistant text and published "the reviewer produced no final text".
    """
    if not isinstance(turn, dict) or turn.get("type") != "result":
        return ""
    result = turn.get("result")
    return result if isinstance(result, str) and result.strip() else ""


def _assistant_texts(turn: Any) -> list[str]:
    """The text blocks of an assistant turn, and nothing from any other turn."""
    if not isinstance(turn, dict) or turn.get("type") != "assistant":
        return []
    message = turn.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return []
    return [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]


def read_report(execution_file: pathlib.Path) -> AgentReport:
    """Return the report the execution file holds, or an unavailable one saying why."""
    try:
        # Checked before the parse. The report is bounded later, but the whole
        # execution file is materialised first, so an oversized one would consume
        # runner memory before any bound applied -- a bound that arrives after the cost
        # is not a bound.
        size = execution_file.stat().st_size
        if size > MAX_EXECUTION_BYTES:
            return unavailable(
                f"The execution output is too large to publish safely "
                f"({size} bytes, limit {MAX_EXECUTION_BYTES}). The job's logs hold it."
            )
        turns = json.loads(execution_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return unavailable(f"Could not read the execution output: {error}")
    if not isinstance(turns, list):
        return unavailable("The execution output was not a list of turns.")
    report, complete = final_report(turns)
    if not report.strip():
        return unavailable("The reviewer produced no final text.")
    return AgentReport("complete" if complete else "incomplete", report, False)
