from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ATTEST_SCHEMA = "gnostoa-derived-artifact-identity/v1"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_CHUNK_SIZE = 1024 * 1024


class EvidenceError(ValueError):
    """Raised when an evidence identity is malformed."""


@dataclass(frozen=True, slots=True)
class InputIdentity:
    id: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "sha256": self.sha256}


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        + b"\n"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as source:
        while True:
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def require_sha256(value: str, *, field: str = "sha256") -> str:
    if not _SHA256_RE.fullmatch(value):
        raise EvidenceError(f"invalid-{field}")
    return value


def parse_input_identity(value: str) -> InputIdentity:
    identifier, separator, digest = value.partition("=")
    if not separator or not identifier:
        raise EvidenceError(f"invalid-input-identity:{value}")
    return InputIdentity(identifier, require_sha256(digest))


def parse_input_identities(
    values: Sequence[str],
    *,
    require_nonempty: bool = True,
    reserved: frozenset[str] = frozenset(),
) -> list[InputIdentity]:
    if require_nonempty and not values:
        raise EvidenceError("input-identities-required")
    parsed = [parse_input_identity(value) for value in values]
    identifiers = [item.id for item in parsed]
    if len(set(identifiers)) != len(identifiers):
        raise EvidenceError("duplicate-input-identity")
    if reserved & set(identifiers):
        raise EvidenceError("reserved-input-identity")
    return parsed


def parse_identity_mappings(
    raw: object,
    *,
    require_nonempty: bool = True,
) -> list[InputIdentity]:
    if not isinstance(raw, list):
        raise EvidenceError("inputs-must-be-a-list")
    values: list[InputIdentity] = []
    identifiers: set[str] = set()
    for item in cast(list[object], raw):
        if not isinstance(item, dict):
            raise EvidenceError("input-identity-must-be-a-mapping")
        mapping = cast(dict[object, object], item)
        identifier = mapping.get("id")
        digest = mapping.get("sha256")
        if not isinstance(identifier, str) or not identifier:
            raise EvidenceError("input-id-invalid")
        if not isinstance(digest, str):
            raise EvidenceError("input-sha256-invalid")
        require_sha256(digest)
        if identifier in identifiers:
            raise EvidenceError("duplicate-input-identity")
        identifiers.add(identifier)
        values.append(InputIdentity(identifier, digest))
    if require_nonempty and not values:
        raise EvidenceError("input-identities-required")
    return values


def configuration_digest(value: Mapping[str, object]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(value)))


def producer_record(
    producer_id: str,
    version: str,
    config_sha256: str,
) -> dict[str, str]:
    if not producer_id or not version:
        raise EvidenceError("producer-identity-invalid")
    require_sha256(config_sha256, field="config-sha256")
    return {
        "id": producer_id,
        "version": version,
        "config_sha256": config_sha256,
    }


def attest_file(
    artifact: Path,
    *,
    producer_id: str,
    producer_version: str,
    config_sha256: str,
    inputs: Sequence[InputIdentity],
) -> dict[str, object]:
    digest, size = sha256_file(artifact)
    return {
        "schema": ATTEST_SCHEMA,
        "sha256": digest,
        "bytes": size,
        "producer": producer_record(
            producer_id,
            producer_version,
            config_sha256,
        ),
        "inputs": [item.as_dict() for item in inputs],
    }


def parse_input_identity_mapping(value: str) -> dict[str, str]:
    return parse_input_identity(value).as_dict()
