"""Deterministic applicability routing for Gnostoa's extended verification."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_UNCONDITIONAL_EVENTS = {"schedule", "workflow_dispatch"}
_CANDIDATE_EVENTS = {"pull_request", "merge_group", "push"}
_HIGH_RISK_PREFIXES = (
    ".github/workflows/",
    "ci/",
    "core/",
    "docs/",
    "guidance/",
    "knowledge/",
    "requirements/",
    "schemas/",
    "tasks/",
    "templates/",
    "tests/",
    "tools/",
)
_HIGH_RISK_EXACT = {
    ".dockerignore",
    ".gitignore",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "Dockerfile",
    "README.md",
    "SECURITY.md",
    "mkdocs.yml",
    "pyproject.toml",
}
_MAX_PATH_INPUT_BYTES = 4_194_304


@dataclass(frozen=True)
class ExtendedRoute:
    decision: str
    reason: str

    @property
    def run_extended(self) -> bool:
        return self.decision == "RUN"


def _valid_path(path: str) -> bool:
    candidate = PurePosixPath(path)
    return (
        bool(path)
        and path.isprintable()
        and not candidate.is_absolute()
        and ".." not in candidate.parts
    )


def _high_risk(path: str) -> bool:
    return (
        path in _HIGH_RISK_EXACT
        or path.endswith(".py")
        or any(path.startswith(prefix) for prefix in _HIGH_RISK_PREFIXES)
    )


def route_extended(
    event_name: str,
    changed_paths: tuple[str, ...],
    *,
    ref_name: str = "",
) -> ExtendedRoute:
    """Return an explicit run/not-applicable decision for one provider event."""

    if event_name in _UNCONDITIONAL_EVENTS:
        return ExtendedRoute("RUN", f"{event_name} requires full evidence")
    if event_name not in _CANDIDATE_EVENTS:
        return ExtendedRoute(
            "NOT_APPLICABLE",
            f"unsupported event {event_name!r}",
        )
    if event_name == "push" and ref_name != "refs/heads/main":
        return ExtendedRoute(
            "NOT_APPLICABLE",
            "push is outside the protected integration ref",
        )
    invalid = [path for path in changed_paths if not _valid_path(path)]
    if invalid:
        raise ValueError("changed paths contain an unsafe repository-relative path")
    for path in sorted(set(changed_paths)):
        if _high_risk(path):
            return ExtendedRoute("RUN", f"applicable changed path: {path}")
    if not changed_paths:
        return ExtendedRoute("NOT_APPLICABLE", "candidate has no changed paths")
    return ExtendedRoute(
        "NOT_APPLICABLE",
        "candidate changes no declared extended-evidence surface",
    )


def _changed_paths() -> tuple[str, ...]:
    raw = sys.stdin.buffer.read(_MAX_PATH_INPUT_BYTES + 1)
    if len(raw) > _MAX_PATH_INPUT_BYTES:
        raise ValueError("changed-path input exceeds the bounded size")
    if not raw:
        return ()
    try:
        return tuple(part.decode("utf-8") for part in raw.split(b"\0") if part)
    except UnicodeDecodeError as exc:
        raise ValueError("changed paths are not valid UTF-8") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    parser.add_argument("--ref", default="")
    parser.add_argument("--github-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = route_extended(args.event, _changed_paths(), ref_name=args.ref)
    except ValueError as exc:
        print(f"ERROR: extended route failed: {exc}", file=sys.stderr)
        return 2
    print(f"extended route: {result.decision} — {result.reason}")
    if args.github_output is not None:
        if "\n" in result.reason or "\r" in result.reason:
            print("ERROR: extended route produced an unsafe reason", file=sys.stderr)
            return 2
        with args.github_output.open("a", encoding="utf-8") as stream:
            stream.write(f"decision={result.decision}\n")
            stream.write(f"run_extended={'true' if result.run_extended else 'false'}\n")
            stream.write(f"reason={result.reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
