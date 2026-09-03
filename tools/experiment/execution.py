from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from . import backend, capture, relay, smoke
from .evidence import ATTEST_SCHEMA, parse_input_identity_mapping
from .profile import (
    PROFILE_SCHEMA,
    VALIDATION_SCHEMA,
    RunnerError,
    clean_environment_args,
    executor_provenance,
    load_profile,
    profile_network,
    profile_paths,
    profile_runtime,
    profile_timeout_seconds,
    string_list,
    validate_profile_data,
)

PROBE_SCHEMA = backend.PROBE_SCHEMA
SMOKE_SCHEMA = smoke.SMOKE_SCHEMA
SIZE_SCHEMA = capture.SIZE_SCHEMA
RUN_SCHEMA = "gnostoa-experiment-runner-result/v1"
ProbeResult = backend.ProbeResult
Handler = Callable[[argparse.Namespace], int]
SCHEMA_COMPATIBILITY = (PROFILE_SCHEMA, ATTEST_SCHEMA)


def emit(payload: Mapping[str, object]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, separators=(",", ":")))


def run_profile_command(
    profile_path: Path,
    requested_backend: str,
    command: Sequence[str],
) -> tuple[int, dict[str, object]]:
    profile = load_profile(profile_path)
    reasons = validate_profile_data(profile, for_run=True)
    if reasons:
        return 2, {
            "schema": RUN_SCHEMA,
            "status": "BLOCKED",
            "backend": None,
            "backend_requested": requested_backend,
            "backend_resolved": None,
            "reasons": reasons,
        }
    if not command:
        return 2, {
            "schema": RUN_SCHEMA,
            "status": "BLOCKED",
            "backend": None,
            "backend_requested": requested_backend,
            "backend_resolved": None,
            "reasons": ["empty-command"],
        }

    image, relay_image = profile_runtime(profile)
    timeout_seconds = profile_timeout_seconds(profile)
    probe = backend.probe_backend(requested_backend, image=image)
    resolved_backend = probe.backend
    if probe.status != "AVAILABLE" or resolved_backend != "oci":
        return 2, {
            "schema": RUN_SCHEMA,
            "status": "BLOCKED",
            "backend": None,
            "backend_requested": requested_backend,
            "backend_resolved": resolved_backend,
            "reasons": probe.reasons,
        }

    read_roots, project_text, evidence_text, temporary_roots, _ = profile_paths(profile)
    project = Path(project_text)
    evidence = Path(evidence_text)
    evidence.mkdir(parents=True, exist_ok=True)
    mode, allow = profile_network(profile)
    reserved_names = ["run-stdout.log", "run-stderr.log", "run-result.json"]
    if mode == "restricted":
        reserved_names.append("run-network.jsonl")

    evidence_fd, evidence_identity = capture.open_bound_directory(
        evidence,
        "evidence-root",
    )
    internal_id = ""
    external_id = ""
    relay_id = ""
    try:
        capture.ensure_directory_names_absent(
            evidence_fd,
            reserved_names,
            label="evidence-output",
        )

        if mode == "none":
            network_args = ["--network", "none"]
        elif mode == "restricted":
            if relay_image is None:
                raise RunnerError("relay-image-missing")
            internal_id, external_id, relay_id = backend.create_restricted_network(
                relay_image, allow
            )
            network_args = [
                "--network",
                internal_id,
                "--env",
                "HTTP_PROXY=http://relay:8080",
                "--env",
                "HTTPS_PROXY=http://relay:8080",
                "--env",
                "ALL_PROXY=http://relay:8080",
                "--env",
                "NO_PROXY=",
            ]
        else:
            raise RunnerError("unsupported-network-mode")

        env_args, admitted_env_names = clean_environment_args(profile)
        uid = os.getuid() if hasattr(os, "getuid") else 10001
        gid = os.getgid() if hasattr(os, "getgid") else 10001
        create_args = [
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{uid}:{gid}",
            "--env",
            "HOME=/tmp",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,mode=1777,size=256m",
            *network_args,
            *env_args,
        ]
        for index, root in enumerate(read_roots):
            create_args.extend(
                [
                    "--mount",
                    f"type=bind,source={root},target=/inputs/{index},readonly",
                ]
            )
        create_args.extend(["--mount", f"type=bind,source={project},target=/workspace"])
        create_args.extend(["--mount", f"type=bind,source={evidence},target=/evidence"])
        for index, root in enumerate(temporary_roots):
            create_args.extend(
                ["--mount", f"type=bind,source={root},target=/scratch/{index}"]
            )
        create_args.extend(["--workdir", "/workspace", image, *command])

        mounted_roots = [*read_roots, project_text, evidence_text, *temporary_roots]
        with tempfile.TemporaryDirectory(
            prefix="gnostoa-runner-capture-"
        ) as raw_capture:
            capture_root = Path(raw_capture)
            capture.ensure_private_capture_root(capture_root, mounted_roots)
            staged_stdout = capture_root / "run-stdout.log"
            staged_stderr = capture_root / "run-stderr.log"
            staged_network = capture_root / "run-network.jsonl"
            container_id = ""
            with (
                staged_stdout.open("xb") as stdout_file,
                staged_stderr.open("xb") as stderr_file,
            ):
                container_id = backend.require_docker_object_id(
                    backend.docker_checked("create", *create_args),
                    "container",
                )
                try:
                    subprocess.run(
                        [
                            backend.docker_executable(),
                            "start",
                            "--attach",
                            container_id,
                        ],
                        check=False,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        timeout=timeout_seconds,
                    )
                    exit_code = backend.container_exit_code(container_id)
                finally:
                    backend.ensure_container_absent(container_id)

            capture.assert_visible_directory(
                evidence,
                evidence_identity,
                "evidence-root",
            )
            capture.ensure_directory_names_absent(
                evidence_fd,
                reserved_names,
                label="evidence-output",
            )

            if relay_id:
                backend.ensure_container_stopped(relay_id)
                capture.stream_container_logs(relay_id, staged_network)

            config_digest = capture.run_configuration_digest(
                profile_path,
                requested_backend,
                resolved_backend,
                command,
            )
            input_identities = string_list(
                profile.get("input_identities", []), "input_identities"
            )
            stdout_attestation = capture.attest_payload(
                staged_stdout,
                "gnostoa-experiment-runner",
                "1",
                config_digest,
                input_identities,
            )
            stderr_attestation = capture.attest_payload(
                staged_stderr,
                "gnostoa-experiment-runner",
                "1",
                config_digest,
                input_identities,
            )
            network_attestation: dict[str, object] | None = None
            if relay_id:
                network_attestation = capture.attest_payload(
                    staged_network,
                    "gnostoa-experiment-runner-relay",
                    "1",
                    config_digest,
                    input_identities,
                )

            archive_limit = profile.get("archive_limit_bytes")
            workspace_size_observation: dict[str, object] | None = None
            if isinstance(archive_limit, int) and not isinstance(archive_limit, bool):
                observed, method = capture.measured_path_size(project)
                workspace_size_observation = {
                    "bytes": observed,
                    "configured_archive_limit_bytes": archive_limit,
                    "measurement": method,
                    "note": "workspace observation is not an archive-size substitute",
                }

            payload: dict[str, object] = {
                "schema": RUN_SCHEMA,
                "status": "PASS" if exit_code == 0 else "FAIL",
                "backend": resolved_backend,
                "backend_requested": requested_backend,
                "backend_resolved": resolved_backend,
                "exit_code": exit_code,
                "timeout_seconds": timeout_seconds,
                "network_mode": mode,
                "command_argv": list(command),
                "executor": executor_provenance(profile),
                "run_config_sha256": config_digest,
                "input_identities": [
                    parse_input_identity_mapping(value) for value in input_identities
                ],
                "admitted_environment_names": admitted_env_names,
                "stdout": stdout_attestation,
                "stderr": stderr_attestation,
                "network_evidence": network_attestation,
                "workspace_size_observation": workspace_size_observation,
                "counters": {
                    "semantic_owner_interventions": 0,
                    "mechanical_boundary_controls": capture.applied_control_count(
                        read_roots,
                        temporary_roots,
                        mode,
                    ),
                },
            }
            encoded = (
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
                + b"\n"
            )

            capture.publish_captured_file_at(
                staged_stdout,
                evidence_fd,
                "run-stdout.log",
            )
            capture.publish_captured_file_at(
                staged_stderr,
                evidence_fd,
                "run-stderr.log",
            )
            if relay_id:
                capture.publish_captured_file_at(
                    staged_network,
                    evidence_fd,
                    "run-network.jsonl",
                )
            capture.publish_bytes_at(
                encoded,
                evidence_fd,
                "run-result.json",
            )
            os.fsync(evidence_fd)
            capture.assert_visible_directory(
                evidence,
                evidence_identity,
                "evidence-root",
            )
            return exit_code, payload
    finally:
        if relay_id:
            backend.safe_remove_container(relay_id)
        if internal_id:
            backend.safe_remove_network(internal_id)
        if external_id:
            backend.safe_remove_network(external_id)
        os.close(evidence_fd)


def command_validate_profile(args: argparse.Namespace) -> int:
    try:
        profile = load_profile(Path(cast(str, args.profile)))
        reasons = validate_profile_data(profile, for_run=False)
    except RunnerError as exc:
        reasons = [str(exc)]
    emit(
        {
            "schema": VALIDATION_SCHEMA,
            "status": "VALID" if not reasons else "INVALID",
            "reasons": reasons,
        }
    )
    return 0 if not reasons else 2


def command_probe(args: argparse.Namespace) -> int:
    image = os.environ.get("GNOSTOA_EXPERIMENT_RUNNER_IMAGE")
    result = backend.probe_backend(cast(str, args.backend), image=image)
    emit(
        {
            "schema": PROBE_SCHEMA,
            "status": result.status,
            "backend": result.backend,
            "reasons": result.reasons,
        }
    )
    return 0


def command_smoke(args: argparse.Namespace) -> int:
    image = os.environ.get("GNOSTOA_EXPERIMENT_RUNNER_IMAGE")
    relay_image = os.environ.get("GNOSTOA_EXPERIMENT_RUNNER_RELAY_IMAGE") or image
    network = cast(str, args.network)
    requested_backend = cast(str, args.backend)
    if network != "restricted":
        emit(smoke.blocked_smoke(["only-restricted-smoke-is-qualified"]))
        return 0
    if image is None or relay_image is None:
        emit(smoke.blocked_smoke(["oci-image-not-bound"]))
        return 0
    if requested_backend not in {"auto", "oci"}:
        emit(smoke.blocked_smoke(["bwrap-backend-not-qualified"]))
        return 0
    emit(smoke.run_smoke_oci(image, relay_image))
    return 0


def command_attest(args: argparse.Namespace) -> int:
    try:
        payload = capture.attest_payload(
            Path(cast(str, args.artifact)),
            cast(str, args.producer_id),
            cast(str, args.producer_version),
            cast(str, args.config_sha256),
            cast(list[str], args.input),
        )
    except (OSError, RunnerError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    emit(payload)
    return 0


def command_check_size(args: argparse.Namespace) -> int:
    try:
        observed, method = capture.measured_path_size(Path(cast(str, args.path)))
    except (OSError, RunnerError) as exc:
        emit({"schema": SIZE_SCHEMA, "status": "ERROR", "reasons": [str(exc)]})
        return 2
    maximum = cast(int, args.max_bytes)
    oversize = observed > maximum
    emit(
        {
            "schema": SIZE_SCHEMA,
            "status": "OVERSIZE" if oversize else "WITHIN_LIMIT",
            "bytes": observed,
            "max_bytes": maximum,
            "measurement": method,
        }
    )
    return 2 if oversize else 0


def command_run(args: argparse.Namespace) -> int:
    command = cast(list[str], args.command)
    if command and command[0] == "--":
        command = command[1:]
    requested_backend = cast(str, args.backend)
    try:
        exit_code, payload = run_profile_command(
            Path(cast(str, args.profile)),
            requested_backend,
            command,
        )
    except (OSError, RunnerError, subprocess.TimeoutExpired) as exc:
        emit(
            {
                "schema": RUN_SCHEMA,
                "status": "BLOCKED",
                "backend": None,
                "backend_requested": requested_backend,
                "backend_resolved": None,
                "reasons": [f"{type(exc).__name__}:{exc}"],
            }
        )
        return 2
    emit(payload)
    return exit_code


def command_relay(args: argparse.Namespace) -> int:
    return relay.relay_server(
        cast(str, args.listen),
        cast(int, args.port),
        cast(list[str], args.allow),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="experiment_runner.py")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    validate = subparsers.add_parser("validate-profile")
    validate.add_argument("--profile", required=True)
    validate.set_defaults(handler=command_validate_profile)

    probe = subparsers.add_parser("probe")
    probe.add_argument("--backend", choices=("auto", "oci", "bwrap"), default="auto")
    probe.set_defaults(handler=command_probe)

    smoke_parser = subparsers.add_parser("smoke")
    smoke_parser.add_argument(
        "--backend", choices=("auto", "oci", "bwrap"), default="auto"
    )
    smoke_parser.add_argument(
        "--network", choices=("none", "restricted"), default="restricted"
    )
    smoke_parser.set_defaults(handler=command_smoke)

    attest = subparsers.add_parser("attest")
    attest.add_argument("--artifact", required=True)
    attest.add_argument("--producer-id", required=True)
    attest.add_argument("--producer-version", required=True)
    attest.add_argument("--config-sha256", required=True)
    attest.add_argument("--input", action="append", default=[])
    attest.set_defaults(handler=command_attest)

    size = subparsers.add_parser("check-size")
    size.add_argument("--path", required=True)
    size.add_argument("--max-bytes", required=True, type=int)
    size.set_defaults(handler=command_check_size)

    run = subparsers.add_parser("run")
    run.add_argument("--profile", required=True)
    run.add_argument("--backend", choices=("auto", "oci", "bwrap"), default="auto")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(handler=command_run)

    relay_parser = subparsers.add_parser("_relay")
    relay_parser.add_argument("--listen", default="0.0.0.0")
    relay_parser.add_argument("--port", type=int, default=8080)
    relay_parser.add_argument("--allow", action="append", default=[])
    relay_parser.set_defaults(handler=command_relay)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = cast(Handler, args.handler)
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())