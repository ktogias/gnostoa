"""Conformance for the private VF0 bounded execution observation boundary."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import shutil
import subprocess  # nosec B404 -- test-only fixed list-argv Git/process fixtures
import sys
import tempfile
import textwrap
import time
import unittest
from collections.abc import Callable, Iterator, Sequence
from dataclasses import fields
from pathlib import Path
from typing import cast
from unittest import mock

from tools.vf0_execution import (
    DockerBackend,
    EvidenceFile,
    ExecutionLimits,
    ExecutionObservation,
    ExecutionRejected,
    GitSubject,
    SubprocessBackend,
    UntrustedCapture,
    execute,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(  # nosec B603 -- fixed /usr/bin/git test helper, no shell
        ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(repo.parent),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_NO_REPLACE_OBJECTS": "1",
        },
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> GitSubject:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        "user.name=VF0 Test",
        "-c",
        "user.email=vf0@example.invalid",
        "commit",
        "-m",
        message,
        "--quiet",
    )
    commit = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    return GitSubject(commit=commit, tree=tree)


def _repo(root: Path) -> tuple[Path, GitSubject]:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    (repo / "subject.txt").write_text("one\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "existing.py").write_text("VALUE = 'parent'\n")
    (repo / "bin").mkdir()
    script = repo / "bin" / "run"
    script.write_text("#!/bin/sh\nprintf 'parent-script\\n'\n")
    script.chmod(0o755)
    return repo, _commit(repo, "one")


def _evidence(source: str, path: str = "tests/vf0_evidence.py") -> EvidenceFile:
    return EvidenceFile(path=path, content=textwrap.dedent(source).encode())


class _DirectTestBackend:
    """Test-only direct capture; production containment is tested separately."""

    def run(
        self,
        root: Path,
        command: Sequence[str],
        limits: ExecutionLimits,
        *,
        subject: GitSubject,
    ) -> UntrustedCapture:
        del subject
        from tools.vf0_execution import _capture_process

        return _capture_process(command, cwd=root, limits=limits)


class VF0ExecutionEntryTests(unittest.TestCase):
    def test_entrypoint_exists_without_provider_dependency(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        self.assertTrue(callable(module.execute))
        module_file = module.__file__
        self.assertIsNotNone(module_file)
        if module_file is None:
            self.fail("module source path unavailable")
        source = Path(module_file).read_text()
        self.assertNotIn("github", source.lower())
        self.assertNotIn("requests", source)

    def test_observation_has_no_approval_compliance_or_publication_fields(self) -> None:
        names = {field.name for field in fields(ExecutionObservation)}
        self.assertTrue(
            {"subject", "capture", "subject_unchanged"} <= names,
            names,
        )
        for forbidden in (
            "approval",
            "approved",
            "compliance",
            "vf0_active",
            "receipt",
            "publication",
            "provider",
        ):
            self.assertNotIn(forbidden, names)


class VF0SubjectTests(unittest.TestCase):
    def test_git_subject_requires_exact_lowercase_sha1(self) -> None:
        for commit, tree in [
            ("a" * 39, "b" * 40),
            ("A" * 40, "b" * 40),
            ("a" * 40, "tree"),
        ]:
            with self.subTest(commit=commit, tree=tree):
                with self.assertRaises(ExecutionRejected):
                    GitSubject(commit=commit, tree=tree)

    def test_evidence_is_tests_only_and_canonical(self) -> None:
        for path in (
            "tools/evidence.py",
            "../tests/evidence.py",
            "/tests/evidence.py",
            "tests/../evidence.py",
            "tests",
            "tests/./evidence.py",
            "tests/.git/config",
            "tests/.GIT/config",
            "tests/a\0b.py",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ExecutionRejected):
                    EvidenceFile(path=path, content=b"pass\n")

    def test_evidence_mode_is_bounded(self) -> None:
        with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_MODE"):
            EvidenceFile(path="tests/e.py", content=b"pass\n", mode="120000")

    def test_execution_limits_are_bounded(self) -> None:
        for kwargs in (
            {"timeout_seconds": 0.0},
            {"output_bytes": 0},
            {"memory_bytes": 1},
            {"cpus": 0.0},
            {"pids": 1},
            {"tmpfs_bytes": 1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ExecutionRejected):
                    ExecutionLimits(**kwargs)

    def test_evidence_payload_is_snapshotted_to_immutable_bytes(self) -> None:
        payload = bytearray(b"print('original')\n")
        original = bytes(payload)
        evidence = EvidenceFile(
            path="tests/e.py",
            content=cast(bytes, payload),
        )

        class MutatingBackend:
            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del root, command, limits, subject
                payload[:] = b"print('mutated!')\n"
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            result = execute(
                repo,
                subject,
                [evidence],
                ["/bin/true"],
                MutatingBackend(),
            )

        self.assertIsInstance(evidence.content, bytes)
        self.assertEqual(original, evidence.content)
        self.assertEqual(
            ((evidence.path, hashlib.sha256(original).hexdigest()),),
            result.evidence_sha256,
        )

    def test_deleted_materialization_root_is_bounded_snapshot_rejection(self) -> None:
        class DeleteRootBackend:
            subject_immutable_during_execution = False

            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del command, limits, subject
                shutil.rmtree(root)
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_SNAPSHOT"):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["/bin/true"],
                    DeleteRootBackend(),
                )

    def test_direct_backend_snapshot_equality_is_not_runtime_immutability(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            evidence = _evidence(
                """
                from pathlib import Path
                assert Path('subject.txt').read_text() == 'one\\n'
                assert Path('tests/existing.py').read_text() == "VALUE = 'parent'\\n"
                print('OBSERVED')
                """
            )
            result = execute(
                repo,
                subject,
                [evidence],
                [sys.executable, "-I", evidence.path],
                _DirectTestBackend(),
            )
            self.assertEqual("completed", result.capture.termination)
            self.assertEqual(0, result.capture.exit_code)
            self.assertEqual(b"OBSERVED\n", result.capture.stdout)
            self.assertFalse(result.subject_unchanged)
            self.assertEqual(
                result.before_manifest_sha256, result.after_manifest_sha256
            )
            self.assertEqual(
                ((evidence.path, hashlib.sha256(evidence.content).hexdigest()),),
                result.evidence_sha256,
            )

    def test_subject_file_count_is_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            _git(repo, "init", "--quiet")
            empty = repo / "empty"
            empty.write_bytes(b"")
            oid = _git(repo, "hash-object", "-w", "empty")
            tree_input = "".join(
                f"100644 blob {oid}\tfile-{index:04d}\n"
                for index in range(module._MAX_SUBJECT_FILES + 1)
            ).encode()
            result = subprocess.run(  # nosec B603 -- fixed Git plumbing fixture, no shell
                [
                    "/usr/bin/git",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-C",
                    str(repo),
                    "mktree",
                ],
                check=True,
                input=tree_input,
                capture_output=True,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": str(repo.parent),
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "GIT_NO_REPLACE_OBJECTS": "1",
                },
            )
            tree = result.stdout.decode().strip()
            commit = _git(
                repo,
                "-c",
                "user.name=VF0 Test",
                "-c",
                "user.email=vf0@example.invalid",
                "commit-tree",
                tree,
                "-m",
                "many-files",
            )
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_FILE_COUNT"):
                module._trusted_git_tree_entries(repo, commit)

    def test_subject_tree_listing_bytes_are_bounded(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with mock.patch.object(module, "_MAX_SUBJECT_TREE_LISTING_BYTES", 1):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_TREE_BOUND"):
                    module._trusted_git_tree_entries(repo, subject.commit)

    def test_subject_path_bytes_are_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            raw_name = b"x" * (module._MAX_SUBJECT_PATH_BYTES + 1)
            entry = b"100644 blob " + b"0" * 40 + b" 1\t" + raw_name
            target = Path(td) / "materialized"
            with (
                mock.patch.object(
                    module, "_trusted_git_tree_entries", return_value=[entry]
                ),
                mock.patch.object(
                    module,
                    "_write_git_blob",
                    side_effect=AssertionError("blob written before path bound"),
                ),
            ):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_PATH_BOUND"):
                    module._materialize_subject(repo, subject, target)
            self.assertFalse(target.exists())

    def test_subject_path_components_are_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            raw_name = b"/".join(
                b"x" for _ in range(module._MAX_SUBJECT_PATH_COMPONENTS + 1)
            )
            entry = b"100644 blob " + b"0" * 40 + b" 1\t" + raw_name
            target = Path(td) / "materialized"
            with (
                mock.patch.object(
                    module, "_trusted_git_tree_entries", return_value=[entry]
                ),
                mock.patch.object(
                    module,
                    "_write_git_blob",
                    side_effect=AssertionError("blob written before component bound"),
                ),
            ):
                with self.assertRaisesRegex(
                    ExecutionRejected, "SUBJECT_PATH_COMPONENT_BOUND"
                ):
                    module._materialize_subject(repo, subject, target)
            self.assertFalse(target.exists())

    def test_subject_directory_entries_are_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            entries = [
                b"100644 blob " + b"0" * 40 + b" 1\ta/b/one.txt",
                b"100644 blob " + b"1" * 40 + b" 1\tc/d/two.txt",
            ]
            target = Path(td) / "materialized"
            with (
                mock.patch.object(
                    module, "_trusted_git_tree_entries", return_value=entries
                ),
                mock.patch.object(module, "_MAX_SNAPSHOT_ENTRIES", 5),
                mock.patch.object(
                    module,
                    "_write_git_blob",
                    side_effect=AssertionError("blob written before aggregate bound"),
                ),
            ):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_ENTRY_BOUND"):
                    module._materialize_subject(repo, subject, target)
            self.assertFalse(target.exists())

    def test_subject_tree_listing_selector_setup_failure_reaps_child(self) -> None:
        module = importlib.import_module("tools.vf0_execution")

        class ExplodingSelector:
            def register(self, fileobj: object, events: int) -> None:
                del fileobj, events
                raise OSError("selector setup failed")

            def close(self) -> None:
                pass

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            process = mock.Mock()
            process.stdout = mock.Mock()
            process.poll.return_value = None
            with (
                mock.patch.object(module.subprocess, "Popen", return_value=process),
                mock.patch.object(
                    module.selectors,
                    "DefaultSelector",
                    return_value=ExplodingSelector(),
                ),
            ):
                with self.assertRaisesRegex(ExecutionRejected, "GIT_COMMAND_FAILED"):
                    module._trusted_git_tree_entries(repo, subject.commit)
            process.kill.assert_called_once_with()
            process.wait.assert_called_once_with()

    def test_snapshot_rejects_oversized_file_before_read_bytes(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            oversized = root / "oversized.bin"
            with oversized.open("wb") as handle:
                handle.truncate(module._MAX_FILE_BYTES + 1)
            original_read_bytes = Path.read_bytes

            def guarded_read_bytes(path: Path) -> bytes:
                if path == oversized:
                    raise AssertionError("oversized file read before size bound")
                return original_read_bytes(path)

            with mock.patch.object(Path, "read_bytes", guarded_read_bytes):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_FILE_BOUND"):
                    module._snapshot(root)

    def test_snapshot_bounds_entry_count_before_manifest_growth(self) -> None:
        import tools.vf0_execution as module

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("a", "b", "c"):
                (root / name).write_text(name)
            with mock.patch.object(module, "_MAX_SNAPSHOT_ENTRIES", 2):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_ENTRY_BOUND"):
                    module._snapshot(root)

    def test_restrictive_umask_normalizes_materialization_directory_modes(self) -> None:
        class ModeBackend:
            modes: dict[str, int]

            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del command, limits, subject
                self.modes = {
                    "root": root.stat().st_mode & 0o777,
                    "tests": (root / "tests").stat().st_mode & 0o777,
                    "bin": (root / "bin").stat().st_mode & 0o777,
                    "nested": (root / "tests" / "nested").stat().st_mode & 0o777,
                    "deep": (root / "tests" / "nested" / "deep").stat().st_mode & 0o777,
                }
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            evidence = EvidenceFile(
                path="tests/nested/deep/e.py",
                content=b"print('mode-ok')\n",
            )
            backend = ModeBackend()
            previous_umask = os.umask(0o077)
            try:
                execute(repo, subject, [evidence], ["/bin/true"], backend)
            finally:
                os.umask(previous_umask)

            self.assertEqual(
                {
                    "root": 0o755,
                    "tests": 0o755,
                    "bin": 0o755,
                    "nested": 0o755,
                    "deep": 0o755,
                },
                backend.modes,
            )

    def test_oversized_evidence_is_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")

        class OversizedEvidence(Sequence[EvidenceFile]):
            def __init__(self) -> None:
                self.pulled = 0

            def __len__(self) -> int:
                return 10_000_000

            def __getitem__(self, index: int) -> EvidenceFile:
                if index >= 100:
                    raise IndexError
                self.pulled += 1
                return EvidenceFile(
                    path=f"tests/oversized-{index}.py", content=b"pass\n"
                )

        evidence = OversizedEvidence()
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ):
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_COUNT"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    evidence,
                    ["/bin/true"],
                    SubprocessBackend(),
                )
        self.assertEqual(module._MAX_EVIDENCE_FILES + 1, evidence.pulled)

    def test_evidence_path_bytes_are_bounded_before_split(self) -> None:
        with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_PATH_BOUND"):
            EvidenceFile(path="tests/" + "x" * 4096, content=b"pass\n")

    def test_evidence_path_components_are_bounded_before_split(self) -> None:
        path = "tests/" + "/".join("x" for _ in range(256))
        with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_PATH_COMPONENT_BOUND"):
            EvidenceFile(path=path, content=b"pass\n")

    def test_evidence_sequence_is_snapshotted_before_backend_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            original = _evidence("print('original')")
            evidence = [original]

            class MutatingBackend:
                def run(
                    self,
                    root: Path,
                    command: Sequence[str],
                    limits: ExecutionLimits,
                    *,
                    subject: GitSubject,
                ) -> UntrustedCapture:
                    del root, command, limits, subject
                    evidence[0] = EvidenceFile(
                        path="tests/replaced.py", content=b"print('replacement')\n"
                    )
                    return UntrustedCapture("completed", 0, b"", b"", 0)

            result = execute(repo, subject, evidence, ["/bin/true"], MutatingBackend())
            self.assertEqual(
                ((original.path, hashlib.sha256(original.content).hexdigest()),),
                result.evidence_sha256,
            )

    def test_admitted_evidence_can_replace_existing_test_byte_for_this_execution_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            original = (repo / "tests" / "existing.py").read_bytes()
            evidence = EvidenceFile(
                path="tests/existing.py",
                content=b"VALUE = 'evidence'\nprint(VALUE)\n",
            )
            result = execute(
                repo,
                subject,
                [evidence],
                [sys.executable, "-I", evidence.path],
                _DirectTestBackend(),
            )
            self.assertEqual(b"evidence\n", result.capture.stdout)
            self.assertEqual(original, (repo / "tests" / "existing.py").read_bytes())

    def test_wrong_tree_rejects_before_backend(self) -> None:
        class NeverBackend:
            called = False

            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del root, command, limits, subject
                self.called = True
                raise AssertionError("backend must not run")

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            wrong = GitSubject(commit=subject.commit, tree="f" * 40)
            backend = NeverBackend()
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_TREE"):
                execute(
                    repo,
                    wrong,
                    [_evidence("print('x')")],
                    [sys.executable, "-c", "pass"],
                    backend,
                )
            self.assertFalse(backend.called)

    def test_repository_subdirectory_is_not_an_implicit_subject_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "REPOSITORY_ROOT"):
                execute(
                    repo / "tests",
                    subject,
                    [_evidence("print('x')")],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_git_symlink_subject_is_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, _ = _repo(Path(td))
            link = repo / "tests" / "link"
            link.symlink_to("../subject.txt")
            subject = _commit(repo, "symlink")
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_FILE_TYPE"):
                execute(
                    repo,
                    subject,
                    [_evidence("print('x')")],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_subject_git_metadata_path_rejects_before_materialization(self) -> None:
        import tools.vf0_execution as module

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            fake_entry = b"100644 blob " + (b"a" * 40) + b" 1\t.git/config"
            with mock.patch(
                "tools.vf0_execution._trusted_git_tree_entries",
                return_value=[fake_entry],
            ):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_PATH"):
                    module._materialize_subject(
                        repo, subject, Path(td) / "materialized"
                    )

    def test_evidence_cannot_replace_an_existing_subject_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, _ = _repo(Path(td))
            directory = repo / "tests" / "nested"
            directory.mkdir()
            (directory / "keep.py").write_text("VALUE = 1\n")
            subject = _commit(repo, "nested-directory")
            evidence = EvidenceFile(path="tests/nested", content=b"not-a-directory\n")
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_DESTINATION"):
                execute(
                    repo,
                    subject,
                    [evidence],
                    ["/bin/true"],
                    _DirectTestBackend(),
                )

    def test_duplicate_evidence_path_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            item = _evidence("print('x')")
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_DUPLICATE"):
                execute(
                    repo,
                    subject,
                    [item, item],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_empty_evidence_set_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_COUNT"):
                execute(
                    repo,
                    subject,
                    [],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_empty_command_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "COMMAND"):
                execute(repo, subject, [_evidence("pass")], [], _DirectTestBackend())

    def test_path_lookup_command_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "COMMAND_EXECUTABLE"):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["python3", "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_relative_command_escape_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "COMMAND_EXECUTABLE"):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["./../bin/tool"],
                    _DirectTestBackend(),
                )

    def test_evidence_file_size_is_bounded(self) -> None:
        with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_FILE_BOUND"):
            EvidenceFile(path="tests/large.bin", content=b"x" * (2 * 1024 * 1024 + 1))

    def test_evidence_total_size_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            first = EvidenceFile(path="tests/a.bin", content=b"a" * (1024 * 1024 + 1))
            second = EvidenceFile(path="tests/b.bin", content=b"b" * (1024 * 1024 + 1))
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_TOTAL_BOUND"):
                execute(
                    repo,
                    subject,
                    [first, second],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_executable_mode_is_preserved_for_admitted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            evidence = EvidenceFile(
                path="tests/evidence.sh",
                content=b"#!/bin/sh\nprintf 'mode-ok\\n'\n",
                mode="100755",
            )
            result = execute(
                repo, subject, [evidence], ["./tests/evidence.sh"], _DirectTestBackend()
            )
            self.assertEqual(
                ("completed", 0),
                (result.capture.termination, result.capture.exit_code),
            )
            self.assertEqual(b"mode-ok\n", result.capture.stdout)

    def test_evidence_digest_order_is_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            first = EvidenceFile(path="tests/a.py", content=b"A = 1\n")
            second = EvidenceFile(path="tests/b.py", content=b"B = 2\n")
            one = execute(
                repo,
                subject,
                [first, second],
                [sys.executable, "-c", "pass"],
                _DirectTestBackend(),
            )
            two = execute(
                repo,
                subject,
                [second, first],
                [sys.executable, "-c", "pass"],
                _DirectTestBackend(),
            )
            self.assertEqual(one.evidence_sha256, two.evidence_sha256)
            self.assertEqual(one.before_manifest_sha256, two.before_manifest_sha256)

    def test_backend_receives_ephemeral_gitless_materialization(self) -> None:
        class InspectingBackend:
            def __init__(self, repository: Path) -> None:
                self.repository = repository.resolve()
                self.seen = False

            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del command, limits, subject
                self.seen = True
                if root.resolve() == self.repository or (root / ".git").exists():
                    raise AssertionError("backend received repository metadata")
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            backend = InspectingBackend(repo)
            execute(
                repo,
                subject,
                [_evidence("pass")],
                [sys.executable, "-c", "pass"],
                backend,
            )
            self.assertTrue(backend.seen)

    def test_command_sequence_is_snapshotted_before_validation(self) -> None:
        class FlippingCommand:
            def __init__(self) -> None:
                self.iterations = 0

            def __len__(self) -> int:
                return 1

            def __iter__(self) -> Iterator[str]:
                self.iterations += 1
                yield "/bin/true" if self.iterations == 1 else "/bin/false"

        class RecordingBackend:
            command: tuple[str, ...] | None = None

            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del root, limits, subject
                self.command = tuple(command)
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            command = FlippingCommand()
            backend = RecordingBackend()
            execute(
                repo,
                subject,
                [_evidence("pass")],
                cast(Sequence[str], command),
                backend,
            )
            self.assertEqual(("/bin/true",), backend.command)
            self.assertEqual(1, command.iterations)

    def test_command_count_is_bounded_while_snapshotting(self) -> None:
        module = importlib.import_module("tools.vf0_execution")

        class LargeCommand(Sequence[str]):
            def __init__(self) -> None:
                self.pulled = 0

            def __len__(self) -> int:
                return 10_000_000

            def __getitem__(self, index: int) -> str:
                self.pulled += 1
                return "/bin/true"

        command = LargeCommand()
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ):
            with self.assertRaisesRegex(ExecutionRejected, "COMMAND_COUNT_BOUND"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    [_evidence("pass")],
                    command,
                    SubprocessBackend(),
                )
        self.assertEqual(module._MAX_COMMAND_ARGS + 1, command.pulled)

    def test_command_total_utf8_bytes_are_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        command = ["/bin/true", "x" * module._MAX_COMMAND_BYTES]
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ):
            with self.assertRaisesRegex(ExecutionRejected, "COMMAND_BYTES_BOUND"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    [_evidence("pass")],
                    command,
                    SubprocessBackend(),
                )

    def test_runtime_empty_directory_creation_is_rejected_after_observation(
        self,
    ) -> None:
        class DirectoryMutatingBackend:
            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del command, limits, subject
                (root / "runtime-empty").mkdir()
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_MUTATED"):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["/bin/true"],
                    DirectoryMutatingBackend(),
                )

    def test_runtime_directory_mode_change_is_rejected_after_observation(self) -> None:
        class DirectoryModeBackend:
            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del command, limits, subject
                (root / "tests").chmod(0o700)
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_MUTATED"):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["/bin/true"],
                    DirectoryModeBackend(),
                )

    def test_process_group_is_cleared_before_leader_reap(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        events: list[str] = []
        process = mock.Mock()
        process.pid = 12345
        process.stdout = mock.Mock()
        process.stderr = mock.Mock()
        process.returncode = 0
        process.wait.side_effect = lambda *args, **kwargs: events.append("wait") or 0

        class EmptySelector:
            def register(self, *args: object, **kwargs: object) -> None:
                pass

            def get_map(self) -> dict[object, object]:
                return {}

            def close(self) -> None:
                pass

        def observe_without_reap(
            _process: subprocess.Popen[bytes], _deadline: float
        ) -> bool:
            events.append("observe")
            return True

        def record_kill(_process: subprocess.Popen[bytes]) -> None:
            events.append("kill")

        with (
            mock.patch.object(module.subprocess, "Popen", return_value=process),
            mock.patch.object(
                module.selectors, "DefaultSelector", return_value=EmptySelector()
            ),
            mock.patch.object(
                module, "_wait_for_exit_without_reap", side_effect=observe_without_reap
            ),
            mock.patch.object(module, "_kill_process_group", side_effect=record_kill),
        ):
            module._capture_process(["/bin/true"], cwd=None, limits=ExecutionLimits())
        self.assertEqual(["observe", "kill", "wait"], events)

    def test_runtime_file_mode_change_is_rejected_after_observation(self) -> None:
        class FileModeBackend:
            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del command, limits, subject
                (root / "subject.txt").chmod(0o600)
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_MUTATED"):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["/bin/true"],
                    FileModeBackend(),
                )

    def test_runtime_file_mutation_is_rejected_after_observation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            command = [
                sys.executable,
                "-I",
                "-c",
                "from pathlib import Path; Path('subject.txt').write_text('changed\\n')",
            ]
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_MUTATED"):
                execute(
                    repo, subject, [_evidence("pass")], command, _DirectTestBackend()
                )

    def test_runtime_symlink_creation_is_rejected_after_observation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            command = [
                sys.executable,
                "-I",
                "-c",
                "from pathlib import Path; Path('tests/runtime-link').symlink_to('../subject.txt')",
            ]
            with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_SYMLINK"):
                execute(
                    repo, subject, [_evidence("pass")], command, _DirectTestBackend()
                )

    def test_successive_calls_bind_distinct_subjects_without_global_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, first = _repo(Path(td))
            (repo / "subject.txt").write_text("two\n")
            second = _commit(repo, "two")
            evidence = _evidence(
                "from pathlib import Path; print(Path('subject.txt').read_text(), end='')"
            )
            one = execute(
                repo,
                first,
                [evidence],
                [sys.executable, "-I", evidence.path],
                _DirectTestBackend(),
            )
            two = execute(
                repo,
                second,
                [evidence],
                [sys.executable, "-I", evidence.path],
                _DirectTestBackend(),
            )
            self.assertEqual(b"one\n", one.capture.stdout)
            self.assertEqual(b"two\n", two.capture.stdout)
            self.assertEqual(first, one.subject)
            self.assertEqual(second, two.subject)
            self.assertNotEqual(one.before_manifest_sha256, two.before_manifest_sha256)


class VF0CaptureTests(unittest.TestCase):
    def _run(
        self, source: str, limits: ExecutionLimits | None = None
    ) -> UntrustedCapture:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            evidence = _evidence(source)
            return execute(
                repo,
                subject,
                [evidence],
                [sys.executable, "-I", evidence.path],
                _DirectTestBackend(),
                limits,
            ).capture

    def test_nonzero_exit_is_observed_not_promoted_to_rejection(self) -> None:
        capture = self._run("import sys; print('claimed-red'); sys.exit(17)")
        self.assertEqual(("completed", 17), (capture.termination, capture.exit_code))
        self.assertIn(b"claimed-red", capture.stdout)

    def test_stdout_and_stderr_are_retained_separately(self) -> None:
        capture = self._run("import sys; print('out'); print('err', file=sys.stderr)")
        self.assertEqual(b"out\n", capture.stdout)
        self.assertEqual(b"err\n", capture.stderr)

    def test_output_overflow_is_bounded_and_has_no_exit_claim(self) -> None:
        capture = self._run(
            "import os\nwhile True: os.write(1, b'x' * 4096)",
            ExecutionLimits(timeout_seconds=2.0, output_bytes=8192),
        )
        self.assertEqual("output_limit", capture.termination)
        self.assertIsNone(capture.exit_code)
        self.assertEqual(8192, len(capture.stdout) + len(capture.stderr))
        self.assertTrue(capture.truncated)
        self.assertGreater(capture.observed_bytes_at_least, 8192)

    def test_timeout_kills_a_descendant_pipe_group(self) -> None:
        capture = self._run(
            """
            import subprocess, sys, time
            subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(60)'])
            print('DESCENDANT_STARTED', flush=True)
            time.sleep(60)
            """,
            ExecutionLimits(timeout_seconds=1.5),
        )
        self.assertEqual("timeout", capture.termination)
        self.assertIsNone(capture.exit_code)
        self.assertIn(b"DESCENDANT_STARTED", capture.stdout)

    def test_group_kill_is_attempted_even_after_leader_exit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            marker = Path(td) / "descendant-survived.txt"
            child = (
                "import pathlib,time; "
                "time.sleep(0.25); "
                f"pathlib.Path({str(marker)!r}).write_text('survived')"
            )
            capture = self._run(
                f"""
                import subprocess, sys
                subprocess.Popen(
                    [sys.executable, '-I', '-c', {child!r}],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print('LEADER_DONE', flush=True)
                """,
                ExecutionLimits(timeout_seconds=1.0),
            )
            self.assertEqual(("completed", 0), (capture.termination, capture.exit_code))
            self.assertIn(b"LEADER_DONE", capture.stdout)
            time.sleep(0.5)
            self.assertFalse(marker.exists(), "descendant survived normal leader exit")

    def test_detached_session_descendant_cannot_outlive_local_execution(self) -> None:
        import tools.vf0_execution as module

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            try:
                module._probe_local_containment(repo)
            except ExecutionRejected as exc:
                if str(exc) != "LOCAL_CONTAINMENT_UNAVAILABLE":
                    raise
                self.skipTest("local PID/user namespace containment unavailable")
            marker = Path(td) / "detached-survived.txt"
            child = (
                "import pathlib,time; "
                "time.sleep(0.25); "
                f"pathlib.Path({str(marker)!r}).write_text('survived')"
            )
            evidence = _evidence(
                f"""
                import subprocess, sys
                subprocess.Popen(
                    [sys.executable, '-I', '-c', {child!r}],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                print('LEADER_DONE', flush=True)
                """
            )
            capture = execute(
                repo,
                subject,
                [evidence],
                [sys.executable, "-I", evidence.path],
                SubprocessBackend(),
                ExecutionLimits(timeout_seconds=1.0),
            ).capture
            self.assertEqual(("completed", 0), (capture.termination, capture.exit_code))
            self.assertIn(b"LEADER_DONE", capture.stdout)
            time.sleep(0.5)
            self.assertFalse(marker.exists(), "detached descendant escaped containment")

    def test_subprocess_backend_does_not_claim_transiently_restored_subject_immutable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            evidence = _evidence(
                """
                from pathlib import Path
                subject = Path('subject.txt')
                original = subject.read_bytes()
                subject.write_bytes(b'forged\\n')
                assert subject.read_bytes() == b'forged\\n'
                subject.write_bytes(original)
                print('TRANSIENT_FORGE_OBSERVED')
                """
            )
            try:
                result = execute(
                    repo,
                    subject,
                    [evidence],
                    [sys.executable, "-I", evidence.path],
                    SubprocessBackend(),
                    ExecutionLimits(timeout_seconds=2.0),
                )
            except ExecutionRejected as exc:
                if str(exc) != "LOCAL_CONTAINMENT_UNAVAILABLE":
                    raise
                self.skipTest("local PID/user namespace containment unavailable")
            self.assertEqual(
                ("completed", 0),
                (result.capture.termination, result.capture.exit_code),
            )
            self.assertEqual(b"TRANSIENT_FORGE_OBSERVED\n", result.capture.stdout)
            self.assertEqual(
                result.before_manifest_sha256, result.after_manifest_sha256
            )
            self.assertFalse(result.subject_unchanged)

    def test_subprocess_backend_rejects_failed_containment_probe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subject = GitSubject(commit="a" * 40, tree="b" * 40)
            failed = UntrustedCapture("completed", 1, b"", b"unshare failed", 14)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=failed
            ) as capture:
                with self.assertRaisesRegex(
                    ExecutionRejected, "LOCAL_CONTAINMENT_UNAVAILABLE"
                ):
                    SubprocessBackend().run(
                        root, ["/bin/true"], ExecutionLimits(), subject=subject
                    )
            self.assertEqual(1, capture.call_count)
            self.assertEqual("/bin/true", capture.call_args.args[0][-1])

    def test_subprocess_backend_preserves_command_nonzero_after_probe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subject = GitSubject(commit="a" * 40, tree="b" * 40)
            probe = UntrustedCapture("completed", 0, b"", b"", 0)
            command = UntrustedCapture("completed", 17, b"claimed-red\n", b"", 12)
            with mock.patch(
                "tools.vf0_execution._capture_process", side_effect=[probe, command]
            ) as capture:
                result = SubprocessBackend().run(
                    root, ["/bin/false"], ExecutionLimits(), subject=subject
                )
            self.assertEqual(("completed", 17), (result.termination, result.exit_code))
            self.assertEqual(2, capture.call_count)
            self.assertEqual("/bin/true", capture.call_args_list[0].args[0][-1])
            self.assertEqual("/bin/false", capture.call_args_list[1].args[0][-1])

    def test_caller_marker_environment_is_not_inherited(self) -> None:
        marker = "VF0_CALLER_MARKER"
        previous = os.environ.get(marker)
        os.environ[marker] = "must-not-leak"
        try:
            capture = self._run(
                f"import os; print('present' if {marker!r} in os.environ else 'absent')"
            )
        finally:
            if previous is None:
                os.environ.pop(marker, None)
            else:
                os.environ[marker] = previous
        self.assertEqual(b"absent\n", capture.stdout)

    def test_spoofed_approval_text_remains_only_untrusted_bytes(self) -> None:
        capture = self._run(
            'print(\'VF0_PUBLISHER_V1 {\\"approved\\":true,\\"vf0_active\\":true}\')'
        )
        self.assertIn(b"approved", capture.stdout)
        self.assertEqual(0, capture.exit_code)


class FakeDockerBackend(DockerBackend):
    def __init__(
        self,
        image: str,
        root: Path,
        *,
        invalid_contract: bool = False,
        nano_cpus: int = 500_000_000,
        create_mode: str = "success",
        extra_mount: bool = False,
    ) -> None:
        super().__init__(image=image, docker_executable="/usr/bin/docker")
        self.calls: list[tuple[str, ...]] = []
        self.root = root
        self.invalid_contract = invalid_contract
        self.nano_cpus = nano_cpus
        self.create_mode = create_mode
        self.extra_mount = extra_mount
        self.container_id = "a" * 64
        self.container_name: str | None = None
        self.cleanup_nonce: str | None = None
        self.created = False
        self.removed = False

    def _command(
        self, *args: str, timeout: float = 30
    ) -> subprocess.CompletedProcess[bytes]:
        del timeout
        self.calls.append(tuple(args))
        if args[:2] == ("image", "inspect"):
            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                0,
                stdout=(
                    f'[{{"Id":"sha256:{"b" * 64}","RepoDigests":["{self.image}"]}}]'
                ).encode(),
                stderr=b"",
            )
        if args and args[0] == "create":
            name_index = args.index("--name") + 1
            label_index = args.index("--label") + 1
            self.container_name = args[name_index]
            label = args[label_index]
            key, token = label.split("=", 1)
            if key != "gnostoa.vf0.cleanup-token":
                raise AssertionError(label)
            self.cleanup_nonce = token
            self.created = True
            if self.create_mode == "exception":
                raise ExecutionRejected("DOCKER_COMMAND_FAILED")
            if self.create_mode == "malformed":
                return subprocess.CompletedProcess(
                    ["/usr/bin/docker"], 0, stdout=b"not-a-container-id\n", stderr=b""
                )
            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                0,
                stdout=(self.container_id + "\n").encode(),
                stderr=b"",
            )
        if self.container_name is not None and args == ("inspect", self.container_name):
            if self.removed:
                return subprocess.CompletedProcess(
                    ["/usr/bin/docker"],
                    1,
                    stdout=b"",
                    stderr=b"Error: No such container",
                )
            import json

            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                0,
                stdout=json.dumps(
                    [
                        {
                            "Config": {
                                "Labels": {
                                    "gnostoa.vf0.cleanup-token": self.cleanup_nonce
                                }
                            }
                        }
                    ]
                ).encode(),
                stderr=b"",
            )
        if args == ("inspect", self.container_id):
            if self.removed:
                return subprocess.CompletedProcess(
                    ["/usr/bin/docker"],
                    1,
                    stdout=b"",
                    stderr=b"Error: No such container",
                )
            contract = {
                "HostConfig": {
                    "ReadonlyRootfs": not self.invalid_contract,
                    "NetworkMode": "none",
                    "IpcMode": "none",
                    "Privileged": False,
                    "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges"],
                    "PidsLimit": 32,
                    "Memory": 256 * 1024 * 1024,
                    "MemorySwap": 256 * 1024 * 1024,
                    "NanoCpus": self.nano_cpus,
                },
                "Config": {
                    "User": "10001:10001",
                    "Labels": {"gnostoa.vf0.cleanup-token": self.cleanup_nonce},
                    "Env": [
                        "KNOWLEDGE_KIT_ROOT=/workspace",
                        "KNOWLEDGE_KIT_REVISION=" + ("d" * 40),
                        "PYTHONPATH=/workspace",
                    ],
                },
                "Mounts": [
                    {
                        "Type": "bind",
                        "Source": str(self.root),
                        "Destination": "/workspace",
                        "RW": False,
                    }
                ]
                + (
                    [
                        {
                            "Type": "volume",
                            "Source": "anonymous",
                            "Destination": "/workspace/shadow",
                            "RW": True,
                        }
                    ]
                    if self.extra_mount
                    else []
                ),
            }
            import json

            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                0,
                stdout=json.dumps([contract]).encode(),
                stderr=b"",
            )
        if args[:3] == ("inspect", "--format", "{{json .State}}"):
            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                0,
                stdout=b'{"Running":false,"ExitCode":17}\n',
                stderr=b"",
            )
        if args[:2] == ("rm", "--force"):
            self.removed = True
            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                0,
                stdout=(str(args[-1]) + "\n").encode(),
                stderr=b"",
            )
        if args[:2] == ("container", "inspect"):
            return subprocess.CompletedProcess(
                ["/usr/bin/docker"],
                1,
                stdout=b"",
                stderr=b"Error: No such container",
            )
        raise AssertionError(args)


class VF0DockerBackendTests(unittest.TestCase):
    image = "ghcr.io/ktogias/gnostoa@sha256:" + "c" * 64
    subject = GitSubject(commit="d" * 40, tree="e" * 40)

    def test_image_must_be_digest_pinned(self) -> None:
        for image in ("ghcr.io/ktogias/gnostoa:latest", "sha256:short", "http://bad"):
            with self.subTest(image=image):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_IMAGE_PIN"):
                    DockerBackend(image)

    def test_docker_executable_is_fixed(self) -> None:
        with self.assertRaisesRegex(ExecutionRejected, "DOCKER_EXECUTABLE"):
            DockerBackend(self.image, docker_executable="/usr/local/bin/docker")

    def test_create_contract_is_read_only_network_free_nonroot_and_bounded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            capture = UntrustedCapture("completed", 0, b"ok\n", b"", 3)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                result = backend.run(
                    root,
                    ["/usr/local/bin/python3", "-I", "/workspace/tests/e.py"],
                    ExecutionLimits(),
                    subject=self.subject,
                )
            self.assertEqual(17, result.exit_code)
            create = next(
                call for call in backend.calls if call and call[0] == "create"
            )
            rendered = " ".join(create)
            name = create[create.index("--name") + 1]
            label = create[create.index("--label") + 1]
            self.assertRegex(name, r"^gnostoa-vf0-[0-9a-f]{32}$")
            self.assertEqual(
                "gnostoa.vf0.cleanup-token=" + name.removeprefix("gnostoa-vf0-"),
                label,
            )
            for fragment in (
                "--read-only",
                "--network none",
                "--ipc none",
                "--cap-drop ALL",
                "--security-opt no-new-privileges",
                "--user 10001:10001",
                "--pids-limit 32",
                "--log-driver none",
                "target=/workspace,readonly",
                "KNOWLEDGE_KIT_ROOT=/workspace",
                "KNOWLEDGE_KIT_REVISION=" + self.subject.commit,
                "PYTHONPATH=/workspace",
            ):
                self.assertIn(fragment, rendered)

    def test_extra_image_declared_mount_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root, extra_mount=True)
            with mock.patch("tools.vf0_execution._capture_process") as attached:
                with self.assertRaisesRegex(ExecutionRejected, "OCI_MOUNT_CONTRACT"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            attached.assert_not_called()
            self.assertIn(
                ("rm", "--force", "--volumes", backend.container_id), backend.calls
            )

    def test_fractional_cpu_contract_uses_docker_nano_cpu_rounding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root, nano_cpus=2_010_000_000)
            capture = UntrustedCapture("completed", 0, b"ok\n", b"", 3)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                result = backend.run(
                    root,
                    ["/usr/local/bin/python3", "-I", "/workspace/tests/e.py"],
                    ExecutionLimits(cpus=2.01),
                    subject=self.subject,
                )
            self.assertEqual(17, result.exit_code)

    def test_container_inspect_contract_is_verified_before_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root, invalid_contract=True)
            with mock.patch("tools.vf0_execution._capture_process") as attached:
                with self.assertRaisesRegex(ExecutionRejected, "OCI_CONTRACT"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            attached.assert_not_called()
            self.assertIn(
                ("rm", "--force", "--volumes", backend.container_id), backend.calls
            )
            self.assertIn(("inspect", backend.container_id), backend.calls)

    def test_attachment_failure_still_removes_and_verifies_absence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            with mock.patch(
                "tools.vf0_execution._capture_process",
                side_effect=ExecutionRejected("BACKEND_START_FAILED"),
            ):
                with self.assertRaisesRegex(ExecutionRejected, "BACKEND_START_FAILED"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            rm_index = backend.calls.index(
                ("rm", "--force", "--volumes", backend.container_id)
            )
            absent_index = backend.calls.index(
                ("inspect", backend.container_id), rm_index + 1
            )
            self.assertLess(rm_index, absent_index)

        for create_mode, reason in (
            ("exception", "DOCKER_COMMAND_FAILED"),
            ("malformed", "OCI_CONTAINER_ID"),
        ):
            with (
                self.subTest(create_mode=create_mode),
                tempfile.TemporaryDirectory() as td,
            ):
                root = Path(td).resolve()
                backend = FakeDockerBackend(self.image, root, create_mode=create_mode)
                with self.assertRaisesRegex(ExecutionRejected, reason):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
                self.assertTrue(backend.created)
                self.assertTrue(backend.removed)
                if backend.container_name is None:
                    self.fail("cleanup identity was not established before create")
                self.assertIn(("inspect", backend.container_name), backend.calls)
                self.assertIn(
                    ("rm", "--force", "--volumes", backend.container_name),
                    backend.calls,
                )
                self.assertGreaterEqual(
                    backend.calls.count(("inspect", backend.container_name)), 2
                )

    def test_uncertain_create_retries_transient_inspect_failure(self) -> None:
        class TransientInspect(FakeDockerBackend):
            def __init__(self, image: str, root: Path) -> None:
                super().__init__(image, root, create_mode="exception")
                self.name_inspects = 0

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if self.container_name is not None and args == (
                    "inspect",
                    self.container_name,
                ):
                    self.name_inspects += 1
                    if self.name_inspects == 1:
                        self.calls.append(tuple(args))
                        raise ExecutionRejected("DOCKER_COMMAND_FAILED")
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = TransientInspect(self.image, root)
            with (
                mock.patch(
                    "tools.vf0_execution.time.monotonic",
                    side_effect=[0.0, 0.0, 0.1, 0.1, 0.2],
                ),
                mock.patch("tools.vf0_execution.time.sleep"),
            ):
                with self.assertRaisesRegex(ExecutionRejected, "DOCKER_COMMAND_FAILED"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            self.assertGreaterEqual(backend.name_inspects, 2)
            self.assertTrue(backend.removed)

    def test_uncertain_create_waits_for_delayed_owned_container(self) -> None:
        class DelayedAppearance(FakeDockerBackend):
            def __init__(self, image: str, root: Path) -> None:
                super().__init__(image, root, create_mode="exception")
                self.name_inspects = 0

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if self.container_name is not None and args == (
                    "inspect",
                    self.container_name,
                ):
                    self.name_inspects += 1
                    if self.name_inspects < 3:
                        self.calls.append(tuple(args))
                        return subprocess.CompletedProcess(
                            ["/usr/bin/docker"],
                            1,
                            stdout=b"",
                            stderr=b"Error: No such container",
                        )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = DelayedAppearance(self.image, root)
            with (
                mock.patch(
                    "tools.vf0_execution.time.monotonic",
                    side_effect=[0.0, 0.0, 0.1, 0.1],
                ),
                mock.patch("tools.vf0_execution.time.sleep"),
            ):
                with self.assertRaisesRegex(ExecutionRejected, "DOCKER_COMMAND_FAILED"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            self.assertGreaterEqual(backend.name_inspects, 3)
            self.assertTrue(backend.removed)

    def test_timeout_has_no_container_exit_claim_and_cleanup_still_occurs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            capture = UntrustedCapture("timeout", None, b"started\n", b"", 8)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                result = backend.run(
                    root,
                    ["/bin/sleep", "60"],
                    ExecutionLimits(),
                    subject=self.subject,
                )
            self.assertEqual("timeout", result.termination)
            self.assertIsNone(result.exit_code)
            self.assertNotIn(
                ("inspect", "--format", "{{json .State}}", backend.container_id),
                backend.calls,
            )
            self.assertIn(("inspect", backend.container_id), backend.calls)

    def test_output_limit_has_no_container_exit_claim_and_cleanup_still_occurs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            capture = UntrustedCapture("output_limit", None, b"x" * 8, b"", 9)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                result = backend.run(
                    root, ["/bin/cat"], ExecutionLimits(), subject=self.subject
                )
            self.assertTrue(result.truncated)
            self.assertIsNone(result.exit_code)
            self.assertIn(
                ("rm", "--force", "--volumes", backend.container_id), backend.calls
            )

    def test_uncertain_remove_retries_and_verifies_absence(self) -> None:
        class UncertainRemove(FakeDockerBackend):
            def __init__(self, image: str, root: Path) -> None:
                super().__init__(image, root)
                self.remove_attempts = 0

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:2] == ("rm", "--force"):
                    self.calls.append(tuple(args))
                    self.remove_attempts += 1
                    if self.remove_attempts == 1:
                        raise ExecutionRejected("DOCKER_COMMAND_FAILED")
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = UncertainRemove(self.image, root)
            capture = UntrustedCapture("completed", 0, b"", b"", 0)
            with (
                mock.patch(
                    "tools.vf0_execution._capture_process", return_value=capture
                ),
                mock.patch("tools.vf0_execution.time.sleep"),
            ):
                result = backend.run(
                    root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                )
            self.assertEqual(17, result.exit_code)
            self.assertGreaterEqual(backend.remove_attempts, 2)
            self.assertTrue(backend.removed)

    def test_cleanup_failure_is_fail_closed(self) -> None:
        class BrokenCleanup(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:2] == ("rm", "--force"):
                    self.calls.append(tuple(args))
                    return subprocess.CompletedProcess(
                        ["/usr/bin/docker"], 1, stdout=b"", stderr=b"denied"
                    )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = BrokenCleanup(self.image, root)
            capture = UntrustedCapture("completed", 0, b"", b"", 0)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_CLEANUP_REMOVE"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )

    def test_wrong_repo_digest_rejects_before_create(self) -> None:
        class WrongImage(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:2] == ("image", "inspect"):
                    self.calls.append(tuple(args))
                    return subprocess.CompletedProcess(
                        ["/usr/bin/docker"],
                        0,
                        stdout=b'[{"Id":"sha256:00","RepoDigests":[]}]',
                        stderr=b"",
                    )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = WrongImage(self.image, root)
            with self.assertRaisesRegex(ExecutionRejected, "OCI_IMAGE_IDENTITY"):
                backend.run(
                    root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                )
            self.assertFalse(
                any(call and call[0] == "create" for call in backend.calls)
            )


def _load_smoke_success_checker() -> Callable[[ExecutionObservation, bytes], None]:
    path = Path(__file__).with_name("vf0_execution_oci_smoke.py")
    spec = importlib.util.spec_from_file_location("_vf0_execution_oci_smoke", path)
    if spec is None or spec.loader is None:
        raise AssertionError("SMOKE_HELPER_LOAD")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(
        Callable[[ExecutionObservation, bytes], None],
        module._expect_completed_success,
    )


class VF0SmokeContractTests(unittest.TestCase):
    def _observation(
        self, termination: str, exit_code: int | None, stdout: bytes
    ) -> ExecutionObservation:
        return ExecutionObservation(
            subject=GitSubject(commit="a" * 40, tree="b" * 40),
            evidence_sha256=(("tests/e.py", "c" * 64),),
            before_manifest_sha256="d" * 64,
            after_manifest_sha256="d" * 64,
            capture=UntrustedCapture(
                termination=termination,
                exit_code=exit_code,
                stdout=stdout,
                stderr=b"",
                observed_bytes_at_least=len(stdout),
            ),
            subject_unchanged=True,
        )

    def test_smoke_success_requires_zero_exit_not_only_expected_output(self) -> None:
        expect_completed_success = _load_smoke_success_checker()

        with self.assertRaisesRegex(AssertionError, "SMOKE_SUCCESS_CONTRACT"):
            expect_completed_success(
                self._observation("completed", 17, b"two\n"), b"two\n"
            )

    def test_smoke_success_rejects_timeout_even_with_expected_output(self) -> None:
        expect_completed_success = _load_smoke_success_checker()

        with self.assertRaisesRegex(AssertionError, "SMOKE_SUCCESS_CONTRACT"):
            expect_completed_success(
                self._observation("timeout", None, b"two\n"), b"two\n"
            )

    def test_smoke_success_accepts_completed_zero_exact_output(self) -> None:
        expect_completed_success = _load_smoke_success_checker()

        expect_completed_success(self._observation("completed", 0, b"two\n"), b"two\n")


if __name__ == "__main__":
    unittest.main()
