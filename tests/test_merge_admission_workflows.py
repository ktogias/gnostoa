"""The merge-admission workflows' protected boundary, and L1's two modes the relay
reads (#407, MA0 slice 1b.4; Decisions 0096 and 0112).

The trigger computes nothing and holds nothing. The privileged workflow runs only
from protected main, re-reads every subject, re-reads the analyzer inventory at the
admission point through the existing readback, and publishes through the dedicated
App's token alone.
"""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

import yaml
from test_merge_evidence_github import API, HEAD, _replies
from test_review_reconcile_l1 import adapter_fixture, paged_fake_fixture

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
TRIGGER = WORKFLOWS / "merge-admission-trigger.yml"
ADMISSION = WORKFLOWS / "merge-admission.yml"
READBACK = WORKFLOWS / "analyzer-readback.yml"
# Selected in the MA0 package (#407, 6069729619): v3.2.0, MIT.
APP_TOKEN_ACTION = (
    "actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1"
)
MAIN_ONLY = "github.ref == 'refs/heads/main'"


def _load(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"{path.name} is not a workflow")
    # YAML reads the key `on` as True.
    if True in document:
        document["on"] = document.pop(True)
    return document


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return list(job.get("steps", []))


class TriggerWorkflowTests(unittest.TestCase):
    """Decision 0096 rule 2: the untrusted trigger has no permission, no secret
    and no checkout, and computes nothing."""

    def test_it_wakes_on_the_events_that_change_a_verdict(self) -> None:
        workflow = _load(TRIGGER)
        self.assertEqual("Merge admission trigger", workflow["name"])
        events = workflow["on"]
        self.assertEqual({"pull_request", "pull_request_review"}, set(events))
        self.assertLessEqual(
            {"opened", "edited", "reopened", "synchronize", "ready_for_review"},
            set(events["pull_request"]["types"]),
        )
        self.assertLessEqual(
            {"submitted", "edited", "dismissed"},
            set(events["pull_request_review"]["types"]),
        )

    def test_it_holds_nothing(self) -> None:
        text = TRIGGER.read_text(encoding="utf-8")
        workflow = _load(TRIGGER)
        self.assertEqual({}, workflow["permissions"])
        self.assertNotIn("secrets.", text)
        self.assertNotIn("pull_request_target", text)
        for name, job in workflow["jobs"].items():
            with self.subTest(job=name):
                self.assertNotIn("environment", job)
                self.assertNotIn("permissions", job)
                for step in _steps(job):
                    self.assertNotIn("uses", step)


class AdmissionWorkflowTests(unittest.TestCase):
    """The privileged relay: protected main only, events as hints only."""

    def test_its_events(self) -> None:
        workflow = _load(ADMISSION)
        self.assertEqual("Merge admission", workflow["name"])
        events = workflow["on"]
        self.assertEqual({"workflow_run", "schedule", "workflow_dispatch"}, set(events))
        self.assertEqual(
            ["Merge admission trigger", "Gnostoa verification"],
            events["workflow_run"]["workflows"],
        )
        self.assertEqual(["completed"], events["workflow_run"]["types"])
        self.assertTrue(events["schedule"])
        self.assertIn("pull_number", events["workflow_dispatch"]["inputs"])

    def test_the_workflow_token_writes_nothing(self) -> None:
        workflow = _load(ADMISSION)
        scopes = [workflow.get("permissions", {})] + [
            job.get("permissions", {}) for job in workflow["jobs"].values()
        ]
        for scope in scopes:
            for permission, level in scope.items():
                with self.subTest(permission=permission):
                    self.assertIn(level, {"read", "none"})

    def test_every_job_runs_only_from_protected_main(self) -> None:
        workflow = _load(ADMISSION)
        for name, job in workflow["jobs"].items():
            with self.subTest(job=name):
                self.assertIn(MAIN_ONLY, str(job.get("if", "")))

    def test_a_workflow_run_counts_only_from_its_named_files(self) -> None:
        """Rule 7: `workflow_run` matches by name, so the path and the event of the
        triggering run are admitted explicitly."""

        conditions = " ".join(
            str(job.get("if", "")) for job in _load(ADMISSION)["jobs"].values()
        )
        for needle in (
            ".github/workflows/merge-admission-trigger.yml",
            ".github/workflows/verification.yml",
            "github.event.workflow_run.event == 'pull_request'",
            "github.event.workflow_run.event == 'pull_request_review'",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, conditions)

    def test_the_inventory_is_re_read_through_the_existing_readback(self) -> None:
        jobs = _load(ADMISSION)["jobs"]
        callers = [
            job
            for job in jobs.values()
            if job.get("uses") == "./.github/workflows/analyzer-readback.yml"
        ]
        self.assertEqual(1, len(callers))
        self.assertIs(True, callers[0]["with"]["admission"])
        self.assertIn("pull_number", callers[0]["with"])
        self.assertIn("head", callers[0]["with"])

    def test_only_the_publishing_job_holds_the_dedicated_app(self) -> None:
        jobs = _load(ADMISSION)["jobs"]
        holders = {
            name: job
            for name, job in jobs.items()
            if job.get("environment") == "gnostoa-ma0"
        }
        self.assertEqual(1, len(holders))
        (job,) = holders.values()
        minting = [step for step in _steps(job) if step.get("uses") == APP_TOKEN_ACTION]
        self.assertEqual(1, len(minting))
        inputs = minting[0].get("with", {})
        permissions = {k: v for k, v in inputs.items() if k.startswith("permission-")}
        self.assertEqual({"permission-checks": "write"}, permissions)
        for other_name, other in jobs.items():
            if other_name in holders:
                continue
            with self.subTest(job=other_name):
                self.assertNotIn(APP_TOKEN_ACTION, str(other))

    def test_checkouts_take_main_without_credentials(self) -> None:
        for name, job in _load(ADMISSION)["jobs"].items():
            for step in _steps(job):
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    with self.subTest(job=name):
                        self.assertNotIn("ref", step.get("with", {}))
                        self.assertIs(False, step["with"]["persist-credentials"])

    def test_it_runs_main_s_own_commands(self) -> None:
        text = ADMISSION.read_text(encoding="utf-8")
        for command in (
            "ci/review_github_current_state.py",
            "--mode subjects",
            "--mode merge-evidence",
            "merge-evidence",
            "merge-admission",
            "ci/merge_admission_relay.py",
        ):
            with self.subTest(command=command):
                self.assertIn(command, text)
        self.assertNotIn("pull_request_target", text)


class ReadbackCallTests(unittest.TestCase):
    """`analyzer-readback.yml` gains one entry: a call from the admission run."""

    def test_it_can_be_called_for_an_exact_subject(self) -> None:
        call = _load(READBACK)["on"]["workflow_call"]
        self.assertEqual({"pull_number", "head", "admission"}, set(call["inputs"]))
        self.assertEqual("boolean", call["inputs"]["admission"]["type"])

    def test_a_call_names_its_subject_as_a_call(self) -> None:
        """The secret-free subject step resolves a call from its inputs, never from
        the caller's own event."""
        steps = _load(READBACK)["jobs"]["readback"]["steps"]
        (subject,) = [step for step in steps if step.get("id") == "subject"]
        self.assertEqual(
            "${{ inputs.admission == true && 'workflow_call' || github.event_name }}",
            subject["env"]["EVENT_NAME"],
        )
        self.assertEqual("${{ inputs.pull_number }}", subject["env"]["DISPATCH_PULL"])
        self.assertEqual("${{ inputs.head }}", subject["env"]["DISPATCH_HEAD"])

    def test_a_call_is_admitted_from_protected_main_only(self) -> None:
        condition = str(_load(READBACK)["jobs"]["readback"]["if"])
        self.assertTrue(condition.strip().startswith(MAIN_ONLY))
        self.assertIn("inputs.admission", condition)


class ReadbackSubjectTests(unittest.TestCase):
    """The admission run's call names its subject through the inputs, as an owner's
    dispatch does; the runner still re-reads the Pull Request."""

    @staticmethod
    def _resolver() -> Any:
        import importlib.util

        path = ROOT / "ci" / "analyzer_readback_subject.py"
        spec = importlib.util.spec_from_file_location("gnostoa_readback_subject", path)
        if spec is None or spec.loader is None:
            raise AssertionError("readback subject resolver is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_a_call_resolves_its_inputs(self) -> None:
        resolver = self._resolver()
        self.assertEqual(
            {"pull_number": "300", "head": HEAD},
            resolver.resolve(
                {
                    "EVENT_NAME": "workflow_call",
                    "DISPATCH_PULL": "300",
                    "DISPATCH_HEAD": HEAD,
                }
            ),
        )

    def test_a_call_without_an_exact_subject_binds_none(self) -> None:
        resolver = self._resolver()
        for name, environ in (
            ("no head", {"EVENT_NAME": "workflow_call", "DISPATCH_PULL": "300"}),
            (
                "a short head",
                {
                    "EVENT_NAME": "workflow_call",
                    "DISPATCH_PULL": "300",
                    "DISPATCH_HEAD": "abc",
                },
            ),
            ("no pull", {"EVENT_NAME": "workflow_call", "DISPATCH_HEAD": HEAD}),
        ):
            with self.subTest(name), self.assertRaises(ValueError):
                resolver.resolve(environ)


class L1ModeTests(unittest.TestCase):
    """L1's command line exposes what it already owns: the subjects to admit, and
    one pull request's merge-evidence snapshot. Its acquisition is unchanged."""

    def _run(self, module: Any, replies: dict[str, Any], *argv: str) -> int:
        fake = paged_fake_fixture(replies)
        with (
            mock.patch.object(module, "GitHubRestClient", return_value=fake),
            mock.patch.dict(os.environ, {"GH_TOKEN": "x" * 40}),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            try:
                return int(module.main(list(argv)))
            except SystemExit as exc:
                # A message instead of a status exits 1, as Python's own exit does.
                return exc.code if isinstance(exc.code, int) else 1

    def test_subjects_from_a_hint_read_each_head_natively(self) -> None:
        module = adapter_fixture()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "subjects.json"
            code = self._run(
                module,
                _replies(),
                "--mode",
                "subjects",
                "--repository",
                "ktogias/gnostoa",
                "--workflow-run-pulls-json",
                json.dumps([{"number": 300, "head": {"sha": "f" * 40}}]),
                "--output",
                str(output),
            )
            self.assertEqual(0, code)
            self.assertEqual(
                [{"pull_number": 300, "head": HEAD}],
                json.loads(output.read_text(encoding="utf-8")),
            )

    def test_a_closed_hint_is_no_subject(self) -> None:
        module = adapter_fixture()
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["state"] = "closed"
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "subjects.json"
            code = self._run(
                module,
                replies,
                "--mode",
                "subjects",
                "--repository",
                "ktogias/gnostoa",
                "--pull-number",
                "300",
                "--output",
                str(output),
            )
            self.assertEqual(0, code)
            self.assertEqual([], json.loads(output.read_text(encoding="utf-8")))

    def test_without_a_hint_the_sweep_selects_the_open_population(self) -> None:
        module = adapter_fixture()
        replies = _replies()
        pull = copy.deepcopy(replies[f"{API}/pulls/300"][0])
        replies[f"{API}/pulls?state=open&per_page=100"] = ([pull], {})
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "subjects.json"
            code = self._run(
                module,
                replies,
                "--mode",
                "subjects",
                "--repository",
                "ktogias/gnostoa",
                "--output",
                str(output),
            )
            self.assertEqual(0, code)
            self.assertEqual(
                [{"pull_number": 300, "head": HEAD}],
                json.loads(output.read_text(encoding="utf-8")),
            )

    def test_merge_evidence_writes_the_snapshot_the_adapter_reads(self) -> None:
        module = adapter_fixture()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "snapshot.json"
            code = self._run(
                module,
                _replies(),
                "--mode",
                "merge-evidence",
                "--repository",
                "ktogias/gnostoa",
                "--pull-number",
                "300",
                "--output",
                str(output),
            )
            self.assertEqual(0, code)
            snapshot = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(HEAD, snapshot["subject"]["head_commit"])
            for key in ("commits", "files", "closing_issues", "work_items"):
                with self.subTest(key=key):
                    self.assertIn(key, snapshot)

    def test_merge_evidence_takes_exactly_one_pull_request(self) -> None:
        module = adapter_fixture()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "snapshot.json"
            code = self._run(
                module,
                _replies(),
                "--mode",
                "merge-evidence",
                "--repository",
                "ktogias/gnostoa",
                "--pull-number",
                "300",
                "--pull-number",
                "301",
                "--output",
                str(output),
            )
            self.assertNotEqual(0, code)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
