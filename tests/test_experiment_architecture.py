from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = ROOT / "tools" / "experiment"
RUNNER_CLI = ROOT / "tools" / "experiment_runner.py"
HANDOFF_CLI = ROOT / "tools" / "experiment_handoff.py"
PACKAGER_CLI = ROOT / "tools" / "experiment_packager.py"


class ExperimentArchitectureContractTests(unittest.TestCase):
    def test_internal_trust_domain_modules_exist(self) -> None:
        expected = {
            "__init__.py",
            "evidence.py",
            "handoff.py",
            "execution.py",
            "packaging.py",
        }
        observed = {path.name for path in INTERNAL.glob("*.py")} if INTERNAL.is_dir() else set()
        self.assertTrue(expected <= observed, (expected, observed))

    def test_public_self_clis_are_thin_adapters(self) -> None:
        expected = (RUNNER_CLI, HANDOFF_CLI, PACKAGER_CLI)
        for path in expected:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), path)
                text = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(text.splitlines()), 40, path)
                tree = ast.parse(text)
                definitions = [
                    node.name
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                ]
                self.assertEqual([], definitions, (path, definitions))

    def test_packager_cli_requires_frozen_handoff_not_raw_root(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PACKAGER_CLI), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--handoff", result.stdout)
        self.assertNotIn("--root", result.stdout)

    def test_packaging_domain_cannot_import_execution_domain(self) -> None:
        packaging = INTERNAL / "packaging.py"
        if not packaging.is_file():
            self.skipTest("RED retained until internal packaging domain exists")
        tree = ast.parse(packaging.read_text(encoding="utf-8"))
        forbidden = {
            "tools.experiment.execution",
            "tools.experiment.coordinator",
            "tools.experiment_runner",
        }
        observed: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                observed.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                observed.add(node.module)
        self.assertFalse(forbidden & observed, observed)


if __name__ == "__main__":
    unittest.main()
