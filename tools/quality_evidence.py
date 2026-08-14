"""Collect bounded release-quality evidence for the current tracked tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, TextIO

from tools.repository_scope import candidate_paths

DEFAULT_COVERAGE_FLOOR = 65.0


class QualityEvidenceError(RuntimeError):
    """A quality-evidence precondition or gate failed."""


def file_evidence(path: Path) -> dict[str, int | str]:
    """Return content identity without embedding a host-specific path."""

    content = path.read_bytes()
    return {
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }


def json_array_diagnostic_count(path: Path, label: str) -> int:
    """Validate a JSON-array diagnostic report and return its item count."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityEvidenceError(f"cannot read {label}: {exc}") from exc
    if not isinstance(document, list) or any(
        not isinstance(item, dict) for item in document
    ):
        raise QualityEvidenceError(f"{label} is not a JSON diagnostic array")
    return len(document)


def json_lines_diagnostic_count(path: Path, label: str) -> int:
    """Validate a JSON-lines diagnostic report and return its record count."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise QualityEvidenceError(f"cannot read {label}: {exc}") from exc

    count = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            diagnostic = json.loads(line)
        except json.JSONDecodeError as exc:
            raise QualityEvidenceError(f"cannot read {label}: {exc}") from exc
        if not isinstance(diagnostic, dict):
            raise QualityEvidenceError(f"{label} contains a non-object diagnostic")
        count += 1
    return count


def secret_findings(document: dict[str, Any]) -> list[dict[str, int | str]]:
    """Return reviewable secret-candidate metadata without secret material."""

    results = document.get("results")
    if not isinstance(results, dict):
        raise QualityEvidenceError("detect-secrets report has no results mapping")

    findings: list[dict[str, int | str]] = []
    for path, candidates in sorted(results.items()):
        if not isinstance(path, str) or not isinstance(candidates, list):
            raise QualityEvidenceError("detect-secrets results are malformed")
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise QualityEvidenceError("detect-secrets candidate is malformed")
            candidate_type = candidate.get("type")
            line = candidate.get("line_number")
            if not isinstance(candidate_type, str) or not isinstance(line, int):
                raise QualityEvidenceError(
                    "detect-secrets candidate lacks a type or line number"
                )
            findings.append(
                {
                    "path": path,
                    "line": line,
                    "type": candidate_type,
                }
            )
    return findings


def dependency_audit_summary(document: dict[str, Any]) -> dict[str, Any]:
    """Summarize pip-audit output without weakening its exit-code gate."""

    dependencies = document.get("dependencies")
    if not isinstance(dependencies, list):
        raise QualityEvidenceError("pip-audit report has no dependencies list")

    vulnerability_ids: list[str] = []
    vulnerability_count = 0
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise QualityEvidenceError("pip-audit dependency is malformed")
        vulnerabilities = dependency.get("vulns")
        if not isinstance(vulnerabilities, list):
            raise QualityEvidenceError("pip-audit dependency has no vulns list")
        vulnerability_count += len(vulnerabilities)
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise QualityEvidenceError("pip-audit vulnerability is malformed")
            identifier = vulnerability.get("id")
            if isinstance(identifier, str):
                vulnerability_ids.append(identifier)

    return {
        "dependencies": len(dependencies),
        "vulnerabilities": vulnerability_count,
        "vulnerability_ids": sorted(vulnerability_ids),
    }


def _run(
    command: list[str],
    *,
    root: Path,
    environment: dict[str, str] | None = None,
    stdout: TextIO | None = None,
) -> int:
    displayed = command
    if len(displayed) > 20:
        displayed = [*displayed[:8], f"<{len(displayed) - 8} bounded arguments>"]
    print("+ " + " ".join(displayed), flush=True)
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        stdout=stdout,
        check=False,
    )
    return completed.returncode


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityEvidenceError(f"cannot read {label}: {exc}") from exc
    if not isinstance(document, dict):
        raise QualityEvidenceError(f"{label} is not a JSON object")
    return document


def _git_state(root: Path) -> dict[str, Any]:
    revision = os.environ.get("KNOWLEDGE_KIT_REVISION", "unbound")
    dirty: bool | None = None
    try:
        revision_result = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        revision = revision_result.stdout.strip()
        status_result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root}",
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        dirty = bool(status_result.stdout)
    except (OSError, subprocess.CalledProcessError):
        pass
    return {"revision": revision, "tracked_tree_dirty": dirty}


def _tool_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in (
        "coverage",
        "detect-secrets",
        "mypy",
        "pip-audit",
        "ruff",
        "types-PyYAML",
        "types-jsonschema",
    ):
        try:
            versions[distribution] = metadata.version(distribution)
        except metadata.PackageNotFoundError as exc:
            raise QualityEvidenceError(
                f"required quality tool is not installed: {distribution}"
            ) from exc
    return versions


def collect_quality_evidence(
    repository_root: Path,
    output_directory: Path,
    *,
    coverage_floor: float = DEFAULT_COVERAGE_FLOOR,
) -> Path:
    """Run the bounded gates and write a content-addressable summary."""

    root = repository_root.resolve()
    output = output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)

    tracked_paths = candidate_paths(root)
    if not tracked_paths:
        raise QualityEvidenceError("tracked-tree secret scan has no candidate files")
    tracked_symlinks = [
        path.as_posix() for path in tracked_paths if (root / path).is_symlink()
    ]
    if tracked_symlinks:
        raise QualityEvidenceError(
            "tracked-tree secret scan refuses symlinks: " + ", ".join(tracked_symlinks)
        )

    coverage_data = output / ".coverage"
    coverage_report = output / "coverage.json"
    format_report = output / "ruff-format.json"
    lint_report = output / "ruff-lint.json"
    typing_report = output / "mypy.jsonl"
    runtime_audit = output / "runtime-dependency-audit.json"
    development_audit = output / "development-dependency-audit.json"
    secret_report = output / "tracked-tree-secret-scan.json"
    summary_path = output / "quality-summary.json"

    environment = os.environ.copy()
    environment["COVERAGE_FILE"] = str(coverage_data)
    environment["MYPY_CACHE_DIR"] = str(output / ".mypy_cache")
    environment["RUFF_CACHE_DIR"] = str(output / ".ruff_cache")
    python = sys.executable
    statuses: dict[str, int] = {}

    with format_report.open("w", encoding="utf-8") as stream:
        statuses["format"] = _run(
            [
                python,
                "-m",
                "ruff",
                "format",
                "--check",
                "--output-format",
                "json",
                "tools",
                "ci",
                "tests",
            ],
            root=root,
            environment=environment,
            stdout=stream,
        )
    with lint_report.open("w", encoding="utf-8") as stream:
        statuses["lint"] = _run(
            [
                python,
                "-m",
                "ruff",
                "check",
                "--output-format",
                "json",
                "tools",
                "ci",
                "tests",
            ],
            root=root,
            environment=environment,
            stdout=stream,
        )
    with typing_report.open("w", encoding="utf-8") as stream:
        statuses["typing"] = _run(
            [python, "-m", "mypy", "--output", "json", "tools", "ci"],
            root=root,
            environment=environment,
            stdout=stream,
        )

    statuses["coverage_erase"] = _run(
        [python, "-m", "coverage", "erase"],
        root=root,
        environment=environment,
    )
    statuses["coverage_run"] = _run(
        [
            python,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--source=tools",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
        ],
        root=root,
        environment=environment,
    )
    statuses["coverage_floor"] = _run(
        [
            python,
            "-m",
            "coverage",
            "report",
            "--show-missing",
            f"--fail-under={coverage_floor:g}",
        ],
        root=root,
        environment=environment,
    )
    statuses["coverage_json"] = _run(
        [python, "-m", "coverage", "json", "-o", str(coverage_report)],
        root=root,
        environment=environment,
    )

    for label, requirements, report in (
        ("runtime_audit", root / "requirements" / "runtime.lock", runtime_audit),
        (
            "development_audit",
            root / "requirements" / "development.lock",
            development_audit,
        ),
    ):
        statuses[label] = _run(
            [
                python,
                "-m",
                "pip_audit",
                "--no-deps",
                "--strict",
                "--progress-spinner",
                "off",
                "--requirement",
                str(requirements),
                "--format",
                "json",
                "--output",
                str(report),
            ],
            root=root,
        )

    with secret_report.open("w", encoding="utf-8") as stream:
        statuses["secret_scan"] = _run(
            [
                python,
                "-m",
                "detect_secrets",
                "--cores",
                "1",
                "scan",
                "--no-verify",
                *(path.as_posix() for path in tracked_paths),
            ],
            root=root,
            stdout=stream,
        )

    coverage_document = _read_json(coverage_report, "coverage report")
    runtime_document = _read_json(runtime_audit, "runtime dependency audit")
    development_document = _read_json(
        development_audit,
        "development dependency audit",
    )
    secret_document = _read_json(secret_report, "tracked-tree secret scan")

    totals = coverage_document.get("totals")
    if not isinstance(totals, dict) or not isinstance(
        totals.get("percent_covered"),
        (int, float),
    ):
        raise QualityEvidenceError("coverage report has no total percentage")
    coverage_percent = float(totals["percent_covered"])
    secret_candidates = secret_findings(secret_document)
    format_diagnostics = json_array_diagnostic_count(
        format_report,
        "Ruff format report",
    )
    lint_diagnostics = json_array_diagnostic_count(
        lint_report,
        "Ruff lint report",
    )
    typing_diagnostics = json_lines_diagnostic_count(
        typing_report,
        "mypy report",
    )

    reports = {
        path.name: file_evidence(path)
        for path in (
            coverage_report,
            format_report,
            lint_report,
            typing_report,
            runtime_audit,
            development_audit,
            secret_report,
        )
    }
    summary = {
        "schema_version": 1,
        "source": _git_state(root),
        "tools": _tool_versions(),
        "scope": {
            "static_quality": {
                "format_and_lint": ["tools", "ci", "tests"],
                "strict_typing": ["tools", "ci"],
            },
            "coverage": "branch-aware unittest coverage of the tools package",
            "dependency_audit": [
                "requirements/runtime.lock",
                "requirements/development.lock",
            ],
            "secret_scan": {
                "boundary": "current Git-tracked regular-file working tree only",
                "tracked_files": len(tracked_paths),
            },
        },
        "thresholds": {"coverage_percent": coverage_floor},
        "results": {
            "static_quality": {
                "format_diagnostics": format_diagnostics,
                "lint_diagnostics": lint_diagnostics,
                "typing_diagnostics": typing_diagnostics,
            },
            "coverage": {
                "percent": coverage_percent,
                "passes_floor": coverage_percent >= coverage_floor,
            },
            "runtime_dependency_audit": dependency_audit_summary(runtime_document),
            "development_dependency_audit": dependency_audit_summary(
                development_document
            ),
            "secret_scan": {
                "candidates": len(secret_candidates),
                "findings": secret_candidates,
            },
        },
        "command_statuses": statuses,
        "reports": reports,
        "limits": [
            (
                "Formatting, lint and static typing cover the declared Python "
                "paths only; a clean result is not behavior, security or semantic "
                "acceptance evidence."
            ),
            "Coverage is a regression signal, not acceptance or test-quality proof.",
            (
                "The dependency audits cover known Python-package advisories "
                "available from the configured provider at run time; they do not "
                "prove package trustworthiness or cover non-Python components."
            ),
            (
                "The heuristic secret scan covers the current tracked tree, not "
                "Git history, provider metadata, Actions artifacts or logs."
            ),
            "These unsigned CI reports are quality evidence, not release provenance.",
        ],
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failures = [name for name, status in statuses.items() if status != 0]
    if secret_candidates:
        failures.append("secret_candidates")
    if coverage_percent < coverage_floor:
        failures.append("coverage_percent")
    if failures:
        raise QualityEvidenceError(
            "quality evidence failed: " + ", ".join(sorted(set(failures)))
        )
    return summary_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect bounded static-quality, coverage and security evidence",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="candidate repository root (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory for machine-readable reports",
    )
    parser.add_argument(
        "--coverage-floor",
        type=float,
        default=DEFAULT_COVERAGE_FLOOR,
        help="minimum branch-aware tools coverage percentage",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = collect_quality_evidence(
            args.repository_root,
            args.output_dir,
            coverage_floor=args.coverage_floor,
        )
    except QualityEvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"quality evidence: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
