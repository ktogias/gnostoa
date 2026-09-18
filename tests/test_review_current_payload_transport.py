from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import review_current


class ProtectedPayloadTransportTests(unittest.TestCase):
    def test_protected_judge_uses_stdin_without_host_payload_files(self) -> None:
        image = "ghcr.io/example/gnostoa@sha256:" + "a" * 64
        revision = "b" * 40
        surface_digest = "sha256:" + "c" * 64
        marker = "private-review-payload-marker"
        input_document = {"input": marker}
        policy_document = {"policy": marker}
        observed_run: dict[str, object] = {}

        def checked_output(
            arguments: list[str],
            *,
            config_dir: Path,
            description: str,
            timeout: int = review_current._DOCKER_TIMEOUT_SECONDS,
        ) -> bytes:
            del config_dir, description, timeout
            rendered = " ".join(arguments)
            self.assertNotIn(marker, rendered)
            if arguments[:2] == ["pull", image]:
                return b""
            if "{{json .RepoDigests}}" in arguments:
                return json.dumps([image]).encode("utf-8")
            if "{{.Id}}" in arguments:
                return ("sha256:" + "d" * 64 + "\n").encode("ascii")
            if "{{.Os}}|{{.Architecture}}" in rendered:
                return f"linux|amd64|kit|{revision}\n".encode()
            if "surface-digest" in arguments:
                return f"{surface_digest}\n".encode("ascii")
            self.fail(f"unexpected checked Docker invocation: {arguments!r}")

        def run_docker(
            arguments: list[str],
            *,
            config_dir: Path,
            timeout: int = review_current._DOCKER_TIMEOUT_SECONDS,
            input_bytes: bytes | None = None,
        ) -> subprocess.CompletedProcess[bytes]:
            del timeout
            host_files = [
                path for path in config_dir.parent.rglob("*") if path.is_file()
            ]
            for path in host_files:
                self.assertNotIn(marker.encode("utf-8"), path.read_bytes())
            self.assertFalse(
                any(
                    path.name
                    in {"gnostoa-review-input.json", "gnostoa-review-policy.json"}
                    for path in host_files
                )
            )
            observed_run.update(arguments=arguments, input_bytes=input_bytes)
            return subprocess.CompletedProcess(
                arguments,
                3,
                b'{"outcome":"INCOMPLETE","reason":"QUORUM_UNMET"}\n',
                b"",
            )

        with (
            mock.patch.object(
                review_current,
                "_checked_output",
                side_effect=checked_output,
            ),
            mock.patch.object(review_current, "_run_docker", side_effect=run_docker),
        ):
            code, payload = review_current.run_prior_integrated_judge(
                image=image,
                input_document=input_document,
                policy_document=policy_document,
                expected_revision=revision,
                expected_surface_digest=surface_digest,
            )

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        arguments = observed_run["arguments"]
        self.assertIsInstance(arguments, list)
        assert isinstance(arguments, list)
        self.assertIn("-i", arguments)
        self.assertIn("--log-driver=none", arguments)
        self.assertNotIn("--mount", arguments)
        self.assertNotIn(marker, " ".join(arguments))
        bridge = arguments[arguments.index("-c") + 1]
        self.assertIn("while len(raw) <= limit", bridge)
        self.assertIn("raw.extend(chunk)", bridge)
        self.assertIn("os.O_EXCL", bridge)
        self.assertIn("os.O_NOFOLLOW", bridge)
        self.assertIn("/tmp/gnostoa-review-input.json", bridge)
        self.assertIn("/tmp/gnostoa-review-policy.json", bridge)
        raw_envelope = observed_run["input_bytes"]
        self.assertIsInstance(raw_envelope, bytes)
        assert isinstance(raw_envelope, bytes)
        self.assertEqual(
            {"input": input_document, "policy": policy_document},
            json.loads(raw_envelope),
        )

    def test_docker_input_is_bounded_before_process_creation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            oversized = b"x" * (review_current._MAX_RUNTIME_INPUT_BYTES + 1)
            with mock.patch.object(review_current.subprocess, "Popen") as popen:
                with self.assertRaisesRegex(
                    review_current.ProtectedJudgeUnavailable,
                    "input exceeds the bounded size",
                ):
                    review_current._run_docker(
                        ["version"],
                        config_dir=config,
                        input_bytes=oversized,
                    )
            popen.assert_not_called()

    def test_docker_run_rejects_caller_owned_cleanup_identity_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            for arguments in (
                ["run", "--name", "caller-name", "example-image"],
                ["run", "--name=caller-name", "example-image"],
                ["run", "--cidfile", "/tmp/caller.cid", "example-image"],
                ["run", "--cidfile=/tmp/caller.cid", "example-image"],
            ):
                with self.subTest(arguments=arguments):
                    with self.assertRaisesRegex(
                        review_current.ProtectedJudgeUnavailable,
                        "cleanup identity option",
                    ):
                        review_current._run_identity(arguments, config_dir)

    def test_container_command_may_use_identity_like_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            for arguments in (
                ["run", "--rm", "example-image", "--name", "application-name"],
                ["run", "--rm", "example-image", "--cidfile=/app/state"],
            ):
                with self.subTest(arguments=arguments):
                    identity = review_current._run_identity(arguments, config_dir)
                    self.assertIsNotNone(identity)

    def test_docker_run_accepts_the_b16_smoke_mount_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            identity = review_current._run_identity(
                [
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network",
                    "none",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,nodev,size=32m",
                    "--mount",
                    "type=bind,src=/input,dst=/gnostoa-input,readonly",
                    "--entrypoint",
                    "python",
                    "example-image",
                    "-m",
                    "tools.review_live_entrypoint",
                ],
                config_dir,
            )

        self.assertIsNotNone(identity)

    def test_oversized_envelope_is_rejected_before_any_docker_operation(self) -> None:
        image = "ghcr.io/example/gnostoa@sha256:" + "a" * 64
        with (
            mock.patch.object(review_current, "_checked_output") as checked_output,
            mock.patch.object(review_current, "_run_docker") as run_docker,
        ):
            with self.assertRaisesRegex(
                review_current.ProtectedJudgeUnavailable,
                "input exceeds the bounded size",
            ):
                review_current.run_prior_integrated_judge(
                    image=image,
                    input_document={
                        "input": "x" * review_current._MAX_RUNTIME_INPUT_BYTES
                    },
                    policy_document={},
                    expected_revision="b" * 40,
                    expected_surface_digest="sha256:" + "c" * 64,
                )

        checked_output.assert_not_called()
        run_docker.assert_not_called()

    def test_docker_streams_bounded_input_while_draining_output(self) -> None:
        payload = b"x" * 1_048_576
        expected = str(len(payload)).encode("ascii")
        script = (
            "import sys;"
            "data=sys.stdin.buffer.read();"
            "sys.stdout.buffer.write(str(len(data)).encode('ascii'))"
        )
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                review_current,
                "_docker_executable",
                return_value=sys.executable,
            ):
                result = review_current._run_docker(
                    ["-c", script],
                    config_dir=Path(directory),
                    input_bytes=payload,
                    timeout=5,
                )

        self.assertEqual(0, result.returncode)
        self.assertEqual(expected, result.stdout)
        self.assertEqual(b"", result.stderr)

    def test_early_child_stdin_close_does_not_deadlock(self) -> None:
        script = (
            "import os, sys, time;"
            "os.close(0);"
            "sys.stdout.write('closed');"
            "sys.stdout.flush();"
            "time.sleep(0.1)"
        )
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(
                review_current,
                "_docker_executable",
                return_value=sys.executable,
            ):
                result = review_current._run_docker(
                    ["-c", script],
                    config_dir=Path(directory),
                    input_bytes=b"x" * 1_048_576,
                    timeout=5,
                )

        self.assertEqual(0, result.returncode)
        self.assertEqual(b"closed", result.stdout)

    def test_nonblocking_stdin_setup_failure_uses_predeclared_cleanup_identity(
        self,
    ) -> None:
        script = "import time; time.sleep(30)"
        real_popen = subprocess.Popen
        observed: dict[str, object] = {}

        def start_process(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.Popen[bytes]:
            observed["command"] = command
            process = real_popen(
                [sys.executable, "-c", script],
                **kwargs,
            )
            observed["process"] = process
            return process

        cleanup = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["docker", "rm", "-f", "candidate"],
                0,
            )
        )
        requested_name = "gnostoa-protected-explicit-test"
        with tempfile.TemporaryDirectory() as directory:
            try:
                with (
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="docker",
                    ) as docker_executable,
                    mock.patch.object(
                        review_current.subprocess,
                        "Popen",
                        side_effect=start_process,
                    ),
                    mock.patch.object(
                        review_current.os,
                        "set_blocking",
                        side_effect=OSError("cannot configure stdin"),
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "run",
                        cleanup,
                    ),
                ):
                    with self.assertRaisesRegex(
                        review_current.ProtectedJudgeUnavailable,
                        "cannot configure stdin",
                    ):
                        review_current._run_docker(
                            ["run", "--rm", "example-image"],
                            config_dir=Path(directory),
                            input_bytes=b"payload",
                            timeout=5,
                            run_name=requested_name,
                        )
            finally:
                process = observed.get("process")
                if isinstance(process, subprocess.Popen) and process.poll() is None:
                    process.kill()
                    process.wait()

            command = observed["command"]
            self.assertIsInstance(command, list)
            assert isinstance(command, list)
            self.assertEqual(1, command.count("--name"))
            self.assertIn("--name", command)
            name = command[command.index("--name") + 1]
            self.assertEqual(requested_name, name)
            cleanup.assert_called_once()
            self.assertEqual(
                ["docker", "rm", "-f", name],
                cleanup.call_args.args[0],
            )
            docker_executable.assert_called_once_with()
            process = observed["process"]
            self.assertIsInstance(process, subprocess.Popen)
            assert isinstance(process, subprocess.Popen)
            self.assertIsNotNone(process.poll())

    def test_failed_cleanup_retries_and_retains_recovery_identity(self) -> None:
        real_popen = subprocess.Popen
        observed: dict[str, object] = {}

        def start_process(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.Popen[bytes]:
            observed["command"] = command
            cidfile = Path(command[command.index("--cidfile") + 1])
            cidfile.write_text("a" * 64, encoding="ascii")
            observed["cidfile"] = cidfile
            process = real_popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                **kwargs,
            )
            observed["process"] = process
            return process

        cleanup = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["docker", "rm", "-f", "candidate"],
                1,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            try:
                with (
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="docker",
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "Popen",
                        side_effect=start_process,
                    ),
                    mock.patch.object(
                        review_current.os,
                        "set_blocking",
                        side_effect=OSError("cannot configure stdin"),
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "run",
                        cleanup,
                    ),
                ):
                    with self.assertRaisesRegex(
                        review_current.ProtectedJudgeUnavailable,
                        "cleanup.*recovery identity",
                    ):
                        review_current._run_docker(
                            ["run", "--rm", "example-image"],
                            config_dir=Path(directory),
                            input_bytes=b"payload",
                            timeout=5,
                        )
            finally:
                process = observed.get("process")
                if isinstance(process, subprocess.Popen) and process.poll() is None:
                    process.kill()
                    process.wait()

            self.assertEqual(3, cleanup.call_count)
            for cleanup_call in cleanup.call_args_list:
                self.assertEqual(
                    ["docker", "rm", "-f", "a" * 64],
                    cleanup_call.args[0],
                )
            cidfile = observed["cidfile"]
            self.assertIsInstance(cidfile, Path)
            assert isinstance(cidfile, Path)
            self.assertTrue(cidfile.exists())

    def test_output_overflow_aborts_and_cleans_the_named_container(self) -> None:
        real_popen = subprocess.Popen
        observed: dict[str, object] = {}

        def start_process(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.Popen[bytes]:
            observed["command"] = command
            cidfile = Path(command[command.index("--cidfile") + 1])
            cidfile.write_text("b" * 64, encoding="ascii")
            process = real_popen(
                [
                    sys.executable,
                    "-c",
                    "import sys, time; "
                    "sys.stdout.buffer.write(b'x' * 65); "
                    "sys.stdout.buffer.flush(); time.sleep(30)",
                ],
                **kwargs,
            )
            observed["process"] = process
            return process

        cleanup = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["docker", "rm", "-f", "candidate"],
                0,
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            try:
                with (
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="docker",
                    ),
                    mock.patch.object(
                        review_current,
                        "_MAX_RUNTIME_OUTPUT_BYTES",
                        64,
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "Popen",
                        side_effect=start_process,
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "run",
                        cleanup,
                    ),
                ):
                    with self.assertRaisesRegex(
                        review_current.ProtectedJudgeUnavailable,
                        "stdout exceeds the bounded size",
                    ):
                        review_current._run_docker(
                            ["run", "--rm", "example-image"],
                            config_dir=Path(directory),
                            timeout=5,
                        )
            finally:
                process = observed.get("process")
                if isinstance(process, subprocess.Popen) and process.poll() is None:
                    process.kill()
                    process.wait()

        cleanup.assert_called_once()
        self.assertEqual(
            ["docker", "rm", "-f", "b" * 64],
            cleanup.call_args.args[0],
        )

    def test_non_ascii_cid_falls_back_to_the_predeclared_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            cidfile = config_dir / "candidate.cid"
            cidfile.write_bytes(b"\xff\xfe")
            identity = review_current._ContainerRunIdentity(
                name="gnostoa-protected-test",
                cidfile=cidfile,
            )
            cleanup = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    ["docker", "rm", "-f", identity.name],
                    0,
                )
            )
            with (
                mock.patch.object(
                    review_current,
                    "_docker_executable",
                    return_value="docker",
                ),
                mock.patch.object(review_current.subprocess, "run", cleanup),
            ):
                review_current._cleanup_container(identity, config_dir)

        self.assertEqual(
            ["docker", "rm", "-f", identity.name],
            cleanup.call_args.args[0],
        )

    def test_timeout_failure_survives_a_failed_cleanup(self) -> None:
        """A failed cleanup must not replace the primary timeout diagnostic."""

        real_popen = subprocess.Popen
        observed: dict[str, object] = {}

        def start_process(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.Popen[bytes]:
            cidfile = Path(command[command.index("--cidfile") + 1])
            cidfile.write_text("c" * 64, encoding="ascii")
            process = real_popen(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                **kwargs,
            )
            observed["process"] = process
            return process

        cleanup = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["docker", "rm", "-f", "candidate"],
                1,
                b"",
                b"Error response from daemon: cannot connect to the daemon",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            try:
                with (
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="docker",
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "Popen",
                        side_effect=start_process,
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "run",
                        cleanup,
                    ),
                ):
                    with self.assertRaises(
                        review_current.ProtectedJudgeUnavailable
                    ) as raised:
                        review_current._run_docker(
                            ["run", "--rm", "example-image"],
                            config_dir=Path(directory),
                            timeout=1,
                        )
            finally:
                process = observed.get("process")
                if isinstance(process, subprocess.Popen) and process.poll() is None:
                    process.kill()
                    process.wait()

        message = str(raised.exception)
        self.assertIn("timed out", message)
        self.assertIn("cleanup", message)
        self.assertIn("recovery identity", message)
        self.assertEqual(3, cleanup.call_count)

    def test_output_overflow_failure_survives_a_failed_cleanup(self) -> None:
        """A failed cleanup must not replace the primary bounded-size failure."""

        real_popen = subprocess.Popen
        observed: dict[str, object] = {}

        def start_process(
            command: list[str],
            **kwargs: object,
        ) -> subprocess.Popen[bytes]:
            cidfile = Path(command[command.index("--cidfile") + 1])
            cidfile.write_text("d" * 64, encoding="ascii")
            process = real_popen(
                [
                    sys.executable,
                    "-c",
                    "import sys, time; "
                    "sys.stdout.buffer.write(b'x' * 65); "
                    "sys.stdout.buffer.flush(); time.sleep(30)",
                ],
                **kwargs,
            )
            observed["process"] = process
            return process

        cleanup = mock.Mock(
            return_value=subprocess.CompletedProcess(
                ["docker", "rm", "-f", "candidate"],
                1,
                b"",
                b"Error response from daemon: device or resource busy",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            try:
                with (
                    mock.patch.object(
                        review_current,
                        "_docker_executable",
                        return_value="docker",
                    ),
                    mock.patch.object(
                        review_current,
                        "_MAX_RUNTIME_OUTPUT_BYTES",
                        64,
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "Popen",
                        side_effect=start_process,
                    ),
                    mock.patch.object(
                        review_current.subprocess,
                        "run",
                        cleanup,
                    ),
                ):
                    with self.assertRaises(
                        review_current.ProtectedJudgeUnavailable
                    ) as raised:
                        review_current._run_docker(
                            ["run", "--rm", "example-image"],
                            config_dir=Path(directory),
                            timeout=5,
                        )
            finally:
                process = observed.get("process")
                if isinstance(process, subprocess.Popen) and process.poll() is None:
                    process.kill()
                    process.wait()

        message = str(raised.exception)
        self.assertIn("stdout exceeds the bounded size", message)
        self.assertIn("cleanup", message)
        self.assertIn("recovery identity", message)

    def test_absent_container_reconciles_as_successful_cleanup(self) -> None:
        """An already-removed container is absence, not a cleanup failure."""

        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            identity = review_current._ContainerRunIdentity(
                name="gnostoa-protected-test",
                cidfile=config_dir / "candidate.cid",
            )
            cleanup = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    ["docker", "rm", "-f", identity.name],
                    1,
                    b"",
                    "Error response from daemon: No such container: "
                    f"{identity.name}".encode(),
                )
            )
            with (
                mock.patch.object(
                    review_current,
                    "_docker_executable",
                    return_value="docker",
                ),
                mock.patch.object(review_current.subprocess, "run", cleanup),
            ):
                issue = review_current._cleanup_container(identity, config_dir)

        self.assertIsNone(issue)
        cleanup.assert_called_once()

    def test_non_absence_cleanup_failure_is_retried_and_reported(self) -> None:
        """Every other bounded cleanup diagnostic stays fail-closed."""

        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            identity = review_current._ContainerRunIdentity(
                name="gnostoa-protected-test",
                cidfile=config_dir / "candidate.cid",
            )
            cleanup = mock.Mock(
                return_value=subprocess.CompletedProcess(
                    ["docker", "rm", "-f", identity.name],
                    1,
                    b"",
                    b"Error response from daemon: container is marked for removal",
                )
            )
            with (
                mock.patch.object(
                    review_current,
                    "_docker_executable",
                    return_value="docker",
                ),
                mock.patch.object(review_current.subprocess, "run", cleanup),
            ):
                issue = review_current._cleanup_container(identity, config_dir)

        self.assertIsNotNone(issue)
        assert issue is not None
        self.assertIn("cleanup", issue)
        self.assertIn("marked for removal", issue)
        self.assertEqual(3, cleanup.call_count)

    def test_abort_reap_is_bounded_and_cleanup_runs_after_reap_timeout(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            identity = review_current._ContainerRunIdentity(
                name="gnostoa-protected-test",
                cidfile=config_dir / "candidate.cid",
            )
            process = mock.Mock(spec=subprocess.Popen)
            process.poll.return_value = None
            process.wait.side_effect = subprocess.TimeoutExpired(
                ["docker", "run"],
                1,
            )
            with mock.patch.object(
                review_current,
                "_cleanup_container",
                return_value=None,
            ) as cleanup:
                detail = review_current._abort_docker_run(
                    process,
                    identity,
                    config_dir,
                )

        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertRegex(detail, "reap.*recovery identity")

        process.wait.assert_called_once_with(
            timeout=review_current._PROCESS_REAP_TIMEOUT_SECONDS
        )
        cleanup.assert_called_once_with(identity, config_dir)


if __name__ == "__main__":
    unittest.main()
