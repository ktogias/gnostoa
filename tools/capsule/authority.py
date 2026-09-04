"""Authorities, bound by identity and scope rather than truthiness.

Two distinct records. Preflight authority permits running the hidden oracle against
BASE and REFERENCE inside the coordinator-private domain. Launch authority permits
real experimental execution and is additionally bound to one exact frozen lock, so a
stale authority for another lock cannot open the execution path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

AUTHORITY_SCHEMA = "gnostoa-preflight-authority/v1"
LAUNCH_AUTHORITY_SCHEMA = "gnostoa-launch-authority/v1"
EXPERIMENTAL_EXECUTION = "experimental-execution"


class AuthorityError(ValueError):
    """The authority is malformed or does not cover this experiment."""


@dataclass(frozen=True, slots=True)
class PreflightAuthority:
    id: str
    experiment_id: str
    scope: tuple[str, ...]

    def covers(self, experiment_id: str, scope: str) -> bool:
        return self.experiment_id == experiment_id and scope in self.scope

    def as_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "scope": list(self.scope),
        }


def parse(payload: Mapping[str, Any]) -> PreflightAuthority:
    if payload.get("schema") != AUTHORITY_SCHEMA:
        raise AuthorityError(f"unsupported authority schema {payload.get('schema')!r}")
    for key in ("id", "experiment_id"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise AuthorityError(f"authority is missing {key}")
    scope = payload.get("scope")
    if not isinstance(scope, list) or not scope:
        raise AuthorityError("authority must declare a non-empty scope")
    return PreflightAuthority(
        id=cast(str, payload["id"]),
        experiment_id=cast(str, payload["experiment_id"]),
        scope=tuple(str(item) for item in scope),
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
