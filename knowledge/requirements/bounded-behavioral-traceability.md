---
type: Requirement
title: Require bounded behavioral traceability for applicable Gnostoa-self work
description: Applicable Gnostoa-self tasks retain a compact task-to-implementation-to-evidence map so contradictions and unsupported narrowing remain visible at execution and review boundaries.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-31T11:08:55Z"
sources:
  - id: behavioral-traceability-decision
    resource: ../decisions/0056-run-a-bounded-behavioral-traceability-review-experiment.md
    title: Run a bounded behavioral-traceability review experiment
  - id: diagnosis-evidence-authority-decision
    resource: ../decisions/0058-harden-behavioral-diagnosis-evidence-authority.md
    title: Harden behavioral diagnosis evidence authority and hypothesis reconciliation
  - id: behavioral-traceability-work-item
    resource: https://github.com/ktogias/gnostoa/issues/170
    title: Add bounded behavioral traceability to agent execution and review
  - id: diagnosis-evidence-authority-work-item
    resource: https://github.com/ktogias/gnostoa/issues/182
    title: Harden behavioral diagnosis evidence authority and hypothesis reconciliation
x-project-knowledge:
  id: kit.requirement.bounded-behavioral-traceability
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0056-run-a-bounded-behavioral-traceability-review-experiment.md
    - kind: governed-by
      target: /decisions/0058-harden-behavioral-diagnosis-evidence-authority.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: derived-from
      target: /assessments/nextcloud-mail-phase-b-owner-led-task-result.md
---

# Require bounded behavioral traceability for applicable Gnostoa-self work

## Scope and claim boundary

This is an experimental Gnostoa-self review contract. It is not inherited by
adopting projects and does not add a public schema, validator, CLI, template,
readiness predicate or new provider-specific job, status or configuration.
Existing repository verification may retain the self-only contract and replay
packet as ordinary source evidence.

The behavior map makes declared obligations and contradictions reviewable. Its
structural presence **does not establish semantic completeness**, correctness,
model independence, human approval or owner disposition. People remain
responsible for finding and interpreting material behavior; deterministic checks
may only preserve the claims and identities they are given.

Decision 0058 narrows one demonstrated failure class without expanding this
claim: a map must expose enough diagnostic evidence authority and evidence
dependency to distinguish a plausible, internally consistent bug scenario from
identification of the task's reported case. This preserves auditability; it does
not establish that the map improves diagnostic correctness.

## Applicability

Use the map when a task has any of:

- multiple material behaviors that share or cross implementation paths;
- a contradiction or ambiguity among consequences, examples, suggested fixes
  or authoritative project evidence; or
- material correctness risk for which a plausible implementation and passing
  test could still preserve prohibited behavior.

A trivial task outside those conditions needs no behavior map. When its
applicability is explicitly under review, it may record `NOT APPLICABLE` and one
bounded reason; it does not manufacture behavior rows merely to satisfy
ceremony.

## Required workflow

### Executor checkpoint

For applicable work, record the initial map in the active Work Item or change
record **before the first semantic production mutation**. This is the durable
human-review checkpoint; deterministic checks retain its routing and bounded
replay controls but do not prove that every applicable change created a
complete map at the required time.

The initial map retains each known material behavior and may use a prospective
implementation path, a base or prospective candidate identity, verification
state `NOT RUN`, alignment `UNKNOWN`, and executor/reviewer dispositions
`PENDING`. It does not invent final evidence. Each material behavior retains:

1. a stable local ID and exact task/source selector;
2. the expected observable behavior;
3. every identified contradiction, ambiguity or assumption and its current
   resolution state;
4. the implementation path intended to satisfy it;
5. the corresponding test or other evidence, or an explicit reason it is
   unavailable;
6. the actual verification result, initially `NOT RUN` when it does not yet
   exist;
7. whether the evidence `SUPPORTS`, `CONTRADICTS` or leaves the behavior
   `UNKNOWN`; and
8. separate executor and reviewer dispositions.

Bind the initial map to the exact task identity and the available base or
prospective candidate identity. Before review, update actual results and
**re-bind** the map to the exact final candidate and evidence identities. A
relevant mutation invalidates the affected row; reconcile and re-bind it before
reusing a result.

An unresolved contradiction, unsupported narrowing, uncovered material
behavior, unavailable required evidence or evidence marked `CONTRADICTS`
**blocks review-ready** status. The executor records the blocker instead of
silently selecting the narrower interpretation.

### Diagnostic evidence authority and hypothesis reconciliation

When an applicable task contains material diagnostic ambiguity, keep three
semantic object types distinct where they exist:

- **task obligation** — the observable behavior required by the authoritative
  task or project source;
- **semantic hypothesis** — a proposed explanation or task interpretation that
  may still be wrong; and
- **implementation claim** — what the candidate code, test or implementation
  path claims will occur.

An implementation claim or test expectation does not become the meaning of a
task obligation merely because code and test agree.

A task-semantic hypothesis records its resolution state and the evidence used to
resolve it. Where evidence is used for that resolution, retain the evidence
authority and the evidence dependency needed to review whether the evidence is
independent of the hypothesis. At minimum, distinguish as applicable:

- authoritative task/project evidence;
- pre-existing independent project evidence;
- executor-authored diagnostic evidence;
- executor-authored regression evidence derived from the same hypothesis;
- reviewer inference; and
- unknown or unclassified evidence.

Execution result and semantic authority remain separate. An
executor-authored regression may legitimately `PASS` and establish **base reproduction**
of the selected scenario and **candidate correction** of that scenario without
establishing **task identification**.

A task-semantic hypothesis must not become `CONFIRMED` solely from evidence
authored to instantiate that same hypothesis. Such same-hypothesis evidence may
show that the selected scenario is possible and repaired, but it cannot by
itself prove that the selected scenario is the one described by the task.
Without authoritative or sufficiently independent discriminating evidence,
task identification remains `OPEN` or `UNKNOWN`; when that identification is
material to correctness, the unresolved state **blocks review-ready** status or
is escalated to the owner.

When material ambiguity admits competing hypotheses, retain the material
alternatives identified during diagnosis and, where feasible, a discriminating
observation or test for each. A rejected material hypothesis retains the reason
and evidence for rejection. **Implementation convenience must not be used as
evidence to reject a competing hypothesis.** Locality, size or convenience may
influence repair selection only after the relevant cause is adequately
established.

When an identity, classification, routing or other **behavior-classifying predicate**
lies on the **suspected defect path**, do not use that predicate as its own
definition of correctness. Treat its relevant behavior as a hypothesis or
implementation dependency requiring **independent validation** before it can
close the semantic question it classifies.

### Reviewer checkpoint

Before recommending acceptance, the reviewer independently reconciles the
complete declared behavior set against the exact task, candidate and evidence.
The reviewer checks observable consequences rather than trusting the executor,
an implementation-shaped test name or a passing result.

For materially ambiguous or high-risk behavioral diagnosis, the operational
runbook requires the reviewer to form an independent task-to-code view before
consuming the executor's final diagnosis/map conclusions, then reconcile that
view with the map, its competing hypotheses and its evidence authority and
dependencies.

A test may report `PASS` while its asserted behavior contradicts the task. That
combination remains a blocker. A different reviewer model can reduce correlated
blind spots but does not become a semantic oracle, and model diversity alone is
not evidence independence.

## Execution, alignment and disposition states

Keep `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` and `SKIPPED` distinct:

- `PASS` means the named evidence executed and met its own expectation;
- `FAIL` means it executed and did not meet that expectation;
- `BLOCKED` means a prerequisite prevented execution;
- `NOT RUN` means no execution was attempted; and
- `SKIPPED` means an explicit condition omitted execution.

Only aligned evidence can support a behavior. `BLOCKED`, `NOT RUN`, `SKIPPED`
and missing evidence are never rewritten as `PASS`; a mechanically passing but
semantically contradictory test is never rewritten as support.

Alignment is separately `SUPPORTS`, `CONTRADICTS` or `UNKNOWN`. Executor and
reviewer dispositions remain `PENDING` until their checkpoint is complete;
neither a `PASS` execution state nor an executor disposition supplies the
reviewer's semantic result.

## Experiment and stop rules

Decision 0056 admits one bounded blind replay. Its Decision and result record,
not this reviewer-facing Requirement, own the control composition and scoring
key. After the raw response is frozen, record the predeclared measures, owner
interventions, elapsed time and bounded context cost.

If the map does not improve recall at proportionate cost, retain the negative
result and narrow or remove this rule. Do not rescue it with a schema, workflow
engine or broader evidence platform. Any promotion outside Gnostoa-self requires
separate research, owner selection, classification and admission.
