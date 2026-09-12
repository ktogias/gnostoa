from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from .review_adapter_file import normalize_observation
from .review_model import canonical_digest, parse_rfc3339, semantic_result
from .review_policy import effective_policy_issues

RECOGNIZED_RECOMMENDATIONS = {
    "APPROVE",
    "REQUEST_CHANGES",
    "COMMENT_ONLY",
    "ABSTAIN",
    "UNKNOWN",
}


class ReviewInputError(ValueError):
    def __init__(
        self, code: str, message: str, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = {} if details is None else details


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewInputError("MALFORMED_INVOCATION", f"{name} must be an object")
    return value


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewInputError("MALFORMED_INVOCATION", f"{name} must be an array")
    return value


def _time(value: object, name: str) -> datetime:
    try:
        return parse_rfc3339(value)
    except (TypeError, ValueError) as exc:
        raise ReviewInputError("CONFIGURATION_ERROR", f"invalid {name}: {exc}") from exc


def _fresh(cut: datetime, as_of: datetime, rule: object) -> bool:
    if not isinstance(rule, dict):
        return False
    mode = rule.get("mode")
    if mode == "not_age_sensitive":
        return True
    if mode != "max_age":
        return False
    seconds = rule.get("seconds")
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 0:
        return False
    age = (as_of - cut).total_seconds()
    return 0 <= age <= seconds


def _judge_binding_matches(expected: dict[str, Any], acquired: dict[str, Any]) -> bool:
    fields = (
        "acquisition",
        "source_revision",
        "public_surface_digest",
        "runtime_image",
        "runtime_revision",
        "supported_input_schema_versions",
    )
    return all(expected.get(field) == acquired.get(field) for field in fields)


def _semantic(
    outcome: str,
    reason: str,
    *,
    input_document: dict[str, Any],
    policy_document: dict[str, Any],
    assessments: list[dict[str, Any]] | None = None,
    collection: dict[str, Any] | None = None,
    qualification: dict[str, Any] | None = None,
    quorum: dict[str, Any] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    conflicts: list[dict[str, Any]] | None = None,
    exclusions: list[dict[str, Any]] | None = None,
    diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    return semantic_result(
        outcome,
        reason,
        input_document=input_document,
        policy_document=policy_document,
        assessments=[] if assessments is None else assessments,
        collection={} if collection is None else collection,
        qualification={} if qualification is None else qualification,
        quorum={} if quorum is None else quorum,
        blockers=[] if blockers is None else blockers,
        conflicts=[] if conflicts is None else conflicts,
        exclusions=[] if exclusions is None else exclusions,
        diagnostics=[] if diagnostics is None else diagnostics,
    )


def _exact_subject_binding(binding: object, target: dict[str, Any]) -> bool:
    if not isinstance(binding, dict) or binding.get("status") != "exact":
        return False
    if binding.get("head_commit") != target.get("head_commit"):
        return False
    expected = target.get("comparison")
    observed = binding.get("comparison")
    return (
        isinstance(expected, dict)
        and isinstance(observed, dict)
        and observed == expected
    )


def _prepare_assessments(
    observations: list[Any],
    target: dict[str, Any],
    policy: dict[str, Any],
    as_of: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    recognized = set(policy.get("collection", {}).get("recognized_sources", []))
    observation_rule = policy.get("subject", {}).get("observation_freshness", {})
    assessments: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    normalized_rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for raw in observations:
        observation = _mapping(raw, "review observation")
        observation_id = observation.get("observation_id")
        if isinstance(observation_id, str) and observation_id in seen_ids:
            continue
        if isinstance(observation_id, str):
            seen_ids.add(observation_id)
        assessment, claim_mismatches = normalize_observation(observation)
        if claim_mismatches:
            raise ReviewInputError(
                "CONFIGURATION_ERROR",
                "caller-supplied normalization claims conflict with active-adapter recomputation",
                details={
                    "observation_id": observation_id,
                    "mismatches": claim_mismatches,
                },
            )
        normalized_rows.append((observation, assessment))

    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    ungrouped: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in normalized_rows:
        native = row[0].get("native")
        object_id = native.get("object_id") if isinstance(native, dict) else None
        if isinstance(object_id, str) and object_id:
            grouped[object_id].append(row)
        else:
            ungrouped.append(row)

    semantic_rows: list[tuple[dict[str, Any], dict[str, Any]]] = list(ungrouped)
    for rows in grouped.values():
        revisions = [
            row[0].get("native", {}).get("revision")
            if isinstance(row[0].get("native"), dict)
            else None
            for row in rows
        ]
        if len(rows) > 1 and all(
            isinstance(item, int) and not isinstance(item, bool) for item in revisions
        ):
            highest = max(int(item) for item in revisions)
            for row, revision in zip(rows, revisions, strict=True):
                if revision == highest:
                    semantic_rows.append(row)
                else:
                    row[1]["exclusion_reasons"].append("superseded_revision")
                    exclusions.append(
                        {
                            "observation_id": row[1].get("observation_id"),
                            "reason": "superseded_revision",
                        }
                    )
                    assessments.append(row[1])
        else:
            semantic_rows.extend(rows)

    for observation, assessment in semantic_rows:
        reasons: list[str] = []
        if not _exact_subject_binding(observation.get("subject_binding"), target):
            reasons.append("subject_not_exact")
        source = observation.get("source_id")
        if not isinstance(source, str) or not source or source not in recognized:
            reasons.append("source_not_recognized")
        observed_at = _time(observation.get("observed_at"), "observation observed_at")
        if observed_at > as_of:
            raise ReviewInputError(
                "CONFIGURATION_ERROR",
                "observation cut is later than EvaluationContext.as_of",
                details={"observation_id": observation.get("observation_id")},
            )
        if not _fresh(observed_at, as_of, observation_rule):
            reasons.append("observation_not_current")
        if (
            assessment.get("normalized_recommendation")
            not in RECOGNIZED_RECOMMENDATIONS
        ):
            reasons.append("normalization_unrecognized")
        assessment["eligible"] = not reasons
        assessment["exclusion_reasons"] = sorted(set(reasons))
        assessments.append(assessment)
        if reasons:
            exclusions.append(
                {
                    "observation_id": assessment.get("observation_id"),
                    "reasons": sorted(set(reasons)),
                }
            )
        else:
            active.append(assessment)

    assessments.sort(key=lambda item: str(item.get("observation_id")))
    active.sort(key=lambda item: str(item.get("observation_id")))
    return assessments, active, exclusions


def evaluate(
    input_document: dict[str, Any],
    policy_document: dict[str, Any],
) -> dict[str, Any]:
    if input_document.get("schema_version") != "1.0":
        raise ReviewInputError(
            "UNSUPPORTED_INPUT", "unsupported review-check input schema_version"
        )
    if policy_document.get("schema_version") != "1.0":
        raise ReviewInputError(
            "CONFIGURATION_ERROR", "unsupported review policy schema_version"
        )

    context = _mapping(input_document.get("evaluation_context"), "evaluation_context")
    as_of = _time(context.get("as_of"), "EvaluationContext.as_of")
    mode = context.get("mode")
    relation = context.get("judge_relation")
    fixture_only = context.get("fixture_only", False)
    if not isinstance(fixture_only, bool):
        raise ReviewInputError(
            "CONFIGURATION_ERROR", "fixture_only must be boolean when supplied"
        )
    if mode not in {"current_advisory", "historical_replay"}:
        raise ReviewInputError("CONFIGURATION_ERROR", "evaluation mode is unsupported")
    if relation not in {"prior_integrated", "candidate_under_test"}:
        raise ReviewInputError("CONFIGURATION_ERROR", "judge_relation is unsupported")
    if mode == "current_advisory" and fixture_only:
        raise ReviewInputError(
            "CONFIGURATION_ERROR", "current_advisory cannot be fixture-only"
        )

    target = _mapping(input_document.get("subject"), "subject")
    target_cut = _time(target.get("observed_at"), "subject observed_at")
    if target_cut > as_of:
        raise ReviewInputError(
            "CONFIGURATION_ERROR", "subject cut is later than EvaluationContext.as_of"
        )
    comparison = _mapping(target.get("comparison"), "subject comparison")
    if comparison.get("kind") != "merge_base" or not isinstance(
        comparison.get("commit_sha"), str
    ):
        raise ReviewInputError(
            "CONFIGURATION_ERROR",
            "v1 subject comparison must be an exact merge_base commit",
        )

    authority = _mapping(input_document.get("authority"), "authority")
    expected_judge = _mapping(
        authority.get("expected_judge"), "authority.expected_judge"
    )
    acquired_judge = _mapping(input_document.get("acquired_judge"), "acquired_judge")
    qualification_snapshot = _mapping(
        input_document.get("qualification_snapshot"), "qualification_snapshot"
    )

    if authority.get("policy_digest") != canonical_digest(policy_document):
        return _semantic(
            "INCOMPLETE",
            "POLICY_AUTHORITY_UNRESOLVED",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=[
                "effective policy digest does not match authority-owned policy digest"
            ],
        )
    if authority.get("qualification_snapshot_digest") != canonical_digest(
        qualification_snapshot
    ):
        return _semantic(
            "INCOMPLETE",
            "QUALIFICATION_AUTHORITY_UNRESOLVED",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=[
                "qualification snapshot digest does not match authority binding"
            ],
        )

    policy_issues = effective_policy_issues(policy_document)
    if policy_issues:
        return _semantic(
            "INCOMPLETE",
            "POLICY_UNRESOLVED",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=policy_issues,
        )

    if not _judge_binding_matches(expected_judge, acquired_judge):
        return _semantic(
            "INCOMPLETE",
            "JUDGE_BINDING_UNRESOLVED",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=[
                "acquired judge does not exactly match authority-owned judge binding"
            ],
        )
    if (
        expected_judge.get("status") != "accepted"
        or acquired_judge.get("status") != "accepted"
    ):
        return _semantic(
            "INCOMPLETE",
            "JUDGE_UNAVAILABLE",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=["judge status is not accepted"],
        )
    if relation == "prior_integrated" and acquired_judge.get("acquisition") != "oci":
        return _semantic(
            "INCOMPLETE",
            "JUDGE_NOT_PRIOR_INTEGRATED",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=[
                "v1 prior-integrated judge must use the authority-bound OCI route"
            ],
        )
    supported = acquired_judge.get("supported_input_schema_versions")
    if (
        not isinstance(supported, list)
        or input_document.get("schema_version") not in supported
    ):
        raise ReviewInputError(
            "UNSUPPORTED_INPUT",
            "selected judge does not support the input schema version",
        )
    if mode == "current_advisory" and relation != "prior_integrated":
        return _semantic(
            "INCOMPLETE",
            "BOOTSTRAP_JUDGE_UNAVAILABLE",
            input_document=input_document,
            policy_document=policy_document,
            diagnostics=["current advisory evaluation has no prior-integrated judge"],
        )
    if mode == "historical_replay" and not fixture_only:
        qualifier = qualification_snapshot.get("qualifying_authority")
        fixture_entries = qualification_snapshot.get("entries", [])
        fixture_basis = (
            any(
                isinstance(entry, dict)
                and isinstance(entry.get("provenance"), dict)
                and str(entry["provenance"].get("basis", "")).startswith("fixture")
                for entry in fixture_entries
            )
            if isinstance(fixture_entries, list)
            else False
        )
        if (
            str(qualifier).startswith("fixture")
            or fixture_basis
            or relation == "candidate_under_test"
        ):
            return _semantic(
                "INCOMPLETE",
                "HISTORICAL_REPLAY_PROVENANCE_UNRESOLVED",
                input_document=input_document,
                policy_document=policy_document,
                diagnostics=[
                    "bootstrap synthetic historical replay requires explicit fixture_only:true"
                ],
            )

    subject_rule = policy_document.get("subject", {}).get("freshness", {})
    target_current = _fresh(target_cut, as_of, subject_rule)

    evidence_set = _mapping(input_document.get("evidence_set"), "evidence_set")
    sources = _list(evidence_set.get("sources"), "evidence_set.sources")
    observations = _list(evidence_set.get("observations"), "evidence_set.observations")
    required_sources = list(
        policy_document.get("collection", {}).get("required_sources", [])
    )
    source_rule = policy_document.get("collection", {}).get("freshness", {})
    sources_by_id: dict[str, dict[str, Any]] = {}
    source_diagnostics: list[str] = []
    for raw_source in sources:
        source = _mapping(raw_source, "collection source")
        source_id = source.get("source_id")
        if isinstance(source_id, str) and source_id:
            sources_by_id[source_id] = source
        cut = _time(source.get("observed_at"), "collection source observed_at")
        if cut > as_of:
            raise ReviewInputError(
                "CONFIGURATION_ERROR",
                "collection cut is later than EvaluationContext.as_of",
                details={"source_id": source_id},
            )

    collection_complete = target_current
    if not target_current:
        source_diagnostics.append("subject freshness requirement is unmet")
    for source_id in required_sources:
        source = sources_by_id.get(source_id)
        if source is None:
            collection_complete = False
            source_diagnostics.append(f"required source {source_id!r} is missing")
            continue
        if source.get("status") != "COMPLETE":
            collection_complete = False
            source_diagnostics.append(
                f"required source {source_id!r} is {source.get('status')!r}"
            )
        cut = _time(source.get("observed_at"), "required collection source observed_at")
        if not _fresh(cut, as_of, source_rule):
            collection_complete = False
            source_diagnostics.append(f"required source {source_id!r} is stale")

    snapshot_cut = _time(
        qualification_snapshot.get("observed_at"), "qualification snapshot observed_at"
    )
    if snapshot_cut > as_of:
        raise ReviewInputError(
            "CONFIGURATION_ERROR",
            "qualification cut is later than EvaluationContext.as_of",
        )
    qualification_rule = policy_document.get("qualification", {}).get(
        "snapshot_freshness", {}
    )
    snapshot_current = _fresh(snapshot_cut, as_of, qualification_rule)
    entries = _list(
        qualification_snapshot.get("entries"), "qualification_snapshot.entries"
    )
    for raw_entry in entries:
        entry = _mapping(raw_entry, "qualification entry")
        cut = _time(entry.get("observed_at"), "qualification entry observed_at")
        if cut > as_of:
            raise ReviewInputError(
                "CONFIGURATION_ERROR",
                "qualification entry cut is later than EvaluationContext.as_of",
                details={"reviewer_id": entry.get("reviewer_id")},
            )

    assessments, active, exclusions = _prepare_assessments(
        observations,
        target,
        policy_document,
        as_of,
    )

    blockers: list[dict[str, Any]] = []
    blocker_recommendations = set(
        policy_document.get("blockers", {}).get("recommendations", [])
    )
    thread_rule = policy_document.get("blockers", {}).get(
        "unresolved_threads", "ignore"
    )
    unknown_thread = False
    for assessment in active:
        recommendation = assessment.get("normalized_recommendation")
        if recommendation in blocker_recommendations:
            blockers.append(
                {
                    "observation_id": assessment.get("observation_id"),
                    "kind": "recommendation",
                    "value": recommendation,
                }
            )
        threads = assessment.get("threads")
        thread_state = threads.get("state") if isinstance(threads, dict) else None
        if thread_rule == "block" and thread_state == "unresolved":
            blockers.append(
                {
                    "observation_id": assessment.get("observation_id"),
                    "kind": "thread",
                    "value": "unresolved",
                }
            )
        if thread_rule == "incomplete" and thread_state not in {
            "resolved",
            "unresolved",
        }:
            unknown_thread = True

    collection_result = {
        "complete": collection_complete,
        "required_sources": required_sources,
        "sources": sources,
        "diagnostics": sorted(set(source_diagnostics)),
    }

    if blockers:
        return _semantic(
            "BLOCKED",
            "BLOCKER_PRESENT",
            input_document=input_document,
            policy_document=policy_document,
            assessments=assessments,
            collection=collection_result,
            blockers=blockers,
            exclusions=exclusions,
            diagnostics=source_diagnostics,
        )

    recommendations = {
        assessment.get("normalized_recommendation")
        for assessment in active
        if assessment.get("normalized_recommendation") != "UNKNOWN"
    }
    conflicts: list[dict[str, Any]] = []
    for pair in policy_document.get("conflicts", {}).get("pairs", []):
        if (
            isinstance(pair, list)
            and len(pair) == 2
            and pair[0] in recommendations
            and pair[1] in recommendations
        ):
            conflicts.append({"recommendations": list(pair)})
    if conflicts:
        return _semantic(
            "CONFLICTING",
            "REVIEW_CONFLICT",
            input_document=input_document,
            policy_document=policy_document,
            assessments=assessments,
            collection=collection_result,
            conflicts=conflicts,
            exclusions=exclusions,
            diagnostics=source_diagnostics,
        )

    if policy_document.get("review_requirement") == "none":
        return _semantic(
            "PASS",
            "POLICY_EXEMPT",
            input_document=input_document,
            policy_document=policy_document,
            assessments=assessments,
            collection=collection_result,
            exclusions=exclusions,
        )

    if not collection_complete or unknown_thread:
        return _semantic(
            "INCOMPLETE",
            "COLLECTION_INCOMPLETE"
            if not unknown_thread
            else "THREAD_STATE_INCOMPLETE",
            input_document=input_document,
            policy_document=policy_document,
            assessments=assessments,
            collection=collection_result,
            exclusions=exclusions,
            diagnostics=source_diagnostics,
        )

    required_capabilities = set(
        policy_document.get("qualification", {}).get("required_capabilities", [])
    )
    owner_reviews_count = bool(
        policy_document.get("qualification", {}).get("owner_reviews_count", False)
    )
    acceptable = set(
        policy_document.get("quorum", {}).get("acceptable_recommendations", [])
    )
    minimum_domains = policy_document.get("quorum", {}).get(
        "minimum_distinct_domains", 0
    )
    target_repo = target.get("repository")
    qualified_domains: set[str] = set()
    qualifying_observations: list[str] = []
    qualification_diagnostics: list[str] = []
    entries_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for raw_entry in entries:
        entry = _mapping(raw_entry, "qualification entry")
        reviewer_id = entry.get("reviewer_id")
        source_id = entry.get("source_id")
        if isinstance(reviewer_id, str) and isinstance(source_id, str):
            entries_by_key[(reviewer_id, source_id)].append(entry)

    for assessment in active:
        recommendation = assessment.get("normalized_recommendation")
        if recommendation not in acceptable:
            continue
        reviewer_id = assessment.get("reviewer_id")
        source_id = assessment.get("source_id")
        if not isinstance(reviewer_id, str) or not isinstance(source_id, str):
            continue
        for entry in entries_by_key.get((reviewer_id, source_id), []):
            if entry.get("status") != "established":
                continue
            if not snapshot_current:
                continue
            entry_cut = _time(
                entry.get("observed_at"), "qualification entry observed_at"
            )
            if not _fresh(entry_cut, as_of, qualification_rule):
                continue
            if entry.get("owner_relation") == "owner" and not owner_reviews_count:
                continue
            capabilities = entry.get("capability_ids")
            if not isinstance(capabilities, list) or not required_capabilities.issubset(
                set(capabilities)
            ):
                continue
            scope = entry.get("scope")
            if isinstance(scope, dict) and scope.get("repository") not in {
                None,
                target_repo,
            }:
                continue
            domain = entry.get("independence_domain_id")
            if not isinstance(domain, str) or not domain:
                continue
            qualified_domains.add(domain)
            observation_id = assessment.get("observation_id")
            if isinstance(observation_id, str):
                qualifying_observations.append(observation_id)
            break

    if not snapshot_current:
        qualification_diagnostics.append("qualification snapshot is stale")
    qualification_result = {
        "snapshot_current": snapshot_current,
        "required_capabilities": sorted(required_capabilities),
        "qualifying_observations": sorted(set(qualifying_observations)),
        "diagnostics": qualification_diagnostics,
    }
    quorum_result = {
        "minimum_distinct_domains": minimum_domains,
        "distinct_domains": len(qualified_domains),
        "domain_ids": sorted(qualified_domains),
    }

    if (
        not isinstance(minimum_domains, int)
        or isinstance(minimum_domains, bool)
        or len(qualified_domains) < minimum_domains
    ):
        return _semantic(
            "INCOMPLETE",
            "QUORUM_UNMET",
            input_document=input_document,
            policy_document=policy_document,
            assessments=assessments,
            collection=collection_result,
            qualification=qualification_result,
            quorum=quorum_result,
            exclusions=exclusions,
            diagnostics=qualification_diagnostics,
        )

    return _semantic(
        "PASS",
        "REQUIREMENTS_SATISFIED",
        input_document=input_document,
        policy_document=policy_document,
        assessments=assessments,
        collection=collection_result,
        qualification=qualification_result,
        quorum=quorum_result,
        exclusions=exclusions,
    )
