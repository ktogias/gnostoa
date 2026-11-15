"""Review regressions for the four findings retained on PR #500 (Work Item #499)."""

from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime

from tools import project_progress as core
from tools import project_progress_native as n

NOW = 1_800_000_000.0
HEAD = "a" * 40


def _iso(at: float) -> str:
    return datetime.fromtimestamp(at, UTC).isoformat()


class GenerationlessScopeUpdateTests(unittest.TestCase):
    def test_core_compares_fingerprints_when_both_generations_are_absent(self) -> None:
        held = core.Source("scope", None, "before", None, True, ("reader-a", 1))
        update = core.Source("scope", None, "after", None, True, ("reader-a", 2))
        merged, added, refresh = core.merge_sources((held,), (update,))
        self.assertEqual(merged, (update,))
        self.assertTrue(added)
        self.assertFalse(refresh)
        replay = core.Source("scope", None, "after", None, True, ("reader-a", 3))
        merged, added, refresh = core.merge_sources((update,), (replay,))
        self.assertEqual(merged, (update,))
        self.assertFalse(added)
        self.assertFalse(refresh)

    def test_native_generationless_update_replaces_the_scope_and_rearms(self) -> None:
        store: n.Native = {}
        scope: n.Native = {"kind": "work_item", "ref": "issue:496"}
        first = {
            "kind": "scope",
            "title": "before",
            "observed": {"epoch": "reader-a", "seq": 1},
        }
        obligation, _, _ = n.open_obligation(store, scope, [first], None, NOW)
        obligation["status"] = "DISCHARGED"
        update = {
            "kind": "scope",
            "title": "after",
            "observed": {"epoch": "reader-a", "seq": 2},
        }
        obligation, added, refresh = n.open_obligation(
            store, scope, [update], None, NOW + 1
        )
        self.assertTrue(added)
        self.assertIsNone(refresh)
        self.assertEqual(obligation["sources"], [update])
        self.assertEqual(obligation["status"], "OPEN")

        obligation["status"] = "DISCHARGED"
        for sequence in (0, 3):
            late = {**first, "observed": {"epoch": "reader-a", "seq": sequence}}
            replay = {**update, "observed": {"epoch": "reader-a", "seq": sequence}}
            for incoming in (late, replay) if sequence == 0 else (replay,):
                with self.subTest(incoming=incoming):
                    obligation, added, refresh = n.open_obligation(
                        store, scope, [incoming], None, NOW + 2
                    )
                    self.assertFalse(added)
                    self.assertIsNone(refresh)
                    self.assertEqual(obligation["sources"], [update])
                    self.assertEqual(obligation["status"], "DISCHARGED")


class ReviewSubmissionTimeTests(unittest.TestCase):
    def setUp(self) -> None:
        row: n.Native = {
            "id": "gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": {"pr_number": 600, "head_sha": HEAD},
            "source_sha256": "captured",
            "canonical": {"criterion": "M16"},
        }
        claim: n.Native = {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "captured",
        }
        binding = n.gate_binding({}, row, claim)
        assert binding is not None
        self.gate: n.Native = {**binding, "at": NOW}
        self.fact: n.Native = {"head": HEAD, "provider_id": 90}

    def resume(self, item: n.Native) -> str | None:
        record: n.Native = {
            "kind": "review",
            "number": 600,
            "material_id": "one-material",
            "observed_at": NOW + 2,
            "payload": {"item": {"commit_id": HEAD, **item}},
        }
        return n.gate_resume(self.gate, record, self.fact, NOW + 3, owner_review=True)

    def test_an_edit_after_the_gate_cannot_resume_an_older_submission(self) -> None:
        self.assertIsNone(
            self.resume({"submitted_at": _iso(NOW - 1), "updated_at": _iso(NOW + 1)})
        )

    def test_a_review_without_a_submission_time_fails_closed(self) -> None:
        self.assertIsNone(self.resume({"updated_at": _iso(NOW + 1)}))

    def test_a_submission_after_the_gate_resumes_whatever_its_edit_time(self) -> None:
        for updated in (None, NOW - 1, NOW + 2):
            item: n.Native = {"submitted_at": _iso(NOW + 1)}
            if updated is not None:
                item["updated_at"] = _iso(updated)
            with self.subTest(updated=updated):
                self.assertEqual(self.resume(item), "OWNER_REVIEW")


class UnresolvedOriginIdentityTests(unittest.TestCase):
    def test_unresolved_origins_get_distinct_row_identities(self) -> None:
        scope: n.Native = {"kind": "work_item", "ref": None}
        sources = [{"kind": "operation", "delivery_key": "completed-step"}]
        first = n.progress_row(scope, sources, origin="origin-a")
        second = n.progress_row(scope, sources, origin="origin-b")
        self.assertNotEqual(first["source_key"], second["source_key"])
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first, n.progress_row(scope, sources, origin="origin-a"))

    def test_bound_and_originless_row_identities_are_unchanged(self) -> None:
        sources = [{"kind": "operation", "delivery_key": "completed-step"}]
        for scope in (
            {"kind": "work_item", "ref": "issue:496"},
            {"kind": "work_item", "ref": None},
        ):
            with self.subTest(scope=scope):
                plain = n.progress_row(scope, sources)
                origin = "origin-a" if scope["ref"] else None
                self.assertEqual(plain, n.progress_row(scope, sources, origin=origin))
                self.assertEqual(
                    plain["source_key"],
                    "progress:"
                    + n._digest({"kind": scope["kind"], "ref": scope["ref"]}),
                )


class CapturedClosedTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.row = n.progress_row({"kind": "work_item", "ref": "issue:496"}, [])
        self.issue = "https://github.com/ktogias/gnostoa/issues/496"
        self.pull = "https://github.com/ktogias/gnostoa/pull/600"
        self.context: n.Native = {
            self.issue: {
                "kind": "work_item",
                "number": 496,
                "body_sha256": "issue-digest",
                "coverage": "CURRENT",
                "body_complete": True,
                "observed_at": NOW,
            },
            self.pull: {
                "kind": "pr",
                "number": 600,
                "state": "open",
                "body_sha256": "pull-digest",
                "coverage": "CURRENT",
                "body_complete": True,
                "observed_at": NOW,
            },
            "_coverage": {"coverage": "COMPLETE"},
        }
        self.claim: n.Native = {
            "id": self.row["id"],
            "disposition": "ASSIGNED",
            "assignment_index": 0,
            "evidence": [
                {"source": self.issue, "digest": "issue-digest", "observed_at": NOW},
                {"source": self.pull, "digest": "pull-digest", "observed_at": NOW},
            ],
        }

    def validate(self, context: n.Native) -> None:
        n.validate_progress(
            {"authority_context": context},
            {"coverage": "COMPLETE", "rows": [self.row]},
            self.row,
            self.claim,
            {"assignments": [{"operation": {"operation_target": "pr:600"}}]},
            [self.claim],
        )

    def test_an_open_captured_target_is_assignable(self) -> None:
        self.validate(self.context)

    def test_a_target_captured_closed_or_merged_is_never_dispatched(self) -> None:
        for change in (
            {"state": "closed"},
            {"state": "CLOSED"},
            {"state": "merged"},
            {"merged": True},
        ):
            context = copy.deepcopy(self.context)
            context[self.pull].update(change)
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(ValueError, "never dispatches a closed PR"),
            ):
                self.validate(context)

    def test_a_closed_capture_of_another_pr_does_not_close_the_target(self) -> None:
        context = copy.deepcopy(self.context)
        context["https://github.com/ktogias/gnostoa/pull/601"] = {
            **self.context[self.pull],
            "number": 601,
            "state": "closed",
        }
        self.validate(context)


if __name__ == "__main__":
    unittest.main()
