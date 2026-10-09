from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
        self.assertLessEqual(
            review_reconcile.COVERAGE_STATUSES,
            assurance_completeness.RECEIPT_STATUSES,
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
                with self.subTest(path=path):
                    with self.assertRaisesRegex(
                        assurance_completeness.AssuranceCompletenessError,
                        "outside the project root",
                    ):
                        assurance_completeness.load_declaration(path, project_root=root)


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
            with self.subTest(change_class=value):
                with self.assertRaisesRegex(
                    assurance_completeness.AssuranceCompletenessError, "change class"
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
            with self.subTest(applies_to=value):
                with self.assertRaises(
                    assurance_completeness.AssuranceCompletenessError
                ):
                    assurance_completeness.parse_declaration(document)


def _run(text: str, declaration: object | None = None) -> tuple[int, str]:
    """Run the command in a scratch project, with `text` on standard input."""

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "policy").mkdir()
        (root / "policy" / "assurance-evidence.yaml").write_text(
            json.dumps(DECLARATION if declaration is None else declaration),
            encoding="utf-8",
        )
        stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
