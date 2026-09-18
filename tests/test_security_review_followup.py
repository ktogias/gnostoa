from __future__ import annotations

import errno
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_security_gates import _report

from tools import review_current, security_scan

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = "private exception body must never be published"


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
            raise OSError(PRIVATE)
        super().close()


class ReviewFollowupTests(unittest.TestCase):
    def test_completed_run_reports_cid_discard_failure(self) -> None:
        for child_code in (0, 3):
            with self.subTest(child_code=child_code):
                process = mock.Mock(stdout=_Stream(), stderr=_Stream(), stdin=None)
                process.wait.return_value = child_code
                process.poll.return_value = child_code
                selector = mock.Mock()
                selector.get_map.return_value = {}
                with (
                    tempfile.TemporaryDirectory() as directory,
                    mock.patch("subprocess.Popen", return_value=process),
                    mock.patch("selectors.DefaultSelector", return_value=selector),
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="/usr/bin/docker",
                    ),
                    mock.patch.object(
                        Path, "unlink", side_effect=OSError(errno.EACCES, PRIVATE)
                    ) as unlink,
                    mock.patch.object(review_current, "_cleanup_container") as cleanup,
                    self.assertRaises(
                        review_current.ProtectedJudgeUnavailable
                    ) as raised,
                ):
                    review_current._run_docker(
                        ["run", "--rm", "fixture"], config_dir=Path(directory)
                    )
                message = str(raised.exception)
                self.assertIn("cleanup identity file", message)
                if child_code:
                    self.assertTrue(
                        message.startswith(
                            f"protected Docker process exited with status {child_code}"
                        )
                    )
                self.assertNotIn(PRIVATE, message)
                self.assertNotIn("recovery identity", str(raised.exception))
                unlink.assert_called_once()
                cleanup.assert_not_called()
                self.assertTrue(process.stdout.closed and process.stderr.closed)

    def test_full_cleanup_prefix_keeps_close_roles_and_command_status(self) -> None:
        for prefix in (b"x" * 4096, b"\xce\xb1" * 2048, b"x" * 4095 + b"\xce"):
            for child_code in (0, 1):
                with self.subTest(prefix_end=prefix[-3:], child_code=child_code):
                    stream = _Stream(fails=True)
                    process = mock.Mock(stderr=stream)
                    process.wait.return_value = child_code
                    process.poll.return_value = child_code
                    selector = mock.Mock()
                    selector.get_map.side_effect = [{10: True}, {}]
                    selector.select.return_value = [True]
                    selector.close.side_effect = OSError(PRIVATE)
                    try:
                        with (
                            tempfile.TemporaryDirectory() as directory,
                            mock.patch("subprocess.Popen", return_value=process),
                            mock.patch(
                                "selectors.DefaultSelector", return_value=selector
                            ),
                            mock.patch("os.read", return_value=prefix),
                        ):
                            code, detail = review_current._cleanup_diagnostic(
                                ["docker", "rm", "fixture"], config_dir=Path(directory)
                            )
                        self.assertEqual(child_code, code)
                        self.assertIn("cleanup selector could not be closed", detail)
                        self.assertIn("cleanup stderr pipe could not be closed", detail)
                        self.assertLessEqual(len(detail.encode()), 4096)
                        self.assertNotIn(PRIVATE, detail)
                        self.assertEqual(1, stream.close_attempts)
                    finally:
                        io.BytesIO.close(stream)

    def test_scanner_os_error_exposes_only_safe_errno(self) -> None:
        for number, symbol in (
            (errno.EIO, "EIO"),
            (errno.EBADF, "EBADF"),
            (999999, "UNKNOWN"),
            (None, "UNKNOWN"),
        ):
            for phase in ("launch", "read"):
                with self.subTest(number=number, phase=phase):
                    error = OSError(number, PRIVATE, PRIVATE)
                    process = mock.Mock(stdout=_Stream(), stderr=_Stream())
                    process.poll.return_value = 0
                    selector = mock.Mock()
                    selector.get_map.return_value = {10: True}
                    selector.select.side_effect = error
                    with (
                        tempfile.TemporaryDirectory() as directory,
                        mock.patch(
                            "subprocess.Popen",
                            side_effect=error if phase == "launch" else None,
                            return_value=process,
                        ),
                        mock.patch("selectors.DefaultSelector", return_value=selector),
                        self.assertRaises(security_scan.SecurityScanError) as raised,
                    ):
                        security_scan._run_bounded_scan(
                            ["fixture"], cwd=Path(directory), timeout=5
                        )
                    self.assertIn(symbol, str(raised.exception))
                    self.assertNotIn(PRIVATE, str(raised.exception))
                    self.assertLess(len(str(raised.exception)), 256)

    def test_docker_os_errors_expose_only_safe_errno(self) -> None:
        for number, symbol in (
            (errno.EIO, "EIO"),
            (errno.EBADF, "EBADF"),
            (999999, "UNKNOWN"),
            (None, "UNKNOWN"),
        ):
            error = OSError(number, PRIVATE, PRIVATE)
            with (
                self.subTest(number=number, phase="launch"),
                tempfile.TemporaryDirectory() as directory,
                mock.patch.object(
                    review_current, "_docker_executable", return_value="/usr/bin/docker"
                ),
                mock.patch("subprocess.Popen", side_effect=error),
                self.assertRaises(review_current.ProtectedJudgeUnavailable) as raised,
            ):
                review_current._run_docker(
                    ["run", "--rm", "fixture"], config_dir=Path(directory)
                )
            self.assertIn(symbol, str(raised.exception))
            self.assertNotIn(PRIVATE, str(raised.exception))

            with (
                self.subTest(number=number, phase="cleanup"),
                tempfile.TemporaryDirectory() as directory,
                mock.patch("subprocess.Popen", side_effect=error),
            ):
                code, detail = review_current._cleanup_diagnostic(
                    ["docker", "rm", "fixture"], config_dir=Path(directory)
                )
            self.assertIsNone(code)
            self.assertIn(symbol, detail)
            self.assertNotIn(PRIVATE, detail)

    def test_security_gate_filesystem_errors_expose_only_safe_errno(self) -> None:
        error = OSError(errno.EACCES, PRIVATE, PRIVATE)
        with (
            mock.patch.object(Path, "open", side_effect=error),
            self.assertRaises(security_scan.SecurityScanError) as read_error,
        ):
            security_scan._read_document(
                Path("private-baseline"), "detect-secrets baseline"
            )
        self.assertIn("EACCES", str(read_error.exception))
        self.assertNotIn(PRIVATE, str(read_error.exception))

        with (
            mock.patch.object(security_scan.os, "dup", side_effect=error),
            self.assertRaises(security_scan.SecurityScanError) as snapshot_error,
        ):
            security_scan._copy_candidate_to_snapshot(
                10,
                Path("."),
                Path("tracked.txt"),
                deadline=time.monotonic() + 10,
                remaining_total_bytes=1024,
            )
        self.assertIn("EACCES", str(snapshot_error.exception))
        self.assertNotIn(PRIVATE, str(snapshot_error.exception))

    def test_completed_child_status_is_primary_for_close_failures(self) -> None:
        for child_code in (3, -9):
            for finalizer in ("stdout", "selector"):
                with self.subTest(child_code=child_code, finalizer=finalizer):
                    stdout = _Stream(fails=finalizer == "stdout")
                    stderr = _Stream()
                    process = mock.Mock(stdout=stdout, stderr=stderr, stdin=None)
                    process.wait.return_value = child_code
                    process.poll.return_value = child_code
                    selector = mock.Mock()
                    selector.get_map.return_value = {}
                    if finalizer == "selector":
                        selector.close.side_effect = OSError(PRIVATE)
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
                            self.assertRaises(
                                review_current.ProtectedJudgeUnavailable
                            ) as raised,
                        ):
                            review_current._run_docker(
                                ["version"], config_dir=Path(directory)
                            )
                        message = str(raised.exception)
                        self.assertTrue(
                            message.startswith(
                                f"protected Docker process exited with status {child_code}"
                            ),
                            message,
                        )
                        self.assertIn(finalizer, message)
                        self.assertNotIn(PRIVATE, message)
                    finally:
                        io.BytesIO.close(stdout)
                        io.BytesIO.close(stderr)

    def test_snapshot_checks_deadline_between_partial_writes(self) -> None:
        now = [0.0]
        writes = []

        def write(descriptor: int, data: bytes) -> int:
            writes.append(bytes(data))
            now[0] = 61.0
            return 1

        with (
            mock.patch.object(
                security_scan.time, "monotonic", side_effect=lambda: now[0]
            ),
            mock.patch.object(security_scan.os, "write", side_effect=write),
            self.assertRaisesRegex(
                security_scan.SecurityScanError, "snapshot timed out"
            ),
        ):
            security_scan._write_all(10, b"abc", deadline=60.0)
        self.assertEqual([b"abc"], writes)

    def test_expired_snapshot_never_reaches_scanner(self) -> None:
        for operation in ("last-copy-return", "end-of-file-read"):
            with (
                self.subTest(operation=operation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / "tracked.txt").write_text("hello\n")
                (root / ".secrets.baseline").write_text(json.dumps(_report({})))
                now = [0.0]
                real_copy = security_scan._copy_candidate_to_snapshot
                real_read = os.read

                def copy(
                    *args: object,
                    target=real_copy,
                    clock=now,
                    selected=operation,
                    **kwargs: object,
                ) -> int:
                    result = target(*args, **kwargs)
                    if selected == "last-copy-return":
                        clock[0] = 61.0
                    return result

                def read(
                    fd: int, count: int, target=real_read, clock=now, selected=operation
                ) -> bytes:
                    result = target(fd, count)
                    if not result and selected == "end-of-file-read":
                        clock[0] = 61.0
                    return result

                with (
                    mock.patch.object(
                        security_scan.time,
                        "monotonic",
                        side_effect=lambda clock=now: clock[0],
                    ),
                    mock.patch.object(
                        security_scan, "_copy_candidate_to_snapshot", side_effect=copy
                    ),
                    mock.patch.object(security_scan.os, "read", side_effect=read),
                    mock.patch.object(
                        security_scan,
                        "_run_bounded_scan",
                        return_value=subprocess.CompletedProcess(
                            [], 0, json.dumps(_report({})).encode(), b""
                        ),
                    ) as scanner,
                    self.assertRaisesRegex(
                        security_scan.SecurityScanError, "snapshot timed out"
                    ),
                ):
                    security_scan.scan_tracked_tree(
                        root,
                        tracked_paths=[Path("tracked.txt")],
                        baseline_path=root / ".secrets.baseline",
                    )
                scanner.assert_not_called()

    def test_nonblocking_path_input_cannot_classify_a_prefix(self) -> None:
        for prefix in (b"", b"assets/safe.txt\0"):
            with self.subTest(prefix=prefix):
                read_fd, write_fd = os.pipe()
                try:
                    os.set_blocking(read_fd, False)
                    if prefix:
                        os.write(write_fd, prefix)
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            str(ROOT / "tools/extended_route.py"),
                            "--event",
                            "pull_request",
                        ],
                        stdin=read_fd,
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertNotIn(b"NOT_APPLICABLE", result.stdout)
                    self.assertNotIn(b"Traceback", result.stderr)
                    self.assertIn(b"incomplete", result.stderr)
                finally:
                    os.close(read_fd)
                    os.close(write_fd)

    def test_complete_and_oversized_path_input_keep_their_contract(self) -> None:
        for raw, expected in (
            (b"assets/a.txt\0tools/x.py\0", 0),
            (b"x" * 4_194_305, 2),
        ):
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(ROOT / "tools/extended_route.py"),
                    "--event",
                    "pull_request",
                ],
                input=raw,
                capture_output=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(expected, result.returncode)
            if expected == 0:
                self.assertIn(b"RUN", result.stdout)

    def test_strict_input_rejects_early_close_but_generic_mode_survives(self) -> None:
        for strict in (False, True):
            with (
                self.subTest(strict=strict),
                tempfile.TemporaryDirectory() as directory,
            ):
                with mock.patch.object(
                    review_current, "_docker_executable", return_value=sys.executable
                ):
                    args = ["-c", "import os; os.close(0); print('closed')"]
                    if strict:
                        with self.assertRaisesRegex(
                            review_current.ProtectedJudgeUnavailable,
                            "before the envelope was delivered",
                        ):
                            review_current._run_docker(
                                args,
                                config_dir=Path(directory),
                                input_bytes=b"x" * 1_048_576,
                                timeout=5,
                                reject_incomplete_input=True,
                            )
                    else:
                        result = review_current._run_docker(
                            args,
                            config_dir=Path(directory),
                            input_bytes=b"x" * 1_048_576,
                            timeout=5,
                        )
                        self.assertEqual(0, result.returncode)

    def test_strict_transport_accepts_a_complete_write(self) -> None:
        payload = b"bounded input" * 8192
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                review_current, "_docker_executable", return_value=sys.executable
            ):
                result = review_current._run_docker(
                    [
                        "-c",
                        "import sys; data=sys.stdin.buffer.read(); print(len(data))",
                    ],
                    config_dir=Path(directory),
                    input_bytes=payload,
                    timeout=5,
                    reject_incomplete_input=True,
                )
        self.assertEqual(0, result.returncode)
        self.assertEqual(str(len(payload)).encode() + b"\n", result.stdout)

    def test_strict_transport_reaps_and_reconciles_the_container(self) -> None:
        process = mock.Mock(stdout=_Stream(), stderr=_Stream(), stdin=_Stream())
        process.poll.return_value = None
        selector = mock.Mock()
        selector.get_map.return_value = {10: True}
        selector.select.return_value = [(SimpleNamespace(data="stdin", fd=10), 1)]
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch("subprocess.Popen", return_value=process),
            mock.patch("selectors.DefaultSelector", return_value=selector),
            mock.patch.object(
                review_current, "_docker_executable", return_value="/usr/bin/docker"
            ),
            mock.patch.object(
                review_current, "_cleanup_container", return_value=None
            ) as cleanup,
            mock.patch("os.set_blocking"),
            mock.patch("os.write", side_effect=BrokenPipeError(PRIVATE)),
            self.assertRaisesRegex(
                review_current.ProtectedJudgeUnavailable,
                "before the envelope was delivered",
            ) as raised,
        ):
            review_current._run_docker(
                ["run", "--rm", "fixture"],
                config_dir=Path(directory),
                input_bytes=b"abc",
                reject_incomplete_input=True,
            )
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
        cleanup.assert_called_once()
        self.assertTrue(cleanup.call_args.args[0].name.startswith("gnostoa-protected-"))
        self.assertNotIn(PRIVATE, str(raised.exception))
        self.assertTrue(
            all(
                stream.closed
                for stream in (process.stdout, process.stderr, process.stdin)
            )
        )

    def test_launch_sites_explicitly_forbid_shell_interpretation(self) -> None:
        for module, runner in ((review_current, "docker"), (security_scan, "scanner")):
            with (
                self.subTest(runner=runner),
                tempfile.TemporaryDirectory() as directory,
            ):
                process = mock.Mock(stdout=_Stream(), stderr=_Stream(), stdin=None)
                process.wait.return_value = 0
                selector = mock.Mock()
                selector.get_map.return_value = {}
                args = (
                    ["version", "data; not shell code"]
                    if runner == "docker"
                    else [
                        sys.executable,
                        "-I",
                        "-m",
                        "detect_secrets",
                        "scan",
                        "--",
                        "data; not shell code",
                    ]
                )
                with (
                    mock.patch.object(
                        module.subprocess, "Popen", return_value=process
                    ) as popen,
                    mock.patch("selectors.DefaultSelector", return_value=selector),
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="/usr/bin/docker",
                    ),
                ):
                    if runner == "docker":
                        review_current._run_docker(args, config_dir=Path(directory))
                    else:
                        security_scan._run_bounded_scan(
                            args, cwd=Path(directory), timeout=5
                        )
                self.assertIs(popen.call_args.kwargs.get("shell"), False)
                self.assertIsInstance(popen.call_args.args[0], list)
                self.assertEqual(
                    args,
                    popen.call_args.args[0][1:]
                    if runner == "docker"
                    else popen.call_args.args[0],
                )


if __name__ == "__main__":
    unittest.main()
