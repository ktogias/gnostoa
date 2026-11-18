"""Every mutant table's anchors still apply (Decision 0104, #373).

A refactor that breaks an anchor fails here, in the `fast` profile, the git hooks and
provider CI, instead of after a candidate's whole verification pipeline.
"""

from __future__ import annotations

import pathlib
import unittest

from tools import mutation

ROOT = pathlib.Path(__file__).resolve().parents[1]
TABLES = sorted((ROOT / "tests" / "mutants").glob("*.yaml"))


class MutantTableTests(unittest.TestCase):
    def test_there_is_at_least_one_table(self) -> None:
        self.assertTrue(TABLES, "tests/mutants holds no table")

    def test_every_table_s_anchors_apply(self) -> None:
        for path in TABLES:
            with self.subTest(table=path.name):
                table = mutation.load_table(path)
                self.assertEqual([], mutation.check(ROOT, table))


if __name__ == "__main__":
    unittest.main()
