"""#389 F3 S2 B: the diagnostic inventory analyzes the frozen commit's exact tree,
staged privately through the shared exact-tree owner, never the checkout, its index
or a later HEAD (Router 6324876845; D1-D4 selected in 6325382720)."""

from __future__ import annotations

import dataclasses
import importlib
import math
import os
import shutil
import subprocess  # nosec B404 -- test-only: drives git on temporary fixture repositories
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from quality_evidence_fixtures import (
    _EXTRA_COMPLEX,
    _diagnostic_line,
    _DiagnosticFixture,
    _fixture_git_env,
)


class ExactSourceTreeTests(_DiagnosticFixture):
    """#389 F3 S2 B (Router 6324876845): the producers analyze the frozen commit's exact
    tree, staged privately through the shared exact-tree owner, never the caller's
    checkout, its index or a later HEAD. RED first, on main d617c21e."""

    def _extra_line(self) -> int:
        return _diagnostic_line(
            self.files["tools/sample.py"] + _EXTRA_COMPLEX, "def extra"
        )

    def _complexity(self, inventory: dict, line: int) -> list[dict]:
        return self._find(inventory, "complexity", "cc", "tools/sample.py", line)

    # A dirty, uncommitted edit to a tracked file is not the named source.
    def test_a_dirty_tracked_edit_is_not_analyzed(self) -> None:
        (self.root / "tools" / "sample.py").write_text(
            self.files["tools/sample.py"] + _EXTRA_COMPLEX, encoding="utf-8"
        )
        inventory = self._read(self.collect(self.root, self.output))
        self.assertEqual([], self._complexity(inventory, self._extra_line()))
        self.assertTrue(self._complexity(inventory, self.lines["branchy"]))

    # An edit the index hides from git status is not the named source either.
    def test_an_index_hidden_edit_is_not_analyzed(self) -> None:
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                (self.root / "tools" / "sample.py").write_text(
                    self.files["tools/sample.py"] + _EXTRA_COMPLEX, encoding="utf-8"
                )
                self._git("update-index", flag, "tools/sample.py")
                self.assertEqual(
                    "", self._git("status", "--porcelain", "--untracked-files=no")
                )
                inventory = self._read(self.collect(self.root, self.output))
                self.assertEqual([], self._complexity(inventory, self._extra_line()))
                self._git(
                    "update-index", flag.replace("--", "--no-"), "tools/sample.py"
                )
                self._git("checkout", "--", "tools/sample.py")

    # An untracked module in the checkout cannot shape a tracked diagnostic: the staged
    # source holds only the tree (the inverse of the earlier stated limit).
    def test_an_untracked_module_cannot_shape_a_tracked_diagnostic(self) -> None:
        (self.root / "tools" / "uses_injected.py").write_text(
            "from injected import f\n\nx: str = f()\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a tracked import")
        rules, ran = {}, False
        for label in ("without", "with"):
            if label == "with":
                (self.root / "injected.py").write_text(
                    "def f() -> int:\n    return 1\n", encoding="utf-8"
                )
            inventory = self._read(self.collect(self.root, self.output))
            # The narrower residual stays stated (Router #389 6325382720, D1).
            self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
            self.assertIn(
                "import graph is not proven confined", inventory["coverage"]["reason"]
            )
            rules[label] = {
                f.get("rule")
                for f in inventory["findings"]
                if f["path"] == "tools/uses_injected.py" and f["tool"]["id"] == "mypy"
            }
            ran = ran or any(
                p["invocation"].split(":")[0] == "mypy" and p.get("version")
                for p in inventory["producers"]
            )
        if not ran:
            self.skipTest("mypy does not run in this image")
        self.assertEqual(rules["without"], rules["with"])

    # The comparison is the frozen commit's against its base, even when HEAD moves on
    # during collection.
    def test_the_diff_is_the_frozen_commits_not_a_later_heads(self) -> None:
        (self.root / "tools" / "sample.py").write_text(
            self.files["tools/sample.py"] + "\n# the frozen change\n", encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "the frozen commit")
        real = self.module._run_complexity

        def moving(*args, **kwargs):
            (self.root / "tests" / "test_sample.py").write_text(
                self.files["tests/test_sample.py"] + "\n# later\n", encoding="utf-8"
            )
            self._git("commit", "-q", "-am", "a later HEAD")
            return real(*args, **kwargs)

        with patch.object(self.module, "_run_complexity", side_effect=moving):
            inventory = self._read(self.collect(self.root, self.output, base=self.base))
        self.assertIsNotNone(inventory["scope"]["diff"])
        self.assertEqual(
            ["tools/sample.py"], inventory["scope"]["diff"]["changed_paths"]
        )

    # The lines each finding is compared against are the frozen commit's patch, never
    # a later HEAD's: a later commit that removes the frozen change leaves it in_diff.
    def test_the_patch_lines_are_the_frozen_commits(self) -> None:
        (self.root / "tools" / "sample.py").write_text(
            self.files["tools/sample.py"] + _EXTRA_COMPLEX, encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "the frozen change")
        real = self.module._run_complexity

        def reverting(*args, **kwargs):
            (self.root / "tools" / "sample.py").write_text(
                self.files["tools/sample.py"] + "\n# later\n", encoding="utf-8"
            )
            self._git("commit", "-q", "-am", "a later HEAD without it")
            return real(*args, **kwargs)

        with patch.object(self.module, "_run_complexity", side_effect=reverting):
            inventory = self._read(self.collect(self.root, self.output, base=self.base))
        (extra,) = self._complexity(inventory, self._extra_line())
        self.assertIs(True, extra["native"]["in_diff"])

    # A staged source that changes while the producers read it is refused, never
    # published as the tree's evidence.
    def test_a_changed_staged_source_is_refused(self) -> None:
        real = self.module._run_complexity

        def mutating(root, paths, *args, **kwargs):
            with open(Path(root) / "tools" / "sample.py", "a", encoding="utf-8") as f:
                f.write("\n# changed\n")
            return real(root, paths, *args, **kwargs)

        with patch.object(self.module, "_run_complexity", side_effect=mutating):
            with self.assertRaises(self.module.QualityEvidenceError) as raised:
                self.collect(self.root, self.output)
        self.assertIn("staged source", str(raised.exception))

    # The tree is staged within the collector's own absolute deadline, never a fresh
    # budget of the owner's.
    def test_staging_shares_the_collectors_deadline(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        real, seen = owner.materialize, []

        def staging(*args, **kwargs):
            seen.append(kwargs["limits"])
            return real(*args, **kwargs)

        start = time.monotonic()
        limits = self.module.DiagnosticLimits(timeout_seconds=123.0)
        with patch.object(owner, "materialize", side_effect=staging):
            self.collect(self.root, self.output, limits=limits)
        self.assertEqual(1, len(seen))
        self.assertGreaterEqual(seen[0].deadline, start + 123.0)
        self.assertLessEqual(seen[0].deadline, time.monotonic() + 123.0)

    # The whole tree has its own finite file bound, at the cap and past it, apart from
    # max_files, which still counts the Python inputs.
    def test_the_whole_tree_has_its_own_file_bound(self) -> None:
        total = len(self.files)
        at_cap = self.module.DiagnosticLimits(max_tree_files=total)
        inventory = self._read(self.collect(self.root, self.output, limits=at_cap))
        self.assertTrue(self._complexity(inventory, self.lines["branchy"]))
        past = self.module.DiagnosticLimits(max_tree_files=total - 1)
        inventory = self._read(self.collect(self.root, self.output, limits=past))
        self.assertEqual([], [f for f in inventory["findings"]])
        self.assertIn("cap-files", inventory["coverage"]["reason"])

    # A filter driver the repository configures never runs during collection.
    def test_a_configured_driver_never_runs(self) -> None:
        marker = Path(self.directory.name) / "driver-ran"
        command = f"sh -c 'touch {marker}; cat'"
        self._git("config", "filter.probe.clean", command)
        self._git("config", "filter.probe.smudge", command)
        info = self.root / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("*.py filter=probe\n", encoding="utf-8")
        later = time.time() + 10
        os.utime(self.root / "tools" / "sample.py", (later, later))
        marker.unlink(missing_ok=True)
        self.collect(self.root, self.output)
        self.assertFalse(marker.exists())

    def _promisor(self, marker: Path) -> tuple[str, str]:
        """A partial clone whose HEAD tracks a Python file by a missing blob, its base
        the same path's real bytes, and a promisor whose configured command only leaves
        `marker` (PAO 6325156914)."""

        def git(*args: str, stdin: bytes) -> str:
            return (
                subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on a temporary fixture repository
                    [
                        "git",
                        "-c",
                        "user.name=diagnostic",
                        "-c",
                        "user.email=diagnostic@example.invalid",
                        *args,
                    ],
                    cwd=self.root,
                    env=_fixture_git_env(),
                    input=stdin,
                    check=True,
                    capture_output=True,
                )
                .stdout.decode()
                .strip()
            )

        real = git("hash-object", "-w", "--stdin", stdin=b"VALUE = 1\n")
        base_tree = git("mktree", stdin=f"100644 blob {real}\tf.py\n".encode())
        head_tree = git(
            "mktree", "--missing", stdin=f"100644 blob {'1' * 40}\tf.py\n".encode()
        )
        base = git("commit-tree", base_tree, "-m", "base", stdin=b"")
        head = git("commit-tree", head_tree, "-p", base, "-m", "head", stdin=b"")
        self._git("update-ref", "HEAD", head)
        for key, value in (
            ("core.repositoryformatversion", "1"),
            ("extensions.partialClone", "o"),
            ("remote.o.url", str(self.root)),
            ("remote.o.promisor", "true"),
            ("remote.o.uploadpack", f"touch {marker}; false"),
            ("protocol.file.allow", "always"),
        ):
            self._git("config", key, value)
        return base, head

    # No diagnostic Git read fetches: the missing object is refused, and the
    # repository's configured promisor command never runs (PAO 6325156914).
    def test_a_diagnostic_read_fetches_no_missing_object(self) -> None:
        marker = Path(self.directory.name) / "fetched"
        self._promisor(marker)
        with self.assertRaises(subprocess.CalledProcessError):
            self.module._diagnostic_git(
                self.root, time.monotonic() + 60, "cat-file", "-p", "1" * 40
            )
        self.assertFalse(marker.exists())

    # The whole chain, with a base to compare: staging, enumeration and the
    # comparison's patch read all refuse the missing object, and none fetches it.
    def test_the_collection_fetches_no_missing_object(self) -> None:
        marker = Path(self.directory.name) / "fetched"
        base, _ = self._promisor(marker)
        self.collect(self.root, self.output, base=base)
        self.assertFalse(marker.exists())

    # Export attributes change nothing: the staged bytes are the committed ones (a
    # characterization, as the owner guarantees).
    def test_export_attributes_leave_the_committed_bytes(self) -> None:
        (self.root / ".gitattributes").write_text(
            "tools/sample.py export-subst export-ignore\n", encoding="utf-8"
        )
        (self.root / "tools" / "sample.py").write_text(
            "# $Format:%H$\n" + self.files["tools/sample.py"], encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "export attributes")
        inventory = self._read(self.collect(self.root, self.output))
        self.assertTrue(self._complexity(inventory, self.lines["branchy"] + 1))


class SelectedSourceContractTests(_DiagnosticFixture):
    """#389 F3 S2 B, the contract the Router selected (6325382720, D1-D4 and the no-fetch
    policy). RECONSTRUCTED pre-change evidence: written after the first production
    edit and run against the prior subject d617c21e, never test-first (chronology
    record 6325643085)."""

    _TREE_LIMITS = ("max_tree_files", "max_tree_bytes")

    def _has_tree_limits(self) -> None:
        names = {
            field.name for field in dataclasses.fields(self.module.DiagnosticLimits)
        }
        for name in self._TREE_LIMITS:
            self.assertIn(name, names)

    def _spawns(self) -> tuple[list[list[str]], Any]:
        """Every child started under the patch, by its argv."""
        started: list[list[str]] = []
        real = subprocess.Popen

        def recording(argv, *args, **kwargs):
            started.append([str(part) for part in argv])
            return real(argv, *args, **kwargs)

        return started, patch("subprocess.Popen", side_effect=recording)

    @staticmethod
    def _python(inventory: dict) -> list[str]:
        return inventory["scope"]["full"]["expected"]

    @staticmethod
    def _unanalyzed(inventory: dict) -> list[str]:
        return [u["path"] for u in inventory["scope"]["full"]["unanalyzed"]]

    def _tracked_python(self) -> list[str]:
        return sorted(p for p in self.files if p.endswith(".py"))

    # D1: an explicit v2 record of the frozen commit, its tree and the staged
    # identity; the checkout's dirty state is never read, and the source binding stays
    # UNVERIFIED with its residual.
    def test_the_record_is_v2_and_binds_the_staged_tree(self) -> None:
        inventory = self._read(self.collect(self.root, self.output))
        self.assertEqual("gnostoa-diagnostic-inventory/v2", inventory["schema"])
        head = self._git("rev-parse", "HEAD")
        tree = self._git("rev-parse", "HEAD^{tree}")
        self.assertEqual(
            {
                "revision": head,
                "tree": tree,
                "staged_identity": tree,
                "tree_binding": "EXACT_TREE_STAGED",
                "expected_revision": None,
                "source_binding": "UNVERIFIED",
            },
            inventory["source"],
        )
        reason = inventory["coverage"]["reason"]
        self.assertIn("source binding UNVERIFIED", reason)
        self.assertNotIn("dirty", reason)
        runs = sorted(self.output.glob("diagnostic-*"))
        self.assertEqual(1, len(runs))
        self.assertFalse((runs[0] / "source").exists())

    # D2: the whole tree's bytes have their own bound, at the cap and past it.
    def test_the_whole_tree_has_its_own_byte_bound(self) -> None:
        self._has_tree_limits()
        total = sum(len(text.encode("utf-8")) for text in self.files.values())
        at_cap = self.module.DiagnosticLimits(max_tree_bytes=total)
        inventory = self._read(self.collect(self.root, self.output, limits=at_cap))
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])
        for run in self.output.glob("diagnostic-*"):
            shutil.rmtree(run)
        past = self.module.DiagnosticLimits(max_tree_bytes=total - 1)
        inventory = self._read(self.collect(self.root, self.output, limits=past))
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
        self.assertIsNone(inventory["source"]["staged_identity"])
        self.assertIn("cap-bytes", inventory["coverage"]["reason"])
        self.assertEqual([], inventory["producers"])
        self.assertEqual(self._tracked_python(), self._unanalyzed(inventory))

    # D2: each tree limit is an exact non-negative integer, refused before any work
    # otherwise, and the effective limits are recorded.
    def test_the_tree_limits_are_validated_and_recorded(self) -> None:
        self._has_tree_limits()
        for name in self._TREE_LIMITS:
            for value in (True, 1.5, -1, math.inf, "1"):
                with self.subTest(name=name, value=value):
                    started, spawning = self._spawns()
                    limits = self.module.DiagnosticLimits(**{name: value})
                    with (
                        spawning,
                        self.assertRaises(self.module.QualityEvidenceError) as raised,
                    ):
                        self.collect(self.root, self.output, limits=limits)
                    self.assertIn(name, str(raised.exception))
                    self.assertEqual([], started)
        limits = self.module.DiagnosticLimits(max_tree_files=4321, max_tree_bytes=98765)
        inventory = self._read(self.collect(self.root, self.output, limits=limits))
        recorded = inventory["configuration"]["limits"]
        self.assertEqual(
            (4321, 98765), (recorded["max_tree_files"], recorded["max_tree_bytes"])
        )
        default = self.module.DEFAULT_DIAGNOSTIC_LIMITS
        self.assertEqual(
            (200_000, 4 << 30), (default.max_tree_files, default.max_tree_bytes)
        )

    # D2 and D3: a zero file bound refuses the enumeration itself, so the tracked set
    # stays unknown (null, never an invented set), and nothing is staged or run.
    def test_a_zero_tree_bound_leaves_the_set_unknown_and_stages_nothing(self) -> None:
        self._has_tree_limits()
        owner = importlib.import_module("tools.exact_tree")
        with patch.object(owner, "materialize", side_effect=AssertionError("staged")):
            inventory = self._read(
                self.collect(
                    self.root,
                    self.output,
                    limits=self.module.DiagnosticLimits(max_tree_files=0),
                )
            )
        self.assertIsNone(self._python(inventory))
        self.assertEqual([], self._unanalyzed(inventory))
        self.assertIn("cap-files", inventory["coverage"]["reason"])
        self.assertEqual([], inventory["producers"])
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])

    # D2: a budget spent by the enumeration starts no later child: no stage, no
    # identity read and no producer.
    def test_a_budget_spent_at_the_enumeration_starts_no_later_child(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        real, called = owner.tree_paths, []
        started, spawning = self._spawns()

        def spending(*args, **kwargs):
            answer = real(*args, **kwargs)
            called.append(len(started))
            while time.monotonic() <= kwargs["limits"].deadline:
                time.sleep(0.05)
            return answer

        limits = self.module.DiagnosticLimits(timeout_seconds=3.0)
        with spawning, patch.object(owner, "tree_paths", side_effect=spending):
            inventory = self._read(self.collect(self.root, self.output, limits=limits))
        self.assertEqual(1, len(called))
        self.assertEqual(called[0], len(started))
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
        self.assertIn("deadline", inventory["coverage"]["reason"])
        self.assertEqual(self._tracked_python(), self._unanalyzed(inventory))

    # The no-fetch policy is the owner's: one that cannot be read, or no longer
    # refuses every transport and lazy fetch, fails closed, before any child.
    def test_an_unavailable_no_fetch_policy_fails_closed(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        cases = {
            "a transport allowed": {"GIT_ALLOW_PROTOCOL": "file"},
            "lazy fetch allowed": {"GIT_NO_LAZY_FETCH": ""},
            # Git reads "0" as false: a lazy fetch allowed again (Router 6325382720
            # names the exact values, "" and "1").
            "lazy fetch re-enabled": {"GIT_NO_LAZY_FETCH": "0"},
            "a transport list": {"GIT_ALLOW_PROTOCOL": "file:ssh"},
        }
        for label, change in cases.items():
            with self.subTest(label):
                started, spawning = self._spawns()
                with patch.dict(owner._GIT_ENV, change), spawning:
                    with self.assertRaises((OSError, ValueError)) as raised:
                        self.module._diagnostic_git(
                            self.root, time.monotonic() + 60, "rev-parse", "HEAD"
                        )
                self.assertIn("no-fetch policy", str(raised.exception))
                self.assertEqual([], started)
        with self.subTest("the owner cannot be imported"):
            started, spawning = self._spawns()
            with patch.dict(sys.modules, {"tools.exact_tree": None}), spawning:
                with self.assertRaises((OSError, ValueError)) as raised:
                    self.module._diagnostic_git(
                        self.root, time.monotonic() + 60, "rev-parse", "HEAD"
                    )
            self.assertIn("no-fetch policy", str(raised.exception))
            self.assertEqual([], started)
        self.assertEqual("", owner._GIT_ENV["GIT_ALLOW_PROTOCOL"])
        self.assertEqual("1", owner._GIT_ENV["GIT_NO_LAZY_FETCH"])

    # The collection's missing object is refused by the stage, and nothing is fetched
    # (PAO 6325156914: a failed read alone proves no absence of a side effect).
    def test_a_missing_object_is_refused_by_the_stage(self) -> None:
        marker = Path(self.directory.name) / "fetched"
        base, _ = ExactSourceTreeTests._promisor(self, marker)
        inventory = self._read(self.collect(self.root, self.output, base=base))
        self.assertFalse(marker.exists())
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
        self.assertIn(
            "the source tree cannot be staged: git-failed",
            inventory["coverage"]["reason"],
        )
        self.assertEqual(["f.py"], self._unanalyzed(inventory))
        self.assertEqual([], inventory["producers"])

    # D3: a stage the owner refuses, of a known set, names every tracked Python file
    # unanalyzed with the owner's code; no producer runs and no staged tree is claimed.
    def test_a_refused_stage_of_a_known_set_runs_nothing(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        refusal = owner.ExactTreeError("unsupported-entry", "a probe")
        with patch.object(owner, "materialize", side_effect=refusal):
            inventory = self._read(self.collect(self.root, self.output))
        self.assertEqual(self._tracked_python(), self._python(inventory))
        self.assertEqual(self._tracked_python(), self._unanalyzed(inventory))
        self.assertIn(
            "the source tree cannot be staged: unsupported-entry",
            inventory["coverage"]["reason"],
        )
        self.assertEqual([], inventory["producers"])
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
        self.assertIsNone(inventory["source"]["staged_identity"])
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])

    # D1 and D3: the staged identity is observed independently; one that differs from
    # the frozen tree is no stage, and one that cannot be observed again after the
    # producers certifies no staged tree.
    def test_the_staged_identity_must_match_before_and_after(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        real = owner.observed_tree
        cases = {
            "differs": ("the source tree cannot be staged: tree-mismatch", 1),
            "unobservable at first": (
                "the source tree cannot be staged: identity-unavailable",
                1,
            ),
            "unobservable after": ("the staged source could not be observed again", 2),
        }
        for label, (gap, count) in cases.items():
            with self.subTest(label):
                calls: list[int] = []

                def observing(*args, _label=label, _calls=calls, **kwargs):
                    _calls.append(1)
                    if _label == "differs":
                        return "0" * 40
                    if _label == "unobservable at first" or len(_calls) > 1:
                        raise owner.ExactTreeError("identity-unavailable")
                    return real(*args, **kwargs)

                with patch.object(owner, "observed_tree", side_effect=observing):
                    inventory = self._read(self.collect(self.root, self.output))
                self.assertEqual(count, len(calls))
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                self.assertIsNone(inventory["source"]["staged_identity"])
                self.assertIn(gap, inventory["coverage"]["reason"])
                self.assertEqual([], list(self.output.glob("*/source")))
                for run in self.output.glob("diagnostic-*"):
                    shutil.rmtree(run)

    # D4: an answer that is not exactly one full object id freezes nothing.
    def test_a_freeze_answer_that_is_not_one_full_id_freezes_nothing(self) -> None:
        real = self.module._diagnostic_git
        for label, answer in (
            ("two answers", lambda text: text + text),
            ("no id", lambda _text: "not an object id\n"),
            ("a short id", lambda text: text[:12] + "\n"),
        ):
            with self.subTest(label):

                def answering(root, deadline, *arguments, _answer=answer, **options):
                    return _answer(real(root, deadline, *arguments, **options))

                with patch.object(
                    self.module, "_diagnostic_git", side_effect=answering
                ):
                    commit, tree, gaps = self.module._frozen_subject(
                        self.root, None, time.monotonic() + 60
                    )
                self.assertEqual((None, None), (commit, tree))
                self.assertEqual(
                    [
                        "cannot freeze the subject's commit: "
                        "the answer is not one full object id"
                    ],
                    gaps,
                )

    # D4: with an expected revision, that exact commit is analyzed, never HEAD.
    def test_the_expected_commit_is_analyzed_not_head(self) -> None:
        (self.root / "tools" / "sample.py").write_text(
            self.files["tools/sample.py"] + _EXTRA_COMPLEX, encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "a later HEAD")
        inventory = self._read(
            self.collect(self.root, self.output, expected_revision=self.base)
        )
        self.assertEqual(self.base, inventory["source"]["revision"])
        self.assertEqual(self.base, inventory["source"]["expected_revision"])
        self.assertEqual(
            self._git("rev-parse", f"{self.base}^{{tree}}"), inventory["source"]["tree"]
        )
        extra = _diagnostic_line(
            self.files["tools/sample.py"] + _EXTRA_COMPLEX, "def extra"
        )
        self.assertEqual(
            [], self._find(inventory, "complexity", "cc", "tools/sample.py", extra)
        )

    # D4: an expected revision that only peels to a commit, is not one full id, or is
    # option-like binds nothing and runs nothing.
    def test_an_expected_revision_that_is_not_exactly_a_commit_binds_nothing(
        self,
    ) -> None:
        self._git("tag", "-a", "-m", "a tag", "probe")
        tag = self._git("rev-parse", "probe")
        self.assertNotEqual(self.base, tag)
        for label, expected in (
            ("an annotated tag", tag),
            ("a short id", self.base[:12]),
            ("a ref name", "HEAD"),
            ("option-like", "--output=" + str(Path(self.directory.name) / "x")),
        ):
            with self.subTest(label):
                inventory = self._read(
                    self.collect(self.root, self.output, expected_revision=expected)
                )
                self.assertIsNone(inventory["source"]["revision"])
                self.assertIsNone(inventory["source"]["tree"])
                self.assertEqual(expected, inventory["source"]["expected_revision"])
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                self.assertEqual([], inventory["producers"])
                self.assertIsNone(self._python(inventory))
                self.assertFalse((Path(self.directory.name) / "x").exists())
                formed = label == "an annotated tag"
                self.assertEqual(
                    not formed,
                    f"expected revision {expected!r} is not a full commit id"
                    in inventory["coverage"]["reason"],
                )
                for run in self.output.glob("diagnostic-*"):
                    shutil.rmtree(run)

    # D4: the tree is the frozen commit id's, never a second read of a moving HEAD.
    def test_the_tree_is_derived_from_the_frozen_commit(self) -> None:
        first = self._git("rev-parse", "HEAD")
        real = self.module._diagnostic_git
        moved = []

        def moving(root, deadline, *arguments, **kwargs):
            answer = real(root, deadline, *arguments, **kwargs)
            if not moved and "rev-parse" in arguments:
                (self.root / "tools" / "sample.py").write_text(
                    self.files["tools/sample.py"] + "\n# moved\n", encoding="utf-8"
                )
                self._git("commit", "-q", "-am", "moved between the reads")
                moved.append(1)
            return answer

        with patch.object(self.module, "_diagnostic_git", side_effect=moving):
            inventory = self._read(self.collect(self.root, self.output))
        self.assertTrue(moved)
        self.assertEqual(first, inventory["source"]["revision"])
        self.assertEqual(
            self._git("rev-parse", f"{first}^{{tree}}"), inventory["source"].get("tree")
        )
        self.assertEqual(
            inventory["source"].get("tree"), inventory["source"].get("staged_identity")
        )


class FixtureIsolationTests(_DiagnosticFixture):
    """The fixtures' own Git never reads the developer's global or system
    configuration (Revix on #450, captured for S2 B in #389 6327632965). RED first on
    main 1e4cc560."""

    def _hostile(self) -> tuple[Path, Path]:
        """A home whose global configuration runs hooks that leave a marker, and that
        marker."""
        home = Path(self.directory.name) / "home"
        hooks = home / "hooks"
        hooks.mkdir(parents=True)
        marker = Path(self.directory.name) / "hook-ran"
        for name in ("post-commit", "reference-transaction"):
            hook = hooks / name
            hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
            hook.chmod(0o755)
        (home / ".gitconfig").write_text(
            f"[core]\n\thooksPath = {hooks}\n", encoding="utf-8"
        )
        return home, marker

    def _a_change(self) -> None:
        (self.root / "tools" / "sample.py").write_text(
            self.files["tools/sample.py"] + "\n# more\n", encoding="utf-8"
        )

    # A hook that a developer's ~/.gitconfig names never runs in the fixtures' Git.
    def test_a_global_hook_never_runs_in_the_fixtures_git(self) -> None:
        home, marker = self._hostile()
        with patch.dict(
            os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}
        ):
            self._a_change()
            self._git("commit", "-q", "-am", "under a hostile home")
            ExactSourceTreeTests._promisor(self, Path(self.directory.name) / "fetched")
        self.assertFalse(marker.exists())

    # A malformed global or system configuration cannot fail or steer them either.
    def test_a_malformed_global_or_system_config_is_never_read(self) -> None:
        broken = Path(self.directory.name) / "broken.gitconfig"
        broken.write_text("[core\n", encoding="utf-8")
        home = Path(self.directory.name) / "broken-home"
        home.mkdir()
        (home / ".gitconfig").write_text("[core\n", encoding="utf-8")
        for label, change in (
            ("global", {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config")}),
            ("system", {"GIT_CONFIG_SYSTEM": str(broken)}),
        ):
            with self.subTest(label), patch.dict(os.environ, change):
                self._a_change()
                self._git("commit", "-q", "-am", f"under a broken {label} config")
                ExactSourceTreeTests._promisor(
                    self, Path(self.directory.name) / f"fetched-{label}"
                )
