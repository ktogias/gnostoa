from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess  # nosec B404 -- audited subprocess boundary in _run
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "gnostoa-candidate-preparation-receipt/v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_GIT = shutil.which("git")
_GIT_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_INDEX_FILE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)
_FOCUSED_PROFILES = (
    "policy",
    "security-fast",
    "fast",
    "regression",
    "smoke",
    "extended",
)


class PrepareError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _digest(value: object) -> str:
    encoded = _canonical_json(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _git_executable() -> str:
    if _GIT is None:
        raise PrepareError("git executable is unavailable")
    return _GIT


def _base_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in _GIT_ENVIRONMENT_VARIABLES:
        env.pop(name, None)
    return env


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    if env is None:
        env = _base_env()
    # Every command is passed as an argv vector with shell=False. Git and
    # repository-owned verification commands are locally resolved. Candidate
    # preparation accepts only a closed focused profile at both the CLI and
    # implementation-private API boundaries; callers cannot supply executable
    # paths or arbitrary subprocess arguments.
    completed = subprocess.run(  # nosemgrep  # nosec B603
        list(command),
        cwd=cwd,
        env=env,
        check=False,
        shell=False,
        capture_output=True,
    )
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        detail = f": {stderr}" if stderr else ""
        raise PrepareError(f"command failed ({completed.returncode}){detail}")
    return completed


def _git_text(
    root: Path,
    *arguments: str,
    env: dict[str, str] | None = None,
) -> str:
    completed = _run([_git_executable(), *arguments], cwd=root, env=env)
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _repository_root() -> Path:
    completed = _run(
        [_git_executable(), "rev-parse", "--show-toplevel"],
        cwd=Path.cwd(),
    )
    return Path(completed.stdout.decode("utf-8", errors="strict").strip()).resolve()


def _ruff_version(root: Path) -> str:
    completed = _run(
        [sys.executable, "-m", "ruff", "--version"],
        cwd=root,
    )
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _assert_external_receipt(root: Path, receipt: Path) -> Path:
    resolved_root = root.resolve()
    resolved = receipt.expanduser().resolve()
    if resolved == resolved_root or resolved_root in resolved.parents:
        raise PrepareError("receipt path must be outside the repository worktree")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _focused_profile_command(root: Path, profile: str) -> tuple[str, ...]:
    verify = (root / "ci" / "verify").resolve()
    if not verify.is_file():
        raise PrepareError("ci/verify is unavailable")
    if profile == "policy":
        return (str(verify), "policy")
    if profile == "security-fast":
        return (str(verify), "security-fast")
    if profile == "fast":
        return (str(verify), "fast")
    if profile == "regression":
        return (str(verify), "regression")
    if profile == "smoke":
        return (str(verify), "smoke")
    if profile == "extended":
        return (str(verify), "extended")
    raise PrepareError("unsupported focused verification profile")


def _focused_receipt_command(profile: str) -> tuple[str, ...]:
    if profile == "policy":
        return ("ci/verify", "policy")
    if profile == "security-fast":
        return ("ci/verify", "security-fast")
    if profile == "fast":
        return ("ci/verify", "fast")
    if profile == "regression":
        return ("ci/verify", "regression")
    if profile == "smoke":
        return ("ci/verify", "smoke")
    if profile == "extended":
        return ("ci/verify", "extended")
    raise PrepareError("unsupported focused verification profile")


def _assert_head(root: Path, parent: str) -> None:
    head = _git_text(root, "rev-parse", "HEAD")
    if head != parent:
        raise PrepareError(f"stale parent: HEAD is {head}, expected {parent}")


def _stage_candidate(root: Path, parent: str, index: Path) -> tuple[str, list[str]]:
    env = _base_env()
    env["GIT_INDEX_FILE"] = str(index)
    if not index.exists():
        _git_text(root, "read-tree", parent, env=env)
    _git_text(root, "add", "-A", env=env)
    tree = _git_text(root, "write-tree", env=env)
    changed_raw = _run(
        [_git_executable(), "diff", "--cached", "--name-only", "-z", parent],
        cwd=root,
        env=env,
    ).stdout
    changed = sorted(os.fsdecode(item) for item in changed_raw.split(b"\0") if item)
    return tree, changed


def _binary_diff(root: Path, parent: str, index: Path) -> bytes:
    env = _base_env()
    env["GIT_INDEX_FILE"] = str(index)
    return _run(
        [
            _git_executable(),
            "diff",
            "--cached",
            "--binary",
            "--full-index",
            parent,
        ],
        cwd=root,
        env=env,
    ).stdout


def _write_receipt(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    document = dict(payload)
    document["receipt_sha256"] = _digest(payload)
    encoded = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return document


def prepare(
    parent_commit: str,
    receipt_path: Path,
    focused_profile: str,
) -> dict[str, Any]:
    if _SHA40.fullmatch(parent_commit) is None:
        raise PrepareError("parent must be an exact 40-character commit SHA")

    root = _repository_root()
    focused_argv = _focused_profile_command(root, focused_profile)
    focused_receipt_argv = _focused_receipt_command(focused_profile)
    receipt = _assert_external_receipt(root, receipt_path)
    _assert_head(root, parent_commit)
    parent_tree = _git_text(root, "rev-parse", f"{parent_commit}^{{tree}}")
    style = root / "ci" / "style"
    if not style.is_file():
        raise PrepareError("ci/style is unavailable")

    with tempfile.TemporaryDirectory(prefix="gnostoa-candidate-index-") as directory:
        index = Path(directory) / "index"
        proposed_tree, proposed_paths = _stage_candidate(root, parent_commit, index)
        if not proposed_paths:
            raise PrepareError("candidate has no changes relative to parent")

        env = _base_env()
        env["GIT_INDEX_FILE"] = str(index)
        _run([str(style), "--fix"], cwd=root, env=env)
        _assert_head(root, parent_commit)
        normalized_tree, changed_paths = _stage_candidate(root, parent_commit, index)
        if not changed_paths:
            raise PrepareError("candidate has no changes after normalization")

        focused = _run(focused_argv, cwd=root, env=env, check=False)
        if focused.returncode != 0:
            stderr = focused.stderr.decode("utf-8", errors="replace").strip()
            detail = f": {stderr}" if stderr else ""
            raise PrepareError(
                f"focused verification failed ({focused.returncode}){detail}"
            )
        _assert_head(root, parent_commit)
        after_focused, _ = _stage_candidate(root, parent_commit, index)
        if after_focused != normalized_tree:
            raise PrepareError("focused verification mutated candidate")

        _run([str(style), "--check"], cwd=root, env=env)
        _assert_head(root, parent_commit)
        after_check, changed_paths = _stage_candidate(root, parent_commit, index)
        if after_check != normalized_tree:
            raise PrepareError("style check mutated candidate")
        _run(
            [_git_executable(), "diff", "--cached", "--check", parent_commit],
            cwd=root,
            env=env,
        )
        prepared_diff = _binary_diff(root, parent_commit, index)

    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "parent_commit": parent_commit,
        "parent_tree": parent_tree,
        "prepared_tree": normalized_tree,
        "prepared_diff_sha256": _sha256_bytes(prepared_diff),
        "changed_paths": changed_paths,
        "style_sha256": _sha256_bytes(style.read_bytes()),
        "style_subject": ".",
        "ruff_version": _ruff_version(root),
        "focused_profile": focused_profile,
        "focused_command": list(focused_receipt_argv),
        "checks": {
            "style_fix": 0,
            "focused_verification": focused.returncode,
            "style_check": 0,
            "diff_check": 0,
        },
        "metric_event": (
            "PRE_CANDIDATE_RUFF_CATCH"
            if proposed_tree != normalized_tree
            else "PRE_CANDIDATE_NO_RUFF_CHANGE"
        ),
    }
    return _write_receipt(receipt, payload)


def _load_receipt(receipt_path: Path) -> dict[str, Any]:
    try:
        document = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrepareError("receipt is unreadable or invalid JSON") from exc
    if not isinstance(document, dict):
        raise PrepareError("receipt must be a JSON object")
    return document


def _validate_receipt_digest(document: dict[str, Any]) -> None:
    digest = document.get("receipt_sha256")
    payload = {key: value for key, value in document.items() if key != "receipt_sha256"}
    if not isinstance(digest, str) or digest != _digest(payload):
        raise PrepareError("receipt digest mismatch")


def _require_sha40(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
        raise PrepareError(f"receipt {key} is invalid")
    return value


def _require_sha256(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PrepareError(f"receipt {key} is invalid")
    return value


def _validate_receipt_checks(document: dict[str, Any]) -> None:
    expected = {
        "style_fix": 0,
        "focused_verification": 0,
        "style_check": 0,
        "diff_check": 0,
    }
    if document.get("checks") != expected:
        raise PrepareError("receipt check state is not successful")


def _validate_receipt_focused_command(document: dict[str, Any]) -> None:
    profile = document.get("focused_profile")
    if not isinstance(profile, str):
        raise PrepareError("receipt focused profile is invalid")
    if document.get("focused_command") != list(_focused_receipt_command(profile)):
        raise PrepareError("receipt focused command is invalid")


def _validate_receipt_metric(document: dict[str, Any]) -> None:
    if document.get("metric_event") not in {
        "PRE_CANDIDATE_RUFF_CATCH",
        "PRE_CANDIDATE_NO_RUFF_CHANGE",
    }:
        raise PrepareError("receipt metric event is invalid")


def verify_receipt(
    receipt_path: Path,
    expected_parent: str,
    expected_tree: str,
) -> dict[str, Any]:
    document = _load_receipt(receipt_path)
    _validate_receipt_digest(document)
    if document.get("schema") != RECEIPT_SCHEMA:
        raise PrepareError("receipt schema mismatch")
    if document.get("parent_commit") != expected_parent:
        raise PrepareError("parent mismatch")
    if document.get("prepared_tree") != expected_tree:
        raise PrepareError("tree mismatch")
    _validate_receipt_checks(document)
    _validate_receipt_focused_command(document)
    _require_sha40(document, "parent_tree")
    _require_sha40(document, "prepared_tree")
    _require_sha256(document, "prepared_diff_sha256")
    _require_sha256(document, "style_sha256")
    _validate_receipt_metric(document)
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or verify a normalized Gnostoa candidate tree."
    )
    actions = parser.add_subparsers(dest="action", required=True)

    prepare_parser = actions.add_parser("prepare")
    prepare_parser.add_argument("--parent", required=True)
    prepare_parser.add_argument("--receipt", required=True, type=Path)
    prepare_parser.add_argument(
        "--focused-profile",
        required=True,
        choices=_FOCUSED_PROFILES,
    )

    verify_parser = actions.add_parser("verify")
    verify_parser.add_argument("--parent", required=True)
    verify_parser.add_argument("--tree", required=True)
    verify_parser.add_argument("--receipt", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.action == "verify":
            document = verify_receipt(
                arguments.receipt,
                arguments.parent,
                arguments.tree,
            )
        else:
            document = prepare(
                arguments.parent,
                arguments.receipt,
                arguments.focused_profile,
            )
    except PrepareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(_canonical_json(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
