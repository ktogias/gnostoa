from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
import importlib
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.check_change_policy import load_change_policy
from tools.cli import main as cli_main
from tools.knowledge_common import KnowledgeFormatError, load_yaml, parse_markdown


ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "plans" / "issue-3-durable-task-context.yaml"


class TaskContextContractTests(unittest.TestCase):
    def test_generic_contract_and_routes_are_public(self) -> None:
        expected = (
            ROOT / "schemas" / "execution-plan.schema.json",
            ROOT / "templates" / "execution-plan.project.yaml",
            ROOT / "guidance" / "workflows" / "resume-and-handoff-change.md",
        )
        self.assertTrue(all(path.is_file() for path in expected), expected)

        policy = load_change_policy(ROOT / "core" / "change-control.yaml")
        self.assertTrue(policy["continuity"]["resume_reconciliation_required"])
        self.assertTrue(
            policy["continuity"]["unfinished_handoff_checkpoint_required"]
        )
        self.assertFalse(policy["continuity"]["raw_activity_log_canonical"])
        self.assertEqual(
            "when-needed",
            policy["change_classes"]["normal"]["execution_plan"],
        )

        router = (ROOT / "templates" / "AGENTS.project.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("resume-and-handoff-change.md", router)
        boundary = (
            ROOT / "knowledge" / "contracts" / "public-inheritance-surface.md"
        ).read_text(encoding="utf-8")
        self.assertIn("`change-lifecycle` Agent", boundary)

    def test_gnostoa_specialization_requires_proportionate_plans(self) -> None:
        policy = load_change_policy(ROOT / "policy" / "change-control.yaml")
        self.assertEqual(
            "optional",
            policy["change_classes"]["mechanical"]["execution_plan"],
        )
        self.assertEqual(
            "when-needed",
            policy["change_classes"]["normal"]["execution_plan"],
        )
        for class_id in ("normative", "critical"):
            self.assertEqual(
                "required",
                policy["change_classes"][class_id]["execution_plan"],
                class_id,
            )

    def test_execution_plan_requirement_cannot_weaken_its_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            child = Path(directory) / "child.yaml"
            parent = (ROOT / "policy" / "change-control.yaml").resolve()
            child.write_text(
                f"""
id: weakening-plan-child
version: "0.1.0"
owner: team:example-maintainers
extends:
  - {str(parent)!r}
change_classes:
  normative:
    execution_plan: optional
""".lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(KnowledgeFormatError):
                load_change_policy(child)

    def test_cross_agent_skill_and_provider_adapters_are_bounded(self) -> None:
        skill = ROOT / ".agents" / "skills" / "change-lifecycle" / "SKILL.md"
        agent = skill.parent / "agents" / "openai.yaml"
        issue_form = ROOT / ".github" / "ISSUE_TEMPLATE" / "change.yml"
        pull_request = ROOT / ".github" / "pull_request_template.md"
        copilot = ROOT / ".github" / "copilot-instructions.md"
        for path in (skill, agent, issue_form, pull_request, copilot):
            self.assertTrue(path.is_file(), path)

        skill_document = parse_markdown(skill, ROOT)
        self.assertEqual("change-lifecycle", skill_document.metadata["name"])
        self.assertTrue(skill_document.metadata["description"].strip())
        self.assertTrue(skill_document.body.strip())

        agent_config = load_yaml(agent)["interface"]
        self.assertEqual("Change Lifecycle", agent_config["display_name"])
        self.assertIn("$change-lifecycle", agent_config["default_prompt"])

        copilot_text = copilot.read_text(encoding="utf-8")
        self.assertIn("AGENTS.md", copilot_text)
        self.assertIn("change-lifecycle", copilot_text)
        self.assertLessEqual(len(copilot_text.splitlines()), 24)

        issue_form = load_yaml(issue_form)
        field_ids = [
            item["id"]
            for item in issue_form["body"]
            if isinstance(item, dict) and "id" in item
        ]
        self.assertEqual(len(field_ids), len(set(field_ids)))

    def test_active_plan_omits_machine_local_tool_paths(self) -> None:
        plan_text = PLAN.read_text(encoding="utf-8")
        for prefix in ("/home/", "/Users/"):
            self.assertNotIn(prefix, plan_text)
        self.assertNotRegex(plan_text, r"[A-Za-z]:\\Users\\")

    def test_github_adapter_checks_the_pull_request_candidate(self) -> None:
        module = importlib.import_module("tools.task_context")
        plan = module.load_execution_plan(PLAN)
        revision = "a" * 40
        event = {
            "pull_request": {
                "body": module.render_change_request_context(plan, revision),
                "head": {
                    "ref": plan["repository"]["branch"],
                    "sha": revision,
                },
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / ".github" / "check_task_context.py"),
                    "--event",
                    str(event_path),
                    "--repository-root",
                    str(ROOT),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(0, result.returncode, result.stderr)

        workflow = (
            ROOT / ".github" / "workflows" / "verification.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("check_task_context.py", workflow)

    def test_github_adapter_requires_a_plan_for_normative_changes(self) -> None:
        event = {
            "pull_request": {
                "body": "- Class: `normative`\n",
                "head": {
                    "ref": "change/normative-example",
                    "sha": "b" * 40,
                },
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            event_path = root / "event.json"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / ".github" / "check_task_context.py"),
                    "--event",
                    str(event_path),
                    "--repository-root",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(1, result.returncode)
        self.assertIn("requires an active Execution Plan", result.stderr)

    def test_container_first_task_commands_have_a_pinned_git_runtime(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("ARG GIT_PACKAGE_VERSION=", dockerfile)
        self.assertIn('"git=${GIT_PACKAGE_VERSION}"', dockerfile)


class TaskContextToolTests(unittest.TestCase):
    @staticmethod
    def module():
        return importlib.import_module("tools.task_context")

    def test_active_gnostoa_plan_is_schema_valid(self) -> None:
        issues = self.module().validate_execution_plan(PLAN, ROOT)
        self.assertEqual([], issues)

    def test_anonymous_project_template_is_schema_valid(self) -> None:
        template = ROOT / "templates" / "execution-plan.project.yaml"
        issues = self.module().validate_execution_plan(template, ROOT)
        self.assertEqual([], issues)

    def test_unified_cli_validates_an_execution_plan(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            result = cli_main(
                [
                    "task",
                    "validate",
                    "--plan",
                    str(PLAN),
                    "--repository-root",
                    str(ROOT),
                ]
            )
        self.assertEqual(0, result)
        self.assertIn("execution plan is valid", output.getvalue())

    def test_reconciliation_detects_branch_and_worktree_drift(self) -> None:
        module = self.module()
        plan = module.load_execution_plan(PLAN)
        expected = deepcopy(plan)
        expected["repository"]["branch"] = "change/example"
        expected["handoff"]["expected_worktree"] = ["known.txt"]

        issues = module.reconcile_execution_plan(
            expected,
            branch="change/other",
            changed_paths={"known.txt", "unexpected.txt"},
            require_clean=False,
            base_is_ancestor=False,
        )
        self.assertTrue(any("branch" in issue for issue in issues), issues)
        self.assertTrue(any("unexpected.txt" in issue for issue in issues), issues)
        self.assertTrue(any("base revision" in issue for issue in issues), issues)

    def test_plan_file_is_implicit_during_a_local_checkpoint(self) -> None:
        module = self.module()
        plan = deepcopy(module.load_execution_plan(PLAN))
        plan["handoff"]["expected_worktree"] = []
        plan_path = PLAN.relative_to(ROOT).as_posix()
        issues = module.reconcile_execution_plan(
            plan,
            branch=plan["repository"]["branch"],
            changed_paths={plan_path},
            require_clean=False,
            implicit_expected_paths={plan_path},
        )
        self.assertEqual([], issues)

    def test_repository_state_expands_untracked_directories_to_files(self) -> None:
        module = self.module()
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(
                ["git", "init", str(repository)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repository),
                    "-c",
                    "user.name=Example Maintainer",
                    "-c",
                    "user.email=maintainer@example.invalid",
                    "commit",
                    "--allow-empty",
                    "-m",
                    "baseline",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            nested = repository / "plans" / "active" / "example.yaml"
            nested.parent.mkdir(parents=True)
            nested.write_text("status: planned\n", encoding="utf-8")

            _, _, changed_paths = module.repository_state(repository)
        self.assertEqual({"plans/active/example.yaml"}, changed_paths)

    def test_git_trust_is_scoped_to_the_selected_repository(self) -> None:
        module = self.module()
        command = module._git_command(ROOT, "status", "--short")
        self.assertIn(f"safe.directory={ROOT.resolve()}", command)
        self.assertNotIn("safe.directory=*", command)

    def test_change_request_projection_rejects_a_stale_revision(self) -> None:
        module = self.module()
        plan = module.load_execution_plan(PLAN)
        candidate = "a" * 40
        body = module.render_change_request_context(plan, candidate)
        self.assertIn("<!-- task-context:start -->", body)
        self.assertEqual(
            [],
            module.check_change_request_context(plan, body, candidate),
        )

        issues = module.check_change_request_context(plan, body, "b" * 40)
        self.assertTrue(any("candidate revision" in issue for issue in issues))

    def test_handoff_requires_a_clean_committed_checkpoint(self) -> None:
        module = self.module()
        plan = module.load_execution_plan(PLAN)
        plan["handoff"]["status"] = "ready"
        plan["handoff"]["expected_worktree"] = []

        issues = module.reconcile_execution_plan(
            plan,
            branch=plan["repository"]["branch"],
            changed_paths={"uncommitted.txt"},
            require_clean=True,
        )
        self.assertTrue(any("clean" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
