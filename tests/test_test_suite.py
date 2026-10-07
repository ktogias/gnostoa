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

    def test_run_stays_in_the_caller_s_group_and_returns_its_status(self) -> None:
        """No session of its own: the caller's containment, as preparation's kill of
        its focused group, reaches the runner and its workers (Codex on #392)."""
        from tools import test_suite

        with patch("tools.test_suite.subprocess.Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.wait.return_value = 3
            self.assertEqual(3, test_suite.run(ROOT, environment={"A": "1"}))
        popen.assert_called_once_with(
            test_suite.command(sys.executable), cwd=ROOT, env={"A": "1"}
        )
        process.wait.assert_called_once_with(timeout=test_suite.TIMEOUT_SECONDS)

    def test_a_suite_past_its_bound_is_stopped_with_its_workers(self) -> None:
        """Past the bound the runner's descendants are killed, deepest first, then
        the runner, and the status says the bound was reached (Kody on #392)."""
        import signal
        import subprocess  # nosec B404 -- test-only: the timeout the owner catches

        from tools import test_suite

        self.assertEqual(3600, test_suite.TIMEOUT_SECONDS)
        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite._descendants", return_value=[12, 11]),
            patch("tools.test_suite.os.kill") as kill,
        ):
            process = popen.return_value.__enter__.return_value
            process.pid = 4242
            process.wait.side_effect = [
                # An exception the stub raises, not a process: nothing is run.
                subprocess.TimeoutExpired(
                    cmd="suite", timeout=1
                ),  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                -9,
            ]
            self.assertEqual(test_suite.TIMED_OUT, test_suite.run(ROOT))
        self.assertEqual(
            [
                ((12, signal.SIGKILL),),
                ((11, signal.SIGKILL),),
                ((4242, signal.SIGKILL),),
            ],
            [call.args and (call.args,) for call in kill.call_args_list],
        )
        self.assertEqual(124, test_suite.TIMED_OUT)

    def test_a_process_that_ended_before_its_kill_is_passed_over(self) -> None:
        """A process may end between the bound and its kill; the stop is still
        reported, not raised (Amazon Q and Claude on #392)."""
        import subprocess  # nosec B404 -- test-only: the timeout the owner catches

        from tools import test_suite

        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite._descendants", return_value=[11]),
            patch("tools.test_suite.os.kill", side_effect=ProcessLookupError) as kill,
        ):
            process = popen.return_value.__enter__.return_value
            process.wait.side_effect = [
                # An exception the stub raises, not a process: nothing is run.
                subprocess.TimeoutExpired(
                    cmd="suite", timeout=1
                ),  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                0,
            ]
            self.assertEqual(test_suite.TIMED_OUT, test_suite.run(ROOT))
        self.assertEqual(2, kill.call_count)

    def test_an_interrupt_stops_the_runner_and_is_raised(self) -> None:
        """An interrupt while waiting stops the runner and its descendants, and is
        raised again (CodeReviewBot.ai on #392)."""
        import signal

        from tools import test_suite

        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite._descendants", return_value=[11]),
            patch("tools.test_suite.os.kill") as kill,
        ):
            process = popen.return_value.__enter__.return_value
            process.pid = 4242
            process.wait.side_effect = [KeyboardInterrupt, -9]
            with self.assertRaises(KeyboardInterrupt):
                test_suite.run(ROOT)
        self.assertEqual(
            [(11, signal.SIGKILL), (4242, signal.SIGKILL)],
            [call.args for call in kill.call_args_list],
        )

    def test_descendants_are_listed_deepest_first(self) -> None:
        from tools import test_suite

        tree = {1: [2, 3], 2: [4], 3: [], 4: []}
        with patch("tools.test_suite._children", side_effect=lambda pid: tree[pid]):
            self.assertEqual([4, 3, 2], test_suite._descendants(1))  # skipcq: PYL-W0212

    @unittest.skipUnless(Path("/proc/self/task").is_dir(), "Linux records children")
    def test_a_live_child_is_found_through_the_system_s_record(self) -> None:
        """Under the parallel runner a test runs in a daemonic worker, which
        `multiprocessing` refuses children; a plain process is allowed."""
        import os
        import subprocess  # nosec B404 -- test-only boundary; the argv below is literal

        from tools import test_suite

        with subprocess.Popen(["sleep", "30"]) as child:  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            try:
                found = test_suite._children(os.getpid())  # skipcq: PYL-W0212
            finally:
                child.kill()
        self.assertIn(child.pid, found)
        self.assertEqual([], test_suite._children(-1))  # skipcq: PYL-W0212

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
            encoding="utf-8-sig"
        )
        self.assertIn("\nunittest-parallel==1.8.6 \\\n", runtime)
        # unittest-parallel imports coverage unconditionally, so the runtime image
        # holds it too.
        self.assertIn("\ncoverage==", runtime)
        self.assertIn("\nunittest-parallel==1.8.6 \\\n", development)


if __name__ == "__main__":
    unittest.main()
