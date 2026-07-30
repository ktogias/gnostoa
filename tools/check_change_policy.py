from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_common import (
    KnowledgeFormatError,
    deep_merge,
    load_yaml,
    toolkit_root,
)


WORK_ITEM_RANK = {
    "optional": 0,
    "required-follow-up": 1,
    "required": 2,
}
TIMING_RANK = {
    "post-event-allowed": 0,
    "before-merge": 1,
}
AUTOMATED_TEST_RANK = {
    "existing-evidence": 0,
    "when-automatable": 1,
    "required": 2,
}
FAILING_EVIDENCE_RANK = {
    "optional": 0,
    "when-applicable": 1,
    "required-follow-up": 2,
    "required": 3,
}
EVIDENCE_TIMING_RANK = {
    "post-event": 0,
    "before-merge": 1,
    "before-implementation": 2,
}
REQUIRED_TRUE_PATHS = (
    ("integration", "protected_default_branch"),
    ("integration", "change_request_required"),
    ("integration", "required_checks"),
    ("integration", "resolved_conversations"),
    ("branches", "short_lived"),
    ("verification", "expected_behavior_required"),
    ("verification", "observable_behavior_over_implementation_details"),
    ("verification", "deterministic_required_tests"),
    ("verification", "flaky_required_tests_block"),
)
REQUIRED_FALSE_PATHS = (
    ("integration", "direct_push"),
    ("integration", "force_push"),
    ("integration", "branch_deletion"),
    ("agents", "may_approve_own_change"),
    ("agents", "may_bypass_controls"),
    ("agents", "may_promote_stable_without_human"),
    ("verification", "coverage_alone_sufficient"),
)
CLASS_REQUIRED_TRUE = (
    "independent_approval",
    "code_owner_approval",
    "decision_record",
    "human_approval",
    "follow_up_review",
)


def _nested(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _assert_monotonic(
    parent: dict[str, Any],
    child: dict[str, Any],
    path: Path,
) -> None:
    for rule_path in REQUIRED_TRUE_PATHS:
        if _nested(parent, rule_path) is True and _nested(child, rule_path) is False:
            raise KnowledgeFormatError(
                f"{path} disables parent change-control rule "
                f"{'.'.join(rule_path)}"
            )

    for rule_path in REQUIRED_FALSE_PATHS:
        if _nested(parent, rule_path) is False and _nested(child, rule_path) is True:
            raise KnowledgeFormatError(
                f"{path} enables forbidden change-control capability "
                f"{'.'.join(rule_path)}"
            )

    parent_lifetime = _nested(parent, ("branches", "target_lifetime_hours"))
    child_lifetime = _nested(child, ("branches", "target_lifetime_hours"))
    if (
        isinstance(parent_lifetime, int)
        and isinstance(child_lifetime, int)
        and child_lifetime > parent_lifetime
    ):
        raise KnowledgeFormatError(
            f"{path} weakens branch lifetime target: "
            f"{parent_lifetime} -> {child_lifetime} hours"
        )

    parent_feedback = _nested(
        parent,
        ("verification", "fast_feedback_target_minutes"),
    )
    child_feedback = _nested(
        child,
        ("verification", "fast_feedback_target_minutes"),
    )
    if (
        isinstance(parent_feedback, int)
        and isinstance(child_feedback, int)
        and child_feedback > parent_feedback
    ):
        raise KnowledgeFormatError(
            f"{path} weakens fast feedback target: "
            f"{parent_feedback} -> {child_feedback} minutes"
        )

    parent_classes = parent.get("change_classes", {})
    child_classes = child.get("change_classes", {})
    if not isinstance(parent_classes, dict) or not isinstance(child_classes, dict):
        return

    for class_id, overrides in child_classes.items():
        baseline = parent_classes.get(class_id)
        if not isinstance(baseline, dict) or not isinstance(overrides, dict):
            continue

        parent_work_item = baseline.get("work_item")
        child_work_item = overrides.get("work_item")
        if (
            child_work_item is not None
            and WORK_ITEM_RANK.get(child_work_item, -1)
            < WORK_ITEM_RANK.get(parent_work_item, -1)
        ):
            raise KnowledgeFormatError(
                f"{path} weakens {class_id}.work_item: "
                f"{parent_work_item} -> {child_work_item}"
            )

        parent_timing = baseline.get("change_request_timing")
        child_timing = overrides.get("change_request_timing")
        if (
            child_timing is not None
            and TIMING_RANK.get(child_timing, -1)
            < TIMING_RANK.get(parent_timing, -1)
        ):
            raise KnowledgeFormatError(
                f"{path} weakens {class_id}.change_request_timing: "
                f"{parent_timing} -> {child_timing}"
            )

        parent_approvals = baseline.get("minimum_approvals")
        child_approvals = overrides.get("minimum_approvals")
        if (
            isinstance(parent_approvals, int)
            and isinstance(child_approvals, int)
            and child_approvals < parent_approvals
        ):
            raise KnowledgeFormatError(
                f"{path} reduces {class_id}.minimum_approvals: "
                f"{parent_approvals} -> {child_approvals}"
            )

        for name in CLASS_REQUIRED_TRUE:
            if baseline.get(name) is True and overrides.get(name) is False:
                raise KnowledgeFormatError(
                    f"{path} disables parent rule {class_id}.{name}"
                )

        if baseline.get("auto_merge") is False and overrides.get("auto_merge") is True:
            raise KnowledgeFormatError(
                f"{path} enables forbidden auto-merge for {class_id}"
            )

        parent_verification = baseline.get("verification", {})
        child_verification = overrides.get("verification", {})
        if not isinstance(parent_verification, dict) or not isinstance(
            child_verification,
            dict,
        ):
            continue

        ranked_fields = (
            ("automated_test", AUTOMATED_TEST_RANK),
            ("failing_evidence", FAILING_EVIDENCE_RANK),
            ("evidence_timing", EVIDENCE_TIMING_RANK),
        )
        for name, ranks in ranked_fields:
            parent_value = parent_verification.get(name)
            child_value = child_verification.get(name)
            if (
                child_value is not None
                and ranks.get(child_value, -1) < ranks.get(parent_value, -1)
            ):
                raise KnowledgeFormatError(
                    f"{path} weakens {class_id}.verification.{name}: "
                    f"{parent_value} -> {child_value}"
                )

        if (
            parent_verification.get("human_semantic_verification") is True
            and child_verification.get("human_semantic_verification") is False
        ):
            raise KnowledgeFormatError(
                f"{path} disables parent rule "
                f"{class_id}.verification.human_semantic_verification"
            )


def load_change_policy(path: Path) -> dict[str, Any]:
    return _load_change_policy(path.resolve(), ())


def _load_change_policy(path: Path, stack: tuple[Path, ...]) -> dict[str, Any]:
    if path in stack:
        chain = " -> ".join(str(item) for item in (*stack, path))
        raise KnowledgeFormatError(f"Change-control inheritance cycle: {chain}")

    current = load_yaml(path)
    extends = current.get("extends", [])
    if not isinstance(extends, list):
        raise KnowledgeFormatError(
            f"Change-control extends must be a list in {path}"
        )
    if len(extends) > 1:
        raise KnowledgeFormatError(
            f"Change-control policy supports one parent at most in {path}"
        )

    merged: dict[str, Any] = {}
    for reference in extends:
        if not isinstance(reference, str):
            raise KnowledgeFormatError(
                f"Change-control parent reference must be a string in {path}"
            )
        parent_path = (path.parent / reference).resolve()
        if not parent_path.is_file():
            raise KnowledgeFormatError(
                f"Parent change-control policy {reference!r} from {path} "
                "does not exist"
            )
        parent = _load_change_policy(parent_path, (*stack, path))
        _assert_monotonic(parent, current, path)
        merged = deep_merge(merged, parent)

    return deep_merge(merged, current)


def check_change_policy(
    policy_path: Path,
    schema_path: Path | None = None,
) -> list[str]:
    policy = load_change_policy(policy_path)
    schema = (
        schema_path.resolve()
        if schema_path
        else toolkit_root() / "schemas" / "change-control.schema.json"
    )
    schema_value = json.loads(schema.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema_value).iter_errors(policy),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'.'.join(str(item) for item in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def _parser() -> argparse.ArgumentParser:
    root = toolkit_root()
    parser = argparse.ArgumentParser(
        description="Validate an inherited provider-neutral change-control policy."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=root / "policy" / "change-control.yaml",
    )
    parser.add_argument("--schema", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        issues = check_change_policy(args.policy, args.schema)
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for issue in issues:
        print(f"ERROR: {issue}")
    if issues:
        return 1

    print(f"OK: change-control policy is valid ({args.policy})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
