from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_common import KnowledgeFormatError, deep_merge, load_yaml, toolkit_root

REVIEW_REQUIREMENTS = {"none", "required"}
CHANGE_CLASSES = {"mechanical", "normal", "normative", "critical", "emergency"}


def effective_policy_issues(policy: object) -> list[str]:
    if not isinstance(policy, dict):
        return ["policy must be an object"]
    issues: list[str] = []
    if policy.get("schema_version") != "1.0":
        issues.append("unsupported policy schema_version")
    if policy.get("abstract") is True:
        issues.append("policy is abstract")
    requirement = policy.get("review_requirement")
    if requirement not in REVIEW_REQUIREMENTS:
        issues.append("review_requirement is unresolved")
    change_class = policy.get("change_class")
    if change_class not in CHANGE_CLASSES:
        issues.append("change_class is unresolved")
    for name in ("subject", "collection", "qualification", "quorum", "blockers", "conflicts"):
        if not isinstance(policy.get(name), dict):
            issues.append(f"{name} section is unresolved")
    if requirement == "required":
        collection = policy.get("collection", {})
        qualification = policy.get("qualification", {})
        quorum = policy.get("quorum", {})
        required_sources = collection.get("required_sources") if isinstance(collection, dict) else None
        capabilities = (
            qualification.get("required_capabilities")
            if isinstance(qualification, dict)
            else None
        )
        minimum = quorum.get("minimum_distinct_domains") if isinstance(quorum, dict) else None
        if not isinstance(required_sources, list) or not required_sources:
            issues.append("required review has no required collection source")
        if not isinstance(capabilities, list) or not capabilities:
            issues.append("required review has no required capability")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            issues.append("required review has no positive distinct-domain quorum")
    return sorted(set(issues))


def _load_source(path: Path, stack: tuple[Path, ...]) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in stack:
        chain = " -> ".join(str(item) for item in (*stack, resolved))
        raise KnowledgeFormatError(f"Review-policy inheritance cycle: {chain}")
    current = load_yaml(resolved)
    extends = current.get("extends", [])
    if not isinstance(extends, list) or len(extends) > 1:
        raise KnowledgeFormatError(f"Review-policy extends must contain at most one parent in {resolved}")
    merged: dict[str, Any] = {}
    for reference in extends:
        if not isinstance(reference, str):
            raise KnowledgeFormatError(f"Review-policy parent reference must be a string in {resolved}")
        parent = (resolved.parent / reference).resolve()
        if not parent.is_file():
            raise KnowledgeFormatError(f"Parent review policy {reference!r} from {resolved} does not exist")
        merged = deep_merge(merged, _load_source(parent, (*stack, resolved)))
    return deep_merge(merged, current)


def resolve_project_policy(path: Path, change_class: str) -> dict[str, Any]:
    if change_class not in CHANGE_CLASSES:
        raise KnowledgeFormatError(f"Unknown review change class {change_class!r}")
    source = _load_source(path, ())
    defaults = source.get("defaults", {})
    classes = source.get("change_classes", {})
    if not isinstance(defaults, dict) or not isinstance(classes, dict):
        raise KnowledgeFormatError("Review-policy source must define mapping defaults and change_classes")
    override = classes.get(change_class)
    if not isinstance(override, dict):
        raise KnowledgeFormatError(f"Review-policy source does not specialize {change_class!r}")
    selected = deep_merge(defaults, override)
    selected.update(
        {
            "schema_version": "1.0",
            "id": source.get("id"),
            "version": source.get("version"),
            "abstract": False,
            "change_class": change_class,
        }
    )
    issues = effective_policy_issues(selected)
    if issues:
        raise KnowledgeFormatError("Invalid effective review policy: " + "; ".join(issues))
    return selected


def default_project_policy_path() -> Path:
    return toolkit_root() / "policy" / "review-policy.yaml"
