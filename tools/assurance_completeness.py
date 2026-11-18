"""Reduce exact-subject evidence receipts into a completeness verdict (#389 S1).

A project declares which evidence each change class requires, as named coverage
items. Producers' receipts are reduced against that declaration for one exact
subject: a repository, a change request and its head commit. Only a current
`COMPLETE` receipt covers an item. An item no current receipt covers is
`MISSING`, or `STALE` when only receipts for another head cover it, and receipts
that disagree fail closed at the worse status. Nothing here fetches evidence or
grants any authority: the verdict is evidence for a consumer such as the
merge-admission verdict (Decision 0112).

The subject is compared exactly, field for field. Producers' adapters translate
their own identifiers into the subject's form before the receipt reaches the
reducer: for example, an analyzer readback's `owner/name` into the repository
form the current-state observation uses (slice 1b.3). A receipt in another form
is ignored and counted, so its items fail closed as `MISSING`.

A declaration of schema `1.1` (#389 F1) also gives each item its failure domain and
names claims. A claim lists the items qualified to support it and, for each change
class it applies to, how many distinct domains must support it with a current
`COMPLETE` item. Its verdict (`v2`) is `COMPLETE` only when every applicable claim
is. Item statuses are computed as for `1.0` and never upgraded: an item that is not
complete is listed as degraded. Domains and claims come only from the protected
declaration, never from a receipt. A `1.0` declaration keeps its form and its `v1`
verdict.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import analyzer_readback, verdict_cli
from .knowledge_common import KnowledgeFormatError
from .review_model import parse_rfc3339
from .review_policy import CHANGE_CLASSES, load_policy_yaml
from .verdict_cli import confine, read_json_input, run

DECLARATION_SCHEMA_VERSION = "1.0"
CLAIMS_SCHEMA_VERSION = "1.1"
RECEIPT_SCHEMA = "gnostoa-evidence-receipt/v1"
VERDICT_SCHEMA = "gnostoa-assurance-completeness/v1"
CLAIMS_VERDICT_SCHEMA = "gnostoa-assurance-completeness/v2"

# Decision 0091's coverage statuses, which include Decision 0086's, plus #389's
# SKIPPED. The reducer derives MISSING and STALE; a producer cannot report them.
RECEIPT_STATUSES = analyzer_readback.COVERAGE_STATUSES | frozenset({"SKIPPED"})
DERIVED_STATUSES = frozenset({"MISSING", "STALE"})
# Worst first, so receipts that disagree fail closed at the worse status, and a
# requirement reports its worst item.
_PRECEDENCE = (
    "ERROR",
    "UNAVAILABLE",
    "RATE_LIMITED",
    "PARTIAL",
    "INCOMPLETE",
    "SKIPPED",
    "STALE",
    "MISSING",
)

# The shared boundary's bound, named here for this command's callers.
MAX_INPUT_BYTES = verdict_cli.MAX_INPUT_BYTES
DEFAULT_DECLARATION = Path("policy") / "assurance-evidence.yaml"
_INPUT_LABEL = "assurance-check input"
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_DECLARATION_KEYS = frozenset({"schema_version", "id", "version", "requirements"})
_REQUIREMENT_KEYS = frozenset({"id", "title", "applies_to", "coverage"})
_CLAIMS_DECLARATION_KEYS = _DECLARATION_KEYS | {"claims"}
_CLAIMS_REQUIREMENT_KEYS = _REQUIREMENT_KEYS | {"domains"}
_CLAIM_KEYS = frozenset({"id", "title", "evidence", "independent_domains"})
_EVIDENCE_KEYS = frozenset({"requirement", "item"})
_RECEIPT_KEYS = frozenset(
    {
        "schema",
        "requirement",
        "subject",
        "producer",
        "observed_at",
        "status",
        "coverage",
    }
)
_RECEIPT_OPTIONAL_KEYS = frozenset({"provenance"})
_SUBJECT_KEYS = frozenset({"repository", "change_request", "head_commit"})
_CHANGE_REQUEST_KEYS = frozenset({"kind", "id"})
_INPUT_KEYS = frozenset({"subject", "change_class", "receipts"})


class AssuranceCompletenessError(ValueError):
    """A declaration, subject or receipt violates the closed contract."""


def require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssuranceCompletenessError(f"{label} must be a mapping")
    return value


def require_closed_keys(
    value: Mapping[str, Any],
    label: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    # YAML admits keys of any type; sorting a mix of them would raise TypeError.
    if not all(isinstance(key, str) for key in value):
        raise AssuranceCompletenessError(f"{label} has a key that is not a string")
    unknown = sorted(set(value) - required - optional)
    if unknown:
        raise AssuranceCompletenessError(f"{label} has unknown key {unknown[0]!r}")
    missing = sorted(required - set(value))
    if missing:
        raise AssuranceCompletenessError(f"{label} lacks {missing[0]!r}")


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssuranceCompletenessError(f"{label} must be a non-empty string")
    return value


def require_identifier(value: object, label: str) -> str:
    """A requirement or coverage-item identifier: lowercase letters, digits and
    hyphens. The merge-evidence adapter's manifest uses it too (#407, 1b.3b-1)."""

    text = require_text(value, label)
    if _IDENTIFIER.fullmatch(text) is None:
        raise AssuranceCompletenessError(
            f"{label} must be lowercase letters, digits and hyphens"
        )
    return text


_identifier = require_identifier


def require_unique_texts(
    value: object, label: str, *, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or not (value or allow_empty):
        raise AssuranceCompletenessError(f"{label} must be a non-empty list")
    items = [require_text(item, label) for item in value]
    if len(set(items)) != len(items):
        raise AssuranceCompletenessError(f"{label} has a duplicate entry")
    return items


def parse_change_class(value: object) -> str:
    # A string first: a JSON array or object is unhashable in the membership test.
    if not isinstance(value, str) or value not in CHANGE_CLASSES:
        raise AssuranceCompletenessError(f"unknown change class {value!r}")
    return value


def parse_declaration(document: object) -> dict[str, Any]:
    """Validate a required-evidence declaration and return it normalized."""

    value = require_mapping(document, "declaration")
    claims_form = value.get("schema_version") == CLAIMS_SCHEMA_VERSION
    require_closed_keys(
        value,
        "declaration",
        _CLAIMS_DECLARATION_KEYS if claims_form else _DECLARATION_KEYS,
    )
    if not claims_form and value["schema_version"] != DECLARATION_SCHEMA_VERSION:
        raise AssuranceCompletenessError(
            f"declaration schema_version must be {DECLARATION_SCHEMA_VERSION!r} "
            f"or {CLAIMS_SCHEMA_VERSION!r}"
        )
    requirements = value["requirements"]
    if not isinstance(requirements, list) or not requirements:
        raise AssuranceCompletenessError("declaration requirements must be non-empty")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(requirements):
        label = f"requirement {index}"
        requirement = require_mapping(item, label)
        require_closed_keys(
            requirement,
            label,
            _CLAIMS_REQUIREMENT_KEYS if claims_form else _REQUIREMENT_KEYS,
        )
        classes = require_unique_texts(requirement["applies_to"], f"{label} applies_to")
        for change_class in classes:
            parse_change_class(change_class)
        entry: dict[str, Any] = {
            "id": _identifier(requirement["id"], f"{label} id"),
            "title": require_text(requirement["title"], f"{label} title"),
            "applies_to": classes,
            "coverage": require_unique_texts(
                requirement["coverage"], f"{label} coverage"
            ),
        }
        if claims_form:
            entry["domains"] = _domains(
                requirement["domains"], entry["coverage"], label
            )
        normalized.append(entry)
    ids = [requirement["id"] for requirement in normalized]
    if len(set(ids)) != len(ids):
        raise AssuranceCompletenessError("declaration has a duplicate requirement id")
    declaration: dict[str, Any] = {
        "schema_version": (
            CLAIMS_SCHEMA_VERSION if claims_form else DECLARATION_SCHEMA_VERSION
        ),
        "id": require_text(value["id"], "declaration id"),
        "version": require_text(value["version"], "declaration version"),
        "requirements": normalized,
    }
    if claims_form:
        declaration["claims"] = _claims(value["claims"], normalized)
    return declaration


def _domains(value: object, coverage: list[str], label: str) -> dict[str, str]:
    """Each coverage item's failure domain: one identifier per item, no more."""

    domains = require_mapping(value, f"{label} domains")
    if set(domains) != set(coverage):
        raise AssuranceCompletenessError(
            f"{label} domains must name exactly its coverage"
        )
    return {
        item: _identifier(domains[item], f"{label} domain of {item!r}")
        for item in coverage
    }


def _minimum(value: object, label: str) -> int:
    # bool is an int in Python; a minimum of True is not one.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AssuranceCompletenessError(f"{label} must be a positive integer")
    return value


def _claim_evidence(
    value: object, label: str, requirements: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise AssuranceCompletenessError(f"{label} evidence must be a non-empty list")
    evidence: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(value):
        entry_label = f"{label} evidence {index}"
        entry = require_mapping(item, entry_label)
        require_closed_keys(entry, entry_label, _EVIDENCE_KEYS)
        requirement = require_text(entry["requirement"], f"{entry_label} requirement")
        name = require_text(entry["item"], f"{entry_label} item")
        if (
            requirement not in requirements
            or name not in requirements[requirement]["coverage"]
        ):
            raise AssuranceCompletenessError(
                f"{entry_label}: requirement {requirement!r} item {name!r} "
                "is not declared"
            )
        if (requirement, name) in seen:
            raise AssuranceCompletenessError(f"{label} has duplicate evidence")
        seen.add((requirement, name))
        evidence.append({"requirement": requirement, "item": name})
    return evidence


def _claim(
    value: object, index: int, requirements: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    label = f"claim {index}"
    claim = require_mapping(value, label)
    require_closed_keys(claim, label, _CLAIM_KEYS)
    identifier = _identifier(claim["id"], f"{label} id")
    evidence = _claim_evidence(claim["evidence"], label, requirements)
    minimums = require_mapping(
        claim["independent_domains"], f"{label} independent_domains"
    )
    if not minimums:
        raise AssuranceCompletenessError(
            f"{label} independent_domains must be non-empty"
        )
    available = len(
        {requirements[e["requirement"]]["domains"][e["item"]] for e in evidence}
    )
    normalized: dict[str, int] = {}
    for change_class, minimum in minimums.items():
        parse_change_class(change_class)
        normalized[change_class] = _minimum(
            minimum, f"{label} independent_domains {change_class!r}"
        )
        for entry in evidence:
            if change_class not in requirements[entry["requirement"]]["applies_to"]:
                raise AssuranceCompletenessError(
                    f"{label}: requirement {entry['requirement']!r} "
                    f"does not apply to {change_class!r}"
                )
        if normalized[change_class] > available:
            raise AssuranceCompletenessError(
                f"{label} {identifier!r} requires {normalized[change_class]} "
                f"independent domains for {change_class!r} but its evidence has "
                f"{available}"
            )
    return {
        "id": identifier,
        "title": require_text(claim["title"], f"{label} title"),
        "evidence": evidence,
        "independent_domains": normalized,
    }


def _claims(value: object, requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The declaration's claims, each checked against the requirements it names.

    Every item a class collects must support some claim of that class, or an
    obligation would be dropped without a trace.
    """

    if not isinstance(value, list) or not value:
        raise AssuranceCompletenessError("declaration claims must be non-empty")
    by_id = {requirement["id"]: requirement for requirement in requirements}
    claims = [_claim(item, index, by_id) for index, item in enumerate(value)]
    ids = [claim["id"] for claim in claims]
    if len(set(ids)) != len(ids):
        raise AssuranceCompletenessError("declaration has a duplicate claim id")
    supported = {
        (change_class, entry["requirement"], entry["item"])
        for claim in claims
        for change_class in claim["independent_domains"]
        for entry in claim["evidence"]
    }
    for requirement in requirements:
        for change_class in requirement["applies_to"]:
            for item in requirement["coverage"]:
                if (change_class, requirement["id"], item) not in supported:
                    raise AssuranceCompletenessError(
                        f"requirement {requirement['id']!r} item {item!r} "
                        f"supports no claim for {change_class!r}"
                    )
    return claims


def load_declaration(path: Path, *, project_root: Path) -> dict[str, Any]:
    """Load a declaration from inside `project_root`, strictly and within bounds.

    The path is resolved, symbolic links included, and refused outside the root,
    as Decisions 0033 and 0034 confine a project's own references.
    """

    resolved = confine(
        path, project_root, label="declaration", error=AssuranceCompletenessError
    )
    try:
        document = load_policy_yaml(resolved, label="Required-evidence declaration")
    except KnowledgeFormatError as exc:
        raise AssuranceCompletenessError(str(exc)) from exc
    return parse_declaration(document)


def require_commit(value: object, label: str) -> str:
    """An exact commit identity: 40 lowercase hexadecimal characters."""

    commit = require_text(value, label)
    if _SHA40.fullmatch(commit) is None:
        raise AssuranceCompletenessError(f"{label} must be an exact 40-character SHA")
    return commit


def parse_subject(value: object, label: str) -> dict[str, Any]:
    subject = require_mapping(value, label)
    require_closed_keys(subject, label, _SUBJECT_KEYS)
    change_request = require_mapping(
        subject["change_request"], f"{label} change_request"
    )
    require_closed_keys(change_request, f"{label} change_request", _CHANGE_REQUEST_KEYS)
    head = require_commit(subject["head_commit"], f"{label} head_commit")
    return {
        "repository": require_text(subject["repository"], f"{label} repository"),
        "change_request": {
            "kind": require_text(
                change_request["kind"], f"{label} change_request kind"
            ),
            "id": require_text(change_request["id"], f"{label} change_request id"),
        },
        "head_commit": head,
    }


def _receipt(value: object, index: int) -> dict[str, Any]:
    label = f"receipt {index}"
    receipt = require_mapping(value, label)
    require_closed_keys(receipt, label, _RECEIPT_KEYS, _RECEIPT_OPTIONAL_KEYS)
    if receipt["schema"] != RECEIPT_SCHEMA:
        raise AssuranceCompletenessError(f"{label} schema must be {RECEIPT_SCHEMA!r}")
    status = receipt["status"]
    if not isinstance(status, str) or status not in RECEIPT_STATUSES:
        raise AssuranceCompletenessError(f"{label} has unknown status {status!r}")
    try:
        parse_rfc3339(receipt["observed_at"])
    except ValueError as exc:
        raise AssuranceCompletenessError(f"{label} observed_at: {exc}") from exc
    if "provenance" in receipt:
        require_mapping(receipt["provenance"], f"{label} provenance")
    require_text(receipt["producer"], f"{label} producer")
    return {
        "requirement": _identifier(receipt["requirement"], f"{label} requirement"),
        "subject": parse_subject(receipt["subject"], f"{label} subject"),
        "status": status,
        "coverage": require_unique_texts(receipt["coverage"], f"{label} coverage"),
    }


def _worst(statuses: list[str]) -> str:
    for status in _PRECEDENCE:
        if status in statuses:
            return status
    return "COMPLETE"


def _item_status(statuses: list[str], stale: bool) -> str:
    if statuses:
        return _worst(statuses)
    return "STALE" if stale else "MISSING"


def _change_of(subject: Mapping[str, Any]) -> tuple[str, str, str]:
    change_request = subject["change_request"]
    return subject["repository"], change_request["kind"], change_request["id"]


def _by_requirement(
    receipts: list[dict[str, Any]], exact: Mapping[str, Any], applicable: set[str]
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """Group the receipts for this change by requirement, counting the rest."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    ignored = 0
    for receipt in receipts:
        if (
            _change_of(receipt["subject"]) != _change_of(exact)
            or receipt["requirement"] not in applicable
        ):
            ignored += 1
            continue
        grouped.setdefault(receipt["requirement"], []).append(receipt)
    return grouped, ignored


def _requirement_result(
    requirement: Mapping[str, Any], own: list[dict[str, Any]], head: str
) -> dict[str, Any]:
    # One pass over the receipts' coverage, so the work grows with the input
    # rather than with items times receipts (CodeAnt on #408).
    current: dict[str, list[str]] = {}
    stale: set[str] = set()
    for receipt in own:
        if receipt["subject"]["head_commit"] == head:
            for item in receipt["coverage"]:
                current.setdefault(item, []).append(receipt["status"])
        else:
            stale.update(receipt["coverage"])
    items = [
        {
            "item": item,
            "status": _item_status(current.get(item, []), item in stale),
        }
        for item in requirement["coverage"]
    ]
    return {
        "id": requirement["id"],
        "status": _worst([entry["status"] for entry in items]),
        "items": items,
    }


def evaluate(
    declaration: Mapping[str, Any],
    *,
    subject: object,
    change_class: object,
    receipts: object,
) -> dict[str, Any]:
    """Reduce `receipts` for `subject` against a parsed declaration."""

    exact = parse_subject(subject, "subject")
    change_class = parse_change_class(change_class)
    if not isinstance(receipts, list):
        raise AssuranceCompletenessError("receipts must be a list")
    parsed = [_receipt(value, index) for index, value in enumerate(receipts)]

    applicable = [
        r for r in declaration["requirements"] if change_class in r["applies_to"]
    ]
    grouped, ignored = _by_requirement(parsed, exact, {r["id"] for r in applicable})
    results = [
        _requirement_result(r, grouped.get(r["id"], []), exact["head_commit"])
        for r in applicable
    ]

    if declaration["schema_version"] == CLAIMS_SCHEMA_VERSION:
        status, claims, degraded, reasons = _claims_reduction(
            declaration, change_class, results
        )
        return {
            "schema": CLAIMS_VERDICT_SCHEMA,
            "status": status,
            "subject": exact,
            "change_class": change_class,
            "declaration": {"id": declaration["id"], "version": declaration["version"]},
            "requirements": results,
            "claims": claims,
            "degraded": degraded,
            "reasons": reasons,
            "ignored_receipts": ignored,
        }
    reasons = []
    if not applicable:
        reasons.append(f"no requirement applies to change class {change_class!r}")
    complete = bool(applicable) and all(r["status"] == "COMPLETE" for r in results)
    return {
        "schema": VERDICT_SCHEMA,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "subject": exact,
        "change_class": change_class,
        "declaration": {"id": declaration["id"], "version": declaration["version"]},
        "requirements": results,
        "reasons": reasons,
        "ignored_receipts": ignored,
    }


def _claims_reduction(
    declaration: Mapping[str, Any], change_class: str, results: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Reduce a `1.1` declaration's claims over the item statuses already computed.

    A claim counts the distinct failure domains of its items that are `COMPLETE`;
    no status is upgraded, and every applicable item that is not complete is
    listed as degraded.
    """

    # `results` holds only the requirements that apply to `change_class`. Every
    # item a claim of this class names has a status here all the same: `_claim`
    # refuses a claim whose evidence names a requirement that does not apply to
    # each of its classes, and `evaluate` selects the applicable requirements by
    # that same class.
    statuses = {
        (result["id"], entry["item"]): entry["status"]
        for result in results
        for entry in result["items"]
    }
    domains = {
        (requirement["id"], item): domain
        for requirement in declaration["requirements"]
        for item, domain in requirement["domains"].items()
    }
    claims: list[dict[str, Any]] = []
    reasons: list[str] = []
    for claim in declaration["claims"]:
        if change_class not in claim["independent_domains"]:
            continue
        reduced, claim_reasons = _claim_reduction(
            claim, claim["independent_domains"][change_class], statuses, domains
        )
        claims.append(reduced)
        reasons.extend(claim_reasons)
    if not claims:
        reasons.append(f"no claim applies to change class {change_class!r}")
    complete = bool(claims) and all(claim["status"] == "COMPLETE" for claim in claims)
    status = "COMPLETE" if complete else "INCOMPLETE"
    return status, claims, _degraded(results), reasons


def _claim_reduction(
    claim: Mapping[str, Any],
    required: int,
    statuses: Mapping[tuple[str, str], str],
    domains: Mapping[tuple[str, str], str],
) -> tuple[dict[str, Any], list[str]]:
    """One applicable claim's result, and its reason when it is not complete."""

    evidence = [
        {
            "requirement": entry["requirement"],
            "item": entry["item"],
            "domain": domains[(entry["requirement"], entry["item"])],
            "status": statuses[(entry["requirement"], entry["item"])],
        }
        for entry in claim["evidence"]
    ]
    supporting = sorted(
        {entry["domain"] for entry in evidence if entry["status"] == "COMPLETE"}
    )
    complete = len(supporting) >= required
    reasons: list[str] = []
    if not complete:
        reasons.append(
            f"claim {claim['id']!r} is supported by {len(supporting)} of the "
            f"{required} independent domains it requires"
        )
    result: dict[str, Any] = {
        "id": claim["id"],
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "required_domains": required,
        "domains": supporting,
        "evidence": evidence,
    }
    return result, reasons


def _degraded(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every applicable item that is not `COMPLETE`, in requirement and item order."""

    return [
        {"requirement": result["id"], "item": entry["item"], "status": entry["status"]}
        for result in results
        for entry in result["items"]
        if entry["status"] != "COMPLETE"
    ]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge assurance-check",
        description=(
            "Reduce evidence receipts for one exact subject against a "
            "required-evidence declaration. Exit 0 when COMPLETE, 1 when "
            "INCOMPLETE, 2 when the input is invalid."
        ),
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="the project whose declaration applies (default: the working directory)",
    )
    parser.add_argument(
        "--declaration",
        type=Path,
        default=DEFAULT_DECLARATION,
        help=(
            "the required-evidence declaration, inside the project root "
            f"(default: {DEFAULT_DECLARATION})"
        ),
    )
    parser.epilog = (
        "The input, JSON with the subject, the change class and the receipts, is "
        "read from standard input."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    def compute() -> dict[str, Any]:
        declaration_path = (
            args.declaration
            if args.declaration.is_absolute()
            else args.project_root / args.declaration
        )
        declaration = load_declaration(declaration_path, project_root=args.project_root)
        payload = require_mapping(
            read_json_input(_INPUT_LABEL, AssuranceCompletenessError), "input"
        )
        require_closed_keys(payload, "input", _INPUT_KEYS)
        return evaluate(
            declaration,
            subject=payload["subject"],
            change_class=payload["change_class"],
            receipts=payload["receipts"],
        )

    return run(
        "assurance-check",
        compute,
        positive=lambda verdict: verdict["status"] == "COMPLETE",
        input_errors=(AssuranceCompletenessError,),
    )
