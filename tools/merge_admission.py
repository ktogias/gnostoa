"""Admit or deny one merge from normalized evidence (MA0 Phase 1b, slice 1b.2).

The verdict is provider-neutral and pure: a provider's adapter (slice 1b.3)
supplies an evidence document for the exact change, and the verdict is `ALLOW`
only when every criterion holds. Otherwise it is `DENY`, and it names each
criterion that failed. An unknown or missing input fails closed. The evidence part
(M2-M8) is the completeness reducer's verdict, computed here from the same
receipts ("one reducer", Decision 0112). The owner's native approval of the exact
head is the only per-merge human act (Decision 0112, item 3): justified
suppressions and trust-root changes are listed for it, not attested separately.
An emergency is never this verdict's `ALLOW`, since break glass bypasses the
protected branch's rules (Decision 0110).
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import assurance_completeness as completeness
from .assurance_completeness import (
    AssuranceCompletenessError,
    parse_change_class,
    parse_subject,
    require_closed_keys,
    require_mapping,
    require_text,
)
from .check_change_policy import load_change_policy
from .knowledge_common import KnowledgeFormatError
from .review_model import parse_rfc3339
from .verdict_cli import confine, read_json_input, run

VERDICT_SCHEMA = "gnostoa-merge-admission/v1"
DEFAULT_CHANGE_POLICY = Path("policy") / "change-control.yaml"
_INPUT_LABEL = "merge-admission input"
_EVIDENCE_KEYS = frozenset(
    {
        "subject",
        "lifecycle",
        "change_class",
        "links",
        "declared_candidate",
        "authorities",
        "reviews",
        "threads",
        "closing_references",
        "suppressions",
        "trust_root_changes",
        "receipts",
    }
)
_LIFECYCLE_KEYS = frozenset({"state", "draft", "target", "protected_target"})
_LINK_KEYS = frozenset({"work_items", "decisions"})
_CANDIDATE_KEYS = frozenset({"declarer", "head_commit"})
_AUTHORITY_KEYS = frozenset({"declarer", "required_approvers"})
_REVIEW_KEYS = frozenset({"reviewer", "state", "commit_id", "submitted_at"})
_REVIEW_STATES = frozenset(
    {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}
)
_OPINIONS = frozenset({"APPROVED", "CHANGES_REQUESTED"})
_COVERAGE_KEYS = frozenset({"coverage"})
_SUPPRESSION_KEYS = frozenset({"path", "marker", "justified"})
_REFERENCE_KEYS = frozenset({"surface", "reference"})


def _texts(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise AssuranceCompletenessError(f"{label} must be a list")
    return [require_text(item, label) for item in value]


def _flag(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise AssuranceCompletenessError(f"{label} must be true or false")
    return value


def _count(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise AssuranceCompletenessError(f"{label} must be a non-negative integer")
    return value


def _coverage(value: object, label: str, extra: frozenset[str]) -> Mapping[str, Any]:
    record = require_mapping(value, label)
    require_closed_keys(record, label, _COVERAGE_KEYS | extra)
    status = record["coverage"]
    if not isinstance(status, str) or status not in completeness.RECEIPT_STATUSES:
        raise AssuranceCompletenessError(f"{label} has unknown coverage {status!r}")
    return record


def _reviews(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise AssuranceCompletenessError("reviews must be a list")
    reviews = []
    for index, item in enumerate(value):
        label = f"review {index}"
        review = require_mapping(item, label)
        require_closed_keys(review, label, _REVIEW_KEYS)
        state = review["state"]
        if not isinstance(state, str) or state not in _REVIEW_STATES:
            raise AssuranceCompletenessError(f"{label} has unknown state {state!r}")
        try:
            submitted = parse_rfc3339(review["submitted_at"])
        except ValueError as exc:
            raise AssuranceCompletenessError(f"{label} submitted_at: {exc}") from exc
        reviews.append(
            {
                "reviewer": require_text(review["reviewer"], f"{label} reviewer"),
                "state": state,
                "commit_id": require_text(review["commit_id"], f"{label} commit_id"),
                "submitted_at": submitted,
            }
        )
    return reviews


def _latest(
    reviews: list[dict[str, Any]], reviewer: str, states: frozenset[str] | None
) -> dict[str, Any] | None:
    own = [
        r
        for r in reviews
        if r["reviewer"] == reviewer and (states is None or r["state"] in states)
    ]
    return max(own, key=lambda r: r["submitted_at"]) if own else None


def _criterion(identifier: str, reasons: list[str]) -> dict[str, Any]:
    return {
        "id": identifier,
        "status": "FAIL" if reasons else "PASS",
        "reasons": reasons,
    }


def _lifecycle(evidence: Mapping[str, Any]) -> dict[str, Any]:
    lifecycle = require_mapping(evidence["lifecycle"], "lifecycle")
    require_closed_keys(lifecycle, "lifecycle", _LIFECYCLE_KEYS)
    reasons = []
    if require_text(lifecycle["state"], "lifecycle state") != "open":
        reasons.append(f"the change request is {lifecycle['state']}, not open")
    if _flag(lifecycle["draft"], "lifecycle draft"):
        reasons.append("the change request is a draft")
    target = require_text(lifecycle["target"], "lifecycle target")
    protected = require_text(
        lifecycle["protected_target"], "lifecycle protected_target"
    )
    if target != protected:
        reasons.append(f"the change targets {target!r}, not {protected!r}")
    return _criterion("M1", reasons)


def _candidate(evidence: Mapping[str, Any], head: str, declarer: str) -> dict[str, Any]:
    if evidence["declared_candidate"] is None:
        return _criterion("M9", ["no candidate is declared"])
    candidate = require_mapping(evidence["declared_candidate"], "declared_candidate")
    require_closed_keys(candidate, "declared_candidate", _CANDIDATE_KEYS)
    reasons = []
    if require_text(candidate["declarer"], "declared_candidate declarer") != declarer:
        reasons.append(
            f"the candidate is declared by {candidate['declarer']!r}, not {declarer!r}"
        )
    if require_text(candidate["head_commit"], "declared_candidate head_commit") != head:
        reasons.append("the declared candidate is not the head")
    return _criterion("M9", reasons)


def _threads(evidence: Mapping[str, Any]) -> dict[str, Any]:
    threads = _coverage(evidence["threads"], "threads", frozenset({"unresolved"}))
    reasons = []
    if threads["coverage"] != "COMPLETE":
        reasons.append(f"thread coverage is {threads['coverage']}")
    unresolved = _count(threads["unresolved"], "threads unresolved")
    if unresolved:
        reasons.append(f"{unresolved} thread(s) unresolved")
    return _criterion("M10", reasons)


def _requests_for_changes(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = []
    for reviewer in sorted({r["reviewer"] for r in reviews}):
        opinion = _latest(reviews, reviewer, _OPINIONS)
        if opinion is not None and opinion["state"] == "CHANGES_REQUESTED":
            reasons.append(f"{reviewer} requests changes")
    return _criterion("M11", reasons)


def _closing_references(evidence: Mapping[str, Any]) -> dict[str, Any]:
    record = _coverage(
        evidence["closing_references"], "closing_references", frozenset({"found"})
    )
    found = record["found"]
    if not isinstance(found, list):
        raise AssuranceCompletenessError("closing_references found must be a list")
    reasons = []
    if record["coverage"] != "COMPLETE":
        reasons.append(f"closing-reference coverage is {record['coverage']}")
    for index, item in enumerate(found):
        reference = require_mapping(item, f"closing reference {index}")
        require_closed_keys(reference, f"closing reference {index}", _REFERENCE_KEYS)
        reasons.append(
            f"{require_text(reference['surface'], 'surface')} closes "
            f"{require_text(reference['reference'], 'reference')}"
        )
    return _criterion("M12", reasons)


def _suppressions(
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value = evidence["suppressions"]
    if not isinstance(value, list):
        raise AssuranceCompletenessError("suppressions must be a list")
    justified, reasons = [], []
    for index, item in enumerate(value):
        label = f"suppression {index}"
        suppression = require_mapping(item, label)
        require_closed_keys(suppression, label, _SUPPRESSION_KEYS)
        entry = {
            "path": require_text(suppression["path"], f"{label} path"),
            "marker": require_text(suppression["marker"], f"{label} marker"),
            "justified": _flag(suppression["justified"], f"{label} justified"),
        }
        if entry["justified"]:
            justified.append(entry)
        else:
            reasons.append(f"{entry['marker']} in {entry['path']} has no justification")
    return _criterion("M13", reasons), justified


def _class_links(
    evidence: Mapping[str, Any], change_class: str, change_policy: Mapping[str, Any]
) -> dict[str, Any]:
    if change_class == "emergency":
        return _criterion(
            "M14",
            ["an emergency merges through break glass, never through this verdict"],
        )
    links = require_mapping(evidence["links"], "links")
    require_closed_keys(links, "links", _LINK_KEYS)
    requirements = require_mapping(
        require_mapping(
            change_policy.get("change_classes"), "change policy classes"
        ).get(change_class),
        f"change policy class {change_class!r}",
    )
    reasons = []
    if requirements.get("work_item") == "required" and not _texts(
        links["work_items"], "links work_items"
    ):
        reasons.append(f"a {change_class} change needs a linked Work Item")
    if requirements.get("decision_record") is True and not _texts(
        links["decisions"], "links decisions"
    ):
        reasons.append(f"a {change_class} change needs a linked Decision")
    return _criterion("M14", reasons)


def _approval(
    reviews: list[dict[str, Any]], head: str, approvers: list[str]
) -> dict[str, Any]:
    if not approvers:
        return _criterion("M16", ["no required approver is named"])
    reasons = []
    for approver in approvers:
        latest = _latest(reviews, approver, None)
        if latest is None:
            reasons.append(f"{approver} has not reviewed")
        elif latest["state"] != "APPROVED":
            reasons.append(f"{approver}'s latest review is {latest['state']}")
        elif latest["commit_id"] != head:
            reasons.append(f"{approver} approved another commit, not the head")
    return _criterion("M16", reasons)


def evaluate(
    evidence: object,
    *,
    declaration: Mapping[str, Any],
    change_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Admit or deny the change the evidence describes."""

    document = require_mapping(evidence, "evidence")
    require_closed_keys(document, "evidence", _EVIDENCE_KEYS)
    subject = parse_subject(document["subject"], "subject")
    head = subject["head_commit"]
    change_class = parse_change_class(document["change_class"])
    authorities = require_mapping(document["authorities"], "authorities")
    require_closed_keys(authorities, "authorities", _AUTHORITY_KEYS)
    declarer = require_text(authorities["declarer"], "authorities declarer")
    approvers = _texts(
        authorities["required_approvers"], "authorities required_approvers"
    )
    reviews = _reviews(document["reviews"])
    trust_roots = _texts(document["trust_root_changes"], "trust_root_changes")

    evidence_verdict = completeness.evaluate(
        declaration,
        subject=subject,
        change_class=change_class,
        receipts=document["receipts"],
    )
    complete = _criterion(
        "M2-M8",
        []
        if evidence_verdict["status"] == "COMPLETE"
        else [f"required evidence is {evidence_verdict['status']}"],
    )
    suppressions, justified = _suppressions(document)
    criteria = [
        _lifecycle(document),
        complete,
        _candidate(document, head, declarer),
        _threads(document),
        _requests_for_changes(reviews),
        _closing_references(document),
        suppressions,
        _class_links(document, change_class, change_policy),
        _approval(reviews, head, approvers),
    ]
    allowed = all(c["status"] == "PASS" for c in criteria)
    return {
        "schema": VERDICT_SCHEMA,
        "status": "ALLOW" if allowed else "DENY",
        "subject": subject,
        "change_class": change_class,
        "criteria": criteria,
        "completeness": evidence_verdict,
        "for_approval": {
            "suppressions": justified,
            "trust_root_changes": trust_roots,
        },
    }


def load_policy(path: Path, *, project_root: Path) -> dict[str, Any]:
    """Load the effective change policy from inside `project_root`."""

    resolved = confine(
        path, project_root, label="change policy", error=AssuranceCompletenessError
    )
    try:
        return load_change_policy(resolved)
    except KnowledgeFormatError as exc:
        raise AssuranceCompletenessError(str(exc)) from exc


def _inside(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge merge-admission",
        description=(
            "Admit or deny one merge from normalized evidence. Exit 0 when "
            "ALLOW, 1 when DENY, 2 when the run failed."
        ),
        epilog="The evidence document is read from standard input.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="the project whose policy applies (default: the working directory)",
    )
    parser.add_argument(
        "--declaration",
        type=Path,
        default=completeness.DEFAULT_DECLARATION,
        help=f"the required-evidence declaration (default: {completeness.DEFAULT_DECLARATION})",
    )
    parser.add_argument(
        "--change-policy",
        type=Path,
        default=DEFAULT_CHANGE_POLICY,
        help=f"the change-control policy (default: {DEFAULT_CHANGE_POLICY})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    def compute() -> dict[str, Any]:
        root = args.project_root
        declaration = completeness.load_declaration(
            _inside(root, args.declaration), project_root=root
        )
        policy = load_policy(_inside(root, args.change_policy), project_root=root)
        return evaluate(
            read_json_input(_INPUT_LABEL, AssuranceCompletenessError),
            declaration=declaration,
            change_policy=policy,
        )

    return run(
        "merge-admission",
        compute,
        positive=lambda verdict: verdict["status"] == "ALLOW",
        input_errors=(AssuranceCompletenessError,),
    )
