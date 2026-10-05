"""Whether an agent's provider token holds exactly its declared least privilege.

Decision 0101 (#362). This is the provider-neutral core: it validates the declaration
and judges observations against it. It makes no request. A provider adapter turns each
probe's answer into an ``Observation``; capability names, credential kinds and
repositories are the policy's and the adapter's vocabulary, opaque here.

The asymmetry is deliberate. An excess grant must be *disproven*: one the probes could
not rule out leaves the verdict UNVERIFIED, unless the declaration's owner accepted
that level as unmeasurable, with a reason. A missing grant need only not be *proven*:
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
        "credential_kind",
        "max_lifetime_days",
        "resource_owner",
        "repositories",
        "capabilities",
    }
)
_OPTIONAL_KEYS = frozenset({"owner", "description", "accepted_unmeasurable"})
# Most dangerous first: the wrong kind of credential, then a grant beyond the
# declaration, then one missing, then a lifetime beyond the bound, then what could not
# be ruled out.
_PRECEDENCE = (
    "CREDENTIAL_KIND_MISMATCH",
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
    credential_kind: str
    max_lifetime_days: int
    resource_owner: str
    repositories: tuple[str, ...]
    capabilities: dict[str, Bound]
    # "capability:level" -> why the owner accepts that no probe can measure it.
    accepted_unmeasurable: dict[str, str]


class Observation(NamedTuple):
    """What one probe established about one level of one capability."""

    capability: str
    level: str
    state: str
    evidence: str


class ScopeObservation(NamedTuple):
    """Whether the token can write to one repository it can see."""

    repository: str
    state: str
    evidence: str


class Facts(NamedTuple):
    """Everything an adapter established about one token, for one subject."""

    subject: str
    credential_kind: str
    expires_at: str | None
    observations: tuple[Observation, ...]
    scope: tuple[ScopeObservation, ...]
    # Whether the scope shows the token's selection is not everything its owner has
    # and will have: a selection of "all" is otherwise indistinguishable.
    selection_bounded: bool = False
    # Whether the transport's own credential for writes (a push) is shown to be the
    # checked token: BOUND, or why not, with its evidence.
    transport: tuple[str, str] = ("UNKNOWN", "not observed")


def _level(value: Any, label: str) -> str:
    """Return ``value`` as a level, or raise ``PolicyError`` naming ``label``."""
    if value not in LEVELS:
        raise PolicyError(f"{label} is not one of {', '.join(LEVELS)}")
    return str(value)


def _text(value: Any, label: str) -> str:
    """Return ``value`` as a non-empty string, or raise ``PolicyError``."""
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{label} is not a non-empty string")
    return value


def _checked_keys(document: Any) -> Mapping[str, Any]:
    """Return ``document`` once it has every required key and no unknown one."""
    if not isinstance(document, Mapping):
        raise PolicyError("the policy is not a mapping")
    keys = set(document)
    unknown = keys - _REQUIRED_KEYS - _OPTIONAL_KEYS
    if unknown:
        raise PolicyError(f"unknown policy keys: {sorted(unknown)}")
    if _REQUIRED_KEYS - keys:
        raise PolicyError(f"missing policy keys: {sorted(_REQUIRED_KEYS - keys)}")
    return document


def _bounds(capabilities: Any) -> dict[str, Bound]:
    """Return each capability's validated ``{min, max}`` bound."""
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
    return bounds


def _accepted(value: Any) -> dict[str, str]:
    """Return the accepted unmeasurable levels, each with its non-empty reason."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise PolicyError("accepted_unmeasurable is not a mapping")
    accepted: dict[str, str] = {}
    for key, reason in value.items():
        capability, _, level = str(key).partition(":")
        if not capability or level not in LEVELS[1:]:
            raise PolicyError(
                f"accepted_unmeasurable key {key!r} is not capability:level"
            )
        accepted[str(key)] = _text(reason, f"the reason for accepting {key}")
    return accepted


def load_policy(document: Any) -> Policy:
    """Return ``document`` as a validated policy, or raise ``PolicyError``."""
    checked = _checked_keys(document)
    lifetime = checked["max_lifetime_days"]
    # An integral float such as 31.0 is an integer to JSON Schema, and so to this check
    # (CodeAnt on #364).
    if isinstance(lifetime, float) and lifetime.is_integer():
        lifetime = int(lifetime)
    if isinstance(lifetime, bool) or not isinstance(lifetime, int) or lifetime <= 0:
        raise PolicyError("max_lifetime_days is not a positive integer")
    repositories = checked["repositories"]
    if not isinstance(repositories, list) or not repositories:
        raise PolicyError("repositories is not a non-empty list")
    bounds = _bounds(checked["capabilities"])
    accepted = _accepted(checked.get("accepted_unmeasurable"))
    # Accepting a level of a capability the declaration does not declare would let an
    # undeclared grant pass as accepted (CodeAnt on #364).
    undeclared = sorted(k for k in accepted if k.partition(":")[0] not in bounds)
    if undeclared:
        raise PolicyError(
            f"accepted_unmeasurable names undeclared capabilities: {undeclared}"
        )
    return Policy(
        id=_text(checked["id"], "id"),
        credential_kind=_text(checked["credential_kind"], "credential_kind"),
        max_lifetime_days=lifetime,
        resource_owner=_text(checked["resource_owner"], "resource_owner"),
        repositories=tuple(_text(r, "repository") for r in repositories),
        capabilities=bounds,
        accepted_unmeasurable=accepted,
    )


def _instant(value: str) -> datetime.datetime:
    """Return the time-zone-aware instant ``value`` names."""
    moment = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"{value!r} carries no time zone")
    return moment


def _excess(
    name: str, bound: Bound, read: str | None, write: str | None
) -> tuple[list[str], list[tuple[str, str | None]]]:
    """Return the excess certainly held, and each level not ruled out with its state."""
    maximum = LEVELS.index(bound.maximum)
    certain: list[str] = []
    possible: list[tuple[str, str | None]] = []
    # A write grant includes a read one, so a read refused rules out a write.
    read_refused = read == "NOT_GRANTED"
    if maximum < LEVELS.index("write"):
        if write == "GRANTED":
            certain.append(f"{name}:write")
        elif write != "NOT_GRANTED" and write not in _MOOT and not read_refused:
            possible.append((f"{name}:write", write))
    if maximum < LEVELS.index("read") and write != "GRANTED":
        if read == "GRANTED":
            certain.append(f"{name}:read")
        elif read not in {"NOT_GRANTED", *_MOOT}:
            possible.append((f"{name}:read", read))
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


def _scope(policy: Policy, facts: Facts) -> tuple[list[str], list[str]]:
    """Return writable repositories outside the declaration, and those not ruled out.

    The subject is one of them: checking a repository the declaration does not name
    cannot come back EXACT merely because the probes were aimed at it.
    """
    excess: list[str] = []
    unverified: list[str] = []
    # The subject is the control: a token has one selection and one set of repository
    # permissions, so a probe that detects the grant on the subject tells the
    # selection apart. When it does not, a refusal elsewhere proves nothing.
    controlled = any(
        s.repository == facts.subject and s.state == "GRANTED" for s in facts.scope
    )
    for scoped in facts.scope:
        if scoped.repository in policy.repositories:
            continue
        if scoped.state == "GRANTED":
            excess.append(f"scope:{scoped.repository}")
        elif scoped.state != "NOT_GRANTED" or not controlled:
            unverified.append(f"scope:{scoped.repository}")
    if facts.subject not in {s.repository for s in facts.scope}:
        unverified.append(f"scope:{facts.subject}")
    # The same control bounds the selection: a refused subject means the permission is
    # missing, not that the selection is narrow (CodeAnt on #364).
    if not (facts.selection_bounded and controlled):
        unverified.append("scope:selection")
    return excess, unverified


class _Judgement(NamedTuple):
    """What the observed levels establish against the declared bounds."""

    excess: list[str]
    unverified: list[str]
    accepted: list[str]
    deficient: list[str]
    minimum_unverified: list[str]
    rows: list[dict[str, Any]]
    undeclared: list[str]


def _states(facts: Facts) -> dict[tuple[str, str], str]:
    """Return each observed level's state, refusing a malformed observation."""
    states: dict[tuple[str, str], str] = {}
    for observation in facts.observations:
        if observation.state not in STATES or observation.level not in LEVELS[1:]:
            raise ValueError(f"malformed observation {observation!r}")
        states[(observation.capability, observation.level)] = observation.state
    return states


def _judge(policy: Policy, states: dict[tuple[str, str], str]) -> _Judgement:
    """Judge every capability's observed levels against its declared bound."""
    # An observed capability the policy does not name is held to "none": a grant the
    # declaration did not foresee is excess, never a silent pass.
    observed = set(states)
    undeclared = sorted(
        f"{c}:{level}" for c, level in observed if c not in policy.capabilities
    )
    bounds = {c: Bound("none", "none") for c, _ in observed}
    bounds.update(policy.capabilities)
    judged = _Judgement([], [], [], [], [], [], undeclared)
    for name, bound in sorted(bounds.items()):
        read, write = states.get((name, "read")), states.get((name, "write"))
        certain, possible = _excess(name, bound, read, write)
        missing, unproven = _minimum(name, bound, read, write)
        judged.excess.extend(certain)
        for entry, state in possible:
            if state == "UNMEASURABLE" and entry in policy.accepted_unmeasurable:
                judged.accepted.append(entry)
            else:
                judged.unverified.append(entry)
        judged.deficient.extend(missing)
        judged.minimum_unverified.extend(unproven)
        judged.rows.append(
            {
                "capability": name,
                "declared": {"min": bound.minimum, "max": bound.maximum},
                "read": read,
                "write": write,
            }
        )
    return judged


def evaluate(policy: Policy, facts: Facts, now: str) -> dict[str, Any]:
    """Return the verdict of ``facts`` against ``policy`` at ``now``."""
    judged = _judge(policy, _states(facts))
    excess, unverified = judged.excess, judged.unverified
    accepted, deficient = judged.accepted, judged.deficient
    minimum_unverified, rows, undeclared = (
        judged.minimum_unverified,
        judged.rows,
        judged.undeclared,
    )
    scope_excess, scope_unverified = _scope(policy, facts)
    excess += scope_excess
    unverified += scope_unverified
    if facts.transport[0] != "BOUND":
        unverified.append("transport:push")
    within, remaining = _lifetime(policy, facts.expires_at, now)
    found = {
        "CREDENTIAL_KIND_MISMATCH": facts.credential_kind != policy.credential_kind,
        "EXCESS": bool(excess),
        "DEFICIENT": bool(deficient),
        "LIFETIME_EXCEEDED": not within,
        "UNVERIFIED": bool(unverified),
    }
    reasons = [reason for reason in _PRECEDENCE if found[reason]]
    return {
        "schema": SCHEMA,
        "policy": policy.id,
        "subject": facts.subject,
        "verdict": reasons[0] if reasons else "EXACT",
        "reasons": reasons,
        "credential_kind": {
            "declared": policy.credential_kind,
            "observed": facts.credential_kind,
        },
        "lifetime": {
            "expires_at": facts.expires_at,
            "max_days": policy.max_lifetime_days,
            "remaining_days": remaining,
        },
        "excess": excess,
        "deficient": deficient,
        "unverified": unverified,
        "accepted_unverified": accepted,
        "minimum_unverified": minimum_unverified,
        "undeclared": undeclared,
        "rows": rows,
        "scope": [{"repository": s.repository, "state": s.state} for s in facts.scope],
        "transport": {"state": facts.transport[0], "evidence": facts.transport[1]},
    }
