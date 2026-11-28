"""Targeted-mutant table schema, anchor engine, and check gate (Decision 0104, #373).

A targeted mutant is a named code change that a named test must kill, such as "a
link is followed". Tables of them live with the code they guard, as
`tests/mutants/*.yaml`, and this module is their one owner:

- `check` confirms that every anchor applies exactly once and that every mutated
  Python file still compiles, refusing a mutant whose path passes through a symbolic
  link as `REFUSED`.
- In a Python file, an anchor that parses is located by AST (expression, statement, or
  run of consecutive statements within one block). Any other anchor, and any other
  file, is located by token sequence with whitespace ignored.
- A replacement is dedented, and its later lines keep their indentation relative to
  its first, starting from the indentation of the line where the match starts.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tools.knowledge_common import KnowledgeFormatError, load_yaml

_TOKEN = re.compile(r"\w+|[^\w\s]")
_LINE_END = re.compile(r"\r\n|\r|\n")
# How a node's source span is computed, and how a table problem is raised.
Span = Callable[[ast.AST, ast.AST], tuple[int, int]]
Refuse = Callable[[str], KnowledgeFormatError]
_MODULE = re.compile(r"\A[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\Z", re.ASCII)
_MUTANT_KEYS = frozenset({"name", "path", "find", "replace"})
_TABLE_KEYS = frozenset({"id", "tests", "mutants"})


class AnchorError(ValueError):
    """A mutant's anchor does not apply exactly once: ``status`` says how."""

    def __init__(self, status: str, detail: str) -> None:
        self.status = status
        super().__init__(f"{status}: {detail}")


@dataclass(frozen=True)
class Mutant:
    name: str
    path: str
    find: str
    replace: str

    @property
    def python(self) -> bool:
        return self.path.endswith(".py")


@dataclass(frozen=True)
class Table:
    id: str
    tests: tuple[str, ...]
    mutants: tuple[Mutant, ...]


@dataclass(frozen=True)
class Outcome:
    name: str
    status: str
    detail: str


def load_table(path: Path) -> Table:
    """Return the mutant table at ``path``, or raise `KnowledgeFormatError`."""
    document = load_yaml(path)

    def refuse(problem: str) -> KnowledgeFormatError:
        return KnowledgeFormatError(f"{path}: {problem}")

    # Names are strings: keys of two types made sorting them raise (CodeAnt on #374).
    if not isinstance(document, dict) or not all(isinstance(k, str) for k in document):
        raise refuse("a table must be a mapping of names")
    if set(document) - _TABLE_KEYS:
        raise refuse(f"unknown keys {sorted(set(document) - _TABLE_KEYS)}")
    table_id = document.get("id")
    if not isinstance(table_id, str) or not table_id:
        raise refuse("id must be a non-empty string")
    return Table(
        table_id,
        _tests(document.get("tests"), refuse),
        _mutants(document.get("mutants"), refuse),
    )


def _tests(tests: object, refuse: Refuse) -> tuple[str, ...]:
    if (
        not isinstance(tests, list)
        or not tests
        or not all(isinstance(t, str) and _MODULE.fullmatch(t) for t in tests)
    ):
        raise refuse("tests must be a non-empty list of test module names")
    return tuple(tests)


def _mutants(raw: object, refuse: Refuse) -> tuple[Mutant, ...]:
    if not isinstance(raw, list) or not raw:
        raise refuse("mutants must be a non-empty list")
    mutants = [
        _mutant(item, f"mutant {index}", refuse) for index, item in enumerate(raw)
    ]
    names = [m.name for m in mutants]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise refuse(f"mutant names used twice: {repeated}")
    return tuple(mutants)


def _mutant(item: object, where: str, refuse: Refuse) -> Mutant:
    if not isinstance(item, dict) or set(item) != _MUTANT_KEYS:
        raise refuse(f"{where} must have exactly {sorted(_MUTANT_KEYS)}")
    if not all(isinstance(item[key], str) for key in _MUTANT_KEYS):
        raise refuse(f"{where}: every field must be a string")
    if not item["name"] or not item["find"].strip():
        raise refuse(f"{where}: name and find must not be empty")
    relative = PurePosixPath(item["path"])
    # Checked as POSIX, a backslash or a drive would be read natively elsewhere
    # (CodeAnt on #374).
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
        or any(c in item["path"] for c in "\\:")
    ):
        raise refuse(f"{where}: path must stay inside the root: {item['path']!r}")
    return Mutant(item["name"], item["path"], item["find"], item["replace"])


def _offset(lines: list[str], starts: list[int], lineno: int, column: int) -> int:
    """The character offset of an AST position: its column counts UTF-8 bytes."""
    line = lines[lineno - 1]
    return starts[lineno - 1] + len(line.encode("utf-8")[:column].decode("utf-8"))


def _python_spans(text: str, find: str) -> tuple[list[tuple[int, int]], bool] | None:
    """Locate ``find`` in ``text`` by AST; None when either does not parse.

    The flag says whether the match is a run of statements, which a replacement must
    re-indent, rather than an expression.
    """
    try:
        tree = ast.parse(text)
        snippet = ast.parse(textwrap.dedent(find).strip("\n"))
    except SyntaxError:
        return None
    if not snippet.body:
        return None
    # Lines as Python counts them: `str.splitlines` also breaks at a form feed.
    lines = io.StringIO(text, newline="").readlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def span(first: ast.AST, last: ast.AST) -> tuple[int, int]:
        # A definition starts at its first decorator, at the definition's own column.
        decorators = getattr(first, "decorator_list", None)
        line = decorators[0].lineno if decorators else first.lineno  # type: ignore[attr-defined]  # ast.AST base lacks lineno
        return (
            _offset(lines, starts, line, first.col_offset),  # type: ignore[attr-defined]  # ast.AST base lacks col_offset
            _offset(lines, starts, last.end_lineno, last.end_col_offset),  # type: ignore[attr-defined]  # ast.AST base lacks end_lineno/end_col_offset
        )

    body = snippet.body
    if len(body) == 1 and isinstance(body[0], ast.Expr):
        return _expression_spans(text, tree, body[0].value, span), False
    return _statement_spans(tree, body, span), True


def _expression_spans(
    text: str, tree: ast.AST, wanted: ast.expr, span: Span
) -> list[tuple[int, int]]:
    """Every expression in ``tree`` equal to ``wanted`` whose own source is that
    expression.

    A node can equal ``wanted`` while its text is something else: the fragment
    `foo` of `f"foo{bar}"` is the string `'foo'`, without the quotes. Replacing it
    would put quotes into the f-string (Codex on #374). So a candidate's text must
    parse back to ``wanted``.
    """
    shape = ast.dump(wanted)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.expr) or ast.dump(node) != shape:
            continue
        start, end = span(node, node)
        if _parses_as(text[start:end], shape):
            found.append((start, end))
    return found


def _parses_as(source: str, shape: str) -> bool:
    """Whether ``source`` is, by itself, the expression ``shape`` dumps."""
    try:
        # Parenthesized, so an expression that spans lines still parses.
        parsed = ast.parse(f"({source})", mode="eval")
    except SyntaxError:
        return False
    return ast.dump(parsed.body) == shape


def _blocks(tree: ast.AST) -> list[list[ast.stmt]]:
    """Every block of statements in ``tree``: bodies, else branches, finally blocks."""
    found = []
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                found.append(block)
    return found


def _statement_spans(
    tree: ast.AST, wanted: list[ast.stmt], span: Span
) -> list[tuple[int, int]]:
    """Every run of consecutive statements, within one block, equal to ``wanted``."""
    shapes = [ast.dump(statement) for statement in wanted]
    found = []
    for block in _blocks(tree):
        for i in range(len(block) - len(wanted) + 1):
            if [ast.dump(s) for s in block[i : i + len(wanted)]] == shapes:
                found.append(span(block[i], block[i + len(wanted) - 1]))
    return found


def _token_spans(text: str, find: str) -> list[tuple[int, int]]:
    """Locate ``find`` in ``text`` by its sequence of tokens, whitespace ignored."""
    tokens = list(_TOKEN.finditer(text))
    wanted = _TOKEN.findall(find)
    if not wanted:
        return []
    found = []
    for i in range(len(tokens) - len(wanted) + 1):
        if tokens[i].group() != wanted[0]:
            continue
        if all(tokens[i + j].group() == wanted[j] for j in range(1, len(wanted))):
            found.append((tokens[i].start(), tokens[i + len(wanted) - 1].end()))
    return found


_NOT_FOUND = "NOT FOUND"


def apply(text: str, find: str, replace: str, *, python: bool) -> str:
    """Return ``text`` with the one place ``find`` names replaced by ``replace``.

    Raises `AnchorError` with status `NOT FOUND`, `AMBIGUOUS` or `INVALID`.
    """
    located = _python_spans(text, find) if python else None
    if located is None:
        spans, statements = _token_spans(text, find), False
    else:
        spans, statements = located
    if not spans:
        raise AnchorError(_NOT_FOUND, "the anchor matches nowhere")
    if len(spans) > 1:
        raise AnchorError("AMBIGUOUS", f"the anchor matches {len(spans)} places")
    start, end = spans[0]
    # Lines end as Python reads them, at `\r\n`, `\r` or `\n`: a CR-only file has no
    # `\n` at all (Codex on #374).
    line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
    # The matched line's own ending, since a file may mix them (Codex on #374).
    ending = _LINE_END.search(text, start) or _LINE_END.search(text)
    eol = ending.group() if ending else "\n"
    indent = re.match(r"[ \t]*", text[line_start:start]).group()  # type: ignore[union-attr]  # [ \t]* always matches at start of string
    lines = textwrap.dedent(replace).strip("\n").splitlines()
    if statements and not lines:
        lines = ["pass"]
    # A statement after other code on its line, as in `if flag: x = 1`, has no
    # indentation of its own; later lines would leave its suite (CodeAnt on #374).
    if statements and len(lines) > 1 and text[line_start:start].strip():
        raise AnchorError(
            "INVALID",
            "a multi-line replacement of a statement that does not begin its line",
        )
    return text[:start] + (eol + indent).join(lines).rstrip() + text[end:]


def _compiles(text: str, path: str) -> str | None:
    """Why a mutated Python file does not compile, or None if it does."""
    try:
        compile(text, path, "exec")
    except SyntaxError as exc:
        return f"{path}: {exc.msg}"
    return None


def _linked(root: Path, relative: str) -> str | None:
    """The first part of ``relative`` under ``root`` that is a symbolic link, if any."""
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            return current.relative_to(root).as_posix()
    return None


def _mutated(root: Path, mutant: Mutant) -> str | Outcome:
    """``mutant``'s file under ``root`` with the mutant applied, or why it does not
    apply: `REFUSED`, `NOT FOUND`, `AMBIGUOUS` or `INVALID`."""
    linked = _linked(root, mutant.path)
    if linked is not None:
        return Outcome(mutant.name, "REFUSED", f"{linked} is a symbolic link")
    try:
        # Line endings are kept as they are: a test may read the bytes (CodeAnt on
        # #374).
        with (root / mutant.path).open(encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        # Tables name UTF-8 files; another encoding is reported, not raised (CodeAnt
        # on #374).
        reason = f"cannot read {mutant.path} as UTF-8: {exc.reason}"
        return Outcome(mutant.name, _NOT_FOUND, reason)
    except OSError as exc:
        return Outcome(mutant.name, _NOT_FOUND, f"cannot read {mutant.path}: {exc}")
    try:
        mutated = apply(text, mutant.find, mutant.replace, python=mutant.python)
    except AnchorError as exc:
        return Outcome(mutant.name, exc.status, mutant.path)
    broken = _compiles(mutated, mutant.path) if mutant.python else None
    if broken:
        return Outcome(mutant.name, "INVALID", broken)
    return mutated


def check(root: Path, table: Table) -> list[str]:
    """Return one line for each mutant of ``table`` that does not apply under ``root``."""
    # A missing root is a usage error, as for `run`, not missing anchors (CodeAnt on
    # #374).
    if not root.is_dir():
        raise ValueError(f"the root is not a directory: {root}")
    problems = []
    for mutant in table.mutants:
        result = _mutated(root, mutant)
        if isinstance(result, Outcome):
            problems.append(f"{result.name}: {result.status} ({result.detail})")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="knowledge mutants",
        description="Check a table of targeted mutants (Decision 0104).",
    )
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="only check every anchor")
    args = parser.parse_args(argv)
    if not args.check:
        print("mutants: --check is required in slice 1")
        return 2
    try:
        table = load_table(args.table)
        problems = check(args.root, table)
    except ValueError as exc:  # a KnowledgeFormatError, or a bad --root
        print(f"mutants: {exc}")
        return 2
    for problem in problems:
        print(problem)
    applying = len(table.mutants) - len(problems)
    print(f"anchors: {applying} of {len(table.mutants)} apply")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
