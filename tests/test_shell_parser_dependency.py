"""The pinned shell parser pair is installed, compatible, and reads the constructs
the shell reader relies on (Decision 0108)."""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
import unittest
from importlib import metadata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "shell_parser_probe.py"
# GitHub Actions expressions are not shell; each is masked at its own width.
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
SHELL_SHEBANG = re.compile(r"\A#!\s*/(?:usr/)?bin/(?:env\s+)?(?:ba|da)?sh\b")


def _probe(scripts: list[str]) -> list[dict[str, object]]:
    """The probe's facts for ``scripts``, from a child process: a native crash fails
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
    facts: list[dict[str, object]] = json.loads(done.stdout)
    return facts


def _workflow_runs(path: Path) -> list[str]:
    found: list[str] = []
    stack = [yaml.safe_load(path.read_text(encoding="utf-8"))]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "run" and isinstance(value, str):
                    found.append(
                        EXPRESSION.sub(lambda match: "_" * len(match.group(0)), value)
                    )
                else:
                    stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
    return found


def _shell_surfaces() -> dict[str, str]:
    """Each workflow or action `run:` value, and each shell script under `ci`,
    `templates` and `.githooks`, whole."""
    surfaces: dict[str, str] = {}
    for path in sorted((ROOT / ".github").rglob("*.y*ml")):
        for index, text in enumerate(_workflow_runs(path)):
            surfaces[f"{path.relative_to(ROOT)}#{index}"] = text
    for directory in ("ci", "templates", ".githooks"):
        for path in sorted((ROOT / directory).rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if SHELL_SHEBANG.match(text):
                surfaces[str(path.relative_to(ROOT))] = text
    return surfaces


class ShellParserDependencyTests(unittest.TestCase):
    def test_the_pinned_pair_is_installed(self) -> None:
        """`tree-sitter` 0.26.0 segfaulted with this grammar in the evaluation, so
        the pair is pinned together."""
        self.assertEqual("0.25.2", metadata.version("tree-sitter"))
        self.assertEqual("0.25.1", metadata.version("tree-sitter-bash"))

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
        }
        facts = _probe(list(cases))
        for (text, names), found in zip(cases.items(), facts, strict=True):
            with self.subTest(text=text):
                self.assertEqual(sorted(names), found["names"])
                self.assertEqual(0, found["errors"])
        [heredoc] = _probe(['bash 2>&1 <<EOF\n"git" status\nEOF\n'])
        self.assertEqual(['"git" status\n'], heredoc["heredocs"])

    def test_every_shell_surface_parses_without_an_error(self) -> None:
        surfaces = _shell_surfaces()
        self.assertGreater(len(surfaces), 50)
        facts = _probe(list(surfaces.values()))
        broken = [
            name for name, found in zip(surfaces, facts, strict=True) if found["errors"]
        ]
        self.assertEqual([], broken)


if __name__ == "__main__":
    unittest.main()
