"""VF0 normalized relation conformance; synthetic inputs confer no authority."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import importlib.util
import json
import unittest
from pathlib import Path
from typing import Any

MODULE = "tools.vf0_contract"


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(raw.encode("ascii")).hexdigest()


def _ref(opaque_id: str, provider: str = "provider-a") -> dict[str, str]:
    return {
        "provider": provider,
        "instance": "instance-a",
        "repository": "repository-a",
        "opaque_id": opaque_id,
    }


def _guarantees() -> dict[str, dict[str, object]]:
    return {
        key: {"state": "VERIFIED", "records": ["sha256:" + "a" * 64]}
        for key in (
            "request_binding",
            "record_coverage",
            "attempt_identity",
            "latest_attempt",
            "source_revalidation",
            "protection_revalidation",
            "credential_separation",
        )
    }


def _fixture() -> dict[str, Any]:
    sha = "sha256:" + "a" * 64
    outcome = {
        "exit_code": 1,
        "cases": [{"id": "target", "result": "FAIL", "cause": "ASSERTION_FAILURE"}],
    }
    policy = {
        "id": "effective-policy",
        "modes": {
            "mechanical": ["STRUCTURAL"],
            "normal": ["RED", "CHARACTERIZATION", "STRUCTURAL"],
            "normative": ["RED", "STRUCTURAL"],
            "critical": ["RED"],
            "emergency": ["EMERGENCY_POST_EVENT"],
        },
        "required_guarantees": sorted(_guarantees()),
        "max_age_seconds": 900,
    }
    request = {
        "identity": _ref("request"),
        "work_item": _ref("work"),
        "decision": _ref("decision"),
        "policy_sha256": _digest(policy),
        "change_class": "critical",
        "mode": "RED",
        "criterion": "EXECUTABLE",
        "candidate_paths": ["tests/test_target.py", "tools/target.py"],
        "material": {
            "parent_commit": "git-sha1:parent",
            "parent_tree": "git-sha1:parent-tree",
            "evidence_tree": "git-sha1:evidence-tree",
            "evidence_patch_sha256": sha,
            "production_sha256": sha,
            "command_sha256": sha,
            "oracle_sha256": sha,
            "evidence_files": {"tests/test_target.py": sha},
        },
        "outcome": outcome,
        "valid_from": 100,
        "valid_until": 2000,
        "follow_up": None,
    }
    admission = {
        "request_sha256": _digest(request),
        "record": _ref("native-admission"),
        "record_sha256": sha,
        "principal": _ref("principal"),
        "disposition": "APPROVED",
        "observed_at": 200,
        "guarantees": _guarantees(),
    }
    return {
        "schema": "gnostoa-vf0-relation-input/v1",
        "now": 1000,
        "policy": policy,
        "request": request,
        "admission": admission,
        "evidence": {
            "request_sha256": _digest(request),
            "admission_sha256": _digest(admission),
            "material": copy.deepcopy(request["material"]),
            "mode": "RED",
            "chronology": "PRE_CHANGE",
            "execution": _ref("run"),
            "attempt": "attempt-z",
            "latest_attempt": "attempt-z",
            "publisher": _ref("publisher"),
            "artifact": _ref("artifact"),
            "source_sha256": sha,
            "archive_sha256": sha,
            "status": "COMPLETED",
            "coverage": "COMPLETE",
            "started_at": 300,
            "completed_at": 400,
            "expires_at": 1900,
            "outcome": copy.deepcopy(outcome),
            "accountable_review": None,
            "guarantees": _guarantees(),
        },
        "candidate": {
            "parent_commit": "git-sha1:parent",
            "parent_tree": "git-sha1:parent-tree",
            "tree": "git-sha1:candidate-tree",
            "observed_at": 500,
            "changed_paths": ["tests/test_target.py", "tools/target.py"],
            "evidence_files": {"tests/test_target.py": sha},
        },
    }


def _rebind(document: dict[str, Any]) -> None:
    document["request"]["policy_sha256"] = _digest(document["policy"])
    digest = _digest(document["request"])
    document["admission"]["request_sha256"] = digest
    document["evidence"]["request_sha256"] = digest
    document["evidence"]["admission_sha256"] = _digest(document["admission"])


class VF0ContractEntryTests(unittest.TestCase):
    def test_network_free_relation_entrypoint_exists(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec(MODULE),
            "D0092 normalized relation entry point is not implemented",
        )


class VF0RelationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.core = importlib.import_module(MODULE)
        self.document = _fixture()

    def assertRejected(self, document: object) -> dict[str, Any]:
        result: dict[str, Any] = self.core.evaluate(document)
        self.assertEqual("REJECTED", result["status"], result)
        self.assertTrue(result["reasons"])
        self.assertFalse(result["compliance"])
        self.assertEqual("NOT_ESTABLISHED", result["authentication"])
        return result

    def test_matching_data_is_not_authenticated_or_authorized(self) -> None:
        result = self.core.evaluate(self.document)
        self.assertEqual("MATCH", result["status"])
        self.assertEqual([], result["reasons"])
        self.assertFalse(result["compliance"])
        self.assertFalse(result["vf0_active"])
        self.assertEqual("NOT_ESTABLISHED", result["authentication"])
        self.assertNotIn("approved", result)
        self.assertNotIn("write_authorized", result)

    def test_input_is_not_mutated_and_repeated_evaluation_is_deterministic(
        self,
    ) -> None:
        before = copy.deepcopy(self.document)
        first = self.core.evaluate(self.document)
        self.assertEqual(first, self.core.evaluate(self.document))
        self.assertEqual(before, self.document)

    def test_unknown_fields_reject_at_every_structural_level(self) -> None:
        selectors = [
            (),
            ("policy",),
            ("request",),
            ("admission",),
            ("evidence",),
            ("candidate",),
            ("request", "material"),
            ("request", "identity"),
            ("request", "outcome"),
            ("evidence", "outcome"),
        ]
        for selector in selectors:
            with self.subTest(selector=selector):
                doc = copy.deepcopy(self.document)
                target = doc
                for key in selector:
                    target = target[key]
                target["trusted"] = True
                self.assertRejected(doc)

    def test_missing_required_fields_reject(self) -> None:
        for block in ("policy", "request", "admission", "evidence", "candidate"):
            for key in self.document[block]:
                with self.subTest(block=block, key=key):
                    doc = copy.deepcopy(self.document)
                    del doc[block][key]
                    self.assertRejected(doc)

    def test_wrong_request_and_admission_digests_reject(self) -> None:
        for block, field in [
            ("request", "policy_sha256"),
            ("admission", "request_sha256"),
            ("evidence", "request_sha256"),
            ("evidence", "admission_sha256"),
        ]:
            with self.subTest(block=block, field=field):
                doc = copy.deepcopy(self.document)
                doc[block][field] = "sha256:" + "b" * 64
                self.assertRejected(doc)

    def test_any_material_substitution_rejects(self) -> None:
        for key in self.document["evidence"]["material"]:
            with self.subTest(key=key):
                doc = copy.deepcopy(self.document)
                doc["evidence"]["material"][key] = (
                    {"tests/test_target.py": "sha256:" + "b" * 64}
                    if key == "evidence_files"
                    else (
                        "sha256:" + "b" * 64
                        if key.endswith("sha256")
                        else "substituted"
                    )
                )
                self.assertRejected(doc)

    def test_candidate_parent_tree_and_retained_evidence_are_exact(self) -> None:
        for field, value in [
            ("parent_commit", "different-parent"),
            ("parent_tree", "different-tree"),
            ("evidence_files", {}),
            ("evidence_files", {"tests/test_target.py": "sha256:" + "b" * 64}),
        ]:
            with self.subTest(field=field):
                doc = copy.deepcopy(self.document)
                doc["candidate"][field] = value
                self.assertRejected(doc)

    def test_candidate_diff_must_carry_each_admitted_evidence_delta_file(self) -> None:
        self.document["candidate"]["changed_paths"] = ["tools/target.py"]
        self.assertRejected(self.document)

    def test_changed_candidate_cannot_retain_the_parent_tree(self) -> None:
        self.document["candidate"]["tree"] = self.document["request"]["material"][
            "parent_tree"
        ]
        result = self.assertRejected(self.document)
        self.assertEqual(["CANDIDATE_TREE_UNCHANGED"], result["reasons"])

    def test_candidate_paths_do_not_escape_the_request(self) -> None:
        for paths, reason in [
            ([], "PATH_SET"),
            (["tools/foreign.py"], "CANDIDATE_PATH_SCOPE"),
            (["../outside.py"], "PATH_FORMAT"),
            (["/outside"], "PATH_FORMAT"),
            (["tools/../target.py"], "PATH_FORMAT"),
            (["tools//target.py"], "PATH_FORMAT"),
            (["tools\\target.py"], "PATH_FORMAT"),
            (["tools/target.py", "tools/target.py"], "DUPLICATE_PATH"),
        ]:
            with self.subTest(paths=paths):
                doc = copy.deepcopy(self.document)
                # Keep the valid request unchanged so candidate validation is
                # exercised; a generic scope refusal cannot hide a format bug.
                doc["candidate"]["changed_paths"] = paths
                self.assertEqual([reason], self.assertRejected(doc)["reasons"])

    def test_requested_paths_and_evidence_members_are_canonical(self) -> None:
        for path, reason in [
            ("../outside", "PATH_FORMAT"),
            ("/absolute", "PATH_FORMAT"),
            ("a//b", "PATH_FORMAT"),
            ("a/./b", "PATH_FORMAT"),
            ("a\\b", "PATH_FORMAT"),
            (".git/config", "PATH_FORMAT"),
            ("x/\x00", "TEXT_IDENTITY"),
        ]:
            with self.subTest(path=path):
                doc = copy.deepcopy(self.document)
                doc["request"]["candidate_paths"].append(path)
                _rebind(doc)
                self.assertEqual([reason], self.assertRejected(doc)["reasons"])

    def test_guarantee_missing_unknown_unsupported_or_contradicted_rejects(
        self,
    ) -> None:
        for block in ("admission", "evidence"):
            for name in _guarantees():
                for state in (None, "UNKNOWN", "UNSUPPORTED", "CONTRADICTED"):
                    with self.subTest(block=block, name=name, state=state):
                        doc = copy.deepcopy(self.document)
                        if state is None:
                            del doc[block]["guarantees"][name]
                        else:
                            doc[block]["guarantees"][name]["state"] = state
                        _rebind(doc)
                        self.assertRejected(doc)

    def test_verified_guarantee_requires_retained_record(self) -> None:
        self.document["evidence"]["guarantees"]["source_revalidation"]["records"] = []
        self.assertRejected(self.document)

    def test_namespace_collisions_are_not_equal_execution_identity(self) -> None:
        for member in ("execution", "publisher", "artifact"):
            for field in ("provider", "instance", "repository"):
                with self.subTest(member=member, field=field):
                    doc = copy.deepcopy(self.document)
                    doc["evidence"][member][field] = "other"
                    self.assertRejected(doc)

    def test_two_distinct_provider_mappings_share_the_same_common_outcome(self) -> None:
        # Deliberately different native layouts: nested numeric REST-style fields
        # versus compound string identifiers and retry metadata. Test-only adapters;
        # neither can authenticate a production observation.
        flat = {
            "repo": {"id": 17},
            "workflow_run": {"id": 90, "attempt": 2},
            "job": {"id": 80},
            "archive": {"id": 71},
        }
        compound: dict[str, Any] = {
            "workspace": "tenant/project",
            "build": "urn:build:alpha/z",
            "retry_metadata": {"cursor": "retry:two"},
            "publication": ("worker:beta", "object:gamma"),
        }

        def apply_context(
            doc: dict[str, Any],
            provider: str,
            repository: str,
            run: str,
            attempt: str,
            job: str,
            artifact: str,
        ) -> None:
            context = {
                "provider": provider,
                "instance": provider + ".example.invalid",
                "repository": repository,
            }
            for field in ("identity", "work_item", "decision"):
                doc["request"][field].update(context)
            for field in ("record", "principal"):
                doc["admission"][field].update(context)
            for field, identifier in (
                ("execution", run),
                ("publisher", job),
                ("artifact", artifact),
            ):
                doc["evidence"][field].update(context, opaque_id=identifier)
            doc["evidence"].update(attempt=attempt, latest_attempt=attempt)
            _rebind(doc)

        first_doc, second_doc = (
            copy.deepcopy(self.document),
            copy.deepcopy(self.document),
        )
        apply_context(
            first_doc,
            "rest-like",
            str(flat["repo"]["id"]),
            str(flat["workflow_run"]["id"]),
            str(flat["workflow_run"]["attempt"]),
            str(flat["job"]["id"]),
            str(flat["archive"]["id"]),
        )
        apply_context(
            second_doc,
            "compound-like",
            compound["workspace"],
            compound["build"],
            compound["retry_metadata"]["cursor"],
            compound["publication"][0],
            compound["publication"][1],
        )
        first, second = self.core.evaluate(first_doc), self.core.evaluate(second_doc)
        self.assertEqual("MATCH", first["status"])
        self.assertEqual("MATCH", second["status"])
        self.assertEqual(first["reasons"], second["reasons"])
        self.assertNotEqual(first["request_sha256"], second["request_sha256"])

    def test_attempt_is_opaque_explicit_and_exactly_latest(self) -> None:
        for attempt, latest in [
            (None, "attempt-z"),
            (1, 1),
            (True, True),
            ("", ""),
            ("attempt-z", "attempt-a"),
        ]:
            with self.subTest(attempt=attempt, latest=latest):
                doc = copy.deepcopy(self.document)
                doc["evidence"]["attempt"] = attempt
                doc["evidence"]["latest_attempt"] = latest
                self.assertRejected(doc)

    def test_incomplete_execution_and_coverage_reject(self) -> None:
        for field, values in [
            ("status", ["PENDING", "FAILED"]),
            ("coverage", ["PARTIAL", "UNKNOWN"]),
        ]:
            for value in values:
                with self.subTest(field=field, value=value):
                    doc = copy.deepcopy(self.document)
                    doc["evidence"][field] = value
                    self.assertRejected(doc)

    def test_disposition_must_be_explicit_approval(self) -> None:
        for value in ("REJECTED", "UNKNOWN", True, "approved"):
            with self.subTest(value=value):
                doc = copy.deepcopy(self.document)
                doc["admission"]["disposition"] = value
                _rebind(doc)
                self.assertRejected(doc)

    def test_expiry_freshness_and_ordering_boundaries(self) -> None:
        mutations = [
            ("now", None, True),
            ("now", None, 2000),
            ("evidence", "expires_at", 1000),
            ("evidence", "started_at", 199),
            ("evidence", "completed_at", 299),
            ("evidence", "completed_at", 501),
            ("candidate", "observed_at", 1001),
            ("admission", "observed_at", 99),
        ]
        for block, key, value in mutations:
            with self.subTest(block=block, key=key):
                doc = copy.deepcopy(self.document)
                if key is None:
                    doc[block] = value
                else:
                    doc[block][key] = value
                _rebind(doc)
                self.assertRejected(doc)
        self.document["policy"]["max_age_seconds"] = 599
        _rebind(self.document)
        self.assertRejected(self.document)

    def test_maximum_age_is_inclusive(self) -> None:
        self.document["policy"]["max_age_seconds"] = 600
        _rebind(self.document)
        self.assertEqual("MATCH", self.core.evaluate(self.document)["status"])

    def test_late_reconstruction_is_not_pre_change_evidence(self) -> None:
        self.document["evidence"]["chronology"] = "LATE_RECONSTRUCTION"
        self.assertRejected(self.document)

    def test_red_requires_exact_nonvacuous_failures_not_infrastructure(self) -> None:
        outcomes = [
            {"exit_code": 1, "cases": []},
            {"exit_code": 2, "cases": self.document["request"]["outcome"]["cases"]},
            {"exit_code": True, "cases": self.document["request"]["outcome"]["cases"]},
            {
                "exit_code": 1,
                "cases": [{"id": "target", "result": "ERROR", "cause": "IMPORT_ERROR"}],
            },
            {
                "exit_code": 1,
                "cases": [{"id": "target", "result": "SKIP", "cause": "SKIPPED"}],
            },
            {
                "exit_code": 1,
                "cases": [{"id": "target", "result": "FAIL", "cause": "TIMEOUT"}],
            },
        ]
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                doc = copy.deepcopy(self.document)
                doc["request"]["outcome"] = outcome
                doc["evidence"]["outcome"] = copy.deepcopy(outcome)
                _rebind(doc)
                self.assertRejected(doc)

    def test_different_case_and_conflicting_duplicate_cannot_match(self) -> None:
        for cases in [
            [{"id": "unrelated", "result": "FAIL", "cause": "ASSERTION_FAILURE"}],
            self.document["evidence"]["outcome"]["cases"] * 2,
        ]:
            with self.subTest(cases=cases):
                doc = copy.deepcopy(self.document)
                doc["evidence"]["outcome"]["cases"] = cases
                self.assertRejected(doc)

    def test_characterization_needs_policy_allowance_and_success(self) -> None:
        doc = self.document
        doc["request"].update(change_class="normal", mode="CHARACTERIZATION")
        doc["evidence"]["mode"] = "CHARACTERIZATION"
        outcome = {
            "exit_code": 0,
            "cases": [{"id": "target", "result": "PASS", "cause": "NONE"}],
        }
        doc["request"]["outcome"] = outcome
        doc["evidence"]["outcome"] = copy.deepcopy(outcome)
        _rebind(doc)
        self.assertEqual("MATCH", self.core.evaluate(doc)["status"])
        doc["request"]["change_class"] = "critical"
        _rebind(doc)
        self.assertRejected(doc)

    def test_structural_is_accountable_review_not_executed_red(self) -> None:
        doc = self.document
        doc["request"].update(
            change_class="normative", mode="STRUCTURAL", criterion="NON_EXECUTABLE"
        )
        doc["evidence"]["mode"] = "STRUCTURAL"
        doc["request"]["material"]["evidence_files"] = {}
        doc["evidence"]["material"] = copy.deepcopy(doc["request"]["material"])
        doc["candidate"]["evidence_files"] = {}
        doc["request"]["outcome"] = {"exit_code": 0, "cases": []}
        doc["evidence"]["outcome"] = {"exit_code": 0, "cases": []}
        doc["evidence"]["accountable_review"] = _ref("accountable-review")
        _rebind(doc)
        self.assertEqual("MATCH", self.core.evaluate(doc)["status"])
        doc["evidence"]["accountable_review"] = None
        self.assertRejected(doc)

    def test_structural_cannot_relabel_executable_criterion(self) -> None:
        self.document["request"].update(change_class="normal", mode="STRUCTURAL")
        self.document["evidence"]["mode"] = "STRUCTURAL"
        _rebind(self.document)
        self.assertRejected(self.document)

    def test_emergency_requires_emergency_class_followup_and_explicit_chronology(
        self,
    ) -> None:
        doc = self.document
        doc["request"].update(
            change_class="emergency",
            mode="EMERGENCY_POST_EVENT",
            follow_up=_ref("required-followup"),
        )
        doc["evidence"].update(
            mode="EMERGENCY_POST_EVENT",
            chronology="EMERGENCY_POST_EVENT",
            started_at=600,
            completed_at=700,
        )
        _rebind(doc)
        self.assertEqual("MATCH", self.core.evaluate(doc)["status"])
        doc["request"]["follow_up"] = None
        _rebind(doc)
        self.assertRejected(doc)

    def test_json_duplicate_nonfinite_invalid_utf8_and_nonobject_reject(self) -> None:
        for raw in [
            b'{"schema":1,"schema":2}',
            b'{"v":NaN}',
            b'{"v":1e999}',
            b'{"v":1.5}',
            b"\xff",
            b"[]",
            b"null",
            b"{",
        ]:
            with self.subTest(raw=raw):
                result = self.core.evaluate_json(raw)
                self.assertEqual("REJECTED", result["status"])
                self.assertFalse(result["compliance"])

    def test_json_and_programmatic_paths_agree(self) -> None:
        self.assertEqual(
            self.core.evaluate(self.document),
            self.core.evaluate_json(json.dumps(self.document).encode()),
        )

    def test_cyclic_deep_large_and_custom_python_values_are_bounded(self) -> None:
        cycle: dict[str, object] = {}
        cycle["cycle"] = cycle
        deep: object = None
        for _ in range(40):
            deep = [deep]
        for value in (
            cycle,
            deep,
            {"x": "x" * 300000},
            {"x": float("nan")},
            {"x": object()},
        ):
            with self.subTest(kind=type(value).__name__):
                self.assertRejected(value)
        result = self.core.evaluate_json(b" " * 262145)
        self.assertEqual("REJECTED", result["status"])

    def test_empty_and_weakened_guarantee_requirements_reject(self) -> None:
        for required in (
            [],
            ["request_binding"],
            ["request_binding", "request_binding"],
        ):
            with self.subTest(required=required):
                doc = copy.deepcopy(self.document)
                doc["policy"]["required_guarantees"] = required
                _rebind(doc)
                self.assertRejected(doc)

    def test_common_core_has_no_effectful_or_provider_specific_imports(self) -> None:
        filename = self.core.__file__
        if filename is None:
            self.fail("The relation module must have a source file.")
        tree = ast.parse(Path(filename).read_text())
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        self.assertFalse(
            imported
            & {"os", "subprocess", "socket", "urllib.request", "requests", "pathlib"}
        )
        self.assertFalse(
            any("github" in value or "gitlab" in value for value in imported)
        )

    def test_link_mapping_rejection_does_not_change_relation(self) -> None:
        subject = self.document["request"]["identity"]
        baseline = self.core.evaluate(self.document)
        links = [
            {
                "subject": subject,
                "label": "Run",
                "relation": "run",
                "url": "https://ci.example.invalid/jobs/opaque#report",
            }
        ]
        retained, rejected = self.core.resolve_links(subject, links)
        self.assertEqual(links, retained)
        self.assertEqual([], rejected)
        for url in [
            "http://ci.example.invalid/jobs/opaque",
            "https://u:p@ci.example.invalid/run",
            "https://ci.example.invalid/run?token=secret",
            "https://ci.example.invalid:444/run",
            "https://ci.example.invalid/\nrun",
        ]:
            invalid = copy.deepcopy(links)
            invalid[0]["url"] = url
            selected, reasons = self.core.resolve_links(subject, invalid)
            self.assertEqual([], selected)
            self.assertTrue(reasons)
            self.assertEqual(baseline, self.core.evaluate(self.document))
        invalid = copy.deepcopy(links)
        invalid[0]["subject"] = _ref("wrong-subject")
        self.assertEqual([], self.core.resolve_links(subject, invalid)[0])
        self.assertEqual(([], []), self.core.resolve_links(subject, []))
        self.assertEqual(baseline, self.core.evaluate(self.document))


if __name__ == "__main__":
    unittest.main()
