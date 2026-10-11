"""Work Item existence and reference integrity in the merge evidence (#407, slice
1b.3b-3, admitted in 6108453639).

Each Work Item the Change control section lists must be an issue of the subject
repository, observed by L1 in the same stable cut; and a listed Work Item or
Decision carried by a link must be linked to its own issue or record. A read
that could not prove it, or a link to anything else, fails the run.
"""

from __future__ import annotations

import copy
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import unittest
from collections.abc import Mapping, Sequence
from typing import Any
from unittest.mock import patch

from test_merge_evidence_github import (
    API,
    BODY,
    ROOT,
    _evidence,
    _failed,
    _issue,
    _replies,
    unregistered_tests,
)
from test_review_reconcile_l1 import adapter_fixture, paged_fake_fixture

import tools
from tools import merge_evidence_github

ISSUE_407 = f"{API}/issues/407"
ISSUE_15 = f"{API}/issues/15"
RECORD = (
    "knowledge/decisions/"
    "0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md"
)
ISSUES = "https://github.com/ktogias/gnostoa/issues"
WORK_ITEM_LINE = "- Work Item: #407, #15\n"
DECISION_LINE = f"- Decision: [0112]({RECORD})\n"


def _body(*, work_item: str = WORK_ITEM_LINE, decision: str = DECISION_LINE) -> str:
    if WORK_ITEM_LINE not in BODY or DECISION_LINE not in BODY:
        raise AssertionError("BODY no longer holds the lines these tests replace")
    return BODY.replace(WORK_ITEM_LINE, work_item).replace(DECISION_LINE, decision)


def _with_body(
    replies: dict[str, tuple[Any, dict[str, str]]], body: str
) -> dict[str, tuple[Any, dict[str, str]]]:
    pull = copy.deepcopy(replies[f"{API}/pulls/300"])
    pull[0]["body"] = body
    replies[f"{API}/pulls/300"] = pull
    return replies


def _collect(
    replies: dict[str, tuple[Any, dict[str, str]]],
    refusals: Mapping[str, int | None] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """L1's merge-evidence snapshot from the fake provider, with some URLs refused
    with the given HTTP status, and every URL the collector read. The refusal is
    the loaded adapter's own error, as its client raises it."""

    adapter = adapter_fixture()
    fake = paged_fake_fixture(replies)
    original = fake.get

    def get(url: str) -> tuple[Any, dict[str, str]]:
        if refusals and url in refusals:
            fake.calls.append(url)
            raise adapter.ProviderReadError(
                "GitHub refused the read", status=refusals[url]
            )
        reply: tuple[Any, dict[str, str]] = original(url)
        return reply

    fake.get = get
    snapshot: dict[str, Any] = adapter.collect_snapshot(
        fake,
        repository="ktogias/gnostoa",
        pull_number=300,
        observed_at="2026-09-19T16:41:00Z",
        merge_evidence=True,
    )
    return snapshot, fake.calls


class WorkItemCollectionTests(unittest.TestCase):
    """L1 reads each listed Work Item once per pass, bounded, inside the cut."""

    def test_each_listed_work_item_is_read_once_per_pass(self) -> None:
        replies = _with_body(
            _replies(), _body(work_item="- Work Item: #407, #15, #407\n")
        )
        snapshot, calls = _collect(replies)
        self.assertEqual(
            [
                {"number": 407, "repository": "ktogias/gnostoa", "kind": "issue"},
                {"number": 15, "repository": "ktogias/gnostoa", "kind": "issue"},
            ],
            snapshot["work_items"],
        )
        self.assertEqual(
            {"status": "COMPLETE", "pages": 2, "count": 2},
            snapshot["coverage"]["work_items"],
        )
        passes = snapshot["collection"]["passes"]
        self.assertEqual("STABLE_READBACK", snapshot["collection"]["status"])
        self.assertEqual(passes, calls.count(ISSUE_407))
        self.assertEqual(passes, calls.count(ISSUE_15))

    def test_an_absent_work_item_and_a_pull_request_are_observed_as_such(
        self,
    ) -> None:
        replies = _replies()
        replies[ISSUE_15] = _issue(15, pull=True)
        snapshot, _ = _collect(replies, {ISSUE_407: 404})
        self.assertEqual(
            [
                {"number": 407, "repository": "ktogias/gnostoa", "kind": "absent"},
                {"number": 15, "repository": "ktogias/gnostoa", "kind": "pull_request"},
            ],
            snapshot["work_items"],
        )
        self.assertEqual("COMPLETE", snapshot["coverage"]["work_items"]["status"])

    def test_an_unreadable_work_item_leaves_the_source_incomplete(self) -> None:
        for name, refusals, status in (
            ("a rate limit", {ISSUE_407: 429}, "RATE_LIMITED"),
            ("a refusal on the first read", {ISSUE_407: 403}, "ERROR"),
            ("a refusal on a later read", {ISSUE_15: 500}, "PARTIAL"),
        ):
            with self.subTest(name):
                snapshot, _ = _collect(_replies(), refusals)
                self.assertEqual(status, snapshot["coverage"]["work_items"]["status"])

    def test_an_answer_for_another_resource_is_observed_as_it_is(self) -> None:
        replies = _replies()
        replies[ISSUE_407] = _issue(408)
        replies[ISSUE_15] = _issue(15, repository="other/project")
        snapshot, _ = _collect(replies)
        self.assertEqual(
            [
                {"number": 408, "repository": "ktogias/gnostoa", "kind": "issue"},
                {"number": 15, "repository": "other/project", "kind": "issue"},
            ],
            snapshot["work_items"],
        )

    def test_a_malformed_answer_leaves_the_source_incomplete(self) -> None:
        for name, payload in (
            ("not an object", []),
            ("no number", {"repository_url": f"{API}"}),
            ("a number that is not one", {"number": "407", "repository_url": API}),
            ("no repository", {"number": 407}),
            (
                "another origin",
                {"number": 407, "repository_url": "https://x/repos/a/b"},
            ),
        ):
            with self.subTest(name):
                replies = _replies()
                replies[ISSUE_407] = (payload, {})
                snapshot, _ = _collect(replies)
                self.assertEqual("ERROR", snapshot["coverage"]["work_items"]["status"])

    def test_the_reads_are_bounded(self) -> None:
        numbers = list(range(1001, 1022))
        listed = ", ".join(f"#{n}" for n in numbers)
        replies = _with_body(_replies(), _body(work_item=f"- Work Item: {listed}\n"))
        for number in numbers:
            replies[f"{API}/issues/{number}"] = _issue(number)
        snapshot, calls = _collect(replies)
        coverage = snapshot["coverage"]["work_items"]
        self.assertEqual("PARTIAL", coverage["status"])
        self.assertEqual("work_item_limit", coverage["limit"])
        self.assertEqual(20, len(snapshot["work_items"]))
        passes = snapshot["collection"]["passes"]
        self.assertEqual(
            20 * passes, sum(1 for c in calls if c.startswith(f"{API}/issues/10"))
        )

    def test_a_work_item_that_changes_during_collection_is_not_certified(
        self,
    ) -> None:
        replies = _replies()
        adapter = adapter_fixture()
        fake = paged_fake_fixture(replies)
        original = fake.get
        reads = {"issue": 0}

        def get(url: str) -> tuple[Any, dict[str, str]]:
            if url == ISSUE_407:
                reads["issue"] += 1
                return _issue(407, pull=reads["issue"] % 2 == 0)
            reply: tuple[Any, dict[str, str]] = original(url)
            return reply

        fake.get = get
        snapshot = adapter.collect_snapshot(
            fake,
            repository="ktogias/gnostoa",
            pull_number=300,
            observed_at="2026-09-19T16:41:00Z",
            merge_evidence=True,
        )
        self.assertEqual("UNSTABLE_READBACK", snapshot["collection"]["status"])
        self.assertEqual("PARTIAL", snapshot["coverage"]["work_items"]["status"])

    def test_a_truncated_description_reads_no_work_item(self) -> None:
        """The adapter fails a cut description's run anyway (Claude on #422)."""

        body = _body() + "x" * 70_000
        snapshot, calls = _collect(_with_body(_replies(), body))
        self.assertTrue(snapshot["subject"]["body_truncated"])
        self.assertEqual([], snapshot["work_items"])
        self.assertEqual("ERROR", snapshot["coverage"]["work_items"]["status"])
        self.assertNotIn(ISSUE_407, calls)

    def test_an_overlong_number_leaves_the_source_incomplete(self) -> None:
        """cubic and CodeAnt on #422: a number too long to convert is not read,
        and conversion never fails outside the collector's error path."""

        body = _body(work_item="- Work Item: #" + "9" * 5000 + "\n")
        snapshot, calls = _collect(_with_body(_replies(), body))
        self.assertEqual("ERROR", snapshot["coverage"]["work_items"]["status"])
        self.assertFalse(any("/issues/9" in call for call in calls))

    def test_an_unreadable_description_reads_no_work_item(self) -> None:
        replies = _with_body(_replies(), "## Change control\n\n- Work Item: see #407\n")
        snapshot, calls = _collect(replies)
        self.assertEqual([], snapshot["work_items"])
        self.assertEqual("ERROR", snapshot["coverage"]["work_items"]["status"])
        self.assertNotIn(ISSUE_407, calls)


class WorkItemEvidenceTests(unittest.TestCase):
    """The adapter links a Work Item only when L1 proved it an issue of the
    subject, and fails the run naming any it could not prove."""

    def _refused_run(
        self,
        replies: dict[str, tuple[Any, dict[str, str]]],
        refusals: Mapping[str, int | None] | None = None,
        reason: str = "",
    ) -> None:
        snapshot, _ = _collect(replies, refusals)
        with self.assertRaisesRegex(merge_evidence_github.MergeEvidenceError, reason):
            _evidence(snapshot)

    def test_proven_work_items_are_linked(self) -> None:
        snapshot, _ = _collect(_replies())
        evidence = _evidence(snapshot)
        self.assertEqual(
            {"work_items": ["#407", "#15"], "decisions": ["0112"]}, evidence["links"]
        )
        # The other slices' items still deny: these two obligations are not an ALLOW.
        self.assertNotIn("M14", _failed(evidence))
        self.assertTrue(_failed(evidence))

    def test_a_listed_work_item_must_be_an_issue_of_the_subject(self) -> None:
        """The run names the Work Item and why it is not proven."""

        for name, number, reply, reason in (
            ("absent", 407, None, "Work Item #407 does not exist in ktogias/gnostoa"),
            ("a pull request", 407, _issue(407, pull=True), "#407 is a pull request"),
            (
                "another repository",
                407,
                _issue(407, repository="other/project"),
                "#407 is not an issue of ktogias/gnostoa",
            ),
            ("another number", 407, _issue(408), "are not the ones the description"),
            ("one of several", 15, _issue(15, pull=True), "#15 is a pull request"),
        ):
            with self.subTest(name):
                replies = _replies()
                url = f"{API}/issues/{number}"
                if reply is None:
                    self._refused_run(replies, {url: 404}, reason)
                else:
                    replies[url] = reply
                    self._refused_run(replies, reason=reason)

    def test_an_incomplete_work_item_read_fails_the_run(self) -> None:
        for name, refusals in (
            ("a rate limit", {ISSUE_407: 429}),
            ("a server error", {ISSUE_15: 502}),
        ):
            with self.subTest(name):
                self._refused_run(_replies(), refusals)

    def test_an_incomplete_source_fails_even_when_its_items_match(self) -> None:
        """An unstable cut keeps every item and marks the source PARTIAL."""

        snapshot, _ = _collect(_replies())
        snapshot["coverage"]["work_items"]["status"] = "PARTIAL"
        with self.assertRaisesRegex(
            merge_evidence_github.MergeEvidenceError, "work_items source is PARTIAL"
        ):
            _evidence(snapshot)

    def test_observations_must_be_the_listed_work_items(self) -> None:
        snapshot, _ = _collect(_replies())
        for name, observations in (
            ("one missing", snapshot["work_items"][:1]),
            (
                "one more",
                [
                    *snapshot["work_items"],
                    {"number": 9, "repository": "ktogias/gnostoa", "kind": "issue"},
                ],
            ),
        ):
            with self.subTest(name):
                changed = copy.deepcopy(snapshot)
                changed["work_items"] = observations
                changed["coverage"]["work_items"]["count"] = len(observations)
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(changed)

    def test_an_observation_has_a_closed_typed_shape(self) -> None:
        """Codex on #422: `validate_snapshot` does not normalize this source, so
        `407.0` or `True` must not compare equal to a listed number."""

        snapshot, _ = _collect(_replies())
        proven = {"number": 407, "repository": "ktogias/gnostoa", "kind": "issue"}
        for name, first in (
            ("a float number", {**proven, "number": 407.0}),
            ("a text number", {**proven, "number": "407"}),
            ("a negative number", {**proven, "number": -407}),
            ("an unknown kind", {**proven, "kind": "Issue"}),
            ("a repository that is not text", {**proven, "repository": 7}),
            ("an extra field", {**proven, "state": "open"}),
            ("a missing field", {"number": 407, "kind": "issue"}),
            ("not an object", [407, "issue"]),
        ):
            with self.subTest(name):
                changed = copy.deepcopy(snapshot)
                changed["work_items"][0] = first
                with self.assertRaises(merge_evidence_github.MergeEvidenceError):
                    _evidence(changed)


class ReferenceIntegrityTests(unittest.TestCase):
    """A listed Work Item or Decision carried by a link is linked to its own issue
    or record; any other target fails the run, and a label with no identifier
    lists nothing (#407 6085544477, 6085507735)."""

    @staticmethod
    def _links(body: str) -> dict[str, Any]:
        snapshot, _ = _collect(_with_body(_replies(), body))
        links: dict[str, Any] = _evidence(snapshot)["links"]
        return links

    def _assert_refused(self, body: str) -> None:
        snapshot, _ = _collect(_with_body(_replies(), body))
        with self.assertRaises(merge_evidence_github.MergeEvidenceError):
            _evidence(snapshot)

    def test_a_work_item_link_must_point_to_its_issue(self) -> None:
        for name, line in (
            (
                "another repository",
                "[#407](https://github.com/other/project/issues/999)",
            ),
            ("another number", f"[#407]({ISSUES}/408)"),
            ("a pull request", "[#407](https://github.com/ktogias/gnostoa/pull/407)"),
            ("a relative target", "[#407](../issues/407)"),
            ("a root-relative target", "[#407](/issues/407)"),
            ("a fragment", f"[#407]({ISSUES}/407#top)"),
            ("a query", f"[#407]({ISSUES}/407?x=1)"),
            ("another host", "[#407](https://example.com/ktogias/gnostoa/issues/407)"),
            ("plain HTTP", "[#407](http://github.com/ktogias/gnostoa/issues/407)"),
            ("several identifiers", f"[#407, #15]({ISSUES}/407)"),
            # Codex on #422: the text after the link continues its number.
            ("a link covering part of a number", f"[#4]({ISSUES}/4)07"),
            ("a link covering more of it", f"[#40]({ISSUES}/40)7"),
            # cubic and Codex on #422: a zero-width link does not separate them.
            ("an empty link between", f"[#4]({ISSUES}/4)[](https://example.com)07"),
            ("a comment between", f"[#4]({ISSUES}/4)<!-- c -->07"),
            ("inline code after", f"[#4]({ISSUES}/4)`07`"),
            # CodeAnt on #422: a label holding only part of the identifier.
            ("a link on the hash alone", f"[#]({ISSUES}/999)407"),
            ("a link to the issue's number spelt otherwise", f"[#407]({ISSUES}/408)"),
        ):
            with self.subTest(name):
                self._assert_refused(_body(work_item=f"- Work Item: {line}, #15\n"))

    def test_a_matching_work_item_link_counts(self) -> None:
        for line in (
            f"[#407]({ISSUES}/407), #15",
            f"[`#407`]({ISSUES}/407), [#15]({ISSUES}/15)",
            "`#407`, #15",
        ):
            with self.subTest(line):
                links = self._links(_body(work_item=f"- Work Item: {line}\n"))
                self.assertEqual(["#407", "#15"], links["work_items"])

    def test_a_decision_link_must_point_to_its_record(self) -> None:
        for name, line in (
            (
                "another protected record",
                "[0112](knowledge/decisions/"
                "0091-add-authenticated-provider-neutral-analyzer-readback.md)",
            ),
            ("a record that does not exist", "[0112](knowledge/decisions/0112-x.md)"),
            (
                "an absolute target",
                "[0112](https://github.com/ktogias/gnostoa/blob/main/" + RECORD + ")",
            ),
            ("another directory", "[0112](knowledge/" + RECORD.split("/")[-1] + ")"),
            ("several identifiers", f"[0112, 0091]({RECORD})"),
        ):
            with self.subTest(name):
                self._assert_refused(_body(decision=f"- Decision: {line}\n"))

    def test_a_matching_decision_link_counts(self) -> None:
        for line in (f"[0112]({RECORD})", f"[`0112`]({RECORD})", "0112", "`0112`"):
            with self.subTest(line):
                links = self._links(_body(decision=f"- Decision: {line}\n"))
                self.assertEqual(["0112"], links["decisions"])

    def test_a_work_item_is_its_number(self) -> None:
        """cubic and CodeAnt on #422, as the PAO advisory (6110693561) settled
        it: the protected base's `#N` spellings stay valid, and a Work Item's
        identity is its number, so `#0407` is issue 407, read once with `#407`,
        and linked to issue 407."""

        for line, expected in (
            ("#0407, #15", ["#407", "#15"]),
            ("#407, #0407, #15", ["#407", "#15"]),
            (f"[#0407]({ISSUES}/407), #15", ["#407", "#15"]),
            (f"[#407]({ISSUES}/0407), #15", ["#407", "#15"]),
        ):
            with self.subTest(line):
                body = _body(work_item=f"- Work Item: {line}\n")
                snapshot, calls = _collect(_with_body(_replies(), body))
                self.assertEqual(expected, _evidence(snapshot)["links"]["work_items"])
                passes = snapshot["collection"]["passes"]
                self.assertEqual(passes, calls.count(ISSUE_407))

    def test_a_work_item_number_has_no_digit_ceiling(self) -> None:
        """cubic on #422: round 7 removed round 1's ten-digit cap, so an
        eleven-digit Work Item is read and observed like any other."""

        replies = _with_body(
            _replies(), _body(work_item="- Work Item: #12345678901, #15\n")
        )
        replies[f"{API}/issues/12345678901"] = _issue(12345678901)
        snapshot, calls = _collect(replies)
        self.assertEqual(
            ["#12345678901", "#15"], _evidence(snapshot)["links"]["work_items"]
        )
        self.assertIn(f"{API}/issues/12345678901", calls)

    def test_padding_and_empty_links_list_nothing_more(self) -> None:
        """The PAO advisory on #422: an empty label lists nothing wherever it sits
        (#407 6085478125), and a padded label's identifier is its trimmed text."""

        for line, expected in (
            (f"#407[]({ISSUES}/407), #15", ["#407", "#15"]),
            (f"[]({ISSUES}/999)#407, #15", ["#407", "#15"]),
            (f"[#407 ]({ISSUES}/407), #15", ["#407", "#15"]),
            (f"[#407 ]({ISSUES}/407)#15", ["#407", "#15"]),
            (f"[ #407]({ISSUES}/407), #15", ["#407", "#15"]),
            (f"#15[ #407]({ISSUES}/407)", ["#15", "#407"]),
        ):
            with self.subTest(line):
                links = self._links(_body(work_item=f"- Work Item: {line}\n"))
                self.assertEqual(expected, links["work_items"])

    def test_an_image_in_an_item_fails_the_run(self) -> None:
        """Codex on #422: an image's alt text is a label the visible value does
        not show, so it could hide an identifier from the link check."""

        for line in (
            f"#407 [![#15](i.png)]({ISSUES}/999), #15",
            "#407, #15 ![#9](i.png)",
        ):
            with self.subTest(line):
                self._assert_refused(_body(work_item=f"- Work Item: {line}\n"))

    def test_a_label_without_an_identifier_lists_nothing(self) -> None:
        """#413's rule, kept: a link's target is never a source of identifiers."""

        links = self._links(
            _body(
                work_item="- Work Item: #407 [](https://github.com/x/y/issues/9), #15\n"
            )
        )
        self.assertEqual(["#407", "#15"], links["work_items"])
        self._assert_refused(_body(work_item=f"- Work Item: [see]({ISSUES}/407)\n"))


class _NoMarkdownParser(importlib.abc.MetaPathFinder):
    """The workflow's publish job, which has no runtime lock: `markdown_it`
    cannot be imported."""

    @staticmethod
    def find_spec(
        fullname: str,
        path: Sequence[str] | None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname == "markdown_it" or fullname.startswith("markdown_it."):
            raise ModuleNotFoundError(f"No module named {fullname!r}")
        return None


class StartupTests(unittest.TestCase):
    def test_loading_l1_does_not_load_the_merge_evidence_adapter(self) -> None:
        """Codex on #422: the workflow's publish job runs L1's script with no
        runtime lock installed, so loading it must not import the adapter or its
        Markdown parser; only merge-evidence collection does."""

        loaded = ("markdown_it", "tools.merge_evidence_github")
        with (
            patch.dict(sys.modules),
            # `from tools import merge_evidence_github` would otherwise find the
            # package attribute this module's own import left.
            patch.dict(tools.__dict__),
            patch.object(sys, "meta_path", [_NoMarkdownParser(), *sys.meta_path]),
        ):
            for name in list(sys.modules):
                if name.startswith(loaded):
                    del sys.modules[name]
            tools.__dict__.pop("merge_evidence_github", None)
            spec = importlib.util.spec_from_file_location(
                "gnostoa_l1_publish_mode",
                ROOT / "ci" / "review_github_current_state.py",
            )
            if spec is None or spec.loader is None:
                raise AssertionError("L1's script cannot be loaded")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual([], [n for n in sys.modules if n.startswith(loaded)])


class GuardrailRegistrationTests(unittest.TestCase):
    def test_every_test_in_this_module_is_registered_in_its_guardrail(self) -> None:
        """Claude on #422: the sibling module's check covers only itself."""

        self.assertEqual(
            set(),
            unregistered_tests(globals(), "tests/test_merge_evidence_work_items.py"),
        )


if __name__ == "__main__":
    unittest.main()
