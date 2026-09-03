from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools.experiment import execution as runner

_CONTAINER_ID = "e" * 64
_INTERNAL_NETWORK_ID = "a" * 64
_EXTERNAL_NETWORK_ID = "b" * 64
_RELAY_ID = "d" * 64


class ExperimentRunnerReviewRegressionTests(unittest.TestCase):
    def write_run_profile(self, root: Path) -> Path:
        project = root / "project"
        evidence = root / "evidence"
        project.mkdir()
        evidence.mkdir()
        profile = {
            "schema": runner.PROFILE_SCHEMA,
            "read_only_roots": [],
            "project_root": str(project.resolve()),
            "evidence_root": str(evidence.resolve()),
            "temporary_roots": [],
            "excluded_roots": [],
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
            "timeout_seconds": 60,
        }
        path = root / "profile.yaml"
        path.write_text(yaml.safe_dump(profile, sort_keys=True), encoding="utf-8")
        return path

    @staticmethod
    def writable_mount_sources(argv: list[str]) -> list[Path]:
        sources: list[Path] = []
        for index, value in enumerate(argv[:-1]):
            if value != "--mount":
                continue
            spec = argv[index + 1]
            fields = dict(
                field.split("=", 1) for field in spec.split(",") if "=" in field
            )
            if fields.get("type") != "bind" or "readonly" in spec:
                continue
            source = fields.get("source")
            if source:
                sources.append(Path(source))
        return sources

    def test_production_run_attests_original_coordinator_capture_bytes(self) -> None:
        captured = b"captured-by-coordinator\n"
        forged = b"replacement-created-by-untrusted-process\n"

        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-review-red-") as raw:
            profile_path = self.write_run_profile(Path(raw))
            create_argv: list[str] = []

            def docker_checked(*args: str, timeout: int = 60) -> str:
                del timeout
                self.assertEqual("create", args[0])
                create_argv.extend(args)
                return _CONTAINER_ID

            def fake_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, stderr, timeout
                stdout_file = stdout
                stdout_file.write(captured)
                stdout_file.flush()

                stdout_path = Path(stdout_file.name)
                writable_sources = self.writable_mount_sources(create_argv)
                if any(
                    stdout_path == source or stdout_path.is_relative_to(source)
                    for source in writable_sources
                ):
                    stdout_path.unlink()
                    stdout_path.write_bytes(forged)

                return subprocess.CompletedProcess(argv, 0)

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
                    side_effect=docker_checked,
                ),
                mock.patch.object(
                    runner.backend, "container_exit_code", return_value=0
                ),
                mock.patch.object(runner.backend, "ensure_container_absent"),
                mock.patch.object(runner.subprocess, "run", side_effect=fake_run),
            ):
                exit_code, payload = runner.run_profile_command(
                    profile_path,
                    "auto",
                    ["python", "-c", "print('fixture')"],
                )

            self.assertEqual(0, exit_code)
            self.assertEqual("PASS", payload["status"])
            stdout_identity = payload["stdout"]
            self.assertIsInstance(stdout_identity, dict)
            self.assertEqual(
                hashlib.sha256(captured).hexdigest(),
                stdout_identity["sha256"],
                "coordinator evidence identity must bind the bytes captured on its own file descriptor, not a path the untrusted process can replace",
            )

    def test_production_run_retains_requested_and_resolved_backend_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-review-red-") as raw:
            profile_path = self.write_run_profile(Path(raw))

            def fake_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, timeout
                stdout.write(b"ok\n")
                stderr.write(b"")
                return subprocess.CompletedProcess(argv, 0)

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
                mock.patch.object(
                    runner.backend, "container_exit_code", return_value=0
                ),
                mock.patch.object(runner.backend, "ensure_container_absent"),
                mock.patch.object(runner.subprocess, "run", side_effect=fake_run),
            ):
                exit_code, payload = runner.run_profile_command(
                    profile_path,
                    "auto",
                    ["python", "-V"],
                )

            self.assertEqual(0, exit_code)
            self.assertEqual("auto", payload.get("backend_requested"))
            self.assertEqual("oci", payload.get("backend_resolved"))

    def test_restricted_run_quiesces_relay_before_retaining_network_logs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-review-red-") as raw:
            root = Path(raw)
            profile_path = self.write_run_profile(root)
            profile = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            profile["network"] = {
                "mode": "restricted",
                "allow": ["provider.example:443"],
            }
            profile["runtime"]["relay_image"] = f"sha256:{'d' * 64}"
            profile_path.write_text(
                yaml.safe_dump(profile, sort_keys=True),
                encoding="utf-8",
            )

            def fake_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, timeout
                stdout.write(b"ok\n")
                stderr.write(b"")
                return subprocess.CompletedProcess(argv, 0)

            with (
                mock.patch.object(
                    runner.backend,
                    "probe_backend",
                    return_value=runner.ProbeResult("AVAILABLE", "oci", []),
                ),
                mock.patch.object(
                    runner.backend,
                    "create_restricted_network",
                    return_value=(
                        _INTERNAL_NETWORK_ID,
                        _EXTERNAL_NETWORK_ID,
                        _RELAY_ID,
                    ),
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
                mock.patch.object(
                    runner.backend, "container_exit_code", return_value=0
                ),
                mock.patch.object(runner.backend, "ensure_container_absent"),
                mock.patch.object(
                    runner.backend,
                    "ensure_container_stopped",
                    create=True,
                ) as ensure_stopped,
                mock.patch.object(runner.backend, "safe_remove_container"),
                mock.patch.object(runner.backend, "safe_remove_network"),
                mock.patch.object(runner.subprocess, "run", side_effect=fake_run),
            ):

                def retain_logs(_container: str, output: Path) -> None:
                    self.assertTrue(
                        ensure_stopped.called,
                        "relay must be quiesced before network logs are retained",
                    )
                    output.write_text(
                        '{"event":"READY"}\n{"event":"CLOSED"}\n',
                        encoding="utf-8",
                    )

                with mock.patch.object(
                    runner.capture,
                    "stream_container_logs",
                    side_effect=retain_logs,
                ):
                    exit_code, payload = runner.run_profile_command(
                        profile_path,
                        "oci",
                        ["python", "-V"],
                    )

            self.assertEqual(0, exit_code)
            self.assertEqual("PASS", payload["status"])
            ensure_stopped.assert_called_once_with(_RELAY_ID)
            self.assertIsNotNone(payload["network_evidence"])


if __name__ == "__main__":
    unittest.main()
