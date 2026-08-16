from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import NoSuchResource, Unresolvable, Unretrievable
from yaml.nodes import MappingNode, Node, ScalarNode
from yaml.tokens import (
    AliasToken,
    AnchorToken,
    BlockEndToken,
    BlockMappingStartToken,
    BlockSequenceStartToken,
    FlowMappingEndToken,
    FlowMappingStartToken,
    FlowSequenceEndToken,
    FlowSequenceStartToken,
)

from .knowledge_common import KnowledgeFormatError, KnowledgeLoader, toolkit_root

IMMUTABLE_GIT_IDENTITY = re.compile(r"^git:[0-9a-f]{40}$")

# An additional operational bound on the YAML *source representation*, not a
# claim that every JSON-Schema-valid spelling of an envelope is accepted. The
# schema bounds code points, while comments, anchors, quoting and multibyte
# characters all cost bytes, so a schema-valid envelope can still exceed this.
MAX_ENVELOPE_BYTES = 524_288

# The same operational bound for a caller-supplied schema source.
MAX_SCHEMA_BYTES = 524_288

# The schema nests at most four levels (root, `identities`, `dependencies`, one
# dependency), which is also the depth of the current Gnostoa envelope. Thirty-two
# leaves room for schema growth and stays far below the roughly five hundred
# levels at which `yaml.compose` exhausts the interpreter stack.
MAX_ENVELOPE_DEPTH = 32

_DEPTH_OPENING = (
    BlockMappingStartToken,
    BlockSequenceStartToken,
    FlowMappingStartToken,
    FlowSequenceStartToken,
)
_DEPTH_CLOSING = (BlockEndToken, FlowMappingEndToken, FlowSequenceEndToken)

# Task state is a canonical JSON-shaped document that happens to be written in
# YAML. Anchors and aliases have no JSON meaning, and a very small alias graph
# expands exponentially once the document is serialised or validated, so they
# are refused in the source rather than accounted for later.
MERGE_TAG = "tag:yaml.org,2002:merge"


class ProjectionBudgetError(ValueError):
    """A valid envelope would exceed its declared review surface."""


def _read_bounded_text(path: Path, limit: int, label: str) -> str:
    """Capture one bounded immutable snapshot of a source file.

    At most `limit + 1` bytes are read, so an over-large file is refused
    without pulling its whole content into memory. Every later step works on
    the returned string, never on the path again, so a source that changes
    afterwards cannot alter what was checked.
    """

    try:
        with path.open("rb") as handle:
            raw = handle.read(limit + 1)
    except OSError as exc:
        raise KnowledgeFormatError(f"Cannot read {label} {path}: {exc}") from exc
    if len(raw) > limit:
        raise KnowledgeFormatError(
            f"{label} source is larger than the {limit}-byte bound: {path}"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise KnowledgeFormatError(
            f"{label} is not valid UTF-8 in {path}: {exc}"
        ) from exc


def _schema(path: Path) -> dict[str, Any]:
    text = _read_bounded_text(path, MAX_SCHEMA_BYTES, "Schema")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise KnowledgeFormatError(
            f"Schema is not valid JSON in {path}: {exc}"
        ) from exc
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Schema nesting exhausted the JSON parser in {path}"
        ) from exc
    except ValueError as exc:
        raise KnowledgeFormatError(
            f"Schema holds a literal the JSON parser refuses in {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise KnowledgeFormatError(f"Schema must be a mapping in {path}")
    _assert_local_references(value, path)
    try:
        Draft202012Validator.check_schema(value)
    except SchemaError as exc:
        raise KnowledgeFormatError(
            f"Schema is not a valid Draft 2020-12 schema in {path}: {exc.message}"
        ) from exc
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Schema nesting exhausted the schema checker in {path}"
        ) from exc
    return value


def _assert_local_references(schema: dict[str, Any], path: Path) -> None:
    """A supplied schema is a bounded local input, not a retrieval root.

    Only same-document fragment references are supported, so validation can
    never reach the filesystem or the network. The walk is iterative because a
    supplied schema is bounded by size but not by depth.
    """

    pending: list[Any] = [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if "$dynamicRef" in node:
                raise KnowledgeFormatError(
                    f"Schema uses $dynamicRef, which the portable custom-schema "
                    f"mode does not support, in {path}"
                )
            reference = node.get("$ref")
            if isinstance(reference, str) and not reference.startswith("#"):
                raise KnowledgeFormatError(
                    f"Schema reference is not a local fragment in {path}: {reference}"
                )
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)


def _offline_registry() -> Registry[Any]:
    """An empty registry, whose default retrieval refuses every request.

    `referencing` fails closed by default, so no filesystem or network client
    is reachable from schema validation. Non-fragment references are already
    refused before this point; the registry is the second barrier.
    """

    return Registry()


def _assert_bounded_source(text: str, path: Path) -> None:
    """Bound depth and refuse unsupported YAML features, before composition.

    `yaml.compose` recurses per level and exhausts the interpreter stack at
    roughly five hundred levels; `yaml.scan` is a token state machine and stays
    bounded, so both the depth and the anchors and aliases are measured here
    rather than discovered by crashing or by expanding.
    """

    depth = 0
    try:
        for token in yaml.scan(text, Loader=yaml.SafeLoader):
            if isinstance(token, (AnchorToken, AliasToken)):
                feature = "anchor" if isinstance(token, AnchorToken) else "alias"
                raise KnowledgeFormatError(
                    f"Task envelopes do not support YAML anchors, aliases or "
                    f"merge keys: {feature} at line {token.start_mark.line + 1}"
                )
            if isinstance(token, _DEPTH_OPENING):
                depth += 1
                if depth > MAX_ENVELOPE_DEPTH:
                    raise KnowledgeFormatError(
                        f"Task envelope nests deeper than the "
                        f"{MAX_ENVELOPE_DEPTH}-level bound at line "
                        f"{token.start_mark.line + 1}"
                    )
            elif isinstance(token, _DEPTH_CLOSING):
                depth -= 1
    except yaml.YAMLError as exc:
        raise KnowledgeFormatError(f"Cannot scan YAML {path}: {exc}") from exc


def _assert_json_compatible(envelope: dict[str, Any], path: Path) -> None:
    """Canonical task state is JSON-shaped, because its digest is JSON text."""

    try:
        json.dumps(envelope, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise KnowledgeFormatError(
            f"Task envelope holds state that is not JSON-compatible in {path}: {exc}"
        ) from exc


def _reject_duplicate_keys(text: str, path: Path) -> None:
    """Reject repeated scalar keys before safe loading discards an earlier value.

    This compares composed key nodes, so keys whose text differs but whose
    constructed values collide are outside its current reach; see the deferred
    finding in the B2/P1 measurement record.
    """

    try:
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise KnowledgeFormatError(f"Cannot load YAML {path}: {exc}") from exc
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Task envelope nesting exhausted the YAML composer in {path}"
        ) from exc

    # Aliases may make the composed node graph cyclic or repeat a shared
    # subgraph. Track the active path to reject cycles, and remember completed
    # nodes so a shared subgraph is inspected exactly once.
    active: set[int] = set()
    completed: set[int] = set()

    def visit(node: Node | None, location: str) -> None:
        if node is None:
            return
        identity = id(node)
        if identity in active:
            raise KnowledgeFormatError(
                f"Recursive YAML alias at {location or '<root>'} "
                f"line {node.start_mark.line + 1}"
            )
        if identity in completed:
            return
        active.add(identity)
        if isinstance(node, MappingNode):
            seen: set[tuple[str, str]] = set()
            for key_node, value_node in node.value:
                if key_node.tag == MERGE_TAG:
                    raise KnowledgeFormatError(
                        f"Task envelopes do not support YAML anchors, aliases or "
                        f"merge keys: merge key at line "
                        f"{key_node.start_mark.line + 1}"
                    )
                if isinstance(key_node, ScalarNode):
                    key = (key_node.tag, key_node.value)
                    if key in seen:
                        line = key_node.start_mark.line + 1
                        raise KnowledgeFormatError(
                            f"Duplicate YAML key at {location or '<root>'} "
                            f"line {line}: {key_node.value}"
                        )
                    seen.add(key)
                    child = (
                        f"{location}.{key_node.value}" if location else key_node.value
                    )
                else:
                    child = location
                visit(value_node, child)
        elif isinstance(node, yaml.nodes.SequenceNode):
            for index, child_node in enumerate(node.value):
                visit(child_node, f"{location}[{index}]")
        active.discard(identity)
        completed.add(identity)

    visit(root, "")


def _construct_envelope(text: str, path: Path) -> dict[str, Any]:
    """Build the envelope from the captured snapshot, not from the path."""

    try:
        value = yaml.load(text, Loader=KnowledgeLoader)
    except yaml.YAMLError as exc:
        raise KnowledgeFormatError(f"Cannot load YAML file {path}: {exc}") from exc
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Task envelope nesting exhausted the YAML constructor in {path}"
        ) from exc
    except ValueError as exc:
        # The scalar parsers reject values such as an integer literal above the
        # interpreter's integer-string conversion limit.
        raise KnowledgeFormatError(
            f"Task envelope holds a scalar the YAML parser refuses in {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise KnowledgeFormatError(f"Expected a YAML mapping in {path}")
    return value


def load_task_envelope(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    text = _read_bounded_text(resolved, MAX_ENVELOPE_BYTES, "Task envelope")
    _assert_bounded_source(text, resolved)
    _reject_duplicate_keys(text, resolved)
    envelope = _construct_envelope(text, resolved)
    _assert_json_compatible(envelope, resolved)
    return envelope


def checkpoint_digest(envelope: dict[str, Any]) -> str:
    try:
        payload = json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KnowledgeFormatError(
            f"Task envelope holds state that is not JSON-compatible: {exc}"
        ) from exc
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _location(error: Any) -> str:
    return ".".join(str(item) for item in error.absolute_path) or "<root>"


def _duplicate_ids(items: Any, label: str) -> list[str]:
    if not isinstance(items, list):
        return []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        identifier = item["id"]
        if identifier in seen:
            duplicates.add(identifier)
        seen.add(identifier)
    return [f"duplicate {label} id: {identifier}" for identifier in sorted(duplicates)]


def _reference_issues(envelope: dict[str, Any], repository_root: Path) -> list[str]:
    references = envelope.get("references")
    if not isinstance(references, dict):
        return []

    root = repository_root.resolve()
    issues: list[str] = []
    for label, singular in (("decisions", "decision"), ("evidence", "evidence")):
        items = references.get(label)
        issues.extend(_duplicate_ids(items, singular))
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            resource = item.get("resource")
            if not isinstance(resource, str):
                continue
            try:
                parsed = urlsplit(resource)
            except ValueError:
                issues.append(f"reference is not a parsable URL or path: {resource}")
                continue
            if (
                resource.startswith(("/", "~"))
                or PureWindowsPath(resource).is_absolute()
                or "\\" in resource
            ):
                issues.append(f"reference is not a portable relative path: {resource}")
                continue
            if parsed.scheme:
                if parsed.scheme != "https":
                    issues.append(
                        f"reference uses unsupported external scheme: {resource}"
                    )
                elif not parsed.netloc:
                    issues.append(f"https reference has no host: {resource}")
                continue
            if parsed.netloc or not parsed.path:
                issues.append(f"reference is not a portable relative path: {resource}")
                continue
            candidate = (root / parsed.path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                issues.append(f"reference escapes repository root: {resource}")
                continue
            if not candidate.exists():
                issues.append(f"reference does not exist: {resource}")
    return issues


def validate_task_envelope(
    envelope_path: Path,
    repository_root: Path,
    schema_path: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    envelope = load_task_envelope(envelope_path)
    schema = (
        schema_path.resolve()
        if schema_path
        else toolkit_root() / "schemas" / "task-envelope.schema.json"
    )
    validator = Draft202012Validator(_schema(schema), registry=_offline_registry())
    try:
        errors = sorted(
            validator.iter_errors(envelope),
            key=lambda error: (list(error.absolute_path), error.message),
        )
    except (Unresolvable, NoSuchResource, Unretrievable) as exc:
        raise KnowledgeFormatError(
            f"Schema reference does not resolve locally in {schema}: {exc}"
        ) from exc
    except RecursionError as exc:
        raise KnowledgeFormatError(
            f"Schema references recurse without termination in {schema}"
        ) from exc
    issues = [f"{_location(error)}: {error.message}" for error in errors]

    identities = envelope.get("identities")
    if isinstance(identities, dict):
        issues.extend(_duplicate_ids(identities.get("dependencies"), "dependency"))
    issues.extend(_reference_issues(envelope, repository_root))
    return envelope, sorted(set(issues))


def _parse_observations(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        identifier, separator, value = raw.partition("=")
        if not separator or not identifier or not value:
            raise KnowledgeFormatError(
                "Observed dependencies use the exact form ID=VALUE"
            )
        if identifier in result:
            raise KnowledgeFormatError(
                f"Observed dependency supplied more than once: {identifier}"
            )
        result[identifier] = value
    return result


def current_state_issues(
    envelope: dict[str, Any],
    observed_base: str,
    observed_dependencies: dict[str, str],
    expected_checkpoint: str | None = None,
    expected_previous_checkpoint: str | None = None,
) -> list[str]:
    issues = checkpoint_observation_issues(
        envelope,
        expected_checkpoint,
        expected_previous_checkpoint,
    )
    identities = envelope.get("identities", {})
    base = identities.get("base", {}) if isinstance(identities, dict) else {}
    expected_base = base.get("value") if isinstance(base, dict) else None
    if isinstance(expected_base, str) and observed_base != expected_base:
        issues.append(
            f"base identity mismatch: expected {expected_base}, observed {observed_base}"
        )

    dependencies = (
        identities.get("dependencies", []) if isinstance(identities, dict) else []
    )
    expected_ids: set[str] = set()
    if isinstance(dependencies, list):
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue
            identifier = dependency.get("id")
            expected = dependency.get("value")
            if not isinstance(identifier, str) or not isinstance(expected, str):
                continue
            expected_ids.add(identifier)
            observed = observed_dependencies.get(identifier)
            if observed is None:
                issues.append(f"missing observed dependency: {identifier}")
            elif observed != expected:
                issues.append(
                    "dependency identity mismatch: "
                    f"{identifier}: expected {expected}, observed {observed}"
                )
    for identifier in sorted(set(observed_dependencies) - expected_ids):
        issues.append(f"unknown observed dependency: {identifier}")
    return sorted(set(issues))


def checkpoint_observation_issues(
    envelope: dict[str, Any],
    expected_checkpoint: str | None,
    expected_previous_checkpoint: str | None,
) -> list[str]:
    issues: list[str] = []
    digest = checkpoint_digest(envelope)
    if expected_checkpoint is not None and expected_checkpoint != digest:
        issues.append(
            f"checkpoint conflict: expected {expected_checkpoint}, observed {digest}"
        )

    checkpoint = envelope.get("checkpoint")
    previous = checkpoint.get("previous") if isinstance(checkpoint, dict) else None
    if (
        expected_previous_checkpoint is not None
        and expected_previous_checkpoint != previous
    ):
        issues.append(
            "previous checkpoint mismatch: "
            f"expected {expected_previous_checkpoint}, observed {previous}"
        )

    return sorted(set(issues))


def _bullet_list(values: list[str]) -> list[str]:
    return [f"- {_markdown_text(value)}" for value in values]


def _markdown_text(value: str) -> str:
    """Keep envelope prose from creating Markdown structure in the projection."""

    return re.sub(r"([\\`*_{}\[\]()#+!|>~-])", r"\\\1", value)


def render_current_projection(
    envelope: dict[str, Any],
    candidate: str,
) -> str:
    task = envelope["task"]
    scope = envelope["scope"]
    state = envelope["state"]
    identities = envelope["identities"]
    references = envelope["references"]
    handoff = envelope["handoff"]
    checkpoint = envelope["checkpoint"]
    recording = envelope["recording"]
    review = envelope["review"]
    digest = checkpoint_digest(envelope)

    lines = [
        "# Current task projection",
        "",
        "> Derived, replaceable orientation only. The task envelope and linked",
        "> source records remain authoritative.",
        "> Candidate identity is an immutable caller observation; this command does",
        "> not refresh or mediate provider HEAD.",
        "> The named owner is accountable but is not thereby the author or approver.",
        "> Recorded status grants no acceptance, integration or external effect.",
        "",
        f"- Task: `{task['id']}`",
        f"- Objective: {_markdown_text(task['objective'])}",
        f"- Owner/class: `{task['owner']}` / `{task['change_class']}`",
        f"- State: `{state['status']}`",
        f"- Checkpoint: `{digest}`",
        f"- Sequence: `{checkpoint['sequence']}`",
        f"- Candidate: `{candidate}`",
        f"- Base: `{identities['base']['value']}`",
        f"- Recorded by/at: `{recording['actor']}` / `{recording['at']}`",
        (
            "- Review budget: "
            f"`{review['projection_characters']}` projection characters / "
            f"`{review['owner_minutes']}` owner minutes; "
            f"on exceed `{review['on_exceed']}`"
        ),
        "",
        "## Completed",
        "",
        *(_bullet_list(state["completed"]) or ["- Nothing recorded yet."]),
        "",
        "## Next action",
        "",
        f"- {_markdown_text(state['next_action'])}"
        if state["next_action"]
        else "- No active next action.",
    ]
    if state["blocker"]:
        lines.extend(["", "## Blocker", "", f"- {_markdown_text(state['blocker'])}"])

    lines.extend(["", "## Scope", "", "Included:"])
    lines.extend(_bullet_list(scope["included"]))
    lines.extend(["", "Excluded:"])
    lines.extend(_bullet_list(scope["excluded"]))

    lines.extend(["", "## Exact dependencies", ""])
    dependencies = identities["dependencies"]
    if dependencies:
        lines.extend(
            f"- `{item['id']}` ({item['kind']}): `{item['value']}`"
            for item in dependencies
        )
    else:
        lines.append("- None.")

    lines.extend(["", "## Linked decisions and evidence", ""])
    for label, singular in (("decisions", "decision"), ("evidence", "evidence")):
        for item in references[label]:
            lines.append(f"- {singular} `{item['id']}`: `{item['resource']}`")
    if not references["decisions"] and not references["evidence"]:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Handoff",
            "",
            f"- Next actor: {_markdown_text(handoff['actor'])}",
            "- Read:",
            *[f"  - {_markdown_text(item)}" for item in handoff["read"]],
            "- Verify:",
            *[f"  - {_markdown_text(item)}" for item in handoff["verify"]],
        ]
    )
    projection = "\n".join(lines).rstrip() + "\n"
    budget = review["projection_characters"]
    if len(projection) > budget:
        raise ProjectionBudgetError(
            "Current projection exceeds its declared character budget: "
            f"{len(projection)} > {budget}"
        )
    return projection


def _common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--envelope", required=True, type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--expected-checkpoint")
    parser.add_argument("--expected-previous-checkpoint")
    return parser


def _validate_parser() -> argparse.ArgumentParser:
    return _common_parser("Validate a bounded Gnostoa task envelope.")


def _project_parser() -> argparse.ArgumentParser:
    parser = _common_parser(
        "Validate current identities and render one deterministic task projection."
    )
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--observed-base", required=True)
    parser.add_argument("--observed-dependency", action="append", default=[])
    parser.add_argument("--output", type=Path)
    return parser


def _print_issues(issues: list[str]) -> int:
    for issue in issues:
        print(f"ERROR: {issue}")
    return 1


def validate_main(argv: list[str] | None = None) -> int:
    args = _validate_parser().parse_args(argv)
    try:
        envelope, issues = validate_task_envelope(
            args.envelope,
            args.repository_root,
            args.schema,
        )
        # A checkpoint describes a schema-valid envelope, so it is neither
        # compared nor reported for one that already failed validation.
        if not issues and (
            args.expected_checkpoint or args.expected_previous_checkpoint
        ):
            issues.extend(
                checkpoint_observation_issues(
                    envelope,
                    args.expected_checkpoint,
                    args.expected_previous_checkpoint,
                )
            )
        if issues:
            return _print_issues(sorted(set(issues)))
        digest = checkpoint_digest(envelope)
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"OK: task envelope is valid ({digest})")
    return 0


def project_main(argv: list[str] | None = None) -> int:
    args = _project_parser().parse_args(argv)
    try:
        envelope, issues = validate_task_envelope(
            args.envelope,
            args.repository_root,
            args.schema,
        )
        observations = _parse_observations(args.observed_dependency)
        if IMMUTABLE_GIT_IDENTITY.fullmatch(args.candidate) is None:
            issues.append(
                "candidate must be an immutable Git identity in the form "
                "git:<40 lowercase hex characters>"
            )
        if not issues:
            issues.extend(
                current_state_issues(
                    envelope,
                    args.observed_base,
                    observations,
                    args.expected_checkpoint,
                    args.expected_previous_checkpoint,
                )
            )
        if issues:
            return _print_issues(sorted(set(issues)))
        if args.output:
            if args.output.exists():
                raise KnowledgeFormatError(
                    "Derived projection output already exists; refusing to overwrite it"
                )
        projection = render_current_projection(envelope, args.candidate)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as output:
                output.write(projection)
            print(f"Wrote {args.output}")
        else:
            print(projection, end="")
    except ProjectionBudgetError as exc:
        return _print_issues([str(exc)])
    except (KnowledgeFormatError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(validate_main())
