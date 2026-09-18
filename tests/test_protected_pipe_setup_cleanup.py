from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import review_current, security_scan


class _FailingClose(io.BytesIO):
    def __init__(self) -> None:
        super().__init__()
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1
        raise OSError("sensitive stream error must not enter diagnostics")


class IncompletePipeCleanupTests(unittest.TestCase):
    def _invoke(self, runner: str, process: mock.Mock) -> str:
        error_type = (
            review_current.ProtectedJudgeUnavailable
            if runner == "docker"
            else security_scan.SecurityScanError
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch("subprocess.Popen", return_value=process),
            mock.patch.object(
                review_current, "_docker_executable", return_value="/usr/bin/docker"
            ),
            mock.patch.object(
                review_current, "_cleanup_container", return_value=None
            ) as cleanup,
            self.assertRaises(error_type) as raised,
        ):
            if runner == "docker":
                review_current._run_docker(
                    ["run", "--rm", "fixture-image"],
                    config_dir=Path(directory),
                    input_bytes=b"synthetic input",
                )
            else:
                security_scan._run_bounded_scan(
                    ["fixture-scanner"], cwd=Path(directory), timeout=10
                )
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
        if runner == "docker":
            cleanup.assert_called_once()
            self.assertTrue(cleanup.call_args.args[0].name)
        else:
            cleanup.assert_not_called()
        message = str(raised.exception)
        self.assertIn("pipes are unavailable", message.split(";")[0])
        return message

    def test_missing_pipe_aborts_and_closes_every_surviving_stream(self) -> None:
        for runner in ("scanner", "docker"):
            names = (
                ("stdout", "stderr", "stdin")
                if runner == "docker"
                else ("stdout", "stderr")
            )
            for missing in names:
                with self.subTest(runner=runner, missing=missing):
                    streams = {name: io.BytesIO() for name in names if name != missing}
                    process = mock.Mock(stdin=None, stdout=None, stderr=None)
                    process.poll.return_value = None
                    process.wait.return_value = -9
                    for name, stream in streams.items():
                        setattr(process, name, stream)
                    try:
                        self._invoke(runner, process)
                        self.assertTrue(
                            all(stream.closed for stream in streams.values())
                        )
                    finally:
                        for stream in streams.values():
                            stream.close()

    def test_close_failure_preserves_primary_and_remaining_cleanup(self) -> None:
        for runner in ("scanner", "docker"):
            with self.subTest(runner=runner):
                failing = _FailingClose()
                other = io.BytesIO()
                process = mock.Mock(stdout=failing, stderr=None, stdin=other)
                process.poll.return_value = None
                process.wait.side_effect = subprocess.TimeoutExpired("fixture", 5)
                try:
                    message = self._invoke(runner, process)
                    self.assertEqual(1, failing.close_calls)
                    self.assertTrue(other.closed)
                    self.assertIn("reap", message)
                    self.assertIn("stdout pipe could not be closed", message)
                    self.assertNotIn("sensitive stream error", message)
                finally:
                    io.BytesIO.close(failing)
                    other.close()


if __name__ == "__main__":
    unittest.main()
