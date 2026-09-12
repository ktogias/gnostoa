from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReviewAssuranceIntegrationTests(unittest.TestCase):
    def test_candidate_binding_extends_historical_sb2_boundary(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "verification.yml").read_text(
            encoding="utf-8"
        )
        binding = workflow.split("- name: Bind the exact PR executable candidate", 1)[1]
        historical = 'test "$(wc -l < "${sb2_paths_file}")" -eq 14'
        final = 'test "$(wc -l < "${sb2_paths_file}")" -eq 19'
        review_paths = (
            "tools/review_adapter_file.py",
            "tools/review_check.py",
            "tools/review_evaluate.py",
            "tools/review_model.py",
            "tools/review_policy.py",
        )
        self.assertIn(historical, binding)
        self.assertIn(final, binding)
        self.assertLess(binding.index(historical), binding.index(review_paths[0]))
        self.assertLess(binding.index(review_paths[-1]), binding.index(final))
        for path in review_paths:
            with self.subTest(path=path):
                self.assertEqual(1, binding.count(path))
        self.assertIn("sb2.membership=19", binding)

    def test_fast_suite_runs_the_pre_registered_review_assurance_oracle(self) -> None:
        verify = (ROOT / "ci" / "verify").read_text(encoding="utf-8")
        fast = verify.split("  fast)", 1)[1].split("    ;;", 1)[0]
        self.assertIn("python -m unittest discover -s tests -v", fast)
        self.assertIn("python tests/test_review_assurance.py", fast)


if __name__ == "__main__":
    unittest.main()
