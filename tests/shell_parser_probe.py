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
        stack.extend(node.children)
    return {"names": sorted(names), "errors": errors, "heredocs": bodies}


def main() -> int:
    # Standard input is the test's own `json.dumps`; anything else fails this child,
    # which the test reports with its standard error.
    scripts = json.load(sys.stdin)
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
