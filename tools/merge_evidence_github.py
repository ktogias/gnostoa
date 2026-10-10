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
names (slice 1b.3b-1). Until the analyzer readback's (1b.3b-2) and SonarCloud's
(1b.3c) receipts exist, and while the suppressions and trust-root changes are
`UNAVAILABLE` (1b.3b-4), the verdict denies on M2-M8, M13 and M15 rather than
passing them vacuously.
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
from .verdict_cli import confine, read_json_input, run

DEFAULT_AUTHORITIES = Path("policy") / "merge-authorities.yaml"
DEFAULT_REQUIRED_CHECKS = Path("policy") / "merge-required-checks.yaml"
_REQUIRED_CHECKS_LABEL = "required checks"
_REQUIRED_CHECK_KEYS = frozenset({"schema_version", "id", "version", "requirements"})
_CHECK_KEYS = frozenset({"app_id", "name"})
_CHECK_PRODUCER = "gnostoa.merge-evidence-github/check-runs"
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
_WORK_ITEM_VALUE = re.compile(r"#\d+(?:(?: +| *, *)#\d+)*", re.ASCII)
_DECISION_VALUE = re.compile(r"\d{4}(?:(?: +| *, *)\d{4})*", re.ASCII)
_NUMBER = re.compile(r"\d+", re.ASCII)
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
        record = require_mapping(document, _REQUIRED_CHECKS_LABEL)
        require_closed_keys(record, _REQUIRED_CHECKS_LABEL, _REQUIRED_CHECK_KEYS)
        if record["schema_version"] != "1.0":
            raise MergeEvidenceError("required checks schema_version must be 1.0")
        require_text(record["id"], "required checks id")
        require_text(record["version"], "required checks version")
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
    latest = latest_checks(checks, subject["head_commit"])
    runs = check_runs_by_key(checks, subject["head_commit"])
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


def _change_control_fields(body: str) -> dict[str, str]:
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
    fields: dict[str, str] = {}
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
        match = _FIELD.fullmatch(_inline_value(token).strip(" \t"))
        if match is None:
            raise MergeEvidenceError(
                "a Change control item is not one of the template's fields"
            )
        if match.group(1) in fields:
            raise MergeEvidenceError(
                f"the Change control section repeats {match.group(1)}"
            )
        fields[match.group(1)] = match.group(2)
    return fields


def _listed(
    fields: Mapping[str, str], name: str, grammar: re.Pattern[str]
) -> list[str]:
    """The numbers a field lists, in order. An empty field lists nothing; a value
    that is not the field's grammar fails the run."""

    # Only ASCII spaces pad a value: a Unicode space is not erased.
    value = fields.get(name, "").strip(" ")
    if value and grammar.fullmatch(value) is None:
        raise MergeEvidenceError(f"the {name} field is not a list the template allows")
    return _unique(_NUMBER.findall(value))


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
    work_items = [f"#{n}" for n in _listed(fields, "Work Item", _WORK_ITEM_VALUE)]
    linked = _listed(fields, "Decision", _DECISION_VALUE)
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
    required_checks: Mapping[str, Mapping[str, str]],
) -> dict[str, Any]:
    """The evidence document for the pull request the snapshot observed."""

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
        # The check items' receipts (1b.3b-1); the analyzer readback's come with
        # 1b.3b-2 and SonarCloud's with 1b.3c.
        "receipts": _check_receipts(document, subject, required_checks),
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
        "--required-checks",
        type=Path,
        default=DEFAULT_REQUIRED_CHECKS,
        help=f"the required-check manifest (default: {DEFAULT_REQUIRED_CHECKS})",
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
        return evidence_from_snapshot(
            read_json_input(_INPUT_LABEL, MergeEvidenceError),
            authorities=authorities,
            change_policy=policy,
            codeowners=codeowners,
            decisions=load_decisions(root),
            required_checks=required_checks,
        )

    return run(
        "merge-evidence",
        compute,
        positive=lambda _evidence: True,
        input_errors=(MergeEvidenceError, AssuranceCompletenessError),
    )
