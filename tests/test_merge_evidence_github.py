"""The GitHub evidence adapter, MA0 Phase 1b slice 1b.3a (#407).

Every adapter test runs on a snapshot that L1 itself collects from the fake
provider, which refuses any URL it was not given, so a mismatch between L1's
contract and the adapter's fails here rather than in production.
"""

from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml
from test_review_reconcile_l1 import (
    adapter_fixture,
    complete_replies_fixture,
    paged_fake_fixture,
)

from tools import assurance_completeness, merge_admission, merge_evidence_github

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com/repos/ktogias/gnostoa"
HEAD = "a" * 40
BASE = "b" * 40
PREVIOUS = "d" * 40
# The comparison of the subject's exact base and head, which L1 already reads for
# the merge base, and the GraphQL page of the conversation's edit state.
COMPARE = f"{API}/compare/{BASE}...{HEAD}"
EDITS = "graphql:comments:first"
# The GraphQL page of the issues the merge would close (#413 round 10).
CLOSING = "graphql:closingIssuesReferences:first"
DECLARER = "gnostoa-agent[bot]"
BODY = """## Outcome

The verdict reads normalized evidence.

## Change control

- Class: `normative`
- Work Item: #407, #15
- Decision: [0112](knowledge/decisions/0112-admit-merges.md)
- Accountable owner: @ktogias
"""


def _commit(sha: str, message: str) -> dict[str, Any]:
    return {"sha": sha, "commit": {"message": message}}


FILES = [
    {"filename": "tools/merge_admission.py", "status": "added"},
    {"filename": "tests/test_merge_admission.py", "status": "added"},
]


def _comparison(
    commits: list[dict[str, Any]],
    files: list[dict[str, Any]],
    *,
    total: int | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """GitHub's comparison of the exact base and head: its merge base, its commits
    with their total, and its changed files."""

    return (
        {
            "merge_base_commit": {"sha": "c" * 40},
            "total_commits": len(commits) if total is None else total,
            "commits": commits,
            "files": files,
        },
        {},
    )


def _closing(
    *issues: tuple[str, int], next_cursor: str | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """The issues the merge would close, keyword-linked or linked by hand."""

    page = {
        "nodes": [
            {"number": number, "repository": {"nameWithOwner": repository}}
            for repository, number in issues
        ],
        "pageInfo": {"hasNextPage": next_cursor is not None, "endCursor": next_cursor},
    }
    return {
        "data": {"repository": {"pullRequest": {"closingIssuesReferences": page}}}
    }, {}


def _edits(*comments: tuple[int, str | None]) -> tuple[dict[str, Any], dict[str, str]]:
    """The conversation's edit state: each comment's id and `lastEditedAt`, null
    when it was never edited."""

    page = {
        "nodes": [{"databaseId": i, "lastEditedAt": at} for i, at in comments],
        "pageInfo": {"hasNextPage": False, "endCursor": None},
    }
    return {"data": {"repository": {"pullRequest": {"comments": page}}}}, {}


def _replies(**changes: Any) -> dict[str, tuple[Any, dict[str, str]]]:
    """PR 300 in the shape of a converged change, with the merge-evidence reads."""

    replies = copy.deepcopy(complete_replies_fixture(API))
    pull = replies[f"{API}/pulls/300"][0]
    pull.update(
        {
            "draft": False,
            "merged": False,
            "title": "Admit or deny one merge",
            "body": BODY,
            "user": {"login": "gnostoa-agent-user"},
        }
    )
    pull["base"]["ref"] = "main"
    pull["base"]["repo"] = {"default_branch": "main"}
    replies[f"{API}/issues/300/comments?per_page=100"] = (
        [
            {
                "id": 1,
                "user": {"login": DECLARER},
                "created_at": "2026-09-19T16:40:00Z",
                "updated_at": "2026-09-19T16:40:00Z",
                "body": f"Exact review candidate: {HEAD}",
            }
        ],
        {},
    )
    replies.pop("https://api.github.com/page2/issues", None)
    first_reviews = replies[f"{API}/pulls/300/reviews?per_page=100"][0]
    first_reviews[0]["user"] = {"login": "ktogias"}
    replies[COMPARE] = _comparison(
        [_commit(HEAD, "Admit or deny one merge\n\nRefs #407")], FILES
    )
    replies[EDITS] = _edits((1, None))
    replies[CLOSING] = _closing()
    for key, value in changes.items():
        replies[key] = value
    return replies


def _snapshot(
    replies: dict[str, tuple[Any, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    adapter = adapter_fixture()
    snapshot: dict[str, Any] = adapter.collect_snapshot(
        paged_fake_fixture(_replies() if replies is None else replies),
        repository="ktogias/gnostoa",
        pull_number=300,
        observed_at="2026-09-19T16:41:00Z",
        merge_evidence=True,
    )
    return snapshot


def _authorities() -> dict[str, Any]:
    return merge_evidence_github.parse_authorities(
        {
            "schema_version": "1.0",
            "id": "example.merge-authorities",
            "version": "0.1.0",
            "declarer": DECLARER,
            "human_approvers": ["ktogias"],
        }
    )


def _policy() -> dict[str, Any]:
    return merge_admission.load_policy(
        ROOT / "policy" / "change-control.yaml", project_root=ROOT
    )


def _evidence(
    snapshot: dict[str, Any] | None = None,
    *,
    codeowners: str = "* @ktogias\n",
) -> dict[str, Any]:
    return merge_evidence_github.evidence_from_snapshot(
        _snapshot() if snapshot is None else snapshot,
        authorities=_authorities(),
        change_policy=_policy(),
        codeowners=merge_evidence_github.parse_codeowners(codeowners),
        decisions=merge_evidence_github.load_decisions(ROOT),
    )


def _failed(evidence: dict[str, Any]) -> dict[str, list[str]]:
    declaration = assurance_completeness.load_declaration(
        ROOT / "policy" / "assurance-evidence.yaml", project_root=ROOT
    )
    verdict = merge_admission.evaluate(
        evidence, declaration=declaration, change_policy=_policy()
    )
    return {c["id"]: c["reasons"] for c in verdict["criteria"] if c["status"] == "FAIL"}


class L1MergeEvidenceSnapshotTests(unittest.TestCase):
    def test_the_default_snapshot_is_unchanged_and_reads_nothing_new(self) -> None:
        """The current-state advisory keeps its reads and its keys."""
        adapter = adapter_fixture()
        fake = paged_fake_fixture(complete_replies_fixture(API))
        snapshot = adapter.collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )
        self.assertNotIn("commits", snapshot)
        self.assertNotIn("files", snapshot)
        self.assertNotIn("draft", snapshot["subject"])
        self.assertFalse(
            any("/commits?" in url or "/files?" in url for url in fake.calls)
        )
        self.assertNotIn(EDITS, fake.calls)
        self.assertNotIn(CLOSING, fake.calls)
        self.assertNotIn("edited", snapshot["conversation"][0])

    def test_merge_evidence_adds_the_pull_fields_and_two_sources(self) -> None:
        snapshot = _snapshot()
        subject = snapshot["subject"]
        self.assertEqual(
            {
                "draft": False,
                "merged": False,
                "target": "main",
                "author": "gnostoa-agent-user",
                "body": BODY,
                "body_truncated": False,
            },
            {
                key: subject[key]
                for key in (
                    "draft",
                    "merged",
                    "target",
                    "author",
                    "body",
                    "body_truncated",
                )
            },
        )
        self.assertEqual("main", subject["default_branch"])
        self.assertEqual("COMPLETE", snapshot["coverage"]["commits"]["status"])
        self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])
        self.assertEqual(
            [
                {
                    "sha": HEAD,
                    "message": "Admit or deny one merge\n\nRefs #407",
                    "message_truncated": False,
                }
            ],
            snapshot["commits"],
        )
        self.assertEqual(
            ["tools/merge_admission.py", "tests/test_merge_admission.py"],
            [item["path"] for item in snapshot["files"]],
        )

    def test_a_comparison_short_of_its_total_commits_is_partial(self) -> None:
        """A comparison lists at most 250 commits; its total says how many it has."""
        commits = [_commit(f"{index:040x}", "x") for index in range(250)]
        whole = _snapshot(_replies(**{COMPARE: _comparison(commits, FILES)}))
        self.assertEqual("COMPLETE", whole["coverage"]["commits"]["status"])
        self.assertEqual(250, len(whole["commits"]))
        short = _snapshot(_replies(**{COMPARE: _comparison(commits, FILES, total=251)}))
        self.assertEqual("PARTIAL", short["coverage"]["commits"]["status"])
        self.assertEqual("commit_list_cap", short["coverage"]["commits"]["reason"])

    def test_a_comparison_s_total_is_a_count(self) -> None:
        """cubic on #413: a comparison with no commits is empty, not an error; a
        missing or non-integer total is."""
        empty = _snapshot(_replies(**{COMPARE: _comparison([], [])}))
        for source in ("commits", "files"):
            with self.subTest(source=source):
                self.assertEqual(
                    {"status": "COMPLETE", "pages": 1, "count": 0},
                    empty["coverage"][source],
                )
        for name, total in (("missing", None), ("text", "1"), ("negative", -1)):
            with self.subTest(total=name):
                reply = _comparison([_commit(HEAD, "x")], FILES)
                if total is None:
                    del reply[0]["total_commits"]
                else:
                    reply[0]["total_commits"] = total
                snapshot = _snapshot(_replies(**{COMPARE: reply}))
                self.assertEqual("ERROR", snapshot["coverage"]["commits"]["status"])
                self.assertEqual("ERROR", snapshot["coverage"]["files"]["status"])

    def test_the_comparison_s_file_cap_is_partial(self) -> None:
        """GitHub lists at most 300 files on a comparison, so a list that reaches
        300 may be cut."""

        def files(count: int) -> list[dict[str, Any]]:
            return [{"filename": f"f/{n}", "status": "added"} for n in range(count)]

        commits = [_commit(HEAD, "x")]
        whole = _snapshot(_replies(**{COMPARE: _comparison(commits, files(299))}))
        self.assertEqual("COMPLETE", whole["coverage"]["files"]["status"])
        self.assertEqual(299, len(whole["files"]))
        # The owner accepted 300 as initial MA0's domain (#407, 6084981368).
        for count in (300, 301):
            with self.subTest(files=count):
                capped = _snapshot(
                    _replies(**{COMPARE: _comparison(commits, files(count))})
                )
                coverage = capped["coverage"]["files"]
                self.assertEqual("PARTIAL", coverage["status"])
                self.assertEqual("file_list_cap", coverage["reason"])

    def test_a_commit_without_a_message_is_not_read(self) -> None:
        """CodeAnt on #413: a commit message that is not a string was read as
        an empty one, so M12 reported COMPLETE without reading it. It now fails
        the comparison read, which the files share, so the run fails. An empty
        string is still a message."""
        unread = _snapshot(
            _replies(**{COMPARE: _comparison([{"sha": HEAD, "commit": {}}], FILES)})
        )
        self.assertNotEqual("COMPLETE", unread["coverage"]["commits"]["status"])
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(unread)
        empty = _snapshot(
            _replies(**{COMPARE: _comparison([_commit(HEAD, "")], FILES)})
        )
        self.assertEqual("COMPLETE", empty["coverage"]["commits"]["status"])

    def test_a_long_commit_message_is_bounded_and_marked(self) -> None:
        message = "x" * 70_000
        snapshot = _snapshot(
            _replies(**{COMPARE: _comparison([_commit(HEAD, message)], FILES)})
        )
        self.assertTrue(snapshot["commits"][0]["message_truncated"])
        # Bounded, not only flagged (cubic on #413).
        self.assertLessEqual(
            len(snapshot["commits"][0]["message"].encode("utf-8")), 65_536
        )

    def test_the_lists_are_the_exact_comparison_s(self) -> None:
        """cubic and Claude on #413: the pull request's commit and file lists are
        not bound to the head they were read with. The comparison of the
        subject's exact base and head is a function of those two commits."""
        commits = [_commit(PREVIOUS, "first"), _commit(HEAD, "second")]
        files = [{"filename": "docs/x.md", "status": "modified"}]
        fake = paged_fake_fixture(_replies(**{COMPARE: _comparison(commits, files)}))
        snapshot = adapter_fixture().collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
            merge_evidence=True,
        )
        self.assertEqual([PREVIOUS, HEAD], [c["sha"] for c in snapshot["commits"]])
        self.assertEqual(["docs/x.md"], [f["path"] for f in snapshot["files"]])
        self.assertEqual("COMPLETE", snapshot["coverage"]["commits"]["status"])
        self.assertEqual("COMPLETE", snapshot["coverage"]["files"]["status"])
        self.assertIn(COMPARE, fake.calls)
        self.assertFalse(
            any(
                "/pulls/300/commits" in u or "/pulls/300/files" in u for u in fake.calls
            )
        )

    def test_the_issues_the_merge_would_close_are_read(self) -> None:
        """Codex on #413: an issue linked by hand closes on merge too, and only
        `closingIssuesReferences` lists it (#407, 6086122133)."""
        snapshot = _snapshot(_replies(**{CLOSING: _closing(("ktogias/gnostoa", 407))}))
        self.assertEqual(
            [{"repository": "ktogias/gnostoa", "number": 407}],
            snapshot["closing_issues"],
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["closing_issues"]["status"])

    def test_each_comment_carries_its_edit_state(self) -> None:
        """Codex on #413: timestamps in whole seconds cannot show an edit made in
        the second the comment was posted. GraphQL's `lastEditedAt` can."""
        for edited_at, edited in ((None, False), ("2026-09-19T16:40:00Z", True)):
            with self.subTest(edited=edited):
                snapshot = _snapshot(_replies(**{EDITS: _edits((1, edited_at))}))
                self.assertEqual(edited, snapshot["conversation"][0]["edited"])
                self.assertEqual(
                    "COMPLETE", snapshot["coverage"]["conversation"]["status"]
                )

    def test_a_comment_without_its_edit_state_makes_the_conversation_partial(
        self,
    ) -> None:
        malformed = _edits((1, None))
        malformed[0]["data"]["repository"]["pullRequest"]["comments"]["nodes"] = {}
        # The first page lists the comment, but the read was cut after it.
        cut = _edits((1, None))
        cut[0]["data"]["repository"]["pullRequest"]["comments"]["pageInfo"] = {
            "hasNextPage": True,
            "endCursor": None,
        }
        for name, reply in (
            ("missing comment", _edits((2, None))),
            ("malformed page", malformed),
            ("cut read", cut),
        ):
            with self.subTest(name):
                snapshot = _snapshot(_replies(**{EDITS: reply}))
                coverage = snapshot["coverage"]["conversation"]
                self.assertEqual("PARTIAL", coverage["status"])
                self.assertEqual("comment_edits_unavailable", coverage["reason"])
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)

    def test_a_head_that_moves_between_reads_is_refused(self) -> None:
        """L1's collector is composed, not changed (DeepSource on #413): the pull
        request is read again for the merge-evidence fields, and a change in
        between fails the read, as L1 refuses a changed identity. cubic on #413:
        the state and title too, not only the head."""
        for name, change in (
            ("head", {"head": {"sha": "e" * 40}}),
            ("state", {"state": "closed"}),
            ("title", {"title": "Fixes #12"}),
            # CodeAnt on #413: the first read binds the number; so does this one.
            ("number", {"number": 301}),
        ):
            with self.subTest(name):
                self._assert_refused_when_second_read_differs(change)

    def _assert_refused_when_second_read_differs(self, change: dict[str, Any]) -> None:
        adapter = adapter_fixture()
        replies = _replies()
        fake = paged_fake_fixture(replies)
        moved = copy.deepcopy(replies[f"{API}/pulls/300"])
        moved[0].update(change)
        reads = {"pull": 0}
        original = fake.get

        def get(url: str) -> tuple[Any, dict[str, str]]:
            if url == f"{API}/pulls/300":
                reads["pull"] += 1
                if reads["pull"] % 2 == 0:
                    return moved
            reply: tuple[Any, dict[str, str]] = original(url)
            return reply

        fake.get = get
        with self.assertRaises(adapter.ProviderReadError):
            adapter.collect_snapshot(
                fake,
                repository="ktogias/gnostoa",
                pull_number=300,
                observed_at="2026-09-19T16:41:00Z",
                merge_evidence=True,
            )

    def test_a_description_edited_during_collection_is_paired_with_later_reads(
        self,
    ) -> None:
        """CodeAnt on #413: an edit between the two pull reads cannot pair the new
        description with reviews read before it. L1 certifies only two identical
        passes, the second starting after the first ends."""
        replies = _replies()
        pull_url = f"{API}/pulls/300"
        reviews_url = f"{API}/pulls/300/reviews?per_page=100"
        edited = _replies()
        edited[pull_url][0]["body"] = BODY + "\nEdited.\n"
        for review in edited[reviews_url][0]:
            review["state"] = "CHANGES_REQUESTED"
        fake = paged_fake_fixture(replies)
        reads = {"pull": 0}
        original = fake.get

        def get(url: str) -> tuple[Any, dict[str, str]]:
            if url == pull_url:
                reads["pull"] += 1
                if reads["pull"] == 2:
                    # The body and the reviews change together, mid-pass.
                    replies[pull_url] = edited[pull_url]
                    replies[reviews_url] = edited[reviews_url]
            reply: tuple[Any, dict[str, str]] = original(url)
            return reply

        fake.get = get
        snapshot = adapter_fixture().collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
            merge_evidence=True,
        )
        after = _snapshot(edited)
        self.assertEqual("STABLE_READBACK", snapshot["collection"]["status"])
        self.assertEqual(after["subject"]["body"], snapshot["subject"]["body"])
        self.assertEqual(after["reviews"], snapshot["reviews"])

    def test_the_reconciler_s_snapshot_validation_accepts_the_extension(self) -> None:
        from tools import review_reconcile

        subject, _, coverage = review_reconcile.validate_snapshot(_snapshot())
        self.assertEqual(HEAD, subject["head_commit"])
        self.assertEqual("COMPLETE", coverage["reviews"]["status"])


def _owners(text: str, path: str) -> list[str] | None:
    return merge_evidence_github.parse_codeowners(text).owners(path)


class CodeOwnersTests(unittest.TestCase):
    def test_the_last_matching_rule_wins(self) -> None:
        text = "* @alice\n/docs/ @bob\n"
        self.assertEqual(["@alice"], _owners(text, "tools/x.py"))
        self.assertEqual(["@bob"], _owners(text, "docs/guide.md"))

    def test_patterns_follow_github_s_documented_forms(self) -> None:
        text = "\n".join(
            [
                "*.js @js",
                "**/logs @anylogs",
                "/build/logs/ @logs",
                "docs/* @docs-direct",
                "apps/ @apps",
                "/scripts/run.sh @runner",
            ]
        )
        cases = {
            "web/app.js": ["@js"],
            "build/logs/a/b.txt": ["@logs"],
            "docs/getting-started.md": ["@docs-direct"],
            "docs/build-app/troubleshooting.md": None,
            "deep/apps/x.py": ["@apps"],
            "a/b/logs/x": ["@anylogs"],
            "scripts/run.sh": ["@runner"],
            "other/scripts/run.sh": None,
        }
        for path, owners in cases.items():
            with self.subTest(path=path):
                self.assertEqual(owners, _owners(text, path))

    def test_double_asterisks_are_special_only_as_a_segment(self) -> None:
        """Codex on #413: gitignore's `**` matches across `/` only as a leading
        `**/`, a middle `/**/` or a trailing `/**`; elsewhere it is `*`."""
        text = "* @root\nfoo**bar @x\nup**/down @y\na/**/b @m\nabc/** @t\n"
        cases = {
            "foo/x/bar": ["@root"],
            "fooXYbar": ["@x"],
            "up/x/down": ["@root"],
            "upX/down": ["@y"],
            "a/b": ["@m"],
            "a/x/y/b": ["@m"],
            "abc/x/y": ["@t"],
        }
        for path, owners in cases.items():
            with self.subTest(path=path):
                self.assertEqual(owners, _owners(text, path))

    def test_comments_blank_lines_and_ownerless_rules(self) -> None:
        text = "# owners\n\n* @alice\n/generated/\n"
        self.assertEqual([], _owners(text, "generated/x"))
        self.assertEqual(["@alice"], _owners(text, "src/x"))

    def test_an_inline_comment_ends_a_rule_s_owners(self) -> None:
        """Codex on #413: GitHub documents `*.js @js-owner #This is an inline
        comment.`"""
        text = "*.js @js-owner #This is an inline comment.\n/apps/ @a # @b\n"
        self.assertEqual(["@js-owner"], _owners(text, "web/app.js"))
        self.assertEqual(["@a"], _owners(text, "apps/x"))
        self.assertEqual([], _owners("/apps/ # none\n", "apps/x"))
        # Only a word that starts with `#` opens a comment.
        self.assertEqual(["a#b@example.com"], _owners("* a#b@example.com\n", "x"))

    def test_malformed_segments_are_refused(self) -> None:
        """Codex on #413, and the owner's choice (#407, 6092909419): git
        matches nothing for an empty or dot segment, but `//sensitive` was
        read as `/sensitive` and could replace an earlier rule's owners."""
        refused = (
            "/sensitive @alice\n//sensitive @bob\n",
            "//sensitive @alice\n",
            "docs//x @alice\n",
            "sensitive// @alice\n",
            "docs/./x @alice\n",
            "./docs @alice\n",
            "a/../docs/x @alice\n",
            "docs/. @alice\n",
            ".. @alice\n",
        )
        for text in refused:
            with (
                self.subTest(text=text),
                self.assertRaises(merge_evidence_github.MergeEvidenceError),
            ):
                merge_evidence_github.parse_codeowners(text)
        accepted = {
            ("/sensitive @alice\n", "sensitive/x"): ["@alice"],
            ("docs/ @alice\n", "docs/x"): ["@alice"],
            ("**/logs @alice\n", "a/logs/x"): ["@alice"],
            ("*.js @alice\n", "web/app.js"): ["@alice"],
            (".github/ @alice\n", ".github/CODEOWNERS"): ["@alice"],
            ("/.gitignore @alice\n", ".gitignore"): ["@alice"],
        }
        for (text, path), owners in accepted.items():
            with self.subTest(text=text):
                self.assertEqual(owners, _owners(text, path))

    def test_syntax_github_does_not_support_is_refused(self) -> None:
        for line in ("!/keep @alice", "/file[0-9].txt @alice", "\\#literal @alice"):
            with (
                self.subTest(line=line),
                self.assertRaises(merge_evidence_github.MergeEvidenceError),
            ):
                merge_evidence_github.parse_codeowners(line + "\n")

    def test_the_protected_target_s_file_is_found_in_github_s_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "CODEOWNERS").write_text("* @docs\n", encoding="utf-8")
            (root / "CODEOWNERS").write_text("* @root\n", encoding="utf-8")
            self.assertEqual(
                ["@root"],
                merge_evidence_github.load_codeowners(root).owners("x"),
            )
            (root / ".github").mkdir()
            (root / ".github" / "CODEOWNERS").write_text(
                "* @github\n", encoding="utf-8"
            )
            self.assertEqual(
                ["@github"],
                merge_evidence_github.load_codeowners(root).owners("x"),
            )

    def test_a_file_over_github_s_limit_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CODEOWNERS").write_text(
                "# " + "x" * (3 * 1024 * 1024) + "\n", encoding="utf-8"
            )
            with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                merge_evidence_github.load_codeowners(root)


class EvidenceDocumentTests(unittest.TestCase):
    def test_a_converged_change_fails_only_on_evidence_not_yet_produced(self) -> None:
        """Receipts are 1b.3b's and 1b.3c's; so are suppressions and trust roots."""
        evidence = _evidence()
        self.assertEqual({"M2-M8", "M13", "M15"}, set(_failed(evidence)))
        self.assertEqual(
            {
                "repository": "https://github.com/ktogias/gnostoa",
                "change_request": {"kind": "github-pull-request", "id": "300"},
                "head_commit": HEAD,
            },
            evidence["subject"],
        )
        self.assertEqual(
            {
                "state": "open",
                "draft": False,
                "target": "main",
                "protected_target": "main",
            },
            evidence["lifecycle"],
        )
        self.assertEqual("normative", evidence["change_class"])
        self.assertEqual(
            {"work_items": ["#407", "#15"], "decisions": ["0112"]}, evidence["links"]
        )
        self.assertEqual(
            {"declarer": DECLARER, "head_commit": HEAD}, evidence["declared_candidate"]
        )
        self.assertEqual(
            {
                "declarer": DECLARER,
                "author": "gnostoa-agent-user",
                "required_approvers": ["ktogias"],
            },
            evidence["authorities"],
        )
        self.assertEqual({"coverage": "COMPLETE", "unresolved": 0}, evidence["threads"])
        self.assertEqual(
            {"coverage": "COMPLETE", "found": []}, evidence["closing_references"]
        )
        self.assertEqual("UNAVAILABLE", evidence["suppressions"]["coverage"])
        self.assertEqual("UNAVAILABLE", evidence["trust_root_changes"]["coverage"])
        self.assertEqual([], evidence["receipts"])

    def test_an_unsealed_head_denies(self) -> None:
        """#338: the head was never declared."""
        snapshot = _snapshot(
            _replies(
                **{f"{API}/issues/300/comments?per_page=100": ([], {}), EDITS: _edits()}
            )
        )
        evidence = _evidence(snapshot)
        self.assertIsNone(evidence["declared_candidate"])
        self.assertIn("M9", _failed(evidence))

    def test_only_an_unedited_seal_by_the_declarer_counts(self) -> None:
        def comment(**changes: Any) -> dict[str, Any]:
            return {
                "id": 1,
                "user": {"login": DECLARER},
                "created_at": "2026-09-19T16:40:00Z",
                "updated_at": "2026-09-19T16:40:00Z",
                "body": f"Exact review candidate: {HEAD}",
                **changes,
            }

        for name, comments in (
            ("edited", [comment(updated_at="2026-09-19T16:40:30Z")]),
            ("edited in its own second", [comment(edited_at="2026-09-19T16:40:00Z")]),
            ("foreign", [comment(user={"login": "someone-else"})]),
            ("previous head", [comment(body=f"Exact review candidate: {PREVIOUS}")]),
            (
                "not the first line",
                [comment(body=f"Note\nExact review candidate: {HEAD}")],
            ),
            (
                "superseded",
                [
                    comment(),
                    comment(
                        id=2,
                        created_at="2026-09-19T16:40:10Z",
                        updated_at="2026-09-19T16:40:10Z",
                        body=f"Exact review candidate: {PREVIOUS}",
                    ),
                ],
            ),
        ):
            with self.subTest(name):
                edits = _edits(*((c["id"], c.pop("edited_at", None)) for c in comments))
                snapshot = _snapshot(
                    _replies(
                        **{
                            f"{API}/issues/300/comments?per_page=100": (comments, {}),
                            EDITS: edits,
                        }
                    )
                )
                self.assertIn("M9", _failed(_evidence(snapshot)))

    def test_closing_references_are_found_on_every_surface(self) -> None:
        cases: dict[str, dict[str, Any]] = {
            "title": {f"{API}/pulls/300": None, "title": "Fixes #12: the gate"},
            "body": {
                f"{API}/pulls/300": None,
                "body": BODY + "\nCloses ktogias/gnostoa#13\n",
            },
            "commit body": {
                COMPARE: _comparison(
                    [_commit(HEAD, "Subject\n\nSome context.\nresolved: #14")], FILES
                )
            },
            "issue URL": {
                COMPARE: _comparison(
                    [_commit(HEAD, "fix https://github.com/ktogias/gnostoa/issues/15")],
                    FILES,
                )
            },
        }
        for name, change in cases.items():
            with self.subTest(name):
                replies = _replies()
                pull = replies[f"{API}/pulls/300"][0]
                for key in ("title", "body"):
                    if key in change:
                        pull[key] = change[key]
                for key, value in change.items():
                    if key.startswith("https://") and value is not None:
                        replies[key] = value
                evidence = _evidence(_snapshot(replies))
                self.assertEqual(
                    1,
                    len(evidence["closing_references"]["found"]),
                    evidence["closing_references"],
                )
                self.assertIn("M12", _failed(evidence))

    def test_an_issue_the_merge_would_close_denies(self) -> None:
        """Codex on #413: M12 sees an issue linked by hand, and an incomplete
        read of them is not COMPLETE coverage (#407, 6086122133)."""
        linked = _evidence(
            _snapshot(_replies(**{CLOSING: _closing(("ktogias/gnostoa", 407))}))
        )
        self.assertEqual(
            [
                {
                    "surface": "github.closingIssuesReferences",
                    "reference": "ktogias/gnostoa#407",
                }
            ],
            linked["closing_references"]["found"],
        )
        self.assertIn("M12", _failed(linked))
        # A complete, empty relation leaves M12 to the other sources.
        self.assertNotIn("M12", _failed(_evidence()))
        # A second page is read too.
        paged = _evidence(
            _snapshot(
                _replies(
                    **{
                        CLOSING: _closing(next_cursor="page-2"),
                        "graphql:closingIssuesReferences:page-2": _closing(
                            ("ktogias/gnostoa", 15)
                        ),
                    }
                )
            )
        )
        self.assertEqual(
            ["ktogias/gnostoa#15"],
            [f["reference"] for f in paged["closing_references"]["found"]],
        )
        malformed = _closing()
        malformed[0]["data"]["repository"]["pullRequest"]["closingIssuesReferences"][
            "nodes"
        ] = {}
        missing = _closing()
        del missing[0]["data"]["repository"]["pullRequest"]["closingIssuesReferences"]
        for name, reply in (
            ("malformed page", malformed),
            ("missing connection", missing),
            ("missing cursor", _closing(next_cursor="")),
        ):
            with self.subTest(name):
                unread = _evidence(_snapshot(_replies(**{CLOSING: reply})))
                self.assertNotEqual(
                    "COMPLETE", unread["closing_references"]["coverage"]
                )
                self.assertIn("M12", _failed(unread))

    def test_a_link_added_during_collection_is_not_missed(self) -> None:
        """The relation is part of each pass, so a link added between passes is
        in the certified snapshot, never a stale empty read."""
        replies = _replies()
        fake = paged_fake_fixture(replies)
        original = fake.get

        def get(url: str) -> tuple[Any, dict[str, str]]:
            reply: tuple[Any, dict[str, str]] = original(url)
            if url == CLOSING:
                # The link is added just after the first pass reads the relation.
                replies[CLOSING] = _closing(("ktogias/gnostoa", 407))
            return reply

        fake.get = get
        snapshot = adapter_fixture().collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
            merge_evidence=True,
        )
        self.assertEqual("STABLE_READBACK", snapshot["collection"]["status"])
        self.assertIn("M12", _failed(_evidence(snapshot)))

    def test_a_missing_title_is_not_complete_coverage(self) -> None:
        """CodeAnt on #413: L1 records a missing title as None, and its keywords
        were then never read while M12 reported COMPLETE."""
        replies = _replies()
        del replies[f"{API}/pulls/300"][0]["title"]
        evidence = _evidence(_snapshot(replies))
        self.assertEqual("PARTIAL", evidence["closing_references"]["coverage"])
        self.assertIn("M12", _failed(evidence))

    def test_words_that_are_not_closing_keywords_are_not_references(self) -> None:
        for text in (
            "Refs #407",
            "prefix #3",
            "unfixed #3",
            "fixture #12",
            "closes the gap",
        ):
            with self.subTest(text=text):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["title"] = text
                evidence = _evidence(_snapshot(replies))
                self.assertEqual([], evidence["closing_references"]["found"])

    def test_closing_reference_coverage_follows_its_sources(self) -> None:
        commits = [_commit(f"{index:040x}", "x") for index in range(250)]
        capped = _replies(**{COMPARE: _comparison(commits, FILES, total=251)})
        truncated_message = _replies(
            **{COMPARE: _comparison([_commit(HEAD, "y" * 70_000)], FILES)}
        )
        for name, replies in (
            ("fewer commits than the total", capped),
            ("truncated message", truncated_message),
        ):
            with self.subTest(name):
                evidence = _evidence(_snapshot(replies))
                self.assertEqual("PARTIAL", evidence["closing_references"]["coverage"])
                self.assertIn("M12", _failed(evidence))

    def test_threads_map_their_count_and_coverage(self) -> None:
        snapshot = _snapshot()
        snapshot["review_threads"][0]["state"] = "unresolved"
        self.assertEqual(1, _evidence(snapshot)["threads"]["unresolved"])
        snapshot["coverage"]["review_threads"]["status"] = "PARTIAL"
        self.assertEqual("PARTIAL", _evidence(snapshot)["threads"]["coverage"])

    def test_reviews_are_raw_and_their_partial_reads_fail_the_run(self) -> None:
        evidence = _evidence()
        self.assertEqual(
            {
                "reviewer": "ktogias",
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-09-19T16:40:02Z",
            },
            evidence["reviews"][0],
        )
        snapshot = _snapshot()
        snapshot["coverage"]["reviews"].update(
            {"status": "PARTIAL", "limit": "page_limit"}
        )
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)

    def test_l1_s_semantic_partial_reasons_keep_every_review(self) -> None:
        for reason in (
            "unsubmitted_provider_items",
            "unavailable_reviewer_identity",
            "ambiguous_latest_reviewer_opinion",
        ):
            with self.subTest(reason=reason):
                snapshot = _snapshot()
                snapshot["coverage"]["reviews"].update(
                    {"status": "PARTIAL", "reason": reason}
                )
                self.assertEqual(2, len(_evidence(snapshot)["reviews"]))

    def test_a_deleted_reviewer_keeps_a_per_review_identity(self) -> None:
        replies = _replies()
        replies[f"{API}/pulls/300/reviews?per_page=100"][0][0]["user"] = None
        reviewers = [r["reviewer"] for r in _evidence(_snapshot(replies))["reviews"]]
        self.assertEqual("github-unavailable-reviewer:10", reviewers[0])

    def test_lifecycle_reflects_draft_target_and_merge(self) -> None:
        for change, criterion in (
            ({"draft": True}, "M1"),
            ({"merged": True, "state": "closed"}, "M1"),
            ({"state": "closed"}, "M1"),
        ):
            with self.subTest(change=change):
                replies = _replies()
                replies[f"{API}/pulls/300"][0].update(change)
                self.assertIn(criterion, _failed(_evidence(_snapshot(replies))))
        replies = _replies()
        replies[f"{API}/pulls/300"][0].update({"merged": True, "state": "closed"})
        self.assertEqual("merged", _evidence(_snapshot(replies))["lifecycle"]["state"])
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["base"]["ref"] = "release"
        evidence = _evidence(_snapshot(replies))
        self.assertEqual("release", evidence["lifecycle"]["target"])
        self.assertIn("M1", _failed(evidence))

    def test_the_required_approvers_come_from_the_protected_codeowners_and_roster(
        self,
    ) -> None:
        self.assertEqual(
            ["ktogias"],
            _evidence(codeowners="* @ktogias\n")["authorities"]["required_approvers"],
        )
        self.assertEqual(
            [],
            _evidence(codeowners="/docs/ @ktogias\n")["authorities"][
                "required_approvers"
            ],
        )
        for text in (
            "* @org/maintainers\n",
            "* someone@example.com\n",
            "* @stranger\n",
        ):
            with (
                self.subTest(codeowners=text),
                self.assertRaises(merge_evidence_github.MergeEvidenceError),
            ):
                _evidence(codeowners=text)

    def test_a_candidate_s_own_codeowners_change_does_not_choose_its_approvers(
        self,
    ) -> None:
        """The candidate may edit `.github/CODEOWNERS`; the protected copy decides."""
        replies = _replies(
            **{
                COMPARE: _comparison(
                    [_commit(HEAD, "x")],
                    [{"filename": ".github/CODEOWNERS", "status": "modified"}],
                )
            }
        )
        evidence = _evidence(_snapshot(replies), codeowners="* @ktogias\n")
        self.assertEqual(["ktogias"], evidence["authorities"]["required_approvers"])

    def test_change_control_comes_from_the_template_fields(self) -> None:
        for body in (
            "## Outcome\n\nNo change-control section.\n",
            BODY.replace(
                "`normative`",
                "`mechanical | normal | normative | critical | emergency`",
            ),
            BODY.replace("`normative`", "`urgent`"),
        ):
            with self.subTest(body=body[:40]):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = body
                snapshot = _snapshot(replies)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            "- Work Item: #407, #15", "- Work Item:"
        ).replace(
            "- Decision: [0112](knowledge/decisions/0112-admit-merges.md)",
            "- Decision:",
        )
        evidence = _evidence(_snapshot(replies))
        self.assertEqual({"work_items": [], "decisions": []}, evidence["links"])
        self.assertIn("M14", _failed(evidence))

    def test_a_decision_must_name_an_existing_decision(self) -> None:
        """Codex, cubic and CodeAnt on #413: prose such as "wait until 2026" must
        not satisfy M14. Under the strict grammar (#407, 6088050686) prose fails the
        run, and an id counts only when the protected target has its record."""
        line = "- Decision: [0112](knowledge/decisions/0112-admit-merges.md)"
        for value in (
            "wait until 2026",
            "see https://github.com/ktogias/gnostoa/issues/0112",
            "Decision 0016 and 0112",
            # A Decision id is four digits.
            "112",
            "01120",
            "0112x",
            "0112 and 0113",
            "0112,, 0113",
            # A Decision id is ASCII digits.
            "\u0660\u0661\u0661\u0662",
        ):
            with self.subTest(value=value):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
                    line, f"- Decision: {value}"
                )
                snapshot = _snapshot(replies)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)
        for value, expected in (
            ("9999", []),
            ("0112", ["0112"]),
            ("0016, 0112", ["0016", "0112"]),
            ("0112, 0113", ["0112", "0113"]),
            ("[0112](knowledge/decisions/0112-admit-merges.md)", ["0112"]),
        ):
            with self.subTest(value=value):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
                    line, f"- Decision: {value}"
                )
                evidence = _evidence(_snapshot(replies))
                self.assertEqual(expected, evidence["links"]["decisions"])
                if not expected:
                    self.assertIn("M14", _failed(evidence))

    def test_the_protected_target_s_decisions_are_its_decision_records(self) -> None:
        decisions = merge_evidence_github.load_decisions(ROOT)
        self.assertIn("0112", decisions)
        self.assertIn("0016", decisions)
        self.assertNotIn("9999", decisions)

    def test_a_protected_target_without_decision_records_fails_the_run(self) -> None:
        """cubic on #413: every other declaration fails loudly when missing; an
        absent directory silently dropped every reference."""
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(merge_evidence_github.MergeEvidenceError),
        ):
            merge_evidence_github.load_decisions(Path(directory))

    def test_a_decision_record_outside_the_protected_target_does_not_count(
        self,
    ) -> None:
        """cubic on #413: a symlink could lend an external record."""
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            outside = base / "outside"
            outside.mkdir()
            (outside / "9999-fake.md").write_text("x", encoding="utf-8")
            project = base / "project"
            records = project / "knowledge" / "decisions"
            records.mkdir(parents=True)
            (records / "0001-real.md").write_text("x", encoding="utf-8")
            (records / "9998-linked.md").symlink_to(outside / "9999-fake.md")
            self.assertEqual(
                frozenset({"0001"}), merge_evidence_github.load_decisions(project)
            )
            linked = base / "linked"
            (linked / "knowledge").mkdir(parents=True)
            (linked / "knowledge" / "decisions").symlink_to(outside)
            with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                merge_evidence_github.load_decisions(linked)

    def test_an_example_in_a_code_block_is_not_change_control(self) -> None:
        """CodeAnt on #413: fields inside a fenced example supplied links."""
        example = (
            "## Notes\n\n```markdown\n## Change control\n\n- Class: `normal`\n"
            "- Work Item: #999\n- Decision: 0112\n```\n"
        )
        for body in (
            example,
            BODY.replace("- Work Item: #407, #15", "- Work Item:")
            + "\n~~~\n- Work Item: #999\n~~~\n<!--\n- Decision: 0016\n-->\n",
        ):
            with self.subTest(body=body[:30]):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = body
                if body is example:
                    snapshot = _snapshot(replies)
                    with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                        _evidence(snapshot)
                else:
                    links = _evidence(_snapshot(replies))["links"]
                    self.assertEqual([], links["work_items"])
                    self.assertEqual(["0112"], links["decisions"])

    def test_every_markdown_code_form_hides_its_fields(self) -> None:
        """Codex on #413: a fence may be indented by up to three spaces, may be
        longer than three, and an indented block is code too; none of their
        lines is a field."""
        stripped = BODY.replace("- Work Item: #407, #15", "- Work Item:")
        for name, extra in (
            # A paragraph ends the list first: after a list item, an indented fence
            # would sit inside the item, and the next line would break out as a
            # visible item, as GitHub renders it.
            ("indented fence", "\nText.\n\n  ```\n- Work Item: #999\n  ```\n"),
            ("long fence", "\n````text\n```\n- Work Item: #999\n````\n"),
            ("mixed markers", "\n~~~\n```\n- Work Item: #999\n~~~\n"),
            ("tilde fence", "\nText.\n\n   ~~~~\n- Work Item: #999\n   ~~~~\n"),
            ("indented code block", "\n    - Work Item: #999\n"),
            ("unclosed fence", "\n```\n- Work Item: #999\n"),
        ):
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = stripped + extra
                links = _evidence(_snapshot(replies))["links"]
                self.assertEqual([], links["work_items"])

    def test_an_unclosed_comment_hides_the_rest_of_the_description(self) -> None:
        """Codex on #413: GitHub renders an unclosed comment as hiding
        everything after it, so its fields are not visible evidence."""
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = (
            BODY.replace("- Work Item: #407, #15", "- Work Item:")
            + "\n<!--\n- Work Item: #999\n"
        )
        self.assertEqual([], _evidence(_snapshot(replies))["links"]["work_items"])
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = "<!--\n" + BODY
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)

    def test_html_and_code_spans_follow_commonmark(self) -> None:
        """Codex, cubic, CodeAnt and Claude on #413: a raw HTML block is code; a
        fence can straddle a comment; `<!--` in a code span opens nothing; an
        inline comment in a value is not part of it (Decision 0113)."""
        stripped = BODY.replace("- Work Item: #407, #15", "- Work Item:")
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = (
            stripped + "\n<pre>\n- Work Item: #999\n</pre>\n"
        )
        # A raw `<pre>` in the section can hold content, so the run fails (the
        # owner's choice, #407 6086999580).
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)
        # A fence that opens before a comment closes at its own marker, so what
        # follows renders as a visible item (Decision 0113): here a second Work
        # Item, which is ambiguous.
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = (
            stripped + "\n```\n<!--\n```\n- Work Item: #999\n-->\n"
        )
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = (
            "Write `<!--` to open a comment.\n\n" + BODY
        )
        self.assertEqual(
            ["#407", "#15"], _evidence(_snapshot(replies))["links"]["work_items"]
        )
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            "- Decision: [0112](knowledge/decisions/0112-admit-merges.md)",
            "- Decision: 0112 <!-- 0016 -->",
        )
        self.assertEqual(["0112"], _evidence(_snapshot(replies))["links"]["decisions"])

    def test_the_section_is_the_top_level_heading_and_its_own_items(self) -> None:
        """Only the top-level section's own top-level items are fields: not a
        later section's, not a nested item, not a heading inside a quote."""
        cases = {
            "a later section": BODY + "\n## Notes\n\n- Work Item: #999\n",
            "a nested item": BODY.replace(
                "- Accountable owner: @ktogias",
                "- Accountable owner: @ktogias\n  - Work Item: #999",
            ),
        }
        for name, body in cases.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = body
                self.assertEqual(
                    ["#407", "#15"],
                    _evidence(_snapshot(replies))["links"]["work_items"],
                )
        # A quoted section is not the description's own, so it neither counts
        # nor makes the real one ambiguous.
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = (
            BODY + "\n> ## Change control\n>\n> - Class: `normal`\n"
        )
        self.assertEqual("normative", _evidence(_snapshot(replies))["change_class"])

    def test_a_work_item_is_a_visible_issue_number(self) -> None:
        """The owner's #402 decisions (#407, 6086766086 and 6088050686): a Work Item
        value is only `#N` entries in ASCII digits, separated by commas or
        spaces. Anything else fails the run: an issue URL, another repository, a
        lookalike host, a suffix, non-ASCII digits, an invisible character or
        prose."""
        refused = (
            "https://github.com/ktogias/gnostoa/issues/407",
            "https://github.com/unrelated/project/issues/999999",
            "https://g\u0131thub.com/ktogias/gnostoa/issues/999",
            "#407 https://github.com/ktogias/gnostoa-x/issues/9",
            "other/project#999",
            "#\u0661",
            # Codex on #413: a zero-width space GitHub does not show.
            "#40\u200b7",
            "#407 (MA0)",
            "see #407",
            "#407,",
            # The separators are ASCII commas and spaces.
            "#407\u2003#15",
            # The owner-requested analysis's table (#407, 6088035894): each
            # fails by not being in the grammar, with no special case.
            "#40\u200d7",
            "#40\ufeff7",
            "#40\u00a07",
            "#40\u202e7",
            # Only ASCII spaces pad a value; the parser itself trims a line's
            # end, so these sit where it does not.
            "\u00a0#407",
            "`#407\u00a0`",
            "#407junk",
            "#407 extra",
            "#407, garbage",
            "#407,, #15",
        )
        for text in refused:
            with self.subTest(text=text):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace("#407, #15", text)
                snapshot = _snapshot(replies)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)
        for text, expected in (
            ("#407, #15", ["#407", "#15"]),
            ("#407 #15", ["#407", "#15"]),
            ("#407,#15", ["#407", "#15"]),
            ("#407, #407", ["#407"]),
            ("#407 , #15", ["#407", "#15"]),
            ("[#407](https://github.com/ktogias/gnostoa/issues/407)", ["#407"]),
        ):
            with self.subTest(text=text):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace("#407, #15", text)
                links = _evidence(_snapshot(replies))["links"]
                self.assertEqual(expected, links["work_items"])

    def test_a_value_is_its_visible_text(self) -> None:
        """Codex on #413, and the owner's re-slice decision (#407, 6085478125): a
        link's target is never read, so an empty link contributes nothing and a
        Decision counts only by the id it shows."""
        cases = {
            "an empty Work Item link": (
                ("#407, #15", "[](https://github.com/ktogias/gnostoa/issues/407)"),
                "work_items",
                [],
            ),
            "a descriptive Work Item link": (
                (
                    "#407, #15",
                    "[the issue](https://github.com/ktogias/gnostoa/issues/407)",
                ),
                "work_items",
                None,
            ),
            "a Work Item in inline code": (
                ("#407, #15", "`#407`"),
                "work_items",
                ["#407"],
            ),
            "a Work Item link showing its number": (
                ("#407, #15", "[#407](https://github.com/ktogias/gnostoa/issues/407)"),
                "work_items",
                ["#407"],
            ),
            "a Decision named only by its target": (
                ("[0112]", "[the verdict's record]"),
                "decisions",
                None,
            ),
            "a Decision showing its id": ((BODY, BODY), "decisions", ["0112"]),
        }
        for name, ((old, new), key, expected) in cases.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(old, new)
                if expected is None:
                    # Text that is not the grammar fails the run (#407, 6088050686).
                    snapshot = _snapshot(replies)
                    with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                        _evidence(snapshot)
                else:
                    links = _evidence(_snapshot(replies))["links"]
                    self.assertEqual(expected, links[key])

    def test_a_heading_is_compared_by_its_visible_text(self) -> None:
        """cubic on #413: inline HTML in the heading is not part of its text."""
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            "## Change control", "## Change control <!-- the template's fields -->"
        )
        links = _evidence(_snapshot(replies))["links"]
        self.assertEqual(["#407", "#15"], links["work_items"])

    def test_raw_html_that_can_hold_content_fails_the_run(self) -> None:
        """Codex on #413, and the owner's choice (#407, 6086999580): GitHub may
        render Markdown inside a raw HTML element, and HTML5 nesting is not
        modelled, so any raw tag that can hold content before the end of the
        section fails the run. Comments and void elements hold nothing."""
        heading = "## Change control"
        refused = {
            "the section in details": BODY.replace(
                heading, f"<details>\n<summary>More</summary>\n\n{heading}"
            )
            + "\n</details>\n",
            "the fields in details": BODY.replace("- Class:", "<details>\n\n- Class:")
            + "\n</details>\n",
            "the heading in details": BODY.replace(
                heading, f"<details>\n\n{heading}\n\n</details>"
            ),
            "a closed details before": BODY.replace(
                heading,
                f"<details>\n<summary>Notes</summary>\n\nNotes.\n\n</details>\n\n{heading}",
            ),
            # Codex on #413: HTML5 closes the <p> at <details>, so the stray </p>
            # leaves <details> open.
            "a misnested details": BODY.replace(
                heading, f"<p><details></p>\n\n{heading}"
            ),
            "a self-closing details": BODY.replace(heading, f"<details/>\n\n{heading}"),
            "an inline details": BODY.replace(heading, f"Note <details>\n\n{heading}"),
            "a hidden span": BODY.replace(
                "- Class: `normative`", "- <span hidden>Class: `normative`</span>"
            ),
            "a value in details": BODY.replace(
                "#407, #15", "#407, <details>metadata #999</details>"
            ),
            "inline markup in a value": BODY.replace("#407, #15", "<b>#407</b>, #15"),
            "a stray end tag": BODY.replace("#407, #15", "#407</span>, #15"),
            "a tag in the heading": BODY.replace(
                heading, "## <span>Change control</span>"
            ),
            "an item opening with details": BODY.replace(
                "- Work Item: #407, #15", "- <details>Work Item: #407, #15</details>"
            ),
        }
        for name, body in refused.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = body
                snapshot = _snapshot(replies)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)
        accepted = {
            "void elements before": BODY.replace(
                heading, f"Line<br>\n\n<img src=x>\n\n<param name=x>\n\n{heading}"
            ),
            "a comment in a value": BODY.replace(
                "#407, #15", "#407, #15 <!-- note -->"
            ),
            # A comment renders as nothing, so the text around it joins.
            "a comment inside a number": BODY.replace(
                "#407, #15", "#4<!-- x -->07, #15"
            ),
            "raw HTML after the section": BODY
            + "\n## Later\n\n<details>\n\nNotes.\n\n</details>\n",
        }
        for name, body in accepted.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = body
                links = _evidence(_snapshot(replies))["links"]
                self.assertEqual(["#407", "#15"], links["work_items"])

    def test_raw_html_in_a_field_fails_the_run(self) -> None:
        """cubic and Codex on #413, and the owner's choice (#407, 6087507517): how
        a void element renders differs, `<wbr>` joining and `<br>` breaking, so a
        field holding raw HTML other than a comment fails the run. A comment
        renders as nothing, and the text around it joins."""
        field = "- Work Item: #407, #15"
        refused = {
            "a break in a value": "- Work Item: #40<br>7",
            "a zero-width break in a value": "- Work Item: #40<wbr>7",
            "an image in a value": "- Work Item: #40<img src=x>7",
            "a stripped tag in a value": "- Work Item: #40<meta>7",
            "a tag in a label": "- Wo<wbr>rk Item: #407",
            "a tag in a Decision": "- Decision: 01<wbr>12",
            # #407, 6087484196: every candidate is checked before extraction, so
            # HTML that keeps a label from matching is refused too.
            "a label the tag breaks": f"{field}\n- Work<br>Item: #999",
            "an item that is not a field": f"{field}\n- Note: see below<br>",
        }
        for name, text in refused.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(field, text)
                snapshot = _snapshot(replies)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)
        # Inline code is code, not raw HTML, even when it shows a tag, so an
        # item showing one is read (a field value must still be its grammar).
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            "- Accountable owner: @ktogias", "- Accountable owner: @ktogias `<wbr>`"
        )
        links = _evidence(_snapshot(replies))["links"]
        self.assertEqual(["#407", "#15"], links["work_items"])

    def test_an_item_s_field_is_its_first_paragraph(self) -> None:
        """Codex on #413, and the owner's choice (#407, 6085825905 and
        6085819873): a continuation paragraph of an item is not a field."""
        field = "- Work Item: #407, #15\n"
        cases = {
            "a tight list": (field, ["#407", "#15"]),
            "a loose list": (f"\n{field}\n", ["#407", "#15"]),
            "a soft break in the first paragraph": (
                "- Work Item: #407,\n  #15\n",
                ["#407", "#15"],
            ),
            "a field and a continuation": (
                f"{field}\n  Work Item: #999\n",
                ["#407", "#15"],
            ),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(field, text)
                evidence = _evidence(_snapshot(replies))
                self.assertEqual(expected, evidence["links"]["work_items"])
                self.assertEqual(not expected, "M14" in _failed(evidence))
        # A `- Notes` item, whose continuation holds the Work Item, is not one
        # of the template's fields, so the run fails (#407, 6092909419).
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            field, "- Notes\n\n  Work Item: #407, #15\n"
        )
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)

    def test_the_section_holds_only_the_template_s_fields(self) -> None:
        """cubic on #413, and the owner's choice (#407, 6092909419): every
        top-level item begins with exactly one of the template's four labels,
        each once, so a near-match label cannot escape the duplicate check."""
        field = "- Work Item: #407, #15"
        refused = {
            "a near-match label": f"{field}\n- Work Item\u00a0: #999",
            "a lowercase label": f"{field}\n- work item: #999",
            "another item": f"{field}\n- Notes",
            "an unknown label": f"{field}\n- Context: the verdict's inputs",
            # Duplicates fail even when their values agree (#407, 6092907589).
            "a repeated Work Item": f"{field}\n{field}",
            # cubic and Codex on #413: an ordered list's items are top-level
            # items of the section too.
            "an ordered list's conflicting class": f"{field}\n\n1. Class: critical",
            "an ordered list's other item": f"{field}\n\n1. Notes",
            "an item opening with code": f"{field}\n-     Work Item: #999",
            "a repeated owner": f"{field}\n- Accountable owner: @someone",
        }
        for name, text in refused.items():
            with self.subTest(name):
                replies = _replies()
                replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(field, text)
                snapshot = _snapshot(replies)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(field, "- Work Item:")
        self.assertEqual([], _evidence(_snapshot(replies))["links"]["work_items"])
        # A nested ordered list is not a top-level item, so it is allowed.
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            "- Accountable owner: @ktogias",
            "- Accountable owner: @ktogias\n\n  1. approves natively",
        )
        links = _evidence(_snapshot(replies))["links"]
        self.assertEqual(["#407", "#15"], links["work_items"])
        # Prose in the section is not an item, so the fields are still read.
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY.replace(
            "- Accountable owner: @ktogias",
            "- Accountable owner: @ktogias\n\nThe owner approves natively.",
        )
        links = _evidence(_snapshot(replies))["links"]
        self.assertEqual(["#407", "#15"], links["work_items"])

    def test_two_change_control_sections_are_ambiguous(self) -> None:
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY + "\n" + BODY
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)

    def test_logins_compare_without_case(self) -> None:
        """CodeAnt on #413: GitHub logins are case-insensitive."""
        approvers = _evidence(codeowners="* @KTogias\n")["authorities"][
            "required_approvers"
        ]
        self.assertEqual(["ktogias"], approvers)
        self.assertNotIn("M16", _failed(_evidence(codeowners="* @KTogias\n")))
        roster = {**_authorities(), "human_approvers": ["KTogias"]}
        evidence = merge_evidence_github.evidence_from_snapshot(
            _snapshot(),
            authorities=roster,
            change_policy=_policy(),
            codeowners=merge_evidence_github.parse_codeowners("* @ktogias\n"),
            decisions=merge_evidence_github.load_decisions(ROOT),
        )
        self.assertEqual(["ktogias"], evidence["authorities"]["required_approvers"])

    def test_only_ascii_letters_fold_in_logins(self) -> None:
        """cubic on #413: `casefold` folds the Kelvin sign to `k`, so a roster
        entry or a login containing it would match another account."""
        kelvin = "\u212atogias"
        for name, change in (
            ("roster", {"human_approvers": [kelvin]}),
            ("roster with a space", {"human_approvers": ["kto gias"]}),
            ("an App on the human roster", {"human_approvers": [DECLARER]}),
            ("declarer", {"declarer": "gnostoa agent[bot]"}),
        ):
            with (
                self.subTest(name),
                self.assertRaises(merge_evidence_github.MergeEvidenceError),
            ):
                merge_evidence_github.parse_authorities(
                    {
                        "schema_version": "1.0",
                        "id": "example.merge-authorities",
                        "version": "0.1.0",
                        "declarer": DECLARER,
                        "human_approvers": ["ktogias"],
                        **change,
                    }
                )
        replies = _replies()
        for review in replies[f"{API}/pulls/300/reviews?per_page=100"][0]:
            if review["user"] == {"login": "ktogias"}:
                review["user"] = {"login": kelvin}
        evidence = _evidence(_snapshot(replies))
        self.assertNotIn("ktogias", [r["reviewer"] for r in evidence["reviews"]])
        self.assertIn("M16", _failed(evidence))

    def test_a_rename_without_its_previous_path_fails_the_run(self) -> None:
        """CodeAnt on #413: the old location's code owner would be skipped."""
        replies = _replies(
            **{
                COMPARE: _comparison(
                    [_commit(HEAD, "x")],
                    [{"filename": "tools/new.py", "status": "renamed"}],
                )
            }
        )
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)
        replies = _replies(
            **{
                COMPARE: _comparison(
                    [_commit(HEAD, "x")],
                    [
                        {
                            "filename": "tools/new.py",
                            "status": "renamed",
                            "previous_filename": "docs/old.py",
                        }
                    ],
                )
            }
        )
        approvers = _evidence(
            _snapshot(replies), codeowners="* @ktogias\n/docs/ @ktogias\n"
        )["authorities"]["required_approvers"]
        self.assertEqual(["ktogias"], approvers)
        # The old location's owners count too: one off the roster fails the run.
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot, codeowners="* @ktogias\n/docs/ @stranger\n")

    def test_a_failed_roster_names_the_first_path_in_order(self) -> None:
        """Claude on #413: a rename's two paths are visited in sorted order, so
        the message does not depend on set order."""
        for n in range(10):
            with self.subTest(n=n):
                new, old = f"z{n}/new.py", f"a{n}/old.py"
                replies = _replies(
                    **{
                        COMPARE: _comparison(
                            [_commit(HEAD, "x")],
                            [
                                {
                                    "filename": new,
                                    "status": "renamed",
                                    "previous_filename": old,
                                }
                            ],
                        )
                    }
                )
                snapshot = _snapshot(replies)
                with self.assertRaisesRegex(
                    merge_evidence_github.MergeEvidenceError, f"of {old} is"
                ):
                    _evidence(snapshot, codeowners="* @stranger\n")

    def test_a_truncated_description_cannot_vouch_for_its_change_control(self) -> None:
        """CodeAnt on #413: a cut body may have lost part of its section."""
        replies = _replies()
        replies[f"{API}/pulls/300"][0]["body"] = BODY + "x" * 70_000
        snapshot = _snapshot(replies)
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)

    def test_incomplete_conversation_or_files_fail_the_run(self) -> None:
        for source in ("conversation", "files", "subject"):
            with self.subTest(source=source):
                snapshot = _snapshot()
                snapshot["coverage"][source]["status"] = "PARTIAL"
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(snapshot)

    def test_a_snapshot_without_the_merge_evidence_fields_is_refused(self) -> None:
        adapter = adapter_fixture()
        plain = adapter.collect_snapshot(
            paged_fake_fixture(complete_replies_fixture(API)),
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
        )
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(plain)
        unmarked = _snapshot()
        del unmarked["conversation"][0]["edited"]
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(unmarked)


def _project(directory: Path, *, authorities: bool = True) -> Path:
    project = directory / "project"
    (project / "policy").mkdir(parents=True)
    (project / "core").mkdir()
    (project / ".github").mkdir()
    for name in ("policy/change-control.yaml", "core/change-control.yaml"):
        shutil.copyfile(ROOT / name, project / name)
    shutil.copytree(
        ROOT / "knowledge" / "decisions", project / "knowledge" / "decisions"
    )
    (project / ".github" / "CODEOWNERS").write_text("* @ktogias\n", encoding="utf-8")
    if authorities:
        (project / "policy" / "merge-authorities.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "1.0",
                    "id": "example.merge-authorities",
                    "version": "0.1.0",
                    "declarer": DECLARER,
                    "human_approvers": ["ktogias"],
                }
            ),
            encoding="utf-8",
        )
    return project


def _run(project: Path, text: str) -> tuple[int, str, str]:
    stdin = io.TextIOWrapper(io.BytesIO(text.encode("utf-8")), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    with patch("sys.stdin", stdin), redirect_stdout(out), redirect_stderr(err):
        code = merge_evidence_github.main(["--project-root", str(project)])
    return code, out.getvalue(), err.getvalue()


class CommandTests(unittest.TestCase):
    def test_the_command_writes_the_evidence_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code, out, err = _run(_project(Path(directory)), json.dumps(_snapshot()))
        self.assertEqual(0, code, err)
        self.assertEqual(HEAD, json.loads(out)["subject"]["head_commit"])

    def test_a_failed_run_exits_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = _project(Path(directory))
            for text in ("[]", "not json", json.dumps({"schema_version": "x"})):
                with self.subTest(text=text):
                    self.assertEqual(2, _run(project, text)[0])
        with tempfile.TemporaryDirectory() as directory:
            missing = _project(Path(directory), authorities=False)
            self.assertEqual(2, _run(missing, json.dumps(_snapshot()))[0])

    def test_the_knowledge_cli_routes_merge_evidence(self) -> None:
        from tools import cli

        self.assertIs(merge_evidence_github.main, cli.COMMANDS["merge-evidence"][1])


class AuthoritiesTests(unittest.TestCase):
    def test_the_declaration_has_a_closed_contract(self) -> None:
        valid = {
            "schema_version": "1.0",
            "id": "example.merge-authorities",
            "version": "0.1.0",
            "declarer": DECLARER,
            "human_approvers": ["ktogias"],
        }
        changes: tuple[dict[str, Any], ...] = (
            {"extra": 1},
            {"declarer": ""},
            {"human_approvers": []},
            {"human_approvers": ["ktogias", "ktogias"]},
            {"human_approvers": "ktogias"},
        )
        for change in changes:
            with (
                self.subTest(change=change),
                self.assertRaises(merge_evidence_github.MergeEvidenceError),
            ):
                merge_evidence_github.parse_authorities({**valid, **change})

    def test_gnostoa_s_authorities_and_codeowners(self) -> None:
        authorities = merge_evidence_github.load_authorities(
            ROOT / "policy" / "merge-authorities.yaml", project_root=ROOT
        )
        self.assertEqual(DECLARER, authorities["declarer"])
        self.assertEqual(["ktogias"], authorities["human_approvers"])
        owners = merge_evidence_github.load_codeowners(ROOT)
        for path in ("tools/merge_admission.py", ".github/workflows/verification.yml"):
            with self.subTest(path=path):
                self.assertEqual(["@ktogias"], owners.owners(path))


class GuardrailRegistrationTests(unittest.TestCase):
    def test_every_test_in_this_module_is_registered_in_its_guardrail(self) -> None:
        manifest = yaml.safe_load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        )
        (entry,) = [
            g for g in manifest["guardrails"] if g["id"] == "github-merge-evidence"
        ]
        prefix = "tests/test_merge_evidence_github.py::"
        registered = {t[len(prefix) :] for t in entry["tests"] if t.startswith(prefix)}
        defined = {
            f"{name}.{method}"
            for name, case in globals().items()
            if isinstance(case, type) and issubclass(case, unittest.TestCase)
            for method in unittest.defaultTestLoader.getTestCaseNames(case)
        }
        self.assertEqual(set(), defined - registered)
        # The command's route is part of the entry point (cubic on #413).
        self.assertIn("tools/cli.py", entry["implementation"])


if __name__ == "__main__":
    unittest.main()
