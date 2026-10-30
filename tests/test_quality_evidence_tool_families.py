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
import importlib.util
import json
import os
import platform
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.quality_evidence_fixtures import _DiagnosticInventoryFixture
from tests.test_quality_evidence_profile import _original

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
# The repository's protected reviewed baseline, which the producer tree's secrets family holds the scan to.
_REVIEWED_BASELINE = Path(__file__).resolve().parent.parent / ".secrets.baseline"
_NEW_FAMILIES = (
    "shell-lint",
    "dockerfile-lint",
    "workflow-lint",
    "gitlab-script",
    "secrets",
    "unsafe-calls",
)


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
        for name, version in (
            ("shellcheck", "0.11.0"),
            ("hadolint", "2.15.1"),
            ("actionlint", "1.7.12"),
        ):
            binary = self.tool_root / name
            binary.write_bytes(f"#!fake {name}\n".encode())
            binary.chmod(0o755)
            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
            pins[name] = {"version": version, "sha256": {platform.machine(): digest}}
        self.profile: dict[str, Any] = {
            "schema": "gnostoa-diagnostic-profile/v2",
            "id": "fixture.tool-families",
            "scopes": {"all": {"exclude": []}},
            "tools": pins,
            "families": [
                {
                    "id": "shell-lint",
                    "producer": "shellcheck",
                    "diff": "all",
                    "full": "all",
                    "active": True,
                },
                {
                    "id": "dockerfile-lint",
                    "producer": "hadolint",
                    "diff": "all",
                    "full": "all",
                    "active": True,
                },
                {
                    "id": "workflow-lint",
                    "producer": "actionlint",
                    "diff": "all",
                    "full": "all",
                    "active": True,
                },
                {
                    "id": "gitlab-script",
                    "producer": "gitlab-shellcheck",
                    "diff": "all",
                    "full": "all",
                    "active": True,
                },
                {
                    "id": "secrets",
                    "producer": "secrets",
                    "diff": "all",
                    "full": "all",
                    "active": True,
                },
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
        self.executed: list[tuple[str, str]] = []
        self.tool_answers: dict[str, tuple[int | None, object]] = {
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
                command,
                cwd=cwd,
                environment=environment,
                report=report,
                deadline=deadline,
                limits=limits,
            )
        self.commands.append((list(command), Path(cwd), dict(environment)))
        if not {"--version", "-version"} & set(command):
            self.executed.append(
                (name, hashlib.sha256(Path(command[0]).read_bytes()).hexdigest())
            )
        if report.exists():
            # As the real run does: its report is always a new file (_bounded_run, _new_file).
            return None, "cannot create its report: FileExistsError", False
        if "--version" in command or "-version" in command:
            report.write_text(
                f"{name} {self.profile['tools'][name]['version']}\n", encoding="utf-8"
            )
            return 0, None, False
        status, body = self.tool_answers[name]
        if name == "shellcheck" and isinstance(body, dict):
            # As ShellCheck does: each comment names the file it was given, the first one here.
            given = command[command.index("--") + 1] if "--" in command else command[-1]
            body = {"comments": [dict(c, file=given) for c in body["comments"]]}
        report.write_text(
            body if isinstance(body, str) else json.dumps(body), encoding="utf-8"
        )
        return status, None, False

    def _collect(self, profile=None, **options) -> dict:
        # The pinned tools are found under the protected tool root only; `create=True`, because on protected main
        # there is none yet, so the collection reaches the profile's own contract before anything else.
        with (
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch.object(self.module, "TOOL_ROOT", self.tool_root, create=True),
        ):
            # The private collector, as the shared fixture captured it from unittest.mock (no attribute access).
            path = self.collect.func(
                self.root, self.output, profile=profile or self.profile, **options
            )
        return self._read(path)

    def _rows(self, inventory: dict) -> dict[str, dict]:
        return {row["family"]: row for row in inventory.get("families", [])}

    def _change(self, path: str, old: str, new: str) -> None:
        source = self.root / path
        source.write_text(
            source.read_text(encoding="utf-8").replace(old, new, 1) + "# head\n",
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "head")

    def _commands_of(self, name: str) -> list[tuple[list[str], Path, dict[str, str]]]:
        return [
            c
            for c in self.commands
            if Path(c[0][0]).name == name and not {"--version", "-version"} & set(c[0])
        ]

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

    def test_a_tool_whose_digest_differs_from_its_pin_is_a_gap_and_never_runs(
        self,
    ) -> None:
        (self.tool_root / "shellcheck").write_bytes(b"#!altered\n")
        inventory = self._collect(base=self.base)
        self.assertNotEqual("COMPLETE", self._rows(inventory)["shell-lint"]["analysis"])
        self.assertIn("family shell-lint", inventory["coverage"]["reason"])
        self.assertEqual([], self._commands_of("shellcheck"))

    def test_a_family_names_why_its_targets_went_unanalyzed(self) -> None:
        # Found by the real-tool qualification: a count alone attributes nothing (#389 H-PYSEC-2 q1).
        (self.tool_root / "shellcheck").write_bytes(b"#!altered\n")
        row = self._rows(self._collect(base=self.base))["shell-lint"]
        self.assertIn("tool shellcheck is not its pinned bytes", row["reason"])
        self.assertIn("ci/tool", row["reason"])

    def test_every_family_that_runs_shellcheck_verifies_it_for_itself(self) -> None:
        # Found by the real-tool qualification: one version report per run directory let only the first family
        # that verified ShellCheck run it (#389 H-PYSEC-2 q1).
        rows = self._rows(self._collect(base=self.base))
        for family in ("shell-lint", "workflow-lint", "gitlab-script"):
            with self.subTest(family=family):
                self.assertEqual(
                    "COMPLETE", rows[family]["analysis"], rows[family]["reason"]
                )


class ShellFamilyTests(_ToolFamilyFixture):
    def test_an_extensionless_sh_script_is_selected_and_its_finding_listed(
        self,
    ) -> None:
        inventory = self._collect(base=self.base)
        found = self._findings(inventory, "shellcheck")
        self.assertEqual(
            [("ci/tool", 2)], [(f["path"], f["range"]["start_line"]) for f in found]
        )
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
        (self.root / "ci" / "tool").write_text(
            "#!/bin/sh\n# shellcheck disable=SC2086\necho $1\n", encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "directive")
        self.tool_answers["shellcheck"] = (0, {"comments": []})
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["shell-lint"]["analysis"])
        self.assertIn("ci/tool:2", inventory["coverage"]["reason"])

    def test_a_sourced_file_is_an_attributable_gap(self) -> None:
        (self.root / "ci" / "tool").write_text(
            "#!/bin/sh\n. ./lib.sh\n", encoding="utf-8"
        )
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
        self._change(
            "tools/sample.py", "VALUE", "VALUE"
        )  # a head commit that leaves ci/tool unchanged
        inventory = self._collect(base=self.base)
        found = [
            f for f in self._findings(inventory, "shellcheck") if f["path"] == "ci/tool"
        ]
        self.assertNotEqual([], found)
        self.assertEqual({False}, {f["native"]["in_diff"] for f in found})

    def test_another_shell_s_script_is_a_gap_that_names_it(self) -> None:
        # Found by the real-tool qualification: the note named the interpreter, not the script (#389 H-PYSEC-2 q2).
        for name in ("ci/zshy", "ci/fishy"):
            target = self.root / name
            target.write_text("#!/usr/bin/env zsh\necho hi\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "other shells")
        row = self._rows(self._collect(base=self.base))["shell-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        for name in ("ci/zshy", "ci/fishy"):
            with self.subTest(script=name):
                self.assertIn(
                    f"{name}: an unsupported interpreter 'zsh'", row["reason"]
                )


class DockerfileFamilyTests(_ToolFamilyFixture):
    def test_a_run_defect_is_listed_and_the_protected_config_governs(self) -> None:
        (self.root / ".hadolint.yaml").write_text(
            "ignored: [SC2086]\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "hostile hadolint config")
        with patch.dict(os.environ, {"HADOLINT_IGNORE": "SC2086"}):
            inventory = self._collect(base=self.base)
        found = self._findings(inventory, "hadolint")
        self.assertEqual(
            [("Dockerfile", 2)], [(f["path"], f["range"]["start_line"]) for f in found]
        )
        command, cwd, environment = self._commands_of("hadolint")[0]
        self.assertIn("--disable-ignore-pragma", command)
        config = Path(command[command.index("-c") + 1])
        self.assertFalse(config.resolve().is_relative_to(self.root.resolve()))
        self.assertNotIn("HADOLINT_IGNORE", environment)
        self.assertFalse((Path(cwd) / ".hadolint.yaml").exists())

    def test_a_pragma_is_an_attributable_gap(self) -> None:
        (self.root / "Dockerfile").write_text(
            "FROM debian:12\n# hadolint ignore=DL3008\nRUN echo $FOO\n",
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "pragma")
        inventory = self._collect(base=self.base)
        self.assertEqual(
            "PARTIAL", self._rows(inventory)["dockerfile-lint"]["analysis"]
        )
        self.assertIn("Dockerfile:2", inventory["coverage"]["reason"])

    def test_exit_one_without_a_report_is_a_gap(self) -> None:
        self.tool_answers["hadolint"] = (1, "")
        inventory = self._collect(base=self.base)
        self.assertNotEqual(
            "COMPLETE", self._rows(inventory)["dockerfile-lint"]["analysis"]
        )


class WorkflowFamilyTests(_ToolFamilyFixture):
    def test_a_run_defect_is_listed_and_the_protected_config_and_shellcheck_govern(
        self,
    ) -> None:
        (self.root / ".github" / "actionlint.yaml").write_text(
            "paths:\n  '**':\n    ignore: ['.+']\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "hostile actionlint config")
        inventory = self._collect(base=self.base)
        found = self._findings(inventory, "actionlint")
        self.assertEqual(
            [(".github/workflows/w.yml", 10)],
            [(f["path"], f["range"]["start_line"]) for f in found],
        )
        self.assertEqual("echo $FOO", _WORKFLOW.split("\n")[9].split("run: ", 1)[1])
        command, _, _ = self._commands_of("actionlint")[0]
        config = Path(command[command.index("-config-file") + 1])
        self.assertFalse(config.resolve().is_relative_to(self.root.resolve()))
        # The pinned ShellCheck governs: the run's verified copy of its bytes (cubic on #470), never the head's.
        shellcheck = Path(command[command.index("-shellcheck") + 1])
        self.assertEqual(
            self.profile["tools"]["shellcheck"]["sha256"][platform.machine()],
            hashlib.sha256(shellcheck.read_bytes()).hexdigest(),
        )
        self.assertTrue(shellcheck.resolve().is_relative_to(self.output.resolve()))
        self.assertIn("-pyflakes=", command)

    def test_the_queue_projection_changes_only_the_validated_line(self) -> None:
        text, projected, refused = self.module.project_concurrency_queue(_WORKFLOW)
        self.assertEqual([(5, "max")], projected)
        self.assertEqual([], refused)
        changed = [
            (a, b)
            for a, b in zip(_WORKFLOW.split("\n"), text.split("\n"), strict=True)
            if a != b
        ]
        self.assertEqual(1, len(changed))
        self.assertEqual(len(_WORKFLOW.split("\n")), len(text.split("\n")))
        self.assertTrue(changed[0][1].lstrip().startswith("#"))

    def test_the_queue_projection_refuses_undocumented_and_conflicting_forms(
        self,
    ) -> None:
        for name, form in {
            "value": _WORKFLOW.replace("queue: max", "queue: maxx"),
            "cancel": _WORKFLOW.replace(
                "cancel-in-progress: false", "cancel-in-progress: true"
            ),
            "expression": _WORKFLOW.replace(
                "cancel-in-progress: false",
                "cancel-in-progress: ${{ github.ref == 'x' }}",
            ),
            "flow": _WORKFLOW.replace(
                "concurrency:\n  group: g\n  cancel-in-progress: false\n  queue: max\n",
                "concurrency: {group: g, queue: max}\n",
            ),
            "duplicate": _WORKFLOW.replace(
                "  queue: max\n", "  queue: max\n  queue: single\n"
            ),
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
        path.write_text(
            _WORKFLOW + "      - run: print(1)\n        shell: python\n",
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "python step")
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["workflow-lint"]["analysis"])
        self.assertIn(".github/workflows/w.yml", inventory["coverage"]["reason"])


class GitlabScriptFamilyTests(_ToolFamilyFixture):
    def test_a_script_item_is_analyzed_and_mapped_to_its_yaml_line(self) -> None:
        self.tool_answers["shellcheck"] = (1, {"comments": [dict(_SC_NATIVE, line=2)]})
        inventory = self._collect(base=self.base)
        found = [
            f
            for f in self._findings(inventory, "gitlab-shellcheck")
            if f["path"] == ".gitlab-ci.yml"
        ]
        self.assertEqual([3], [f["range"]["start_line"] for f in found])

    def test_an_unsupported_construct_is_an_attributable_gap(self) -> None:
        (self.root / ".gitlab-ci.yml").write_text(
            "include: other.yml\n" + _GITLAB, encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "include")
        inventory = self._collect(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["gitlab-script"]["analysis"])
        self.assertIn(".gitlab-ci.yml", inventory["coverage"]["reason"])


@unittest.skipUnless(
    importlib.util.find_spec("detect_secrets") is not None,
    "detect-secrets is available only in the exact development verification environment",
)
class SecretsFamilyTests(_ToolFamilyFixture):
    # Synthetic values only; the family runs the protected scanner with its pinned plugin over the head's data.

    def test_a_dockerfile_env_secret_is_listed_by_the_secrets_family(self) -> None:
        (self.root / "Dockerfile").write_text(
            "FROM scratch\nENV DB_PASSWORD=" + "Zq7" * 6 + "\n",
            encoding="utf-8",  # pragma: allowlist secret -- synthetic fixture value
        )
        self._git("commit", "-q", "-am", "env secret")
        inventory = self._collect(base=self.base)
        found = [
            f for f in self._findings(inventory, "secrets") if f["path"] == "Dockerfile"
        ]
        self.assertEqual([2], [f["range"]["start_line"] for f in found])

    def test_a_workflow_secret_reference_is_not_listed(self) -> None:
        (self.root / ".github" / "workflows" / "w.yml").write_text(
            _WORKFLOW + "        env:\n          API_TOKEN: ${{ secrets.API_TOKEN }}\n",
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "secret reference")
        inventory = self._collect(base=self.base)
        self.assertEqual(
            [],
            [
                f
                for f in self._findings(inventory, "secrets")
                if f["path"].startswith(".github/")
            ],
        )

    def test_the_scanner_pins_its_plugin_by_digest(self) -> None:
        from tools import security_scan

        self.assertTrue(
            hasattr(security_scan, "PLUGIN_PINS"), "the scanner pins no plugin"
        )
        pins = security_scan.PLUGIN_PINS
        self.assertEqual(1, len(pins))
        for _name, (relative, digest) in pins.items():
            path = Path(security_scan.__file__).resolve().parent.parent / relative
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_a_spent_budget_starts_no_secrets_scan(self) -> None:
        # Amazon Q and cubic on #470: the secrets family keeps the inventory's one deadline.
        run = Path(self.directory.name) / "run"
        run.mkdir()
        with patch("tools.security_scan.scan_tracked_tree") as scan:
            result, _notes = _original(self.module, "_run_secrets")(
                self.root,
                run,
                ["Dockerfile"],
                self.module.DEFAULT_DIAGNOSTIC_LIMITS,
                time.monotonic() - 1,
                100,
            )
        scan.assert_not_called()
        self.assertIn("deadline", result.unanalyzed["Dockerfile"])

    def test_a_scanner_failure_is_named_by_its_type_alone(self) -> None:
        # Amazon Q, Revix and cubic on #470: an exception's text can carry a host path.
        absent = Path(self.directory.name) / "host-only-directory" / "baseline.json"
        with patch.object(self.module, "_PROTECTED_BASELINE", absent):
            row = self._rows(self._collect(base=self.base))["secrets"]
        self.assertIn("secrets: FileNotFoundError", row["reason"])
        self.assertNotIn("host-only-directory", row["reason"])

    def test_a_file_holding_nul_bytes_is_a_named_gap(self) -> None:
        # cubic on #470: the protected plugins never read such a file, so it must never count as clean.
        (self.root / "blob.yml").write_bytes(b"password: x\0y\n")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "nul file")
        row = self._rows(self._collect(base=self.base))["secrets"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("NUL", row["reason"])
        self.assertIn("blob.yml", row["reason"])

    def test_a_file_with_carriage_return_line_ends_is_read_line_by_line(self) -> None:
        # cubic on #470: a lone CR ends a line too, or every line after the first is never read.
        (self.root / "Dockerfile").write_bytes(
            b"FROM scratch\rENV DB_PASSWORD="
            + b"Zq7" * 6
            + b"\r"  # pragma: allowlist secret -- synthetic fixture value
        )
        self._git("commit", "-q", "-am", "carriage returns")
        found = [
            f
            for f in self._findings(self._collect(base=self.base), "secrets")
            if f["path"] == "Dockerfile"
        ]
        self.assertEqual([2], [f["range"]["start_line"] for f in found])

    def test_a_finding_after_a_form_feed_keeps_its_file_line_number(self) -> None:
        # cubic on #470: lines are the file's, split at newlines only.
        (self.root / "Dockerfile").write_text(
            "FROM scratch\n# a\x0cb\nENV DB_PASSWORD=" + "Zq7" * 6 + "\n",
            encoding="utf-8",  # pragma: allowlist secret -- synthetic fixture value
        )
        self._git("commit", "-q", "-am", "form feed")
        found = [
            f
            for f in self._findings(self._collect(base=self.base), "secrets")
            if f["path"] == "Dockerfile"
        ]
        self.assertEqual([3], [f["range"]["start_line"] for f in found])

    def _secrets_runs(self, inventory: dict) -> list[dict]:
        return [r for r in inventory["producers"] if r["producer"] == "secrets"]

    def test_the_secrets_run_names_the_scanner_version_it_was_held_to(self) -> None:
        # The scan refuses any settings but the protected baseline's, so its version is the baseline's; the run
        # record names it (#389 6510431996, residual).
        baseline = json.loads(_REVIEWED_BASELINE.read_text(encoding="utf-8"))
        runs = self._secrets_runs(self._collect(base=self.base))
        self.assertEqual([baseline["version"]], [r["version"] for r in runs])

    def test_a_baseline_held_to_other_scanner_settings_leaves_the_family_unanalyzed(
        self,
    ) -> None:
        # The Router's 6510622435 on #389: the scanner's version, plugins and filters are each held to the protected
        # reviewed baseline, and a mismatch is an attributable refusal, never a clean row.
        protected = _REVIEWED_BASELINE
        reviewed = json.loads(protected.read_text(encoding="utf-8"))

        def other_version(document: dict) -> None:
            document["version"] = "0.0.1"

        def one_plugin_fewer(document: dict) -> None:
            document["plugins_used"] = document["plugins_used"][1:]

        def one_filter_fewer(document: dict) -> None:
            document["filters_used"] = document["filters_used"][1:]

        for change in (other_version, one_plugin_fewer, one_filter_fewer):
            with self.subTest(change=change.__name__):
                document = copy.deepcopy(reviewed)
                change(document)
                other = Path(self.directory.name) / f"{change.__name__}.baseline"
                other.write_text(json.dumps(document), encoding="utf-8")
                with patch.object(self.module, "_PROTECTED_BASELINE", other):
                    inventory = self._collect(base=self.base)
                row = self._rows(inventory)["secrets"]
                self.assertEqual("INCOMPLETE", row["analysis"])
                self.assertIn(
                    "settings do not match the reviewed baseline", row["reason"]
                )
                self.assertEqual([], self._findings(inventory, "secrets"))

    def test_the_secrets_run_binds_its_scanner_and_plugin_identity(self) -> None:
        # The Router's 6510622435 on #389: the run record names what the scan was held to, by digest.
        from tools import security_scan

        inventory = self._collect(base=self.base)
        (run,) = self._secrets_runs(inventory)
        identity = self.output.glob(f"diagnostic-*/{run['report']['path']}")
        document = json.loads(next(identity).read_text(encoding="utf-8"))
        protected = _REVIEWED_BASELINE
        self.assertEqual(
            {
                "scanner": "detect-secrets",
                "version": run["version"],
                "baseline_sha256": hashlib.sha256(protected.read_bytes()).hexdigest(),
                "plugins": {n: d for n, (_r, d) in security_scan.PLUGIN_PINS.items()},
            },
            document,
        )


class RoundTwoContractTests(_ToolFamilyFixture):
    """The contract #470's review rounds found missing (#389 H-PYSEC-2). Its own class, since the secrets
    tests skip without detect-secrets and these must run wherever the suite does."""

    def _commit(self, files: dict[str, str]) -> None:
        for name, body in files.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "round two")

    def test_a_run_with_no_status_and_no_gap_is_never_clean(self) -> None:
        # Amazon Q on #470.
        self.tool_answers["shellcheck"] = (None, {"comments": []})
        row = self._rows(self._collect(base=self.base))["shell-lint"]
        self.assertEqual("INCOMPLETE", row["analysis"])
        self.assertIn("did not finish", row["reason"])

    def test_a_report_with_a_duplicate_key_is_a_gap(self) -> None:
        # Revix and cubic on #470: reports are read strictly.
        self.tool_answers["shellcheck"] = (1, '{"comments": [], "comments": []}')
        self.tool_answers["hadolint"] = (
            1,
            '[{"code": "DL3006", "code": "DL3007", "column": 1, "file": "Dockerfile",'
            ' "level": "warning", "line": 1, "message": "m"}]',
        )
        self.tool_answers["actionlint"] = (1, '[{"message": "m", "message": "n"}]')
        rows = self._rows(self._collect(base=self.base))
        for family in ("shell-lint", "dockerfile-lint", "workflow-lint"):
            with self.subTest(family=family):
                self.assertEqual("INCOMPLETE", rows[family]["analysis"])
                self.assertIn("unparsable report", rows[family]["reason"])

    def test_a_refused_queue_form_is_a_named_gap(self) -> None:
        # cubic on #470: a refused form is left for actionlint, and named.
        self._commit(
            {
                ".github/workflows/w.yml": _WORKFLOW.replace(
                    "concurrency:\n  group: g\n  cancel-in-progress: false\n  queue: max\n",
                    "concurrency: {group: g, queue: max}\n",
                )
            }
        )
        row = self._rows(self._collect(base=self.base))["workflow-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("flow-style concurrency", row["reason"])

    def test_a_malformed_workflow_structure_is_a_named_gap_and_still_linted(
        self,
    ) -> None:
        # Codex, Revix and cubic on #470.
        self._commit(
            {
                ".github/workflows/w.yml": "on: push\njobs: [build]\n",
                ".github/workflows/x.yml": (
                    "on: push\ndefaults: bash\njobs:\n  a:\n    runs-on: x\n    steps:\n"
                    "      - run: echo\n        shell: ' '\n"
                ),
            }
        )
        inventory = self._collect(base=self.base)
        row = self._rows(inventory)["workflow-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        for needle in ("w.yml", "x.yml", "not a mapping", "an empty shell"):
            with self.subTest(needle=needle):
                self.assertIn(needle, row["reason"])
        self.assertTrue(self._commands_of("actionlint"))

    def test_a_gitlab_scalar_that_cannot_be_constructed_is_a_named_gap(self) -> None:
        # Revix on #470.
        self._commit({".gitlab-ci.yml": "job:\n  script:\n    - !!int x\n"})
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn(".gitlab-ci.yml", row["reason"])

    def test_distinct_gitlab_jobs_are_each_analyzed(self) -> None:
        # Codex and cubic on #470: `build app` and `build_app` once shared one analysis file.
        self._commit(
            {
                ".gitlab-ci.yml": (
                    "build app:\n  script:\n    - echo $A\nbuild_app:\n  script:\n    - echo ok\n"
                )
            }
        )
        self._collect(base=self.base)
        command = next(
            c for c, _cwd, _env in self._commands_of("shellcheck") if "--shell=sh" in c
        )
        analyzed = command[command.index("--") + 1 :]
        self.assertEqual(2, len(set(analyzed)), analyzed)

    def test_a_diff_only_family_acquires_changed_non_python_files(self) -> None:
        # Codex on #470: the comparison was read only when a Python path reached past FULL.
        profile = copy.deepcopy(self.profile)
        profile["scopes"]["no-python"] = {"exclude": ["tools/", "tests/"]}
        shell = next(f for f in profile["families"] if f["id"] == "shell-lint")
        shell.update(diff="no-python", full=None)
        self._change("ci/tool", "echo $1", "echo $2")
        row = self._rows(self._collect(profile, base=self.base))["shell-lint"]
        self.assertEqual(1, row["targets"])
        self.assertTrue(self._commands_of("shellcheck"))

    def test_a_bash_or_ksh_file_is_selected_by_its_suffix_and_another_shell_s_is_named(
        self,
    ) -> None:
        # cubic on #470.
        self._commit(
            {
                "ci/lib.bash": "echo $1\n",
                "ci/lib.ksh": "echo $1\n",
                "ci/lib.zsh": "echo $1\n",
            }
        )
        inventory = self._collect(base=self.base)
        command = next(
            c
            for c, _cwd, _env in self._commands_of("shellcheck")
            if "--shell=sh" not in c
        )
        self.assertIn("ci/lib.bash", command)
        self.assertIn("ci/lib.ksh", command)
        self.assertNotIn("ci/lib.zsh", command)
        self.assertIn("ci/lib.zsh", self._rows(inventory)["shell-lint"]["reason"])

    def test_a_marked_line_keeps_its_file_line_number_after_a_form_feed(self) -> None:
        # Revix on #470: lines split at newlines only, so a note names the file's own line.
        self._commit(
            {"ci/tool": "#!/bin/sh\n# a\x0cb\n# shellcheck disable=SC2086\necho $1\n"}
        )
        row = self._rows(self._collect(base=self.base))["shell-lint"]
        self.assertIn("ci/tool:3: a ShellCheck directive", row["reason"])

    def test_a_deeply_nested_workflow_or_gitlab_file_is_a_named_gap(self) -> None:
        # Revix on #470: a nesting past the YAML reader's depth is a gap, never a crash.
        depth = 3000
        nested = "[" * depth + "]" * depth
        self._commit(
            {
                ".github/workflows/w.yml": f"on: push\njobs: {nested}\n",
                ".gitlab-ci.yml": f"job:\n  script: {nested}\n",
            }
        )
        rows = self._rows(self._collect(base=self.base))
        self.assertIn("w.yml", rows["workflow-lint"]["reason"])
        self.assertNotEqual("COMPLETE", rows["gitlab-script"]["analysis"])
        self.assertIn(".gitlab-ci.yml", rows["gitlab-script"]["reason"])

    def test_a_windows_job_s_default_shell_is_a_named_gap(self) -> None:
        # Revix on #470: a Windows runner's default shell is pwsh, which actionlint gives to no analyzer.
        self._commit(
            {
                ".github/workflows/w.yml": (
                    "on: push\njobs:\n  a:\n    runs-on: windows-latest\n    steps:\n      - run: echo $FOO\n"
                )
            }
        )
        row = self._rows(self._collect(base=self.base))["workflow-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("'pwsh'", row["reason"])

    def test_an_executable_past_its_byte_bound_never_runs(self) -> None:
        # Revix on #470: the executable is read within a bound, as every read in tools/ is.
        with patch.object(self.module, "_MAX_TOOL_BYTES", 4, create=True):
            inventory = self._collect(base=self.base)
        row = self._rows(inventory)["shell-lint"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn("tool shellcheck is not a bounded regular file", row["reason"])
        self.assertEqual([], self._commands_of("shellcheck"))

    def test_a_yaml_line_break_the_file_does_not_count_is_a_named_gap(self) -> None:
        # A control (cubic on #470): PyYAML also breaks lines at NEL, LS and PS, which the file does not count. In a
        # comment or a block scalar PyYAML refuses the file, and the reader refuses any scalar spanning its lines, so
        # no YAML-derived line is reported shifted: the file is a named gap.
        for text in (
            "# a\u2028b\njob:\n  script:\n    - echo $FOO\n",
            'variables:\n  A: "x\u2028y"\njob:\n  script:\n    - echo $FOO\n',
            "job:\n  script:\n    - |\n      echo a\u2028echo $FOO\n",
        ):
            with self.subTest(text=text[:20]):
                self._commit({".gitlab-ci.yml": text})
                row = self._rows(self._collect(base=self.base))["gitlab-script"]
                self.assertNotEqual("COMPLETE", row["analysis"])
                self.assertIn(".gitlab-ci.yml", row["reason"])

    def test_a_runner_that_names_no_platform_has_an_unknown_default_shell(self) -> None:
        # cubic on #470: a runner group or a bare self-hosted label can select Windows.
        for runs_on in ("self-hosted", "{group: g}", "[self-hosted, gpu]"):
            with self.subTest(runs_on=runs_on):
                self._commit(
                    {
                        ".github/workflows/w.yml": (
                            f"on: push\njobs:\n  a:\n    runs-on: {runs_on}\n    steps:\n      - run: echo $FOO\n"
                        )
                    }
                )
                row = self._rows(self._collect(base=self.base))["workflow-lint"]
                self.assertEqual("PARTIAL", row["analysis"])
                self.assertIn("runs-on does not name", row["reason"])

    def _gitlab_analyzed(self) -> list[str]:
        command = next(
            c for c, _cwd, _env in self._commands_of("shellcheck") if "--shell=sh" in c
        )
        return command[command.index("--") + 1 :]

    def test_the_gitlab_pages_job_is_analyzed(self) -> None:
        # Codex on #470: `pages` is a job, not a reserved key.
        self._commit({".gitlab-ci.yml": "pages:\n  script:\n    - echo $FOO\n"})
        self._collect(base=self.base)
        self.assertEqual(1, len(self._gitlab_analyzed()))

    def test_a_top_level_before_script_is_analyzed_with_each_job(self) -> None:
        # Codex on #470: the runner runs a top-level before_script, so the reader reads it.
        self._commit(
            {
                ".gitlab-ci.yml": "before_script:\n  - echo $UNQUOTED\njob:\n  script:\n    - echo ok\n"
            }
        )
        self._collect(base=self.base)
        (analyzed,) = self._gitlab_analyzed()
        (body,) = [
            p.read_text(encoding="utf-8")
            for p in self.output.glob(f"diagnostic-*/gitlab-input/{analyzed}")
        ]
        self.assertIn("echo $UNQUOTED", body)

    def test_an_unsupported_script_outside_the_family_s_scope_is_no_gap(self) -> None:
        # Codex on #470: only what the family's scopes select can downgrade its row.
        profile = copy.deepcopy(self.profile)
        profile["scopes"]["no-tests"] = {"exclude": ["tests/"]}
        shell = next(f for f in profile["families"] if f["id"] == "shell-lint")
        shell.update(diff="no-tests", full="no-tests")
        self._commit({"tests/tool.zsh": "echo $1\n"})
        row = self._rows(self._collect(profile, base=self.base))["shell-lint"]
        self.assertNotIn("tests/tool.zsh", row["reason"] or "")

    def test_the_verified_bytes_are_the_bytes_that_run(self) -> None:
        # cubic on #470: a tool replaced after its check must never be what runs.
        pinned = self.profile["tools"]["shellcheck"]["sha256"][platform.machine()]
        verify = _original(self.module, "_tool_version")

        def then_replace(*args, **kwargs):
            version = verify(*args, **kwargs)
            (self.tool_root / "shellcheck").write_bytes(b"#!replaced\n")
            return version

        with patch.object(self.module, "_tool_version", side_effect=then_replace):
            self._collect(base=self.base)
        ran = {digest for name, digest in self.executed if name == "shellcheck"}
        self.assertEqual({pinned}, ran)


class RepositoryCleanTests(_ToolFamilyFixture):
    # RED on main: the repairs are owed.

    @unittest.skipUnless(
        importlib.util.find_spec("ruff") is not None,
        "Ruff is available only in the exact development verification environment",
    )
    def test_the_unsafe_call_rules_find_nothing_in_the_repository(self) -> None:
        # The repository is clean under the family's rules. Ruff runs through the inventory's own bounded runner, and
        # must finish with status 0 and an empty report, so a Ruff that never ran is a failure (cubic on #470). The
        # family's wiring is RealToolPositiveTests' and the profile tests'. A collection here would read the frozen
        # HEAD, which is the parent in exact-parent preparation, not this candidate.
        import sys

        repository = Path(__file__).resolve().parent.parent
        run = Path(self.directory.name) / "clean"
        run.mkdir()
        report = run / "ruff.json"
        status, gap, invalid = _original(self.module, "_bounded_run")(
            [
                sys.executable,
                "-I",
                "-m",
                "ruff",
                "check",
                "--isolated",
                "--no-cache",
                "--ignore-noqa",  # a flag, not a marker -- Ruff's option to ignore every inline suppression
                "--preview",
                "--select",
                "S301,S307,S324,S602,S605,S608",
                "--output-format",
                "json",
                ".",
            ],
            cwd=repository,
            environment=_original(self.module, "_tool_environment")(run),
            report=report,
            deadline=time.monotonic() + 600,
            limits=self.module.DEFAULT_DIAGNOSTIC_LIMITS,
        )
        self.assertEqual((0, None, False), (status, gap, invalid))
        records = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual([], [(r["filename"], r["code"]) for r in records])

    def test_the_protected_profile_pins_the_official_release_executables(self) -> None:
        # The executables inside the official release assets, whose own digests GitHub publishes (#389 6503632912).
        official = {
            "shellcheck": (
                "0.11.0",
                "4da528ddb3a4d1b7b24a59d4e16eb2f5fd960f4bd9a3708a15baddbdf1d5a55b",  # pragma: allowlist secret -- an official release executable's SHA-256 pin
            ),
            "hadolint": (
                "2.15.1",
                "c7187db94eeeeca956519a6af171adc31453941a1e777961f6e680f697c8c507",  # pragma: allowlist secret -- an official release executable's SHA-256 pin
            ),
            "actionlint": (
                "1.7.12",
                "c872d6db8c6bf83a8eaa704fc93999f027d55dffbc63b8a6abdccb47df5f4cd4",  # pragma: allowlist secret -- an official release executable's SHA-256 pin
            ),
        }
        self.assertTrue(
            hasattr(self.module, "TOOL_ROOT"),
            "the inventory names no protected tool root",
        )
        profile = self.module.load_diagnostic_profile()
        self.assertIn("tools", profile)
        for name, (version, x86_64) in official.items():
            with self.subTest(tool=name):
                self.assertEqual(version, profile["tools"][name]["version"])
                self.assertEqual(x86_64, profile["tools"][name]["sha256"]["x86_64"])
