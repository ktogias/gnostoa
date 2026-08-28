---
type: Decision
title: Select proportional release retrospection and owner-led product learning
description: Record the v0.2.0 release-series retrospective conclusion, use proportionate retrospective depth, and keep follow-up implementation behind separate admission while prioritizing the first real owner-led trial.
status: draft
generated:
  by: chatgpt/gpt-5.6-pro
  at: "2026-08-28T14:33:45+03:00"
sources:
  - id: retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/155
    title: Retrospect the v0.2.0 release series and staged-evidence transition
  - id: retrospective-assessment
    resource: ../assessments/v0-2-0-release-series-retrospective.md
    title: v0.2.0 release-series retrospective
  - id: release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: staged-evidence-decision
    resource: 0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    title: Use staged evidence maturity for early adoption trials
x-project-knowledge:
  id: kit.decision.0053.select-proportional-release-retrospection-and-owner-led-product-learning
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    - kind: derived-from
      target: /assessments/v0-2-0-release-series-retrospective.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0049-bind-adoption-evidence-to-an-authoritative-ledger.md
    - kind: references
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
---

# Select proportional release retrospection and owner-led product learning

Recorded from the accountable owner's authorization to create Work Item 155 and
prepare one bounded retrospective. The assessment remains subject to human
semantic review before integration. This Decision selects only the retrospective
conclusion and follow-up boundary; it does not admit implementation of any
backlog item.

## Context

The `v0.2.0` series successfully produced one immutable source identity and one
public write-once OCI artifact, reconciled them by exact digest and provenance,
and integrated a bounded `OWNER-LED` Nextcloud Mail trial baseline. The release
controls prevented a broken installed `adoption-check` capability from shipping,
kept publication to one authorized first attempt and preserved exact historical
identities.

The same series also required repeated candidate replacement and re-verification.
Material findings arrived late in evidence custody, installed-artifact behavior,
evidence freshness, provider rerun authority, lifecycle metadata and the
proportionality of the originally selected strict-B3 path. The release is valid;
the process nevertheless exposed avoidable detection cost and an unresolved
product-learning gap.

## Decision

### A. Accept the bounded retrospective conclusion

The release-series outcome is successful and no current source, OCI, provenance
or reconciliation blocker is identified by the retrospective.

The central causal conclusion is narrower than either "the controls failed" or
"more controls are required":

> Strong principles and effective safeguards existed, but several were dispersed
> across records and were not routed into one phase-specific coverage, freshness
> and effect-authority contract early enough. At the same time, assurance work
> grew faster than evidence of practical user value.

The response is earlier and cheaper falsification plus stage-appropriate product
learning, not uniform process expansion.

### B. Use proportionate retrospective depth

Use a short close-out reflection for every bounded Work Item. It asks:

1. What was expected?
2. What happened?
3. What was surprising or detected late?
4. Which existing control worked or failed to activate?
5. Is there one concrete change worth considering for a later cycle?

A micro-retrospective does not require a new canonical document for every small
change.

Use a formal causal retrospective only when at least one deliberate trigger is
present:

- a minor or major release;
- a critical integrity or security defect or near-miss;
- two or more candidate resets after a readiness or acceptance claim;
- a defect that passed source checks and was found in a shipping artifact;
- evidence-subject invalidation or repeated stale projections;
- a new cross-trust execution or publication boundary; or
- an accountable-owner request.

The `v0.2.0` series satisfies several triggers and therefore warrants the formal
assessment recorded by Work Item 155. Routing this rule into an operational
runbook remains a separate proposed effect and is not implemented here.

### C. Keep retrospective actions proportional and separately admitted

Classify follow-up actions as:

- `P0`: a current release or integrity blocker;
- `P1`: a bounded improvement required for the next relevant cycle or before the
  next equivalent release boundary; and
- `P2`: a research or product hypothesis with no automatic admission.

The retrospective selects no `P0` action. Every `P1` or `P2` item requires its
own concrete proposed surface, change classification, Work Item and applicable
Decision before implementation.

### D. Prioritize real owner-led product evidence

The first substantive next product-learning activity is one real,
`OWNER-LED` Nextcloud Mail task under Decision 0052, followed by a separate trial
retrospective. That run may produce a preliminary owner assessment and product
changes without waiting for upstream feedback.

Do not admit new assurance machinery merely to resolve discomfort created by a
rejected or unrun experiment. A concrete blocker, repeated real-project friction
or a future stronger claim must justify the mechanism at its own boundary.

### E. Preserve the controls that proved their value

Do not weaken:

- exact source, tag, tree, digest and provenance binding;
- Decision 0049's authoritative evidence ledger and explicit residual same-user
  boundary;
- Decision 0050's separation of observations, conditions, readiness policy and
  owner disposition;
- shipping-artifact execution for public capabilities;
- first-attempt, actor-bound, input-free publication authority;
- provider read-back, integrated-tree equality and close-last reconciliation;
- the rule that `SKIPPED` is not execution evidence; or
- bounded human semantic judgement for oracle limits.

Simplification should remove duplicated prose, late routing and unnecessary
coordination, not erase the controls that caught real defects.

### F. Preserve the effect boundary of this slice

Work Item 155 may add only the retrospective assessment, this Decision and
routing from `knowledge/index.md`.

It does not:

- execute the owner-led trial;
- mutate either Mail repository;
- contact upstream;
- implement any retrospective action;
- alter source, OCI, provenance or Release identities;
- change provider settings or publish another artifact; or
- complete the lifecycle of Work Item 146.

## Consequences

- The completed release remains valid while its preparation cost and late
  findings become durable learning.
- Micro-retrospection becomes the selected default; formal RCA remains
  trigger-based rather than universal.
- The next product claim must come from a real owner-led task, not from another
  layer of self-referential assurance evidence.
- Concrete reliability and usability findings remain visible in a prioritized
  backlog, but none is implemented by implication.
- A future independent-adoption experiment remains available when Gnostoa's
  maturity and claims justify its coordination cost.
