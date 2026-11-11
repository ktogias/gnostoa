"""Shell surfaces in CI definitions, checkouts and Markdown are found by what they
are, not where they sit (Decision 0108). The shared interim helpers are in
`shell_parser_dependency_support`."""

from __future__ import annotations

import os
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.shell_parser_dependency_support import (
    ROOT,
    _ci_shell,
    _declared,
    _dockerfile_runs,
    _files,
    _gitlab_lineage,
    _gitlab_scripts,
    _refuse_extends_cycle,
    _runner_shell,
    _script_value,
    _shell_surfaces,
)
from tools.repository_scope import SOURCE_MANIFEST, candidate_paths
from tools.trusted_path import trusted_executable


class CiShapeTests(unittest.TestCase):
    """Shell surfaces are found by what they are, not where they sit (CodeAnt and
    Claude on #394)."""

    def test_ci_definitions_are_read_by_their_shape_anywhere(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ci").mkdir()
            (root / ".gitlab-ci.yml").write_text(
                "stages: [test]\ndefault:\n  image: alpine\n  before_script:\n    - git fetch\n"
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
                'stages: [t]\nimage: alpine\njob: {stage: t, script: "git describe"}\n',
                "utf-8",
            )
            self.assertEqual(
                {
                    # `default`'s `before_script` runs with the job's `script`, as one
                    # script; `after_script` apart (Codex on #396).
                    ".gitlab-ci.yml#0": "git fetch\ngit status\necho ok",
                    ".gitlab-ci.yml#1": "git gc",
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
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        env.update(
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_CONFIG_SYSTEM="/dev/null",
            GIT_CONFIG_NOSYSTEM="1",
        )
        with patch.dict(os.environ, env, clear=True):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / ".husky").mkdir()
                (root / ".husky" / "hook").write_text("#!/bin/sh\ngit a\n", "utf-8")
                (root / "scratch").write_text("#!/bin/sh\ngit b\n", "utf-8")
                git = [
                    trusted_executable("git"),
                    "-c",
                    "init.defaultBranch=main",
                    "-C",
                    str(root),
                ]
                for argv in (["init", "-q"], ["add", ".husky/hook"]):
                    subprocess.run([*git, *argv], check=True, timeout=60)  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed Git fixture argv in a temporary repository
                self.assertEqual({".husky/hook"}, set(_shell_surfaces(root)))
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "listed").write_text("#!/bin/sh\ngit c\n", "utf-8")
                (root / "unlisted").write_text("#!/bin/sh\ngit d\n", "utf-8")
                (root / ".gnostoa-source-files").write_bytes(b"listed\0")
                self.assertEqual({"listed"}, set(_shell_surfaces(root)))

    def test_canonical_symlinks_are_refused_without_reading_targets(self) -> None:
        """Both membership owners retain listed links; an unlisted link is not
        source. The smoke refuses listed links rather than following them."""
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        env.update(
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_CONFIG_SYSTEM="/dev/null",
            GIT_CONFIG_NOSYSTEM="1",
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, env, clear=True),
        ):
            base = Path(directory)
            outside = base / "outside"
            outside.write_text("#!/bin/sh\ngit outside\n", "utf-8")
            for membership in ("git", "manifest"):
                root = base / membership
                root.mkdir()
                regular = root / "regular"
                regular.write_text("#!/bin/sh\ngit regular\n", "utf-8")
                link = root / "linked"
                link.symlink_to(outside)
                git = [
                    trusted_executable("git"),
                    "-c",
                    "init.defaultBranch=main",
                    "-C",
                    str(root),
                ]
                if membership == "git":
                    for argv in (["init", "-q"], ["add", "regular"]):
                        subprocess.run([*git, *argv], check=True, timeout=60)  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed Git fixture argv in a temporary repository
                else:
                    (root / SOURCE_MANIFEST).write_bytes(b"regular\0")
                self.assertEqual({"regular"}, set(_shell_surfaces(root)))
                if membership == "git":
                    subprocess.run([*git, "add", "linked"], check=True, timeout=60)  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed Git fixture argv in a temporary repository
                else:
                    (root / SOURCE_MANIFEST).write_bytes(b"regular\0linked\0")
                for target in (regular, outside, base / "missing", base):
                    link.unlink()
                    link.symlink_to(target, target_is_directory=target == base)
                    self.assertIn(Path("linked"), candidate_paths(root))
                    with (
                        self.subTest(membership=membership, target=target.name),
                        patch.object(
                            Path,
                            "open",
                            side_effect=AssertionError("target bytes read"),
                        ),
                        self.assertRaisesRegex(
                            AssertionError, "linked: a candidate symlink"
                        ),
                    ):
                        _shell_surfaces(root)

    def test_canonical_paths_with_symlinked_ancestors_are_refused(self) -> None:
        """A listed child cannot make a symlinked parent canonical source, under
        either membership owner; refusal precedes all target-byte reads."""
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        env.update(
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_CONFIG_SYSTEM="/dev/null",
            GIT_CONFIG_NOSYSTEM="1",
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, env, clear=True),
        ):
            base = Path(directory)
            outside = base / "outside"
            outside.mkdir()
            (outside / "script").write_text("#!/bin/sh\ngit outside\n", "utf-8")
            for membership in ("git", "manifest"):
                for relative in (Path("linked/script"), Path("nested/linked/script")):
                    root = base / f"{membership}-{len(relative.parts)}"
                    root.mkdir()
                    regular = root / "regular"
                    regular.write_text("#!/bin/sh\ngit regular\n", "utf-8")
                    internal = root / "target"
                    internal.mkdir()
                    (internal / "script").write_text(
                        "#!/bin/sh\ngit internal\n", "utf-8"
                    )
                    link = (root / relative).parent
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(outside, target_is_directory=True)
                    git = [
                        trusted_executable("git"),
                        "-c",
                        "init.defaultBranch=main",
                        "-C",
                        str(root),
                    ]
                    if membership == "git":
                        for argv in (["init", "-q"], ["add", "regular"]):
                            subprocess.run([*git, *argv], check=True, timeout=60)  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed Git fixture argv in a temporary repository
                    else:
                        (root / SOURCE_MANIFEST).write_bytes(b"regular\0")
                    self.assertEqual({"regular"}, set(_shell_surfaces(root)))
                    link.unlink()
                    link.mkdir()
                    child = root / relative
                    child.write_text("#!/bin/sh\ngit tracked\n", "utf-8")
                    if membership == "git":
                        subprocess.run(  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed Git fixture argv in a temporary repository
                            [*git, "add", relative.as_posix()], check=True, timeout=60
                        )
                    else:
                        (root / SOURCE_MANIFEST).write_bytes(
                            b"regular\0" + relative.as_posix().encode() + b"\0"
                        )
                    child.unlink()
                    link.rmdir()
                    for target in (internal, outside, base / "missing", regular):
                        link.symlink_to(
                            target, target_is_directory=target in (internal, outside)
                        )
                        self.assertIn(relative, candidate_paths(root))
                        with self.subTest(
                            membership=membership, relative=relative, target=target.name
                        ):
                            with self.assertRaisesRegex(
                                AssertionError,
                                f"{relative.as_posix()}: a candidate symlink",
                            ):
                                _files(root)
                            with (
                                patch.object(
                                    Path,
                                    "open",
                                    side_effect=AssertionError("target bytes read"),
                                ),
                                self.assertRaisesRegex(
                                    AssertionError,
                                    f"{relative.as_posix()}: a candidate symlink",
                                ),
                            ):
                                _shell_surfaces(root)
                        link.unlink()

    def test_checkout_fixture_does_not_write_caller_selected_git_state(self) -> None:
        """The checkout fixture cannot create Git state outside its own directory."""
        for variable in ("GIT_DIR", "GIT_INDEX_FILE"):
            with (
                self.subTest(variable=variable),
                tempfile.TemporaryDirectory() as directory,
            ):
                foreign = Path(directory) / "foreign"
                environment = {
                    "PATH": "/usr/bin:/bin",
                    "HOME": directory,
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_CONFIG_SYSTEM": "/dev/null",
                    "GIT_CONFIG_NOSYSTEM": "1",
                    variable: str(foreign),
                }
                result = unittest.TestResult()
                case = type(self)("test_a_checkout_s_tracked_files_are_the_universe")
                with patch.dict("os.environ", environment, clear=True):
                    case.run(result)
                self.assertFalse(
                    foreign.exists(), "fixture wrote caller-selected Git state"
                )
                self.assertTrue(result.wasSuccessful(), result.errors + result.failures)

    def test_nested_gitlab_script_lists_are_flattened_and_others_fail(self) -> None:
        """GitLab flattens nested `script` arrays (anchors and aliases build them)
        at any depth; a value that is not a string fails closed rather than being
        stringified (CodeAnt on #396). A `!reference` tag fails closed at the YAML
        load: none is tracked (cubic on #396)."""
        nested: dict[str, object] = {
            "image": "alpine",
            "job": {"script": ["git a", ["git b", ["git c"]]]},
        }
        self.assertEqual(["git a\ngit b\ngit c"], _gitlab_scripts(nested, "x"))
        with self.assertRaisesRegex(AssertionError, "a `int` script line"):
            _gitlab_scripts({"image": "alpine", "job": {"script": ["git a", 7]}}, "x")
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
                "image: alpine\nbefore_script: [git a]\nafter_script: git z\n"
                "job:\n  script: [git b]\n",
                "utf-8",
            )
            (root / "ci" / "quoted.yml").write_text(
                '{"stages": ["t"], "image": "alpine", "job": {"stage": "t", "script": "git c"}}\n',
                "utf-8",
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
                    # The global `before_script` runs with the job's `script`, as
                    # one script; the global `after_script` apart (Codex on #396).
                    ".gitlab-ci.yml#0": "git a\ngit b",
                    ".gitlab-ci.yml#1": "git z",
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
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- literal interpreter program and controlled hostile fixture under a deadline
            [
                sys.executable,
                "-c",
                "import sys; from tests.shell_parser_dependency_support import "
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
                self.assertEqual([line[4:]], _dockerfile_runs(f"FROM alpine\n{line}\n"))
        for line in ("RUN cat <<EOF\n", "RUN cat << EOF\n", "RUN cat 3<<-EOF\n"):
            with (
                self.subTest(line=line),
                self.assertRaisesRegex(AssertionError, "here-document"),
            ):
                _dockerfile_runs("FROM alpine\n" + line)
        with self.assertRaisesRegex(AssertionError, "an unreadable RUN"):
            _dockerfile_runs('FROM alpine\nRUN echo "unclosed\n')

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
                "image: alpine\njob:\n  ? script\n  : git status\n",
                "image: alpine\njob:\n  ? script  # the job's commands\n  : git status\n",
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

    def test_a_gitlab_hook_s_commands_are_read(self) -> None:
        """`hooks:pre_get_sources_script` runs on the runner before the clone, in
        a job or in `default`; another hook fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                "default:\n  image: alpine\n  hooks:\n    pre_get_sources_script: [git a]\n"
                "job:\n  hooks:\n    pre_get_sources_script: git b\n  script: [git c]\n",
                "utf-8",
            )
            self.assertEqual(
                ["git a", "git b", "git c"], _ci_shell(path, under_github=False)
            )
            path.write_text(
                "job:\n  image: alpine\n  hooks:\n    other: git x\n  script: [git c]\n",
                "utf-8",
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

    def test_a_hidden_job_runs_in_the_jobs_that_extend_it(self) -> None:
        """A hidden job's scripts run in each job that extends it, whose image is
        checked; one that no job extends is checked by its own image (Claude on
        #396). A malformed `extends` entry fails closed."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                ".lint:\n  script: [git a]\njob:\n  extends: .lint\n  image: alpine\n",
                "utf-8",
            )
            self.assertEqual(["git a"], _ci_shell(path, under_github=False))
            for document, reason in (
                (
                    ".t:\n  image: mcr.microsoft.com/windows/nanoserver:ltsc2022\n"
                    "  script: [git a]\n",
                    "`.t`: a Windows image",
                ),
                (
                    ".t:\n  script: [git a]\n",
                    "`.t`: a GitLab job whose shell its runner decides",
                ),
                (
                    "job:\n  image: alpine\n  extends: [[.x]]\n  script: [git a]\n",
                    "`job`: an `extends` of",
                ),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=False)

    def test_gitlab_global_keywords_are_not_jobs(self) -> None:
        """A global keyword, such as `variables`, holds data, not a job, even when
        one of its keys is named `script`; a job with hooks alone is GitLab's too
        (Codex and Claude on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            path.write_text(
                "variables:\n  script: 'not shell ('\nworkflow:\n  rules: []\n"
                "job:\n  image: alpine\n  script: [git a]\n",
                "utf-8",
            )
            self.assertEqual(["git a"], _ci_shell(path, under_github=False))
            path.write_text(
                "fetch:\n  image: alpine\n  hooks:\n"
                "    pre_get_sources_script: [git submodule sync]\n",
                "utf-8",
            )
            self.assertEqual(
                ["git submodule sync"], _ci_shell(path, under_github=False)
            )

    def test_a_fence_in_another_shell_fails_closed(self) -> None:
        """A fence tagged with a shell this parser does not read, such as `zsh`,
        fails closed instead of being skipped (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for tag in ("zsh", "ksh", "pwsh", "powershell"):
                (root / "AGENTS.md").write_text(f"```{tag}\ngit a\n```\n", "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(tag=tag),
                    self.assertRaisesRegex(AssertionError, f"a `{tag}` fence"),
                ):
                    _shell_surfaces(declared)

    def test_gitlab_rejects_what_gitlab_rejects(self) -> None:
        """A script field that is neither text nor a list fails closed, as GitLab
        refuses it (CodeAnt on #396); an absent one is nothing. An `extends` cycle
        fails closed, as GitLab refuses it, while a base two paths reach is read
        once (CodeAnt on #396)."""
        self.assertEqual([], _script_value(None))
        for value in ({"a": 1}, 3, True):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(
                    AssertionError, "a GitLab script of an unread shape"
                ),
            ):
                _script_value(value)
        cycle: dict[str, object] = {
            "a": {"extends": "b", "script": "git a"},
            "b": {"extends": "c"},
            "c": {"extends": "a"},
        }
        with self.assertRaisesRegex(AssertionError, "an `extends` cycle"):
            _gitlab_lineage(cycle, cycle["a"], "a", ".gitlab-ci.yml")  # type: ignore[arg-type]  # -- deliberately object-typed YAML cycle fixture for lineage validation
        diamond: dict[str, object] = {
            "a": {"extends": ["b", "c"], "script": "git a"},
            "b": {"extends": "d"},
            "c": {"extends": "d"},
            "d": {"before_script": "git d"},
        }
        lineage = _gitlab_lineage(diamond, diamond["a"], "a", ".gitlab-ci.yml")  # type: ignore[arg-type]  # -- deliberately object-typed YAML diamond fixture for precedence validation
        self.assertEqual(["a", "c", "d", "b"], [key for key, _ in lineage])

    def test_a_job_name_cannot_select_the_legacy_reader(self) -> None:
        """An invalid job's name is data, not a shared-reader refusal category."""
        document: dict[str, object] = {
            "image": "alpine",
            "valid": {"script": ["git status"]},
            "bad has a non-string or deeper item": 7,
        }
        with self.assertRaisesRegex(AssertionError, "not a mapping"):
            _gitlab_scripts(document, "job-name-refusal")

    def test_a_gitlab_job_runs_its_before_script_and_script_as_one(self) -> None:
        """GitLab concatenates a job's effective `before_script` and `script` into
        one shell script, `after_script` running apart; each comes from the job, its
        `extends` lineage, then `default`, unless `inherit` drops it (Codex on
        #396). A template no job extends is still read, alone."""
        cases: list[tuple[dict[str, object], list[str]]] = [
            (
                {
                    "image": "alpine",
                    "j": {
                        "before_script": ["if true; then"],
                        "script": ["git x", "fi"],
                    },
                },
                ["if true; then\ngit x\nfi"],
            ),
            (
                {
                    "image": "alpine",
                    ".t": {"before_script": "git a"},
                    "j": {"extends": ".t", "script": "git b", "after_script": "git c"},
                },
                ["git a\ngit b", "git c"],
            ),
            (
                {
                    "image": "alpine",
                    "default": {"before_script": "git d"},
                    "j": {"script": "git e"},
                },
                ["git d\ngit e"],
            ),
            (
                {
                    "image": "alpine",
                    "default": {"before_script": "git d"},
                    "j": {
                        "inherit": {"default": False},
                        "image": "alpine",
                        "script": "git e",
                    },
                },
                ["git e"],
            ),
            (
                {
                    "image": "alpine",
                    ".u": {"script": "git u"},
                    "j": {"script": "git j"},
                },
                ["git j", "git u"],
            ),
        ]
        for document, expected in cases:
            with self.subTest(document=document):
                self.assertEqual(expected, sorted(_gitlab_scripts(document, "x")))

    def test_the_cycle_check_visits_each_job_once(self) -> None:
        """A chain of diamonds has exponentially many paths but few jobs; the cycle
        check visits each job once, so it stays linear (cubic on #396)."""

        class Counted(dict[str, object]):
            lookups = 0

            def get(self, key: str, default: object = None) -> object:
                Counted.lookups += 1
                return super().get(key, default)

        levels = 12
        document = Counted()
        for level in range(levels):
            document[f"j{level}"] = {"extends": [f"a{level}", f"b{level}"]}
            document[f"a{level}"] = {"extends": f"j{level + 1}"}
            document[f"b{level}"] = {"extends": f"j{level + 1}"}
        document[f"j{levels}"] = {"script": "git x"}
        _refuse_extends_cycle(document, "j0", ".gitlab-ci.yml")
        self.assertLessEqual(Counted.lookups, 2 * len(document))

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
                ("job:\n  image: alpine\n  script: &s\n    - git a\n    - *s\n", False),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "a recursive YAML alias"),
                ):
                    _ci_shell(path, under_github=under_github)
            path.write_text(
                "job:\n  image: alpine\n  before_script: &s [git a]\n"
                "  script: [*s, git b]\n",
                "utf-8",
            )
            # One script, `before_script` and `script` concatenated (Codex on #396).
            self.assertEqual(
                ["git a\ngit a\ngit b"], _ci_shell(path, under_github=False)
            )

    def test_a_gitlab_job_named_like_github_s_keys_stays_gitlab(self) -> None:
        """A workflow has `on` and `jobs`, an action `runs.using`; a GitLab job may
        be named `jobs` or `runs` (CodeAnt on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitlab-ci.yml").write_text(
                "image: alpine\njobs:\n  script: git status\nruns:\n  script:\n    - git log\n",
                "utf-8",
            )
            declared = _declared(root)
            self.assertEqual(
                {".gitlab-ci.yml#0": "git status", ".gitlab-ci.yml#1": "git log"},
                _shell_surfaces(declared),
            )


if __name__ == "__main__":
    unittest.main()
