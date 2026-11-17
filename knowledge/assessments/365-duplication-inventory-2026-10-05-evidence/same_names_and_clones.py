"""Detectors A and B of the 2026-10-05 duplication inventory (#365).

Run: python same_names_and_clones.py <root> [--counts], where <root> is an extracted
`git archive 4618e1b`. With CPython 3.14.7 it prints, byte for byte, the JSON recorded
in same-names-and-clones.json. Under 3.12 the similarity ratios differ, because
`ast.dump`'s format changed in 3.13; the clone groups do not.

The JSON lists at most 45 same-name groups, 30 clone groups and 40 near clones. With
`--counts` it prints instead how many there are in all, as recorded in
same-names-and-clones-counts.json (Codex on #375).

- A: top-level functions with one name in two or more modules, with the best and
  mean similarity of their normalized bodies.
- B: exact structural clones: identical normalized bodies, of at least five
  statements, in two or more modules.
- B': near clones: at least 0.90 similar, of at least eight statements, in two
  modules, with different bodies.

Normalizing replaces every identifier and constant, and drops annotations,
decorators and a leading docstring, so only the shape remains.
"""

import ast
import collections
import difflib
import itertools
import json
import pathlib
import sys
from typing import Any

# (module, name, statements, source, normalized dump)
Function = tuple[str, str, int, str, str]


class Normalize(ast.NodeTransformer):
    """Replace identifiers and constants so only the shape remains."""

    @staticmethod
    def visit_Name(node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    @staticmethod
    def visit_arg(node: ast.arg) -> ast.AST:
        node.arg = "_"
        node.annotation = None
        return node

    @staticmethod
    def visit_Constant(node: ast.Constant) -> ast.AST:
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        node.name = "_"
        node.returns = None
        node.decorator_list = []
        first = node.body[0] if node.body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            node.body = node.body[1:] or [ast.Pass()]
        self.generic_visit(node)
        return node


def functions_of(root: pathlib.Path) -> list[Function]:
    """Every top-level function of the production modules under ``root``."""
    files = sorted(
        p for d in ("tools", "ci", "tasks", ".github") for p in (root / d).rglob("*.py")
    )
    found: list[Function] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        rel = path.relative_to(root).as_posix()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stmts = sum(1 for n in ast.walk(node) if isinstance(n, ast.stmt)) - 1
                source = ast.get_source_segment(text, node) or ""
                norm = (
                    ast.dump(Normalize().visit(ast.parse(source).body[0]))
                    if source
                    else ""
                )
                found.append((rel, node.name, stmts, source, norm))
    return found


def same_names(functions: list[Function]) -> list[Any]:
    """Detector A."""
    by_name: dict[str, list[Function]] = collections.defaultdict(list)
    for f in functions:
        by_name[f[1]].append(f)
    rows: list[Any] = []
    for name, group in by_name.items():
        modules = {g[0] for g in group}
        if len(modules) < 2:
            continue
        sims = [
            difflib.SequenceMatcher(None, a[4], b[4]).ratio()
            for a, b in itertools.combinations(group, 2)
        ]
        rows.append(
            (
                name,
                len(modules),
                round(max(sims), 2),
                round(sum(sims) / len(sims), 2),
                sorted(modules),
            )
        )
    rows.sort(key=lambda r: (-r[1], -r[2]))
    return rows


def exact_clones(functions: list[Function]) -> list[Any]:
    """Detector B."""
    by_shape: dict[str, list[Function]] = collections.defaultdict(list)
    for f in functions:
        if f[2] >= 5:
            by_shape[f[4]].append(f)
    rows: list[Any] = []
    for group in by_shape.values():
        modules = {g[0] for g in group}
        if len(modules) >= 2:
            rows.append((len(modules), group[0][2], [f"{g[0]}::{g[1]}" for g in group]))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    return rows


def near_clones(functions: list[Function]) -> list[Any]:
    """Detector B'."""
    big = [f for f in functions if f[2] >= 8]
    rows: list[Any] = []
    for a, b in itertools.combinations(big, 2):
        if a[0] == b[0] or a[4] == b[4]:
            continue
        if abs(len(a[4]) - len(b[4])) > 0.15 * max(len(a[4]), len(b[4])):
            continue
        if difflib.SequenceMatcher(None, a[4], b[4]).quick_ratio() < 0.9:
            continue
        r = difflib.SequenceMatcher(None, a[4], b[4]).ratio()
        if r >= 0.9:
            rows.append((round(r, 2), a[2], f"{a[0]}::{a[1]}", f"{b[0]}::{b[1]}"))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    return rows


def main() -> None:
    functions = functions_of(pathlib.Path(sys.argv[1]))
    if sys.argv[2:] == ["--counts"]:
        names = same_names(functions)
        counts = {
            "functions": len(functions),
            "same_name_groups": len(names),
            "same_name_groups_at_least_0_90_similar": sum(r[2] >= 0.9 for r in names),
            "exact_clone_groups": len(exact_clones(functions)),
            "near_clone_pairs": len(near_clones(functions)),
        }
        print(json.dumps(counts, indent=1))
        return
    print(
        json.dumps(
            {
                "functions": len(functions),
                "same_name": same_names(functions)[:45],
                "exact_clones": exact_clones(functions)[:30],
                "near_clones": near_clones(functions)[:40],
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
