"""The repository's test suite runs in parallel processes, through one owner
(Decision 0109)."""

from __future__ import annotations

import sys
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

    def test_run_runs_the_command_in_its_own_session_and_returns_its_status(
        self,
    ) -> None:
        from tools import test_suite

        with patch("tools.test_suite.subprocess.Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.wait.return_value = 3
            self.assertEqual(3, test_suite.run(ROOT))
        popen.assert_called_once_with(
            test_suite.command(sys.executable), cwd=ROOT, start_new_session=True
        )
        process.wait.assert_called_once_with(timeout=test_suite.TIMEOUT_SECONDS)

    def test_a_suite_past_its_bound_is_stopped_with_its_workers(self) -> None:
        """The whole session is killed, so the runner's workers stop too, and the
        status says the bound was reached (Kody on #392)."""
        import signal
        import subprocess

        from tools import test_suite

        self.assertEqual(3600, test_suite.TIMEOUT_SECONDS)
        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite.os.killpg") as killpg,
        ):
            process = popen.return_value.__enter__.return_value
            process.pid = 4242
            process.wait.side_effect = [
                subprocess.TimeoutExpired(cmd="suite", timeout=1),
                -9,
            ]
            self.assertEqual(test_suite.TIMED_OUT, test_suite.run(ROOT))
        killpg.assert_called_once_with(4242, signal.SIGKILL)
        self.assertEqual(124, test_suite.TIMED_OUT)

    def test_fast_runs_the_suite_through_the_owner(self) -> None:
        verify = (ROOT / "ci" / "verify").read_text(encoding="utf-8-sig")
        fast = verify.split("  fast)", 1)[1].split("    ;;", 1)[0]
        self.assertIn("python -m tools.test_suite", fast)
        self.assertNotIn("unittest discover", fast)

    def test_self_check_runs_the_suite_through_the_owner(self) -> None:
        from tools import self_check

        with patch("tools.test_suite.run", return_value=0) as run:
            self.assertTrue(self_check.self_check(ROOT))
        run.assert_called_once_with(ROOT.resolve())

    def test_the_runner_is_declared_and_pinned(self) -> None:
        project = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8-sig")
        )
        self.assertIn(
            "unittest-parallel",
            {
                d.split(">")[0].split("=")[0].strip()
                for d in project["project"]["dependencies"]
            },
        )
        runtime = (ROOT / "requirements" / "runtime.lock").read_text(
            encoding="utf-8-sig"
        )
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
