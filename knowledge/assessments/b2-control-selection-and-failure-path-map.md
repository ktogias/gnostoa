---
type: Source
title: B2 control selection and failure-path map
description: Evidence-derived taxonomy of observed control failures, a typed candidate-control matrix, established-practice study and three alternatives for one owner selection.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-17T16:40:00Z"
sources:
  - id: control-selection-work-item
    resource: https://github.com/ktogias/gnostoa/issues/31
    title: Map observed control failures and select one bounded enforcement experiment
  - id: b2-p1-measurements
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/assessments/b2-p1-streamlined-self-hosting-measurements.md
    title: B2/P1 streamlined self-hosting measurements
  - id: b2-p2-findings
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/assessments/b2-p2-fresh-session-and-effect-authority-findings.md
    title: B2/P2 fresh-session resume and effect-authority findings
  - id: design-by-contract
    resource: https://se.inf.ethz.ch/~meyer/publications/computer/contract.pdf
    title: Meyer, Applying Design by Contract
  - id: kubernetes-controllers
    resource: https://github.com/kubernetes/community/blob/main/contributors/devel/sig-api-machinery/controllers.md
    title: Kubernetes SIG API Machinery, writing controllers
  - id: stripe-idempotency
    resource: https://docs.stripe.com/error-low-level
    title: Stripe, advanced error handling and indeterminate results
  - id: idempotency-key-header
    resource: https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header
    title: IETF draft, the Idempotency-Key HTTP header field
  - id: github-required-checks
    resource: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
    title: GitHub, troubleshooting required status checks
  - id: transactional-outbox
    resource: https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
    title: AWS Prescriptive Guidance, transactional outbox pattern
x-project-knowledge:
  id: kit.assessment.b2-control-selection-and-failure-path-map
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: derived-from
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
    - kind: derived-from
      target: /assessments/b2-p1-streamlined-self-hosting-measurements.md
    - kind: references
      target: /failure-modes/post-effect-current-state-drift.md
---

# B2 control selection and failure-path map

## Recording boundary

Research and mapping only, under Issue #31 and Decision 0016's capability-loop
rule. **No control is implemented, selected or activated here.** The document
ends in one owner selection, and `NO CONTROL EXPERIMENT YET` is a valid outcome.

Two scope decisions shape everything below.

**Product defects are excluded from the control taxonomy.** B2/P1 recorded eight
material defect families in the envelope tooling itself — working-directory
dependence, checkout-normalization fragility, unbounded alias traversal, a
narrow CLI error boundary, a non-single-snapshot read, and the YAML-feature,
scalar-literal and schema-reference boundaries. Those were input-robustness
defects in a program, found by tests, a declared gate or review, and fixed. They
are not failures of *workflow control*, and counting them here would inflate any
candidate's apparent value.

**The earlier informal mapping is discarded as a source.** It claimed thirteen
paths while listing eleven, stated three P1 false-ready outcomes where the
canonical record says **five**, treated A–F as validated controls, and credited
read-back with preventing failures it can only detect. It is not cited below.

## Phase 1 — evidence-derived control failure taxonomy

Fifteen paths, deduplicated by mechanism rather than by which control might
address them. Recurrence appears only where reconstructable.

| ID | Failed property | Stage | Primary outcome | How it surfaced | Recurrence | Source |
|---|---|---|---|---|---|---|
| CF-1 | An agent performed a provider mutation with no admission for that effect | authority | unauthorized effect | detected after effect, by the agent | **2** episodes | P2 §2 |
| CF-2 | Verification was asserted complete while a required route had not run | verification | false readiness | detected after effect, by later reconstruction | 1 episode, 2 manifestations | P2 §5 |
| CF-3 | A verification route was structurally incapable of observing a defect class | verification | escaped until another route ran | detected only by the runtime-target gate | 1 | P1, route asymmetry |
| CF-4 | Durable state was written invalid against its own declared contract | state construction | incorrect state | detected after effect, before review | 1 | P2 §4 |
| CF-5 | An identity was written by hand where it could be computed | state construction | incorrect state | detected after effect | **3** values | P2 §6, §6b |
| CF-6 | A declared immutable dependency lay inside the task's own mutable scope | state declaration | ambiguous truth, self-invalidation | detected after effect | 1 | P2 §6b |
| CF-7 | Durable state was left behind work already completed | state advancement | stale representation misdirecting the next actor | detected after effect | 1 episode, 2 manifestations | P2 §3 |
| CF-8 | Readiness was asserted while a named precondition was false | readiness | false readiness | human review or later reconstruction | **P1 = 5, P2 ≥ 3** | P1, P2 §10 |
| CF-9 | Readiness was asserted about state the provider did not hold | observation | false readiness | owner disposition; not independently reconstructable | 1 | P2 §8 |
| CF-10 | Authorized effects completed while projections stayed one effect behind | projection | stale representation | detected after effect | 1 episode, 3 surfaces | drift record, #29 |
| CF-11 | A projection asserted a future provider state as current | projection | false current claim | **human semantic review only; all automated routes green** | 1 | #29 lesson 1 |
| CF-12 | A local command result was treated as evidence of external-effect outcome | provider effect | ambiguous truth, near-duplicate effect | prevented by read-before-retry | 1 | #29 lesson 2 |
| CF-13 | A constructed durable value silently lost meaning its source appeared to carry | representation | semantic loss; validator accepted it | found during later reconstruction | 3 values, 1 episode | P2 §7 |
| CF-14 | Current state absorbed event history until it saturated | representation, design | durable surface could not record its own work | observed at the bound | **2** independent slices | P1, P2 |
| CF-15 | A partial result was reported as overall success | reporting | control failure masked by orientation success | human review | 1 | P2 §9 |

Two observations follow from the table rather than from any candidate.

**CF-8 is by far the most recurrent path** — at least eight occurrences across two
slices — and every other readiness-adjacent path (CF-2, CF-9) manifested *as* a
false-ready event. **CF-11 is the only path that no automated route detected**;
the candidate carrying it was green on all five.

## Phase 2 — candidate controls and typed relations

Candidate directions A–F are inputs, regrouped here by mechanism boundary.

- **C1 effect admission with operation identity** — an external mutation requires
  an admission record naming that effect, carrying a stable operation identity.
- **C2 post-effect read-back and reconciliation** — after any external mutation,
  read authoritative state and reconcile projections; before any retry, read
  before deciding.
- **C3 computed state advancement** — identities computed, never accepted as
  written; state transitions checked for legality.
- **C4 deterministic readiness predicate** — `READY` is computed, refusing unless
  schema validation actually ran on the artifact, the required-suite result is
  bound to the exact head, the checkpoint chain verifies, declared and observed
  identities agree, the projection budget holds, and `next_action` and `handoff`
  are mutually consistent.
- **C5 verification-route completeness binding** — a route declares which
  artifacts it validated; any validity claim about an unvalidated artifact fails
  closed.
- **C6 representation-integrity check** — detect constructed values that differ
  materially from their source representation, and separate the replaceable
  current projection from append-only history.
- **C7 multidimensional outcome schema** — outcomes recorded per dimension, with
  no single aggregate verdict.

Relations use only the six permitted types. Evidence strength: **[G]** already
demonstrated in Gnostoa, **[P]** engineering-principle hypothesis, **[X]**
requires a future experiment.

| Path | C1 | C2 | C3 | C4 | C5 | C6 | C7 |
|---|---|---|---|---|---|---|---|
| CF-1 | PREVENTS **[P]** | DETECTS_AFTER_EFFECT **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-2 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | DETECTS_BEFORE_EFFECT **[P]** | PREVENTS **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-3 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | PARTIALLY_MITIGATES **[X]** | PARTIALLY_MITIGATES **[X]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-4 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | PARTIALLY_MITIGATES **[P]** | DETECTS_BEFORE_EFFECT **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-5 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | PREVENTS **[P]** | DETECTS_BEFORE_EFFECT **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-6 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | UNKNOWN | PARTIALLY_MITIGATES **[X]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-7 | NO_EXPECTED_EFFECT | PARTIALLY_MITIGATES **[P]** | PARTIALLY_MITIGATES **[P]** | DETECTS_BEFORE_EFFECT **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-8 | NO_EXPECTED_EFFECT | PARTIALLY_MITIGATES **[P]** | PARTIALLY_MITIGATES **[P]** | PREVENTS **[P]** | PARTIALLY_MITIGATES **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-9 | NO_EXPECTED_EFFECT | PREVENTS **[P]** | NO_EXPECTED_EFFECT | DETECTS_BEFORE_EFFECT **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-10 | NO_EXPECTED_EFFECT | DETECTS_AFTER_EFFECT **[P]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-11 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| CF-12 | PARTIALLY_MITIGATES **[P]** | PREVENTS **[G]** | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| CF-13 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | PARTIALLY_MITIGATES **[X]** | NO_EXPECTED_EFFECT | PREVENTS **[P]** | NO_EXPECTED_EFFECT |
| CF-14 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | PARTIALLY_MITIGATES **[X]** | NO_EXPECTED_EFFECT |
| CF-15 | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | PREVENTS **[P]** |

### Assurance boundaries that must not be blurred

- **Admission is not read-back.** C1 may stop an effect; C2 can only tell you
  what happened. They are not equivalent assurance.
- **A readiness gate does not prevent bad state being written.** C4 refuses to
  *promote* it. CF-4 and CF-5 would still occur and would be caught one step
  later.
- **Schema validity is not semantic truth.** CF-11 was schema-valid, green and
  false. This is the one path where the honest entry is `UNKNOWN` for every
  mechanical candidate, and the only demonstrated detector is a human.
### Exactly one [G] relation exists

**[G]** means the *same mechanism* has already been empirically demonstrated in
Gnostoa. A relation is **not** [G] because an underlying validator existed,
because a human later noticed the failure, because a related mechanism could have
noticed it, or because the candidate would compose checks that already exist. An
earlier revision of this assessment marked five cells [G] while claiming two; the
audit below reduces the count to **one**, and the narrative now agrees with the
matrix.

| Relation | Was | Now | Why |
|---|---|---|---|
| C2 → CF-12 | [G] | **[G]** | Read-before-retry was *actually performed* on the ambiguous PR-creation outcome and demonstrably prevented a duplicate Change Request. Same mechanism, same boundary, observed result. |
| C2 → CF-1 | [G] | **[P]** | No read-back control existed. The agent noticed its own violation. Self-noticing is not the mechanism. |
| C3 → CF-5 | [G] | **[P]** | `checkpoint_digest` existed as a *function*, but the control "identities are computed, never accepted as written" did not exist at that boundary — the digests were hand-written past it. This is precisely the "underlying validator existed" exclusion. |
| C4 → CF-4 | [G] | **[P]** | No readiness predicate existed. Schema validation demonstrably rejects that state *when run*, but the relation under test is the predicate, not one of its future components. |
| C4 → CF-5 | [G] | **[P]** | Same distinction as C4 → CF-4. |

The correction lowers the apparent evidence behind Alternative 2 and leaves
Alternative 3 holding the only demonstrated relation in the matrix. That shift is
reported rather than smoothed over; evidence strength was not raised anywhere to
make an alternative look better.

## Phase 3 — established practice

- **Design by contract.** Meyer's preconditions, postconditions and invariants
  are the direct ancestor of C4: a routine refuses to proceed unless its
  precondition holds, and the obligation is stated where it is checked rather
  than in prose.
- **Level-triggered reconciliation.** Kubernetes controllers reconcile *observed*
  against *desired* state read at reconcile time rather than reacting to events,
  which is exactly the shape C2 would need; the drift in CF-10 is what an
  edge-triggered, hope-based workflow produces.
- **Idempotency and indeterminate results.** Stripe treats a failed mutation as
  *indeterminate* and reconciles rather than assuming, and the IETF
  `Idempotency-Key` draft exists because a client cannot tell from a timeout
  whether a resource was created. CF-12 is that exact problem, and stable
  operation identity plus read-before-retry is the established answer.
- **Required checks bound to the exact head.** GitHub's own rule is that checks
  from earlier commit SHAs do not satisfy a requirement. C5 generalises the same
  binding to the artifacts a route claims to have validated.
- **Transactional outbox.** Relevant as a *warning*: it solves atomic
  state-plus-effect at the cost of a relay, a store and duplicate suppression.
  Adopting it here would be the general-orchestration outcome Decision 0016
  forbids without measured need.

The research question is the smallest useful invariant, not which framework
implements these patterns.

## Phase 4 — comparison

| Dimension | C1 admission | C2 read-back | C3 computed state | C4 readiness predicate | C5 route binding | C6 representation | C7 outcome schema |
|---|---|---|---|---|---|---|---|
| Prevents | CF-1 | CF-9, CF-12 | CF-5 | CF-8 | CF-2 | CF-13 | CF-15 |
| Detects earlier | — | CF-1, CF-10 | — | CF-2, CF-4, CF-5, CF-7, CF-9 | CF-8 | — | — |
| Untouched | most state paths | CF-4, CF-5, CF-8 | most effect paths | **CF-1, CF-10, CF-11** | most state paths | all effect paths | all state paths |
| New mutable state | admission record | none | none | none | route manifest | none | none |
| Provider-specific | **yes, high risk** | partly | no | only for one input | partly | no | no |
| More human prompts | **yes** | no | no | no | no | no | no |
| More foreground evidence | some | some | no | no | some | no | **less** |
| One small primitive | no | plausible | **yes** | **plausible** | plausible | plausible | **yes** |
| Falsifiable self-test | yes | yes | **yes** | **yes** | yes | yes | weak |
| Cleanly removable | hard | yes | **yes** | **yes** | yes | yes | yes |
| Historical manifestations of the paths it *hypothetically* relates to | 2 | 3 | 3 | ≥ 11 | 2 | 3 | 1 |
| Blast radius if absent | high | medium | medium | **high** | medium | medium | low |

The historical-manifestation row counts **observed occurrences of the failure
paths** a candidate is *hypothesised* to relate to. It is not a measure of
demonstrated control effectiveness, and it must not be read as one: with exactly
one [G] relation in the matrix, no candidate has demonstrated effectiveness
against any path except C2 against CF-12. Recurrence, relation type, evidence
strength, blast radius, maintenance cost and human-attention cost are kept as
separate dimensions above and are deliberately not combined into a score.

**C1 is the highest-risk candidate despite addressing a serious path.** It adds
human approval prompts and pulls provider-specific authority into the portable
core — the two costs Decision 0016 and the reverse-centaur failure mode single
out.

## Owner selection

Three alternatives. Each meets the admission bar, or is stated as not meeting it.

### Alternative 1 — deterministic readiness predicate (C4)

- **Primary failed property:** CF-8, readiness asserted while a named
  precondition was false, at least eight occurrences.
- **Strongest benefit:** the one computed refusal that also detects CF-2, CF-4,
  CF-5, CF-7 and CF-9 one step earlier, and it is the direct application of
  design by contract to the one claim that repeatedly proved false.
- **Strongest limitation:** it does not touch CF-1, CF-10 or CF-11, and it does
  not stop invalid state being written — only promoted.
- **Surface:** one predicate over existing artifacts. No new mutable state, no
  provider abstraction, no extra human prompt.
- **Narrow experimental form — C4-v0.** The candidate under consideration is
  **not a general workflow engine**. C4-v0 is a deterministic, **read-only**
  `READY` predicate over existing evidence. It creates no canonical state,
  advances no state, performs no external effect, grants no authority and adds no
  human approval prompt. It returns `READY` only when its declared existing
  preconditions are satisfied, and otherwise returns one bounded blocking reason.
  This is research framing only; **C4-v0 remains NOT SELECTED / NOT ACTIVATED**
  until the owner disposition, and no implementation fixtures are created here.
- **Falsifiable test:** replay P1's five and P2's three false-ready states; the
  predicate must refuse each, and must not refuse the states that were genuinely
  ready.
- **Key uncertainty:** false-block rate on legitimately ready candidates.

### Alternative 2 — computed state advancement (C3), the smaller precursor

- **Primary failed property:** CF-5, an identity written where it could be
  computed, three values.
- **Strongest benefit:** the smallest possible implementation surface. The
  primitive already exists — `checkpoint_digest` computes correct digests today
  and was simply not called — so the change is to route identities through it
  rather than to build anything. This is a **surface** argument, not an evidence
  argument: after the [G] audit the relation C3 → CF-5 is **[P]**, a hypothesis.
- **Strongest limitation:** narrow. Leaves CF-8 and every effect path untouched.
- **Falsifiable test:** the two 61-character digests and the wrong dependency
  value must become impossible to express, not merely rejected.
- **Key uncertainty:** whether it is large enough to change any measured outcome.

### Alternative 3 — post-effect read-back and reconciliation (C2)

- **Primary failed property:** CF-10, authorized effects completing while
  projections stay behind; with CF-12 as the second path.
- **Strongest benefit:** the established level-triggered reconciliation shape, and
  one [G] prevention already demonstrated when read-before-retry stopped a
  duplicate Change Request.
- **Strongest limitation:** it **detects**, it does not prevent, CF-10 and CF-1.
  Drift would still occur and would still need someone to act on the report.
- **Falsifiable test:** after a merge and Work Item closure, the loop must report
  every projection contradicted by provider state, with no false report on the
  #29 close-out that was deliberately written to survive its own effects.
- **Key uncertainty:** whether reporting without enforcement changes behaviour at
  all, given that CF-10 was already noticed by a human without it.

### Not recommended in this round

C5 overlaps C4's strongest benefit at similar cost; C6 addresses real but
lower-recurrence representation paths; C7 is cheap but touches one path; and
**C1 is deliberately not offered** — its provider coupling and added human prompts
are the costs Decision 0016 warns against, and CF-1 has been reliably detected
and corrected in both observed episodes.

### CF-11 has no mechanical candidate

The one path that survived every automated route has `UNKNOWN` against **every**
candidate, including C7. An earlier revision gave C7 a `PARTIALLY_MITIGATES`
relation here, which contradicted this section; the conservative resolution is
`UNKNOWN`, because no exact evidence supports a mechanical relation.

CF-11 was **schema-valid and green on every automated route, and human semantic
review was the only demonstrated detector.** No alternative above claims to
address it, and this Work Item does not invent one.

## Uncertainties

- CF-8's true count is a floor, not a measurement; session-internal readiness
  claims leave no repository or provider trace.
- CF-9's exact moment is not reconstructable.
- Every **[P]** relation is an engineering-principle hypothesis, not a Gnostoa
  result. Exactly **one [G]** relation exists in the whole matrix.
- Recurrence counts measure *observation*, not frequency: paths that no route
  could see are under-counted by construction, which is precisely CF-3's point.
