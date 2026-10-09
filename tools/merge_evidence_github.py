"""Produce the merge-admission evidence for one GitHub pull request (MA0 Phase 1b,
slice 1b.3a, #407).

The input is one L1 snapshot (Decision 0086), collected with `merge_evidence`; the
output is the evidence document `knowledge merge-admission` reads. The adapter
reads nothing itself: the snapshot is the provider's state, and the project root is
a checkout of the **protected target**, whose change policy, merge authorities and
CODEOWNERS apply. A value is never inferred. Where the evidence contract has a
coverage field, it carries the read's real status; where it has none, an incomplete
read fails the run.

Until slices 1b.3b and 1b.3c, the receipts are empty and the suppressions and
trust-root changes are `UNAVAILABLE`, so the verdict denies on M2-M8, M13 and M15
rather than passing them vacuously.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .assurance_completeness import (
    AssuranceCompletenessError,
    require_closed_keys,
    require_mapping,
    require_text,
    require_unique_texts,
)
from .knowledge_common import KnowledgeFormatError
from .merge_admission import load_policy
from .review_model import parse_rfc3339
from .review_policy import CHANGE_CLASSES, load_policy_yaml
from .review_reconcile import ReconciliationInputError, validate_snapshot
from .verdict_cli import confine, read_json_input, run

DEFAULT_AUTHORITIES = Path("policy") / "merge-authorities.yaml"
DEFAULT_CHANGE_POLICY = Path("policy") / "change-control.yaml"
_INPUT_LABEL = "merge-evidence input"
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
_OWNER = re.compile(r"@[A-Za-z0-9-]+(?:/[A-Za-z0-9_.-]+)?|[^@\s]+@[^@\s]+")
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
_FIELD = re.compile(r"(Class|Work Item|Decision):[ \t]*(.*)", re.DOTALL)
_ISSUE = re.compile(
    r"(?<![\w/])#(\d+)\b|https://github\.com/[^/\s]+/[^/\s]+/issues/(\d+)"
)
# A standalone four-digit id, or a link to a Decision record; anything else, such as
# a year or an issue number in a URL, is not a reference (Codex, cubic and CodeAnt
# on #413). Only an id with a record in the protected target counts.
_DECISION = re.compile(r"knowledge/decisions/(\d{4})-|(?<![\w/.#-])(\d{4})(?![\w/.-])")
_DECISION_RECORD = re.compile(r"(\d{4})-[a-z0-9-]+\.md")
DECISIONS_DIRECTORY = Path("knowledge") / "decisions"
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


def parse_authorities(document: object) -> dict[str, Any]:
    """The merge authorities: the seal's declarer and the human approvers' roster."""

    try:
        record = require_mapping(document, "merge authorities")
        require_closed_keys(record, "merge authorities", _AUTHORITY_KEYS)
        if record["schema_version"] != "1.0":
            raise MergeEvidenceError("merge authorities schema_version must be 1.0")
        require_text(record["id"], "merge authorities id")
        require_text(record["version"], "merge authorities version")
        return {
            "declarer": require_text(record["declarer"], "declarer"),
            "human_approvers": require_unique_texts(
                record["human_approvers"], "human_approvers"
            ),
        }
    except AssuranceCompletenessError as exc:
        raise MergeEvidenceError(str(exc)) from exc


def load_authorities(path: Path, *, project_root: Path) -> dict[str, Any]:
    resolved = confine(
        path, project_root, label="merge authorities", error=MergeEvidenceError
    )
    try:
        document = load_policy_yaml(resolved, label="Merge authorities")
    except KnowledgeFormatError as exc:
        raise MergeEvidenceError(str(exc)) from exc
    return parse_authorities(document)


def _glob(text: str) -> str:
    pattern, index = "", 0
    while index < len(text):
        if text.startswith("**/", index):
            pattern += "(?:.*/)?"
            index += 3
        elif text.startswith("**", index):
            pattern += ".*"
            index += 2
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


def _rule(pattern: str) -> re.Pattern[str]:
    """One CODEOWNERS pattern, as GitHub documents it: gitignore's rules, without
    `!`, `[ ]` and `\\` escapes, which are refused rather than skipped."""

    if pattern.startswith("!") or any(c in pattern for c in "[]\\"):
        raise MergeEvidenceError(f"CODEOWNERS pattern {pattern!r} is not supported")
    directory = pattern.endswith("/")
    body = pattern.strip("/")
    if not body:
        raise MergeEvidenceError(f"CODEOWNERS pattern {pattern!r} names no path")
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
    return re.compile(prefix + _glob(body) + suffix)


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
        pattern, *owners = stripped.split()
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


def _required_approvers(
    files: Sequence[Mapping[str, Any]], codeowners: CodeOwners, roster: Sequence[str]
) -> list[str]:
    """The roster's people among each changed file's code owners. A file whose rule
    names owners, none of whom is on the roster, cannot be approved by anyone the
    verdict can recognize, so the run fails."""

    required: set[str] = set()
    for item in files:
        if item["status"] == "renamed" and not item.get("previous_path"):
            # The old location's owners would be skipped (CodeAnt on #413).
            raise MergeEvidenceError(
                f"the rename to {item['path']} has no previous path"
            )
        for path in {item["path"], item.get("previous_path")} - {None}:
            owners = codeowners.owners(path)
            if not owners:
                continue
            # GitHub logins are case-insensitive (CodeAnt on #413).
            people = {
                o[1:].casefold() for o in owners if o.startswith("@") and "/" not in o
            }
            on_roster = people & {r.casefold() for r in roster}
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
        if (
            comment["author"].casefold() != declarer.casefold()
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
    return {"declarer": declarer.casefold(), "head_commit": max(seals)[2]}


def _closing_references(
    subject: Mapping[str, Any],
    commits: Sequence[Mapping[str, Any]],
    commit_coverage: str,
) -> dict[str, Any]:
    surfaces = [("title", subject.get("title") or ""), ("body", subject["body"])]
    surfaces += [(f"commit {c['sha']}", c["message"]) for c in commits]
    found = [
        {"surface": surface, "reference": match.group(2)}
        for surface, text in surfaces
        for match in _CLOSING.finditer(text)
    ]
    if commit_coverage != "COMPLETE":
        coverage = commit_coverage
    elif any(c["message_truncated"] for c in commits):
        coverage = "PARTIAL"
    else:
        coverage = "COMPLETE"
    return {"coverage": coverage, "found": found}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def load_decisions(project_root: Path) -> frozenset[str]:
    """The ids of the protected target's Decision records. Each record must lie
    inside the protected target, and a missing directory fails the run (cubic on
    #413)."""

    root = project_root.resolve()
    candidate = project_root / DECISIONS_DIRECTORY
    if not candidate.is_dir():
        raise MergeEvidenceError(
            f"the protected target has no {DECISIONS_DIRECTORY} directory"
        )
    directory = confine(
        candidate, project_root, label="decision records", error=MergeEvidenceError
    )
    return frozenset(
        match.group(1)
        for entry in directory.iterdir()
        if (match := _DECISION_RECORD.fullmatch(entry.name))
        and entry.is_file()
        and entry.resolve().is_relative_to(root)
    )


def _inline_value(token: Token) -> str:
    """An item's visible value: its text, inline code and link targets. Inline
    HTML, comments included, is not part of it."""

    parts: list[str] = []
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type == "link_open":
            parts.append(f" {child.attrGet('href') or ''} ")
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


def _change_control_fields(body: str) -> dict[str, str]:
    """The fields of the description's one top-level `## Change control` section:
    the items of its top-level bullet lists, up to the next top-level h1 or h2."""

    tokens = _MARKDOWN.parse(body)
    starts = [
        index
        for index, token in enumerate(tokens)
        if token.type == "heading_open"
        and token.level == 0
        and token.tag == "h2"
        and tokens[index + 1].content.strip() == "Change control"
    ]
    if not starts:
        raise MergeEvidenceError("the description has no Change control section")
    if len(starts) > 1:
        raise MergeEvidenceError(
            "the description has more than one Change control section"
        )
    fields: dict[str, str] = {}
    in_list = False
    for index in range(starts[0] + 3, len(tokens)):
        token = tokens[index]
        if (
            token.type == "heading_open"
            and token.level == 0
            and token.tag in ("h1", "h2")
        ):
            break
        if token.type == "bullet_list_open" and token.level == 0:
            in_list = True
        elif token.type == "bullet_list_close" and token.level == 0:
            in_list = False
        elif in_list and token.type == "inline" and token.level == 3:
            match = _FIELD.fullmatch(_inline_value(token).strip())
            if match is None:
                continue
            if match.group(1) in fields:
                raise MergeEvidenceError(
                    f"the Change control section repeats {match.group(1)}"
                )
            fields[match.group(1)] = match.group(2)
    return fields


def _change_control(
    body: str, decisions: frozenset[str]
) -> tuple[str, dict[str, list[str]]]:
    """The class, Work Items and Decisions from the change-request template's
    `## Change control` section (owner decision 3, #407). Examples in code blocks
    and comments are not fields, and a Decision counts only when the protected
    target has its record."""

    fields = _change_control_fields(body)
    change_class = fields.get("Class", "").strip()
    if change_class not in CHANGE_CLASSES:
        raise MergeEvidenceError(f"the change class {change_class!r} is not a class")
    work_items = _unique(
        [f"#{a or b}" for a, b in _ISSUE.findall(fields.get("Work Item", ""))]
    )
    linked = _unique([a or b for a, b in _DECISION.findall(fields.get("Decision", ""))])
    return change_class, {
        "work_items": work_items,
        "decisions": [d for d in linked if d in decisions],
    }


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
            "reviewer": item["reviewer_id"].casefold(),
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
    decisions: frozenset[str],
) -> dict[str, Any]:
    """The evidence document for the pull request the snapshot observed."""

    document = require_mapping(snapshot, "snapshot")
    try:
        subject, _, coverage = validate_snapshot(dict(document))
    except ReconciliationInputError as exc:
        raise MergeEvidenceError(f"the snapshot is invalid: {exc}") from exc
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
    change_class, links = _change_control(provider["body"], decisions)
    state = "merged" if provider["merged"] else provider["state"]
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
            "declarer": authorities["declarer"].casefold(),
            "author": provider["author"].casefold(),
            "required_approvers": _required_approvers(
                files, codeowners, authorities["human_approvers"]
            ),
        },
        "reviews": _reviews(document),
        "threads": {
            "coverage": coverage["review_threads"]["status"],
            "unresolved": sum(1 for t in threads if t.get("state") != "resolved"),
        },
        "closing_references": _closing_references(provider, commits, commit_coverage),
        # Produced by slice 1b.3b; until then they cannot be read.
        "suppressions": {"coverage": "UNAVAILABLE", "found": []},
        "trust_root_changes": {"coverage": "UNAVAILABLE", "paths": []},
        "receipts": [],
    }


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
        return evidence_from_snapshot(
            read_json_input(_INPUT_LABEL, MergeEvidenceError),
            authorities=authorities,
            change_policy=policy,
            codeowners=codeowners,
            decisions=load_decisions(root),
        )

    return run(
        "merge-evidence",
        compute,
        positive=lambda _evidence: True,
        input_errors=(MergeEvidenceError, AssuranceCompletenessError),
    )
