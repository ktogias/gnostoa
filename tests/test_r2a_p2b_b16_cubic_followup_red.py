from __future__ import annotations

import unittest
from pathlib import Path

import yaml
from test_r2a_p2b_b16_publication import (
    _has_direct_top_level_shell_sequence,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW_PATH = ROOT / ".github/workflows/publish-r2a-p2b-b16-oci.yml"
R2A_WORKFLOW_PATH = ROOT / ".github/workflows/r2a-protected-current-advisory.yml"


def _load_workflow(path: Path) -> dict[str, object]:
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(workflow, dict):
        raise AssertionError(f"workflow {path} must be a mapping")
    return workflow


def _named_step(steps: list[object], name: str) -> dict[str, object]:
    matches = [
        step for step in steps if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one workflow step named {name!r}")
    return matches[0]


def _job_steps(workflow: dict[str, object], job_name: str) -> list[object]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise AssertionError("workflow jobs must be a mapping")
    job = jobs.get(job_name)
    if not isinstance(job, dict):
        raise AssertionError(f"workflow job {job_name!r} must be a mapping")
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise AssertionError(f"workflow job {job_name!r} steps must be a list")
    return steps


def _bash_run(step: dict[str, object]) -> str:
    run = step.get("run")
    if step.get("shell") != "bash" or not isinstance(run, str):
        raise AssertionError("expected a bash run step")
    return run


class R2AP2bB16CubicFollowupTests(unittest.TestCase):
    def test_dedicated_r2a_executes_both_contracts_as_top_level_commands(self) -> None:
        workflow = _load_workflow(R2A_WORKFLOW_PATH)
        native_step = _named_step(
            _job_steps(workflow, "dormant-current-advisory-consumer"),
            "Run dormant consumer contract tests via native orchestration fallback",
        )
        sequence = (
            "PYTHONPATH=. python tests/test_r2a_p2b_b16_publication.py",
            "PYTHONPATH=. python tests/test_r2a_p2b_b16_reconciliation_fail_closed.py",
        )
        run = native_step.get("run")
        self.assertIsInstance(run, str)
        assert isinstance(run, str)
        self.assertTrue(
            _has_direct_top_level_shell_sequence(run, sequence),
            "both B1.6 contracts must execute directly at top level",
        )

        inert_variants = (
            "\n".join(f"# {command}" for command in sequence),
            "\n".join(("if false; then", *sequence, "fi")),
            "\n".join(("cat <<'EOF'", *sequence, "EOF")),
        )
        for script in inert_variants:
            with self.subTest(script=script):
                self.assertFalse(
                    _has_direct_top_level_shell_sequence(script, sequence),
                    "commented, heredoc-contained, or unreachable commands are not execution coverage",
                )

    def test_authorization_uses_meaningful_landing_binding_without_tautological_guards(
        self,
    ) -> None:
        workflow = _load_workflow(PUBLISH_WORKFLOW_PATH)
        authorize_steps = _job_steps(workflow, "authorize")
        boundary_run = _bash_run(
            _named_step(
                authorize_steps,
                "Refuse any context outside the admitted one-shot boundary",
            )
        )
        provider_binding_run = _bash_run(
            _named_step(authorize_steps, "Bind the pushed commit to merged PR 257")
        )

        for required in (
            "merge_commit_sha",
            "expected_merge_sha",
            "GITHUB_SHA",
            "AUTHORIZED_BEFORE_COMMIT",
            "AUTHORIZED_PR_HEAD_REF",
        ):
            self.assertIn(
                required,
                provider_binding_run,
                "the merged-PR binding must remain the exact landing-commit authority",
            )

        tautological_guards = (
            'test "${EVENT_AFTER}" = "${GITHUB_SHA}"',
            'test "${GITHUB_WORKFLOW_SHA}" = "${GITHUB_SHA}"',
        )
        present = [guard for guard in tautological_guards if guard in boundary_run]
        self.assertEqual(
            [],
            present,
            "push-derived SHA equalities must not masquerade as independent transition guards",
        )


if __name__ == "__main__":
    unittest.main()
