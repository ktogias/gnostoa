"""Review regressions for the four findings retained on PR #500 (Work Item #499)."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from tools import project_progress as core
from tools import project_progress_github as github
from tools import project_progress_native as n
from tools.agent_review_model import Ref

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
                identity = {"kind": scope["kind"], "ref": scope["ref"]}
                self.assertEqual(
                    plain["source_key"],
                    "progress:"
                    + hashlib.sha256(
                        json.dumps(identity, sort_keys=True).encode()
                    ).hexdigest(),
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

    def test_a_captured_target_without_a_state_fails_closed(self) -> None:
        for state in (None, "", 7):
            context = copy.deepcopy(self.context)
            if state is None:
                del context[self.pull]["state"]
            else:
                context[self.pull]["state"] = state
            with (
                self.subTest(state=state),
                self.assertRaisesRegex(ValueError, "never dispatches a closed PR"),
            ):
                self.validate(context)

    def test_sources_and_captured_reads_share_one_closed_rule(self) -> None:
        cases: tuple[tuple[n.Native, bool], ...] = (
            ({"state": "open"}, False),
            ({"state": "OPEN", "merged": False, "merge_commit_sha": None}, False),
            ({"state": "closed"}, True),
            ({"state": "CLOSED"}, True),
            ({"state": "merged"}, True),
            ({"state": "open", "merged": True}, True),
            ({"state": "open", "merge_commit_sha": "c" * 40}, True),
        )
        for value, closed in cases:
            expected = (Ref("pr", "600"),) if closed else ()
            with self.subTest(value=value):
                self.assertEqual(github.pr_closed(value), closed)
                self.assertEqual(
                    github.closed_targets([{"kind": "pr", "pr_number": 600, **value}]),
                    expected,
                )
                self.assertEqual(
                    github.closed_reads(
                        {self.pull: {"kind": "pr", "number": 600, **value}}
                    ),
                    expected,
                )

    def test_a_retained_source_without_a_state_stays_assignable(self) -> None:
        self.assertEqual(github.closed_targets([{"kind": "pr", "pr_number": 600}]), ())


class ProviderNumberTests(unittest.TestCase):
    def test_only_ascii_digits_name_a_provider_number(self) -> None:
        self.assertEqual(github.target_ref("issue:496/pr:500"), Ref("pr", "500"))
        self.assertEqual(github.target_ref("issue:496"), Ref("work_item", "496"))
        self.assertEqual(
            github.read_ref(
                "https://github.com/ktogias/gnostoa/pull/500#issuecomment-1",
                {"kind": "pr"},
            ),
            Ref("pr", "500"),
        )
        other_script = "5" + chr(0x665)  # ARABIC-INDIC DIGIT FIVE
        self.assertTrue(other_script.isdigit())
        self.assertIsNone(github.target_ref("pr:" + other_script))
        self.assertIsNone(github.target_ref("issue:" + other_script))
        self.assertIsNone(github.scope_ref({"ref": "issue:" + other_script}))
        self.assertIsNone(
            github.read_ref(
                "https://github.com/ktogias/gnostoa/pull/" + other_script,
                {"kind": "pr"},
            )
        )


class SourceChangeResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate: n.Native = {
            "resume_subject": {"pr_number": 600, "head_sha": HEAD},
            "resume_event": "provider_source_changed",
            "canonical": {"check_run_id": 456},
            "at": NOW,
        }
        self.record: n.Native = {
            "kind": "check_verdict",
            "number": 600,
            "material_id": "one-verdict",
            "observed_at": NOW + 1,
            "payload": {"item": {"head_sha": HEAD}},
        }

    def resume(self, provider_id: object, **changes: object) -> str | None:
        record = {**self.record, **changes}
        fact: n.Native = {"head": HEAD, "provider_id": provider_id}
        return n.gate_resume(self.gate, record, fact, NOW + 2, changed=True)

    def test_a_later_verdict_than_the_captured_check_run_resumes(self) -> None:
        self.assertEqual(self.resume(457), "MERGE_ADMISSION_CHANGE")

    def test_the_captured_or_an_earlier_check_run_never_resumes(self) -> None:
        for provider_id in (456, 455, None, "457", True):
            with self.subTest(provider_id=provider_id):
                self.assertIsNone(self.resume(provider_id))

    def test_only_a_changed_verdict_on_the_exact_head_resumes(self) -> None:
        fact: n.Native = {"head": HEAD, "provider_id": 457}
        self.assertIsNone(n.gate_resume(self.gate, self.record, fact, NOW + 2))
        self.assertIsNone(self.resume(457, kind="review"))
        self.assertIsNone(self.resume(457, payload={"item": {"head_sha": "b" * 40}}))
        self.assertIsNone(self.resume(457, material_id=""))
        unsupported = {**self.gate, "resume_event": "another_event"}
        self.assertIsNone(
            n.gate_resume(unsupported, self.record, fact, NOW + 2, changed=True)
        )


class TransitionTableTests(unittest.TestCase):
    """Every branch of the transition choice, as it read before it was split."""

    def test_each_state_keeps_its_decision(self) -> None:
        sent = core.Transition(has_request=True, reason="SENT")
        pending = replace(sent, changed=True, reason="PENDING_INGRESS")
        cases: tuple[tuple[core.Transition, tuple[str, str | None]], ...] = (
            (core.Transition(open=False, intent=True), ("HOLD", "ACCOUNTED")),
            (replace(sent, intent=True, fate="DISCHARGE"), ("REEMIT", "SENT")),
            (core.Transition(reason="IGNORED"), ("REQUEST", "OPENED")),
            (core.Transition(fate="DISCHARGE"), ("REQUEST", "OPENED")),
            (core.Transition(hold="DAILY_CAP"), ("HELD", "DAILY_CAP")),
            (
                core.Transition(source_open=True, return_open=True, hold="DAILY_CAP"),
                ("HOLD", "SOURCE_OWNER_OPEN"),
            ),
            (
                core.Transition(return_open=True, hold="DAILY_CAP"),
                ("HOLD", "SOURCE_RETURN_OPEN"),
            ),
            (sent, ("HOLD", "SENT")),
            (replace(sent, changed=True), ("HOLD", "SENT")),
            (replace(sent, fate="DISCHARGE"), ("DISCHARGE", "SENT")),
            (replace(sent, fate="DISCHARGE", changed=True), ("REQUEST", "SENT")),
            (replace(sent, fate="REEMIT", changed=True), ("REEMIT", "SENT")),
            (replace(sent, fate="RETRY"), ("REQUEST", "SENT")),
            (
                replace(sent, fate="RETRY", source_open=True),
                ("HOLD", "SOURCE_OWNER_OPEN"),
            ),
            (replace(sent, reason="TAKEN"), ("HOLD", "TAKEN")),
            (replace(sent, reason="TAKEN", changed=True), ("REQUEST", "TAKEN")),
            (
                replace(sent, reason="LOST", changed=True, hold="IDENTITY_CAP"),
                ("HELD", "IDENTITY_CAP"),
            ),
            (replace(pending, changed=False), ("HOLD", "PENDING_INGRESS")),
            (pending, ("REFRESH_PENDING", "PENDING_INGRESS")),
            (
                replace(pending, pending_refreshed=True),
                ("REFRESHED", "PENDING_INGRESS"),
            ),
            (replace(pending, pending_refreshed=False), ("REQUEST", "PENDING_INGRESS")),
            (
                replace(pending, pending_refreshed=False, return_open=True),
                ("HOLD", "SOURCE_RETURN_OPEN"),
            ),
            (
                replace(pending, fate="DISCHARGE"),
                ("REFRESH_PENDING", "PENDING_INGRESS"),
            ),
            (
                replace(pending, fate="REEMIT", pending_refreshed=True),
                ("REEMIT", "PENDING_INGRESS"),
            ),
        )
        for state, expected in cases:
            decision = core.decide_transition(state)
            with self.subTest(state=state):
                self.assertEqual((decision.action, decision.reason), expected)


class BudgetLimitTests(unittest.TestCase):
    def test_the_controller_decision_applies_each_named_limit(self) -> None:
        store: n.Native = {}
        scope: n.Native = {"kind": "work_item", "ref": "issue:496"}
        obligation, _, _ = n.open_obligation(store, scope, [], None, NOW)
        obligation["requests"] = [{"key": "k", "at": _iso(NOW - 10), "state": "SENT"}]

        def decide(**limits: Any) -> tuple[str, str]:
            return n.controller_decision(
                obligation,
                fate="RETRY",
                reason="SENT",
                touched=False,
                linked_open=False,
                source_router_open=False,
                now=NOW,
                obligations=store,
                current_input="same",
                last_input="same",
                **limits,
            )

        self.assertEqual(decide(), ("REQUEST", "SENT"))
        self.assertEqual(decide(per_identity=1), ("HELD", "IDENTITY_CAP"))
        self.assertEqual(decide(per_identity=1, window_seconds=5), ("REQUEST", "SENT"))
        self.assertEqual(decide(daily_cap=1), ("HELD", "DAILY_CAP"))
        with self.assertRaises(TypeError):
            decide(another_limit=1)


if __name__ == "__main__":
    unittest.main()
