from __future__ import annotations

import base64
import copy
import html
import json
import re
from typing import Any

from .review_model import canonical_json, parse_rfc3339

_INTERNAL_SCHEMA_VERSION = "gnostoa-l1-current-state/v1"
PROVIDER_STATE_SCHEMA_VERSION = "gnostoa-review-provider-state/v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_COVERAGE = {"COMPLETE", "PARTIAL", "RATE_LIMITED", "UNAVAILABLE", "ERROR"}
_SEMANTIC_OUTCOMES = {"PASS", "BLOCKED", "INCOMPLETE", "CONFLICTING"}
_MARKER = re.compile(r"<!-- gnostoa:l1-current-state:v1:([A-Za-z0-9_-]+) -->")
_MAX_RENDER_BYTES = 32_768


class ReconciliationInputError(ValueError):
    """Raised when a normalized provider snapshot cannot be reduced safely."""


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReconciliationInputError(f"{label} must be an object")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReconciliationInputError(f"{label} must be a non-empty string")
    return value


def _optional_summary(value: object, *, limit: int = 512) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    if not normalized:
        return None
    return normalized[:limit]


def _markdown_code(value: object, label: str) -> str:
    rendered = _string(value, label)
    normalized = " ".join(rendered.split())
    if not normalized:
        raise ReconciliationInputError(f"{label} must contain visible text")
    escaped = html.escape(normalized, quote=False)
    longest = max(
        (len(match.group(0)) for match in re.finditer(r"`+", escaped)),
        default=0,
    )
    fence = "`" * (longest + 1)
    return f"{fence}{escaped}{fence}"


def _timestamp(value: object, label: str) -> str:
    rendered = _string(value, label)
    try:
        parse_rfc3339(rendered)
    except ValueError as exc:
        raise ReconciliationInputError(f"{label} must be RFC3339") from exc
    return rendered


def _sha(value: object, label: str) -> str:
    rendered = _string(value, label)
    if _SHA40.fullmatch(rendered) is None:
        raise ReconciliationInputError(f"{label} must be an exact Git commit")
    return rendered


def _change_request(value: object, label: str) -> dict[str, str]:
    item = _mapping(value, label)
    return {
        "kind": _string(item.get("kind"), f"{label}.kind"),
        "id": _string(item.get("id"), f"{label}.id"),
    }


def _subject(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if snapshot.get("schema_version") != PROVIDER_STATE_SCHEMA_VERSION:
        raise ReconciliationInputError(
            "provider snapshot schema_version is unsupported"
        )
    provider = _mapping(snapshot.get("provider"), "provider")
    provider_id = _string(provider.get("id"), "provider.id")
    observed_at = _timestamp(snapshot.get("observed_at"), "observed_at")

    subject = _mapping(snapshot.get("subject"), "subject")
    repository = _string(subject.get("repository"), "subject.repository")
    change_request = _change_request(
        subject.get("change_request"),
        "subject.change_request",
    )
    state = _string(subject.get("state"), "subject.state")
    head = _sha(subject.get("head_commit"), "subject.head_commit")
    base = _sha(subject.get("base_commit"), "subject.base_commit")
    comparison = _mapping(subject.get("comparison"), "subject.comparison")
    if comparison.get("kind") != "merge_base":
        raise ReconciliationInputError("subject.comparison.kind must be merge_base")
    merge_base = _sha(
        comparison.get("commit_sha"),
        "subject.comparison.commit_sha",
    )
    source_url = _string(subject.get("source_url"), "subject.source_url")

    return (
        {
            "repository": repository,
            "change_request": copy.deepcopy(change_request),
            "head_commit": head,
            "comparison": {
                "kind": "merge_base",
                "commit_sha": merge_base,
            },
            "observed_at": observed_at,
        },
        {
            "provider_id": provider_id,
            "repository": repository,
            "change_request": copy.deepcopy(change_request),
            "state": state,
            "head_commit": head,
            "base_commit": base,
            "merge_base_commit": merge_base,
            "source_url": source_url,
            **(
                {"title": title}
                if (title := _optional_summary(subject.get("title"))) is not None
                else {}
            ),
        },
    )


def _coverage(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = _mapping(snapshot.get("coverage"), "coverage")
    result: dict[str, dict[str, Any]] = {}
    for source in (
        "subject",
        "conversation",
        "reviews",
        "review_threads",
        "checks",
    ):
        item = _mapping(coverage.get(source), f"coverage.{source}")
        status = _string(item.get("status"), f"coverage.{source}.status")
        if status not in _ALLOWED_COVERAGE:
            raise ReconciliationInputError(f"coverage.{source}.status is unsupported")
        pages = item.get("pages")
        if type(pages) is not int or pages < 0:
            raise ReconciliationInputError(
                f"coverage.{source}.pages must be a non-negative integer"
            )
        count = item.get("count")
        if count is not None and (type(count) is not int or count < 0):
            raise ReconciliationInputError(
                f"coverage.{source}.count must be a non-negative integer"
            )
        result[source] = {
            "status": status,
            "pages": pages,
            **({"count": count} if count is not None else {}),
        }
    return result


def _review_source_status(coverage: dict[str, dict[str, Any]]) -> str:
    statuses = {
        coverage["reviews"]["status"],
        coverage["review_threads"]["status"],
    }
    for status in ("ERROR", "UNAVAILABLE", "RATE_LIMITED", "PARTIAL"):
        if status in statuses:
            return status
    return "COMPLETE"


def _thread_records_by_review(
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    reviews = snapshot.get("reviews")
    review_threads = snapshot.get("review_threads")
    if not isinstance(reviews, list) or not isinstance(review_threads, list):
        raise ReconciliationInputError("reviews and review_threads must be arrays")

    normalized_reviews = [_mapping(raw_review, "review") for raw_review in reviews]
    review_observation_ids = {
        _string(review.get("observation_id"), "review.observation_id")
        for review in normalized_reviews
    }
    threads_by_review: dict[str, list[dict[str, Any]]] = {}
    for raw_thread in review_threads:
        thread = _mapping(raw_thread, "review_thread")
        review_observation_id = _string(
            thread.get("review_observation_id"),
            "review_thread.review_observation_id",
        )
        _string(thread.get("id"), "review_thread.id")
        thread_state = thread.get("state")
        if thread_state not in {"resolved", "unresolved"}:
            raise ReconciliationInputError(
                "review_thread.state must be resolved or unresolved"
            )
        if review_observation_id not in review_observation_ids:
            raise ReconciliationInputError(
                "review_thread references unknown review observation"
            )
        threads_by_review.setdefault(review_observation_id, []).append(thread)
    return normalized_reviews, threads_by_review


def _observations(
    snapshot: dict[str, Any],
    subject: dict[str, Any],
    provider_id: str,
) -> list[dict[str, Any]]:
    reviews, threads_by_review = _thread_records_by_review(snapshot)

    target_head = subject["head_commit"]
    observations: list[dict[str, Any]] = []
    for raw_review in reviews:
        review = _mapping(raw_review, "review")
        observation_id = _string(
            review.get("observation_id"),
            "review.observation_id",
        )
        reviewer_id = _string(review.get("reviewer_id"), "review.reviewer_id")
        state = _string(
            review.get("recommendation_state"),
            "review.recommendation_state",
        )
        observed_at = _timestamp(review.get("observed_at"), "review.observed_at")
        review_head = review.get("head_commit")

        if isinstance(review_head, str) and _SHA40.fullmatch(review_head):
            bound_head = review_head
            binding_status = "exact" if review_head == target_head else "partial"
        else:
            bound_head = target_head
            binding_status = "unestablished"

        thread_records = threads_by_review.get(observation_id, [])
        thread_states = {item["state"] for item in thread_records}
        aggregate_thread_state = (
            "unresolved" if "unresolved" in thread_states else "resolved"
        )
        observations.append(
            {
                "observation_id": observation_id,
                "reviewer_id": reviewer_id,
                "source_id": "retained-review-evidence",
                "observed_at": observed_at,
                "subject_binding": {
                    "status": binding_status,
                    "repository": subject["repository"],
                    "change_request": copy.deepcopy(subject["change_request"]),
                    "head_commit": bound_head,
                    "comparison": copy.deepcopy(subject["comparison"]),
                },
                "native": {
                    "object_id": observation_id,
                    "revision": 1,
                    "provider": provider_id,
                    "source_url": review.get("source_url"),
                    "review_commit_id": review_head,
                    "recommendation_state": state,
                },
                "findings": [],
                "threads": {
                    "state": aggregate_thread_state,
                    "count": len(thread_records),
                    "thread_ids": sorted(
                        item["id"]
                        for item in thread_records
                        if isinstance(item.get("id"), str)
                    ),
                },
            }
        )
    return observations


def build_review_input(
    snapshot: dict[str, Any],
    protected_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Translate normalized provider state into the existing R2A input contract."""

    subject, provider_subject = _subject(snapshot)
    coverage = _coverage(snapshot)
    bundle = _mapping(protected_bundle, "protected_bundle")
    authority = _mapping(bundle.get("authority"), "protected_bundle.authority")
    judge = _mapping(bundle.get("acquired_judge"), "protected_bundle.acquired_judge")
    qualification = _mapping(
        bundle.get("qualification_snapshot"),
        "protected_bundle.qualification_snapshot",
    )
    observed_at = subject["observed_at"]
    source_status = _review_source_status(coverage)

    return {
        "schema_version": "1.0",
        "subject": subject,
        "evaluation_context": {
            "mode": "current_advisory",
            "as_of": observed_at,
            "judge_relation": "prior_integrated",
            "fixture_only": False,
        },
        "authority": copy.deepcopy(authority),
        "acquired_judge": copy.deepcopy(judge),
        "evidence_set": {
            "observed_at": observed_at,
            "sources": [
                {
                    "source_id": "retained-review-evidence",
                    "status": source_status,
                    "observed_at": observed_at,
                    "snapshot": {
                        "review_pages": coverage["reviews"]["pages"],
                        "review_thread_pages": coverage["review_threads"]["pages"],
                    },
                }
            ],
            "observations": _observations(
                snapshot,
                subject,
                provider_subject["provider_id"],
            ),
        },
        "qualification_snapshot": copy.deepcopy(qualification),
    }


def _projection_coverage(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _coverage(snapshot)


def _check_summary(snapshot: dict[str, Any], target_head: str) -> dict[str, Any]:
    raw_checks = snapshot.get("checks")
    if not isinstance(raw_checks, list):
        raise ReconciliationInputError("checks must be an array")

    latest: dict[str, dict[str, Any]] = {}
    for raw in raw_checks:
        check = _mapping(raw, "check")
        if check.get("head_commit") != target_head:
            continue
        check_id = check.get("id")
        name = check.get("name")
        status = check.get("status")
        if not isinstance(check_id, str) or not check_id:
            continue
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(status, str) or not status:
            continue
        observed_at = _timestamp(check.get("observed_at"), "check.observed_at")
        observed_key = parse_rfc3339(observed_at)
        state = (status, check.get("conclusion"))
        previous = latest.get(name)
        if previous is None or observed_key > previous["observed_key"]:
            latest[name] = {
                "observed_at": observed_at,
                "observed_key": observed_key,
                "states": {state},
            }
        elif observed_key == previous["observed_key"]:
            previous["states"].add(state)

    ambiguous: list[str] = []
    pending: list[str] = []
    non_success: list[str] = []
    for name, item in latest.items():
        states = item["states"]
        if len(states) != 1:
            ambiguous.append(name)
            continue
        status, conclusion = next(iter(states))
        if status != "completed":
            pending.append(name)
        elif conclusion not in {"success", "neutral", "skipped"}:
            non_success.append(name)

    ambiguous.sort()
    pending.sort()
    non_success.sort()
    return {
        "observed_names": len(latest),
        "ambiguous": ambiguous[:32],
        "pending": pending[:32],
        "non_success": non_success[:32],
        "omitted_ambiguous": max(0, len(ambiguous) - 32),
        "omitted_pending": max(0, len(pending) - 32),
        "omitted_non_success": max(0, len(non_success) - 32),
    }


def build_projection(
    snapshot: dict[str, Any],
    *,
    protected_main_revision: str | None,
    outer_consumer: dict[str, Any] | None,
    r2a_result: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Build a bounded non-canonical owner-facing current-state projection."""

    _, provider_subject = _subject(snapshot)
    _thread_records_by_review(snapshot)
    coverage = _projection_coverage(snapshot)
    protected_revision = (
        _sha(protected_main_revision, "protected_main_revision")
        if protected_main_revision is not None
        else None
    )
    consumer = outer_consumer if isinstance(outer_consumer, dict) else None
    runtime_image = (
        _string(consumer.get("runtime_image"), "outer_consumer.runtime_image")
        if consumer is not None
        else None
    )
    runtime_revision = (
        _sha(consumer.get("runtime_revision"), "outer_consumer.runtime_revision")
        if consumer is not None
        else None
    )
    protected_status = (
        "AVAILABLE"
        if protected_revision is not None
        and runtime_image is not None
        and runtime_revision is not None
        else "PARTIAL"
        if any(
            item is not None
            for item in (protected_revision, runtime_image, runtime_revision)
        )
        else "UNAVAILABLE"
    )

    execution_id = _string(
        execution.get("execution_id"),
        "execution.execution_id",
    )
    execution_observed_at = _timestamp(
        execution.get("observed_at"),
        "execution.observed_at",
    )

    outcome = r2a_result.get("outcome")
    if isinstance(outcome, str) and outcome in _SEMANTIC_OUTCOMES:
        r2a_status = "SEMANTIC_RESULT"
        semantic_outcome = outcome
        reason = _string(r2a_result.get("reason"), "r2a_result.reason")
        if r2a_result.get("binding") is not False:
            raise ReconciliationInputError("R2A semantic result must be non-binding")
    else:
        r2a_status = "UNAVAILABLE"
        semantic_outcome = "UNAVAILABLE"
        raw_reason = r2a_result.get("reason")
        reason = raw_reason if isinstance(raw_reason, str) and raw_reason else "NOT_RUN"

    observed_r2a = {
        "status": r2a_status,
        "outcome": semantic_outcome,
        "reason": reason,
        "binding": False,
    }
    complete = all(item["status"] == "COMPLETE" for item in coverage.values())
    provider_current = provider_subject["state"] == "open" and complete
    currentness = (
        "CURRENT_AT_OBSERVATION" if provider_current else "INCOMPLETE_AT_OBSERVATION"
    )
    projection_r2a = (
        observed_r2a
        if provider_current
        else {
            "status": "NON_CURRENT",
            "outcome": "UNAVAILABLE",
            "reason": "PROVIDER_STATE_INCOMPLETE",
            "binding": False,
            "observed": observed_r2a,
        }
    )
    checks = _check_summary(snapshot, provider_subject["head_commit"])
    if provider_subject["state"] != "open" or not complete:
        next_action = "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE"
    elif protected_status != "AVAILABLE":
        next_action = "WAIT_FOR_PROTECTED_CAPABILITY"
    elif checks["ambiguous"]:
        next_action = "RECONCILE_PROVIDER_CHECKS"
    elif checks["pending"]:
        next_action = "WAIT_FOR_PROVIDER_CHECKS"
    elif checks["non_success"]:
        next_action = "RECONCILE_PROVIDER_CHECKS"
    else:
        next_action = {
            "PASS": "CONTINUE_EXISTING_WORKFLOW",
            "BLOCKED": "RECONCILE_REVIEW_EVIDENCE",
            "CONFLICTING": "RECONCILE_REVIEW_EVIDENCE",
            "INCOMPLETE": "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE",
            "UNAVAILABLE": "WAIT_FOR_PROTECTED_CAPABILITY",
        }[semantic_outcome]

    return {
        "schema_version": _INTERNAL_SCHEMA_VERSION,
        "status": "draft",
        "non_canonical": True,
        "subject": provider_subject,
        "coverage": coverage,
        "checks": checks,
        "protected": {
            "status": protected_status,
            "main_revision": protected_revision,
            "outer_runtime_image": runtime_image,
            "outer_runtime_revision": runtime_revision,
        },
        "r2a": projection_r2a,
        "currentness": currentness,
        "next_permitted_action": next_action,
        "observation": {
            "observed_at": snapshot["observed_at"],
            "execution_observed_at": execution_observed_at,
            "execution_id": execution_id,
        },
    }


def _encode_projection(projection: dict[str, Any]) -> str:
    raw = canonical_json(projection).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def render_projection(projection: dict[str, Any]) -> str:
    """Render one bounded replaceable provider-neutral status projection."""

    subject = _mapping(projection.get("subject"), "projection.subject")
    change_request = _mapping(
        subject.get("change_request"),
        "projection.subject.change_request",
    )
    r2a = _mapping(projection.get("r2a"), "projection.r2a")
    protected = _mapping(projection.get("protected"), "projection.protected")
    observation = _mapping(projection.get("observation"), "projection.observation")
    coverage = _mapping(projection.get("coverage"), "projection.coverage")
    checks = _mapping(projection.get("checks"), "projection.checks")

    coverage_text = ", ".join(
        f"{name}={_mapping(value, f'coverage.{name}').get('status')}"
        for name, value in sorted(coverage.items())
    )
    provider_literal = _markdown_code(
        subject.get("provider_id"),
        "projection.subject.provider_id",
    )
    repository_literal = _markdown_code(
        subject.get("repository"),
        "projection.subject.repository",
    )
    change_kind_literal = _markdown_code(
        change_request.get("kind"),
        "projection.subject.change_request.kind",
    )
    change_id_literal = _markdown_code(
        change_request.get("id"),
        "projection.subject.change_request.id",
    )
    execution_literal = _markdown_code(
        observation.get("execution_id"),
        "projection.observation.execution_id",
    )

    lines = [
        f"<!-- gnostoa:l1-current-state:v1:{_encode_projection(projection)} -->",
        "## Gnostoa current-state advisory",
        "",
        "**Non-canonical diagnostic projection. It grants no approval or merge authority.**",
        "",
        f"- Provider: {provider_literal}",
        f"- Repository: {repository_literal}",
    ]
    title = _optional_summary(subject.get("title"))
    if title is not None:
        literal_title = re.sub(
            r"([\\`*_{}\[\]()#+.!|~-])",
            r"\\\1",
            html.escape(title, quote=False),
        )
        lines.append(f"- Intent summary: {literal_title}")
    lines.extend(
        [
            (
                f"- Subject: {change_kind_literal} "
                f"{change_id_literal} at `{subject['head_commit']}`"
            ),
            (
                f"- Base / merge-base: `{subject['base_commit']}` / "
                f"`{subject['merge_base_commit']}`"
            ),
            f"- Observation cut: `{observation['observed_at']}`",
            f"- Coverage: {coverage_text}",
            (
                f"- Checks: observed={checks['observed_names']}, "
                f"ambiguous={len(checks['ambiguous'])}, "
                f"pending={len(checks['pending'])}, "
                f"non-success={len(checks['non_success'])}"
            ),
            (
                f"- Protected authority: **{protected['status']}**; "
                f"main=`{protected.get('main_revision') or 'UNAVAILABLE'}`"
            ),
            (
                "- Protected outer runtime: "
                f"`{protected.get('outer_runtime_image') or 'UNAVAILABLE'}`"
            ),
            f"- R2A: **{r2a['outcome']} / {r2a['reason']}**, binding: false",
            f"- Currentness: **{projection['currentness']}**",
            f"- Next permitted action: `{projection['next_permitted_action']}`",
            f"- Execution generation: {execution_literal}",
            "",
        ]
    )
    rendered = "\n".join(lines)
    if len(rendered.encode("utf-8")) > _MAX_RENDER_BYTES:
        raise ReconciliationInputError("projection exceeds the bounded comment size")
    return rendered


def parse_projection_comment(body: object) -> dict[str, Any] | None:
    if not isinstance(body, str):
        return None
    match = _MARKER.search(body)
    if match is None:
        return None
    encoded = match.group(1)
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode((encoded + padding).encode("ascii"))
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    if document.get("schema_version") != _INTERNAL_SCHEMA_VERSION:
        return None
    if document.get("status") != "draft":
        return None
    return document
