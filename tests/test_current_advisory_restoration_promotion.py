from __future__ import annotations

import copy
import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

import yaml
from jsonschema import Draft202012Validator

from ci import review_current_advisory_promotion_smoke as promotion_smoke
from tools import review_outer, review_protected, security_scan
from tools.review_check import FORMAT_CHECKER
from tools.review_model import canonical_json
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json"
SCHEMA_PATH = ROOT / "schemas" / "review-protected-consumer-authority.schema.json"
DECISION_RELATIVE_PATH = (
    "knowledge/decisions/0085-promote-current-advisory-restoration-runtime.md"
)
DECISION_PATH = ROOT / DECISION_RELATIVE_PATH
WORKFLOW_PATH = ROOT / ".github/workflows/r2a-protected-current-advisory.yml"
GUARDRAILS_PATH = ROOT / "policy/guardrails.yaml"
INDEX_PATH = ROOT / "knowledge/index.md"
PROMOTION_SMOKE_RELATIVE_PATH = "ci/review_current_advisory_promotion_smoke.py"
PROMOTION_SMOKE_PATH = ROOT / PROMOTION_SMOKE_RELATIVE_PATH
FOCUSED_TEST_RELATIVE_PATH = "tests/test_current_advisory_restoration_promotion.py"

SOURCE_REVISION = "315487e7a67635ebf3ec3f70f666ef41646102e1"  # pragma: allowlist secret -- public source revision
SOURCE_TREE = "ea3fdebc6afa9bf5a4c2d0691199beca4dcece81"  # pragma: allowlist secret -- public source tree
PUBLIC_SURFACE = (
    "sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2"
)
OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:6bf4b876987fa4a5db8e3ae6bcc420e306666d8ee81ca40b934a6570a45b2b0f"
)
PUBLISHER_MAIN = "d097f166a2a6a43e7c963b27aeadd91217e19ac7"  # pragma: allowlist secret -- public protected-main revision
WORKFLOW_RUN = "35436003854"
ATTESTATION_ID = "48625673"
REKOR_LOG_INDEX = "2892075330"
RECEIPT = "https://github.com/ktogias/gnostoa/issues/11#issuecomment-5741025232"

EXPECTED_CONSUMER = {
    "role": "current_advisory_outer_consumer",
    "acquisition": "oci",
    "source_revision": SOURCE_REVISION,
    "source_tree": SOURCE_TREE,
    "public_surface_digest": PUBLIC_SURFACE,
    "runtime_image": OCI_IMAGE,
    "runtime_revision": SOURCE_REVISION,
    "supported_input_schema_versions": ["1.0"],
    "status": "accepted",
}
EXPECTED_IDENTITY = canonical_json(EXPECTED_CONSUMER)


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return value


class CurrentAdvisoryRestorationPromotionTests(unittest.TestCase):
    def test_r4_protected_authority_binds_exact_reconciled_r3_identity(self) -> None:
        schema = _load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        authority = _load_json(AUTHORITY_PATH)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
        self.assertEqual([], list(validator.iter_errors(authority)))
        self.assertEqual(EXPECTED_CONSUMER, authority.get("expected_consumer"))
        self.assertEqual(EXPECTED_CONSUMER, authority.get("acquired_consumer"))
        self.assertEqual(
            {
                "protected_main_revision": PUBLISHER_MAIN,
                "workflow_run": WORKFLOW_RUN,
                "attestation_id": ATTESTATION_ID,
                "rekor_log_index": REKOR_LOG_INDEX,
                "receipt": RECEIPT,
            },
            authority.get("materialization"),
        )

    def test_r4_security_baseline_pin_binds_exact_authority_bytes(self) -> None:
        expected = hashlib.sha256(AUTHORITY_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            expected,
            security_scan._PROTECTED_BASELINE_FILE_SHA256[
                "tasks/issue-11-r2a-current-advisory-consumer.json"
            ],
        )
        self.assertEqual(
            "5c51c34e3a591c43707a108674eed3a6b77b0ce82516c18ed95bf4470db2eebf",  # pragma: allowlist secret -- reviewed protected-authority content digest
            expected,
        )

    def test_r4_catalog_admits_only_complete_exact_consumer_identity(self) -> None:
        self.assertEqual(
            frozenset({EXPECTED_IDENTITY}),
            review_outer._HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES,
        )
        validated = review_outer._validate_consumer_authority(
            {
                "schema_version": "1.0",
                "subject": {
                    "kind": "gnostoa-protected-main-consumer-record",
                    "value": "tasks/issue-11-r2a-current-advisory-consumer.json:v1",
                },
                "expected_consumer": copy.deepcopy(EXPECTED_CONSUMER),
                "acquired_consumer": copy.deepcopy(EXPECTED_CONSUMER),
                "materialization": {
                    "protected_main_revision": PUBLISHER_MAIN,
                    "workflow_run": WORKFLOW_RUN,
                    "attestation_id": ATTESTATION_ID,
                    "rekor_log_index": REKOR_LOG_INDEX,
                    "receipt": RECEIPT,
                },
            }
        )
        review_outer._require_transport_compatible_consumer(validated)

        for field, value in EXPECTED_CONSUMER.items():
            changed = copy.deepcopy(EXPECTED_CONSUMER)
            changed[field] = (
                [*value, "2.0"] if isinstance(value, list) else str(value) + "-changed"
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    review_outer.PriorEffectiveOuterUnavailable,
                    "transport is not admitted",
                ):
                    review_outer._require_transport_compatible_consumer(changed)

    def test_r4_exact_identity_still_requires_protected_image_proof(self) -> None:
        authority = _load_json(AUTHORITY_PATH)
        protected = ProtectedMainDocument("c" * 40, authority)
        with (
            mock.patch.object(
                review_outer,
                "acquire_gnostoa_current_advisory_consumer",
                return_value=protected,
            ),
            mock.patch.object(
                review_outer,
                "_verify_outer_image",
                side_effect=review_outer.ProtectedJudgeUnavailable(
                    "synthetic promoted-image proof failed"
                ),
            ) as verify_image,
            mock.patch.object(review_outer, "_checked_output") as command,
            mock.patch.object(review_outer, "_run_docker") as docker,
        ):
            code, raw = review_outer.run_prior_effective_current_advisory({})
        self.assertEqual(2, code)
        self.assertIn("synthetic promoted-image proof failed", raw.decode("utf-8"))
        verify_image.assert_called_once()
        command.assert_not_called()
        docker.assert_not_called()

    def test_r4_protected_smoke_executes_the_revision_checked_authority(self) -> None:
        expected_main = "a" * 40
        advanced_main = "b" * 40
        authority = _load_json(AUTHORITY_PATH)
        checked_consumer = ProtectedMainDocument(
            protected_main_revision=expected_main,
            document=copy.deepcopy(authority),
        )
        advanced_consumer = ProtectedMainDocument(
            protected_main_revision=advanced_main,
            document=copy.deepcopy(authority),
        )
        inner = ProtectedMainDocument(
            protected_main_revision=expected_main,
            document={
                "authority": {},
                "acquired_judge": {},
                "qualification_snapshot": {},
            },
        )
        semantic = (
            b'{"binding":false,"outcome":"INCOMPLETE","reason":"QUORUM_UNMET"}\n'
        )

        second_acquisition = mock.Mock(return_value=advanced_consumer)

        def execute(_: object) -> tuple[int, bytes]:
            observed = review_outer.acquire_gnostoa_current_advisory_consumer()
            if observed.protected_main_revision != expected_main:
                raise RuntimeError(
                    "protected consumer authority changed during R4 promotion proof"
                )
            return 3, semantic

        with (
            mock.patch.object(
                review_protected,
                "acquire_gnostoa_current_advisory_bundle",
                return_value=inner,
            ),
            mock.patch.object(
                review_protected,
                "acquire_gnostoa_current_advisory_consumer",
                return_value=checked_consumer,
            ) as checked_acquisition,
            mock.patch.object(
                review_outer,
                "acquire_gnostoa_current_advisory_consumer",
                second_acquisition,
            ),
            mock.patch.object(
                review_outer,
                "run_prior_effective_current_advisory",
                side_effect=execute,
            ),
            mock.patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            code = promotion_smoke.main(
                [
                    "--mode",
                    "protected",
                    "--expected-protected-main",
                    expected_main,
                ]
            )

        self.assertEqual(0, code)
        checked_acquisition.assert_called_once_with()
        second_acquisition.assert_not_called()
        receipt = json.loads(output.getvalue())
        self.assertEqual(expected_main, receipt["protected_main_revision"])
        self.assertEqual("protected-main", receipt["authority_source"])
        self.assertEqual(
            canonical_json(EXPECTED_CONSUMER),
            receipt["consumer_identity"],
        )

    def test_r4_decision_governance_and_live_smoke_are_routed(self) -> None:
        self.assertTrue(DECISION_PATH.is_file())
        self.assertTrue(
            PROMOTION_SMOKE_PATH.is_file(),
            "R4_PROMOTION_SMOKE_UNAVAILABLE: no candidate-side live proof exists",
        )
        self.assertIn(
            DECISION_RELATIVE_PATH.removeprefix("knowledge/"),
            INDEX_PATH.read_text(encoding="utf-8"),
        )

        guardrails = yaml.safe_load(GUARDRAILS_PATH.read_text(encoding="utf-8"))
        entries = guardrails["guardrails"]
        semantic = next(
            entry for entry in entries if entry.get("id") == "semantic-review-assurance"
        )
        self.assertIn(DECISION_RELATIVE_PATH, semantic["implementation"])
        self.assertIn("tools/review_outer.py", semantic["implementation"])
        self.assertIn(
            "tasks/issue-11-r2a-current-advisory-consumer.json",
            semantic["implementation"],
        )
        self.assertIn(FOCUSED_TEST_RELATIVE_PATH, semantic["tests"])

        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        workflow_doc = yaml.load(workflow, Loader=yaml.BaseLoader)
        self.assertIsInstance(workflow_doc, dict)
        assert isinstance(workflow_doc, dict)
        jobs = workflow_doc.get("jobs")
        self.assertIsInstance(jobs, dict)
        assert isinstance(jobs, dict)
        protected_job = jobs.get("protected-current-advisory-consumer")
        self.assertIsInstance(protected_job, dict)
        assert isinstance(protected_job, dict)
        steps = protected_job.get("steps")
        self.assertIsInstance(steps, list)
        assert isinstance(steps, list)
        guards = [
            step
            for step in steps
            if isinstance(step, dict)
            and step.get("name") == "Require protected main for manual R2A verification"
        ]
        self.assertEqual(1, len(guards))
        guard = guards[0]
        self.assertEqual(
            "github.event_name == 'workflow_dispatch'",
            guard.get("if"),
        )
        guard_run = guard.get("run")
        self.assertIsInstance(guard_run, str)
        assert isinstance(guard_run, str)
        self.assertIn(
            'test "${GITHUB_REF}" = "refs/heads/main"',
            guard_run,
        )
        self.assertIn(
            "manual protected-route verification must run from refs/heads/main",
            guard_run,
        )

        for path in (
            DECISION_RELATIVE_PATH,
            PROMOTION_SMOKE_RELATIVE_PATH,
            FOCUSED_TEST_RELATIVE_PATH,
        ):
            self.assertIn(f'- "{path}"', workflow)
        self.assertGreaterEqual(workflow.count(FOCUSED_TEST_RELATIVE_PATH), 3)
        self.assertIn(
            "PYTHONPATH=. python ci/review_current_advisory_promotion_smoke.py",
            workflow,
        )
        self.assertIn(
            "Exercise candidate-side exact R4 promoted current-advisory path",
            workflow,
        )
        self.assertIn("--mode candidate", workflow)
        self.assertIn(
            "Exercise protected-main promoted current-advisory route",
            workflow,
        )
        protected_routes = [
            step
            for step in steps
            if isinstance(step, dict)
            and step.get("name")
            == "Exercise protected-main promoted current-advisory route"
        ]
        self.assertEqual(1, len(protected_routes))
        self.assertEqual(
            "github.event_name == 'workflow_dispatch'",
            protected_routes[0].get("if"),
        )
        self.assertIn("--mode protected", workflow)
        self.assertIn("workflow_dispatch:", workflow)


if __name__ == "__main__":
    unittest.main()
