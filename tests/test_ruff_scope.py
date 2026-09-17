from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GENERATED_EXCLUDES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "context-packs",
    "dist",
    "site",
    "*.egg-info",
}


class RuffScopeContractTests(unittest.TestCase):
    def test_pyproject_declares_explicit_generated_exclusions(self) -> None:
        document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        ruff = document["tool"]["ruff"]
        exclusions = set(ruff.get("extend-exclude", []))

        self.assertTrue(EXPECTED_GENERATED_EXCLUDES <= exclusions)
        self.assertNotIn("tasks", exclusions)
        self.assertNotIn("tools", exclusions)
        self.assertNotIn("ci", exclusions)
        self.assertNotIn("tests", exclusions)

    def test_style_surface_is_repository_root_scoped(self) -> None:
        style_path = ROOT / "ci" / "style"
        self.assertTrue(style_path.is_file())
        style = style_path.read_text(encoding="utf-8")

        self.assertIn("python -m ruff format --check .", style)
        self.assertIn("python -m ruff check .", style)
        self.assertIn("python -m ruff check --fix .", style)
        self.assertIn("python -m ruff format .", style)
        self.assertNotIn("tools ci tests", style)

        safe_fix = style.index("python -m ruff check --fix .")
        format_fix = style.index("python -m ruff format .")
        format_check = style.index("python -m ruff format --check .")
        lint_check = style.index("python -m ruff check .")
        self.assertLess(safe_fix, format_fix)
        self.assertLess(format_fix, format_check)
        self.assertLess(format_check, lint_check)

    def test_provider_and_pre_push_consume_shared_check_surface(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text(
            encoding="utf-8"
        )
        pre_push = (ROOT / ".githooks" / "pre-push").read_text(encoding="utf-8")

        self.assertIn("./ci/style --check", workflow)
        self.assertNotIn("python -m ruff format --check tools ci tests", workflow)
        self.assertNotIn("python -m ruff check tools ci tests", workflow)
        self.assertIn("./ci/style --check", pre_push)

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
        exclusions = set(document["tool"]["ruff"].get("extend-exclude", []))
        self.assertFalse(
            any(item == "tasks" or item.startswith("tasks/") for item in exclusions)
        )


if __name__ == "__main__":
    unittest.main()
