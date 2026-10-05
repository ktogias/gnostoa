"""The one owner of targeted mutants, and its tables (Decision 0104, #373).

About twenty hand-maintained scripts matched literal text, so `ruff --fix` and refactors
broke their anchors silently. These tests define the owner that replaces them.
"""

from __future__ import annotations

import ast
import pathlib
import tempfile
import textwrap
import threading
import time
import unittest
from unittest import mock

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
            with mock.patch.object(mutation, "_run_one", one):
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
