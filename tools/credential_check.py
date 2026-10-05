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
import os
import shlex
import subprocess  # nosec B404 -- `gh auth token`, a fixed argv, no shell
import sys
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools import agent_review_paths, github_rest
from tools import credential_posture as posture
from tools import credential_posture_github as github
from tools.knowledge_common import (
    TRUSTED_EXECUTABLE_PATH,
    load_yaml,
    trusted_executable,
    trusted_path,
    utc_timestamp,
)
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
_GH_TIMEOUT_SECONDS = 30
_GIT_TIMEOUT_SECONDS = 30
# Where a bare `git push` may go: `branch.<name>.pushRemote`, then `remote.pushDefault`,
# then `branch.<name>.remote` (Codex on #364).
_PUSH_ROUTING = r"^(remote\.pushdefault|branch\..*\.(pushremote|remote))$"
_URL_REWRITES = r"^url\..*\.(pushinsteadof|insteadof)$"
_REPOSITORY_LISTING = "user/repos?per_page=100"


class _ArgumentParser(argparse.ArgumentParser):
    """An argument error is an input error: exit 2 through ``main``, not argparse."""

    def error(self, message: str) -> Any:
        """Raise ``message`` as a ``PolicyError``."""
        raise posture.PolicyError(message)

    def exit(self, status: int = 0, message: str | None = None) -> Any:
        """Exit, never with 0: only EXACT does, so help is not a verdict (CodeAnt on #364)."""
        if message:
            sys.stderr.write(message)
        raise SystemExit(status or 2)


def _token() -> str:
    """Return the token the agents' tools use, never printing it."""
    value = github_rest.environment_token().strip()
    if value:
        return value
    # From the trusted system directories, never from the caller's `PATH`, where a
    # shadowed `gh` would run (CodeAnt on #364).
    executable = trusted_executable("gh")
    if executable is None:
        raise posture.PolicyError(
            "no GH_TOKEN or GITHUB_TOKEN, and no gh in the trusted directories"
            f" ({TRUSTED_EXECUTABLE_PATH}) to read a token from"
        )
    # The executable is resolved once, so the argv is fixed: no shell, no caller text.
    # The host is github.com, whose token the push's credential helper answers with,
    # never the one `GH_HOST` selects (Codex on #364).
    try:
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [executable, "auth", "token", "--hostname", "github.com"],
            capture_output=True,
            text=True,
            check=False,
            # A keyring prompt or a stalled helper must not hang the check that gates
            # every first provider write (CodeRabbit on #364).
            timeout=_GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise posture.PolicyError(
            f"gh auth token timed out after {_GH_TIMEOUT_SECONDS} seconds"
        ) from error
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
            # The client's own judgement of whether a write may have landed travels
            # with the answer, so the adapter stops on it (Codex on #364). A refused
            # redirect is not a refusal of the write, so a redirected write's outcome is
            # unknown too, though the client reports the redirect as a read error.
            unknown = method != "GET" and (
                error.outcome_unknown or isinstance(error, github_rest.UnsafeRedirect)
            )
            return github.Answer(error.status, headers, str(error), None, unknown)

    return send


def _listed_repository(item: Any) -> tuple[str, bool]:
    """Return a listed repository's name, or raise if it cannot be probed safely.

    Skipping it would leave a repository the token can see unchecked, where an excess
    grant could hide, so a name the shared rule refuses stops the check.
    """
    name = str(item.get("full_name", "")) if isinstance(item, dict) else ""
    try:
        # A private repository the token can see is one it can read (CodeAnt on #364).
        return github_rest.repository_key(name), item.get("private") is not False
    except github_rest.InvalidRepository as error:
        raise posture.PolicyError(
            f"the listing names a repository that cannot be probed safely: {name!r}"
        ) from error


def _visible_repositories(send: github.Send) -> tuple[tuple[str, ...], frozenset[str]]:
    """Return every repository the token can see, and those not public, or raise."""

    def read(url: str) -> tuple[Any, Mapping[str, str]]:
        """Read one page of the listing, refusing anything but a listed page."""
        answer = send("GET", url, None)
        if answer.status != 200 or not isinstance(answer.document, list):
            raise posture.PolicyError(f"the repository listing failed: {answer.status}")
        return answer.document, answer.headers

    found: list[tuple[str, bool]] = []
    for page in github_rest.follow_pages(
        read,
        f"{github_rest.API_ROOT}/{_REPOSITORY_LISTING}",
        max_pages=_MAX_REPOSITORY_PAGES,
    ):
        found += map(_listed_repository, page)
    names = tuple(name for name, _ in found)
    return names, frozenset(name for name, private in found if private)


def _repository_facts(
    send: github.Send, repository: str
) -> tuple[bool, str | None, str]:
    """Return whether ``repository`` is public, one environment to probe, and the login."""
    answer = send("GET", f"repos/{repository}", None)
    if answer.status != 200 or not isinstance(answer.document, dict):
        raise posture.PolicyError(f"the repository {repository} could not be read")
    public = answer.document.get("private") is False
    listed = send("GET", f"repos/{repository}/environments", None)
    if listed.status != 200 or not isinstance(listed.document, dict):
        # An outage or a refusal is not "no environments" (CodeAnt on #364).
        raise posture.PolicyError(f"the environment listing failed: {listed.status}")
    environments = listed.document.get("environments")
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
    policy = posture.load_policy(document)
    # A fine-grained token reaches only its resource owner's resources, so the subject
    # proving writable shows whose token it is -- if every declared repository is the
    # declared owner's (CodeAnt on #364).
    declared = tuple(github_rest.repository_key(r) for r in policy.repositories)
    for repository in declared:
        owner = repository.split("/")[0]
        if owner != policy.resource_owner.lower():
            raise posture.PolicyError(
                f"{repository} is not the declared resource owner's"
                f" ({policy.resource_owner})"
            )
    # GitHub resolves names case-insensitively, so every name is compared on its key.
    return policy._replace(repositories=declared)


def _git(
    worktree: Path, *arguments: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the trusted git in ``worktree``, reading what a push there would read.

    The worktree is git's working directory, never an argument.
    """
    executable = trusted_executable("git")
    if executable is None:
        raise posture.PolicyError(
            f"no git in the trusted directories ({TRUSTED_EXECUTABLE_PATH})"
        )
    return subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        [executable, *arguments],
        cwd=worktree,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        timeout=_GIT_TIMEOUT_SECONDS,
    )


def _matches(worktree: Path, context: str, url: str) -> int:
    """Git's own answer whether credential ``context`` applies to ``url``: 0 if it
    does, 1 if not, anything else if git cannot say."""
    # A subsection escapes `\` and `"`, so the probe holds the context exactly.
    quoted = context.replace("\\", "\\\\").replace('"', '\\"')
    probe = f'[credential "{quoted}"]\n\thelper = matched\n'
    return _git(
        worktree,
        "config",
        "--file",
        "-",
        "--get-urlmatch",
        "credential.helper",
        url,
        stdin=probe,
    ).returncode


def _applies(worktree: Path, key: str, target: str) -> bool | None:
    """Whether credential config ``key`` applies to ``target``; None if not judged.

    Git matches a context after normalizing it (scheme and host in any case, a default
    port, percent-encoding), so git, not this check, decides (Codex and CodeAnt on
    #364).
    """
    if key == "credential.helper":
        return True
    context = key.removeprefix("credential.").removesuffix(".helper")
    if context.startswith("-"):
        # Never an option on git's command line.
        return None
    if _matches(worktree, context, context) != 0:
        # Git cannot normalize it as a URL (a wildcard, a scheme-less or partial
        # context), yet a push may match it, by rules this check does not model: fail
        # closed.
        return None
    applies = _matches(worktree, context, target)
    return None if applies not in (0, 1) else applies == 0


def _effective_helpers(worktree: Path, target: str) -> list[str] | None:
    """Git's credential helpers for ``target``, in order; an empty one resets them."""
    listed = _git(
        worktree, "config", "--null", "--get-regexp", r"^credential\..*helper$"
    )
    if listed.returncode not in (0, 1):
        return None
    helpers: list[str] = []
    for entry in filter(None, listed.stdout.split("\0")):
        key, _, value = entry.partition("\n")
        applies = _applies(worktree, key, target)
        if applies is None:
            return None
        if applies:
            helpers = [] if value == "" else [*helpers, value]
    return helpers


def _is_trusted_gh(helper: str) -> bool:
    """Whether ``helper`` is exactly the trusted gh's credential helper."""
    gh = trusted_executable("gh")
    if gh is None or not helper.startswith("!"):
        return False
    words = shlex.split(helper[1:])
    # Git runs the helper's own path, not its target, so the path itself must be one no
    # one can repoint (Codex on #364).
    return (
        len(words) == 3
        and words[1:] == ["auth", "git-credential"]
        and trusted_path(words[0]) == gh
    )


def _checkout(worktree: str) -> Path:
    """Return the checkout whose pushes are bound, as an existing directory, or raise."""
    resolved = Path(worktree).resolve()
    if not resolved.is_dir():
        raise posture.PolicyError(f"the worktree {worktree!r} is not a directory")
    return resolved


def _pushed_target(pushed: str, subject: str) -> tuple[str | None, str]:
    """Return the github.com URL a push to ``pushed`` reaches for ``subject``, or None
    and why it is not one."""
    url = urllib.parse.urlsplit(pushed)
    try:
        port = url.port
    except ValueError:
        return None, "a push URL has a malformed port"
    if url.scheme != "https" or (url.hostname or "").lower() != "github.com":
        return None, "a push URL is not HTTPS to github.com"
    # Another port would escape a port-scoped header or helper, and not reach GitHub's
    # own service (CodeAnt on #364).
    if port not in (None, 443):
        return None, "a push URL names a port other than HTTPS's"
    if url.username or url.password:
        return None, "a push URL carries a credential of its own"
    path = url.path.strip("/")
    try:
        named = github_rest.repository_key(path.removesuffix(".git"))
    except github_rest.InvalidRepository:
        return None, "a push URL names no repository"
    if named != subject:
        return None, f"a push URL names {named}, not {subject}"
    # Git looks configuration up by the URL it pushes to, `.git` and all (CodeAnt on
    # #364).
    return f"https://github.com/{path}", ""


def _url_binding(worktree: Path, pushed: str, subject: str) -> tuple[str, str]:
    """Whether a push to the URL ``pushed`` uses the checked token."""
    target, why = _pushed_target(pushed, subject)
    if target is None:
        return "UNBOUND", why
    try:
        header = _git(worktree, "config", "--get-urlmatch", "http.extraheader", target)
        helpers = _effective_helpers(worktree, target)
    except (posture.PolicyError, OSError, subprocess.TimeoutExpired) as error:
        # Every read after the push URL fails closed too (gitar on #364).
        return "UNKNOWN", f"git could not be read: {error}"
    if header.returncode not in (0, 1):
        return "UNKNOWN", "the extra HTTP headers for a push URL could not be read"
    if header.returncode == 0 and header.stdout.strip():
        return "UNBOUND", "an extra HTTP header is configured for a push URL"
    if helpers is None:
        return "UNKNOWN", "Git's credential helpers for a push URL could not be judged"
    if len(helpers) != 1 or not _is_trusted_gh(helpers[0]):
        return "UNBOUND", (
            "Git's credential helpers for a push URL are not exactly the trusted gh"
            f" ({len(helpers)} configured)"
        )
    return "BOUND", "HTTPS push through the trusted gh's credential helper"


def _push_destinations(worktree: Path) -> tuple[list[str], list[str]] | str:
    """Every remote, and every URL push routing names directly, a push could reach;
    or why they cannot be judged.

    The names are git's own answer, never a caller's value (SonarCloud S8705 on #364);
    `.`, a branch's local upstream, is no remote.
    """
    listed = _git(worktree, "remote")
    routed = _git(worktree, "config", "--null", "--get-regexp", _PUSH_ROUTING)
    if listed.returncode != 0 or routed.returncode not in (0, 1):
        return "Git's remotes and push routing could not be read"
    remotes = listed.stdout.split()
    urls = []
    for entry in filter(None, routed.stdout.split("\0")):
        value = entry.partition("\n")[2]
        if value and value != "." and value not in remotes:
            urls.append(value)
    if urls:
        # A remote's URLs come back already rewritten; a routed URL is the raw value,
        # which a rewrite rule could send elsewhere (gitar on #364).
        rewrites = _git(worktree, "config", "--get-regexp", _URL_REWRITES)
        if rewrites.returncode not in (0, 1) or rewrites.stdout.strip():
            return "a push-routed URL could be rewritten by insteadOf or pushInsteadOf"
    return remotes, urls


def _push_binding(worktree: Path, subject: str) -> tuple[str, str]:
    """Whether every push of ``subject`` from ``worktree`` uses the checked token.

    A bare push may go to any remote push routing selects, so every remote's push URLs,
    and every URL routing names directly, must be HTTPS to github.com for the subject
    with no credential in them, no extra header configured, and Git's effective
    credential helpers exactly the trusted gh, which answers with the token this check
    read. Only configuration is read, never a credential (Codex on #364).
    """
    if os.environ.get("GIT_EXEC_PATH"):
        # It chooses which `git-remote-https` a push runs: another transport than the
        # one checked (Codex on #364).
        return (
            "UNBOUND",
            "GIT_EXEC_PATH is set, so it chooses the transport a push runs",
        )
    try:
        destinations = _push_destinations(worktree)
        if isinstance(destinations, str):
            return "UNKNOWN", destinations
        remotes, urls = destinations
        for remote in remotes:
            if remote.startswith("-"):
                return "UNKNOWN", "a remote's name could be read as an option"
            pushed = _git(worktree, "remote", "get-url", "--push", "--all", remote)
            if pushed.returncode != 0:
                return (
                    "UNKNOWN",
                    f"the push URLs of the remote {remote!r} could not be read",
                )
            # Git pushes to every configured push URL, not only the first.
            urls += pushed.stdout.split()
    except (posture.PolicyError, OSError, subprocess.TimeoutExpired) as error:
        return "UNKNOWN", f"git could not be read: {error}"
    if not urls:
        return "UNKNOWN", "the checkout has no remote to push to"
    for url in urls:
        state, evidence = _url_binding(worktree, url, subject)
        if state != "BOUND":
            return state, evidence
    return "BOUND", (
        f"every push URL ({len(urls)}, from {len(remotes)} remotes and push routing)"
        " goes through the trusted gh's credential helper"
    )


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
    parser.add_argument(
        "--worktree", default=".", help="the checkout whose pushes the check binds"
    )
    try:
        args = parser.parse_args(argv)
        worktree = _checkout(args.worktree)
        policy = _policy(args.policy)
        subject = github_rest.repository_key(args.repository)
        if subject not in policy.repositories:
            raise posture.PolicyError(
                f"the declaration does not list {args.repository}; check a repository"
                " it lists"
            )
        token = _token()
        send = _transport(token)
        public, environment, login = _repository_facts(send, subject)
        visible, private = _visible_repositories(send)
        facts = github.observe(
            send,
            repository=subject,
            public=public,
            environment=environment,
            visible_repositories=visible,
            login=login,
            token=token,
            private_repositories=private,
            resource_owner=policy.resource_owner,
        )
        facts = facts._replace(transport=_push_binding(worktree, subject))
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
