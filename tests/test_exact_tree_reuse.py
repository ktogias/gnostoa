"""The exact-tree owner's reuse, on-disk containment and tree-record tests (#389 F3 S2
A), moved from `test_exact_tree` as one cohesive group to keep each module's patch
within merge admission's per-file bound (Router #389 6317709857). The fixture and `_owner`
stay in `test_exact_tree` and are imported, never copied.
"""

from __future__ import annotations

import functools
import os
import stat
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from test_exact_tree import ExactTreeFixture, _owner, git


def _open_descriptors(case: unittest.TestCase) -> int:
    """This process's open descriptors, as Linux and macOS both list them."""
    for listing in ("/dev/fd", "/proc/self/fd"):
        if os.path.isdir(listing):
            return len(os.listdir(listing))
    case.skipTest("this platform lists no open descriptors")


class RoundFiveTests(ExactTreeFixture):
    """#446 round 5 (Router #389 6313854024, option A): a reused tracked link stays
    inside the root through the components actually on disk. RED first."""

    def setUp(self) -> None:
        super().setUp()
        self.outside = self.root / "outside"
        (self.outside / "dir").mkdir(parents=True)
        (self.outside / "secret").write_bytes(b"secret\n")
        self.count = 0

    def reused(
        self,
        links: dict[str, str],
        files: dict[str, bytes] | None = None,
        *,
        ignore: tuple[str, ...] = (),
    ) -> tuple[str, Path]:
        tree = self.link_tree(links, {"keep.txt": b"k\n", **(files or {})})
        self.count += 1
        destination = self.root / f"project-{self.count}"
        _owner().materialize_or_verify(
            self.repo, tree, destination, limits=self.limits(), ignore=ignore
        )
        return tree, destination

    def again(
        self, tree: str, destination: Path, *, ignore: tuple[str, ...] = ()
    ) -> None:
        _owner().materialize_or_verify(
            self.repo, tree, destination, limits=self.limits(), ignore=ignore
        )

    def open_descriptors(self) -> int:
        return _open_descriptors(self)

    def plant(self, destination: Path, name: str, pointed: Path | str) -> None:
        """An untracked link a run left behind, relative to where it sits."""
        link = destination / name
        link.parent.mkdir(parents=True, exist_ok=True)
        target = (
            pointed
            if isinstance(pointed, str)
            else os.path.relpath(pointed, link.parent)
        )
        os.symlink(target, link)

    # The two supplied escapes (Revix 4335680236).
    def test_a_reused_tracked_link_cannot_escape_through_an_untracked_link(
        self,
    ) -> None:
        for target, pointed in (
            ("u/secret", self.outside),
            ("u", self.outside / "secret"),
        ):
            with self.subTest(target=target):
                tree, destination = self.reused({"t": target})
                self.plant(destination, "u", pointed)
                self.assertRefused(
                    "escaping-link",
                    lambda tree=tree, destination=destination: self.again(
                        tree, destination
                    ),
                )

    def test_a_deeper_mixed_chain_cannot_escape(self) -> None:
        # d/t -> ../a/b/x, where a is the tracked link a -> real and real/b is an
        # untracked link out of the root.
        tree, destination = self.reused(
            {"a": "real", "d/t": "../a/b/x"},
            {"real/f.txt": b"f\n", "d/g.txt": b"g\n"},
        )
        self.plant(destination, "real/b", self.outside)
        self.assertRefused("escaping-link", lambda: self.again(tree, destination))

    def test_a_physical_parent_through_an_untracked_link_cannot_escape(self) -> None:
        # Lexically t -> u/../outside/secret stays inside; with u -> . the physical
        # parent of u is above the root.
        tree, destination = self.reused({"t": "u/../outside/secret"})
        self.plant(destination, "u", ".")
        self.assertRefused("escaping-link", lambda: self.again(tree, destination))

    def test_a_loop_of_untracked_links_is_refused(self) -> None:
        tree, destination = self.reused({"t": "u"})
        self.plant(destination, "u", "v")
        self.plant(destination, "v", "u")
        self.assertRefused("escaping-link", lambda: self.again(tree, destination))

    def test_an_unreadable_untracked_link_is_a_refusal_not_containment(self) -> None:
        tree, destination = self.reused({"t": "u/x"})
        (destination / "real").mkdir()
        (destination / "real" / "x").write_bytes(b"x\n")
        self.plant(destination, "u", "real")
        real_readlink = os.readlink

        def refused(path: Any, *args: Any, **kwargs: Any) -> str:
            if os.fspath(path) == "u":
                raise PermissionError(13, "Permission denied")
            return real_readlink(path, *args, **kwargs)

        with mock.patch("os.readlink", side_effect=refused):
            self.assertRefused("filesystem", lambda: self.again(tree, destination))

    def test_the_on_disk_check_keeps_the_single_deadline(self) -> None:
        owner = _owner()
        resolver = getattr(owner, "_resolves_on_disk", None)
        if resolver is None:
            self.fail("missing capability: tools.exact_tree._resolves_on_disk")
        _, destination = self.reused({"t": "u/x"})
        self.plant(destination, "u", "real")
        spent = self.limits(deadline=time.monotonic() - 1)
        root_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
        try:
            self.assertRefused("deadline", lambda: resolver(root_fd, "t", "u/x", spent))
        finally:
            os.close(root_fd)

    # Kill tests, added with the round-5 mutants and labelled as such.
    def test_verify_tracked_accepts_a_link_past_a_missing_component(self) -> None:
        # Round 12 (G1 W, Router #389 6319318065): the missing component reaches
        # nothing in the tree as written and on disk, so both checks accept it. A
        # component created there later is the disk check's to refuse.
        tree = self.link_tree({"t": "missing/../../outside"}, {"keep.txt": b"k\n"})
        root = self.root / "reused"
        root.mkdir()
        (root / "keep.txt").write_bytes(b"k\n")
        os.symlink("missing/../../outside", root / "t")
        _owner().verify_tracked(self.repo, tree, root, limits=self.limits())

    def test_verify_tracked_refuses_an_escape_through_an_ignored_directory(
        self,
    ) -> None:
        # The tree's own check, not the disk's: `d` is a directory in the tree as
        # written, ignored and absent on disk, so only the tree carries t outside.
        files = {"keep.txt": b"k\n", "d/x": b"x\n"}
        tree = self.link_tree({"t": "d/../../outside"}, files)
        root = self.root / "reused"
        root.mkdir()
        (root / "keep.txt").write_bytes(b"k\n")
        os.symlink("d/../../outside", root / "t")
        limits = self.limits()
        self.assertRefused(
            "escaping-link",
            lambda: _owner().verify_tracked(
                self.repo, tree, root, limits=limits, ignore=("d",)
            ),
        )

    def test_an_unreadable_component_is_a_refusal_not_a_missing_one(self) -> None:
        tree, destination = self.reused({"t": "u/x"})
        (destination / "u").mkdir()
        real_stat = os.stat

        def refused(path: Any, *args: Any, **kwargs: Any) -> Any:
            if os.fspath(path) == "u":
                raise PermissionError(13, "Permission denied")
            return real_stat(path, *args, **kwargs)

        with mock.patch("os.stat", side_effect=refused):
            self.assertRefused("filesystem", lambda: self.again(tree, destination))

    def test_an_absolute_untracked_link_on_a_tracked_path_is_refused(self) -> None:
        tree, destination = self.reused({"t": "u/secret"})
        self.plant(destination, "u", os.fspath(self.outside))
        self.assertRefused("escaping-link", lambda: self.again(tree, destination))

    # Falsifiers: legitimate reuse stays accepted.
    def test_a_contained_untracked_link_on_a_tracked_path_is_kept(self) -> None:
        tree, destination = self.reused({"t": "u/x"})
        (destination / "real").mkdir()
        (destination / "real" / "x").write_bytes(b"x\n")
        self.plant(destination, "u", "real")
        self.again(tree, destination)

    def test_an_escaping_output_off_every_tracked_path_is_allowed(self) -> None:
        tree, destination = self.reused({"t": "keep.txt"})
        self.plant(destination, "venv/bin/python", "/usr/bin/env")
        self.again(tree, destination)

    def test_a_dangling_in_root_tracked_link_is_allowed(self) -> None:
        tree, destination = self.reused({"t": "missing/x", "s": "build/out"})
        (destination / "build").mkdir()
        self.again(tree, destination)

    def test_a_declared_generated_path_keeps_its_exclusion(self) -> None:
        tree, destination = self.reused(
            {"t": "gen.txt"}, {"gen.txt": b"tracked\n"}, ignore=("gen.txt",)
        )
        (destination / "gen.txt").write_bytes(b"generated by the run\n")
        self.again(tree, destination, ignore=("gen.txt",))

    def test_the_check_leaves_no_descriptor_behind(self) -> None:
        tree, destination = self.reused({"t": "u/x", "w": "keep.txt"})
        (destination / "real").mkdir()
        (destination / "real" / "x").write_bytes(b"x\n")
        self.plant(destination, "u", "real")
        before = self.open_descriptors()
        self.again(tree, destination)
        self.assertEqual(before, self.open_descriptors())
        os.unlink(destination / "u")
        self.plant(destination, "u", self.outside)
        self.assertRefused("escaping-link", lambda: self.again(tree, destination))
        self.assertEqual(before, self.open_descriptors())


class RoundSixTests(ExactTreeFixture):
    """#446 round 6 (#389 6314305587): one RED per recorded class, run before the fix."""

    # AE: an ignored directory covers its subtree, as `observed_tree`'s does.
    def test_verify_tracked_skips_an_ignored_directory_and_its_subtree(self) -> None:
        tree = self.commit({"gen/out.txt": b"tracked\n", "keep.txt": b"k\n"})
        root = self.root / "reused"
        _owner().materialize(self.repo, tree, root, limits=self.limits())
        (root / "gen" / "out.txt").write_bytes(b"generated by the run\n")
        _owner().verify_tracked(
            self.repo, tree, root, limits=self.limits(), ignore=("gen",)
        )

    # AG: the deadline holds before every descent to a tracked link's parent.
    def test_a_spent_deadline_opens_no_parent_directory(self) -> None:
        owner = _owner()
        tree = self.link_tree({"d/t": "x"}, {"d/f.txt": b"f\n"})
        destination = self.root / "reused"
        owner.materialize(self.repo, tree, destination, limits=self.limits())
        spent = self.limits(deadline=time.monotonic() - 1)
        real_open = os.open
        opened: list[Any] = []

        def counting(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            opened.append(path)
            return real_open(path, flags, *args, **kwargs)

        root_fd = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
        try:
            with mock.patch("os.open", side_effect=counting):
                self.assertRefused(
                    "deadline",
                    lambda: owner._resolves_on_disk(root_fd, "d/t", "x", spent),
                )
        finally:
            os.close(root_fd)
        self.assertEqual([], opened)

    def test_a_name_that_only_prefixes_a_directory_skips_nothing(self) -> None:
        tree = self.commit({"gen/out.txt": b"tracked\n", "keep.txt": b"k\n"})
        root = self.root / "reused"
        _owner().materialize(self.repo, tree, root, limits=self.limits())
        (root / "gen" / "out.txt").write_bytes(b"generated by the run\n")
        limits = self.limits()
        self.assertRefused(
            "tree-mismatch",
            lambda: _owner().verify_tracked(
                self.repo, tree, root, limits=limits, ignore=("ge",)
            ),
        )


class RoundNineTests(ExactTreeFixture):
    """#446 round 9 (#389 6315681106): one RED per recorded class, run before the fix."""

    # AR: the tree-binding record is opened without blocking and must be a file.
    def test_a_fifo_in_place_of_the_record_is_refused_not_waited_on(self) -> None:
        owner = _owner()
        destination = self.root / "project"
        destination.mkdir()
        (destination / "x.txt").write_bytes(b"x\n")
        record = self.root / ".project.exact-tree"
        os.mkfifo(record)
        waited, outcome = self.without_waiting(
            lambda: owner._bound_tree(destination), record
        )
        self.assertFalse(waited, "the record's open waited on a FIFO")
        self.assertEqual(["unsafe-path"], outcome)


class RoundTenTests(ExactTreeFixture):
    """#446 round 10 (#389 6316110363): one RED per recorded class, run first."""

    # AS: a record another process wrote is refused and kept, never replaced.
    def test_a_concurrent_record_is_refused_not_replaced(self) -> None:
        owner = _owner()
        destination = self.root / "project"
        destination.mkdir()
        record = self.root / ".project.exact-tree"
        record.write_text("another\n", encoding="ascii")
        binding = owner._Record("a" * 40, 1, 2)
        self.assertRefused("tree-mismatch", lambda: owner._bind(destination, binding))
        self.assertEqual("another\n", record.read_text(encoding="ascii"))
        names = [p.name for p in self.root.iterdir() if ".exact-tree." in p.name]
        self.assertEqual([], names)


class RoundTwelveReuseTests(ExactTreeFixture):
    """#446 round 12 (Router #389 6319318065): G1 W, the immutable tree as written, and
    G2 I, the record bound to the published directory as well as its tree. RED first."""

    def empty_tree(self) -> str:
        return git(self.repo, "mktree", stdin=b"")

    def through(self, target: str) -> str:
        return self.link_tree({"l": target}, {"f": b"f\n", "d/x": b"x\n"})

    def reuse(self, tree: str, destination: Path) -> Any:
        return functools.partial(
            _owner().materialize_or_verify,
            self.repo,
            tree,
            destination,
            limits=self.limits(),
        )

    # G1: a link through a tracked file or a component the tree does not have reaches
    # nothing, as the kernel resolves it on the written tree, so the tree is written.
    def test_a_link_through_a_file_or_a_missing_component_is_written(self) -> None:
        for name, target in (("file", "f/../../outside"), ("missing", "m/../../out")):
            with self.subTest(name):
                tree, out = self.through(target), self.root / f"out-{name}"
                _owner().materialize(self.repo, tree, out, limits=self.limits())
                self.assertEqual(target, os.readlink(out / "l"))

    # G1: a link through a real directory still escapes, and is refused (the control).
    def test_a_link_through_a_directory_is_still_refused(self) -> None:
        tree, out, limits = self.through("d/../../out"), self.root / "o", self.limits()
        self.assertRefused(
            "escaping-link",
            lambda: _owner().materialize(self.repo, tree, out, limits=limits),
        )

    # G1: on reuse, the disk check refuses a missing component that has since become
    # an escaping directory or link.
    def test_a_missing_component_that_escapes_later_is_refused_on_reuse(self) -> None:
        tree = self.through("m/../../out")
        for name in ("directory", "link"):
            with self.subTest(name):
                destination = self.root / f"project-{name}"
                self.reuse(tree, destination)()
                if name == "directory":
                    (destination / "m").mkdir()
                else:
                    (destination / "m").symlink_to("d")
                self.assertRefused("escaping-link", self.reuse(tree, destination))

    # G2: a writer whose rename replaces a published empty tree is not blessed, and
    # the empty tree is never reused over that writer's tracked file (CodeAnt).
    def test_a_replaced_empty_tree_is_never_reused_as_it(self) -> None:
        owner, empty = _owner(), self.empty_tree()
        other = self.commit({"b.txt": b"b\n"})
        destination, real_rename, raced = self.root / "project", os.rename, []

        def rename(source: Any, target: Any, **kwargs: Any) -> None:
            real_rename(source, target, **kwargs)
            if not raced and target == destination.name:
                raced.append(True)
                aside = self.root / "b"
                owner.materialize(self.repo, other, aside, limits=self.limits())
                real_rename(aside, destination)

        with mock.patch("os.rename", side_effect=rename):
            self.assertRefused("tree-mismatch", self.reuse(empty, destination))
        self.assertRefused("tree-mismatch", self.reuse(empty, destination))
        self.assertEqual(b"b\n", (destination / "b.txt").read_bytes())

    # G2: a directory replaced after the bind is found by the check that follows it.
    def test_a_directory_replaced_after_the_bind_is_not_blessed(self) -> None:
        owner, empty = _owner(), self.empty_tree()
        other = self.commit({"b.txt": b"b\n"})
        destination, real_bind = self.root / "project", owner._bind

        def bind(where: Path, record: Any) -> None:
            real_bind(where, record)
            aside = self.root / "b"
            owner.materialize(self.repo, other, aside, limits=self.limits())
            os.rename(aside, destination)

        with mock.patch.object(owner, "_bind", side_effect=bind):
            self.assertRefused("tree-mismatch", self.reuse(empty, destination))
        self.assertRefused("tree-mismatch", self.reuse(empty, destination))
        self.assertEqual(b"b\n", (destination / "b.txt").read_bytes())

    # G2: a publisher whose directory was replaced before it binds refuses without
    # removing the winner's record, and the winner is reused.
    def test_a_replaced_publisher_keeps_the_winners_record(self) -> None:
        owner, empty = _owner(), self.empty_tree()
        other = self.commit({"b.txt": b"b\n"})
        destination, real_rename, raced = self.root / "project", os.rename, []

        def rename(source: Any, target: Any, **kwargs: Any) -> None:
            real_rename(source, target, **kwargs)
            if not raced and target == destination.name:
                raced.append(True)
                aside = self.root / "b"
                owner.materialize(self.repo, other, aside, limits=self.limits())
                real_rename(aside, destination)
                info = os.lstat(destination)
                owner._bind(destination, owner._Record(other, info.st_dev, info.st_ino))

        with mock.patch("os.rename", side_effect=rename):
            self.assertRefused("tree-mismatch", self.reuse(empty, destination))
        record = (self.root / ".project.exact-tree").read_text(encoding="ascii")
        self.assertIn(other, record)
        self.reuse(other, destination)()

    def swapping(
        self, destination: Path, into: Path, aside: Path, after: str = "_bound_tree"
    ) -> Any:
        """The owner's `after`, swapping `into` for `destination` once it has run."""
        real = getattr(_owner(), after)

        def run(where: Path) -> Any:
            result = real(where)
            os.rename(destination, aside)
            os.rename(into, destination)
            return result

        return mock.patch.object(_owner(), after, side_effect=run)

    # G2: reuse verifies the directory whose identity it checked, not one swapped in.
    def test_reuse_verifies_the_directory_whose_identity_it_checked(self) -> None:
        tree, destination = self.commit({"a.txt": b"a\n"}), self.root / "project"
        self.reuse(tree, destination)()
        (destination / "a.txt").write_bytes(b"changed\n")
        pristine = self.root / "pristine"
        _owner().materialize(self.repo, tree, pristine, limits=self.limits())
        with self.swapping(destination, pristine, self.root / "bound"):
            self.assertRefused("tree-mismatch", self.reuse(tree, destination))

    # G2: the identity checked is the verified directory's own, never the path's,
    # whenever the path is swapped after the root is opened (the swap point
    # strengthened with the round-12 mutants).
    def test_reuse_checks_the_identity_of_the_directory_it_verifies(self) -> None:
        tree, destination = self.commit({"a.txt": b"a\n"}), self.root / "project"
        self.reuse(tree, destination)()
        bound = self.root / "bound"
        os.rename(destination, bound)
        _owner().materialize(self.repo, tree, destination, limits=self.limits())
        unbound = self.root / "unbound"
        with self.swapping(destination, bound, unbound, after="_open_root"):
            self.assertRefused("tree-mismatch", self.reuse(tree, destination))

    # G2: one versioned record names the tree and the directory, in either algorithm.
    def test_the_record_round_trips_in_either_algorithm(self) -> None:
        owner, destination = _owner(), self.root / "project"
        for tree in ("a" * 40, "b" * 64):
            with self.subTest(len(tree)):
                record = owner._Record(tree, 2**64 - 1, 2**64 - 2)
                owner._unbind(destination)
                owner._bind(destination, record)
                self.assertEqual(record, owner._bound_tree(destination))
        written = (self.root / ".project.exact-tree").read_bytes()
        self.assertTrue(written.startswith(owner._RECORD_VERSION.encode() + b" "))

    # G2: a missing, old, malformed, oversized or mismatched record never makes a
    # non-empty destination trusted, and the record and bytes are left as they were.
    def test_an_untrusted_record_is_refused_and_kept(self) -> None:
        tree, destination = self.commit({"a.txt": b"a\n"}), self.root / "project"
        self.reuse(tree, destination)()
        record = self.root / ".project.exact-tree"
        current = record.read_text(encoding="ascii")
        version, tree_id, device, inode = current.split()
        for name, text in (
            ("missing", None),
            ("old", f"{tree}\n"),
            ("malformed", f"{version} {tree_id.upper()} {device} {inode}\n"),
            ("oversized", current + " " * 4096),
            ("another directory", f"{version} {tree_id} {device} {int(inode) + 1}\n"),
            # A kill case, added with the round-12 mutants: another version.
            ("another version", f"{version}9 {tree_id} {device} {inode}\n"),
        ):
            with self.subTest(name):
                record.unlink()
                if text is not None:
                    record.write_text(text, encoding="ascii")
                self.assertRefused("tree-mismatch", self.reuse(tree, destination))
                self.assertEqual(text, record.read_text() if text else None)
                self.assertEqual(b"a\n", (destination / "a.txt").read_bytes())
                record.unlink(missing_ok=True)
                record.write_text(current, encoding="ascii")

    # G2: a filesystem that gives the directory no identity is a coded refusal, made
    # before anything is published.
    def test_an_unavailable_identity_is_refused_before_publishing(self) -> None:
        owner = _owner()
        nameless = os.stat_result((stat.S_IFDIR | 0o755, 0, 1, 2, 0, 0, 0, 0, 0, 0))
        with mock.patch("os.fstat", return_value=nameless):
            self.assertRefused("identity-unavailable", lambda: owner._identity(0))
        tree, destination = self.commit({"a.txt": b"a\n"}), self.root / "project"
        refusal = owner.ExactTreeError("identity-unavailable", "injected")
        with mock.patch.object(owner, "_identity", side_effect=refusal):
            self.assertRefused("identity-unavailable", self.reuse(tree, destination))
        self.assertFalse(destination.exists())
        names = [p.name for p in self.root.iterdir() if p.name.startswith(".project")]
        self.assertEqual([], names)

    # G2: the empty tree is bound and reused like any other, its outputs allowed.
    def test_the_empty_tree_is_bound_and_reused_with_its_outputs(self) -> None:
        empty, destination = self.empty_tree(), self.root / "project"
        self.reuse(empty, destination)()
        (destination / "out.txt").write_bytes(b"run output\n")
        self.reuse(empty, destination)()
        self.assertEqual(b"run output\n", (destination / "out.txt").read_bytes())

    # G2: a SHA-256 tree is bound and reused, its outputs allowed.
    def test_a_sha256_tree_is_bound_and_reused(self) -> None:
        repo, destination = self.root / "repo256", self.root / "project"
        repo.mkdir()
        git(repo, "init", "-q", "--object-format=sha256", "-b", "main")
        (repo / "a.txt").write_bytes(b"a\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "c")
        tree, limits = git(repo, "rev-parse", "HEAD^{tree}"), self.limits()
        self.assertEqual(64, len(tree))
        _owner().materialize_or_verify(repo, tree, destination, limits=limits)
        (destination / "out.txt").write_bytes(b"run output\n")
        _owner().materialize_or_verify(repo, tree, destination, limits=self.limits())

    # G2: a stale record beside a removed destination does not block a fresh tree
    # there, and the fresh tree is reused (a positive control).
    def test_a_stale_record_does_not_block_a_fresh_tree(self) -> None:
        first, destination = self.commit({"a.txt": b"a\n"}), self.root / "project"
        second = self.commit({"b.txt": b"b\n"})
        self.reuse(first, destination)()
        for path in destination.iterdir():
            path.unlink()
        self.reuse(second, destination)()
        self.reuse(second, destination)()

    # G2: a short read still reads the whole record (a kill test, added with the
    # round-12 mutants).
    def test_a_short_read_still_reads_the_whole_record(self) -> None:
        owner, destination = _owner(), self.root / "project"
        record, real_read = owner._Record("a" * 64, 1, 2), os.read
        owner._bind(destination, record)
        with mock.patch("os.read", side_effect=lambda fd, n: real_read(fd, min(n, 5))):
            self.assertEqual(record, owner._bound_tree(destination))

    # G2: binding, reuse and their refusals release every descriptor they open.
    def test_binding_and_reuse_release_their_descriptors(self) -> None:
        owner, tree = _owner(), self.commit({"a.txt": b"a\n"})
        other, destination = self.commit({"b.txt": b"b\n"}), self.root / "project"
        before = _open_descriptors(self)
        self.reuse(tree, destination)()
        self.reuse(tree, destination)()
        self.assertRefused("tree-mismatch", self.reuse(other, destination))
        failed = self.root / "failed"
        refusal = owner.ExactTreeError("filesystem", "injected bind failure")
        with mock.patch.object(owner, "_bind", side_effect=refusal):
            self.assertRefused("filesystem", self.reuse(tree, failed))
        self.assertEqual(before, _open_descriptors(self))


if __name__ == "__main__":
    unittest.main()
