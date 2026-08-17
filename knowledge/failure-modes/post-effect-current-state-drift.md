---
type: Failure Mode
title: Post-effect current-state drift
description: Failure mode in which authorized provider effects complete while repository current-state and resume projections remain one effect behind.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-17T13:20:00Z"
sources:
  - id: post-effect-reconciliation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/29
    title: Reconcile post-effect current-state drift after B2/P2 integration
  - id: b2-p2-integration
    resource: https://github.com/ktogias/gnostoa/pull/28
    title: Authorized integration of the B2/P2 close-out candidate
x-project-knowledge:
  id: kit.failure-mode.post-effect-current-state-drift
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
---

# Post-effect current-state drift

## Failed property

> **Authorized provider effects can complete while repository current-state and
> resume projections remain one effect behind.**

More precisely: **repository current-state projections are not effect-consistent
across the repository/provider boundary.**

## What is not being claimed

This is **not** an effect-authority failure, and it must not be filed with the
unauthorized-effect findings recorded for B2/P2.

| | |
|---|---|
| PR #28 merge | authorized and correct |
| Issue #24 closure | authorized and correct |
| The failure | those successful effects changed authoritative external state **after** the reviewed terminal repository candidate had already been produced |

Three distinctions carry the whole finding:

- **authorized-effect completion** is not unauthorized-effect failure — nothing
  here was done without permission;
- **immutable historical state** is not a **replaceable current projection** — a
  commit identity that was true at a moment stays true about that moment, but a
  sentence claiming it is *current* goes stale;
- **pre-effect terminal repository state** is not **post-effect provider
  state** — a candidate can be terminal, reviewed and green, and still describe
  the world as it stood one effect earlier.

## Boundary and evidence

The reviewed terminal boundary was candidate
`0e336b49c16d2b8bbef7b9435b683d5df52755a7`: P2 envelope terminal at checkpoint
6, required routes green, owner disposition recorded. Nothing about that
candidate was wrong when it was reviewed.

Two authorized provider effects then completed: PR #28 merged as
`ac95c558d70b119df4d635e6531334bf83bab1a9`, and Issue #24 was closed as
completed with its `roadmap:now` label removed.

At that integrated base, three repository projections contradicted the provider:

| Surface | Stale claim |
|---|---|
| `knowledge/decisions/0016-…md` Resume card | `Active delivery` and `Current experiment` still presented P2 as current work |
| `docs/roadmap.md` | closed Issue #24 still occupied `Now`, still stating that integration and Work Item closure remained separate owner effects |
| `docs/status.md` | `cda51dad…` presented as the current protected-main identity, and "The active B2 experiment" retained after B2/P2 completed |

None of these was reachable by the reviewed candidate's own verification,
because each became false only when the effects landed.

## Why no existing control caught it

The workflow has no mechanically guaranteed step between an authorized provider
effect and the projections that describe it. Verification runs against a
candidate; the effect happens after. Reconciliation depended entirely on someone
noticing afterwards.

## Relationship to the B2/P2 narrowed claim

B2/P2 narrowed the product claim to: the bounded envelope and projection improve
orientation, resumability and bounded human understanding, but are **not** an
enforcement mechanism. This failure mode is that claim observed from the other
side of the boundary. P2's named failed property was that critical workflow
constraints are advisory rather than mechanically enforced; post-effect
reconciliation is one more constraint that is currently advisory, and it failed
in the very act of closing the experiment that recorded the framing.

### The repair reproduced the failure once, in miniature

The first candidate for this record's own Work Item, #29, prematurely projected
the expected **post-#29** state — a resume card and roadmap both asserting that
no active delivery item existed — while #29 was still OPEN and labelled
`roadmap:now`. The same page then named #29 as the current repair, so the
candidate contradicted itself.

Automated verification stayed **green** on that candidate: every required route
passed, all surfaces validated, and the declared bound held. **Human semantic
verification caught the temporal contradiction before a Change Request was
opened.**

This reinforces the failure mode rather than creating a new one. The candidate
was not describing the authoritative present; it was anticipating its own future
closure, which is the same pre-effect versus post-effect confusion recorded
above, observed this time inside the repair that documents it. It is also a
second datum for the B2/P2 named failed property: the constraint violated —
*describe the state that exists, not the state a future effect will create* —
was advisory, and nothing mechanical noticed.

## Research hypothesis — RECORDED / NOT ACTIVATED

    human disposition
      → mechanically bound terminal receipt/state
      → authorized provider effect
      → exact provider read-back
      → reconciled/regenerated current projection

**Status: RECORDED / NOT ACTIVATED.** This is a research hypothesis, not an
implemented, selected or proven architecture. No mechanism is chosen, no tooling
is built, and this record does not promote any candidate direction already
recorded for B2.

## Supporting evidence: current projection is not an event ledger

Two independent slices drove their task state to the same wall:

- B2/P1 `state.completed` reached its 20-item maximum before the slice closed;
- B2/P2 `state.completed` independently reached 20/20 while writing its
  close-out.

Current task state therefore repeatedly absorbed event-history pressure it was
not shaped to hold. That supports investigating the distinction
**current projection ≠ event ledger**, in which a compact replaceable current
view and an append-only history are separate surfaces with separate bounds.

The task-envelope schema is deliberately **not** redesigned here, and no
saturation fix is implemented or proposed as selected.

## Note on the policy gate that preceded this record

Repository mutation for this repair was initially blocked because the effective
Gnostoa self-policy requires a linked Work Item and Decision before
implementation for a `normal` change, and an agent stopped rather than proceed
without one.

That is positive **behavioural** evidence and nothing more. Nothing mechanically
prevented the mutation; the agent chose to stop. The gate remains advisory, which
is the same property this failure mode and the B2/P2 finding both describe.
