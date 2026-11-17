from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from . import test_suite
from .check_change_policy import check_change_policy
from .check_ci_policy import check_ci_policy
from .check_guardrails import check_guardrails
from .knowledge_common import KnowledgeFormatError, toolkit_root
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
        # In parallel processes, as every run of the suite (Decision 0109).
        passed = test_suite.run(root) == 0 and passed

    for check in (_bundles, _guardrails, _change_policies, _ci_policies):
        passed = check(root) and passed
    return passed


def _report(name: str, issues: Iterable[str], passed_as: str | None = None) -> bool:
    """Print each issue under ``name``, or that the check passed; whether it did."""
    reported = False
    for issue in issues:
        print(f"ERROR: {name}: {issue}", file=sys.stderr)
        reported = True
    if not reported:
        print(f"OK: {passed_as or name}")
    return not reported


def _bundles(root: Path) -> bool:
    passed = True
    for name, profile, bundle in BUNDLES:
        _, issues = validate_bundle(root / profile, root / bundle, project_root=root)
        errors = [
            f"{issue.path}: {issue.message}"
            for issue in issues
            if issue.severity == "error"
        ]
        passed = _report(name, errors) and passed
    return passed


def _guardrails(root: Path) -> bool:
    issues = check_guardrails(root / "policy" / "guardrails.yaml", root)
    return _report("guardrails", issues, passed_as="guardrail coverage")


def _change_policies(root: Path) -> bool:
    passed = True
    for name, path in (
        ("generic change control", "core/change-control.yaml"),
        ("toolkit change control", "policy/change-control.yaml"),
    ):
        try:
            issues = check_change_policy(root / path)
        except (OSError, ValueError) as exc:
            issues = [str(exc)]
        passed = _report(name, issues) and passed
    return passed


def _ci_policies(root: Path) -> bool:
    passed = True
    for name, policy, verification in (
        ("generic CI policy", "core/continuous-integration.yaml", None),
        (
            "toolkit CI policy",
            "policy/continuous-integration.yaml",
            "policy/verification.yaml",
        ),
    ):
        try:
            issues = check_ci_policy(
                root / policy,
                root / verification if verification else None,
            )
        except (OSError, ValueError) as exc:
            issues = [str(exc)]
        passed = _report(name, issues) and passed
    return passed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the toolkit's complete non-container self-check."
    )
    parser.add_argument("--repository-root", type=Path, default=toolkit_root())
    parser.add_argument("--skip-tests", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        return 0 if self_check(args.repository_root, not args.skip_tests) else 1
    except (KnowledgeFormatError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
