"""What other test modules share from tests/test_exact_tree.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import contextlib
import importlib.util
import os
import subprocess  # nosec B404 -- test-only: a literal git argv on temporary fixtures
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tools.exact_tree import Limits


_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    # The repository's trusted executable lookup (AGENTS.md), as the owner uses it.
    "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
    # No automatic housekeeping in the fixture repositories: a commit otherwise spawns
    # a detached `git maintenance run --auto`, which can still write into `.git` while
    # a test's cleanup removes it (python-compatibility 3.12, job 119192065066).
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "gc.auto",
    "GIT_CONFIG_VALUE_0": "0",
    "GIT_CONFIG_KEY_1": "maintenance.auto",
    "GIT_CONFIG_VALUE_1": "false",
}


def git(
    repo: Path,
    *args: str,
    stdin: bytes | None = None,
    env: dict[str, str] | None = None,
) -> str:
    return (
        subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on temporary fixtures
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            input=stdin,
            env=_ENV if env is None else env,
        )
        .stdout.decode()
        .strip()
    )


def _owner() -> ModuleType:
    try:
        return importlib.import_module("tools.exact_tree")
    except ModuleNotFoundError as exc:
        raise AssertionError("missing capability: tools.exact_tree") from exc


class ExactTreeFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.marker = self.root / "driver-ran"

    def commit(self, files: dict[str, bytes]) -> str:
        for rel, data in files.items():
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "c")
        return git(self.repo, "rev-parse", "HEAD^{tree}")

    @staticmethod
    def limits(**overrides: Any) -> Limits:
        values: dict[str, Any] = {
            "deadline": time.monotonic() + 60,
            "max_files": 1_000,
            "max_bytes": 1 << 20,
        }
        values.update(overrides)
        return _owner().Limits(**values)

    def assertRefused(self, code: str | None, call: Any) -> Any:
        owner = _owner()
        with self.assertRaises(owner.ExactTreeError) as raised:
            call()
        if code is not None:
            self.assertEqual(code, raised.exception.code)
        return raised.exception

    def link_tree(
        self, links: dict[str, str], files: dict[str, bytes] | None = None
    ) -> str:
        """A tree of symlink entries (and files) written with mktree, nested as given."""
        entries: dict[str, tuple[str, str]] = {}
        for path, data in (files or {}).items():
            entries[path] = (
                "100644",
                git(self.repo, "hash-object", "-w", "--stdin", stdin=data),
            )
        for path, target in links.items():
            entries[path] = (
                "120000",
                git(self.repo, "hash-object", "-w", "--stdin", stdin=target.encode()),
            )

        def build(paths: dict[str, tuple[str, str]]) -> str:
            lines: list[str] = []
            subdirs: dict[str, dict[str, tuple[str, str]]] = {}
            for path, (mode, oid) in sorted(paths.items()):
                head, _, rest = path.partition("/")
                if rest:
                    subdirs.setdefault(head, {})[rest] = (mode, oid)
                else:
                    lines.append(f"{mode} blob {oid}\t{head}")
            for name, sub in sorted(subdirs.items()):
                lines.append(f"040000 tree {build(sub)}\t{name}")
            return git(self.repo, "mktree", stdin=("\n".join(lines) + "\n").encode())

        return build(entries)

    @staticmethod
    def feeding(output: bytes) -> Any:
        """A stand-in for the owner's Git child: it hands `output` to the child's sink
        when it has one, as the real drain does, and returns it otherwise."""

        def git(repo: Path, args: list[str], **kwargs: Any) -> bytes:
            sink = kwargs.get("sink")
            if sink is None:
                return output
            sink(output)
            return b""

        return git

    @staticmethod
    def without_waiting(call: Any, fifo: Path) -> tuple[bool, list[Any]]:
        """Run `call` in a thread: whether it waited on `fifo` past 5 s, and its result
        or refusal code. A writer's open releases a reader that waits."""
        outcome: list[Any] = []

        def run() -> None:
            try:
                outcome.append(call())
            except _owner().ExactTreeError as exc:
                outcome.append(exc.code)

        reader = threading.Thread(target=run, daemon=True)
        reader.start()
        reader.join(5)
        waited = reader.is_alive()
        if waited:
            with contextlib.suppress(OSError):
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
            reader.join(5)
        return waited, outcome

    def blob(self, tree: str, path: str) -> bytes:
        return subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on temporary fixtures
            ["git", "-C", str(self.repo), "cat-file", "blob", f"{tree}:{path}"],
            check=True,
            capture_output=True,
            env=_ENV,
        ).stdout

    def arm_driver(self, pattern: str = "*") -> None:
        command = f"sh -c 'touch {self.marker}; cat'"
        git(self.repo, "config", "filter.probe.smudge", command)
        git(self.repo, "config", "filter.probe.clean", command)
        info = self.repo / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text(f"{pattern} filter=probe\n")
