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

    def test_a_gitlab_anchor_or_alias_is_refused_before_composition(self) -> None:
        # Codex and Revix on #470, Router 6513998438: anchors and aliases are refused by task_envelope's bounded
        # preflight before composition, a named gap, so an alias chain never expands.
        chain = ["variables:", "  a0: &a0 [x, x]"]
        chain += [f"  a{n}: &a{n} [*a{n - 1}, *a{n - 1}]" for n in range(1, 19)]
        cases = {
            "an alias chain": (
                "\n".join(chain) + "\njob:\n  script:\n    - echo $A\n",
                "a YAML anchor at line 2",
            ),
            "an alias": ("job:\n  script:\n    - *a\n", "a YAML alias at line 3"),
            "a nesting past the bound": (
                "variables:\n  v: "
                + "[" * 33
                + "]" * 33
                + "\njob:\n  script:\n    - echo $A\n",
                "a nesting deeper than 32 levels at line 2",
            ),
        }
        for case, (text, reason) in cases.items():
            with self.subTest(case=case):
                self._commit({".gitlab-ci.yml": text})
                row = self._rows(self._collect(base=self.base))["gitlab-script"]
                self.assertNotEqual("COMPLETE", row["analysis"])
                self.assertIn(reason, row["reason"])

    def test_a_long_gitlab_job_name_is_analyzed_at_its_lines(self) -> None:
        # Codex on #470: an analysis file is named by numbers only, so no job name can exceed a file name's bound, and
        # each finding still maps back to its job's YAML line.
        self._commit({".gitlab-ci.yml": "j" * 255 + ":\n  script:\n    - echo $A\n"})
        inventory = self._collect(base=self.base)
        self.assertEqual(
            [(".gitlab-ci.yml", 3)],
            [
                (f["path"], f["range"]["start_line"])
                for f in self._findings(inventory, "gitlab-shellcheck")
            ],
        )

    def test_an_unreadable_gitlab_boolean_is_a_named_gap(self) -> None:
        # Codex on #470: PyYAML's boolean constructor raises KeyError for a value it does not know.
        self._commit({".gitlab-ci.yml": "job:\n  script: !!bool invalid\n"})
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn(
            "a tag:yaml.org,2002:bool item that cannot be read at line 2", row["reason"]
        )

    def test_a_gitlab_item_that_is_not_utf8_text_is_a_named_gap(self) -> None:
        # Codex on #470: an escaped lone surrogate decodes, but no analysis copy can hold it.
        self._commit({".gitlab-ci.yml": 'job:\n  script:\n    - "echo \\uD800"\n'})
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn("an item that is not UTF-8 text at line 3", row["reason"])

    def test_a_decoded_gitlab_directive_is_a_named_gap(self) -> None:
        # Codex on #470: `"\x23 shellcheck ..."` hides from the file's lines, but ShellCheck reads the decoded `#`.
        self._commit(
            {
                ".gitlab-ci.yml": 'job:\n  script:\n    - "\\x23 shellcheck disable=all"\n    - echo $V\n'
            }
        )
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertEqual("PARTIAL", row["analysis"])
        self.assertIn(
            ".gitlab-ci.yml:3: a ShellCheck directive, never honoured as clean",
            row["reason"],
        )

    def test_a_line_break_the_file_does_not_count_is_refused_before_reading(
        self,
    ) -> None:
        # Codex on #470: between a key and its mapping, PyYAML's NEL, LS or PS break is valid YAML, so every later
        # YAML line is one past the file's (measured: line 5 for the file's 4); the file is refused first.
        for mark in ("\x85", "\u2028", "\u2029"):
            with self.subTest(mark=repr(mark)):
                self._commit(
                    {
                        ".gitlab-ci.yml": f"variables:{mark}  A: b\njob:\n  script:\n    - echo $A\n"
                    }
                )
                inventory = self._collect(base=self.base)
                self.assertEqual(
                    [],
                    [
                        f
                        for f in self._findings(inventory, "gitlab-shellcheck")
                        if f["path"] == ".gitlab-ci.yml"
                    ],
                )
                self.assertIn(
                    ".gitlab-ci.yml: a NEL, LS or PS line break at line 1",
                    self._rows(inventory)["gitlab-script"]["reason"],
                )
