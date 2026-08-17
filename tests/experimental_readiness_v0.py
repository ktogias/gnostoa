"""Experimental C4-v0 readiness predicate — Gnostoa self-hosted, not public surface.

This module answers one question deterministically, read-only, over evidence that
already exists in the repository: **may a given commit's task envelope be
presented as ready?** It never repairs, writes or fetches anything.

It is deliberately not a supported tool, an inherited schema, a generic guardrail
or an adopter contract. See
`knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md`.
It lives under `tests/` because that directory is outside the pinned
public-surface digest and is not packaged for adopting projects.

Fail-closed means READY is returned only when every precondition is *decided*
satisfied. Evidence that cannot be checked locally yields INDETERMINATE, which is
not READY.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from tools.knowledge_common import KnowledgeFormatError
from tools.task_envelope import (
    checkpoint_digest,
    load_task_envelope,
    validate_task_envelope,
)

TERMINAL_STATUSES = frozenset({"complete", "superseded"})
#: Identity kinds whose subject is a repository file, so the digest recomputes
#: from evidence that is already present locally.
LOCAL_DIGEST_KINDS = frozenset({"file-sha256"})

ENVELOPE_VALIDATES = "envelope-validates"
CHECKPOINT_CHAIN_RECOMPUTES = "checkpoint-chain-recomputes"
DEPENDENCIES_RECOMPUTE = "declared-dependencies-recompute"
ENVELOPE_IS_CURRENT = "envelope-is-current"

SCHEMA_PATH = "schemas/task-envelope.schema.json"


class ReadinessInputError(RuntimeError):
    """The evidence could not be read at all, so no verdict may be produced."""


class Decision(Enum):
    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNDECIDABLE = "undecidable"


class Verdict(Enum):
    READY = "ready"
    BLOCKED = "blocked"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class Check:
    precondition: str
    decision: Decision
    detail: str


@dataclass(frozen=True)
class Result:
    commit: str
    envelope: str
    verdict: Verdict
    checks: tuple[Check, ...]

    def decision(self, precondition: str) -> Decision:
        for check in self.checks:
            if check.precondition == precondition:
                return check.decision
        raise KeyError(precondition)

    def failing(self) -> tuple[Check, ...]:
        return tuple(
            check for check in self.checks if check.decision is not Decision.SATISFIED
        )


def _git(repository: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repository.resolve()}",
            "-C",
            str(repository),
            *arguments,
        ],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ReadinessInputError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout


def _tracked_paths(repository: Path, commit: str) -> frozenset[str]:
    listing = _git(repository, "ls-tree", "-r", "--name-only", "-z", commit)
    return frozenset(entry for entry in listing.decode("utf-8").split("\0") if entry)


def _blob(repository: Path, commit: str, path: str) -> bytes:
    return _git(repository, "cat-file", "blob", f"{commit}:{path}")


def _last_change(repository: Path, commit: str, path: str) -> str | None:
    try:
        listing = _git(repository, "rev-list", "-1", commit, "--", path)
    except ReadinessInputError:
        return None
    revision = listing.decode("utf-8").strip()
    return revision or None


def _predecessor(repository: Path, commit: str, path: str) -> str | None:
    """The commit holding the version before the one this candidate carries.

    The candidate's envelope version was recorded at some commit R, which may be
    an ancestor rather than the candidate itself. The predecessor of that version
    is therefore the last change before R, not before the candidate.
    """
    recording = _last_change(repository, commit, path)
    if recording is None:
        return None
    return _last_change(repository, f"{recording}^", path)


def _materialize(
    repository: Path,
    commit: str,
    destination: Path,
    tracked: frozenset[str],
    wanted: tuple[str, ...],
) -> None:
    """Write exactly the named blobs into an isolated tree. Missing stays missing."""
    for path in wanted:
        if path not in tracked:
            continue
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_blob(repository, commit, path))


def _local_references(envelope: dict[str, Any]) -> tuple[str, ...]:
    references = envelope.get("references")
    if not isinstance(references, dict):
        return ()
    resources: list[str] = []
    for label in ("decisions", "evidence"):
        items = references.get(label)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            resource = item.get("resource")
            if isinstance(resource, str) and "://" not in resource:
                resources.append(resource)
    return tuple(resources)


def _resource_for(envelope: dict[str, Any], identifier: str) -> str | None:
    """Join a declared dependency id to its reference resource. Ambiguity is None."""
    references = envelope.get("references")
    if not isinstance(references, dict):
        return None
    found: list[str] = []
    for label in ("decisions", "evidence"):
        items = references.get(label)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get("id") != identifier:
                continue
            resource = item.get("resource")
            if isinstance(resource, str):
                found.append(resource)
    if len(found) != 1:
        return None
    return found[0]


def _load_envelope_only(repository: Path, commit: str, envelope_path: str) -> Any:
    """Parse the envelope without judging it, for checks that need its fields."""
    tracked = _tracked_paths(repository, commit)
    if envelope_path not in tracked:
        raise ReadinessInputError(f"{envelope_path} does not exist at {commit}")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _materialize(repository, commit, root, tracked, (envelope_path,))
        return load_task_envelope(root / envelope_path)


def _check_envelope_validates(
    repository: Path, commit: str, envelope_path: str, tracked: frozenset[str]
) -> Check:
    if SCHEMA_PATH not in tracked:
        return Check(
            ENVELOPE_VALIDATES,
            Decision.UNDECIDABLE,
            f"no {SCHEMA_PATH} exists at {commit[:12]}",
        )
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _materialize(repository, commit, root, tracked, (envelope_path, SCHEMA_PATH))
        try:
            envelope = _load_envelope_only(repository, commit, envelope_path)
        except KnowledgeFormatError as exc:
            return Check(ENVELOPE_VALIDATES, Decision.VIOLATED, str(exc))
        _materialize(repository, commit, root, tracked, _local_references(envelope))
        try:
            _, issues = validate_task_envelope(
                root / envelope_path, root, root / SCHEMA_PATH
            )
        except KnowledgeFormatError as exc:
            return Check(ENVELOPE_VALIDATES, Decision.VIOLATED, str(exc))
    if issues:
        return Check(
            ENVELOPE_VALIDATES,
            Decision.VIOLATED,
            f"{len(issues)} validation issue(s); first: {issues[0]}",
        )
    return Check(ENVELOPE_VALIDATES, Decision.SATISFIED, "validates with no issues")


def _check_checkpoint_chain(
    repository: Path, commit: str, envelope_path: str, envelope: dict[str, Any]
) -> Check:
    checkpoint = envelope.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES, Decision.VIOLATED, "no checkpoint recorded"
        )
    sequence = checkpoint.get("sequence")
    previous = checkpoint.get("previous")
    if not isinstance(sequence, int):
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES,
            Decision.VIOLATED,
            "checkpoint sequence is not an integer",
        )

    ancestor = _predecessor(repository, commit, envelope_path)
    if ancestor is None:
        if sequence == 1 and previous is None:
            return Check(
                CHECKPOINT_CHAIN_RECOMPUTES,
                Decision.SATISFIED,
                "first checkpoint with no predecessor",
            )
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES,
            Decision.UNDECIDABLE,
            f"sequence {sequence} declares a predecessor that this history does not contain",
        )

    try:
        recorded = _load_envelope_only(repository, ancestor, envelope_path)
    except (ReadinessInputError, KnowledgeFormatError) as exc:
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES,
            Decision.UNDECIDABLE,
            f"predecessor {ancestor[:12]} is unreadable: {exc}",
        )
    try:
        expected = checkpoint_digest(recorded)
    except KnowledgeFormatError as exc:
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES,
            Decision.UNDECIDABLE,
            f"predecessor {ancestor[:12]} has no computable digest: {exc}",
        )
    if previous != expected:
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES,
            Decision.VIOLATED,
            f"declared previous {str(previous)[:19]}… does not match predecessor "
            f"{ancestor[:12]} digest {expected[:19]}…",
        )
    recorded_checkpoint = recorded.get("checkpoint")
    recorded_sequence = (
        recorded_checkpoint.get("sequence")
        if isinstance(recorded_checkpoint, dict)
        else None
    )
    if recorded_sequence != sequence - 1:
        return Check(
            CHECKPOINT_CHAIN_RECOMPUTES,
            Decision.VIOLATED,
            f"sequence {sequence} does not follow predecessor sequence {recorded_sequence}",
        )
    return Check(
        CHECKPOINT_CHAIN_RECOMPUTES,
        Decision.SATISFIED,
        f"chains onto {ancestor[:12]} at sequence {recorded_sequence}",
    )


def _check_dependencies(
    repository: Path,
    commit: str,
    envelope: dict[str, Any],
    tracked: frozenset[str],
) -> Check:
    identities = envelope.get("identities")
    dependencies = (
        identities.get("dependencies") if isinstance(identities, dict) else None
    )
    if not isinstance(dependencies, list):
        return Check(
            DEPENDENCIES_RECOMPUTE, Decision.VIOLATED, "no declared dependencies"
        )

    undecidable: list[str] = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            return Check(
                DEPENDENCIES_RECOMPUTE, Decision.VIOLATED, "malformed dependency entry"
            )
        identifier = dependency.get("id")
        kind = dependency.get("kind")
        value = dependency.get("value")
        if not isinstance(identifier, str) or not isinstance(value, str):
            return Check(
                DEPENDENCIES_RECOMPUTE, Decision.VIOLATED, "malformed dependency entry"
            )
        if kind not in LOCAL_DIGEST_KINDS:
            undecidable.append(f"{identifier}: kind {kind} is not locally verifiable")
            continue
        resource = _resource_for(envelope, identifier)
        if resource is None:
            undecidable.append(f"{identifier}: no unambiguous reference resource")
            continue
        if resource not in tracked:
            undecidable.append(
                f"{identifier}: {resource} does not exist at this commit"
            )
            continue
        digest = hashlib.sha256(_blob(repository, commit, resource)).hexdigest()
        if value != f"sha256:{digest}":
            return Check(
                DEPENDENCIES_RECOMPUTE,
                Decision.VIOLATED,
                f"{identifier} declares {value[:19]}… but {resource} hashes to "
                f"sha256:{digest[:12]}…",
            )
    if undecidable:
        return Check(
            DEPENDENCIES_RECOMPUTE,
            Decision.UNDECIDABLE,
            "; ".join(undecidable),
        )
    return Check(
        DEPENDENCIES_RECOMPUTE,
        Decision.SATISFIED,
        f"{len(dependencies)} declared identity(ies) recompute",
    )


def _check_envelope_is_current(
    repository: Path, commit: str, envelope_path: str, envelope: dict[str, Any]
) -> Check:
    state = envelope.get("state")
    status = state.get("status") if isinstance(state, dict) else None
    if status in TERMINAL_STATUSES:
        return Check(
            ENVELOPE_IS_CURRENT,
            Decision.SATISFIED,
            f"status {status} makes currency irrelevant",
        )
    last = _last_change(repository, commit, envelope_path)
    if last is None:
        return Check(
            ENVELOPE_IS_CURRENT,
            Decision.UNDECIDABLE,
            "no recorded change to this envelope in this history",
        )
    if last != commit:
        return Check(
            ENVELOPE_IS_CURRENT,
            Decision.VIOLATED,
            f"envelope last changed at {last[:12]}, but the candidate is {commit[:12]}",
        )
    return Check(
        ENVELOPE_IS_CURRENT, Decision.SATISFIED, "candidate is the recording commit"
    )


def _combine(checks: tuple[Check, ...]) -> Verdict:
    if any(check.decision is Decision.VIOLATED for check in checks):
        return Verdict.BLOCKED
    if any(check.decision is Decision.UNDECIDABLE for check in checks):
        return Verdict.INDETERMINATE
    return Verdict.READY


def evaluate(repository: Path, commit: str, envelope_path: str) -> Result:
    """Decide whether `envelope_path` at `commit` may be presented as ready.

    `commit` accepts the repository's canonical `git:<sha>` identity form, which
    is what `identities.base` records, as well as any ordinary Git revision.
    """
    if commit.startswith("git:"):
        commit = commit[len("git:") :]
    resolved = _git(repository, "rev-parse", f"{commit}^{{commit}}")
    commit = resolved.decode("utf-8").strip()
    tracked = _tracked_paths(repository, commit)

    validity = _check_envelope_validates(repository, commit, envelope_path, tracked)
    try:
        envelope = _load_envelope_only(repository, commit, envelope_path)
    except KnowledgeFormatError as exc:
        checks = (
            validity,
            Check(CHECKPOINT_CHAIN_RECOMPUTES, Decision.VIOLATED, str(exc)),
            Check(DEPENDENCIES_RECOMPUTE, Decision.VIOLATED, str(exc)),
            Check(ENVELOPE_IS_CURRENT, Decision.VIOLATED, str(exc)),
        )
        return Result(commit, envelope_path, _combine(checks), checks)

    checks = (
        validity,
        _check_checkpoint_chain(repository, commit, envelope_path, envelope),
        _check_dependencies(repository, commit, envelope, tracked),
        _check_envelope_is_current(repository, commit, envelope_path, envelope),
    )
    return Result(commit, envelope_path, _combine(checks), checks)
