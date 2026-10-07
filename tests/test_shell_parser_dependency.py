"""The pinned shell parser pair is installed, compatible, and reads the constructs
the shell reader relies on (Decision 0108)."""

from __future__ import annotations

import hashlib
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
from types import SimpleNamespace
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).resolve().parent / "shell_parser_probe.py"
# GitHub Actions expressions are not shell; each is masked at its own width.
EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)
# A shebang's interpreter: its last path part, after `env` and its options.
SHEBANG = re.compile(rb"\A#![ \t]*(?:\S*/)?(?:env[ \t]+(?:-\S+[ \t]+)*)?([\w.+-]+)")
SHELLS = {b"sh", b"bash", b"dash", b"ash"}
OTHER_SHELLS = {
    b"zsh",
    b"ksh",
    b"mksh",
    b"oksh",
    b"fish",
    b"csh",
    b"tcsh",
    b"yash",
    b"posh",
}
# A YAML key that holds shell in a CI definition.
CI_KEY = re.compile(r"^\s*(?:-\s*)?(?:run|script|before_script|after_script)\s*:", re.M)
GITLAB_KEYS = ("before_script", "script", "after_script")
BOM = b"\xef\xbb\xbf"
# The instruction files whose shell fences agents run.
INSTRUCTION_FILES = ("AGENTS.md",)
FENCE = re.compile(r"^```(?:bash|sh|shell)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
# A documentation placeholder, such as `<exact-40-character-parent-sha>`: not shell.
PLACEHOLDER = re.compile(r"<[a-z0-9][a-z0-9-]*>")
RUN = re.compile(r"[ \t]*RUN[ \t]+(.*)", re.I)
RUN_FLAGS = re.compile(r"\A(?:--[a-z-]+(?:=\S*)?[ \t]+)*")
MAKEFILE = re.compile(r"\A(?:GNUmakefile|[Mm]akefile|.+\.mk)\Z")
CONTAINER_FILE = re.compile(r"(?i)\A(?:.*\.)?(?:dockerfile|containerfile)(?:\..*)?\Z")
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


def _github_runs(path: Path, document: object) -> list[str]:
    found: list[str] = []
    stack = [document]
    while stack:
        node = stack.pop()
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
            stack.extend(value for key, value in node.items() if key != "run")
        elif isinstance(node, list):
            stack.extend(node)
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
                lines = [
                    line
                    for item in value
                    for line in (item if isinstance(item, list) else [item])
                ]
                found.append("\n".join(str(line) for line in lines))
    return found


def _ci_shell(path: Path, under_github: bool) -> list[str]:
    """The shell of a CI definition, read by its shape wherever it sits: a GitHub
    workflow or action, or a GitLab CI file. A YAML file outside `.github` that
    holds a shell key in another shape fails closed (CodeAnt on #394)."""
    if not under_github and not CI_KEY.search(path.read_text(encoding="utf-8-sig")):
        return []
    document = _load_yaml(path)
    if under_github or (
        isinstance(document, dict) and ("jobs" in document or "runs" in document)
    ):
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
        name = path.relative_to(root).as_posix()
        if MAKEFILE.match(path.name):
            raise AssertionError(f"{name}: a Make recipe; extend this extraction")
        if path.suffix in (".yml", ".yaml"):
            for index, text in enumerate(_ci_shell(path, name.startswith(".github/"))):
                surfaces[f"{name}#{index}"] = text
            continue
        if name in INSTRUCTION_FILES:
            text = path.read_text(encoding="utf-8-sig")
            for index, fence in enumerate(FENCE.findall(text)):
                surfaces[f"{name}#{index}"] = PLACEHOLDER.sub(_masked, fence)
            continue
        if CONTAINER_FILE.match(path.name) and path.name != "Dockerfile":
            raise AssertionError(f"{name}: a container file; extend this extraction")
        if path.name == "Dockerfile":
            text = path.read_text(encoding="utf-8-sig")
            for index, run in enumerate(_dockerfile_runs(text)):
                surfaces[f"{name}#{index}"] = run
            continue
        with path.open("rb") as handle:
            head = handle.read(256).removeprefix(BOM)
        shebang = SHEBANG.match(head)
        if shebang is None:
            continue
        interpreter = shebang.group(1)
        if interpreter in SHELLS:
            # A shell script that is not UTF-8 fails here, loudly.
            surfaces[name] = path.read_text(encoding="utf-8-sig")
        elif interpreter in OTHER_SHELLS:
            # Another shell's grammar is not bash's (Claude on #394).
            raise AssertionError(
                f"{name}: a `{interpreter.decode()}` script; extend this extraction"
            )
    return surfaces


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
                name.startswith(INSTRUCTION_FILES) and "_exact-" in text
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
            (root / "Dockerfile").write_text("FROM a\nRUN git fetch\n", "utf-8")
            (root / "deep" / "er").mkdir(parents=True)
            (root / "deep" / "er" / "tool").write_bytes(BOM + b"#!/bin/sh\ngit gc\n")
            (root / "deep" / "data.bin").write_bytes(b"\xff\xfe")
            (root / ".cache").mkdir()
            (root / ".cache" / "tool").write_text("#!/bin/sh\nskipped\n", "utf-8")
            self.assertEqual(
                {
                    ".github/workflows/w.yml#0": "git status",
                    "AGENTS.md#0": "git log _ref_\n",
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
                with (
                    self.subTest(name=name),
                    self.assertRaisesRegex(AssertionError, "a container file"),
                ):
                    _shell_surfaces(root)


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
                "jobs:\n  j:\n    steps:\n      - run: git log\n", "utf-8"
            )
            (root / "ci" / "policy.yml").write_text("checks:\n  - name: x\n", "utf-8")
            self.assertEqual(
                {
                    ".gitlab-ci.yml#0": "git fetch",
                    ".gitlab-ci.yml#1": "git status\necho ok",
                    ".gitlab-ci.yml#2": "git gc",
                    "ci/github-actions.yml#0": "git log",
                },
                _shell_surfaces(root),
            )
            (root / "ci" / "other.yml").write_text(
                "pipeline:\n  steps:\n    - script: git status\n", "utf-8"
            )
            with self.assertRaisesRegex(
                AssertionError, "other.yml: shell in an unknown"
            ):
                _shell_surfaces(root)

    def test_a_shebang_is_classified_by_its_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = {
                "a": b"#!/bin/ash\ngit a\n",
                "b": b"#!/usr/local/bin/bash\ngit b\n",
                "c": b"#!/usr/bin/env -S bash -e\ngit c\n",
                "d": b"#! /bin/dash\ngit d\n",
                "p": b"#!/usr/bin/env python3\nprint()\n",
            }
            for name, content in scripts.items():
                (root / name).write_bytes(content)
            self.assertEqual({"a", "b", "c", "d"}, set(_shell_surfaces(root)))
            (root / "z").write_bytes(b"#!/usr/bin/env zsh\ngit z\n")
            with self.assertRaisesRegex(AssertionError, "z: a `zsh` script"):
                _shell_surfaces(root)


class RetainedEvidenceTests(unittest.TestCase):
    """The assessment's retained evidence is the evidence it names (Codex and
    CodeRabbit on #394)."""

    ASSESSMENT = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.md"
    EVIDENCE = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"

    def test_each_retained_script_hashes_to_its_declared_digest(self) -> None:
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        sections = re.findall(
            r"^### `([^`]+)`\n(.*?)^````(\w*)\n(.*?)^````\n", text, re.M | re.S
        )
        self.assertGreaterEqual(len(sections), 11)
        for name, prose, fence, code in sections:
            with self.subTest(script=name):
                declared = re.search(r"SHA-256\s+`([0-9a-f]{16})…`", prose)
                self.assertIsNotNone(declared)
                # A `text` fence keeps formatters away from the retained bytes.
                self.assertEqual("text", fence)
                digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
                self.assertTrue(digest.startswith(declared.group(1)))  # type: ignore[union-attr]

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
