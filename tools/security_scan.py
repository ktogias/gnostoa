"""Fail-closed tracked-tree secret scanning with an audited exact baseline."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.repository_scope import candidate_paths

DEFAULT_BASELINE = Path(".secrets.baseline")
_MAX_REPORT_BYTES = 8_388_608
_SCAN_TIMEOUT_SECONDS = 300
_BASELINE_EXCLUDE_PATTERN = r"^\.secrets\.baseline$"
_ALLOWED_BASELINE_PATHS = {
    "tasks/issue-11-r2a-current-advisory-consumer.json",
    "tasks/issue-11-r2a-current-advisory.json",
}
_SECRET_HASH = re.compile(r"^[0-9a-f]{40}$")


class SecurityScanError(RuntimeError):
    """The tracked-tree scan or its reviewed baseline is unusable."""


@dataclass(frozen=True)
class SecretScanResult:
    """Sanitized result containing no candidate or candidate-derived hash."""

    reviewed_false_positives: int
    unresolved_findings: list[dict[str, int | str]]


SecretIdentity = tuple[str, str, str]


def _results(document: dict[str, Any], label: str) -> dict[str, Any]:
    results = document.get("results")
    if not isinstance(results, dict):
        raise SecurityScanError(f"{label} has no results mapping")
    return results


def _settings(document: dict[str, Any], label: str) -> tuple[object, object, object]:
    version = document.get("version")
    plugins = document.get("plugins_used")
    filters = document.get("filters_used")
    if not isinstance(version, str) or not isinstance(plugins, list):
        raise SecurityScanError(f"{label} has invalid scanner settings")
    if filters is not None and not isinstance(filters, list):
        raise SecurityScanError(f"{label} has invalid scanner filters")
    return version, plugins, filters


def _identities(
    document: dict[str, Any],
    *,
    label: str,
    require_false_positive: bool,
) -> tuple[dict[SecretIdentity, dict[str, int | str]], set[SecretIdentity]]:
    records: dict[SecretIdentity, dict[str, int | str]] = {}
    identities: set[SecretIdentity] = set()
    results = _results(document, label)
    if any(not isinstance(path, str) for path in results):
        raise SecurityScanError(f"{label} results are malformed")
    for path in sorted(results):
        candidates = results[path]
        if not isinstance(candidates, list):
            raise SecurityScanError(f"{label} results are malformed")
        if (
            not path
            or not path.isprintable()
            or Path(path).is_absolute()
            or ".." in Path(path).parts
        ):
            raise SecurityScanError(f"{label} contains an unsafe result path")
        if require_false_positive and path not in _ALLOWED_BASELINE_PATHS:
            raise SecurityScanError(
                f"{label} contains an unauthorized false-positive path"
            )
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise SecurityScanError(f"{label} candidate is malformed")
            candidate_type = candidate.get("type")
            secret_hash = candidate.get("hashed_secret")
            line = candidate.get("line_number")
            if (
                not isinstance(candidate_type, str)
                or not candidate_type
                or not candidate_type.isprintable()
                or not isinstance(secret_hash, str)
                or _SECRET_HASH.fullmatch(secret_hash) is None
                or not isinstance(line, int)
                or isinstance(line, bool)
                or line < 1
            ):
                raise SecurityScanError(f"{label} candidate identity is malformed")
            if require_false_positive and candidate.get("is_secret") is not False:
                raise SecurityScanError(
                    f"{label} contains an entry not reviewed as a false positive"
                )
            identity = (path, candidate_type, secret_hash)
            if identity in identities:
                raise SecurityScanError(f"{label} repeats a candidate identity")
            identities.add(identity)
            records[identity] = {
                "path": path,
                "line": line,
                "type": candidate_type,
            }
    return records, identities


def evaluate_secret_report(
    scan_document: dict[str, Any],
    baseline_document: dict[str, Any],
) -> SecretScanResult:
    """Compare one scan with exact reviewed false positives.

    Candidate hashes are used only as in-memory comparison identities and are
    deliberately absent from the returned result and diagnostics.
    """

    if _settings(scan_document, "detect-secrets report") != _settings(
        baseline_document,
        "detect-secrets baseline",
    ):
        raise SecurityScanError(
            "detect-secrets report settings do not match the reviewed baseline"
        )
    scan_records, scan_identities = _identities(
        scan_document,
        label="detect-secrets report",
        require_false_positive=False,
    )
    _, baseline_identities = _identities(
        baseline_document,
        label="detect-secrets baseline",
        require_false_positive=True,
    )
    stale = baseline_identities - scan_identities
    if stale:
        raise SecurityScanError(
            "detect-secrets baseline contains stale reviewed entries"
        )
    unresolved = sorted(
        (scan_records[identity] for identity in scan_identities - baseline_identities),
        key=lambda item: (str(item["path"]), int(item["line"]), str(item["type"])),
    )
    return SecretScanResult(
        reviewed_false_positives=len(baseline_identities),
        unresolved_findings=unresolved,
    )


def _read_document(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        if len(raw) > _MAX_REPORT_BYTES:
            raise SecurityScanError(f"{label} exceeds the bounded size")
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SecurityScanError(f"cannot read {label}: {exc}") from exc
    if not isinstance(document, dict):
        raise SecurityScanError(f"{label} is not a JSON object")
    return document


def scan_tracked_tree(
    repository_root: Path,
    *,
    report_path: Path | None = None,
    baseline_path: Path = DEFAULT_BASELINE,
    tracked_paths: list[Path] | None = None,
) -> SecretScanResult:
    """Scan the exact tracked regular-file tree and apply the reviewed baseline."""

    root = repository_root.resolve()
    paths = candidate_paths(root) if tracked_paths is None else list(tracked_paths)
    if not paths:
        raise SecurityScanError("tracked-tree secret scan has no candidate files")
    tracked_symlinks = [path.as_posix() for path in paths if (root / path).is_symlink()]
    if tracked_symlinks:
        raise SecurityScanError(
            "tracked-tree secret scan refuses symlinks: " + ", ".join(tracked_symlinks)
        )

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "detect_secrets",
                "--cores",
                "1",
                "scan",
                "--no-verify",
                "--exclude-files",
                _BASELINE_EXCLUDE_PATTERN,
                *(path.as_posix() for path in paths),
            ],
            cwd=root,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=_SCAN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise SecurityScanError("tracked-tree secret scan timed out") from exc
    except OSError as exc:
        raise SecurityScanError("cannot execute the tracked-tree secret scan") from exc
    if completed.returncode != 0:
        raise SecurityScanError(
            f"tracked-tree secret scan returned status {completed.returncode}"
        )
    if len(completed.stdout) > _MAX_REPORT_BYTES:
        raise SecurityScanError("tracked-tree secret scan report exceeds the bound")
    try:
        scan_document = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SecurityScanError(
            "tracked-tree secret scan returned invalid JSON"
        ) from exc
    if not isinstance(scan_document, dict):
        raise SecurityScanError("tracked-tree secret scan report is not an object")
    resolved_baseline = baseline_path
    if not resolved_baseline.is_absolute():
        resolved_baseline = root / resolved_baseline
    baseline_document = _read_document(
        resolved_baseline,
        "detect-secrets baseline",
    )
    result = evaluate_secret_report(scan_document, baseline_document)
    if report_path is not None:
        sanitized_report = {
            "schema_version": 1,
            "reviewed_false_positives": result.reviewed_false_positives,
            "unresolved_findings": result.unresolved_findings,
        }
        try:
            report_path.write_text(
                json.dumps(sanitized_report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise SecurityScanError(
                "cannot write the sanitized tracked-tree secret report"
            ) from exc
    return result
