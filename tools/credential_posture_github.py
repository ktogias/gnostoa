"""GitHub's side of the least-privilege check: probes and how their answers are read.

Decision 0101 (#362). GitHub offers no endpoint that lists a fine-grained personal
access token's permissions, so each permission is measured by a probe, and every probe
is non-effecting whatever the answer: a read, or a write aimed at something that cannot
exist, or a creation whose body the provider must reject.

Two facts calibrated on 2026-10-04 against the agents' token decide how an answer is
read:

- Every answer carries ``X-Accepted-GitHub-Permissions``: the permission sets the route
  accepts, ``;`` between alternatives and ``,`` within a set. A probe whose route no
  longer names the permission it was meant to measure has drifted, and says UNKNOWN.
- A refusal is ``403 Resource not accessible by personal access token``. A grant passes
  the permission check and the request then fails on its target: 422 for a rejected
  body, 404 for a missing object. But a lookup can come first: ``PATCH`` on a missing
  gist answered 404 while ``POST /gists`` answered 403 for the same token. So a 404 is
  read as a grant only on a route a calibrated refusal showed to check the permission
  first (``permission_first``); creation routes rejected on their body (422) are read
  as a grant by construction.

Reads of a public repository's data are open to anyone, so their level is PUBLIC, never
probed. ``workflows`` has no non-effecting probe: changing a workflow file is the only
thing it grants, so its write level is UNMEASURABLE and listed as such.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable, Mapping
from typing import Any, NamedTuple

from tools.credential_posture import Facts, Observation, ScopeObservation

NOT_ACCESSIBLE = "Resource not accessible by personal access token"
ACCEPTED_HEADER = "x-accepted-github-permissions"
EXPIRY_HEADER = "github-authentication-token-expiration"
_ZERO = "0" * 40
_PROBE = "zz-credential-probe"


class Answer(NamedTuple):
    """One provider answer: its status (None if none came), headers, message, body."""

    status: int | None
    headers: Mapping[str, str]
    message: str
    document: Any = None


Send = Callable[[str, str, Any], Answer]


class Probe(NamedTuple):
    """One non-effecting request that measures one level of one permission."""

    id: str
    capability: str
    level: str
    method: str
    path: str  # relative to the API root; ``{repository}`` and ``{environment}``
    body: dict[str, Any] | None
    # The statuses that mean the permission check passed.
    granted_statuses: frozenset[int]
    # A calibrated refusal showed this route checks the permission before the lookup.
    permission_first: bool
    # A creation the provider must refuse, and why.
    rejected_body: bool = False
    rejected_body_reason: str = ""

    @property
    def accepted(self) -> str:
        """The permission the route must name for this probe to be read at all."""
        return f"{self.capability}={self.level}"


def _write(
    pid: str,
    capability: str,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    granted: tuple[int, ...],
    *,
    permission_first: bool = True,
    rejected_body_reason: str = "",
) -> Probe:
    return Probe(
        id=pid,
        capability=capability,
        level="write",
        method=method,
        path=path,
        body=body,
        granted_statuses=frozenset(granted),
        permission_first=permission_first,
        rejected_body=bool(rejected_body_reason),
        rejected_body_reason=rejected_body_reason,
    )


def _read(pid: str, capability: str, path: str) -> Probe:
    return Probe(
        id=pid,
        capability=capability,
        level="read",
        method="GET",
        path=path,
        body=None,
        granted_statuses=frozenset({200, 404}),
        permission_first=True,
    )


_REPO = "repos/{repository}"
# Calibrated on 2026-10-04 (#362): each refusal below was observed as a 403 for a token
# lacking the permission, so each route checks the permission first.
CATALOGUE: tuple[Probe, ...] = (
    _write(
        "contents-write",
        "contents",
        "POST",
        f"{_REPO}/git/refs",
        {"ref": f"refs/heads/{_PROBE}", "sha": _ZERO},
        (422,),
        permission_first=False,
    ),
    _write(
        "issues-write",
        "issues",
        "POST",
        f"{_REPO}/issues",
        {"body": _PROBE},
        (422,),
        permission_first=False,
        rejected_body_reason="an issue without a title",
    ),
    _write(
        "pull-requests-write",
        "pull_requests",
        "POST",
        f"{_REPO}/pulls",
        {"title": _PROBE, "head": f"{_PROBE}-none", "base": f"{_PROBE}-none"},
        (422,),
        permission_first=False,
        rejected_body_reason="a pull request between branches that do not exist",
    ),
    _write(
        "statuses-write",
        "statuses",
        "POST",
        f"{_REPO}/statuses/{_ZERO}",
        {"state": "pending", "context": _PROBE},
        (422,),
    ),
    _write(
        "actions-write",
        "actions",
        "POST",
        f"{_REPO}/actions/workflows/{_PROBE}.yml/dispatches",
        {"ref": f"{_PROBE}-none"},
        (404, 422),
    ),
    _write(
        "deployments-write",
        "deployments",
        "POST",
        f"{_REPO}/actions/runs/1/pending_deployments",
        {"environment_ids": [1], "state": "rejected", "comment": _PROBE},
        (404, 422),
    ),
    _write(
        "administration-write",
        "administration",
        "PUT",
        f"{_REPO}/branches/{_PROBE}/protection",
        {
            "required_status_checks": None,
            "enforce_admins": False,
            "required_pull_request_reviews": None,
            "restrictions": None,
        },
        (404, 422),
    ),
    _write(
        "gists-write",
        "gists",
        "POST",
        "gists",
        {"files": {}, "public": False, "description": _PROBE},
        (422,),
        permission_first=False,
        rejected_body_reason="a gist with no files",
    ),
    _read("administration-read", "administration", f"{_REPO}/branches/main/protection"),
    _read("secrets-read", "secrets", f"{_REPO}/actions/secrets"),
    _read("variables-read", "actions_variables", f"{_REPO}/actions/variables"),
    _read("hooks-read", "repository_hooks", f"{_REPO}/hooks"),
    _read(
        "environments-read",
        "environments",
        f"{_REPO}/environments/{{environment}}/secrets",
    ),
    _read(
        "dependabot-secrets-read", "dependabot_secrets", f"{_REPO}/dependabot/secrets"
    ),
    _read(
        "code-scanning-read",
        "security_events",
        f"{_REPO}/code-scanning/alerts?per_page=1",
    ),
    _read(
        "secret-scanning-read",
        "secret_scanning_alerts",
        f"{_REPO}/secret-scanning/alerts?per_page=1",
    ),
    _read(
        "dependabot-alerts-read",
        "vulnerability_alerts",
        f"{_REPO}/dependabot/alerts?per_page=1",
    ),
    _read("ssh-keys-read", "keys", "user/keys"),
    _read("signing-keys-read", "git_signing_ssh_public_keys", "user/ssh_signing_keys"),
    _read("gpg-keys-read", "gpg_keys", "user/gpg_keys"),
    _read("emails-read", "emails", "user/emails"),
)
# A public repository's data is readable by anyone, so these reads are PUBLIC.
PUBLIC_READS = (
    "contents",
    "issues",
    "pull_requests",
    "actions",
    "statuses",
    "deployments",
)
# Levels GitHub does not define for the capability.
NOT_APPLICABLE = (("workflows", "read"), ("gists", "read"))
# Levels no non-effecting probe can reach.
UNMEASURABLE = (("workflows", "write"),)
# How a write to another repository is probed: the contents-write probe, aimed there.
_SCOPE_PROBE = CATALOGUE[0]
_KINDS = (
    ("github_pat_", "fine-grained"),
    ("ghp_", "classic"),
    ("gho_", "oauth"),
    ("ghs_", "app-installation"),
    ("ghu_", "app-user"),
)
_EXPIRY = re.compile(r"\A(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) UTC\Z")


def token_kind(token: str) -> str:
    """Return the kind of ``token`` from its prefix alone."""
    for prefix, kind in _KINDS:
        if token.startswith(prefix):
            return kind
    return "unknown"


def _accepted_sets(headers: Mapping[str, str]) -> list[set[str]]:
    raw = str(headers.get(ACCEPTED_HEADER, "") or "")
    return [
        {part.strip() for part in alternative.split(",") if part.strip()}
        for alternative in raw.split(";")
        if alternative.strip()
    ]


def classify(probe: Probe, answer: Answer) -> tuple[str, str]:
    """Return the state ``answer`` establishes for ``probe``, and the evidence."""
    named = any(
        probe.accepted in alternative for alternative in _accepted_sets(answer.headers)
    )
    evidence = f"{probe.method} {probe.id}: {answer.status}"
    if not named:
        return "UNKNOWN", f"{evidence}; the route does not name {probe.accepted}"
    if answer.status == 403 and NOT_ACCESSIBLE in answer.message:
        return "NOT_GRANTED", evidence
    if answer.status in probe.granted_statuses:
        if answer.status == 404 and not probe.permission_first:
            return "UNKNOWN", f"{evidence}; a lookup may precede the permission check"
        return "GRANTED", evidence
    return "UNKNOWN", evidence


def _expiry(headers: Mapping[str, str]) -> str | None:
    match = _EXPIRY.match(str(headers.get(EXPIRY_HEADER, "") or ""))
    if not match:
        return None
    moment = datetime.datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}+00:00")
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def observe(
    send: Send,
    *,
    repository: str,
    public: bool,
    environment: str | None,
    owned_repositories: tuple[str, ...],
    token: str,
) -> Facts:
    """Probe the token ``send`` carries and return what the answers establish.

    ``token`` is read for its kind only; it is neither kept nor returned.
    """
    user = send("GET", "user", None)
    observations: list[Observation] = []
    for probe in CATALOGUE:
        if "{environment}" in probe.path and environment is None:
            observations.append(
                Observation(
                    probe.capability, probe.level, "UNMEASURABLE", "no environment"
                )
            )
            continue
        path = probe.path.format(repository=repository, environment=environment)
        state, evidence = classify(probe, send(probe.method, path, probe.body))
        observations.append(Observation(probe.capability, probe.level, state, evidence))
    for capability in PUBLIC_READS:
        state = "PUBLIC" if public else "UNMEASURABLE"
        observations.append(
            Observation(capability, "read", state, "repository visibility")
        )
    for capability, level in NOT_APPLICABLE:
        observations.append(
            Observation(capability, level, "NOT_APPLICABLE", "not defined")
        )
    for capability, level in UNMEASURABLE:
        observations.append(Observation(capability, level, "UNMEASURABLE", "no probe"))
    scope = []
    for other in owned_repositories:
        if other == repository:
            continue
        path = _SCOPE_PROBE.path.format(repository=other)
        state, evidence = classify(_SCOPE_PROBE, send("POST", path, _SCOPE_PROBE.body))
        scope.append(ScopeObservation(other, state, evidence))
    return Facts(
        token_kind=token_kind(token),
        expires_at=_expiry(user.headers),
        observations=tuple(observations),
        scope=tuple(scope),
    )
