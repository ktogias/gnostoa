"""The gitlab-script family (#389 H-PYSEC-2; Decision 0122): its bounded reader, tools/gitlab_ci_reader.py, and its
run in the collector, through the families' own fixture."""

from __future__ import annotations

from tests.test_quality_evidence_tool_families import (
    _GITLAB,
    _SC_NATIVE,
    _sourced,
    _ToolFamilyFixture,
)


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


class GitlabReaderTests(_ToolFamilyFixture):
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

    def test_the_gitlab_pages_job_is_analyzed(self) -> None:
        # Codex on #470: `pages` is a job, not a reserved key.
        self._commit({".gitlab-ci.yml": "pages:\n  script:\n    - echo $FOO\n"})
        self._collect(base=self.base)
        self.assertEqual(1, len(self._gitlab_analyzed()))

    def test_a_gitlab_item_is_analyzed_as_it_reads(self) -> None:
        # Codex on #470: only a newline ends an analysis line, so a decoded vertical tab stays in its command.
        self._commit(
            {".gitlab-ci.yml": 'job:\n  script:\n    - "echo foo\\vbar $VALUE"\n'}
        )
        self._collect(base=self.base)
        (analyzed,) = self._gitlab_analyzed()
        (body,) = [
            p.read_text(encoding="utf-8")
            for p in self.output.glob(f"diagnostic-*/gitlab-input/{analyzed}")
        ]
        self.assertEqual(
            ["#!/bin/sh", "echo foo\x0bbar $VALUE"], body.rstrip("\n").split("\n")
        )

    def test_a_tagged_gitlab_sequence_is_a_named_gap(self) -> None:
        # Revix on #470: `!reference` is unsupported, in a sequence as in a scalar.
        self._commit(
            {
                ".gitlab-ci.yml": ".setup:\n  script:\n    - echo $A\njob:\n  script:\n    - !reference [.setup, script]\n"
            }
        )
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn("!reference", row["reason"])

    def test_a_sourced_file_in_a_gitlab_script_is_a_named_gap(self) -> None:
        # Claude and cubic on #470: the GitLab family reads shell too, so a source ShellCheck reports, after a `;`
        # as at a line's start, is never followed there either. The answer is the real tool's (qualification).
        self._commit(
            {
                ".gitlab-ci.yml": "job:\n  script:\n    - echo ok; source ./ci/common.sh\n    - . ./ci/more.sh\n"
            }
        )
        self.tool_answers["shellcheck"] = (1, {"comments": [_sourced(2), _sourced(3)]})
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn(".gitlab-ci.yml:3: a sourced file, never followed", row["reason"])
        self.assertIn(".gitlab-ci.yml:4: a sourced file, never followed", row["reason"])

    def test_a_gitlab_key_that_is_not_text_is_a_named_gap(self) -> None:
        # Revix and Codex on #470: `1:` or `yes:` decodes to a number or a boolean, never a job name to read.
        for key in ("1", "yes"):
            with self.subTest(key=key):
                self._commit(
                    {".gitlab-ci.yml": f"{key}:\n  script:\n    - echo $FOO\n"}
                )
                row = self._rows(self._collect(base=self.base))["gitlab-script"]
                self.assertNotEqual("COMPLETE", row["analysis"])
                self.assertIn("a key that is not text", row["reason"])

    def test_a_duplicate_gitlab_key_is_a_named_gap(self) -> None:
        # Revix on #470: a second `script:` would replace the first, whose commands would never be read.
        self._commit(
            {
                ".gitlab-ci.yml": "job:\n  script:\n    - echo $A\n  script:\n    - echo ok\n"
            }
        )
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn("a duplicate key", row["reason"])
