from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

from .knowledge_common import (
    Document,
    KnowledgeFormatError,
    load_concepts,
    load_profile,
    parse_markdown,
    relation_target_document,
)
from .validate_bundle import validate_bundle


def _document_key(document: Document) -> str:
    return "/" + document.relative_path.as_posix()


def _resolve_seeds(
    seeds: list[str],
    by_id: dict[str, Document],
    by_key: dict[str, Document],
) -> list[Document]:
    resolved: list[Document] = []
    for seed in seeds:
        document = by_id.get(seed) or by_key.get(
            seed if seed.startswith("/") else f"/{seed}"
        )
        if document is None:
            available = ", ".join(sorted(by_id)[:12])
            raise KnowledgeFormatError(
                f"Unknown seed {seed!r}. Example available IDs: {available}"
            )
        if document not in resolved:
            resolved.append(document)
    return resolved


def _neighbors(
    document: Document,
    bundle: Path,
    by_id: dict[str, Document],
    by_path: dict[Path, Document],
    incoming: dict[Path, list[Document]],
) -> list[Document]:
    result: list[Document] = []
    for relation in document.project_metadata.get("relations", []) or []:
        if not isinstance(relation, dict) or not isinstance(
            relation.get("target"), str
        ):
            continue
        target = relation_target_document(
            bundle,
            document,
            relation["target"],
            by_id,
            by_path,
        )
        if target is not None and target not in result:
            result.append(target)
    for source in incoming.get(document.path.resolve(), []):
        if source not in result:
            result.append(source)
    return sorted(result, key=lambda item: item.relative_path.as_posix())


def _render_document(document: Document) -> str:
    metadata = document.metadata
    project = document.project_metadata
    owners = ", ".join(project.get("owners", [])) or "unassigned"
    scope = ", ".join(project.get("scope", []))
    lines = [
        f"## {metadata.get('title', document.relative_path.stem)}",
        "",
        f"- ID: `{document.concept_id or 'missing'}`",
        f"- Type/status: `{metadata.get('type', 'unknown')}` / "
        f"`{metadata.get('status', 'unknown')}`",
        f"- Owners: {owners}",
        f"- Path: `/{document.relative_path.as_posix()}`",
    ]
    if scope:
        lines.append(f"- Scope: {scope}")
    lines.extend(["", metadata.get("description", "No description.")])

    relations = project.get("relations", []) or []
    if relations:
        lines.extend(["", "Relations:"])
        for relation in relations:
            if isinstance(relation, dict):
                lines.append(
                    f"- `{relation.get('kind', 'unknown')}` → "
                    f"`{relation.get('target', 'missing')}`"
                )
    return "\n".join(lines) + "\n"


def build_pack(
    profile_path: Path,
    bundle_path: Path,
    seeds: list[str],
    depth: int = 1,
    max_tokens: int = 1600,
) -> str:
    _, issues = validate_bundle(profile_path, bundle_path)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        preview = "; ".join(f"{issue.path}: {issue.message}" for issue in errors[:5])
        raise KnowledgeFormatError(
            f"Refusing to build context from an invalid bundle: {preview}"
        )

    profile = load_profile(profile_path.resolve())
    bundle = bundle_path.resolve()
    concepts = load_concepts(bundle)
    by_id = {
        document.concept_id: document
        for document in concepts
        if document.concept_id is not None
    }
    by_key = {_document_key(document): document for document in concepts}
    by_path = {document.path.resolve(): document for document in concepts}
    selected_seeds = _resolve_seeds(seeds, by_id, by_key)

    incoming: dict[Path, list[Document]] = {}
    for source in concepts:
        for relation in source.project_metadata.get("relations", []) or []:
            if not isinstance(relation, dict) or not isinstance(
                relation.get("target"), str
            ):
                continue
            target = relation_target_document(
                bundle,
                source,
                relation["target"],
                by_id,
                by_path,
            )
            if target is not None:
                incoming.setdefault(target.path.resolve(), []).append(source)

    queue = deque((document, 0) for document in selected_seeds)
    ordered: list[Document] = []
    seen: set[Path] = set()
    while queue:
        document, level = queue.popleft()
        resolved_path = document.path.resolve()
        if resolved_path in seen:
            continue
        seen.add(resolved_path)
        ordered.append(document)
        if level < depth:
            for neighbor in _neighbors(document, bundle, by_id, by_path, incoming):
                queue.append((neighbor, level + 1))

    root_index = parse_markdown(bundle / "index.md", bundle)
    header = "\n".join(
        [
            "# Agent orientation context pack",
            "",
            f"- Profile: `{profile['id']}` `{profile['version']}`",
            f"- OKF: `{profile['okf_version']}`",
            f"- Seeds: {', '.join(f'`{seed}`' for seed in seeds)}",
            f"- Graph depth: `{depth}`",
            "- Authority: derived orientation only; follow concept paths for evidence.",
            "",
            "## Corpus roadmap",
            "",
            root_index.body.strip(),
            "",
        ]
    )

    max_characters = max_tokens * 4
    output = header
    included = 0
    for document in ordered:
        section = "\n" + _render_document(document)
        if len(output) + len(section) > max_characters:
            output += (
                "\n## Truncation\n\n"
                f"Stopped after {included} concept(s) at the approximate "
                f"{max_tokens}-token budget.\n"
            )
            break
        output += section
        included += 1
    return output.rstrip() + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic orientation pack from an OKF graph."
    )
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--seed", required=True, action="append")
    parser.add_argument("--depth", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=1600)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.depth < 0 or args.max_tokens < 128:
        print(
            "ERROR: depth must be >= 0 and max-tokens must be >= 128", file=sys.stderr
        )
        return 2
    try:
        result = build_pack(
            args.profile,
            args.bundle,
            args.seed,
            args.depth,
            args.max_tokens,
        )
    except (KnowledgeFormatError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
