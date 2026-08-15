---
type: Decision
title: Evolve human-agent workflow through bounded self-hosted slices
description: Treat B1 workflow failures as demonstrated product need, finish the bounded publication baseline, and implement the smallest durable human-agent loop through measured self-hosted increments.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-15T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
  - id: historical-guided-review-ledger
    resource: https://github.com/ktogias/gnostoa/issues/12
    title: Historical B1 guided-review design and dogfood ledger
  - id: durable-task-context-research
    resource: https://github.com/ktogias/gnostoa/pull/4
    title: Parked durable task context and explicit handoff research
  - id: streamlined-self-hosting-experiment
    resource: https://github.com/ktogias/gnostoa/issues/24
    title: Run one bounded B2 streamlined self-hosting experiment
  - id: agile-principles
    resource: https://agilemanifesto.org/principles
    title: Principles behind the Agile Manifesto
  - id: google-sre-toil-reduction
    resource: https://sre.google/workbook/eliminating-toil/
    title: Google SRE Workbook — Eliminating toil
  - id: kanban-guide
    resource: https://kanbanguides.org/the-kanban-guide/
    title: The Kanban Guide
x-project-knowledge:
  id: kit.decision.0016.evolve-human-agent-workflow-through-bounded-self-hosted-slices
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /lifecycles/toolkit-evolution.md
    - kind: references
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: references
      target: /failure-modes/publication-baseline-review-drift.md
    - kind: references
      target: /failure-modes/container-first-verification-routing-bypass.md
    - kind: references
      target: /runbooks/prepare-first-publication.md
---

# Evolve human-agent workflow through bounded self-hosted slices

## Resume card

| Field | Current state |
|---|---|
| Vision | People and agents resume bounded work from durable current state without replaying raw conversations or confusing evidence with human authority. |
| Evidence | B1 demonstrated material need for guided review, durable task context, bounded plans, explicit handoffs, checkpoint/resume and safe restart. |
| Uncertainty | The need is demonstrated; the minimum sufficient implementation is not. |
| Publication rule | The full workflow platform is not a first-publication prerequisite. Only a concrete security, legal, correctness or exposure failure may promote one of its slices into that critical path. |
| Active delivery | Finish the bounded source-publication baseline in Issue #1 without another workflow-platform expansion. |
| Next experiment | [Issue #24](https://github.com/ktogias/gnostoa/issues/24) runs B2 and selects the smallest useful enabling slice. |
| First candidate slice | A validated task envelope, one current projection, explicit handoff, checkpoint/resume and stale-state detection; no database, general event-sourcing platform or interactive wizard. |
| WIP policy | Permit one active delivery item and one active enabling slice. Queue other findings unless they prove an immediate safety or correctness blocker. |
| Resume route | Read this card, the current roadmap projection and the active Issue/PR body. Load the B1 ledger only for a named unresolved question. |

## Context

Gnostoa deliberately used itself as its first consumer. The B1 publication
review found and corrected real source-scope, authority, lifecycle, drift and
disclosure defects. It also exposed a bootstrapping loop: publication remained
blocked by proposed workflow prerequisites, while systematic implementation of
those prerequisites was itself deferred until after publication. Manual
recording expanded into 407 comments across the two main ledger threads and
became an unimplemented event store rather than a usable review interface.

This is not evidence that the workflow need is speculative. It is evidence
that the need is real and that recursively designing the complete solution on
the publication critical path is unsafe. The broad Issue #12 record remains
historical design and failure evidence. PR #4 remains useful implementation
research, but its conflicting branch and unresolved findings are not a current
merge candidate.

## Decision

1. Publish the smallest truthful validation and knowledge-architecture
   baseline before building the full workflow platform. Publication is a
   stable starting boundary, not completion of the product vision.
2. Treat guided review, durable task context, bounded execution plans, explicit
   human-agent handoffs, checkpoint/resume, invalidation and safe restart as
   planned product capabilities whose need was demonstrated by B1.
3. Use two coupled loops:
   - the **delivery loop** publishes or improves one bounded user-facing
     capability; and
   - the **capability loop** selects one measured workflow bottleneck, builds
     the smallest reusable remedy and dogfoods it in the next delivery cycle.
4. Implement in small, independently revertible slices with observable fitness
   checks. Do not create a general workflow engine, database or provider
   adapter before a smaller slice fails a named experiment.
5. Preserve semantic decisions and corrections append-only, but maintain one
   compact replaceable current projection. Detailed evidence remains linked
   and expandable rather than foregrounded or copied into every checkpoint.
6. Ask for one human decision per genuine semantic choice. Deterministic
   recording, read-back, projection and reconstruction of that exact effect do
   not create another approval gate.
7. Keep work pull-based and bounded: one active delivery item and one active
   enabling slice. A new finding changes the active scope only when it names a
   failed property that cannot be mitigated safely inside the current slice.

## Publication gate

The first source publication is blocked only by evidence of an unsafe public
effect: credential or private-data exposure, unresolved license or identity
risk, incorrect or unreconstructable source, materially misleading public
documentation, failed required verification, missing provider protection or
an unsafe visibility transition.

The absence of a general guided-review engine, durable workflow service,
execution-plan orchestrator, event store, GitHub adapter, TUI or web wizard is
not a first-publication prerequisite. The current compact provider projection,
exact candidate binding, required checks, explicit owner control and read-back
form a bounded temporary publication harness.

If that harness exposes a new unmitigable publication risk, implement only the
minimum safety shim needed to clear the named failure. Do not promote the rest
of the workflow roadmap with it.

## B2 walking skeleton

B2 should make the smallest end-to-end durable loop executable. Seed its own
state manually, implement the validator/projector, and use the result for later
checkpoints in the same bounded change.

The first candidate contract contains:

- a stable task ID, objective, owner, class and explicit non-goals;
- exact base, candidate and dependency identities;
- current state: `ready`, `active`, `blocked`, `complete` or `superseded`;
- completed work, the single next action and named blocker, if any;
- semantic Decision and evidence references without duplicating their bodies;
- an explicit handoff naming what the next actor must read and verify;
- checkpoint/resume with idempotent reconstruction;
- stale-head, changed-dependency and conflicting-update detection; and
- one current projection generated from the durable state.

It excludes automated human approval, transcript storage, hidden reasoning,
general branching workflows, a hosted database and provider-specific authority
from the generic core.

## Increment sequence

1. Task envelope, current projection and checkpoint/resume.
2. Explicit human-agent handoff and fresh-session recovery.
3. Bounded execution plan with one active step and stop conditions.
4. Precise candidate invalidation and verified unaffected-state reuse.
5. Declarative guided-review questions, completion rules and corrections.
6. Provider adapters or interactive interfaces only after the portable
   contract is useful without them.

Each increment is developed in one small PR, used by the following Gnostoa
change and compared with B1. PR #4 may supply code or design input, but useful
parts are intentionally rebased or reimplemented against the then-current
baseline rather than treating its old branch as accepted wholesale.

The container-verification routing incident is a candidate B2 input: test a
small repository-root-aware wrapper only if it measurably prevents native-route
drift. It is not permission to build a general environment orchestrator or to
delay the first source publication.

## Agent and developer resume contract

Load in this order:

1. this Resume card;
2. `docs/roadmap.md` for Now/Next/Research;
3. the active Issue and PR current bodies;
4. the task envelope/current projection when B2 supplies it; and
5. only the exact Decision, test or historical record needed for an unresolved
   question.

Do not replay Issue #12, PR #2 or raw conversations for ordinary orientation.
Do not infer authority from an agent summary. On state drift, stop, refresh the
exact provider/source identities and regenerate the affected projection.

## Measures and stop rules

Every B2 slice records owner review time, total cycle time, review rounds,
evidence words per changed normative line, recovery time after interruption,
defects caught before integration, escaped defects, false-ready/false-block
outcomes and new maintenance surface.

Continue expanding the workflow surface only when the slice retains B1's
material defect detection and safe recovery while reducing foreground evidence
and owner effort. If an increment does not improve a named outcome, simplify,
remove or redesign it. If B2 remains as amplified as B1, narrow the product
claim to the demonstrated validation, profile, policy and context foundation.

## Consequences

- Publication no longer waits for completion of the workflow vision.
- The workflow vision is explicitly planned rather than dismissed as an
  unproven need.
- Issue #12 stays closed as a historical experiment, not as the forward
  product backlog; Issue #24 and later bounded Work Items own implementation.
- PR #4 stays closed and unmerged as reconstructable research until selected
  parts earn a new current-base implementation.
- The project accepts a temporary manual publication harness once, but does
  not normalize repeated transcript replay or marker-heavy provider ledgers.
- B3 still requires an independently owned transfer pilot before claims of
  easy adoption, productivity gain or independent assurance.
