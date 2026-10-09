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
import string
from collections.abc import Iterator, Mapping, Sequence
from html.parser import HTMLParser
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
_FIELD = re.compile(r"(Class|Work Item|Decision):[ \t]*(.*)", re.DOTALL)
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
# `#N`, or an issue's URL, which keeps its repository (Codex on #413); the scheme
# and host compare without case, as the owner and name do (Claude on #413), and
# only ASCII letters fold, so a lookalike host is not GitHub (cubic on #413). The
# number ends at a boundary, as `#N`'s does (Codex on #413).
_ISSUE = re.compile(
    r"(?<![\w/])#(\d+)\b|(?ai:https://github\.com/)([^/\s]+/[^/\s]+)/issues/(\d+)\b"
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
        record = require_mapping(document, "merge authorities")
        require_closed_keys(record, "merge authorities", _AUTHORITY_KEYS)
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
        path, project_root, label="merge authorities", error=MergeEvidenceError
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
        # In order, so a failed run names the same path each time (Claude on
        # #413).
        for path in sorted({item["path"], item.get("previous_path")} - {None}):
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

    surfaces = [("title", subject.get("title") or ""), ("body", subject["body"])]
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
    """An item's visible value: its text and inline code. A link's target is not
    visible, so it is never read (Codex on #413; the owner's re-slice decision,
    #407 6085478125), and inline HTML, comments included, is not part of it."""

    parts: list[str] = []
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


class _OpenElements(HTMLParser):
    """The raw HTML elements open at a point in the description. CommonMark does
    not track HTML nesting, so Markdown inside an unclosed element, such as a
    collapsed `<details>`, is top-level to the parser while GitHub renders it
    inside the element (Codex on #413)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in _VOID_ELEMENTS:
            self.open.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # HTML ignores the slash: `<details/>` opens a details element.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in self.open:
            del self.open[len(self.open) - 1 - self.open[::-1].index(tag) :]


def _has_raw_tag(token: Token) -> bool:
    """Whether an inline token holds a raw HTML tag. GitHub may hide what a tag
    wraps, such as `<span hidden>` or `<details>`, so a heading or field holding
    one is not read; comments hide only themselves (cubic and Codex on #413)."""

    return any(
        child.type == "html_inline" and not child.content.startswith("<!--")
        for child in token.children or []
    )


def _inside_raw_html(tokens: Sequence[Token]) -> list[bool]:
    """For each token, whether a raw HTML element before it is still open."""

    elements = _OpenElements()
    inside = []
    for token in tokens:
        inside.append(bool(elements.open))
        if token.type == "html_block":
            elements.feed(token.content)
        for child in token.children or []:
            if child.type == "html_inline":
                elements.feed(child.content)
    return inside


def _is_top_heading(token: Token, tags: tuple[str, ...]) -> bool:
    return token.type == "heading_open" and token.level == 0 and token.tag in tags


def _section_start(tokens: Sequence[Token], inside: Sequence[bool]) -> int:
    """The index of the one top-level `## Change control` heading, which must not
    be inside raw HTML."""

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
    if inside[starts[0]] or _has_raw_tag(tokens[starts[0] + 1]):
        raise MergeEvidenceError("the Change control heading is in raw HTML")
    return starts[0]


def _section_items(
    tokens: Sequence[Token], start: int, inside: Sequence[bool]
) -> Iterator[tuple[Token, bool]]:
    """Each top-level list item's field, up to the next top-level h1 or h2, with
    whether it is in raw HTML. The field is the inline token of the item's first
    block when that is a paragraph: a continuation paragraph is not a field, as
    the owner chose (Codex on #413; #407, 6085825905)."""

    in_list = False
    for index in range(start + 3, len(tokens)):
        token = tokens[index]
        if _is_top_heading(token, ("h1", "h2")):
            return
        if token.type in ("bullet_list_open", "bullet_list_close") and token.level == 0:
            in_list = token.type == "bullet_list_open"
        elif (
            in_list
            and token.type == "list_item_open"
            and token.level == 1
            and tokens[index + 1].type == "paragraph_open"
        ):
            field = tokens[index + 2]
            yield field, inside[index + 2] or _has_raw_tag(field)


def _change_control_fields(body: str) -> dict[str, str]:
    """The fields of the description's one top-level `## Change control` section:
    the items of its top-level bullet lists, up to the next top-level h1 or h2."""

    tokens = _MARKDOWN.parse(body)
    inside = _inside_raw_html(tokens)
    fields: dict[str, str] = {}
    for token, hidden in _section_items(tokens, _section_start(tokens, inside), inside):
        match = _FIELD.fullmatch(_inline_value(token).strip())
        if match is None:
            continue
        if hidden:
            raise MergeEvidenceError(
                f"the Change control field {match.group(1)} is in raw HTML"
            )
        if match.group(1) in fields:
            raise MergeEvidenceError(
                f"the Change control section repeats {match.group(1)}"
            )
        fields[match.group(1)] = match.group(2)
    return fields


def _work_items(text: str, repository: str) -> list[str]:
    """This repository's issues the field names: `#N`, or a link to one of its
    issues. Another repository's issue is not this change's Work Item (Codex on
    #413); whether each exists is 1b.3b's acceptance case (#407, 6085101448)."""

    # The subject's repository is its URL; owner and name compare without case.
    own = login_key(repository)
    return _unique(
        [
            f"#{local or linked}"
            for local, linked_repository, linked in _ISSUE.findall(text)
            if local or login_key(f"https://github.com/{linked_repository}") == own
        ]
    )


def _change_control(
    body: str, decisions: frozenset[str], repository: str
) -> tuple[str, dict[str, list[str]]]:
    """The class, Work Items and Decisions from the change-request template's
    `## Change control` section (owner decision 3, #407). Examples in code blocks
    and comments are not fields, and a Decision counts only when the protected
    target has its record."""

    fields = _change_control_fields(body)
    change_class = fields.get("Class", "").strip()
    if change_class not in CHANGE_CLASSES:
        raise MergeEvidenceError(f"the change class {change_class!r} is not a class")
    work_items = _work_items(fields.get("Work Item", ""), repository)
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
    change_class, links = _change_control(
        provider["body"], decisions, subject["repository"]
    )
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
