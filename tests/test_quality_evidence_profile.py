"""The diagnostic inventory's protected family profile (#389 A0-MP1 slice 1, owner A
6384969093). The producer tree's own `policy/diagnostic-profile.yaml` decides, before
any producer runs, which families run, with which selectors, on which files: a FULL
scope, plus a DIFF scope's changed files, whole, and for complexity only the functions
a change adds a line to. Nothing obtained is dropped afterwards. Each family has its
own coverage row, and the composite is their conjunction with the inventory's shared
gaps. A profile in the analyzed tree is never read."""

from __future__ import annotations

import copy
import inspect
import json
import os
import stat
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from quality_evidence_fixtures import _DiagnosticInventoryFixture

ROOT = Path(__file__).resolve().parent.parent

# The admitted contract's values (Router 6381924685's risk table, from r2 6381493734):
# typing and protected access on every changed Python file and on non-test FULL,
# literal secrets everywhere, complexity above 15 on changed functions only. PLR6301
# and SIM117 are not selected. Unactivated: no claim reads it yet.
PROTECTED = {
    "schema": "gnostoa-diagnostic-profile/v1",
    "id": "gnostoa.project-risk",
    "scopes": {"all": {"exclude": []}, "non-test": {"exclude": ["tests/"]}},
    "families": [
        {"id": "typing", "producer": "mypy", "diff": "all", "full": "non-test"},
        {
            "id": "protected-access",
            "producer": "ruff",
            "select": ["SLF001"],
            "diff": "all",
            "full": "non-test",
        },
        {
            "id": "literal-secrets",
            "producer": "ruff",
            "select": ["S106"],
            "diff": "all",
            "full": "all",
        },
        {
            "id": "complexity",
            "producer": "complexity",
            "reported_above": 15,
            "diff": "all",
            "full": None,
        },
    ],
}
FAMILIES = {"typing", "protected-access", "literal-secrets", "complexity"}


def _files(command: list[str]) -> list[str]:
    """The paths a producer command was given: everything after `--`."""
    return command[command.index("--") + 1 :] if "--" in command else []


def _select(command: list[str]) -> set[str]:
    if "--select" not in command:
        return set()
    return set(command[command.index("--select") + 1].split(","))


class DiagnosticProfileTests(_DiagnosticInventoryFixture):
    """The protected route's inventory: collected with no profile argument, so that
    the producer tree's own profile governs. The fake Ruff answers as Ruff does."""

    def setUp(self) -> None:
        super().setUp()
        self.ruff_exit, self.ruff_as_ruff = None, True

    def _protected(self, **options) -> dict:
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            path = self.module.collect_diagnostic_inventory(
                self.root, self.output, **options
            )
        self.run_directory = Path(path).parent
        return self._read(path)

    def _inventory_with(self, profile: dict, **options) -> dict:
        """The private path's inventory under a supplied profile."""
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            path = self.module._collect_diagnostic_inventory(
                self.root, self.output, profile=profile, **options
            )
        return self._read(path)

    def _producer_commands(self, producer: str) -> list[list[str]]:
        return [
            c
            for c, _, _ in self.commands
            if producer in c and "--version" not in c and "-m" in c
        ]

    def _ruff_files(self, code: str) -> set[str]:
        """Every file a Ruff run selecting `code` was given."""
        return {
            f
            for c in self._producer_commands("ruff")
            if code in _select(c)
            for f in _files(c)
        }

    def _mypy_files(self) -> set[str]:
        """Every file mypy was given, by its path from the analyzed root."""
        given = set()
        for command, cwd, _ in self.commands:
            if "mypy" in command and "--version" not in command:
                group = self._group(cwd)
                prefix = "" if group == "." else group + "/"
                given |= {prefix + f for f in _files(command)}
        return given

    def _rows(self, inventory: dict) -> dict[str, dict]:
        rows = inventory.get("families", [])
        return {row["family"]: row for row in rows}

    def _change(self, path: str, old: str, new: str, after: str = "") -> None:
        source = self.root / path
        text = source.read_text(encoding="utf-8")
        start = text.index(after) if after else 0
        source.write_text(
            text[:start] + text[start:].replace(old, new, 1), encoding="utf-8"
        )
        self._git("commit", "-q", "-am", "head")

    # RED on protected main: it runs every selector on every file.

    def test_typing_and_protected_access_run_on_non_test_full_only(self) -> None:
        self._protected()
        typed = self._mypy_files()
        self.assertIn("tools/sample.py", typed)
        self.assertEqual(set(), {f for f in typed if f.startswith("tests/")})
        self.assertIn("tools/sample.py", self._ruff_files("SLF001"))
        self.assertEqual(
            set(), {f for f in self._ruff_files("SLF001") if f.startswith("tests/")}
        )
        self.assertIn("tests/test_sample.py", self._ruff_files("S106"))

    def test_the_excluded_rules_are_never_run(self) -> None:
        self.ruff_records.append(
            self._ruff("tools/sample.py", 1, 1, "SIM117", "Use a single `with`")
        )
        inventory = self._protected()
        selected = set().union(*(_select(c) for c in self._producer_commands("ruff")))
        self.assertEqual({"SLF001", "S106"}, selected)
        self.assertEqual(
            [],
            [
                f
                for f in inventory["findings"]
                if f.get("rule") in {"PLR6301", "SIM117"}
            ],
        )

    def test_a_changed_file_is_acquired_whole_and_an_unchanged_test_file_is_not(
        self,
    ) -> None:
        self._change(
            "tests/test_sample.py",
            '"""Diagnostic fixture: test side."""',
            '"""Diagnostic fixture: test side, changed."""',
        )
        inventory = self._protected(base=self.base)
        self.assertIn("tests/test_sample.py", self._mypy_files())
        self.assertIn("tests/test_sample.py", self._ruff_files("SLF001"))
        self.assertNotIn("tests/fixtures/one/baseline.py", self._mypy_files())
        self.assertNotIn("tests/fixtures/one/baseline.py", self._ruff_files("SLF001"))
        # Whole: the findings on its unchanged lines are obtained, so listed, outside
        # the DIFF projection (the PAO's R1 on 6387305292).
        for tool, rule, line in (
            ("mypy", "arg-type", self.lines["typing"]),
            ("ruff", "SLF001", self.lines["private"]),
        ):
            listed = self._find(inventory, tool, rule, "tests/test_sample.py", line)
            self.assertEqual([False], [f["native"]["in_diff"] for f in listed], rule)

    def test_complexity_is_acquired_only_for_a_function_a_change_adds_a_line_to(
        self,
    ) -> None:
        self._change("tools/sample.py", "total = 0", "total = 1", after="def sixteen")
        inventory = self._protected(base=self.base)
        listed = [f for f in inventory["findings"] if f["tool"]["id"] == "complexity"]
        self.assertEqual(
            [(self.lines["sixteen"], True)],
            [(f["range"]["start_line"], f["native"]["in_diff"]) for f in listed],
        )

    def test_each_family_has_a_row_and_the_composite_names_the_incomplete_one(
        self,
    ) -> None:
        # mypy aborts. Nothing changed, so complexity has no target: a complete
        # discovery proves the empty set, unlike a failed one (the PAO's R2).
        self.mypy_records, self.mypy_exit = {}, {".": 2}
        inventory = self._protected(base=self.base)
        rows = self._rows(inventory)
        self.assertEqual(FAMILIES, set(rows))
        self.assertEqual("INCOMPLETE", rows["typing"]["analysis"])
        self.assertEqual("COMPLETE", rows["protected-access"]["analysis"])
        self.assertEqual("COMPLETE", rows["literal-secrets"]["analysis"])
        self.assertEqual(
            ("COMPLETE", 0, 0),
            tuple(rows["complexity"][k] for k in ("analysis", "targets", "analyzed")),
        )
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertIn("family typing INCOMPLETE", inventory["coverage"]["reason"])
        self.assertNotIn("family literal-secrets", inventory["coverage"]["reason"])

    def test_a_partial_family_is_named_in_the_composite(self) -> None:
        # The composite is the families' conjunction: a PARTIAL row is named, as an
        # INCOMPLETE one is (Revix on #459).
        self.mypy_records = {
            "tools/sample.py": [
                self._mypy(
                    "tools/sample.py",
                    1,
                    0,
                    "import-not-found",
                    'Cannot find implementation or library stub for module named "gone"',
                )
            ]
        }
        inventory = self._protected(base=self.base)
        self.assertEqual("PARTIAL", self._rows(inventory)["typing"]["analysis"])
        self.assertIn(
            "family typing PARTIAL: 1 files with unresolved imports",
            inventory["coverage"]["reason"],
        )

    def test_an_unresolved_import_in_a_followed_file_is_the_family_s(self) -> None:
        # mypy follows an import from its target into a file it was not given, and
        # cannot resolve one there: its own run is PARTIAL (CodeAnt on #459).
        self.mypy_records = {
            "tools/sample.py": [
                self._mypy(
                    "tests/test_sample.py",
                    1,
                    0,
                    "import-not-found",
                    'Cannot find implementation or library stub for module named "gone"',
                )
            ]
        }
        rows = self._rows(self._protected(base=self.base))
        self.assertEqual("PARTIAL", rows["typing"]["analysis"])

    def test_a_mode_only_change_keeps_the_known_changed_files(self) -> None:
        # Complexity cannot read added lines from a mode-only change; only its own
        # row is unknown, and typing still acquires the changed test file (CodeAnt on
        # #459).
        source = self.root / "tests" / "test_sample.py"
        source.write_text(
            source.read_text(encoding="utf-8").replace(
                '"""Diagnostic fixture: test side."""',
                '"""Diagnostic fixture: test side, changed."""',
            ),
            encoding="utf-8",
        )
        # Owner-only: the executable bit Git records is the whole mode change.
        os.chmod(self.root / "tools" / "sample.py", stat.S_IRWXU)
        self._git("commit", "-q", "-am", "a mode-only change beside a text one")
        rows = self._rows(self._protected(base=self.base))
        self.assertIn("tests/test_sample.py", self._mypy_files())
        self.assertEqual("COMPLETE", rows["typing"]["analysis"])
        self.assertEqual("INCOMPLETE", rows["complexity"]["analysis"])

    def test_a_profile_without_a_launched_producer_observes_no_environment(
        self,
    ) -> None:
        # Only mypy and Ruff run as launched processes; the metric runs in process,
        # so a complexity-only profile observes no environment (CodeAnt on #459).
        profile = {
            "schema": "gnostoa-diagnostic-profile/v1",
            "id": "complexity-only",
            "scopes": {"all": {"exclude": []}},
            "families": [
                {
                    "id": "complexity",
                    "producer": "complexity",
                    "reported_above": 15,
                    "diff": "all",
                    "full": "all",
                }
            ],
        }
        self._inventory_with(profile)
        self.assertNotIn(self._observation_command(), [c for c, _, _ in self.commands])

    def test_the_composite_counts_only_files_a_family_analyzed(self) -> None:
        # A tracked file no family targets is not analyzed, so not counted (CodeAnt
        # on #459).
        profile = copy.deepcopy(PROTECTED)
        profile["families"] = [profile["families"][0]]
        profile["families"][0]["diff"] = None
        inventory = self._inventory_with(profile)
        self.assertEqual(2, inventory["coverage"]["count"])
        self.assertEqual(4, inventory["coverage"]["total"])

    def test_one_unreadable_file_never_withholds_another_s_functions(self) -> None:
        # Each file's added lines are its own: a mode-only change to one complexity
        # target leaves only that file unanalyzed, named, while a changed function in
        # another is still measured (Claude on #459).
        self._change("tools/sample.py", "total = 0", "total = 1", after="def sixteen")
        os.chmod(self.root / "tools" / "__init__.py", stat.S_IRWXU)
        self._git("commit", "-q", "-am", "a mode-only change beside a text one")
        inventory = self._protected(base=self.base)
        listed = [f for f in inventory["findings"] if f["tool"]["id"] == "complexity"]
        self.assertEqual(
            [self.lines["sixteen"]], [f["range"]["start_line"] for f in listed]
        )
        unanalyzed = {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }
        self.assertEqual(["tools/__init__.py"], sorted(unanalyzed))
        row = self._rows(inventory)["complexity"]
        self.assertEqual(
            ("INCOMPLETE", 2, 1), (row["analysis"], row["targets"], row["analyzed"])
        )

    def test_the_changed_names_are_scanned_once_for_acquisition(self) -> None:
        # One name scan for the acquisition, whatever the number of complexity
        # targets, and one for the annotation: never one per target (cubic on #459).
        self._change("tools/sample.py", "total = 0", "total = 1", after="def sixteen")
        (self.root / "tools" / "__init__.py").write_text("X = 1\n", encoding="utf-8")
        self._git("commit", "-q", "-am", "two changed complexity targets")
        real = self.module._diagnostic_git
        scans = []

        def counting(root, deadline, *arguments, **options):
            if "--name-only" in arguments:
                scans.append(arguments)
            return real(root, deadline, *arguments, **options)

        with patch.object(self.module, "_diagnostic_git", side_effect=counting):
            self._protected(base=self.base)
        self.assertEqual(2, len(scans))

    def test_a_family_the_findings_budget_stopped_targeted_nothing(self) -> None:
        # Past the findings budget no later family starts, and the refusal follows;
        # the families it stopped never count as having targeted anything (Claude on
        # #459).
        profile = self.module._validated_profile(
            {
                "schema": "gnostoa-diagnostic-profile/v1",
                "id": "budget",
                "scopes": {"all": {"exclude": []}, "tests": {"exclude": ["tools/"]}},
                "families": [
                    {"id": "typing", "producer": "mypy", "diff": None, "full": "tests"},
                    {
                        "id": "complexity",
                        "producer": "complexity",
                        "reported_above": 15,
                        "diff": None,
                        "full": "all",
                    },
                ],
            }
        )
        run = Path(self.directory.name) / "run"
        run.mkdir()
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            result = self.module._run_producers(
                self.root,
                run,
                sorted(p for p in self.files if p.endswith(".py")),
                self.module.DiagnosticLimits(max_findings=0),
                [],
                time.monotonic() + 30,
                profile,
                self.module._Changes(frozenset(), {}),
            )
        self.assertEqual(["typing"], [row["family"] for row in result.families])
        self.assertEqual(
            {"tests/test_sample.py", "tests/fixtures/one/baseline.py"}, result.targeted
        )

    def test_an_unknown_comparison_never_makes_a_diff_family_complete(self) -> None:
        for options in ({}, {"base": "0" * 40}):
            with self.subTest(options=options):
                self.commands.clear()
                rows = self._rows(self._protected(**options))
                self.assertEqual(FAMILIES, set(rows))
                # Its changed files are unknown: typing's tests, complexity's all. So
                # is how many targets there are, never a count of the known part
                # (CodeAnt on #459).
                self.assertEqual("INCOMPLETE", rows["typing"]["analysis"])
                self.assertEqual("INCOMPLETE", rows["complexity"]["analysis"])
                self.assertEqual("COMPLETE", rows["literal-secrets"]["analysis"])
                self.assertEqual(
                    [None, None], [rows[f]["targets"] for f in ("typing", "complexity")]
                )
                self.assertEqual(2, rows["typing"]["analyzed"])

    def test_a_profile_in_the_analyzed_tree_is_never_read(self) -> None:
        planted = copy.deepcopy(PROTECTED)
        planted["families"][1]["select"] = ["SLF001", "PLR6301"]
        planted["scopes"]["non-test"]["exclude"] = []
        (self.root / "policy").mkdir()
        (self.root / "policy" / "diagnostic-profile.yaml").write_text(
            json.dumps(planted), encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "plant a profile")
        inventory = self._protected()
        selected = set().union(*(_select(c) for c in self._producer_commands("ruff")))
        self.assertNotIn("PLR6301", selected)
        self.assertEqual(
            set(), {f for f in self._mypy_files() if f.startswith("tests/")}
        )
        from tools.knowledge_common import load_yaml
        from tools.review_model import canonical_digest

        own = load_yaml(ROOT / "policy" / "diagnostic-profile.yaml")
        self.assertEqual(
            canonical_digest(own),
            (inventory["configuration"].get("profile") or {}).get("digest"),
        )

    def test_a_kit_root_naming_the_analyzed_tree_never_governs(self) -> None:
        # The configurable kit locator accepts any tree holding its three markers, the
        # analyzed one included: it locates a toolkit, never authorizes a profile (the
        # PAO's 6387738095 on #389). The producer tree's own profile still governs.
        planted = copy.deepcopy(PROTECTED)
        planted["families"][1]["select"] = ["SLF001", "PLR6301"]
        for marker, text in (
            ("pyproject.toml", "[project]\nname = 'planted'\n"),
            ("core/profile.yaml", "id: planted\n"),
            ("schemas/profile.schema.json", "{}\n"),
            ("policy/diagnostic-profile.yaml", json.dumps(planted)),
        ):
            (self.root / marker).parent.mkdir(parents=True, exist_ok=True)
            (self.root / marker).write_text(text, encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "a marker-complete analyzed tree")
        with patch.dict(os.environ, {"KNOWLEDGE_KIT_ROOT": str(self.root)}):
            inventory = self._protected()
        selected = set().union(*(_select(c) for c in self._producer_commands("ruff")))
        self.assertNotIn("PLR6301", selected)
        from tools.knowledge_common import load_yaml
        from tools.review_model import canonical_digest

        own = load_yaml(ROOT / "policy" / "diagnostic-profile.yaml")
        self.assertEqual(
            canonical_digest(own),
            inventory["configuration"]["profile"]["digest"],
        )

    def test_a_kit_root_naming_the_producer_tree_is_kept(self) -> None:
        with patch.dict(os.environ, {"KNOWLEDGE_KIT_ROOT": str(ROOT)}):
            inventory = self._protected()
        from tools.knowledge_common import load_yaml
        from tools.review_model import canonical_digest

        own = load_yaml(ROOT / "policy" / "diagnostic-profile.yaml")
        self.assertEqual(
            canonical_digest(own),
            inventory["configuration"]["profile"]["digest"],
        )

    # Characterization, green on protected main and kept: nothing obtained is
    # dropped, and no profile promotes the source binding.

    def test_an_obtained_finding_outside_every_selected_scope_stays_listed(
        self,
    ) -> None:
        # mypy follows an import from the non-test file it was given into a test
        # module, and reports there (the PAO's R4).
        followed = self._mypy(
            "tests/test_sample.py", self.lines["typing"], 11, "arg-type", "followed"
        )
        self.mypy_records = {"tools/sample.py": [followed]}
        inventory = self._protected()
        self.assertEqual(
            1,
            len(
                self._find(
                    inventory,
                    "mypy",
                    "arg-type",
                    "tests/test_sample.py",
                    self.lines["typing"],
                )
            ),
        )

    def test_a_family_the_analysis_never_reached_is_incomplete(self) -> None:
        # The tree is never staged: no family ran, and none is COMPLETE by omission
        # (the PAO's R2 on #389 6387305292).
        with patch.object(self.module, "_stage", return_value="not staged here"):
            rows = self._rows(self._protected(base=self.base))
        self.assertEqual(FAMILIES, set(rows))
        self.assertEqual(
            {("INCOMPLETE", None, "never analyzed")},
            {(r["analysis"], r["targets"], r["reason"]) for r in rows.values()},
        )

    def test_no_profile_promotes_the_source_binding(self) -> None:
        inventory = self._protected(base=self.base)
        self.assertEqual("UNVERIFIED", inventory["source"]["source_binding"])
        self.assertEqual("EXPERIMENTAL", inventory["status"])
        self.assertEqual("INCOMPLETE", inventory["coverage"]["status"])
        self.assertIn("source binding UNVERIFIED", inventory["coverage"]["reason"])


class DiagnosticProfileContractTests(_DiagnosticInventoryFixture):
    """The profile's own contract: absent on protected main, so these fail there by
    absence, which is not a semantic RED; their falsifiers are mutations of the
    implementation (#389 A0-MP1)."""

    def test_the_protected_profile_holds_the_admitted_contract(self) -> None:
        self.assertEqual(PROTECTED, self.module.load_diagnostic_profile())

    def test_the_public_collector_takes_no_profile(self) -> None:
        # Only the producer tree's profile selects what the public collector runs; a
        # supplied one is the private path's, for tests and labelled qualification
        # variants (cubic and Revix on #459).
        parameters = inspect.signature(
            self.module.collect_diagnostic_inventory
        ).parameters
        self.assertNotIn("profile", parameters)

    def test_the_profile_s_origin_is_recorded(self) -> None:
        supplied = self._inventory()
        self.assertEqual("argument", supplied["configuration"]["profile"]["origin"])
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            own = self._read(
                self.module.collect_diagnostic_inventory(self.root, self.output)
            )
        self.assertEqual("producer-tree", own["configuration"]["profile"]["origin"])

    def test_the_inventory_records_the_profile_it_ran(self) -> None:
        inventory = self._inventory()
        record = inventory["configuration"]["profile"]
        from tools.review_model import canonical_digest

        self.assertEqual(
            canonical_digest(record["value"]),
            record["digest"],
        )

    def test_the_profile_s_threshold_governs_the_metric(self) -> None:
        profile = copy.deepcopy(PROTECTED)
        profile["families"][3].update(reported_above=16, full="all")
        inventory = self._inventory(profile=profile)
        listed = {
            f["range"]["start_line"]
            for f in inventory["findings"]
            if f["tool"]["id"] == "complexity"
        }
        self.assertEqual({self.lines["branchy"], self.lines["outer"]}, listed)

    def test_a_profile_with_a_duplicate_key_is_refused(self) -> None:
        path = Path(self.directory.name) / "profile.yaml"
        path.write_text(
            "schema: gnostoa-diagnostic-profile/v1\nid: a\nid: b\n", encoding="utf-8"
        )
        with self.assertRaises(self.module.QualityEvidenceError):
            self.module.load_diagnostic_profile(path)

    def test_a_default_profile_resolving_outside_the_producer_tree_is_refused(
        self,
    ) -> None:
        # A symlink at the default path is never followed out of the producer tree
        # (CodeAnt on #459).
        # The link is the producer tree's own default path, and its target lies
        # outside that tree (CodeAnt on #459).
        planted = Path(self.directory.name) / "planted.yaml"
        planted.write_text(json.dumps(PROTECTED), encoding="utf-8")
        producer = Path(self.directory.name) / "producer"
        (producer / "policy").mkdir(parents=True)
        link = producer / "policy" / "diagnostic-profile.yaml"
        link.symlink_to(planted)
        with (
            patch.object(self.module, "_PRODUCER_TREE", producer),
            patch.object(self.module, "_PROFILE", link),
        ):
            with self.assertRaises(self.module.QualityEvidenceError):
                self.module.load_diagnostic_profile()

    def test_a_missing_protected_profile_is_refused_before_anything_runs(self) -> None:
        # An installed wheel ships the collector without policy/, as every policy file
        # is data of the source tree: the collection then fails closed (cubic on #459).
        absent = self.module._PRODUCER_TREE / "policy" / "absent-profile.yaml"
        with patch.object(self.module, "_PROFILE", absent):
            with self.assertRaises(self.module.QualityEvidenceError):
                self.module.collect_diagnostic_inventory(self.root, self.output)
        self.assertEqual([], self.commands)
        self.assertFalse(self.output.exists() and any(self.output.iterdir()))

    def test_a_default_profile_that_cannot_be_resolved_is_refused(self) -> None:
        # A link loop at the default path fails its resolution, before any read: that
        # is a refusal too, never a raw error (Revix on #459).
        first = Path(self.directory.name) / "loop-a.yaml"
        second = Path(self.directory.name) / "loop-b.yaml"
        first.symlink_to(second)
        second.symlink_to(first)
        with patch.object(self.module, "_PROFILE", first):
            with self.assertRaises(self.module.QualityEvidenceError) as raised:
                self.module.load_diagnostic_profile()
        # The refusal names the failure by its type, never a path or the text it
        # carries (Revix's sanitized-error-diagnostics on #459).
        self.assertNotIn(self.directory.name, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)

    def test_a_profile_that_is_not_utf_8_is_refused(self) -> None:
        path = Path(self.directory.name) / "profile.yaml"
        path.write_bytes(b"schema: \xff\xfe\n")
        with self.assertRaises(self.module.QualityEvidenceError) as raised:
            self.module.load_diagnostic_profile(path)
        self.assertEqual(
            "cannot load the diagnostic profile: UnicodeDecodeError",
            str(raised.exception),
        )
        self.assertIsNone(raised.exception.__cause__)

    def test_a_malformed_profile_is_refused_before_any_producer_runs(self) -> None:
        cases = {
            "schema": lambda p: p.update(schema="gnostoa-diagnostic-profile/v0"),
            "unknown key": lambda p: p.update(owner="anyone"),
            "producer": lambda p: p["families"][0].update(producer="pylint"),
            "scope": lambda p: p["families"][1].update(diff="tests-only"),
            "duplicate id": lambda p: p["families"].append(
                {**p["families"][1], "select": ["PLR6301"]}
            ),
            "second mypy": lambda p: p["families"].append(
                {"id": "typing-2", "producer": "mypy", "diff": "all", "full": None}
            ),
            "rule twice": lambda p: p["families"][2].update(select=["SLF001"]),
            "unknown rule": lambda p: p["families"][1].update(select=["ALL"]),
            "no selector": lambda p: p["families"][1].update(select=[]),
            "threshold": lambda p: p["families"][3].update(reported_above=True),
            "absolute": lambda p: p["scopes"]["non-test"].update(exclude=["/tests/"]),
            "not a directory": lambda p: p["scopes"]["non-test"].update(
                exclude=["tests"]
            ),
            "parent": lambda p: p["scopes"]["non-test"].update(exclude=["../tests/"]),
            "nothing run": lambda p: p["families"][0].update(diff=None, full=None),
            # A pattern's $ also matches before a trailing newline (Revix on #459).
            "profile id newline": lambda p: p.update(id="gnostoa.project-risk\n"),
            "family id newline": lambda p: p["families"][0].update(id="typing\n"),
            "scope name newline": lambda p: p["scopes"].update(
                {"later\n": {"exclude": []}}
            ),
            "exclude newline": lambda p: p["scopes"]["non-test"].update(
                exclude=["tests/\n"]
            ),
        }
        for name, change in cases.items():
            profile = copy.deepcopy(PROTECTED)
            change(profile)
            with self.subTest(case=name):
                self.commands.clear()
                with self.assertRaises(self.module.QualityEvidenceError):
                    self._inventory(profile=profile)
                self.assertEqual([], self.commands)


if __name__ == "__main__":
    unittest.main()
