from __future__ import annotations

import base64
import copy
import json
import re
from typing import Any

from .review_model import canonical_json, parse_rfc3339

_INTERNAL_SCHEMA_VERSION = "gnostoa-l1-current-state/v1"
_PROVIDER_SNAPSHOT_VERSION = 1
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_ALLOWED_COVERAGE = {"COMPLETE", "PARTIAL", "RATE_LIMITED", "UNAVAILABLE", "ERROR"}
_SEMANTIC_OUTCOMES = {"PASS", "BLOCKED", "INCOMPLETE", "CONFLICTING"}
_MARKER = re.compile(
    r"<!-- gnostoa:l1-current-state:v1:([A-Za-z0-9_-]+) -->"
)
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


def _subject(snapshot: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if snapshot.get("schema_version") != _PROVIDER_SNAPSHOT_VERSION:
        raise ReconciliationInputError("provider snapshot schema_version is unsupported")
    if snapshot.get("provider") != "github":
        raise ReconciliationInputError("provider snapshot must be GitHub")
    repository = _string(snapshot.get("repository"), "repository")
    if _REPOSITORY.fullmatch(repository) is None:
        raise ReconciliationInputError("repository must be owner/name")
    pull_number = snapshot.get("pull_number")
    if type(pull_number) is not int or pull_number <= 0:
        raise ReconciliationInputError("pull_number must be a positive integer")
    observed_at = _timestamp(snapshot.get("observed_at"), "observed_at")
    subject = _mapping(snapshot.get("subject"), "subject")
    head = _sha(subject.get("head_sha"), "subject.head_sha")
    base = _sha(subject.get("base_sha"), "subject.base_sha")
    merge_base = _sha(subject.get("merge_base_sha"), "subject.merge_base_sha")
    state = _string(subject.get("state"), "subject.state")
    html_url = _string(subject.get("html_url"), "subject.html_url")
    return (
        {
            "repository": f"https://github.com/{repository}",
            "change_request": {
                "kind": "github-pull-request",
                "id": str(pull_number),
            },
            "head_commit": head,
            "comparison": {"kind": "merge_base", "commit_sha": merge_base},
            "observed_at": observed_at,
        },
        {
            "repository": repository,
            "pull_number": pull_number,
            "state": state,
            "head_sha": head,
            "base_sha": base,
            "merge_base_sha": merge_base,
            "html_url": html_url,
        },
    )


def _coverage(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = _mapping(snapshot.get("coverage"), "coverage")
    result: dict[str, dict[str, Any]] = {}
    for source in (
        "pull",
        "issue_comments",
        "reviews",
        "review_comments",
        "check_runs",
    ):
        item = _mapping(coverage.get(source), f"coverage.{source}")
        status = _string(item.get("status"), f"coverage.{source}.status")
        if status not in _ALLOWED_COVERAGE:
            raise ReconciliationInputError(
                f"coverage.{source}.status is unsupported"
            )
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
        coverage["review_comments"]["status"],
    }
    for status in ("ERROR", "UNAVAILABLE", "RATE_LIMITED", "PARTIAL"):
        if status in statuses:
            return status
    return "COMPLETE"


def _observations(
    snapshot: dict[str, Any],
    subject: dict[str, Any],
) -> list[dict[str, Any]]:
    reviews = snapshot.get("reviews")
    review_comments = snapshot.get("review_comments")
    if not isinstance(reviews, list) or not isinstance(review_comments, list):
        raise ReconciliationInputError(
            "reviews and review_comments must be arrays"
        )

    comments_by_review: dict[int, list[dict[str, Any]]] = {}
    for raw_comment in review_comments:
        comment = _mapping(raw_comment, "review_comment")
        review_id = comment.get("pull_request_review_id")
        comment_id = comment.get("id")
        if type(review_id) is not int or type(comment_id) is not int:
            continue
        comments_by_review.setdefault(review_id, []).append(comment)

    target_head = subject["head_commit"]
    observations: list[dict[str, Any]] = []
    for raw_review in reviews:
        review = _mapping(raw_review, "review")
        review_id = review.get("id")
        if type(review_id) is not int:
            raise ReconciliationInputError("review.id must be an integer")
        author = _string(review.get("author"), "review.author")
        state = _string(review.get("state"), "review.state")
        observed_at = _timestamp(review.get("submitted_at"), "review.submitted_at")
        commit_id = review.get("commit_id")

        if isinstance(commit_id, str) and _SHA40.fullmatch(commit_id):
            bound_head = commit_id
            binding_status = "exact" if commit_id == target_head else "partial"
        else:
            bound_head = target_head
            binding_status = "unestablished"

        thread_records = comments_by_review.get(review_id, [])
        observations.append(
            {
                "observation_id": f"github-review-{review_id}",
                "reviewer_id": author,
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
                    "object_id": f"github-pull-review-{review_id}",
                    "revision": 1,
                    "provider": "github",
                    "source_url": review.get("html_url"),
                    "review_commit_id": commit_id,
                    "recommendation_state": state,
                },
                "findings": [],
                "threads": {
                    "state": "observed",
                    "count": len(thread_records),
                    "comment_ids": sorted(
                        item["id"]
                        for item in thread_records
                        if type(item.get("id")) is int
                    ),
                },
            }
        )
    return observations


def build_review_input(
    snapshot: dict[str, Any],
    protected_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Translate normalized GitHub state into the existing R2A input contract."""

    subject, _ = _subject(snapshot)
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
                        "review_comment_pages": coverage["review_comments"]["pages"],
                    },
                }
            ],
            "observations": _observations(snapshot, subject),
        },
        "qualification_snapshot": copy.deepcopy(qualification),
    }


def _projection_coverage(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _coverage(snapshot)


def build_projection(
    snapshot: dict[str, Any],
    *,
    protected_main_revision: str,
    outer_consumer: dict[str, Any],
    r2a_result: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Build a bounded non-canonical owner-facing current-state projection."""

    _, provider_subject = _subject(snapshot)
    coverage = _projection_coverage(snapshot)
    protected_revision = _sha(
        protected_main_revision,
        "protected_main_revision",
    )
    consumer = _mapping(outer_consumer, "outer_consumer")
    runtime_image = _string(consumer.get("runtime_image"), "outer_consumer.runtime_image")
    runtime_revision = _sha(
        consumer.get("runtime_revision"),
        "outer_consumer.runtime_revision",
    )

    run_id = execution.get("run_id")
    run_attempt = execution.get("run_attempt")
    if type(run_id) is not int or run_id <= 0:
        raise ReconciliationInputError("execution.run_id must be a positive integer")
    if type(run_attempt) is not int or run_attempt <= 0:
        raise ReconciliationInputError(
            "execution.run_attempt must be a positive integer"
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

    complete = all(item["status"] == "COMPLETE" for item in coverage.values())
    currentness = (
        "CURRENT_AT_OBSERVATION"
        if provider_subject["state"] == "open" and complete
        else "INCOMPLETE_AT_OBSERVATION"
    )
    next_action = {
        "PASS": "CONTINUE_EXISTING_WORKFLOW",
        "BLOCKED": "RECONCILE_REVIEW_EVIDENCE",
        "CONFLICTING": "RECONCILE_REVIEW_EVIDENCE",
        "INCOMPLETE": "WAIT_OR_RECONCILE_REQUIRED_EVIDENCE",
        "UNAVAILABLE": "WAIT_FOR_PROTECTED_CAPABILITY",
    }[semantic_outcome]

    return {
        "schema_version": _INTERNAL_SCHEMA_VERSION,
        "non_canonical": True,
        "subject": provider_subject,
        "coverage": coverage,
        "protected": {
            "main_revision": protected_revision,
            "outer_runtime_image": runtime_image,
            "outer_runtime_revision": runtime_revision,
        },
        "r2a": {
            "status": r2a_status,
            "outcome": semantic_outcome,
            "reason": reason,
            "binding": False,
        },
        "currentness": currentness,
        "next_permitted_action": next_action,
        "observation": {
            "observed_at": snapshot["observed_at"],
            "execution_observed_at": execution_observed_at,
            "run_id": run_id,
            "run_attempt": run_attempt,
        },
    }


def _encode_projection(projection: dict[str, Any]) -> str:
    raw = canonical_json(projection).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def render_projection(projection: dict[str, Any]) -> str:
    """Render one bounded replaceable PR comment without raw provider bodies."""

    subject = _mapping(projection.get("subject"), "projection.subject")
    r2a = _mapping(projection.get("r2a"), "projection.r2a")
    protected = _mapping(projection.get("protected"), "projection.protected")
    observation = _mapping(projection.get("observation"), "projection.observation")
    coverage = _mapping(projection.get("coverage"), "projection.coverage")

    coverage_text = ", ".join(
        f"{name}={_mapping(value, f'coverage.{name}').get('status')}"
        for name, value in sorted(coverage.items())
    )
    rendered = "\n".join(
        [
            f"<!-- gnostoa:l1-current-state:v1:{_encode_projection(projection)} -->",
            "## Gnostoa current-state advisory",
            "",
            "**Non-canonical diagnostic projection. It grants no approval or merge authority.**",
            "",
            f"- Subject: PR #{subject['pull_number']} at \`{subject['head_sha']}\`",
            f"- Base / merge-base: \`{subject['base_sha']}\` / \`{subject['merge_base_sha']}\`",
            f"- Observation cut: \`{observation['observed_at']}\`",
            f"- Coverage: {coverage_text}",
            f"- Protected main: \`{protected['main_revision']}\`",
            f"- Protected outer runtime: \`{protected['outer_runtime_image']}\`",
            f"- R2A: **{r2a['outcome']} / {r2a['reason']}**, binding: false",
            f"- Currentness: **{projection['currentness']}**",
            f"- Next permitted action: \`{projection['next_permitted_action']}\`",
            f"- Execution generation: run \`{observation['run_id']}\`, attempt \`{observation['run_attempt']}\`",
            "",
        ]
    )
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
    return document
