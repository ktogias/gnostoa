---
type: Decision
title: Run a bounded behavioral-traceability review experiment
description: Test whether a compact Gnostoa-self behavior map helps an executor and reviewer expose a task-to-code-to-test contradiction without claiming semantic automation or exporting a new public contract.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-31T11:08:55Z"
sources:
  - id: behavioral-traceability-work-item
    resource: https://github.com/ktogias/gnostoa/issues/170
    title: Add bounded behavioral traceability to agent execution and review
  - id: phase-b-owner-led-task-result
    resource: ../assessments/nextcloud-mail-phase-b-owner-led-task-result.md
    title: Nextcloud Mail Phase-B owner-led task result
x-project-knowledge:
  id: kit.decision.0056.run-a-bounded-behavioral-traceability-review-experiment
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
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: derived-from
      target: /assessments/nextcloud-mail-phase-b-owner-led-task-result.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# Run a bounded behavioral-traceability review experiment

## Context

Phase B completed with a technically wrong frozen candidate even though its
implementation and regression test agreed with each other and a fresh reviewer
recommended `ACCEPT`. The pair contradicted a material task consequence: an
already-satisfied operation was required to remain a no-op, while the candidate
and its test preserved the prohibited mutation.

This is a semantic-review failure, not evidence that a parser can derive every
behavioral obligation from prose. A completeness validator would be gameable by
declaring less and would repeat the oracle inflation rejected by the
evidence-gated capability lifecycle.

## Decision

### A. Select one Gnostoa-self experiment before any public contract

Run one provider-neutral, Gnostoa-self-only experiment that compares the
historical Phase-B baseline with a compact trace-assisted review. Do not add a
public schema, CLI, template, readiness predicate, workflow engine or provider
adapter in this slice.

The experiment is a `normative` Gnostoa-self change because it adds a conditional
execution and review obligation. Its result may be positive or negative.

### B. Use a compact per-behavior map

For every applicable material behavior, the experimental map retains:

- a stable local behavior ID and exact task/source selector;
- the expected observable behavior;
- any contradiction, ambiguity or assumption;
- the intended implementation path;
- the linked test or other evidence and its actual result;
- whether that evidence supports, contradicts or leaves the behavior unknown;
- separate executor and reviewer dispositions; and
- exact task, candidate and evidence identities.

`PASS`, `FAIL`, `BLOCKED`, `NOT RUN` and `SKIPPED` remain distinct. A passing
test that contradicts the task is not supporting evidence.

### C. Apply the map only when risk justifies it

The map is required experimentally when a task has multiple material behaviors,
a contradiction or ambiguity, or material correctness risk. A trivial task may
record `NOT APPLICABLE` with one bounded reason and no behavior rows.

The executor records the map before the first semantic production mutation. An
unresolved contradiction, unsupported narrowing, missing material evidence or
contradictory evidence blocks review-ready disposition. The reviewer then
reconciles the complete declared behavior set independently against the exact
task, candidate and evidence before recommending acceptance.

This does not prove that the declared set is complete or correctly interpreted.
Those remain bounded semantic judgments.

### D. Falsify with one negative and two positive controls

Use a sanitized, product-neutral reconstruction of the Phase-B failure as the
negative case: code and test agree but contradict a task consequence. Compare it
with one aligned non-trivial case and one trivial `NOT APPLICABLE` case.

The measured result records at least defect recall, false blocks, owner
interventions, elapsed time and bounded context cost. Historical Phase-B reviewer
`ACCEPT` is the baseline; the frozen experiment is neither rescored nor repaired.

### E. Preserve subject and claim boundaries

Task, candidate or evidence mutation invalidates the affected trace and requires
reconciliation. Structural presence, exact identities and recorded statuses do
not establish semantic correctness, model independence, human approval or owner
disposition.

If the experiment does not improve recall at proportionate cost, narrow or
remove the experimental rule. Promotion to generic guidance, schemas, tools or
templates requires a later owner selection and separate normative Decision.

## Consequences

- The first slice measures a semantic review aid rather than prematurely
  shipping a validator.
- The known agreeing-but-wrong failure becomes a retained sanitized control.
- Reviewer diversity remains useful as decorrelation, never as an oracle.
- No Mail source, Phase-B score, public inheritance surface, release, OCI image
  or provider setting changes under this Decision.
