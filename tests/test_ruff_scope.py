from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RECURSIVE_EXCLUDES = {
    ".bzr",
    ".direnv",
    ".eggs",
    ".git",
    ".git-rewrite",
    ".hg",
    ".ipynb_checkpoints",
    ".mypy_cache",
    ".nox",
    ".pants.d",
    ".pyenv",
    ".pytest_cache",
    ".pytype",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    ".vscode",
    "__pypackages__",
    "__pycache__",
    "node_modules",
    "site-packages",
    "venv",
    "*.egg-info",
}
EXPECTED_ROOT_OUTPUT_EXCLUDES = {
    "_build/**",
    "build/**",
    "buck-out/**",
    "context-packs/**",
    "dist/**",
    "site/**",
}
EXPECTED_ROOT_GITIGNORES = {
    "/context-packs/",
    "/dist/",
    "/site/",
}
RUFF_AVAILABLE = importlib.util.find_spec("ruff") is not None


class RuffScopeContractTests(unittest.TestCase):
    def test_configuration_separates_git_candidate_and_ruff_exclusions(self) -> None:
        document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        ruff = document["tool"]["ruff"]
        exclusions = set(ruff.get("exclude", []))

        self.assertTrue(ruff.get("respect-gitignore", False))
        self.assertFalse(ruff.get("extend-exclude"))
        self.assertTrue(EXPECTED_RECURSIVE_EXCLUDES <= exclusions)
        self.assertTrue(EXPECTED_ROOT_OUTPUT_EXCLUDES <= exclusions)
        for bare_output in (
            "_build",
            "build",
            "buck-out",
            "context-packs",
            "dist",
            "site",
        ):
            with self.subTest(bare_output=bare_output):
                self.assertNotIn(bare_output, exclusions)
        self.assertNotIn("tasks", exclusions)
        self.assertNotIn("tools", exclusions)
        self.assertNotIn("ci", exclusions)
        self.assertNotIn("tests", exclusions)

        gitignore = {
            line
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        }
        self.assertTrue(EXPECTED_ROOT_GITIGNORES <= gitignore)
        for unanchored in ("context-packs/", "dist/", "site/"):
            with self.subTest(unanchored=unanchored):
                self.assertNotIn(unanchored, gitignore)

        ignored_tracked = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.resolve()}",
                "ls-files",
                "--cached",
                "--ignored",
                "--exclude-standard",
                "--",
                "*.py",
                "*.pyi",
                "*.ipynb",
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual("", ignored_tracked.stdout)

    @unittest.skipUnless(
        RUFF_AVAILABLE,
        "Ruff is available only in the exact development verification environment",
    )
    def test_root_output_ignores_do_not_hide_nested_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            nested = [
                root / "pkg" / name / "covered.py"
                for name in (
                    "_build",
                    "build",
                    "buck-out",
                    "context-packs",
                    "dist",
                    "site",
                )
            ]
            generated = [
                root / name / "generated.py"
                for name in (
                    "_build",
                    "build",
                    "buck-out",
                    "context-packs",
                    "dist",
                    "site",
                )
            ]
            for path in nested + generated:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("value = 1\n", encoding="utf-8")

            ignored_local = root / "local-scratch" / "ignored.py"
            ignored_local.parent.mkdir(parents=True, exist_ok=True)
            ignored_local.write_text("value = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                "/context-packs/\n/dist/\n/site/\n/local-scratch/\n",
                encoding="utf-8",
            )

            ignored_by_git = subprocess.run(
                [
                    "git",
                    "check-ignore",
                    "--no-index",
                    "--",
                    *[
                        str(path.relative_to(root))
                        for path in generated
                        if path.parent.name in {"context-packs", "dist", "site"}
                    ],
                    str(ignored_local.relative_to(root)),
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            expected_git_ignored = {
                str(path.relative_to(root))
                for path in generated
                if path.parent.name in {"context-packs", "dist", "site"}
            } | {str(ignored_local.relative_to(root))}
            self.assertEqual(
                expected_git_ignored,
                set(ignored_by_git.stdout.splitlines()),
            )
            nested_ignored = subprocess.run(
                [
                    "git",
                    "check-ignore",
                    "--no-index",
                    "--",
                    *[str(path.relative_to(root)) for path in nested],
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(1, nested_ignored.returncode)
            self.assertEqual("", nested_ignored.stdout)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--show-files",
                    "--config",
                    str(ROOT / "pyproject.toml"),
                    ".",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            discovered = completed.stdout

            for path in nested:
                with self.subTest(path=path):
                    self.assertIn(str(path.resolve()), discovered)
            for path in generated:
                with self.subTest(path=path):
                    self.assertNotIn(str(path.resolve()), discovered)
            self.assertNotIn(str(ignored_local.resolve()), discovered)

    def test_style_surface_rejects_tracked_ignored_ruff_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            (root / ".gitignore").write_text("hidden.py\n", encoding="utf-8")
            (root / "hidden.py").write_text("value = 1\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".gitignore"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "add", "--force", "hidden.py"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            completed = subprocess.run(
                [str(ROOT / "ci" / "style"), "--check"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, completed.returncode)
            self.assertIn("tracked Ruff input is ignored by Git", completed.stderr)
            self.assertIn("hidden.py", completed.stderr)

    @unittest.skipUnless(
        RUFF_AVAILABLE,
        "Ruff is available only in the exact development verification environment",
    )
    def test_fix_leaves_untracked_ignored_python_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            (root / ".gitignore").write_text("/local-scratch/\n", encoding="utf-8")
            (root / "visible.py").write_text("value = 1\n", encoding="utf-8")
            ignored = root / "local-scratch" / "ignored.py"
            ignored.parent.mkdir()
            ignored.write_text("value=1\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".gitignore", "visible.py"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            environment = dict(os.environ)
            environment["PATH"] = (
                f"{Path(sys.executable).parent}{os.pathsep}{environment['PATH']}"
            )

            completed = subprocess.run(
                [str(ROOT / "ci" / "style"), "--fix"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual("value=1\n", ignored.read_text(encoding="utf-8"))

    def test_style_surface_is_repository_root_scoped(self) -> None:
        style_path = ROOT / "ci" / "style"
        self.assertTrue(style_path.is_file())
        style = style_path.read_text(encoding="utf-8")

        self.assertIn("python -m ruff format --check .", style)
        self.assertIn("python -m ruff check .", style)
        self.assertIn("python -m ruff check --fix .", style)
        self.assertIn("python -m ruff format .", style)
        self.assertIn("ls-files --cached --ignored --exclude-standard", style)
        self.assertIn('git -c "safe.directory=${repository_root}"', style)
        self.assertNotIn("tools ci tests", style)

        fix_branch = style.split("--fix)", 1)[1].split(";;", 1)[0]
        safe_fix = fix_branch.index("python -m ruff check --fix .")
        format_fix = fix_branch.index("python -m ruff format .")
        format_check = fix_branch.index("python -m ruff format --check .")
        lint_check = fix_branch.index("python -m ruff check .")
        self.assertLess(safe_fix, format_fix)
        self.assertLess(format_fix, format_check)
        self.assertLess(format_check, lint_check)

    def test_provider_and_pre_push_consume_shared_check_surface(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text(
            encoding="utf-8"
        )
        pre_push = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")
        verify = (ROOT / "ci" / "verify").read_text(encoding="utf-8")

        self.assertIn("./ci/style --check", workflow)
        self.assertNotIn("python -m ruff format --check tools ci tests", workflow)
        self.assertNotIn("python -m ruff check tools ci tests", workflow)
        self.assertIn("./ci/style --check", pre_push)
        self.assertIn("./ci/style --check", verify)

    def test_extended_quality_evidence_uses_repository_root_subject(self) -> None:
        source = (ROOT / "tools" / "quality_evidence.py").read_text(encoding="utf-8")

        self.assertNotIn(
            '"tools",\n                "ci",\n                "tests",',
            source,
        )
        self.assertGreaterEqual(source.count('"."'), 2)

    def test_tasks_python_is_not_an_accidental_scope_exception(self) -> None:
        self.assertTrue((ROOT / "tasks" / "gnostoa_orientation.py").is_file())

        document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        exclusions = set(document["tool"]["ruff"].get("exclude", []))
        self.assertFalse(
            any(item == "tasks" or item.startswith("tasks/") for item in exclusions)
        )


if __name__ == "__main__":
    unittest.main()
