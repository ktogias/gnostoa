"""The diagnostic inventory's subject: its Git metadata, identity, freeze, recheck
and comparison binding (#389 F3 S2 B, Router 6326577610)."""

from __future__ import annotations

import ast
import base64
import csv
import dataclasses
import errno
import hashlib
import importlib
import json
import os
import shutil
import string
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from quality_evidence_fixtures import (
    _DIAGNOSTIC_SAMPLE,
    _EXTRA_COMPLEX,
    _SOURCE_BINDING_GAP,
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

    # The Router's G451-R9 (6339588153 on #389): the residual agrees with the
    # published staged-tree binding. A NOT_STAGED record, after no freeze, a failed
    # stage or an unavailable final observation, never says that the bytes were
    # observed before and after the producers; an EXACT_TREE_STAGED one keeps the
    # whole residual.
    def test_the_residual_agrees_with_the_published_binding(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        unconfined = (
            "source binding UNVERIFIED: the producers' installed environment and "
            "import graph is not proven confined to the staged tracked inputs"
        )
        unavailable = owner.ExactTreeError("identity-unavailable")
        cases = {
            "no freeze": patch.object(
                self.module, "has_git_metadata", return_value=False
            ),
            "a failed stage": patch.object(
                owner, "observed_tree", side_effect=unavailable
            ),
            "an unavailable final observation": patch.object(
                owner,
                "observed_tree",
                side_effect=self._then(owner.observed_tree, unavailable),
            ),
        }
        for label, failing in cases.items():
            with self.subTest(label):
                with failing:
                    inventory = self._inventory()
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                self.assertEqual("UNVERIFIED", inventory["source"]["source_binding"])
                reason = inventory["coverage"]["reason"]
                self.assertIn(unconfined, reason)
                self.assertNotIn("observed before and after the producers", reason)
                for run in self.output.glob("diagnostic-*"):
                    shutil.rmtree(run)
        inventory = self._inventory()
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])
        self.assertIn(_SOURCE_BINDING_GAP, inventory["coverage"]["reason"])

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


class ProducerEnvironmentTests(_DiagnosticInventoryFixture):
    """The producers' installed environment, an input outside the staged tree: the
    same tree under two installed sets gave mypy two findings with every recorded
    field identical (#389 F3 S2-C, the C6 probe in 6347549109). The producers stay
    faked at `_bounded_run`; anything they launch besides a version read, mypy and
    Ruff is the environment's isolated identity read, answered by `installed`."""

    def _environment(self, *installed: tuple[str, ...]):
        """A launcher whose identity reads answer `installed[0]`, then `installed[1]`
        and so on, keeping the last one; None answers as an unreadable read."""
        answers = list(installed)

        def run(command, *, cwd, environment, report, deadline, limits):
            if "--version" in command or "mypy" in command or "ruff" in command:
                return self._fake_run(
                    command,
                    cwd=cwd,
                    environment=environment,
                    report=report,
                    deadline=deadline,
                    limits=limits,
                )
            if command != self._observation_command():
                raise AssertionError(f"unexpected launch: {command}")
            answer = answers.pop(0) if len(answers) > 1 else answers[0]
            if answer is None:
                return 1, "exited 1", False
            report.write_text(self._observation(tuple(answer)), encoding="utf-8")
            return 0, None, False

        return run

    def _run(self, launcher, code: str) -> dict:
        self.mypy_records = {
            "tests/test_sample.py": [
                self._mypy(
                    "tests/test_sample.py",
                    self.lines["typing"],
                    1,
                    code,
                    f"{code}: probe_dep as this environment resolves it",
                )
            ]
        }
        shutil.rmtree(self.output, ignore_errors=True)
        with patch("tools.quality_evidence._bounded_run", side_effect=launcher):
            path = self.collect(self.root, self.output)
        self.run_directory = Path(path).parent
        return self._read(path)

    @staticmethod
    def _producers(inventory: dict) -> list[dict]:
        # A report's digest follows its bytes, which the findings already compare.
        return [
            {key: value for key, value in record.items() if key != "report"}
            for record in inventory["producers"]
        ]

    @staticmethod
    def _rules(inventory: dict) -> list[str]:
        return sorted(
            f["rule"] for f in inventory["findings"] if f["tool"]["id"] == "mypy"
        )

    def test_an_unchanged_environment_records_the_same_producers_twice(self) -> None:
        first = self._run(self._environment(("types-PyYAML 6.0",)), "import-untyped")
        second = self._run(self._environment(("types-PyYAML 6.0",)), "import-untyped")
        self.assertEqual(self._producers(first), self._producers(second))
        self.assertEqual(self._rules(first), self._rules(second))
        self.assertEqual("UNVERIFIED", second["source"]["source_binding"])

    def test_a_changed_installed_environment_is_visible_in_the_producer_records(
        self,
    ) -> None:
        absent = self._run(self._environment(()), "import-not-found")
        present = self._run(self._environment(("probe-dep 1.0",)), "import-untyped")
        self.assertNotEqual(self._rules(absent), self._rules(present))
        self.assertEqual(absent["source"]["tree"], present["source"]["tree"])
        self.assertNotEqual(
            self._producers(absent),
            self._producers(present),
            "the installed environment changed mypy's finding on the same tree, "
            "yet every producer record is identical",
        )
        self.assertEqual("UNVERIFIED", present["source"]["source_binding"])

    def test_an_environment_changed_during_the_producers_is_a_gap(self) -> None:
        inventory = self._run(
            self._environment((), ("probe-dep 1.0",)), "import-not-found"
        )
        self.assertRegex(
            inventory["coverage"]["reason"] or "",
            r"producer environment changed",
        )
        self.assertEqual("UNVERIFIED", inventory["source"]["source_binding"])

    def test_an_unreadable_environment_identity_is_a_gap(self) -> None:
        inventory = self._run(self._environment(None), "import-not-found")
        self.assertRegex(
            inventory["coverage"]["reason"] or "",
            r"producer environment identity unavailable",
        )
        self.assertEqual("UNVERIFIED", inventory["source"]["source_binding"])

    def test_the_observation_member_names_its_format_scope_and_status(self) -> None:
        # The optional v2 member (Router 6347672936): its own format, endpoint scope,
        # recorded caps, interpreter and both observations' evidence. A v2 record
        # without it was not observed.
        inventory = self._run(self._environment(("fixture-1.0",)), "import-untyped")
        runs = {r["invocation"]: r for r in inventory["producers"]}
        self.assertNotIn("environment_observation", runs["complexity"])
        member = runs["mypy:main"]["environment_observation"]
        self.assertEqual(member, runs["ruff:every-rule"]["environment_observation"])
        self.assertEqual(self.module.ENVIRONMENT_OBSERVATION_FORMAT, member["format"])
        self.assertEqual(self.module.ENVIRONMENT_OBSERVATION_SCOPE, member["scope"])
        self.assertEqual(self.module.ENVIRONMENT_OBSERVATION_CAPS, member["caps"])
        self.assertEqual("endpoints_equal", member["status"])
        self.assertEqual("/fixture/python", member["interpreter"]["executable"])
        for when in ("before", "after"):
            path = self.run_directory / member[when]["path"]
            self.assertEqual(
                self.module.file_evidence(path)["sha256"], member[when]["sha256"]
            )

    def test_equal_endpoints_never_certify_an_unchanged_run(self) -> None:
        # A -> B -> A: the dependency appears while mypy runs and is gone again before
        # the last observation (PAO 6347682576; cubic on #452). The endpoints compare
        # equal, which is all the member states, although mypy's finding is B's.
        installed: dict[str, tuple[str, ...]] = {"now": ()}

        def run(command, *, cwd, environment, report, deadline, limits):
            if command == self._observation_command():
                report.write_text(self._observation(installed["now"]), encoding="utf-8")
                return 0, None, False
            if "--version" not in command and "mypy" in command:
                installed["now"] = ("probe-dep-1.0",)
            elif "--version" not in command and "ruff" in command:
                installed["now"] = ()
            return self._fake_run(
                command,
                cwd=cwd,
                environment=environment,
                report=report,
                deadline=deadline,
                limits=limits,
            )

        inventory = self._run(run, "import-untyped")
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("endpoints_equal", member["status"])
        a = hashlib.sha256(self._observation(()).encode("utf-8")).hexdigest()
        self.assertEqual(
            [a, a], [member["before"]["sha256"], member["after"]["sha256"]]
        )
        self.assertEqual(["import-untyped"], self._rules(inventory))
        self.assertIn(
            "neither continuous nor complete installed content", member["scope"]
        )
        self.assertEqual("UNVERIFIED", inventory["source"]["source_binding"])
        self.assertNotEqual("COMPLETE", inventory["coverage"]["status"])

    def test_the_observations_bracket_every_launch_of_the_producers(self) -> None:
        # The first observation precedes the version reads, and the last follows the
        # producers, so the endpoints enclose every producer launch (Sourcery on #452).
        launches: list[str] = []

        def run(command, *, cwd, environment, report, deadline, limits):
            if command == self._observation_command():
                launches.append("observation")
            else:
                launches.append("version" if "--version" in command else command[3])
            return self._fake_run(
                command,
                cwd=cwd,
                environment=environment,
                report=report,
                deadline=deadline,
                limits=limits,
            )

        self._run(run, "import-untyped")
        self.assertEqual(["observation", "version", "version"], launches[:3])
        self.assertEqual("observation", launches[-1])
        self.assertEqual(2, launches.count("observation"))
        self.assertEqual({"mypy", "ruff"}, set(launches[3:-1]))

    def _observe_with(self, *roots: Path, caps: dict | None = None) -> dict:
        """The collector's own observer module, run for real through its bounded
        launcher with exactly `roots` as its import path, so that the result does not
        depend on the image running the tests (Claude on #452). Without `caps`, it runs
        with the composed command's own caps and format."""
        command = self.module._environment_command()
        if caps is not None:
            command = [*command[:3], json.dumps(caps, sort_keys=True), command[4]]
        source = Path(command[2]).read_text(encoding="utf-8")
        # The script's own imports are loaded first, so that only its import path, not
        # the standard library, is replaced.
        prefix = (
            "import base64, codecs, collections.abc, csv, hashlib, json, os\n"
            "import pathlib, stat, sys\n"
            f"sys.path[:] = {[str(r) for r in roots]!r}\n"
        )
        report = self.output / f"observation-{len(list(self.output.glob('*')))}.json"
        self.output.mkdir(parents=True, exist_ok=True)
        status, gap, invalid = self.module._bounded_run(
            [*command[:2], "-c", prefix + source, *command[3:]],
            cwd=self.root,
            environment=dict(os.environ),
            report=report,
            deadline=time.monotonic() + 60,
            limits=self.module.DEFAULT_DIAGNOSTIC_LIMITS,
        )
        self.assertEqual((0, None, False), (status, gap, invalid))
        self.observed_bytes = len(report.read_bytes())
        return json.loads(report.read_text(encoding="utf-8"))

    def _observed_root(self, name: str) -> Path:
        """A root of two modules and one distribution whose RECORD is 64 bytes: valid
        rows, all without a hash, so outside the RECORD check."""
        root = Path(self.directory.name) / name
        (root / "one-1.0.dist-info").mkdir(parents=True)
        record = "one-1.0.dist-info/RECORD,,\n" + "a.py,,\n" * 5 + "\n\n"
        (root / "one-1.0.dist-info" / "RECORD").write_text(record, encoding="utf-8")
        for module in ("a.py", "b.py"):
            (root / module).write_text("", encoding="utf-8")
        return root

    def test_an_unreadable_record_or_an_archive_on_the_path_is_observed(self) -> None:
        # A RECORD that cannot be read is no identity, and an archive on the import
        # path is observed by its bytes, within the file caps (Sourcery and cubic on
        # #452).
        site = Path(self.directory.name) / "site"
        (site / "broken-1.0.dist-info").mkdir(parents=True)
        archive = Path(self.directory.name) / "dependency.zip"
        archive.write_bytes(b"PK\x05\x06" + bytes(18))
        with self.subTest("an unreadable RECORD"):
            self.assertEqual("unreadable", self._observe_with(site)["incomplete"])
        with self.subTest("an archive"):
            observed = self._observe_with(archive)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual([str(archive), digest], observed["archives"][0])
        with self.subTest("an archive over its cap"):
            caps = {**self.module.ENVIRONMENT_OBSERVATION_CAPS, "file_bytes": 4}
            observed = self._observe_with(archive, caps=caps)
            self.assertEqual("file_bytes", observed["incomplete"])

    def test_a_capped_or_cut_observation_is_a_gap_never_an_identity(self) -> None:
        capped = self._observation(("fixture-1.0",), incomplete="entries")
        for name, answer in (("capped", capped), ("cut", None)):
            with self.subTest(name):

                def run(
                    command,
                    *,
                    cwd,
                    environment,
                    report,
                    deadline,
                    limits,
                    answer=answer,
                ):
                    if command != self._observation_command():
                        return self._fake_run(
                            command,
                            cwd=cwd,
                            environment=environment,
                            report=report,
                            deadline=deadline,
                            limits=limits,
                        )
                    report.write_text(answer or self._observation(), encoding="utf-8")
                    return 0, None, answer is None

                inventory = self._run(run, "import-untyped")
                member = inventory["producers"][0]["environment_observation"]
                self.assertEqual("unavailable", member["status"])
                self.assertIsNone(member["before"])
                self.assertIn(
                    "producer environment identity unavailable",
                    inventory["coverage"]["reason"],
                )

    def test_the_observations_share_the_inventory_deadline(self) -> None:
        # One original absolute deadline, never a fresh budget: a spent one starts no
        # later observation, which is then a gap (Router 6347672936).
        deadlines: list[tuple[str, float]] = []
        observations = 0

        def run(command, *, cwd, environment, report, deadline, limits):
            nonlocal observations
            if command != self._observation_command():
                deadlines.append(("producer", deadline))
                return self._fake_run(
                    command,
                    cwd=cwd,
                    environment=environment,
                    report=report,
                    deadline=deadline,
                    limits=limits,
                )
            deadlines.append(("observation", deadline))
            observations += 1
            if observations == 2:
                return None, "not started: the inventory deadline had passed", False
            report.write_text(self._observation(), encoding="utf-8")
            return 0, None, False

        inventory = self._run(run, "import-untyped")
        self.assertEqual(1, len({deadline for _, deadline in deadlines}))
        self.assertEqual(
            ["observation", "observation"],
            [k for k, _ in deadlines if k == "observation"],
        )
        self.assertEqual("observation", deadlines[-1][0])
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertIsNone(member["after"])

    def test_the_observation_enforces_its_caps_while_it_enumerates(self) -> None:
        # The collector's own script over two controlled roots. The output cap lies
        # above the fixed stand-in that names it and below the full observation, so its
        # case proves the bound itself (Sourcery on #452).
        caps = self.module.ENVIRONMENT_OBSERVATION_CAPS
        roots = (self._observed_root("first"), self._observed_root("second"))
        cases = (
            (caps, None),
            ({**caps, "roots": 1}, "roots"),
            ({**caps, "entries_per_root": 1}, "entries_per_root"),
            # Each root holds 3 entries and a 64-byte RECORD: only the totals stop
            # these two (X19, X20, round 3).
            ({**caps, "entries": 3}, "entries"),
            ({**caps, "file_bytes": 1}, "file_bytes"),
            ({**caps, "file_bytes_total": 100}, "file_bytes_total"),
            # One distribution in each root: only the second stops it (X64, Claude on
            # #452).
            ({**caps, "distributions": 1}, "distributions"),
            ({**caps, "string_bytes": 8}, "string_bytes"),
            ({**caps, "output_bytes": 200}, "output_bytes"),
        )
        for limit, expected in cases:
            with self.subTest(incomplete=expected):
                observed = self._observe_with(*roots, caps=limit)
                self.assertEqual(
                    self.module.ENVIRONMENT_OBSERVATION_FORMAT, observed["format"]
                )
                self.assertEqual(expected, observed["incomplete"])
                self.assertLessEqual(self.observed_bytes, limit["output_bytes"])
                if expected is None:
                    self.assertEqual([str(r) for r in roots], observed["roots"])
                    self.assertEqual(2, len(observed["distributions"]))
                if expected == "entries_per_root":
                    self.assertTrue(
                        all(len(v) <= 1 for v in observed["entries"].values())
                    )
                if expected == "string_bytes":
                    # A root path over the cap ends the enumeration: none is kept.
                    self.assertEqual([], observed["roots"])

    def test_an_observation_in_another_format_is_a_gap(self) -> None:
        # Only the collector's own format is an observation (X11, round 1).
        foreign = json.loads(self._observation())
        foreign["format"] = "another-observation/v1"

        def run(command, *, cwd, environment, report, deadline, limits):
            if command != self._observation_command():
                return self._fake_run(
                    command,
                    cwd=cwd,
                    environment=environment,
                    report=report,
                    deadline=deadline,
                    limits=limits,
                )
            report.write_text(json.dumps(foreign), encoding="utf-8")
            return 0, None, False

        inventory = self._run(run, "import-untyped")
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertIsNone(member["before"])

    def test_an_unavailable_first_observation_is_a_gap(self) -> None:
        # Either end missing leaves nothing to compare, even when the other completed
        # (X17, round 1).
        inventory = self._run(
            self._environment(None, ("fixture-1.0",)), "import-untyped"
        )
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertIsNone(member["before"])
        self.assertIsNotNone(member["after"])
        self.assertIn(
            "producer environment identity unavailable", inventory["coverage"]["reason"]
        )

    def test_the_observation_command_runs_as_the_collector_composes_it(self) -> None:
        # The composed command's own caps and format, run for real over a controlled
        # root (X18, round 1).
        observed = self._observe_with(self._observed_root("composed"))
        self.assertEqual(self.module.ENVIRONMENT_OBSERVATION_FORMAT, observed["format"])
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(
            os.path.realpath(sys.executable), observed["interpreter"]["executable"]
        )

    def test_the_output_cap_counts_the_final_newline(self) -> None:
        # At exactly the output's size the observation fits; one byte less and only
        # the stand-in that names the cap is written (Sourcery on #452).
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        root = self._observed_root("boundary")
        self.assertIsNone(self._observe_with(root, caps=caps)["incomplete"])
        size = self.observed_bytes
        fits = self._observe_with(root, caps={**caps, "output_bytes": size})
        self.assertIsNone(fits["incomplete"])
        short = self._observe_with(root, caps={**caps, "output_bytes": size - 1})
        self.assertEqual("output_bytes", short["incomplete"])
        self.assertLessEqual(self.observed_bytes, size - 1)

    def test_the_interpreter_strings_pass_the_string_cap(self) -> None:
        # With no root at all, only the interpreter's own path and version can exceed
        # the cap (Sourcery on #452).
        caps = {**self.module.ENVIRONMENT_OBSERVATION_CAPS, "string_bytes": 8}
        observed = self._observe_with(caps=caps)
        self.assertEqual("string_bytes", observed["incomplete"])
        self.assertEqual([], observed["roots"])
        self.assertIsNone(observed["interpreter"]["executable"])

    def _answering(self, answer: object):
        """A launcher that answers the observation command with `answer` as JSON, and
        every other command as the fixture does."""
        return self._answering_text(json.dumps(answer))

    def _answering_text(self, text: str):
        """A launcher that answers the observation command with exactly `text`."""

        def run(command, *, cwd, environment, report, deadline, limits):
            if command != self._observation_command():
                return self._fake_run(
                    command,
                    cwd=cwd,
                    environment=environment,
                    report=report,
                    deadline=deadline,
                    limits=limits,
                )
            report.write_text(text, encoding="utf-8")
            return 0, None, False

        return run

    @staticmethod
    def _recording(launcher, launched: list[list[str]]):
        """`launcher`, with every command it is given appended to `launched`."""

        def run(command, **kwargs):
            launched.append(command)
            return launcher(command, **kwargs)

        return run

    def test_a_malformed_observation_is_a_gap(self) -> None:
        # The collector's own format with a broken structure is no observation: each
        # field the shape the observer writes, each checked by its own case (cubic
        # 4353631703; owner 6351449420 item 5).
        root = "/fixture/site-packages"
        for name, broken in (
            ("not a mapping", None),
            ("no interpreter", {"interpreter": None}),
            ("a version not text", {"interpreter": {"executable": "/p", "version": 3}}),
            ("roots not a list", {"roots": root}),
            ("roots a mapping", {"roots": {root: []}}),
            ("entries a list", {"entries": [root]}),
            ("entries not the roots", {"entries": {}}),
            ("an entry not text", {"entries": {root: [1]}}),
            ("archives a mapping", {"archives": {}}),
            ("an archive not a pair", {"archives": [["/fixture/a.zip"]]}),
            ("distributions a mapping", {"distributions": {}}),
            ("a distribution not a triple", {"distributions": [["/fixture", "x"]]}),
            ("unlisted a mapping", {"unlisted": {}}),
            ("an unlisted entry not four fields", {"unlisted": [[root, "x", "file"]]}),
            ("an unlisted kind unknown", {"unlisted": [[root, "x", "socket", None]]}),
            (
                "an unlisted file without a digest",
                {"unlisted": [[root, "x", "file", None]]},
            ),
            (
                "an unlisted file digest not hex",
                {"unlisted": [[root, "x", "file", "z" * 64]]},
            ),
            (
                "an unlisted link without a target",
                {"unlisted": [[root, "x", "link", None]]},
            ),
            (
                "an unlisted other with a value",
                {"unlisted": [[root, "x", "other", "v"]]},
            ),
            (
                "an unlisted entry outside the roots",
                {"unlisted": [["/x", "y", "other", None]]},
            ),
            (
                "an unlisted directory with a value",
                {"unlisted": [[root, "x", "directory", "v"]]},
            ),
            # A path is plain and root-relative (cubic on #455).
            ("an unlisted path absolute", {"unlisted": [[root, "/x", "other", None]]}),
            (
                "an unlisted path upward",
                {"unlisted": [[root, "a/../x", "other", None]]},
            ),
            (
                "an unlisted path with an empty part",
                {"unlisted": [[root, "a//x", "other", None]]},
            ),
            (
                "an unlisted path with a dot",
                {"unlisted": [[root, "a/./x", "other", None]]},
            ),
            ("an unlisted path empty", {"unlisted": [[root, "", "other", None]]}),
            ("an unknown field", {"unknown": 1}),
            (
                "an unknown interpreter field",
                {"interpreter": {"executable": "/p", "version": "v", "unknown": "x"}},
            ),
        ):
            with self.subTest(name):
                observation = (
                    [json.loads(self._observation())]
                    if broken is None
                    else {**json.loads(self._observation()), **broken}
                )
                member = self._run(self._answering(observation), "import-untyped")[
                    "producers"
                ][0]["environment_observation"]
                self.assertEqual("unavailable", member["status"])

    def _with_probe_runs(self, *probes: tuple[str, list[str], object]):
        """The collector's runner, merging further producers' runs after complexity's,
        without changing the collector: each probe is (producer, argv, launch), from an
        adapter that declares `launch`, or declares nothing when it is None."""
        original = self.module._run_complexity

        def run_complexity(*args, **kwargs):
            result = original(*args, **kwargs)
            for producer, argv, launch in probes:
                record = {
                    "invocation": producer,
                    "producer": producer,
                    "version": None,
                    "argv": argv,
                    "exit_status": 0,
                }
                if launch is None:
                    result.runs.append(record)
                else:
                    result.add_run(record, launch)
            return result

        return patch.object(self.module, "_run_complexity", side_effect=run_complexity)

    def test_the_observation_follows_the_declared_launch_not_a_name(self) -> None:
        # A producer whose adapter declares the observed launch receives the
        # observation whatever its name; one declaring another interpreter does not,
        # nor does in-process complexity (Router 6351766731 R2; PAO 6351691418).
        observed = getattr(self.module, "_ISOLATED_PYTHON", None)
        self.assertIsNotNone(observed, "the collector declares no observed launch")
        other = self.module._Launch("/another/python", ("-I",))
        with self._with_probe_runs(
            ("probe-producer", [*observed.argv(), "-m", "probe"], observed),
            ("another-interpreter", [*other.argv(), "-m", "probe"], other),
        ):
            inventory = self._run(self._environment(("fixture-1.0",)), "import-untyped")
        runs = {r["producer"]: r for r in inventory["producers"]}
        self.assertIn("environment_observation", runs["probe-producer"])
        self.assertNotIn("environment_observation", runs["another-interpreter"])
        self.assertNotIn("environment_observation", runs["complexity"])
        self.assertIn("environment_observation", runs["mypy"])
        self.assertIn("environment_observation", runs["ruff"])

    def test_a_run_that_only_looks_like_the_observed_launch_gets_no_observation(
        self,
    ) -> None:
        # An argv that starts as the observed interpreter's does, from an adapter that
        # declares no launch, is no association: neither a name nor an argv prefix
        # proves a run's scope (Router 6351766731 R2; PAO 6351691418).
        argv = [sys.executable, "-I", "-m", "lookalike"]
        with self._with_probe_runs(("lookalike", argv, None)):
            inventory = self._run(self._environment(("fixture-1.0",)), "import-untyped")
        runs = {r["producer"]: r for r in inventory["producers"]}
        self.assertNotIn("environment_observation", runs["lookalike"])
        self.assertIn("environment_observation", runs["mypy"])

    def _observer(self) -> Path:
        return (
            Path(self.module.__file__).resolve().parent
            / "python_environment_observation.py"
        )

    def test_the_observer_is_the_module_beside_the_collector(self) -> None:
        # The observer is the toolkit's own module beside the collector, run by its
        # path under -I: never the staged tree's, the cwd's or one searched on PATH
        # (Router 6351766731 R1).
        observer = self._observer()
        self.assertTrue(
            observer.is_file() and not observer.is_symlink(),
            "no observer module beside the collector",
        )
        command = self.module._environment_command()
        self.assertEqual([sys.executable, "-I", str(observer)], command[:3])
        self.assertNotIn("-c", command)

    def test_the_observer_imports_only_the_standard_library(self) -> None:
        # Under -I the observer cannot import the toolkit, and it does not try to.
        observer = self._observer()
        self.assertTrue(observer.is_file(), "no observer module beside the collector")
        tree = ast.parse(observer.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertLessEqual(imported, set(sys.stdlib_module_names))

    def test_a_missing_or_linked_observer_is_unavailable_without_a_launch(
        self,
    ) -> None:
        # Refused before any launch: an observer that is missing, or reached through a
        # link (Router 6351766731 R1).
        target = Path(self.directory.name) / "observer-target.py"
        target.write_text("print('{}')\n", encoding="utf-8")
        linked = Path(self.directory.name) / "linked-observer.py"
        linked.symlink_to(target)
        for name, observer in (
            ("missing", Path(self.directory.name) / "absent-observer.py"),
            ("linked", linked),
        ):
            with self.subTest(name):
                launched: list[list[str]] = []
                run = self._recording(self._environment(("fixture-1.0",)), launched)
                with patch.object(self.module, "_OBSERVER", observer, create=True):
                    inventory = self._run(run, "import-untyped")
                member = inventory["producers"][0]["environment_observation"]
                self.assertEqual("unavailable", member["status"])
                observations = [
                    command
                    for command in launched
                    if not (
                        "--version" in command or "mypy" in command or "ruff" in command
                    )
                ]
                self.assertEqual([], observations)

    def test_the_observer_runs_isolated_from_a_planted_working_directory(
        self,
    ) -> None:
        # Characterization, run for real: a staged root that plants an observer of its
        # own, at its top and under tools/, and a json.py, runs none of them, and
        # neither that root nor the observer's directory is an observed import root
        # (Router 6351766731 R1).
        forged_report = json.dumps(
            {
                "format": self.module.ENVIRONMENT_OBSERVATION_FORMAT,
                "incomplete": None,
                "roots": ["/forged"],
            }
        )
        forged = f"print({forged_report!r})\n"
        for place in (
            "python_environment_observation.py",
            "tools/python_environment_observation.py",
            "json.py",
        ):
            (self.root / place).parent.mkdir(parents=True, exist_ok=True)
            (self.root / place).write_text(forged, encoding="utf-8")
        run = Path(self.directory.name) / "isolated-run"
        run.mkdir()
        self.module._observe_environment(
            self.root,
            run,
            self.module.DEFAULT_DIAGNOSTIC_LIMITS,
            time.monotonic() + 120,
            "before",
        )
        # The real environment may still leave the observation incomplete, through a
        # cap, a listed file that cannot be read or a real mismatch; rows outside their
        # root never do (E1, Octopus on #453). So isolation is read from the
        # observer's own report, complete or not.
        report = run / "diagnostic-environment-before.json"
        observed = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(self.module.ENVIRONMENT_OBSERVATION_FORMAT, observed["format"])
        roots = {os.path.realpath(root) for root in observed["roots"]}
        self.assertNotIn("/forged", observed["roots"])
        self.assertNotIn(os.path.realpath(self.root), roots)
        self.assertNotIn(os.path.realpath(self._observer().parent), roots)
        self.assertEqual(
            os.path.realpath(sys.executable), observed["interpreter"]["executable"]
        )

    def test_the_member_is_additive_to_the_record(self) -> None:
        # Characterization: the record keeps its fields; the member is the one
        # optional addition, absent where nothing was observed (complexity), and its
        # unobserved scope is the one field added to it (Router 6351766731).
        inventory = self._run(self._environment(("fixture-1.0",)), "import-untyped")
        self.assertEqual("gnostoa-diagnostic-inventory/v3", inventory["schema"])
        known = {"invocation", "producer", "version", "argv", "exit_status", "report"}
        for record in inventory["producers"]:
            self.assertLessEqual(set(record) - known, {"environment_observation"})
        runs = {r["producer"]: r for r in inventory["producers"]}
        self.assertNotIn("environment_observation", runs["complexity"])
        self.assertEqual(
            {
                "format",
                "scope",
                "caps",
                "unobserved",
                "status",
                "interpreter",
                "before",
                "after",
            },
            set(runs["ruff"]["environment_observation"]),
        )

    def test_the_observation_names_what_it_does_not_observe(self) -> None:
        # Equal endpoints are never complete equality: the member lists its unobserved
        # scope (owner 6351449420 item 4).
        inventory = self._run(self._environment(("fixture-1.0",)), "import-untyped")
        member = inventory["producers"][0]["environment_observation"]
        self.assertIn("unobserved", member, "the member names no unobserved scope")
        unobserved = member["unobserved"]
        for scope in (
            "installed files a RECORD lists without a hash",
            "files outside RECORD-owned directories: loose top-level modules and the "
            "standard library",
            "rows outside the import root",
            "import resolution beyond the interpreter's -I path",
            "changes between the endpoints",
        ):
            self.assertIn(scope, unobserved)

    def test_an_observation_in_the_previous_format_is_a_gap(self) -> None:
        # RED (D-U, one shared v2 authority): a v1 report, its fields complete, is
        # refused by the v2 collector, never relabelled as the new coverage.
        observation = json.loads(self._observation())
        del observation["unlisted"]
        observation["format"] = "gnostoa-producer-environment-observation/v1"
        member = self._run(self._answering(observation), "import-untyped")["producers"][
            0
        ]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertEqual(
            "gnostoa-producer-environment-observation/v2", member["format"]
        )

    def test_a_record_reached_through_a_link_is_unreadable(self) -> None:
        # Only a regular file, never followed through a link, as the existing bounded
        # reader does (adoption_check._read_regular_bounded; owner 6351449420 item 1).
        site = Path(self.directory.name) / "linked-site"
        (site / "linked-1.0.dist-info").mkdir(parents=True)
        target = Path(self.directory.name) / "elsewhere-RECORD"
        target.write_text("x" * 64, encoding="utf-8")
        (site / "linked-1.0.dist-info" / "RECORD").symlink_to(target)
        self.assertEqual("unreadable", self._observe_with(site)["incomplete"])

    def test_a_record_that_is_not_a_regular_file_is_refused_without_blocking(
        self,
    ) -> None:
        # A FIFO RECORD is opened without blocking and refused as not a regular file:
        # the copied pattern keeps the owner's refusal, never waiting for a writer
        # (PAO 6351691418).
        site = Path(self.directory.name) / "fifo-site"
        (site / "fifo-1.0.dist-info").mkdir(parents=True)
        os.mkfifo(site / "fifo-1.0.dist-info" / "RECORD")
        started = time.monotonic()
        self.assertEqual("unreadable", self._observe_with(site)["incomplete"])
        self.assertLess(time.monotonic() - started, 30)

    def test_a_record_that_fails_mid_read_stops_the_observation(self) -> None:
        # Characterization, in process: a read that fails once the file is open is an
        # unreadable stop, never a digest or an escaping error (owner 6351449420 item 6).
        observer = importlib.import_module("tools.python_environment_observation")
        record = Path(self.directory.name) / "RECORD"
        record.write_text("x" * 64, encoding="utf-8")
        opened = os.fdopen

        class Failing:
            def __init__(self, stream) -> None:
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> None:
                self.stream.close()

            def fileno(self) -> int:
                return self.stream.fileno()

            def read(self, size: int) -> bytes:
                raise OSError(errno.EIO, "a read that fails mid-file")

        observation = observer._Observation(
            dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        )
        with patch.object(
            observer.os,
            "fdopen",
            lambda fd, *args, **kwargs: Failing(opened(fd, *args, **kwargs)),
        ):
            self.assertIsNone(observation.digest_of(str(record)))
        self.assertEqual("unreadable", observation.incomplete)

    def test_a_report_with_a_duplicate_field_is_a_gap(self) -> None:
        # A field given twice is refused while decoding, never read as its last value
        # (cubic 4354512437; security_scan's strict loader, #365 F1).
        text = '{"format": "elsewhere", ' + self._observation().lstrip()[1:]
        member = self._run(self._answering_text(text), "import-untyped")["producers"][
            0
        ]["environment_observation"]
        self.assertEqual("unavailable", member["status"])

    def test_an_observer_without_a_safe_open_stops(self) -> None:
        # Where the platform lacks the no-follow or non-blocking open, the observation
        # stops as unreadable, never following a link or blocking (Codex 4354512574,
        # cubic 4354512373; adoption_check._read_regular_bounded).
        observer = importlib.import_module("tools.python_environment_observation")
        root = self._observed_root("unsafe-open")
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        for flags in ("_SAFE_OPEN", "_DIRECTORY_OPEN"):
            with self.subTest(flags), patch.object(observer, flags, None, create=True):
                observed = json.loads(observer.observe([str(root)], caps, form))
                self.assertEqual("unreadable", observed["incomplete"])

    @staticmethod
    def _offset_recording(opened, offsets: list[int]):
        """`opened` (os.fdopen), its streams appending the descriptor's offset after
        every read to `offsets`: what the reader consumed from the file."""

        class Recording:
            def __init__(self, stream) -> None:
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> None:
                self.stream.close()

            def fileno(self) -> int:
                return self.stream.fileno()

            def read(self, size: int = -1) -> bytes:
                chunk = self.stream.read(size)
                offsets.append(os.lseek(self.fileno(), 0, os.SEEK_CUR))
                return chunk

        return lambda fd, *args, **kwargs: Recording(opened(fd, *args, **kwargs))

    def test_a_read_never_passes_a_file_cap_by_more_than_one_byte(self) -> None:
        # Each read asks for at most what is left of both file caps, and one byte more
        # to see an overflow; the descriptor's offset is what the observer consumed
        # (cubic 4354512414).
        observer = importlib.import_module("tools.python_environment_observation")
        record = Path(self.directory.name) / "LARGE-RECORD"
        record.write_bytes(b"x" * 100_000)
        opened = os.fdopen
        base = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        for name, caps, stop in (
            ("per file", {**base, "file_bytes": 1}, "file_bytes"),
            ("in all", {**base, "file_bytes_total": 1}, "file_bytes_total"),
        ):
            with self.subTest(name):
                offsets: list[int] = []
                observation = observer._Observation(caps)
                with patch.object(
                    observer.os, "fdopen", self._offset_recording(opened, offsets)
                ):
                    self.assertIsNone(observation.digest_of(str(record)))
                self.assertEqual(stop, observation.incomplete)
                self.assertLessEqual(max(offsets), 2)

    def test_a_distribution_directory_reached_through_a_link_is_unreadable(
        self,
    ) -> None:
        # The *.dist-info directory is opened without following a link, and its RECORD
        # relative to it: no component of the RECORD's path is followed (cubic
        # 4354512430).
        site = Path(self.directory.name) / "linked-dist-site"
        site.mkdir()
        real = Path(self.directory.name) / "real-dist-info"
        real.mkdir()
        (real / "RECORD").write_text("x" * 64, encoding="utf-8")
        (site / "linked-1.0.dist-info").symlink_to(real, target_is_directory=True)
        self.assertEqual("unreadable", self._observe_with(site)["incomplete"])

    def test_a_record_is_read_from_the_directory_opened_not_its_path(self) -> None:
        # Kill test (X54, round 5): the RECORD is opened relative to the *.dist-info
        # directory the observer opened, so a directory replaced by a link after that
        # open is never followed (cubic 4354512430). The walk then enters that owned
        # directory again and finds this test's substituted link in its place: the
        # observation stops as unreadable, never complete (D-U). This is that one
        # substitution, not a guarantee that any change in place is seen.
        observer = importlib.import_module("tools.python_environment_observation")
        site = self._observed_root("swapped")
        dist = site / "one-1.0.dist-info"
        elsewhere = Path(self.directory.name) / "elsewhere-dist-info"
        elsewhere.mkdir()
        (elsewhere / "RECORD").write_text("y" * 64, encoding="utf-8")
        moved = Path(self.directory.name) / "moved-dist-info"
        opened = os.open

        def swapping(path, flags, *args, **kwargs):
            descriptor = opened(path, flags, *args, **kwargs)
            named = os.fspath(path) in (str(dist), dist.name)
            if named and flags & os.O_DIRECTORY and not moved.exists():
                dist.rename(moved)
                dist.symlink_to(elsewhere, target_is_directory=True)
            return descriptor

        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        opened_record = hashlib.sha256((dist / "RECORD").read_bytes()).hexdigest()
        with patch.object(observer.os, "open", swapping):
            observed = json.loads(observer.observe([str(site)], caps, form))
        self.assertEqual("unreadable", observed["incomplete"])
        self.assertEqual(
            [[str(site), "one-1.0.dist-info", opened_record]],
            observed["distributions"],
        )

    def test_a_record_and_the_files_it_names_come_from_one_root(self) -> None:
        # Q 4358351672 on #453: the RECORD and the files its rows name are read from
        # one opened import root, so a root link retargeted between the two never
        # verifies one directory's RECORD against another directory's files.
        observer = importlib.import_module("tools.python_environment_observation")
        first = self._recorded_root("first-root")
        second = self._recorded_root("second-root")
        (first / "mm" / "__init__.py").write_text("VALUE: int = 1\n", encoding="utf-8")
        link = Path(self.directory.name) / "linked-site"
        link.symlink_to(first, target_is_directory=True)
        retarget = Path(self.directory.name) / "linked-site.new"
        dist = "mm-1.0.dist-info"
        opened = os.open

        def swapping(path, flags, *args, **kwargs):
            descriptor = opened(path, flags, *args, **kwargs)
            named = os.fspath(path) in (str(link / dist), dist)
            if named and not retarget.exists():
                retarget.symlink_to(second, target_is_directory=True)
                os.replace(retarget, link)
                retarget.mkdir()
            return descriptor

        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        with patch.object(observer.os, "open", swapping):
            observed = json.loads(observer.observe([str(link)], caps, form))
        self.assertTrue(retarget.exists())
        self.assertEqual("record_mismatch", observed["incomplete"])

    def test_a_distribution_is_opened_from_the_root_already_opened(self) -> None:
        # Kill test for the root binding (Q and Sourcery on #453): the *.dist-info
        # directory is opened relative to the import root's descriptor, so a root link
        # retargeted right after that open never pairs another root's RECORD with this
        # root's files. Here the first root agrees with its RECORD and the second does
        # not, with a RECORD of other bytes.
        observer = importlib.import_module("tools.python_environment_observation")
        first = self._recorded_root("consistent-root")
        second = self._recorded_root("inconsistent-root", "mm/extra.txt,,")
        (second / "mm" / "__init__.py").write_text("VALUE: int = 1\n", encoding="utf-8")
        link = Path(self.directory.name) / "linked-consistent"
        link.symlink_to(first, target_is_directory=True)
        retarget = Path(self.directory.name) / "linked-consistent.new"
        expected = hashlib.sha256(
            (first / "mm-1.0.dist-info" / "RECORD").read_bytes()
        ).hexdigest()
        opened = os.open

        def swapping(path, flags, *args, **kwargs):
            descriptor = opened(path, flags, *args, **kwargs)
            if os.fspath(path) == str(link) and not retarget.exists():
                retarget.symlink_to(second, target_is_directory=True)
                os.replace(retarget, link)
                retarget.mkdir()
            return descriptor

        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        with patch.object(observer.os, "open", swapping):
            observed = json.loads(observer.observe([str(link)], caps, form))
        self.assertTrue(retarget.exists())
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(
            [[str(link), "mm-1.0.dist-info", expected]], observed["distributions"]
        )

    def test_an_alias_into_the_opened_root_is_ambiguous_after_a_swap(self) -> None:
        # CodeAnt on #453 and PAO-453-ROOT-CLASSIFICATION-ANCHOR-7EBFCE9B-v1: a row is
        # classified against the real path of the root that was opened, not one
        # recomputed later, so a root link retargeted after its open never turns an
        # alias into that root, relative or absolute, into an unchecked "outside" row.
        observer = importlib.import_module("tools.python_environment_observation")
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        claim = f"sha256={self._claim(b'x')},1"
        opened = os.open
        for kind in ("relative", "absolute"):
            with self.subTest(kind):
                name = f"alias-{kind}-root"
                row = (
                    f"../{name}/mm/__init__.py"
                    if kind == "relative"
                    else f"{Path(self.directory.name).resolve() / name}/mm/__init__.py"
                )
                pinned = self._recorded_root(name, f"{row},{claim}")
                other = self._recorded_root(f"alias-{kind}-other")
                link = Path(self.directory.name) / f"linked-alias-{kind}"
                link.symlink_to(pinned, target_is_directory=True)
                retarget = Path(self.directory.name) / f"linked-alias-{kind}.new"

                def swapping(
                    path,
                    flags,
                    *args,
                    link=link,
                    other=other,
                    retarget=retarget,
                    **kwargs,
                ):
                    descriptor = opened(path, flags, *args, **kwargs)
                    if os.fspath(path) == str(link) and not retarget.exists():
                        retarget.symlink_to(other, target_is_directory=True)
                        os.replace(retarget, link)
                        retarget.mkdir()
                    return descriptor

                with patch.object(observer.os, "open", swapping):
                    observed = json.loads(observer.observe([str(link)], caps, form))
                self.assertTrue(retarget.exists())
                self.assertEqual("record_ambiguous_path", observed["incomplete"])

    def test_a_root_that_changes_while_being_opened_is_unreadable(self) -> None:
        # Kill test for the pinned real path (CodeAnt on #453): a root link retargeted
        # between the read of its real path and its open leaves a real path naming
        # another directory than the one opened, and the observation stops.
        observer = importlib.import_module("tools.python_environment_observation")
        first = self._recorded_root("racing-first")
        second = self._recorded_root("racing-second")
        link = Path(self.directory.name) / "linked-racing"
        link.symlink_to(first, target_is_directory=True)
        retarget = Path(self.directory.name) / "linked-racing.new"
        resolved = os.path.realpath

        def swapping(path, *args, **kwargs):
            real = resolved(path, *args, **kwargs)
            if os.fspath(path) == str(link) and not retarget.exists():
                retarget.symlink_to(second, target_is_directory=True)
                os.replace(retarget, link)
                retarget.mkdir()
            return real

        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        with patch.object(observer.os.path, "realpath", swapping):
            observed = json.loads(observer.observe([str(link)], caps, form))
        self.assertTrue(retarget.exists())
        self.assertEqual("unreadable", observed["incomplete"])

    def test_the_observation_closes_every_descriptor_it_opens(self) -> None:
        # Kill test (R12, round 3): whichever way a distribution's check ends, matched,
        # mismatched, malformed, outside, ambiguous, unreadable or with a linked
        # *.dist-info directory, the observer closes every descriptor it opened.
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("needs /proc/self/fd to count descriptors")
        observer = importlib.import_module("tools.python_environment_observation")
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        claim = f"sha256={self._claim(b'x')},1"
        mismatched = self._recorded_root("fd-mismatched")
        (mismatched / "mm" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
        linked = self._recorded_root("fd-linked")
        (linked / "mm-1.0.dist-info").rename(linked / "elsewhere")
        (linked / "mm-1.0.dist-info").symlink_to(linked / "elsewhere")
        roots = (
            self._recorded_root("fd-matched"),
            mismatched,
            self._recorded_root("fd-malformed", "mm/__init__.py,md5=x,1"),
            self._recorded_root("fd-outside", f"../bin/tool,{claim}"),
            self._recorded_root("fd-ambiguous", f"mm/../x.py,{claim}"),
            self._recorded_root("fd-unreadable", f"mm/absent/x.py,{claim}"),
            linked,
        )
        for root in roots:
            with self.subTest(root.name):
                before = sorted(os.listdir("/proc/self/fd"))
                observer.observe([str(root)], caps, form)
                self.assertEqual(before, sorted(os.listdir("/proc/self/fd")))

    def test_an_inaccessible_root_is_unreadable_never_absent(self) -> None:
        # An import-path entry that exists but cannot be examined stops the observation
        # as unreadable; only a path that is absent is skipped (PAO 6353587922,
        # PAO-452-ROOT-PERMISSION-NOT-ABSENCE-A4B26156-v1).
        observer = importlib.import_module("tools.python_environment_observation")
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        root = self._observed_root("inaccessible")
        absent = Path(self.directory.name) / "absent-root"
        observed = json.loads(observer.observe([str(absent)], caps, form))
        self.assertIsNone(observed["incomplete"], "an absent entry is skipped")
        self.assertEqual([], observed["roots"])
        examined = os.stat

        def refusing(path, *args, **kwargs):
            if os.fspath(path) == str(root):
                raise PermissionError(errno.EACCES, "permission denied", str(path))
            return examined(path, *args, **kwargs)

        with self.subTest("simulated"), patch.object(observer.os, "stat", refusing):
            observed = json.loads(observer.observe([str(root)], caps, form))
            self.assertEqual("unreadable", observed["incomplete"])

    def test_a_real_permission_denial_reaches_the_collector_as_a_gap(self) -> None:
        # The negative control where denial really occurs: the observer's own child
        # over a root whose parent denies search, and its report through the actual
        # acceptance boundary, which records unavailable and its gap. The positive
        # control, an absent entry, is accepted (Router 6353798690).
        absent = self._observe_with(Path(self.directory.name) / "absent-root")
        self.assertIsNone(absent["incomplete"])
        member = self._run(self._answering(absent), "import-untyped")["producers"][0][
            "environment_observation"
        ]
        self.assertEqual("endpoints_equal", member["status"])
        parent = Path(self.directory.name) / "closed-parent"
        closed = parent / "root"
        closed.mkdir(parents=True)
        parent.chmod(0o600)
        try:
            try:
                closed.stat()
            except PermissionError:
                pass
            else:
                # An elevated process reads past the permission, so the control
                # cannot occur here: reported as skipped, never passed.
                self.skipTest("this process is not denied the closed root")
            observed = self._observe_with(closed)
        finally:
            parent.chmod(0o700)
        self.assertEqual("unreadable", observed["incomplete"])
        inventory = self._run(self._answering(observed), "import-untyped")
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertRegex(
            inventory["coverage"]["reason"] or "",
            r"producer environment identity unavailable",
        )

    def test_an_observation_without_its_completion_marker_is_a_gap(self) -> None:
        # Characterization: a report lacking `incomplete` is not the observer's format,
        # so its absence is never read as complete (PAO 6353587922).
        observation = json.loads(self._observation())
        del observation["incomplete"]
        member = self._run(self._answering(observation), "import-untyped")["producers"][
            0
        ]["environment_observation"]
        self.assertEqual("unavailable", member["status"])

    def test_the_fixture_launchers_refuse_an_unexpected_launch(self) -> None:
        # A launcher answers only the observation the collector must compose, never
        # any other command, so that a wrong launch fails its test (CodeAnt on #452).
        wrong = [
            sys.executable,
            "-I",
            "/elsewhere/python_environment_observation.py",
            json.dumps(self.module.ENVIRONMENT_OBSERVATION_CAPS, sort_keys=True),
            self.module.ENVIRONMENT_OBSERVATION_FORMAT,
        ]
        report = Path(self.directory.name) / "unexpected-launch.json"
        for name, launcher in (
            ("the environment launcher", self._environment(("fixture-1.0",))),
            (
                "the answering launcher",
                self._answering(json.loads(self._observation())),
            ),
            ("the fixture launcher", self._fake_run),
        ):
            with self.subTest(name), self.assertRaises(AssertionError):
                launcher(
                    wrong,
                    cwd=self.root,
                    environment={},
                    report=report,
                    deadline=time.monotonic() + 60,
                    limits=self.module.DEFAULT_DIAGNOSTIC_LIMITS,
                )

    def test_the_fixture_pins_the_observation_it_answers(self) -> None:
        # The expected launch is pinned, never read from the collector: a collector
        # whose caps, format or observer has moved is refused, so that such a regression
        # fails its tests (cubic 4355103949).
        changed = {**self.module.ENVIRONMENT_OBSERVATION_CAPS, "roots": 1}
        report = Path(self.directory.name) / "moved-launch.json"
        for name, moved in (
            ("caps", ("ENVIRONMENT_OBSERVATION_CAPS", changed)),
            ("format", ("ENVIRONMENT_OBSERVATION_FORMAT", "elsewhere/v1")),
            ("observer", ("_OBSERVER", Path("/elsewhere/observer.py"))),
        ):
            with self.subTest(name), patch.object(self.module, *moved):
                command = self.module._environment_command()
                with self.assertRaises(AssertionError):
                    self._environment(("fixture-1.0",))(
                        command,
                        cwd=self.root,
                        environment={},
                        report=report,
                        deadline=time.monotonic() + 60,
                        limits=self.module.DEFAULT_DIAGNOSTIC_LIMITS,
                    )

    @staticmethod
    def _record_row(root: Path, relative: str) -> str:
        """A RECORD row as an installer writes it: the path, sha256= urlsafe base64
        without padding, and the size."""
        content = (root / relative).read_bytes()
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
        return f"{relative},sha256={digest.decode()},{len(content)}"

    def _recorded_root(self, name: str, *rows: str) -> Path:
        """A root with the typed distribution `mm` 1.0, whose RECORD lists its module,
        py.typed and METADATA with their real digests, and then any extra `rows`."""
        root = Path(self.directory.name) / name
        (root / "mm").mkdir(parents=True)
        (root / "mm-1.0.dist-info").mkdir()
        (root / "mm" / "__init__.py").write_text('VALUE: str = "s"\n', encoding="utf-8")
        (root / "mm" / "py.typed").write_text("", encoding="utf-8")
        (root / "mm-1.0.dist-info" / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: mm\nVersion: 1.0\n", encoding="utf-8"
        )
        listed = [
            self._record_row(root, f)
            for f in ("mm/__init__.py", "mm/py.typed", "mm-1.0.dist-info/METADATA")
        ]
        record = [*listed, *rows, "mm-1.0.dist-info/RECORD,,"]
        (root / "mm-1.0.dist-info" / "RECORD").write_text(
            "\n".join(record) + "\n", encoding="utf-8"
        )
        return root

    def test_a_record_that_matches_its_files_is_a_complete_observation(self) -> None:
        # Characterization: every hashed RECORD row agrees with its file, so the
        # observation completes (F3-S2-RECORD-GUARD positive control).
        observed = self._observe_with(self._recorded_root("matched"))
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(1, len(observed["distributions"]))

    def test_an_installed_file_that_differs_from_its_record_stops_the_observation(
        self,
    ) -> None:
        # The installed module's bytes changed while its RECORD, METADATA, version and
        # names did not: the observation stops as record_mismatch, through the
        # observer and through the collector's acceptance boundary (Router #389
        # 6361147179; the f837 probe 6360875795).
        root = self._recorded_root("mismatched")
        (root / "mm" / "__init__.py").write_text("VALUE: int = 1\n", encoding="utf-8")
        observed = self._observe_with(root)
        self.assertEqual("record_mismatch", observed["incomplete"])
        inventory = self._run(self._answering(observed), "import-untyped")
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertRegex(
            inventory["coverage"]["reason"] or "",
            r"producer environment identity unavailable",
        )

    def test_a_record_row_that_cannot_be_verified_stops_the_observation(self) -> None:
        # A hashed row that is not a supported, well-formed sha256 over a readable
        # regular file in the root never passes as verified (Router #389 6361147179).
        # A well-formed sha256 claim, so that each case isolates its own condition.
        claim = base64.urlsafe_b64encode(hashlib.sha256(b"x").digest()).rstrip(b"=")
        claim = claim.decode()
        cases = (
            (
                "an unsupported algorithm",
                "mm/__init__.py,md5=abcd,17",
                "record_unsupported",
            ),
            ("a malformed digest", "mm/__init__.py,sha256=!!!,17", "record_malformed"),
            ("a short digest", "mm/__init__.py,sha256=AAAA,17", "record_malformed"),
            (
                "a malformed size",
                f"mm/__init__.py,sha256={claim},many",
                "record_malformed",
            ),
            ("a missing listed file", f"mm/absent.py,sha256={claim},1", "unreadable"),
        )
        for name, row, reason in cases:
            with self.subTest(name):
                root = self._recorded_root(name.replace(" ", "-"), row)
                self.assertEqual(reason, self._observe_with(root)["incomplete"])
        with self.subTest("a listed file reached through a link"):
            root = self._recorded_root("linked-listed")
            target = Path(self.directory.name) / "elsewhere-module.py"
            target.write_text('VALUE: str = "s"\n', encoding="utf-8")
            (root / "mm" / "__init__.py").unlink()
            (root / "mm" / "__init__.py").symlink_to(target)
            self.assertEqual("unreadable", self._observe_with(root)["incomplete"])
        with self.subTest("a listed file that is not a regular file"):
            root = self._recorded_root("fifo-listed")
            (root / "mm" / "__init__.py").unlink()
            os.mkfifo(root / "mm" / "__init__.py")
            self.assertEqual("unreadable", self._observe_with(root)["incomplete"])

    @staticmethod
    def _claim(content: bytes) -> str:
        """A well-formed sha256 RECORD claim for `content`."""
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=")
        return digest.decode()

    def test_a_row_outside_its_root_is_outside_the_check_and_never_accessed(
        self,
    ) -> None:
        # E1 (Router #389 6361519666): a valid console-script or data row naming a path
        # lexically outside the import root is classified before any filesystem access:
        # never opened, stat'ed or hashed, never verified, and it does not stop an
        # otherwise complete observation. The outside target is a FIFO, so any access
        # would leave the observation incomplete.
        outside = Path(self.directory.name) / "outside-bin"
        sibling = Path(self.directory.name) / "with-script-bin"
        for directory in (outside, sibling):
            directory.mkdir()
            os.mkfifo(directory / "tool")
        claim = f"sha256={self._claim(b'x')},1"
        root = self._recorded_root(
            "with-script",
            f"../outside-bin/tool,{claim}",
            f"{outside}/tool,{claim}",
            f"../with-script-bin/tool,{claim}",
        )
        observed = self._observe_with(root)
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(1, len(observed["distributions"]))
        observer = importlib.import_module("tools.python_environment_observation")
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        touched: list[str] = []
        real_open, real_stat, real_lstat = os.open, os.stat, os.lstat

        def opening(path, *args, **kwargs):
            touched.append(os.fspath(path))
            return real_open(path, *args, **kwargs)

        def stating(path, *args, **kwargs):
            touched.append(os.fspath(path))
            return real_stat(path, *args, **kwargs)

        def lstating(path, *args, **kwargs):
            touched.append(os.fspath(path))
            return real_lstat(path, *args, **kwargs)

        with (
            patch.object(observer.os, "open", opening),
            patch.object(observer.os, "stat", stating),
            patch.object(observer.os, "lstat", lstating),
        ):
            result = json.loads(observer.observe([str(root)], caps, form))
        self.assertIsNone(result["incomplete"])
        self.assertTrue(touched)
        self.assertFalse(
            [t for t in touched if "-bin" in t or t in ("..", "tool", "outside-bin")]
        )

    def test_an_ambiguous_or_in_root_alias_row_stops_the_observation(self) -> None:
        # E1 is lexical and narrow: a traversal after a component, a path written to
        # leave the root and come back into it, an absolute path into the root, and
        # dot or empty components are not "outside"; each stops the observation, so
        # an in-scope mismatch can never hide behind them (Router #389 6361519666).
        claim = self._claim(b"x")
        root = Path(self.directory.name) / "aliased"
        cases = (
            ("a traversal after a component", "mm/../../x.py"),
            ("a relative alias back into the root", "../aliased/mm/__init__.py"),
            ("an absolute alias into the root", f"{root}/mm/__init__.py"),
            ("a dot component", "mm/./__init__.py"),
            ("an empty component", "mm//__init__.py"),
            ("the root itself", "../aliased"),
            ("a bare parent", ".."),
            ("an absolute alias with a dot", f"{root.parent}/./aliased/mm/__init__.py"),
            # Kill test (G19, round 6): a parent component, which only normalization
            # removes, since pathlib collapses a dot but never `..`.
            (
                "an absolute alias through a parent",
                f"{root.parent}/elsewhere/../aliased/mm/__init__.py",
            ),
            # Sourcery 4358369113 and 4358369120 on #453.
            ("a NUL in a component", "mm/\x00x.py"),
            ("a doubled leading slash into the root", f"/{root}/mm/__init__.py"),
            ("a doubled leading slash elsewhere", "//usr/bin/tool"),
        )
        for name, path in cases:
            with self.subTest(name):
                shutil.rmtree(root, ignore_errors=True)
                self._recorded_root("aliased", f"{path},sha256={claim},1")
                observed = self._observe_with(root)
                self.assertEqual("record_ambiguous_path", observed["incomplete"])

    def test_a_claim_in_any_but_the_canonical_encoding_is_malformed(self) -> None:
        # Sourcery 4358369089 on #453: a RECORD claim is urlsafe base64 without
        # padding, canonically; the standard alphabet, padding, or unused bits set in
        # its last character are malformed even when they decode to the right digest.
        claim = self._claim(b"x")
        self.assertIn("-", claim)
        last = string.ascii_uppercase + string.ascii_lowercase + string.digits + "-_"
        cases = (
            ("the standard alphabet", claim.replace("-", "+").replace("_", "/")),
            ("padding", claim + "="),
            ("unused bits set", claim[:-1] + last[last.index(claim[-1]) + 1]),
            # Characterization (Sonar python:S5713 on #453): base64 raises a plain
            # ValueError, not binascii.Error, for a claim that is not ASCII.
            ("a non-ASCII claim", "é" + claim[1:]),
        )
        for name, encoded in cases:
            with self.subTest(name):
                root = self._recorded_root(
                    name.replace(" ", "-"), f"mm/data.bin,sha256={encoded},1"
                )
                (root / "mm" / "data.bin").write_bytes(b"x")
                self.assertEqual(
                    "record_malformed", self._observe_with(root)["incomplete"]
                )

    def test_a_row_in_loose_quoting_or_a_non_ascii_size_is_malformed(self) -> None:
        # CodeAnt on #453: a RECORD is read as strict CSV, so quoting that a lenient
        # reader would repair into a valid path is malformed. A size is ASCII digits
        # only: a Unicode digit that `int` refuses is malformed, never an escape.
        module = b'VALUE: str = "s"\n'
        claim = self._claim(module)
        cases = (
            ("loose quoting", f'"mm/__init__."py,sha256={claim},{len(module)}'),
            ("a superscript size", f"mm/__init__.py,sha256={claim},\u00b2"),
            ("an Arabic-Indic size", f"mm/__init__.py,sha256={claim},\u0661\u0667"),
            # Owner 6364237541 item 2: a size is bounded before anything reads it, at
            # 20 digits, as 2**64 has; one digit more, or past Python's 4,300-digit
            # conversion limit, is malformed.
            ("a 21-digit size", f"mm/__init__.py,sha256={claim},{'9' * 21}"),
            ("a 4,301-digit size", f"mm/__init__.py,sha256={claim},{'1' * 4301}"),
        )
        for name, row in cases:
            with self.subTest(name):
                root = self._recorded_root(name.replace(" ", "-"), row)
                self.assertEqual(
                    "record_malformed", self._observe_with(root)["incomplete"]
                )

    def test_a_size_that_equals_its_file_as_a_number_is_verified(self) -> None:
        # Router #453 6368854931 (b), after PAO 6368524836 and CodeAnt 4361108960: the
        # PyPA RECORD size is a base-ten byte count, so a padded spelling of the right
        # count agrees; the size stays bounded at 20 ASCII digits before it is read.
        cases = (
            ("a one-byte file as 1", b"x", "1"),
            ("a one-byte file as 01", b"x", "01"),
            ("a one-byte file as 0001", b"x", "0001"),
            ("a one-byte file in 20 digits", b"x", "0" * 19 + "1"),
            ("an empty file as 0", b"", "0"),
            ("an empty file as 00", b"", "00"),
            ("an empty size", b"x", ""),
        )
        for name, content, size in cases:
            with self.subTest(name):
                row = f"mm/data.bin,sha256={self._claim(content)},{size}"
                root = self._recorded_root(name.replace(" ", "-"), row)
                (root / "mm" / "data.bin").write_bytes(content)
                self.assertIsNone(self._observe_with(root)["incomplete"])

    def test_a_size_that_disagrees_with_its_file_is_a_mismatch(self) -> None:
        # Sourcery 4358369095 on #453: a row's size is a claim too, compared with the
        # bytes read; one that disagrees stops the observation even when the digest
        # agrees.
        claim = self._claim(b"x")
        cases = (
            ("a different size", "2"),
            # The longest size admitted, 20 digits as 2**64 has (Revix 4359050029 on
            # #453), and a padded count that still disagrees.
            ("a 20-digit size", "9" * 20),
            ("a padded wrong count", "02"),
        )
        for name, size in cases:
            with self.subTest(name):
                root = self._recorded_root(
                    name.replace(" ", "-").replace("'", ""),
                    f"mm/data.bin,sha256={claim},{size}",
                )
                (root / "mm" / "data.bin").write_bytes(b"x")
                self.assertEqual(
                    "record_mismatch", self._observe_with(root)["incomplete"]
                )

    def test_a_record_is_parsed_the_same_across_its_read_chunks(self) -> None:
        # Characterization for the RECORD's streamed parse (Router 6364506650): a
        # two-byte character split across the reader's 64 KiB chunks, CRLF rows and a
        # final row without a newline parse as one decoded text does.
        module = b'VALUE: str = "s"\n'
        claim = f"sha256={self._claim(module)},{len(module)}"
        for name in (
            "a character across the chunk boundary",
            "a row across the chunk boundary",
            "CRLF rows",
            "no final newline",
        ):
            with self.subTest(name):
                root = self._recorded_root(name.replace(" ", "-"))
                record = root / "mm-1.0.dist-info" / "RECORD"
                if name == "CRLF rows":
                    body = record.read_bytes().replace(b"\n", b"\r\n")
                elif name == "no final newline":
                    body = record.read_bytes().rstrip(b"\n")
                elif name == "a row across the chunk boundary":
                    # Hashless rows, then a hashed row that starts 20 bytes before the
                    # first chunk ends, so that its parse needs both chunks.
                    (root / "mm" / "copy.py").write_bytes(module)
                    body = record.read_bytes()
                    filler = b"mm/a.py,,\n"
                    body += filler * ((65516 - len(body)) // len(filler))
                    body += b"m" * (65516 - len(body) - len(",,\n")) + b",,\n"
                    body += f"mm/copy.py,{claim}\n".encode()
                    self.assertEqual(65516, body.index(b"mm/copy.py,"))
                else:
                    # Hashless rows up to byte 65,535, then a row whose path starts
                    # with a two-byte character at bytes 65,535 and 65,536.
                    body = record.read_bytes()
                    filler = b"mm/a.py,,\n"
                    body += filler * ((65535 - len(body)) // len(filler))
                    body += b"m" * (65535 - len(body) - len(",,\n")) + b",,\n"
                    body += "é.py,,\n".encode()
                    self.assertEqual(b"\xc3", body[65535:65536])
                    (root / "mm" / "copy.py").write_bytes(module)
                    body += f"mm/copy.py,{claim}\n".encode()
                record.write_bytes(body)
                self.assertIsNone(self._observe_with(root)["incomplete"])

    def test_a_record_is_never_held_whole_while_it_is_parsed(self) -> None:
        # Router 6364506650: the RECORD's bytes are released as its lines are parsed,
        # and a line longer than any row the CSV reader accepts is refused before it is
        # held, so a RECORD at the per-file cap costs about its own size.
        observer = importlib.import_module("tools.python_environment_observation")
        chunks = [b"mm/a.py,,\n" * 6553] * 64
        lines = observer._record_lines(chunks)
        self.assertEqual("mm/a.py,,\n", next(lines))
        self.assertEqual(63, len(chunks))
        self.assertEqual(6553 * 64 - 1, sum(1 for _ in lines))
        self.assertEqual([], chunks)
        endless = [b"x" * 65536] * 64
        with self.assertRaises(csv.Error):
            next(observer._record_lines(endless))
        self.assertGreater(len(endless), 40)
        # CodeAnt on #453: a line whose end falls in the chunk that takes it past the
        # bound is refused before it is joined; one at the bound, its newline
        # included, is a line.
        bound = observer._RECORD_LINE_CHARACTERS
        for length, refused in ((bound, False), (bound + 1, True)):
            with self.subTest(length=length):
                data = b"x" * (length - 1) + b"\n"
                chunks = [data[i : i + 65536] for i in range(0, len(data), 65536)]
                lines = observer._record_lines(chunks)
                if refused:
                    with self.assertRaises(csv.Error):
                        next(lines)
                else:
                    self.assertEqual(length, len(next(lines)))

    def test_a_legitimate_large_installed_payload_is_observed(self) -> None:
        # Router 6364506650 (B): the composed caps admit a matching in-root payload of
        # the measured real size, a file over the former 8 MiB per-file cap and files
        # over the former 32 MiB aggregate, within every other limit.
        mebibyte = 1024 * 1024
        cases = (
            ("a file over the former per-file cap", (9 * mebibyte,)),
            ("files over the former aggregate", (7 * mebibyte,) * 5),
        )
        for name, sizes in cases:
            with self.subTest(name):
                contents = [bytes([index]) * size for index, size in enumerate(sizes)]
                rows = [
                    f"mm/big{index}.bin,sha256={self._claim(content)},{len(content)}"
                    for index, content in enumerate(contents)
                ]
                root = self._recorded_root(name.replace(" ", "-"), *rows)
                for index, content in enumerate(contents):
                    (root / "mm" / f"big{index}.bin").write_bytes(content)
                observed = self._observe_with(root)
                self.assertIsNone(observed["incomplete"])
                self.assertEqual(1, len(observed["distributions"]))

    def test_containment_keeps_the_parents_a_relative_root_cannot_hold(self) -> None:
        # cubic 4359922819 on #453: a relative root such as `.` has no components, so
        # a parent-relative target was "within" it and an outside row turned
        # ambiguous. Containment is exact for normalized paths: the root's components
        # begin the target's, and no `..` follows them.
        observer = importlib.import_module("tools.python_environment_observation")
        real = os.path.realpath(self.directory.name)
        bases = {".", real}
        self.assertEqual(("outside", None), observer._record_path(bases, "../bin/tool"))
        self.assertEqual(
            ("ambiguous", None),
            observer._record_path(bases, f"../{os.path.basename(real)}/mm/x.py"),
        )
        self.assertEqual(
            ("inside", ["mm", "x.py"]), observer._record_path(bases, "mm/x.py")
        )
        self.assertFalse(observer._within_any({"."}, "../bin/tool"))
        self.assertFalse(observer._within_any({"../a"}, "../../a/b"))
        self.assertTrue(observer._within_any({"."}, "mm/x.py"))
        self.assertTrue(observer._within_any({"../a"}, "../a/b"))
        self.assertTrue(observer._within_any({"/r"}, "/r"))
        # The full observer, as PAO-453-OWNER-6364237541-E41F55F8-v1 replayed it: the
        # same root supplied as `.` and as its absolute path, with a matching module
        # and a valid hashed row outside the root, is complete either way.
        root = self._recorded_root(
            "relative-root", f"../outside.bin,sha256={self._claim(b'x')},1"
        )
        caps = dict(self.module.ENVIRONMENT_OBSERVATION_CAPS)
        form = self.module.ENVIRONMENT_OBSERVATION_FORMAT
        here = os.getcwd()
        os.chdir(root)
        try:
            for spelling in (".", str(root)):
                with self.subTest(spelling=spelling):
                    observed = json.loads(observer.observe([spelling], caps, form))
                    self.assertIsNone(observed["incomplete"])
        finally:
            os.chdir(here)

    def test_a_new_distribution_in_scope_changes_the_observation(self) -> None:
        # C6 kept under E1: adding a distribution whose in-root rows match, with an
        # outside console script, changes a complete observation rather than making it
        # unavailable (Router #389 6361519666).
        root = Path(self.directory.name) / "growing"
        root.mkdir()
        (root / "a.py").write_text("", encoding="utf-8")
        before = self._observe_with(root)
        shutil.rmtree(root)
        self._recorded_root("growing", f"../bin/mm,sha256={self._claim(b'x')},1")
        after = self._observe_with(root)
        self.assertIsNone(before["incomplete"])
        self.assertIsNone(after["incomplete"])
        self.assertNotEqual(before["distributions"], after["distributions"])

    def test_the_record_check_refuses_what_it_cannot_parse_or_reach(self) -> None:
        # Kill tests (round 1: G7, G9, G12, G14): a row of one field, a RECORD that is
        # not UTF-8, a digest valid only when decoded leniently, and a listed file
        # reached through a linked directory all stop the observation.
        module = b'VALUE: str = "s"\n'
        with self.subTest("a row of one field"):
            root = self._recorded_root("one-field", "mm/__init__.py")
            self.assertEqual("record_malformed", self._observe_with(root)["incomplete"])
        with self.subTest("a RECORD with lone-CR row endings"):
            # Characterization (CodeAnt on #453): lines split on LF only, as the
            # StringIO iteration they replace split them, so lone-CR rows were and stay
            # malformed.
            root = self._recorded_root("lone-cr")
            record = root / "mm-1.0.dist-info" / "RECORD"
            record.write_bytes(record.read_bytes().replace(b"\n", b"\r"))
            self.assertEqual("record_malformed", self._observe_with(root)["incomplete"])
        with self.subTest("a RECORD ending inside a character"):
            root = self._recorded_root("truncated-utf8")
            record = root / "mm-1.0.dist-info" / "RECORD"
            record.write_bytes(record.read_bytes() + "é".encode()[:1])
            self.assertEqual("record_malformed", self._observe_with(root)["incomplete"])
        with self.subTest("a RECORD that is not UTF-8"):
            root = self._recorded_root("not-utf8")
            record = root / "mm-1.0.dist-info" / "RECORD"
            record.write_bytes(record.read_bytes() + b"\xff,,\n")
            self.assertEqual("record_malformed", self._observe_with(root)["incomplete"])
        with self.subTest("a digest valid only when decoded leniently"):
            lenient = self._claim(module)[:10] + "!!" + self._claim(module)[10:]
            root = self._recorded_root("lenient", f"mm/__init__.py,sha256={lenient},17")
            self.assertEqual("record_malformed", self._observe_with(root)["incomplete"])
        with self.subTest("a listed file reached through a linked directory"):
            root = self._recorded_root("linked-dir")
            elsewhere = Path(self.directory.name) / "elsewhere-dir"
            elsewhere.mkdir()
            (elsewhere / "x.py").write_bytes(module)
            (root / "mm" / "sub").symlink_to(elsewhere, target_is_directory=True)
            row = f"mm/sub/x.py,sha256={self._claim(module)},{len(module)}"
            record = root / "mm-1.0.dist-info" / "RECORD"
            record.write_text(
                row + "\n" + record.read_text(encoding="utf-8"), encoding="utf-8"
            )
            self.assertEqual("unreadable", self._observe_with(root)["incomplete"])

    def test_an_alias_through_a_linked_root_is_ambiguous(self) -> None:
        # Kill test for the real-root comparison: observed through a link to the root,
        # a row written to leave the link and come back into the real root is an alias,
        # never "outside" (Router #389 6361519666).
        real = self._recorded_root("real-root")
        link = Path(self.directory.name) / "link-root"
        link.symlink_to(real, target_is_directory=True)
        record = real / "mm-1.0.dist-info" / "RECORD"
        row = f"../real-root/mm/__init__.py,sha256={self._claim(b'x')},1"
        record.write_text(
            row + "\n" + record.read_text(encoding="utf-8"), encoding="utf-8"
        )
        observed = self._observe_with(link)
        self.assertEqual("record_ambiguous_path", observed["incomplete"])

    def test_a_report_that_cannot_be_read_is_a_gap(self) -> None:
        # Characterization: a read of the observation's own report that fails is an
        # unavailable observation, never an escaping error.
        original = Path.read_bytes

        def failing(path):
            if path.name.startswith("diagnostic-environment-"):
                raise OSError("unreadable report")
            return original(path)

        with patch.object(Path, "read_bytes", failing):
            inventory = self._run(self._environment(("fixture-1.0",)), "import-untyped")
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])

    # D-U: the entries of RECORD-owned directories that no RECORD lists (#389
    # F3-S2-DU-HOUT-FINAL-PROOF; Router 6373641379, H-out). Each test below names its
    # pre-change evidence mode.

    def _unlisted_root(self, name: str, extra: bytes = b'VALUE: str = "s"\n') -> Path:
        """The typed `mm` root, with mm/extra.py, which no RECORD lists."""
        root = self._recorded_root(name)
        (root / "mm" / "extra.py").write_bytes(extra)
        return root

    def _walk_caps(self, **overrides: int) -> dict:
        return {**self.module.ENVIRONMENT_OBSERVATION_CAPS, **overrides}

    def test_a_file_no_record_lists_changes_the_observation(self) -> None:
        # RED: the probe's class (#389 6372454439). The same root, names, version and
        # RECORD, with only mm/extra.py's bytes changed, are two observations; the same
        # bytes observed twice are one.
        root = self._unlisted_root("unlisted")
        first, repeated = self._observe_with(root), self._observe_with(root)
        (root / "mm" / "extra.py").write_bytes(b"VALUE: int = 1\n")
        changed = self._observe_with(root)
        self.assertEqual(first, repeated)
        self.assertIsNone(changed["incomplete"])
        self.assertNotEqual(first, changed)
        digest = hashlib.sha256(b"VALUE: int = 1\n").hexdigest()
        self.assertEqual(
            [[str(root), "mm/extra.py", "file", digest]], changed.get("unlisted")
        )

    def test_an_unlisted_entry_is_recorded_by_its_kind_and_never_followed(self) -> None:
        # RED: a link is recorded by its target and never followed, and anything but a
        # regular file or a link is recorded without being opened.
        root = self._recorded_root("unlisted-kinds")
        target = Path(self.directory.name) / "unlisted-target.py"
        target.write_text("VALUE = 1\n", encoding="utf-8")
        (root / "mm" / "alias.py").symlink_to(target)
        (root / "mm" / "tree").symlink_to(self.directory.name, target_is_directory=True)
        os.mkfifo(root / "mm" / "pipe")
        observed = self._observe_with(root)
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(
            [
                [str(root), "mm/alias.py", "link", str(target)],
                [str(root), "mm/pipe", "other", None],
                [str(root), "mm/tree", "link", self.directory.name],
            ],
            observed.get("unlisted"),
        )

    def test_a_file_a_record_lists_without_a_hash_stays_unobserved(self) -> None:
        # RED: H-out. A listed path is never an unlisted entry, hashed or not; a
        # hashless row's bytes stay the named residual, as pip lists compiled files.
        root = self._recorded_root("hashless", "mm/__pycache__/x.cpython-312.pyc,,")
        (root / "mm" / "__pycache__").mkdir()
        (root / "mm" / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"compiled")
        observed = self._observe_with(root)
        self.assertIsNone(observed["incomplete"])
        self.assertEqual([], observed.get("unlisted"))

    def test_each_walk_cap_holds_at_its_bound_and_stops_past_it(self) -> None:
        # RED: each count at its bound and one past it, over the typed root's own
        # walk: 2 owned directories (mm, mm-1.0.dist-info), 4 entries, depth 1, 4
        # in-root rows and no unlisted entry. Rows added for files are hashless.
        def root_with(name: str, key: str, count: int) -> Path:
            if key == "tree_entries":
                files = [f"mm/f{i}.py" for i in range(count)]
                root = self._recorded_root(name, *(f"{f},," for f in files))
                for f in files:
                    (root / f).write_text("", encoding="utf-8")
            elif key == "record_rows":
                root = self._recorded_root(
                    name, *(f"mm/gone{i}.py,," for i in range(count))
                )
            else:
                root = self._recorded_root(name)
                for i in range(count):
                    if key == "tree_directories":
                        (root / "mm" / f"s{i}").mkdir()
                    elif key == "tree_depth":
                        (root / "mm" / "/".join(["d"] * (i + 1))).mkdir()
                    else:
                        (root / "mm" / f"extra{i}.py").write_text(f"V = {i}\n")
            return root

        for key, cap, start in (
            ("tree_entries", 6, 4),
            ("tree_directories", 4, 2),
            ("tree_depth", 3, 1),
            ("record_rows", 6, 4),
            ("unlisted", 2, 0),
        ):
            for added, expected in (
                (cap - start - 1, None),
                (cap - start, None),
                (cap - start + 1, key),
            ):
                with self.subTest(key=key, total=start + added):
                    root = root_with(f"cap-{key}-{added}", key, added)
                    observed = self._observe_with(
                        root, caps=self._walk_caps(**{key: cap})
                    )
                    self.assertEqual(expected, observed["incomplete"])

    def test_a_directory_is_charged_before_it_is_opened(self) -> None:
        # RED (PAO 6373356762): 80 sibling directories at a directory cap of 2 stop at
        # the cap, never holding more directories open than the walk's depth beside
        # the held root, and leave no descriptor behind.
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("needs /proc/self/fd to count descriptors")
        observer = importlib.import_module("tools.python_environment_observation")
        root = self._recorded_root("broad")
        for i in range(80):
            (root / "mm" / f"s{i:02d}").mkdir()
        real_open, real_close = os.open, os.close
        live: set[int] = set()
        peak = [0]
        opened: list[str] = []

        def counting_open(path, flags, *args, **kwargs):
            descriptor = real_open(path, flags, *args, **kwargs)
            if flags & os.O_DIRECTORY:
                live.add(descriptor)
                peak[0] = max(peak[0], len(live))
                opened.append(os.fspath(path))
            return descriptor

        def counting_close(descriptor):
            live.discard(descriptor)
            real_close(descriptor)

        before = sorted(os.listdir("/proc/self/fd"))
        with (
            patch.object(observer.os, "open", counting_open),
            patch.object(observer.os, "close", counting_close),
        ):
            observed = json.loads(
                observer.observe(
                    [str(root)],
                    self._walk_caps(tree_directories=2),
                    self.module.ENVIRONMENT_OBSERVATION_FORMAT,
                )
            )
        self.assertEqual("tree_directories", observed["incomplete"])
        # No sibling is ever opened: the second is charged when listed and kept, the
        # third stops the walk, so none is opened (Sourcery and cubic on #455).
        self.assertEqual([], [name for name in opened if name.startswith("s")])
        # At most the held root, the *.dist-info and one RECORD path component, which
        # the RECORD check opens.
        self.assertLessEqual(peak[0], 3)
        self.assertEqual(before, sorted(os.listdir("/proc/self/fd")))

    def test_one_observation_reads_one_generation_of_each_root(self) -> None:
        # RED (PAO 6373356762): a root link retargeted after the listing, or after the
        # RECORDs, leaves the observation on the root it opened first: its listing,
        # its RECORDs and its unlisted entries all come from that one directory.
        observer = importlib.import_module("tools.python_environment_observation")
        first = self._unlisted_root("generation-a", b"X = 'a'\n")
        # A RECORD that differs, so that a RECORD read from the second root shows too
        # (Sourcery on #455).
        second = self._recorded_root("generation-b", "mm/other.py,,")
        (second / "mm" / "extra.py").write_bytes(b"X = 'b'\n")
        record = first / "mm-1.0.dist-info" / "RECORD"
        opened = hashlib.sha256(record.read_bytes()).hexdigest()
        link = Path(self.directory.name) / "generation-root"
        for stage in ("_import_roots", "_distributions"):
            with self.subTest(stage):
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(first, target_is_directory=True)
                original = getattr(observer, stage)

                def retargeting(*args, original=original, **kwargs):
                    result = original(*args, **kwargs)
                    link.unlink()
                    link.symlink_to(second, target_is_directory=True)
                    return result

                with patch.object(observer, stage, retargeting):
                    observed = json.loads(
                        observer.observe(
                            [str(link)],
                            self._walk_caps(),
                            self.module.ENVIRONMENT_OBSERVATION_FORMAT,
                        )
                    )
                self.assertIsNone(observed["incomplete"])
                self.assertEqual(
                    [hashlib.sha256(b"X = 'a'\n").hexdigest()],
                    [entry[3] for entry in observed.get("unlisted") or []],
                )
                self.assertEqual(
                    [opened], [digest for _, _, digest in observed["distributions"]]
                )

    def test_a_walk_that_cannot_read_a_directory_stops_the_observation(self) -> None:
        # RED: an owned top that is a link, a subdirectory replaced by a link after it
        # was listed, and an unreadable subdirectory are each unreadable.
        observer = importlib.import_module("tools.python_environment_observation")
        elsewhere = Path(self.directory.name) / "walk-elsewhere"
        elsewhere.mkdir()
        linked = self._recorded_root("walk-linked-top", "pkg/m.py,,")
        (linked / "pkg").symlink_to(elsewhere, target_is_directory=True)
        swapped = self._recorded_root("walk-swapped")
        (swapped / "mm" / "sub").mkdir()
        cases = [
            ("an owned top that is a link", linked, None),
            ("a swapped directory", swapped, "sub"),
        ]
        if os.geteuid() != 0:
            locked = self._recorded_root("walk-locked")
            (locked / "mm" / "locked").mkdir()
            (locked / "mm" / "locked").chmod(0)
            self.addCleanup((locked / "mm" / "locked").chmod, 0o755)
            cases.append(("an unreadable directory", locked, None))
        real_open = os.open
        for name, root, swap in cases:
            with self.subTest(name):

                def swapping(path, flags, *args, root=root, swap=swap, **kwargs):
                    moved = root / "mm" / swap if swap else None
                    if (
                        swap
                        and path == swap
                        and moved.is_dir()
                        and not moved.is_symlink()
                    ):
                        moved.rename(root / "mm" / "moved")
                        moved.symlink_to(
                            root / "mm" / "moved", target_is_directory=True
                        )
                    return real_open(path, flags, *args, **kwargs)

                with patch.object(observer.os, "open", swapping):
                    observed = json.loads(
                        observer.observe(
                            [str(root)],
                            self._walk_caps(),
                            self.module.ENVIRONMENT_OBSERVATION_FORMAT,
                        )
                    )
                self.assertEqual("unreadable", observed["incomplete"])

    def test_the_walk_closes_every_descriptor_on_every_exit(self) -> None:
        # Characterization at the base, a kill test once the walk exists: complete,
        # each cap's stop and an unreadable top all leave the descriptors as they were.
        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("needs /proc/self/fd to count descriptors")
        observer = importlib.import_module("tools.python_environment_observation")
        deep = self._unlisted_root("fd-walk-deep")
        (deep / "mm" / "a" / "b" / "c").mkdir(parents=True)
        linked = self._recorded_root("fd-walk-linked", "pkg/m.py,,")
        (linked / "pkg").symlink_to(deep, target_is_directory=True)
        for name, root, caps in (
            (None, deep, {}),
            ("tree_entries", deep, {"tree_entries": 3}),
            ("tree_directories", deep, {"tree_directories": 3}),
            ("tree_depth", deep, {"tree_depth": 2}),
            ("unlisted", deep, {"unlisted": 0}),
            ("record_rows", deep, {"record_rows": 2}),
            ("unreadable", linked, {}),
        ):
            with self.subTest(name or "complete"):
                before = sorted(os.listdir("/proc/self/fd"))
                observed = json.loads(
                    observer.observe(
                        [str(root)],
                        self._walk_caps(**caps),
                        self.module.ENVIRONMENT_OBSERVATION_FORMAT,
                    )
                )
                # The exit taken, then the cleanup after it (Sourcery on #455).
                self.assertEqual(name, observed["incomplete"])
                self.assertEqual(before, sorted(os.listdir("/proc/self/fd")))

    def test_a_later_observation_runs_on_the_remaining_deadline_only(self) -> None:
        # Characterization (Router 6373641379 item 3), green before D-U too: every
        # launch gets the inventory's one absolute deadline. The producers are faked;
        # the launcher's stand-in spends the budget itself, waiting until at most 0.1 s
        # remains, and then starts the after-observation, the real observer through the
        # real launcher, with what remains. It is cut there and leaves no process: the
        # member is unavailable and no fresh budget is ever granted. The child sleeps
        # before the observer's own code, so that it always needs longer than what
        # remains: the cut is the launcher's, the same for any child. A synthetic spent
        # budget, not a run of the real producers.
        real = self.module._bounded_run
        marker = f"# remaining-deadline-{os.getpid()}-{time.monotonic_ns()}"
        launches: list[tuple[bool, float]] = []
        after: dict[str, float] = {}

        def run(command, *, cwd, environment, report, deadline, limits):
            observation = command == self._observation_command()
            launches.append((observation, deadline))
            if not observation or len([o for o, _ in launches if o]) == 1:
                if observation:
                    report.write_text(self._observation(), encoding="utf-8")
                    return 0, None, False
                return self._fake_run(
                    command,
                    cwd=cwd,
                    environment=environment,
                    report=report,
                    deadline=deadline,
                    limits=limits,
                )
            time.sleep(max(0.0, deadline - time.monotonic() - 0.1))
            after["remaining"] = deadline - time.monotonic()
            source = Path(command[2]).read_text(encoding="utf-8")
            prefix = f"{marker}\nimport time\ntime.sleep(30)\n"
            started = time.monotonic()
            outcome = real(
                [*command[:2], "-c", prefix + source, *command[3:]],
                cwd=cwd,
                environment=environment,
                report=report,
                deadline=deadline,
                limits=limits,
            )
            after["seconds"] = time.monotonic() - started
            return outcome

        self.mypy_records = {"tests/test_sample.py": []}
        limits = dataclasses.replace(
            self.module.DEFAULT_DIAGNOSTIC_LIMITS, timeout_seconds=3.0
        )
        started = time.monotonic()
        with patch("tools.quality_evidence._bounded_run", side_effect=run):
            inventory = self._read(self.collect(self.root, self.output, limits=limits))
        self.assertLess(time.monotonic() - started, 3.0 + 10)
        self.assertEqual(1, len({deadline for _, deadline in launches}))
        self.assertLessEqual(after["remaining"], 0.1)
        self.assertLess(after["seconds"], 10)
        member = inventory["producers"][0]["environment_observation"]
        self.assertEqual("unavailable", member["status"])
        self.assertIsNone(member["after"])
        for entry in os.listdir("/proc") if os.path.isdir("/proc") else ():
            if entry.isdigit():
                try:
                    cmdline = (Path("/proc") / entry / "cmdline").read_bytes()
                except OSError:
                    continue
                self.assertNotIn(marker.encode(), cmdline)

    def test_a_directory_with_nothing_beneath_it_is_an_unlisted_entry(self) -> None:
        # RED (Octopus, Sourcery and CodeAnt on #455): an empty directory no RECORD
        # implies, such as a namespace portion, is recorded as one entry, its deepest
        # empty directory; a directory holding a listed file or an unlisted entry
        # already shows, and is not recorded again.
        root = self._recorded_root("empty-dirs", "mm/held/x.py,,")
        (root / "mm" / "held").mkdir()
        (root / "mm" / "held" / "x.py").write_text("", encoding="utf-8")
        (root / "mm" / "sub").mkdir()
        (root / "mm" / "deep" / "er").mkdir(parents=True)
        observed = self._observe_with(root)
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(
            [
                [str(root), "mm/deep/er", "directory", None],
                [str(root), "mm/sub", "directory", None],
            ],
            observed.get("unlisted"),
        )
        (root / "mm" / "sub").rmdir()
        self.assertNotEqual(observed, self._observe_with(root))

    def test_a_row_that_is_not_a_plain_in_root_path_lists_nothing(self) -> None:
        # Characterization (Sourcery on #455): a hashless row spelled other than as a
        # plain in-root path names no file the walk may skip, so a file named only that
        # way is recorded as unlisted: more is observed, never less.
        root = self._recorded_root("spelled", "./mm/extra.py,,")
        (root / "mm" / "extra.py").write_text("V = 1\n", encoding="utf-8")
        observed = self._observe_with(root)
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(
            [
                [
                    str(root),
                    "mm/extra.py",
                    "file",
                    hashlib.sha256(b"V = 1\n").hexdigest(),
                ]
            ],
            observed.get("unlisted"),
        )

    def test_every_record_row_path_is_charged_to_the_string_cap(self) -> None:
        # RED (Sourcery on #455): a row's path is a string the observer holds, so one
        # longer than string_bytes stops the observation, hashless or not.
        root = self._recorded_root("long-row", f"mm/{'x' * 5000}.py,,")
        observed = self._observe_with(root)
        self.assertEqual("string_bytes", observed["incomplete"])

    def test_a_zero_depth_opens_no_owned_directory(self) -> None:
        # RED (CodeAnt on #455): an owned directory is depth 1, checked before it is
        # opened like any other.
        observed = self._observe_with(
            self._recorded_root("zero-depth"), caps=self._walk_caps(tree_depth=0)
        )
        self.assertEqual("tree_depth", observed["incomplete"])

    def test_a_root_named_twice_is_walked_once(self) -> None:
        # RED (cubic on #455): the same root string twice on the import path is one
        # directory, opened once, so its owned directories are walked once: one entry,
        # charged once. Different spellings of one directory stay a residual.
        root = self._unlisted_root("twice")
        observed = self._observe_with(root, root, caps=self._walk_caps(unlisted=1))
        self.assertIsNone(observed["incomplete"])
        self.assertEqual(1, len(observed.get("unlisted") or []))

    def test_an_empty_owned_directory_shows_through_the_root_entries(self) -> None:
        # Characterization (Claude on #455): an owned top-level directory, even an
        # empty one owned only through a hashless row whose file is absent, is never an
        # unlisted entry; its name is one of the root's entries, so adding or removing
        # it still changes the observation.
        root = self._recorded_root("empty-top", "empty/missing.py,,")
        (root / "empty").mkdir()
        observed = self._observe_with(root)
        self.assertIsNone(observed["incomplete"])
        self.assertIn("empty", observed["entries"][str(root)])
        self.assertEqual([], observed["unlisted"])
        (root / "empty").rmdir()
        self.assertNotEqual(observed, self._observe_with(root))
