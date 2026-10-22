"""The diagnostic inventory's subject: its Git metadata, identity, freeze, recheck
and comparison binding (#389 F3 S2 B, Router 6326577610)."""

from __future__ import annotations

import errno
import importlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from quality_evidence_fixtures import (
    _DIAGNOSTIC_SAMPLE,
    _EXTRA_COMPLEX,
    _DiagnosticInventoryFixture,
)


class DiagnosticSubjectTests(_DiagnosticInventoryFixture):
    """The subject the inventory binds, and the Git metadata it reads to bind it,
    with the producers faked at `_bounded_run`."""

    def test_a_root_without_its_own_git_is_not_bound_to_an_enclosing_checkout(
        self,
    ) -> None:
        # Codex on #436, by the Router's G-a (6234212478): a manifest-backed root with
        # no `.git` of its own, inside another checkout, recorded that checkout's HEAD
        # and compared against its history. It reads no Git: no revision, no tree, the
        # named gap, and no comparison; a requested revision is never an observed one.
        # In v2 nothing is frozen for it, so its set stays unknown and nothing is
        # analyzed: never the checkout or its manifest (Router #389 6325382720, D3,
        # D4). A linked worktree's `.git` file is its own.
        self.mypy_records, self.ruff_records = {}, []
        nested = self._package(self.root / "pkg")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a package")
        standalone = self._package(Path(self.directory.name) / "standalone")
        unfrozen = "the subject has no Git metadata of its own: no commit was frozen"
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
                self.assertIsNone(inventory["source"]["tree"])
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                self.assertIsNone(inventory["scope"]["diff"])
                self.assertIsNone(inventory["scope"]["full"]["expected"])
                self.assertEqual([], inventory["producers"])
                self.assertIn(unfrozen, inventory["coverage"]["reason"])
                self.assertNotIn(
                    "could not be re-read", inventory["coverage"]["reason"]
                )
        with self.subTest("a requested revision is never observed"):
            with patch.dict(os.environ, {"KNOWLEDGE_KIT_REVISION": self.base}):
                inventory, state, comparison = self._collect_spied(
                    nested,
                    Path(self.directory.name) / "out-expected",
                    expected_revision=self.base,
                )
            self.assertEqual([], state.call_args_list)
            self.assertEqual([], comparison.call_args_list)
            self.assertIsNone(inventory["source"]["revision"])
            self.assertEqual(self.base, inventory["source"]["expected_revision"])
            self.assertIn(unfrozen, inventory["coverage"]["reason"])
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
            self.assertEqual(0, state.call_count)
            self.assertEqual(
                self._git("rev-parse", "HEAD"), inventory["source"]["revision"]
            )
            self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])

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

    def test_unsafe_metadata_at_the_freeze_alone_refuses_before_any_work(self) -> None:
        # Mutant F7 on S2 B (#389 6326768433): the recheck after collection refuses
        # unsafe metadata too, so the freeze's own refusal is observable only when the
        # metadata is unsafe there alone. It refuses at once: no listing, no stage, no
        # producer and no inventory (Router #389 6325382720, D3).
        from tools.repository_scope import RepositoryScopeError

        owner = importlib.import_module("tools.exact_tree")
        unsafe = RepositoryScopeError("raw /host detail", category="UNSAFE_PATH")
        listing = Mock(side_effect=owner.tree_paths)
        with (
            patch.object(self.module, "has_git_metadata", side_effect=[unsafe, True]),
            patch.object(owner, "tree_paths", listing),
        ):
            reason, state, comparison = self._refused_spied(self.root)
        self.assertIn("UNSAFE_PATH", reason)
        self.assertNotIn("raw /host detail", reason)
        self.assertEqual([], listing.call_args_list)
        self.assertEqual([], comparison.call_args_list)
        self.assertEqual([], state.call_args_list)
        self.assertEqual([], [c for c, *_ in self.commands if "--version" not in c])
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))

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
            commit, _tree, _gaps = self.module._frozen_subject(
                self.root, None, time.monotonic() - 1
            )
        self.assertEqual([], identity.call_args_list)
        self.assertIsNone(commit)
        identity = Mock(return_value=True)
        gaps: list[str] = []
        with patch.object(self.module, "has_git_metadata", identity):
            rebound = self.module._metadata_rebound(
                self.root, time.monotonic() - 1, gaps
            )
        self.assertEqual([], identity.call_args_list)
        self.assertFalse(rebound)
        self.assertEqual(["the subject could not be re-read after collection"], gaps)
        identity = Mock(return_value=True)
        with patch.object(self.module, "has_git_metadata", identity):
            self.module._frozen_subject(self.root, None, time.monotonic() + 30)
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
        # exactly what that reading leaves, never the floor. The frozen tree's owner
        # takes the absolute deadline itself, never a converted timeout (#389 F3 S2 B).
        def clock(*readings):
            values = iter(readings)
            return SimpleNamespace(
                monotonic=lambda: next(values, readings[-1]), sleep=time.sleep
            )

        identity, reader = Mock(return_value=True), Mock()
        with (
            patch.object(self.module, "time", clock(101.0)),
            patch.object(self.module, "has_git_metadata", identity),
            patch.object(self.module, "_diagnostic_git", reader),
        ):
            commit, _tree, _gaps = self.module._frozen_subject(self.root, None, 100.5)
        self.assertEqual([], identity.call_args_list)
        self.assertEqual([], reader.call_args_list)
        self.assertIsNone(commit)
        identity = Mock(return_value=True)
        reader = Mock(side_effect=OSError("spent"))
        with (
            patch.object(self.module, "time", clock(100.0, 101.0)),
            patch.object(self.module, "has_git_metadata", identity),
            patch.object(self.module, "_diagnostic_git", reader),
        ):
            self.module._frozen_subject(self.root, None, 100.5)
        self.assertEqual(0.5, identity.call_args.kwargs["timeout"])
        owner = importlib.import_module("tools.exact_tree")
        bounds = owner.Limits(100.5, 10, 10)
        enumeration = Mock(return_value=frozenset({"tools/sample.py", "a.txt"}))
        with patch.object(owner, "tree_paths", enumeration):
            expected = self.module._tracked_python(self.root, "t" * 40, bounds)
        self.assertIs(bounds, enumeration.call_args.kwargs["limits"])
        self.assertEqual(["tools/sample.py"], expected)

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
                self.assertEqual([], _comparison.call_args_list)
                self.assertIsNone(inventory["source"]["revision"])
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                reason = inventory["coverage"]["reason"]
                self.assertEqual(
                    1,
                    reason.count(
                        f"cannot confirm the subject's Git identity (scope error: {category})"
                    ),
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
                # Nothing reads the root's Git after a failed freeze, so it is not
                # checked again (cubic and Octopus on #451).
                "a failure at the freeze",
                [failed],
                {named.format("GIT_FAILED"): 1, reread: 0},
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

    def test_the_tracked_set_is_the_frozen_trees_listing(self) -> None:
        # Claude on #436, by the Router's C-a, in v2: the tracked set is the frozen
        # tree's object listing, never the scope owner's index listing, so that read's
        # metadata seam is gone. Unsafe metadata stays refused at the freeze and at the
        # recheck after collection (test_unsafe_git_metadata_refuses_the_inventory,
        # test_unsafe_git_metadata_at_the_final_read_refuses_the_inventory).
        owner = importlib.import_module("tools.exact_tree")
        listing = Mock(side_effect=owner.tree_paths)
        with (
            patch.object(
                self.module,
                "candidate_paths",
                side_effect=AssertionError("the index's listing"),
            ),
            patch.object(owner, "tree_paths", listing),
        ):
            inventory = self._inventory()
        self.assertEqual(1, listing.call_count)
        self.assertEqual(
            self._git("rev-parse", "HEAD^{tree}"), listing.call_args.args[1]
        )
        self.assertEqual(
            sorted(p for p in self.files if p.endswith(".py")),
            inventory["scope"]["full"]["expected"],
        )

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
        # symlink there is refused too. Both reads are the scope owner's identity
        # check; no git status runs at either (Router #389 6325382720, D1, D3: the
        # existing hard refusals remain).
        real = self.module.has_git_metadata
        calls: list[Path] = []

        def final_with_a_link(root, *args, **kwargs):
            calls.append(root)
            if len(calls) == 2:
                (root / ".git").rename(root / ".git-moved")
                (root / ".git").symlink_to(root / ".git-moved")
            return real(root, *args, **kwargs)

        with patch.object(
            self.module, "has_git_metadata", side_effect=final_with_a_link
        ):
            reason, state, _comparison = self._refused_spied(self.root, base=self.base)
        self.assertEqual(2, len(calls))
        self.assertEqual(0, state.call_count)
        self.assertIn("UNSAFE_PATH", reason)
        self.assertEqual([], list(self.output.rglob(self.module.DIAGNOSTIC_INVENTORY)))

    def test_an_unfrozen_subjects_base_is_checked_for_its_form_only(self) -> None:
        # Codex on #436, by the Router's B-a (6239259708), in v2: with nothing
        # compared, because no commit was frozen, a base is checked for its form only,
        # never verified as a commit, and no Git comparison work starts; a malformed
        # base keeps its gap.
        from tools.repository_scope import RepositoryScopeError

        self._git("tag", "-a", "-m", "a tag", "base-tag", self.base)
        bases = {
            "tree": self._git("rev-parse", f"{self.base}^{{tree}}"),
            "blob": self._git("rev-parse", f"{self.base}:tools/sample.py"),
            "tag": self._git("rev-parse", "base-tag"),
            "missing object": "f" * 40,
        }
        unknown = RepositoryScopeError("raw detail", category="GIT_FAILED")
        for kind, base in bases.items():
            with self.subTest(kind):
                shutil.rmtree(self.output, ignore_errors=True)
                comparison = Mock(side_effect=self.module._diagnostic_git)
                with (
                    patch.object(
                        self.module, "has_git_metadata", side_effect=[unknown, True]
                    ),
                    patch.object(self.module, "_diagnostic_git", comparison),
                ):
                    inventory = self._inventory(base=base)
                self.assertEqual([], comparison.call_args_list)
                self.assertIsNone(inventory["scope"]["diff"])
                reason = inventory["coverage"]["reason"]
                self.assertNotIn("is not a commit", reason)
                self.assertIn("no commit was frozen to compare", reason)
        with self.subTest("a malformed base"):
            shutil.rmtree(self.output, ignore_errors=True)
            with patch.object(
                self.module, "has_git_metadata", side_effect=[unknown, True]
            ):
                inventory = self._inventory(base="not-a-sha")
            self.assertIn(
                "base 'not-a-sha' is not a 40-hex commit id",
                inventory["coverage"]["reason"],
            )

    def test_metadata_gone_at_the_final_read_leaves_the_comparison_unbound(
        self,
    ) -> None:
        # The Router's G-a at the final subject read: metadata gone there leaves the
        # comparison, which read it, unbound: no diff and every in_diff null. The
        # staged tree's own binding is unaffected (Router #389 6325382720).
        real = self.module.has_git_metadata
        calls: list[Path] = []

        def final_without_metadata(root, *args, **kwargs):
            calls.append(root)
            if len(calls) == 2:
                (root / ".git").rename(root / ".git-moved")
            return real(root, *args, **kwargs)

        with patch.object(
            self.module, "has_git_metadata", side_effect=final_without_metadata
        ):
            inventory, state, _comparison = self._collect_spied(
                self.root, self.output, base=self.base
            )
        self.assertEqual(2, len(calls))
        self.assertEqual(0, state.call_count)
        self.assertIn(
            "the subject could not be re-read after collection",
            inventory["coverage"]["reason"],
        )
        self.assertIsNone(inventory["scope"]["diff"])
        self.assertTrue(inventory["findings"])
        self.assertEqual(
            {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
        )
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])

    # The Router's G451-R6 (6335930651 on #389): a final staged observation that is
    # only unavailable, with the metadata still confirmed, keeps the frozen-object
    # comparison but no finding's attribution, positive or negative: no finding was
    # observed on verified bytes. The observation fails by an unavailable identity,
    # leaving the comparison its time, never by an expired deadline.
    def test_an_unobserved_staged_source_keeps_the_comparison_not_attribution(
        self,
    ) -> None:
        sample = self.root / "tools" / "sample.py"
        sample.write_text(
            sample.read_text(encoding="utf-8") + _EXTRA_COMPLEX, encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "an extra complex function")
        bound = self._inventory(base=self.base)
        self.assertEqual(
            {True, False}, {f["native"]["in_diff"] for f in bound["findings"]}
        )
        for run in self.output.glob("diagnostic-*"):
            shutil.rmtree(run)
        owner = importlib.import_module("tools.exact_tree")
        unavailable = self._then(
            owner.observed_tree, owner.ExactTreeError("identity-unavailable")
        )
        with patch.object(owner, "observed_tree", side_effect=unavailable):
            inventory = self._inventory(base=self.base)
        self.assertIsNotNone(inventory["scope"]["diff"])
        self.assertEqual(
            bound["scope"]["diff"]["changed_paths"],
            inventory["scope"]["diff"]["changed_paths"],
        )
        self.assertEqual(len(bound["findings"]), len(inventory["findings"]))
        self.assertEqual(
            {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
        )
        reason = inventory["coverage"]["reason"]
        self.assertIn("finding-to-diff attribution is unknown", reason)
        self.assertIn("the staged source could not be observed again", reason)
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
        self.assertIsNone(inventory["source"]["staged_identity"])
        self.assertNotEqual("COMPLETE", inventory["coverage"]["status"])

    def test_an_unfrozen_subject_is_never_compared(self) -> None:
        # The Router's D1 (6231894979), in v2 (Router #389 6325382720, D4): a subject
        # whose commit was not frozen is not compared: no comparison read, no diff, and
        # the named gap. A dirty checkout is no longer such a subject: the frozen
        # commit is analyzed and compared, and no dirty state is read.
        from tools.repository_scope import RepositoryScopeError

        unknown = RepositoryScopeError("raw detail", category="GIT_FAILED")
        spy = Mock(side_effect=self.module._diagnostic_git)
        with (
            patch.object(self.module, "has_git_metadata", side_effect=[unknown, True]),
            patch.object(self.module, "_diagnostic_git", spy),
        ):
            inventory = self._inventory(base=self.base)
        self.assertEqual([], spy.call_args_list)
        self.assertIsNone(inventory["scope"]["diff"])
        self.assertEqual([], inventory["findings"])
        self.assertIn(
            f"cannot compare with base {self.base}: no commit was frozen to compare",
            inventory["coverage"]["reason"],
        )
        with self.subTest("a dirty checkout is compared as its frozen commit"):
            shutil.rmtree(self.output, ignore_errors=True)
            self._changed_once()
            (self.root / "tools" / "sample.py").write_text(
                _DIAGNOSTIC_SAMPLE + "\n# dirty\n", encoding="utf-8"
            )
            inventory = self._inventory(base=self.base)
            self.assertEqual(
                ["tools/sample.py"], inventory["scope"]["diff"]["changed_paths"]
            )
            self.assertNotIn(
                None, {f["native"]["in_diff"] for f in inventory["findings"]}
            )
            self.assertNotIn("dirty", inventory["coverage"]["reason"])

    def test_an_unbound_subject_publishes_no_diff(self) -> None:
        # Codex on #436, by the Router's D1b (6240492499), in v2: a comparison whose
        # metadata could not be confirmed again after collection keeps no scope.diff,
        # and the gap names why. A later HEAD is no longer a changed subject: the
        # comparison is the frozen commit's (Router #389 6325382720, D4; held by
        # ExactSourceTreeTests.test_the_diff_is_the_frozen_commits_not_a_later_heads).
        from tools.repository_scope import RepositoryScopeError

        self._changed_once()
        reread = "the subject could not be re-read after collection"
        cases = (
            ("metadata gone", [True, False]),
            (
                "unconfirmed",
                [True, RepositoryScopeError("raw detail", category="GIT_FAILED")],
            ),
        )
        for label, effect in cases:
            with self.subTest(label):
                shutil.rmtree(self.output, ignore_errors=True)
                with patch.object(self.module, "has_git_metadata", side_effect=effect):
                    inventory = self._inventory(base=self.base)
                self.assertIsNone(inventory["scope"]["diff"])
                self.assertTrue(inventory["findings"])
                self.assertEqual(
                    {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
                )
                self.assertIn(reread, inventory["coverage"]["reason"])
        with self.subTest("a stable subject keeps its diff"):
            shutil.rmtree(self.output, ignore_errors=True)
            inventory = self._inventory(base=self.base)
            self.assertEqual(self.base, inventory["scope"]["diff"]["base"])
        with self.subTest("no base, no diff"):
            shutil.rmtree(self.output, ignore_errors=True)
            self.assertIsNone(self._inventory()["scope"]["diff"])
