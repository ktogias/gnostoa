from __future__ import annotations

import importlib
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PATTERNS = {
    "project name": re.compile("Open" + "OP", re.IGNORECASE),
}


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve()}",
            "-C",
            str(root),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repository(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )


class RepositoryCandidateScopeTests(unittest.TestCase):
    @staticmethod
    def module():
        return importlib.import_module("tools.repository_scope")

    def test_only_git_tracked_candidate_files_are_semantic_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / ".gitignore").write_text(
                ".venv/\nlocal-cache/\n",
                encoding="utf-8",
            )
            (root / "tracked.md").write_text("generic source\n", encoding="utf-8")
            git(root, "add", ".gitignore", "tracked.md")

            leak = "Open" + "OP"
            (root / "scratch.md").write_text(leak, encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "activate").write_text(leak, encoding="utf-8")
            (root / "local-cache").mkdir()
            (root / "local-cache" / "record.txt").write_text(
                leak,
                encoding="utf-8",
            )

            self.assertEqual(
                [Path(".gitignore"), Path("tracked.md")],
                self.module().candidate_paths(root),
            )
            self.assertEqual(
                [],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )

            self.assertTrue((root / "scratch.md").is_file())
            self.assertTrue((root / ".venv" / "activate").is_file())
            self.assertIn("?? scratch.md", git(root, "status", "--short").stdout)

    def test_forbidden_vocabulary_in_a_tracked_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / "tracked.md").write_text(
                "Open" + "OP",
                encoding="utf-8",
            )
            git(root, "add", "tracked.md")

            self.assertEqual(
                ["tracked.md: project name"],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )

    def test_tracked_symlink_does_not_expose_external_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "repository"
            root.mkdir()
            initialize_repository(root)
            external = parent / "external.md"
            external.write_text("Open" + "OP", encoding="utf-8")
            (root / "reference.md").symlink_to(external)
            git(root, "add", "reference.md")

            self.assertEqual(
                [],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )
            self.assertEqual("Open" + "OP", external.read_text(encoding="utf-8"))

    def test_packaged_candidate_uses_its_build_manifest_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.md").write_text("generic source\n", encoding="utf-8")
            (root / "incidental.md").write_text(
                "Open" + "OP",
                encoding="utf-8",
            )
            (root / self.module().SOURCE_MANIFEST).write_bytes(b"source.md\0")

            self.assertEqual(
                [Path("source.md")],
                self.module().candidate_paths(root),
            )
            self.assertEqual(
                [],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )

    def test_unsafe_build_manifest_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / self.module().SOURCE_MANIFEST).write_bytes(b"../external.md\0")

            with self.assertRaisesRegex(
                self.module().RepositoryScopeError,
                "unsafe candidate path",
            ):
                self.module().candidate_paths(root)

    def test_container_runtime_declares_both_candidate_sources(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(
            dockerfile,
            r"ARG GIT_PACKAGE_VERSION=[^\s]+",
        )
        self.assertIn('"git=${GIT_PACKAGE_VERSION}"', dockerfile)
        self.assertIn(self.module().SOURCE_MANIFEST, dockerfile)
        self.assertLess(
            dockerfile.index(self.module().SOURCE_MANIFEST),
            dockerfile.index("python -m pip install"),
        )

    def test_container_build_context_excludes_local_analysis_state(self) -> None:
        exclusions = set(
            (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        )
        self.assertTrue(
            {".coverage", ".coverage.*", ".mypy_cache", ".ruff_cache"} <= exclusions
        )


if __name__ == "__main__":
    unittest.main()
