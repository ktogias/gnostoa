from __future__ import annotations

import contextlib
import importlib
import inspect
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from test_r2a_p2b_b16_publication import _has_direct_top_level_shell_sequence

from tools import review_check, review_protected
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
GUARDRAIL_PATH = ROOT / "policy" / "guardrails.yaml"
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0077-activate-r2a-p2b-b2-through-prior-effective-b16.md"
)
CONSUMER_PATH = "tasks/issue-11-r2a-current-advisory-consumer.json"
PROTECTED_REPOSITORY = "https://github.com/ktogias/gnostoa.git"
B16_SOURCE_REVISION = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- public source revision
B16_PUBLIC_SURFACE_DIGEST = "sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57"  # pragma: allowlist secret -- public surface digest
B16_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867"  # pragma: allowlist secret -- public OCI digest
)
_DIGEST_IMAGE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)+"
    r"@sha256:[0-9a-f]{64}$"
)


def _consumer_authority() -> dict[str, object]:
    document = json.loads((ROOT / CONSUMER_PATH).read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError("protected outer-consumer authority must be an object")
    return document


def _current_advisory_input() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "subject": {
            "repository": "https://github.com/ktogias/gnostoa",
            "change_request": {"kind": "pull_request", "id": "p2b-b2-red"},
            "head_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # pragma: allowlist secret -- synthetic public test commit
            "comparison": {
                "kind": "merge_base",
                "commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",  # pragma: allowlist secret -- synthetic public test merge base
            },
            "observed_at": "2026-09-16T00:00:00Z",
        },
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": "2026-09-16T00:00:00Z",
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "authority": {},
        "acquired_judge": {},
        "evidence_set": {
            "observed_at": "2026-09-16T00:00:00Z",
            "sources": [],
            "observations": [],
        },
        "qualification_snapshot": {},
    }


def _load_outer() -> object:
    try:
        return importlib.import_module("tools.review_outer")
    except ModuleNotFoundError as exc:
        raise AssertionError(
            "P2B_B2_PRIOR_EFFECTIVE_OUTER_RUNTIME_UNAVAILABLE"
        ) from exc


class ReviewAssuranceP2bB2ActivationRedTests(unittest.TestCase):
    def test_protected_consumer_acquisition_is_fixed_to_gnostoa_main_record(
        self,
    ) -> None:
        protected = ProtectedMainDocument(
            protected_main_revision="c" * 40,
            document=_consumer_authority(),
        )
        acquire_consumer = getattr(
            review_protected,
            "acquire_gnostoa_current_advisory_consumer",
            None,
        )
        self.assertTrue(
            callable(acquire_consumer),
            "P2B_B2_PROTECTED_CONSUMER_ACQUISITION_UNAVAILABLE",
        )
        if not callable(acquire_consumer):
            return
        with mock.patch.object(
            review_protected,
            "_acquire_from_repository",
            return_value=protected,
        ) as acquire:
            observed = acquire_consumer()
        self.assertEqual(protected, observed)
        acquire.assert_called_once_with(PROTECTED_REPOSITORY, CONSUMER_PATH)

    def test_candidate_cli_delegates_and_forwards_prior_effective_bytes_exactly(
        self,
    ) -> None:
        input_document = _current_advisory_input()
        raw_result = (
            b'{"binding":false,"outcome":"INCOMPLETE","reason":"QUORUM_UNMET"}\n'
        )
        delegate = mock.Mock(return_value=(3, raw_result))

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "input.json"
            input_path.write_text(json.dumps(input_document), encoding="utf-8")
            output_bytes = io.BytesIO()
            stdout = io.TextIOWrapper(
                output_bytes, encoding="utf-8", write_through=True
            )
            with (
                mock.patch.object(
                    review_check,
                    "run_prior_effective_current_advisory",
                    delegate,
                    create=True,
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = review_check.main(["--input", str(input_path)])
            stdout.flush()
            observed = output_bytes.getvalue()

        self.assertEqual(3, code, "P2B_B2_CLI_OUTER_DELEGATION_UNAVAILABLE")
        self.assertEqual(raw_result, observed)
        delegate.assert_called_once_with(input_document)

    def test_prior_effective_outer_runtime_exposes_only_untrusted_input(self) -> None:
        outer = _load_outer()
        runner = getattr(outer, "run_prior_effective_current_advisory", None)
        self.assertTrue(callable(runner), "P2B_B2_OUTER_RUNNER_UNAVAILABLE")
        if callable(runner):
            self.assertEqual(
                ["input_document"], list(inspect.signature(runner).parameters)
            )

    def test_isolated_nested_daemon_plan_shares_only_internal_socket_and_tmp(
        self,
    ) -> None:
        outer = _load_outer()
        build_plan = getattr(outer, "_build_isolated_execution_plan", None)
        self.assertTrue(callable(build_plan), "P2B_B2_ISOLATED_DAEMON_PLAN_UNAVAILABLE")
        if not callable(build_plan):
            return

        authority = _consumer_authority()
        consumer = authority["acquired_consumer"]
        self.assertIsInstance(consumer, dict)
        assert isinstance(consumer, dict)
        socket_volume = "gnostoa-r2a-socket-test"
        tmp_volume = "gnostoa-r2a-tmp-test"
        daemon_name = "gnostoa-r2a-daemon-test"
        outer_name = "gnostoa-r2a-outer-test"
        input_dir = Path("/tmp/gnostoa-r2a-untrusted-input-test")
        plan = build_plan(
            consumer=consumer,
            input_dir=input_dir,
            socket_volume=socket_volume,
            tmp_volume=tmp_volume,
            daemon_name=daemon_name,
            outer_name=outer_name,
        )
        self.assertIsInstance(plan, dict)
        assert isinstance(plan, dict)
        daemon = plan.get("daemon")
        protected_outer = plan.get("outer")
        self.assertIsInstance(daemon, list)
        self.assertIsInstance(protected_outer, list)
        assert isinstance(daemon, list)
        assert isinstance(protected_outer, list)
        daemon_args = [str(item) for item in daemon]
        outer_args = [str(item) for item in protected_outer]

        daemon_image = plan.get("daemon_image")
        self.assertIsInstance(daemon_image, str)
        assert isinstance(daemon_image, str)
        self.assertIsNotNone(_DIGEST_IMAGE.fullmatch(daemon_image))
        self.assertIn("--privileged", daemon_args)
        self.assertIn(f"{socket_volume}:/gnostoa-docker", daemon_args)
        self.assertNotIn(f"{socket_volume}:/var/run", daemon_args)
        self.assertIn(f"{tmp_volume}:/tmp", daemon_args)
        daemon_image_index = daemon_args.index(daemon_image)
        self.assertEqual("dockerd", daemon_args[daemon_image_index + 1])
        self.assertEqual(
            1, daemon_args.count("--host=unix:///gnostoa-docker/docker.sock")
        )
        self.assertEqual(1, daemon_args.count("--group=10001"))
        self.assertNotIn("tcp://0.0.0.0:2375", " ".join(daemon_args))
        self.assertNotIn("tcp://0.0.0.0:2376", " ".join(daemon_args))

        self.assertIn(B16_OCI_IMAGE, outer_args)
        self.assertIn("--read-only", outer_args)
        self.assertIn("--cap-drop", outer_args)
        self.assertIn("ALL", outer_args)
        self.assertIn("no-new-privileges", " ".join(outer_args))
        self.assertIn(f"{socket_volume}:/var/run", outer_args)
        self.assertNotIn("/gnostoa-docker", " ".join(outer_args))
        self.assertIn(f"{tmp_volume}:/tmp", outer_args)
        self.assertIn(
            f"type=bind,src={input_dir},dst=/gnostoa-input,readonly",
            outer_args,
        )
        self.assertNotIn("--privileged", outer_args)
        joined = " ".join(outer_args)
        self.assertNotIn("src=/var/run/docker.sock", joined)
        self.assertNotIn("/usr/bin/docker", joined)
        self.assertNotIn("GNOSTOA_R2A_CANDIDATE_IMAGE", joined)
        self.assertNotIn(str(ROOT), joined)
        self.assertEqual(B16_SOURCE_REVISION, consumer.get("runtime_revision"))
        self.assertEqual(
            B16_PUBLIC_SURFACE_DIGEST, consumer.get("public_surface_digest")
        )

    def test_daemon_control_plane_rejects_listening_tcp_ports(self) -> None:
        outer = _load_outer()
        no_forbidden_listener = mock.Mock(
            returncode=0,
            stdout=(
                b"  sl  local_address rem_address   st\n"
                b"   0: 0100007F:0016 00000000:0000 0A\n"
            ),
            stderr=b"",
        )
        with mock.patch.object(
            outer, "_run_docker", return_value=no_forbidden_listener
        ) as run:
            outer._verify_daemon_control_plane(
                "gnostoa-r2a-daemon-test", Path("/tmp/config")
            )
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(
            [
                "exec",
                "gnostoa-r2a-daemon-test",
                "sh",
                "-ec",
                "cat /proc/1/net/tcp; [ ! -r /proc/1/net/tcp6 ] || cat /proc/1/net/tcp6",
            ],
            command,
        )

        forbidden_listeners = mock.Mock(
            returncode=0,
            stdout=(
                b"  sl  local_address rem_address   st\n"
                b"   0: 00000000:0947 00000000:0000 0A\n"
                b"  sl  local_address rem_address   st\n"
                b"   0: 00000000000000000000000000000000:0948 "
                b"00000000000000000000000000000000:0000 0A\n"
            ),
            stderr=b"",
        )
        with mock.patch.object(outer, "_run_docker", return_value=forbidden_listeners):
            with self.assertRaisesRegex(
                outer.PriorEffectiveOuterUnavailable,
                "unexpectedly exposes TCP control plane on 2375, 2376",
            ):
                outer._verify_daemon_control_plane(
                    "gnostoa-r2a-daemon-test", Path("/tmp/config")
                )

        inspection_failure = mock.Mock(
            returncode=1,
            stdout=b"",
            stderr=b"synthetic inspection failure",
        )
        with mock.patch.object(outer, "_run_docker", return_value=inspection_failure):
            with self.assertRaisesRegex(
                outer.PriorEffectiveOuterUnavailable,
                "cannot inspect isolated Docker daemon listening sockets",
            ):
                outer._verify_daemon_control_plane(
                    "gnostoa-r2a-daemon-test", Path("/tmp/config")
                )

    def test_successful_create_registers_cleanup_name_before_reply_validation(
        self,
    ) -> None:
        outer = _load_outer()
        config_dir = Path("/tmp/gnostoa-r2a-test-config")

        owned_volumes: list[str] = []
        volume_name = "gnostoa-r2a-volume-test"
        with mock.patch.object(
            outer, "_checked_output", return_value=b"malformed-volume-reply\n"
        ):
            with self.assertRaisesRegex(
                outer.PriorEffectiveOuterUnavailable,
                "malformed isolated-volume identity",
            ):
                outer._volume_create(volume_name, config_dir, owned_volumes)
        self.assertEqual([volume_name], owned_volumes)

        owned_containers: list[str] = []
        container_name = "gnostoa-r2a-container-test"
        with mock.patch.object(
            outer, "_checked_output", return_value=b"malformed-container-reply\n"
        ):
            with self.assertRaisesRegex(
                outer.PriorEffectiveOuterUnavailable,
                "malformed isolated-container identity",
            ):
                outer._container_create(
                    [], container_name, config_dir, owned_containers
                )
        self.assertEqual([container_name], owned_containers)

    def test_cleanup_retries_transient_container_failure(self) -> None:
        outer = _load_outer()
        failed = mock.Mock(returncode=1, stderr=b"synthetic busy")
        succeeded = mock.Mock(returncode=0, stderr=b"")
        with (
            mock.patch.object(
                outer, "_run_docker", side_effect=[failed, succeeded]
            ) as run,
            mock.patch.object(outer.time, "sleep") as sleep,
        ):
            issue = outer._remove_container(
                "gnostoa-r2a-container-test", Path("/tmp/config")
            )
        self.assertIsNone(issue)
        self.assertEqual(2, run.call_count)
        sleep.assert_called_once()

    def test_tmp_initializer_keeps_helper_registered_when_cleanup_fails(self) -> None:
        outer = _load_outer()
        owned: list[str] = []

        def create(
            arguments: list[str],
            name: str,
            config_dir: Path,
            owned_containers: list[str],
        ) -> str:
            del arguments, config_dir
            owned_containers.append(name)
            return name

        with (
            mock.patch.object(outer, "_container_create", side_effect=create),
            mock.patch.object(
                outer,
                "_run_docker",
                return_value=mock.Mock(returncode=0, stderr=b""),
            ),
            mock.patch.object(
                outer,
                "_remove_container",
                return_value="synthetic cleanup failure",
            ),
        ):
            with self.assertRaisesRegex(
                outer.PriorEffectiveOuterUnavailable,
                "synthetic cleanup failure",
            ):
                outer._initialize_tmp_volume(
                    tmp_volume="gnostoa-r2a-tmp-test",
                    config_dir=Path("/tmp/config"),
                    owned_containers=owned,
                )
        self.assertEqual(1, len(owned))

    def test_outer_error_envelope_is_closed_and_typed(self) -> None:
        outer = _load_outer()
        error_codes = {
            "MALFORMED_INVOCATION",
            "UNSUPPORTED_INPUT",
            "CONFIGURATION_ERROR",
            "TOOL_ERROR",
        }
        for code in error_codes:
            payload = {
                "error": {
                    "code": code,
                    "message": "synthetic protected error",
                    "details": {},
                }
            }
            raw = (outer.canonical_json(payload) + "\n").encode("utf-8")
            with self.subTest(valid_code=code):
                self.assertEqual(payload, outer._decode_outer_result(2, raw))

        invalid_payloads = (
            {
                "error": {
                    "code": "UNKNOWN_ERROR",
                    "message": "synthetic protected error",
                    "details": {},
                }
            },
            {
                "error": {
                    "code": "TOOL_ERROR",
                    "message": "synthetic protected error",
                }
            },
            {
                "error": {
                    "code": "TOOL_ERROR",
                    "message": "synthetic protected error",
                    "details": [],
                }
            },
            {
                "error": {
                    "code": "TOOL_ERROR",
                    "message": "synthetic protected error",
                    "details": {},
                    "extra": True,
                }
            },
            {
                "error": {
                    "code": "TOOL_ERROR",
                    "message": "synthetic protected error",
                    "details": {},
                },
                "extra": True,
            },
        )
        for payload in invalid_payloads:
            raw = (outer.canonical_json(payload) + "\n").encode("utf-8")
            with self.subTest(invalid_payload=payload):
                with self.assertRaisesRegex(
                    outer.PriorEffectiveOuterUnavailable,
                    "error envelope is malformed",
                ):
                    outer._decode_outer_result(2, raw)

    def test_tmp_setup_failure_returns_canonical_tool_error(self) -> None:
        outer = _load_outer()
        protected = ProtectedMainDocument(
            protected_main_revision="c" * 40,
            document=_consumer_authority(),
        )
        with (
            mock.patch.object(
                outer,
                "acquire_gnostoa_current_advisory_consumer",
                return_value=protected,
            ),
            mock.patch.object(
                outer.tempfile,
                "TemporaryDirectory",
                side_effect=OSError("synthetic /tmp unavailable"),
            ),
        ):
            code, raw = outer.run_prior_effective_current_advisory(
                _current_advisory_input()
            )
        payload = json.loads(raw.decode("utf-8"))
        self.assertEqual(2, code)
        self.assertEqual("TOOL_ERROR", payload["error"]["code"])
        self.assertIn(
            "synthetic /tmp unavailable", payload["error"]["details"]["error"]
        )

    def test_b2_has_durable_activation_decision_and_guardrail_ownership(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(), "P2B_B2_ACTIVATION_DECISION_UNAVAILABLE"
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn("Decision 0077", decision)
        self.assertIn("Decision 0076", decision)
        self.assertIn(
            "kit.decision.0077.activate-r2a-p2b-b2-through-prior-effective-b16",
            decision,
        )
        self.assertIn(B16_SOURCE_REVISION, decision)
        self.assertIn(B16_PUBLIC_SURFACE_DIGEST, decision)
        self.assertIn(B16_OCI_IMAGE, decision)
        self.assertIn("isolated nested Docker daemon", decision)
        self.assertIn("does not authorize those later publication", decision)

        decision_path = "knowledge/decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md"
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(f'- "{decision_path}"', workflow)

        guardrails = GUARDRAIL_PATH.read_text(encoding="utf-8")
        for protected_path in (
            decision_path,
            "tools/review_outer.py",
            "ci/review_outer_smoke.py",
            "tests/test_review_assurance_p2b_b2_activation_red.py",
        ):
            self.assertIn(f"- {protected_path}", guardrails)

    def test_dedicated_r2a_workflow_executes_canonical_b2_contract(self) -> None:
        workflow = yaml.load(
            WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)
        on = workflow.get("on")
        self.assertIsInstance(on, dict)
        assert isinstance(on, dict)
        pull_request = on.get("pull_request")
        self.assertIsInstance(pull_request, dict)
        assert isinstance(pull_request, dict)
        paths = pull_request.get("paths")
        self.assertIsInstance(paths, list)
        assert isinstance(paths, list)

        test_path = "tests/test_review_assurance_p2b_b2_activation_red.py"
        self.assertIn(test_path, paths)
        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        job = jobs.get("dormant-current-advisory-consumer")
        self.assertIsInstance(job, dict)
        assert isinstance(job, dict)
        self.assertEqual("protected-current-advisory-consumer", job.get("name"))
        steps = job.get("steps")
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        matches = [
            step
            for step in steps
            if isinstance(step, dict)
            and step.get("name")
            == "Run protected current-advisory consumer contract tests via native orchestration fallback"
        ]
        self.assertEqual(1, len(matches))
        run = matches[0].get("run")
        self.assertIsInstance(run, str)
        assert isinstance(run, str)
        command = f"PYTHONPATH=. python {test_path}"
        self.assertTrue(
            _has_direct_top_level_shell_sequence(run, (command,)),
            "the B2 contract must execute directly in dedicated R2A verification",
        )


if __name__ == "__main__":
    unittest.main()
