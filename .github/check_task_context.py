from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.task_context import (  # noqa: E402
    check_change_request_context,
    load_execution_plan,
    validate_execution_plan,
)

CHANGE_CLASS_RE = re.compile(
    r"(?im)^\s*-\s*(?:change class|class):\s*"
    r"`?(mechanical|normal|normative|critical|emergency)`?\s*$"
)


def check_event(event_path: Path, repository_root: Path) -> tuple[list[str], str]:
    payload: Any = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return ["GitHub event payload must be an object"], "invalid"
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict):
        return [], "not a pull_request event"

    head = pull_request.get("head", {})
    if not isinstance(head, dict):
        return ["pull_request.head must be an object"], "invalid"
    branch = head.get("ref")
    revision = head.get("sha")
    body = pull_request.get("body") or ""
    if not isinstance(branch, str) or not isinstance(revision, str):
        return ["pull request head branch and revision are required"], "invalid"
    if not isinstance(body, str):
        return ["pull request body must be a string"], "invalid"

    candidates: list[tuple[Path, dict[str, Any]]] = []
    plans_root = repository_root / "plans"
    if plans_root.is_dir():
        for path in sorted(plans_root.rglob("*.yaml")):
            plan = load_execution_plan(path)
            repository = plan.get("repository", {})
            if (
                isinstance(repository, dict)
                and repository.get("branch") == branch
                and plan.get("status") != "complete"
            ):
                candidates.append((path, plan))

    if not candidates:
        match = CHANGE_CLASS_RE.search(body)
        if not match:
            return ["Pull Request must declare its change class"], "invalid"
        change_class = match.group(1).casefold()
        if change_class in {"normative", "critical"}:
            return [
                f"{change_class} Gnostoa change requires an active "
                f"Execution Plan for branch {branch}"
            ], "invalid"
        return [], f"no active plan required for {change_class} branch {branch}"
    if len(candidates) > 1:
        paths = ", ".join(str(path.relative_to(repository_root)) for path, _ in candidates)
        return [f"multiple active plans match branch {branch}: {paths}"], "invalid"

    plan_path, plan = candidates[0]
    issues = validate_execution_plan(plan_path, repository_root)
    if not issues:
        issues.extend(check_change_request_context(plan, body, revision))
    return issues, str(plan_path.relative_to(repository_root))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check GitHub Pull Request context against its active plan."
    )
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        issues, selected = check_event(
            args.event.resolve(),
            args.repository_root.resolve(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for issue in issues:
        print(f"ERROR: {issue}", file=sys.stderr)
    if issues:
        return 1
    print(f"OK: GitHub task context ({selected})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
