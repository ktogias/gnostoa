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
metadata transitions -- reading a coherent snapshot, arbitrating, publishing --
never across the qualification effect. The owner-liveness lock is held for the life
of a transaction and grants no right to write; it answers only whether the reserving
owner is still alive, which avoids leases, heartbeats and clock comparisons. Holding
it is not ownership: ownership begins only when a reservation is installed.

`arbitrate` is the single decision point. Reading the committed state, inspecting
the reservation, judging liveness, recovering an abandoned transaction and taking
the reservation all happen inside one coordination critical section, because every
split between observing and acting on that observation is a window in which the
observation expires.

Recovery after the effect boundary is forward-only. A claimed transaction is never
rolled back and never freshly retried; it is either finished forward from its
durable staged output or reported interrupted. Absence of recoverable evidence is
never converted into permission to run the effect again.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

try:  # POSIX advisory locking
    import fcntl
except ImportError:  # pragma: no cover - platform dependent
    fcntl = None  # type: ignore[assignment]

COMMIT_RECORD_FILENAME = ".retained-commit.json"
COORDINATION_LOCK_FILENAME = ".retained-coordination.lock"
RESERVATION_FILENAME = ".retained-reservation.json"
STAGING_DIRECTORY = ".retained-transactions"
MANIFEST_FILENAME = "manifest.json"
OWNER_LOCK_FILENAME = "owner.lock"
PUBLICATION_FILENAME = ".retained-publication.json"

COMMIT_RECORD_SCHEMA = "gnostoa-retained-commit-record/v1"
RESERVATION_SCHEMA = "gnostoa-retained-reservation/v1"
MANIFEST_SCHEMA = "gnostoa-retained-transaction-manifest/v1"
PUBLICATION_SCHEMA = "gnostoa-retained-publication-intent/v1"

#: A transaction identifier addresses a directory inside the workspace, and it is
#: read back from records anyone may have written. It is accepted only in exactly
#: the form new_transaction_id emits, so it can never be a path.
_TRANSACTION_ID = re.compile(r"^[0-9a-f]{32}$")

STATE_FILENAME = "experiment-state.json"
LEDGER_FILENAME = "stages.json"
LOCK_FILENAME = "experiment.lock"

#: Written into the canonical public state by every transactional commit. Its
#: presence is what distinguishes "this workspace never had a commit record" from
#: "this workspace had one and it is gone".
TRANSACTION_MARKER_FIELD = "retained_transaction"
TRANSACTION_MARKER_VALUE = "gnostoa-retained-transaction/v1"

#: The public status that asserts a lock was emitted and bound.
READY_STATUS = "READY_FOR_OWNER_REVIEW"

#: Stage receipts whose recorded output binds the emitted experiment lock.
_LOCK_BINDING_STAGES = ("EXECUTION_FROZEN", "READY_FOR_OWNER_REVIEW")

#: Reported when a stale invocation declines to overwrite newer retained state.
CONCURRENT_STATE_CHANGED = "retained-state-changed-concurrently"
#: Reported when another transaction holds the right to cross the effect boundary.
TRANSACTION_RESERVED = "retained-transaction-reserved"
#: Reported when retained state and its commit record disagree.
INCONSISTENT_STATE = "retained-state-inconsistent"
#: What the caller must do next. `arbitrate` performs everything that has to be
#: atomic itself; these say what is left.
TAKE = "TAKE"
WAIT = "WAIT"
REFUSE = "REFUSE"
RECONCILE = "RECONCILE"


class RetainedTransactionError(RuntimeError):
    """Retained transaction state cannot be used safely."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@contextmanager
def _open_directory(path: Path) -> Iterator[int]:
    """Open the anchor directory this module was handed, refusing a non-directory.

    Only the workspace root is opened this way: it is the one path the module is
    given rather than derives. Everything beneath it is reached with
    _open_child_directory, relative to a descriptor that is already trusted.
    """
    try:
        descriptor = os.open(path, os.O_RDONLY | _O_DIRECTORY)
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot open {path.name or path} as a directory: {exc}"
        ) from exc
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):  # pragma: no cover
            raise RetainedTransactionError(
                INCONSISTENT_STATE, f"{path.name} is not a directory"
            )
        yield descriptor
    finally:
        os.close(descriptor)


def _write_at(directory_fd: int, name: str, payload: bytes) -> None:
    """Write one file durably inside an open directory.

    The temporary is created exclusively under a name nobody can predict, because a
    deterministic one can be pre-created as a hardlink to any file on the same
    filesystem and O_NOFOLLOW does not protect against that. The write loops until
    the payload is exhausted: a short write is a successful call that wrote less
    than it was given, and accepting it publishes a truncated file as a finished one.
    """
    temporary = f".{name}.{uuid.uuid4().hex}.partial"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
        0o600,
        dir_fd=directory_fd,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:  # pragma: no cover - defensive
                raise RetainedTransactionError(
                    INCONSISTENT_STATE, f"writing {name} made no progress"
                )
            view = view[written:]
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        os.unlink(temporary, dir_fd=directory_fd)
        raise
    os.close(descriptor)
    os.rename(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    os.fsync(directory_fd)


def _write_atomic(path: Path, payload: bytes) -> None:
    """Write, fsync, rename, then fsync the directory entry, all descriptor-bound."""
    with _open_directory(path.parent) as directory_fd:
        _write_at(directory_fd, path.name, payload)


def _read_at(directory_fd: int, name: str) -> bytes | None:
    """Read a regular file inside an open directory, or None if it is not there."""
    try:
        descriptor = os.open(name, os.O_RDONLY | _O_NOFOLLOW, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot open {name}: {exc}"
        ) from exc
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RetainedTransactionError(
                INCONSISTENT_STATE, f"{name} is not a regular file"
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _digest_at(directory_fd: int, name: str) -> str | None:
    payload = _read_at(directory_fd, name)
    return None if payload is None else _digest_bytes(payload)


def _stat_at(directory_fd: int, name: str) -> os.stat_result | None:
    """lstat a name inside an open directory. Absent is None; unknown is refused."""
    try:
        return os.lstat(name, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot inspect {name}: {exc}"
        ) from exc


def _open_child_directory(parent_fd: int, name: str, *, create: bool) -> int | None:
    """Open a subdirectory relative to an already-trusted directory descriptor.

    Resolving a whole pathname re-walks every component, and O_NOFOLLOW guards only
    the last one: an intermediate directory can be renamed away and replaced by a
    symlink, after which a final component that is a real directory in somebody
    else's tree passes every check. Opening each component relative to the
    descriptor above it walks the namespace once and never revisits it.
    """
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            pass
        except OSError as exc:
            raise RetainedTransactionError(
                INCONSISTENT_STATE, f"cannot create {name}: {exc}"
            ) from exc
        else:
            # The new entry must reach the disk before anything durable is written
            # inside it, or "durable staging" is only true of its contents.
            os.fsync(parent_fd)
    try:
        descriptor = os.open(
            name, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW, dir_fd=parent_fd
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"{name} is not a directory this workspace owns: {exc}"
        ) from exc
    if not stat.S_ISDIR(os.fstat(descriptor).st_mode):  # pragma: no cover - defensive
        os.close(descriptor)
        raise RetainedTransactionError(INCONSISTENT_STATE, f"{name} is not a directory")
    return descriptor


@contextmanager
def _transaction_directory(
    root: Path, transaction_id: str, *, create: bool
) -> Iterator[tuple[int, int] | None]:
    """Yield (staging descriptor, transaction descriptor), or None when absent."""
    name = _validated_transaction_id(transaction_id)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    with _open_directory(root) as root_fd:
        staging_fd = _open_child_directory(root_fd, STAGING_DIRECTORY, create=create)
        if staging_fd is None:
            yield None
            return
        try:
            transaction_fd = _open_child_directory(staging_fd, name, create=create)
            if transaction_fd is None:
                yield None
                return
            try:
                yield staging_fd, transaction_fd
            finally:
                os.close(transaction_fd)
        finally:
            os.close(staging_fd)


def _read_file(path: Path) -> bytes | None:
    with _open_directory(path.parent) as directory_fd:
        return _read_at(directory_fd, path.name)


def _digest_file(path: Path) -> str | None:
    """Digest of a regular file, or None when absent. A non-regular path is refused."""
    payload = _read_file(path)
    return None if payload is None else _digest_bytes(payload)


def _unlink_file(path: Path) -> bool:
    with _open_directory(path.parent) as directory_fd:
        try:
            os.unlink(path.name, dir_fd=directory_fd)
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise RetainedTransactionError(
                INCONSISTENT_STATE, f"cannot remove {path.name}: {exc}"
            ) from exc
        os.fsync(directory_fd)
        return True


def _fsync_directory(path: Path) -> None:
    with _open_directory(path) as descriptor:
        os.fsync(descriptor)


def _open_lock_file_at(directory_fd: int, name: str) -> int:
    """Open a lock file refusing symlinks and anything that is not a regular file.

    A lock whose path can be redirected is not a lock: it would serialise callers
    against a file of somebody else's choosing, or against nothing at all.
    """
    try:
        descriptor = os.open(
            name, os.O_WRONLY | os.O_CREAT | _O_NOFOLLOW, 0o600, dir_fd=directory_fd
        )
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot open {name} as a lock: {exc}"
        ) from exc
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise RetainedTransactionError(
                INCONSISTENT_STATE, f"{name} is not a regular file"
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _require_locking(purpose: str) -> None:
    if fcntl is None:  # pragma: no cover - platform dependent
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            f"advisory locking is unavailable; {purpose} cannot be performed safely "
            "on this platform",
        )


@contextmanager
def coordination_lock(root: Path) -> Iterator[None]:
    """Serialise short retained-metadata transitions. Never held across an effect."""
    _require_locking("retained transaction coordination")
    root.mkdir(parents=True, exist_ok=True)
    with _open_directory(root) as root_fd:
        descriptor = _open_lock_file_at(root_fd, COORDINATION_LOCK_FILENAME)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:  # pragma: no cover - defensive
                pass
            os.close(descriptor)


def _validated_transaction_id(transaction_id: str) -> str:
    """A transaction identifier, or a refusal. Never a path.

    This value is used to address a directory and is read back from retained
    records, so it is checked against the exact form it is generated in. Anything
    else -- an absolute path, a traversal, a name with a separator -- would let a
    record decide which directory the workspace writes to and deletes from.
    """
    if not isinstance(transaction_id, str) or not _TRANSACTION_ID.match(transaction_id):
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            f"{transaction_id!r} is not a transaction identifier",
        )
    return transaction_id


def staging_directory(root: Path, transaction_id: str) -> Path:
    """Where a transaction stages its output. The identifier is validated first."""
    return root / STAGING_DIRECTORY / _validated_transaction_id(transaction_id)


def owner_lock_path(root: Path, transaction_id: str) -> Path:
    return staging_directory(root, transaction_id) / OWNER_LOCK_FILENAME


def new_transaction_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def owner_liveness(root: Path, transaction_id: str) -> Iterator[None]:
    """Held for the life of a transaction. Confers no right to write."""
    _require_locking("transaction liveness")
    with _transaction_directory(root, transaction_id, create=True) as opened:
        assert opened is not None  # create=True never yields None
        _, transaction_fd = opened
        descriptor = _open_lock_file_at(transaction_fd, OWNER_LOCK_FILENAME)
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
    _require_locking("transaction liveness")
    with _transaction_directory(
        root, reservation.transaction_id, create=False
    ) as opened:
        if opened is None:
            return False
        _, transaction_fd = opened
        if _stat_at(transaction_fd, OWNER_LOCK_FILENAME) is None:
            return False
        descriptor = _open_lock_file_at(transaction_fd, OWNER_LOCK_FILENAME)
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
    _require_locking("transaction liveness")
    with _transaction_directory(
        root, reservation.transaction_id, create=False
    ) as opened:
        if opened is None:
            return
        _, transaction_fd = opened
        if _stat_at(transaction_fd, OWNER_LOCK_FILENAME) is None:
            return
        descriptor = _open_lock_file_at(transaction_fd, OWNER_LOCK_FILENAME)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _required_str(payload: Mapping[str, Any], field: str, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"{label} field {field!r} is missing or not a string"
        )
    return value


def _required_digest(payload: Mapping[str, Any], field: str, label: str) -> str:
    value = _required_str(payload, field, label)
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"{label} field {field!r} is not a sha256 digest"
        )
    return value


def _optional_digest(payload: Mapping[str, Any], field: str, label: str) -> str | None:
    if payload.get(field) is None:
        return None
    return _required_digest(payload, field, label)


def _present(path: Path) -> bool:
    """Whether the path exists, refusing to read a failed stat as absence.

    ``Path.exists`` answers False for a path it merely cannot inspect. Treating that
    as "nothing is here" is how an unreadable reservation becomes "nobody holds the
    effect boundary".
    """
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot inspect {path.name}: {exc}"
        ) from exc
    return True


def _load_json_document(path: Path, *, label: str, schema: str) -> dict[str, Any]:
    try:
        observed = path.lstat()
    except OSError as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"cannot inspect the {label}: {exc}"
        ) from exc
    if not stat.S_ISREG(observed.st_mode):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the {label} is not a regular file"
        )
    raw = _read_file(path)
    if raw is None:  # pragma: no cover - raced with a removal
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the {label} disappeared while it was being read"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the {label} is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != schema:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the {label} has an unsupported schema"
        )
    return payload


@dataclass(frozen=True, slots=True)
class CommittedSnapshot:
    """The last complete truth of a workspace, bound to its actual contents.

    ``lock_file_sha256`` digests the persisted bytes; ``lock_identity`` is the
    canonical experiment-lock identity those bytes carry. They are different facts
    and are never recorded under one name.
    """

    generation: int
    transaction_id: str
    stages_sha256: str | None
    state_sha256: str | None
    lock_file_sha256: str | None
    lock_identity: str | None

    @property
    def identity(self) -> str:
        return _digest_bytes(json.dumps(self.as_json(), sort_keys=True).encode())

    def as_json(self) -> dict[str, object]:
        return {
            "schema": COMMIT_RECORD_SCHEMA,
            "generation": self.generation,
            "transaction_id": self.transaction_id,
            "stages_sha256": self.stages_sha256,
            "state_sha256": self.state_sha256,
            "lock_file_sha256": self.lock_file_sha256,
            "lock_identity": self.lock_identity,
        }


def state_is_transactional(root: Path) -> bool:
    """Whether the canonical public state says it was written under a transaction.

    Only a genuinely absent state file answers False. A state that cannot be read is
    not evidence of a workspace predating the transaction model, and reading it that
    way would let a damaged workspace with no commit record pass as legacy.
    """
    path = root / STATE_FILENAME
    raw = _read_file(path)
    if raw is None:
        return False
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the retained public state is unreadable: {exc}"
        ) from exc
    return (
        isinstance(payload, dict)
        and payload.get(TRANSACTION_MARKER_FIELD) == TRANSACTION_MARKER_VALUE
    )


def _parse_commit_record(payload: Mapping[str, Any]) -> CommittedSnapshot:
    """The one structural reading of a commit record.

    Recovery and the canonical read share it deliberately. A record that parses but
    is not structurally a commit record must not become a different valid snapshot:
    recovery compares staged output against the snapshot identity, so "different" is
    what it treats as superseded, and one malformed field would quietly authorise
    discarding evidence. Absent, valid and invalid stay three answers.
    """
    generation = payload.get("generation")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
    ):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the commit record generation is malformed"
        )
    return CommittedSnapshot(
        generation=generation,
        transaction_id=_validated_transaction_id(
            _required_str(payload, "transaction_id", "commit record")
        ),
        stages_sha256=_optional_digest(payload, "stages_sha256", "commit record"),
        state_sha256=_optional_digest(payload, "state_sha256", "commit record"),
        lock_file_sha256=_optional_digest(payload, "lock_file_sha256", "commit record"),
        lock_identity=_optional_digest(payload, "lock_identity", "commit record"),
    )


def read_committed(root: Path) -> CommittedSnapshot | None:
    """The committed snapshot, or None for a workspace that never committed.

    A malformed record, one that disagrees with the files it names, or a missing one
    for a workspace whose own state says it committed transactionally, is none of
    those: it is an inconsistent workspace and is refused. Collapsing those cases
    onto the initial state is what lets damaged evidence be rewritten as if empty.
    """
    path = root / COMMIT_RECORD_FILENAME
    if not _present(path):
        if state_is_transactional(root):
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                "the retained state was written under a transaction but its commit "
                "record is missing; the workspace cannot vouch for itself",
            )
        return None
    snapshot = _parse_commit_record(
        _load_json_document(path, label="commit record", schema=COMMIT_RECORD_SCHEMA)
    )
    for name, recorded in (
        (LEDGER_FILENAME, snapshot.stages_sha256),
        (STATE_FILENAME, snapshot.state_sha256),
        (LOCK_FILENAME, snapshot.lock_file_sha256),
    ):
        if _digest_file(root / name) != recorded:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                f"retained {name} does not match the committed record; the workspace "
                "is mid-transaction or was modified outside it",
            )
    _validate_committed_lock_identity(root, snapshot)
    return snapshot


def _validate_committed_lock_identity(root: Path, snapshot: CommittedSnapshot) -> None:
    """Every retained reference to the lock must name the identity the lock carries.

    Digesting the lock file proves the bytes are the ones that were committed. It
    says nothing about the identity recorded beside them, which can be rewritten on
    its own: the record would then bind a lock the workspace does not contain, and
    every downstream check that trusts the record would follow it. Agreement is
    therefore re-established on every read, not inherited from the write.

    For a state that claims readiness the chain is required rather than checked
    where it happens to be present. Readiness is exactly the claim that a lock was
    emitted and bound, so a missing link is not one fewer thing to verify -- it is
    the claim failing. A blocked state carries no such claim, and a lock published by
    an earlier transaction may legitimately still sit beside it.
    """
    carried = _published_lock_identity(root)
    if carried != snapshot.lock_identity:
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            f"the commit record names lock identity {snapshot.lock_identity!r}, "
            f"which the published lock does not carry",
        )

    state: object = None
    raw_state = _read_file(root / STATE_FILENAME)
    if raw_state is not None:
        try:
            state = json.loads(raw_state)
        except (UnicodeDecodeError, json.JSONDecodeError):
            state = None
    references: dict[str, str | None] = {
        "the retained public state": (
            state.get("lock_sha256") if isinstance(state, dict) else None
        )
    }
    payload = _read_file(root / LEDGER_FILENAME) or b""
    for stage in _LOCK_BINDING_STAGES:
        references[f"the retained {stage} receipt"] = _binding_output(payload, stage)

    claims_ready = isinstance(state, dict) and state.get("status") == READY_STATUS
    if claims_ready and snapshot.lock_identity is None:
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "the retained state claims readiness but no experiment lock is committed",
        )
    for label, referenced in references.items():
        if referenced is None:
            if claims_ready:
                raise RetainedTransactionError(
                    INCONSISTENT_STATE,
                    f"the retained state claims readiness but {label} names no lock",
                )
            continue
        if referenced != snapshot.lock_identity:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                f"{label} names lock {referenced!r}, not the committed lock "
                f"{snapshot.lock_identity!r}",
            )


def _recorded_snapshot(root: Path) -> CommittedSnapshot | None:
    """What the commit record says, without requiring it to still be true.

    Recovery acts on a workspace whose record is already known to disagree with its
    contents -- that disagreement is what it exists to resolve -- so it reads the
    record as a statement of which transaction last committed, not as a verified
    description of the files. It is read with the same structural parser as the
    canonical path: only the agreement with the files is relaxed, never the shape.
    """
    raw = _read_file(root / COMMIT_RECORD_FILENAME)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the commit record is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema") != COMMIT_RECORD_SCHEMA:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the commit record has an unsupported schema"
        )
    return _parse_commit_record(payload)


@dataclass(frozen=True, slots=True)
class Reservation:
    """The right to cross the next effect boundary. Not proof that it was crossed."""

    transaction_id: str
    base_identity: str | None
    experiment_id: str
    scope: str
    candidate_sha256: str
    authority_sha256: str
    #: Digest of the manifest of this transaction's staged output, recorded once
    #: that output is complete. It is the only commitment to those bytes that lives
    #: outside the staging directory, and until it exists nothing vouches for what
    #: is staged there.
    staged_manifest_sha256: str | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "schema": RESERVATION_SCHEMA,
            "transaction_id": self.transaction_id,
            "base_identity": self.base_identity,
            "experiment_id": self.experiment_id,
            "scope": self.scope,
            "candidate_sha256": self.candidate_sha256,
            "authority_sha256": self.authority_sha256,
            "staged_manifest_sha256": self.staged_manifest_sha256,
        }

    def is_same_request_as(
        self,
        *,
        experiment_id: str,
        scope: str,
        candidate_sha256: str,
        authority_sha256: str | None,
    ) -> bool:
        return (
            authority_sha256 is not None
            and self.experiment_id == experiment_id
            and self.scope == scope
            and self.candidate_sha256 == candidate_sha256
            and self.authority_sha256 == authority_sha256
        )


def read_reservation(root: Path) -> Reservation | None:
    """The installed reservation, or None when there is none.

    Only a genuinely absent file is absence. Any other failure to read it is refused:
    treating an unreadable reservation as "nobody is reserving" hands the effect
    boundary to whoever asked at the wrong moment.
    """
    path = root / RESERVATION_FILENAME
    if not _present(path):
        return None
    payload = _load_json_document(path, label="reservation", schema=RESERVATION_SCHEMA)
    base_identity = payload.get("base_identity")
    if base_identity is not None:
        base_identity = _required_digest(payload, "base_identity", "reservation")
    return Reservation(
        transaction_id=_validated_transaction_id(
            _required_str(payload, "transaction_id", "reservation")
        ),
        base_identity=base_identity,
        experiment_id=_required_str(payload, "experiment_id", "reservation"),
        scope=_required_str(payload, "scope", "reservation"),
        candidate_sha256=_required_digest(payload, "candidate_sha256", "reservation"),
        authority_sha256=_required_digest(payload, "authority_sha256", "reservation"),
        staged_manifest_sha256=(
            None
            if payload.get("staged_manifest_sha256") is None
            else _required_digest(payload, "staged_manifest_sha256", "reservation")
        ),
    )


def write_reservation(root: Path, reservation: Reservation) -> None:
    """Durably record the reservation. Caller holds the coordination lock."""
    root.mkdir(parents=True, exist_ok=True)
    _write_atomic(
        root / RESERVATION_FILENAME,
        (json.dumps(reservation.as_json(), indent=2, sort_keys=True) + "\n").encode(),
    )


def seal_reservation(
    root: Path, *, expected_transaction_id: str, manifest_sha256: str
) -> None:
    """Commit the reservation to the staged output. Caller holds the coordination lock.

    Until this lands, the staging directory vouches only for itself: a member can be
    rewritten and the manifest updated to match, leaving the transaction, base,
    candidate and authority untouched, and recovery would finish the substitution
    forward. The seal is the commitment that lives outside the tree it describes.
    """
    existing = read_reservation(root)
    if existing is None or existing.transaction_id != expected_transaction_id:
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "the installed reservation is not this transaction's; refusing to seal "
            "staged output onto a reservation it does not own",
        )
    write_reservation(root, replace(existing, staged_manifest_sha256=manifest_sha256))


def clear_reservation(root: Path, *, expected_transaction_id: str) -> None:
    """Remove our own reservation. Caller holds the coordination lock.

    Owner-bound, never a blind unlink: removing a reservation installed by another
    transaction would silently hand away a right that transaction still holds.
    """
    existing = read_reservation(root)
    if existing is None:
        return
    if existing.transaction_id != expected_transaction_id:
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "the installed reservation belongs to another transaction; refusing to "
            "clear a reservation this transaction does not own",
        )
    _unlink_file(root / RESERVATION_FILENAME)


@dataclass(frozen=True, slots=True)
class StagedTransaction:
    """A transaction's complete output, durable before any of it becomes canonical."""

    transaction_id: str
    base_identity: str | None
    candidate_sha256: str | None
    authority_sha256: str | None
    stages_file_sha256: str
    state_file_sha256: str
    lock_file_sha256: str | None
    lock_identity: str | None
    #: Digest of this manifest as persisted. Not part of the manifest itself.
    manifest_sha256: str = ""

    def as_json(self) -> dict[str, object]:
        return {
            "schema": MANIFEST_SCHEMA,
            "transaction_id": self.transaction_id,
            "base_identity": self.base_identity,
            "candidate_sha256": self.candidate_sha256,
            "authority_sha256": self.authority_sha256,
            "stages_file_sha256": self.stages_file_sha256,
            "state_file_sha256": self.state_file_sha256,
            "lock_file_sha256": self.lock_file_sha256,
            "lock_identity": self.lock_identity,
        }

    def members(self) -> dict[str, str]:
        """Canonical filename to expected digest, for every member of this commit."""
        members = {
            LEDGER_FILENAME: self.stages_file_sha256,
            STATE_FILENAME: self.state_file_sha256,
        }
        if self.lock_file_sha256 is not None:
            members[LOCK_FILENAME] = self.lock_file_sha256
        return members


def _binding_output(ledger_payload: bytes, stage: str) -> str | None:
    try:
        document = json.loads(ledger_payload)
        record = document["records"][stage]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError):
        return None
    outputs = record.get("outputs")
    if not isinstance(outputs, dict):
        return None
    bound = outputs.get("lock_sha256")
    return bound if isinstance(bound, str) else None


def _validate_lock_bindings(
    *, ledger: bytes, state: bytes, lock: bytes, lock_identity: str
) -> None:
    """Every recorded reference to the lock must name the same canonical identity.

    The persisted bytes and the identity they carry are separate facts, so agreement
    between them is checked rather than assumed from having written both.
    """
    try:
        carried = json.loads(lock).get("lock_sha256")
        declared = json.loads(state).get("lock_sha256")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"staged transaction output is unreadable: {exc}"
        ) from exc
    references = {
        "the staged lock": carried,
        "the staged public state": declared,
    }
    for stage in _LOCK_BINDING_STAGES:
        references[f"the {stage} receipt"] = _binding_output(ledger, stage)
    for label, referenced in references.items():
        if referenced != lock_identity:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                f"{label} names lock {referenced!r}, not the staged lock "
                f"{lock_identity!r}; a transaction must publish one lock, not two",
            )


def stage(
    root: Path,
    *,
    transaction_id: str,
    base_identity: str | None,
    candidate_sha256: str | None,
    authority_sha256: str | None,
    ledger: bytes,
    state: bytes,
    lock: bytes | None,
    lock_identity: str | None,
) -> StagedTransaction:
    """Write a transaction's whole output durably, manifest last.

    Nothing here is canonical yet. Until the manifest lands the staging directory is
    incomplete and is never a recovery source; once it lands, every byte the commit
    needs is on disk and the commit can be finished forward by anyone.
    """
    if (lock is None) != (lock_identity is None):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "a staged lock must be accompanied by its identity"
        )
    if lock is not None and lock_identity is not None:
        _validate_lock_bindings(
            ledger=ledger, state=state, lock=lock, lock_identity=lock_identity
        )
    staged = StagedTransaction(
        transaction_id=transaction_id,
        base_identity=base_identity,
        candidate_sha256=candidate_sha256,
        authority_sha256=authority_sha256,
        stages_file_sha256=_digest_bytes(ledger),
        state_file_sha256=_digest_bytes(state),
        lock_file_sha256=None if lock is None else _digest_bytes(lock),
        lock_identity=lock_identity,
    )
    manifest = (json.dumps(staged.as_json(), indent=2, sort_keys=True) + "\n").encode()
    with _transaction_directory(root, transaction_id, create=True) as opened:
        assert opened is not None  # create=True never yields None
        _, transaction_fd = opened
        _write_at(transaction_fd, LEDGER_FILENAME, ledger)
        _write_at(transaction_fd, STATE_FILENAME, state)
        if lock is not None:
            _write_at(transaction_fd, LOCK_FILENAME, lock)
        # Written last: until it lands the staging directory is incomplete, and it
        # is never a recovery source.
        _write_at(transaction_fd, MANIFEST_FILENAME, manifest)
    return replace(staged, manifest_sha256=_digest_bytes(manifest))


def read_staged(root: Path, transaction_id: str) -> StagedTransaction | None:
    """A complete, self-consistent staged transaction, or None.

    None means "not a recovery source": there is nothing complete here. It never
    means "safe to start again" -- that judgement belongs to whoever knows whether
    the effect boundary was crossed -- and it never stands in for a workspace that
    could not be inspected. An unreadable manifest or member is refused rather than
    reported as incomplete, because recovery deletes what it decides is incomplete.
    """
    with _transaction_directory(root, transaction_id, create=False) as opened:
        if opened is None:
            return None
        _, transaction_fd = opened
        return _staged_from(transaction_fd, transaction_id)


def _staged_from(transaction_fd: int, transaction_id: str) -> StagedTransaction | None:
    raw = _read_at(transaction_fd, MANIFEST_FILENAME)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != MANIFEST_SCHEMA:
        return None
    try:
        staged = StagedTransaction(
            transaction_id=_validated_transaction_id(
                _required_str(payload, "transaction_id", "manifest")
            ),
            base_identity=(
                None
                if payload.get("base_identity") is None
                else _required_digest(payload, "base_identity", "manifest")
            ),
            candidate_sha256=(
                None
                if payload.get("candidate_sha256") is None
                else _required_digest(payload, "candidate_sha256", "manifest")
            ),
            authority_sha256=(
                None
                if payload.get("authority_sha256") is None
                else _required_digest(payload, "authority_sha256", "manifest")
            ),
            stages_file_sha256=_required_digest(
                payload, "stages_file_sha256", "manifest"
            ),
            state_file_sha256=_required_digest(
                payload, "state_file_sha256", "manifest"
            ),
            lock_file_sha256=(
                None
                if payload.get("lock_file_sha256") is None
                else _required_digest(payload, "lock_file_sha256", "manifest")
            ),
            lock_identity=(
                None
                if payload.get("lock_identity") is None
                else _required_digest(payload, "lock_identity", "manifest")
            ),
        )
    except RetainedTransactionError:
        return None
    staged = replace(staged, manifest_sha256=_digest_bytes(raw))
    if staged.transaction_id != transaction_id:
        return None
    if (staged.lock_file_sha256 is None) != (staged.lock_identity is None):
        return None
    for name, expected in staged.members().items():
        # _digest_at refuses a member it cannot inspect and reports an absent one as
        # None; only the latter makes this staging incomplete.
        if _digest_at(transaction_fd, name) != expected:
            return None
    return staged


def discard_staging(root: Path, transaction_id: str) -> None:
    """Remove a staging directory whose transaction is finished with."""
    with _transaction_directory(root, transaction_id, create=False) as opened:
        if opened is None:
            return
        staging_fd, transaction_fd = opened
        for name in sorted(os.listdir(transaction_fd)):
            observed = _stat_at(transaction_fd, name)
            if observed is not None and stat.S_ISREG(observed.st_mode):
                os.unlink(name, dir_fd=transaction_fd)
        os.fsync(transaction_fd)
        emptied = os.fstat(transaction_fd)
        name = _validated_transaction_id(transaction_id)
        current = _stat_at(staging_fd, name)
        if (
            current is None
            or current.st_ino != emptied.st_ino
            or current.st_dev != emptied.st_dev
        ):
            # The name no longer refers to the directory that was just emptied.
            # Removing whatever it points at now would delete somebody else's.
            return
        try:
            os.rmdir(name, dir_fd=staging_fd)
        except OSError:  # pragma: no cover - non-empty, left as evidence
            return
        os.fsync(staging_fd)


def _staged_manifest_digest(root: Path, transaction_id: str) -> str | None:
    """Digest of a transaction's persisted manifest, or None when there is none."""
    with _transaction_directory(root, transaction_id, create=False) as opened:
        if opened is None:
            return None
        _, transaction_fd = opened
        return _digest_at(transaction_fd, MANIFEST_FILENAME)


@dataclass(frozen=True, slots=True)
class PublicationIntent:
    """Which staged transaction is being made canonical, and from exactly which bytes."""

    transaction_id: str
    manifest_sha256: str

    def as_json(self) -> dict[str, object]:
        return {
            "schema": PUBLICATION_SCHEMA,
            "transaction_id": self.transaction_id,
            "manifest_sha256": self.manifest_sha256,
        }


def read_publication_intent(root: Path) -> PublicationIntent | None:
    """Which staged transaction is being made canonical, if any.

    An effect reservation says who may cross the effect boundary. It is not a record
    of who is publishing: an invocation with no authority never reserves and still
    writes canonical files. Discovering an interrupted commit through the
    reservation would therefore strand every torn publication a non-reserving caller
    left behind, with its complete staged output sitting next to it unreachable.
    """
    path = root / PUBLICATION_FILENAME
    if not _present(path):
        return None
    payload = _load_json_document(
        path, label="publication intent", schema=PUBLICATION_SCHEMA
    )
    return PublicationIntent(
        transaction_id=_validated_transaction_id(
            _required_str(payload, "transaction_id", "publication intent")
        ),
        manifest_sha256=_required_digest(
            payload, "manifest_sha256", "publication intent"
        ),
    )


def _write_publication_intent(root: Path, intent: PublicationIntent) -> None:
    _write_atomic(
        root / PUBLICATION_FILENAME,
        (json.dumps(intent.as_json(), indent=2, sort_keys=True) + "\n").encode(),
    )


def clear_publication_intent(root: Path) -> None:
    _unlink_file(root / PUBLICATION_FILENAME)


def _published_lock_identity(root: Path) -> str | None:
    """The canonical identity carried by the published lock, if one is published."""
    raw = _read_file(root / LOCK_FILENAME)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RetainedTransactionError(
            INCONSISTENT_STATE, f"the published experiment lock is unreadable: {exc}"
        ) from exc
    carried = payload.get("lock_sha256") if isinstance(payload, dict) else None
    if not isinstance(carried, str):
        raise RetainedTransactionError(
            INCONSISTENT_STATE, "the published experiment lock carries no identity"
        )
    return carried


def publish(
    root: Path, *, staged: StagedTransaction, generation: int
) -> CommittedSnapshot:
    """Make a staged transaction canonical, then record it. Coordination lock held.

    The record describes the workspace, not merely this transaction's own members. A
    transaction that stages no lock does not remove the lock already published, so
    the record must still name it; recording only what was staged would leave the
    workspace disagreeing with its own record the moment anything blocked before the
    lock was rebuilt.

    The commit record is written last, so a crash mid-publication leaves a workspace
    whose contents disagree with its record -- detectably inconsistent, rather than
    an older version an outdated writer may overwrite -- with the staged output still
    on disk to finish forward from.
    """
    members: dict[str, bytes] = {}
    with _transaction_directory(root, staged.transaction_id, create=False) as opened:
        if opened is None:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                "the staged transaction being published is no longer on disk",
            )
        _, transaction_fd = opened
        # The manifest and every member are read from this one open. A publication
        # that reopened the directory by name in between could bind its intent to
        # one directory and publish the bytes of another, and a name is not an
        # object: it can be made to resolve somewhere else at any moment.
        manifest_sha256 = _digest_at(transaction_fd, MANIFEST_FILENAME)
        if manifest_sha256 is None:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                "the staged transaction has no manifest to publish from",
            )
        if manifest_sha256 != staged.manifest_sha256:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                "the staged transaction changed between being validated and being "
                "published; refusing to publish output nothing vouched for",
            )
        for member in staged.members():
            payload = _read_at(transaction_fd, member)
            if payload is None:
                raise RetainedTransactionError(
                    INCONSISTENT_STATE, f"staged {member} is no longer on disk"
                )
            members[member] = payload
    existing = read_publication_intent(root)
    if existing is not None and (
        existing.transaction_id != staged.transaction_id
        or existing.manifest_sha256 != staged.manifest_sha256
    ):
        # An unresolved publication is in flight or interrupted. Overwriting its
        # intent would erase the only route back to whatever it staged, which may be
        # the sole record of an effect that cannot be run again. A record naming the
        # same transaction but different bytes is just as foreign: it is not this
        # publication, whoever started it.
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "an unresolved publication names output other than this one; refusing "
            "to publish over the record of an interrupted commit",
        )
    # Recorded before the first canonical byte moves, so an interrupted publication
    # names the staged output it was finishing -- and the exact bytes of it --
    # regardless of who started it.
    _write_publication_intent(
        root,
        PublicationIntent(
            transaction_id=staged.transaction_id, manifest_sha256=manifest_sha256
        ),
    )
    for name, expected in staged.members().items():
        payload = members[name]
        if _digest_bytes(payload) != expected:
            raise RetainedTransactionError(
                INCONSISTENT_STATE,
                f"staged {name} does not match the manifest it is published under",
            )
        _write_atomic(root / name, payload)
    snapshot = CommittedSnapshot(
        generation=generation,
        transaction_id=staged.transaction_id,
        stages_sha256=_digest_file(root / LEDGER_FILENAME),
        state_sha256=_digest_file(root / STATE_FILENAME),
        lock_file_sha256=_digest_file(root / LOCK_FILENAME),
        lock_identity=(
            staged.lock_identity
            if staged.lock_file_sha256 is not None
            else _published_lock_identity(root)
        ),
    )
    _write_atomic(
        root / COMMIT_RECORD_FILENAME,
        (json.dumps(snapshot.as_json(), indent=2, sort_keys=True) + "\n").encode(),
    )
    clear_publication_intent(root)
    return snapshot


@dataclass(frozen=True, slots=True)
class Decision:
    """What a caller must do next, decided from one coherent read of the workspace."""

    action: str
    snapshot: CommittedSnapshot | None = None
    reservation: Reservation | None = None
    detail: str = ""


def _resolve_publication(root: Path, intent: PublicationIntent) -> bool:
    """Finish, or refuse to abandon, a publication that was already under way.

    A durable intent is a record that a commit had started. Failing to prove that
    commit can be completed is not the same as proving it is safe to throw away:
    with the effect claim already consumed, discarding the staged output leaves an
    effect that happened, no evidence of it, and no permission to run it again. So
    this either finishes the publication, establishes that it already finished, or
    keeps everything exactly where it is.
    """
    manifest_sha256 = _staged_manifest_digest(root, intent.transaction_id)
    if manifest_sha256 != intent.manifest_sha256:
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "the staged output of an interrupted publication is not the output its "
            "intent was recorded for; refusing to publish it, and keeping both as "
            "evidence",
        )
    staged = read_staged(root, intent.transaction_id)
    if staged is None:
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "an interrupted publication names staged output that is no longer "
            "complete; refusing to publish it, and keeping both as evidence",
        )
    if staged.manifest_sha256 != intent.manifest_sha256:
        # The digest above was satisfied by one observation and this is a later one.
        # Comparing the intent against what was actually parsed closes the gap
        # between them, which matters most for a publisher that never reserved: the
        # intent is then the only record vouching for those bytes.
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "the staged output changed between the intent being checked and being "
            "read; refusing to publish it, and keeping both as evidence",
        )
    reservation = read_reservation(root)
    if reservation is not None and not _matches_reservation(staged, reservation):
        raise RetainedTransactionError(
            INCONSISTENT_STATE,
            "an interrupted publication is contradicted by the reservation covering "
            "this workspace; refusing to publish it, and keeping both as evidence",
        )

    recorded = _recorded_snapshot(root)
    recorded_identity = recorded.identity if recorded is not None else None
    if staged.base_identity == recorded_identity:
        publish(
            root,
            staged=staged,
            generation=(recorded.generation + 1 if recorded is not None else 1),
        )
        discard_staging(root, intent.transaction_id)
        return True
    if recorded is not None and recorded.transaction_id == intent.transaction_id:
        # The publication finished and only the clearing of its intent did not. The
        # committed snapshot has to hold up before this is treated as complete.
        read_committed(root)
        clear_publication_intent(root)
        discard_staging(root, intent.transaction_id)
        return True
    raise RetainedTransactionError(
        INCONSISTENT_STATE,
        "an interrupted publication can neither be finished nor shown to have "
        "finished; keeping it and its staged output as evidence",
    )


def _matches_reservation(staged: StagedTransaction, reservation: Reservation) -> bool:
    """Whether staged output is the output of the transaction that reserved.

    The request identities say which transaction it belongs to; the seal says which
    bytes. Without the seal, a complete replacement carrying the same identities is
    indistinguishable from the output that was actually staged, so a reservation
    carrying none covers no output at all. A transaction that died before sealing is
    recognised before this is reached.
    """
    return (
        staged.transaction_id == reservation.transaction_id
        and staged.base_identity == reservation.base_identity
        and staged.candidate_sha256 == reservation.candidate_sha256
        and staged.authority_sha256 == reservation.authority_sha256
        and reservation.staged_manifest_sha256 is not None
        and reservation.staged_manifest_sha256 == staged.manifest_sha256
    )


def recover(root: Path) -> bool:
    """Finish or release an interrupted transaction. Caller holds the coordination lock.

    Recovery is forward-only and never re-runs anything. It reads two records,
    because a transaction becomes recoverable before it becomes discoverable
    through the intent: the output is staged and durable first, and the intent is
    written inside publication. A crash in that window leaves a complete commit
    that only the reservation points at.

    With a publication intent, the intent decides. It names the exact bytes, and a
    publication that cannot be finished or shown to have finished is kept rather
    than abandoned: an intent that has become durable is a record that a commit was
    under way, and the staged output beneath it may be the only evidence of an
    effect that is already consumed.

    Without one, a dead reservation is asked what it left behind:

      complete staged output matching the reservation, based on what is committed
          finished forward, running nothing again
      complete staged output matching the reservation, but superseded
          discarded; another transaction has committed since and this describes a
          workspace that no longer exists
      complete staged output that does not match the reservation
          refused and kept as evidence
      nothing complete
          released; the effect claim, if the boundary was crossed, remains the fence

    Whether an effect ran is not asked. Complete staged output is the transaction's
    own intended commit either way, and releasing is never permission to run again.

    Returns whether the workspace changed.
    """
    changed = False
    intent = read_publication_intent(root)
    if intent is not None:
        changed = _resolve_publication(root, intent)

    existing = read_reservation(root)
    if existing is not None and not owner_is_live(root, existing):
        if intent is None:
            # The transaction may have died between staging its output and
            # recording that it was publishing it. That output is complete and is
            # the only evidence of an effect that cannot be run again, so it is
            # finished forward rather than discarded with the reservation.
            staged = read_staged(root, existing.transaction_id)
            if staged is None and existing.staged_manifest_sha256 is not None:
                # The seal is durable proof that a complete transaction was staged
                # here. Staging that can no longer reproduce it is a damaged commit,
                # not an absent one, and the effect it recorded may already be
                # consumed. Everything is left where it is.
                raise RetainedTransactionError(
                    INCONSISTENT_STATE,
                    "the staged output this reservation was sealed to is no longer "
                    "complete; refusing to discard it, and keeping both as evidence",
                )
            if staged is not None and existing.staged_manifest_sha256 is None:
                # The transaction died before it could commit to what it staged.
                # Nothing outside that directory vouches for those bytes, so they are
                # neither published nor deleted: the effect claim, if the boundary
                # was crossed, remains the fence.
                clear_reservation(root, expected_transaction_id=existing.transaction_id)
                return True
            if staged is not None:
                if existing.staged_manifest_sha256 != staged.manifest_sha256:
                    raise RetainedTransactionError(
                        INCONSISTENT_STATE,
                        "the staged output under this reservation is not the output "
                        "the reservation was sealed to; refusing to publish it, and "
                        "keeping both as evidence",
                    )
                if not _matches_reservation(staged, existing):
                    raise RetainedTransactionError(
                        INCONSISTENT_STATE,
                        "the staged output under this reservation is not the output "
                        "of the transaction that reserved; refusing to publish it, "
                        "and keeping both as evidence",
                    )
                recorded = _recorded_snapshot(root)
                if staged.base_identity == (
                    recorded.identity if recorded is not None else None
                ):
                    publish(
                        root,
                        staged=staged,
                        generation=(
                            recorded.generation + 1 if recorded is not None else 1
                        ),
                    )
        clear_reservation(root, expected_transaction_id=existing.transaction_id)
        discard_staging(root, existing.transaction_id)
        changed = True
    return changed


def arbitrate(
    root: Path,
    *,
    transaction_id: str,
    base_identity: str | None,
    experiment_id: str,
    scope: str,
    candidate_sha256: str,
    authority_sha256: str | None,
) -> Decision:
    """Decide, and take, the right to cross the next effect boundary.

    Everything that must not be split -- recovering an abandonment, reading the
    committed state, reading the reservation, judging liveness, installing a
    reservation -- happens here under one coordination lock, because every gap
    between observing the workspace and acting on that observation is a window in
    which the observation expires.
    """
    with coordination_lock(root):
        recover(root)
        current = read_committed(root)
        current_identity = current.identity if current is not None else None
        existing = read_reservation(root)

        if existing is not None and existing.transaction_id != transaction_id:
            # Recovery has already released every reservation whose owner is gone, so
            # anything still here belongs to a transaction that is running now.
            if existing.is_same_request_as(
                experiment_id=experiment_id,
                scope=scope,
                candidate_sha256=candidate_sha256,
                authority_sha256=authority_sha256,
            ):
                return Decision(WAIT, snapshot=current, reservation=existing)
            return Decision(
                REFUSE,
                snapshot=current,
                reservation=existing,
                detail=(
                    "another transaction holds the effect reservation for this "
                    "workspace; refusing to act while it is in flight"
                ),
            )

        if current_identity != base_identity:
            # The workspace moved while this caller was working. It is not entitled
            # to overwrite that, and it is not stale in a terminal sense either: it
            # must look at what landed before deciding anything.
            return Decision(
                RECONCILE,
                snapshot=current,
                detail=(
                    "the retained workspace advanced while this invocation was "
                    "preparing; reconciling onto the committed transaction"
                ),
            )

        if authority_sha256 is None:
            # Nothing to reserve for: without an authority this invocation can never
            # cross the boundary, so it takes no right it cannot use.
            return Decision(TAKE, snapshot=current)

        write_reservation(
            root,
            Reservation(
                transaction_id=transaction_id,
                base_identity=current_identity,
                experiment_id=experiment_id,
                scope=scope,
                candidate_sha256=candidate_sha256,
                authority_sha256=authority_sha256,
            ),
        )
        return Decision(TAKE, snapshot=current, detail="reservation installed")
