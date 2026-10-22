"""#389 F3 S2 B: the diagnostic inventory analyzes the frozen commit's exact tree,
staged privately through the shared exact-tree owner, never the checkout, its index
or a later HEAD (Router 6324876845; D1-D4 selected in 6325382720)."""

from __future__ import annotations

import contextlib
import dataclasses
import errno
import importlib
import math
import os
import shlex
import shutil
import subprocess  # nosec B404 -- test-only: drives git on temporary fixture repositories
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from quality_evidence_fixtures import (
    _EXTRA_COMPLEX,
    _diagnostic_line,
    _DiagnosticFixture,
    _fixture_git_env,
)
from test_exact_tree_reuse import _open_descriptors


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
                # A failed assertion still restores the flag and the file, so the
                # next flag starts clean (Revix on #451).
                try:
                    self.assertEqual(
                        "", self._git("status", "--porcelain", "--untracked-files=no")
                    )
                    inventory = self._read(self.collect(self.root, self.output))
                    self.assertEqual(
                        [], self._complexity(inventory, self._extra_line())
                    )
                finally:
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
    # published as the tree's evidence, and the refusal names the run directory that
    # keeps the raw reports.
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
        (run,) = self.output.glob("diagnostic-*")
        self.assertIn(f"the raw reports are in {run}", str(raised.exception))

    def _refused_without_inventory(self, failing: Any) -> tuple[str, Path]:
        """Collect under `failing` (a patch), which must refuse; the refusal's text and
        its run directory, which holds the raw reports and no inventory."""
        with failing, self.assertRaises(self.module.QualityEvidenceError) as raised:
            self.collect(self.root, self.output)
        (run,) = self.output.glob("diagnostic-*")
        self.assertFalse((run / self.module.DIAGNOSTIC_INVENTORY).exists())
        self.assertTrue([p for p in run.iterdir() if p.name != "source"])
        return str(raised.exception), run

    # D3 as the Router corrected it (6332488628 on #389): a re-observation that finds
    # the staged source no longer matching, unsafe or over its bound refuses the
    # inventory, worded by its native code; an unrepresentable one, which an unknown
    # object format also raises before the staged root is read, refuses without
    # claiming a change.
    def test_a_reobservation_that_finds_no_exact_tree_refuses_the_inventory(
        self,
    ) -> None:
        owner = importlib.import_module("tools.exact_tree")
        cases = {
            "tree-mismatch": "the staged source no longer matches the frozen tree",
            "unsafe-path": "the staged source holds an unsafe path",
            "cap-files": "the staged source exceeds its file bound",
            "cap-bytes": "the staged source exceeds its byte bound",
            "unsupported-entry": (
                "unrepresentable re-observation of the staged source, change not "
                "established"
            ),
        }
        for code, reason in cases.items():
            with self.subTest(code):
                failure = owner.ExactTreeError(code, "an unknown object format")
                failing = patch.object(
                    owner,
                    "observed_tree",
                    side_effect=self._then(owner.observed_tree, failure),
                )
                message, run = self._refused_without_inventory(failing)
                self.assertIn(f"{reason}: {code};", message)
                self.assertIn(f"the raw reports are in {run}", message)
                self.assertNotIn("changed during collection", message)
                shutil.rmtree(run)

    # A special entry a producer leaves in the staged source is refused as an
    # unrepresentable re-observation, never as a demonstrated change.
    def test_a_special_entry_left_in_the_staged_source_is_refused(self) -> None:
        real = self.module._run_complexity

        def leaving(root, paths, *args, **kwargs):
            os.mkfifo(Path(root) / "tools" / "pipe")
            return real(root, paths, *args, **kwargs)

        message, _run = self._refused_without_inventory(
            patch.object(self.module, "_run_complexity", side_effect=leaving)
        )
        self.assertIn("change not established: unsupported-entry;", message)
        self.assertNotIn("changed during collection", message)

    # An observation that is only unavailable certifies nothing, and refuses nothing:
    # D3's not-certified treatment, for every code that proves no change.
    def test_an_unavailable_reobservation_certifies_nothing(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        for code in (
            "deadline",
            "filesystem",
            "git-failed",
            "cap-descriptors",
            "identity-unavailable",
            "an-unclassified-code",
        ):
            with self.subTest(code):
                failing = self._then(owner.observed_tree, owner.ExactTreeError(code))
                with patch.object(owner, "observed_tree", side_effect=failing):
                    inventory = self._read(self.collect(self.root, self.output))
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                self.assertIn(
                    "the staged source could not be observed again",
                    inventory["coverage"]["reason"],
                )
                for run in self.output.glob("diagnostic-*"):
                    shutil.rmtree(run)

    # The cleanup examines every named entry, directories included, while staging
    # counts files: at max_tree_files equal to the files alone, staging passes and the
    # cleanup stops at that bound, leaving the staged source named (Router 6332488628).
    def test_the_cleanup_examines_no_more_entries_than_the_tree_bound(self) -> None:
        limits = self.module.DiagnosticLimits(max_tree_files=len(self.files))
        inventory = self._read(self.collect(self.root, self.output, limits=limits))
        self.assertTrue(self._complexity(inventory, self.lines["branchy"]))
        self.assertIn(
            f"more than the {len(self.files)} named entries its removal may examine",
            inventory["coverage"]["reason"],
        )
        (run,) = self.output.glob("diagnostic-*")
        self.assertTrue((run / "source").is_dir())

    # A staged source that a producer grows past the bound is refused, and its removal
    # stops at the bound, leaving it named on the refusal rather than listed whole.
    def test_a_staged_source_grown_past_the_bound_is_left_named(self) -> None:
        bound = 12
        real = self.module._run_complexity

        def growing(root, paths, *args, **kwargs):
            for n in range(6):
                (Path(root) / f"grown-{n}.py").write_text("", encoding="utf-8")
            return real(root, paths, *args, **kwargs)

        limits = self.module.DiagnosticLimits(max_tree_files=bound)
        with (
            patch.object(self.module, "_run_complexity", side_effect=growing),
            self.assertRaises(self.module.QualityEvidenceError) as raised,
        ):
            self.collect(self.root, self.output, limits=limits)
        self.assertIn(
            f"more than the {bound} named entries its removal may examine",
            "\n".join(getattr(raised.exception, "__notes__", [])),
        )
        (run,) = self.output.glob("diagnostic-*")
        self.assertTrue((run / "source").is_dir())

    # The tree is staged within the collector's own absolute deadline, never a fresh
    # budget of the owner's.
    def test_staging_shares_the_collectors_deadline(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        real, seen = owner.materialize, []

        def staging(*args, **kwargs):
            seen.append(kwargs["limits"])
            return real(*args, **kwargs)

        reader, deadlines = self.module._diagnostic_git, []

        def reading(root, deadline, *arguments, **options):
            deadlines.append(deadline)
            return reader(root, deadline, *arguments, **options)

        start = time.monotonic()
        limits = self.module.DiagnosticLimits(timeout_seconds=123.0)
        with (
            patch.object(owner, "materialize", side_effect=staging),
            patch.object(self.module, "_diagnostic_git", side_effect=reading),
        ):
            self.collect(self.root, self.output, limits=limits)
        self.assertEqual(1, len(seen))
        self.assertGreaterEqual(seen[0].deadline, start + 123.0)
        # The very deadline of the freeze's own reads: a budget the owner got afresh,
        # however close, differs (cubic on #451).
        self.assertTrue(deadlines)
        self.assertEqual({seen[0].deadline}, set(deadlines))

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

    # A filter driver the repository configures never runs during collection. The
    # marker's name holds a space, and a calibration first proves the probe fires, so
    # a probe that cannot run never passes for a driver that did not (CodeAnt on #451).
    def test_a_configured_driver_never_runs(self) -> None:
        marker = Path(self.directory.name) / "driver ran"
        command = "sh -c " + shlex.quote(f"touch {shlex.quote(str(marker))}; cat")
        self._git("config", "filter.probe.clean", command)
        self._git("config", "filter.probe.smudge", command)
        info = self.root / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("*.py filter=probe\n", encoding="utf-8")
        self._git("hash-object", "--path", "tools/sample.py", "tools/sample.py")
        self.assertTrue(marker.exists(), "the probe's own calibration did not fire")
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
            ("remote.o.uploadpack", f"touch {shlex.quote(str(marker))}; false"),
            ("protocol.file.allow", "always"),
        ):
            self._git("config", key, value)
        # A live probe: a plain read of the missing object fetches, and leaves the
        # marker, so its later absence proves that no fetch ran (Amazon Q on #451).
        with contextlib.suppress(subprocess.CalledProcessError):
            self._git("cat-file", "-p", "1" * 40)
        self.assertTrue(marker.exists(), "the promisor probe did not fire")
        marker.unlink()
        return base, head

    # No diagnostic Git read fetches: the missing object is refused, and the
    # repository's configured promisor command never runs (PAO 6325156914).
    def test_a_diagnostic_read_fetches_no_missing_object(self) -> None:
        marker = Path(self.directory.name) / "was fetched"
        self._promisor(marker)
        with self.assertRaises(subprocess.CalledProcessError):
            self.module._diagnostic_git(
                self.root, time.monotonic() + 60, "cat-file", "-p", "1" * 40
            )
        self.assertFalse(marker.exists())

    # The whole chain, with a base to compare: staging, enumeration and the
    # comparison's patch read all refuse the missing object, and none fetches it.
    def test_the_collection_fetches_no_missing_object(self) -> None:
        marker = Path(self.directory.name) / "was fetched"
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
    record 6325643085). On main 1e4cc560 they failed first again, with production
    unchanged (#389 6328550076)."""

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
        marker = Path(self.directory.name) / "was fetched"
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

        def observer(label: str, calls: list[int]):
            """The identity read for one case, counting its calls in `calls`."""

            def observing(*args, **kwargs):
                calls.append(1)
                if label == "differs":
                    return "0" * 40
                if label == "unobservable at first" or len(calls) > 1:
                    raise owner.ExactTreeError("identity-unavailable")
                return real(*args, **kwargs)

            return observing

        for label, (gap, count) in cases.items():
            with self.subTest(label):
                calls: list[int] = []
                with patch.object(
                    owner, "observed_tree", side_effect=observer(label, calls)
                ):
                    inventory = self._read(self.collect(self.root, self.output))
                self.assertEqual(count, len(calls))
                self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
                self.assertIsNone(inventory["source"]["staged_identity"])
                self.assertIn(gap, inventory["coverage"]["reason"])
                self.assertEqual([], list(self.output.glob("*/source")))
                for run in self.output.glob("diagnostic-*"):
                    shutil.rmtree(run)

    # An unexpected failure while staging is raised as it is, and the staged copy is
    # still removed (cubic on #451).
    def test_an_unexpected_stage_failure_is_raised_and_leaves_no_staged_source(
        self,
    ) -> None:
        owner = importlib.import_module("tools.exact_tree")
        for failure in (RuntimeError("an unexpected failure"), OSError(5, "I/O")):
            with self.subTest(type(failure).__name__):
                with (
                    patch.object(owner, "observed_tree", side_effect=failure),
                    self.assertRaises(type(failure)) as raised,
                ):
                    self.collect(self.root, self.output)
                self.assertIs(failure, raised.exception)
                self.assertEqual([], list(self.output.glob("*/source")))

    def _producers_ending(self, before: float):
        """A patch under which the producers run, then return `before` seconds before
        the inventory's deadline, or after it when negative."""
        real = self.module._run_producers

        def ending(staged, run, expected, limits, gaps, deadline):
            result = real(staged, run, expected, limits, gaps, deadline)
            while time.monotonic() < deadline - before:
                time.sleep(0.02)
            return result

        return patch.object(self.module, "_run_producers", side_effect=ending)

    # The owned cleanup keeps the inventory's one deadline: a spent budget starts no
    # removal, and the staged source is left in the run, named in the gaps (PAO
    # 6329094433 on #389).
    def test_a_spent_budget_leaves_the_staged_source_named(self) -> None:
        limits = self.module.DiagnosticLimits(timeout_seconds=3.0)
        with self._producers_ending(-0.05):
            inventory = self._read(self.collect(self.root, self.output, limits=limits))
        (run,) = self.output.glob("diagnostic-*")
        self.assertTrue((run / "source" / "tools" / "sample.py").exists())
        self.assertIn(
            "the staged source was left in the run directory",
            inventory["coverage"]["reason"],
        )

    # The removal never follows a link: a staged link to a directory goes as a link.
    def test_a_staged_directory_link_is_removed_as_a_link(self) -> None:
        (self.root / "tools" / "fixtures").symlink_to("../tests/fixtures")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a tracked directory link")
        inventory = self._read(self.collect(self.root, self.output))
        self.assertEqual("EXACT_TREE_STAGED", inventory["source"]["tree_binding"])
        self.assertNotIn("staged source was left", inventory["coverage"]["reason"])
        self.assertEqual([], list(self.output.glob("*/source")))

    @staticmethod
    def _limits(deadline: float, entries: int = 10_000) -> Any:
        """The collector's tree limits for one removal: its deadline and an entry
        bound, with the byte bound unused by the removal."""
        return importlib.import_module("tools.exact_tree").Limits(
            deadline, entries, 1 << 30
        )

    def _deep(self, levels: int, name: str = "deep") -> Path:
        """An owned tree `levels` directories deep, with one file at the bottom."""
        top = Path(self.directory.name) / name
        bottom = top.joinpath(*(f"d{n}" for n in range(levels)))
        bottom.mkdir(parents=True)
        (bottom / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
        return top

    def _counting_reads(self):
        """A patch counting every directory read, and the list it counts into."""
        reads: list[int] = []
        real = os.scandir

        def counting(*args, **kwargs):
            reads.append(1)
            return real(*args, **kwargs)

        return patch.object(os, "scandir", counting), reads

    # The traversal itself keeps the deadline: a spent budget reads no directory of
    # the staged source (PAO 6330677193 on #389).
    def test_a_spent_budget_reads_no_directory_of_the_staged_source(self) -> None:
        top = self._deep(13)
        counting, reads = self._counting_reads()
        opens: list[int] = []
        real_open = os.open

        def opening(*args, **kwargs):
            opens.append(1)
            return real_open(*args, **kwargs)

        with counting, patch.object(os, "open", opening):
            retained = self.module._discard_staged(
                top, self._limits(time.monotonic() - 1)
            )
        self.assertEqual([], reads)
        self.assertEqual([], opens)
        self.assertIn("left in the run directory", retained or "")
        self.assertTrue(top.joinpath(*(f"d{n}" for n in range(13)), "leaf.py").exists())

    # A budget that the first directory read spends starts no further read.
    def test_a_budget_spent_during_the_descent_reads_no_further_directory(self) -> None:
        top = self._deep(13)
        clock = [0.0]
        reads: list[int] = []
        real = os.scandir

        def spending(*args, **kwargs):
            reads.append(1)
            clock[0] = 10.0
            return real(*args, **kwargs)

        clocked = SimpleNamespace(monotonic=lambda: clock[0], sleep=time.sleep)
        with (
            patch.object(os, "scandir", spending),
            patch.object(self.module, "time", clocked),
        ):
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertEqual(1, len(reads))
        self.assertIn("deadline", retained or "")
        self.assertTrue(top.joinpath(*(f"d{n}" for n in range(13)), "leaf.py").exists())

    def _spending(self, name: str, after: int):
        """Patches under which the `after`-th call of `os.<name>` spends the budget of a
        removal whose deadline is 5.0, and the list of those calls."""
        clock, calls = [0.0], []
        real = getattr(os, name)

        def spending(*args, **kwargs):
            calls.append(1)
            if len(calls) == after:
                clock[0] = 10.0
            return real(*args, **kwargs)

        clocked = SimpleNamespace(monotonic=lambda: clock[0], sleep=time.sleep)
        return (
            patch.object(os, name, spending),
            patch.object(self.module, "time", clocked),
            calls,
        )

    # A budget spent while a directory is opened reads not that directory.
    def test_a_budget_spent_by_an_open_reads_not_that_directory(self) -> None:
        top = self._deep(3)
        counting, reads = self._counting_reads()
        opening, clocked, opens = self._spending("open", 2)
        with counting, opening, clocked:
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertEqual(2, len(opens))
        self.assertEqual(1, len(reads))
        self.assertIn("deadline", retained or "")

    # A budget spent by one removal removes no further entry.
    def test_a_budget_spent_by_a_removal_removes_no_further_entry(self) -> None:
        top = self._flat(5)
        unlinking, clocked, unlinks = self._spending("unlink", 1)
        with unlinking, clocked:
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertEqual(1, len(unlinks))
        self.assertEqual(4, len(list(top.iterdir())))
        self.assertIn("deadline", retained or "")

    # A budget spent by the last removal in a directory removes not that directory.
    def test_a_budget_spent_by_the_last_removal_keeps_its_directory(self) -> None:
        top = self._deep(3)
        unlinking, clocked, _unlinks = self._spending("unlink", 1)
        with unlinking, clocked:
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertTrue(top.joinpath("d0", "d1", "d2").is_dir())
        self.assertIn("deadline", retained or "")

    # A staged source that is itself a link is never followed: what it points to
    # stays whole.
    def test_a_staged_source_that_is_a_link_is_never_followed(self) -> None:
        outside = self._deep(2)
        link = Path(self.directory.name) / "staged-link"
        link.symlink_to(outside)
        retained = self.module._discard_staged(
            link, self._limits(time.monotonic() + 60)
        )
        self.assertIn("could not be removed whole", retained or "")
        self.assertTrue(outside.joinpath("d0", "d1", "leaf.py").exists())

    def _flat(self, files: int) -> Path:
        """An owned directory holding `files` files and nothing else."""
        top = Path(self.directory.name) / "flat"
        top.mkdir()
        for n in range(files):
            (top / f"f{n}.py").write_text("VALUE = 1\n", encoding="utf-8")
        return top

    def _listing(self, *, spend_on: str):
        """Patches under which each directory listing counts its advances and spends
        the budget of a removal whose deadline is 5.0: on its first advance (`next`),
        on its first entry's type read (`type`) or on the first unlink (`unlink`); with
        the count of the advances, and the type reads, opens and unlinks dispatched in
        their order."""
        clock: list[float] = [0.0]
        advances: list[int] = []
        dispatched: list[str] = []
        real_scandir, real_open, real_unlink = os.scandir, os.open, os.unlink

        class Entry:
            def __init__(self, entry: os.DirEntry[str]) -> None:
                self.name = entry.name
                self._entry = entry

            def is_dir(self, *, follow_symlinks: bool = True) -> bool:
                dispatched.append("type")
                if spend_on == "type":
                    clock[0] = 10.0
                return self._entry.is_dir(follow_symlinks=follow_symlinks)

        class Listing:
            def __init__(self, fd: int) -> None:
                self._real = real_scandir(fd)

            def __enter__(self) -> Listing:
                return self

            def __exit__(self, *_exc: object) -> None:
                self._real.close()

            def __iter__(self) -> Listing:
                return self

            def __next__(self) -> Entry:
                advances.append(1)
                if spend_on == "next":
                    clock[0] = 10.0
                return Entry(next(self._real))

        def opening(*args, **kwargs):
            dispatched.append("open")
            return real_open(*args, **kwargs)

        def unlinking(*args, **kwargs):
            dispatched.append("unlink")
            if spend_on == "unlink":
                clock[0] = 10.0
            return real_unlink(*args, **kwargs)

        clocked = SimpleNamespace(monotonic=lambda: clock[0], sleep=time.sleep)
        patches = contextlib.ExitStack()
        patches.enter_context(patch.object(os, "scandir", Listing))
        patches.enter_context(patch.object(os, "open", opening))
        patches.enter_context(patch.object(os, "unlink", unlinking))
        patches.enter_context(patch.object(self.module, "time", clocked))
        return patches, advances, dispatched

    # The listing's own reads keep the deadline: a budget its first advance spends
    # starts no further advance (Router 6330915173 on #389).
    def test_a_budget_spent_by_a_listing_advance_advances_it_no_further(self) -> None:
        top = self._flat(5)
        patches, advances, dispatched = self._listing(spend_on="next")
        with patches:
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertEqual(1, len(advances))
        self.assertEqual(["open"], dispatched)
        self.assertEqual(5, len(list(top.iterdir())))
        self.assertIn("deadline", retained or "")

    # An entry's type read keeps the deadline: a budget it spends opens or removes
    # nothing after it.
    def test_a_budget_spent_by_an_entry_type_read_dispatches_nothing_after_it(
        self,
    ) -> None:
        top = self._flat(5)
        patches, _advances, dispatched = self._listing(spend_on="type")
        with patches:
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertEqual(["open", "type"], dispatched)
        self.assertEqual(5, len(list(top.iterdir())))
        self.assertIn("deadline", retained or "")

    # A budget spent by one removal reads not even the next entry's type.
    def test_a_budget_spent_by_a_removal_reads_no_further_entry_type(self) -> None:
        top = self._flat(5)
        patches, _advances, dispatched = self._listing(spend_on="unlink")
        with patches:
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertEqual(["open", "type", "unlink"], dispatched)
        self.assertEqual(4, len(list(top.iterdir())))
        self.assertIn("deadline", retained or "")

    # The walk closes every descriptor it opened, both when it completes and when the
    # deadline stops it with directories still open.
    def test_the_walk_closes_every_descriptor_it_opens(self) -> None:
        before = _open_descriptors(self)
        completed = self._deep(4)
        self.assertIsNone(
            self.module._discard_staged(completed, self._limits(time.monotonic() + 60))
        )
        self.assertFalse(completed.exists())
        self.assertEqual(before, _open_descriptors(self))
        stopped = self._deep(4, name="stopped")
        unlinking, clocked, _unlinks = self._spending("unlink", 1)
        with unlinking, clocked:
            retained = self.module._discard_staged(stopped, self._limits(5.0))
        self.assertIn("deadline", retained or "")
        self.assertEqual(before, _open_descriptors(self))

    # A descriptor whose close fails, while the deadline leaves directories open,
    # neither replaces the walk's result nor leaves the others open: the walk's own
    # exception surface stays the returned gap (Claude on #451, 6331607363).
    def test_a_failed_close_leaves_the_result_and_no_other_descriptor_open(
        self,
    ) -> None:
        before = _open_descriptors(self)
        top = self._deep(3)
        unlinking, clocked, _unlinks = self._spending("unlink", 1)
        closes: list[int] = []
        real_close = os.close

        def failing(fd: int) -> None:
            closes.append(fd)
            real_close(fd)
            if len(closes) == 2:
                raise OSError(errno.EIO, "the close failed")

        with unlinking, clocked, patch.object(os, "close", failing):
            retained = self.module._discard_staged(top, self._limits(5.0))
        self.assertIn("deadline", retained or "")
        self.assertEqual(4, len(closes))
        self.assertEqual(before, _open_descriptors(self))

    def _bounded(self, top: Path, entries: int) -> str | None:
        """Remove `top` with ample time and `entries` as the removal's entry bound."""
        return self.module._discard_staged(
            top, self._limits(time.monotonic() + 60, entries=entries)
        )

    # The removal's entry bound at its boundaries (Router 6332488628 on #389): an empty
    # staged source needs none, and a wide listing or a deep chain of `count` named
    # entries is removed at a bound of `count`, and left named at one fewer, or zero.
    def test_the_entry_bound_holds_at_its_boundaries(self) -> None:
        empty = Path(self.directory.name) / "empty"
        empty.mkdir()
        self.assertIsNone(self._bounded(empty, 0))
        self.assertFalse(empty.exists())
        shapes = {
            "wide": (lambda: self._flat(5), 5),
            "deep": (lambda: self._deep(4, name="chain"), 5),
        }
        for shape, (build, count) in shapes.items():
            for entries in (count, count - 1, 0):
                with self.subTest(shape, entries=entries):
                    top = build()
                    retained = self._bounded(top, entries)
                    if entries == count:
                        self.assertIsNone(retained)
                        self.assertFalse(top.exists())
                    else:
                        self.assertIn(
                            f"more than the {entries} named entries", retained or ""
                        )
                        self.assertTrue(top.exists())
                        shutil.rmtree(top)

    # One budget is shared by every directory the removal lists, never reset per
    # directory: an ancestor's entries and its child's count together.
    def test_the_entry_bound_is_shared_across_directories(self) -> None:
        for entries, removed in ((6, True), (5, False)):
            with self.subTest(entries=entries):
                top = Path(self.directory.name) / "shared"
                (top / "child").mkdir(parents=True)
                for name in ("child/one.py", "child/two.py", "child/three.py", "b.py"):
                    (top / name).write_text("", encoding="utf-8")
                (top / "c.py").write_text("", encoding="utf-8")
                retained = self._bounded(top, entries)
                self.assertEqual(removed, retained is None)
                self.assertEqual(removed, not top.exists())
                if top.exists():
                    shutil.rmtree(top)

    # A listing past the bound is never read whole before the bound is checked: it
    # stops at the first entry over the bound.
    def test_a_listing_past_the_bound_is_never_held_whole(self) -> None:
        top = self._flat(5)
        patches, advances, _dispatched = self._listing(spend_on="nothing")
        with patches:
            retained = self._bounded(top, 2)
        self.assertEqual(3, len(advances))
        self.assertIn("more than the 2 named entries", retained or "")
        self.assertEqual(5, len(list(top.iterdir())))

    # A removal the bound stops closes every descriptor it opened.
    def test_a_removal_the_bound_stops_closes_its_descriptors(self) -> None:
        before = _open_descriptors(self)
        top = self._deep(4)
        retained = self._bounded(top, 3)
        self.assertIn("more than the 3 named entries", retained or "")
        self.assertEqual(before, _open_descriptors(self))

    # A stage that fails unexpectedly keeps its own failure when the removal after it
    # stops at the bound: the bound is a note on it, never a replacement.
    def test_the_entry_bound_never_replaces_a_stage_failure(self) -> None:
        owner = importlib.import_module("tools.exact_tree")
        failure = RuntimeError("an unexpected failure")
        limits = self.module.DiagnosticLimits(max_tree_files=len(self.files))
        with (
            patch.object(owner, "observed_tree", side_effect=failure),
            self.assertRaises(RuntimeError) as raised,
        ):
            self.collect(self.root, self.output, limits=limits)
        self.assertIs(failure, raised.exception)
        self.assertIn(
            f"more than the {len(self.files)} named entries",
            "\n".join(getattr(raised.exception, "__notes__", [])),
        )

    # A slow removal stops at the deadline, rather than running on past it.
    def test_a_slow_removal_stops_at_the_deadline(self) -> None:
        limits = self.module.DiagnosticLimits(timeout_seconds=4.0)
        unlink = os.unlink

        def slow(*args, **kwargs):
            time.sleep(0.4)
            return unlink(*args, **kwargs)

        start = time.monotonic()
        with self._producers_ending(0.3), patch.object(self.module.os, "unlink", slow):
            inventory = self._read(self.collect(self.root, self.output, limits=limits))
        overrun = time.monotonic() - (start + 4.0)
        self.assertLess(overrun, 1.0)
        self.assertIn(
            "the staged source was left in the run directory",
            inventory["coverage"]["reason"],
        )

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
        inventory = self._read(
            self.collect(self.root, self.output, expected_revision=tag)
        )
        self.assertIsNone(inventory["source"]["revision"])
        self.assertIsNone(inventory["source"]["tree"])
        self.assertEqual(tag, inventory["source"]["expected_revision"])
        self.assertEqual("NOT_STAGED", inventory["source"]["tree_binding"])
        self.assertEqual([], inventory["producers"])
        self.assertIsNone(self._python(inventory))
        shutil.rmtree(self.output)
        # Anything that is not one full id is refused before any work, by its form,
        # never echoed: an arbitrary input cannot grow the record (CodeAnt on #451).
        for label, expected in (
            ("a short id", self.base[:12]),
            ("a ref name", "HEAD"),
            ("option-like", "--output=" + str(Path(self.directory.name) / "x")),
            ("long", "a" * 100_000),
            ("not text", 40),
        ):
            with self.subTest(label):
                started, spawning = self._spawns()
                with (
                    spawning,
                    self.assertRaises(self.module.QualityEvidenceError) as raised,
                ):
                    self.collect(self.root, self.output, expected_revision=expected)
                message = str(raised.exception)
                self.assertIn("expected_revision", message)
                self.assertLess(len(message), 200)
                self.assertEqual([], started)
                self.assertFalse(self.output.exists())
                self.assertFalse((Path(self.directory.name) / "x").exists())

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
        marker = Path(self.directory.name) / "hook ran"
        for name in ("post-commit", "reference-transaction"):
            hook = hooks / name
            hook.write_text(
                f"#!/bin/sh\ntouch {shlex.quote(str(marker))}\n", encoding="utf-8"
            )
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
            # A live probe: Git outside the fixtures' isolation runs the hook.
            subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on a temporary fixture repository
                [
                    "git",
                    "-c",
                    "user.name=diagnostic",
                    "-c",
                    "user.email=diagnostic@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-q",
                    "--allow-empty",
                    "-m",
                    "a probe",
                ],
                cwd=self.root,
                check=True,
                capture_output=True,
            )
            self.assertTrue(marker.exists(), "the hook probe did not fire")
            marker.unlink()
            self._a_change()
            self._git("commit", "-q", "-am", "under a hostile home")
            ExactSourceTreeTests._promisor(
                self, Path(self.directory.name) / "was fetched"
            )
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
                    self, Path(self.directory.name) / f"was fetched-{label}"
                )
