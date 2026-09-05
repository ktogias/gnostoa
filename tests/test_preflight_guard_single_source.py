from __future__ import annotations

import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.capsule import compiler


class DeterministicPreEffectGuardTests(unittest.TestCase):
    def test_prepare_routes_both_guard_phases_through_one_helper(self) -> None:
        prepare_source = inspect.getsource(compiler.prepare)
        helper_source = inspect.getsource(compiler._deterministic_pre_effect_blocker)

        self.assertEqual(prepare_source.count("_deterministic_pre_effect_blocker("), 2)
        self.assertNotIn('"oci-qualification-unsupported-for-adapter"', prepare_source)
        self.assertNotIn('"qualification-subject-unavailable"', prepare_source)
        self.assertEqual(
            helper_source.count('"oci-qualification-unsupported-for-adapter"'), 1
        )
        self.assertEqual(helper_source.count('"qualification-subject-unavailable"'), 1)

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
