from __future__ import annotations

import base64
import copy
import hashlib
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
_MAX_RENDERED_CHECK_NAMES = 8
_MAX_CHECK_NAMES = _MAX_RENDERED_CHECK_NAMES
# Compatibility is only for already-owned pre-bound projections. Retire it once
# repository-wide inventory finds no open change request whose owned projection
# is accepted only by the legacy parser: every such projection has been rewritten
# by the strict bounded reconciler or its change request has closed.
_PRE_BOUND_MAX_CHECK_NAMES = 32
_MAX_CHECK_LABEL_BYTES = 128


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


def _bounded_check_label(value: str) -> str:
    raw = value.encode("utf-8")
    if len(raw) <= _MAX_CHECK_LABEL_BYTES:
        return value
    digest = hashlib.sha256(raw).hexdigest()[:12]
    suffix = f"...#{digest}"
    budget = _MAX_CHECK_LABEL_BYTES - len(suffix.encode("ascii"))
    prefix = raw[:budget].decode("utf-8", errors="ignore")
    return prefix + suffix


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
    padding = " " if escaped.startswith("`") or escaped.endswith("`") else ""
    return f"{fence}{padding}{escaped}{padding}{fence}"


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
    title = _optional_summary(subject.get("title"))

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
            **({"title": title} if title is not None else {}),
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
        if type(count) is not int or count < 0:
            raise ReconciliationInputError(
                f"coverage.{source}.count must be a non-negative integer"
            )
        result[source] = {
            "status": status,
            "pages": pages,
            "count": count,
        }
    return result


def _validate_source_payloads(
    snapshot: dict[str, Any],
    coverage: dict[str, dict[str, Any]],
) -> None:
    if coverage["subject"]["count"] != 1:
        raise ReconciliationInputError("coverage.subject.count must equal one subject")

    for source in ("conversation", "reviews", "review_threads", "checks"):
        payload = snapshot.get(source)
        if not isinstance(payload, list):
            raise ReconciliationInputError(f"{source} must be an array")
        if coverage[source]["count"] != len(payload):
            raise ReconciliationInputError(
                f"coverage.{source}.count does not match retained payload"
            )


def _validate_temporal_integrity(snapshot: dict[str, Any]) -> None:
    cut_text = _timestamp(snapshot.get("observed_at"), "observed_at")
    cut = parse_rfc3339(cut_text)
    for source in ("reviews", "review_threads", "checks"):
        payload = snapshot.get(source)
        if not isinstance(payload, list):
            raise ReconciliationInputError(f"{source} must be an array")
        for index, raw_item in enumerate(payload):
            item = _mapping(raw_item, f"{source}[{index}]")
            observed_at = _timestamp(
                item.get("observed_at"),
                f"{source}[{index}].observed_at",
            )
            if parse_rfc3339(observed_at) > cut:
                raise ReconciliationInputError(
                    f"{source}[{index}].observed_at is later than "
                    "snapshot observation cut"
                )


def _review_source_status(coverage: dict[str, dict[str, Any]]) -> str:
    statuses = {
        coverage["reviews"]["status"],
        coverage["review_threads"]["status"],
    }
    for status in ("ERROR", "UNAVAILABLE", "RATE_LIMITED", "PARTIAL"):
        if status in statuses:
            return status
    return "COMPLETE"


def _review_payloads(
    snapshot: dict[str, Any],
) -> tuple[list[object], list[object]]:
    reviews = snapshot.get("reviews")
    review_threads = snapshot.get("review_threads")
    if not isinstance(reviews, list) or not isinstance(review_threads, list):
        raise ReconciliationInputError("reviews and review_threads must be arrays")
    return reviews, review_threads


def _normalize_review(
    raw_review: object,
    review_observation_ids: set[str],
) -> dict[str, Any]:
    review = _mapping(raw_review, "review")
    observation_id = _string(
        review.get("observation_id"),
        "review.observation_id",
    )
    if observation_id in review_observation_ids:
        raise ReconciliationInputError("duplicate review observation_id")

    _string(review.get("reviewer_id"), "review.reviewer_id")
    _string(review.get("recommendation_state"), "review.recommendation_state")
    _timestamp(review.get("observed_at"), "review.observed_at")
    head_commit = review.get("head_commit")
    if head_commit is not None:
        _sha(head_commit, "review.head_commit")
    source_url = review.get("source_url")
    if source_url is not None:
        _string(source_url, "review.source_url")
    effective = review.get("effective")
    if effective is not None and type(effective) is not bool:
        raise ReconciliationInputError("review.effective must be a boolean")

    review_observation_ids.add(observation_id)
    return review


def _normalize_review_thread(
    raw_thread: object,
    *,
    review_observation_ids: set[str],
    thread_ids: set[str],
) -> tuple[str, dict[str, Any]]:
    thread = _mapping(raw_thread, "review_thread")
    review_observation_id = _string(
        thread.get("review_observation_id"),
        "review_thread.review_observation_id",
    )
    thread_id = _string(thread.get("id"), "review_thread.id")
    if thread_id in thread_ids:
        raise ReconciliationInputError("duplicate review_thread.id")
    thread_ids.add(thread_id)

    _string(thread.get("reviewer_id"), "review_thread.reviewer_id")
    _timestamp(thread.get("observed_at"), "review_thread.observed_at")
    head_commit = thread.get("head_commit")
    if head_commit is not None:
        _sha(head_commit, "review_thread.head_commit")
    if not isinstance(thread.get("body"), str):
        raise ReconciliationInputError("review_thread.body must be a string")
    source_url = thread.get("source_url")
    if source_url is not None:
        _string(source_url, "review_thread.source_url")
    if thread.get("state") not in {"resolved", "unresolved"}:
        raise ReconciliationInputError(
            "review_thread.state must be resolved or unresolved"
        )
    if review_observation_id not in review_observation_ids:
        raise ReconciliationInputError(
            "review_thread references unknown review observation"
        )
    return review_observation_id, thread


def _thread_records_by_review(
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    reviews, review_threads = _review_payloads(snapshot)

    normalized_reviews: list[dict[str, Any]] = []
    review_observation_ids: set[str] = set()
    for raw_review in reviews:
        normalized_reviews.append(_normalize_review(raw_review, review_observation_ids))

    threads_by_review: dict[str, list[dict[str, Any]]] = {}
    thread_ids: set[str] = set()
    for raw_thread in review_threads:
        review_observation_id, thread = _normalize_review_thread(
            raw_thread,
            review_observation_ids=review_observation_ids,
            thread_ids=thread_ids,
        )
        threads_by_review.setdefault(review_observation_id, []).append(thread)

    return normalized_reviews, threads_by_review


def _observation_binding(
    *,
    target_head: str,
    review_head: object,
    binding_head: object | None,
) -> tuple[str, str]:
    subject_head = review_head if binding_head is None else binding_head
    if subject_head is None:
        return target_head, "unestablished"

    bound_head = _sha(subject_head, "review.subject_binding.head_commit")
    status = "exact" if bound_head == target_head else "partial"
    return bound_head, status


def _make_observation(
    *,
    subject: dict[str, Any],
    provider_id: str,
    target_head: str,
    observation_id: str,
    reviewer_id: str,
    state: str,
    observed_at: str,
    review_head: object,
    source_url: object,
    thread_records: list[dict[str, Any]],
    binding_head: object | None = None,
    native_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bound_head, binding_status = _observation_binding(
        target_head=target_head,
        review_head=review_head,
        binding_head=binding_head,
    )
    thread_states = {item["state"] for item in thread_records}
    aggregate_thread_state = (
        "unresolved" if "unresolved" in thread_states else "resolved"
    )
    return {
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
            "source_url": source_url,
            "review_commit_id": review_head,
            "recommendation_state": state,
            **({} if native_extra is None else copy.deepcopy(native_extra)),
        },
        "findings": [],
        "threads": {
            "state": aggregate_thread_state,
            "count": len(thread_records),
            "thread_ids": sorted(
                item["id"] for item in thread_records if isinstance(item.get("id"), str)
            ),
        },
    }


def _partition_review_threads(
    thread_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unresolved = [item for item in thread_records if item["state"] == "unresolved"]
    resolved = [item for item in thread_records if item["state"] == "resolved"]
    return resolved, unresolved


def _thread_evidence_native_extra(
    review: dict[str, Any],
    unresolved_threads: list[dict[str, Any]],
) -> dict[str, Any]:
    observed_at = _timestamp(review.get("observed_at"), "review.observed_at")
    observation_id = _string(
        review.get("observation_id"),
        "review.observation_id",
    )
    thread_origin_times = sorted(
        {
            _timestamp(
                item.get("observed_at"),
                "review_thread.observed_at",
            )
            for item in unresolved_threads
        },
        key=parse_rfc3339,
    )
    thread_origin_heads = sorted(
        {
            _sha(item["head_commit"], "review_thread.head_commit")
            for item in unresolved_threads
            if item.get("head_commit") is not None
        }
    )
    native_extra: dict[str, Any] = {
        "thread_evidence_only": True,
        "origin_review_observation_id": observation_id,
        "origin_review_observed_at": observed_at,
        "origin_thread_observed_at": thread_origin_times,
        "origin_thread_head_commits": thread_origin_heads,
    }
    if review.get("effective") is False:
        native_extra.update(
            {
                "superseded_review_observation_id": observation_id,
                "superseded_recommendation_state": _string(
                    review.get("recommendation_state"),
                    "review.recommendation_state",
                ),
            }
        )
    return native_extra


def _thread_evidence_observation_id(
    origin_observation_id: str,
    occupied_observation_ids: set[str],
) -> str:
    legacy_id = f"gnostoa-thread-evidence::{origin_observation_id}"
    if legacy_id not in occupied_observation_ids:
        return legacy_id

    probe = 0
    while True:
        if probe == 0:
            digest_payload = origin_observation_id.encode("utf-8")
        else:
            digest_payload = canonical_json(
                {
                    "namespace": "gnostoa-thread-evidence/v2",
                    "origin_observation_id": origin_observation_id,
                    "probe": probe,
                }
            ).encode("utf-8")
        candidate = (
            "gnostoa-thread-evidence:v2:sha256:"
            + hashlib.sha256(digest_payload).hexdigest()
        )
        if candidate not in occupied_observation_ids:
            return candidate
        probe += 1


def _derived_thread_observation(
    *,
    review: dict[str, Any],
    unresolved_threads: list[dict[str, Any]],
    occupied_observation_ids: set[str],
    subject: dict[str, Any],
    provider_id: str,
    target_head: str,
    snapshot_cut: str,
) -> dict[str, Any] | None:
    if not unresolved_threads:
        return None

    observation_id = _string(
        review.get("observation_id"),
        "review.observation_id",
    )
    thread_observation_id = _thread_evidence_observation_id(
        observation_id,
        occupied_observation_ids,
    )

    return _make_observation(
        subject=subject,
        provider_id=provider_id,
        target_head=target_head,
        observation_id=thread_observation_id,
        reviewer_id=_string(review.get("reviewer_id"), "review.reviewer_id"),
        state="COMMENT_ONLY",
        observed_at=snapshot_cut,
        review_head=review.get("head_commit"),
        source_url=review.get("source_url"),
        thread_records=unresolved_threads,
        binding_head=target_head,
        native_extra=_thread_evidence_native_extra(review, unresolved_threads),
    )


def _observations(
    snapshot: dict[str, Any],
    subject: dict[str, Any],
    provider_id: str,
) -> list[dict[str, Any]]:
    reviews, threads_by_review = _thread_records_by_review(snapshot)
    target_head = subject["head_commit"]
    snapshot_cut = _timestamp(subject.get("observed_at"), "subject.observed_at")
    occupied_observation_ids = {
        _string(review.get("observation_id"), "review.observation_id")
        for review in reviews
        if review.get("effective") is not False
    }
    observations: list[dict[str, Any]] = []

    for review in reviews:
        observation_id = _string(
            review.get("observation_id"),
            "review.observation_id",
        )
        thread_records = threads_by_review.get(observation_id, [])
        resolved_threads, unresolved_threads = _partition_review_threads(thread_records)

        if review.get("effective") is not False:
            observations.append(
                _make_observation(
                    subject=subject,
                    provider_id=provider_id,
                    target_head=target_head,
                    observation_id=observation_id,
                    reviewer_id=_string(
                        review.get("reviewer_id"),
                        "review.reviewer_id",
                    ),
                    state=_string(
                        review.get("recommendation_state"),
                        "review.recommendation_state",
                    ),
                    observed_at=_timestamp(
                        review.get("observed_at"),
                        "review.observed_at",
                    ),
                    review_head=review.get("head_commit"),
                    source_url=review.get("source_url"),
                    thread_records=resolved_threads,
                )
            )

        thread_observation = _derived_thread_observation(
            review=review,
            unresolved_threads=unresolved_threads,
            occupied_observation_ids=occupied_observation_ids,
            subject=subject,
            provider_id=provider_id,
            target_head=target_head,
            snapshot_cut=snapshot_cut,
        )
        if thread_observation is not None:
            observations.append(thread_observation)
            occupied_observation_ids.add(thread_observation["observation_id"])

    return observations


def build_review_input(
    snapshot: dict[str, Any],
    protected_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Translate normalized provider state into the existing R2A input contract."""

    subject, provider_subject = _subject(snapshot)
    coverage = _coverage(snapshot)
    _validate_source_payloads(snapshot, coverage)
    _validate_temporal_integrity(snapshot)
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


def _normalize_check(raw_check: object) -> dict[str, Any]:
    check = _mapping(raw_check, "check")
    _string(check.get("id"), "check.id")
    key = _string(check.get("key"), "check.key")
    name = _string(check.get("name"), "check.name")
    head_commit = _sha(check.get("head_commit"), "check.head_commit")
    observed_at = _timestamp(check.get("observed_at"), "check.observed_at")
    status = _string(check.get("status"), "check.status")
    conclusion = check.get("conclusion")
    if conclusion is not None and (not isinstance(conclusion, str) or not conclusion):
        raise ReconciliationInputError(
            "check.conclusion must be null or a non-empty string"
        )
    return {
        "key": key,
        "name": name,
        "head_commit": head_commit,
        "observed_at": observed_at,
        "observed_key": parse_rfc3339(observed_at),
        "status": status,
        "conclusion": conclusion,
    }


def _record_latest_check(
    latest: dict[str, dict[str, Any]],
    check: dict[str, Any],
    target_head: str,
) -> None:
    if check["head_commit"] != target_head:
        return

    key = check["key"]
    state = (check["name"], check["status"], check["conclusion"])
    previous = latest.get(key)
    if previous is None or check["observed_key"] > previous["observed_key"]:
        latest[key] = {
            "observed_at": check["observed_at"],
            "observed_key": check["observed_key"],
            "states": {state},
        }
    elif check["observed_key"] == previous["observed_key"]:
        previous["states"].add(state)


def _latest_checks(
    raw_checks: list[object],
    target_head: str,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for raw_check in raw_checks:
        _record_latest_check(latest, _normalize_check(raw_check), target_head)
    return latest


def _classify_latest_check(
    key: str,
    item: dict[str, Any],
) -> tuple[str, str, str] | None:
    states = item["states"]
    names = sorted({state[0] for state in states})
    name = names[0] if len(names) == 1 else key
    if len(states) != 1:
        return key, name, "ambiguous"

    _, status, conclusion = next(iter(states))
    if status != "completed":
        return key, name, "pending"
    if conclusion not in {"success", "neutral", "skipped"}:
        return key, name, "non_success"
    return None


def _classified_checks(
    latest: dict[str, dict[str, Any]],
) -> list[tuple[str, str, str]]:
    classified: list[tuple[str, str, str]] = []
    for key, item in latest.items():
        result = _classify_latest_check(key, item)
        if result is not None:
            classified.append(result)
    return classified


def _check_categories(
    classified: list[tuple[str, str, str]],
) -> dict[str, list[str]]:
    name_counts: dict[str, int] = {}
    for _, name, _ in classified:
        name_counts[name] = name_counts.get(name, 0) + 1

    categories: dict[str, list[str]] = {
        "ambiguous": [],
        "pending": [],
        "non_success": [],
    }
    for key, name, category in classified:
        label = name if name_counts[name] == 1 else f"{name} [{key}]"
        categories[category].append(_bounded_check_label(label))
    for items in categories.values():
        items.sort()
    return categories


def _retained_check_category(items: list[str]) -> tuple[list[str], int]:
    return (
        items[:_MAX_CHECK_NAMES],
        max(0, len(items) - _MAX_CHECK_NAMES),
    )


def _check_summary(snapshot: dict[str, Any], target_head: str) -> dict[str, Any]:
    raw_checks = snapshot.get("checks")
    if not isinstance(raw_checks, list):
        raise ReconciliationInputError("checks must be an array")

    latest = _latest_checks(raw_checks, target_head)
    categories = _check_categories(_classified_checks(latest))
    ambiguous, omitted_ambiguous = _retained_check_category(categories["ambiguous"])
    pending, omitted_pending = _retained_check_category(categories["pending"])
    non_success, omitted_non_success = _retained_check_category(
        categories["non_success"]
    )
    return {
        "observed_names": len(latest),
        "ambiguous": ambiguous,
        "pending": pending,
        "non_success": non_success,
        "omitted_ambiguous": omitted_ambiguous,
        "omitted_pending": omitted_pending,
        "omitted_non_success": omitted_non_success,
    }


def _protected_projection(
    protected_main_revision: str | None,
    outer_consumer: dict[str, Any] | None,
) -> dict[str, Any]:
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
    status = (
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
    return {
        "status": status,
        "main_revision": protected_revision,
        "outer_runtime_image": runtime_image,
        "outer_runtime_revision": runtime_revision,
    }


def _observed_r2a(r2a_result: dict[str, Any]) -> tuple[dict[str, Any], str]:
    outcome = r2a_result.get("outcome")
    if isinstance(outcome, str) and outcome in _SEMANTIC_OUTCOMES:
        reason = _string(r2a_result.get("reason"), "r2a_result.reason")
        if r2a_result.get("binding") is not False:
            raise ReconciliationInputError("R2A semantic result must be non-binding")
        semantic_outcome = outcome
        status = "SEMANTIC_RESULT"
    else:
        raw_reason = r2a_result.get("reason")
        reason = raw_reason if isinstance(raw_reason, str) and raw_reason else "NOT_RUN"
        semantic_outcome = "UNAVAILABLE"
        status = "UNAVAILABLE"

    return (
        {
            "status": status,
            "outcome": semantic_outcome,
            "reason": reason,
            "binding": False,
        },
        semantic_outcome,
    )


def _provider_is_current(
    state: str,
    coverage: dict[str, dict[str, Any]],
) -> bool:
    return state == "open" and all(
        item["status"] == "COMPLETE" for item in coverage.values()
    )


def _projection_r2a(
    observed_r2a: dict[str, Any],
    *,
    provider_current: bool,
) -> dict[str, Any]:
    if provider_current:
        return observed_r2a
    return {
        "status": "NON_CURRENT",
        "outcome": "UNAVAILABLE",
        "reason": "PROVIDER_STATE_INCOMPLETE",
        "binding": False,
        "observed": observed_r2a,
    }


def _check_category_present(checks: dict[str, Any], name: str) -> bool:
    return bool(checks[name] or checks.get(f"omitted_{name}", 0))


def _next_permitted_action(
    *,
    provider_current: bool,
    protected_status: str,
    checks: dict[str, Any],
    semantic_outcome: str,
) -> str:
    if not provider_current:
        return "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE"
    if protected_status != "AVAILABLE":
        return "WAIT_FOR_PROTECTED_CAPABILITY"
    if _check_category_present(checks, "ambiguous"):
        return "RECONCILE_PROVIDER_CHECKS"
    if _check_category_present(checks, "non_success"):
        return "RECONCILE_PROVIDER_CHECKS"
    if _check_category_present(checks, "pending"):
        return "WAIT_FOR_PROVIDER_CHECKS"
    if semantic_outcome == "PASS":
        return "CONTINUE_EXISTING_WORKFLOW"
    if semantic_outcome in {"BLOCKED", "CONFLICTING"}:
        return "RECONCILE_REVIEW_EVIDENCE"
    if semantic_outcome == "INCOMPLETE":
        return "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE"
    return "WAIT_FOR_PROTECTED_CAPABILITY"


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
    coverage = _projection_coverage(snapshot)
    _validate_source_payloads(snapshot, coverage)
    _validate_temporal_integrity(snapshot)
    _thread_records_by_review(snapshot)

    protected = _protected_projection(protected_main_revision, outer_consumer)
    execution_id = _string(
        execution.get("execution_id"),
        "execution.execution_id",
    )
    execution_observed_at = _timestamp(
        execution.get("observed_at"),
        "execution.observed_at",
    )
    observed_r2a, semantic_outcome = _observed_r2a(r2a_result)
    provider_current = _provider_is_current(provider_subject["state"], coverage)
    projection_r2a = _projection_r2a(
        observed_r2a,
        provider_current=provider_current,
    )
    checks = _check_summary(snapshot, provider_subject["head_commit"])
    next_action = _next_permitted_action(
        provider_current=provider_current,
        protected_status=protected["status"],
        checks=checks,
        semantic_outcome=semantic_outcome,
    )

    return {
        "schema_version": _INTERNAL_SCHEMA_VERSION,
        "status": "draft",
        "non_canonical": True,
        "subject": provider_subject,
        "coverage": coverage,
        "checks": checks,
        "protected": protected,
        "r2a": projection_r2a,
        "currentness": (
            "CURRENT_AT_OBSERVATION"
            if provider_current
            else "INCOMPLETE_AT_OBSERVATION"
        ),
        "next_permitted_action": next_action,
        "observation": {
            "observed_at": snapshot["observed_at"],
            "execution_observed_at": execution_observed_at,
            "execution_id": execution_id,
        },
    }


def _projection_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ReconciliationInputError(f"{label} must be an array")
    result = [_string(item, f"{label}[]") for item in value]
    if len(set(result)) != len(result):
        raise ReconciliationInputError(f"{label} must not contain duplicates")
    return result


def _projection_check_limit(*, allow_legacy_check_bounds: bool) -> int:
    if allow_legacy_check_bounds:
        return _PRE_BOUND_MAX_CHECK_NAMES
    return _MAX_CHECK_NAMES


def _full_retained_check_sizes(*, allow_legacy_check_bounds: bool) -> set[int]:
    if allow_legacy_check_bounds:
        return {_MAX_CHECK_NAMES, _PRE_BOUND_MAX_CHECK_NAMES}
    return {_MAX_CHECK_NAMES}


def _validate_projection_check_category(
    checks: dict[str, Any],
    *,
    name: str,
    allow_legacy_check_bounds: bool,
    seen_names: set[str],
) -> tuple[list[str], int]:
    items = _projection_string_list(
        checks.get(name),
        f"projection.checks.{name}",
    )
    retained_limit = _projection_check_limit(
        allow_legacy_check_bounds=allow_legacy_check_bounds
    )
    if len(items) > retained_limit:
        raise ReconciliationInputError(
            f"projection.checks.{name} exceeds retained label bound"
        )
    if not allow_legacy_check_bounds and any(
        len(item.encode("utf-8")) > _MAX_CHECK_LABEL_BYTES for item in items
    ):
        raise ReconciliationInputError(
            f"projection.checks.{name} label exceeds bounded size"
        )

    overlap = seen_names.intersection(items)
    if overlap:
        raise ReconciliationInputError("projection.checks categories must not overlap")
    seen_names.update(items)

    omitted_name = f"omitted_{name}"
    omitted = checks.get(omitted_name)
    if type(omitted) is not int or omitted < 0:
        raise ReconciliationInputError(
            f"projection.checks.{omitted_name} must be a non-negative integer"
        )
    if omitted and len(items) not in _full_retained_check_sizes(
        allow_legacy_check_bounds=allow_legacy_check_bounds
    ):
        raise ReconciliationInputError(
            f"projection.checks.{omitted_name} requires a full retained list"
        )
    return items, omitted


def _validate_projection_checks(
    value: object,
    *,
    allow_legacy_check_bounds: bool = False,
) -> dict[str, Any]:
    checks = _mapping(value, "projection.checks")
    observed_names = checks.get("observed_names")
    if type(observed_names) is not int or observed_names < 0:
        raise ReconciliationInputError(
            "projection.checks.observed_names must be a non-negative integer"
        )

    result: dict[str, Any] = {"observed_names": observed_names}
    classified = 0
    seen_names: set[str] = set()
    for name in ("ambiguous", "pending", "non_success"):
        items, omitted = _validate_projection_check_category(
            checks,
            name=name,
            allow_legacy_check_bounds=allow_legacy_check_bounds,
            seen_names=seen_names,
        )
        result[name] = items
        result[f"omitted_{name}"] = omitted
        classified += len(items) + omitted

    if classified > observed_names:
        raise ReconciliationInputError(
            "projection.checks classified count exceeds observed names"
        )
    return result


def _validate_projection_protected(value: object) -> str:
    protected = _mapping(value, "projection.protected")
    status = _string(protected.get("status"), "projection.protected.status")

    main_revision = protected.get("main_revision")
    if main_revision is not None:
        _sha(main_revision, "projection.protected.main_revision")
    runtime_image = protected.get("outer_runtime_image")
    if runtime_image is not None:
        _string(runtime_image, "projection.protected.outer_runtime_image")
    runtime_revision = protected.get("outer_runtime_revision")
    if runtime_revision is not None:
        _sha(runtime_revision, "projection.protected.outer_runtime_revision")

    expected_status = (
        "AVAILABLE"
        if main_revision is not None
        and runtime_image is not None
        and runtime_revision is not None
        else "PARTIAL"
        if any(
            item is not None
            for item in (main_revision, runtime_image, runtime_revision)
        )
        else "UNAVAILABLE"
    )
    if status != expected_status:
        raise ReconciliationInputError(
            "projection.protected.status is inconsistent with protected evidence"
        )
    return status


def _validate_projection_observed_r2a(value: object, label: str) -> str:
    r2a = _mapping(value, label)
    status = _string(r2a.get("status"), f"{label}.status")
    outcome = _string(r2a.get("outcome"), f"{label}.outcome")
    _string(r2a.get("reason"), f"{label}.reason")
    if r2a.get("binding") is not False:
        raise ReconciliationInputError(f"{label}.binding must be false")
    if status == "SEMANTIC_RESULT":
        if outcome not in _SEMANTIC_OUTCOMES:
            raise ReconciliationInputError(f"{label}.outcome is unsupported")
    elif status == "UNAVAILABLE":
        if outcome != "UNAVAILABLE":
            raise ReconciliationInputError(
                f"{label}.outcome must be UNAVAILABLE when status is UNAVAILABLE"
            )
    else:
        raise ReconciliationInputError(f"{label}.status is unsupported")
    return outcome


def _validate_projection_header(document: dict[str, Any]) -> None:
    if document.get("schema_version") != _INTERNAL_SCHEMA_VERSION:
        raise ReconciliationInputError("projection schema_version is unsupported")
    if document.get("status") != "draft":
        raise ReconciliationInputError("projection status must be draft")
    if document.get("non_canonical") is not True:
        raise ReconciliationInputError("projection must remain non-canonical")


def _validate_projection_subject(value: object) -> str:
    subject = _mapping(value, "projection.subject")
    _string(subject.get("provider_id"), "projection.subject.provider_id")
    _string(subject.get("repository"), "projection.subject.repository")
    _change_request(
        subject.get("change_request"),
        "projection.subject.change_request",
    )
    state = _string(subject.get("state"), "projection.subject.state")
    _sha(subject.get("head_commit"), "projection.subject.head_commit")
    _sha(subject.get("base_commit"), "projection.subject.base_commit")
    _sha(
        subject.get("merge_base_commit"),
        "projection.subject.merge_base_commit",
    )
    _string(subject.get("source_url"), "projection.subject.source_url")
    return state


def _validate_projection_currentness(
    document: dict[str, Any],
    *,
    state: str,
) -> tuple[dict[str, dict[str, Any]], bool]:
    coverage = _coverage({"coverage": document.get("coverage")})
    provider_current = _provider_is_current(state, coverage)
    expected_currentness = (
        "CURRENT_AT_OBSERVATION" if provider_current else "INCOMPLETE_AT_OBSERVATION"
    )
    currentness = _string(
        document.get("currentness"),
        "projection.currentness",
    )
    if currentness != expected_currentness:
        raise ReconciliationInputError(
            "projection currentness is inconsistent with provider coverage"
        )
    return coverage, provider_current


def _validate_projection_r2a(
    value: object,
    *,
    provider_current: bool,
) -> str:
    r2a = _mapping(value, "projection.r2a")
    if provider_current:
        return _validate_projection_observed_r2a(
            r2a,
            "projection.r2a",
        )

    if (
        r2a.get("status") != "NON_CURRENT"
        or r2a.get("outcome") != "UNAVAILABLE"
        or r2a.get("reason") != "PROVIDER_STATE_INCOMPLETE"
        or r2a.get("binding") is not False
    ):
        raise ReconciliationInputError(
            "incomplete provider evidence requires non-current R2A state"
        )
    _validate_projection_observed_r2a(
        r2a.get("observed"),
        "projection.r2a.observed",
    )
    return "UNAVAILABLE"


def _validate_projection_observation(value: object) -> None:
    observation = _mapping(value, "projection.observation")
    _timestamp(
        observation.get("observed_at"),
        "projection.observation.observed_at",
    )
    _timestamp(
        observation.get("execution_observed_at"),
        "projection.observation.execution_observed_at",
    )
    _string(
        observation.get("execution_id"),
        "projection.observation.execution_id",
    )


def _validate_projection_document(
    document: dict[str, Any],
    *,
    allow_legacy_check_bounds: bool = False,
) -> None:
    _validate_projection_header(document)
    state = _validate_projection_subject(document.get("subject"))
    _, provider_current = _validate_projection_currentness(
        document,
        state=state,
    )
    protected_status = _validate_projection_protected(document.get("protected"))
    checks = _validate_projection_checks(
        document.get("checks"),
        allow_legacy_check_bounds=allow_legacy_check_bounds,
    )
    semantic_outcome = _validate_projection_r2a(
        document.get("r2a"),
        provider_current=provider_current,
    )
    _validate_projection_observation(document.get("observation"))

    expected_action = _next_permitted_action(
        provider_current=provider_current,
        protected_status=protected_status,
        checks=checks,
        semantic_outcome=semantic_outcome,
    )
    next_action = _string(
        document.get("next_permitted_action"),
        "projection.next_permitted_action",
    )
    if next_action != expected_action:
        raise ReconciliationInputError(
            "projection next permitted action is inconsistent with current state"
        )


def _encode_projection(projection: dict[str, Any]) -> str:
    raw = canonical_json(projection).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _render_check_labels(
    checks: dict[str, Any],
    *,
    key: str,
    label: str,
) -> str | None:
    items = _projection_string_list(
        checks.get(key),
        f"projection.checks.{key}",
    )
    omitted_key = f"omitted_{key}"
    omitted = checks.get(omitted_key)
    if type(omitted) is not int or omitted < 0:
        raise ReconciliationInputError(
            f"projection.checks.{omitted_key} must be a non-negative integer"
        )
    if not items and omitted == 0:
        return None

    visible = items[:_MAX_RENDERED_CHECK_NAMES]
    hidden = omitted + max(0, len(items) - len(visible))
    rendered = ", ".join(
        _markdown_code(item, f"projection.checks.{key}[]") for item in visible
    )
    if hidden:
        rendered += f" (+{hidden} more)"
    return f"- {label}: {rendered}"


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
    runtime_image_literal = _markdown_code(
        protected.get("outer_runtime_image") or "UNAVAILABLE",
        "projection.protected.outer_runtime_image",
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
        title_literal = _markdown_code(
            title,
            "projection.subject.title",
        )
        lines.append(f"- Intent summary: {title_literal}")
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
                f"ambiguous={len(checks['ambiguous'])} "
                f"(+{checks['omitted_ambiguous']} omitted), "
                f"pending={len(checks['pending'])} "
                f"(+{checks['omitted_pending']} omitted), "
                f"non-success={len(checks['non_success'])} "
                f"(+{checks['omitted_non_success']} omitted)"
            ),
            *[
                line
                for line in (
                    _render_check_labels(
                        checks,
                        key="ambiguous",
                        label="Ambiguous checks",
                    ),
                    _render_check_labels(
                        checks,
                        key="pending",
                        label="Pending checks",
                    ),
                    _render_check_labels(
                        checks,
                        key="non_success",
                        label="Non-success checks",
                    ),
                )
                if line is not None
            ],
            (
                f"- Protected authority: **{protected['status']}**; "
                f"main=`{protected.get('main_revision') or 'UNAVAILABLE'}`"
            ),
            f"- Protected outer runtime: {runtime_image_literal}",
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


def parse_projection_comment(
    body: object,
    *,
    allow_legacy_check_bounds: bool = False,
) -> dict[str, Any] | None:
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
    except ValueError:
        return None
    if not isinstance(document, dict):
        return None
    try:
        _validate_projection_document(
            document,
            allow_legacy_check_bounds=allow_legacy_check_bounds,
        )
    except ReconciliationInputError:
        return None
    return document
