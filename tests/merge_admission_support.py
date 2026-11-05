"""What other test modules share from tests/test_merge_admission.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import copy
from typing import Any

from tools import (
    assurance_completeness,
    merge_admission,
)

HEAD = "a" * 40


SUBJECT = {
    "repository": "https://github.com/example/project",
    "change_request": {"kind": "github-pull-request", "id": "7"},
    "head_commit": HEAD,
}


DECLARATION = {
    "schema_version": "1.0",
    "id": "example.required-evidence",
    "version": "0.1.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The required checks ran on the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["fast", "smoke"],
        }
    ],
}


_APPROVED_BY_ONE_INDEPENDENT_HUMAN = {
    "minimum_approvals": 1,
    "independent_approval": True,
    "human_approval": True,
    "code_owner_approval": True,
}


POLICY = {
    "change_classes": {
        "mechanical": {
            "work_item": "optional",
            "decision_record": False,
            **_APPROVED_BY_ONE_INDEPENDENT_HUMAN,
        },
        **{
            name: {
                "work_item": "required",
                "decision_record": True,
                **_APPROVED_BY_ONE_INDEPENDENT_HUMAN,
            }
            for name in ("normal", "normative", "critical")
        },
        "emergency": {
            "work_item": "required-follow-up",
            "decision_record": True,
            "minimum_approvals": 0,
            "independent_approval": False,
            "human_approval": False,
            "code_owner_approval": False,
        },
    }
}


def _receipt(subject: dict[str, Any], coverage: list[str]) -> dict[str, Any]:
    return {
        "schema": "gnostoa-evidence-receipt/v1",
        "requirement": "verification-checks",
        "subject": subject,
        "producer": "checks",
        "observed_at": "2026-10-09T08:00:00Z",
        "status": "COMPLETE",
        "coverage": coverage,
    }


def _evidence(subject: dict[str, Any] | None = None) -> dict[str, Any]:
    exact = copy.deepcopy(SUBJECT if subject is None else subject)
    return {
        "subject": exact,
        "lifecycle": {
            "state": "open",
            "draft": False,
            "target": "main",
            "protected_target": "main",
        },
        "change_class": "normal",
        "links": {"work_items": ["#407"], "decisions": ["0112"]},
        "declared_candidate": {"declarer": "agent-app", "head_commit": HEAD},
        "authorities": {
            "declarer": "agent-app",
            "author": "agent-user",
            "required_approvers": ["owner"],
        },
        "reviews": [
            {
                "reviewer": "owner",
                "state": "APPROVED",
                "commit_id": HEAD,
                "submitted_at": "2026-10-09T09:00:00Z",
            }
        ],
        "threads": {"coverage": "COMPLETE", "unresolved": 0},
        "closing_references": {"coverage": "COMPLETE", "found": []},
        "suppressions": {"coverage": "COMPLETE", "found": []},
        "trust_root_changes": {"coverage": "COMPLETE", "paths": []},
        "analyzer_retired": [{"provider": "deepsource", "decision": "0130"}],
        "analyzer_findings": {"coverage": "COMPLETE", "findings": []},
        "receipts": [_receipt(exact, ["fast", "smoke"])],
    }


def _verdict(evidence: dict[str, Any]) -> dict[str, Any]:
    declaration = assurance_completeness.parse_declaration(DECLARATION)
    return merge_admission.evaluate(
        evidence, declaration=declaration, change_policy=POLICY
    )


def _failed(verdict: dict[str, Any]) -> dict[str, list[str]]:
    return {c["id"]: c["reasons"] for c in verdict["criteria"] if c["status"] == "FAIL"}


# A finding's enclosing scope on the head, and the ledger entry that proved it on
# protected main (#389, the M17 transition).
_SCOPE = "c" * 64
# A finding's run-bound configuration identity, as merge evidence derives it (owner
# 6620829215 §2, 6621293483 §1): its readback's adapter and protected profile digest,
# and its own producer's effective identity.
CONFIGURATION = (
    "gnostoa-inventory-fake/v1@sha256:" + "b" * 64 + "/python@sha256:" + "e" * 64
)


def debt_entry(**changes: Any) -> dict[str, Any]:
    """A ledger entry for `debt_finding`'s finding, shared with the evidence tests."""
    entry: dict[str, Any] = {
        "id": "debt-1",
        "item": "deepsource-full",
        "rule": "PY-R1000",
        "path": "tools/x.py",
        "message": "`f` has a cyclomatic complexity of 16",
        "enclosing_sha256": _SCOPE,
        "tool": {"id": "python"},
        "severity": "MINOR",
        "configuration": CONFIGURATION,
        "aspect": "complexity",
        "provenance": {
            "commit": "d" * 40,
            "readback_run": "41678204434",
            "admitted_by": "6612057593",
        },
    }
    entry.update(changes)
    return entry


def debt_finding(**changes: Any) -> dict[str, Any]:
    """A listed finding with its enclosing scope, shared with the evidence tests."""
    finding: dict[str, Any] = {
        "item": "deepsource-full",
        "id": "issue-1",
        "message": "`f` has a cyclomatic complexity of 16",
        "rule": "PY-R1000",
        "path": "tools/x.py",
        "tool": {"id": "python"},
        "severity": "MINOR",
        "configuration": CONFIGURATION,
        "enclosing": {"kind": "function", "name": "f", "sha256": _SCOPE},
    }
    finding.update(changes)
    return finding
