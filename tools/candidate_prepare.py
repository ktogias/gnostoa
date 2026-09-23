from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import selectors
import shutil
import signal
import subprocess  # nosec B404 -- audited subprocess boundary in _run
import sys
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RECEIPT_SCHEMA = "gnostoa-candidate-preparation-receipt/v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_RETENTION_REF = re.compile(
    r"^refs/gnostoa/prepared/"
    r"(?P<parent>[0-9a-f]{40})/"
    r"(?P<tree>[0-9a-f]{40})/"
    r"(?P<nonce>[0-9a-f]{32})$"
)
_GIT = shutil.which("git")
_GIT_ROUTING_ENVIRONMENT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_INDEX_FILE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
)
_GIT_ENVIRONMENT_VARIABLES = (
    *_GIT_ROUTING_ENVIRONMENT_VARIABLES,
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
    "GIT_ATTR_NOSYSTEM",
    "GIT_EXTERNAL_DIFF",
    "GIT_TEMPLATE_DIR",
)
_FOCUSED_PROFILES = (
    "policy",
    "security-fast",
    "fast",
    "regression",
    "smoke",
    "extended",
)
_FOCUSED_TIMEOUT_SECONDS = 900
_FOCUSED_OUTPUT_BYTES = 65_536
_FOCUSED_TERMINATE_GRACE_SECONDS = 2
_PREPARATION_AUTHORITY_PATHS = (
    "ci/prepare-candidate",
    "ci/style",
    "ci/verify",
    "tools/candidate_prepare.py",
    "pyproject.toml",
    "ruff.toml",
    ".ruff.toml",
    ":(glob)**/pyproject.toml",
    ":(glob)**/ruff.toml",
    ":(glob)**/.ruff.toml",
)


class PrepareError(RuntimeError):
    pass


@dataclass(frozen=True)
class _FocusedResult:
    returncode: int
    stdout: bytes
    stderr: bytes


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


def _git_env_without_caller_overrides() -> dict[str, str]:
    env = dict(os.environ)
    for name in tuple(env):
        if (
            name in _GIT_ENVIRONMENT_VARIABLES
            or name == "GIT_CONFIG_COUNT"
            or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))
        ):
            env.pop(name, None)
    return env


def _caller_excludes_snapshot(root: Path) -> bytes:
    lookup_env = _git_env_without_caller_overrides()
    configured = _run(
        [
            _git_executable(),
            "config",
            "--includes",
            "--path",
            "--get",
            "core.excludesFile",
        ],
        cwd=root,
        env=lookup_env,
        check=False,
    )
    if configured.returncode not in {0, 1}:
        raise PrepareError("unable to inspect caller Git exclude configuration")

    if configured.returncode == 0:
        configured_path = configured.stdout.decode("utf-8", errors="strict").strip()
        if not configured_path:
            return b""
        excludes = Path(configured_path).expanduser()
        if not excludes.is_absolute():
            excludes = root / excludes
    else:
        config_home = lookup_env.get("XDG_CONFIG_HOME")
        if config_home:
            excludes = Path(config_home).expanduser() / "git" / "ignore"
        else:
            home = lookup_env.get("HOME")
            if not home:
                return b""
            excludes = Path(home).expanduser() / ".config" / "git" / "ignore"

    try:
        if not excludes.exists():
            return b""
        if not excludes.is_file():
            raise PrepareError("caller Git exclude file is not a regular file")
        return excludes.read_bytes()
    except OSError as exc:
        raise PrepareError("caller Git exclude snapshot is unavailable") from exc


def _base_env() -> dict[str, str]:
    env = _git_env_without_caller_overrides()
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_ATTR_NOSYSTEM"] = "1"
    # Disable repository/default hooks without inheriting caller command config.
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "core.hooksPath"
    env["GIT_CONFIG_VALUE_0"] = os.devnull
    return env


def _trusted_python_env(env: dict[str, str] | None = None) -> dict[str, str]:
    trusted = dict(_base_env() if env is None else env)
    for name in ("PYTHONHOME", "PYTHONPATH", "PYTHONSAFEPATH", "PYTHONUSERBASE"):
        trusted.pop(name, None)
    trusted["PYTHONSAFEPATH"] = "1"
    trusted["PYTHONNOUSERSITE"] = "1"
    python_dir = str(Path(sys.executable).parent)
    git_dir = str(Path(_git_executable()).parent)
    trusted["PATH"] = os.pathsep.join((python_dir, git_dir, os.defpath))
    return trusted


def _focused_tooling_directory(git_dir: Path) -> Path:
    tooling = git_dir.parent / "focused-bin"
    tooling.mkdir(mode=0o700)
    knowledge = tooling / "knowledge"
    knowledge.write_text(
        '#!/bin/sh\nset -eu\nexec "$GNOSTOA_PREPARE_PYTHON" -m tools.cli "$@"\n',
        encoding="utf-8",
    )
    knowledge.chmod(0o700)
    return tooling


def _focused_verification_env(
    env: dict[str, str] | None = None,
    *,
    workspace: Path | None = None,
    tooling: Path | None = None,
) -> dict[str, str]:
    focused = _trusted_python_env(env)
    # Preparation-only Git routing must not leak into candidate verification:
    # inherited GIT_DIR/GIT_WORK_TREE routing overrides ordinary discovery and
    # hijacks nested repositories created by the verification suite. The
    # workspace's .git pointer supplies the intended isolated metadata instead.
    for name in _GIT_ROUTING_ENVIRONMENT_VARIABLES:
        focused.pop(name, None)
    # Caller toolkit routing must not redirect repository-owned verification to
    # the mutable source checkout or an installed image copy.
    focused.pop("KNOWLEDGE_KIT_ROOT", None)
    focused.pop("KNOWLEDGE_KIT_REVISION", None)
    if workspace is not None:
        focused["KNOWLEDGE_KIT_ROOT"] = str(workspace.resolve())
        focused["KNOWLEDGE_KIT_REVISION"] = "development"
    if tooling is not None:
        focused["GNOSTOA_PREPARE_PYTHON"] = sys.executable
        focused["PATH"] = os.pathsep.join((str(tooling), focused["PATH"]))
    # Focused verification must import the exact candidate workspace, while
    # inherited Python search paths and user-site state remain excluded.
    focused.pop("PYTHONSAFEPATH", None)
    return focused


def _terminate_focused_process(process: subprocess.Popen[bytes]) -> None:
    # A verification leader may exit while one of its descendants keeps an
    # inherited pipe open. Cleanup therefore targets the whole process group,
    # even after the leader itself has already been reaped.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=_FOCUSED_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            continue
        if sig == signal.SIGTERM:
            continue
        break
    try:
        process.wait(timeout=_FOCUSED_TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise PrepareError("focused verification process could not be reaped") from exc


def _append_bounded(buffer: bytearray, chunk: bytes, limit: int) -> None:
    if len(chunk) >= limit:
        buffer[:] = chunk[-limit:]
        return
    buffer.extend(chunk)
    excess = len(buffer) - limit
    if excess > 0:
        del buffer[:excess]


def _run_focused(
    command: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: float = _FOCUSED_TIMEOUT_SECONDS,
    max_output_bytes: int = _FOCUSED_OUTPUT_BYTES,
) -> _FocusedResult:
    if timeout_seconds <= 0 or max_output_bytes <= 0:
        raise PrepareError("focused verification bounds must be positive")

    argv = list(
        command
    )  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
    deadline = time.monotonic() + timeout_seconds
    try:
        # Audited for command injection: the executable is the repository-owned
        # ci/verify resolved by _focused_profile_command(), the profile is from a
        # closed allowlist, shell parsing is disabled, cwd is the isolated
        # prepared workspace, and env is the preparation-owned scrubbed mapping.
        # ast-grep-ignore: os-system-unsanitized-data, subprocess-from-request
        process: subprocess.Popen[bytes] = subprocess.Popen(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit, python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
            argv,  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
    except OSError as exc:
        raise PrepareError("focused verification could not start") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    group_terminated = False
    selector = selectors.DefaultSelector()
    output = {"stdout": bytearray(), "stderr": bytearray()}
    timed_out = False
    try:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            events = selector.select(remaining)
            if not events:
                timed_out = True
                break
            for key, _mask in events:
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                _append_bounded(output[key.data], chunk, max_output_bytes)

        if timed_out:
            _terminate_focused_process(process)
            group_terminated = True
            raise PrepareError(
                f"focused verification timed out after {timeout_seconds:g}s"
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_focused_process(process)
            group_terminated = True
            raise PrepareError(
                f"focused verification timed out after {timeout_seconds:g}s"
            )
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as exc:
            _terminate_focused_process(process)
            group_terminated = True
            raise PrepareError(
                f"focused verification timed out after {timeout_seconds:g}s"
            ) from exc

        # A successful leader may leave descendants alive. End the complete
        # preparation-owned process group before mutation/style evidence is read.
        _terminate_focused_process(process)
        group_terminated = True
        return _FocusedResult(
            returncode=returncode,
            stdout=bytes(output["stdout"]),
            stderr=bytes(output["stderr"]),
        )
    finally:
        # Exceptions while collecting output must not leak candidate processes.
        # Preserve an already-active primary exception if cleanup itself fails.
        active_exception = sys.exc_info()[0] is not None
        if not group_terminated:
            try:
                _terminate_focused_process(process)
            except PrepareError:
                if not active_exception:
                    raise
        selector.close()
        process.stdout.close()
        process.stderr.close()


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


def _ruff_version(
    root: Path,
    *,
    env: dict[str, str] | None = None,
) -> str:
    completed = _run(
        [sys.executable, "-P", "-m", "ruff", "--version"],
        cwd=root,
        env=_trusted_python_env(env),
    )
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _assert_external_receipt(root: Path, receipt: Path) -> Path:
    resolved_root = root.resolve()
    expanded = receipt.expanduser()
    if expanded.exists() or expanded.is_symlink():
        raise PrepareError("receipt path already exists")
    resolved = expanded.resolve()
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


def _source_object_directory(root: Path) -> Path:
    common_text = _git_text(root, "rev-parse", "--git-common-dir")
    common = Path(common_text)
    if not common.is_absolute():
        common = root / common
    objects = (common / "objects").resolve()
    if not objects.is_dir():
        raise PrepareError("repository object directory is unavailable")
    return objects


def _prepared_tree_ref(parent: str, tree: str, nonce: str) -> str:
    if _SHA40.fullmatch(parent) is None:
        raise PrepareError("prepared-tree parent identity is invalid")
    if _SHA40.fullmatch(tree) is None:
        raise PrepareError("prepared tree identity is invalid")
    if re.fullmatch(r"[0-9a-f]{32}", nonce) is None:
        raise PrepareError("prepared-tree retention nonce is invalid")
    return f"refs/gnostoa/prepared/{parent}/{tree}/{nonce}"


def _retention_ref_matches(ref: object, parent: str, tree: str) -> bool:
    if not isinstance(ref, str):
        return False
    match = _RETENTION_REF.fullmatch(ref)
    return bool(
        match and match.group("parent") == parent and match.group("tree") == tree
    )


def _retain_prepared_tree(root: Path, parent: str, tree: str) -> str:
    ref = _prepared_tree_ref(parent, tree, secrets.token_hex(16))
    created = _run(
        [_git_executable(), "update-ref", ref, tree, "0" * 40],
        cwd=root,
        check=False,
    )
    if created.returncode != 0:
        raise PrepareError("unable to retain prepared tree")
    return ref


def _release_prepared_tree(
    root: Path,
    ref: str,
    parent: str,
    tree: str,
) -> None:
    if not _retention_ref_matches(ref, parent, tree):
        raise PrepareError("prepared-tree retention ref is invalid")
    released = _run(
        [_git_executable(), "update-ref", "-d", ref, tree],
        cwd=root,
        check=False,
    )
    if released.returncode != 0:
        raise PrepareError("unable to release prepared tree")


def _isolated_git_env(git_dir: Path, worktree: Path) -> dict[str, str]:
    env = _base_env()
    env["GIT_DIR"] = str(git_dir)
    env["GIT_WORK_TREE"] = str(worktree)
    alternates = git_dir / "objects" / "info" / "alternates"
    try:
        object_directory = alternates.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PrepareError("isolated object binding is unavailable") from exc
    if not object_directory:
        raise PrepareError("isolated object binding is unavailable")
    # Git metadata/config stays disposable, while content-addressed candidate
    # objects are written to the source object store so the prepared tree
    # remains reachable after this preparation process exits.
    env["GIT_OBJECT_DIRECTORY"] = object_directory
    return env


@contextmanager
def _isolated_git_metadata(
    repository_root: Path,
    parent: str,
    caller_excludes: bytes,
) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="gnostoa-candidate-git-") as directory:
        metadata_root = Path(directory)
        git_dir = metadata_root / "git"
        template_dir = metadata_root / "empty-template"
        template_dir.mkdir(mode=0o700)
        _run(
            [
                _git_executable(),
                "init",
                "--bare",
                f"--template={template_dir}",
                str(git_dir),
            ],
            cwd=metadata_root,
        )

        source_objects = _source_object_directory(repository_root)
        alternates = git_dir / "objects" / "info" / "alternates"
        alternates.write_text(
            str(source_objects) + "\n",
            encoding="utf-8",
        )
        source_exclude = source_objects.parent / "info" / "exclude"
        isolated_exclude = git_dir / "info" / "exclude"
        caller_exclude = git_dir / "info" / "caller-exclude"
        try:
            isolated_exclude.parent.mkdir(parents=True, exist_ok=True)
            if source_exclude.is_file():
                isolated_exclude.write_bytes(source_exclude.read_bytes())
            caller_exclude.write_bytes(caller_excludes)
        except OSError as exc:
            raise PrepareError("Git exclude snapshot is unavailable") from exc

        env = _isolated_git_env(git_dir, repository_root)
        _git_text(
            repository_root,
            "config",
            "--local",
            "core.bare",
            "false",
            env=env,
        )
        _git_text(
            repository_root,
            "config",
            "--local",
            "core.hooksPath",
            os.devnull,
            env=env,
        )
        _git_text(
            repository_root,
            "config",
            "--local",
            "core.excludesFile",
            str(caller_exclude),
            env=env,
        )
        _git_text(
            repository_root,
            "update-ref",
            "refs/heads/preparation-parent",
            parent,
            env=env,
        )
        _git_text(
            repository_root,
            "symbolic-ref",
            "HEAD",
            "refs/heads/preparation-parent",
            env=env,
        )
        yield git_dir


def _stage_candidate(
    root: Path,
    parent: str,
    git_dir: Path,
) -> tuple[str, list[str]]:
    env = _isolated_git_env(git_dir, root)
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


def _capture_stable_candidate(
    root: Path,
    parent: str,
    git_dir: Path,
) -> tuple[str, list[str]]:
    first_tree, first_paths = _stage_candidate(root, parent, git_dir)
    _assert_head(root, parent)
    second_tree, second_paths = _stage_candidate(root, parent, git_dir)
    _assert_head(root, parent)
    if first_tree != second_tree or first_paths != second_paths:
        raise PrepareError("source candidate changed during capture")
    return second_tree, second_paths


def _binary_diff_between_trees(
    root: Path,
    parent: str,
    tree: str,
    git_dir: Path,
) -> bytes:
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
        env=_isolated_git_env(git_dir, root),
    ).stdout


def _assert_parent_preparation_authorities(
    root: Path,
    parent: str,
    git_dir: Path,
) -> None:
    env = _isolated_git_env(git_dir, root)
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


def _stage_workspace_candidate(
    root: Path,
    parent: str,
    git_dir: Path,
) -> tuple[str, list[str]]:
    env = _isolated_git_env(git_dir, root)
    _git_text(root, "add", "-A", env=env)
    tree = _git_text(root, "write-tree", env=env)
    changed_raw = _run(
        [_git_executable(), "diff", "--cached", "--name-only", "-z", parent],
        cwd=root,
        env=env,
    ).stdout
    changed = sorted(os.fsdecode(item) for item in changed_raw.split(b"\0") if item)
    return tree, changed


def _assert_no_candidate_symlinks(root: Path, git_dir: Path) -> None:
    records = _run(
        [_git_executable(), "ls-files", "--stage", "-z"],
        cwd=root,
        env=_isolated_git_env(git_dir, root),
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
    git_dir: Path,
    expected_tree: str,
    message: str,
) -> None:
    env = _isolated_git_env(git_dir, root)
    if _git_text(root, "write-tree", env=env) != expected_tree:
        raise PrepareError(message)
    tracked = _run(
        [_git_executable(), "diff", "--quiet", "--"],
        cwd=root,
        env=env,
        check=False,
    )
    if tracked.returncode not in {0, 1}:
        raise PrepareError("unable to inspect isolated candidate workspace")
    untracked = _run(
        [_git_executable(), "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root,
        env=env,
    ).stdout
    if tracked.returncode != 0 or untracked:
        raise PrepareError(message)


def _reset_workspace_to_index(root: Path, git_dir: Path) -> None:
    env = _isolated_git_env(git_dir, root)
    _run([_git_executable(), "clean", "-ffdx"], cwd=root, env=env)
    _git_text(root, "checkout-index", "--all", "--force", env=env)


def _assert_worktree_matches_tree_with_trusted_metadata(
    root: Path,
    trusted_git_dir: Path,
    expected_tree: str,
    message: str,
) -> None:
    # Focused verification receives different disposable Git metadata. Build a
    # fresh index from the trusted normalized tree so candidate-controlled
    # skip-worktree bits, config, excludes or index bytes cannot hide mutations.
    with tempfile.TemporaryDirectory(prefix="gnostoa-candidate-inspect-") as directory:
        env = _isolated_git_env(trusted_git_dir, root)
        # Keep any blobs created solely for comparison inside disposable trusted
        # metadata instead of publishing them into the source object store.
        env.pop("GIT_OBJECT_DIRECTORY", None)
        env["GIT_INDEX_FILE"] = str(Path(directory) / "index")
        _git_text(root, "read-tree", expected_tree, env=env)
        staged = _run(
            [_git_executable(), "add", "-A"],
            cwd=root,
            env=env,
            check=False,
        )
        if staged.returncode != 0:
            raise PrepareError(message)
        observed_tree = _git_text(root, "write-tree", env=env)
        if observed_tree != expected_tree:
            raise PrepareError(message)


@contextmanager
def _candidate_workspace(
    git_dir: Path,
    tree: str,
) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(
        prefix="gnostoa-candidate-workspace-"
    ) as directory:
        workspace = Path(directory) / "worktree"
        workspace.mkdir()
        env = _isolated_git_env(git_dir, workspace)
        _git_text(workspace, "read-tree", tree, env=env)
        _assert_no_candidate_symlinks(workspace, git_dir)
        (workspace / ".git").write_text(
            f"gitdir: {git_dir}\n",
            encoding="utf-8",
        )
        _git_text(workspace, "checkout-index", "--all", "--force", env=env)
        yield workspace


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
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise PrepareError("receipt path already exists") from exc
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
    caller_excludes = _caller_excludes_snapshot(root)
    _assert_safe_repository_git_configuration(root)

    with _isolated_git_metadata(root, parent_commit, caller_excludes) as git_dir:
        root_env = _isolated_git_env(git_dir, root)
        parent_tree = _git_text(
            root,
            "rev-parse",
            f"{parent_commit}^{{tree}}",
            env=root_env,
        )
        proposed_tree, proposed_paths = _capture_stable_candidate(
            root,
            parent_commit,
            git_dir,
        )
        if not proposed_paths:
            raise PrepareError("candidate has no changes relative to parent")
        _assert_parent_preparation_authorities(root, parent_commit, git_dir)

        with _candidate_workspace(git_dir, proposed_tree) as workspace:
            style = workspace / "ci" / "style"
            if not style.is_file():
                raise PrepareError("ci/style is unavailable")
            isolated_env = _isolated_git_env(git_dir, workspace)
            style_env = _trusted_python_env(isolated_env)

            _run([str(style), "--fix"], cwd=workspace, env=style_env)
            _assert_head(workspace, parent_commit)
            normalized_tree, changed_paths = _stage_workspace_candidate(
                workspace,
                parent_commit,
                git_dir,
            )
            if not changed_paths:
                raise PrepareError("candidate has no changes after normalization")
            _assert_parent_preparation_authorities(
                workspace,
                parent_commit,
                git_dir,
            )
            _assert_no_candidate_symlinks(workspace, git_dir)

            # Focused candidate code receives separate disposable Git metadata
            # and a separate worktree. It never gets the normalization index or
            # config used by trusted post-checks.
            _reset_workspace_to_index(workspace, git_dir)
            with _isolated_git_metadata(
                root,
                parent_commit,
                caller_excludes,
            ) as focused_git_dir:
                with _candidate_workspace(
                    focused_git_dir,
                    normalized_tree,
                ) as focused_workspace:
                    focused_argv = _focused_profile_command(
                        focused_workspace,
                        focused_profile,
                    )
                    focused_isolated_env = _isolated_git_env(
                        focused_git_dir,
                        focused_workspace,
                    )
                    focused_tooling = _focused_tooling_directory(focused_git_dir)
                    focused_env = _focused_verification_env(
                        focused_isolated_env,
                        workspace=focused_workspace,
                        tooling=focused_tooling,
                    )
                    focused = _run_focused(
                        focused_argv,
                        cwd=focused_workspace,
                        env=focused_env,
                    )
                    if focused.returncode != 0:
                        stderr = focused.stderr.decode(
                            "utf-8", errors="replace"
                        ).strip()
                        stdout = focused.stdout.decode(
                            "utf-8", errors="replace"
                        ).strip()
                        diagnostics = "\n".join(
                            value for value in (stderr, stdout) if value
                        )
                        if len(diagnostics) > 4096:
                            diagnostics = diagnostics[-4096:]
                        detail = f": {diagnostics}" if diagnostics else ""
                        raise PrepareError(
                            "focused verification failed "
                            f"({focused.returncode}){detail}"
                        )
                    _assert_worktree_matches_tree_with_trusted_metadata(
                        focused_workspace,
                        git_dir,
                        normalized_tree,
                        "focused verification mutated candidate",
                    )

            _assert_head(root, parent_commit)
            # The normalization workspace was never exposed to focused candidate
            # code. Restore it from the trusted index before final evidence.
            _reset_workspace_to_index(workspace, git_dir)
            _run([str(style), "--check"], cwd=workspace, env=style_env)
            _assert_head(workspace, parent_commit)
            _assert_workspace_matches_tree(
                workspace,
                git_dir,
                normalized_tree,
                "style check mutated candidate",
            )
            workspace_env = _isolated_git_env(git_dir, workspace)
            _run(
                [_git_executable(), "diff", "--cached", "--check", parent_commit],
                cwd=workspace,
                env=workspace_env,
            )

            prepared_diff = _binary_diff_between_trees(
                workspace,
                parent_commit,
                normalized_tree,
                git_dir,
            )
            style_sha256 = _sha256_bytes(style.read_bytes())
            verify_sha256 = _sha256_bytes((workspace / "ci" / "verify").read_bytes())
            ruff_version = _ruff_version(workspace, env=style_env)

        # The source parent must remain stable for the full capture/verification
        # interval. Later source-worktree edits cannot affect the isolated tree.
        _assert_head(root, parent_commit)
        retention_ref = _retain_prepared_tree(
            root,
            parent_commit,
            normalized_tree,
        )

    payload: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "parent_commit": parent_commit,
        "parent_tree": parent_tree,
        "prepared_tree": normalized_tree,
        "retention_ref": retention_ref,
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
    try:
        return _write_receipt(receipt, payload)
    except (OSError, TypeError, ValueError, PrepareError):
        _release_prepared_tree(
            root,
            retention_ref,
            parent_commit,
            normalized_tree,
        )
        raise


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
    prepared_tree = _require_sha40(document, "prepared_tree")
    if not _retention_ref_matches(
        document.get("retention_ref"),
        expected_parent,
        prepared_tree,
    ):
        raise PrepareError("receipt retention ref is invalid")
    _require_sha256(document, "prepared_diff_sha256")
    _require_sha256(document, "style_sha256")
    _require_sha256(document, "verify_sha256")
    _validate_receipt_metric(document)
    _validate_receipt_shape(document)
    return document


def release_receipt(
    receipt_path: Path,
    expected_parent: str,
    expected_tree: str,
    trusted_receipt_sha256: str,
) -> dict[str, Any]:
    document = verify_receipt(
        receipt_path,
        expected_parent,
        expected_tree,
        trusted_receipt_sha256,
    )
    root = _repository_root()
    retention_ref = document.get("retention_ref")
    if not isinstance(retention_ref, str):
        raise PrepareError("receipt retention ref is invalid")
    _release_prepared_tree(
        root,
        retention_ref,
        expected_parent,
        expected_tree,
    )
    return {
        "schema": "gnostoa-candidate-preparation-release/v1",
        "parent_commit": expected_parent,
        "prepared_tree": expected_tree,
        "retention_ref": retention_ref,
        "receipt_sha256": trusted_receipt_sha256,
        "released": True,
    }


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

    release_parser = actions.add_parser("release")
    release_parser.add_argument("--parent", required=True)
    release_parser.add_argument("--tree", required=True)
    release_parser.add_argument("--receipt", required=True, type=Path)
    release_parser.add_argument("--receipt-sha256", required=True)

    # Consumed and validated by the exact-parent shell wrapper. Keeping the
    # option in the private parser lets the trusted wrapper forward argv
    # unchanged without giving the Python implementation authority to select an
    # interpreter.
    for action_parser in (prepare_parser, verify_parser, release_parser):
        action_parser.add_argument(
            "--trusted-python",
            help=argparse.SUPPRESS,
        )
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
        elif arguments.action == "release":
            document = release_receipt(
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
