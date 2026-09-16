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
FOLLOWUP_TEST_RELATIVE_PATH = "tests/test_r2a_p2b_b16_cubic_followup_red.py"
R2A_COMPATIBILITY_JOB_KEY = "dormant-current-advisory-consumer"
R2A_ACTIVE_DISPLAY_NAME = "protected-current-advisory-consumer"
R2A_ACTIVE_CONTRACT_STEP = "Run protected current-advisory consumer contract tests via native orchestration fallback"


def _load_workflow(path: Path) -> dict[str, object]:
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if not isinstance(workflow, dict):
        raise AssertionError(f"workflow {path} must be a mapping")
    return workflow


def _job(workflow: dict[str, object], job_name: str) -> dict[str, object]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise AssertionError("workflow jobs must be a mapping")
    job = jobs.get(job_name)
    if not isinstance(job, dict):
        raise AssertionError(f"workflow job {job_name!r} must be a mapping")
    return job


def _named_step(steps: list[object], name: str) -> dict[str, object]:
    matches = [
        step for step in steps if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one workflow step named {name!r}")
    return matches[0]


def _job_steps(workflow: dict[str, object], job_name: str) -> list[object]:
    job = _job(workflow, job_name)
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise AssertionError(f"workflow job {job_name!r} steps must be a list")
    return steps


def _bash_run(step: dict[str, object]) -> str:
    run = step.get("run")
    if step.get("shell") != "bash" or not isinstance(run, str):
        raise AssertionError("expected a bash run step")
    return run


def _run(step: dict[str, object]) -> str:
    run = step.get("run")
    if not isinstance(run, str):
        raise AssertionError("expected a run step")
    return run


def _continued_command(script: str, command_head: str) -> tuple[str, ...]:
    lines = script.splitlines()
    starts = [index for index, line in enumerate(lines) if line.strip() == command_head]
    if len(starts) != 1:
        raise AssertionError(f"expected exactly one command headed by {command_head!r}")

    index = starts[0]
    command = [lines[index].strip()]
    while command[-1].endswith("\\"):
        index += 1
        if index >= len(lines):
            raise AssertionError(f"unterminated continued command {command_head!r}")
        command.append(lines[index].strip())
    return tuple(command)


class R2AP2bB16CubicFollowupTests(unittest.TestCase):
    def test_dedicated_r2a_executes_both_contracts_as_top_level_commands(self) -> None:
        workflow = _load_workflow(R2A_WORKFLOW_PATH)
        job = _job(workflow, R2A_COMPATIBILITY_JOB_KEY)
        self.assertEqual(R2A_ACTIVE_DISPLAY_NAME, job.get("name"))
        native_step = _named_step(
            _job_steps(workflow, R2A_COMPATIBILITY_JOB_KEY),
            R2A_ACTIVE_CONTRACT_STEP,
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

    def test_dedicated_r2a_protects_this_followup_contract(self) -> None:
        workflow = _load_workflow(R2A_WORKFLOW_PATH)
        on = workflow.get("on")
        self.assertIsInstance(on, dict)
        assert isinstance(on, dict)
        pull_request = on.get("pull_request")
        self.assertIsInstance(pull_request, dict)
        assert isinstance(pull_request, dict)
        paths = pull_request.get("paths")
        self.assertIsInstance(paths, list)
        assert isinstance(paths, list)
        self.assertIn(
            FOLLOWUP_TEST_RELATIVE_PATH,
            paths,
            "the follow-up regression guard must itself trigger dedicated R2A verification",
        )

        job = _job(workflow, R2A_COMPATIBILITY_JOB_KEY)
        self.assertEqual(R2A_ACTIVE_DISPLAY_NAME, job.get("name"))
        steps = _job_steps(workflow, R2A_COMPATIBILITY_JOB_KEY)
        static_run = _run(
            _named_step(steps, "Verify protected consumer trust-domain sources")
        )
        ruff_commands = (
            (
                "format",
                _continued_command(static_run, "python -m ruff format --check \\"),
            ),
            ("check", _continued_command(static_run, "python -m ruff check \\")),
        )
        for scope, command in ruff_commands:
            with self.subTest(scope=scope):
                arguments = {line.removesuffix("\\").strip() for line in command[1:]}
                self.assertIn(
                    FOLLOWUP_TEST_RELATIVE_PATH,
                    arguments,
                    f"the follow-up regression guard must remain in Ruff {scope} scope",
                )

        native_run = _run(_named_step(steps, R2A_ACTIVE_CONTRACT_STEP))
        command = f"PYTHONPATH=. python {FOLLOWUP_TEST_RELATIVE_PATH}"
        self.assertTrue(
            _has_direct_top_level_shell_sequence(native_run, (command,)),
            "the follow-up regression guard must execute directly in dedicated R2A verification",
        )

    def test_local_verification_image_cleanup_is_fail_closed(self) -> None:
        workflow = _load_workflow(PUBLISH_WORKFLOW_PATH)
        local_run = _bash_run(
            _named_step(
                _job_steps(workflow, "publish"),
                "Build and verify exact B1.6 consumer locally before any registry effect",
            )
        )

        cleanup_trap = "trap cleanup_local_image EXIT"
        bounded_build = "timeout --kill-after=5s 900s ./ci/build-runtime"
        for required in (
            "cleanup_local_image()",
            "local prior_status=$?",
            "trap - EXIT",
            bounded_build,
        ):
            self.assertIn(required, local_run)

        self.assertNotIn(
            "trap 'docker image rm \"${local_image}\" >/dev/null 2>&1 || true' EXIT",
            local_run,
            "local verification cleanup must not suppress removal failure",
        )
        self.assertLess(
            local_run.index(cleanup_trap),
            local_run.index(bounded_build),
            "fail-closed cleanup must be armed before the local image can be created",
        )
        self.assertEqual(
            "cleanup_local_image",
            local_run.rstrip().splitlines()[-1],
            "the successful local path must use the same fail-closed cleanup routine",
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

        self.assertIn(
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"',
            boundary_run,
            "the push event must remain bound to the exact protected-main predecessor",
        )
        for required in (
            "merge_commit_sha",
            "expected_merge_sha",
            "GITHUB_SHA",
            "AUTHORIZED_PR_HEAD_REF",
        ):
            self.assertIn(
                required,
                provider_binding_run,
                "the merged-PR binding must remain the exact landing-commit authority",
            )

        for forbidden in (
            "expected_base_sha",
            'pr.get("base", {}).get("sha")',
        ):
            self.assertNotIn(
                forbidden,
                provider_binding_run,
                "PR base.sha is not a documented merge-predecessor authority and must not reject an otherwise exact authorized landing",
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
