"""The one owner of a deadline-bounded, byte-capped drain of a direct child's pipes,
and of that child's bounded reap (#365, the owner's admitted factor 6218886743).

It never spawns a process, signals a process group, sets an environment, closes a
pipe or words an error: each consumer keeps its own spawn, sinks, caps, wording and
close handling. `security_scan` is its first consumer.
"""

from __future__ import annotations

import dataclasses
import os
import selectors
import subprocess  # nosec B404 -- it signals, waits on and reads a caller's child; it starts none
import time
from collections.abc import Callable, Mapping
from typing import IO, Literal

_READ_CHUNK_BYTES = 65_536

Outcome = Literal["exited", "deadline", "cap", "error", "unexpected"]


@dataclasses.dataclass(frozen=True)
class Drained:
    """How one drain of a direct child ended.

    `returncode` is set when the child `exited`; `stream` names the stream that
    crossed the `cap`; `error` is the read or wait failure of an `error`, and
    `exception` the failure of any other kind (`unexpected`). `selector_closed` is
    False when the drain's own selector could not be closed.
    """

    outcome: Outcome
    returncode: int | None = None
    stream: str | None = None
    error: OSError | None = None
    exception: Exception | None = None
    selector_closed: bool = True


def drain(
    process: subprocess.Popen[bytes],
    streams: Mapping[str, IO[bytes]],
    sink: Callable[[str, bytes], None],
    *,
    deadline: float,
    cap: int,
) -> Drained:
    """Read every stream until it closes, the absolute `deadline` passes, or one
    stream crosses `cap` bytes; then wait for the child's exit within the deadline.

    The sink receives each chunk read while its stream's total stays within `cap`.
    The chunk that crosses it is never delivered, and at most one byte past the cap
    is read. A spent deadline reads nothing before its first select; a batch that a
    select returns at or after the deadline is still read, and the next loop stops.
    A failure is returned, never raised, so that a consumer can reap the child and
    word the failure itself. The child is waited on within the deadline, which reaps
    it once it has exited (cubic on #437); nothing is killed or closed here, except
    the drain's own selector.
    """
    # A spent deadline reads nothing: _drain checks it before any select or read.
    selector: selectors.BaseSelector | None = None
    closed = True
    try:
        try:
            selector = selectors.DefaultSelector()
            result = _drain(process, streams, sink, selector, deadline, cap)
        except OSError as exc:
            result = Drained("error", error=exc)
        except Exception as exc:
            # Any other kind is returned too, for the consumer to word and to reap.
            result = Drained("unexpected", exception=exc)
    finally:
        if selector is not None:
            try:
                selector.close()
            except Exception:
                # A close failure of any kind is reported, never raised, so that the
                # consumer still reaps its child (Sourcery on #437).
                closed = False
    return result if closed else dataclasses.replace(result, selector_closed=False)


def _drain(
    process: subprocess.Popen[bytes],
    streams: Mapping[str, IO[bytes]],
    sink: Callable[[str, bytes], None],
    selector: selectors.BaseSelector,
    deadline: float,
    cap: int,
) -> Drained:
    delivered = dict.fromkeys(streams, 0)
    for name, stream in streams.items():
        selector.register(stream, selectors.EVENT_READ, name)
    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return Drained("deadline")
        events = selector.select(remaining)
        if not events:
            return Drained("deadline")
        stopped = _read_ready(events, selector, sink, delivered, cap)
        if stopped is not None:
            return stopped
    return _wait_for_exit(process, deadline)


def _read_ready(
    events: list[tuple[selectors.SelectorKey, int]],
    selector: selectors.BaseSelector,
    sink: Callable[[str, bytes], None],
    delivered: dict[str, int],
    cap: int,
) -> Drained | None:
    """Read each ready stream once: the drain's end, or None to select again."""
    # The deadline is checked before each select, as the scanner did on main, and not
    # again before each ready stream: a batch that select returns at or after the
    # deadline is still read, and the next loop stops (Router 6221408680 on #437).
    for key, _ in events:
        name = str(key.data)
        # At most one byte past the cap is read, so a crossing is seen at once.
        room = cap + 1 - delivered[name]
        chunk = os.read(key.fd, min(_READ_CHUNK_BYTES, max(1, room)))
        if not chunk:
            selector.unregister(key.fileobj)
            continue
        delivered[name] += len(chunk)
        if delivered[name] > cap:
            # The crossing chunk is never delivered, whole or in part: a sink keeps
            # only the chunks before it (the PAO on #436, 6220140281).
            return Drained("cap", stream=name)
        sink(name, chunk)
    return None


def _wait_for_exit(process: subprocess.Popen[bytes], deadline: float) -> Drained:
    """The child's exit, waited on within what is left of the deadline."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return Drained("deadline")
    try:
        return Drained("exited", returncode=process.wait(timeout=remaining))
    except subprocess.TimeoutExpired:
        return Drained("deadline")


def reap(process: subprocess.Popen[bytes], *, timeout: float) -> Exception | None:
    """Kill the child if it is still running, and confirm its exit within
    `timeout`. Nothing is raised, so that cleanup always reaches the bounded wait
    (Sourcery on #437). The wait's failure is returned, and None means the child
    was reaped. A poll() that fails is taken as running, so the child is killed,
    and a kill() that fails is absorbed: in both cases the bounded wait decides
    (CodeAnt and cubic on #437)."""
    try:
        running = process.poll() is None
    except Exception:
        running = True
    if running:
        try:
            process.kill()
        except Exception:  # nosec B110 -- a failed kill still reaches the bounded wait below
            pass
    try:
        process.wait(timeout=timeout)
    except Exception as exc:
        return exc
    return None
