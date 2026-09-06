"""Retained-workspace transactions: committed snapshot, reservation, staged commit.

`prepare()` reads a workspace once, works for a long time -- including running a
hidden-oracle qualification that cannot be repeated -- and only then persists.
Arbitrating that by arrival order is wrong, because the contenders are not
equivalent: an invocation that has crossed the irreversible effect boundary has
strictly more standing than one that has done nothing. Four facts are therefore
kept distinct.

    COMMITTED SNAPSHOT  the last complete truth of the workspace
    RESERVATION         which transaction may cross the next effect boundary
    EFFECT CLAIM        proof the irreversible boundary actually opened
    LIVE OWNER          whether the reserving process is still running

The commit record is content-bound rather than a counter, so a torn write reads as
an inconsistent workspace instead of an older valid version, and a crash between
writing state and recording it is detectable rather than an invitation to overwrite.

Two locks with different jobs. The coordination lock is held only across short
metadata transitions -- reading a coherent snapshot, reserving, publishing -- never
across the qualification effect. The owner-liveness lock is held for the life of a
transaction and grants no right to write; it answers only whether the reserving
owner is still alive, which avoids leases, heartbeats and clock comparisons.

Recovery after the effect boundary is forward-only. A claimed transaction is never
rolled back and never freshly retried; it is either finished forward from its staged
evidence or left interrupted.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

try:  # POSIX advisory locking
    import fcntl
except ImportError:  # pragma: no cover - platform dependent
    fcntl = None  # type: ignore[assignment]

COMMIT_RECORD_FILENAME = ".retained-commit.json"
COORDINATION_LOCK_FILENAME = ".retained-coordination.lock"
RESERVATION_FILENAME = ".retained-reservation.json"
STAGING_DIRECTORY = ".retained-transactions"

COMMIT_RECORD_SCHEMA = "gnostoa-retained-commit-record/v1"
RESERVATION_SCHEMA = "gnostoa-retained-reservation/v1"

STATE_FILENAME = "experiment-state.json"
LEDGER_FILENAME = "stages.json"
LOCK_FILENAME = "experiment.lock"

#: Reported when a stale invocation declines to overwrite newer retained state.
CONCURRENT_STATE_CHANGED = "retained-state-changed-concurrently"
#: Reported when another transaction holds the right to cross the effect boundary.
TRANSACTION_RESERVED = "retained-transaction-reserved"
#: Reported when retained state and its commit record disagree.
INCONSISTENT_STATE = "retained-state-inconsistent"


class RetainedTransactionError(RuntimeError):
    """Retained transaction state cannot be used safely."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _digest_file(path: Path) -> str | None:
    """Digest of a regular file, or None when absent. A non-regular path is refused."""
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot inspect {path.name}: {exc}"
        ) from exc
    if not stat.S_ISREG(observed.st_mode):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"{path.name} is not a regular file"
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_atomic(path: Path, payload: bytes) -> None:
    """Write, fsync, rename, then fsync the directory entry."""
    temporary = path.with_name(f"{path.name}.partial")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def coordination_lock(root: Path) -> Iterator[None]:
    """Serialise short retained-metadata transitions. Never held across an effect."""
    if fcntl is None:  # pragma: no cover - platform dependent
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "advisory locking is unavailable; retained transactions cannot be "
            "coordinated safely on this platform",
        )
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        root / COORDINATION_LOCK_FILENAME, os.O_WRONLY | os.O_CREAT, 0o600
    )
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:  # pragma: no cover - defensive
            pass
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class CommittedSnapshot:
    """The last complete truth of a workspace, bound to its actual contents."""

    generation: int
    transaction_id: str
    stages_sha256: str | None
    state_sha256: str | None
    lock_sha256: str | None

    @property
    def identity(self) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "generation": self.generation,
                    "transaction_id": self.transaction_id,
                    "stages_sha256": self.stages_sha256,
                    "state_sha256": self.state_sha256,
                    "lock_sha256": self.lock_sha256,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def as_json(self) -> dict[str, object]:
        return {
            "schema": COMMIT_RECORD_SCHEMA,
            "generation": self.generation,
            "transaction_id": self.transaction_id,
            "stages_sha256": self.stages_sha256,
            "state_sha256": self.state_sha256,
            "lock_sha256": self.lock_sha256,
        }


def read_committed(root: Path) -> CommittedSnapshot | None:
    """The committed snapshot, or None for a workspace that never committed.

    A malformed record, or one that disagrees with the files it names, is neither:
    it is an inconsistent workspace and is refused. Collapsing those cases onto the
    initial state is what lets a crashed commit look like a fresh workspace.
    """
    path = root / COMMIT_RECORD_FILENAME
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot inspect the commit record: {exc}"
        ) from exc
    if not stat.S_ISREG(observed.st_mode):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the commit record is not a regular file"
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the commit record is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != COMMIT_RECORD_SCHEMA:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the commit record has an unsupported schema"
        )
    generation = payload.get("generation")
    transaction_id = payload.get("transaction_id")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or not isinstance(transaction_id, str)
        or not transaction_id
    ):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the commit record is malformed"
        )

    def _recorded(name: str) -> str | None:
        value = payload.get(name)
        if value is None or isinstance(value, str):
            return value
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the commit record has a malformed {name}"
        )

    snapshot = CommittedSnapshot(
        generation=generation,
        transaction_id=transaction_id,
        stages_sha256=_recorded("stages_sha256"),
        state_sha256=_recorded("state_sha256"),
        lock_sha256=_recorded("lock_sha256"),
    )
    for name, recorded in (
        (LEDGER_FILENAME, snapshot.stages_sha256),
        (STATE_FILENAME, snapshot.state_sha256),
        (LOCK_FILENAME, snapshot.lock_sha256),
    ):
        if _digest_file(root / name) != recorded:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                f"retained {name} does not match the committed record; the workspace "
                "is mid-transaction or was modified outside it",
            )
    return snapshot


@dataclass(frozen=True, slots=True)
class Reservation:
    """The right to cross the next effect boundary. Not proof that it was crossed."""

    transaction_id: str
    base_identity: str | None
    experiment_id: str
    scope: str
    candidate_sha256: str
    authority_sha256: str

    def as_json(self) -> dict[str, object]:
        return {
            "schema": RESERVATION_SCHEMA,
            "transaction_id": self.transaction_id,
            "base_identity": self.base_identity,
            "experiment_id": self.experiment_id,
            "scope": self.scope,
            "candidate_sha256": self.candidate_sha256,
            "authority_sha256": self.authority_sha256,
        }


def read_reservation(root: Path) -> Reservation | None:
    path = root / RESERVATION_FILENAME
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    if not stat.S_ISREG(observed.st_mode):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the reservation is not a regular file"
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the reservation is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != RESERVATION_SCHEMA:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the reservation has an unsupported schema"
        )
    try:
        return Reservation(
            transaction_id=str(payload["transaction_id"]),
            base_identity=(
                str(payload["base_identity"])
                if payload.get("base_identity") is not None
                else None
            ),
            experiment_id=str(payload["experiment_id"]),
            scope=str(payload["scope"]),
            candidate_sha256=str(payload["candidate_sha256"]),
            authority_sha256=str(payload["authority_sha256"]),
        )
    except KeyError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the reservation is missing {exc}"
        ) from exc


def owner_lock_path(root: Path, transaction_id: str) -> Path:
    return root / STAGING_DIRECTORY / transaction_id / "owner.lock"


def new_transaction_id() -> str:
    return uuid.uuid4().hex


def staging_directory(root: Path, transaction_id: str) -> Path:
    return root / STAGING_DIRECTORY / transaction_id


def write_reservation(root: Path, reservation: Reservation) -> None:
    """Durably record the reservation. Caller holds the coordination lock."""
    root.mkdir(parents=True, exist_ok=True)
    _write_atomic(
        root / RESERVATION_FILENAME,
        (json.dumps(reservation.as_json(), indent=2, sort_keys=True) + "\n").encode(),
    )


def clear_reservation(root: Path) -> None:
    """Caller holds the coordination lock."""
    try:
        (root / RESERVATION_FILENAME).unlink()
    except FileNotFoundError:
        pass


@contextmanager
def owner_liveness(root: Path, transaction_id: str) -> Iterator[None]:
    """Held for the life of a transaction. Confers no right to write."""
    if fcntl is None:  # pragma: no cover - platform dependent
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "advisory locking is unavailable"
        )
    path = owner_lock_path(root, transaction_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:  # pragma: no cover - defensive
            pass
        os.close(descriptor)


def owner_is_live(root: Path, reservation: Reservation) -> bool:
    """True while the reserving process still holds its liveness lock.

    Probed by trying to take the lock without blocking: success means nobody holds
    it, so the owner is gone. No lease, no heartbeat, no clock.
    """
    if fcntl is None:  # pragma: no cover - platform dependent
        return True
    path = owner_lock_path(root, reservation.transaction_id)
    if not path.is_file():
        return False
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    else:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def wait_for_owner(root: Path, reservation: Reservation) -> None:
    """Block until the reserving transaction has finished, then return."""
    if fcntl is None:  # pragma: no cover - platform dependent
        return
    path = owner_lock_path(root, reservation.transaction_id)
    if not path.is_file():
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def publish(
    root: Path,
    *,
    transaction_id: str,
    generation: int,
    staged: dict[str, bytes],
) -> CommittedSnapshot:
    """Publish staged files forward, then record the commit. Coordination lock held.

    The commit record is written last, so a crash mid-publication leaves a workspace
    whose contents disagree with its record -- detectably inconsistent, rather than
    an older version an outdated writer may overwrite.
    """
    for name, payload in staged.items():
        _write_atomic(root / name, payload)
    snapshot = CommittedSnapshot(
        generation=generation,
        transaction_id=transaction_id,
        stages_sha256=_digest_file(root / LEDGER_FILENAME),
        state_sha256=_digest_file(root / STATE_FILENAME),
        lock_sha256=_digest_file(root / LOCK_FILENAME),
    )
    _write_atomic(
        root / COMMIT_RECORD_FILENAME,
        (json.dumps(snapshot.as_json(), indent=2, sort_keys=True) + "\n").encode(),
    )
    return snapshot
