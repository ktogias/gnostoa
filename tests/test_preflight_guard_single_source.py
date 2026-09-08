from __future__ import annotations

import ast
import inspect
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.capsule import compiler


def _contains_call(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(item, ast.Call)
        and (
            (isinstance(item.func, ast.Name) and item.func.id == name)
            or (isinstance(item.func, ast.Attribute) and item.func.attr == name)
        )
        for item in ast.walk(node)
    )


class DeterministicPreEffectGuardTests(unittest.TestCase):
    def test_prepare_claims_just_in_time_after_candidate_wide_guard_pass(self) -> None:
        prepare_source = inspect.getsource(compiler.prepare)
        helper_source = inspect.getsource(compiler._deterministic_pre_effect_blocker)

        # The candidate-wide fresh-viability pass is the only guard caller. There is
        # no dry-run copy to keep synchronized, and the current refusal codes live
        # only in the helper.
        self.assertEqual(prepare_source.count("_deterministic_pre_effect_blocker("), 1)
        self.assertNotIn('"oci-qualification-unsupported-for-adapter"', prepare_source)
        self.assertNotIn('"qualification-subject-unavailable"', prepare_source)
        self.assertEqual(
            helper_source.count('"oci-qualification-unsupported-for-adapter"'), 1
        )
        self.assertEqual(helper_source.count('"qualification-subject-unavailable"'), 1)

        # The one guard call must live in a separate for-loop before the effect loop.
        # This pins the #206 property: all fresh deterministic viability is settled
        # candidate-wide before the irreversible candidate claim can be opened.
        self.assertEqual(prepare_source.count("claim_fresh_candidate("), 1)
        self.assertEqual(prepare_source.count("qualify_subjects("), 1)
        tree = ast.parse(textwrap.dedent(prepare_source))
        guard_loops = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.For)
            and _contains_call(node, "_deterministic_pre_effect_blocker")
        ]
        effect_loops = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.For) and _contains_call(node, "qualify_subjects")
        ]
        self.assertEqual(len(guard_loops), 1)
        self.assertEqual(len(effect_loops), 1)
        guard_loop = guard_loops[0]
        loop = effect_loops[0]
        self.assertFalse(_contains_call(guard_loop, "qualify_subjects"))
        self.assertFalse(_contains_call(loop, "_deterministic_pre_effect_blocker"))
        self.assertLess(
            prepare_source.index("_deterministic_pre_effect_blocker("),
            prepare_source.index("claim_fresh_candidate("),
        )

        # The decisive whole-candidate settlement must return immediately after the
        # guard loop when any blocker was found. The later in-loop blocker gate is
        # defence-in-depth only; it must not be what makes the pre-pass effective.
        qualification_branches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "not qualification_reused"
            and guard_loop in node.body
        ]
        self.assertEqual(len(qualification_branches), 1)
        qualification_branch = qualification_branches[0]
        guard_index = qualification_branch.body.index(guard_loop)
        self.assertLess(guard_index + 1, len(qualification_branch.body))
        post_guard = qualification_branch.body[guard_index + 1]
        self.assertIsInstance(post_guard, ast.If)
        assert isinstance(post_guard, ast.If)
        self.assertEqual(ast.unparse(post_guard.test), "blockers")
        self.assertEqual(len(post_guard.body), 1)
        self.assertIsInstance(post_guard.body[0], ast.Return)
        assert isinstance(post_guard.body[0], ast.Return)
        self.assertEqual(
            ast.unparse(post_guard.body[0].value),
            "finish(stages.STATIC_QUALIFIED)",
        )
        self.assertEqual(qualification_branch.body[guard_index + 2], loop)

        # The irreversible claim still belongs inside the ordered effect loop. An
        # accumulated blocker is checked immediately before the one-shot claim, and
        # the next top-level statement after that claim block is the first actual
        # qualification effect.
        claim_index = next(
            index
            for index, statement in enumerate(loop.body)
            if _contains_call(statement, "claim_fresh_candidate")
        )
        effect_index = next(
            index
            for index, statement in enumerate(loop.body)
            if _contains_call(statement, "qualify_subjects")
        )
        self.assertEqual(effect_index, claim_index + 1)
        self.assertGreater(claim_index, 0)

        blocker_gate = loop.body[claim_index - 1]
        self.assertIsInstance(blocker_gate, ast.If)
        assert isinstance(blocker_gate, ast.If)
        self.assertEqual(
            ast.unparse(blocker_gate.test), "blockers and (not effect_claimed)"
        )

        # Also close the nested version of the drift: after the claim call succeeds,
        # the claim block may only mark the transaction claimed. A future refusal or
        # other operation inserted inside this block would fail this test even though
        # the top-level claim/effect statements would still look adjacent.
        claim_block = loop.body[claim_index]
        self.assertIsInstance(claim_block, ast.If)
        assert isinstance(claim_block, ast.If)
        self.assertEqual(ast.unparse(claim_block.test), "not effect_claimed")
        self.assertEqual(len(claim_block.body), 2)
        claim_try, claimed_assignment = claim_block.body
        self.assertIsInstance(claim_try, ast.Try)
        assert isinstance(claim_try, ast.Try)
        self.assertEqual(len(claim_try.body), 1)
        self.assertTrue(_contains_call(claim_try.body[0], "claim_fresh_candidate"))
        self.assertIsInstance(claimed_assignment, ast.Assign)
        assert isinstance(claimed_assignment, ast.Assign)
        self.assertEqual(ast.unparse(claimed_assignment.targets[0]), "effect_claimed")
        self.assertEqual(ast.unparse(claimed_assignment.value), "True")

    def test_shared_helper_preserves_current_deterministic_refusals(self) -> None:
        task = SimpleNamespace(id="task", adapter="node-vitest")
        current = SimpleNamespace(
            base_path=Path("/base"), reference_path=Path("/reference")
        )

        self.assertEqual(
            compiler._deterministic_pre_effect_blocker(
                task, current, qualification_backend="oci"
            ),
            {
                "task": "task",
                "code": "oci-qualification-unsupported-for-adapter",
                "detail": (
                    "the OCI result parser is pytest-specific; adapter 'node-vitest' "
                    "has no OCI qualification support in v1"
                ),
            },
        )

        task.adapter = "python-pytest"
        current.base_path = None
        self.assertEqual(
            compiler._deterministic_pre_effect_blocker(
                task, current, qualification_backend="oci"
            ),
            {
                "task": "task",
                "code": "qualification-subject-unavailable",
                "detail": "a materialised subject is missing; nothing can be qualified",
            },
        )

        current.base_path = Path("/base")
        self.assertIsNone(
            compiler._deterministic_pre_effect_blocker(
                task, current, qualification_backend="oci"
            )
        )


if __name__ == "__main__":
    unittest.main()
