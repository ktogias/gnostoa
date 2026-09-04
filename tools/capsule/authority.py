"""Preflight authority, bound by identity and scope rather than truthiness."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

AUTHORITY_SCHEMA = "gnostoa-preflight-authority/v1"


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
