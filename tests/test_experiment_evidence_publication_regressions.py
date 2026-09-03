from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools.experiment import execution as runner

_CONTAINER_ID = "e" * 64


class ExperimentEvidencePublicationRegressionTests(unittest.TestCase):
    def write_profile(
        self,
        root: Path,
        *,
        evidence_inside_project: bool = False,
    ) -> tuple[Path, Path, Path]:
        project = root / "project"
        project.mkdir()
        evidence = (
            project / "evidence" if evidence_inside_project else root / "evidence"
        )
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
        }
        profile_path = root / "profile.yaml"
        profile_path.write_text(
            yaml.safe_dump(profile, sort_keys=True), encoding="utf-8"
        )
        return profile_path, project, evidence

    def run_with_fake_executor(
        self,
        profile_path: Path,
        side_effect: object,
    ) -> tuple[int, dict[str, object]]:
        with (
            mock.patch.object(
                runner.backend,
                "probe_backend",
                return_value=runner.ProbeResult("AVAILABLE", "oci", []),
            ),
            mock.patch.object(
                runner.backend,
                "docker_executable",
                return_value="/usr/bin/docker",
            ),
            mock.patch.object(
                runner.backend,
                "docker_checked",
                return_value=_CONTAINER_ID,
            ),
            mock.patch.object(runner.backend, "container_exit_code", return_value=0),
            mock.patch.object(runner.backend, "ensure_container_absent"),
            mock.patch.object(runner.subprocess, "run", side_effect=side_effect),
        ):
            return runner.run_profile_command(
                profile_path,
                "oci",
                ["python", "-c", "print('fixture')"],
            )

    def test_executor_created_stdout_symlink_cannot_redirect_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-evidence-red-") as raw:
            root = Path(raw)
            profile_path, _project, evidence = self.write_profile(root)
            outside = root / "outside-stdout.txt"

            def fake_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, timeout
                stdout.write(b"captured-stdout\n")
                stderr.write(b"")
                (evidence / "run-stdout.log").symlink_to(outside)
                return subprocess.CompletedProcess(argv, 0)

            with self.assertRaises((OSError, runner.RunnerError)):
                self.run_with_fake_executor(profile_path, fake_run)

            self.assertFalse(outside.exists())
            self.assertTrue((evidence / "run-stdout.log").is_symlink())

    def test_executor_created_result_symlink_cannot_redirect_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-evidence-red-") as raw:
            root = Path(raw)
            profile_path, _project, evidence = self.write_profile(root)
            outside = root / "outside-result.json"

            def fake_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, timeout
                stdout.write(b"captured-stdout\n")
                stderr.write(b"")
                (evidence / "run-result.json").symlink_to(outside)
                return subprocess.CompletedProcess(argv, 0)

            with self.assertRaises((OSError, runner.RunnerError)):
                self.run_with_fake_executor(profile_path, fake_run)

            self.assertFalse(outside.exists())
            self.assertTrue((evidence / "run-result.json").is_symlink())

    def test_executor_cannot_replace_evidence_root_namespace_before_publication(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-evidence-red-") as raw:
            root = Path(raw)
            profile_path, project, evidence = self.write_profile(
                root,
                evidence_inside_project=True,
            )
            moved_evidence = project / "evidence-owned-moved"

            def fake_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, timeout
                stdout.write(b"captured-stdout\n")
                stderr.write(b"")
                evidence.rename(moved_evidence)
                evidence.mkdir()
                (evidence / "foreign-sentinel.txt").write_text(
                    "foreign\n",
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(argv, 0)

            with self.assertRaises(runner.RunnerError):
                self.run_with_fake_executor(profile_path, fake_run)

            self.assertEqual(
                "foreign\n",
                (evidence / "foreign-sentinel.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((evidence / "run-stdout.log").exists())
            self.assertFalse((evidence / "run-stderr.log").exists())
            self.assertFalse((evidence / "run-result.json").exists())
            self.assertTrue(moved_evidence.is_dir())


if __name__ == "__main__":
    unittest.main()
