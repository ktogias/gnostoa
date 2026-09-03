from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools.experiment import execution as runner
from tools.experiment import handoff, packaging, profile

_CONTAINER_ID = "e" * 64


class ExperimentFinalSecurityRegressionTests(unittest.TestCase):
    def make_run_profile(self, root: Path, *, timeout_seconds: int = 17) -> Path:
        project = root / "project"
        evidence = root / "evidence"
        temporary = root / "temporary"
        excluded = root / "excluded"
        for path in (project, evidence, temporary, excluded):
            path.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": runner.PROFILE_SCHEMA,
            "read_only_roots": [],
            "project_root": str(project.resolve()),
            "evidence_root": str(evidence.resolve()),
            "temporary_roots": [str(temporary.resolve())],
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
            "timeout_seconds": timeout_seconds,
        }
        path = root / "profile.yaml"
        path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        return path

    def test_read_only_root_cannot_overlap_any_writable_surface(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            root = Path(raw)
            project = root / "project"
            evidence = root / "evidence"
            temporary = root / "temporary"
            excluded = root / "excluded"
            read_inside_project = project / "admitted-input"
            for path in (
                project,
                evidence,
                temporary,
                excluded,
                read_inside_project,
            ):
                path.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": runner.PROFILE_SCHEMA,
                "read_only_roots": [str(read_inside_project.resolve())],
                "project_root": str(project.resolve()),
                "evidence_root": str(evidence.resolve()),
                "temporary_roots": [str(temporary.resolve())],
                "excluded_roots": [str(excluded.resolve())],
                "environment_allowlist": [],
                "credential_environment": [],
                "input_identities": [],
                "network": {"mode": "none", "allow": []},
            }

            reasons = profile.validate_profile_data(payload, for_run=False)

            self.assertIn("read-only-root-overlaps-writable-surface", reasons)

    def test_mount_source_path_with_comma_is_rejected_before_docker_grammar(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            root = Path(raw)
            read_root = root / "input,readonly"
            project = root / "project"
            evidence = root / "evidence"
            temporary = root / "temporary"
            excluded = root / "excluded"
            for path in (read_root, project, evidence, temporary, excluded):
                path.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": runner.PROFILE_SCHEMA,
                "read_only_roots": [str(read_root.resolve())],
                "project_root": str(project.resolve()),
                "evidence_root": str(evidence.resolve()),
                "temporary_roots": [str(temporary.resolve())],
                "excluded_roots": [str(excluded.resolve())],
                "environment_allowlist": [],
                "credential_environment": [],
                "input_identities": [],
                "network": {"mode": "none", "allow": []},
            }

            reasons = profile.validate_profile_data(payload, for_run=False)

            self.assertIn("mount-source-path-contains-comma", reasons)

    def test_run_requires_explicit_positive_timeout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            root = Path(raw)
            profile_path = self.make_run_profile(root)
            payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            payload.pop("timeout_seconds")

            reasons = profile.validate_profile_data(payload, for_run=True)

            self.assertIn("run-timeout-seconds-required", reasons)

    def test_timeout_uses_declared_limit_and_reaps_owned_executor_container_id(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            profile_path = self.make_run_profile(Path(raw), timeout_seconds=17)
            observed: dict[str, object] = {}

            def timeout_run(
                argv: list[str],
                *,
                check: bool,
                stdout: object,
                stderr: object,
                timeout: int,
            ) -> subprocess.CompletedProcess[bytes]:
                del check, stdout, stderr
                observed["argv"] = list(argv)
                observed["timeout"] = timeout
                raise subprocess.TimeoutExpired(argv, timeout)

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
                mock.patch.object(runner.backend, "ensure_container_absent") as ensure_absent,
                mock.patch.object(runner.subprocess, "run", side_effect=timeout_run),
            ):
                with self.assertRaises(subprocess.TimeoutExpired):
                    runner.run_profile_command(
                        profile_path,
                        "oci",
                        ["python", "-c", "while True: pass"],
                    )

            self.assertEqual(17, observed.get("timeout"))
            argv = observed.get("argv")
            self.assertEqual(
                ["/usr/bin/docker", "start", "--attach", _CONTAINER_ID],
                argv,
            )
            ensure_absent.assert_called_once_with(_CONTAINER_ID)

    def test_run_backend_unavailable_is_nonzero_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            profile_path = self.make_run_profile(Path(raw))
            with mock.patch.object(
                runner.backend,
                "probe_backend",
                return_value=runner.ProbeResult(
                    "BLOCKED", None, ["docker-daemon-unavailable"]
                ),
            ):
                exit_code, payload = runner.run_profile_command(
                    profile_path,
                    "oci",
                    ["python", "-V"],
                )

            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])

    def test_handoff_failure_cleanup_never_deletes_replacement_bundle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            publish_parent = root / "publish"
            publish_parent.mkdir()
            bundle = publish_parent / "bundle"
            moved_owned_bundle = publish_parent / "owned-bundle-moved"

            def replace_bundle_then_fail(
                _source_root: Path,
                _snapshot_fd: int,
            ) -> list[dict[str, object]]:
                bundle.rename(moved_owned_bundle)
                bundle.mkdir()
                (bundle / "sentinel.txt").write_text("foreign\n", encoding="utf-8")
                raise handoff.HandoffError("forced-after-bundle-replacement")

            with mock.patch.object(
                handoff,
                "_source_members_and_copy_fd",
                side_effect=replace_bundle_then_fail,
            ):
                exit_code, payload = handoff.freeze_handoff(
                    source,
                    bundle,
                    [f"fixture={'a' * 64}"],
                )

            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertTrue(bundle.is_dir())
            self.assertEqual(
                "foreign\n",
                (bundle / "sentinel.txt").read_text(encoding="utf-8"),
            )

    def test_packager_failure_cleanup_never_unlinks_post_publish_replacement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            bundle = root / "bundle"
            freeze_code, freeze_payload = handoff.freeze_handoff(
                source,
                bundle,
                [f"fixture={'a' * 64}"],
            )
            self.assertEqual(0, freeze_code, freeze_payload)
            handoff_path = bundle / "handoff.json"
            output = root / "candidate.tar"
            real_link = packaging.os.link
            replaced = False

            def publish_then_replace(
                source_name: object,
                target_name: object,
                *args: object,
                **kwargs: object,
            ) -> object:
                nonlocal replaced
                result = real_link(source_name, target_name, *args, **kwargs)
                output.unlink()
                output.write_bytes(b"foreign-after-publication\n")
                replaced = True
                return result

            with mock.patch.object(
                packaging.os,
                "link",
                side_effect=publish_then_replace,
            ):
                exit_code, payload = packaging.create_package(
                    handoff_path,
                    output,
                    1_048_576,
                )

            self.assertTrue(replaced)
            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertTrue(output.is_file())
            self.assertEqual(b"foreign-after-publication\n", output.read_bytes())

    def test_packager_canonicalizes_handoff_bundle_before_output_containment(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="gnostoa-final-red-") as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            (source / "candidate.txt").write_text("candidate\n", encoding="utf-8")
            bundle = root / "bundle"
            freeze_code, freeze_payload = handoff.freeze_handoff(
                source,
                bundle,
                [f"fixture={'a' * 64}"],
            )
            self.assertEqual(0, freeze_code, freeze_payload)
            alias = root / "bundle-alias"
            alias.symlink_to(bundle, target_is_directory=True)
            output = bundle / "candidate.tar"

            exit_code, payload = packaging.create_package(
                alias / "handoff.json",
                output,
                1_048_576,
            )

            self.assertEqual(2, exit_code)
            self.assertEqual("BLOCKED", payload["status"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
