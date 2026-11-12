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
import tempfile
import unittest
from pathlib import Path

from markdown_it import MarkdownIt

from tools.repository_scope import SOURCE_MANIFEST, candidate_paths

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = "knowledge/assessments/supervisor-lessons-ledger.md"
LEDGER = ROOT / LEDGER_PATH
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
SOURCE_COLUMNS = ("Record", "Posted", "Body bytes", "SHA-256 of the body")
SOURCE_COMMENT = "issuecomment-6828048375"
SOURCE_SHA256 = "cc879bf3ddcdbafb852f73243f9649c6c93a8aa6c556f90bf8f3efda37f41d76"  # pragma: allowlist secret -- public digest of the source record's body
CLOSED_AT_SOURCE: frozenset[str] = frozenset()
RECORD = "`knowledge/failure-modes/container-first-verification-routing-bypass.md`"
CLOSED = frozenset({"1"})


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


def ledger_problems(
    markdown: str,
    root: Path = ROOT,
    closed_at_source: frozenset[str] = CLOSED_AT_SOURCE,
) -> list[str]:
    """Every way the text breaks the ledger schema; empty when it holds.

    RED seam for #496: `closed_at_source` is accepted and not yet used, which is
    the unchanged behaviour (the source's closure is prose only)."""

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


def source_witness_problems(markdown: str, digest: str = SOURCE_SHA256) -> list[str]:
    """RED seam for #496: nothing checks the ledger's source digest yet, which is
    the unchanged behaviour."""

    del markdown, digest
    return []


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


def _repository(parent: Path) -> Path:
    """A packaged checkout under `parent`, without Git metadata, so its tracked set
    is its manifest. The manifest lists a guard file, a knowledge record, a
    directory (as a gitlink would appear) and three symlinks: one to a listed file,
    one to a file outside the checkout, and one directory link. The checkout also
    holds an unlisted file and a nested `.git` directory, and `parent` holds a file
    outside the checkout."""

    root = parent / "checkout"
    for directory in ("tests/fixtures", "tests/.git", "knowledge/failure-modes"):
        (root / directory).mkdir(parents=True)
    for name in (
        "tests/test_guard.py",
        "tests/untracked_guard.py",
        "tests/.git/config",
        "knowledge/failure-modes/a-record.md",
    ):
        (root / name).write_text("x\n", encoding="utf-8")
    (parent / "outside.py").write_text("x\n", encoding="utf-8")
    (root / "tests" / "linked_guard.py").symlink_to("test_guard.py")
    (root / "tests" / "external_guard.py").symlink_to(parent / "outside.py")
    (root / "guards").symlink_to("tests", target_is_directory=True)
    listed = (
        "guards/test_guard.py",
        "knowledge/failure-modes/a-record.md",
        "tests/external_guard.py",
        "tests/fixtures",
        "tests/linked_guard.py",
        "tests/test_guard.py",
    )
    (root / SOURCE_MANIFEST).write_bytes(b"".join(f"{n}\0".encode() for n in listed))
    return root


class LedgerRecordTests(unittest.TestCase):
    maxDiff = None

    def test_every_table_row_has_as_many_cells_as_its_header(self) -> None:
        tables = _tables(LEDGER.read_text(encoding="utf-8"))
        self.assertTrue(tables)
        self.assertEqual(_width_problems(tables), [])

    def test_the_ledger_meets_its_schema_and_closure_rule(self) -> None:
        self.assertEqual(ledger_problems(LEDGER.read_text(encoding="utf-8")), [])

    def test_the_ledger_cites_the_pinned_source_digest(self) -> None:
        text = LEDGER.read_text(encoding="utf-8")
        self.assertEqual(source_witness_problems(text), [])

    def test_the_tracked_set_holds_the_ledger_this_test_and_the_record(self) -> None:
        # A checkout reads its Git index. The runtime image has no `.git`, so the
        # self-check there reads the packaged manifest: this case shows that the
        # manifest covers knowledge/ and tests/ (#496, the PAO's open check).
        tracked = {path.as_posix() for path in candidate_paths(ROOT)}
        expected = {
            LEDGER_PATH,
            "tests/test_supervisor_lessons_ledger.py",
            RECORD.strip("`"),
        }
        self.assertLessEqual(expected, tracked)


class LedgerCheckReplayTests(unittest.TestCase):
    """Each check fails on a replay of the defect it guards, and passes its
    control."""

    maxDiff = None

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
        row = _row(Status="Closed", English_record=RECORD, Memory_note="none cited")
        self.assertEqual(
            ledger_problems(_table(row), closed_at_source=CLOSED),
            ["row 1: closed without Memory note"],
        )

    def test_a_closed_row_with_all_three_passes(self) -> None:
        self.assertEqual(ledger_problems(_table(_row(Status="Closed"))), [])

    def test_a_closed_row_with_all_four_passes(self) -> None:
        # The control of the #496 rule: closed at source, a live guard, a tracked
        # knowledge record other than the ledger, and a memory note.
        for state, reference in (
            ("live-pilot", f"{PILOT_LABEL}: a gate"),
            ("live-repo", "`tests/test_supervisor_lessons_ledger.py`"),
        ):
            with self.subTest(state=state):
                row = _row(
                    Status="Closed",
                    Guard_state=state,
                    Guard_reference=reference,
                    English_record=RECORD,
                )
                self.assertEqual(
                    ledger_problems(_table(row), closed_at_source=CLOSED), []
                )

    def test_a_closed_row_without_a_built_guard_is_refused(self) -> None:
        row = _row(Status="Closed", Guard_state="none", English_record=RECORD)
        self.assertEqual(
            ledger_problems(_table(row), closed_at_source=CLOSED),
            ["row 1: closed without Guard state"],
        )

    def test_a_closed_row_with_a_staged_guard_is_refused(self) -> None:
        # #496 gap (b), test (iii): a guard still being built is not a live guard.
        row = _row(Status="Closed", Guard_state="staged", English_record=RECORD)
        self.assertEqual(
            ledger_problems(_table(row), closed_at_source=CLOSED),
            ["row 1: closed without a live guard (staged)"],
        )

    def test_a_closed_row_needs_a_tracked_knowledge_record(self) -> None:
        # #496 gap (c), tests (i) and (ii): a GitHub-only link, a self-citation of
        # the ledger, or a cited path that is no tracked knowledge record.
        missing = "knowledge/assessments/no-such-record.md"
        escape = "knowledge/../tests/test_supervisor_lessons_ledger.py"
        cases = {
            "[ledger][L]": "row 1: closed without English record",
            f"[ledger][L]; `{LEDGER_PATH}`": (
                f"row 1: English record path {LEDGER_PATH!r} is this ledger"
            ),
            "`tests/test_supervisor_lessons_ledger.py`": (
                "row 1: English record path "
                "'tests/test_supervisor_lessons_ledger.py' is not a knowledge record"
            ),
            f"`{missing}`": f"row 1: English record path {missing!r} is not a tracked file",
            "`knowledge/failure-modes`": (
                "row 1: English record path 'knowledge/failure-modes' "
                "is not a tracked file"
            ),
            f"`{escape}`": (
                f"row 1: English record path {escape!r} is not repository-relative"
            ),
            f"{RECORD}; `{missing}`": (
                f"row 1: English record path {missing!r} is not a tracked file"
            ),
        }
        for record, problem in cases.items():
            with self.subTest(record=record):
                row = _row(Status="Closed", English_record=record)
                self.assertEqual(
                    ledger_problems(_table(row), closed_at_source=CLOSED), [problem]
                )

    def test_a_closed_row_not_closed_at_source_is_refused(self) -> None:
        # #496 gap (a), test (iv): all evidence cited while the source is Open.
        row = _row(Status="Closed", English_record=RECORD)
        self.assertEqual(
            ledger_problems(_table(row)),
            ["row 1: closed here but not closed at source"],
        )

    def test_a_changed_or_missing_source_digest_is_refused(self) -> None:
        # #496 Required outcome 2: the source digest the ledger cites is the pinned
        # witness; a source edit needs a reviewed change to both.
        text = LEDGER.read_text(encoding="utf-8")
        other = "0" * 64
        changed = text.replace(SOURCE_SHA256, other)
        self.assertNotEqual(changed, text)
        for markdown, cited in ((changed, [other]), ("No table here.\n", [])):
            with self.subTest(cited=cited):
                self.assertEqual(
                    source_witness_problems(markdown),
                    [
                        f"the ledger cites source digests {cited}; "
                        f"the pinned witness is {SOURCE_SHA256}"
                    ],
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

    def test_a_labelled_pilot_path_is_not_checked_against_the_tree(self) -> None:
        # Row 15: a pilot path is outside this repository by its label.
        reference = f"{PILOT_LABEL}: `publish-gate/prior_art_gate.py`"
        self.assertEqual(ledger_problems(_table(_row(Guard_reference=reference))), [])

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


class LedgerGuardPathTests(unittest.TestCase):
    """A live-repo guard cites only tracked regular files of this repository, every
    one of them (#496 item 1; the PAO's failure modes 1 to 6, #15 6836636966).
    The checkout here has no `.git`, so its tracked set is its packaged manifest."""

    maxDiff = None

    def setUp(self) -> None:
        self.parent = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = _repository(self.parent)

    def problems(self, reference: str) -> list[str]:
        row = _row(Guard_state="live-repo", Guard_reference=reference)
        return ledger_problems(_table(row), self.root)

    def assert_refused(self, cases: dict[str, str]) -> None:
        for path, reason in cases.items():
            with self.subTest(path=path):
                self.assertEqual(
                    self.problems(f"`{path}`"),
                    [f"row 1: live-repo guard path {path!r} {reason}"],
                )

    def test_a_tracked_regular_file_passes(self) -> None:
        self.assertEqual(self.problems("`tests/test_guard.py`"), [])

    def test_a_path_that_is_not_repository_relative_is_refused(self) -> None:
        # Failure modes 1 and 2: `root / "/abs"` drops the root, and `..` leaves it.
        reason = "is not repository-relative"
        self.assert_refused(
            {
                f"{self.root}/tests/test_guard.py": reason,
                "../outside.py": reason,
                "tests/../../outside.py": reason,
                "./tests/test_guard.py": reason,
                "tests/.git/config": reason,
            }
        )

    def test_a_directory_is_refused(self) -> None:
        # Failure mode 3: a directory stood in for a guard file.
        self.assert_refused(
            {
                "tests/": "is not repository-relative",
                "knowledge/failure-modes": "is not a tracked file",
                "tests/fixtures": "is not a regular file",
            }
        )

    def test_an_untracked_file_is_refused(self) -> None:
        # Failure mode 4: the check read the worktree, not the tracked set.
        self.assert_refused({"tests/untracked_guard.py": "is not a tracked file"})

    def test_a_symlink_is_refused(self) -> None:
        # Failure mode 5: exists() follows links, inside or outside the checkout.
        self.assert_refused(
            {
                "tests/linked_guard.py": "is not a regular file",
                "tests/external_guard.py": "is not a regular file",
                "guards/test_guard.py": "is reached through a symlink",
            }
        )

    def test_every_cited_path_counts(self) -> None:
        # Failure mode 6: one real path covered for a bogus one.
        self.assertEqual(
            self.problems("`tests/test_guard.py` and `tests/no_such_guard.py`"),
            [
                "row 1: live-repo guard path 'tests/no_such_guard.py' is not a tracked file"
            ],
        )

    def test_without_git_or_a_manifest_the_check_fails_closed(self) -> None:
        # Neither a Git index nor a packaged manifest: no path counts as tracked.
        (self.root / SOURCE_MANIFEST).unlink()
        self.assertEqual(
            self.problems("`tests/test_guard.py`"),
            [
                "the tracked set cannot be read (scope error: MANIFEST_MISSING)",
                "row 1: live-repo guard path 'tests/test_guard.py' is not a tracked file",
            ],
        )


if __name__ == "__main__":
    unittest.main()
