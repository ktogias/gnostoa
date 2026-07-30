from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator

from .knowledge_common import KnowledgeFormatError, load_yaml, toolkit_root


HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
NON_SLUG_RE = re.compile(r"[^\w\s-]", re.UNICODE)


def _schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _anchor(value: str) -> str:
    normalized = NON_SLUG_RE.sub("", value.strip().casefold())
    return re.sub(r"[\s-]+", "-", normalized).strip("-")


def _split_reference(reference: str) -> tuple[str, str | None]:
    path_part, separator, fragment = reference.partition("#")
    if "::" in path_part:
        path_part, selector = path_part.split("::", 1)
        fragment = selector
        separator = "#"
    return path_part, fragment if separator else None


def _check_reference(
    root: Path,
    reference: str,
    label: str,
) -> list[str]:
    path_part, fragment = _split_reference(reference)
    path = (root / path_part).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return [f"{label} escapes repository root: {reference!r}"]
    if not path.is_file():
        return [f"{label} does not exist: {reference!r}"]
    if fragment:
        text = path.read_text(encoding="utf-8")
        if path.suffix.casefold() == ".md":
            headings = {
                _anchor(match.group(1)) for match in HEADING_RE.finditer(text)
            }
            if fragment not in headings:
                return [f"{label} heading does not exist: {reference!r}"]
        if path.suffix.casefold() == ".py":
            symbol = fragment.rsplit(".", 1)[-1]
            definition = re.compile(
                rf"^\s*(?:(?:async\s+)?def|class)\s+{re.escape(symbol)}\b",
                re.MULTILINE,
            )
            if not definition.search(text):
                return [f"{label} Python symbol does not exist: {reference!r}"]
    return []


def check_guardrails(
    manifest_path: Path,
    repository_root: Path,
    schema_path: Path | None = None,
) -> list[str]:
    root = repository_root.resolve()
    manifest = load_yaml(manifest_path.resolve())
    schema = (
        schema_path.resolve()
        if schema_path
        else root / "schemas" / "guardrails.schema.json"
    )
    issues: list[str] = []

    errors = sorted(
        Draft202012Validator(_schema(schema)).iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    for error in errors:
        location = ".".join(str(item) for item in error.absolute_path) or "<root>"
        issues.append(f"{location}: {error.message}")

    seen: set[str] = set()
    guardrails = manifest.get("guardrails", [])
    if not isinstance(guardrails, list):
        return sorted(issues)

    for index, guardrail in enumerate(guardrails):
        if not isinstance(guardrail, dict):
            continue
        guardrail_id = guardrail.get("id")
        label = f"guardrails.{index}"
        if isinstance(guardrail_id, str):
            label = guardrail_id
            if guardrail_id in seen:
                issues.append(f"duplicate guardrail ID {guardrail_id!r}")
            seen.add(guardrail_id)

        guidance = guardrail.get("guidance")
        if isinstance(guidance, str):
            issues.extend(_check_reference(root, guidance, f"{label}.guidance"))

        for field in ("implementation", "tests"):
            references = guardrail.get(field, [])
            if not isinstance(references, list):
                continue
            for reference in references:
                if isinstance(reference, str):
                    issues.extend(
                        _check_reference(root, reference, f"{label}.{field}")
                    )

    return sorted(set(issues))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate guardrail ownership and coverage references."
    )
    default_root = toolkit_root()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_root / "policy" / "guardrails.yaml",
    )
    parser.add_argument("--repository-root", type=Path, default=default_root)
    parser.add_argument("--schema", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        issues = check_guardrails(
            args.manifest,
            args.repository_root,
            args.schema,
        )
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for issue in issues:
        print(f"ERROR: {issue}")
    if issues:
        return 1

    print(f"OK: guardrail coverage is valid ({args.manifest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
