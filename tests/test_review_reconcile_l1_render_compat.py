from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


def _fixtures() -> Any:
    """Reuse source-bound L1 fixtures independently of discovery's sys.path."""
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location("l1_render_compat_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UsefulL1RenderCompatibilityTests(unittest.TestCase):
    def test_owned_prior_render_remains_replaceable_from_valid_semantics(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        projection = reducer.build_projection(
            fixtures._snapshot(),
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result={
                "outcome": "INCOMPLETE",
                "reason": "QUORUM_UNMET",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:280:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        canonical = reducer.render_projection(projection)
        current_checks = (
            "ambiguous=0 (+0 omitted), pending=0 (+0 omitted), "
            "non-success=0 (+0 omitted)"
        )
        prior_checks = "ambiguous=0, pending=0, non-success=0"
        self.assertIn(current_checks, canonical)
        prior_render = canonical.replace(current_checks, prior_checks)
        self.assertNotEqual(canonical, prior_render)

        # The embedded document is the durable semantic identity. Presentation
        # produced by an earlier renderer remains valid ownership evidence.
        self.assertEqual(
            projection,
            reducer.parse_projection_comment(prior_render),
        )

        existing = adapter._existing_projection(
            [
                {
                    "id": 77,
                    "author": adapter._PROJECTION_AUTHOR,
                    "body": prior_render,
                }
            ],
            repository="ktogias/gnostoa",
            pull_number=300,
        )

        self.assertIsNotNone(existing)
        self.assertEqual(77, existing[0])
        self.assertEqual(projection, existing[1])


if __name__ == "__main__":
    unittest.main()
