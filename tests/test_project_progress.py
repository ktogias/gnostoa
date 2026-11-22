"""Private progress owner: behavior, opaque identities and effect-free decisions."""

from __future__ import annotations

import ast
import unittest
from dataclasses import replace
from pathlib import Path

from tools import project_progress as p
from tools.agent_review_model import Ref


class ProgressOwnerTests(unittest.TestCase):
    def test_opaque_scope_identity_preserves_bound_and_unresolved_history(self) -> None:
        ref = Ref("ticket", "opaque/A-7")
        self.assertEqual(p.scope_identity(ref), p.scope_identity(ref, "ignored"))
        self.assertNotEqual(
            p.scope_identity(Ref("ticket", ""), "a"),
            p.scope_identity(Ref("ticket", ""), "b"),
        )

    def test_sources_deduplicate_and_replace_only_the_selected_generation(self) -> None:
        old = p.Source("selection", None, "old", "g1", True, ("reader", 1))
        completion = p.Source("completion", "opaque-key", "event")
        new = p.Source("selection", None, "new", "g2", True, ("reader", 2))
        merged, added, pending = p.merge_sources((old, completion), (new, completion))
        self.assertTrue(added)
        self.assertFalse(pending)
        self.assertEqual(merged, (completion, new))
        self.assertEqual(
            p.merge_sources(merged, (new, completion)), (merged, False, False)
        )

    def test_late_older_scope_generation_does_not_replace_or_rearm(self) -> None:
        old = p.Source("scope", None, "old", "g1", True, ("reader-a", 1))
        held = p.Source("scope", None, "newer", "g2", True, ("reader-a", 2))
        current, added, pending = p.merge_sources((), (held,))
        self.assertTrue(added)
        self.assertFalse(pending)
        current, added, pending = p.merge_sources(current, (old,))
        self.assertFalse(added)
        self.assertFalse(pending)
        self.assertEqual(current, (held,))
        self.assertEqual(p.opening("DISCHARGED", added), (False, False))

    def test_newer_observation_accepts_a_legitimate_generation_reversion(self) -> None:
        first = p.Source("scope", None, "g1", "g1", True, ("reader-a", 1))
        second = p.Source("scope", None, "g2", "g2", True, ("reader-a", 2))
        reverted = p.Source("scope", None, "g1-again", "g1", True, ("reader-a", 3))
        current, added, pending = p.merge_sources((), (first,))
        self.assertTrue(added)
        self.assertFalse(pending)
        current, added, pending = p.merge_sources(current, (second,))
        self.assertTrue(added)
        self.assertFalse(pending)
        current, added, pending = p.merge_sources(current, (reverted,))
        self.assertTrue(added)
        self.assertFalse(pending)
        self.assertEqual(current, (reverted,))

    def test_missing_or_incomparable_observation_requests_refresh(self) -> None:
        held = p.Source("scope", None, "held", "g2", True, ("reader-a", 2))
        missing = p.Source("scope", None, "missing", "g1", True)
        other_epoch = p.Source("scope", None, "other", "g1", True, ("reader-b", 3))
        equal_order_conflict = p.Source(
            "scope", None, "equal", "g1", True, ("reader-a", 2)
        )
        for incoming in (missing, other_epoch, equal_order_conflict):
            with self.subTest(incoming=incoming):
                current, added, pending = p.merge_sources((held,), (incoming,))
                self.assertFalse(added)
                self.assertTrue(pending)
                self.assertEqual(current, (held,))

    def test_dirty_disposition_never_discharges_and_intent_reemits_same_key(
        self,
    ) -> None:
        self.assertEqual(
            p.decide_transition(
                p.Transition(has_request=True, fate="DISCHARGE", changed=True)
            ).action,
            "REQUEST",
        )
        self.assertEqual(
            p.decide_transition(
                p.Transition(has_request=True, intent=True, hold="IDENTITY_CAP")
            ).action,
            "REEMIT",
        )
        self.assertEqual(
            p.decide_transition(
                p.Transition(has_request=True, fate="DISCHARGE")
            ).action,
            "DISCHARGE",
        )

    def test_pending_refresh_and_actual_source_owner_have_no_added_grace(self) -> None:
        state = p.Transition(
            has_request=True, changed=True, fate="HOLD", reason="PENDING_INGRESS"
        )
        self.assertEqual(p.decide_transition(state).action, "REFRESH_PENDING")
        self.assertEqual(
            p.decide_transition(replace(state, pending_refreshed=True)).action,
            "REFRESHED",
        )
        self.assertEqual(
            p.decide_transition(replace(state, pending_refreshed=False)).action,
            "REQUEST",
        )
        source_hold = p.decide_transition(p.Transition(source_open=True))
        self.assertEqual(
            (source_hold.action, source_hold.reason), ("HOLD", "SOURCE_OWNER_OPEN")
        )
        return_hold = p.decide_transition(p.Transition(return_open=True))
        self.assertEqual(
            (return_hold.action, return_hold.reason), ("HOLD", "SOURCE_RETURN_OPEN")
        )

    def test_rolling_identity_and_daily_budget_preserve_real_reset(self) -> None:
        now = 1_800_000_000.0
        stamps = tuple(p.RequestStamp(str(n), now - n) for n in (1, 2, 3))
        self.assertEqual(p.request_budget(stamps, stamps, now), "IDENTITY_CAP")
        self.assertIsNone(p.request_budget(stamps, stamps, now + 86401))
        carried = tuple(p.RequestStamp(str(n), now - n, True) for n in (1, 2, 3))
        self.assertIsNone(p.request_budget((), carried, now, daily_cap=1))

    def test_future_dated_stamps_do_not_count_in_the_rolling_window(self) -> None:
        now = 1_800_000_000.0
        past = (p.RequestStamp("a", now - 1), p.RequestStamp("b", now - 2))
        future = p.RequestStamp("c", now + 60)
        self.assertEqual(
            p.request_budget((*past, future), (*past, future), now),
            "TIME_MONOTONICITY_HOLD",
        )
        third = p.RequestStamp("d", now - 3)
        self.assertEqual(
            p.request_budget((*past, third, future), (*past, third, future), now),
            "TIME_MONOTONICITY_HOLD",
        )

    def test_future_stamp_same_utc_day_does_not_count_toward_daily_cap(
        self,
    ) -> None:
        now = 1_800_000_000.0
        future = (p.RequestStamp("a", now + 60),)
        self.assertEqual(
            p.request_budget((), future, now, daily_cap=1),
            "TIME_MONOTONICITY_HOLD",
        )
        past = (p.RequestStamp("b", now - 60),)
        self.assertEqual(p.request_budget((), past, now, daily_cap=1), "DAILY_CAP")

    def test_characterization_future_stamp_later_utc_day_not_in_daily_cap(
        self,
    ) -> None:
        now = 1_800_000_000.0
        future = (p.RequestStamp("a", now + 86400),)
        self.assertEqual(
            p.request_budget((), future, now, daily_cap=1),
            "TIME_MONOTONICITY_HOLD",
        )

    def test_characterization_future_stamps_never_count_toward_identity_cap(
        self,
    ) -> None:
        now = 1_800_000_000.0
        # Stamps within jitter (<=5s) are clamped to now for evaluation and count toward identity cap
        jitter = tuple(p.RequestStamp(str(n), now + 1.0) for n in (1, 2, 3))
        self.assertEqual(p.request_budget(jitter, jitter, now, daily_cap=100), "IDENTITY_CAP")
        # Stamps beyond jitter trigger TIME_MONOTONICITY_HOLD
        future = tuple(p.RequestStamp(str(n), now + 10.0 + n) for n in (1, 2, 3))
        self.assertEqual(
            p.request_budget(future, future, now, daily_cap=100),
            "TIME_MONOTONICITY_HOLD",
        )

    def test_future_stamps_absorb_jitter_and_fail_closed_on_large_skew(
        self,
    ) -> None:
        now = 1_800_000_000.0
        # Absorbs jitter <= 5.0s: evaluate virtually within window
        jitter = tuple(p.RequestStamp(str(n), now + 3.0) for n in (1, 2, 3))
        self.assertEqual(p.request_budget(jitter, jitter, now), "IDENTITY_CAP")

        # Gross forward skew > 5.0s: fail closed with explicit monotonic hold
        skew = tuple(p.RequestStamp(str(n), now + 60.0) for n in (1, 2, 3))
        self.assertEqual(p.request_budget(skew, skew, now), "TIME_MONOTONICITY_HOLD")

    def test_future_stamps_exact_threshold_and_utc_midnight(self) -> None:
        # UTC midnight test: 2027-01-15 00:00:00 UTC = 1_800_000_000
        now = 1_800_000_000.0
        # Exact threshold test: 5.0s jitter absorbed, 5.001s skew holds
        exact_border = (p.RequestStamp("1", now + 5.0),)
        self.assertIsNone(p.request_budget(exact_border, exact_border, now))

        over_border = (p.RequestStamp("1", now + 5.001),)
        self.assertEqual(
            p.request_budget(over_border, over_border, now),
            "TIME_MONOTONICITY_HOLD",
        )

        # Carried stamps excluded from daily cap even if jittered
        carried_jitter = (p.RequestStamp("1", now + 2.0, carried=True),)
        self.assertIsNone(p.request_budget((), carried_jitter, now, daily_cap=1))

        # Non-carried jittered stamp within same UTC day counts towards daily cap
        non_carried = (p.RequestStamp("1", now + 2.0, carried=False),)
        self.assertEqual(
            p.request_budget((), non_carried, now, daily_cap=1),
            "DAILY_CAP",
        )

    def test_characterization_unordered_first_scope_source_requests_refresh(
        self,
    ) -> None:
        # Nothing held and no ordering: fail closed, ask for a refresh, add nothing.
        source = p.Source("scope", "k", "fp", "gen", True, None)
        merged, added, refresh = p.merge_sources((), (source,))
        self.assertEqual((merged, added, refresh), ((), False, True))

    @staticmethod
    def evaluation() -> p.Evaluation:
        ref = Ref("ticket", "opaque-A")
        read = p.Read("source-A", ref, "digest-A", 20.0, True, True)
        return p.Evaluation(ref, (read,), (ref,), (), True, True)

    def test_result_assignment_requires_scope_and_target_reads(self) -> None:
        evaluation = self.evaluation()
        result = p.Result(
            "ASSIGNED",
            evidence=(p.Citation("source-A", "digest-A", 20.0),),
            assignment_index=0,
        )
        p.validate_result(evaluation, result)
        scope = Ref("ticket", "scope/opaque-A")
        target = Ref("ticket", "target/opaque-B")
        distinct = p.Evaluation(
            scope,
            (
                p.Read("scope-source", scope, "scope-digest", 20.0, True, True),
                p.Read("target-source", target, "target-digest", 20.0, True, True),
            ),
            (target,),
            (),
            True,
            True,
        )
        bound = p.Result(
            "ASSIGNED",
            assignment_index=0,
            evidence=(
                p.Citation("scope-source", "scope-digest", 20.0),
                p.Citation("target-source", "target-digest", 20.0),
            ),
        )
        p.validate_result(distinct, bound)
        for missing in ("scope", "target"):
            # The remaining citation is valid and captured; only this binding is absent.
            evidence = bound.evidence[1:] if missing == "scope" else bound.evidence[:1]
            unbound = replace(bound, evidence=evidence)
            with (
                self.subTest(missing=missing),
                self.assertRaisesRegex(p.ProgressError, "scope_binding"),
            ):
                p.validate_result(distinct, unbound)
        lineage = p.Citation("lineage", "d", None)
        lineage_only = p.Result("ASSIGNED", evidence=(lineage,), assignment_index=0)
        # The cited lineage is exempt from the read check, yet it binds no scope.
        for reads in ((), evaluation.reads):
            cited_lineage = p.Evaluation(
                evaluation.scope,
                reads,
                evaluation.targets,
                (),
                True,
                True,
                lineage=lineage,
            )
            with (
                self.subTest(reads=len(reads)),
                self.assertRaisesRegex(p.ProgressError, "scope_binding"),
            ):
                p.validate_result(cited_lineage, lineage_only)
        # Beside the scope and target read, the same lineage citation is accepted ...
        with_read = replace(result, evidence=(*result.evidence, lineage))
        p.validate_result(replace(evaluation, lineage=lineage), with_read)
        # ... and without the evaluation's lineage it is an unheld citation.
        with self.assertRaisesRegex(p.ProgressError, "scope_binding"):
            p.validate_result(evaluation, with_read)

    def test_quiescence_and_refresh_are_distinct_and_empty_is_never_progress(
        self,
    ) -> None:
        evaluation = self.evaluation()
        empty = p.Result("")
        with self.assertRaises(p.ProgressError):
            p.validate_result(evaluation, empty)
        needless = p.Result("REFRESH", reason="need evidence")
        with self.assertRaisesRegex(p.ProgressError, "refresh"):
            p.validate_result(evaluation, needless)
        p.validate_result(
            evaluation, p.Result("REFRESH", reason="another source", need=("other",))
        )
        p.validate_result(
            evaluation,
            p.Result("QUIESCENT", evidence=(p.Citation("source-A", "digest-A", 20.0),)),
        )

    def test_changed_or_missing_egress_source_cannot_reuse_the_plan(self) -> None:
        before = self.evaluation().reads[0]
        self.assertIsNone(p.source_changes((before,), (before,)))
        missing = p.source_changes((before,), ())
        assert missing is not None
        self.assertEqual(missing[0], "SOURCE_PENDING")
        changed = p.Read("source-A", before.ref, "other", 30.0, True, True)
        difference = p.source_changes((before,), (changed,))
        assert difference is not None
        self.assertEqual(difference[0], "REPAIR_PENDING")

    def test_core_has_no_host_provider_or_executor_dependencies(self) -> None:
        source = (
            Path(__file__).parents[1] / "tools" / "project_progress.py"
        ).read_text()
        tree = ast.parse(source)
        allowed = {
            "__future__",
            "hashlib",
            "json",
            "collections.abc",
            "dataclasses",
            "datetime",
            "tools.agent_review_model",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertLessEqual({entry.name for entry in node.names}, allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "__import__"})


if __name__ == "__main__":
    unittest.main()
