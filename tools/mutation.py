"""Run targeted mutants from one owner (Decision 0104, #373).

A targeted mutant is a named code change that a named test must kill, such as "a
link is followed". Tables of them live with the code they guard, as
`tests/mutants/*.yaml`, and this module is their one runner:

- `check` confirms that every anchor applies exactly once and that every mutated
  Python file still compiles. `tests/test_mutant_tables.py` runs it over every table,
  so an anchor a refactor breaks fails in the `fast` profile.
- `run` first runs the table's tests unmutated, in an isolated copy of the root. Only if
  they pass does a failure mean anything: otherwise every mutant is `NOT RUN`. It then
  applies each mutant in its own isolated copy and runs the tests there. A mutant is
  `KILLED` when they fail or time out, and `SURVIVED` when they pass. A timeout ends
  the tests' whole process group.
- `check` and `run` both refuse a mutant whose path passes through a symbolic link,
  as `REFUSED`: writing through it would change a file outside the copy.

Anchors survive reformatting:

- In a Python file, an anchor that parses is located by AST. It is either an
  expression, or a statement or run of consecutive statements within one block, so
  whitespace, line breaks and comments do not matter. A decorated definition's
  statement includes its decorators.
- Any other anchor, and any other file, is located by token sequence: runs of word
  characters and single punctuation marks, with whitespace ignored.
- A replacement is dedented, and its later lines keep their indentation relative to
  its first, starting from the indentation of the line where the match starts. It
  fits a reflowed file whose structure follows relative indentation, as YAML's does,
  but it keeps the table's indentation width, not the file's.

Extend this module, and its tests in `tests/test_mutation.py`; do not write another
mutation runner.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import contextlib
import math
import os
import re
import shutil
import signal
import subprocess  # nosec B404
import sys
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tools.knowledge_common import KnowledgeFormatError, load_yaml

DEFAULT_TIMEOUT = 300.0
# How much of the end of the tests' output an outcome reports from.
_OUTPUT_TAIL_BYTES = 4096
_TOKEN = re.compile(r"\w+|[^\w\s]")
# How a node's source span is computed, and how a table problem is raised.
Span = Callable[[ast.AST, ast.AST], tuple[int, int]]
Refuse = Callable[[str], KnowledgeFormatError]
_MODULE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_MUTANT_KEYS = frozenset({"name", "path", "find", "replace"})
_TABLE_KEYS = frozenset({"id", "tests", "mutants"})
_CACHES = shutil.ignore_patterns(
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".venv",
    "venv",
)


def _ignored(directory: str, names: list[str]) -> set[str]:
    """What an isolated copy leaves out: caches, and any `.git` that is not a directory.

    A copy keeps the repository's own Git metadata, so tests that read Git see what
    they would see in place; without it they fail in every copy, and every mutant
    looks killed. A `.git` file points at metadata other worktrees share, which a copy
    must never write to, so it is left out, and such tests fail the baseline instead.
    """
    ignored = set(_CACHES(directory, names))
    git = os.path.join(directory, ".git")
    if ".git" in names and (os.path.islink(git) or not os.path.isdir(git)):
        ignored.add(".git")
    return ignored


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
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
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
    lines = text.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def span(first: ast.AST, last: ast.AST) -> tuple[int, int]:
        # A definition starts at its first decorator, at the definition's own column.
        decorators = getattr(first, "decorator_list", None)
        line = decorators[0].lineno if decorators else first.lineno  # type: ignore[attr-defined]
        return (
            _offset(lines, starts, line, first.col_offset),  # type: ignore[attr-defined]
            _offset(lines, starts, last.end_lineno, last.end_col_offset),  # type: ignore[attr-defined]
        )

    body = snippet.body
    if len(body) == 1 and isinstance(body[0], ast.Expr):
        return _expression_spans(tree, body[0].value, span), False
    return _statement_spans(tree, body, span), True


def _expression_spans(
    tree: ast.AST, wanted: ast.expr, span: Span
) -> list[tuple[int, int]]:
    """Every expression in ``tree`` equal to ``wanted``."""
    shape = ast.dump(wanted)
    return [
        span(node, node)
        for node in ast.walk(tree)
        if isinstance(node, ast.expr) and ast.dump(node) == shape
    ]


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


def apply(text: str, find: str, replace: str, *, python: bool) -> str:
    """Return ``text`` with the one place ``find`` names replaced by ``replace``.

    Raises `AnchorError` with status `NOT FOUND` or `AMBIGUOUS`.
    """
    located = _python_spans(text, find) if python else None
    if located is None:
        spans, statements = _token_spans(text, find), False
    else:
        spans, statements = located
    if not spans:
        raise AnchorError("NOT FOUND", "the anchor matches nowhere")
    if len(spans) > 1:
        raise AnchorError("AMBIGUOUS", f"the anchor matches {len(spans)} places")
    start, end = spans[0]
    line_start = text.rfind("\n", 0, start) + 1
    indent = re.match(r"[ \t]*", text[line_start:start]).group()  # type: ignore[union-attr]
    lines = textwrap.dedent(replace).strip("\n").splitlines()
    if statements and not lines:
        lines = ["pass"]
    return text[:start] + ("\n" + indent).join(lines).rstrip() + text[end:]


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


def check(root: Path, table: Table) -> list[str]:
    """Return one line for each mutant of ``table`` that does not apply under ``root``."""
    problems = []
    for mutant in table.mutants:
        linked = _linked(root, mutant.path)
        if linked is not None:
            problems.append(f"{mutant.name}: REFUSED ({linked} is a symbolic link)")
            continue
        try:
            text = (root / mutant.path).read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(
                f"{mutant.name}: NOT FOUND (cannot read {mutant.path}: {exc})"
            )
            continue
        try:
            mutated = apply(text, mutant.find, mutant.replace, python=mutant.python)
        except AnchorError as exc:
            problems.append(f"{mutant.name}: {exc.status} ({mutant.path})")
            continue
        broken = _compiles(mutated, mutant.path) if mutant.python else None
        if broken:
            problems.append(f"{mutant.name}: INVALID ({broken})")
    return problems


def _run_tests(
    work: Path, scratch: str, tests: tuple[str, ...], timeout: float
) -> tuple[int | None, str]:
    """Run ``tests`` in ``work``: their exit status, None on timeout, and last line.

    The tests run in a new session, and their whole process group is killed when
    they end, so a child they leave behind dies with them. Their output goes to a
    file, so such a child cannot hold a pipe open.
    """
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": scratch,
        "LC_ALL": "C.UTF-8",
        "PYTHONPATH": str(work),
        "KNOWLEDGE_KIT_ROOT": str(work),
    }
    output = Path(scratch) / "tests.log"
    with output.open("wb") as log:
        process = subprocess.Popen(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, "-m", "unittest", *tests],
            cwd=work,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            status: int | None = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            status = None
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    with output.open("rb") as log:
        log.seek(max(0, output.stat().st_size - _OUTPUT_TAIL_BYTES))
        tail = log.read().decode("utf-8", errors="replace")
    return status, (tail.strip().splitlines() or [""])[-1]


def _copy(root: Path, scratch: str) -> Path:
    work = Path(scratch) / "w"
    shutil.copytree(root, work, ignore=_ignored, symlinks=True)
    return work


def _baseline(root: Path, table: Table, timeout: float) -> str | None:
    """Why the table's tests fail without any mutant, or None when they pass."""
    with tempfile.TemporaryDirectory(prefix="gnostoa-mutant-") as scratch:
        status, last = _run_tests(_copy(root, scratch), scratch, table.tests, timeout)
    if status is None:
        last = f"timed out after {timeout:g} s"
    return None if status == 0 else f"the unmutated tests fail: {last}"


def _run_one(root: Path, table: Table, mutant: Mutant, timeout: float) -> Outcome:
    """Apply ``mutant`` in an isolated copy of ``root`` and run the table's tests."""
    with tempfile.TemporaryDirectory(prefix="gnostoa-mutant-") as scratch:
        work = _copy(root, scratch)
        linked = _linked(work, mutant.path)
        if linked is not None:
            return Outcome(mutant.name, "REFUSED", f"{linked} is a symbolic link")
        target = work / mutant.path
        try:
            mutated = apply(
                target.read_text(encoding="utf-8"),
                mutant.find,
                mutant.replace,
                python=mutant.python,
            )
        except (AnchorError, OSError) as exc:
            return Outcome(mutant.name, getattr(exc, "status", "NOT FOUND"), str(exc))
        broken = _compiles(mutated, mutant.path) if mutant.python else None
        if broken:
            return Outcome(mutant.name, "INVALID", broken)
        target.write_text(mutated, encoding="utf-8")
        status, last = _run_tests(work, scratch, table.tests, timeout)
    if status is None:
        return Outcome(mutant.name, "KILLED", f"timed out after {timeout:g} s")
    if status == 0:
        return Outcome(mutant.name, "SURVIVED", "the tests passed")
    return Outcome(mutant.name, "KILLED", last)


def run(
    root: Path,
    table: Table,
    *,
    jobs: int = 1,
    timeout: float = DEFAULT_TIMEOUT,
    only: tuple[str, ...] = (),
) -> list[Outcome]:
    """Run ``table``'s mutants, or those named in ``only``, in ``jobs`` workers.

    The unmutated baseline runs alongside them. When it fails, a failure says
    nothing about a mutant, so every mutant that ran is `NOT RUN` instead.
    """
    if not (math.isfinite(timeout) and timeout > 0):
        raise ValueError(f"timeout must be a positive number of seconds: {timeout!r}")
    known = {m.name for m in table.mutants}
    unknown = sorted(set(only) - known)
    if unknown:
        raise KnowledgeFormatError(f"{table.id} has no mutant named {unknown}")
    selected = [m for m in table.mutants if not only or m.name in only]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        baseline = pool.submit(_baseline, root, table, timeout)
        outcomes = list(
            pool.map(lambda mutant: _run_one(root, table, mutant, timeout), selected)
        )
    failure = baseline.result()
    if failure is None:
        return outcomes
    return [
        Outcome(o.name, "NOT RUN", failure) if o.status in {"KILLED", "SURVIVED"} else o
        for o in outcomes
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="knowledge mutants",
        description="Check or run a table of targeted mutants (Decision 0104).",
    )
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="only check every anchor")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("names", nargs="*", help="run only these mutants")
    args = parser.parse_args(argv)
    try:
        table = load_table(args.table)
        if args.check:
            problems = check(args.root, table)
            for problem in problems:
                print(problem)
            applying = len(table.mutants) - len(problems)
            print(f"anchors: {applying} of {len(table.mutants)} apply")
            return 1 if problems else 0
        outcomes = run(
            args.root,
            table,
            jobs=args.jobs,
            timeout=args.timeout,
            only=tuple(args.names),
        )
    except (KnowledgeFormatError, ValueError) as exc:
        print(f"mutants: {exc}")
        return 2
    for outcome in outcomes:
        detail = "" if outcome.status == "KILLED" else f" ({outcome.detail})"
        print(f"{outcome.status:<9} {outcome.name}{detail}")
    killed = sum(outcome.status == "KILLED" for outcome in outcomes)
    print(f"mutants: {killed} of {len(outcomes)} killed")
    return 0 if killed == len(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
