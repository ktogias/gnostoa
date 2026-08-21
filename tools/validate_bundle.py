from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_common import (
    RESERVED_NAMES,
    Document,
    KnowledgeFormatError,
    headings,
    is_external_target,
    iter_documents,
    load_profile,
    markdown_links,
    relation_target_document,
    toolkit_root,
)


@dataclass(frozen=True, order=True)
class Issue:
    severity: str
    path: str
    message: str


def _schema(path: Path) -> dict[str, Any]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise KnowledgeFormatError(f"Schema must be a mapping in {path}")
    return schema


def _verification_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _policy_issue(
    issues: list[Issue], policy: str, path: Path, message: str, bundle: Path
) -> None:
    if policy == "ignore":
        return
    issues.append(Issue(policy, str(path.relative_to(bundle)), message))


def _within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _lexical_in_root(root: Path, base: Path, reference: Path) -> Path | None:
    """Join and normalise a path without consulting the filesystem.

    Returning ``None`` on the first attempt to leave ``root`` prevents an
    out-and-back reference from probing an intermediate outside directory.
    ``root`` and ``base`` are already absolute paths supplied by the supported
    validation route.
    """

    if reference.is_absolute():
        try:
            parts = reference.relative_to(root).parts
        except ValueError:
            return None
        stack: list[str] = []
    else:
        try:
            stack = list(base.relative_to(root).parts)
        except ValueError:
            return None
        parts = reference.parts

    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not stack:
                return None
            stack.pop()
            continue
        stack.append(part)

    candidate = root.joinpath(*stack)
    return candidate if _within(root, candidate) else None


def _canonicalise_markdown_target(root: Path, candidate: Path) -> tuple[Path, bool]:
    """Resolve symlinks while observing only path objects inside ``root``.

    The boolean reports an authority escape. Missing in-root components remain
    as an in-root unresolved path so the existing broken-link check can handle
    them. This is a bounded validation ordering property, not a general
    race-free filesystem capability.
    """

    pending = deque(candidate.relative_to(root).parts)
    resolved = root
    followed = 0

    while pending:
        component = pending.popleft()
        current = resolved / component
        try:
            metadata = current.lstat()
        except OSError:
            return current.joinpath(*pending), False

        if not stat.S_ISLNK(metadata.st_mode):
            resolved = current
            continue

        followed += 1
        if followed > 40:
            return current.joinpath(*pending), False

        try:
            declared_target = Path(os.readlink(current))
        except OSError:
            return current.joinpath(*pending), False

        symlink_target = _lexical_in_root(
            root,
            current.parent,
            declared_target,
        )
        if symlink_target is None:
            return current, True

        pending = deque((*symlink_target.relative_to(root).parts, *pending))
        resolved = root

    return resolved, False


def _resolve_markdown_target(
    bundle: Path,
    source: Path,
    target: str,
    project_root: Path,
) -> tuple[Path | None, bool]:
    """Resolve one local Markdown target within the explicit project root."""

    clean_target = target.split("#", 1)[0].split("?", 1)[0]
    if not clean_target or is_external_target(clean_target):
        return None, False

    if clean_target.startswith("/"):
        base = bundle
        reference = Path(clean_target.lstrip("/"))
    else:
        base = source.parent
        reference = Path(clean_target)

    lexical_target = _lexical_in_root(project_root, base, reference)
    if lexical_target is None:
        return None, True

    resolved, escaped = _canonicalise_markdown_target(
        project_root,
        lexical_target,
    )
    if escaped:
        return None, True

    if resolved.is_dir():
        index_target = _lexical_in_root(project_root, resolved, Path("index.md"))
        if index_target is None:
            return None, True
        resolved, escaped = _canonicalise_markdown_target(
            project_root,
            index_target,
        )
        if escaped:
            return None, True

    return resolved, False


def _validate_links(
    documents: Iterable[Document],
    bundle: Path,
    policy: str,
    issues: list[Issue],
    *,
    project_root: Path,
) -> None:
    for document in documents:
        for target in markdown_links(document.body):
            resolved, escaped = _resolve_markdown_target(
                bundle,
                document.path,
                target,
                project_root,
            )
            if escaped:
                _policy_issue(
                    issues,
                    policy,
                    document.path,
                    f"local Markdown link {target!r} escapes project root",
                    bundle,
                )
            elif resolved is not None and not resolved.exists():
                _policy_issue(
                    issues,
                    policy,
                    document.path,
                    f"broken Markdown link {target!r}",
                    bundle,
                )


def validate_bundle(
    profile_path: Path,
    bundle_path: Path,
    schema_dir: Path | None = None,
    *,
    project_root: Path,
) -> tuple[dict[str, Any], list[Issue]]:
    profile_path = profile_path.resolve()
    bundle = bundle_path.resolve()
    project_root = project_root.resolve()
    schema_dir = schema_dir.resolve() if schema_dir else toolkit_root() / "schemas"
    issues: list[Issue] = []

    if not bundle.is_dir():
        raise KnowledgeFormatError(f"Bundle directory does not exist: {bundle}")

    profile = load_profile(profile_path, project_root=project_root)
    profile_errors = sorted(
        Draft202012Validator(_schema(schema_dir / "profile.schema.json")).iter_errors(
            profile
        ),
        key=lambda error: list(error.absolute_path),
    )
    for error in profile_errors:
        location = ".".join(str(item) for item in error.absolute_path) or "<root>"
        issues.append(Issue("error", str(profile_path), f"{location}: {error.message}"))

    documents = list(iter_documents(bundle))
    concepts = [doc for doc in documents if doc.path.name not in RESERVED_NAMES]
    rules = profile.get("rules", {})
    known_types = set(profile.get("concept_types", []))
    known_relations = set(profile.get("relation_kinds", []))
    required_fields = rules.get("required_fields", [])
    required_project_fields = rules.get("required_project_fields", [])

    root_index_path = bundle / "index.md"
    root_index = next(
        (doc for doc in documents if doc.path.resolve() == root_index_path), None
    )
    if root_index is None:
        issues.append(Issue("error", "index.md", "missing bundle root index"))
    elif root_index.metadata.get("okf_version") != profile.get("okf_version"):
        issues.append(
            Issue(
                "error",
                "index.md",
                "root index okf_version does not match the resolved profile",
            )
        )

    for document in documents:
        if (
            document.path.name == "index.md"
            and document.path.resolve() != root_index_path
            and document.metadata
        ):
            issues.append(
                Issue(
                    "error",
                    str(document.relative_path),
                    "nested index.md must not contain frontmatter",
                )
            )
        if document.path.name == "log.md" and document.metadata:
            issues.append(
                Issue(
                    "error",
                    str(document.relative_path),
                    "log.md must not contain concept frontmatter",
                )
            )

    frontmatter_validator = Draft202012Validator(
        _schema(schema_dir / "frontmatter.schema.json")
    )
    concepts_by_id: dict[str, Document] = {}
    concepts_by_path = {document.path.resolve(): document for document in concepts}

    for document in concepts:
        relative = str(document.relative_path)
        if not document.metadata:
            issues.append(Issue("error", relative, "missing YAML frontmatter"))
            continue

        schema_errors = sorted(
            frontmatter_validator.iter_errors(document.metadata),
            key=lambda error: list(error.absolute_path),
        )
        for error in schema_errors:
            location = ".".join(str(item) for item in error.absolute_path) or "<root>"
            issues.append(Issue("error", relative, f"{location}: {error.message}"))

        for field in required_fields:
            if field not in document.metadata:
                issues.append(
                    Issue("error", relative, f"missing required field {field}")
                )

        concept_type = document.metadata.get("type")
        if concept_type not in known_types:
            _policy_issue(
                issues,
                rules.get("unknown_types", "error"),
                document.path,
                f"unknown concept type {concept_type!r}",
                bundle,
            )

        status = document.metadata.get("status")
        if status not in rules.get("statuses", []):
            issues.append(Issue("error", relative, f"unsupported status {status!r}"))

        verification = _verification_entries(document.metadata.get("verified"))
        if status == "stable" and rules.get("stable_requires_verification"):
            if not verification:
                issues.append(
                    Issue("error", relative, "stable concept has no verification")
                )
        if status == "stable" and rules.get("stable_requires_human_verification"):
            if not any(
                isinstance(entry.get("by"), str) and entry["by"].startswith("human:")
                for entry in verification
            ):
                issues.append(
                    Issue(
                        "error",
                        relative,
                        "stable concept has no human: verifier",
                    )
                )

        project_metadata = document.project_metadata
        for field in required_project_fields:
            if field not in project_metadata:
                issues.append(
                    Issue(
                        "error",
                        relative,
                        f"x-project-knowledge missing required field {field}",
                    )
                )

        concept_id = document.concept_id
        if concept_id:
            if concept_id in concepts_by_id and rules.get("require_unique_ids"):
                first = concepts_by_id[concept_id]
                issues.append(
                    Issue(
                        "error",
                        relative,
                        f"duplicate concept ID {concept_id!r}; first in "
                        f"{first.relative_path}",
                    )
                )
            else:
                concepts_by_id[concept_id] = document

        required_sections = (
            profile.get("type_rules", {})
            .get(concept_type, {})
            .get("required_sections", [])
        )
        present_headings = headings(document.body)
        for section in required_sections:
            if section.casefold() not in present_headings:
                issues.append(
                    Issue(
                        "error",
                        relative,
                        f"missing required section {section!r} for {concept_type}",
                    )
                )

    for document in concepts:
        for relation in document.project_metadata.get("relations", []) or []:
            if not isinstance(relation, dict):
                continue
            kind = relation.get("kind")
            target = relation.get("target")
            if kind not in known_relations:
                _policy_issue(
                    issues,
                    rules.get("unknown_relation_kinds", "error"),
                    document.path,
                    f"unknown relationship kind {kind!r}",
                    bundle,
                )
            if isinstance(target, str):
                target_document = relation_target_document(
                    bundle,
                    document,
                    target,
                    concepts_by_id,
                    concepts_by_path,
                )
                if target_document is None:
                    _policy_issue(
                        issues,
                        rules.get("broken_links", "error"),
                        document.path,
                        f"relationship target {target!r} does not resolve",
                        bundle,
                    )

    _validate_links(
        documents,
        bundle,
        rules.get("broken_links", "error"),
        issues,
        project_root=project_root,
    )
    return profile, sorted(issues)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an OKF bundle against an inherited project profile."
    )
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--schema-dir", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Return a failing exit status when warnings are present.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        profile, issues = validate_bundle(
            args.profile,
            args.bundle,
            args.schema_dir,
            project_root=args.project_root,
        )
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for issue in issues:
        print(f"{issue.severity.upper()}: {issue.path}: {issue.message}")

    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    if not issues:
        print(
            f"OK: bundle conforms to {profile['id']} "
            f"{profile['version']} (OKF {profile['okf_version']})"
        )
    else:
        print(f"Summary: {errors} error(s), {warnings} warning(s)")
    return 1 if errors or (warnings and args.strict_warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
