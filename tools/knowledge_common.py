from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml


FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|$)(?P<body>.*)\Z",
    re.DOTALL,
)
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
RESERVED_NAMES = {"index.md", "log.md"}
POLICY_RANK = {"ignore": 0, "warning": 1, "error": 2}


class KnowledgeLoader(yaml.SafeLoader):
    """Safe YAML loader that keeps ISO dates as strings."""


KnowledgeLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:timestamp"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class KnowledgeFormatError(ValueError):
    pass


def toolkit_root() -> Path:
    configured = os.environ.get("KNOWLEDGE_KIT_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Document:
    path: Path
    relative_path: Path
    metadata: dict[str, Any]
    body: str

    @property
    def project_metadata(self) -> dict[str, Any]:
        value = self.metadata.get("x-project-knowledge", {})
        return value if isinstance(value, dict) else {}

    @property
    def concept_id(self) -> str | None:
        value = self.project_metadata.get("id")
        return value if isinstance(value, str) else None


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=KnowledgeLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise KnowledgeFormatError(f"Cannot load YAML file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise KnowledgeFormatError(f"Expected a YAML mapping in {path}")
    return value


def parse_markdown(path: Path, root: Path) -> Document:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeFormatError(f"Cannot read {path}: {exc}") from exc

    match = FRONTMATTER_RE.match(text)
    if not match:
        return Document(path, path.relative_to(root), {}, text)

    try:
        metadata = yaml.load(match.group("yaml"), Loader=KnowledgeLoader)
    except yaml.YAMLError as exc:
        raise KnowledgeFormatError(f"Invalid frontmatter in {path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise KnowledgeFormatError(f"Frontmatter in {path} must be a mapping")
    return Document(path, path.relative_to(root), metadata, match.group("body"))


def iter_documents(bundle: Path) -> Iterable[Document]:
    root = bundle.resolve()
    for path in sorted(root.rglob("*.md")):
        yield parse_markdown(path, root)


def load_concepts(bundle: Path) -> list[Document]:
    return [
        document
        for document in iter_documents(bundle)
        if document.path.name not in RESERVED_NAMES
    ]


def deep_merge(parent: Any, child: Any) -> Any:
    if isinstance(parent, dict) and isinstance(child, dict):
        merged = dict(parent)
        for key, value in child.items():
            merged[key] = (
                deep_merge(merged[key], value) if key in merged else value
            )
        return merged
    if isinstance(parent, list) and isinstance(child, list):
        merged = list(parent)
        for value in child:
            if value not in merged:
                merged.append(value)
        return merged
    return child


def _assert_monotonic(parent: dict[str, Any], child: dict[str, Any], path: Path) -> None:
    parent_rules = parent.get("rules", {})
    child_rules = child.get("rules", {})
    if not isinstance(parent_rules, dict) or not isinstance(child_rules, dict):
        return

    for name in ("unknown_types", "unknown_relation_kinds", "broken_links"):
        if name not in child_rules or name not in parent_rules:
            continue
        parent_rank = POLICY_RANK.get(parent_rules[name], -1)
        child_rank = POLICY_RANK.get(child_rules[name], -1)
        if child_rank < parent_rank:
            raise KnowledgeFormatError(
                f"{path} weakens parent rule {name}: "
                f"{parent_rules[name]} -> {child_rules[name]}"
            )

    for name in (
        "stable_requires_verification",
        "stable_requires_human_verification",
        "require_unique_ids",
    ):
        if parent_rules.get(name) is True and child_rules.get(name) is False:
            raise KnowledgeFormatError(f"{path} disables parent rule {name}")

    parent_okf = parent.get("okf_version")
    child_okf = child.get("okf_version")
    if parent_okf and child_okf and parent_okf != child_okf:
        raise KnowledgeFormatError(
            f"{path} changes OKF version {parent_okf} -> {child_okf}"
        )


def load_profile(path: Path) -> dict[str, Any]:
    return _load_profile(path.resolve(), ())


def _load_profile(path: Path, stack: tuple[Path, ...]) -> dict[str, Any]:
    if path in stack:
        chain = " -> ".join(str(item) for item in (*stack, path))
        raise KnowledgeFormatError(f"Profile inheritance cycle: {chain}")

    current = load_yaml(path)
    extends = current.get("extends", [])
    if not isinstance(extends, list):
        raise KnowledgeFormatError(f"Profile extends must be a list in {path}")

    merged: dict[str, Any] = {}
    for reference in extends:
        if not isinstance(reference, str):
            raise KnowledgeFormatError(f"Profile reference must be a string in {path}")
        parent_path = (path.parent / reference).resolve()
        if not parent_path.is_file():
            raise KnowledgeFormatError(
                f"Parent profile {reference!r} from {path} does not exist"
            )
        parent = _load_profile(parent_path, (*stack, path))
        merged = deep_merge(merged, parent)

    _assert_monotonic(merged, current, path)
    return deep_merge(merged, current)


def markdown_links(body: str) -> list[str]:
    links: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(body):
        raw = match.group(1).strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        target = raw.split(maxsplit=1)[0]
        links.append(target)
    return links


def headings(body: str) -> set[str]:
    return {match.group(1).strip().casefold() for match in HEADING_RE.finditer(body)}


def is_external_target(target: str) -> bool:
    if target.startswith(("#", "mailto:")):
        return True
    parsed = urlparse(target)
    return bool(parsed.scheme)


def resolve_target(bundle: Path, source: Path, target: str) -> Path | None:
    clean_target = target.split("#", 1)[0].split("?", 1)[0]
    if not clean_target or is_external_target(clean_target):
        return None
    if clean_target.startswith("/"):
        resolved = bundle.resolve() / clean_target.lstrip("/")
    else:
        resolved = source.parent / clean_target
    resolved = resolved.resolve()
    if resolved.is_dir():
        resolved = resolved / "index.md"
    return resolved


def relation_target_document(
    bundle: Path,
    source: Document,
    target: str,
    concepts_by_id: dict[str, Document],
    concepts_by_path: dict[Path, Document],
) -> Document | None:
    if target in concepts_by_id:
        return concepts_by_id[target]
    resolved = resolve_target(bundle, source.path, target)
    if resolved is None:
        return None
    return concepts_by_path.get(resolved)
