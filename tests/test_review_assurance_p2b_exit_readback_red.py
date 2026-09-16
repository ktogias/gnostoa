from __future__ import annotations

import copy
import importlib
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tools import review_outer
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
SMOKE_MODULE = "ci.review_outer_smoke"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "r2a-protected-current-advisory.yml"
AUTHORITY_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
INNER_AUTHORITY_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
DECISION_RELATIVE_PATH = "knowledge/decisions/0080-complete-r2a-p2b-rolling-trust-exit-by-negative-readback.md"
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
INDEX_PATH = ROOT / "knowledge" / "index.md"
GUARDRAILS_PATH = ROOT / "policy" / "guardrails.yaml"
FOCUSED_TEST_PATH = "tests/test_review_assurance_p2b_exit_readback_red.py"

PROMOTION_MAIN_REVISION = "21e4ada5e849b70d5349029f1fa3424fe9fa2fd0"  # pragma: allowlist secret -- public protected-main revision
P2B_SOURCE_REVISION = "2aa1ed3217c42819155b8ff36385b000720ba4f8"  # pragma: allowlist secret -- public source revision
P2B_SOURCE_TREE = "4cda4e4a704cb518f56201423e313d4dd9db5e24"  # pragma: allowlist secret -- public source tree
P2B_PUBLIC_SURFACE_DIGEST = "sha256:b69f11e1efe181f959a14310fed0a35d3533114d734de584790a85cba7bdb565"  # pragma: allowlist secret -- public surface digest
P2B_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281"  # pragma: allowlist secret -- public OCI digest
)
B16_SOURCE_REVISION = "f29499286bac9859364d45da0f6c59396518b749"  # pragma: allowlist secret -- historical public source revision
B16_SOURCE_TREE = "ff38abe5718ebc550054ea6af18a73d0aef8e514"  # pragma: allowlist secret -- historical public source tree
B16_PUBLIC_SURFACE_DIGEST = "sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57"  # pragma: allowlist secret -- historical public surface digest
B16_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867"  # pragma: allowlist secret -- historical public OCI digest
)
CANDIDATE_IMAGE = "gnostoa-r2a-candidate:untrusted"

EXPECTED_CONSUMER = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": P2B_SOURCE_REVISION,
    "source_tree": P2B_SOURCE_TREE,
    "public_surface_digest": P2B_PUBLIC_SURFACE_DIGEST,
    "runtime_image": P2B_OCI_IMAGE,
    "runtime_revision": P2B_SOURCE_REVISION,
    "supported_input_schema_versions": ["1.0"],
    "status": "accepted",
}


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


def _load_smoke() -> object:
    return importlib.import_module(SMOKE_MODULE)


def _stale_b16_authority() -> dict[str, object]:
    authority = copy.deepcopy(_load_json(AUTHORITY_PATH))
    stale = copy.deepcopy(EXPECTED_CONSUMER)
    stale.update(
        {
            "source_revision": B16_SOURCE_REVISION,
            "source_tree": B16_SOURCE_TREE,
            "public_surface_digest": B16_PUBLIC_SURFACE_DIGEST,
            "runtime_image": B16_OCI_IMAGE,
            "runtime_revision": B16_SOURCE_REVISION,
        }
    )
    authority["expected_consumer"] = stale
    authority["acquired_consumer"] = copy.deepcopy(stale)
    return authority


class ReviewAssuranceP2bExitReadbackRedTests(unittest.TestCase):
    def test_live_readback_accepts_only_exact_promoted_p2b(self) -> None:
        smoke = _load_smoke()
        assert_readback = getattr(smoke, "_assert_promoted_readback", None)
        self.assertTrue(
            callable(assert_readback),
            "P2B_EXIT_PROMOTED_READBACK_ASSERTION_UNAVAILABLE",
        )
        if not callable(assert_readback):
            return

        authority = _load_json(AUTHORITY_PATH)
        protected = ProtectedMainDocument(
            protected_main_revision=PROMOTION_MAIN_REVISION,
            document=authority,
        )
        self.assertEqual(
            EXPECTED_CONSUMER,
            assert_readback(protected, PROMOTION_MAIN_REVISION),
        )

        with self.assertRaisesRegex(RuntimeError, "protected main revision"):
            assert_readback(protected, "0" * 40)

        stale = ProtectedMainDocument(
            protected_main_revision=PROMOTION_MAIN_REVISION,
            document=_stale_b16_authority(),
        )
        with self.assertRaisesRegex(RuntimeError, "promoted OCI.P2b"):
            assert_readback(stale, PROMOTION_MAIN_REVISION)

    def test_candidate_local_b16_authority_is_ignored_by_live_acquisition(self) -> None:
        smoke = _load_smoke()
        acquire = getattr(smoke, "_acquire_under_candidate_poison", None)
        self.assertTrue(
            callable(acquire),
            "P2B_EXIT_CANDIDATE_AUTHORITY_NEGATIVE_READBACK_UNAVAILABLE",
        )
        if not callable(acquire):
            return

        protected = ProtectedMainDocument(
            protected_main_revision=PROMOTION_MAIN_REVISION,
            document=_load_json(AUTHORITY_PATH),
        )

        def observe_candidate_poison() -> ProtectedMainDocument:
            candidate_root = Path(os.environ["KNOWLEDGE_KIT_ROOT"])
            stale_path = (
                candidate_root / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
            )
            self.assertEqual(_stale_b16_authority(), _load_json(stale_path))
            self.assertEqual(
                CANDIDATE_IMAGE,
                os.environ["GNOSTOA_R2A_CANDIDATE_IMAGE"],
            )
            return protected

        with mock.patch.object(
            smoke.review_protected,
            "acquire_gnostoa_current_advisory_consumer",
            side_effect=observe_candidate_poison,
        ) as protected_acquire:
            observed, consumer = acquire(
                expected_protected_main=PROMOTION_MAIN_REVISION,
                candidate_image=CANDIDATE_IMAGE,
            )

        self.assertEqual(protected, observed)
        self.assertEqual(EXPECTED_CONSUMER, consumer)
        protected_acquire.assert_called_once_with()

    def test_selected_live_plan_rejects_candidate_and_stale_b16_images(self) -> None:
        smoke = _load_smoke()
        assert_plan = getattr(smoke, "_assert_promoted_outer_plan", None)
        self.assertTrue(
            callable(assert_plan),
            "P2B_EXIT_OUTER_PLAN_NEGATIVE_ASSERTION_UNAVAILABLE",
        )
        if not callable(assert_plan):
            return

        plan = review_outer._build_isolated_execution_plan(
            consumer=copy.deepcopy(EXPECTED_CONSUMER),
            input_dir=Path("/tmp/gnostoa-r2a-exit-input"),
            socket_volume="gnostoa-r2a-exit-socket",
            tmp_volume="gnostoa-r2a-exit-tmp",
            daemon_name="gnostoa-r2a-exit-daemon",
            outer_name="gnostoa-r2a-exit-outer",
        )
        receipt = assert_plan(plan, CANDIDATE_IMAGE)
        self.assertEqual(P2B_OCI_IMAGE, receipt["selected_runtime_image"])
        self.assertTrue(receipt["candidate_runtime_rejected"])
        self.assertTrue(receipt["stale_b1x_runtime_rejected"])

        for rejected_image in (CANDIDATE_IMAGE, B16_OCI_IMAGE):
            poisoned = copy.deepcopy(plan)
            outer = poisoned["outer"]
            self.assertIsInstance(outer, list)
            assert isinstance(outer, list)
            outer[outer.index(P2B_OCI_IMAGE)] = rejected_image
            with self.subTest(rejected_image=rejected_image):
                with self.assertRaisesRegex(RuntimeError, "exact promoted OCI.P2b"):
                    assert_plan(poisoned, CANDIDATE_IMAGE)

    def test_dedicated_workflow_executes_subsequent_candidate_readback(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow = yaml.load(workflow_text, Loader=yaml.BaseLoader)
        self.assertIsInstance(workflow, dict)
        assert isinstance(workflow, dict)

        for protected_path in (DECISION_RELATIVE_PATH, FOCUSED_TEST_PATH):
            self.assertIn(f'- "{protected_path}"', workflow_text)
        self.assertGreaterEqual(workflow_text.count(FOCUSED_TEST_PATH), 4)

        jobs = workflow.get("jobs")
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        job = jobs.get("protected-current-advisory-consumer")
        self.assertIsInstance(job, dict)
        assert isinstance(job, dict)
        steps = job.get("steps")
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        matches = [
            step
            for step in steps
            if isinstance(step, dict)
            and step.get("name")
            == "Exercise promoted OCI(P2b) and reject candidate/stale selectors"
        ]
        self.assertEqual(1, len(matches))
        step = matches[0]
        env = step.get("env")
        self.assertIsInstance(env, dict)
        assert isinstance(env, dict)
        self.assertEqual(
            "${{ github.event.pull_request.base.sha || github.sha }}",
            env.get("EXPECTED_PROTECTED_MAIN"),
        )
        run = step.get("run")
        self.assertIsInstance(run, str)
        assert isinstance(run, str)
        self.assertIn(
            "PYTHONPATH=. python ci/review_outer_smoke.py "
            '--expected-protected-main "${EXPECTED_PROTECTED_MAIN}"',
            run,
        )
        self.assertNotIn("prior-effective B1.6", workflow_text)

    def test_exit_decision_and_semantic_guardrail_are_durable(self) -> None:
        self.assertTrue(
            DECISION_PATH.is_file(),
            "P2B_EXIT_NEGATIVE_READBACK_DECISION_UNAVAILABLE",
        )
        decision = DECISION_PATH.read_text(encoding="utf-8")
        for required in (
            "Decision 0079",
            "5680382022",
            PROMOTION_MAIN_REVISION,
            P2B_SOURCE_REVISION,
            P2B_SOURCE_TREE,
            P2B_PUBLIC_SURFACE_DIGEST,
            P2B_OCI_IMAGE,
            B16_OCI_IMAGE,
            "candidate-controlled runtime",
            "subsequent candidate",
            "negative read-back",
            "no registry write",
            "does not close issue #11",
        ):
            self.assertIn(required, decision)

        index = INDEX_PATH.read_text(encoding="utf-8")
        self.assertIn(DECISION_RELATIVE_PATH.removeprefix("knowledge/"), index)

        guardrails = yaml.safe_load(GUARDRAILS_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(guardrails, dict)
        entries = guardrails.get("guardrails")
        self.assertIsInstance(entries, list)
        assert isinstance(entries, list)
        semantic = next(
            item
            for item in entries
            if isinstance(item, dict) and item.get("id") == "semantic-review-assurance"
        )
        self.assertIn(DECISION_RELATIVE_PATH, semantic.get("implementation", []))
        self.assertIn(FOCUSED_TEST_PATH, semantic.get("tests", []))

        inner = _load_json(INNER_AUTHORITY_PATH)
        self.assertNotIn("expected_consumer", inner.get("authority", {}))


if __name__ == "__main__":
    unittest.main()
