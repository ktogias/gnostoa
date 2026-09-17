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
            del config_dir, timeout
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
            mock.patch.object(
                Path,
                "write_text",
                side_effect=AssertionError("protected payload reached a host file"),
            ),
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
        self.assertNotIn("--mount", arguments)
        self.assertNotIn(marker, " ".join(arguments))
        bridge = arguments[arguments.index("-c") + 1]
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
        script = "import sys; sys.stdout.write('closed')"
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


if __name__ == "__main__":
    unittest.main()
