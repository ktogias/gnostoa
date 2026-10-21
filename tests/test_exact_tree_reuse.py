"""The exact-tree owner's reuse, on-disk containment and tree-record tests (#389 F3 S2
A), moved from `test_exact_tree` as one cohesive group to keep each module's patch
within merge admission's per-file bound (Router #389 6317709857). The fixture and `_owner`
stay in `test_exact_tree` and are imported, never copied.
"""

from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from test_exact_tree import ExactTreeFixture, _owner


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
        """This process's open descriptors, as Linux and macOS both list them."""
        for listing in ("/dev/fd", "/proc/self/fd"):
            if os.path.isdir(listing):
                return len(os.listdir(listing))
        self.skipTest("this platform lists no open descriptors")

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
    def test_verify_tracked_refuses_a_lexical_escape_past_a_missing_component(
        self,
    ) -> None:
        # On disk the missing component reaches nothing today; the tree's own check
        # still refuses it, since creating `missing` later would carry t outside.
        tree = self.link_tree({"t": "missing/../../outside"}, {"keep.txt": b"k\n"})
        root = self.root / "reused"
        root.mkdir()
        (root / "keep.txt").write_bytes(b"k\n")
        os.symlink("missing/../../outside", root / "t")
        limits = self.limits()
        self.assertRefused(
            "escaping-link",
            lambda: _owner().verify_tracked(self.repo, tree, root, limits=limits),
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
        self.assertRefused("tree-mismatch", lambda: owner._bind(destination, "a" * 40))
        self.assertEqual("another\n", record.read_text(encoding="ascii"))
        names = [p.name for p in self.root.iterdir() if ".exact-tree." in p.name]
        self.assertEqual([], names)


if __name__ == "__main__":
    unittest.main()
