"""Read where a shell runs a command (Decision 0105).

Shell text is split by the standard library's `shlex`, so quotes, escapes, comments
and control operators are read as a shell reads them. A command is found at its
position, after the words that only precede it are peeled: no regular expression
describes shell syntax here. The reuse check asks whether a command runs Git
(`runs_git`), which command an argument list hands a shell (`handed_command`), and
which lines of a file are shell text (`shell_lines`).
"""

from __future__ import annotations

import bisect
import json
import re
import shlex
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import yaml

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
# Wrappers whose first word that is no option is an operand of their own, however it
# is spelt, before the command they run: `flock`'s lock file, `timeout`'s duration,
# as `.5s`, and `chrt`'s priority (Codex on #369).
_OPERANDS = frozenset({"flock", "timeout", "chrt"})
# A wrapper's options whose value is the command it runs: `env -S` splits its value
# into one, and `flock -c` hands its value to a shell (Codex on #369).
_COMMAND_OPTIONS = {
    "env": ("-S", "--split-string"),
    "flock": ("-c", "--command"),
}
_NAMES = _WRAPPERS | _SHELLS | {"git"}
# The word a backquoted command substitution leaves in its place: a name no rule
# reads, so `` `date` git `` runs no Git, while `x=`date` git` does.
_SUBSTITUTED = "_"
# A group's closing token, and the token that opens it.
_GROUPS = {"}": "{", ")": "("}
# The shell's redirection operators, as `2>`'s `>`, `>&` or `<<`; and a process
# substitution's opening. A set, not a pattern, so nothing backtracks (SonarCloud).
_REDIRECTIONS = frozenset(
    {"<", ">", ">>", "<<", "<<<", "<&", ">&", "<>", ">|", "&>", "&>>"}
)
_PROCESS = frozenset({"<(", ">("})
# What ends the command a here-document follows.
_BOUNDARIES = _SEPARATORS | _PROCESS
_ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=", re.ASCII)
# How deep `sh -c` and `env -S` may nest before the reader stops following.
_DEPTH = 4
_FENCES = frozenset({"bash", "sh", "shell", "zsh", "console"})


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
    lines is read on its own, as a shell runs each line. Only a newline ends one:
    `str.splitlines` also split at U+2028, NEL and form feed, which a shell does
    not (CodeAnt on #369)."""
    if depth > _DEPTH:
        return False
    for line in text.split("\n"):
        outer, substituted = _substitutions(line)
        if any(_runs_git(command, depth) for command in _commands(words(outer))):
            return True
        if any(runs_git(command, depth + 1) for command in substituted):
            return True
    return False


def _substitutions(line: str) -> tuple[str, list[str]]:
    """``line`` with each backquoted command substitution replaced by a word, and the
    substitutions' commands. A backtick opens one unless it is in single quotes or
    after a backslash; in double quotes it opens one too. `shlex` keeps no quoting,
    so it cannot tell these apart (Codex, Kody and Claude on #369)."""
    outer: list[str] = []
    substituted: list[str] = []
    quote = ""
    index = 0
    while index < len(line):
        char = line[index]
        if quote != "'" and char == "\\":
            outer.append(line[index : index + 2])
            index += 2
            continue
        if quote != "'" and char == "`":
            command, index = _backquoted(line, index + 1)
            substituted.append(command)
            outer.append(_SUBSTITUTED)
            continue
        quote = _quote(quote, char)
        outer.append(char)
        index += 1
    return "".join(outer), substituted


def _quote(quote: str, char: str) -> str:
    """The quote that is open after ``char``, given the one open before it."""
    if not quote and char in "'\"":
        return char
    return "" if char == quote else quote


def _backquoted(line: str, index: int) -> tuple[str, int]:
    """The command of the substitution whose text starts at ``index``, and where its
    closing backtick ends. As Bash's manual states, the first backtick that no
    backslash precedes closes it, and in it a backslash before `$`, a backtick or a
    backslash is removed. An unclosed one runs to the line's end."""
    command: list[str] = []
    while index < len(line):
        char = line[index]
        if char == "`":
            return "".join(command), index + 1
        if char == "\\" and line[index + 1 : index + 2] in ("$", "`", "\\"):
            char = line[index + 1]
            index += 1
        command.append(char)
        index += 1
    return "".join(command), index


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
        index, nested = _past_wrapper(argv, index + 1, name)
        if nested is not None:
            return nested
    return None


def _commands(tokens: list[str]) -> list[list[str]]:
    """The simple commands of ``tokens``: its words between separators, without
    their redirections. A redirection, its target and a descriptor's number before
    it are the shell's, wherever they stand, as in `2>/dev/null git fetch`; a
    process substitution, `<(...)`, opens a command of its own (Codex on #369)."""
    current: list[str] = []
    found = [current]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in _SEPARATORS or token in _PROCESS:
            current = []
            found.append(current)
        elif token in _REDIRECTIONS:
            if current and current[-1].isdigit():
                current.pop()
            index += 1
        else:
            current.append(token)
        index += 1
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
        if name == "eval":
            # `eval` joins its arguments and runs them as a command (Codex on #369).
            return runs_git(" ".join(command[index + 1 :]), depth + 1)
        if name not in _WRAPPERS:
            return False
        index, nested = _past_wrapper(command, index + 1, name)
        if nested is not None and runs_git(nested[1], depth + 1):
            return True
    return False


def _command_name(word: str) -> str:
    """A command word's name: after Make's `@`, `-` and `+` prefixes, and its path."""
    return word.lstrip("@+-").rsplit("/", 1)[-1]


def _past_wrapper(
    argv: Sequence[str | None], index: int, name: str
) -> tuple[int, tuple[int, str] | None]:
    """Where the command after the wrapper ``name``'s options and arguments stands,
    and the command an option of it names, if any. An option's word, an assignment
    and the operand some wrappers take are the wrapper's own."""
    operand = name in _OPERANDS
    while index < len(argv):
        word = argv[index]
        if word is not None and word.rsplit("/", 1)[-1] in _NAMES:
            break
        nested = _command_option(argv, index, _COMMAND_OPTIONS.get(name, ()))
        if nested is not None:
            return nested
        previous = argv[index - 1] if index else None
        if operand and _positional(word, previous):
            operand = False
        elif not _wrapper_word(word, previous):
            break
        index += 1
    return index, None


def _positional(word: str | None, previous: str | None) -> bool:
    """Whether a word is a positional one: no option, and not the word an option
    before it takes. A word whose text is unknown counts."""
    if previous is not None and previous.startswith("-"):
        return False
    return word is None or not word.startswith(("-", "+"))


def _command_option(
    argv: Sequence[str | None], index: int, options: tuple[str, ...]
) -> tuple[int, tuple[int, str] | None] | None:
    """An option of ``options`` with its value, as `-S value` or
    `--split-string=value`: where the command after it stands, and the command its
    value names; None for any other word."""
    word = argv[index]
    if word in options and index + 1 < len(argv):
        value = argv[index + 1]
        return index + 2, None if value is None else (index + 1, value)
    for option in options:
        if word is not None and word.startswith(f"{option}="):
            return index + 1, (index, word.split("=", 1)[1])
    return None


def _wrapper_word(word: str | None, previous: str | None) -> bool:
    """Whether a word is a wrapper's own: an option, an assignment, or the word an
    option before it takes. A path is the command the wrapper runs, as in
    `sudo /usr/bin/make`; a lock file, a duration or a priority is an operand,
    which `_positional` reads."""
    if word is not None and (word.startswith(("-", "+")) or _ASSIGNMENT.match(word)):
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
        texts = _make_recipes(lines)
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
    # Split as a shell splits it, so a quoted program name is that name (CodeAnt on
    # #369): `env -S "sh" -e` runs `sh`.
    parts = words(first[2:])
    if parts and parts[0].rsplit("/", 1)[-1] == "env":
        # `env`'s options and assignments come before the program, as `-S` and `-i`
        # do (CodeAnt on #369). The line is already split into words, so `-S` names
        # no command of its own here.
        parts = parts[_past_wrapper(parts, 1, "")[0] :]
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
    """A workflow, or an action's metadata: a composite action's steps run in a
    shell as a workflow's do (Codex on #369)."""
    return name in {"action.yml", "action.yaml"} or (
        relative.startswith(".github/workflows/") and name.endswith((".yml", ".yaml"))
    )


def _make_recipes(lines: list[str]) -> list[tuple[int, str]]:
    """Each recipe line's shell text: a line opened by the recipe prefix, a tab
    unless `.RECIPEPREFIX` names another character, from its assignment on; an empty
    value restores the tab (Codex on #369)."""
    prefix = "\t"
    found: list[tuple[int, str]] = []
    for number, text in enumerate(lines, start=1):
        if text.startswith(prefix):
            found.append((number, text[1:]))
            continue
        name, equals, value = text.partition("=")
        if equals and name.rstrip(" :?+!") == ".RECIPEPREFIX":
            prefix = value.strip()[:1] or "\t"
    return found


@dataclass
class _Heredoc:
    """A `RUN` instruction's here-document, while its body is read."""

    delimiter: str
    strip_tabs: bool
    shell: bool
    bare: bool
    first: bool = True


def _dockerfile(lines: list[str]) -> list[tuple[int, str]]:
    """Each `RUN` instruction's shell text, and its continuation lines, each on its
    own line. The exec form's JSON list is read as the argument list it runs. A
    here-document's body is shell text when a shell reads it (Codex on #369)."""
    escape = _escape(lines)
    found: list[tuple[int, str]] = []
    continued = False
    document: _Heredoc | None = None
    instruction = ""
    for number, text in enumerate(lines, start=1):
        if document is not None:
            document = _heredoc_line(document, number, text, found)
            continue
        rest = text if continued else _run_text(text)
        if rest is None:
            continue
        found.append((number, rest))
        # A continuation line may open one too, and the command it follows may
        # stand on an earlier line (Claude on #369).
        instruction = (
            f"{instruction.removesuffix(escape)} {rest}" if continued else rest
        )
        document = _heredoc(instruction)
        continued = document is None and text.endswith(escape)
    return found


def _run_text(text: str) -> str | None:
    """A `RUN` instruction's text past its own options; None for any other line. Any whitespace separates `RUN` from its text (Claude on
    #369)."""
    instruction = text.split(None, 1)
    if len(instruction) < 2 or instruction[0].upper() != "RUN":
        return None
    rest = _past_run_options(instruction[1])
    return _exec_form(rest) if rest.startswith("[") else rest


def _exec_form(rest: str) -> str:
    """An exec-form `RUN`'s JSON list as the command text it runs, which may hand a
    shell its command (CodeAnt on #369). Text that is no JSON list of strings stays
    as it is: Docker runs it as the shell form, as in `RUN [ -f x ] && make`."""
    try:
        argv = json.loads(rest)
    except ValueError:
        return rest
    if isinstance(argv, list) and all(isinstance(word, str) for word in argv):
        return shlex.join(argv)
    return rest


def _heredoc(rest: str) -> _Heredoc | None:
    """The here-document a `RUN` text opens, if any. A shell reads its body when it
    stands alone, as `RUN <<EOF`, or after a shell that reads its standard input, as
    `RUN bash -e <<EOF`; another program's body, as `python3 <<EOF`'s, is data. The
    command is the one the document follows, after any control operator, as in
    `apt-get update && bash <<EOF` (Claude on #369). One here-document per
    instruction is read."""
    tokens = words(rest)
    if "<<" not in tokens:
        return None
    at = tokens.index("<<")
    delimiter = tokens[at + 1] if at + 1 < len(tokens) else ""
    strip_tabs = delimiter.startswith("-")
    delimiter = delimiter.removeprefix("-")
    if not delimiter:
        return None
    command = _heredoc_command(tokens[:at])
    shell = not command or _reads_stdin(command)
    return _Heredoc(delimiter, strip_tabs, shell, bare=not command)


def _heredoc_command(before: list[str]) -> list[str]:
    """The command a here-document goes to: after a group, as in `{ cat; } <<EOF`,
    the group's first command (Kody on #369); else the command after the last
    control operator."""
    opened = _group_start(before)
    if opened is not None:
        commands = _commands(before[opened + 1 : -1])
        return commands[0] if commands else []
    starts = [i for i, token in enumerate(before) if token in _BOUNDARIES]
    return before[starts[-1] + 1 :] if starts else before


def _group_start(before: list[str]) -> int | None:
    """Where the group ``before`` ends with opens; None if it ends with none."""
    closer = before[-1] if before else ""
    if closer not in _GROUPS:
        return None
    depth = 0
    for index in range(len(before) - 1, -1, -1):
        if before[index] == closer:
            depth += 1
        elif before[index] == _GROUPS[closer]:
            depth -= 1
            if depth == 0:
                return index
    return None


def _reads_stdin(command: list[str]) -> bool:
    """Whether ``command`` is a shell that reads its script from standard input: a
    shell with options only, and no `-c` string."""
    if _command_name(command[0]) not in _SHELLS:
        return False
    index = 1
    while index < len(command):
        option = command[index]
        if option in _VALUE_OPTIONS:
            index += 2
            continue
        if not option.startswith("-") or (
            not option.startswith("--") and "c" in option
        ):
            return False
        index += 1
    return True


def _heredoc_line(
    document: _Heredoc, number: int, text: str, found: list[tuple[int, str]]
) -> _Heredoc | None:
    """Read one line of a here-document: its end, or a body line, kept when a shell
    reads it. A bare document whose shebang names no shell is that program's."""
    body = text.lstrip("\t") if document.strip_tabs else text
    if body == document.delimiter:
        return None
    if document.bare and document.first and body.startswith("#!"):
        document.shell = _shell_shebang(body)
    document.first = False
    if document.shell:
        found.append((number, body))
    return document


def _past_run_options(text: str) -> str:
    """A `RUN` instruction's text after its own options, as `--mount=type=cache` or
    `--network=none`, which Docker reads before the shell text (Codex on #369)."""
    while text.startswith("--"):
        parts = text.split(None, 1)
        text = parts[1] if len(parts) > 1 else ""
    return text


def _escape(lines: list[str]) -> str:
    """The character that continues a Dockerfile's line: `\\`, or the one its
    `escape` parser directive names, as `` ` ``. A directive stands only before any
    other line; after one, it is a comment (CodeAnt on #369)."""
    for text in lines:
        body = text.strip()
        key, equals, value = body[1:].partition("=")
        if not body.startswith("#") or not equals or not key.strip().isalnum():
            break
        if key.strip().lower() == "escape" and value.strip() in ("\\", "`"):
            return value.strip()
    return "\\"


def _workflow(lines: list[str]) -> list[tuple[int, str]]:
    """Each workflow `run` value, where YAML finds it, so any spelling of the key, a
    flow mapping, any block indicator and an alias's anchor are read as YAML reads
    them (Codex and CodeAnt on #369). A block's lines are read each on its own;
    another value is read as YAML decodes it, on the line it starts on. A workflow
    YAML cannot read is read whole, so it cannot pass as clean."""
    try:
        values = _run_values(yaml.compose_all("\n".join(lines), Loader=yaml.SafeLoader))
    except (yaml.YAMLError, RecursionError):
        return list(enumerate(lines, start=1))
    # Where each line starts. YAML also ends a line at NEL or U+2028, so a line is
    # found by its offset, never by YAML's count.
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    found: list[tuple[int, str]] = []
    for node in values:
        first = bisect.bisect_right(starts, node.start_mark.index)
        if node.style not in ("|", ">"):
            found.append((first, node.value))
            continue
        end = node.end_mark.index
        last = bisect.bisect_right(starts, end)
        if end == starts[last - 1]:
            last -= 1
        found.extend(
            (number, lines[number - 1]) for number in range(first + 1, last + 1)
        )
    return found


def _run_values(documents: Iterable[yaml.Node | None]) -> list[yaml.ScalarNode]:
    """Each scalar a `run` key names, once. An alias is its anchor's node, so each
    node is walked once, however often it is named, and a recursive one ends."""
    walked: set[int] = set()
    found: dict[int, yaml.ScalarNode] = {}
    stack: list[yaml.Node] = [
        document for document in documents if document is not None
    ]
    while stack:
        node = stack.pop()
        if id(node) in walked:
            continue
        walked.add(id(node))
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                if (
                    isinstance(key, yaml.ScalarNode)
                    and key.value == "run"
                    and isinstance(value, yaml.ScalarNode)
                ):
                    found[id(value)] = value
                stack.append(value)
        elif isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
    return list(found.values())


def _fenced(lines: list[str]) -> list[tuple[int, str]]:
    """The lines of each fenced shell block; a console block's `$ ` prompt goes. A
    fence opens with three or more backticks or tildes, and only a bare run of at
    least as many of the same character closes it (CodeAnt on #369)."""
    found: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    language = ""
    for number, text in enumerate(lines, start=1):
        marker = _fence(text.strip())
        if fence is None:
            if marker is not None:
                fence, language = (marker[0], marker[1]), marker[2]
            continue
        if _closes(marker, fence):
            fence = None
            continue
        if language in _FENCES:
            found.append((number, text.lstrip().removeprefix("$ ")))
    return found


def _closes(marker: tuple[str, int, str] | None, fence: tuple[str, int]) -> bool:
    """Whether a line's fence closes the open one: the same character, at least as
    many, and no info string."""
    return (
        marker is not None
        and marker[0] == fence[0]
        and marker[1] >= fence[1]
        and not marker[2]
    )


def _fence(stripped: str) -> tuple[str, int, str] | None:
    """A fence's character, its length and its info string, or None for a line that
    is no fence."""
    for character in "`~":
        length = len(stripped) - len(stripped.lstrip(character))
        if length >= 3:
            return character, length, stripped[length:].strip()
    return None
