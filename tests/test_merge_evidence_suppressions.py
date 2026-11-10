"""Suppressions (M13) and trust-root changes (M15) in the merge evidence (#407,
slice 1b.3b-4, admitted in #325 6113092417 with the contract 6112833932).

The adapter reads both from the exact base-to-head comparison L1 already
collects, against two declarations read from the protected target: the
suppression markers and the trust-root patterns. A marker in an added line is
reported with its head line and its same-line reason; a changed trust root is
reported with every name it has. Anything the comparison does not show
completely leaves the observation incomplete, never an empty complete list.

A hunkless file that the protected target's frozen-archive declaration names by
path, blob and SHA-256 is read whole from the content L1 attaches, and every
marker in its members is listed as frozen evidence, shown for the approval and
denying nothing (Decision 0112's amendment, option (c): the admission packet
#389 6761333802 and the PAO's assessment 6761351016).
"""

from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from unittest import mock

import yaml

from tests.merge_admission_support import _evidence as _verdict_evidence
from tests.merge_admission_support import _failed as _verdict_failed
from tests.merge_admission_support import _verdict
from tests.merge_evidence_github_support import (
    API,
    COMPARE,
    HEAD,
    REQUIRED_CHECKS,
    ROOT,
    _authorities,
    _commit,
    _comparison,
    _merge_evidence_guardrail,
    _policy,
    _project,
    _replies,
    _run,
    _snapshot,
    unregistered_tests,
)
from tests.review_reconcile_l1_support import adapter_fixture, paged_fake_fixture
from tools import assurance_completeness, merge_admission, merge_evidence_github

# What `knowledge merge-evidence` reports as an input error.
INPUT_ERRORS = (
    merge_evidence_github.MergeEvidenceError,
    assurance_completeness.AssuranceCompletenessError,
)
EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # pragma: allowlist secret -- Git's empty-blob id
BLOB = "b" * 40
# The collector's response budget, which also bounds a comparison file's patch: a
# patch arrives whole inside one comparison response (Decision 0086, #389).
RESPONSE_BUDGET = 4_194_304
# A patch past the 65,536-byte bound of comments and messages, inside that budget.
LONG_PATCH = "@@ -0,0 +1,1 @@\n+" + "x" * 70_000
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
    """L1's merge-evidence snapshot of `files`. A blob read, which a hunkless file
    may cause, is refused as the client refuses one (see _collect_blobs)."""

    return _collect_blobs(files, {})[0]


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
        "justified": bool(reason.strip()),
        "reason": reason,
    }


class FileCollectionTests(unittest.TestCase):
    """L1 keeps what the comparison says about each file's added content."""

    def test_each_changed_file_keeps_its_additions_blob_and_patch(self) -> None:
        """Also a patch past the 65,536-byte body bound: GitHub's comparison returns
        it whole, and M13 reads it whole (#389 6606110648)."""

        patch = "@@ -1,2 +1,3 @@\n a\n+b\n c"
        files = [
            _file("tools/x.py", patch=patch),
            _file("tools/y.py", "added", patch=LONG_PATCH),
        ]
        snapshot = _collected(files)
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
                },
                {
                    "path": "tools/y.py",
                    "status": "added",
                    "previous_path": None,
                    "additions": 1,
                    "blob": BLOB,
                    "patch": LONG_PATCH,
                    "patch_truncated": False,
                },
            ],
            snapshot["files"],
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])
        self.assertEqual("COMPLETE", _suppressions(files)["coverage"])

    def test_an_omitted_or_empty_patch_is_no_hunks(self) -> None:
        """As GitHub leaves a binary's patch out (agent_review_github's rule)."""

        omitted = _file("docs/logo.png", "added")
        empty = {**_file("docs/x.md"), "patch": ""}
        snapshot = _collected([omitted, empty])
        self.assertEqual([None, None], [f["patch"] for f in snapshot["files"]])
        self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])

    def test_a_long_patch_is_bounded_and_marked(self) -> None:
        """Past the response budget, a patch is cut and marked; a comparison the client
        refuses as over that budget fails the collection, since L1 reads it first for the
        merge base; and a commit message keeps the 65,536-byte bound of comments and
        messages (#389 6606110648)."""

        patch = "@@ -0,0 +1,1 @@\n+" + "x" * RESPONSE_BUDGET
        snapshot = _collected([_file("tools/x.py", "added", patch=patch)])
        kept = snapshot["files"][0]
        self.assertTrue(kept["patch_truncated"])
        self.assertLess(len(kept["patch"].encode("utf-8")), len(patch))

        adapter = adapter_fixture()
        # The refusal below is the client's, so this adapter's client must carry that
        # budget (Revix on #479). The client's own refusal past it is
        # test_github_rest.SharedGitHubClientTests.test_bodies_are_bounded's.
        self.assertEqual(
            RESPONSE_BUDGET, adapter.GitHubRestClient("t").policy.max_response_bytes
        )
        fake = paged_fake_fixture(_replies())
        answer = fake.get

        def refusing(url: str) -> tuple[Any, dict[str, str]]:
            if url == COMPARE:
                # What the adapter's client raises for a body past its budget.
                raise adapter.ProviderReadError(
                    f"provider body exceeded {RESPONSE_BUDGET} bytes for {url!r}"
                )
            return answer(url)

        with (
            mock.patch.object(fake, "get", side_effect=refusing),
            self.assertRaises(adapter.ProviderReadError),
        ):
            adapter.collect_snapshot(
                fake,
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:41:00Z",
                merge_evidence=True,
            )

        replies = _replies()
        replies[COMPARE] = _comparison([_commit(HEAD, "m" * 70_000)], [])
        message = _snapshot(replies)["commits"][0]
        self.assertTrue(message["message_truncated"])
        self.assertEqual(65_536, len(message["message"].encode("utf-8")))

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
            with self.subTest(pattern), self.assertRaises(INPUT_ERRORS):
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
                # Kept as written (cubic on #423): only blankness is judged.
                "found": [_found("tools/x.py", 11, "noqa", " a long URL  ")],
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
                    [_found("ci/x.py", 1, "# nosec", "   " if "blank" in name else "")],
                    _suppressions([_file("ci/x.py", "added", patch=patch)])["found"],
                )

    def test_every_occurrence_is_reported(self) -> None:
        """In reading order: by line, then by position in the line."""

        patch = "@@ -0,0 +1,1 @@\n+f()  # type: ignore -- stub  # noqa  # noqa -- twice"
        self.assertEqual(
            [
                _found(
                    "tools/x.py", 1, "# type: ignore", " stub  # noqa  # noqa -- twice"
                ),
                _found("tools/x.py", 1, "noqa", " twice"),
                _found("tools/x.py", 1, "noqa", " twice"),
            ],
            _suppressions([_file("tools/x.py", "added", patch=patch)])["found"],
        )

    def test_each_occurrence_has_its_own_reason(self) -> None:
        """CodeReviewBot on #423: a repeated marker's reasons are each read from
        that occurrence's own position (characterization)."""

        patch = "@@ -0,0 +1,1 @@\n+f()  # noqa -- first  # noqa -- second"
        self.assertEqual(
            [
                _found("tools/x.py", 1, "noqa", " first  # noqa -- second"),
                _found("tools/x.py", 1, "noqa", " second"),
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
                _found("tools/x.py", 2, "noqa", " one"),
                _found("tools/x.py", 20, "NOSONAR", " two"),
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
            # CodeAnt on #423: the old side's start is checked as the new side's is.
            (
                "an old line before the first",
                _file("t.py", patch="@@ -0 +1 @@\n-a\n+b"),
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
                _file(
                    "t.py", "added", patch="@@ -0,0 +1,1 @@\n+" + "x" * RESPONSE_BUDGET
                ),
            ),
            (
                "a long patch with fewer added lines than the entry counts",
                _file("t.py", "added", patch=LONG_PATCH, additions=2),
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
            # PAO on #423 (6113955118): a context line keeps head content too.
            (
                "an empty blob whose patch keeps a line",
                _file("tools/x.py", blob=EMPTY_BLOB, patch="@@ -1 +1 @@\n a"),
                "PARTIAL",
            ),
            (
                "a removal whose patch keeps a line",
                _file("tools/x.py", "removed", patch="@@ -1 +1 @@\n a"),
                "PARTIAL",
            ),
            (
                "a delete-only removal",
                _file("tools/x.py", "removed", patch="@@ -1,2 +0,0 @@\n-a\n-b"),
                "COMPLETE",
            ),
            (
                "a file emptied",
                _file("tools/x.py", blob=EMPTY_BLOB, patch="@@ -1 +0,0 @@\n-a"),
                "COMPLETE",
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
                _found("tools/x.py", 2, "noqa", " one"),
                _found("tools/x.py", 3, "noqa", " two"),
            ],
            _suppressions([_file("tools/x.py", patch=patch)])["found"],
        )

    def test_one_terminal_newline_ends_the_last_line(self) -> None:
        """cubic and CodeAnt on #423: Git ends every line with a newline, so a
        patch that keeps the last one is the same hunks. A second is a blank
        line no hunk counts."""

        patch = "@@ -0,0 +1,1 @@\n+a  # noqa -- kept\n"
        self.assertEqual(
            {"coverage": "COMPLETE", "found": [_found("t.py", 1, "noqa", " kept")]},
            _suppressions([_file("t.py", "added", patch=patch)]),
        )
        doubled = _file("t.py", "added", patch=patch + "\n")
        self.assertEqual("PARTIAL", _suppressions([doubled])["coverage"])

    def test_a_hunk_header_s_context_is_not_examined(self) -> None:
        """The text after a header's closing `@@` is the hunk's context, not an
        added line, and is accepted without being interpreted."""

        patch = "@@ -1 +1,2 @@ x = 1  # noqa -- in the context\n a\n+b"
        self.assertEqual(
            {"coverage": "COMPLETE", "found": []},
            _suppressions([_file("tools/x.py", patch=patch)]),
        )

    def test_the_suppression_list_is_bounded_in_count(self) -> None:
        """Codex on #423 and the coordinator's selection (6114751092): past the
        occurrence budget the list stops, keeps its prefix, and is PARTIAL."""

        cap = merge_evidence_github.MAX_SUPPRESSIONS

        def lines(count: int) -> dict[str, Any]:
            body = "\n".join("+a  # noqa -- r" for _ in range(count))
            return _file("t.py", "added", patch=f"@@ -0,0 +1,{count} @@\n{body}")

        self.assertEqual("COMPLETE", _suppressions([lines(cap)])["coverage"])
        over = _suppressions([lines(cap + 1)])
        self.assertEqual("PARTIAL", over["coverage"])
        self.assertEqual(cap, len(over["found"]))
        self.assertEqual(_suppressions([lines(cap)])["found"], over["found"])

    def test_the_suppression_list_is_bounded_in_bytes_across_files(self) -> None:
        """Every record is charged, its path and reason included, and the budget
        is the comparison's, not a file's or a line's."""

        budget = merge_evidence_github.MAX_SUPPRESSION_BYTES
        reason = "r" * 60_000
        files = [
            _file(
                f"tools/t{n:02d}.py",
                "added",
                patch=f"@@ -0,0 +1 @@\n+a  # noqa --{reason}",
            )
            for n in range(40)
        ]
        cost = merge_evidence_github.suppression_record_bytes(
            _found("tools/t10.py", 1, "noqa", reason)
        )
        fit = budget // cost
        self.assertLess(fit, len(files))
        self.assertLess(fit, merge_evidence_github.MAX_SUPPRESSIONS)
        self.assertEqual("COMPLETE", _suppressions(files[:fit])["coverage"])
        over = _suppressions(files[: fit + 1])
        self.assertEqual("PARTIAL", over["coverage"])
        self.assertEqual(fit, len(over["found"]))

    def test_the_byte_budget_is_exact(self) -> None:
        """At exactly the byte budget the list is COMPLETE, and one charged byte
        more makes it PARTIAL (the PAO on #423, 6115083586; characterization)."""

        budget = merge_evidence_github.MAX_SUPPRESSION_BYTES

        def entry(n: int, size: int) -> tuple[dict[str, Any], int]:
            path, reason = f"tools/t{n:02d}.py", "r" * size
            cost = merge_evidence_github.suppression_record_bytes(
                _found(path, 1, "noqa", reason)
            )
            patch = f"@@ -0,0 +1 @@\n+a  # noqa --{reason}"
            return _file(path, "added", patch=patch), cost

        files: list[dict[str, Any]] = []
        total = 0
        while (
            total + entry(len(files), 60_000)[1] + entry(len(files) + 1, 0)[1] <= budget
        ):
            item, cost = entry(len(files), 60_000)
            files.append(item)
            total += cost
        n = len(files)
        # From a one-character reason, each more character costs one byte; an
        # empty one is unjustified, and `false` is a byte longer than `true`.
        last = budget - total - entry(n, 1)[1] + 1
        exact, cost = entry(n, last)
        self.assertEqual(budget, total + cost)
        fits = _suppressions([*files, exact])
        self.assertEqual(("COMPLETE", n + 1), (fits["coverage"], len(fits["found"])))
        over = _suppressions([*files, entry(n, last + 1)[0]])
        self.assertEqual(("PARTIAL", n), (over["coverage"], len(over["found"])))

    def test_a_record_is_charged_as_the_command_writes_it(self) -> None:
        """The cost covers the serializer's escaping of quotes, backslashes and
        non-ASCII text, at the record's depth in the evidence document."""

        reason = ' quote" slash\\ caf\u00e9 \u20ac \U0001f600'
        patch = "\n".join(
            ["@@ -0,0 +1,3 @@"] + [f"+x{n}  # noqa --{reason}" for n in range(3)]
        )
        files = [_file("tools/\u00e9t\u00e9.py", "added", patch=patch)]
        evidence = _evidence(files)
        found = evidence["suppressions"]["found"]
        self.assertEqual(3, len(found))
        empty = copy.deepcopy(evidence)
        empty["suppressions"]["found"] = []
        written = len(json.dumps(evidence, indent=2, sort_keys=True).encode("utf-8"))
        bare = len(json.dumps(empty, indent=2, sort_keys=True).encode("utf-8"))
        charged = sum(merge_evidence_github.suppression_record_bytes(r) for r in found)
        self.assertGreaterEqual(charged, written - bare)
        self.assertLessEqual(charged - (written - bare), 16)

    def test_records_past_the_budget_are_never_built(self) -> None:
        """The walk is lazy: a line packed with markers yields one record at a
        time, so nothing past the budget is copied."""

        consumed = 0
        original = merge_evidence_github.marker_occurrences

        def counted(*args: Any) -> Any:
            nonlocal consumed
            for record in original(*args):
                consumed += 1
                yield record

        line = "+" + "noqa--x " * 8_000
        files = [_file("t.py", "added", patch=f"@@ -0,0 +1 @@\n{line}")]
        with mock.patch.object(merge_evidence_github, "marker_occurrences", counted):
            record = _suppressions(files)
        self.assertEqual("PARTIAL", record["coverage"])
        # cubic on #423: the long reasons reach the byte budget well before the
        # count's, and exactly one record past the kept ones is ever built.
        self.assertLess(len(record["found"]), merge_evidence_github.MAX_SUPPRESSIONS)
        self.assertEqual(len(record["found"]) + 1, consumed)

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

    def test_a_name_with_a_newline_is_matched_like_any_other(self) -> None:
        """Codex on #423: Git allows a newline in a file name, and a root's
        pattern must still match it, for M15 and for the code owners alike."""

        files = [_file("ci/a\nb.py", "added", patch="@@ -0,0 +1 @@\n+a")]
        self.assertEqual(
            {"coverage": "COMPLETE", "paths": ["ci/a\nb.py"]}, _trust_roots(files)
        )
        owners = merge_evidence_github.parse_codeowners("/ci/ @ktogias\n")
        self.assertEqual(["@ktogias"], owners.owners("ci/a\nb.py"))

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


# The frozen-archive declaration on the protected target, its one format, and the
# Decision that admits the entry the repository ships (6761333802 sections 3.1, 3.5).
FROZEN_ARCHIVES = Path("policy") / "merge-frozen-archives.yaml"
ARCHIVE = "knowledge/assessments/x-evidence/scripts.tar.gz"
ARCHIVE_DECISION = "0134"
# Each member's markers, as MARKERS_DOCUMENT declares them: one unjustified, two
# justified, and a member with none.
MEMBERS: tuple[tuple[str, bytes], ...] = (
    ("spike.py", b"import os  # noqa\nx = 1\ny = f()  # type: ignore -- stub\n"),
    ("notes.txt", b"plain\n"),
    ("eval.py", b"z = 2  # noqa -- kept"),
)
# The packet's bounds (6761333802 section 5).
EXPANDED_BOUND = 8 * 1024 * 1024
MEMBER_BOUND = 256
BLOB_BOUND = 1024 * 1024
BLOB_TOTAL = 4 * 1024 * 1024
BLOB_READS = 8
# The archive of #396 that the owner chose under (c), read from its exact blob
# (6761333802 section 2), as the protected declaration ships it (PAO Q3).
SHIPPED_ARCHIVE = {
    "path": "knowledge/assessments/0108-shell-parser-evaluation-evidence/spike-scripts.tar.gz",
    "blob": "585d4608efc744818e06d773840ace0806b693a0",  # pragma: allowlist secret -- public Git blob id
    "sha256": "f682e3bcc1fc12fc843f1bcaaa64905867d5f4782d9f038130d822f7800c3ea3",  # pragma: allowlist secret -- public archive digest
    "format": "tar+gzip",
    "decision": ARCHIVE_DECISION,
}


def _blob_id(data: bytes) -> str:
    """Git's object id for `data` as a blob, which a comparison's `sha` holds,
    computed apart from both implementations under test."""

    return hashlib.sha1(  # nosemgrep: python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1 -- test-only: Git's blob id is SHA-1 by definition
        b"blob %d\0" % len(data) + data, usedforsecurity=False
    ).hexdigest()


def _content(data: bytes) -> str:
    """The content L1 attaches: the blob's bytes in base64, on one line."""

    return base64.b64encode(data).decode("ascii")


def _regular(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def _directory(archive: tarfile.TarFile) -> None:
    info = tarfile.TarInfo("sub")
    info.type = tarfile.DIRTYPE
    archive.addfile(info)


def _symbolic_link(archive: tarfile.TarFile) -> None:
    info = tarfile.TarInfo("link.py")
    info.type = tarfile.SYMTYPE
    info.linkname = "spike.py"
    archive.addfile(info)


def _hard_link(archive: tarfile.TarFile) -> None:
    info = tarfile.TarInfo("again.py")
    info.type = tarfile.LNKTYPE
    info.linkname = "spike.py"
    archive.addfile(info)


def _sparse(archive: tarfile.TarFile) -> None:
    """A PAX sparse member: 4 stored bytes and a mebibyte of logical ones."""

    info = tarfile.TarInfo("holes.py")
    info.size = 4
    info.pax_headers = {"GNU.sparse.map": "0,4", "GNU.sparse.realsize": str(1 << 20)}
    archive.addfile(info, io.BytesIO(b"abcd"))


def _tar(
    members: Sequence[tuple[str, bytes]] = MEMBERS,
    *,
    then: Callable[[tarfile.TarFile], None] | None = None,
    size: int | None = None,
) -> bytes:
    """A tar of regular members, built natively, with what `then` adds after them,
    and zero bytes past its end to make it `size` bytes, which a tar reader
    ignores."""

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name, data in members:
            _regular(archive, name, data)
        if then is not None:
            then(archive)
    tar = buffer.getvalue()
    return tar if size is None else tar + bytes(size - len(tar))


def _cut_in_last_member(tar: bytes, *, header: bool = False) -> bytes:
    """`tar` cut inside its last member: within its header, or a few bytes into
    its data, so nothing but that member is short."""

    with tarfile.open(fileobj=io.BytesIO(tar), mode="r:") as archive:
        last = archive.getmembers()[-1]
    return tar[: last.offset + 200 if header else last.offset_data + 5]


# A member that comes after the archive's last one.
LATE = (("late.py", b"x\n"),)


def _archive(tar: bytes | None = None) -> bytes:
    """One gzip member of `tar`, by default of MEMBERS."""

    return gzip.compress(_tar() if tar is None else tar, mtime=0)


def _archives(data: bytes, **changes: Any) -> dict[str, Any]:
    """A frozen-archive declaration whose one entry names `data` at ARCHIVE."""

    entry = {
        "path": ARCHIVE,
        "blob": _blob_id(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "format": "tar+gzip",
        "decision": ARCHIVE_DECISION,
        **changes,
    }
    return {
        "schema_version": "1.0",
        "id": "example.merge-frozen-archives",
        "version": "0.1.0",
        "archives": [entry],
    }


def _archive_file(data: bytes, status: str = "added", **changes: Any) -> dict[str, Any]:
    """The comparison's entry for `data` at ARCHIVE: by default no patch and no
    additions, as GitHub lists a binary."""

    return _file(ARCHIVE, status, blob=_blob_id(data), **changes)


def _attached(
    files: list[dict[str, Any]], contents: Mapping[str, bytes | str]
) -> dict[str, Any]:
    """L1's snapshot of `files`, with the content L1 would attach to each named file:
    bytes as L1 encodes them, text as given."""

    snapshot = _collected(files)
    for item in snapshot["files"]:
        value = contents.get(item["path"])
        if value is not None:
            item["content"] = value if isinstance(value, str) else _content(value)
    return snapshot


def _frozen(
    member: str, line: int, marker: str, reason: str = "", path: str = ARCHIVE
) -> dict[str, Any]:
    return {**_found(path, line, marker, reason), "member": member, "frozen": True}


# MEMBERS' markers, in member order and then in line order.
FROZEN = [
    _frozen("spike.py", 1, "noqa"),  # not a suppression -- an expected record
    _frozen("spike.py", 3, "# type: ignore", " stub"),  # not one -- the same
    _frozen("eval.py", 1, "noqa", " kept"),  # not a suppression -- the same
]


class FrozenArchiveTests(unittest.TestCase):
    """M13 over a declared frozen archive (I1-I5 and I7 of 6761333802): read whole
    within bounds, each marker of its members listed as frozen; anything else as
    today. Where today's outcome is already PARTIAL, a case's control first reads
    the same archive, so the case fails before the change for the missing read.

    The protected target has the M13 and M15 declarations. Each case writes, or
    removes, its frozen-archive declaration before it reads the evidence through
    `evidence_for`, the function the command and the guarded merge both call."""

    project: Path

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.project = _project(Path(directory.name))
        for name, document in (
            ("merge-suppression-markers.yaml", MARKERS_DOCUMENT),
            ("merge-trust-roots.yaml", ROOTS_DOCUMENT),
        ):
            (cls.project / "policy" / name).write_text(
                yaml.safe_dump(document), encoding="utf-8"
            )

    def _evidence(
        self,
        files: list[dict[str, Any]],
        contents: Mapping[str, bytes | str],
        *,
        declared: dict[str, Any] | None,
        listed: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The producer's evidence for L1's snapshot of `files`, with `contents`
        attached and the last file's `listed` fields, which L1 never gives but the
        producer reads as given."""

        target = self.project / FROZEN_ARCHIVES
        if declared is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(yaml.safe_dump(declared), encoding="utf-8")
        snapshot = _attached(files, contents)
        snapshot["files"][-1].update(listed or {})
        evidence: dict[str, Any] = merge_evidence_github.evidence_for(
            snapshot, project_root=self.project
        )
        return evidence

    def _suppressions_of(
        self,
        files: list[dict[str, Any]],
        contents: Mapping[str, bytes | str],
        *,
        declared: dict[str, Any] | None,
    ) -> dict[str, Any]:
        record: dict[str, Any] = self._evidence(files, contents, declared=declared)[
            "suppressions"
        ]
        return record

    def _assert_read(self, data: bytes, found: list[dict[str, Any]]) -> None:
        """The control: `data`, declared and attached, is read with `found`."""

        self.assertEqual(
            {"coverage": "COMPLETE", "found": found},
            self._suppressions_of(
                [_archive_file(data)], {ARCHIVE: data}, declared=_archives(data)
            ),
        )

    def test_a_declared_archive_is_read_whole_and_its_markers_are_frozen(
        self,
    ) -> None:
        data = _archive()
        ordinary = _file("tools/x.py", "added", patch="@@ -0,0 +1 @@\n+a  # noqa -- r")
        found = [_found("tools/x.py", 1, "noqa", " r"), *FROZEN]  # not one -- expected
        for status in ("added", "modified"):
            with self.subTest(status):
                self.assertEqual(
                    {"coverage": "COMPLETE", "found": found},
                    self._suppressions_of(
                        [ordinary, _archive_file(data, status)],
                        {ARCHIVE: data},
                        declared=_archives(data),
                    ),
                )

    def test_a_declared_archive_meets_m13_and_is_shown_for_the_approval(
        self,
    ) -> None:
        """The packet's acceptance C3, from evidence to verdict."""

        data = _archive()
        evidence = self._evidence(
            [_archive_file(data)], {ARCHIVE: data}, declared=_archives(data)
        )
        verdict = merge_admission.evaluate(
            evidence,
            declaration=assurance_completeness.load_declaration(
                ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
            ),
            change_policy=_policy(),
        )
        self.assertNotIn("M13", _verdict_failed(verdict))
        self.assertEqual([], verdict["for_approval"]["suppressions"])
        self.assertEqual(FROZEN, verdict["for_approval"]["frozen_suppressions"])

    def test_an_undeclared_binary_stays_partial(self) -> None:
        """I1, characterization: without an entry for its path the archive is
        PARTIAL with no record, as today, its content attached or not."""

        data = _archive()
        for name, contents, declared in (
            ("no declaration", {ARCHIVE: data}, None),
            ("no declaration and no content", {}, None),
            (
                "another path declared",
                {ARCHIVE: data},
                _archives(data, path="docs/other.tar.gz"),
            ),
        ):
            with self.subTest(name):
                self.assertEqual(
                    {"coverage": "PARTIAL", "found": []},
                    self._suppressions_of(
                        [_archive_file(data)], contents, declared=declared
                    ),
                )

    def test_an_identity_mismatch_leaves_the_archive_partial(self) -> None:
        """I2: the listed blob, the blob recomputed from the content and its SHA-256
        must all be the entry's."""

        data = _archive()
        other = _archive(_tar((("other.py", b"x\n"),)))
        self._assert_read(data, FROZEN)
        for name, entry, content, declared in (
            (
                "another listed blob",
                _file(ARCHIVE, "added", blob=_blob_id(other)),
                data,
                _archives(data),
            ),
            ("content of other bytes", _archive_file(data), other, _archives(data)),
            (
                "another declared blob",
                _archive_file(data),
                data,
                _archives(data, blob="0" * 40),
            ),
            (
                "another declared SHA-256",
                _archive_file(data),
                data,
                _archives(data, sha256="0" * 64),
            ),
            (
                "a listed and declared blob that is not the content's",
                _file(ARCHIVE, "added", blob="0" * 40),
                data,
                _archives(data, blob="0" * 40),
            ),
            (
                "content that is not base64",
                _archive_file(data),
                "not base64!",
                _archives(data),
            ),
            (
                "base64 with a character outside its alphabet",
                _archive_file(data),
                "*" + _content(data),
                _archives(data),
            ),
            ("no content", _archive_file(data), None, _archives(data)),
        ):
            with self.subTest(name):
                contents = {} if content is None else {ARCHIVE: content}
                self.assertEqual(
                    {"coverage": "PARTIAL", "found": []},
                    self._suppressions_of([entry], contents, declared=declared),
                )

    def test_a_declared_path_with_hunks_or_another_status_is_read_as_today(
        self,
    ) -> None:
        """I3: a patch, a count of additions, a cut patch, a removal, a rename or a
        mode change is never read as an archive, whatever is declared and
        attached."""

        data = _archive()
        self._assert_read(data, FROZEN)
        added = "@@ -0,0 +1 @@\n+a  # noqa"  # not one -- a fixture's added line
        for name, entry in (
            ("a patch", _archive_file(data, patch=added)),
            (
                "a patch that only removes",
                _archive_file(data, "modified", patch="@@ -1 +0,0 @@\n-a", additions=0),
            ),
            ("additions without a patch", _archive_file(data, additions=2)),
            (
                "a truncated patch",
                _archive_file(data, patch="@@ -0,0 +1,1 @@\n+" + "x" * RESPONSE_BUDGET),
            ),
            ("a removal", _archive_file(data, "removed")),
            ("a rename", _archive_file(data, "renamed", previous="docs/old.tar.gz")),
            ("a mode change", _archive_file(data, "changed")),
        ):
            with self.subTest(name):
                today = self._suppressions_of([entry], {ARCHIVE: data}, declared=None)
                declared = self._suppressions_of(
                    [entry], {ARCHIVE: data}, declared=_archives(data)
                )
                self.assertEqual(today, declared)
                self.assertFalse(any("frozen" in r for r in declared["found"]))

    def test_a_listing_l1_never_gives_is_not_read_as_an_archive(self) -> None:
        """I3, on the producer's own input: a cut listing without a patch, or an
        addition count that is not a whole number, is not hunkless, so the declared
        archive is not read and the file stays PARTIAL as today."""

        data = _archive()
        self._assert_read(data, FROZEN)
        for name, listed in (
            ("a cut listing without a patch", {"patch_truncated": True}),
            ("a count that is a boolean", {"additions": False}),
        ):
            with self.subTest(name):
                self.assertEqual(
                    {"coverage": "PARTIAL", "found": []},
                    self._evidence(
                        [_archive_file(data)],
                        {ARCHIVE: data},
                        declared=_archives(data),
                        listed=listed,
                    )["suppressions"],
                )

    def test_each_archive_bound_leaves_it_partial_without_a_record(self) -> None:
        """I4: the whole archive is checked before any record is built, so one
        refusal lists none of its markers. At a bound it is still read."""

        tar = _tar()
        many = tuple((f"m{n:03d}.txt", b"x\n") for n in range(MEMBER_BOUND + 1))
        for name, data, found in (
            ("at the expanded bound", _archive(_tar(size=EXPANDED_BOUND)), FROZEN),
            ("at the member count", _archive(_tar(many[:MEMBER_BOUND])), []),
        ):
            with self.subTest(name):
                self._assert_read(data, found)
        for name, data in (
            ("past the expanded bound", _archive(_tar(size=EXPANDED_BOUND + 1))),
            ("trailing bytes", _archive(tar) + b"\0"),
            ("a second gzip member", _archive(tar) + gzip.compress(b"", mtime=0)),
            ("a truncated stream", _archive(tar)[:-8]),
            ("a member's data cut short", _archive(_cut_in_last_member(tar))),
            ("a second tar after the end", _archive(tar + _tar(LATE))),
            ("bytes after the end", _archive(tar + b"late")),
            ("a zero block before the first member", _archive(bytes(512) + tar)),
            (
                "a header cut short after the last member",
                _archive(_cut_in_last_member(_tar((*MEMBERS, *LATE)), header=True)),
            ),
            ("an uncompressed tar", tar),
            ("bytes that are no archive", b"plain text\n"),
            ("an empty file", b""),
            ("past the member count", _archive(_tar(many))),
            ("a directory", _archive(_tar(then=_directory))),
            ("a symbolic link", _archive(_tar(then=_symbolic_link))),
            ("a hard link", _archive(_tar(then=_hard_link))),
            ("a sparse member", _archive(_tar(then=_sparse))),
            ("an absolute name", _archive(_tar((*MEMBERS, ("/abs.py", b"x\n"))))),
            ("a parent segment", _archive(_tar((*MEMBERS, ("a/../b.py", b"x\n"))))),
            ("a current segment", _archive(_tar((*MEMBERS, ("./c.py", b"x\n"))))),
            ("an empty segment", _archive(_tar((*MEMBERS, ("a//d.py", b"x\n"))))),
            ("a repeated name", _archive(_tar((*MEMBERS, ("spike.py", b"x\n"))))),
            (
                "a member that is not UTF-8",
                _archive(_tar((*MEMBERS, ("bad.py", b"\xff\n")))),
            ),
        ):
            with self.subTest(name):
                self.assertEqual(
                    {"coverage": "PARTIAL", "found": []},
                    self._suppressions_of(
                        [_archive_file(data)], {ARCHIVE: data}, declared=_archives(data)
                    ),
                )

    def test_frozen_records_share_the_comparison_s_budgets(self) -> None:
        """I5: a frozen record is charged as the command writes it, its member and
        flag included, against the one count and byte budget of the comparison.
        Past either, the list keeps its prefix and is PARTIAL."""

        data = _archive()
        declared = _archives(data)
        cap = merge_evidence_github.MAX_SUPPRESSIONS

        def lines(count: int) -> dict[str, Any]:
            body = "\n".join("+a  # noqa -- r" for _ in range(count))
            return _file("t.py", "added", patch=f"@@ -0,0 +1,{count} @@\n{body}")

        fits = self._suppressions_of(
            [lines(cap - len(FROZEN)), _archive_file(data)],
            {ARCHIVE: data},
            declared=declared,
        )
        self.assertEqual(("COMPLETE", cap), (fits["coverage"], len(fits["found"])))
        self.assertEqual(FROZEN, fits["found"][-len(FROZEN) :])
        over = self._suppressions_of(
            [lines(cap - len(FROZEN) + 1), _archive_file(data)],
            {ARCHIVE: data},
            declared=declared,
        )
        self.assertEqual(("PARTIAL", cap), (over["coverage"], len(over["found"])))
        self.assertEqual(FROZEN[:-1], over["found"][1 - len(FROZEN) :])

        budget = merge_evidence_github.MAX_SUPPRESSION_BYTES
        frozen = sum(merge_evidence_github.suppression_record_bytes(r) for r in FROZEN)

        def charged(size: int) -> tuple[dict[str, Any], int]:
            reason = "r" * size
            cost = merge_evidence_github.suppression_record_bytes(
                _found("tools/t.py", 1, "noqa", reason)  # not a suppression -- a record
            )
            patch = f"@@ -0,0 +1 @@\n+a  # noqa --{reason}"
            return _file("tools/t.py", "added", patch=patch), cost

        # From a one-character reason, each more character costs one byte.
        size = budget - frozen - (charged(1)[1] - 1)
        exact, cost = charged(size)
        self.assertEqual(budget, cost + frozen)
        at = self._suppressions_of(
            [exact, _archive_file(data)], {ARCHIVE: data}, declared=declared
        )
        self.assertEqual(
            ("COMPLETE", 1 + len(FROZEN)), (at["coverage"], len(at["found"]))
        )
        past = self._suppressions_of(
            [charged(size + 1)[0], _archive_file(data)],
            {ARCHIVE: data},
            declared=declared,
        )
        self.assertEqual(
            ("PARTIAL", len(FROZEN)), (past["coverage"], len(past["found"]))
        )

    def test_the_declaration_is_closed_and_versioned(self) -> None:
        """I7: in the convention of the other declarations, each entry closed and
        typed; a declaration that is not is an input error."""

        data = _archive()
        entry = _archives(data)["archives"][0]
        cases: list[tuple[str, dict[str, Any]]] = [
            ("another schema", {**_archives(data), "schema_version": "2.0"}),
            ("an unknown key", {**_archives(data), "extra": 1}),
            ("no id", {**_archives(data), "id": ""}),
            ("an empty list", {**_archives(data), "archives": []}),
            ("not a list", {**_archives(data), "archives": entry}),
            (
                "an entry that is not a mapping",
                {**_archives(data), "archives": [ARCHIVE]},
            ),
            ("a repeated path", {**_archives(data), "archives": [entry, entry]}),
        ]
        missing = _archives(data)
        del missing["archives"]
        cases.append(("no archives", missing))
        for key in entry:
            without = _archives(data)
            del without["archives"][0][key]
            cases.append((f"an entry without its {key}", without))
        for name, change in (
            ("an unknown entry key", {"owner": "ktogias"}),
            ("a blob in capitals", {"blob": entry["blob"].upper()}),
            ("a short blob", {"blob": entry["blob"][:39]}),
            ("a SHA-256 in capitals", {"sha256": entry["sha256"].upper()}),
            ("a short SHA-256", {"sha256": entry["sha256"][:63]}),
            ("another format", {"format": "tar+xz"}),
            ("a decision that is a number", {"decision": 134}),
            ("a decision of three digits", {"decision": "134"}),
            ("a blank path", {"path": " "}),
            ("an absolute path", {"path": "/" + ARCHIVE}),
            ("a parent segment in the path", {"path": "docs/../" + ARCHIVE}),
            ("a path that is not text", {"path": 7}),
        ):
            cases.append((name, _archives(data, **change)))
        for name, document in cases:
            # The listing is built before its block, so only the read can raise
            # (Sonar S5778 on #489).
            files = [_archive_file(data)]
            with self.subTest(name), self.assertRaises(INPUT_ERRORS):
                self._evidence(files, {ARCHIVE: data}, declared=document)

    def test_the_declaration_is_read_from_the_project_root_only(self) -> None:
        """I7: the candidate's own declaration in its diff declares nothing; without
        one on the protected target, no archive is declared."""

        data = _archive()
        text = yaml.safe_dump(_archives(data)).splitlines()
        patch = f"@@ -0,0 +1,{len(text)} @@\n" + "\n".join(f"+{line}" for line in text)
        files = [
            _file(str(FROZEN_ARCHIVES), "added", patch=patch),
            _archive_file(data),
        ]
        self.assertEqual(
            {"coverage": "PARTIAL", "found": []},
            self._suppressions_of(files, {ARCHIVE: data}, declared=None),
        )
        self.assertEqual(
            {"coverage": "COMPLETE", "found": FROZEN},
            self._suppressions_of(files, {ARCHIVE: data}, declared=_archives(data)),
        )

    def test_the_repository_declaration_ships_the_owner_chosen_archive(self) -> None:
        """Q3 (PAO 6761351016): the protected declaration names exactly the archive
        the owner chose under (c), under the Decision that admits it, and the
        guardrail lists it."""

        path = ROOT / FROZEN_ARCHIVES
        self.assertTrue(path.is_file(), f"{FROZEN_ARCHIVES} is missing")
        self.assertEqual(
            {
                "schema_version": "1.0",
                "id": "gnostoa.merge-frozen-archives",
                "version": "0.1.0",
                "archives": [SHIPPED_ARCHIVE],
            },
            yaml.safe_load(path.read_text(encoding="utf-8")),
        )
        self.assertIn(ARCHIVE_DECISION, merge_evidence_github.load_decisions(ROOT))
        self.assertIn(
            str(FROZEN_ARCHIVES), _merge_evidence_guardrail()["implementation"]
        )


def _blob_url(blob: str) -> str:
    return f"{API}/git/blobs/{blob}"


def _blob_reply(data: bytes, **changes: Any) -> tuple[Any, dict[str, str]]:
    """GitHub's answer for one blob: its base64 in lines of 60, as the API sends
    it."""

    encoded = _content(data)
    blob = _blob_id(data)
    payload = {
        "sha": blob,
        "node_id": "B_kwDOtest",
        "size": len(data),
        "url": _blob_url(blob),
        "content": "".join(
            encoded[i : i + 60] + "\n" for i in range(0, len(encoded), 60)
        ),
        "encoding": "base64",
        **changes,
    }
    return payload, {}


def _collect_blobs(
    files: list[dict[str, Any]],
    blobs: Mapping[str, tuple[Any, dict[str, str]]],
    *,
    refused: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """L1's merge-evidence snapshot of `files`, with `blobs` answered by their URL;
    `refused`, and any other blob, refused as the client refuses a read (an
    unknown blob is GitHub's 404); and every blob read attempted, in order."""

    replies = _replies()
    replies[COMPARE] = _comparison(
        [_commit(HEAD, "Admit or deny one merge\n\nRefs #407")], files
    )
    replies.update(blobs)
    adapter = adapter_fixture()
    fake = paged_fake_fixture(replies)
    answer: Callable[[str], tuple[Any, dict[str, str]]] = fake.get

    def get(url: str) -> tuple[Any, dict[str, str]]:
        if url == refused or ("/git/blobs/" in url and url not in blobs):
            raise adapter.ProviderReadError(f"provider refused {url!r}")
        return answer(url)

    with mock.patch.object(fake, "get", side_effect=get) as reads:
        snapshot: dict[str, Any] = adapter.collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
            merge_evidence=True,
        )
    urls = [call.args[0] for call in reads.call_args_list]
    return snapshot, [url for url in urls if "/git/blobs/" in url]


class FrozenArchiveCollectionTests(unittest.TestCase):
    """L1 attaches a hunkless file's content for the producer, verified and
    bounded, and reads no declaration (PAO Q1-A; I8 of 6761333802). Whatever it
    does not attach leaves the file exactly as today."""

    def test_a_hunkless_file_s_blob_is_read_once_and_attached(self) -> None:
        data = _archive()
        ordinary = _file("tools/x.py", patch="@@ -1 +1 @@\n-a\n+b")
        url = _blob_url(_blob_id(data))
        for status in ("added", "modified"):
            with self.subTest(status):
                snapshot, reads = _collect_blobs(
                    [ordinary, _archive_file(data, status)], {url: _blob_reply(data)}
                )
                self.assertEqual([url], reads)
                kept, archived = snapshot["files"]
                self.assertNotIn("content", kept)
                self.assertEqual(_content(data), archived.get("content"))
                self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])

    def test_only_a_hunkless_added_or_modified_non_empty_blob_is_read(self) -> None:
        data = _archive()
        blobs = {_blob_url(_blob_id(data)): _blob_reply(data)}
        snapshot, _ = _collect_blobs([_archive_file(data)], blobs)
        self.assertEqual(_content(data), snapshot["files"][0].get("content"))
        for name, entry in (
            ("a patch", _archive_file(data, patch="@@ -0,0 +1 @@\n+a")),
            (
                "a patch that only removes",
                _archive_file(data, "modified", patch="@@ -1 +0,0 @@\n-a", additions=0),
            ),
            ("additions without a patch", _archive_file(data, additions=1)),
            ("a removal", _archive_file(data, "removed")),
            ("a rename", _archive_file(data, "renamed", previous="docs/old.tar.gz")),
            ("a mode change", _archive_file(data, "changed")),
            ("an empty blob", _file(ARCHIVE, "added", blob=EMPTY_BLOB)),
            ("no blob", _file(ARCHIVE, "added", blob=None)),
            (
                "a blob that is not an id",
                _file(ARCHIVE, "added", blob="../" + "0" * 37),
            ),
        ):
            with self.subTest(name):
                snapshot, reads = _collect_blobs([entry], blobs)
                self.assertEqual([], reads)
                self.assertNotIn("content", snapshot["files"][0])

    def test_a_blob_answer_that_does_not_verify_gives_no_content(self) -> None:
        """The blob id recomputed from strict base64 must be the listed one, and
        each blob is at most BLOB_BOUND bytes by its answer's size. A refused read
        gives no content and leaves the file list COMPLETE."""

        data = _archive()
        other = _archive(_tar((("other.py", b"x\n"),)))
        at_bound, past_bound = bytes(BLOB_BOUND), bytes(BLOB_BOUND + 1)
        for control in (data, at_bound):
            snapshot, _ = _collect_blobs(
                [_archive_file(control)],
                {_blob_url(_blob_id(control)): _blob_reply(control)},
            )
            self.assertEqual(_content(control), snapshot["files"][0].get("content"))
        url = _blob_url(_blob_id(data))
        for name, entry, answer, refused in (
            (
                "another sha",
                _archive_file(data),
                _blob_reply(data, sha=_blob_id(other)),
                None,
            ),
            (
                "other bytes",
                _archive_file(data),
                _blob_reply(other, sha=_blob_id(data), url=url),
                None,
            ),
            (
                "another encoding",
                _archive_file(data),
                _blob_reply(data, encoding="utf-8"),
                None,
            ),
            (
                "content that is not base64",
                _archive_file(data),
                _blob_reply(data, content="not base64!"),
                None,
            ),
            (
                "base64 with a character outside its alphabet",
                _archive_file(data),
                _blob_reply(data, content="*" + _content(data)),
                None,
            ),
            (
                "a size that is not the content's",
                _archive_file(data),
                _blob_reply(data, size=len(data) + 1),
                None,
            ),
            (
                "a size that is text",
                _archive_file(data),
                _blob_reply(data, size="1"),
                None,
            ),
            (
                "past the blob bound",
                _archive_file(past_bound),
                _blob_reply(past_bound),
                None,
            ),
            ("an answer that is not an object", _archive_file(data), ([], {}), None),
            ("a refused read", _archive_file(data), _blob_reply(data), url),
        ):
            with self.subTest(name):
                snapshot, _ = _collect_blobs(
                    [entry], {_blob_url(entry["sha"]): answer}, refused=refused
                )
                self.assertNotIn("content", snapshot["files"][0])
                self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])

    def test_blob_reads_are_bounded_in_count_and_in_total(self) -> None:
        """At most BLOB_READS distinct blobs read per comparison, in its order, and
        at most BLOB_TOTAL bytes attached in all; a file past either gets no
        content. A blob listed again is no second read (Decision 0134, item 2)."""

        same, other = bytes(16), bytes([1]) * 16
        files = [
            _file(f"docs/s{n}.bin", "added", blob=_blob_id(same))
            for n in range(BLOB_READS)
        ]
        files.append(_file("docs/other.bin", "added", blob=_blob_id(other)))
        with self.subTest("a blob listed again"):
            snapshot, reads = _collect_blobs(
                files,
                {
                    _blob_url(_blob_id(data)): _blob_reply(data)
                    for data in (same, other)
                },
            )
            self.assertEqual(
                [*([_content(same)] * BLOB_READS), _content(other)],
                [item.get("content") for item in snapshot["files"]],
            )
            self.assertEqual(
                [_blob_url(_blob_id(data)) for data in (same, other)], reads
            )

        for name, blobs in (
            ("past the read count", [bytes([n]) * 16 for n in range(BLOB_READS + 1)]),
            (
                "past the total",
                [bytes([n]) * BLOB_BOUND for n in range(BLOB_TOTAL // BLOB_BOUND + 1)],
            ),
        ):
            with self.subTest(name):
                files = [
                    _file(f"docs/b{n}.bin", "added", blob=_blob_id(data))
                    for n, data in enumerate(blobs)
                ]
                snapshot, reads = _collect_blobs(
                    files,
                    {_blob_url(_blob_id(data)): _blob_reply(data) for data in blobs},
                )
                self.assertEqual(
                    [*(_content(data) for data in blobs[:-1]), None],
                    [item.get("content") for item in snapshot["files"]],
                )
                if name == "past the read count":
                    self.assertEqual(
                        [_blob_url(_blob_id(data)) for data in blobs[:-1]], reads
                    )


class FrozenVerdictTests(unittest.TestCase):
    """M13 over frozen records (I6 of 6761333802): listed for the approval apart
    from the justified ones, never denying, and closed and typed."""

    def test_a_frozen_record_is_listed_apart_and_never_denies(self) -> None:
        evidence = _verdict_evidence()
        evidence["suppressions"]["found"] = copy.deepcopy(FROZEN)
        verdict = _verdict(evidence)
        self.assertEqual("ALLOW", verdict["status"])
        self.assertEqual([], verdict["for_approval"]["suppressions"])
        self.assertEqual(FROZEN, verdict["for_approval"]["frozen_suppressions"])
        partial = _verdict_evidence()
        partial["suppressions"] = {
            "coverage": "PARTIAL",
            "found": copy.deepcopy(FROZEN),
        }
        self.assertEqual(
            ["suppression coverage is PARTIAL"],
            _verdict_failed(_verdict(partial))["M13"],
        )

    def test_a_record_that_is_not_frozen_still_denies(self) -> None:
        justified = _found("tools/z.py", 1, "noqa", "why")  # not one -- a record
        evidence = _verdict_evidence()
        evidence["suppressions"]["found"] = [
            *copy.deepcopy(FROZEN),
            _found("tools/y.py", 12, "noqa"),  # not a suppression -- a record
            justified,
        ]
        verdict = _verdict(evidence)
        self.assertEqual(
            ["noqa in tools/y.py:12 has no justification"],  # not one -- a reason
            _verdict_failed(verdict)["M13"],
        )
        self.assertEqual([justified], verdict["for_approval"]["suppressions"])
        self.assertEqual(FROZEN, verdict["for_approval"]["frozen_suppressions"])
        self.assertEqual(
            [], _verdict(_verdict_evidence())["for_approval"]["frozen_suppressions"]
        )

    def test_a_frozen_record_is_closed_and_typed(self) -> None:
        """A member only with the flag, the flag only true, and both only with a
        line; anything else is malformed evidence."""

        record = FROZEN[0]
        accepted = _verdict_evidence()
        accepted["suppressions"]["found"] = [dict(record)]
        self.assertEqual("ALLOW", _verdict(accepted)["status"])
        for name, broken in (
            ("no member", {k: v for k, v in record.items() if k != "member"}),
            ("no line", {k: v for k, v in record.items() if k != "line"}),
            (
                "a member without the flag",
                {k: v for k, v in record.items() if k != "frozen"},
            ),
            ("a member that is not text", {**record, "member": 7}),
            ("a blank member", {**record, "member": " "}),
            ("a flag that is text", {**record, "frozen": "true"}),
            ("a flag of one", {**record, "frozen": 1}),
            ("a false flag", {**record, "frozen": False}),
        ):
            with self.subTest(name):
                evidence = _verdict_evidence()
                evidence["suppressions"]["found"] = [broken]
                with self.assertRaises(INPUT_ERRORS):
                    _verdict(evidence)


class GuardrailRegistrationTests(unittest.TestCase):
    def test_every_test_in_this_module_is_registered_in_its_guardrail(self) -> None:
        self.assertEqual(
            set(),
            unregistered_tests(globals(), "tests/test_merge_evidence_suppressions.py"),
        )


if __name__ == "__main__":
    unittest.main()
