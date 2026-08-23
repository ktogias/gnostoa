---
type: Source
title: Weather-note evaluation root-cause retrospective
description: Bounded Gnostoa-self causal synthesis of the completed seven-run synthetic weather-note evaluation series and implications for one later B3 experiment.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-23T14:33:16Z"
sources:
  - id: weather-note-root-cause-retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/105
    title: Canonicalize the weather-note evaluation root-cause retrospective
x-project-knowledge:
  id: kit.assessment.weather-note-evaluation-root-cause-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0042-accept-the-weather-note-cold-start-onboarding-result.md
    - kind: references
      target: /assessments/weather-note-cold-start-onboarding-result.md
    - kind: references
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Weather-note evaluation root-cause retrospective

## Authority and evidence boundary

[Decision 0042](../decisions/0042-accept-the-weather-note-cold-start-onboarding-result.md)
owns the synthetic `weather-note` experiment disposition. The
[cold-start assessment](weather-note-cold-start-onboarding-result.md) remains
the authority for exact run evidence and dispositions; this retrospective
links to that record instead of duplicating evaluator narratives, commands or
result histories. [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
owns external-adopter B3, while [Decision 0036](../decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md)
owns the separate Gnostoa-self fresh-agent transfer question.

Across seven owner-reported evaluations, three runs had mechanically supported
technical execution. Two of those were semantic passes and the third was a
technical pass with a semantic partial failure. Three reports were invalid or
fabricated execution claims. One report was honestly blocked: it did not run
Gnostoa, retained sound semantic questions, and was stale or unbound to current
public state. These are bounded observations, not statistical reliability
rates or vendor comparisons.

## Causal distinctions

The series exposed seven independent result dimensions. A positive result in
one does not substitute for evidence in another.

| Dimension | Question preserved by the evidence |
|---|---|
| Product execution | Did the supported Gnostoa route actually execute? |
| Semantic fidelity | Were unknown facts, ownership and readiness kept unresolved rather than invented? |
| Environment eligibility | Could the evaluator satisfy the declared execution prerequisites? |
| Public/current-state orientation | Was the evaluator bound to the relevant current documentation and artifact state? |
| Evidence binding | Do exact identities, exits, artifacts and hashes support the claimed execution? |
| Human-owner acceptance | Did an accountable owner actually select the missing project semantics? |
| Measured adoption value | Was benefit and effort measured under a comparable contract in a real adopting context? |

## Principal root causes

- Narrative reports could initially masquerade as execution evidence without
  mandatory artifact-bound receipts.
- Schema validity could not establish semantic truth, real ownership or
  implementation readiness. Human semantic authority remained necessary.
- Execution prerequisites and source/documentation freshness were not always
  established through a fail-closed preflight before evaluation.
- The tiny, synthetic and ownerless fixture could test onboarding mechanics,
  but could not establish independent adoption value.
- Minimal evaluation and durable adoption were not initially separated clearly
  enough, so evaluators selected materially different surfaces.
- Timing and adoption verdicts were not measured under one common contract and
  therefore were not consistently comparable.
- Canonicalizing each report separately created self-governance effort
  disproportionate to the bounded experiment; an admitted series should be
  batched and reconciled once.

These causes reinforce the existing
[evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md):
an executable receipt is not semantic acceptance, and semantic plausibility is
not executed evidence.

## Supported execution properties that held

The supported executions did not fail at the measured immutable OCI route,
offline validation and context generation, source/runtime lock binding, OKF
validation, non-weakening enforcement, deterministic bounded context
generation, or exclusion of Gnostoa self-knowledge. This bounded result does
not transfer those properties to the invalid or non-executed reports.

## Imagined-interface observation

Three invalid reports independently converged on an imagined interface:

```text
.gnostoa or gnostoa.yaml
+ simplified YAML manifests
+ gnostoa validate
+ context or compile
+ latest
```

The repetition is only a product and discoverability hypothesis for later
external testing. It does not establish user demand, a current documentation
defect, or a need for a generator, new DSL, command aliases, compatibility
surface or mutable `latest` tag. None is selected or admitted here.

## Smallest implications for a later B3 experiment

A real B3 experiment should:

- use one independently owned repository with human-owner ground truth;
- bind documentation and execution subjects separately;
- verify environment eligibility before evaluation and stop as `BLOCKED` when
  prerequisites are absent;
- require exact source/runtime identities, command exit codes, generated
  artifacts and hashes for a technical-pass claim;
- measure orientation, setup, correction, owner intervention and review effort
  under one consistent contract;
- report technical execution, semantic fidelity, owner acceptance and product
  value as separate outcomes; and
- batch the admitted experiment series and reconcile it once.

These are bounded experiment-design lessons. They do not create a generic
receipt mechanism or adopter-facing workflow.

## Limits and stop point

This retrospective does not reproduce complete reports, rank model vendors,
or treat invalid reports as tests of Gnostoa's technical reliability. Seven
synthetic runs do not establish population-level success rates. The synthetic
experiment remains closed: no generator, DSL, alias, mutable tag, schema,
validator, workflow mechanism or further `weather-note` replay is selected.

B3 remains incomplete, and the Decision 0036 fresh-agent transfer condition
remains unsatisfied. The next owner subject is one real B3 experiment in an
independently owned project with human-owner ground truth and artifact-bound
acceptance evidence.
