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
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
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
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_ATTR_NOSYSTEM",
    "GIT_EXTERNAL_DIFF",
)
_FOCUSED_PROFILES = (
    "policy",
    "security-fast",
    "fast",
    "regression",
    "smoke",
    "extended",
)
_PREPARATION_AUTHORITY_PATHS = ("ci/style", "ci/verify")


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
    for name in tuple(env):
        if (
            name in _GIT_ENVIRONMENT_VARIABLES
            or name == "GIT_CONFIG_COUNT"
            or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
        ):
            env.pop(name, None)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_ATTR_NOSYSTEM"] = "1"
    # Disable repository/default hooks without inheriting caller command config.
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "core.hooksPath"
    env["GIT_CONFIG_VALUE_0"] = os.devnull
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
    # Audited for command injection: no shell is involved. Git and
    # repository-owned verification executables are locally resolved, argv is
    # passed as a list, and candidate preparation accepts only a closed focused
    # profile at both the CLI and implementation-private API boundaries.
    argv = list(command)
    completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        argv,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
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


def _assert_safe_repository_git_configuration(root: Path) -> None:
    pattern = (
        r"^(filter\..*\.(clean|smudge|process|required)"
        r"|diff\.external|diff\..*\.(command|textconv)"
        r"|core\.(attributesfile|hookspath|fsmonitor))$"
    )
    configured = _run(
        [
            _git_executable(),
            "config",
            "--local",
            "--includes",
            "--get-regexp",
            pattern,
        ],
        cwd=root,
        check=False,
    )
    if configured.returncode not in {0, 1}:
        raise PrepareError("unable to inspect repository-local Git configuration")
    if configured.returncode == 0 and configured.stdout.strip():
        raise PrepareError(
            "repository-local Git execution configuration is unsupported"
        )

    attributes_text = _git_text(root, "rev-parse", "--git-path", "info/attributes")
    attributes = Path(attributes_text)
    if not attributes.is_absolute():
        attributes = root / attributes
    try:
        if attributes.is_file() and attributes.read_bytes().strip():
            raise PrepareError("repository-local Git attributes are unsupported")
    except OSError as exc:
        raise PrepareError("unable to inspect repository-local Git attributes") from exc


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


def _binary_diff_between_trees(root: Path, parent: str, tree: str) -> bytes:
    return _run(
        [
            _git_executable(),
            "diff",
            "--binary",
            "--full-index",
            parent,
            tree,
        ],
        cwd=root,
    ).stdout


def _assert_parent_preparation_authorities(
    root: Path,
    parent: str,
    index: Path | None = None,
) -> None:
    env = _base_env()
    if index is not None:
        env["GIT_INDEX_FILE"] = str(index)
    changed_raw = _run(
        [
            _git_executable(),
            "diff",
            "--cached",
            "--name-only",
            "-z",
            parent,
            "--",
            *_PREPARATION_AUTHORITY_PATHS,
        ],
        cwd=root,
        env=env,
    ).stdout
    changed = sorted(os.fsdecode(item) for item in changed_raw.split(b"\0") if item)
    if changed:
        raise PrepareError(
            "candidate modifies preparation authority: " + ", ".join(changed)
        )


def _stage_workspace_candidate(root: Path, parent: str) -> tuple[str, list[str]]:
    _git_text(root, "add", "-A")
    tree = _git_text(root, "write-tree")
    changed_raw = _run(
        [_git_executable(), "diff", "--cached", "--name-only", "-z", parent],
        cwd=root,
    ).stdout
    changed = sorted(os.fsdecode(item) for item in changed_raw.split(b"\0") if item)
    return tree, changed


def _assert_no_candidate_symlinks(root: Path) -> None:
    records = _run(
        [_git_executable(), "ls-files", "--stage", "-z"],
        cwd=root,
    ).stdout
    symlinks: list[str] = []
    for record in records.split(b"\0"):
        if not record:
            continue
        metadata, separator, raw_path = record.partition(b"\t")
        if not separator:
            raise PrepareError("unable to inspect candidate file modes")
        mode = metadata.split(b" ", 1)[0]
        if mode == b"120000":
            symlinks.append(os.fsdecode(raw_path))
    if symlinks:
        raise PrepareError(
            "candidate symlinks are unsupported: " + ", ".join(sorted(symlinks))
        )


def _assert_workspace_matches_tree(
    root: Path,
    expected_tree: str,
    message: str,
) -> None:
    if _git_text(root, "write-tree") != expected_tree:
        raise PrepareError(message)
    tracked = _run(
        [_git_executable(), "diff", "--quiet", "--"],
        cwd=root,
        check=False,
    )
    if tracked.returncode not in {0, 1}:
        raise PrepareError("unable to inspect isolated candidate workspace")
    untracked = _run(
        [_git_executable(), "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root,
    ).stdout
    if tracked.returncode != 0 or untracked:
        raise PrepareError(message)


def _reset_workspace_to_index(root: Path) -> None:
    _run([_git_executable(), "clean", "-ffdx"], cwd=root)
    _git_text(root, "checkout-index", "--all", "--force")


@contextmanager
def _candidate_workspace(
    repository_root: Path,
    parent: str,
    tree: str,
) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-candidate-workspace-"
    ) as directory:
        workspace = Path(directory) / "worktree"
        _run(
            [
                _git_executable(),
                "worktree",
                "add",
                "--detach",
                "--no-checkout",
                str(workspace),
                parent,
            ],
            cwd=repository_root,
        )
        try:
            _git_text(workspace, "read-tree", tree)
            _git_text(workspace, "checkout-index", "--all", "--force")
            _assert_no_candidate_symlinks(workspace)
            yield workspace
        finally:
            _run(
                [
                    _git_executable(),
                    "worktree",
                    "remove",
                    "--force",
                    str(workspace),
                ],
                cwd=repository_root,
                check=False,
            )
            _run(
                [_git_executable(), "worktree", "prune"],
                cwd=repository_root,
                check=False,
            )


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
    focused_receipt_argv = _focused_receipt_command(focused_profile)
    receipt = _assert_external_receipt(root, receipt_path)
    _assert_head(root, parent_commit)
    _assert_safe_repository_git_configuration(root)
    parent_tree = _git_text(root, "rev-parse", f"{parent_commit}^{{tree}}")

    with tempfile.TemporaryDirectory(prefix="gnostoa-candidate-index-") as directory:
        index = Path(directory) / "index"
        proposed_tree, proposed_paths = _stage_candidate(root, parent_commit, index)
        if not proposed_paths:
            raise PrepareError("candidate has no changes relative to parent")
        _assert_parent_preparation_authorities(root, parent_commit, index)

    with _candidate_workspace(root, parent_commit, proposed_tree) as workspace:
        style = workspace / "ci" / "style"
        if not style.is_file():
            raise PrepareError("ci/style is unavailable")
        focused_argv = _focused_profile_command(workspace, focused_profile)

        _run([str(style), "--fix"], cwd=workspace)
        _assert_head(workspace, parent_commit)
        normalized_tree, changed_paths = _stage_workspace_candidate(
            workspace,
            parent_commit,
        )
        if not changed_paths:
            raise PrepareError("candidate has no changes after normalization")
        _assert_parent_preparation_authorities(workspace, parent_commit)
        _assert_no_candidate_symlinks(workspace)

        # Verification must observe only bytes reachable from the prepared tree.
        # Drop ignored/untracked formatter residue, then restore tracked bytes
        # from the normalized index before executing the focused profile.
        _reset_workspace_to_index(workspace)
        focused = _run(focused_argv, cwd=workspace, check=False)
        if focused.returncode != 0:
            stderr = focused.stderr.decode("utf-8", errors="replace").strip()
            detail = f": {stderr}" if stderr else ""
            raise PrepareError(
                f"focused verification failed ({focused.returncode}){detail}"
            )
        _assert_head(workspace, parent_commit)
        _assert_workspace_matches_tree(
            workspace,
            normalized_tree,
            "focused verification mutated candidate",
        )

        # Focused verification may create ignored caches. Remove them before the
        # final style decision so that it rechecks the exact normalized tree.
        _reset_workspace_to_index(workspace)
        _run([str(style), "--check"], cwd=workspace)
        _assert_head(workspace, parent_commit)
        _assert_workspace_matches_tree(
            workspace,
            normalized_tree,
            "style check mutated candidate",
        )
        _run(
            [_git_executable(), "diff", "--cached", "--check", parent_commit],
            cwd=workspace,
        )

        prepared_diff = _binary_diff_between_trees(
            root,
            parent_commit,
            normalized_tree,
        )
        style_sha256 = _sha256_bytes(style.read_bytes())
        verify_sha256 = _sha256_bytes((workspace / "ci" / "verify").read_bytes())
        ruff_version = _ruff_version(workspace)

    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "parent_commit": parent_commit,
        "parent_tree": parent_tree,
        "prepared_tree": normalized_tree,
        "prepared_diff_sha256": _sha256_bytes(prepared_diff),
        "changed_paths": changed_paths,
        "style_sha256": style_sha256,
        "verify_sha256": verify_sha256,
        "style_subject": ".",
        "ruff_version": ruff_version,
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


def _validate_receipt_shape(document: dict[str, Any]) -> None:
    changed_paths = document.get("changed_paths")
    if (
        not isinstance(changed_paths, list)
        or not changed_paths
        or not all(isinstance(path, str) and path for path in changed_paths)
    ):
        raise PrepareError("receipt changed paths are invalid")
    if changed_paths != sorted(set(changed_paths)):
        raise PrepareError("receipt changed paths are invalid")
    if document.get("style_subject") != ".":
        raise PrepareError("receipt style subject is invalid")
    ruff_version = document.get("ruff_version")
    if not isinstance(ruff_version, str) or not ruff_version.strip():
        raise PrepareError("receipt Ruff version is invalid")


def verify_receipt(
    receipt_path: Path,
    expected_parent: str,
    expected_tree: str,
    trusted_receipt_sha256: str,
) -> dict[str, Any]:
    """Validate a receipt against identity retained by a trusted preparation path."""

    if _SHA256.fullmatch(trusted_receipt_sha256) is None:
        raise PrepareError("trusted receipt identity is invalid")
    document = _load_receipt(receipt_path)
    if document.get("receipt_sha256") != trusted_receipt_sha256:
        raise PrepareError("trusted receipt identity mismatch")
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
    _require_sha256(document, "verify_sha256")
    _validate_receipt_metric(document)
    _validate_receipt_shape(document)
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
    verify_parser.add_argument("--receipt-sha256", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.action == "verify":
            document = verify_receipt(
                arguments.receipt,
                arguments.parent,
                arguments.tree,
                arguments.receipt_sha256,
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
