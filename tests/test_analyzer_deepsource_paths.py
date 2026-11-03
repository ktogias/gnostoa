"""Characterization of the DeepSource full read's paths (#309, cleanup C).

Each return path and each provider-failure cause of `read_full_run` is pinned
here, on `main`, before the reader is factored, so the factoring can be shown to
keep every observable outcome. A provider failure is observable only as an
`ERROR` / `PROVIDER_ERROR` readback, so its cause is recorded through the
module's own exception type.
"""

from __future__ import annotations

import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

from deepsource_fakes import (
    HEAD,
    OBSERVED,
    RUN_UID,
    GraphQLFake,
    check,
    check_page,
    issue,
    run_page,
)

from tools import analyzer_deepsource

PYTHON = "check-python"


@contextmanager
def _recorded_failures() -> Iterator[list[str]]:
    """Every `ProviderReadFailure` the reader raises, by message."""

    messages: list[str] = []
    original = analyzer_deepsource.ProviderReadFailure

    class Recording(original):  # type: ignore[misc, valid-type]
        def __init__(self, kind: str, message: str) -> None:
            messages.append(message)
            super().__init__(kind, message)

    with patch.object(analyzer_deepsource, "ProviderReadFailure", Recording):
        yield messages


def _read(responses: dict[tuple[str, str | None], Any]) -> dict[str, Any]:
    return analyzer_deepsource.read_full_run(
        GraphQLFake(responses),
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        run_uid=RUN_UID,
        observed_at=OBSERVED,
    )


def _outcome(document: dict[str, Any]) -> tuple[Any, ...]:
    coverage = document["coverage"]
    return (
        document["completeness"],
        coverage["status"],
        coverage.get("reason"),
        coverage["pages"],
        len(document["findings"]),
        document.get("observed_head"),
    )


class FullReadReturnPathTests(unittest.TestCase):
    def test_each_early_return_keeps_its_outcome(self) -> None:
        cases: dict[str, tuple[dict[tuple[str, str | None], Any], tuple[Any, ...]]] = {
            "a run the provider does not associate": (
                {("run", None): {"data": {"run": None}}},
                ("AMBIGUOUS", "INCOMPLETE", "RUN_ASSOCIATION_AMBIGUOUS", 1, 0, None),
            ),
            "another run uid": (
                {("run", None): run_page(uid="1" * 8)},
                ("AMBIGUOUS", "INCOMPLETE", "RUN_UID_MISMATCH", 1, 0, HEAD),
            ),
            "another repository": (
                {("run", None): run_page(name="other")},
                ("AMBIGUOUS", "INCOMPLETE", "REPOSITORY_MISMATCH", 1, 0, HEAD),
            ),
            "another head": (
                {("run", None): run_page(head="b" * 40)},
                ("AMBIGUOUS", "INCOMPLETE", "SUBJECT_MISMATCH", 1, 0, "b" * 40),
            ),
            "a run still running": (
                {("run", None): run_page(status="RUNNING")},
                (
                    "READBACK_UNAVAILABLE",
                    "PARTIAL",
                    "ANALYSIS_RUN_NOT_COMPLETE",
                    1,
                    0,
                    HEAD,
                ),
            ),
            "no analyzer checks": (
                {("run", None): run_page(checks=[], total=0)},
                ("READBACK_UNAVAILABLE", "PARTIAL", "NO_ANALYZER_CHECKS", 1, 0, HEAD),
            ),
            "a check still running": (
                {("run", None): run_page(checks=[check(status="PENDING")])},
                (
                    "READBACK_UNAVAILABLE",
                    "PARTIAL",
                    "ANALYZER_CHECK_NOT_COMPLETE",
                    1,
                    0,
                    HEAD,
                ),
            ),
            "fewer checks than their total": (
                {("run", None): run_page(total=2)},
                (
                    "READBACK_UNAVAILABLE",
                    "PARTIAL",
                    "CHECK_PAGINATION_INCOMPLETE",
                    1,
                    0,
                    HEAD,
                ),
            ),
            "a complete read": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): check_page([issue("i-1", 3), issue("i-2", 4)]),
                },
                ("FULL_RUN", "COMPLETE", None, 2, 2, HEAD),
            ),
        }
        for name, (responses, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(expected, _outcome(_read(responses)))

    def test_each_outcome_names_its_run(self) -> None:
        """Claude on #419: the analysis id and run state differ by path; only a
        run-uid mismatch reports the provider's own uid."""
        cases: dict[str, tuple[dict[tuple[str, str | None], Any], tuple[Any, ...]]] = {
            "no run": ({("run", None): {"data": {"run": None}}}, (RUN_UID, "UNKNOWN")),
            "another run uid": (
                {("run", None): run_page(uid="1" * 8)},
                ("1" * 8, "FAILURE"),
            ),
            "another repository": (
                {("run", None): run_page(name="other")},
                (RUN_UID, "FAILURE"),
            ),
            "another head": (
                {("run", None): run_page(head="b" * 40)},
                (RUN_UID, "FAILURE"),
            ),
            "a run still running": (
                {("run", None): run_page(status="RUNNING")},
                (RUN_UID, "RUNNING"),
            ),
            "a failure while reading checks": (
                {
                    ("run", None): run_page(has_next=True, cursor="c1", total=2),
                    ("run", "c1"): run_page(head="b" * 40, total=2),
                },
                (RUN_UID, "UNKNOWN"),
            ),
            "a failure while reading issues": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): check_page([issue("i-1", 3)], total=2),
                },
                (RUN_UID, "FAILURE"),
            ),
            "a complete read": (
                {("run", None): run_page(), (PYTHON, None): check_page([])},
                (RUN_UID, "FAILURE"),
            ),
        }
        for name, (responses, expected) in cases.items():
            with self.subTest(name):
                document = _read(responses)
                actual = (document.get("analysis_id"), document["run_state"])
                self.assertEqual(expected, actual)

    def test_a_check_still_running_reports_the_states(self) -> None:
        document = _read({("run", None): run_page(checks=[check(status="PENDING")])})
        self.assertEqual(
            {"check_states": {"check-python": "PENDING"}}, document["native"]
        )

    def test_a_complete_read_reports_its_counts(self) -> None:
        document = _read(
            {
                ("run", None): run_page(),
                (PYTHON, None): check_page([issue("i-1", 3), issue("i-2", 4)]),
            }
        )
        self.assertEqual(
            {"checks": 1, "raw_issue_count": 2, "provider_total": 2},
            document["native"],
        )
        self.assertEqual(2, document["coverage"]["total"])


class FullReadProviderFailureTests(unittest.TestCase):
    def test_each_cause_is_its_own_failure(self) -> None:
        many = check_page([issue("i-1", 3)], total=3, has_next=True, cursor="i1")
        cases: dict[
            str, tuple[dict[tuple[str, str | None], Any], str, tuple[Any, ...]]
        ] = {
            "the run changes during pagination": (
                {
                    ("run", None): run_page(has_next=True, cursor="c1", total=2),
                    ("run", "c1"): run_page(head="b" * 40, total=2),
                },
                "DeepSource run changed during pagination",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 0, None),
            ),
            "check pagination does not advance": (
                {
                    ("run", None): run_page(has_next=True, cursor="c1", total=2),
                    ("run", "c1"): run_page(has_next=True, cursor="c1", total=2),
                },
                "DeepSource check pagination did not advance",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 0, None),
            ),
            "the check total changes": (
                {
                    ("run", None): run_page(has_next=True, cursor="c1", total=2),
                    ("run", "c1"): run_page(total=3),
                },
                "DeepSource check total changed during pagination",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 0, None),
            ),
            "the check total disappears": (
                {
                    ("run", None): run_page(has_next=True, cursor="c1", total=2),
                    ("run", "c1"): run_page(total=None),
                },
                "DeepSource check total availability changed during pagination",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 0, None),
            ),
            "the check's metadata changes": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): check_page([issue("i-1", 3)], status="SUCCESS"),
                },
                "DeepSource check metadata changed during pagination",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 0, HEAD),
            ),
            "issue pagination does not advance": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): many,
                    (PYTHON, "i1"): many,
                },
                "DeepSource issue pagination did not advance",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 3, 1, HEAD),
            ),
            "the issue total changes": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): many,
                    (PYTHON, "i1"): check_page([issue("i-2", 4)], total=4),
                },
                "DeepSource issue total changed during pagination",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 3, 1, HEAD),
            ),
            "the issue total disappears": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): many,
                    (PYTHON, "i1"): {
                        "data": {
                            "node": {
                                **check(),
                                "issues": {
                                    "totalCount": None,
                                    "edges": [],
                                    "pageInfo": {
                                        "hasNextPage": False,
                                        "endCursor": None,
                                    },
                                },
                            }
                        }
                    },
                },
                "DeepSource issue total availability changed during pagination",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 3, 1, HEAD),
            ),
            "fewer issues than their total": (
                {
                    ("run", None): run_page(),
                    (PYTHON, None): check_page([issue("i-1", 3)], total=2),
                },
                "DeepSource issue pagination is incomplete",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 1, HEAD),
            ),
        }
        for name, (responses, cause, expected) in cases.items():
            with self.subTest(name), _recorded_failures() as messages:
                document = _read(responses)
                self.assertEqual(expected, _outcome(document))
                self.assertEqual([cause], messages)

    def test_pagination_past_its_bound_fails(self) -> None:
        run_pages = {
            ("run", None): run_page(has_next=True, cursor="c1", total=9),
            ("run", "c1"): run_page(has_next=True, cursor="c2", total=9),
        }
        issue_pages = {
            ("run", None): run_page(),
            (PYTHON, None): check_page(
                [issue("i-1", 3)], total=9, has_next=True, cursor="i1"
            ),
            (PYTHON, "i1"): check_page(
                [issue("i-2", 4)], total=9, has_next=True, cursor="i2"
            ),
        }
        for name, responses, cause, expected in (
            (
                "checks",
                run_pages,
                "DeepSource check pagination exceeded bound",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 2, 0, None),
            ),
            (
                "issues",
                issue_pages,
                "DeepSource issue pagination exceeded bound",
                ("READBACK_UNAVAILABLE", "ERROR", "PROVIDER_ERROR", 3, 2, HEAD),
            ),
        ):
            with (
                self.subTest(name),
                patch.object(analyzer_deepsource, "_MAX_PAGES", 2),
                _recorded_failures() as messages,
            ):
                document = _read(responses)
                self.assertEqual(expected, _outcome(document))
                self.assertEqual([cause], messages)


def _status(state: str = "failure", analyzer: str = "Python") -> dict[str, Any]:
    return {
        "context": f"DeepSource: {analyzer}",
        "source_kind": "commit_status",
        "creator_login": "deepsource-io[bot]",
        "creator_type": "Bot",
        "state": state,
        "target_url": (
            "https://app.deepsource.com/gh/ktogias/gnostoa/run/"
            f"{RUN_UID}/{analyzer.lower()}/"
        ),
    }


def _comment(marker: str | None = "Q2hlY2s6MQ==", **change: Any) -> dict[str, Any]:
    body = (
        (f"<!-- DeepSource: id={marker} -->\n" if marker else "")
        + "<h3><picture></picture>A finding</h3>\n"
        + "severity_major.svg category_typecheck.svg"
    )
    return {
        "body": body,
        "path": "tools/example.py",
        "line": 7,
        "commit_id": HEAD,
        "original_commit_id": HEAD,
        "url": "https://github.com/ktogias/gnostoa/pull/312#discussion_r1",
        "author_login": "deepsource-io[bot]",
        "author_type": "Bot",
        **change,
    }


def _diff(
    statuses: list[dict[str, Any]], comments: list[dict[str, Any]]
) -> dict[str, Any]:
    return analyzer_deepsource.diff_local_from_github(
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        observed_head=HEAD,
        statuses=statuses,
        comments=comments,
        observed_at=OBSERVED,
    )


class DiffLocalPathTests(unittest.TestCase):
    def test_only_trusted_marked_exact_head_comments_become_findings(self) -> None:
        comments = [
            _comment(),
            _comment(marker="Q2hlY2s6Mg==", author_login="someone", author_type="User"),
            _comment(marker=None),
            {**_comment(marker="Q2hlY2s6Mw=="), "body": 7},
            _comment(marker="Q2hlY2s6NA==", commit_id="b" * 40),
            _comment(marker="Q2hlY2s6NQ==", original_commit_id="b" * 40),
        ]
        document = _diff([_status()], comments)
        self.assertEqual(
            [
                {
                    "id": "Q2hlY2s6MQ==",
                    "message": "A finding",
                    "state": "open",
                    "native_ref": "Q2hlY2s6MQ==",
                    "path": "tools/example.py",
                    "range": {"start_line": 7, "end_line": 7},
                    "severity": "MAJOR",
                    "category": "TYPECHECK",
                }
            ],
            [
                {k: v for k, v in f.items() if k != "provenance"}
                for f in document["findings"]
            ],
        )
        actual = (
            document["completeness"],
            document["coverage"]["status"],
            document["coverage"]["reason"],
        )
        self.assertEqual(
            ("DIFF_LOCAL", "PARTIAL", "CARRIED_FORWARD_COMMENTS_EXCLUDED"),
            actual,
        )
        self.assertEqual(1, document["native"]["carried_forward_comments_excluded"])

    def test_a_finding_s_optional_fields_need_valid_values(self) -> None:
        document = _diff(
            [_status()],
            [
                {
                    **_comment(path="", line=0),
                    "body": "<!-- DeepSource: id=Q2hlY2s6Ng== -->",
                }
            ],
        )
        [finding] = document["findings"]
        self.assertEqual(
            {"id", "message", "state", "native_ref", "provenance"}, set(finding)
        )

    def test_the_analyzer_states_decide_the_run_state(self) -> None:
        for name, statuses, expected in (
            ("all succeeded", [_status("success")], ("SUCCESS", "COMPLETE", None)),
            (
                "one failed",
                [_status("success"), _status("failure", "Shell")],
                ("FAILURE", "COMPLETE", None),
            ),
            (
                "one pending",
                [_status("success"), _status("pending", "Shell")],
                ("PENDING", "PARTIAL", "ANALYZER_STATE_UNAVAILABLE"),
            ),
            (
                "one errored",
                [_status("error")],
                ("FAILURE", "PARTIAL", "ANALYZER_STATE_UNAVAILABLE"),
            ),
            (
                "an unknown state",
                [_status("cancelled")],
                ("UNKNOWN", "PARTIAL", "ANALYZER_STATE_UNAVAILABLE"),
            ),
            ("no status", [], ("UNKNOWN", "INCOMPLETE", "RUN_ASSOCIATION_AMBIGUOUS")),
        ):
            with self.subTest(name):
                document = _diff(statuses, [])
                actual = (
                    document["run_state"],
                    document["coverage"]["status"],
                    document["coverage"].get("reason"),
                )
                self.assertEqual(expected, actual)
                expected_id = RUN_UID if statuses else None
                self.assertEqual(expected_id, document.get("analysis_id"))


if __name__ == "__main__":
    unittest.main()
