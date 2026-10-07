"""Owned responsibilities: the registry, and the check that refuses a new copy.

Decision 0102, #368 and #365: a responsibility with an owner is extended at its
owner, never written again. The check runs in the `fast`, `regression` and
`extended` profiles, so in the repository's pre-commit and pre-push hooks and in
provider CI.
"""

from __future__ import annotations

import io
import os
import pathlib
import re
import shlex
import subprocess  # nosec B404
import tempfile
import time
import tracemalloc
import unittest
from unittest import mock

from tools import reuse_check, shell_reader, trusted_execution
from tools.knowledge_common import KnowledgeFormatError

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "policy" / "owned-responsibilities.yaml"


def _tree(files: dict[str, str]) -> tempfile.TemporaryDirectory[str]:
    scratch = tempfile.TemporaryDirectory()
    for relative, text in files.items():
        path = pathlib.Path(scratch.name) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return scratch


def _init(root: pathlib.Path, *tracked: str) -> None:
    """Make ``root`` a repository that tracks ``tracked``, as a developer would."""
    environment = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    for arguments in (["init", "--quiet"], ["add", "--", *tracked]):
        subprocess.run(  # nosec B603 B607
            ["git", "-C", str(root), *arguments], check=True, env=environment
        )


def _signature(responsibility: str, signature: str) -> reuse_check.Signature:
    """A signature of the repository's own registry."""
    for entry in reuse_check.load_registry(REGISTRY).responsibilities:
        for candidate in entry.signatures:
            if entry.id == responsibility and candidate.id == signature:
                return candidate
    raise AssertionError(f"the registry has no {responsibility}/{signature} signature")


def _pattern(responsibility: str, signature: str) -> re.Pattern[str]:
    """The line pattern of a signature of the repository's own registry."""
    pattern = _signature(responsibility, signature).pattern
    if pattern is None:
        raise AssertionError(f"{responsibility}/{signature} is a structural signature")
    return pattern


_REGISTRY_TEXT = """\
id: test-registry
version: "1.0"
responsibilities:
  - id: trusted-execution
    responsibility: Running a tool with trust.
    owner: tools/owner.py
    interface: [run]
    extend: Extend tools/owner.py.
    decision: knowledge/decisions/0102-own-trusted-execution-in-one-hardened-module.md
    signatures:
      - id: git-environment
        pattern: 'GIT_CONFIG_GLOBAL'
        means: a Git environment built outside the owner
    allowed:
      - path: tools/owner.py
        reason: the owner
    debt:
      - path: tools/pending.py
        signatures: [git-environment]
        lines: [GIT_CONFIG_GLOBAL]
        until: https://github.com/ktogias/gnostoa/issues/368
"""


_GUARDED_CONFINEMENT = (
    "import pathlib\n\n\n"
    "def inside(path, root):\n"
    "    try:\n"
    "        pathlib.Path(path).relative_to(root)\n"
    "    except ValueError:\n"
    "        return False\n"
    "    return True\n"
)


def _findings_with_the_real_registry(files: dict[str, str]) -> list[str]:
    """The repository's own registry over a tree holding only ``files``: its debt is
    stale there, so only findings that name one of ``files`` are returned."""
    registry = REGISTRY.read_text(encoding="utf-8")
    with _tree({"policy/owned-responsibilities.yaml": registry, **files}) as scratch:
        root = pathlib.Path(scratch)
        loaded = reuse_check.load_registry(
            root / "policy" / "owned-responsibilities.yaml"
        )
        found = [str(v) for v in reuse_check.violations(root, loaded)]
    # A finding on a line: "path:number: ...". Stale debt names no line.
    return [
        f
        for f in found
        if any(re.match(rf"{re.escape(name)}:\d+:", f) for name in files)
    ]


def _git_runs(files: dict[str, str]) -> set[str]:
    """Each `path:line` where a signature of running Git marks a line."""
    return {
        ":".join(f.split(":")[:2])
        for f in _findings_with_the_real_registry(files)
        if "git-execution" in f or "git-shell-command" in f
    }


class ShellReaderTests(unittest.TestCase):
    """The shell command reader, Decision 0105: positions, peeled words, sources."""

    def test_a_command_position_after_any_separator_or_word_runs_git(self) -> None:
        cases = {
            "ci/a.sh": "if true; then git status; fi\n",
            "ci/b.sh": '"git" status\n',
            "ci/c.sh": "\\git status\n",
            "ci/d.sh": "sh -c 'if true; then git gc; fi'\n",
            "ci/e.sh": "true && { LC_ALL=C time git log; }\n",
        }
        self.assertEqual({f"{name}:1" for name in cases}, _git_runs(cases))

    def test_python_hands_a_shell_its_command_through_a_wrapper(self) -> None:
        """`["env", "bash", "-c", "git status"]` reaches a shell through a wrapper
        (Codex on #369)."""
        cases = {
            "tools/a.py": 'import subprocess\nsubprocess.run(["env", "bash", "-c", "git status"])\n',
            "tools/b.py": 'run(["/usr/bin/env", "-i", "sh", "-c", "git fetch"])\n',
            "tools/c.py": 'from os import system\nsystem("if true; then git gc; fi")\n',
        }
        self.assertEqual(
            {"tools/a.py:2", "tools/b.py:1", "tools/c.py:2"}, _git_runs(cases)
        )

    def test_each_source_of_shell_text_is_read(self) -> None:
        cases = {
            ".github/workflows/w.yml": (
                "jobs:\n  j:\n    steps:\n      - run: |\n"
                "          echo start\n          if true; then git fetch; fi\n"
            ),
            "Dockerfile": "FROM x\nRUN set -e; if true; then git clone y; fi\n",
            "Makefile": "all:\n\tif true; then git gc; fi\n",
            "AGENTS.md": "Run:\n\n```bash\nif true; then git status; fi\n```\n",
            "ci/tool": "#!/bin/sh\nif true; then git log; fi\n",
        }
        self.assertEqual(
            {
                ".github/workflows/w.yml:6",
                "Dockerfile:2",
                "Makefile:2",
                "AGENTS.md:4",
                "ci/tool:2",
            },
            _git_runs(cases),
        )

    def test_text_that_only_names_git_is_no_command(self) -> None:
        cases = {
            "ci/a.sh": "echo git status\n",
            "ci/b.sh": "printf '%s\\n' 'if true; then git gc; fi'\n",
            "ci/c.sh": "grep -r git .\n",
            "ci/d.sh": "# if true; then git status; fi\n",
            "ci/e.sh": "git_status=1\n",
            "AGENTS.md": "Prose: if true; then git status; fi\n",
            "tools/a.py": 'run(["env", "bash", "-c", "make test"])\n',
        }
        self.assertEqual(set(), _git_runs(cases))


class ShellReaderUnitTests(unittest.TestCase):
    """Each branch of the shell command reader, Decision 0105."""

    def test_each_word_before_a_command_is_peeled(self) -> None:
        runs = (
            "git status",
            "/usr/bin/git fetch",
            '"git" log',
            "\\git gc",
            "@git status",
            "`git rev-parse HEAD`",
            "`git`",
            "x=$(git describe)",
            "if git diff; then",
            "then git status",
            "! git diff --quiet",
            "{ git status; }",
            "while git fetch; do",
            "until git pull; do",
            "true && git push",
            "false || git fetch",
            "a | git apply",
            "x & git gc",
            "(git gc)",
            "case m in a) git gc ;; esac",
            "A=1 B=2 git log",
            "env git status",
            "env -i git status",
            "env -u GIT_DIR git status",
            "env A=1 git status",
            "env -S 'git status'",
            "env --split-string='git log'",
            "sudo -u builder git fetch",
            "timeout -s KILL 10 git fetch",
            "nice -n 5 git gc",
            "xargs -0 git add",
            "command -p git status",
            "flock /var/lock/x git gc",
            "stdbuf -oL git log",
            "time -p git status",
            "exec git status",
            "nohup git fetch",
            "sh -c 'git status'",
            "bash -lc 'git fetch'",
            "bash -O extglob -c 'git log'",
            "bash --norc -c 'git gc'",
            "bash -o pipefail -c 'git status'",
            "sh -c 'sh -c \"git status\"'",
            "echo ok\ngit status",
        )
        for text in runs:
            with self.subTest(runs=text):
                self.assertTrue(shell_reader.runs_git(text))
        names = (
            "echo git status",
            "grep git file",
            "git_dir=x",
            "printf 'git status'",
            "# git status",
            "make git",
            "sh script.sh",
            "sh -c",
            "bash -c 'echo git'",
            "sudo make",
            "env",
            "nice -n 5 make git",
            "timeout 10 python3 tool.py",
            "'unterminated git",
            "time",
            "env -S",
            "",
        )
        for text in names:
            with self.subTest(names=text):
                self.assertFalse(shell_reader.runs_git(text))

    def test_nesting_is_followed_to_a_bound(self) -> None:
        text = "git status"
        for _ in range(4):
            text = f"sh -c {shlex.quote(text)}"
        self.assertTrue(shell_reader.runs_git(text))
        self.assertFalse(shell_reader.runs_git(f"sh -c {shlex.quote(text)}"))

    def test_an_argument_list_hands_its_shell_a_command(self) -> None:
        cases = (
            (["sh", "-c", "git status"], (2, "git status")),
            (["env", "bash", "-c", "git status"], (3, "git status")),
            (["/usr/bin/env", "-i", "sh", "-c", "x"], (4, "x")),
            (["env", "-S", "git status"], (2, "git status")),
            (["env", "--split-string=git log"], (1, "git log")),
            (["sh", "script.sh"], None),
            ([None, "-c", "x"], None),
            (["python3", "-c", "x"], None),
            (["sh", "-c"], None),
            (["env", None, "sh", "-c", "x"], None),
            (["sh", None, "-c", "x"], None),
            (["sh", "-c", None], None),
        )
        for argv, handed in cases:
            with self.subTest(argv=argv):
                self.assertEqual(handed, shell_reader.handed_command(argv))

    def test_each_source_keeps_its_own_lines(self) -> None:
        cases: tuple[tuple[str, list[str], dict[int, tuple[str, ...]]], ...] = (
            ("ci/a.sh", ["x", "git status"], {1: ("x",), 2: ("git status",)}),
            (
                "ci/tool",
                ["#!/usr/bin/env bash", "git gc"],
                {1: ("#!/usr/bin/env bash",), 2: ("git gc",)},
            ),
            (
                "Dockerfile",
                [
                    "FROM a",
                    "RUN a \\",
                    "  && git clone x",
                    'RUN ["git", "x"]',
                    "ENV X=1",
                ],
                {2: ("a \\",), 3: ("  && git clone x",)},
            ),
            ("Makefile", ["all:", "\tgit gc", "git: all"], {2: ("git gc",)}),
            (
                ".github/workflows/w.yml",
                [
                    "      - run: git status",
                    '      - run: "git log"',
                    "      - run: |",
                    "          git fetch",
                    "",
                    "          git gc",
                    "      - name: x",
                ],
                {
                    1: ("git status",),
                    2: ("git log",),
                    4: ("          git fetch",),
                    5: ("",),
                    6: ("          git gc",),
                },
            ),
            (
                "docs/AGENTS.md",
                [
                    "prose git status",
                    "```bash",
                    "git status",
                    "```",
                    "```console",
                    "$ git log",
                    "```",
                    "```python",
                    "git = 1",
                    "```",
                ],
                {3: ("git status",), 6: ("git log",)},
            ),
            ("README.txt", ["git status"], {}),
        )
        for relative, lines, found in cases:
            with self.subTest(relative=relative):
                self.assertEqual(found, shell_reader.shell_lines(relative, lines))

    def test_a_shell_source_is_known_by_its_name_or_shebang(self) -> None:
        for relative, first, shell in (
            ("ci/a.sh", "", True),
            ("ci/a.bash", "", True),
            ("ci/tool", "#!/bin/sh", True),
            ("ci/tool", "#!/usr/bin/env bash", True),
            ("ci/tool", "#!/usr/bin/env python3", False),
            ("ci/tool", "#!/usr/bin/python3", False),
            ("Dockerfile", "", True),
            ("Dockerfile.dev", "", True),
            ("x.Dockerfile", "", True),
            ("Makefile", "", True),
            ("rules.mk", "", True),
            (".github/workflows/w.yaml", "", True),
            ("docs/w.yml", "", False),
            ("sub/AGENTS.md", "", True),
            ("README.md", "", False),
        ):
            with self.subTest(relative=relative, first=first):
                self.assertEqual(shell, shell_reader.is_shell_source(relative, first))


class UnreadableTreeTests(unittest.TestCase):
    def test_a_subtree_that_cannot_be_read_is_an_error(self) -> None:
        """Outside a repository the tree is walked, and the walk skipped a directory it
        could not read, so a copy there passed unseen (CodeAnt on #369)."""
        if os.geteuid() == 0:
            self.skipTest("root reads every directory")
        files = {
            "policy/owned-responsibilities.yaml": REGISTRY.read_text(encoding="utf-8"),
            "tools/hidden/new.py": "import yaml\nyaml.safe_load('a: 1')\n",
        }
        with _tree(files) as scratch:
            root = pathlib.Path(scratch)
            hidden = root / "tools" / "hidden"
            hidden.chmod(0)
            try:
                loaded = reuse_check.load_registry(
                    root / "policy" / "owned-responsibilities.yaml"
                )
                with self.assertRaises(KnowledgeFormatError):
                    reuse_check.violations(root, loaded)
            finally:
                hidden.chmod(0o755)


class SkippedTreeTests(unittest.TestCase):
    def test_an_unreadable_directory_the_walk_skips_is_no_error(self) -> None:
        """The walk went into a hidden directory it excludes, so an unreadable
        `.evidence` stopped the check (CodeAnt on #369)."""
        if os.geteuid() == 0:
            self.skipTest("root reads every directory")
        files = {
            "policy/owned-responsibilities.yaml": REGISTRY.read_text(encoding="utf-8"),
            ".evidence/run/out.txt": "x\n",
        }
        with _tree(files) as scratch:
            root = pathlib.Path(scratch)
            hidden = root / ".evidence" / "run"
            hidden.chmod(0)
            try:
                loaded = reuse_check.load_registry(
                    root / "policy" / "owned-responsibilities.yaml"
                )
                reuse_check.violations(root, loaded)
            finally:
                hidden.chmod(0o755)


class StructuralSignatureTests(unittest.TestCase):
    """`relative_to` under `except ValueError` confines a path (Codex on #369; the
    owner chose a structural signature, 2026-10-06)."""

    def test_a_guarded_relative_to_is_a_copy_of_path_confinement(self) -> None:
        found = _findings_with_the_real_registry({"tools/new.py": _GUARDED_CONFINEMENT})
        self.assertTrue(
            any(
                f.startswith("tools/new.py:6:") and "path-confinement" in f
                for f in found
            ),
            found,
        )

    def test_a_line_number_counts_lines_as_python_does(self) -> None:
        """`str.splitlines` also breaks at a form feed, U+2028 or NEL inside one Python
        line, so every later line was misnumbered (CodeAnt on #369)."""
        source = "# a\x0cb\u2028c\x85d\nimport yaml\nyaml.safe_load(x)\n"
        found = _findings_with_the_real_registry({"tools/new.py": source})
        self.assertTrue(
            any(f.startswith("tools/new.py:3:") and "yaml-load" in f for f in found),
            found,
        )

    def test_a_long_file_with_carriage_returns_only_is_read(self) -> None:
        """`readline` splits only at `\\n`, so a CR-only file over 1 MiB was read as
        one line too long to check (CodeAnt on #369)."""
        source = "x = 1\r" * 300_000 + "import yaml\ryaml.safe_load(x)\r"
        found = _findings_with_the_real_registry({"tools/new.py": source})
        self.assertTrue(
            any(
                f.startswith("tools/new.py:300002:") and "yaml-load" in f for f in found
            ),
            found,
        )

    def test_a_line_end_split_between_blocks_is_one_end(self) -> None:
        """A `\\r\\n` whose `\\r` ends one block read is one line end, not two, and a
        last line with no end is still read. Characterization: `readline` read both
        so, and the block reader must too."""
        first = "x" * (64 * 1024 - 1)
        source = first + "\r\nimport yaml\r\nyaml.safe_load(x)"
        found = _findings_with_the_real_registry({"tools/new.py": source})
        self.assertTrue(
            any(f.startswith("tools/new.py:3:") and "yaml-load" in f for f in found),
            found,
        )

    def test_structural_debt_reads_the_line_python_marked(self) -> None:
        """The marked line's number named another line's text after such a break, so
        debt owed for the line seemed gone (CodeAnt on #369)."""
        registry = _REGISTRY_TEXT.replace(
            "      - id: git-environment\n"
            "        pattern: 'GIT_CONFIG_GLOBAL'\n"
            "        means: a Git environment built outside the owner\n",
            "      - id: path-relation-guarded\n"
            "        structure: relative-to-under-value-error\n"
            "        means: a path confined outside the owner\n",
        ).replace(
            "        signatures: [git-environment]\n"
            "        lines: [GIT_CONFIG_GLOBAL]\n",
            "        signatures: [path-relation-guarded]\n"
            "        lines: ['pathlib.Path(path).relative_to(root)']\n",
        )
        self.assertIn("relative-to-under-value-error", registry)
        self.assertIn("lines: ['pathlib", registry)
        files = {
            "policy/owned-responsibilities.yaml": registry,
            "tools/pending.py": "# a\x0cb\n" + _GUARDED_CONFINEMENT,
        }
        with _tree(files) as scratch:
            root = pathlib.Path(scratch)
            loaded = reuse_check.load_registry(
                root / "policy" / "owned-responsibilities.yaml"
            )
            found = [str(v) for v in reuse_check.violations(root, loaded)]
        self.assertEqual([], found)

    def test_a_python_script_without_the_suffix_is_read_as_python(self) -> None:
        script = "#!/usr/bin/env python3\n" + _GUARDED_CONFINEMENT
        found = _findings_with_the_real_registry({"ci/new-tool": script})
        self.assertTrue(any(f.startswith("ci/new-tool:7:") for f in found), found)

    def test_a_function_reached_another_way_is_a_copy(self) -> None:
        """A parenthesized import puts the name on a line of its own, and a module
        alias hides the module's name, so each went unseen line by line (Codex on
        #369). Both are read from the syntax tree, and only what the line pattern
        cannot see is marked, so no line is marked twice."""
        cases = (
            (
                "yaml-load-indirect",
                "from yaml import (\n    SafeDumper,\n    safe_load,\n)\n",
                3,
            ),
            (
                "yaml-load-indirect",
                "import yaml as y\n\n\ndef f(t):\n    return y.safe_load(t)\n",
                5,
            ),
            (
                "jsonschema-validator-indirect",
                "from jsonschema import (\n    validate,\n)\n",
                2,
            ),
            (
                "jsonschema-validator-indirect",
                "import jsonschema as js\njs.validate(1, {})\n",
                2,
            ),
            (
                "executable-lookup-indirect",
                "from shutil import (\n    copy,\n    which,\n)\n",
                3,
            ),
            ("executable-lookup-indirect", "import shutil as sh\nsh.which('git')\n", 2),
            ("yaml-load-indirect", "import yaml as y\ny.load_all(t)\n", 2),
            (
                "jsonschema-validator-indirect",
                "from jsonschema import (\n    validator_for,\n)\n",
                2,
            ),
        )
        for signature, source, line in cases:
            with self.subTest(signature=signature, source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if f", {signature})" in f],
                    found,
                )
        for source in (
            "from yaml import (\n    SafeDumper,\n)\n",
            "import yaml as y\ny.dump({})\n",
            "import yaml\nyaml.safe_load('a: 1')\n",
            "from shutil import which\n",
            "from .yaml import (\n    safe_load,\n)\n",
        ):
            with self.subTest(unmarked=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertFalse([f for f in found if "-indirect)" in f], found)

    def test_an_argument_list_the_line_does_not_show_is_a_copy(self) -> None:
        """The argv alternatives need `[` and a name like `git_bin` on one line, so a
        list split across lines, or a tuple, ran Git unseen (CodeAnt on #369)."""
        cases = (
            (
                "subprocess.run(\n    [\n        git_bin,\n        'status',\n    ]\n)\n",
                3,
            ),
            (
                "subprocess.run(\n    [\n        self._git,\n        'log',\n    ]\n)\n",
                3,
            ),
            ("subprocess.run((git_bin, 'status'))\n", 1),
            ("command = (\n    GIT,\n    'status',\n)\n", 2),
        )
        for source, line in cases:
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if ", git-argv)" in f],
                    found,
                )
        for source in (
            "digits = [\n    digit,\n    1,\n]\n",
            "subprocess.run([git_bin, 'status'])\n",
            "pair = (gitlab, 1)\n",
        ):
            with self.subTest(unmarked=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertFalse([f for f in found if ", git-argv)" in f], found)

    def test_a_submodule_reached_through_an_alias_is_reached_too(self) -> None:
        """`import jsonschema as js` then `js.validators.validate(...)` went unseen: the
        dotted owner was not resolved through the alias (CodeAnt on #369). So was a
        submodule imported by name, `from jsonschema import validators as v`."""
        for source in (
            "import jsonschema as js\njs.validators.validate(1, {})\n",
            "from jsonschema import validators as v\nv.validate(1, {})\n",
            "from jsonschema import validators\nvalidators.validate(1, {})\n",
        ):
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    ["2"],
                    [f.split(":")[1] for f in found if "jsonschema-validator" in f],
                    found,
                )
        for source in (
            "import jsonschema\njsonschema.validate(1, {})\n",
            "import jsonschema as jsonschema\njsonschema.validate(1, {})\n",
            "from .jsonschema import validators as v\nv.validate(1, {})\n",
        ):
            with self.subTest(unmarked=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertFalse([f for f in found if "indirect" in f], found)

    def test_an_http_client_on_a_line_of_its_own_is_a_copy(self) -> None:
        """A multi-line import puts `client` or `request` on a line of its own, where
        the line pattern cannot see it (Codex on #369)."""
        for source, line in (
            ("from http import (\n    HTTPStatus,\n    client,\n)\n", 3),
            ("from urllib import (\n    request,\n)\n", 2),
        ):
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if "http-request" in f],
                    found,
                )

    def test_a_path_confined_by_a_common_path_or_its_parents_is_a_copy(self) -> None:
        """`os.path.commonpath([root, candidate]) == root` matched neither the line
        pattern nor the `relative_to` detector (Codex on #369). Nor did the same
        family's other ordinary forms: a common prefix, the parents and a prefix
        ending in the separator."""
        cases = (
            (
                "import os\ndef inside(root, path):\n"
                "    return os.path.commonpath([root, path]) == root\n",
                3,
            ),
            ("from os.path import commonpath\nok = commonpath((r, p)) != r\n", 2),
            ("import os\nok = os.path.commonprefix([r, p]) == r\n", 2),
            (
                "import os\nok = os.path.commonpath([p, '/srv/root']) == '/srv/root'\n",
                2,
            ),
            ("import os\nok = (\n    os.path.commonpath([r, p])\n    == r\n)\n", 3),
            ("ok = root in path.parents\n", 1),
            ("ok = root not in path.resolve().parents\n", 1),
            ("import os\nok = str(p).startswith(str(r) + os.sep)\n", 2),
            ('import os\nok = p.startswith(f"{r}{os.sep}")\n', 2),
        )
        for source, line in cases:
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if "path-prefix-compared" in f],
                    found,
                )
        for source in (
            "import os\nbase = os.path.commonpath(paths)\n",
            "for place in (start, *start.parents):\n    pass\n",
            "ROOT = Path(__file__).resolve().parents[1]\n",
            "ok = name.startswith(prefix + '/')\n",
            "import os\npath = os.path.join(root + os.sep, name)\n",
            "ok = len(paths) == count\n",
            "import os\nok = os.path.commonprefix(names) == 'pre'\n",
        ):
            with self.subTest(unmarked=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertFalse([f for f in found if "path-confinement" in f], found)

    def test_a_shell_helper_imported_by_name_runs_its_command_too(self) -> None:
        """`from subprocess import run`, then `run("git status", shell=True)`, runs Git
        where no line shows it (Codex on #369). So does a module alias, and a command
        on a line of its own. A command handed to a shell is read as a line is, so
        the responsibility's own line patterns judge it."""
        cases = (
            ('from subprocess import run\nrun("git status", shell=True)\n', 2),
            ('from os import system\nsystem("git fetch")\n', 2),
            ('from os import system as sh\nsh("LC_ALL=C git status")\n', 2),
            ('import subprocess as sp\nsp.run("git status", shell=True)\n', 2),
            (
                'import subprocess\nsubprocess.run(\n    "git status",\n'
                "    shell=True,\n)\n",
                3,
            ),
            (
                "from subprocess import check_output as co\n"
                'out = co(f"git -C {path} rev-parse HEAD", shell=True)\n',
                2,
            ),
            ('from os import system\nsystem("sudo -u builder git gc")\n', 2),
            ('from subprocess import run\nrun(args="git status", shell=True)\n', 2),
            (
                'import subprocess\nsubprocess.run("echo ok\\ngit status", shell=True)\n',
                2,
            ),
            ('from os import system\nsystem("cd /srv\\ngit fetch")\n', 2),
            ('from os import system\nsystem("echo ok\\nGIT=git")\n', 2),
        )
        for source, line in cases:
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if "shell-command" in f],
                    found,
                )
        for source in (
            'from subprocess import run\nrun("make test", shell=True)\n',
            "from os import system\nsystem(command)\n",
            'import subprocess\nsubprocess.run("git status", shell=True)\n',
            'from subprocess import run\nrun(["git", "status"])\n',
        ):
            with self.subTest(unmarked=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertFalse([f for f in found if "shell-command" in f], found)

    def test_a_shell_argument_list_runs_its_command_too(self) -> None:
        """`subprocess.run(["sh", "-c", "git status"])` hands a shell its command as an
        argument list, which no signature read (Codex on #369). An argument list
        headed by a shell is read wherever it stands, as one headed by Git is."""
        cases = (
            ('import subprocess\nsubprocess.run(["sh", "-c", "git status"])\n', 2),
            (
                "import subprocess\nsubprocess.run(\n"
                '    ["bash", "-lc", "git fetch"],\n)\n',
                3,
            ),
            ('args = ("/bin/sh", "-ec", "git gc")\n', 1),
            ('run(["bash", "--norc", "-o", "pipefail", "-c", "git log"])\n', 1),
            ('run(["sh", "-c", f"git -C {d} status"])\n', 1),
            ('run(["bash", "-O", "extglob", "-c", "git status"])\n', 1),
            ('run(["bash", "+O", "nullglob", "-c", "git status"])\n', 1),
            ('run(["bash", "--rcfile", "/srv/rc", "-c", "git status"])\n', 1),
            ('run(["bash", "--init-file", "/srv/rc", "-c", "git status"])\n', 1),
        )
        for source, line in cases:
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if "shell-command" in f],
                    found,
                )
        for source in (
            'run(["sh", "-c", "make test"])\n',
            'run(["sh", "script.sh"])\n',
            'run(["sh", "script.sh", "git status"])\n',
            'run(["bash", "-c", command])\n',
        ):
            with self.subTest(unmarked=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertFalse([f for f in found if "shell-command" in f], found)

    def test_a_submodule_s_function_is_reached_too(self) -> None:
        """`from jsonschema.validators import validator_for as select` and a dotted call
        through a submodule went unseen: only the module itself was read (Codex on
        #369)."""
        cases = (
            ("from jsonschema.validators import validator_for as select\n", 1),
            ("import jsonschema.validators as v\nv.validate(1, {})\n", 2),
            (
                "import jsonschema.validators\njsonschema.validators.validate(1, {})\n",
                2,
            ),
        )
        for source, line in cases:
            with self.subTest(source=source):
                found = _findings_with_the_real_registry({"tools/new.py": source})
                self.assertEqual(
                    [str(line)],
                    [f.split(":")[1] for f in found if "jsonschema-validator" in f],
                    found,
                )

    def test_what_a_definition_runs_at_once_is_the_try_s_own(self) -> None:
        """A decorator and a default run where the definition stands, inside the `try`;
        a generator's body runs later, when iterated (CodeAnt on #369)."""
        guarded = (
            "import pathlib\n\n\ndef inside(path, root):\n    try:\n"
            "        def f(x=pathlib.Path(path).relative_to(root)):\n"
            "            return x\n"
            "    except ValueError:\n        return False\n    return True\n"
        )
        found = _findings_with_the_real_registry({"tools/new.py": guarded})
        self.assertEqual(
            ["6"], [f.split(":")[1] for f in found if "path-confinement" in f], found
        )

    def test_a_generator_s_body_runs_after_the_try(self) -> None:
        """A generator's body runs when iterated, perhaps after the `try`, so it was
        marked as guarded when it was not (CodeAnt on #369)."""
        lazy = (
            "import pathlib\n\n\ndef shown(paths, root):\n    try:\n"
            "        found = (pathlib.Path(p).relative_to(root) for p in paths)\n"
            "    except ValueError:\n        return None\n    return found\n"
        )
        found = _findings_with_the_real_registry({"tools/new.py": lazy})
        self.assertFalse([f for f in found if "path-confinement" in f], found)

    def test_a_class_body_runs_inside_the_try(self) -> None:
        """A class body runs where it stands, so its `relative_to` is guarded by the
        `try` around it; only function and lambda bodies wait (CodeAnt on #369)."""
        source = (
            "import pathlib\n\n\n"
            "def inside(path, root):\n"
            "    try:\n"
            "        class Probe:\n"
            "            relative = pathlib.Path(path).relative_to(root)\n"
            "\n"
            "            def later(self):\n"
            "                return pathlib.Path(path).relative_to(root)\n"
            "    except ValueError:\n"
            "        return False\n"
            "    return True\n"
        )
        found = _findings_with_the_real_registry({"tools/new.py": source})
        self.assertEqual(
            ["7"], [f.split(":")[1] for f in found if "path-confinement" in f], found
        )

    def test_a_relative_path_computed_without_a_guard_is_no_copy(self) -> None:
        computed = (
            "import pathlib\n\n\n"
            "def shown(path, root):\n"
            "    return pathlib.Path(path).relative_to(root).as_posix()\n"
        )
        self.assertEqual(
            [], _findings_with_the_real_registry({"tools/new.py": computed})
        )

    def test_the_same_text_outside_python_is_no_structural_match(self) -> None:
        self.assertEqual(
            [], _findings_with_the_real_registry({"AGENTS.md": _GUARDED_CONFINEMENT})
        )

    def test_a_signature_is_a_pattern_or_a_known_structure_never_both(self) -> None:
        signature = (
            "      - id: git-environment\n"
            "        pattern: 'GIT_CONFIG_GLOBAL'\n"
            "        means: a Git environment built outside the owner\n"
        )
        for label, replacement in (
            (
                "both",
                signature.replace(
                    "        means:",
                    "        structure: relative-to-under-value-error\n        means:",
                ),
            ),
            (
                "unknown",
                signature.replace(
                    "        pattern: 'GIT_CONFIG_GLOBAL'\n",
                    "        structure: something-else\n",
                ),
            ),
            (
                "neither",
                signature.replace("        pattern: 'GIT_CONFIG_GLOBAL'\n", ""),
            ),
        ):
            registry = _REGISTRY_TEXT.replace(signature, replacement, 1)
            self.assertNotEqual(_REGISTRY_TEXT, registry, label)
            with (
                self.subTest(label),
                _tree({"policy/r.yaml": registry}) as scratch,
                self.assertRaises(KnowledgeFormatError),
            ):
                reuse_check.load_registry(pathlib.Path(scratch) / "policy" / "r.yaml")

    def test_a_relative_to_in_a_nested_function_is_not_guarded(self) -> None:
        # The outer handler does not guard a function defined in its `try` (CodeAnt on
        # #369), whether at the top of the `try` or deeper in it.
        for label, opening, indent in (
            ("at the top", "", "        "),
            ("in an if", "        if root:\n", "            "),
        ):
            nested = (
                "import pathlib\n\n\n"
                "def make(root):\n"
                "    try:\n"
                + opening
                + f"{indent}def shown(path):\n"
                + f"{indent}    return pathlib.Path(path).relative_to(root).as_posix()\n"
                + "    except ValueError:\n"
                "        return None\n"
                "    return shown\n"
            )
            with self.subTest(label):
                self.assertEqual(
                    [], _findings_with_the_real_registry({"tools/new.py": nested})
                )

    def test_a_line_beyond_the_bound_cannot_pass_as_clean(self) -> None:
        # A file with no newline was read whole (Codex on #369).
        with (
            mock.patch.object(reuse_check, "_LINE_LIMIT_BYTES", 1024),
            self.assertRaises(KnowledgeFormatError),
        ):
            _findings_with_the_real_registry({"tools/minified.py": "x = 1;" * 1000})

    def test_a_line_at_the_bound_before_a_split_crlf_is_read(self) -> None:
        """A block that ended in the `\\r` of a `\\r\\n` kept it pending, so a line
        of exactly the bound counted one byte over and was refused (CodeAnt on
        #369). One byte more is still refused."""
        with (
            mock.patch.object(reuse_check, "_LINE_LIMIT_BYTES", 1024),
            mock.patch.object(reuse_check, "_BLOCK_BYTES", 1025),
        ):
            lines = list(
                reuse_check._byte_lines(  # skipcq: PYL-W0212
                    io.BytesIO(b"x" * 1024 + b"\r\ny\n"), "tools/at_bound.py"
                )
            )
        self.assertEqual([b"x" * 1024, b"y"], lines)
        with (
            mock.patch.object(reuse_check, "_LINE_LIMIT_BYTES", 1024),
            mock.patch.object(reuse_check, "_BLOCK_BYTES", 1026),
        ):
            over = reuse_check._byte_lines(  # skipcq: PYL-W0212
                io.BytesIO(b"x" * 1025 + b"\r\ny\n"), "tools/over.py"
            )
            with self.assertRaises(KnowledgeFormatError):
                list(over)
        with (
            mock.patch.object(reuse_check, "_LINE_LIMIT_BYTES", 1024),
            mock.patch.object(reuse_check, "_BLOCK_BYTES", 1025),
        ):
            no_end = reuse_check._byte_lines(  # skipcq: PYL-W0212
                io.BytesIO(b"x" * 1025), "tools/no_end.py"
            )
            with self.assertRaises(KnowledgeFormatError):
                list(no_end)

    def test_a_line_beyond_the_bound_inside_one_block_is_refused(self) -> None:
        """Only what was still pending was measured, so a line that ended inside the
        block it was read in passed the bound (CodeAnt on #369)."""
        with (
            mock.patch.object(reuse_check, "_LINE_LIMIT_BYTES", 1024),
            mock.patch.object(reuse_check, "_BLOCK_BYTES", 4096),
        ):
            lines = reuse_check._byte_lines(  # skipcq: PYL-W0212
                io.BytesIO(b"x" * 1025 + b"\ny\n"), "tools/long.py"
            )
            with self.assertRaises(KnowledgeFormatError):
                list(lines)

    def test_a_byte_order_mark_hides_nothing(self) -> None:
        """A UTF-8 byte order mark reached `ast.parse` as U+FEFF, which it refuses, and
        stood before a first line's command, which no line start then matched
        (CodeAnt on #369)."""
        for name, source, line in (
            ("tools/marked.py", "\ufeffimport os\nos.system('git status')\n", "2"),
            ("ci/marked.sh", "\ufeffgit status\n", "1"),
        ):
            with self.subTest(name=name):
                found = _findings_with_the_real_registry({name: source})
                self.assertEqual(
                    [line], [f.split(":")[1] for f in found if "git-execution" in f]
                )

    def test_a_nested_agents_file_is_production(self) -> None:
        # Only the root AGENTS.md was scanned (CodeAnt on #369).
        found = _findings_with_the_real_registry(
            {"sub/AGENTS.md": "    unset GIT_DIR GIT_WORK_TREE\n"}
        )
        self.assertTrue(any(f.startswith("sub/AGENTS.md:1:") for f in found), found)

    def test_python_that_does_not_parse_cannot_pass_as_clean(self) -> None:
        with self.assertRaises(KnowledgeFormatError):
            _findings_with_the_real_registry({"tools/broken.py": "def broken(:\n"})


class RepositoryTests(unittest.TestCase):
    def test_the_registry_conforms_to_its_schema(self) -> None:
        self.assertEqual([], reuse_check.registry_errors(REGISTRY))

    def test_the_production_tree_holds_no_unowned_copy_and_no_stale_debt(self) -> None:
        """A failure names the copy: extend the owner the registry names instead."""
        found = reuse_check.violations(ROOT, reuse_check.load_registry(REGISTRY))
        self.assertEqual([], [str(v) for v in found])

    def test_the_git_environment_signature_sees_a_shell_scrub_list(self) -> None:
        """A scrub list that names only `GIT_EXEC_PATH` or `GIT_TRACE` builds a Git
        environment outside the owner too (CodeAnt on #369)."""
        pattern = _pattern("trusted-execution", "git-environment")
        for line in (
            "    unset GIT_DIR GIT_WORK_TREE GIT_EXEC_PATH",
            "  unset GIT_TRACE",
            'environment.pop("GIT_EXEC_PATH", None)',
            # A scrubber that names the routing variables themselves (CodeAnt on #369).
            '    environment.pop("GIT_DIR", None)',
            '    for name in ("GIT_WORK_TREE", "GIT_INDEX_FILE"):',
            '    env["GIT_OBJECT_DIRECTORY"] = objects',
            '  if [ -n "${GIT_DIR:-}" ]; then',
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))

    def test_the_shell_form_knows_every_git_command(self) -> None:
        """A hand-kept list of subcommands missed `git blame` (CodeAnt on #369); the
        list is Git's own, so a Git with a new command fails here, not in a copy."""
        git = trusted_execution.git_executable()
        listed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [git, "--list-cmds=main"],
            capture_output=True,
            text=True,
            check=True,
            env=trusted_execution.git_environment(),
        ).stdout.split()
        pattern = _pattern("trusted-execution", "git-execution")
        missed = [c for c in listed if not pattern.search(f"  git {c} HEAD")]
        self.assertEqual([], missed)

    def test_no_signature_backtracks_on_a_hostile_line(self) -> None:
        """Each signature searches these lines in about linear time. They are the
        shapes that backtracked: a run of `-C` or `--x` options was read two ways at
        each step, exponentially, and an import list's `[^#]*` rescanned the line from
        each `from ... import`, quadratically (CodeAnt on #369). The test guards these
        shapes, not every possible one."""
        lines = [
            "git " + "-C " * 32 + "!",
            "git " + "--a " * 22 + "!",
            "; git " + "--a " * 22 + "!",
            "; git " + "-C " * 32 + "!",
            *(
                f"from {module} import " * 4000 + "!"
                for module in ("shutil", "yaml", "jsonschema")
            ),
            " " * 100_000 + "!",
            "'/a" * 30_000 + "!",
            "os.system('git " * 8000 + "!",
            "git " + "--version " * 20_000 + "!",
            "if ! " * 20_000 + "!",
            "/a" * 30_000 + "git!",
        ]
        for entry in reuse_check.load_registry(REGISTRY).responsibilities:
            for signature in entry.signatures:
                if signature.pattern is None:
                    continue
                for line in lines:
                    started = time.perf_counter()
                    signature.pattern.search(line)
                    with self.subTest(signature=signature.id, line=line[:24]):
                        self.assertLess(time.perf_counter() - started, 0.5)

    def test_the_rest_of_git_s_command_forms_are_signatures(self) -> None:
        """Rounds 15 to 19 each found one more way to run Git unseen. These are the
        forms still missed, listed at once rather than one review round apiece."""
        for line in (
            "    head=`git rev-parse HEAD`",
            "      - run: git fetch --depth=1 origin main",
            "        run: git diff --name-only HEAD~1",
            "RUN git clone --depth 1 https://example.invalid/x.git /x",
            "sh -c 'git status --short'",
            '    bash -lc "git log -1"',
            "timeout 30 git fetch origin",
            "nice -n 10 git gc",
            "nohup git fetch &",
            "sudo git config --system x y",
            "printf '%s\\n' a | xargs -0 git add --",
            "find . -name x -exec git add {} +",
            "time git status",
            "import git",
            "from git import Repo",
            '    subprocess.run([git_bin, "status"])',
            '    subprocess.run([self.git_path, "log"])',
            '    subprocess.run(shlex.split("git status"))',
            '    pexpect.spawn("git status")',
            "git lfs pull",
            "/usr/bin/git annex sync",
            "env GIT_TRACE=1 git filter-repo --path x",
            "if git frobnicate; then",
            '    os.system("git my-extension --flag")',
            "if git --no-pager log -1; then",
            '    os.system("git --no-pager diff")',
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("trusted-execution", "git-execution").search(line)
                )
        for prose in (
            "    digits = [digit, 1]",
            '    raise ValueError(f"git describe failed: {exc}")',
            "import gitlab",
            "# the timeout for git fetch is set above",
            "            git and no candidate tree. The change is in",
            "    git with which to check. They are escaped",
        ):
            with self.subTest(prose=prose):
                self.assertFalse(
                    _pattern("trusted-execution", "git-execution").search(prose)
                )

    def test_git_by_an_unquoted_absolute_path_is_a_signature(self) -> None:
        """A shell line ran `/usr/bin/git status` unseen: only a quoted path to Git was
        matched (Codex on #369)."""
        for line in (
            "/usr/bin/git status",
            "exec /usr/bin/git status",
            "if ! /opt/git/bin/git diff --quiet; then",
            '    os.system("/usr/bin/git rev-parse HEAD")',
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("trusted-execution", "git-execution").search(line)
                )
        for line in ("ls -l /usr/bin/git", "# see /usr/bin/git status"):
            with self.subTest(line=line):
                self.assertFalse(
                    _pattern("trusted-execution", "git-execution").search(line)
                )

    def test_an_http_client_imported_by_name_is_a_signature(self) -> None:
        """`from http import client` made requests unseen: only dotted names were
        matched (Codex on #369). The family: a standard-library client imported by
        name, and a third-party client, whose import changes the lock but may already
        be installed."""
        for line in (
            "from http import client",
            "from http import client as transport",
            "from urllib import request",
            "from urllib import parse, request",
            "import requests",
            "from httpx import Client",
            "import urllib3",
            "import aiohttp",
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("github-rest-transport", "http-request").search(line)
                )
        for line in (
            "from http import HTTPStatus",
            "from urllib import parse",
            "import requests_mock_notes",
        ):
            with self.subTest(unmatched=line):
                self.assertFalse(
                    _pattern("github-rest-transport", "http-request").search(line)
                )

    def test_a_routing_variable_assigned_in_a_shell_is_a_signature(self) -> None:
        """`export GIT_DIR=/srv/repo` set Git's routing unseen: only a quoted or `$`
        name was matched (CodeAnt on #369). The family: export, a command's prefix,
        `env`, a workflow's `env:` key and a Dockerfile's `ENV`."""
        for line in (
            "export GIT_DIR=/srv/repo",
            "GIT_WORK_TREE=/srv/tree git status",
            "env GIT_INDEX_FILE=/srv/index git add x",
            "      GIT_DIR: /srv/repo",
            "ENV GIT_DIR /srv/repo",
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("trusted-execution", "git-environment").search(line)
                )
        for prose in (
            "# GIT_DIR names the metadata directory",
            "GIT_DIRS = 3",
            "GIT_DIR_LIST=a",
        ):
            with self.subTest(prose=prose):
                self.assertFalse(
                    _pattern("trusted-execution", "git-environment").search(prose)
                )

    def test_git_named_by_a_keyword_or_a_later_argument_is_a_signature(self) -> None:
        """`trusted_executable(name="git")` and `run(args, executable="git")` named Git
        unseen: only `("git")` and `"git",` were matched (Codex on #369)."""
        for line in (
            '    executable = trusted_execution.trusted_executable(name="git")',
            '    subprocess.run(args, executable="git")',
            "    found = lookup(kind, 'git')",
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("trusted-execution", "git-execution").search(line)
                )
        for prose in ('    labels = {"git": 1}', '    message = f"{name}: git tree"'):
            with self.subTest(prose=prose):
                self.assertFalse(
                    _pattern("trusted-execution", "git-execution").search(prose)
                )

    def test_git_with_no_subcommand_is_a_signature(self) -> None:
        """`git --version` and `git --help` run Git with no subcommand, so a probe for
        Git went unseen (Codex on #369)."""
        for line in (
            "git --version",
            "if ! git --version >/dev/null 2>&1; then",
            '    os.system("git -v")',
            "    subprocess.run('git --help', shell=True)",
            "  git -h",
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("trusted-execution", "git-execution").search(line)
                )
        self.assertFalse(
            _pattern("trusted-execution", "git-execution").search(
                "    git_version = parse(output)  # git --version"
            )
        )

    def test_git_in_a_shell_string_is_a_signature(self) -> None:
        """`subprocess.run("git status", shell=True)` and `os.system` ran Git unseen
        (Codex on #369)."""
        for line in (
            '    subprocess.run("git status", shell=True)',
            "    os.system('git -C repo log --oneline')",
            '    os.popen(f"git rev-parse {ref}")',
        ):
            with self.subTest(line=line):
                self.assertTrue(
                    _pattern("trusted-execution", "git-execution").search(line)
                )
        for prose in (
            '    raise ValueError("git: no such tree")',
            '    help = "a git tree"',
        ):
            with self.subTest(prose=prose):
                self.assertFalse(
                    _pattern("trusted-execution", "git-execution").search(prose)
                )

    def test_more_lookup_and_path_forms_are_signatures(self) -> None:
        """`from shutil import which` (Codex on #369) and any absolute path to `git`
        (CodeAnt on #369)."""
        for responsibility, signature, line in (
            ("trusted-execution", "executable-lookup", "from shutil import which"),
            (
                "trusted-execution",
                "executable-lookup",
                "from shutil import copy, which",
            ),
            (
                "trusted-execution",
                "git-execution",
                '    subprocess.run(["/opt/git/bin/git", "status"])',
            ),
            (
                "trusted-execution",
                "git-execution",
                "    GIT = '/usr/local/libexec/git'",
            ),
            (
                "trusted-execution",
                "git-execution",
                '    subprocess.run(["/usr/bin/git", "status"])',
            ),
        ):
            with self.subTest(line=line):
                self.assertTrue(_pattern(responsibility, signature).search(line))
        self.assertFalse(
            _pattern("trusted-execution", "git-execution").search(
                '    url = "https://github.com/ktogias/gnostoa"'
            )
        )

    def test_a_name_bound_to_git_is_a_signature(self) -> None:
        """`GIT = "git"`, then `[GIT, ...]`, runs Git outside the owner (Codex on
        #369); a value that only names Git is no execution."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            'GIT = "git"',
            "    _GIT: Final = 'git'",
            'git_name = "git"  # the tool',
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        self.assertFalse(pattern.search('        identity["authority"] = "git"'))

    def test_a_shell_name_bound_to_git_is_a_signature(self) -> None:
        """`git_cmd=git`, then `"$git_cmd" status`, runs Git outside the owner, and so
        do the unquoted path, the declarations and an alias (Codex on #369)."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "git_cmd=git",
            'git_cmd=git; "$git_cmd" status',
            "export GIT=/usr/bin/git",
            "readonly g=git  # Git",
            "  local git_bin=git",
            "declare -r GIT=git",
            "alias g=git",
            "alias g='git'",
            'alias g="/usr/bin/git"',
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ("VCS=github", "kind=git-lfs", 'git_cmd="$1"', "name=gitlab"):
            with self.subTest(unmarked=line):
                self.assertFalse(pattern.search(line))

    def test_a_wrapper_named_by_its_path_runs_git_too(self) -> None:
        """`/usr/bin/env git status` and `/usr/bin/timeout 10 git status` run Git as
        their bare names do (Codex on #369), and so does a wrapper whose option takes a
        word or a path, as `sudo -u builder git fetch` does."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "/usr/bin/env git status",
            "/usr/bin/timeout 10 git status",
            "if /usr/bin/env git diff --quiet; then",
            "head=$(/usr/bin/env git rev-parse HEAD)",
            "/usr/bin/sudo -u builder /usr/bin/git fetch",
            "/usr/bin/nice -n 5 /usr/bin/xargs git add",
            "sudo -u builder git fetch",
            "timeout -s KILL 10 git fetch",
            "flock /var/lock/repo git gc",
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ("#!/usr/bin/env bash", "/usr/bin/env python3 tool.py"):
            with self.subTest(unmarked=line):
                self.assertFalse(pattern.search(line))

    def test_env_s_options_that_take_an_argument_run_git_too(self) -> None:
        """`env -u GIT_DIR git status` and `env -C dir git status` run Git, but the
        argument after the option was read as the command (Codex on #369). `env -S`
        splits a string into the command, as `sh -c` runs one."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "env -u GIT_DIR git status",
            "/usr/bin/env -C /srv/work git status",
            "env --unset GIT_DIR git status",
            "env --chdir /srv/work git status",
            "env -i PATH=/usr/bin git status",
            "env -S 'git status'",
            "env --split-string='git status'",
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ("env -u GIT_DIR python3 tool.py", "env -S 'python3 tool.py'"):
            with self.subTest(unmarked=line):
                self.assertFalse(pattern.search(line))

    def test_git_after_a_shell_assignment_runs_it(self) -> None:
        """`LC_ALL=C git status` runs Git with one variable set, in any command
        position (Codex on #369)."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "LC_ALL=C git status",
            "FOO=bar /usr/bin/git status",
            "LANG=C LC_ALL=C git log --oneline",
            "out=$(LC_ALL=C git rev-parse HEAD)",
            "if GIT_TERMINAL_PROMPT=0 git fetch; then",
            "      run: LC_ALL=C git diff --exit-code",
            "sudo LC_ALL=C git gc",
            "env FOO=1 git status",
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ("LC_ALL=C python3 tool.py", "x=1 y=2", "FOO=bar github status"):
            with self.subTest(unmarked=line):
                self.assertFalse(pattern.search(line))

    def test_the_shell_s_own_lookup_is_a_signature(self) -> None:
        """`$(which git)` and `$(type -P git)` resolve an executable as `command -v`
        does (Codex on #369)."""
        pattern = _pattern("trusted-execution", "executable-lookup")
        for line in ("G=$(which git)", "G=`which git`", "G=$(type -P git)"):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        self.assertFalse(pattern.search("Check which git version is installed."))

    def test_a_loop_condition_or_a_group_runs_git_too(self) -> None:
        """`while git status; do` and `until git fetch; do` run Git as `if` does, and
        so does a brace group or a subshell that opens a line (Codex on #369)."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "while git status; do",
            "until git fetch; do sleep 1; done",
            "  while ! git diff --quiet; do",
            "      run: while git fetch; do sleep 1; done",
            "{ git status; }",
            "( git fetch )",
            "(git gc)",
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ("while true; do", "until [ -f done ]; do", "{ echo ok; }"):
            with self.subTest(unmarked=line):
                self.assertFalse(pattern.search(line))

    def test_make_runs_git_through_its_own_forms(self) -> None:
        """A recipe's `@`, `-` and `+` prefixes are Make's, and the command still runs
        (Codex on #369); `$(shell ...)` runs one too, and a variable can name Git."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "\t@git status",
            "\t-git fetch",
            "\t+git gc",
            "\t@-git status",
            "\t@env GIT_PAGER=cat git log",
            "VERSION := $(shell git describe --tags)",
            "GIT := git",
            "GIT ?= /usr/bin/git",
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ("- git status is shown below", "\t@echo done", "OUT := build"):
            with self.subTest(unmarked=line):
                self.assertFalse(pattern.search(line))

    def test_a_case_arm_runs_its_command(self) -> None:
        """Each arm of a `case` is `PATTERN) COMMANDS`, so the text after `)` runs
        (Codex on #369)."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "  check) git status ;;",
            "  a|b) git fetch ;;",
            'case "$m" in x) git gc ;; esac',
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        self.assertFalse(pattern.search("  check) echo ok ;;"))

    def test_an_archive_or_a_template_named_as_its_own_word_is_seen(self) -> None:
        """`["archive", tree]` uses Git's default format, and `"--template", empty`
        names the template as its own word (Codex on #369)."""
        for signature, line in (
            ("tree-archive", 'trusted_execution.run_git(["archive", tree], cwd=d)'),
            ("tree-archive", 'run_git(["archive", "--prefix=x/", tree])'),
            ("disposable-metadata", 'run_git(["init", "--bare", "--template", empty])'),
            ("disposable-metadata", "git init --bare --template /srv/empty repo"),
        ):
            with self.subTest(line=line):
                self.assertTrue(_pattern("trusted-execution", signature).search(line))
        self.assertFalse(
            _pattern("trusted-execution", "tree-archive").search('{"archive": 1}')
        )

    def test_git_s_other_bare_options_run_it(self) -> None:
        """`git --exec-path` runs Git with no subcommand, as `--version` does
        (CodeAnt on #369)."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            "git --exec-path",
            "git --html-path",
            "git --man-path",
            "git --info-path",
            "git --list-cmds=main",
            'PATH="$(git --exec-path):$PATH"',
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))

    def test_the_standard_entry_points_are_signatures(self) -> None:
        """`jsonschema.validate` and a directly imported YAML loader are the common
        ways to do what those owners do (Codex on #369)."""
        for responsibility, signature, line in (
            (
                "schema-validation",
                "jsonschema-validator",
                "    jsonschema.validate(document, schema)",
            ),
            (
                "schema-validation",
                "jsonschema-validator",
                "from jsonschema import validate",
            ),
            (
                "schema-validation",
                "jsonschema-validator",
                "    validator = Draft7Validator(schema)",
            ),
            ("yaml-loading", "yaml-load", "from yaml import safe_load"),
            ("yaml-loading", "yaml-load", "from yaml import CSafeLoader, load"),
            ("yaml-loading", "yaml-load", "    data = yaml.full_load(text)"),
        ):
            with self.subTest(line=line):
                self.assertTrue(_pattern(responsibility, signature).search(line))

    def test_running_git_directly_is_a_signature(self) -> None:
        """Running Git belongs to the owner, so a new `subprocess.run(["git", ...])`
        helper is a copy (Codex on #369)."""
        pattern = _pattern("trusted-execution", "git-execution")
        for line in (
            'subprocess.run(["git", "status"], check=True)',
            '            "git",',
            "head=$(git rev-parse HEAD)",
            '  git -C "$dir" ls-files -z',
            'test -z "$(git status --porcelain)"',
            "git archive HEAD | tar -x",
            # Obtaining the executable is how any caller runs Git, whatever the call's
            # layout or the name it is kept under (Codex on #369).
            "        trusted_execution.git_executable(),",
            "    executable = trusted_execution.git_executable()",
            "    git = trusted_execution.git_executable()",
            '    found = trusted_execution.trusted_executable("git")',
            '    subprocess.run(["/usr/bin/git", "status"], check=True)',
            "  git --no-pager status",
            # An import alias loses both the call's parentheses and the name `git`
            # at the call (Codex on #369).
            "from tools.trusted_execution import git_executable as executable",
            "    from tools import trusted_execution as te; run = te.git_executable",
            '    found = find("git")',
            # `env` looks Git up itself (Codex on #369).
            '    subprocess.run(["env", "git", "status"], check=True)',
            '    subprocess.run(["env", "GIT_TRACE=1", "git", "log"], check=True)',
            "  env git status",
            # `command` bypasses shell functions and aliases (CodeAnt on #369).
            "  command git status",
            # A command continued on the next line (CodeRabbit on #369).
            "    git \\",
            '    git -c "safe.directory=${repository_root}" \\',
            "  head=$(command -p git rev-parse HEAD)",
            '  env -i PATH="$PATH" git rev-parse HEAD',
            '  git --git-dir="$dir" log -1',
            # A resolved executable in a variable runs Git too (Codex on #369).
            '            [git, "add", "-A", "--force"],',
            "            [_git_executable(), *arguments],",
            '        [trusted_execution.git_executable(), "ls-files", "-z"],',
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in (
            "            git and no candidate tree. The change is in",
            "    git with which to check. They are escaped",
            '        raise PreparationError(f"git describe failed: {exc}") from exc',
            "    confirmed against ``git hash-object``. SHA-1 appears here",
            "replacement objects, and check `git show` success instead",
        ):
            with self.subTest(line=line):
                self.assertFalse(pattern.search(line))

    def test_every_owner_exists_and_names_its_registry_id(self) -> None:
        """An agent reading the owner learns it is the owner and how to extend it."""
        for entry in reuse_check.load_registry(REGISTRY):
            with self.subTest(responsibility=entry.id):
                owner = ROOT / entry.owner
                self.assertTrue(owner.is_file(), entry.owner)
                self.assertIn(
                    f"registry id `{entry.id}`", owner.read_text(encoding="utf-8")
                )


class CheckTests(unittest.TestCase):
    @staticmethod
    def _check(files: dict[str, str]) -> list[str]:
        with _tree({"policy/r.yaml": _REGISTRY_TEXT, **files}) as scratch:
            root = pathlib.Path(scratch)
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            return [str(v) for v in reuse_check.violations(root, registry)]

    def test_a_planted_copy_is_reported_with_its_place(self) -> None:
        found = self._check(
            {
                "tools/owner.py": "GIT_CONFIG_GLOBAL\n",
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "tools/new.py": "x = 1\nenv = {'GIT_CONFIG_GLOBAL': '/dev/null'}\n",
            }
        )
        self.assertEqual(1, len(found), found)
        self.assertIn("tools/new.py:2", found[0])
        self.assertIn("trusted-execution", found[0])
        self.assertIn("tools/owner.py", found[0])

    def test_a_copy_in_any_production_surface_is_seen(self) -> None:
        for path in (
            "ci/some-script",
            "AGENTS.md",
            ".github/workflows/w.yml",
            "tools/x/y.py",
        ):
            with self.subTest(path=path):
                found = self._check(
                    {
                        "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                        path: "GIT_CONFIG_GLOBAL=/dev/null\n",
                    }
                )
                self.assertEqual(1, len(found), found)

    def test_a_copy_outside_the_listed_directories_is_seen(self) -> None:
        """Production is everything but tests, knowledge, guidance and documents, so a
        copy under `tasks/` or a new directory does not escape (CodeAnt on #369)."""
        for path in ("tasks/orientation.py", "scripts/new-tool", "core/x.yaml"):
            with self.subTest(path=path):
                found = self._check(
                    {
                        "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                        path: "GIT_CONFIG_GLOBAL\n",
                    }
                )
                self.assertEqual(1, len(found), found)

    def test_a_new_copy_in_a_file_that_owes_debt_is_seen(self) -> None:
        """Debt names its lines: one more in the same file is a new copy, not old
        debt (CodeAnt on #369)."""
        found = self._check(
            {"tools/pending.py": "GIT_CONFIG_GLOBAL\nGIT_CONFIG_GLOBAL\n"}
        )
        self.assertEqual(1, len(found), found)
        self.assertIn("tools/pending.py", found[0])
        self.assertIn("2", found[0])

    def test_a_swapped_line_in_a_file_that_owes_debt_is_seen(self) -> None:
        """A count of lines stayed equal when one owed line went and a new copy came
        (Codex on #369): debt is the exact lines it names."""
        found = self._check(
            {"tools/pending.py": 'x = 1\nos.environ["GIT_CONFIG_GLOBAL"] = ""\n'}
        )
        self.assertTrue(any(f.startswith("tools/pending.py:2:") for f in found), found)
        # The line the entry names has gone, so the entry must shrink.
        self.assertTrue(
            any("'GIT_CONFIG_GLOBAL' no longer matches" in f for f in found), found
        )

    def test_a_failed_stat_closes_the_file(self) -> None:
        """An `fstat` that raised left the descriptor open (CodeAnt on #369)."""
        with _tree({"tools/a.py": "x = 1\n"}) as scratch:
            root = pathlib.Path(scratch)
            before = len(os.listdir("/dev/fd"))
            with (
                mock.patch.object(os, "fstat", side_effect=OSError(5, "I/O error")),
                self.assertRaises(OSError),
            ):
                list(reuse_check._lines(root, "tools/a.py"))  # skipcq: PYL-W0212
            self.assertEqual(before, len(os.listdir("/dev/fd")))

    def test_a_registry_that_is_not_utf_8_is_an_error_result(self) -> None:
        """`UnicodeDecodeError` escaped `main` as a traceback (CodeAnt on #369)."""
        with _tree({"policy/r.yaml": ""}) as scratch:
            registry = pathlib.Path(scratch) / "policy" / "r.yaml"
            registry.write_bytes(b"id: \xff\xfe\n")
            code = reuse_check.main(["--root", scratch, "--registry", str(registry)])
            self.assertEqual(2, code)

    def test_a_large_tracked_file_is_read_a_line_at_a_time(self) -> None:
        """A file was read whole, then decoded and split, so its size was held three
        times over (CodeAnt on #369)."""
        line = "x" * 999 + "\n"
        with _tree(
            {"policy/r.yaml": _REGISTRY_TEXT, "tools/big.py": line * 20_000}
        ) as scratch:
            root = pathlib.Path(scratch)
            # Tracked, so production is read through Git's file list, not a walk
            # (CodeAnt on #369).
            environment = {
                "PATH": "/usr/bin:/bin",
                "HOME": scratch,
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            for arguments in (["init", "--quiet"], ["add", "policy", "tools"]):
                subprocess.run(  # nosec B603 B607
                    ["git", "-C", scratch, *arguments], check=True, env=environment
                )
            listed = trusted_execution.repository_files(root)
            self.assertIsNotNone(listed)
            self.assertIn("tools/big.py", listed or ())
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            tracemalloc.start()
            try:
                reuse_check.violations(root, registry)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        self.assertLess(peak, 4_000_000, f"peak {peak} bytes for a 20 MB file")

    def test_the_registry_itself_is_not_a_copy(self) -> None:
        found = self._check(
            {
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "policy/r.yaml": _REGISTRY_TEXT + "# GIT_CONFIG_GLOBAL\n",
            }
        )
        self.assertEqual([], found)

    def test_an_untracked_file_of_a_repository_is_not_production(self) -> None:
        """In a repository, production is what is tracked: a developer's virtualenv
        or scratch file is not the product."""
        with _tree(
            {
                "policy/r.yaml": _REGISTRY_TEXT,
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "venv/lib/x.py": "GIT_CONFIG_GLOBAL\n",
            }
        ) as scratch:
            root = pathlib.Path(scratch)
            environment = {
                "PATH": "/usr/bin:/bin",
                "HOME": scratch,
                "GIT_CONFIG_NOSYSTEM": "1",
            }
            for arguments in (["init", "--quiet"], ["add", "policy", "tools"]):
                subprocess.run(  # nosec B603 B607
                    ["git", "-C", scratch, *arguments], check=True, env=environment
                )
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            self.assertEqual(
                [], [str(v) for v in reuse_check.violations(root, registry)]
            )

    def test_the_owner_is_allowed_without_repeating_itself(self) -> None:
        """The registered owner is where the signature belongs (CodeRabbit on #369)."""
        registry = _REGISTRY_TEXT.replace(
            "    allowed:\n      - path: tools/owner.py\n        reason: the owner\n",
            "    allowed: []\n",
        )
        with _tree(
            {
                "policy/r.yaml": registry,
                "tools/owner.py": "GIT_CONFIG_GLOBAL\n",
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
            }
        ) as scratch:
            root = pathlib.Path(scratch)
            found = reuse_check.violations(
                root, reuse_check.load_registry(root / "policy" / "r.yaml")
            )
            self.assertEqual([], [str(v) for v in found])

    def test_an_undecodable_file_is_still_read(self) -> None:
        """One invalid byte must not hide a copy (CodeRabbit on #369)."""
        with _tree(
            {"policy/r.yaml": _REGISTRY_TEXT, "tools/pending.py": "GIT_CONFIG_GLOBAL\n"}
        ) as scratch:
            root = pathlib.Path(scratch)
            (root / "ci").mkdir()
            (root / "ci" / "script").write_bytes(
                b"\xff\xfe broken\nexport GIT_CONFIG_GLOBAL=/dev/null\n"
            )
            found = reuse_check.violations(
                root, reuse_check.load_registry(root / "policy" / "r.yaml")
            )
            self.assertEqual(1, len(found), [str(v) for v in found])
            self.assertIn("ci/script:2", str(found[0]))

    def test_outside_a_repository_a_hidden_build_directory_is_not_production(
        self,
    ) -> None:
        """An installed tree is no repository, so it is walked; a generated directory
        such as `.evidence/` is not the product, while `.github` is."""
        found = self._check(
            {
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                ".evidence/report.json": "GIT_CONFIG_GLOBAL\n",
                ".github/workflows/w.yml": "GIT_CONFIG_GLOBAL\n",
            }
        )
        self.assertEqual(1, len(found), found)
        self.assertIn(".github/workflows/w.yml", found[0])

    def test_a_responsibility_without_a_signature_is_refused(self) -> None:
        """An entry with no signature would never be enforced (Codex on #369)."""
        registry = _REGISTRY_TEXT.replace(
            "    signatures:\n      - id: git-environment\n"
            "        pattern: 'GIT_CONFIG_GLOBAL'\n"
            "        means: a Git environment built outside the owner\n",
            "    signatures: []\n",
        )
        self.assertIn("signatures: []", registry)
        with _tree({"policy/r.yaml": registry}) as scratch:
            errors = reuse_check.registry_errors(
                pathlib.Path(scratch) / "policy" / "r.yaml"
            )
            self.assertTrue(any("signatures" in error for error in errors), errors)

    def test_a_tracked_path_that_is_not_utf8_is_read(self) -> None:
        """`git ls-files -z` writes a path's bytes as they are (CodeRabbit and CodeAnt
        on #369)."""
        with _tree(
            {"policy/r.yaml": _REGISTRY_TEXT, "tools/pending.py": "GIT_CONFIG_GLOBAL\n"}
        ) as scratch:
            root = pathlib.Path(scratch)
            name = os.fsdecode(b"tools/caf\xe9.py")
            (root / name).write_text("GIT_CONFIG_GLOBAL\n", encoding="utf-8")
            _init(root, "policy", "tools")
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            found = [str(v) for v in reuse_check.violations(root, registry)]
            self.assertEqual(1, len(found), found)
            self.assertIn("tools/caf\\xe9.py:1", found[0])

    def test_a_repository_git_cannot_list_is_an_error_not_a_walk(self) -> None:
        """Walking a checkout would read its untracked files as production, so a
        failure to list it is an error, not a reason to walk (CodeRabbit on #369)."""
        with _tree(
            {
                "policy/r.yaml": _REGISTRY_TEXT,
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "venv/x.py": "GIT_CONFIG_GLOBAL\n",
            }
        ) as scratch:
            root = pathlib.Path(scratch)
            _init(root, "policy", "tools")
            (root / ".git" / "index").write_bytes(b"not an index")
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                reuse_check.violations(root, registry)

    def test_a_production_file_that_cannot_be_read_is_an_error(self) -> None:
        """A file the check cannot read would otherwise pass as clean (CodeAnt on
        #369)."""
        if os.geteuid() == 0:
            self.skipTest("root reads a file whatever its mode")
        with _tree(
            {
                "policy/r.yaml": _REGISTRY_TEXT,
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "tools/sealed.py": "GIT_CONFIG_GLOBAL\n",
            }
        ) as scratch:
            root = pathlib.Path(scratch)
            sealed = root / "tools" / "sealed.py"
            sealed.chmod(0)
            try:
                registry = reuse_check.load_registry(root / "policy" / "r.yaml")
                with self.assertRaises(OSError):
                    reuse_check.violations(root, registry)
            finally:
                sealed.chmod(0o644)

    def test_a_tracked_link_is_not_followed(self) -> None:
        """A link's target is no file of the product: one to `/dev/zero` never ends,
        and one outside the tree is not production (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as outside:
            elsewhere = pathlib.Path(outside) / "elsewhere.py"
            elsewhere.write_text("GIT_CONFIG_GLOBAL\n", encoding="utf-8")
            with _tree(
                {
                    "policy/r.yaml": _REGISTRY_TEXT,
                    "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                }
            ) as scratch:
                root = pathlib.Path(scratch)
                (root / "tools" / "linked.py").symlink_to(elsewhere)
                _init(root, "policy", "tools")
                registry = reuse_check.load_registry(root / "policy" / "r.yaml")
                self.assertEqual(
                    [], [str(v) for v in reuse_check.violations(root, registry)]
                )

    def test_a_submodule_holds_no_copy(self) -> None:
        """A gitlink is listed, but it is a directory, not a file of the product."""
        with _tree(
            {"policy/r.yaml": _REGISTRY_TEXT, "tools/pending.py": "GIT_CONFIG_GLOBAL\n"}
        ) as scratch:
            root = pathlib.Path(scratch)
            _init(root, "policy", "tools")
            (root / "vendor").mkdir()
            subprocess.run(  # nosec B603 B607
                [
                    "git",
                    "-C",
                    scratch,
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    "160000,0123456789abcdef0123456789abcdef01234567,vendor",
                ],
                check=True,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": scratch,
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
            )
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            self.assertEqual(
                [], [str(v) for v in reuse_check.violations(root, registry)]
            )

    def test_a_tracked_link_loop_holds_no_copy(self) -> None:
        """Resolving a looping link raised `RuntimeError` and crashed the check
        (CodeAnt on #369)."""
        with _tree(
            {"policy/r.yaml": _REGISTRY_TEXT, "tools/pending.py": "GIT_CONFIG_GLOBAL\n"}
        ) as scratch:
            root = pathlib.Path(scratch)
            (root / "tools" / "loop.py").symlink_to("loop.py")
            _init(root, "policy", "tools")
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            self.assertEqual(
                [], [str(v) for v in reuse_check.violations(root, registry)]
            )

    def test_a_tracked_file_missing_from_the_work_tree_has_nothing_to_copy(
        self,
    ) -> None:
        """A file deleted but not yet staged is still listed; it holds no copy."""
        with _tree(
            {
                "policy/r.yaml": _REGISTRY_TEXT,
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "tools/gone.py": "x = 1\n",
            }
        ) as scratch:
            root = pathlib.Path(scratch)
            _init(root, "policy", "tools")
            (root / "tools" / "gone.py").unlink()
            registry = reuse_check.load_registry(root / "policy" / "r.yaml")
            self.assertEqual(
                [], [str(v) for v in reuse_check.violations(root, registry)]
            )

    def test_tests_and_knowledge_are_not_production(self) -> None:
        found = self._check(
            {
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "tests/test_x.py": "GIT_CONFIG_GLOBAL\n",
                "knowledge/notes.md": "GIT_CONFIG_GLOBAL\n",
            }
        )
        self.assertEqual([], found)

    def test_debt_that_no_longer_matches_is_reported_so_it_only_shrinks(self) -> None:
        found = self._check({"tools/pending.py": "migrated = True\n"})
        self.assertEqual(1, len(found), found)
        self.assertIn("stale debt", found[0])
        self.assertIn("tools/pending.py", found[0])
        # Nothing left to owe: the entry goes, not merely shrinks.
        self.assertIn("remove the entry", found[0])

    def test_a_missing_debt_file_is_stale_too(self) -> None:
        found = self._check({})
        self.assertEqual(1, len(found), found)
        self.assertIn("stale debt", found[0])
        self.assertIn("remove the entry", found[0])


class CommandTests(unittest.TestCase):
    def test_the_command_exits_one_on_a_copy_and_zero_when_clean(self) -> None:
        with _tree(
            {
                "policy/r.yaml": _REGISTRY_TEXT,
                "tools/pending.py": "GIT_CONFIG_GLOBAL\n",
                "tools/new.py": "GIT_CONFIG_GLOBAL\n",
            }
        ) as scratch:
            root = pathlib.Path(scratch)
            self.assertEqual(
                1,
                reuse_check.main(
                    ["--root", str(root), "--registry", str(root / "policy" / "r.yaml")]
                ),
            )
            (root / "tools" / "new.py").write_text("clean = True\n", encoding="utf-8")
            self.assertEqual(
                0,
                reuse_check.main(
                    ["--root", str(root), "--registry", str(root / "policy" / "r.yaml")]
                ),
            )


class SignatureScopeTests(unittest.TestCase):
    def test_the_tree_archive_signature_is_an_archive_of_a_tree(self) -> None:
        """A quoted word `archive` alone is not a copy (CodeAnt on #369)."""
        pattern = _pattern("trusted-execution", "tree-archive")
        for line in (
            '    [git, "archive", "--format=tar", tree],',
            'git archive "${commit}" | tar -x -C out',
            "subprocess.run(['git', 'archive', '--format', 'tar', tree])",
        ):
            with self.subTest(line=line):
                self.assertTrue(pattern.search(line))
        for line in ('kind = "archive"', '    "archive": archive_path,'):
            with self.subTest(line=line):
                self.assertFalse(pattern.search(line))


class CommandFailureTests(unittest.TestCase):
    def test_the_command_exits_two_when_it_cannot_check(self) -> None:
        """A repository Git cannot list is neither clean nor a copy: the command says
        so and exits two, rather than walking the checkout (CodeRabbit on #369)."""
        with _tree(
            {"policy/r.yaml": _REGISTRY_TEXT, "tools/pending.py": "GIT_CONFIG_GLOBAL\n"}
        ) as scratch:
            root = pathlib.Path(scratch)
            _init(root, "policy", "tools")
            (root / ".git" / "index").write_bytes(b"not an index")
            code = reuse_check.main(
                ["--root", scratch, "--registry", str(root / "policy" / "r.yaml")]
            )
            self.assertEqual(2, code)

    def test_the_command_exits_two_on_a_pattern_that_is_no_regular_expression(
        self,
    ) -> None:
        """A schema-valid registry can still hold a broken pattern (CodeAnt on
        #369)."""
        registry = _REGISTRY_TEXT.replace(
            "pattern: 'GIT_CONFIG_GLOBAL'", "pattern: 'GIT_CONFIG_(GLOBAL'"
        )
        self.assertIn("GIT_CONFIG_(GLOBAL", registry)
        with _tree({"policy/r.yaml": registry}) as scratch:
            root = pathlib.Path(scratch)
            code = reuse_check.main(
                ["--root", scratch, "--registry", str(root / "policy" / "r.yaml")]
            )
            self.assertEqual(2, code)

    def test_the_command_exits_two_on_a_pattern_too_deep_to_compile(self) -> None:
        """`re.compile` raises `RecursionError`, not `re.error`, on a deeply nested
        pattern (CodeAnt on #369)."""
        deep = "(?:" * 1000 + "a" + ")" * 1000
        registry = _REGISTRY_TEXT.replace(
            "pattern: 'GIT_CONFIG_GLOBAL'", f"pattern: '{deep}'"
        )
        with _tree({"policy/r.yaml": registry}) as scratch:
            root = pathlib.Path(scratch)
            code = reuse_check.main(
                ["--root", scratch, "--registry", str(root / "policy" / "r.yaml")]
            )
            self.assertEqual(2, code)

    def test_a_signature_id_used_twice_is_refused(self) -> None:
        """An allowance for one pattern would cover another of the same id
        (CodeAnt on #369)."""
        registry = _REGISTRY_TEXT.replace(
            "        means: a Git environment built outside the owner\n",
            "        means: a Git environment built outside the owner\n"
            "      - id: git-environment\n"
            "        pattern: 'GIT_DIR'\n"
            "        means: another pattern under the same id\n",
            1,
        )
        with (
            _tree({"policy/r.yaml": registry}) as scratch,
            self.assertRaises(KnowledgeFormatError),
        ):
            reuse_check.load_registry(pathlib.Path(scratch) / "policy" / "r.yaml")

    def test_a_responsibility_id_used_twice_is_refused(self) -> None:
        """Two entries under one id leave a responsibility with no single owner, and
        the check passed (Codex on #369)."""
        registry = _REGISTRY_TEXT + (
            "  - id: trusted-execution\n"
            "    responsibility: Running a tool with trust, again.\n"
            "    owner: tools/other_owner.py\n"
            "    interface: [run]\n"
            "    extend: Extend tools/other_owner.py.\n"
            "    decision: knowledge/decisions/0102-own-trusted-execution-in-one-hardened-module.md\n"
            "    signatures:\n"
            "      - id: git-environment\n"
            "        pattern: 'GIT_DIR'\n"
            "        means: a Git environment built outside the other owner\n"
            "    allowed: []\n"
            "    debt: []\n"
        )
        with (
            _tree({"policy/r.yaml": registry}) as scratch,
            self.assertRaisesRegex(KnowledgeFormatError, "trusted-execution"),
        ):
            reuse_check.load_registry(pathlib.Path(scratch) / "policy" / "r.yaml")

    def test_a_path_owing_debt_twice_is_refused(self) -> None:
        """Two debt entries for one path pooled their counts, so each looked changed
        (CodeAnt on #369)."""
        registry = _REGISTRY_TEXT.replace(
            "        until: https://github.com/ktogias/gnostoa/issues/368\n",
            "        until: https://github.com/ktogias/gnostoa/issues/368\n"
            "      - path: tools/pending.py\n"
            "        signatures: [git-environment]\n"
            "        lines: [GIT_CONFIG_GLOBAL]\n"
            "        until: https://github.com/ktogias/gnostoa/issues/365\n",
            1,
        )
        with (
            _tree({"policy/r.yaml": registry}) as scratch,
            self.assertRaises(KnowledgeFormatError),
        ):
            reuse_check.load_registry(pathlib.Path(scratch) / "policy" / "r.yaml")

    def test_the_registry_is_read_once(self) -> None:
        """What is checked against the schema is what is used: reading the file twice
        let a concurrent edit through unchecked (CodeAnt on #369)."""
        from tools import knowledge_common

        real = knowledge_common.load_yaml
        reads: list[object] = []

        def counting(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            reads.append(path)
            return real(path, *args, **kwargs)

        with (
            _tree({"policy/r.yaml": _REGISTRY_TEXT}) as scratch,
            mock.patch.object(reuse_check, "load_yaml", counting),
        ):
            reuse_check.load_registry(pathlib.Path(scratch) / "policy" / "r.yaml")
        self.assertEqual(1, len(reads), reads)

    def test_the_command_exits_two_on_an_invalid_registry(self) -> None:
        """A registry that breaks its schema cannot be checked against; it is not a
        crash (CodeRabbit on #369)."""
        with _tree({"policy/r.yaml": "id: broken\n"}) as scratch:
            root = pathlib.Path(scratch)
            code = reuse_check.main(
                ["--root", scratch, "--registry", str(root / "policy" / "r.yaml")]
            )
            self.assertEqual(2, code)


if __name__ == "__main__":
    unittest.main()
