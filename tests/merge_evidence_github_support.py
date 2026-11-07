"""What other test modules share from tests/test_merge_evidence_github.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import copy
import io
import shutil
import tempfile
import unittest
from collections.abc import Mapping
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from tests.merge_admission_support import debt_entry
from tests.review_reconcile_l1_support import (
    adapter_fixture,
    complete_replies_fixture,
    paged_fake_fixture,
)
from tools import (
    analyzer_readback,
    assurance_completeness,
    merge_admission,
    merge_evidence_github,
)

ROOT = Path(__file__).resolve().parents[1]


API = "https://api.github.com/repos/ktogias/gnostoa"


HEAD = "a" * 40


BASE = "b" * 40


COMPARE = f"{API}/compare/{BASE}...{HEAD}"


EDITS = "graphql:comments:first"


CLOSING = "graphql:closingIssuesReferences:first"


DECLARER = "gnostoa-agent[bot]"


BODY = """## Outcome

The verdict reads normalized evidence.

## Change control

- Class: `normative`
- Work Item: #407, #15
- Decision: [0112](knowledge/decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md)
- Accountable owner: @ktogias
"""


def _commit(sha: str, message: str) -> dict[str, Any]:
    return {"sha": sha, "commit": {"message": message}}


ACTIONS = 15368


CODEQL = 57789


REQUIRED = ("policy", "fast", "regression", "smoke")


REQUIRED_CHECKS: dict[str, Any] = {
    "schema_version": "1.0",
    "id": "example.merge-required-checks",
    "version": "0.1.0",
    "requirements": {
        "verification-checks": {
            name: {"app_id": ACTIONS, "name": name} for name in REQUIRED
        },
        "codeql": {"codeql": {"app_id": CODEQL, "name": "CodeQL"}},
        # Each declared item has one producer, so the gate is here and the
        # inventory is the readback's (G1).
        "sonarcloud": {
            "quality-gate": {
                "app_id": 12526,
                "name": "SonarCloud Code Analysis",
                "pull_request": "details_url",
            }
        },
    },
}


CHECK_RUNS = f"{API}/commits/{HEAD}/check-runs?per_page=100"


CHECK_SUITES = f"{API}/commits/{HEAD}/check-suites?per_page=100"


SUITE_OF = {ACTIONS: 9001, CODEQL: 9002, 12526: 9003}


_DEFAULT_SUITE = object()


def _check_run(
    identifier: int,
    name: str,
    app_id: int,
    *,
    conclusion: str | None = "success",
    status: str = "completed",
    completed_at: str | None = "2026-09-19T16:40:30Z",
    started_at: str = "2026-09-19T16:40:20Z",
    suite: object = _DEFAULT_SUITE,
) -> dict[str, Any]:
    """A check run on the head, in its App's suite unless `suite` names another,
    or omits it when None, as a run without suite metadata would."""

    run: dict[str, Any] = {
        "id": identifier,
        "name": name,
        "app": {"id": app_id},
        "head_sha": HEAD,
        "started_at": started_at,
        "completed_at": completed_at,
        "status": status,
        "conclusion": conclusion,
    }
    if suite is _DEFAULT_SUITE:
        suite = SUITE_OF.get(app_id, 9009)
    if suite is not None:
        run["check_suite"] = {"id": suite}
    return run


def _green_checks() -> list[dict[str, Any]]:
    runs = [_check_run(40 + i, name, ACTIONS) for i, name in enumerate(REQUIRED)]
    return [*runs, _check_run(50, "CodeQL", CODEQL)]


def _suite(
    identifier: int,
    app_id: int,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    head_sha: str = HEAD,
) -> dict[str, Any]:
    """A check suite on the head as GitHub lists it."""

    return {
        "id": identifier,
        "app": {"id": app_id},
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
    }


def _green_suites() -> list[dict[str, Any]]:
    return [_suite(suite, app) for app, suite in SUITE_OF.items()]


def _suites(
    suites: list[dict[str, Any]], *, total: int | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """One page of the head's check suites, counting them unless `total` says
    otherwise."""

    count = len(suites) if total is None else total
    return {"total_count": count, "check_suites": suites}, {}


FILES = [
    {"filename": "tools/merge_admission.py", "status": "added"},
    {"filename": "tests/test_merge_admission.py", "status": "added"},
]


def _comparison(
    commits: list[dict[str, Any]],
    files: list[dict[str, Any]],
    *,
    total: int | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """GitHub's comparison of the exact base and head: its merge base, its commits
    with their total, and its changed files."""

    return (
        {
            "merge_base_commit": {"sha": "c" * 40},
            "total_commits": len(commits) if total is None else total,
            "commits": commits,
            "files": files,
        },
        {},
    )


def _closing(
    *issues: tuple[str, int], next_cursor: str | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """The issues the merge would close, keyword-linked or linked by hand."""

    page = {
        "nodes": [
            {"number": number, "repository": {"nameWithOwner": repository}}
            for repository, number in issues
        ],
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
    }
    return {
        "data": {"repository": {"pullRequest": {"closingIssuesReferences": page}}}
    }, {}


def _edits(*comments: tuple[int, str | None]) -> tuple[dict[str, Any], dict[str, str]]:
    """The conversation's edit state: each comment's id and `lastEditedAt`, null
    when it was never edited."""

    page = {
        "nodes": [{"databaseId": i, "lastEditedAt": at} for i, at in comments],
        "pageInfo": {"hasNextPage": False, "endCursor": None},
    }
    return {"data": {"repository": {"pullRequest": {"comments": page}}}}, {}


def _issue(
    number: int, *, repository: str = "ktogias/gnostoa", pull: bool = False
) -> tuple[dict[str, Any], dict[str, str]]:
    """GitHub's REST answer for one issue, or for a pull request read as one."""

    payload: dict[str, Any] = {
        "number": number,
        "repository_url": f"https://api.github.com/repos/{repository}",
        "title": f"Work Item {number}",
        "state": "open",
    }
    if pull:
        payload["pull_request"] = {
            "url": f"https://api.github.com/repos/{repository}/pulls/{number}"
        }
    return payload, {}


def _replies(**changes: Any) -> dict[str, tuple[Any, dict[str, str]]]:
    """PR 300 in the shape of a converged change, with the merge-evidence reads."""

    replies = copy.deepcopy(complete_replies_fixture(API))
    pull = replies[f"{API}/pulls/300"][0]
    pull.update(
        {
            "draft": False,
            "merged": False,
            "title": "Admit or deny one merge",
            "body": BODY,
            "user": {"login": "gnostoa-agent-user"},
        }
    )
    pull["base"]["ref"] = "main"
    pull["base"]["repo"] = {"default_branch": "main"}
    replies[f"{API}/issues/300/comments?per_page=100"] = (
        [
            {
                "id": 1,
                "user": {"login": DECLARER},
                "created_at": "2026-09-19T16:40:00Z",
                "updated_at": "2026-09-19T16:40:00Z",
                "body": f"Exact review candidate: {HEAD}",
            }
        ],
        {},
    )
    replies.pop("https://api.github.com/page2/issues", None)
    first_reviews = replies[f"{API}/pulls/300/reviews?per_page=100"][0]
    first_reviews[0]["user"] = {"login": "ktogias"}
    replies[COMPARE] = _comparison(
        [_commit(HEAD, "Admit or deny one merge\n\nRefs #407")], FILES
    )
    replies[EDITS] = _edits((1, None))
    replies[CHECK_RUNS] = ({"check_runs": _green_checks()}, {})
    replies.pop("https://api.github.com/page2/check-runs", None)
    replies[CHECK_SUITES] = _suites(_green_suites())
    replies[CLOSING] = _closing()
    # BODY's Work Items (1b.3b-3).
    replies[f"{API}/issues/407"] = _issue(407)
    replies[f"{API}/issues/15"] = _issue(15)
    for key, value in changes.items():
        replies[key] = value
    return replies


def _snapshot(
    replies: dict[str, tuple[Any, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    adapter = adapter_fixture()
    snapshot: dict[str, Any] = adapter.collect_snapshot(
        paged_fake_fixture(_replies() if replies is None else replies),
        repository="ktogias/gnostoa",
        pull_number=300,
        observed_at="2026-09-19T16:41:00Z",
        merge_evidence=True,
    )
    return snapshot


def _authorities() -> dict[str, Any]:
    return merge_evidence_github.parse_authorities(
        {
            "schema_version": "1.0",
            "id": "example.merge-authorities",
            "version": "0.1.0",
            "declarer": DECLARER,
            "human_approvers": ["ktogias"],
        }
    )


def _policy() -> dict[str, Any]:
    return merge_admission.load_policy(
        ROOT / "policy" / "change-control.yaml", project_root=ROOT
    )


def _evidence(
    snapshot: dict[str, Any] | None = None,
    *,
    codeowners: str = "* @ktogias\n",
    analyzer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return merge_evidence_github.evidence_from_snapshot(
        _snapshot() if snapshot is None else snapshot,
        authorities=_authorities(),
        change_policy=_policy(),
        codeowners=merge_evidence_github.parse_codeowners(codeowners),
        decisions=merge_evidence_github.load_decisions(ROOT),
        required_checks=merge_evidence_github.parse_required_checks(REQUIRED_CHECKS),
        analyzer_readback=analyzer,
    )


def _failed(evidence: dict[str, Any]) -> dict[str, list[str]]:
    declaration = assurance_completeness.load_declaration(
        ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
    )
    verdict = merge_admission.evaluate(
        evidence, declaration=declaration, change_policy=_policy()
    )
    return {c["id"]: c["reasons"] for c in verdict["criteria"] if c["status"] == "FAIL"}


def _project(directory: Path, *, authorities: bool = True) -> Path:
    project = directory / "project"
    (project / "policy").mkdir(parents=True)
    (project / "core").mkdir()
    (project / ".github").mkdir()
    for name in (
        "policy/change-control.yaml",
        "core/change-control.yaml",
        "policy/assurance-evidence.yaml",
    ):
        shutil.copyfile(ROOT / name, project / name)
    shutil.copytree(
        ROOT / "knowledge" / "decisions", project / "knowledge" / "decisions"
    )
    (project / ".github" / "CODEOWNERS").write_text("* @ktogias\n", encoding="utf-8")
    (project / "policy" / "merge-required-checks.yaml").write_text(
        yaml.safe_dump(REQUIRED_CHECKS), encoding="utf-8"
    )
    if authorities:
        (project / "policy" / "merge-authorities.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "id": "example.merge-authorities",
                    "version": "0.1.0",
                    "declarer": DECLARER,
                    "human_approvers": ["ktogias"],
                }
            ),
            encoding="utf-8",
        )
    return project


def _run(project: Path, text: str, *options: str) -> tuple[int, str, str]:
    stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    with patch("sys.stdin", stdin), redirect_stdout(out), redirect_stderr(err):
        code = merge_evidence_github.main(["--project-root", str(project), *options])
    return code, out.getvalue(), err.getvalue()


def _merge_evidence_guardrail() -> dict[str, Any]:
    manifest = yaml.safe_load(
        (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
    )
    (entry,) = [g for g in manifest["guardrails"] if g["id"] == "github-merge-evidence"]
    return dict(entry)


def unregistered_tests(namespace: Mapping[str, Any], path: str) -> set[str]:
    """The tests a module defines that the github-merge-evidence guardrail does
    not list, for each module whose tests it lists."""

    prefix = f"{path}::"
    entry = _merge_evidence_guardrail()
    registered = {t[len(prefix) :] for t in entry["tests"] if t.startswith(prefix)}
    defined = {
        f"{name}.{method}"
        for name, case in namespace.items()
        if isinstance(case, type) and issubclass(case, unittest.TestCase)
        for method in unittest.defaultTestLoader.getTestCaseNames(case)
    }
    return defined - registered


def _readback(
    provider: str,
    scope: str,
    *findings: dict[str, Any],
    status: str = "COMPLETE",
    head: str = HEAD,
    repository: str = "ktogias/gnostoa",
    pull: int = 300,
    completeness: str | None = None,
    native_mode: str | None = None,
    native: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    complete = status == "COMPLETE"
    if completeness is None:
        # As the producer marks them: Codacy's and SonarCloud's reads are full runs,
        # and a retired DeepSource's diff read, which only the retirement tests
        # build, diff-local (Decision 0130).
        local = (provider, scope) == ("deepsource", "DIFF")
        completeness = "DIFF_LOCAL" if local else "FULL_RUN"
    if native_mode is None:
        # Each producer's own native mode (CodeAnt and Cubic on #461): Codacy's and
        # SonarCloud's pull-request analyses; DeepSource's and the inventory's
        # diff-local and full reads.
        native_mode = (
            "PULL_REQUEST"
            if provider in ("codacy", "sonarcloud")
            else "DIFF_LOCAL"
            if completeness == "DIFF_LOCAL"
            else "FULL_RUN"
        )
    record: dict[str, Any] = {"status": status, "pages": 1, "count": len(findings)}
    if not complete:
        record["reason"] = "AUTH_UNAVAILABLE"
    return analyzer_readback.build_readback(
        provider=provider,
        adapter=f"{provider}-fake/v1",
        repository=repository,
        pull_number=pull,
        requested_head=head,
        observed_head=head if complete else None,
        analysis_id=None,
        scope=scope,
        completeness=completeness if complete else "AUTH_UNAVAILABLE",
        native_mode=native_mode,
        observed_at="2026-09-19T16:40:50Z",
        run_state="SUCCESS" if complete else "UNKNOWN",
        coverage_record=record,
        findings=findings,
        native=native,
    )


def _bundle(*readbacks: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """The authenticated readback's bundle for the snapshot's pull request; by
    default its four readbacks are complete and find nothing: Codacy's, SonarCloud's
    and, since #389 A0-MP1 slice 3, the project inventory's two. DeepSource gives
    none: it is retired as merge evidence (Decision 0130)."""

    bundle: dict[str, Any] = {
        "schema": analyzer_readback.BUNDLE_SCHEMA,
        "repository": "ktogias/gnostoa",
        "pull_number": 300,
        "requested_head": HEAD,
        "observed_head": HEAD,
        "observed_at": "2026-09-19T16:40:50Z",
        "subject_binding": "BOUND",
        "github_projection": {"statuses": 0, "check_runs": 5, "review_comments": 0},
        "readbacks": list(readbacks)
        or [
            _readback("codacy", "DIFF"),
            _readback(*SONAR),
            *_inventory_readbacks(),
        ],
    }
    bundle.update(changes)
    return bundle


def _inventory_readbacks() -> tuple[dict[str, Any], dict[str, Any]]:
    """The project inventory's two complete readbacks, as #460's adapter marks them:
    DIFF diff-local, FULL a full run, in completeness and native mode alike, built
    by the one inventory fixture (#389 A0-MP1 slice 3; CodeAnt on #461)."""

    return (_inventory("DIFF"), _inventory("FULL"))


# SonarCloud's inventory gives the `sonarcloud` requirement's own item (1b.3c).
SONAR = ("sonarcloud", "DIFF")


FINDING = {
    "id": "issue-1",
    "message": "Reimport 'x'",
    "rule": "PYL-W0404",
    "severity": "MAJOR",
    "path": "tests/test_x.py",
    "state": "open",
}


def _section_c_declaration() -> dict[str, Any]:
    """Gnostoa's own declaration: Codacy stays `analyzer-readback`'s, and the
    project's inventory gives `project-risk-readback`, NORMAL's alone under
    6381812211 section C and every class's since Decision 0130, which retires
    DeepSource's requirement and claims."""

    document: dict[str, Any] = yaml.safe_load(
        (ROOT / "policy" / "assurance-evidence.yaml").read_text(encoding="utf-8")
    )
    return document


def _inventory(scope: str, *findings: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """One of the project inventory's two readbacks, as #460's adapter builds them:
    DIFF is diff-local, FULL a full run, in completeness and native mode alike
    (CodeAnt on #461)."""

    kind = "DIFF_LOCAL" if scope == "DIFF" else "FULL_RUN"
    return _readback(
        "gnostoa-inventory",
        scope,
        *findings,
        completeness=kind,
        native_mode=kind,
        **changes,
    )


def _admitted(
    declaration: dict[str, Any],
    bundle: dict[str, Any] | None,
    change_class: str | None = None,
    *,
    ledger: dict[str, Any] | None = None,
    review_body: str | None = None,
    extra_reviews: tuple[dict[str, Any], ...] = (),
    files: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """The merge decision on one head under `declaration`, with `bundle`, if any, as
    its analyzer readback, the gate green, and the body's class `change_class` if given:
    the evidence and the failed criteria. Module-level, so each class's tests call
    it without reaching into another's private member (#461's own inventory). A
    `ledger` is the protected target's analyzer debt ledger (#389). `review_body` is
    the owner's approving review's text, `extra_reviews` are further GitHub reviews
    on the first page, and `files` replaces the comparison's changed files (#389
    Track 2's dispositions and baseline)."""
    evidence, verdict = _decision(
        declaration,
        bundle,
        change_class,
        ledger=ledger,
        review_body=review_body,
        extra_reviews=extra_reviews,
        files=files,
    )
    failed = {
        c["id"]: c["reasons"] for c in verdict["criteria"] if c["status"] == "FAIL"
    }
    return evidence, failed


def _decision(
    declaration: dict[str, Any],
    bundle: dict[str, Any] | None,
    change_class: str | None = None,
    *,
    ledger: dict[str, Any] | None = None,
    review_body: str | None = None,
    extra_reviews: tuple[dict[str, Any], ...] = (),
    files: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """`_admitted`'s evidence and its whole verdict, every criterion and what it
    carries for approval (Claude on #480)."""
    with tempfile.TemporaryDirectory() as directory:
        project = _project(Path(directory))
        path = project / "policy" / "assurance-evidence.yaml"
        path.write_text(yaml.safe_dump(declaration, sort_keys=False), encoding="utf-8")
        if ledger is not None:
            (project / merge_evidence_github.DEFAULT_DEBT_LEDGER).write_text(
                yaml.safe_dump(ledger, sort_keys=False), encoding="utf-8"
            )
        # The gate passed on the exact head, so every check item is
        # COMPLETE, as in `test_a_green_gate_s_findings_reach_m17`.
        gate = {
            **_check_run(60, "SonarCloud Code Analysis", 12526),
            "details_url": "https://sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest=300",
        }
        replies = _replies(
            **{CHECK_RUNS: ({"check_runs": [*_green_checks(), gate]}, {})}
        )
        if change_class is not None:
            replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
                "- Class: `normative`", f"- Class: `{change_class}`"
            )
        reviews = replies[f"{API}/pulls/300/reviews?per_page=100"][0]
        if review_body is not None:
            reviews[0]["body"] = review_body
        reviews.extend(copy.deepcopy(list(extra_reviews)))
        if files is not None:
            replies[COMPARE] = _comparison(
                [_commit(HEAD, "Admit or deny one merge\n\nRefs #407")], files
            )
        snapshot = _snapshot(replies)
        evidence = merge_evidence_github.evidence_for(
            snapshot, project_root=project, analyzer_readback=bundle
        )
        loaded = assurance_completeness.load_declaration(path, project_root=project)
    verdict = merge_admission.evaluate(
        evidence, declaration=loaded, change_policy=_policy()
    )
    return evidence, verdict


LEDGER_DOCUMENT: dict[str, Any] = {
    "schema_version": "1.0",
    "id": "example.analyzer-debt-ledger",
    "version": "0.1.0",
    "entries": [debt_entry()],
}


# The project inventory's run-bound configuration, as its adapter states it: the
# protected profile's digest, bound to its own run (owner 6620829215 §2).
_PROFILE = "sha256:" + "b" * 64


# The finding's own producer's effective identity, as the inventory adapter states it
# (owner 6621293483 §1).
_PRODUCER = "sha256:" + "e" * 64


def _complete_bundle(
    *codacy: dict[str, Any],
    sonarcloud: tuple[dict[str, Any], ...] = (),
    inventory_diff: tuple[dict[str, Any], ...] = (),
    inventory_full: tuple[dict[str, Any], ...] = (),
    profile: str = _PROFILE,
    binding: str = "BOUND",
    producers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """A bound bundle of the active providers whose every readback is complete, with
    `codacy` in Codacy's pull-request read and `sonarcloud` in SonarCloud's, neither
    of which states a configuration, and `inventory_diff` and `inventory_full` in
    the inventory's two reads, under `profile`. DeepSource gives none: it is retired
    as merge evidence (Decision 0130)."""
    bound = {
        "profile": profile,
        "source_binding": binding,
        "tree": "c" * 40,
        "producers": {"python": _PRODUCER} if producers is None else dict(producers),
    }
    return _bundle(
        _readback("codacy", "DIFF", *codacy),
        _readback(*SONAR, *sonarcloud),
        _inventory("DIFF", *inventory_diff, native=bound),
        _inventory("FULL", *inventory_full, native=bound),
    )
