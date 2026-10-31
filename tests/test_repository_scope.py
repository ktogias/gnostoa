from __future__ import annotations

import importlib
import itertools
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_PATTERNS = {
    "project name": re.compile("Open" + "OP", re.IGNORECASE),
}


def git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve()}",
            "-C",
            str(root),
            *arguments,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def initialize_repository(root: Path) -> None:
    subprocess.run(
        ["git", "init", "--quiet", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )


def fake_git(parent: Path, body: str) -> str:
    """A PATH whose first `git` runs `body`: a stalled or failing Git."""
    directory = parent / "fake-bin"
    directory.mkdir()
    executable = directory / "git"
    executable.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    executable.chmod(0o755)
    return f"{directory}{os.pathsep}{os.environ['PATH']}"


class RepositoryCandidateScopeTests(unittest.TestCase):
    @staticmethod
    def module():
        return importlib.import_module("tools.repository_scope")

    def test_only_git_tracked_candidate_files_are_semantic_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / ".gitignore").write_text(
                ".venv/\nlocal-cache/\n",
                encoding="utf-8",
            )
            (root / "tracked.md").write_text("generic source\n", encoding="utf-8")
            git(root, "add", ".gitignore", "tracked.md")

            leak = "Open" + "OP"
            (root / "scratch.md").write_text(leak, encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "activate").write_text(leak, encoding="utf-8")
            (root / "local-cache").mkdir()
            (root / "local-cache" / "record.txt").write_text(
                leak,
                encoding="utf-8",
            )

            self.assertEqual(
                [Path(".gitignore"), Path("tracked.md")],
                self.module().candidate_paths(root),
            )
            self.assertEqual(
                [],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )

            self.assertTrue((root / "scratch.md").is_file())
            self.assertTrue((root / ".venv" / "activate").is_file())
            self.assertIn("?? scratch.md", git(root, "status", "--short").stdout)

    def test_forbidden_vocabulary_in_a_tracked_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize_repository(root)
            (root / "tracked.md").write_text(
                "Open" + "OP",
                encoding="utf-8",
            )
            git(root, "add", "tracked.md")

            self.assertEqual(
                ["tracked.md: project name"],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )

    def test_tracked_symlink_does_not_expose_external_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "repository"
            root.mkdir()
            initialize_repository(root)
            external = parent / "external.md"
            external.write_text("Open" + "OP", encoding="utf-8")
            (root / "reference.md").symlink_to(external)
            git(root, "add", "reference.md")

            self.assertEqual(
                [],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )
            self.assertEqual("Open" + "OP", external.read_text(encoding="utf-8"))

    def test_packaged_candidate_uses_its_build_manifest_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.md").write_text("generic source\n", encoding="utf-8")
            (root / "incidental.md").write_text(
                "Open" + "OP",
                encoding="utf-8",
            )
            (root / self.module().SOURCE_MANIFEST).write_bytes(b"source.md\0")

            self.assertEqual(
                [Path("source.md")],
                self.module().candidate_paths(root),
            )
            self.assertEqual(
                [],
                self.module().find_text_matches(root, FORBIDDEN_PATTERNS),
            )

    def test_git_metadata_is_classified_by_its_entry_never_followed(self) -> None:
        # cubic and Claude on #436, by the Router's 6239259708: one owner classifies
        # `root/.git` by lstat. A missing entry is no metadata; a directory, or a
        # linked worktree's regular file, is; a symlink, dangling or not, or any other
        # kind is refused as UNSAFE_PATH, never followed; an entry that cannot be
        # inspected stays GIT_METADATA_IO.
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outer = self._tracked_repository(parent)
            self.assertTrue(module.has_git_metadata(outer))
            empty = parent / "empty"
            empty.mkdir()
            self.assertFalse(module.has_git_metadata(empty))
            git(
                outer,
                "-c",
                "user.email=a@b",
                "-c",
                "user.name=a",
                "commit",
                "-q",
                "-m",
                "base",
            )
            worktree = parent / "linked"
            git(outer, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
            self.assertTrue((worktree / ".git").is_file())
            self.assertTrue(module.has_git_metadata(worktree))
            for label, make in (
                (
                    "a symlink to a checkout",
                    lambda entry: entry.symlink_to(outer / ".git"),
                ),
                (
                    "a dangling symlink",
                    lambda entry: entry.symlink_to(parent / "missing"),
                ),
                ("another kind", lambda entry: os.mkfifo(entry)),
            ):
                with self.subTest(label):
                    root = parent / label.replace(" ", "-")
                    root.mkdir()
                    make(root / ".git")
                    with self.assertRaises(module.RepositoryScopeError) as raised:
                        module.has_git_metadata(root)
                    self.assertEqual("UNSAFE_PATH", raised.exception.category)
            real_lstat = Path.lstat

            def failing(path, *args, **kwargs):
                if path.name == ".git" and path.parent == outer:
                    raise PermissionError(13, "denied")
                return real_lstat(path, *args, **kwargs)

            with mock.patch.object(Path, "lstat", failing):
                with self.assertRaises(module.RepositoryScopeError) as raised:
                    module.has_git_metadata(outer)
            self.assertEqual("GIT_METADATA_IO", raised.exception.category)

    def test_unsafe_git_metadata_refuses_the_enumeration_before_any_fallback(
        self,
    ) -> None:
        # The Router's 6239259708: candidate_paths consumes the one classification
        # before any Git or manifest fallback, so a packaged root whose `.git` links to
        # an enclosing checkout never enumerates that checkout's paths. A missing
        # entry keeps the manifest, and a worktree's file keeps Git.
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outer = self._tracked_repository(parent)
            git(
                outer,
                "-c",
                "user.email=a@b",
                "-c",
                "user.name=a",
                "commit",
                "-q",
                "-m",
                "base",
            )
            for label, target in (
                ("to-a-checkout", outer / ".git"),
                ("dangling", parent / "missing"),
            ):
                with self.subTest(label):
                    package = parent / f"package-{label}"
                    package.mkdir()
                    (package / "source.md").write_text(
                        "generic source\n", encoding="utf-8"
                    )
                    (package / module.SOURCE_MANIFEST).write_bytes(b"source.md\0")
                    (package / ".git").symlink_to(target)
                    with (
                        mock.patch.object(module, "_git_candidate_paths") as enumerated,
                        mock.patch.object(
                            module, "_manifest_candidate_paths"
                        ) as listed,
                        self.assertRaises(module.RepositoryScopeError) as raised,
                    ):
                        module.candidate_paths(package)
                    self.assertEqual("UNSAFE_PATH", raised.exception.category)
                    self.assertEqual([], enumerated.call_args_list)
                    self.assertEqual([], listed.call_args_list)
            manifest_only = parent / "manifest-only"
            manifest_only.mkdir()
            (manifest_only / "source.md").write_text(
                "generic source\n", encoding="utf-8"
            )
            (manifest_only / module.SOURCE_MANIFEST).write_bytes(b"source.md\0")
            self.assertEqual([Path("source.md")], module.candidate_paths(manifest_only))
            worktree = parent / "linked"
            git(outer, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
            self.assertEqual([Path("tracked.md")], module.candidate_paths(worktree))

    def test_metadata_that_git_resolves_elsewhere_is_refused(self) -> None:
        # cubic on #436, by the Router's I-b: an empty `.git` directory, or a `gitdir:`
        # file to an enclosing checkout, is accepted by type, but Git's own discovery
        # resolves it to that checkout. Git's top level must be the root itself, else
        # UNSAFE_PATH, before any enumeration; a real linked worktree keeps its route.
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outer = self._tracked_repository(parent)
            git(
                outer,
                "-c",
                "user.email=a@b",
                "-c",
                "user.name=a",
                "commit",
                "-q",
                "-m",
                "base",
            )
            for label, make in (("an empty directory", lambda entry: entry.mkdir()),):
                with self.subTest(label):
                    package = outer / label.replace(" ", "-")
                    package.mkdir()
                    (package / "source.md").write_text(
                        "generic source\n", encoding="utf-8"
                    )
                    make(package / ".git")
                    with self.assertRaises(module.RepositoryScopeError) as raised:
                        module.candidate_paths(package)
                    self.assertEqual("UNSAFE_PATH", raised.exception.category)
            worktree = parent / "linked"
            git(outer, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
            self.assertEqual([Path("tracked.md")], module.candidate_paths(worktree))
            self.assertEqual([Path("tracked.md")], module.candidate_paths(outer))

    def test_a_gitfile_binds_only_through_its_own_registration(self) -> None:
        # cubic on #436, with the Router's falsifiers (6240492499, 6240734250): a
        # `gitdir:` file can borrow another repository's or another worktree's
        # metadata while Git's top level still names the root. A regular-file `.git`
        # binds only when the selected Git directory's own declaration names the
        # root: a linked worktree's back-pointer, or `core.worktree`.
        module = self.module()
        commit = ("-c", "user.email=a@b", "-c", "user.name=a")
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            main = self._tracked_repository(parent)
            git(main, *commit, "commit", "-q", "-m", "base")
            source = parent / "module-source"
            source.mkdir()
            initialize_repository(source)
            (source / "inner.md").write_text("inner\n", encoding="utf-8")
            git(source, "add", "inner.md")
            git(source, *commit, "commit", "-q", "-m", "inner")
            git(
                main,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "-q",
                str(source),
                "vendored",
            )
            git(main, *commit, "commit", "-q", "-m", "a submodule")
            first, spaced = parent / "first", parent / "with space"
            git(main, "worktree", "add", "-q", "--detach", str(first), "HEAD")
            git(main, "worktree", "add", "-q", "--detach", str(spaced), "HEAD")
            declared = parent / "declared"
            subprocess.run(
                [
                    "git",
                    "init",
                    "-q",
                    f"--separate-git-dir={parent / 'declared.git'}",
                    str(declared),
                ],
                check=True,
                capture_output=True,
            )
            git(declared, "config", "core.worktree", str(declared))
            # The Router's 6240734250, per-worktree configuration: with
            # extensions.worktreeConfig the declaration lives in config.worktree.
            per_worktree = parent / "per-worktree"
            subprocess.run(
                [
                    "git",
                    "init",
                    "-q",
                    f"--separate-git-dir={parent / 'per-worktree.git'}",
                    str(per_worktree),
                ],
                check=True,
                capture_output=True,
            )
            git(per_worktree, "config", "extensions.worktreeConfig", "true")
            git(
                per_worktree, "config", "--worktree", "core.worktree", str(per_worktree)
            )
            shared = parent / "shared"
            subprocess.run(
                [
                    "git",
                    "init",
                    "-q",
                    f"--separate-git-dir={parent / 'shared.git'}",
                    str(shared),
                ],
                check=True,
                capture_output=True,
            )
            git(shared, "config", "extensions.worktreeConfig", "true")
            git(shared, "config", "core.worktree", str(shared))
            undeclared = parent / "undeclared"
            subprocess.run(
                [
                    "git",
                    "init",
                    "-q",
                    f"--separate-git-dir={parent / 'undeclared.git'}",
                    str(undeclared),
                ],
                check=True,
                capture_output=True,
            )
            # Git's own setup takes core.worktree from the repository's config and,
            # under extensions.worktreeConfig, its config.worktree, the last winning;
            # never from an include, the global config or a `-c` (measured, Git 2.47).
            extra = parent / "extra.cfg"
            extra.write_text(f"[core]\n\tworktree = {undeclared}\n", encoding="utf-8")
            for label, environment, include in (
                (
                    "an undeclared separate Git directory, the approved narrowing",
                    {},
                    False,
                ),
                ("declared only by an include", {}, True),
                ("declared only globally", {"GIT_CONFIG_GLOBAL": str(extra)}, False),
                (
                    "declared only on the command line",
                    {
                        "GIT_CONFIG_COUNT": "1",
                        "GIT_CONFIG_KEY_0": "core.worktree",
                        "GIT_CONFIG_VALUE_0": str(undeclared),
                    },
                    False,
                ),
            ):
                with self.subTest(label):
                    if include:
                        git(undeclared, "config", "include.path", str(extra))
                    try:
                        with (
                            mock.patch.dict(os.environ, environment),
                            self.assertRaises(module.RepositoryScopeError) as raised,
                        ):
                            module.has_git_metadata(undeclared)
                        self.assertEqual("UNSAFE_PATH", raised.exception.category)
                        self.assertIn(
                            "declares no core.worktree", str(raised.exception)
                        )
                    finally:
                        if include:
                            git(undeclared, "config", "--unset", "include.path")
            git(undeclared, "config", "core.worktree", str(undeclared))
            for label, root in (
                ("the same, once its work tree is declared", undeclared),
                ("an ordinary checkout", main),
                ("a linked worktree", first),
                ("a linked worktree with a space", spaced),
                ("a submodule", main / "vendored"),
                ("a declared separate Git directory", declared),
                ("a separate Git directory declared per worktree", per_worktree),
                ("a shared declaration under worktreeConfig", shared),
            ):
                with self.subTest(label):
                    self.assertTrue(module.has_git_metadata(root))
            hijacked = main / "hijacked"
            hijacked.mkdir()
            (hijacked / ".git").write_text(
                f"gitdir: {main / '.git'}\n", encoding="utf-8"
            )
            borrowed = parent / "borrowed"
            borrowed.mkdir()
            first_admin = git(first, "rev-parse", "--absolute-git-dir").stdout.strip()
            (borrowed / ".git").write_text(f"gitdir: {first_admin}\n", encoding="utf-8")
            second = parent / "second"
            git(main, "worktree", "add", "-q", "--detach", str(second), "HEAD")
            own = (second / ".git").read_text(encoding="utf-8")
            for label, root, heads in (
                ("the main metadata", hijacked, None),
                ("another worktree's metadata", borrowed, None),
                ("a registered worktree redirected, equal HEADs", second, "equal"),
                (
                    "a registered worktree redirected, different HEADs",
                    second,
                    "different",
                ),
            ):
                with self.subTest(label):
                    if heads is not None:
                        (second / ".git").write_text(own, encoding="utf-8")
                        if heads == "different":
                            (second / "own.md").write_text("own\n", encoding="utf-8")
                            git(second, "add", "own.md")
                            git(second, *commit, "commit", "-q", "-m", "own")
                        (second / ".git").write_text(
                            f"gitdir: {first_admin}\n", encoding="utf-8"
                        )
                    with self.assertRaises(module.RepositoryScopeError) as raised:
                        module.has_git_metadata(root)
                    self.assertEqual("UNSAFE_PATH", raised.exception.category)

    def _watched(self, module, worktree: Path, record: Path) -> BaseException | None:
        """has_git_metadata's outcome, watched: a read that blocks on a FIFO in the
        record's place is released by a writer and fails the test, never hangs it."""
        outcome: dict[str, BaseException] = {}

        def call() -> None:
            try:
                module.has_git_metadata(worktree, timeout=10.0)
            except BaseException as exc:
                outcome["raised"] = exc

        thread = threading.Thread(target=call, daemon=True)
        thread.start()
        thread.join(15)
        if thread.is_alive():
            os.close(os.open(record, os.O_WRONLY | os.O_NONBLOCK))
            thread.join(15)
            self.fail("reading the worktree back-pointer blocked")
        return outcome.get("raised")

    def test_a_worktree_back_pointer_is_read_bounded_and_classified(self) -> None:
        # The owner's N-a (6241486091): a linked worktree's own `gitdir` record is read
        # once and bounded, from a regular file only. A missing, foreign, oversized or
        # irregular record is UNSAFE_PATH, never absence or a fallback; a record that
        # cannot be read is GIT_METADATA_IO; every query shares the one budget.
        module = self.module()
        commit = ("-c", "user.email=a@b", "-c", "user.name=a")
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            main = self._tracked_repository(parent)
            git(main, *commit, "commit", "-q", "-m", "base")
            worktree = parent / "linked"
            git(main, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
            admin = Path(
                git(worktree, "rev-parse", "--absolute-git-dir").stdout.strip()
            )
            record = admin / "gitdir"
            original = record.read_bytes()

            def replace(content) -> None:
                record.unlink()
                if isinstance(content, bytes):
                    record.write_bytes(content)
                elif content is not None:
                    content(record)

            def fifo_behind_symlink(entry: Path) -> None:
                os.mkfifo(entry.with_name("gitdir.fifo"))
                entry.symlink_to(entry.with_name("gitdir.fifo"))

            for label, content, detail in (
                ("missing", None, "no worktree back-pointer"),
                (
                    "foreign",
                    f"{parent / 'elsewhere' / '.git'}\n".encode(),
                    "another work tree",
                ),
                ("oversized", b"/" * 5000 + b"\n", "larger than"),
                ("a directory", Path.mkdir, "not a regular file"),
                ("a FIFO", os.mkfifo, "not a regular file"),
                # A symlink in the record's place is an unsafe entry, whatever it names
                # (the owner's N-a 6241486091; cubic and the PAO's NA-BP-01 on #436).
                ("a symlink to a FIFO", fifo_behind_symlink, "not a regular file"),
                (
                    "a symlink to a regular record naming this root",
                    lambda entry: (
                        entry.with_name("gitdir.target").write_bytes(original),
                        entry.symlink_to(entry.with_name("gitdir.target")),
                    ),
                    "not a regular file",
                ),
            ):
                with self.subTest(label):
                    replace(content)
                    try:
                        raised = self._watched(module, worktree, record)
                        self.assertIsInstance(raised, module.RepositoryScopeError)
                        assert isinstance(raised, module.RepositoryScopeError)
                        self.assertEqual("UNSAFE_PATH", raised.category)
                        self.assertIn(detail, str(raised))
                    finally:
                        if record.is_dir():
                            record.rmdir()
                        else:
                            record.unlink(missing_ok=True)
                        record.write_bytes(original)
            with self.subTest("the restored record binds"):
                self.assertTrue(module.has_git_metadata(worktree))
            real_open = os.open

            def failing(path, *args, **kwargs):
                if Path(path) == record:
                    raise PermissionError(13, "denied")
                return real_open(path, *args, **kwargs)

            with self.subTest("unreadable"):
                with (
                    mock.patch.object(module.os, "open", side_effect=failing),
                    self.assertRaises(module.RepositoryScopeError) as unreadable,
                ):
                    module.has_git_metadata(worktree)
                self.assertEqual("GIT_METADATA_IO", unreadable.exception.category)
            seen: list[float] = []
            real = subprocess.run

            def recording(command, **arguments):
                seen.append(arguments.get("timeout"))
                return real(command, **arguments)

            with self.subTest("one budget"):
                with mock.patch.object(module.subprocess, "run", side_effect=recording):
                    self.assertTrue(module.has_git_metadata(worktree, timeout=5.0))
                self.assertLess(1, len(seen))
                # The first read gets what is left of the one budget, never more
                # (#436's identity check takes the remaining budget, the Router's I-b).
                self.assertLessEqual(seen[0], 5.0)
                self.assertGreater(seen[0], 0)
                self.assertTrue(all(b < a for a, b in itertools.pairwise(seen)), seen)
            stalled = parent / "stalled"
            stalled.mkdir()
            fake = stalled / "git"
            fake.write_text(
                '#!/bin/sh\ncase "$*" in *absolute-git-dir*) exec sleep 30;; esac\n'
                f'exec {shutil.which("git")} "$@"\n',
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.subTest("a stalled query"):
                with (
                    mock.patch.dict(
                        os.environ,
                        {"PATH": f"{stalled}{os.pathsep}{os.environ['PATH']}"},
                    ),
                    self.assertRaises(module.RepositoryScopeError) as stalled_query,
                ):
                    module.has_git_metadata(worktree, timeout=0.5)
                self.assertEqual("GIT_TIMEOUT", stalled_query.exception.category)

    def test_the_identity_check_compares_the_resolved_root(self) -> None:
        # cubic on #436, by the Router's I-b ("the resolved requested root"): Git's top
        # level is absolute, so a relative root of a real repository is still its own.
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = self._tracked_repository(Path(directory))
            previous = os.getcwd()
            os.chdir(root.parent)
            try:
                self.assertTrue(module.has_git_metadata(Path(root.name)))
            finally:
                os.chdir(previous)

    def test_the_identity_check_keeps_a_root_name_that_ends_in_a_newline(self) -> None:
        # CodeAnt on #436: Git ends its top level with one newline, and only that one is
        # its terminator, so a root whose name itself ends in a newline is its own.
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repository\n"
            root.mkdir()
            initialize_repository(root)
            self.assertTrue(module.has_git_metadata(root))

    def test_the_identity_check_fails_closed_and_shares_the_budget(self) -> None:
        # The Router's I-b on #436: a malformed answer is UNSAFE_PATH; a failed or a
        # timed-out check keeps Git's own category, never the manifest's fallback; a
        # budget the check spends starts no enumeration.
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self._tracked_repository(parent)
            (root / module.SOURCE_MANIFEST).write_bytes(b"tracked.md\0")
            real = subprocess.run

            def malformed(command, **arguments):
                if "rev-parse" in command:
                    return mock.Mock(returncode=0, stdout=b"\n", stderr=b"")
                return real(command, **arguments)

            with (
                mock.patch.object(module.subprocess, "run", side_effect=malformed),
                self.assertRaises(module.RepositoryScopeError) as raised,
            ):
                module.candidate_paths(root)
            self.assertEqual("UNSAFE_PATH", raised.exception.category)
            for label, body, category in (
                ("a failed check", "exit 3", "GIT_FAILED"),
                ("a timed-out check", "exec sleep 30", "GIT_TIMEOUT"),
            ):
                with self.subTest(label):
                    home = parent / label.replace(" ", "-")
                    home.mkdir()
                    fake = fake_git(home, body)
                    with (
                        mock.patch.dict(os.environ, {"PATH": fake}),
                        self.assertRaises(module.RepositoryScopeError) as raised,
                    ):
                        module.candidate_paths(root, timeout=0.5)
                    self.assertEqual(category, raised.exception.category)
            clock = [100.0]

            def advancing(command, **arguments):
                if "rev-parse" in command:
                    result = real(command, **arguments)
                    clock[0] = 200.0
                    return result
                raise AssertionError("the enumeration started past the budget")

            with (
                mock.patch.object(
                    module, "time", mock.Mock(monotonic=lambda: clock[0])
                ),
                mock.patch.object(module.subprocess, "run", side_effect=advancing),
                self.assertRaises(module.RepositoryScopeError) as raised,
            ):
                module.candidate_paths(root, timeout=2.5)
            self.assertEqual("GIT_TIMEOUT", raised.exception.category)

    def _tracked_repository(self, parent: Path) -> Path:
        root = parent / "repository"
        root.mkdir()
        initialize_repository(root)
        (root / "tracked.md").write_text("generic source\n", encoding="utf-8")
        git(root, "add", "tracked.md")
        return root

    def _enumerate_recording_git(self, root: Path, **options) -> tuple[list, list]:
        seen: list[object] = []
        real = subprocess.run

        def recording(command, **arguments):
            seen.append(arguments.get("timeout"))
            return real(command, **arguments)

        with mock.patch.object(self.module().subprocess, "run", side_effect=recording):
            paths = self.module().candidate_paths(root, **options)
        return paths, seen

    def test_the_default_enumeration_takes_no_budget(self) -> None:
        # Characterization: a legacy caller passes no budget, and Git gets no timeout.
        with tempfile.TemporaryDirectory() as directory:
            root = self._tracked_repository(Path(directory))
            paths, seen = self._enumerate_recording_git(root)
        self.assertEqual([Path("tracked.md")], paths)
        # The identity check, then the enumeration (the Router's I-b on #436).
        self.assertEqual([None, None], seen)

    def test_an_enumeration_passes_its_budget_to_git(self) -> None:
        # An optional budget, for the diagnostic inventory (#389 F3-S1, Option A on #436).
        with tempfile.TemporaryDirectory() as directory:
            root = self._tracked_repository(Path(directory))
            paths, seen = self._enumerate_recording_git(root, timeout=2.5)
        self.assertEqual([Path("tracked.md")], paths)
        # One absolute budget for both (the Router's I-b on #436): each Git read gets
        # only what is left of it, never a fresh one (Codex on #436).
        self.assertEqual(2, len(seen))
        self.assertLess(2.0, seen[0])
        self.assertLessEqual(seen[0], 2.5)
        self.assertLess(0, seen[1])
        self.assertLess(seen[1], seen[0])

    def test_the_identity_check_gets_what_is_left_of_the_budget(self) -> None:
        # The surviving mutant on e412f307: the identity check took the caller's whole
        # timeout instead of what was left of the end it had fixed. A clock that moves
        # between the two readings tells them apart.
        module = self.module()
        readings = iter([100.0, 100.5, 101.0])
        identity = mock.Mock(return_value=True)
        with (
            mock.patch.object(
                module.time, "monotonic", side_effect=lambda: next(readings)
            ),
            mock.patch.object(module, "has_git_metadata", identity),
            mock.patch.object(module, "_git_candidate_paths", return_value=[]),
        ):
            module.candidate_paths(Path("."), timeout=2.5)
        self.assertEqual(2.0, identity.call_args.kwargs["timeout"])

    def test_the_identity_check_counts_its_own_inspection(self) -> None:
        # Codex on #436, by the Router's I-b: the entry's lstat ran after the budget
        # was fixed, and the identity Git read still got the full timeout, so a slow
        # inspection let identity plus enumeration overrun it. The inspection is inside
        # the budget: the Git read gets only what is left, and none once it is spent.
        module = self.module()
        real = Path.lstat

        def slow(path, *args, **kwargs):
            if path.name == ".git":
                time.sleep(0.3)
            return real(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            root = self._tracked_repository(Path(directory))
            with self.subTest("a positive remainder"):
                # A budget well above two real Git reads plus the 0.3 s inspection, so
                # a loaded worker cannot fail it; the remainder is still pinned
                # (CodeAnt on #436).
                with mock.patch.object(Path, "lstat", autospec=True, side_effect=slow):
                    started = time.monotonic()
                    paths, seen = self._enumerate_recording_git(root, timeout=10.0)
                self.assertEqual([Path("tracked.md")], paths)
                self.assertEqual(2, len(seen))
                self.assertLessEqual(seen[0], 10.0 - 0.3)
                self.assertLess(seen[1], seen[0])
                self.assertLess(time.monotonic() - started, 10.0)
            spent: list[object] = []
            run = subprocess.run

            def recording(command, **arguments):
                spent.append(command)
                return run(command, **arguments)

            # The Router's 6244180021: exhaustion before the launch starts neither the
            # identity read nor the enumeration, at either entry.
            for label, call in (
                ("the identity check", module.has_git_metadata),
                ("the enumeration", module.candidate_paths),
            ):
                with self.subTest(label):
                    spent.clear()
                    with (
                        mock.patch.object(
                            Path, "lstat", autospec=True, side_effect=slow
                        ),
                        mock.patch.object(
                            module.subprocess, "run", side_effect=recording
                        ),
                        self.assertRaises(module.RepositoryScopeError) as raised,
                    ):
                        call(root, timeout=0.2)
                    self.assertEqual("GIT_TIMEOUT", raised.exception.category)
                    self.assertEqual([], spent)
        with self.subTest("a missing .git is the manifest's, budget or not"):
            with tempfile.TemporaryDirectory() as directory:
                packaged = Path(directory)
                (packaged / "tracked.md").write_text("tracked\n", encoding="utf-8")
                (packaged / module.SOURCE_MANIFEST).write_bytes(b"tracked.md\0")
                spent.clear()
                with (
                    mock.patch.object(Path, "lstat", autospec=True, side_effect=slow),
                    mock.patch.object(module.subprocess, "run", side_effect=recording),
                ):
                    paths = module.candidate_paths(packaged, timeout=0.2)
                self.assertEqual([Path("tracked.md")], paths)
                self.assertEqual([], spent)

    def test_a_stalled_enumeration_is_refused_within_its_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self._tracked_repository(parent)
            # Built before the assertion, so that it holds one call (SonarCloud S5778).
            scope = self.module()
            stalled = fake_git(parent, "exec sleep 30")
            started = time.monotonic()
            with (
                mock.patch.dict(os.environ, {"PATH": stalled}),
                self.assertRaises(scope.RepositoryScopeError) as raised,
            ):
                scope.candidate_paths(root, timeout=0.5)
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual("GIT_TIMEOUT", raised.exception.category)

    def test_a_failing_enumeration_keeps_its_category_under_a_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = self._tracked_repository(parent)
            scope = self.module()
            failing = fake_git(parent, "exit 3")
            with (
                mock.patch.dict(os.environ, {"PATH": failing}),
                self.assertRaises(scope.RepositoryScopeError) as raised,
            ):
                scope.candidate_paths(root, timeout=5.0)
        self.assertEqual("GIT_FAILED", raised.exception.category)

    def test_a_packaged_candidate_keeps_its_manifest_under_a_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.md").write_text("generic source\n", encoding="utf-8")
            (root / self.module().SOURCE_MANIFEST).write_bytes(b"source.md\0")
            self.assertEqual(
                [Path("source.md")], self.module().candidate_paths(root, timeout=0.5)
            )

    def test_unsafe_build_manifest_entry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / self.module().SOURCE_MANIFEST).write_bytes(b"../external.md\0")

            with self.assertRaisesRegex(
                self.module().RepositoryScopeError,
                "unsafe candidate path",
            ):
                self.module().candidate_paths(root)

    def test_container_runtime_declares_both_candidate_sources(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(
            dockerfile,
            r"ARG GIT_PACKAGE_VERSION=[^\s]+",
        )
        self.assertIn('"git=${GIT_PACKAGE_VERSION}"', dockerfile)
        self.assertIn(self.module().SOURCE_MANIFEST, dockerfile)
        self.assertLess(
            dockerfile.index(self.module().SOURCE_MANIFEST),
            dockerfile.index("python -m pip install"),
        )

    def test_container_runtime_pins_the_admitted_util_linux_security_versions(
        self,
    ) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        for argument in (
            "ARG UTIL_LINUX_VERSION=",
            "ARG UTIL_LINUX_BSDUTILS_VERSION=",
            "ARG UTIL_LINUX_LOGIN_VERSION=",
        ):
            self.assertIn(argument, dockerfile)
        for package in (
            '"bsdutils=${UTIL_LINUX_BSDUTILS_VERSION}"',
            '"libblkid1=${UTIL_LINUX_VERSION}"',
            '"liblastlog2-2=${UTIL_LINUX_VERSION}"',
            '"libmount1=${UTIL_LINUX_VERSION}"',
            '"libsmartcols1=${UTIL_LINUX_VERSION}"',
            '"libuuid1=${UTIL_LINUX_VERSION}"',
            '"login=${UTIL_LINUX_LOGIN_VERSION}"',
            '"mount=${UTIL_LINUX_VERSION}"',
            '"util-linux=${UTIL_LINUX_VERSION}"',
        ):
            self.assertIn(package, dockerfile)
        self.assertIn("--only-upgrade", dockerfile)
        for forbidden in ("apt-get upgrade", "dist-upgrade", "full-upgrade"):
            self.assertNotIn(forbidden, dockerfile)

    @staticmethod
    def _dockerfile_stages() -> dict[str, str]:
        """Split the Dockerfile into its named build stages.

        The pip/ensurepip removal is only correct in the published `runtime`
        stage. Splitting by stage keeps the assertions semantic instead of
        counting occurrences across the whole file, where a `base`-stage match
        would be indistinguishable from a `runtime`-stage one.
        """
        stages: dict[str, str] = {}
        name = ""
        for line in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines():
            match = re.match(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?\s*$", line)
            if match:
                name = match.group(1) or ""
                stages[name] = ""
                continue
            if name:
                stages[name] += line + "\n"
        return stages

    def test_container_runtime_removes_the_affected_pip_component(self) -> None:
        stages = self._dockerfile_stages()
        for required in ("base", "runtime-build", "runtime", "development"):
            self.assertIn(required, stages)

        runtime = stages["runtime"]
        base = stages["base"]

        # The published runtime must drop both shipped pip component copies:
        # the installed distribution with its console scripts, and the wheel
        # bundled under ensurepip that an uninstall alone cannot reach.
        self.assertIn("pip uninstall", runtime)
        self.assertIn("ensurepip", runtime)
        self.assertIn("USER root", runtime)
        # Privilege is dropped again before the runtime is handed to a consumer.
        self.assertLess(runtime.index("USER root"), runtime.rindex("USER kit"))

        # Both branches install through pip; the removal must stay in the
        # published runtime and out of the shared base and of development.
        self.assertIn("python -m pip install", stages["runtime-build"])
        self.assertNotIn("pip uninstall", base)
        self.assertNotIn("ensurepip", base)
        self.assertNotIn("pip uninstall", stages["development"])

        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        # R1 was not selected: no replacement pip is fetched or pinned.
        for forbidden in ("get-pip", "--upgrade pip", "pip install --upgrade"):
            self.assertNotIn(forbidden, dockerfile)
        # Flattening was not selected.
        self.assertNotIn("FROM scratch", dockerfile)

    def test_container_runtime_source_comes_from_the_git_candidate(self) -> None:
        """The runtime's Gnostoa source must come from the filtered candidate.

        Copying the ordinary build context into the runtime would let untracked
        host-local files become importable Gnostoa source and shadow the pip
        commands that install it, so the filtered source and its manifest check
        have to be in place before any source-sensitive Python runs.
        """
        stages = self._dockerfile_stages()
        runtime_build = stages["runtime-build"]
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        # Source arrives only from the named candidate context, never from the
        # ordinary context that carries whatever the builder happens to have.
        self.assertIn("COPY --from=candidate", runtime_build)
        self.assertNotIn("COPY --chown=kit:kit . .", runtime_build)

        # The manifest is bound to exact bytes and the payload is proven to
        # match it, both before the first Python install in this stage.
        self.assertIn("MANIFEST_SHA256", runtime_build)
        self.assertIn("sha256sum -c -", runtime_build)
        self.assertIn("cmp -s", runtime_build)
        self.assertLess(
            runtime_build.index("cmp -s"),
            runtime_build.index("python -m pip install"),
        )
        # Ordering must not depend on the builder's locale.
        self.assertIn("LC_ALL=C sort -z", runtime_build)

        # Development keeps the ordinary context and must not require the
        # candidate context, so `docker build --target development` still works
        # and the devcontainer needs no extra input.
        development_build = stages["development-build"]
        self.assertIn("COPY --chown=kit:kit . .", development_build)
        self.assertNotIn("candidate", development_build)
        self.assertNotIn("candidate", stages["development"])
        self.assertIn("FROM base AS development-build", dockerfile)

        # The helper is self-owned build plumbing, not a supported command.
        helper = ROOT / "ci" / "build-runtime"
        self.assertTrue(helper.is_file())
        self.assertTrue(os.access(helper, os.X_OK))
        self.assertNotIn(
            "build-runtime", (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )

    def test_container_build_context_excludes_local_analysis_state(self) -> None:
        exclusions = set(
            (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        )
        self.assertTrue(
            {".coverage", ".coverage.*", ".mypy_cache", ".ruff_cache"} <= exclusions
        )


if __name__ == "__main__":
    unittest.main()
