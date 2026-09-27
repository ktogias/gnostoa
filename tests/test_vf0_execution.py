"""Conformance for the private VF0 bounded execution observation boundary."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import os
import shlex
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
from types import ModuleType
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

    def test_git_subject_rejects_nonstring_identity_with_stable_reason(self) -> None:
        for value in (None, True, 123, 1.5, b"a" * 40, [], {}):
            for field, reason in (
                ("commit", "SUBJECT_COMMIT"),
                ("tree", "SUBJECT_TREE"),
            ):
                with self.subTest(field=field, value=value):
                    identities = {"commit": "a" * 40, "tree": "b" * 40}
                    identities[field] = cast(str, value)
                    with self.assertRaisesRegex(ExecutionRejected, f"^{reason}$"):
                        GitSubject(**identities)

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

    def test_evidence_mode_rejects_nonstring_with_stable_reason(self) -> None:
        for mode in (None, True, 100644, b"100644", [], {}):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ExecutionRejected, "^EVIDENCE_MODE$"):
                    EvidenceFile(
                        path="tests/e.py", content=b"pass\n", mode=cast(str, mode)
                    )

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

    def test_execution_limit_types_fail_through_stable_rejection(self) -> None:
        for kwargs, reason in (
            ({"timeout_seconds": "5"}, "TIMEOUT_BOUND"),
            ({"timeout_seconds": True}, "TIMEOUT_BOUND"),
            ({"output_bytes": 1.5}, "OUTPUT_BOUND"),
            ({"memory_bytes": True}, "MEMORY_BOUND"),
            ({"cpus": "0.5"}, "CPU_BOUND"),
            ({"cpus": False}, "CPU_BOUND"),
            ({"pids": 32.0}, "PIDS_BOUND"),
            ({"tmpfs_bytes": False}, "TMPFS_BOUND"),
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ExecutionRejected, reason):
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

    def test_backend_attribute_cannot_claim_runtime_immutability(self) -> None:
        evidence = _evidence(
            """
            from pathlib import Path
            subject = Path('subject.txt')
            original = subject.read_bytes()
            subject.write_bytes(b'forged\\n')
            assert subject.read_bytes() != original
            subject.write_bytes(original)
            print('TRANSIENT_FORGE_OBSERVED')
            """
        )
        for backend in (_DirectTestBackend(), SubprocessBackend()):
            with self.subTest(backend=type(backend).__name__):
                with tempfile.TemporaryDirectory() as td:
                    repo, subject = _repo(Path(td))
                    backend.__dict__["subject_immutable_during_execution"] = True
                    # Exercise real mutation/capture without depending on host
                    # namespace availability; the local backend cannot enforce
                    # immutability even when PID containment is available.
                    with mock.patch.object(
                        backend, "run", side_effect=_DirectTestBackend().run
                    ):
                        observation = execute(
                            repo,
                            subject,
                            [evidence],
                            [sys.executable, "-I", evidence.path],
                            backend,
                        )
                    self.assertEqual(0, observation.capture.exit_code)
                    self.assertEqual(
                        b"TRANSIENT_FORGE_OBSERVED\n", observation.capture.stdout
                    )
                    self.assertEqual(
                        observation.before_manifest_sha256,
                        observation.after_manifest_sha256,
                    )
                    self.assertFalse(observation.subject_unchanged)

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

    def test_missing_promised_blob_never_invokes_configured_ssh_command(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()
            _git(repo, "init", "--quiet")
            blob = (
                subprocess.run(  # nosec B603 -- fixed Git plumbing fixture, no shell
                    ["/usr/bin/git", "-C", str(repo), "hash-object", "-w", "--stdin"],
                    check=True,
                    input=b"promised blob\n",
                    capture_output=True,
                    env={
                        "PATH": "/usr/local/bin:/usr/bin:/bin",
                        "HOME": str(root),
                        "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": "/dev/null",
                        "GIT_NO_REPLACE_OBJECTS": "1",
                    },
                )
                .stdout.decode("ascii")
                .strip()
            )
            object_path = repo / ".git" / "objects" / blob[:2] / blob[2:]
            object_path.unlink()
            marker = root / "ssh-command-ran"
            ssh_command = root / "ssh-command"
            ssh_command.write_text(
                "#!/bin/sh\n/usr/bin/touch " + shlex.quote(str(marker)) + "\nexit 1\n"
            )
            ssh_command.chmod(0o700)
            _git(repo, "config", "extensions.partialClone", "origin")
            _git(repo, "config", "remote.origin.promisor", "true")
            _git(repo, "config", "remote.origin.url", "ssh://git@promisor.invalid/repo")
            _git(repo, "config", "protocol.ssh.allow", "always")
            _git(
                repo,
                "config",
                "core.sshCommand",
                "/bin/sh " + shlex.quote(str(ssh_command)),
            )

            compatible_git_env = dict(module._GIT_ENV)
            compatible_git_env.pop("GIT_NO_LAZY_FETCH", None)
            self.assertEqual(compatible_git_env.get("GIT_ALLOW_PROTOCOL"), "")
            with mock.patch.object(module, "_GIT_ENV", compatible_git_env):
                with self.assertRaisesRegex(ExecutionRejected, "GIT_COMMAND_FAILED"):
                    module._write_git_blob(repo, blob, root / "materialized", 14)

            self.assertFalse(marker.exists())

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

    def test_snapshot_rejects_oversized_file_before_content_read(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            oversized = root / "oversized.bin"
            with oversized.open("wb") as handle:
                handle.truncate(module._MAX_FILE_BYTES + 1)
            with mock.patch.object(module.os, "read", wraps=os.read) as content_read:
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_FILE_BOUND"):
                    module._snapshot(root)
            content_read.assert_not_called()

    def test_snapshot_bounds_entry_count_before_manifest_growth(self) -> None:
        import tools.vf0_execution as module

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("a", "b", "c"):
                (root / name).write_text(name)
            with mock.patch.object(module, "_MAX_SNAPSHOT_ENTRIES", 2):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_ENTRY_BOUND"):
                    module._snapshot(root)

    def test_snapshot_bounds_individual_relative_path_bytes(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            root.mkdir()
            open_directories = [os.open(root, directory_flags)]
            try:
                parent_fd = open_directories[-1]
                for _ in range(43):
                    name = "d" * 100
                    os.mkdir(name, dir_fd=parent_fd)
                    parent_fd = os.open(name, directory_flags, dir_fd=parent_fd)
                    open_directories.append(parent_fd)
                leaf_fd = os.open(
                    "leaf",
                    os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                    0o644,
                    dir_fd=parent_fd,
                )
                os.close(leaf_fd)
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_PATH_BOUND"):
                    module._snapshot(root)
            finally:
                for descriptor in reversed(open_directories):
                    os.close(descriptor)

    def test_snapshot_bounds_aggregate_path_bytes_before_manifest_growth(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a").write_bytes(b"")
            (root / "b").write_bytes(b"")
            with mock.patch.object(module, "_MAX_SNAPSHOT_TOTAL_PATH_BYTES", 1):
                with self.assertRaisesRegex(
                    ExecutionRejected, "SUBJECT_PATH_TOTAL_BOUND"
                ):
                    module._snapshot(root)

    def test_snapshot_handles_allowed_depth_under_bounded_descriptor_limit(
        self,
    ) -> None:
        try:
            import resource
        except ImportError:
            self.skipTest("resource limits are unavailable on this platform")

        module = importlib.import_module("tools.vf0_execution")
        previous_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        if previous_limit[1] < 256:
            self.skipTest("hard file-descriptor limit is below the test contract")
        try:
            resource.setrlimit(
                resource.RLIMIT_NOFILE, (min(256, previous_limit[1]), previous_limit[1])
            )
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                current = root
                for _ in range(200):
                    current = current / "d"
                    current.mkdir()

                files, directories = module._snapshot(root)

            self.assertEqual({}, files)
            self.assertEqual(201, len(directories))
        finally:
            resource.setrlimit(resource.RLIMIT_NOFILE, previous_limit)

    def test_snapshot_rejects_file_swap_between_classification_and_open(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            root.mkdir()
            victim = root / "victim.txt"
            victim.write_text("inside\n")
            outside = Path(td) / "outside.txt"
            outside.write_text("outside secret\n")
            original_open = os.open
            replacement_attempted = False

            def replace_before_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                nonlocal replacement_attempted
                if (
                    path == victim.name
                    and dir_fd is not None
                    and not replacement_attempted
                ):
                    replacement_attempted = True
                    victim.unlink()
                    victim.symlink_to(outside)
                if dir_fd is None:
                    return original_open(path, flags, mode)
                return original_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(module.os, "open", side_effect=replace_before_open):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_SNAPSHOT"):
                    module._snapshot(root)

            self.assertTrue(replacement_attempted)

    def test_snapshot_rejects_directory_swap_between_classification_and_open(
        self,
    ) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "root"
            root.mkdir()
            victim = root / "nested"
            victim.mkdir()
            (victim / "inside.txt").write_text("inside\n")
            outside = Path(td) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("outside secret\n")
            original_open = os.open
            replacement_attempted = False

            def replace_before_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                nonlocal replacement_attempted
                if (
                    path == victim.name
                    and dir_fd is not None
                    and not replacement_attempted
                ):
                    replacement_attempted = True
                    victim.rename(root / "displaced")
                    victim.symlink_to(outside, target_is_directory=True)
                if dir_fd is None:
                    return original_open(path, flags, mode)
                return original_open(path, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(module.os, "open", side_effect=replace_before_open):
                with self.assertRaisesRegex(ExecutionRejected, "SUBJECT_SNAPSHOT"):
                    module._snapshot(root)

            self.assertTrue(replacement_attempted)

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

    def test_evidence_snapshot_rejects_duck_typed_item_before_materialization(
        self,
    ) -> None:
        module = importlib.import_module("tools.vf0_execution")

        class DuckEvidence:
            path = "tests/duck.py"
            content = b"pass\n"
            mode = "100644"

        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ):
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_CONTENT"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    cast(Sequence[EvidenceFile], [DuckEvidence()]),
                    ["/bin/true"],
                    _DirectTestBackend(),
                )

    def test_noniterable_evidence_rejects_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        for evidence in (None, True, 123):
            with self.subTest(evidence=evidence):
                with mock.patch.object(
                    module,
                    "_materialize_subject",
                    side_effect=AssertionError("materialized"),
                ) as materialize:
                    with self.assertRaisesRegex(
                        ExecutionRejected, "^EVIDENCE_CONTENT$"
                    ):
                        execute(
                            Path.cwd() / "unused-repository",
                            subject,
                            cast(Sequence[EvidenceFile], evidence),
                            ["/bin/true"],
                            _DirectTestBackend(),
                        )
                materialize.assert_not_called()

    def test_evidence_snapshot_revalidates_post_construction_path_mutation(
        self,
    ) -> None:
        module = importlib.import_module("tools.vf0_execution")
        item = _evidence("pass")
        object.__setattr__(item, "path", "../../outside")
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ):
            with self.assertRaisesRegex(ExecutionRejected, "EVIDENCE_PATH"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    [item],
                    ["/bin/true"],
                    _DirectTestBackend(),
                )

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

    def test_repository_root_preserves_valid_non_utf8_filesystem_bytes(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            raw_repo = os.fsencode(td) + b"/repo-\xff"
            repo = Path(os.fsdecode(raw_repo))
            repo.mkdir()
            _git(repo, "init", "--quiet")
            expected = repo.resolve(strict=True)

            self.assertEqual(expected, module._repo_root(repo))

    def test_missing_repository_root_is_a_bounded_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            missing = repo.parent / "missing-repository"
            with self.assertRaisesRegex(ExecutionRejected, "REPOSITORY_ROOT"):
                execute(
                    missing,
                    subject,
                    [_evidence("print('x')")],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )

    def test_reported_repository_root_resolution_is_a_bounded_rejection(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            repo, _ = _repo(Path(td))
            missing = repo.parent / "reported-missing-root"
            with mock.patch.object(
                module, "_trusted_git", return_value=str(missing).encode()
            ):
                with self.assertRaisesRegex(ExecutionRejected, "REPOSITORY_ROOT"):
                    module._repo_root(repo)

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

    def test_duplicate_evidence_path_rejects_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        first = _evidence("print('first')")
        second = _evidence("print('second')")
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ) as materialize:
            with self.assertRaisesRegex(ExecutionRejected, "^EVIDENCE_DUPLICATE$"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    [first, second],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )
        materialize.assert_not_called()

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

    def test_evidence_total_size_is_bounded_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        first = EvidenceFile(path="tests/a.bin", content=b"a" * (1024 * 1024))
        second = EvidenceFile(path="tests/b.bin", content=b"b" * (1024 * 1024 + 1))
        with mock.patch.object(
            module, "_materialize_subject", side_effect=AssertionError("materialized")
        ) as materialize:
            with self.assertRaisesRegex(ExecutionRejected, "^EVIDENCE_TOTAL_BOUND$"):
                execute(
                    Path.cwd() / "unused-repository",
                    subject,
                    [first, second],
                    [sys.executable, "-c", "pass"],
                    _DirectTestBackend(),
                )
        materialize.assert_not_called()

    def test_evidence_exact_total_byte_budget_can_execute(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            first = EvidenceFile(path="tests/a.bin", content=b"a" * (1024 * 1024))
            second = EvidenceFile(path="tests/b.bin", content=b"b" * (1024 * 1024))
            result = execute(
                repo,
                subject,
                [first, second],
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "from pathlib import Path; print(sum(p.stat().st_size "
                    "for p in (Path('tests/a.bin'), Path('tests/b.bin'))))",
                ],
                _DirectTestBackend(),
            )
            self.assertEqual("completed", result.capture.termination)
            self.assertEqual(0, result.capture.exit_code)
            self.assertEqual(b"2097152\n", result.capture.stdout)

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

    def test_observation_binds_command_and_effective_limits(self) -> None:
        class StaticBackend:
            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del root, command, limits, subject
                return UntrustedCapture("completed", 0, b"same", b"", 4)

        def digest(value: object) -> str:
            raw = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
            return "sha256:" + hashlib.sha256(raw).hexdigest()

        limits = ExecutionLimits(
            timeout_seconds=7.5,
            output_bytes=4096,
            memory_bytes=128 * 1024 * 1024,
            cpus=1.25,
            pids=64,
            tmpfs_bytes=8 * 1024 * 1024,
        )
        command = ["/bin/true", "--fixture"]
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            result = execute(
                repo, subject, [_evidence("pass")], command, StaticBackend(), limits
            )
        self.assertEqual(digest(command), result.command_sha256)
        self.assertEqual(
            digest(
                {
                    "timeout_seconds": limits.timeout_seconds,
                    "output_bytes": limits.output_bytes,
                    "memory_bytes": limits.memory_bytes,
                    "cpus": limits.cpus,
                    "pids": limits.pids,
                    "tmpfs_bytes": limits.tmpfs_bytes,
                }
            ),
            result.limits_sha256,
        )
        self.assertIsNone(result.backend_identity)
        self.assertIsNone(result.runtime_identity)

    def test_custom_backend_runtime_configuration_is_explicitly_unbound(self) -> None:
        module = importlib.import_module("tools.vf0_execution")

        class ConfiguredBackend:
            def __init__(self, runtime: str) -> None:
                self.runtime = runtime

        self.assertEqual(
            (None, None),
            module._backend_runtime_identities(ConfiguredBackend("/runtime/a")),
        )
        self.assertEqual(
            (None, None),
            module._backend_runtime_identities(ConfiguredBackend("/runtime/b")),
        )

    def test_runtime_identity_distinguishes_pinned_oci_images(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        first = "sha256:" + "1" * 64
        second = "sha256:" + "2" * 64
        first_backend, first_runtime = module._backend_runtime_identities(
            DockerBackend(first)
        )
        second_backend, second_runtime = module._backend_runtime_identities(
            DockerBackend(second)
        )
        self.assertEqual("gnostoa-docker-oci-v1", first_backend)
        self.assertEqual(first_backend, second_backend)
        self.assertEqual(first, first_runtime)
        self.assertEqual(second, second_runtime)
        self.assertNotEqual(first_runtime, second_runtime)

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

    def test_nul_command_rejects_before_materialization(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        subject = GitSubject(commit="a" * 40, tree="b" * 40)
        for command in (["/bin/true\0"], ["/bin/true", "a\0b"]):
            with self.subTest(command=command):
                with mock.patch.object(
                    module,
                    "_materialize_subject",
                    side_effect=AssertionError("materialized"),
                ) as materialize:
                    with self.assertRaisesRegex(ExecutionRejected, "^COMMAND$"):
                        execute(
                            Path.cwd() / "unused-repository",
                            subject,
                            [_evidence("pass")],
                            command,
                            _DirectTestBackend(),
                        )
                materialize.assert_not_called()

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

    def test_actual_local_containment_launch_requires_ready_handshake(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            subject = GitSubject(commit="0" * 40, tree="1" * 40)
            failed_launch = [sys.executable, "-I", "-c", "raise SystemExit(1)"]
            with (
                mock.patch.object(
                    module, "_probe_local_containment", return_value=None
                ),
                mock.patch.object(
                    module, "_local_containment_launch_argv", return_value=failed_launch
                ),
            ):
                with self.assertRaisesRegex(
                    ExecutionRejected, "LOCAL_CONTAINMENT_UNAVAILABLE"
                ):
                    SubprocessBackend().run(
                        root, ["/bin/true"], ExecutionLimits(), subject=subject
                    )

    def test_local_containment_ready_handshake_preserves_evidence_result(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        sentinel_literal = repr(module._LOCAL_CONTAINMENT_READY_SENTINEL)
        script = (
            "import os; "
            f"os.write(2,{sentinel_literal}); "
            "os.write(1,b'abc'); "
            "raise SystemExit(1)"
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            subject = GitSubject(commit="0" * 40, tree="1" * 40)
            launch = [sys.executable, "-I", "-c", script]
            with (
                mock.patch.object(
                    module, "_probe_local_containment", return_value=None
                ),
                mock.patch.object(
                    module, "_local_containment_launch_argv", return_value=launch
                ),
            ):
                result = SubprocessBackend().run(
                    root,
                    ["/bin/false"],
                    ExecutionLimits(output_bytes=3),
                    subject=subject,
                )
        self.assertEqual(("completed", 1), (result.termination, result.exit_code))
        self.assertEqual(b"abc", result.stdout)
        self.assertEqual(b"", result.stderr)
        self.assertEqual(3, result.observed_bytes_at_least)

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

    def test_selector_construction_failure_cleans_and_reaps_owned_process(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        events: list[str] = []
        process = mock.Mock()
        process.pid = 12345
        process.stdout = mock.Mock()
        process.stderr = mock.Mock()
        process.returncode = 0
        process.wait.side_effect = lambda *args, **kwargs: events.append("wait") or 0

        with (
            mock.patch.object(module.subprocess, "Popen", return_value=process),
            mock.patch.object(
                module.selectors, "DefaultSelector", side_effect=OSError("selector")
            ),
            mock.patch.object(
                module,
                "_kill_process_group",
                side_effect=lambda _process: events.append("kill"),
            ),
        ):
            with self.assertRaisesRegex(ExecutionRejected, "BACKEND_CAPTURE_FAILED"):
                module._capture_process(
                    ["/bin/true"], cwd=None, limits=ExecutionLimits()
                )
        self.assertEqual(["kill", "wait"], events)
        process.stdout.close.assert_called_once_with()
        process.stderr.close.assert_called_once_with()

    def test_selector_registration_failure_cleans_and_reaps_owned_process(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        events: list[str] = []
        process = mock.Mock()
        process.pid = 12345
        process.stdout = mock.Mock()
        process.stderr = mock.Mock()
        process.returncode = 0
        process.wait.side_effect = lambda *args, **kwargs: events.append("wait") or 0
        selector = mock.Mock()
        selector.register.side_effect = OSError("register")

        with (
            mock.patch.object(module.subprocess, "Popen", return_value=process),
            mock.patch.object(
                module.selectors, "DefaultSelector", return_value=selector
            ),
            mock.patch.object(
                module,
                "_kill_process_group",
                side_effect=lambda _process: events.append("kill"),
            ),
        ):
            with self.assertRaisesRegex(ExecutionRejected, "BACKEND_CAPTURE_FAILED"):
                module._capture_process(
                    ["/bin/true"], cwd=None, limits=ExecutionLimits()
                )
        self.assertEqual(["kill", "wait"], events)
        selector.close.assert_called_once_with()
        process.stdout.close.assert_called_once_with()
        process.stderr.close.assert_called_once_with()

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
        extra_environment: tuple[str, ...] = (),
    ) -> None:
        super().__init__(image=image, docker_executable="/usr/bin/docker")
        self.calls: list[tuple[str, ...]] = []
        self.root = root
        self.invalid_contract = invalid_contract
        self.nano_cpus = nano_cpus
        self.create_mode = create_mode
        self.extra_mount = extra_mount
        self.extra_environment = extra_environment
        self.container_id = "a" * 64
        self.container_name: str | None = None
        self.cleanup_nonce: str | None = None
        self.created_entrypoint: str | None = None
        self.created_command: list[str] = []
        self.created_working_dir: str | None = None
        self.created_tmpfs_destination: str | None = None
        self.created_tmpfs_options: str | None = None
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
                stdout=json.dumps(
                    [
                        {
                            "Id": "sha256:" + "b" * 64,
                            "RepoDigests": [self.image],
                            "Os": "linux",
                            "Architecture": "amd64",
                            "Config": {"Env": ["PATH=/usr/bin", "IMAGE_POLICY=bound"]},
                        }
                    ]
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
            entrypoint_index = args.index("--entrypoint") + 1
            image_index = entrypoint_index + 1
            self.created_entrypoint = args[entrypoint_index]
            self.created_command = list(args[image_index + 1 :])
            self.created_working_dir = args[args.index("--workdir") + 1]
            tmpfs_spec = args[args.index("--tmpfs") + 1]
            self.created_tmpfs_destination, self.created_tmpfs_options = (
                tmpfs_spec.split(":", 1)
            )
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
                    stderr=f"Error: No such object: {args[-1]}\n".encode(),
                )
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
                    stderr=f"Error: No such object: {args[-1]}\n".encode(),
                )
            contract = {
                "Image": "sha256:" + "b" * 64,
                "Path": self.created_entrypoint,
                "Args": self.created_command,
                "HostConfig": {
                    "Tmpfs": {
                        self.created_tmpfs_destination: self.created_tmpfs_options
                    },
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
                    "Entrypoint": [self.created_entrypoint],
                    "Cmd": self.created_command,
                    "WorkingDir": self.created_working_dir,
                    "User": "10001:10001",
                    "Labels": {"gnostoa.vf0.cleanup-token": self.cleanup_nonce},
                    "Env": [
                        "PATH=/usr/bin",
                        "IMAGE_POLICY=bound",
                        "HOME=/tmp",
                        "PYTHONDONTWRITEBYTECODE=1",
                        "KNOWLEDGE_KIT_ROOT=/workspace",
                        "KNOWLEDGE_KIT_REVISION=" + ("d" * 40),
                        "PYTHONPATH=/workspace",
                        *self.extra_environment,
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
                stdout=(
                    b'{"Status":"exited","Running":false,"ExitCode":17,'
                    b'"OOMKilled":false}\n'
                ),
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
                stderr=f"Error: No such object: {args[-1]}\n".encode(),
            )
        raise AssertionError(args)


class VF0DockerBackendTests(unittest.TestCase):
    image = "ghcr.io/ktogias/gnostoa@sha256:" + "c" * 64
    subject = GitSubject(commit="d" * 40, tree="e" * 40)

    @staticmethod
    def _completed_capture(
        exit_code: int = 17, stdout: bytes = b"ok\n", stderr: bytes = b""
    ) -> UntrustedCapture:
        marker = b"\x1eGNOSTOA_VF0_EXIT_V1:" + str(exit_code).encode() + b"\x1f"
        return UntrustedCapture(
            "completed",
            exit_code,
            stdout,
            stderr + marker,
            len(stdout) + len(stderr) + len(marker),
        )

    def test_image_must_be_digest_pinned(self) -> None:
        for image in ("ghcr.io/ktogias/gnostoa:latest", "sha256:short", "http://bad"):
            with self.subTest(image=image):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_IMAGE_PIN"):
                    DockerBackend(image)

    def test_docker_executable_is_fixed(self) -> None:
        with self.assertRaisesRegex(ExecutionRejected, "DOCKER_EXECUTABLE"):
            DockerBackend(self.image, docker_executable="/usr/local/bin/docker")

    def test_validated_backend_configuration_cannot_be_reassigned(self) -> None:
        for backend in (
            DockerBackend(self.image),
            FakeDockerBackend(self.image, Path("/unused")),
        ):
            for attribute, replacement in (
                ("image", "sha256:" + "f" * 64),
                ("docker_executable", "/bin/echo"),
            ):
                with self.subTest(backend=type(backend).__name__, attribute=attribute):
                    original = getattr(backend, attribute)
                    with self.assertRaises(AttributeError):
                        setattr(backend, attribute, replacement)
                    self.assertEqual(original, getattr(backend, attribute))

    def test_command_dispatch_retains_the_validated_docker_executable(self) -> None:
        backend = DockerBackend(self.image)
        attribute = "docker_executable"
        try:
            setattr(backend, attribute, "/bin/echo")
        except AttributeError:
            pass
        completed = subprocess.CompletedProcess(
            ["/usr/bin/docker"], 0, stdout=b"", stderr=b""
        )
        with mock.patch(
            "tools.vf0_execution.subprocess.run", return_value=completed
        ) as launched:
            backend._command("version")
        self.assertEqual(["/usr/bin/docker", "version"], launched.call_args.args[0])

    def test_cleanup_absence_requires_exact_native_inspect_diagnostic(self) -> None:
        container_id = "a" * 64
        native = f"Error: No such object: {container_id}\n".encode()
        for diagnostic, expected in (
            (native, False),
            (native.lower(), False),
            (b"Error: No such object: other-container\n", None),
            (
                b"dial unix /var/run/docker.sock: connect: no such file or directory",
                None,
            ),
            (native + b"daemon connection interrupted\n", None),
        ):
            with self.subTest(diagnostic=diagnostic):
                backend = DockerBackend(self.image)
                missing = subprocess.CompletedProcess(
                    ["/usr/bin/docker"], 1, stdout=b"[]\n", stderr=diagnostic
                )
                with mock.patch.object(DockerBackend, "_command", return_value=missing):
                    self.assertIs(
                        expected, backend._cleanup_presence(container_id, "owned")
                    )

    def test_cleanup_cannot_infer_absence_from_transport_or_remove_errors(
        self,
    ) -> None:
        class FailedCommand(FakeDockerBackend):
            known_present: bool
            diagnostic: bytes

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[0] == "inspect" and self.known_present:
                    return super()._command(*args, timeout=timeout)
                self.calls.append(tuple(args))
                return subprocess.CompletedProcess(
                    ["/usr/bin/docker"], 1, stdout=b"", stderr=self.diagnostic
                )

        socket_error = (
            b"dial unix /var/run/docker.sock: connect: no such file or directory"
        )
        remove_error = b"Error response from daemon: No such container: " + b"a" * 64
        for operation, known_present, diagnostic in (
            ("presence", False, socket_error),
            ("remove", False, socket_error),
            ("retry", True, socket_error),
            ("create", False, socket_error),
            ("remove", True, remove_error),
            ("retry", True, remove_error),
        ):
            with self.subTest(operation=operation, diagnostic=diagnostic):
                with tempfile.TemporaryDirectory() as td:
                    backend = FailedCommand(self.image, Path(td).resolve())
                    backend.known_present = known_present
                    backend.diagnostic = diagnostic
                    backend.cleanup_nonce = "owned"
                    with (
                        mock.patch(
                            "tools.vf0_execution.time.monotonic",
                            side_effect=[0.0, 0.0, 3.0],
                        ),
                        mock.patch("tools.vf0_execution.time.sleep"),
                    ):
                        if operation == "presence":
                            self.assertIsNone(
                                backend._cleanup_presence(backend.container_id, "owned")
                            )
                            continue
                        action = {
                            "remove": backend._remove_and_verify,
                            "retry": backend._reconcile_uncertain_remove,
                            "create": backend._cleanup_uncertain_create,
                        }[operation]
                        with self.assertRaisesRegex(
                            ExecutionRejected, "OCI_CLEANUP_UNVERIFIED"
                        ):
                            action(backend.container_id, "owned")

    def test_foreign_returned_container_id_is_never_force_removed(self) -> None:
        class ForeignReturnedId(FakeDockerBackend):
            def __init__(self, root: Path) -> None:
                super().__init__(VF0DockerBackendTests.image, root)
                self.container_id = "f" * 64

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                result = super()._command(*args, timeout=timeout)
                if args == ("inspect", self.container_id) and result.returncode == 0:
                    payload = json.loads(result.stdout)
                    payload[0]["Config"]["Labels"]["gnostoa.vf0.cleanup-token"] = (
                        "foreign-owner"
                    )
                    result.stdout = json.dumps(payload).encode()
                return result

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = ForeignReturnedId(root)
            with mock.patch("tools.vf0_execution._capture_process") as attached:
                with self.assertRaisesRegex(ExecutionRejected, "OCI_CONTRACT"):
                    backend.run(
                        root,
                        ["/usr/local/bin/python3", "-I", "/workspace/tests/e.py"],
                        ExecutionLimits(),
                        subject=self.subject,
                    )

            attached.assert_not_called()
            remove_targets = [
                call[-1] for call in backend.calls if call[:2] == ("rm", "--force")
            ]
            self.assertEqual([backend.container_name], remove_targets)
            self.assertNotIn(backend.container_id, remove_targets)

    def test_absent_returned_container_id_still_cleans_owned_generated_name(
        self,
    ) -> None:
        class AbsentReturnedId(FakeDockerBackend):
            reported_id = "f" * 64

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args == ("inspect", self.reported_id):
                    self.calls.append(tuple(args))
                    return subprocess.CompletedProcess(
                        ["/usr/bin/docker", *args],
                        1,
                        stdout=b"[]\n",
                        stderr=(
                            f"error: no such object: {self.reported_id}\n"
                        ).encode(),
                    )
                result = super()._command(*args, timeout=timeout)
                if args and args[0] == "create":
                    result.stdout = (self.reported_id + "\n").encode()
                return result

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = AbsentReturnedId(self.image, root)
            with mock.patch("tools.vf0_execution._capture_process") as attached:
                with self.assertRaisesRegex(ExecutionRejected, "DOCKER_COMMAND_FAILED"):
                    backend.run(
                        root,
                        ["/usr/local/bin/python3", "-I", "/workspace/tests/e.py"],
                        ExecutionLimits(),
                        subject=self.subject,
                    )

            attached.assert_not_called()
            self.assertTrue(backend.removed)
            remove_targets = [
                call[-1] for call in backend.calls if call[:2] == ("rm", "--force")
            ]
            self.assertEqual([backend.container_name], remove_targets)
            self.assertNotIn(backend.reported_id, remove_targets)

    def test_image_platform_must_be_linux_amd64_before_create(self) -> None:
        class WrongPlatform(FakeDockerBackend):
            platform: dict[str, str]

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                result = super()._command(*args, timeout=timeout)
                if args[:2] == ("image", "inspect"):
                    spec = json.loads(result.stdout)
                    spec[0].pop("Os")
                    spec[0].pop("Architecture")
                    spec[0].update(self.platform)
                    result.stdout = json.dumps(spec).encode()
                return result

        for platform in (
            {"Os": "linux", "Architecture": "arm64"},
            {"Os": "windows", "Architecture": "amd64"},
            {},
        ):
            with self.subTest(platform=platform):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td).resolve()
                    backend = WrongPlatform(self.image, root)
                    backend.platform = platform
                    with mock.patch(
                        "tools.vf0_execution._capture_process",
                        return_value=self._completed_capture(),
                    ) as attached:
                        with self.assertRaisesRegex(
                            ExecutionRejected, "OCI_IMAGE_PLATFORM"
                        ):
                            backend.run(
                                root,
                                ["/bin/true"],
                                ExecutionLimits(),
                                subject=self.subject,
                            )
                    attached.assert_not_called()
                    self.assertFalse(backend.created)

    def test_created_container_uses_inspected_image_config_before_attachment(
        self,
    ) -> None:
        class WrongContainerImage(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                result = super()._command(*args, timeout=timeout)
                if args == ("inspect", self.container_id) and not self.removed:
                    spec = json.loads(result.stdout)
                    spec[0]["Image"] = "sha256:" + "f" * 64
                    result.stdout = json.dumps(spec).encode()
                return result

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = WrongContainerImage(self.image, root)
            with mock.patch(
                "tools.vf0_execution._capture_process",
                return_value=self._completed_capture(),
            ) as attached:
                with self.assertRaisesRegex(ExecutionRejected, "OCI_IMAGE_IDENTITY"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            attached.assert_not_called()
            self.assertTrue(backend.removed)

    def test_effective_container_runtime_config_is_verified_before_attachment(
        self,
    ) -> None:
        class WrongRuntimeConfig(FakeDockerBackend):
            field: str

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                result = super()._command(*args, timeout=timeout)
                if args == ("inspect", self.container_id) and not self.removed:
                    spec = json.loads(result.stdout)[0]
                    if self.field == "Path":
                        spec["Path"] = "/bin/sh"
                    elif self.field == "Args":
                        spec["Args"] = ["-c", "unexpected"]
                    elif self.field == "Config.Entrypoint":
                        spec["Config"]["Entrypoint"] = ["/bin/sh"]
                    elif self.field == "Config.Cmd":
                        spec["Config"]["Cmd"] = ["-c", "unexpected"]
                    elif self.field == "Config.WorkingDir":
                        spec["Config"]["WorkingDir"] = "/tmp"
                    elif self.field == "HostConfig.Tmpfs":
                        spec["HostConfig"]["Tmpfs"] = {"/tmp": "rw"}
                    else:
                        raise AssertionError(self.field)
                    result.stdout = json.dumps([spec]).encode()
                return result

        for field in (
            "Path",
            "Args",
            "Config.Entrypoint",
            "Config.Cmd",
            "Config.WorkingDir",
            "HostConfig.Tmpfs",
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as td:
                root = Path(td).resolve()
                backend = WrongRuntimeConfig(self.image, root)
                backend.field = field
                with mock.patch(
                    "tools.vf0_execution._capture_process",
                    return_value=self._completed_capture(),
                ) as attached:
                    with self.assertRaisesRegex(
                        ExecutionRejected, "OCI_CONTAINER_CONFIG"
                    ):
                        backend.run(
                            root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                        )
                attached.assert_not_called()
                self.assertTrue(backend.removed)

    def test_create_contract_is_read_only_network_free_nonroot_and_bounded(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            capture = self._completed_capture()
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
            entrypoint_index = create.index("--entrypoint") + 1
            self.assertEqual("/usr/local/bin/python3", create[entrypoint_index])
            self.assertEqual("sha256:" + "b" * 64, create[entrypoint_index + 1])
            self.assertEqual(
                ("-I", "-c"), create[entrypoint_index + 2 : entrypoint_index + 4]
            )
            for fragment in (
                "--platform linux/amd64",
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
                ("rm", "--force", "--volumes", backend.container_name),
                backend.calls,
            )

    def test_unbound_container_environment_is_rejected_before_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(
                self.image, root, extra_environment=("LD_PRELOAD=/tmp/unbound.so",)
            )
            capture = self._completed_capture()
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ) as attached:
                with self.assertRaisesRegex(ExecutionRejected, "OCI_ENV_CONTRACT"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            attached.assert_not_called()

    def test_fractional_cpu_contract_uses_docker_nano_cpu_rounding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root, nano_cpus=2_010_000_000)
            capture = self._completed_capture()
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
                ("rm", "--force", "--volumes", backend.container_name),
                backend.calls,
            )
            self.assertIn(("inspect", backend.container_id), backend.calls)

    def test_created_container_cannot_be_reported_as_completed(self) -> None:
        class CreatedState(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:3] == ("inspect", "--format", "{{json .State}}"):
                    self.calls.append(tuple(args))
                    return subprocess.CompletedProcess(
                        ["/usr/bin/docker"],
                        0,
                        stdout=b'{"Status":"created","Running":false,"ExitCode":0}\n',
                        stderr=b"",
                    )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = CreatedState(self.image, root)
            capture = self._completed_capture(
                125, stdout=b"", stderr=b"daemon unavailable\n"
            )
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_EXIT_STATE"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            self.assertTrue(backend.removed)

    def test_oom_killed_container_cannot_be_reported_from_wrapper_trailer(
        self,
    ) -> None:
        class OomKilled(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:3] == ("inspect", "--format", "{{json .State}}"):
                    self.calls.append(tuple(args))
                    return subprocess.CompletedProcess(
                        ["/usr/bin/docker"],
                        0,
                        stdout=(
                            b'{"Status":"exited","Running":false,'
                            b'"ExitCode":137,"OOMKilled":true}\n'
                        ),
                        stderr=b"",
                    )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = OomKilled(self.image, root)
            capture = self._completed_capture(137)
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ) as attached:
                with self.assertRaisesRegex(ExecutionRejected, "OCI_EXIT_STATE"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            attached.assert_called_once()
            self.assertTrue(backend.removed)

    def test_successful_rm_smoke_accepts_a_single_exact_absence_read_back(
        self,
    ) -> None:
        class AlreadyRemoved(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                self.calls.append(tuple(args))
                return subprocess.CompletedProcess(
                    ["/usr/bin/docker"],
                    1,
                    stdout=b"",
                    stderr=f"Error: No such object: {args[-1]}\n".encode(),
                )

        backend = AlreadyRemoved(self.image, Path("/unused"))
        with (
            mock.patch("tools.vf0_execution.time.monotonic", return_value=10.0),
            mock.patch("tools.vf0_execution.time.sleep") as sleep,
        ):
            backend._cleanup_uncertain_create(
                "gnostoa-vf0-readonly-" + "a" * 32,
                "a" * 32,
                completion_observed=True,
            )
        self.assertEqual(1, len(backend.calls))
        self.assertEqual(
            ("inspect", "gnostoa-vf0-readonly-" + "a" * 32), backend.calls[0]
        )
        sleep.assert_not_called()

    def test_attachment_failure_cannot_be_overwritten_by_container_exit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            stderr = b"daemon unavailable\n"
            capture = UntrustedCapture("completed", 125, b"", stderr, len(stderr))
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_ATTACH_STATE"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            self.assertTrue(backend.removed)

    def test_colliding_attachment_failure_status_is_rejected_without_trailer(
        self,
    ) -> None:
        class ExitOne(FakeDockerBackend):
            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:3] == ("inspect", "--format", "{{json .State}}"):
                    self.calls.append(tuple(args))
                    return subprocess.CompletedProcess(
                        ["/usr/bin/docker"],
                        0,
                        stdout=b'{"Status":"exited","Running":false,"ExitCode":1}\n',
                        stderr=b"",
                    )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = ExitOne(self.image, root)
            stderr = b"daemon connection lost\n"
            capture = UntrustedCapture("completed", 1, b"", stderr, len(stderr))
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_ATTACH_STATE"):
                    backend.run(
                        root, ["/bin/true"], ExecutionLimits(), subject=self.subject
                    )
            self.assertTrue(backend.removed)

    def test_unique_final_wrapper_trailer_allows_nonzero_container_exit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            capture = self._completed_capture(17, stderr=b"child stderr\n")
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                result = backend.run(
                    root, ["/bin/false"], ExecutionLimits(), subject=self.subject
                )
            self.assertEqual(("completed", 17), (result.termination, result.exit_code))
            self.assertEqual(b"child stderr\n", result.stderr)

    def test_trusted_wrapper_trailer_does_not_consume_evidence_budget(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        limit = 64
        marker = (
            module._OCI_EXIT_SENTINEL_PREFIX + b"0" + module._OCI_EXIT_SENTINEL_SUFFIX
        )
        script = f"import os;os.write(1,b'x'*{limit});os.write(2,{marker!r})"
        capture = module._capture_process(
            [sys.executable, "-c", script],
            cwd=None,
            limits=ExecutionLimits(timeout_seconds=3.0, output_bytes=limit),
            output_headroom_bytes=module._OCI_EXIT_TRAILER_MAX,
        )
        result = module._enforce_output_limit(
            module._unwrap_oci_completion(capture), limit
        )
        self.assertEqual(("completed", 0), (result.termination, result.exit_code))
        self.assertEqual(limit, len(result.stdout))
        self.assertEqual(b"", result.stderr)
        self.assertEqual(limit, result.observed_bytes_at_least)

    def test_child_output_over_budget_is_limited_after_trailer_strip(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        limit = 64
        marker = (
            module._OCI_EXIT_SENTINEL_PREFIX + b"0" + module._OCI_EXIT_SENTINEL_SUFFIX
        )
        script = f"import os;os.write(1,b'x'*{limit + 1});os.write(2,{marker!r})"
        capture = module._capture_process(
            [sys.executable, "-c", script],
            cwd=None,
            limits=ExecutionLimits(timeout_seconds=3.0, output_bytes=limit),
            output_headroom_bytes=module._OCI_EXIT_TRAILER_MAX,
        )
        result = module._enforce_output_limit(
            module._unwrap_oci_completion(capture), limit
        )
        self.assertEqual("output_limit", result.termination)
        self.assertIsNone(result.exit_code)
        self.assertEqual(limit, len(result.stdout) + len(result.stderr))
        self.assertEqual(limit + 1, result.observed_bytes_at_least)

    def test_expanded_output_limit_is_rebounded_to_caller_evidence_budget(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            limit = 64
            capture = UntrustedCapture(
                "output_limit",
                None,
                b"x" * (limit + module._OCI_EXIT_TRAILER_MAX),
                b"",
                limit + module._OCI_EXIT_TRAILER_MAX + 8192,
            )
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                result = backend.run(
                    root,
                    ["/bin/cat"],
                    ExecutionLimits(output_bytes=limit),
                    subject=self.subject,
                )
            self.assertEqual(
                ("output_limit", None), (result.termination, result.exit_code)
            )
            self.assertEqual(limit, len(result.stdout) + len(result.stderr))
            self.assertGreater(result.observed_bytes_at_least, limit)
            self.assertTrue(backend.removed)

    def test_spoofed_wrapper_trailer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = FakeDockerBackend(self.image, root)
            marker = b"\x1eGNOSTOA_VF0_EXIT_V1:17\x1f"
            capture = UntrustedCapture(
                "completed", 17, b"", marker + marker, len(marker) * 2
            )
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                with self.assertRaisesRegex(ExecutionRejected, "OCI_ATTACH_STATE"):
                    backend.run(
                        root, ["/bin/false"], ExecutionLimits(), subject=self.subject
                    )
            self.assertTrue(backend.removed)

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
                            stderr=f"Error: No such object: {args[-1]}\n".encode(),
                        )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = DelayedAppearance(self.image, root)
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
            capture = self._completed_capture(stdout=b"")
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

    def test_nonzero_remove_client_result_reconciles_before_failing(self) -> None:
        class NonzeroThenRemoved(FakeDockerBackend):
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
                        return subprocess.CompletedProcess(
                            ["/usr/bin/docker"],
                            1,
                            stdout=b"",
                            stderr=b"connection reset by peer",
                        )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = NonzeroThenRemoved(self.image, root)
            capture = self._completed_capture(stdout=b"")
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

    def test_nonzero_cleanup_inspect_reconciles_before_failing(self) -> None:
        class NonzeroInspectThenRemoved(FakeDockerBackend):
            def __init__(self, image: str, root: Path) -> None:
                super().__init__(image, root)
                self.remove_attempts = 0
                self.inspect_attempts = 0

            def _command(
                self, *args: str, timeout: float = 30
            ) -> subprocess.CompletedProcess[bytes]:
                if args[:2] == ("rm", "--force"):
                    self.calls.append(tuple(args))
                    self.remove_attempts += 1
                    if self.remove_attempts == 1:
                        raise ExecutionRejected("DOCKER_COMMAND_FAILED")
                if args == ("inspect", self.container_id) and self.remove_attempts > 0:
                    self.inspect_attempts += 1
                    if self.inspect_attempts == 1:
                        self.calls.append(tuple(args))
                        return subprocess.CompletedProcess(
                            ["/usr/bin/docker"],
                            1,
                            stdout=b"",
                            stderr=b"temporary daemon disconnect",
                        )
                return super()._command(*args, timeout=timeout)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            backend = NonzeroInspectThenRemoved(self.image, root)
            capture = self._completed_capture(stdout=b"")
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
            self.assertGreaterEqual(backend.inspect_attempts, 2)
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
            capture = self._completed_capture(stdout=b"")
            with mock.patch(
                "tools.vf0_execution._capture_process", return_value=capture
            ):
                with self.assertRaisesRegex(
                    ExecutionRejected, "OCI_CLEANUP_UNVERIFIED"
                ):
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


def _load_smoke_module() -> ModuleType:
    path = Path(__file__).with_name("vf0_execution_oci_smoke.py")
    spec = importlib.util.spec_from_file_location("_vf0_execution_oci_smoke", path)
    if spec is None or spec.loader is None:
        raise AssertionError("SMOKE_HELPER_LOAD")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_smoke_success_checker() -> Callable[[ExecutionObservation, bytes], None]:
    module = _load_smoke_module()
    return cast(
        Callable[[ExecutionObservation, bytes], None],
        module._expect_completed_success,
    )


class _ReadOnlyProbeTransport:
    def __init__(
        self,
        failure: BaseException | None = None,
        inspection: str = "owned",
        *,
        auto_remove: bool = False,
    ) -> None:
        self.failure = failure
        self.inspection = inspection
        self.auto_remove = auto_remove
        self.calls: list[list[str]] = []
        self.present = False
        self.name = ""
        self.nonce = ""
        self.root: Path | None = None
        self.root_mode = 0
        self.probe_mode = 0

    def run(
        self, argv: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        self.calls.append(list(argv))
        action = argv[1]
        if action == "run":
            self.present = True
            if "--name" in argv:
                self.name = argv[argv.index("--name") + 1]
            if "--label" in argv:
                self.nonce = argv[argv.index("--label") + 1].split("=", 1)[1]
            mount = argv[argv.index("--mount") + 1]
            source = next(
                part[7:] for part in mount.split(",") if part.startswith("source=")
            )
            self.root = Path(source)
            self.root_mode = self.root.stat().st_mode & 0o777
            self.probe_mode = (self.root / "writable.txt").stat().st_mode & 0o777
            if self.failure is not None:
                raise self.failure
            if self.auto_remove and "--rm" in argv:
                self.present = False
            return subprocess.CompletedProcess(
                list(argv),
                0,
                stdout=b'{"rootfs_read_only":true,"workspace_bind_read_only":true}',
                stderr=b"",
            )
        if action == "inspect":
            if self.inspection == "unavailable":
                return subprocess.CompletedProcess(
                    list(argv),
                    1,
                    stdout=b"",
                    stderr=b"dial unix /var/run/docker.sock: connect: no such file or directory",
                )
            if not self.present:
                return subprocess.CompletedProcess(
                    list(argv),
                    1,
                    stdout=b"[]\n",
                    stderr=f"Error: No such object: {self.name}\n".encode(),
                )
            nonce = "foreign" if self.inspection == "foreign" else self.nonce
            return subprocess.CompletedProcess(
                list(argv),
                0,
                stdout=json.dumps(
                    [{"Config": {"Labels": {"gnostoa.vf0.cleanup-token": nonce}}}]
                ).encode(),
                stderr=b"",
            )
        if action == "rm":
            if self.root is None or not self.root.is_dir():
                raise AssertionError("PROBE_MOUNT_REMOVED_BEFORE_CONTAINER")
            self.present = False
            return subprocess.CompletedProcess(list(argv), 0, stdout=b"", stderr=b"")
        raise AssertionError(f"Unexpected probe command: {argv}")


class VF0SmokeContractTests(unittest.TestCase):
    def test_read_only_probe_cleans_after_timeout_and_interruption(self) -> None:
        module = _load_smoke_module()
        for failure in (
            subprocess.TimeoutExpired("/usr/bin/docker run", 30),
            KeyboardInterrupt(),
        ):
            with self.subTest(failure=type(failure).__name__):
                transport = _ReadOnlyProbeTransport(failure=failure)
                expected_type = (
                    ExecutionRejected
                    if isinstance(failure, subprocess.TimeoutExpired)
                    else KeyboardInterrupt
                )
                with mock.patch("subprocess.run", side_effect=transport.run):
                    with self.assertRaises(expected_type) as caught:
                        module._probe_read_only_behavior(module.FIXED_IMAGE)
                self.assertIs(type(caught.exception), expected_type)
                if isinstance(failure, subprocess.TimeoutExpired):
                    self.assertEqual("DOCKER_COMMAND_FAILED", str(caught.exception))
                    self.assertIs(failure, caught.exception.__cause__)
                else:
                    self.assertIs(failure, caught.exception)
                self.assertFalse(transport.present, "probe container survived failure")
                self.assertTrue(transport.name)
                self.assertTrue(transport.nonce)
                self.assertEqual(
                    ["run", "inspect", "inspect", "rm", "inspect"],
                    [call[1] for call in transport.calls],
                )
                for call in transport.calls[1:]:
                    self.assertEqual(transport.name, call[-1])

    def test_read_only_probe_preserves_writable_target_success_control(self) -> None:
        module = _load_smoke_module()
        transport = _ReadOnlyProbeTransport()
        with mock.patch("subprocess.run", side_effect=transport.run):
            result = module._probe_read_only_behavior(module.FIXED_IMAGE)
        self.assertEqual(
            {"rootfs_read_only": True, "workspace_bind_read_only": True}, result
        )
        self.assertEqual(0o777, transport.root_mode)
        self.assertEqual(0o666, transport.probe_mode)
        self.assertIn("--read-only", transport.calls[0])
        mount = transport.calls[0][transport.calls[0].index("--mount") + 1]
        self.assertTrue(mount.endswith(",target=/probe,readonly"))

    def test_read_only_probe_verifies_native_absence_after_successful_auto_remove(
        self,
    ) -> None:
        module = _load_smoke_module()
        transport = _ReadOnlyProbeTransport(auto_remove=True)
        with (
            mock.patch("subprocess.run", side_effect=transport.run),
            mock.patch(
                "tools.vf0_execution.time.monotonic", side_effect=[0.0, 0.0, 2.0]
            ),
            mock.patch("tools.vf0_execution.time.sleep") as sleep,
        ):
            result = module._probe_read_only_behavior(module.FIXED_IMAGE)
        self.assertEqual(
            {"rootfs_read_only": True, "workspace_bind_read_only": True}, result
        )
        run = transport.calls[0]
        self.assertIn("--rm", run)
        self.assertTrue(transport.name.startswith("gnostoa-vf0-readonly-"))
        self.assertEqual(transport.name, run[run.index("--name") + 1])
        self.assertEqual(
            f"gnostoa.vf0.cleanup-token={transport.nonce}",
            run[run.index("--label") + 1],
        )
        self.assertFalse(transport.present)
        self.assertEqual(["run", "inspect"], [call[1] for call in transport.calls])
        for call in transport.calls[1:]:
            self.assertEqual(transport.name, call[-1])
        sleep.assert_not_called()

    def test_read_only_probe_does_not_ignore_unverified_cleanup(self) -> None:
        module = _load_smoke_module()
        for inspection, reason in (
            ("foreign", "OCI_CLEANUP_OWNERSHIP"),
            ("unavailable", "OCI_CLEANUP_UNVERIFIED"),
        ):
            with self.subTest(inspection=inspection):
                transport = _ReadOnlyProbeTransport(inspection=inspection)
                with mock.patch("subprocess.run", side_effect=transport.run):
                    with self.assertRaisesRegex(ExecutionRejected, reason):
                        module._probe_read_only_behavior(module.FIXED_IMAGE)
                self.assertTrue(transport.present)
                self.assertNotIn("rm", [call[1] for call in transport.calls])

    def _observation(
        self, termination: str, exit_code: int | None, stdout: bytes
    ) -> ExecutionObservation:
        return ExecutionObservation(
            subject=GitSubject(commit="a" * 40, tree="b" * 40),
            evidence_sha256=(("tests/e.py", "c" * 64),),
            command_sha256="sha256:" + "e" * 64,
            limits_sha256="sha256:" + "f" * 64,
            backend_identity="gnostoa-docker-oci-v1",
            runtime_identity="sha256:" + "1" * 64,
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
