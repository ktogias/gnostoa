from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any
from unittest import mock

import yaml

from tools import adoption_check
from tools.check_runtime_lock import public_surface_digest
from tools.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1" * 40
IMAGE = f"registry.example.org/gnostoa@sha256:{'2' * 64}"


def _native_observation(
    *,
    suite: str = "fast",
    binding: str = "3" * 64,
    entry: str = "./ci/verify",
) -> dict[str, object]:
    return {
        "schema": adoption_check.OBSERVATION_SCHEMA,
        "suite": suite,
        "invocation_binding": binding,
        "route_kind": "native",
        "runtime_identity": [
            {
                "kind": "native-executable",
                "role": "suite-runtime",
                "subject": "/usr/bin/python3",
                "value": {"sha256": f"sha256:{'4' * 64}", "version": "3.12.0"},
                "measurement": {"method": "executable-sha256-and-version-v1"},
            },
            {
                "kind": "dependency-lock",
                "role": "suite-lock",
                "subject": "requirements.lock",
                "value": {"sha256": f"sha256:{'5' * 64}"},
                "measurement": {"method": "file-sha256-v1"},
            },
        ],
        "origin": {"kind": "project-adapter", "entry": entry},
    }


def _container_observation() -> dict[str, object]:
    return {
        "schema": adoption_check.OBSERVATION_SCHEMA,
        "suite": "fast",
        "invocation_binding": "3" * 64,
        "route_kind": "container",
        "runtime_identity": [
            {
                "kind": "oci-platform-manifest",
                "role": "suite-runtime",
                "subject": "container-instance-1",
                "value": {
                    "manifest_digest": f"sha256:{'6' * 64}",
                    "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
                    "configuration_digest": f"sha256:{'7' * 64}",
                    "platform": {"os": "linux", "architecture": "amd64"},
                },
                "measurement": {
                    "method": "entered-container-platform-manifest-config-v1"
                },
            }
        ],
        "origin": {"kind": "project-adapter", "entry": "./ci/verify"},
    }


class AdoptionCheckContractTests(unittest.TestCase):
    def _validate(self, value: dict[str, object]) -> adoption_check.RuntimeObservation:
        return adoption_check.validate_runtime_observation(
            (json.dumps(value) + "\n").encode(),
            suite="fast",
            invocation_binding="3" * 64,
            origin_entry="./ci/verify",
        )

    def test_unified_cli_exposes_the_bounded_adoption_check(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli_main(["adoption-check", "--help"])

        self.assertEqual(0, result, stderr.getvalue())
        help_text = stdout.getvalue()
        self.assertIn("--execution-route", help_text)
        self.assertIn("--seed", help_text)
        self.assertIn("--output-dir", help_text)
        self.assertIn(adoption_check.OBSERVATION_SCHEMA, help_text)
        self.assertIn(adoption_check.BUNDLE_COMMITMENT_SCHEMA, help_text)
        self.assertIn("GNOSTOA_ADOPTION_OBSERVATION_PATH", help_text)
        self.assertNotIn("--owner", help_text)
        self.assertNotIn("--accept", help_text)
        self.assertNotIn("--force", help_text)

    def test_public_workflow_owns_the_completion_and_sidecar_boundary(self) -> None:
        adoption = (
            ROOT / "guidance" / "workflows" / "adopt-existing-project.md"
        ).read_text(encoding="utf-8")
        bootstrap = (
            ROOT / "guidance" / "workflows" / "bootstrap-new-project.md"
        ).read_text(encoding="utf-8")
        guardrails = (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")

        self.assertIn("## Mechanical completion evidence", adoption)
        self.assertIn("knowledge adoption-check", adoption)
        self.assertIn("GNOSTOA_ADOPTION_OBSERVATION_PATH", adoption)
        self.assertIn(adoption_check.OBSERVATION_SCHEMA, adoption)
        self.assertIn("executable-sha256-and-version-v1", adoption)
        self.assertIn("entered-container-platform-manifest-config-v1", adoption)
        self.assertIn("64 KiB", adoption)
        self.assertIn("READY FOR ACCOUNTABLE-OWNER REVIEW", " ".join(adoption.split()))
        self.assertIn("project-reported runtime observation", adoption)
        self.assertIn("append-only in-memory ledger", adoption)
        self.assertIn(adoption_check.BUNDLE_COMMITMENT_SCHEMA, adoption)
        self.assertIn("unrestricted persistent process", adoption)
        self.assertIn("mechanical-completion-evidence", bootstrap)
        self.assertIn("bounded-adoption-completion-evidence", guardrails)

    def test_closed_native_profile_requires_measured_executable_and_lock(self) -> None:
        observation = self._validate(_native_observation())
        self.assertEqual("native", observation.route_kind)
        self.assertIsNone(observation.manifest_digest)

        missing_lock = _native_observation()
        identities = missing_lock["runtime_identity"]
        assert isinstance(identities, list)
        identities.pop()
        with self.assertRaisesRegex(
            adoption_check.ObservationBlocked, "dependency lock"
        ):
            self._validate(missing_lock)

        arbitrary = _native_observation()
        identities = arbitrary["runtime_identity"]
        assert isinstance(identities, list)
        identity = identities[0]
        assert isinstance(identity, dict)
        identity["measurement"] = {"method": "adapter-defined"}
        with self.assertRaisesRegex(
            adoption_check.ObservationBlocked, "measurement method"
        ):
            self._validate(arbitrary)

    def test_closed_json_rejects_duplicate_unknown_stale_and_unbound_members(
        self,
    ) -> None:
        duplicate = (
            b'{"schema":"gnostoa-project-runtime-observation/v1",'
            b'"schema":"gnostoa-project-runtime-observation/v1"}'
        )
        with self.assertRaisesRegex(adoption_check.ObservationBlocked, "duplicate"):
            adoption_check.validate_runtime_observation(
                duplicate,
                suite="fast",
                invocation_binding="3" * 64,
                origin_entry="./ci/verify",
            )

        cases = []
        unknown = _native_observation()
        unknown["expected_digest"] = f"sha256:{'8' * 64}"
        cases.append((unknown, "unknown members"))
        stale = _native_observation(binding="9" * 64)
        cases.append((stale, "wrong invocation binding"))
        wrong_suite = _native_observation(suite="regression")
        cases.append((wrong_suite, "does not match"))
        wrong_origin = _native_observation(entry="./another-entry")
        cases.append((wrong_origin, "does not match"))
        for value, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(adoption_check.ObservationBlocked, message):
                    self._validate(value)

    def test_container_profile_keeps_descriptor_kinds_distinct(self) -> None:
        observation = self._validate(_container_observation())
        self.assertEqual(f"sha256:{'6' * 64}", observation.manifest_digest)
        self.assertEqual(
            "application/vnd.oci.image.manifest.v1+json",
            observation.manifest_media_type,
        )

        index = _container_observation()
        identities = index["runtime_identity"]
        assert isinstance(identities, list)
        identity = identities[0]
        assert isinstance(identity, dict)
        value = identity["value"]
        assert isinstance(value, dict)
        value["manifest_media_type"] = "application/vnd.oci.image.index.v1+json"
        with self.assertRaisesRegex(
            adoption_check.ObservationBlocked, "not a platform manifest"
        ):
            self._validate(index)

        conflated = _container_observation()
        identities = conflated["runtime_identity"]
        assert isinstance(identities, list)
        identity = identities[0]
        assert isinstance(identity, dict)
        value = identity["value"]
        assert isinstance(value, dict)
        value["image_id"] = value["configuration_digest"]
        with self.assertRaisesRegex(
            adoption_check.ObservationBlocked, "unknown members"
        ):
            self._validate(conflated)

    def test_service_and_composite_routes_are_blocked_in_v1(self) -> None:
        for route in ("service", "composite"):
            with self.subTest(route=route):
                value = _native_observation()
                value["route_kind"] = route
                with self.assertRaisesRegex(
                    adoption_check.ObservationBlocked, "unsupported"
                ):
                    self._validate(value)

    def test_sidecar_bounds_and_closed_members_fail_blocked(self) -> None:
        wrong_schema = _native_observation()
        wrong_schema["schema"] = "gnostoa-project-runtime-observation/v2"
        invalid_origin = _native_observation()
        invalid_origin["origin"] = {
            "kind": "independent-attestation",
            "entry": "./ci/verify",
        }
        nested_unknown = _native_observation()
        identities = nested_unknown["runtime_identity"]
        assert isinstance(identities, list)
        identity = identities[0]
        assert isinstance(identity, dict)
        value = identity["value"]
        assert isinstance(value, dict)
        value["expected"] = f"sha256:{'4' * 64}"
        surrogate = _native_observation()
        surrogate["origin"] = {
            "kind": "project-adapter",
            "entry": "./ci/verify\ud800",
        }

        for candidate, message in (
            (wrong_schema, "wrong schema"),
            (invalid_origin, "not project-adapter"),
            (nested_unknown, "unknown members"),
            (surrogate, "non-scalar"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(adoption_check.ObservationBlocked, message):
                    self._validate(candidate)

        with self.assertRaisesRegex(adoption_check.ObservationBlocked, "exceeds"):
            adoption_check.validate_runtime_observation(
                b"x" * (adoption_check.MAX_OBSERVATION_BYTES + 1),
                suite="fast",
                invocation_binding="3" * 64,
                origin_entry="./ci/verify",
            )

    def test_container_declarations_and_engine_ids_cannot_substitute_for_profile(
        self,
    ) -> None:
        for identity in (
            {
                "kind": "oci-tag",
                "role": "suite-runtime",
                "subject": "container-instance-1",
                "value": {"tag": "example:stable"},
                "measurement": {"method": "caller-value"},
            },
            {
                "kind": "oci-repodigest",
                "role": "suite-runtime",
                "subject": "container-instance-1",
                "value": {"digest": f"sha256:{'6' * 64}"},
                "measurement": {"method": "engine-repodigest"},
            },
            {
                "kind": "engine-image-id",
                "role": "suite-runtime",
                "subject": "container-instance-1",
                "value": {"sha256": f"sha256:{'7' * 64}"},
                "measurement": {"method": "engine-image-id"},
            },
        ):
            candidate = _container_observation()
            candidate["runtime_identity"] = [identity]
            with self.subTest(kind=identity["kind"]):
                with self.assertRaisesRegex(
                    adoption_check.ObservationBlocked, "unknown identity profile"
                ):
                    self._validate(candidate)


class AdoptionCheckSidecarAcquisitionTests(unittest.TestCase):
    def _race_openers(
        self,
        target: Path,
        replacement: Path,
        *,
        symlink: bool = False,
    ) -> tuple[Callable[..., Any], Callable[..., int]]:
        real_path_open = Path.open
        real_os_open = os.open

        def replace() -> None:
            if symlink:
                if os.path.lexists(target):
                    target.unlink()
                target.symlink_to(replacement)
            else:
                os.replace(replacement, target)

        def pathname_open(path: Path, *args: Any, **kwargs: Any) -> Any:
            if Path(path) == target:
                replace()
            return real_path_open(path, *args, **kwargs)

        def descriptor_open(
            path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if symlink and Path(os.fsdecode(path)) == target:
                replace()
            if dir_fd is None:
                descriptor = real_os_open(path, flags, mode)
            else:
                descriptor = real_os_open(path, flags, mode, dir_fd=dir_fd)
            if not symlink and Path(os.fsdecode(path)) == target:
                replace()
            return descriptor

        return pathname_open, descriptor_open

    def test_symlink_swap_during_acquisition_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "observation.json"
            replacement = root / "replacement.json"
            target.write_bytes(b"original file bytes\n")
            replacement.write_bytes(b"replacement file bytes\n")
            pathname_open, descriptor_open = self._race_openers(
                target, replacement, symlink=True
            )

            with (
                mock.patch.object(Path, "open", pathname_open),
                mock.patch("tools.adoption_check.os.open", descriptor_open),
                self.assertRaisesRegex(
                    adoption_check.ObservationBlocked,
                    "regular non-symlink file",
                ),
            ):
                adoption_check._read_regular_bounded(target, 64, "observation")

    def test_path_replacement_cannot_redirect_an_opened_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "observation.json"
            replacement = root / "replacement.json"
            opened_file_content = b"original inode bytes\n"
            replacement_file_content = b"replacement inode bytes\n"
            target.write_bytes(opened_file_content)
            replacement.write_bytes(replacement_file_content)
            pathname_open, descriptor_open = self._race_openers(target, replacement)

            with (
                mock.patch.object(Path, "open", pathname_open),
                mock.patch("tools.adoption_check.os.open", descriptor_open),
            ):
                observed = adoption_check._read_regular_bounded(
                    target, 64, "observation"
                )

            self.assertEqual(opened_file_content, observed)
            self.assertEqual(replacement_file_content, target.read_bytes())

    def test_retention_uses_only_the_safely_opened_file_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "observation.json"
            replacement = root / "replacement.json"
            opened_file_content = b'{"sample":"original"}\n'
            replacement_file_content = b'{"sample":"replacement"}\n'
            target.write_bytes(opened_file_content)
            replacement.write_bytes(replacement_file_content)
            pathname_open, descriptor_open = self._race_openers(target, replacement)

            with (
                mock.patch.object(Path, "open", pathname_open),
                mock.patch("tools.adoption_check.os.open", descriptor_open),
            ):
                observed = adoption_check._read_regular_bounded(
                    target, 64, "observation"
                )

            writer = adoption_check.EvidenceWriter([])
            artifact = writer.write_bytes(
                "runtime-observations/fast.json",
                observed,
                origin="project-adapter:fast",
            )
            retained = writer.artifacts()[0]
            self.assertEqual(opened_file_content, retained.content)
            self.assertEqual(
                adoption_check._sha256(opened_file_content), artifact["sha256"]
            )
            self.assertNotEqual(replacement_file_content, retained.content)

    def test_relative_path_replacement_cannot_redirect_an_opened_descriptor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "observation.json"
            replacement = root / "replacement.json"
            opened_file_content = b"original relative inode bytes\n"
            replacement_file_content = b"replacement relative inode bytes\n"
            target.write_bytes(opened_file_content)
            replacement.write_bytes(replacement_file_content)
            real_open = os.open

            directory_descriptor = real_open(root, os.O_RDONLY | os.O_DIRECTORY)

            def descriptor_open(
                path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                flags: int,
                mode: int = 0o777,
                *,
                dir_fd: int | None = None,
            ) -> int:
                if dir_fd is None:
                    descriptor = real_open(path, flags, mode)
                else:
                    descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
                if dir_fd == directory_descriptor and os.fsdecode(path) == target.name:
                    os.replace(replacement, target)
                return descriptor

            try:
                with mock.patch("tools.adoption_check.os.open", descriptor_open):
                    observed = adoption_check._read_regular_bounded_at(
                        directory_descriptor, target.name, 64, "observation"
                    )
            finally:
                os.close(directory_descriptor)

            self.assertEqual(opened_file_content, observed)
            self.assertEqual(replacement_file_content, target.read_bytes())


class AdoptionCheckExecutionTests(unittest.TestCase):
    def _git(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    def _project(
        self, directory: str, *, runtime_mode: str = "toolkit"
    ) -> tuple[Path, Path]:
        container = Path(directory)
        project = container / "project"
        project.mkdir()
        self._git(project, "init", "-b", "main")
        self._git(project, "config", "user.email", "fixture@example.invalid")
        self._git(project, "config", "user.name", "Fixture")
        (project / "AGENTS.md").write_text(
            "# Existing project authority\n", encoding="utf-8"
        )
        self._git(project, "add", "AGENTS.md")
        self._git(project, "commit", "-m", "baseline")

        toolkit = project / ".knowledge-kit"
        toolkit.mkdir()
        shutil.copy2(ROOT / "pyproject.toml", toolkit / "pyproject.toml")
        shutil.copytree(ROOT / "core", toolkit / "core")
        shutil.copytree(ROOT / "schemas", toolkit / "schemas")
        digest = public_surface_digest(toolkit)

        configuration = project / ".knowledge"
        configuration.mkdir()
        (configuration / "profile.yaml").write_text(
            """id: example-adopter
version: "0.1.0"
okf_version: "0.2"
extends: [../.knowledge-kit/core/profile.yaml]
concept_types: []
relation_kinds: []
""",
            encoding="utf-8",
        )
        (configuration / "kit.lock.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "toolkit": {
                        "source": ".knowledge-kit",
                        "revision": REVISION,
                        "public_surface_digest": digest,
                        "profile": ".knowledge/profile.yaml",
                    },
                    "runtime": {"image": IMAGE, "revision": REVISION},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (configuration / "change-control.yaml").write_text(
            """id: example-change-control
version: "0.1.0"
owner: team:example
extends: [../.knowledge-kit/core/change-control.yaml]
""",
            encoding="utf-8",
        )
        (configuration / "continuous-integration.yaml").write_text(
            """id: example-ci
version: "0.1.0"
owner: team:example
extends: [../.knowledge-kit/core/continuous-integration.yaml]
""",
            encoding="utf-8",
        )
        runtime: dict[str, str] = {"mode": runtime_mode}
        if runtime_mode == "project":
            runtime["image"] = f"registry.example.org/project@sha256:{'6' * 64}"
        verification = {
            "id": "example-verification",
            "version": "0.1.0",
            "owner": "team:example",
            "policy": "continuous-integration.yaml",
            "runtime": runtime,
            "capabilities": {
                "integration": False,
                "smoke": False,
                "extended": False,
                "deployable_artifact": False,
            },
            "suites": {
                suite: {
                    "command": ["./ci/verify", suite],
                    "timeout_minutes": 1,
                    "evidence": ["test-report"],
                }
                for suite in ("fast", "regression")
            },
        }
        (configuration / "verification.yaml").write_text(
            yaml.safe_dump(verification, sort_keys=False), encoding="utf-8"
        )
        (configuration / "project.lock").write_text("fixture-lock\n", encoding="utf-8")

        bundle = project / "knowledge"
        shutil.copytree(ROOT / "examples" / "generic", bundle)
        ci = project / "ci"
        ci.mkdir()
        adapter = ci / "verify"
        adapter.write_text(
            """#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

mode = os.environ.get("ADOPTION_FIXTURE_MODE", "pass")
suite = sys.argv[1]
if mode == "blocked":
    raise SystemExit(127)

target = Path(os.environ["GNOSTOA_ADOPTION_OBSERVATION_PATH"])
def publish(content):
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.link(temporary, target)
    temporary.unlink()

if mode == "malformed":
    publish("{\\n")
elif mode == "oversized":
    publish("x" * 65537)
elif mode == "symlink":
    target.symlink_to(Path(".knowledge/project.lock").resolve())
elif mode == "parent-symlink":
    external = target.parent.parent.parent / f"external-{suite}"
    external.mkdir()
    (external / target.name).write_text(
        '{"sample":"external"}\\n', encoding="utf-8"
    )
    target.parent.rmdir()
    target.parent.symlink_to(external, target_is_directory=True)
elif mode == "parent-replaced":
    opened_directory = target.parent.parent.parent / f"opened-{suite}"
    target.parent.rename(opened_directory)
    (opened_directory / target.name).write_text(
        '{"sample":"original"}\\n', encoding="utf-8"
    )
    target.parent.mkdir()
    target.write_text('{"sample":"replacement"}\\n', encoding="utf-8")
elif mode != "no-observation":
    if mode.startswith("container-"):
        digest_character = "6" if mode == "container-pass" else "8"
        observation = {
            "schema": "gnostoa-project-runtime-observation/v1",
            "suite": suite,
            "invocation_binding": os.environ["GNOSTOA_ADOPTION_INVOCATION_BINDING"],
            "route_kind": "container",
            "runtime_identity": [
                {
                    "kind": "oci-platform-manifest",
                    "role": "suite-runtime",
                    "subject": "fixture-container-instance",
                    "value": {
                        "manifest_digest": "sha256:" + digest_character * 64,
                        "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
                        "configuration_digest": "sha256:" + "7" * 64,
                        "platform": {"os": "linux", "architecture": "amd64"},
                    },
                    "measurement": {
                        "method": "entered-container-platform-manifest-config-v1"
                    },
                }
            ],
            "origin": {"kind": "project-adapter", "entry": "./ci/verify"},
        }
    else:
        executable = Path(sys.executable)
        lock = Path(".knowledge/project.lock")
        observation = {
            "schema": "gnostoa-project-runtime-observation/v1",
            "suite": suite,
            "invocation_binding": os.environ["GNOSTOA_ADOPTION_INVOCATION_BINDING"],
            "route_kind": "native",
            "runtime_identity": [
                {
                    "kind": "native-executable",
                    "role": "suite-runtime",
                    "subject": str(executable),
                    "value": {
                        "sha256": "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest(),
                        "version": sys.version.split()[0],
                    },
                    "measurement": {"method": "executable-sha256-and-version-v1"},
                },
                {
                    "kind": "dependency-lock",
                    "role": "suite-lock",
                    "subject": ".knowledge/project.lock",
                    "value": {
                        "sha256": "sha256:" + hashlib.sha256(lock.read_bytes()).hexdigest(),
                    },
                    "measurement": {"method": "file-sha256-v1"},
                },
            ],
            "origin": {"kind": "project-adapter", "entry": "./ci/verify"},
        }
    if mode == "wrong-binding":
        observation["invocation_binding"] = "9" * 64
    publish(json.dumps(observation, sort_keys=True) + "\\n")
if mode == "mutate":
    with Path("AGENTS.md").open("a", encoding="utf-8") as handle:
        handle.write("suite mutation\\n")
if mode in {
    "overwrite-component",
    "replace-component",
    "mutate-candidate",
    "mutate-context",
    "unexpected-evidence-path",
    "background-evidence-mutation",
}:
    evidence_root = target.parent.parent
    if mode == "overwrite-component":
        artifact = evidence_root / "components" / "runtime-lock.stdout"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"replacement component bytes\\n")
    elif mode == "replace-component":
        artifact = evidence_root / "components" / "runtime-lock.stdout"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        replacement = evidence_root / "component-replacement.tmp"
        replacement.write_bytes(b"replacement inode bytes\\n")
        os.replace(replacement, artifact)
    elif mode == "mutate-candidate":
        (evidence_root / "candidate.patch").write_bytes(
            b"replacement candidate bytes\\n"
        )
    elif mode == "mutate-context":
        (evidence_root / "context-pack.md").write_bytes(
            b"replacement context bytes\\n"
        )
    elif mode == "unexpected-evidence-path":
        (evidence_root / "suite-created.txt").write_text(
            "unexpected suite path\\n", encoding="utf-8"
        )
    else:
        program = (
            "import pathlib,time\\n"
            f"root=pathlib.Path({str(evidence_root)!r})\\n"
            "deadline=time.monotonic()+2\\n"
            "marker=root/'adoption-check.json'\\n"
            "while time.monotonic()<deadline and not marker.exists():\\n"
            "    time.sleep(0.002)\\n"
            "if marker.exists():\\n"
            "    (root/'candidate.patch').write_bytes("
            "b'background replacement bytes\\\\n')\\n"
        )
        subprocess.Popen(
            [sys.executable, "-c", program],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
if mode == "fail":
    raise SystemExit(1)
raise SystemExit(0)
""",
            encoding="utf-8",
        )
        adapter.chmod(0o755)
        with (project / "AGENTS.md").open("a", encoding="utf-8") as handle:
            handle.write(
                "\n## Gnostoa route\n\nFollow the existing-project workflow.\n"
            )
        self._git(project, "add", ".")
        return project, toolkit

    def _run(
        self,
        project: Path,
        toolkit: Path,
        output: Path,
        *,
        mode: str = "pass",
        execution_route: str = "native",
        documentation_root: Path | None = None,
        execution_root: Path | None = None,
    ) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        environment = {
            "KNOWLEDGE_KIT_ROOT": str(toolkit),
            "KNOWLEDGE_KIT_REVISION": REVISION,
            "ADOPTION_FIXTURE_MODE": mode,
        }
        arguments = [
            "adoption-check",
            "--execution-route",
            execution_route,
            "--seed",
            "example.system.processing",
            "--output-dir",
            str(output),
            "--project-root",
            str(project),
        ]
        if documentation_root is not None:
            arguments.extend(["--documentation-root", str(documentation_root)])
        with (
            mock.patch.dict(os.environ, environment, clear=False),
            mock.patch(
                "tools.adoption_check._execution_root",
                return_value=execution_root or toolkit,
            ),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            result = cli_main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_complete_native_candidate_is_evidence_bound_not_semantically_accepted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            before = self._git(project, "status", "--porcelain=v2").stdout
            result, stdout, stderr = self._run(project, toolkit, output)
            after = self._git(project, "status", "--porcelain=v2").stdout

            self.assertEqual((0, ""), (result, stderr), stdout)
            self.assertIn("READY FOR ACCOUNTABLE-OWNER REVIEW", stdout)
            self.assertEqual(before, after)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(adoption_check.RESULT_SCHEMA, manifest["schema"])
            self.assertEqual(
                "REQUIRED", manifest["dimensions"]["semantic_owner_review"]
            )
            self.assertEqual(
                "NOT DETERMINED", manifest["dimensions"]["durable_adoption"]
            )
            self.assertEqual(
                "PASS", manifest["dimensions"]["bounded_context"]["result"]
            )
            self.assertEqual("PASS", manifest["dimensions"]["project_suites"]["result"])
            self.assertTrue((output / "context-pack.md").is_file())
            self.assertTrue((output / "candidate.patch").is_file())
            self.assertTrue((output / "git-state.json").is_file())
            sums = (output / "SHA256SUMS").read_text()
            self.assertIn("adoption-check.json", sums)
            self.assertIn("context-pack.md", sums)

    def test_missing_observation_and_unavailable_suite_are_blocked_with_evidence(
        self,
    ) -> None:
        for mode in ("no-observation", "blocked"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                project, toolkit = self._project(directory)
                output = Path(directory) / "evidence"
                result, stdout, stderr = self._run(project, toolkit, output, mode=mode)
                self.assertEqual((3, ""), (result, stderr), stdout)
                manifest = json.loads((output / "adoption-check.json").read_text())
                self.assertEqual("BLOCKED", manifest["outcome"])
                self.assertEqual(
                    "BLOCKED",
                    manifest["dimensions"]["project_suites"][
                        "project_runtime_observation"
                    ],
                )
                self.assertEqual(
                    "BLOCKED" if mode == "blocked" else "PASS",
                    manifest["dimensions"]["environment"]["result"],
                )

    def _assert_unavailable_git_snapshot_is_blocked(self, fail_call: int) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            before_status = self._git(
                project, "status", "--porcelain=v2", "--untracked-files=all"
            ).stdout
            before_index = self._git(
                project, "diff", "--cached", "--binary", "--full-index"
            ).stdout
            stage = "initial" if fail_call == 1 else "final"
            real_snapshot = adoption_check._git_snapshot
            calls = 0

            def unavailable_snapshot(root: Path) -> dict[str, object]:
                nonlocal calls
                calls += 1
                if calls == fail_call:
                    raise adoption_check.BlockedPrerequisite(
                        f"{stage} Git snapshot unavailable"
                    )
                return real_snapshot(root)

            with mock.patch(
                "tools.adoption_check._git_snapshot",
                side_effect=unavailable_snapshot,
            ):
                result, stdout, stderr = self._run(project, toolkit, output)

            self.assertEqual((3, ""), (result, stderr), stdout)
            self.assertIn("BLOCKED", stdout)
            self.assertNotIn("READY FOR ACCOUNTABLE-OWNER REVIEW", stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual("BLOCKED", manifest["outcome"])
            self.assertEqual(
                "BLOCKED", manifest["dimensions"]["git_representability"]["result"]
            )
            self.assertIn(
                f"{stage} Git snapshot unavailable",
                manifest["dimensions"]["git_representability"]["detail"],
            )
            self._assert_prerequisite_dimension_history(
                manifest, completed=fail_call == 2
            )
            self.assertEqual(
                before_status,
                self._git(
                    project, "status", "--porcelain=v2", "--untracked-files=all"
                ).stdout,
            )
            self.assertEqual(
                before_index,
                self._git(
                    project, "diff", "--cached", "--binary", "--full-index"
                ).stdout,
            )

    def test_unavailable_initial_git_snapshot_is_retained_as_blocked(self) -> None:
        self._assert_unavailable_git_snapshot_is_blocked(1)

    def test_unavailable_final_git_snapshot_is_retained_as_blocked(self) -> None:
        self._assert_unavailable_git_snapshot_is_blocked(2)

    def _assert_unavailable_git_representation_is_blocked(self, fail_call: int) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            before_status = self._git(
                project, "status", "--porcelain=v2", "--untracked-files=all"
            ).stdout
            before_index = self._git(
                project, "diff", "--cached", "--binary", "--full-index"
            ).stdout
            stage = "initial" if fail_call == 1 else "final"
            real_representation = adoption_check._git_representation
            calls = 0

            def unavailable_representation(
                paths: adoption_check.PathSet,
                verification: dict[str, object],
            ) -> tuple[dict[str, object], list[str]]:
                nonlocal calls
                calls += 1
                if calls == fail_call:
                    raise adoption_check.BlockedPrerequisite(
                        f"{stage} Git representation unavailable"
                    )
                return real_representation(paths, verification)

            with mock.patch(
                "tools.adoption_check._git_representation",
                side_effect=unavailable_representation,
            ):
                result, stdout, stderr = self._run(project, toolkit, output)

            self.assertEqual((3, ""), (result, stderr), stdout)
            self.assertIn("BLOCKED", stdout)
            self.assertNotIn("READY FOR ACCOUNTABLE-OWNER REVIEW", stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual("BLOCKED", manifest["outcome"])
            self.assertEqual(
                "BLOCKED", manifest["dimensions"]["git_representability"]["result"]
            )
            self.assertIn(
                f"{stage} Git representation unavailable",
                manifest["dimensions"]["git_representability"]["detail"],
            )
            self._assert_prerequisite_dimension_history(
                manifest, completed=fail_call == 2
            )
            self.assertEqual(
                before_status,
                self._git(
                    project, "status", "--porcelain=v2", "--untracked-files=all"
                ).stdout,
            )
            self.assertEqual(
                before_index,
                self._git(
                    project, "diff", "--cached", "--binary", "--full-index"
                ).stdout,
            )

    def _assert_prerequisite_dimension_history(
        self, manifest: dict[str, object], *, completed: bool
    ) -> None:
        dimensions = manifest["dimensions"]
        assert isinstance(dimensions, dict)
        expected = "PASS" if completed else "NOT RUN"
        for name in (
            "runtime_lock_validation",
            "change_policy",
            "ci_policy",
            "profile_and_bundle",
            "bounded_context",
            "project_suites",
        ):
            with self.subTest(dimension=name, completed=completed):
                dimension = dimensions[name]
                assert isinstance(dimension, dict)
                self.assertEqual(expected, dimension["result"])

        if not completed:
            return
        components = manifest["components"]
        assert isinstance(components, list)
        component_results = {
            component["name"]: component["result"]
            for component in components
            if isinstance(component, dict)
        }
        self.assertEqual(
            component_results["runtime-lock"],
            dimensions["runtime_lock_validation"]["result"],
        )
        self.assertEqual(
            component_results["change-policy"],
            dimensions["change_policy"]["result"],
        )
        self.assertEqual(
            component_results["ci-policy"], dimensions["ci_policy"]["result"]
        )
        self.assertEqual(
            component_results["bundle"], dimensions["profile_and_bundle"]["result"]
        )
        self.assertEqual(
            {
                "fast": component_results["project-fast"],
                "regression": component_results["project-regression"],
            },
            dimensions["project_suites"]["suites"],
        )
        self.assertEqual("PASS", dimensions["environment"]["result"])
        self.assertEqual(
            "PASS", dimensions["documentation_toolkit_execution_coherence"]["result"]
        )
        self.assertEqual("PASS", dimensions["evidence_bundle"]["result"])

    def test_unavailable_initial_git_representation_is_retained_as_blocked(
        self,
    ) -> None:
        self._assert_unavailable_git_representation_is_blocked(1)

    def test_unavailable_final_git_representation_preserves_completed_results(
        self,
    ) -> None:
        self._assert_unavailable_git_representation_is_blocked(2)

    def test_parent_symlink_escape_is_blocked_without_retaining_external_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, mode="parent-symlink"
            )

            self.assertEqual((3, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual("BLOCKED", manifest["outcome"])
            self.assertFalse((output / "runtime-observations" / "fast.json").exists())
            self.assertFalse(
                (output / "runtime-observations" / "regression.json").exists()
            )
            artifact_paths = {artifact["path"] for artifact in manifest["artifacts"]}
            self.assertFalse(
                any(path.startswith("runtime-observations/") for path in artifact_paths)
            )
            for component in manifest["components"]:
                if component["name"].startswith("project-"):
                    self.assertNotIn("sha256", component["runtime_observation"])

    def test_renamed_parent_retains_only_descriptor_bound_bytes_and_hash(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, mode="parent-replaced"
            )

            self.assertEqual((3, ""), (result, stderr), stdout)
            retained = output / "runtime-observations" / "fast.json"
            opened_file_content = b'{"sample":"original"}\n'
            replacement_file_content = b'{"sample":"replacement"}\n'
            self.assertEqual(opened_file_content, retained.read_bytes())
            manifest = json.loads((output / "adoption-check.json").read_text())
            fast = next(
                component
                for component in manifest["components"]
                if component["name"] == "project-fast"
            )
            self.assertEqual(
                adoption_check._sha256(opened_file_content),
                fast["runtime_observation"]["sha256"],
            )
            self.assertNotEqual(replacement_file_content, retained.read_bytes())

    def test_incoming_directory_descriptors_close_on_blocked_and_exception_paths(
        self,
    ) -> None:
        real_open = os.open
        real_close = os.close
        real_run_bytes = adoption_check._run_bytes

        for outcome in ("blocked", "launch-error", "timeout"):
            with (
                self.subTest(outcome=outcome),
                tempfile.TemporaryDirectory() as directory,
            ):
                project, toolkit = self._project(directory)
                output = Path(directory) / "evidence"
                opened: set[int] = set()
                closed: set[int] = set()

                def tracking_open(
                    path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    flags: int,
                    mode: int = 0o777,
                    opened_descriptors: set[int] = opened,
                    *,
                    dir_fd: int | None = None,
                ) -> int:
                    if dir_fd is None:
                        descriptor = real_open(path, flags, mode)
                    else:
                        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
                    if flags & getattr(os, "O_DIRECTORY", 0):
                        opened_descriptors.add(descriptor)
                    return descriptor

                def tracking_close(
                    descriptor: int,
                    opened_descriptors: set[int] = opened,
                    closed_descriptors: set[int] = closed,
                ) -> None:
                    if descriptor in opened_descriptors:
                        closed_descriptors.add(descriptor)
                    real_close(descriptor)

                def controlled_run(
                    command: list[str],
                    *,
                    cwd: Path,
                    env: dict[str, str] | None = None,
                    timeout: float | None = None,
                    fixture_outcome: str = outcome,
                ) -> subprocess.CompletedProcess[bytes]:
                    if command and command[0] == "./ci/verify":
                        if fixture_outcome == "launch-error":
                            raise OSError("fixture launch unavailable")
                        if fixture_outcome == "timeout":
                            raise subprocess.TimeoutExpired(command, timeout or 0)
                    return real_run_bytes(command, cwd=cwd, env=env, timeout=timeout)

                mode = "no-observation" if outcome == "blocked" else "pass"
                with (
                    mock.patch("tools.adoption_check.os.open", tracking_open),
                    mock.patch("tools.adoption_check.os.close", tracking_close),
                    mock.patch(
                        "tools.adoption_check._run_bytes", side_effect=controlled_run
                    ),
                ):
                    self._run(project, toolkit, output, mode=mode)

                self.assertTrue(opened)
                self.assertEqual(opened, closed)
                for descriptor in opened:
                    with self.assertRaises(OSError):
                        os.fstat(descriptor)

    def test_invalid_sidecars_are_blocked_and_never_escape_the_evidence_root(
        self,
    ) -> None:
        for mode in ("malformed", "oversized", "wrong-binding", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                project, toolkit = self._project(directory)
                output = Path(directory) / "evidence"
                result, stdout, stderr = self._run(project, toolkit, output, mode=mode)
                self.assertEqual((3, ""), (result, stderr), stdout)
                manifest = json.loads((output / "adoption-check.json").read_text())
                self.assertEqual("BLOCKED", manifest["outcome"])
                self.assertEqual(
                    "BLOCKED",
                    manifest["dimensions"]["project_suites"][
                        "project_runtime_observation"
                    ],
                )
                self.assertFalse(any(path.is_symlink() for path in output.rglob("*")))
                retained = output / "runtime-observations" / "fast.json"
                self.assertEqual(
                    mode in {"malformed", "wrong-binding"}, retained.is_file()
                )

    def test_evidence_artifacts_are_created_once_without_replacement(self) -> None:
        writer = adoption_check.EvidenceWriter([])
        writer.write_text("component.txt", "first\n", origin="gnostoa-test")
        with self.assertRaisesRegex(
            adoption_check.UnsafeInvocation, "without replacement"
        ):
            writer.write_text("component.txt", "second\n", origin="gnostoa-test")
        self.assertEqual(b"first\n", writer.artifacts()[0].content)

    def test_documentation_drift_and_unobserved_oci_digest_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            documentation = Path(directory) / "documentation"
            shutil.copytree(toolkit, documentation)
            with (documentation / "pyproject.toml").open("a", encoding="utf-8") as file:
                file.write("# distinct documentation subject\n")
            output = Path(directory) / "documentation-evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, documentation_root=documentation
            )
            self.assertEqual((3, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertIn(
                "documentation and toolkit public surfaces differ",
                manifest["dimensions"]["documentation_toolkit_execution_coherence"][
                    "blockers"
                ],
            )

        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "oci-evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, execution_route="oci"
            )
            self.assertEqual((3, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(
                "NOT OBSERVED", manifest["dimensions"]["external_oci_digest"]["result"]
            )

    def test_locked_declaration_cannot_replace_a_measured_actual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            lock_path = project / ".knowledge" / "kit.lock.yaml"
            lock = yaml.safe_load(lock_path.read_text())
            lock["toolkit"]["public_surface_digest"] = f"sha256:{'0' * 64}"
            lock_path.write_text(
                yaml.safe_dump(lock, sort_keys=False), encoding="utf-8"
            )
            self._git(project, "add", ".knowledge/kit.lock.yaml")
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(project, toolkit, output)
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(
                "FAIL", manifest["dimensions"]["runtime_lock_validation"]["result"]
            )
            self.assertEqual(
                "NOT RUN", manifest["dimensions"]["change_policy"]["result"]
            )

    def test_measured_toolkit_and_execution_surface_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            execution_root = Path(directory) / "execution-root"
            shutil.copytree(toolkit, execution_root)
            with (execution_root / "pyproject.toml").open(
                "a", encoding="utf-8"
            ) as file:
                file.write("# runtime drift\n")
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, execution_root=execution_root
            )
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            identity = manifest["dimensions"][
                "documentation_toolkit_execution_coherence"
            ]
            self.assertEqual("FAIL", identity["result"])
            self.assertIn(
                "toolkit source and executing runtime public surfaces differ",
                identity["failures"],
            )

    def test_context_must_regenerate_byte_identically_before_retention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            generated = iter(("first context\n", "different context\n"))

            def context_main(_: list[str] | None = None) -> int:
                print(next(generated), end="")
                return 0

            with mock.patch(
                "tools.adoption_check.build_context_pack.main", side_effect=context_main
            ):
                result, stdout, stderr = self._run(project, toolkit, output)
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(
                "FAIL", manifest["dimensions"]["bounded_context"]["result"]
            )
            self.assertFalse((output / "context-pack.md").exists())

    def test_untracked_required_target_and_suite_mutation_fail_git_binding(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            self._git(project, "rm", "--cached", ".knowledge/profile.yaml")
            output = Path(directory) / "untracked-evidence"
            result, stdout, stderr = self._run(project, toolkit, output)
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(
                "FAIL", manifest["dimensions"]["git_representability"]["result"]
            )

        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "mutation-evidence"
            result, stdout, stderr = self._run(project, toolkit, output, mode="mutate")
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            problems = manifest["dimensions"]["git_representability"]["problems"]
            self.assertTrue(
                any("changed during adoption-check" in problem for problem in problems)
            )

    def test_staged_submodule_gitlink_must_equal_the_toolkit_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, original_toolkit = self._project(directory)
            source = Path(directory) / "toolkit-source"
            source.mkdir()
            self._git(source, "init", "-b", "main")
            self._git(source, "config", "user.email", "fixture@example.invalid")
            self._git(source, "config", "user.name", "Fixture")
            shutil.copy2(ROOT / "pyproject.toml", source / "pyproject.toml")
            shutil.copytree(ROOT / "core", source / "core")
            shutil.copytree(ROOT / "schemas", source / "schemas")
            self._git(source, "add", ".")
            self._git(source, "commit", "-m", "toolkit v1")
            first = self._git(source, "rev-parse", "HEAD").stdout.strip()
            with (source / "pyproject.toml").open("a", encoding="utf-8") as file:
                file.write("# second source identity\n")
            self._git(source, "add", "pyproject.toml")
            self._git(source, "commit", "-m", "toolkit v2")

            self._git(project, "rm", "-r", "--cached", ".knowledge-kit")
            shutil.rmtree(original_toolkit)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "-C",
                    str(project),
                    "submodule",
                    "add",
                    str(source),
                    ".knowledge-kit",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            toolkit = project / ".knowledge-kit"
            self._git(toolkit, "checkout", "--detach", first)
            lock_path = project / ".knowledge" / "kit.lock.yaml"
            lock = yaml.safe_load(lock_path.read_text())
            lock["toolkit"]["revision"] = first
            lock["runtime"]["revision"] = first
            lock["toolkit"]["public_surface_digest"] = public_surface_digest(toolkit)
            lock_path.write_text(
                yaml.safe_dump(lock, sort_keys=False), encoding="utf-8"
            )
            self._git(project, "add", ".knowledge/kit.lock.yaml", ".gitmodules")

            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(project, toolkit, output)
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            submodule = manifest["dimensions"]["git_representability"]
            self.assertEqual("FAIL", submodule["result"])
            self.assertIn(
                "staged toolkit gitlink differs from toolkit worktree HEAD",
                submodule["problems"],
            )

    def test_executed_suite_failure_takes_precedence_over_missing_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(project, toolkit, output, mode="fail")
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual("MECHANICAL CHECK FAILED", manifest["outcome"])
            self.assertEqual("FAIL", manifest["dimensions"]["project_suites"]["result"])

    def test_mandatory_image_conflict_is_failure_not_incomplete_observation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory, runtime_mode="project")
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(project, toolkit, output)
            self.assertEqual((1, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(
                "FAIL",
                manifest["dimensions"]["project_suites"]["project_runtime_observation"],
            )

    def test_platform_manifest_coherence_uses_only_the_same_descriptor_kind(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory, runtime_mode="project")
            output = Path(directory) / "matching-evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, mode="container-pass"
            )
            self.assertEqual((0, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            observations = [
                component["runtime_observation"]
                for component in manifest["components"]
                if component["name"].startswith("project-")
            ]
            self.assertTrue(
                all(
                    item["declared_manifest_coherence"] == "PASS"
                    for item in observations
                )
            )

        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory, runtime_mode="project")
            output = Path(directory) / "different-evidence"
            result, stdout, stderr = self._run(
                project, toolkit, output, mode="container-different"
            )
            self.assertEqual((3, ""), (result, stderr), stdout)
            manifest = json.loads((output / "adoption-check.json").read_text())
            self.assertEqual(
                "BLOCKED",
                manifest["dimensions"]["project_suites"]["project_runtime_observation"],
            )

    def test_existing_or_in_project_output_is_refused_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            existing = Path(directory) / "evidence"
            existing.mkdir()
            marker = existing / "marker"
            marker.write_text("preserve\n", encoding="utf-8")
            result, _, stderr = self._run(project, toolkit, existing)
            self.assertEqual(2, result)
            self.assertIn("already exists", stderr)
            self.assertEqual("preserve\n", marker.read_text())

            result, _, stderr = self._run(
                project, toolkit, project / "in-project-evidence"
            )
            self.assertEqual(2, result)
            self.assertIn("outside the project root", stderr)

    def _assert_suite_cannot_mutate_authoritative_evidence(self, mode: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, stdout, _ = self._run(project, toolkit, output, mode=mode)

            self.assertEqual(2, result, stdout)
            self.assertNotIn("READY FOR ACCOUNTABLE-OWNER REVIEW", stdout)
            self.assertFalse(output.exists())

    def test_suite_cannot_overwrite_a_pre_suite_component_artifact(self) -> None:
        self._assert_suite_cannot_mutate_authoritative_evidence("overwrite-component")

    def test_suite_cannot_replace_a_pre_suite_artifact_inode(self) -> None:
        self._assert_suite_cannot_mutate_authoritative_evidence("replace-component")

    def test_suite_cannot_mutate_candidate_or_context_before_hashing(self) -> None:
        for mode in ("mutate-candidate", "mutate-context"):
            with self.subTest(mode=mode):
                self._assert_suite_cannot_mutate_authoritative_evidence(mode)

    def test_unexpected_suite_created_evidence_path_fails_closed(self) -> None:
        self._assert_suite_cannot_mutate_authoritative_evidence(
            "unexpected-evidence-path"
        )

    def test_background_descendant_cannot_reach_authoritative_finalization(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(
                project,
                toolkit,
                output,
                mode="background-evidence-mutation",
            )

            self.assertEqual((0, ""), (result, stderr), stdout)
            self.assertIn("READY FOR ACCOUNTABLE-OWNER REVIEW", stdout)
            self.assertNotEqual(
                b"background replacement bytes\n",
                (output / "candidate.patch").read_bytes(),
            )

    def test_mutation_between_reconciliation_and_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            real_reconcile = adoption_check._reconcile_materialized
            calls = 0

            def mutate_after_first_reconciliation(
                root: Path,
                artifacts: tuple[adoption_check.EvidenceArtifact, ...],
            ) -> None:
                nonlocal calls
                real_reconcile(root, artifacts)
                calls += 1
                if calls == 1:
                    (root / "candidate.patch").write_bytes(
                        b"post-reconciliation replacement bytes\n"
                    )

            with mock.patch(
                "tools.adoption_check._reconcile_materialized",
                side_effect=mutate_after_first_reconciliation,
            ):
                result, stdout, _ = self._run(project, toolkit, output)

            self.assertEqual(2, result, stdout)
            self.assertNotIn("READY FOR ACCOUNTABLE-OWNER REVIEW", stdout)
            self.assertFalse(output.exists())

    def test_external_bundle_commitment_detects_later_bundle_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, stdout, stderr = self._run(project, toolkit, output)
            self.assertEqual((0, ""), (result, stderr), stdout)
            match = re.search(
                r"^EVIDENCE BUNDLE COMMITMENT: "
                r"gnostoa-adoption-evidence-bundle/v1 (sha256:[0-9a-f]{64})$",
                stdout,
                flags=re.MULTILINE,
            )
            self.assertIsNotNone(match, stdout)
            assert match is not None
            published_commitment = match.group(1)
            self.assertEqual(
                published_commitment,
                adoption_check._materialized_bundle_commitment(output),
            )

            (output / "candidate.patch").write_bytes(b"later custody bytes\n")
            self.assertNotEqual(
                published_commitment,
                adoption_check._materialized_bundle_commitment(output),
            )

    def test_final_hash_manifest_matches_every_retained_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project, toolkit = self._project(directory)
            output = Path(directory) / "evidence"
            result, _, _ = self._run(project, toolkit, output)
            self.assertEqual(0, result)
            lines = (output / "SHA256SUMS").read_text().splitlines()
            recorded = {
                path: digest for digest, path in (line.split("  ", 1) for line in lines)
            }
            files = {
                path.relative_to(output).as_posix()
                for path in output.rglob("*")
                if path.is_file() and path.name != "SHA256SUMS"
            }
            self.assertEqual(files, set(recorded))
            for relative, digest in recorded.items():
                self.assertEqual(
                    digest,
                    hashlib.sha256((output / relative).read_bytes()).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
