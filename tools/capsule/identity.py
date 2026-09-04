"""Content addressing for capsule artifacts.

Reuses the runner's canonical JSON and digest primitives so that capsule and
runner evidence share one identity discipline instead of two.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from tools.experiment.evidence import canonical_json_bytes, sha256_bytes, sha256_file

__all__ = ["digest_of", "digest_text", "digest_path", "PRODUCER"]

PRODUCER = "gnostoa.capsule/v1"


def digest_of(value: object) -> str:
    """Content digest of any JSON-serialisable value, canonically encoded."""
    return sha256_bytes(canonical_json_bytes(value))


def digest_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def digest_path(path: Path) -> str:
    digest, _size = sha256_file(path)
    return digest


def provenance(inputs: Mapping[str, object]) -> dict[str, object]:
    """Producer provenance for a generated artifact."""
    return {"producer": PRODUCER, "inputs_sha256": digest_of(dict(inputs))}
