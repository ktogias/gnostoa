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
