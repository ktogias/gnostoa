"""DeepSource's 0-based columns in the readback's 1-based model (#309, A2).

DeepSource reports issue columns from 0 and lines from 1 (#309, 6103702467), so
a finding on a top-level `def` sits at column 0, which the readback's model
refuses: every full read carrying one failed with NORMALIZATION_ERROR. The
conversion adds one to a column only when it is a non-negative integer; any
other value reaches the model unchanged and stays refused.
"""

from __future__ import annotations

import unittest
from typing import Any

from deepsource_fakes import (
    HEAD,
    OBSERVED,
    RUN_UID,
    GraphQLFake,
    check_page,
    issue,
    run_page,
)

from tools import analyzer_deepsource


def _read(*issues: dict[str, Any]) -> dict[str, Any]:
    return analyzer_deepsource.read_full_run(
        GraphQLFake(
            {
                ("run", None): run_page(),
                ("check-python", None): check_page(list(issues)),
            }
        ),
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        run_uid=RUN_UID,
        observed_at=OBSERVED,
    )


def _at(begin: object, end: object, *, line: int = 7) -> dict[str, Any]:
    return {**issue("i-1", line), "beginColumn": begin, "endColumn": end}


class ColumnConversionTests(unittest.TestCase):
    def test_columns_count_from_one_and_lines_are_kept(self) -> None:
        for name, begin, end, expected in (
            ("a top-level def at column 0", 0, 0, (1, 1)),
            ("a nonzero column", 21, 21, (22, 22)),
            ("distinct endpoints", 3, 9, (4, 10)),
        ):
            with self.subTest(name):
                document = _read(_at(begin, end, line=395))
                self.assertEqual("COMPLETE", document["coverage"]["status"])
                [finding] = document["findings"]
                self.assertEqual(
                    {
                        "start_line": 395,
                        "end_line": 395,
                        "start_column": expected[0],
                        "end_column": expected[1],
                    },
                    finding["range"],
                )

    def test_an_absent_column_stays_absent(self) -> None:
        [finding] = _read(_at(None, None))["findings"]
        self.assertEqual({"start_line": 7, "end_line": 7}, finding["range"])

    def test_a_malformed_column_is_still_refused(self) -> None:
        for name, value in (
            ("negative", -1),
            ("boolean", True),
            ("text", "3"),
            ("fractional", 1.5),
        ):
            for end in (False, True):
                with self.subTest(name, endpoint="end" if end else "begin"):
                    item = _at(2, value) if end else _at(value, 2)
                    document = _read(item)
                    self.assertEqual("ERROR", document["coverage"]["status"])
                    self.assertEqual(
                        "NORMALIZATION_ERROR", document["coverage"]["reason"]
                    )


if __name__ == "__main__":
    unittest.main()
