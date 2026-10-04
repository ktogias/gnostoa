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
import pathlib
import re
import unittest
from typing import Any
from unittest import mock

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy" / "agent-credentials.yaml"
NOW = "2026-10-04T12:00:00Z"
NOT_ACCESSIBLE = "Resource not accessible by personal access token"


def _policy_document() -> dict[str, Any]:
    return {
        "id": "test-agent-credentials",
        "version": "1.0",
        "token_kind": "fine-grained",
        "max_lifetime_days": 31,
        "resource_owner": "o",
        "repositories": ["o/r"],
        "capabilities": {
            "contents": {"min": "write", "max": "write"},
            "workflows": {"min": "write", "max": "write"},
            "actions": {"min": "read", "max": "read"},
            "deployments": {"min": "none", "max": "none"},
            "administration": {"min": "none", "max": "none"},
        },
    }


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
    }
    base.update(states)
    return tuple(
        posture.Observation(key.rsplit("_", 1)[0], key.rsplit("_", 1)[1], state, "e")
        for key, state in base.items()
    )


def _facts(**overrides: Any) -> Any:
    from tools import credential_posture as posture

    fields: dict[str, Any] = {
        "token_kind": "fine-grained",
        "expires_at": "2026-11-03T13:01:27Z",
        "observations": _observations(),
        "scope": (posture.ScopeObservation("o/other", "NOT_GRANTED", "e"),),
    }
    fields.update(overrides)
    return posture.Facts(**fields)


def _verdict(facts: Any) -> dict[str, Any]:
    """The verdict of ``facts`` against the test policy."""
    from tools import credential_posture as posture

    return posture.evaluate(posture.load_policy(_policy_document()), facts, NOW)


def _observe(answers: dict[tuple[str, str], tuple[int, str, str]]) -> Any:
    """What the adapter establishes from ``answers``."""
    from tools import credential_posture_github as github

    return github.observe(
        _Replay(answers),
        repository="ktogias/gnostoa",
        public=True,
        environment="claude-review",
        owned_repositories=("ktogias/gnostoa", "ktogias/ai-peaf", "ktogias/elsewhere"),
        token="github_pat_" + "x" * 20,
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


def _run(answers: dict[tuple[str, str], tuple[int, str, str]]) -> tuple[int, str]:
    """Run the command over ``answers``; the declaration is named, not found by cwd."""
    from tools import credential_check

    replay = _Replay(answers)
    out = io.StringIO()
    with (
        mock.patch.object(credential_check, "_token", return_value="github_pat_SECRET"),
        mock.patch.object(credential_check, "_transport", return_value=replay),
        mock.patch.object(
            credential_check,
            "_owned_repositories",
            return_value=("ktogias/gnostoa", "ktogias/ai-peaf", "ktogias/elsewhere"),
        ),
        mock.patch.object(credential_check, "_now", return_value=NOW),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(out),
    ):
        code = credential_check.main(
            ["--repository", "ktogias/gnostoa", "--policy", str(POLICY), "--json"]
        )
    return code, out.getvalue()


class CorePolicyTests(unittest.TestCase):
    """The declaration is validated before anything is judged against it."""

    def test_a_valid_policy_loads(self) -> None:
        from tools import credential_posture as posture

        policy = posture.load_policy(_policy_document())
        self.assertEqual(("o/r",), policy.repositories)
        self.assertEqual("write", policy.capabilities["contents"].maximum)

    def test_a_malformed_policy_is_refused(self) -> None:
        from tools import credential_posture as posture

        def broken(**change: Any) -> dict[str, Any]:
            document = _policy_document()
            document.update(change)
            return document

        cases = {
            "an unknown key": broken(extra=1),
            "a minimum above its maximum": broken(
                capabilities={"contents": {"min": "write", "max": "read"}}
            ),
            "an unknown level": broken(
                capabilities={"contents": {"min": "x", "max": "write"}}
            ),
            "a lifetime that is not a positive integer": broken(max_lifetime_days=0),
            "no repositories": broken(repositories=[]),
        }
        for name, document in cases.items():
            with self.subTest(case=name), self.assertRaises(posture.PolicyError):
                posture.load_policy(document)

    def test_the_repository_policy_is_valid_and_forbids_deployment_approval(
        self,
    ) -> None:
        """Channel C holds only while the agents' token cannot approve a deployment
        (#15 5979734602): the committed policy must say so."""
        from tools import credential_posture as posture

        policy = posture.load_policy(yaml.safe_load(POLICY.read_text(encoding="utf-8")))
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

    def test_a_writable_repository_outside_the_scope_is_excess(self) -> None:
        from tools import credential_posture as posture

        verdict = _verdict(
            _facts(scope=(posture.ScopeObservation("o/other", "GRANTED", "e"),))
        )
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("scope:o/other", verdict["excess"])

    def test_the_token_kind_and_lifetime_are_part_of_the_verdict(self) -> None:
        cases = {
            "another kind": (_facts(token_kind="oauth"), "TOKEN_KIND_MISMATCH"),
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

    def test_a_capability_the_policy_does_not_name_is_reported_not_covered(
        self,
    ) -> None:
        """Exact means exact over what was probed: a probe outside the declaration is
        named, never silently dropped."""
        from tools import credential_posture as posture

        extra = (
            *_observations(),
            posture.Observation("pages", "write", "NOT_GRANTED", "e"),
        )
        verdict = _verdict(_facts(observations=extra))
        self.assertEqual(["pages:write"], verdict["undeclared"])

    def test_an_undeclared_grant_is_excess(self) -> None:
        """A grant the declaration did not foresee is held to none: excess, not a
        silent pass."""
        from tools import credential_posture as posture

        extra = (
            *_observations(),
            posture.Observation("pages", "write", "GRANTED", "e"),
        )
        verdict = _verdict(_facts(observations=extra))
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertIn("pages:write", verdict["excess"])

    def test_the_precedence_puts_the_most_dangerous_first(self) -> None:
        verdict = _verdict(
            _facts(
                token_kind="oauth",
                observations=_observations(
                    deployments_write="GRANTED", contents_write="NOT_GRANTED"
                ),
            )
        )
        self.assertEqual("TOKEN_KIND_MISMATCH", verdict["verdict"])
        self.assertEqual(
            ["TOKEN_KIND_MISMATCH", "EXCESS", "DEFICIENT"], verdict["reasons"]
        )


class _Replay:
    """A provider that answers each (method, path) from the calibration, and refuses
    anything else -- so a probe outside the catalogue is a test failure, not a pass."""

    def __init__(self, answers: dict[tuple[str, str], tuple[int, str, str]]) -> None:
        self.answers = answers
        self.sent: list[tuple[str, str, Any]] = []

    def __call__(self, method: str, path: str, body: Any) -> Any:
        from tools import credential_posture_github as github

        self.sent.append((method, path, body))
        if (method, path) not in self.answers:
            raise AssertionError(f"unexpected probe {method} {path}")
        status, accepted, message = self.answers[(method, path)]
        headers = {"x-accepted-github-permissions": accepted} if accepted else {}
        if path == "user":
            headers["github-authentication-token-expiration"] = (
                "2026-11-03 13:01:27 UTC"
            )
        document = {
            "repos/ktogias/gnostoa": {"private": False},
            "repos/ktogias/gnostoa/environments": {
                "environments": [{"name": "claude-review"}]
            },
        }.get(path)
        return github.Answer(status, headers, message, document)


def _calibrated() -> dict[tuple[str, str], tuple[int, str, str]]:
    """The answers observed for the agents' token on 2026-10-04 (#362)."""
    r = "repos/ktogias/gnostoa"
    zero = "0" * 40
    no = NOT_ACCESSIBLE
    return {
        ("GET", "user"): (200, "", ""),
        ("GET", f"{r}"): (200, "metadata=read", ""),
        ("GET", f"{r}/environments"): (200, "actions=read", ""),
        ("POST", f"{r}/git/refs"): (
            422,
            "contents=write;contents=write,workflows=write",
            "Object does not exist",
        ),
        ("POST", f"{r}/issues"): (422, "issues=write", "Invalid request."),
        ("POST", f"{r}/pulls"): (422, "pull_requests=write", "Validation Failed"),
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
        ("GET", "user/keys"): (403, "keys=read", no),
        ("GET", "user/ssh_signing_keys"): (403, "git_signing_ssh_public_keys=read", no),
        ("GET", "user/gpg_keys"): (403, "gpg_keys=read", no),
        ("GET", "user/emails"): (403, "emails=read", no),
        ("POST", "gists"): (403, "gists=write", no),
        ("POST", "repos/ktogias/ai-peaf/git/refs"): (
            422,
            "contents=write;contents=write,workflows=write",
            "Object does not exist",
        ),
        ("POST", "repos/ktogias/elsewhere/git/refs"): (
            403,
            "contents=write;contents=write,workflows=write",
            no,
        ),
    }


class GitHubAdapterTests(unittest.TestCase):
    """Each answer becomes an observation by the rule it was calibrated against."""

    def test_the_calibration_is_read_as_observed(self) -> None:
        facts = _observe(_calibrated())
        self.assertEqual("fine-grained", facts.token_kind)
        self.assertEqual("2026-11-03T13:01:27Z", facts.expires_at)
        for capability, level, state in (
            ("contents", "write", "GRANTED"),
            ("issues", "write", "GRANTED"),
            ("pull_requests", "write", "GRANTED"),
            ("workflows", "write", "UNMEASURABLE"),
            ("actions", "write", "NOT_GRANTED"),
            ("actions", "read", "PUBLIC"),
            ("workflows", "read", "NOT_APPLICABLE"),
            ("deployments", "read", "PUBLIC"),
            ("statuses", "write", "NOT_GRANTED"),
            ("deployments", "write", "NOT_GRANTED"),
            ("administration", "write", "NOT_GRANTED"),
            ("administration", "read", "NOT_GRANTED"),
            ("secrets", "read", "NOT_GRANTED"),
            ("environments", "read", "NOT_GRANTED"),
            ("gists", "write", "NOT_GRANTED"),
            ("git_signing_ssh_public_keys", "read", "NOT_GRANTED"),
        ):
            with self.subTest(capability=capability, level=level):
                self.assertEqual(state, _state(facts, capability, level))
        self.assertEqual(
            {"ktogias/ai-peaf": "GRANTED", "ktogias/elsewhere": "NOT_GRANTED"},
            {s.repository: s.state for s in facts.scope},
        )

    def test_a_refusal_or_acceptance_that_names_another_permission_is_unknown(
        self,
    ) -> None:
        """A probe that drifted -- the route now checks something else -- must not be
        read as an answer about the permission it was meant to measure."""
        answers = _calibrated()
        r = "repos/ktogias/gnostoa"
        answers[("POST", f"{r}/actions/runs/1/pending_deployments")] = (
            403,
            "actions=write",
            NOT_ACCESSIBLE,
        )
        answers[("POST", f"{r}/issues")] = (422, "", "Invalid request.")
        facts = _observe(answers)
        self.assertEqual("UNKNOWN", _state(facts, "deployments", "write"))
        self.assertEqual("UNKNOWN", _state(facts, "issues", "write"))

    def test_a_provider_failure_is_unknown(self) -> None:
        answers = _calibrated()
        r = "repos/ktogias/gnostoa"
        answers[("GET", f"{r}/actions/secrets")] = (502, "secrets=read", "Bad Gateway")
        answers[("GET", f"{r}/hooks")] = (429, "repository_hooks=read", "rate limited")
        facts = _observe(answers)
        self.assertEqual("UNKNOWN", _state(facts, "secrets", "read"))
        self.assertEqual("UNKNOWN", _state(facts, "repository_hooks", "read"))

    def test_a_403_that_is_not_a_permission_refusal_is_unknown(self) -> None:
        """A secondary rate limit is also a 403: only GitHub's permission refusal is
        read as "not granted"."""
        answers = _calibrated()
        r = "repos/ktogias/gnostoa"
        answers[("POST", f"{r}/actions/runs/1/pending_deployments")] = (
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
        answers[("POST", "repos/ktogias/gnostoa/issues")] = (
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

    def test_the_token_kind_is_read_from_its_prefix_and_never_kept(self) -> None:
        from tools import credential_posture_github as github

        for token, kind in (
            ("github_pat_abc", "fine-grained"),
            ("ghp_abc", "classic"),
            ("gho_abc", "oauth"),
            ("ghs_abc", "app-installation"),
            ("ghu_abc", "app-user"),
            ("something", "unknown"),
        ):
            with self.subTest(kind=kind):
                self.assertEqual(kind, github.token_kind(token))
        facts = _observe(_calibrated())
        self.assertNotIn("github_pat_", repr(facts))

    def test_no_probe_can_change_provider_state(self) -> None:
        """Every write probe aims at something that cannot exist, or carries a body the
        provider must reject: the answer is the same refusal whether the grant is there
        or not, and nothing is created, changed or deleted either way."""
        from tools import credential_posture_github as github

        for probe in github.CATALOGUE:
            with self.subTest(probe=probe.id):
                self.assertIn(probe.method, {"GET", "POST", "PUT", "PATCH"})
                if probe.method == "GET":
                    continue
                path, body = probe.path, json.dumps(probe.body or {})
                self.assertTrue(
                    "zz-credential-probe" in path + body
                    or "0" * 40 in path + body
                    or "/runs/1/" in path
                    or probe.rejected_body,
                    f"{probe.id} does not aim at a non-existent target",
                )
                if probe.rejected_body:
                    # A creation that the provider must refuse: issues without a title,
                    # a pull request between branches that do not exist, a gist with
                    # no files.
                    self.assertTrue(probe.rejected_body_reason, probe.id)


class CredentialCheckCliTests(unittest.TestCase):
    """The command composes the adapter and the core, and never shows the token."""

    def test_the_calibrated_token_is_excess_for_its_extra_repository(self) -> None:
        """The token observed on 2026-10-04 can write ktogias/ai-peaf, which the
        repository policy does not declare: the check says so, exit 1."""
        code, output = _run(_calibrated())
        verdict = json.loads(output)
        self.assertEqual(1, code)
        self.assertEqual("EXCESS", verdict["verdict"])
        self.assertEqual(["scope:ktogias/ai-peaf"], verdict["excess"])
        self.assertNotIn("SECRET", output)

    def test_without_the_extra_repository_the_token_is_exact(self) -> None:
        answers = _calibrated()
        answers[("POST", "repos/ktogias/ai-peaf/git/refs")] = (
            403,
            "contents=write;contents=write,workflows=write",
            NOT_ACCESSIBLE,
        )
        code, output = _run(answers)
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
        answers[
            ("POST", "repos/ktogias/gnostoa/actions/runs/1/pending_deployments")
        ] = (502, "deployments=write", "Bad Gateway")
        code, output = _run(answers)
        self.assertEqual(3, code, output)
        self.assertEqual("UNVERIFIED", json.loads(output)["verdict"])

    def test_the_command_is_registered(self) -> None:
        from tools import cli

        self.assertIn("credential-check", cli.COMMANDS)


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
        assert spec is not None and spec.loader is not None
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        COUPLING = guard.COUPLING

        source = (ROOT / "tools" / "credential_posture.py").read_text(encoding="utf-8")
        self.assertEqual([], COUPLING.findall(source))
        imported = {
            node.module.split(".")[0]
            if isinstance(node, ast.ImportFrom) and node.module
            else ""
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
        }
        self.assertLessEqual(
            imported, {"__future__", "collections", "datetime", "typing", ""}
        )
        self.assertIsNone(
            re.search(r"\bimport (urllib|http|socket|subprocess)\b", source)
        )


if __name__ == "__main__":
    unittest.main()
