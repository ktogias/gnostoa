"""Work Item 195: workspace-size observation must be symlink-safe.

The runner measures the project workspace after the container exits and before
retained run artifacts are published. It refused any nested symlink outright, so a
subject whose own frozen tree legitimately contains one lost its run evidence after
the work had already been done.

Every fixture here is synthetic. No Phase-D subject, oracle, key or evidence byte
participates, and no hidden oracle runs.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools.experiment import capture
from tools.experiment import execution as runner
from tools.experiment.profile import RunnerError

_CONTAINER_ID = "f" * 64
_METHOD = "recursive-lstat-size-v2"


class SymlinkSizeObservationTests(unittest.TestCase):
    """Nested links contribute their own lstat size and are never followed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="gnostoa-symlink-size-")
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()

    def test_ordinary_files_are_summed_under_the_new_method_label(self) -> None:
        (self.project / "a.txt").write_bytes(b"x" * 10)
        (self.project / "nested").mkdir()
        (self.project / "nested" / "b.txt").write_bytes(b"y" * 15)
        observed, method = capture.measured_path_size(self.project)
        self.assertEqual(observed, 25)
        self.assertEqual(method, _METHOD)

    def test_file_symlink_contributes_its_own_size_not_its_target(self) -> None:
        target = self.project / "target.txt"
        target.write_bytes(b"z" * 4096)
        link = self.project / "link.txt"
        link.symlink_to("target.txt")
        observed, _ = capture.measured_path_size(self.project)
        # 4096 for the regular file plus the link's own lstat size, which is the
        # byte length of the stored path -- never the 4096-byte target again.
        self.assertEqual(observed, 4096 + link.lstat().st_size)
        self.assertLess(observed, 4096 * 2)

    def test_directory_symlink_is_counted_but_never_traversed(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "huge.bin").write_bytes(b"q" * 100_000)
        link = self.project / "linked-dir"
        link.symlink_to(outside, target_is_directory=True)
        observed, method = capture.measured_path_size(self.project)
        self.assertEqual(method, _METHOD)
        # The 100 kB behind the link must not be counted: it was never entered.
        self.assertEqual(observed, link.lstat().st_size)

    def test_broken_symlink_does_not_raise(self) -> None:
        (self.project / "dangling").symlink_to("nowhere-at-all")
        observed, _ = capture.measured_path_size(self.project)
        self.assertEqual(observed, (self.project / "dangling").lstat().st_size)

    def test_symlink_to_an_absolute_external_path_is_not_followed(self) -> None:
        secret = self.root / "outside-secret.txt"
        secret.write_bytes(b"s" * 50_000)
        (self.project / "escape").symlink_to(secret)
        observed, _ = capture.measured_path_size(self.project)
        self.assertLess(observed, 50_000)

    def test_symlink_loop_terminates(self) -> None:
        (self.project / "loop").symlink_to(self.project, target_is_directory=True)
        observed, method = capture.measured_path_size(self.project)
        self.assertEqual(method, _METHOD)
        self.assertGreaterEqual(observed, 0)

    def test_root_symlink_is_still_refused(self) -> None:
        real = self.root / "real-project"
        real.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(RunnerError) as caught:
            capture.measured_path_size(alias)
        self.assertIn("size-check-refuses-symlink", str(caught.exception))

    def test_single_regular_file_keeps_its_own_method_label(self) -> None:
        single = self.project / "one.bin"
        single.write_bytes(b"a" * 7)
        observed, method = capture.measured_path_size(single)
        self.assertEqual((observed, method), (7, "lstat-size-v1"))

    def test_no_symlink_target_is_opened_or_stat_followed(self) -> None:
        target = self.project / "target.txt"
        target.write_bytes(b"t" * 32)
        (self.project / "link.txt").symlink_to("target.txt")
        followed: list[str] = []
        real_stat = os.stat

        def watched_stat(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            if str(path).endswith("link.txt") and kwargs.get("follow_symlinks", True):
                followed.append(str(path))
            return real_stat(path, *args, **kwargs)

        with mock.patch.object(os, "stat", side_effect=watched_stat):
            capture.measured_path_size(self.project)
        self.assertEqual(followed, [], "a link must never be stat-followed")


class SymlinkBearingRunRetainsEvidenceTests(unittest.TestCase):
    """End to end: a symlink-bearing project must not lose its run artifacts."""

    def write_profile(self, root: Path) -> tuple[Path, Path, Path]:
        project = root / "project"
        project.mkdir()
        evidence = root / "evidence"
        evidence.mkdir()
        excluded = root / "excluded"
        excluded.mkdir()
        profile = {
            "schema": runner.PROFILE_SCHEMA,
            "read_only_roots": [],
            "project_root": str(project.resolve()),
            "evidence_root": str(evidence.resolve()),
            "temporary_roots": [],
            "excluded_roots": [str(excluded.resolve())],
            "environment_allowlist": [],
            "credential_environment": [],
            "input_identities": [f"fixture={'b' * 64}"],
            "executor": {
                "id": "fixture-executor",
                "version": "1",
                "config_sha256": "a" * 64,
            },
            "network": {"mode": "none", "allow": []},
            "runtime": {"image": f"sha256:{'c' * 64}"},
            "timeout_seconds": 17,
            # The observation only runs when a limit is configured.
            "archive_limit_bytes": 67_108_864,
        }
        path = root / "profile.yaml"
        path.write_text(yaml.safe_dump(profile, sort_keys=True), encoding="utf-8")
        return path, project, evidence

    def test_symlink_in_project_does_not_discard_completed_run_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-symlink-e2e-") as raw:
            root = Path(raw)
            profile_path, project, evidence = self.write_profile(root)
            # A subject that legitimately carries a relative symlink, exactly as a
            # real frozen tree can.
            (project / "docs").mkdir()
            (project / "docs" / "contributing.md").write_bytes(b"# contributing\n")
            (project / "CONTRIBUTING.md").symlink_to("docs/contributing.md")

            def fake_run(argv, *, check, stdout, stderr, timeout):  # type: ignore[no-untyped-def]
                del check, timeout
                stdout.write(b"captured-stdout\n")
                stderr.write(b"")
                return subprocess.CompletedProcess(argv, 0)

            with (
                mock.patch.object(
                    runner.backend,
                    "probe_backend",
                    return_value=runner.ProbeResult("AVAILABLE", "oci", []),
                ),
                mock.patch.object(
                    runner.backend, "docker_executable", return_value="/usr/bin/docker"
                ),
                mock.patch.object(
                    runner.backend, "docker_checked", return_value=_CONTAINER_ID
                ),
                mock.patch.object(
                    runner.backend, "container_exit_code", return_value=0
                ),
                mock.patch.object(runner.backend, "ensure_container_absent"),
                mock.patch.object(runner.subprocess, "run", side_effect=fake_run),
            ):
                exit_code, payload = runner.run_profile_command(
                    profile_path, "oci", ["python", "-c", "print('fixture')"]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["status"], "PASS")
            observation = payload["workspace_size_observation"]
            self.assertEqual(observation["measurement"], _METHOD)
            # The work is not thrown away: retained artifacts exist on disk.
            self.assertTrue((evidence / "run-stdout.log").is_file())
            self.assertTrue((evidence / "run-stderr.log").is_file())
            self.assertTrue((evidence / "run-result.json").is_file())


if __name__ == "__main__":
    unittest.main()
