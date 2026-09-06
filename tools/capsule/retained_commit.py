"""Same-workspace stale-writer protection at the persistence boundary.

`prepare()` reads a retained workspace once, computes for a long time -- including
running a hidden-oracle qualification -- and only then persists. Any decision it
made about retained state is therefore a decision about a snapshot, and by the time
it writes, another invocation sharing that workspace may already have persisted a
newer one.

Guarding individual refusal branches cannot fix that: the stale writer is not a
property of any one branch, it is a property of the write. So the invariant lives
here instead, stated once:

    an invocation working from an older snapshot must never overwrite state
    persisted by a newer one.

Re-reading the generation and then writing would not be enough on its own -- two
invocations could both read the same value and both proceed -- so the comparison
and the write happen inside one same-workspace commit lock, making check-and-commit
atomic against other holders of that lock. Only the commit is serialised; the
expensive preparation and qualification work outside it still runs concurrently.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Callable
from pathlib import Path

try:  # POSIX advisory locking; absent on some platforms
    import fcntl
except ImportError:  # pragma: no cover - platform dependent
    fcntl = None  # type: ignore[assignment]

GENERATION_FILENAME = ".retained-generation.json"
COMMIT_LOCK_FILENAME = ".retained-commit.lock"
GENERATION_SCHEMA = "gnostoa-retained-generation/v1"

#: Reported when a stale invocation declines to overwrite newer retained state.
CONCURRENT_STATE_CHANGED = "retained-state-changed-concurrently"


def read_generation(root: Path) -> int:
    """The retained workspace generation, or 0 when none has been recorded.

    An unreadable or malformed marker reads as 0 rather than raising: this value is
    only ever compared for equality, and a workspace that cannot report a generation
    must not be able to claim it matches one.
    """
    path = root / GENERATION_FILENAME
    try:
        observed = path.lstat()
    except OSError:
        return 0
    if not stat.S_ISREG(observed.st_mode):
        return 0
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return 0
    if not isinstance(payload, dict) or payload.get("schema") != GENERATION_SCHEMA:
        return 0
    generation = payload.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool):
        return 0
    return generation


def _write_generation(root: Path, generation: int) -> None:
    path = root / GENERATION_FILENAME
    temporary = root / f"{GENERATION_FILENAME}.partial"
    payload = {"schema": GENERATION_SCHEMA, "generation": generation}
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
    )
    try:
        os.write(descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode())
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


def commit_if_current(
    root: Path,
    *,
    expected: int,
    persist: Callable[[], None],
) -> bool:
    """Persist only while the retained generation still matches `expected`.

    Returns True when `persist` ran and the generation advanced, False when another
    invocation has persisted since `expected` was read. On False nothing is written,
    so a stale caller returns its result without destroying newer evidence.
    """
    lock_path = root / COMMIT_LOCK_FILENAME
    lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if read_generation(root) != expected:
            return False
        persist()
        _write_generation(root, expected + 1)
        return True
    finally:
        if fcntl is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:  # pragma: no cover - defensive
                pass
        os.close(lock_fd)
