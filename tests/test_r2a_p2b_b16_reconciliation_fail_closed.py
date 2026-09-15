from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/publish-r2a-p2b-b16-oci.yml"


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
        for forbidden in ("docker pull", "docker push", "--push-by-digest"):
            self.assertNotIn(forbidden, reconciliation_run)

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
            "if [ \"${cleanup_status}\" -ne 0 ]; then",
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


if __name__ == "__main__":
    unittest.main()
