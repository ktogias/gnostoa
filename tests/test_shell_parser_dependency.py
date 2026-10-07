"""The pinned shell parser pair is installed, compatible, and reads the constructs
the shell reader relies on (Decision 0108)."""

from __future__ import annotations

import json
import os
import re
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
import tempfile
import tomllib
import unittest
from importlib import metadata
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "shell_parser_probe.py"
# GitHub Actions expressions are not shell; each is masked at its own width.
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
SHELL_SHEBANG = re.compile(rb"\A#!\s*/(?:usr/)?bin/(?:env\s+)?(?:ba|da)?sh\b")
BOM = b"\xef\xbb\xbf"
# The instruction files whose shell fences agents run.
INSTRUCTION_FILES = ("AGENTS.md",)
FENCE = re.compile(r"^```(?:bash|sh|shell)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
# A documentation placeholder, such as `<exact-40-character-parent-sha>`: not shell.
PLACEHOLDER = re.compile(r"<[a-z0-9][a-z0-9-]*>")
RUN = re.compile(r"[ \t]*RUN[ \t]+(.*)", re.I)
RUN_FLAGS = re.compile(r"\A(?:--[a-z-]+(?:=\S*)?[ \t]+)*")
MAKEFILE = re.compile(r"\A(?:GNUmakefile|[Mm]akefile|.+\.mk)\Z")
# Directories that hold no source: caches, environments and Git's own metadata.
PRUNED = {".git", "__pycache__", ".mypy_cache", ".ruff_cache", ".venv", "node_modules"}
KEPT_DOT_DIRECTORIES = {".github", ".githooks", ".devcontainer"}


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
        answer: dict[str, object] = json.loads(done.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"the parser probe answered no JSON ({exc}): {done.stdout[-2000:]!r}"
        ) from exc
    return answer


def _facts(scripts: list[str]) -> list[dict[str, object]]:
    facts: list[dict[str, object]] = _probe(scripts)["facts"]  # type: ignore[assignment]
    return facts


def _workflow_runs(path: Path) -> list[str]:
    """Each shell `run:` value of a workflow or action, with its expressions masked.
    A step in another language fails closed: this reads shell only."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise AssertionError(f"{path}: not YAML: {exc}") from exc
    found: list[str] = []
    stack = [document]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("run"), str):
                if node.get("shell", "bash") not in ("bash", "sh"):
                    raise AssertionError(
                        f"{path}: a `{node['shell']}` step; extend this extraction"
                    )
                found.append(
                    EXPRESSION.sub(lambda match: "_" * len(match.group(0)), node["run"])
                )
            stack.extend(value for key, value in node.items() if key != "run")
        elif isinstance(node, list):
            stack.extend(node)
    return found


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
        while command.endswith("\\") and index < len(lines):
            line = lines[index]
            index += 1
            if not line.lstrip().startswith("#"):
                command = command[:-1] + line
        command = RUN_FLAGS.sub("", command)
        if command.lstrip().startswith("["):
            continue
        if "<<" in command:
            raise AssertionError("a RUN here-document; extend this extraction")
        runs.append(command)
    return runs


def _files(root: Path) -> list[Path]:
    """Every regular file under ``root``, but in caches, environments and Git's
    metadata."""
    found: list[Path] = []
    for directory, names, files in os.walk(root):
        names[:] = sorted(
            name
            for name in names
            if name not in PRUNED
            and (not name.startswith(".") or name in KEPT_DOT_DIRECTORIES)
        )
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_file() and not path.is_symlink():
                found.append(path)
    return found


def _shell_surfaces(root: Path = ROOT) -> dict[str, str]:
    """Every shell surface of the kinds the frozen corpus held (Decision 0108):
    - each workflow or action `run:` value;
    - each shell script, by its shebang, anywhere;
    - each shell fence of the instruction files;
    - each shell-form `RUN` of the Dockerfile.
    A Make recipe fails closed: none is tracked, and none was in the corpus."""
    surfaces: dict[str, str] = {}
    for path in _files(root):
        name = path.relative_to(root).as_posix()
        if MAKEFILE.match(path.name):
            raise AssertionError(f"{name}: a Make recipe; extend this extraction")
        if name.startswith(".github/") and path.suffix in (".yml", ".yaml"):
            for index, text in enumerate(_workflow_runs(path)):
                surfaces[f"{name}#{index}"] = text
            continue
        if name in INSTRUCTION_FILES:
            text = path.read_text(encoding="utf-8-sig")
            for index, fence in enumerate(FENCE.findall(text)):
                surfaces[f"{name}#{index}"] = fence
            continue
        if path.name == "Dockerfile":
            text = path.read_text(encoding="utf-8-sig")
            for index, run in enumerate(_dockerfile_runs(text)):
                surfaces[f"{name}#{index}"] = run
            continue
        with path.open("rb") as handle:
            head = handle.read(256).removeprefix(BOM)
        if SHELL_SHEBANG.match(head):
            # A shell script that is not UTF-8 fails here, loudly.
            surfaces[name] = path.read_text(encoding="utf-8-sig")
    return surfaces


class ShellParserDependencyTests(unittest.TestCase):
    def test_the_pinned_pair_is_installed(self) -> None:
        """`tree-sitter` 0.26.0 segfaulted with this grammar in the evaluation, so
        the pair is pinned together; the grammar's ABI is the runtime's."""
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

    def test_every_shell_surface_parses_without_an_unexpected_error(self) -> None:
        """Every surface kind of the frozen corpus parses with no error but the
        instruction fences' placeholders, which are documentation, not shell
        (Codex, Kody and CodeAnt on #394)."""
        surfaces = _shell_surfaces()
        self.assertGreater(len(surfaces), 50)
        for kind in (
            ".github/workflows/verification.yml#",
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
        placeholders = {
            name
            for name, text in surfaces.items()
            if name.startswith(INSTRUCTION_FILES) and PLACEHOLDER.search(text)
        }
        self.assertTrue(placeholders)
        self.assertEqual(placeholders, broken)


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

    def test_a_run_here_document_or_another_escape_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "here-document"):
            _dockerfile_runs("RUN <<EOF\ngit status\nEOF\n")
        with self.assertRaisesRegex(AssertionError, "escape directive"):
            _dockerfile_runs("# escape=`\nRUN true\n")

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
            (root / "Dockerfile").write_text("FROM a\nRUN git fetch\n", "utf-8")
            (root / "deep" / "er").mkdir(parents=True)
            (root / "deep" / "er" / "tool").write_bytes(BOM + b"#!/bin/sh\ngit gc\n")
            (root / "deep" / "data.bin").write_bytes(b"\xff\xfe")
            (root / ".cache").mkdir()
            (root / ".cache" / "tool").write_text("#!/bin/sh\nskipped\n", "utf-8")
            self.assertEqual(
                {
                    ".github/workflows/w.yml#0": "git status",
                    "AGENTS.md#0": "git log <ref>\n",
                    "Dockerfile#0": "git fetch",
                    "deep/er/tool": "#!/bin/sh\ngit gc\n",
                },
                _shell_surfaces(root),
            )
            (root / "deep" / "er" / "tool").write_bytes(b"#!/bin/sh\n\xff\n")
            with self.assertRaises(UnicodeDecodeError):
                _shell_surfaces(root)
            (root / "deep" / "er" / "tool").unlink()
            (root / "Makefile").write_text("all:\n\tgit status\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "Makefile: a Make recipe"):
                _shell_surfaces(root)

    def test_a_probe_answer_that_is_not_json_is_reported(self) -> None:
        answer = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="warn", stderr=""
        )
        with (
            patch("subprocess.run", return_value=answer),
            self.assertRaisesRegex(AssertionError, "answered no JSON.*'warn'"),
        ):
            _probe([])


if __name__ == "__main__":
    unittest.main()
