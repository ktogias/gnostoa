"""The repository's test suite runs in parallel processes, through one owner
(Decision 0109)."""

from __future__ import annotations

import os
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Linux records a thread's children only when built with CONFIG_PROC_CHILDREN
# (Codex on #392).
_RECORDS_CHILDREN = Path(f"/proc/self/task/{os.getpid()}/children").is_file()


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

    def test_a_suite_past_its_bound_is_interrupted_so_its_pool_ends_its_workers(
        self,
    ) -> None:
        """Past the bound the runner is interrupted, and its pool ends its own workers,
        on every system (Kody, Codex and CodeAnt on #392); the status says the bound
        was reached."""
        import signal
        import subprocess  # nosec B404 -- test-only: the timeout the owner catches

        from tools import test_suite

        self.assertEqual(3600, test_suite.TIMEOUT_SECONDS)
        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite.os.kill") as kill,
        ):
            process = popen.return_value.__enter__.return_value
            process.wait.side_effect = [
                # An exception the stub raises, not a process: nothing is run.
                subprocess.TimeoutExpired("suite", 1),  # nosemgrep
                -2,
            ]
            self.assertEqual(test_suite.TIMED_OUT, test_suite.run(ROOT))
        process.send_signal.assert_called_once_with(signal.SIGINT)
        self.assertEqual(
            [((), {"timeout": 3600}), ((), {"timeout": test_suite.GRACE_SECONDS})],
            [(call.args, call.kwargs) for call in process.wait.call_args_list],
        )
        kill.assert_not_called()
        self.assertEqual(124, test_suite.TIMED_OUT)
        self.assertEqual(10, test_suite.GRACE_SECONDS)

    def test_a_runner_past_its_grace_is_killed_with_its_descendants(self) -> None:
        """A runner still running after its grace is killed, its recorded
        descendants first, deepest first."""
        import signal
        import subprocess  # nosec B404 -- test-only: the timeout the owner catches

        from tools import test_suite

        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite._descendants", return_value=[12, 11]),
            patch("tools.test_suite.os.kill") as kill,
        ):
            process = popen.return_value.__enter__.return_value
            process.pid = 4242
            process.wait.side_effect = [
                # Exceptions the stub raises, not processes: nothing is run.
                subprocess.TimeoutExpired("suite", 1),  # nosemgrep
                subprocess.TimeoutExpired("suite", 1),  # nosemgrep
                -9,
            ]
            self.assertEqual(test_suite.TIMED_OUT, test_suite.run(ROOT))
        self.assertEqual(
            [(12, signal.SIGKILL), (11, signal.SIGKILL), (4242, signal.SIGKILL)],
            [call.args for call in kill.call_args_list],
        )
        self.assertEqual(
            [{"timeout": 3600}, {"timeout": test_suite.GRACE_SECONDS}, {}],
            [call.kwargs for call in process.wait.call_args_list],
        )

    def test_a_process_that_ended_before_its_kill_is_passed_over(self) -> None:
        """A process may end between its grace and its kill; the stop is still
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
                # Exceptions the stub raises, not processes: nothing is run.
                subprocess.TimeoutExpired("suite", 1),  # nosemgrep
                subprocess.TimeoutExpired("suite", 1),  # nosemgrep
                0,
            ]
            self.assertEqual(test_suite.TIMED_OUT, test_suite.run(ROOT))
        self.assertEqual(2, kill.call_count)

    def test_an_interrupt_waits_for_the_runner_it_reached_and_is_raised(self) -> None:
        """A terminal's Ctrl+C reaches the runner in the same group, so the owner
        does not interrupt it again, which could cut its pool's cleanup short; it
        waits for it and raises the interrupt again (CodeReviewBot.ai on #392)."""
        from tools import test_suite

        with (
            patch("tools.test_suite.subprocess.Popen") as popen,
            patch("tools.test_suite.os.kill") as kill,
        ):
            process = popen.return_value.__enter__.return_value
            process.wait.side_effect = [KeyboardInterrupt, -2]
            with self.assertRaises(KeyboardInterrupt):
                test_suite.run(ROOT)
        process.send_signal.assert_not_called()
        process.wait.assert_called_with(timeout=test_suite.GRACE_SECONDS)
        kill.assert_not_called()

    def test_another_error_interrupts_the_runner_and_is_raised(self) -> None:
        """Any other error while waiting reached only the owner, so the runner is
        interrupted, and the error raised again."""
        import signal

        from tools import test_suite

        with patch("tools.test_suite.subprocess.Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.wait.side_effect = [MemoryError, -2]
            with self.assertRaises(MemoryError):
                test_suite.run(ROOT)
        process.send_signal.assert_called_once_with(signal.SIGINT)

    def test_a_hung_worker_ends_with_its_runner_where_no_record_lists_it(
        self,
    ) -> None:
        """The real runner, with a test that hangs: at the bound, its worker ends
        although no record of children lists it, as on macOS (Codex and CodeAnt on
        #392)."""
        import signal
        import subprocess  # nosec B404 -- test-only: the real runner, this interpreter
        import tempfile
        import time

        from tools import test_suite

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            started = root / "worker.pid"
            (root / "tests").mkdir()
            (root / "tests" / "test_hang.py").write_text(
                "import os\nimport time\nimport unittest\n\n\n"
                "class Hang(unittest.TestCase):\n"
                "    def test_hang(self):\n"
                f"        os.replace(os.path.join({str(root)!r}, 'tmp.pid'), "
                f"{str(started)!r}) if open(os.path.join({str(root)!r}, 'tmp.pid'), "
                "'w').write(str(os.getpid())) else None\n"
                "        time.sleep(600)\n",
                encoding="utf-8",
            )

            class ReachesItsBoundOnceStarted(subprocess.Popen[bytes]):
                """The bound is reached once the worker has started the test."""

                def wait(self, timeout: float | None = None) -> int:
                    if timeout == test_suite.TIMEOUT_SECONDS:
                        deadline = time.monotonic() + 60
                        while not started.exists() and time.monotonic() < deadline:
                            time.sleep(0.05)
                        raise subprocess.TimeoutExpired(self.args, timeout)  # nosemgrep
                    return super().wait(timeout)

            with (
                patch("tools.test_suite.subprocess.Popen", ReachesItsBoundOnceStarted),
                patch("tools.test_suite._children", return_value=[]),
            ):
                self.assertEqual(test_suite.TIMED_OUT, test_suite.run(root))
            worker = int(started.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(worker, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                os.kill(worker, signal.SIGKILL)
                self.fail(f"the hung worker {worker} outlived its runner")

    def test_descendants_are_listed_deepest_first(self) -> None:
        from tools import test_suite

        tree = {1: [2, 3], 2: [4], 3: [], 4: []}
        with patch("tools.test_suite._children", side_effect=lambda pid: tree[pid]):
            self.assertEqual([4, 3, 2], test_suite._descendants(1))  # skipcq: PYL-W0212

    @unittest.skipUnless(
        _RECORDS_CHILDREN, "this kernel keeps no record of a thread's children"
    )
    def test_a_live_child_is_found_through_the_system_s_record(self) -> None:
        """Under the parallel runner a test runs in a daemonic worker, which
        `multiprocessing` refuses children; a plain process is allowed."""
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
