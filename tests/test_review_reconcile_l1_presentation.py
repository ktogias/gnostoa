from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]


def _fixtures() -> Any:
    path = Path(__file__).with_name("test_review_reconcile_l1.py")
    spec = importlib.util.spec_from_file_location("l1_presentation_fixtures", path)
    if spec is None or spec.loader is None:
        raise AssertionError("L1_FIXTURES_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workflow() -> dict[str, Any]:
    path = _ROOT / ".github/workflows/review-current-state.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class UsefulL1PresentationTests(unittest.TestCase):
    def test_serialized_workflow_uses_finite_max_pending_queue(self) -> None:
        concurrency = _workflow()["concurrency"]
        self.assertIs(False, concurrency["cancel-in-progress"])
        self.assertEqual("max", concurrency.get("queue"))

    def test_both_workflow_entrypoints_import_in_a_clean_environment(self) -> None:
        workflow = _workflow()
        for job_name in ("collect", "publish"):
            with self.subTest(job=job_name):
                job = workflow["jobs"][job_name]
                steps = [
                    step
                    for step in job["steps"]
                    if "ci/review_github_current_state.py" in step.get("run", "")
                ]
                self.assertEqual(1, len(steps))
                step = steps[0]
                command = re.search(
                    r"(?m)^\s*(?:PYTHONPATH=(\S+)\s+)?"
                    r"python ci/review_github_current_state\.py\b",
                    step["run"],
                )
                self.assertIsNotNone(command)
                assert command is not None
                environment = {"PATH": os.defpath, "PYTHONNOUSERSITE": "1"}
                for scope in (workflow, job, step):
                    value = scope.get("env", {}).get("PYTHONPATH")
                    if value is not None:
                        environment["PYTHONPATH"] = value
                if command.group(1) is not None:
                    environment["PYTHONPATH"] = command.group(1)
                completed = subprocess.run(
                    [sys.executable, "ci/review_github_current_state.py", "--help"],
                    cwd=_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertIn("--mode", completed.stdout)

    def test_rendered_check_summary_exposes_omitted_adverse_counts(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        projection = reducer.build_projection(
            fixtures._snapshot(),
            protected_main_revision="e" * 40,
            outer_consumer={
                "runtime_image": "ghcr.io/ktogias/gnostoa@sha256:" + "f" * 64,
                "runtime_revision": "9" * 40,
            },
            r2a_result={
                "outcome": "PASS",
                "reason": "QUORUM_SATISFIED",
                "binding": False,
            },
            execution={
                "execution_id": "presentation-test::omitted-checks",
                "observed_at": "2026-09-19T16:41:00Z",
            },
        )
        projection["checks"] = {
            "observed_names": 106,
            "ambiguous": [f"ambiguous-{index}" for index in range(32)],
            "pending": [f"pending-{index}" for index in range(32)],
            "non_success": [f"non-success-{index}" for index in range(32)],
            "omitted_ambiguous": 5,
            "omitted_pending": 3,
            "omitted_non_success": 2,
        }
        projection["next_permitted_action"] = "RECONCILE_PROVIDER_CHECKS"

        rendered = reducer.render_projection(projection)

        self.assertIn("ambiguous=32 (+5 omitted)", rendered)
        self.assertIn("pending=32 (+3 omitted)", rendered)
        self.assertIn("non-success=32 (+2 omitted)", rendered)
        self.assertEqual(projection, reducer.parse_projection_comment(rendered))

    def test_provider_title_cannot_inject_markdown_or_html(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
        snapshot["subject"]["title"] = (
            "[fake approval](https://example.invalid) **PASS** "
            '<img src="x"> `CONTINUE` &lt;b&gt;'
        )
        projection = reducer.build_projection(
            snapshot,
            protected_main_revision=None,
            outer_consumer=None,
            r2a_result={"reason": "TEST_UNAVAILABLE"},
            execution={
                "execution_id": "presentation-test::opaque-execution",
                "observed_at": "2026-09-19T16:41:00Z",
            },
        )
        rendered = reducer.render_projection(projection)
        line = next(line for line in rendered.splitlines() if "Intent summary:" in line)
        for active in (
            "[fake approval](",
            "**PASS**",
            "<img ",
            "`CONTINUE`",
            "<b>",
        ):
            with self.subTest(active=active):
                self.assertNotIn(active, line)
        self.assertIn(r"\[fake approval\]\(https://example\.invalid\)", line)
        self.assertIn(r"\*\*PASS\*\*", line)
        self.assertIn('&lt;img src="x"&gt;', line)
        self.assertIn(r"\`CONTINUE\`", line)
        self.assertIn("&amp;lt;b&amp;gt;", line)
        self.assertLessEqual(len(rendered.encode("utf-8")), 65_536)
        self.assertEqual(projection, reducer.parse_projection_comment(rendered))

    def test_provider_controlled_identities_cannot_inject_markdown_structure(
        self,
    ) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot(
            provider_id="provider`\n- **FORGED PROVIDER**",
            repository="https://example.invalid/repo`\n## FORGED REPOSITORY",
            change_kind="merge`\n> FORGED KIND",
            change_id="42`\n[FORGED](https://example.invalid)",
            source_url="https://example.invalid/change/42",
        )
        projection = reducer.build_projection(
            snapshot,
            protected_main_revision=None,
            outer_consumer=None,
            r2a_result={"reason": "TEST_UNAVAILABLE"},
            execution={
                "execution_id": "provider-run`\n- [x] FORGED EXECUTION",
                "observed_at": "2026-09-19T16:41:00Z",
            },
        )

        rendered = reducer.render_projection(projection)
        lines = rendered.splitlines()
        forbidden_lines = {
            "- **FORGED PROVIDER**",
            "## FORGED REPOSITORY",
            "> FORGED KIND",
            "[FORGED](https://example.invalid)",
            "- [x] FORGED EXECUTION",
        }
        self.assertTrue(forbidden_lines.isdisjoint(lines))
        self.assertEqual(1, sum(line.startswith("- Provider:") for line in lines))
        self.assertEqual(1, sum(line.startswith("- Repository:") for line in lines))
        self.assertEqual(1, sum(line.startswith("- Subject:") for line in lines))
        self.assertEqual(
            1,
            sum(line.startswith("- Execution generation:") for line in lines),
        )
        self.assertEqual(projection, reducer.parse_projection_comment(rendered))


if __name__ == "__main__":
    unittest.main()
