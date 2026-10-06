"""Refuse a new copy of a responsibility the toolkit owns once (Decision 0102, #368).

`policy/owned-responsibilities.yaml` lists each responsibility the toolkit owns once,
its owner, and the source signatures that mark a re-implementation. Production is
every file but tests, knowledge, guidance and Markdown other than `AGENTS.md`: in a
repository, every tracked one, so a developer's virtualenv is not the product. A
repository Git cannot list, or a file the check cannot read, is an error, never a
clean result. The check reports:
- each signature outside its owner, its allowed places and its declared debt;
- in a file that owes debt, each matching line its entry does not name, which is a
  new copy, and each line the entry names that has gone, which must be removed from
  it. An entry none of whose lines match must go.

A unittest runs this in the `fast`, `regression` and `extended` profiles of
`ci/verify`, so in the repository's pre-commit and pre-push hooks and in provider CI.
"""

from __future__ import annotations

import argparse
import ast
import errno
import os
import re
import stat
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from tools import trusted_execution
from tools.knowledge_common import KnowledgeFormatError, load_yaml
from tools.schema_validation import schema_errors

SCHEMA = "owned-responsibilities.schema.json"
# What is not production: tests, knowledge, guidance, and documents but AGENTS.md.
_NOT_PRODUCTION = ("tests/", "knowledge/", "guidance/")
_PRODUCTION_DOCUMENTS = ("AGENTS.md",)
_SKIPPED_PARTS = {"__pycache__"}
# Outside a repository, a hidden directory is a build or cache artifact, such as an
# installed image's `.evidence/`, unless it is one the product tracks.
_PRODUCT_DIRECTORIES = {".github", ".githooks", ".devcontainer"}


@dataclass(frozen=True)
class Signature:
    """A line pattern, or the name of a structural detector for Python files."""

    id: str
    pattern: re.Pattern[str] | None
    means: str
    structure: str | None = None


@dataclass(frozen=True)
class Place:
    """A path, and the signatures that may appear there; ``None`` means all of them.

    For debt, ``lines`` is the exact text, stripped, of each line it owes. A count of
    lines stayed equal when one owed line went and a new copy came (Codex on #369).
    """

    path: str
    signatures: frozenset[str] | None
    note: str
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class Responsibility:
    id: str
    owner: str
    extend: str
    signatures: tuple[Signature, ...]
    allowed: tuple[Place, ...]
    debt: tuple[Place, ...]


@dataclass(frozen=True)
class Registry:
    """The registry, and where it is: it names every signature, so it is no copy."""

    path: Path
    responsibilities: tuple[Responsibility, ...]

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.responsibilities)


@dataclass(frozen=True)
class Violation:
    responsibility: Responsibility
    path: str
    line: int | None
    signature: str
    stale: bool = False
    # A line the debt entry names that the file no longer has.
    vanished: str | None = None

    def __str__(self) -> str:
        entry = self.responsibility
        # A path that is not UTF-8 is shown by its bytes, escaped, never by a lone
        # surrogate that cannot be printed (CodeRabbit and CodeAnt on #369).
        path = os.fsencode(self.path).decode("utf-8", errors="backslashreplace")
        if self.vanished is not None:
            return (
                f"{path}: stale debt for {entry.id} ({self.signature}): the line"
                f" {self.vanished!r} no longer matches, so remove it from the entry's"
                " lines in policy/owned-responsibilities.yaml"
            )
        if self.stale:
            return (
                f"{path}: stale debt for {entry.id} ({self.signature}): it no longer"
                " matches, so remove the entry from policy/owned-responsibilities.yaml"
            )
        means = next(
            (s.means for s in entry.signatures if s.id == self.signature),
            self.signature,
        )
        return (
            f"{path}:{self.line}: {means} ({entry.id}, {self.signature}): extend"
            f" {entry.owner} instead. {entry.extend}"
        )


def registry_errors(path: Path) -> list[str]:
    """Return each way the registry at ``path`` breaks its schema."""
    return schema_errors(load_yaml(path), SCHEMA)


def _places(raw: list[dict[str, Any]], note: str) -> tuple[Place, ...]:
    return tuple(
        Place(
            path=str(item["path"]),
            signatures=frozenset(item["signatures"]) if "signatures" in item else None,
            note=str(item.get(note, "")),
            lines=tuple(str(line) for line in item.get("lines", ())),
        )
        for item in raw
    )


def _compile(path: Path, signature: dict[str, Any]) -> re.Pattern[str]:
    """A signature's pattern; a schema-valid string that is no regular expression is
    a registry error, not a crash (CodeAnt on #369)."""
    try:
        return re.compile(str(signature["pattern"]))
    # A deeply nested pattern raises `RecursionError`, not `re.error` (CodeAnt on
    # #369).
    except (re.error, RecursionError) as exc:
        raise KnowledgeFormatError(
            f"{path}: signature {signature['id']}: {exc}"
        ) from exc


def _refuse_repeats(path: Path, document: dict[str, Any]) -> None:
    """Refuse an id or a path the registry names twice where it must name it once."""
    names = [str(item["id"]) for item in document["responsibilities"]]
    again = sorted({n for n in names if names.count(n) > 1})
    if again:
        raise KnowledgeFormatError(
            f"{path}: the responsibility id {', '.join(again)} is used twice"
        )
    for item in document["responsibilities"]:
        ids = [str(signature["id"]) for signature in item["signatures"]]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise KnowledgeFormatError(
                f"{path}: {item['id']} uses the signature id {', '.join(repeated)} twice"
            )
        # Two entries for one path pooled their counts (CodeAnt on #369).
        for kind in ("allowed", "debt"):
            paths = [str(place["path"]) for place in item[kind]]
            twice = sorted({p for p in paths if paths.count(p) > 1})
            if twice:
                raise KnowledgeFormatError(
                    f"{path}: {item['id']} lists {', '.join(twice)} twice in {kind}"
                )


def load_registry(path: Path) -> Registry:
    """Return the registry at ``path``, checked against its schema.

    The document is read once, and what is checked is what is used: reading it twice
    let a concurrent edit through unchecked (CodeAnt on #369). A responsibility id
    used twice is refused, since it would name no single owner (Codex on #369), and
    so is a signature id used twice in one entry, since an allowance for one pattern
    would cover another.
    """
    document = load_yaml(path)
    errors = schema_errors(document, SCHEMA)
    if errors:
        raise KnowledgeFormatError(f"{path}: " + "; ".join(errors))
    _refuse_repeats(path, document)
    return Registry(
        path.resolve(),
        tuple(
            Responsibility(
                id=str(item["id"]),
                owner=str(item["owner"]),
                extend=" ".join(str(item["extend"]).split()),
                signatures=tuple(
                    Signature(
                        str(s["id"]),
                        _compile(path, s) if "pattern" in s else None,
                        str(s["means"]),
                        structure=s.get("structure"),
                    )
                    for s in item["signatures"]
                ),
                allowed=_places(item["allowed"], "reason"),
                debt=_places(item["debt"], "until"),
            )
            for item in document["responsibilities"]
        ),
    )


def _is_production(relative: str) -> bool:
    if relative.startswith(_NOT_PRODUCTION):
        return False
    # An AGENTS.md anywhere routes agents as the root one does (CodeAnt on #369).
    name = relative.rsplit("/", 1)[-1]
    return not relative.endswith(".md") or name in _PRODUCTION_DOCUMENTS


def _walked(relative: Path) -> bool:
    """Whether a walk outside a repository reads ``relative``: not a cache, and not
    inside a hidden directory the product does not track."""
    directories = relative.parts[:-1]
    if _SKIPPED_PARTS.intersection(relative.parts):
        return False
    return not any(
        part.startswith(".") and part not in _PRODUCT_DIRECTORIES
        for part in directories
    )


def _walked_files(root: Path) -> list[str]:
    """Every file under ``root`` a walk keeps. A directory it cannot read is an error:
    `rglob` skipped one, and a copy there passed unseen (CodeAnt on #369)."""

    def refuse(error: OSError) -> None:
        raise KnowledgeFormatError(
            f"cannot walk {error.filename}: {error.strerror}"
        ) from error

    found = []
    for directory, subdirectories, names in os.walk(root, onerror=refuse):
        here = Path(directory).relative_to(root)
        # Not into a directory the walk would skip anyway, where an unreadable one
        # stopped the check (CodeAnt on #369). `_walked` reads a file's path.
        subdirectories[:] = [d for d in subdirectories if _walked(here / d / "_")]
        for name in names:
            relative = (Path(directory) / name).relative_to(root)
            if (root / relative).is_file() and _walked(relative):
                found.append(relative.as_posix())
    return found


def _production_files(root: Path, registry: Path) -> list[str]:
    """Return every production file under ``root``, as a relative POSIX path."""
    # Outside any repository, as in the installed image, the tree is walked. A
    # repository Git cannot list raises: walking it instead would read its untracked
    # files as production (CodeRabbit on #369).
    listed = trusted_execution.repository_files(root)
    if listed is None:
        listed = _walked_files(root)
    # Only the registry is resolved, once: resolving each file raised on a looping
    # link (CodeAnt on #369).
    try:
        own = registry.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        own = None
    return sorted(
        relative for relative in listed if _is_production(relative) and relative != own
    )


def _lines(root: Path, relative: str) -> Iterator[str]:
    """Yield the lines of a regular file of the product, one at a time.

    - An undecodable byte must not hide a copy, so it is replaced (CodeRabbit on
      #369).
    - A tracked file missing from the work tree holds no copy, and nor does a link or
      a special file. A link's target is no file of the product, and one to
      `/dev/zero` would never end (CodeAnt on #369). So the file is opened without
      following a link or blocking, and read only if it is regular.
    - Any other failure to read raises, since a file the check cannot read would
      otherwise pass as clean (CodeAnt on #369).
    - It is read a block at a time: read whole, then decoded and split, a file was
      held three times over (CodeAnt on #369). Lines end where Python ends them, at
      `\\r\\n`, `\\r` or `\\n`. `readline` ends them at `\\n` only, so a long file with
      `\\r` alone was read as one line too long to check (CodeAnt on #369).
    """
    descriptor = _open_regular(root, relative)
    if descriptor is None:
        return
    with os.fdopen(descriptor, "rb") as handle:
        for line in _byte_lines(handle, relative):
            yield line.decode("utf-8", errors="replace")


def _byte_lines(handle: IO[bytes], relative: str) -> Iterator[bytes]:
    """Yield each line of ``handle``, without its ending, holding one line at most."""
    pending, searched = b"", 0
    while True:
        block = handle.read(_BLOCK_BYTES)
        pending += block
        start = 0
        for ending in _LINE_END.finditer(pending, searched):
            # A `\r` that ends what is read so far may begin a `\r\n`.
            if block and ending.group() == b"\r" and ending.end() == len(pending):
                break
            yield pending[start : ending.start()]
            start = ending.end()
        pending = pending[start:]
        # A deferred `\r` ends the line; it is none of its content (CodeAnt on #369).
        if len(pending) - pending.endswith(b"\r") > _LINE_LIMIT_BYTES:
            # A file with no line end was read whole (Codex on #369); a line this
            # long is an error, never a clean result.
            raise KnowledgeFormatError(
                f"{relative}: a line longer than {_LINE_LIMIT_BYTES} bytes cannot be"
                " checked"
            )
        # What is pending holds no line end, but perhaps a final `\r`.
        searched = max(0, len(pending) - 1)
        if not block:
            if pending:
                yield pending
            return


def _open_regular(root: Path, relative: str) -> int | None:
    """A descriptor for a regular file of the product, or None for a missing file, a
    link or a special file; see `_lines`."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(root / relative, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return None
        raise
    # Judge the open descriptor itself: `fdopen` refuses a directory, such as a
    # submodule's.
    try:
        regular = stat.S_ISREG(os.fstat(descriptor).st_mode)
    except OSError:
        # The descriptor is closed on this path too (CodeAnt on #369).
        os.close(descriptor)
        raise
    if not regular:
        os.close(descriptor)
        return None
    return descriptor


# A line longer than this is an error to check, never a pass.
_LINE_LIMIT_BYTES = 1024 * 1024
# Lines end where Python ends them: `str.splitlines` also breaks at a form feed, U+2028
# or NEL inside one Python line, and misnumbered every later line (CodeAnt on #369).
# No UTF-8 sequence holds either byte, so the bytes are split before decoding.
_LINE_END = re.compile(rb"\r\n|\r|\n")
_BLOCK_BYTES = 64 * 1024
# A Python file larger than this is an error to check structurally, never a pass.
_STRUCTURE_LIMIT_BYTES = 8 * 1024 * 1024


def _catches_value_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    caught = (
        handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    )
    names = {
        node.id if isinstance(node, ast.Name) else getattr(node, "attr", "")
        for node in caught
    }
    return bool(names & {"ValueError", "Exception", "BaseException"})


def _relative_to_under_value_error(tree: ast.AST) -> set[int]:
    """The lines of `relative_to` calls in a `try` whose handlers catch `ValueError`:
    the common way to confine a path (Codex on #369)."""
    tries = (ast.Try, *((ast.TryStar,) if hasattr(ast, "TryStar") else ()))
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, tries):
            continue
        if not any(_catches_value_error(h) for h in node.handlers):
            continue
        for call in _calls_in_this_scope(node.body):
            if isinstance(call.func, ast.Attribute) and call.func.attr == "relative_to":
                found.add(call.lineno)
    return found


def _path_prefix_comparison(tree: ast.AST) -> set[int]:
    """The lines where a path is confined by comparison: a common path or prefix
    compared with a root, a root among a path's parents, or a prefix ending in the
    separator (Codex on #369)."""
    return {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.Compare, ast.Call))
        and (
            (isinstance(node, ast.Compare) and _compares_a_prefix(node))
            or _starts_with_the_separator(node)
        )
    }


def _compares_a_prefix(node: ast.Compare) -> bool:
    """`commonpath(...) == root`, or `root in path.parents`, either way round. A
    common prefix compared with a constant compares strings, and confines no path
    (CodeAnt on #369)."""
    sides = (node.left, *node.comparators)
    if (
        any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
        and any(
            isinstance(side, ast.Call)
            and _called(side) in {"commonpath", "commonprefix"}
            for side in sides
        )
        and not any(isinstance(side, ast.Constant) for side in sides)
    ):
        return True
    return any(
        isinstance(op, (ast.In, ast.NotIn))
        and isinstance(right, ast.Attribute)
        and right.attr == "parents"
        for op, right in zip(node.ops, node.comparators, strict=True)
    )


def _starts_with_the_separator(node: ast.AST) -> bool:
    """`path.startswith(root + os.sep)`, or the same prefix as an f-string."""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
        and node.args
    ):
        return False
    prefix = node.args[0]
    if isinstance(prefix, ast.BinOp) and isinstance(prefix.op, ast.Add):
        return _is_separator(prefix.right)
    if isinstance(prefix, ast.JoinedStr) and prefix.values:
        last = prefix.values[-1]
        return isinstance(last, ast.FormattedValue) and _is_separator(last.value)
    return False


def _is_separator(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "sep"


def _called(call: ast.Call) -> str | None:
    """The name a call ends in: `commonpath` for `os.path.commonpath(...)` too."""
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else None


def _runs_now(node: ast.AST) -> list[ast.AST]:
    """The parts of ``node`` that run where it stands. A function's or a lambda's body
    runs when called, and a generator's when iterated, perhaps after the `try` (CodeAnt
    on #369); their decorators, defaults and first iterable run at once."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        decorators = [] if isinstance(node, ast.Lambda) else node.decorator_list
        defaults = [d for d in node.args.kw_defaults if d is not None]
        return [*decorators, *node.args.defaults, *defaults]
    if isinstance(node, ast.GeneratorExp):
        return [node.generators[0].iter]
    return list(ast.iter_child_nodes(node))


def _calls_in_this_scope(body: list[ast.stmt]) -> Iterator[ast.Call]:
    """The calls that run in ``body`` itself, as `_runs_now` reads each node."""
    pending: list[ast.AST] = list(body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Call):
            yield node
        pending.extend(_runs_now(node))


def _under(name: str | None, module: str) -> bool:
    """Whether ``name`` is ``module`` or one of its submodules."""
    return name is not None and (name == module or name.startswith(f"{module}."))


def _dotted(node: ast.expr) -> str | None:
    """``node`` as a dotted name, `a.b.c`, or None if it is no such chain."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


def _imports_unseen(
    tree: ast.AST, module: str, imported: Callable[[str], bool]
) -> set[int]:
    """The lines of wanted names imported from ``module`` or a submodule where the
    line pattern cannot see them: any import from a submodule, as in `from
    jsonschema.validators import validator_for as select` (Codex on #369), and a name
    on a line of its own in a multi-line import. A relative import is another module."""
    return {
        alias.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and not node.level
        and _under(node.module, module)
        for alias in node.names
        if imported(alias.name)
        and (node.module != module or alias.lineno != node.lineno)
    }


def _module_aliases(tree: ast.AST, module: str) -> dict[str, str]:
    """Each name bound to ``module`` or a submodule, other than the module's own, with
    the dotted path it stands for. `import module as name`, `import module.sub as
    name`, and `from module import sub [as name]`, a submodule imported by name
    (CodeAnt on #369). A name imported by `from` may be a function rather than a
    submodule; only the calls ``called`` wants through it are marked."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _under(alias.name, module) and alias.asname not in (None, module):
                    aliases[str(alias.asname)] = alias.name
        elif (
            isinstance(node, ast.ImportFrom)
            and not node.level
            and _under(node.module, module)
        ):
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _calls_through(
    tree: ast.AST, module: str, aliases: dict[str, str], called: Callable[[str], bool]
) -> set[int]:
    """The lines of wanted calls whose owner, its alias resolved, is ``module`` reached
    through an alias, or one of its submodules. A call through the module's own name
    is the line pattern's."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and called(node.func.attr)
        ):
            continue
        owner = _dotted(node.func.value)
        if owner is None:
            continue
        root, _, rest = owner.partition(".")
        if root in aliases:
            owner = aliases[root] + (f".{rest}" if rest else "")
        if _under(owner, module) and (root in aliases or owner != module):
            lines.add(node.lineno)
    return lines


def _indirect_uses(
    module: str, imported: Callable[[str], bool], called: Callable[[str], bool]
) -> Callable[[ast.AST], set[int]]:
    """A detector for ``module``'s functions where a line pattern cannot see them: a
    name on a line of its own in a multi-line import, and a call through an alias of
    the module (Codex on #369). An import's own line, and a call through the module's
    own name, are the line pattern's, so no line is marked twice."""

    def detect(tree: ast.AST) -> set[int]:
        aliases = _module_aliases(tree, module)
        return _imports_unseen(tree, module, imported) | _calls_through(
            tree, module, aliases, called
        )

    return detect


# A name for the git executable: `git`, `git_bin` or `self._git`, but not `digit`,
# `gitlab` or `git_dir`.
_GIT_NAME = re.compile(
    r"(?:^|_)git(?:_(?:bin|binary|exe|executable|path|cmd|command|program))?$",
    re.IGNORECASE,
)


def _names_git(node: ast.expr) -> bool:
    name = (
        node.attr
        if isinstance(node, ast.Attribute)
        else node.id
        if isinstance(node, ast.Name)
        else None
    )
    return name is not None and _GIT_NAME.search(name) is not None


def _git_argv(tree: ast.AST) -> set[int]:
    """The first element of an argument list headed by a name for git, where the line
    pattern cannot see it: a tuple, or a list split across lines (CodeAnt on #369)."""
    return {
        node.elts[0].lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.List, ast.Tuple))
        and node.elts
        and _names_git(node.elts[0])
        and (isinstance(node, ast.Tuple) or node.elts[0].lineno != node.lineno)
    }


def _never(_name: str) -> bool:
    return False


def _either(
    *detectors: Callable[[ast.AST], set[int]],
) -> Callable[[ast.AST], set[int]]:
    """A detector that marks what any of ``detectors`` marks."""

    def detect(tree: ast.AST) -> set[int]:
        return set().union(*(found(tree) for found in detectors))

    return detect


def _yaml_loader(name: str) -> bool:
    return re.fullmatch(r"(?:safe_|full_|unsafe_)?load(?:_all)?", name) is not None


# The line patterns already see a `Draft<n>Validator` name anywhere, and a call of
# validator_for.
_STRUCTURES: dict[str, Callable[[ast.AST], set[int]]] = {
    "relative-to-under-value-error": _relative_to_under_value_error,
    "path-prefix-comparison": _path_prefix_comparison,
    "git-argv": _git_argv,
    "http-request-indirect": _either(
        _indirect_uses("http", "client".__eq__, _never),
        _indirect_uses("urllib", "request".__eq__, _never),
    ),
    "yaml-load-indirect": _indirect_uses("yaml", _yaml_loader, _yaml_loader),
    "jsonschema-validator-indirect": _indirect_uses(
        "jsonschema", {"validate", "validator_for"}.__contains__, "validate".__eq__
    ),
    "executable-lookup-indirect": _indirect_uses(
        "shutil", "which".__eq__, "which".__eq__
    ),
}


def _structural_lines(
    root: Path, relative: str, wanted: frozenset[str]
) -> dict[str, frozenset[int]]:
    """For a Python file of the product, the lines each wanted detector marks.

    A Python file ends in `.py` or starts with a Python shebang. One that does not
    parse, or is too large to parse, cannot pass as clean, so it is an error.
    """
    if not wanted:
        return {}
    descriptor = _open_regular(root, relative)
    if descriptor is None:
        return {}
    with os.fdopen(descriptor, "rb") as handle:
        data = handle.read(128)
        first = data.split(b"\n", 1)[0]
        if not relative.endswith(".py") and not (
            first.startswith(b"#!") and b"python" in first
        ):
            return {}
        data += handle.read(_STRUCTURE_LIMIT_BYTES + 1 - len(data))
    if len(data) > _STRUCTURE_LIMIT_BYTES:
        raise KnowledgeFormatError(f"{relative}: too large to check its structure")
    try:
        tree = ast.parse(data.decode("utf-8", errors="replace"), filename=relative)
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise KnowledgeFormatError(
            f"{relative}: Python that does not parse cannot be checked: {exc}"
        ) from exc
    return {name: frozenset(_STRUCTURES[name](tree)) for name in wanted}


def _covers(places: tuple[Place, ...], path: str, signature: str) -> bool:
    return any(
        place.path == path
        and (place.signatures is None or signature in place.signatures)
        for place in places
    )


def _allowed(entry: Responsibility, relative: str, signature: str) -> bool:
    """Whether a signature may appear here: at its owner (CodeRabbit on #369), or in a
    place the registry allows."""
    return relative == entry.owner or _covers(entry.allowed, relative, signature)


# A line a debt entry may owe: its number, its stripped text and the signature.
Owed = tuple[int, str, str]


def _scan(
    entry: Responsibility,
    relative: str,
    number: int,
    text: str,
    marked: dict[str, frozenset[int]],
) -> tuple[list[Violation], Owed | None]:
    """Return each copy of ``entry`` on one line, and the line if a debt entry may owe
    it. ``marked`` holds the lines each structural detector marked in the file."""
    matched = [
        s.id
        for s in entry.signatures
        if (s.pattern is not None and s.pattern.search(text))
        or (s.structure is not None and number in marked.get(s.structure, ()))
    ]
    unexplained = [s for s in matched if not _allowed(entry, relative, s)]
    indebted = [s for s in unexplained if _covers(entry.debt, relative, s)]
    copies = [
        Violation(entry, relative, number, s) for s in unexplained if s not in indebted
    ]
    return copies, (number, text.strip(), indebted[0]) if indebted else None


def _debt_findings(
    entry: Responsibility, owed: dict[str, list[Owed]]
) -> list[Violation]:
    """Return each line a debt entry does not name, and each it names that is gone.

    A line beyond what the entry names is a new copy, however many lines it names.
    """
    found: list[Violation] = []
    for place in entry.debt:
        listed = ", ".join(sorted(place.signatures or ()))
        lines = owed.get(place.path, [])
        if not lines:
            found.append(Violation(entry, place.path, None, listed, stale=True))
            continue
        named = Counter(place.lines)
        for number, text, signature in lines:
            if named[text] > 0:
                named[text] -= 1
            else:
                found.append(Violation(entry, place.path, number, signature))
        found.extend(
            Violation(entry, place.path, None, listed, vanished=text)
            for text in sorted(named.elements())
        )
    return found


def violations(root: Path, registry: Registry) -> list[Violation]:
    """Return every copy outside its owner, and every changed debt entry, in order.

    One line is read at a time, so a large tracked file is never held whole (CodeAnt
    on #369).
    """
    entries = registry.responsibilities
    copies: list[list[Violation]] = [[] for _ in entries]
    owed: list[dict[str, list[Owed]]] = [{} for _ in entries]
    structures = frozenset(
        s.structure for e in entries for s in e.signatures if s.structure is not None
    )
    for relative in _production_files(root, registry.path):
        marked = _structural_lines(root, relative, structures)
        for number, text in enumerate(_lines(root, relative), start=1):
            for index, entry in enumerate(entries):
                found, owes = _scan(entry, relative, number, text, marked)
                copies[index].extend(found)
                if owes is not None:
                    owed[index].setdefault(relative, []).append(owes)
    result: list[Violation] = []
    for index, entry in enumerate(entries):
        result.extend(copies[index])
        result.extend(_debt_findings(entry, owed[index]))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="knowledge reuse-check",
        description="Refuse a new copy of a responsibility the toolkit owns once.",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args(argv)
    registry_path = (
        args.registry or args.root / "policy" / "owned-responsibilities.yaml"
    )
    try:
        found = violations(args.root, load_registry(registry_path))
    except (
        trusted_execution.TrustedExecutionError,
        KnowledgeFormatError,
        OSError,
        UnicodeDecodeError,
    ) as exc:
        # A registry that breaks its schema cannot be checked against either
        # (CodeRabbit on #369), and nor can one that is not UTF-8 (CodeAnt on #369).
        print(f"reuse-check: cannot check {args.root}: {exc}")
        return 2
    for violation in found:
        print(violation)
    if found:
        print(f"reuse-check: {len(found)} finding(s); extend the owner each one names")
        return 1
    print("reuse-check: no copy of an owned responsibility")
    return 0
