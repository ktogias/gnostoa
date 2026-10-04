"""Whether an agent's provider token holds exactly its declared least privilege.

Decision 0101 (#362). This is the provider-neutral core: it validates the declaration
and judges observations against it. It makes no request. A provider adapter turns each
probe's answer into an ``Observation``; capability names, token kinds and repositories
are the policy's and the adapter's vocabulary, opaque here.

The asymmetry is deliberate. An excess grant must be *disproven*: one the probes could
not rule out leaves the verdict UNVERIFIED. A missing grant need only not be *proven*:
a required grant no probe can measure is listed, because a missing grant reveals itself
the first time it is used, and an excess one never does.
"""

from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, NamedTuple

SCHEMA = "gnostoa-credential-posture/v1"
LEVELS = ("none", "read", "write")
# GRANTED and NOT_GRANTED are the provider's answers. UNKNOWN is a probe that got no
# usable answer. UNMEASURABLE is a level no non-effecting probe can reach. PUBLIC is a
# read anyone may make, so a grant there adds nothing and cannot be told apart.
# NOT_APPLICABLE is a level the provider does not define for the capability.
STATES = frozenset(
    {"GRANTED", "NOT_GRANTED", "UNKNOWN", "UNMEASURABLE", "PUBLIC", "NOT_APPLICABLE"}
)
_MOOT = frozenset({"PUBLIC", "NOT_APPLICABLE"})
_REQUIRED_KEYS = frozenset(
    {
        "id",
        "version",
        "token_kind",
        "max_lifetime_days",
        "resource_owner",
        "repositories",
        "capabilities",
    }
)
_OPTIONAL_KEYS = frozenset({"owner", "description"})
# Most dangerous first: the wrong kind of credential, then a grant beyond the
# declaration, then one missing, then a lifetime beyond the bound, then what could not
# be ruled out.
_PRECEDENCE = (
    "TOKEN_KIND_MISMATCH",
    "EXCESS",
    "DEFICIENT",
    "LIFETIME_EXCEEDED",
    "UNVERIFIED",
)


class PolicyError(ValueError):
    """The least-privilege declaration is malformed."""


class Bound(NamedTuple):
    """The lowest and highest level a capability may hold."""

    minimum: str
    maximum: str


class Policy(NamedTuple):
    """A validated least-privilege declaration."""

    id: str
    token_kind: str
    max_lifetime_days: int
    resource_owner: str
    repositories: tuple[str, ...]
    capabilities: dict[str, Bound]


class Observation(NamedTuple):
    """What one probe established about one level of one capability."""

    capability: str
    level: str
    state: str
    evidence: str


class ScopeObservation(NamedTuple):
    """Whether the token can write to a repository other than the subject."""

    repository: str
    state: str
    evidence: str


class Facts(NamedTuple):
    """Everything an adapter established about one token."""

    token_kind: str
    expires_at: str | None
    observations: tuple[Observation, ...]
    scope: tuple[ScopeObservation, ...]


def _level(value: Any, label: str) -> str:
    if value not in LEVELS:
        raise PolicyError(f"{label} is not one of {', '.join(LEVELS)}")
    return str(value)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{label} is not a non-empty string")
    return value


def load_policy(document: Any) -> Policy:
    """Return ``document`` as a validated policy, or raise ``PolicyError``."""
    if not isinstance(document, Mapping):
        raise PolicyError("the policy is not a mapping")
    keys = set(document)
    if keys - _REQUIRED_KEYS - _OPTIONAL_KEYS:
        raise PolicyError(
            f"unknown policy keys: {sorted(keys - _REQUIRED_KEYS - _OPTIONAL_KEYS)}"
        )
    if _REQUIRED_KEYS - keys:
        raise PolicyError(f"missing policy keys: {sorted(_REQUIRED_KEYS - keys)}")
    lifetime = document["max_lifetime_days"]
    if isinstance(lifetime, bool) or not isinstance(lifetime, int) or lifetime <= 0:
        raise PolicyError("max_lifetime_days is not a positive integer")
    repositories = document["repositories"]
    if not isinstance(repositories, list) or not repositories:
        raise PolicyError("repositories is not a non-empty list")
    capabilities = document["capabilities"]
    if not isinstance(capabilities, Mapping) or not capabilities:
        raise PolicyError("capabilities is not a non-empty mapping")
    bounds: dict[str, Bound] = {}
    for name, bound in capabilities.items():
        if not isinstance(bound, Mapping) or set(bound) != {"min", "max"}:
            raise PolicyError(f"capability {name!r} is not a {{min, max}} mapping")
        minimum = _level(bound["min"], f"{name}.min")
        maximum = _level(bound["max"], f"{name}.max")
        if LEVELS.index(minimum) > LEVELS.index(maximum):
            raise PolicyError(f"capability {name!r} has a minimum above its maximum")
        bounds[_text(name, "capability name")] = Bound(minimum, maximum)
    return Policy(
        id=_text(document["id"], "id"),
        token_kind=_text(document["token_kind"], "token_kind"),
        max_lifetime_days=lifetime,
        resource_owner=_text(document["resource_owner"], "resource_owner"),
        repositories=tuple(_text(r, "repository") for r in repositories),
        capabilities=bounds,
    )


def _instant(value: str) -> datetime.datetime:
    moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"{value!r} carries no time zone")
    return moment


def _excess(
    name: str, bound: Bound, read: str | None, write: str | None
) -> tuple[list[str], list[str]]:
    """Return the excess this capability certainly holds, and what was not ruled out."""
    maximum = LEVELS.index(bound.maximum)
    certain: list[str] = []
    possible: list[str] = []
    # A write grant includes a read one, so a read refused rules out a write.
    read_refused = read == "NOT_GRANTED"
    if maximum < LEVELS.index("write"):
        if write == "GRANTED":
            certain.append(f"{name}:write")
        elif write != "NOT_GRANTED" and write not in _MOOT and not read_refused:
            possible.append(f"{name}:write")
    if maximum < LEVELS.index("read") and write != "GRANTED":
        if read == "GRANTED":
            certain.append(f"{name}:read")
        elif read not in {"NOT_GRANTED", *_MOOT}:
            possible.append(f"{name}:read")
    return certain, possible


def _minimum(
    name: str, bound: Bound, read: str | None, write: str | None
) -> tuple[list[str], list[str]]:
    """Return the required grants certainly missing, and those not proven present."""
    if bound.minimum == "write":
        if write == "GRANTED":
            return [], []
        if write == "NOT_GRANTED" or read == "NOT_GRANTED":
            return [f"{name}:write"], []
        return [], [f"{name}:write"]
    if bound.minimum == "read":
        if write == "GRANTED" or read in {"GRANTED", "PUBLIC"}:
            return [], []
        if read == "NOT_GRANTED":
            return [f"{name}:read"], []
        return [], [f"{name}:read"]
    return [], []


def _lifetime(policy: Policy, expires_at: str | None, now: str) -> tuple[bool, Any]:
    """Return whether the token's remaining lifetime is within the bound, and its days."""
    if expires_at is None:
        return False, None
    remaining = (_instant(expires_at) - _instant(now)).total_seconds() / 86400
    return 0 < remaining <= policy.max_lifetime_days, round(remaining, 2)


def evaluate(policy: Policy, facts: Facts, now: str) -> dict[str, Any]:
    """Return the verdict of ``facts`` against ``policy`` at ``now``."""
    states: dict[tuple[str, str], str] = {}
    undeclared: list[str] = []
    for observation in facts.observations:
        if observation.state not in STATES or observation.level not in LEVELS[1:]:
            raise ValueError(f"malformed observation {observation!r}")
        states[(observation.capability, observation.level)] = observation.state
        if observation.capability not in policy.capabilities:
            undeclared.append(f"{observation.capability}:{observation.level}")
    excess: list[str] = []
    unverified: list[str] = []
    deficient: list[str] = []
    minimum_unverified: list[str] = []
    rows = []
    # An observed capability the policy does not name is held to "none": a grant the
    # declaration did not foresee is excess, never a silent pass.
    names = sorted(set(policy.capabilities) | {c for c, _ in states})
    for name in names:
        bound = policy.capabilities.get(name, Bound("none", "none"))
        read, write = states.get((name, "read")), states.get((name, "write"))
        certain, possible = _excess(name, bound, read, write)
        missing, unproven = _minimum(name, bound, read, write)
        excess += certain
        unverified += possible
        deficient += missing
        minimum_unverified += unproven
        rows.append(
            {
                "capability": name,
                "declared": {"min": bound.minimum, "max": bound.maximum},
                "read": read,
                "write": write,
            }
        )
    for scoped in facts.scope:
        if scoped.repository in policy.repositories:
            continue
        if scoped.state == "GRANTED":
            excess.append(f"scope:{scoped.repository}")
        elif scoped.state != "NOT_GRANTED":
            unverified.append(f"scope:{scoped.repository}")
    within, remaining = _lifetime(policy, facts.expires_at, now)
    found = {
        "TOKEN_KIND_MISMATCH": facts.token_kind != policy.token_kind,
        "EXCESS": bool(excess),
        "DEFICIENT": bool(deficient),
        "LIFETIME_EXCEEDED": not within,
        "UNVERIFIED": bool(unverified),
    }
    reasons = [reason for reason in _PRECEDENCE if found[reason]]
    return {
        "schema": SCHEMA,
        "policy": policy.id,
        "verdict": reasons[0] if reasons else "EXACT",
        "reasons": reasons,
        "token_kind": {"declared": policy.token_kind, "observed": facts.token_kind},
        "lifetime": {
            "expires_at": facts.expires_at,
            "max_days": policy.max_lifetime_days,
            "remaining_days": remaining,
        },
        "excess": excess,
        "deficient": deficient,
        "unverified": unverified,
        "minimum_unverified": minimum_unverified,
        "undeclared": undeclared,
        "rows": rows,
        "scope": [{"repository": s.repository, "state": s.state} for s in facts.scope],
    }
