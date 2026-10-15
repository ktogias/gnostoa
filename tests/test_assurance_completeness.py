from __future__ import annotations

import io
import json
import os
import subprocess  # nosec B404 -- test-only: runs the command under a real pipe
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from tools import analyzer_readback, assurance_completeness, review_reconcile
from tools.review_policy import CHANGE_CLASSES

ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40
PREVIOUS = "b" * 40
SUBJECT = {
    "repository": "https://github.com/example/project",
    "change_request": {"kind": "github-pull-request", "id": "7"},
    "head_commit": HEAD,
}
DECLARATION = {
    "schema_version": "1.0",
    "id": "example.required-evidence",
    "version": "0.1.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The required checks ran on the exact head",
            "applies_to": ["normal", "critical"],
            "coverage": ["fast", "smoke"],
        },
        {
            "id": "analyzer-readback",
            "title": "Every analyzer read back the exact head",
            "applies_to": ["normal", "critical"],
            "coverage": ["analyzer-one", "analyzer-two"],
        },
        {
            "id": "sonarcloud",
            "title": "The quality gate and the issue inventory",
            "applies_to": ["normal", "critical"],
            "coverage": ["quality-gate", "issue-inventory"],
        },
    ],
}


def _receipt(
    requirement: str,
    coverage: list[str],
    *,
    status: str = "COMPLETE",
    head: str = HEAD,
    change: str = "7",
) -> dict[str, Any]:
    return {
        "schema": "gnostoa-evidence-receipt/v1",
        "requirement": requirement,
        "subject": {
            "repository": SUBJECT["repository"],
            "change_request": {"kind": "github-pull-request", "id": change},
            "head_commit": head,
        },
        "producer": f"{requirement}-producer",
        "observed_at": "2026-10-09T07:00:00Z",
        "status": status,
        "coverage": coverage,
    }


def _complete() -> list[dict[str, Any]]:
    return [
        _receipt("verification-checks", ["fast", "smoke"]),
        _receipt("analyzer-readback", ["analyzer-one", "analyzer-two"]),
        _receipt("sonarcloud", ["quality-gate", "issue-inventory"]),
    ]


def _evaluate(
    receipts: list[dict[str, Any]], *, change_class: str = "normal"
) -> dict[str, Any]:
    declaration = assurance_completeness.parse_declaration(DECLARATION)
    return assurance_completeness.evaluate(
        declaration, subject=SUBJECT, change_class=change_class, receipts=receipts
    )


def _items(verdict: dict[str, Any], requirement: str) -> dict[str, str]:
    [entry] = [r for r in verdict["requirements"] if r["id"] == requirement]
    return {item["item"]: item["status"] for item in entry["items"]}


class AssuranceCompletenessTests(unittest.TestCase):
    def test_every_item_complete_on_the_exact_head_is_complete(self) -> None:
        verdict = _evaluate(_complete())
        self.assertEqual("COMPLETE", verdict["status"])
        self.assertEqual(
            ["COMPLETE"] * 3, [r["status"] for r in verdict["requirements"]]
        )

    def test_an_analyzer_that_never_ran_is_missing(self) -> None:
        """#387: the readback never ran, so no receipt exists for it."""
        receipts = [r for r in _complete() if r["requirement"] != "analyzer-readback"]
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"analyzer-one": "MISSING", "analyzer-two": "MISSING"},
            _items(verdict, "analyzer-readback"),
        )

    def test_a_receipt_for_the_previous_head_is_stale(self) -> None:
        """#358: its only readback was bound to another head."""
        receipts = [r for r in _complete() if r["requirement"] != "analyzer-readback"]
        receipts.append(
            _receipt(
                "analyzer-readback", ["analyzer-one", "analyzer-two"], head=PREVIOUS
            )
        )
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"analyzer-one": "STALE", "analyzer-two": "STALE"},
            _items(verdict, "analyzer-readback"),
        )

    def test_a_green_gate_without_the_inventory_is_not_complete(self) -> None:
        """#359: SonarCloud's gate passed while 29 issues were open."""
        receipts = [r for r in _complete() if r["requirement"] != "sonarcloud"]
        receipts.append(_receipt("sonarcloud", ["quality-gate"]))
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"quality-gate": "COMPLETE", "issue-inventory": "MISSING"},
            _items(verdict, "sonarcloud"),
        )

    def test_a_green_check_does_not_stand_in_for_an_absent_receipt(self) -> None:
        """#294: the publication job succeeded without publishing. A complete
        receipt for one requirement says nothing about another."""
        receipts = [
            _receipt("verification-checks", ["fast", "smoke"]),
            _receipt("verification-checks", ["analyzer-one", "analyzer-two"]),
            _receipt("sonarcloud", ["quality-gate", "issue-inventory"]),
        ]
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"analyzer-one": "MISSING", "analyzer-two": "MISSING"},
            _items(verdict, "analyzer-readback"),
        )

    def test_a_skipped_required_check_is_not_executed(self) -> None:
        """#202: a required test that was skipped did not run."""
        receipts = [r for r in _complete() if r["requirement"] != "verification-checks"]
        receipts += [
            _receipt("verification-checks", ["fast"]),
            _receipt("verification-checks", ["smoke"], status="SKIPPED"),
        ]
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"fast": "COMPLETE", "smoke": "SKIPPED"},
            _items(verdict, "verification-checks"),
        )

    def test_executed_scope_smaller_than_configured_is_incomplete(self) -> None:
        """#262/#221: the declared scope exceeded the enforced one. A producer
        that reports COMPLETE over less than the declared coverage covers less."""
        receipts = [r for r in _complete() if r["requirement"] != "analyzer-readback"]
        receipts.append(_receipt("analyzer-readback", ["analyzer-one"]))
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"analyzer-one": "COMPLETE", "analyzer-two": "MISSING"},
            _items(verdict, "analyzer-readback"),
        )

    def test_every_status_but_complete_fails_closed(self) -> None:
        for status in sorted(assurance_completeness.RECEIPT_STATUSES - {"COMPLETE"}):
            with self.subTest(status=status):
                receipts = [r for r in _complete() if r["requirement"] != "sonarcloud"]
                receipts.append(
                    _receipt(
                        "sonarcloud",
                        ["quality-gate", "issue-inventory"],
                        status=status,
                    )
                )
                verdict = _evaluate(receipts)
                self.assertEqual("INCOMPLETE", verdict["status"])
                self.assertEqual(
                    {"quality-gate": status, "issue-inventory": status},
                    _items(verdict, "sonarcloud"),
                )

    def test_disagreeing_receipts_fail_closed_at_the_worse_status(self) -> None:
        receipts = _complete()
        receipts.append(_receipt("analyzer-readback", ["analyzer-two"], status="ERROR"))
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"analyzer-one": "COMPLETE", "analyzer-two": "ERROR"},
            _items(verdict, "analyzer-readback"),
        )

    def test_a_current_receipt_outranks_a_stale_one(self) -> None:
        receipts = _complete()
        receipts.append(
            _receipt(
                "analyzer-readback",
                ["analyzer-one", "analyzer-two"],
                status="ERROR",
                head=PREVIOUS,
            )
        )
        self.assertEqual("COMPLETE", _evaluate(receipts)["status"])

    def test_receipts_for_another_change_are_ignored_and_counted(self) -> None:
        receipts = [r for r in _complete() if r["requirement"] != "sonarcloud"]
        receipts.append(
            _receipt("sonarcloud", ["quality-gate", "issue-inventory"], change="8")
        )
        verdict = _evaluate(receipts)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(
            {"quality-gate": "MISSING", "issue-inventory": "MISSING"},
            _items(verdict, "sonarcloud"),
        )
        self.assertEqual(1, verdict["ignored_receipts"])

    def test_receipts_for_an_undeclared_requirement_are_ignored_and_counted(
        self,
    ) -> None:
        receipts = _complete()
        receipts.append(_receipt("undeclared", ["anything"]))
        verdict = _evaluate(receipts)
        self.assertEqual("COMPLETE", verdict["status"])
        self.assertEqual(1, verdict["ignored_receipts"])

    def test_no_applicable_requirement_is_incomplete(self) -> None:
        verdict = _evaluate(_complete(), change_class="mechanical")
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual([], verdict["requirements"])
        self.assertEqual(
            ["no requirement applies to change class 'mechanical'"],
            verdict["reasons"],
        )

    def test_only_requirements_for_the_class_apply(self) -> None:
        document = json.loads(json.dumps(DECLARATION))
        document["requirements"][2]["applies_to"] = ["critical"]
        declaration = assurance_completeness.parse_declaration(document)
        receipts = [r for r in _complete() if r["requirement"] != "sonarcloud"]
        normal = assurance_completeness.evaluate(
            declaration, subject=SUBJECT, change_class="normal", receipts=receipts
        )
        critical = assurance_completeness.evaluate(
            declaration, subject=SUBJECT, change_class="critical", receipts=receipts
        )
        self.assertEqual("COMPLETE", normal["status"])
        self.assertEqual("INCOMPLETE", critical["status"])

    def test_the_verdict_names_its_subject_and_declaration_and_nothing_more(
        self,
    ) -> None:
        """The verdict is evidence for a consumer, not an approval: it carries no
        authority field."""
        verdict = _evaluate(_complete())
        self.assertEqual(
            {
                "schema",
                "status",
                "subject",
                "change_class",
                "declaration",
                "requirements",
                "reasons",
                "ignored_receipts",
            },
            set(verdict),
        )
        self.assertEqual("gnostoa-assurance-completeness/v1", verdict["schema"])
        self.assertEqual(SUBJECT, verdict["subject"])
        self.assertEqual(
            {"id": "example.required-evidence", "version": "0.1.0"},
            verdict["declaration"],
        )

    def test_receipt_statuses_reuse_the_existing_coverage_vocabularies(self) -> None:
        """Decision 0086's and 0091's coverage statuses, plus #389's SKIPPED; the
        reducer derives MISSING and STALE itself."""
        # The two owners' vocabularies, related exactly, so neither can drift from
        # the other unnoticed (Claude on #408).
        self.assertEqual(
            review_reconcile.L1_COVERAGE_STATUSES | {"INCOMPLETE"},
            analyzer_readback.COVERAGE_STATUSES,
        )
        self.assertLessEqual(
            analyzer_readback.COVERAGE_STATUSES,
            assurance_completeness.RECEIPT_STATUSES,
        )
        self.assertEqual(
            analyzer_readback.COVERAGE_STATUSES | {"SKIPPED"},
            assurance_completeness.RECEIPT_STATUSES,
        )
        self.assertEqual(
            frozenset({"MISSING", "STALE"}), assurance_completeness.DERIVED_STATUSES
        )
        self.assertFalse(
            assurance_completeness.RECEIPT_STATUSES
            & assurance_completeness.DERIVED_STATUSES
        )


def _with(**changes: object) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(json.dumps(DECLARATION))
    document["requirements"][0].update(changes)
    return document


class DeclarationTests(unittest.TestCase):
    def _rejects(self, document: object, message: str) -> None:
        with self.assertRaisesRegex(
            assurance_completeness.AssuranceCompletenessError, message
        ):
            assurance_completeness.parse_declaration(document)

    def test_a_valid_declaration_parses(self) -> None:
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        self.assertEqual("example.required-evidence", declaration["id"])

    def test_the_schema_version_is_closed(self) -> None:
        document = dict(DECLARATION, schema_version="2.0")
        self._rejects(document, "schema_version")

    def test_unknown_keys_are_refused(self) -> None:
        self._rejects(dict(DECLARATION, extra=True), "unknown key")
        self._rejects(_with(optional=True), "unknown key")

    def test_requirement_ids_are_unique(self) -> None:
        document = json.loads(json.dumps(DECLARATION))
        document["requirements"][1]["id"] = "verification-checks"
        self._rejects(document, "duplicate requirement")

    def test_classes_are_known_and_unique(self) -> None:
        self._rejects(_with(applies_to=["routine"]), "change class")
        self._rejects(_with(applies_to=["normal", "normal"]), "duplicate")
        self._rejects(_with(applies_to=[]), "applies_to")

    def test_coverage_items_are_unique_and_present(self) -> None:
        self._rejects(_with(coverage=[]), "coverage")
        self._rejects(_with(coverage=["fast", "fast"]), "duplicate")
        self._rejects(_with(coverage=[""]), "coverage")

    def test_at_least_one_requirement(self) -> None:
        self._rejects(dict(DECLARATION, requirements=[]), "requirements")

    def test_the_file_loader_refuses_duplicate_and_merge_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "declaration.yaml"
            for text in (
                'schema_version: "1.0"\nschema_version: "1.0"\n',
                "base: &b {id: x}\nother:\n  <<: *b\n",
            ):
                with self.subTest(text=text):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(
                        assurance_completeness.AssuranceCompletenessError
                    ):
                        assurance_completeness.load_declaration(path, project_root=root)

    def test_the_declaration_must_lie_inside_the_project_root(self) -> None:
        """SonarCloud S8707 on #408: a declaration path from the command line is
        confined to the project the declaration belongs to."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            outside = Path(directory) / "declaration.yaml"
            outside.write_text(json.dumps(DECLARATION), encoding="utf-8")
            (root / "link.yaml").symlink_to(outside)
            for path in (outside, root / ".." / "declaration.yaml", root / "link.yaml"):
                with (
                    self.subTest(path=path),
                    self.assertRaisesRegex(
                        assurance_completeness.AssuranceCompletenessError,
                        "outside the project root",
                    ),
                ):
                    assurance_completeness.load_declaration(path, project_root=root)

    def test_keys_that_are_not_strings_are_refused(self) -> None:
        """Codex and CodeAnt on #408: an integer key beside an unknown string key
        made the sort of unknown keys raise TypeError."""
        mixed: dict[Any, Any] = {1: "one", "extra": True, **DECLARATION}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "declaration.yaml"
            path.write_text(
                yaml.safe_dump(mixed, sort_keys=False),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                assurance_completeness.AssuranceCompletenessError, "not a string"
            ):
                assurance_completeness.load_declaration(path, project_root=root)
        self._rejects(mixed, "not a string")

    def test_a_declaration_that_cannot_be_resolved_is_refused(self) -> None:
        """Codex and CodeAnt on #408: a symbolic-link loop made resolve() raise."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.yaml").symlink_to(root / "b.yaml")
            (root / "b.yaml").symlink_to(root / "a.yaml")
            with self.assertRaisesRegex(
                assurance_completeness.AssuranceCompletenessError, "cannot resolve"
            ):
                assurance_completeness.load_declaration(
                    root / "a.yaml", project_root=root
                )


class ReceiptTests(unittest.TestCase):
    def test_a_malformed_receipt_is_refused_not_ignored(self) -> None:
        changes: tuple[dict[str, object], ...] = (
            {"schema": "other/v1"},
            {"status": "CLEAN"},
            {"status": "MISSING"},
            {"coverage": []},
            {"head_commit": "abc"},
            {"extra": 1},
        )
        for change in changes:
            with self.subTest(change=change):
                receipt = _receipt("sonarcloud", ["quality-gate"])
                if "head_commit" in change:
                    receipt["subject"]["head_commit"] = change["head_commit"]
                else:
                    receipt.update(change)
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    _evaluate([receipt])

    def test_an_unknown_change_class_is_refused(self) -> None:
        receipts = _complete()
        with self.assertRaisesRegex(
            assurance_completeness.AssuranceCompletenessError, "change class"
        ):
            _evaluate(receipts, change_class="routine")

    def test_unhashable_values_are_refused_not_crashed_on(self) -> None:
        """Codex, Sourcery and CodeAnt on #408: a JSON array or object where a
        string belongs raised TypeError on the set membership."""
        declaration = assurance_completeness.parse_declaration(DECLARATION)
        for value in ([], {}, ["normal"], {"normal": True}):
            with (
                self.subTest(change_class=value),
                self.assertRaisesRegex(
                    assurance_completeness.AssuranceCompletenessError, "change class"
                ),
            ):
                assurance_completeness.evaluate(
                    declaration, subject=SUBJECT, change_class=value, receipts=[]
                )
            with self.subTest(status=value):
                receipt = _receipt("sonarcloud", ["quality-gate"])
                receipt["status"] = value
                with self.assertRaisesRegex(
                    assurance_completeness.AssuranceCompletenessError, "status"
                ):
                    _evaluate([receipt])
        for value in ([], {}):
            document = _with(applies_to=[value])
            with (
                self.subTest(applies_to=value),
                self.assertRaises(assurance_completeness.AssuranceCompletenessError),
            ):
                assurance_completeness.parse_declaration(document)


def _run(text: str | bytes, declaration: object | None = None) -> tuple[int, str]:
    """Run the command in a scratch project, with `text` on standard input."""

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "policy").mkdir()
        (root / "policy" / "assurance-evidence.yaml").write_text(
            json.dumps(DECLARATION if declaration is None else declaration),
            encoding="utf-8",
        )
        raw = text if isinstance(text, bytes) else text.encode("utf-8")
        stdin = io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdin", stdin), redirect_stdout(out), redirect_stderr(err):
            code = assurance_completeness.main(["--project-root", str(root)])
        return code, out.getvalue() + err.getvalue()


def _payload(receipts: list[dict[str, Any]]) -> str:
    return json.dumps(
        {"subject": SUBJECT, "change_class": "normal", "receipts": receipts}
    )


class CommandTests(unittest.TestCase):
    def test_complete_exits_zero_with_the_verdict(self) -> None:
        code, output = _run(_payload(_complete()))
        self.assertEqual(0, code)
        self.assertEqual("COMPLETE", json.loads(output)["status"])

    def test_incomplete_exits_one_with_the_verdict(self) -> None:
        code, output = _run(_payload(_complete()[:1]))
        self.assertEqual(1, code)
        self.assertEqual("INCOMPLETE", json.loads(output)["status"])

    def test_invalid_input_exits_two(self) -> None:
        for text in (
            json.dumps({"subject": SUBJECT, "change_class": "normal"}),
            _payload([{"schema": "other/v1"}]),
            "[]",
            "not json",
        ):
            with self.subTest(text=text):
                code, _ = _run(text)
                self.assertEqual(2, code)
        code, _ = _run(_payload(_complete()), declaration={"id": "x"})
        self.assertEqual(2, code)

    def test_a_repeated_json_field_is_refused(self) -> None:
        """Sourcery and CodeAnt on #408: JSON keeps the last of a repeated field,
        so a receipt saying both ERROR and COMPLETE was read as COMPLETE."""
        receipts = _complete()
        text = _payload(receipts).replace(
            '"status": "COMPLETE"', '"status": "ERROR", "status": "COMPLETE"', 1
        )
        code, output = _run(text)
        self.assertEqual(2, code)
        self.assertIn("repeats JSON object field 'status'", output)

    def test_a_non_finite_number_is_refused(self) -> None:
        code, output = _run(_payload(_complete())[:-1] + ', "extra": NaN}')
        self.assertEqual(2, code)
        self.assertIn("non-finite", output)

    def test_input_that_is_not_utf_8_exits_two(self) -> None:
        """cubic on #408: the harness only ever supplied UTF-8."""
        code, output = _run(b'{"subject": "\xff"}')
        self.assertEqual(2, code)
        self.assertIn("not valid JSON", output)

    def test_input_over_the_bound_exits_two_unread(self) -> None:
        """cubic on #408: no test crossed the input bound. Valid JSON one byte
        over it is refused before decoding."""
        padding = assurance_completeness.MAX_INPUT_BYTES - len(_payload(_complete()))
        text = _payload(_complete())[:-1] + ', "pad": "' + "x" * padding + '"}'
        self.assertGreater(
            len(text.encode("utf-8")), assurance_completeness.MAX_INPUT_BYTES
        )
        code, output = _run(text)
        self.assertEqual(2, code)
        self.assertIn("larger than the", output)

    def test_a_failed_read_of_standard_input_exits_two(self) -> None:
        """cubic on #408: a read error escaped as a traceback with exit 1, the
        code that means INCOMPLETE."""

        class _Unreadable:
            @staticmethod
            def read(_size: int = -1) -> bytes:
                raise OSError("input/output error")

        class _Stdin:
            buffer = _Unreadable()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy").mkdir()
            (root / "policy" / "assurance-evidence.yaml").write_text(
                json.dumps(DECLARATION), encoding="utf-8"
            )
            err = io.StringIO()
            with patch("sys.stdin", _Stdin()), redirect_stderr(err):
                code = assurance_completeness.main(["--project-root", str(root)])
        self.assertEqual(2, code)
        self.assertIn("cannot read the input", err.getvalue())

    def test_no_failure_exits_as_a_verdict_would(self) -> None:
        """Four rounds on #408 found an exception that escaped with Python's exit
        1, the code that means INCOMPLETE. Whatever fails inside the command, it
        exits 2 and names the failure."""
        for error in (TypeError("t"), RuntimeError("r"), KeyError("k"), OSError("o")):
            with (
                self.subTest(error=type(error).__name__),
                patch.object(assurance_completeness, "evaluate", side_effect=error),
            ):
                code, output = _run(_payload(_complete()))
                self.assertEqual(2, code)
                self.assertIn(type(error).__name__, output)

    def test_a_failed_write_of_the_verdict_exits_two(self) -> None:
        """cubic on #408: the verdict was written after the guarded block, so a
        broken pipe escaped with exit 1, the code that means INCOMPLETE."""

        class _Closed(io.StringIO):
            def write(self, _text: str) -> int:
                raise BrokenPipeError("broken pipe")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy").mkdir()
            (root / "policy" / "assurance-evidence.yaml").write_text(
                json.dumps(DECLARATION), encoding="utf-8"
            )
            stdin = io.TextIOWrapper(
                io.BytesIO(_payload(_complete()).encode("utf-8")), encoding="utf-8"
            )
            err = io.StringIO()
            with (
                patch("sys.stdin", stdin),
                patch("sys.stdout", _Closed()),
                redirect_stderr(err),
            ):
                code = assurance_completeness.main(["--project-root", str(root)])
        self.assertEqual(2, code)
        self.assertIn("BrokenPipeError", err.getvalue())

    def test_a_closed_pipe_exits_two(self) -> None:
        """Claude on #408: on a pipe, stdout is block-buffered, so `print` returns
        and the write fails in the flush at shutdown, after `main` has returned:
        Python then exits 120. Run for real, with stdout a pipe whose reader has
        already gone."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policy").mkdir()
            (root / "policy" / "assurance-evidence.yaml").write_text(
                json.dumps(DECLARATION), encoding="utf-8"
            )
            reader, writer = os.pipe()
            os.close(reader)
            environment = {
                key: value
                for key, value in os.environ.items()
                if key != "PYTHONUNBUFFERED"
            }
            environment["PYTHONPATH"] = str(ROOT)
            # The suppressions below are for a fixed argument list: the interpreter
            # running this test, on this repository's own command.
            try:
                completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                    [
                        sys.executable,
                        "-m",
                        "tools.cli",
                        "assurance-check",
                        "--project-root",
                        str(root),
                    ],
                    input=_payload(_complete()).encode("utf-8"),
                    stdout=writer,
                    stderr=subprocess.PIPE,
                    env=environment,
                    check=False,
                    timeout=60,
                )
            finally:
                os.close(writer)
        self.assertEqual(2, completed.returncode, completed.stderr.decode())

    def test_an_input_nested_past_the_bound_exits_two(self) -> None:
        """Claude on #408: the input was decoded strictly but not bounded in depth,
        where review-check bounds the same decoder's result at 64 levels."""
        receipts = _complete()
        nested: dict[str, Any] = {}
        for _ in range(100):
            nested = {"next": nested}
        receipts[0]["provenance"] = nested
        code, output = _run(_payload(receipts))
        self.assertEqual(2, code)
        self.assertIn("nests deeper than the 64-level operational bound", output)

    def test_unhashable_input_exits_two_without_a_traceback(self) -> None:
        text = json.dumps(
            {"subject": SUBJECT, "change_class": ["normal"], "receipts": []}
        )
        code, output = _run(text)
        self.assertEqual(2, code)
        self.assertNotIn("Traceback", output)

    def test_the_knowledge_cli_routes_assurance_check(self) -> None:
        from tools import cli

        self.assertIs(assurance_completeness.main, cli.COMMANDS["assurance-check"][1])


class GnostoaDeclarationTests(unittest.TestCase):
    def test_gnostoa_declares_the_merge_evidence_for_every_merging_class(
        self,
    ) -> None:
        declaration = assurance_completeness.load_declaration(
            ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
        )
        requirements = {r["id"]: r for r in declaration["requirements"]}
        self.assertEqual(
            {"verification-checks", "codeql", "analyzer-readback", "sonarcloud"},
            set(requirements),
        )
        merging = sorted(CHANGE_CLASSES - {"emergency"})
        for requirement in requirements.values():
            with self.subTest(requirement=requirement["id"]):
                self.assertEqual(merging, sorted(requirement["applies_to"]))
        # Every requirement's items, so none can drift to another name (cubic on
        # #408); the verification checks are bound to R-main in the merge-gate test.
        self.assertEqual(["codeql"], requirements["codeql"]["coverage"])
        self.assertEqual(
            ["deepsource-diff", "deepsource-full", "codacy"],
            requirements["analyzer-readback"]["coverage"],
        )
        self.assertEqual(
            ["quality-gate", "issue-inventory"],
            requirements["sonarcloud"]["coverage"],
        )


# Gnostoa's declaration at main 935ea6c: a guard that no later form of it changes
# a verdict before a substitute is qualified (#389, the owner's admission 6157791244).
GNOSTOA_1_0: dict[str, Any] = {
    "schema_version": "1.0",
    "id": "gnostoa.required-evidence",
    "version": "0.1.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The status checks R-main requires ran on the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["policy", "fast", "regression", "smoke"],
        },
        {
            "id": "codeql",
            "title": "CodeQL analysed the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["codeql"],
        },
        {
            "id": "analyzer-readback",
            "title": "The authenticated analyzer readback is bound to the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["deepsource-diff", "deepsource-full", "codacy"],
        },
        {
            "id": "sonarcloud",
            "title": "SonarCloud's quality gate and its issue inventory",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["quality-gate", "issue-inventory"],
        },
    ],
}
MERGING_CLASSES = sorted(CHANGE_CLASSES - {"emergency"})


def _gnostoa_receipts(down: dict[tuple[str, str], str]) -> list[dict[str, Any]]:
    """One receipt per item of Gnostoa's declaration, complete unless `down`
    gives its status."""

    return [
        _receipt(
            requirement["id"],
            [item],
            status=down.get((requirement["id"], item), "COMPLETE"),
        )
        for requirement in GNOSTOA_1_0["requirements"]
        for item in requirement["coverage"]
    ]


class MissingVendorCharacterizationTests(unittest.TestCase):
    """Today's truthful hold when a vendor cannot analyse (#430 at a88f057, #389
    6157776894): green before #389 F1 and after it."""

    def test_today_a_vendor_that_cannot_analyse_holds_gnostoa(self) -> None:
        """#430: DeepSource's quota was exhausted, both of its readbacks were
        INCOMPLETE, and every other item was complete."""
        declaration = assurance_completeness.load_declaration(
            ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
        )
        down = {
            ("analyzer-readback", "deepsource-diff"): "INCOMPLETE",
            ("analyzer-readback", "deepsource-full"): "INCOMPLETE",
        }
        for change_class in MERGING_CLASSES:
            with self.subTest(change_class=change_class):
                verdict = assurance_completeness.evaluate(
                    declaration,
                    subject=SUBJECT,
                    change_class=change_class,
                    receipts=_gnostoa_receipts(down),
                )
                self.assertEqual("INCOMPLETE", verdict["status"])
                self.assertEqual(
                    {
                        "deepsource-diff": "INCOMPLETE",
                        "deepsource-full": "INCOMPLETE",
                        "codacy": "COMPLETE",
                    },
                    _items(verdict, "analyzer-readback"),
                )

    def test_a_1_0_declaration_holds_whenever_a_declared_item_is_not_complete(
        self,
    ) -> None:
        """Under 1.0 every declared item is required, so no other evidence can
        stand for one that is not complete: the only route past an unavailable
        vendor would be deleting its item, which erases its status (#389
        6157776894, section 2)."""
        declared: dict[str, Any] = DECLARATION
        items = [
            (requirement["id"], item)
            for requirement in declared["requirements"]
            for item in requirement["coverage"]
        ]
        wrong = []
        for mask in range(2 ** len(items)):
            down = {pair for index, pair in enumerate(items) if mask >> index & 1}
            receipts = [
                _receipt(r, [i], status="UNAVAILABLE" if (r, i) in down else "COMPLETE")
                for r, i in items
            ]
            expected = "INCOMPLETE" if down else "COMPLETE"
            if _evaluate(receipts)["status"] != expected:
                wrong.append(sorted(down))
        self.assertEqual([], wrong)

    def test_claims_belong_to_schema_1_1_only(self) -> None:
        """A 1.0 declaration keeps its closed form (#389 F1 versions the change)."""
        document = dict(DECLARATION, claims=[])
        with self.assertRaisesRegex(
            assurance_completeness.AssuranceCompletenessError, "unknown key"
        ):
            assurance_completeness.parse_declaration(document)
        document = _with(domains={"fast": "ci", "smoke": "ci"})
        with self.assertRaisesRegex(
            assurance_completeness.AssuranceCompletenessError, "unknown key"
        ):
            assurance_completeness.parse_declaration(document)

    def test_a_1_0_verdict_keeps_its_schema(self) -> None:
        """R6: a 1.0 declaration's verdict is unchanged by #389 F1, in its schema
        and in the order of its keys, its requirements and their items, as at main
        2f63cf3. The other tests compare its values."""
        declared: dict[str, Any] = DECLARATION
        verdict = _evaluate(_complete())
        self.assertEqual("gnostoa-assurance-completeness/v1", verdict["schema"])
        self.assertNotIn("claims", verdict)
        self.assertEqual(
            [
                "schema",
                "status",
                "subject",
                "change_class",
                "declaration",
                "requirements",
                "reasons",
                "ignored_receipts",
            ],
            list(verdict),
        )
        self.assertEqual(
            [requirement["id"] for requirement in declared["requirements"]],
            [requirement["id"] for requirement in verdict["requirements"]],
        )
        for requirement, declared_requirement in zip(
            verdict["requirements"], declared["requirements"], strict=True
        ):
            with self.subTest(requirement=requirement["id"]):
                self.assertEqual(["id", "status", "items"], list(requirement))
                self.assertEqual(
                    declared_requirement["coverage"],
                    [entry["item"] for entry in requirement["items"]],
                )
                for entry in requirement["items"]:
                    self.assertEqual(["item", "status"], list(entry))

    def test_a_receipt_cannot_name_its_own_domain_or_claim(self) -> None:
        """R6, R9: domains and claims come only from the protected declaration."""
        for key in ("domain", "claim", "independent_domains"):
            with self.subTest(key=key):
                receipt = {**_receipt("analyzer-readback", ["analyzer-one"]), key: "x"}
                with self.assertRaisesRegex(
                    assurance_completeness.AssuranceCompletenessError, "unknown key"
                ):
                    _evaluate([receipt])

    def test_gnostoa_s_declaration_keeps_its_935ea6c_verdict_for_every_status(
        self,
    ) -> None:
        """Over every combination of complete and unavailable items, for every
        merging class, Gnostoa's declaration gives the verdict status its 1.0
        form gave at main 935ea6c. Only the status is compared: this is the guard
        F2's migration must keep green (the Router's disposition, #389
        6158642620). F1 leaves that declaration's bytes unchanged, and the other
        1.0 tests pin the rest of the verdict."""
        baseline = assurance_completeness.parse_declaration(GNOSTOA_1_0)
        current = assurance_completeness.load_declaration(
            ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
        )
        items = [
            (requirement["id"], item)
            for requirement in GNOSTOA_1_0["requirements"]
            for item in requirement["coverage"]
        ]
        wrong = []
        for mask in range(2 ** len(items)):
            down = {
                pair: "UNAVAILABLE"
                for index, pair in enumerate(items)
                if mask >> index & 1
            }
            receipts = _gnostoa_receipts(down)
            for change_class in MERGING_CLASSES:
                verdicts = [
                    assurance_completeness.evaluate(
                        declaration,
                        subject=SUBJECT,
                        change_class=change_class,
                        receipts=receipts,
                    )["status"]
                    for declaration in (baseline, current)
                ]
                if verdicts[0] != verdicts[1]:
                    wrong.append((change_class, sorted(down), verdicts))
        self.assertEqual([], wrong)


# #389 F1's claims (the owner's admission 6157791244): a 1.1 declaration gives
# each item its failure domain and names the claims a change class requires, each
# supported by any of its prequalified items and counted by distinct domain. The
# cases trace the RCA's R1-R12 (6157776894). Vendors A, B and C are a test-only
# qualification, never a live certification.
CLAIMS_DECLARATION: dict[str, Any] = {
    "schema_version": "1.1",
    "id": "example.required-evidence",
    "version": "0.2.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The required checks ran on the exact head",
            "applies_to": ["normal", "critical"],
            "coverage": ["fast", "smoke"],
            "domains": {"fast": "ci", "smoke": "ci"},
        },
        {
            "id": "analyzer-readback",
            "title": "Every analyzer read back the exact head",
            "applies_to": ["normal", "critical"],
            "coverage": ["vendor-a-diff", "vendor-a-full", "vendor-b"],
            "domains": {
                "vendor-a-diff": "vendor-a",
                "vendor-a-full": "vendor-a",
                "vendor-b": "vendor-b",
            },
        },
        {
            "id": "second-inventory",
            "title": "Another vendor's issue inventory",
            "applies_to": ["normal", "critical"],
            "coverage": ["vendor-c"],
            "domains": {"vendor-c": "vendor-c"},
        },
    ],
    "claims": [
        {
            "id": "fast-tests",
            "title": "The fast tests ran",
            "evidence": [{"requirement": "verification-checks", "item": "fast"}],
            "independent_domains": {"normal": 1, "critical": 1},
        },
        {
            "id": "smoke-tests",
            "title": "The smoke tests ran",
            "evidence": [{"requirement": "verification-checks", "item": "smoke"}],
            "independent_domains": {"normal": 1, "critical": 1},
        },
        {
            "id": "diff-findings",
            "title": "Every finding in the changed lines is known",
            "evidence": [
                {"requirement": "analyzer-readback", "item": "vendor-a-diff"},
                {"requirement": "second-inventory", "item": "vendor-c"},
            ],
            "independent_domains": {"normal": 1, "critical": 2},
        },
        {
            "id": "full-findings",
            "title": "Every finding in the exact head's analysis is known",
            "evidence": [
                {"requirement": "analyzer-readback", "item": "vendor-a-full"},
                {"requirement": "analyzer-readback", "item": "vendor-b"},
                {"requirement": "second-inventory", "item": "vendor-c"},
            ],
            "independent_domains": {"normal": 2, "critical": 3},
        },
    ],
}
VENDOR_A_DOWN = {"vendor-a-diff": "UNAVAILABLE", "vendor-a-full": "UNAVAILABLE"}


def _claims_document() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(json.dumps(CLAIMS_DECLARATION))
    return document


def _claim_receipts(down: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """One receipt per item on the exact head, complete unless `down` gives its
    status."""

    statuses = down or {}
    return [
        _receipt(requirement["id"], [item], status=statuses.get(item, "COMPLETE"))
        for requirement in CLAIMS_DECLARATION["requirements"]
        for item in requirement["coverage"]
    ]


def _evaluate_claims(
    receipts: list[dict[str, Any]],
    *,
    change_class: str = "normal",
    document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    declaration = assurance_completeness.parse_declaration(
        CLAIMS_DECLARATION if document is None else document
    )
    return assurance_completeness.evaluate(
        declaration, subject=SUBJECT, change_class=change_class, receipts=receipts
    )


def _claim(verdict: dict[str, Any], claim: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = [c for c in verdict["claims"] if c["id"] == claim]
    [entry] = entries
    return entry


class ClaimPolicyTests(unittest.TestCase):
    def test_r1_a_qualified_substitute_covers_an_unavailable_vendor(self) -> None:
        """R1: vendor A's quota is exhausted on a normal head and prequalified
        independent evidence supports every claim: the verdict is COMPLETE, and
        vendor A stays UNAVAILABLE in it, never clean."""
        verdict = _evaluate_claims(_claim_receipts(VENDOR_A_DOWN))
        self.assertEqual("COMPLETE", verdict["status"])
        self.assertEqual("gnostoa-assurance-completeness/v2", verdict["schema"])
        self.assertEqual(
            {
                "vendor-a-diff": "UNAVAILABLE",
                "vendor-a-full": "UNAVAILABLE",
                "vendor-b": "COMPLETE",
            },
            _items(verdict, "analyzer-readback"),
        )
        self.assertEqual(
            [
                {
                    "requirement": "analyzer-readback",
                    "item": "vendor-a-diff",
                    "status": "UNAVAILABLE",
                },
                {
                    "requirement": "analyzer-readback",
                    "item": "vendor-a-full",
                    "status": "UNAVAILABLE",
                },
            ],
            verdict["degraded"],
        )
        self.assertEqual(["vendor-c"], _claim(verdict, "diff-findings")["domains"])
        self.assertEqual(
            ["vendor-b", "vendor-c"], _claim(verdict, "full-findings")["domains"]
        )

    def test_r1_without_a_qualified_substitute_the_same_receipts_deny(self) -> None:
        """R1's converse: where the protected declaration qualifies no
        substitute, the vendor's absence still holds the change."""
        document = _claims_document()
        document["claims"][2]["evidence"] = [
            {"requirement": "analyzer-readback", "item": "vendor-a-diff"}
        ]
        document["claims"][2]["independent_domains"] = {"normal": 1, "critical": 1}
        verdict = _evaluate_claims(_claim_receipts(VENDOR_A_DOWN), document=document)
        self.assertEqual("INCOMPLETE", verdict["status"])
        claim = _claim(verdict, "diff-findings")
        self.assertEqual(
            ("INCOMPLETE", 1, []),
            (claim["status"], claim["required_domains"], claim["domains"]),
        )
        self.assertEqual(
            [
                "claim 'diff-findings' is supported by 0 of the 1 independent "
                "domains it requires"
            ],
            verdict["reasons"],
        )

    def test_r2_one_vendor_s_two_reads_are_one_domain(self) -> None:
        """R2: vendor A's diff and full reads are both complete, but they are one
        failure domain, never a two-vendor quorum."""
        document = _claims_document()
        document["claims"][3]["evidence"].insert(
            0, {"requirement": "analyzer-readback", "item": "vendor-a-diff"}
        )
        down = {"vendor-b": "UNAVAILABLE", "vendor-c": "UNAVAILABLE"}
        verdict = _evaluate_claims(_claim_receipts(down), document=document)
        self.assertEqual("INCOMPLETE", verdict["status"])
        claim = _claim(verdict, "full-findings")
        self.assertEqual(
            (2, ["vendor-a"]), (claim["required_domains"], claim["domains"])
        )

    def test_r3_a_critical_change_needs_its_independent_domains(self) -> None:
        """R3: a critical change's diff claim needs two independent domains, and
        clean receipts for an undeclared reviewer requirement are ignored."""
        receipts = [
            *_claim_receipts(VENDOR_A_DOWN),
            _receipt("agent-review", ["reviewer-one"]),
            _receipt("agent-review", ["reviewer-two"]),
        ]
        verdict = _evaluate_claims(receipts, change_class="critical")
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(2, verdict["ignored_receipts"])
        claim = _claim(verdict, "diff-findings")
        self.assertEqual(
            (2, ["vendor-c"]), (claim["required_domains"], claim["domains"])
        )

    def test_r4_only_a_complete_current_receipt_supports_a_claim(self) -> None:
        """R4: a substitute that skipped, ran partially, was rate limited, read
        another head or belongs to another change supports nothing."""
        base = [
            r for r in _claim_receipts(VENDOR_A_DOWN) if r["coverage"] != ["vendor-c"]
        ]
        substitutes = {
            status: _receipt("second-inventory", ["vendor-c"], status=status)
            for status in sorted(assurance_completeness.RECEIPT_STATUSES - {"COMPLETE"})
        }
        substitutes["another head"] = _receipt(
            "second-inventory", ["vendor-c"], head=PREVIOUS
        )
        substitutes["another change"] = _receipt(
            "second-inventory", ["vendor-c"], change="8"
        )
        for label, substitute in substitutes.items():
            with self.subTest(substitute=label):
                verdict = _evaluate_claims([*base, substitute])
                self.assertEqual("INCOMPLETE", verdict["status"])
                self.assertEqual([], _claim(verdict, "diff-findings")["domains"])

    def test_every_item_that_is_not_complete_is_listed_as_degraded(self) -> None:
        """R4, R12: the degraded list names each applicable item that is not
        complete, with its own status, whatever that status is."""
        receipts = [
            r
            for r in _claim_receipts()
            if r["coverage"] not in (["vendor-a-diff"], ["vendor-c"])
        ]
        receipts.append(_receipt("second-inventory", ["vendor-c"], status="PARTIAL"))
        verdict = _evaluate_claims(receipts)
        self.assertEqual(
            [
                {
                    "requirement": "analyzer-readback",
                    "item": "vendor-a-diff",
                    "status": "MISSING",
                },
                {
                    "requirement": "second-inventory",
                    "item": "vendor-c",
                    "status": "PARTIAL",
                },
            ],
            verdict["degraded"],
        )

    def test_r9_items_that_share_a_domain_count_once(self) -> None:
        """R9: vendor B's inventory shares vendor C's backend, so the protected
        declaration gives both one domain, and together they count once."""
        document = _claims_document()
        document["requirements"][1]["domains"]["vendor-b"] = "vendor-c"
        document["claims"][3]["independent_domains"] = {"normal": 2, "critical": 2}
        verdict = _evaluate_claims(_claim_receipts(VENDOR_A_DOWN), document=document)
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual(["vendor-c"], _claim(verdict, "full-findings")["domains"])

    def test_r10_a_claim_is_supported_only_by_its_own_evidence(self) -> None:
        """R10: vendor B's complete inventory supports the full claim it is
        qualified for, never the diff claim it is not."""
        down = {**VENDOR_A_DOWN, "vendor-c": "UNAVAILABLE"}
        verdict = _evaluate_claims(_claim_receipts(down))
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual([], _claim(verdict, "diff-findings")["domains"])
        self.assertEqual(["vendor-b"], _claim(verdict, "full-findings")["domains"])

    def test_r11_classes_differ_only_by_the_declared_minimums(self) -> None:
        """R11: the same receipts suffice for a normal change and not a critical
        one, since only the protected declaration's minimums differ."""
        receipts = _claim_receipts(VENDOR_A_DOWN)
        normal = _evaluate_claims(receipts)
        critical = _evaluate_claims(receipts, change_class="critical")
        self.assertEqual(
            ("COMPLETE", "INCOMPLETE"), (normal["status"], critical["status"])
        )
        self.assertEqual(normal["requirements"], critical["requirements"])

    def test_no_applicable_claim_is_incomplete(self) -> None:
        verdict = _evaluate_claims(_claim_receipts(), change_class="mechanical")
        self.assertEqual("INCOMPLETE", verdict["status"])
        self.assertEqual([], verdict["claims"])
        self.assertEqual(
            ["no claim applies to change class 'mechanical'"], verdict["reasons"]
        )

    def test_the_claims_verdict_names_its_claims_and_nothing_more(self) -> None:
        """R6, R12: the verdict is evidence, versioned with its declaration, and
        carries no authority field."""
        verdict = _evaluate_claims(_claim_receipts())
        self.assertEqual(
            {
                "schema",
                "status",
                "subject",
                "change_class",
                "declaration",
                "requirements",
                "claims",
                "degraded",
                "reasons",
                "ignored_receipts",
            },
            set(verdict),
        )
        self.assertEqual(
            {"id": "example.required-evidence", "version": "0.2.0"},
            verdict["declaration"],
        )
        self.assertEqual(([], []), (verdict["degraded"], verdict["reasons"]))
        self.assertEqual(
            {
                "id": "diff-findings",
                "status": "COMPLETE",
                "required_domains": 1,
                "domains": ["vendor-a", "vendor-c"],
                "evidence": [
                    {
                        "requirement": "analyzer-readback",
                        "item": "vendor-a-diff",
                        "domain": "vendor-a",
                        "status": "COMPLETE",
                    },
                    {
                        "requirement": "second-inventory",
                        "item": "vendor-c",
                        "domain": "vendor-c",
                        "status": "COMPLETE",
                    },
                ],
            },
            _claim(verdict, "diff-findings"),
        )


class ClaimDeclarationTests(unittest.TestCase):
    def _rejects(self, document: object, message: str) -> None:
        with self.assertRaisesRegex(
            assurance_completeness.AssuranceCompletenessError, message
        ):
            assurance_completeness.parse_declaration(document)

    def test_a_valid_claims_declaration_parses(self) -> None:
        declaration = assurance_completeness.parse_declaration(CLAIMS_DECLARATION)
        self.assertEqual("1.1", declaration["schema_version"])
        self.assertEqual(
            ["fast-tests", "smoke-tests", "diff-findings", "full-findings"],
            [claim["id"] for claim in declaration["claims"]],
        )
        self.assertEqual(
            {
                "vendor-a-diff": "vendor-a",
                "vendor-a-full": "vendor-a",
                "vendor-b": "vendor-b",
            },
            declaration["requirements"][1]["domains"],
        )

    def test_a_1_1_declaration_needs_claims_and_domains(self) -> None:
        document = _claims_document()
        del document["claims"]
        self._rejects(document, "lacks 'claims'")
        document = _claims_document()
        del document["requirements"][0]["domains"]
        self._rejects(document, "lacks 'domains'")
        self._rejects(dict(_claims_document(), claims=[]), "claims must be non-empty")

    def test_every_item_has_exactly_one_domain(self) -> None:
        document = _claims_document()
        del document["requirements"][1]["domains"]["vendor-b"]
        self._rejects(document, "domains must name exactly its coverage")
        document = _claims_document()
        document["requirements"][1]["domains"]["vendor-d"] = "vendor-d"
        self._rejects(document, "domains must name exactly its coverage")
        document = _claims_document()
        document["requirements"][1]["domains"]["vendor-b"] = "Vendor B"
        self._rejects(document, "lowercase letters, digits and hyphens")

    def test_a_claim_names_declared_evidence(self) -> None:
        for evidence in (
            {"requirement": "undeclared", "item": "vendor-b"},
            {"requirement": "analyzer-readback", "item": "vendor-c"},
        ):
            with self.subTest(evidence=evidence):
                document = _claims_document()
                document["claims"][3]["evidence"].append(evidence)
                self._rejects(document, "is not declared")

    def test_a_claim_cannot_require_more_domains_than_its_evidence_has(self) -> None:
        """R2: vendor A's two reads cannot meet a two-domain minimum."""
        document = _claims_document()
        document["claims"][2]["evidence"] = [
            {"requirement": "analyzer-readback", "item": "vendor-a-diff"},
            {"requirement": "analyzer-readback", "item": "vendor-a-full"},
        ]
        self._rejects(document, "requires 2 independent domains")

    def test_a_minimum_is_a_positive_integer(self) -> None:
        for minimum in (0, -1, True, 1.5, "1", None):
            with self.subTest(minimum=minimum):
                document = _claims_document()
                document["claims"][0]["independent_domains"]["normal"] = minimum
                self._rejects(document, "must be a positive integer")

    def test_a_claim_applies_only_where_its_evidence_does(self) -> None:
        document = _claims_document()
        document["claims"][0]["independent_domains"]["mechanical"] = 1
        self._rejects(document, "does not apply to 'mechanical'")
        document = _claims_document()
        document["claims"][0]["independent_domains"] = {"unknown": 1}
        self._rejects(document, "unknown change class")

    def test_every_applicable_item_supports_a_claim(self) -> None:
        """An item collected for a class but required by no claim of it would be
        an obligation dropped silently."""
        document = _claims_document()
        document["claims"][1]["independent_domains"] = {"critical": 1}
        self._rejects(
            document,
            "'verification-checks' item 'smoke' supports no claim for 'normal'",
        )

    def test_claim_ids_and_evidence_are_unique(self) -> None:
        document = _claims_document()
        document["claims"][1]["id"] = "fast-tests"
        self._rejects(document, "duplicate claim id")
        document = _claims_document()
        document["claims"][3]["evidence"].append(
            {"requirement": "analyzer-readback", "item": "vendor-b"}
        )
        self._rejects(document, "duplicate evidence")

    def test_claim_keys_are_closed(self) -> None:
        document = _claims_document()
        document["claims"][0]["waiver"] = True
        self._rejects(document, "claim 0 has unknown key 'waiver'")
        document = _claims_document()
        document["claims"][0]["evidence"][0]["domain"] = "ci"
        self._rejects(document, "claim 0 evidence 0 has unknown key 'domain'")

    def test_the_command_reduces_a_claims_declaration(self) -> None:
        code, output = _run(
            json.dumps(
                {
                    "subject": SUBJECT,
                    "change_class": "normal",
                    "receipts": _claim_receipts(VENDOR_A_DOWN),
                }
            ),
            CLAIMS_DECLARATION,
        )
        self.assertEqual(0, code)
        self.assertEqual("COMPLETE", json.loads(output)["status"])


if __name__ == "__main__":
    unittest.main()
