"""Publish the merge-admission verdict as a check run (#407, MA0 slice 1b.4).

Decision 0112 item 5: a dedicated App, `gnostoa-ma0`, posts `merge-admission` from a
main-only environment, woken by Decision 0096's relay and a sweep. This command never
decides admission. It publishes the existing verdict (`knowledge merge-admission`) on
the exact head that verdict was evaluated for, and only while the evidence it rests on
is unchanged: the workflow evaluates, reads a second snapshot and rebuilds the
evidence from it, and the two are compared, observation times aside.

Four commands, run by the privileged workflow (F1, the Decisions Router on #426):

- `hint` names the pull request a relayed PR conversation comment is on. It is a hint
  only: L1 re-reads the subject.
- `dispatch-hint` names the pull request and the nonce a guarded merge's
  `repository_dispatch` carries (G1), exactly, or refuses. The nonce is recorded
  beside the run's own identity, so the guard finds this run; it grants nothing.
- `invalidate` runs before anything is acquired again. A success the App published on
  the head stops standing: a pending run of the App replaces it until this workflow
  run completes it.
- `publish` completes that pending run while it is the App's latest run. Without one,
  a success is written only while the latest run is still the one observed at
  invalidation. A superseded, incomplete or denied evaluation never ends as a success,
  and never leaves an older one standing.

A check run belongs to a commit, not to a pull request, so a success is planned only
when the complete open population shows this pull request alone at its head (H1 on
#426): a shared head is a failure naming the pull requests. Each run records the
workflow run, attempt and protected revision that wrote it, and the digest of the
evidence rebuilt without the analyzer bundle, which the guarded merge re-reads.

No path comes from the command line: the commands read and write fixed names under
the runner's `RUNNER_TEMP`, and take the run's identity from the runner. Without the
App's token the run is a shadow: it records its plan and writes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools import github_rest
from tools.agent_review_admission import Refused, read_payload
from tools.agent_review_github import DELIVERED_EVENT_BYTES
from tools.agent_review_report import neutralise
from tools.github_events import delivered_comment_pull_number
from tools.merge_admission_checks import (
    CHECK_NAME,
    NONCE,
    PublicationError,
    app_latest,
    canonical,
    comparable,
    correlation_text,
    digest,
    matches,
    ours,
    read_run,
    run_id,
)
from tools.verdict_cli import read_json_file

_APP_CREDENTIAL_VARIABLE = "GNOSTOA_MA0_TOKEN"
_SHA40 = re.compile(r"[0-9a-f]{40}")
_VERDICT_SCHEMA = "gnostoa-merge-admission/v1"
_SUBJECT_KIND = "github-pull-request"
# GitHub's limits for a check run's output.
_MAX_TITLE = 255
_MAX_SUMMARY = 60_000
# Room the summary keeps around an inert block: its lines, the fence and the cut marker.
_SUMMARY_FRAME = 1_024
_WORK = "gnostoa-merge-admission"
_RELAYED = "gnostoa-merge-admission-relay"
_DISPATCH_TYPE = "gnostoa-merge-admission"
_POLICY = github_rest.Policy(
    timeout_seconds=30, attempts=1, max_response_bytes=4_194_304
)

__all__ = ["CHECK_NAME", "PublicationError", "invalidate", "main", "plan", "publish"]


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "\n\n… (cut at GitHub's limit; the run's artifact keeps the whole verdict)"
    return text[: limit - len(marker)] + marker


def _well_formed(verdict: Mapping[str, Any]) -> bool:
    return (
        verdict.get("schema") == _VERDICT_SCHEMA
        and verdict.get("status") in {"ALLOW", "DENY"}
        and isinstance(verdict.get("criteria"), list)
    )


def _denial(verdict: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    failing = [
        criterion
        for criterion in verdict["criteria"]
        if isinstance(criterion, Mapping) and criterion.get("status") == "FAIL"
    ]
    names = ", ".join(str(criterion.get("id")) for criterion in failing)
    reasons = "\n".join(
        f"{criterion.get('id')}: "
        + "; ".join(str(reason) for reason in criterion.get("reasons") or [])
        for criterion in failing
    )
    lines = ["The failing criteria and their reasons:", "", _inert(reasons)]
    return "failure", f"merge-admission: DENY ({names})", lines


def _inert(text: str) -> str:
    """Contributor-controlled text, such as the paths a reason names, in a fence no
    line of it can close: a check run's summary is Markdown, so a crafted name makes
    no link or image (CodeAnt on #426).

    The block is bounded whole, fences included, so the summary's own bound never
    cuts inside it. A fence is one backtick longer than the longest run the text
    holds, so a block can be several times its text (Kilo on #426): if the text cut
    to the budget, less the shortest fences, does not fit, the text cut to a third of
    it always does, as a block is at most three times its text and a few
    characters."""

    budget = _MAX_SUMMARY - _SUMMARY_FRAME
    # The shortest fences and the info string take 12 characters: room for them.
    block = neutralise(_bounded(text, budget - 16))
    if len(block) <= budget:
        return block
    return neutralise(_bounded(text, (budget - 16) // 3))


def _verdict_state(
    subject: Mapping[str, Any], verdict: object, verdict_exit: int
) -> tuple[str, str, list[str]]:
    """The conclusion, title and summary lines. Only a well-formed ALLOW for this
    exact subject, from a command that exited 0, is ever a success."""

    if not isinstance(verdict, Mapping) or not _well_formed(verdict):
        return (
            "failure",
            "merge-admission: the evaluation produced no verdict",
            ["No verdict exists for this exact head, so nothing is admitted."],
        )
    if verdict.get("subject") != subject:
        return (
            "failure",
            "merge-admission: the verdict names another subject",
            ["The verdict is not for this repository, pull request and head."],
        )
    if verdict["status"] == "ALLOW" and verdict_exit == 0:
        return (
            "success",
            "merge-admission: ALLOW",
            ["Every applicable criterion holds for this exact head."],
        )
    if verdict["status"] == "DENY" and verdict_exit == 1:
        return _denial(verdict)
    return (
        "failure",
        "merge-admission: the verdict and the command's exit disagree",
        [f"The verdict says {verdict['status']}, the command exited {verdict_exit}."],
    )


def _sharing(
    subject: Mapping[str, Any], population: Mapping[str, Any]
) -> tuple[str, str, list[str]] | None:
    """H1: a failure when the population does not show this pull request alone at
    its head, else None."""

    head = subject["head_commit"]
    number = int(subject["change_request"]["id"])
    listed = {item["pull_number"]: item["head"] for item in population["pulls"]}
    if listed.get(number) != head:
        return (
            "failure",
            "merge-admission: the open pull requests do not show this one at its head",
            [
                f"The complete open population lists #{number} "
                + (f"at `{listed[number]}`." if number in listed else "nowhere.")
            ],
        )
    sharing = sorted(pull for pull, at in listed.items() if at == head)
    if len(sharing) == 1:
        return None
    names = ", ".join(f"#{pull}" for pull in sharing)
    return (
        "failure",
        f"merge-admission: the head is shared by {names}",
        [
            "A check run belongs to a commit, so a success here would also satisfy "
            "every other pull request at this head. Each is denied until the others "
            "close or move, and a fresh evaluation recovers."
        ],
    )


def plan(
    evaluated: Mapping[str, Any],
    current: Mapping[str, Any],
    verdict: object,
    verdict_exit: int,
    *,
    evaluated_population: Mapping[str, Any],
    current_population: Mapping[str, Any],
    expected_head: str | None = None,
) -> dict[str, Any]:
    """What to publish for the evaluated evidence, given the current evidence, the
    open population each snapshot observed, and the head the run selected. An
    evaluation of another head than the selected one is not this run's subject
    (Octopus on #426): it is superseded too."""

    subject = evaluated["subject"]
    head = subject["head_commit"]
    conclusion, title, lines = _sharing(
        subject, evaluated_population
    ) or _verdict_state(subject, verdict, verdict_exit)
    external_id = hashlib.sha256(
        canonical(
            {
                "evidence": comparable(evaluated),
                "population": comparable(evaluated_population),
                "verdict": verdict,
                "exit": verdict_exit,
            }
        )
    ).hexdigest()
    unchanged = (
        comparable(current) == comparable(evaluated)
        and current_population == evaluated_population
        and (expected_head is None or expected_head == head)
    )
    summary = "\n".join(
        [
            f"Pull request {subject['change_request']['id']} at `{head}`.",
            "",
            *lines,
            "",
            "Evaluated by `knowledge merge-admission` from protected `main` (Decision 0112).",
        ]
    )
    return {
        "action": "PUBLISH" if unchanged else "SUPERSEDED",
        "subject": subject,
        "head_sha": head,
        "conclusion": conclusion,
        "title": _bounded(title, _MAX_TITLE),
        "summary": _bounded(summary, _MAX_SUMMARY),
        "external_id": external_id,
    }


def plan_incomplete(head: str, reason: str) -> dict[str, Any]:
    """The plan of an evaluation that did not complete: never a success."""

    return {
        "action": "INCOMPLETE",
        "subject": None,
        "head_sha": head,
        "conclusion": "failure",
        "title": "merge-admission: the evaluation did not complete",
        "summary": _bounded(
            f"No verdict is published for `{head}`:\n\n{_inert(reason)}", _MAX_SUMMARY
        ),
        "external_id": None,
    }


def _identity(correlation: Mapping[str, Any]) -> str:
    return f"{correlation['workflow_run_id']}:{correlation['run_attempt']}"


def _final(
    planned: Mapping[str, Any], correlation: Mapping[str, Any]
) -> dict[str, Any]:
    """What the completed run holds: the planned verdict, or a failure that names why
    nothing current was admitted."""

    if planned["action"] == "PUBLISH":
        conclusion, title, summary = (
            planned["conclusion"],
            planned["title"],
            planned["summary"],
        )
        external_id = planned["external_id"]
    elif planned["action"] == "SUPERSEDED":
        conclusion = "failure"
        title = "merge-admission: superseded; re-evaluating"
        summary = (
            "The evidence changed while it was evaluated, so nothing is admitted until "
            "the next evaluation completes."
        )
        external_id = f"superseded:{_identity(correlation)}"
    else:
        conclusion, title, summary = "failure", planned["title"], planned["summary"]
        external_id = f"incomplete:{_identity(correlation)}"
    text = correlation_text({"unbundled_evidence_sha256": None, **correlation})
    return {
        "conclusion": conclusion,
        "external_id": external_id,
        "output": {"title": title, "summary": summary, "text": text},
    }


def _verified(
    run: Mapping[str, Any], head: str, app_id: int, expected: Mapping[str, Any]
) -> int:
    if not ours(run, app_id):
        raise PublicationError("MISMATCH", "the check run is another App's")
    wanted = {"name": CHECK_NAME, "head_sha": head, **expected}
    if not matches(run, wanted):
        raise PublicationError("MISMATCH", "the check run reads back otherwise")
    identifier = run_id(run)
    if identifier is None:
        raise PublicationError("MISMATCH", "the check run reads back with no id")
    return identifier


def _post(
    client: Any,
    repository: str,
    head: str,
    app_id: int,
    payload: Mapping[str, Any],
) -> int:
    """Post a run once. An unknown outcome is found in the App's latest run by its
    `external_id`, never posted again."""

    expected = {
        "status": payload["status"],
        "external_id": payload["external_id"],
        **({"conclusion": payload["conclusion"]} if "conclusion" in payload else {}),
    }
    body = {"name": CHECK_NAME, "head_sha": head, **payload}
    try:
        posted = client.post(client.url(f"repos/{repository}/check-runs"), body)
    except github_rest.GitHubWriteError as exc:
        if not exc.outcome_unknown:
            raise PublicationError("REFUSED", str(exc)) from exc
        found = app_latest(client, repository, head, app_id)
        if found is None or found.get("external_id") != payload["external_id"]:
            raise PublicationError(
                "UNKNOWN", "the write's outcome is unknown and no such run is listed"
            ) from exc
        return _verified(found, head, app_id, expected)
    identifier = run_id(posted)
    if identifier is None:
        raise PublicationError("MISMATCH", "the provider's answer names no check run")
    return _verified(read_run(client, repository, identifier), head, app_id, expected)


def _complete(
    client: Any,
    repository: str,
    head: str,
    app_id: int,
    identifier: int,
    final: Mapping[str, Any],
) -> int:
    """Complete one run of the App by its id, read back. An unknown outcome is read
    back by that id, never written again."""

    payload = {"status": "completed", **final}
    expected = {
        "status": "completed",
        "conclusion": final["conclusion"],
        "external_id": final["external_id"],
    }
    try:
        client.patch(client.url(f"repos/{repository}/check-runs/{identifier}"), payload)
    except github_rest.GitHubWriteError as exc:
        if not exc.outcome_unknown:
            raise PublicationError("REFUSED", str(exc)) from exc
    return _verified(read_run(client, repository, identifier), head, app_id, expected)


def invalidate(
    client: Any,
    *,
    repository: str,
    head: str,
    app_id: int,
    correlation: Mapping[str, Any],
) -> dict[str, Any]:
    """Before anything is acquired again, replace a success the App's latest run
    stands on with a pending run of the App, and record what was observed."""

    latest = app_latest(client, repository, head, app_id)
    observed = run_id(latest)
    if (
        latest is None
        or latest.get("status") != "completed"
        or latest.get("conclusion") != "success"
    ):
        return {"result": "NOT_NEEDED", "pending": None, "observed": observed}
    payload = {
        "status": "in_progress",
        "external_id": f"pending:{_identity(correlation)}",
        "output": {
            "title": "merge-admission: re-evaluating",
            "summary": (
                "An earlier success on this head no longer stands while the head is "
                "evaluated again."
            ),
            # The run and the nonce, so a guarded merge can find this run (G1).
            "text": correlation_text(
                {**correlation, "unbundled_evidence_sha256": None}
            ),
        },
    }
    pending = _post(client, repository, head, app_id, payload)
    return {"result": "PENDING", "pending": pending, "observed": observed}


def _standing_success(run: Mapping[str, Any] | None) -> bool:
    return (
        run is not None
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    )


def _close(
    client: Any,
    repository: str,
    head: str,
    app_id: int,
    pending: int,
    correlation: Mapping[str, Any],
) -> None:
    """Complete this run's own pending run, no longer the latest, as a failure, so it
    never lingers as an evaluation that might still conclude."""

    _complete(
        client,
        repository,
        head,
        app_id,
        pending,
        {
            "conclusion": "failure",
            "external_id": f"overtaken:{_identity(correlation)}",
            "output": {
                "title": "merge-admission: overtaken",
                "summary": "A later run of the App on this head stands instead.",
                "text": "",
            },
        },
    )


def _already_latest(latest: Mapping[str, Any] | None, final: Mapping[str, Any]) -> bool:
    return (
        latest is not None
        and latest.get("status") == "completed"
        and latest.get("conclusion") == final["conclusion"]
        and latest.get("external_id") == final["external_id"]
    )


def publish(
    client: Any,
    *,
    repository: str,
    planned: Mapping[str, Any],
    app_id: int,
    record: Mapping[str, Any] | None,
    correlation: Mapping[str, Any],
) -> dict[str, Any]:
    """Complete this run's evaluation as the dedicated App, at most once."""

    head = planned["head_sha"]
    latest = app_latest(client, repository, head, app_id)
    pending = record.get("pending") if record is not None else None
    final = _final(planned, correlation)
    # A guarded merge's run always leaves the record its nonce is found by, so the
    # guard refuses at once rather than at its deadline (Octopus on #426).
    dispatched = correlation.get("nonce") is not None
    if type(pending) is int:
        if run_id(latest) != pending:
            _close(client, repository, head, app_id, pending, correlation)
            return _overtaken(
                client,
                repository,
                head,
                app_id,
                correlation,
                dispatched,
                latest=latest,
                record=record,
            )
        identifier = _complete(client, repository, head, app_id, pending, final)
        return {"result": "COMPLETED", "check_run_id": identifier}
    succeeding = planned["action"] == "PUBLISH" and planned["conclusion"] == "success"
    current = record is not None and run_id(latest) == record.get("observed")
    if succeeding and not current:
        # An older worker never restores a success over a newer run, nor without the
        # record of what it observed.
        return _overtaken(
            client,
            repository,
            head,
            app_id,
            correlation,
            dispatched,
            latest=latest,
            record=record,
        )
    if planned["action"] != "PUBLISH":
        return _without_verdict(
            client,
            repository,
            head,
            app_id,
            latest,
            final,
            planned["action"],
            dispatched,
        )
    return _with_verdict(client, repository, head, app_id, latest, final, dispatched)


def _overtaken(
    client: Any,
    repository: str,
    head: str,
    app_id: int,
    correlation: Mapping[str, Any],
    dispatched: bool,
    *,
    latest: Mapping[str, Any] | None,
    record: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """A success this run may not write. A dispatched run records a failure carrying
    its nonce, so the guard refuses at once; and a run with no record of what it
    observed, its invalidation having failed, replaces a success standing, which may
    predate the change that woke it (CodeAnt on #426). Otherwise nothing is written:
    a newer run's verdict stands. The cost is a fresh evaluation, never a merge."""

    standing = record is None and _standing_success(latest)
    if not dispatched and not standing:
        return {"result": "OVERTAKEN"}
    final = {
        "conclusion": "failure",
        "external_id": f"overtaken:{_identity(correlation)}",
        "output": {
            "title": "merge-admission: overtaken; re-evaluating",
            "summary": (
                "This run's success could not be written over the App's latest run on "
                "the head, so nothing is admitted until the next evaluation completes."
            ),
            "text": correlation_text(
                {"unbundled_evidence_sha256": None, **correlation}
            ),
        },
    }
    identifier = _post(
        client, repository, head, app_id, {"status": "completed", **final}
    )
    return {
        "result": "INVALIDATED" if _standing_success(latest) else "RECORDED",
        "check_run_id": identifier,
    }


def _without_verdict(
    client: Any,
    repository: str,
    head: str,
    app_id: int,
    latest: Mapping[str, Any] | None,
    final: Mapping[str, Any],
    action: str,
    dispatched: bool,
) -> dict[str, Any]:
    """A superseded or incomplete evaluation: it invalidates a standing success, and a
    dispatched run records its failure; otherwise nothing is written."""

    standing = _standing_success(latest)
    if not standing and not dispatched:
        return {"result": action}
    identifier = _post(
        client, repository, head, app_id, {"status": "completed", **final}
    )
    return {
        "result": "INVALIDATED" if standing else "RECORDED",
        "check_run_id": identifier,
    }


def _with_verdict(
    client: Any,
    repository: str,
    head: str,
    app_id: int,
    latest: Mapping[str, Any] | None,
    final: Mapping[str, Any],
    dispatched: bool,
) -> dict[str, Any]:
    """The verdict, posted once. A scheduled run's verdict already the latest is not
    posted again; a dispatched run always leaves its own record."""

    if not dispatched and latest is not None and _already_latest(latest, final):
        expected = {
            "external_id": final["external_id"],
            "conclusion": final["conclusion"],
        }
        return {
            "result": "PUBLISHED",
            "check_run_id": _verified(latest, head, app_id, expected),
        }
    identifier = _post(
        client, repository, head, app_id, {"status": "completed", **final}
    )
    return {"result": "PUBLISHED", "check_run_id": identifier}


def _document(path: Path, root: Path, label: str) -> dict[str, Any]:
    """One file, read as every verdict command reads its input: confined to the work
    directory, bounded before it is held, strictly decoded and depth-bounded."""

    document = read_json_file(path, label, ValueError, project_root=root)
    if not isinstance(document, dict):
        raise ValueError(f"the {label} is not an object")
    return document


def _evidence(root: Path, name: str, label: str) -> dict[str, Any]:
    document = _document(root / name, root, f"{label} evidence")
    subject = document.get("subject")
    if (
        not isinstance(subject, dict)
        or not isinstance(subject.get("change_request"), dict)
        or subject["change_request"].get("kind") != _SUBJECT_KIND
        or not isinstance(subject["change_request"].get("id"), str)
        or not subject["change_request"]["id"].isdigit()
        or not isinstance(subject.get("head_commit"), str)
        or _SHA40.fullmatch(subject["head_commit"]) is None
    ):
        raise ValueError(f"the {label} evidence names no pull-request subject")
    return document


def _population(root: Path, name: str, label: str) -> dict[str, Any]:
    """The complete open population an evaluation observed: each pull request once,
    with an exact head."""

    document = _document(root / name, root, f"{label} population")
    pulls = document.get("pulls")
    if document.get("coverage") != "COMPLETE" or not isinstance(pulls, list):
        raise ValueError(f"the {label} population is not complete")
    numbers = set()
    for item in pulls:
        if (
            not isinstance(item, dict)
            or set(item) != {"pull_number", "head"}
            or type(item["pull_number"]) is not int
            or item["pull_number"] <= 0
            or not isinstance(item["head"], str)
            or _SHA40.fullmatch(item["head"]) is None
            or item["pull_number"] in numbers
        ):
            raise ValueError(f"the {label} population is malformed")
        numbers.add(item["pull_number"])
    return document


def _verdict(root: Path) -> object:
    """The verdict, or None when the evaluation wrote none, or wrote what the verdict
    commands' own input rules refuse."""

    try:
        return read_json_file(
            root / "verdict.json", "verdict", ValueError, project_root=root
        )
    except ValueError:
        return None


def _client(token: str) -> Any:
    return github_rest.GitHubRestClient(
        token, user_agent="gnostoa-merge-admission", policy=_POLICY
    )


def parser() -> argparse.ArgumentParser:
    """The commands and their options: none of them takes a path."""
    commands_parser = argparse.ArgumentParser(description=__doc__)
    commands = commands_parser.add_subparsers(dest="command", required=True)
    commands.add_parser("hint", help="the pull request a relayed comment names")
    commands.add_parser(
        "dispatch-hint", help="the pull request and nonce a guarded merge dispatched"
    )
    for name in ("invalidate", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--repository", required=True)
        command.add_argument("--expected-head", required=True)
        command.add_argument("--app-id", type=int)
        if name == "publish":
            command.add_argument("--verdict-exit", type=int, required=True)
    return commands_parser


def _summary(result: Mapping[str, Any]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    planned = result.get("planned") or {}
    lines = [
        "## Gnostoa merge admission",
        "",
        f"- Result: {result['result']}",
        f"- Head: `{planned.get('head_sha')}`",
        f"- Conclusion: {planned.get('conclusion')} ({planned.get('action')})",
        f"- {planned.get('title')}",
    ]
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        print("Gnostoa merge admission: STEP_SUMMARY_UNAVAILABLE")


def _runner() -> tuple[Path, dict[str, Any]]:
    """The runner's work directory and this run's identity, from the runner alone."""

    temporary = os.environ.get("RUNNER_TEMP", "")
    run, attempt = (
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    )
    revision = os.environ.get("GITHUB_SHA", "")
    if not temporary:
        raise ValueError("the runner names no temporary directory")
    if not run.isdigit() or not attempt.isdigit() or int(run) <= 0 or int(attempt) <= 0:
        raise ValueError("the runner names no workflow run")
    if _SHA40.fullmatch(revision) is None:
        raise ValueError("the runner names no protected revision")
    # The guarded merge's nonce, from this run's own `subjects` job, as data (G1).
    nonce = os.environ.get("DISPATCH_NONCE", "") or None
    if nonce is not None and NONCE.fullmatch(nonce) is None:
        raise ValueError("the dispatch nonce is not 128 bits of hex")
    return Path(temporary).resolve(strict=True), {
        "workflow_run_id": int(run),
        "run_attempt": int(attempt),
        "protected_revision": revision,
        "nonce": nonce,
    }


def _dispatch_hint() -> int:
    """A guarded merge's `repository_dispatch`: exactly its pull request and its nonce,
    from the runner's own event file (G1, #426 6132395441). Anything else refuses,
    and never falls back to the sweep."""

    event = read_payload(
        os.environ.get("GITHUB_EVENT_PATH", ""), limit=DELIVERED_EVENT_BYTES
    )
    payload = event.get("client_payload") if isinstance(event, dict) else None
    if (
        not isinstance(event, dict)
        or event.get("action") != _DISPATCH_TYPE
        or not isinstance(payload, dict)
        or set(payload) != {"pull_number", "nonce"}
        or type(payload["pull_number"]) is not int
        or payload["pull_number"] <= 0
        or not isinstance(payload["nonce"], str)
        or NONCE.fullmatch(payload["nonce"]) is None
    ):
        raise ValueError("the dispatch names no pull request and nonce exactly")
    print(f"{payload['pull_number']} {payload['nonce']}")
    return 0


def _hint(temporary: Path) -> int:
    event = read_payload(
        str(temporary / _RELAYED / "event.json"), limit=DELIVERED_EVENT_BYTES
    )
    number = delivered_comment_pull_number(event)
    if number is not None:
        print(number)
    return 0


def _write(root: Path, name: str, document: Mapping[str, Any]) -> None:
    (root / name).write_text(
        json.dumps(document, sort_keys=True, indent=1), encoding="utf-8"
    )


def _publish_inputs(
    root: Path, args: argparse.Namespace, correlation: dict[str, Any]
) -> tuple[dict[str, Any], int]:
    """The plan from the work directory's files, or an INCOMPLETE plan and exit 2
    when any of them cannot be read."""

    try:
        evaluated = _evidence(root, "evaluated-evidence.json", "evaluated")
        current = _evidence(root, "current-evidence.json", "current")
        unbundled = _evidence(root, "current-unbundled-evidence.json", "unbundled")
        evaluated_population = _population(
            root, "evaluated-population.json", "evaluated"
        )
        current_population = _population(root, "current-population.json", "current")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return plan_incomplete(args.expected_head, str(exc)), 2
    correlation["unbundled_evidence_sha256"] = digest(unbundled)
    planned = plan(
        evaluated,
        current,
        _verdict(root),
        args.verdict_exit,
        evaluated_population=evaluated_population,
        current_population=current_population,
        expected_head=args.expected_head,
    )
    return planned, 0


def _record(root: Path, head: str) -> dict[str, Any] | None:
    """This run's invalidation record for the head, or None: a record for another
    head, or none at all, is no record of what this run observed."""

    try:
        record = _document(root / "pending.json", root, "invalidation record")
    except (OSError, ValueError):
        return None
    if record.get("result") not in {"PENDING", "NOT_NEEDED"}:
        # A failed or shadow invalidation observed nothing (Octopus on #426).
        return None
    return record if record.get("head", head) == head else None


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    token = os.environ.get(_APP_CREDENTIAL_VARIABLE, "")
    try:
        temporary, correlation = _runner()
        if args.command == "hint":
            return _hint(temporary)
        if args.command == "dispatch-hint":
            return _dispatch_hint()
        if _SHA40.fullmatch(args.expected_head) is None:
            raise ValueError("the expected head is no exact SHA")
        if token and (args.app_id is None or args.app_id <= 0):
            raise ValueError("publishing needs the dedicated App's id")
        root = temporary / _WORK
        root.mkdir(exist_ok=True)
    except (OSError, ValueError, Refused) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.command == "invalidate":
        return _run_invalidate(root, args, token, correlation)
    planned, code = _publish_inputs(root, args, correlation)
    if not token:
        result: dict[str, Any] = {"result": "SHADOW", "planned": planned}
    else:
        try:
            result = {
                **publish(
                    _client(token),
                    repository=args.repository,
                    planned=planned,
                    app_id=int(args.app_id),
                    record=_record(root, args.expected_head),
                    correlation=correlation,
                ),
                "planned": planned,
            }
        except PublicationError as exc:
            result = {
                "result": "FAILED",
                "kind": exc.kind,
                "reason": str(exc),
                "planned": planned,
            }
            code = code or 1
    _write(root, "result.json", result)
    _summary(result)
    print(f"merge-admission: {result['result']} ({planned['conclusion']})")
    return code


def _run_invalidate(
    root: Path, args: argparse.Namespace, token: str, correlation: Mapping[str, Any]
) -> int:
    if not token:
        record: dict[str, Any] = {"result": "SHADOW", "pending": None, "observed": None}
        code = 0
    else:
        try:
            record = invalidate(
                _client(token),
                repository=args.repository,
                head=args.expected_head,
                app_id=int(args.app_id),
                correlation=correlation,
            )
            code = 0
        except PublicationError as exc:
            record = {
                "result": "FAILED",
                "kind": exc.kind,
                "reason": str(exc),
                "pending": None,
                "observed": None,
            }
            code = 1
    _write(root, "pending.json", {**record, "head": args.expected_head})
    print(f"merge-admission invalidation: {record['result']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
