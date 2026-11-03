"""What other test modules share from tests/test_quality_evidence_tool_families.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.quality_evidence_fixtures import _DiagnosticInventoryFixture
from tools.quality_evidence import DiagnosticLimits

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


def _sourced(line: int) -> dict[str, object]:
    """ShellCheck's own record of a source it does not follow."""
    message = "Not following: ./lib.sh was not specified as input (see shellcheck -x)."
    return dict(_SC_NATIVE, line=line, endLine=line, code=1091, message=message)


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


def _shellcheck_answer(
    command: list[str], status: int | None, body: dict[str, Any]
) -> tuple[int | None, dict[str, Any]]:
    """ShellCheck's answer to `command`: each comment names the file it was given, the first one here, and an
    `--include` keeps its own codes alone, exiting 0 when none is left (measured on the pinned 0.11.0, #389 round 12)."""
    given = command[command.index("--") + 1] if "--" in command else command[-1]
    codes = [a[10:].split(",") for a in command if a.startswith("--include=")]
    comments = [
        dict(c, file=given)
        for c in body["comments"]
        if not codes or f"SC{c['code']}" in codes[0]
    ]
    return (0 if codes and not comments else status), {"comments": comments}


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

    def _tool(self, command: list[str]) -> str | None:
        for name in ("shellcheck", "hadolint", "actionlint"):
            if Path(command[0]).name == name:
                return name
        return None

    def _fake_run(
        self,
        command: list[str],
        *,
        cwd: Path,
        environment: dict[str, str],
        report: Path,
        deadline: float,
        limits: DiagnosticLimits,
    ) -> tuple[int | None, str | None, bool]:
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
            status, body = _shellcheck_answer(command, status, body)
        report.write_text(
            body if isinstance(body, str) else json.dumps(body), encoding="utf-8"
        )
        return status, None, False

    def _collect(
        self, profile: dict[str, Any] | None = None, **options: object
    ) -> dict[str, Any]:
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

    def _rows(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
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

    def _findings(self, inventory: dict[str, Any], tool: str) -> list[dict[str, Any]]:
        return [f for f in inventory["findings"] if f["tool"]["id"] == tool]

    def _commit(self, files: dict[str, str]) -> None:
        for name, body in files.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "round two")

    def _gitlab_analyzed(self) -> list[str]:
        command = next(
            c for c, _cwd, _env in self._commands_of("shellcheck") if "--shell=sh" in c
        )
        return command[command.index("--") + 1 :]
