from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/publish-r2a-p2b-b16-oci.yml"
R2A_WORKFLOW_PATH = ROOT / ".github/workflows/r2a-protected-current-advisory.yml"


def _publish_steps() -> list[object]:
    workflow = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("B1.6 publication workflow must be a mapping")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise AssertionError("B1.6 publication jobs must be a mapping")
    publish = jobs.get("publish")
    if not isinstance(publish, dict):
        raise AssertionError("B1.6 publication job must be a mapping")
    steps = publish.get("steps")
    if not isinstance(steps, list):
        raise AssertionError("B1.6 publication steps must be a list")
    return steps


def _named_step(steps: list[object], name: str) -> dict[str, object]:
    matches = [
        step for step in steps if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one workflow step named {name!r}")
    return matches[0]


def _run(step: dict[str, object]) -> str:
    run = step.get("run")
    if step.get("shell") != "bash" or not isinstance(run, str):
        raise AssertionError("expected a bash run step")
    return run


class R2AP2bB16ReconciliationFailClosedTests(unittest.TestCase):
    def test_terminal_publish_job_does_not_export_unused_job_outputs(self) -> None:
        workflow = yaml.load(
            WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)
        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs.get("publish")
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)

        self.assertNotIn(
            "outputs",
            publish,
            "terminal publish job must not expose unused job-level outputs; "
            "the digest step outputs remain internal to this job",
        )

    def test_possible_push_reconciles_even_without_publish_step_output(self) -> None:
        steps = _publish_steps()
        publish = _named_step(
            steps,
            "Publish exact B1.6 consumer without a remote tag and read back digest",
        )
        reconciliation = _named_step(
            steps, "Reconcile and clean post-publication state"
        )

        publish_run = _run(publish)
        reconciliation_run = _run(reconciliation)
        metadata_path = "${RUNNER_TEMP}/r2a-p2b-b16-build-metadata.json"

        self.assertIn(f'metadata_file="{metadata_path}"', publish_run)
        self.assertEqual(
            "${{ always() && steps.publish.outcome != 'skipped' }}",
            reconciliation.get("if"),
            "reconciliation must not depend on a publish output that can be lost "
            "after a successful registry effect",
        )
        self.assertEqual(
            {
                "GH_TOKEN": "${{ github.token }}",
                "REGISTRY_DIGEST": "${{ steps.publish.outputs.registry_digest }}",
                "METADATA_FILE": "${{ runner.temp }}/r2a-p2b-b16-build-metadata.json",
                "BUILD_DATE": "${{ steps.source.outputs.build_date }}",
                "PUBLIC_DIGEST": "${{ steps.local.outputs.public_digest }}",
            },
            reconciliation.get("env"),
        )
        for required in (
            'registry_digest="${REGISTRY_DIGEST}"',
            'if [ -z "${registry_digest}" ]; then',
            'python - "${METADATA_FILE}"',
            'metadata["containerimage.digest"]',
            'digest_ref="${IMAGE_NAME}@${registry_digest}"',
        ):
            self.assertIn(required, reconciliation_run)
        self.assertLess(
            reconciliation_run.index("trap cleanup_post_write EXIT"),
            reconciliation_run.index('if [ -z "${registry_digest}" ]; then'),
            "cleanup must already be armed while recovering an ambiguous push identity",
        )
        for forbidden in ("docker push", "--push-by-digest"):
            self.assertNotIn(forbidden, reconciliation_run)

    def test_local_pre_effect_build_is_bounded(self) -> None:
        steps = _publish_steps()
        local = _named_step(
            steps,
            "Build and verify exact B1.6 consumer locally before any registry effect",
        )
        local_run = _run(local)

        bounded_build = "timeout --kill-after=5s 900s ./ci/build-runtime"
        self.assertIn(
            bounded_build,
            local_run,
            "the pre-effect BuildKit cut must have a finite execution bound",
        )
        self.assertLess(local_run.index(bounded_build), local_run.index("--tag"))

    def test_digest_only_publication_registry_write_is_bounded(self) -> None:
        steps = _publish_steps()
        publish = _named_step(
            steps,
            "Publish exact B1.6 consumer without a remote tag and read back digest",
        )
        publish_run = _run(publish)

        bounded_write = "timeout --kill-after=5s 900s ./ci/build-runtime"
        self.assertIn(
            bounded_write,
            publish_run,
            "the one registry write must terminate so fail-closed reconciliation can run",
        )
        self.assertLess(
            publish_run.index(bounded_write),
            publish_run.index("--push-by-digest"),
        )

    def test_buildx_builder_setup_and_cleanup_are_bounded(self) -> None:
        steps = _publish_steps()
        publish = _named_step(
            steps,
            "Publish exact B1.6 consumer without a remote tag and read back digest",
        )
        publish_run = _run(publish)

        bounded_create = "timeout --kill-after=5s 120s docker buildx create"
        cleanup_function = "cleanup_builder()"
        cleanup_trap = "trap cleanup_builder EXIT"
        bounded_cleanup = (
            'if ! timeout --kill-after=5s 30s docker buildx rm "${builder}" '
            ">/dev/null 2>&1; then"
        )
        for required in (
            cleanup_function,
            "local prior_status=$?",
            "trap - EXIT",
            bounded_cleanup,
            'echo "BuildKit builder cleanup failed" >&2',
            'exit "${prior_status}"',
            cleanup_trap,
            bounded_create,
        ):
            self.assertIn(
                required,
                publish_run,
                "BuildKit builder cleanup must be bounded and fail closed",
            )
        self.assertNotIn(
            'docker buildx rm "${builder}" >/dev/null 2>&1 || true', publish_run
        )
        self.assertLess(
            publish_run.index(cleanup_trap),
            publish_run.index(bounded_create),
            "builder cleanup must be armed before bounded builder creation",
        )

    def test_failed_authentication_is_cleaned_before_publish_can_be_skipped(self) -> None:
        steps = _publish_steps()
        authenticate = _named_step(
            steps, "Authenticate to GHCR for the single digest-only effect"
        )
        auth_cleanup = _named_step(
            steps, "Clean GHCR authentication state after failed login"
        )
        publish = _named_step(
            steps,
            "Publish exact B1.6 consumer without a remote tag and read back digest",
        )

        self.assertEqual(
            "authenticate",
            authenticate.get("id"),
            "authentication outcome must be addressable by the cleanup guard",
        )
        self.assertEqual(
            "${{ always() && steps.authenticate.outcome == 'failure' }}",
            auth_cleanup.get("if"),
            "an attempted but failed authentication must still reach credential cleanup",
        )
        self.assertEqual(
            "1",
            auth_cleanup.get("timeout-minutes"),
            "authentication cleanup must itself have a finite step bound",
        )
        self.assertIn(
            "timeout --kill-after=5s 30s docker logout ghcr.io",
            _run(auth_cleanup),
            "failed authentication cleanup must bound credential removal",
        )
        self.assertLess(steps.index(authenticate), steps.index(auth_cleanup))
        self.assertLess(steps.index(auth_cleanup), steps.index(publish))

    def test_post_publish_attestation_verification_is_bounded(self) -> None:
        steps = _publish_steps()
        verify = _named_step(
            steps, "Verify attestation and anonymous digest acquisition"
        )
        verify_run = _run(verify)

        bounded_attestation = "bounded_registry_capture 30 gh attestation verify"
        self.assertIn(
            bounded_attestation,
            verify_run,
            "post-publication attestation verification must terminate so reconciliation can run",
        )

    def test_runtime_verification_steps_have_finite_bounds(self) -> None:
        steps = _publish_steps()
        bounded_step_names = (
            "Build and verify exact B1.6 consumer locally before any registry effect",
            "Publish exact B1.6 consumer without a remote tag and read back digest",
            "Verify attestation and anonymous digest acquisition",
            "Reconcile and clean post-publication state",
        )
        invalid_bounds: list[str] = []
        for name in bounded_step_names:
            timeout = _named_step(steps, name).get("timeout-minutes")
            if (
                not isinstance(timeout, str)
                or not timeout.isdigit()
                or not 1 <= int(timeout) <= 30
            ):
                invalid_bounds.append(name)

        self.assertEqual(
            [],
            invalid_bounds,
            "every verification cut that can run containers or smoke harnesses must "
            "have a finite step timeout so hangs cannot bypass fail-closed progression",
        )
        reconciliation = _named_step(
            steps, "Reconcile and clean post-publication state"
        )
        self.assertEqual(
            "${{ always() && steps.publish.outcome != 'skipped' }}",
            reconciliation.get("if"),
            "a timed-out post-write cut must still reach reconciliation",
        )

    def test_attestation_write_and_registry_credentials_are_bounded(self) -> None:
        steps = _publish_steps()
        authenticate = _named_step(
            steps, "Authenticate to GHCR for the single digest-only effect"
        )
        attest = _named_step(steps, "Attest the digest-only registry manifest")
        verify = _named_step(
            steps, "Verify attestation and anonymous digest acquisition"
        )
        reconciliation = _named_step(
            steps, "Reconcile and clean post-publication state"
        )

        self.assertEqual(
            "1",
            authenticate.get("timeout-minutes"),
            "registry authentication must have a finite step bound",
        )
        self.assertEqual(
            "5",
            attest.get("timeout-minutes"),
            "the attestation registry write must time out without cancelling later reconciliation",
        )
        self.assertEqual(
            "${{ always() && steps.publish.outcome != 'skipped' }}",
            reconciliation.get("if"),
        )

        bounded_logout = "timeout --kill-after=5s 30s docker logout ghcr.io"
        self.assertIn(
            bounded_logout,
            _run(verify),
            "post-write credential cleanup must terminate before anonymous reacquisition",
        )
        self.assertGreaterEqual(
            _run(reconciliation).count(bounded_logout),
            2,
            "reconciliation must bound both immediate and EXIT-trap credential cleanup",
        )

    def test_dedicated_r2a_workflow_executes_both_b16_contracts(self) -> None:
        workflow = yaml.load(
            R2A_WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
        )
        if not isinstance(workflow, dict):
            raise AssertionError("dedicated R2A workflow must be a mapping")
        jobs = workflow.get("jobs")
        if not isinstance(jobs, dict):
            raise AssertionError("dedicated R2A jobs must be a mapping")
        job = jobs.get("dormant-current-advisory-consumer")
        if not isinstance(job, dict):
            raise AssertionError("dedicated R2A consumer job must be a mapping")
        steps = job.get("steps")
        if not isinstance(steps, list):
            raise AssertionError("dedicated R2A steps must be a list")
        native_contracts = _named_step(
            steps,
            "Run dormant consumer contract tests via native orchestration fallback",
        )
        run = native_contracts.get("run")
        self.assertIsInstance(run, str)
        assert isinstance(run, str)
        for command in (
            "PYTHONPATH=. python tests/test_r2a_p2b_b16_publication.py",
            "PYTHONPATH=. python tests/test_r2a_p2b_b16_reconciliation_fail_closed.py",
        ):
            self.assertIn(
                command,
                run,
                "path-filter coverage must be backed by native execution of each B1.6 contract",
            )

    def test_post_write_cleanup_failure_cannot_be_reported_as_success(self) -> None:
        steps = _publish_steps()
        reconciliation = _named_step(
            steps, "Reconcile and clean post-publication state"
        )
        reconciliation_run = _run(reconciliation)

        for required in (
            "cleanup_post_write()",
            "local prior_status=$?",
            "local cleanup_status=0",
            "trap - EXIT",
            "docker logout ghcr.io",
            'docker image inspect "${digest_ref}"',
            'docker image rm "${digest_ref}"',
            (
                'if [ -n "${digest_ref}" ] && docker image inspect '
                '"${digest_ref}" >/dev/null 2>&1; then'
            ),
            'echo "post-write digest image remained cached" >&2',
            'if [ "${cleanup_status}" -ne 0 ]; then',
            'exit "${cleanup_status}"',
            'exit "${prior_status}"',
        ):
            self.assertIn(required, reconciliation_run)
        self.assertNotIn(
            "docker logout ghcr.io >/dev/null 2>&1 || true", reconciliation_run
        )
        self.assertNotIn(
            'docker image rm "${digest_ref}" >/dev/null 2>&1 || true',
            reconciliation_run,
        )

    def test_reconciliation_reproves_exact_digest_runtime_identity(self) -> None:
        steps = _publish_steps()
        reconciliation = _named_step(
            steps, "Reconcile and clean post-publication state"
        )
        reconciliation_run = _run(reconciliation)

        for required in (
            'reconcile_config="$(mktemp -d)"',
            'test "$(git -C b16-source rev-parse HEAD)" = "${SOURCE_COMMIT}"',
            (
                "test \"$(git -C b16-source rev-parse 'HEAD^{tree}')\" "
                '= "${SOURCE_TREE}"'
            ),
            '[[ "${registry_digest}" =~ ^sha256:[0-9a-f]{64}$ ]]',
            'test "${reconciled_manifest}" = "${registry_digest}"',
            'docker image rm "${digest_ref}"',
            'env DOCKER_CONFIG="${reconcile_config}"',
            'docker pull --quiet "${digest_ref}"',
            "bounded_registry_capture 30 docker buildx imagetools inspect",
            "bounded_registry_capture 30 gh attestation verify",
            (
                "docker image inspect --format "
                "'{{.Os}}/{{.Architecture}}' \"${digest_ref}\""
            ),
            ("docker image inspect --format '{{.Config.User}}' \"${digest_ref}\""),
            "org.opencontainers.image.version",
            "org.opencontainers.image.revision",
            "org.opencontainers.image.created",
            'docker run --rm --entrypoint id "${digest_ref}" -u',
            'docker run --rm --entrypoint id "${digest_ref}" -g',
            "surface-digest --root /opt/gnostoa",
            'test "${actual}" = "${PUBLIC_DIGEST}"',
            'docker run --rm "${digest_ref}" self-check --skip-tests',
            'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}"',
            "python b16-source/ci/review_b15_runtime_smoke.py",
            "python b16-source/ci/review_b16_entrypoint_smoke.py",
        ):
            self.assertIn(required, reconciliation_run)
        self.assertNotIn("docker push", reconciliation_run)
        self.assertNotIn("--push-by-digest", reconciliation_run)


if __name__ == "__main__":
    unittest.main()
