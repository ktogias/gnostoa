from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.review_model import canonical_digest
from tools.review_policy import effective_policy_issues, resolve_project_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / "tasks" / "issue-11-r2a-current-advisory.json"
POLICY_PATH = ROOT / "policy" / "review-policy.yaml"
P2A_SOURCE_REVISION = "d66d1830d724d759db6ec87e1f8d5dcc0847f221"
P2A_PUBLIC_SURFACE_DIGEST = (
    "sha256:ee2418fccd7e8907b8b8f60b0e0c7663e93c3e9abb66d9496efd1c3666ca1845"
)
P2A_OCI_IMAGE = (
    "ghcr.io/ktogias/gnostoa@"
    "sha256:adcf9ce060a382b47973bbd9848ba9dff3bc05985c17411c4b8a2adb9b0c6504"
)
CRITICAL_POLICY_DIGEST = (
    "sha256:6cd1e270ef49170dbfe839107d5e745d8f45b62f33ab4c9116f9846210095179"
)
QUALIFICATION_SNAPSHOT = {
    "snapshot_id": "gnostoa-r2a-qualification-empty-5659481721",
    "revision": "5659481721",
    "qualifying_authority": (
        "https://github.com/ktogias/gnostoa/issues/10#issuecomment-5659481721"
    ),
    "observed_at": "2026-09-14T05:32:08Z",
    "entries": [],
}
QUALIFICATION_DIGEST = (
    "sha256:db18242f682af42490369c85d2f0b770a46a133bfb69c4aba6f12ce6fa2f70a4"
)
EXPECTED_JUDGE = {
    "acquisition": "oci",
    "source_revision": P2A_SOURCE_REVISION,
    "public_surface_digest": P2A_PUBLIC_SURFACE_DIGEST,
    "runtime_image": P2A_OCI_IMAGE,
    "runtime_revision": P2A_SOURCE_REVISION,
    "supported_input_schema_versions": ["1.0"],
    "status": "accepted",
}


class ReviewAssuranceP2bAuthorityLandingTests(unittest.TestCase):
    def test_protected_p2b_a_bundle_binds_exact_prior_integrated_identities(
        self,
    ) -> None:
        self.assertTrue(
            BUNDLE_PATH.is_file(),
            "P2B_PROTECTED_AUTHORITY_UNAVAILABLE: protected current-advisory "
            "authority bundle is absent; do not activate from candidate-authored trust data",
        )
        bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            {"authority", "policy", "qualification_snapshot", "acquired_judge"},
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

    def test_p2b_a_remains_dormant_and_does_not_activate_current_advisory(self) -> None:
        evaluator = (ROOT / "tools" / "review_evaluate.py").read_text(encoding="utf-8")
        cli = (ROOT / "tools" / "review_check.py").read_text(encoding="utf-8")
        self.assertIn('if mode == "current_advisory":', evaluator)
        self.assertIn('"BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE"', evaluator)
        self.assertIn(
            "current_advisory prior-integrated authority acquisition is not available",
            cli,
        )


if __name__ == "__main__":
    unittest.main()
