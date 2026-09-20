from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any
from unittest import mock


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

    def test_publish_updates_prior_render_in_place(self) -> None:
        fixtures = _fixtures()
        adapter = fixtures._adapter()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
        outer = {
            "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
            "runtime_revision": "9" * 40,
        }
        existing_projection = reducer.build_projection(
            snapshot,
            protected_main_revision="e" * 40,
            outer_consumer=outer,
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
        candidate_projection = reducer.build_projection(
            snapshot,
            protected_main_revision="e" * 40,
            outer_consumer=outer,
            r2a_result={
                "outcome": "INCOMPLETE",
                "reason": "QUORUM_UNMET",
                "binding": False,
            },
            execution={
                "execution_id": "github-actions:281:1",
                "observed_at": "2026-09-19T16:42:10Z",
            },
        )
        current_checks = (
            "ambiguous=0 (+0 omitted), pending=0 (+0 omitted), "
            "non-success=0 (+0 omitted)"
        )
        prior_render = reducer.render_projection(existing_projection).replace(
            current_checks,
            "ambiguous=0, pending=0, non-success=0",
        )
        candidate_body = reducer.render_projection(candidate_projection)
        current_pr = {
            "state": "open",
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "merge_base_sha": "c" * 40,
        }
        client = mock.Mock()
        protected = mock.Mock(protected_main_revision="e" * 40)

        with (
            mock.patch.object(adapter, "_current_pr", return_value=current_pr),
            mock.patch.object(
                adapter,
                "_protected_state",
                return_value=(protected, protected),
            ),
            mock.patch.object(
                adapter,
                "_collect_pages",
                return_value=(
                    [
                        {
                            "id": 77,
                            "author": adapter._PROJECTION_AUTHOR,
                            "body": prior_render,
                        }
                    ],
                    {"status": "COMPLETE", "pages": 1, "count": 1},
                ),
            ),
        ):
            result = adapter.publish_entry(
                client,
                repository="ktogias/gnostoa",
                entry={
                    "pull_number": 300,
                    "head_sha": "a" * 40,
                    "body": candidate_body,
                },
            )

        self.assertEqual(
            {"pull_number": 300, "published": True, "reason": "UPDATED"},
            result,
        )
        client.post.assert_not_called()
        client.patch.assert_called_once_with(
            "https://api.github.com/repos/ktogias/gnostoa/issues/comments/77",
            {"body": candidate_body},
        )


if __name__ == "__main__":
    unittest.main()
