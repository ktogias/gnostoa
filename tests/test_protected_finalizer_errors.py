from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from tools import review_current, security_scan

_SENTINEL = "private final-close exception must not be published"


class _Stream(io.BytesIO):
    def __init__(self, *, fails: bool = False) -> None:
        super().__init__()
        self.fails = fails
        self.close_attempts = 0

    def fileno(self) -> int:
        return 10

    def close(self) -> None:
        self.close_attempts += 1
        if self.fails:
            raise OSError(_SENTINEL)
        super().close()


class FinalizerErrorTests(unittest.TestCase):
    def test_runner_finalizers_preserve_primary_and_attempt_every_role(self) -> None:
        for runner in ("docker", "scanner"):
            roles = (
                ("selector", "stdout", "stderr", "stdin")
                if runner == "docker"
                else ("selector", "stdout", "stderr")
            )
            for failure in ("timeout", "io", "overflow", "success"):
                for failed_role in roles:
                    with self.subTest(runner=runner, failure=failure, role=failed_role):
                        streams = {
                            role: _Stream(fails=role == failed_role)
                            for role in roles
                            if role != "selector"
                        }
                        process = mock.Mock(**{"stdin": None, **streams})
                        if runner == "docker":
                            process.stdin = streams["stdin"]
                        process.wait.return_value = 0
                        process.poll.return_value = None
                        selector = mock.Mock()
                        selector.get_map.return_value = (
                            {} if failure == "success" else {10: True}
                        )
                        if failed_role == "selector":
                            selector.close.side_effect = OSError(_SENTINEL)
                        if failure == "timeout":
                            selector.select.return_value = []
                        elif failure == "io":
                            selector.select.side_effect = OSError(
                                "synthetic primary I/O"
                            )
                        else:
                            selector.select.return_value = [
                                (
                                    SimpleNamespace(
                                        data="stdout"
                                        if runner == "docker"
                                        else "report",
                                        fd=10,
                                    ),
                                    1,
                                )
                            ]
                        module = review_current if runner == "docker" else security_scan
                        error_type = (
                            review_current.ProtectedJudgeUnavailable
                            if runner == "docker"
                            else security_scan.SecurityScanError
                        )
                        try:
                            with (
                                tempfile.TemporaryDirectory() as directory,
                                mock.patch("subprocess.Popen", return_value=process),
                                mock.patch(
                                    "selectors.DefaultSelector", return_value=selector
                                ),
                                mock.patch.object(
                                    review_current,
                                    "_docker_executable",
                                    return_value="/usr/bin/docker",
                                ),
                                mock.patch.object(
                                    review_current,
                                    "_cleanup_container",
                                    return_value=None,
                                ),
                                mock.patch("os.read", return_value=b"xxx"),
                                mock.patch("os.set_blocking"),
                                mock.patch.object(
                                    module,
                                    "_MAX_RUNTIME_OUTPUT_BYTES"
                                    if runner == "docker"
                                    else "_MAX_REPORT_BYTES",
                                    2,
                                ),
                                self.assertRaises(error_type) as raised,
                            ):
                                if runner == "docker":
                                    review_current._run_docker(
                                        ["run", "--rm", "fixture"],
                                        config_dir=Path(directory),
                                        input_bytes=b"test",
                                    )
                                else:
                                    security_scan._run_bounded_scan(
                                        ["fixture"], cwd=Path(directory), timeout=10
                                    )
                            message = str(raised.exception)
                            self.assertNotIn(_SENTINEL, message)
                            self.assertIn(failed_role, message)
                            if failure == "timeout":
                                self.assertIn("timed out", message.split(";")[0])
                            elif failure == "overflow":
                                self.assertIn("exceeds", message.split(";")[0])
                            elif failure == "io":
                                self.assertTrue(
                                    message.startswith(
                                        "protected Docker execution failed"
                                        if runner == "docker"
                                        else "cannot execute the tracked-tree secret scan"
                                    )
                                )
                            selector.close.assert_called_once_with()
                            for stream in streams.values():
                                self.assertEqual(1, stream.close_attempts)
                            if failure != "success":
                                process.kill.assert_called_once_with()
                        finally:
                            for stream in streams.values():
                                io.BytesIO.close(stream)

    def test_cleanup_diagnostic_retains_status_and_closes_after_selector_failure(
        self,
    ) -> None:
        for failure in ("timeout", "io", "overflow", "success"):
            for failed_role in ("selector", "stderr"):
                with self.subTest(failure=failure, role=failed_role):
                    stream = _Stream(fails=failed_role == "stderr")
                    process = mock.Mock(stderr=stream)
                    process.poll.return_value = None if failure != "success" else 0
                    process.wait.return_value = 0
                    selector = mock.Mock()
                    selector.get_map.return_value = (
                        {} if failure == "success" else {10: True}
                    )
                    if failed_role == "selector":
                        selector.close.side_effect = OSError(_SENTINEL)
                    if failure == "timeout":
                        selector.select.return_value = []
                    elif failure == "io":
                        selector.select.side_effect = OSError("synthetic primary I/O")
                    else:
                        selector.select.return_value = [True]
                    try:
                        with (
                            tempfile.TemporaryDirectory() as directory,
                            mock.patch("subprocess.Popen", return_value=process),
                            mock.patch(
                                "selectors.DefaultSelector", return_value=selector
                            ),
                            mock.patch("os.read", return_value=b"x" * 257),
                            mock.patch.object(
                                review_current, "_MAX_CLEANUP_DIAGNOSTIC_BYTES", 256
                            ),
                        ):
                            code, detail = review_current._cleanup_diagnostic(
                                ["docker", "rm", "fixture"], config_dir=Path(directory)
                            )
                        self.assertEqual(0 if failure == "success" else None, code)
                        self.assertIn(failed_role, detail)
                        self.assertNotIn(_SENTINEL, detail)
                        self.assertLessEqual(len(detail.encode("utf-8")), 256)
                        if failure == "timeout":
                            self.assertIn("timed out", detail.split(";")[0])
                        elif failure == "io":
                            self.assertIn("synthetic primary I/O", detail.split(";")[0])
                        elif failure == "overflow":
                            self.assertIn("bounded size", detail.split(";")[0])
                        selector.close.assert_called_once_with()
                        self.assertEqual(1, stream.close_attempts)
                        self.assertIn(mock.call(timeout=5), process.wait.call_args_list)
                        if failure != "success":
                            process.kill.assert_called_once_with()
                    finally:
                        io.BytesIO.close(stream)

    def test_missing_input_pipe_is_not_diagnosed_as_output_failure(self) -> None:
        streams = {role: _Stream() for role in ("stdout", "stderr")}
        process = mock.Mock(**{"stdin": None, **streams})
        process.poll.return_value = None
        process.wait.return_value = -9
        try:
            with (
                tempfile.TemporaryDirectory() as directory,
                mock.patch("subprocess.Popen", return_value=process),
                mock.patch.object(
                    review_current, "_docker_executable", return_value="/usr/bin/docker"
                ),
                mock.patch.object(
                    review_current, "_cleanup_container", return_value=None
                ),
                self.assertRaises(review_current.ProtectedJudgeUnavailable) as raised,
            ):
                review_current._run_docker(
                    ["run", "--rm", "fixture"],
                    config_dir=Path(directory),
                    input_bytes=b"test",
                )
            self.assertIn("input pipes are unavailable", str(raised.exception))
            self.assertNotIn("output pipes", str(raised.exception))
        finally:
            for stream in streams.values():
                io.BytesIO.close(stream)


if __name__ == "__main__":
    unittest.main()
