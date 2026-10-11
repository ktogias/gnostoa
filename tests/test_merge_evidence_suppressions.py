"""Suppressions (M13) and trust-root changes (M15) in the merge evidence (#407,
slice 1b.3b-4, admitted in #325 6113092417 with the contract 6112833932).

The adapter reads both from the exact base-to-head comparison L1 already
collects, against two declarations read from the protected target: the
suppression markers and the trust-root patterns. A marker in an added line is
reported with its head line and its same-line reason; a changed trust root is
reported with every name it has. Anything the comparison does not show
completely leaves the observation incomplete, never an empty complete list.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml
from test_merge_admission import _evidence as _verdict_evidence
from test_merge_admission import _failed as _verdict_failed
from test_merge_admission import _verdict
from test_merge_evidence_github import (
    COMPARE,
    HEAD,
    REQUIRED_CHECKS,
    ROOT,
    _authorities,
    _commit,
    _comparison,
    _policy,
    _project,
    _replies,
    _run,
    _snapshot,
    unregistered_tests,
)

from tools import assurance_completeness, merge_evidence_github

# What `knowledge merge-evidence` reports as an input error.
INPUT_ERRORS = (
    merge_evidence_github.MergeEvidenceError,
    assurance_completeness.AssuranceCompletenessError,
)
EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # pragma: allowlist secret -- Git's empty-blob id
BLOB = "b" * 40
MARKERS_DOCUMENT: dict[str, Any] = {
    "schema_version": "1.0",
    "id": "example.merge-suppression-markers",
    "version": "0.1.0",
    "markers": ["noqa", "# nosec", "# type: ignore", "NOSONAR"],
}
ROOTS_DOCUMENT: dict[str, Any] = {
    "schema_version": "1.0",
    "id": "example.merge-trust-roots",
    "version": "0.1.0",
    "patterns": ["/.github/", "/CODEOWNERS", "/ci/", "/policy/"],
}
# The admitted contract's declarations (#325 6112833932), in its order.
ADMITTED_MARKERS = [
    "noqa",
    "# type: ignore",
    "# nosec",
    "skipcq",
    "nosemgrep",
    "# pragma: no cover",
    "pragma: allowlist secret",
    "NOSONAR",
    "eslint-disable",
]
ADMITTED_ROOTS = [
    "/.github/",
    "/CODEOWNERS",
    "/docs/CODEOWNERS",
    "/.gitlab-ci.yml",
    "/.devcontainer/",
    "/.githooks/",
    "/.dockerignore",
    "/.secrets.baseline",
    "/AGENTS.md",
    "/Dockerfile",
    "/pyproject.toml",
    "/requirements/",
    "/ci/",
    "/tools/",
    "/core/",
    "/policy/",
    "/schemas/",
    "/guidance/",
    "/knowledge/",
    "/templates/",
    "/tests/",
    "/CONTRIBUTING.md",
    "/SECURITY.md",
]


def _added(patch: str) -> int:
    return sum(1 for line in patch.split("\n") if line.startswith("+"))


def _file(
    path: str,
    status: str = "modified",
    *,
    patch: str | None = None,
    additions: int | None = None,
    blob: str | None = BLOB,
    previous: str | None = None,
) -> dict[str, Any]:
    """One entry of GitHub's comparison, in the shape the live API returns."""

    entry: dict[str, Any] = {"filename": path, "status": status, "sha": blob}
    if patch is not None:
        entry["patch"] = patch
    if additions is None:
        additions = _added(patch) if patch else 0
    entry["additions"] = additions
    entry["deletions"] = 0
    entry["changes"] = additions
    if previous is not None:
        entry["previous_filename"] = previous
    return entry


def _collected(files: list[dict[str, Any]]) -> dict[str, Any]:
    replies = _replies()
    replies[COMPARE] = _comparison(
        [_commit(HEAD, "Admit or deny one merge\n\nRefs #407")], files
    )
    return _snapshot(replies)


def _markers(document: dict[str, Any] | None = None) -> Any:
    return merge_evidence_github.parse_suppression_markers(
        MARKERS_DOCUMENT if document is None else document
    )


def _roots(document: dict[str, Any] | None = None) -> Any:
    return merge_evidence_github.parse_trust_roots(
        ROOTS_DOCUMENT if document is None else document
    )


def _evidence(
    files: list[dict[str, Any]], *, markers: Any = None, roots: Any = None
) -> dict[str, Any]:
    return merge_evidence_github.evidence_from_snapshot(
        _collected(files),
        authorities=_authorities(),
        change_policy=_policy(),
        codeowners=merge_evidence_github.parse_codeowners("* @ktogias\n"),
        decisions=merge_evidence_github.load_decisions(ROOT),
        required_checks=merge_evidence_github.parse_required_checks(REQUIRED_CHECKS),
        suppression_markers=_markers() if markers is None else markers,
        trust_roots=_roots() if roots is None else roots,
    )


def _suppressions(files: list[dict[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = _evidence(files)["suppressions"]
    return record


def _trust_roots(files: list[dict[str, Any]]) -> dict[str, Any]:
    record: dict[str, Any] = _evidence(files)["trust_root_changes"]
    return record


def _found(path: str, line: int, marker: str, reason: str = "") -> dict[str, Any]:
    return {
        "path": path,
        "line": line,
        "marker": marker,
        "justified": bool(reason),
        "reason": reason,
    }


class FileCollectionTests(unittest.TestCase):
    """L1 keeps what the comparison says about each file's added content."""

    def test_each_changed_file_keeps_its_additions_blob_and_patch(self) -> None:
        patch = "@@ -1,2 +1,3 @@\n a\n+b\n c"
        snapshot = _collected([_file("tools/x.py", patch=patch)])
        self.assertEqual(
            [
                {
                    "path": "tools/x.py",
                    "status": "modified",
                    "previous_path": None,
                    "additions": 1,
                    "blob": BLOB,
                    "patch": patch,
                    "patch_truncated": False,
                }
            ],
            snapshot["files"],
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])

    def test_an_omitted_or_empty_patch_is_no_hunks(self) -> None:
        """As GitHub leaves a binary's patch out (agent_review_github's rule)."""

        omitted = _file("docs/logo.png", "added")
        empty = {**_file("docs/x.md"), "patch": ""}
        snapshot = _collected([omitted, empty])
        self.assertEqual([None, None], [f["patch"] for f in snapshot["files"]])
        self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])

    def test_a_long_patch_is_bounded_and_marked(self) -> None:
        patch = "@@ -0,0 +1,1 @@\n+" + "x" * 70_000
        snapshot = _collected([_file("tools/x.py", "added", patch=patch)])
        kept = snapshot["files"][0]
        self.assertTrue(kept["patch_truncated"])
        self.assertLess(len(kept["patch"].encode("utf-8")), len(patch))

    def test_a_mistyped_field_fails_the_files_source(self) -> None:
        """A present null patch is malformed, not an absence, and a count is a
        non-negative whole number (agent_review_github's typing rules)."""

        for name, change in (
            ("a null patch", {"patch": None}),
            ("a patch that is not text", {"patch": 7}),
            ("a boolean count", {"additions": True}),
            ("a negative count", {"additions": -1}),
            ("a count that is text", {"additions": "1"}),
            ("a blob that is not text", {"sha": 7}),
        ):
            with self.subTest(name):
                entry = {**_file("tools/x.py", patch="@@ -1 +1 @@\n-a\n+b"), **change}
                snapshot = _collected([entry])
                self.assertEqual("ERROR", snapshot["coverage"]["files"]["status"])


class DeclarationTests(unittest.TestCase):
    """The two declarations: closed, versioned, and read from the project root."""

    def test_the_declarations_are_closed_and_versioned(self) -> None:
        for parse, document, field in (
            (
                merge_evidence_github.parse_suppression_markers,
                MARKERS_DOCUMENT,
                "markers",
            ),
            (merge_evidence_github.parse_trust_roots, ROOTS_DOCUMENT, "patterns"),
        ):
            for name, change in (
                ("another schema", {"schema_version": "2.0"}),
                ("an unknown key", {"extra": 1}),
                ("no id", {"id": ""}),
                ("an empty list", {field: []}),
                ("an entry that is not text", {field: ["noqa", 7]}),
                ("a blank entry", {field: [" "]}),
                ("a repeated entry", {field: ["/ci/", "/ci/"]}),
                ("not a list", {field: "noqa"}),
            ):
                with self.subTest(field=field, case=name):
                    changed = {**copy.deepcopy(document), **change}
                    with self.assertRaises(INPUT_ERRORS):
                        parse(changed)
            with self.subTest(field=field, case="a missing key"):
                missing = copy.deepcopy(document)
                del missing[field]
                with self.assertRaises(INPUT_ERRORS):
                    parse(missing)

    def test_an_unsupported_trust_root_pattern_fails(self) -> None:
        """The CODEOWNERS matcher's own refusals."""

        for pattern in ("!/ci/", "/c[i]/", "//ci/", "/docs/guides*"):
            with self.subTest(pattern):
                with self.assertRaises(INPUT_ERRORS):
                    _roots({**ROOTS_DOCUMENT, "patterns": [pattern]})

    def test_a_missing_declaration_reads_as_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(
                merge_evidence_github.load_suppression_markers(
                    root / merge_evidence_github.DEFAULT_SUPPRESSION_MARKERS,
                    project_root=root,
                )
            )
            self.assertIsNone(
                merge_evidence_github.load_trust_roots(
                    root / merge_evidence_github.DEFAULT_TRUST_ROOTS,
                    project_root=root,
                )
            )

    def test_the_repository_declarations_are_the_admitted_contract(self) -> None:
        for path, field, expected in (
            (
                merge_evidence_github.DEFAULT_SUPPRESSION_MARKERS,
                "markers",
                ADMITTED_MARKERS,
            ),
            (merge_evidence_github.DEFAULT_TRUST_ROOTS, "patterns", ADMITTED_ROOTS),
        ):
            with self.subTest(path=str(path)):
                document = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
                self.assertEqual(expected, document[field])
        self.assertIsNotNone(
            merge_evidence_github.load_suppression_markers(
                ROOT / merge_evidence_github.DEFAULT_SUPPRESSION_MARKERS,
                project_root=ROOT,
            )
        )
        self.assertIsNotNone(
            merge_evidence_github.load_trust_roots(
                ROOT / merge_evidence_github.DEFAULT_TRUST_ROOTS, project_root=ROOT
            )
        )


class SuppressionTests(unittest.TestCase):
    """M13: each marker in an added line, with its head line and its reason."""

    def test_a_marker_in_an_added_line_is_reported_with_its_head_line_and_reason(
        self,
    ) -> None:
        patch = "@@ -10,3 +10,4 @@\n a\n+x = 1  # noqa: E501 -- a long URL  \n b\n c"
        self.assertEqual(
            {
                "coverage": "COMPLETE",
                "found": [_found("tools/x.py", 11, "noqa", "a long URL")],
            },
            _suppressions([_file("tools/x.py", patch=patch)]),
        )

    def test_a_missing_or_blank_reason_is_unjustified(self) -> None:
        for name, text in (
            ("no delimiter", "+run()  # nosec B603"),
            ("a blank reason", "+run()  # nosec B603 --   "),
            ("a delimiter before the marker", "+run()  -- why # nosec B603"),
        ):
            with self.subTest(name):
                patch = f"@@ -0,0 +1,1 @@\n{text}"
                self.assertEqual(
                    [_found("ci/x.py", 1, "# nosec")],
                    _suppressions([_file("ci/x.py", "added", patch=patch)])["found"],
                )

    def test_every_occurrence_is_reported(self) -> None:
        """In reading order: by line, then by position in the line."""

        patch = "@@ -0,0 +1,1 @@\n+f()  # type: ignore -- stub  # noqa  # noqa -- twice"
        self.assertEqual(
            [
                _found(
                    "tools/x.py", 1, "# type: ignore", "stub  # noqa  # noqa -- twice"
                ),
                _found("tools/x.py", 1, "noqa", "twice"),
                _found("tools/x.py", 1, "noqa", "twice"),
            ],
            _suppressions([_file("tools/x.py", "added", patch=patch)])["found"],
        )

    def test_markers_are_case_sensitive_literals(self) -> None:
        patch = "@@ -0,0 +1,3 @@\n+a  # NOQA\n+b  // nosonar\n+c  # NOSEC"
        self.assertEqual(
            {"coverage": "COMPLETE", "found": []},
            _suppressions([_file("tools/x.py", "added", patch=patch)]),
        )

    def test_unchanged_and_removed_lines_are_not_examined(self) -> None:
        patch = "@@ -1,3 +1,3 @@\n old()  # noqa\n-gone()  # nosec\n+kept()\n tail()"
        self.assertEqual(
            {"coverage": "COMPLETE", "found": []},
            _suppressions([_file("tools/x.py", patch=patch)]),
        )

    def test_head_lines_follow_each_hunk(self) -> None:
        patch = (
            "@@ -1,4 +1,3 @@ def first():\n"
            " a\n"
            "-b\n"
            "-c\n"
            "+d  # noqa -- one\n"
            " e\n"
            "@@ -20,2 +19,3 @@\n"
            " f\n"
            "+g  NOSONAR -- two\n"
            " h\n"
            "\\ No newline at end of file"
        )
        self.assertEqual(
            [
                _found("tools/x.py", 2, "noqa", "one"),
                _found("tools/x.py", 20, "NOSONAR", "two"),
            ],
            _suppressions([_file("tools/x.py", patch=patch)])["found"],
        )

    def test_an_inconsistent_patch_leaves_suppressions_partial(self) -> None:
        for name, entry in (
            ("too few lines", _file("t.py", patch="@@ -1,2 +1,3 @@\n a\n+b")),
            ("too many lines", _file("t.py", patch="@@ -1 +1,2 @@\n a\n+b\n+c")),
            ("an unknown line prefix", _file("t.py", patch="@@ -1 +1,2 @@\n a\n*b")),
            ("an empty line", _file("t.py", patch="@@ -1 +1,2 @@\n a\n\n+b")),
            ("a malformed header", _file("t.py", patch="@@ -1 +x @@\n+b")),
            # Added after the reader, as characterization for its mutants.
            (
                "an annotation that follows no line",
                _file("t.py", patch="@@ -0,0 +1 @@\n\\ No newline at end of file\n+b"),
            ),
            (
                "a head line before the first",
                _file("t.py", patch="@@ -0,0 +0,1 @@\n+b"),
            ),
            (
                "a number too long to read",
                _file("t.py", patch="@@ -1 +" + "9" * 5000 + " @@\n+b"),
            ),
            # Only the exact annotation is metadata (the coordinator, 6113356451).
            (
                "another backslash line",
                _file("t.py", patch="@@ -1 +1,2 @@\n a\n\\ something else\n+b"),
            ),
            (
                "text before the first hunk",
                _file("t.py", patch="diff\n@@ -0,0 +1 @@\n+b"),
            ),
            (
                "fewer added lines than the entry counts",
                _file("t.py", patch="@@ -0,0 +1 @@\n+b", additions=2),
            ),
            (
                "a truncated patch",
                _file("t.py", "added", patch="@@ -0,0 +1,1 @@\n+" + "x" * 70_000),
            ),
        ):
            with self.subTest(name):
                self.assertEqual("PARTIAL", _suppressions([entry])["coverage"])

    def test_a_hunkless_file_is_inspectable_only_when_nothing_can_be_added(
        self,
    ) -> None:
        """A removal adds nothing and neither does an empty head blob. Anything
        else without hunks may hide added content: a binary, an oversized file,
        or a rename or mode change the comparison cannot tell from one (#407,
        A-2 in 6113162966)."""

        for name, entry, coverage in (
            ("a removal", _file("tools/x.py", "removed"), "COMPLETE"),
            (
                "an empty file",
                _file("tools/__init__.py", "added", blob=EMPTY_BLOB),
                "COMPLETE",
            ),
            ("a binary", _file("docs/logo.png", "added"), "PARTIAL"),
            ("a modified binary", _file("docs/logo.png"), "PARTIAL"),
            (
                "a rename",
                _file("tools/y.py", "renamed", previous="tools/x.py"),
                "PARTIAL",
            ),
            ("a mode change", _file("ci/run", "changed"), "PARTIAL"),
            # The coordinator on #407 (6113356451): contradictory evidence never
            # establishes an empty added-line domain.
            (
                "a removal that counts additions",
                _file("tools/x.py", "removed", additions=1),
                "PARTIAL",
            ),
            (
                "an empty blob that counts additions",
                _file("tools/__init__.py", "added", blob=EMPTY_BLOB, additions=1),
                "PARTIAL",
            ),
            (
                "a removal whose patch adds a line",
                _file("tools/x.py", "removed", patch="@@ -1 +1 @@\n-a\n+b"),
                "PARTIAL",
            ),
            (
                "an empty blob whose patch adds a line",
                _file(
                    "tools/__init__.py",
                    "added",
                    blob=EMPTY_BLOB,
                    patch="@@ -0,0 +1 @@\n+a",
                ),
                "PARTIAL",
            ),
            (
                "an unknown count",
                {
                    k: v
                    for k, v in _file("docs/logo.png", "added").items()
                    if k != "additions"
                },
                "PARTIAL",
            ),
        ):
            with self.subTest(name):
                self.assertEqual(
                    {"coverage": coverage, "found": []}, _suppressions([entry])
                )

    def test_consecutive_added_lines_are_numbered_in_turn(self) -> None:
        """Added after the reader, as characterization for its mutants."""

        patch = "@@ -1 +1,3 @@\n a\n+b  # noqa -- one\n+c  # noqa -- two"
        self.assertEqual(
            [
                _found("tools/x.py", 2, "noqa", "one"),
                _found("tools/x.py", 3, "noqa", "two"),
            ],
            _suppressions([_file("tools/x.py", patch=patch)])["found"],
        )

    def test_a_hunk_header_s_context_is_not_examined(self) -> None:
        """The text after a header's closing `@@` is the hunk's context, not an
        added line, and is accepted without being interpreted."""

        patch = "@@ -1 +1,2 @@ x = 1  # noqa -- in the context\n a\n+b"
        self.assertEqual(
            {"coverage": "COMPLETE", "found": []},
            _suppressions([_file("tools/x.py", patch=patch)]),
        )

    def test_a_complete_diff_without_markers_is_complete_and_empty(self) -> None:
        patch = "@@ -1 +1 @@\n-a\n+b"
        self.assertEqual(
            {"coverage": "COMPLETE", "found": []},
            _suppressions([_file("tools/x.py", patch=patch)]),
        )


class TrustRootTests(unittest.TestCase):
    """M15: each changed trust root, under every name it has."""

    def test_changed_trust_roots_are_reported_with_every_name(self) -> None:
        files = [
            _file("ci/verify", patch="@@ -1 +1 @@\n-a\n+b"),
            _file("policy/new.yaml", "added", patch="@@ -0,0 +1 @@\n+a: 1"),
            _file(".github/old.yml", "removed"),
            _file("ci/moved.py", "renamed", previous="scratch/moved.py"),
            _file("scratch/out.py", "renamed", previous="tools/out.py"),
            _file("docs/readme.md", patch="@@ -1 +1 @@\n-a\n+b"),
            _file("CODEOWNERS", patch="@@ -1 +1 @@\n-a\n+b"),
        ]
        self.assertEqual(
            {
                "coverage": "COMPLETE",
                "paths": [
                    ".github/old.yml",
                    "CODEOWNERS",
                    "ci/moved.py",
                    "ci/verify",
                    "policy/new.yaml",
                    "scratch/moved.py",
                ],
            },
            _trust_roots(files),
        )
        # A rename out of a root names both sides; tools/ is not a root here.
        roots = _roots({**ROOTS_DOCUMENT, "patterns": ["/tools/"]})
        self.assertEqual(
            ["scratch/out.py", "tools/out.py"],
            _evidence(files, roots=roots)["trust_root_changes"]["paths"],
        )

    def test_a_declaration_change_is_itself_a_trust_root_change(self) -> None:
        patch = "@@ -1 +1,2 @@\n patterns:\n+  - /scratch/"
        files = [_file("policy/merge-trust-roots.yaml", patch=patch)]
        self.assertEqual(
            {"coverage": "COMPLETE", "paths": ["policy/merge-trust-roots.yaml"]},
            _trust_roots(files),
        )

    def test_an_unsupported_status_leaves_trust_roots_partial(self) -> None:
        """The contract names four statuses: added, modified, removed, renamed."""

        for status in ("copied", "changed", "unchanged"):
            with self.subTest(status):
                entry = _file("docs/x.md", status, previous="docs/y.md")
                self.assertEqual("PARTIAL", _trust_roots([entry])["coverage"])

    def test_a_complete_change_outside_the_roots_is_complete_and_empty(self) -> None:
        files = [_file("docs/readme.md", patch="@@ -1 +1 @@\n-a\n+b")]
        self.assertEqual({"coverage": "COMPLETE", "paths": []}, _trust_roots(files))


class ProtectedTargetTests(unittest.TestCase):
    """The declarations come from the project root, never from the candidate."""

    def test_without_the_declarations_both_stay_unavailable(self) -> None:
        evidence = merge_evidence_github.evidence_from_snapshot(
            _collected([_file("ci/x.py", "added", patch="@@ -0,0 +1 @@\n+a  # noqa")]),
            authorities=_authorities(),
            change_policy=_policy(),
            codeowners=merge_evidence_github.parse_codeowners("* @ktogias\n"),
            decisions=merge_evidence_github.load_decisions(ROOT),
            required_checks=merge_evidence_github.parse_required_checks(
                REQUIRED_CHECKS
            ),
        )
        self.assertEqual(
            {"coverage": "UNAVAILABLE", "found": []}, evidence["suppressions"]
        )
        self.assertEqual(
            {"coverage": "UNAVAILABLE", "paths": []}, evidence["trust_root_changes"]
        )

    def test_the_command_reads_the_declarations_from_the_project_root(self) -> None:
        """The candidate's own declaration in its diff changes nothing; without
        one on the protected target, both stay unavailable (the bootstrap)."""

        candidate = _file(
            "policy/merge-suppression-markers.yaml",
            "added",
            patch="@@ -0,0 +1,2 @@\n+markers:\n+  - other  # noqa",
        )
        text = json.dumps(_collected([candidate]))
        with tempfile.TemporaryDirectory() as directory:
            project = _project(Path(directory))
            code, out, err = _run(project, text)
            self.assertEqual(0, code, err)
            bootstrap = json.loads(out)
            for name, document in (
                ("merge-suppression-markers.yaml", MARKERS_DOCUMENT),
                ("merge-trust-roots.yaml", ROOTS_DOCUMENT),
            ):
                (project / "policy" / name).write_text(
                    yaml.safe_dump(document), encoding="utf-8"
                )
            code, out, err = _run(project, text)
            self.assertEqual(0, code, err)
            protected = json.loads(out)
        self.assertEqual("UNAVAILABLE", bootstrap["suppressions"]["coverage"])
        self.assertEqual("UNAVAILABLE", bootstrap["trust_root_changes"]["coverage"])
        self.assertEqual(
            {
                "coverage": "COMPLETE",
                "found": [_found("policy/merge-suppression-markers.yaml", 2, "noqa")],
            },
            protected["suppressions"],
        )
        self.assertEqual(
            {
                "coverage": "COMPLETE",
                "paths": ["policy/merge-suppression-markers.yaml"],
            },
            protected["trust_root_changes"],
        )


class VerdictTests(unittest.TestCase):
    """M13 carries each suppression's line and reason; M17 is unchanged."""

    def test_old_suppression_inputs_stay_valid(self) -> None:
        evidence = _verdict_evidence()
        old = {"path": "tests/x.py", "marker": "# nosec", "justified": True}
        evidence["suppressions"]["found"] = [old]
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual([old], verdict["for_approval"]["suppressions"])

    def test_line_and_reason_are_carried_and_typed(self) -> None:
        justified = _found("tests/x.py", 3, "# nosec", "a fixed argv")
        evidence = _verdict_evidence()
        evidence["suppressions"]["found"] = [justified]
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual([justified], verdict["for_approval"]["suppressions"])
        for name, change in (
            ("line zero", {"line": 0}),
            ("a negative line", {"line": -1}),
            ("a boolean line", {"line": True}),
            ("a line that is text", {"line": "3"}),
            ("a reason that is not text", {"reason": 3}),
            ("an unknown field", {"column": 1}),
            # A reason decides the flag, so the two cannot disagree.
            ("a reason marked unjustified", {"justified": False}),
            ("no reason marked justified", {"reason": "  "}),
        ):
            with self.subTest(name):
                broken = _verdict_evidence()
                broken["suppressions"]["found"] = [{**justified, **change}]
                with self.assertRaises(INPUT_ERRORS):
                    _verdict(broken)

    def test_an_unjustified_suppression_is_denied_at_its_line(self) -> None:
        evidence = _verdict_evidence()
        evidence["suppressions"]["found"] = [_found("tools/y.py", 12, "noqa")]
        self.assertEqual(
            ["noqa in tools/y.py:12 has no justification"],
            _verdict_failed(_verdict(evidence))["M13"],
        )

    def test_a_justified_suppression_does_not_discharge_a_finding(self) -> None:
        """M17 is the owner's no-waiver rule (#407 6096770145)."""

        evidence = _verdict_evidence()
        evidence["suppressions"]["found"] = [
            _found("tools/y.py", 12, "noqa", "the finding is known")
        ]
        evidence["analyzer_findings"]["findings"] = [
            {"item": "deepsource-full", "id": "issue-1", "message": "Reimport"}
        ]
        failed = _verdict_failed(_verdict(evidence))
        self.assertNotIn("M13", failed)
        self.assertIn("M17", failed)


class GuardrailRegistrationTests(unittest.TestCase):
    def test_every_test_in_this_module_is_registered_in_its_guardrail(self) -> None:
        self.assertEqual(
            set(),
            unregistered_tests(globals(), "tests/test_merge_evidence_suppressions.py"),
        )


if __name__ == "__main__":
    unittest.main()
