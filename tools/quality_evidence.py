"""Collect bounded release-quality evidence for the current tracked tree."""

from __future__ import annotations

import argparse
import ast
import bisect
import dataclasses
import hashlib
import importlib
import io
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import tokenize
import tomllib
import uuid
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path
from typing import Any, BinaryIO, TextIO
from urllib.parse import quote, unquote, urlparse

from tools import bounded_process, test_suite
from tools.analyzer_readback import (
    MAX_FINDINGS,
    AnalyzerReadbackError,
    deduplicate_findings,
    normalize_finding,
)
from tools.analyzer_readback import coverage as readback_coverage
from tools.github_events import exact_sha
from tools.repository_scope import (
    RepositoryScopeError,
    candidate_paths,
    scope_error_detail,
)
from tools.requirements_lock import (
    LockedRequirement,
    LockFormatError,
    locked_requirements,
    normalized_distribution_name,
)
from tools.security_scan import SecurityScanError, scan_tracked_tree

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


def dependency_audit_summary(
    document: dict[str, Any],
    *,
    expected_requirements: list[LockedRequirement] | None = None,
) -> dict[str, Any]:
    """Summarize pip-audit output without weakening its exit-code gate."""

    dependencies = document.get("dependencies")
    if not isinstance(dependencies, list):
        raise QualityEvidenceError("pip-audit report has no dependencies list")

    vulnerability_ids: list[str] = []
    vulnerability_count = 0
    reported: dict[str, str] = {}
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise QualityEvidenceError("pip-audit dependency is malformed")
        name = dependency.get("name")
        version = dependency.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise QualityEvidenceError("pip-audit dependency lacks name or version")
        normalized_name = normalized_distribution_name(name)
        if normalized_name in reported:
            raise QualityEvidenceError(f"pip-audit report duplicates {normalized_name}")
        reported[normalized_name] = version
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

    summary: dict[str, Any] = {
        "dependencies": len(dependencies),
        "vulnerabilities": vulnerability_count,
        "vulnerability_ids": sorted(vulnerability_ids),
    }
    if expected_requirements is not None:
        expected = {
            requirement["normalized_name"]: requirement["version"]
            for requirement in expected_requirements
        }
        unexpected = sorted(set(reported) - set(expected))
        if unexpected:
            raise QualityEvidenceError(
                "pip-audit report contains unlocked dependencies: "
                + ", ".join(unexpected)
            )
        mismatched = sorted(
            name for name, version in reported.items() if version != expected[name]
        )
        if mismatched:
            raise QualityEvidenceError(
                "pip-audit report has version mismatches: " + ", ".join(mismatched)
            )
        summary.update(
            {
                "lock_entries": len(expected),
                "reported_dependencies": len(reported),
                "unreported_dependencies": sorted(set(expected) - set(reported)),
            }
        )
    return summary


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


_REPORT_ENVIRONMENT_FIELDS = (
    "implementation_name",
    "platform_machine",
    "platform_system",
    "python_version",
    "sys_platform",
)


def parse_pip_artifact_report(
    lock_path: Path,
    report_path: Path,
    *,
    lock_identity: str,
    scope: str,
) -> dict[str, Any]:
    """Bind pip's selected wheels to the committed lock hash allow-list."""

    try:
        document = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityEvidenceError(
            f"cannot read {scope} pip installation report: {exc}"
        ) from exc
    if not isinstance(document, dict) or document.get("version") != "1":
        raise QualityEvidenceError(
            f"{scope} pip installation report must use stable format version 1"
        )
    pip_version = document.get("pip_version")
    installs = document.get("install")
    environment = document.get("environment")
    if not isinstance(pip_version, str) or not isinstance(installs, list):
        raise QualityEvidenceError(f"{scope} pip installation report is malformed")
    if not isinstance(environment, dict):
        raise QualityEvidenceError(
            f"{scope} pip installation report has no environment"
        )

    sanitized_environment: dict[str, str] = {}
    for field in _REPORT_ENVIRONMENT_FIELDS:
        value = environment.get(field)
        if not isinstance(value, str) or not value:
            raise QualityEvidenceError(
                f"{scope} pip installation report lacks environment field {field}"
            )
        sanitized_environment[field] = value

    requirements = locked_requirements(lock_path)
    expected = {
        requirement["normalized_name"]: requirement for requirement in requirements
    }
    selected: dict[str, dict[str, str]] = {}
    for item in installs:
        if not isinstance(item, dict):
            raise QualityEvidenceError(
                f"{scope} pip installation report contains a malformed item"
            )
        package_metadata = item.get("metadata")
        if not isinstance(package_metadata, dict):
            raise QualityEvidenceError(
                f"{scope} pip installation report item has no metadata"
            )
        name = package_metadata.get("name")
        version = package_metadata.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise QualityEvidenceError(
                f"{scope} pip installation report item lacks package identity"
            )
        normalized_name = normalized_distribution_name(name)
        requirement = expected.get(normalized_name)
        if requirement is None:
            raise QualityEvidenceError(
                f"{scope} pip installation report contains unlocked {name}=={version}"
            )
        if normalized_name in selected:
            raise QualityEvidenceError(
                f"{scope} pip installation report duplicates {normalized_name}"
            )
        if version != requirement["version"]:
            raise QualityEvidenceError(
                f"{scope} pip installation report version mismatch for {name}: "
                f"expected {requirement['version']}, found {version}"
            )
        if item.get("is_direct") is not False:
            raise QualityEvidenceError(
                f"{scope} pip installation report uses an unbound direct artifact "
                f"for {name}"
            )
        if item.get("is_yanked") is not False:
            raise QualityEvidenceError(
                f"{scope} pip installation report selected a yanked artifact for {name}"
            )

        download_info = item.get("download_info")
        if not isinstance(download_info, dict):
            raise QualityEvidenceError(
                f"{scope} pip installation report lacks download info for {name}"
            )
        url = download_info.get("url")
        archive_info = download_info.get("archive_info")
        hashes = archive_info.get("hashes") if isinstance(archive_info, dict) else None
        digest = hashes.get("sha256") if isinstance(hashes, dict) else None
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise QualityEvidenceError(
                f"{scope} pip installation report lacks a SHA-256 for {name}"
            )
        if digest not in requirement["artifact_hashes"]:
            raise QualityEvidenceError(
                f"selected artifact for {name} is not admitted by the committed lock"
            )
        if not isinstance(url, str):
            raise QualityEvidenceError(
                f"{scope} pip installation report lacks an artifact URL for {name}"
            )
        parsed_url = urlparse(url)
        filename = unquote(parsed_url.path.rsplit("/", maxsplit=1)[-1])
        if (
            parsed_url.scheme != "https"
            or not isinstance(parsed_url.hostname, str)
            or not filename.endswith(".whl")
            or "/" in filename
            or "\\" in filename
        ):
            raise QualityEvidenceError(
                f"{scope} pip installation report has an invalid wheel source for {name}"
            )
        selected[normalized_name] = {
            "name": name,
            "normalized_name": normalized_name,
            "version": version,
            "filename": filename,
            "sha256": digest,
            "source_host": parsed_url.hostname.lower(),
        }

    missing = sorted(set(expected) - set(selected))
    if missing:
        raise QualityEvidenceError(
            f"{scope} pip installation report omits locked packages: "
            + ", ".join(missing)
        )
    packages = [selected[item["normalized_name"]] for item in requirements]
    lock_evidence = {
        "path": lock_identity,
        **file_evidence(lock_path),
    }
    digest_payload = {
        "environment": sanitized_environment,
        "installer": {"name": "pip", "version": pip_version, "report_version": "1"},
        "lock": lock_evidence,
        "packages": packages,
        "scope": scope,
    }
    selection_digest = hashlib.sha256(
        json.dumps(
            digest_payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        **digest_payload,
        "selection_sha256": selection_digest,
        "summary": {
            "packages": len(packages),
            "selected_hashes_admitted": len(packages),
            "yanked_artifacts": 0,
        },
        "limits": [
            (
                "This records the exact wheel selected for one declared Python and "
                "platform environment; another admitted environment can select a "
                "different wheel from the same committed lock."
            ),
            (
                "A lock hash prevents unlisted artifact bytes from being installed "
                "for this scope, but does not authenticate the publisher, establish "
                "legal compatibility or provide release provenance."
            ),
            (
                "The pip installation-report format is a supported pip interface, "
                "not a PyPA interoperability standard or an input lock format."
            ),
        ],
    }


def build_license_inventory(
    lock_path: Path,
    *,
    lock_identity: str,
    scope: str,
    artifact_selection: dict[str, Any],
) -> dict[str, Any]:
    """Bind exact lock entries to selected artifacts and installed metadata."""

    lock_evidence = {"path": lock_identity, **file_evidence(lock_path)}
    if artifact_selection.get("scope") != scope:
        raise QualityEvidenceError(f"{scope} artifact selection scope mismatch")
    if artifact_selection.get("lock") != lock_evidence:
        raise QualityEvidenceError(f"{scope} artifact selection lock mismatch")
    selection_digest = artifact_selection.get("selection_sha256")
    selected_packages = artifact_selection.get("packages")
    if (
        not isinstance(selection_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", selection_digest) is None
        or not isinstance(selected_packages, list)
    ):
        raise QualityEvidenceError(f"{scope} artifact selection is malformed")
    selected_by_name = {
        package.get("normalized_name"): package
        for package in selected_packages
        if isinstance(package, dict) and isinstance(package.get("normalized_name"), str)
    }
    if len(selected_by_name) != len(selected_packages):
        raise QualityEvidenceError(f"{scope} artifact selection identities are invalid")
    packages: list[dict[str, Any]] = []
    for requirement in locked_requirements(lock_path):
        selected_artifact = selected_by_name.get(requirement["normalized_name"])
        if not isinstance(selected_artifact, dict):
            raise QualityEvidenceError(
                f"{scope} artifact selection omits {requirement['normalized_name']}"
            )
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
            normalized_distribution_name(distribution_name)
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
                "artifact": {
                    "filename": selected_artifact["filename"],
                    "sha256": selected_artifact["sha256"],
                    "source_host": selected_artifact["source_host"],
                },
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
        "artifact_identities": len(packages),
    }
    return {
        "schema_version": 2,
        "scope": scope,
        "lock": lock_evidence,
        "artifact_selection": {
            "sha256": selection_digest,
            "environment": artifact_selection.get("environment"),
            "installer": artifact_selection.get("installer"),
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
            (
                "The selected wheel SHA-256 is verified against the committed lock "
                "allow-list; it is artifact identity evidence, not publisher trust, "
                "legal compatibility or release provenance."
            ),
            (
                "Installed metadata confirms distribution identity and version but "
                "does not independently reconstruct or re-hash installed files into "
                "the selected wheel archive."
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
    artifact_selection = inventory.get("artifact_selection")
    packages = inventory.get("packages")
    if (
        not isinstance(scope, str)
        or not isinstance(lock, dict)
        or not isinstance(lock.get("path"), str)
        or not isinstance(lock.get("sha256"), str)
        or not isinstance(artifact_selection, dict)
        or not isinstance(artifact_selection.get("sha256"), str)
        or not isinstance(packages, list)
    ):
        raise QualityEvidenceError("license inventory cannot produce an SBOM")

    lock_digest = lock["sha256"]
    selection_digest = artifact_selection["sha256"]
    root_reference = f"urn:gnostoa:python-lock:{scope}:{lock_digest}:{selection_digest}"
    serial = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"urn:gnostoa:{source_revision}:{scope}:{lock_digest}:{selection_digest}",
    )
    components: list[dict[str, Any]] = []
    for package in packages:
        if not isinstance(package, dict):
            raise QualityEvidenceError("license inventory contains a malformed package")
        name = package.get("name")
        normalized_name = package.get("normalized_name")
        version = package.get("version")
        license_record = package.get("license")
        artifact = package.get("artifact")
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
        if not isinstance(artifact, dict):
            raise QualityEvidenceError(
                "license inventory package artifact identity is malformed"
            )
        artifact_filename = artifact.get("filename")
        artifact_digest = artifact.get("sha256")
        artifact_source_host = artifact.get("source_host")
        if (
            not isinstance(artifact_filename, str)
            or not isinstance(artifact_digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", artifact_digest) is None
            or not isinstance(artifact_source_host, str)
        ):
            raise QualityEvidenceError(
                "license inventory package artifact identity is malformed"
            )
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
                "hashes": [{"alg": "SHA-256", "content": artifact_digest}],
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
                    {
                        "name": "gnostoa:artifact-filename",
                        "value": artifact_filename,
                    },
                    {
                        "name": "gnostoa:artifact-source-host",
                        "value": artifact_source_host,
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
                    {
                        "name": "gnostoa:artifact-selection-sha256",
                        "value": selection_digest,
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


def _time_left(end: float | None) -> float | None:
    """The time left before `end` on the monotonic clock, at least a millisecond, or
    None without an end."""
    return None if end is None else max(end - time.monotonic(), 0.001)


def _git_state(root: Path, *, timeout: float | None = None) -> dict[str, Any]:
    revision = os.environ.get("KNOWLEDGE_KIT_REVISION", "unbound")
    dirty: bool | None = None
    # Both reads share the one budget (cubic and CodeAnt on #436).
    end = None if timeout is None else time.monotonic() + timeout
    try:
        revision_result = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=_time_left(end),
        )
        revision = revision_result.stdout.strip()
        if end is not None and time.monotonic() >= end:
            # A spent budget starts no status read (Codex on #436).
            return {"revision": revision, "tracked_tree_dirty": None}
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
            timeout=_time_left(end),
        )
        dirty = bool(status_result.stdout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
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

    try:
        tracked_paths = candidate_paths(root)
    except RepositoryScopeError as exc:
        raise QualityEvidenceError(
            scope_error_detail("cannot enumerate tracked-tree candidates", exc)
        ) from exc
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
    runtime_selection_report = output / "runtime-artifact-selection.json"
    development_selection_report = output / "development-artifact-selection.json"
    runtime_pip_report = output / ".runtime-pip-install-report.json"
    development_pip_report = output / ".development-pip-install-report.json"
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

    environment = os.environ.copy()
    environment["COVERAGE_FILE"] = str(coverage_data)
    environment["MYPY_CACHE_DIR"] = str(output / ".mypy_cache")
    environment["RUFF_CACHE_DIR"] = str(output / ".ruff_cache")
    python = sys.executable
    statuses: dict[str, int] = {}
    selections: dict[str, dict[str, Any]] = {}
    for scope, lock_path, raw_report in (
        (
            "runtime",
            root / "requirements" / "runtime.lock",
            runtime_pip_report,
        ),
        (
            "development",
            root / "requirements" / "development.lock",
            development_pip_report,
        ),
    ):
        status_name = f"{scope}_artifact_selection"
        statuses[status_name] = _run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--dry-run",
                "--ignore-installed",
                "--no-cache-dir",
                "--only-binary=:all:",
                "--require-hashes",
                "--report",
                str(raw_report),
                "--requirement",
                str(lock_path),
            ],
            root=root,
            environment=environment,
        )
        if statuses[status_name] != 0:
            raw_report.unlink(missing_ok=True)
            raise QualityEvidenceError(f"{scope} artifact selection command failed")
        try:
            selection = parse_pip_artifact_report(
                lock_path,
                raw_report,
                lock_identity=f"requirements/{lock_path.name}",
                scope=scope,
            )
        finally:
            raw_report.unlink(missing_ok=True)
        selections[scope] = selection

    runtime_inventory = build_license_inventory(
        root / "requirements" / "runtime.lock",
        lock_identity="requirements/runtime.lock",
        scope="runtime",
        artifact_selection=selections["runtime"],
    )
    development_inventory = build_license_inventory(
        root / "requirements" / "development.lock",
        lock_identity="requirements/development.lock",
        scope="development",
        artifact_selection=selections["development"],
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
        (runtime_selection_report, selections["runtime"]),
        (development_selection_report, selections["development"]),
        (runtime_inventory_report, runtime_inventory),
        (development_inventory_report, development_inventory),
        (runtime_sbom_report, runtime_sbom),
        (development_sbom_report, development_sbom),
    ):
        report.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

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
                ".",
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
                ".",
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
    # The same branch coverage of `tools`, measured in the suite's parallel
    # processes and combined (Decision 0109).
    # Through the owner, so the coverage run has the suite's bound too (CodeAnt on
    # #392).
    print(
        "+ " + " ".join(test_suite.command(python, coverage_source="tools")), flush=True
    )
    statuses["coverage_run"] = test_suite.run(
        root, coverage_source="tools", environment=environment
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

    try:
        secret_result = scan_tracked_tree(
            root,
            report_path=secret_report,
        )
    except SecurityScanError as exc:
        raise QualityEvidenceError(str(exc)) from exc
    statuses["secret_scan"] = 0

    coverage_document = _read_json(coverage_report, "coverage report")
    runtime_document = _read_json(runtime_audit, "runtime dependency audit")
    development_document = _read_json(
        development_audit,
        "development dependency audit",
    )

    totals = coverage_document.get("totals")
    if not isinstance(totals, dict) or not isinstance(
        totals.get("percent_covered"),
        (int, float),
    ):
        raise QualityEvidenceError("coverage report has no total percentage")
    coverage_percent = float(totals["percent_covered"])
    secret_candidates = secret_result.unresolved_findings
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
            runtime_selection_report,
            development_selection_report,
            runtime_inventory_report,
            development_inventory_report,
            runtime_sbom_report,
            development_sbom_report,
            secret_report,
        )
    }
    summary = {
        "schema_version": 3,
        "source": source_state,
        "tools": _tool_versions(),
        "scope": {
            "static_quality": {
                "format_and_lint": ".",
                "strict_typing": ["tools", "ci"],
            },
            "coverage": "branch-aware unittest coverage of the tools package",
            "dependency_audit": [
                "requirements/runtime.lock",
                "requirements/development.lock",
            ],
            "artifact_identity": {
                "boundary": (
                    "exact non-yanked wheel selected for the current Python and "
                    "platform environment from each committed SHA-256 allow-list"
                ),
                "locks": [
                    "requirements/runtime.lock",
                    "requirements/development.lock",
                ],
                "installer_report": "pip installation report version 1",
            },
            "license_inventory_and_sbom": {
                "boundary": (
                    "exact installed Python distributions and selected wheel "
                    "identities named by each lock"
                ),
                "locks": [
                    "requirements/runtime.lock",
                    "requirements/development.lock",
                ],
                "sbom_format": "CycloneDX 1.6 JSON",
            },
            "secret_scan": {
                "boundary": "current Git-tracked regular-file working tree only",
                "tracked_files": secret_result.scanned_files,
                "baseline": ".secrets.baseline",
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
            "runtime_dependency_audit": dependency_audit_summary(
                runtime_document,
                expected_requirements=locked_requirements(
                    root / "requirements" / "runtime.lock"
                ),
            ),
            "development_dependency_audit": dependency_audit_summary(
                development_document,
                expected_requirements=locked_requirements(
                    root / "requirements" / "development.lock"
                ),
            ),
            "artifact_identity": {
                "runtime": selections["runtime"]["summary"],
                "development": selections["development"]["summary"],
            },
            "runtime_license_inventory": runtime_inventory["summary"],
            "development_license_inventory": development_inventory["summary"],
            "sbom": {
                "format": "CycloneDX",
                "spec_version": "1.6",
                "runtime_components": len(runtime_sbom["components"]),
                "development_components": len(development_sbom["components"]),
                "component_hashes": "selected wheel SHA-256",
            },
            "secret_scan": {
                "candidates": len(secret_candidates),
                "reviewed_false_positives": (secret_result.reviewed_false_positives),
                "findings": secret_candidates,
            },
        },
        "command_statuses": statuses,
        "reports": reports,
        "limits": [
            (
                "Formatting and lint cover the Git-candidate-aware repository-root "
                "Ruff subject with explicit configuration exclusions; static typing "
                "remains limited to its declared paths. A clean result is not "
                "behavior, security or semantic acceptance evidence."
            ),
            "Coverage is a regression signal, not acceptance or test-quality proof.",
            (
                "The dependency audits cover known Python-package advisories "
                "available from the configured provider at run time; they do not "
                "prove package trustworthiness or cover non-Python components."
            ),
            (
                "The summary validates every pip-audit row against the exact lock "
                "and lists lock entries omitted from the provider's no-finding JSON; "
                "an omitted row is not silently counted as package-level evidence."
            ),
            (
                "License inventories and SBOMs cover exact installed Python "
                "distributions and the selected wheel identities admitted by the "
                "two locks. Package-declared metadata is not legal advice, "
                "compatibility approval or evidence about operating-system, "
                "base-image or external components."
            ),
            (
                "Legacy license fields and classifiers are retained as manual-review "
                "evidence. Committed hashes and selected-wheel read-back establish "
                "bounded artifact identity, not publisher trust, availability, "
                "legal compatibility or release provenance."
            ),
            (
                "The selected wheel is a fresh resolver read-back for the declared "
                "environment; installed metadata does not independently prove the "
                "archive origin of every installed file."
            ),
            (
                "The heuristic secret scan covers the current tracked tree, not "
                "Git history, provider metadata, Actions artifacts or logs. Its "
                "reviewed baseline is an exact false-positive disposition, not a "
                "general secret-pattern or path exclusion."
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


# The explicit, offline diagnostic inventory (#389 F3-S1, the Router's 6201584332). It is
# experimental qualification material: collect_quality_evidence and the CLI never run it,
# it is no assurance receipt, and it filters nothing. Every diagnostic its producers emit is
# listed with its producer, code, mapping status, path and range. Coverage is never
# COMPLETE in this slice: the source binding is UNVERIFIED (the Router's I3 and U1 on
# #436), so the COMPLETE and PARTIAL statuses stay unreachable until it is proven.

DIAGNOSTIC_SCHEMA = "gnostoa-diagnostic-inventory/v1"
DIAGNOSTIC_INVENTORY = "diagnostic-inventory.json"
# Provisional mappings, calibrated on #389's thirteen reference heads (6201413011) and not
# qualified: a mapped code is evidence about a DeepSource rule, never a substitute for it.
DIAGNOSTIC_RULE_MAP: dict[tuple[str, str], str] = {
    ("mypy", "arg-type"): "TYP-050",
    ("ruff", "SLF001"): "PYL-W0212",
    ("ruff", "PLR6301"): "PYL-R0201",
    ("ruff", "SIM117"): "PTC-W0062",
    ("ruff", "S106"): "SCT-A000",
    ("complexity", "cc"): "PY-R1000",
}
DIAGNOSTIC_RUFF_SELECT = ("SLF001", "PLR6301", "SIM117", "S106")
COMPLEXITY_METRIC = "cyclomatic-n-1/v1"
COMPLEXITY_REPORTED_ABOVE = 15
_DIAGNOSTIC_FIXTURE_ROOT = "tests/fixtures/"
_UNRESOLVED_IMPORTS = frozenset({"import-not-found", "import-untyped"})
_QUOTED = re.compile(r'"([^"]+)"')
_DECISIONS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)


@dataclasses.dataclass(frozen=True)
class DiagnosticLimits:
    """The finite bounds of one inventory: one deadline for every producer and Git
    call, and caps on the tracked files, the findings, each producer's output and
    each source that the complexity metric parses in this process."""

    max_files: int = 5_000
    max_findings: int = MAX_FINDINGS
    max_report_bytes: int = 64 * 1024 * 1024
    timeout_seconds: float = 900.0
    max_source_bytes: int = 8 * 1024 * 1024


DEFAULT_DIAGNOSTIC_LIMITS = DiagnosticLimits()


@dataclasses.dataclass
class _ProducerResult:
    runs: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    truncated: bool = False
    findings: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    unanalyzed: dict[str, str] = dataclasses.field(default_factory=dict)
    partial: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    # Valid findings counted past the allowance, never kept (the Router's M1 on #436).
    excess: int = 0

    def count(self) -> int:
        """The raw count of valid findings, those kept and those only counted."""
        return len(self.findings) + self.excess

    def keep(self, finding: dict[str, Any], max_findings: int) -> None:
        """Keep a validated finding while the raw count is within `max_findings`,
        the first one past it included as the witness; past it, count it only, so
        that the refusal names the real count (the Router's M1, R1 and S-a on
        #436)."""
        if self.count() <= max_findings:
            self.findings.append(finding)
        else:
            self.excess += 1

    def merge(self, other: _ProducerResult) -> None:
        self.runs += other.runs
        self.truncated = self.truncated or other.truncated
        self.findings += other.findings
        self.excess += other.excess
        for path, reason in other.unanalyzed.items():
            # Every producer's failure of a file is named (Codex on #436).
            known = self.unanalyzed.get(path)
            self.unanalyzed[path] = reason if known is None else f"{known}; {reason}"
        for path, modules in other.partial.items():
            self.partial.setdefault(path, []).extend(modules)


def cyclomatic_complexity(function: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """1, plus each decision (if, loop, conditional expression, except handler), each
    boolean operand after the first, and each comprehension with its conditions, over
    the whole function node, its decorators, annotations and defaults included (CodeAnt
    on #436): a nested function's decisions count in its parent too. This is the
    calibrated definition of #389 6201028334 section 4, an unqualified hypothesis. A
    `match` statement's cases are not counted: no calibration subject holds one, so
    how DeepSource counts them is unmeasured (CodeAnt on #436)."""
    total = 1
    for node in ast.walk(function):
        if isinstance(node, _DECISIONS):
            total += 1
        elif isinstance(node, ast.BoolOp):
            total += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            total += 1 + len(node.ifs)
    return total


def _location_range(
    location: tuple[int, int, int | None, int | None],
) -> dict[str, int] | None:
    start_line, start_column, end_line, end_column = location
    # Exact integers, as the producer emitted them, checked before any clamping: a
    # fraction or a boolean is the record's fault, never a position (cubic and Claude
    # on #436). The range owner refuses them too, but only after the clamps below.
    if not all(type(value) is int for value in (start_line, start_column)) or not all(
        value is None or type(value) is int for value in (end_line, end_column)
    ):
        raise ValueError("a position is not an exact integer")
    if start_line < 1:
        return None
    result = {"start_line": start_line, "start_column": max(start_column, 1)}
    if end_line is not None and end_column is not None:
        end = (end_line, max(end_column, 1))
        if end >= (start_line, result["start_column"]):
            result["end_line"], result["end_column"] = end
    return result


def _diagnostic_finding(
    tool: str,
    code: str | None,
    path: str,
    location: tuple[int, int, int | None, int | None],
    message: str,
    native: dict[str, Any],
) -> dict[str, Any]:
    deepsource_rule = None if code is None else DIAGNOSTIC_RULE_MAP.get((tool, code))
    location_range = _location_range(location)
    identity = json.dumps([tool, code, path, location_range, message], sort_keys=True)
    finding = {
        "id": f"{tool}:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}",
        "message": message,
        "rule": code,
        "path": path,
        "tool": {"id": tool},
        "range": location_range,
        "native": {
            **native,
            "producer_code": code,
            "deepsource_rule": deepsource_rule,
            "mapping": "UNMAPPED" if deepsource_rule is None else "PROVISIONAL",
        },
        "provenance": [{"surface": "diagnostic-inventory", "reference": tool}],
    }
    # Validated by the consumed owner record by record (Router on #436), which refuses
    # a code or message that is not text, and keeps a null code null (Claude on
    # #436): a record it refuses is its report's gap, never the collection's abort.
    normalize_finding(finding)
    return finding


def _new_file(path: Path) -> BinaryIO:
    """A new regular file at `path`: never an existing file, and never a symlink."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    return os.fdopen(os.open(path, flags, 0o644), "wb")


_OUTPUT_CAP_GAP = "budget: the output exceeds max_report_bytes"


_REAP_SECONDS = 5.0


def _reap(process: subprocess.Popen[bytes]) -> str | None:
    """The shared owner's bounded reap (#365): None once the child is reaped, or its
    failure by type alone (the Router's X1 on #436)."""
    failure = bounded_process.reap(process, timeout=_REAP_SECONDS)
    if failure is None:
        return None
    if isinstance(failure, subprocess.TimeoutExpired):
        return f"its process could not be reaped within {_REAP_SECONDS:g} seconds"
    return f"its process could not be reaped: {type(failure).__name__}"


def _with(gap: str | None, detail: str | None) -> str | None:
    """The primary gap first, then a cleanup's detail."""
    if detail is None:
        return gap
    return detail if gap is None else f"{gap}; {detail}"


def _and(reason: str, detail: str | None) -> str:
    """A reason, then a cleanup's detail."""
    return reason if detail is None else f"{reason}; {detail}"


def _bounded_run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    report: Path,
    deadline: float,
    limits: DiagnosticLimits,
) -> tuple[int | None, str | None, bool]:
    """Run one producer with its stdout drained into a new `report` by the shared
    owner (#365), under the inventory's deadline and max_report_bytes: its exit
    status, a gap if any, and whether its capture is invalid. An invalid capture, cut
    at the cap or failed part way, keeps a prefix whose rest is unknown, so the
    collector writes no inventory (the Router's V1 and G2 on #436). A spent budget
    starts nothing (Codex on #436)."""
    if time.monotonic() >= deadline:
        return None, "not started: the inventory deadline had passed", False
    print("+ " + " ".join(command[:8]), flush=True)
    try:
        stream = _new_file(report)
    except OSError as exc:
        return None, f"cannot create its report: {type(exc).__name__}", False
    status: int | None
    gap: str | None
    try:
        try:
            process = subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- argv list, no shell: the producer and its options are fixed, and the files follow "--"
                command,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            status, gap, invalid = None, f"could not run: {type(exc).__name__}", False
        else:
            status, gap, invalid = _drain_report(process, stream, deadline, limits)
    except BaseException:
        _close_report(stream)
        raise
    if gap is None and status not in (0, 1):
        gap = f"exited {status}"
    closed = _close_report(stream)
    if closed is not None:
        # The report's tail may be lost, so its capture is invalid, after the primary
        # reason (Codex, the Router's C-a on #436).
        gap, invalid = _with(gap, closed), True
    return status, gap, invalid


def _close_report(stream: BinaryIO) -> str | None:
    """Close a report: None, or its failure by the exception's type, never raised."""
    try:
        stream.close()
    except OSError as exc:
        return f"its report could not be closed: {type(exc).__name__}"
    return None


def _drain_report(
    process: subprocess.Popen[bytes],
    stream: BinaryIO,
    deadline: float,
    limits: DiagnosticLimits,
) -> tuple[int | None, str | None, bool]:
    """The producer's stdout drained into `stream`, and the child reaped: each of the
    shared owner's outcomes mapped to the consumer's status, gap and validity."""
    if process.stdout is None:
        gap = _with("the producer's stdout pipe is unavailable", _reap(process))
        return process.returncode, gap, True

    def sink(_name: str, chunk: bytes) -> None:
        stream.write(chunk)

    try:
        drained = bounded_process.drain(
            process,
            {"stdout": process.stdout},
            sink,
            deadline=deadline,
            cap=limits.max_report_bytes,
        )
    finally:
        # Not `with process`: Popen's own exit waits without a bound.
        try:
            process.stdout.close()
        except OSError:
            pass
    cleanup = (
        None if drained.selector_closed else "its output selector could not be closed"
    )
    if drained.outcome == "exited" and drained.returncode is not None:
        return drained.returncode, cleanup, False
    if drained.outcome == "deadline":
        gap, invalid = "timed out at the inventory deadline", False
    elif drained.outcome == "cap":
        gap, invalid = _OUTPUT_CAP_GAP, True
    elif drained.outcome == "error" and drained.error is not None:
        gap = f"the producer could not be followed: {type(drained.error).__name__}"
        invalid = True
    elif drained.outcome == "unexpected" and drained.exception is not None:
        gap = f"the producer could not be followed: {type(drained.exception).__name__}"
        invalid = True
    else:
        gap = f"the producer could not be followed: unexpected drain outcome {drained.outcome}"
        invalid = True
    gap = _with(_with(gap, cleanup), _reap(process))
    return process.returncode, gap, invalid


def _run_record(
    name: str,
    producer: str,
    command: list[str],
    status: int | None,
    report: Path,
    run: Path,
    version: str | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "invocation": name,
        "producer": producer,
        "version": version,
        "argv": command,
        "exit_status": status,
    }
    if report.is_file() and not report.is_symlink():
        record["report"] = {
            "path": report.relative_to(run).as_posix(),
            **file_evidence(report),
        }
    return record


def _producer_version(
    root: Path, run: Path, producer: str, limits: DiagnosticLimits, deadline: float
) -> str | None:
    """The producer's own `--version`, run as it runs: isolated with -I, and under the
    deadline. The collector's metadata search can include the
    analyzed root, so a tracked dist-info could name another version (Codex on
    #436). None when it cannot be read."""
    report = run / f"diagnostic-{producer}-version.txt"
    status, gap, _invalid = _bounded_run(
        [sys.executable, "-I", "-m", producer, "--version"],
        cwd=root,
        environment=dict(os.environ),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    if gap is not None or status != 0:
        return None
    try:
        words = report.read_text(encoding="utf-8").split()
    except (OSError, ValueError):
        return None
    return words[1] if len(words) > 1 and words[0] == producer else None


def _mypy_groups(paths: list[str]) -> dict[str, list[str]]:
    """The non-fixture set analyzed from the root, and each tests/fixtures/<name>
    directory from its own root: the c0 configuration of #389 6201413011 section 3."""
    groups: dict[str, list[str]] = {}
    for path in paths:
        parts = path.split("/")
        fixture = path.startswith(_DIAGNOSTIC_FIXTURE_ROOT) and len(parts) > 3
        groups.setdefault("/".join(parts[:3]) if fixture else "", []).append(path)
    return groups


def _mypy_command(
    root: Path, key: str, files: list[str]
) -> tuple[str, Path, str, list[str], dict[str, str]]:
    """One group's invocation: its name, root, path prefix, argv and environment."""
    name = f"mypy:{key or 'main'}"
    cwd = root / key if key else root
    prefix = f"{key}/" if key else ""
    flags = [] if key else ["--explicit-package-bases"]
    command = [
        sys.executable,
        # -I, the interpreter's own isolation, as security_scan's child runs: -P left
        # the user site on, so a usercustomize ran in every producer (Codex on #436).
        "-I",
        "-m",
        "mypy",
        "--config-file=",
        "--python-version",
        "3.11",
        "--output",
        "json",
        *flags,
        "--",
        *(path[len(prefix) :] for path in files),
    ]
    environment = {
        **os.environ,
        "MYPYPATH": str(cwd),
        # No cache: a fresh run never reuses one, and the run directory keeps only
        # evidence (CodeAnt on #436). /dev/null is mypy's own way to disable it.
        "MYPY_CACHE_DIR": os.devnull,
    }
    return name, cwd, prefix, command, environment


def _mypy_finding(record: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    # Nothing is coerced: _location_range and _diagnostic_finding refuse what is not
    # an exact integer or a text, and only an integer column moves to 1-based.
    path = record["file"]
    # A file that is absolute or has a .. segment cannot be bound to the group's root:
    # it is the report's malformed record, before any prefix could hide it (Codex,
    # routed by the Router 6224373564 on #436, M2).
    if type(path) is str and (path.startswith("/") or ".." in path.split("/")):
        raise ValueError(f"mypy file {path!r} is not relative to its group's root")
    # A severity is a text or null: json.loads takes NaN and Infinity, which the
    # inventory would write back as bare tokens (Codex, the Router's S1 on #436).
    severity = record.get("severity")
    if severity is not None and type(severity) is not str:
        raise ValueError("the mypy severity is not a text or null")
    column, end_column = record["column"], record.get("end_column")
    location = (
        record["line"],
        column + 1 if type(column) is int else column,
        record.get("end_line"),
        end_column + 1 if type(end_column) is int else end_column,
    )
    return _diagnostic_finding(
        "mypy",
        record.get("code"),
        prefix + path,
        location,
        record["message"],
        {"severity": severity},
    )


def _mypy_records(
    report: Path, prefix: str, result: _ProducerResult, max_findings: int
) -> tuple[list[str], int, str | None]:
    """Every mypy record as a finding, a code-less one included. Returns the
    aborting messages, the error count and a parse failure: any nonblank line
    that is not a record is one (Codex, cubic and Sourcery on #436). Past
    max_findings, a valid record is still validated and counted, never kept, so the
    refusal that follows names the real count (CodeAnt, the Router's M1 on #436)."""
    aborts: list[str] = []
    errors = 0
    try:
        lines = report.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError) as exc:
        # The exception's type, never its text, which can carry a host path (Octopus,
        # the Router's X1 on #436): so for every written gap below.
        return aborts, errors, f"unreadable mypy report: {type(exc).__name__}"
    parse_gap: str | None = None
    for line in filter(str.strip, lines):
        try:
            record = json.loads(line)
            finding = _mypy_finding(record, prefix)
        except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
            # The first malformed line is the gap; the records after it are still
            # read, never dropped (Codex on #436). json.loads accepts Infinity, which is
            # no exact integer, so the position check refuses it (cubic on #436).
            if parse_gap is None:
                parse_gap = f"unparsable mypy report: {type(exc).__name__}"
            continue
        result.keep(finding, max_findings)
        is_error = record.get("severity") == "error"
        errors += is_error
        if is_error and record.get("code") is None:
            aborts.append(finding["message"])
        unresolved = _QUOTED.search(finding["message"])
        if record.get("code") in _UNRESOLVED_IMPORTS and unresolved:
            result.partial.setdefault(finding["path"], []).append(unresolved.group(1))
    return aborts, errors, parse_gap


def _mypy_gap(
    report: Path,
    prefix: str,
    status: int | None,
    gap: str | None,
    result: _ProducerResult,
    max_findings: int,
) -> str | None:
    """Read one group's report into `result`; its gap, if it is not analyzed whole.
    An exit 2 is still read, so that its aborting messages name the gap."""
    aborts, errors, parse_gap = _mypy_records(report, prefix, result, max_findings)
    if gap is not None and not (status == 2 and gap == "exited 2"):
        return gap
    if parse_gap is not None:
        return parse_gap
    if aborts or status == 2:
        return "aborted: " + "; ".join(aborts or ["exited 2"])
    if status == 1 and errors == 0:
        return "exited 1 without an error record"
    if status == 0 and errors > 0:
        # The inverse: mypy exits 0 only with no error, though notes may remain
        # (Codex, the Router's Z1 on #436).
        return "exited 0 with an error record"
    return None


def _run_mypy(
    root: Path,
    run: Path,
    paths: list[str],
    limits: DiagnosticLimits,
    deadline: float,
    version: str | None,
) -> _ProducerResult:
    result = _ProducerResult()
    for index, (key, files) in enumerate(sorted(_mypy_groups(paths).items())):
        if result.count() > limits.max_findings:
            # mypy runs first, so these are every finding so far: past the existing
            # refusal's predicate, no later group starts (cubic on #436).
            break
        name, cwd, prefix, command, environment = _mypy_command(root, key, files)
        # The index keeps names apart that the replacement would merge, as
        # tests/fixtures/a-b and tests/fixtures/a:b (Codex on #436).
        slug = name.replace(":", "-").replace("/", "-")
        report = run / f"diagnostic-{index:03d}-{slug}.jsonl"
        status, gap, invalid = _bounded_run(
            command,
            cwd=cwd,
            environment=environment,
            report=report,
            deadline=deadline,
            limits=limits,
        )
        result.runs.append(
            _run_record(name, "mypy", command, status, report, run, version)
        )
        result.truncated = result.truncated or invalid
        gap = _mypy_gap(report, prefix, status, gap, result, limits.max_findings)
        if gap is not None:
            result.unanalyzed.update({path: f"{name} {gap}" for path in files})
    return result


def _ruff_finding(record: Mapping[str, Any], root: Path) -> dict[str, Any]:
    name = Path(record["filename"])
    path = (name if name.is_absolute() else root / name).resolve().relative_to(root)
    start, end = record["location"], record.get("end_location") or {}
    # Nothing is coerced, as for mypy: _location_range and _diagnostic_finding refuse
    # what is not an exact integer or a text (cubic and Claude on #436).
    location = (start["row"], start["column"], end.get("row"), end.get("column"))
    return _diagnostic_finding(
        "ruff",
        record["code"],
        path.as_posix(),
        location,
        record["message"],
        {},
    )


def _ruff_gap(status: int | None, gap: str | None, records: list[Any]) -> str | None:
    """A ruff run's gap, if it is not analyzed whole: an earlier one, or a status its
    report contradicts. Ruff exits 1 only when it reports a diagnostic, and, without
    --exit-zero or a fix, 0 only when it reports none, as mypy's _mypy_gap reads its
    own (Codex, the Router's Z1 and K2 on #436)."""
    if gap is not None:
        return gap
    if status == 1 and not records:
        return "exited 1 without a finding record"
    if status == 0 and records:
        return "exited 0 with a finding record"
    return None


def _run_ruff(
    root: Path,
    run: Path,
    paths: list[str],
    limits: DiagnosticLimits,
    deadline: float,
    version: str | None,
    max_findings: int | None = None,
) -> _ProducerResult:
    allowance = limits.max_findings if max_findings is None else max_findings
    result = _ProducerResult()
    command = [
        sys.executable,
        # -I, the interpreter's own isolation, as security_scan's child runs: -P left
        # the user site on, so a usercustomize ran in every producer (Codex on #436).
        "-I",
        "-m",
        "ruff",
        "check",
        "--isolated",
        "--ignore-noqa",  # a flag, not a marker -- ruff then reports what its suppression comments would hide (Codex on #436)
        "--no-cache",
        "--preview",
        "--target-version",
        "py311",
        "--select",
        ",".join(DIAGNOSTIC_RUFF_SELECT),
        "--output-format",
        "json",
        "--",
        *paths,
    ]
    report = run / "diagnostic-ruff.json"
    status, gap, invalid = _bounded_run(
        command,
        cwd=root,
        environment=dict(os.environ),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    result.runs.append(
        _run_record("ruff", "ruff", command, status, report, run, version)
    )
    result.truncated = result.truncated or invalid
    # A complete report is read even after a gap, so that nothing ruff emitted is
    # dropped (Codex on #436); a truncated or missing one keeps its gap.
    try:
        records = json.loads(report.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("the report is not a list of records")
    except (OSError, ValueError, RecursionError) as exc:
        # A report nested past the decoder's recursion is unparsable too (Codex, the
        # Router's J-a on #436).
        records = []
        if gap is None:
            gap = f"unparsable report: {type(exc).__name__}"
    # One malformed record is the gap, and the records after it are still read
    # (Codex on #436), as mypy's are.
    for record in records:
        try:
            finding = _ruff_finding(record, root)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            if gap is None:
                gap = f"unparsable report: {type(exc).__name__}"
            continue
        result.keep(finding, allowance)
    gap = _ruff_gap(status, gap, records)
    if gap is not None:
        result.unanalyzed.update({path: f"ruff {gap}" for path in paths})
    return result


def _source_lines(source: bytes) -> list[str]:
    """The source's lines as the tokenizer counts them: decoded by its declared
    encoding, split at CRLF, CR and LF only."""
    encoding, _ = tokenize.detect_encoding(io.BytesIO(source).readline)
    return re.split(r"\r\n|\r|\n", source.decode(encoding))


def _column(lines: list[str], line: int, offset: int) -> int:
    """The 1-based character column of the AST's UTF-8 byte `offset` on `line`
    (CodeAnt on #436)."""
    text = lines[line - 1] if 0 < line <= len(lines) else ""
    return len(text.encode("utf-8")[:offset].decode("utf-8", errors="ignore")) + 1


def _function_findings(
    tree: ast.AST, path: str, lines: list[str]
) -> list[dict[str, Any]]:
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        value = cyclomatic_complexity(node)
        if value <= COMPLEXITY_REPORTED_ABOVE:
            continue
        end_line = node.end_lineno or node.lineno
        location = (
            node.lineno,
            _column(lines, node.lineno, node.col_offset),
            end_line,
            _column(lines, end_line, node.end_col_offset or 0),
        )
        message = f"`{node.name}` has a cyclomatic complexity of {value}"
        findings.append(
            _diagnostic_finding(
                "complexity", "cc", path, location, message, {"value": value}
            )
        )
    return findings


def _run_complexity(
    root: Path,
    paths: list[str],
    deadline: float,
    *,
    max_source_bytes: int = DEFAULT_DIAGNOSTIC_LIMITS.max_source_bytes,
    max_findings: int = DEFAULT_DIAGNOSTIC_LIMITS.max_findings,
) -> _ProducerResult:
    """The complexity metric, in this process: checked against the inventory deadline
    before each file (Codex, cubic and Claude on #436), and never reading more than
    max_source_bytes of one (CodeAnt on #436). The parser reports a source nested too
    deeply to parse as MemoryError or RecursionError, not SyntaxError, and the read
    raises OverflowError for a size it cannot provide, as for a max_source_bytes of
    sys.maxsize: each is that file's named gap (Codex, the Router's L2 on #436).
    max_findings is what the earlier producers left of the inventory's own: past it,
    no next file starts, and the caller's refusal follows (CodeAnt, the Router's C1
    on #436)."""
    result = _ProducerResult()
    result.runs.append(
        {
            "invocation": "complexity",
            "producer": "complexity",
            "version": COMPLEXITY_METRIC,
        }
    )
    for index, path in enumerate(paths):
        if len(result.findings) > max_findings:
            break
        if time.monotonic() >= deadline:
            late = "complexity timed out at the inventory deadline"
            result.unanalyzed.update(dict.fromkeys(paths[index:], late))
            break
        try:
            # Non-blocking, so that a FIFO swapped in after the check below cannot hold
            # the read (CodeAnt on #436).
            descriptor = os.open(
                root / path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
            )
            with os.fdopen(descriptor, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    result.unanalyzed[path] = "complexity: not a regular file, not read"
                    continue
                source = stream.read(max_source_bytes + 1)
            if len(source) > max_source_bytes:
                result.unanalyzed[path] = (
                    f"complexity: larger than {max_source_bytes} bytes, not parsed"
                )
                continue
            # The bytes, so that an encoding cookie or a BOM is read as Python reads it
            # (Octopus on #436).
            tree = ast.parse(source, filename=path)
        except (
            OSError,
            SyntaxError,
            ValueError,
            RecursionError,
            MemoryError,
            OverflowError,
        ) as exc:
            result.unanalyzed[path] = (
                f"complexity could not parse: {type(exc).__name__}"
            )
            continue
        result.findings += _function_findings(tree, path, _source_lines(source))
    return result


def _symlinked(root: Path, path: str) -> bool:
    """Whether the tracked path, or a directory on its way, is a symlink."""
    current = root
    for part in Path(path).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _regular_file(root: Path, path: str) -> bool:
    """Whether the tracked path is a regular file now. A FIFO or a device would block
    a read or never end it (CodeAnt on #436), and a missing file cannot be analyzed."""
    try:
        return stat.S_ISREG((root / path).lstat().st_mode)
    except OSError:
        return False


def _source_size(root: Path, path: str) -> int:
    """The tracked file's size by lstat; -1 when it cannot be read, so that the
    producers meet it and report it."""
    try:
        return (root / path).lstat().st_size
    except OSError:
        return -1


def _run_producers(
    root: Path,
    run: Path,
    expected: list[str],
    limits: DiagnosticLimits,
    gaps: list[str],
    deadline: float,
) -> _ProducerResult:
    """Every producer over the analyzable tracked Python set: never a symlinked path,
    whose content may lie outside the tree, and nothing when over budget."""
    result = _ProducerResult()
    if len(expected) > limits.max_files:
        gaps.append(
            f"budget: {len(expected)} tracked Python files exceed max_files {limits.max_files}"
        )
        result.unanalyzed = dict.fromkeys(expected, "budget: not analyzed")
        return result
    paths = []
    withheld: list[str] = []
    for path in expected:
        if _symlinked(root, path):
            result.unanalyzed[path] = "a symlink, never analyzed"
            withheld.append(path)
        elif not _regular_file(root, path):
            result.unanalyzed[path] = "missing or not a regular file, never analyzed"
            withheld.append(path)
        elif _source_size(root, path) > limits.max_source_bytes:
            # One bound for every producer, not only the metric (CodeAnt on #436).
            result.unanalyzed[path] = (
                f"larger than {limits.max_source_bytes} bytes, never analyzed"
            )
            # Never analyzed, so a finding a producer reaches it by is out of scope too
            # (cubic on #436).
            withheld.append(path)
        else:
            paths.append(path)
    if paths:
        versions = {
            producer: _producer_version(root, run, producer, limits, deadline)
            for producer in ("mypy", "ruff")
        }
        result.merge(_run_mypy(root, run, paths, limits, deadline, versions["mypy"]))
        # The existing refusal's predicate, the raw count above max_findings: once it
        # holds, no later producer starts, and that refusal follows (cubic on #436).
        if result.count() <= limits.max_findings:
            result.merge(
                _run_ruff(
                    root,
                    run,
                    paths,
                    limits,
                    deadline,
                    versions["ruff"],
                    limits.max_findings - result.count(),
                )
            )
        if result.count() <= limits.max_findings:
            result.merge(
                _run_complexity(
                    root,
                    paths,
                    deadline,
                    max_source_bytes=limits.max_source_bytes,
                    max_findings=limits.max_findings - result.count(),
                )
            )
    # A withheld path's findings come from a producer following an import into it
    # (Codex on #436): they stay listed, and are not tracked-source evidence.
    tracked = set(expected) - set(withheld)
    for finding in result.findings:
        # Whether the finding's named file is tracked: never proof that every input
        # that shaped it was tracked or bound to HEAD (the Router's U1 on #436).
        finding["native"]["tracked"] = finding["path"] in tracked
    return result


class _ComparisonUnavailable(OSError):
    """The comparison's own reason that Git cannot run, written into the gap as it is
    (the Router's Y2 on #436)."""


class _ComparisonRefused(ValueError):
    """The comparison's own reason that the base or a patch cannot be compared,
    written into the gap as it is (the Router's Y2 on #436)."""


def _diagnostic_git(
    root: Path,
    deadline: float,
    *arguments: str,
    cap: int = DEFAULT_DIAGNOSTIC_LIMITS.max_report_bytes,
) -> str:
    if time.monotonic() >= deadline:
        # Never Git against the millisecond floor (CodeAnt on #436).
        raise subprocess.SubprocessError("the inventory deadline had passed")
    # Consumed unchanged, as data: no caller GIT_DIR or configuration override reroutes
    # the comparison (IMPLEMENTER_RCA probe 2; Router 6218796619 on #436). Its PATH
    # lookup and the repository's own configuration are not isolated by it (PAO
    # 6218788670). Imported here, so that the default collection never loads it.
    from tools.candidate_prepare import PrepareError, _base_env, _git_executable

    try:
        git = _git_executable()
    except PrepareError as exc:
        raise _ComparisonUnavailable("git is unavailable") from exc
    # --no-replace-objects: every comparison read uses the objects the recorded base
    # names, never a refs/replace/ substitute (Codex, routed by the Router 6227604656
    # on #436, N1).
    command = [git, "--no-replace-objects", "-c", f"safe.directory={root}", *arguments]
    process = subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- argv list, no shell: Git by its resolved path, fixed options and a validated commit id
        command,
        cwd=root,
        env=_base_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    # Drained by the shared owner under max_report_bytes, so that a large historical
    # blob is never read whole (CodeAnt, the Router's G1 on #436): the output is used
    # only after a complete, successful exit.
    output = bytearray()
    if process.stdout is None:
        raise _ComparisonRefused(
            _and("the comparison's Git output is unavailable", _reap(process))
        )
    try:
        drained = bounded_process.drain(
            process,
            {"stdout": process.stdout},
            lambda _name, chunk: output.extend(chunk),
            deadline=deadline,
            cap=cap,
        )
    finally:
        try:
            process.stdout.close()
        except OSError:
            pass
    if drained.outcome == "exited" and drained.returncode is not None:
        if drained.returncode != 0:
            raise subprocess.CalledProcessError(drained.returncode, command)
        if not drained.selector_closed:
            raise _ComparisonRefused(
                "the comparison's Git selector could not be closed"
            )
        # Bytes, decoded without newline translation, so that a CRLF inside a
        # NUL-delimited name survives (CodeAnt on #436).
        return output.decode("utf-8", errors="surrogateescape")
    raise _git_failure(drained, _reap(process))


def _git_failure(
    drained: bounded_process.Drained, reaped: str | None
) -> _ComparisonRefused | subprocess.TimeoutExpired | OSError:
    """The exception for a Git read that did not exit cleanly, after its child was
    reaped once: the comparison's own reason, by the exception's type and with the
    cleanup's detail, or, when the child was reaped, the timeout or the read error
    itself (the Router's G1 and S-b on #436). It never reaps, and never runs Git."""
    if drained.outcome == "cap":
        return _ComparisonRefused(
            _and("the comparison's Git output exceeds max_report_bytes", reaped)
        )
    if drained.outcome == "deadline" and reaped is None:
        # The static name: an exception value, no process (Codacy on #436).
        return subprocess.TimeoutExpired("git", 0)
    if drained.outcome == "error" and drained.error is not None and reaped is None:
        return drained.error
    failure = drained.error or drained.exception
    kind = type(failure).__name__ if failure is not None else drained.outcome
    return _ComparisonRefused(
        _and(f"the comparison's Git output was not read whole ({kind})", reaped)
    )


def _diff_scope(
    root: Path,
    base: str,
    deadline: float,
    wanted: set[str] | None = None,
    cap: int = DEFAULT_DIAGNOSTIC_LIMITS.max_report_bytes,
) -> tuple[dict[str, Any], dict[str, set[int]]]:
    """The paths changed since `base`, and the lines each change adds, read per path
    by the GitHub patch reader's own hunk accounting (Claude on #436). It is imported
    here, so that the default collection never loads the merge-evidence reader. With
    `wanted`, only those paths are read line by line: a changed path that no finding
    names is listed, never read whole (CodeAnt on #436)."""
    from tools.merge_evidence_github import _added_lines

    # The base must be the commit it names: a tree, a blob, a tag that peels to
    # another id, a missing object or an unusable answer is the comparison's gap,
    # never a comparison labelled as its base (Codex, routed by the Router
    # 6224373564 on #436, B1).
    resolved = _diagnostic_git(
        root,
        deadline,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{base}^{{commit}}",
        cap=cap,
    )
    if resolved.splitlines() != [base]:
        raise _ComparisonRefused("the base is not that commit")
    names = _diagnostic_git(
        root,
        deadline,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        base,
        "HEAD",
        cap=cap,
    ).split("\0")
    changed = sorted(name for name in names if name)
    lines: dict[str, set[int]] = {}
    for path in changed:
        if wanted is not None and path not in wanted:
            continue
        patch = _diagnostic_git(
            root,
            deadline,
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            base,
            "HEAD",
            "--",
            f":(literal){path}",
            cap=cap,
        )
        if "\n@@" not in patch:
            # No textual hunk proves that no line was added: a binary, mode-only or
            # otherwise unaccounted change is the comparison's gap, never an empty set
            # (the PAO and the Router on #436).
            raise _ComparisonRefused(f"the comparison of {path} has no textual hunk")
        read = _added_lines(patch[patch.index("\n@@") + 1 :])
        if read is None:
            raise _ComparisonRefused(
                f"the comparison of {path} is not a sequence of hunks"
            )
        lines[path] = {number for number, _ in read[0]}
    return {"base": base, "changed_paths": changed}, lines


def _in_diff(finding: Mapping[str, Any], changed: Mapping[str, list[int]]) -> bool:
    """Whether a changed line lies anywhere in the finding's range (CodeAnt on #436)."""
    location = finding.get("range") or {}
    start = location.get("start_line")
    if start is None:
        return False
    end = location.get("end_line", start)
    # The path's changed lines, ordered once, and one bisect: never every line of the
    # range, whose end comes from a producer record (Codex, the Router's W1), nor
    # every changed line for each finding (cubic, the Router's I1 on #436).
    lines = changed.get(finding["path"], [])
    index = bisect.bisect_left(lines, start)
    return index < len(lines) and lines[index] <= end


def _annotate_diff(
    root: Path,
    base: str,
    findings: list[dict[str, Any]],
    gaps: list[str],
    deadline: float,
    cap: int = DEFAULT_DIAGNOSTIC_LIMITS.max_report_bytes,
    *,
    compare: bool = True,
) -> dict[str, Any] | None:
    """Each finding's `in_diff` against `base`, or None, never False, when the
    comparison failed (Amazon Q, Kilo and Octopus on #436); the diff scope. Without
    `compare`, the base is still checked, and nothing is compared: a dirty or unknown
    tree's producers read the working tree, and the comparison reads HEAD (the
    Router's D1 on #436)."""
    diff: dict[str, Any] | None = None
    changed: dict[str, list[int]] | None = None
    try:
        exact_sha(base, "base")
    except ValueError:
        gaps.append(f"base {base!r} is not a 40-hex commit id")
    else:
        try:
            if compare:
                diff, lines = _diff_scope(
                    root, base, deadline, {finding["path"] for finding in findings}, cap
                )
                # Each path's changed lines ordered once, for every finding's bisect
                # (cubic, the Router's I1 on #436).
                changed = {path: sorted(numbers) for path, numbers in lines.items()}
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            # The comparison's own reasons are written as they are; any other failure
            # by its type alone, never its text (the Router's X1 and Y2 on #436).
            own = isinstance(exc, (_ComparisonUnavailable, _ComparisonRefused))
            reason = str(exc) if own else type(exc).__name__
            gaps.append(f"cannot compare with base {base}: {reason}")
    for finding in findings:
        finding["native"]["in_diff"] = (
            None if changed is None else _in_diff(finding, changed)
        )
    return diff


_SOURCE_BINDING_GAP = (
    "source binding UNVERIFIED: no bounded check of the index's assume-unchanged and "
    "skip-worktree entries, which can hide edits from git status; and the producers' "
    "import graph is not proven confined to the recorded tracked inputs, so an "
    "untracked module in the checkout can shape a diagnostic on a tracked path"
)


def _diagnostic_subject(
    root: Path, expected_revision: str | None, deadline: float
) -> tuple[dict[str, Any], list[str]]:
    """The subject as `git status` sees it, and its gaps. The index can hide an edit
    from that view (Codex on #436), and no bounded check of the index is admitted, so
    the source binding stays UNVERIFIED and is always a gap (the Router's I3 on #436,
    6210989878)."""
    if time.monotonic() >= deadline:
        # A spent budget reads nothing: the state is unknown (CodeAnt on #436).
        state: dict[str, Any] = {"revision": None, "tracked_tree_dirty": None}
    else:
        state = _git_state(root, timeout=_time_left(deadline))
    if state["tracked_tree_dirty"] is None:
        # A state the shared reader could not read whole names no revision: its value
        # may be the caller's KNOWLEDGE_KIT_REVISION, never observed. A revision read
        # just before a failed or out-of-budget status read is dropped too, a stated,
        # conservative loss (the Router's V1, 6225341677 on #436).
        state = {**state, "revision": None}
    gaps = []
    if state["tracked_tree_dirty"] is not False:
        gaps.append("the tracked tree is dirty or its state is unknown")
    if expected_revision is not None and state["revision"] != expected_revision:
        gaps.append(
            f"revision {state['revision']} is not the expected {expected_revision}"
        )
    gaps.append(_SOURCE_BINDING_GAP)
    return {
        **state,
        "expected_revision": expected_revision,
        "source_binding": "UNVERIFIED",
    }, gaps


def _diagnostic_coverage(
    expected: list[str] | None,
    result: _ProducerResult,
    gaps: list[str],
    pages: int,
) -> dict[str, Any]:
    reasons = list(gaps)
    if expected is not None and not expected:
        reasons.append("no tracked Python file")
    if result.unanalyzed:
        reasons.append(f"{len(result.unanalyzed)} tracked Python files unanalyzed")
    status = "COMPLETE"
    if reasons:
        status = "INCOMPLETE"
    elif result.partial:
        status = "PARTIAL"
    if result.partial:
        reasons.append(f"{len(result.partial)} files with unresolved imports")
    known = expected or []
    return readback_coverage(
        status,
        pages=pages,
        count=len(known) - len(set(result.unanalyzed) & set(known)),
        total=None if expected is None else len(expected),
        reason="; ".join(reasons) or None,
    )


def _inventory_configuration(limits: DiagnosticLimits) -> dict[str, Any]:
    return {
        "rule_map": [
            {
                "producer": tool,
                "code": code,
                "deepsource_rule": rule,
                "mapping": "PROVISIONAL",
            }
            for (tool, code), rule in sorted(DIAGNOSTIC_RULE_MAP.items())
        ],
        "ruff_select": list(DIAGNOSTIC_RUFF_SELECT),
        "complexity": {
            "metric": COMPLEXITY_METRIC,
            "reported_above": COMPLEXITY_REPORTED_ABOVE,
            "qualification": "UNQUALIFIED",
        },
        "limits": dataclasses.asdict(limits),
    }


def _tracked_python(root: Path, deadline: float) -> tuple[list[str] | None, str | None]:
    """The tracked Python set, enumerated by candidate_paths within what is left of
    the inventory's one budget; None, an unknown set, and its gap when it cannot be
    (Option A on #436). A spent budget enumerates nothing, rather than race Git
    against the millisecond floor."""
    if time.monotonic() >= deadline:
        return None, "the deadline passed before the tracked set was enumerated"
    try:
        paths = candidate_paths(root, timeout=_time_left(deadline))
    except RepositoryScopeError as exc:
        return None, scope_error_detail("cannot enumerate tracked-tree candidates", exc)
    return sorted(p.as_posix() for p in paths if p.suffix == ".py"), None


def _check_limits(limits: DiagnosticLimits) -> None:
    """Refuse, before any work, a limit that would fail open or admit none: a negative
    bound, which read() takes as everything (cubic on #436), a max_findings above the
    normalization bound, or a timeout that is not a positive finite number of seconds
    (CodeAnt on #436)."""
    for name in ("max_files", "max_findings", "max_report_bytes", "max_source_bytes"):
        value = getattr(limits, name)
        # An exact integer: inf or 1.5 would pass a comparison (CodeAnt on #436).
        if type(value) is not int or value < 0:
            raise QualityEvidenceError(f"{name} {value} must be a non-negative integer")
    if limits.max_findings > MAX_FINDINGS:
        raise QualityEvidenceError(
            f"max_findings {limits.max_findings} exceeds the normalization bound {MAX_FINDINGS}"
        )
    timeout = limits.timeout_seconds
    # A number first: isfinite raises on a string (CodeAnt on #436), and overflows on
    # an int too large for a float (cubic on #436).
    try:
        valid = type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
    except OverflowError:
        valid = False
    if not valid:
        raise QualityEvidenceError(
            f"timeout_seconds {timeout} must be a positive finite number of seconds"
        )


def _refuse_caller_git_overrides() -> None:
    """Refuse a caller whose environment overrides Git, before the inventory's first
    work (the Router's R1 and X-a on #436)."""
    # A caller whose environment overrides Git is refused before any work: each
    # variable that preparation's own scrub removes, even empty, could rebind the
    # subject, the scope or the comparison. The rule is that owner's, consumed
    # unchanged as data, with no list of its own, and a failure to obtain it is
    # refused too, never a fallback (Router 6223042901 on #436, R1). Only names are
    # reported, never values. The import is inside the boundary, so that an owner
    # that cannot be imported is refused too (Claude on #436).
    try:
        from tools.candidate_prepare import _git_env_without_caller_overrides

        kept = _git_env_without_caller_overrides()
    except Exception as exc:
        raise QualityEvidenceError(
            "the caller's Git environment could not be checked, so the subject cannot "
            "be bound: no inventory was written"
        ) from exc
    overrides = sorted(set(os.environ) - set(kept))
    if overrides:
        raise QualityEvidenceError(
            f"the caller's Git overrides are set ({', '.join(overrides)}), so the "
            "subject cannot be bound: no inventory was written"
        )


def collect_diagnostic_inventory(
    repository_root: Path,
    output_directory: Path,
    *,
    base: str | None = None,
    expected_revision: str | None = None,
    limits: DiagnosticLimits = DEFAULT_DIAGNOSTIC_LIMITS,
) -> Path:
    """Write the experimental diagnostic inventory of the tracked Python set into a
    new run directory under `output_directory`, and return its path. Only an
    explicit call runs it. More findings than `limits.max_findings` write no
    inventory at all: the raw reports stay in the run directory. It is never
    COMPLETE while its source binding is UNVERIFIED."""
    _check_limits(limits)
    _refuse_caller_git_overrides()
    root = repository_root.resolve()
    output = output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="diagnostic-", dir=output))
    deadline = time.monotonic() + limits.timeout_seconds
    source, gaps = _diagnostic_subject(root, expected_revision, deadline)
    expected, unknown = _tracked_python(root, deadline)
    if unknown is not None:
        gaps.append(unknown)
    result = _run_producers(root, run, expected or [], limits, gaps, deadline)
    if result.truncated:
        # A report cut at max_report_bytes, or whose capture failed, holds a prefix
        # whose rest is unknown, so, as over max_findings, nothing is published (Codex
        # on #436; the Router's V1 and G2).
        raise QualityEvidenceError(
            f"budget: a producer's output exceeded max_report_bytes "
            f"{limits.max_report_bytes} or was not captured whole; no inventory was "
            f"written, the raw reports are in {run}"
        )
    if result.count() > limits.max_findings:
        raise QualityEvidenceError(
            f"budget: {result.count()} findings exceed max_findings "
            f"{limits.max_findings}; no inventory was written, the raw reports are in {run}"
        )
    diff = (
        None
        if base is None
        else _annotate_diff(
            root,
            base,
            result.findings,
            gaps,
            deadline,
            limits.max_report_bytes,
            compare=source["tracked_tree_dirty"] is False,
        )
    )
    after, _ = _diagnostic_subject(root, expected_revision, deadline)
    unbound = True
    if after["tracked_tree_dirty"] is None:
        # A read that could not finish is no evidence of a change (Claude on #436).
        gaps.append("the subject could not be re-read after collection")
    elif source["tracked_tree_dirty"] is not None and (
        after["revision"],
        after["tracked_tree_dirty"],
    ) != (source["revision"], source["tracked_tree_dirty"]):
        gaps.append("the subject changed during collection")
    else:
        unbound = False
    if base is not None and unbound:
        # The comparison no longer describes the subject, so no answer stays definite
        # (the Router's D1 on #436).
        for finding in result.findings:
            finding["native"]["in_diff"] = None
    try:
        findings = deduplicate_findings(result.findings)
    except AnalyzerReadbackError as exc:
        raise QualityEvidenceError(f"cannot normalize the findings: {exc}") from exc
    return _publish(
        run,
        deadline,
        source=source,
        limits=limits,
        result=result,
        expected=expected,
        diff=diff,
        findings=findings,
        gaps=gaps,
    )


def _publish(
    run: Path,
    deadline: float,
    *,
    source: dict[str, Any],
    limits: DiagnosticLimits,
    result: _ProducerResult,
    expected: list[str] | None,
    diff: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    gaps: list[str],
) -> Path:
    """Write the inventory once. Its bytes are serialized, and its exclusive file
    opened, before the clock's last reading, so that a deadline crossed while
    preparing them is recorded: the gap is added once, and the coverage and the bytes
    are rebuilt once (Codex, the Router's T1 and S-c on #436). Only the write and
    close follow that reading."""

    def encoded() -> bytes:
        document = {
            "schema": DIAGNOSTIC_SCHEMA,
            "status": "EXPERIMENTAL",
            "source": source,
            "configuration": _inventory_configuration(limits),
            "producers": result.runs,
            "scope": {
                "full": {
                    "expected": expected,
                    "unanalyzed": [
                        {"path": p, "reason": r}
                        for p, r in sorted(result.unanalyzed.items())
                    ],
                    "partial": {
                        p: sorted(set(m)) for p, m in sorted(result.partial.items())
                    },
                },
                "diff": diff,
            },
            "coverage": _diagnostic_coverage(expected, result, gaps, len(result.runs)),
            "findings": findings,
        }
        return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")

    payload = encoded()
    inventory = run / DIAGNOSTIC_INVENTORY
    stream = _new_file(inventory)
    try:
        with stream:
            if time.monotonic() > deadline:
                gaps.append("the inventory ran past its deadline")
                payload = encoded()
            stream.write(payload)
    except BaseException as primary:
        # Only the file this call created exclusively is removed, and the primary
        # failure is raised (Codex, the Router's P-a on #436). This is no atomic
        # publication: until the removal, a reader can see the partial bytes.
        try:
            os.unlink(inventory)
        except OSError as removal:
            primary.add_note(
                f"the partial inventory {inventory} could not be removed: "
                f"{type(removal).__name__}"
            )
        raise
    return inventory


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
    except (LockFormatError, QualityEvidenceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"quality evidence: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
