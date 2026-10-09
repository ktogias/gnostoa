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
import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import analyzer_readback
from .knowledge_common import KnowledgeFormatError
from .review_check import assert_document_depth, strict_json_loads
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
    # YAML admits keys of any type; sorting a mix of them would raise TypeError.
    if not all(isinstance(key, str) for key in value):
        raise AssuranceCompletenessError(f"{label} has a key that is not a string")
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
    # A string first: a JSON array or object is unhashable in the membership test.
    if not isinstance(value, str) or value not in CHANGE_CLASSES:
        raise AssuranceCompletenessError(f"unknown change class {value!r}")
    return value


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


def load_declaration(path: Path, *, project_root: Path) -> dict[str, Any]:
    """Load a declaration from inside `project_root`, strictly and within bounds.

    The path is resolved, symbolic links included, and refused outside the root,
    as Decisions 0033 and 0034 confine a project's own references.
    """

    try:
        root = project_root.resolve()
        resolved = path.resolve()
    except (OSError, RuntimeError) as exc:
        # A symbolic-link loop raises RuntimeError before Python 3.13.
        raise AssuranceCompletenessError(
            f"cannot resolve the declaration: {exc}"
        ) from exc
    if not root.is_dir():
        raise AssuranceCompletenessError(f"project root {root} is not a directory")
    if not resolved.is_relative_to(root):
        raise AssuranceCompletenessError(
            f"declaration {resolved} is outside the project root {root}"
        )
    try:
        document = load_policy_yaml(resolved, label="Required-evidence declaration")
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
    if not isinstance(status, str) or status not in RECEIPT_STATUSES:
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
        "status": status,
        "coverage": _unique_texts(receipt["coverage"], f"{label} coverage"),
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

    exact = _subject(subject, "subject")
    change_class = _change_class(change_class)
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


def _read_input() -> object:
    """Read the input from standard input, so no input path reaches a file read
    (SonarCloud S8707 on #408)."""

    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    except (OSError, ValueError) as exc:
        # A closed stream raises ValueError; neither may exit as INCOMPLETE does.
        raise AssuranceCompletenessError(f"cannot read the input: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise AssuranceCompletenessError(
            f"input is larger than the {MAX_INPUT_BYTES}-byte bound"
        )
    try:
        value = strict_json_loads(raw.decode("utf-8"), label=_INPUT_LABEL)
        # The nesting bound review-check pairs with the same decoder (Claude on
        # #408).
        assert_document_depth(value, _INPUT_LABEL)
    except ValueError as exc:
        # UnicodeDecodeError and json's errors are ValueErrors.
        raise AssuranceCompletenessError(f"input is not valid JSON: {exc}") from exc
    return value


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


def _discard_stdout() -> None:
    """Point standard output at the null device after a broken pipe, as Python's
    `signal` documentation recommends, so the flush at shutdown cannot fail again
    and turn exit 2 into 120."""

    try:
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, sys.stdout.fileno())
    except (OSError, ValueError):
        # A stream without a file descriptor has nothing left to flush to a pipe.
        return


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        declaration_path = (
            args.declaration
            if args.declaration.is_absolute()
            else args.project_root / args.declaration
        )
        declaration = load_declaration(declaration_path, project_root=args.project_root)
        payload = _mapping(_read_input(), "input")
        _closed(payload, "input", _INPUT_KEYS)
        verdict = evaluate(
            declaration,
            subject=payload["subject"],
            change_class=payload["change_class"],
            receipts=payload["receipts"],
        )
        # Written and flushed inside the guard, so a broken pipe is a failed run
        # (cubic and Claude on #408). On a pipe, stdout is block-buffered: without
        # the flush the write fails at shutdown, after main returned, and Python
        # exits 120.
        print(json.dumps(verdict, indent=2, sort_keys=True))
        sys.stdout.flush()
    except AssuranceCompletenessError as exc:
        print(f"assurance-check: {exc}", file=sys.stderr)
        return 2
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        LookupError,
        AttributeError,
    ) as exc:
        # Whatever else fails is a failed run, never a verdict: Python's own exit
        # 1 for an uncaught exception would read as INCOMPLETE (#408).
        # RuntimeError includes RecursionError.
        if isinstance(exc, BrokenPipeError):
            _discard_stdout()
        print(f"assurance-check: error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0 if verdict["status"] == "COMPLETE" else 1
