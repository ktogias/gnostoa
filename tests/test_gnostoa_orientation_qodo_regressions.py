from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class OrientationQodoRegressionTests(unittest.TestCase):
    def test_real_retained_snapshot_regression_is_checkout_root_bound(self) -> None:
        source = (ROOT / "tests/test_gnostoa_orientation.py").read_text(encoding="utf-8")
        method = source.split(
            "    def test_live_cli_rejects_retained_projection_after_git_subject_drift",
            maxsplit=1,
        )[1].split("\n    def ", maxsplit=1)[0]
        self.assertIn("live_root = ROOT", method)
        self.assertNotIn("Path.cwd()", method)

    def test_repository_subject_guard_is_declared_in_guardrail_coverage(self) -> None:
        policy = (ROOT / "policy/guardrails.yaml").read_text(encoding="utf-8")
        for expected in (
            "id: self-orientation-repository-subject-currentness",
            "tasks/gnostoa_orientation.py#build_manifest",
            "tasks/gnostoa_orientation.py#observe_repository_subject",
            "tests/test_gnostoa_orientation.py::OrientationTests.test_live_cli_rejects_retained_projection_after_git_subject_drift",
            "tests/test_gnostoa_orientation_git_guard.py::OrientationGitGuardTests.test_bound_repository_subject_is_evidence_and_each_mismatch_is_stale",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, policy)

    def test_decision_records_proportionate_git_prior_art_and_license_fit(self) -> None:
        decision = (
            ROOT
            / "knowledge/decisions/0066-invalidate-self-orientation-on-local-git-subject-drift.md"
        ).read_text(encoding="utf-8")
        for expected in (
            "Git CLI",
            "GPL-2.0-only",
            "GitPython",
            "BSD-3-Clause",
            "Dulwich",
            "Apache-2.0 OR GPL-2.0-or-later",
            "No new Python dependency",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, decision)


if __name__ == "__main__":
    unittest.main()
