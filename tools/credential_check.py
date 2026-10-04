"""``knowledge credential-check``: does the agents' token hold exactly its declared grants?

Decision 0101 (#362). Composes the GitHub adapter's probes with the provider-neutral
core, against the least-privilege declaration (``policy/agent-credentials.yaml`` by
default). It is read-only and non-effecting: every probe is a read, or a write aimed at
something that cannot exist, or a creation the provider must reject.

Exit status: 0 EXACT; 1 a grant beyond or below the declaration, the wrong kind of
token, or a lifetime beyond the bound; 3 UNVERIFIED (an excess grant could not be ruled
out); 2 an input or tool error. The token is read from ``GH_TOKEN`` or ``GITHUB_TOKEN``,
or else from ``gh auth token``, and is never printed.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess  # nosec B404 -- `gh auth token`, a fixed argv, no shell
import sys
from pathlib import Path
from typing import Any

import yaml

from tools import credential_posture as posture
from tools import credential_posture_github as github
from tools import github_rest

_EXIT = {
    "EXACT": 0,
    "EXCESS": 1,
    "DEFICIENT": 1,
    "TOKEN_KIND_MISMATCH": 1,
    "LIFETIME_EXCEEDED": 1,
    "UNVERIFIED": 3,
}
_MAX_REPOSITORY_PAGES = 10


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> Any:
        raise posture.PolicyError(message)


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _token() -> str:
    """Return the token the agents' tools use, never printing it."""
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    executable = shutil.which("gh")
    if executable is None:
        raise posture.PolicyError(
            "no GH_TOKEN, GITHUB_TOKEN or gh to read a token from"
        )
    completed = subprocess.run(  # nosec B603 -- fixed argv, resolved executable
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
        url = client.url(path)
        try:
            if method == "GET":
                document, headers = client.get(url)
                return github.Answer(200, headers, "", document)
            document = writers[method](url, body or {})
            # A non-effecting probe the provider accepted: report it, never hide it.
            return github.Answer(200, {}, "accepted", document)
        except github_rest.GitHubError as error:
            headers = {}
            if error.accepted_permissions is not None:
                headers[github.ACCEPTED_HEADER] = error.accepted_permissions
            return github.Answer(error.status, headers, str(error))

    return send


def _owned_repositories(send: github.Send, owner: str) -> tuple[str, ...]:
    """Return the repositories ``owner`` owns that the token can see."""
    found: list[str] = []
    for page in range(1, _MAX_REPOSITORY_PAGES + 1):
        answer = send(
            "GET", f"user/repos?affiliation=owner&per_page=100&page={page}", None
        )
        if answer.status != 200 or not isinstance(answer.document, list):
            raise posture.PolicyError(f"the repository listing failed: {answer.status}")
        names = [
            str(item.get("full_name"))
            for item in answer.document
            if isinstance(item, dict)
            and str(item.get("full_name", "")).startswith(f"{owner}/")
        ]
        found += names
        if len(answer.document) < 100:
            return tuple(found)
    raise posture.PolicyError("more owned repositories than the bound allows")


def _repository_facts(send: github.Send, repository: str) -> tuple[bool, str | None]:
    """Return whether ``repository`` is public, and one environment to probe."""
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
    return public, (sorted(names)[0] if names else None)


def _render(verdict: dict[str, Any]) -> str:
    lines = [f"{'verdict':<22} {verdict['verdict']}"]
    lines.append(
        f"{'token kind':<22} {verdict['token_kind']['observed']}"
        f" (declared {verdict['token_kind']['declared']})"
    )
    lifetime = verdict["lifetime"]
    lines.append(
        f"{'expires':<22} {lifetime['expires_at']} ({lifetime['remaining_days']} days;"
        f" at most {lifetime['max_days']})"
    )
    for key in (
        "excess",
        "deficient",
        "unverified",
        "minimum_unverified",
        "undeclared",
    ):
        if verdict[key]:
            lines.append(f"{key:<22} {', '.join(verdict[key])}")
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
        policy = posture.load_policy(
            yaml.safe_load(Path(args.policy).read_text(encoding="utf-8"))
        )
        token = _token()
        send = _transport(token)
        public, environment = _repository_facts(send, args.repository)
        facts = github.observe(
            send,
            repository=args.repository,
            public=public,
            environment=environment,
            owned_repositories=_owned_repositories(send, policy.resource_owner),
            token=token,
        )
        verdict = posture.evaluate(policy, facts, _now())
    except (posture.PolicyError, OSError, ValueError, yaml.YAMLError) as error:
        print(f"credential-check: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(verdict, indent=2, sort_keys=True) if args.json else _render(verdict)
    )
    return _EXIT[verdict["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
