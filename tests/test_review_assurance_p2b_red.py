from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from tools.review_check import FORMAT_CHECKER
from tools.review_model import canonical_digest
from tools.review_policy import effective_policy_issues, resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
BUNDLE_SCHEMA_PATH = ROOT / "schemas" / "review-protected-authority-bundle.schema.json"
POLICY_PATH = ROOT / "policy" / "review-policy.yaml"
P2A_SOURCE_REVISION = "d66d1830d724d759db6ec87e1f8d5dcc0847f221"  # pragma: allowlist secret -- public prior-integrated source revision
P2A_PUBLIC_SURFACE_DIGEST = "sha256:ee2418fccd7e8907b8b8f60b0e0c7663e93c3e9abb66d9496efd1c3666ca1845"  # pragma: allowlist secret -- public surface digest
P2A_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:adcf9ce060a382b47973bbd9848ba9dff3bc05985c17411c4b8a2adb9b0c6504"  # pragma: allowlist secret -- public registry identity
)
CRITICAL_POLICY_DIGEST = "sha256:6cd1e270ef49170dbfe839107d5e745d8f45b62f33ab4c9116f9846210095179"  # pragma: allowlist secret -- public policy digest
QUALIFICATION_SNAPSHOT = {
    "snapshot_id": "gnostoa-r2a-qualification-empty-5659481721",
    "revision": "5659481721",
    "qualifying_authority": (
        "https://github.com/ktogias/gnostoa/issues/10#issuecomment-5659481721"
    ),
    "observed_at": "2026-09-14T05:32:08Z",
    "entries": [],
}
QUALIFICATION_DIGEST = "sha256:db18242f682af42490369c85d2f0b770a46a133bfb69c4aba6f12ce6fa2f70a4"  # pragma: allowlist secret -- public qualification snapshot digest
EXPECTED_JUDGE = {
    "acquisition": "oci",
    "source_revision": P2A_SOURCE_REVISION,
    "public_surface_digest": P2A_PUBLIC_SURFACE_DIGEST,
    "runtime_image": P2A_OCI_IMAGE,
    "runtime_revision": P2A_SOURCE_REVISION,
    "supported_input_schema_versions": ["1.0"],
    "status": "accepted",
}


def _bundle() -> dict[str, object]:
    value = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError("P2b-A candidate landing bundle must be a JSON object")
    return value


class ReviewAssuranceP2bAuthorityLandingTests(unittest.TestCase):
    def test_p2b_a_candidate_landing_bundle_is_versioned_and_schema_closed(
        self,
    ) -> None:
        self.assertTrue(
            BUNDLE_SCHEMA_PATH.is_file(),
            "P2B_AUTHORITY_BUNDLE_SCHEMA_UNAVAILABLE: dormant authority landing needs "
            "a dedicated versioned closed schema before integration",
        )
        schema = json.loads(BUNDLE_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
        bundle = _bundle()
        self.assertEqual("1.0", bundle.get("schema_version"))
        self.assertEqual([], list(validator.iter_errors(bundle)))

        unknown = copy.deepcopy(bundle)
        unknown["candidate_claim"] = True
        self.assertNotEqual([], list(validator.iter_errors(unknown)))

        nonempty_qualification = copy.deepcopy(bundle)
        qualification = nonempty_qualification["qualification_snapshot"]
        assert isinstance(qualification, dict)
        qualification["entries"] = [
            {
                "reviewer_id": "unadmitted-reviewer",
                "source_id": "unadmitted-source",
                "independence_domain_id": "unadmitted-domain",
                "capability_ids": ["semantic-review"],
                "status": "established",
                "observed_at": "2026-09-14T05:32:08Z",
                "owner_relation": "non_owner",
                "scope": {"candidate_claim": True},
                "provenance": {"candidate_claim": True},
            }
        ]
        self.assertNotEqual(
            [],
            list(validator.iter_errors(nonempty_qualification)),
            "P2b-A v1 must not admit qualification facts beyond the protected empty #10 snapshot",
        )

        malformed_timestamp = copy.deepcopy(bundle)
        qualification = malformed_timestamp["qualification_snapshot"]
        assert isinstance(qualification, dict)
        qualification["observed_at"] = "not-a-timestamp"
        self.assertNotEqual(
            [],
            list(validator.iter_errors(malformed_timestamp)),
            "P2b-A v1 date-time fields must reject malformed timestamps",
        )

    def test_p2b_a_candidate_landing_declares_exact_intended_bindings(self) -> None:
        self.assertTrue(
            BUNDLE_PATH.is_file(),
            "P2B_AUTHORITY_LANDING_UNAVAILABLE: candidate authority landing artifact is absent",
        )
        bundle = _bundle()
        self.assertEqual(
            {
                "schema_version",
                "authority",
                "policy",
                "qualification_snapshot",
                "acquired_judge",
            },
            set(bundle),
        )

        policy = bundle["policy"]
        self.assertEqual(resolve_project_policy(POLICY_PATH, "critical"), policy)
        self.assertEqual([], effective_policy_issues(policy))
        self.assertEqual(CRITICAL_POLICY_DIGEST, canonical_digest(policy))

        qualification = bundle["qualification_snapshot"]
        self.assertEqual(QUALIFICATION_SNAPSHOT, qualification)
        self.assertEqual([], qualification["entries"])
        self.assertEqual(QUALIFICATION_DIGEST, canonical_digest(qualification))

        acquired_judge = bundle["acquired_judge"]
        self.assertEqual(EXPECTED_JUDGE, acquired_judge)

        authority = bundle["authority"]
        self.assertEqual(
            {
                "kind": "gnostoa-protected-main-record",
                "value": "tasks/issue-11-r2a-current-advisory.json:v1",
            },
            authority["subject"],
        )
        self.assertEqual(CRITICAL_POLICY_DIGEST, authority["policy_digest"])
        self.assertEqual(
            QUALIFICATION_DIGEST,
            authority["qualification_snapshot_digest"],
        )
        self.assertEqual(EXPECTED_JUDGE, authority["expected_judge"])

    def test_protected_main_readback_remains_authority_source_after_activation(self) -> None:
        protected = (ROOT / "tools" / "review_protected.py").read_text(encoding="utf-8")
        evaluator = (ROOT / "tools" / "review_evaluate.py").read_text(encoding="utf-8")
        cli = (ROOT / "tools" / "review_check.py").read_text(encoding="utf-8")

        self.assertIn(
            '_GNOSTOA_SELF_BUNDLE_PATH = "tasks/issue-11-r2a-current-advisory.json"',
            protected,
        )
        self.assertIn(
            '"+refs/heads/main:refs/remotes/protected/main"',
            protected,
        )
        self.assertNotIn("issue-11-r2a-current-advisory.json", evaluator)
        self.assertNotIn("issue-11-r2a-current-advisory.json", cli)
        self.assertIn('if mode == "current_advisory":', evaluator)
        self.assertIn('"BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE"', evaluator)
        self.assertIn(
            "from .review_live import evaluate_gnostoa_current_advisory",
            cli,
        )
        self.assertIn(
            "code, payload = evaluate_gnostoa_current_advisory(input_document)",
            cli,
        )


if __name__ == "__main__":
    unittest.main()
