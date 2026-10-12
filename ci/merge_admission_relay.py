"""Publish the merge-admission verdict as a check run (#407, MA0 slice 1b.4).

Decision 0112 item 5: a dedicated App, `gnostoa-ma0`, posts `merge-admission` from a
main-only environment, woken by Decision 0096's relay and a sweep. This command never
decides admission. It publishes the existing verdict (`knowledge merge-admission`) on
the exact head that verdict was evaluated for, and only while the evidence it rests on
is unchanged. The workflow evaluates, reads a second snapshot, rebuilds the evidence
from it, and this command compares the two, observation times aside. A moved head, or
a changed description, relation, review, thread or check supersedes the verdict, so a
stale check is never published; the next event or the sweep evaluates again.

The check is posted once. Its outcome is read back, and an unknown outcome is found by
its `external_id` rather than posted again. Without the App's token the run is a
shadow: it records its plan and writes nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tools import github_rest
from tools.verdict_cli import MAX_INPUT_BYTES

CHECK_NAME = "merge-admission"
_TOKEN_ENV = "GNOSTOA_MA0_TOKEN"  # nosec B105 -- environment variable name, not a credential
_VERDICT_SCHEMA = "gnostoa-merge-admission/v1"
_SUBJECT_KIND = "github-pull-request"
# GitHub's limits for a check run's output.
_MAX_TITLE = 255
_MAX_SUMMARY = 60_000
_MAX_LISTED_RUNS = 100
_POLICY = github_rest.Policy(
    timeout_seconds=30, attempts=1, max_response_bytes=4_194_304
)


class PublicationError(RuntimeError):
    """A check run that was refused, could not be read back, or reads back as
    something other than what was posted."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def _comparable(value: Any) -> Any:
    """The evidence as the verdict reads it: every observation time dropped, at any
    depth, since a re-read observes again without changing what it found."""

    if isinstance(value, Mapping):
        return {
            key: _comparable(item)
            for key, item in value.items()
            if key != "observed_at"
        }
    if isinstance(value, list):
        return [_comparable(item) for item in value]
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    marker = "\n\n… (cut at GitHub's limit; the run's artifact keeps the whole verdict)"
    return text[: limit - len(marker)] + marker


def _verdict_state(
    subject: Mapping[str, Any], verdict: object, verdict_exit: int
) -> tuple[str, str, list[str]]:
    """The conclusion, title and summary lines. Only a well-formed ALLOW for this
    exact subject, from a command that exited 0, is ever a success."""

    if (
        not isinstance(verdict, Mapping)
        or verdict.get("schema") != _VERDICT_SCHEMA
        or verdict.get("status") not in {"ALLOW", "DENY"}
        or not isinstance(verdict.get("criteria"), list)
    ):
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
        failing = [
            criterion
            for criterion in verdict["criteria"]
            if isinstance(criterion, Mapping) and criterion.get("status") == "FAIL"
        ]
        names = ", ".join(str(criterion.get("id")) for criterion in failing)
        lines = [
            f"- **{criterion.get('id')}**: "
            + "; ".join(str(reason) for reason in criterion.get("reasons") or [])
            for criterion in failing
        ]
        return "failure", f"merge-admission: DENY ({names})", lines
    return (
        "failure",
        "merge-admission: the verdict and the command's exit disagree",
        [f"The verdict says {verdict['status']}, the command exited {verdict_exit}."],
    )


def plan(
    evaluated: Mapping[str, Any],
    current: Mapping[str, Any],
    verdict: object,
    verdict_exit: int,
) -> dict[str, Any]:
    """What to publish for the evaluated evidence, given the current evidence."""

    subject = evaluated["subject"]
    head = subject["head_commit"]
    conclusion, title, lines = _verdict_state(subject, verdict, verdict_exit)
    external_id = hashlib.sha256(
        _canonical(
            {
                "evidence": _comparable(evaluated),
                "verdict": verdict,
                "exit": verdict_exit,
            }
        )
    ).hexdigest()
    unchanged = _comparable(current) == _comparable(evaluated)
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


def _verified(run: object, planned: Mapping[str, Any]) -> int:
    expected = {
        "name": CHECK_NAME,
        "head_sha": planned["head_sha"],
        "status": "completed",
        "conclusion": planned["conclusion"],
        "external_id": planned["external_id"],
    }
    if not isinstance(run, Mapping) or any(
        run.get(field) != value for field, value in expected.items()
    ):
        raise PublicationError("MISMATCH", "the check run reads back otherwise")
    identifier = run.get("id")
    if type(identifier) is not int:
        raise PublicationError("MISMATCH", "the check run reads back with no id")
    return identifier


def _found(client: Any, repository: str, planned: Mapping[str, Any]) -> object:
    """The posted run, after a write whose outcome is unknown, or None."""

    url = client.url(
        f"repos/{repository}/commits/{planned['head_sha']}/check-runs"
        f"?check_name={CHECK_NAME}&filter=all&per_page={_MAX_LISTED_RUNS}"
    )
    try:
        document, _ = client.get(url)
    except github_rest.GitHubError as exc:
        raise PublicationError(
            "UNKNOWN", "the check runs could not be read back"
        ) from exc
    runs = document.get("check_runs") if isinstance(document, Mapping) else None
    total = document.get("total_count") if isinstance(document, Mapping) else None
    if not isinstance(runs, list) or type(total) is not int or total > _MAX_LISTED_RUNS:
        raise PublicationError("UNKNOWN", "the check runs read back incompletely")
    matches = [
        run
        for run in runs
        if isinstance(run, Mapping) and run.get("external_id") == planned["external_id"]
    ]
    return matches[-1] if matches else None


def publish(
    client: Any, *, repository: str, planned: Mapping[str, Any]
) -> dict[str, Any]:
    """Post the planned check run once and read it back."""

    if planned["action"] != "PUBLISH":
        return {"result": "SUPERSEDED"}
    payload = {
        "name": CHECK_NAME,
        "head_sha": planned["head_sha"],
        "status": "completed",
        "conclusion": planned["conclusion"],
        "external_id": planned["external_id"],
        "output": {"title": planned["title"], "summary": planned["summary"]},
    }
    try:
        posted = client.post(client.url(f"repos/{repository}/check-runs"), payload)
    except github_rest.GitHubWriteError as exc:
        if not exc.outcome_unknown:
            raise PublicationError("REFUSED", str(exc)) from exc
        found = _found(client, repository, planned)
        if found is None:
            raise PublicationError(
                "UNKNOWN", "the write's outcome is unknown and no such run is listed"
            ) from exc
        return {"result": "PUBLISHED", "check_run_id": _verified(found, planned)}
    identifier = posted.get("id") if isinstance(posted, Mapping) else None
    if type(identifier) is not int:
        raise PublicationError("MISMATCH", "the provider's answer names no check run")
    try:
        read, _ = client.get(client.url(f"repos/{repository}/check-runs/{identifier}"))
    except github_rest.GitHubError as exc:
        raise PublicationError(
            "UNKNOWN", "the check run could not be read back"
        ) from exc
    return {"result": "PUBLISHED", "check_run_id": _verified(read, planned)}


def _evidence(path: Path, label: str) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"the {label} evidence exceeds its bound")
    document: object = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"the {label} evidence is not an object")
    subject = document.get("subject")
    if (
        not isinstance(subject, dict)
        or not isinstance(subject.get("change_request"), dict)
        or subject["change_request"].get("kind") != _SUBJECT_KIND
        or not isinstance(subject.get("head_commit"), str)
    ):
        raise ValueError(f"the {label} evidence names no pull-request subject")
    return document


def _verdict(path: Path | None) -> object:
    """The verdict, or None when the evaluation wrote none or wrote no JSON."""

    if path is None or not path.is_file():
        return None
    raw = path.read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _client(token: str) -> Any:
    return github_rest.GitHubRestClient(
        token, user_agent="gnostoa-merge-admission", policy=_POLICY
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--evaluated", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--verdict", type=Path)
    parser.add_argument("--verdict-exit", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _summary(result: Mapping[str, Any]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    planned = result["planned"]
    lines = [
        "## Gnostoa merge admission",
        "",
        f"- Result: {result['result']}",
        f"- Head: `{planned['head_sha']}`",
        f"- Conclusion: {planned['conclusion']} ({planned['action']})",
        f"- {planned['title']}",
    ]
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        print("Gnostoa merge admission: STEP_SUMMARY_UNAVAILABLE")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        evaluated = _evidence(args.evaluated, "evaluated")
        current = _evidence(args.current, "current")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    planned = plan(evaluated, current, _verdict(args.verdict), args.verdict_exit)
    token = os.environ.get(_TOKEN_ENV, "")
    code = 0
    if not token:
        result: dict[str, Any] = {"result": "SHADOW", "planned": planned}
    else:
        try:
            result = {
                **publish(_client(token), repository=args.repository, planned=planned),
                "planned": planned,
            }
        except PublicationError as exc:
            result = {
                "result": "FAILED",
                "kind": exc.kind,
                "reason": str(exc),
                "planned": planned,
            }
            code = 1
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=1), encoding="utf-8"
    )
    _summary(result)
    print(f"merge-admission: {result['result']} ({planned['conclusion']})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
