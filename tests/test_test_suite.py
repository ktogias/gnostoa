"""The repository's test suite runs in parallel processes, through one owner
(Decision 0109)."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class TestSuiteOwnerTests(unittest.TestCase):
    def test_the_suite_runs_one_module_per_parallel_task(self) -> None:
        from tools import test_suite

        self.assertEqual(
            [
                "python",
                "-m",
                "unittest_parallel",
                "--start-directory",
                "tests",
                "--level",
                "module",
            ],
            test_suite.command("python"),
        )

    def test_coverage_is_measured_through_the_runner_as_before(self) -> None:
        """The same measurement as `coverage run --branch --source=tools`, combined
        across the runner's processes."""
        from tools import test_suite

        command = test_suite.command("python", coverage_source="tools")
        self.assertEqual(
            ["--coverage", "--coverage-branch", "--coverage-source", "tools"],
            command[command.index("--coverage") :],
        )

    def test_run_runs_the_command_in_the_root_and_returns_its_status(self) -> None:
        import subprocess
        import sys

        from tools import test_suite

        done: subprocess.CompletedProcess[bytes] = subprocess.CompletedProcess(
            args=[], returncode=3
        )
        with patch("tools.test_suite.subprocess.run", return_value=done) as run:
            self.assertEqual(3, test_suite.run(ROOT))
        run.assert_called_once_with(
            test_suite.command(sys.executable), cwd=ROOT, check=False
        )

    def test_fast_runs_the_suite_through_the_owner(self) -> None:
        verify = (ROOT / "ci" / "verify").read_text(encoding="utf-8")
        fast = verify.split("  fast)", 1)[1].split("    ;;", 1)[0]
        self.assertIn("python -m tools.test_suite", fast)
        self.assertNotIn("unittest discover", fast)

    def test_self_check_runs_the_suite_through_the_owner(self) -> None:
        from tools import self_check

        with patch("tools.test_suite.run", return_value=0) as run:
            self.assertTrue(self_check.self_check(ROOT))
        run.assert_called_once_with(ROOT.resolve())

    def test_the_runner_is_declared_and_pinned(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn(
            "unittest-parallel",
            {
                d.split(">")[0].split("=")[0].strip()
                for d in project["project"]["dependencies"]
            },
        )
        runtime = (ROOT / "requirements" / "runtime.lock").read_text(encoding="utf-8")
        development = (ROOT / "requirements" / "development.lock").read_text(
            encoding="utf-8"
        )
        self.assertIn("\nunittest-parallel==1.8.6 \\\n", runtime)
        # unittest-parallel imports coverage unconditionally, so the runtime image
        # holds it too.
        self.assertIn("\ncoverage==", runtime)
        self.assertIn("\nunittest-parallel==1.8.6 \\\n", development)


if __name__ == "__main__":
    unittest.main()
