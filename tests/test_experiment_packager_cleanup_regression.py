from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.experiment import handoff, packaging


class ExperimentPackagerCleanupRegressionTests(unittest.TestCase):
    def test_staging_cleanup_never_unlinks_foreign_replacement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-package-cleanup-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            bundle = root / "bundle"
            freeze_code, freeze_payload = handoff.freeze_handoff(
                source,
                bundle,
                [f"fixture={'a' * 64}"],
            )
            self.assertEqual(0, freeze_code, freeze_payload)

            handoff_path = bundle / "handoff.json"
            original_create_staging = packaging._create_staging
            staging_path: Path | None = None

            def create_then_replace(parent_fd: int) -> tuple[int, str]:
                nonlocal staging_path
                descriptor, name = original_create_staging(parent_fd)
                parent = Path(f"/proc/self/fd/{parent_fd}").resolve()
                staging_path = parent / name
                staging_path.unlink()
                staging_path.write_bytes(b"foreign-staging\n")
                return descriptor, name

            with mock.patch.object(
                packaging,
                "_create_staging",
                side_effect=create_then_replace,
            ):
                exit_code, payload = packaging.create_package(
                    handoff_path,
                    root / "candidate.tar",
                    1_048_576,
                )

            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertIsNotNone(staging_path)
            assert staging_path is not None
            self.assertTrue(staging_path.is_file())
            self.assertEqual(b"foreign-staging\n", staging_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
