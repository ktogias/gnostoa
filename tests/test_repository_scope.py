from __future__ import annotations

import importlib
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


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
                self.module().tracked_candidate_paths(root),
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

    def test_container_runtime_pins_the_git_used_for_candidate_scope(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(
            dockerfile,
            r"ARG GIT_PACKAGE_VERSION=[^\s]+",
        )
        self.assertIn('"git=${GIT_PACKAGE_VERSION}"', dockerfile)


if __name__ == "__main__":
    unittest.main()
