"""Produce the merge-admission evidence for one GitHub pull request (MA0 Phase 1b,
slice 1b.3a, #407).

The input is one L1 snapshot (Decision 0086), collected with `merge_evidence`; the
output is the evidence document `knowledge merge-admission` reads. The adapter
reads nothing itself: the snapshot is the provider's state, and the project root is
a checkout of the **protected target**, whose change policy, merge authorities and
CODEOWNERS apply. A value is never inferred. Where the evidence contract has a
coverage field, it carries the read's real status; where it has none, an incomplete
read fails the run.

The receipts cover the check items the protected target's required-check manifest
names (slice 1b.3b-1) and the analyzer-readback items, from the authenticated
readback's bundle (slice 1b.3b-2). The suppressions and trust-root changes come
from the exact comparison, against the protected target's declarations (slice
1b.3b-4); without a declaration, what it governs is `UNAVAILABLE`. Until
SonarCloud's (1b.3c) receipts exist, the verdict denies on M2-M8 rather than
passing it vacuously.
"""

from __future__ import annotations

import argparse
import heapq
import json
import re
import string
from collections.abc import Iterator, Mapping, Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, NamedTuple

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .analyzer_readback import parse_bundle
from .assurance_completeness import (
    RECEIPT_SCHEMA,
    RECEIPT_STATUSES,
    AssuranceCompletenessError,
    require_closed_keys,
    require_identifier,
    require_mapping,
    require_text,
    require_unique_texts,
)
from .knowledge_common import KnowledgeFormatError
from .merge_admission import load_policy
from .review_model import parse_rfc3339
from .review_policy import CHANGE_CLASSES, load_policy_yaml
from .review_reconcile import (
    ReconciliationInputError,
    check_runs_by_key,
    latest_checks,
    validate_snapshot,
)
from .verdict_cli import confine, read_json_file, read_json_input, run

DEFAULT_AUTHORITIES = Path("policy") / "merge-authorities.yaml"
DEFAULT_REQUIRED_CHECKS = Path("policy") / "merge-required-checks.yaml"
DEFAULT_SUPPRESSION_MARKERS = Path("policy") / "merge-suppression-markers.yaml"
DEFAULT_TRUST_ROOTS = Path("policy") / "merge-trust-roots.yaml"
_REQUIRED_CHECKS_LABEL = "required checks"
# The closed, versioned header every merge-evidence declaration shares.
_DECLARATION_KEYS = frozenset({"schema_version", "id", "version"})
_MARKERS_LABEL = "suppression markers"
_ROOTS_LABEL = "trust roots"
_CHECK_KEYS = frozenset({"app_id", "name"})
_CHECK_PRODUCER = "gnostoa.merge-evidence-github/check-runs"
# The authenticated readback's readbacks, by (provider, scope), and the
# declaration's items they give (1b.3b-2; #407, 6101607240).
_ANALYZER_REQUIREMENT = "analyzer-readback"
_ANALYZER_ITEMS = {
    ("deepsource", "DIFF"): "deepsource-diff",
    ("deepsource", "FULL"): "deepsource-full",
    ("codacy", "DIFF"): "codacy",
}
# The kind of read each item stands for, as the producer marks a complete one; a
# complete read of another kind does not give it (Decision 0091; Codex on #417).
_ANALYZER_COMPLETENESS = {
    "deepsource-diff": "DIFF_LOCAL",
    "deepsource-full": "FULL_RUN",
    "codacy": "FULL_RUN",
}
_ANALYZER_PRODUCER = "gnostoa.merge-evidence-github/analyzer-readback"
_ANALYZER_LABEL = "analyzer readback"
# As the readback normalized them; its provenance and native metadata stay in the
# bundle (the owner's re-admission, #417 6107601240).
_FINDING_FIELDS = (
    "rule",
    "severity",
    "category",
    "path",
    "state",
    "native_ref",
    "tool",
    "range",
)
DEFAULT_CHANGE_POLICY = Path("policy") / "change-control.yaml"
_INPUT_LABEL = "merge-evidence input"
_AUTHORITIES_LABEL = "merge authorities"
_AUTHORITY_KEYS = frozenset(
    {"schema_version", "id", "version", "declarer", "human_approvers"}
)
# GitHub's documented search order and size limit for CODEOWNERS.
CODEOWNERS_LOCATIONS = (
    Path(".github") / "CODEOWNERS",
    Path("CODEOWNERS"),
    Path("docs") / "CODEOWNERS",
)
CODEOWNERS_LIMIT = 3 * 1024 * 1024
# `*.ext`: GitHub's documented extension pattern.
_EXTENSION = re.compile(r"\*\.[^*?/]+")
_OWNER = re.compile(r"@[A-Za-z0-9-]+(?:/[A-Za-z0-9_.-]+)?|[^@\s]+@[^@\s]+")
# GitHub's login syntax: ASCII letters, digits and hyphens, and an App's `[bot]`.
_LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}")
_BOT_LOGIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}\[bot\]")
# Only ASCII letters fold. Unicode case folding maps compatibility characters,
# such as the Kelvin sign to `k`, so a login containing one would match another
# account (cubic on #413).
_ASCII_FOLD = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
_SEAL = re.compile(r"Exact review candidate: ([0-9a-f]{40})")
# GitHub's closing keywords, then an issue in one of its reference forms.
_CLOSING = re.compile(
    r"(?<![\w-])(close[sd]?|fix(?:e[sd])?|resolve[sd]?)(?![\w-]):?\s+"
    r"(#\d+|[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#\d+"
    r"|https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/\d+)(?!\w)",
    re.IGNORECASE,
)
# The description is read as CommonMark (Decision 0113): code blocks, HTML blocks
# and comments are their own tokens, never list items, so none can be a field.
_MARKDOWN = MarkdownIt("commonmark")
# The template's four fields; the section holds nothing else (cubic on #413; the
# owner's choice, #407 6092909419). Accountable owner is not read.
_FIELD = re.compile(
    r"(Class|Work Item|Decision|Accountable owner):[ \t]*(.*)", re.DOTALL
)
# The elements HTML's tree construction closes at once, so they contain nothing
# (cubic on #413).
_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "basefont",
        "bgsound",
        "br",
        "col",
        "embed",
        "frame",
        "hr",
        "img",
        "input",
        "keygen",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)
# A Work Item value is `#N` entries in ASCII digits, and a Decision value
# four-digit ids, separated by spaces or by one comma with optional spaces.
# Anything else, such as an invisible character, a URL or prose, fails the run:
# the owner chose a strict grammar over reading identifiers out of free text
# (#407, 6086766086, 6088050686 and 6088035894).
# `re.ASCII`, so `\d` is `[0-9]` and a Unicode digit is not one (CodeAnt on #413).
_WORK_ITEM_DIGITS = r"\d+"
_WORK_ITEM_NUMBER = rf"#{_WORK_ITEM_DIGITS}"
_WORK_ITEM_VALUE = re.compile(
    rf"{_WORK_ITEM_NUMBER}(?:(?: +| *, *){_WORK_ITEM_NUMBER})*", re.ASCII
)
_DECISION_VALUE = re.compile(r"\d{4}(?:(?: +| *, *)\d{4})*", re.ASCII)
_NUMBER = re.compile(r"\d+", re.ASCII)
_DECISION_RECORD = re.compile(r"(\d{4})-[a-z0-9-]+\.md")
DECISIONS_DIRECTORY = Path("knowledge") / "decisions"
# A link's label that carries one identifier, as the field's grammar writes it
# (1b.3b-3, #407 6108453639).
_WORK_ITEM_LABEL = re.compile(rf"#({_WORK_ITEM_DIGITS})", re.ASCII)
_DECISION_LABEL = re.compile(r"(\d{4})", re.ASCII)
_GITHUB = "https://github.com/"
# The rest of a link to an issue of the subject, after its repository URL.
_ISSUE_TARGET = re.compile(r"/issues/(\d+)", re.ASCII)
_WORK_ITEM_FIELD = "Work Item"
# L1's reasons for a PARTIAL reviews source that still kept every submitted review.
_REVIEW_SEMANTIC_REASONS = frozenset(
    {
        "unsubmitted_provider_items",
        "unavailable_reviewer_identity",
        "ambiguous_latest_reviewer_opinion",
    }
)
_MERGE_EVIDENCE_SUBJECT = (
    "draft",
    "merged",
    "target",
    "default_branch",
    "author",
    "body",
    "body_truncated",
)


class MergeEvidenceError(ValueError):
    """The snapshot or the protected target's declarations cannot give evidence."""


def login_key(login: str) -> str:
    """A login as compared and emitted: GitHub logins are case-insensitive
    (CodeAnt on #413), and only their ASCII letters fold."""

    return login.translate(_ASCII_FOLD)


def _declared_login(
    value: object, label: str, syntax: tuple[re.Pattern[str], ...]
) -> str:
    login = require_text(value, label)
    if not any(pattern.fullmatch(login) for pattern in syntax):
        raise MergeEvidenceError(f"{label} {login!r} is not a GitHub login")
    return login


def parse_authorities(document: object) -> dict[str, Any]:
    """The merge authorities: the seal's declarer and the human approvers' roster."""

    try:
        record = require_mapping(document, _AUTHORITIES_LABEL)
        require_closed_keys(record, _AUTHORITIES_LABEL, _AUTHORITY_KEYS)
        if record["schema_version"] != "1.0":
            raise MergeEvidenceError("merge authorities schema_version must be 1.0")
        require_text(record["id"], "merge authorities id")
        require_text(record["version"], "merge authorities version")
        approvers = require_unique_texts(record["human_approvers"], "human_approvers")
        return {
            "declarer": _declared_login(
                record["declarer"], "declarer", (_LOGIN, _BOT_LOGIN)
            ),
            "human_approvers": [
                _declared_login(login, "human approver", (_LOGIN,))
                for login in approvers
            ],
        }
    except AssuranceCompletenessError as exc:
        raise MergeEvidenceError(str(exc)) from exc


def load_authorities(path: Path, *, project_root: Path) -> dict[str, Any]:
    resolved = confine(
        path, project_root, label=_AUTHORITIES_LABEL, error=MergeEvidenceError
    )
    try:
        document = load_policy_yaml(resolved, label="Merge authorities")
    except KnowledgeFormatError as exc:
        raise MergeEvidenceError(str(exc)) from exc
    return parse_authorities(document)


def _is_directories_segment(text: str, index: int) -> bool:
    """Whether a leading or middle `**/` starts at `index`: gitignore's any
    directories. Anywhere else consecutive asterisks are ordinary ones (Codex on
    #413); a trailing `/**` needs no case, since the rule's directory suffix
    already matches everything inside."""

    return text.startswith("**/", index) and text[index - 1 : index] in ("", "/")


def parse_required_checks(document: object) -> dict[str, dict[str, str]]:
    """The manifest naming, for each declared requirement's coverage item, the
    GitHub check run that gives it: requirement, then item, then the L1 check key
    `github-check-run:<app_id>:<name>` (#407, slice 1b.3b-1). No two items, within
    or across requirements, name one check, so one run cannot satisfy two
    declared checks (#15, 6099845892)."""

    try:
        record = _declaration(document, _REQUIRED_CHECKS_LABEL, "requirements")
        requirements = require_mapping(record["requirements"], "required checks")
        if not requirements:
            raise MergeEvidenceError("required checks names no requirement")
        manifest: dict[str, dict[str, str]] = {}
        named: dict[str, str] = {}
        for requirement, raw_items in requirements.items():
            label = f"required checks {requirement!r}"
            require_identifier(requirement, "required checks requirement")
            items = require_mapping(raw_items, label)
            if not items:
                raise MergeEvidenceError(f"{label} names no item")
            manifest[requirement] = {
                require_identifier(item, f"{label} item"): _check_key(
                    check, f"{label} item {item!r}"
                )
                for item, check in items.items()
            }
            for item, key in manifest[requirement].items():
                pair = f"{requirement}.{item}"
                if key in named:
                    raise MergeEvidenceError(
                        f"required checks {named[key]} and {pair} both name {key}"
                    )
                named[key] = pair
        return manifest
    except AssuranceCompletenessError as exc:
        raise MergeEvidenceError(str(exc)) from exc


def _declaration(document: object, label: str, field: str) -> Mapping[str, Any]:
    """A declaration in the convention the required-check manifest set: version
    1.0 of a closed mapping with its id, its version and one named field."""

    record = require_mapping(document, label)
    require_closed_keys(record, label, _DECLARATION_KEYS | {field})
    if record["schema_version"] != "1.0":
        raise MergeEvidenceError(f"{label} schema_version must be 1.0")
    require_text(record["id"], f"{label} id")
    require_text(record["version"], f"{label} version")
    return record


def parse_suppression_markers(document: object) -> tuple[str, ...]:
    """The literal markers whose occurrence in an added line is a suppression
    (#407, slice 1b.3b-4): case-sensitive, and matched as written."""

    try:
        record = _declaration(document, _MARKERS_LABEL, "markers")
        return tuple(
            require_unique_texts(record["markers"], f"{_MARKERS_LABEL} markers")
        )
    except AssuranceCompletenessError as exc:
        raise MergeEvidenceError(str(exc)) from exc


class TrustRoots(NamedTuple):
    """The protected target's trust-root patterns, in CODEOWNERS syntax."""

    rules: tuple[re.Pattern[str], ...]

    def matches(self, path: str) -> bool:
        return any(rule.fullmatch(path) for rule in self.rules)


def parse_trust_roots(document: object) -> TrustRoots:
    """The paths whose change is shown for the owner's approval (M15), each
    pattern compiled by the CODEOWNERS matcher, which refuses what it cannot
    match as GitHub does (#407, slice 1b.3b-4)."""

    try:
        record = _declaration(document, _ROOTS_LABEL, "patterns")
        patterns = require_unique_texts(record["patterns"], f"{_ROOTS_LABEL} patterns")
    except AssuranceCompletenessError as exc:
        raise MergeEvidenceError(str(exc)) from exc
    return TrustRoots(tuple(_rule(pattern) for pattern in patterns))


def _check_key(value: object, label: str) -> str:
    check = require_mapping(value, label)
    require_closed_keys(check, label, _CHECK_KEYS)
    app_id = check["app_id"]
    if type(app_id) is not int or app_id <= 0:
        raise MergeEvidenceError(f"{label} app_id must be a positive integer")
    return f"github-check-run:{app_id}:{require_text(check['name'], f'{label} name')}"


def load_required_checks(
    path: Path, *, project_root: Path
) -> dict[str, dict[str, str]]:
    resolved = confine(
        path, project_root, label=_REQUIRED_CHECKS_LABEL, error=MergeEvidenceError
    )
    try:
        document = load_policy_yaml(resolved, label="Required checks")
    except KnowledgeFormatError as exc:
        raise MergeEvidenceError(str(exc)) from exc
    return parse_required_checks(document)


def _load_declaration(path: Path, project_root: Path, label: str) -> object | None:
    """A declaration's document, or None when the protected target has none: then
    what it governs is UNAVAILABLE, as on the target that introduces it (the
    bootstrap, #325 6112833932)."""

    resolved = confine(path, project_root, label=label, error=MergeEvidenceError)
    if not resolved.exists():
        return None
    try:
        return load_policy_yaml(resolved, label=label.capitalize())
    except KnowledgeFormatError as exc:
        raise MergeEvidenceError(str(exc)) from exc


def load_suppression_markers(
    path: Path, *, project_root: Path
) -> tuple[str, ...] | None:
    document = _load_declaration(path, project_root, _MARKERS_LABEL)
    return None if document is None else parse_suppression_markers(document)


def load_trust_roots(path: Path, *, project_root: Path) -> TrustRoots | None:
    document = _load_declaration(path, project_root, _ROOTS_LABEL)
    return None if document is None else parse_trust_roots(document)


def _check_status(states: set[tuple[str, str, str | None]]) -> tuple[str, str | None]:
    """A check's receipt status from its latest states. Only a run that completed
    successfully is COMPLETE; a skipped or neutral one did not run, so it is not
    evidence (I10)."""

    if len(states) != 1:
        return "PARTIAL", None
    ((_, status, conclusion),) = states
    if status != "completed":
        return "INCOMPLETE", conclusion
    if conclusion == "success":
        return "COMPLETE", conclusion
    if conclusion in ("skipped", "neutral"):
        return "SKIPPED", conclusion
    return "INCOMPLETE", conclusion


def _item_status(
    states: set[tuple[str, str, str | None]],
    runs: Sequence[tuple[str, str | None]],
) -> tuple[str, str | None]:
    """The latest state decides, unless several runs share the key and any of
    them did not succeed: then PARTIAL. This is the owner's choice under #402's
    stop rule, recorded on #407 (6097259307, 6097251980)."""

    if len(runs) > 1 and any(run != ("completed", "success") for run in runs):
        return "PARTIAL", None
    return _check_status(states)


def _check_receipts(
    snapshot: Mapping[str, Any],
    subject: Mapping[str, Any],
    required_checks: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    """One receipt per manifest item with a check run on the exact head. An item
    with none gets no receipt, so the reducer makes it MISSING. A checks read that
    is not COMPLETE, commit statuses included, gives every item its status: it can
    only deny (#407, 6097059408). With several runs of one key, as when two check
    suites post the same name, the item is COMPLETE only if every run succeeded,
    so a later success cannot hide another current run (Codex on #415)."""

    checks, coverage = _source(snapshot, "checks")
    # The reconciler normalizes each check; a malformed one is an invalid snapshot
    # (#15, 6100292562).
    try:
        latest = latest_checks(checks, subject["head_commit"])
        runs = check_runs_by_key(checks, subject["head_commit"])
    except ReconciliationInputError as exc:
        raise MergeEvidenceError(f"the snapshot is invalid: {exc}") from exc
    receipts = []
    for requirement, items in required_checks.items():
        for item, key in items.items():
            if coverage != "COMPLETE":
                status = coverage if coverage in RECEIPT_STATUSES else "ERROR"
                conclusion, observed_at = None, snapshot["observed_at"]
            elif key in latest:
                status, conclusion = _item_status(latest[key]["states"], runs[key])
                observed_at = latest[key]["observed_at"]
            else:
                continue
            receipts.append(
                {
                    "schema": RECEIPT_SCHEMA,
                    "requirement": requirement,
                    "subject": subject_of(subject),
                    "producer": _CHECK_PRODUCER,
                    "observed_at": observed_at,
                    "status": status,
                    "coverage": [item],
                    "provenance": {"check": key, "conclusion": conclusion},
                }
            )
    return receipts


def _glob(text: str) -> str:
    pattern, index = "", 0
    while index < len(text):
        if _is_directories_segment(text, index):
            pattern += "(?:.*/)?"
            index += 3
        elif text[index] == "*":
            pattern += "[^/]*"
            index += 1
        elif text[index] == "?":
            pattern += "[^/]"
            index += 1
        else:
            pattern += re.escape(text[index])
            index += 1
    return pattern


def _documented_wildcards(segments: Sequence[str]) -> bool:
    """Whether every wildcard is in one of GitHub's documented forms: `*` alone
    or as the last segment, `*.ext` as the only segment, and `**` as a leading
    or middle segment. `docs/guides*` gave a nested file to its owner, which
    GitHub does not document (Codex on #413; the owner's choice, #407 6095614968)."""

    last = len(segments) - 1
    for position, segment in enumerate(segments):
        if not any(c in segment for c in "*?"):
            continue
        if segment == "**" and position < last:
            continue
        if segment == "*" and position == last:
            continue
        if last == 0 and _EXTENSION.fullmatch(segment):
            continue
        return False
    return True


def _rule(pattern: str) -> re.Pattern[str]:
    """One CODEOWNERS pattern, as GitHub documents it: gitignore's rules, without
    `!`, `[ ]` and `\\` escapes, which are refused rather than skipped."""

    if pattern.startswith("!") or any(c in pattern for c in "[]\\"):
        raise MergeEvidenceError(f"CODEOWNERS pattern {pattern!r} is not supported")
    directory = pattern.endswith("/")
    body = pattern.removeprefix("/").removesuffix("/")
    # git matches nothing for an empty or dot segment, and stripping every
    # boundary slash read `//sensitive` as `/sensitive` (Codex on #413; the
    # owner's choice, #407 6092909419).
    if any(segment in ("", ".", "..") for segment in body.split("/")):
        raise MergeEvidenceError(
            f"CODEOWNERS pattern {pattern!r} has an empty or dot segment"
        )
    if not _documented_wildcards(body.split("/")):
        raise MergeEvidenceError(
            f"CODEOWNERS pattern {pattern!r} uses a wildcard GitHub does not document"
        )
    # A slash at the start or in the middle anchors the pattern at the root.
    anchored = pattern.startswith("/") or "/" in body
    prefix = "" if anchored else "(?:.*/)?"
    if directory:
        suffix = "/.*"
    elif body.endswith("/*"):
        # GitHub: `docs/*` owns the files in docs, not its subdirectories.
        suffix = ""
    else:
        suffix = "(?:/.*)?"
    # A newline is an ordinary character of a Git file name (Codex on #423).
    return re.compile(prefix + _glob(body) + suffix, re.DOTALL)


class CodeOwners:
    """A parsed CODEOWNERS file: the last matching rule decides a path's owners."""

    def __init__(self, rules: Sequence[tuple[re.Pattern[str], list[str]]]) -> None:
        self._rules = list(rules)

    def owners(self, path: str) -> list[str] | None:
        """The owners of `path`, `[]` for an ownerless rule, `None` with no rule."""

        found: list[str] | None = None
        for pattern, owners in self._rules:
            if pattern.fullmatch(path):
                found = owners
        return None if found is None else list(found)


def parse_codeowners(text: str) -> CodeOwners:
    rules = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pattern, *words = stripped.split()
        # An inline comment ends the owners, as GitHub documents (Codex on #413).
        comment = next((i for i, w in enumerate(words) if w.startswith("#")), None)
        owners = words[:comment]
        for owner in owners:
            if _OWNER.fullmatch(owner) is None:
                raise MergeEvidenceError(
                    f"CODEOWNERS line {number}: {owner!r} is not an owner"
                )
        rules.append((_rule(pattern), owners))
    return CodeOwners(rules)


def load_codeowners(project_root: Path) -> CodeOwners:
    """The protected target's CODEOWNERS, found where GitHub looks for it."""

    for location in CODEOWNERS_LOCATIONS:
        candidate = project_root / location
        if not candidate.is_file():
            continue
        resolved = confine(
            candidate, project_root, label="CODEOWNERS", error=MergeEvidenceError
        )
        with resolved.open("rb") as handle:
            raw = handle.read(CODEOWNERS_LIMIT)
        if len(raw) >= CODEOWNERS_LIMIT:
            raise MergeEvidenceError("CODEOWNERS is not under GitHub's 3 MB limit")
        try:
            return parse_codeowners(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise MergeEvidenceError(f"CODEOWNERS is not UTF-8: {exc}") from exc
    return CodeOwners([])


def _names(item: Mapping[str, Any]) -> list[str]:
    """Every name a changed file has, its old one included, in order, so a failed
    run names the same path each time (Claude on #413)."""

    if item["status"] == "renamed" and not item.get("previous_path"):
        # The old location would be skipped (CodeAnt on #413).
        raise MergeEvidenceError(f"the rename to {item['path']} has no previous path")
    return sorted({item["path"], item.get("previous_path")} - {None})


# The file statuses whose names say what changed (#325 6112833932); any other
# leaves the trust-root changes unproven.
_TRUST_ROOT_STATUSES = frozenset({"added", "modified", "removed", "renamed"})


def _trust_root_changes(
    files: Sequence[Mapping[str, Any]], roots: TrustRoots | None
) -> dict[str, Any]:
    """M15: each changed file with a name under a trust root, under every name it
    has, so a rename into or out of a root shows both sides."""

    if roots is None:
        return {"coverage": "UNAVAILABLE", "paths": []}
    paths: set[str] = set()
    complete = True
    for item in files:
        if item["status"] not in _TRUST_ROOT_STATUSES:
            complete = False
            continue
        names = _names(item)
        if any(roots.matches(name) for name in names):
            paths.update(names)
    return {"coverage": "COMPLETE" if complete else "PARTIAL", "paths": sorted(paths)}


# Git's id for an empty blob: a file whose head blob it is holds no line at all.
_EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"  # pragma: allowlist secret -- Git's empty-blob id
# A hunk header in Git's range form. What follows the closing `@@` is the hunk's
# context, accepted and never read (the owner's selection, #407 6113448747).
_HUNK_HEADER = re.compile(
    r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?", re.ASCII
)
_NO_NEWLINE = "\\ No newline at end of file"
_CONTENT = frozenset(" -+")
# What each content line takes from a hunk's old and new counts.
_STEPS = {" ": (1, 1), "-": (1, 0), "+": (0, 1)}


def _hunk_header(text: str) -> tuple[int, int, int] | None:
    """A hunk header's old count, new count and first head line, or None."""

    header = _HUNK_HEADER.fullmatch(text)
    if header is None:
        return None
    try:
        old = 1 if header.group(2) is None else int(header.group(2))
        new = 1 if header.group(4) is None else int(header.group(4))
        line = int(header.group(3))
    except ValueError:  # a number too long to convert
        return None
    if new and line < 1:
        return None
    return old, new, line


def _hunk_body(
    lines: Sequence[str],
    index: int,
    counts: tuple[int, int, int],
    added: list[tuple[int, str]],
) -> int | None:
    """Account for one hunk's lines from `index`, exactly as its header counts
    them, and add each added line to `added` with its head-line number. The
    index after the hunk, or None when its lines do not fit its counts."""

    old, new, line = counts
    previous = ""
    while old or new or (index < len(lines) and lines[index] == _NO_NEWLINE):
        if index == len(lines):
            return None
        text = lines[index]
        index += 1
        if text == _NO_NEWLINE:
            # Metadata about the line before it, so only after a content line.
            if previous not in _CONTENT:
                return None
            previous = "\\"
            continue
        kind = text[:1]
        taken = _STEPS.get(kind)
        if taken is None or old < taken[0] or new < taken[1]:
            return None
        old, new = old - taken[0], new - taken[1]
        if kind == "+":
            added.append((line, text[1:]))
        line += taken[1]
        previous = kind
    return index


def _added_lines(patch: str) -> tuple[list[tuple[int, str]], int] | None:
    """Each line a file's patch adds, with its head-line number, and how many
    head-side lines its hunks hold, context included; or None unless the patch
    is exactly a sequence of hunks: every line accounted for by its header's
    counts, and only the exact no-newline annotation besides."""

    lines = patch.split("\n")
    if len(lines) > 1 and lines[-1] == "":
        # Git ends every line with a newline, the last one included (cubic and
        # CodeAnt on #423); a second would be a blank line no hunk counts.
        lines.pop()
    added: list[tuple[int, str]] = []
    head = index = 0
    while index < len(lines):
        counts = _hunk_header(lines[index])
        if counts is None:
            return None
        after = _hunk_body(lines, index + 1, counts, added)
        if after is None:
            return None
        head += counts[1]
        index = after
    return added, head


def _file_additions(item: Mapping[str, Any]) -> list[tuple[int, str]] | None:
    """The lines one changed file adds, or None when the comparison does not show
    them completely. A file without hunks adds nothing only when it is a removal
    or its head blob is empty, and nothing contradicts that (A-2, #407
    6113448747); zero additions alone proves nothing, since a binary has them.
    Such a file keeps no head-side line either, a context line included (the PAO
    on #423, 6113955118)."""

    additions = item.get("additions")
    if type(additions) is not int or item.get("patch_truncated") is not False:
        return None
    empty = item["status"] == "removed" or item.get("blob") == _EMPTY_BLOB
    patch = item.get("patch")
    if patch is None:
        return [] if empty and additions == 0 else None
    read = _added_lines(patch)
    if read is None:
        return None
    added, head = read
    if len(added) != additions or (empty and head):
        return None
    return added


# M13's resource budgets per comparison (the coordinator on #423, 6114751092):
# a reason is the rest of its line, so a line packed with markers grows
# quadratically. Past either budget the list keeps what it holds and is PARTIAL.
_MAX_SUPPRESSIONS = 1_000
_MAX_SUPPRESSION_BYTES = 1_048_576
# Records sit three levels deep in the evidence document, which the command
# writes with `indent=2`, so each line of a record carries six more spaces. Each
# record is also charged six bytes for its separator and a share of the list's
# own framing: N records take 2(N-1) + 6 bytes of it, never more than 6N.
_RECORD_INDENT = 6
_RECORD_FRAMING = 6


def _record_bytes(record: Mapping[str, Any]) -> int:
    """An upper bound on a record's size as the command writes it:
    `json.dumps(indent=2, sort_keys=True)`, which escapes all but ASCII, at its
    depth in the document, with its share of the list's separators and framing."""

    rendered = json.dumps(record, indent=2, sort_keys=True)
    lines = rendered.count("\n") + 1
    return len(rendered.encode("utf-8")) + _RECORD_INDENT * lines + _RECORD_FRAMING


def _hits(text: str, order: int, marker: str) -> Iterator[tuple[int, int, str]]:
    """Each position of one marker in a line, with the marker's declared order,
    which breaks a tie between markers at one position."""

    start = text.find(marker)
    while start != -1:
        yield start, order, marker
        start = text.find(marker, start + 1)


def _occurrences(
    path: str, line: int, text: str, markers: Sequence[str]
) -> Iterator[dict[str, Any]]:
    """Every occurrence of a marker in one added line, in reading order, one at a
    time, so nothing past the budget is built. Its reason is what follows the
    first `--` after it on the line, kept as written; only whether it is blank
    is judged (cubic on #423)."""

    hits = heapq.merge(
        *(_hits(text, order, marker) for order, marker in enumerate(markers))
    )
    for start, _, marker in hits:
        delimiter = text.find("--", start + len(marker))
        reason = "" if delimiter == -1 else text[delimiter + 2 :]
        yield {
            "path": path,
            "line": line,
            "marker": marker,
            "justified": bool(reason.strip()),
            "reason": reason,
        }


def _suppressions(
    files: Sequence[Mapping[str, Any]], markers: Sequence[str] | None
) -> dict[str, Any]:
    """M13: each declared marker in a line the comparison adds. A file whose added
    lines it does not show completely leaves the list PARTIAL, and so does
    reaching either budget, before the record that would pass it."""

    if markers is None:
        return {"coverage": "UNAVAILABLE", "found": []}
    found: list[dict[str, Any]] = []
    size = 0
    complete = True
    for item in files:
        added = _file_additions(item)
        if added is None:
            complete = False
            continue
        for line, text in added:
            for record in _occurrences(item["path"], line, text, markers):
                cost = _record_bytes(record)
                if (
                    len(found) == _MAX_SUPPRESSIONS
                    or size + cost > _MAX_SUPPRESSION_BYTES
                ):
                    return {"coverage": "PARTIAL", "found": found}
                found.append(record)
                size += cost
    return {"coverage": "COMPLETE" if complete else "PARTIAL", "found": found}


def _required_approvers(
    files: Sequence[Mapping[str, Any]], codeowners: CodeOwners, roster: Sequence[str]
) -> list[str]:
    """The roster's people among each changed file's code owners. A file whose rule
    names owners, none of whom is on the roster, cannot be approved by anyone the
    verdict can recognize, so the run fails."""

    required: set[str] = set()
    for item in files:
        for path in _names(item):
            owners = codeowners.owners(path)
            if not owners:
                continue
            people = {
                login_key(o[1:]) for o in owners if o.startswith("@") and "/" not in o
            }
            on_roster = people & {login_key(r) for r in roster}
            if not on_roster:
                raise MergeEvidenceError(
                    f"no code owner of {path} is on the human approvers' roster"
                )
            required |= on_roster
    return sorted(required)


def _seal(
    conversation: Sequence[Mapping[str, Any]], declarer: str
) -> dict[str, Any] | None:
    seals = []
    for comment in conversation:
        edited = comment.get("edited")
        if not isinstance(edited, bool):
            raise MergeEvidenceError(
                "the snapshot was not collected with merge evidence: comment edits"
            )
        if (
            login_key(comment["author"]) != login_key(declarer)
            or edited
            or comment["created_at"] != comment["updated_at"]
        ):
            continue
        match = _SEAL.fullmatch(comment["body"].split("\n", 1)[0].rstrip("\r"))
        if match:
            seals.append(
                (parse_rfc3339(comment["created_at"]), comment["id"], match.group(1))
            )
    if not seals:
        return None
    return {"declarer": login_key(declarer), "head_commit": max(seals)[2]}


def _closing_references(
    subject: Mapping[str, Any],
    commits: Sequence[Mapping[str, Any]],
    commit_coverage: str,
    closing: tuple[Sequence[Mapping[str, Any]], str],
) -> dict[str, Any]:
    """GitHub's closing keywords in the title, the body and every commit message,
    and the issues the provider lists as closed by the merge, keyword-linked or
    linked by hand (Codex on #413; #407, 6086122133). The coverage is COMPLETE
    only when every source is."""

    title = subject.get("title")
    surfaces = [
        ("title", title if isinstance(title, str) else ""),
        ("body", subject["body"]),
    ]
    surfaces += [(f"commit {c['sha']}", c["message"]) for c in commits]
    found = [
        {"surface": surface, "reference": match.group(2)}
        for surface, text in surfaces
        for match in _CLOSING.finditer(text)
    ]
    issues, issue_coverage = closing
    found += [
        {
            "surface": "github.closingIssuesReferences",
            "reference": f"{issue['repository']}#{issue['number']}",
        }
        for issue in issues
    ]
    if commit_coverage != "COMPLETE":
        coverage = commit_coverage
    elif issue_coverage != "COMPLETE":
        coverage = issue_coverage
    elif not isinstance(title, str):
        # L1 had no title, so its keywords were not read (CodeAnt on #413).
        coverage = "PARTIAL"
    elif any(c["message_truncated"] for c in commits):
        coverage = "PARTIAL"
    else:
        coverage = "COMPLETE"
    return {"coverage": coverage, "found": found}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def load_decisions(project_root: Path) -> dict[str, frozenset[str]]:
    """The protected target's Decision records: each id's record file names. Each
    record must lie inside the protected target, and a missing directory fails the
    run (cubic on #413). A link to a Decision must name one of its records
    (1b.3b-3)."""

    root = project_root.resolve()
    candidate = project_root / DECISIONS_DIRECTORY
    if not candidate.is_dir():
        raise MergeEvidenceError(
            f"the protected target has no {DECISIONS_DIRECTORY} directory"
        )
    directory = confine(
        candidate, project_root, label="decision records", error=MergeEvidenceError
    )
    records: dict[str, set[str]] = {}
    for entry in directory.iterdir():
        if (
            (match := _DECISION_RECORD.fullmatch(entry.name))
            and entry.is_file()
            and entry.resolve().is_relative_to(root)
        ):
            records.setdefault(match.group(1), set()).add(entry.name)
    return {identifier: frozenset(names) for identifier, names in records.items()}


def _visible(child: Token) -> str | None:
    """What one inline token shows: its text and inline code, a line break as a
    space, and nothing else."""

    if child.type in ("text", "code_inline"):
        return child.content
    if child.type in ("softbreak", "hardbreak"):
        return " "
    return None


def _inline_value(token: Token) -> str:
    """An item's visible value: its text and inline code. A link's target is not
    visible, so it is never read for identifiers (Codex on #413; the owner's
    re-slice decision, #407 6085478125), and inline HTML, comments included, is
    not part of it."""

    return "".join(part for child in token.children or [] if (part := _visible(child)))


class _Link(NamedTuple):
    """A link of a Change control item: its visible label, read as `_inline_value`
    reads the item, and its target. The label `touches` an identifier when it
    holds an identifier character, and it is `whole` when, in the item's visible
    text, no identifier character comes right before or after its text trimmed
    of spaces (the PAO advisory on #422)."""

    label: str
    target: str
    touches: bool
    whole: bool


# What continues an identifier in visible text: `#407` is one token, not `#4`
# and `07`.
_IDENTIFIER_CHARACTERS = frozenset("#0123456789")


def _links(token: Token) -> tuple[_Link, ...]:
    """Each link of an item, with its label's place in the item's visible text,
    the string `_inline_value` builds. A zero-width link, a comment or a code span
    therefore cannot separate a label from the digits a reader sees next to it
    (cubic and Codex on #422). The target is only checked against the label's
    identifier, never read for one (1b.3b-3, #407 6085544477)."""

    visible = ""
    spans: list[tuple[int, int, str]] = []
    start: int | None = None
    target = ""
    for child in token.children or []:
        if child.type == "link_open":
            start, target = len(visible), str(child.attrGet("href") or "")
        elif child.type == "link_close" and start is not None:
            spans.append((start, len(visible), target))
            start = None
        elif part := _visible(child):
            visible += part
    links: list[_Link] = []
    for begin, end, target in spans:
        label = visible[begin:end]
        first = begin + len(label) - len(label.lstrip(" "))
        last = end - (len(label) - len(label.rstrip(" ")))
        neighbours = (visible[first - 1 : first], visible[last : last + 1])
        bordered = any(n and n in _IDENTIFIER_CHARACTERS for n in neighbours)
        touches = any(c in _IDENTIFIER_CHARACTERS for c in label)
        links.append(_Link(label, target, touches, not bordered))
    return tuple(links)


class _Field(NamedTuple):
    """A Change control field's visible value, and the links its item holds."""

    value: str
    links: tuple[_Link, ...]


class _ContainerTags(HTMLParser):
    """Whether raw HTML holds a tag of an element that can hold content: any
    element but a void one. GitHub may render Markdown inside such an element,
    for example a collapsed `<details>`, and HTML5 nesting, which closes and
    reopens elements, is not modelled, so any such tag is refused (Codex on #413;
    the owner's choice, #407 6086999580). Comments are not tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found = False

    # `HTMLParser` reports `<details/>` here too, as HTML parses it.
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.found = self.found or tag not in _VOID_ELEMENTS

    def handle_endtag(self, tag: str) -> None:
        self.handle_starttag(tag, [])


def _holds_container_tag(tokens: Sequence[Token]) -> bool:
    """Whether any raw HTML among the tokens, block or inline, holds such a
    tag."""

    tags = _ContainerTags()
    for token in tokens:
        if token.type == "html_block":
            tags.feed(token.content)
        for child in token.children or []:
            if child.type == "html_inline":
                tags.feed(child.content)
    tags.close()
    return tags.found


def _is_top_heading(token: Token, tags: tuple[str, ...]) -> bool:
    return token.type == "heading_open" and token.level == 0 and token.tag in tags


def _section_start(tokens: Sequence[Token]) -> int:
    """The index of the one top-level `## Change control` heading."""

    starts = [
        index
        for index, token in enumerate(tokens)
        if _is_top_heading(token, ("h2",))
        # Its visible text: inline HTML in a heading is not part of it (cubic on
        # #413).
        and _inline_value(tokens[index + 1]).strip() == "Change control"
    ]
    if not starts:
        raise MergeEvidenceError("the description has no Change control section")
    if len(starts) > 1:
        raise MergeEvidenceError(
            "the description has more than one Change control section"
        )
    return starts[0]


def _section_end(tokens: Sequence[Token], start: int) -> int:
    """The index of the next top-level h1 or h2, or the description's end."""

    return next(
        (
            index
            for index in range(start + 3, len(tokens))
            if _is_top_heading(tokens[index], ("h1", "h2"))
        ),
        len(tokens),
    )


def _section_items(tokens: Sequence[Token], start: int, end: int) -> Iterator[Token]:
    """Each top-level list item's field: the inline token of its first block. A
    continuation paragraph is not a field (Codex on #413; #407, 6085825905), and
    an item whose first block is not a paragraph has none, so it fails the run
    in a closed section (#407, 6092909419)."""

    in_list = False
    for index in range(start + 3, end):
        token = tokens[index]
        if token.type == "ordered_list_open" and token.level == 0:
            # Its items are top-level items too, and the template's fields are
            # bullet items (cubic and Codex on #413; #407, 6092909419).
            raise MergeEvidenceError("the Change control section holds an ordered list")
        if token.type in ("bullet_list_open", "bullet_list_close") and token.level == 0:
            in_list = token.type == "bullet_list_open"
        elif in_list and token.type == "list_item_open" and token.level == 1:
            if tokens[index + 1].type != "paragraph_open":
                raise MergeEvidenceError(
                    "a Change control item does not open with one of the "
                    "template's fields"
                )
            yield tokens[index + 2]


def _change_control_fields(body: str) -> dict[str, _Field]:
    """The fields of the description's one top-level `## Change control` section:
    the items of its top-level bullet lists, up to the next top-level h1 or h2.
    Raw HTML that can hold content anywhere before the section's end fails the
    run."""

    tokens = _MARKDOWN.parse(body)
    start = _section_start(tokens)
    end = _section_end(tokens, start)
    if _holds_container_tag(tokens[:end]):
        raise MergeEvidenceError(
            "raw HTML that can hold content precedes the end of the Change "
            "control section"
        )
    fields: dict[str, _Field] = {}
    for token in _section_items(tokens, start, end):
        if any(
            child.type == "html_inline" and not child.content.startswith("<!--")
            for child in token.children or []
        ):
            # How a void element renders differs, `<wbr>` joining and `<br>`
            # breaking, so a candidate holding one is refused before it is read,
            # label included (cubic and Codex on #413; the owner's choice, #407
            # 6087507517 and 6087484196). A comment renders as nothing, so the
            # text around it joins.
            raise MergeEvidenceError("a Change control item holds raw HTML")
        if any(child.type == "image" for child in token.children or []):
            # An image's alt text is a label the visible value does not show, so
            # it could hide an identifier from the link check (Codex on #422).
            raise MergeEvidenceError("a Change control item holds an image")
        match = _FIELD.fullmatch(_inline_value(token).strip(" \t"))
        if match is None:
            raise MergeEvidenceError(
                "a Change control item is not one of the template's fields"
            )
        if match.group(1) in fields:
            raise MergeEvidenceError(
                f"the Change control section repeats {match.group(1)}"
            )
        fields[match.group(1)] = _Field(match.group(2), _links(token))
    return fields


def _listed(
    fields: Mapping[str, _Field], name: str, grammar: re.Pattern[str]
) -> list[str]:
    """The numbers a field lists, in order. An empty field lists nothing; a value
    that is not the field's grammar fails the run."""

    # Only ASCII spaces pad a value: a Unicode space is not erased.
    value = fields[name].value.strip(" ") if name in fields else ""
    if value and grammar.fullmatch(value) is None:
        raise MergeEvidenceError(f"the {name} field is not a list the template allows")
    return _unique(_NUMBER.findall(value))


def work_item_numbers(body: str) -> list[int]:
    """The Work Items a description's Change control section lists, in order and
    once each: what L1 reads for this adapter (1b.3b-3), from the same section,
    field and grammar. A section this adapter would refuse fails here too."""

    return _work_item_values(_change_control_fields(body))


def _work_item_values(fields: Mapping[str, _Field]) -> list[int]:
    """The listed Work Items' numbers, once each by value: `#0407` is issue 407
    (cubic and CodeAnt on #422; the PAO advisory, 6110693561). A spelling too long
    to convert fails the run here, inside every caller's error path."""

    values: list[int] = []
    seen: set[int] = set()
    for spelling in _listed(fields, _WORK_ITEM_FIELD, _WORK_ITEM_VALUE):
        try:
            value = int(spelling)
        except ValueError as exc:
            raise MergeEvidenceError("a Work Item number is too long to read") from exc
        # A set, so the cost is linear in the field (cubic on #422).
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _linked_identifiers(
    field: _Field | None, label: re.Pattern[str], name: str
) -> list[tuple[str, str]]:
    """Each identifier a field carries by a link, with the link's target. A label
    with no identifier carries none, and one with any other text, several
    identifiers included, fails the run."""

    found: list[tuple[str, str]] = []
    for link in field.links if field else ():
        # A label with no identifier character lists none, wherever it sits (#407
        # 6085478125); one with any must be exactly one whole identifier, trimmed
        # of spaces (CodeAnt, cubic and the PAO advisory on #422).
        if not link.touches:
            continue
        match = label.fullmatch(link.label.strip(" "))
        if match is None:
            raise MergeEvidenceError(f"a {name} link must carry one identifier")
        if not link.whole:
            # `[#4](…/issues/4)07` shows `#407` (Codex and cubic on #422).
            raise MergeEvidenceError(f"a {name} link must cover its whole identifier")
        found.append((match.group(1), link.target))
    return found


def _same_number(target: str, label: str) -> bool:
    """Whether two spellings name one issue number; a spelling too long to
    convert names none."""

    try:
        return int(target) == int(label)
    except ValueError:
        return False


def _check_links(
    fields: Mapping[str, _Field],
    repository: str,
    decisions: Mapping[str, frozenset[str]],
) -> None:
    """A Work Item or Decision a link carries is linked to its own issue or record
    (1b.3b-3, #407 6108453639): a Work Item to `https://github.com/<subject>/issues/
    <number>`, a Decision to `knowledge/decisions/<one of its protected records>`.
    Any other target fails the run; nothing is fetched."""

    for number, target in _linked_identifiers(
        fields.get(_WORK_ITEM_FIELD), _WORK_ITEM_LABEL, _WORK_ITEM_FIELD
    ):
        rest = target[len(repository) :] if target.startswith(repository) else ""
        issue = _ISSUE_TARGET.fullmatch(rest)
        if issue is None or not _same_number(issue.group(1), number):
            raise MergeEvidenceError(
                f"the link for Work Item #{number} does not point to its issue"
            )
    for identifier, target in _linked_identifiers(
        fields.get("Decision"), _DECISION_LABEL, "Decision"
    ):
        records = decisions.get(identifier, frozenset())
        if target not in {f"{DECISIONS_DIRECTORY.as_posix()}/{r}" for r in records}:
            raise MergeEvidenceError(
                f"the link for Decision {identifier} does not point to its record"
            )


def _change_control(
    body: str, decisions: Mapping[str, frozenset[str]], repository: str
) -> tuple[str, dict[str, list[str]]]:
    """The class, Work Items and Decisions from the change-request template's
    `## Change control` section (owner decision 3, #407). Examples in code blocks
    and comments are not fields, a Decision counts only when the protected target
    has its record, and a linked one only when its link is its own (1b.3b-3)."""

    fields = _change_control_fields(body)
    change_class = fields["Class"].value.strip() if "Class" in fields else ""
    if change_class not in CHANGE_CLASSES:
        raise MergeEvidenceError(f"the change class {change_class!r} is not a class")
    work_items = [f"#{n}" for n in _work_item_values(fields)]
    linked = _listed(fields, "Decision", _DECISION_VALUE)
    _check_links(fields, repository, decisions)
    return change_class, {
        "work_items": work_items,
        "decisions": [d for d in linked if d in decisions],
    }


def _proven_work_items(
    snapshot: Mapping[str, Any], work_items: Sequence[str], repository: str
) -> None:
    """Every listed Work Item is an issue, not a pull request, of the subject
    repository, as L1 observed it in the snapshot's cut (1b.3b-3, #407
    6108453639). An incomplete read, a missing or extra observation, or any other
    answer fails the run and names the Work Item, so none is silently dropped."""

    observed = [_observation(item) for item in _complete(snapshot, "work_items")]
    listed = [int(item.removeprefix("#")) for item in work_items]
    if [number for number, _, _ in observed] != listed:
        raise MergeEvidenceError(
            "the observed Work Items are not the ones the description lists"
        )
    name = repository.removeprefix(_GITHUB)
    for number, kind, observed_repository in observed:
        if kind == "absent":
            raise MergeEvidenceError(f"Work Item #{number} does not exist in {name}")
        if kind == "pull_request":
            raise MergeEvidenceError(f"Work Item #{number} is a pull request")
        if observed_repository != name:
            raise MergeEvidenceError(f"Work Item #{number} is not an issue of {name}")


_OBSERVATION_KEYS = frozenset({"number", "repository", "kind"})
_OBSERVATION_KINDS = frozenset({"issue", "pull_request", "absent"})


def _observation(item: object) -> tuple[int, str, str]:
    """One Work Item observation, in L1's closed shape. `validate_snapshot` does
    not normalize this merge-evidence source, so `407.0` or `True` must not pass
    for a number (Codex on #422). The shape is checked with the same helpers as
    every closed evidence object (Claude on #422)."""

    label = "work_items observation"
    observation = require_mapping(item, label)
    require_closed_keys(observation, label, _OBSERVATION_KEYS)
    kind = require_text(observation["kind"], f"{label} kind")
    if kind not in _OBSERVATION_KINDS:
        raise MergeEvidenceError(f"{label} has the unknown kind {kind!r}")
    repository = require_text(observation["repository"], f"{label} repository")
    number = observation["number"]
    # As L1 writes them: a provider's answer has a positive number, and an absent
    # Work Item carries the listed one, so only it may be 0 (Codex on #422).
    lowest = 0 if kind == "absent" else 1
    if type(number) is not int or number < lowest:
        raise MergeEvidenceError(f"{label} has a number that is not one L1 records")
    return number, kind, repository


def _source(snapshot: Mapping[str, Any], name: str) -> tuple[list[dict[str, Any]], str]:
    coverage = require_mapping(snapshot.get("coverage"), "coverage")
    record = coverage.get(name)
    items = snapshot.get(name)
    if not isinstance(record, Mapping) or not isinstance(items, list):
        raise MergeEvidenceError(
            f"the snapshot was not collected with merge evidence: {name}"
        )
    if record.get("count") != len(items):
        raise MergeEvidenceError(f"coverage.{name}.count does not match its items")
    return items, str(record.get("status"))


def _complete(snapshot: Mapping[str, Any], name: str) -> list[dict[str, Any]]:
    items, status = _source(snapshot, name)
    if status != "COMPLETE":
        raise MergeEvidenceError(f"the {name} source is {status}, not COMPLETE")
    return items


def _reviews(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Raw reviews; the verdict owns the effective-review rule. The contract has no
    reviews coverage, so a read that may have missed a review fails the run."""

    items, status = _source(snapshot, "reviews")
    record = snapshot["coverage"]["reviews"]
    if status != "COMPLETE" and not (
        status == "PARTIAL"
        and record.get("reason") in _REVIEW_SEMANTIC_REASONS
        and "limit" not in record
        and "error" not in record
    ):
        raise MergeEvidenceError(
            f"the reviews source is {status}: {record.get('reason') or record.get('limit') or record.get('error')}"
        )
    return [
        {
            "reviewer": login_key(item["reviewer_id"]),
            "state": item["recommendation_state"],
            "commit_id": item["head_commit"],
            "submitted_at": item["observed_at"],
        }
        for item in items
    ]


def evidence_from_snapshot(
    snapshot: object,
    *,
    authorities: Mapping[str, Any],
    change_policy: Mapping[str, Any],
    codeowners: CodeOwners,
    decisions: Mapping[str, frozenset[str]],
    required_checks: Mapping[str, Mapping[str, str]],
    analyzer_readback: object = None,
    suppression_markers: Sequence[str] | None = None,
    trust_roots: TrustRoots | None = None,
) -> dict[str, Any]:
    """The evidence document for the pull request the snapshot observed, with the
    authenticated analyzer readback's bundle when one is given. Without the
    protected target's suppression markers or trust roots, what each governs is
    UNAVAILABLE."""

    document = require_mapping(snapshot, "snapshot")
    try:
        subject, _, coverage = validate_snapshot(dict(document))
    except ReconciliationInputError as exc:
        raise MergeEvidenceError(f"the snapshot is invalid: {exc}") from exc
    # GitHub evidence only from a GitHub snapshot (the owner's review 5478389359
    # on #413).
    if document["provider"]["id"] != "github":
        raise MergeEvidenceError("the snapshot's provider is not github")
    if coverage["subject"]["status"] != "COMPLETE":
        raise MergeEvidenceError("the subject source is not COMPLETE")
    provider = document["subject"]
    missing = [key for key in _MERGE_EVIDENCE_SUBJECT if key not in provider]
    if missing:
        raise MergeEvidenceError(
            f"the snapshot was not collected with merge evidence: {', '.join(missing)}"
        )
    if provider["author"] is None:
        raise MergeEvidenceError("the pull request's author is unavailable")
    integration = require_mapping(
        change_policy.get("integration"), "change policy integration"
    )
    if integration.get("protected_default_branch") is not True:
        raise MergeEvidenceError("the change policy protects no default branch")

    conversation = _complete(document, "conversation")
    files = _complete(document, "files")
    commits, commit_coverage = _source(document, "commits")
    threads = document["review_threads"]
    if provider["body_truncated"]:
        # A cut description may have lost part of its section (CodeAnt on #413).
        raise MergeEvidenceError("the pull request's description is truncated")
    repository = subject["repository"]
    if not repository.startswith(_GITHUB):
        raise MergeEvidenceError("the subject repository is not a GitHub repository")
    change_class, links = _change_control(provider["body"], decisions, repository)
    _proven_work_items(document, links["work_items"], repository)
    state = "merged" if provider["merged"] else provider["state"]
    analyzer_receipts, analyzer_findings = _analyzer_evidence(
        analyzer_readback, subject
    )
    return {
        "subject": subject_of(subject),
        "lifecycle": {
            "state": state,
            "draft": provider["draft"],
            "target": provider["target"],
            "protected_target": provider["default_branch"],
        },
        "change_class": change_class,
        "links": links,
        "declared_candidate": _seal(conversation, authorities["declarer"]),
        "authorities": {
            "declarer": login_key(authorities["declarer"]),
            "author": login_key(provider["author"]),
            "required_approvers": _required_approvers(
                files, codeowners, authorities["human_approvers"]
            ),
        },
        "reviews": _reviews(document),
        "threads": {
            "coverage": coverage["review_threads"]["status"],
            "unresolved": sum(1 for t in threads if t.get("state") != "resolved"),
        },
        "closing_references": _closing_references(
            provider, commits, commit_coverage, _source(document, "closing_issues")
        ),
        "suppressions": _suppressions(files, suppression_markers),
        "trust_root_changes": _trust_root_changes(files, trust_roots),
        "analyzer_findings": analyzer_findings,
        # The check items' receipts (1b.3b-1) and the analyzer items' (1b.3b-2);
        # SonarCloud's come with 1b.3c.
        "receipts": [
            *_check_receipts(document, subject, required_checks),
            *analyzer_receipts,
        ],
    }


def _analyzer_receipt(
    subject: Mapping[str, Any],
    item: str,
    status: str,
    observed_at: str,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "requirement": _ANALYZER_REQUIREMENT,
        "subject": subject_of(subject),
        "producer": _ANALYZER_PRODUCER,
        "observed_at": observed_at,
        "status": status,
        "coverage": [item],
        "provenance": dict(provenance),
    }


def _bound_to(bundle: Mapping[str, Any], subject: Mapping[str, Any]) -> bool:
    return bool(
        bundle["subject_binding"] == "BOUND"
        and subject["repository"] == f"https://github.com/{bundle['repository']}"
        # The pull number names a pull request (cubic on #417).
        and subject["change_request"]["kind"] == "github-pull-request"
        and subject["change_request"]["id"] == str(bundle["pull_number"])
        and subject["head_commit"] == bundle["requested_head"]
    )


def _analyzer_evidence(
    value: object, subject: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """The analyzer items' receipts and the findings, from the authenticated
    readback's bundle (1b.3b-2; the owner's rule, #407 6096770145).

    A bundle bound to the exact subject gives each item the receipt of its
    readback's own coverage, whatever its findings: they stay explicit, every one
    unresolved, for M17. A bundle that is not gives every item `INCOMPLETE`; a
    readback that is missing gives its item none, so the reducer reports it
    `MISSING`. Without a bundle the findings are `UNAVAILABLE`."""

    if value is None:
        return [], {"coverage": "UNAVAILABLE", "findings": []}
    try:
        bundle = parse_bundle(value)
        _check_times(bundle)
    except ValueError as exc:
        # AnalyzerReadbackError is a ValueError, as parse_rfc3339's errors are.
        raise MergeEvidenceError(f"the {_ANALYZER_LABEL} is invalid: {exc}") from exc
    # Before the binding, so a bundle for another subject is still refused when its
    # readbacks break the contract (Codex on #417).
    readbacks = _readbacks_by_item(bundle["readbacks"])
    if not _bound_to(bundle, subject):
        provenance = {"subject_binding": bundle["subject_binding"], "bound": False}
        receipts = [
            _analyzer_receipt(
                subject, item, "INCOMPLETE", bundle["observed_at"], provenance
            )
            for item in _ANALYZER_ITEMS.values()
        ]
        return receipts, {"coverage": "INCOMPLETE", "findings": []}
    receipts, findings = [], []
    for item, readback in readbacks.items():
        receipts.append(
            _analyzer_receipt(
                subject,
                item,
                _analyzer_item_status(item, readback),
                readback["observed_at"],
                {"completeness": readback["completeness"], "bound": True},
            )
        )
        for finding in readback["findings"]:
            entry = {"item": item, "id": finding["id"], "message": finding["message"]}
            entry.update({k: finding[k] for k in _FINDING_FIELDS if k in finding})
            findings.append(entry)
    complete = len(readbacks) == len(_ANALYZER_ITEMS) and all(
        r["status"] == "COMPLETE" for r in receipts
    )
    return receipts, {
        "coverage": "COMPLETE" if complete else "INCOMPLETE",
        "findings": findings,
    }


def _check_times(bundle: Mapping[str, Any]) -> None:
    """The bundle's and each readback's observation time, before the binding, so a
    bundle for another subject is refused as a bound one is (Claude on #417)."""

    parse_rfc3339(bundle["observed_at"])
    for readback in bundle["readbacks"]:
        parse_rfc3339(readback["observed_at"])


def _readbacks_by_item(
    readbacks: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """A bound bundle's readbacks by the item each stands for. An unknown or a
    repeated readback fails the run."""

    by_item: dict[str, dict[str, Any]] = {}
    for readback in readbacks:
        pair = (readback["provider"], readback["scope"])
        if pair not in _ANALYZER_ITEMS:
            raise MergeEvidenceError(
                f"the {_ANALYZER_LABEL} has an unknown readback {pair}"
            )
        if _ANALYZER_ITEMS[pair] in by_item:
            raise MergeEvidenceError(
                f"the {_ANALYZER_LABEL} repeats the readback {pair}"
            )
        by_item[_ANALYZER_ITEMS[pair]] = readback
    return by_item


def _analyzer_item_status(item: str, readback: Mapping[str, Any]) -> str:
    """The readback's coverage, as the receipt of the item it stands for. A
    complete read of another kind does not give it (Decision 0091; Codex on
    #417)."""

    status: str = readback["coverage"]["status"]
    if (
        status == "COMPLETE"
        and readback["completeness"] != _ANALYZER_COMPLETENESS[item]
    ):
        return "INCOMPLETE"
    return status


def subject_of(subject: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "repository": subject["repository"],
        "change_request": dict(subject["change_request"]),
        "head_commit": subject["head_commit"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge merge-evidence",
        description=(
            "Write the merge-admission evidence document for one GitHub pull "
            "request from its L1 snapshot. Exit 0 when written, 2 when the run "
            "failed."
        ),
        epilog="The L1 snapshot, collected with merge evidence, is read from standard input.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="a checkout of the protected target (default: the working directory)",
    )
    parser.add_argument(
        "--authorities",
        type=Path,
        default=DEFAULT_AUTHORITIES,
        help=f"the merge authorities (default: {DEFAULT_AUTHORITIES})",
    )
    parser.add_argument(
        "--required-checks",
        type=Path,
        default=DEFAULT_REQUIRED_CHECKS,
        help=f"the required-check manifest (default: {DEFAULT_REQUIRED_CHECKS})",
    )
    parser.add_argument(
        "--suppression-markers",
        type=Path,
        default=DEFAULT_SUPPRESSION_MARKERS,
        help=(
            f"the suppression markers (default: {DEFAULT_SUPPRESSION_MARKERS}; "
            "without them, the suppressions are UNAVAILABLE)"
        ),
    )
    parser.add_argument(
        "--trust-roots",
        type=Path,
        default=DEFAULT_TRUST_ROOTS,
        help=(
            f"the trust-root patterns (default: {DEFAULT_TRUST_ROOTS}; without "
            "them, the trust-root changes are UNAVAILABLE)"
        ),
    )
    parser.add_argument(
        "--analyzer-readback",
        type=Path,
        default=None,
        help=(
            "the authenticated analyzer readback's bundle for this pull request, "
            "inside the project root (without one, its items stay MISSING and "
            "its findings UNAVAILABLE)"
        ),
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

    def inside(path: Path) -> Path:
        return path if path.is_absolute() else args.project_root / path

    def compute() -> dict[str, Any]:
        root = args.project_root
        authorities = load_authorities(inside(args.authorities), project_root=root)
        policy = load_policy(inside(args.change_policy), project_root=root)
        codeowners = load_codeowners(root)
        required_checks = load_required_checks(
            inside(args.required_checks), project_root=root
        )
        bundle = None
        if args.analyzer_readback is not None:
            bundle = read_json_file(
                inside(args.analyzer_readback),
                _ANALYZER_LABEL,
                MergeEvidenceError,
                project_root=root,
            )
            if bundle is None:
                # A given file that holds `null` is not "no bundle" (CodeAnt on #417).
                raise MergeEvidenceError(
                    f"the {_ANALYZER_LABEL} is invalid: bundle must be an object"
                )
        return evidence_from_snapshot(
            read_json_input(_INPUT_LABEL, MergeEvidenceError),
            authorities=authorities,
            change_policy=policy,
            codeowners=codeowners,
            decisions=load_decisions(root),
            required_checks=required_checks,
            analyzer_readback=bundle,
            suppression_markers=load_suppression_markers(
                inside(args.suppression_markers), project_root=root
            ),
            trust_roots=load_trust_roots(inside(args.trust_roots), project_root=root),
        )

    return run(
        "merge-evidence",
        compute,
        positive=lambda _evidence: True,
        input_errors=(MergeEvidenceError, AssuranceCompletenessError),
    )
