"""Obtain the guarded merge's own admission result (#407, MA0 slice 1b.4).

F1 part 3 (the Decisions Router on #426, 6130207025): after the owner's exact-head
approval and step 8's other reads, the merge procedure obtains a current admission
result of its own instead of relying on the check's last publication. This command:

1. refuses unless it runs from a checkout of protected `main`, and the pull request
   is open, targets `main` and has the approved head;
2. requests the protected `merge-admission.yml` for that pull request by
   `repository_dispatch` (G1, #426 6132395441), with a fresh 128-bit nonce. GitHub
   answers with an empty `204` and names no run, so the nonce is the correlation,
   never time;
3. finds this dispatch's record as the pinned App's latest `merge-admission` run on
   the approved head carrying the nonce, beside the workflow run, attempt and
   protected revision that wrote it (`tools.merge_admission_checks`). A newer record
   without the nonce refuses;
4. reads that workflow run natively, and refuses unless it is the protected workflow,
   dispatched, on `main` at the protected revision, at that attempt, and succeeded;
   then re-reads the record, which must still be the latest and a completed success;
5. re-reads the subject, rebuilding its evidence through the function the workflow's
   command calls (without the analyzer bundle it cannot re-read), and refuses unless
   its digest is the one the run recorded; and re-reads the open population,
   refusing unless this pull request is alone at its head (H1);
6. re-reads the pull request and `main` last, and refuses if either moved.

It never merges: step 8's `--match-head-commit` merge follows it at once. What is left
is the window from those last reads to the provider's merge, and an analyzer change
after the run's readback, recorded in Decision 0112.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import secrets
import shutil
import subprocess  # nosec B404 -- git alone, by its absolute trusted path, with fixed arguments
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Run as `python3 -I ci/merge_admission_guard.py` (runbook `guard_merge`), so no file of
# the checkout runs at interpreter startup: the checkout joins the path only here.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools import github_rest  # noqa: E402
from tools.merge_admission_checks import (  # noqa: E402
    CHECK_NAME,
    PublicationError,
    app_latest,
    correlation_of,
    digest,
    matches,
    ours,
    read_run,
    run_id,
)

if TYPE_CHECKING:
    from tools import review_current_state_surface as surface

_WORKFLOW = ".github/workflows/merge-admission.yml"
_DISPATCH_TYPE = "gnostoa-merge-admission"
# What a record names of the run that wrote it.
_IDENTITY = ("workflow_run_id", "run_attempt", "protected_revision", "nonce")
_PROTECTED = "main"
_SHA40 = re.compile(r"[0-9a-f]{40}")
# Git runs no program a configuration names: no file-system monitor, no hook.
_NO_PROGRAMS = ("-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null")
# The executable search path the preparation helper trusts (AGENTS.md).
TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
_POLICY = github_rest.Policy(
    timeout_seconds=30, attempts=3, max_response_bytes=4_194_304
)


class Refused(RuntimeError):
    """The guarded merge must not proceed."""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read(client: Any, path: str) -> Mapping[str, Any]:
    try:
        document, _ = client.get(client.url(path))
    except github_rest.GitHubError as exc:
        raise Refused(f"{path} could not be read: {exc}") from exc
    if not isinstance(document, Mapping):
        raise Refused(f"{path} reads back as no object")
    return document


def _pull(client: Any, repository: str, number: int, approved: str) -> None:
    pull = _read(client, f"repos/{repository}/pulls/{number}")
    head, base = _mapping(pull.get("head")), _mapping(pull.get("base"))
    if (
        pull.get("number") != number
        or pull.get("state") != "open"
        or head.get("sha") != approved
        or base.get("ref") != _PROTECTED
    ):
        raise Refused(
            f"the pull request is not #{number}, open, on {_PROTECTED} at {approved}"
        )


def _main(client: Any, repository: str) -> str:
    branch = _read(client, f"repos/{repository}/branches/{_PROTECTED}")
    sha = _mapping(branch.get("commit")).get("sha")
    if not isinstance(sha, str) or _SHA40.fullmatch(sha) is None:
        raise Refused(f"protected {_PROTECTED} reads back with no revision")
    return sha


def fresh_nonce() -> str:
    """A fresh, unpredictable 128-bit nonce for one guarded dispatch (G1)."""

    return secrets.token_hex(16)


def _dispatch(client: Any, repository: str, number: int, nonce: str) -> None:
    """Request the protected admission by `repository_dispatch`, with the App's own
    `contents: write` (G1, #426 6132395441). GitHub accepts it with an empty `204`
    and names no run. A lost answer is reconciled by the nonce, never sent again."""

    try:
        client.post_accepted(
            client.url(f"repos/{repository}/dispatches"),
            {
                "event_type": _DISPATCH_TYPE,
                "client_payload": {"pull_number": number, "nonce": nonce},
            },
        )
    except github_rest.GitHubWriteError as exc:
        if not exc.outcome_unknown:
            raise Refused(f"the dispatch was refused: {exc}") from exc
    except github_rest.GitHubError as exc:
        raise Refused(f"the dispatch was refused: {exc}") from exc


def _latest_record(
    client: Any, repository: str, approved: str, app_id: int
) -> tuple[Mapping[str, Any] | None, dict[str, Any] | None]:
    try:
        latest = app_latest(client, repository, approved, app_id)
    except PublicationError as exc:
        raise Refused(f"the check could not be read: {exc}") from exc
    return latest, (correlation_of(latest) if latest is not None else None)


def _discover(
    client: Any,
    repository: str,
    approved: str,
    app_id: int,
    nonce: str,
    *,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    poll_seconds: float,
    deadline: float,
) -> dict[str, Any]:
    """This dispatch's completed record, found as the pinned App's latest run on the
    head carrying the nonce. A pending record names the run early. Once this nonce
    has been seen, a newer record without it means this dispatch no longer stands:
    nothing falls back to it, and nothing is chosen by time."""

    seen = False
    while True:
        latest, record = _latest_record(client, repository, approved, app_id)
        if record is not None and record["nonce"] == nonce:
            seen = True
            if latest is not None and latest.get("status") == "completed":
                return record
        elif seen:
            raise Refused("this dispatch's record was overtaken by a newer run")
        if clock() >= deadline:
            raise Refused(
                "the admission did not complete in time"
                if seen
                else "no record of this dispatch appeared in time"
            )
        sleep(poll_seconds)


def _await(
    client: Any,
    repository: str,
    workflow_run: int,
    *,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    poll_seconds: float,
    deadline: float,
) -> Mapping[str, Any]:
    while True:
        run = _read(client, f"repos/{repository}/actions/runs/{workflow_run}")
        if run.get("status") == "completed":
            return run
        if clock() >= deadline:
            raise Refused(f"workflow run {workflow_run} did not complete in time")
        sleep(poll_seconds)


def _protected_run(
    run: Mapping[str, Any],
    repository: str,
    record: Mapping[str, Any],
    revision: str,
) -> None:
    workflow_run = record["workflow_run_id"]
    expected = {
        "id": workflow_run,
        "path": _WORKFLOW,
        "event": "repository_dispatch",
        "head_branch": _PROTECTED,
        "head_sha": revision,
        "run_attempt": record["run_attempt"],
        "conclusion": "success",
    }
    wrong = sorted(
        field for field, value in expected.items() if not matches(run, {field: value})
    )
    if _mapping(run.get("repository")).get("full_name") != repository:
        wrong.append("repository")
    if wrong:
        raise Refused(
            f"workflow run {workflow_run} is not the protected admission run: {wrong}"
        )


def _admitted(
    client: Any,
    repository: str,
    approved: str,
    app_id: int,
    record: Mapping[str, Any],
) -> tuple[int, str]:
    """The record re-read: still the pinned App's latest run on the head, read again
    by its id, a completed success carrying exactly this dispatch's correlation and
    the evaluation's digest."""

    latest, current = _latest_record(client, repository, approved, app_id)
    if latest is None or current is None:
        raise Refused("this dispatch's check is no longer the latest")
    identifier = run_id(latest)
    if identifier is None:
        raise Refused("the pinned App's check has no id")
    try:
        check = read_run(client, repository, identifier)
    except PublicationError as exc:
        raise Refused(f"the check could not be read: {exc}") from exc
    expected = {
        "id": identifier,
        "name": CHECK_NAME,
        "head_sha": approved,
        "status": "completed",
        "conclusion": "success",
    }
    if not ours(check, app_id) or not matches(check, expected):
        raise Refused("the check is not the pinned App's completed success on the head")
    recorded = correlation_of(check)
    if recorded is None or any(recorded[field] != record[field] for field in _IDENTITY):
        raise Refused("the check does not correlate with this dispatch's run")
    digest_recorded = recorded["unbundled_evidence_sha256"]
    if not isinstance(digest_recorded, str):
        raise Refused("the check records no evidence digest")
    return identifier, digest_recorded


def _unchanged(
    rebuilt: Any, recorded: str, repository: str, number: int, approved: str
) -> None:
    subject = _mapping(_mapping(rebuilt).get("subject"))
    request = _mapping(subject.get("change_request"))
    if (
        request.get("id") != str(number)
        or subject.get("head_commit") != approved
        or subject.get("repository") != f"https://github.com/{repository}"
    ):
        raise Refused("the rebuilt evidence names another subject")
    if digest(rebuilt) != recorded:
        raise Refused("the subject changed since the evaluation")


def _alone(population: Any, number: int, approved: str) -> None:
    pulls = population.get("pulls") if isinstance(population, Mapping) else None
    if not isinstance(pulls, list) or population.get("coverage") != "COMPLETE":
        raise Refused("the open population is not complete")
    heads = {
        item.get("pull_number"): item.get("head")
        for item in pulls
        if isinstance(item, Mapping)
    }
    if heads.get(number) != approved:
        raise Refused("the open population does not show this pull request at its head")
    sharing = sorted(str(pull) for pull, head in heads.items() if head == approved)
    if len(sharing) != 1:
        raise Refused(f"the head is shared by #{', #'.join(sharing)}")


def guard(
    client: Any,
    *,
    repository: str,
    pull_number: int,
    approved: str,
    app_id: int,
    checkout_revision: str,
    rebuild: Callable[[], Any],
    population: Callable[[], Any],
    nonce: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    poll_seconds: float = 15.0,
    # The admission's critical path, each job's own limit, and a 5-minute margin: a
    # deadline refusal means the run did not finish within its limits (CodeAnt on
    # #426). The path is 75 minutes since the call runs the inventory, then the
    # readback that needs it (#389 A0-MP1 slice 3, the owner's
    # OWNER-389-S3-MA0-TIMING-SCOPE): a ceiling, not a target or a queue's wait.
    deadline_seconds: float = 4800.0,
) -> dict[str, Any]:
    """PROCEED only for a current, correlated admission of the approved head."""

    _pull(client, repository, pull_number, approved)
    revision = _main(client, repository)
    if checkout_revision != revision:
        raise Refused(
            f"the guard's checkout is {checkout_revision}, not protected {_PROTECTED} {revision}"
        )
    nonce = nonce or fresh_nonce()
    deadline = clock() + deadline_seconds
    _dispatch(client, repository, pull_number, nonce)
    record = _discover(
        client,
        repository,
        approved,
        app_id,
        nonce,
        sleep=sleep,
        clock=clock,
        poll_seconds=poll_seconds,
        deadline=deadline,
    )
    if record["protected_revision"] != revision:
        raise Refused("the check does not correlate with this dispatch's run")
    run = _await(
        client,
        repository,
        record["workflow_run_id"],
        sleep=sleep,
        clock=clock,
        poll_seconds=poll_seconds,
        deadline=deadline,
    )
    _protected_run(run, repository, record, revision)
    check, recorded = _admitted(client, repository, approved, app_id, record)
    try:
        rebuilt, observed = rebuild(), population()
    except (github_rest.GitHubError, ValueError, OSError) as exc:
        # An unreadable or invalid re-read, a policy file included, refuses with its
        # reason (Kilo on #426).
        raise Refused(f"the subject could not be re-read: {exc}") from exc
    _unchanged(rebuilt, recorded, repository, pull_number, approved)
    _alone(observed, pull_number, approved)
    # Read once more after the evidence, by the same rule: a check's id does not
    # freeze its contents, so the run must still be this dispatch's completed success
    # recording the digest the evidence matched (the PAO and CodeAnt on #426).
    if _admitted(client, repository, approved, app_id, record) != (check, recorded):
        raise Refused("this dispatch's admission changed during the evidence reads")
    _pull(client, repository, pull_number, approved)
    if _main(client, repository) != revision:
        raise Refused(f"protected {_PROTECTED} moved during the guard")
    return {
        "result": "PROCEED",
        "workflow_run_id": record["workflow_run_id"],
        "check_run_id": check,
        "protected_revision": revision,
    }


def _client(token: str) -> Any:
    return github_rest.GitHubRestClient(
        token, user_agent="gnostoa-merge-admission-guard", policy=_POLICY
    )


def _git(root: Path, *arguments: str) -> str:
    """Run git, found on the trusted path and run by its absolute name. Its
    environment is an allowlist, so no credential reaches it under any name, and it
    loads no global or system configuration. The monitor and hooks a local
    configuration names are disabled, so git runs no other program (Codex on #426;
    AGENTS.md's trusted retrieval)."""

    executable = shutil.which("git", path=TRUSTED_PATH)
    if executable is None:
        raise Refused("git is unavailable on the trusted path")
    environment = {
        "PATH": TRUSTED_PATH,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_COUNT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    try:
        # Audited: no shell, an absolute executable, and fixed arguments only.
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [executable, *_NO_PROGRAMS, *arguments],
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Refused(f"the checkout could not be read: {exc}") from exc
    return str(completed.stdout)


def read_checkout_revision(root: Path) -> str:
    """The checkout's revision, refused when its files differ from it: a changed
    tracked file, an untracked one, such as a stray decision the rebuild would read,
    or an ignored one, such as a `*.pyc` (CodeAnt and Codex on #426)."""

    head = _git(root, "rev-parse", "HEAD").strip()
    if _git(root, "status", "--porcelain", "--untracked-files=all", "--ignored"):
        raise Refused("the checkout is not exactly its revision")
    return head


def rebuilders(
    token: str, repository: str, number: int, root: Path
) -> tuple[Callable[[], Any], Callable[[], Any]]:
    """The re-reads the workflow's own commands make, in process: L1's snapshot with
    merge evidence, the evidence built from it, and L1's open population."""

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    # ci remains flat CLI scripts, and the two type checkers name this sibling
    # differently: the project's gate as a top-level module, the protected collector
    # by its path from the root (#389 F1). Imported by its name at run time, as the
    # statement this replaces did, and typed by the surface L1 checks itself against.
    l1: surface.Surface = importlib.import_module("review_github_current_state")

    from tools import merge_evidence_github

    # Built as L1's own command builds it, from the token alone (CodeAnt and Kilo on
    # #426: its constructor takes no other option).
    reader = l1.GitHubRestClient(token)

    def rebuild() -> Any:
        snapshot = l1.collect_snapshot(
            reader,
            repository=repository,
            pull_number=number,
            observed_at=None,
            merge_evidence=True,
        )
        return merge_evidence_github.evidence_for(snapshot, project_root=root)

    def population() -> Any:
        return {
            "coverage": "COMPLETE",
            "pulls": [
                {"pull_number": item["number"], "head": item["head_sha"]}
                for item in l1.open_pulls(reader, repository)
            ],
        }

    return rebuild, population


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-number", type=int, required=True)
    parser.add_argument("--approved", required=True)
    parser.add_argument("--app-id", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("GH_TOKEN", "")
    if not token or _SHA40.fullmatch(args.approved) is None or args.app_id <= 0:
        print(
            "ERROR: the guard needs GH_TOKEN, an exact approved head and the App's id",
            file=sys.stderr,
        )
        return 2
    root = Path.cwd()
    try:
        client = _client(token)
        rebuild, population = rebuilders(token, args.repository, args.pull_number, root)
        result = guard(
            client,
            repository=args.repository,
            pull_number=args.pull_number,
            approved=args.approved,
            app_id=args.app_id,
            checkout_revision=read_checkout_revision(root),
            rebuild=rebuild,
            population=population,
        )
    except Refused as exc:
        print(json.dumps({"result": "REFUSED", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
