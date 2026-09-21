---
type: Source
title: Reviewer capability, quota and orchestration baseline
description: Dated Gnostoa-self baseline separating reviewer capabilities, account availability, exact-head review evidence and orchestration policy, with a staged review-collection workflow for scarce external reviewers.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-21T22:29:45Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: l0-baseline
    resource: ./15-l0-lite-observed-workflow-baseline.md
    title: WI-DET-01 L0-lite observed workflow baseline
  - id: useful-l1
    resource: ../decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
  - id: reviewer-registry
    resource: ./reviewer-provider-capabilities.json
    title: Reviewer provider capability registry snapshot
  - id: sourcery-auto-review-cap
    resource: https://github.com/ktogias/gnostoa/pull/272#issuecomment-5711489476
    title: Sourcery five-auto-review observation
  - id: sourcery-standalone-recovery
    resource: https://github.com/ktogias/gnostoa/pull/272#issuecomment-5714172963
    title: Sourcery standalone-command exact-head recovery
  - id: sourcery-rolling-budget
    resource: https://github.com/ktogias/gnostoa/pull/285#issuecomment-5757528323
    title: Sourcery rolling diff-character budget observation
  - id: cubic-quota
    resource: https://github.com/ktogias/gnostoa/pull/272#issuecomment-5715456960
    title: Cubic 40,037 / 40,000 reviewed-line quota observation
  - id: cubic-quota-later
    resource: https://github.com/ktogias/gnostoa/pull/285#issuecomment-5744117247
    title: Cubic later 60,991 / 60,000 reviewed-line quota observation
  - id: bito-size-limit
    resource: https://github.com/ktogias/gnostoa/pull/285#issuecomment-5763817612
    title: Bito trial fair-usage PR-size observation
  - id: turingmind-credits
    resource: https://github.com/ktogias/gnostoa/pull/285#issuecomment-5758253881
    title: TuringMind exhausted review-credit observation
  - id: deepsource-autofix-incident
    resource: https://github.com/ktogias/gnostoa/pull/285#issuecomment-5761254096
    title: DeepSource autofix rejection and revert
  - id: coderabbit-draft-dogfood
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765178931
    title: CodeRabbit natural Draft skip on orchestration baseline
  - id: deepsource-draft-dogfood
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765181973
    title: DeepSource Draft static-analysis versus on-demand AI review
  - id: coderabbit-trigger
    resource: https://kb.coderabbit.ai/articles/1442026547-troubleshoot-why-coderabbit-reviews-might-not-trigger
    title: CodeRabbit review triggering and rate-limit troubleshooting
  - id: coderabbit-faq
    resource: https://www.coderabbit.ai/faq
    title: CodeRabbit review allowance FAQ
  - id: coderabbit-pricing
    resource: https://www.coderabbit.ai/pricing
    title: CodeRabbit plan review allowances and usage-based overage
  - id: qodo-workflow
    resource: https://www.qodo.ai/blog/configuring-qodo-code-review-for-your-teams-workflows/
    title: Qodo review workflow configuration
  - id: qodo-agentic-review-command
    resource: https://docs.qodo.ai/qodo-documentation/code-review/get-started/configuration-overview/configuration-file
    title: Qodo GitHub App agentic review command configuration
  - id: qodo-ready-auto
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5766935150
    title: Qodo automatic Ready-transition review observation
  - id: codeant-ready-auto
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765816608
    title: CodeAnt automatic Ready-transition incremental review observation
  - id: qodo-pricing
    resource: https://www.qodo.ai/pricing/
    title: Qodo pooled review credits and overage controls
  - id: qodo-current-v2-config
    resource: https://docs.qodo.ai/qodo-documentation/code-review/get-started/configuration-overview/configuration-file
    title: Qodo v2 Git review command configuration
  - id: bito-draft-filter
    resource: https://docs.bito.ai/ai-code-reviews-in-git/excluding-files-folders-or-branches-with-filters
    title: Bito draft and branch review filters
  - id: bito-test-mode
    resource: https://docs.bito.ai/ai-code-reviews-in-git/try-ai-code-reviews-using-test-mode
    title: Bito test mode and full integration
  - id: cubic-pricing
    resource: https://www.cubic.dev/pricing-plans
    title: Cubic review usage and pricing
  - id: codacy-ai
    resource: https://docs.codacy.com/codacy-ai/codacy-ai/
    title: Codacy AI Reviewer
  - id: codacy-drafts
    resource: https://docs.codacy.com/release-notes/cloud/cloud-2026-05/
    title: Codacy draft PR AI review control
  - id: gitar-pricing
    resource: https://gitar.ai/pricing
    title: Gitar plans and interactive PR review capability
x-project-knowledge:
  id: kit.assessment.reviewer-capability-quota-orchestration-baseline
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
    - kind: references
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# Reviewer capability, quota and orchestration baseline

## Purpose and boundary

Gnostoa now has enough real multi-reviewer history to distinguish four concepts
that were previously mixed together:

1. **provider capability** — what a reviewer can generally do;
2. **workspace/account availability** — whether this installation can use that
   capability now;
3. **subject eligibility** — whether the current PR state, size, head and
   trigger form are acceptable to that reviewer; and
4. **review evidence** — what a completed reviewer actually reported about one
   exact subject.

Only the fourth item can become review evidence. The first three are scheduling
inputs. None of them establish reviewer qualification, independence, semantic
quorum, accountable-owner approval or merge authority.

This assessment is a dated operational baseline for Gnostoa-self. It does not
create a generic public reviewer schema, a new review semantics engine, a
reviewer identity service, provider-write authority, or a requirement that every
configured reviewer must complete a review.

## Why the distinction is necessary

The same provider can be generally capable but currently unavailable. Gnostoa
has already observed all of the following:

- Sourcery exhausted a rolling account review budget and supplied an explicit
  retry-after time;
- Cubic exhausted a monthly reviewed-line allowance and supplied a later resume
  date;
- Bito could run as a reviewer in general but refused the large PR #285 under
  the trial fair-usage size boundary;
- TuringMind was installed but could not review because the account had no PR
  review credits;
- a provider can be clean on a prior head while having no current exact-head
  result; and
- a provider can emit an analyzer/autofix mutation that must be treated as a new
  untrusted candidate rather than as review evidence.

Encoding any of those cases as a permanent provider trait would be wrong. The
machine-readable snapshot therefore keeps dated observations separate from
capabilities and requires fresh read-back before scarce scheduling decisions.

## Capability model

The companion
[`reviewer-provider-capabilities.json`](reviewer-provider-capabilities.json)
is the first implementation-private registry snapshot. It intentionally has no
standalone lifecycle/promotion flag: the protected repository revision and
Decision 0087 determine whether a registry revision is operative, and a
standalone JSON status token must not manufacture review or integration
authority. Version `v0.10` exposes one planner-facing shape rather than
provider-specific field names.

Every provider has the same typed `capabilities.manual_trigger` contract:
`channel`, `dispatch_kind`, `command`, `action`,
`configuration_path`, `isolation`, `instruction_mode`,
`instruction_template`, `dispatch_safety` and `alternatives`.
Alternatives use the same normalized dispatch payload plus a `purpose`.
`dispatch_kind` prevents unlike surfaces from being conflated:
`comment_command` carries actual comment syntax, `provider_action` carries a
UI/API action, `configuration_only` carries a repository configuration path
and is not an invocation, while `interactive_manual` and `unknown` remain
non-automatic. A planner/dispatcher must never reinterpret a UI label,
configuration path or sentinel as GitHub comment syntax.

Every volatile provider fact belongs in one `observations[]` array. Each
observation has the same fields and an explicit `scope` of `account`,
`repository` or `subject`; absent values are `null`, not alternate
top-level keys. Version `v0.10` separates the operational dimensions inside every
observation:

- `status` records the observed provider event or outcome and may therefore be
  descriptive, such as `FORMAL_REVIEW_SUBMITTED_ON_DRAFT`;
- `route_state` is mandatory and is the only field used for orchestration
  terminality. It must belong to `terminal_route_states` or
  `nonterminal_route_states`. A `COMPLETED` route state means only that the
  provider route/attempt completed; it does not establish current-head semantic
  review evidence, reviewer qualification, quorum, approval or merge authority;
- `scope_identity` is a non-sensitive stable identity for the account/workspace,
  repository or change-request scope when that identity is actually known. A
  null identity is historical-only and cannot participate in machine precedence
  or authorize automatic dispatch;
- `event_at` is attributable provider/source event time, while
  `observed_at` records when Gnostoa acquired/retained the observation.
  Historical ordering uses exact `event_at`, never record time. For retained
  formal GitHub reviews, `event_at` is the cited review's exact
  `submitted_at` timestamp when available.

The top-level `observation_status_vocabulary` remains a closed superset of all
route-state labels plus descriptive provider-event statuses. A planner must
never infer terminality directly from a descriptive `status`. Repository-scope
descriptive events are configuration evidence rather than current route
observations and therefore carry `route_state: UNKNOWN`; they cannot satisfy
route completion, availability or quorum without a separately bound exact
subject observation.

For historical interpretation, observations are comparable only when provider,
scope, applicable subject and a **non-null matching `scope_identity`** agree
and an exact RFC3339 `event_at` is attributable. `observed_at` is acquisition
provenance and never substitutes for event ordering. A `retry_after` is an
advisory forecast and cannot override a later attributable event. Null scope
identity, missing/coarse event time, ties or conflicts require revalidation
instead of guessed precedence. A newer `FAILED` or `TIMED_OUT` attempt also
stales older cached `AVAILABLE` for automatic dispatch without asserting
`UNAVAILABLE`.

Version `v0.10` keeps freshness deterministic by refusing to invent a TTL:
retained registry observations are historical scheduling hints, not sufficient
current provider truth for automatic dispatch. Before a scarce route is
automatically dispatched, eligibility and the current non-sensitive scope identity
must be reacquired in the current orchestration observation cut. If current
read-back is unavailable or ambiguous, the route becomes
`REVALIDATION_REQUIRED` and automatic dispatch is prohibited.

The normalized observation subject is `{repository, change_request,
head_commit}`. For `scope: subject`, a non-null `head_commit` matches only
that exact candidate. A null exact head is historical-only and forces
revalidation; it can never match the current candidate. Repository-scoped
observations use the same subject shape with `change_request=null` and
`head_commit=null`, while account-scoped observations use `subject=null`.
This prevents a completed review on one PR head from becoming a completion
signal for a successor head.

Provider entries still retain:

- reviewer class: semantic reviewer, hybrid reviewer, analyzer/mutation lane;
- draft and Ready behavior;
- automatic/incremental review behavior where documented;
- quota model, but never an invented "unlimited" state;
- primary vendor documentation and repository evidence.

The registry deliberately uses values such as `unknown`,
`plan_dependent`, `vendor_claimed_unlimited` or dated runtime status. The
absence of a limit observation is not evidence of unlimited capacity.

### Trigger isolation rule

For Gnostoa-self, use **one isolated invocation per reviewer** through the
provider-specific channel retained in the registry.

For reviewers whose manual trigger is a GitHub comment, use one top-level
trigger comment for that reviewer and do not batch several reviewer commands
into one comment. A reviewer whose documented or observed command parser
expects a dedicated trigger can otherwise miss the invocation, while a parser
that treats the remainder as instructions can behave differently from one that
expects exact command text.

For UI, API, GitHub-app and interactive-agent routes, use the provider-specific
trigger surface from the registry rather than manufacturing a comment command.

A documented generic comment command such as Bito's bare `/review` is not
automatically safe for future dispatch in a repository with several installed
review apps. Until repository-specific command ownership/collision behavior is
verified, retain that route as manually invokable but not safely isolated for
automatic dispatch.

Provider-specific instruction behavior remains data:

- Sourcery receives a dedicated comment whose complete body is
  `@sourcery-ai review`. Gnostoa has observed that the standalone command
  restores review after the automatic-review counter is exhausted.
- CodeRabbit, Qodo, CodeAnt and Cubic have accepted exact-head review requests
  carrying a bounded falsification charter in Gnostoa history.
- Unknown parsers receive the smallest documented trigger form rather than an
  invented instruction syntax.

This rule reduces trigger ambiguity and also leaves each invocation separately
attributable in the provider history.

## Deterministic instruction recipes

Instruction support and planner dispatch are separate facts. A provider may
accept extra prose in practice without giving the planner authority to invent
that prose or its syntax. Typed `dispatch_kind` also means `command` is
executable comment syntax only for `comment_command`; UI actions,
configuration paths and interactive/manual routes use their own fields.

The registry therefore retains an explicit `instruction_mode` and optional
`instruction_template`. CodeAnt's observed comment shape is represented as
`{command}\n\n{instructions}`, where `instructions` is bounded,
caller-supplied text rather than provider folklore. Version `v0.10` makes the
bound deterministic: normalize CRLF/CR to LF, allow HT/LF as the only control
characters, reject other C0/C1 controls and the reserved caller literals
`{command}` / `{instructions}`, and cap the normalized UTF-8 payload at
**4096 bytes**. Rendering is one non-recursive substitution pass. Invalid input
produces `MANUAL_ONLY_NO_DISPATCH`, never a partial/fallback comment.

For an optional template, empty instructions reduce to command-only; for a
required template, empty instructions are invalid. When isolation is required
or recommended, instructions may not contain another retained comment-trigger
command. Non-comment surfaces keep their typed action/configuration/manual
representation. The registry's machine-readable `dispatch_kind_constraints`
also defines required/non-null versus required-null fields for every typed
surface, so a UI action or configuration path cannot accidentally satisfy the
`comment_command` shape.

## Observed provider classes

### CodeRabbit

CodeRabbit documents that draft PR actions are not normally reviewed and
documents manual `@coderabbitai review` and
`@coderabbitai full review` commands. Current pricing publishes hourly PR
review allowances of **5 / 8 / 10 / 12 reviews per developer** for
Essentials / Team / Advanced / Enterprise, subject to fair use; eligible
overage can use usage-based billing with a configurable monthly spending cap.
Gnostoa therefore treats it as a scarce-but-repeatable reviewer: useful for
selected early reviews and for an exact-head final pass, but not something to
spend automatically on every intermediate commit.

### Sourcery

The strongest Gnostoa-specific observation is explicit: on PR #272 Sourcery
reported that it **auto-reviews a PR five times**, withdrew approval after that
automatic limit, and instructed the owner to comment
`@sourcery-ai review` for a fresh review. A later standalone command produced
fresh exact-head approval.

Separately, PR #285 observed a rolling account budget of **2,500,000 diff
characters over seven days**. At `2026-09-21T08:23:00Z` Sourcery said another
review could be requested in **13h03m**, retained as a
`2026-09-21T21:26:00Z` retry prediction. A successful formal review was then
observed at `2026-09-21T18:55:52Z`, proving historically that review capacity
was usable by that later event. However, the retained account observations have
`scope_identity=null`, so v0.10 deliberately forbids machine supersession or
current dispatch authorization from those records alone; current scheduling
requires fresh account/provider read-back in the planning cut. The
automatic-per-PR limit and rolling account availability remain separate quota
dimensions.

### Qodo

Qodo's July 2026 workflow documentation states that draft PR auto-review is off
by default but configurable. Current Qodo 2.x GitHub App configuration documents
`/agentic_review` as the manual review command; the older open-source PR-Agent
surface documents legacy `/review`. Gnostoa has directly observed automatic
review starting on a Ready transition, but has not yet established
repository-specific ownership/collision behavior for manual
`/agentic_review`, so the registry marks that route
`manual_only_until_repository_validation`. `instruction_mode: none` describes
the command's instruction syntax only; it does not authorize automatic
dispatch. Current pricing is usage-based rather than
request-rate-based: reviews consume a **pooled monthly team credit pack**
according to size/complexity, with a customer-set overage cap. Thus “no rate
limit” must not be normalized to “no quota.”

### CodeAnt

Gnostoa has repeatedly obtained exact-head CodeAnt results from a dedicated
`@codeant-ai: review` comment followed by instructions. Current public pricing
does not supply enough evidence to encode "no quota", so the registry keeps its
quota state plan-dependent/unknown instead of pretending it is free.

### Cubic

Cubic's current pricing distinguishes a free PR-count allowance from
reviewed-line plans; reviewed-line usage resets with the billing period,
incremental reviews count newly reviewed lines, and manual reruns count again.
Gnostoa directly observed quota refusal at 40,037/40,000 reviewed lines and later
at a higher account allowance. The later provider message supplied only the
resume **date** `2026-10-15`, not an attributable instant, so v0.10 retains that
coarse value in observation details and keeps normalized `retry_after=null`.
Current availability must still be reacquired before dispatch.

### Bito

Bito defaults to excluding draft PRs from automatic review but permits manual
`/review`; the draft behavior is configurable. Test mode documents ten
reviews, while full Git integration is advertised as unlimited reviews.
Gnostoa's current trial installation also rejected PR #285 because the PR
exceeded its fair-usage size limit. That refusal is a **subject/account-mode
eligibility state**, not evidence that Bito is permanently unavailable.

### Codacy AI Reviewer

Codacy's May 2026 release notes state that its reviewer no longer runs
automatically on draft PRs; draft review can still be triggered manually from
the summary. Current documentation exposes the `Run Reviewer` UI/public API
and repository instructions at `.codacy/instructions/review.md`. This is a
different trigger surface from comment-driven bots and should be represented as
such instead of emulating a GitHub comment command.

### Gitar

Gitar's current plans advertise customizable reviews and an interactive agent
on PRs, but the inspected pricing source does not publish a numeric per-review
quota. Gnostoa therefore records the capability and leaves numeric quota
unknown.

### TuringMind

PR #285 provides a direct account observation: review was skipped because the
account had no review credits, and the bot explicitly said the skipped review
was not charged. This is best represented as `CREDIT_REQUIRED`, not
`QUOTA_EXHAUSTED_FOREVER` and not an adverse review result.

### DeepSource

DeepSource is retained in a separate analyzer/mutation lane. The #285 autofix
incident demonstrated that an analyzer-generated mutation can corrupt syntax and
contracts. Any autofix therefore creates a new candidate requiring normal
verification and review. Analyzer availability must not be counted as semantic
review convergence.

## Draft automation is not review evidence

PR #297 supplied immediate natural dogfood of the distinction this baseline is
trying to preserve. Without any manual reviewer trigger:

- CodeRabbit posted an explicit Draft skip and stated that Draft auto-review is
  disabled by default for this repository/configuration;
- DeepSource ran static analysis on the Draft but stated that its AI Review is
  on demand and requires `@deepsourcebot review`;
- Sourcery, under the current repository configuration, submitted a formal
  `COMMENTED` review while the PR was still Draft and found one actionable
  trigger-channel defect;
- Gitar automatically posted a semantic review result as an issue comment on
  the Draft, not as a formal GitHub `PullRequestReview`;
- Codacy reported that its first AI Reviewer review was requested successfully
  on the Draft, but the request/status message alone does not establish a
  completed review result;
- provider-generated guides or summaries can also appear on a Draft without
  themselves being a semantic review.

Therefore provider activity must be classified by its actual result surface.
Bot comments, summaries, PR-body edits, analyzer runs and review requests are
not automatically completed review evidence; conversely, a Draft state does not
prove that every configured reviewer will abstain. The orchestration layer must
identify the provider's actual review-result surface and current repository
configuration before it treats an event as `COMPLETED`.

## Exact-head binding inside the capability registry

The review-assurance layer already binds semantic review evidence to an exact
subject. The planner registry must not weaken that property indirectly.

Subject-scoped operational observations such as `COMPLETED` therefore carry
the exact `head_commit` they describe. For example, Codacy reviews retained from distinct Ready cycles of PR #297 are
stored as separate subject-scoped observations for the exact heads they actually
reviewed; the older `716687d…`, later `562fc9a…`, and later `e304af4…`
records are not interchangeable. Sourcery and Gitar records follow the same
exact-subject rule. A provider capability/Ready-activation evidence entry never
silently substitutes for a differently bound review observation.

When the exact historical head is not retained, `head_commit=null` is
fail-safe: the observation remains useful historical context but the planner
must reacquire current availability/eligibility instead of treating it as a
match.

## Ready-state final-review dogfood

The first Ready transition of PR #297 exposed two additional contract defects
before integration:

- Codacy identified that volatile observations still used different
  provider-level keys and would force provider-specific planner parsing. The
  registry was normalized to one `observations[]` shape and one common
  `manual_trigger` contract.
- Sourcery identified that the initial bounded-repair wording could reuse
  old-head final-review evidence after a candidate mutation. The corrected rule
  invalidates the whole final review cut whenever the exact head changes; every
  domain required for final policy/quorum must provide evidence for the new
  head.

Both findings are examples of the intended staged workflow. The first
head-changing repair was initially left Ready; natural dogfood showed that this
could immediately spend auto-review quota before the new CI seal. The corrected
provider projection therefore returns to Draft for every head-changing final
repair, even when the internal repair is bounded. After CI reseals the new
candidate, Ready starts a completely new exact-head final evidence cut. No
old-head recommendation is silently promoted to the successor head.

## Review collection state machine

The efficient Gnostoa-self operating loop should use internal states richer than
GitHub's single Draft/Ready boolean.

```text
DRAFT_BUILD
  -> deterministic preflight
  -> CI / focused verification
  -> self-review
  -> EARLY_REVIEW
       only selected reviewers that are draft-capable/currently available
       and worth spending on the unstable candidate
  -> repair batch if needed
  -> repeat preflight/CI/self-review
  -> SEAL_EXACT_HEAD
  -> READY_FINAL_COLLECTION
       transition to Ready
       reacquire current-head provider request/review state
       for each selected reviewer choose exactly one activation path:
         auto-started/current request -> wait/reconcile, do not retrigger
         no current request -> consider one safe manual trigger
  -> while selected routes remain:
       terminal route -> retain outcome
       optional + REVALIDATION_REQUIRED -> explicit DESELECTED_OPTIONAL disposition
       required/unknown-required + REVALIDATION_REQUIRED -> remain blocked
  -> reconcile when every route still selected is terminal:
       COMPLETED | SKIPPED | QUOTA_EXHAUSTED | CREDIT_REQUIRED |
       UNAVAILABLE | UNSUPPORTED_FOR_SUBJECT | FAILED | TIMED_OUT |
       DESELECTED_OPTIONAL
  -> reconcile exact-head evidence cut
  -> findings?
       no  -> accountable-owner decision boundary
       yes -> classify repair
```

A final-review finding that requires **any source/head mutation** first
invalidates the complete prior final review cut and projects the PR back to
**Draft before the repair is pushed**. This suppresses Ready-only automatic
reviewers while the successor candidate is unstable and prevents quota from
being spent on pre-CI heads. Batch the repair, rerun deterministic/CI checks,
seal the new exact head, then transition to Ready and obtain fresh evidence from
every review domain required by the effective review policy/qualification
result. Optional old-head reviews remain historical evidence only and are
excluded from the new final cut unless explicitly re-run on the new head.

A Ready PR may stay Ready only for reconciliation/disposition work that does
**not** change the exact candidate head.

A material finding additionally reopens the broader development phase when it
changes architecture, scope or implementation class, for example:

- architecture or abstraction changes;
- significant new production behavior;
- multiple repair commits that make the previous review surface misleading;
- scope/classification expansion; or
- a new implementation phase rather than a bounded correction.

The scheduler state is therefore authoritative for orchestration; GitHub Draft
is one provider projection of that state, not the complete lifecycle.

## Cheap feedback early, scarce diversity late

The scheduling objective is not "run every bot as often as possible." It is:

> spend cheap/deterministic feedback while the candidate is unstable, and spend
> scarce independent review diversity on sealed heads.

This follows directly from Gnostoa's L0 evidence. PR #257 had 28 distinct
reviewed heads and PR #272 had 17; most earlier reviewed heads were later
superseded. The baseline does not claim that every supersession was avoidable,
but it proves that repeated exact-head review collection is a meaningful source
of churn and should be scheduled deliberately.

The default policy should therefore be:

1. deterministic normalization and focused tests before candidate creation;
2. authoritative CI before expensive final collection;
3. self-review on every meaningful repair batch;
4. early external review only from selected available routes whose expected
   unique yield justifies the cost;
5. preserve quota-limited, Ready-only or full-review routes for the sealed
   candidate;
6. after the Ready transition, **read provider state back before any manual
   trigger**; if Ready already started or completed a current-head review for a
   selected route, reconcile that request and do not trigger it again;
7. manually invoke only selected routes that still have no current-head
   activation and whose dispatch-safety/current-eligibility requirements are
   satisfied; if eligibility cannot be reacquired, surface
   `REVALIDATION_REQUIRED` rather than spending quota speculatively;
8. when current read-back cannot revalidate a **policy-established optional**
   selected route, explicitly move it to `DESELECTED_OPTIONAL` with a retained
   reason before reconciliation; this is a scheduling disposition, not review
   evidence;
9. never use `DESELECTED_OPTIONAL` when the route/domain is required or its
   required-domain status is unknown/incomplete; those cases remain blocking;
10. record unavailable optional reviewers truthfully and continue according to
   the effective review policy rather than treating configured-provider count
   as quorum.

The existing Gnostoa review policy still owns quorum. For normal, normative and
critical work it currently requires at least two distinct reviewer domains.
Provider multiplicity alone does not establish those domains.

## Availability is a terminal scheduling result, not a semantic verdict

For one scheduling attempt, these are legitimate terminal availability results:

- `COMPLETED`;
- `SKIPPED`;
- `QUOTA_EXHAUSTED`;
- `CREDIT_REQUIRED`;
- `UNAVAILABLE`;
- `UNSUPPORTED_FOR_SUBJECT`;
- `FAILED`;
- `TIMED_OUT`;
- `DESELECTED_OPTIONAL`.

`DESELECTED_OPTIONAL` is a terminal scheduling disposition only for a route
that protected policy/R2A already identifies as optional. It is never review
evidence, never satisfies a required domain/capability, and is forbidden when
required-domain status is unknown or incomplete.

`FAILED` and `TIMED_OUT` terminate one invocation attempt only. The admitted
read-only planner performs **zero automatic retries**. After same-cut
revalidation, a required or unknown-required route yields
`MANUAL_ESCALATION_REQUIRED`; it remains blocking until an explicitly
authorized provider effect creates a new activation identity and succeeds, or
alternative protected policy/R2A evidence satisfies the required domain. An
optional route may be `DESELECTED_OPTIONAL` only when protected policy/R2A
already proves it optional and policy-sufficient evidence remains. The planner
never invents a retry/backoff interval.

`FAILED` and `TIMED_OUT` never
mean clean review; a required review route/domain remains incomplete until a
later successful exact-head result or other policy-sufficient qualified
evidence exists. Retries must be bounded and must revalidate current subject and
provider state.

These route states answer "what happened to this scheduling attempt?" They do
not answer "is the code clean?"

Accordingly:

- unavailability cannot be normalized into a clean review;
- an optional unavailable provider need not block convergence when effective
  review policy is already satisfied;
- a required qualified domain that is unavailable still leaves review
  requirements incomplete;
- retry-after information can inform scheduling without changing semantic
  review policy.

## Read-only planner boundary

The next implementation should be a **read-only review planner**, not a
dispatcher.

Version `v0.10` makes freshness, activation and final-review identity explicit:

- a planning cut carries `cut_id`, exact RFC3339 `as_of`, and the exact
  candidate subject;
- a provider `current_readback` is a same-cut route-target evaluation, not a
  raw historical observation. Its `planning_subject` must equal the active
  cut's exact PR/head, while its fact-level `subject` remains faithful to the
  declared scope: account scope uses `subject=null`, repository scope remains
  repository-scoped, and subject scope carries the exact subject. The read-back
  separately carries `availability_state` and `eligibility_state`.
  Automatic scarce-review dispatch requires current same-cut
  `availability_state=AVAILABLE` **and** `eligibility_state=ELIGIBLE`, plus
  current non-sensitive `scope_identity` where required and a provider
  current-readback source. An adapter may combine separately acquired
  account/workspace availability and exact-subject eligibility only when both
  were acquired in the same cut; it never rewrites the underlying fact scope.
  Committed historical registry observations cannot satisfy this same-cut
  requirement;
- an observation may retain a non-sensitive `attempt_id`; ambiguous multiple
  same-head attempts without attributable identity/order become
  `REVALIDATION_REQUIRED`, not an inferred duplicate or retry;
- a final-review cut is bound to one exact `head_commit`. Any head change
  invalidates the entire cut as `INVALIDATED_HEAD_CHANGED`; no old-head
  completion may survive into the successor cut;
- protected required-domain `{id,status}` entries are opaque pass-through
  input. The planner preserves them unchanged and blocks readiness when the
  protected input is missing, ambiguous, incomplete or bound to another head.


Inputs:

- current provider-neutral L1 projection and exact subject;
- PR Draft/Ready state;
- exact-head check state;
- existing review-evidence cut and unresolved findings/threads;
- change class and effective review policy;
- the protected R2A/review-policy required-domain result, as opaque input;
- the capability registry;
- freshly reacquired account/subject availability and current non-sensitive scope
  identity where a provider exposes it.

Output:

- current orchestration phase;
- reviewers eligible for early review;
- reviewers reserved for final collection;
- unavailable routes and reasons;
- typed trigger recipe for each eligible route;
- the opaque required-domain statuses supplied by effective review policy/R2A,
  without deriving reviewer independence from provider count;
- an explicit blocker whenever any required domain remains incomplete;
- whether the candidate should remain Draft, become Ready, remain Ready for
  reconciliation-only work, or return to Draft for a head-changing repair;
- the next permitted orchestration action.

The planner must remain advisory and deterministic. It cannot post comments,
change Draft/Ready state, request reviewers, resolve threads, approve, merge or
alter R2A/quorum semantics. It also cannot recommend review convergence or
owner-decision readiness while the protected policy/R2A input reports an
incomplete required domain, even if optional provider routes completed.

Any future dispatcher is a separate effect-capable slice with its own authority
decision, exact provider adapters, stale-state protection, idempotence and
read-back. Decision 0086 deliberately excluded reviewer trigger/wait
orchestration from useful L1; this baseline does not smuggle those writes into
L1.

## Suggested measurements

Prospective review-orchestration measurement should retain at least:

- review requests per candidate generation;
- completed versus unavailable requests by provider/reason;
- unique actionable root causes per completed reviewer;
- overlap between reviewer findings;
- reviewed-head generations per PR;
- fresh-review requests invalidated by later candidate mutation;
- quota/credit refusals and retry delay;
- time from sealed exact head to policy-sufficient review convergence;
- Ready -> Draft reopen count and reason;
- final reviewers triggered but not needed for effective quorum.

These metrics assess scheduling value, not reviewer "quality rankings." A
reviewer with fewer unique findings may still provide useful diversity; a high
finding count may reflect duplicate or low-value noise.

## Disposition

The evidence supports a small next step:

1. retain this assessment and the machine-readable capability snapshot;
2. update the Gnostoa-self delivery runbook with staged review collection and
   isolated reviewer triggers;
3. adopt a Decision that separates capability, availability, evidence and
   orchestration authority;
4. implement the read-only planner as a later bounded #15 slice after this
   normative baseline is reviewed and integrated;
5. do not implement automatic reviewer dispatch in this slice.

This captures the operational learning without creating a new semantic-review
authority or another broad workflow engine.
