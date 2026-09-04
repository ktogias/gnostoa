"""Two separate trust domains: qualification and experimental execution.

Qualification is coordinator-private. It may see the BASE subject, the frozen
REFERENCE and the hidden oracle, because no experimental agent participates.

Experimental execution must never see the reference, the oracle, the
identification key, assignment-private material or hidden scoring evidence.
Handing an executor the known-correct reference would invalidate the experiment,
so the execution profile is built from a separate materialisation and is checked
against an explicit forbidden-surface list before it is frozen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from tools.experiment.profile import PROFILE_SCHEMA

QUALIFICATION = "qualification"
EXECUTION = "execution"


class ProfileBoundaryError(RuntimeError):
    """A profile would admit a surface its trust domain must never see."""


@dataclass(frozen=True, slots=True)
class ProfileCommon:
    """Everything both trust domains share, typed rather than splatted."""

    image: str
    executor: Mapping[str, object]
    timeout_seconds: int
    archive_limit_bytes: int
    network: Mapping[str, object]
    environment_allowlist: tuple[str, ...]
    # Names only. A secret value never enters a profile or a lock.
    credential_environment: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProfileRoots:
    project: Path
    evidence: Path
    temporary: Path
    read_only: tuple[Path, ...] = ()


def build_profile(
    *,
    domain: str,
    roots: ProfileRoots,
    common: ProfileCommon,
    input_identities: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": PROFILE_SCHEMA,
        "project_root": str(roots.project),
        "evidence_root": str(roots.evidence),
        "temporary_roots": [str(roots.temporary)],
        "read_only_roots": [str(path) for path in roots.read_only],
        "excluded_roots": [],
        "environment_allowlist": sorted(common.environment_allowlist),
        "credential_environment": sorted(common.credential_environment),
        "input_identities": list(input_identities),
        "network": dict(common.network),
        "archive_limit_bytes": common.archive_limit_bytes,
        "timeout_seconds": common.timeout_seconds,
        "executor": dict(common.executor),
        "runtime": {"image": common.image},
        "trust_domain": domain,
    }


def admitted_paths(profile: Mapping[str, object]) -> list[Path]:
    """Every filesystem surface the profile makes visible to its process."""
    surfaces: list[Path] = [
        Path(str(profile["project_root"])),
        Path(str(profile["evidence_root"])),
    ]
    for key in ("temporary_roots", "read_only_roots"):
        declared = cast(Sequence[object], profile.get(key) or [])
        surfaces.extend(Path(str(value)) for value in declared)
    return surfaces


def _resolve(path: Path) -> Path:
    """Resolve without requiring existence, so a planned surface can still be checked."""
    try:
        return path.resolve()
    except OSError:  # pragma: no cover - platform dependent
        return path.absolute()


def _overlaps(left: Path, right: Path) -> bool:
    """True when either path contains the other, or they are the same path.

    Both directions matter. An admitted surface containing a private path exposes it
    directly; an admitted surface nested *inside* a private directory means the
    execution capsule was laid out within the coordinator-private domain, which is
    just as unacceptable.
    """
    left, right = _resolve(left), _resolve(right)
    if left == right:
        return True
    return left.is_relative_to(right) or right.is_relative_to(left)


def assert_execution_boundary(
    profile: Mapping[str, object], forbidden: Mapping[str, Path]
) -> None:
    """Refuse an execution profile that admits, or sits inside, any private surface.

    `forbidden` maps a human name (reference subject, oracle, identification key,
    qualification workspace, sibling arm, ...) to the path that must stay invisible.
    """
    if profile.get("trust_domain") != EXECUTION:
        raise ProfileBoundaryError("not-an-execution-profile")
    admitted = admitted_paths(profile)
    for name, secret in forbidden.items():
        for surface in admitted:
            if _overlaps(surface, Path(secret)):
                raise ProfileBoundaryError(
                    f"execution-profile-admits-{name}: {surface} overlaps {secret}"
                )
