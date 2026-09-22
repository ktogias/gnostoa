---
type: Runbook
title: Deliver a bounded self-hosted slice
description: Short Gnostoa-self operational route from current-subject orientation through exact-candidate verification, authorized integration, subject re-binding and close-last reconciliation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T07:25:33Z"
sources:
  - id: delivery-practice-work-item
    resource: https://github.com/ktogias/gnostoa/issues/80
    title: Canonicalize bounded self-hosted delivery practice
x-project-knowledge:
  id: kit.runbook.deliver-bounded-self-hosted-slice
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: governed-by
      target: /decisions/0058-harden-behavioral-diagnosis-evidence-authority.md
    - kind: governed-by
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: governed-by
      target: /decisions/0087-separate-reviewer-capability-state-from-staged-review-orchestration.md
    - kind: depends-on
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /runbooks/maintain-the-kit.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
---

# Deliver a bounded self-hosted slice

**Scope: ordinary changes to Gnostoa itself.** This is an operational route, not
a second lifecycle and not adopter guidance. The
[evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
owns epistemic order, gap classes, selection/admission and oracle limits.

## Compact task input

An ordinary task prompt normally supplies only the concrete task or selected
owner outcome, authoritative starting subject, admitted scope and exclusions,
task-specific stop conditions, material evidence, authorized effects and the
result needed for the next owner decision. There is no fixed length limit.

## Preconditions

- The current source and provider subject can be read back.
- The concrete task, admitted scope and accountable owner are known.
- Any required Work Item, Decision and pre-implementation evidence are present
  before implementation begins.
- When the proposed work originates from a finding, its finding provenance and
  admission state can be identified separately from the evidence that discovered
  it.

## Prior-art and reuse checkpoint

Before creating or materially revising an Issue, Decision or PR, and before new
code or implementation, check existing project work and suitable external
projects for the same bounded need. Apply this checkpoint before the procedure's
create/admission steps, including finding capture. Prefer using, adapting or
composing an existing suitable mechanism; justify the remaining custom work.

First inspect the current Work Item, related PRs, Decisions and relevant project
knowledge, then consult primary project documentation and license sources for
plausible external alternatives. Preserve one compact assessment in the owning
Work Item, Decision or PR, linked from subsequent steps. Research may be prepared
locally before that first record is created. A separate report, fixed source
count or new issue solely for the search is not required. Retain:

- the question, scope, research date and the sources/search boundary inspected;
- plausible candidates, the versions or revisions inspected, intended use and
  relevant capabilities, limitations and operational/maintenance cost;
- license and provenance evidence for that use, including applicable dependency,
  distribution, attribution and NOTICE obligations; consult
  [the licensing contract](https://github.com/ktogias/gnostoa/blob/main/LICENSING.md) rather than treating an inventory
  or an "open source" label as compatibility clearance;
- the disposition: use, adapt, compose or implement the residual need, with
  reasons for rejecting material alternatives and remaining uncertainty.

Running an external service, adding a dependency and copying or distributing
material are different uses. Resolve material license uncertainty before the
affected acquisition, copying, dependency or distribution effect; record an
unavailable search as incomplete rather than inventing a negative result.
Research itself supplies no implementation admission or effect authority.

If no suitable complete project is found within the recorded search, inspect
relevant established practices, patterns and antipatterns before custom design.
State what transfers to this task and what still needs verification. An existing
checker, orchestration tool or template does not establish that its inputs are
authoritative, its invocation is unavoidable or its result has a real consumer.

At each later transition, reuse the assessment when its question, scope and
material inputs still apply. Revalidate affected conclusions when requirements,
candidate/version, license, environment or security/support facts change; avoid
both a stale blanket approval and a full repeated search for an unchanged need.
The reviewer checks applicability and rationale alongside the actual candidate.
This is review enforcement, not a software gate or proof of search completeness.
The existing emergency route retains its declared timing and follow-up.

## Procedure

1. **Orient and read back the current subject.** Start through `AGENTS.md`; bind
   protected source, provider lifecycle and the active Work Item without replaying
   raw conversations. Before creating another Work Item or PR for the same outcome,
   read provider state for an existing open same-purpose record. Resume it when it
   already owns the outcome; otherwise explicitly separate or supersede it before
   creating a competing canonical path. Use Decision 0016's resume route.
2. **Classify the observed gap.** Apply the
   [canonical lifecycle](../lifecycles/evidence-gated-capability-evolution.md);
   do not infer a new mechanism or implementation from research or selection.
3. **Check finding provenance and admission.** When the proposed change comes from
   a retrospective, experiment, evaluation, review, incident analysis or similar
   finding, apply the
   [explicit-admission requirement](../requirements/retrospective-findings-require-explicit-admission.md).
   Capture the observation in its owning evidence first. Resume the existing
   same-purpose Work Item when it already owns the outcome; otherwise create one
   focused tracked Work Item with desired outcome, bounded acceptance criteria,
   scope and explicit admission condition. Issue creation is capture, not
   implementation admission and does not automatically become active WIP or
   `roadmap:now`. A lesson without a concrete actionable outcome may remain
   knowledge-only. Stop before implementation until a separate observable owner
   admission selects the work under the current classification, Decision,
   pre-implementation evidence and effect boundary.
4. **Acquire bounded evidence or research.** Reuse or update the
   [prior-art assessment](#prior-art-and-reuse-checkpoint), load only what
   distinguishes the proposed result and preserve negative findings. Confirm
   its applicability again before a Decision, PR or implementation transition.
5. **Obtain an owner semantic choice when required.** Oracle or unresolved
   semantic limits remain human decisions.
6. **Name the proposed surface and class.** Use the generic
   [change workflow](../../guidance/workflows/propose-review-merge-change.md) and
   `policy/change-control.yaml`; reclassify upward if the real surface expands.
7. **Satisfy implementation admission.** Create or link required records and
   establish the applicable pre-implementation evidence before editing. A finding
   Work Item recorded for backlog capture satisfies durable tracking only; it does
   not satisfy this admission step until its separately declared admission state is
   observed.
8. **Make the smallest admitted change.** When the Requirement's applicability
   criteria hold, apply the
   [bounded behavioral-traceability requirement](../requirements/bounded-behavioral-traceability.md)
   and record its initial behavior map in the active Work Item or change record
   **before the first semantic production mutation**. Use explicit prospective,
   `NOT RUN`, `UNKNOWN` and `PENDING` states where candidate or evidence does not
   exist yet; re-bind the final candidate and evidence before review. An
   unresolved contradiction or unsupported narrowing blocks review-ready
   disposition. When material diagnostic ambiguity exists, keep task obligations,
   semantic hypotheses and implementation claims separate; retain the evidence
   authority/dependency needed to show what each item can actually establish.
   Then follow the
   [verification-first workflow](../../guidance/workflows/develop-verification-first.md)
   and keep specialized semantics in their owning runbooks.
9. **Verify the exact candidate.** Inspect the final diff, identify the measured
   subject, run applicable local/runtime checks and record actual results. For an
   applicable behavior map, independently reconcile the behavior map against the
   exact task, candidate and evidence. When the task has material diagnostic
   ambiguity or comparable high correctness risk, use a bounded two-pass reviewer
   route: **independent task-to-code pass** first, then **map reconciliation pass**.
   In the first pass, inspect the exact task and candidate before consuming the
   executor's final diagnosis/map conclusions and record materially plausible
   causes, affected paths or interpretation risks. In the second pass, compare
   that view with the executor's hypotheses, rejected alternatives, evidence
   authority/dependencies and final candidate. A different model or fresh context
   may reduce correlated blind spots but does not establish evidence independence.
   Reviewer inference remains inference; unresolved task identification remains
   unresolved rather than becoming acceptance. A passing test that preserves
   task-prohibited behavior remains a blocker. Apply
   [supplied-agent review capture](#supplied-agent-reviews) when reviews are
   received, including outside this exact-candidate checkpoint.
10. **Verify the exact PR head.** Provider checks must bind to that head; inspect
    required jobs individually. A successful run does not turn `SKIPPED` into
    `PASS`.
11. **Obtain authority for the exact effect.** Repository preparation and green
    evidence do not authorize merge or another provider mutation. For release or
    publication effects, follow the specialized runbook instead.
12. **Perform only the authorized effect.** If the Work Item must survive merge,
    keep provider metadata and the prospective merge message free of automatic
    closing semantics; the
    [source-release runbook](publish-source-only-release.md) records the known
    GitHub parsing precaution.
13. **Read back integrated and provider state.** PR-head verification and the
    integrated-main revision are separate observations. Read the exact protected
    revision, changed paths, provider jobs and lifecycle state.
14. **Re-bind the subject and reconcile.** A new SHA alone does not invalidate
    general evidence. Prove the relevant subject unchanged before reuse; when it
    changed materially, replay only affected evidence. **Final semantic review
    evidence is the explicit exception:** Decision 0067 binds it to the exact
    head, so any new candidate head invalidates the prior final review cut even
    when the broader subject is otherwise unchanged. Other evidence may still be
    reused after subject-equivalence is proven. Re-read navigation under
    [Decision 0024](../decisions/0024-separate-stable-navigation-from-volatile-state.md).
15. **Record the micro-retrospective.** Before closure, answer briefly: what was
    expected; what actually happened; what surprised us or was detected late;
    which existing control worked or failed to activate; and whether one concrete
    improvement is worth considering later. The close-out comment is normally
    sufficient. A finding is not automatic implementation admission; route a
    concrete follow-up through step 3 rather than starting it automatically.
16. **Close the Work Item last.** Close only after integrated/provider read-back,
    subject re-binding, reconciliation and the micro-retrospective succeed; then
    record the next owner decision without starting it automatically.

## Supplied agent reviews

When agent reviews are supplied for Gnostoa work, whether the owner forwards
them or we commission them, record each reviewer before reporting the reviews
as handled. Use the owning PR or Work Item review record and keep the existing
capture, language and authorized-effect limits of this runbook. If publication
is unavailable or not authorized, retain the pending record in the active
change record rather than an ephemeral session note, state that limit
explicitly and publish it once the effect is authorized. Link an existing
sufficient record instead of duplicating it. A compact table normally suffices,
but a combined verdict must not replace individual dispositions.

For each supplied review, retain:

- Source or supplied attribution, reviewed subject/head and the reviewer's
  reported verification environment and date. Mark missing or unverified
  attribution, subject binding or environment explicitly; a supplied model name
  is not authenticated reviewer identity.
- Reported findings, including explicit no-findings reports, limitations and
  conditional recommendations. Do not infer "no findings" from silence.
- The reviewer's own overall recommendation, or that none was supplied.
- Our disposition of each finding and the review overall, with rationale,
  evidence links, resolution subject/head and remaining uncertainty. Distinguish
  addressed, accepted for follow-up, deferred, not adopted and unresolved items;
  agreement alone does not mean implementation is complete.

Shared findings may use one evidence link while retaining each reviewer's
attribution. Keep original recommendations separate from our conclusions.
Record corrections or superseding reviews explicitly rather than silently
rewriting history or treating an older-head review as review of a new head.
Distinguish reviewer-reported execution from our reproduction and from evidence
we have not inspected.

Agent recommendations do not supply human semantic acceptance, merge authority
or implementation admission. Apply the
[explicit-admission requirement](../requirements/retrospective-findings-require-explicit-admission.md)
to new work. Record capture and source validation are review practices; neither
establishes mandatory software enforcement or prevents future omissions.


### Staged external review collection

This subsection is operative only when read from a protected-main revision that
already contains Decision 0087. On an unintegrated review branch it is candidate
guidance under falsification, not governing repository state.

For Gnostoa-self external automated reviewers, apply
[Decision 0087](../decisions/0087-separate-reviewer-capability-state-from-staged-review-orchestration.md)
and the dated
[reviewer capability baseline](../assessments/reviewer-capability-quota-orchestration-baseline.md).
Keep provider capability, current account/workspace availability, exact-subject
eligibility and completed review evidence separate. In registry observations,
`status` preserves the provider event while mandatory `route_state` carries
the terminal/nonterminal orchestration state; never infer terminality from a
descriptive status label. A `COMPLETED` route state records provider-route
completion only; it is not semantic review acceptance unless separate
subject-bound exact-head evidence satisfies the existing review-assurance path.

Historical observations are comparable only when provider, scope, applicable
subject and a **non-null matching non-secret `scope_identity`** agree and an
exact source/provider `event_at` is attributable. `observed_at` is
acquisition provenance, not event ordering. A subject-scoped observation matches
the current candidate only when its retained `head_commit` exactly equals the
current head; null/unknown identity or head is historical-only and requires
revalidation. A newer `FAILED` or `TIMED_OUT` attempt also stales an older
cached `AVAILABLE` state for automatic dispatch until availability is
revalidated. Historical committed observations have no implicit TTL and never
authorize automatic scarce-review dispatch by themselves. For automatic
dispatch, require a provider `current_readback` whose `cut_id` equals the
active planning cut and whose `planning_subject` equals the exact target
PR/head. Keep its fact-level `subject` faithful to the declared scope:
account scope uses `subject=null`, repository scope remains repository-scoped,
and subject scope uses the exact subject. Require same-cut
`availability_state=AVAILABLE` and `eligibility_state=ELIGIBLE`, with a
current non-secret `scope_identity` where required and an actual provider
current-readback source. An adapter may combine separately acquired
account/workspace availability and exact-subject eligibility only when both were
acquired in the same cut; it must not rewrite the fact scope to manufacture an
exact-subject record. Historical registry observations cannot be promoted into
this shape; missing, incomplete, or ambiguous availability-plus-eligibility
proof is `REVALIDATION_REQUIRED`/manual disposition.

Use one isolated invocation per reviewer through the provider-specific channel
retained in the capability registry. Use the retained stable `route_id` for the
primary/alternative manual surface and the distinct non-null
`ready_activation.route_id` for attributable Ready auto-review in current
read-back, activation deduplication, protected qualification binding and
reconciliation; never reconstruct or alias route identity from provider name or
command text. Historical observations with `route_id=null` cannot suppress a
current activation. For comment-driven reviewers, use one
top-level trigger comment per reviewer and do not batch several reviewer
commands into one comment. For UI, API, GitHub-app and interactive-agent routes,
use their recorded channel instead of manufacturing a comment command. The
typed `dispatch_kind` is authoritative for payload meaning:
`comment_command` may carry comment syntax, `provider_action` carries a
UI/API action, `configuration_only` is not an invocation, and
`interactive_manual`/`unknown` are non-automatic. Treat a generic comment
command as manual-only for future automation until repository-specific command
ownership/collision behavior is verified. Treat `dispatch_safety` as a closed registry vocabulary: reject an unknown
value instead of inferring provider-specific semantics. Treat any
`dispatch_safety: manual_only_until_*` route as ineligible for automatic
dispatch regardless of `instruction_mode`.

Follow only the retained typed recipe and enforce its
`dispatch_kind_constraints`: comment commands require only a command,
provider actions require only an action, configuration-only routes are never
invocations, and interactive/unknown routes are non-automatic. For templates,
normalize CRLF/CR to LF, allow only HT/LF controls, reject reserved placeholder
literals, enforce the **4096-byte UTF-8 maximum**, and perform one
non-recursive render pass. Invalid input is `MANUAL_ONLY_NO_DISPATCH`.
Optional-template empty instructions reduce to command-only;
required-template empty instructions are invalid, and isolated instructions may
not contain another retained comment-trigger command. Never invent provider
syntax or instruction prose. The current Sourcery route uses a standalone
comment containing only `@sourcery-ai review`.

Collect review in stages rather than spending every configured reviewer on each
intermediate head:

1. while the PR is unstable, run deterministic preflight, applicable CI and
   self-review first;
2. use only selected, currently available early-review routes whose expected
   value justifies reviewing a Draft or intermediate candidate;
3. explicitly seal the exact head before final collection;
4. before recommending Ready, **PRE_READY_RECONCILE** requires one
   typed provider/head activation scan for every provider whose Ready path may
   auto-activate (automatic/configurable/unknown or otherwise not proven
   non-automatic), plus any provider already used for early review on the exact
   head. A negative result is valid only when the scan is
   `completeness=COMPLETE` and `activation_state=ABSENT` after inspecting all
   provider-native review/request/summary/status/check surfaces available to the
   adapter. Explicit exact-head SHA binding in a provider-authored mutable
   summary/footer/source link counts as provider/head activity even when the
   route identity is unknown; timestamps or generic green status alone do not.
   `INCOMPLETE`/`AMBIGUOUS` is `REVALIDATION_REQUIRED`. If same-head
   activity is `PRESENT` and Ready automatic activation cannot be excluded,
   require current `ready_activation_state` and
   `provider_head_deduplication_state`; enabled/unknown Ready auto-activation
   without established provider-level deduplication blocks Ready and requires
   manual disposition. Immediately before the Ready effect, refresh the exact
   head/lifecycle state and all PRE_READY scans; any newer provider activity or
   competing orchestration state invalidates the cut;
5. only after PRE_READY_RECONCILE is safe, transition to Ready and retain
   an attributable **Ready-transition receipt** bound to the exact head and
   PRE_READY cut. Mint a **new POST_READY cut** with a new `cut_id` and
   `as_of >= transitioned_at`; never reuse a PRE_READY cut to prove
   post-transition ordering. Under that POST_READY cut, read current-head
   provider request/review state before any manual trigger. For each selected
   reviewer use exactly one provider-level activation path: if Ready
   auto-started or completed a current-head request/review, wait/reconcile it and
   suppress every sibling manual route; otherwise consider exactly one manual
   route only after dispatch-safety and current eligibility are established.
   Provider/head activity may suppress sibling activation even when its route is
   unknown; route-specific reconciliation remains `REVALIDATION_REQUIRED`
   until attribution is complete. When multiple same-head attempts exist and
   their provider/request identity or ordering is ambiguous, use
   `REVALIDATION_REQUIRED` instead of guessing;
6. if current provider eligibility cannot be reacquired for an automatic
   dispatch decision, use `REVALIDATION_REQUIRED` and do not spend quota
   speculatively; retained dated registry observations are historical hints, not
   sufficient current provider truth;
7. if a selected route remains `REVALIDATION_REQUIRED`, use
   `DESELECTED_OPTIONAL` only when protected assurance already reports `PASS` or
   an authority-produced route binding marks that stable `route_id`
   `optional_for_current_assurance=true`; if a route is claimed to advance
   non-PASS assurance but its binding is missing/ambiguous, use
   `QUALIFICATION_ROUTE_BINDING_REQUIRED` instead of guessing;
8. treat `SKIPPED`, `QUOTA_EXHAUSTED`, `CREDIT_REQUIRED`,
   `UNAVAILABLE`, `UNSUPPORTED_FOR_SUBJECT`, `FAILED`, `TIMED_OUT` and
   `DESELECTED_OPTIONAL` as truthful scheduling outcomes, never as clean
   reviews. The admitted read-only planner performs **zero automatic retries**:
   after same-cut revalidation, a policy-eligible assurance-advancing
   failed/timed-out route becomes `MANUAL_ESCALATION_REQUIRED`; any later
   activation is a separately authorized provider-write effect, and only a new
   protected R2A result decides whether quorum/assurance advanced;
9. batch related repair findings before creating another final candidate where
   practical;
10. before any final-review repair that will change the exact head, invalidate
   the complete prior final review cut and convert the provider PR back to Draft;
   `final_review_cut.head_commit` must equal the current candidate head,
   otherwise the cut is `INVALIDATED_HEAD_CHANGED` and no old-head review,
   qualified-domain result or route activation survives;
   for **final semantic review evidence this exact-head rule supersedes the
   general subject-rebinding reuse rule in step 14**; batch the mutation, rerun
   deterministic/CI evidence, reseal the new exact candidate, then return to
   Ready, collect fresh exact-head evidence and recompute protected R2A
   assurance; optional old-head reviews remain historical and do not count in
   the new cut;
11. keep a Ready PR Ready only for reconciliation/disposition that does not change
   the exact candidate head; architecture, provider abstractions, broad
   production behavior, scope/classification expansion or another implementation
   phase also reopens the broader development state.

Configured-provider count is not review quorum. The effective review policy,
R2A result and Issue #10 qualification/independence semantics remain
authoritative. The planner must pass protected `outcome`/`reason`,
`minimum_distinct_domains`, `qualified_domain_ids`, required capabilities
and qualification revision through unchanged. Any route claimed to advance
assurance must have an authority-produced binding from stable `route_id` to
reviewer/source identity and independence domain; the planner never invents that
mapping. Missing/ambiguous binding is
`QUALIFICATION_ROUTE_BINDING_REQUIRED`. Convergence or owner-decision
readiness may be recommended only when exact-head protected assurance is
complete and `PASS`; an R2A `INCOMPLETE / QUORUM_UNMET` result remains
blocking regardless of provider count.

## Verification

Use the repository's current policy and container routes rather than copying a
fixed suite here. Record exact-candidate and integrated-main results separately,
including public-surface digest, executable/runtime-subject equality and X3 when
applicable. Provider command success is not authoritative read-back.

## Recovery

On subject drift, a failed required job, an unexpected provider effect or scope
expansion, stop before the next effect. Read back the authoritative state,
reclassify or re-bind as applicable, and return to the owner rather than silently
retargeting the slice.

## Fresh-agent falsification

Run the retrospective's fresh-agent test on the first naturally occurring
eligible ordinary slice. The agent should reconstruct this route from repository
knowledge using only task-specific input. This tests discoverability and process
reconstruction, not semantic autonomy or adopter transfer.
