from __future__ import annotations

import importlib
import os
import re
import subprocess
import tempfile
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
                    return subprocess.CompletedProcess(command, 0, b"\n", b"")
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
        # One budget: the identity check gets it whole, the enumeration what is left
        # (the Router's I-b on #436).
        self.assertEqual(2, len(seen))
        self.assertEqual(2.5, seen[0])
        self.assertLess(0, seen[1])
        self.assertLess(seen[1], 2.5)

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
