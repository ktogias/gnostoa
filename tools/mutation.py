"""Run targeted mutants from one owner (Decision 0104, #373).

A targeted mutant is a named code change that a named test must kill, such as "a
link is followed". Tables of them live with the code they guard, as
`tests/mutants/*.yaml`, and this module is their one runner:

- `check` confirms that every anchor applies exactly once and that every mutated
  Python file still compiles. `tests/test_mutant_tables.py` runs it over every table,
  so an anchor a refactor breaks fails in the `fast` profile.
- `run` first runs the table's tests unmutated, in isolated copies of the root, as
  many at once as the mutants will run. Only if every copy passes does a failure mean
  anything: otherwise no mutant runs, and each that applies is `NOT RUN`. It then
  applies each mutant in its own isolated copy and runs the tests there. A mutant is
  `KILLED` when they fail or time out, and `SURVIVED` when they pass. A timeout ends
  the tests' whole process group.
- `check` and `run` both refuse a mutant whose path passes through a symbolic link,
  as `REFUSED`: writing through it would change a file outside the copy.
- What the runner sets up stays in the copy. The tests themselves are not sandboxed;
  see below.
  - Every copy is taken from one snapshot of the root, made when the run starts. The
    snapshot is itself copied file by file, so an edit made during that copy can
    still mix; it narrows the window from the whole run to the copy.
  - A copy holding a link that resolves outside it is refused.
  - A copy's Git metadata keeps only the repository's format: no work tree, include,
    filter, hook or other program the repository configured. A copy that shares
    another repository's Git directory, or borrows its objects, is refused.
  - Output beyond a limit ends the tests, as a timeout does. The output is measured
    every `_POLL_SECONDS`, so a fast writer can pass the limit by what it writes in
    one interval before it is stopped.
- A copy that fails, or tests that cannot start, credit nothing: the mutant is
  `NOT RUN`.

What this does not do:
- It does not sandbox the tests. The owner confirmed this boundary on 2026-10-06. They
  run as the caller, with the caller's file-system access, as they do in place under
  `ci/verify`. The runner keeps its own writes, and Git, inside the copy. To bound
  what the tests can reach, run it as the publication flow does, in a container with
  the root mounted read-only (CodeAnt on #374).
- It runs on POSIX only. It starts the tests in a new session and ends their process
  group, which Windows has no equivalent of.

Anchors survive reformatting:

- In a Python file, an anchor that parses is located by AST. It is either an
  expression, or a statement or run of consecutive statements within one block, so
  whitespace, line breaks and comments do not matter. A decorated definition's
  statement includes its decorators.
- Any other anchor, and any other file, is located by token sequence: runs of word
  characters and single punctuation marks, with whitespace ignored. Tokens include
  comments and quoted text. So an anchor can match a commented-out copy of a setting.
  Beside the real one that match is `AMBIGUOUS`; alone, the mutant changes a comment
  and `SURVIVED` says so. Whitespace inside quoted text is ignored too, so an anchor
  can still match a literal that differs from it only there (CodeAnt on #374).
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
import io
import math
import os
import re
import shutil
import signal
import subprocess  # nosec B404
import sys
import tempfile
import textwrap
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tools.knowledge_common import KnowledgeFormatError, load_yaml

DEFAULT_TIMEOUT = 300.0
# How much of the end of the tests' output an outcome reports from.
_OUTPUT_TAIL_BYTES = 4096
# Output beyond this ends the tests, so a mutant that prints forever cannot fill the
# scratch file system (CodeAnt on #374). How often the size and the deadline are read.
_OUTPUT_LIMIT_BYTES = 16 * 1024 * 1024
# Runs the tests as `python -m unittest` does, once each test module is shown to come
# from the copy: a `tests` directory without `__init__.py` loses to a regular `tests`
# package later on the path, an installed one say (CodeAnt on #374).
_BOOTSTRAP = """\
import importlib, os, sys, unittest
root = os.path.realpath(os.getcwd())
for name in sys.argv[1:]:
    origin = os.path.realpath(importlib.import_module(name).__file__ or "")
    if os.path.commonpath([root, origin]) != root:
        sys.exit(f"{name} is not the copy's: {origin}")
unittest.main(module=None, argv=["python -m unittest", *sys.argv[1:]])
"""
_POLL_SECONDS = 0.2
_TOKEN = re.compile(r"\w+|[^\w\s]")
_LINE_END = re.compile(r"\r\n|\r|\n")
# How a node's source span is computed, and how a table problem is raised.
Span = Callable[[ast.AST, ast.AST], tuple[int, int]]
Refuse = Callable[[str], KnowledgeFormatError]
_MODULE = re.compile(r"\A[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\Z", re.ASCII)
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
    # Other repositories' metadata, a submodule's or a linked worktree's, keeps its
    # own configuration and hooks; the tests need the repository's own only (Codex
    # on #374).
    if os.path.basename(directory) == ".git":
        ignored |= {"modules", "worktrees"} & set(names)
    return ignored


class CopyRefused(Exception):
    """An isolated copy holds a link out of it, which its tests could write through."""


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
        line = decorators[0].lineno if decorators else first.lineno  # type: ignore[attr-defined]
        return (
            _offset(lines, starts, line, first.col_offset),  # type: ignore[attr-defined]
            _offset(lines, starts, last.end_lineno, last.end_col_offset),  # type: ignore[attr-defined]
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
        raise AnchorError("NOT FOUND", "the anchor matches nowhere")
    if len(spans) > 1:
        raise AnchorError("AMBIGUOUS", f"the anchor matches {len(spans)} places")
    start, end = spans[0]
    # Lines end as Python reads them, at `\r\n`, `\r` or `\n`: a CR-only file has no
    # `\n` at all (Codex on #374).
    line_start = max(text.rfind("\n", 0, start), text.rfind("\r", 0, start)) + 1
    # The matched line's own ending, since a file may mix them (Codex on #374).
    ending = _LINE_END.search(text, start) or _LINE_END.search(text)
    eol = ending.group() if ending else "\n"
    indent = re.match(r"[ \t]*", text[line_start:start]).group()  # type: ignore[union-attr]
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
        return Outcome(mutant.name, "NOT FOUND", reason)
    except OSError as exc:
        return Outcome(mutant.name, "NOT FOUND", f"cannot read {mutant.path}: {exc}")
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


def _run_tests(
    work: Path, scratch: str, tests: tuple[str, ...], timeout: float
) -> tuple[int | None, str]:
    """Run ``tests`` in ``work``: their exit status and their last line of output, or
    None and why they were stopped.

    The tests run in a new session, and their whole process group is killed when
    they end, so a child they leave behind dies with them. Their output goes to a
    file, so such a child cannot hold a pipe open. They are stopped at ``timeout``, or
    once their output passes `_OUTPUT_LIMIT_BYTES`.
    """
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": scratch,
        "LC_ALL": "C.UTF-8",
        "PYTHONPATH": str(work),
        "KNOWLEDGE_KIT_ROOT": str(work),
        # Git in the tests reads only the copy's reduced configuration: not the
        # host's system file, which could set hooks or filters (CodeAnt on #374).
        # With HOME a scratch directory, there is no global one either.
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    output = Path(scratch) / "tests.log"
    with output.open("wb") as log:
        process = subprocess.Popen(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, "-c", _BOOTSTRAP, *tests],
            cwd=work,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            status, stopped = _wait(process, log.fileno(), timeout)
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    if stopped is not None:
        return None, stopped
    with output.open("rb") as log:
        log.seek(max(0, output.stat().st_size - _OUTPUT_TAIL_BYTES))
        tail = log.read().decode("utf-8", errors="replace")
    return status, (tail.strip().splitlines() or [""])[-1]


def _wait(
    process: subprocess.Popen[bytes], log: int, timeout: float
) -> tuple[int | None, str | None]:
    """Wait for ``process``: its exit status, or why it must be stopped.

    The output is measured after every wait, the last one too: tests that wrote past
    the limit and exited within one poll were credited with their exit status (Codex
    on #374).
    """
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None, f"timed out after {timeout:g} s"
        try:
            status: int | None = process.wait(timeout=min(_POLL_SECONDS, remaining))
        except subprocess.TimeoutExpired:
            status = None
        if os.fstat(log).st_size > _OUTPUT_LIMIT_BYTES:
            return None, f"the tests wrote more than {_OUTPUT_LIMIT_BYTES} bytes"
        if status is not None:
            return status, None


def _copy(root: Path, scratch: str) -> Path:
    """An isolated copy of ``root``, its Git metadata reduced to the repository's
    format, or `CopyRefused` when a link in it, or a shared Git directory, leads out."""
    work = Path(scratch) / "w"
    shutil.copytree(root, work, ignore=_ignored, symlinks=True)
    escaping = _escaping_link(work)
    if escaping is not None:
        raise CopyRefused(f"the link {escaping} resolves outside the copy")
    _sanitize_git(work)
    return work


def _escaping_link(work: Path) -> str | None:
    """The first symbolic link in ``work`` that resolves outside it, if any.

    A copy keeps its links, and one leading out, such as an absolute link back into
    the original tree, would let the tests write there (CodeAnt on #374). Each is
    resolved in full, through any links it passes, since `..` after a link climbs
    from that link's target.
    """
    base = os.path.realpath(work)
    for directory, directories, files in os.walk(work):
        for name in (*directories, *files):
            path = os.path.join(directory, name)
            if os.path.islink(path):
                target = os.path.realpath(path)
                if os.path.commonpath([base, target]) != base:
                    return os.path.relpath(path, work)
    return None


# What a copy's `.git` configuration keeps: the repository's format, and nothing that
# routes Git elsewhere or runs a program.
_CORE_KEYS = frozenset(
    {
        "repositoryformatversion",
        "bare",
        "filemode",
        "logallrefupdates",
        "ignorecase",
        "symlinks",
        "precomposeunicode",
    }
)
_SECTION = re.compile(r'^\s*\[\s*([A-Za-z0-9.-]+)\s*(")?')
# A key with a simple value, quoted or not, or alone, which Git reads as true
# (CodeAnt on #374). Matched whole against the stripped line, so a run of spaces can
# be read only one way: two `\s*` around it backtracked quadratically (CodeRabbit on
# #374).
_SIMPLE = re.compile(r'([A-Za-z][A-Za-z0-9-]*)(?:\s*=\s*("?)([A-Za-z0-9._-]+)\2)?')


def _sanitize_git(work: Path) -> None:
    """Reduce every `.git` directory in ``work`` to the repository's format.

    A copy keeps the repository's `.git`, and Git run inside it read that metadata. A
    `core.worktree`, or one an `include` brought, made Git work on another tree, and a
    filter, a hook or `core.fsmonitor` ran a program (Codex on #374). So each copied
    configuration keeps only `[core]`'s format keys and `[extensions]` but
    `worktreeConfig`; the hooks and any per-worktree configuration are removed. A
    `commondir`, which shares another repository's directory, refuses the copy.
    """
    for directory, directories, _files in os.walk(work):
        if ".git" not in directories:
            continue
        git_dir = Path(directory) / ".git"
        if (git_dir / "commondir").exists():
            where = git_dir.relative_to(work) / "commondir"
            raise CopyRefused(f"{where} shares another repository's directory")
        # A clone made with --reference reads its objects from outside the copy
        # (Codex on #374).
        for name in ("alternates", "http-alternates"):
            borrowed = git_dir / "objects" / "info" / name
            if borrowed.is_file() and borrowed.read_text(errors="replace").strip():
                where = borrowed.relative_to(work)
                raise CopyRefused(f"{where} borrows objects from outside the copy")
        # A link or a file is unlinked, never followed: `rmtree` refuses a link,
        # and an ignored error left linked hooks in place (CodeAnt on #374).
        hooks = git_dir / "hooks"
        if hooks.is_symlink() or hooks.is_file():
            hooks.unlink()
        elif hooks.is_dir():
            shutil.rmtree(hooks)
        (git_dir / "config.worktree").unlink(missing_ok=True)
        config = git_dir / "config"
        if config.is_file():
            text = config.read_text(encoding="utf-8", errors="replace")
            # A new file, so a linked configuration is never written through.
            config.unlink()
            config.write_text(_format_config(text), encoding="utf-8")


def _format_config(text: str) -> str:
    """``text``'s format keys, as a configuration of their own."""
    kept: dict[str, list[str]] = {"core": [], "extensions": []}
    section: str | None = None
    for line in text.splitlines():
        header = _SECTION.match(line)
        if header:
            # A subsection, such as `[remote "origin"]`, keeps nothing.
            section = None if header.group(2) else header.group(1).lower()
            continue
        setting = _SIMPLE.fullmatch(line.strip())
        if setting is None or section not in kept:
            continue
        key = setting.group(1).lower()
        if (section == "core" and key in _CORE_KEYS) or (
            section == "extensions" and key != "worktreeconfig"
        ):
            kept[section].append(f"\t{key} = {setting.group(3) or 'true'}\n")
    return "".join(f"[{name}]\n" + "".join(rows) for name, rows in kept.items() if rows)


def _baseline(root: Path, table: Table, timeout: float) -> str | None:
    """Why the table's tests fail without any mutant, or None when they pass."""
    with tempfile.TemporaryDirectory(prefix="gnostoa-mutant-") as scratch:
        try:
            work = _copy(root, scratch)
        except CopyRefused as exc:
            return f"the copy is refused: {exc}"
        except OSError as exc:
            # A full disk is no verdict on the tests (CodeAnt on #374).
            return f"the copy failed: {exc}"
        try:
            status, last = _run_tests(work, scratch, table.tests, timeout)
        except OSError as exc:
            return f"the tests could not run: {exc}"
    return None if status == 0 else f"the unmutated tests fail: {last}"


def _run_one(root: Path, table: Table, mutant: Mutant, timeout: float) -> Outcome:
    """Apply ``mutant`` in an isolated copy of ``root`` and run the table's tests."""
    with tempfile.TemporaryDirectory(prefix="gnostoa-mutant-") as scratch:
        try:
            work = _copy(root, scratch)
        except CopyRefused as exc:
            return Outcome(mutant.name, "REFUSED", str(exc))
        except OSError as exc:
            return Outcome(mutant.name, "NOT RUN", f"the copy failed: {exc}")
        mutated = _mutated(work, mutant)
        if isinstance(mutated, Outcome):
            return mutated
        try:
            with (work / mutant.path).open("w", encoding="utf-8", newline="") as out:
                out.write(mutated)
            status, last = _run_tests(work, scratch, table.tests, timeout)
        except OSError as exc:
            return Outcome(mutant.name, "NOT RUN", f"the tests could not run: {exc}")
    if status is None:
        return Outcome(mutant.name, "KILLED", last)
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

    The unmutated baseline ends before any mutant starts, and runs as many copies at
    once as the mutants will. A suite that cannot share the machine with itself, such
    as one holding a fixed port or lock, then fails here rather than killing mutants
    it never detected (Codex on #374). When any copy fails, no mutant runs: each that
    applies is `NOT RUN`, and each that does not keeps its status.
    """
    if not (math.isfinite(timeout) and timeout > 0):
        raise ValueError(f"timeout must be a positive number of seconds: {timeout!r}")
    if not root.is_dir():
        raise ValueError(f"the root is not a directory: {root}")
    # The snapshot would be copied into the tree it copies (Codex on #374).
    scratch, top = Path(tempfile.gettempdir()).resolve(), root.resolve()
    if scratch == top or top in scratch.parents:
        raise ValueError(
            f"the temporary directory {scratch} is inside the root; set TMPDIR outside it"
        )
    known = {m.name for m in table.mutants}
    unknown = sorted(set(only) - known)
    if unknown:
        raise KnowledgeFormatError(f"{table.id} has no mutant named {unknown}")
    selected = [m for m in table.mutants if not only or m.name in only]
    with tempfile.TemporaryDirectory(prefix="gnostoa-snapshot-") as held:
        # Every copy is taken from one snapshot, so a root that changes during the run
        # cannot give the baseline and the mutants different subjects (Codex on #374).
        try:
            snapshot = _copy(root, held)
        except CopyRefused as exc:
            return [_static(root, m, f"the copy is refused: {exc}") for m in selected]
        except OSError as exc:
            return [_static(root, m, f"the copy failed: {exc}") for m in selected]
        return _run_from(snapshot, table, selected, jobs, timeout)


def _run_from(
    snapshot: Path,
    table: Table,
    selected: list[Mutant],
    jobs: int,
    timeout: float,
) -> list[Outcome]:
    """The baseline, then each mutant in ``selected``, each in a copy of ``snapshot``."""
    width = max(1, min(jobs, len(selected)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        failures = [
            failure
            for failure in pool.map(
                lambda _: _baseline(snapshot, table, timeout), range(width)
            )
            if failure is not None
        ]
        if not failures:
            return list(
                pool.map(
                    lambda mutant: _run_one(snapshot, table, mutant, timeout),
                    selected,
                )
            )
    failure = failures[0]
    if width > 1:
        failure += f" ({len(failures)} of {width} copies run at once failed)"
    return [_static(snapshot, mutant, failure) for mutant in selected]


def _static(root: Path, mutant: Mutant, failure: str) -> Outcome:
    """Why ``mutant`` does not apply, or `NOT RUN` because the baseline failed."""
    result = _mutated(root, mutant)
    return (
        result
        if isinstance(result, Outcome)
        else Outcome(mutant.name, "NOT RUN", failure)
    )


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
    except ValueError as exc:  # a KnowledgeFormatError, or a bad --timeout
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
