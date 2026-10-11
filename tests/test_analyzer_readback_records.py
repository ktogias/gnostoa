"""Recorded analyzer readbacks and bundles read back through their contract
(#407, slice 1b.3b-2).

A recorded readback or bundle is accepted only when the readback module's own
contract rebuilds it, so there is no second schema. Kept apart from
`test_analyzer_readback`, whose module these tests do not need.
"""

from __future__ import annotations

import json
import unittest
from typing import Any

from tools import analyzer_readback

HEAD = "a" * 40
OTHER_HEAD = "b" * 40
RUN_UID = "0c29b163-9e8e-43be-bd8b-a93254aa2748"
OBSERVED = "2026-09-23T13:30:00Z"


def _recorded(
    provider: str = "deepsource",
    scope: str = "FULL",
    *,
    findings: tuple[dict[str, Any], ...] = (),
    status: str = "COMPLETE",
    head: str = HEAD,
) -> dict[str, Any]:
    """A readback as the contract builds it, for the readers below."""

    complete = status == "COMPLETE"
    record: dict[str, Any] = {"status": status, "pages": 1, "count": len(findings)}
    if not complete:
        record["reason"] = "READBACK_UNAVAILABLE"
    return analyzer_readback.build_readback(
        provider=provider,
        adapter=f"{provider}-fake/v1",
        repository="ktogias/gnostoa",
        pull_number=300,
        requested_head=head,
        observed_head=head if complete else None,
        analysis_id=RUN_UID,
        scope=scope,
        completeness="FULL_RUN" if complete else "READBACK_UNAVAILABLE",
        native_mode="FULL_RUN",
        observed_at=OBSERVED,
        run_state="SUCCESS" if complete else "UNKNOWN",
        coverage_record=record,
        findings=findings,
    )


def _bound(*readbacks: dict[str, Any], head: str = HEAD) -> dict[str, Any]:
    return {
        "schema": analyzer_readback.BUNDLE_SCHEMA,
        "repository": "ktogias/gnostoa",
        "pull_number": 300,
        "requested_head": head,
        "observed_head": head,
        "observed_at": OBSERVED,
        "subject_binding": "BOUND",
        "github_projection": {"statuses": 2, "check_runs": 3, "review_comments": 0},
        "readbacks": list(readbacks),
    }


FINDING = {
    "id": "issue-1",
    "message": "Reimport 'x'",
    "rule": "PYL-W0404",
    "severity": "MAJOR",
    "path": "tests/test_x.py",
    "state": "suppressed",
}


class RecordedReadbackTests(unittest.TestCase):
    """1b.3b-2 (#407, 6101607240): a recorded readback or bundle is read back
    through the contract that builds it, with no second schema."""

    def test_a_built_readback_reads_back_unchanged(self) -> None:
        for name, readback in (
            ("complete with findings", _recorded(findings=(FINDING,))),
            ("unavailable", _recorded("codacy", "DIFF", status="UNAVAILABLE")),
        ):
            with self.subTest(name):
                recorded = json.loads(analyzer_readback.canonical_json(readback))
                self.assertEqual(readback, analyzer_readback.parse_readback(recorded))

    def test_a_recorded_readback_must_be_what_the_contract_builds(self) -> None:
        def changed(**change: Any) -> dict[str, Any]:
            return {**_recorded(findings=(FINDING,)), **change}

        complete = _recorded(findings=(FINDING,))
        for name, readback in (
            ("an unknown field", changed(extra=1)),
            ("another schema", changed(schema="gnostoa-analyzer-readback/v0")),
            (
                "a count the findings disagree with",
                changed(coverage={**complete["coverage"], "count": 2}),
            ),
            (
                "a finding the contract would not keep",
                changed(findings=[{**FINDING, "rule": ""}]),
            ),
            (
                "complete without its head",
                {k: v for k, v in complete.items() if k != "observed_head"},
            ),
            ("an ambiguous complete read", changed(completeness="AMBIGUOUS")),
            ("findings that are not a list", changed(findings={})),
            ("a finding that is not an object", changed(findings=["finding"])),
            ("a scope that is not text", changed(scope=["FULL"])),
            (
                "a coverage field the contract drops",
                changed(coverage={**complete["coverage"], "x": 1}),
            ),
            (
                "findings out of the contract's order",
                {
                    **_recorded(findings=(FINDING, {**FINDING, "id": "issue-0"})),
                    "findings": list(
                        reversed(
                            _recorded(findings=(FINDING, {**FINDING, "id": "issue-0"}))[
                                "findings"
                            ]
                        )
                    ),
                },
            ),
            ("not an object", []),
        ):
            with (
                self.subTest(name),
                self.assertRaises(analyzer_readback.AnalyzerReadbackError),
            ):
                analyzer_readback.parse_readback(readback)

    def test_a_bundle_reads_back_unchanged(self) -> None:
        incomplete = {
            "schema": analyzer_readback.BUNDLE_SCHEMA,
            "repository": "ktogias/gnostoa",
            "pull_number": 300,
            "requested_head": HEAD,
            "observed_head": OTHER_HEAD,
            "observed_at": OBSERVED,
            "subject_binding": "INCOMPLETE",
            "reason": "GITHUB_SUBJECT_MISMATCH",
            "readbacks": [],
        }
        for name, bundle in (
            (
                "bound",
                _bound(_recorded(findings=(FINDING,)), _recorded("codacy", "DIFF")),
            ),
            ("incomplete", incomplete),
        ):
            with self.subTest(name):
                recorded = json.loads(analyzer_readback.canonical_json(bundle))
                self.assertEqual(bundle, analyzer_readback.parse_bundle(recorded))

    def test_a_bundle_has_a_closed_contract(self) -> None:
        bound = _bound(_recorded())

        def changed(**change: Any) -> dict[str, Any]:
            return {**json.loads(json.dumps(bound)), **change}

        without = {k: v for k, v in bound.items() if k != "github_projection"}
        for name, bundle in (
            ("an unknown field", changed(extra=1)),
            ("another schema", changed(schema="gnostoa-analyzer-readback-bundle/v0")),
            ("an unknown binding", changed(subject_binding="BOUNDISH")),
            ("a binding that is not text", changed(subject_binding=["BOUND"])),
            ("bound without its projection", without),
            ("bound with a reason", changed(reason="x")),
            ("bound to another observed head", changed(observed_head=OTHER_HEAD)),
            (
                "incomplete without a reason",
                {
                    **{k: v for k, v in bound.items() if k != "github_projection"},
                    "subject_binding": "INCOMPLETE",
                    "readbacks": [],
                },
            ),
            (
                "a readback for another head",
                changed(readbacks=[_recorded(head=OTHER_HEAD)]),
            ),
            (
                "a readback that is not the contract's",
                changed(readbacks=[{**_recorded(), "extra": 1}]),
            ),
            (
                "an unknown projection field",
                changed(
                    github_projection={
                        "statuses": 0,
                        "check_runs": 0,
                        "review_comments": 0,
                        "x": 0,
                    }
                ),
            ),
            (
                "a projection count that is not one",
                changed(
                    github_projection={
                        "statuses": -1,
                        "check_runs": 0,
                        "review_comments": 0,
                    }
                ),
            ),
            (
                "an incomplete bundle with readbacks",
                {
                    **{k: v for k, v in bound.items() if k != "github_projection"},
                    "subject_binding": "INCOMPLETE",
                    "reason": "x",
                },
            ),
            (
                "an incomplete bundle with an empty reason",
                {
                    **{k: v for k, v in bound.items() if k != "github_projection"},
                    "subject_binding": "INCOMPLETE",
                    "reason": "",
                    "readbacks": [],
                },
            ),
            ("a pull number that is not positive", changed(pull_number=0)),
            ("not an object", []),
        ):
            with (
                self.subTest(name),
                self.assertRaises(analyzer_readback.AnalyzerReadbackError),
            ):
                analyzer_readback.parse_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
