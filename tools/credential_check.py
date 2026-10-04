"""``knowledge credential-check``: does the agents' token hold exactly its declared grants?

Decision 0101 (#362). Composes the GitHub adapter's probes with the provider-neutral
core, against the least-privilege declaration (``policy/agent-credentials.yaml`` by
default, read from the working tree). It is read-only and non-effecting: every probe
is a read, or a write whose body the provider must reject, aimed at a name that does
not exist; a write the provider accepts stops the check.

Exit status: 0 EXACT; 1 a grant beyond or below the declaration, the wrong kind of
credential, or a lifetime beyond the bound; 3 UNVERIFIED (an excess grant could not be
ruled out); 2 an input or tool error, or a probe the provider accepted. The token is
read from ``GH_TOKEN`` or ``GITHUB_TOKEN``, or else from ``gh auth token``, and is
never printed.

Each responsibility it needs is consumed from its owner (#365): the token, names and
pages from the shared GitHub client, path confinement from ``agent_review_paths``, the
declaration's contract from ``schemas/`` through ``schema_validation``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess  # nosec B404 -- `gh auth token`, a fixed argv, no shell
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools import agent_review_paths, github_rest
from tools import credential_posture as posture
from tools import credential_posture_github as github
from tools.knowledge_common import load_yaml, utc_timestamp
from tools.schema_validation import schema_errors

SCHEMA = "agent-credentials.schema.json"
_EXIT = {
    "EXACT": 0,
    "EXCESS": 1,
    "DEFICIENT": 1,
    "CREDENTIAL_KIND_MISMATCH": 1,
    "LIFETIME_EXCEEDED": 1,
    "UNVERIFIED": 3,
}
_MAX_REPOSITORY_PAGES = 10
_REPOSITORY_LISTING = "user/repos?per_page=100"


class _ArgumentParser(argparse.ArgumentParser):
    """An argument error is an input error: exit 2 through ``main``, not argparse."""

    def error(self, message: str) -> Any:
        """Raise ``message`` as a ``PolicyError``."""
        raise posture.PolicyError(message)


def _token() -> str:
    """Return the token the agents' tools use, never printing it."""
    value = github_rest.environment_token().strip()
    if value:
        return value
    executable = shutil.which("gh")
    if executable is None:
        raise posture.PolicyError(
            "no GH_TOKEN, GITHUB_TOKEN or gh to read a token from"
        )
    # The executable is resolved once, so the argv is fixed: no shell, no caller text.
    completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        [executable, "auth", "token"], capture_output=True, text=True, check=False
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or not value:
        raise posture.PolicyError("gh auth token gave no token")
    return value


def _transport(token: str) -> github.Send:
    """Return a ``send`` that makes one bounded attempt through the shared client."""
    client = github_rest.GitHubRestClient(token, user_agent="gnostoa-credential-check")
    writers = {"POST": client.post, "PUT": client.put, "PATCH": client.patch}

    def send(method: str, path: str, body: Any) -> github.Answer:
        """Send one request; a refusal comes back as an answer, never raised.

        ``path`` is relative to the API root, or a followed page's absolute URL, which
        must stay on the client's origin.
        """
        try:
            if "://" in path:
                url = github_rest.validate_url(path, client.api_root)
            else:
                url = client.url(path)
            if method == "GET":
                document, headers = client.get(url)
                return github.Answer(200, headers, "", document)
            document = writers[method](url, body or {})
            # A write probe the provider accepted: the adapter stops on it.
            return github.Answer(201, {}, "accepted", document)
        except github_rest.GitHubError as error:
            headers = {}
            if error.accepted_permissions is not None:
                headers[github.ACCEPTED_HEADER] = error.accepted_permissions
            return github.Answer(error.status, headers, str(error))

    return send


def _listed_repository(item: Any) -> str:
    """Return a listed repository's name, or raise if it cannot be probed safely.

    Skipping it would leave a repository the token can see unchecked, where an excess
    grant could hide, so a name the shared rule refuses stops the check.
    """
    name = str(item.get("full_name", "")) if isinstance(item, dict) else ""
    try:
        return github_rest.repository_name(name)
    except github_rest.InvalidRepository as error:
        raise posture.PolicyError(
            f"the listing names a repository that cannot be probed safely: {name!r}"
        ) from error


def _visible_repositories(send: github.Send) -> tuple[str, ...]:
    """Return every repository the token can see, whoever owns it, or raise."""

    def read(url: str) -> tuple[Any, Mapping[str, str]]:
        """Read one page of the listing, refusing anything but a listed page."""
        answer = send("GET", url, None)
        if answer.status != 200 or not isinstance(answer.document, list):
            raise posture.PolicyError(f"the repository listing failed: {answer.status}")
        return answer.document, answer.headers

    found: list[str] = []
    for page in github_rest.follow_pages(
        read,
        f"{github_rest.API_ROOT}/{_REPOSITORY_LISTING}",
        max_pages=_MAX_REPOSITORY_PAGES,
    ):
        found += map(_listed_repository, page)
    return tuple(found)


def _repository_facts(
    send: github.Send, repository: str
) -> tuple[bool, str | None, str]:
    """Return whether ``repository`` is public, one environment to probe, and the login."""
    answer = send("GET", f"repos/{repository}", None)
    if answer.status != 200 or not isinstance(answer.document, dict):
        raise posture.PolicyError(f"the repository {repository} could not be read")
    public = answer.document.get("private") is False
    listed = send("GET", f"repos/{repository}/environments", None)
    environments = (
        (listed.document or {}).get("environments") if listed.status == 200 else None
    )
    names = [
        str(item.get("name"))
        for item in environments or []
        if isinstance(item, dict) and item.get("name")
    ]
    user = send("GET", "user", None)
    if user.status != 200 or not isinstance(user.document, dict):
        raise posture.PolicyError("the token's user could not be read")
    login = github_rest.owner_name(str(user.document.get("login") or ""))
    return public, (min(names) if names else None), login


def _policy(raw: str) -> posture.Policy:
    """Load the declaration from inside the working tree, against its schema."""
    path = agent_review_paths.within_root(raw, Path.cwd(), must_exist=True)
    document = load_yaml(path)
    errors = schema_errors(document, SCHEMA)
    if errors:
        raise posture.PolicyError(
            f"the policy does not match {SCHEMA}: {'; '.join(errors[:5])}"
        )
    return posture.load_policy(document)


def _render(verdict: dict[str, Any]) -> str:
    """Return the verdict as text for a person."""
    kind, lifetime = verdict["credential_kind"], verdict["lifetime"]
    lines = [
        f"{'verdict':<22} {verdict['verdict']}",
        f"{'subject':<22} {verdict['subject']}",
        f"{'credential kind':<22} {kind['observed']} (declared {kind['declared']})",
        f"{'expires':<22} {lifetime['expires_at']} ({lifetime['remaining_days']} days;"
        f" at most {lifetime['max_days']})",
    ]
    lines += [
        f"{key:<22} {', '.join(verdict[key])}"
        for key in (
            "excess",
            "deficient",
            "unverified",
            "accepted_unverified",
            "minimum_unverified",
            "undeclared",
        )
        if verdict[key]
    ]
    lines.append(
        "This check grants nothing; it only reports the token's effective grants."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the check and print its verdict."""
    parser = _ArgumentParser(prog="knowledge credential-check", description=__doc__)
    parser.add_argument("--repository", required=True, help="the subject, owner/name")
    parser.add_argument("--policy", default="policy/agent-credentials.yaml")
    parser.add_argument("--json", action="store_true", help="print the verdict as JSON")
    try:
        args = parser.parse_args(argv)
        github_rest.repository_name(args.repository)
        policy = _policy(args.policy)
        if args.repository not in policy.repositories:
            raise posture.PolicyError(
                f"the declaration does not list {args.repository}; check a repository"
                " it lists"
            )
        token = _token()
        send = _transport(token)
        public, environment, login = _repository_facts(send, args.repository)
        facts = github.observe(
            send,
            repository=args.repository,
            public=public,
            environment=environment,
            visible_repositories=_visible_repositories(send),
            login=login,
            token=token,
        )
        verdict = posture.evaluate(policy, facts, utc_timestamp())
    except github.ProbeHadEffect as error:
        print(
            f"credential-check: {error}; stop and inspect the repository",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError, github_rest.GitHubError) as error:
        # ValueError covers a malformed subject (InvalidRepository) or declaration
        # (PolicyError, and the KnowledgeFormatError of a duplicate key or a missing
        # schema), a path outside the working tree, and a malformed answer.
        print(f"credential-check: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(verdict, indent=2, sort_keys=True) if args.json else _render(verdict)
    )
    return _EXIT[verdict["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
