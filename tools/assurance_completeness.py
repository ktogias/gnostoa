"""Reduce exact-subject evidence receipts into a completeness verdict (#389 S1).

A project declares which evidence each change class requires, as named coverage
items. Producers' receipts are reduced against that declaration for one exact
subject: a repository, a change request and its head commit. Only a current
`COMPLETE` receipt covers an item. An item no current receipt covers is
`MISSING`, or `STALE` when only receipts for another head cover it, and receipts
that disagree fail closed at the worse status. Nothing here fetches evidence or
grants any authority: the verdict is evidence for a consumer such as the
merge-admission verdict (Decision 0112).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import analyzer_readback
from .knowledge_common import KnowledgeFormatError
from .review_model import parse_rfc3339
from .review_policy import CHANGE_CLASSES, load_policy_yaml

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

MAX_INPUT_BYTES = 8 * 1024 * 1024
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


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AssuranceCompletenessError(f"{label} must be a mapping")
    return value


def _closed(
    value: Mapping[str, Any],
    label: str,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    unknown = sorted(set(value) - required - optional)
    if unknown:
        raise AssuranceCompletenessError(f"{label} has unknown key {unknown[0]!r}")
    missing = sorted(required - set(value))
    if missing:
        raise AssuranceCompletenessError(f"{label} lacks {missing[0]!r}")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssuranceCompletenessError(f"{label} must be a non-empty string")
    return value


def _identifier(value: object, label: str) -> str:
    text = _text(value, label)
    if _IDENTIFIER.fullmatch(text) is None:
        raise AssuranceCompletenessError(
            f"{label} must be lowercase letters, digits and hyphens"
        )
    return text


def _unique_texts(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise AssuranceCompletenessError(f"{label} must be a non-empty list")
    items = [_text(item, label) for item in value]
    if len(set(items)) != len(items):
        raise AssuranceCompletenessError(f"{label} has a duplicate entry")
    return items


def _change_class(value: object) -> str:
    if value not in CHANGE_CLASSES:
        raise AssuranceCompletenessError(f"unknown change class {value!r}")
    return str(value)


def parse_declaration(document: object) -> dict[str, Any]:
    """Validate a required-evidence declaration and return it normalized."""

    value = _mapping(document, "declaration")
    _closed(value, "declaration", _DECLARATION_KEYS)
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
        requirement = _mapping(item, label)
        _closed(requirement, label, _REQUIREMENT_KEYS)
        classes = _unique_texts(requirement["applies_to"], f"{label} applies_to")
        for change_class in classes:
            _change_class(change_class)
        normalized.append(
            {
                "id": _identifier(requirement["id"], f"{label} id"),
                "title": _text(requirement["title"], f"{label} title"),
                "applies_to": classes,
                "coverage": _unique_texts(requirement["coverage"], f"{label} coverage"),
            }
        )
    ids = [requirement["id"] for requirement in normalized]
    if len(set(ids)) != len(ids):
        raise AssuranceCompletenessError("declaration has a duplicate requirement id")
    return {
        "schema_version": DECLARATION_SCHEMA_VERSION,
        "id": _text(value["id"], "declaration id"),
        "version": _text(value["version"], "declaration version"),
        "requirements": normalized,
    }


def load_declaration(path: Path) -> dict[str, Any]:
    """Load a declaration through the strict, bounded policy loader."""

    try:
        document = load_policy_yaml(path, label="Required-evidence declaration")
    except KnowledgeFormatError as exc:
        raise AssuranceCompletenessError(str(exc)) from exc
    return parse_declaration(document)


def _subject(value: object, label: str) -> dict[str, Any]:
    subject = _mapping(value, label)
    _closed(subject, label, _SUBJECT_KEYS)
    change_request = _mapping(subject["change_request"], f"{label} change_request")
    _closed(change_request, f"{label} change_request", _CHANGE_REQUEST_KEYS)
    head = _text(subject["head_commit"], f"{label} head_commit")
    if _SHA40.fullmatch(head) is None:
        raise AssuranceCompletenessError(
            f"{label} head_commit must be an exact 40-character SHA"
        )
    return {
        "repository": _text(subject["repository"], f"{label} repository"),
        "change_request": {
            "kind": _text(change_request["kind"], f"{label} change_request kind"),
            "id": _text(change_request["id"], f"{label} change_request id"),
        },
        "head_commit": head,
    }


def _receipt(value: object, index: int) -> dict[str, Any]:
    label = f"receipt {index}"
    receipt = _mapping(value, label)
    _closed(receipt, label, _RECEIPT_KEYS, _RECEIPT_OPTIONAL_KEYS)
    if receipt["schema"] != RECEIPT_SCHEMA:
        raise AssuranceCompletenessError(f"{label} schema must be {RECEIPT_SCHEMA!r}")
    status = receipt["status"]
    if status not in RECEIPT_STATUSES:
        raise AssuranceCompletenessError(f"{label} has unknown status {status!r}")
    try:
        parse_rfc3339(receipt["observed_at"])
    except ValueError as exc:
        raise AssuranceCompletenessError(f"{label} observed_at: {exc}") from exc
    if "provenance" in receipt:
        _mapping(receipt["provenance"], f"{label} provenance")
    _text(receipt["producer"], f"{label} producer")
    return {
        "requirement": _identifier(receipt["requirement"], f"{label} requirement"),
        "subject": _subject(receipt["subject"], f"{label} subject"),
        "status": str(status),
        "coverage": _unique_texts(receipt["coverage"], f"{label} coverage"),
    }


def _worst(statuses: list[str]) -> str:
    for status in _PRECEDENCE:
        if status in statuses:
            return status
    return "COMPLETE"


def _item_status(item: str, current: list[dict[str, Any]], stale: bool) -> str:
    statuses = [r["status"] for r in current if item in r["coverage"]]
    if statuses:
        return _worst(statuses)
    return "STALE" if stale else "MISSING"


def evaluate(
    declaration: Mapping[str, Any],
    *,
    subject: object,
    change_class: object,
    receipts: object,
) -> dict[str, Any]:
    """Reduce `receipts` for `subject` against a parsed declaration."""

    exact = _subject(subject, "subject")
    change_class = _change_class(change_class)
    if not isinstance(receipts, list):
        raise AssuranceCompletenessError("receipts must be a list")
    parsed = [_receipt(value, index) for index, value in enumerate(receipts)]

    applicable = [
        r for r in declaration["requirements"] if change_class in r["applies_to"]
    ]
    applicable_ids = {r["id"] for r in applicable}
    same_change = {
        "repository": exact["repository"],
        "change_request": exact["change_request"],
    }
    ignored = 0
    by_requirement: dict[str, list[dict[str, Any]]] = {}
    for receipt in parsed:
        receipt_change = {
            "repository": receipt["subject"]["repository"],
            "change_request": receipt["subject"]["change_request"],
        }
        if (
            receipt_change != same_change
            or receipt["requirement"] not in applicable_ids
        ):
            ignored += 1
            continue
        by_requirement.setdefault(receipt["requirement"], []).append(receipt)

    results: list[dict[str, Any]] = []
    for requirement in applicable:
        own = by_requirement.get(requirement["id"], [])
        current = [
            r for r in own if r["subject"]["head_commit"] == exact["head_commit"]
        ]
        items = []
        for item in requirement["coverage"]:
            stale = any(
                item in r["coverage"]
                for r in own
                if r["subject"]["head_commit"] != exact["head_commit"]
            )
            items.append({"item": item, "status": _item_status(item, current, stale)})
        results.append(
            {
                "id": requirement["id"],
                "status": _worst([entry["status"] for entry in items]),
                "items": items,
            }
        )

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


def _read_input(path: Path) -> object:
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise AssuranceCompletenessError(f"cannot read input {path}: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise AssuranceCompletenessError(
            f"input {path} is larger than the {MAX_INPUT_BYTES}-byte bound"
        )
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise AssuranceCompletenessError(
            f"input {path} is not valid JSON: {exc}"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge assurance-check",
        description=(
            "Reduce evidence receipts for one exact subject against a "
            "required-evidence declaration. Exit 0 when COMPLETE, 1 when "
            "INCOMPLETE, 2 when the input is invalid."
        ),
    )
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="JSON with the subject, the change class and the receipts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        declaration = load_declaration(args.declaration)
        payload = _mapping(_read_input(args.input), "input")
        _closed(payload, "input", _INPUT_KEYS)
        verdict = evaluate(
            declaration,
            subject=payload["subject"],
            change_class=payload["change_class"],
            receipts=payload["receipts"],
        )
    except AssuranceCompletenessError as exc:
        print(f"assurance-check: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["status"] == "COMPLETE" else 1
