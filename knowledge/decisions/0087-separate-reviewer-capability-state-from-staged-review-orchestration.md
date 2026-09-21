---
type: Decision
title: Separate reviewer capability state from staged review orchestration
description: Adopt a Gnostoa-self reviewer capability registry and staged review-collection policy that preserves scarce external review for stable subjects while leaving qualification, semantic quorum and provider-write authority unchanged.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-21T22:29:45Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5765148226
    title: Owner admission — reviewer capability registry and staged review orchestration baseline
  - id: l0-baseline
    resource: ../assessments/15-l0-lite-observed-workflow-baseline.md
    title: WI-DET-01 L0-lite observed workflow baseline
  - id: capability-baseline
    resource: ../assessments/reviewer-capability-quota-orchestration-baseline.md
    title: Reviewer capability, quota and orchestration baseline
  - id: capability-registry
    resource: ../assessments/reviewer-provider-capabilities.json
    title: Reviewer provider capability registry snapshot
  - id: review-capture
    resource: ./0061-retain-individual-agent-review-dispositions.md
    title: Retain individual agent review findings and dispositions
  - id: review-assurance
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Evaluate semantic review assurance through bound evidence and an advisory deterministic gate
  - id: useful-l1
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
x-project-knowledge:
  id: kit.decision.0087.separate-reviewer-capability-state-from-staged-review-orchestration
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
    - kind: references
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
---

# Separate reviewer capability state from staged review orchestration

## Context

Gnostoa has accumulated enough real multi-provider review history that the old
informal practice "trigger all reviewers again" is no longer a harmless default.

The L0 baseline measured substantial exact-head review churn. Later PRs added
more direct provider evidence:

- some reviewers do not normally auto-review Draft PRs;
- some accept detailed instructions in their trigger comment while others are
  more reliable when the trigger comment contains only the command;
- some have per-PR automatic re-review limits;
- some have account-wide rolling budgets or billing-period reviewed-line
  quotas;
- some are credit-gated;
- some can refuse a particular large PR while remaining generally available;
- analyzer/autofix products can mutate the branch and therefore create a new
  candidate rather than review evidence.

Treating these as one undifferentiated "reviewer list" wastes quota, creates
stale exact-head evidence and can mistake provider unavailability for either a
clean result or a semantic blocker.

Decision 0086 intentionally excluded reviewer trigger/wait orchestration from
useful L1. Issue #10/#11/R2A already own qualification, independence, evidence
semantics and review-assurance outcomes. The missing layer is smaller:
deterministic scheduling knowledge about when and how to ask external reviewers
for evidence.

## Decision

Adopt an implementation-private **reviewer capability registry** plus a
Gnostoa-self **staged review-collection policy**.

The registry and scheduler may decide *which review route is worth attempting
now* and *how that route must be invoked*. They do not decide whether a reviewer
is qualified, independent, sufficient for quorum, semantically correct or
authoritative.

### 1. Separate four state classes

The implementation and records must keep these classes distinct:

1. **Capability** — relatively stable provider behavior such as supported
   trigger channels, Draft behavior and incremental/full-review modes.
2. **Availability** — account/workspace state such as quota exhausted, credits
   required or retry-after.
3. **Subject eligibility** — current PR-specific constraints such as Draft
   state, diff size, unsupported subject or missing provider configuration.
4. **Review evidence** — a completed result bound to one exact review subject.

Capability may be cached as dated knowledge. Availability and subject
eligibility are volatile and require revalidation before a scarce scheduling
decision when the retained observation is stale or unknown. Review evidence
continues to use the existing exact-subject and review-assurance contracts.

A missing quota observation is `UNKNOWN`, not `UNLIMITED`. Historical
precedence is valid only when provider, scope, applicable subject and a
**non-null matching non-secret `scope_identity`** are the same and an exact
provider/source `event_at` is attributable. A null account/workspace identity
is historical-only and cannot authorize automatic dispatch or cross-observation
supersession.

The implementation-private registry must expose one planner-facing contract:
every provider uses the same typed `manual_trigger` fields, while every
volatile account/repository/subject fact is carried through one normalized
`observations[]` array with explicit scope, `scope_identity`, `event_at`
and `observed_at`. Provider-specific parser branches are not an acceptable
substitute for a shared registry shape.

For historical interpretation, comparable observations are ordered by exact
RFC3339 `event_at`; `observed_at` records when Gnostoa acquired/retained the
observation and never substitutes for event ordering. `retry_after` is an
advisory forecast and cannot override a later attributable event. A newer
`FAILED` or `TIMED_OUT` attempt does not assert `UNAVAILABLE`, but it
invalidates reuse of older cached `AVAILABLE` for automatic dispatch until
provider availability/eligibility and current scope identity are revalidated.

No fixed freshness TTL is invented. For automatic dispatch of an external
review route, current availability/eligibility must be reacquired in the current
orchestration observation cut. Version `v0.10` binds that proof explicitly:
the active planning input carries `cut_id`, exact `as_of` and exact subject.
A provider `current_readback` is a **same-cut route-target evaluation**, not a
raw retained observation. It must carry the same `cut_id` and a
`planning_subject` equal to the exact active PR/head. Its separate fact-level
`subject` remains faithful to the declared scope: account scope has
`subject=null`, repository scope stays repository-scoped, and subject scope
uses the exact subject. The read-back carries independent
`availability_state` and `eligibility_state`; automatic scarce-review
dispatch requires `AVAILABLE` and `ELIGIBLE` in the same cut, with current
non-secret scope identity where required and a provider-current-readback source.
Adapters may combine separately acquired account/workspace availability and
exact-subject eligibility only when both were acquired in that same cut; they
must not rewrite the underlying fact scope. Incomplete or ambiguous composition
is `REVALIDATION_REQUIRED`.

The separate historical `observations[]` subject rules remain scope-faithful:
for `scope: subject`, the normalized subject must include `repository`,
`change_request` and `head_commit`; a non-null head matches only that exact
candidate. A null head is historical-only and must force revalidation rather
than match current state. Repository/account observations retain null
change-request/head or null subject respectively and must not be promoted into
exact-subject completion or directly substituted for `current_readback`.

The registry's `observation_status_vocabulary` must contain every declared
terminal and nonterminal route state plus any descriptive provider-event
statuses. Each observation also carries a mandatory `route_state` that belongs
to the terminal/nonterminal route-state vocabularies. Descriptive `status`
retains provider-event meaning; only `route_state` determines orchestration
terminality. A `COMPLETED` route state means the provider route/attempt completed, not that
current-head semantic review assurance is satisfied. Repository-scope
descriptive events are configuration/behavior history and carry
`route_state: UNKNOWN`; only separately subject-bound exact-head evidence can
enter the existing qualification/assurance path. This keeps event fidelity without forcing
descriptive labels into terminal/nonterminal state classes.

### 2. Isolate each reviewer invocation by provider channel

For comment-driven reviewers, Gnostoa-self sends one reviewer invocation in one
top-level comment. Different reviewers are not batched into the same comment.
For UI, API, GitHub-app and interactive-agent routes, the registry-provided
channel is used instead of inventing a comment trigger. A generic comment
command whose ownership is not isolated from other installed apps is not
eligible for automatic dispatch until repository-specific collision behavior is
verified.

The registry declares the smallest known-safe trigger form, an explicit
instruction contract and independent dispatch-safety metadata. Typed
`dispatch_kind` separates `comment_command`, `provider_action`,
`configuration_only`, `interactive_manual` and `unknown`; a UI action,
configuration path or manual sentinel may never be reinterpreted as GitHub
comment syntax. An `instruction_mode` such as `none` describes syntax only
and cannot override a `manual_only_until_*` dispatch-safety state.

A planner may emit only a retained typed recipe whose fields satisfy the
machine-readable `dispatch_kind_constraints`, or render a retained
`instruction_template` using supported placeholders and bounded
caller-supplied instructions. Version `v0.10` fixes a 4096-byte normalized
UTF-8 instruction maximum, CRLF/CR-to-LF normalization, HT/LF-only
control-character allowance, reserved-placeholder rejection and one
non-recursive substitution pass. Invalid input becomes
`MANUAL_ONLY_NO_DISPATCH`. Optional-template empty instructions reduce to
command-only; required-template empty instructions are invalid. Where isolation
is required/recommended, instructions may not contain another retained
comment-trigger command. The planner must never invent provider syntax or
instruction prose. When no deterministic recipe is retained, the route is
`manual_only`.

In particular, the current Sourcery operating rule uses a dedicated comment
whose complete body is:

```text
@sourcery-ai review
```

because Gnostoa has direct evidence that the standalone command restores fresh
review after its automatic-review counter is exhausted.

This is an invocation/reliability rule, not a semantic-review requirement.

### 3. Stage review collection around candidate stability

Use these logical orchestration phases:

```text
DRAFT_BUILD
  -> PREFLIGHT_CLEAN
  -> EARLY_REVIEW
  -> REPAIR
  -> SEAL_EXACT_HEAD
  -> READY_FINAL_COLLECTION
  -> RECONCILE_REVIEW_CUT
  -> OWNER_DECISION_BOUNDARY
```

The phases do not replace the canonical evidence-gated lifecycle. They are a
narrow projection for external review collection.

#### DRAFT_BUILD / PREFLIGHT_CLEAN

Apply deterministic normalization, focused verification, authoritative CI where
applicable and self-review before spending scarce final-review capacity.

#### EARLY_REVIEW

Invoke only selected reviewers whose current eligibility and expected value
justify reviewing an unstable candidate. Draft-capable or cheap/unrestricted
routes are preferred here. A configured reviewer is not automatically selected.

#### SEAL_EXACT_HEAD

The candidate to be used for final review is explicitly identified after the
relevant deterministic and CI gates are clean.

#### READY_FINAL_COLLECTION

Transition the provider PR to Ready when final collection is intended, then
**reacquire current-head provider request/review state before any manual
trigger**. For each selected reviewer and exact head, use exactly one activation
path: if Ready already auto-started or completed a current-head request/review,
wait for or reconcile that request and do not manually retrigger it. Only routes
with no current-head activation may be considered for a manual trigger, and only
after their dispatch-safety and current-eligibility requirements are satisfied.

Final collection is not "every integration at any cost." A
`REVALIDATION_REQUIRED` route may leave the active selected set only through an
explicit `DESELECTED_OPTIONAL` disposition after protected policy/R2A already
establishes that the route/domain is optional. That disposition is not review
evidence and cannot satisfy a required domain or capability. If required-domain
status is incomplete or unknown, revalidation failure remains blocking.

#### REPAIR

Batch related findings where possible before minting another final candidate.
**For final semantic-review evidence, any repair that changes the candidate head
first invalidates the complete prior final review cut and transitions the
provider PR back to Draft before the mutation is pushed.** This exact-head rule
is a specific exception to the general subject-rebinding rule: non-review
evidence may still be reused when its relevant subject is proven unchanged, but
final semantic-review evidence is never reusable across heads.

This prevents Ready-only automatic reviewers from spending quota on an unstable
pre-CI successor. After deterministic/CI re-verification, seal the new exact
head, transition to Ready again, and obtain fresh evidence from every review
domain required by the effective review policy/qualification result. Optional
older-head reviews remain historical only and cannot count in the successor cut
unless re-run.

A Ready PR may remain Ready only for reconciliation or finding disposition that
does not change the candidate head. The planner's `final_review_cut` is bound
to one exact `head_commit`; if the candidate head changes, the whole cut is
`INVALIDATED_HEAD_CHANGED` and every protected required domain is reacquired
under a new cut. Architecture, provider abstractions, broad production behavior,
scope/classification expansion or another implementation phase additionally
return the internal workflow to broader development. GitHub Draft/Ready remains
a provider projection of orchestration state, not the complete state machine.

### 4. Treat availability as a scheduling outcome, not a review verdict

The scheduler may use terminal route states such as:

- `COMPLETED`;
- `SKIPPED`;
- `QUOTA_EXHAUSTED`;
- `CREDIT_REQUIRED`;
- `UNAVAILABLE`;
- `UNSUPPORTED_FOR_SUBJECT`;
- `FAILED`;
- `TIMED_OUT`;
- `DESELECTED_OPTIONAL`.

`DESELECTED_OPTIONAL` is terminal only as an explicit scheduling disposition
for a policy-established optional route. It never counts as review evidence,
never satisfies a required review domain/capability, and is forbidden when the
required-domain status is unknown or incomplete.

`FAILED` and `TIMED_OUT` are terminal for one invocation attempt, not for
the semantic requirement, and must never become "clean review" observations.
The read-only planner has zero automatic retry authority. After same-cut
revalidation, a required or unknown-required route produces
`MANUAL_ESCALATION_REQUIRED` and remains blocking until a later successful
exact-head result or other policy-sufficient qualified evidence exists. The
planner neither invents backoff nor performs provider writes. A separately
authorized provider-write effect may create a new activation identity on the
same exact head after current eligibility is revalidated; only its later result
can advance the route. Optional routes may be deselected only under the
protected optional-route rule.

Nor does every unavailable configured reviewer block convergence. The effective
Gnostoa review policy remains authoritative for required distinct domains and
capabilities. If its required evidence is satisfied, optional provider
unavailability is retained as truthful operational evidence rather than a
blocker.

### 5. Keep semantic and authority boundaries unchanged

This Decision does not change:

- Issue #10 reviewer capability/independence authority;
- Issue #11 semantic capture and review-assurance semantics;
- Decision 0067 / R2A outcomes, quorum or qualification;
- `policy/review-policy.yaml`;
- accountable-owner semantic approval;
- merge authorization.

Reviewer count, provider count and registry entries remain descriptive until
the existing protected qualification/policy path says otherwise.

### 6. Select a read-only planner as the next implementation

After this normative baseline is reviewed and integrated, the next #15 slice
should implement a deterministic **read-only review planner**.

It consumes current state and produces an advisory plan containing at least the
outputs listed below. The input contract also carries the exact planning cut,
provider-current read-backs, optional provider/request
`attempt_id`/activation identity, the current final-review cut, and protected
required-domain input. Multiple same-head attempts whose identity/order cannot
be established are `REVALIDATION_REQUIRED`, never deduplicated by guess:

- orchestration phase;
- exact candidate identity;
- selected early-review routes;
- selected final-review routes;
- routes currently unavailable and reason;
- typed provider-specific trigger recipe;
- the opaque required-domain identifiers/statuses supplied by effective
  review-policy/R2A input, without deriving independence from provider count;
- an explicit blocker whenever any required domain remains incomplete;
- whether Draft/Ready transition is recommended;
- next permitted orchestration action.

It must not post comments, request reviewers, change Draft/Ready state, resolve
threads, approve or merge. Protected required-domain input is an opaque
pass-through: every `id` and `status` is preserved unchanged, and readiness
remains blocked unless that protected input is complete, bound to the current
exact head and reports `all_required_satisfied=true`. Missing or ambiguous
protected input is blocking regardless of how many optional provider routes
completed.

The planner must consume the existing L1 projection and protected
review-policy/R2A results rather than reimplement current-state, qualification,
independence or semantic-review logic.

### 7. Defer the dispatcher to a separate effect-capable Decision

Any future component that actually posts reviewer trigger comments or mutates
provider lifecycle state crosses a new write boundary.

That dispatcher requires separate admission and must address:

- exact-subject stale-state revalidation;
- per-provider trigger adapters;
- idempotence and duplicate-trigger prevention;
- quota/retry coordination;
- effect receipts and provider read-back;
- least-privilege credentials;
- failure isolation without false success;
- interaction with existing L1 publication writes.

No such authority is created here.

## Alternatives considered

### Trigger every installed reviewer after every commit

Rejected. It maximizes stale review evidence and quota consumption and ignores
the measured reviewed-head churn already present in L0.

### Trigger every reviewer only when Ready

Too coarse. It protects scarce final reviewers but loses useful early feedback
from reviewers that can cheaply inspect a Draft or selected intermediate head.

### Encode quota/provider behavior directly in the reducer or R2A

Rejected. Quota and trigger syntax are provider operations, not semantic review
truth. Mixing them into R2A would violate the provider-neutral authority
boundary established by Decisions 0067 and 0086.

### Treat every configured reviewer as mandatory

Rejected. Gnostoa has already corrected this mistake in practice: the review
policy requires qualified domains, not completion by every installed vendor.

### Build the write-capable dispatcher immediately

Rejected for this slice. The evidence supports scheduler knowledge first; a
dispatcher would add provider-write and retry/idempotence risks before the
read-only plan has demonstrated value.

## Verification and falsification

This is a normative/process Decision plus an implementation-private registry.
Review should challenge at least:

- whether a capability fact has been confused with dated account availability;
- whether any "unlimited" claim is inferred from missing evidence;
- whether a provider trigger syntax is claimed without documentation or direct
  repository observation;
- whether the staged workflow can hide an unavailable required review domain;
- whether Ready/Draft guidance can wrongly reuse stale exact-head review
  evidence;
- whether the proposed planner would duplicate R2A or current-state semantics;
- whether any text accidentally grants provider-write or merge authority.

The companion JSON must remain valid JSON and its source links must be
individually attributable. Repository policy/knowledge validation and fresh
semantic review remain required before integration.

## Consequences

Gnostoa gains one durable place to record reviewer trigger, Draft, quota and
availability behavior without turning volatile provider state into policy.

Review collection becomes explicitly cost-aware and exact-head-aware:
deterministic feedback early, scarce review diversity late.

The new registry is advisory implementation knowledge, not a public adopter
contract. It may evolve as providers change behavior. Dated observations should
be superseded, not silently rewritten into timeless truths.

The next implementation is deliberately read-only. Automatic review dispatch is
deferred.
