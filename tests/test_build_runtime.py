"""Materialisation properties of the self-owned runtime build helper.

The helper decides which repository files become the published runtime's
Gnostoa source. These tests exercise that decision against anonymous temporary
Git fixtures; the Docker build itself is covered separately by the explicit
conformance harness, which needs a container runtime.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "ci" / "build-runtime"


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={root.resolve()}", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def fixture_repository(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", str(root)], check=True, capture_output=True
    )
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture")
    (root / ".gitignore").write_text("ignored/\n*.pyc\n", encoding="utf-8")
    (root / "plain.txt").write_text("plain\n", encoding="utf-8")
    (root / "runnable.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "runnable.sh").chmod(0o755)
    (root / "with space.txt").write_text("space\n", encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "deep.txt").write_text("deep\n", encoding="utf-8")
    (root / "link.txt").symlink_to("plain.txt")
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "fixture")


class BuildRuntimeMaterialisationTests(unittest.TestCase):
    """Run the helper's materialisation without invoking Docker.

    The helper ends in `exec docker build`, so these tests stop it just before
    that by exercising the same shell body with the build replaced. Keeping the
    substitution to the final command means the tested text is the shipped text.
    """

    def materialise(
        self, source: Path, destination: Path
    ) -> subprocess.CompletedProcess[str]:
        body = HELPER.read_text(encoding="utf-8")
        body = body.replace("trap 'rm -rf \"$CONTEXT\"' EXIT INT TERM", "")
        body = body.replace(
            'CONTEXT=$(mktemp -d "${TMPDIR:-/tmp}/gnostoa-candidate.XXXXXX")',
            f'CONTEXT="{destination}"',
        )
        body = body[: body.index("exec docker build")] + 'echo "$CONTEXT"\n'
        script = destination.parent / "materialise.sh"
        script.write_text(body, encoding="utf-8")
        script.chmod(0o755)
        return subprocess.run(
            ["/bin/sh", str(script)],
            cwd=source,
            capture_output=True,
            text=True,
        )

    def test_materialises_exactly_the_git_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            fixture_repository(source)

            # Local state that is untracked, ignored, or both. None of it is
            # part of the candidate, so none of it may reach the runtime.
            (source / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            (source / "ignored").mkdir()
            (source / "ignored" / "cache.txt").write_text("cache\n", encoding="utf-8")
            (source / "nested" / "stale.pyc").write_bytes(b"stale")

            destination = Path(directory) / "candidate"
            result = self.materialise(source, destination)
            self.assertEqual(0, result.returncode, result.stderr)

            expected = {
                line
                for line in git(
                    source, "ls-files", "--cached", "--deduplicate"
                ).stdout.splitlines()
                if line
            }
            payload = destination / "source"
            actual = {
                os.path.relpath(os.path.join(parent, name), payload)
                for parent, _, names in os.walk(payload)
                for name in names
            }
            actual |= {
                os.path.relpath(os.path.join(parent, name), payload)
                for parent, directories, _ in os.walk(payload)
                for name in directories
                if os.path.islink(os.path.join(parent, name))
            }
            self.assertEqual(expected, actual)
            self.assertIn(".gitignore", actual)
            for excluded in ("untracked.txt", "ignored/cache.txt", "nested/stale.pyc"):
                self.assertNotIn(excluded, actual)

    def test_preserves_working_tree_contents_modes_and_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            fixture_repository(source)
            # An uncommitted edit to a tracked file must reach the runtime:
            # development builds are expected to carry work in progress.
            (source / "plain.txt").write_text("edited\n", encoding="utf-8")

            destination = Path(directory) / "candidate"
            self.assertEqual(0, self.materialise(source, destination).returncode)
            payload = destination / "source"

            self.assertEqual("edited\n", (payload / "plain.txt").read_text())
            self.assertTrue(os.access(payload / "runnable.sh", os.X_OK))
            self.assertFalse(os.access(payload / "plain.txt", os.X_OK))
            self.assertTrue((payload / "link.txt").is_symlink())
            self.assertEqual("plain.txt", os.readlink(payload / "link.txt"))
            self.assertEqual("space\n", (payload / "with space.txt").read_text())

    def test_manifest_is_nul_separated_and_locale_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            fixture_repository(source)

            destination = Path(directory) / "candidate"
            self.assertEqual(0, self.materialise(source, destination).returncode)
            manifest = (destination / "meta" / ".gnostoa-source-files").read_bytes()

            self.assertNotIn(b"\n", manifest)
            self.assertTrue(manifest.endswith(b"\0"))
            entries = [entry for entry in manifest.split(b"\0") if entry]
            # C ordering, not the builder's locale: an in-build check recomputes
            # this ordering and compares the bytes.
            self.assertEqual(sorted(entries), entries)
            self.assertIn(b".gitignore", entries)
            self.assertTrue(hashlib.sha256(manifest).hexdigest())

    def test_missing_tracked_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            fixture_repository(source)
            (source / "plain.txt").unlink()

            destination = Path(directory) / "candidate"
            result = self.materialise(source, destination)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing tracked working-tree path", result.stderr)
            self.assertIn("plain.txt", result.stderr)

    def test_dangling_symlink_is_not_reported_as_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            fixture_repository(source)
            # A symlink whose target is gone still exists as a candidate entry.
            # Presence must be tested without following the link.
            (source / "plain.txt").unlink()
            (source / "plain.txt").symlink_to("absent.txt")

            destination = Path(directory) / "candidate"
            result = self.materialise(source, destination)
            self.assertNotIn("missing tracked working-tree path", result.stderr)

    def test_candidate_context_root_carries_no_dockerignore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            fixture_repository(source)
            (source / ".dockerignore").write_text("nested\n", encoding="utf-8")
            git(source, "add", ".dockerignore")
            git(source, "commit", "--quiet", "-m", "dockerignore")

            destination = Path(directory) / "candidate"
            self.assertEqual(0, self.materialise(source, destination).returncode)

            # A .dockerignore at the wrapper root would filter the candidate
            # context itself, silently dropping paths the manifest still claims.
            self.assertFalse((destination / ".dockerignore").exists())
            self.assertTrue((destination / "source" / ".dockerignore").is_file())
            self.assertTrue((destination / "source" / "nested" / "deep.txt").is_file())


if __name__ == "__main__":
    unittest.main()
