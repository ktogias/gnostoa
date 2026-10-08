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
# GitHub Actions expressions are not shell; each is masked at its own width.
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
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
OTHER_SHELLS = {"zsh", "ksh", "mksh", "oksh", "fish", "csh", "tcsh", "yash", "posh"}
# A YAML key that holds shell in a CI definition.
# Anywhere in the text, so a flow-style mapping is found too (CodeAnt on #394).
CI_KEY = re.compile(r"(?<![\w-])(?:run|script|before_script|after_script)\s*:")
GITLAB_KEYS = ("before_script", "script", "after_script")
BOM = b"\xef\xbb\xbf"
# The instruction files whose shell fences agents run, found by name at any depth.
INSTRUCTION_FILES = {"AGENTS.md"}
FENCE = re.compile(r"^```(?:bash|sh|shell)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
# A documentation placeholder, such as `<exact-40-character-parent-sha>`: not shell.
PLACEHOLDER = re.compile(r"<[a-z0-9][a-z0-9-]*>")
RUN = re.compile(r"[ \t]*(?:RUN|SHELL)[ \t]+(.*)", re.I)
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


def _masked_expression(match: re.Match[str]) -> str:
    """An Actions expression as underscores of its own width, each line break kept,
    so the shell's lines stay where they were (CodeAnt on #394)."""
    return re.sub(r"[^\n]", "_", match.group(0))


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


def _github_runs(path: Path, document: object) -> list[str]:
    found: list[str] = []
    # Each node with the containers above it, so that a recursive alias, a
    # container inside itself, fails closed instead of looping (CodeAnt on #396).
    stack: list[tuple[object, frozenset[int]]] = [(document, frozenset())]
    while stack:
        node, above = stack.pop()
        if isinstance(node, (dict, list)):
            above = _entered(node, above, path.name)
        if isinstance(node, dict):
            default = node.get("defaults")
            if isinstance(default, dict) and isinstance(default.get("run"), dict):
                shell = default["run"].get("shell", "bash")
                if shell not in ("bash", "sh"):
                    raise AssertionError(
                        f"{path}: a `{shell}` default; extend this extraction"
                    )
            if isinstance(node.get("run"), str):
                if node.get("shell", "bash") not in ("bash", "sh"):
                    raise AssertionError(
                        f"{path}: a `{node['shell']}` step; extend this extraction"
                    )
                found.append(EXPRESSION.sub(_masked_expression, node["run"]))
            stack.extend((value, above) for key, value in node.items() if key != "run")
        elif isinstance(node, list):
            stack.extend((item, above) for item in node)
    return found


def _gitlab_scripts(document: dict[str, object]) -> list[str]:
    """Each GitLab CI job's (and `default`'s) `before_script`, `script` and
    `after_script`, in document order. A list is the lines the runner's shell runs
    in turn."""
    found: list[str] = []
    for job in document.values():
        if not isinstance(job, dict):
            continue
        for key in GITLAB_KEYS:
            value = job.get(key)
            if isinstance(value, str):
                found.append(value)
            elif isinstance(value, list):
                found.append("\n".join(_script_lines(value)))
    return found


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
    if not under_github and not CI_KEY.search(path.read_text(encoding="utf-8-sig")):
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


def _refuse(name: str, reason: str) -> AssertionError:
    return AssertionError(f"{name}: {reason}; extend this extraction")


def _shebang_command(head: bytes, name: str) -> str:
    """The name of the command a shebang line runs. Through `env`, its whole
    documented grammar is read (GNU `env --help`, and BSD's `-P`): options and their
    arguments, `-S` strings split again, then assignments, then the command. A word
    outside that grammar, a line that cannot be split, or no command fails closed, so
    nothing is guessed (Codex, Claude and CodeAnt on #394)."""
    try:
        words = shlex.split(head[2:].split(b"\n", 1)[0].decode("utf-8"))
        # A chained `env` is followed, to a bound (Claude on #396).
        for _ in range(ENV_CHAIN_LIMIT):
            if not words or Path(words[0]).name != "env":
                break
            words = _env_operands(words[1:], name)
    except ValueError as exc:  # UnicodeDecodeError included
        raise _refuse(name, "an unreadable shebang") from exc
    if not words or Path(words[0]).name == "env":
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
    if option != "split-string" and option not in ENV_LONG_ARGUMENT:
        raise _refuse(name, f"an unknown env option `{word}`")
    if not equals:
        value, rest = _env_argument(rest, name)
    return shlex.split(value) + rest if option == "split-string" else rest


def _env_short_options(word: str, rest: list[str], name: str) -> list[str]:
    for index, letter in enumerate(word[1:], start=1):
        if letter in ENV_FLAGS:
            continue
        if letter not in ENV_ARGUMENT_FLAGS:
            raise _refuse(name, f"an unknown env option `{word}`")
        value = word[index + 1 :]
        if not value:
            value, rest = _env_argument(rest, name)
        return shlex.split(value) + rest if letter == "S" else rest
    return rest


def _env_argument(rest: list[str], name: str) -> tuple[str, list[str]]:
    if not rest:
        raise _refuse(name, "an unreadable shebang")
    return rest[0], rest[1:]


def _exec_form_shell(argv: list[str]) -> list[str]:
    """An exec-form `RUN` of `sh`, `bash`, `dash` or `ash` still hands its `-c`
    command to that shell; another shell fails closed (cubic on #396)."""
    program = Path(argv[0]).name if argv else ""
    if program in OTHER_SHELLS:
        raise AssertionError(f"an exec-form `{program}` RUN; extend this extraction")
    if program not in SHELLS:
        return []
    for index, word in enumerate(argv[1:-1], start=1):
        if word.startswith("-") and not word.startswith("--") and "c" in word[1:]:
            return [argv[index + 1]]
    return []


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
        command = match.group(1)
        if match.group(0).lstrip()[:5].upper() == "SHELL":
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
        if "<<" in command:
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
        fences = FENCE.findall(path.read_text(encoding="utf-8-sig"))
        return _numbered(name, [PLACEHOLDER.sub(_masked, fence) for fence in fences])
    if CONTAINER_FILE.match(path.name) and path.name != "Dockerfile":
        raise _refuse(name, "a container file")
    if path.name == "Dockerfile":
        return _numbered(name, _dockerfile_runs(path.read_text(encoding="utf-8-sig")))
    return {}


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
                "steps:\n  - run: |\n      echo ${{ fromJSON(\n        x) }}\n"
                "      git status\n",
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
            path.write_text("steps:\n  - run: print(1)\n    shell: python\n", "utf-8")
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
                "steps:\n  - run: git status\n", "utf-8"
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
                "on: push\njobs:\n  j:\n    steps:\n      - run: git log\n", "utf-8"
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
                "e": b'#!/usr/bin/env -S "bash -e"\ngit e\n',
                "f": b"#!/usr/bin/env VAR=1 bash\ngit f\n",
                "g": b'#!/usr/bin/env --split-string="bash -e"\ngit g\n',
                "h": b"#!/usr/bin/env -Sbash -e\ngit h\n",
                "j": b"#!/usr/bin/env -i - --unset=X -C /tmp -0v bash\ngit j\n",
                "p": b"#!/usr/bin/env python3\nprint()\n",
            }
            for name, content in scripts.items():
                (root / name).write_bytes(content)
            self.assertEqual(
                {"a", "b", "c", "d", "e", "f", "g", "h", "j"},
                set(_shell_surfaces(_declared(root))),
            )
            for content in (
                b"#!\ngit u\n",
                b"#! \t\ngit u\n",
                b"#!/bin/\xffsh\ngit u\n",
                b"#!/usr/bin/env -S 'bash\ngit u\n",
                b"#!/usr/bin/env -u\ngit u\n",
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
                b'#!/usr/bin/env -S "env -i bash"\ngit k\n',
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
