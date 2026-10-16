from __future__ import annotations

import selectors
import subprocess  # nosec B404 -- test-only: real children of this interpreter
import sys
import time
import unittest
from unittest import mock

from tools import bounded_process


class _Children(unittest.TestCase):
    """Real children, killed and reaped after each test whatever it left."""

    def setUp(self) -> None:
        self.children: list[subprocess.Popen[bytes]] = []
        self.addCleanup(self._kill_leftovers)

    def _kill_leftovers(self) -> None:
        for process in self.children:
            if process.poll() is None:
                process.kill()
            # Bounded, so that a child that survives its kill fails the cleanup
            # instead of hanging the suite (Amazon Q on #437).
            process.wait(timeout=10)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()

    def _child(self, script: str) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- test-only: this interpreter, a literal script
            [sys.executable, "-c", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.children.append(process)
        return process

    def _drain(
        self, process: subprocess.Popen[bytes], *, seconds: float = 10, cap: int = 64
    ) -> tuple[bounded_process.Drained, dict[str, bytes]]:
        received: dict[str, bytes] = {"out": b"", "err": b""}

        def sink(name: str, chunk: bytes) -> None:
            received[name] += chunk

        if process.stdout is None or process.stderr is None:
            self.fail("the child has no pipes")
        drained = bounded_process.drain(
            process,
            {"out": process.stdout, "err": process.stderr},
            sink,
            deadline=time.monotonic() + seconds,
            cap=cap,
        )
        return drained, received


class DrainTests(_Children):
    """One deadline-bounded, byte-capped drain of a direct child's pipes (#365's
    admitted factor, 6218886743), against its two consumers' controls."""

    def test_a_child_that_exits_is_drained_whole(self) -> None:
        process = self._child(
            "import sys; sys.stdout.buffer.write(b'o' * 64); "
            "sys.stderr.buffer.write(b'e' * 10); sys.exit(3)"
        )
        drained, received = self._drain(process)
        self.assertEqual(("exited", 3), (drained.outcome, drained.returncode))
        self.assertEqual({"out": b"o" * 64, "err": b"e" * 10}, received)

    def test_the_chunk_that_crosses_the_cap_is_never_delivered(self) -> None:
        # The diagnostic inventory's sink keeps the chunks before the crossing one,
        # never a trimmed part of it (the PAO on #436, 6220140281): one write of 65
        # bytes past a cap of 64 delivers nothing, as its s03 kept 0 bytes.
        process = self._child("import sys; sys.stdout.buffer.write(b'x' * 65)")
        drained, received = self._drain(process)
        self.assertEqual(("cap", "out"), (drained.outcome, drained.stream))
        self.assertEqual(b"", received["out"])
        self.assertIsNone(drained.returncode)

    def test_the_chunks_before_the_crossing_one_are_delivered(self) -> None:
        # The child writes its second chunk only after the sink holds the first: a
        # handshake on its stdin, never a sleep (Sourcery on #437).
        process = subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- test-only: this interpreter, a literal script
            [
                sys.executable,
                "-c",
                "import sys\nsys.stdout.buffer.write(b'a' * 40); sys.stdout.flush()\n"
                "sys.stdin.read(1)\nsys.stdout.buffer.write(b'b' * 40); sys.stdout.flush()",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.children.append(process)
        if process.stdin is None or process.stdout is None or process.stderr is None:
            self.fail("the child has no pipes")
        received = {"out": b"", "err": b""}

        def sink(name: str, chunk: bytes) -> None:
            received[name] += chunk
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.write(b"go")
                process.stdin.close()

        drained = bounded_process.drain(
            process,
            {"out": process.stdout, "err": process.stderr},
            sink,
            deadline=time.monotonic() + 10,
            cap=64,
        )
        self.assertEqual(("cap", "out"), (drained.outcome, drained.stream))
        self.assertEqual(b"a" * 40, received["out"])

    def test_endless_output_stops_at_the_cap_at_once(self) -> None:
        process = self._child(
            "import sys\nwhile True: sys.stderr.buffer.write(b'x' * 65536)"
        )
        began = time.monotonic()
        drained, received = self._drain(process, seconds=30)
        self.assertEqual(("cap", "err"), (drained.outcome, drained.stream))
        self.assertLess(time.monotonic() - began, 5)
        self.assertLessEqual(len(received["err"]), 64)

    def test_a_silent_child_stops_at_the_deadline(self) -> None:
        process = self._child("import time; time.sleep(30)")
        began = time.monotonic()
        drained, _ = self._drain(process, seconds=0.5)
        self.assertEqual("deadline", drained.outcome)
        # One second of scheduling margin past the 0.5-second deadline, never more
        # (Sourcery on #437).
        self.assertLess(time.monotonic() - began, 1.5)

    def test_a_spent_deadline_reads_nothing(self) -> None:
        process = self._child("import sys; sys.stdout.write('late')")
        process.wait()
        drained, received = self._drain(process, seconds=-1)
        self.assertEqual("deadline", drained.outcome)
        self.assertEqual({"out": b"", "err": b""}, received)

    def test_an_exit_wait_past_the_deadline_stops_there(self) -> None:
        # Both pipes close early, but the child outlives the deadline.
        process = self._child(
            "import os, time; os.close(1); os.close(2); time.sleep(30)"
        )
        began = time.monotonic()
        drained, _ = self._drain(process, seconds=0.5)
        self.assertEqual("deadline", drained.outcome)
        self.assertLess(time.monotonic() - began, 1.5)

    def test_a_batch_already_selected_is_read_past_the_deadline_then_stops(
        self,
    ) -> None:
        # The legacy limit the factor preserves (Router 6221408680 on #437): the
        # deadline is checked before select, so a slow sink lets the rest of the same
        # batch be read late, and the next loop stops at the deadline.
        process = self._child(
            "import sys\nsys.stdout.write('o'); sys.stdout.flush()\n"
            "sys.stderr.write('e'); sys.stderr.flush()\nimport time; time.sleep(30)"
        )
        if process.stdout is None or process.stderr is None:
            self.fail("the child has no pipes")
        # Both streams are readable before the drain starts: waited for, never slept
        # for (cubic and CodeAnt on #437).
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            ready.register(process.stderr, selectors.EVENT_READ)
            waited = time.monotonic() + 10
            while len(ready.select(1)) < 2 and time.monotonic() < waited:
                pass
        received: dict[str, bytes] = {"out": b"", "err": b""}

        def slow_sink(name: str, chunk: bytes) -> None:
            received[name] += chunk
            time.sleep(1.0)  # past the deadline, before the other stream is read

        if process.stdout is None or process.stderr is None:
            self.fail("the child has no pipes")
        drained = bounded_process.drain(
            process,
            {"out": process.stdout, "err": process.stderr},
            slow_sink,
            deadline=time.monotonic() + 0.5,
            cap=64,
        )
        self.assertEqual("deadline", drained.outcome)
        self.assertEqual({"out": b"o", "err": b"e"}, received)

    def test_the_exit_wait_takes_only_what_is_left_of_the_deadline(self) -> None:
        # Deterministic, with no wall-clock threshold (the owner's audit on #437): the
        # wait gets the time remaining, a timeout there is the deadline, and a spent
        # deadline never waits at all.
        process = mock.Mock(spec=subprocess.Popen)
        process.wait.return_value = 0
        with mock.patch.object(bounded_process.time, "monotonic", return_value=100.0):
            drained = bounded_process.drain(
                process, {}, mock.Mock(), deadline=105.0, cap=64
            )
        self.assertEqual(("exited", 0), (drained.outcome, drained.returncode))
        process.wait.assert_called_once_with(timeout=5.0)
        process.wait.side_effect = subprocess.TimeoutExpired(["child"], 5)
        with mock.patch.object(bounded_process.time, "monotonic", return_value=100.0):
            drained = bounded_process.drain(
                process, {}, mock.Mock(), deadline=105.0, cap=64
            )
        self.assertEqual("deadline", drained.outcome)
        process.wait.reset_mock()
        with mock.patch.object(bounded_process.time, "monotonic", return_value=105.0):
            drained = bounded_process.drain(
                process, {}, mock.Mock(), deadline=105.0, cap=64
            )
        self.assertEqual("deadline", drained.outcome)
        process.wait.assert_not_called()

    def test_a_read_error_is_returned_not_raised(self) -> None:
        process = self._child("import time; print('x', flush=True); time.sleep(30)")
        with mock.patch.object(
            bounded_process.os, "read", side_effect=OSError(5, "read failed")
        ):
            drained, _ = self._drain(process)
        self.assertEqual("error", drained.outcome)
        self.assertIsInstance(drained.error, OSError)

    def test_an_unexpected_failure_is_returned_with_the_selector_state(self) -> None:
        class Failing:
            def register(self, *args: object) -> None:
                raise RuntimeError("register failed")

            def close(self) -> None:
                raise OSError("cannot close")

        process = self._child("import time; time.sleep(30)")
        with mock.patch.object(bounded_process.selectors, "DefaultSelector", Failing):
            drained, _ = self._drain(process)
        self.assertEqual("unexpected", drained.outcome)
        self.assertIsInstance(drained.exception, RuntimeError)
        self.assertFalse(drained.selector_closed)

    def test_a_selector_close_failure_of_any_kind_is_returned(self) -> None:
        # Sourcery on #437: a close failure other than OSError escaped drain(), and
        # the scanner then skipped its reap of a running child.
        class Failing:
            def register(self, *args: object) -> None:
                raise RuntimeError("register failed")

            def close(self) -> None:
                raise RuntimeError("cannot close")

        process = self._child("import time; time.sleep(30)")
        with mock.patch.object(bounded_process.selectors, "DefaultSelector", Failing):
            drained, _ = self._drain(process)
        self.assertEqual("unexpected", drained.outcome)
        self.assertFalse(drained.selector_closed)

    def test_a_selector_close_failure_alone_keeps_the_outcome(self) -> None:
        # The PAO's T1 on #437: with no other failure, the drain's own outcome stands,
        # and the close failure is reported beside it.
        real = bounded_process.selectors.DefaultSelector

        class CloseFails(real):
            def close(self) -> None:
                super().close()
                raise OSError("cannot close")

        process = self._child("import sys; sys.stdout.write('ok'); sys.exit(4)")
        with mock.patch.object(
            bounded_process.selectors, "DefaultSelector", CloseFails
        ):
            drained, received = self._drain(process)
        self.assertEqual(("exited", 4), (drained.outcome, drained.returncode))
        self.assertFalse(drained.selector_closed)
        self.assertEqual(b"ok", received["out"])

    def test_a_batch_returned_after_the_deadline_is_read_then_the_drain_stops(
        self,
    ) -> None:
        # The PAO's T1 and the Router (6221408680) on #437: a select that returns ready
        # streams only after the deadline, deterministically. Its batch is still read,
        # as main's scanner read it, and the next loop stops at the deadline.
        real = bounded_process.selectors.DefaultSelector

        class Late(real):
            def select(self, timeout: float | None = None) -> list:
                # Bounded, so that a mutated deadline cannot hold the test.
                time.sleep(min(max(0.0, (timeout or 0.0) + 0.2), 2.0))
                return super().select(0)

        process = self._child(
            "import sys; sys.stdout.write('late'); sys.stdout.flush()"
        )
        process.wait()
        with mock.patch.object(bounded_process.selectors, "DefaultSelector", Late):
            drained, received = self._drain(process, seconds=0.3)
        self.assertEqual("deadline", drained.outcome)
        self.assertEqual(b"late", received["out"])

    def test_draining_kills_nothing_and_closes_nothing(self) -> None:
        # Killing, reaping and closing stay with each consumer.
        process = self._child("import time; time.sleep(30)")
        drained, _ = self._drain(process, seconds=0.3)
        self.assertEqual("deadline", drained.outcome)
        self.assertIsNone(process.poll())
        self.assertFalse(process.stdout.closed or process.stderr.closed)


class ReapTests(_Children):
    """The bounded reap of a direct child: the steps both consumers already take."""

    def test_a_running_child_is_killed_and_its_exit_confirmed(self) -> None:
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.wait.return_value = -9
        self.assertIsNone(bounded_process.reap(process, timeout=5))
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)

    def test_an_exited_child_is_not_killed_but_still_reaped(self) -> None:
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = 0
        process.wait.return_value = 0
        self.assertIsNone(bounded_process.reap(process, timeout=5))
        process.kill.assert_not_called()
        process.wait.assert_called_once_with(timeout=5)

    def test_a_kill_error_is_ignored_and_the_wait_still_bounded(self) -> None:
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.kill.side_effect = OSError("already gone")
        process.wait.return_value = -9
        self.assertIsNone(bounded_process.reap(process, timeout=2))
        process.wait.assert_called_once_with(timeout=2)

    def test_an_unconfirmed_exit_is_returned_not_raised(self) -> None:
        for failure in (
            subprocess.TimeoutExpired(["child"], 5),
            ChildProcessError(10, "no child"),
        ):
            with self.subTest(failure=type(failure).__name__):
                process = mock.Mock(spec=subprocess.Popen)
                process.poll.return_value = None
                process.wait.side_effect = failure
                self.assertIs(failure, bounded_process.reap(process, timeout=5))

    def test_a_kill_or_wait_failure_of_any_kind_is_returned_not_raised(self) -> None:
        # Sourcery on #437: a kill() or wait() failure other than OSError escaped.
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.kill.side_effect = RuntimeError("kill failed")
        process.wait.return_value = -9
        self.assertIsNone(bounded_process.reap(process, timeout=2))
        process.wait.assert_called_once_with(timeout=2)
        failure = RuntimeError("wait failed")
        process.wait.side_effect = failure
        self.assertIs(failure, bounded_process.reap(process, timeout=2))

    def test_a_failed_poll_is_taken_as_running_and_the_wait_still_bounded(self) -> None:
        # CodeAnt on #437: a poll() failure escaped before the kill and the bounded
        # wait. A state that cannot be read is taken as running, so it is killed.
        process = mock.Mock(spec=subprocess.Popen)
        process.poll.side_effect = RuntimeError("poll failed")
        process.wait.return_value = -9
        try:
            failure = bounded_process.reap(process, timeout=2)
        except RuntimeError as exc:
            self.fail(f"reap() raised {exc!r} from poll()")
        self.assertIsNone(failure)
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=2)

    def test_a_real_running_child_is_reaped(self) -> None:
        process = self._child("import time; time.sleep(30)")
        self.assertIsNone(bounded_process.reap(process, timeout=5))
        self.assertIsNotNone(process.poll())


if __name__ == "__main__":
    unittest.main()
