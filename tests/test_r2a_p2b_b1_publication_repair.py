from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-r2a-p2b-b1-oci.yml"
DECISION_PATH = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md"
)
FAILED_PUBLISHER_COMMIT = "8d1ac1812509a2f6beb220b4989ec9b472ff441b"
FAILED_RUN_ID = "34842626132"
FAILURE_RECORD_COMMENT = "5663773822"


def _workflow() -> dict[str, object]:
    loaded = yaml.load(
        WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(loaded, dict):
        raise AssertionError("B1 publication workflow must be a YAML mapping")
    return loaded


def _step(steps: list[object], name: str) -> dict[str, object]:
    matches = [
        step for step in steps if isinstance(step, dict) and step.get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one workflow step named {name!r}")
    return matches[0]


class R2AP2bB1PublicationRepairTests(unittest.TestCase):
    def test_prewrite_failure_repair_is_exact_and_container_first(self) -> None:
        workflow = _workflow()
        env = workflow["env"]
        jobs = workflow["jobs"]
        self.assertIsInstance(env, dict)
        self.assertIsInstance(jobs, dict)
        assert isinstance(env, dict)
        assert isinstance(jobs, dict)

        self.assertEqual(FAILED_PUBLISHER_COMMIT, env["AUTHORIZED_BEFORE_COMMIT"])

        authorize = jobs["authorize"]
        publish = jobs["publish"]
        self.assertIsInstance(authorize, dict)
        self.assertIsInstance(publish, dict)
        assert isinstance(authorize, dict)
        assert isinstance(publish, dict)

        authorize_steps = authorize["steps"]
        publish_steps = publish["steps"]
        self.assertIsInstance(authorize_steps, list)
        self.assertIsInstance(publish_steps, list)
        assert isinstance(authorize_steps, list)
        assert isinstance(publish_steps, list)

        gate = _step(
            authorize_steps,
            "Refuse any context outside the admitted one-shot boundary",
        )
        gate_run = gate["run"]
        self.assertIsInstance(gate_run, str)
        assert isinstance(gate_run, str)
        self.assertIn(
            'test "${EVENT_BEFORE}" = "${AUTHORIZED_BEFORE_COMMIT}"', gate_run
        )
        self.assertNotIn('test "${EVENT_BEFORE}" = "${SOURCE_COMMIT}"', gate_run)
        self.assertIn('test "${GITHUB_RUN_ATTEMPT}" = "1"', gate_run)

        source = _step(
            publish_steps,
            "Verify exact B1 source identity and derive bound source metadata",
        )
        source_run = source["run"]
        self.assertIsInstance(source_run, str)
        assert isinstance(source_run, str)
        self.assertNotIn("surface-digest", source_run)

        local = _step(
            publish_steps,
            "Build and verify exact B1 consumer locally before any registry effect",
        )
        self.assertEqual("local", local["id"])
        local_run = local["run"]
        self.assertIsInstance(local_run, str)
        assert isinstance(local_run, str)
        self.assertIn("surface-digest --root /opt/gnostoa", local_run)
        self.assertIn(
            'echo "public_digest=${public_digest}" >> "${GITHUB_OUTPUT}"', local_run
        )

        outputs = publish["outputs"]
        self.assertIsInstance(outputs, dict)
        assert isinstance(outputs, dict)
        self.assertEqual(
            "${{ steps.local.outputs.public_digest }}", outputs["public-digest"]
        )

        publish_effect = _step(
            publish_steps,
            "Publish exact B1 consumer without a remote tag and read back digest",
        )
        verify_effect = _step(
            publish_steps,
            "Verify attestation and anonymous digest acquisition",
        )
        for effect in (publish_effect, verify_effect):
            effect_env = effect["env"]
            self.assertIsInstance(effect_env, dict)
            assert isinstance(effect_env, dict)
            self.assertEqual(
                "${{ steps.local.outputs.public_digest }}",
                effect_env["PUBLIC_DIGEST"],
            )

    def test_prewrite_failure_and_repair_authority_are_recorded(self) -> None:
        decision = DECISION_PATH.read_text(encoding="utf-8")
        self.assertIn(FAILED_RUN_ID, decision)
        self.assertIn(FAILED_PUBLISHER_COMMIT, decision)
        self.assertIn(FAILURE_RECORD_COMMENT, decision)
        self.assertIn("before GHCR authentication", decision)
        self.assertIn("container", decision.lower())


if __name__ == "__main__":
    unittest.main()
