"""Read where a shell runs a command (Decision 0105).

Shell text is split by the standard library's `shlex`, so quotes, escapes, comments
and control operators are read as a shell reads them. A command is found at its
position, after the words that only precede it are peeled: no regular expression
describes shell syntax here. The reuse check asks whether a command runs Git
(`runs_git`), which command an argument list hands a shell (`handed_command`), and
which lines of a file are shell text (`shell_lines`).
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Sequence

# Words that open a command position without being the command. `time` and `exec`
# are wrappers, since options can follow them.
_RESERVED = frozenset({"if", "then", "elif", "else", "do", "while", "until", "!", "{"})
# Tokens that end one command and begin the next.
_SEPARATORS = frozenset(
    {";", "&&", "||", "|", "&", "(", ")", ";;", "|&", ";&", ";;&", "}"}
)
# Commands that run the command after their own options and arguments.
_WRAPPERS = frozenset(
    {
        "env",
        "command",
        "sudo",
        "timeout",
        "nice",
        "nohup",
        "xargs",
        "stdbuf",
        "ionice",
        "setsid",
        "chrt",
        "flock",
        "time",
        "exec",
    }
)
# The shells that run a command string given with `-c`.
_SHELLS = frozenset({"sh", "bash", "dash", "ksh", "zsh", "ash"})
# A shell's options that take the next word as their value, as `-O extglob` does.
_VALUE_OPTIONS = frozenset({"-o", "+o", "-O", "+O", "--rcfile", "--init-file"})
# `env -S` splits its value into the command it runs.
_SPLIT_STRING = frozenset({"-S", "--split-string"})
_NAMES = _WRAPPERS | _SHELLS | {"git"}
_ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=", re.ASCII)
# How deep `sh -c` and `env -S` may nest before the reader stops following.
_DEPTH = 4
_FENCES = frozenset({"bash", "sh", "shell", "zsh", "console"})
_BLOCK = re.compile(r"[|>][-+]?\d*\s*(?:#.*)?")
_RUN = re.compile(r"(\s*)(?:-\s+)?run:\s*(.*)")


def words(text: str) -> list[str]:
    """The tokens of ``text``, as a shell splits them, as far as they split."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    found: list[str] = []
    try:
        found.extend(lexer)
    except ValueError:
        # An unterminated quote or escape: what split before it still counts.
        pass
    return found


def runs_git(text: str, depth: int = 0) -> bool:
    """Whether the shell text ``text`` runs Git at any command position. Each of its
    lines is read on its own, as a shell runs each line."""
    if depth > _DEPTH:
        return False
    return any(
        _runs_git(command, depth)
        for line in text.splitlines()
        for command in _commands(words(line))
    )


def handed_command(argv: Sequence[str | None]) -> tuple[int, str] | None:
    """The command string an argument list hands a shell, after any wrappers before
    the shell, with its index; None if it hands none. An unknown word is None."""
    index = 0
    while index < len(argv):
        # A word that is no literal names no shell and no wrapper.
        name = (argv[index] or "").rsplit("/", 1)[-1]
        if name in _SHELLS:
            return _shell_command(argv, index + 1)
        if name not in _WRAPPERS:
            return None
        index, nested = _past_wrapper(argv, index + 1)
        if nested is not None:
            return nested
    return None


def _commands(tokens: list[str]) -> list[list[str]]:
    """The simple commands of ``tokens``: its words between separators."""
    found: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            found.append([])
        else:
            found[-1].append(token)
    return [command for command in found if command]


def _runs_git(command: list[str], depth: int) -> bool:
    """Whether one simple command runs Git: as its command word, after reserved
    words, assignments and wrappers, or through a shell or `env -S`."""
    index = 0
    while index < len(command) and (
        command[index] in _RESERVED or _ASSIGNMENT.match(command[index])
    ):
        index += 1
    while index < len(command):
        name = _command_name(command[index])
        if name == "git":
            return True
        if name in _SHELLS:
            found = _shell_command(command, index + 1)
            return found is not None and runs_git(found[1], depth + 1)
        if name not in _WRAPPERS:
            return False
        index, nested = _past_wrapper(command, index + 1)
        if nested is not None and runs_git(nested[1], depth + 1):
            return True
    return False


def _command_name(word: str) -> str:
    """A command word's name: after Make's `@`, `-` and `+` prefixes, a backtick and
    its path."""
    return word.lstrip("@+-`").rstrip("`").rsplit("/", 1)[-1]


def _past_wrapper(
    argv: Sequence[str | None], index: int
) -> tuple[int, tuple[int, str] | None]:
    """Where the command after a wrapper's options and arguments stands, and the
    command `env -S` names, if any. An option's word, a number, a path and an
    assignment are the wrapper's own."""
    while index < len(argv):
        word = argv[index]
        if word is not None and word.rsplit("/", 1)[-1] in _NAMES:
            break
        split = _split_string(argv, index)
        if split is not None:
            return split
        if not _wrapper_word(word, argv[index - 1] if index else None):
            break
        index += 1
    return index, None


def _split_string(
    argv: Sequence[str | None], index: int
) -> tuple[int, tuple[int, str] | None] | None:
    """`env -S value` or `--split-string=value`: where the command after it stands,
    and the command its value names; None for any other word."""
    word = argv[index]
    if word in _SPLIT_STRING and index + 1 < len(argv):
        value = argv[index + 1]
        return index + 2, None if value is None else (index + 1, value)
    if word is not None and word.startswith("--split-string="):
        return index + 1, (index, word.split("=", 1)[1])
    return None


def _wrapper_word(word: str | None, previous: str | None) -> bool:
    """Whether a word is a wrapper's own: an option, an assignment, a number, a
    path, or the word an option before it takes."""
    if word is not None and (
        word.startswith(("-", "+"))
        or _ASSIGNMENT.match(word)
        or word[:1].isdigit()
        or word.startswith("/")
    ):
        return True
    return previous is not None and previous.startswith("-")


def _shell_command(argv: Sequence[str | None], index: int) -> tuple[int, str] | None:
    """The word a shell's `-c` names, read past the options before it; None if a word
    that is no option comes first, or no word follows."""
    while index < len(argv):
        option = argv[index]
        if option is None:
            return None
        if option in _VALUE_OPTIONS:
            index += 2
        elif not option.startswith("-"):
            return None
        elif not option.startswith("--") and "c" in option:
            value = argv[index + 1] if index + 1 < len(argv) else None
            return None if value is None else (index + 1, value)
        else:
            index += 1
    return None


def is_shell_source(relative: str, first: str) -> bool:
    """Whether the file ``relative``, whose first line is ``first``, holds shell text
    anywhere: a script, a Dockerfile, a Makefile, a workflow or an `AGENTS.md`."""
    name = relative.rsplit("/", 1)[-1]
    return (
        name.endswith((".sh", ".bash"))
        or _shell_shebang(first)
        or _is_dockerfile(name)
        or _is_makefile(name)
        or _is_workflow(relative, name)
        or name == "AGENTS.md"
    )


def shell_lines(relative: str, lines: list[str]) -> dict[int, tuple[str, ...]]:
    """The shell text of a file, by line: the whole of a script, `RUN` in a
    Dockerfile, a Make recipe, a workflow's `run:` and a fenced shell block in an
    `AGENTS.md`. Each physical line is read on its own, so a command is reported on
    the line that holds it, and a continuation line starts a position of its own."""
    name = relative.rsplit("/", 1)[-1]
    if name.endswith((".sh", ".bash")) or (lines and _shell_shebang(lines[0])):
        texts = list(enumerate(lines, start=1))
    elif _is_dockerfile(name):
        texts = _dockerfile(lines)
    elif _is_makefile(name):
        texts = [(n, t[1:]) for n, t in enumerate(lines, 1) if t[:1] == "\t"]
    elif _is_workflow(relative, name):
        texts = _workflow(lines)
    elif name == "AGENTS.md":
        texts = _fenced(lines)
    else:
        texts = []
    found: dict[int, list[str]] = {}
    for number, text in texts:
        found.setdefault(number, []).append(text)
    return {number: tuple(found[number]) for number in found}


def _shell_shebang(first: str) -> bool:
    if not first.startswith("#!"):
        return False
    parts = first[2:].split()
    if parts and parts[0].rsplit("/", 1)[-1] == "env" and len(parts) > 1:
        parts = parts[1:]
    return bool(parts) and parts[0].rsplit("/", 1)[-1] in _SHELLS


def _is_dockerfile(name: str) -> bool:
    return (
        name == "Dockerfile"
        or name.startswith("Dockerfile.")
        or name.endswith(".Dockerfile")
    )


def _is_makefile(name: str) -> bool:
    return name in {"Makefile", "makefile", "GNUmakefile"} or name.endswith(".mk")


def _is_workflow(relative: str, name: str) -> bool:
    return relative.startswith(".github/workflows/") and name.endswith(
        (".yml", ".yaml")
    )


def _dockerfile(lines: list[str]) -> list[tuple[int, str]]:
    """Each `RUN` instruction's shell text, and its continuation lines, each on its
    own line. The exec form, a JSON list, is no shell text."""
    found: list[tuple[int, str]] = []
    continued = False
    for number, text in enumerate(lines, start=1):
        if continued:
            found.append((number, text))
        else:
            head, _, rest = text.strip().partition(" ")
            if head.upper() != "RUN" or rest.lstrip().startswith("["):
                continue
            found.append((number, rest))
        continued = text.endswith("\\")
    return found


def _workflow(lines: list[str]) -> list[tuple[int, str]]:
    """Each workflow `run:` value: one line, or a block's more-indented lines."""
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        match = _RUN.fullmatch(lines[index])
        index += 1
        if match is None:
            continue
        indent, value = len(match.group(1)), match.group(2).strip()
        if not _BLOCK.fullmatch(value):
            found.append((index, _unquoted(value)))
            continue
        block: list[tuple[int, str]] = []
        while index < len(lines) and (
            not lines[index].strip()
            or len(lines[index]) - len(lines[index].lstrip()) > indent
        ):
            block.append((index + 1, lines[index]))
            index += 1
        found.extend(block)
    return found


def _unquoted(value: str) -> str:
    """A YAML scalar's text, without the quotes around it."""
    if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _fenced(lines: list[str]) -> list[tuple[int, str]]:
    """The lines of each fenced shell block; a console block's `$ ` prompt goes."""
    found: list[tuple[int, str]] = []
    language: str | None = None
    for number, text in enumerate(lines, start=1):
        stripped = text.strip()
        if stripped.startswith("```"):
            language = None if language is not None else stripped[3:].strip()
            continue
        if language in _FENCES:
            found.append((number, text.lstrip().removeprefix("$ ")))
    return found
