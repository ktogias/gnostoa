"""The exact commit-tree owner (#389 F3 S2 A, the owner's Option A 6268025835).

One bounded owner materializes a Git tree's exact bytes and independently rebuilds a
directory's tree identity, for the capsule compiler and executor first. No attribute
or configured driver applies and the caller's environment is kept out; only the two
plumbing commands read the repository's own configuration. It refuses what it cannot
represent exactly (S2-MAT-01, S2-A3-01, Router 6267325366 and 6297725852).
"""

from __future__ import annotations

import contextlib
import errno
import importlib.util
import os
import resource
import shutil
import stat
import subprocess  # nosec B404 -- test-only: a literal git argv on temporary fixtures
import sys
import tempfile
import threading
import time
import traceback
import unittest
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any
from unittest import mock

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
# The suppression markers the Popen line must carry, built so that this module never
# writes a marker itself: merge admission reads every marker an added line holds (M13).
_SEMGREP_RULE = (
    "python.lang.security.audit."
    "dangerous-subprocess-use-audit.dangerous-subprocess-use-audit"
)
_NOSEMGREP = "no" + "semgrep: " + _SEMGREP_RULE
_NOSEC_B603 = "#" + " nosec B603 -- "


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

    def limits(self, **overrides: Any) -> Limits:
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

    def feeding(self, output: bytes) -> Any:
        """A stand-in for the owner's Git child: it hands `output` to the child's sink
        when it has one, as the real drain does, and returns it otherwise."""

        def git(repo: Path, args: list[str], **kwargs: Any) -> bytes:
            sink = kwargs.get("sink")
            if sink is None:
                return output
            sink(output)
            return b""

        return git

    def without_waiting(self, call: Any, fifo: Path) -> tuple[bool, list[Any]]:
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


class ExactBytesTests(ExactTreeFixture):
    def test_materializes_the_exact_blob_bytes_despite_the_tree_attributes(
        self,
    ) -> None:
        tree = self.commit(
            {
                ".gitattributes": b"id.txt ident\ncrlf.txt text eol=crlf\n"
                b"gone.txt export-ignore\nsubst.txt export-subst\n",
                "id.txt": b"$Id$\n",
                "crlf.txt": b"line\n",
                "gone.txt": b"export-ignore must not drop me\n",
                "subst.txt": b"$Format:%H$\n",
            }
        )
        owner = _owner()
        destination = self.root / "out"
        owner.materialize(self.repo, tree, destination, limits=self.limits())
        for path in (".gitattributes", "id.txt", "crlf.txt", "gone.txt", "subst.txt"):
            with self.subTest(path=path):
                self.assertEqual(
                    self.blob(tree, path), (destination / path).read_bytes()
                )
        self.assertEqual(
            tree, owner.observed_tree(self.repo, destination, limits=self.limits())
        )

    def test_a_modified_file_changes_the_observed_tree(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        owner = _owner()
        destination = self.root / "out"
        owner.materialize(self.repo, tree, destination, limits=self.limits())
        (destination / "a.txt").write_bytes(b"changed\n")
        self.assertNotEqual(
            tree, owner.observed_tree(self.repo, destination, limits=self.limits())
        )

    def test_tree_paths_lists_every_tracked_path(self) -> None:
        tree = self.commit({"a.txt": b"a\n", "d/b.txt": b"b\n"})
        self.assertEqual(
            frozenset({"a.txt", "d/b.txt"}),
            _owner().tree_paths(self.repo, tree, limits=self.limits()),
        )


class NoConfiguredDriverTests(ExactTreeFixture):
    """S2-A3-01: neither path runs a driver, including one that leaves the bytes
    unchanged, so a matching tree cannot hide an earlier invocation."""

    def test_materialization_never_runs_a_repository_filter_driver(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        self.arm_driver()
        _owner().materialize(self.repo, tree, self.root / "out", limits=self.limits())
        self.assertFalse(self.marker.exists(), "a configured driver ran")

    def test_identity_never_runs_a_repository_filter_driver(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        owner = _owner()
        destination = self.root / "out"
        owner.materialize(self.repo, tree, destination, limits=self.limits())
        self.arm_driver()
        self.assertEqual(
            tree, owner.observed_tree(self.repo, destination, limits=self.limits())
        )
        self.assertFalse(self.marker.exists(), "a configured driver ran")

    def test_repository_info_attributes_change_nothing(self) -> None:
        tree = self.commit({"a.txt": b"a\n", "b.txt": b"b\n"})
        info = self.repo / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("b.txt export-ignore\na.txt ident\n")
        destination = self.root / "out"
        _owner().materialize(self.repo, tree, destination, limits=self.limits())
        self.assertEqual(b"b\n", (destination / "b.txt").read_bytes())
        self.assertEqual(b"a\n", (destination / "a.txt").read_bytes())

    def test_the_callers_git_environment_changes_nothing(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        command = f"sh -c 'touch {self.marker}; cat'"
        spoof = {
            "GIT_DIR": str(self.root / "elsewhere"),
            "GIT_INDEX_FILE": str(self.root / "index"),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "filter.probe.smudge",
            "GIT_CONFIG_VALUE_0": command,
            "GIT_ATTR_SOURCE": "HEAD",
        }
        (self.repo / ".git" / "info").mkdir(exist_ok=True)
        (self.repo / ".git" / "info" / "attributes").write_text("* filter=probe\n")
        destination = self.root / "out"
        with mock.patch.dict(os.environ, spoof):
            _owner().materialize(self.repo, tree, destination, limits=self.limits())
        self.assertEqual(b"a\n", (destination / "a.txt").read_bytes())
        self.assertFalse(self.marker.exists(), "a caller-configured driver ran")


class VerifyTrackedTests(ExactTreeFixture):
    """S2-A3-02: a reused directory is checked against the frozen tree's tracked paths
    only. A run's own outputs and the consumer's declared overlays are allowed; a
    changed, missing or retyped tracked path is refused."""

    def test_untracked_outputs_and_ignored_overlays_are_allowed(self) -> None:
        tree = self.commit({"a.txt": b"a\n", "d/b.txt": b"b\n"})
        owner = _owner()
        root = self.root / "out"
        owner.materialize(self.repo, tree, root, limits=self.limits())
        (root / "run-output.log").write_bytes(b"made by a run\n")
        (root / "d" / "b.txt").write_bytes(b"overlay\n")
        owner.verify_tracked(
            self.repo, tree, root, limits=self.limits(), ignore=("d/b.txt",)
        )

    def test_a_changed_or_missing_tracked_path_is_refused(self) -> None:
        tree = self.commit({"a.txt": b"a\n", "d/b.txt": b"b\n"})
        owner = _owner()
        for label, damage in (
            ("changed", lambda root: (root / "a.txt").write_bytes(b"x\n")),
            ("missing", lambda root: (root / "d" / "b.txt").unlink()),
            ("mode", lambda root: (root / "a.txt").chmod(0o755)),
        ):
            with self.subTest(damage=label):
                root = self.root / label
                owner.materialize(self.repo, tree, root, limits=self.limits())
                damage(root)
                limits = self.limits()
                with self.assertRaises(owner.ExactTreeError) as raised:
                    owner.verify_tracked(self.repo, tree, root, limits=limits)
                self.assertEqual("tree-mismatch", raised.exception.code)


class RefusalTests(ExactTreeFixture):
    def test_a_gitlink_is_refused(self) -> None:
        self.commit({"a.txt": b"a\n"})
        head = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "update-index", "--add", "--cacheinfo", f"160000,{head},sub")
        git(self.repo, "commit", "-q", "-m", "gitlink")
        tree = git(self.repo, "rev-parse", "HEAD^{tree}")
        self.assertRefused(
            "unsupported-entry",
            lambda: _owner().materialize(
                self.repo, tree, self.root / "out", limits=self.limits()
            ),
        )

    def test_an_in_tree_symlink_is_kept_and_an_escaping_one_refused(self) -> None:
        (self.repo / "kept.txt").write_bytes(b"k\n")
        os.symlink("kept.txt", self.repo / "inside")
        tree = self.commit({})
        destination = self.root / "out"
        _owner().materialize(self.repo, tree, destination, limits=self.limits())
        self.assertEqual("kept.txt", os.readlink(destination / "inside"))
        os.symlink("../../outside", self.repo / "escape")
        escaping = self.commit({})
        self.assertRefused(
            "escaping-link",
            lambda: _owner().materialize(
                self.repo, escaping, self.root / "out2", limits=self.limits()
            ),
        )

    def test_the_file_cap_holds_at_the_cap_and_refuses_past_it(self) -> None:
        tree = self.commit({"a.txt": b"a\n", "b.txt": b"b\n", "c.txt": b"c\n"})
        _owner().materialize(
            self.repo, tree, self.root / "at", limits=self.limits(max_files=3)
        )
        self.assertRefused(
            "cap-files",
            lambda: _owner().materialize(
                self.repo, tree, self.root / "past", limits=self.limits(max_files=2)
            ),
        )
        self.assertRefused(
            "cap-files",
            lambda: _owner().tree_paths(
                self.repo, tree, limits=self.limits(max_files=2)
            ),
        )

    def test_the_byte_cap_holds_at_the_cap_and_refuses_past_it(self) -> None:
        tree = self.commit({"a.txt": b"x" * 100, "b.txt": b"y" * 50})
        _owner().materialize(
            self.repo, tree, self.root / "at", limits=self.limits(max_bytes=150)
        )
        self.assertRefused(
            "cap-bytes",
            lambda: _owner().materialize(
                self.repo, tree, self.root / "past", limits=self.limits(max_bytes=149)
            ),
        )

    def test_a_spent_deadline_refuses_without_starting_a_child(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        spent = self.limits(deadline=time.monotonic() - 1)
        nested = self.root / "parent" / "out"
        with mock.patch("subprocess.Popen", side_effect=AssertionError("spawned")):
            self.assertRefused(
                "deadline",
                lambda: _owner().materialize(self.repo, tree, nested, limits=spent),
            )
            self.assertRefused(
                "deadline",
                lambda: _owner().tree_paths(self.repo, tree, limits=spent),
            )
        self.assertFalse(nested.parent.exists(), "a spent deadline created a directory")

    def crafted(self, listing: str) -> str:
        """A tree written by mktree from `listing`, as no checkout could produce."""
        return git(self.repo, "mktree", "--missing", stdin=listing.encode())

    def test_a_tree_that_cannot_be_written_exactly_is_refused(self) -> None:
        # An empty subtree has no file to write, so the bytes on disk cannot be the
        # tree: the independent identity check refuses it, and nothing is left.
        blob = git(self.repo, "hash-object", "-w", "--stdin", stdin=b"a\n")
        empty = git(self.repo, "mktree", stdin=b"")
        tree = self.crafted(f"100644 blob {blob}\ta.txt\n040000 tree {empty}\tempty\n")
        destination = self.root / "out"
        self.assertRefused(
            "tree-mismatch",
            lambda: _owner().materialize(
                self.repo, tree, destination, limits=self.limits()
            ),
        )
        self.assertFalse(destination.exists(), "a refused materialization left files")

    def test_a_crafted_git_metadata_entry_is_refused(self) -> None:
        blob = git(self.repo, "hash-object", "-w", "--stdin", stdin=b"x\n")
        tree = self.crafted(f"100644 blob {blob}\t.git\n")
        self.assertRefused(
            "unsupported-entry",
            lambda: _owner().materialize(
                self.repo, tree, self.root / "out", limits=self.limits()
            ),
        )
        # The listing refuses it on its own, not only the written tree's identity.
        self.assertRefused(
            "unsupported-entry",
            lambda: _owner().tree_paths(self.repo, tree, limits=self.limits()),
        )

    def test_a_nonempty_destination_is_refused(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        destination = self.root / "out"
        destination.mkdir()
        (destination / "stale.txt").write_bytes(b"stale\n")
        self.assertRefused(
            "destination-not-empty",
            lambda: _owner().materialize(
                self.repo, tree, destination, limits=self.limits()
            ),
        )


class RoundTwoTests(ExactTreeFixture):
    """#446 round 2 (#389 6311879794): one RED per recorded class, run before the fix."""

    # A (P0): a link's containment is decided through the tree's own links.
    def test_a_link_chain_through_an_in_tree_link_cannot_escape(self) -> None:
        for name, links in (
            ("parent-chain", {"d/l": "..", "m": "d/l/.."}),
            ("dot-chain", {"s": ".", "t": "s/../secret"}),
            ("loop", {"a": "b", "b": "a"}),
        ):
            with self.subTest(case=name):
                tree = self.link_tree(
                    links, {"d/keep.txt": b"k\n"} if name == "parent-chain" else None
                )
                destination = self.root / f"out-{name}"
                self.assertRefused(
                    "escaping-link",
                    lambda tree=tree, destination=destination: _owner().materialize(
                        self.repo, tree, destination, limits=self.limits()
                    ),
                )
                self.assertFalse(
                    destination.exists(), "a refused materialization left files"
                )

    def test_an_absolute_link_target_is_refused(self) -> None:
        # A kill test (the round-2 mutants): "/x" splits into "", "x", so without its
        # own check an absolute target would resolve as if it were inside.
        tree = self.link_tree({"abs": "/etc/passwd"})
        limits = self.limits()
        self.assertRefused(
            "escaping-link",
            lambda: _owner().materialize(
                self.repo, tree, self.root / "out", limits=limits
            ),
        )

    def test_verify_tracked_refuses_a_reused_chain_that_escapes(self) -> None:
        tree = self.link_tree({"d/l": "..", "m": "d/l/.."}, {"d/keep.txt": b"k\n"})
        root = self.root / "reused"
        (root / "d").mkdir(parents=True)
        (root / "d" / "keep.txt").write_bytes(b"k\n")
        os.symlink("..", root / "d" / "l")
        os.symlink("d/l/..", root / "m")
        limits = self.limits()
        self.assertRefused(
            "escaping-link",
            lambda: _owner().verify_tracked(self.repo, tree, root, limits=limits),
        )

    # B: nothing below the caller's own parent is followed.
    def test_a_symlinked_destination_is_refused_and_its_target_untouched(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        outside = self.root / "outside"
        outside.mkdir()
        destination = self.root / "out"
        os.symlink(outside, destination)
        limits = self.limits()
        self.assertRefused(
            None,
            lambda: _owner().materialize(self.repo, tree, destination, limits=limits),
        )
        self.assertEqual(
            [], list(outside.iterdir()), "files were written through a destination link"
        )

    def test_verify_tracked_refuses_a_symlinked_intermediate_directory(self) -> None:
        tree = self.commit({"d/b.txt": b"b\n"})
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "b.txt").write_bytes(b"b\n")
        root = self.root / "reused"
        root.mkdir()
        os.symlink(outside, root / "d")
        limits = self.limits()
        self.assertRefused(
            "tree-mismatch",
            lambda: _owner().verify_tracked(self.repo, tree, root, limits=limits),
        )

    def test_observed_tree_refuses_a_symlinked_root(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        real = self.root / "real"
        _owner().materialize(self.repo, tree, real, limits=self.limits())
        alias = self.root / "alias"
        os.symlink(real, alias)
        limits = self.limits()
        self.assertRefused(
            "unsafe-path",
            lambda: _owner().observed_tree(self.repo, alias, limits=limits),
        )

    # C: ownership is decided by atomic creation; a rollback deletes only its own work.
    def test_a_concurrent_file_in_the_destination_survives_a_refusal(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        destination = self.root / "out"
        destination.mkdir()
        owner = _owner()
        real_drain = owner.bounded_process.drain
        concurrent = destination / "written-by-another-process"

        def drain(*args: Any, **kwargs: Any) -> Any:
            if not concurrent.exists():
                concurrent.write_bytes(b"theirs\n")
            return real_drain(*args, **kwargs)

        limits = self.limits()
        with mock.patch.object(owner.bounded_process, "drain", side_effect=drain):
            self.assertRefused(
                None,
                lambda: owner.materialize(self.repo, tree, destination, limits=limits),
            )
        self.assertEqual(b"theirs\n", concurrent.read_bytes())

    # D: malformed Git output and filesystem failures are refusals, never tracebacks.
    def test_a_malformed_listing_is_a_refusal(self) -> None:
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n"})
        limits = self.limits()
        for listing in (b"100644 blob\ta.txt\0", b"\xff\xfe blob x\ta\0"):
            with (
                self.subTest(listing=listing),
                mock.patch.object(owner, "_git", side_effect=self.feeding(listing)),
            ):
                self.assertRefused(
                    "git-failed",
                    lambda: owner.tree_paths(self.repo, tree, limits=limits),
                )

    def test_an_entry_whose_object_id_is_malformed_is_refused(self) -> None:
        # A kill test for the entry's own id check (added with the mutants).
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n"})
        limits = self.limits()
        with mock.patch.object(
            owner, "_git", side_effect=self.feeding(b"100644 blob XYZ\ta.txt\0")
        ):
            self.assertRefused(
                "unsupported-entry",
                lambda: owner.tree_paths(self.repo, tree, limits=limits),
            )

    def test_a_blob_mode_entry_of_another_kind_is_refused(self) -> None:
        # A kill test (the round-2 mutants): the mode check alone is not the kind check.
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n"})
        limits = self.limits()
        for kind in ("tree", "commit"):
            listing = f"100644 {kind} {'a' * 40}\tx\0".encode()
            with (
                self.subTest(kind=kind),
                mock.patch.object(owner, "_git", side_effect=self.feeding(listing)),
            ):
                self.assertRefused(
                    "unsupported-entry",
                    lambda: owner.tree_paths(self.repo, tree, limits=limits),
                )

    def test_a_malformed_object_header_is_a_refusal(self) -> None:
        owner = _owner()
        oid = "a" * 40
        for header in (
            f"{oid} blob not-a-size\n".encode(),
            f"{oid} blob 1 extra\n".encode(),
        ):
            with self.subTest(header=header):
                writer = owner._BatchWriter(
                    self.root, [owner._Entry("100644", oid, "a.txt")], "sha1"
                )
                self.assertRefused(
                    "git-failed", lambda writer=writer, header=header: writer(header)
                )

    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0, "root reads everything"
    )
    def test_an_unreadable_reused_file_is_a_refusal(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        root = self.root / "out"
        _owner().materialize(self.repo, tree, root, limits=self.limits())
        (root / "a.txt").chmod(0)
        self.addCleanup(lambda: (root / "a.txt").chmod(0o644))
        limits = self.limits()
        self.assertRefused(
            None, lambda: _owner().verify_tracked(self.repo, tree, root, limits=limits)
        )

    # E: hashing is bounded by the deadline and by the size it recorded.
    def file_reads(self, path: Path, extra: int) -> tuple[Any, list[int]]:
        """An os.read that, for `path` only, never reaches EOF for `extra` more reads."""
        inode = os.stat(path).st_ino
        real_read = os.read
        calls: list[int] = []

        def read(fd: int, size: int) -> bytes:
            try:
                mine = os.fstat(fd).st_ino == inode
            except OSError:
                mine = False
            if not mine:
                return real_read(fd, size)
            calls.append(fd)
            data = real_read(fd, size)
            return data if data or len(calls) > extra else b"g" * 16

        return read, calls

    def test_hashing_reads_no_more_than_the_recorded_size(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        root = self.root / "out"
        _owner().materialize(self.repo, tree, root, limits=self.limits())
        read, calls = self.file_reads(root / "a.txt", extra=50)
        limits = self.limits()
        with mock.patch("os.read", side_effect=read):
            # A file that changed size while it was read is refused, not hashed short.
            self.assertRefused(
                "tree-mismatch",
                lambda: _owner().verify_tracked(self.repo, tree, root, limits=limits),
            )
        self.assertLessEqual(
            len(calls), 3, f"a growing file was read {len(calls)} times"
        )

    def test_a_deadline_passing_while_hashing_is_a_refusal(self) -> None:
        tree = self.commit({"a.txt": b"a" * 4096})
        root = self.root / "out"
        _owner().materialize(self.repo, tree, root, limits=self.limits())
        read, calls = self.file_reads(root / "a.txt", extra=0)
        start = time.monotonic()
        limits = self.limits(deadline=start + 30)
        real_monotonic = time.monotonic
        clock = mock.Mock(
            side_effect=lambda: start + 3_600 if calls else real_monotonic()
        )
        with (
            mock.patch("os.read", side_effect=read),
            mock.patch("time.monotonic", clock),
        ):
            self.assertRefused(
                "deadline",
                lambda: _owner().verify_tracked(self.repo, tree, root, limits=limits),
            )

    # F: a failing cleanup never replaces the primary refusal.
    def test_a_failing_cleanup_keeps_the_primary_refusal(self) -> None:
        blob = git(self.repo, "hash-object", "-w", "--stdin", stdin=b"a\n")
        empty = git(self.repo, "mktree", stdin=b"")
        tree = git(
            self.repo,
            "mktree",
            "--missing",
            stdin=f"100644 blob {blob}\ta.txt\n040000 tree {empty}\tempty\n".encode(),
        )
        limits = self.limits()
        with mock.patch("shutil.rmtree", side_effect=OSError("cleanup failed")):
            self.assertRefused(
                "tree-mismatch",
                lambda: _owner().materialize(
                    self.repo, tree, self.root / "out", limits=limits
                ),
            )

    # G, I, M, S6350, B101: the child's argv, environment and descriptors.
    def test_the_git_child_is_started_by_absolute_path_on_the_trusted_lookup(
        self,
    ) -> None:
        owner = _owner()
        self.assertEqual(
            "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin", owner._GIT_ENV["PATH"]
        )
        tree = self.commit({"a.txt": b"a\n"})
        seen: list[list[str]] = []

        def popen(argv: list[str], **kwargs: Any) -> Any:
            seen.append(argv)
            raise OSError("stop")

        limits = self.limits()
        with mock.patch("subprocess.Popen", side_effect=popen):
            self.assertRefused(
                "git-failed", lambda: owner.tree_paths(self.repo, tree, limits=limits)
            )
        self.assertTrue(
            seen and os.path.isabs(seen[0][0]) and seen[0][0].endswith("/git"), seen
        )

    def test_the_popen_call_carries_its_bandit_justification(self) -> None:
        source = Path(_owner().__file__).read_text(encoding="utf-8").splitlines()
        lines = [line for line in source if "subprocess.Popen(" in line]
        self.assertTrue(lines and all("nosec B603" in line for line in lines), lines)

    def test_no_assert_statement_guards_production_logic(self) -> None:
        import ast

        tree = ast.parse(Path(_owner().__file__).read_text(encoding="utf-8"))
        asserts = [
            node.lineno for node in ast.walk(tree) if isinstance(node, ast.Assert)
        ]
        self.assertEqual([], asserts)

    def test_an_early_deadline_exit_closes_the_childs_stdin(self) -> None:
        owner = _owner()
        read_end, write_end = os.pipe()
        os.close(write_end)
        spent = self.limits(deadline=time.monotonic() - 1)
        self.assertRefused(
            "deadline",
            lambda: owner._git(
                self.repo, ["ls-tree"], limits=spent, cap=1, stdin=read_end
            ),
        )
        with self.assertRaises(OSError):
            os.fstat(read_end)

    def test_an_option_shaped_tree_id_is_refused_before_any_child(self) -> None:
        destination = self.root / "out"
        limits = self.limits()
        with mock.patch(
            "subprocess.Popen", side_effect=AssertionError("git was started")
        ):
            for value in ("-" + "a" * 39, "--output=/tmp/x" + "a" * 25, "A" * 40):
                with self.subTest(value=value):
                    self.assertRefused(
                        "unsupported-entry",
                        lambda value=value: _owner().materialize(
                            self.repo, value, destination, limits=limits
                        ),
                    )

    # K: a reused destination is bound to the tree it was written for.
    def test_a_destination_written_for_one_tree_is_not_reused_for_another(self) -> None:
        owner = _owner()
        ensure = getattr(owner, "materialize_or_verify", None)
        if ensure is None:
            self.fail("missing capability: tools.exact_tree.materialize_or_verify")
        first = self.commit({"a.txt": b"a\n", "old.txt": b"dropped later\n"})
        (self.repo / "old.txt").unlink()
        second = self.commit({})
        destination = self.root / "project"
        ensure(self.repo, first, destination, limits=self.limits())
        ensure(self.repo, first, destination, limits=self.limits())
        limits = self.limits()
        self.assertRefused(
            "tree-mismatch",
            lambda: ensure(self.repo, second, destination, limits=limits),
        )


class RoundThreeTests(ExactTreeFixture):
    """#446 round 3 (#389 6312793333): one RED per recorded class, run before the fix."""

    # O (S6350): an object id reaches Git's argv as its canonical, plain string.
    def test_an_object_id_reaches_git_as_its_canonical_plain_string(self) -> None:
        owner = _owner()

        class Carried(str):
            pass

        tree = self.commit({"a.txt": b"a\n"})
        seen: list[list[str]] = []

        def popen(argv: list[str], **kwargs: Any) -> Any:
            seen.append(list(argv))
            raise OSError("stop")

        limits = self.limits()
        with mock.patch("subprocess.Popen", side_effect=popen):
            self.assertRefused(
                "git-failed",
                lambda: owner.tree_paths(self.repo, Carried(tree), limits=limits),
            )
        self.assertTrue(seen, "git was never started")
        self.assertEqual(tree, seen[0][-1])
        self.assertIs(str, type(seen[0][-1]))

    # Q: the Semgrep justification sits on the Popen line, with the full rule id.
    def test_the_popen_call_carries_its_semgrep_justification_on_its_line(
        self,
    ) -> None:
        source = Path(_owner().__file__).read_text(encoding="utf-8").splitlines()
        lines = [line for line in source if "subprocess.Popen(" in line]
        self.assertTrue(lines and all(_NOSEMGREP in line for line in lines), lines)

    # T: the observed walk is bounded: no recursion, a deadline per entry, a budget.
    def test_a_tree_deeper_than_the_recursion_limit_is_materialized(self) -> None:
        # The recursion limit is lowered below the tree's depth for the call, so a walk
        # that recursed per level would fail; 200 levels stay within macOS's PATH_MAX
        # and its default of 256 descriptors (Revix 4336200061).
        depth = 200
        tree = self.commit({"d/" * depth + "f.txt": b"deep\n"})
        destination = self.root / "out"
        limits = self.limits()
        previous = sys.getrecursionlimit()
        sys.setrecursionlimit(len(traceback.extract_stack()) + 100)
        try:
            self.assertLess(sys.getrecursionlimit(), depth)
            result = _owner().materialize(self.repo, tree, destination, limits=limits)
        finally:
            sys.setrecursionlimit(previous)
        self.assertEqual(tree, result.tree)

    def test_a_flood_of_empty_directories_holds_at_the_bound_and_is_refused_past_it(
        self,
    ) -> None:
        # With max_files=0 the listing bound is 4,352 B: 870 names of 4 bytes cost
        # 5 B each (4,350 B), and one of 1 byte costs 2 B, exactly at the bound.
        root = self.root / "flood"
        root.mkdir()
        for index in range(870):
            (root / f"{index:04d}").mkdir()
        (root / "x").mkdir()
        limits = self.limits(max_files=0)
        empty = git(self.repo, "hash-object", "-t", "tree", "--stdin", stdin=b"")
        self.assertEqual(_owner().observed_tree(self.repo, root, limits=limits), empty)
        (root / "y").mkdir()
        limits = self.limits(max_files=0)
        self.assertRefused(
            "cap-bytes",
            lambda: _owner().observed_tree(self.repo, root, limits=limits),
        )

    def test_the_deadline_holds_for_entries_that_hold_no_file(self) -> None:
        owner = _owner()
        root = self.root / "empty-dirs"
        root.mkdir()
        for name in ("a", "b", "c"):
            (root / name).mkdir()
        spent = self.limits(deadline=time.monotonic() - 1)
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            self.assertRefused(
                "deadline",
                lambda: owner._observed(root_fd, "sha1", spent, frozenset()),
            )
        finally:
            os.close(root_fd)

    # U: no optional locks; the ownership check is never relaxed by a pin.
    def test_the_child_takes_no_optional_locks_and_pins_no_safe_directory(
        self,
    ) -> None:
        owner = _owner()
        self.assertEqual("0", owner._GIT_ENV.get("GIT_OPTIONAL_LOCKS"))
        self.assertFalse(
            [part for part in owner._GIT_OVERRIDES if "safe.directory" in part]
        )

    # V: a failed bind leaves no stale record that a later reuse could accept.
    def test_a_failed_bind_leaves_no_stale_record_to_reuse(self) -> None:
        owner = _owner()
        first = self.commit({"a.txt": b"a\n"})
        second = self.commit({"b.txt": b"b\n"})
        destination = self.root / "project"
        owner.materialize_or_verify(self.repo, first, destination, limits=self.limits())
        shutil.rmtree(destination)
        injected = owner.ExactTreeError("filesystem", "injected bind failure")
        limits = self.limits()
        with mock.patch.object(owner, "_bind", side_effect=injected):
            self.assertRefused(
                "filesystem",
                lambda: owner.materialize_or_verify(
                    self.repo, second, destination, limits=limits
                ),
            )
        self.assertRefused(
            "tree-mismatch",
            lambda: owner.materialize_or_verify(
                self.repo, first, destination, limits=limits
            ),
        )


class RoundFourTests(ExactTreeFixture):
    """#446 round 4 (#389 6313297746): one RED per recorded class, run before the fix."""

    # X (S6350): the repository is Git's working directory, never an argument.
    def test_the_repository_reaches_git_as_its_working_directory_not_its_argv(
        self,
    ) -> None:
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n"})
        seen: list[tuple[list[str], Any]] = []

        def popen(argv: list[str], **kwargs: Any) -> Any:
            seen.append((list(argv), kwargs.get("cwd")))
            raise OSError("stop")

        limits = self.limits()
        with mock.patch("subprocess.Popen", side_effect=popen):
            self.assertRefused(
                "git-failed", lambda: owner.tree_paths(self.repo, tree, limits=limits)
            )
        self.assertTrue(seen, "git was never started")
        argv, cwd = seen[0]
        self.assertFalse([part for part in argv if str(self.repo) in part], argv)
        self.assertNotIn("-C", argv)
        self.assertIsNotNone(cwd)
        self.assertEqual(os.fspath(self.repo), os.fspath(cwd))

    # AA (M13): each suppression on the Popen line carries its reason.
    def test_the_popen_suppressions_carry_their_reason(self) -> None:
        source = Path(_owner().__file__).read_text(encoding="utf-8").splitlines()
        lines = [line for line in source if "subprocess.Popen(" in line]
        self.assertTrue(lines, "no Popen line")
        for line in lines:
            self.assertIn(f"{_NOSEMGREP}  {_NOSEC_B603}", line)
            self.assertTrue(line.split(_NOSEC_B603, 1)[1].strip(), line)

    # AB: descriptor exhaustion is a named refusal, wherever it happens.
    def test_descriptor_exhaustion_is_named(self) -> None:
        owner = _owner()
        for number in (errno.EMFILE, errno.ENFILE):
            with self.subTest(errno=number):
                refusal = owner._filesystem(OSError(number, "exhausted"))
                self.assertEqual("cap-descriptors", refusal.code)

    def test_a_sinks_own_os_error_keeps_its_meaning(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        real_open = os.open

        def exhausted(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            if flags & os.O_CREAT and kwargs.get("dir_fd") is not None:
                raise OSError(errno.EMFILE, "Too many open files")
            return real_open(path, flags, *args, **kwargs)

        destination = self.root / "out"
        limits = self.limits()
        with mock.patch("os.open", side_effect=exhausted):
            self.assertRefused(
                "cap-descriptors",
                lambda: _owner().materialize(
                    self.repo, tree, destination, limits=limits
                ),
            )
        self.assertFalse(destination.exists())

    # Kill tests, added with the round-4 mutants: the sink's other failures, and
    # exhaustion at the other two points.
    def test_a_sinks_other_os_error_is_a_filesystem_refusal(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        real_open = os.open

        def denied(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            if flags & os.O_CREAT and kwargs.get("dir_fd") is not None:
                raise PermissionError(errno.EACCES, "Permission denied")
            return real_open(path, flags, *args, **kwargs)

        destination = self.root / "out"
        limits = self.limits()
        with mock.patch("os.open", side_effect=denied):
            self.assertRefused(
                "filesystem",
                lambda: _owner().materialize(
                    self.repo, tree, destination, limits=limits
                ),
            )

    def test_exhaustion_starting_git_is_named(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        limits = self.limits()
        with mock.patch(
            "subprocess.Popen", side_effect=OSError(errno.EMFILE, "Too many open files")
        ):
            self.assertRefused(
                "cap-descriptors",
                lambda: _owner().tree_paths(self.repo, tree, limits=limits),
            )

    def test_exhaustion_inside_the_drain_is_named(self) -> None:
        tree = self.commit({"a.txt": b"a\n"})
        limits = self.limits()
        with mock.patch(
            "selectors.DefaultSelector",
            side_effect=OSError(errno.EMFILE, "Too many open files"),
        ):
            self.assertRefused(
                "cap-descriptors",
                lambda: _owner().tree_paths(self.repo, tree, limits=limits),
            )


class RoundSevenTests(ExactTreeFixture):
    """#446 round 7 (#389 6314724299): one RED per recorded class, run before the fix."""

    # AJ: a FIFO swapped in for a file is refused, never waited on.
    def test_a_fifo_in_place_of_a_file_is_refused_not_waited_on(self) -> None:
        owner = _owner()
        root = self.root / "fifo-root"
        root.mkdir()
        os.mkfifo(root / "f")
        dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        limits = self.limits()
        waited, outcome = self.without_waiting(
            lambda: owner._blob_id_at(dir_fd, "f", 1, "sha1", limits), root / "f"
        )
        os.close(dir_fd)
        self.assertFalse(waited, "the open waited on a FIFO")
        self.assertEqual(["tree-mismatch"], outcome)

    def test_a_fifo_in_place_of_an_empty_file_is_not_its_blob(self) -> None:
        # Kill test, added with the round-7 mutants: opened without blocking, a FIFO
        # with no writer reads as empty, so only the type of the opened descriptor
        # tells it from an empty file.
        owner = _owner()
        root = self.root / "fifo-root"
        root.mkdir()
        os.mkfifo(root / "f")
        dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        limits = self.limits()
        try:
            self.assertRefused(
                "tree-mismatch",
                lambda: owner._blob_id_at(dir_fd, "f", 0, "sha1", limits),
            )
        finally:
            os.close(dir_fd)

    # AL: the materialized root has the mode a nested directory gets.
    def test_the_materialized_root_has_the_mode_of_a_nested_directory(self) -> None:
        tree = self.commit({"d/a.txt": b"a\n"})
        destination = self.root / "out"
        _owner().materialize(self.repo, tree, destination, limits=self.limits())
        self.assertEqual(
            stat.S_IMODE((destination / "d").stat().st_mode),
            stat.S_IMODE(destination.stat().st_mode),
        )

    # AM: a failed bind leaves no temporary record beside the destination.
    def test_a_failed_bind_leaves_no_temporary_record(self) -> None:
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n"})
        destination = self.root / "project"
        real_link = os.link

        def failing(source: Any, target: Any, *args: Any, **kwargs: Any) -> None:
            if os.fspath(target).endswith(".exact-tree"):
                raise OSError(errno.EIO, "injected")
            real_link(source, target, *args, **kwargs)

        limits = self.limits()
        with mock.patch("os.link", side_effect=failing):
            self.assertRefused(
                "filesystem",
                lambda: owner.materialize_or_verify(
                    self.repo, tree, destination, limits=limits
                ),
            )
        leftovers = [p.name for p in self.root.iterdir() if ".exact-tree" in p.name]
        self.assertEqual([], leftovers)

    def test_the_identity_walk_holds_one_descriptor_per_level(self) -> None:
        # Kill test, added with the round-7 mutants: with the soft descriptor limit
        # between one and two descriptors per level, a tree materializes only if
        # the write's directory chain is released before the identity walk.
        depth = 200
        tree = self.commit({"d/" * depth + "f.txt": b"deep\n"})
        destination = self.root / "out"
        limits = self.limits()
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        listing = "/dev/fd" if os.path.isdir("/dev/fd") else "/proc/self/fd"
        if not os.path.isdir(listing):
            self.skipTest("this platform lists no open descriptors")
        ceiling = len(os.listdir(listing)) + depth + 60
        if soft != resource.RLIM_INFINITY and soft < ceiling:
            self.skipTest("the descriptor limit is already below the test's ceiling")
        resource.setrlimit(resource.RLIMIT_NOFILE, (ceiling, hard))
        try:
            result = _owner().materialize(self.repo, tree, destination, limits=limits)
        finally:
            resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
        self.assertEqual(tree, result.tree)

    # AI: a fixture commit spawns no detached housekeeping into a directory that the
    # test's cleanup removes (python-compatibility 3.12, job 119192065066).
    def test_a_fixture_commit_spawns_no_background_maintenance(self) -> None:
        trace = self.root / "git.trace"
        (self.repo / "a.txt").write_bytes(b"a\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "c", env={**_ENV, "GIT_TRACE": str(trace)})
        traced = trace.read_text(encoding="utf-8")
        self.assertNotIn("maintenance run --auto", traced)
        self.assertNotIn("gc --auto", traced)


class RoundEightTests(ExactTreeFixture):
    """#446 round 8 (#389 6315273156): one RED per recorded class, run before the fix."""

    # AO: the staging directory stays owner-only while the tree is written into it.
    def test_the_staging_directory_is_owner_only_while_it_is_written(self) -> None:
        owner = _owner()
        tree = self.commit({"d/a.txt": b"a\n"})
        destination = self.root / "out"
        real_write_tree = owner._write_tree
        seen: list[int] = []

        def spy(
            repo: Path, tree: str, algorithm: str, directories: Any, limits: Any
        ) -> Any:
            seen.append(
                stat.S_IMODE(os.fstat(directories.at("", create=False)).st_mode)
            )
            return real_write_tree(repo, tree, algorithm, directories, limits)

        with mock.patch.object(owner, "_write_tree", side_effect=spy):
            owner.materialize(self.repo, tree, destination, limits=self.limits())
        self.assertEqual(1, len(seen))
        self.assertEqual(0, seen[0] & 0o077, oct(seen[0]))
        self.assertEqual(
            stat.S_IMODE((destination / "d").stat().st_mode),
            stat.S_IMODE(destination.stat().st_mode),
        )

    # AQ: the listing streams into entries; it is never held as one buffer.
    def test_the_listing_streams_into_entries(self) -> None:
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n", "d/b.txt": b"b\n"})
        real_git = owner._git
        calls: list[tuple[str, bool]] = []

        def spy(repo: Path, args: list[str], **kwargs: Any) -> Any:
            calls.append((args[0], kwargs.get("sink") is not None))
            return real_git(repo, args, **kwargs)

        with mock.patch.object(owner, "_git", side_effect=spy):
            paths = owner.tree_paths(self.repo, tree, limits=self.limits())
        self.assertEqual(frozenset({"a.txt", "d/b.txt"}), paths)
        self.assertIn(("ls-tree", True), calls)
        self.assertNotIn(("ls-tree", False), calls)

    def test_a_listing_that_ends_inside_a_record_is_a_refusal(self) -> None:
        # Kill test, added with the round-8 mutants: `-z` ends every record with NUL,
        # so bytes left over when the stream ends are a malformed record.
        owner = _owner()
        tree = self.commit({"a.txt": b"a\n"})
        limits = self.limits()
        unterminated = f"100644 blob {'a' * 40}\ta.txt".encode()
        with mock.patch.object(owner, "_git", side_effect=self.feeding(unterminated)):
            self.assertRefused(
                "git-failed", lambda: owner.tree_paths(self.repo, tree, limits=limits)
            )


class RoundElevenTests(ExactTreeFixture):
    """#446 round 11 (#389 6317039166)."""

    # AU: no Git child fetches, so a promisor remote's command never runs, even where
    # the repository re-allows its transport and Git ignores GIT_NO_LAZY_FETCH
    # (CodeAnt 4337243054, PAO 6317385619).
    def test_a_promisor_remote_runs_no_command(self) -> None:
        marker = self.root / "ran"
        line = f"100644 blob {'1' * 40}\tf.txt\n".encode()
        tree = git(self.repo, "mktree", "--missing", stdin=line)
        for key, value in (
            ("core.repositoryformatversion", "1"),
            ("extensions.partialClone", "o"),
            ("remote.o.url", str(self.root)),
            ("remote.o.promisor", "true"),
            ("remote.o.uploadpack", f"touch {marker}; false"),
            ("protocol.file.allow", "always"),
        ):
            git(self.repo, "config", key, value)
        out, limits, env = self.root / "out", self.limits(), _owner()._GIT_ENV
        kept = {k: v for k, v in env.items() if k != "GIT_NO_LAZY_FETCH"}
        with mock.patch.dict(env, kept, clear=True):
            self.assertRefused(
                "git-failed",
                lambda: _owner().materialize(self.repo, tree, out, limits=limits),
            )
        self.assertFalse(marker.exists())

    # AV: a short write never publishes a truncated record.
    def test_a_short_write_publishes_the_whole_record(self) -> None:
        owner, destination = _owner(), self.root / "project"
        destination.mkdir()
        real_write = os.write
        with mock.patch(
            "os.write", side_effect=lambda fd, data: real_write(fd, bytes(data)[:5])
        ):
            owner._bind(destination, owner._Record("a" * 40, 1, 2))
        self.assertEqual(owner._Record("a" * 40, 1, 2), owner._bound_tree(destination))

    # AW: a link target holding a NUL cannot be written exactly.
    def test_a_link_target_with_a_nul_is_refused(self) -> None:
        tree, out, limits = (
            self.link_tree({"t": "a\0b"}),
            self.root / "out",
            self.limits(),
        )
        self.assertRefused(
            "unsupported-entry",
            lambda: _owner().materialize(self.repo, tree, out, limits=limits),
        )

    # AX: the deadline holds before each link is created.
    def test_the_deadline_holds_between_links(self) -> None:
        tree = self.link_tree({"a": "x", "b": "x", "c": "x"}, {"x": b"x\n"})
        real_symlink, real_clock, made = os.symlink, time.monotonic, []

        def symlink(target: str, name: str, **kwargs: Any) -> None:
            made.append(name)
            real_symlink(target, name, **kwargs)

        out, limits = self.root / "out", self.limits()
        with (
            mock.patch("os.symlink", side_effect=symlink),
            mock.patch(
                "time.monotonic", side_effect=lambda: real_clock() + 1e9 * bool(made)
            ),
        ):
            self.assertRefused(
                "deadline",
                lambda: _owner().materialize(self.repo, tree, out, limits=limits),
            )
        self.assertEqual(["a"], made)


class RoundTwelveTests(ExactTreeFixture):
    """#446 round 12: the reviews of the sealed c199bf12 (#389 6318984068)."""

    # AY: a platform without an open flag the owner relies on refuses the module when
    # it loads; it never runs without that flag's guarantee (Q 4338237790).
    def test_a_platform_without_an_open_flag_is_refused(self) -> None:
        source = _owner().__file__
        for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"):
            spec = importlib.util.spec_from_file_location("exact_tree_probe", source)
            if spec is None or spec.loader is None:
                self.fail("the owner's source cannot be loaded")
            probe, saved = importlib.util.module_from_spec(spec), getattr(os, flag)
            delattr(os, flag)
            try:
                with self.subTest(flag=flag):
                    with (
                        mock.patch.dict(sys.modules, {"exact_tree_probe": probe}),
                        self.assertRaises(AttributeError) as raised,
                    ):
                        spec.loader.exec_module(probe)
                    self.assertIn(flag, str(raised.exception))
            finally:
                setattr(os, flag, saved)


if __name__ == "__main__":
    unittest.main()
