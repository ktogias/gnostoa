from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools.experiment import backend, execution, smoke
from tools.experiment.profile import RunnerError

_CONTAINER_ID = "c" * 64
_INTERNAL_NETWORK_ID = "a" * 64
_EXTERNAL_NETWORK_ID = "b" * 64
_RELAY_ID = "d" * 64


class ExperimentDockerOwnershipRegressionTests(unittest.TestCase):
    def write_run_profile(self, root: Path) -> Path:
        project = root / "project"
        evidence = root / "evidence"
        project.mkdir()
        evidence.mkdir()
        payload = {
            "schema": execution.PROFILE_SCHEMA,
            "read_only_roots": [],
            "project_root": str(project.resolve()),
            "evidence_root": str(evidence.resolve()),
            "temporary_roots": [],
            "excluded_roots": [],
            "environment_allowlist": [],
            "credential_environment": [],
            "input_identities": [f"fixture={'e' * 64}"],
            "executor": {
                "id": "fixture-executor",
                "version": "1",
                "config_sha256": "f" * 64,
            },
            "network": {"mode": "none", "allow": []},
            "runtime": {"image": f"sha256:{'1' * 64}"},
            "timeout_seconds": 17,
        }
        profile = root / "profile.yaml"
        profile.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        return profile

    def test_failed_network_creation_never_cleans_up_guessed_names(self) -> None:
        with (
            mock.patch.object(
                backend,
                "unique_name",
                side_effect=[
                    "generated-internal",
                    "generated-external",
                    "generated-relay",
                ],
            ),
            mock.patch.object(
                backend,
                "docker_checked",
                side_effect=RunnerError("simulated-name-collision"),
            ),
            mock.patch.object(backend, "safe_remove_container") as remove_container,
            mock.patch.object(backend, "safe_remove_network") as remove_network,
        ):
            with self.assertRaises(RunnerError):
                backend.create_restricted_network("relay-image", ["provider:443"])

        remove_container.assert_not_called()
        remove_network.assert_not_called()

    def test_partial_network_creation_cleans_up_only_returned_object_ids(self) -> None:
        calls = 0

        def create_then_fail(*args: str, timeout: int = 60) -> str:
            nonlocal calls
            del timeout
            calls += 1
            if calls == 1:
                self.assertEqual(
                    ("network", "create", "--internal", "generated-internal"), args
                )
                return _INTERNAL_NETWORK_ID
            raise RunnerError("simulated-second-create-collision")

        with (
            mock.patch.object(
                backend,
                "unique_name",
                side_effect=[
                    "generated-internal",
                    "generated-external",
                    "generated-relay",
                ],
            ),
            mock.patch.object(backend, "docker_checked", side_effect=create_then_fail),
            mock.patch.object(backend, "safe_remove_container") as remove_container,
            mock.patch.object(backend, "safe_remove_network") as remove_network,
        ):
            with self.assertRaises(RunnerError):
                backend.create_restricted_network("relay-image", ["provider:443"])

        remove_container.assert_not_called()
        remove_network.assert_called_once_with(_INTERNAL_NETWORK_ID)

    def test_restricted_topology_returns_daemon_object_ids_not_generated_names(
        self,
    ) -> None:
        responses = iter(
            [
                _INTERNAL_NETWORK_ID,
                _EXTERNAL_NETWORK_ID,
                _RELAY_ID,
                "",
            ]
        )

        def checked(*args: str, timeout: int = 60) -> str:
            del args, timeout
            return next(responses)

        with (
            mock.patch.object(
                backend,
                "unique_name",
                side_effect=[
                    "generated-internal",
                    "generated-external",
                    "generated-relay",
                ],
            ),
            mock.patch.object(backend, "docker_checked", side_effect=checked),
            mock.patch.object(backend, "wait_for_log") as wait_for_log,
        ):
            topology = backend.create_restricted_network(
                "relay-image",
                ["provider:443"],
            )

        self.assertEqual(
            (_INTERNAL_NETWORK_ID, _EXTERNAL_NETWORK_ID, _RELAY_ID),
            topology,
        )
        wait_for_log.assert_called_once_with(_RELAY_ID, '"event": "READY"')

    def test_executor_is_created_before_start_and_cleanup_uses_created_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-docker-owner-red-") as raw:
            profile_path = self.write_run_profile(Path(raw))
            observed_start: list[str] = []

            def checked(*args: str, timeout: int = 60) -> str:
                del timeout
                if args and args[0] == "create":
                    return _CONTAINER_ID
                raise AssertionError(f"unexpected docker_checked call: {args!r}")

            def start_attached(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, timeout
                observed_start.extend(argv)
                stdout.write(b"owned-output\n")
                stderr.write(b"")
                return subprocess.CompletedProcess(argv, 0)

            with (
                mock.patch.object(
                    execution.backend,
                    "probe_backend",
                    return_value=execution.ProbeResult("AVAILABLE", "oci", []),
                ),
                mock.patch.object(
                    execution.backend,
                    "docker_executable",
                    return_value="/usr/bin/docker",
                ),
                mock.patch.object(
                    execution.backend, "docker_checked", side_effect=checked
                ),
                mock.patch.object(
                    execution.backend,
                    "container_exit_code",
                    return_value=0,
                    create=True,
                ),
                mock.patch.object(
                    execution.backend, "ensure_container_absent"
                ) as reap,
                mock.patch.object(
                    execution.subprocess, "run", side_effect=start_attached
                ),
            ):
                exit_code, payload = execution.run_profile_command(
                    profile_path,
                    "oci",
                    ["python", "-V"],
                )

            self.assertEqual(0, exit_code)
            self.assertEqual("PASS", payload["status"])
            self.assertEqual(
                ["/usr/bin/docker", "start", "--attach", _CONTAINER_ID],
                observed_start,
            )
            reap.assert_called_once_with(_CONTAINER_ID)

    def test_smoke_failed_creation_does_not_remove_generated_names(self) -> None:
        with (
            mock.patch.object(
                smoke,
                "probe_backend",
                return_value=backend.ProbeResult("AVAILABLE", "oci", []),
            ),
            mock.patch.object(
                smoke,
                "unique_name",
                side_effect=[
                    "generated-internal",
                    "generated-external",
                    "generated-target",
                    "generated-relay",
                ],
            ),
            mock.patch.object(
                smoke,
                "docker_checked",
                side_effect=RunnerError("simulated-name-collision"),
            ),
            mock.patch.object(smoke, "safe_remove_container") as remove_container,
            mock.patch.object(smoke, "safe_remove_network") as remove_network,
        ):
            result = smoke.run_smoke_oci("image", "relay-image")

        self.assertEqual("FAIL", result["status"])
        remove_container.assert_not_called()
        remove_network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
