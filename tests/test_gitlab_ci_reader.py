"""The gitlab-script family (#389 H-PYSEC-2; Decision 0122): its bounded reader, tools/gitlab_ci_reader.py, and its
run in the collector, through the families' own fixture."""

from __future__ import annotations

import itertools
from pathlib import Path
from unittest.mock import patch

from tests.quality_evidence_fixtures import _calling_through
from tests.test_quality_evidence_profile import _original
from tests.test_quality_evidence_tool_families import (
    _GITLAB,
    _SC_NATIVE,
    _sourced,
    _ToolFamilyFixture,
)
from tools import gitlab_ci_reader


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

    def test_an_out_of_range_escape_is_a_named_gap(self) -> None:
        # cubic on #470: PyYAML's scanner raises ValueError, not a YAMLError, for `\U00110000` (measured).
        self._commit({".gitlab-ci.yml": 'job:\n  script:\n    - "echo \\U00110000"\n'})
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn(".gitlab-ci.yml: unparsable: ValueError", row["reason"])

    def test_a_job_that_is_not_a_mapping_is_a_named_gap(self) -> None:
        # cubic on #470: GitLab runs every visible key that is not a global keyword as a job, whose definition is a
        # mapping; one given any other value was dropped, and the file read as clean. A hidden key is ignored.
        for text in ('job: "echo $A"\n', "job:\n  - echo $A\n", "job:\n"):
            with self.subTest(text=text):
                self._commit({".gitlab-ci.yml": text})
                row = self._rows(self._collect(base=self.base))["gitlab-script"]
                self.assertNotEqual("COMPLETE", row["analysis"])
                self.assertIn(
                    ".gitlab-ci.yml: job 'job' is not a mapping", row["reason"]
                )
        self._commit(
            {".gitlab-ci.yml": '.hidden: "echo"\njob:\n  script:\n    - echo $A\n'}
        )
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertEqual("COMPLETE", row["analysis"], row["reason"])

    def test_a_shared_extends_ancestor_is_resolved_once(self) -> None:
        # Codex on #470: five hidden jobs per level, each extending the five below, were resolved once per
        # occurrence, exponential work in a file of a few kilobytes. Each job now resolves once per file.
        levels = [[f".l{level}j{k}" for k in range(5)] for level in range(6)]
        text = "".join(f"{name}:\n  script:\n    - echo $A\n" for name in levels[0])
        for below, names in itertools.pairwise(levels):
            text += "".join(
                f"{name}:\n  extends: [{', '.join(below)}]\n" for name in names
            )
        text += f"job:\n  extends: [{', '.join(levels[-1])}]\n"
        with patch.object(
            gitlab_ci_reader,
            "_gitlab_resolve",
            spec=True,
            new_callable=_calling_through,
        ) as resolve:
            jobs = gitlab_ci_reader.read_scripts(text)
        self.assertEqual(["job"], list(jobs))
        self.assertLessEqual(resolve.call_count, 200)

    def test_extends_keeps_its_merge_cycle_and_eleven_levels(self) -> None:
        # Controls for the resolution's cache (Codex on #470): they hold before and after it.
        read, unsupported = (
            gitlab_ci_reader.read_scripts,
            gitlab_ci_reader.GitlabUnsupported,
        )

        def chain(ancestors: int, first: str = "") -> str:
            text = ".j0:\n  script:\n    - echo $A\n" + first
            text += "".join(
                f".j{k}:\n  extends: .j{k - 1}\n" for k in range(1, ancestors)
            )
            return text + f"job:\n  extends: .j{ancestors - 1}\n"

        merged = read(".p:\n  script:\n    - echo $A\njob:\n  extends: .p\n")
        self.assertEqual("echo $A", merged["job"][0][0][0])
        with self.assertRaisesRegex(unsupported, "an extends cycle"):
            read(".a:\n  extends: .b\n.b:\n  extends: .a\njob:\n  extends: .a\n")
        self.assertEqual(["job"], list(read(chain(11))))
        # Each text is built before its block, so only the read can raise (Sonar S5778). A job resolved first at a
        # shallow depth still keeps the bound when it is reached deeper.
        for text in (chain(12), chain(12, first="a:\n  extends: .j0\n")):
            with self.subTest(text=text[-40:]), self.assertRaises(unsupported):
                read(text)

    def test_a_gitlab_file_that_is_not_utf8_text_is_a_named_gap(self) -> None:
        # Codex on #470: a replacement decode analyzed a repaired copy and read as clean; the file is read strictly.
        (self.root / ".gitlab-ci.yml").write_bytes(
            b"job:\n  script:\n    - echo \xff\n"
        )
        self._git("commit", "-q", "-am", "not utf-8")
        row = self._rows(self._collect(base=self.base))["gitlab-script"]
        self.assertNotEqual("COMPLETE", row["analysis"])
        self.assertIn(
            ".gitlab-ci.yml: not readable UTF-8 text, never analyzed as a repaired copy",
            row["reason"],
        )

    def test_a_yaml_family_reads_one_strict_snapshot_of_its_file(self) -> None:
        # cubic on #470: _yaml_text checked one read and analyzed a second, replacement-decoded one, and read an
        # unreadable file as an empty document. It decodes the one snapshot it reads, and an unreadable file is None.
        yaml_text = _original(self.module, "_yaml_text")
        (self.root / "w.yml").write_bytes(b"a: \xff\n")
        with self.subTest("one snapshot"):
            with patch.object(Path, "read_bytes", return_value=b"a: b\r\n"):
                snapshot = yaml_text(self.root, "w.yml")
            self.assertEqual("a: b\n", snapshot)
        with self.subTest("unreadable"):
            self.assertIsNone(yaml_text(self.root, "missing.yml"))
