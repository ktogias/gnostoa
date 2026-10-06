"""The one owner of targeted mutants, and its tables (Decision 0104, #373).

About twenty hand-maintained scripts matched literal text, so `ruff --fix` and refactors
broke their anchors silently. These tests define the owner that replaces them.
"""

from __future__ import annotations

import ast
import os
import pathlib
import shutil
import subprocess  # nosec B404 -- test fixtures run only git, resolved once, with fixed arguments
import tempfile
import textwrap
import threading
import time
import unittest
from unittest import mock

import yaml

from tools import mutation
from tools.knowledge_common import KnowledgeFormatError


def _project(base: pathlib.Path) -> pathlib.Path:
    """A tiny project whose test checks `double(2) == 4` and `double(3) == 6`."""
    root = base / "project"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "m.py").write_text(
        "def double(x):\n    return x * 2\n\n\ndef wait():\n    return None\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_m.py").write_text(
        "import unittest\n\nfrom pkg import m\n\n\n"
        "class T(unittest.TestCase):\n"
        "    def test_double(self):\n"
        "        self.assertEqual(4, m.double(2))\n\n"
        "    def test_wait(self):\n"
        "        self.assertIsNone(m.wait())\n",
        encoding="utf-8",
    )
    return root


def _table(
    base: pathlib.Path, mutants: str, tests: str = "[tests.test_m]"
) -> pathlib.Path:
    path = base / "table.yaml"
    path.write_text(
        f"id: fixture\ntests: {tests}\nmutants:\n{mutants}", encoding="utf-8"
    )
    return path


def _alive(pid: int) -> bool:
    """Whether ``pid`` runs: a killed child an init never reaped is a zombie."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        stat = pathlib.Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return True
    return stat.rpartition(")")[2].split()[0] != "Z"


class PythonAnchorTests(unittest.TestCase):
    """A Python anchor is located by AST, so formatting cannot break it."""

    def test_a_statement_anchor_survives_reformatting(self) -> None:
        source = (
            "def f(a, b):\n"
            "    if (\n"
            "        a\n"
            "        and b  # a comment ruff would keep\n"
            "    ):\n"
            "        return 1\n"
            "    return 0\n"
        )
        mutated = mutation.apply(
            source,
            "if a and b:\n    return 1\n",
            "if a or b:\n    return 1\n",
            python=True,
        )
        expected = "def f(a, b):\n    if a or b:\n        return 1\n    return 0\n"
        self.assertEqual(ast.dump(ast.parse(expected)), ast.dump(ast.parse(mutated)))

    def test_a_run_of_statements_is_matched_within_one_block(self) -> None:
        source = "def f():\n    a = 1\n    b = 2\n    c = 3\n    return a + b + c\n"
        mutated = mutation.apply(
            source, "a = 1\nb = 2\n", "a = 0\nb = 0\n", python=True
        )
        self.assertIn("    a = 0\n    b = 0\n    c = 3\n", mutated)

    def test_an_expression_is_matched_where_it_appears(self) -> None:
        source = "value = os.path.abspath(\n    repository\n)\n"
        mutated = mutation.apply(
            source, "os.path.abspath(repository)", "'*'", python=True
        )
        self.assertEqual("value = '*'\n", mutated)

    def test_an_anchor_that_does_not_parse_is_matched_by_tokens(self) -> None:
        source = "run(\n    command,\n    timeout=_LIMIT,\n).stdout\n"
        mutated = mutation.apply(
            source, "timeout=_LIMIT,\n).stdout", "timeout=None,\n).stdout", python=True
        )
        self.assertIn("timeout=None", mutated)


class TextAnchorTests(unittest.TestCase):
    def test_a_yaml_anchor_ignores_whitespace(self) -> None:
        source = "jobs:\n  smoke:\n    needs:   [policy,extended]\n"
        mutated = mutation.apply(
            source, "needs: [policy, extended]", "needs: [policy]", python=False
        )
        self.assertEqual("jobs:\n  smoke:\n    needs: [policy]\n", mutated)

    def test_an_anchor_that_matches_nowhere_or_twice_is_reported(self) -> None:
        with self.assertRaises(mutation.AnchorError) as missing:
            mutation.apply("a = 1\n", "b = 2", "b = 3", python=True)
        self.assertEqual("NOT FOUND", missing.exception.status)
        with self.assertRaises(mutation.AnchorError) as twice:
            mutation.apply("x: 1\ny: 1\nx: 1\n", "x: 1", "x: 2", python=False)
        self.assertEqual("AMBIGUOUS", twice.exception.status)


class TableTests(unittest.TestCase):
    def test_a_table_is_loaded_with_its_tests_and_mutants(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            path = _table(
                pathlib.Path(scratch),
                "  - name: double adds\n    path: pkg/m.py\n"
                "    find: 'x * 2'\n    replace: 'x + 2'\n",
            )
            table = mutation.load_table(path)
            self.assertEqual("fixture", table.id)
            self.assertEqual(("tests.test_m",), table.tests)
            self.assertEqual(["double adds"], [m.name for m in table.mutants])

    def test_a_table_that_is_no_mapping_of_names_is_refused(self) -> None:
        # Mixed key types made `sorted` raise TypeError (CodeAnt on #374).
        for label, text in (
            ("a list", "- id: fixture\n"),
            # Two unknown keys of two types: sorting them is what raised.
            ("a key that is no string", "id: fixture\n1: x\nb: y\n"),
        ):
            with tempfile.TemporaryDirectory() as scratch, self.subTest(label):
                path = pathlib.Path(scratch) / "table.yaml"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(KnowledgeFormatError):
                    mutation.load_table(path)

    def test_a_malformed_table_is_refused(self) -> None:
        one = "  - name: n\n    path: pkg/m.py\n    find: 'a'\n    replace: 'b'\n"
        for label, mutants, tests in (
            ("no tests", one, "[]"),
            ("a repeated name", one + one, "[tests.test_m]"),
            (
                "an absolute path",
                one.replace("pkg/m.py", "/etc/passwd"),
                "[tests.test_m]",
            ),
            (
                "a path that climbs",
                one.replace("pkg/m.py", "../m.py"),
                "[tests.test_m]",
            ),
            # Checked as POSIX, a Windows path would be used natively (CodeAnt on #374).
            (
                "a backslash",
                one.replace("pkg/m.py", "'pkg\\..\\..\\m.py'"),
                "[tests.test_m]",
            ),
            ("a drive", one.replace("pkg/m.py", "'C:/m.py'"), "[tests.test_m]"),
            ("an empty anchor", one.replace("find: 'a'", "find: ''"), "[tests.test_m]"),
            (
                "a non-string replacement",
                one.replace("replace: 'b'", "replace: 7"),
                "[tests.test_m]",
            ),
        ):
            with tempfile.TemporaryDirectory() as scratch, self.subTest(label):
                path = _table(pathlib.Path(scratch), mutants, tests)
                with self.assertRaises(KnowledgeFormatError):
                    mutation.load_table(path)


class LineEndingTests(unittest.TestCase):
    def test_a_crlf_file_keeps_its_line_endings(self) -> None:
        # The copy was rewritten with LF, so a byte-sensitive test killed a mutant it
        # cannot see (CodeAnt on #374).
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / "pkg" / "crlf.txt").write_bytes(b"alpha = 1\r\nbeta = 2\r\n")
            (root / "tests" / "test_crlf.py").write_text(
                "import unittest\n\n\n"
                "class E(unittest.TestCase):\n"
                "    def test_endings(self):\n"
                "        data = open('pkg/crlf.txt', 'rb').read()\n"
                "        self.assertEqual(2, data.count(b'\\r\\n'))\n",
                encoding="utf-8",
            )
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: beta changes\n    path: pkg/crlf.txt\n"
                    "    find: 'beta = 2'\n    replace: 'beta = 3'\n",
                    tests="[tests.test_crlf]",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
        self.assertEqual("SURVIVED", outcome.status, outcome.detail)

    def test_a_replacement_takes_the_matched_line_s_ending(self) -> None:
        # A file with CRLF elsewhere gave an LF region CRLF breaks (Codex on #374).
        source = "a = 1\r\nif x:\n    y = 1\n    z = 2\n"
        mutated = mutation.apply(source, "y = 1\nz = 2", "y = 3\nz = 4", python=True)
        self.assertEqual("a = 1\r\nif x:\n    y = 3\n    z = 4\n", mutated)

    def test_a_cr_only_file_keeps_its_lines_and_indentation(self) -> None:
        # `rfind("\\n")` saw a CR-only file as one line, so a nested replacement lost
        # its indentation and its line breaks (Codex on #374).
        source = "def f():\r    a = 1\r    b = 2\r"
        mutated = mutation.apply(source, "a = 1\nb = 2", "a = 3\nb = 4", python=True)
        self.assertEqual("def f():\r    a = 3\r    b = 4\r", mutated)

    def test_a_form_feed_does_not_move_a_python_anchor(self) -> None:
        # `str.splitlines` breaks at a form feed, which Python does not, so the
        # matched span was computed on the wrong line.
        source = "x = 1\x0c\ny = 2\nz = 3\n"
        mutated = mutation.apply(source, "z = 3", "z = 4", python=True)
        self.assertEqual("x = 1\x0c\ny = 2\nz = 4\n", mutated)


class EncodingTests(unittest.TestCase):
    def test_a_file_that_is_not_utf_8_is_reported_not_raised(self) -> None:
        # A declared Latin-1 file aborted `check` and `run` (CodeAnt on #374).
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / "pkg" / "legacy.py").write_bytes(
                b"# -*- coding: latin-1 -*-\nname = '\xe9t\xe9'\nvalue = 2\n"
            )
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: legacy\n    path: pkg/legacy.py\n"
                    "    find: 'value = 2'\n    replace: 'value = 3'\n",
                )
            )
            try:
                problems = mutation.check(root, table)
                (outcome,) = mutation.run(root, table, jobs=1)
            except UnicodeDecodeError as exc:
                self.fail(f"raised {exc!r}")
            self.assertEqual(
                ["legacy: NOT FOUND"], [p.split(" (")[0] for p in problems]
            )
            self.assertEqual("NOT FOUND", outcome.status)
            self.assertIn("UTF-8", outcome.detail)


class CheckTests(unittest.TestCase):
    def test_check_reports_each_anchor_that_does_not_apply(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: applies\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n"
                    "  - name: gone\n    path: pkg/m.py\n"
                    "    find: 'x * 9'\n    replace: 'x'\n"
                    "  - name: breaks the file\n    path: pkg/m.py\n"
                    "    find: 'return x * 2'\n    replace: 'return ('\n",
                )
            )
            self.assertEqual(
                ["gone: NOT FOUND", "breaks the file: INVALID"],
                [problem.split(" (")[0] for problem in mutation.check(root, table)],
            )


class RunTests(unittest.TestCase):
    def test_a_mutant_the_tests_catch_is_killed_and_one_they_miss_survives(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n"
                    "  - name: double adds two\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x + 2'\n",
                )
            )
            outcomes = mutation.run(root, table, jobs=2)
            self.assertEqual(
                {"double triples": "KILLED", "double adds two": "SURVIVED"},
                {o.name: o.status for o in outcomes},
            )
            # The original tree is never touched.
            self.assertIn("x * 2", (root / "pkg" / "m.py").read_text(encoding="utf-8"))

    def test_a_mutant_that_hangs_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: wait never returns\n    path: pkg/m.py\n"
                    "    find: 'return None'\n    replace: 'while True:\n  pass'\n",
                )
            )
            started = time.monotonic()
            (outcome,) = mutation.run(root, table, jobs=1, timeout=2)
            self.assertLess(time.monotonic() - started, 30)
            self.assertEqual("KILLED", outcome.status)
            self.assertIn("timed out", outcome.detail)

    def test_mutants_run_in_parallel_workers(self) -> None:
        active = 0
        peak = 0
        lock = threading.Lock()

        def one(*args):  # type: ignore[no-untyped-def]
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.3)
            with lock:
                active -= 1
            return mutation.Outcome(args[2].name, "KILLED", "")

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            mutants = "".join(
                f"  - name: m{i}\n    path: pkg/m.py\n    find: 'x * 2'\n    replace: 'x * {i + 3}'\n"
                for i in range(3)
            )
            table = mutation.load_table(_table(base, mutants))
            with (
                mock.patch.object(mutation, "_run_one", one),
                mock.patch.object(mutation, "_baseline", return_value=None),
            ):
                mutation.run(root, table, jobs=3)
        self.assertEqual(3, peak)


class CommandTests(unittest.TestCase):
    def test_the_command_exits_zero_only_when_every_mutant_is_killed(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            killed = _table(
                base,
                "  - name: double triples\n    path: pkg/m.py\n"
                "    find: 'x * 2'\n    replace: 'x * 3'\n",
            )
            self.assertEqual(
                0, mutation.main(["--root", str(root), "--table", str(killed)])
            )
            survived = _table(
                base,
                "  - name: double adds two\n    path: pkg/m.py\n"
                "    find: 'x * 2'\n    replace: 'x + 2'\n",
            )
            self.assertEqual(
                1, mutation.main(["--root", str(root), "--table", str(survived)])
            )

    def test_check_mode_exits_zero_only_when_every_anchor_applies(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            good = _table(
                base,
                "  - name: ok\n    path: pkg/m.py\n    find: 'x * 2'\n    replace: 'x * 3'\n",
            )
            self.assertEqual(
                0, mutation.main(["--root", str(root), "--table", str(good), "--check"])
            )
            stale = _table(
                base,
                "  - name: stale\n    path: pkg/m.py\n    find: 'x * 9'\n    replace: 'x'\n",
            )
            self.assertEqual(
                1,
                mutation.main(["--root", str(root), "--table", str(stale), "--check"]),
            )


class SoundnessTests(unittest.TestCase):
    """A kill must mean the tests caught the mutant (Codex and CodeAnt on #374)."""

    def test_tests_that_already_fail_kill_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n"
                    "  - name: nowhere\n    path: pkg/m.py\n"
                    "    find: 'x * 9'\n    replace: 'x * 3'\n",
                    tests="[tests.test_misspelled]",
                )
            )
            outcomes = mutation.run(root, table, jobs=1)
            self.assertEqual(["NOT RUN", "NOT FOUND"], [o.status for o in outcomes])
            self.assertIn("the unmutated tests fail", outcomes[0].detail)
            self.assertEqual(
                1,
                mutation.main(
                    ["--root", str(root), "--table", str(base / "table.yaml")]
                ),
            )

    def test_a_symlinked_target_is_never_written_through(self) -> None:
        for linked, target in (
            ("file", "pkg/linked.py"),
            ("directory", "out/linked.py"),
        ):
            with self.subTest(linked), tempfile.TemporaryDirectory() as scratch:
                base = pathlib.Path(scratch)
                root = _project(base)
                (base / "elsewhere").mkdir()
                outside = base / "elsewhere" / "linked.py"
                outside.write_text("value = 2\n", encoding="utf-8")
                if linked == "file":
                    (root / "pkg" / "linked.py").symlink_to(outside)
                else:
                    (root / "out").symlink_to(base / "elsewhere")
                table = mutation.load_table(
                    _table(
                        base,
                        f"  - name: through a link\n    path: {target}\n"
                        "    find: 'value = 2'\n    replace: 'value = 3'\n",
                    )
                )
                (outcome,) = mutation.run(root, table, jobs=1)
                self.assertEqual("value = 2\n", outside.read_text(encoding="utf-8"))
                self.assertEqual("REFUSED", outcome.status)
                self.assertIn("through a link: REFUSED", mutation.check(root, table)[0])

    def test_a_timeout_ends_the_tests_child_processes_too(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            pid_file = base / "child.pid"
            spawn = (
                "import subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
                f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
                "while True:\n"
                "    time.sleep(0.1)\n"
            )
            table_path = base / "table.yaml"
            table_path.write_text(
                yaml.safe_dump(
                    {
                        "id": "fixture",
                        "tests": ["tests.test_m"],
                        "mutants": [
                            {
                                "name": "wait spawns and hangs",
                                "path": "pkg/m.py",
                                "find": "return None",
                                "replace": spawn,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (outcome,) = mutation.run(
                root, mutation.load_table(table_path), jobs=1, timeout=3
            )
            self.assertEqual("KILLED", outcome.status)
            pid = int(pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 5
            while _alive(pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertFalse(_alive(pid), "the tests' child outlived the timeout")

    def test_a_missing_root_is_a_usage_error_for_check_too(self) -> None:
        # `--check` reported a missing root as missing anchors (CodeAnt on #374).
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            path = _table(
                base,
                "  - name: n\n    path: pkg/m.py\n    find: 'x * 2'\n    replace: 'x * 3'\n",
            )
            arguments = [
                "--root",
                str(base / "missing"),
                "--table",
                str(path),
                "--check",
            ]
            self.assertEqual(2, mutation.main(arguments))

    def test_the_tests_read_no_system_git_configuration(self) -> None:
        # A host's /etc/gitconfig could set hooks or filters for Git in the copy
        # (CodeAnt on #374).
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / "tests" / "test_env.py").write_text(
                "import os\nimport unittest\n\n\n"
                "class E(unittest.TestCase):\n"
                "    def test_no_system_config(self):\n"
                "        self.assertEqual('1', os.environ.get('GIT_CONFIG_NOSYSTEM'))\n",
                encoding="utf-8",
            )
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: n\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                    tests="[tests.test_env, tests.test_m]",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
        self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_a_missing_root_is_a_usage_error(self) -> None:
        # It raised a traceback from inside the copy (CodeAnt on #374).
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            path = _table(
                base,
                "  - name: n\n    path: pkg/m.py\n    find: 'x * 2'\n    replace: 'x * 3'\n",
            )
            arguments = ["--root", str(base / "missing"), "--table", str(path)]
            try:
                code = mutation.main(arguments)
            except Exception as exc:
                self.fail(f"main raised {exc!r}")
            self.assertEqual(2, code)

    def test_a_copy_that_fails_credits_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: n\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                )
            )
            with mock.patch(
                "tools.mutation.shutil.copytree", side_effect=OSError("no space left")
            ):
                try:
                    outcomes = mutation.run(root, table, jobs=1)
                except OSError as exc:
                    self.fail(f"run raised {exc!r}")
        self.assertEqual(["NOT RUN"], [o.status for o in outcomes])
        self.assertIn("no space left", outcomes[0].detail)

    def test_a_copy_that_fails_after_the_snapshot_credits_nothing(self) -> None:
        # The snapshot is copied first; a later copy failing must not escape either.
        # `copytree` recurses through itself, so only a copy into a mutant's scratch
        # directory, never the snapshot's, fails here.
        real = shutil.copytree

        def fail_after_the_snapshot(src, dst, *args, **kwargs):  # type: ignore[no-untyped-def]
            if pathlib.Path(dst).parent.name.startswith("gnostoa-mutant-"):
                raise OSError("no space left")
            return real(src, dst, *args, **kwargs)

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: n\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                )
            )
            with mock.patch("tools.mutation.shutil.copytree", fail_after_the_snapshot):
                outcomes = mutation.run(root, table, jobs=1)
        self.assertEqual(["NOT RUN"], [o.status for o in outcomes])
        self.assertIn("the copy failed: no space left", outcomes[0].detail)

    def test_a_timeout_must_be_positive(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            path = _table(
                base,
                "  - name: n\n    path: pkg/m.py\n    find: 'x * 2'\n    replace: 'x * 3'\n",
            )
            table = mutation.load_table(path)
            with self.assertRaises(ValueError):
                mutation.run(root, table, timeout=0)
            self.assertEqual(
                2,
                mutation.main(
                    ["--root", str(root), "--table", str(path), "--timeout", "0"]
                ),
            )


class BaselineOrderTests(unittest.TestCase):
    """The baseline runs first, alone, as wide as the mutants (Codex on #374)."""

    @staticmethod
    def _table(base: pathlib.Path) -> mutation.Table:
        mutants = "".join(
            f"  - name: m{i}\n    path: pkg/m.py\n    find: 'x * 2'\n"
            f"    replace: 'x * {i + 3}'\n"
            for i in range(2)
        )
        return mutation.load_table(_table(base, mutants))

    def test_the_baseline_ends_before_any_mutant_starts(self) -> None:
        events: list[str] = []

        def baseline(*_args):  # type: ignore[no-untyped-def]
            time.sleep(0.3)
            events.append("baseline ended")

        def one(*args):  # type: ignore[no-untyped-def]
            events.append("mutant started")
            return mutation.Outcome(args[2].name, "KILLED", "")

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = self._table(base)
            with (
                mock.patch.object(mutation, "_baseline", baseline),
                mock.patch.object(mutation, "_run_one", one),
            ):
                mutation.run(root, table, jobs=2)
        first = events.index("mutant started")
        self.assertNotIn("baseline ended", events[first:], events)

    def test_the_baseline_runs_as_wide_as_the_mutants(self) -> None:
        active = 0
        peak = 0
        lock = threading.Lock()

        def baseline(*_args):  # type: ignore[no-untyped-def]
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.3)
            with lock:
                active -= 1

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = self._table(base)
            with (
                mock.patch.object(mutation, "_baseline", baseline),
                mock.patch.object(
                    mutation,
                    "_run_one",
                    lambda *a: mutation.Outcome(a[2].name, "KILLED", ""),
                ),
            ):
                mutation.run(root, table, jobs=2)
        self.assertEqual(2, peak)

    def test_no_mutant_runs_after_a_failing_baseline(self) -> None:
        ran: list[str] = []

        def one(*args):  # type: ignore[no-untyped-def]
            ran.append(args[2].name)
            return mutation.Outcome(args[2].name, "KILLED", "")

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = self._table(base)
            with (
                mock.patch.object(mutation, "_baseline", return_value="it fails"),
                mock.patch.object(mutation, "_run_one", one),
            ):
                outcomes = mutation.run(root, table, jobs=2)
        self.assertEqual([], ran)
        self.assertEqual(["NOT RUN", "NOT RUN"], [o.status for o in outcomes])

    def test_a_suite_that_cannot_run_beside_itself_kills_nothing(self) -> None:
        # Its test holds an exclusive lock outside the copy for a second.
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            lock = base / "shared.lock"
            (root / "tests" / "test_lock.py").write_text(
                "import os\nimport time\nimport unittest\n\n\n"
                "class L(unittest.TestCase):\n"
                "    def test_alone(self):\n"
                f"        held = os.open({str(lock)!r}, os.O_CREAT | os.O_EXCL)\n"
                "        time.sleep(1)\n"
                "        os.close(held)\n"
                f"        os.unlink({str(lock)!r})\n",
                encoding="utf-8",
            )
            # Two mutants the suite cannot see: alone, each survives.
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: same double\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: '2 * x'\n"
                    "  - name: added double\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x + x'\n",
                    tests="[tests.test_lock]",
                )
            )
            outcomes = mutation.run(root, table, jobs=2)
        self.assertNotIn("KILLED", [o.status for o in outcomes], outcomes)


class ContainmentTests(unittest.TestCase):
    """What the tests do in a copy stays in it (CodeAnt on #374)."""

    def test_output_beyond_the_limit_ends_the_tests(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table_path = base / "table.yaml"
            table_path.write_text(
                yaml.safe_dump(
                    {
                        "id": "fixture",
                        "tests": ["tests.test_m"],
                        "mutants": [
                            {
                                "name": "wait prints forever",
                                "path": "pkg/m.py",
                                "find": "return None",
                                "replace": "while True:\n    print('x' * 65536)\n",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            started = time.monotonic()
            with mock.patch.object(mutation, "_OUTPUT_LIMIT_BYTES", 1_000_000):
                (outcome,) = mutation.run(
                    root, mutation.load_table(table_path), jobs=1, timeout=15
                )
            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual("KILLED", outcome.status)
            self.assertIn("more than", outcome.detail)

    def test_output_beyond_the_limit_counts_after_the_tests_exit(self) -> None:
        # Tests that write past the limit and exit within one poll (Codex on #374).
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: wait prints a lot\n    path: pkg/m.py\n"
                    "    find: 'return None'\n"
                    "    replace: |\n"
                    "      print('x' * 2_000_000)\n"
                    "      return None\n",
                )
            )
            with (
                mock.patch.object(mutation, "_OUTPUT_LIMIT_BYTES", 1_000_000),
                mock.patch.object(mutation, "_POLL_SECONDS", 60),
            ):
                (outcome,) = mutation.run(root, table, jobs=1, timeout=120)
            self.assertEqual("KILLED", outcome.status, outcome.detail)
            self.assertIn("more than", outcome.detail)

    def test_a_link_out_of_the_copy_refuses_the_copy(self) -> None:
        for kind in ("absolute", "relative", "through a link to the root"):
            with self.subTest(kind), tempfile.TemporaryDirectory() as scratch:
                base = pathlib.Path(scratch)
                root = _project(base)
                outside = base / "outside"
                outside.mkdir()
                if kind == "absolute":
                    (root / "pkg" / "data").symlink_to(outside)
                elif kind == "relative":
                    (root / "pkg" / "data").symlink_to("../../outside")
                else:
                    (root / "here").symlink_to(".")
                    (root / "pkg" / "data").symlink_to("../here/../outside")
                (root / "tests" / "test_write.py").write_text(
                    "import unittest\n\n\n"
                    "class W(unittest.TestCase):\n"
                    "    def test_write(self):\n"
                    "        with open('pkg/data/written', 'w') as handle:\n"
                    "            handle.write('x')\n",
                    encoding="utf-8",
                )
                table = mutation.load_table(
                    _table(
                        base,
                        "  - name: double triples\n    path: pkg/m.py\n"
                        "    find: 'x * 2'\n    replace: 'x * 3'\n",
                        tests="[tests.test_write, tests.test_m]",
                    )
                )
                (outcome,) = mutation.run(root, table, jobs=1)
                self.assertFalse((outside / "written").exists())
                self.assertEqual("NOT RUN", outcome.status, outcome.detail)
                self.assertIn("outside the copy", outcome.detail)

    def test_a_link_inside_the_copy_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / "pkg" / "alias.py").symlink_to("m.py")
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
            self.assertEqual("KILLED", outcome.status, outcome.detail)


class CopyTests(unittest.TestCase):
    """A copy is faithful: its tests see the repository they would see in place."""

    def test_tests_that_read_git_see_the_repository(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / "tests" / "test_git.py").write_text(
                "import subprocess\nimport unittest\n\n\n"
                "class G(unittest.TestCase):\n"
                "    def test_tracked(self):\n"
                "        subprocess.run(\n"
                "            ['git', 'ls-files', '--error-unmatch', 'pkg/m.py'],\n"
                "            check=True, capture_output=True,\n"
                "        )\n",
                encoding="utf-8",
            )
            git = shutil.which("git")
            if git is None:
                self.skipTest("git is not installed")
            clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            for command in (["init", "-q"], ["add", "-A"]):
                subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                    [git, *command], cwd=root, env=clean, check=True
                )
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                    tests="[tests.test_git, tests.test_m]",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
            self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_git_metadata_that_routes_outside_is_dropped_from_the_copy(self) -> None:
        # Git in the copy took its work tree from the copied configuration (Codex on
        # #374), and `git clean` there removed files outside the copy. The copy's
        # configuration keeps only the repository's format, so Git stays in it.
        git = shutil.which("git")
        if git is None:
            self.skipTest("git is not installed")
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        for route in ("worktree", "include"):
            with self.subTest(route), tempfile.TemporaryDirectory() as scratch:
                base = pathlib.Path(scratch)
                root = _project(base)
                outside = base / "outside"
                outside.mkdir()
                marker = outside / "keep.txt"
                marker.write_text("keep\n", encoding="utf-8")
                (root / "tests" / "test_clean.py").write_text(
                    "import subprocess\nimport unittest\n\n\n"
                    "class C(unittest.TestCase):\n"
                    "    def test_clean(self):\n"
                    "        subprocess.run(['git', 'clean', '-fdq'], check=True)\n",
                    encoding="utf-8",
                )
                for command in (["init", "-q"], ["add", "-A"]):
                    subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                        [git, *command], cwd=root, env=clean, check=True
                    )
                if route == "worktree":
                    setting = f"[core]\n\tworktree = {outside}\n"
                else:
                    included = base / "included.cfg"
                    included.write_text(
                        f"[core]\n\tworktree = {outside}\n", encoding="utf-8"
                    )
                    setting = f"[include]\n\tpath = {included}\n"
                with (root / ".git" / "config").open("a", encoding="utf-8") as config:
                    config.write(setting)
                table = mutation.load_table(
                    _table(
                        base,
                        "  - name: double triples\n    path: pkg/m.py\n"
                        "    find: 'x * 2'\n    replace: 'x * 3'\n",
                        tests="[tests.test_clean, tests.test_m]",
                    )
                )
                (outcome,) = mutation.run(root, table, jobs=1)
                self.assertTrue(marker.exists(), "git in the copy cleaned outside it")
                self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_git_configuration_that_runs_programs_is_dropped_from_the_copy(
        self,
    ) -> None:
        # A clean filter, and a hook, ran from the copied metadata (Codex on #374).
        git = shutil.which("git")
        if git is None:
            self.skipTest("git is not installed")
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        for route in ("filter", "hook"):
            with self.subTest(route), tempfile.TemporaryDirectory() as scratch:
                base = pathlib.Path(scratch)
                root = _project(base)
                marker = base / "ran"
                (root / "pkg" / "data.txt").write_text("data\n", encoding="utf-8")
                (root / ".gitattributes").write_text(
                    "*.txt filter=mark\n", encoding="utf-8"
                )
                (root / "tests" / "test_git_use.py").write_text(
                    "import pathlib\nimport subprocess\nimport unittest\n\n\n"
                    "class U(unittest.TestCase):\n"
                    "    def test_use(self):\n"
                    "        pathlib.Path('pkg/data.txt').write_text('more\\n')\n"
                    "        subprocess.run(['git', 'add', 'pkg/data.txt'], check=True)\n"
                    "        subprocess.run(['git', '-c', 'user.name=t', '-c',\n"
                    "                        'user.email=t@example.invalid', 'commit',\n"
                    "                        '-qm', 'x'], check=True)\n",
                    encoding="utf-8",
                )
                for command in (["init", "-q"], ["add", "-A"]):
                    subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                        [git, *command], cwd=root, env=clean, check=True
                    )
                if route == "filter":
                    # A script, since `;` would start a comment in Git's configuration.
                    script = base / "filter.sh"
                    script.write_text(
                        f"#!/bin/sh\ntouch {marker}\ncat\n", encoding="utf-8"
                    )
                    script.chmod(0o755)
                    with (root / ".git" / "config").open(
                        "a", encoding="utf-8"
                    ) as config:
                        config.write(f'[filter "mark"]\n\tclean = {script}\n')
                else:
                    hook = root / ".git" / "hooks" / "pre-commit"
                    hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
                    hook.chmod(0o755)
                table = mutation.load_table(
                    _table(
                        base,
                        "  - name: double triples\n    path: pkg/m.py\n"
                        "    find: 'x * 2'\n    replace: 'x * 3'\n",
                        tests="[tests.test_git_use, tests.test_m]",
                    )
                )
                (outcome,) = mutation.run(root, table, jobs=1)
                self.assertFalse(marker.exists(), f"the copied {route} ran")
                self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_a_linked_hooks_directory_is_removed_too(self) -> None:
        # `rmtree` refuses a link, and its ignored error left the hooks in place
        # (CodeAnt on #374).
        git = shutil.which("git")
        if git is None:
            self.skipTest("git is not installed")
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            marker = base / "hooked"
            (root / "tests" / "test_commit.py").write_text(
                "import subprocess\nimport unittest\n\n\n"
                "class C(unittest.TestCase):\n"
                "    def test_commit(self):\n"
                "        subprocess.run(['git', '-c', 'user.name=t', '-c',\n"
                "                        'user.email=t@example.invalid', 'commit',\n"
                "                        '--allow-empty', '-qm', 'x'], check=True)\n",
                encoding="utf-8",
            )
            subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                [git, "init", "-q"], cwd=root, env=clean, check=True
            )
            hooks = root / ".git" / "hooks"
            shutil.rmtree(hooks)
            real = root / ".git" / "real-hooks"
            real.mkdir()
            hook = real / "pre-commit"
            hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
            hook.chmod(0o755)
            hooks.symlink_to("real-hooks")
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                    tests="[tests.test_commit, tests.test_m]",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
            # Inside the block: the marker goes with the scratch directory.
            self.assertFalse(marker.exists(), "a linked hook ran in the copy")
        self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_a_subsection_keeps_none_of_its_settings(self) -> None:
        # `[core "x"] bare = true` is `core.x.bare`, not `core.bare`; kept as the
        # latter, it would make the copy a bare repository.
        git = shutil.which("git")
        if git is None:
            self.skipTest("git is not installed")
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / "tests" / "test_status.py").write_text(
                "import subprocess\nimport unittest\n\n\n"
                "class S(unittest.TestCase):\n"
                "    def test_status(self):\n"
                "        subprocess.run(['git', 'status', '--short'], check=True)\n",
                encoding="utf-8",
            )
            subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                [git, "init", "-q"], cwd=root, env=clean, check=True
            )
            with (root / ".git" / "config").open("a", encoding="utf-8") as config:
                config.write('[core "x"]\n\tbare = true\n')
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                    tests="[tests.test_status, tests.test_m]",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
        self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_a_shared_git_directory_refuses_the_copy(self) -> None:
        # `commondir` makes Git share another repository's directory.
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / ".git").mkdir()
            (root / ".git" / "commondir").write_text(
                str(base / "other"), encoding="utf-8"
            )
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
        self.assertEqual("NOT RUN", outcome.status, outcome.detail)
        self.assertIn("shares another repository", outcome.detail)

    def test_every_copy_is_taken_from_one_snapshot(self) -> None:
        # The root changed during a run, and later copies saw the change (Codex on
        # #374): here an edit after the baseline removes the mutant's anchor.
        # The test wraps the real baseline.
        real = mutation._baseline  # skipcq: PYL-W0212

        def baseline_then_edit(root, table, timeout):  # type: ignore[no-untyped-def]
            failure = real(root, table, timeout)
            for live in roots:
                (live / "pkg" / "m.py").write_text(
                    "def double(x):\n    return x + x\n\n\n"
                    "def wait():\n    return None\n",
                    encoding="utf-8",
                )
            return failure

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            roots = [root]
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                )
            )
            with mock.patch.object(mutation, "_baseline", baseline_then_edit):
                (outcome,) = mutation.run(root, table, jobs=1)
        self.assertEqual("KILLED", outcome.status, outcome.detail)

    def test_a_git_file_is_never_copied(self) -> None:
        # A `.git` file points at metadata that other worktrees share.
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            root = _project(base)
            (root / ".git").write_text(f"gitdir: {base / 'shared'}\n", encoding="utf-8")
            (root / "tests" / "test_no_git.py").write_text(
                "import pathlib\nimport unittest\n\n\n"
                "class N(unittest.TestCase):\n"
                "    def test_no_git(self):\n"
                "        self.assertFalse(pathlib.Path('.git').exists())\n",
                encoding="utf-8",
            )
            table = mutation.load_table(
                _table(
                    base,
                    "  - name: double triples\n    path: pkg/m.py\n"
                    "    find: 'x * 2'\n    replace: 'x * 3'\n",
                    tests="[tests.test_no_git, tests.test_m]",
                )
            )
            (outcome,) = mutation.run(root, table, jobs=1)
            self.assertEqual("KILLED", outcome.status, outcome.detail)


class AnchorShapeTests(unittest.TestCase):
    def test_a_decorated_definition_is_replaced_with_its_decorator(self) -> None:
        source = "@cache\ndef f():\n    return 1\n"
        mutated = mutation.apply(
            source,
            "@cache\ndef f():\n    return 1\n",
            "def f():\n    return 2\n",
            python=True,
        )
        self.assertEqual("def f():\n    return 2\n", mutated)

    def test_a_token_anchor_keeps_the_document_s_indentation(self) -> None:
        source = "jobs:\n  smoke:\n    name: smoke\n    needs: [policy]\n"
        mutated = mutation.apply(
            source,
            "  smoke:\n    name: smoke\n    needs: [policy]\n",
            "  smoke:\n    name: smoke\n    needs: [policy, extended]\n",
            python=False,
        )
        self.assertEqual(
            {"jobs": {"smoke": {"name": "smoke", "needs": ["policy", "extended"]}}},
            yaml.safe_load(mutated),
        )
        self.assertEqual(
            "jobs:\n  smoke:\n    name: smoke\n    needs: [policy, extended]\n",
            mutated,
        )
        reflowed = mutation.apply(
            "jobs:\n    smoke:\n        name: smoke\n        needs: [policy]\n",
            "  smoke:\n    name: smoke\n    needs: [policy]\n",
            "  smoke:\n    name: smoke\n    needs: [policy, extended]\n",
            python=False,
        )
        self.assertEqual(yaml.safe_load(mutated), yaml.safe_load(reflowed))


class ReindentTests(unittest.TestCase):
    def test_a_statement_replacement_takes_the_matched_indentation(self) -> None:
        source = textwrap.dedent(
            """\
            class C:
                def f(self):
                    if self:
                        return 1
                    return 0
            """
        )
        mutated = mutation.apply(
            source,
            "if self:\n    return 1\n",
            "if not self:\n    return 1\n",
            python=True,
        )
        self.assertIn("        if not self:\n            return 1\n", mutated)
        ast.parse(mutated)


if __name__ == "__main__":
    unittest.main()
