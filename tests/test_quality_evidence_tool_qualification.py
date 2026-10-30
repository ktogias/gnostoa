"""Qualification of H-PYSEC-2's pinned tool and secrets families with the real executables (#389; owner admission
6508582845, Router 6508695016; Decision 0122).

Opt-in, never production evidence: these run only when `GNOSTOA_QUALIFICATION_TOOL_ROOT` names a directory holding
the official ShellCheck 0.11.0, Hadolint 2.15.1 and actionlint 1.7.12 executables whose bytes are the protected
profile's pins, and otherwise skip with that reason. The profile is the protected one with its new families switched
on, passed explicitly, so every record names its origin as an argument, never the producer tree's. Nothing here is
faked: the tools, Ruff and the secret scanner run as the collector runs them, over a small repository with changed
and unchanged inputs, real positives, benign controls, and the inputs each family names as a gap. The collected
findings then reach the inventory's readbacks and the verdict's M17 unchanged."""

from __future__ import annotations

import copy
import hashlib
import os
import platform
import shutil
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.quality_evidence_fixtures import _DiagnosticFixture
from tests.test_merge_admission import _evidence, _failed, _verdict
from tools import analyzer_inventory
from tools.analyzer_readback import parse_readback

_VARIABLE = "GNOSTOA_QUALIFICATION_TOOL_ROOT"
_TOOLS = ("shellcheck", "hadolint", "actionlint")
_NEW_FAMILIES = (
    "shell-lint",
    "dockerfile-lint",
    "workflow-lint",
    "gitlab-script",
    "secrets",
    "unsafe-calls",
)
# A secret-like literal, built here so that no tracked file holds one (#389 6506406920).
_PLANTED = "q7".join(["Zr", "Lm", "Vx", "Wp"])
_BASE_FILES = {
    "ci/unchanged.sh": "#!/bin/sh\necho $1\n",
    "ci/changed.sh": '#!/bin/sh\necho "$1"\n',
    "ci/benign": "#!/bin/bash\nset -eu\nprintf '%s\\n' \"$1\"\n",
    "Dockerfile": "FROM debian:12\nRUN echo hi\n",
    ".github/workflows/w.yml": (
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
        '      - run: echo "$FOO"\n'
    ),
    ".gitlab-ci.yml": 'job:\n  script:\n    - echo $FOO\n    - echo "$BAR"\n',
    "tools/runner.py": (
        "import subprocess\n\n\n"
        "def run(command: str) -> None:\n"
        "    subprocess.run(command, shell=True, check=True)\n\n\n"
        "def status() -> None:\n"
        '    subprocess.run(["git", "status"], check=True)\n'
    ),
    "config/app.yml": "service:\n  api_key: ${API_KEY}\n",
}


def _tool_root() -> Path | None:
    value = os.environ.get(_VARIABLE)
    return Path(value) if value else None


@unittest.skipUnless(
    _tool_root(),
    f"{_VARIABLE} names no directory of the real pinned executables: qualification only",
)
class _RealToolFixture(_DiagnosticFixture):
    """A repository with a base and a head commit, the real tools from the named root, and the protected profile
    with its new families active."""

    def setUp(self) -> None:
        super().setUp()
        named = _tool_root()
        if named is None:
            self.skipTest(f"{_VARIABLE} is unset")
        self.qualified_root: Path = named
        protected = self.module.load_diagnostic_profile()
        for name in _TOOLS:
            digest = protected["tools"][name]["sha256"][platform.machine()]
            actual = hashlib.sha256(
                (self.qualified_root / name).read_bytes()
            ).hexdigest()
            # The named executables must be the pinned ones, or nothing below qualifies them.
            self.assertEqual(digest, actual, f"{name} is not the protected pin")
        self.profile = copy.deepcopy(protected)
        self.profile["id"] = "qualification.h-pysec-2"
        self.profile["families"] = [
            dict(family, active=True)
            for family in self.profile["families"]
            if family["id"] in _NEW_FAMILIES
        ]
        self._write(_BASE_FILES)
        (self.root / "ci" / "benign").chmod(0o755)
        self._commit("qualification base")
        self.base = self._git("rev-parse", "HEAD")
        self._write(
            {
                "ci/changed.sh": "#!/bin/sh\necho $2\n",
                "docker/Dockerfile.app": "FROM ubuntu:latest\nRUN apt-get update\n",
                "config/app.yml": f"service:\n  api_key: {_PLANTED}\n",
                "docker/Dockerfile.env": f"FROM debian:12\nENV SERVICE_TOKEN={_PLANTED}\n",
            }
        )
        self._commit("qualification head")
        self.head = self._git("rev-parse", "HEAD")

    def _write(self, files: dict[str, str]) -> None:
        for path, text in files.items():
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    def _commit(self, message: str) -> None:
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)

    def _collect(
        self,
        tool_root: Path | None = None,
        profile: dict[str, Any] | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        with patch.object(self.module, "TOOL_ROOT", tool_root or self.qualified_root):
            path = self.collect.func(
                self.root,
                self.output,
                base=self.base,
                expected_revision=self.head,
                profile=profile or self.profile,
                **options,
            )
        return self._read(path)

    @staticmethod
    def _rows(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {row["family"]: row for row in inventory["families"]}

    @staticmethod
    def _at(inventory: dict[str, Any], tool: str) -> set[tuple[str, int]]:
        return {
            (f["path"], f["range"]["start_line"])
            for f in inventory["findings"]
            if f["tool"]["id"] == tool
        }

    def _copied_root(self, names: tuple[str, ...]) -> Path:
        root = Path(self.directory.name) / "copied-tools"
        root.mkdir()
        for name in names:
            shutil.copyfile(self.qualified_root / name, root / name)
            (root / name).chmod(0o755)
        return root


class RealToolPositiveTests(_RealToolFixture):
    def test_each_family_reports_its_real_positive_and_not_its_benign_control(
        self,
    ) -> None:
        inventory = self._collect()
        self.assertEqual("argument", inventory["configuration"]["profile"]["origin"])
        self.assertEqual(
            {("ci/unchanged.sh", 2), ("ci/changed.sh", 2)},
            self._at(inventory, "shellcheck"),
        )
        self.assertIn(("docker/Dockerfile.app", 1), self._at(inventory, "hadolint"))
        self.assertNotIn("Dockerfile", {p for p, _ in self._at(inventory, "hadolint")})
        self.assertEqual(
            {(".github/workflows/w.yml", 10)}, self._at(inventory, "actionlint")
        )
        self.assertEqual(
            {(".gitlab-ci.yml", 3)}, self._at(inventory, "gitlab-shellcheck")
        )
        self.assertEqual({("tools/runner.py", 5)}, self._at(inventory, "ruff"))
        self.assertLessEqual(
            {("config/app.yml", 2), ("docker/Dockerfile.env", 2)},
            self._at(inventory, "secrets"),
        )
        rows = self._rows(inventory)
        for family in (
            "shell-lint",
            "dockerfile-lint",
            "gitlab-script",
            "unsafe-calls",
            "secrets",
        ):
            with self.subTest(family=family):
                self.assertEqual(
                    "COMPLETE", rows[family]["analysis"], rows[family]["reason"]
                )

    def test_the_queue_key_is_projected_and_never_reported(self) -> None:
        inventory = self._collect()
        messages = [
            f["message"]
            for f in inventory["findings"]
            if f["tool"]["id"] == "actionlint"
        ]
        self.assertFalse([m for m in messages if "queue" in m], messages)
        self.assertEqual("COMPLETE", self._rows(inventory)["workflow-lint"]["analysis"])

    def test_no_value_reaches_the_inventory(self) -> None:
        inventory = self._collect()
        for path in self.output.rglob("*"):
            if path.is_file():
                with self.subTest(path=path.name):
                    self.assertNotIn(_PLANTED.encode(), path.read_bytes())
        self.assertTrue(self._at(inventory, "secrets"))


class RealToolGapTests(_RealToolFixture):
    def _with(self, files: dict[str, str]) -> dict[str, Any]:
        self._write(files)
        self._commit("gap")
        self.head = self._git("rev-parse", "HEAD")
        return self._collect()

    def test_a_shellcheck_directive_and_a_sourced_file_are_named_gaps(self) -> None:
        inventory = self._with(
            {
                "ci/directive.sh": "#!/bin/sh\n# shellcheck disable=SC2086\necho $1\n",
                "ci/sourcing.sh": '#!/bin/sh\n. ./lib.sh\necho "$1"\n',
            }
        )
        row = self._rows(inventory)["shell-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("ci/directive.sh:2", row["reason"])
        self.assertIn("ci/sourcing.sh:2", row["reason"])

    def test_a_source_in_any_command_position_is_a_named_gap(self) -> None:
        # cubic on #470: the real ShellCheck names a source wherever the shell runs one, and never one in a string.
        script = (
            "#!/bin/sh\necho ok; . ./a.sh\ntrue && . ./b.sh\nif true; then . ./c.sh; fi\n( . ./d.sh )\n"
            'x=$(. ./e.sh)\nf() { . ./g.sh; }\necho ". ./not.sh"\n'
        )
        row = self._rows(self._with({"ci/positions.sh": script}))["shell-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        reason = row["reason"]
        for line in range(2, 8):
            self.assertIn(
                f"ci/positions.sh:{line}: a sourced file, never followed", reason
            )
        self.assertNotIn("ci/positions.sh:8:", reason)

    def test_a_source_in_a_gitlab_job_or_a_workflow_step_is_a_named_gap(self) -> None:
        # Claude and cubic on #470; actionlint never reports SC1091, so a step's sources are read for themselves.
        workflow = _BASE_FILES[".github/workflows/w.yml"] + (
            '      - run: echo "${{ github.sha }}"; source ./b.sh\n'
        )
        gitlab = "job:\n  script:\n    - echo ok; source ./ci/common.sh\n"
        rows = self._rows(
            self._with({".github/workflows/w.yml": workflow, ".gitlab-ci.yml": gitlab})
        )
        for family in ("gitlab-script", "workflow-lint"):
            self.assertEqual("PARTIAL", rows[family]["analysis"], family)
        self.assertIn(
            ".gitlab-ci.yml:3: a sourced file, never followed",
            rows["gitlab-script"]["reason"],
        )
        self.assertIn(
            ".github/workflows/w.yml:12: a sourced file, never followed",
            rows["workflow-lint"]["reason"],
        )

    def test_a_step_source_is_acquired_alone_at_its_line_and_counted(self) -> None:
        # Router 6513998438 on #470: the step pass acquires SC1091 alone, the source code actionlint excludes; an
        # SC1090 is actionlint's own, once. A source is a finding at its workflow line and a named gap, a non-source
        # diagnostic stays actionlint's alone, a clean step adds nothing, and past max_findings the refusal counts
        # every finding.
        workflow = _BASE_FILES[".github/workflows/w.yml"] + (
            "      - run: |\n          echo ok\n          source ./b.sh\n"
            '      - run: echo "$BAR"\n'
            '      - run: . "$BAR"\n'
        )
        inventory = self._with({".github/workflows/w.yml": workflow})
        self.assertEqual(
            [
                (".github/workflows/w.yml", 10, "SC2086"),
                (".github/workflows/w.yml", 14, "SC1091"),
                (".github/workflows/w.yml", 16, "SC1090"),
            ],
            sorted(
                (f["path"], f["range"]["start_line"], f["rule"])
                for f in inventory["findings"]
                if f["tool"]["id"] == "actionlint"
            ),
        )
        for line in (14, 16):
            self.assertIn(
                f".github/workflows/w.yml:{line}: a sourced file, never followed",
                self._rows(inventory)["workflow-lint"]["reason"],
            )
        count = len(inventory["findings"])
        # Built before the block, so only the collection can raise (Sonar S5778).
        limits = self.module.DiagnosticLimits(max_findings=count - 1)
        with self.assertRaisesRegex(
            self.module.QualityEvidenceError,
            f"budget: {count} findings exceed max_findings {count - 1};",
        ):
            self._collect(limits=limits)

    def test_a_decoded_step_directive_is_a_named_gap(self) -> None:
        # Codex on #470: the real ShellCheck honours the `#` that a double-quoted `run` decodes from `\x23`, so
        # the step's finding is gone and only the gap names why.
        workflow = _BASE_FILES[".github/workflows/w.yml"] + (
            '      - run: "\\x23 shellcheck disable=all\\necho $BAR"\n'
        )
        inventory = self._with({".github/workflows/w.yml": workflow})
        self.assertNotIn(
            (".github/workflows/w.yml", 12), self._at(inventory, "actionlint")
        )
        row = self._rows(inventory)["workflow-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn(
            ".github/workflows/w.yml:12: a ShellCheck directive, never honoured as clean",
            row["reason"],
        )

    def test_actionlint_never_follows_a_source_outside_its_inputs(self) -> None:
        # PAO 6520190154 on #389: actionlint 1.7.12 always passes `-x` to ShellCheck, which then opened a sourced file
        # outside its inputs (measured with this witness). A FIFO outside the repository records any reader.
        fifo = Path(self.directory.name) / "outside-witness.sh"
        os.mkfifo(fifo)
        opened = threading.Event()

        def write() -> None:
            try:
                with open(fifo, "w", encoding="utf-8") as stream:
                    opened.set()
                    stream.write("WITNESS=1\n")
            except OSError:
                pass  # released by the test itself, after the collection

        threading.Thread(target=write, daemon=True).start()
        workflow = _BASE_FILES[".github/workflows/w.yml"] + f"      - run: . {fifo}\n"
        try:
            row = self._rows(self._with({".github/workflows/w.yml": workflow}))[
                "workflow-lint"
            ]
        finally:
            was_opened = opened.wait(0.5)
            os.close(os.open(fifo, os.O_RDONLY | os.O_NONBLOCK))
        self.assertFalse(was_opened, "a sourced file outside the inputs was read")
        self.assertIn(
            ".github/workflows/w.yml:12: a sourced file, never followed", row["reason"]
        )

    def test_a_hadolint_pragma_is_a_named_gap_and_its_finding_is_kept(self) -> None:
        inventory = self._with(
            {
                "docker/Dockerfile.pragma": (
                    "FROM debian:12\n# hadolint ignore=DL3008\nRUN apt-get install -y curl\n"
                )
            }
        )
        row = self._rows(inventory)["dockerfile-lint"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("docker/Dockerfile.pragma:2", row["reason"])
        rules = {
            f["rule"]
            for f in inventory["findings"]
            if f["path"] == "docker/Dockerfile.pragma"
        }
        self.assertIn("DL3008", rules)

    def test_a_step_under_another_shell_is_a_named_gap(self) -> None:
        workflow = _BASE_FILES[".github/workflows/w.yml"] + (
            "      - shell: pwsh\n        run: Write-Host $env:FOO\n"
        )
        row = self._rows(self._with({".github/workflows/w.yml": workflow}))[
            "workflow-lint"
        ]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("'pwsh'", row["reason"])

    def test_another_shell_s_script_is_a_named_gap(self) -> None:
        row = self._rows(self._with({"ci/fishy": "#!/usr/bin/env fish\necho hi\n"}))[
            "shell-lint"
        ]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn("ci/fishy", row["reason"])

    def test_an_unsupported_gitlab_construct_is_a_named_gap(self) -> None:
        gitlab = "include:\n  - local: other.yml\n" + _BASE_FILES[".gitlab-ci.yml"]
        row = self._rows(self._with({".gitlab-ci.yml": gitlab}))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn("include", row["reason"])


class RealToolIdentityTests(_RealToolFixture):
    def _shell_row(
        self, root: Path, profile: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        inventory = self._collect(root, profile)
        self.assertFalse(self._at(inventory, "shellcheck"))
        self.assertNotEqual("COMPLETE", inventory["coverage"]["status"])
        return self._rows(inventory)["shell-lint"]

    def test_an_altered_executable_never_runs(self) -> None:
        root = self._copied_root(("shellcheck",))
        with (root / "shellcheck").open("ab") as handle:
            handle.write(b"\0")
        self.assertIn("is not its pinned bytes", self._shell_row(root)["reason"])

    def test_a_linked_executable_never_runs(self) -> None:
        root = Path(self.directory.name) / "linked-tools"
        root.mkdir()
        (root / "shellcheck").symlink_to(self.qualified_root / "shellcheck")
        self.assertIn("is reached through a link", self._shell_row(root)["reason"])

    def test_a_missing_executable_never_runs(self) -> None:
        root = self._copied_root(("hadolint",))
        self.assertIn("tool shellcheck is unavailable", self._shell_row(root)["reason"])

    def test_the_right_digest_of_the_wrong_tool_fails_its_version(self) -> None:
        root = self._copied_root(("actionlint",))
        (root / "actionlint").rename(root / "shellcheck")
        profile = copy.deepcopy(self.profile)
        profile["tools"]["shellcheck"]["sha256"][platform.machine()] = profile["tools"][
            "actionlint"
        ]["sha256"][platform.machine()]
        self.assertIn(
            "its version is not its pin", self._shell_row(root, profile)["reason"]
        )


class RealToolVerdictTests(_RealToolFixture):
    def test_every_real_finding_reaches_one_readback_and_denies_m17(self) -> None:
        inventory = self._collect()
        readbacks = analyzer_inventory.readbacks(
            inventory,
            repository="ktogias/gnostoa",
            pull_number=1,
            requested_head=self.head,
            observed_at="2026-10-30T00:00:00Z",
        )
        for readback in readbacks:
            self.assertEqual(readback, parse_readback(readback))
        diff, full = readbacks
        ids = [f["id"] for f in inventory["findings"]]
        self.assertEqual(
            sorted(ids), sorted(f["id"] for r in readbacks for f in r["findings"])
        )
        self.assertIn("ci/unchanged.sh", {f["path"] for f in full["findings"]})
        self.assertIn("ci/changed.sh", {f["path"] for f in diff["findings"]})
        evidence = _evidence()
        evidence["analyzer_findings"] = {
            "coverage": "COMPLETE",
            "findings": [
                {"item": "project-diff", "id": f["id"], "message": f["message"]}
                for f in diff["findings"]
            ],
        }
        reasons = _failed(_verdict(evidence))["M17"]
        plural = "" if len(diff["findings"]) == 1 else "s"
        self.assertIn(
            f"{len(diff['findings'])} unresolved analyzer finding{plural}", reasons
        )
