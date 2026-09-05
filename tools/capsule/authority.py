"""Authorities, bound by identity and scope rather than truthiness.

Two distinct records. Preflight authority permits running the hidden oracle against
BASE and REFERENCE inside the coordinator-private domain. Launch authority permits
real experimental execution and is additionally bound to one exact frozen lock, so a
stale authority for another lock cannot open the execution path.

Preflight authority binds the same way. Naming an experiment is not enough: the
same experiment id can be prepared into materially different qualification
requests, and the same request can be run through a different backend. A v2
authority therefore carries the digest of one exact prepared candidate, and the
compiler compares it against the identity it computes itself. v1 named only the
experiment, so it cannot express this and is refused as authority for a new
preflight; it stays readable only so historical evidence can still be parsed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

AUTHORITY_SCHEMA = "gnostoa-preflight-authority/v2"
LEGACY_AUTHORITY_SCHEMA = "gnostoa-preflight-authority/v1"
CANDIDATE_SCHEMA = "gnostoa-preflight-candidate/v1"
BASE_REFERENCE_QUALIFICATION = "base-reference-qualification"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
LAUNCH_AUTHORITY_SCHEMA = "gnostoa-launch-authority/v1"
EXPERIMENTAL_EXECUTION = "experimental-execution"


class AuthorityError(ValueError):
    """The authority is malformed or does not cover this experiment."""


def preflight_candidate_payload(
    *,
    experiment_id: str,
    scope: str,
    qualification_backend: str,
    tasks: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """The exact qualification request an owner authorises, as canonical data.

    Built only from implementation-owned identities already fixed by static
    preparation. Task order is the order qualification will actually run in, so a
    reordered request is a different request; it is not sorted away. Nothing
    caller-supplied enters the payload, and no oracle, key or credential material
    does either -- every value here is already a digest or a declared identity.

    Each task also carries the disposition that will actually occur: a fresh
    hidden-oracle qualification, or reuse of one exact prior receipt. Approving the
    subjects and backend is not enough if the same digest could stand for either
    running the oracle or not running it.
    """
    return {
        "schema": CANDIDATE_SCHEMA,
        "experiment_id": experiment_id,
        "scope": scope,
        "qualification_backend": qualification_backend,
        "tasks": [dict(entry) for entry in tasks],
    }


def preflight_candidate_identity(
    *,
    experiment_id: str,
    scope: str,
    qualification_backend: str,
    tasks: Sequence[Mapping[str, str]],
) -> str:
    """The canonical digest of one exact prepared qualification request."""
    from tools.capsule.identity import digest_of

    return digest_of(
        preflight_candidate_payload(
            experiment_id=experiment_id,
            scope=scope,
            qualification_backend=qualification_backend,
            tasks=tasks,
        )
    )


@dataclass(frozen=True, slots=True)
class LegacyPreflightAuthorityV1:
    """A historical v1 record, readable but never effect-bearing.

    Deliberately not a PreflightAuthority: it cannot be passed where authority is
    required, so old evidence stays parseable without becoming usable.
    """

    id: str
    experiment_id: str
    scope: tuple[str, ...]

    def as_json(self) -> dict[str, object]:
        return {
            "schema": LEGACY_AUTHORITY_SCHEMA,
            "id": self.id,
            "experiment_id": self.experiment_id,
            "scope": list(self.scope),
        }


@dataclass(frozen=True, slots=True)
class PreflightAuthority:
    id: str
    experiment_id: str
    scope: tuple[str, ...]
    # The one prepared candidate this authority approves. Required: an authority
    # without it would be a wildcard over every candidate sharing the experiment id.
    preflight_candidate_sha256: str

    def covers(
        self,
        experiment_id: str,
        scope: str,
        *,
        candidate_sha256: str | None = None,
    ) -> bool:
        """True only for this experiment, this scope and this exact candidate.

        A caller that supplies no candidate gets False: absence is never treated as
        a match, so a code path that forgets to compute the identity fails closed
        instead of silently authorising whatever was prepared.
        """
        if self.experiment_id != experiment_id or scope not in self.scope:
            return False
        return (
            candidate_sha256 is not None
            and candidate_sha256 == self.preflight_candidate_sha256
        )

    def as_json(self) -> dict[str, object]:
        return {
            "schema": AUTHORITY_SCHEMA,
            "id": self.id,
            "experiment_id": self.experiment_id,
            "scope": list(self.scope),
            "preflight_candidate_sha256": self.preflight_candidate_sha256,
        }


def _identity_and_scope(payload: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    for key in ("id", "experiment_id"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise AuthorityError(f"authority is missing {key}")
    scope = payload.get("scope")
    if not isinstance(scope, list) or not scope:
        raise AuthorityError("authority must declare a non-empty scope")
    return (
        cast(str, payload["id"]),
        cast(str, payload["experiment_id"]),
        tuple(str(item) for item in scope),
    )


def parse(payload: Mapping[str, Any]) -> PreflightAuthority:
    """Parse an effect-bearing preflight authority. v2 only.

    A v1 record is refused here rather than upgraded. Deriving a candidate digest
    on a legacy object's behalf would invent approval the owner never gave, and
    accepting a missing digest would make v1 a wildcard over every candidate
    sharing the experiment id -- which is the defect this contract exists to close.
    """
    schema = payload.get("schema")
    if schema == LEGACY_AUTHORITY_SCHEMA:
        raise AuthorityError(
            f"{LEGACY_AUTHORITY_SCHEMA} names only an experiment and cannot authorise a "
            f"new base/reference preflight; issue a {AUTHORITY_SCHEMA} authority naming "
            "the exact preflight_candidate_sha256 reported by an authority-less prepare"
        )
    if schema != AUTHORITY_SCHEMA:
        raise AuthorityError(f"unsupported authority schema {schema!r}")
    identifier, experiment_id, scope = _identity_and_scope(payload)
    candidate = payload.get("preflight_candidate_sha256")
    if not isinstance(candidate, str) or not _SHA256.fullmatch(candidate):
        raise AuthorityError(
            "authority must bind preflight_candidate_sha256 as a 64-character "
            "lowercase hex digest of one exact prepared candidate"
        )
    return PreflightAuthority(
        id=identifier,
        experiment_id=experiment_id,
        scope=scope,
        preflight_candidate_sha256=candidate,
    )


def parse_legacy_v1(payload: Mapping[str, Any]) -> LegacyPreflightAuthorityV1:
    """Read a historical v1 record. Never usable as authority for a new effect."""
    if payload.get("schema") != LEGACY_AUTHORITY_SCHEMA:
        raise AuthorityError(
            f"expected {LEGACY_AUTHORITY_SCHEMA}, got {payload.get('schema')!r}"
        )
    identifier, experiment_id, scope = _identity_and_scope(payload)
    return LegacyPreflightAuthorityV1(
        id=identifier, experiment_id=experiment_id, scope=scope
    )


def load_file(path: Path) -> PreflightAuthority:
    return parse(json.loads(path.read_text()))


@dataclass(frozen=True, slots=True)
class LaunchAuthority:
    """Permission to execute one exact frozen lock."""

    id: str
    experiment_id: str
    lock_sha256: str
    scope: tuple[str, ...]
    max_runs: int | None = None

    def covers(self, *, experiment_id: str, lock_sha256: str, runs: int) -> list[str]:
        """Return the reasons this authority does not cover the request."""
        reasons: list[str] = []
        if self.experiment_id != experiment_id:
            reasons.append(
                f"authority names experiment {self.experiment_id!r}, not {experiment_id!r}"
            )
        if self.lock_sha256 != lock_sha256:
            reasons.append("authority is bound to a different experiment lock")
        if EXPERIMENTAL_EXECUTION not in self.scope:
            reasons.append(
                f"authority scope {list(self.scope)} does not permit {EXPERIMENTAL_EXECUTION}"
            )
        if self.max_runs is not None and runs > self.max_runs:
            reasons.append(f"plan has {runs} runs, authority permits {self.max_runs}")
        return reasons

    def as_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "lock_sha256": self.lock_sha256,
            "scope": list(self.scope),
            "max_runs": self.max_runs,
        }


def parse_launch(payload: Mapping[str, Any]) -> LaunchAuthority:
    if payload.get("schema") != LAUNCH_AUTHORITY_SCHEMA:
        raise AuthorityError(
            f"unsupported launch-authority schema {payload.get('schema')!r}; "
            f"expected {LAUNCH_AUTHORITY_SCHEMA}"
        )
    for key in ("id", "experiment_id", "lock_sha256"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise AuthorityError(f"launch authority is missing {key}")
    scope = payload.get("scope")
    if not isinstance(scope, list) or not scope:
        raise AuthorityError("launch authority must declare a non-empty scope")
    max_runs = payload.get("max_runs")
    if max_runs is not None and (not isinstance(max_runs, int) or max_runs <= 0):
        raise AuthorityError("max_runs must be a positive integer when declared")
    return LaunchAuthority(
        id=cast(str, payload["id"]),
        experiment_id=cast(str, payload["experiment_id"]),
        lock_sha256=cast(str, payload["lock_sha256"]),
        scope=tuple(str(item) for item in scope),
        max_runs=max_runs,
    )


def load_launch_file(path: Path) -> LaunchAuthority:
    return parse_launch(json.loads(path.read_text()))
