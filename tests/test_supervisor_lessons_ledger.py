"""The supervisor lessons ledger keeps one fixed table schema (#494, PR #495).

The PAO's acceptance cases for the ledger (#325 6830768656, routed by #325
6830817025) found that GitHub Flavored Markdown drops every cell beyond a table's
header, so the published ledger hid the fix and status cells of rows 17 to 31
(P1). Two rows were also marked closed without the three pieces of evidence the
ledger's own rule requires (P2), and the status words mixed progress with closure
(P3). These tests read the record's raw table lines, split as GFM splits them, so
a row wider than its header is counted rather than silently cut. They fail when a
row's cell count differs from its header's, when a kind, guard state or status
leaves its vocabulary, when an id repeats or is not a number, when a pilot guard
lacks its label, or when a row is closed without its guard, English record and
memory note.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "knowledge" / "assessments" / "supervisor-lessons-ledger.md"
COLUMNS = (
    "Id",
    "Kind",
    "Item",
    "Timeline",
    "Root cause",
    "Fix and mechanical guard",
    "Guard state",
    "Guard reference",
    "English record",
    "Memory note",
    "Status",
    "Notes",
)
KINDS = frozenset({"lesson", "incident", "liveness firing"})
GUARD_STATES = frozenset({"none", "staged", "live-pilot", "live-repo"})
STATUSES = frozenset({"Open", "Closed"})
ABSENT = frozenset({"", "—", "none", "none cited"})
PILOT_LABEL = "pilot tooling (not in this repository)"
EPISODE = re.compile(r"Liveness episode: [0-9a-f]{16}\b")
POSITIVE_ID = re.compile(r"[1-9][0-9]*")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
CODE_PATH = re.compile(r"`([^`\s]+/[^`\s]*)`")


def _cells(line: str) -> list[str]:
    """A table line's cells as GFM splits them: at every pipe that no backslash
    escapes, after the optional leading and trailing pipes."""

    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.strip() for cell in UNESCAPED_PIPE.split(text)]


def _tables(markdown: str) -> list[list[list[str]]]:
    """Every table the parser finds, as its raw rows of cells: the header first,
    then the body rows, without the delimiter row."""

    lines = markdown.splitlines()
    tables = []
    parser = MarkdownIt("commonmark").enable("table")
    for token in parser.parse(markdown):
        if token.type == "table_open" and token.map is not None:
            start, end = token.map
            rows = [_cells(line) for line in lines[start:end]]
            tables.append([rows[0], *rows[2:]])
    return tables


def _width_problems(tables: list[list[list[str]]]) -> list[str]:
    """Every body row whose cell count differs from its header's."""

    problems = []
    for number, table in enumerate(tables, start=1):
        width = len(table[0])
        for index, row in enumerate(table[1:], start=1):
            if len(row) != width:
                problems.append(
                    f"table {number} row {index}: {len(row)} cells under a "
                    f"{width}-cell header"
                )
    return problems


def _id_problems(ids: list[str]) -> list[str]:
    """Ids are unique positive integers in ascending order."""

    problems = [
        f"id {ident!r} is not a positive integer"
        for ident in ids
        if not POSITIVE_ID.fullmatch(ident)
    ]
    numbers = [int(ident) for ident in ids if POSITIVE_ID.fullmatch(ident)]
    if len(set(numbers)) != len(numbers):
        problems.append("an id repeats")
    if numbers != sorted(numbers):
        problems.append("the ids are not in ascending order")
    return problems


def _guard_problems(ident: str, fields: dict[str, str], root: Path) -> list[str]:
    """A pilot guard carries its label; a repository guard cites a path that
    exists."""

    state, reference = fields["Guard state"], fields["Guard reference"]
    if state in ("staged", "live-pilot") and PILOT_LABEL not in reference:
        return [f"row {ident}: a {state} guard lacks the label {PILOT_LABEL!r}"]
    if state == "live-repo" and not any(
        (root / path).exists() for path in CODE_PATH.findall(reference)
    ):
        return [f"row {ident}: a live-repo guard cites no repository path that exists"]
    return []


def _closure_problems(ident: str, fields: dict[str, str]) -> list[str]:
    """Closed needs a built guard, an English record and a memory note."""

    if fields["Status"] != "Closed":
        return []
    missing = [
        name
        for name in ("Guard reference", "English record", "Memory note")
        if fields[name] in ABSENT
    ]
    if fields["Guard state"] == "none":
        missing.append("Guard state")
    return [f"row {ident}: closed without {name}" for name in missing]


def _row_problems(fields: dict[str, str], root: Path) -> list[str]:
    """One ledger row against the vocabularies, the pilot label and the closure
    rule."""

    ident = fields["Id"]
    problems = [
        f"row {ident}: {column} {fields[column]!r} is not one of {sorted(allowed)}"
        for column, allowed in (
            ("Kind", KINDS),
            ("Guard state", GUARD_STATES),
            ("Status", STATUSES),
        )
        if fields[column] not in allowed
    ]
    if fields["Kind"] == "liveness firing" and not EPISODE.search(fields["Item"]):
        problems.append(
            f"row {ident}: a liveness firing names no 'Liveness episode: <id>'"
        )
    if fields["Guard state"] in GUARD_STATES:
        problems.extend(_guard_problems(ident, fields, root))
    problems.extend(_closure_problems(ident, fields))
    return problems


def ledger_problems(markdown: str, root: Path = ROOT) -> list[str]:
    """Every way the text breaks the ledger schema; empty when it holds."""

    tables = _tables(markdown)
    problems = _width_problems(tables)
    ledgers = [table for table in tables if tuple(table[0]) == COLUMNS]
    if len(ledgers) != 1:
        return [*problems, f"{len(ledgers)} tables carry the ledger header, not 1"]
    rows = [row for row in ledgers[0][1:] if len(row) == len(COLUMNS)]
    problems.extend(_id_problems([row[0] for row in rows]))
    for row in rows:
        problems.extend(_row_problems(dict(zip(COLUMNS, row, strict=True)), root))
    return problems


def _table(*rows: tuple[str, ...]) -> str:
    """A ledger table with the given body rows."""

    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def _row(ident: str = "1", **changes: str) -> tuple[str, ...]:
    """A complete open lesson row, with the named cells changed."""

    fields = {
        "Id": ident,
        "Kind": "lesson",
        "Item": "A lesson",
        "Timeline": "—",
        "Root cause": "—",
        "Fix and mechanical guard": "A guard",
        "Guard state": "live-pilot",
        "Guard reference": f"{PILOT_LABEL}: a gate",
        "English record": "[ledger][L]",
        "Memory note": "a-note",
        "Status": "Open",
        "Notes": "—",
    }
    fields.update(
        {column.replace("_", " "): value for column, value in changes.items()}
    )
    return tuple(fields[column] for column in COLUMNS)


class LedgerRecordTests(unittest.TestCase):
    maxDiff = None

    def test_every_table_row_has_as_many_cells_as_its_header(self) -> None:
        tables = _tables(LEDGER.read_text(encoding="utf-8"))
        self.assertTrue(tables)
        self.assertEqual(_width_problems(tables), [])

    def test_the_ledger_meets_its_schema_and_closure_rule(self) -> None:
        self.assertEqual(ledger_problems(LEDGER.read_text(encoding="utf-8")), [])


class LedgerCheckReplayTests(unittest.TestCase):
    """Each check fails on a replay of the defect it guards, and passes its
    control."""

    def test_a_complete_table_passes(self) -> None:
        self.assertEqual(ledger_problems(_table(_row("1"), _row("2"))), [])

    def test_a_row_wider_than_its_header_is_refused(self) -> None:
        # P1: the published table had a 4-cell header over 6-cell rows.
        markdown = (
            "| # | Lesson | Mechanical guard | Status |\n|---|---|---|---|\n"
            "| 17 | Liveness episode | Timeline | Root cause | Fix | Open |\n"
        )
        self.assertEqual(
            _width_problems(_tables(markdown)),
            ["table 1 row 1: 6 cells under a 4-cell header"],
        )

    def test_an_escaped_pipe_stays_inside_its_cell(self) -> None:
        markdown = "| a | b |\n|---|---|\n| x \\| y | z |\n"
        self.assertEqual(_width_problems(_tables(markdown)), [])

    def test_a_closed_row_without_a_memory_note_is_refused(self) -> None:
        # P2: row 13 was marked closed with no memory note cited.
        markdown = _table(_row(Status="Closed", Memory_note="none cited"))
        self.assertEqual(
            ledger_problems(markdown), ["row 1: closed without Memory note"]
        )

    def test_a_closed_row_with_all_three_passes(self) -> None:
        self.assertEqual(ledger_problems(_table(_row(Status="Closed"))), [])

    def test_a_closed_row_without_a_built_guard_is_refused(self) -> None:
        markdown = _table(_row(Status="Closed", Guard_state="none"))
        self.assertEqual(
            ledger_problems(markdown), ["row 1: closed without Guard state"]
        )

    def test_a_status_outside_open_and_closed_is_refused(self) -> None:
        # P3: "Live" read as done although the lesson was open.
        problems = ledger_problems(_table(_row(Status="Live")))
        self.assertEqual(len(problems), 1)
        self.assertIn("Status 'Live'", problems[0])

    def test_a_repeated_or_non_numeric_id_is_refused(self) -> None:
        # P4 and P7: the correction row "26-corr" sat beside row 26.
        markdown = _table(_row("26"), _row("26-corr"), _row("26"))
        self.assertEqual(
            ledger_problems(markdown),
            ["id '26-corr' is not a positive integer", "an id repeats"],
        )

    def test_zero_a_non_ascii_digit_and_a_descending_id_are_refused(self) -> None:
        digit = chr(0x0663)  # ARABIC-INDIC DIGIT THREE: str.isdigit() accepts it
        markdown = _table(_row("2"), _row("1"), _row("0"), _row(digit))
        self.assertEqual(
            ledger_problems(markdown),
            [
                "id '0' is not a positive integer",
                f"id {digit!r} is not a positive integer",
                "the ids are not in ascending order",
            ],
        )

    def test_a_pilot_guard_without_its_label_is_refused(self) -> None:
        # P5: pilot paths read as if they were in this repository.
        markdown = _table(_row(Guard_reference="`publish-gate/prior_art_gate.py`"))
        self.assertEqual(
            ledger_problems(markdown),
            [f"row 1: a live-pilot guard lacks the label {PILOT_LABEL!r}"],
        )

    def test_a_repository_guard_must_cite_an_existing_path(self) -> None:
        missing = _row(Guard_state="live-repo", Guard_reference="`publish-gate/x.py`")
        present = _row(
            Guard_state="live-repo",
            Guard_reference="`tests/test_supervisor_lessons_ledger.py`",
        )
        self.assertEqual(
            ledger_problems(_table(missing)),
            ["row 1: a live-repo guard cites no repository path that exists"],
        )
        self.assertEqual(ledger_problems(_table(present)), [])

    def test_a_liveness_firing_names_its_episode(self) -> None:
        unnamed = _row(Kind="liveness firing", Item="A firing")
        named = _row(Kind="liveness firing", Item="Liveness episode: 93e1f30a24e3bf46.")
        self.assertEqual(
            ledger_problems(_table(unnamed)),
            ["row 1: a liveness firing names no 'Liveness episode: <id>'"],
        )
        self.assertEqual(ledger_problems(_table(named)), [])

    def test_a_missing_ledger_table_is_refused(self) -> None:
        self.assertEqual(
            ledger_problems("No table here.\n"),
            ["0 tables carry the ledger header, not 1"],
        )


if __name__ == "__main__":
    unittest.main()
