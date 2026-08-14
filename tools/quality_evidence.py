"""Collect bounded release-quality evidence for the current tracked tree."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tomllib
import uuid
from importlib import metadata
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import quote

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


def _normalized_distribution_name(name: str) -> str:
    """Return the normalized Python distribution identity used by the locks."""

    return re.sub(r"[-_.]+", "-", name).lower()


def locked_requirements(path: Path) -> list[dict[str, str]]:
    """Parse the repository's deliberately narrow exact-lock format."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise QualityEvidenceError(
            f"cannot read exact lock {path.name}: {exc}"
        ) from exc

    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        if candidate.count("==") != 1:
            raise QualityEvidenceError(
                f"{path.name}:{line_number} must use exact name==version syntax"
            )
        name, version = candidate.split("==", maxsplit=1)
        if (
            not name
            or not version
            or name != name.strip()
            or version != version.strip()
            or any(character.isspace() for character in candidate)
        ):
            raise QualityEvidenceError(
                f"{path.name}:{line_number} must use exact name==version syntax"
            )
        normalized_name = _normalized_distribution_name(name)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized_name):
            raise QualityEvidenceError(
                f"{path.name}:{line_number} has an invalid distribution name"
            )
        if normalized_name in seen:
            raise QualityEvidenceError(
                f"{path.name}:{line_number} duplicates {normalized_name}"
            )
        seen.add(normalized_name)
        requirements.append(
            {
                "name": name,
                "normalized_name": normalized_name,
                "version": version,
            }
        )
    if not requirements:
        raise QualityEvidenceError(f"exact lock {path.name} has no requirements")
    return requirements


def _normalized_spdx_expression(value: str) -> str | None:
    """Validate and normalize an SPDX expression with the pinned parser."""

    try:
        license_expression = importlib.import_module("license_expression")
    except ModuleNotFoundError as exc:
        raise QualityEvidenceError(
            "required quality tool is not installed: license-expression"
        ) from exc

    result = license_expression.get_spdx_licensing().validate(value, strict=True)
    normalized = result.normalized_expression
    if result.errors or not isinstance(normalized, str):
        return None
    return normalized


_TROVE_LICENSE_EXPRESSIONS = {
    "Apache Software License": "Apache-2.0",
    "MIT License": "MIT",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Python Software Foundation License": "PSF-2.0",
}


def _metadata_value(package_metadata: Any, field: str) -> str | None:
    try:
        value = package_metadata[field]
    except KeyError:
        return None
    return value if isinstance(value, str) else None


def _license_record(package_metadata: Any, package_name: str) -> dict[str, Any]:
    expression = package_metadata.get("License-Expression")
    raw_license = package_metadata.get("License")
    classifiers = sorted(
        classifier.removeprefix("License :: OSI Approved :: ")
        for classifier in package_metadata.get_all("Classifier", [])
        if classifier.startswith("License :: OSI Approved :: ")
    )

    if isinstance(expression, str) and expression.strip():
        normalized = _normalized_spdx_expression(expression.strip())
        if normalized is None:
            raise QualityEvidenceError(
                f"{package_name} has an invalid License-Expression"
            )
        return {
            "declaration": expression.strip(),
            "expression": normalized,
            "manual_review": False,
            "source": "license-expression",
        }

    usable_raw = (
        raw_license.strip()
        if isinstance(raw_license, str)
        and raw_license.strip()
        and raw_license.strip().lower() not in {"unknown", "n/a", "none"}
        else None
    )
    if usable_raw is not None:
        normalized = _normalized_spdx_expression(usable_raw)
        if normalized is not None:
            return {
                "declaration": usable_raw,
                "expression": normalized,
                "manual_review": True,
                "source": "legacy-license",
            }

    mapped = sorted(
        {
            _TROVE_LICENSE_EXPRESSIONS[classifier]
            for classifier in classifiers
            if classifier in _TROVE_LICENSE_EXPRESSIONS
        }
    )
    if len(mapped) == 1 and all(
        classifier in _TROVE_LICENSE_EXPRESSIONS for classifier in classifiers
    ):
        return {
            "declaration": mapped[0],
            "expression": mapped[0],
            "manual_review": True,
            "source": "license-classifier",
        }

    declarations = [value for value in [usable_raw, *classifiers] if value]
    if declarations:
        return {
            "declaration": "; ".join(dict.fromkeys(declarations)),
            "expression": None,
            "manual_review": True,
            "source": "legacy-metadata",
        }
    raise QualityEvidenceError(f"{package_name} has no license declaration")


def build_license_inventory(
    lock_path: Path,
    *,
    lock_identity: str,
    scope: str,
) -> dict[str, Any]:
    """Bind exact lock entries to installed distribution license metadata."""

    packages: list[dict[str, Any]] = []
    for requirement in locked_requirements(lock_path):
        try:
            distribution = metadata.distribution(requirement["name"])
        except metadata.PackageNotFoundError as exc:
            raise QualityEvidenceError(
                f"locked distribution is not installed: {requirement['name']}"
            ) from exc
        if distribution.version != requirement["version"]:
            raise QualityEvidenceError(
                "installed distribution version mismatch for "
                f"{requirement['name']}: expected {requirement['version']}, "
                f"found {distribution.version}"
            )
        distribution_name = _metadata_value(distribution.metadata, "Name")
        if not isinstance(distribution_name, str) or (
            _normalized_distribution_name(distribution_name)
            != requirement["normalized_name"]
        ):
            raise QualityEvidenceError(
                f"installed distribution identity mismatch for {requirement['name']}"
            )

        license_record = _license_record(
            distribution.metadata,
            requirement["name"],
        )
        packages.append(
            {
                "name": distribution_name,
                "normalized_name": requirement["normalized_name"],
                "version": distribution.version,
                "metadata_version": _metadata_value(
                    distribution.metadata,
                    "Metadata-Version",
                )
                or "unknown",
                "license": license_record,
                "license_files": sorted(
                    set(distribution.metadata.get_all("License-File", []))
                ),
                "raw_license": _metadata_value(distribution.metadata, "License"),
                "license_classifiers": sorted(
                    classifier
                    for classifier in distribution.metadata.get_all("Classifier", [])
                    if classifier.startswith("License ::")
                ),
            }
        )

    summary = {
        "packages": len(packages),
        "spdx_expressions": sum(
            package["license"]["expression"] is not None for package in packages
        ),
        "legacy_declarations": sum(
            package["license"]["source"] != "license-expression" for package in packages
        ),
        "manual_review": sum(
            bool(package["license"]["manual_review"]) for package in packages
        ),
        "non_spdx_declarations": sum(
            package["license"]["expression"] is None for package in packages
        ),
        "missing_declarations": 0,
    }
    return {
        "schema_version": 1,
        "scope": scope,
        "lock": {
            "path": lock_identity,
            **file_evidence(lock_path),
        },
        "packages": packages,
        "summary": summary,
        "limits": [
            (
                "This inventory records metadata declared by the exact installed "
                "Python distributions; it is not legal advice or a license-"
                "compatibility determination."
            ),
            (
                "Legacy License fields and Trove classifiers remain visibly marked "
                "for manual review instead of being presented as authoritative SPDX "
                "expressions."
            ),
            (
                "The scope excludes the Python interpreter, operating-system and "
                "base-image packages, system tools, externally hosted services and "
                "untracked build inputs."
            ),
        ],
    }


def _purl(name: str, version: str) -> str:
    encoded_name = quote(name, safe=".-_~")
    encoded_version = quote(version, safe=".-_~")
    return f"pkg:pypi/{encoded_name}@{encoded_version}"


def build_cyclonedx_sbom(
    inventory: dict[str, Any],
    *,
    project_name: str,
    project_version: str,
    source_revision: str,
) -> dict[str, Any]:
    """Build a deterministic CycloneDX dependency-set SBOM."""

    scope = inventory.get("scope")
    lock = inventory.get("lock")
    packages = inventory.get("packages")
    if (
        not isinstance(scope, str)
        or not isinstance(lock, dict)
        or not isinstance(lock.get("path"), str)
        or not isinstance(lock.get("sha256"), str)
        or not isinstance(packages, list)
    ):
        raise QualityEvidenceError("license inventory cannot produce an SBOM")

    lock_digest = lock["sha256"]
    root_reference = f"urn:gnostoa:python-lock:{scope}:{lock_digest}"
    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"urn:gnostoa:{source_revision}:{scope}:{lock_digest}",
    )
    components: list[dict[str, Any]] = []
    for package in packages:
        if not isinstance(package, dict):
            raise QualityEvidenceError("license inventory contains a malformed package")
        name = package.get("name")
        normalized_name = package.get("normalized_name")
        version = package.get("version")
        license_record = package.get("license")
        if (
            not isinstance(name, str)
            or not isinstance(normalized_name, str)
            or not isinstance(version, str)
        ):
            raise QualityEvidenceError(
                "license inventory package identity is malformed"
            )
        if not isinstance(license_record, dict):
            raise QualityEvidenceError("license inventory package license is malformed")
        licenses: list[dict[str, Any]]
        expression = license_record.get("expression")
        declaration = license_record.get("declaration")
        if isinstance(expression, str):
            licenses = [{"expression": expression}]
        elif isinstance(declaration, str):
            licenses = [{"license": {"name": declaration}}]
        else:
            raise QualityEvidenceError("license inventory package has no declaration")
        package_purl = _purl(normalized_name, version)
        components.append(
            {
                "type": "library",
                "bom-ref": package_purl,
                "name": name,
                "version": version,
                "purl": package_purl,
                "licenses": licenses,
                "properties": [
                    {
                        "name": "gnostoa:license-metadata-source",
                        "value": str(license_record.get("source", "unknown")),
                    },
                    {
                        "name": "gnostoa:license-manual-review",
                        "value": str(
                            bool(license_record.get("manual_review", True))
                        ).lower(),
                    },
                ],
            }
        )

    return {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": root_reference,
                "name": project_name,
                "version": project_version,
                "properties": [
                    {
                        "name": "gnostoa:python-dependency-scope",
                        "value": scope,
                    },
                    {
                        "name": "gnostoa:source-revision",
                        "value": source_revision,
                    },
                    {
                        "name": "gnostoa:lock-path",
                        "value": lock["path"],
                    },
                    {
                        "name": "gnostoa:lock-sha256",
                        "value": lock_digest,
                    },
                ],
            }
        },
        "components": components,
    }


def validate_cyclonedx_document(document: dict[str, Any], label: str) -> None:
    """Strictly validate the generated CycloneDX 1.6 document."""

    try:
        from cyclonedx.schema import SchemaVersion
        from cyclonedx.validation.json import JsonStrictValidator
    except ImportError as exc:
        raise QualityEvidenceError(
            "required quality tool is not installed: cyclonedx-python-lib"
        ) from exc

    error = JsonStrictValidator(SchemaVersion.V1_6).validate_str(
        json.dumps(document, sort_keys=True)
    )
    if error is not None:
        raise QualityEvidenceError(f"{label} is not valid CycloneDX 1.6: {error}")


def _project_identity(root: Path) -> tuple[str, str]:
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
        name = project["name"]
        version = project["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise QualityEvidenceError(f"cannot read project identity: {exc}") from exc
    if not isinstance(name, str) or not isinstance(version, str):
        raise QualityEvidenceError("project name and version must be strings")
    return name, version


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
        "cyclonedx-python-lib",
        "detect-secrets",
        "license-expression",
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
    runtime_inventory_report = output / "runtime-license-inventory.json"
    development_inventory_report = output / "development-license-inventory.json"
    runtime_sbom_report = output / "runtime-sbom.cdx.json"
    development_sbom_report = output / "development-sbom.cdx.json"
    secret_report = output / "tracked-tree-secret-scan.json"
    summary_path = output / "quality-summary.json"

    source_state = _git_state(root)
    source_revision = source_state.get("revision")
    if not isinstance(source_revision, str):
        raise QualityEvidenceError("source revision is not a string")
    project_name, project_version = _project_identity(root)
    runtime_inventory = build_license_inventory(
        root / "requirements" / "runtime.lock",
        lock_identity="requirements/runtime.lock",
        scope="runtime",
    )
    development_inventory = build_license_inventory(
        root / "requirements" / "development.lock",
        lock_identity="requirements/development.lock",
        scope="development",
    )
    runtime_sbom = build_cyclonedx_sbom(
        runtime_inventory,
        project_name=project_name,
        project_version=project_version,
        source_revision=source_revision,
    )
    development_sbom = build_cyclonedx_sbom(
        development_inventory,
        project_name=project_name,
        project_version=project_version,
        source_revision=source_revision,
    )
    validate_cyclonedx_document(runtime_sbom, "runtime SBOM")
    validate_cyclonedx_document(development_sbom, "development SBOM")
    for report, document in (
        (runtime_inventory_report, runtime_inventory),
        (development_inventory_report, development_inventory),
        (runtime_sbom_report, runtime_sbom),
        (development_sbom_report, development_sbom),
    ):
        report.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
            runtime_inventory_report,
            development_inventory_report,
            runtime_sbom_report,
            development_sbom_report,
            secret_report,
        )
    }
    summary = {
        "schema_version": 2,
        "source": source_state,
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
            "license_inventory_and_sbom": {
                "boundary": "exact installed Python distributions named by each lock",
                "locks": [
                    "requirements/runtime.lock",
                    "requirements/development.lock",
                ],
                "sbom_format": "CycloneDX 1.6 JSON",
            },
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
            "runtime_license_inventory": runtime_inventory["summary"],
            "development_license_inventory": development_inventory["summary"],
            "sbom": {
                "format": "CycloneDX",
                "spec_version": "1.6",
                "runtime_components": len(runtime_sbom["components"]),
                "development_components": len(development_sbom["components"]),
            },
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
                "License inventories and SBOMs cover exact installed Python "
                "distributions named by the two locks. Package-declared metadata "
                "is not legal advice, compatibility approval or evidence about "
                "operating-system, base-image or external components."
            ),
            (
                "Legacy license fields and classifiers are retained as manual-review "
                "evidence; SBOM component presence does not prove artifact identity "
                "until lock artifact hashes and provenance are added."
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
        description=(
            "Collect bounded static-quality, coverage, dependency, license, SBOM "
            "and security evidence"
        ),
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
