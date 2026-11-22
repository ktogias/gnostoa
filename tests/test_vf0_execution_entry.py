"""Conformance tests for the VF0 execution entrypoint and observation boundary."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from collections.abc import Sequence
from dataclasses import fields
from pathlib import Path
from unittest import mock

from tests.test_vf0_execution import _evidence, _repo
from tools.vf0_execution import (
    DockerBackend,
    ExecutionLimits,
    ExecutionObservation,
    ExecutionRejected,
    GitSubject,
    UntrustedCapture,
    execute,
)


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

    def test_backend_cannot_mutate_controller_output_limit(self) -> None:
        class MutatingLimitsBackend:
            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del root, command, subject
                object.__setattr__(limits, "output_bytes", 100)
                return UntrustedCapture("completed", 0, b"four", b"", 4)

        limits = ExecutionLimits(output_bytes=3)
        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            with self.assertRaisesRegex(
                ExecutionRejected, "^BACKEND_CAPTURE_OUTPUT_BOUND$"
            ):
                execute(
                    repo,
                    subject,
                    [_evidence("pass")],
                    ["/bin/true"],
                    MutatingLimitsBackend(),
                    limits,
                )
        self.assertEqual(3, limits.output_bytes)

    def test_controller_owned_subject_survives_backend_mutation(self) -> None:
        class MutatingSubjectBackend:
            received_subject: GitSubject | None = None

            def run(
                self,
                root: Path,
                command: Sequence[str],
                limits: ExecutionLimits,
                *,
                subject: GitSubject,
            ) -> UntrustedCapture:
                del root, command, limits
                self.received_subject = subject
                object.__setattr__(subject, "commit", "f" * 40)
                return UntrustedCapture("completed", 0, b"", b"", 0)

        with tempfile.TemporaryDirectory() as td:
            repo, subject = _repo(Path(td))
            original_subject = GitSubject(commit=subject.commit, tree=subject.tree)
            backend = MutatingSubjectBackend()
            observation = execute(
                repo,
                subject,
                [_evidence("pass")],
                ["/bin/true"],
                backend,
            )

        self.assertEqual(original_subject, subject)
        self.assertEqual(original_subject, observation.subject)
        self.assertIsNot(backend.received_subject, subject)

    def test_controller_owned_subject_uses_rebuilt_builtin_backends(self) -> None:
        module = importlib.import_module("tools.vf0_execution")
        backends = (
            (
                module.DockerBackend("ghcr.io/ktogias/gnostoa@sha256:" + "a" * 64),
                "gnostoa-docker-oci-v1",
                True,
            ),
            (module.SubprocessBackend(), "gnostoa-local-subprocess-v1", False),
        )
        for backend, identity, subject_unchanged in backends:
            with self.subTest(identity=identity):
                injected_calls: list[str] = []
                controller_receivers: list[object] = []

                def injected_run(
                    root: Path,
                    command: Sequence[str],
                    limits: ExecutionLimits,
                    *,
                    subject: GitSubject,
                    calls: list[str] = injected_calls,
                ) -> UntrustedCapture:
                    del root, command, limits, subject
                    calls.append("injected")
                    return UntrustedCapture("completed", 0, b"", b"", 0)

                def controller_run(
                    receiver: object,
                    root: Path,
                    command: Sequence[str],
                    limits: ExecutionLimits,
                    *,
                    subject: GitSubject,
                    receivers: list[object] = controller_receivers,
                ) -> UntrustedCapture:
                    del root, command, limits, subject
                    receivers.append(receiver)
                    return UntrustedCapture("completed", 0, b"", b"", 0)

                object.__setattr__(backend, "run", injected_run)
                with (
                    mock.patch.object(type(backend), "run", new=controller_run),
                    tempfile.TemporaryDirectory() as td,
                ):
                    repo, subject = _repo(Path(td))
                    observation = execute(
                        repo,
                        subject,
                        [_evidence("pass")],
                        ["/bin/true"],
                        backend,
                    )

                self.assertEqual([], injected_calls)
                self.assertEqual(1, len(controller_receivers))
                self.assertIsNot(backend, controller_receivers[0])
                self.assertEqual(identity, observation.backend_identity)
                self.assertEqual(subject_unchanged, observation.subject_unchanged)
                self.assertEqual(
                    backend.image if type(backend) is DockerBackend else None,
                    observation.runtime_identity,
                )
