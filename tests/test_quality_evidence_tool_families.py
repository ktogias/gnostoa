"""RED for H-PYSEC-2 (#389; owner admission 6508582845, Router 6508335114): the inventory's pinned tool families.

The contract these tests fix, before any implementation:
- a v2 protected profile with `tools` pins (each pinned executable's SHA-256 per machine) and a per-family `active`
  flag, off for the new families on the protected profile;
- producers `shellcheck`, `hadolint`, `actionlint`, `gitlab-shellcheck` and `secrets`, run from a protected
  `tool_root` only after their digest matches the pin, in a clean environment, with the protected configuration;
- an inline ShellCheck directive or Hadolint pragma, a `source`, an unsupported GitLab construct, a missing or altered
  tool, or a report contradicting its exit status is an attributable gap, never a clean result;
- the analysis-only `concurrency.queue` projection, which changes nothing but a validated documented line;
- every acquired finding listed, in the existing lossless DIFF/FULL partition.

On protected main each test fails for its stated reason: the profile admits no such producer, family field or tool
pin, and the module has no such helper. Producers are faked at `_bounded_run` with their native report bytes,
captured from ShellCheck 0.11.0, Hadolint 2.15.1 and actionlint 1.7.12 (#389 6503632912)."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
from pathlib import Path
from unittest.mock import patch

from tests.quality_evidence_fixtures import _DiagnosticInventoryFixture

_SC_NATIVE = {
    "file": "tool",
    "line": 2,
    "endLine": 2,
    "column": 6,
    "endColumn": 8,
    "level": "info",
    "code": 2086,
    "message": "Double quote to prevent globbing and word splitting.",
    "fix": None,
}
_HL_NATIVE = {
    "code": "SC2086",
    "column": 1,
    "file": "Dockerfile",
    "level": "info",
    "line": 2,
    "message": "Double quote to prevent globbing and word splitting.",
}
_AL_NATIVE = {
    "message": "shellcheck reported issue in this script: SC2086:info:1:6: Double quote to prevent globbing and word splitting",
    "filepath": ".github/workflows/w.yml",
    "line": 10,
    "column": 9,
    "kind": "shellcheck",
    "snippet": "      - run: echo $FOO\n        ^~~~",
    "end_column": 12,
}
_SCRIPT = "#!/bin/sh\necho $1\n"
_DOCKERFILE = "FROM debian:12\nRUN echo $FOO\n"
_WORKFLOW = (
    "on: push\n"
    "concurrency:\n"
    "  group: g\n"
    "  cancel-in-progress: false\n"
    "  queue: max\n"
    "jobs:\n"
    "  a:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - run: echo $FOO\n"
)
_GITLAB = "job:\n  script:\n    - echo $FOO\n"
_NEW_FAMILIES = ("shell-lint", "dockerfile-lint", "workflow-lint", "gitlab-script", "secrets", "unsafe-calls")


class _ToolFamilyFixture(_DiagnosticInventoryFixture):
    """The shared fixture plus one file per new family, fake pinned tools and a v2 profile with every new family
    active, as a qualification run uses it."""

    def setUp(self) -> None:
        super().setUp()
        for path, text in {
            "ci/tool": _SCRIPT,
            "Dockerfile": _DOCKERFILE,
            ".github/workflows/w.yml": _WORKFLOW,
            ".gitlab-ci.yml": _GITLAB,
        }.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        (self.root / "ci" / "tool").chmod(0o755)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "tool families")
        self.base = self._git("rev-parse", "HEAD")
        self.tool_root = Path(self.directory.name) / "tools"
        self.tool_root.mkdir()
        pins = {}
        for name, version in (("shellcheck", "0.11.0"), ("hadolint", "2.15.1"), ("actionlint", "1.7.12")):
            binary = self.tool_root / name
            binary.write_bytes(f"#!fake {name}\n".encode())
            binary.chmod(0o755)
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            pins[name] = {"version": version, "sha256": {platform.machine(): digest}}
        self.profile = {
            "schema": "gnostoa-diagnostic-profile/v2",
            "id": "fixture.tool-families",
            "scopes": {"all": {"exclude": []}},
            "tools": pins,
            "families": [
                {"id": "shell-lint", "producer": "shellcheck", "diff": "all", "full": "all", "active": True},
                {"id": "dockerfile-lint", "producer": "hadolint", "diff": "all", "full": "all", "active": True},
                {"id": "workflow-lint", "producer": "actionlint", "diff": "all", "full": "all", "active": True},
                {"id": "gitlab-script", "producer": "gitlab-shellcheck", "diff": "all", "full": "all", "active": True},
                {"id": "secrets", "producer": "secrets", "diff": "all", "full": "all", "active": True},
                {
                    "id": "unsafe-calls",
                    "producer": "ruff",
                    "select": ["S301", "S307", "S324", "S602", "S605", "S608"],
                    "diff": "all",
                    "full": "all",
                    "active": True,
                },
            ],
        }
        self.tool_answers: dict[str, tuple[int, object]] = {
            "shellcheck": (1, {"comments": [dict(_SC_NATIVE, file="ci/tool")]}),
            "hadolint": (1, [_HL_NATIVE]),
            "actionlint": (1, [_AL_NATIVE]),
        }

    def _tool(self, command) -> str | None:
        for name in ("shellcheck", "hadolint", "actionlint"):
            if Path(command[0]).name == name:
                return name
        return None

    def _fake_run(self, command, *, cwd, environment, report, deadline, limits):
        name = self._tool(command)
        if name is None:
            return super()._fake_run(
                command, cwd=cwd, environment=environment, report=report, deadline=deadline, limits=limits
            )
        self.commands.append((list(command), Path(cwd), dict(environment)))
        if "--version" in command or "-version" in command:
            report.write_text(f"{name} {self.profile['tools'][name]['version']}\n", encoding="utf-8")
            return 0, None, False
        status, body = self.tool_answers[name]
        report.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
        return status, None, False

    def _collect(self, profile=None, **options) -> dict:
        # The pinned tools are found under the protected tool root only; `create=True`, because on protected main
        # there is none yet, so the collection reaches the profile's own contract before anything else.
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run), patch.object(
            self.module, "TOOL_ROOT", self.tool_root, create=True
        ):
            path = self.module._collect_diagnostic_inventory(
                self.root, self.output, profile=profile or self.profile, **options
            )
        return self._read(path)

    def _rows(self, inventory: dict) -> dict[str, dict]:
        return {row["family"]: row for row in inventory.get("families", [])}

    def _change(self, path: str, old: str, new: str) -> None:
        source = self.root / path
        source.write_text(source.read_text(encoding="utf-8").replace(old, new, 1) + "# head\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "head")

    def _commands_of(self, name: str) -> list[tuple[list[str], Path, dict[str, str]]]:
        return [c for c in self.commands if Path(c[0][0]).name == name and "--version" not in c[0]]

    def _findings(self, inventory: dict, tool: str) -> list[dict]:
        return [f for f in inventory["findings"] if f["tool"]["id"] == tool]


class ToolFamilyProfileTests(_ToolFamilyFixture):
    # RED: main's profile shape is v1, with producers mypy/ruff/complexity and no `tools` or `active`.

    def test_the_v2_profile_admits_the_pinned_tool_families(self) -> None:
        rows = self._rows(self._collect(base=self.base))
        self.assertEqual(set(_NEW_FAMILIES), set(rows))

    def test_the_protected_profile_declares_every_new_family_inactive(self) -> None:
        profile = self.module.load_diagnostic_profile()
        families = {f["id"]: f for f in profile["families"]}
        for family in _NEW_FAMILIES:
            with self.subTest(family=family):
                self.assertIn(family, families)
                self.assertIs(False, families[family].get("active"))
        self.assertIn("tools", profile)
        for name in ("shellcheck", "hadolint", "actionlint"):
            with self.subTest(tool=name):
                self.assertIn(name, profile["tools"])

    def test_an_inactive_family_runs_nothing(self) -> None:
        profile = copy.deepcopy(self.profile)
        for family in profile["families"]:
            family["active"] = False
        self._collect(profile, base=self.base)
        for name in ("shellcheck", "hadolint", "actionlint"):
            with self.subTest(tool=name):
                self.assertEqual([], self._commands_of(name))

    def test_a_tool_whose_digest_differs_from_its_pin_is_a_gap_and_never_runs(self) -> None:
        (self.tool_root / "shellcheck").write_bytes(b"#!altered\n")
        inventory = self._collect(base=self.base)
        self.assertNotEqual("COMPLETE", self._rows(inventory)["shell-lint"]["analysis"])
        self.assertIn("family shell-lint", inventory["coverage"]["reason"])
        self.assertEqual([], self._commands_of("shellcheck"))


class ShellFamilyTests(_ToolFamilyFixture):
    def test_an_extensionless_sh_script_is_selected_and_its_finding_listed(self) -> None:
        inventory = self._collect(base=self.base)
        found = self._findings(inventory, "shellcheck")
        self.assertEqual([("ci/tool", 2)], [(f["path"], f["range"]["start_line"]) for f in found])
        self.assertIn("SC2086", found[0]["rule"])
        self.assertEqual("COMPLETE", self._rows(inventory)["shell-lint"]["analysis"])

    def test_shellcheck_runs_with_norc_and_a_clean_environment(self) -> None:
        (self.root / ".shellcheckrc").write_text("disable=all\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "hostile rc")
        with patch.dict(os.environ, {"SHELLCHECK_OPTS": "--exclude=SC2086"}):
            self._collect(base=self.base)
        command, _, environment = self._commands_of("shellcheck")[0]
        self.assertIn("--norc", command)
        self.assertIn("--format=json1", command)
        self.assertNotIn("SHELLCHECK_OPTS", environment)
        self.assertNotIn("-x", command)

    def test_an_inline_directive_is_an_attributable_gap(self) -> None:
        (self.root / "ci" / "tool").write_text("#!/bin/sh\n# shellcheck disable=SC2086\necho $1\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "directive")
        self.tool_answers["shellcheck"] = (0, {"comments": []})
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["shell-lint"]["analysis"])
        self.assertIn("ci/tool:2", inventory["coverage"]["reason"])

    def test_a_sourced_file_is_an_attributable_gap(self) -> None:
        (self.root / "ci" / "tool").write_text("#!/bin/sh\n. ./lib.sh\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "source")
        self.tool_answers["shellcheck"] = (0, {"comments": []})
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["shell-lint"]["analysis"])
        self.assertIn("ci/tool:2", inventory["coverage"]["reason"])

    def test_an_exit_status_contradicting_its_report_is_a_gap(self) -> None:
        self.tool_answers["shellcheck"] = (1, {"comments": []})
        inventory = self._collect(base=self.base)
        self.assertNotEqual("COMPLETE", self._rows(inventory)["shell-lint"]["analysis"])

    def test_an_unchanged_script_is_in_full_and_not_in_diff(self) -> None:
        self._change("tools/sample.py", "VALUE", "VALUE")  # a head commit that leaves ci/tool unchanged
        inventory = self._collect(base=self.base)
        found = self._findings(inventory, "shellcheck")
        self.assertEqual(["FULL"], sorted({s for f in found for s in f["scopes"]}))


class DockerfileFamilyTests(_ToolFamilyFixture):
    def test_a_run_defect_is_listed_and_the_protected_config_governs(self) -> None:
        (self.root / ".hadolint.yaml").write_text("ignored: [SC2086]\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "hostile hadolint config")
        with patch.dict(os.environ, {"HADOLINT_IGNORE": "SC2086"}):
            inventory = self._collect(base=self.base)
        found = self._findings(inventory, "hadolint")
        self.assertEqual([("Dockerfile", 2)], [(f["path"], f["range"]["start_line"]) for f in found])
        command, cwd, environment = self._commands_of("hadolint")[0]
        self.assertIn("--disable-ignore-pragma", command)
        config = Path(command[command.index("-c") + 1])
        self.assertFalse(config.resolve().is_relative_to(self.root.resolve()))
        self.assertNotIn("HADOLINT_IGNORE", environment)
        self.assertFalse((Path(cwd) / ".hadolint.yaml").exists())

    def test_a_pragma_is_an_attributable_gap(self) -> None:
        (self.root / "Dockerfile").write_text("FROM debian:12\n# hadolint ignore=DL3008\nRUN echo $FOO\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "pragma")
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["dockerfile-lint"]["analysis"])
        self.assertIn("Dockerfile:2", inventory["coverage"]["reason"])

    def test_exit_one_without_a_report_is_a_gap(self) -> None:
        self.tool_answers["hadolint"] = (1, "")
        inventory = self._collect(base=self.base)
        self.assertNotEqual("COMPLETE", self._rows(inventory)["dockerfile-lint"]["analysis"])


class WorkflowFamilyTests(_ToolFamilyFixture):
    def test_a_run_defect_is_listed_and_the_protected_config_and_shellcheck_govern(self) -> None:
        (self.root / ".github" / "actionlint.yaml").write_text("paths:\n  '**':\n    ignore: ['.+']\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "hostile actionlint config")
        inventory = self._collect(base=self.base)
        found = self._findings(inventory, "actionlint")
        self.assertEqual([(".github/workflows/w.yml", 10)], [(f["path"], f["range"]["start_line"]) for f in found])
        self.assertEqual("echo $FOO", _WORKFLOW.split("\n")[9].split("run: ", 1)[1])
        command, _, _ = self._commands_of("actionlint")[0]
        config = Path(command[command.index("-config-file") + 1])
        self.assertFalse(config.resolve().is_relative_to(self.root.resolve()))
        self.assertEqual(str(self.tool_root / "shellcheck"), command[command.index("-shellcheck") + 1])
        self.assertIn("-pyflakes=", command)

    def test_the_queue_projection_changes_only_the_validated_line(self) -> None:
        text, projected, refused = self.module.project_concurrency_queue(_WORKFLOW)
        self.assertEqual([(5, "max")], projected)
        self.assertEqual([], refused)
        changed = [(a, b) for a, b in zip(_WORKFLOW.split("\n"), text.split("\n")) if a != b]
        self.assertEqual(1, len(changed))
        self.assertEqual(len(_WORKFLOW.split("\n")), len(text.split("\n")))
        self.assertTrue(changed[0][1].lstrip().startswith("#"))

    def test_the_queue_projection_refuses_undocumented_and_conflicting_forms(self) -> None:
        for name, form in {
            "value": _WORKFLOW.replace("queue: max", "queue: maxx"),
            "cancel": _WORKFLOW.replace("cancel-in-progress: false", "cancel-in-progress: true"),
            "expression": _WORKFLOW.replace("cancel-in-progress: false", "cancel-in-progress: ${{ github.ref == 'x' }}"),
            "flow": _WORKFLOW.replace("concurrency:\n  group: g\n  cancel-in-progress: false\n  queue: max\n",
                                      "concurrency: {group: g, queue: max}\n"),
            "duplicate": _WORKFLOW.replace("  queue: max\n", "  queue: max\n  queue: single\n"),
        }.items():
            with self.subTest(form=name):
                text, projected, refused = self.module.project_concurrency_queue(form)
                self.assertEqual([], projected)
                self.assertNotEqual([], refused)
                self.assertEqual(form, text)

    def test_a_queue_word_in_a_run_block_or_comment_is_never_projected(self) -> None:
        form = _WORKFLOW.replace("echo $FOO", "echo 'queue: max'") + "# queue: max\n"
        text, _, _ = self.module.project_concurrency_queue(form)
        self.assertIn("echo 'queue: max'", text)
        self.assertTrue(text.endswith("# queue: max\n"))

    def test_a_step_with_a_non_sh_shell_is_an_attributable_gap(self) -> None:
        path = self.root / ".github" / "workflows" / "w.yml"
        path.write_text(_WORKFLOW + "      - run: print(1)\n        shell: python\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "python step")
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["workflow-lint"]["analysis"])
        self.assertIn(".github/workflows/w.yml", inventory["coverage"]["reason"])


class GitlabScriptFamilyTests(_ToolFamilyFixture):
    def test_a_script_item_is_analyzed_and_mapped_to_its_yaml_line(self) -> None:
        self.tool_answers["shellcheck"] = (1, {"comments": [dict(_SC_NATIVE, line=2)]})
        inventory = self._collect(base=self.base)
        found = [f for f in self._findings(inventory, "gitlab-shellcheck") if f["path"] == ".gitlab-ci.yml"]
        self.assertEqual([3], [f["range"]["start_line"] for f in found])

    def test_an_unsupported_construct_is_an_attributable_gap(self) -> None:
        (self.root / ".gitlab-ci.yml").write_text("include: other.yml\n" + _GITLAB, encoding="utf-8")
        self._git("commit", "-q", "-am", "include")
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["gitlab-script"]["analysis"])
        self.assertIn(".gitlab-ci.yml", inventory["coverage"]["reason"])


class SecretsFamilyTests(_ToolFamilyFixture):
    # Synthetic values only; the family runs the protected scanner with its pinned plugin over the head's data.

    def test_a_dockerfile_env_secret_is_listed_by_the_secrets_family(self) -> None:
        (self.root / "Dockerfile").write_text(
            "FROM scratch\nENV DB_PASSWORD=" + "Zq7" * 6 + "\n", encoding="utf-8"  # pragma: allowlist secret -- synthetic fixture value
        )
        self._git("commit", "-q", "-am", "env secret")
        inventory = self._collect(base=self.base)
        found = [f for f in self._findings(inventory, "secrets") if f["path"] == "Dockerfile"]
        self.assertEqual([2], [f["range"]["start_line"] for f in found])

    def test_a_workflow_secret_reference_is_not_listed(self) -> None:
        (self.root / ".github" / "workflows" / "w.yml").write_text(
            _WORKFLOW + "        env:\n          API_TOKEN: ${{ secrets.API_TOKEN }}\n", encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "secret reference")
        inventory = self._collect(base=self.base)
        self.assertEqual([], [f for f in self._findings(inventory, "secrets") if f["path"].startswith(".github/")])

    def test_the_scanner_pins_its_plugin_by_digest(self) -> None:
        from tools import security_scan

        self.assertTrue(hasattr(security_scan, "PLUGIN_PINS"), "the scanner pins no plugin")
        pins = security_scan.PLUGIN_PINS
        self.assertEqual(1, len(pins))
        for _name, (relative, digest) in pins.items():
            path = Path(security_scan.__file__).resolve().parent.parent / relative
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())


class RepositoryCleanTests(_ToolFamilyFixture):
    # RED on main: the repairs are owed. Each runs the real pinned tool, from the protected tool root.

    def test_the_unsafe_calls_family_finds_nothing_in_the_repository(self) -> None:
        import subprocess  # nosec B404 -- test-only: the pinned ruff on the repository's own files
        import sys

        repository = Path(__file__).resolve().parent.parent
        completed = subprocess.run(  # nosec B603 -- test-only: a literal argv
            [sys.executable, "-I", "-m", "ruff", "check", "--isolated", "--no-cache", "--ignore-noqa", "--preview",
             "--select", "S301,S307,S324,S602,S605,S608", "--output-format", "json", "."],
            cwd=repository, capture_output=True, text=True, check=False,
        )
        self.assertEqual([], [(r["filename"], r["code"]) for r in json.loads(completed.stdout or "[]")])

    def test_the_pinned_tools_are_installed_at_the_protected_tool_root(self) -> None:
        self.assertTrue(hasattr(self.module, "TOOL_ROOT"), "the inventory names no protected tool root")
        profile = self.module.load_diagnostic_profile()
        self.assertIn("tools", profile)
        for name, pin in profile["tools"].items():
            with self.subTest(tool=name):
                binary = Path(self.module.TOOL_ROOT) / name
                self.assertEqual(pin["sha256"][platform.machine()], hashlib.sha256(binary.read_bytes()).hexdigest())
