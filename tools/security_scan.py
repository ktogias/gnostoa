"""Fail-closed tracked-tree secret scanning with an audited exact baseline."""

from __future__ import annotations

import errno
import hashlib
import json
import math
import os
import re
import selectors
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

from tools.repository_scope import (
    REPOSITORY_SCOPE_ERROR_CATEGORIES,
    RepositoryScopeError,
    candidate_paths,
)

DEFAULT_BASELINE = Path(".secrets.baseline")
_MAX_REPORT_BYTES = 8_388_608
_READ_CHUNK_BYTES = 65_536
_SNAPSHOT_CHUNK_BYTES = 65_536
_MAX_SNAPSHOT_FILE_BYTES = 16_777_216
_MAX_SNAPSHOT_TOTAL_BYTES = 67_108_864
_SNAPSHOT_TIMEOUT_SECONDS = 60
_SCAN_TIMEOUT_SECONDS = 300
_PROCESS_REAP_TIMEOUT_SECONDS = 5
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
_BASELINE_TOP_LEVEL_KEYS = frozenset(
    {"version", "plugins_used", "filters_used", "results", "generated_at"}
)
_BASELINE_PLUGIN_KEYS = frozenset({"name", "limit", "keyword_exclude"})
_BASELINE_FILTER_KEYS = frozenset({"path", "pattern"})
_BASELINE_CANDIDATE_REQUIRED_KEYS = frozenset(
    {"type", "filename", "hashed_secret", "line_number"}
)
_BASELINE_CANDIDATE_OPTIONAL_KEYS = frozenset({"is_secret", "is_verified"})
_BASELINE_GENERATED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class SecurityScanError(RuntimeError):
    """The tracked-tree scan or its reviewed baseline is unusable."""


def _os_error_symbol(exc: OSError) -> str:
    """Return a closed-set symbolic errno without exception-controlled text."""

    return (
        errno.errorcode.get(exc.errno, "UNKNOWN")
        if type(exc.errno) is int
        else "UNKNOWN"
    )


def _safe_os_error(prefix: str, exc: OSError) -> str:
    return f"{prefix} (OS error: {_os_error_symbol(exc)})"


def _close_snapshot_descriptor(descriptor: int | None, role: str) -> str | None:
    """Close one snapshot descriptor without publishing exception-controlled text."""

    if descriptor is None:
        return None
    try:
        os.close(descriptor)
    except OSError as exc:
        return _safe_os_error(
            f"tracked-tree snapshot {role} descriptor could not be closed", exc
        )
    return None


@dataclass(frozen=True)
class SecretScanResult:
    """Sanitized result containing no candidate or candidate-derived hash."""

    reviewed_false_positives: int
    unresolved_findings: list[dict[str, int | str]]


SecretIdentity = tuple[str, str, str, int]


def _report_schema_error(label: str, detail: str) -> SecurityScanError:
    return SecurityScanError(f"{label} schema is invalid: {detail}")


def _object_without_duplicate_fields(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SecurityScanError("JSON document contains a duplicate field")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> NoReturn:
    raise SecurityScanError("JSON document contains a non-finite number")


def _strict_json_loads(raw: bytes | str) -> Any:
    document = json.loads(
        raw,
        object_pairs_hook=_object_without_duplicate_fields,
        parse_constant=_reject_non_finite_constant,
    )
    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, float) and not math.isfinite(value):
            raise SecurityScanError("JSON document contains a non-finite number")
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return document


def _is_finite_number(value: object) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_report_schema(document: dict[str, Any], *, label: str) -> None:
    if set(document) != _BASELINE_TOP_LEVEL_KEYS:
        raise _report_schema_error(label, "unexpected or missing top-level fields")

    generated_at = document.get("generated_at")
    if (
        not isinstance(generated_at, str)
        or _BASELINE_GENERATED_AT.fullmatch(generated_at) is None
    ):
        raise _report_schema_error(label, "generated_at is not a UTC timestamp")
    try:
        datetime.strptime(generated_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise _report_schema_error(
            label, "generated_at is not a valid timestamp"
        ) from exc

    plugins = document.get("plugins_used")
    if not isinstance(plugins, list):
        raise _report_schema_error(label, "plugins_used is not a list")
    for plugin in plugins:
        if (
            not isinstance(plugin, dict)
            or "name" not in plugin
            or not set(plugin) <= _BASELINE_PLUGIN_KEYS
            or not isinstance(plugin.get("name"), str)
            or not plugin["name"]
        ):
            raise _report_schema_error(label, "plugin entry is malformed")
        limit = plugin.get("limit")
        if limit is not None and not _is_finite_number(limit):
            raise _report_schema_error(label, "plugin limit is malformed")
        keyword_exclude = plugin.get("keyword_exclude")
        if keyword_exclude is not None and not isinstance(keyword_exclude, str):
            raise _report_schema_error(label, "plugin keyword exclusion is malformed")

    filters = document.get("filters_used")
    if not isinstance(filters, list):
        raise _report_schema_error(label, "filters_used is not a list")
    for filter_entry in filters:
        if (
            not isinstance(filter_entry, dict)
            or "path" not in filter_entry
            or not set(filter_entry) <= _BASELINE_FILTER_KEYS
            or not isinstance(filter_entry.get("path"), str)
            or not filter_entry["path"]
        ):
            raise _report_schema_error(label, "filter entry is malformed")
        pattern = filter_entry.get("pattern")
        if pattern is not None and (
            not isinstance(pattern, list)
            or any(not isinstance(item, str) for item in pattern)
        ):
            raise _report_schema_error(label, "filter pattern is malformed")

    results = document.get("results")
    if not isinstance(results, dict):
        raise _report_schema_error(label, "results is not a mapping")
    allowed_candidate_keys = (
        _BASELINE_CANDIDATE_REQUIRED_KEYS | _BASELINE_CANDIDATE_OPTIONAL_KEYS
    )
    for path, candidates in results.items():
        if not isinstance(path, str) or not isinstance(candidates, list):
            raise _report_schema_error(label, "result entry is malformed")
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or not _BASELINE_CANDIDATE_REQUIRED_KEYS <= set(candidate)
                or not set(candidate) <= allowed_candidate_keys
                or candidate.get("filename") != path
            ):
                raise _report_schema_error(label, "candidate entry is malformed")
            if "is_secret" in candidate and not isinstance(
                candidate["is_secret"], bool
            ):
                raise _report_schema_error(label, "candidate is_secret is malformed")
            if "is_verified" in candidate and candidate["is_verified"] is not False:
                raise _report_schema_error(label, "candidate is_verified is malformed")


def _validate_baseline_schema(document: dict[str, Any]) -> None:
    _validate_report_schema(document, label="detect-secrets baseline")


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
                or line > _MAX_SNAPSHOT_FILE_BYTES
            ):
                raise SecurityScanError(f"{label} candidate identity is malformed")
            if require_false_positive and candidate.get("is_secret") is not False:
                raise SecurityScanError(
                    f"{label} contains an entry not reviewed as a false positive"
                )
            identity = (path, candidate_type, secret_hash, line)
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

    _validate_baseline_schema(baseline_document)
    _validate_report_schema(scan_document, label="detect-secrets report")

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
        with path.open("rb") as stream:
            raw = stream.read(_MAX_REPORT_BYTES + 1)
        if len(raw) > _MAX_REPORT_BYTES:
            raise SecurityScanError(f"{label} exceeds the bounded size")
        document = _strict_json_loads(raw)
    except OSError as exc:
        raise SecurityScanError(_safe_os_error(f"cannot read {label}", exc)) from exc
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise SecurityScanError(f"cannot read {label}: invalid document") from exc
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
        process.wait(timeout=_PROCESS_REAP_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SecurityScanError(
            "tracked-tree secret scan child could not be reaped within the bound"
        ) from exc


def _reap_detail(process: subprocess.Popen[bytes]) -> str | None:
    """Reap the scanner child and report a bounded problem instead of raising.

    Reaping runs while a primary failure is already known, so a reap problem is
    secondary context and must never replace the pipe, bounded-size, timeout or
    I/O failure that triggered the abort.
    """

    try:
        _terminate_and_reap(process)
    except SecurityScanError as exc:
        return str(exc)
    return None


def _with_secondary(primary: str, secondary: str | None) -> str:
    """Keep the primary failure first and append bounded secondary context."""

    return primary if secondary is None else f"{primary}; {secondary}"


def _scanner_os_error(exc: OSError) -> str:
    """Classify OS failures without copying exception text or filenames."""

    return _safe_os_error("cannot execute the tracked-tree secret scan", exc)


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
            shell=False,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise SecurityScanError(_scanner_os_error(exc)) from exc

    if process.stdout is None or process.stderr is None:
        reap_detail = _reap_detail(process)
        close_issues = [reap_detail] if reap_detail is not None else []
        for role, stream in (
            ("stdout", process.stdout),
            ("stderr", process.stderr),
            ("stdin", process.stdin),
        ):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    close_issues.append(
                        f"tracked-tree secret scan {role} pipe could not be closed"
                    )
        raise SecurityScanError(
            _with_secondary(
                "tracked-tree secret scan pipes are unavailable",
                "; ".join(close_issues) or None,
            )
        )

    outputs = {"report": bytearray(), "diagnostics": bytearray()}
    selector: selectors.BaseSelector | None = None
    deadline = time.monotonic() + timeout
    execution_error: str | None = None
    execution_cause: Exception | None = None
    close_issues = []
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
                    raise SecurityScanError(
                        _with_secondary(
                            f"tracked-tree secret scan {label} exceeds the bound",
                            _reap_detail(process),
                        )
                    )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired as exc:
        execution_error = _with_secondary(
            "tracked-tree secret scan timed out", _reap_detail(process)
        )
        execution_cause = exc
    except OSError as exc:
        execution_error = _with_secondary(_scanner_os_error(exc), _reap_detail(process))
        execution_cause = exc
    except SecurityScanError as exc:
        execution_error = str(exc)
        execution_cause = exc
    finally:
        if selector is not None:
            try:
                selector.close()
            except OSError:
                close_issues.append(
                    "tracked-tree secret scan selector could not be closed"
                )
        for role, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            if not stream.closed:
                try:
                    stream.close()
                except OSError:
                    close_issues.append(
                        f"tracked-tree secret scan {role} pipe could not be closed"
                    )

    if execution_error is not None or close_issues:
        raise SecurityScanError(
            _with_secondary(
                execution_error
                or "tracked-tree secret scan process finalization failed",
                "; ".join(close_issues) or None,
            )
        ) from execution_cause

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
                    _safe_os_error(f"cannot inspect candidate path {rendered!r}", exc)
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
                _safe_os_error(f"cannot inspect candidate path {rendered!r}", exc)
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


def _stable_file_metadata(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _check_snapshot_deadline(deadline: float) -> None:
    """Check cooperative time; a blocked filesystem syscall is not interrupted."""

    if time.monotonic() >= deadline:
        raise SecurityScanError("tracked-tree snapshot timed out")


def _write_all(descriptor: int, content: bytes, *, deadline: float) -> None:
    offset = 0
    while offset < len(content):
        _check_snapshot_deadline(deadline)
        written = os.write(descriptor, content[offset:])
        _check_snapshot_deadline(deadline)
        if written <= 0:
            raise OSError("snapshot write made no progress")
        offset += written


def _copy_candidate_to_snapshot(
    root_descriptor: int,
    snapshot: Path,
    relative: Path,
    *,
    deadline: float,
    remaining_total_bytes: int,
) -> int:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    nonblock = getattr(os, "O_NONBLOCK", None)
    if nofollow is None or directory is None or nonblock is None:
        raise SecurityScanError(
            "tracked-tree snapshot requires O_NOFOLLOW, O_DIRECTORY and O_NONBLOCK"
        )

    parent_descriptor: int | None = None
    source_descriptor: int | None = None
    destination_descriptor: int | None = None
    current_parent_descriptor: int | None = None
    copied_bytes = 0
    primary_error: SecurityScanError | None = None
    primary_cause: Exception | None = None
    close_issues: list[str] = []
    try:
        parent_descriptor = os.dup(root_descriptor)
        for part in relative.parts[:-1]:
            next_descriptor = os.open(
                part,
                os.O_RDONLY | directory | nofollow,
                dir_fd=parent_descriptor,
            )
            previous_descriptor = parent_descriptor
            parent_descriptor = next_descriptor
            close_issue = _close_snapshot_descriptor(
                previous_descriptor, "parent traversal"
            )
            if close_issue is not None:
                raise SecurityScanError(close_issue)

        source_descriptor = os.open(
            relative.name,
            os.O_RDONLY | nofollow | nonblock,
            dir_fd=parent_descriptor,
        )
        before = os.fstat(source_descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise SecurityScanError(
                f"candidate path is not a regular file: {relative.as_posix()!r}"
            )
        if before.st_size > _MAX_SNAPSHOT_FILE_BYTES:
            raise SecurityScanError(
                f"candidate exceeds the snapshot file size bound: {relative.as_posix()!r}"
            )
        if before.st_size > remaining_total_bytes:
            raise SecurityScanError(
                "tracked-tree snapshot total size exceeds the bound"
            )

        destination = snapshot / relative
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
        )
        while True:
            _check_snapshot_deadline(deadline)
            chunk = os.read(source_descriptor, _SNAPSHOT_CHUNK_BYTES)
            _check_snapshot_deadline(deadline)
            if not chunk:
                break
            copied_bytes += len(chunk)
            if copied_bytes > _MAX_SNAPSHOT_FILE_BYTES:
                raise SecurityScanError(
                    f"candidate exceeds the snapshot file size bound: {relative.as_posix()!r}"
                )
            if copied_bytes > remaining_total_bytes:
                raise SecurityScanError(
                    "tracked-tree snapshot total size exceeds the bound"
                )
            _write_all(destination_descriptor, chunk, deadline=deadline)

        after = os.fstat(source_descriptor)
        visible = os.stat(
            relative.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        current_parent_descriptor = os.dup(root_descriptor)
        for part in relative.parts[:-1]:
            next_descriptor = os.open(
                part,
                os.O_RDONLY | directory | nofollow,
                dir_fd=current_parent_descriptor,
            )
            previous_descriptor = current_parent_descriptor
            current_parent_descriptor = next_descriptor
            close_issue = _close_snapshot_descriptor(
                previous_descriptor, "current-parent traversal"
            )
            if close_issue is not None:
                raise SecurityScanError(close_issue)
        current_visible = os.stat(
            relative.name,
            dir_fd=current_parent_descriptor,
            follow_symlinks=False,
        )
        if (
            _stable_file_metadata(before) != _stable_file_metadata(after)
            or _stable_file_metadata(after) != _stable_file_metadata(visible)
            or _stable_file_metadata(after) != _stable_file_metadata(current_visible)
        ):
            raise SecurityScanError(
                f"candidate path changed while snapshotting: {relative.as_posix()!r}"
            )
        _check_snapshot_deadline(deadline)
    except SecurityScanError as exc:
        primary_error = exc
    except OSError as exc:
        primary_error = SecurityScanError(
            _safe_os_error(
                f"cannot snapshot candidate path {relative.as_posix()!r}", exc
            )
        )
        primary_cause = exc
    finally:
        for role, descriptor in (
            ("current-parent", current_parent_descriptor),
            ("destination", destination_descriptor),
            ("source", source_descriptor),
            ("parent", parent_descriptor),
        ):
            close_issue = _close_snapshot_descriptor(descriptor, role)
            if close_issue is not None:
                close_issues.append(close_issue)

    secondary = "; ".join(close_issues) or None
    if primary_error is not None:
        if secondary is not None:
            raise SecurityScanError(
                _with_secondary(str(primary_error), secondary)
            ) from primary_error
        if primary_cause is not None:
            raise primary_error from primary_cause
        raise primary_error
    if secondary is not None:
        raise SecurityScanError(
            _with_secondary("tracked-tree snapshot finalization failed", secondary)
        )
    return copied_bytes


@contextmanager
def _immutable_candidate_snapshot(
    root: Path,
    paths: list[Path],
) -> Iterator[Path]:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise SecurityScanError(
            "tracked-tree snapshot requires O_NOFOLLOW and O_DIRECTORY"
        )

    try:
        root_descriptor = os.open(root, os.O_RDONLY | directory | nofollow)
    except OSError as exc:
        raise SecurityScanError("cannot open the tracked-tree root safely") from exc

    primary_error: SecurityScanError | None = None
    primary_cause: Exception | None = None
    workspace: tempfile.TemporaryDirectory[str] | None = None
    finalization_issues: list[str] = []
    try:
        workspace = tempfile.TemporaryDirectory(prefix="gnostoa-secret-scan-")
        snapshot = Path(workspace.name)
        deadline = time.monotonic() + _SNAPSHOT_TIMEOUT_SECONDS
        total_bytes = 0
        for relative in paths:
            _check_snapshot_deadline(deadline)
            copied_bytes = _copy_candidate_to_snapshot(
                root_descriptor,
                snapshot,
                relative,
                deadline=deadline,
                remaining_total_bytes=_MAX_SNAPSHOT_TOTAL_BYTES - total_bytes,
            )
            total_bytes += copied_bytes
            _check_snapshot_deadline(deadline)
        _check_snapshot_deadline(deadline)
        yield snapshot
    except SecurityScanError as exc:
        primary_error = exc
    except OSError as exc:
        primary_error = SecurityScanError(
            _safe_os_error("tracked-tree snapshot workspace failed", exc)
        )
        primary_cause = exc
    finally:
        if workspace is not None:
            try:
                workspace.cleanup()
            except OSError as exc:
                finalization_issues.append(
                    _safe_os_error(
                        "tracked-tree snapshot workspace could not be removed", exc
                    )
                )
        close_issue = _close_snapshot_descriptor(root_descriptor, "root")
        if close_issue is not None:
            finalization_issues.append(close_issue)

    secondary = "; ".join(finalization_issues) or None
    if primary_error is not None:
        if secondary is not None:
            raise SecurityScanError(
                _with_secondary(str(primary_error), secondary)
            ) from primary_error
        if primary_cause is not None:
            raise primary_error from primary_cause
        raise primary_error
    if secondary is not None:
        raise SecurityScanError(
            _with_secondary("tracked-tree snapshot finalization failed", secondary)
        )


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
    if tracked_paths is None:
        try:
            paths = candidate_paths(root)
        except RepositoryScopeError as exc:
            category = (
                exc.category
                if exc.category in REPOSITORY_SCOPE_ERROR_CATEGORIES
                else "UNKNOWN"
            )
            raise SecurityScanError(
                "cannot enumerate tracked-tree candidates "
                f"(scope error: {category})"
            ) from exc
    else:
        paths = list(tracked_paths)
    if not paths:
        raise SecurityScanError("tracked-tree secret scan has no candidate files")
    paths = _validated_candidate_paths(root, paths)
    snapshot_paths = list(paths)
    relative_baseline: Path | None = None
    if not baseline_path.is_absolute():
        relative_baseline = _validated_candidate_paths(root, [baseline_path])[0]
        if relative_baseline not in snapshot_paths:
            if canonical_scan:
                raise SecurityScanError(
                    "detect-secrets baseline is outside the canonical candidate set"
                )
            snapshot_paths.append(relative_baseline)

    baseline_document: dict[str, Any] | None = None
    if baseline_path.is_absolute():
        baseline_document = _read_document(
            baseline_path,
            "detect-secrets baseline",
        )

    with _immutable_candidate_snapshot(root, snapshot_paths) as snapshot:
        scan_paths = _validated_candidate_paths(snapshot, paths)
        _verify_protected_baseline_files(
            snapshot,
            scan_paths,
            require_all=canonical_scan,
        )
        if relative_baseline is not None:
            baseline_document = _read_document(
                snapshot / relative_baseline,
                "detect-secrets baseline",
            )

        completed = _run_bounded_scan(
            [
                sys.executable,
                "-I",
                "-m",
                "detect_secrets",
                "--cores",
                "1",
                "scan",
                "--no-verify",
                "--exclude-files",
                _BASELINE_EXCLUDE_PATTERN,
                "--",
                *(path.as_posix() for path in scan_paths),
            ],
            cwd=snapshot,
            timeout=_SCAN_TIMEOUT_SECONDS,
        )
    if completed.returncode != 0:
        raise SecurityScanError(
            f"tracked-tree secret scan returned status {completed.returncode}"
        )
    try:
        scan_document = _strict_json_loads(completed.stdout)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise SecurityScanError(
            "tracked-tree secret scan returned invalid JSON"
        ) from exc
    if not isinstance(scan_document, dict):
        raise SecurityScanError("tracked-tree secret scan report is not an object")
    if baseline_document is None:
        raise SecurityScanError("detect-secrets baseline was not acquired")
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
