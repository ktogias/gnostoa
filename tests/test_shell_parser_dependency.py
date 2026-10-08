"""The pinned shell parser pair is installed, compatible, and reads the constructs
the shell reader relies on (Decision 0108).

The surface extraction below is interim. Decision 0108's item 1 makes host-language
extraction the reader's own (#369), and nothing on `main` owns it yet. When #369
lands, this smoke consumes the reader's extraction and these helpers are deleted, so
the two cannot drift apart (Claude on #394)."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
import tarfile
import tempfile
import tomllib
import unittest
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from tools.repository_scope import SOURCE_MANIFEST, candidate_paths

ROOT = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "shell_parser_probe.py"
# `env`'s documented options: GNU coreutils' `env --help`, and BSD's `-P`.
ENV_FLAGS = set("i0v")
ENV_ARGUMENT_FLAGS = set("uCaPS")
ENV_LONG_FLAGS = {
    "ignore-environment",
    "null",
    "debug",
    "list-signal-handling",
    "block-signal",
    "default-signal",
    "ignore-signal",
    "help",
    "version",
}
ENV_LONG_ARGUMENT = {"unset", "chdir", "argv0"}
ASSIGNMENT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
# How many chained `env` invocations a shebang may make.
ENV_CHAIN_LIMIT = 3
# A name shaped like a shell, such as a version-suffixed `bash5`.
SHELL_LIKE = re.compile(r"\A[a-z]*sh[\d.]*\Z")
SHELLS = {"sh", "bash", "dash", "ash"}
OTHER_SHELLS = {
    "zsh",
    "ksh",
    "mksh",
    "oksh",
    "fish",
    "csh",
    "tcsh",
    "yash",
    "posh",
    "hush",
}
# A multi-call binary runs the applet its first argument names, such as `sh`.
MULTI_CALL = {"busybox", "toybox"}

# The YAML keys that hold shell in a CI definition. They are looked for in the
# loaded document, wherever and however written: flow style (CodeAnt on #394), quoted,
# or as an explicit `? key` (Codex on #396).
CI_KEYS = {"run", "script", "before_script", "after_script", "pre_get_sources_script"}
GITLAB_KEYS = ("before_script", "script", "after_script")
# GitLab's job hooks: commands the runner runs before the clone (Codex on #396).
GITLAB_HOOKS = {"pre_get_sources_script"}
BOM = b"\xef\xbb\xbf"
# The instruction files whose shell fences agents run, found by name at any depth.
INSTRUCTION_FILES = {"AGENTS.md"}
# A top-level CommonMark fence line: up to three spaces of indent, then three or more
# backticks or tildes (CommonMark 0.31.2, section 4.5).
FENCE_LINE = re.compile(r"(?P<indent> {0,3})(?P<fence>`{3,}|~{3,})(?P<info>.*)")
# A shell fence's opener, and what a container's prefix is made of: block-quote and
# list markers, and indent. A shell fence behind such a prefix is in a list item, a
# block quote or deeper indent; this reader reads the top level only, so it fails
# closed. The prefix is stripped, not matched, so no input backtracks (CodeQL and
# Codacy on #396).
SHELL_FENCE_OPEN = re.compile(
    r"(?:`{3,}|~{3,})[ \t]*(?:bash|sh|shell)(?:[ \t]|$)", re.I
)
CONTAINER_PREFIX = " \t>-+*.)0123456789"
SHELL_INFO = {"bash", "sh", "shell"}
# The runner labels whose implicit shell is bash.
BASH_RUNNERS = {
    # GitHub's documented hosted labels with a Linux or macOS image. A custom
    # self-hosted label, such as `ubuntu-builder`, may name any runner (Codex on
    # #396), so only these imply bash.
    "ubuntu-latest",
    "ubuntu-24.04",
    "ubuntu-22.04",
    "ubuntu-24.04-arm",
    "ubuntu-22.04-arm",
    "macos-latest",
    "macos-15",
    "macos-14",
    "macos-13",
    *(
        f"macos-{v}-{size}"
        for v in ("latest", "15", "14", "13")
        for size in ("large", "xlarge")
    ),
    # A self-hosted runner's operating-system label.
    "linux",
    "macos",
}
# What a program's name is made of; a word with quotes, spaces or escapes names none.
PROGRAM = re.compile(r"[\w./+-]+")
# GNU env's `-S` escapes and what each yields (coreutils `env.c`, `build_argv`).
ENV_ESCAPES = {
    **{char: char for char in "\"#$'\\"},
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}
ENV_SPACE = " \t\n\v\f\r"
# What a `-S` step yields besides a character: a separator, or the string's end.
ENV_SEPARATE, ENV_END = "<separate>", "<end>"
# Bash's long options (bash(1)): those that take a word, and the flags.
BASH_LONG_ARGUMENT = {"init-file", "rcfile"}
BASH_LONG_FLAGS = {
    "debugger",
    "dump-po-strings",
    "dump-strings",
    "help",
    "login",
    "noediting",
    "noprofile",
    "norc",
    "posix",
    "pretty-print",
    "restricted",
    "verbose",
    "version",
}
# The single-letter shell options that take a word: `-o` an option, `-O` a shopt.
SHELL_OPTION_WORDS = set("oO")
# A BuildKit here-document word: an optional descriptor, `<<`, an optional `-`, and
# a name holding no `<` (BuildKit's `frontend/dockerfile/parser`, measured on #396).
HEREDOC_WORD = re.compile(r"\d*<<-?[^<]*")
# A documentation placeholder, such as `<exact-40-character-parent-sha>`: not shell.
PLACEHOLDER = re.compile(r"<[a-z0-9][a-z0-9-]*>")
# A `RUN` or `SHELL`, also as a trigger that `ONBUILD` defers to a later build
# (CodeAnt on #396).
RUN = re.compile(r"[ \t]*(?:ONBUILD[ \t]+)?(?P<instruction>RUN|SHELL)[ \t]+(.*)", re.I)
RUN_FLAGS = re.compile(r"\A(?:--[a-z-]+(?:=\S*)?[ \t]+)*")
MAKEFILE = re.compile(r"\A(?:GNUmakefile|[Mm]akefile|.+\.mk)\Z")
CONTAINER_FILE = re.compile(r"(?i)\A(?:.*\.)?(?:dockerfile|containerfile)(?:\..*)?\Z")


def _probe(scripts: list[str]) -> dict[str, object]:
    """The probe's answer for ``scripts``, from a child process: a native crash fails
    here, as an error the test reports."""
    done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        [sys.executable, str(PROBE)],
        input=json.dumps(scripts),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if done.returncode != 0:
        raise AssertionError(
            f"the parser probe exited {done.returncode}: {done.stderr[-2000:]}"
        )
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"the parser probe answered no JSON ({exc}): {done.stdout[-2000:]!r}"
        ) from exc
    if not isinstance(answer, dict) or set(answer) != {"abi", "facts"}:
        raise AssertionError(
            f"the parser probe answered another shape: {done.stdout[-2000:]!r}"
        )
    return answer


def _mask_expressions(run: str, path: Path) -> str:
    """Each Actions expression as underscores of its own width, each line break
    kept, so the shell's lines stay where they were (CodeAnt on #394). An
    expression ends at the first `}}` outside its string literals; an unclosed one
    fails closed (Codex on #396)."""
    masked: list[str] = []
    index = 0
    while (start := run.find("${{", index)) != -1:
        end = _expression_end(run, start + 3)
        if end is None:
            raise AssertionError(
                f"{path}: an unclosed expression; extend this extraction"
            )
        masked.extend((run[index:start], re.sub(r"[^\n]", "_", run[start:end])))
        index = end
    return "".join(masked) + run[index:]


def _expression_end(text: str, index: int) -> int | None:
    """Where an expression ends: after its first `}}` outside a string literal.
    Strings quote with `'`, and a doubled `''` inside one is a quote (GitHub's
    expression syntax), so toggling on each `'` reads both."""
    quoted = False
    while index < len(text):
        if text[index] == "'":
            quoted = not quoted
        elif not quoted and text.startswith("}}", index):
            return index + 2
        index += 1
    return None


def _masked(match: re.Match[str]) -> str:
    """A placeholder as a plain word of its own width: `<ref>` becomes `_ref_`."""
    return "_" + match.group(0)[1:-1] + "_"


def _facts(scripts: list[str]) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = _probe(scripts)["facts"]  # type: ignore[assignment]
    return facts


def _workflow_runs(path: Path) -> list[str]:
    """Each shell `run:` value of a workflow or action, with its expressions masked.
    A step, or a job's or workflow's default, in another language fails closed:
    this reads shell only."""
    return _github_runs(path, _load_yaml(path))


def _load_yaml(path: Path) -> object:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise AssertionError(f"{path}: not YAML: {exc}") from exc


def _entered(node: object, above: frozenset[int], where: str) -> frozenset[int]:
    """The containers above a node's children: a container already above is a
    recursive YAML alias, which fails closed. An anchor merely reused elsewhere is not
    above itself, and is read."""
    if id(node) in above:
        raise AssertionError(f"{where}: a recursive YAML alias; extend this extraction")
    return above | {id(node)}


def _runner_shell(runs_on: object) -> str | None:
    """The shell a job's runner gives a `run` without one: bash on Linux and macOS.
    On Windows it is PowerShell, and an expression or a group is decided at run
    time, so neither is known (GitHub's workflow syntax, `defaults.run`)."""
    labels = runs_on if isinstance(runs_on, list) else [runs_on]
    names = [label for label in labels if isinstance(label, str) and "${{" not in label]
    if len(names) != len(labels) or any("windows" in name.lower() for name in names):
        return None
    return "bash" if any(name.lower() in BASH_RUNNERS for name in names) else None


def _github_context(
    path: Path, node: dict[str, object], default: str | None, runner: str | None
) -> tuple[str | None, str | None]:
    """The nearest `defaults.run.shell` and the job's runner's shell, for the
    nodes below this one. A default other than bash or sh fails closed."""
    defaults = node.get("defaults")
    run = defaults.get("run") if isinstance(defaults, dict) else None
    if isinstance(run, dict) and "shell" in run:
        default = run["shell"]
        if default not in ("bash", "sh"):
            raise AssertionError(
                f"{path}: a `{default}` default; extend this extraction"
            )
    if "runs-on" in node:
        runner = _runner_shell(node["runs-on"])
    return default, runner


def _step_run(path: Path, step: dict[str, object], shell: object) -> list[str]:
    """A step's `run`, with its expressions masked, read with its shell. A step
    without one runs an action; a `run` that is not a string fails closed (Claude on
    #396)."""
    if "run" not in step:
        return []
    run = step["run"]
    if not isinstance(run, str):
        raise AssertionError(
            f"{path}: a `run` that is not a string; extend this extraction"
        )
    _check_step_shell(path, shell)
    return [_mask_expressions(run, path)]


def _check_step_shell(path: Path, shell: object) -> None:
    """A step's shell: its own, else its default, else its runner's. Unknown, or
    neither bash nor sh, it fails closed."""
    if shell is None:
        raise AssertionError(
            f"{path}: a `run` whose shell is decided by its runner; "
            "extend this extraction"
        )
    if shell not in ("bash", "sh"):
        raise AssertionError(f"{path}: a `{shell}` step; extend this extraction")


def _github_runs(path: Path, document: object) -> list[str]:
    """Each step's `run`, read where GitHub runs one: a workflow's
    `jobs.<id>.steps[*]`, or a composite action's `runs.steps[*]`. A `run` key
    elsewhere, such as a variable in `env`, is data (Codex on #396). A step's shell
    is its own, else its job's or the workflow's `defaults.run.shell`, else its
    runner's. Another shape on those paths fails closed, and so does a recursive
    alias along them (CodeAnt on #396)."""
    if not isinstance(document, dict) or not ("jobs" in document or "runs" in document):
        if _has_shell_key(path):
            raise _refuse(path.name, "shell in an unknown GitHub shape")
        return []
    above = _entered(document, frozenset(), path.name)
    default, _ = _github_context(path, document, None, None)
    if "runs" in document:
        runs = _mapping(document["runs"], "runs", path)
        return _github_steps(path, runs.get("steps", []), above, None)
    jobs = _mapping(document["jobs"], "jobs", path)
    above = _entered(jobs, above, path.name)
    found: list[str] = []
    for job in jobs.values():
        job = _mapping(job, "a job", path)
        job_default, runner = _github_context(path, job, default, None)
        found.extend(
            _github_steps(
                path,
                job.get("steps", []),
                _entered(job, above, path.name),
                job_default or runner,
            )
        )
    return found


def _mapping(node: object, what: str, path: Path) -> dict[str, object]:
    if not isinstance(node, dict):
        noun = "jobs that are" if what == "jobs" else f"{what} that is"
        raise _refuse(path.name, f"{noun} not a mapping")
    return node


def _github_steps(
    path: Path, steps: object, above: frozenset[int], shell: str | None
) -> list[str]:
    """Each step's `run`, with `shell` the one a step without its own takes."""
    if not isinstance(steps, list):
        raise _refuse(path.name, "steps that are not a list")
    above = _entered(steps, above, path.name)
    found: list[str] = []
    for step in steps:
        step = _mapping(step, "a step", path)
        _entered(step, above, path.name)
        found.extend(_step_run(path, step, step.get("shell") or shell))
    return found


def _gitlab_scripts(document: dict[str, object]) -> list[str]:
    """Each GitLab CI job's (and `default`'s) hook commands, `before_script`,
    `script` and `after_script`, and the deprecated top-level ones, in document
    order. A list is the lines the runner's shell runs in turn."""
    found: list[str] = []
    for key, value in document.items():
        if key in GITLAB_KEYS:
            # A deprecated but valid global lifecycle script (Codex on #396).
            found.extend(_script_value(value))
        elif isinstance(value, dict):
            found.extend(_gitlab_hooks(value))
            for name in GITLAB_KEYS:
                found.extend(_script_value(value.get(name)))
    return found


def _gitlab_hooks(job: dict[str, object]) -> list[str]:
    """A job's hook commands, which run before its scripts. A hook this reader does
    not know fails closed."""
    hooks = job.get("hooks")
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        raise AssertionError(
            "GitLab hooks that are not a mapping; extend this extraction"
        )
    for hook in hooks:
        if hook not in GITLAB_HOOKS:
            raise AssertionError(
                f"an unknown GitLab hook `{hook}`; extend this extraction"
            )
    return _script_value(hooks.get("pre_get_sources_script"))


def _script_value(value: object) -> list[str]:
    """A `before_script`, `script` or `after_script` value as shell: a string, or a
    list of lines."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return ["\n".join(_script_lines(value))]
    return []


def _script_lines(value: list[object]) -> list[str]:
    """A GitLab `script` array, flattened at any depth as GitLab flattens nested
    arrays (YAML anchors and aliases build them). A line that is not a string fails
    closed rather than being stringified (CodeAnt on #396). A `!reference` tag never
    reaches here: the YAML load refuses it, and that fails closed (cubic on #396)."""
    lines: list[str] = []
    top = _entered(value, frozenset(), "a GitLab script")
    stack: list[tuple[object, frozenset[int]]] = [
        (item, top) for item in reversed(value)
    ]
    while stack:
        item, above = stack.pop()
        if isinstance(item, list):
            inner = _entered(item, above, "a GitLab script")
            stack.extend((nested, inner) for nested in reversed(item))
        elif isinstance(item, str):
            lines.append(item)
        else:
            raise AssertionError(
                f"a `{type(item).__name__}` script line; extend this extraction"
            )
    return lines


def _github_shaped(document: object) -> bool:
    """A GitHub workflow (`on` and `jobs`; YAML reads a bare `on` as true) or action
    (`runs.using`). A GitLab job may itself be named `jobs` or `runs` (CodeAnt on
    #396)."""
    if not isinstance(document, dict):
        return False
    workflow = isinstance(document.get("jobs"), dict) and (
        "on" in document or True in document
    )
    runs = document.get("runs")
    return workflow or (isinstance(runs, dict) and "using" in runs)


def _ci_shell(path: Path, under_github: bool) -> list[str]:
    """The shell of a CI definition, read by its shape wherever it sits: a GitHub
    workflow or action, or a GitLab CI file. A YAML file outside `.github` that
    holds a shell key in another shape fails closed (CodeAnt on #394)."""
    if not under_github and not _has_shell_key(path):
        return []
    document = _load_yaml(path)
    if under_github or _github_shaped(document):
        return _github_runs(path, document)
    if isinstance(document, dict) and (
        "stages" in document
        or "default" in document
        or any(isinstance(job, dict) and "script" in job for job in document.values())
    ):
        return _gitlab_scripts(document)
    raise AssertionError(
        f"{path.name}: shell in an unknown CI shape; extend this extraction"
    )


def _has_shell_key(path: Path) -> bool:
    """Whether any mapping in a YAML file has a key that holds shell in a CI
    definition. The file is composed, not constructed: its node graph is read
    without its tags' meaning, so a tag the safe loader refuses, such as
    `mkdocs.yml`'s `!!python/name:`, hides no key. Extraction still loads safely,
    so a tagged CI file, such as one with GitLab's `!reference`, fails closed. Each
    node is visited once, so a recursive alias ends."""
    try:
        root = yaml.compose(
            path.read_text(encoding="utf-8-sig"), Loader=yaml.SafeLoader
        )
    except yaml.YAMLError as exc:
        raise AssertionError(f"{path}: not YAML: {exc}") from exc
    seen: set[int] = set()
    stack: list[yaml.Node | None] = [root]
    while stack:
        node = stack.pop()
        if not isinstance(node, yaml.CollectionNode) or id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
            continue
        for key, value in node.value:
            if isinstance(key, yaml.ScalarNode) and key.value in CI_KEYS:
                return True
            stack.extend((key, value))
    return False


def _refuse(name: str, reason: str) -> AssertionError:
    return AssertionError(f"{name}: {reason}; extend this extraction")


def _shebang_command(head: bytes, name: str) -> str:
    """The name of the command a shebang line runs. Through `env`, its whole
    documented grammar is read (GNU `env --help`, and BSD's `-P`): options and their
    arguments, `-S` strings split again, then assignments, then the command. A word
    outside that grammar, a line that cannot be split, or no command fails closed, so
    nothing is guessed (Codex, Claude and CodeAnt on #394)."""
    try:
        line = head[2:].split(b"\n", 1)[0].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _refuse(name, "an unreadable shebang") from exc
    # A kernel splits on whitespace and reads no quotes; `env -S` reads its own.
    words = line.split()
    # A chained `env` is followed, to a bound (Claude on #396).
    for _ in range(ENV_CHAIN_LIMIT):
        if not words or Path(words[0]).name != "env":
            break
        words = _env_operands(words[1:], name)
    if words and Path(words[0]).name in MULTI_CALL:
        words = words[1:]
    if not words or Path(words[0]).name == "env" or not PROGRAM.fullmatch(words[0]):
        raise _refuse(name, "an unreadable shebang")
    return Path(words[0]).name


def _env_operands(rest: list[str], name: str) -> list[str]:
    """`env`'s arguments after its options and assignments: the command and its
    arguments."""
    while rest and rest[0].startswith("-") and rest[0] != "--":
        word, rest = rest[0], rest[1:]
        if word == "-":
            continue
        handler = _env_long_option if word.startswith("--") else _env_short_options
        rest = handler(word, rest, name)
    if rest and rest[0] == "--":
        rest = rest[1:]
    while rest and ASSIGNMENT.match(rest[0]):
        rest = rest[1:]
    return rest


def _env_long_option(word: str, rest: list[str], name: str) -> list[str]:
    option, equals, value = word[2:].partition("=")
    if option in ENV_LONG_FLAGS:
        return rest
    if option == "split-string":
        return _env_split(" ".join([value, *rest]), name)
    if option not in ENV_LONG_ARGUMENT:
        raise _refuse(name, f"an unknown env option `{word}`")
    if not equals:
        _, rest = _env_argument(rest, name)
    return rest


def _env_short_options(word: str, rest: list[str], name: str) -> list[str]:
    for index, letter in enumerate(word[1:], start=1):
        if letter in ENV_FLAGS:
            continue
        if letter not in ENV_ARGUMENT_FLAGS:
            raise _refuse(name, f"an unknown env option `{word}`")
        value = word[index + 1 :]
        if letter == "S":
            return _env_split(" ".join([value, *rest]), name)
        if not value:
            _, rest = _env_argument(rest, name)
        return rest
    return rest


def _env_split(value: str, name: str) -> list[str]:
    """GNU `env -S`'s words, read as `env` reads them (coreutils `env.c`,
    `build_argv`). Linux passes a shebang's rest as one argument, so `-S` takes the
    rest of the line (rejoined here). Quotes group; outside them, whitespace and
    `\\_` separate; `#` at a word's start and `\\c` end the string. An expansion,
    which the environment decides, an unknown escape or an open quote fails closed
    (CodeAnt on #396)."""
    words: list[str] = []
    separated, quote, index = True, "", 0
    while index < len(value):
        added, index, quote = _env_step(value, index, quote, separated, name)
        if added == ENV_END:
            return words
        if added == ENV_SEPARATE:
            separated = True
            continue
        if separated:
            words.append("")
            separated = False
        words[-1] += added
    if quote:
        raise _refuse(name, "an unreadable shebang")
    return words


def _env_argument(rest: list[str], name: str) -> tuple[str, list[str]]:
    if not rest:
        raise _refuse(name, "an unreadable shebang")
    return rest[0], rest[1:]


def _env_step(
    value: str, index: int, quote: str, separated: bool, name: str
) -> tuple[str, int, str]:
    """One step of reading a `-S` string at `index`: what it adds (a character, ""
    for an opening or closing quote, which starts a word, `ENV_SEPARATE` or
    `ENV_END`), the next index, and the quote then open."""
    char = value[index]
    index += 1
    if char in "'\"" and quote in ("", char):
        return "", index, "" if quote else char
    if char in ENV_SPACE and not quote:
        return ENV_SEPARATE, index, quote
    if char == "#" and separated:
        return ENV_END, index, quote
    if char == "$" and quote != "'":
        raise _refuse(name, "an unreadable shebang")
    # Inside single quotes, only a doubled backslash and `\'` are escapes.
    if char != "\\" or (quote == "'" and value[index : index + 1] not in ("\\", "'")):
        return char, index, quote
    return _env_escape(value[index : index + 1], quote, name), index + 1, quote


def _env_escape(escape: str, quote: str, name: str) -> str:
    """What a `-S` escape yields. `\\c` ends the string, and `\\_` separates
    words outside quotes and is a space inside them. An unknown escape, `\\c`
    inside quotes, or a backslash at the end fails closed."""
    if escape == "c" and not quote:
        return ENV_END
    if escape == "_":
        return " " if quote else ENV_SEPARATE
    if escape not in ENV_ESCAPES:
        raise _refuse(name, "an unreadable shebang")
    return ENV_ESCAPES[escape]


def _exec_form_shell(argv: list[str]) -> list[str]:
    """An exec-form `RUN` of `sh`, `bash`, `dash` or `ash` still hands its `-c`
    command to that shell; another shell fails closed (cubic on #396). The options
    are read as the shell reads them, up to the first word that is not one. With
    `-c` among them, that word is the command; otherwise it is a script's path
    (CodeAnt on #396). A multi-call binary's applet is the program."""
    if argv and Path(argv[0]).name in MULTI_CALL:
        argv = argv[1:]
    program = Path(argv[0]).name if argv else ""
    if program in OTHER_SHELLS:
        raise AssertionError(f"an exec-form `{program}` RUN; extend this extraction")
    if program not in SHELLS:
        return []
    inline, words = _shell_options(argv[1:])
    if not inline:
        return []
    if words[:1] == ["-"]:
        words = words[1:]
    if not words:
        raise AssertionError("a `-c` without its command; extend this extraction")
    return [words[0]]


def _shell_options(words: list[str]) -> tuple[bool, list[str]]:
    """Whether `-c` is among a shell's options, and the words after the options."""
    inline = False
    while words and words[0][:1] in ("-", "+") and len(words[0]) > 1:
        word, words = words[0], words[1:]
        if word == "--":
            break
        if word.startswith("--"):
            words = _shell_long_option(word, words)
            continue
        if "c" in word[1:]:
            if word[0] == "+":
                raise _unknown_shell_option(word)
            inline = True
        for _ in range(sum(letter in SHELL_OPTION_WORDS for letter in word[1:])):
            words = _shell_option_word(words)
    return inline, words


def _shell_long_option(word: str, words: list[str]) -> list[str]:
    if word[2:] in BASH_LONG_ARGUMENT:
        return _shell_option_word(words)
    if word[2:] not in BASH_LONG_FLAGS:
        raise _unknown_shell_option(word)
    return words


def _unknown_shell_option(word: str) -> AssertionError:
    return AssertionError(f"an unknown shell option `{word}`; extend this extraction")


def _shell_option_word(words: list[str]) -> list[str]:
    """The words after an option's own word."""
    if not words:
        raise AssertionError("a shell option without its word; extend this extraction")
    return words[1:]


def _exec_form(command: str) -> bool:
    """Whether a `RUN` is in exec form: a JSON list of strings. A shell command that
    starts with `[`, such as a test, is shell (CodeAnt on #394)."""
    try:
        argv = json.loads(command)
    except json.JSONDecodeError:
        return False
    return isinstance(argv, list) and all(isinstance(word, str) for word in argv)


def _check_shell_instruction(argument: str) -> None:
    """A Dockerfile `SHELL` keeps the `RUN` lines shell only when it names `sh`,
    `bash`, `dash` or `ash`; another program fails closed (CodeAnt on #394)."""
    try:
        argv = json.loads(argument)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"an unreadable SHELL: {argument!r}") from exc
    program = Path(argv[0]).name if isinstance(argv, list) and argv else ""
    if program not in SHELLS:
        raise AssertionError(f"a `{program}` SHELL; extend this extraction")


def _dockerfile_runs(text: str) -> list[str]:
    """Each shell-form `RUN` instruction, as Docker hands it to the shell: its
    continuation lines joined, comment lines inside it dropped, its flags removed.
    The exec form is not shell; a here-document or another escape character fails
    closed."""
    if re.search(r"^#[ \t]*escape[ \t]*=", text, re.M | re.I):
        raise AssertionError("a Dockerfile escape directive; extend this extraction")
    runs: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = RUN.fullmatch(lines[index])
        index += 1
        if match is None:
            continue
        command = match.group(2)
        if match["instruction"].upper() == "SHELL":
            _check_shell_instruction(command)
            continue
        while command.endswith("\\") and index < len(lines):
            line = lines[index]
            index += 1
            if not line.lstrip().startswith("#"):
                command = command[:-1] + line
        command = RUN_FLAGS.sub("", command)
        if _exec_form(command):
            runs.extend(_exec_form_shell(json.loads(command)))
            continue
        # BuildKit reads a here-document from a whole word, its quotes kept; `<<`
        # inside quotes, inside a word or as `<<<` is shell (CodeAnt and cubic on
        # #396).
        try:
            words = shlex.split(command, posix=False)
        except ValueError as exc:
            raise AssertionError(
                f"an unreadable RUN: {command!r}; extend this extraction"
            ) from exc
        if any(HEREDOC_WORD.fullmatch(word) for word in words):
            raise AssertionError("a RUN here-document; extend this extraction")
        runs.append(command)
    return runs


def _files(root: Path) -> list[Path]:
    """The repository's candidate files, from their owner: Git's tracked files in a
    checkout, or the runtime image's source manifest (`tools/repository_scope.py`).
    A hidden source directory is read like any other; an untracked file is not
    (Codex on #394)."""
    return [
        path
        for relative in candidate_paths(root)
        if (path := root / relative).is_file() and not path.is_symlink()
    ]


def _shell_surfaces(root: Path = ROOT) -> dict[str, str]:
    """Every shell surface of the kinds the frozen corpus held (Decision 0108), and
    GitLab CI's:
    - each workflow or action `run:` value, and each GitLab CI script, by the CI
      definition's shape, anywhere;
    - each `sh`, `bash`, `dash` or `ash` script, by its shebang's interpreter,
      anywhere; another shell's script fails closed;
    - each shell fence of the instruction files, its placeholders masked;
    - each shell-form `RUN` of the Dockerfile.
    A Make recipe or another container file fails closed: none is tracked, and none
    was in the corpus."""
    surfaces: dict[str, str] = {}
    for path in _files(root):
        surfaces.update(_surfaces_of(path, path.relative_to(root).as_posix()))
    return surfaces


def _surfaces_of(path: Path, name: str) -> dict[str, str]:
    """One file's shell surfaces, by what the file is."""
    if MAKEFILE.match(path.name):
        raise _refuse(name, "a Make recipe")
    # A shebang decides first, whatever the file's name (Codex on #394).
    with path.open("rb") as handle:
        head = handle.read(256).removeprefix(BOM)
    if head.startswith(b"#!"):
        return _script_surface(path, name, head)
    if path.suffix in (".yml", ".yaml"):
        return _numbered(name, _ci_shell(path, name.startswith(".github/")))
    if path.name in INSTRUCTION_FILES:
        fences = _shell_fences(path.read_text(encoding="utf-8-sig"), name)
        return _numbered(name, [PLACEHOLDER.sub(_masked, fence) for fence in fences])
    if CONTAINER_FILE.match(path.name) and path.name != "Dockerfile":
        raise _refuse(name, "a container file")
    if path.name == "Dockerfile":
        return _numbered(name, _dockerfile_runs(path.read_text(encoding="utf-8-sig")))
    return {}


def _shell_fences(text: str, name: str) -> list[str]:
    """Each top-level shell fence's content, as CommonMark reads it. The opener's
    indent is removed from each line. A run of the opener's own character, at least
    as long and with nothing after it, closes it, or the end does. A shell fence in a
    list item or a block quote fails closed (CodeAnt, Codex, cubic and Claude on
    #396)."""
    fences: list[str] = []
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index].rstrip("\r\n")
        index += 1
        opener = FENCE_LINE.fullmatch(line)
        # A backtick fence's info string holds no backtick (CommonMark, 4.5).
        if opener is None or (opener["fence"][0] == "`" and "`" in opener["info"]):
            rest = line.lstrip(CONTAINER_PREFIX)
            prefix = line[: len(line) - len(rest)]
            if SHELL_FENCE_OPEN.match(rest) and not re.fullmatch(" {0,3}", prefix):
                raise _refuse(name, "a shell fence inside a list or quote")
            continue
        fence, indent = opener["fence"], len(opener["indent"])
        closer = re.compile(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*")
        body: list[str] = []
        while index < len(lines) and not closer.fullmatch(lines[index].rstrip("\r\n")):
            content = lines[index]
            body.append(content[min(indent, len(content) - len(content.lstrip(" "))) :])
            index += 1
        index += 1
        words = opener["info"].split()
        if words and words[0].lower() in SHELL_INFO:
            fences.append("".join(body))
    return fences


def _script_surface(path: Path, name: str, head: bytes) -> dict[str, str]:
    """A script read when its shebang runs `sh`, `bash`, `dash` or `ash`; another
    shell, or a shell-like name no known shell, fails closed (Claude on #394)."""
    command = _shebang_command(head, name)
    if command in OTHER_SHELLS:
        raise _refuse(name, f"a `{command}` script")
    if command not in SHELLS and SHELL_LIKE.match(command):
        raise _refuse(name, f"an unrecognised shell `{command}`")
    if command not in SHELLS:
        return {}
    # A shell script that is not UTF-8 fails here, loudly.
    return {name: path.read_text(encoding="utf-8-sig")}


def _numbered(name: str, texts: list[str]) -> dict[str, str]:
    return {f"{name}#{index}": text for index, text in enumerate(texts)}


def _declared(root: Path, *, unlisted: tuple[str, ...] = ()) -> Path:
    """``root`` with a source manifest listing its files, but ``unlisted``."""
    names = sorted(
        relative
        for path in root.rglob("*")
        if path.is_file()
        and path.name != SOURCE_MANIFEST
        and (relative := path.relative_to(root).as_posix()) not in unlisted
    )
    (root / SOURCE_MANIFEST).write_bytes(b"".join(n.encode() + b"\0" for n in names))
    return root


class ShellParserDependencyTests(unittest.TestCase):
    def test_the_pinned_pair_is_installed(self) -> None:
        """`tree-sitter` 0.26.0 segfaulted with this grammar in the evaluation, so
        the pair is pinned together; the grammar's ABI is the runtime's.

        This smoke cannot reproduce that crash: it needs the reader's nested parses
        (the assessment's "The tree-sitter 0.26.0 crash"). Changing either version
        here therefore also needs the reader re-run over the corpus first."""
        self.assertEqual("0.25.2", metadata.version("tree-sitter"))
        self.assertEqual("0.25.1", metadata.version("tree-sitter-bash"))
        self.assertEqual(15, _probe([])["abi"])

    def test_the_pair_is_declared_exactly(self) -> None:
        """An install from the package metadata alone takes the same pair as the
        locks (Codex and CodeAnt on #394; Decision 0108, items 7 and 14)."""
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        declared = project["project"]["dependencies"]
        self.assertIn("tree-sitter==0.25.2", declared)
        self.assertIn("tree-sitter-bash==0.25.1", declared)
        self.assertEqual(
            [],
            [
                line
                for line in declared
                if line.startswith("tree-sitter") and "==" not in line
            ],
        )

    def test_the_grammar_reads_what_the_shell_reader_relies_on(self) -> None:
        cases = {
            # A substitution in an assignment, then the command after it.
            "x=`date` git status": ["date", "git"],
            # Single quotes keep a substitution inert; double quotes do not.
            "echo '$(git status)'": ["echo"],
            'echo "$(git status)"': ["echo", "git"],
            # A quoted newline is part of its word.
            "echo 'abc\ndef`git status`'": ["echo"],
            # A comment's apostrophe opens no quote.
            "echo hi # it's\ngit status": ["echo", "git"],
            # A function body and a process substitution hold commands.
            "f() { git log; }": ["git"],
            "cat < <(git status)": ["cat", "git"],
            # A quoted command word keeps its quotes in the tree, so the shell
            # reader unquotes it (Kody on #394; Decision 0108, item 11).
            '"git" status': ['"git"'],
            "'git' status": ["'git'"],
            'g"i"t status': ['g"i"t'],
            'echo "$("git" status)"': ['"git"', "echo"],
            'f() { "git" status; }; f': ['"git"', "f"],
            'cat < <("git" status)': ['"git"', "cat"],
        }
        facts = _facts(list(cases))
        for (text, names), found in zip(cases.items(), facts, strict=True):
            with self.subTest(text=text):
                self.assertEqual(sorted(names), found["names"])
                self.assertEqual(0, found["errors"])
        [heredoc] = _facts(['bash 2>&1 <<EOF\n"git" status\nEOF\n'])
        self.assertEqual(['"git" status\n'], heredoc["heredocs"])
        # In source order (CodeAnt on #394).
        facts = _facts(["cat <<A\none\nA\ncat <<B\ntwo\nB\n"])
        self.assertEqual(["one\n", "two\n"], facts[0]["heredocs"])

    def test_every_shell_surface_parses_without_an_unexpected_error(self) -> None:
        """Every surface kind of the frozen corpus parses with no error. The
        instruction fences' placeholders are documentation, not shell, so each is
        masked at its own width first (Codex, Kody and CodeAnt on #394)."""
        surfaces = _shell_surfaces()
        self.assertGreater(len(surfaces), 50)
        for kind in (
            ".github/workflows/verification.yml#",
            ".gitlab-ci.yml#",
            "ci/gitlab-ci.yml#",
            "ci/github-actions.yml#",
            "Dockerfile#",
            "AGENTS.md#",
            "ci/verify",
            "knowledge/assessments/365-duplication-inventory-2026-10-05-evidence/"
            "duplicate_code.sh",
        ):
            with self.subTest(kind=kind):
                self.assertTrue(any(name.startswith(kind) for name in surfaces))
        facts = _facts(list(surfaces.values()))
        broken = {
            name for name, found in zip(surfaces, facts, strict=True) if found["errors"]
        }
        # With its placeholders masked, every surface, the instruction fences
        # included, parses with no error at all (Codex and CodeAnt on #394).
        self.assertEqual(set(), broken)
        self.assertTrue(
            any(
                Path(name.split("#")[0]).name in INSTRUCTION_FILES and "_exact-" in text
                for name, text in surfaces.items()
            )
        )


class SurfaceExtractionTests(unittest.TestCase):
    """Each extraction rule, and each case it refuses rather than misreads."""

    def test_a_run_instruction_is_read_as_docker_hands_it_to_the_shell(self) -> None:
        text = (
            "FROM base\n"
            "RUN --mount=type=bind,source=a,target=/b \\\n"
            "    set -eux; \\\n"
            "    # a comment Docker drops\n"
            "    echo 'a b'\n"
            'RUN ["python", "-V"]\n'
            "run true\n"
        )
        self.assertEqual(["set -eux;     echo 'a b'", "true"], _dockerfile_runs(text))
        # Exec form is a JSON list of strings; a shell test is not (CodeAnt on #394).
        self.assertEqual(
            ["[ -f marker ] && git status"],
            _dockerfile_runs('RUN ["python", "-V"]\nRUN [ -f marker ] && git status\n'),
        )

    def test_an_exec_form_shell_run_hands_its_command_to_the_shell(self) -> None:
        """`RUN ["bash", "-c", "…"]` still asks bash to parse its command; another
        shell in exec form fails closed (cubic on #396)."""
        self.assertEqual(
            ["git status"],
            _dockerfile_runs(
                'RUN ["/bin/bash", "-o", "pipefail", "-c", "git status"]\n'
            ),
        )
        self.assertEqual([], _dockerfile_runs('RUN ["python", "-c", "print()"]\n'))
        with self.assertRaisesRegex(AssertionError, "an exec-form `zsh` RUN"):
            _dockerfile_runs('RUN ["zsh", "-c", "git status"]\n')

    def test_a_run_here_document_or_another_escape_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "here-document"):
            _dockerfile_runs("RUN <<EOF\ngit status\nEOF\n")
        with self.assertRaisesRegex(AssertionError, "escape directive"):
            _dockerfile_runs("# escape=`\nRUN true\n")

    def test_a_dockerfile_shell_override_is_honoured_or_fails_closed(self) -> None:
        """A `SHELL` instruction to bash or sh keeps the `RUN` lines shell; to
        another program it fails closed (CodeAnt on #394)."""
        self.assertEqual(
            ["git status"],
            _dockerfile_runs(
                'SHELL ["/bin/bash", "-o", "pipefail", "-c"]\nRUN git status\n'
            ),
        )
        with self.assertRaisesRegex(AssertionError, "a `pwsh` SHELL"):
            _dockerfile_runs('SHELL ["pwsh", "-Command"]\nRUN Write-Output hi\n')

    def test_a_workflow_step_is_read_with_its_expressions_masked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_bytes(
                BOM + b"jobs:\n  j:\n    defaults:\n      run:\n        shell: bash\n"
                b"    steps:\n      - run: echo ${{ github.sha }}\n"
                b"      - run: git status\n        shell: sh\n"
            )
            self.assertEqual(
                sorted(["echo " + "_" * 17, "git status"]),
                sorted(_workflow_runs(path)),
            )

    def test_a_multi_line_expression_keeps_its_line_breaks(self) -> None:
        """Masking keeps each newline, so the shell's lines stay where they were
        (CodeAnt on #394)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: |\n          echo ${{ fromJSON(\n            x) }}\n"
                "          git status\n",
                "utf-8",
            )
            runs = _workflow_runs(path)
            self.assertEqual(
                ["echo " + "_" * 13 + "\n" + "_" * 7 + "\ngit status\n"], runs
            )
            self.assertEqual(3, runs[0].count("\n"))

    def test_a_step_in_another_language_or_broken_yaml_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: print(1)\n        shell: python\n",
                "utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "`python` step"):
                _workflow_runs(path)
            path.write_text("steps: [\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "w.yml: not YAML"):
                _workflow_runs(path)

    def test_every_surface_kind_is_found_and_a_make_recipe_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "w.yml").write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: git status\n",
                "utf-8",
            )
            (root / "AGENTS.md").write_text(
                "x\n```bash\ngit log <ref>\n```\n```python\nprint()\n```\n", "utf-8"
            )
            # An instruction file is found by its name, at any depth (Codex on #394).
            (root / "sub").mkdir()
            (root / "sub" / "AGENTS.md").write_text(
                "```sh\ngit fetch <remote>\n```\n", "utf-8"
            )
            (root / "Dockerfile").write_text("FROM a\nRUN git fetch\n", "utf-8")
            (root / "deep" / "er").mkdir(parents=True)
            (root / "deep" / "er" / "tool").write_bytes(BOM + b"#!/bin/sh\ngit gc\n")
            (root / "deep" / "data.bin").write_bytes(b"\xff\xfe")
            # A hidden source directory is read; an untracked file is not (Codex on
            # #394).
            (root / ".husky").mkdir()
            (root / ".husky" / "pre-commit").write_text(
                "#!/bin/sh\ngit diff\n", "utf-8"
            )
            (root / "scratch").write_text("#!/bin/sh\nuntracked\n", "utf-8")
            self.assertEqual(
                {
                    ".github/workflows/w.yml#0": "git status",
                    "AGENTS.md#0": "git log _ref_\n",
                    "sub/AGENTS.md#0": "git fetch _remote_\n",
                    "Dockerfile#0": "git fetch",
                    "deep/er/tool": "#!/bin/sh\ngit gc\n",
                    ".husky/pre-commit": "#!/bin/sh\ngit diff\n",
                },
                _shell_surfaces(_declared(root, unlisted=("scratch",))),
            )
            (root / "deep" / "er" / "tool").write_bytes(b"#!/bin/sh\n\xff\n")
            declared = _declared(root, unlisted=("scratch",))
            with self.assertRaises(UnicodeDecodeError):
                _shell_surfaces(declared)
            (root / "deep" / "er" / "tool").unlink()
            (root / "Makefile").write_text("all:\n\tgit status\n", "utf-8")
            declared = _declared(root, unlisted=("scratch",))
            with self.assertRaisesRegex(AssertionError, "Makefile: a Make recipe"):
                _shell_surfaces(declared)

    def test_a_probe_answer_that_is_not_json_is_reported(self) -> None:
        answer = SimpleNamespace(returncode=0, stdout="warn", stderr="")
        with (
            patch("subprocess.run", return_value=answer),
            self.assertRaisesRegex(AssertionError, "answered no JSON.*'warn'"),
        ):
            _probe([])

    def test_a_probe_answer_of_another_shape_is_reported(self) -> None:
        """Amazon Q on #394: a missing key is named, not a bare KeyError."""
        for stdout in ('{"facts": []}', "[]", '{"abi": 15, "facts": [], "x": 1}'):
            answer = SimpleNamespace(returncode=0, stdout=stdout, stderr="")
            with (
                self.subTest(stdout=stdout),
                patch("subprocess.run", return_value=answer),
                self.assertRaisesRegex(AssertionError, "answered another shape"),
            ):
                _probe([])

    def test_a_default_shell_in_another_language_fails_closed(self) -> None:
        """A step inherits the job's or the workflow's `defaults.run.shell`
        (Claude on #394)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            for document in (
                "defaults:\n  run:\n    shell: pwsh\njobs:\n  j:\n    steps:\n"
                "      - run: Get-Content x\n",
                "jobs:\n  j:\n    defaults:\n      run:\n        shell: python\n"
                "    steps:\n      - run: print(1)\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "a `(pwsh|python)` default"),
                ):
                    _workflow_runs(path)

    def test_a_dockerfile_variant_fails_closed(self) -> None:
        """Only `Dockerfile` itself is read; another container file fails closed
        rather than going unread (Claude on #394)."""
        for name in ("Dockerfile.ci", "build.Dockerfile", "Containerfile"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).write_text("FROM a\nRUN true\n", "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(name=name),
                    self.assertRaisesRegex(AssertionError, "a container file"),
                ):
                    _shell_surfaces(declared)


class InterpreterAndCiShapeTests(unittest.TestCase):
    """Shell surfaces are found by what they are, not where they sit (CodeAnt and
    Claude on #394)."""

    def test_ci_definitions_are_read_by_their_shape_anywhere(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ci").mkdir()
            (root / ".gitlab-ci.yml").write_text(
                "stages: [test]\ndefault:\n  before_script:\n    - git fetch\n"
                "job:\n  stage: test\n  script:\n    - git status\n    - echo ok\n"
                "  after_script: git gc\n",
                "utf-8",
            )
            (root / "ci" / "github-actions.yml").write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: git log\n",
                "utf-8",
            )
            (root / "ci" / "policy.yml").write_text("checks:\n  - name: x\n", "utf-8")
            (root / "ci" / "flow.yml").write_text(
                'stages: [t]\njob: {stage: t, script: "git describe"}\n', "utf-8"
            )
            self.assertEqual(
                {
                    ".gitlab-ci.yml#0": "git fetch",
                    ".gitlab-ci.yml#1": "git status\necho ok",
                    ".gitlab-ci.yml#2": "git gc",
                    "ci/flow.yml#0": "git describe",
                    "ci/github-actions.yml#0": "git log",
                },
                _shell_surfaces(_declared(root)),
            )
            (root / "ci" / "other.yml").write_text(
                "pipeline:\n  steps:\n    - script: git status\n", "utf-8"
            )
            declared = _declared(root)
            with self.assertRaisesRegex(
                AssertionError, "other.yml: shell in an unknown"
            ):
                _shell_surfaces(declared)

    def test_a_checkout_s_tracked_files_are_the_universe(self) -> None:
        """In a Git checkout the tracked files are read, wherever they sit, and an
        untracked one is not; the runtime image's source manifest stands in for Git
        where there is none."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".husky").mkdir()
            (root / ".husky" / "hook").write_text("#!/bin/sh\ngit a\n", "utf-8")
            (root / "scratch").write_text("#!/bin/sh\ngit b\n", "utf-8")
            git = ["git", "-c", "init.defaultBranch=main", "-C", str(root)]
            for argv in (["init", "-q"], ["add", ".husky/hook"]):
                subprocess.run([*git, *argv], check=True, timeout=60)  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            self.assertEqual({".husky/hook"}, set(_shell_surfaces(root)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "listed").write_text("#!/bin/sh\ngit c\n", "utf-8")
            (root / "unlisted").write_text("#!/bin/sh\ngit d\n", "utf-8")
            (root / ".gnostoa-source-files").write_bytes(b"listed\0")
            self.assertEqual({"listed"}, set(_shell_surfaces(root)))

    def test_nested_gitlab_script_lists_are_flattened_and_others_fail(self) -> None:
        """GitLab flattens nested `script` arrays (anchors and aliases build them)
        at any depth; a value that is not a string fails closed rather than being
        stringified (CodeAnt on #396). A `!reference` tag fails closed at the YAML
        load: none is tracked (cubic on #396)."""
        nested: dict[str, object] = {"job": {"script": ["git a", ["git b", ["git c"]]]}}
        self.assertEqual(["git a\ngit b\ngit c"], _gitlab_scripts(nested))
        with self.assertRaisesRegex(AssertionError, "a `int` script line"):
            _gitlab_scripts({"job": {"script": ["git a", 7]}})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                ".base:\n  script: [git a]\njob:\n  script: [!reference [.base, script]]\n",
                "utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "not YAML.*!reference"):
                _ci_shell(path, under_github=False)

    def test_ci_scripts_are_found_in_every_valid_form_and_source_order(self) -> None:
        """Top-level GitLab lifecycle scripts (Codex on #396), quoted keys, and
        steps numbered in source order (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ci").mkdir()
            (root / ".gitlab-ci.yml").write_text(
                "before_script: [git a]\nafter_script: git z\njob:\n  script: [git b]\n",
                "utf-8",
            )
            (root / "ci" / "quoted.yml").write_text(
                '{"stages": ["t"], "job": {"stage": "t", "script": "git c"}}\n', "utf-8"
            )
            (root / "ci" / "order.yml").write_text(
                "on: push\njobs:\n  one:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: git first\n      - run: git second\n"
                "  two:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: git third\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                {
                    ".gitlab-ci.yml#0": "git a",
                    ".gitlab-ci.yml#1": "git z",
                    ".gitlab-ci.yml#2": "git b",
                    "ci/quoted.yml#0": "git c",
                    "ci/order.yml#0": "git first",
                    "ci/order.yml#1": "git second",
                    "ci/order.yml#2": "git third",
                },
                _shell_surfaces(declared),
            )

    def test_every_commonmark_shell_fence_form_is_read(self) -> None:
        """Up to three spaces of indent, removed from the content; three or more
        backticks or tildes, with spaces or an info string after the language; a fence
        left open to the end; a closer inside another fence is its content (CodeAnt,
        Codex, cubic and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "  ```bash\n  git d\n   git d2\n  ```\n\n"
                "````sh\ngit e\n````\n\n"
                "~~~Shell title=setup\ngit f\n~~~\n\n"
                "``` bash\ngit g\n```\n\n"
                "```text\n```bash\nnot shell\n```\n\n"
                "~~~bash\ngit h\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                ["git d\n git d2\n", "git e\n", "git f\n", "git g\n", "git h\n"],
                list(_shell_surfaces(declared).values()),
            )

    def test_a_line_of_list_markers_is_read_in_linear_time(self) -> None:
        """A container's prefix is read without backtracking: repeated list markers
        and tabs once took exponential time (CodeQL and Codacy on #396). The reader
        runs in a subprocess, so the old shape fails by its deadline instead of
        hanging the suite."""
        hostile = "*\t\t\t" * 40 + "x\n"
        # This interpreter, with a literal argv.
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [
                sys.executable,
                "-c",
                "import sys; from tests.test_shell_parser_dependency import "
                "_shell_fences; print(_shell_fences(sys.argv[1], 'AGENTS.md'))",
                hostile,
            ],
            cwd=ROOT,
            env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        self.assertEqual("[]\n", completed.stdout)

    def test_a_shell_fence_inside_a_list_or_quote_fails_closed(self) -> None:
        """This reader reads top-level fences; one in a list item or a block quote
        fails closed instead of being skipped (Codex, cubic and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for text in (
                "> ```bash\n> git a\n> ```\n",
                "1. Step:\n\n    ```bash\n    git a\n    ```\n",
                "- ```sh\n  git a\n  ```\n",
            ):
                (root / "AGENTS.md").write_text(text, "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(text=text),
                    self.assertRaisesRegex(
                        AssertionError, "a shell fence inside a list or quote"
                    ),
                ):
                    _shell_surfaces(declared)

    def test_a_fence_closes_only_on_its_own_character(self) -> None:
        """A closing fence repeats the opening character alone, so a line such as
        ```~~~ inside a backtick block does not end it (cubic and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text(
                "```bash\ngit a\n```~~~\ngit b\n````\n", "utf-8"
            )
            declared = _declared(root)
            self.assertEqual(
                {"AGENTS.md#0": "git a\n```~~~\ngit b\n"}, _shell_surfaces(declared)
            )

    def test_a_run_s_implicit_shell_is_its_runner_s(self) -> None:
        """A `run` without `shell` takes its job's or workflow's default, else its
        runner's: bash on Linux and macOS, PowerShell on Windows, unknown for an
        expression or a group. Only an established bash or sh is read (Codex on
        #396)."""
        windows = "on: push\njobs:\n  a:\n    runs-on: windows-latest\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            for document in (
                windows + "    steps:\n      - run: Write-Output hi\n",
                "on: push\njobs:\n  a:\n    runs-on: ${{ matrix.os }}\n"
                "    steps:\n      - run: git x\n",
                "on: push\njobs:\n  a:\n    runs-on: {group: g}\n"
                "    steps:\n      - run: git x\n",
                "runs:\n  using: composite\n  steps:\n    - run: git x\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "decided by its runner"),
                ):
                    _ci_shell(path, under_github=True)
            for document, expected in (
                (
                    "on: push\njobs:\n  a:\n    runs-on: macos-15\n"
                    "    steps:\n      - run: git a\n",
                    ["git a"],
                ),
                (
                    "on: push\njobs:\n  a:\n    runs-on: [self-hosted, Linux]\n"
                    "    steps:\n      - run: git b\n",
                    ["git b"],
                ),
                (
                    windows + "    steps:\n      - run: git c\n        shell: bash\n",
                    ["git c"],
                ),
                (
                    windows + "    defaults:\n      run:\n        shell: bash\n"
                    "    steps:\n      - run: git d\n",
                    ["git d"],
                ),
                (
                    "defaults:\n  run:\n    shell: sh\n"
                    + windows
                    + "    steps:\n      - run: git e\n",
                    ["git e"],
                ),
                (
                    "runs:\n  using: composite\n  steps:\n"
                    "    - run: git f\n      shell: bash\n",
                    ["git f"],
                ),
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(expected, _ci_shell(path, under_github=True))

    def test_an_exec_form_shell_s_options_are_read_as_the_shell_reads_them(
        self,
    ) -> None:
        """With `-c` among the options, the command is the first word after them;
        `-o` and `-O` take a word, and so do `--rcfile` and `--init-file`. After a
        script's path, `-c` is the script's (CodeAnt on #396)."""
        for argv, expected in (
            (["bash", "script.sh", "-c", "git a"], []),
            (["bash", "-c", "-e", "git b"], ["git b"]),
            (["bash", "-eo", "pipefail", "-c", "git c"], ["git c"]),
            (["bash", "--rcfile", "f", "-c", "git d"], ["git d"]),
            (["sh", "-c", "--", "git e", "zero"], ["git e"]),
            (["bash", "+e", "-xc", "git f"], ["git f"]),
            (["bash", "-"], []),
        ):
            with self.subTest(argv=argv):
                self.assertEqual(expected, _exec_form_shell(argv))
        for argv, reason in (
            (["bash", "--unknown", "-c", "x"], "an unknown shell option `--unknown`"),
            (["bash", "-c"], "a `-c` without its command"),
            (["bash", "-o"], "a shell option without its word"),
            (["bash", "+c", "x"], "an unknown shell option `\\+c`"),
        ):
            with (
                self.subTest(argv=argv),
                self.assertRaisesRegex(AssertionError, reason),
            ):
                _exec_form_shell(argv)

    def test_only_a_here_document_word_starts_a_here_document(self) -> None:
        """BuildKit reads a here-document from a word, quotes kept, that is an
        optional descriptor, `<<`, an optional `-` and a name holding no `<`.
        `<<` inside quotes, `cat<<EOF` and a `<<<` here-string are shell; measured
        against BuildKit (CodeAnt and cubic on #396)."""
        for line in (
            'RUN echo "a << b"',
            'RUN echo "<<EOF"',
            "RUN cat<<EOF",
            'RUN cat <<<"here"',
        ):
            with self.subTest(line=line):
                self.assertEqual([line[4:]], _dockerfile_runs(line + "\n"))
        for line in ("RUN cat <<EOF\n", "RUN cat << EOF\n", "RUN cat 3<<-EOF\n"):
            with (
                self.subTest(line=line),
                self.assertRaisesRegex(AssertionError, "here-document"),
            ):
                _dockerfile_runs(line)
        with self.assertRaisesRegex(AssertionError, "an unreadable RUN"):
            _dockerfile_runs('RUN echo "unclosed\n')

    def test_a_run_that_is_not_a_string_fails_closed(self) -> None:
        """A step's `run` is a string; any other value fails closed instead of being
        skipped. A `defaults.run` mapping of `shell` and `working-directory` is not a
        step (Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            job = "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
            for document in (
                job + "    steps:\n      - run:\n          - git status\n",
                job + "    steps:\n      - run: {git: status}\n",
                job + "    steps:\n      - run: 1\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(
                        AssertionError, "a `run` that is not a string"
                    ),
                ):
                    _ci_shell(path, under_github=True)
            path.write_text(
                job + "    defaults:\n      run:\n        shell: bash\n"
                "        working-directory: x\n    steps:\n      - run: git log\n",
                "utf-8",
            )
            self.assertEqual(["git log"], _ci_shell(path, under_github=True))

    def test_a_multi_call_binary_runs_its_applet(self) -> None:
        """`busybox sh` and `toybox sh` run a shell: in a shebang and in an exec-form
        `RUN` (CodeAnt on #396). Busybox's `hush` is another shell, which fails
        closed."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in (
                ("q", b"#!/bin/busybox sh\ngit q\n"),
                ("r", b"#!/usr/bin/env busybox ash\ngit r\n"),
                ("s", b"#!/usr/bin/toybox sh\ngit s\n"),
            ):
                (root / name).write_bytes(content)
            self.assertEqual({"q", "r", "s"}, set(_shell_surfaces(_declared(root))))
            for content, reason in (
                (b"#!/bin/busybox\ngit u\n", "u: an unreadable shebang"),
                (b"#!/bin/busybox hush\ngit u\n", "u: a `hush` script"),
            ):
                (root / "u").write_bytes(content)
                declared = _declared(root)
                with (
                    self.subTest(shebang=content),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _shell_surfaces(declared)
        self.assertEqual(
            ["git t"], _exec_form_shell(["/bin/busybox", "sh", "-c", "git t"])
        )
        with self.assertRaisesRegex(AssertionError, "an exec-form `hush` RUN"):
            _exec_form_shell(["busybox", "hush", "-c", "git t"])

    def test_only_a_step_s_run_is_shell(self) -> None:
        """GitHub runs shell at `jobs.<id>.steps[*].run` and a composite action's
        `runs.steps[*].run` only; a `run` key elsewhere, such as a variable in
        `env`, a matrix value or an action's input, is data (Codex on #396). Any
        other shape on those paths fails closed."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            path.write_text(
                "on: push\nenv:\n  run: one\njobs:\n  a:\n"
                "    runs-on: ubuntu-latest\n    env:\n      run: two\n"
                "    strategy:\n      matrix:\n        include:\n          - run: three\n"
                "    steps:\n      - run: git a\n        env:\n          run: four\n"
                "      - uses: some/action@v1\n        with:\n          run: five\n",
                "utf-8",
            )
            self.assertEqual(["git a"], _ci_shell(path, under_github=True))
            for document, reason in (
                ("on: push\njobs: [a]\n", "jobs that are not a mapping"),
                ("on: push\njobs:\n  a: x\n", "a job that is not a mapping"),
                (
                    "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps: x\n",
                    "steps that are not a list",
                ),
                (
                    "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
                    "    steps:\n      - x\n",
                    "a step that is not a mapping",
                ),
                (
                    "runs:\n  using: composite\n  steps: x\n",
                    "steps that are not a list",
                ),
                ("other:\n  run: git x\n", "shell in an unknown GitHub shape"),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=True)
            path.write_text("version: 2\nupdates: []\n", "utf-8")
            self.assertEqual([], _ci_shell(path, under_github=True))

    def test_an_expression_ends_outside_its_strings(self) -> None:
        """An Actions expression ends at the first `}}` outside its string
        literals, which quote with `'` and escape it by doubling; an unclosed one
        fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.yml"
            job = "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
            for expression in (
                "${{ format('{{Hello {0}!}}', github.actor) }}",
                "${{ 'it''s }}' }}",
            ):
                path.write_text(
                    job + "      - run: >-\n          echo " + expression + " done\n",
                    "utf-8",
                )
                with self.subTest(expression=expression):
                    self.assertEqual(
                        ["echo " + "_" * len(expression) + " done"],
                        _ci_shell(path, under_github=True),
                    )
            path.write_text(job + "      - run: echo ${{ x\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "an unclosed expression"):
                _ci_shell(path, under_github=True)

    def test_a_shell_key_is_found_however_it_is_written(self) -> None:
        """Whether a YAML file holds a shell key is read from its loaded structure,
        so YAML's explicit-key form counts like any other (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "explicit.yml"
            for document in (
                "job:\n  ? script\n  : git status\n",
                "job:\n  ? script  # the job's commands\n  : git status\n",
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(
                        ["git status"], _ci_shell(path, under_github=False)
                    )
            path.write_text("other:\n  ? run\n  : git x\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "unknown GitHub shape"):
                _ci_shell(path, under_github=True)
            # Text that merely mentions a key is not one; a tag the safe loader
            # refuses, as in mkdocs.yml, does not hide a file's keys.
            for document in (
                "note: 'run: and script: are words here'\n",
                "markdown: !!python/name:pymdownx.superfences.fence_code_format\n",
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual([], _ci_shell(path, under_github=False))
            # A tagged CI file is not read as plain data; it fails closed.
            path.write_text("job:\n  script: !reference [.setup, script]\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "not YAML"):
                _ci_shell(path, under_github=False)

    def test_an_onbuild_run_is_read(self) -> None:
        """`ONBUILD RUN` runs its command in a later build, so it is read as a `RUN`
        (CodeAnt on #396)."""
        self.assertEqual(
            ["git status", "git log"],
            _dockerfile_runs(
                'ONBUILD RUN git status\nonbuild run ["sh", "-c", "git log"]\n'
            ),
        )

    def test_a_gitlab_hook_s_commands_are_read(self) -> None:
        """`hooks:pre_get_sources_script` runs on the runner before the clone, in
        a job or in `default`; another hook fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                "default:\n  hooks:\n    pre_get_sources_script: [git a]\n"
                "job:\n  hooks:\n    pre_get_sources_script: git b\n  script: [git c]\n",
                "utf-8",
            )
            self.assertEqual(
                ["git a", "git b", "git c"], _ci_shell(path, under_github=False)
            )
            path.write_text(
                "job:\n  hooks:\n    other: git x\n  script: [git c]\n", "utf-8"
            )
            with self.assertRaisesRegex(
                AssertionError, "an unknown GitLab hook `other`"
            ):
                _ci_shell(path, under_github=False)

    def test_only_a_known_runner_label_implies_bash(self) -> None:
        """A documented GitHub-hosted Linux or macOS label, or a self-hosted
        runner's OS label, implies bash; a custom label such as `ubuntu-builder`
        may name any runner, and fails closed (Codex on #396)."""
        for runs_on in (
            "ubuntu-latest",
            "ubuntu-24.04-arm",
            "macos-15-xlarge",
            ["self-hosted", "Linux"],
        ):
            with self.subTest(runs_on=runs_on):
                self.assertEqual("bash", _runner_shell(runs_on))
        for runs_on in ("ubuntu-builder", "macos-anything", ["self-hosted", "build"]):
            with self.subTest(runs_on=runs_on):
                self.assertIsNone(_runner_shell(runs_on))

    def test_a_recursive_yaml_alias_fails_closed(self) -> None:
        """`safe_load` builds self-referential lists and mappings from recursive
        aliases; both walkers refuse a cycle rather than loop on it, and still read an
        anchor that is merely reused (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            # The GitHub walker on a workflow; the GitLab flattening on a script
            # outside `.github` (cubic on #396).
            for document, under_github in (
                ("on: push\njobs: &j\n  again: *j\n", True),
                ("job:\n  script: &s\n    - git a\n    - *s\n", False),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "a recursive YAML alias"),
                ):
                    _ci_shell(path, under_github=under_github)
            path.write_text(
                "job:\n  before_script: &s [git a]\n  script: [*s, git b]\n", "utf-8"
            )
            self.assertEqual(
                ["git a", "git a\ngit b"], _ci_shell(path, under_github=False)
            )

    def test_a_gitlab_job_named_like_github_s_keys_stays_gitlab(self) -> None:
        """A workflow has `on` and `jobs`, an action `runs.using`; a GitLab job may
        be named `jobs` or `runs` (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitlab-ci.yml").write_text(
                "jobs:\n  script: git status\nruns:\n  script:\n    - git log\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                {".gitlab-ci.yml#0": "git status", ".gitlab-ci.yml#1": "git log"},
                _shell_surfaces(declared),
            )

    def test_a_shebang_is_classified_by_its_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = {
                "a": b"#!/bin/ash\ngit a\n",
                "b": b"#!/usr/local/bin/bash\ngit b\n",
                "c": b"#!/usr/bin/env -S bash -e\ngit c\n",
                "d": b"#! /bin/dash\ngit d\n",
                "e": b"#!/usr/bin/env -S 'bash' -e\ngit e\n",
                "f": b"#!/usr/bin/env VAR=1 bash\ngit f\n",
                "g": b"#!/usr/bin/env --split-string=bash -e\ngit g\n",
                "h": b"#!/usr/bin/env -Sbash -e\ngit h\n",
                "j": b"#!/usr/bin/env -i - --unset=X -C /tmp -0v bash\ngit j\n",
                # GNU env's `-S` escapes: `\_` separates, `\c` ends the string,
                # `#` at a word's start is a comment (CodeAnt on #396).
                "m": b"#!/usr/bin/env -S bash\\_-e\ngit m\n",
                "n": b"#!/usr/bin/env -S sh\\c junk\ngit n\n",
                "o": b"#!/usr/bin/env -S bash #comment\ngit o\n",
                "p": b"#!/usr/bin/env python3\nprint()\n",
            }
            for name, content in scripts.items():
                (root / name).write_bytes(content)
            self.assertEqual(
                {"a", "b", "c", "d", "e", "f", "g", "h", "j", "m", "n", "o"},
                set(_shell_surfaces(_declared(root))),
            )
            for content in (
                b"#!\ngit u\n",
                b"#! \t\ngit u\n",
                b"#!/bin/\xffsh\ngit u\n",
                b"#!/usr/bin/env -S 'bash\ngit u\n",
                b"#!/usr/bin/env -u\ngit u\n",
                # Quotes make one word, and no program is named `bash -e`; the
                # environment decides an expansion; an unknown escape is env's
                # error (GNU coreutils, `env.c`).
                b'#!/usr/bin/env -S "bash -e"\ngit u\n',
                b'#!/usr/bin/env --split-string="bash -e"\ngit u\n',
                b'#!/usr/bin/env "bash"\ngit u\n',
                b"#!/usr/bin/env -S ${SHELL}\ngit u\n",
                b"#!/usr/bin/env -S bash\\q\ngit u\n",
            ):
                (root / "u").write_bytes(content)
                declared = _declared(root)
                with (
                    self.subTest(shebang=content),
                    self.assertRaisesRegex(AssertionError, "u: an unreadable shebang"),
                ):
                    _shell_surfaces(declared)
            (root / "u").unlink()
            # An option's argument or an assignment is not the command (Codex,
            # Claude and CodeAnt on #394).
            for content in (
                b"#!/usr/bin/env -u bash python3\nprint()\n",
                b"#!/usr/bin/env FOO=bash python3\nprint()\n",
                b"#!/usr/bin/env --chdir=/bin/sh perl\nprint 1\n",
            ):
                (root / "v").write_bytes(content)
                with self.subTest(shebang=content):
                    self.assertNotIn("v", _shell_surfaces(_declared(root)))
            (root / "v").unlink()
            # A chained env is followed to its command (Claude on #396).
            for content in (
                b"#!/usr/bin/env env bash\ngit k\n",
                b"#!/usr/bin/env -S env -i bash\ngit k\n",
            ):
                (root / "k").write_bytes(content)
                declared = _declared(root)
                with self.subTest(shebang=content):
                    self.assertIn("k", _shell_surfaces(declared))
            (root / "k").write_bytes(b"#!/usr/bin/env env env env env bash\ngit k\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "k: an unreadable shebang"):
                _shell_surfaces(declared)
            (root / "k").unlink()
            # A shell-like name that is no known shell fails closed (Claude on #394).
            (root / "q").write_bytes(b"#!/bin/bash5\ngit q\n")
            declared = _declared(root)
            with self.assertRaisesRegex(
                AssertionError, "q: an unrecognised shell `bash5`"
            ):
                _shell_surfaces(declared)
            (root / "q").unlink()
            # An option env does not document fails closed.
            (root / "x").write_bytes(b"#!/usr/bin/env --frobnicate bash\ngit x\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "x: an unknown env option"):
                _shell_surfaces(declared)
            (root / "x").unlink()
            # A shell script with a YAML name is read by its shebang (Codex on #394).
            (root / "tool.yml").write_bytes(b"#!/bin/sh\ngit y\n")
            self.assertIn("tool.yml", _shell_surfaces(_declared(root)))
            (root / "tool.yml").unlink()
            (root / "w").write_bytes(b"#!/usr/bin/env -u NAME zsh\ngit w\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "w: a `zsh` script"):
                _shell_surfaces(declared)
            (root / "w").unlink()
            (root / "z").write_bytes(b"#!/usr/bin/env zsh\ngit z\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "z: a `zsh` script"):
                _shell_surfaces(declared)


RETAINED_SCRIPTS = [
    "stress_probe.py",
    "audit_oracle.py",
    "audit_docs.py",
    "evaluate314.py",
    "corpus_scripts.py",
    "diff_parsers.py",
    "oracle.py",
    "docs.py",
    "worker.py",
    "parent.py",
    "spike.py",
    "gate.py",
    "crash_doc.py",
]


class RetainedEvidenceTests(unittest.TestCase):
    """The assessment's retained evidence is the evidence it names (Codex and
    CodeRabbit on #394)."""

    ASSESSMENT = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.md"
    EVIDENCE = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"

    ARCHIVE = (
        ROOT
        / "knowledge/assessments/0108-shell-parser-evaluation-evidence"
        / "spike-scripts.tar.gz"
    )

    def test_each_retained_script_is_a_native_file_of_its_declared_digest(
        self,
    ) -> None:
        """The scripts are retained as native `.py` files, byte for byte, in the
        evidence archive (Codex on #394; AGENTS.md: executable artifacts stay
        canonical in their native formats). The assessment declares each digest."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        declared = dict(
            re.findall(r"^\| `([\w.]+\.py)` \| `([0-9a-f]{16})…` \|", text, re.M)
        )
        with tarfile.open(self.ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            # The exact inventory, so a lost script fails too (CodeAnt on #394).
            self.assertEqual(
                sorted(RETAINED_SCRIPTS), [member.name for member in members]
            )
            self.assertEqual(sorted(RETAINED_SCRIPTS), sorted(declared))
            for member in members:
                with self.subTest(script=member.name):
                    self.assertTrue(member.isfile())
                    handle = archive.extractfile(member)
                    if handle is None:
                        self.fail(f"{member.name} has no content")
                    digest = hashlib.sha256(handle.read()).hexdigest()
                    self.assertTrue(digest.startswith(declared[member.name]))
        # The prose holds no copy that could drift from the archive.
        self.assertNotIn("````text", text)

    def test_the_assessment_prints_the_archive_s_digests(self) -> None:
        """The digest prefixes the assessment prints are those of the JSON
        evidence, for the archive and for each script, so neither can go stale
        (CodeAnt on #396)."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        scripts = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))["spike_scripts"]
        [archive] = re.findall(
            r"spike-scripts\.tar\.gz\)\n\(SHA-256 `([0-9a-f]{16})…`\)", text
        )
        self.assertTrue(scripts["sha256"].startswith(archive))
        printed = dict(
            re.findall(r"^\| `([\w.]+\.py)` \| `([0-9a-f]{16})…` \|", text, re.M)
        )
        full = {member["name"]: member["sha256"] for member in scripts["members"]}
        self.assertEqual(sorted(full), sorted(printed))
        for name, digest in printed.items():
            with self.subTest(script=name):
                self.assertTrue(full[name].startswith(digest))

    def test_the_archive_is_deterministic_and_matches_its_full_digests(self) -> None:
        """The archive and each member match their full SHA-256 in the JSON
        evidence, not a prefix (CodeAnt on #396), and the archive is as deterministic
        as the assessment says: sorted members, no times or owners, mode 0644
        (Claude on #396)."""
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        scripts = evidence["spike_scripts"]
        self.assertEqual(
            scripts["sha256"], hashlib.sha256(self.ARCHIVE.read_bytes()).hexdigest()
        )
        expected = {member["name"]: member["sha256"] for member in scripts["members"]}
        with tarfile.open(self.ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual(sorted(expected), [member.name for member in members])
            for member in members:
                with self.subTest(script=member.name):
                    self.assertEqual(
                        (0, 0, 0, "", "", 0o644),
                        (
                            member.mtime,
                            member.uid,
                            member.gid,
                            member.uname,
                            member.gname,
                            member.mode,
                        ),
                    )
                    handle = archive.extractfile(member)
                    if handle is None:
                        self.fail(f"{member.name} has no content")
                    self.assertEqual(
                        expected[member.name], hashlib.sha256(handle.read()).hexdigest()
                    )

    def test_the_oracle_is_retained_with_its_digest(self) -> None:
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        oracle = evidence["oracle"]["entries"]
        self.assertEqual(76, len(oracle))
        # `oracle.py` wrote it with `json.dump(oracle, …, indent=0)`, so those bytes
        # are what its digest names.
        self.assertEqual(
            evidence["oracle"]["sha256"],
            hashlib.sha256(json.dumps(oracle, indent=0).encode("utf-8")).hexdigest(),
        )
        counts: dict[str, int] = {}
        for entry in oracle:
            counts[entry["path"]] = counts.get(entry["path"], 0) + 1
        self.assertEqual(evidence["oracle_git_commands_per_file"], counts)


if __name__ == "__main__":
    unittest.main()
