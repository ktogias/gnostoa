"""Durable one-shot claims for fresh preflight qualification effects.

A v2 preflight authority proves that an owner approved one exact prepared
candidate. This module adds the separate retained-workspace fact that a fresh
candidate has already opened its one permitted qualification transaction.

The record is intentionally not a stage receipt. Stage completion is resumable;
preflight effect consumption is irreversible once durably claimed.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from tools.capsule.authority import PreflightAuthority, parse
from tools.capsule.identity import digest_of
from tools.experiment.evidence import canonical_json_bytes

CLAIM_SCHEMA = "gnostoa-preflight-effect-claim/v1"
CLAIM_DIRECTORY = "preflight-effects"
ALREADY_CONSUMED = "preflight-candidate-already-consumed"
INVALID_CLAIM = "preflight-effect-claim-invalid"
WRITE_FAILED = "preflight-effect-claim-write-failed"

_MAX_CLAIM_BYTES = 64 * 1024
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class EffectClaimError(RuntimeError):
    """A fresh effect claim could not be safely established or was already spent."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        left.st_dev == right.st_dev
        and left.st_ino == right.st_ino
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def _disposition_summary(
    candidate_tasks: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in candidate_tasks:
        task_id = entry.get("id")
        mode = entry.get("qualification_mode")
        if not task_id or task_id in seen or mode not in {"fresh", "reuse"}:
            raise EffectClaimError(
                INVALID_CLAIM,
                "candidate disposition is malformed; refusing to infer effect consumption",
            )
        seen.add(task_id)
        summary.append({"id": task_id, "qualification_mode": mode})
    if not summary or not any(
        item["qualification_mode"] == "fresh" for item in summary
    ):
        raise EffectClaimError(
            INVALID_CLAIM,
            "an effect claim may be created only for a candidate containing a fresh task",
        )
    return summary


def _open_visible_directory(path: Path, *, label: str) -> int:
    try:
        observed = os.stat(path, follow_symlinks=False)
        if not stat.S_ISDIR(observed.st_mode):
            raise EffectClaimError(INVALID_CLAIM, f"{label} is not a directory")
        descriptor = os.open(path, os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW)
        identity = os.fstat(descriptor)
    except EffectClaimError:
        raise
    except OSError as exc:
        raise EffectClaimError(WRITE_FAILED, f"cannot open {label}: {exc}") from exc
    if not stat.S_ISDIR(identity.st_mode) or not _same_object(observed, identity):
        os.close(descriptor)
        raise EffectClaimError(
            INVALID_CLAIM, f"{label} namespace changed while opening"
        )
    return descriptor


def _open_existing_claim_directory(root_fd: int) -> int:
    try:
        observed = os.stat(CLAIM_DIRECTORY, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise EffectClaimError(
            INVALID_CLAIM,
            f"retained {CLAIM_DIRECTORY} directory is missing for a completed fresh qualification",
        ) from exc
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"cannot inspect retained {CLAIM_DIRECTORY}: {exc}"
        ) from exc
    if not stat.S_ISDIR(observed.st_mode):
        raise EffectClaimError(
            INVALID_CLAIM, f"{CLAIM_DIRECTORY} exists but is not a directory"
        )

    try:
        descriptor = os.open(
            CLAIM_DIRECTORY,
            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW,
            dir_fd=root_fd,
        )
        identity = os.fstat(descriptor)
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"cannot safely open retained {CLAIM_DIRECTORY}: {exc}"
        ) from exc
    if not stat.S_ISDIR(identity.st_mode) or not _same_object(observed, identity):
        os.close(descriptor)
        raise EffectClaimError(
            INVALID_CLAIM, f"{CLAIM_DIRECTORY} namespace changed while opening"
        )
    return descriptor


def _open_claim_directory(root_fd: int) -> int:
    created = False
    try:
        os.mkdir(CLAIM_DIRECTORY, 0o700, dir_fd=root_fd)
        created = True
    except FileExistsError:
        pass
    except OSError as exc:
        raise EffectClaimError(
            WRITE_FAILED, f"cannot create {CLAIM_DIRECTORY}: {exc}"
        ) from exc

    try:
        observed = os.stat(CLAIM_DIRECTORY, dir_fd=root_fd, follow_symlinks=False)
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"cannot inspect {CLAIM_DIRECTORY}: {exc}"
        ) from exc
    if not stat.S_ISDIR(observed.st_mode):
        raise EffectClaimError(
            INVALID_CLAIM, f"{CLAIM_DIRECTORY} exists but is not a directory"
        )

    try:
        descriptor = os.open(
            CLAIM_DIRECTORY,
            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW,
            dir_fd=root_fd,
        )
        identity = os.fstat(descriptor)
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"cannot safely open {CLAIM_DIRECTORY}: {exc}"
        ) from exc
    if not stat.S_ISDIR(identity.st_mode) or not _same_object(observed, identity):
        os.close(descriptor)
        raise EffectClaimError(
            INVALID_CLAIM, f"{CLAIM_DIRECTORY} namespace changed while opening"
        )
    if created:
        try:
            os.fsync(root_fd)
        except OSError as exc:
            os.close(descriptor)
            raise EffectClaimError(
                WRITE_FAILED,
                f"cannot durably retain {CLAIM_DIRECTORY} directory entry: {exc}",
            ) from exc
    return descriptor


def _read_existing_claim(directory_fd: int, name: str) -> bytes | None:
    try:
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"cannot inspect existing claim: {exc}"
        ) from exc
    if not stat.S_ISREG(observed.st_mode):
        raise EffectClaimError(
            INVALID_CLAIM, "the candidate claim path exists but is not a regular file"
        )

    try:
        descriptor = os.open(name, os.O_RDONLY | _O_NOFOLLOW, dir_fd=directory_fd)
        identity = os.fstat(descriptor)
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"cannot safely open existing candidate claim: {exc}"
        ) from exc
    try:
        if not stat.S_ISREG(identity.st_mode) or not _same_object(observed, identity):
            raise EffectClaimError(
                INVALID_CLAIM, "the candidate claim namespace changed while opening"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(8192, _MAX_CLAIM_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > _MAX_CLAIM_BYTES:
                raise EffectClaimError(
                    INVALID_CLAIM, "the candidate claim is oversized"
                )
        payload = b"".join(chunks)
    finally:
        os.close(descriptor)

    try:
        visible = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except OSError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"the candidate claim namespace changed after reading: {exc}"
        ) from exc
    if not _same_object(observed, visible):
        raise EffectClaimError(
            INVALID_CLAIM, "the candidate claim namespace changed while reading"
        )
    return payload


def _validate_existing_claim(
    data: bytes,
    *,
    experiment_id: str,
    scope: str,
    candidate_sha256: str,
    disposition: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"candidate claim is not valid JSON: {exc}"
        ) from exc
    if not isinstance(decoded, dict):
        raise EffectClaimError(INVALID_CLAIM, "candidate claim must be a JSON object")
    payload = cast(dict[str, Any], decoded)
    expected_keys = {
        "schema",
        "experiment_id",
        "scope",
        "preflight_candidate_sha256",
        "authority",
        "authority_sha256",
        "qualification_disposition",
    }
    if set(payload) != expected_keys:
        raise EffectClaimError(
            INVALID_CLAIM, "candidate claim has unexpected or missing fields"
        )
    if canonical_json_bytes(payload) != data:
        raise EffectClaimError(INVALID_CLAIM, "candidate claim bytes are not canonical")
    if payload.get("schema") != CLAIM_SCHEMA:
        raise EffectClaimError(
            INVALID_CLAIM, "candidate claim uses an unsupported schema"
        )
    if (
        payload.get("experiment_id") != experiment_id
        or payload.get("scope") != scope
        or payload.get("preflight_candidate_sha256") != candidate_sha256
    ):
        raise EffectClaimError(
            INVALID_CLAIM, "candidate claim identity does not match its path"
        )
    if payload.get("qualification_disposition") != list(disposition):
        raise EffectClaimError(
            INVALID_CLAIM, "candidate claim disposition does not match"
        )

    authority_payload = payload.get("authority")
    if not isinstance(authority_payload, dict):
        raise EffectClaimError(INVALID_CLAIM, "candidate claim authority is malformed")
    authority_dict = cast(dict[str, Any], authority_payload)
    if payload.get("authority_sha256") != digest_of(authority_dict):
        raise EffectClaimError(
            INVALID_CLAIM, "candidate claim authority digest does not match"
        )
    try:
        authority = parse(authority_dict)
    except ValueError as exc:
        raise EffectClaimError(
            INVALID_CLAIM, f"candidate claim authority is invalid: {exc}"
        ) from exc
    if not authority.covers(experiment_id, scope, candidate_sha256=candidate_sha256):
        raise EffectClaimError(
            INVALID_CLAIM, "candidate claim authority does not cover the claim"
        )
    return payload


def load_consumed_candidate(
    workspace: Path,
    *,
    experiment_id: str,
    scope: str,
    candidate_sha256: str,
    candidate_tasks: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """Read and validate the irreversible claim for one completed fresh candidate."""
    disposition = _disposition_summary(candidate_tasks)
    name = f"{candidate_sha256}.json"

    root_fd = _open_visible_directory(workspace, label="retained workspace")
    try:
        claim_fd = _open_existing_claim_directory(root_fd)
        try:
            existing = _read_existing_claim(claim_fd, name)
            if existing is None:
                raise EffectClaimError(
                    INVALID_CLAIM,
                    f"completed fresh candidate {candidate_sha256} has no retained effect claim",
                )
            return dict(
                _validate_existing_claim(
                    existing,
                    experiment_id=experiment_id,
                    scope=scope,
                    candidate_sha256=candidate_sha256,
                    disposition=disposition,
                )
            )
        finally:
            os.close(claim_fd)
    finally:
        os.close(root_fd)


def _raise_if_existing(
    directory_fd: int,
    name: str,
    *,
    experiment_id: str,
    scope: str,
    candidate_sha256: str,
    disposition: Sequence[Mapping[str, str]],
) -> None:
    existing = _read_existing_claim(directory_fd, name)
    if existing is None:
        return
    _validate_existing_claim(
        existing,
        experiment_id=experiment_id,
        scope=scope,
        candidate_sha256=candidate_sha256,
        disposition=disposition,
    )
    raise EffectClaimError(
        ALREADY_CONSUMED,
        f"preflight candidate {candidate_sha256} already opened its fresh qualification transaction",
    )


def claim_fresh_candidate(
    workspace: Path,
    *,
    experiment_id: str,
    scope: str,
    candidate_sha256: str,
    authority: PreflightAuthority,
    candidate_tasks: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """Durably consume one fresh candidate before any qualification effect begins."""
    disposition = _disposition_summary(candidate_tasks)
    authority_payload = authority.as_json()
    payload: dict[str, object] = {
        "schema": CLAIM_SCHEMA,
        "experiment_id": experiment_id,
        "scope": scope,
        "preflight_candidate_sha256": candidate_sha256,
        "authority": authority_payload,
        "authority_sha256": digest_of(authority_payload),
        "qualification_disposition": disposition,
    }
    data = canonical_json_bytes(payload)
    name = f"{candidate_sha256}.json"

    root_fd = _open_visible_directory(workspace, label="retained workspace")
    try:
        claim_fd = _open_claim_directory(root_fd)
        try:
            _raise_if_existing(
                claim_fd,
                name,
                experiment_id=experiment_id,
                scope=scope,
                candidate_sha256=candidate_sha256,
                disposition=disposition,
            )
            try:
                destination = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW,
                    0o600,
                    dir_fd=claim_fd,
                )
            except FileExistsError as exc:
                _raise_if_existing(
                    claim_fd,
                    name,
                    experiment_id=experiment_id,
                    scope=scope,
                    candidate_sha256=candidate_sha256,
                    disposition=disposition,
                )
                raise EffectClaimError(
                    INVALID_CLAIM,
                    "candidate claim appeared concurrently but cannot be trusted",
                ) from exc
            except OSError as exc:
                raise EffectClaimError(
                    WRITE_FAILED, f"cannot create candidate claim: {exc}"
                ) from exc

            write_error: OSError | None = None
            try:
                view = memoryview(data)
                while view:
                    written = os.write(destination, view)
                    if written <= 0:
                        raise OSError("short candidate-claim write")
                    view = view[written:]
                os.fsync(destination)
            except OSError as exc:
                write_error = exc
            finally:
                try:
                    os.close(destination)
                except OSError as exc:
                    write_error = write_error or exc
            if write_error is not None:
                # Leave any partial file in place. Ambiguous persistence must never be
                # repaired into permission to retry a prospective effect.
                raise EffectClaimError(
                    WRITE_FAILED, f"cannot durably write candidate claim: {write_error}"
                ) from write_error
            try:
                os.fsync(claim_fd)
            except OSError as exc:
                raise EffectClaimError(
                    WRITE_FAILED,
                    f"cannot durably retain candidate claim directory entry: {exc}",
                ) from exc
        finally:
            os.close(claim_fd)
    finally:
        os.close(root_fd)
    return payload
