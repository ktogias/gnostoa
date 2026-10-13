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
import re
import sys
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
RUNBOOK = ROOT / "knowledge" / "runbooks" / "operate-the-merge-gate.md"
AUTHORITIES = ROOT / "policy" / "merge-authorities.yaml"
# Selected in the MA0 package (#407, 6069729619): v3.2.0, MIT.
APP_MINT_ACTION = (
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


def _run_lines(step: dict[str, Any]) -> list[str]:
    """The step's executable shell lines, stripped, with comments dropped."""

    lines = (line.strip() for line in str(step.get("run", "")).splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def _declarer() -> str:
    document = yaml.safe_load(AUTHORITIES.read_text(encoding="utf-8"))
    declarer: str = document["declarer"]
    return declarer


def _normalized(expression: object) -> str:
    return " ".join(str(expression).split())


# The exact conditions (cubic r4251444309 on #426): a substring proves nothing about
# what an `||` beside it admits.
SUBJECTS_IF = (
    "github.ref == 'refs/heads/main' && (github.event_name == 'schedule'"
    " || github.event_name == 'workflow_dispatch'"
    " || (github.event_name == 'repository_dispatch'"
    " && github.event.action == 'gnostoa-merge-admission')"
    " || (github.event_name == 'workflow_run'"
    " && ((github.event.workflow_run.path == '.github/workflows/merge-admission-trigger.yml'"
    " && github.event.workflow_run.conclusion == 'success'"
    ' && contains(fromJSON(\'["pull_request","pull_request_review",'
    '"pull_request_review_comment","issue_comment"]\'),'
    " github.event.workflow_run.event))"
    " || (github.event.workflow_run.path == '.github/workflows/verification.yml'"
    " && github.event.workflow_run.event == 'pull_request'))))"
)
INVALIDATE_IF = (
    "github.ref == 'refs/heads/main' && needs.subjects.result == 'success'"
    " && needs.subjects.outputs.subjects != '[]'"
)
AFTER_INVALIDATION_IF = (
    "always() && github.ref == 'refs/heads/main' && needs.subjects.result == 'success'"
    " && needs.subjects.outputs.subjects != '[]'"
)
# GitHub Actions' trigger events, as "Events that trigger workflows" documents them
# (docs.github.com, read 2026-10-13). A webhook-only event in `on:`, such as
# `pull_request_review_thread`, makes the whole workflow invalid, so nothing wakes
# (Codex on #426; run 38321482587, "Unexpected value 'pull_request_review_thread'").
ACTIONS_EVENTS = frozenset(
    {
        "branch_protection_rule",
        "check_run",
        "check_suite",
        "create",
        "delete",
        "deployment",
        "deployment_status",
        "discussion",
        "discussion_comment",
        "fork",
        "gollum",
        "image_version",
        "issue_comment",
        "issues",
        "label",
        "merge_group",
        "milestone",
        "page_build",
        "public",
        "pull_request",
        "pull_request_review",
        "pull_request_review_comment",
        "pull_request_target",
        "push",
        "registry_package",
        "release",
        "repository_dispatch",
        "schedule",
        "status",
        "watch",
        "workflow_call",
        "workflow_dispatch",
        "workflow_run",
    }
)
UPLOAD_ACTION = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
DOWNLOAD_ACTION = "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0"


class TriggerWorkflowTests(unittest.TestCase):
    """Decision 0096 rule 2: the untrusted trigger has no permission, no secret
    and no checkout, and computes nothing."""

    def test_every_event_is_an_actions_trigger(self) -> None:
        """The Router's T1 on #426 (6134806265): each workflow declares, and the
        relay admits, only events Actions can trigger a workflow with."""
        for path in (TRIGGER, ADMISSION):
            with self.subTest(path.name):
                self.assertLessEqual(set(_load(path)["on"]), ACTIONS_EVENTS)
        condition = str(_load(ADMISSION)["jobs"]["subjects"]["if"])
        (listed,) = re.findall(r"fromJSON\('(\[[^']*\])'\)", condition)
        self.assertLessEqual(set(json.loads(listed)), ACTIONS_EVENTS)

    def test_it_wakes_on_the_events_that_change_a_verdict(self) -> None:
        workflow = _load(TRIGGER)
        self.assertEqual("Merge admission trigger", workflow["name"])
        events = workflow["on"]
        # F1 part 1 (#426 6130207025): the seal changes a verdict too. A thread's
        # resolution has no Actions event (T1, 6134806265), so none is declared.
        self.assertEqual(
            {
                "pull_request",
                "pull_request_review",
                "pull_request_review_comment",
                "issue_comment",
            },
            set(events),
        )
        # CodeAnt on #426: deleting a thread's only comment removes the thread, an
        # unresolved one included, with no resolved or unresolved event.
        self.assertEqual(
            {"created", "deleted"}, set(events["pull_request_review_comment"]["types"])
        )
        # cubic on #426: a draft is denied (M1), so turning one back into a draft
        # changes the verdict.
        # Codex and CodeAnt on #426: closing one of two pull requests at a head ends
        # H1's shared-head failure, so its event wakes the relay, which evaluates the
        # open pull requests left at that head.
        self.assertLessEqual(
            {
                "opened",
                "edited",
                "reopened",
                "synchronize",
                "ready_for_review",
                "converted_to_draft",
                "closed",
            },
            set(events["pull_request"]["types"]),
        )
        self.assertLessEqual(
            {"submitted", "edited", "dismissed"},
            set(events["pull_request_review"]["types"]),
        )
        # A deleted or edited seal must wake the relay as a created one does.
        self.assertEqual(
            {"created", "edited", "deleted"}, set(events["issue_comment"]["types"])
        )

    def test_a_comment_is_relayed_by_its_author_never_by_its_body(self) -> None:
        """The Router's F1: a filter on the body's prefix would miss an edit that
        removes it. The filter is the declarer's identity, as
        `policy/merge-authorities.yaml` declares it, and only an efficiency filter:
        the protected side re-reads the seal."""
        job = _load(TRIGGER)["jobs"]["relay-comment"]
        self.assertEqual(
            "github.event_name == 'issue_comment' && github.event.issue.pull_request"
            f" && github.event.comment.user.login == '{_declarer()}'",
            _normalized(job["if"]),
        )
        self.assertNotIn("body", str(job["if"]))
        (step,) = _steps(job)
        self.assertEqual(UPLOAD_ACTION, step["uses"])
        self.assertEqual("${{ github.event_path }}", step["with"]["path"])
        self.assertEqual(
            "merge-admission-event-${{ github.run_attempt }}", step["with"]["name"]
        )
        self.assertEqual("error", step["with"]["if-no-files-found"])

    def test_the_wake_job_leaves_comments_to_the_relay(self) -> None:
        job = _load(TRIGGER)["jobs"]["wake"]
        self.assertEqual("github.event_name != 'issue_comment'", _normalized(job["if"]))

    def test_it_holds_nothing(self) -> None:
        text = TRIGGER.read_text(encoding="utf-8")
        workflow = _load(TRIGGER)
        self.assertEqual({}, workflow["permissions"])
        self.assertNotIn("secrets.", text)
        self.assertNotIn("pull_request_target", text)
        for name, job in workflow["jobs"].items():
            with self.subTest(job=name):
                self.assertNotIn("environment", job)
                self.assertIn(job.get("permissions", {}), ({},))
                for step in _steps(job):
                    self.assertIn(step.get("uses"), (None, UPLOAD_ACTION))
                    if step.get("uses"):
                        self.assertNotIn("run", step)
                    else:
                        # CodeAnt on #426: the one shell step computes nothing.
                        self.assertEqual(_WAKE, str(step.get("run", "")).strip())


# The trigger's only shell step: it says what the relay does, and computes nothing.
_WAKE = 'echo "The protected relay re-reads this pull request from the provider."'


class DeliveredCommentHintTests(unittest.TestCase):
    """The relayed comment's pull request, parsed once in the shared module of event
    fields, as a hint: it is re-read before anything relies on it."""

    def test_a_pull_request_comment_names_its_number(self) -> None:
        from tools import github_events

        for action in ("created", "edited", "deleted"):
            with self.subTest(action):
                event = {"action": action, "issue": {"number": 426, "pull_request": {}}}
                self.assertEqual(
                    426, github_events.delivered_comment_pull_number(event)
                )

    def test_an_issue_comment_names_none(self) -> None:
        from tools import github_events

        event = {"action": "created", "issue": {"number": 407}}
        self.assertIsNone(github_events.delivered_comment_pull_number(event))

    def test_a_malformed_event_is_refused(self) -> None:
        from tools import github_events

        for name, event in (
            ("not an object", []),
            ("no issue", {}),
            ("a boolean", {"issue": {"number": True, "pull_request": {}}}),
            ("a string", {"issue": {"number": "426", "pull_request": {}}}),
            ("zero", {"issue": {"number": 0, "pull_request": {}}}),
            ("a list pull request", {"issue": {"number": 426, "pull_request": []}}),
        ):
            with self.subTest(name), self.assertRaises(ValueError):
                github_events.delivered_comment_pull_number(event)


class AdmissionWorkflowTests(unittest.TestCase):
    """The privileged relay: protected main only, events as hints only."""

    def test_its_events(self) -> None:
        workflow = _load(ADMISSION)
        self.assertEqual("Merge admission", workflow["name"])
        events = workflow["on"]
        self.assertEqual(
            {"workflow_run", "schedule", "workflow_dispatch", "repository_dispatch"},
            set(events),
        )
        # The guarded merge's dispatch is admitted by its one type alone (G1).
        self.assertEqual(
            ["gnostoa-merge-admission"], events["repository_dispatch"]["types"]
        )
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

    def test_each_job_s_condition_is_exactly_its_own(self) -> None:
        """Rule 7, Kilo's failed selection and the trigger's conclusion, pinned whole:
        `workflow_run` matches by name, so the path and the event are admitted
        explicitly, and only a successful trigger run counts."""
        jobs = _load(ADMISSION)["jobs"]
        for name, expected in (
            ("subjects", SUBJECTS_IF),
            ("invalidate", INVALIDATE_IF),
            ("readback", AFTER_INVALIDATION_IF),
            ("admit", AFTER_INVALIDATION_IF),
        ):
            with self.subTest(job=name):
                self.assertEqual(expected, _normalized(jobs[name]["if"]))

    def test_permissions_are_granted_per_job(self) -> None:
        """SonarCloud S8264 on #426: the workflow grants nothing, and each job only
        the reads it needs. Only `subjects` reads another run's artifact (the
        relayed comment), and `admit` reads no Actions state (cubic r4251444300)."""
        workflow = _load(ADMISSION)
        self.assertEqual({}, workflow["permissions"])
        jobs = workflow["jobs"]
        self.assertEqual(
            {"contents": "read", "pull-requests": "read", "actions": "read"},
            jobs["subjects"]["permissions"],
        )
        self.assertEqual({"contents": "read"}, jobs["invalidate"]["permissions"])
        self.assertNotIn("actions", jobs["admit"]["permissions"])
        for name, job in jobs.items():
            with self.subTest(job=name):
                self.assertTrue(job.get("permissions"))

    def test_the_relayed_comment_is_downloaded_from_its_trigger_run(self) -> None:
        steps = _steps(_load(ADMISSION)["jobs"]["subjects"])
        (download,) = [s for s in steps if s.get("uses") == DOWNLOAD_ACTION]
        self.assertEqual(
            "github.event_name == 'workflow_run'"
            " && github.event.workflow_run.event == 'issue_comment'",
            _normalized(download["if"]),
        )
        self.assertEqual(
            "merge-admission-event-${{ github.event.workflow_run.run_attempt }}",
            download["with"]["name"],
        )
        self.assertEqual(
            "${{ github.event.workflow_run.id }}", download["with"]["run-id"]
        )
        self.assertEqual("${{ github.token }}", download["with"]["github-token"])
        self.assertEqual(
            "${{ runner.temp }}/gnostoa-merge-admission-relay", download["with"]["path"]
        )

    def test_every_handoff_is_scoped_to_its_run_attempt(self) -> None:
        """Codex on #426: a re-run keeps the workflow run and increments its attempt,
        and an artifact's name cannot be reused within the run. Every handoff names its
        attempt, so no upload collides with an earlier attempt's, and no attempt reads
        another's invalidation record, readback or comment event."""
        jobs = _load(ADMISSION)["jobs"]
        handoffs = [
            str(step["with"]["name"])
            for job in jobs.values()
            for step in _steps(job)
            if step.get("uses") in (UPLOAD_ACTION, DOWNLOAD_ACTION)
        ]
        self.assertEqual(5, len(handoffs))
        for name in handoffs:
            with self.subTest(name=name):
                attempt = (
                    "-${{ github.event.workflow_run.run_attempt }}"
                    if name.startswith("merge-admission-event")
                    else "-${{ github.run_attempt }}"
                )
                self.assertTrue(name.endswith(attempt), name)
        (relayed,) = [
            step
            for step in _steps(_load(TRIGGER)["jobs"]["relay-comment"])
            if step.get("uses") == UPLOAD_ACTION
        ]
        self.assertEqual(
            "merge-admission-event-${{ github.run_attempt }}", relayed["with"]["name"]
        )
        (readback,) = [
            step
            for step in _steps(_load(READBACK)["jobs"]["readback"])
            if step.get("name") == "Upload non-secret analyzer readback"
        ]
        # The readback's secret-free resolver names it: the admission point's call
        # names its attempt; a readback of its own keeps the name its readers use.
        self.assertEqual(
            "${{ steps.subject.outputs.artifact }}", readback["with"]["name"]
        )
        (resolve,) = [
            step
            for step in _steps(_load(READBACK)["jobs"]["readback"])
            if step.get("id") == "subject"
        ]
        self.assertEqual("${{ github.run_attempt }}", resolve["env"]["RUN_ATTEMPT"])
        resolver = _readback_resolver()
        subject = {"pull_number": "300", "head": HEAD}
        self.assertEqual(
            f"gnostoa-analyzer-readback-300-{HEAD}-2",
            resolver.artifact(
                {"EVENT_NAME": "workflow_call", "RUN_ATTEMPT": "2"}, subject
            ),
        )
        self.assertEqual(
            f"gnostoa-analyzer-readback-300-{HEAD}",
            resolver.artifact(
                {"EVENT_NAME": "workflow_run", "RUN_ATTEMPT": "2"}, subject
            ),
        )
        for attempt in ("", "0", "02", "2\n", "two"):
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):
                resolver.artifact(
                    {"EVENT_NAME": "workflow_call", "RUN_ATTEMPT": attempt}, subject
                )
        self.assertIn(
            "gnostoa-analyzer-readback-${{ matrix.subject.pull_number }}"
            "-${{ matrix.subject.head }}-${{ github.run_attempt }}",
            handoffs,
        )

    def test_the_guard_waits_as_long_as_the_admission_may_run(self) -> None:
        """CodeAnt on #426: the guard's deadline covers the admission's critical path,
        each job's own limit, so a deadline refusal means the run did not complete
        within its limits, never that a valid run was still finishing."""
        import importlib.util
        import inspect

        jobs = _load(ADMISSION)["jobs"]
        (call,) = _load(READBACK)["jobs"].values()
        path = sum(
            int(jobs[name]["timeout-minutes"])
            for name in ("subjects", "invalidate", "admit")
        ) + int(call["timeout-minutes"])
        spec = importlib.util.spec_from_file_location(
            "gnostoa_guard_deadline", ROOT / "ci" / "merge_admission_guard.py"
        )
        if spec is None or spec.loader is None:
            raise AssertionError("the guard is unavailable")
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        default = inspect.signature(guard.guard).parameters["deadline_seconds"].default
        self.assertGreaterEqual(default, path * 60)

    def test_invalidation_precedes_every_acquisition(self) -> None:
        jobs = _load(ADMISSION)["jobs"]
        self.assertEqual("subjects", jobs["invalidate"]["needs"])
        self.assertEqual(["subjects", "invalidate"], jobs["readback"]["needs"])
        self.assertEqual(["subjects", "invalidate", "readback"], jobs["admit"]["needs"])
        record = [
            s for s in _steps(jobs["invalidate"]) if s.get("uses") == UPLOAD_ACTION
        ]
        self.assertEqual(1, len(record))
        self.assertEqual(
            "gnostoa-merge-admission-pending-${{ matrix.subject.pull_number }}"
            "-${{ matrix.subject.head }}-${{ github.run_attempt }}",
            record[0]["with"]["name"],
        )
        fetched = [
            s
            for s in _steps(jobs["admit"])
            if s.get("uses") == DOWNLOAD_ACTION
            and str(s["with"]["name"]).startswith("gnostoa-merge-admission-pending-")
        ]
        self.assertEqual(1, len(fetched))
        self.assertEqual(record[0]["with"]["name"], fetched[0]["with"]["name"])
        self.assertNotIn("run-id", fetched[0]["with"])

    def test_the_dispatch_nonce_reaches_both_app_jobs_as_data(self) -> None:
        """The nonce leaves `subjects` as an output and reaches the two jobs that hold
        the App through the environment, never through an expression in a script."""
        jobs = _load(ADMISSION)["jobs"]
        self.assertEqual(
            "${{ steps.subjects.outputs.nonce }}", jobs["subjects"]["outputs"]["nonce"]
        )
        for job, name in (
            ("invalidate", "Invalidate a standing success on the exact head"),
            ("admit", "Publish the verdict on the exact head"),
        ):
            with self.subTest(job=job):
                (step,) = [s for s in _steps(jobs[job]) if s.get("name") == name]
                self.assertEqual(
                    "${{ needs.subjects.outputs.nonce }}", step["env"]["DISPATCH_NONCE"]
                )
                self.assertNotIn("nonce }}", str(step.get("run")))

    def test_a_failed_evaluation_still_completes_the_run(self) -> None:
        steps = _steps(_load(ADMISSION)["jobs"]["admit"])
        (publish,) = [
            s for s in steps if s.get("name") == "Publish the verdict on the exact head"
        ]
        self.assertEqual("${{ !cancelled() }}", publish["if"])

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

    def test_only_the_publishing_jobs_hold_the_dedicated_app(self) -> None:
        jobs = _load(ADMISSION)["jobs"]
        holders = {
            name: job
            for name, job in jobs.items()
            if job.get("environment") == "gnostoa-ma0"
        }
        self.assertEqual({"invalidate", "admit"}, set(holders))
        gates = {
            # cubic on #426: without the App's id no token is minted (the shadow).
            "invalidate": "${{ vars.GNOSTOA_MA0_APP_ID != '' }}",
            "admit": "${{ !cancelled() && vars.GNOSTOA_MA0_APP_ID != '' }}",
        }
        for name, job in holders.items():
            with self.subTest(job=name):
                minting = [s for s in _steps(job) if s.get("uses") == APP_MINT_ACTION]
                self.assertEqual(1, len(minting))
                inputs = minting[0].get("with", {})
                permissions = {
                    k: v for k, v in inputs.items() if k.startswith("permission-")
                }
                self.assertEqual({"permission-checks": "write"}, permissions)
                self.assertEqual(gates[name], minting[0].get("if"))
        for other_name, other in jobs.items():
            if other_name in holders:
                continue
            with self.subTest(job=other_name):
                text = str(other)
                self.assertNotIn(APP_MINT_ACTION, text)
                # CodeAnt on #426: nor the App's key, id or token by any other route.
                self.assertNotIn("secrets.", text)
                self.assertNotIn("GNOSTOA_MA0", text)
                self.assertNotIn("steps.token", text)
        relays = {
            "invalidate": "Invalidate a standing success on the exact head",
            "admit": "Publish the verdict on the exact head",
        }
        for name, job in holders.items():
            for step in _steps(job):
                with self.subTest(job=name, step=step.get("name")):
                    if "secrets." in str(step):
                        self.assertEqual(APP_MINT_ACTION, step.get("uses"))
                    if "steps.token" in str(step):
                        self.assertEqual(relays[name], step.get("name"))

    def test_checkouts_take_main_without_credentials(self) -> None:
        for name, job in _load(ADMISSION)["jobs"].items():
            for step in _steps(job):
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    with self.subTest(job=name):
                        self.assertNotIn("ref", step.get("with", {}))
                        self.assertIs(False, step["with"]["persist-credentials"])

    def test_it_runs_main_s_own_commands(self) -> None:
        """cubic on #426: each exact invocation is an executable line of the step
        that owns it, not a substring anywhere in the file."""
        jobs = _load(ADMISSION)["jobs"]
        expected = {
            ("subjects", "Select the subjects"): (
                "--mode subjects",
                'hint="$(PYTHONPATH=. python ci/merge_admission_relay.py hint)"',
                'args+=(--pull-number "${hint}")',
                'dispatched="$(PYTHONPATH=. python ci/merge_admission_relay.py dispatch-hint)"',
                'args+=(--pull-number "${dispatched% *}")',
                'printf \'nonce=%s\\n\' "${dispatched#* }" >> "${GITHUB_OUTPUT}"',
                # An event run never falls back to the sweep, and a pull request's
                # event names the open pull requests at its head (CodeAnt on #426).
                'if [[ "${EVENT_NAME}" == "workflow_run"'
                ' || "${EVENT_NAME}" == "repository_dispatch" ]]; then',
                "args+=(--event)",
                'if [[ "${EVENT_NAME}" == "workflow_run"'
                ' && "${TRIGGER_EVENT:-}" != "issue_comment" ]]; then',
                'args+=(--workflow-run-head-sha "${WORKFLOW_RUN_HEAD_SHA}")',
                'PYTHONPATH=. python ci/review_github_current_state.py "${args[@]}"',
            ),
            ("invalidate", "Invalidate a standing success on the exact head"): (
                "PYTHONPATH=. python ci/merge_admission_relay.py invalidate \\",
            ),
            ("admit", "Evaluate the exact subject"): (
                "PYTHONPATH=. python ci/review_github_current_state.py"
                " --mode merge-evidence \\",
                "&& PYTHONPATH=. python ci/review_github_current_state.py"
                " --mode open-heads \\",
                "&& PYTHONPATH=. python -m tools.cli merge-evidence --project-root ."
                ' "${bundle[@]}" \\',
                "PYTHONPATH=. python -m tools.cli merge-admission --project-root . \\",
                "PYTHONPATH=. python -m tools.cli merge-evidence --project-root . \\",
            ),
            ("admit", "Publish the verdict on the exact head"): (
                "PYTHONPATH=. python ci/merge_admission_relay.py publish \\",
            ),
        }
        for (job, name), lines in expected.items():
            steps = [step for step in _steps(jobs[job]) if step.get("name") == name]
            self.assertEqual(1, len(steps), name)
            executable = _run_lines(steps[0])
            for line in lines:
                with self.subTest(step=name, line=line):
                    self.assertIn(line, executable)
        text = ADMISSION.read_text(encoding="utf-8")
        self.assertNotIn("pull_request_target", text)
        # No path reaches the relay from the command line (SonarCloud S8707).
        for job, name in (
            ("invalidate", "Invalidate a standing success on the exact head"),
            ("admit", "Publish the verdict on the exact head"),
        ):
            (step,) = [s for s in _steps(jobs[job]) if s.get("name") == name]
            for line in _run_lines(step):
                for option in (
                    "--work-dir",
                    "--evaluated",
                    "--current",
                    "--verdict ",
                    "--output",
                ):
                    with self.subTest(step=name, option=option):
                        self.assertNotIn(option, line)


class ActivationRunbookTests(unittest.TestCase):
    """The owner's activation steps in the merge-gate runbook (#407, MA0 1b.4)."""

    @staticmethod
    def _section() -> str:
        text = RUNBOOK.read_text(encoding="utf-8")
        return text.split("### Merge admission (MA0 1b.4)", 1)[1].split("\n### ", 1)[0]

    @classmethod
    def _steps(cls) -> dict[str, str]:
        """Each numbered owner operation with its indented lines."""
        section = cls._section().split("**Owner operations.**", 1)[1]
        steps: dict[str, str] = {}
        current = ""
        for line in section.splitlines():
            match = re.match(r"(\d+)\. ", line)
            if match:
                current = match.group(1)
                steps[current] = line
            elif current and line.startswith(" "):
                steps[current] += "\n" + line
        return steps

    def test_the_credentials_are_the_environment_s(self) -> None:
        """cubic on #426: a repository secret reaches every branch's workflows, the
        `gnostoa-ma0` environment's only main's."""
        step = self._steps()["3"]
        self.assertIn("environment variable `GNOSTOA_MA0_APP_ID`", step)
        self.assertIn("environment secret `GNOSTOA_MA0_PRIVATE_KEY`", step)

    def test_routing_the_rerun_case_does_not_resolve_it(self) -> None:
        """The PAO on #426 (6130135014). Added after round 1's change to step 5, as a
        regression guard: it is not that change's pre-change evidence."""
        step = self._steps()["5"]
        self.assertNotIn("or explicitly routed", step)
        self.assertIn("**the owner explicitly chooses**", step)
        self.assertIn("activation stays pending", step)

    def test_activation_waits_for_the_live_proofs_f1_names(self) -> None:
        """The Router's F1: a same-named pending run is no proof by itself that
        GitHub stopped using an older success, and the dispatch's run id is not yet
        exercised here. Both are read back natively before activation."""
        step = self._steps()["4"]
        self.assertIn("a pending run over an older success", step)
        self.assertIn("App-pinned", step)
        # G1: the dispatch names no run; its nonce, in the run's record, does.
        self.assertIn("nonce", step)
        self.assertIn("`repository_dispatch`", step)

    def test_the_launch_says_what_runs_at_the_guard_s_startup(self) -> None:
        """CodeAnt on #426: `-I` still runs the environment's `.pth` startup hooks, such
        as the pinned coverage package's, so the launch's text names them rather than
        claiming nothing runs."""
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertNotIn("so no file runs\n  at its startup", text)
        self.assertIn("`.pth` startup hooks", text)

    def test_the_merge_after_activation_obtains_its_own_admission(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        procedure = text.split("## Procedure", 1)[1]
        step8 = procedure.split("8. **The merge.**", 1)[1].split("\n9. ", 1)[0]
        self.assertIn("guard_merge --repository", step8)
        guard = step8.index("guard_merge --repository")
        self.assertLess(guard, step8.rindex("--match-head-commit"))
        # The launch it names runs the guard (Credentials; the PAO on #426).
        launch = text.split("  guard_merge() {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn('"$created/venv/bin/python" -I -B', launch)
        self.assertIn("ci/merge_admission_guard.py", launch)


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


def _readback_resolver() -> Any:
    """The readback's secret-free subject resolver, loaded from its file."""
    import importlib.util

    path = ROOT / "ci" / "analyzer_readback_subject.py"
    spec = importlib.util.spec_from_file_location("gnostoa_readback_subject", path)
    if spec is None or spec.loader is None:
        raise AssertionError("readback subject resolver is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReadbackSubjectTests(unittest.TestCase):
    """The admission run's call names its subject through the inputs, as an owner's
    dispatch does; the runner still re-reads the Pull Request."""

    def test_a_call_resolves_its_inputs(self) -> None:
        resolver = _readback_resolver()
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
        resolver = _readback_resolver()
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

    @staticmethod
    def _run(module: Any, replies: dict[str, Any], *argv: str) -> int:
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

    @staticmethod
    def _open(number: int, head: str, *, base: str = "main") -> dict[str, Any]:
        return {
            "number": number,
            "state": "open",
            "html_url": f"https://github.com/ktogias/gnostoa/pull/{number}",
            "head": {"sha": head, "repo": {"full_name": "someone/fork"}},
            "base": {"sha": "b" * 40, "ref": base},
        }

    def test_open_heads_reads_the_whole_population_with_each_head(self) -> None:
        """H1 (#426 6131149850): every open pull request of the repository, whatever
        its author, fork or target, from L1's one enumeration, every page read."""
        module = adapter_fixture()
        first = [self._open(n, f"{n:040x}") for n in range(1, 101)]
        second = [self._open(426, HEAD, base="release")]
        listing = f"{API}/pulls?state=open&per_page=100"
        replies = {
            listing: (first, {"link": f'<{listing}&page=2>; rel="next"'}),
            f"{listing}&page=2": (second, {}),
        }
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "population.json"
            code = self._run(
                module,
                replies,
                "--mode",
                "open-heads",
                "--repository",
                "ktogias/gnostoa",
                "--output",
                str(output),
            )
            self.assertEqual(0, code)
            population = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("COMPLETE", population["coverage"])
        pulls = population["pulls"]
        self.assertEqual(101, len(pulls))
        self.assertEqual({"pull_number": 426, "head": HEAD}, pulls[-1])
        self.assertEqual(
            sorted(p["pull_number"] for p in pulls), [p["pull_number"] for p in pulls]
        )
        # The sweep's projection of the same enumeration is unchanged.
        self.assertEqual(
            [*range(1, 101), 426],
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            module._open_pull_numbers(paged_fake_fixture(replies), "ktogias/gnostoa"),
        )

    def test_the_sweep_keeps_a_repeated_number_once(self) -> None:
        """The Router's H1: the sweep's projection of the one enumeration is
        unchanged, so a number an overlapping page repeats is kept once there, while
        the population refuses a number listed at two heads."""
        module = adapter_fixture()
        listing = f"{API}/pulls?state=open&per_page=100"
        replies: dict[str, tuple[Any, dict[str, str]]] = {
            listing: ([self._open(1, HEAD), self._open(1, "c" * 40)], {})
        }
        self.assertEqual(
            [1],
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            module._open_pull_numbers(paged_fake_fixture(replies), "ktogias/gnostoa"),
        )
        fake = paged_fake_fixture(replies)
        with self.assertRaises(module.ProviderReadError):
            # skipcq: PYL-W0212 -- intentional white-box L1 test
            module._open_pulls(fake, "ktogias/gnostoa")

    def test_open_heads_refuses_an_incomplete_or_conflicting_population(self) -> None:
        module = adapter_fixture()
        listing = f"{API}/pulls?state=open&per_page=100"
        broken = self._open(2, "c" * 40)
        broken["head"] = {"sha": "short"}
        for name, items in (
            ("a malformed item", [self._open(1, HEAD), broken]),
            ("a repeated number", [self._open(1, HEAD), self._open(1, "c" * 40)]),
        ):
            with self.subTest(name), tempfile.TemporaryDirectory() as raw:
                output = Path(raw) / "population.json"
                code = self._run(
                    module,
                    {listing: (items, {})},
                    "--mode",
                    "open-heads",
                    "--repository",
                    "ktogias/gnostoa",
                    "--output",
                    str(output),
                )
                self.assertNotEqual(0, code)
                self.assertFalse(output.exists())

    def _subjects(self, replies: dict[str, Any], *argv: str) -> tuple[int, Any]:
        module = adapter_fixture()
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "subjects.json"
            code = self._run(
                module,
                replies,
                "--mode",
                "subjects",
                "--repository",
                "ktogias/gnostoa",
                *argv,
                "--output",
                str(output),
            )
            written = (
                json.loads(output.read_text(encoding="utf-8"))
                if output.exists()
                else None
            )
        return code, written

    def test_an_unreadable_pull_request_refuses_cleanly(self) -> None:
        """Claude and CodeAnt on #426: a pull request that reads back malformed
        refuses `subjects` and `merge-evidence` with a clean message, as
        `open-heads` does, never a traceback; nothing is written."""
        replies = _replies()
        broken = copy.deepcopy(replies[f"{API}/pulls/300"][0])
        broken["head"] = {"sha": "short"}
        replies[f"{API}/pulls/300"] = (broken, {})
        for mode in ("subjects", "merge-evidence"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as raw:
                output = Path(raw) / "out.json"
                code = self._run(
                    adapter_fixture(),
                    replies,
                    "--mode",
                    mode,
                    "--repository",
                    "ktogias/gnostoa",
                    "--pull-number",
                    "300",
                    "--output",
                    str(output),
                )
                self.assertNotEqual(0, code)
                self.assertFalse(output.exists())

    def test_an_unreadable_open_listing_refuses_the_sweep_cleanly(self) -> None:
        """CodeAnt on #426: the scheduled sweep's listing, read back malformed,
        refuses `subjects` with a clean message too; nothing is written."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        broken = self._open(300, HEAD)
        broken["head"] = {"sha": "short"}
        replies[listing] = ([broken], {})
        code, written = self._subjects(replies)
        self.assertNotEqual(0, code)
        self.assertIsNone(written)

    def test_l1_imports_without_the_runtime_dependencies(self) -> None:
        """CodeAnt on #426: L1's `publish` job installs no runtime lock, so L1 imports
        nothing that needs PyYAML or jsonschema at module level; the merge-evidence
        mode, which runs where the lock is installed, imports its bound itself."""
        import subprocess  # nosec B404 -- the test's own interpreter

        probe = (
            "import sys\n"
            "sys.modules['yaml'] = None\n"
            "sys.modules['jsonschema'] = None\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "import ci.review_github_current_state\n"
        )
        completed = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [sys.executable, "-I", "-c", probe],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr[-500:])

    def test_a_fork_s_event_selects_the_open_pull_requests_at_its_head(self) -> None:
        """CodeAnt on #426: GitHub leaves a fork's pull request out of the trigger
        run's `pull_requests` (github/docs#22501, expected behavior). An event run's
        subjects are its hints and every open pull request at the trigger run's own
        head, whatever the hour: never a sweep batch that may omit it."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        others = [self._open(number, "c" * 40) for number in range(301, 310)]
        replies[listing] = ([*others, self._open(300, HEAD)], {})
        code, written = self._subjects(
            replies,
            "--event",
            "--workflow-run-pulls-json",
            "[]",
            "--workflow-run-head-sha",
            HEAD,
        )
        self.assertEqual(0, code)
        self.assertEqual([{"pull_number": 300, "head": HEAD}], written)

    def test_an_event_run_never_falls_back_to_the_sweep(self) -> None:
        """An event that names no pull request, and no head with one, has no
        subject; the schedule sweeps."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        replies[listing] = ([self._open(300, HEAD)], {})
        self.assertEqual(
            (0, []),
            self._subjects(replies, "--event", "--workflow-run-pulls-json", "[]"),
        )
        self.assertEqual(
            (0, []),
            self._subjects(
                replies,
                "--event",
                "--workflow-run-pulls-json",
                "[]",
                "--workflow-run-head-sha",
                "c" * 40,
            ),
        )

    def test_an_event_evaluates_one_subject_per_head(self) -> None:
        """CodeAnt and Claude on #426: a check run belongs to a commit, so one
        subject evaluates it for every pull request at that head, and H1's failure
        names them all when it is shared. However many share a head, nothing aborts
        before the head is evaluated; a hinted pull request is the one chosen."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        replies[listing] = ([self._open(n, HEAD) for n in range(300, 312)], {})
        replies[f"{API}/pulls/305"] = (self._open(305, HEAD), {})
        self.assertEqual(
            (0, [{"pull_number": 300, "head": HEAD}]),
            self._subjects(replies, "--event", "--workflow-run-head-sha", HEAD),
        )
        self.assertEqual(
            (0, [{"pull_number": 305, "head": HEAD}]),
            self._subjects(
                replies,
                "--event",
                "--pull-number",
                "305",
                "--workflow-run-head-sha",
                HEAD,
            ),
        )

    def test_a_hint_the_listing_does_not_show_yet_is_kept(self) -> None:
        """A hinted pull request the open listing does not yet show keeps its own
        place, and is re-read like every subject."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        replies[listing] = ([self._open(300, HEAD)], {})
        replies[f"{API}/pulls/307"] = (self._open(307, "c" * 40), {})
        self.assertEqual(
            (
                0,
                [
                    {"pull_number": 307, "head": "c" * 40},
                    {"pull_number": 300, "head": HEAD},
                ],
            ),
            self._subjects(
                replies,
                "--event",
                "--pull-number",
                "307",
                "--workflow-run-head-sha",
                HEAD,
            ),
        )

    def test_a_closed_peer_s_event_evaluates_the_survivor_at_its_head(self) -> None:
        """A `closed` event names the closed pull request, which L1 drops, and the
        trigger run's head, where the survivor is: the survivor is the subject."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        replies[listing] = ([self._open(300, HEAD)], {})
        closed = self._open(301, HEAD)
        closed["state"] = "closed"
        replies[f"{API}/pulls/301"] = (closed, {})
        self.assertEqual(
            (0, [{"pull_number": 300, "head": HEAD}]),
            self._subjects(
                replies,
                "--event",
                "--workflow-run-pulls-json",
                json.dumps([{"number": 301, "head": {"sha": HEAD}}]),
                "--workflow-run-head-sha",
                HEAD,
            ),
        )

    def test_an_event_s_subjects_stay_within_the_bounded_capacity(self) -> None:
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        heads = [f"{n:040x}" for n in range(300, 309)]
        replies[listing] = (
            [
                self._open(n, head)
                for n, head in zip(range(300, 309), heads, strict=True)
            ],
            {},
        )
        hints = [
            argument for n in range(300, 309) for argument in ("--pull-number", str(n))
        ]
        code, written = self._subjects(replies, "--event", *hints)
        self.assertNotEqual(0, code)
        self.assertIsNone(written)

    def test_an_unreadable_population_refuses_cleanly(self) -> None:
        """Claude on #426: an event's population read that GitHub contradicts
        refuses with the same clean message `open-heads` gives, never a traceback."""
        replies = _replies()
        listing = f"{API}/pulls?state=open&per_page=100"
        replies[listing] = ([self._open(300, HEAD), self._open(300, "c" * 40)], {})
        code, written = self._subjects(
            replies, "--event", "--workflow-run-head-sha", HEAD
        )
        self.assertNotEqual(0, code)
        self.assertIsNone(written)

    def test_a_malformed_trigger_head_refuses(self) -> None:
        for head in ("", "C" * 40, "c" * 39, f"{'c' * 40}\n"):
            with self.subTest(head=head):
                code, written = self._subjects(
                    _replies(), "--event", "--workflow-run-head-sha", head
                )
                self.assertNotEqual(0, code)
                self.assertIsNone(written)

    def test_the_selection_passes_the_trigger_run_s_head(self) -> None:
        (step,) = [
            step
            for step in _steps(_load(ADMISSION)["jobs"]["subjects"])
            if step.get("name") == "Select the subjects"
        ]
        self.assertEqual(
            "${{ github.event.workflow_run.head_sha }}",
            step["env"]["WORKFLOW_RUN_HEAD_SHA"],
        )

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
