from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .knowledge_common import KnowledgeFormatError, load_yaml, toolkit_root


START_MARKER = "<!-- task-context:start -->"
END_MARKER = "<!-- task-context:end -->"
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
MANAGED_BLOCK_RE = re.compile(
    re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
    re.DOTALL,
)
CANDIDATE_RE = re.compile(r"Candidate revision: `([0-9a-f]{40})`")


def load_execution_plan(path: Path) -> dict[str, Any]:
    return load_yaml(path.resolve())


def _schema_issues(plan: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(plan),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'.'.join(str(item) for item in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def _local_references(plan: dict[str, Any]) -> list[str]:
    change = plan.get("change", {})
    contracts = plan.get("contracts", {})
    references: list[str] = []
    if isinstance(change, dict):
        decisions = change.get("decisions", [])
        if isinstance(decisions, list):
            references.extend(item for item in decisions if isinstance(item, str))
    if isinstance(contracts, dict):
        for name in ("read", "affected"):
            values = contracts.get(name, [])
            if isinstance(values, list):
                references.extend(item for item in values if isinstance(item, str))
    return references


def validate_execution_plan(
    plan_path: Path,
    repository_root: Path | None = None,
    schema_path: Path | None = None,
) -> list[str]:
    root = (repository_root or toolkit_root()).resolve()
    schema = (
        schema_path.resolve()
        if schema_path
        else toolkit_root() / "schemas" / "execution-plan.schema.json"
    )
    plan = load_execution_plan(plan_path)
    issues = _schema_issues(plan, schema)
    if issues:
        return issues

    for reference in _local_references(plan):
        target = reference.split("#", 1)[0]
        if not target or "://" in target:
            continue
        resolved = (root / target).resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            issues.append(f"reference escapes repository root: {reference}")
            continue
        if not resolved.exists():
            issues.append(f"referenced path does not exist: {reference}")
    return issues


def reconcile_execution_plan(
    plan: dict[str, Any],
    *,
    branch: str,
    changed_paths: set[str],
    require_clean: bool,
    implicit_expected_paths: set[str] | None = None,
    base_is_ancestor: bool | None = None,
) -> list[str]:
    issues: list[str] = []
    repository = plan.get("repository", {})
    expected_branch = repository.get("branch") if isinstance(repository, dict) else None
    if branch != expected_branch:
        issues.append(
            f"repository branch drift: plan expects {expected_branch!r}, "
            f"found {branch!r}"
        )

    handoff = plan.get("handoff", {})
    expected_values = (
        handoff.get("expected_worktree", []) if isinstance(handoff, dict) else []
    )
    expected = {
        value for value in expected_values if isinstance(value, str)
    }
    expected.update(implicit_expected_paths or set())
    unexpected = sorted(changed_paths - expected)
    missing = sorted(expected - changed_paths)
    if unexpected:
        issues.append(
            "unexpected worktree paths: " + ", ".join(unexpected)
        )
    if missing:
        issues.append(
            "expected worktree paths are absent: " + ", ".join(missing)
        )
    if require_clean and changed_paths:
        issues.append("handoff requires a clean committed worktree")
    if base_is_ancestor is False:
        issues.append("plan base revision is not an ancestor of repository HEAD")
    return issues


def render_change_request_context(
    plan: dict[str, Any],
    candidate_revision: str,
) -> str:
    if not REVISION_RE.fullmatch(candidate_revision):
        raise KnowledgeFormatError(
            "Candidate revision must be a lowercase 40-character Git SHA."
        )
    change = plan["change"]
    decisions = change.get("decisions", [])
    decision_text = ", ".join(f"`{item}`" for item in decisions) or "none"
    work_item = change.get("work_item", "not linked")
    return "\n".join(
        (
            START_MARKER,
            "## Managed task context",
            "",
            f"- Plan: `{plan['id']}`",
            f"- Status: `{plan['status']}`",
            f"- Change class: `{change['class']}`",
            f"- Work Item: {work_item}",
            f"- Decisions: {decision_text}",
            f"- Candidate revision: `{candidate_revision}`",
            f"- Current: {plan['progress']['current']}",
            f"- Next action: {plan['next_action']['instruction']}",
            END_MARKER,
        )
    )


def check_change_request_context(
    plan: dict[str, Any],
    body: str,
    candidate_revision: str,
) -> list[str]:
    issues: list[str] = []
    match = MANAGED_BLOCK_RE.search(body)
    if not match:
        return ["managed task-context block is absent"]

    revision_match = CANDIDATE_RE.search(match.group(0))
    actual_revision = revision_match.group(1) if revision_match else None
    if actual_revision != candidate_revision:
        issues.append(
            "candidate revision is stale: "
            f"expected {candidate_revision}, found {actual_revision or 'none'}"
        )

    expected = render_change_request_context(plan, candidate_revision)
    if match.group(0) != expected:
        issues.append("managed task-context block does not match the plan")
    return issues


def _git_command(repository_root: Path, *arguments: str) -> list[str]:
    root = repository_root.resolve()
    return [
        "git",
        "-c",
        f"safe.directory={root}",
        "-C",
        str(root),
        *arguments,
    ]


def _git_output(repository_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        _git_command(repository_root, *arguments),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KnowledgeFormatError(
            result.stderr.strip()
            or f"Git command failed with exit code {result.returncode}."
        )
    return result.stdout.strip()


def repository_state(repository_root: Path) -> tuple[str, str, set[str]]:
    root = repository_root.resolve()
    branch = _git_output(root, "branch", "--show-current") or "HEAD"
    revision = _git_output(root, "rev-parse", "HEAD")
    result = subprocess.run(
        _git_command(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "-z",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise KnowledgeFormatError(
            result.stderr.strip()
            or f"Git status failed with exit code {result.returncode}."
        )
    records = result.stdout.split("\0")
    changed_paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        status = record[:2]
        changed_paths.add(record[3:])
        if ("R" in status or "C" in status) and index < len(records):
            source = records[index]
            index += 1
            if source:
                changed_paths.add(source)
    return branch, revision, changed_paths


def _base_is_ancestor(repository_root: Path, base_revision: str) -> bool:
    result = subprocess.run(
        _git_command(
            repository_root,
            "merge-base",
            "--is-ancestor",
            base_revision,
            "HEAD",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in {0, 1}:
        raise KnowledgeFormatError(
            result.stderr.strip() or "Cannot compare plan base revision to HEAD."
        )
    return result.returncode == 0


def _orientation(plan: dict[str, Any]) -> str:
    return "\n".join(
        (
            f"Plan: {plan['id']} ({plan['status']})",
            f"Outcome: {plan['scope']['outcome']}",
            f"Current: {plan['progress']['current']}",
            f"Next: {plan['next_action']['instruction']}",
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, resume, checkpoint and hand off bounded changes."
    )
    parser.add_argument(
        "operation",
        choices=(
            "validate",
            "start",
            "resume",
            "checkpoint",
            "handoff",
            "render-change-request",
            "check-change-request",
        ),
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--candidate-revision")
    parser.add_argument("--body", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.repository_root.resolve()
    try:
        issues = validate_execution_plan(args.plan, root, args.schema)
        if issues:
            for issue in issues:
                print(f"ERROR: {issue}", file=sys.stderr)
            return 1
        plan = load_execution_plan(args.plan)

        if args.operation == "validate":
            print(f"OK: execution plan is valid ({args.plan})")
            return 0

        branch, revision, changed_paths = repository_state(root)
        candidate = args.candidate_revision or revision

        if args.operation == "render-change-request":
            print(render_change_request_context(plan, candidate))
            return 0
        if args.operation == "check-change-request":
            if args.body is None:
                print("ERROR: --body is required", file=sys.stderr)
                return 2
            body = args.body.read_text(encoding="utf-8")
            issues = check_change_request_context(plan, body, candidate)
        else:
            require_clean = args.operation == "handoff"
            implicit_expected: set[str] = set()
            if not require_clean:
                try:
                    implicit_expected.add(
                        args.plan.resolve().relative_to(root).as_posix()
                    )
                except ValueError:
                    pass
            issues = reconcile_execution_plan(
                plan,
                branch=branch,
                changed_paths=changed_paths,
                require_clean=require_clean,
                implicit_expected_paths=implicit_expected,
                base_is_ancestor=_base_is_ancestor(
                    root,
                    plan["repository"]["base_revision"],
                ),
            )
            if args.operation == "start" and plan["status"] not in {
                "planned",
                "active",
            }:
                issues.append("start requires a planned or active plan")
            if args.operation == "resume" and plan["status"] == "complete":
                issues.append("a complete plan cannot be resumed")
            if args.operation == "handoff":
                if plan["handoff"]["status"] != "ready":
                    issues.append("handoff status must be ready")
                if not plan["handoff"].get("recipient"):
                    issues.append("handoff recipient is required")

        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        if issues:
            return 1
        print(_orientation(plan))
        print(f"Repository revision: {revision}")
        return 0
    except (
        KnowledgeFormatError,
        OSError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
