---
type: Source
title: WI-DET-01 L0-lite observed workflow baseline
description: Receipt-derived baseline for Issue #15 using real assurance and deterministic-normalization specimens while preserving unknown historical effort and authority boundaries.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-19T15:22:00Z"
sources:
  - id: wi-det-01
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: l0-l5-blueprint
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5706403186
    title: Post-P2b execution blueprint — durable mobile-first L0-L5 ascent
  - id: restoration-exit
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5742408676
    title: Restored protected capability returns to the L0-L5 ascent
  - id: assurance-cost-specimen
    resource: https://github.com/ktogias/gnostoa/pull/257
    title: Materialize integrated R2A B1.6 outer consumer by digest
  - id: assurance-cost-pr-metadata
    resource: "https://api.github.com/repos/ktogias/gnostoa/pulls/257"
    title: PR 257 provider metadata at the observation cut
  - id: assurance-cost-pr-commits
    resource: "https://api.github.com/repos/ktogias/gnostoa/pulls/257/commits?per_page=100"
    title: PR 257 branch commits at the observation cut
  - id: assurance-cost-pr-reviews
    resource: "https://api.github.com/repos/ktogias/gnostoa/pulls/257/reviews?per_page=100"
    title: PR 257 formal reviews at the observation cut
  - id: deterministic-normalization-specimen
    resource: https://github.com/ktogias/gnostoa/issues/262
    title: Align Ruff configured scope with enforced CI coverage
  - id: deterministic-normalization-implementation
    resource: https://github.com/ktogias/gnostoa/pull/272
    title: Make Ruff scope authoritative before candidate sealing
  - id: normalization-pr-metadata
    resource: "https://api.github.com/repos/ktogias/gnostoa/pulls/272"
    title: PR 272 provider metadata at the observation cut
  - id: normalization-pr-commits
    resource: "https://api.github.com/repos/ktogias/gnostoa/pulls/272/commits?per_page=100"
    title: PR 272 branch commits at the observation cut
  - id: normalization-pr-reviews
    resource: "https://api.github.com/repos/ktogias/gnostoa/pulls/272/reviews?per_page=100"
    title: PR 272 formal reviews at the observation cut
  - id: ruff-candidate-churn-rca
    resource: https://github.com/ktogias/gnostoa/issues/262#issuecomment-5696790428
    title: Empirical Ruff RCA — candidate normalization is happening after candidate creation
  - id: review-overlap-disposition
    resource: https://github.com/ktogias/gnostoa/pull/272#issuecomment-5713775569
    title: Fresh-review finding disposition — shell-wrapper bypass
  - id: liveness-wakeup
    resource: https://github.com/ktogias/gnostoa/pull/272#issuecomment-5713992293
    title: Cubic exact-head review follow-up
  - id: retained-provider-receipts
    resource: https://github.com/ktogias/gnostoa/blob/1c82ad3ccc36d6f07579ce0fe6cb6519d0a733d2/knowledge/assessments/15-l0-lite-observed-workflow-baseline-receipts.json
    title: Immutable normalized provider-receipt snapshot for L0-lite measurements
  - id: convergence-receipt
    resource: https://github.com/ktogias/gnostoa/pull/272#issuecomment-5714172963
    title: Final exact-head convergence
x-project-knowledge:
  id: kit.assessment.wi-det-01-l0-lite-observed-workflow-baseline
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: references
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: references
      target: /decisions/0081-make-repository-root-ruff-scope-authoritative-before-candidate-sealing.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# WI-DET-01 L0-lite observed workflow baseline

## Status and boundary

This is the bounded **L0-lite** baseline selected by Issue #15 after the
current-advisory restoration sequence closed. It is evidence-only. It does not
add telemetry infrastructure, a public schema, a controller, a worker, a
provider mutation, paid inference, a new semantic result, or execution
authority.

The observation cut is protected `main`
`e2b29e820117b9780a9168ab8709026b40975105` on 2026-09-19. The retained
receipt snapshot includes the provider branch read-back that observed
`main`, `protected:true`, that exact head, and required checks
`policy`, `fast`, `regression`, and `smoke`. The principal
assurance-cost specimen is PR #257. Issue #262 and PR #272 are the bounded
mechanical-normalization specimen. Decision 0081's post-integration
effectiveness assessment remains a separate parallel evidence lane and is not a
prerequisite for this baseline or the next #15 rung.

Only facts recoverable from durable GitHub/provider receipts are reported as
measurements. Historical owner effort, token/context consumption, monetary cost
and unrecorded waiting are **UNKNOWN** rather than estimated.

### Retained reproducibility snapshot

The numeric provider baseline is reproduced from the immutable normalized
snapshot
[`15-l0-lite-observed-workflow-baseline-receipts.json`](https://github.com/ktogias/gnostoa/blob/1c82ad3ccc36d6f07579ce0fe6cb6519d0a733d2/knowledge/assessments/15-l0-lite-observed-workflow-baseline-receipts.json).
It retains every provider record field used by the published metrics: PR
timestamps and size fields, all 119 selected branch commits with SHA/date/title,
all 147 formal review records with review ID/author/state/submitted time/head,
the exact derivation rules, the selected non-formal comments used for the
overlap/liveness observations, and the exact retained #262 Ruff-RCA comment
body supporting the 49-commit / 7 directly proven Ruff-failing-candidate
measurement. The live GitHub API URLs remain provenance and
audit routes only; they are not the frozen measurement input.

This is a normalized measurement receipt, not a byte-for-byte archive of every
provider response. The claim here is reproducibility of the published L0
metrics and classifications from the retained fields, not preservation of
GitHub's complete historical JSON representation.

## Measurement method

The provider-observable measurements use the retained normalized snapshot as
their frozen input and the live provider as a cross-check:

- PR creation and merge timestamps for wall-clock span;
- formal PR-review timestamps for the first and last recorded review;
- branch commit count as branch churn, not as a count of semantic candidates;
- distinct `commit_id` values in recorded review submissions as **reviewed
  heads**, a bounded proxy for review-generation churn rather than an assertion
  that every head was an official sealed candidate;
- the frozen #262 RCA for directly proven Ruff-failing candidate generations;
- exact durable comments for one reviewer-overlap cluster, one explicit
  liveness wake-up and provider quota observations.

Review-provider multiplicity is descriptive only. It does not establish Issue
#10 qualification, semantic independence or quorum by itself.

## Observed baseline

| Observable | PR #257 assurance-cost specimen | #262 / PR #272 deterministic-normalization specimen | Claim boundary |
|---|---:|---:|---|
| PR open → merge | **20 h 46 m** | **8 h 21 m** | Wall-clock provider span; not active human time |
| Open → first recorded formal review | **31 m 35 s** | **2 h 10 m 54 s** | Provider timestamp interval |
| First → last recorded formal review | **20 h 12 m** | **5 h 28 m 29 s** | Includes reviewer/provider/repair waiting |
| Last recorded formal review → merge | **2 m 30 s** | **42 m 01 s** | Does not imply all semantic work happened in this interval |
| Branch commits | **71** | **48** | Churn only; commits are not candidate generations |
| Recorded review submissions | **92** | **55** | Includes repeat submissions and owner/provider records |
| Distinct heads carrying recorded review submissions | **28** | **17** | Reviewed-head generations, not canonical-seal count |
| Earlier reviewed heads superseded by a later reviewed head | **27** | **16** | Churn lower bound; not all supersession is avoidable |
| External automated reviewer families visible in formal review records | **4** | **4** | Cubic, Sourcery, Qodo and CodeRabbit. CodeAnt appears in the separate issue-comment overlap disposition, not in the retained formal-review collection, so it is excluded from this metric; none are Issue #10-qualified domains |
| Known post-clean/merge escaped structural finding | **≥1** | **not concluded** | #262 was discovered after #257; Decision 0081 effectiveness remains open separately |
| Human active effort | **UNKNOWN** | **UNKNOWN** | Provider receipts do not encode active time |
| Token/context consumption | **UNKNOWN** | **UNKNOWN** | No trustworthy durable accounting in the selected receipts |
| Monetary inference/provider cost | **UNKNOWN** | **UNKNOWN** | No trustworthy durable accounting in the selected receipts |
| Mobile-only end-to-end recovery | **UNKNOWN** | **UNKNOWN** | Durable state supports reconstruction, but the selected receipts do not prove a mobile-only run |

The two specimens differ materially in scope, risk, implementation shape and
review history. Their elapsed spans, commit counts and reviewed-head counts are
**not a before/after effectiveness estimate** and do not establish that PR #272
was faster or cheaper because of the #262 fix. They are separate observed
baselines for future, protocol-declared comparison.

### Directly measured deterministic-normalization churn

The frozen #262 RCA examined **49 total commits** from its declared measurement
window and found **7 distinct candidate SHAs with directly proven Ruff
failures**. Against that total-commit denominator, the directly evidenced
incidence is **7 / 49 = 14.3%**. This is not a candidate-generation denominator:
the RCA does not establish that all 49 commits were candidate generations.

- 6 formatter failures;
- 1 lint failure;
- one explicit partial-repair cascade where a two-file Ruff report was only
  partly repaired and generated another failing candidate.

The same RCA records 10 explicit `Format`/`Normalize` commits (20.4%) and 11
style/lint housekeeping commits (22.4%), while explicitly refusing to attribute
the broader 20–22% figures wholly to Ruff. The 14.3% figure is therefore only
the conservative directly evidenced Ruff-failure incidence against the frozen
49-commit denominator. It must not be relabeled as the percentage of candidate
generations that failed Ruff.

This is the clearest L0 evidence that deterministic work was crossing the
candidate boundary too late: a review repair could create a new SHA, wait for
remote setup, fail deterministic style, create another SHA, and invalidate
exact-head evidence again.

## Review overlap and unique-yield evidence

A complete historical raw-finding inventory cannot be reconstructed
reliably from the selected timelines without inventing classifications across
provider summaries, inline comments, withdrawn findings and owner replies.
Accordingly, this baseline does **not** publish a whole-PR duplicate rate.

One bounded overlap cluster is directly evidenced in PR #272. The owner
disposition records that **CodeRabbit, Qodo and CodeAnt independently reported
the same shell-wrapper bypass** on head
`183b5948426bf8e074156a50c6b20ce05dec6c54`.

CodeAnt's evidence for this cluster is retained as an issue-comment
disposition, not a formal GitHub PR-review record; this is why CodeAnt does not
increase the formal-review-family count in the table above.

For that one cluster only:

- raw reports: **3**;
- distinct root causes: **1**;
- overlapping reports beyond the first: **2 / 3 = 66.7%**.

This demonstrates that reviewer count and unique-finding yield are different
measurements. It does not generalize a 66.7% duplicate rate to PR #272 or to
Gnostoa review as a whole.

## Escaped finding and successor value

PR #257 reached a recorded clean/converged state and was merged. The later
independent post-merge review that opened #262 found a structural mismatch:
project-wide Ruff expectations exceeded the ordinary PR gate's handwritten
`tools ci tests` scope, leaving `tasks/gnostoa_orientation.py` outside that
gate.

That escaped finding is important for L0 for two reasons:

1. a declared-clean review state did not imply that all deterministic workflow
   gaps were exhausted; and
2. the successor #262 RCA converted the escape into measurable workflow debt
   rather than merely adding another reviewer or another generic gate.

PR #272 then implemented the bounded fix. Its separate Decision 0081
effectiveness window remains open and must not be reinterpreted here as a
positive or negative effectiveness result.

## Liveness, stale-work and provider-capability observations

### Explicit liveness wake-up

PR #272 contains at least one durable, unambiguous manual wake-up. At
2026-09-17 12:00:36Z the owner explicitly followed up with Cubic for an
already-started exact-head review and asked it either to finish or report
unavailability. Final exact-head convergence was recorded at
2026-09-17 12:14:55Z.

The observable wake-up-to-convergence interval is therefore **14 m 19 s**.
This is not generalized as “idle time”: the receipts do not prove which
sub-intervals were provider execution, queueing, owner attention or other work.

### Reviewed-head staleness

The formal review stream contains 28 distinct reviewed heads for PR #257 and 17
for PR #272. Consequently 27 and 16 earlier reviewed heads, respectively, were
superseded by later reviewed heads before the final reviewed generation.

Those counts are useful as an exact-head churn baseline. They are **not**
attributed wholesale to defects, reviewers, Ruff or avoidable work. #262's
separate 7/49 directly proven Ruff-failure measurement is the bounded causal
subset available today.

No reliable durable count was found for duplicate/sibling WIP in the selected
specimens, so that metric is **UNKNOWN** rather than zero.

### Quota and capability

PR #272 records a dated provider-capability failure: a further Cubic exact-head
review could not start after the workspace reached its monthly
**40,000-line** allowance (**40,037 used**). An earlier attempted “Fix with
Cubic” request also received a plan/capability response rather than an edit.

These are provider observations, not core workflow contracts. L0 therefore
records the failure and preserves the work; it does not infer unlimited quota,
require a paid fallback, weaken review requirements or convert provider
unavailability into a clean result.

## Owner liveness attention versus semantic attention

The durable timeline distinguishes event *types* but does not measure active
human minutes:

- liveness attention is visibly represented by explicit trigger/follow-up
  comments such as the Cubic wake-up above;
- semantic attention is visibly represented by finding dispositions that
  evaluate evidence and decide whether a reported gap is valid;
- the same wall-clock interval can contain both, and provider timestamps do not
  identify how long either took.

Therefore this baseline records the distinction but leaves both active-time
totals **UNKNOWN**. A later mechanism may reduce liveness events, but it cannot
claim saved semantic effort from these historical receipts without new
measurement.

## Setup and maintenance effort

Provider-visible artifact volume is measurable; effort is not. PR #257 changed
8 files with +2,224/-0 lines and used 71 branch commits. PR #272 changed 15
files with +1,392/-34 lines and used 48 branch commits. These figures describe
change/review surface and churn, **not person-hours**.

The L0 lesson is to measure future setup/maintenance work prospectively rather
than backfill a historical labor estimate.

## Smallest reusable operating loop

For the first #15 successor slice, the durable operating state is intentionally
small:

| Field | Current L0 value |
|---|---|
| Task | Issue #15 WI-DET-01, L0-lite observed baseline |
| Source | Protected main plus exact Issue/PR/provider receipts named above |
| Current intent | Establish a truthful baseline and expose a falsifiable target for useful L1 |
| Semantic owner | Existing #10/#11/#12 contracts; L0 creates no new semantic authority |
| Accountable owner | `@ktogias` under existing project governance |
| Effect authority | None created by this assessment |
| Parallel lane | #262 / Decision 0081 effectiveness assessment; non-blocking for #15 ascent |
| Next #15 rung after integrated L0-lite | Separately admitted **useful L1** read-only intent/current-state reconciliation and real R2A dogfood |
| Explicit non-goals | L2/L3 code, worker dispatch, provider mutation, paid inference, telemetry platform, Phase-D execution |

A fresh client should be able to recover this row, reacquire the exact current
provider state, and identify the next permitted action without access to the
conversation that produced this assessment. That property is the **recovery
target** for L0. This record demonstrates durable reconstruction from project
surfaces in the present workflow; it does not claim that a mobile-only
end-to-end recovery run has already been measured.

## Falsifiable L1 targets derived from L0

L0 does not pre-approve an L1 design. It supplies a baseline against which the
already-selected useful-L1 hypothesis can fail.

A useful L1 should, on real subsequent work, be able to show all of the
following without acquiring semantic or write authority:

1. **Current-state recovery:** a fresh client reconstructs the exact subject,
   current intent, observation cut, protected authority identities and next
   permitted action from durable state.
2. **Liveness reduction:** explicit manual status/wake-up events decrease
   relative to comparable work, while unavailable providers remain visible.
3. **Stale-work reduction:** reviewed-head or equivalent exact-subject churn
   attributable to stale collection/reconciliation decreases; unrelated
   semantic repair remains visible rather than being counted as automation
   failure.
4. **Truthful incompleteness:** missing pages, reviews, qualification, quota or
   protected runtime capability yield explicit incomplete/unavailable states,
   never fabricated completion.
5. **No authority drift:** the reducer consumes R2A/#10/#11/#12-owned results
   and projects status; it does not create a second PASS, quorum, qualification
   or owner-approval semantics.
6. **Net-value accounting:** new setup/maintenance effort and provider/cost
   observations are measured prospectively and retained with negative or
   missing outcomes.

No threshold is invented here for metrics that lack a comparable denominator.
The first real L1 dogfood must declare its comparison protocol before using its
results to claim improvement.

## L0-lite disposition

The baseline is **established with explicit unknowns**, not “complete
telemetry.”

It supports three bounded conclusions:

- exact-head review churn is large enough to measure rather than hand-wave;
- deterministic preflight escapes are directly evidenced in #262's frozen
  window: 7 distinct Ruff-failing candidate SHAs among 49 total commits
  (14.3% against that commit denominator, not a candidate-generation rate); and
- liveness/provider friction is visible in durable receipts, but historical
  human attention, context and cost cannot be reconstructed honestly.

That is sufficient for the intended L0-lite role: define a truthful comparison
surface for the next useful L1 slice without creating the infrastructure that
L1 is supposed to justify.
