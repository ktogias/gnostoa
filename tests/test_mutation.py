"""The one owner of targeted mutants, and its tables (Decision 0104, #373).

About twenty hand-maintained scripts matched literal text, so `ruff --fix` and refactors
broke their anchors silently. These tests define the owner that replaces them.
"""

from __future__ import annotations

import ast
import pathlib
import tempfile
import textwrap
import unittest

import yaml

from tools import mutation
from tools.knowledge_common import KnowledgeFormatError


def _project(base: pathlib.Path) -> pathlib.Path:
    """A tiny project with one module for anchor and check tests."""
    root = base / "project"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "pkg" / "m.py").write_text(
        "def double(x):\n    return x * 2\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
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
            self.assertEqual([], mutation.check(root, table))
        self.assertEqual(
            "alpha = 1\r\nbeta = 3\r\n",
            mutation.apply(
                "alpha = 1\r\nbeta = 2\r\n", "beta = 2", "beta = 3", python=False
            ),
        )

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
            except UnicodeDecodeError as exc:
                self.fail(f"raised {exc!r}")
            self.assertEqual(
                ["legacy: NOT FOUND"], [p.split(" (")[0] for p in problems]
            )
            self.assertIn("UTF-8", problems[0])


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


class CommandTests(unittest.TestCase):
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


class AnchorShapeTests(unittest.TestCase):
    def test_a_multi_line_replacement_in_an_inline_suite_is_refused(self) -> None:
        # `if flag: x = 1` gives its statement no indentation, so later lines of a
        # replacement would leave the suite (CodeAnt on #374).
        source = "if flag: x = 1\n"
        with self.assertRaises(mutation.AnchorError) as raised:
            mutation.apply(source, "x = 1", "x = 2\ny = 3", python=True)
        self.assertEqual("INVALID", raised.exception.status)
        self.assertEqual(
            "if flag: x = 2\n", mutation.apply(source, "x = 1", "x = 2", python=True)
        )

    def test_an_f_string_fragment_is_no_string_literal(self) -> None:
        # `'foo'` matched the fragment of `f"foo{bar}"`, whose text has no quotes, and
        # the replacement put quotes into the f-string (Codex on #374).
        source = "x = f'foo{bar}'\n"
        with self.assertRaises(mutation.AnchorError) as raised:
            mutation.apply(source, "'foo'", "'baz'", python=True)
        self.assertEqual("NOT FOUND", raised.exception.status)
        # An expression inside the f-string is a real expression.
        self.assertEqual(
            "x = f'foo{baz}'\n", mutation.apply(source, "bar", "baz", python=True)
        )

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
