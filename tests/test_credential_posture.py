"""Least-privilege verification of an agent's provider token (#362, Decision 0101).

The core decides from probe observations alone; the GitHub adapter turns each probe's
answer into an observation; the CLI composes them. Every provider answer here is a
replay of the calibration made against the agents' token on 2026-10-04 (#362), so a
test that passes does not rest on an answer the provider would not give.
"""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import tempfile
import unittest
from typing import Any
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy" / "agent-credentials.yaml"
NOW = "2026-10-04T12:00:00Z"
NOT_ACCESSIBLE = "Resource not accessible by personal access token"
SUBJECT = "ktogias/gnostoa"
VISIBLE = (SUBJECT, "ktogias/ai-peaf", "ktogias/elsewhere", "someorg/shared")
# The listing of every repository the token can see, whoever owns it.
REPOS = "user/repos?per_page=100"

# Every fine-grained personal access token permission GitHub documents for a token
# whose resource owner is a user, as `X-Accepted-GitHub-Permissions` names them
# (docs.github.com, "Permissions required for fine-grained personal access tokens",
# read 2026-10-04): 32 repository permissions and 14 user permissions.
DOCUMENTED_PERMISSIONS = frozenset(
    {
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
    }
)


# The levels for which that page documents no endpoint at all, read the same day. Only
# these may be NOT_APPLICABLE: a level reachable only through an organization, or
# answered by a lookup first, is UNMEASURABLE and must be accepted by name.
UNDOCUMENTED_LEVELS = frozenset(
    {
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
    }
)


def _policy_document(**change: Any) -> dict[str, Any]:
    document = {
        "id": "test-agent-credentials",
        "version": "1.0",
        "credential_kind": "fine-grained",
        "max_lifetime_days": 31,
        "resource_owner": "o",
        "repositories": ["o/r"],
        "capabilities": {
            "contents": {"min": "write", "max": "write"},
            "workflows": {"min": "write", "max": "write"},
            "actions": {"min": "read", "max": "read"},
            "deployments": {"min": "none", "max": "none"},
            "administration": {"min": "none", "max": "none"},
            "pages": {"min": "none", "max": "none"},
        },
    }
    document.update(change)
    return document


def _observations(**states: str) -> tuple[Any, ...]:
    """Observations for the test policy, overridden per ``capability_level`` key."""
    from tools import credential_posture as posture

    # A public repository's data is readable without any grant, so its read level is
    # PUBLIC: a read grant there neither adds anything nor can be told apart. A level
    # the provider does not have (workflows and gists are write-only) is NOT_APPLICABLE.
    base = {
        "contents_write": "GRANTED",
        "contents_read": "PUBLIC",
        "workflows_write": "UNMEASURABLE",
        "workflows_read": "NOT_APPLICABLE",
        "actions_write": "NOT_GRANTED",
        "actions_read": "PUBLIC",
        "deployments_write": "NOT_GRANTED",
        "deployments_read": "PUBLIC",
        "administration_write": "NOT_GRANTED",
        "administration_read": "NOT_GRANTED",
        "pages_write": "NOT_GRANTED",
        "pages_read": "PUBLIC",
    }
    base.update(states)
    return tuple(
        posture.Observation(key.rsplit("_", 1)[0], key.rsplit("_", 1)[1], state, "e")
        for key, state in base.items()
    )


def _facts(**overrides: Any) -> Any:
    from tools import credential_posture as posture

    fields: dict[str, Any] = {
        "subject": "o/r",
        "credential_kind": "fine-grained",
        "expires_at": "2026-11-03T13:01:27Z",
        "observations": _observations(),
        "scope": (
            posture.ScopeObservation("o/r", "GRANTED", "e"),
            posture.ScopeObservation("o/other", "NOT_GRANTED", "e"),
        ),
    }
    fields.update(overrides)
    return posture.Facts(**fields)


def _placeholder_token(kind: str, tail: str = "placeholder") -> str:
    """A token of ``kind``'s shape, built from the adapter's own prefix table: no
    credential-like literal lives in this file."""
    from tools import credential_posture_github as github

    prefix = {k: p for p, k in github.CREDENTIAL_PREFIXES}[kind]
    return prefix + tail


def _probe(capability: str) -> Any:
    """The catalogue's one probe for ``capability``."""
    from tools import credential_posture_github as github

    probes = [p for p in github.CATALOGUE if p.capability == capability]
    if len(probes) != 1:
        raise AssertionError(f"{capability} has {len(probes)} probes")
    return probes[0]


def _verdict(facts: Any, **policy: Any) -> dict[str, Any]:
    """The verdict of ``facts`` against the test policy."""
    from tools import credential_posture as posture

    return posture.evaluate(posture.load_policy(_policy_document(**policy)), facts, NOW)


_UNEXPECTED = object()


def _catalogue_bodies() -> dict[tuple[str, str], Any]:
    """Each write route the check may send to, with the body it must carry."""
    from tools import credential_posture_github as github

    bodies: dict[tuple[str, str], Any] = {}
    for probe in github.CATALOGUE:
        if probe.method != "GET":
            path = probe.path.format(
                repository=SUBJECT, environment="", login="ktogias"
            )
            bodies[(probe.method, path)] = probe.body
    scope = github._SCOPE_PROBE  # skipcq: PYL-W0212
    for name in VISIBLE:
        bodies[("POST", scope.path.format(repository=name))] = scope.body
    return bodies


class _Replay:
    """A provider that answers each (method, path) from the calibration, and refuses
    anything else -- so a probe outside the catalogue is a test failure, not a pass."""

    def __init__(
        self,
        answers: dict[tuple[str, str], tuple[int, str, str]],
        listing: dict[str, tuple[list[str], str | None]] | None = None,
        private: frozenset[str] = frozenset(),
    ) -> None:
        self.answers = answers
        self.private = private
        # Each page of the repository listing: its names, and the page its `Link`
        # header names next.
        self.listing = listing or {REPOS: (list(VISIBLE), None)}
        self.sent: list[tuple[str, str, Any]] = []

    def __call__(self, method: str, path: str, body: Any) -> Any:
        from tools import credential_posture_github as github
        from tools import github_rest

        # A followed page arrives as the absolute URL its `Link` header named.
        path = path.removeprefix(f"{github_rest.API_ROOT}/")
        self.sent.append((method, path, body))
        # A write is answered only if it carries the catalogue's body for its route:
        # the provider would treat any other body differently, so neither does this
        # double (CodeAnt on #364).
        if method != "GET" and body != _catalogue_bodies().get(
            (method, path), _UNEXPECTED
        ):
            raise AssertionError(
                f"{method} {path} sent {body!r}, not its catalogue body"
            )
        if (method, path) not in self.answers:
            raise AssertionError(f"unexpected probe {method} {path}")
        status, accepted, message = self.answers[(method, path)]
        headers = {"x-accepted-github-permissions": accepted} if accepted else {}
        if message.startswith("OUTCOME-UNKNOWN"):
            # A write that reached the provider and was not refused: the shared
            # client reports its outcome as unknown.
            return github.Answer(status, headers, message, None, outcome_unknown=True)
        if path == "user":
            headers["github-authentication-token-expiration"] = (
                "2026-11-03 13:01:27 UTC"
            )
        if path in self.listing:
            names, following = self.listing[path]
            if following is not None:
                headers["link"] = f'<{github_rest.API_ROOT}/{following}>; rel="next"'
            listed = [
                {"full_name": name, "private": name in self.private} for name in names
            ]
            return github.Answer(status, headers, message, listed)
        document = {
            "user": {"login": "ktogias"},
            f"repos/{SUBJECT}": {"private": False},
            f"repos/{SUBJECT}/environments": {
                "environments": [{"name": "claude-review"}]
            },
        }.get(path)
        return github.Answer(status, headers, message, document)


def _calibrated() -> dict[tuple[str, str], tuple[int, str, str]]:
    """The answers observed for the agents' token on 2026-10-04 (#362)."""
    r = f"repos/{SUBJECT}"
    zero = "0" * 40
    no = NOT_ACCESSIBLE
    answers: dict[tuple[str, str], tuple[int, str, str]] = {
        ("GET", "user"): (200, "", ""),
        ("GET", r): (200, "metadata=read", ""),
        ("GET", f"{r}/environments"): (200, "actions=read", ""),
        ("GET", REPOS): (200, "metadata=read", ""),
        # Writes the provider must reject whatever the repository holds.
        ("POST", f"{r}/git/refs"): (
            422,
            "contents=write;contents=write,workflows=write",
            "Object does not exist",
        ),
        ("POST", f"{r}/issues"): (422, "issues=write", "Invalid request."),
        ("POST", f"{r}/pulls"): (422, "pull_requests=write", "Invalid request."),
        ("POST", f"{r}/statuses/{zero}"): (403, "statuses=write", no),
        ("POST", f"{r}/actions/workflows/zz-credential-probe.yml/dispatches"): (
            403,
            "actions=write",
            no,
        ),
        ("POST", f"{r}/actions/runs/1/pending_deployments"): (
            403,
            "deployments=write",
            no,
        ),
        ("PUT", f"{r}/branches/zz-credential-probe/protection"): (
            403,
            "administration=write",
            no,
        ),
        ("POST", f"{r}/attestations"): (403, "attestations=write", no),
        ("POST", f"{r}/security-advisories"): (403, "repository_advisories=write", no),
        ("POST", f"{r}/pages/deployments"): (403, "pages=write", no),
        ("POST", "user/repos"): (
            403,
            "administration=write;repository_creation=write",
            no,
        ),
        ("POST", "gists"): (403, "gists=write", no),
        ("PATCH", "user"): (403, "profile=write", no),
        # Reads that a grant would answer and its absence refuses.
        ("GET", f"{r}/branches/main/protection"): (403, "administration=read", no),
        ("GET", f"{r}/actions/secrets"): (403, "secrets=read", no),
        ("GET", f"{r}/actions/variables"): (403, "actions_variables=read", no),
        ("GET", f"{r}/hooks"): (403, "repository_hooks=read", no),
        ("GET", f"{r}/environments/claude-review/secrets"): (
            403,
            "environments=read",
            no,
        ),
        ("GET", f"{r}/dependabot/secrets"): (403, "dependabot_secrets=read", no),
        ("GET", f"{r}/code-scanning/alerts?per_page=1"): (
            403,
            "security_events=read",
            no,
        ),
        ("GET", f"{r}/secret-scanning/alerts?per_page=1"): (
            403,
            "secret_scanning_alerts=read",
            no,
        ),
        ("GET", f"{r}/dependabot/alerts?per_page=1"): (
            403,
            "vulnerability_alerts=read",
            no,
        ),
        ("GET", f"{r}/codespaces?per_page=1"): (403, "codespaces=read", no),
        ("GET", f"{r}/codespaces/devcontainers?per_page=1"): (
            403,
            "codespaces_metadata=read",
            no,
        ),
        ("GET", f"{r}/codespaces/secrets"): (403, "codespaces_secrets=write", no),
        ("GET", f"{r}/agents/secrets"): (403, "agent_secrets=read", no),
        ("GET", f"{r}/agents/variables"): (403, "agent_variables=read", no),
        ("GET", f"{r}/code-quality/findings"): (403, "code_quality=read", no),
        ("GET", f"{r}/copilot/cloud-agent/configuration"): (
            403,
            "copilot_agent_settings=read",
            no,
        ),
        ("GET", f"{r}/invitations"): (
            403,
            "administration=read;private_repository_invitations=read",
            no,
        ),
        ("GET", "user/keys"): (403, "keys=read", no),
        ("GET", "user/ssh_signing_keys"): (403, "git_signing_ssh_public_keys=read", no),
        ("GET", "user/gpg_keys"): (403, "gpg_keys=read", no),
        ("GET", "user/emails"): (403, "emails=read", no),
        ("GET", "user/blocks"): (403, "blocking=read", no),
        ("GET", "user/codespaces/secrets"): (403, "codespaces_user_secrets=read", no),
        ("GET", "user/interaction-limits"): (403, "interaction_limits=read", no),
        ("GET", "user/followers?per_page=1"): (403, "followers=read", no),
        ("GET", "users/ktogias/settings/billing/usage"): (403, "plan=read", no),
    }
    # Scope: the contents-write probe, aimed at every repository the token can see.
    contents = "contents=write;contents=write,workflows=write"
    answers[("POST", "repos/ktogias/ai-peaf/git/refs")] = (
        422,
        contents,
        "Object does not exist",
    )
    for other in ("ktogias/elsewhere", "someorg/shared"):
        answers[("POST", f"repos/{other}/git/refs")] = (403, contents, no)
    return answers


def _calibrated_exact() -> dict[tuple[str, str], tuple[int, str, str]]:
    """The calibration after the owner removed the extra repository from the token."""
    answers = _calibrated()
    answers[("POST", "repos/ktogias/ai-peaf/git/refs")] = (
        403,
        "contents=write;contents=write,workflows=write",
        NOT_ACCESSIBLE,
    )
    return answers


def _observe(answers: dict[tuple[str, str], tuple[int, str, str]]) -> Any:
    """What the adapter establishes from ``answers``."""
    from tools import credential_posture_github as github

    return github.observe(
        _Replay(answers),
        repository=SUBJECT,
        public=True,
        environment="claude-review",
        visible_repositories=VISIBLE,
        login="ktogias",
        token=_placeholder_token("fine-grained"),
    )


def _state(facts: Any, capability: str, level: str) -> str:
    """The one state observed for ``capability`` at ``level``."""
    states = [
        o.state
        for o in facts.observations
        if (o.capability, o.level) == (capability, level)
    ]
    if len(states) != 1:
        raise AssertionError(f"{capability}:{level} was observed {len(states)} times")
    return str(states[0])


@contextlib.contextmanager
def _working_directory(path: pathlib.Path) -> Any:
    """Run inside ``path``: the declaration is confined to the working tree."""
    previous = pathlib.Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _run(
    answers: dict[tuple[str, str], tuple[int, str, str]],
    *arguments: str,
    policy: str | None = None,
    cwd: pathlib.Path = ROOT,
    listing: dict[str, tuple[list[str], str | None]] | None = None,
    private: frozenset[str] = frozenset(),
) -> tuple[int, str, Any]:
    """Run the command over ``answers`` from ``cwd``, naming the declaration."""
    from tools import credential_check

    replay = _Replay(answers, listing, private)
    out = io.StringIO()
    argv = list(arguments) or ["--repository", SUBJECT]
    argv += ["--policy", policy or str(POLICY), "--json"]
    with (
        _working_directory(cwd),
        mock.patch.object(
            credential_check,
            "_token",
            return_value=_placeholder_token("fine-grained", "SECRETVALUE"),
        ),
        mock.patch.object(credential_check, "_transport", return_value=replay),
        mock.patch.object(credential_check, "utc_timestamp", return_value=NOW),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(out),
    ):
        code = credential_check.main(argv)
    return code, out.getvalue(), replay


class CorePolicyTests(unittest.TestCase):
    """The declaration is validated before anything is judged against it."""

    def test_a_valid_policy_loads(self) -> None:
        from tools import credential_posture as posture

        policy = posture.load_policy(_policy_document())
        self.assertEqual(("o/r",), policy.repositories)
        self.assertEqual("write", policy.capabilities["contents"].maximum)

    def test_a_malformed_policy_is_refused(self) -> None:
        from tools import credential_posture as posture

        cases = {
            "an unknown key": _policy_document(extra=1),
            "a minimum above its maximum": _policy_document(
                capabilities={"contents": {"min": "write", "max": "read"}}
            ),
            "an unknown level": _policy_document(
                capabilities={"contents": {"min": "x", "max": "write"}}
            ),
            "a lifetime that is not a positive integer": _policy_document(
                max_lifetime_days=0
            ),
            "no repositories": _policy_document(repositories=[]),
            "an acceptance without a reason": _policy_document(
                accepted_unmeasurable={"pages:write": ""}
            ),
            "an acceptance of no level": _policy_document(
                accepted_unmeasurable={"pages": "a reason"}
            ),
            # Accepting a level of a capability the declaration does not declare would
            # let an undeclared grant pass as accepted (CodeAnt on #364).
            "an acceptance of an undeclared capability": _policy_document(
                accepted_unmeasurable={"codespaces:write": "a reason"}
            ),
        }
        for name, document in cases.items():
            with self.subTest(case=name), self.assertRaises(posture.PolicyError):
                posture.load_policy(document)

    def test_the_repository_policy_declares_every_documented_permission(self) -> None:
        """Exact means exact over every permission the provider can grant: the
        declaration names each one, and channel C's essence is among them."""
        from tools import credential_posture as posture
        from tools import knowledge_common

        policy = posture.load_policy(knowledge_common.load_yaml(POLICY))
        self.assertEqual(DOCUMENTED_PERMISSIONS, set(policy.capabilities))
        for forbidden in ("deployments", "administration", "environments", "secrets"):
            with self.subTest(capability=forbidden):
                self.assertEqual("none", policy.capabilities[forbidden].maximum)
        self.assertEqual("read", policy.capabilities["actions"].maximum)


class CoreVerdictTests(unittest.TestCase):
    """The verdict says whether the token holds exactly the declared grants."""

    def test_the_calibrated_token_is_exact(self) -> None:
        """The minimum it cannot measure (workflows write) is listed, not passed off:
        a missing grant reveals itself when used, an excess one never does."""
        verdict = _verdict(_facts())
        self.assertEqual("EXACT", verdict["verdict"])
        self.assertEqual(["workflows:write"], verdict["minimum_unverified"])
        self.assertEqual([], verdict["excess"])

    def test_a_forbidden_grant_is_excess(self) -> None:
        verdict = _verdict(
            _facts(observations=_observations(deployments_write="GRANTED"))
        )
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("deployments:write", verdict["excess"])

    def test_a_level_above_the_declared_maximum_is_excess(self) -> None:
        verdict = _verdict(_facts(observations=_observations(actions_write="GRANTED")))
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("actions:write", verdict["excess"])

    def test_a_forbidden_read_is_excess(self) -> None:
        verdict = _verdict(
            _facts(observations=_observations(administration_read="GRANTED"))
        )
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("administration:read", verdict["excess"])

    def test_a_missing_required_grant_is_deficient(self) -> None:
        verdict = _verdict(
            _facts(observations=_observations(contents_write="NOT_GRANTED"))
        )
        self.assertEqual("DEFICIENT", verdict["verdict"])
        self.assertIn("contents:write", verdict["deficient"])

    def test_an_unanswered_probe_for_a_forbidden_grant_is_unverified(self) -> None:
        """Excess must be disproven: an answer that cannot be read leaves it open."""
        verdict = _verdict(
            _facts(observations=_observations(deployments_write="UNKNOWN"))
        )
        self.assertEqual("UNVERIFIED", verdict["verdict"])
        self.assertIn("deployments:write", verdict["unverified"])

    def test_a_forbidden_grant_no_probe_can_measure_is_unverified(self) -> None:
        verdict = _verdict(
            _facts(observations=_observations(deployments_write="UNMEASURABLE"))
        )
        self.assertEqual("UNVERIFIED", verdict["verdict"])

    def test_an_accepted_unmeasurable_level_is_listed_not_failed(self) -> None:
        """A level no probe can reach can be accepted, with a reason, by the
        declaration's owner; it is listed, and only an UNMEASURABLE one qualifies --
        an unanswered probe is never accepted away."""
        accepted = {"pages:write": "needs administration too, which is refused"}
        verdict = _verdict(
            _facts(observations=_observations(pages_write="UNMEASURABLE")),
            accepted_unmeasurable=accepted,
        )
        self.assertEqual("EXACT", verdict["verdict"])
        self.assertEqual(["pages:write"], verdict["accepted_unverified"])
        unanswered = _verdict(
            _facts(observations=_observations(pages_write="UNKNOWN")),
            accepted_unmeasurable=accepted,
        )
        self.assertEqual("UNVERIFIED", unanswered["verdict"])

    def test_a_writable_repository_outside_the_scope_is_excess(self) -> None:
        from tools import credential_posture as posture

        verdict = _verdict(
            _facts(
                scope=(
                    posture.ScopeObservation("o/r", "GRANTED", "e"),
                    posture.ScopeObservation("o/other", "GRANTED", "e"),
                )
            )
        )
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("scope:o/other", verdict["excess"])

    def test_scope_counts_only_when_the_subject_proves_the_control_grant(self) -> None:
        """A token has one repository selection and one set of repository permissions,
        so one write probe identifies the selection -- but only if it detects the grant
        on the subject. When it does not, a refusal elsewhere proves nothing, and every
        other repository's scope is unverified (CodeAnt on #364)."""
        from tools import credential_posture as posture

        for control in ("NOT_GRANTED", "UNKNOWN"):
            with self.subTest(control=control):
                verdict = _verdict(
                    _facts(
                        scope=(
                            posture.ScopeObservation("o/r", control, "e"),
                            posture.ScopeObservation("o/other", "NOT_GRANTED", "e"),
                        )
                    )
                )
                self.assertIn("scope:o/other", verdict["unverified"])
                self.assertNotEqual("EXACT", verdict["verdict"])

    def test_a_subject_outside_the_declaration_is_excess(self) -> None:
        """Checking a repository the declaration does not name cannot come back
        EXACT: its own writability is scope excess (gitar, Codex, CodeAnt, CodeRabbit
        on #364)."""
        from tools import credential_posture as posture

        verdict = _verdict(
            _facts(
                subject="o/undeclared",
                scope=(
                    posture.ScopeObservation("o/undeclared", "GRANTED", "e"),
                    posture.ScopeObservation("o/r", "GRANTED", "e"),
                ),
            )
        )
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("scope:o/undeclared", verdict["excess"])

    def test_the_kind_and_lifetime_are_part_of_the_verdict(self) -> None:
        cases = {
            "another kind": (
                _facts(credential_kind="oauth"),
                "CREDENTIAL_KIND_MISMATCH",
            ),
            "no expiry": (_facts(expires_at=None), "LIFETIME_EXCEEDED"),
            "a year": (_facts(expires_at="2027-10-04T12:00:00Z"), "LIFETIME_EXCEEDED"),
            "already expired": (
                _facts(expires_at="2026-10-01T00:00:00Z"),
                "LIFETIME_EXCEEDED",
            ),
        }
        for name, (facts, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(expected, _verdict(facts)["verdict"])

    def test_an_undeclared_grant_is_excess(self) -> None:
        """A grant the declaration did not foresee is held to none: excess, not a
        silent pass."""
        from tools import credential_posture as posture

        extra = (
            *_observations(),
            posture.Observation("codespaces", "write", "GRANTED", "e"),
        )
        verdict = _verdict(_facts(observations=extra))
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("codespaces:write", verdict["excess"])
        self.assertIn("codespaces:write", verdict["undeclared"])

    def test_the_precedence_puts_the_most_dangerous_first(self) -> None:
        verdict = _verdict(
            _facts(
                credential_kind="oauth",
                observations=_observations(
                    deployments_write="GRANTED", contents_write="NOT_GRANTED"
                ),
            )
        )
        self.assertEqual("CREDENTIAL_KIND_MISMATCH", verdict["verdict"])
        self.assertEqual(
            ["CREDENTIAL_KIND_MISMATCH", "EXCESS", "DEFICIENT"], verdict["reasons"]
        )


class GitHubAdapterTests(unittest.TestCase):
    """Each answer becomes an observation by the rule it was calibrated against."""

    def test_the_calibration_is_read_as_observed(self) -> None:
        facts = _observe(_calibrated_exact())
        self.assertEqual(SUBJECT, facts.subject)
        self.assertEqual("fine-grained", facts.credential_kind)
        self.assertEqual("2026-11-03T13:01:27Z", facts.expires_at)
        for capability, level, state in (
            ("contents", "write", "GRANTED"),
            ("contents", "read", "PUBLIC"),
            ("issues", "write", "GRANTED"),
            ("pull_requests", "write", "GRANTED"),
            ("workflows", "write", "UNMEASURABLE"),
            ("workflows", "read", "NOT_APPLICABLE"),
            ("actions", "write", "NOT_GRANTED"),
            ("actions", "read", "PUBLIC"),
            ("statuses", "write", "NOT_GRANTED"),
            ("deployments", "write", "NOT_GRANTED"),
            ("deployments", "read", "PUBLIC"),
            ("administration", "write", "NOT_GRANTED"),
            ("administration", "read", "NOT_GRANTED"),
            ("secrets", "read", "NOT_GRANTED"),
            ("environments", "read", "NOT_GRANTED"),
            ("gists", "write", "NOT_GRANTED"),
            ("repository_creation", "write", "NOT_GRANTED"),
            ("private_repository_invitations", "read", "NOT_GRANTED"),
            ("pages", "write", "NOT_GRANTED"),
            ("installation_repositories", "write", "UNMEASURABLE"),
            ("artifact_metadata", "write", "UNMEASURABLE"),
            ("repository_custom_properties", "read", "NOT_APPLICABLE"),
            ("watching", "write", "NOT_APPLICABLE"),
            ("git_signing_ssh_public_keys", "read", "NOT_GRANTED"),
        ):
            with self.subTest(capability=capability, level=level):
                self.assertEqual(state, _state(facts, capability, level))
        self.assertEqual(
            {
                SUBJECT: "GRANTED",
                "ktogias/ai-peaf": "NOT_GRANTED",
                "ktogias/elsewhere": "NOT_GRANTED",
                "someorg/shared": "NOT_GRANTED",
            },
            {s.repository: s.state for s in facts.scope},
        )

    def test_a_read_is_public_only_over_a_proven_public_selection(self) -> None:
        """A repository read grant reaches only the token's selection, so it adds
        nothing when the selection is proven to be the public subject alone. With
        another repository writable -- or the subject not -- the selection is not
        known, and a read grant there is not moot."""
        exact = _observe(_calibrated_exact())
        widened = _observe(_calibrated())
        for capability in ("contents", "actions", "deployments", "statuses"):
            with self.subTest(capability=capability):
                self.assertEqual("PUBLIC", _state(exact, capability, "read"))
                self.assertEqual("UNMEASURABLE", _state(widened, capability, "read"))

    def test_a_visible_private_repository_makes_repository_reads_count(self) -> None:
        """A fine-grained token sees a private repository only when it is in the
        selection, so one in the listing is a repository the token can read: with it,
        a repository read grant is not moot, whether or not the write probe got
        through (CodeAnt on #364)."""
        from tools import credential_posture_github as github

        facts = github.observe(
            _Replay(_calibrated_exact()),
            repository=SUBJECT,
            public=True,
            environment="claude-review",
            visible_repositories=VISIBLE,
            login="ktogias",
            token=_placeholder_token("fine-grained"),
            private_repositories=frozenset({"ktogias/elsewhere"}),
        )
        self.assertEqual("UNMEASURABLE", _state(facts, "deployments", "read"))
        code, output, _ = _run(
            _calibrated_exact(), private=frozenset({"ktogias/elsewhere"})
        )
        self.assertEqual(3, code, output)
        self.assertIn("deployments:read", json.loads(output)["unverified"])

    def test_a_read_the_provider_filters_rather_than_refuses_is_unmeasurable(
        self,
    ) -> None:
        """Draft and triage advisories, a Pages site's builds, and the private
        repositories in a user's starred and watched lists: each route answers 200
        without the grant, leaving the private part out rather than refusing, so no
        probe can tell a grant apart (Codex on #364, calibrated 2026-10-04)."""
        facts = _observe(_calibrated_exact())
        # Attestations too: the repository route looks the digest up before the
        # permission, and the user route filters (CodeAnt on #364).
        for capability in (
            "repository_advisories",
            "pages",
            "starring",
            "watching",
            "attestations",
        ):
            with self.subTest(capability=capability):
                self.assertEqual("UNMEASURABLE", _state(facts, capability, "read"))

    def test_every_documented_permission_is_observed_at_both_levels(self) -> None:
        """Exact covers what the provider can grant, not what was convenient to
        probe (Codex on #364): every documented permission gets an observation at
        each level, from a probe or a stated reason."""
        from tools import credential_posture_github as github

        self.assertEqual(DOCUMENTED_PERMISSIONS, set(github.PERMISSIONS))
        facts = _observe(_calibrated())
        observed = {(o.capability, o.level) for o in facts.observations}
        expected = {
            (p, level) for p in DOCUMENTED_PERMISSIONS for level in ("read", "write")
        }
        self.assertEqual(expected, observed)

    def test_only_an_undocumented_level_is_not_applicable(self) -> None:
        """NOT_APPLICABLE is moot in the verdict, so it is reserved for a level GitHub
        documents no endpoint for. One whose endpoints merely sit out of reach is
        UNMEASURABLE: the declaration's owner has to accept it by name."""
        from tools import credential_posture_github as github

        self.assertEqual(UNDOCUMENTED_LEVELS, set(github.NOT_APPLICABLE))

    def test_a_refusal_or_acceptance_that_names_another_permission_is_unknown(
        self,
    ) -> None:
        """A probe that drifted -- the route now checks something else -- must not be
        read as an answer about the permission it was meant to measure."""
        answers = _calibrated()
        r = f"repos/{SUBJECT}"
        answers[("POST", f"{r}/actions/runs/1/pending_deployments")] = (
            403,
            "actions=write",
            NOT_ACCESSIBLE,
        )
        answers[("POST", f"{r}/issues")] = (422, "", "Invalid request.")
        facts = _observe(answers)
        self.assertEqual("UNKNOWN", _state(facts, "deployments", "write"))
        self.assertEqual("UNKNOWN", _state(facts, "issues", "write"))

    def test_a_refusal_that_needs_another_grant_too_is_not_a_refusal(self) -> None:
        """`pages=write,administration=write`: refused because either is missing, so
        it says nothing about pages alone."""
        from tools import credential_posture_github as github

        probe = _probe("pages")
        refused = github.Answer(
            403,
            {github.ACCEPTED_HEADER: "pages=write,administration=write"},
            NOT_ACCESSIBLE,
        )
        self.assertEqual("UNMEASURABLE", github.classify(probe, refused)[0])
        alone = github.Answer(
            403, {github.ACCEPTED_HEADER: "pages=write"}, NOT_ACCESSIBLE
        )
        self.assertEqual("NOT_GRANTED", github.classify(probe, alone)[0])

    def test_a_pass_that_another_grant_alone_explains_is_not_a_grant(self) -> None:
        """`administration=write;repository_creation=write`: passing proves one of
        them, not repository creation."""
        from tools import credential_posture_github as github

        probe = _probe("repository_creation")
        either = github.Answer(
            422,
            {github.ACCEPTED_HEADER: "administration=write;repository_creation=write"},
            "Validation Failed",
        )
        self.assertEqual("UNKNOWN", github.classify(probe, either)[0])

    def test_a_provider_failure_is_unknown(self) -> None:
        answers = _calibrated()
        r = f"repos/{SUBJECT}"
        answers[("GET", f"{r}/actions/secrets")] = (502, "secrets=read", "Bad Gateway")
        answers[("GET", f"{r}/hooks")] = (429, "repository_hooks=read", "rate limited")
        facts = _observe(answers)
        self.assertEqual("UNKNOWN", _state(facts, "secrets", "read"))
        self.assertEqual("UNKNOWN", _state(facts, "repository_hooks", "read"))

    def test_a_403_that_is_not_a_permission_refusal_is_unknown(self) -> None:
        """A secondary rate limit is also a 403: only GitHub's permission refusal is
        read as "not granted"."""
        answers = _calibrated()
        answers[("POST", f"repos/{SUBJECT}/actions/runs/1/pending_deployments")] = (
            403,
            "deployments=write",
            "You have exceeded a secondary rate limit",
        )
        facts = _observe(answers)
        self.assertEqual("UNKNOWN", _state(facts, "deployments", "write"))

    def test_a_404_on_a_lookup_first_route_is_unknown(self) -> None:
        """A creation probe answered with a lookup failure says nothing about the
        grant: the route may have looked up before checking the permission."""
        answers = _calibrated()
        answers[("POST", f"repos/{SUBJECT}/issues")] = (
            404,
            "issues=write",
            "Not Found",
        )
        facts = _observe(answers)
        self.assertEqual("UNKNOWN", _state(facts, "issues", "write"))

    def test_classify_refuses_a_404_from_a_route_not_shown_to_check_first(self) -> None:
        """Defence in depth beside the catalogue rule below: even a probe that admitted
        404 as a grant is not believed unless its route was shown to check first."""
        from tools import credential_posture_github as github

        probe = github.CATALOGUE[0]._replace(
            granted_statuses=frozenset({404, 422}), permission_first=False
        )
        answer = github.Answer(
            404, {github.ACCEPTED_HEADER: "contents=write"}, "Not Found"
        )
        self.assertEqual("UNKNOWN", github.classify(probe, answer)[0])
        first = probe._replace(permission_first=True)
        self.assertEqual("GRANTED", github.classify(first, answer)[0])

    def test_a_lookup_failure_never_proves_a_grant_on_its_own(self) -> None:
        """PATCH on a missing gist answered 404 while POST /gists answered 403 for the
        same token: a lookup can precede the permission check (#362). A 404 counts as
        granted only where a calibrated refusal showed the route checks first."""
        from tools import credential_posture_github as github

        for probe in github.CATALOGUE:
            with self.subTest(probe=probe.id):
                if 404 in probe.granted_statuses:
                    self.assertTrue(probe.permission_first, probe.id)

    def test_a_write_probe_the_provider_accepts_stops_the_check(self) -> None:
        """Every write probe carries a body the provider must reject. One it accepts
        broke that assumption and may have changed something: the check stops and
        says which, rather than reading it as a grant (CodeAnt and Codacy on #364)."""
        from tools import credential_posture_github as github

        answers = _calibrated()
        answers[("POST", f"repos/{SUBJECT}/pulls")] = (201, "", "")
        with self.assertRaisesRegex(github.ProbeHadEffect, "pull-requests-write"):
            _observe(answers)

    def test_a_write_probe_whose_outcome_is_unknown_stops_the_check(self) -> None:
        """A write that timed out, lost its transport, met a 5xx or got an unreadable
        success may have been applied, as the shared client says (`outcome_unknown`):
        the check stops on it as on an accepted write, never reading it as a mere
        unanswered probe (Codex on #364)."""
        from tools import credential_posture_github as github

        probe = _probe("issues")
        unknown = github.Answer(
            502, {github.ACCEPTED_HEADER: "issues=write"}, "Bad Gateway", None, True
        )
        with self.assertRaisesRegex(github.ProbeHadEffect, "issues-write"):
            github.classify(probe, unknown)
        # A read whose answer was lost changed nothing: it is only unanswered.
        read = _probe("secrets")
        lost = github.Answer(
            502, {github.ACCEPTED_HEADER: "secrets=read"}, "", None, True
        )
        self.assertEqual("UNKNOWN", github.classify(read, lost)[0])

    def test_the_kind_is_read_from_its_prefix_and_never_kept(self) -> None:
        from tools import credential_posture_github as github

        # Pinned independently of the adapter's table, so a changed table fails here.
        expected = {
            "github_pat_": "fine-grained",
            "ghp_": "classic",
            "gho_": "oauth",
            "ghs_": "app-installation",
            "ghu_": "app-user",
        }
        self.assertEqual(expected, dict(github.CREDENTIAL_PREFIXES))
        for prefix, kind in expected.items():
            with self.subTest(kind=kind):
                self.assertEqual(kind, github.credential_kind(prefix + "placeholder"))
        self.assertEqual("unknown", github.credential_kind("placeholder"))
        facts = _observe(_calibrated())
        self.assertNotIn("placeholder", repr(facts))

    def test_every_write_probe_is_rejected_by_construction(self) -> None:
        """A write probe's safety cannot rest on a name nobody created: a branch,
        workflow or run that happens to exist would let it act (Codex, CodeAnt on
        #364). Each carries a body the provider must reject whatever the repository
        holds, and aims at something that cannot exist as well."""
        from tools import credential_posture_github as github

        for probe in github.CATALOGUE:
            with self.subTest(probe=probe.id):
                self.assertIn(probe.method, {"GET", "POST", "PUT", "PATCH"})
                if probe.method == "GET":
                    continue
                self.assertTrue(probe.rejected_body_reason, probe.id)
                # Where the route names a target (a branch, workflow, commit or run),
                # the path names one that cannot exist. A route without one --
                # `PATCH user`, `POST gists` -- rests on the type violation alone, which
                # the next test requires of every write (CodeAnt on #364).
                names_a_target = any(
                    part in probe.path
                    for part in ("/branches/", "/workflows/", "/statuses/", "/runs/")
                )
                if names_a_target:
                    self.assertTrue(
                        "zz-credential-probe" in probe.path
                        or "0" * 40 in probe.path
                        or "/runs/1/" in probe.path,
                        probe.id,
                    )

    def test_every_write_probe_is_rejected_by_a_construction_no_cleanup_repairs(
        self,
    ) -> None:
        """GitHub cleans up a repository name with disallowed characters instead of
        rejecting it, so a "bad value" can be accepted after all (gitar on #364).

        A write body therefore rests on one of two constructions, never on a value the
        provider might normalize:
        - a documented field given an array or object of a JSON type it does not
          accept, where a calibrated refusal showed the permission check comes first;
        - a schema-valid body naming an object that cannot exist (the zero SHA),
          where the route validates the schema *before* the permission. `git/refs`
          does: a type-violating ref answered 422 on a repository the token cannot
          see (calibrated 2026-10-04), which would read every repository as writable.
        """
        from tools import credential_posture_github as github

        names: dict[type, str] = {list: "array", dict: "object"}
        for probe in github.CATALOGUE:
            if probe.method == "GET":
                continue
            with self.subTest(probe=probe.id):
                field, accepted = probe.type_violation
                body = probe.body or {}
                if field:
                    value = body.get(field)
                    self.assertIn(type(value), names, f"{field} is not a container")
                    self.assertNotIn(names[type(value)], accepted)
                else:
                    self.assertEqual("0" * 40, body.get(probe.impossible_target))
                    self.assertFalse(
                        any(isinstance(v, (list, dict)) for v in body.values()),
                        "a schema-valid body has no container where a scalar belongs",
                    )

    def test_the_scope_probe_is_schema_valid(self) -> None:
        """Scope reads a refusal on every other repository as "not writable". On a
        route that validates the schema first, only a schema-valid body is refused
        where the token has no grant."""
        from tools import credential_posture_github as github

        scope = github._SCOPE_PROBE  # skipcq: PYL-W0212
        self.assertEqual("", scope.type_violation[0])
        self.assertEqual("0" * 40, (scope.body or {}).get(scope.impossible_target))


class CredentialCheckCliTests(unittest.TestCase):
    """The command composes the adapter and the core, and never shows the token."""

    def test_the_calibrated_token_is_excess_for_its_extra_repository(self) -> None:
        """The token observed on 2026-10-04 could write ktogias/ai-peaf, which the
        repository policy does not declare: the check says so, exit 1."""
        code, output, _ = _run(_calibrated())
        verdict = json.loads(output)
        self.assertEqual(1, code)
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertEqual(["scope:ktogias/ai-peaf"], verdict["excess"])
        self.assertNotIn("SECRETVALUE", output)

    def test_without_the_extra_repository_the_token_is_exact(self) -> None:
        answers = _calibrated()
        answers[("POST", "repos/ktogias/ai-peaf/git/refs")] = (
            403,
            "contents=write;contents=write,workflows=write",
            NOT_ACCESSIBLE,
        )
        code, output, _ = _run(answers)
        self.assertEqual(0, code, output)
        self.assertEqual("EXACT", json.loads(output)["verdict"])

    def test_an_unverified_verdict_exits_three(self) -> None:
        """An excess grant that could not be ruled out is neither a pass nor a
        finding: exit 3, distinct from both."""
        answers = _calibrated()
        answers[("POST", "repos/ktogias/ai-peaf/git/refs")] = (
            403,
            "contents=write;contents=write,workflows=write",
            NOT_ACCESSIBLE,
        )
        answers[("POST", f"repos/{SUBJECT}/actions/runs/1/pending_deployments")] = (
            502,
            "deployments=write",
            "Bad Gateway",
        )
        code, output, _ = _run(answers)
        self.assertEqual(3, code, output)
        self.assertEqual("UNVERIFIED", json.loads(output)["verdict"])

    def test_a_malformed_repository_is_refused_before_any_request(self) -> None:
        """The subject is interpolated into request paths: a query, a traversal or a
        third segment would probe another endpoint (CodeAnt on #364)."""
        for repository in ("ktogias/gnostoa?x=1", "ktogias/../x", "a/b/c", "nobody"):
            with self.subTest(repository=repository):
                code, output, replay = _run(_calibrated(), "--repository", repository)
                self.assertEqual(2, code, output)
                self.assertEqual([], replay.sent)

    def test_a_malformed_subject_is_refused_even_when_declared(self) -> None:
        """The format check does not lean on the declaration: a declaration that lists a
        name GitHub does not allow still cannot route a probe through it."""
        malformed = "ktogias/../x"
        text = POLICY.read_text(encoding="utf-8").replace(
            "  - ktogias/gnostoa\n", f"  - {malformed}\n", 1
        )
        with tempfile.TemporaryDirectory() as scratch:
            declared = pathlib.Path(scratch) / "agent-credentials.yaml"
            declared.write_text(text, encoding="utf-8")
            code, output, replay = _run(
                _calibrated(),
                "--repository",
                malformed,
                policy=str(declared),
                cwd=pathlib.Path(scratch),
            )
        self.assertEqual(2, code, output)
        self.assertIn("owner/name", output)
        self.assertEqual([], replay.sent)

    def test_a_subject_the_declaration_does_not_list_is_refused_first(self) -> None:
        """Checking a repository the declaration does not name is a usage error,
        refused before any request (Codex, CodeRabbit on #364). The core still counts
        such a subject's writability as excess, so either guard alone holds."""
        code, output, replay = _run(_calibrated(), "--repository", "ktogias/ai-peaf")
        self.assertEqual(2, code, output)
        self.assertIn("does not list", output)
        self.assertEqual([], replay.sent)

    def test_a_probe_the_provider_accepts_exits_two(self) -> None:
        answers = _calibrated()
        answers[("POST", f"repos/{SUBJECT}/pulls")] = (201, "", "")
        code, output, _ = _run(answers)
        self.assertEqual(2, code)
        self.assertIn("may have had an effect", output)

    def test_a_policy_outside_the_working_tree_is_refused(self) -> None:
        """The declaration is read from the working tree, never from a path an
        argument points elsewhere (SonarCloud S8707 on #364)."""
        with (
            tempfile.TemporaryDirectory() as scratch,
            tempfile.TemporaryDirectory() as elsewhere,
        ):
            outside = pathlib.Path(scratch) / "agent-credentials.yaml"
            outside.write_text(POLICY.read_text(encoding="utf-8"), encoding="utf-8")
            code, output, replay = _run(
                _calibrated(), policy=str(outside), cwd=pathlib.Path(elsewhere)
            )
        self.assertEqual(2, code, output)
        self.assertEqual([], replay.sent)

    def test_a_policy_with_a_duplicate_key_is_refused(self) -> None:
        """A repeated capability key would silently keep its last value, so a second
        `deployments: {max: write}` could hide an excess grant (CodeRabbit on #364)."""
        # Inside `capabilities`, where the repeated key would otherwise win.
        text = POLICY.read_text(encoding="utf-8").replace(
            "capabilities:\n",
            "capabilities:\n  deployments: {min: none, max: write}\n",
            1,
        )
        with tempfile.TemporaryDirectory() as scratch:
            duplicated = pathlib.Path(scratch) / "agent-credentials.yaml"
            duplicated.write_text(text, encoding="utf-8")
            code, output, _ = _run(
                _calibrated(), policy=str(duplicated), cwd=pathlib.Path(scratch)
            )
        self.assertEqual(2, code, output)
        self.assertIn("duplicate", output)

    def test_a_client_that_refuses_the_token_exits_two(self) -> None:
        """A malformed token is refused by the shared client as it is built: an
        input error with its exit, not a traceback (CodeAnt on #364)."""
        from tools import credential_check, github_rest

        out = io.StringIO()
        with (
            _working_directory(ROOT),
            mock.patch.object(credential_check, "_token", return_value="bad token"),
            mock.patch.object(
                credential_check,
                "_transport",
                side_effect=github_rest.GitHubError("the token is malformed"),
            ),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(out),
        ):
            code = credential_check.main(
                ["--repository", SUBJECT, "--policy", str(POLICY)]
            )
        self.assertEqual(2, code)
        self.assertIn("malformed", out.getvalue())

    def test_scope_covers_every_repository_the_token_can_see(self) -> None:
        """Not only the resource owner's own: a writable repository of any owner is
        probed (CodeAnt on #364)."""
        _, _, replay = _run(_calibrated())
        probed = {path for method, path, _ in replay.sent if path.endswith("/git/refs")}
        self.assertEqual({f"repos/{name}/git/refs" for name in VISIBLE}, probed)

    def test_a_listing_of_several_pages_is_followed_by_its_links(self) -> None:
        answers = _calibrated()
        second = f"{REPOS}&page=2"
        answers[("GET", second)] = (200, "metadata=read", "")
        listing = {
            REPOS: (list(VISIBLE[:2]), second),
            second: (list(VISIBLE[2:]), None),
        }
        _, _, replay = _run(answers, listing=listing)
        probed = {path for _, path, _ in replay.sent if path.endswith("/git/refs")}
        self.assertEqual({f"repos/{name}/git/refs" for name in VISIBLE}, probed)

    def test_a_listed_repository_that_cannot_be_probed_stops_the_check(self) -> None:
        """Skipping it would leave a repository the token can see unchecked, where an
        excess grant could hide: the check stops instead (exit 2)."""
        for listed in (["ktogias/../x"], ["a/b?c=1"], [""]):
            with self.subTest(listed=listed):
                code, output, replay = _run(
                    _calibrated(), listing={REPOS: ([SUBJECT, *listed], None)}
                )
                self.assertEqual(2, code, output)
                self.assertIn("cannot be probed", output)
                self.assertFalse(
                    any(path.endswith("/git/refs") for _, path, _ in replay.sent)
                )

    def test_a_listing_past_its_bound_is_refused_not_read_in_part(self) -> None:
        """Scope read in part could miss the one writable repository: past the bound
        the check stops (exit 2) rather than judge what it did read."""
        answers = _calibrated()
        listing: dict[str, tuple[list[str], str | None]] = {}
        page = REPOS
        for number in range(2, 13):
            following = f"{REPOS}&page={number}"
            listing[page] = ([SUBJECT], following)
            answers[("GET", following)] = (200, "metadata=read", "")
            page = following
        listing[page] = ([SUBJECT], None)
        code, output, replay = _run(answers, listing=listing)
        self.assertEqual(2, code, output)
        self.assertIn("pages", output)
        self.assertFalse(any(path.endswith("/git/refs") for _, path, _ in replay.sent))

    def test_a_declared_repository_of_another_owner_is_refused(self) -> None:
        """A fine-grained token reaches only its resource owner's resources, so the
        subject proving writable shows the token's owner is the subject's -- provided
        every declared repository belongs to the declared owner (CodeAnt on #364)."""
        text = POLICY.read_text(encoding="utf-8").replace(
            "resource_owner: ktogias", "resource_owner: someone-else", 1
        )
        with tempfile.TemporaryDirectory() as scratch:
            declared = pathlib.Path(scratch) / "agent-credentials.yaml"
            declared.write_text(text, encoding="utf-8")
            code, output, replay = _run(
                _calibrated(), policy=str(declared), cwd=pathlib.Path(scratch)
            )
        self.assertEqual(2, code, output)
        self.assertIn("resource owner", output)
        self.assertEqual([], replay.sent)

    def test_a_declaration_its_schema_refuses_is_refused_with_its_location(
        self,
    ) -> None:
        """The declaration is a public contract (`schemas/agent-credentials.schema.json`):
        a violation names where it is, before any request."""
        text = POLICY.read_text(encoding="utf-8").replace(
            "  contents: {min: write, max: write}",
            "  contents: {min: write, max: owner}",
            1,
        )
        with tempfile.TemporaryDirectory() as scratch:
            declared = pathlib.Path(scratch) / "agent-credentials.yaml"
            declared.write_text(text, encoding="utf-8")
            code, output, replay = _run(
                _calibrated(), policy=str(declared), cwd=pathlib.Path(scratch)
            )
        self.assertEqual(2, code, output)
        self.assertIn("capabilities.contents.max", output)
        self.assertEqual([], replay.sent)

    def test_a_write_whose_outcome_is_unknown_exits_two(self) -> None:
        answers = _calibrated_exact()
        answers[("POST", f"repos/{SUBJECT}/issues")] = (
            502,
            "issues=write",
            "OUTCOME-UNKNOWN: Bad Gateway",
        )
        code, output, _ = _run(answers)
        self.assertEqual(2, code, output)
        self.assertIn("may have had an effect", output)

    def test_a_failed_environment_listing_stops_the_check(self) -> None:
        """An outage or a refusal is not "no environments": skipping the environment
        probe on it would hide the failure behind an unmeasured row (CodeAnt on #364)."""
        answers = _calibrated_exact()
        answers[("GET", f"repos/{SUBJECT}/environments")] = (
            502,
            "actions=read",
            "Bad Gateway",
        )
        code, output, replay = _run(answers)
        self.assertEqual(2, code, output)
        self.assertIn("environment listing", output)
        self.assertFalse(any(m != "GET" for m, _, _ in replay.sent))

    def test_gh_is_resolved_only_from_trusted_system_directories(self) -> None:
        """Without a token in the environment the command runs `gh auth token`. The
        executable comes from the root-owned system directories the preparation wrapper
        trusts (`knowledge_common.trusted_executable`), never from the caller's `PATH`,
        where a shadowed `gh` would run (CodeAnt on #364). Not `os.defpath`: on this
        host `gh` is in `/usr/local/bin`, which `os.defpath` omits."""
        from tools import credential_check, github_rest
        from tools import credential_posture as posture

        with (
            mock.patch.object(github_rest, "environment_token", return_value=""),
            mock.patch.object(
                credential_check, "trusted_executable", return_value=None
            ) as trusted,
            self.assertRaisesRegex(posture.PolicyError, "GH_TOKEN"),
        ):
            credential_check._token()  # skipcq: PYL-W0212
        trusted.assert_called_once_with("gh")

    def test_gh_auth_token_is_bounded_in_time(self) -> None:
        """A keyring prompt or a stalled credential helper must not hang the check
        that gates every first provider write (CodeRabbit on #364)."""
        import subprocess  # nosec B404 -- only to build the TimeoutExpired a stall raises

        from tools import credential_check, github_rest
        from tools import credential_posture as posture

        stall = subprocess.TimeoutExpired(["gh", "auth", "token"], 30)
        with (
            mock.patch.object(github_rest, "environment_token", return_value=""),
            mock.patch.object(
                credential_check, "trusted_executable", return_value="/usr/bin/gh"
            ),
            mock.patch.object(subprocess, "run", side_effect=stall) as run,
            self.assertRaisesRegex(posture.PolicyError, "timed out"),
        ):
            credential_check._token()  # skipcq: PYL-W0212
        self.assertGreater(run.call_args.kwargs["timeout"], 0)

    def test_an_environment_name_is_one_encoded_path_segment(self) -> None:
        """The provider names the environment; its name is one segment of the probe's
        path, whatever it contains (CodeAnt on #364)."""
        from tools import credential_posture_github as github

        answers = _calibrated_exact()
        r = f"repos/{SUBJECT}"
        answers[("GET", f"{r}/environments/a%2Fb%3Fx/secrets")] = answers.pop(
            ("GET", f"{r}/environments/claude-review/secrets")
        )
        facts = github.observe(
            _Replay(answers),
            repository=SUBJECT,
            public=True,
            environment="a/b?x",
            visible_repositories=VISIBLE,
            login="ktogias",
            token=_placeholder_token("fine-grained"),
        )
        self.assertEqual("NOT_GRANTED", _state(facts, "environments", "read"))
        with self.assertRaises(ValueError):
            github.observe(
                _Replay(answers),
                repository=SUBJECT,
                public=True,
                environment="..",
                visible_repositories=VISIBLE,
                login="ktogias",
                token=_placeholder_token("fine-grained"),
            )

    def test_names_differing_only_in_case_are_one_repository(self) -> None:
        """A declaration, a subject and a listing that spell one repository with
        different case name one repository, as GitHub resolves it (CodeAnt on #364)."""
        text = POLICY.read_text(encoding="utf-8").replace(
            "  - ktogias/gnostoa\n", "  - ktogias/Gnostoa\n", 1
        )
        with tempfile.TemporaryDirectory() as scratch:
            declared = pathlib.Path(scratch) / "agent-credentials.yaml"
            declared.write_text(text, encoding="utf-8")
            code, output, _ = _run(
                _calibrated_exact(),
                "--repository",
                "KTOGIAS/gnostoa",
                policy=str(declared),
                cwd=pathlib.Path(scratch),
            )
        self.assertEqual(0, code, output)
        self.assertEqual("EXACT", json.loads(output)["verdict"])

    def test_the_command_is_registered(self) -> None:
        from tools import cli

        self.assertIn("credential-check", cli.COMMANDS)


class _Client:
    """The shared client's surface ``_transport`` uses, recording each request; a
    request it was not given an answer for fails, like a real refusal."""

    api_root = "https://api.github.com"

    def __init__(self, token: str, **_options: Any) -> None:
        self.token = token
        self.requests: list[tuple[str, str]] = []

    def url(self, path: str) -> str:
        return f"{self.api_root}/{path}"

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        from tools import github_rest

        self.requests.append(("GET", url))
        if url.endswith("/refused"):
            raise github_rest.GitHubError(
                NOT_ACCESSIBLE, status=403, accepted_permissions="secrets=read"
            )
        return {"ok": True}, {"link": ""}

    def _write(self, method: str, url: str, payload: dict[str, Any]) -> Any:
        from tools import github_rest

        self.requests.append((method, url))
        if url.endswith("/unknown"):
            raise github_rest.GitHubWriteError(
                "Bad Gateway", status=502, outcome_unknown=True
            )
        if url.endswith("/redirected"):
            # The shared client refuses every redirect, and reports it as a read error
            # whatever the method.
            raise github_rest.UnsafeRedirect("refusing a redirect")
        return payload

    def post(self, url: str, payload: dict[str, Any]) -> Any:
        return self._write("POST", url, payload)

    def put(self, url: str, payload: dict[str, Any]) -> Any:
        return self._write("PUT", url, payload)

    def patch(self, url: str, payload: dict[str, Any]) -> Any:
        return self._write("PATCH", url, payload)


def _fake_transport() -> tuple[Any, _Client]:
    """``_transport``'s ``send``, built over a recording stand-in for the client."""
    from tools import credential_check, github_rest

    made: list[_Client] = []

    def build(token: str, **options: Any) -> _Client:
        made.append(_Client(token, **options))
        return made[-1]

    with mock.patch.object(github_rest, "GitHubRestClient", side_effect=build):
        send = credential_check._transport("tok")  # skipcq: PYL-W0212
    return send, made[0]


class TransportTests(unittest.TestCase):
    """``_transport`` turns the shared client's calls into probe answers."""

    def test_a_path_and_a_followed_page_on_the_origin_are_read(self) -> None:
        send, client = _fake_transport()
        self.assertEqual(200, send("GET", "user", None).status)
        followed = "https://api.github.com/user/repos?per_page=100&page=2"
        self.assertEqual(200, send("GET", followed, None).status)
        self.assertEqual(
            [("GET", "https://api.github.com/user"), ("GET", followed)], client.requests
        )

    def test_a_followed_page_off_the_origin_is_never_requested(self) -> None:
        send, client = _fake_transport()
        answer = send("GET", "https://api.github.com.evil.example/x", None)
        self.assertNotEqual(200, answer.status)
        self.assertEqual([], [r for r in client.requests if "evil" in r[1]])

    def test_a_refusal_keeps_its_accepted_permissions(self) -> None:
        from tools import credential_posture_github as github

        send, _ = _fake_transport()
        answer = send("GET", "repos/o/r/refused", None)
        self.assertEqual(403, answer.status)
        self.assertEqual("secrets=read", answer.headers[github.ACCEPTED_HEADER])
        self.assertIn(NOT_ACCESSIBLE, answer.message)

    def test_a_write_the_client_reports_outcome_unknown_keeps_the_flag(self) -> None:
        send, _ = _fake_transport()
        self.assertTrue(send("POST", "repos/o/r/unknown", {"a": 1}).outcome_unknown)
        self.assertFalse(send("GET", "repos/o/r/refused", None).outcome_unknown)

    def test_a_redirected_write_is_outcome_unknown(self) -> None:
        """A redirect is not a refusal: the write reached the provider and its rejection
        was never established, so it is outcome-unknown, and the check stops on it
        (Codex on #364)."""
        send, _ = _fake_transport()
        self.assertTrue(send("POST", "repos/o/r/redirected", {"a": 1}).outcome_unknown)

    def test_an_accepted_write_is_reported_as_accepted(self) -> None:
        send, client = _fake_transport()
        for method in ("POST", "PUT", "PATCH"):
            with self.subTest(method=method):
                self.assertEqual(201, send(method, "repos/o/r/x", {"a": 1}).status)
        self.assertEqual(["POST", "PUT", "PATCH"], [m for m, _ in client.requests])


def _source_facts(path: pathlib.Path) -> tuple[set[str], set[str], set[str]]:
    """The string literals, names and attributes used, and top modules imported."""
    nodes = list(ast.walk(ast.parse(path.read_text(encoding="utf-8"))))
    constants = {
        n.value
        for n in nodes
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    }
    used = {n.attr for n in nodes if isinstance(n, ast.Attribute)}
    used |= {n.id for n in nodes if isinstance(n, ast.Name)}
    imported = {
        a.name.split(".")[0]
        for n in nodes
        if isinstance(n, ast.Import)
        for a in n.names
    }
    imported |= {
        (n.module or "").split(".")[0] for n in nodes if isinstance(n, ast.ImportFrom)
    }
    return constants, used, imported


class SharedOwnerReuseTests(unittest.TestCase):
    """The command consumes the owner of each responsibility it needs (#365).

    Round 2's first draft wrote its own owner/name regex, path confinement, token
    reader, page loop, timestamp and hand validation beside the owners of each; no
    analyzer saw it, because none of it was copied text. Until #365 gives the codebase
    a registry and a checker, this pins the instance.
    """

    def test_the_command_reuses_every_owner_it_needs(self) -> None:
        constants, used, imported = _source_facts(
            ROOT / "tools" / "credential_check.py"
        )
        not_again = {
            "a token read from the environment": bool(
                {"GH_TOKEN", "GITHUB_TOKEN"} & constants
            ),
            "a path confined inline": "is_relative_to" in used,
            "a name checked by its own regex": "re" in imported,
            "a page loop of its own": any('rel="next"' in c for c in constants)
            or "&page=" in "".join(constants),
            "YAML loaded past the duplicate-key loader": "safe_load" in used,
            "a clock of its own": "datetime" in imported,
        }
        for responsibility, rewritten in not_again.items():
            with self.subTest(responsibility=responsibility):
                self.assertFalse(rewritten)
        for owner in (
            "environment_token",
            "owner_name",
            "repository_key",
            "follow_pages",
            "within_root",
            "schema_errors",
            "utc_timestamp",
            "load_yaml",
        ):
            with self.subTest(owner=owner):
                self.assertIn(owner, used)


class SharedClientAcceptedPermissionsTests(unittest.TestCase):
    """A refusal keeps the permissions the provider said it would have accepted."""

    def test_a_refusal_carries_the_accepted_permissions(self) -> None:
        import email.message
        import urllib.error

        from tools import github_rest

        headers = email.message.Message()
        headers["X-Accepted-GitHub-Permissions"] = "deployments=write"
        error = urllib.error.HTTPError(
            "https://api.github.com/x",
            403,
            "Forbidden",
            headers,
            io.BytesIO(
                b'{"message":"Resource not accessible by personal access token"}'
            ),
        )
        client = github_rest.GitHubRestClient("t")
        classified = client._classified(error, True)  # skipcq: PYL-W0212
        self.assertEqual("deployments=write", classified.accepted_permissions)
        self.assertEqual(403, classified.status)

    def test_the_client_can_put(self) -> None:
        from tools import github_rest

        self.assertTrue(callable(getattr(github_rest.GitHubRestClient, "put", None)))


class NeutralCoreTests(unittest.TestCase):
    """The core names no provider: capabilities, kinds and scope are the policy's."""

    def test_the_core_is_provider_neutral(self) -> None:
        # Loaded by path: the runtime image runs these tests outside a `tests`
        # package, so the guard is shared through its file, never copied.
        spec = importlib.util.spec_from_file_location(
            "gnostoa_neutral_core_guard", ROOT / "tests" / "test_agent_review_core.py"
        )
        if spec is None or spec.loader is None:
            self.fail("the neutral-core guard could not be loaded")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        source = (ROOT / "tools" / "credential_posture.py").read_text(encoding="utf-8")
        self.assertEqual([], guard.COUPLING.findall(source))
        imported = {
            node.module.split(".")[0]
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertLessEqual(
            imported, {"__future__", "collections", "datetime", "typing"}
        )
        self.assertIsNone(
            re.search(r"\bimport (urllib|http|socket|subprocess)\b", source)
        )


if __name__ == "__main__":
    unittest.main()
