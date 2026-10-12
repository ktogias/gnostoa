"""Obtain the guarded merge's own admission result (#407, MA0 slice 1b.4).

F1 part 3 (the Decisions Router on #426, 6130207025): after the owner's exact-head
approval and step 8's other reads, the merge procedure obtains a current admission
result of its own instead of relying on the check's last publication. This command:

1. refuses unless it runs from a checkout of protected `main`, and the pull request
   is open, targets `main` and has the approved head;
2. dispatches the protected `merge-admission.yml` for that pull request, and takes the
   workflow run the dispatch answers with: the correlation is that run, never time;
3. waits for the run, and refuses unless it is that workflow, dispatched, on `main` at
   the protected revision, and succeeded;
4. reads the pinned App's latest `merge-admission` run on the approved head natively,
   and refuses unless it is a completed success that names that workflow run, its
   attempt and the protected revision (`tools.merge_admission_checks`);
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
import json
import os
import re
import shutil
import subprocess  # nosec B404 -- git alone, by its absolute trusted path, with fixed arguments
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from tools import github_rest
from tools.merge_admission_checks import (
    CHECK_NAME,
    PublicationError,
    app_latest,
    correlation_of,
    digest,
    ours,
    read_run,
    run_id,
)

_WORKFLOW = ".github/workflows/merge-admission.yml"
_PROTECTED = "main"
_SHA40 = re.compile(r"[0-9a-f]{40}")
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


def _dispatch(client: Any, repository: str, number: int) -> int:
    url = client.url(
        f"repos/{repository}/actions/workflows/merge-admission.yml/dispatches"
    )
    try:
        answer = client.post(
            url, {"ref": _PROTECTED, "inputs": {"pull_number": str(number)}}
        )
    except github_rest.GitHubError as exc:
        raise Refused(f"the dispatch failed: {exc}") from exc
    identifier = answer.get("workflow_run_id") if isinstance(answer, Mapping) else None
    if type(identifier) is not int or identifier <= 0:
        raise Refused("the dispatch named no workflow run to correlate")
    return identifier


def _await(
    client: Any,
    repository: str,
    workflow_run: int,
    *,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    poll_seconds: float,
    deadline_seconds: float,
) -> Mapping[str, Any]:
    deadline = clock() + deadline_seconds
    while True:
        run = _read(client, f"repos/{repository}/actions/runs/{workflow_run}")
        if run.get("status") == "completed":
            return run
        if clock() >= deadline:
            raise Refused(f"workflow run {workflow_run} did not complete in time")
        sleep(poll_seconds)


def _protected_run(run: Mapping[str, Any], workflow_run: int, revision: str) -> int:
    expected = {
        "id": workflow_run,
        "path": _WORKFLOW,
        "event": "workflow_dispatch",
        "head_branch": _PROTECTED,
        "head_sha": revision,
        "conclusion": "success",
    }
    wrong = sorted(
        field for field, value in expected.items() if run.get(field) != value
    )
    if wrong:
        raise Refused(
            f"workflow run {workflow_run} is not the protected admission run: {wrong}"
        )
    attempt = run.get("run_attempt")
    if type(attempt) is not int or attempt <= 0:
        raise Refused(f"workflow run {workflow_run} names no attempt")
    return attempt


def _admitted(
    client: Any,
    repository: str,
    approved: str,
    app_id: int,
    correlation: Mapping[str, Any],
) -> tuple[int, str]:
    try:
        latest = app_latest(client, repository, approved, app_id)
        if latest is None:
            raise Refused("the pinned App has no check on the approved head")
        identifier = run_id(latest)
        if identifier is None:
            raise Refused("the pinned App's check has no id")
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
    if not ours(check, app_id) or any(
        check.get(field) != value for field, value in expected.items()
    ):
        raise Refused("the check is not the pinned App's completed success on the head")
    recorded = correlation_of(check)
    if recorded is None or any(
        recorded[field] != value for field, value in correlation.items()
    ):
        raise Refused("the check does not correlate with this dispatch's run")
    return identifier, str(recorded["unbundled_evidence_sha256"])


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
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    poll_seconds: float = 15.0,
    deadline_seconds: float = 1800.0,
) -> dict[str, Any]:
    """PROCEED only for a current, correlated admission of the approved head."""

    _pull(client, repository, pull_number, approved)
    revision = _main(client, repository)
    if checkout_revision != revision:
        raise Refused(
            f"the guard's checkout is {checkout_revision}, not protected {_PROTECTED} {revision}"
        )
    workflow_run = _dispatch(client, repository, pull_number)
    run = _await(
        client,
        repository,
        workflow_run,
        sleep=sleep,
        clock=clock,
        poll_seconds=poll_seconds,
        deadline_seconds=deadline_seconds,
    )
    attempt = _protected_run(run, workflow_run, revision)
    check, recorded = _admitted(
        client,
        repository,
        approved,
        app_id,
        {
            "workflow_run_id": workflow_run,
            "run_attempt": attempt,
            "protected_revision": revision,
        },
    )
    try:
        rebuilt, observed = rebuild(), population()
    except (github_rest.GitHubError, ValueError) as exc:
        # An unreadable or invalid re-read refuses with its reason (Kilo on #426).
        raise Refused(f"the subject could not be re-read: {exc}") from exc
    _unchanged(rebuilt, recorded, repository, pull_number, approved)
    _alone(observed, pull_number, approved)
    _pull(client, repository, pull_number, approved)
    if _main(client, repository) != revision:
        raise Refused(f"protected {_PROTECTED} moved during the guard")
    return {
        "result": "PROCEED",
        "workflow_run_id": workflow_run,
        "check_run_id": check,
        "protected_revision": revision,
    }


def _client(token: str) -> Any:
    return github_rest.GitHubRestClient(
        token, user_agent="gnostoa-merge-admission-guard", policy=_POLICY
    )


def _git(root: Path, *arguments: str) -> str:
    """Run git, found on the trusted path and run by its absolute name, with no
    caller Git routing or configuration in its environment."""

    executable = shutil.which("git", path=TRUSTED_PATH)
    if executable is None:
        raise Refused("git is unavailable on the trusted path")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    try:
        # Audited: no shell, an absolute executable, and fixed arguments only.
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [executable, *arguments],
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


def _checkout_revision(root: Path) -> str:
    """The checkout's revision, refused when its files differ from it: a changed
    tracked file, or an untracked one, such as a stray decision the rebuild would
    read (CodeAnt on #426)."""

    head = _git(root, "rev-parse", "HEAD").strip()
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise Refused("the checkout is not exactly its revision")
    return head


def _rebuilders(
    repository: str, number: int, root: Path
) -> tuple[Callable[[], Any], Callable[[], Any]]:
    """The re-reads the workflow's own commands make, in process: L1's snapshot with
    merge evidence, the evidence built from it, and L1's open population."""

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import review_github_current_state as l1

    from tools import merge_evidence_github

    reader = l1.GitHubRestClient.from_environment(
        user_agent="gnostoa-merge-admission-guard"
    )

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
                # skipcq: PYL-W0212 -- L1's one enumeration, reused rather than copied
                for item in l1._open_pulls(reader, repository)
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
        rebuild, population = _rebuilders(args.repository, args.pull_number, root)
        result = guard(
            client,
            repository=args.repository,
            pull_number=args.pull_number,
            approved=args.approved,
            app_id=args.app_id,
            checkout_revision=_checkout_revision(root),
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
