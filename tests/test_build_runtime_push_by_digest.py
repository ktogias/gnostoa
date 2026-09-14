from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "ci" / "build-runtime"


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root.resolve()}", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _fixture(root: Path) -> None:
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "9.8.7"\n', encoding="utf-8"
    )
    (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (root / "payload.txt").write_text("payload\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "--quiet", "-m", "fixture")


def _invoke(
    root: Path, scratch: Path, *arguments: str
) -> tuple[subprocess.CompletedProcess[str], Path]:
    fake_bin = scratch / "fake-bin"
    fake_bin.mkdir(exist_ok=True)
    capture = scratch / "docker-arguments"
    docker = fake_bin / "docker"
    docker.write_text(
        '#!/bin/sh\nprintf \'%s\\n\' "$@" > "$GNOSTOA_TEST_DOCKER_ARGS"\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    environment = os.environ.copy() | {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "GNOSTOA_CANDIDATE_REF": _git(root, "rev-parse", "HEAD"),
        "GNOSTOA_TEST_DOCKER_ARGS": str(capture),
    }
    result = subprocess.run(
        [str(HELPER), *arguments],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    return result, capture


class BuildRuntimePushByDigestTests(unittest.TestCase):
    def test_digest_only_mode_uses_unnamed_buildx_image_exporter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            source = scratch / "source"
            source.mkdir()
            _fixture(source)
            metadata = scratch / "metadata.json"

            result, capture = _invoke(
                source,
                scratch,
                "--push-by-digest",
                "ghcr.io/ktogias/gnostoa",
                "--metadata-file",
                str(metadata),
                "--platform",
                "linux/amd64",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            arguments = capture.read_text(encoding="utf-8").splitlines()
            self.assertEqual(["buildx", "build"], arguments[:2])
            self.assertIn(
                "type=image,name=ghcr.io/ktogias/gnostoa,push=true,push-by-digest=true",
                arguments,
            )
            self.assertIn("--metadata-file", arguments)
            self.assertIn(str(metadata), arguments)
            self.assertNotIn("--tag", arguments)
            self.assertNotIn("latest", "\n".join(arguments))

    def test_digest_only_mode_rejects_tagged_or_injected_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            source = scratch / "source"
            source.mkdir()
            _fixture(source)
            metadata = scratch / "metadata.json"

            tagged, tagged_capture = _invoke(
                source,
                scratch,
                "--tag",
                "fixture:candidate",
                "--push-by-digest",
                "ghcr.io/ktogias/gnostoa",
                "--metadata-file",
                str(metadata),
            )
            self.assertNotEqual(0, tagged.returncode)
            self.assertFalse(tagged_capture.exists())

        for destination in (
            "ghcr.io/ktogias/gnostoa,annotation.foo=bar",
            "ghcr.io/ktogias/gnostoa:mutable",
            "ghcr.io/ktogias/gnostoa@sha256:" + "a" * 64,
        ):
            with self.subTest(destination=destination):
                with tempfile.TemporaryDirectory() as directory:
                    scratch = Path(directory)
                    source = scratch / "source"
                    source.mkdir()
                    _fixture(source)
                    metadata = scratch / "metadata.json"
                    result, capture = _invoke(
                        source,
                        scratch,
                        "--push-by-digest",
                        destination,
                        "--metadata-file",
                        str(metadata),
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertFalse(capture.exists())

    def test_digest_only_mode_requires_external_metadata_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory)
            source = scratch / "source"
            source.mkdir()
            _fixture(source)

            missing, missing_capture = _invoke(
                source,
                scratch,
                "--push-by-digest",
                "ghcr.io/ktogias/gnostoa",
            )
            self.assertNotEqual(0, missing.returncode)
            self.assertFalse(missing_capture.exists())

            inside, inside_capture = _invoke(
                source,
                scratch,
                "--push-by-digest",
                "ghcr.io/ktogias/gnostoa",
                "--metadata-file",
                str(source / "metadata.json"),
            )
            self.assertNotEqual(0, inside.returncode)
            self.assertFalse(inside_capture.exists())


if __name__ == "__main__":
    unittest.main()
