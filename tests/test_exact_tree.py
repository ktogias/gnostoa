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
    "PATH": "/usr/bin:/bin",
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
                with self.assertRaises(owner.ExactTreeError) as raised:
                    owner.verify_tracked(self.repo, tree, root, limits=self.limits())
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


if __name__ == "__main__":
    unittest.main()
