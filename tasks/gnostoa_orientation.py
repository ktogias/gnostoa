"""Render the experimental Gnostoa-self D14-O1 orientation snapshot."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONTRACT = "gnostoa-self-orientation/0.1"
MAX_SOURCE_BYTES = 262_144
GIT_TIMEOUT_SECONDS = 5
MAX_GIT_DIAGNOSTIC_CHARS = 500
FACT_GROUPS = (
    "purpose",
    "implemented",
    "proposed",
    "current",
    "next_action",
    "proposed_successor",
    "blockers",
    "constraints",
    "return_to_adoption",
)
LIST_GROUPS = {"implemented", "proposed", "current", "blockers", "constraints"}
SOURCE_STATUSES = {"complete", "partial", "missing", "conflicting"}
SOURCE_KINDS = {"local-file", "recorded-observation"}
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_ID = re.compile(r"^[0-9a-f]{40}$")


class OrientationError(ValueError):
    """The self-only snapshot or invocation is invalid."""


def _closed_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        observed = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise OrientationError(
            f"{label} keys must be {sorted(expected)!r}; observed {observed!r}"
        )
    return value


def _line(value: Any, label: str, maximum: int = 1000) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\n" in value
        or "\r" in value
        or len(value) > maximum
    ):
        raise OrientationError(f"{label} must be one non-empty bounded line")
    return value


def _timestamp(value: Any, label: str) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _fact(value: Any, label: str, source_ids: set[str], successor: bool = False) -> str:
    expected = {"id", "text", "source_ids"}
    if successor:
        expected.add("admission_state")
    item = _closed_keys(value, expected, label)
    _line(item["id"], f"{label}.id", 120)
    _line(item["text"], f"{label}.text", 4000)
    references = item["source_ids"]
    if (
        not isinstance(references, list)
        or not references
        or any(not isinstance(reference, str) for reference in references)
        or len(set(references)) != len(references)
    ):
        raise OrientationError(f"{label}.source_ids must be a non-empty unique list")
    for reference in references:
        if reference not in source_ids:
            raise OrientationError(f"{label} references unknown source {reference!r}")
    if successor:
        _line(item["admission_state"], f"{label}.admission_state", 80)
    return item["id"]


def validate_snapshot(snapshot: Any) -> dict[str, Any]:
    root = _closed_keys(
        snapshot,
        {"contract", "subject", "projection", "sources", "facts"},
        "snapshot",
    )
    if root["contract"] != CONTRACT:
        raise OrientationError(f"contract must be {CONTRACT!r}")
    subject_keys = {"source_commit", "source_tree"}
    if isinstance(root["subject"], dict) and "_public_identity_note" in root["subject"]:
        subject_keys.add("_public_identity_note")
    subject = _closed_keys(root["subject"], subject_keys, "subject")
    if "_public_identity_note" in subject:
        _line(subject["_public_identity_note"], "subject._public_identity_note")
    for name in ("source_commit", "source_tree"):
        if not isinstance(subject[name], str) or not GIT_ID.fullmatch(subject[name]):
            raise OrientationError(
                f"subject.{name} must be a 40-character Git object ID"
            )
    projection = _closed_keys(
        root["projection"],
        {"id", "observed_at", "freshness_seconds", "review_characters"},
        "projection",
    )
    _line(projection["id"], "projection.id", 120)
    if _timestamp(projection["observed_at"], "projection.observed_at") is None:
        raise OrientationError(
            "projection.observed_at must be an RFC 3339 UTC timestamp"
        )
    if (
        not isinstance(projection["freshness_seconds"], int)
        or not 1 <= projection["freshness_seconds"] <= 2_592_000
    ):
        raise OrientationError("projection.freshness_seconds must be 1..2592000")
    if projection["review_characters"] != 5000:
        raise OrientationError("projection.review_characters must be 5000")

    sources = root["sources"]
    if not isinstance(sources, list) or not sources or len(sources) > 30:
        raise OrientationError("sources must be a non-empty list of at most 30 items")
    source_ids: set[str] = set()
    for index, source_value in enumerate(sources):
        source = _closed_keys(
            source_value,
            {"id", "kind", "locator", "identity", "observed_at", "required", "status"},
            f"sources[{index}]",
        )
        identity = _line(source["id"], f"sources[{index}].id", 120)
        if identity in source_ids:
            raise OrientationError(f"duplicate source id {identity!r}")
        source_ids.add(identity)
        if not isinstance(source["kind"], str) or source["kind"] not in SOURCE_KINDS:
            raise OrientationError(f"sources[{index}].kind is unsupported")
        _line(source["locator"], f"sources[{index}].locator", 500)
        _line(source["identity"], f"sources[{index}].identity", 500)
        if source["kind"] == "local-file" and not SHA256.fullmatch(source["identity"]):
            raise OrientationError(
                f"sources[{index}].identity must be sha256 for a local file"
            )
        if not isinstance(source["required"], bool):
            raise OrientationError(f"sources[{index}].required must be boolean")
        if (
            not isinstance(source["status"], str)
            or source["status"] not in SOURCE_STATUSES
        ):
            raise OrientationError(f"sources[{index}].status is unsupported")

    facts = _closed_keys(root["facts"], set(FACT_GROUPS), "facts")
    fact_ids: set[str] = set()
    for group in FACT_GROUPS:
        value = facts[group]
        if group in LIST_GROUPS:
            if not isinstance(value, list) or (
                group in {"implemented", "proposed", "constraints"} and not value
            ):
                raise OrientationError(f"facts.{group} must be an appropriate list")
            for index, item in enumerate(value):
                fact_id = _fact(item, f"facts.{group}[{index}]", source_ids)
                if fact_id in fact_ids:
                    raise OrientationError(f"duplicate fact id {fact_id!r}")
                fact_ids.add(fact_id)
        else:
            fact_id = _fact(
                value, f"facts.{group}", source_ids, group == "proposed_successor"
            )
            if fact_id in fact_ids:
                raise OrientationError(f"duplicate fact id {fact_id!r}")
            fact_ids.add(fact_id)
    return root


def _within_root(root: Path, locator: str) -> Path:
    target = (root / locator).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise OrientationError(
            f"local source escapes repository root: {locator}"
        ) from exc
    return target


def _git_output(root: Path, *args: str) -> str:
    root = root.resolve()
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={root}",
                "-C",
                str(root),
                *args,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OrientationError("cannot observe repository Git subject") from exc
    if result.returncode != 0:
        detail = (
            (result.stderr or result.stdout)
            .strip()
            .replace("\r", " ")
            .replace("\n", " ")
        )
        if len(detail) > MAX_GIT_DIAGNOSTIC_CHARS:
            detail = detail[:MAX_GIT_DIAGNOSTIC_CHARS] + "…"
        suffix = f": {detail}" if detail else f": exit {result.returncode}"
        raise OrientationError(f"cannot observe repository Git subject{suffix}")
    value = result.stdout.strip()
    if not value or "\n" in value or "\r" in value:
        raise OrientationError("cannot observe repository Git subject: invalid Git output")
    return value


def _repository_subject(value: Any, label: str) -> dict[str, str]:
    subject = _closed_keys(value, {"source_commit", "source_tree"}, label)
    for name in ("source_commit", "source_tree"):
        if not isinstance(subject[name], str) or not GIT_ID.fullmatch(subject[name]):
            raise OrientationError(
                f"{label}.{name} must be a 40-character Git object ID"
            )
    return {"source_commit": subject["source_commit"], "source_tree": subject["source_tree"]}


def observe_repository_subject(repository_root: Path) -> dict[str, str]:
    root = repository_root.resolve()
    top_level = Path(_git_output(root, "rev-parse", "--show-toplevel")).resolve()
    if top_level != root:
        raise OrientationError("repository root does not match Git top level")
    return _repository_subject(
        {
            "source_commit": _git_output(root, "rev-parse", "--verify", "HEAD^{commit}"),
            "source_tree": _git_output(root, "rev-parse", "--verify", "HEAD^{tree}"),
        },
        "observed_repository_subject",
    )


def canonical_json(value: dict[str, Any]) -> str:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _digest(manifest: dict[str, Any]) -> str:
    content = copy.deepcopy(manifest)
    content.pop("manifest_digest", None)
    payload = canonical_json(content).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_manifest(
    snapshot: Any,
    repository_root: Path,
    evaluated_at: str,
    observed_sources: dict[str, str] | None = None,
    observed_repository_subject: dict[str, str] | None = None,
) -> dict[str, Any]:
    validated = validate_snapshot(copy.deepcopy(snapshot))
    root = repository_root.resolve()
    evaluated = _timestamp(evaluated_at, "evaluated_at")
    if evaluated is None:
        raise OrientationError("evaluated_at must be an RFC 3339 UTC timestamp")
    observed_sources = observed_sources or {}
    repository_subject = (
        _repository_subject(
            copy.deepcopy(observed_repository_subject), "observed_repository_subject"
        )
        if observed_repository_subject is not None
        else None
    )
    diagnostics: list[str] = []
    states: set[str] = set()
    valid_observation_times: list[datetime] = []
    for source in validated["sources"]:
        observed = _timestamp(
            source["observed_at"], f"source {source['id']} observed_at"
        )
        source["identity_assurance"] = (
            "not-available"
            if source["kind"] == "local-file"
            else "recorded-not-authenticated"
        )
        if observed is None or observed > evaluated:
            states.add("INCOMPLETE")
            diagnostics.append(f"invalid-or-future-observation:{source['id']}")
        elif (
            source["required"]
            and (evaluated - observed).total_seconds()
            > validated["projection"]["freshness_seconds"]
        ):
            states.add("STALE")
            diagnostics.append(f"stale-source:{source['id']}")
        elif source["required"]:
            valid_observation_times.append(observed)
        if source["required"] and source["status"] in {"missing", "partial"}:
            states.add("INCOMPLETE")
            diagnostics.append(f"{source['status']}-source:{source['id']}")
        if source["status"] == "conflicting":
            states.add("CONFLICTING")
            diagnostics.append(f"conflicting-source:{source['id']}")
        if source["kind"] == "local-file":
            target = _within_root(root, source["locator"])
            try:
                with target.open("rb") as handle:
                    raw = handle.read(MAX_SOURCE_BYTES + 1)
            except OSError:
                states.add("INCOMPLETE")
                diagnostics.append(f"unreadable-local-source:{source['id']}")
            else:
                if len(raw) > MAX_SOURCE_BYTES:
                    states.add("INCOMPLETE")
                    diagnostics.append(f"oversized-local-source:{source['id']}")
                else:
                    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
                    source["observed_identity"] = actual
                    source["identity_assurance"] = "locally-recomputed"
                    if actual != source["identity"]:
                        states.add("STALE")
                        diagnostics.append(f"identity-mismatch:{source['id']}")
        elif source["id"] in observed_sources:
            source["supplied_identity"] = observed_sources[source["id"]]
            if observed_sources[source["id"]] != source["identity"]:
                states.add("STALE")
                diagnostics.append(f"identity-mismatch:{source['id']}")

    if repository_subject is not None:
        for name in ("source_commit", "source_tree"):
            if repository_subject[name] != validated["subject"][name]:
                states.add("STALE")
                diagnostics.append(f"repository-subject-mismatch:{name}")

    if len(validated["facts"]["current"]) > 1:
        states.add("CONFLICTING")
        diagnostics.append("multiple-current-items")
    status = (
        "CONFLICTING"
        if "CONFLICTING" in states
        else "INCOMPLETE"
        if "INCOMPLETE" in states
        else "STALE"
        if "STALE" in states
        else "CURRENT"
    )
    freshness = validated["projection"]["freshness_seconds"]
    fresh_until = (
        datetime.fromtimestamp(
            min(item.timestamp() for item in valid_observation_times) + freshness,
            tz=UTC,
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        if valid_observation_times
        else None
    )
    evaluation: dict[str, Any] = {
        "evaluated_at": evaluated_at,
        "fresh_until": fresh_until,
        "status": status,
        "diagnostics": sorted(set(diagnostics)),
    }
    if repository_subject is not None:
        evaluation["repository_subject"] = repository_subject
    validated["evaluation"] = evaluation
    validated["manifest_digest"] = _digest(validated)
    full = _render_full_markdown(validated)
    allowed = validated["projection"]["review_characters"]
    if len(full) > allowed:
        validated["evaluation"]["status"] = "OVER_BUDGET"
        validated["evaluation"]["diagnostics"].append(
            f"markdown-code-points:{len(full)}>{allowed}"
        )
        validated["manifest_digest"] = _digest(validated)
    return validated


def _markdown(value: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+!|>~-])", r"\\\1", value)


def _render_fact(fact: dict[str, Any]) -> str:
    sources = ", ".join(f"`{item}`" for item in fact["source_ids"])
    return f"- **{_markdown(fact['id'])}:** {_markdown(fact['text'])} _(sources: {sources})_"


def _render_full_markdown(manifest: dict[str, Any]) -> str:
    facts = manifest["facts"]
    evaluation = manifest["evaluation"]
    lines = [
        "# Gnostoa current orientation",
        "",
        "> Derived, replaceable Gnostoa-self orientation. Linked source and provider",
        "> records remain authoritative. Recorded hashes do not authenticate provider truth.",
        "",
        f"- Projection: `{manifest['projection']['id']}`",
        f"- Status: `{evaluation['status']}`",
        f"- Subject: `{manifest['subject']['source_commit']}` / tree `{manifest['subject']['source_tree']}`",
        f"- Observed/evaluated: `{manifest['projection']['observed_at']}` / `{evaluation['evaluated_at']}`",
        f"- Freshness: `{manifest['projection']['freshness_seconds']}` seconds; earliest expiry `{evaluation['fresh_until']}`",
        f"- Manifest: `{manifest['manifest_digest']}`",
        f"- Coverage: `{len(manifest['sources'])}` declared sources; diagnostics `{len(evaluation['diagnostics'])}`",
        "",
        "## Purpose",
        "",
        _render_fact(facts["purpose"]),
    ]
    sections = (
        ("Implemented", "implemented"),
        ("Proposed", "proposed"),
        ("Current selected work", "current"),
        ("Next action", "next_action"),
        ("Proposed successor", "proposed_successor"),
        ("Open questions and task-specific blockers", "blockers"),
        ("Constraints", "constraints"),
        ("Return to adoption", "return_to_adoption"),
    )
    empty_messages = {
        "implemented": "No implemented capability declared.",
        "proposed": "No proposed capability declared.",
        "blockers": "No material blockers declared within the captured facts.",
        "constraints": "No constraints declared.",
    }
    for heading, group in sections:
        lines.extend(["", f"## {heading}", ""])
        value = facts[group]
        items = value if isinstance(value, list) else [value]
        if not items and group == "current":
            if evaluation["status"] == "CURRENT":
                lines.append(
                    "- No selected current item in complete, fresh declared coverage."
                )
            else:
                lines.append(
                    f"- No current item is asserted; `{evaluation['status']}` prevents a complete no-selection claim."
                )
        elif not items:
            lines.append(f"- {empty_messages[group]}")
        else:
            lines.extend(_render_fact(item) for item in items)
        if group == "proposed_successor":
            lines.append(f"- Admission: `{value['admission_state']}`")
    lines.extend(["", "## Sources and freshness", ""])
    for source in manifest["sources"]:
        lines.append(
            f"- `{source['id']}`: {source['kind']}, `{source['status']}`, "
            f"observed `{source['observed_at']}`, identity `{source['identity']}`, "
            f"assurance `{source['identity_assurance']}` — {source['locator']}"
        )
    if evaluation["diagnostics"]:
        lines.extend(["", "## Diagnostics", ""])
        lines.extend(f"- `{item}`" for item in evaluation["diagnostics"])
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(manifest: dict[str, Any]) -> str:
    if manifest["evaluation"]["status"] != "OVER_BUDGET":
        return _render_full_markdown(manifest)
    diagnostic = next(
        item
        for item in manifest["evaluation"]["diagnostics"]
        if item.startswith("markdown-code-points:")
    )
    measured, allowed = diagnostic.removeprefix("markdown-code-points:").split(">")
    return (
        "# Gnostoa orientation unavailable\n\n"
        "- Status: `OVER_BUDGET`\n"
        f"- Manifest: `{manifest['manifest_digest']}`\n"
        f"- Markdown code points: `{measured}`; allowed: `{allowed}`\n"
        "- Required facts remain in the machine manifest; none were truncated.\n"
        "- Next action: shorten nonessential source text and regenerate without hiding blockers.\n"
    )


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OrientationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_snapshot(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise OrientationError(f"cannot read snapshot {path}: {exc}") from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise OrientationError(f"snapshot exceeds {MAX_SOURCE_BYTES}-byte bound")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OrientationError(f"snapshot is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise OrientationError("snapshot root must be an object")
    return value


def _observations(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        identity, separator, observed = value.partition("=")
        if not separator or not identity or not observed or identity in result:
            raise OrientationError(
                "--observed-source must be a unique ID=IDENTITY pair"
            )
        result[identity] = observed
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--evaluated-at", required=True)
    parser.add_argument("--observed-source", action="append", default=[])
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    try:
        args = parser.parse_args(argv)
        repository_root = args.repository_root.resolve()
        manifest = build_manifest(
            load_snapshot(args.snapshot),
            repository_root,
            args.evaluated_at,
            _observations(args.observed_source),
            observe_repository_subject(repository_root),
        )
    except OrientationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    output = (
        canonical_json(manifest) if args.format == "json" else render_markdown(manifest)
    )
    print(output, end="")
    return 0 if manifest["evaluation"]["status"] == "CURRENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
