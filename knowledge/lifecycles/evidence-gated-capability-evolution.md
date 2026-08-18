---
type: Lifecycle
title: Evidence-gated capability evolution
description: The canonical Gnostoa-self method for evolving workflow, governance, evidence and control capabilities from observed failure through bounded research, owner selection, admission and falsifiable implementation.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-18T10:20:00Z"
sources:
  - id: canonicalization-work-item
    resource: https://github.com/ktogias/gnostoa/issues/37
    title: Canonicalize and dogfood evidence-gated capability evolution
x-project-knowledge:
  id: kit.lifecycle.evidence-gated-capability-evolution
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: references
      target: /lifecycles/toolkit-evolution.md
    - kind: derived-from
      target: /assessments/b2-p1-streamlined-self-hosting-measurements.md
    - kind: derived-from
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
    - kind: derived-from
      target: /assessments/b2-control-selection-and-failure-path-map.md
    - kind: derived-from
      target: /assessments/b2-c4v0-readiness-predicate-experiment.md
    - kind: derived-from
      target: /assessments/post-c4-evidence-boundary-selection.md
    - kind: derived-from
      target: /failure-modes/post-effect-current-state-drift.md
    - kind: references
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: references
      target: /decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md
---

# Evidence-gated capability evolution

**Scope: Gnostoa itself.** This is canonical operating knowledge for maintaining
and evolving this project. It is **not** guidance for adopting projects, and must
not be copied into `guidance/` or `templates/`. See
[Decision 0018](../decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md).

Read this before proposing implementation of a new workflow, governance,
evidence or control capability.

Everything here was learned from this project's own failures. Each rule links the
result that produced it. The method records uncertainty and negative results; it
is not a universal law, and evidence may contradict it.

## Seven states that are not synonyms

Confusing these states repeatedly caused observed rework, premature claims and
unnecessary mechanism expansion.

| State | Means | Does **not** mean |
|---|---|---|
| **Evidence** | something observed and recorded | that it was interpreted correctly |
| **Research / inference** | a bounded study of options | that anything was chosen |
| **Owner selection** | the owner chose what to try next | permission to implement |
| **Implementation admission** | policy gates satisfied for *this* concrete diff | that the design is right |
| **Implementation** | the thing exists | that it works |
| **Experimental result** | measured outcome, positive or negative | success |
| **Adoption / promotion** | it is kept, and possibly inherited | that it transfers to other projects |

*Why recorded:* the C4-v0 slice held selection, admission and implementation
apart across three separate owner effects, and the post-C4 slice selected a
precursor while explicitly refusing to admit it.

## Delivery and admission sequence

```
OBSERVED EVIDENCE
  → FAILURE / GAP CLASSIFICATION
  → BOUNDED RESEARCH
  → OWNER SELECTION
  → CONCRETE PROPOSED EFFECT / ROUTING / OWNERSHIP LOCATION
  → CONCRETE PROPOSED CHANGED SURFACE
  → CHANGE CLASSIFICATION
  → PUBLIC-SURFACE / AUTHORITY / COMPATIBILITY IMPACT
  → REQUIRED RECORDS + PRE-IMPLEMENTATION EVIDENCE
  → IMPLEMENTATION ADMISSION
  → SMALLEST FALSIFIABLE IMPLEMENTATION
  → MEASUREMENT / HISTORICAL REPLAY
  → OWNER DISPOSITION
  → RETAIN / NARROW / REDESIGN / REMOVE
  → PROVIDER READ-BACK
  → CURRENT-PROJECTION RECONCILIATION
```

### Concrete location before classification, classification before implementation

Both halves are required, and neither licenses the other. Abstract intent is not
enough to classify trustworthily — but "derive the class from a real diff" never
means *edit first and classify afterwards*. Effective policy requires
classification and the applicable pre-implementation evidence **before**
implementation.

1. identify the concrete **proposed** effect, routing or ownership location;
2. identify the concrete **proposed** changed paths, surfaces and semantic effect;
3. derive the change class from that proposed diff and surface, **before**
   implementation;
4. determine public-surface, authority, compatibility and blast-radius impact;
5. satisfy the Work Item, Decision and evidence gates that the actual class
   requires;
6. obtain implementation admission;
7. implement the smallest admitted change;
8. **reclassify upward** if the actual implementation diff expands or changes
   semantic impact.

A *concrete proposed diff* means the specific files, surfaces and semantic
behaviour an actor proposes to change. It does **not** mean repository state that
has already been edited without admission.

### Qualifications

- **Not every slice needs every record.** `policy/change-control.yaml` determines
  the actual gates for the actual change class.
- selection ≠ admission; admission ≠ implementation; implementation ≠ validation;
  validation ≠ promotion.
- Actual scope expansion can require upward reclassification.
- Provider effects require authoritative **read-back**; local command success is
  not provider-effect truth.
- **A negative result is valid** and completes a slice.
- Derived current projections are replaceable and **must not predict their own
  future provider effects**.

This is a method, not a workflow state machine. Do not build an engine from it.

*Why recorded:* post-effect current-state drift (projections left one authorized
effect behind, and the repair candidate then projected its own future closure);
the C4-v0 close-out, where the reviewed candidate had to be corrected twice
before integration.

## Epistemic order

Ask these in order. Several observed failures skipped directly to later
architectural questions before earlier epistemic questions were resolved.

### 1. What can the system actually know?

Identify the available observation, evidence, oracle, provenance and
uncertainty. **If no observation or oracle can establish the fact, classify it as
an oracle limit** rather than inventing an evidence artifact to cover it.

*Why recorded:* three of eight recorded false-ready states were latent product
defects behind uniformly green evidence. No evidence mechanism could have
rejected them, and counting them as coverable would have been false coverage.

### 2. Does an existing deterministic mechanism already check the property?

If yes, **prefer reuse over a new primitive**. Do not create a second mechanism
because the existing one was not routed correctly.

*Why recorded:* during the #33 close-out a stale declared Decision digest passed
ordinary task validation, and the existing projection recomputation caught it the
moment it was invoked. Nothing was missing except the invocation.

### 3. Is the existing mechanism reliably executed at the relevant boundary?

If no, investigate **routing, invocation and admission** before inventing new
evidence.

- A unit test proving a checker works is **not** evidence that the real review or
  effect boundary invokes it.
- A green route is **not** sufficient evidence that the intended check ran.
- **Skipped, empty or bypassed execution does not count as execution.**

*Why recorded:* all five C4-v0 control tests skipped inside the container while
the route reported `OK (skipped=5)`; B2/P1 found development-container green
insufficient for a change touching the CLI. GitHub's protected-branch semantics
likewise accept a skipped required check as satisfying it, so this is a property
of the standard mechanism, not a local defect.

### 4. Only if evidence is genuinely missing, consider a new evidence primitive

Before creating one, establish: which real observed undecidability it changes;
how the evidence is acquired; how it is bound to its subject or candidate;
whether it survives integration; public-surface impact; human-attention cost;
evidence-amplification risk; and its removal condition.

**Do not create evidence infrastructure merely because a rejected experiment
asked a question the current system could not answer.**

*Why recorded:* the post-C4 research compared three candidate primitives, found
none demonstrated at its own boundary, and the owner selected none of them.

### 5. Compose larger controls only after smaller mechanics demonstrate value

Do not jump from a prose rule to a readiness gate, capability broker, state
machine, workflow engine or evidence platform. Require measured need.

*Why recorded:* C4-v0 went from a named failed property to a readiness predicate
in one step and was refuted; its implementation was removed rather than retained.

### 6. Preserve bounded human semantic judgement for oracle limits

Mechanical evidence cannot prove a fact that no available oracle can establish.
**Human semantic review is not a temporary defect the architecture must
eliminate.** For semantic, current-truth and unknown-defect classes, preserve a
bounded human decision boundary.

Human semantic judgement remains necessary for oracle-limit and semantic classes.
Other failures may be detected by human review, by direct inspection, or by a
deterministic mechanism once the appropriate mechanism actually runs.

Keep three classes apart — collapsing them is how a routing problem gets
misdiagnosed as a missing primitive:

| | Class | What it means | Right response |
|---|---|---|---|
| **A** | fact and evidence exist, and an existing deterministic checker can establish it | the mechanism is available | run it; prefer reuse |
| **B** | the fact may be observable, but the correct mechanism or its routing did not execute | a routing or invocation problem | fix routing before inventing evidence |
| **C** | no available oracle can establish the fact | an **oracle limit** | bounded human judgement; do not simulate certainty |

**An existing mechanical mechanism that was not routed is fundamentally different
from an oracle limit.**

*Why recorded, by class:* the #33 stale declared Decision digest was class A/B —
detected by the **existing deterministic dependency recomputation** once that
stronger mechanism was actually invoked, not by human reading. The C4-v0
container skip was found by **direct inspection of what actually executed**. The
three latent product defects behind uniformly green evidence were class C and
were found by **human semantic review**, because no oracle of the time could
establish them.

## Anti-patterns and stop conditions

- **Mechanism rescue** — do not add features until a falsified experiment passes.
- **Sunk-cost retention** — experimental code need not survive a rejected
  hypothesis.
- **Evidence amplification** — do not make an append-only event ledger the human
  interface.
- **Declaration gaming** — a mechanism must not become easier to satisfy by
  declaring less.
- **False-green routing** — success status does not prove the intended work
  executed.
- **Premature genericity** — self-dogfood success does not establish adopter
  value.
- **Advisory-mechanics confusion** — prose instruction is not mechanical
  enforcement.
- **Selection/admission collapse** — selected ≠ admitted ≠ implemented ≠
  validated ≠ promoted.

*Why recorded, in order:* the C4-v0 no-rescue disposition; the removal of 677
lines after that refutation; three consecutive slices saturating `state.completed`
at 20/20; the C4-v0 candidate that reached READY only by declaring no provider
identity; the container skip; Decision 0017's refusal to promote a self-hosted
control; B2/P2's finding that critical constraints are advisory rather than
mechanically enforced; and the five distinct states above.

## Where the evidence lives

This record states the method and links its causes. It deliberately does not
retell the incidents.

- [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md) — capability-loop rationale and bounded-slice architecture
- [Decision 0017](../decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md) — the self-versus-public boundary applied to one experiment
- [B2/P1 measurements](../assessments/b2-p1-streamlined-self-hosting-measurements.md) — false-ready outcomes, route asymmetry, evidence defects
- [B2/P2 findings](../assessments/b2-p2-fresh-session-and-effect-authority-findings.md) — fresh-session resume, effect authority, the narrowed product claim
- [Post-effect current-state drift](../failure-modes/post-effect-current-state-drift.md) — projections trailing authorized effects
- [Control selection and failure-path map](../assessments/b2-control-selection-and-failure-path-map.md) — the failure taxonomy and typed candidate relations
- [C4-v0 readiness predicate experiment](../assessments/b2-c4v0-readiness-predicate-experiment.md) — the refutation, its five findings and the removal
- [Post-C4 evidence boundary selection](../assessments/post-c4-evidence-boundary-selection.md) — evidence gaps, oracle limits, and selecting no primitive
- [Self-dogfood bootstrap assessment](../assessments/gnostoa-self-dogfood-bootstrap-assessment.md) — the original value-and-cost record

## Status and authority

This method is **canonical Gnostoa-self operating knowledge**, adopted by
Decision 0018.

It is **not** generic or adopter guidance, and it is **not** `stable`. Canonical
authority and knowledge-lifecycle maturity are related but not identical:
promoting this record to `stable` would be a distinct human verification choice
under the repository's own rules, and has not been made. The record stays `draft`
while the semantic method is owner-adopted.

## Next falsifiable dogfood check

Canonicalization is a **claim**, not a result. It is falsified or supported by
one fresh-agent continuation test, to be run **after** this record is integrated.

**Setup.** A fresh agent receives only ordinary orientation: root `AGENTS.md`,
repository `main`, the current roadmap, and the active precursor Work Item once
one exists. It receives **no** conversation history, no custom explanation of
this method, and no incident replay unless this record tells it to load a
specific artifact.

**Task given.** *Proceed with the selected routing precursor.*

**Expected independent behaviour, in this order:**

1. orient through root `AGENTS.md`, protected `main`, the current roadmap and the
   active precursor Work Item if one is supplied;
2. follow the `AGENTS.md` route to this lifecycle, Decision 0016, applicable
   policy, and **only** the bounded evidence the unresolved question needs;
3. recognise that **selected ≠ admitted**;
4. identify the concrete proposed routing location **before editing**;
5. identify the proposed changed paths and semantic surface;
6. derive the intended change class from that concrete proposed change;
7. determine public-inheritance, authority and compatibility impact, and the
   semantic and admission gates the class requires;
8. create **or link** the Work Item and Decision that class requires — if the
   task already supplies an active precursor Work Item, **use it rather than
   create a duplicate**;
9. establish the required pre-implementation characterization or failing
   evidence;
10. **stop for the owner before implementation** when public-surface impact needs
    a new Decision, when actual scope differs from the selected precursor, or
    when another genuine semantic choice is unresolved;
11. only after admission, implement the smallest routed use of the **existing**
    deterministic consistency mechanism;
12. create no E1, E2, E3, C4-v1, C2, C3, new readiness semantics or new evidence
    infrastructure.

**Controls the experiment must keep.** The historical #33 stale-digest state is
the negative control; the valid P1, P2 and #33 records are bounded positive
controls; the intended mechanism must **demonstrably execute**, and skipped,
empty or bypassed execution is not success. **A regression test that directly
invokes the checker is not, by itself, evidence that the actual review or
admission boundary routes through it.**

**Provisional success.** The agent reconstructs the epistemic order without
session coaching; does not jump directly to implementation; does not propose a new
primitive first; preserves selection ≠ admission; discovers the entrance gate;
identifies the correct owner stop when one is needed; and loads bounded evidence
rather than replaying historical ledgers.

**Do not blame or prompt-engineer the agent into passing.** If a fresh agent
cannot recover the method from the canonical route, the canonicalization is
falsified or incomplete.

**A negative result here is valid and informative.** If a fresh agent still
cannot route itself, the defect is in this record, not in the agent.
