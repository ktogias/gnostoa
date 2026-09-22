---
type: Decision
title: Separate reviewer capability state from staged review orchestration
description: Adopt a Gnostoa-self reviewer capability registry and staged review-collection policy that preserves scarce external review for stable subjects while leaving qualification, semantic quorum and provider-write authority unchanged.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-21T23:58:39Z"
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
orchestration observation cut. Version `v0.16` binds that proof explicitly:
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

The registry declares the smallest known-safe trigger form, stable retained
route identities, an explicit instruction contract and independent dispatch-safety
metadata. Every manual primary/alternative surface has its own `route_id`; an
attributable Ready-triggered automatic/configurable surface has a distinct
`ready_activation.route_id`. Current read-back, activation deduplication and
reconciliation use the exact retained surface identity rather than provider
name, command text or array position. Typed
`dispatch_kind` separates `comment_command`, `provider_action`,
`configuration_only`, `interactive_manual` and `unknown`; a UI action,
configuration path or manual sentinel may never be reinterpreted as GitHub
comment syntax. An `instruction_mode` such as `none` describes syntax only
and cannot override a `manual_only_until_*` dispatch-safety state.

A planner may emit only a retained typed recipe whose fields satisfy the
machine-readable `dispatch_kind_constraints`, or render a retained
`instruction_template` using supported placeholders and bounded
caller-supplied instructions. Version `v0.16` fixes a 4096-byte normalized
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
  -> PRE_READY_RECONCILE
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

#### PRE_READY_RECONCILE

Before recommending Draft→Ready, consume one typed
`provider_activation_scan` for every provider whose Ready behavior is
automatic, configurable, unknown, or otherwise not proven non-automatic, plus
any provider already used for early review on the exact head. Each scan is bound
to the PRE_READY cut, provider, exact subject and scan time and reports
`COMPLETE|INCOMPLETE|AMBIGUOUS` completeness plus
`PRESENT|ABSENT|AMBIGUOUS` activation state.

Negative evidence is strict: only `COMPLETE + ABSENT` establishes that the
provider has no same-head activation. The scan must cover every provider-native
review/request/summary/status/check surface available to that adapter. A
provider-authored mutable summary/footer/source URL that explicitly names the
exact head is current provider/head activity even if the specific route identity
is unavailable. A mutable update timestamp or generic success status alone is
not attribution. Incomplete or contradictory surfaces are
`REVALIDATION_REQUIRED`, never safe absence.

For `PRESENT` same-head activity, provider-level mutual exclusion applies even
when `route_id=null`. If Ready automatic activation cannot be excluded, current
Ready-activation and provider-level same-head deduplication facts are required.
Ready is safe only when the Ready path is disabled/not applicable or
provider-level same-head deduplication is established; otherwise the next action
is manual disposition.

Immediately before the Ready effect, refresh the exact head, lifecycle state and
all PRE_READY scans. Any new provider activity, head/base/lifecycle change or
competing orchestration receipt after the cut invalidates the recommendation and
restarts PRE_READY_RECONCILE. This reduces TOCTOU risk but does not create an
atomic provider lock; a future write-capable dispatcher requires separately
admitted lease/fencing authority.

Providers whose Ready path may auto-activate are therefore reserved from
same-head early review by default unless current state proves the Ready path
disabled/not-applicable or provider-level same-head deduplication established.

#### READY_FINAL_COLLECTION

Transition the provider PR to Ready only after PRE_READY_RECONCILE is safe.
Treat that lifecycle mutation as a typed effect boundary and retain a
`ready_transition_receipt` bound to the PRE_READY cut and exact head. Then mint
a **new POST_READY planning cut** whose `as_of` follows the transition receipt
and reacquire current-head provider request/review state before any manual
trigger. A PRE_READY read-back can never satisfy this ordering guard.

For each selected reviewer and exact head, use exactly one activation path: if
Ready already auto-started or completed a current-head request/review, wait for
or reconcile that request and do not manually retrigger it. Only routes with no
current-head activation may be considered for a manual trigger, and only after
their dispatch-safety and current-eligibility requirements are satisfied under
the POST_READY cut.

Final collection is not "every integration at any cost." A
`REVALIDATION_REQUIRED` route may leave the active selected set only through an
explicit `DESELECTED_OPTIONAL` disposition when protected assurance already
reports `PASS` or an authority-produced route binding marks that stable
`route_id` optional for current assurance. That disposition is not review
evidence and never advances qualification/quorum. While protected assurance is
not `PASS`, a route claimed to advance assurance must have a complete protected
route→reviewer/source→independence-domain binding; missing or ambiguous binding
is `QUALIFICATION_ROUTE_BINDING_REQUIRED`, never guessed optionality.

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
head, transition to Ready again, and collect fresh exact-head evidence before
recomputing the protected R2A assurance result. Older-head review observations,
qualified-domain results and route activations remain historical only and cannot
count in the successor cut.

A Ready PR may remain Ready only for reconciliation or finding disposition that
does not change the candidate head. The planner's `final_review_cut` is bound
to one exact `head_commit` and protected assurance/qualification revision; if
the candidate head changes, the whole cut is `INVALIDATED_HEAD_CHANGED` and
protected assurance is recomputed under a new cut. Architecture, provider abstractions, broad production behavior,
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
when protected assurance is already `PASS` or an authority route binding marks
the route optional for current assurance. It never counts as review evidence
and never advances qualification or quorum. Missing/ambiguous binding cannot be
turned into optionality by the planner.

`FAILED` and `TIMED_OUT` are terminal for one invocation attempt and must never
become "clean review" observations. The read-only planner has zero automatic
retry authority. After same-cut revalidation, a `policy_eligible` route that can
advance protected assurance produces `MANUAL_ESCALATION_REQUIRED`; a missing or
ambiguous route qualification binding produces
`QUALIFICATION_ROUTE_BINDING_REQUIRED`. A separately authorized provider-write
effect may create a new activation identity on the same stable `route_id` and
exact head after current eligibility is revalidated; only a later protected R2A
result decides whether assurance advanced. Optional routes may be deselected
only under the authority-bound optional-route rule.

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

It consumes current state and produces an advisory plan from the exact planning
cut, provider-current read-backs, stable route identities and **protected
assurance input aligned with the existing R2A/Issue #10 contracts**.

Historical observations also carry nullable `route_id`. A null identity is
truthful when the old provider event cannot be attributed to one retained
activation surface; it remains semantic/provider evidence but cannot suppress a
current route or participate in route-level attempt precedence.

Protected assurance carries, without reinterpretation:

- exact `subject_head_commit`;
- R2A `outcome` and `reason`;
- `minimum_distinct_domains` from effective policy;
- current `qualified_domain_ids` and required capabilities from R2A;
- the accepted qualification revision; and
- authority-produced `route_bindings` that join stable `route_id` values to
  Issue #10 reviewer/source identities, independence domains and capabilities.

The binding producer, not the planner, applies qualification status, freshness,
owner relation, scope and required-capability rules and marks route policy
eligibility/optionality. The planner must not infer an independence domain from
provider identity, route count, model name or registry capability claims.

When exact-head protected assurance is `INCOMPLETE / QUORUM_UNMET`, the planner
may prefer a current AVAILABLE+ELIGIBLE, policy-eligible route whose bound
independence domain is not already in `qualified_domain_ids`. That preference
is only review scheduling diversity. The planner never awards domain credit or
declares quorum; only a later protected R2A evaluation can do so. Missing or
ambiguous binding for a route claimed to advance assurance is an explicit
`QUALIFICATION_ROUTE_BINDING_REQUIRED` blocker.

The advisory plan contains at least:

- orchestration phase;
- exact candidate identity;
- selected early-review route IDs;
- selected final-review route IDs;
- routes currently unavailable and reason;
- typed provider-specific trigger recipe keyed by stable `route_id`;
- protected assurance outcome/reason, minimum-domain requirement and current
  qualified-domain IDs as pass-through facts;
- protected route-binding status for routes considered assurance-advancing;
- explicit blockers for incomplete assurance or missing qualification binding;
- whether Draft/Ready transition is recommended;
- next permitted orchestration action.

It must not post comments, request reviewers, change Draft/Ready state, resolve
threads, approve, merge, qualify reviewers, map providers to domains on its own,
or decide quorum. Owner-decision readiness remains blocked unless protected
assurance is complete, bound to the current exact head and reports `PASS`.
Many completed provider reviews may truthfully coexist with
`INCOMPLETE / QUORUM_UNMET`.

The planner must consume the existing L1 projection, protected R2A result and
accepted Issue #10 qualification/binding projection rather than reimplement
current-state, qualification, independence or semantic-review logic.

### 7. Defer the dispatcher to a separate effect-capable Decision

Any future component that actually posts reviewer trigger comments or mutates
provider lifecycle state crosses a new write boundary.

That dispatcher requires separate admission and must address:

- exact-subject stale-state revalidation;
- fresh PRE_READY cut consumption plus lifecycle/WorkLease fencing so a stale or
  concurrently superseded recommendation cannot mutate Draft/Ready state;
- typed Ready-transition receipts and POST_READY cut creation;
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
- whether the staged workflow can hide an unmet protected assurance requirement;
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
