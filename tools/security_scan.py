"""Fail-closed tracked-tree secret scanning with an audited exact baseline."""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.repository_scope import RepositoryScopeError, candidate_paths

DEFAULT_BASELINE = Path(".secrets.baseline")
_MAX_REPORT_BYTES = 8_388_608
_READ_CHUNK_BYTES = 65_536
_SCAN_TIMEOUT_SECONDS = 300
_BASELINE_EXCLUDE_PATTERN = r"^\.secrets\.baseline$"
_PROTECTED_BASELINE_FILE_SHA256 = {
    "tasks/issue-11-r2a-current-advisory-consumer.json": (
        "c55f9b9d0d564c3e617f7cee5de050b321f3ca60a1d094dc36720ccb6c1394ee"  # pragma: allowlist secret -- reviewed protected-authority content digest
    ),
    "tasks/issue-11-r2a-current-advisory.json": (
        "d6d07e104213a9e18cba909ca1727a5c276e87c9dcaa2e38023053161a3335fb"  # pragma: allowlist secret -- reviewed protected-authority content digest
    ),
}
_ALLOWED_BASELINE_PATHS = frozenset(_PROTECTED_BASELINE_FILE_SHA256)
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


def _terminate_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait()
    except OSError:
        pass


def _run_bounded_scan(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[bytes]:
    """Run the scanner while bounding both captured streams in memory."""

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise SecurityScanError("cannot execute the tracked-tree secret scan") from exc

    if process.stdout is None or process.stderr is None:
        _terminate_and_reap(process)
        raise SecurityScanError("tracked-tree secret scan pipes are unavailable")

    outputs = {"report": bytearray(), "diagnostics": bytearray()}
    selector: selectors.BaseSelector | None = None
    deadline = time.monotonic() + timeout
    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "report")
        selector.register(process.stderr, selectors.EVENT_READ, "diagnostics")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            events = selector.select(remaining)
            if not events:
                raise subprocess.TimeoutExpired(command, timeout)
            for key, _ in events:
                label = str(key.data)
                buffer = outputs[label]
                remaining_bound = _MAX_REPORT_BYTES + 1 - len(buffer)
                read_size = min(_READ_CHUNK_BYTES, max(1, remaining_bound))
                chunk = os.read(key.fd, read_size)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffer.extend(chunk)
                if len(buffer) > _MAX_REPORT_BYTES:
                    _terminate_and_reap(process)
                    raise SecurityScanError(
                        f"tracked-tree secret scan {label} exceeds the bound"
                    )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        _terminate_and_reap(process)
        raise SecurityScanError("tracked-tree secret scan timed out") from exc
    except OSError as exc:
        _terminate_and_reap(process)
        raise SecurityScanError("cannot execute the tracked-tree secret scan") from exc
    finally:
        if selector is not None:
            selector.close()
        process.stdout.close()
        process.stderr.close()

    return subprocess.CompletedProcess(
        command,
        returncode,
        bytes(outputs["report"]),
        bytes(outputs["diagnostics"]),
    )


def _validated_candidate_paths(root: Path, paths: list[Path]) -> list[Path]:
    validated: list[Path] = []
    for relative in sorted(set(paths), key=lambda path: path.as_posix()):
        rendered = relative.as_posix()
        if (
            relative == Path(".")
            or not rendered.isprintable()
            or relative.is_absolute()
            or ".." in relative.parts
        ):
            raise SecurityScanError(
                f"tracked-tree secret scan has an unsafe candidate path: {rendered!r}"
            )

        current = root
        for part in relative.parts[:-1]:
            current /= part
            try:
                mode = current.lstat().st_mode
            except OSError as exc:
                raise SecurityScanError(
                    f"cannot inspect candidate path {rendered!r}: {exc}"
                ) from exc
            if stat.S_ISLNK(mode):
                raise SecurityScanError(
                    f"tracked-tree secret scan refuses symlink parent for {rendered!r}"
                )
            if not stat.S_ISDIR(mode):
                raise SecurityScanError(
                    f"candidate path parent is not a directory: {rendered!r}"
                )

        try:
            mode = (root / relative).lstat().st_mode
        except OSError as exc:
            raise SecurityScanError(
                f"cannot inspect candidate path {rendered!r}: {exc}"
            ) from exc
        if stat.S_ISLNK(mode):
            raise SecurityScanError(
                f"tracked-tree secret scan refuses symlinks: {rendered}"
            )
        if not stat.S_ISREG(mode):
            raise SecurityScanError(
                f"candidate path is not a regular file: {rendered!r}"
            )
        validated.append(relative)
    return validated


def _file_sha256(root: Path, relative: Path) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(root / relative, flags)
    except OSError as exc:
        raise SecurityScanError(
            f"cannot read protected baseline file {relative.as_posix()!r}"
        ) from exc
    try:
        with os.fdopen(descriptor, "rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise SecurityScanError(
            f"cannot read protected baseline file {relative.as_posix()!r}"
        ) from exc


def _verify_protected_baseline_files(
    root: Path,
    paths: list[Path],
    *,
    require_all: bool,
) -> None:
    rendered_paths = {path.as_posix() for path in paths}
    if require_all:
        missing = sorted(_ALLOWED_BASELINE_PATHS - rendered_paths)
        if missing:
            raise SecurityScanError(
                "tracked-tree secret scan is missing protected baseline files"
            )
    for rendered, expected in _PROTECTED_BASELINE_FILE_SHA256.items():
        if rendered not in rendered_paths:
            continue
        if _file_sha256(root, Path(rendered)) != expected:
            raise SecurityScanError(
                f"protected baseline file identity changed: {rendered}"
            )


def scan_tracked_tree(
    repository_root: Path,
    *,
    report_path: Path | None = None,
    baseline_path: Path = DEFAULT_BASELINE,
    tracked_paths: list[Path] | None = None,
) -> SecretScanResult:
    """Scan the exact tracked regular-file tree and apply the reviewed baseline."""

    root = repository_root.resolve()
    canonical_scan = tracked_paths is None
    if canonical_scan:
        try:
            paths = candidate_paths(root)
        except RepositoryScopeError as exc:
            raise SecurityScanError(
                f"cannot enumerate tracked-tree candidates: {exc}"
            ) from exc
    else:
        paths = list(tracked_paths)
    if not paths:
        raise SecurityScanError("tracked-tree secret scan has no candidate files")
    paths = _validated_candidate_paths(root, paths)
    _verify_protected_baseline_files(root, paths, require_all=canonical_scan)

    completed = _run_bounded_scan(
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
            "--",
            *(path.as_posix() for path in paths),
        ],
        cwd=root,
        timeout=_SCAN_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        raise SecurityScanError(
            f"tracked-tree secret scan returned status {completed.returncode}"
        )
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
