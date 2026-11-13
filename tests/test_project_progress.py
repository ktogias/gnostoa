"""Private progress owner: behavior, opaque identities and effect-free decisions."""

from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path

from tools.agent_review_model import Ref

SPEC = importlib.util.find_spec("tools.project_progress")
if SPEC is not None:
    from tools import project_progress as p


class ProgressOwnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertIsNotNone(SPEC, "no canonical progress owner/consumer API at parent")

    def test_opaque_scope_identity_preserves_bound_and_unresolved_history(self) -> None:
        ref = Ref("ticket", "opaque/A-7")
        self.assertEqual(p.scope_identity(ref), p.scope_identity(ref, "ignored"))
        self.assertNotEqual(
            p.scope_identity(Ref("ticket", ""), "a"),
            p.scope_identity(Ref("ticket", ""), "b"),
        )

    def test_sources_deduplicate_and_replace_only_the_selected_generation(self) -> None:
        old = p.Source("selection", None, "old", "g1", True)
        completion = p.Source("completion", "opaque-key", "event")
        new = p.Source("selection", None, "new", "g2", True)
        merged, added = p.merge_sources((old, completion), (new, completion))
        self.assertTrue(added)
        self.assertEqual(merged, (completion, new))
        self.assertEqual(p.merge_sources(merged, (new, completion)), (merged, False))

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
        state = dict(
            has_request=True, changed=True, fate="HOLD", reason="PENDING_INGRESS"
        )
        self.assertEqual(
            p.decide_transition(p.Transition(**state)).action, "REFRESH_PENDING"
        )
        self.assertEqual(
            p.decide_transition(p.Transition(**state, pending_refreshed=True)).action,
            "REFRESHED",
        )
        self.assertEqual(
            p.decide_transition(p.Transition(**state, pending_refreshed=False)).action,
            "REQUEST",
        )
        self.assertEqual(
            p.decide_transition(p.Transition(source_open=True)).reason,
            "SOURCE_OWNER_OPEN",
        )
        self.assertEqual(
            p.decide_transition(p.Transition(return_open=True)).reason,
            "SOURCE_RETURN_OPEN",
        )

    def test_rolling_identity_and_daily_budget_preserve_real_reset(self) -> None:
        now = 1_800_000_000.0
        stamps = tuple(p.RequestStamp(str(n), now - n) for n in (1, 2, 3))
        self.assertEqual(p.request_budget(stamps, stamps, now), "IDENTITY_CAP")
        self.assertIsNone(p.request_budget(stamps, stamps, now + 86401))
        carried = tuple(p.RequestStamp(str(n), now - n, True) for n in (1, 2, 3))
        self.assertIsNone(p.request_budget((), carried, now, daily_cap=1))

    def evaluation(self) -> p.Evaluation:
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
        with self.assertRaisesRegex(p.ProgressError, "scope_binding"):
            p.validate_result(
                p.Evaluation(evaluation.scope, (), evaluation.targets, (), True, True),
                p.Result(
                    "ASSIGNED",
                    evidence=(p.Citation("lineage", "d", None),),
                    assignment_index=0,
                ),
            )

    def test_quiescence_and_refresh_are_distinct_and_empty_is_never_progress(
        self,
    ) -> None:
        evaluation = self.evaluation()
        with self.assertRaises(p.ProgressError):
            p.validate_result(evaluation, p.Result(""))
        with self.assertRaisesRegex(p.ProgressError, "refresh"):
            p.validate_result(evaluation, p.Result("REFRESH", reason="need evidence"))
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
        self.assertEqual(p.source_changes((before,), ())[0], "SOURCE_PENDING")
        changed = p.Read("source-A", before.ref, "other", 30.0, True, True)
        self.assertEqual(p.source_changes((before,), (changed,))[0], "REPAIR_PENDING")

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
                self.assertTrue({entry.name for entry in node.names} <= allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"open", "exec", "eval", "__import__"})


if __name__ == "__main__":
    unittest.main()
