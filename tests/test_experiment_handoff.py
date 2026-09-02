from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "tools" / "experiment_handoff.py"
FIXTURE_ID = f"fixture={'a' * 64}"


class ExperimentHandoffContractTests(unittest.TestCase):
    def invoke_freeze(
        self,
        source: Path,
        bundle: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(HANDOFF),
                "freeze",
                "--root",
                str(source),
                "--bundle",
                str(bundle),
                "--input",
                FIXTURE_ID,
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def invoke_verify(self, manifest: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HANDOFF), "verify", "--handoff", str(manifest)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def parse_stdout(self, result: subprocess.CompletedProcess[str]) -> dict:
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"handoff stdout must be JSON: {exc}: {result.stdout!r}")
        self.assertIsInstance(value, dict)
        return value

    def write_source(self, root: Path) -> Path:
        source = root / "source"
        nested = source / "nested"
        nested.mkdir(parents=True)
        (source / "plain.txt").write_text("alpha\n", encoding="utf-8")
        executable = source / "run.sh"
        executable.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
        executable.chmod(0o755)
        (nested / "data.txt").write_text("payload\n", encoding="utf-8")
        (source / "link").symlink_to("nested/data.txt")
        return source

    def test_freeze_is_path_neutral_and_independent_from_later_source_mutation(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-handoff-red-") as raw:
            root = Path(raw)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            source_left = self.write_source(left)
            source_right = self.write_source(right)
            bundle_left = left / "bundle"
            bundle_right = right / "bundle"

            first = self.invoke_freeze(source_left, bundle_left)
            second = self.invoke_freeze(source_right, bundle_right)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0, second.returncode, second.stderr)

            manifest_left = bundle_left / "handoff.json"
            manifest_right = bundle_right / "handoff.json"
            self.assertEqual(manifest_left.read_bytes(), manifest_right.read_bytes())
            payload = self.parse_stdout(first)
            self.assertEqual(
                hashlib.sha256(manifest_left.read_bytes()).hexdigest(),
                payload["handoff_sha256"],
            )

            (source_left / "plain.txt").write_text("mutated\n", encoding="utf-8")
            verified = self.invoke_verify(manifest_left)
            self.assertEqual(0, verified.returncode, verified.stderr)
            self.assertEqual("VERIFIED", self.parse_stdout(verified)["status"])
            self.assertEqual(
                "alpha\n",
                (bundle_left / "tree" / "plain.txt").read_text(encoding="utf-8"),
            )

    def test_freeze_preserves_symlink_without_copying_external_target(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-handoff-red-") as raw:
            root = Path(raw)
            source = self.write_source(root)
            outside = root / "outside-secret.txt"
            outside.write_text("secret\n", encoding="utf-8")
            (source / "external-link").symlink_to(outside)
            bundle = root / "bundle"

            result = self.invoke_freeze(source, bundle)
            self.assertEqual(0, result.returncode, result.stderr)
            frozen_link = bundle / "tree" / "external-link"
            self.assertTrue(frozen_link.is_symlink())
            self.assertEqual(str(outside), frozen_link.readlink().as_posix())
            self.assertNotIn(
                "secret\n",
                (bundle / "handoff.json").read_text(encoding="utf-8"),
            )

    def test_verify_detects_snapshot_mutation(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-handoff-red-") as raw:
            root = Path(raw)
            source = self.write_source(root)
            bundle = root / "bundle"
            result = self.invoke_freeze(source, bundle)
            self.assertEqual(0, result.returncode, result.stderr)

            frozen = bundle / "tree" / "plain.txt"
            frozen.chmod(0o644)
            frozen.write_text("forged\n", encoding="utf-8")
            verified = self.invoke_verify(bundle / "handoff.json")
            self.assertEqual(2, verified.returncode)
            payload = self.parse_stdout(verified)
            self.assertEqual("BLOCKED", payload["status"])

    def test_bundle_publication_is_create_only(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-handoff-red-") as raw:
            root = Path(raw)
            source = self.write_source(root)
            bundle = root / "bundle"
            first = self.invoke_freeze(source, bundle)
            self.assertEqual(0, first.returncode, first.stderr)
            manifest = bundle / "handoff.json"
            original = manifest.read_bytes()

            second = self.invoke_freeze(source, bundle)
            self.assertEqual(2, second.returncode)
            self.assertEqual(original, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
