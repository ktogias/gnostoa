"""Collect bounded release-quality evidence for the current tracked tree."""

from __future__ import annotations

import argparse
import ast
import bisect
import contextlib
import dataclasses
import hashlib
import importlib
import io
import json
import math
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time
import tokenize
import tomllib
import uuid
from collections.abc import Callable, Mapping
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, BinaryIO, TextIO, TypeGuard, cast
from urllib.parse import quote, unquote, urlparse

from tools import bounded_process, test_suite
from tools.analyzer_readback import (
    MAX_FINDINGS,
    AnalyzerReadbackError,
    canonical_json,
    deduplicate_findings,
    normalize_finding,
)
from tools.analyzer_readback import coverage as readback_coverage
from tools.github_events import exact_sha
from tools.repository_scope import (
    RepositoryScopeError,
    candidate_paths,
    has_git_metadata,
    scope_error_detail,
)
from tools.requirements_lock import (
    LockedRequirement,
    LockFormatError,
    locked_requirements,
    normalized_distribution_name,
)
from tools.security_scan import SecurityScanError, _strict_json_loads, scan_tracked_tree

if TYPE_CHECKING:
    # Only for its type: the default collection, collect_quality_evidence, never imports
    # the exact-tree owner; the explicit diagnostic inventory imports it where it runs.
    from tools.exact_tree import Limits as _TreeLimits

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


def _git_state(root: Path, *, timeout: float | None = None) -> dict[str, Any]:
    revision = os.environ.get("KNOWLEDGE_KIT_REVISION", "unbound")
    dirty: bool | None = None
    # Both reads share the one budget (cubic and CodeAnt on #436).
    end = None if timeout is None else time.monotonic() + timeout
    try:
        # One reading decides each read's check and its timeout, unfloored: a spent
        # budget starts no Git (CodeAnt, the Router's I-b on #436).
        remaining = None if end is None else end - time.monotonic()
        if remaining is not None and remaining <= 0:
            return {"revision": revision, "tracked_tree_dirty": None}
        revision_result = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=remaining,
        )
        revision = revision_result.stdout.strip()
        remaining = None if end is None else end - time.monotonic()
        if remaining is not None and remaining <= 0:
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
            timeout=remaining,
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
# COMPLETE while its source binding is UNVERIFIED (the Router's I3 and U1 on #436): it is
# BOUND only when the run's own record meets P1-P4 (Decision 0120).
# Which families run, with which selectors, on which files, is the protected profile's
# choice, made before any producer starts (#389 A0-MP1, Decision 0117).

DIAGNOSTIC_SCHEMA = "gnostoa-diagnostic-inventory/v3"
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
DIAGNOSTIC_RUFF_SELECT = (
    "SLF001",
    "PLR6301",
    "SIM117",
    "S106",
    # The unsafe-calls family (#389 H-PYSEC-2): pickle, eval, weak hashes, shell=True, os.system, SQL strings.
    "S301",
    "S307",
    "S324",
    "S602",
    "S605",
    "S608",
)
# The Python grammar every producer analyzes: the declared requires-python floor,
# as mypy's --python-version, ruff's --target-version and the metric's own parse
# (Codex on #436).
_PYTHON_TARGET = (3, 11)
COMPLEXITY_METRIC = "cyclomatic-n-1/v1"
COMPLEXITY_REPORTED_ABOVE = 15
_DIAGNOSTIC_FIXTURE_ROOT = "tests/fixtures/"
_UNRESOLVED_IMPORTS = frozenset({"import-not-found", "import-untyped"})
_QUOTED = re.compile(r'"([^"]+)"')
_DECISIONS = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)

# The protected family profile, read from the producer tree (#389 A0-MP1, owner
# 6384969093). Its shape is checked by the jsonschema validator the guardrail manifest
# uses; the rules across its fields by _check_profile.
DIAGNOSTIC_PROFILE = "policy/diagnostic-profile.yaml"
# The producer tree's own: beside the collector's code, never the staged tree, the
# working directory or a configured kit root (Router 6351766731 R1, as _OBSERVER).
_PRODUCER_TREE = Path(__file__).resolve().parent.parent
_PROFILE = _PRODUCER_TREE / DIAGNOSTIC_PROFILE
# The pins the launched producers must answer: the producer tree's lock, which the
# shadow readback's job installs (Decision 0118), never the analyzed tree's (P2).
_PRODUCER_LOCK = _PRODUCER_TREE / "requirements" / "development.lock"
DIAGNOSTIC_PROFILE_SCHEMA = "gnostoa-diagnostic-profile/v1"
# v2 adds the pinned tool families, their `tools` pins and the per-family `active` flag (#389 H-PYSEC-2).
DIAGNOSTIC_PROFILE_SCHEMA_V2 = "gnostoa-diagnostic-profile/v2"
# mypy first, so that its own budget check counts every finding so far; the in-process
# metric last (cubic on #436).
_PRODUCER_ORDER = (
    "mypy",
    "ruff",
    "complexity",
    "shellcheck",
    "hadolint",
    "actionlint",
    "gitlab-shellcheck",
    "secrets",
)
# The producers launched as processes, whose environment is observed.
_LAUNCHED_PRODUCERS = ("mypy", "ruff")
# Each identifier's whole text, checked by fullmatch in _check_profile: a schema
# pattern's $ also matches before a trailing newline (Revix on #459).
_NAME_TEXT = r"[a-z][a-z0-9-]{0,62}"
_PROFILE_ID_TEXT = r"[a-z][a-z0-9.-]{0,127}"
# Directory prefixes of the tree: relative, never a . or .. segment or a NUL, each
# ending in a slash.
_EXCLUDE_TEXT = r"(?:(?!\.{1,2}/)[^/\x00]+/)+"
_PROFILE_NAME = {"type": "string", "pattern": f"^{_NAME_TEXT}$"}
_PROFILE_SCOPE = {"anyOf": [_PROFILE_NAME, {"type": "null"}]}
# The v2 producers (#389 H-PYSEC-2): the pinned-tool families and secrets, and each one's pinned executables.
_V2_PRODUCERS_NAMES = frozenset(
    {"shellcheck", "hadolint", "actionlint", "gitlab-shellcheck", "secrets"}
)
_TOOL_PRODUCER_TOOLS: dict[str, tuple[str, ...]] = {
    "shellcheck": ("shellcheck",),
    "hadolint": ("hadolint",),
    "actionlint": ("actionlint", "shellcheck"),
    "gitlab-shellcheck": ("shellcheck",),
}

_PROFILE_SHAPE: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema", "id", "scopes", "families"],
    "additionalProperties": False,
    "properties": {
        "schema": {"enum": [DIAGNOSTIC_PROFILE_SCHEMA, DIAGNOSTIC_PROFILE_SCHEMA_V2]},
        "tools": {
            "type": "object",
            "propertyNames": _PROFILE_NAME,
            "additionalProperties": {
                "type": "object",
                "required": ["version", "sha256"],
                "additionalProperties": False,
                "properties": {
                    "version": {"type": "string", "minLength": 1},
                    "sha256": {
                        "type": "object",
                        "minProperties": 1,
                        "additionalProperties": {
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                        },
                    },
                },
            },
        },
        "id": {"type": "string", "pattern": f"^{_PROFILE_ID_TEXT}$"},
        "scopes": {
            "type": "object",
            "minProperties": 1,
            "propertyNames": _PROFILE_NAME,
            "additionalProperties": {
                "type": "object",
                "required": ["exclude"],
                "additionalProperties": False,
                "properties": {
                    "exclude": {
                        "type": "array",
                        "uniqueItems": True,
                        "items": {"type": "string", "pattern": f"^{_EXCLUDE_TEXT}$"},
                    }
                },
            },
        },
        "families": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/$defs/family"},
        },
    },
    "$defs": {
        "family": {
            "type": "object",
            "required": ["id", "producer", "diff", "full"],
            "additionalProperties": False,
            "properties": {
                "id": _PROFILE_NAME,
                "producer": {"enum": list(_PRODUCER_ORDER)},
                "diff": _PROFILE_SCOPE,
                "full": _PROFILE_SCOPE,
                "select": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {"type": "string"},
                },
                "reported_above": {"type": "integer", "minimum": 0},
                # Absent means active; the new families are off on the protected profile (#389 H-PYSEC-2).
                "active": {"type": "boolean"},
            },
            "allOf": [
                {
                    "if": {"properties": {"producer": {"const": "ruff"}}},
                    "then": {
                        "required": ["select"],
                        "not": {"required": ["reported_above"]},
                    },
                },
                {
                    "if": {"properties": {"producer": {"const": "complexity"}}},
                    "then": {
                        "required": ["reported_above"],
                        "not": {"required": ["select"]},
                    },
                },
                {
                    "if": {
                        "properties": {
                            "producer": {"enum": sorted(_V2_PRODUCERS_NAMES)}
                        }
                    },
                    "then": {
                        "not": {
                            "anyOf": [
                                {"required": ["select"]},
                                {"required": ["reported_above"]},
                            ]
                        }
                    },
                },
                {
                    "if": {"properties": {"producer": {"const": "mypy"}}},
                    "then": {
                        "not": {
                            "anyOf": [
                                {"required": ["select"]},
                                {"required": ["reported_above"]},
                            ]
                        }
                    },
                },
            ],
        }
    },
}


def load_diagnostic_profile(path: Path | None = None) -> dict[str, Any]:
    """The diagnostic inventory's protected profile, validated: by default
    `policy/diagnostic-profile.yaml` beside the collector's own code, as its observer
    is, so its own revision's, never the analyzed tree's (#389 A0-MP1). The kit
    locator's KNOWLEDGE_KIT_ROOT is not consulted: it accepts any tree holding its
    markers, the analyzed one included (the PAO's 6387738095 on #389), and in the
    runtime image it names the image's kit while a checkout's code runs. A profile
    that cannot be read, or breaks its contract, is refused."""
    from tools.knowledge_common import KnowledgeFormatError, load_yaml

    try:
        # The default is never followed out of the producer tree, a link included
        # (CodeAnt on #459), and one that cannot be resolved, a link loop included,
        # is refused as well (Revix on #459).
        source = path if path is not None else _confined_profile()
        profile = load_yaml(source)
    except (KnowledgeFormatError, UnicodeDecodeError) as exc:
        # By its type alone, never its text or a path, as the comparison's other
        # failures are (Revix's sanitized-error-diagnostics on #459).
        raise QualityEvidenceError(
            f"cannot load the diagnostic profile: {type(exc).__name__}"
        ) from None
    return _validated_profile(profile)


def _confined_profile() -> Path:
    """The default profile's resolved path inside the producer tree, by the existing
    confinement owner; a resolution that fails is its format error."""
    from tools.knowledge_common import KnowledgeFormatError, confine_to_root

    try:
        return confine_to_root(
            _PROFILE, _PRODUCER_TREE, label="the diagnostic profile"
        )[0]
    except (OSError, RuntimeError) as exc:
        raise KnowledgeFormatError(
            f"the diagnostic profile cannot be resolved: {type(exc).__name__}"
        ) from None


def _validated_profile(profile: object) -> dict[str, Any]:
    """A deep copy of `profile`, once its shape and its cross-field rules hold. It is
    untrusted until then, so typed as an object (Revix on #459)."""
    from jsonschema import Draft202012Validator

    errors = sorted(
        Draft202012Validator(_PROFILE_SHAPE).iter_errors(profile),
        key=lambda error: error.json_path,
    )
    if errors:
        raise QualityEvidenceError(
            f"diagnostic profile: {errors[0].json_path}: {errors[0].message}"
        )
    # The shape is now an object of the profile's form.
    checked = cast("Mapping[str, Any]", profile)
    _check_profile(checked)
    copied: dict[str, Any] = json.loads(canonical_json(checked))
    return copied


def _check_profile(profile: Mapping[str, Any]) -> None:
    """The rules its shape cannot state: every identifier's whole text, then, family by
    family, _check_family's, and _check_selection's for the Ruff codes."""
    _check_identifiers(profile)
    _check_version(profile)
    seen: set[str] = set()
    producers: set[str] = set()
    rules: dict[str, str] = {}
    for family in profile["families"]:
        _check_family(profile, family, seen, producers)
        _check_selection(family, rules)


def _check_version(profile: Mapping[str, Any]) -> None:
    """v1 has neither the pinned tool families nor their pins nor `active`; under v2 each pinned family's tools are
    pinned (#389 H-PYSEC-2)."""
    families = profile["families"]
    if profile["schema"] == DIAGNOSTIC_PROFILE_SCHEMA:
        if "tools" in profile or any(
            "active" in f or f["producer"] in _V2_PRODUCERS_NAMES for f in families
        ):
            raise QualityEvidenceError(
                f"diagnostic profile: a {DIAGNOSTIC_PROFILE_SCHEMA} profile has no tool families, pins or activation"
            )
        return
    pinned = profile.get("tools", {})
    for family in families:
        for tool in _TOOL_PRODUCER_TOOLS.get(family["producer"], ()):
            if tool not in pinned:
                raise QualityEvidenceError(
                    f"diagnostic profile: family {family['id']!r} needs tool {tool!r}, which has no pin"
                )


def _active_families(profile: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The families acquisition runs: an inactive one is never planned, run or rowed (#389 H-PYSEC-2)."""
    return [family for family in profile["families"] if family.get("active", True)]


def _check_identifiers(profile: Mapping[str, Any]) -> None:
    """The profile's id, scope names, exclusions and family ids, each matched whole."""
    texts = [(_PROFILE_ID_TEXT, profile["id"])]
    texts += [(_NAME_TEXT, name) for name in profile["scopes"]]
    texts += [
        (_EXCLUDE_TEXT, prefix)
        for scope in profile["scopes"].values()
        for prefix in scope["exclude"]
    ]
    texts += [(_NAME_TEXT, family["id"]) for family in profile["families"]]
    for pattern, text in texts:
        if re.fullmatch(pattern, text) is None:
            raise QualityEvidenceError(f"diagnostic profile: {text!r} is not whole")


def _check_family(
    profile: Mapping[str, Any],
    family: Mapping[str, Any],
    seen: set[str],
    producers: set[str],
) -> None:
    """A family is declared once, names declared scopes and acquires something; there
    is one mypy family and one complexity family at most."""
    name, producer = family["id"], family["producer"]
    if name in seen:
        raise QualityEvidenceError(
            f"diagnostic profile: family {name!r} is declared twice"
        )
    seen.add(name)
    scopes = [family["diff"], family["full"]]
    undeclared = [
        scope
        for scope in scopes
        if scope is not None and scope not in profile["scopes"]
    ]
    if undeclared:
        raise QualityEvidenceError(
            f"diagnostic profile: family {name!r} names an undeclared scope {undeclared[0]!r}"
        )
    if scopes == [None, None]:
        raise QualityEvidenceError(
            f"diagnostic profile: family {name!r} acquires nothing"
        )
    if producer != "ruff" and producer in producers:
        raise QualityEvidenceError(
            f"diagnostic profile: a second {producer} family, {name!r}"
        )
    producers.add(producer)


def _check_selection(family: Mapping[str, Any], rules: dict[str, str]) -> None:
    """Each Ruff code is one the inventory maps, and is selected by one family only."""
    name = family["id"]
    for code in family.get("select", ()):
        if code not in DIAGNOSTIC_RUFF_SELECT:
            raise QualityEvidenceError(
                f"diagnostic profile: family {name!r} selects {code!r}, which the inventory does not map"
            )
        if code in rules:
            raise QualityEvidenceError(
                f"diagnostic profile: {code!r} is selected by {rules[code]!r} and {name!r}"
            )
        rules[code] = name


def _in_scope(profile: Mapping[str, Any], scope: str | None, path: str) -> bool:
    """Whether `path` lies in the profile's named scope; never in a null one."""
    if scope is None:
        return False
    excluded = profile["scopes"][scope]["exclude"]
    return not any(path.startswith(prefix) for prefix in excluded)


def _diff_only(
    profile: Mapping[str, Any], family: Mapping[str, Any], expected: list[str]
) -> list[str]:
    """The family's DIFF-scope paths that its FULL scope does not reach: acquired only
    when a change touches them."""
    return [
        path
        for path in expected
        if _in_scope(profile, family["diff"], path)
        and not _in_scope(profile, family["full"], path)
    ]


@dataclasses.dataclass(frozen=True)
class _Changes:
    """What the DIFF scopes acquire by, read before any producer runs: the changed
    paths and, for the paths complexity acquires by function, the lines each change
    adds; or, when they are unknown, why (#389 A0-MP1)."""

    paths: frozenset[str] | None
    lines: Mapping[str, list[int]]
    unknown: str | None = None
    # Each path whose added lines could not be read, with why: that path's alone,
    # never the changed paths or another path's lines (CodeAnt and Claude on #459).
    lines_unread: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class DiagnosticLimits:
    """The finite bounds of one inventory: one deadline for every producer, Git call,
    enumeration, stage and identity read, and caps on the tracked Python files, the
    findings, each producer's output and each source that the complexity metric
    parses in this process. The whole frozen tree has its own file and byte caps,
    the exact-tree owner's defaults, apart from the Python inputs `max_files`
    counts (Router #389 6325382720, D2)."""

    max_files: int = 5_000
    max_findings: int = MAX_FINDINGS
    max_report_bytes: int = 64 * 1024 * 1024
    timeout_seconds: float = 900.0
    max_source_bytes: int = 8 * 1024 * 1024
    max_tree_files: int = 200_000
    max_tree_bytes: int = 4 << 30


DEFAULT_DIAGNOSTIC_LIMITS = DiagnosticLimits()


@dataclasses.dataclass(frozen=True)
class _Launch:
    """The interpreter launch a producer adapter builds its argv from and declares for
    its runs: what an environment observation is associated by, never a producer name
    or an argv prefix (Router 6351766731 R2)."""

    executable: str
    flags: tuple[str, ...]

    def argv(self) -> list[str]:
        return [self.executable, *self.flags]


# The producers' interpreter under -I, its own isolation, as security_scan's child runs
# (Codex on #436): mypy's and Ruff's adapters declare it, and the environment is observed
# under it.
_ISOLATED_PYTHON = _Launch(sys.executable, ("-I",))


@dataclasses.dataclass
class _ProducerResult:
    runs: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    # The runs whose adapter declares a launch, with it: in memory only, never written
    # (Router 6351766731 R2).
    launched: list[tuple[_Launch, dict[str, Any]]] = dataclasses.field(
        default_factory=list
    )
    truncated: bool = False
    findings: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    unanalyzed: dict[str, str] = dataclasses.field(default_factory=dict)
    partial: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    # Valid findings counted past the allowance, never kept (the Router's M1 on #436).
    excess: int = 0
    # Each family's own analysis of its targets, by _family_row (#389 A0-MP1).
    families: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    # Every path some family targeted (#459).
    targeted: set[str] = dataclasses.field(default_factory=set)

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

    def add_run(self, record: dict[str, Any], launch: _Launch) -> None:
        """A run its adapter launched as `launch`."""
        self.runs.append(record)
        self.launched.append((launch, record))

    def merge(self, other: _ProducerResult) -> None:
        self.runs += other.runs
        self.launched += other.launched
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
    # An argument past 200 bytes, as the environment observation's script, is named by
    # its size: the log keeps the interpreter and its flags (#389 F3 S2-C).
    shown = (a if len(a) <= 200 else f"<{len(a)} bytes>" for a in command[:8])
    print("+ " + " ".join(shown), flush=True)
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
    except BaseException as escaped:
        # A cancellation that escapes the shared drain still reaps the child once,
        # through the existing owner, and is raised again unchanged; a failed reap is
        # noted on it, never in its place (Claude, the Router's K-b on #436).
        failure = _reap(process)
        if failure is not None:
            escaped.add_note(failure)
        raise
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
        # A non-0/1 exit is named first, then a cleanup's detail, once (Octopus, the
        # Router's O-a on #436).
        status = drained.returncode
        named = None if status in (0, 1) else f"exited {status}"
        return status, _with(named, cleanup), False
    gap, invalid = _drain_gap(drained)
    gap = _with(_with(gap, cleanup), _reap(process))
    return process.returncode, gap, invalid


def _drain_gap(drained: bounded_process.Drained) -> tuple[str, bool]:
    """The gap and the validity of a drain that did not exit cleanly, by its outcome
    alone: it performs no I/O, close or reap (SonarCloud, the Router's S-d on #436)."""
    if drained.outcome == "deadline":
        return "timed out at the inventory deadline", False
    if drained.outcome == "cap":
        return _OUTPUT_CAP_GAP, True
    if drained.outcome == "error" and drained.error is not None:
        return (
            f"the producer could not be followed: {type(drained.error).__name__}",
            True,
        )
    if drained.outcome == "unexpected" and drained.exception is not None:
        failure = type(drained.exception).__name__
        return f"the producer could not be followed: {failure}", True
    return (
        f"the producer could not be followed: unexpected drain outcome {drained.outcome}",
        True,
    )


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


# The producers' installed environment, as their own interpreter resolves it under -I:
# the staged tree is not their only input. One tree under two installed sets gave mypy
# two findings with every other recorded field identical (#389 F3 S2-C, the C6 probe in
# 6347549109). Two bounded metadata observations, one before the version reads and one
# after the producers, name the interpreter, its import roots and their top-level
# entries, and each `*.dist-info` with a digest of the RECORD bytes read. What differs
# between them is a gap. Equal endpoints prove neither continuity, since a change
# restored in between is not seen (PAO 6347682576), nor installed content, since a
# RECORD digest attests that file's bytes, not the files it lists (Router 6347672936).
# v2 adds the entries of RECORD-owned directories that no RECORD lists (D-U, H-out:
# Router #389 6373641379). This one version names the observer's report, the closed
# acceptance below and the member written from it, so none of them is relabelled alone
# (PAO 6372664518).
ENVIRONMENT_OBSERVATION_FORMAT = "gnostoa-producer-environment-observation/v2"
ENVIRONMENT_OBSERVATION_SCOPE = (
    "metadata, and the entries of RECORD-owned directories that no RECORD lists, "
    "observed at two endpoints: neither continuous nor complete installed content"
)
# What the observation does not see, stated so that endpoints_equal is never read as
# complete equality (owner 6351449420 item 4). The staged tree on MYPYPATH is bound by
# tree_binding, not by this observation.
ENVIRONMENT_OBSERVATION_UNOBSERVED = (
    "installed files a RECORD lists without a hash",
    "files outside RECORD-owned directories: loose top-level modules and the "
    "standard library",
    "rows outside the import root",
    "import resolution beyond the interpreter's -I path",
    "changes between the endpoints",
)
# Measured in gnostoa:development-445: 4 import-path entries (3 directories and an
# absent zip, no archive), 430 entries (201 in the largest root), 69 distributions, RECORD at most 1,608,909 bytes
# and 2,258,869 in all, names at most 59 bytes (#389 F3 S2-C). Each cap keeps a wide
# margin and is enforced while the observation enumerates or reads, before anything is
# sorted. A file read, a RECORD, an archive on the path or a file a RECORD lists, counts
# against both file caps. The file caps were chosen for those files (Router #389
# 6364506650, B): the RECORD-listed files in the import roots measured 20,172 files and
# 144,144,781 bytes, the largest 36,986,816 bytes, in that image (6364297742).
# The walk's caps bound counts (Router #389 6374387035): directories, each owned one just
# before it is opened and each subdirectory when it is listed; entries as they are
# listed; depth in directory levels below the root, an owned directory being 1; in-root
# RECORD rows as they are kept, each as a fixed-size digest; and unlisted entries as they
# are recorded. Each overflow is that key's own stop. Their values were chosen for
# gnostoa:development-4e4ced3a, whose RECORD-owned directories held 967 directories,
# 23,586 entries, depth 7, 22,769 in-root rows and no unlisted entry (packet 6372955502).
# The cost measured at each bound, in finite cases, is #389 6374250615's: a measurement,
# not a maximum.
ENVIRONMENT_OBSERVATION_CAPS = {
    "roots": 32,
    "entries_per_root": 4096,
    "entries": 16384,
    "distributions": 1024,
    "file_bytes": 64 * 1024 * 1024,
    "file_bytes_total": 256 * 1024 * 1024,
    "string_bytes": 4096,
    "output_bytes": 1024 * 1024,
    "tree_directories": 8192,
    "tree_entries": 131072,
    "tree_depth": 32,
    "record_rows": 131072,
    "unlisted": 1024,
}
# The observer, tools/python_environment_observation.py: the toolkit's own module beside
# this one, so the collector's own revision, run by its path and never from the staged
# tree, the working directory or PATH (Router 6351766731 R1).
_OBSERVER = Path(__file__).resolve().parent / "python_environment_observation.py"
_ENVIRONMENT_UNAVAILABLE_GAP = (
    "producer environment identity unavailable: an observation before or after the "
    "producers did not complete, was capped or was cut, so no installed set is "
    "identified"
)
_ENVIRONMENT_CHANGED_GAP = (
    "producer environment changed between its observations: the metadata observed "
    "before the producers differs from the metadata observed after them"
)


def _is_text_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


# The v2 contract of the observer's report, which is evidence the collector reads, not a
# wire member: every field is required, and an unknown or repeated field is not v1. A
# missing `incomplete` is therefore never read as a completed observation (cubic
# 4354512437; PAO 6353587922; Router 6353798690).
_OBSERVATION_FIELDS = frozenset(
    {
        "format",
        "incomplete",
        "interpreter",
        "roots",
        "entries",
        "archives",
        "distributions",
        "unlisted",
    }
)
_UNLISTED_KINDS = frozenset({"file", "link", "directory", "other"})


def _valid_unlisted(entry: object, roots: list[str]) -> bool:
    """An unlisted entry as the observer writes it: one of its roots, a plain path
    relative to it, a kind, and the kind's value, a file's sha256, a link's target or
    nothing."""
    if not (isinstance(entry, list) and len(entry) == 4):
        return False
    root, path, kind, value = entry
    if not (
        isinstance(root, str)
        and root in roots
        and isinstance(path, str)
        # Plain and root-relative: no absolute path and no empty, `.` or `..` part
        # (cubic on #455).
        and all(part not in ("", ".", "..") for part in path.split("/"))
        and isinstance(kind, str)
        and kind in _UNLISTED_KINDS
    ):
        return False
    if kind == "file":
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(c in "0123456789abcdef" for c in value)
        )
    return isinstance(value, str) if kind == "link" else value is None


def _valid_observation(observed: object) -> bool:
    """A complete observation in the collector's own format, every field the shape the
    script writes; anything else is no observation (cubic 4353631703)."""
    if not isinstance(observed, dict):
        return False
    interpreter, roots, entries = (
        observed.get("interpreter"),
        observed.get("roots"),
        observed.get("entries"),
    )
    archives, distributions = observed.get("archives"), observed.get("distributions")
    return (
        # Exactly the fields the observer writes, and no other (cubic 4354512437).
        set(observed) == _OBSERVATION_FIELDS
        and observed.get("format") == ENVIRONMENT_OBSERVATION_FORMAT
        and observed.get("incomplete") is None
        and isinstance(interpreter, dict)
        and set(interpreter) == {"executable", "version"}
        and all(isinstance(interpreter.get(k), str) for k in ("executable", "version"))
        and _is_text_list(roots)
        and isinstance(entries, dict)
        and set(entries) == set(roots)
        and all(_is_text_list(names) for names in entries.values())
        and isinstance(archives, list)
        and all(_is_text_list(a) and len(a) == 2 for a in archives)
        and isinstance(distributions, list)
        and all(_is_text_list(d) and len(d) == 3 for d in distributions)
        and isinstance(observed.get("unlisted"), list)
        and all(_valid_unlisted(entry, roots) for entry in observed["unlisted"])
    )


def _environment_command() -> list[str]:
    return [
        *_ISOLATED_PYTHON.argv(),
        str(_OBSERVER),
        json.dumps(ENVIRONMENT_OBSERVATION_CAPS, sort_keys=True),
        ENVIRONMENT_OBSERVATION_FORMAT,
    ]


def _regular_observer(path: Path) -> bool:
    """The observer is a regular file reached without a link: checked before any
    launch, so that a missing or linked one is no observation (Router 6351766731
    R1)."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _observe_environment(
    root: Path, run: Path, limits: DiagnosticLimits, deadline: float, when: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """One bounded metadata observation of the producers' environment, run as they
    run, isolated with -I and under the inventory's deadline and max_report_bytes: its
    report's evidence and its interpreter, or None for each when it does not complete,
    is incomplete, is cut or is not the observation's own format."""
    if not _regular_observer(_OBSERVER):
        return None, None
    report = run / f"diagnostic-environment-{when}.json"
    status, gap, invalid = _bounded_run(
        _environment_command(),
        cwd=root,
        environment=dict(os.environ),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    if gap is not None or invalid or status != 0:
        return None, None
    # One read: the bytes parsed are the bytes the evidence names, and a read that
    # fails is an unavailable observation, never an escaping error (Sourcery on #452).
    # The strict loader refuses a duplicate field rather than keep its last value
    # (cubic 4354512437): security_scan's, consumed rather than copied (#365 F1).
    try:
        content = report.read_bytes()
        observed = _strict_json_loads(content.decode("utf-8"))
    except (OSError, ValueError, RecursionError, SecurityScanError):
        return None, None
    if not _valid_observation(observed):
        return None, None
    return (
        {
            "path": report.relative_to(run).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        },
        dict(observed["interpreter"]),
    )


def _environment_observation(
    before: tuple[dict[str, Any] | None, dict[str, Any] | None],
    after: tuple[dict[str, Any] | None, dict[str, Any] | None],
    gaps: list[str],
) -> dict[str, Any]:
    """The optional record member: its own format, its endpoint scope and caps, both
    observations' evidence, and their status. Its absence from a v2 record means not
    observed, never equal or trusted."""
    if before[0] is None or after[0] is None:
        status = "unavailable"
        gaps.append(_ENVIRONMENT_UNAVAILABLE_GAP)
    elif before[0]["sha256"] != after[0]["sha256"]:
        status = "endpoints_differ"
        gaps.append(_ENVIRONMENT_CHANGED_GAP)
    else:
        status = "endpoints_equal"
    return {
        "format": ENVIRONMENT_OBSERVATION_FORMAT,
        "scope": ENVIRONMENT_OBSERVATION_SCOPE,
        "caps": dict(ENVIRONMENT_OBSERVATION_CAPS),
        "unobserved": list(ENVIRONMENT_OBSERVATION_UNOBSERVED),
        "status": status,
        "interpreter": before[1],
        "before": before[0],
        "after": after[0],
    }


def _producer_version(
    root: Path, run: Path, producer: str, limits: DiagnosticLimits, deadline: float
) -> str | None:
    """The producer's own `--version`, run as it runs: isolated with -I, and under the
    deadline. The collector's metadata search can include the
    analyzed root, so a tracked dist-info could name another version (Codex on
    #436). None when it cannot be read."""
    report = run / f"diagnostic-{producer}-version.txt"
    status, gap, _invalid = _bounded_run(
        [*_ISOLATED_PYTHON.argv(), "-m", producer, "--version"],
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
        # -I, the interpreter's own isolation, as security_scan's child runs: -P left
        # the user site on, so a usercustomize ran in every producer (Codex on #436).
        *_ISOLATED_PYTHON.argv(),
        "-m",
        "mypy",
        "--config-file=",
        "--python-version",
        "{}.{}".format(*_PYTHON_TARGET),
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
    # A file that is absolute, has a .. segment, names only the group's root, as "", "."
    # or "./" do, or holds a NUL, which no path can, cannot be bound to a file of the
    # group: it is the report's malformed record, before any prefix could hide it
    # (Codex, routed by the Router 6224373564 and 6241642961 on #436, M2).
    if type(path) is str and (
        not PurePosixPath(path).parts
        or path.startswith("/")
        or ".." in path.split("/")
        or "\0" in path
    ):
        raise ValueError(f"mypy file {path!r} is not relative to its group's root")
    # A valid spelling, as "./tools/sample.py", is keyed by its canonical relative path,
    # as ruff's is, so the tracked set and the diff find the file under one key; the
    # report keeps the producer's own spelling (Claude, the Router's M2 on #436).
    if type(path) is str:
        path = PurePosixPath(path).as_posix()
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
        result.add_run(
            _run_record(name, "mypy", command, status, report, run, version),
            _ISOLATED_PYTHON,
        )
        result.truncated = result.truncated or invalid
        gap = _mypy_gap(report, prefix, status, gap, result, limits.max_findings)
        if gap is not None:
            result.unanalyzed.update({path: f"{name} {gap}" for path in files})
    return result


def _ruff_finding(record: Mapping[str, Any], root: Path) -> dict[str, Any]:
    name = Path(record["filename"])
    path = (name if name.is_absolute() else root / name).resolve().relative_to(root)
    if path == Path("."):
        # A filename that resolves to the root names no file: the report's malformed
        # record (Codex, the Router's M2 on #436).
        raise ValueError("the ruff filename names no file")
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
    *,
    select: tuple[str, ...] | list[str] = DIAGNOSTIC_RUFF_SELECT,
    name: str = "ruff",
) -> _ProducerResult:
    """Ruff's run of `select` over `paths`, named `name`: a family's own run is
    `ruff:<family>` (#389 A0-MP1)."""
    allowance = limits.max_findings if max_findings is None else max_findings
    result = _ProducerResult()
    command = [
        # -I, the interpreter's own isolation, as security_scan's child runs: -P left
        # the user site on, so a usercustomize ran in every producer (Codex on #436).
        *_ISOLATED_PYTHON.argv(),
        "-m",
        "ruff",
        "check",
        "--isolated",
        "--ignore-noqa",  # a flag, not a marker -- ruff then reports what its suppression comments would hide (Codex on #436)
        "--no-cache",
        "--preview",
        "--target-version",
        "py{}{}".format(*_PYTHON_TARGET),
        "--select",
        ",".join(select),
        "--output-format",
        "json",
        "--",
        *paths,
    ]
    report = run / f"diagnostic-{name.replace(':', '-')}.json"
    status, gap, invalid = _bounded_run(
        command,
        cwd=root,
        environment=dict(os.environ),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    result.add_run(
        _run_record(name, "ruff", command, status, report, run, version),
        _ISOLATED_PYTHON,
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
        result.unanalyzed.update({path: f"{name} {gap}" for path in paths})
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
    tree: ast.AST,
    path: str,
    lines: list[str],
    *,
    reported_above: int = COMPLEXITY_REPORTED_ABOVE,
    added: list[int] | None = None,
) -> list[dict[str, Any]]:
    """The functions above `reported_above`; with `added`, the sorted lines a change
    adds, only the functions whose range holds one of them, chosen before any value is
    computed: acquisition, never a filter (#389 A0-MP1)."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = node.end_lineno or node.lineno
        # The range covers what the value counts: from the earliest decorator
        # expression's line, in the function's column (Codex, the Router's D-a on #436).
        start_line = min((d.lineno for d in node.decorator_list), default=node.lineno)
        span = {"path": path, "range": {"start_line": start_line, "end_line": end_line}}
        if added is not None and not _in_diff(span, {path: added}):
            continue
        value = cyclomatic_complexity(node)
        if value <= reported_above:
            continue
        location = (
            start_line,
            _column(lines, start_line, node.col_offset),
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
    reported_above: int = COMPLEXITY_REPORTED_ABOVE,
    functions: Mapping[str, list[int]] | None = None,
) -> _ProducerResult:
    """The complexity metric, in this process: checked against the inventory deadline
    before each file (Codex, cubic and Claude on #436), and never reading more than
    max_source_bytes of one (CodeAnt on #436). The parser reports a source nested too
    deeply to parse as MemoryError or RecursionError, not SyntaxError, and the read
    raises OverflowError for a size it cannot provide, as for a max_source_bytes of
    sys.maxsize: each is that file's named gap (Codex, the Router's L2 on #436).
    max_findings is what the earlier producers left of the inventory's own: past it,
    no next file starts, and the caller's refusal follows (CodeAnt, the Router's C1
    on #436). A path in `functions` is measured only in the functions a change adds
    a line to, by its sorted added lines (#389 A0-MP1)."""
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
            # (Octopus on #436), in the producers' declared grammar, so that a host's
            # newer one changes nothing: best-effort, as Python's feature_version is
            # (Codex on #436).
            tree = ast.parse(source, filename=path, feature_version=_PYTHON_TARGET)
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
        result.findings += _function_findings(
            tree,
            path,
            _source_lines(source),
            reported_above=reported_above,
            added=None if functions is None else functions.get(path),
        )
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


def _attach_environment_observation(
    result: _ProducerResult,
    root: Path,
    run: Path,
    limits: DiagnosticLimits,
    deadline: float,
    before: tuple[dict[str, Any] | None, dict[str, Any] | None],
    gaps: list[str],
) -> None:
    """The second observation, after the producers, and the member on the runs it
    describes."""
    # Past the refusal's predicate no inventory is written, so, as for a later
    # producer, no later observation starts (cubic on #436).
    after = (
        _observe_environment(root, run, limits, deadline, "after")
        if result.count() <= limits.max_findings
        else (None, None)
    )
    observation = _environment_observation(before, after, gaps)
    # The observation describes the runs launched as it was, by the launch their
    # adapter declares: whatever their producer, and never by a name, an argv prefix
    # or for an in-process run (Router 6351766731 R2).
    for launch, record in result.launched:
        if launch == _ISOLATED_PYTHON:
            record["environment_observation"] = observation


def _family_targets(
    profile: Mapping[str, Any],
    family: Mapping[str, Any],
    expected: list[str],
    changes: _Changes,
) -> tuple[list[str], dict[str, list[int]], str | None]:
    """The family's targets, in the tracked order: its FULL scope's, and its DIFF
    scope's changed paths, whole; the added lines of those it acquires through DIFF
    alone; and why its DIFF targets are unknown, if they are."""
    full = {path for path in expected if _in_scope(profile, family["full"], path)}
    diff_only = _diff_only(profile, family, expected)
    changed = changes.paths or frozenset()
    added = {path for path in diff_only if path in changed}
    targets = [path for path in expected if path in full or path in added]
    functions = {path: list(changes.lines.get(path, [])) for path in added}
    return targets, functions, changes.unknown if diff_only else None


def _family_row(
    family: Mapping[str, Any],
    targets: list[str] | None,
    unanalyzed: Mapping[str, str],
    partial: Mapping[str, Any],
    unknown: str | None,
) -> dict[str, Any]:
    """One family's own analysis of its targets, counted in files: COMPLETE only when
    they are known and each was analyzed, none included; never coverage alone, since the
    composite also carries the inventory's shared gaps (the PAO's R2 on #389
    6387305292)."""
    reasons = []
    if unknown is not None:
        reasons.append(f"its DIFF targets are unknown: {unknown}")
    if targets is None:
        reasons.append("never analyzed")
    known = targets or []
    missing = [path for path in known if path in unanalyzed]
    if missing:
        reasons.append(f"{len(missing)} of {len(known)} targets unanalyzed")
    # Every file the family's own run reports an unresolved import for, a followed one
    # outside its targets included (CodeAnt on #459).
    partly = [path for path in partial if path not in unanalyzed]
    if reasons:
        analysis = "INCOMPLETE"
    elif partly:
        analysis = "PARTIAL"
    else:
        analysis = "COMPLETE"
    if partly:
        reasons.append(f"{len(partly)} files with unresolved imports")
    return {
        "family": family["id"],
        "producer": family["producer"],
        "analysis": analysis,
        # Unknown DIFF targets make the count unknown, never the known part's
        # (CodeAnt on #459); what was analyzed of the known part stays counted.
        "targets": None if targets is None or unknown is not None else len(known),
        "analyzed": None if targets is None else len(known) - len(missing),
        "reason": "; ".join(reasons) or None,
    }


# The pinned tool families (#389 H-PYSEC-2; Decision 0122). ShellCheck, Hadolint and actionlint run as their pinned
# release executables from the protected tool root, never from PATH or the analyzed tree, and each only after its bytes
# match the protected profile's pin for this machine. They run in a clean environment with the protected
# configuration, so nothing in the head selects their rules. A directive, a pragma, a sourced file, an unsupported
# construct or a report its exit status contradicts is an attributable gap of its family, never a clean result; every
# finding a run reports stays listed.
TOOL_ROOT = Path("/opt/gnostoa-tools")
# A pinned executable is read within this bound, as every read here is (Revix on #470): the largest pin, Hadolint
# 2.15.1, is about 56 MB.
_MAX_TOOL_BYTES = 256 * 1024 * 1024
_SHEBANG = re.compile(
    rb"#!\s*(?:/usr/bin/env\s+(?:-S\s+)?)?(?:\S*/)?([A-Za-z][\w.+-]*)"
)
_SHELLS = frozenset({"sh", "bash", "dash", "ksh"})
_OTHER_SHELLS = frozenset({"zsh", "fish", "csh", "tcsh", "mksh", "yash"})
_SHELLCHECK_DIRECTIVE = re.compile(r"#\s*shellcheck\s+[a-z][a-z-]*=", re.IGNORECASE)
_HADOLINT_PRAGMA = re.compile(r"#\s*hadolint\b", re.IGNORECASE)
_SOURCED = re.compile(r"^\s*(?:\.|source)\s+\S")
_WORKFLOW_PATH = re.compile(r"\.github/workflows/[^/]+\.ya?ml|ci/github[^/]*\.yml")
_GITLAB_PATH = re.compile(r"\.gitlab-ci\.yml|ci/gitlab[^/]*\.yml")
_STEP_SHELLS = frozenset({"bash", "sh"})
_HADOLINT_CONFIG = "override:\n  error:\n    - DL1001\n"
_ACTIONLINT_CONFIG = "self-hosted-runner:\n  labels: []\n"
_SHELLCHECK_FLAGS = (
    "--norc",
    "--format=json1",
    "--severity=style",
    "--extended-analysis=true",
)


def _first_line(root: Path, path: str) -> bytes:
    try:
        with (root / path).open("rb") as stream:
            return stream.readline(256)
    except OSError:
        return b""


_SHELL_SUFFIXES = frozenset({".sh", ".bash", ".dash", ".ksh"})
_OTHER_SHELL_SUFFIXES = frozenset({".zsh", ".fish", ".csh", ".tcsh", ".mksh", ".yash"})


def _shell_applicability(root: Path, path: str) -> tuple[bool, str | None]:
    """Whether ShellCheck reads `path`, and why not when it is another shell's script: a sh, bash, dash or ksh
    suffix, else a shebang naming one of them (cubic on #470)."""
    suffix = PurePosixPath(path).suffix
    if suffix in _SHELL_SUFFIXES:
        return True, None
    if suffix in _OTHER_SHELL_SUFFIXES:
        return False, f"{path}: an unsupported shell suffix {suffix!r}"
    match = _SHEBANG.match(_first_line(root, path))
    interpreter = match[1].decode("ascii", "replace") if match else None
    if interpreter in _SHELLS:
        return True, None
    if interpreter in _OTHER_SHELLS:
        return False, f"{path}: an unsupported interpreter {interpreter!r}"
    return False, None


_PATH_SELECTORS: dict[str, Callable[[str], bool]] = {
    "hadolint": lambda path: path.rsplit("/", 1)[-1].startswith("Dockerfile"),
    "actionlint": lambda path: _WORKFLOW_PATH.fullmatch(path) is not None,
    "gitlab-shellcheck": lambda path: _GITLAB_PATH.fullmatch(path) is not None,
    "secrets": lambda path: True,
}


def _applicable(
    root: Path, producer: str, tracked: list[str]
) -> tuple[list[str], dict[str, str]]:
    """The tracked paths a pinned-tool family applies to, in order, and the ones it names as unsupported. ShellCheck
    reads a sh, bash, dash or ksh script by its suffix or shebang; another shell's script is unsupported, a gap.
    Secrets read every tracked file."""
    selected: list[str] = []
    unsupported: dict[str, str] = {}
    for path in tracked:
        if producer == "shellcheck":
            chosen, why = _shell_applicability(root, path)
            if why is not None:
                unsupported[path] = why
        else:
            chosen = _PATH_SELECTORS[producer](path)
        if chosen:
            selected.append(path)
    return selected, unsupported


def _verified_tool(
    profile: Mapping[str, Any], name: str, target: Path
) -> tuple[Path | None, str | None]:
    """The pinned executable under TOOL_ROOT, copied into `target` once the pinned-file owner has read its bytes as
    the protected profile's pin for this machine, or why none may run: no pin, absent, a link, not a bounded regular
    file, or other bytes. The copy is what runs, so a replacement after the check never does (cubic on #470); its
    version is read only after this."""
    pin = profile.get("tools", {}).get(name)
    if pin is None:
        return None, f"tool {name}: no pin in the profile"
    digest = pin["sha256"].get(platform.machine())
    if digest is None:
        return None, f"tool {name}: no pin for this machine"
    from tools import security_scan

    try:
        data = security_scan.verified_pinned_bytes(
            Path(TOOL_ROOT), name, digest, _MAX_TOOL_BYTES, label=f"tool {name}"
        )
    except security_scan.SecurityScanError as exc:
        return None, str(exc)
    target.mkdir(exist_ok=True)
    copy = target / name
    descriptor = os.open(
        copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o500
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    return copy, None


def _tool_environment(run: Path) -> dict[str, str]:
    """A clean environment: no SHELLCHECK_OPTS, HADOLINT_* or other caller setting reaches a pinned tool, and its
    home and configuration directories are empty."""
    home = run / "tool-home"
    home.mkdir(exist_ok=True)
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home),
        "LC_ALL": "C.UTF-8",
    }


def _tool_version(
    tool: Path,
    name: str,
    run: Path,
    limits: DiagnosticLimits,
    deadline: float,
    pinned: str,
    *,
    family: str,
) -> str | None:
    """The pinned version when the tool's own version output names it, else None. Each family verifies its
    tools for itself, into a report of its own, since a report is always a new file (_bounded_run)."""
    report = run / f"diagnostic-{family}-{name}-version.txt"
    flag = "-version" if name == "actionlint" else "--version"
    status, gap, _invalid = _bounded_run(
        [str(tool), flag],
        cwd=run,
        environment=_tool_environment(run),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    if gap is not None or status != 0:
        return None
    try:
        text = report.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    return (
        pinned if re.search(rf"(?<![\w.]){re.escape(pinned)}(?![\w.])", text) else None
    )


def _tool_gap(status: int | None, gap: str | None, records: list[Any]) -> str | None:
    """A pinned tool's run gap: an earlier one, a run with no status (Amazon Q on #470), a status other than 0 or 1,
    or a status its report contradicts. Each of the three exits 1 only with a finding and 0 only without one."""
    if gap is not None:
        return gap
    if status is None:
        return "did not finish"
    if status not in (0, 1):
        return f"exited {status}"
    if status == 1 and not records:
        return "exited 1 without a finding record"
    if status == 0 and records:
        return "exited 0 with a finding record"
    return None


_SHELLCHECK_FIELDS = frozenset(
    {
        "file",
        "line",
        "endLine",
        "column",
        "endColumn",
        "level",
        "code",
        "message",
        "fix",
    }
)
_HADOLINT_FIELDS = frozenset({"code", "column", "file", "level", "line", "message"})
_ACTIONLINT_FIELDS = frozenset(
    {"message", "filepath", "line", "column", "kind", "snippet", "end_column"}
)


def _report_records(
    report: Path, fields: frozenset[str], key: str | None = None
) -> list[Any]:
    """A pinned tool's report, read strictly (Revix and cubic on #470): no duplicate key and no non-finite number,
    the pinned version's shape, and records carrying only its fields. Raises ValueError otherwise."""
    try:
        document = _strict_json_loads(report.read_text(encoding="utf-8"))
    except SecurityScanError as exc:
        raise ValueError(str(exc)) from exc
    if key is not None:
        if not isinstance(document, dict) or set(document) != {key}:
            raise ValueError("the report is not the pinned tool's")
        document = document[key]
    if not isinstance(document, list) or not all(
        isinstance(record, dict) and record.keys() <= fields for record in document
    ):
        raise ValueError("the report is not the pinned tool's")
    return document


def _text_lines(root: Path, path: str) -> list[str]:
    """The file's lines as the file counts them: universal newlines, then a split at newlines only, so a form feed
    or a Unicode separator never moves a line number (Revix on #470). A YAML reader counts its own: PyYAML also
    breaks at NEL, LS and PS, and then refuses the file or the reader refuses the scalar, a named gap (cubic)."""
    try:
        text = (root / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def _marked_lines(
    root: Path, path: str, pattern: re.Pattern[str], what: str
) -> list[str]:
    return [
        f"{path}:{n}: {what}"
        for n, line in enumerate(_text_lines(root, path), 1)
        if pattern.search(line)
    ]


def _run_shellcheck(
    cwd: Path,
    run: Path,
    paths: list[str],
    tool: Path,
    limits: DiagnosticLimits,
    deadline: float,
    allowance: int,
    *,
    name: str,
    tool_id: str = "shellcheck",
    shell: str | None = None,
    origin: Mapping[str, tuple[str, Mapping[int, Any]]] | None = None,
) -> _ProducerResult:
    """The pinned ShellCheck over `paths`, relative to `cwd`: `--norc`, no `-x`, explicit files. With `origin`, each
    analyzed file is an analysis copy whose lines map back to their source (the GitLab family)."""
    result = _ProducerResult()
    command = [
        str(tool),
        *_SHELLCHECK_FLAGS,
        *([f"--shell={shell}"] if shell else []),
        "--",
        *paths,
    ]
    report = run / f"diagnostic-{name.replace(':', '-')}.json"
    status, gap, invalid = _bounded_run(
        command,
        cwd=cwd,
        environment=_tool_environment(run),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    result.runs.append(_run_record(name, tool_id, command, status, report, run, None))
    result.truncated = result.truncated or invalid
    try:
        comments = _report_records(report, _SHELLCHECK_FIELDS, key="comments")
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        comments = []
        gap = gap or f"unparsable report: {type(exc).__name__}"
    for comment in comments:
        try:
            path, line = comment["file"], comment["line"]
            column, end_line, end_column = (
                comment["column"],
                comment.get("endLine"),
                comment.get("endColumn"),
            )
            if origin is not None:
                source, lines = origin[path]
                mapped = lines[line]
                if isinstance(mapped, list):
                    mapped = [target for start, target in mapped if start <= column][-1]
                path, line, end_line = source, mapped, None
            finding = _diagnostic_finding(
                tool_id,
                f"SC{comment['code']}",
                path,
                (line, column, end_line, end_column),
                comment["message"],
                {"level": comment["level"]},
            )
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            gap = gap or f"unparsable report: {type(exc).__name__}"
            continue
        result.keep(finding, allowance)
    gap = _tool_gap(status, gap, comments)
    if gap is not None:
        result.unanalyzed.update({path: f"{name} {gap}" for path in paths})
    return result


def _run_hadolint(
    root: Path,
    run: Path,
    paths: list[str],
    tool: Path,
    limits: DiagnosticLimits,
    deadline: float,
    allowance: int,
    *,
    name: str,
) -> _ProducerResult:
    """The pinned Hadolint, file by file, with the protected configuration given explicitly, pragmas disabled, and
    an empty working directory, so that no `.hadolint.yaml` in the head is found."""
    result = _ProducerResult()
    config = run / "hadolint.yaml"
    config.write_text(_HADOLINT_CONFIG, encoding="utf-8")
    cwd = run / "hadolint-cwd"
    cwd.mkdir(exist_ok=True)
    for index, path in enumerate(paths):
        command = [
            str(tool),
            "-c",
            str(config),
            "--disable-ignore-pragma",
            "-f",
            "json",
            str(root / path),
        ]
        report = run / f"diagnostic-{name.replace(':', '-')}-{index}.json"
        status, gap, invalid = _bounded_run(
            command,
            cwd=cwd,
            environment=_tool_environment(run),
            report=report,
            deadline=deadline,
            limits=limits,
        )
        result.runs.append(
            _run_record(name, "hadolint", command, status, report, run, None)
        )
        result.truncated = result.truncated or invalid
        try:
            records = _report_records(report, _HADOLINT_FIELDS)
        except (OSError, ValueError, RecursionError) as exc:
            records = []
            gap = gap or f"unparsable report: {type(exc).__name__}"
        for record in records:
            try:
                finding = _diagnostic_finding(
                    "hadolint",
                    record["code"],
                    path,
                    (record["line"], record["column"], None, None),
                    record["message"],
                    {"level": record["level"]},
                )
            except (ValueError, KeyError, TypeError) as exc:
                gap = gap or f"unparsable report: {type(exc).__name__}"
                continue
            result.keep(finding, allowance)
        gap = _tool_gap(status, gap, records)
        if gap is not None:
            result.unanalyzed[path] = f"{name} {gap}"
    return result


def _run_actionlint(
    root: Path,
    run: Path,
    paths: list[str],
    tool: Path,
    shellcheck: Path,
    limits: DiagnosticLimits,
    deadline: float,
    allowance: int,
    *,
    name: str,
) -> tuple[_ProducerResult, list[str]]:
    """The pinned actionlint, with the protected configuration file, the pinned ShellCheck and no pyflakes, over
    analysis copies in which only a validated `concurrency.queue` line is projected (project_concurrency_queue). A
    refused form is left for actionlint and named, a gap (cubic on #470)."""
    result = _ProducerResult()
    config = run / "actionlint.yaml"
    config.write_text(_ACTIONLINT_CONFIG, encoding="utf-8")
    copies = run / "actionlint-input"
    refusals: list[str] = []
    for path in paths:
        text, _projected, refused = project_concurrency_queue(
            "\n".join(_text_lines(root, path)) + "\n"
        )
        (copies / path).parent.mkdir(parents=True, exist_ok=True)
        (copies / path).write_text(text, encoding="utf-8")
        refusals += [
            f"{path}:{line}: {detail}, left for actionlint"
            if line
            else f"{path}: {detail}"
            for line, detail in refused
        ]
    command = [
        str(tool),
        "-config-file",
        str(config),
        "-shellcheck",
        str(shellcheck),
        "-pyflakes=",
        "-format",
        "{{json .}}",
        *paths,
    ]
    report = run / f"diagnostic-{name.replace(':', '-')}.json"
    status, gap, invalid = _bounded_run(
        command,
        cwd=copies,
        environment=_tool_environment(run),
        report=report,
        deadline=deadline,
        limits=limits,
    )
    result.runs.append(
        _run_record(name, "actionlint", command, status, report, run, None)
    )
    result.truncated = result.truncated or invalid
    try:
        records = _report_records(report, _ACTIONLINT_FIELDS)
    except (OSError, ValueError, RecursionError) as exc:
        records = []
        gap = gap or f"unparsable report: {type(exc).__name__}"
    for record in records:
        try:
            embedded = (
                re.search(r"\bSC\d+\b", record["message"])
                if record["kind"] == "shellcheck"
                else None
            )
            finding = _diagnostic_finding(
                "actionlint",
                embedded[0] if embedded else record["kind"],
                record["filepath"],
                (record["line"], record["column"], None, None),
                record["message"],
                {"kind": record["kind"]},
            )
        except (ValueError, KeyError, TypeError) as exc:
            gap = gap or f"unparsable report: {type(exc).__name__}"
            continue
        result.keep(finding, allowance)
    gap = _tool_gap(status, gap, records)
    if gap is not None:
        result.unanalyzed.update({path: f"{name} {gap}" for path in paths})
    return result, refusals


def _run_shell(container: Mapping[str, Any]) -> Any:
    """`defaults.run.shell` of a workflow or job mapping, None when absent."""
    defaults = container.get("defaults")
    run = defaults.get("run") if isinstance(defaults, dict) else None
    return run.get("shell") if isinstance(run, dict) else None


def _structure_notes(path: str, where: str, container: Mapping[str, Any]) -> list[str]:
    """Each of `defaults` and `defaults.run` present but not a mapping: its step shells cannot be read (Codex, Revix
    and cubic on #470)."""
    defaults = container.get("defaults")
    if defaults is not None and not isinstance(defaults, dict):
        return [
            f"{path}: {where}defaults is not a mapping, so its step shells are not read"
        ]
    run = defaults.get("run") if isinstance(defaults, dict) else None
    if run is not None and not isinstance(run, dict):
        return [
            f"{path}: {where}defaults.run is not a mapping, so its step shells are not read"
        ]
    return []


def _step_note(path: str, job_id: str, index: int, shell: Any) -> list[str]:
    if shell is _UNKNOWN_SHELL:
        return [
            f"{path}: job {job_id} step {index} uses the runner's default shell, which runs-on does not name, never analyzed"
        ]
    if not isinstance(shell, str) or not shell.split():
        return [
            f"{path}: job {job_id} step {index} names an empty shell, or one that is not text, never analyzed"
        ]
    if shell.split()[0] not in _STEP_SHELLS:
        return [
            f"{path}: job {job_id} step {index} runs under {shell!r}, never analyzed"
        ]
    return []


def _job_step_notes(
    path: str, job_id: str, job: Mapping[str, Any], workflow_shell: Any
) -> list[str]:
    notes = _structure_notes(path, f"job {job_id} ", job)
    steps = job.get("steps")
    if steps is not None and not isinstance(steps, list):
        return [
            *notes,
            f"{path}: job {job_id} steps is not a list, so its step shells are not read",
        ]
    job_shell = _run_shell(job)
    for index, step in enumerate(steps or []):
        if isinstance(step, dict) and "run" in step:
            notes += _step_note(
                path,
                job_id,
                index,
                step.get("shell") or job_shell or workflow_shell or _runner_shell(job),
            )
    return notes


# The runner's default shell when `runs-on` names no platform (Revix on #470).
_UNKNOWN_SHELL = object()


def _runner_shell(job: Mapping[str, Any]) -> object:
    """The runner's default shell for a step that names none: pwsh on a Windows runner, bash on a Linux or macOS
    one, and unknown otherwise: an expression, a group or a bare self-hosted label can be any (Revix and cubic on
    #470). Only bash and sh are analyzed."""
    runs_on = job.get("runs-on")
    if isinstance(runs_on, dict):
        runs_on = runs_on.get("labels")
    if isinstance(runs_on, str):
        runs_on = [runs_on]
    labels = runs_on if isinstance(runs_on, list) else []
    texts = [label.lower() for label in labels if isinstance(label, str)]
    if not any("${{" in label for label in texts):
        if any(label.startswith("windows") for label in texts):
            return "pwsh"
        if any(label.startswith(("ubuntu", "macos", "linux")) for label in texts):
            return "bash"
    return _UNKNOWN_SHELL


def _step_shell_notes(root: Path, path: str) -> list[str]:
    """Each workflow step whose effective shell is not bash or sh: actionlint gives it to no analyzer, so it is a
    gap. The step's, then the job's, then the workflow's `defaults.run.shell` decide; a runner's default is bash. A
    structure that is not the documented mapping is a gap too, and actionlint still reads the file."""
    import yaml

    try:
        document = yaml.load("\n".join(_text_lines(root, path)), Loader=yaml.BaseLoader)
    except (yaml.YAMLError, RecursionError):
        # A nesting past the reader's depth is a gap, never a crash (Revix on #470).
        return [f"{path}: the workflow cannot be read for its step shells"]
    if document is None:
        return []
    if not isinstance(document, dict):
        return [
            f"{path}: the workflow is not a mapping, so its step shells are not read"
        ]
    notes = _structure_notes(path, "", document)
    jobs = document.get("jobs")
    if jobs is not None and not isinstance(jobs, dict):
        return [
            *notes,
            f"{path}: jobs is not a mapping, so its step shells are not read",
        ]
    for job_id, job in (jobs or {}).items():
        if isinstance(job, dict):
            notes += _job_step_notes(path, job_id, job, _run_shell(document))
        else:
            notes.append(
                f"{path}: job {job_id} is not a mapping, so its step shells are not read"
            )
    return notes


class _GitlabUnsupported(ValueError):
    """A GitLab CI construct the bounded reader does not resolve: an attributable gap."""


_GITLAB_RESERVED = frozenset(
    {
        "stages",
        "workflow",
        "variables",
        "default",
        "include",
        "image",
        "services",
        "before_script",
        "after_script",
        "cache",
    }
)


_GITLAB_SCALARS = frozenset(
    {"tag:yaml.org,2002:" + name for name in ("str", "int", "bool", "null", "float")}
)


def _gitlab_folded(node: Any, line: int) -> tuple[str, list[tuple[int, int]]]:
    """A simple folded item (non-empty, equally indented lines, each break folded to one space), with each column's
    YAML line; anything else has no exact map."""
    stop = node.end_mark.line + (1 if node.end_mark.column else 0)
    raw = node.start_mark.buffer.rstrip("\0").split("\n")[
        node.start_mark.line + 1 : stop
    ]
    while raw and raw[-1] == "":
        raw.pop()
    parts = [r.strip() for r in raw]
    simple = (
        bool(raw)
        and all(parts)
        and len({len(r) - len(r.lstrip(" ")) for r in raw}) == 1
        and node.value.rstrip("\n") == " ".join(parts)
        and node.value.count("\n") <= 1
    )
    if not simple:
        raise _GitlabUnsupported(f"a folded item with no exact line map at line {line}")
    spans, column = [], 1
    for offset, part in enumerate(parts):
        spans.append((column, line + 1 + offset))
        column += len(part) + 1
    return node.value.rstrip("\n"), spans


def _gitlab_scalar(node: Any) -> Any:
    import yaml

    if node.tag not in _GITLAB_SCALARS:
        raise _GitlabUnsupported(
            f"an unsupported tag {node.tag} at line {node.start_mark.line + 1}"
        )
    if node.tag != "tag:yaml.org,2002:str":
        try:
            return yaml.SafeLoader("").construct_object(node)
        except (ValueError, yaml.YAMLError) as exc:
            # A tag whose text it cannot read, as `!!int x` (Revix on #470).
            raise _GitlabUnsupported(
                f"a {node.tag} item that cannot be read at line {node.start_mark.line + 1}"
            ) from exc
    line = node.start_mark.line + 1
    if node.style == "|":
        return (node.value, line + 1)
    if node.style == ">":
        return _gitlab_folded(node, line)
    if "\n" in node.value or node.start_mark.line != node.end_mark.line:
        raise _GitlabUnsupported(f"a multi-line flow item at line {line}")
    return (node.value, line)


def _gitlab_construct(node: Any) -> Any:
    """The document's value, each script string with its YAML line, refusing what the reader does not resolve."""
    import yaml

    if isinstance(node, yaml.ScalarNode):
        return _gitlab_scalar(node)
    if node.tag not in ("tag:yaml.org,2002:seq", "tag:yaml.org,2002:map"):
        # A tagged collection, as `!reference [.job, script]`, is unsupported as a tagged scalar is (Revix on #470).
        raise _GitlabUnsupported(
            f"an unsupported tag {node.tag} at line {node.start_mark.line + 1}"
        )
    if isinstance(node, yaml.SequenceNode):
        return [_gitlab_construct(v) for v in node.value]
    if not isinstance(node, yaml.MappingNode):
        raise _GitlabUnsupported("an unsupported node")
    out = {}
    for key, value in node.value:
        text = _gitlab_construct(key)
        text = text[0] if isinstance(text, tuple) else text
        if text == "<<":
            raise _GitlabUnsupported(
                f"a YAML merge key at line {key.start_mark.line + 1}"
            )
        out[text] = _gitlab_construct(value)
    return out


def _gitlab_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in over.items():
        merged[key] = (
            _gitlab_merge(merged[key], value)
            if isinstance(value, dict) and isinstance(merged.get(key), dict)
            else value
        )
    return merged


def _gitlab_resolve(
    name: str, jobs: Mapping[str, Any], seen: tuple[str, ...] = ()
) -> dict[str, Any]:
    if name in seen:
        raise _GitlabUnsupported(f"an extends cycle at {name}")
    if len(seen) > 11 or name not in jobs:
        raise _GitlabUnsupported(f"extends names {name!r}, not a local job")
    job = jobs[name]
    if "inherit" in job:
        raise _GitlabUnsupported(f"inherit in {name}")
    parents = job.get("extends")
    own = {k: v for k, v in job.items() if k != "extends"}
    if parents is None:
        return own
    parents = [parents] if isinstance(parents, tuple) else parents
    if not isinstance(parents, list) or not all(isinstance(p, tuple) for p in parents):
        raise _GitlabUnsupported(f"a malformed extends in {name}")
    merged: dict[str, Any] = {}
    for parent in parents:
        merged = _gitlab_merge(merged, _gitlab_resolve(parent[0], jobs, (*seen, name)))
    return _gitlab_merge(merged, own)


def _gitlab_items(value: Any, where: str) -> list[tuple[str, Any]]:
    if value is None:
        return []
    items = [value] if isinstance(value, tuple) else value
    if not isinstance(items, list):
        raise _GitlabUnsupported(f"{where} is neither a string nor a list")
    out: list[tuple[str, Any]] = []
    for item in items:
        if isinstance(item, tuple):
            out.append(item)
        elif isinstance(item, list) and all(isinstance(i, tuple) for i in item):
            out.extend(item)
        else:
            raise _GitlabUnsupported(f"{where} has a non-string or deeper item")
    return out


def _gitlab_job(
    name: str, jobs: Mapping[str, Any], default: Mapping[str, Any]
) -> list[list[tuple[str, Any]]] | None:
    """A job's shells, `before_script` + `script` as one and `after_script` as the other; None without a script."""
    job = _gitlab_resolve(name, jobs)
    if "script" not in job:
        return None
    main = _gitlab_items(
        job.get("before_script", default.get("before_script")), f"{name}.before_script"
    )
    main += _gitlab_items(job.get("script"), f"{name}.script")
    after = _gitlab_items(
        job.get("after_script", default.get("after_script")), f"{name}.after_script"
    )
    return [part for part in (main, after) if part]


def _gitlab_defaults(root: Mapping[str, Any]) -> dict[str, Any]:
    """`default`, with a top-level before_script or after_script read as a default's, since the runner runs them as
    one (Codex on #470); both at once, or an `inherit`, is unsupported."""
    default = root.get("default") or {}
    if not isinstance(default, dict) or "inherit" in default:
        raise _GitlabUnsupported("an unsupported default")
    for key in ("before_script", "after_script"):
        if key in root and key in default:
            raise _GitlabUnsupported(f"both a top-level and a default {key}")
        default = {**default, key: root[key]} if key in root else default
    return default


def _gitlab_scripts(text: str) -> dict[str, list[list[tuple[str, Any]]]]:
    """The bounded GitLab CI reader: per job, its shells, each item with its YAML line (a column table for a simple
    folded item). Local `extends` (GitLab's merge), `default` and anchors are resolved; include, `!reference`,
    `inherit`, cycles, merge keys, more than one document and unmappable items raise _GitlabUnsupported."""
    import yaml

    try:
        nodes = list(yaml.compose_all(text, Loader=yaml.SafeLoader))
    except (yaml.YAMLError, RecursionError) as exc:
        raise _GitlabUnsupported(f"unparsable: {type(exc).__name__}") from exc
    if len(nodes) != 1:
        raise _GitlabUnsupported(f"{len(nodes)} documents")
    root = _gitlab_construct(nodes[0])
    if not isinstance(root, dict) or "include" in root:
        raise _GitlabUnsupported(
            "include" if isinstance(root, dict) else "the document is not a mapping"
        )
    default = _gitlab_defaults(root)
    jobs = {
        k: v
        for k, v in root.items()
        if k not in _GITLAB_RESERVED and isinstance(v, dict)
    }
    scripts = {}
    for name in jobs:
        shells = None if name.startswith(".") else _gitlab_job(name, jobs, default)
        if shells is not None:
            scripts[name] = shells
    return scripts


def _gitlab_analysis_file(items: list[tuple[str, Any]]) -> tuple[str, dict[int, Any]]:
    """An analysis-only POSIX sh file and its map from each analysis line to a YAML line (or a column table)."""
    body, mapping = ["#!/bin/sh"], {}
    for text, line in items:
        if isinstance(line, list):
            body.append(text)
            mapping[len(body)] = line
            continue
        # Only a newline ends an analysis line, so the shell reads the item as it is (Codex on #470).
        parts = text.split("\n")
        if len(parts) > 1 and parts[-1] == "":
            parts.pop()
        for offset, part in enumerate(parts):
            body.append(part)
            mapping[len(body)] = line + offset
    return "\n".join(body) + "\n", mapping


def _gitlab_sourced(path: str, items: list[tuple[str, Any]]) -> list[str]:
    """Each line of a job's items that sources a file, which ShellCheck never follows here either (Claude on #470)."""
    notes = []
    for text, line in items:
        first = line if isinstance(line, int) else line[0][1]
        for offset, part in enumerate(text.split("\n")):
            if _SOURCED.match(part):
                notes.append(f"{path}:{first + offset}: a sourced file, never followed")
    return notes


def _run_gitlab(
    root: Path,
    run: Path,
    paths: list[str],
    tool: Path,
    limits: DiagnosticLimits,
    deadline: float,
    allowance: int,
    *,
    name: str,
) -> tuple[_ProducerResult, list[str]]:
    """The GitLab family: each file's jobs read by the bounded reader into analysis files, analyzed by the pinned
    ShellCheck as POSIX sh, each finding mapped back to its YAML line. An unsupported file is a gap, named."""
    copies = run / "gitlab-input"
    copies.mkdir(exist_ok=True)
    origin: dict[str, tuple[str, Mapping[int, Any]]] = {}
    notes: list[str] = []
    for index, path in enumerate(paths):
        try:
            jobs = _gitlab_scripts("\n".join(_text_lines(root, path)) + "\n")
        except _GitlabUnsupported as exc:
            notes.append(f"{path}: {exc}")
            continue
        except RecursionError:
            notes.append(f"{path}: nested past the reader's depth")
            continue
        # The job's index keeps two names that sanitize alike apart (Codex and cubic on #470).
        for job_index, (job, parts) in enumerate(jobs.items()):
            for part_index, items in enumerate(parts):
                notes += _gitlab_sourced(path, items)
                body, mapping = _gitlab_analysis_file(items)
                analysis = f"{index}-{job_index}-{re.sub(r'[^A-Za-z0-9_.-]', '_', job)}-{part_index}.sh"
                (copies / analysis).write_text(body, encoding="utf-8")
                origin[analysis] = (path, mapping)
    if not origin:
        return _ProducerResult(), notes
    result = _run_shellcheck(
        copies,
        run,
        sorted(origin),
        tool,
        limits,
        deadline,
        allowance,
        name=name,
        tool_id="gitlab-shellcheck",
        shell="sh",
        origin=origin,
    )
    result.unanalyzed = {origin[a][0]: why for a, why in result.unanalyzed.items()}
    return result, notes


_QUEUE_LINE = re.compile(r"^(\s*)queue:\s*([A-Za-z]+)\s*(?:#.*)?$")


def _yaml_values(node: Any, key: str) -> list[tuple[Any, Any]]:
    import yaml

    return [
        (k, v)
        for k, v in node.value
        if isinstance(k, yaml.ScalarNode) and k.value == key
    ]


def _concurrency_nodes(root: Any) -> list[tuple[str, Any]]:
    """The `concurrency` values at the workflow root and at `jobs.<job_id>`, structurally."""
    import yaml

    if not isinstance(root, yaml.MappingNode):
        return []
    found = [("workflow", v) for _, v in _yaml_values(root, "concurrency")]
    for _, jobs in _yaml_values(root, "jobs"):
        if isinstance(jobs, yaml.MappingNode):
            for job_key, job in jobs.value:
                if isinstance(job, yaml.MappingNode):
                    found += [
                        (f"job {job_key.value}", v)
                        for _, v in _yaml_values(job, "concurrency")
                    ]
    return found


def _queue_cancel_allows(node: Any) -> bool:
    """Whether `queue: max` may stand beside this mapping's `cancel-in-progress`: only a literal false, or none."""
    import yaml

    cancel = _yaml_values(node, "cancel-in-progress")
    if not cancel:
        return True
    value = cancel[0][1]
    return (
        isinstance(value, yaml.ScalarNode)
        and value.tag == "tag:yaml.org,2002:bool"
        and value.value.lower() == "false"
    )


def _queue_decision(where: str, node: Any, lines: list[str]) -> tuple[int, str, bool]:
    """(line index, value or refusal reason, projected) for a mapping holding `queue`."""
    import yaml

    queues = _yaml_values(node, "queue")
    if node.flow_style:
        return node.start_mark.line, f"{where}: flow-style concurrency", False
    if len(queues) > 1:
        return queues[1][0].start_mark.line, f"{where}: duplicate queue", False
    key, value = queues[0]
    number = key.start_mark.line
    plain = (
        isinstance(value, yaml.ScalarNode)
        and value.style in (None, "")
        and value.start_mark.line == number
    )
    form = _QUEUE_LINE.match(lines[number]) if plain else None
    if form is None or form[2] != value.value:
        return number, f"{where}: queue is not a plain value alone on its line", False
    if value.value not in ("single", "max"):
        return number, f"{where}: an undocumented queue value {value.value!r}", False
    if value.value == "max" and not _queue_cancel_allows(node):
        return (
            number,
            f"{where}: queue: max with cancel-in-progress not literally false",
            False,
        )
    return number, value.value, True


def project_concurrency_queue(
    text: str,
) -> tuple[str, list[tuple[int, str]], list[tuple[int, str]]]:
    """The analysis-only projection of GitHub's documented `concurrency.queue` for actionlint 1.7.12, which does not
    know the key (#389 6503958085, Router 6503869789). Only a `queue` key of a block-style `concurrency` mapping at the
    workflow root or at `jobs.<job_id>`, with a plain `single` or `max` value alone on its line, is projected: that one
    line becomes a comment at its indentation, so the line count and every other byte are unchanged. `max` with a
    `cancel-in-progress` other than a literal false, a flow-style mapping, a duplicate, another value or any other
    form is refused and left as it is, for actionlint to report. Returns (text, projected, refused), 1-based lines."""
    import yaml

    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except (yaml.YAMLError, RecursionError) as exc:
        return text, [], [(0, f"unparsable: {type(exc).__name__}")]
    lines = text.split("\n")
    projected: list[tuple[int, str]] = []
    refused: list[tuple[int, str]] = []
    for where, node in _concurrency_nodes(root):
        if isinstance(node, yaml.MappingNode) and _yaml_values(node, "queue"):
            index, detail, accepted = _queue_decision(where, node, lines)
            (projected if accepted else refused).append((index + 1, detail))
    for line, _value in projected:
        source = lines[line - 1]
        lines[line - 1] = (
            f"{source[: len(source) - len(source.lstrip())]}# gnostoa-projected: {source.strip()}"
        )
    return "\n".join(lines), projected, refused


_DIRECTIVE_NOTE = "a ShellCheck directive, never honoured as clean"


def _tool_notes(root: Path, producer: str, paths: list[str]) -> list[str]:
    """Each attributable gap a pinned tool's inputs carry, read before it runs: directives, sources, pragmas and
    step shells."""
    notes: list[str] = []
    for path in paths:
        notes += _marked_lines(root, path, _SHELLCHECK_DIRECTIVE, _DIRECTIVE_NOTE)
        if producer == "shellcheck":
            notes += _marked_lines(
                root, path, _SOURCED, "a sourced file, never followed"
            )
        elif producer == "hadolint":
            notes += _marked_lines(
                root,
                path,
                _HADOLINT_PRAGMA,
                "a Hadolint pragma, never honoured as clean",
            )
        elif producer == "actionlint":
            notes += _step_shell_notes(root, path)
    return notes


def _verified_tools(
    profile: Mapping[str, Any],
    family: Mapping[str, Any],
    run: Path,
    limits: DiagnosticLimits,
    deadline: float,
) -> tuple[dict[str, Path], str | None]:
    """Each of the family's pinned executables, verified and copied into this run, then its version read from that
    copy; or why none may run."""
    tools: dict[str, Path] = {}
    target = run / f"tools-{family['id']}"
    for tool_name in _TOOL_PRODUCER_TOOLS[family["producer"]]:
        tool, why = _verified_tool(profile, tool_name, target)
        if tool is not None:
            pinned = profile["tools"][tool_name]["version"]
            version = _tool_version(
                tool, tool_name, run, limits, deadline, pinned, family=family["id"]
            )
            if version is None:
                why = f"tool {tool_name}: its version is not its pin {pinned!r}"
        if why is not None or tool is None:
            return {}, why
        tools[tool_name] = tool
    return tools, None


def _run_tool_family(
    root: Path,
    run: Path,
    profile: Mapping[str, Any],
    family: Mapping[str, Any],
    paths: list[str],
    limits: DiagnosticLimits,
    deadline: float,
    allowance: int,
) -> tuple[_ProducerResult, list[str]]:
    """A pinned-tool family over `paths`: each executable verified, then its version, before anything runs; then the
    run and its attributable notes (directives, pragmas, sources, unsupported step shells or constructs)."""
    producer, name = family["producer"], f"{family['producer']}:{family['id']}"
    tools, why = _verified_tools(profile, family, run, limits, deadline)
    if why is not None:
        return _ProducerResult(unanalyzed=dict.fromkeys(paths, f"{name}: {why}")), []
    notes = _tool_notes(root, producer, paths)
    common = (limits, deadline, allowance)
    if producer == "shellcheck":
        return _run_shellcheck(
            root, run, paths, tools["shellcheck"], *common, name=name
        ), notes
    if producer == "hadolint":
        return _run_hadolint(
            root, run, paths, tools["hadolint"], *common, name=name
        ), notes
    if producer == "actionlint":
        result, refused = _run_actionlint(
            root,
            run,
            paths,
            tools["actionlint"],
            tools["shellcheck"],
            *common,
            name=name,
        )
        return result, notes + refused
    result, unsupported = _run_gitlab(
        root, run, paths, tools["shellcheck"], *common, name=name
    )
    return result, notes + unsupported


def _with_notes(row: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    """A v2 family's row with its attributable gaps: what it read but cannot vouch for makes a COMPLETE row
    PARTIAL, and each one is named."""
    if not notes:
        return row
    if row["analysis"] == "COMPLETE":
        row["analysis"] = "PARTIAL"
    row["reason"] = "; ".join([r for r in (row["reason"],) if r] + notes)
    return row


_PROTECTED_BASELINE = _PRODUCER_TREE / ".secrets.baseline"


def _scoped_baseline(run: Path, paths: list[str]) -> Path:
    """The producer tree's reviewed baseline, restricted to the files this scan reads: a reviewed entry for a file the
    head does not carry is not stale, while one for a file it carries and changed still is. Its settings are kept
    whole, so the scanner's exact settings equality still holds (Router #389 6508695016)."""
    from tools.security_scan import _strict_json_loads

    document = _strict_json_loads(_PROTECTED_BASELINE.read_bytes())
    results = document.get("results") if isinstance(document, dict) else None
    if not isinstance(results, dict):
        # A malformed protected baseline is refused, never read as one with nothing reviewed (Amazon Q on #470).
        raise SecurityScanError("the reviewed baseline has no results mapping")
    scanned = set(paths)
    document["results"] = {
        name: rows for name, rows in results.items() if name in scanned
    }
    scoped = run / "secrets-baseline.json"
    scoped.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return scoped


def _secrets_identity(run: Path, version: str) -> Path:
    """What the scan was held to, as its run record's report: the scanner and the version the protected baseline
    holds it to, that baseline's digest, and each protected plugin's pin (Router 6510622435 on #389)."""
    from tools import security_scan

    identity = run / "diagnostic-secrets-identity.json"
    identity.write_text(
        canonical_json(
            {
                "scanner": "detect-secrets",
                "version": version,
                "baseline_sha256": hashlib.sha256(
                    _PROTECTED_BASELINE.read_bytes()
                ).hexdigest(),
                "plugins": {
                    name: pin
                    for name, (_path, pin) in security_scan.PLUGIN_PINS.items()
                },
            }
        ),
        encoding="utf-8",
    )
    return identity


def _run_secrets(
    root: Path,
    run: Path,
    paths: list[str],
    limits: DiagnosticLimits,
    deadline: float,
    allowance: int,
) -> tuple[_ProducerResult, list[str]]:
    """The secrets family: the project's own scanner over the head's files as data, against the protected reviewed
    baseline, then each protected plugin over the same files. A candidate's path, line and type are listed, never
    its value; a scanner failure leaves every file unanalyzed, named."""
    from tools import security_scan

    del limits
    if time.monotonic() >= deadline:
        # A spent budget starts nothing, as _bounded_run (Amazon Q and cubic on #470); the scan itself is bounded
        # by the scanner's own timeout.
        reason = "secrets: not started: the inventory deadline had passed"
        return _ProducerResult(unanalyzed=dict.fromkeys(paths, reason)), []
    result = _ProducerResult()
    try:
        baseline = _scoped_baseline(run, paths)
        scan = security_scan.scan_tracked_tree(
            root,
            tracked_paths=[Path(path) for path in paths],
            baseline_path=baseline,
        )
        planted, unread = security_scan.scan_with_protected_plugins(root, paths)
        # The scan refuses any settings but the protected baseline's, so that is the version it was held to.
        version = str(json.loads(baseline.read_text(encoding="utf-8"))["version"])
    except Exception as exc:
        # The scanner's own refusals are its classifications, never an exception's text or a filename
        # (tools/security_scan.py); any other failure is named by its type alone (Amazon Q, Revix and cubic on #470).
        detail = f": {exc}" if isinstance(exc, security_scan.SecurityScanError) else ""
        reason = f"secrets: {type(exc).__name__}{detail}"
        return _ProducerResult(unanalyzed=dict.fromkeys(paths, reason)), []
    result.runs.append(
        _run_record(
            "secrets", "secrets", [], 0, _secrets_identity(run, version), run, version
        )
    )
    for record in [*scan.unresolved_findings, *planted]:
        finding = _diagnostic_finding(
            "secrets",
            str(record["type"]),
            str(record["path"]),
            (int(record["line"]), 1, None, None),
            f"a secret candidate ({record['type']})",
            {},
        )
        result.keep(finding, allowance)
    if not unread:
        return result, []
    plural = "" if len(unread) == 1 else "s"
    return result, [
        f"secrets: {len(unread)} file{plural} holding NUL bytes, never read by the protected plugins, "
        f"first {unread[0]}"
    ]


def _unanalyzed_notes(unanalyzed: Mapping[str, str]) -> list[str]:
    """Each reason a v2 family's targets went unanalyzed, with how many and the first of them: its row is the only
    place they are recorded, since they are not tracked Python files, and a count alone attributes nothing."""
    by_reason: dict[str, list[str]] = {}
    for target, reason in sorted(unanalyzed.items()):
        by_reason.setdefault(reason, []).append(target)
    return [
        f"{reason} ({len(targets)} target{'' if len(targets) == 1 else 's'}, first {targets[0]})"
        for reason, targets in sorted(by_reason.items())
    ]


def _run_v2_family(
    root: Path,
    run: Path,
    profile: Mapping[str, Any],
    family: Mapping[str, Any],
    tracked: list[str] | None,
    limits: DiagnosticLimits,
    deadline: float,
    changes: _Changes,
    result: _ProducerResult,
) -> None:
    """A v2 family, planned over its own applicable tracked paths and rowed with its notes. Its unanalyzed paths stay
    in its own row, since they are not tracked Python files."""
    if tracked is None:
        result.families.append(_family_row(family, None, {}, {}, None))
        return
    applicable, unsupported = _applicable(root, family["producer"], tracked)
    targets, _functions, unknown = _family_targets(profile, family, applicable, changes)
    # Only what the family's scopes select can downgrade its row (Codex on #470).
    selected_unsupported = _family_targets(
        profile, family, sorted(unsupported), changes
    )[0]
    unsupported = {path: unsupported[path] for path in selected_unsupported}
    withheld = _withheld(root, targets, limits)
    selected = [path for path in targets if path not in withheld]
    notes = sorted(unsupported.values())
    outcome = _ProducerResult()
    if selected and family["producer"] == "secrets":
        outcome, extra = _run_secrets(
            root, run, selected, limits, deadline, limits.max_findings - result.count()
        )
        notes += extra
    elif selected:
        outcome, extra = _run_tool_family(
            root,
            run,
            profile,
            family,
            selected,
            limits,
            deadline,
            limits.max_findings - result.count(),
        )
        notes += extra
    local = {**withheld, **outcome.unanalyzed}
    outcome.unanalyzed = {}
    notes += _unanalyzed_notes(local)
    result.families.append(
        _with_notes(_family_row(family, targets, local, {}, unknown), notes)
    )
    result.merge(outcome)


def _run_all_families(
    root: Path,
    run: Path,
    expected: list[str],
    limits: DiagnosticLimits,
    gaps: list[str],
    deadline: float,
    profile: Mapping[str, Any],
    changes: _Changes,
    tracked: list[str] | None,
) -> _ProducerResult:
    """The active Python families through _run_producers, unchanged, then each active v2 family over its own
    applicable tracked paths (#389 H-PYSEC-2). An inactive family runs nothing."""
    active = _active_families(profile)
    python_profile = {
        **profile,
        "families": [f for f in active if f["producer"] not in _V2_PRODUCERS_NAMES],
    }
    result = _run_producers(
        root, run, expected, limits, gaps, deadline, python_profile, changes
    )
    for family in sorted(active, key=lambda f: _PRODUCER_ORDER.index(f["producer"])):
        if (
            family["producer"] in _V2_PRODUCERS_NAMES
            and result.count() <= limits.max_findings
        ):
            _run_v2_family(
                root, run, profile, family, tracked, limits, deadline, changes, result
            )
    return result


def _run_family(
    root: Path,
    run: Path,
    family: Mapping[str, Any],
    paths: list[str],
    functions: Mapping[str, list[int]],
    limits: DiagnosticLimits,
    deadline: float,
    versions: Mapping[str, str | None],
    allowance: int,
) -> _ProducerResult:
    """The family's producer, with its own selection, over `paths`."""
    if family["producer"] == "mypy":
        return _run_mypy(root, run, paths, limits, deadline, versions["mypy"])
    if family["producer"] == "ruff":
        return _run_ruff(
            root,
            run,
            paths,
            limits,
            deadline,
            versions["ruff"],
            allowance,
            select=family["select"],
            name=f"ruff:{family['id']}",
        )
    return _run_complexity(
        root,
        paths,
        deadline,
        max_source_bytes=limits.max_source_bytes,
        max_findings=allowance,
        reported_above=family["reported_above"],
        functions=functions,
    )


def _withheld(
    root: Path, expected: list[str], limits: DiagnosticLimits
) -> dict[str, str]:
    """The tracked paths no producer may read, each with why: a symlink, whose content
    may lie outside the tree; one that is not a regular file; and one larger than the
    one source bound every producer shares (CodeAnt on #436)."""
    withheld: dict[str, str] = {}
    for path in expected:
        if _symlinked(root, path):
            withheld[path] = "a symlink, never analyzed"
        elif not _regular_file(root, path):
            withheld[path] = "missing or not a regular file, never analyzed"
        elif _source_size(root, path) > limits.max_source_bytes:
            withheld[path] = (
                f"larger than {limits.max_source_bytes} bytes, never analyzed"
            )
    return withheld


def _run_producers(
    root: Path,
    run: Path,
    expected: list[str],
    limits: DiagnosticLimits,
    gaps: list[str],
    deadline: float,
    profile: Mapping[str, Any],
    changes: _Changes,
) -> _ProducerResult:
    """Each of the profile's families over its own targets, among the analyzable tracked
    Python set: never a symlinked path, whose content may lie outside the tree, and
    nothing when over budget. What runs on which file is decided here, before any
    producer starts, never by dropping what one obtained (#389 A0-MP1)."""
    result = _ProducerResult()
    plans = [
        (family, *_family_targets(profile, family, expected, changes))
        for family in sorted(
            profile["families"], key=lambda f: _PRODUCER_ORDER.index(f["producer"])
        )
    ]
    if len(expected) > limits.max_files:
        gaps.append(
            f"budget: {len(expected)} tracked Python files exceed max_files {limits.max_files}"
        )
        result.unanalyzed = dict.fromkeys(expected, "budget: not analyzed")
        result.families = [
            _family_row(family, targets, result.unanalyzed, {}, unknown)
            for family, targets, _, unknown in plans
        ]
        return result
    result.unanalyzed = _withheld(root, expected, limits)
    # Never analyzed, so a finding a producer reaches one by is out of scope too
    # (cubic on #436).
    withheld = set(result.unanalyzed)
    paths = [path for path in expected if path not in result.unanalyzed]
    unread = dict(result.unanalyzed)
    analyzable = set(paths)
    used = {
        family["producer"]
        for family, targets, _, _ in plans
        if analyzable.intersection(targets)
    }
    # Only a launched producer's environment is observed: the metric runs in process,
    # so a profile without one observes nothing (CodeAnt on #459).
    launched = [producer for producer in _LAUNCHED_PRODUCERS if producer in used]
    versions: dict[str, str | None] = {}
    before: tuple[dict[str, Any] | None, dict[str, Any] | None] = (None, None)
    if launched:
        before = _observe_environment(root, run, limits, deadline, "before")
        versions = {
            producer: _producer_version(root, run, producer, limits, deadline)
            for producer in launched
        }
    for family, targets, functions, unknown in plans:
        # The existing refusal's predicate, the raw count above max_findings: once it
        # holds, no later family starts, and that refusal follows (cubic on #436).
        if result.count() > limits.max_findings:
            break
        # A complexity target whose added lines could not be read is withheld and
        # named; the family's other targets still run (Claude on #459).
        unreadable = {
            path: f"{family['id']}: {changes.lines_unread[path]}"
            for path in functions
            if family["producer"] == "complexity" and path in changes.lines_unread
        }
        selected = [
            path for path in targets if path in analyzable and path not in unreadable
        ]
        outcome = (
            _run_family(
                root,
                run,
                family,
                selected,
                functions,
                limits,
                deadline,
                versions,
                limits.max_findings - result.count(),
            )
            if selected
            else _ProducerResult()
        )
        outcome.unanalyzed.update(unreadable)
        # What a family that ran targeted: the composite counts only these, never a
        # family the findings budget stopped (CodeAnt and Claude on #459).
        result.targeted.update(targets)
        result.families.append(
            _family_row(
                family,
                targets,
                {**unread, **outcome.unanalyzed},
                outcome.partial,
                unknown,
            )
        )
        result.merge(outcome)
    if launched:
        _attach_environment_observation(
            result, root, run, limits, deadline, before, gaps
        )
    # A withheld path's findings come from a producer following an import into it
    # (Codex on #436): they stay listed, and are not tracked-source evidence.
    tracked = set(expected) - withheld
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
    policy = _no_fetch_policy()
    # --no-replace-objects: every comparison read uses the objects the recorded base
    # names, never a refs/replace/ substitute (Codex, routed by the Router 6227604656
    # on #436, N1).
    command = [git, "--no-replace-objects", "-c", f"safe.directory={root}", *arguments]
    process = subprocess.Popen(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- argv list, no shell: Git by its resolved path, fixed options and a validated commit id
        command,
        cwd=root,
        env={**_base_env(), **policy},
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
    except BaseException as escaped:
        # As at the producers' drain: the Git child is reaped once, through the
        # existing owner, and the same exception is raised again, never a comparison
        # result (Codex and Claude, the Router's K-b2 on #436).
        failure = _reap(process)
        if failure is not None:
            escaped.add_note(failure)
        raise
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


# The no-fetch values the Router selected from the exact-tree owner's environment: no
# transport, and no lazy fetch of a missing object (Router #389 6325382720).
_NO_FETCH = {"GIT_ALLOW_PROTOCOL": "", "GIT_NO_LAZY_FETCH": "1"}


def _no_fetch_policy() -> dict[str, str]:
    """The integrated exact-tree owner's no-fetch policy, read from its environment,
    so that a promisor the repository configures runs nothing (PAO 6325156914). A
    policy that cannot be read, or holds anything but those exact values, fails
    closed: never a fetch-capable read."""
    try:
        from tools.exact_tree import _GIT_ENV
    except ImportError as exc:
        raise _ComparisonUnavailable("the no-fetch policy is unavailable") from exc
    policy = {key: _GIT_ENV.get(key) for key in _NO_FETCH}
    if policy != _NO_FETCH:
        raise _ComparisonUnavailable("the no-fetch policy is unavailable")
    return dict(_NO_FETCH)


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
    *,
    head: str,
    unreadable: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, set[int]]]:
    """The paths the frozen commit `head` changes since `base`, and the lines each
    change adds, read per path by the GitHub patch reader's own hunk accounting
    (Claude on #436). `head` is the one commit the inventory froze, never a later
    `HEAD` (Router #389 6325382720, D4). With `wanted`, only those paths are read
    line by line: a changed path that no finding names is listed, never read whole
    (CodeAnt on #436). With `unreadable`, a path whose own patch the comparison
    refuses is recorded there with its reason, and the others are still read; without
    it, that refusal is the whole comparison's (cubic and Claude on #459)."""
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
        head,
        cap=cap,
    ).split("\0")
    changed = sorted(name for name in names if name)
    lines: dict[str, set[int]] = {}
    for path in changed:
        if wanted is not None and path not in wanted:
            continue
        try:
            lines[path] = _patch_added_lines(root, base, head, path, deadline, cap)
        except _ComparisonRefused as exc:
            if unreadable is None:
                raise
            unreadable[path] = str(exc)
    return {"base": base, "changed_paths": changed}, lines


def _patch_added_lines(
    root: Path, base: str, head: str, path: str, deadline: float, cap: int
) -> set[int]:
    """The lines the change adds to `path`, by its own patch; or the comparison's
    refusal of that patch. The merge-evidence reader is imported here, so that the
    default collection never loads it."""
    from tools.merge_evidence_github import _added_lines

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
        head,
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
        raise _ComparisonRefused(f"the comparison of {path} is not a sequence of hunks")
    return {number for number, _ in read[0]}


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


def _compare(
    root: Path,
    base: str,
    wanted: set[str],
    deadline: float,
    cap: int,
    *,
    head: str | None,
    unreadable: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, list[int]] | None, str | None]:
    """The frozen commit `head` against `base`: the diff scope and the added lines of
    each changed path in `wanted`, each ordered once for the bisects (cubic, the
    Router's I1 on #436); or the gap that says why there is no comparison. Its two
    consumers are the DIFF scopes' acquisition and the findings' annotation (#389
    A0-MP1)."""
    try:
        exact_sha(base, "base")
    except ValueError:
        return None, None, f"base {base!r} is not a 40-hex commit id"
    try:
        if head is None:
            raise _ComparisonRefused("no commit was frozen to compare")
        diff, lines = _diff_scope(
            root, base, deadline, wanted, cap, head=head, unreadable=unreadable
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        # The comparison's own reasons are written as they are; any other failure by
        # its type alone, never its text (the Router's X1 and Y2 on #436).
        own = isinstance(exc, (_ComparisonUnavailable, _ComparisonRefused))
        reason = str(exc) if own else type(exc).__name__
        return None, None, f"cannot compare with base {base}: {reason}"
    return diff, {path: sorted(numbers) for path, numbers in lines.items()}, None


def _acquisition_changes(
    root: Path,
    profile: Mapping[str, Any],
    expected: list[str],
    base: str | None,
    head: str | None,
    deadline: float,
    cap: int,
    tracked: list[str] | None = None,
) -> _Changes:
    """The changes the DIFF scopes acquire by, read before any producer runs. Only a
    family whose DIFF scope reaches past its FULL one needs them, and only complexity
    needs their added lines; with neither, no comparison is read. A v2 family reaches by
    the tracked paths, not only the Python ones (Codex on #470)."""
    reached = {
        family["id"]: _diff_only(
            profile,
            family,
            tracked
            if tracked is not None and family["producer"] in _V2_PRODUCERS_NAMES
            else expected,
        )
        for family in _active_families(profile)
    }
    if not any(reached.values()):
        return _Changes(frozenset(), {})
    if base is None:
        return _Changes(None, {}, "no comparison base")
    # One comparison: the changed paths, and complexity's added lines path by path; a
    # path whose own patch is refused withholds only itself (cubic and Claude on #459).
    wanted = {
        path
        for family in _active_families(profile)
        if family["producer"] == "complexity"
        for path in reached[family["id"]]
    }
    unread: dict[str, str] = {}
    diff, lines, gap = _compare(
        root, base, wanted, deadline, cap, head=head, unreadable=unread
    )
    if diff is None or lines is None:
        return _Changes(None, {}, gap)
    return _Changes(frozenset(diff["changed_paths"]), lines, lines_unread=unread)


def _annotate_diff(
    root: Path,
    base: str,
    findings: list[dict[str, Any]],
    gaps: list[str],
    deadline: float,
    cap: int = DEFAULT_DIAGNOSTIC_LIMITS.max_report_bytes,
    *,
    head: str | None,
) -> dict[str, Any] | None:
    """Each finding's `in_diff` against `base`, or None, never False, when the
    comparison failed (Amazon Q, Kilo and Octopus on #436); the diff scope. The
    comparison is the frozen commit `head`'s. Without one, only the base's form is
    checked and nothing is compared, which is the comparison's own gap (Router #389
    6325382720, D4)."""
    diff, changed, gap = _compare(
        root, base, {finding["path"] for finding in findings}, deadline, cap, head=head
    )
    if gap is not None:
        gaps.append(gap)
    for finding in findings:
        finding["native"]["in_diff"] = (
            None if changed is None else _in_diff(finding, changed)
        )
    return diff


# The residual of every inventory. A NOT_STAGED one says only that the producers are
# not proven confined; an EXACT_TREE_STAGED one also says which bytes were bound, and
# when, chosen by the same binding as the record's tree_binding (the Router's G451-R9
# on #389).
_UNCONFINED_PRODUCERS_GAP = (
    "source binding UNVERIFIED: the producers' installed environment and import graph "
    "is not proven confined to the staged tracked inputs"
)
_SOURCE_BINDING_GAP = (
    f"{_UNCONFINED_PRODUCERS_GAP}; only the frozen tree's bytes are bound, observed "
    "before and after the producers, not throughout them"
)
# The comparison is read from the frozen Git objects, but each finding's location came
# from producers reading the staged bytes (the Router's G451-R6 on #389).
_UNOBSERVED_ATTRIBUTION_GAP = (
    "finding-to-diff attribution is unknown: the staged source was not verified after "
    "the producers, so the retained comparison describes only the frozen Git objects"
)


# The owner's four accepted limitations, for a bounded diagnostic source-binding claim
# only (#389 6405841272): a BOUND record names them in place of the residual's gap
# (Decision 0120). They claim no complete source observation.
_SOURCE_BINDING_RESIDUAL: Mapping[str, Any] = {
    "decision": "OWNER-389-M8-RISK-FOLLOWUP-6405282317-51519EC6-v1",
    "limitations": (
        "import resolution and the loaded paths outside RECORD-owned roots are not "
        "established",
        "the standard library is bound to the Python version, not content-hashed",
        "the sources' continuity between the endpoint observations is not proven",
        "listed files without content hashes, such as .pyc, are not "
        "content-authenticated",
    ),
}


def _producer_pins() -> dict[str, str] | str:
    """The producer tree's pins, read once before any producer starts, as its profile
    is (Decision 0117; CodeAnt on #463), through the lock's owner; or why they could
    not be read, by type alone, since a failure's text can name host paths (the
    Router's X1 on #436; Amazon Q, Revix and cubic on #463). A lock that is not
    UTF-8 is such a failure (CodeAnt on #463), and so is one that resolves outside
    the producer tree, a link included, by the profile's own confinement owner
    (CodeAnt on #463)."""
    from tools.knowledge_common import confine_to_root

    try:
        lock = confine_to_root(
            _PRODUCER_LOCK, _PRODUCER_TREE, label="the producer tree's lock"
        )[0]
        return {r["normalized_name"]: r["version"] for r in locked_requirements(lock)}
    # RuntimeError holds LockFormatError and a link loop's resolution; ValueError holds
    # the confinement owner's KnowledgeFormatError and a lock that is not UTF-8.
    except (OSError, RuntimeError, ValueError) as exc:
        return f"the producer tree's lock could not be read: {type(exc).__name__}"


def _unmet_pins(
    launched: list[dict[str, Any]], needed: list[str], pins: dict[str, str] | str
) -> list[str]:
    """P2's failures: a producer a family needed that never ran (cubic on #463), and
    each launched run's own version against its producer's pin. Every run is
    checked, though a producer's runs share one version read, so none can mask
    another (Revix on #463); each failure is named once."""
    if not launched and not needed:
        # Nothing launched and nothing needed to: no pin applies, readable or not
        # (CodeAnt on #463).
        return []
    ran = {run["producer"] for run in launched}
    unmet = [f"{producer} never ran" for producer in needed if producer not in ran]
    if isinstance(pins, str):
        # No pin can be compared, and each needed producer that never ran is still
        # named (Claude on #463).
        return [pins, *unmet]
    for run in launched:
        producer, version = run["producer"], run.get("version")
        if version is None:
            detail = f"{producer}'s version could not be read"
        elif producer not in pins:
            detail = f"{producer} has no pin in the producer tree's lock"
        elif version != pins[producer]:
            detail = (
                f"{producer}'s version {version!r} is not its pin {pins[producer]!r}"
            )
        else:
            continue
        if detail not in unmet:
            unmet.append(detail)
    return unmet


def _unmet_predicates(
    bound: bool,
    rebound: bool,
    origin: str,
    runs: list[dict[str, Any]],
    families: list[dict[str, Any]],
    pins: dict[str, str] | str,
) -> list[str]:
    """The source binding's unmet predicates, one gap each, read from the run's own
    record and the producer tree (Decision 0120). P1: the frozen tree staged and
    observed unchanged, and the subject re-read as its own. P2: each launched producer
    a family needed ran, at its pin. P3: the producer tree's profile. P4: each
    launched run's environment endpoints equal. An in-process family launches
    nothing, so neither P2 nor P4 reads it; a tree never staged ran nothing, which P1
    names, and P2 then reads nothing."""
    launched = [run for run in runs if run["producer"] in _LAUNCHED_PRODUCERS]
    # A family with targets, or whose targets are unknown, needs its producer run;
    # one with none needs nothing (cubic on #463). Withheld or over-budget targets
    # still count: BOUND claims nothing about a producer that analyzed nothing,
    # whose family's own INCOMPLETE row states the coverage (cubic on #463).
    needed = sorted(
        {
            row["producer"]
            for row in families
            if row["producer"] in _LAUNCHED_PRODUCERS and row["targets"] != 0
        }
    )
    unmet: dict[str, list[str]] = {"P1": [], "P2": [], "P3": [], "P4": []}
    if not bound:
        unmet["P1"].append("the frozen tree was not staged and observed unchanged")
    elif not rebound:
        # Its own gap names the failure once; this one names the predicate (the
        # Router's 6239259708 on #436).
        unmet["P1"].append("the subject's Git metadata was not confirmed after the run")
    # Once any producer ran, or the tree was staged, each needed one must have run,
    # whether or not the tree was observed unchanged afterwards (Amazon Q on #463).
    if launched or bound:
        unmet["P2"] = _unmet_pins(launched, needed, pins)
    if origin != "producer-tree":
        unmet["P3"].append("the profile was supplied, not the producer tree's")
    for run in launched:
        observation = run.get("environment_observation")
        if not isinstance(observation, Mapping):
            unmet["P4"].append(f"{run['invocation']}'s environment was not observed")
        elif observation.get("status") != "endpoints_equal":
            unmet["P4"].append(
                f"{run['invocation']}'s environment endpoints are "
                f"{observation.get('status')}"
            )
    return [
        f"source binding {label} unmet: {', '.join(details)}"
        for label, details in unmet.items()
        if details
    ]


def _record_binding(gaps: list[str], at: int, bound: bool, unmet: list[str]) -> str:
    """BOUND when no predicate is unmet; otherwise UNVERIFIED, with the residual still
    a gap at `at`, chosen by the tree binding (the Router's G451-R9 on #389), and each
    unmet predicate named after it (Decision 0120)."""
    if not unmet:
        return "BOUND"
    residual = _SOURCE_BINDING_GAP if bound else _UNCONFINED_PRODUCERS_GAP
    gaps[at:at] = [residual, *unmet]
    return "UNVERIFIED"


def _forget_attribution(findings: list[dict[str, Any]]) -> None:
    """Make every finding's diff attribution unknown, positive and negative alike."""
    for finding in findings:
        finding["native"]["in_diff"] = None


# The one form a frozen object id takes, the owner's two hash lengths.
_OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# The private directory, inside the run, that holds the staged source apart from the
# producers' reports (Router #389 6324876845).
_STAGED_SOURCE = "source"

# The scope owner's categories for Git metadata that is unsafe or cannot be
# inspected: no proof of absence, so no inventory (the Router's 6239259708 and C-a on
# #436). Every other scope error stays its own gap.
_METADATA_REFUSALS = frozenset({"UNSAFE_PATH", "GIT_METADATA_IO"})


def _refuse_unsafe_metadata(exc: RepositoryScopeError, prefix: str) -> None:
    """Refuse the inventory for the metadata categories, by the category alone."""
    if exc.category in _METADATA_REFUSALS:
        raise QualityEvidenceError(
            scope_error_detail(prefix, exc) + "; no inventory was written"
        ) from exc


def _unrepresentable_timeout(read: str) -> QualityEvidenceError:
    """The refusal for a remaining budget that the platform cannot represent as a Git
    read's timeout: subprocess raised OverflowError for a finite timeout_seconds such
    as 1e20 (Codex, the Router's 6243027809 on #436). Its reason is fixed, never the
    exception's text, and it is no evidence that the deadline passed or that the
    metadata is absent."""
    return QualityEvidenceError(
        f"the remaining timeout cannot be represented for {read}; no inventory was "
        "written"
    )


def _frozen_subject(
    root: Path, expected_revision: str | None, deadline: float
) -> tuple[str | None, str | None, list[str]]:
    """The one commit the inventory analyzes, resolved once to its full id, and the
    tree derived from that id, never from a second read of `HEAD` or a ref (Router
    #389 6325382720, D4). With `expected_revision`, that exact commit, never another
    object it peels to; otherwise `HEAD`, read once. Unsafe or uninspectable metadata
    is refused, by its category alone, and a root with no Git metadata of its own
    freezes nothing: no Git is read for it (the Router's G-a on #436). Each other
    failure is the subject's named gap, never a fallback to the checkout."""
    gaps: list[str] = []
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        gaps.append("the deadline passed before the subject was frozen")
        return None, None, gaps
    try:
        owned = has_git_metadata(root, timeout=remaining)
    except RepositoryScopeError as exc:
        _refuse_unsafe_metadata(exc, "cannot bind the subject's Git metadata")
        gaps.append(
            scope_error_detail("cannot confirm the subject's Git identity", exc)
        )
        return None, None, gaps
    except OverflowError as exc:
        raise _unrepresentable_timeout("the subject's Git metadata") from exc
    if not owned:
        gaps.append("the subject has no Git metadata of its own: no commit was frozen")
        return None, None, gaps
    wanted = expected_revision or "HEAD"
    try:
        commit = _one_object(root, deadline, f"{wanted}^{{commit}}")
        if expected_revision is not None and commit != expected_revision:
            raise _ComparisonRefused("the expected revision is not that commit")
        tree = _one_object(root, deadline, f"{commit}^{{tree}}")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        own = isinstance(exc, (_ComparisonUnavailable, _ComparisonRefused))
        reason = str(exc) if own else type(exc).__name__
        gaps.append(f"cannot freeze the subject's commit: {reason}")
        return None, None, gaps
    return commit, tree, gaps


def _check_expected_revision(expected_revision: object) -> None:
    """Refuse, before any work, an expected revision that is not one full commit id,
    by its form alone and never echoed: an arbitrary input can neither reach Git nor
    grow the record (Router #389 6325382720, D4; CodeAnt on #451)."""
    if expected_revision is None:
        return
    if type(expected_revision) is not str or not _OBJECT_ID.fullmatch(
        expected_revision
    ):
        raise QualityEvidenceError(
            "expected_revision must be one full 40- or 64-character lowercase hex "
            "commit id"
        )


def _one_object(root: Path, deadline: float, name: str) -> str:
    """The full object id `name` resolves to, read once; never an answer that is not
    exactly one full id."""
    answer = _diagnostic_git(
        root, deadline, "rev-parse", "--verify", "--end-of-options", name
    ).splitlines()
    if len(answer) != 1 or not _OBJECT_ID.fullmatch(answer[0]):
        raise _ComparisonRefused("the answer is not one full object id")
    return answer[0]


def _stage(
    root: Path, tree: str, run: Path, owner: _TreeLimits
) -> tuple[Path, str] | str:
    """The frozen tree's exact bytes, staged privately in the run through the shared
    exact-tree owner, within the inventory's one deadline and its whole-tree caps,
    and the staged directory's identity, computed again independently; or the
    owner's code as the gap, and nothing staged (Router #389 6325382720, D3)."""
    from tools import exact_tree

    staged = run / _STAGED_SOURCE
    try:
        exact_tree.materialize(root, tree, staged, limits=owner)
        identity = exact_tree.observed_tree(root, staged, limits=owner)
    except exact_tree.ExactTreeError as exc:
        return _and(
            f"the source tree cannot be staged: {exc.code}",
            _discard_staged(staged, owner),
        )
    except OverflowError as exc:
        refusal = _unrepresentable_timeout("the frozen tree's stage")
        _note_retained(refusal, _discard_staged(staged, owner))
        raise refusal from exc
    except BaseException as primary:
        _note_retained(primary, _discard_staged(staged, owner))
        raise
    if identity != tree:
        return _and(
            "the source tree cannot be staged: tree-mismatch",
            _discard_staged(staged, owner),
        )
    return staged, identity


# The owner's codes that refuse an inventory when the staged source is observed again,
# each with its reason. `unsupported-entry` is also what an unknown object format
# raises before the staged root is read, so it claims no change (Router #389
# 6332488628, correcting D3's boundary). Every other code certifies nothing.
_REOBSERVATION_REFUSALS = {
    "tree-mismatch": "the staged source no longer matches the frozen tree",
    "unsafe-path": "the staged source holds an unsafe path",
    "cap-files": "the staged source exceeds its file bound",
    "cap-bytes": "the staged source exceeds its byte bound",
    "unsupported-entry": (
        "unrepresentable re-observation of the staged source, change not established"
    ),
}


def _reobserved(
    root: Path, staged: Path, tree: str, owner: _TreeLimits, run: Path
) -> bool:
    """Whether the staged source is still the frozen tree after the producers read
    it. One that changed is refused, with no inventory (Router #389 6325382720,
    D3), as is one the owner finds mismatched, unsafe, over its bound or
    unrepresentable, worded by its code (6332488628); one that cannot otherwise be
    observed again is not certified."""
    from tools import exact_tree

    try:
        after = exact_tree.observed_tree(root, staged, limits=owner)
    except exact_tree.ExactTreeError as exc:
        reason = _REOBSERVATION_REFUSALS.get(exc.code)
        if reason is None:
            return False
        raise QualityEvidenceError(
            f"{reason}: {exc.code}; no inventory was written, the raw reports are in "
            f"{run}"
        ) from exc
    except OverflowError as exc:
        raise _unrepresentable_timeout("the staged source's identity") from exc
    if after != tree:
        raise QualityEvidenceError(
            "the staged source changed during collection; no inventory was written, "
            f"the raw reports are in {run}"
        )
    return True


def _metadata_rebound(root: Path, deadline: float, gaps: list[str]) -> bool:
    """Whether the subject's Git metadata is still its own after collection, by the
    scope owner's identity check again: never a git status. Unsafe or uninspectable
    metadata refuses the inventory, by its category alone, as at the freeze; one that
    cannot be confirmed, is gone or is out of budget leaves the comparison that read
    it unbound, its own failure named once (the Router's 6239259708 and 6243847776
    on #436; Router #389 6325382720, D3: the existing hard refusals remain)."""
    reread = "the subject could not be re-read after collection"
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        gaps.append(reread)
        return False
    try:
        owned = has_git_metadata(root, timeout=remaining)
    except RepositoryScopeError as exc:
        _refuse_unsafe_metadata(exc, "cannot bind the subject's Git metadata")
        # Only a frozen commit is checked again, so the freeze named no identity
        # failure before this one (cubic and Octopus on #451).
        gaps.append(reread)
        gaps.append(
            scope_error_detail("cannot confirm the subject's Git identity", exc)
        )
        return False
    except OverflowError as exc:
        raise _unrepresentable_timeout("the subject's Git metadata") from exc
    if not owned:
        gaps.append(reread)
    return owned


class _CleanupDeadline(Exception):
    """The inventory's deadline passed while its staged source was being removed."""


class _CleanupOverBound(Exception):
    """The staged source holds more named entries than its removal may examine."""


@dataclasses.dataclass
class _EntryBudget:
    """The named entries, directories included, that one removal may still examine:
    shared by every directory it lists and never reset per directory (Router
    6332488628 on #389)."""

    remaining: int

    def spend(self) -> None:
        """Spend one entry, or refuse it once the budget is spent."""
        if self.remaining <= 0:
            raise _CleanupOverBound
        self.remaining -= 1


_RETAINED = "the staged source was left in the run directory"


def _directory_flags() -> int:
    """The flags that open a directory of the staged source by its own name and never
    through a link: the staging owner's own, consumed rather than copied, so the
    removal opens the directories exactly as the owner that staged them (cubic on
    #451). They are POSIX-only, so the owner is imported here, on the diagnostic path,
    never at import: the default collection imports without them (Codex and Q)."""
    from tools import exact_tree

    return exact_tree.DIRECTORY_FLAGS


def _within(deadline: float) -> None:
    """Start no further cleanup dispatch once the inventory's deadline has passed."""
    if time.monotonic() >= deadline:
        raise _CleanupDeadline


def _listed(fd: int, deadline: float, budget: _EntryBudget) -> list[os.DirEntry[str]]:
    """Every entry of an open directory, the deadline checked before its listing opens
    and before each advance of it, since one advance can read the directory again
    (Router 6330915173 on #389). Each entry spends the removal's shared budget before
    it is kept, so a listing past the bound is never held whole (6332488628)."""
    _within(deadline)
    found: list[os.DirEntry[str]] = []
    with os.scandir(fd) as listing:
        while True:
            _within(deadline)
            entry = next(listing, None)
            if entry is None:
                return found
            budget.spend()
            found.append(entry)


def _descend_or_remove(entry: os.DirEntry[str], fd: int, deadline: float) -> int | None:
    """Open a directory entry for the walk, or remove any other entry, relative to its
    directory's descriptor. Its type is read without following a link, and the
    deadline is checked before that read and again before the open or removal it
    selects. Returns the opened directory's descriptor, or None."""
    _within(deadline)
    try:
        directory = entry.is_dir(follow_symlinks=False)
        _within(deadline)
        if directory:
            return os.open(entry.name, _directory_flags(), dir_fd=fd)
        os.unlink(entry.name, dir_fd=fd)
    except FileNotFoundError:
        pass
    return None


def _discard_staged(staged: Path, owner: _TreeLimits) -> str | None:
    """Remove the staged source this run owns, within the inventory's one deadline and
    its tree bound. The walk is post-order and explicit: the deadline is checked before
    every directory open, every advance of a directory's listing, every entry's type
    read, and every removal, so a spent budget starts none of them; only closing the
    walk's own descriptors runs past it. Each directory is opened relative to its
    parent's descriptor, never through a link, and an entry is removed by its own type,
    never followed. The walk examines at most `max_files` named entries, beyond the
    root, counting directories, where staging counts files alone: so a directory-rich
    tree that staged within the bound can still leave its removal short (Router
    6332488628). What a passed deadline, the entry bound or a failed removal leaves
    stays in the run directory, and that is returned for the record; it never
    replaces the refusal or the result it follows (PAO 6329094433 and 6330677193 on
    #389)."""
    deadline = owner.deadline
    budget = _EntryBudget(owner.max_files)
    # Each frame: an open directory and its name for removal, relative to the frame
    # below, or the staged path itself for the root; beside it, its entries still to
    # remove, None until the directory is read.
    frames: list[tuple[int, str | Path]] = []
    entries: list[list[os.DirEntry[str]] | None] = []
    try:
        _within(deadline)
        try:
            frames.append((os.open(staged, _directory_flags()), staged))
        except FileNotFoundError:
            return None
        entries.append(None)
        while frames:
            fd, name = frames[-1]
            if entries[-1] is None:
                entries[-1] = _listed(fd, deadline, budget)
            pending = entries[-1]
            if pending:
                entry = pending.pop()
                child = _descend_or_remove(entry, fd, deadline)
                if child is not None:
                    frames.append((child, entry.name))
                    entries.append(None)
                continue
            frames.pop()
            entries.pop()
            os.close(fd)
            _within(deadline)
            with contextlib.suppress(FileNotFoundError):
                os.rmdir(name, dir_fd=frames[-1][0] if frames else None)
    except _CleanupDeadline:
        return f"{_RETAINED}: the deadline passed during its removal"
    except _CleanupOverBound:
        return (
            f"{_RETAINED}: it holds more than the {owner.max_files} named entries its "
            "removal may examine"
        )
    except OSError as exc:
        return f"{_RETAINED}: it could not be removed whole ({type(exc).__name__})"
    finally:
        # A close that fails replaces neither the walk's result nor the closing of
        # the other descriptors (Claude on #451, 6331607363).
        for fd, _name in frames:
            with contextlib.suppress(OSError):
                os.close(fd)
    return None


def _note_retained(primary: BaseException, retained: str | None) -> None:
    """Name a staged source left behind on the failure being raised, never replacing
    it."""
    if retained is not None:
        primary.add_note(retained)


def _analyze_frozen(
    root: Path,
    tree: str,
    run: Path,
    limits: DiagnosticLimits,
    owner: _TreeLimits,
    gaps: list[str],
    deadline: float,
    *,
    profile: Mapping[str, Any],
    base: str | None,
    head: str | None,
) -> tuple[list[str] | None, _ProducerResult, str | None, bool]:
    """The frozen tree's tracked Python set, the producers' result over its staged
    bytes, the staged identity and whether it was observed unchanged after them.
    Nothing is analyzed without a staged source, never the checkout: a known set is
    named unanalyzed, and an unknown one stays unknown (Router #389 6325382720, D3).
    The staged source is removed once the producers are done."""
    listed = _tracked_listing(root, tree, owner)
    if isinstance(listed, str):
        gaps.append(listed)
        return None, _ProducerResult(), None, False
    expected = _python_paths(listed)
    changes = _acquisition_changes(
        root,
        profile,
        expected,
        base,
        head,
        deadline,
        limits.max_report_bytes,
        tracked=listed,
    )
    staging = _stage(root, tree, run, owner)
    if isinstance(staging, str):
        gaps.append(staging)
        unstaged = dict.fromkeys(
            expected, "the source tree was not staged, never analyzed"
        )
        return expected, _ProducerResult(unanalyzed=unstaged), None, False
    staged, identity = staging
    try:
        result = _run_all_families(
            staged,
            run,
            expected,
            limits,
            gaps,
            deadline,
            profile,
            changes,
            listed,
        )
        bound = _reobserved(root, staged, tree, owner, run)
    except BaseException as primary:
        _note_retained(primary, _discard_staged(staged, owner))
        raise
    retained = _discard_staged(staged, owner)
    if retained is not None:
        gaps.append(retained)
    if not bound:
        gaps.append("the staged source could not be observed again")
    return expected, result, identity, bound


def _source_record(
    commit: str | None,
    tree: str | None,
    identity: str | None,
    expected_revision: str | None,
    bound: bool,
    binding: str,
) -> dict[str, Any]:
    """The subject as v2 records it: the frozen commit and tree, and the staged
    identity only while the tree was staged and observed unchanged after the
    producers. The checkout is never read, so no dirty state is recorded (Router
    #389 6325382720, D1). A BOUND binding names the owner's accepted residual, an
    UNVERIFIED one none (Decision 0120)."""
    residual = (
        {
            "decision": _SOURCE_BINDING_RESIDUAL["decision"],
            "limitations": list(_SOURCE_BINDING_RESIDUAL["limitations"]),
        }
        if binding == "BOUND"
        else None
    )
    return {
        "revision": commit,
        "tree": tree,
        "staged_identity": identity if bound else None,
        "tree_binding": "EXACT_TREE_STAGED" if bound else "NOT_STAGED",
        "expected_revision": expected_revision,
        "source_binding": binding,
        "accepted_residual": residual,
    }


def _diagnostic_coverage(
    expected: list[str] | None,
    result: _ProducerResult,
    gaps: list[str],
    pages: int,
    families: list[dict[str, Any]],
) -> dict[str, Any]:
    """The composite: the conjunction of the families' rows with the inventory's
    shared gaps, each INCOMPLETE family named (the PAO's R2 on #389 6387305292)."""
    reasons = list(gaps)
    if expected is not None and not expected:
        reasons.append("no tracked Python file")
    if result.unanalyzed:
        reasons.append(f"{len(result.unanalyzed)} tracked Python files unanalyzed")
    reasons += [
        f"family {row['family']} INCOMPLETE: {row['reason']}"
        for row in families
        if row["analysis"] == "INCOMPLETE"
    ]
    partial = [row for row in families if row["analysis"] == "PARTIAL"]
    status = "COMPLETE"
    if reasons:
        status = "INCOMPLETE"
    elif result.partial or partial:
        status = "PARTIAL"
    if result.partial:
        reasons.append(f"{len(result.partial)} files with unresolved imports")
    # Each PARTIAL family is named too: the composite is the rows' conjunction (Revix
    # on #459).
    reasons += [f"family {row['family']} PARTIAL: {row['reason']}" for row in partial]
    known = expected or []
    return readback_coverage(
        status,
        pages=pages,
        count=len(
            [p for p in known if p in result.targeted and p not in result.unanalyzed]
        ),
        total=None if expected is None else len(expected),
        reason="; ".join(reasons) or None,
    )


def _family_rows(
    profile: Mapping[str, Any], result: _ProducerResult
) -> list[dict[str, Any]]:
    """Each of the profile's families' row, in its order: a family the analysis never
    reached has an INCOMPLETE one, never none (the PAO's R2 on #389 6387305292)."""
    rows = {row["family"]: row for row in result.families}
    return [
        rows.get(family["id"]) or _family_row(family, None, {}, {}, None)
        for family in _active_families(profile)
    ]


def _inventory_configuration(
    limits: DiagnosticLimits, profile: Mapping[str, Any], origin: str
) -> dict[str, Any]:
    # The repository's shared canonical digest, in its prefixed form (Revix on #459).
    from tools.review_model import canonical_digest

    complexity = [f for f in profile["families"] if f["producer"] == "complexity"]
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
        "ruff_select": [
            code
            for family in profile["families"]
            if family["producer"] == "ruff"
            for code in family["select"]
        ],
        "profile": {
            "digest": canonical_digest(profile),
            "value": profile,
            # The producer tree's, or one a private caller supplied (#459).
            "origin": origin,
        },
        "complexity": {
            "metric": COMPLEXITY_METRIC,
            "reported_above": complexity[0]["reported_above"] if complexity else None,
            "qualification": "UNQUALIFIED",
            # The grammar the metric parses: the producers' declared target, bound
            # best-effort as Python's feature_version is, which promises no AST
            # identical to that Python's own (Codex, the Router's 6242507671 on #436).
            "grammar": {
                "python": "{}.{}".format(*_PYTHON_TARGET),
                "binding": "BEST_EFFORT",
            },
        },
        "limits": dataclasses.asdict(limits),
    }


def _tracked_listing(root: Path, tree: str, owner: _TreeLimits) -> list[str] | str:
    """Every tracked path of the frozen tree, sorted, listed from its objects, never the
    index or the checkout, within the inventory's one deadline and whole-tree caps;
    or, for a set that stays unknown, its gap (Router #389 6325382720, D3). It is
    listed once, for the Python families and the v2 families alike (#389 H-PYSEC-2)."""
    from tools import exact_tree

    try:
        paths = exact_tree.tree_paths(root, tree, limits=owner)
    except exact_tree.ExactTreeError as exc:
        return f"cannot enumerate the frozen tree: {exc.code}"
    except OverflowError as exc:
        raise _unrepresentable_timeout("the frozen tree's listing") from exc
    return sorted(paths)


def _python_paths(paths: list[str]) -> list[str]:
    return [p for p in paths if PurePosixPath(p).suffix == ".py"]


def _tracked_python(root: Path, tree: str, owner: _TreeLimits) -> list[str] | str:
    """The tracked Python set of the frozen tree, from its one listing, or its gap."""
    listed = _tracked_listing(root, tree, owner)
    return listed if isinstance(listed, str) else _python_paths(listed)


def _check_limits(limits: DiagnosticLimits) -> None:
    """Refuse, before any work, a limit that would fail open or admit none: a negative
    bound, which read() takes as everything (cubic on #436), a max_findings above the
    normalization bound, or a timeout that is not a positive finite number of seconds
    (CodeAnt on #436)."""
    for name in (
        "max_files",
        "max_findings",
        "max_report_bytes",
        "max_source_bytes",
        "max_tree_files",
        "max_tree_bytes",
    ):
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
    explicit call runs it. The producer tree's protected profile selects what runs,
    and no caller supplies another (cubic and Revix on #459); a profile that breaks
    its contract is refused before anything runs. More findings than
    `limits.max_findings` write no inventory at all: the raw reports stay in the run
    directory. It is never COMPLETE while its source binding is UNVERIFIED, and its
    binding is BOUND only when its own run meets P1-P4 (Decision 0120)."""
    return _collect_diagnostic_inventory(
        repository_root,
        output_directory,
        base=base,
        expected_revision=expected_revision,
        limits=limits,
    )


def _collect_diagnostic_inventory(
    repository_root: Path,
    output_directory: Path,
    *,
    base: str | None = None,
    expected_revision: str | None = None,
    limits: DiagnosticLimits = DEFAULT_DIAGNOSTIC_LIMITS,
    profile: Mapping[str, Any] | None = None,
) -> Path:
    """The inventory under `profile`, validated as the protected one is, or without
    one under the producer tree's: the private path for the tests and labelled
    qualification variants. The record names which origin governed it."""
    _check_limits(limits)
    _check_expected_revision(expected_revision)
    _refuse_caller_git_overrides()
    origin = "producer-tree" if profile is None else "argument"
    profile = (
        load_diagnostic_profile() if profile is None else _validated_profile(profile)
    )
    pins = _producer_pins()
    from tools import exact_tree

    root = repository_root.resolve()
    output = output_directory.resolve()
    output.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="diagnostic-", dir=output))
    deadline = time.monotonic() + limits.timeout_seconds
    # The owner's bounds share the inventory's one absolute deadline, never a fresh
    # budget of its own (Router #389 6324876845).
    owner = exact_tree.Limits(deadline, limits.max_tree_files, limits.max_tree_bytes)
    commit, tree, gaps = _frozen_subject(root, expected_revision, deadline)
    if tree is None:
        expected, result, identity, bound = None, _ProducerResult(), None, False
    else:
        expected, result, identity, bound = _analyze_frozen(
            root,
            tree,
            run,
            limits,
            owner,
            gaps,
            deadline,
            profile=profile,
            base=base,
            head=commit,
        )
    # The binding's gaps keep this place in the reason; they are known only once the
    # subject has been re-read (Decision 0120).
    binding_at = len(gaps)
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
            head=commit,
        )
    )
    # Nothing reads the root's Git after a freeze that failed, so the metadata is
    # checked again only for a frozen commit (cubic and Octopus on #451).
    rebound = commit is None or _metadata_rebound(root, deadline, gaps)
    if not rebound and base is not None:
        # The comparison no longer describes the subject, so no answer stays definite,
        # and its own record is not published as bound provenance either (the Router's
        # D1 and D1b on #436).
        diff = None
        _forget_attribution(result.findings)
    elif diff is not None and identity is not None and not bound:
        # The staged source the producers read was not observed again: the comparison
        # still describes the frozen objects, but no finding's place in it is known,
        # and the deduplication below keeps it unknown (the Router's G451-R6 on #389).
        _forget_attribution(result.findings)
        gaps.append(_UNOBSERVED_ATTRIBUTION_GAP)
    unmet = _unmet_predicates(
        bound, rebound, origin, result.runs, _family_rows(profile, result), pins
    )
    binding = _record_binding(gaps, binding_at, bound, unmet)
    source = _source_record(commit, tree, identity, expected_revision, bound, binding)
    try:
        findings = deduplicate_findings(result.findings)
    except AnalyzerReadbackError as exc:
        raise QualityEvidenceError(f"cannot normalize the findings: {exc}") from exc
    return _publish(
        run,
        deadline,
        source=source,
        limits=limits,
        profile=profile,
        origin=origin,
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
    profile: Mapping[str, Any],
    origin: str,
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

    families = _family_rows(profile, result)

    def encoded() -> bytes:
        document = {
            "schema": DIAGNOSTIC_SCHEMA,
            "status": "EXPERIMENTAL",
            "source": source,
            "configuration": _inventory_configuration(limits, profile, origin),
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
            "coverage": _diagnostic_coverage(
                expected, result, gaps, len(result.runs), families
            ),
            "families": families,
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
