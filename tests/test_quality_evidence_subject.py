"""The diagnostic inventory's subject: its Git metadata, identity, freeze, recheck
and comparison binding (#389 F3 S2 B, Router 6326577610)."""

from __future__ import annotations

import errno
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from quality_evidence_fixtures import (
    _DiagnosticInventoryFixture,
)

from tools.quality_evidence import (
    QualityEvidenceError,
)


class DiagnosticSubjectTests(_DiagnosticInventoryFixture):
    """The subject the inventory binds, and the Git metadata it reads to bind it,
    with the producers faked at `_bounded_run`."""

    def test_a_root_without_its_own_git_is_not_bound_to_an_enclosing_checkout(
        self,
    ) -> None:
        # Codex on #436, by the Router's G-a (6234212478): a manifest-backed root with
        # no `.git` of its own, inside another checkout, recorded that checkout's HEAD
        # and compared against its history. It reads no Git: no revision, its state
        # unknown, the named gap, and no comparison; a requested revision is never an
        # observed one. A linked worktree's `.git` file is its own.
        self.mypy_records, self.ruff_records = {}, []
        nested = self._package(self.root / "pkg")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a package")
        standalone = self._package(Path(self.directory.name) / "standalone")
        unknown = "the tracked tree is dirty or its state is unknown"
        cases = (
            ("nested, a base", nested, {"base": self.base}),
            ("nested, no base", nested, {}),
            ("outside any repository, a base", standalone, {"base": self.base}),
            ("outside any repository, no base", standalone, {}),
        )
        for index, (label, root, options) in enumerate(cases):
            with self.subTest(label):
                inventory, state, comparison = self._collect_spied(
                    root, Path(self.directory.name) / f"out-{index}", **options
                )
                self.assertEqual([], state.call_args_list)
                self.assertEqual([], comparison.call_args_list)
                self.assertIsNone(inventory["source"]["revision"])
                self.assertIsNone(inventory["source"]["tracked_tree_dirty"])
                self.assertIsNone(inventory["scope"]["diff"])
                self.assertEqual(
                    ["tools/sample.py"], inventory["scope"]["full"]["expected"]
                )
                self.assertIn(unknown, inventory["coverage"]["reason"])
        with self.subTest("a requested revision is never observed"):
            with patch.dict(os.environ, {"KNOWLEDGE_KIT_REVISION": self.base}):
                inventory, state, _comparison = self._collect_spied(
                    nested,
                    Path(self.directory.name) / "out-expected",
                    expected_revision=self.base,
                )
            self.assertEqual([], state.call_args_list)
            self.assertIsNone(inventory["source"]["revision"])
            self.assertIn(
                f"revision None is not the expected {self.base}",
                inventory["coverage"]["reason"],
            )
        with self.subTest("a malformed base"):
            inventory, _state, comparison = self._collect_spied(
                nested, Path(self.directory.name) / "out-malformed", base="not-a-sha"
            )
            self.assertEqual([], comparison.call_args_list)
            self.assertIn(
                "base 'not-a-sha' is not a 40-hex commit id",
                inventory["coverage"]["reason"],
            )
        with self.subTest("a linked worktree"):
            worktree = Path(self.directory.name) / "linked"
            self._git("worktree", "add", "-q", "--detach", str(worktree), "HEAD")
            self.assertTrue((worktree / ".git").is_file())
            inventory, state, _comparison = self._collect_spied(
                worktree, Path(self.directory.name) / "out-linked"
            )
            self.assertEqual(1 + 1, state.call_count)
            self.assertEqual(
                self._git("rev-parse", "HEAD"), inventory["source"]["revision"]
            )

    def test_unsafe_git_metadata_refuses_the_inventory(self) -> None:
        # cubic and Claude on #436, by the Router's 6239259708: a packaged root whose
        # `.git` links to the enclosing checkout's metadata recorded that checkout's
        # HEAD. Unsafe metadata, a symlink, dangling or not, or another kind, is the
        # scope owner's UNSAFE_PATH: no Git is read, and no inventory is written.
        self.mypy_records, self.ruff_records = {}, []
        for label, make in (
            (
                "a symlink to the checkout",
                lambda entry: entry.symlink_to(self.root / ".git"),
            ),
            (
                "a dangling symlink",
                lambda entry: entry.symlink_to(self.root / "missing"),
            ),
            ("another kind", lambda entry: os.mkfifo(entry)),
        ):
            with self.subTest(label):
                package = self._package(self.root / label.replace(" ", "-"))
                make(package / ".git")
                shutil.rmtree(self.output, ignore_errors=True)
                reason, state, comparison = self._refused_spied(package, base=self.base)
                self.assertIn("UNSAFE_PATH", reason)
                self.assertNotIn(str(self.root), reason)
                self.assertEqual([], state.call_args_list)
                self.assertEqual([], comparison.call_args_list)
                self.assertEqual(
                    [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
                )

    def test_metadata_that_git_resolves_elsewhere_refuses_the_inventory(self) -> None:
        # cubic on #436, by the Router's I-b: metadata that Git resolves to the
        # enclosing checkout recorded that checkout's HEAD. The inventory is refused
        # as UNSAFE_PATH, with no Git subject read and no inventory written.
        self.mypy_records, self.ruff_records = {}, []
        # The owner's N-a (6241486091): a gitfile to the enclosing checkout's metadata,
        # or to another worktree's, bound that checkout's HEAD while Git's top level
        # still named the root.
        elsewhere = Path(tempfile.mkdtemp(dir=self.root.parent))
        self.addCleanup(shutil.rmtree, elsewhere, ignore_errors=True)
        self._git(
            "worktree", "add", "-q", "--detach", str(elsewhere / "linked"), "HEAD"
        )
        borrowed = self._git(
            "-C", str(elsewhere / "linked"), "rev-parse", "--absolute-git-dir"
        )

        def gitfile(target: str):
            return lambda entry: entry.write_text(
                f"gitdir: {target}\n", encoding="utf-8"
            )

        for label, make in (
            ("an empty directory", lambda entry: entry.mkdir()),
            ("a gitfile to the enclosing metadata", gitfile(str(self.root / ".git"))),
            ("a gitfile to another worktree's metadata", gitfile(borrowed)),
        ):
            with self.subTest(label):
                package = self._package(self.root / label.replace(" ", "-"))
                make(package / ".git")
                shutil.rmtree(self.output, ignore_errors=True)
                reason, state, comparison = self._refused_spied(package, base=self.base)
                self.assertIn("UNSAFE_PATH", reason)
                self.assertEqual([], state.call_args_list)
                self.assertEqual([], comparison.call_args_list)
                self.assertEqual(
                    [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
                )

    def test_the_subject_identity_check_holds_to_the_deadline(self) -> None:
        # The Router's I-b, and the two mutants that survived on bfcb906a: a spent
        # budget starts no identity check, so no Git at all, and an open one passes
        # the check what is left of it, never no bound.
        identity = Mock(return_value=True)
        with patch.object(self.module, "has_git_metadata", identity):
            source, _gaps = self.module._diagnostic_subject(
                self.root, None, time.monotonic() - 1
            )
        self.assertEqual([], identity.call_args_list)
        self.assertIsNone(source["tracked_tree_dirty"])
        identity = Mock(return_value=True)
        with patch.object(self.module, "has_git_metadata", identity):
            self.module._diagnostic_subject(self.root, None, time.monotonic() + 30)
        self.assertEqual(1, identity.call_count)
        timeout = identity.call_args.kwargs["timeout"]
        self.assertIsNotNone(timeout)
        self.assertLess(0, timeout)
        self.assertLessEqual(timeout, 30)

    def test_one_clock_reading_decides_each_readers_check_and_timeout(self) -> None:
        # Codex on #436, by the Router's I-b ("no fresh millisecond allowance"): the
        # check and the timeout came from two readings, and _time_left floored a
        # deadline spent in between to a millisecond, so Git started past it. One
        # reading decides both: a spent budget starts no Git, and an open one passes
        # exactly what that reading leaves, never the floor.
        def clock(*readings):
            values = iter(readings)
            return SimpleNamespace(
                monotonic=lambda: next(values, readings[-1]), sleep=time.sleep
            )

        identity, state = Mock(return_value=True), Mock()
        with (
            patch.object(self.module, "time", clock(101.0)),
            patch.object(self.module, "has_git_metadata", identity),
            patch.object(self.module, "_git_state", state),
        ):
            source, _gaps = self.module._diagnostic_subject(self.root, None, 100.5)
        self.assertEqual([], identity.call_args_list)
        self.assertEqual([], state.call_args_list)
        self.assertIsNone(source["tracked_tree_dirty"])
        identity, state = Mock(return_value=True), Mock()
        with (
            patch.object(self.module, "time", clock(100.0, 101.0)),
            patch.object(self.module, "has_git_metadata", identity),
            patch.object(self.module, "_git_state", state),
        ):
            self.module._diagnostic_subject(self.root, None, 100.5)
        self.assertEqual(0.5, identity.call_args.kwargs["timeout"])
        self.assertEqual([], state.call_args_list)
        enumeration = Mock(return_value=[])
        with (
            patch.object(self.module, "time", clock(101.0)),
            patch.object(self.module, "candidate_paths", enumeration),
        ):
            expected, gap = self.module._tracked_python(self.root, 100.5)
        self.assertEqual([], enumeration.call_args_list)
        self.assertIsNone(expected)
        self.assertIn("deadline", gap)
        with (
            patch.object(self.module, "time", clock(100.0, 101.0)),
            patch.object(self.module, "candidate_paths", enumeration),
        ):
            self.module._tracked_python(self.root, 100.5)
        self.assertEqual(0.5, enumeration.call_args.kwargs["timeout"])

    def test_an_unconfirmed_git_identity_reads_no_subject(self) -> None:
        # The Router's I-b on #436: an operational failure of the identity check is
        # never a confirmed identity, so no Git subject is read and the state is
        # unknown; a budget the check spends reads no subject either.
        from tools.repository_scope import RepositoryScopeError

        # Each such failure is its own named gap, by its category and never its text,
        # as every other scope error is (Amazon Q on #436).
        self.mypy_records, self.ruff_records = {}, []
        for category in ("GIT_TIMEOUT", "GIT_FAILED", "GIT_IO"):
            with self.subTest(category):
                shutil.rmtree(self.output, ignore_errors=True)
                failed = RepositoryScopeError("raw /host detail", category=category)
                with patch.object(self.module, "has_git_metadata", side_effect=failed):
                    inventory, state, _comparison = self._collect_spied(
                        self.root, self.output
                    )
                self.assertEqual([], state.call_args_list)
                self.assertIsNone(inventory["source"]["revision"])
                reason = inventory["coverage"]["reason"]
                self.assertIn(
                    "the tracked tree is dirty or its state is unknown", reason
                )
                self.assertIn(
                    f"cannot confirm the subject's Git identity (scope error: {category})",
                    reason,
                )
                self.assertNotIn("raw /host detail", json.dumps(inventory))

        def spending(root, *, timeout=None):
            time.sleep(0.4)
            return True

        shutil.rmtree(self.output, ignore_errors=True)
        limits = self.module.DiagnosticLimits(timeout_seconds=0.3)
        with patch.object(self.module, "has_git_metadata", side_effect=spending):
            inventory, state, _comparison = self._collect_spied(
                self.root, self.output, limits=limits
            )
        self.assertEqual([], state.call_args_list)
        self.assertIsNone(inventory["source"]["revision"])

    def test_an_identity_failure_keeps_its_category_through_the_recheck(self) -> None:
        # The Router's 6243847776 on #436: the identity check's own gap survives at the
        # final subject recheck too, rather than being discarded with its gaps. It is
        # never doubled, and an ordinary success names none.
        from tools.repository_scope import RepositoryScopeError

        self.mypy_records, self.ruff_records = {}, []
        failed = RepositoryScopeError("raw /host detail", category="GIT_FAILED")
        timed_out = RepositoryScopeError("raw /host detail", category="GIT_TIMEOUT")
        named = "cannot confirm the subject's Git identity (scope error: {})"
        reread = "the subject could not be re-read after collection"
        for label, effect, expected in (
            (
                "an initial failure, then success",
                [failed, True],
                {named.format("GIT_FAILED"): 1, reread: 0},
            ),
            (
                "a failure only at the recheck",
                [True, timed_out],
                {named.format("GIT_TIMEOUT"): 1, reread: 1},
            ),
            (
                "the same failure at both",
                [failed, failed],
                {named.format("GIT_FAILED"): 1, reread: 1},
            ),
            (
                "an ordinary success",
                [True, True],
                {"cannot confirm the subject's Git identity": 0, reread: 0},
            ),
        ):
            with self.subTest(label):
                shutil.rmtree(self.output, ignore_errors=True)
                with patch.object(self.module, "has_git_metadata", side_effect=effect):
                    inventory, _state, _comparison = self._collect_spied(
                        self.root, self.output
                    )
                reason = inventory["coverage"]["reason"]
                for text, count in expected.items():
                    self.assertEqual(count, reason.count(text), (text, reason))
                self.assertNotIn("raw /host detail", json.dumps(inventory))
                if effect[0] is True:
                    self.assertEqual(self.base, inventory["source"]["revision"])

    def test_unsafe_metadata_at_the_tracked_read_refuses_the_inventory(self) -> None:
        # Claude on #436, by the Router's C-a: the scope owner's UNSAFE_PATH or
        # GIT_METADATA_IO at the tracked-set read refuses the inventory, as at the
        # subject read, with no producer started; other scope errors stay soft gaps.
        from tools.repository_scope import RepositoryScopeError

        self.mypy_records, self.ruff_records = {}, []
        for category in ("UNSAFE_PATH", "GIT_METADATA_IO"):
            with self.subTest(category):
                shutil.rmtree(self.output, ignore_errors=True)
                self.commands = []
                refused = RepositoryScopeError("/host/private", category=category)
                with (
                    patch(
                        "tools.repository_scope.has_git_metadata", side_effect=refused
                    ),
                    patch(
                        "tools.quality_evidence._bounded_run",
                        side_effect=self._fake_run,
                    ),
                    self.assertRaises(QualityEvidenceError) as raised,
                ):
                    self.collect(self.root, self.output)
                self.assertIn(category, str(raised.exception))
                self.assertNotIn("/host/private", str(raised.exception))
                self.assertEqual(
                    [], [c for c, *_ in self.commands if "--version" not in c]
                )
                self.assertEqual(
                    [], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY))
                )
        for category in ("GIT_TIMEOUT", "MANIFEST_MISSING"):
            with self.subTest(category):
                shutil.rmtree(self.output, ignore_errors=True)
                soft = RepositoryScopeError("/host/private", category=category)
                with patch("tools.repository_scope.has_git_metadata", side_effect=soft):
                    inventory = self._inventory()
                self.assertIsNone(inventory["scope"]["full"]["expected"])
                self.assertIn(category, inventory["coverage"]["reason"])

    def test_an_uninspectable_git_entry_refuses_the_inventory(self) -> None:
        # The Router's 6239259708 tightens G-a: a `.git` that cannot be inspected is no
        # proof of absence, so it is the scope owner's GIT_METADATA_IO, never an
        # unknown subject: no Git is read, and no inventory is written.
        self.mypy_records, self.ruff_records = {}, []
        real_lstat = Path.lstat

        def failing(path, *args, **kwargs):
            if path.name == ".git" and path.parent == self.root:
                raise PermissionError(errno.EACCES, "denied")
            return real_lstat(path, *args, **kwargs)

        with patch.object(Path, "lstat", failing):
            reason, state, comparison = self._refused_spied(self.root, base=self.base)
        self.assertIn("GIT_METADATA_IO", reason)
        self.assertEqual([], state.call_args_list)
        self.assertEqual([], comparison.call_args_list)
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))

    def test_unsafe_git_metadata_at_the_final_read_refuses_the_inventory(self) -> None:
        # The Router's 6239259708 at the final subject read: metadata replaced by a
        # symlink there is refused too, with no second Git subject read. Both reads go
        # through _subject_state (the Router's 6243847776 on #436).
        real = self.module._subject_state
        calls: list[Path] = []

        def final_with_a_link(root, *args, **kwargs):
            calls.append(root)
            if len(calls) == 2:
                (root / ".git").rename(root / ".git-moved")
                (root / ".git").symlink_to(root / ".git-moved")
            return real(root, *args, **kwargs)

        with patch.object(self.module, "_subject_state", side_effect=final_with_a_link):
            reason, state, _comparison = self._refused_spied(self.root, base=self.base)
        self.assertEqual(2, len(calls))
        self.assertEqual(1, state.call_count)
        self.assertIn("UNSAFE_PATH", reason)
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))

    def test_a_dirty_subjects_base_is_checked_for_its_form_only(self) -> None:
        # Codex on #436, by the Router's B-a (6239259708): with nothing compared, a
        # base is checked for its form only, never verified as a commit, and no Git
        # comparison work starts; a malformed base keeps its gap.
        self._git("tag", "-a", "-m", "a tag", "base-tag", self.base)
        bases = {
            "tree": self._git("rev-parse", f"{self.base}^{{tree}}"),
            "blob": self._git("rev-parse", f"{self.base}:tools/sample.py"),
            "tag": self._git("rev-parse", "base-tag"),
            "missing object": "f" * 40,
        }
        clean = self.module._git_state(self.root)
        dirty = {"revision": self.base, "tracked_tree_dirty": True}
        for kind, base in bases.items():
            with self.subTest(kind):
                shutil.rmtree(self.output, ignore_errors=True)
                comparison = Mock(side_effect=self.module._diagnostic_git)
                with (
                    patch.object(self.module, "_git_state", side_effect=[dirty, clean]),
                    patch.object(self.module, "_diagnostic_git", comparison),
                ):
                    inventory = self._inventory(base=base)
                self.assertEqual([], comparison.call_args_list)
                self.assertIsNone(inventory["scope"]["diff"])
                reason = inventory["coverage"]["reason"]
                self.assertNotIn("commit", reason)
                self.assertIn(
                    "the tracked tree is dirty or its state is unknown", reason
                )
        with self.subTest("a malformed base"):
            shutil.rmtree(self.output, ignore_errors=True)
            with patch.object(self.module, "_git_state", side_effect=[dirty, clean]):
                inventory = self._inventory(base="not-a-sha")
            self.assertIn(
                "base 'not-a-sha' is not a 40-hex commit id",
                inventory["coverage"]["reason"],
            )

    def test_metadata_gone_at_the_final_read_leaves_the_comparison_unbound(
        self,
    ) -> None:
        # The Router's G-a at the final subject read: metadata gone there reads no Git,
        # and the existing unbound-subject handling nulls every in_diff. Both reads go
        # through _subject_state (the Router's 6243847776 on #436).
        real = self.module._subject_state
        calls: list[Path] = []

        def final_without_metadata(root, *args, **kwargs):
            calls.append(root)
            if len(calls) == 2:
                (root / ".git").rename(root / ".git-moved")
            return real(root, *args, **kwargs)

        with patch.object(
            self.module, "_subject_state", side_effect=final_without_metadata
        ):
            inventory, state, _comparison = self._collect_spied(
                self.root, self.output, base=self.base
            )
        self.assertEqual(2, len(calls))
        self.assertEqual(1, state.call_count)
        self.assertIn(
            "the subject could not be re-read after collection",
            inventory["coverage"]["reason"],
        )
        self.assertEqual(
            {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
        )

    def test_a_dirty_or_unknown_subject_is_never_compared(self) -> None:
        # The Router's D1 (6231894979): the producers read the working tree and the
        # comparison reads HEAD, so a definite in_diff for a dirty or unknown tree may
        # be wrong. It is not compared: no diff, every in_diff null, and the named gap.
        clean = self.module._git_state(self.root)
        cases = (
            ("dirty", {"revision": self.base, "tracked_tree_dirty": True}),
            ("unknown", {"revision": None, "tracked_tree_dirty": None}),
        )
        for label, first in cases:
            with self.subTest(label):
                spy = Mock(side_effect=self.module._diagnostic_git)
                with (
                    patch.object(self.module, "_git_state", side_effect=[first, clean]),
                    patch.object(self.module, "_diagnostic_git", spy),
                ):
                    inventory = self._inventory(base=self.base)
                self.assertEqual([], spy.call_args_list)
                self.assertIsNone(inventory["scope"]["diff"])
                self.assertEqual(
                    {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
                )
                self.assertIn(
                    "the tracked tree is dirty or its state is unknown",
                    inventory["coverage"]["reason"],
                )

    def test_an_unbound_subject_publishes_no_diff(self) -> None:
        # Codex on #436, by the Router's D1b (6240492499): a subject that changed,
        # turned dirty or could not be re-read after a clean comparison kept
        # scope.diff, whose changed_paths may describe another revision. It is null, as
        # for a subject that was dirty from the start, and the gap names why.
        self._changed_once()
        clean = self.module._git_state(self.root)
        cases = (
            (
                "HEAD changed",
                {"revision": "f" * 40, "tracked_tree_dirty": False},
                "the subject changed during collection",
            ),
            (
                "turned dirty",
                {**clean, "tracked_tree_dirty": True},
                "the subject changed during collection",
            ),
            (
                "could not be re-read",
                {"revision": None, "tracked_tree_dirty": None},
                "the subject could not be re-read after collection",
            ),
        )
        for label, after, gap in cases:
            with self.subTest(label):
                shutil.rmtree(self.output, ignore_errors=True)
                with patch.object(
                    self.module, "_git_state", side_effect=[clean, after]
                ):
                    inventory = self._inventory(base=self.base)
                self.assertIsNone(inventory["scope"]["diff"])
                self.assertEqual(
                    {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
                )
                self.assertIn(gap, inventory["coverage"]["reason"])
        with self.subTest("a stable clean subject keeps its diff"):
            shutil.rmtree(self.output, ignore_errors=True)
            with patch.object(self.module, "_git_state", side_effect=[clean, clean]):
                inventory = self._inventory(base=self.base)
            self.assertEqual(self.base, inventory["scope"]["diff"]["base"])
        with self.subTest("no base, no diff"):
            shutil.rmtree(self.output, ignore_errors=True)
            self.assertIsNone(self._inventory()["scope"]["diff"])

    def test_a_subject_that_changed_or_cannot_be_re_read_has_no_in_diff(self) -> None:
        # The Router's D1: when the final read differs, or cannot finish, the definite
        # answers are cleared to null, and the subject gap stays.
        clean = self.module._git_state(self.root)
        cases = (
            (
                "changed",
                {"revision": "f" * 40, "tracked_tree_dirty": False},
                "the subject changed during collection",
            ),
            (
                "unreadable",
                {"revision": None, "tracked_tree_dirty": None},
                "the subject could not be re-read after collection",
            ),
        )
        for label, after, gap in cases:
            with self.subTest(label):
                with patch.object(
                    self.module, "_git_state", side_effect=[clean, after]
                ):
                    inventory = self._inventory(base=self.base)
                self.assertTrue(inventory["findings"])
                self.assertEqual(
                    {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
                )
                self.assertIn(gap, inventory["coverage"]["reason"])
