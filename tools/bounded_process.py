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
import subprocess
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
    is read. A spent deadline reads nothing. A failure is returned, never raised, so that a consumer
    can reap the child and word the failure itself. Nothing is killed, reaped or
    closed here, except the drain's own selector.
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
            except OSError:
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
                # The crossing chunk is never delivered, whole or in part: a sink
                # keeps only the chunks before it (the PAO on #436, 6220140281).
                return Drained("cap", stream=name)
            sink(name, chunk)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return Drained("deadline")
    try:
        return Drained("exited", returncode=process.wait(timeout=remaining))
    except subprocess.TimeoutExpired:
        return Drained("deadline")


def reap(
    process: subprocess.Popen[bytes], *, timeout: float
) -> OSError | subprocess.TimeoutExpired | None:
    """Kill the child if it is still running, and confirm its exit within
    `timeout`. The failure is returned, never raised; None means it was reaped."""
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return exc
    return None
