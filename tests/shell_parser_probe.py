"""Parse shell text with the pinned tree-sitter pair, in a process of its own.

The compatibility smoke runs this as a child, so a native crash in the parser fails
the test that asked, rather than the test runner (Decision 0108). It reads a JSON
list of scripts on standard input and writes the grammar's ABI and, for each script,
the command names it found, whether the tree holds an error or a missing node, and the
here-document bodies.
"""

from __future__ import annotations

import json
import sys

import tree_sitter_bash
from tree_sitter import Language, Parser

LANGUAGE = Language(tree_sitter_bash.language())
# The most this child reads, in characters: the parent's bound, which the smoke pins
# equal, so the child stays bounded whoever writes to it (Amazon Q on #396).
INPUT_LIMIT = 16_777_216  # 16 MiB


def facts(source: bytes) -> dict[str, object]:
    """What one script's tree holds, walked iteratively."""
    tree = Parser(LANGUAGE).parse(source)
    names: list[str] = []
    bodies: list[str] = []
    errors = 0
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.is_error or node.is_missing:
            errors += 1
        if node.type == "command_name" and node.text is not None:
            names.append(node.text.decode("utf-8", "replace"))
        if node.type == "heredoc_body" and node.text is not None:
            bodies.append(node.text.decode("utf-8", "replace"))
        # Reversed, so the walk visits nodes in source order (CodeAnt on #394).
        stack.extend(reversed(node.children))
    return {"names": sorted(names), "errors": errors, "heredocs": bodies}


def main() -> int:
    # Standard input is the test's own `json.dumps`; anything else fails this child,
    # which the test reports with its standard error.
    payload = sys.stdin.read(INPUT_LIMIT + 1)
    if len(payload) > INPUT_LIMIT:
        sys.stderr.write("an input beyond the probe's input bound\n")
        return 2
    try:
        scripts = json.loads(payload)
    # JSON nested past the decoder's recursion limit raises `RecursionError`, and an
    # integer past Python's digit limit `ValueError`, the parent of
    # `JSONDecodeError`; each is refused the same way (cubic and CodeAnt on #396).
    except (ValueError, RecursionError):
        scripts = None
    if not isinstance(scripts, list) or not all(isinstance(s, str) for s in scripts):
        sys.stderr.write("the probe expects a JSON list of strings\n")
        return 2
    json.dump(
        {
            "abi": LANGUAGE.abi_version,
            "facts": [facts(script.encode("utf-8")) for script in scripts],
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
