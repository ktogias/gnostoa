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
RECEIPT_SCHEMA = "gnostoa-evidence-receipt/v1"
VERDICT_SCHEMA = "gnostoa-assurance-completeness/v1"

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
    require_closed_keys(value, "declaration", _DECLARATION_KEYS)
    if value["schema_version"] != DECLARATION_SCHEMA_VERSION:
        raise AssuranceCompletenessError(
            f"declaration schema_version must be {DECLARATION_SCHEMA_VERSION!r}"
        )
    requirements = value["requirements"]
    if not isinstance(requirements, list) or not requirements:
        raise AssuranceCompletenessError("declaration requirements must be non-empty")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(requirements):
        label = f"requirement {index}"
        requirement = require_mapping(item, label)
        require_closed_keys(requirement, label, _REQUIREMENT_KEYS)
        classes = require_unique_texts(requirement["applies_to"], f"{label} applies_to")
        for change_class in classes:
            parse_change_class(change_class)
        normalized.append(
            {
                "id": _identifier(requirement["id"], f"{label} id"),
                "title": require_text(requirement["title"], f"{label} title"),
                "applies_to": classes,
                "coverage": require_unique_texts(
                    requirement["coverage"], f"{label} coverage"
                ),
            }
        )
    ids = [requirement["id"] for requirement in normalized]
    if len(set(ids)) != len(ids):
        raise AssuranceCompletenessError("declaration has a duplicate requirement id")
    return {
        "schema_version": DECLARATION_SCHEMA_VERSION,
        "id": require_text(value["id"], "declaration id"),
        "version": require_text(value["version"], "declaration version"),
        "requirements": normalized,
    }


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

    reasons: list[str] = []
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
