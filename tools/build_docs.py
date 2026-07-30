from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from .knowledge_common import KnowledgeFormatError, toolkit_root


PROJECTION_SURFACES = (
    "core",
    "docs",
    "guidance",
    "knowledge",
    "policy",
    "templates",
)
NAV_DOCUMENT_RE = re.compile(
    r"^(?P<prefix>\s*-\s+[^:\n]+:\s+)(?P<path>[^\s]+\.md)\s*$",
    re.MULTILINE,
)


def _projection_config(source: str, content: Path, site: Path) -> str:
    def prefix_document(match: re.Match[str]) -> str:
        path = match.group("path")
        if path.startswith("docs/"):
            return match.group(0)
        return f"{match.group('prefix')}docs/{path}"

    projected = NAV_DOCUMENT_RE.sub(prefix_document, source)
    return (
        projected.rstrip()
        + "\n"
        + f"docs_dir: {content.as_posix()}\n"
        + f"site_dir: {site.as_posix()}\n"
    )


def prepare_projection(
    repository_root: Path,
    staging_root: Path,
    site_dir: Path,
) -> Path:
    root = repository_root.resolve()
    staging = staging_root.resolve()
    content = staging / "content"
    content.mkdir(parents=True, exist_ok=True)

    for reference in PROJECTION_SURFACES:
        source = root / reference
        if not source.exists():
            raise KnowledgeFormatError(
                f"Documentation projection source does not exist: {source}"
            )
        destination = content / reference
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    source_config = (root / "mkdocs.yml").read_text(encoding="utf-8")
    config = staging / "mkdocs.yml"
    config.write_text(
        _projection_config(source_config, content, site_dir.resolve()),
        encoding="utf-8",
    )
    return config


def build_docs(repository_root: Path, site_dir: Path, strict: bool = True) -> int:
    with tempfile.TemporaryDirectory(prefix="knowledge-docs-") as directory:
        staging = Path(directory)
        config = prepare_projection(repository_root, staging, site_dir)
        command = [
            sys.executable,
            "-m",
            "mkdocs",
            "build",
            "--config-file",
            str(config),
        ]
        if strict:
            command.append("--strict")
        return subprocess.run(command, check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the derived human site from canonical knowledge surfaces."
    )
    parser.add_argument("--repository-root", type=Path, default=toolkit_root())
    parser.add_argument("--site-dir", type=Path, default=Path("site"))
    parser.add_argument("--no-strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return build_docs(
            args.repository_root,
            args.site_dir,
            strict=not args.no_strict,
        )
    except (KnowledgeFormatError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
