"""Each shell surface runs under the interpreter that really runs it: Dockerfile
instructions, shebangs, launchers and images (Decision 0108). The shared interim
helpers are in `shell_parser_dependency_support`."""

from __future__ import annotations

import ast
import json
import re
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.shell_parser_dependency_support import (
    CONTAINER_FILE,
    FROM_LINE,
    PROBE,
    PROBE_INPUT_LIMIT,
    ROOT,
    _ci_shell,
    _declared,
    _dockerfile_runs,
    _exec_form_shell,
    _files,
    _linux_image,
    _overrides_build_arg,
    _probe,
    _shell_surfaces,
)


class InterpreterTests(unittest.TestCase):
    """Shell surfaces are found by what they are, not where they sit (CodeAnt and
    Claude on #394)."""

    def test_an_exec_form_shell_s_options_are_read_as_the_shell_reads_them(
        self,
    ) -> None:
        """With `-c` among the options, the command is the first word after them;
        `-o` and `-O` take a word, and so do `--rcfile` and `--init-file`. After a
        script's path, `-c` is the script's (CodeAnt on #396). A script operand is
        a file in the image, which this reader cannot map back to the repository, so
        it fails closed (Codex on #396); `-` reads standard input instead."""
        for argv, expected in (
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
            (
                ["bash", "script.sh", "-c", "git a"],
                "an exec-form shell running a script",
            ),
            (["sh", "scripts/check.sh"], "an exec-form shell running a script"),
            (["bash", "-o"], "a shell option without its word"),
            (["bash", "+c", "x"], "an unknown shell option `\\+c`"),
        ):
            with (
                self.subTest(argv=argv),
                self.assertRaisesRegex(AssertionError, reason),
            ):
                _exec_form_shell(argv)

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

    def test_an_onbuild_run_is_read(self) -> None:
        """`ONBUILD RUN` runs its command in a later build, so it is read as a `RUN`
        (CodeAnt on #396)."""
        self.assertEqual(
            ["git status", "git log"],
            _dockerfile_runs(
                'FROM alpine\nONBUILD RUN git status\nonbuild run ["sh", "-c", "git log"]\n'
            ),
        )

    def test_a_gitlab_job_s_shell_is_its_image_s(self) -> None:
        """GitLab's runner, not the file, picks the shell, except in a container: a
        Linux image runs `sh` or `bash` (GitLab Runner's Docker executor). A job's
        image is its own, else its `extends` base's, else `default`'s, else the
        global one. A job without one, or with a Windows base image, fails closed
        (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            for document in (
                "job:\n  image: alpine\n  script: [git a]\n",
                ".base:\n  image: alpine\njob:\n  extends: .base\n  script: [git a]\n",
                # A base reached twice, through both bases, before the image.
                ".root:\n  stage: x\n.img:\n  image: alpine\n"
                ".a:\n  extends: [.img, .root]\n.b:\n  extends: .root\n"
                "job:\n  extends: [.a, .b]\n  script: [git a]\n",
                "default:\n  image: {name: alpine}\njob:\n  script: [git a]\n",
                "image: alpine\njob:\n  script: [git a]\n",
                "job:\n  image: alpine\n  script: [git a]\nbridge:\n  trigger: other\n",
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(["git a"], _ci_shell(path, under_github=False))
            for document, reason in (
                (
                    "job:\n  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                (
                    "job:\n  image: mcr.microsoft.com/windows/servercore:ltsc2022\n"
                    "  script: [git a]\n",
                    "`job`: a Windows image",
                ),
                (
                    "job:\n  extends: .missing\n  script: [git a]\n",
                    "`job`: an `extends` of `.missing`",
                ),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=False)

    def test_gitlab_run_steps_inheritance_and_variable_images(self) -> None:
        """A job's `run` steps hold scripts; a step component fails closed (Codex
        and cubic on #396). `inherit: {default: false}`, or a list without `image`,
        drops `default`'s image (Codex on #396). An image a variable names is known
        only for a variable this repository declares (cubic on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".gitlab-ci.yml"
            for document, expected in (
                (
                    "job:\n  image: alpine\n  run:\n    - name: a\n      script: git a\n",
                    ["git a"],
                ),
                (
                    "default:\n  image: alpine\njob:\n  inherit: {default: [image]}\n"
                    "  script: [git a]\n",
                    ["git a"],
                ),
                (
                    'job:\n  image: {name: "${KNOWLEDGE_KIT_IMAGE}"}\n  script: [git a]\n',
                    ["git a"],
                ),
            ):
                path.write_text(document, "utf-8")
                with self.subTest(document=document):
                    self.assertEqual(expected, _ci_shell(path, under_github=False))
            for document, reason in (
                (
                    "job:\n  image: alpine\n  run:\n    - name: a\n      step: some/step@v1\n",
                    "`job`: a GitLab `run` step that is not a script",
                ),
                (
                    "default:\n  image: alpine\njob:\n  inherit: {default: false}\n"
                    "  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                (
                    "default:\n  image: alpine\njob:\n  inherit: {default: [cache]}\n"
                    "  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                (
                    "job:\n  image: $CI_IMAGE\n  script: [git a]\n",
                    "`job`: an image `CI_IMAGE` decides",
                ),
                # An `inherit` from a base is the job's too (Codex on #396).
                (
                    ".base:\n  inherit: {default: false}\ndefault:\n  image: alpine\n"
                    "job:\n  extends: .base\n  script: [git a]\n",
                    "`job`: a GitLab job whose shell its runner decides",
                ),
                # A declared variable counts only as the whole reference (CodeAnt on
                # #396).
                (
                    'job:\n  image: "registry.example/${KNOWLEDGE_KIT_IMAGE}"\n'
                    "  script: [git a]\n",
                    "`job`: an image a declared variable only partly names",
                ),
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, reason),
                ):
                    _ci_shell(path, under_github=False)

    def test_only_an_image_known_to_be_linux_runs_sh(self) -> None:
        """A name cannot show an image's OS, so only images known to be Linux
        count: an official image published for Linux alone, or `python` with a
        Linux variant's tag. A custom name or a bare digest may be Windows, and
        leaves the shell unknown (cubic on #396)."""
        for image in (
            "alpine",
            "alpine:3.20",
            "docker.io/library/debian:trixie",
            "python:3.12-slim@sha256:" + "0" * 64,
            "python:3.12-alpine3.20",
        ):
            with self.subTest(image=image):
                self.assertTrue(_linux_image(image))
        for image in (
            "registry.example/custom-base",
            "python@sha256:" + "0" * 64,
            "python:3.12",
            "python:3.12-windowsservercore",
            "mcr.microsoft.com/windows/servercore:ltsc2022",
        ):
            with self.subTest(image=image):
                self.assertFalse(_linux_image(image))
        for text in (
            "FROM registry.example/custom-base\nRUN Write-Output hi\n",
            # A platform other than Linux leaves the shell unknown (Codex on #396).
            "FROM --platform=windows/amd64 alpine\nRUN Write-Output hi\n",
            "FROM --platform=$BUILDPLATFORM python:3.12-slim\nRUN true\n",
        ):
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(AssertionError, "a RUN whose shell is unknown"),
            ):
                _dockerfile_runs(text)
        self.assertEqual(
            ["true"], _dockerfile_runs("FROM --platform=linux/arm64 alpine\nRUN true\n")
        )

    def test_a_shell_instruction_hands_run_to_c_and_defers_under_onbuild(
        self,
    ) -> None:
        """Docker appends a shell-form `RUN` to the whole `SHELL` vector, so the
        vector must end its options with `-c` and hold no command of its own (Codex
        on #396). `ONBUILD SHELL` defers to a later build: it changes no current
        stage, only the `ONBUILD RUN`s after it (Codex on #396)."""
        windows = "FROM mcr.microsoft.com/windows/servercore:ltsc2022\n"
        for text in (
            'FROM alpine\nSHELL ["bash", "-c", "git status"]\nRUN true\n',
            'FROM alpine\nSHELL ["bash"]\nRUN true\n',
            windows + 'ONBUILD SHELL ["bash", "-c"]\nRUN Write-Output hi\n',
        ):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                _dockerfile_runs(text)
        self.assertEqual(
            ["git x"],
            _dockerfile_runs(
                windows + 'ONBUILD SHELL ["bash", "-c"]\nONBUILD RUN git x\n'
            ),
        )
        self.assertEqual(
            ["git y"],
            _dockerfile_runs(
                'FROM alpine\nSHELL ["/bin/bash", "-eo", "pipefail", "-c"]\nRUN git y\n'
            ),
        )

    def test_an_exec_form_env_and_the_runtime_instructions_are_read(self) -> None:
        """An exec-form `env` launches its command, so a shell after it is read;
        `-S` there fails closed (Codex on #396). A shell-form `CMD`, `ENTRYPOINT`
        or `HEALTHCHECK CMD` runs through the stage's shell, as `RUN` does (Codex on
        #396)."""
        self.assertEqual(["git a"], _exec_form_shell(["env", "sh", "-c", "git a"]))
        self.assertEqual(
            ["git b"],
            _exec_form_shell(["/usr/bin/env", "-i", "FOO=1", "bash", "-c", "git b"]),
        )
        with self.assertRaisesRegex(AssertionError, "an exec-form `env -S`"):
            _exec_form_shell(["env", "-S", "sh -c", "git x"])
        # A launcher chain beyond the bound fails closed, as a shebang's does
        # (Codex on #396).
        with self.assertRaisesRegex(AssertionError, "a launcher chain beyond"):
            _exec_form_shell(["env", "env", "env", "env", "sh", "-c", "git x"])
        # The multi-call half of the bound too (Claude on #396).
        with self.assertRaisesRegex(AssertionError, "a launcher chain beyond"):
            _exec_form_shell([*["busybox"] * 4, "sh", "-c", "git x"])
        # The health check runs on its own; the process is read when the stage
        # ends, and Docker ignores `CMD` under a shell-form `ENTRYPOINT` (cubic on
        # #396).
        self.assertEqual(
            ["git e", "git d"],
            _dockerfile_runs(
                "FROM alpine\nCMD git c\nENTRYPOINT git d\n"
                "HEALTHCHECK --interval=5m CMD git e\n"
            ),
        )
        self.assertEqual(
            [],
            _dockerfile_runs('FROM alpine\nENTRYPOINT ["knowledge"]\nCMD ["--help"]\n'),
        )

    def test_no_build_overrides_a_from_argument(self) -> None:
        """A `FROM` that names a global `ARG` is read with its default, so no
        repository build may override that `ARG`: a caller's own `--build-arg` is
        outside the repository, the assumption this reader declares (Codex on
        #396)."""
        files = _files(ROOT)
        names: set[str] = set()
        for path in files:
            if CONTAINER_FILE.match(path.name):
                for line in path.read_text(encoding="utf-8").splitlines():
                    if (stage := FROM_LINE.fullmatch(line)) is not None:
                        names |= set(re.findall(r"\$\{?(\w+)", stage["image"]))
        self.assertEqual({"PYTHON_BASE_IMAGE"}, names)
        for path in files:
            # This module's own cases below are examples, not a build.
            if path.resolve() == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for name in names:
                with self.subTest(path=str(path.relative_to(ROOT)), name=name):
                    self.assertFalse(_overrides_build_arg(text, name))
        # Every way a build names the argument, its value given or taken from the
        # environment (cubic on #396).
        base = "PYTHON_BASE_IMAGE"
        for text in (
            f'--build-arg "{base}=x"',
            f"--build-arg {base}=x",
            f"--build-arg={base}=x",
            f"--build-arg {base}",
            f"--build-arg={base}",
            f"--build-arg \\\n    {base}",
        ):
            with self.subTest(text=text):
                self.assertTrue(_overrides_build_arg(text, base))
        self.assertFalse(_overrides_build_arg(f"--build-arg {base}_X=y", base))

    def test_an_exec_form_of_another_shell_fails_closed(self) -> None:
        """An exec form of a shell this reader does not read fails closed, as a
        shebang of one does: a listed shell, or a shell-like name that is no known
        shell, with or without `.exe` (Codex on #396)."""
        # Windows names are case-insensitive and may be paths with either separator
        # (cubic and Codex on #396).
        for program in (
            "pwsh",
            "pwsh.exe",
            "powershell.exe",
            "cmd.exe",
            "zsh5",
            "CMD.EXE",
            "PowerShell.exe",
            "PWSH.EXE",
            "C:\\Windows\\System32\\cmd.exe",
            "C:/Program Files/PowerShell/7/pwsh.exe",
        ):
            with (
                self.subTest(program=program),
                self.assertRaisesRegex(AssertionError, "an exec-form `.*` RUN"),
            ):
                _exec_form_shell([program, "-c", "git x"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "p").write_bytes(b"#!/usr/bin/pwsh.exe\ngit p\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "p: an unrecognised shell"):
                _shell_surfaces(declared)

    def test_an_exec_form_names_a_supported_shell_as_windows_does(self) -> None:
        """A supported shell named as Windows names it, by a backslash path, in any
        case, or with `.exe`, is still that shell (Codex on #396)."""
        for argv in (
            ["C:\\Git\\bin\\bash.exe", "-c", "git x"],
            ["BASH.EXE", "-c", "git x"],
            ["C:/Git/bin/sh.exe", "-c", "git x"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(["git x"], _exec_form_shell(argv))

    def test_shell_continues_and_shebangs_name_shells_as_windows_does(self) -> None:
        """A JSON `SHELL` over continuation lines is joined before it is read
        (CodeAnt on #396); a shebang naming a supported shell as Windows names it,
        such as Cygwin's `/bin/bash.exe`, is that shell (Codex on #396)."""
        self.assertEqual(
            ["git x"],
            _dockerfile_runs(
                'FROM alpine\nSHELL ["/bin/bash", \\\n  "-c"]\nRUN git x\n'
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "w").write_bytes(b"#!/bin/bash.exe\ngit w\n")
            self.assertEqual(
                {"w": "#!/bin/bash.exe\ngit w\n"}, _shell_surfaces(_declared(root))
            )

    def test_launchers_are_named_as_windows_names_them(self) -> None:
        """`env`, a multi-call binary and a declared launcher are recognised however
        Windows spells them (Codex on #396)."""
        self.assertEqual(
            ["git x"], _exec_form_shell(["C:\\tools\\env.exe", "bash", "-c", "git x"])
        )
        self.assertEqual(
            ["git y"], _exec_form_shell(["BUSYBOX.EXE", "sh", "-c", "git y"])
        )
        with self.assertRaisesRegex(AssertionError, "a `timeout` launcher"):
            _exec_form_shell(["Timeout.exe", "10", "sh", "-c", "git z"])

    def test_a_launcher_fails_closed(self) -> None:
        """A launcher such as `timeout`, `su` or `tini` runs a command by its own
        grammar, which may hand it to a shell without naming one, as `su -c` does, or
        name a shell this reader does not list, such as `bash5`. So a declared
        launcher fails closed, in an exec form and in a shebang alike (Codex and
        cubic on #396)."""
        for argv in (
            ["timeout", "10", "sh", "-c", "git x"],
            ["nice", "-n", "5", "bash", "-c", "git y"],
            ["sudo", "-u", "app", "/bin/sh", "-c", "git z"],
            ["su", "-c", "git w", "nobody"],
            ["timeout", "10", "bash5", "-c", "git v"],
            ["tini", "--", "knowledge"],
            # `find` runs its `-exec` action, and the rest run commands too (Codex on
            # #396).
            ["find", ".", "-exec", "sh", "-c", "git u", ";"],
            ["ssh", "host", "git t"],
            # A launcher after the bound's last wrapper is still a launcher (Codex on
            # #396).
            ["env", "env", "env", "timeout", "10", "sh", "-c", "git s"],
        ):
            launcher = next((word for word in argv if word != "env"), argv[0])
            with (
                self.subTest(argv=argv),
                self.assertRaisesRegex(AssertionError, f"a `{launcher}` launcher;"),
            ):
                _exec_form_shell(argv)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "t").write_bytes(b"#!/usr/bin/env -S timeout 10 sh\ngit t\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "t: a `timeout` launcher;"):
                _shell_surfaces(declared)

    def test_a_continuation_follows_buildkit_s_rule(self) -> None:
        """BuildKit continues a line whose escape character is followed only by
        spaces or tabs, and skips empty and comment lines inside it; measured with
        a BuildKit build (Codex on #396)."""
        self.assertEqual(
            ["git a     && git b", "git c     && git d", "git e     && git f"],
            _dockerfile_runs(
                "FROM alpine\nRUN git a \\   \n    && git b\n"
                "RUN git c \\\n\n    && git d\n"
                "RUN git e \\\n# a comment\n    && git f\n"
            ),
        )
        # Only a lone escape character continues: two or three end the line, as a
        # BuildKit build measured (Claude on #396).
        for escapes in (2, 3):
            with self.subTest(escapes=escapes):
                self.assertEqual(
                    ["git a" + "\\" * escapes],
                    _dockerfile_runs(
                        "FROM alpine\nRUN git a" + "\\" * escapes + "\n    && git b\n"
                    ),
                )

    def test_an_exec_form_entrypoint_takes_its_cmd(self) -> None:
        """An exec-form `ENTRYPOINT` takes an exec-form `CMD` as its arguments, so
        the stage's process is read whole, as Docker runs it (Codex on #396). A
        stage inherits a named stage's; its own `ENTRYPOINT` resets an inherited
        `CMD`; a shell-form `ENTRYPOINT` ignores `CMD`; only the last of each runs.
        An exec-form `CMD` under an unknown base's `ENTRYPOINT` fails closed."""
        for dockerfile, expected in (
            ('FROM alpine\nENTRYPOINT ["sh"]\nCMD ["-c", "git a"]\n', ["git a"]),
            ('FROM alpine\nENTRYPOINT ["sh", "-c"]\nCMD ["git b"]\n', ["git b"]),
            (
                'FROM alpine AS base\nENTRYPOINT ["bash"]\nFROM base\nCMD ["-c", "git c"]\n',
                ["git c"],
            ),
            (
                'FROM alpine AS base\nENTRYPOINT ["sh", "-c"]\nCMD ["git d"]\n'
                'FROM base\nENTRYPOINT ["knowledge"]\n',
                ["git d"],
            ),
            # Docker ignores `CMD` under a shell-form `ENTRYPOINT`, though it
            # would run on its own.
            ('FROM alpine\nENTRYPOINT git e\nCMD ["sh", "-c", "git z"]\n', ["git e"]),
            (
                'FROM alpine\nCMD ["sh", "-c", "git old"]\nCMD ["sh", "-c", "git f"]\n',
                ["git f"],
            ),
            # Without the reset, the child would run `sh -c "git y"`.
            (
                'FROM alpine AS base\nENTRYPOINT ["knowledge"]\nCMD ["-c", "git y"]\n'
                'FROM base\nENTRYPOINT ["sh"]\n',
                [],
            ),
            ('FROM scratch\nCMD ["/app"]\n', []),
            # A shell-form `CMD` is part of the process too: one Docker ignores, or a
            # later one replaces, is not read (cubic on #396).
            ("FROM alpine\nCMD if then\nENTRYPOINT git i\n", ["git i"]),
            ("FROM alpine\nCMD git old\nCMD git j\n", ["git j"]),
            # `ONBUILD` triggers run in order in a later build, as if after its
            # `FROM`, so they are combined too (Codex on #396).
            (
                'FROM alpine\nONBUILD ENTRYPOINT ["sh"]\nONBUILD CMD ["-c", "git h"]\n',
                ["git h"],
            ),
            (
                'FROM alpine\nENTRYPOINT ["bash"]\nONBUILD CMD ["-c", "git k"]\n',
                ["git k"],
            ),
            # A stage built on this one runs its triggers right after its `FROM`
            # (Codex on #396), and a `-c` whose command a later stage supplies is
            # not yet a defect (cubic on #396).
            (
                'FROM alpine AS base\nONBUILD ENTRYPOINT ["sh", "-c"]\n'
                'FROM base\nCMD ["git x"]\n',
                ["git x"],
            ),
            (
                'FROM alpine AS base\nONBUILD ENTRYPOINT ["sh"]\n'
                'FROM base\nCMD ["-c", "git z"]\n',
                ["git z"],
            ),
            (
                'FROM alpine AS base\nENTRYPOINT ["sh", "-c"]\nFROM base\nCMD ["git y"]\n',
                ["git y"],
            ),
            ('FROM alpine\nENTRYPOINT ["knowledge"]\nCMD ["--help"]\n', []),
        ):
            with self.subTest(dockerfile=dockerfile):
                self.assertEqual(expected, _dockerfile_runs(dockerfile))
        with self.assertRaisesRegex(AssertionError, "an unknown base's `ENTRYPOINT`"):
            _dockerfile_runs('FROM example.com/tool\nCMD ["sh", "-c", "git g"]\n')

    def test_env_s_is_read_by_position_and_flags_belong_to_run(self) -> None:
        """An `S` inside `-u`'s attached argument is not `-S` (cubic on #396).
        Only `RUN` takes `--mount`-style flags; a runtime instruction keeps its
        command whole (cubic on #396). `HEALTHCHECK`'s own options precede its
        `CMD`, and `HEALTHCHECK NONE` runs nothing."""
        self.assertEqual(
            ["git x"], _exec_form_shell(["env", "-uSHELL", "bash", "-c", "git x"])
        )
        with self.assertRaisesRegex(AssertionError, "an exec-form `env -S`"):
            _exec_form_shell(["env", "-iS", "sh -c", "git x"])
        self.assertEqual(
            ["git e", "git f", "--quiet git y"],
            _dockerfile_runs(
                "FROM alpine\nCMD --quiet git y\n"
                "HEALTHCHECK --interval=5m --timeout=3s CMD git e\n"
                'HEALTHCHECK --interval=5m CMD ["sh", "-c", "git f"]\n'
                "HEALTHCHECK NONE\n"
            ),
        )

    def test_each_dockerfile_stage_has_its_own_shell(self) -> None:
        """A stage's shell is its base's: `sh` for a Linux image, a named stage's
        for a stage, its `SHELL` once set. A global `ARG`'s default resolves in
        `FROM`. A Windows base, `scratch`, or an unresolved reference leaves the
        shell unknown, so a shell-form `RUN` there fails closed (Codex on #396)."""
        self.assertEqual(
            ["git a", "git b"],
            _dockerfile_runs(
                "ARG BASE=alpine:3\nFROM ${BASE} AS base\nRUN git a\n"
                "FROM base AS next\nRUN git b\n"
            ),
        )
        self.assertEqual(
            ["git c"],
            _dockerfile_runs(
                "FROM mcr.microsoft.com/windows/servercore:ltsc2022\n"
                'SHELL ["bash", "-c"]\nRUN git c\n'
            ),
        )
        for text in (
            "FROM mcr.microsoft.com/windows/servercore:ltsc2022\nRUN dir\n",
            "FROM scratch\nRUN true\n",
            "FROM $UNSET\nRUN true\n",
            "RUN true\n",
        ):
            with (
                self.subTest(text=text),
                self.assertRaisesRegex(AssertionError, "a RUN whose shell is unknown"),
            ):
                _dockerfile_runs(text)

    def test_a_shebang_s_own_command_is_what_runs(self) -> None:
        """A shebang whose shell has `-c` runs that string, not the file's body;
        `-s` reads standard input instead, and fails closed (Codex on #396)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "c").write_bytes(
                b"#!/usr/bin/env -S bash -c 'git status'\necho body\n"
            )
            (root / "e").write_bytes(b"#!/bin/sh -e\ngit log\n")
            self.assertEqual(
                {"c": "git status", "e": "#!/bin/sh -e\ngit log\n"},
                _shell_surfaces(_declared(root)),
            )
            (root / "s").write_bytes(b"#!/bin/sh -s\ngit log\n")
            declared = _declared(root)
            with self.assertRaisesRegex(
                AssertionError, "s: a shebang shell that reads"
            ):
                _shell_surfaces(declared)
        # With `-c`, bash ignores `-s`; dash runs the string, then reads standard
        # input too, so `sh`, `dash` and `ash` still fail closed (cubic on #396).
        cases: dict[bytes, dict[str, str] | str] = {
            b"#!/usr/bin/env -S bash -sc 'git status'\n": {"b": "git status"},
            b"#!/usr/bin/env -S sh -sc 'git status'\n": "b: a shebang shell that reads",
            # `-c -` names no command: such a file runs its own path as the
            # command, and so itself, without end (Claude on #396).
            b"#!/usr/bin/env -S sh -c -\n": "b: a shebang `-c` without its command",
        }
        for head, expected in cases.items():
            with self.subTest(head=head), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "b").write_bytes(head + b"git log\n")
                declared = _declared(root)
                if isinstance(expected, dict):
                    self.assertEqual(expected, _shell_surfaces(declared))
                else:
                    with self.assertRaisesRegex(AssertionError, expected):
                        _shell_surfaces(declared)
        with self.assertRaisesRegex(AssertionError, "a `-c` without its command"):
            _exec_form_shell(["sh", "-c", "-"])

    def test_the_probe_takes_a_bounded_list_of_strings(self) -> None:
        """The probe child refuses input that is not a list of strings (Amazon Q on
        #396), and the parent refuses a corpus beyond its bound before sending it
        (CodeAnt on #396); the answer, which grows with the input, is bounded with
        it."""
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed probe argv tests the bounded JSON protocol
            [sys.executable, str(PROBE)],
            input='{"not": "a list"}',
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("a JSON list of strings", completed.stderr)
        # Text that is not JSON at all is refused the same way, not with a
        # traceback (Amazon Q on #396).
        malformed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed probe argv tests deliberately malformed JSON
            [sys.executable, str(PROBE)],
            input="not json",
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, malformed.returncode)
        self.assertIn("a JSON list of strings", malformed.stderr)
        self.assertNotIn("Traceback", malformed.stderr)
        # JSON nested past the decoder's recursion limit too (cubic on #396).
        nested = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed probe argv tests the nested JSON refusal
            [sys.executable, str(PROBE)],
            input="[" * 100_000,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, nested.returncode)
        self.assertIn("a JSON list of strings", nested.stderr)
        self.assertNotIn("Traceback", nested.stderr)
        # An integer past Python's digit limit raises `ValueError` (CodeAnt on #396).
        digits = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed probe argv tests the oversized integer refusal
            [sys.executable, str(PROBE)],
            input="[" + "1" * 5000 + "]",
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, digits.returncode)
        self.assertIn("a JSON list of strings", digits.stderr)
        self.assertNotIn("Traceback", digits.stderr)
        with (
            self.assertRaisesRegex(AssertionError, "beyond the probe's input bound"),
            patch.object(json, "dumps", side_effect=AssertionError("serialised")),
        ):
            _probe(["x" * (PROBE_INPUT_LIMIT + 1)])
        # The child bounds its own read too, at the same limit, whoever writes to it
        # (Amazon Q on #396); it reads no more than one character past it.
        probe = ast.parse(PROBE.read_text(encoding="utf-8"))
        [limit] = [
            node.value
            for node in probe.body
            if isinstance(node, ast.Assign)
            and [getattr(target, "id", None) for target in node.targets]
            == ["INPUT_LIMIT"]
        ]
        self.assertEqual(PROBE_INPUT_LIMIT, ast.literal_eval(limit))
        oversized = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- fixed probe argv tests the input-size refusal
            [sys.executable, str(PROBE)],
            input=json.dumps(["x" * PROBE_INPUT_LIMIT]),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        self.assertEqual(2, oversized.returncode)
        self.assertIn("beyond the probe's input bound", oversized.stderr)

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
            # One launcher walk serves shebangs and exec forms (Claude on #396).
            with self.assertRaisesRegex(AssertionError, "k: a launcher chain beyond"):
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
            # A shell whose name does not end in `sh` is named, so it fails closed
            # too (CodeAnt on #396).
            for shell in ("powershell", "nu", "elvish", "rc", "es"):
                (root / "o").write_bytes(f"#!/usr/bin/{shell}\ngit o\n".encode())
                declared = _declared(root)
                with (
                    self.subTest(interpreter=shell),
                    self.assertRaisesRegex(AssertionError, f"o: a `{shell}` script"),
                ):
                    _shell_surfaces(declared)
            (root / "o").unlink()
            (root / "z").write_bytes(b"#!/usr/bin/env zsh\ngit z\n")
            declared = _declared(root)
            with self.assertRaisesRegex(AssertionError, "z: a `zsh` script"):
                _shell_surfaces(declared)


if __name__ == "__main__":
    unittest.main()
