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

    def test_current_and_legacy_retained_check_bounds_are_explicit(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()
        snapshot = fixtures.snapshot_fixture()
        projection = reducer.build_projection(
            snapshot,
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
                "execution_id": "github-actions:281:1",
                "observed_at": "2026-09-19T16:42:10Z",
            },
        )

        strict_over_bound = dict(projection)
        strict_over_bound["checks"] = {
            "observed_names": 9,
            "ambiguous": [],
            "pending": [],
            "non_success": [f"strict-check-{index}" for index in range(9)],
            "omitted_ambiguous": 0,
            "omitted_pending": 0,
            "omitted_non_success": 0,
        }
        strict_over_bound["next_permitted_action"] = "RECONCILE_PROVIDER_CHECKS"
        strict_body = reducer.render_projection(strict_over_bound)
        self.assertIsNone(reducer.parse_projection_comment(strict_body))

        legacy_max = dict(projection)
        legacy_max["checks"] = {
            "observed_names": 32,
            "ambiguous": [],
            "pending": [],
            "non_success": [f"legacy-check-{index}" for index in range(32)],
            "omitted_ambiguous": 0,
            "omitted_pending": 0,
            "omitted_non_success": 0,
        }
        legacy_max["next_permitted_action"] = "RECONCILE_PROVIDER_CHECKS"
        legacy_body = reducer.render_projection(legacy_max)
        self.assertIsNone(reducer.parse_projection_comment(legacy_body))
        self.assertEqual(
            legacy_max,
            reducer.parse_projection_comment(
                legacy_body,
                allow_legacy_check_bounds=True,
            ),
        )

        legacy_over_bound = dict(legacy_max)
        legacy_over_bound["checks"] = dict(legacy_max["checks"])
        legacy_over_bound["checks"]["observed_names"] = 33
        legacy_over_bound["checks"]["non_success"] = [
            f"legacy-check-{index}" for index in range(33)
        ]
        legacy_over_body = reducer.render_projection(legacy_over_bound)
        self.assertIsNone(
            reducer.parse_projection_comment(
                legacy_over_body,
                allow_legacy_check_bounds=True,
            )
        )

    def test_strict_check_label_byte_bound_is_exact(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures.reducer_fixture()
        projection = reducer.build_projection(
            fixtures.snapshot_fixture(),
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
                "execution_id": "github-actions:281:1",
                "observed_at": "2026-09-19T16:42:10Z",
            },
        )

        for byte_count, accepted in ((128, True), (129, False)):
            with self.subTest(byte_count=byte_count):
                candidate = dict(projection)
                candidate["checks"] = {
                    "observed_names": 1,
                    "ambiguous": [],
                    "pending": [],
                    "non_success": ["x" * byte_count],
                    "omitted_ambiguous": 0,
                    "omitted_pending": 0,
                    "omitted_non_success": 0,
                }
                candidate["next_permitted_action"] = "RECONCILE_PROVIDER_CHECKS"
                rendered = reducer.render_projection(candidate)
                parsed = reducer.parse_projection_comment(rendered)
                if accepted:
                    self.assertEqual(candidate, parsed)
                else:
                    self.assertIsNone(parsed)

    def test_publish_updates_pre_bound_long_check_label_in_place(self) -> None:
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
                "execution_id": "github-actions:282:1",
                "observed_at": "2026-09-19T16:41:10Z",
            },
        )
        existing_projection["checks"] = {
            "observed_names": 40,
            "ambiguous": [],
            "pending": [],
            "non_success": [
                "legacy-check-" + ("x" * 180) if index == 0 else f"legacy-check-{index}"
                for index in range(32)
            ],
            "omitted_ambiguous": 0,
            "omitted_pending": 0,
            "omitted_non_success": 8,
        }
        existing_projection["next_permitted_action"] = "RECONCILE_PROVIDER_CHECKS"
        prior_render = reducer.render_projection(existing_projection)

        # The strict current parser rejects newly supplied over-bound labels.
        self.assertIsNone(reducer.parse_projection_comment(prior_render))

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
                "execution_id": "github-actions:283:1",
                "observed_at": "2026-09-19T16:42:10Z",
            },
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
