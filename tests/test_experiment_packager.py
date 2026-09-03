from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "tools" / "experiment_handoff.py"
PACKAGER = ROOT / "tools" / "experiment_packager.py"
INTERNAL_PACKAGING = ROOT / "tools" / "experiment" / "packaging.py"
FIXTURE_ID = f"fixture={'a' * 64}"
GOLDEN_PACKAGE_SHA256 = (
    "63b16ed71e381b7fb2cca2d7a383892bb4dbd84df62eb5fa29ba8be358754b87"
)


class ExperimentPackagerContractTests(unittest.TestCase):
    def parse_stdout(self, result: subprocess.CompletedProcess[str]) -> dict:
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"packager stdout must be JSON: {exc}: {result.stdout!r}")
        self.assertIsInstance(value, dict)
        return value

    def write_source(self, root: Path) -> Path:
        source = root / "source"
        binary = source / "bin"
        nested = source / "nested"
        binary.mkdir(parents=True)
        nested.mkdir()
        (source / "plain.txt").write_text("alpha\n", encoding="utf-8")
        executable = binary / "run.sh"
        executable.write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
        executable.chmod(0o755)
        (nested / "data.txt").write_text("payload\n", encoding="utf-8")
        (source / "link").symlink_to("nested/data.txt")
        return source

    def freeze(self, source: Path, bundle: Path) -> Path:
        result = subprocess.run(
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
        self.assertEqual(0, result.returncode, result.stderr)
        return bundle / "handoff.json"

    def invoke(
        self,
        handoff: Path,
        output: Path,
        *,
        max_bytes: int = 1_048_576,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(PACKAGER),
                "--handoff",
                str(handoff),
                "--output",
                str(output),
                "--max-bytes",
                str(max_bytes),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_golden_digest_is_stable_across_independent_freezes_and_processes(
        self,
    ) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            left = root / "left"
            right = root / "right"
            left.mkdir()
            right.mkdir()
            handoff_left = self.freeze(self.write_source(left), left / "bundle")
            handoff_right = self.freeze(self.write_source(right), right / "bundle")
            outputs = [
                (handoff_left, root / "left-first.tar"),
                (handoff_left, root / "left-second.tar"),
                (handoff_right, root / "right.tar"),
            ]

            observed: list[bytes] = []
            for handoff, output in outputs:
                result = self.invoke(handoff, output)
                self.assertEqual(0, result.returncode, result.stderr)
                observed.append(output.read_bytes())

            self.assertEqual(observed[0], observed[1])
            self.assertEqual(observed[0], observed[2])
            self.assertEqual(
                GOLDEN_PACKAGE_SHA256,
                hashlib.sha256(observed[0]).hexdigest(),
            )

    def test_archive_metadata_is_normalized_and_symlink_is_not_dereferenced(
        self,
    ) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            handoff = self.freeze(self.write_source(root), root / "bundle")
            output = root / "candidate.tar"
            result = self.invoke(handoff, output)
            self.assertEqual(0, result.returncode, result.stderr)

            with tarfile.open(output, mode="r:") as archive:
                members = archive.getmembers()
                names = [member.name for member in members]
                self.assertEqual(names, sorted(names, key=lambda value: value.encode()))
                for member in members:
                    self.assertEqual(0, member.uid)
                    self.assertEqual(0, member.gid)
                    self.assertEqual("", member.uname)
                    self.assertEqual("", member.gname)
                    self.assertEqual(0, member.mtime)
                link = archive.getmember("link")
                self.assertTrue(link.issym())
                self.assertEqual("nested/data.txt", link.linkname)
                self.assertEqual(
                    b"payload\n", archive.extractfile("nested/data.txt").read()
                )

    def test_package_rejects_mutated_frozen_subject(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            bundle = root / "bundle"
            handoff = self.freeze(self.write_source(root), bundle)
            frozen = bundle / "tree" / "plain.txt"
            frozen.chmod(0o644)
            frozen.write_text("forged\n", encoding="utf-8")
            output = root / "candidate.tar"

            result = self.invoke(handoff, output)
            self.assertEqual(2, result.returncode)
            payload = self.parse_stdout(result)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertFalse(output.exists())

    def test_packager_rejects_output_inside_handoff_bundle(self) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            bundle = root / "bundle"
            handoff = self.freeze(self.write_source(root), bundle)
            output = bundle / "candidate.tar"

            result = self.invoke(handoff, output)
            self.assertEqual(2, result.returncode)
            payload = self.parse_stdout(result)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertFalse(output.exists())

    def test_packager_removes_staged_output_when_archive_limit_is_exceeded(
        self,
    ) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "large.bin").write_bytes(b"x" * 131_072)
            handoff = self.freeze(source, root / "bundle")
            output = root / "candidate.tar"

            result = self.invoke(handoff, output, max_bytes=1_024)
            self.assertEqual(2, result.returncode, result.stderr)
            payload = self.parse_stdout(result)
            self.assertEqual("OVERSIZE", payload["status"])
            self.assertFalse(output.exists())

    def test_package_identity_binds_handoff_producer_configuration_and_inputs(
        self,
    ) -> None:
        self.assertTrue(HANDOFF.is_file())
        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            handoff = self.freeze(self.write_source(root), root / "bundle")
            output = root / "candidate.tar"
            result = self.invoke(handoff, output)
            self.assertEqual(0, result.returncode, result.stderr)
            payload = self.parse_stdout(result)

            self.assertEqual("gnostoa-experiment-package/v2", payload["schema"])
            self.assertEqual("PACKAGED", payload["status"])
            self.assertEqual("pax-tar-v1", payload["format"])
            self.assertEqual(
                hashlib.sha256(output.read_bytes()).hexdigest(), payload["sha256"]
            )
            self.assertEqual(output.stat().st_size, payload["bytes"])
            self.assertEqual("gnostoa-experiment-packager", payload["producer"]["id"])
            self.assertRegex(payload["producer"]["config_sha256"], r"^[a-f0-9]{64}$")
            inputs = {item["id"]: item["sha256"] for item in payload["inputs"]}
            self.assertEqual("a" * 64, inputs["fixture"])
            self.assertEqual(
                hashlib.sha256(handoff.read_bytes()).hexdigest(), inputs["handoff"]
            )

    @unittest.skipUnless(
        INTERNAL_PACKAGING.is_file(),
        "RED retained until internal packaging domain exists",
    )
    def test_failed_publication_never_deletes_foreign_output(self) -> None:
        from tools.experiment import packaging

        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            handoff = self.freeze(self.write_source(root), root / "bundle")
            output = root / "candidate.tar"

            def collide(_source: object, target: object) -> None:
                Path(target).write_bytes(b"foreign-output\n")
                raise FileExistsError(str(target))

            with mock.patch.object(packaging.os, "link", side_effect=collide):
                exit_code, payload = packaging.create_package(
                    handoff,
                    output,
                    1_048_576,
                )

            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertEqual(b"foreign-output\n", output.read_bytes())

    @unittest.skipUnless(
        INTERNAL_PACKAGING.is_file(),
        "RED retained until internal packaging domain exists",
    )
    def test_output_parent_replacement_cannot_redirect_publication(self) -> None:
        from tools.experiment import packaging

        with tempfile.TemporaryDirectory(prefix="gnostoa-packager-red-") as raw:
            root = Path(raw)
            handoff = self.freeze(self.write_source(root), root / "bundle")
            output_parent = root / "output"
            output_parent.mkdir()
            output = output_parent / "candidate.tar"
            moved_parent = root / "output-original"
            real_link = packaging.os.link
            swapped = False

            def swap_parent(
                source: object, target: object, *args: object, **kwargs: object
            ) -> object:
                nonlocal swapped
                if not swapped:
                    output_parent.rename(moved_parent)
                    output_parent.mkdir()
                    (output_parent / "foreign-sentinel.txt").write_text(
                        "foreign\n", encoding="utf-8"
                    )
                    if kwargs.get("src_dir_fd") is None:
                        source_path = Path(str(source))
                        if source_path.is_absolute():
                            source_path.write_bytes(b"forged-staging-bytes\n")
                    swapped = True
                return real_link(source, target, *args, **kwargs)

            with mock.patch.object(packaging.os, "link", side_effect=swap_parent):
                exit_code, payload = packaging.create_package(
                    handoff,
                    output,
                    1_048_576,
                )

            self.assertTrue(swapped)
            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertEqual(
                "foreign\n",
                (output_parent / "foreign-sentinel.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse(output.exists())
            self.assertFalse((moved_parent / "candidate.tar").exists())


if __name__ == "__main__":
    unittest.main()
