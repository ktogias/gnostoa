from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGER = ROOT / "tools" / "experiment_packager.py"


class ExperimentPackagerContractTests(unittest.TestCase):
    def require_packager(self) -> None:
        if not PACKAGER.is_file():
            self.skipTest(
                "RED contract retained: tools/experiment_packager.py is not implemented yet"
            )

    def invoke(
        self,
        source: Path,
        output: Path,
        *,
        max_bytes: int = 1_048_576,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PACKAGER),
                "--root",
                str(source),
                "--output",
                str(output),
                "--max-bytes",
                str(max_bytes),
                "--input",
                f"fixture={'a' * 64}",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def parse_json_stdout(self, result: subprocess.CompletedProcess[str]) -> dict:
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"packager stdout must be one JSON object: {exc}: {result.stdout!r}"
            )
        self.assertIsInstance(value, dict)
        return value

    def write_source(self, root: Path) -> Path:
        source = root / "source"
        nested = source / "nested"
        nested.mkdir(parents=True)
        (source / "plain.txt").write_text("plain\n", encoding="utf-8")
        executable = source / "run.sh"
        executable.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
        executable.chmod(0o755)
        (nested / "data.txt").write_text("payload\n", encoding="utf-8")
        (source / "data-link").symlink_to("nested/data.txt")
        return source

    def test_packager_entry_point_exists(self) -> None:
        self.assertTrue(PACKAGER.is_file())

    def test_package_is_byte_deterministic_and_metadata_normalized(self) -> None:
        self.require_packager()
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            source = self.write_source(root)
            first = root / "first.tar"
            second = root / "second.tar"

            first_result = self.invoke(source, first)
            second_result = self.invoke(source, second)

            self.assertEqual(0, first_result.returncode, first_result.stderr)
            self.assertEqual(0, second_result.returncode, second_result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())

            with tarfile.open(first, mode="r:") as archive:
                members = archive.getmembers()
            names = [member.name for member in members]
            self.assertEqual(names, sorted(names, key=os.fsencode))
            for member in members:
                self.assertEqual(0, member.uid)
                self.assertEqual(0, member.gid)
                self.assertEqual("", member.uname)
                self.assertEqual("", member.gname)
                self.assertEqual(0, member.mtime)

    def test_package_preserves_symlink_without_dereference(self) -> None:
        self.require_packager()
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            source = self.write_source(root)
            output = root / "candidate.tar"

            result = self.invoke(source, output)

            self.assertEqual(0, result.returncode, result.stderr)
            with tarfile.open(output, mode="r:") as archive:
                member = archive.getmember("data-link")
                self.assertTrue(member.issym())
                self.assertEqual("nested/data.txt", member.linkname)
                self.assertEqual(b"payload\n", archive.extractfile("nested/data.txt").read())

    def test_packager_rejects_output_inside_source_root(self) -> None:
        self.require_packager()
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            source = self.write_source(Path(raw))
            output = source / "candidate.tar"

            result = self.invoke(source, output)

            self.assertEqual(2, result.returncode, result.stderr)
            payload = self.parse_json_stdout(result)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertIn("output-inside-source-root", payload["reasons"])
            self.assertFalse(output.exists())

    def test_packager_removes_partial_output_when_archive_limit_is_exceeded(self) -> None:
        self.require_packager()
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "large.bin").write_bytes(b"x" * 131_072)
            output = root / "candidate.tar"

            result = self.invoke(source, output, max_bytes=1_024)

            self.assertEqual(2, result.returncode, result.stderr)
            payload = self.parse_json_stdout(result)
            self.assertEqual("OVERSIZE", payload["status"])
            self.assertEqual(1_024, payload["max_bytes"])
            self.assertFalse(output.exists())

    def test_package_identity_binds_producer_configuration_and_inputs(self) -> None:
        self.require_packager()
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            source = self.write_source(root)
            output = root / "candidate.tar"

            result = self.invoke(source, output)

            self.assertEqual(0, result.returncode, result.stderr)
            payload = self.parse_json_stdout(result)
            self.assertEqual("gnostoa-experiment-package/v1", payload["schema"])
            self.assertEqual("PACKAGED", payload["status"])
            self.assertEqual("pax-tar-v1", payload["format"])
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(), payload["sha256"]
            )
            self.assertEqual(output.stat().st_size, payload["bytes"])
            self.assertEqual(
                "gnostoa-experiment-packager", payload["producer"]["id"]
            )
            self.assertEqual("1", payload["producer"]["version"])
            self.assertRegex(
                payload["producer"]["config_sha256"], r"^[a-f0-9]{64}$"
            )
            self.assertEqual(
                [{"id": "fixture", "sha256": "a" * 64}], payload["inputs"]
            )


if __name__ == "__main__":
    unittest.main()
