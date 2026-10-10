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
    require_commit,
    require_mapping,
    require_text,
    require_unique_texts,
)
from .check_change_policy import change_policy_issues, load_change_policy
from .knowledge_common import KnowledgeFormatError
from .review_model import parse_rfc3339
from .verdict_cli import read_json_input, run

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
_AUTHORITY_KEYS = frozenset({"declarer", "author", "required_approvers"})
_REVIEW_KEYS = frozenset({"reviewer", "state", "commit_id", "submitted_at"})
_REVIEW_STATES = frozenset(
    {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}
)
_OPINIONS = frozenset({"APPROVED", "CHANGES_REQUESTED"})
# Reviews from one reviewer that share the latest second and disagree have no
# order: their state reads as this, which is neither an approval nor a pass.
_AMBIGUOUS = "AMBIGUOUS"
# The values the change-control schema allows for the fields M14 reads.
_WORK_ITEM_RULES = frozenset({"optional", "required-follow-up", "required"})
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


def _reviews(value: object) -> dict[str, list[dict[str, Any]]]:
    """The submitted reviews, grouped by reviewer once, so each criterion reads a
    reviewer's own reviews in time linear in the input (CodeAnt on #410)."""

    if not isinstance(value, list):
        raise AssuranceCompletenessError("reviews must be a list")
    by_reviewer: dict[str, list[dict[str, Any]]] = {}
    for index, item in enumerate(value):
        label = f"review {index}"
        review = require_mapping(item, label)
        require_closed_keys(review, label, _REVIEW_KEYS)
        state = review["state"]
        if not isinstance(state, str) or state not in _REVIEW_STATES:
            raise AssuranceCompletenessError(f"{label} has unknown state {state!r}")
        reviewer = require_text(review["reviewer"], f"{label} reviewer")
        # GitHub's commit is null once the commit is garbage-collected or
        # force-deleted (CodeAnt on #410); such a review approves no head.
        commit_id = (
            None
            if review["commit_id"] is None
            else require_commit(review["commit_id"], f"{label} commit_id")
        )
        if state == "PENDING" and review["submitted_at"] is None:
            # Not submitted, so no one's opinion yet; GitHub returns the reader's
            # own with no timestamp (Sourcery on #410). Only the timestamp may be
            # absent: the rest is validated first (Codex on #410).
            continue
        try:
            submitted = parse_rfc3339(review["submitted_at"])
        except ValueError as exc:
            raise AssuranceCompletenessError(f"{label} submitted_at: {exc}") from exc
        if state == "PENDING":
            continue
        by_reviewer.setdefault(reviewer, []).append(
            {
                "state": state,
                "commit_id": commit_id,
                # Whole seconds: a fraction cannot order two opinions inside the
                # second the rule leaves unordered (CodeAnt on #410).
                "second": submitted.timeline_seconds,
            }
        )
    return by_reviewer


def _latest(
    own: list[dict[str, Any]],
    states: frozenset[str] | None,
    *,
    by_commit: bool,
) -> dict[str, Any] | None:
    """One reviewer's latest review among `states`. A tie is judged only by what
    the criterion reads: the state, and with `by_commit` also the commit (cubic on
    #410)."""

    considered = [r for r in own if states is None or r["state"] in states]
    if not considered:
        return None
    newest = max(r["second"] for r in considered)
    tied = {
        (r["state"], r["commit_id"] if by_commit else None)
        for r in considered
        if r["second"] == newest
    }
    if len(tied) > 1:
        # Timestamps have second resolution, so a tie has no order (cubic, CodeAnt
        # and Sourcery on #410).
        return {"state": _AMBIGUOUS, "commit_id": None}
    ((state, commit_id),) = tied
    return {"state": state, "commit_id": commit_id}


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
    if (
        require_commit(candidate["head_commit"], "declared_candidate head_commit")
        != head
    ):
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


def _requests_for_changes(
    reviews: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    reasons = []
    for reviewer in sorted(reviews):
        opinion = _latest(reviews[reviewer], _OPINIONS, by_commit=False)
        if opinion is None or opinion["state"] == "APPROVED":
            continue
        if opinion["state"] == _AMBIGUOUS:
            reasons.append(
                f"{reviewer}'s latest opinions share one second and disagree"
            )
        else:
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
    # A coverage, so "not read" cannot pass as "none found" (#407, slice 1b.3a).
    record = _coverage(evidence["suppressions"], "suppressions", frozenset({"found"}))
    value = record["found"]
    if not isinstance(value, list):
        raise AssuranceCompletenessError("suppressions found must be a list")
    justified, reasons = [], []
    if record["coverage"] != "COMPLETE":
        reasons.append(f"suppression coverage is {record['coverage']}")
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


def _trust_roots(evidence: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """M15: the changed trust roots are listed for the approval, which needs a
    complete read of them (#407, slice 1b.3a)."""

    record = _coverage(
        evidence["trust_root_changes"], "trust_root_changes", frozenset({"paths"})
    )
    paths = _texts(record["paths"], "trust_root_changes paths")
    reasons = []
    if record["coverage"] != "COMPLETE":
        reasons.append(f"trust-root coverage is {record['coverage']}")
    return _criterion("M15", reasons), paths


def _class_requirements(
    change_policy: Mapping[str, Any], change_class: str
) -> tuple[str, Mapping[str, Any]]:
    label = f"change policy class {change_class!r}"
    return label, require_mapping(
        require_mapping(
            change_policy.get("change_classes"), "change policy classes"
        ).get(change_class),
        label,
    )


def _boolean_rule(requirements: Mapping[str, Any], field: str, label: str) -> bool:
    value = requirements.get(field)
    if not isinstance(value, bool):
        raise AssuranceCompletenessError(f"{label} has {field} {value!r}")
    return value


def _class_links(
    evidence: Mapping[str, Any], change_class: str, change_policy: Mapping[str, Any]
) -> dict[str, Any]:
    links = require_mapping(evidence["links"], "links")
    require_closed_keys(links, "links", _LINK_KEYS)
    # Parsed whatever the class requires, emergencies included (Codex on #410).
    work_items = _texts(links["work_items"], "links work_items")
    decisions = _texts(links["decisions"], "links decisions")
    if change_class == "emergency":
        return _criterion(
            "M14",
            ["an emergency merges through break glass, never through this verdict"],
        )
    label, requirements = _class_requirements(change_policy, change_class)
    # The schema's own values only: a malformed field must not read as "not
    # required" (cubic, CodeAnt and Sourcery on #410).
    work_item = requirements.get("work_item")
    if not isinstance(work_item, str) or work_item not in _WORK_ITEM_RULES:
        raise AssuranceCompletenessError(f"{label} has work_item {work_item!r}")
    decision_record = _boolean_rule(requirements, "decision_record", label)
    reasons = []
    if work_item == "required" and not work_items:
        reasons.append(f"a {change_class} change needs a linked Work Item")
    if decision_record and not decisions:
        reasons.append(f"a {change_class} change needs a linked Decision")
    return _criterion("M14", reasons)


def _approval(
    reviews: Mapping[str, list[dict[str, Any]]],
    head: str,
    authorities: Mapping[str, Any],
    rules: tuple[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Runbook step 8, bound to the class's approval rules (CodeAnt on #410).

    Who the required approvers are, the protected target's code owners, and
    whether each is human are the adapter's to establish (1b.3): a provider
    account's type does not tell a person from a machine user.
    """

    label, requirements = rules
    minimum = requirements.get("minimum_approvals")
    if type(minimum) is not int or minimum < 0:
        raise AssuranceCompletenessError(f"{label} has minimum_approvals {minimum!r}")
    independent = _boolean_rule(requirements, "independent_approval", label)
    approvers = authorities["required_approvers"]
    reasons = []
    # The class's minimum alone decides whether an empty list suffices: the core
    # policy requires no approval (Codex on #410).
    if len(approvers) < minimum:
        reasons.append(
            f"the class needs {minimum} approval(s), and "
            f"{len(approvers)} approver(s) are named"
        )
    if independent:
        # No self-approval, required or not (`may_approve_own_change: false`;
        # cubic on #410). A dismissed approval is DISMISSED, so it no longer counts.
        for party in ("declarer", "author"):
            identity = authorities[party]
            if identity in approvers:
                reasons.append(
                    f"{identity} is the change's {party} and cannot be an approver"
                )
            elif any(r["state"] == "APPROVED" for r in reviews.get(identity, [])):
                reasons.append(f"{identity} is the change's {party} and approved it")
    for approver in approvers:
        latest = _latest(reviews.get(approver, []), None, by_commit=True)
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
    author = require_text(authorities["author"], "authorities author")
    # Distinct, or a repeat would be corrupt evidence that rescans the same
    # reviews (Codex on #410); empty when the class requires none.
    approvers = require_unique_texts(
        authorities["required_approvers"],
        "authorities required_approvers",
        allow_empty=True,
    )
    reviews = _reviews(document["reviews"])

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
    trust_root_criterion, trust_roots = _trust_roots(document)
    criteria = [
        _lifecycle(document),
        complete,
        _candidate(document, head, declarer),
        _threads(document),
        _requests_for_changes(reviews),
        _closing_references(document),
        suppressions,
        _class_links(document, change_class, change_policy),
        trust_root_criterion,
        _approval(
            reviews,
            head,
            {"declarer": declarer, "author": author, "required_approvers": approvers},
            _class_requirements(change_policy, change_class),
        ),
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
    """Load the effective change policy, its whole inheritance chain confined to
    `project_root`, and refuse it unless the schema accepts it (Codex, cubic,
    CodeAnt and Sourcery on #410)."""

    try:
        policy = load_change_policy(path, project_root=project_root)
        issues = change_policy_issues(policy)
    except KnowledgeFormatError as exc:
        raise AssuranceCompletenessError(str(exc)) from exc
    if issues:
        raise AssuranceCompletenessError(
            "the change policy does not match its schema: " + "; ".join(issues)
        )
    return policy


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
