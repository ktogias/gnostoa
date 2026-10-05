"""Small shared primitives of the toolkit's common module (#365)."""

from __future__ import annotations

import datetime
import os
import pathlib
import re
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from tools import knowledge_common


class UtcTimestampTests(unittest.TestCase):
    """One timestamp format for every command, instead of a copy in each (#365, I7)."""

    def test_the_timestamp_is_utc_to_the_second_with_a_z(self) -> None:
        before = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
        stamp = knowledge_common.utc_timestamp()
        after = datetime.datetime.now(datetime.UTC)
        self.assertRegex(stamp, r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
        moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        self.assertLessEqual(before, moment)
        self.assertLessEqual(moment, after)
        self.assertIsNone(re.search(r"\.\d", stamp))


class TrustedExecutableTests(unittest.TestCase):
    """A host tool is resolved from root-owned system directories only (#364)."""

    def test_the_directories_are_the_preparation_wrapper_s(self) -> None:
        """`ci/prepare-candidate` is shell and cannot import this; the two lists are
        held equal here instead of drifting apart."""
        wrapper = (
            pathlib.Path(__file__).resolve().parents[1] / "ci" / "prepare-candidate"
        ).read_text(encoding="utf-8")
        declared = re.search(r"^PATH=(\S+)$", wrapper, re.MULTILINE)
        if declared is None:
            self.fail("the preparation wrapper declares no trusted PATH")
        self.assertEqual(declared.group(1), knowledge_common.TRUSTED_EXECUTABLE_PATH)

    def test_the_caller_s_path_is_never_searched(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            tool = pathlib.Path(scratch) / "gh"
            tool.write_text("#!/bin/sh\n", encoding="utf-8")
            tool.chmod(0o755)
            pathlib.Path(scratch).chmod(0o755)
            with mock.patch.object(shutil, "which", return_value=str(tool)) as which:
                self.assertEqual(
                    str(tool.resolve()), knowledge_common.trusted_executable("gh")
                )
        which.assert_called_once_with(
            "gh", path=knowledge_common.TRUSTED_EXECUTABLE_PATH
        )


def _found(file_mode: int, dir_mode: int) -> str | None:
    """What the lookup trusts for a ``gh`` with these modes, in a fresh directory."""
    with tempfile.TemporaryDirectory() as scratch:
        directory = pathlib.Path(scratch) / "bin"
        directory.mkdir()
        tool = directory / "gh"
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        tool.chmod(file_mode)
        directory.chmod(dir_mode)
        try:
            with mock.patch.object(shutil, "which", return_value=str(tool)):
                return knowledge_common.trusted_executable("gh")
        finally:
            directory.chmod(0o755)


class TrustedExecutableWritersTests(unittest.TestCase):
    """A found executable is trusted only if no one but root or the caller can change
    it or its directory: `/opt/homebrew/bin` belongs to a user, not to root, and a
    symlink resolves to where the file really is (CodeAnt on #364)."""

    def test_an_executable_only_its_owner_can_change_is_trusted(self) -> None:
        self.assertIsNotNone(_found(0o755, 0o755))

    def test_an_executable_others_can_change_is_refused(self) -> None:
        for file_mode, dir_mode in (
            (0o775, 0o755),
            (0o757, 0o755),
            (0o755, 0o775),
            (0o755, 0o777),
        ):
            with self.subTest(file=oct(file_mode), directory=oct(dir_mode)):
                self.assertIsNone(_found(file_mode, dir_mode))

    def test_a_symlink_in_a_directory_others_can_change_is_refused(self) -> None:
        """Whoever can change the link's own directory chooses which binary runs, even
        when every binary it could point to is trusted (Codex on #364)."""
        with tempfile.TemporaryDirectory() as scratch:
            safe = pathlib.Path(scratch) / "safe"
            safe.mkdir()
            target = safe / "gh"
            target.write_text("#!/bin/sh\n", encoding="utf-8")
            target.chmod(0o755)
            links = pathlib.Path(scratch) / "links"
            links.mkdir()
            link = links / "gh"
            os.symlink(target, link)
            links.chmod(0o777)
            try:
                with mock.patch.object(shutil, "which", return_value=str(link)):
                    self.assertIsNone(knowledge_common.trusted_executable("gh"))
            finally:
                links.chmod(0o755)

    def test_a_symlink_is_judged_where_it_points(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            open_dir = pathlib.Path(scratch) / "open"
            open_dir.mkdir()
            target = open_dir / "gh"
            target.write_text("#!/bin/sh\n", encoding="utf-8")
            target.chmod(0o755)
            open_dir.chmod(0o777)
            link = pathlib.Path(scratch) / "gh"
            os.symlink(target, link)
            try:
                with mock.patch.object(shutil, "which", return_value=str(link)):
                    self.assertIsNone(knowledge_common.trusted_executable("gh"))
            finally:
                open_dir.chmod(0o755)


class TrustedPathTests(unittest.TestCase):
    """A given path, as a configured helper names one, is held to the same rule."""

    def test_a_path_is_judged_by_its_own_directory_and_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            target_dir = base / "real"
            link_dir = base / "links"
            target_dir.mkdir()
            link_dir.mkdir()
            target = target_dir / "tool"
            target.write_text("#!/bin/sh\n", encoding="utf-8")
            target.chmod(0o755)
            link = link_dir / "tool"
            link.symlink_to(target)
            self.assertEqual(
                str(target.resolve()), knowledge_common.trusted_path(str(link))
            )
            for changed in (link_dir, target_dir):
                with self.subTest(writable=changed.name):
                    changed.chmod(0o775)
                    self.assertIsNone(knowledge_common.trusted_path(str(link)))
                    changed.chmod(0o755)

    def test_every_link_in_a_chain_is_judged_by_its_own_directory(self) -> None:
        """A link in the middle of a chain can be repointed by whoever can change the
        directory it is in, though its first and last hops are safe (gitar on #364)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            for name in ("safe", "shared", "real"):
                (base / name).mkdir()
            target = base / "real" / "tool"
            target.write_text("#!/bin/sh\n", encoding="utf-8")
            target.chmod(0o755)
            (base / "shared" / "tool").symlink_to(target)
            (base / "safe" / "tool").symlink_to(base / "shared" / "tool")
            first = str(base / "safe" / "tool")
            self.assertEqual(
                str(target.resolve()), knowledge_common.trusted_path(first)
            )
            (base / "shared").chmod(0o775)
            self.assertIsNone(knowledge_common.trusted_path(first))
            (base / "shared").chmod(0o755)

    def test_a_link_loop_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            (base / "a").symlink_to(base / "b")
            (base / "b").symlink_to(base / "a")
            self.assertIsNone(knowledge_common.trusted_path(str(base / "a")))

    def test_every_directory_above_is_judged_too(self) -> None:
        """Whoever can change a directory above can replace the one below it whole
        (CodeAnt on #364). A sticky directory, as `/tmp` is, lets no one but an entry's
        owner replace it."""
        with tempfile.TemporaryDirectory() as scratch:
            above = pathlib.Path(scratch) / "above"
            below = above / "bin"
            below.mkdir(parents=True)
            tool = below / "tool"
            tool.write_text("#!/bin/sh\n", encoding="utf-8")
            tool.chmod(0o755)
            self.assertEqual(
                str(tool.resolve()), knowledge_common.trusted_path(str(tool))
            )
            above.chmod(0o775)
            self.assertIsNone(knowledge_common.trusted_path(str(tool)))
            above.chmod(0o1777)
            self.assertEqual(
                str(tool.resolve()), knowledge_common.trusted_path(str(tool))
            )
            above.chmod(0o755)

    def test_a_directory_link_is_judged_where_it_leads(self) -> None:
        """A path through a directory link is judged as it really is too: the link's
        own chain can be safe while the directory it leads into is not."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            real = base / "shared" / "real"
            real.mkdir(parents=True)
            (base / "safe").mkdir()
            (base / "safe" / "link").symlink_to(real)
            tool = real / "tool"
            tool.write_text("#!/bin/sh\n", encoding="utf-8")
            tool.chmod(0o755)
            through = str(base / "safe" / "link" / "tool")
            self.assertEqual(
                str(tool.resolve()), knowledge_common.trusted_path(through)
            )
            (base / "shared").chmod(0o775)
            self.assertIsNone(knowledge_common.trusted_path(through))
            (base / "shared").chmod(0o755)

    def test_a_directory_link_is_judged_by_its_own_owner(self) -> None:
        """In a sticky directory a link's owner can repoint it: a path through another
        user's directory link is not trusted, though where it leads is (Codex on #364).
        Another user's link stands as a caller other than the link's owner."""
        temporary = tempfile.gettempdir()
        held = os.stat(temporary)
        if held.st_uid != 0 or not held.st_mode & stat.S_ISVTX:
            self.skipTest("the temporary directory is not root's and sticky")
        shell = shutil.which("sh", path="/usr/bin:/bin")
        if shell is None:
            self.skipTest("no sh in the system directories")
        system = os.path.dirname(os.path.realpath(shell))
        link = pathlib.Path(temporary) / f"gnostoa-link-{os.getpid()}-{id(self)}"
        link.symlink_to(system)
        self.addCleanup(link.unlink)
        through = str(link / "sh")
        self.assertIsNotNone(knowledge_common.trusted_path(through))
        with mock.patch("os.getuid", return_value=4242):
            self.assertIsNone(knowledge_common.trusted_path(through))

    def test_a_relative_or_missing_path_is_not_trusted(self) -> None:
        self.assertIsNone(knowledge_common.trusted_path("gh"))
        self.assertIsNone(knowledge_common.trusted_path("/nonexistent/gnostoa/gh"))


if __name__ == "__main__":
    unittest.main()
