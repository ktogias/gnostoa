---
type: Decision
title: Scope the readiness predicate experiment to Gnostoa self-hosting
description: The selected C4-v0 readiness predicate is initially a Gnostoa self-hosted experimental control outside the public inherited surface, and a capability-loop remedy outside Decision 0016's numbered increment sequence.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-17T22:22:19Z"
sources:
  - id: control-selection-work-item
    resource: https://github.com/ktogias/gnostoa/issues/31
    title: Map observed control failures and select one bounded enforcement experiment
  - id: readiness-experiment-work-item
    resource: https://github.com/ktogias/gnostoa/issues/33
    title: Experiment with a deterministic read-only READY predicate
x-project-knowledge:
  id: kit.decision.0017.scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /assessments/b2-control-selection-and-failure-path-map.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Scope the readiness predicate experiment to Gnostoa self-hosting

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

## Context

Issue #31 selected C4-v0 — a deterministic, read-only `READY` predicate over
existing evidence — for a separately admitted bounded experiment, against the
primary failed property that **readiness can be asserted while required
preconditions are false**.

Admission then stopped, because the effective change-control policy classifies
the originally proposed implementation as `normative` and requires a linked
Decision before implementation, while Decision 0016 could not supply the missing
authority for two specific choices:

- the [public inheritance surface](../contracts/public-inheritance-surface.md)
  states that the public surface consists of the core profile, schemas,
  **supported tools**, reusable guidance, anonymous templates and documented CI
  integration, and `tools/` lies inside the pinned public-surface digest. Placing
  the predicate there would therefore change the surface adopting projects
  inherit. Decision 0016 mentions the CLI, the public surface and inheritance
  nowhere.
- Decision 0016's numbered increment sequence contains six increments, and a
  readiness predicate is not one of them. No Decision in the repository mentions
  readiness, a `READY` predicate or a readiness gate.

The predicate's preconditions would be derived from Gnostoa's own P1 and P2
failure history, so whether they are generic project-independent controls or
Gnostoa-specific self-tooling is genuinely undecided. The
`self-knowledge-boundary` and `generic-scope-isolation` guardrails police exactly
that line, and getting it wrong in either direction is a defect: shipping
Gnostoa-specific readiness semantics into the inherited surface violates generic
scope isolation, while hiding a genuinely generic control in self-tooling denies
it to adopters.

This Decision resolves **where and how** the selected experiment may be
performed. It does not assert that C4-v0 works.

## Decision

**A.** C4-v0 is initially **Gnostoa self-tooling — a self-hosted experimental
control — outside the public inherited surface.** During this experiment it must
not become a supported public CLI or tool, an inherited schema, a generic
guardrail, a consumer policy requirement or an adopting-project contract.

**B.** C4-v0 is a **capability-loop remedy governed by Decision 0016 but outside
its numbered six-step increment sequence** for now. This Decision does not add to,
amend or reorder that sequence, and **Decision 0016 increment 2 remains not
activated**.

**C.** **Successful experimentation does not automatically promote C4-v0** to the
generic or public contract. Evidence that a self-hosted control refuses Gnostoa's
own historical false-ready states is not evidence that a project-independent
readiness predicate is useful.

**D.** **Public promotion, if later justified, requires a separate owner
Decision** addressing generic semantics, adopter inheritance, public CLI or tool
status, compatibility and versioning, migration impact, and verification
requirements.

**E.** If the experiment cannot be implemented within this self-hosted boundary
without modifying public-surface semantics or consumer inheritance, the work
**stops**. Silent promotion to the public surface is forbidden.

## Consequences

- The experiment becomes admissible, because the missing authority was about
  placement rather than about mechanism.
- The experimental implementation surface must lie outside the pinned
  public-surface digest. `knowledge/`, `policy/`, `tasks/` and internal decisions
  are already outside the consumer inheritance boundary by contract, and `tests/`
  and `docs/` are outside the digest.
- Adopting projects gain nothing from this experiment, by design. That cost is
  accepted in exchange for testing the hypothesis without a compatibility or
  migration obligation.
- The reclassified diff is expected to be lighter than `normative`, because it
  touches no policy, profile, schema, stable knowledge or public contract
  behaviour. The class must still be re-derived from the actual diff rather than
  assumed, and a lower class must not be used to skip evidence the experiment
  needs anyway.
- A later promotion Decision carries a heavier burden than this one: it must
  argue genericity from evidence, not from the fact that a Gnostoa-internal
  experiment succeeded.
- What this Decision deliberately leaves open: whether the predicate works,
  whether its preconditions are the right ones, and whether the approach should
  be kept, narrowed, redesigned or rejected. Those remain the experiment's
  question and the maintainer's later disposition.
