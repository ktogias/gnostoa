"""Review regressions for the four findings retained on PR #500 (Work Item #499)."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest import mock

from tools import project_progress as core
from tools import project_progress_github as github
from tools import project_progress_native as n
from tools.agent_review_model import Ref

NOW = 1_800_000_000.0
HEAD = "a" * 40
# The one refusal of an unreadable journal record, as distinct from a missing list.
_BAD_REQUEST_RECORD = "PROJECT_PROGRESS a request record needs its key"


def _iso(at: float) -> str:
    return datetime.fromtimestamp(at, UTC).isoformat()


def _journal(*records: Any) -> tuple[n.Native, n.Native]:
    """A store of one obligation, and that obligation, journalling `records`."""
    obligation = n.new_obligation("o", {"kind": "work_item", "ref": "issue:499"}, NOW)
    obligation["requests"] = list(records)
    return {"o": obligation}, obligation


def _retry_decision(obligation: n.Native, store: n.Native) -> tuple[str, str]:
    return n.controller_decision(
        obligation,
        fate="RETRY",
        reason="SENT",
        touched=False,
        linked_open=False,
        source_router_open=False,
        now=NOW,
        obligations=store,
        current_input="a",
        last_input="a",
    )


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
        # A replay adds nothing but advances the held observation order.
        self.assertEqual(merged, (replay,))
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
                    self.assertEqual(
                        obligation["sources"], [replay if sequence == 3 else update]
                    )
                    self.assertEqual(obligation["status"], "DISCHARGED")
                    update = obligation["sources"][0]

    def test_a_present_null_generation_is_absent_and_never_the_text_none(self) -> None:
        store: n.Native = {}
        scope: n.Native = {"kind": "work_item", "ref": "issue:496"}
        first: n.Native = {
            "kind": "scope",
            "generation": None,
            "title": "before",
            "observed": {"epoch": "reader-a", "seq": 1},
        }
        obligation, _, _ = n.open_obligation(store, scope, [first], None, NOW)
        obligation["status"] = "DISCHARGED"
        update: n.Native = {
            **first,
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
        # A null generation and the literal text "None" stay two generations.
        obligation["status"] = "DISCHARGED"
        named: n.Native = {
            **first,
            "generation": "None",
            "title": "named",
            "observed": {"epoch": "reader-a", "seq": 3},
        }
        obligation, added, _ = n.open_obligation(store, scope, [named], None, NOW + 2)
        self.assertTrue(added)
        self.assertEqual(obligation["sources"], [named])
        self.assertEqual(obligation["status"], "OPEN")


class ObservationTypeTests(unittest.TestCase):
    def test_a_boolean_is_not_an_observation(self) -> None:
        self.assertIsNone(github.observation(True))
        self.assertIsNone(github.observation(False))
        self.assertEqual(github.observation(3), 3)
        self.assertEqual(github.observation(1.5), 1.5)
        self.assertEqual(github.observation("t"), "t")


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

    def provider_time(self, kind: str, item: n.Native) -> float | None:
        """The provider time the resume decision is handed for one record."""
        record: n.Native = {
            "kind": kind,
            "number": 600,
            "material_id": "one-material",
            "observed_at": NOW + 2,
            "payload": {"item": {"commit_id": HEAD, **item}},
        }
        with mock.patch.object(core, "gate_resume", wraps=core.gate_resume) as decided:
            n.gate_resume(self.gate, record, self.fact, NOW + 3, owner_review=True)
        fact: core.ResumeFact = decided.call_args.args[1]
        return fact.provider_at

    def test_a_submission_time_without_a_timezone_fails_closed(self) -> None:
        aware = _iso(NOW + 1)
        naive = aware[: -len("+00:00")]
        for text in (naive, naive + ".5", naive[:10]):
            with self.subTest(text=text):
                # Read what the decision is handed: the host zone never decides.
                self.assertIsNone(self.provider_time("review", {"submitted_at": text}))
                self.assertIsNone(self.provider_time("comment", {"updated_at": text}))
                self.assertIsNone(self.resume({"submitted_at": text}))
        self.assertEqual(self.provider_time("review", {"submitted_at": aware}), NOW + 1)
        self.assertEqual(self.provider_time("comment", {"updated_at": aware}), NOW + 1)
        self.assertEqual(self.resume({"submitted_at": aware}), "OWNER_REVIEW")

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

    def quiescent(self, context: n.Native, rows: list[n.Native]) -> None:
        claim: n.Native = {
            "id": self.row["id"],
            "disposition": "QUIESCENT",
            "evidence": self.claim["evidence"][:1],
        }
        n.validate_progress(
            {"authority_context": context},
            {"coverage": "COMPLETE", "rows": rows},
            self.row,
            claim,
            {"assignments": []},
            [claim],
        )

    def test_a_non_mapping_retained_read_leaves_the_context_incomplete(self) -> None:
        # CodeAnt 4590772769: skipping the read must not keep COMPLETE coverage.
        self.quiescent(self.context, [self.row])
        for bad in ("text", ["x"], 7, None):
            context = {**self.context, "https://github.com/ktogias/gnostoa/pull/9": bad}
            with (
                self.subTest(bad=bad),
                self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS quiescence"),
            ):
                self.quiescent(context, [self.row])

    def test_a_row_outside_the_captured_frontier_is_never_discharged(self) -> None:
        # CodeAnt 4590772777: ASSIGNED and QUIESCENT need the row in the frontier.
        other = n.progress_row({"kind": "work_item", "ref": "issue:497"}, [])
        with self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS the captured"):
            self.quiescent(self.context, [other])
        context = copy.deepcopy(self.context)
        with self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS the captured"):
            n.validate_progress(
                {"authority_context": context},
                {"coverage": "COMPLETE", "rows": [other]},
                self.row,
                self.claim,
                {"assignments": [{"operation": {"operation_target": "pr:600"}}]},
                [self.claim],
            )

    def test_a_row_with_a_captured_id_but_other_content_is_never_discharged(
        self,
    ) -> None:
        # cubic 4591884412: the whole captured row must match, not only its id.
        altered = {**self.row, "source_sha256": "not-captured"}
        with self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS the captured"):
            self.quiescent_row(altered)

    def quiescent_row(self, row: n.Native) -> None:
        claim: n.Native = {
            "id": self.row["id"],
            "disposition": "QUIESCENT",
            "evidence": self.claim["evidence"][:1],
        }
        n.validate_progress(
            {"authority_context": self.context},
            {"coverage": "COMPLETE", "rows": [self.row]},
            row,
            claim,
            {"assignments": []},
            [claim],
        )

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
            ({"state": "closed", "merge_commit_sha": "c" * 40}, True),
            # The provider sets a test-merge commit on an open PR: that is not closed.
            ({"state": "open", "merge_commit_sha": "c" * 40}, False),
            ({"state": "open", "merged": False, "merge_commit_sha": "c" * 40}, False),
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

    def test_a_captured_read_with_an_unexpected_state_closes_its_target(self) -> None:
        for state in ("draft", "locked", "unknown", "  ", "opened", "reopen"):
            with self.subTest(state=state):
                self.assertEqual(
                    github.closed_reads(
                        {self.pull: {"kind": "pr", "number": 600, "state": state}}
                    ),
                    (Ref("pr", "600"),),
                )

    def test_a_retained_source_without_a_state_stays_assignable(self) -> None:
        self.assertEqual(github.closed_targets([{"kind": "pr", "pr_number": 600}]), ())

    def test_an_open_retained_source_with_a_test_merge_commit_is_assignable(
        self,
    ) -> None:
        source: n.Native = {
            "kind": "pr",
            "pr_number": 600,
            "head_sha": HEAD,
            "state": "open",
            "merged": False,
            "merge_commit_sha": "c" * 40,
        }
        self.row = n.progress_row({"kind": "work_item", "ref": "issue:496"}, [source])
        self.claim["id"] = self.row["id"]
        self.validate(self.context)
        self.row["sources"][0].update(state="closed", merged=True)
        with self.assertRaisesRegex(ValueError, "never dispatches a closed PR"):
            self.validate(self.context)

    def test_an_unmapped_core_refusal_keeps_its_code_and_its_kind(self) -> None:
        refusal = core.ProgressError("future_code")
        with (
            mock.patch.object(core, "validate_result", side_effect=refusal),
            self.assertRaises(ValueError) as raised,
        ):
            self.validate(self.context)
        self.assertEqual(str(raised.exception), "PROJECT_PROGRESS future_code")
        self.assertIs(raised.exception.__cause__, refusal)


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

    def test_a_read_number_is_a_canonical_ascii_provider_number(self) -> None:
        pull = "https://github.com/ktogias/gnostoa/pull/500"
        other_script = "5" + chr(0x665)  # ARABIC-INDIC DIGIT FIVE
        for number in (500, "500"):
            with self.subTest(number=number):
                self.assertEqual(
                    Ref("pr", "500"),
                    github.read_ref("opaque", {"kind": "pr", "number": number}),
                )
        for raw in (other_script, "0500", "0", 0, True, 5.0, -5, " 500"):
            held: n.Native = {"kind": "pr", "number": raw}
            with self.subTest(number=raw):
                # A number that is not canonical names nothing by itself ...
                self.assertIsNone(github.read_ref("opaque", held))
                # ... and the read's own URL still decides, as for an absent number.
                self.assertEqual(Ref("pr", "500"), github.read_ref(pull, held))

    def test_a_gate_subject_names_a_positive_provider_number(self) -> None:
        self.assertTrue(github.valid_subject({"pr_number": 500, "head_sha": HEAD}))
        for number in (0, -1, -500, True, "500", 5.0, None):
            with self.subTest(number=number):
                self.assertFalse(
                    github.valid_subject({"pr_number": number, "head_sha": HEAD})
                )

    def test_no_wait_binding_is_emitted_for_a_zero_or_negative_subject(self) -> None:
        claim: n.Native = {
            "id": "row-m16",
            "disposition": "WAITING",
            "resume_event": "native_exact_head_review",
            "owner": "human:ktogias",
            "evidence_sha256": "source-digest",
        }
        for number, bound in ((500, True), (0, False), (-500, False)):
            row: n.Native = {
                "id": "row-m16",
                "kind": "HUMAN_MERGE",
                "source_kind": "canonical_criterion",
                "canonical": {"criterion": "M16"},
                "source_sha256": "source-digest",
                "subject": {"pr_number": number, "head_sha": HEAD},
            }
            with self.subTest(number=number):
                binding = n.gate_binding({}, row, claim)
                self.assertEqual(binding is not None, bound)


class MergedAttributeChangeTests(unittest.TestCase):
    def test_a_changed_merged_flag_is_a_captured_source_change(self) -> None:
        pointer = "https://github.com/ktogias/gnostoa/pull/500"
        captured: n.Native = {
            "kind": "pr",
            "number": 500,
            "coverage": "CURRENT",
            "body_sha256": "opaque-digest",
            "body_complete": True,
            "observed_at": 1.0,
            "state": "open",
            "merged": False,
        }
        unchanged = dict(captured)
        self.assertIsNone(
            n.source_changes({pointer: captured}, {pointer: unchanged}, [pointer])
        )
        fresh = {**captured, "merged": True}
        self.assertEqual(
            n.source_changes({pointer: captured}, {pointer: fresh}, [pointer]),
            ("REPAIR_PENDING", "captured source changed: " + pointer),
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
        for provider_id in (455, None, "457", True):
            with self.subTest(provider_id=provider_id):
                self.assertIsNone(self.resume(provider_id))

    def test_captured_check_run_resumes_only_with_changed_verdict_and_provider_at_after_gate(
        self,
    ) -> None:
        valid_payload = {"item": {"head_sha": HEAD, "updated_at": _iso(NOW + 0.5)}}
        self.assertEqual(
            self.resume(456, payload=valid_payload),
            "MERGE_ADMISSION_CHANGE",
        )
        # refuses same-run replay (material in seen)
        fact: n.Native = {"head": HEAD, "provider_id": 456}
        record = {**self.record, "payload": valid_payload}
        self.assertIsNone(
            n.gate_resume(
                self.gate,
                record,
                fact,
                NOW + 2,
                changed=True,
                seen=("one-verdict",),
            )
        )
        # refuses unchanged verdict (changed=False / not advances)
        self.assertIsNone(
            n.gate_resume(self.gate, record, fact, NOW + 2, changed=False)
        )
        # refuses missing provider_at
        self.assertIsNone(
            self.resume(456, payload={"item": {"head_sha": HEAD}})
        )
        # refuses provider_at <= gate.at
        self.assertIsNone(
            self.resume(
                456,
                payload={"item": {"head_sha": HEAD, "updated_at": _iso(NOW)}},
            )
        )
        self.assertIsNone(
            self.resume(
                456,
                payload={"item": {"head_sha": HEAD, "updated_at": _iso(NOW - 1)}},
            )
        )
        # refuses provider_at > observed_at
        self.assertIsNone(
            self.resume(
                456,
                payload={"item": {"head_sha": HEAD, "updated_at": _iso(NOW + 1.5)}},
            )
        )
        # refuses lower sequence
        self.assertIsNone(self.resume(455, payload=valid_payload))

    def test_github_check_completion_is_the_provider_time_for_the_captured_run(
        self,
    ) -> None:
        item = {
            "head_sha": HEAD,
            "status": "completed",
            "completed_at": _iso(NOW + 0.5),
        }
        self.assertEqual(
            self.resume(456, payload={"item": item}), "MERGE_ADMISSION_CHANGE"
        )

        for completion in (None, "invalid", _iso(NOW), _iso(NOW + 1.5)):
            with self.subTest(completion=completion):
                invalid = {
                    **item,
                    "completed_at": completion,
                    "updated_at": _iso(NOW + 0.5),
                }
                self.assertIsNone(self.resume(456, payload={"item": invalid}))

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

    def test_same_check_on_three_prs_only_resumes_the_matching_pr(self) -> None:
        item = {"head_sha": HEAD, "completed_at": _iso(NOW + 0.5)}
        fact = {"head": HEAD, "provider_id": 456}
        numbers = (18, 46, 97)
        for number in numbers:
            gate = {
                **self.gate,
                "resume_subject": {"pr_number": number, "head_sha": HEAD},
            }
            for observed_pr in numbers:
                with self.subTest(number=number, observed_pr=observed_pr):
                    record = {
                        **self.record,
                        "number": observed_pr,
                        "payload": {"item": item},
                    }
                    result = n.gate_resume(gate, record, fact, NOW + 2, changed=True)
                    expected = "MERGE_ADMISSION_CHANGE" if observed_pr == number else None
                    self.assertEqual(result, expected)

    def test_shared_policy_accepts_scoped_facts_from_different_adapters(self) -> None:
        github_pr = github.subject_ref({"pr_number": 18})
        other_change = Ref("change_request", "alternate:team/project:18")
        github_time = github.resume_event_time(
            "check_verdict", {"completed_at": _iso(NOW + 0.5)}
        )
        other_payload = {"finished_millis": int((NOW + 0.5) * 1000)}
        inputs = (
            (github_pr, github_time),
            (other_change, other_payload["finished_millis"] / 1000),
        )
        for subject, _ in inputs:
            gate = core.ResumeGate(subject, HEAD, "source", NOW, 456)
            for observed_subject, event_time in inputs:
                with self.subTest(subject=subject, observed_subject=observed_subject):
                    fact = core.ResumeFact(
                        observed_subject,
                        HEAD,
                        "verdict",
                        NOW + 1,
                        event_time,
                        456,
                        "source",
                        True,
                    )
                    self.assertEqual(
                        core.gate_resume(gate, fact, NOW + 2),
                        observed_subject == subject,
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
                self.assertEqual(expected, (decision.action, decision.reason))


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


class MalformedRecordBoundaryTests(unittest.TestCase):
    def test_a_malformed_request_record_is_one_named_refusal(self) -> None:
        store, obligation = _journal({"key": "k", "at": _iso(NOW)})
        with mock.patch.object(
            core, "request_budget", wraps=core.request_budget
        ) as budget:
            n.request_budget(store, obligation, NOW)
        # The budget is handed the record's own key and instant, read once.
        stamps = (core.RequestStamp("k", NOW, False),)
        self.assertEqual(budget.call_args.args[:2], (stamps, stamps))
        for name, record in (
            ("no time", {"key": "k"}),
            ("no key", {"at": _iso(NOW)}),
            ("bad time", {"key": "k", "at": "not-a-time"}),
            ("null time", {"key": "k", "at": None}),
            ("naive time", {"key": "k", "at": "2027-01-15T08:00:00"}),
            ("naive date", {"key": "k", "at": "2027-01-15"}),
        ):
            store, obligation = _journal(record)
            with (
                self.subTest(name),
                self.assertRaisesRegex(ValueError, _BAD_REQUEST_RECORD),
            ):
                n.request_budget(store, obligation, NOW)

    def test_a_malformed_assignment_is_refused_inside_the_value_error_boundary(
        self,
    ) -> None:
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        claim: n.Native = {"id": row["id"], "disposition": "REFRESH", "need": []}
        frontier: n.Native = {"coverage": "COMPLETE", "rows": [row]}
        for name, decoded in (
            ("not a mapping", {"assignments": ["x"]}),
            ("no operation", {"assignments": [{}]}),
            ("operation not a mapping", {"assignments": [{"operation": 7}]}),
            ("null entry", {"assignments": [None]}),
            ("not a list", {"assignments": None}),
            ("absent", {}),
        ):
            with (
                self.subTest(name),
                self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"),
            ):
                n.validate_progress({}, frontier, row, claim, decoded, [claim])


class InvalidRequestHistoryTests(unittest.TestCase):
    """An invalid journal request holds every caller before any intent or egress."""

    INVALID = (
        ("missing time", {"key": "bad", "state": "SENT"}),
        ("malformed time", {"key": "bad", "state": "SENT", "at": "yesterday"}),
        ("naive time", {"key": "bad", "state": "SENT", "at": "2027-01-15T08:00:00"}),
    )

    def setUp(self) -> None:
        self.scope: n.Native = {"kind": "work_item", "ref": "issue:499"}

    def test_the_budget_and_the_decision_refuse_and_keep_the_journal(self) -> None:
        for name, record in self.INVALID:
            obligation = n.new_obligation("opaque-id", self.scope, NOW)
            obligation["requests"] = [dict(record)]
            held = copy.deepcopy(obligation)
            store: n.Native = {"opaque-id": obligation}
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS a request"):
                    n.request_budget(store, obligation, NOW + 1)
                with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS a request"):
                    n.controller_decision(
                        obligation,
                        fate="DISCHARGE",
                        reason="ASSIGNED",
                        touched=True,
                        linked_open=False,
                        source_router_open=False,
                        now=NOW + 1,
                        obligations=store,
                        current_input="new",
                        last_input="old",
                    )
                self.assertEqual(obligation, held)

    def test_a_peer_obligations_invalid_history_also_holds_the_budget(self) -> None:
        good = n.new_obligation("good", self.scope, NOW)
        peer = n.new_obligation("peer", {"kind": "work_item", "ref": "issue:7"}, NOW)
        peer["requests"] = [{"key": "bad", "state": "SENT", "at": "yesterday"}]
        with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS a request"):
            n.request_budget({"good": good, "peer": peer}, good, NOW + 1)

    def test_a_migration_refuses_keeps_both_records_and_resumes_when_repaired(
        self,
    ) -> None:
        for name, record in self.INVALID:
            store: n.Native = {}
            old, _, _ = n.open_obligation(
                store, {"kind": "work_item", "ref": None}, [], "old", NOW
            )
            old["requests"] = [dict(record)]
            held = copy.deepcopy(old)
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS a request"):
                    n.migrate(store, old, self.scope, NOW + 1)
                # The unbound obligation is neither tombstoned nor rewritten.
                self.assertEqual(old, held)
                self.assertEqual(old["status"], "OPEN")
                self.assertNotIn("superseded_by", old)
                # A replay after the record is repaired completes the migration.
                old["requests"][0]["at"] = _iso(NOW)
                bound = n.migrate(store, old, self.scope, NOW + 2)
                self.assertEqual(old["status"], "MIGRATED")
                self.assertEqual([r["key"] for r in bound["requests"]], ["bad"])
                self.assertEqual(bound["requests"][0]["carried_from"], old["id"])


class FailClosedHistoryMatrixTests(unittest.TestCase):
    """Every unreadable journal shape holds all three entry points, unchanged."""

    def setUp(self) -> None:
        self.SCOPE: n.Native = {"kind": "work_item", "ref": "issue:499"}

    BAD = (
        ("at missing", {"key": "k"}),
        ("at null", {"key": "k", "at": None}),
        ("at unparseable", {"key": "k", "at": "yesterday"}),
        ("at naive", {"key": "k", "at": "2027-01-15T08:00:00"}),
        ("at date-only", {"key": "k", "at": "2027-01-15"}),
        ("at integer", {"key": "k", "at": 1800000000}),
        ("key missing", {"at": _iso(NOW)}),
        ("key null", {"key": None, "at": _iso(NOW)}),
        ("key empty", {"key": "", "at": _iso(NOW)}),
        ("key number", {"key": 7, "at": _iso(NOW)}),
        ("record string", "oops"),
        ("record null", None),
    )

    def test_each_bad_record_refuses_budget_decision_and_migration(self) -> None:
        for name, record in self.BAD:
            for last in (False, True):
                requests: list[Any] = [{"key": "ok", "at": _iso(NOW - 5)}]
                requests.insert(len(requests) if last else 0, record)
                obligation = n.new_obligation("o", self.SCOPE, NOW)
                obligation["requests"] = requests
                store: n.Native = {"o": obligation}
                held = copy.deepcopy(store)
                with self.subTest(name, last=last):
                    with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
                        n.request_budget(store, obligation, NOW)
                    with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
                        _retry_decision(obligation, store)
                    unbound = n.new_obligation("u", {"kind": "work_item"}, NOW)
                    unbound["requests"] = copy.deepcopy(requests)
                    migration: n.Native = {}
                    kept = copy.deepcopy(unbound)
                    with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
                        n.migrate(migration, unbound, self.SCOPE, NOW)
                    self.assertEqual(unbound, kept)
                    self.assertEqual(migration, {})
                    self.assertEqual(store, held)

    def test_a_bound_side_bad_record_leaves_the_obligations_untouched(self) -> None:
        bound = n.new_obligation(n.scope_identity(self.SCOPE), self.SCOPE, NOW)
        bound["requests"] = [{"key": "k", "at": "2027-01-15T08:00:00"}]
        unbound = n.new_obligation("u", {"kind": "work_item"}, NOW)
        unbound["requests"] = [{"key": "u", "at": _iso(NOW - 9)}]
        store: n.Native = {bound["id"]: bound}
        records = (store, unbound)
        held = copy.deepcopy(records)
        with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
            n.migrate(store, unbound, self.SCOPE, NOW)
        self.assertEqual(records, held)

    def test_requests_missing_or_null_refuse_without_a_raw_error(self) -> None:
        for name in ("missing", "null", "mapping"):
            obligation = n.new_obligation("o", self.SCOPE, NOW)
            if name == "missing":
                del obligation["requests"]
            else:
                obligation["requests"] = None if name == "null" else {}
            store: n.Native = {"o": obligation}
            held = copy.deepcopy(store)
            with self.subTest(name):
                with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
                    n.request_budget(store, obligation, NOW)
                with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
                    _retry_decision(obligation, store)
                self.assertEqual(store, held)

    def test_a_corrupt_peer_holds_every_obligation_until_repaired(self) -> None:
        good = n.new_obligation("g", self.SCOPE, NOW)
        peer = n.new_obligation("p", {"kind": "work_item", "ref": "issue:7"}, NOW)
        peer["requests"] = [{"key": "p", "at": "2027-01-15"}]
        store: n.Native = {"g": good, "p": peer}
        held = copy.deepcopy(store)
        for _ in range(2):  # a restart replays the same refusal
            with self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"):
                _retry_decision(good, store)
            self.assertEqual(store, held)
        peer["requests"][0]["at"] = _iso(NOW - 5)
        self.assertEqual(_retry_decision(good, store)[0], "REQUEST")

    def test_an_overflowing_timestamp_is_one_named_refusal(self) -> None:
        store, obligation = _journal({"key": "k", "at": _iso(NOW)})
        with mock.patch.object(n, "datetime") as clock:
            clock.fromisoformat.return_value.timestamp.side_effect = OverflowError
            clock.fromisoformat.return_value.tzinfo = UTC
            with self.assertRaisesRegex(ValueError, _BAD_REQUEST_RECORD):
                n.request_budget(store, obligation, NOW)


class DecodedResultShapeTests(unittest.TestCase):
    """A malformed decoded result is one PROJECT_PROGRESS refusal in every mode."""

    def test_each_malformed_shape_is_refused_in_every_mode(self) -> None:
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        frontier: n.Native = {"coverage": "COMPLETE", "rows": [row]}
        target = {"operation_target": "pr:1"}
        shapes: tuple[tuple[str, Any], ...] = (
            ("decoded null", None),
            ("decoded list", []),
            ("decoded string", "x"),
            ("assignments absent", {}),
            ("assignments null", {"assignments": None}),
            ("assignments mapping", {"assignments": {}}),
            ("assignments string", {"assignments": "x"}),
            ("assignments tuple", {"assignments": ()}),
            ("entry string", {"assignments": ["x"]}),
            ("entry null", {"assignments": [None]}),
            ("entry list", {"assignments": [[]]}),
            ("entry empty", {"assignments": [{}]}),
            ("operation null", {"assignments": [{"operation": None}]}),
            ("operation list", {"assignments": [{"operation": []}]}),
            ("operation string", {"assignments": [{"operation": "x"}]}),
            ("operation number", {"assignments": [{"operation": 3}]}),
            (
                "one bad beside a valid one",
                {"assignments": [{"operation": target}, "x"]},
            ),
        )
        for mode in ("ASSIGNED", "WAITING", "REFRESH", "QUIESCENT"):
            claim: n.Native = {"id": row["id"], "disposition": mode, "need": []}
            for name, decoded in shapes:
                inputs = (frontier, claim)
                held = copy.deepcopy(inputs)
                with (
                    self.subTest(mode=mode, shape=name),
                    self.assertRaisesRegex(ValueError, "PROJECT_PROGRESS"),
                ):
                    n.validate_progress({}, frontier, row, claim, decoded, [claim])
                self.assertEqual(inputs, held)

    def test_an_unparseable_operation_target_is_refused(self) -> None:
        scope: n.Native = {"kind": "work_item", "ref": "issue:499"}
        row = n.progress_row(scope, [])
        frontier: n.Native = {"coverage": "COMPLETE", "rows": [row]}
        values: tuple[Any, ...] = (None, 7, {}, "garbage", "pr:")
        for mode in ("ASSIGNED", "WAITING", "REFRESH", "QUIESCENT"):
            claim: n.Native = {"id": row["id"], "disposition": mode, "need": []}
            for value in values:
                decoded: n.Native = {
                    "assignments": [{"operation": {"operation_target": value}}]
                }
                with (
                    self.subTest(mode=mode, value=value),
                    self.assertRaisesRegex(ValueError, "supported operation_target"),
                ):
                    n.validate_progress({}, frontier, row, claim, decoded, [claim])


_SUBJECT: n.Native = {"pr_number": 500, "head_sha": HEAD}
_BAD_SHAPES: tuple[Any, ...] = ("text", ["x"], 7, True)


def _refresh(job: n.Native, row: n.Native) -> None:
    claim: n.Native = {"id": row["id"], "disposition": "REFRESH", "reason": "again"}
    decoded: n.Native = {"assignments": [{"operation": {"operation_target": "pr:500"}}]}
    n.validate_progress(
        job, {"coverage": "COMPLETE", "rows": [row]}, row, claim, decoded, [claim]
    )


def _resume_gate() -> n.Native:
    binding = n.gate_binding(
        {},
        {
            "id": "gate",
            "kind": "HUMAN_MERGE",
            "source_kind": "canonical_criterion",
            "subject": _SUBJECT,
            "source_sha256": "captured",
            "canonical": {"criterion": "M16"},
        },
        {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "captured",
        },
    )
    assert binding is not None
    return {**binding, "at": NOW}


def _resume_review(gate: n.Native, payload: Any) -> str | None:
    record: n.Native = {
        "kind": "review",
        "number": 500,
        "material_id": "m",
        "observed_at": NOW + 2,
        "payload": payload,
    }
    return n.gate_resume(
        gate, record, {"head": HEAD, "provider_id": 9}, NOW + 3, owner_review=True
    )


class OwnerReviewShapeBoundaryTests(unittest.TestCase):
    """Owner review 5921808537: malformed native shapes stay inside the boundary."""

    def test_a_truthy_non_mapping_native_field_is_one_named_refusal(self) -> None:
        row = n.progress_row({"kind": "work_item", "ref": "issue:499"}, [])
        job: n.Native = {"continuation_contract": {"frontier_sha256": "lineage"}}
        _refresh(job, row)
        for bad in _BAD_SHAPES:
            for owner, field in (
                (job, "continuation_contract"),
                (row, "sources"),
                (row, "scope"),
            ):
                if field == "sources" and isinstance(bad, list):
                    continue  # a list is the table's own shape for sources
                held = copy.deepcopy(job)
                held_row = copy.deepcopy(row)
                (held if owner is job else held_row)[field] = bad
                with (
                    self.subTest(field=field, bad=bad),
                    self.assertRaisesRegex(ValueError, "^PROJECT_PROGRESS "),
                ):
                    _refresh(held, held_row)

    def test_a_non_mapping_canonical_or_payload_never_resumes_or_raises(self) -> None:
        item = {"commit_id": HEAD, "submitted_at": _iso(NOW + 1)}
        gate = _resume_gate()
        self.assertEqual(_resume_review(gate, {"item": item}), "OWNER_REVIEW")
        for bad in _BAD_SHAPES:
            with self.subTest(bad=bad):
                self.assertIsNone(
                    _resume_review({**gate, "canonical": bad}, {"item": item})
                )
                self.assertIsNone(_resume_review(gate, bad))
                self.assertIsNone(_resume_review(gate, {"item": bad}))

    def test_a_held_row_is_matched_on_its_whole_canonical_binding(self) -> None:
        held: n.Native = {
            "id": "gate",
            "kind": "TECHNICAL",
            "source_kind": "canonical_criterion",
            "source_key": "k",
            "subject": _SUBJECT,
            "source_sha256": "evidence",
            "canonical": {"check_run_id": 456},
        }
        claim: n.Native = {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "provider:canonical-gate",
            "resume_event": "provider_source_changed",
            "evidence_sha256": "evidence",
            "check_run_id": 456,
        }
        job: n.Native = {"continuation_frontier": {"rows": [held]}}
        self.assertIsNotNone(n.gate_binding(job, dict(held), claim))
        for name, other in {
            "source kind": {**held, "source_kind": "native_outcome"},
            "source key": {**held, "source_key": "other"},
            "canonical": {**held, "canonical": {"check_run_id": 456, "extra": 1}},
            "missing key": {k: v for k, v in held.items() if k != "source_key"},
        }.items():
            with self.subTest(name=name):
                self.assertIsNone(n.gate_binding(job, other, claim))

    def test_a_damaged_held_wait_table_never_yields_a_unique_owner(self) -> None:
        dependency = {"pr_number": 600, "head_sha": "b" * 40}
        dependency_wait: n.Native = {
            "subject": _SUBJECT,
            "dependency": dependency,
            "evidence_sha256": "evidence",
            "check_run_id": 123,
        }
        review_claim: n.Native = {
            "id": "gate",
            "disposition": "WAITING",
            "owner": "human:ktogias",
            "resume_event": "native_exact_head_review",
            "evidence_sha256": "evidence",
            "dependency_pr_number": 600,
            "dependency_head_sha": "b" * 40,
        }
        gate_row: n.Native = {
            "id": "gate",
            "kind": "TECHNICAL",
            "source_kind": "canonical_criterion",
            "subject": _SUBJECT,
            "source_sha256": "evidence",
            "canonical": {"check_run_id": 456},
        }
        native: n.Native = {
            "id": "native",
            "kind": "UNFINISHED",
            "source_kind": "native_outcome",
            "subject": _SUBJECT,
            "source_key": "delivery:1",
            "source_sha256": "native-sha",
        }
        provider_wait: n.Native = {
            "subject": _SUBJECT,
            "source_key": "delivery:1",
            "source_sha256": "native-sha",
            "obligation_ids": ["gate"],
            "observed_check_run_id": 456,
        }
        check_claim: n.Native = {
            "id": "native",
            "disposition": "WAITING",
            "owner": "provider:canonical-gate",
            "resume_event": "provider_source_changed",
            "evidence_sha256": "evidence",
            "check_run_id": 456,
        }

        def review(waits: list[Any]) -> n.Native | None:
            frontier = {"dependency_waits": waits}
            return n.gate_binding(
                {"continuation_frontier": frontier}, gate_row, review_claim
            )

        def native_bind(waits: list[Any], rows: list[Any]) -> n.Native | None:
            frontier = {"rows": rows, "provider_waits": waits}
            return n.gate_binding(
                {"continuation_frontier": frontier}, native, check_claim
            )

        self.assertIsNotNone(review([dependency_wait]))
        # CodeAnt 4591961227: a wait for another digest is not this row's wait.
        borrowed = {**dependency_wait, "evidence_sha256": "other"}
        borrowing = {**review_claim, "evidence_sha256": "other"}
        self.assertIsNone(
            n.gate_binding(
                {"continuation_frontier": {"dependency_waits": [borrowed]}},
                gate_row,
                borrowing,
            )
        )
        self.assertIsNotNone(native_bind([provider_wait], [gate_row]))
        for junk in (None, 7, "text", ["x"]):
            with self.subTest(junk=junk):
                self.assertIsNone(review([dependency_wait, junk]))
                self.assertIsNone(native_bind([provider_wait, junk], [gate_row]))
                self.assertIsNone(native_bind([provider_wait], [gate_row, junk]))


if __name__ == "__main__":
    unittest.main()
