from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.experiment import handoff, packaging


class ExperimentPackagerCleanupRegressionTests(unittest.TestCase):
    def test_existing_output_is_never_replaced_and_no_named_staging_is_left(self) -> None:
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

            output = root / "candidate.tar"
            output.write_bytes(b"foreign-output\n")
            exit_code, payload = packaging.create_package(
                bundle / "handoff.json",
                output,
                1_048_576,
            )

            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertEqual(b"foreign-output\n", output.read_bytes())
            self.assertEqual(
                [],
                [path.name for path in root.iterdir() if path.name.startswith(".gnostoa-package-")],
            )


if __name__ == "__main__":
    unittest.main()
