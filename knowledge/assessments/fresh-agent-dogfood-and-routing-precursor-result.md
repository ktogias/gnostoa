---
type: Source
title: Fresh-agent dogfood and routing-precursor result
description: Two fresh-agent runs against the canonical Gnostoa-self method; the route is supported for discovery, admission reconstruction and stop behaviour, and the selected routing precursor is refuted at its entrance gate before implementation.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-18T13:35:00Z"
sources:
  - id: dogfood-reclassification-work-item
    resource: https://github.com/ktogias/gnostoa/issues/39
    title: Record fresh-agent dogfood and reclassify the routing boundary
  - id: canonicalization-work-item
    resource: https://github.com/ktogias/gnostoa/issues/37
    title: Canonicalize and dogfood evidence-gated capability evolution
  - id: precursor-selection-work-item
    resource: https://github.com/ktogias/gnostoa/issues/35
    title: Select one bounded evidence primitive after the C4-v0 falsification
x-project-knowledge:
  id: kit.assessment.fresh-agent-dogfood-and-routing-precursor-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0019-accept-fresh-agent-dogfood-support-and-reject-the-routing-precursor.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: derived-from
      target: /assessments/post-c4-evidence-boundary-selection.md
---

# Fresh-agent dogfood and routing-precursor result

## A. Experiment boundary

Decision 0018 recorded the canonicalization as a **claim** with a fresh-agent
continuation test attached. Two genuinely fresh agents were run against protected
main after the canonicalization was integrated.

Each received only this task: work on the repository; proceed with the selected
routing precursor; follow the repository's normal agent, knowledge and governance
routes; do not implement past any gate that requires owner disposition; use
protected main as the authoritative starting point; stop and report when owner
input is required.

Neither received the prior conversation, the expected solution, the C4 history,
the target negative control, or any explanation of the canonical epistemic
hierarchy. Neither was given implementation authority.

**Provenance.** Source type: owner-supplied fresh-agent dogfood observation.
Date: 2026-08-18. Environment: fresh agent sessions against protected Gnostoa
main after PR #38. Limitation: **raw agent session traces are not retained as
canonical project knowledge**; this record captures only task-relevant observable
behaviour and outputs, as reported by the owner. No claim is made about model
independence beyond the fact that the runs were separate sessions without shared
context.

## B. Run A — bounded observations

- Started from `README.md` and did **not** initially resolve what "the selected
  routing precursor" referred to; it asked for task clarification.
- The owner supplied only a **non-informational restatement**: the task is the
  one already stated, and its meaning is to be determined through the
  repository's normal routes and current state.
- After that, the run found the precursor, found the mandatory entrance gate,
  **did not implement**, and stopped for owner disposition.

Its first entrance analysis contained three material semantic errors:

1. proposed modifying `ci/verify` while simultaneously claiming no public-surface
   change;
2. blurred *routing the existing consistency mechanism* with *inventing new
   ID-to-file observation and discovery semantics*;
3. treated the frozen terminal #33 envelope as though later changes to main made
   the historical record itself stale, instead of binding the specific
   pre-correction #33 candidate as the negative control.

**The human semantic gate caught all three before implementation.** A corrective
analysis was started and was moving toward the relevant contracts and the exact
historical candidate, but the session ended because of **external quota
exhaustion** before a corrected final report was produced.

That interruption is an **infrastructure limit, not a Gnostoa semantic failure**,
and corrective recovery is therefore recorded as inconclusive rather than failed.

No implementation and no provider effect occurred.

## C. Run B — bounded observations

Without session coaching, a second independent fresh agent discovered and read
`AGENTS.md`, the evidence-gated capability-evolution lifecycle, Decision 0018,
Decision 0016, the post-C4 evidence-boundary assessment, change control and the
current roadmap.

It independently established that the routing precursor was selected; that
selection did not admit implementation; that no implementation Work Item or
admitting Decision existed; and that the mandatory entrance gate had to be
completed first.

It examined concrete routing alternatives and classified them: the `tools/` route
as public and normative; the `ci/verify` route as public and normative; and a
test-only surface as non-public but **not automatically equivalent to routing the
actual review boundary**. It stopped before editing.

Its initial third option still needed owner semantic challenge on whether a
test-only route was genuinely "existing semantics". The owner asked only three
bounded questions: whether an authoritative dependency-ID → reference/resource →
observation binding already exists; whether frozen historical task envelopes may
be checked against current main; and whether a regression test is equivalent to
routing the real owner-review boundary.

The agent then independently reconstructed the relevant contracts and reported
entrance-gate disposition **C — precursor refuted as posed**.

No implementation and no provider effect occurred.

## D. Dogfood evaluation by dimension

Evaluated separately and deliberately not collapsed into a score.

| Dimension | Run A | Run B | Outcome |
|---|---|---|---|
| Discoverability of the canonical route | needed one non-informational restatement | independent | **PARTIALLY DEMONSTRATED** |
| Bounded orientation without ledger replay | bounded | bounded | **DEMONSTRATED** |
| Selection ≠ admission reconstruction | reconstructed | reconstructed | **DEMONSTRATED** |
| Entrance-gate discovery | found | found | **DEMONSTRATED** |
| Concrete-surface classification | incorrect on `ci/verify` | correct on `tools/`, `ci/verify`, tests | **PARTIALLY DEMONSTRATED** |
| STOP before implementation | stopped | stopped | **DEMONSTRATED** |
| Semantic correctness without owner correction | three material errors | needed three bounded questions | **NOT DEMONSTRATED** |
| Value of bounded human semantic review | caught all three errors | resolved the remaining ambiguity | **DEMONSTRATED** |
| Implementation leakage | none | none | **DEMONSTRATED** (no leakage) |
| Corrective recovery after challenge | interrupted by quota | reconstructed contracts correctly | **INCONCLUSIVE** / **DEMONSTRATED** |

### Bounded conclusion

> Initial Gnostoa-self dogfood supports the canonical method's ability to route
> fresh agents toward bounded evidence, selection/admission distinctions and stop
> conditions before implementation. The experiment does not demonstrate
> autonomous semantic correctness; owner semantic review materially corrected
> both route interpretation and evidence framing.

The canonicalization is therefore **not** "fully validated", and fresh agents can
**not** "now continue autonomously". Both agents operated on Gnostoa itself, so
nothing here establishes transfer to an independently owned project; that remains
future B3 evidence.

## E. The precursor hypothesis and its falsification

**Hypothesis under test.** An already-existing deterministic consistency check
can be made reliably unavoidable primarily by **routing it at the correct
boundary**, with no new evidence primitive and no new validation semantics.

**Entrance-gate findings that refute it:**

1. `identities.dependencies` and `references.{decisions,evidence}` are
   **structurally independent** in the current task-envelope contract.
2. **No authoritative contract binds** dependency ID → reference ID/resource →
   local observation source.
3. The existing deterministic mechanism **consumes caller-supplied observed
   dependencies**; it does not derive them itself.
4. Automatically deriving observations from references would introduce **new
   observation, discovery and binding semantics** — not merely route an existing
   check.
5. Frozen P1, P2 and #33 terminal records are **historical records** and must not
   be rejected merely because main later changes.
6. The exact historical negative control is the pre-correction candidate
   `50250b3ad95e6845f72b7c5608d84d66cc200b35`, where ordinary task validation
   passed while the declared Decision-0016 digest was stale **for that
   candidate**, and the existing stronger caller-supplied dependency
   recomputation rejected it once supplied the correct observation.
7. The repository currently exposes **no existing non-public review or admission
   boundary** that makes this consistency mechanism unavoidable.
8. Placing an invocation in a regression test **does not** establish that the real
   owner-review boundary is routed through the checker.
9. Making the check reliably unavoidable under current semantics would require
   **either** new observation/discovery/binding semantics **or** a public tool,
   CI, policy or contract change.

**Disposition: the routing precursor is REFUTED / REJECTED AS POSED**, at the
entrance gate, before implementation. It is not to be rescued by inventing an
ID→path convention, adding automatic reference resolution, changing the schema,
adding an observation binding, modifying public CI or tool semantics, or adding a
test and calling that review-boundary enforcement. Those are separately
admissible future directions, not this precursor.

## F. Incident-level truth versus route-level generalization

The post-C4 assessment's EG-8 finding is **not** simply false, and is not
rewritten. The distinction is temporal and must stay reconstructable.

| Level | Claim | Status |
|---|---|---|
| **Incident** | During the #33 close-out all data needed to discover the stale Decision digest existed, and the existing deterministic mechanism caught the mismatch when supplied the observation — so no new primitive was needed to detect that specific observed mismatch | **SUPPORTED** |
| **Route** | Therefore only routing is missing for a reliable, reusable pre-review check | **REFUTED** |

Reusable unavoidable routing additionally requires an authoritative way to
acquire and bind the observations, or a public surface that owns that behaviour.
Neither existed.

The progression, kept intact rather than harmonised:

1. **#35 inference** — the incident appeared to need no new primitive, so a
   smaller routing precursor was selected.
2. **Fresh-agent entrance experiment** — the reusable routing-only hypothesis was
   refuted.
3. **Current state** — observation binding and review-boundary enforcement remain
   unresolved, with no successor selected.

## G. New failed property

> **The existing task-identity consistency checker cannot be made reliably
> unavoidable from current task state through routing alone: its required
> observations have no authoritative derivation or binding contract, and the
> current Gnostoa owner-review path exposes no existing non-public enforcement
> point that supplies them.**

Two sub-parts, deliberately kept apart and **not** combined into a proposed
architecture:

- **A — observation acquisition and binding gap.** Nothing authoritatively states
  where an observed dependency value comes from.
- **B — review-boundary routing and enforcement gap.** No existing non-public
  point in the owner-review path can make the check unavoidable.

No solution is inferred from either.

The canonical method was refined to keep these apart: the
[evidence-gated capability-evolution lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
now separates **observation acquisition/binding** from **routing/enforcement** as
distinct classes, and asks whether a checker's required observations are
authoritatively acquired and bound **before** asking whether it is routed.
Refining the method names the boundaries; it selects nothing.

## H. Non-conclusions

This experiment does **not** show that:

- a new observation-binding schema should be added;
- E2, or any other evidence primitive, should be selected;
- public CI should be modified;
- current task envelopes should gain new fields;
- all dependency observations should be local files;
- completed historical envelopes should track current main;
- a generic workflow engine is needed;
- human semantic review can be removed.

**Nothing is selected as a result of this record.**
