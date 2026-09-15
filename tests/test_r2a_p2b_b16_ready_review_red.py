from __future__ import annotations

import runpy
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-r2a-p2b-b16-oci.yml"
FOCUSED_TEST_PATH = ROOT / "tests" / "test_r2a_p2b_b16_publication.py"
RATIONALE = (
    "# Restricted native orchestration: the runner owns the Docker service; "
    "the candidate receives no daemon or socket authority."
)
B15 = 'GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" python b16-source/ci/review_b15_runtime_smoke.py'
B16 = (
    'PYTHONPATH=b16-source GNOSTOA_R2A_CANDIDATE_IMAGE="${digest_ref}" '
    "python b16-source/ci/review_b16_entrypoint_smoke.py"
)


def _workflow() -> dict[str, object]:
    parsed = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(parsed, dict):
        raise AssertionError("publication workflow must be a mapping")
    return parsed


def _named_run(steps: list[object], name: str) -> str:
    matches = [
        step for step in steps if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("run"), str):
        raise AssertionError(f"expected one run step named {name!r}")
    return matches[0]["run"]


class R2AP2bB16ReadyReviewRedTests(unittest.TestCase):
    def test_authorization_binds_exact_pr_landing_identity(self) -> None:
        workflow = _workflow()
        env = workflow["env"]
        jobs = workflow["jobs"]
        self.assertIsInstance(env, dict)
        self.assertIsInstance(jobs, dict)
        assert isinstance(env, dict)
        assert isinstance(jobs, dict)
        authorize = jobs["authorize"]
        self.assertIsInstance(authorize, dict)
        assert isinstance(authorize, dict)

        self.assertEqual("257", env["AUTHORIZED_PR_NUMBER"])
        self.assertEqual({"pull-requests": "read"}, authorize["permissions"])
        steps = authorize["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        run_text = "\n".join(
            step["run"]
            for step in steps
            if isinstance(step, dict) and isinstance(step.get("run"), str)
        )
        for required in (
            'test "${EVENT_AFTER}" = "${GITHUB_SHA}"',
            'test "${GITHUB_WORKFLOW_SHA}" = "${GITHUB_SHA}"',
            "pulls/${AUTHORIZED_PR_NUMBER}",
            "merge_commit_sha",
            "AUTHORIZED_BEFORE_COMMIT",
            "timeout --kill-after=5s",
        ):
            self.assertIn(required, run_text)

    def test_registry_readbacks_are_timeout_and_output_bounded(self) -> None:
        workflow = _workflow()
        jobs = workflow["jobs"]
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        publish = jobs["publish"]
        self.assertIsInstance(publish, dict)
        assert isinstance(publish, dict)
        steps = publish["steps"]
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)

        for step_name in (
            "Publish exact B1.6 consumer without a remote tag and read back digest",
            "Verify attestation and anonymous digest acquisition",
        ):
            with self.subTest(step=step_name):
                run = _named_run(steps, step_name)
                self.assertIn("bounded_registry_capture()", run)
                self.assertIn("timeout --kill-after=5s", run)
                self.assertIn("head -c 4097", run)
                self.assertIn('docker pull --quiet "${digest_ref}"', run)
                self.assertIn("docker buildx imagetools inspect", run)

    def test_shell_structure_helper_rejects_inert_smoke_sequences(self) -> None:
        namespace = runpy.run_path(str(FOCUSED_TEST_PATH))
        helper = namespace["_has_direct_top_level_shell_sequence"]
        sequence = (RATIONALE, B15, B16)

        heredoc_inert = "\n".join(
            (
                "set -euo pipefail",
                "cat <<EOF",
                "  EOF",
                *sequence,
                "EOF",
            )
        )
        multiline_if_inert = "\n".join(
            (
                "set -euo pipefail",
                "if false",
                "then",
                *sequence,
                "fi",
            )
        )
        self.assertFalse(helper(heredoc_inert, sequence))
        self.assertFalse(helper(multiline_if_inert, sequence))

    def test_digest_contract_is_named_step_scoped_and_orders_anonymous_identity(
        self,
    ) -> None:
        focused = FOCUSED_TEST_PATH.read_text(encoding="utf-8")
        digest_test = focused.split(
            "    def test_digest_readback_is_uniform_and_anonymous_reacquisition_is_not_cached(",
            1,
        )[1].split(
            "\n    def test_b16_decision_triggers_dedicated_r2a_verification", 1
        )[0]
        self.assertGreaterEqual(digest_test.count("_named_bash_run_step("), 2)
        self.assertIn("anonymous_block.index(anonymous_pull)", digest_test)
        self.assertIn("anonymous_block.index(digest_uid_check)", digest_test)
        self.assertIn("anonymous_block.index(digest_gid_check)", digest_test)


if __name__ == "__main__":
    unittest.main()
