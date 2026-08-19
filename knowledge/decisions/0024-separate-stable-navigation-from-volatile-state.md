---
type: Decision
title: Reduce Gnostoa current-state drift by separating stable navigation from volatile state
description: Gnostoa-self authoring discipline that keeps stable navigation separate from provider-owned lifecycle state and unbound current-outcome state, without selecting any checker, audit or enforcement mechanism.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T10:20:00Z"
sources:
  - id: drift-work-item
    resource: https://github.com/ktogias/gnostoa/issues/56
    title: Reduce recurring current-state drift from volatile projections
  - id: post-effect-drift-record
    resource: https://github.com/ktogias/gnostoa/issues/29
    title: Reconcile post-effect current-state drift after B2/P2 integration
x-project-knowledge:
  id: kit.decision.0024.separate-stable-navigation-from-volatile-state
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /assessments/current-state-drift-retrospective.md
    - kind: references
      target: /failure-modes/post-effect-current-state-drift.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Reduce Gnostoa current-state drift by separating stable navigation from volatile state

Recorded by `agent:claude-opus-5` from the accountable maintainer's disposition.
The semantic choice is the maintainer's; this record is faithful transcription.

Scope: **Gnostoa-self navigation and current-projection authoring only.**

## Context

`post-effect-current-state-drift` named the failed property in 2026-08-17:
authorized provider effects complete while repository current-state and resume
projections remain one effect behind. A bounded read-only retrospective over the
durable repository and provider record has now measured how that property behaves
across the whole project history, and the
[retrospective](../assessments/current-state-drift-retrospective.md) holds the
evidence.

Three findings make a bounded authoring rule worth recording.

**The family recurs, and it has two dimensions rather than one.** Work Item #54
demonstrated that temporally neutral *relationship* wording — "remediation is
tracked by #54 … provider state remains authoritative for that Work Item's
lifecycle" — survived that Work Item's closure with no edit. The adjacent
sentence in the same paragraph copied a mutable *outcome* verdict, and did not.
Both halves sit eighteen words apart in one paragraph, which separates
lifecycle-state neutrality from outcome-state neutrality about as cleanly as
evidence can.

**The repair can create the next defect.** The Change Request that removed a stale
"the active item is #50" assertion introduced, in the same edit, the copied
outcome sentence that later went stale. Removing one duplicated volatile fact
while adding another is not a net improvement.

**Not every drift family shares this root.** Identity and dependency-binding drift
is the most frequent family in the record and is untouched by any wording change;
resume, verification-expectation and observation drift are separate again. A
single unifying mechanism is not justified, and this Decision does not attempt
one.

What was missing was not a mechanism. It was an explicit rule about which kinds of
state durable navigation should carry at all.

## Decision

**A. Historical immutable facts remain historical.** A record that was true about
a moment stays true about that moment and is **never rewritten merely because the
present has changed**. Pre-effect evidence is preserved and post-effect results
are added alongside it, so chronology stays reconstructable.

**B. Provider-owned lifecycle state is not normally mirrored as a static
assertion.** Do not write `active`, `open`, `pending`, `is the active item` or
equivalent into source when a stable relationship plus a provider-authority route
suffices. Name the relationship — which Work Item owns the work, which Decision
governs it — and let the provider own open/closed, labels, assignee and
timestamps.

**C. Candidate and result outcomes may appear in navigation when materially
useful, but only when explicitly bound.** A retained outcome must be past-tense,
scoped to a named completed slice, scoped to the measured subject or platform, and
linked to the candidate-bound result record that carries it. Outcome information
is **not** removed from navigation wholesale; unbound outcome claims are.

**D. Avoid unbound current language.** `the current candidate is…`, `the blocker
currently remains…`, `not admitted until…` and equivalents are forbidden in static
source when the authoritative outcome is expected to change independently of that
source. The failure is not the tense alone; it is an unbound subject plus a
mutable verdict.

**E. Stable Decision semantics stay separate from timestamped external
observations.** A Decision states the rule. Exact vendor versions, feed status,
measured inventories and candidate-time observations live in timestamped result
records, so that a changing external world cannot turn into stale policy.

**F. Deterministically computable current values are not duplicated as static
literals** merely for convenience. The current public-surface digest is
recomputable on demand and changes whenever the public surface changes; copying it
creates a new drift opportunity for no durable gain. A copy requires a measured
orientation need. **Historical release digests bound to an immutable commit are
not copies in this sense and must not be removed.**

**G. Current navigation links rather than restates.** Route to the provider for
lifecycle, to candidate-bound result records for measured outcomes, and to
immutable records for historical identity.

**H. Close-out includes bounded semantic reconciliation.** Before a slice is
complete: provider state is read back; candidate and result state are read back;
static navigation is re-read and is still truthful *after* the closure or effect;
no future effect is predicted; immutable history is unchanged.

**I. Tests should prefer semantic invariants over volatile current wording** — but
**this Decision selects no test change**, and none is made in the slice that
records it.

**J. No mechanism is selected.** No checker, freshness engine, audit script,
provider adapter, state synchronizer, event store, derived-projection engine, CI
gate or enforcement route.

**K. Identity and dependency-binding drift remains a separate family** with a
separate root and a separate — already existing, and unrouted — deterministic
mechanism. It is not addressed here.

**L. The observation acquisition and binding gaps identified through Decisions
0018 and 0019 remain unresolved and are not bypassed.** Nothing here derives an
observation, binds a reference to a source, or routes a check at a review
boundary.

**M. Human semantic review remains required** for judging whether prose reads as
current and whether removing a copy costs more orientation than it saves. No
oracle decides that.

**N. This is Gnostoa-self only.** It is not generic adopter guidance, not a
consumer obligation, and not promoted to the public inherited surface.

**O. The retrospective's proposed read-only audit — its "Half 2" — is not
admitted.** It requires a separate owner disposition after this discipline has
been applied and its residual measured.

## Consequences

- Navigation carries less state and more routing. That is the intended trade, and
  it costs a reader one extra hop for any fact that changes independently of the
  source.
- Orientation loss is the real risk, so this Decision is recorded together with a
  fresh-actor falsification test rather than assumed to be safe. If a fresh actor
  cannot recover the material results through the normal route, the discipline was
  applied too aggressively and must be narrowed — by adding a bounded
  candidate-bound pointer, never by restoring an unbound current verdict.
- Choice **C** deliberately refuses the maximal form of this rule. Removing all
  outcome information from navigation was considered and **not** selected, because
  the one measured instance of that pattern left a needed value recorded nowhere in
  the repository.
- Decisions 0020, 0021, 0022 and 0023 are unchanged, as are the source-release
  runbook, `v0.1.0`, `deployable_artifact: false`, the deferred B3 pilot, the
  rejected C4-v0 predicate and the rejected routing precursor. Decision 0016's
  numbered increment sequence is unchanged and increment 2 stays **not activated**.
- This Decision does not claim to solve drift. It removes one demonstrated class
  of avoidable opportunity and leaves the remaining families explicitly named and
  unmitigated.
