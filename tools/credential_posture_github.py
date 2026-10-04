"""GitHub's side of the least-privilege check: probes and how their answers are read.

Decision 0101 (#362). GitHub offers no endpoint that lists a fine-grained personal
access token's permissions, so each permission is measured by a probe, and every
probe is non-effecting by construction: a read, or a write whose body the provider
must reject whatever the repository holds -- a ref to an object that cannot exist, an
issue without a title, a deployment review with no valid state -- aimed at a name that
does not exist as well, so neither safeguard rests on the other.

Calibrated on 2026-10-04 against the agents' token (#362):

- Every refusal or rejection carries ``X-Accepted-GitHub-Permissions``: the permission
  sets the route accepts, ``;`` between alternatives and ``,`` within a set. A probe
  whose route no longer names its permission has drifted, and says UNKNOWN.
- A refusal is ``403 Resource not accessible by personal access token``. It says the
  permission is absent only when one alternative is that permission alone: for
  ``pages=write,administration=write`` a refusal may be the administration grant's.
- A grant passes the permission check and the request then fails on its body (422) or,
  on a route a calibrated refusal showed to check first, on its target (404). A pass
  proves the permission only when it appears in every alternative. A lookup can come
  first: ``PATCH`` on a missing gist answered 404 for a token ``POST /gists`` refused.
- A write probe the provider *accepts* broke the construction above and may have
  changed something: the check stops (``ProbeHadEffect``) instead of reading it.

``PERMISSIONS`` is every permission GitHub documents for a token whose resource owner
is a user; each gets an observation at both levels, from a probe or a stated reason.
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


class ProbeHadEffect(RuntimeError):
    """A write probe the provider accepted: it may have changed something."""


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
    path: str  # relative to the API root; ``{repository}``, ``{environment}``, ``{login}``
    body: dict[str, Any] | None
    # The statuses that mean the permission check passed.
    granted_statuses: frozenset[int]
    # A calibrated refusal showed this route checks the permission before the lookup.
    permission_first: bool
    # Why the provider must reject this write whatever the repository holds.
    rejected_body_reason: str = ""
    # The documented field the body gives an array or object of a JSON type it does
    # not accept, and the types it does: request validation refuses that before
    # acting. A bad *value* is not enough -- GitHub cleans up a repository name with
    # disallowed characters instead of rejecting it (gitar on #364) -- and a scalar
    # can be coerced, so the violation is always a container.
    type_violation: tuple[str, frozenset[str]] = ("", frozenset())
    # Or, where the route validates the schema before the permission, the field of a
    # schema-valid body that names an object that cannot exist (the zero SHA).
    impossible_target: str = ""

    @property
    def accepted(self) -> str:
        """The permission the route must name for this probe to be read at all."""
        return f"{self.capability}={self.level}"


def _write(
    pid: str,
    capability: str,
    method: str,
    path: str,
    body: dict[str, Any],
    reason: str,
    violation: tuple[str, str],
    granted: tuple[int, ...] = (422,),
    *,
    permission_first: bool = True,
) -> Probe:
    """Return a write probe whose body ``reason`` says the provider must reject.

    ``violation`` names the field the body breaks and the JSON types it accepts, as
    ``"field", "type|type"``; or, as ``"", "field"``, the schema-valid field that names
    an object that cannot exist.
    """
    field, accepted = violation
    impossible = "" if field else accepted
    if impossible:
        accepted = ""
    return Probe(
        id=pid,
        capability=capability,
        level="write",
        method=method,
        path=path,
        body=body,
        granted_statuses=frozenset(granted),
        permission_first=permission_first,
        rejected_body_reason=reason,
        type_violation=(
            field,
            frozenset(accepted.split("|")) if accepted else frozenset(),
        ),
        impossible_target=impossible,
    )


def _read(pid: str, capability: str, path: str, level: str = "read") -> Probe:
    """Return a read probe; a calibrated refusal showed its route checks first."""
    return Probe(
        id=pid,
        capability=capability,
        level=level,
        method="GET",
        path=path,
        body=None,
        granted_statuses=frozenset({200, 404}),
        permission_first=True,
    )


_REPO = "repos/{repository}"
# The 32 repository and 14 user permissions GitHub documents (docs.github.com,
# "Permissions required for fine-grained personal access tokens", read 2026-10-04), by
# the names `X-Accepted-GitHub-Permissions` gives them.
PERMISSIONS = (
    "actions",
    "administration",
    "agent_secrets",
    "agent_variables",
    "artifact_metadata",
    "attestations",
    "code_quality",
    "security_events",
    "codespaces_lifecycle_admin",
    "codespaces_metadata",
    "codespaces_secrets",
    "codespaces",
    "statuses",
    "contents",
    "copilot_agent_settings",
    "repository_custom_properties",
    "vulnerability_alerts",
    "dependabot_secrets",
    "deployments",
    "environments",
    "installation_repositories",
    "issues",
    "metadata",
    "pages",
    "pull_requests",
    "repository_creation",
    "repository_advisories",
    "secret_scanning_alerts",
    "secrets",
    "actions_variables",
    "repository_hooks",
    "workflows",
    "blocking",
    "codespaces_user_secrets",
    "emails",
    "followers",
    "gpg_keys",
    "gists",
    "keys",
    "interaction_limits",
    "plan",
    "private_repository_invitations",
    "profile",
    "git_signing_ssh_public_keys",
    "starring",
    "watching",
)
# Each refusal below was observed as a 403 for a token lacking the permission, with
# the rejected body shown, so each route checks the permission first.
CATALOGUE: tuple[Probe, ...] = (
    _write(
        "contents-write",
        "contents",
        "POST",
        f"{_REPO}/git/refs",
        # Schema-valid on purpose: this route validates the schema before the
        # permission, so a type-violating ref answers 422 even where the token cannot
        # see the repository (calibrated 2026-10-04) -- the scope probe would read
        # every repository as writable. The zero SHA names an object that cannot exist.
        {"ref": f"refs/heads/{_PROBE}", "sha": _ZERO},
        "a ref to an object that cannot exist",
        ("", "sha"),
        permission_first=False,
    ),
    _write(
        "issues-write",
        "issues",
        "POST",
        f"{_REPO}/issues",
        {"title": [_PROBE], "body": _PROBE},
        "an issue whose title is neither a string nor a number",
        ("title", "string|integer"),
        permission_first=False,
    ),
    _write(
        "pull-requests-write",
        "pull_requests",
        "POST",
        f"{_REPO}/pulls",
        {"title": _PROBE, "head": [_PROBE], "base": [_PROBE]},
        "a pull request whose head and base are not branch names",
        ("head", "string"),
        permission_first=False,
    ),
    _write(
        "statuses-write",
        "statuses",
        "POST",
        f"{_REPO}/statuses/{_ZERO}",
        {"state": [_PROBE], "context": _PROBE},
        "a status with no state, for a commit that cannot exist",
        ("state", "string"),
    ),
    _write(
        "actions-write",
        "actions",
        "POST",
        f"{_REPO}/actions/workflows/{_PROBE}.yml/dispatches",
        {"ref": f"{_PROBE}-none", "inputs": [_PROBE]},
        "a dispatch whose inputs are not an object, of a workflow that cannot exist",
        ("inputs", "object"),
        (404, 422),
    ),
    _write(
        "deployments-write",
        "deployments",
        "POST",
        f"{_REPO}/actions/runs/1/pending_deployments",
        {"environment_ids": {_PROBE: 0}, "state": [_PROBE], "comment": _PROBE},
        "a deployment review whose environment list and state have the wrong type",
        ("environment_ids", "array"),
        (404, 422),
    ),
    _write(
        "administration-write",
        "administration",
        "PUT",
        f"{_REPO}/branches/{_PROBE}/protection",
        {
            "required_status_checks": [_PROBE],
            "enforce_admins": [_PROBE],
            "required_pull_request_reviews": [_PROBE],
            "restrictions": [_PROBE],
        },
        "a protection whose every field has the wrong type, of a branch that cannot exist",
        ("enforce_admins", "boolean|null"),
        (404, 422),
    ),
    _write(
        "attestations-write",
        "attestations",
        "POST",
        f"{_REPO}/attestations",
        {"bundle": [_PROBE]},
        "an attestation whose bundle is not an object",
        ("bundle", "object"),
    ),
    _write(
        "advisories-write",
        "repository_advisories",
        "POST",
        f"{_REPO}/security-advisories",
        {"summary": [_PROBE], "description": [_PROBE], "vulnerabilities": {_PROBE: 0}},
        "an advisory whose summary, description and vulnerabilities have the wrong type",
        ("vulnerabilities", "array|null"),
    ),
    _write(
        "pages-write",
        "pages",
        "POST",
        f"{_REPO}/pages/deployments",
        {"artifact_id": [_PROBE], "pages_build_version": [_PROBE]},
        "a Pages deployment whose artifact and build version have the wrong type",
        ("artifact_id", "integer"),
        (404, 422),
    ),
    _write(
        "repository-creation-write",
        "repository_creation",
        "POST",
        "user/repos",
        {"name": [_PROBE], "private": [_PROBE]},
        "a repository whose name and visibility are not a string and a boolean",
        ("name", "string"),
    ),
    _write(
        "gists-write",
        "gists",
        "POST",
        "gists",
        {"files": [_PROBE], "public": [_PROBE], "description": _PROBE},
        "a gist whose files are not an object",
        ("files", "object"),
        permission_first=False,
    ),
    _write(
        "profile-write",
        "profile",
        "PATCH",
        "user",
        {"hireable": [_PROBE]},
        "a profile field with the wrong type",
        ("hireable", "boolean|null"),
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
    _read("codespaces-read", "codespaces", f"{_REPO}/codespaces?per_page=1"),
    _read(
        "codespaces-metadata-read",
        "codespaces_metadata",
        f"{_REPO}/codespaces/devcontainers?per_page=1",
    ),
    # Listing a repository's codespaces secrets needs the write level.
    _read(
        "codespaces-secrets",
        "codespaces_secrets",
        f"{_REPO}/codespaces/secrets",
        "write",
    ),
    _read("agent-secrets-read", "agent_secrets", f"{_REPO}/agents/secrets"),
    _read("agent-variables-read", "agent_variables", f"{_REPO}/agents/variables"),
    _read("code-quality-read", "code_quality", f"{_REPO}/code-quality/findings"),
    _read(
        "copilot-agent-settings-read",
        "copilot_agent_settings",
        f"{_REPO}/copilot/cloud-agent/configuration",
    ),
    _read(
        "invitations-read",
        "private_repository_invitations",
        f"{_REPO}/invitations",
    ),
    _read("ssh-keys-read", "keys", "user/keys"),
    _read("signing-keys-read", "git_signing_ssh_public_keys", "user/ssh_signing_keys"),
    _read("gpg-keys-read", "gpg_keys", "user/gpg_keys"),
    _read("emails-read", "emails", "user/emails"),
    _read("blocks-read", "blocking", "user/blocks"),
    _read(
        "user-codespaces-secrets-read",
        "codespaces_user_secrets",
        "user/codespaces/secrets",
    ),
    _read("interaction-limits-read", "interaction_limits", "user/interaction-limits"),
    _read("followers-read", "followers", "user/followers?per_page=1"),
    _read("plan-read", "plan", "users/{login}/settings/billing/usage"),
)
# A public repository's data, and a user's public lists, are readable by anyone.
PUBLIC_READS = (
    "contents",
    "issues",
    "pull_requests",
    "actions",
    "statuses",
    "deployments",
    "attestations",
    "metadata",
)
# Levels GitHub documents no endpoint for (the permissions page, read 2026-10-04): a
# grant there reaches nothing. Only these are moot; a level whose endpoints are merely
# out of reach is UNMEASURABLE, for the declaration's owner to accept by name.
_NO_ENDPOINT = "GitHub documents no endpoint at this level"
NOT_APPLICABLE: dict[tuple[str, str], str] = dict.fromkeys(
    (
        ("workflows", "read"),
        ("gists", "read"),
        ("profile", "read"),
        ("codespaces_secrets", "read"),
        ("repository_creation", "read"),
        ("installation_repositories", "read"),
        ("repository_custom_properties", "read"),
        ("code_quality", "write"),
        ("codespaces_metadata", "write"),
        ("copilot_agent_settings", "write"),
        ("plan", "write"),
        ("metadata", "write"),
        ("watching", "write"),
        ("private_repository_invitations", "write"),
    ),
    _NO_ENDPOINT,
)
_LOOKUP_FIRST = "its routes look up their target before the permission"
_ORGANIZATION = "every endpoint is an organization's"
# Levels no non-effecting probe can reach, and why.
UNMEASURABLE: dict[tuple[str, str], str] = {
    ("workflows", "write"): "it is checked only on a change to a workflow file",
    ("codespaces_lifecycle_admin", "read"): _LOOKUP_FIRST,
    ("codespaces_lifecycle_admin", "write"): _LOOKUP_FIRST,
    ("installation_repositories", "write"): _LOOKUP_FIRST,
    ("starring", "write"): _LOOKUP_FIRST,
    ("repository_custom_properties", "write"): _LOOKUP_FIRST,
    ("artifact_metadata", "read"): _ORGANIZATION,
    ("artifact_metadata", "write"): _ORGANIZATION,
    # Each route answers 200 without the grant, leaving the private part out rather
    # than refusing, so no probe tells a grant apart (Codex on #364; calibrated
    # 2026-10-04).
    ("repository_advisories", "read"): "draft and triage advisories are filtered out",
    ("pages", "read"): "a Pages site's private parts are filtered out",
    ("starring", "read"): "private repositories are filtered out of the starred list",
    ("watching", "read"): "private repositories are filtered out of the watched list",
}
# How a write to another repository is probed: the contents-write probe, aimed there.
_SCOPE_PROBE = CATALOGUE[0]
CREDENTIAL_PREFIXES = (
    ("github_pat_", "fine-grained"),
    ("ghp_", "classic"),
    ("gho_", "oauth"),
    ("ghs_", "app-installation"),
    ("ghu_", "app-user"),
)
_EXPIRY = re.compile(r"\A(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) UTC\Z")


def credential_kind(token: str) -> str:
    """Return the kind of ``token`` from its prefix alone."""
    for prefix, kind in CREDENTIAL_PREFIXES:
        if token.startswith(prefix):
            return kind
    return "unknown"


def _accepted_sets(headers: Mapping[str, str]) -> list[frozenset[str]]:
    """Return the accepted permission sets: ``;`` between, ``,`` within."""
    raw = str(headers.get(ACCEPTED_HEADER, "") or "")
    return [
        frozenset(part.strip() for part in alternative.split(",") if part.strip())
        for alternative in raw.split(";")
        if alternative.strip()
    ]


def classify(probe: Probe, answer: Answer) -> tuple[str, str]:
    """Return the state ``answer`` establishes for ``probe``, and the evidence."""
    evidence = f"{probe.method} {probe.id}: {answer.status}"
    if (
        probe.method != "GET"
        and answer.status is not None
        and 200 <= answer.status < 300
    ):
        raise ProbeHadEffect(
            f"the provider accepted the write probe {probe.id}, which it must reject;"
            " it may have had an effect"
        )
    alternatives = _accepted_sets(answer.headers)
    if not any(probe.accepted in alternative for alternative in alternatives):
        return "UNKNOWN", f"{evidence}; the route does not name {probe.accepted}"
    if answer.status == 403 and NOT_ACCESSIBLE in answer.message:
        if frozenset({probe.accepted}) in alternatives:
            return "NOT_GRANTED", evidence
        return "UNMEASURABLE", f"{evidence}; refused, but it needs another grant too"
    if answer.status in probe.granted_statuses:
        if answer.status == 404 and not probe.permission_first:
            return "UNKNOWN", f"{evidence}; a lookup may precede the permission check"
        if all(probe.accepted in alternative for alternative in alternatives):
            return "GRANTED", evidence
        return "UNKNOWN", f"{evidence}; another grant alone would also pass"
    return "UNKNOWN", evidence


def _expiry(headers: Mapping[str, str]) -> str | None:
    """Return the token's expiry as ISO 8601, or None if it has none."""
    match = _EXPIRY.match(str(headers.get(EXPIRY_HEADER, "") or ""))
    if not match:
        return None
    moment = datetime.datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}+00:00")
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _unprobed(
    capability: str, level: str, public_selection: bool, probed: set[str]
) -> Observation:
    """Return the observation for a level no probe in the catalogue measures.

    A repository read is PUBLIC -- moot -- only over a public selection: a read grant
    reaches only the token's selected repositories, so it adds nothing when the
    selection is proven to be the public subject alone.
    """
    if level == "read" and capability in PUBLIC_READS:
        state = "PUBLIC" if public_selection else "UNMEASURABLE"
        return Observation(capability, level, state, "the selection's visibility")
    if (capability, level) in NOT_APPLICABLE:
        return Observation(
            capability, level, "NOT_APPLICABLE", NOT_APPLICABLE[(capability, level)]
        )
    if (capability, level) in UNMEASURABLE:
        return Observation(
            capability, level, "UNMEASURABLE", UNMEASURABLE[(capability, level)]
        )
    if level == "write" and capability in probed:
        # A refused read rules a write out: the core reads it so.
        return Observation(capability, level, "UNMEASURABLE", "implied by the read")
    return Observation(capability, level, "UNMEASURABLE", "no probe")


def observe(
    send: Send,
    *,
    repository: str,
    public: bool,
    environment: str | None,
    visible_repositories: tuple[str, ...],
    login: str,
    token: str,
) -> Facts:
    """Probe the token ``send`` carries and return what the answers establish.

    ``token`` is read for its kind only; it is neither kept nor returned.
    """
    user = send("GET", "user", None)
    # Scope first: whether the selection is the public subject alone decides whether
    # a repository read grant is moot.
    scope = []
    for other in dict.fromkeys((repository, *visible_repositories)):
        path = _SCOPE_PROBE.path.format(repository=other)
        state, evidence = classify(_SCOPE_PROBE, send("POST", path, _SCOPE_PROBE.body))
        scope.append(ScopeObservation(other, state, evidence))
    writable = {s.repository for s in scope if s.state == "GRANTED"}
    public_selection = public and writable == {repository}
    observations: list[Observation] = []
    measured: set[tuple[str, str]] = set()
    read_probed: set[str] = set()
    for probe in CATALOGUE:
        if "{environment}" in probe.path and environment is None:
            continue
        path = probe.path.format(
            repository=repository, environment=environment, login=login
        )
        state, evidence = classify(probe, send(probe.method, path, probe.body))
        observations.append(Observation(probe.capability, probe.level, state, evidence))
        measured.add((probe.capability, probe.level))
        if probe.level == "read":
            read_probed.add(probe.capability)
    for capability in PERMISSIONS:
        for level in ("read", "write"):
            if (capability, level) not in measured:
                observations.append(
                    _unprobed(capability, level, public_selection, read_probed)
                )
    return Facts(
        subject=repository,
        credential_kind=credential_kind(token),
        expires_at=_expiry(user.headers),
        observations=tuple(observations),
        scope=tuple(scope),
    )
