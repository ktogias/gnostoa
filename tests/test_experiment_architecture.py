from __future__ import annotations

import ast
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERNAL = ROOT / "tools" / "experiment"
RUNNER_CLI = ROOT / "tools" / "experiment_runner.py"
HANDOFF_CLI = ROOT / "tools" / "experiment_handoff.py"
PACKAGER_CLI = ROOT / "tools" / "experiment_packager.py"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    observed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            observed.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            prefix = "." * node.level
            observed.add(f"{prefix}{node.module}")
    return observed


class ExperimentArchitectureContractTests(unittest.TestCase):
    def test_internal_trust_domain_modules_exist(self) -> None:
        expected = {
            "__init__.py",
            "backend.py",
            "capture.py",
            "evidence.py",
            "execution.py",
            "handoff.py",
            "packaging.py",
            "profile.py",
            "relay.py",
            "smoke.py",
        }
        observed = (
            {path.name for path in INTERNAL.glob("*.py")}
            if INTERNAL.is_dir()
            else set()
        )
        self.assertTrue(expected <= observed, (expected, observed))

    def test_execution_domain_has_no_private_monolith(self) -> None:
        private_engine = INTERNAL / "_execution_engine.py"
        self.assertFalse(private_engine.exists(), private_engine)
        imports = imported_modules(INTERNAL / "execution.py")
        self.assertNotIn("._execution_engine", imports)

        regressions = (
            ROOT / "tests" / "test_experiment_runner_review_regressions.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_execution_engine", regressions)
        self.assertIn("from tools.experiment import execution as runner", regressions)

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
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    )
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

    def test_internal_package_is_part_of_installed_distribution(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream)
        packages = project["tool"]["setuptools"]["packages"]
        self.assertIn("tools.experiment", packages)

    def test_dependency_direction_is_one_way_through_evidence_and_handoff(self) -> None:
        expected = {
            "handoff.py": {".evidence"},
            "packaging.py": {".evidence", ".handoff"},
        }
        for name, required in expected.items():
            path = INTERNAL / name
            if not path.is_file():
                self.skipTest("RED retained until internal trust-domain modules exist")
            observed = imported_modules(path)
            self.assertTrue(required <= observed, (name, required, observed))

        packaging_imports = imported_modules(INTERNAL / "packaging.py")
        handoff_imports = imported_modules(INTERNAL / "handoff.py")
        forbidden_packaging = {
            ".execution",
            ".backend",
            ".capture",
            ".profile",
            ".relay",
            ".smoke",
            "tools.experiment.execution",
            "tools.experiment_runner",
        }
        forbidden_handoff = {
            ".execution",
            ".packaging",
            ".backend",
            ".capture",
            ".profile",
            ".relay",
            ".smoke",
            "tools.experiment.execution",
            "tools.experiment.packaging",
        }
        self.assertFalse(forbidden_packaging & packaging_imports, packaging_imports)
        self.assertFalse(forbidden_handoff & handoff_imports, handoff_imports)


if __name__ == "__main__":
    unittest.main()
