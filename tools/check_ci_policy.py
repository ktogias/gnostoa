from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_common import (
    KnowledgeFormatError,
    deep_merge,
    load_yaml,
    toolkit_root,
)

HOOK_RANK = {
    "optional": 0,
    "recommended": 1,
    "required": 2,
}
GATE_RANK = {
    "advisory": 0,
    "restore-green": 1,
    "required": 2,
}
REQUIRED_TRUE_PATHS = (
    ("authority", "centralized_ci_required"),
    ("authority", "provider_neutral_contract"),
    ("authority", "required_checks_authoritative"),
    ("authority", "latest_revision_required"),
    ("security", "immutable_dependencies"),
    ("security", "least_privilege"),
    ("security", "untrusted_changes_no_secrets"),
    ("local_feedback", "shared_commands_required"),
    ("delivery", "promote_same_artifact"),
    ("delivery", "environment_protection"),
    ("delivery", "post_deploy_smoke"),
)
REQUIRED_FALSE_PATHS = (
    ("local_feedback", "hooks_authoritative"),
    ("local_feedback", "network_access"),
    ("delivery", "rebuild_between_environments"),
)
CAPABILITY_BY_SUITE = {
    "integration": "integration",
    "smoke": "smoke",
    "extended": "extended",
    "release": "deployable_artifact",
}


def _nested(mapping: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = mapping
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _rank(ranks: dict[str, int], value: object) -> int:
    return ranks.get(value, -1) if isinstance(value, str) else -1


def _assert_monotonic(
    parent: dict[str, Any],
    child: dict[str, Any],
    path: Path,
) -> None:
    for rule_path in REQUIRED_TRUE_PATHS:
        if _nested(parent, rule_path) is True and _nested(child, rule_path) is False:
            raise KnowledgeFormatError(
                f"{path} disables parent CI rule {'.'.join(rule_path)}"
            )

    for rule_path in REQUIRED_FALSE_PATHS:
        if _nested(parent, rule_path) is False and _nested(child, rule_path) is True:
            raise KnowledgeFormatError(
                f"{path} enables forbidden CI capability {'.'.join(rule_path)}"
            )

    parent_hooks = _nested(parent, ("local_feedback", "hooks"))
    child_hooks = _nested(child, ("local_feedback", "hooks"))
    if child_hooks is not None and HOOK_RANK.get(child_hooks, -1) < HOOK_RANK.get(
        parent_hooks, -1
    ):
        raise KnowledgeFormatError(
            f"{path} weakens local hook adoption: {parent_hooks} -> {child_hooks}"
        )

    for field in ("max_seconds",):
        parent_value = _nested(parent, ("local_feedback", field))
        child_value = _nested(child, ("local_feedback", field))
        if (
            isinstance(parent_value, int)
            and isinstance(child_value, int)
            and child_value > parent_value
        ):
            raise KnowledgeFormatError(
                f"{path} weakens local feedback target {field}: "
                f"{parent_value} -> {child_value}"
            )

    for field in ("fast_max_minutes", "required_max_minutes"):
        parent_value = _nested(parent, ("feedback", field))
        child_value = _nested(child, ("feedback", field))
        if (
            isinstance(parent_value, int)
            and isinstance(child_value, int)
            and child_value > parent_value
        ):
            raise KnowledgeFormatError(
                f"{path} weakens CI feedback target {field}: "
                f"{parent_value} -> {child_value}"
            )

    parent_events = parent.get("events", {})
    child_events = child.get("events", {})
    if not isinstance(parent_events, dict) or not isinstance(child_events, dict):
        return

    for event_id, overrides in child_events.items():
        baseline = parent_events.get(event_id)
        if not isinstance(baseline, dict) or not isinstance(overrides, dict):
            continue

        parent_activation = baseline.get("activation")
        child_activation = overrides.get("activation")
        if (
            child_activation is not None
            and child_activation != parent_activation
            and child_activation != "always"
        ):
            raise KnowledgeFormatError(
                f"{path} weakens {event_id}.activation: "
                f"{parent_activation} -> {child_activation}"
            )

        parent_gate = baseline.get("gate")
        child_gate = overrides.get("gate")
        if child_gate is not None and _rank(GATE_RANK, child_gate) < _rank(
            GATE_RANK,
            parent_gate,
        ):
            raise KnowledgeFormatError(
                f"{path} weakens {event_id}.gate: {parent_gate} -> {child_gate}"
            )

        for field in ("latest_revision",):
            if baseline.get(field) is True and overrides.get(field) is False:
                raise KnowledgeFormatError(
                    f"{path} disables parent rule {event_id}.{field}"
                )

        parent_cancellation = baseline.get("cancel_superseded")
        child_cancellation = overrides.get("cancel_superseded")
        if (
            isinstance(parent_cancellation, bool)
            and child_cancellation is not None
            and child_cancellation != parent_cancellation
        ):
            raise KnowledgeFormatError(
                f"{path} changes inherited event cancellation semantics "
                f"{event_id}.cancel_superseded: "
                f"{parent_cancellation} -> {child_cancellation}"
            )

        effective = deep_merge(baseline, overrides)
        for field in ("required_suites", "conditional_suites"):
            parent_suites = baseline.get(field, [])
            child_suites = effective.get(field, [])
            if (
                isinstance(parent_suites, list)
                and isinstance(child_suites, list)
                and not set(parent_suites).issubset(child_suites)
            ):
                raise KnowledgeFormatError(
                    f"{path} removes inherited {event_id}.{field}"
                )


def load_ci_policy(path: Path) -> dict[str, Any]:
    return _load_ci_policy(path.resolve(), ())


def _load_ci_policy(path: Path, stack: tuple[Path, ...]) -> dict[str, Any]:
    if path in stack:
        chain = " -> ".join(str(item) for item in (*stack, path))
        raise KnowledgeFormatError(f"CI-policy inheritance cycle: {chain}")

    current = load_yaml(path)
    extends = current.get("extends", [])
    if not isinstance(extends, list):
        raise KnowledgeFormatError(f"CI-policy extends must be a list in {path}")
    if len(extends) > 1:
        raise KnowledgeFormatError(f"CI policy supports one parent at most in {path}")

    merged: dict[str, Any] = {}
    for reference in extends:
        if not isinstance(reference, str):
            raise KnowledgeFormatError(
                f"CI-policy parent reference must be a string in {path}"
            )
        parent_path = (path.parent / reference).resolve()
        if not parent_path.is_file():
            raise KnowledgeFormatError(
                f"Parent CI policy {reference!r} from {path} does not exist"
            )
        parent = _load_ci_policy(parent_path, (*stack, path))
        _assert_monotonic(parent, current, path)
        merged = deep_merge(merged, parent)

    result = deep_merge(merged, current)
    if not isinstance(result, dict):
        raise KnowledgeFormatError(f"Merged CI policy must be a mapping in {path}")
    return result


def _schema_issues(value: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    return [
        f"{'.'.join(str(item) for item in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def _required_suites(
    policy: dict[str, Any],
    capabilities: dict[str, Any],
) -> set[str]:
    required: set[str] = set()
    deployable = capabilities.get("deployable_artifact") is True

    events = policy.get("events", {})
    if not isinstance(events, dict):
        return required
    for event in events.values():
        if not isinstance(event, dict):
            continue
        activation = event.get("activation")
        if activation == "when-deployable" and not deployable:
            continue

        suites = event.get("required_suites", [])
        if isinstance(suites, list):
            required.update(suites)

        conditional = event.get("conditional_suites", [])
        if not isinstance(conditional, list):
            continue
        for suite_id in conditional:
            capability = CAPABILITY_BY_SUITE.get(suite_id)
            if capability and capabilities.get(capability) is True:
                required.add(suite_id)

    # The provider adapter runs the toolkit-owned policy suite separately from
    # the project verification runtime and manifest.
    required.discard("policy")
    return required


def _verification_issues(
    policy: dict[str, Any],
    policy_path: Path,
    manifest_path: Path,
    schema_path: Path,
    expected_runtime_image: str | None,
) -> list[str]:
    manifest = load_yaml(manifest_path)
    issues = _schema_issues(manifest, schema_path)

    policy_reference = manifest.get("policy")
    if isinstance(policy_reference, str):
        resolved = (manifest_path.parent / policy_reference).resolve()
        if resolved != policy_path.resolve():
            issues.append(
                "policy: verification manifest does not reference the "
                f"validated policy ({resolved} != {policy_path.resolve()})"
            )

    capabilities = manifest.get("capabilities", {})
    suites = manifest.get("suites", {})
    if not isinstance(capabilities, dict) or not isinstance(suites, dict):
        return sorted(set(issues))

    runtime = manifest.get("runtime", {})
    if isinstance(runtime, dict) and runtime.get("mode") == "project":
        locked_image = runtime.get("image")
        if (
            expected_runtime_image
            and isinstance(locked_image, str)
            and locked_image != expected_runtime_image
        ):
            issues.append(
                f"runtime.image {locked_image!r} does not match executing "
                f"project runtime {expected_runtime_image!r}"
            )

    required = _required_suites(policy, capabilities)
    for suite_id in sorted(required):
        if suite_id not in suites:
            issues.append(
                f"suites.{suite_id}: required by active CI events and capabilities"
            )

    for suite_id, capability in CAPABILITY_BY_SUITE.items():
        if suite_id in suites and capabilities.get(capability) is not True:
            issues.append(
                f"suites.{suite_id}: declared while capability {capability} is false"
            )

    if _nested(policy, ("local_feedback", "shared_commands_required")) is True:
        for suite_id, suite in suites.items():
            if not isinstance(suite, dict):
                continue
            command = suite.get("command")
            expected = ["./ci/verify", suite_id]
            if not isinstance(command, list) or command[:2] != expected:
                issues.append(
                    f"suites.{suite_id}.command must use shared command {expected!r}"
                )

    fast = suites.get("fast")
    fast_max = _nested(policy, ("feedback", "fast_max_minutes"))
    if isinstance(fast, dict):
        timeout = fast.get("timeout_minutes")
        if (
            isinstance(timeout, int)
            and isinstance(fast_max, int)
            and timeout > fast_max
        ):
            issues.append(
                f"suites.fast.timeout_minutes exceeds policy target {fast_max}"
            )

    required_max = _nested(policy, ("feedback", "required_max_minutes"))
    for suite_id in required - {"fast", "extended", "release"}:
        suite = suites.get(suite_id)
        if not isinstance(suite, dict):
            continue
        timeout = suite.get("timeout_minutes")
        if (
            isinstance(timeout, int)
            and isinstance(required_max, int)
            and timeout > required_max
        ):
            issues.append(
                f"suites.{suite_id}.timeout_minutes exceeds "
                f"required policy target {required_max}"
            )

    return sorted(set(issues))


def check_ci_policy(
    policy_path: Path,
    verification_path: Path | None = None,
    policy_schema_path: Path | None = None,
    verification_schema_path: Path | None = None,
    expected_runtime_image: str | None = None,
) -> list[str]:
    root = toolkit_root()
    policy = load_ci_policy(policy_path)
    policy_schema = (
        policy_schema_path.resolve()
        if policy_schema_path
        else root / "schemas" / "continuous-integration.schema.json"
    )
    issues = _schema_issues(policy, policy_schema)

    if verification_path is not None:
        verification_schema = (
            verification_schema_path.resolve()
            if verification_schema_path
            else root / "schemas" / "verification-manifest.schema.json"
        )
        issues.extend(
            _verification_issues(
                policy,
                policy_path.resolve(),
                verification_path.resolve(),
                verification_schema,
                expected_runtime_image,
            )
        )
    return sorted(set(issues))


def _parser() -> argparse.ArgumentParser:
    root = toolkit_root()
    parser = argparse.ArgumentParser(
        description="Validate inherited CI policy and project verification suites."
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=root / "policy" / "continuous-integration.yaml",
    )
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--policy-schema", type=Path)
    parser.add_argument("--verification-schema", type=Path)
    parser.add_argument(
        "--expected-runtime-image",
        default=os.environ.get("PROJECT_VERIFICATION_IMAGE"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        issues = check_ci_policy(
            args.policy,
            args.verification,
            args.policy_schema,
            args.verification_schema,
            args.expected_runtime_image,
        )
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for issue in issues:
        print(f"ERROR: {issue}")
    if issues:
        return 1

    suffix = (
        f" and verification manifest {args.verification}" if args.verification else ""
    )
    print(f"OK: CI policy is valid ({args.policy}){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
