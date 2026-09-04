"""Content-addressed capability certificates.

An expensive qualification (runner boundary, relay boundary, sealed sink,
reusable runtime adapter) becomes a record binding implementation, runtime and
configuration identity to certified bounds and evidence. A certificate is reused
only under exact identity match and only when the request fits inside the
certified bounds. Bounds are never widened to fit a request.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

CERTIFICATE_SCHEMA = "gnostoa-capability-certificate/v1"

# Bound semantics must be declared, not inferred from the name.
_MAXIMUM_BOUNDS = frozenset({"max_plaintext_bytes", "max_payload_bytes", "max_archive_bytes"})
_MINIMUM_BOUNDS = frozenset({"min_hold_seconds", "min_liveness_samples"})


class CertificateError(ValueError):
    """The certificate is malformed and must not be trusted."""


@dataclass(frozen=True, slots=True)
class CapabilityCertificate:
    capability: str
    implementation_sha256: str
    runtime_identity: str
    configuration_sha256: str
    bounds: Mapping[str, int]
    evidence_sha256: str

    def satisfies(
        self,
        *,
        capability: str,
        runtime_identity: str,
        implementation_sha256: str,
        configuration_sha256: str,
        requested: Mapping[str, int],
    ) -> bool:
        """True only under exact identity match with the request inside the bounds."""
        if capability != self.capability:
            return False
        if runtime_identity != self.runtime_identity:
            return False
        if implementation_sha256 != self.implementation_sha256:
            return False
        if configuration_sha256 != self.configuration_sha256:
            return False
        for name, value in requested.items():
            if name not in self.bounds:
                return False
            certified = self.bounds[name]
            if name in _MAXIMUM_BOUNDS:
                if value > certified:
                    return False
            elif name in _MINIMUM_BOUNDS:
                if value > certified:
                    return False
            elif value != certified:
                return False
        return True

    def as_json(self) -> dict[str, object]:
        return {
            "schema": CERTIFICATE_SCHEMA,
            "capability": self.capability,
            "implementation_sha256": self.implementation_sha256,
            "runtime_identity": self.runtime_identity,
            "configuration_sha256": self.configuration_sha256,
            "bounds": dict(self.bounds),
            "evidence_sha256": self.evidence_sha256,
        }


def load(payload: Mapping[str, Any]) -> CapabilityCertificate:
    if payload.get("schema") != CERTIFICATE_SCHEMA:
        raise CertificateError(f"unsupported certificate schema {payload.get('schema')!r}")
    bounds = payload.get("bounds")
    if not isinstance(bounds, dict):
        raise CertificateError("bounds must be a mapping")
    for key in (
        "capability",
        "implementation_sha256",
        "runtime_identity",
        "configuration_sha256",
        "evidence_sha256",
    ):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise CertificateError(f"missing or invalid {key}")
    return CapabilityCertificate(
        capability=cast(str, payload["capability"]),
        implementation_sha256=cast(str, payload["implementation_sha256"]),
        runtime_identity=cast(str, payload["runtime_identity"]),
        configuration_sha256=cast(str, payload["configuration_sha256"]),
        bounds={str(k): int(v) for k, v in bounds.items()},
        evidence_sha256=cast(str, payload["evidence_sha256"]),
    )


def load_file(path: Path) -> CapabilityCertificate:
    return load(json.loads(path.read_text()))
