from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.experiment import handoff, packaging


class ExperimentAtomicPublicationRegressionTests(unittest.TestCase):
    def freeze_fixture(self, root: Path) -> Path:
        source = root / "source"
        source.mkdir()
        (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
        bundle = root / "bundle"
        code, payload = handoff.freeze_handoff(
            source,
            bundle,
            [f"fixture={'a' * 64}"],
        )
        self.assertEqual(0, code, payload)
        return bundle / "handoff.json"

    def test_packager_staging_has_no_filesystem_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-atomic-red-") as raw:
            root = Path(raw)
            parent_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                staging = packaging._create_staging(parent_fd)
                self.assertIsInstance(staging, int)
                self.assertEqual([], list(root.iterdir()))
                os.close(staging)
            finally:
                os.close(parent_fd)

    def test_failed_handoff_retains_uncommitted_owned_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-atomic-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            bundle = root / "bundle"

            def fail_after_snapshot_created(
                _source_root: Path,
                snapshot_fd: int,
            ) -> list[dict[str, object]]:
                snapshot_path = Path(f"/proc/self/fd/{snapshot_fd}").resolve()
                (snapshot_path / "diagnostic.txt").write_text(
                    "partial-owned-state\n", encoding="utf-8"
                )
                raise handoff.HandoffError("forced-uncommitted-freeze")

            with mock.patch.object(
                handoff,
                "_source_members_and_copy_fd",
                side_effect=fail_after_snapshot_created,
            ):
                code, payload = handoff.freeze_handoff(
                    source,
                    bundle,
                    [f"fixture={'a' * 64}"],
                )

            self.assertEqual(2, code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertTrue(bundle.is_dir())
            self.assertEqual(
                "partial-owned-state\n",
                (bundle / "tree" / "diagnostic.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((bundle / "handoff.json").exists())

    def test_post_publication_failure_does_not_roll_back_by_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-atomic-red-") as raw:
            root = Path(raw)
            handoff_path = self.freeze_fixture(root)
            output = root / "candidate.tar"
            real_assert = packaging._assert_visible_parent
            calls = 0

            def fail_after_publication(
                parent_path: Path,
                expected: os.stat_result,
            ) -> None:
                nonlocal calls
                calls += 1
                if calls >= 3:
                    raise packaging.PackageError("forced-post-publication-uncertainty")
                real_assert(parent_path, expected)

            with mock.patch.object(
                packaging,
                "_assert_visible_parent",
                side_effect=fail_after_publication,
            ):
                code, payload = packaging.create_package(
                    handoff_path,
                    output,
                    1_048_576,
                )

            self.assertEqual(2, code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertTrue(
                output.exists(),
                "once create-only publication occurred, uncertainty must not trigger a name-based destructive rollback",
            )


if __name__ == "__main__":
    unittest.main()
