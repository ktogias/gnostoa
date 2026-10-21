"""The exact commit-tree owner (#389 F3 S2 A, the owner's Option A 6268025835).

One bounded owner materializes a Git tree's exact bytes and independently rebuilds a
directory's tree identity, for the capsule compiler and executor first. It never
reads the caller's or the repository's configuration or attributes, never runs a
configured driver, and refuses what it cannot represent exactly (S2-MAT-01,
S2-A3-01, Router 6267325366 and 6297725852).
"""

from __future__ import annotations

import importlib
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    # The repository's trusted executable lookup (AGENTS.md), as the owner uses it.
    "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin",
}


def git(repo: Path, *args: str, stdin: bytes | None = None) -> str:
    return (
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            input=stdin,
            env=_ENV,
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

    def limits(self, **overrides: Any) -> Any:
        values: dict[str, Any] = {
            "deadline": time.monotonic() + 60,
            "max_files": 1_000,
            "max_bytes": 1 << 20,
        }
        values.update(overrides)
        return _owner().Limits(**values)

    def blob(self, tree: str, path: str) -> bytes:
        return subprocess.run(
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
    def assertRefused(self, code: str, call: Any) -> None:
        owner = _owner()
        with self.assertRaises(owner.ExactTreeError) as raised:
            call()
        self.assertEqual(code, raised.exception.code)

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
            None, lambda: _owner().observed_tree(self.repo, alias, limits=limits)
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
                mock.patch.object(owner, "_git", return_value=listing),
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
        with mock.patch.object(owner, "_git", return_value=b"100644 blob XYZ\ta.txt\0"):
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
                mock.patch.object(owner, "_git", return_value=listing),
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


if __name__ == "__main__":
    unittest.main()
