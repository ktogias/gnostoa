from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

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


def _workflow_entrypoint_pythonpath(
    workflow: dict[str, Any],
    job_name: str,
) -> str:
    job = workflow["jobs"][job_name]
    steps = [
        step
        for step in job["steps"]
        if "ci/review_github_current_state.py" in step.get("run", "")
    ]
    if len(steps) != 1:
        raise AssertionError("workflow entrypoint step is unavailable")
    step = steps[0]
    command = re.search(
        r"(?m)^\s*(?:PYTHONPATH=(\S+)\s+)?"
        r"python ci/review_github_current_state\.py\b",
        step["run"],
    )
    if command is None:
        raise AssertionError("workflow entrypoint command is unavailable")

    pythonpath: object = None
    for scope in (workflow, job, step):
        value = scope.get("env", {}).get("PYTHONPATH")
        if value is not None:
            pythonpath = value
    if command.group(1) is not None:
        pythonpath = command.group(1)
    if not isinstance(pythonpath, str):
        raise AssertionError("workflow entrypoint PYTHONPATH is unavailable")
    return pythonpath


def _load_entrypoint_with_pythonpath(pythonpath: str, job_name: str) -> Any:
    configured_paths = [
        str((_ROOT / item).resolve()) for item in pythonpath.split(os.pathsep) if item
    ]
    if str(_ROOT.resolve()) not in configured_paths:
        raise AssertionError("workflow entrypoint does not expose repository root")

    repository_paths = {
        str(_ROOT.resolve()),
        str((_ROOT / "tests").resolve()),
    }
    isolated_path = [
        *configured_paths,
        *[
            entry
            for entry in sys.path
            if entry and str(Path(entry).resolve()) not in repository_paths
        ],
    ]

    adapter_path = _ROOT / "ci/review_github_current_state.py"
    module_name = f"gnostoa_l1_workflow_entrypoint_{job_name}"
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise AssertionError("workflow entrypoint module is unloadable")

    module_names = ("tools", "tools.review_model", "tools.review_reconcile")
    preserved_modules = {name: sys.modules.get(name) for name in module_names}
    for name in module_names:
        sys.modules.pop(name, None)
    try:
        with mock.patch.object(sys, "path", isolated_path):
            adapter = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(adapter)
    finally:
        for name, preserved in preserved_modules.items():
            if preserved is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = preserved
    return adapter


class UsefulL1PresentationTests(unittest.TestCase):
    def test_serialized_workflow_uses_finite_max_pending_queue(self) -> None:
        concurrency = _workflow()["concurrency"]
        self.assertIs(False, concurrency["cancel-in-progress"])
        self.assertEqual("max", concurrency.get("queue"))

    def test_reconciliation_jobs_have_explicit_bounded_wall_clock_timeouts(
        self,
    ) -> None:
        workflow = _workflow()
        for job_name in ("collect", "publish"):
            with self.subTest(job=job_name):
                timeout = workflow["jobs"][job_name].get("timeout-minutes")
                self.assertIsInstance(timeout, int)
                self.assertGreater(timeout, 0)
                self.assertLessEqual(timeout, 60)

    def test_both_workflow_entrypoints_import_in_a_clean_environment(self) -> None:
        workflow = _workflow()
        for job_name in ("collect", "publish"):
            with self.subTest(job=job_name):
                pythonpath = _workflow_entrypoint_pythonpath(workflow, job_name)
                adapter = _load_entrypoint_with_pythonpath(pythonpath, job_name)

                rendered_help = io.StringIO()
                with (
                    contextlib.redirect_stdout(rendered_help),
                    self.assertRaises(SystemExit) as caught,
                ):
                    adapter.main(["--help"])
                self.assertEqual(0, caught.exception.code)
                self.assertIn("--mode", rendered_help.getvalue())

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

    def test_rendered_check_labels_are_visible_bounded_literals(self) -> None:
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
                "execution_id": "presentation-test::check-labels",
                "observed_at": "2026-09-19T16:41:00Z",
            },
        )
        projection["checks"] = {
            "observed_names": 3,
            "ambiguous": ["@octocat"],
            "pending": ["**pending**"],
            "non_success": ["[failure](https://example.invalid)"],
            "omitted_ambiguous": 0,
            "omitted_pending": 0,
            "omitted_non_success": 0,
        }
        projection["next_permitted_action"] = "RECONCILE_PROVIDER_CHECKS"

        rendered = reducer.render_projection(projection)

        self.assertIn("- Ambiguous checks: `@octocat`", rendered)
        self.assertIn("- Pending checks: `**pending**`", rendered)
        self.assertIn(
            "- Non-success checks: `[failure](https://example.invalid)`",
            rendered,
        )
        self.assertEqual(projection, reducer.parse_projection_comment(rendered))

    def test_provider_title_is_one_inert_literal_including_mentions(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
        snapshot["subject"]["title"] = (
            "[fake approval](https://example.invalid) **PASS** "
            '<img src="x"> `CONTINUE` &lt;b&gt; @octocat @gnostoa/team'
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
        title_lines = [
            item for item in rendered.splitlines() if "Intent summary:" in item
        ]
        self.assertEqual(1, len(title_lines))
        line = title_lines[0]
        literal = line.removeprefix("- Intent summary: ")
        match = re.fullmatch(r"(?P<fence>`+)(?P<body>.*)(?P=fence)", literal)
        if match is None:
            self.fail("provider title did not render as one fenced literal")
        self.assertIn("@octocat", match.group("body"))
        self.assertIn("@gnostoa/team", match.group("body"))
        self.assertNotIn("<img ", line)
        self.assertNotIn("<b>", line)
        self.assertIn("@octocat", line)
        self.assertIn("@gnostoa/team", line)
        self.assertFalse(line.startswith("- Intent summary: @"))
        self.assertLessEqual(len(rendered.encode("utf-8")), 65_536)
        self.assertEqual(projection, reducer.parse_projection_comment(rendered))

    def test_provider_title_ending_in_backtick_keeps_markdown_inert(self) -> None:
        fixtures = _fixtures()
        reducer = fixtures._reducer()
        snapshot = fixtures._snapshot()
        snapshot["subject"]["title"] = "**pwn** [click](https://evil.example) @octocat`"
        projection = reducer.build_projection(
            snapshot,
            protected_main_revision=None,
            outer_consumer=None,
            r2a_result={"reason": "TEST_UNAVAILABLE"},
            execution={
                "execution_id": "presentation-test::trailing-backtick",
                "observed_at": "2026-09-19T16:41:00Z",
            },
        )

        rendered = reducer.render_projection(projection)
        title_lines = [
            item for item in rendered.splitlines() if "Intent summary:" in item
        ]
        self.assertEqual(1, len(title_lines))
        line = title_lines[0]
        self.assertTrue(line.startswith("- Intent summary: `` "))
        self.assertTrue(line.endswith(" ``"))
        self.assertIn("**pwn**", line)
        self.assertIn("[click](https://evil.example)", line)
        self.assertIn("@octocat", line)
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
