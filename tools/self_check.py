from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unittest

from .check_change_policy import check_change_policy
from .check_ci_policy import check_ci_policy
from .check_guardrails import check_guardrails
from .knowledge_common import KnowledgeFormatError, toolkit_root
from .task_context import validate_execution_plan
from .validate_bundle import validate_bundle


BUNDLES = (
    ("generic example", "core/profile.yaml", "examples/generic"),
    (
        "module example",
        "examples/profiles/example-project/example-module/profile.yaml",
        "examples/example-project-module",
    ),
    ("reusable guidance", "guidance/profile.yaml", "guidance"),
    ("toolkit self-knowledge", "knowledge/profile.yaml", "knowledge"),
)


def self_check(repository_root: Path, run_tests: bool = True) -> bool:
    root = repository_root.resolve()
    passed = True

    if run_tests:
        suite = unittest.defaultTestLoader.discover(str(root / "tests"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        passed = result.wasSuccessful() and passed

    for name, profile, bundle in BUNDLES:
        _, issues = validate_bundle(root / profile, root / bundle)
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            passed = False
            for issue in errors:
                print(
                    f"ERROR: {name}: {issue.path}: {issue.message}",
                    file=sys.stderr,
                )
        else:
            print(f"OK: {name}")

    guardrail_issues = check_guardrails(
        root / "policy" / "guardrails.yaml",
        root,
    )
    if guardrail_issues:
        passed = False
        for issue in guardrail_issues:
            print(f"ERROR: guardrails: {issue}", file=sys.stderr)
    else:
        print("OK: guardrail coverage")

    plan_issues: list[str] = []
    for plan in sorted((root / "plans").rglob("*.yaml")):
        for issue in validate_execution_plan(plan, root):
            plan_issues.append(f"{plan.relative_to(root)}: {issue}")
    if plan_issues:
        passed = False
        for issue in plan_issues:
            print(f"ERROR: execution plan: {issue}", file=sys.stderr)
    else:
        print("OK: active execution plans")

    for name, path in (
        ("generic change control", "core/change-control.yaml"),
        ("toolkit change control", "policy/change-control.yaml"),
    ):
        try:
            policy_issues = check_change_policy(root / path)
        except (KnowledgeFormatError, OSError, ValueError) as exc:
            policy_issues = [str(exc)]
        if policy_issues:
            passed = False
            for issue in policy_issues:
                print(f"ERROR: {name}: {issue}", file=sys.stderr)
        else:
            print(f"OK: {name}")

    for name, policy, verification in (
        ("generic CI policy", "core/continuous-integration.yaml", None),
        (
            "toolkit CI policy",
            "policy/continuous-integration.yaml",
            "policy/verification.yaml",
        ),
    ):
        try:
            ci_issues = check_ci_policy(
                root / policy,
                root / verification if verification else None,
            )
        except (KnowledgeFormatError, OSError, ValueError) as exc:
            ci_issues = [str(exc)]
        if ci_issues:
            passed = False
            for issue in ci_issues:
                print(f"ERROR: {name}: {issue}", file=sys.stderr)
        else:
            print(f"OK: {name}")

    return passed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the toolkit's complete non-container self-check."
    )
    parser.add_argument("--repository-root", type=Path, default=toolkit_root())
    parser.add_argument("--skip-tests", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return 0 if self_check(args.repository_root, not args.skip_tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
