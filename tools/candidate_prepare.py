from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

RECEIPT_SCHEMA = "gnostoa-candidate-preparation-receipt/v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_GIT = shutil.which("git")


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


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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


def _stage_candidate(root: Path, parent: str, index: Path) -> tuple[str, list[str]]:
    env = dict(os.environ)
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
    changed = sorted(
        os.fsdecode(item)
        for item in changed_raw.split(b"\0")
        if item
    )
    return tree, changed


def _binary_diff(root: Path, parent: str, index: Path) -> bytes:
    env = dict(os.environ)
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
    focused_command: Sequence[str],
) -> dict[str, Any]:
    if _SHA40.fullmatch(parent_commit) is None:
        raise PrepareError("parent must be an exact 40-character commit SHA")
    if not focused_command or not all(
        isinstance(item, str) and item for item in focused_command
    ):
        raise PrepareError(
            "focused verification command must be a non-empty argv vector"
        )

    root = _repository_root()
    receipt = _assert_external_receipt(root, receipt_path)
    head = _git_text(root, "rev-parse", "HEAD")
    if head != parent_commit:
        raise PrepareError(f"stale parent: HEAD is {head}, expected {parent_commit}")
    parent_tree = _git_text(root, "rev-parse", f"{parent_commit}^{{tree}}")
    style = root / "ci" / "style"
    if not style.is_file():
        raise PrepareError("ci/style is unavailable")

    with tempfile.TemporaryDirectory(prefix="gnostoa-candidate-index-") as directory:
        index = Path(directory) / "index"
        proposed_tree, proposed_paths = _stage_candidate(root, parent_commit, index)
        if not proposed_paths:
            raise PrepareError("candidate has no changes relative to parent")

        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(index)
        _run([str(style), "--fix"], cwd=root, env=env)
        normalized_tree, changed_paths = _stage_candidate(root, parent_commit, index)
        if not changed_paths:
            raise PrepareError("candidate has no changes after normalization")

        before_focused = normalized_tree
        focused = _run(focused_command, cwd=root, env=env, check=False)
        if focused.returncode != 0:
            stderr = focused.stderr.decode("utf-8", errors="replace").strip()
            detail = f": {stderr}" if stderr else ""
            raise PrepareError(
                f"focused verification failed ({focused.returncode}){detail}"
            )
        after_focused, _ = _stage_candidate(root, parent_commit, index)
        if after_focused != before_focused:
            raise PrepareError("focused verification mutated candidate")

        _run([str(style), "--check"], cwd=root, env=env)
        after_check, changed_paths = _stage_candidate(root, parent_commit, index)
        if after_check != before_focused:
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
        "prepared_tree": before_focused,
        "prepared_diff_sha256": _sha256_bytes(prepared_diff),
        "changed_paths": changed_paths,
        "style_sha256": _sha256_bytes(style.read_bytes()),
        "style_subject": ".",
        "ruff_version": _ruff_version(root),
        "focused_command": list(focused_command),
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


def verify_receipt(
    receipt_path: Path,
    expected_parent: str,
    expected_tree: str,
) -> dict[str, Any]:
    try:
        document = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrepareError("receipt is unreadable or invalid JSON") from exc
    if not isinstance(document, dict):
        raise PrepareError("receipt must be a JSON object")
    digest = document.get("receipt_sha256")
    payload = {key: value for key, value in document.items() if key != "receipt_sha256"}
    if not isinstance(digest, str) or digest != _digest(payload):
        raise PrepareError("receipt digest mismatch")
    if document.get("schema") != RECEIPT_SCHEMA:
        raise PrepareError("receipt schema mismatch")
    if document.get("parent_commit") != expected_parent:
        raise PrepareError("parent mismatch")
    if document.get("prepared_tree") != expected_tree:
        raise PrepareError("tree mismatch")
    checks = document.get("checks")
    if checks != {
        "style_fix": 0,
        "focused_verification": 0,
        "style_check": 0,
        "diff_check": 0,
    }:
        raise PrepareError("receipt check state is not successful")
    focused_command = document.get("focused_command")
    if not isinstance(focused_command, list) or not focused_command or not all(
        isinstance(item, str) and item for item in focused_command
    ):
        raise PrepareError("receipt focused command is invalid")
    for key in ("parent_tree", "prepared_tree"):
        value = document.get(key)
        if not isinstance(value, str) or _SHA40.fullmatch(value) is None:
            raise PrepareError(f"receipt {key} is invalid")
    for key in ("prepared_diff_sha256", "style_sha256"):
        value = document.get(key)
        if (
            not isinstance(value, str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", value) is None
        ):
            raise PrepareError(f"receipt {key} is invalid")
    if document.get("metric_event") not in {
        "PRE_CANDIDATE_RUFF_CATCH",
        "PRE_CANDIDATE_NO_RUFF_CHANGE",
    }:
        raise PrepareError("receipt metric event is invalid")
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare or verify a normalized Gnostoa candidate tree."
    )
    actions = parser.add_subparsers(dest="action", required=True)

    prepare_parser = actions.add_parser("prepare")
    prepare_parser.add_argument("--parent", required=True)
    prepare_parser.add_argument("--receipt", required=True, type=Path)
    prepare_parser.add_argument("focused", nargs=argparse.REMAINDER)

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
            focused = list(arguments.focused)
            if focused[:1] == ["--"]:
                focused = focused[1:]
            document = prepare(arguments.parent, arguments.receipt, focused)
    except PrepareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(_canonical_json(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
