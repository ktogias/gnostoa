---
type: Source
title: Issue 15 provider-abstraction retrospective and root-cause analysis
description: Source-bound analysis of the initial GitHub-coupled useful-L1 reducer, owner-triggered correction, architectural traceability failure, extension consequences and bounded prevention actions.
status: draft
generated:
  by: chatgpt/gpt-6-astra-pro
  at: "2026-09-19T21:50:34Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Deterministic knowledge-workflow mechanics with provider-neutral contracts
  - id: change-request
    resource: https://github.com/ktogias/gnostoa/pull/285
    title: Implement useful L1 current-state reconciliation
  - id: capture-scope
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5745552200
    title: Owner-directed retrospective capture and bounded documentation intervention
  - id: initial-reducer
    resource: https://github.com/ktogias/gnostoa/blob/9f00e50/tools/review_reconcile.py
    title: Initial reducer with explicit GitHub-only acceptance
  - id: initial-plan
    resource: https://github.com/ktogias/gnostoa/blob/7c4f929/knowledge/assessments/15-useful-l1-current-state-reconciliation-execution-plan.md
    title: Initial L1 plan before the provider-abstraction correction
  - id: correction
    resource: https://github.com/ktogias/gnostoa/commit/8d9f7e2
    title: Provider-neutral reducer refactor
  - id: reread-subject
    resource: https://github.com/ktogias/gnostoa/commit/0743998c0de025f7b92f5b519390481c388cdc41
    title: Exact implementation subject inspected when retaining this retrospective
  - id: assurance-follow-up
    resource: https://github.com/ktogias/gnostoa/issues/263
    title: Existing owner of perspective-bound critical assurance
  - id: distillation
    resource: https://github.com/ktogias/gnostoa/issues/259
    title: Gnostoa self-dogfood distillation
x-project-knowledge:
  id: kit.assessment.15-provider-abstraction-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: references
      target: /assessments/15-useful-l1-current-state-reconciliation-execution-plan.md
---

# Issue 15 provider-abstraction retrospective and root-cause analysis

## Purpose, provenance and claim boundary

The owner asked why PR #285 initially implemented a provider-specific core,
although provider-agnostic abstractions were already required; whether it would
have remained provider-specific without the owner's reminder; what extension
costs this would cause; and how to prevent recurrence. The owner subsequently
requested retention of the full analysis, necessary interventions and a PR
review. This document retains that analysis and its current-state correction.

This is an agent-authored retrospective, not human semantic approval, an
independent experiment, a blanket rejection of all work on the PR, or merge
authority. It does not record private reasoning. Code and durable project
records establish observable behavior; causal interpretations and hypothetical
future costs are explicitly distinguished below.

Historical analysis inspected a draft, unmerged candidate at `fca6d54`.
Re-read for this retention inspected **`0743998c0de025f7b92f5b519390481c388cdc41`**,
when #285 was open, unmerged and ready-for-review. The protected main was
`0129244780a56bfbb6736dc96343c782f68861a3`, and #15 was the sole open
`roadmap:now` selection. These are dated observations, not durable live-status
assertions. Read the provider again before acting on a later candidate.

Terminology correction: #284 delivered the L0-lite baseline. **#285 is the
subsequent useful-L1 implementation**, not an L0-lite implementation. The
retrospective must not conflate their scope or evidence.

## Executive finding

**The first implementation had an abstraction, but at the wrong boundary.**
It separated provider I/O from a deterministic reducer, while the supposedly
common reducer still required GitHub identities, fields and object semantics.
Provider independence was an existing work-item obligation, not a new feature
request introduced by the owner's intervention.

The root failure was the loss of that inherited architectural obligation when
forming the local design, implementation sequence and pre-implementation
falsifiers. Decision, plan and RED evidence existed, but their presence did not
establish that the material architecture requirement had been covered.

The eventual refactor was a useful early correction. It does not retroactively
make the original contract provider-neutral or prove that the earlier process
would have detected the error without owner intervention.

## 1. What happened

### Existing obligation and legitimate scope limits

The #15 Work Item explicitly includes a provider-neutral contract and shared
validation semantics behind thin provider adapters. Its multipart record must
remain byte-preserved; this retrospective supplements it through linked
records rather than rewriting its content-addressed body. The original
analysis also identified `AC-OPS-07` in the continuation as the relevant
cross-provider operational criterion.

The bounded L1 choice was legitimately GitHub-first and self-only. It excluded
a second production adapter, a public cross-provider schema, a generic
scheduler and a provider simulator. Those exclusions limit delivery size.
They do **not** permit the common reducer to require GitHub-only input.

A sufficient small design could have been: one real adapter, one private
normalized contract, and a small test-only alternative-provider translation.
Neither a plugin framework nor an external GitLab installation was required.

### Recorded commit sequence

The original analysis retained this sequence from 19 September 2026. Commit
links preserve the inspected historical stages rather than replacing them with
what the branch looks like now.

| Stage | Commits | Evidence significance |
|---|---|---|
| Initial design and plan | `b25c634`, `7c4f929` | GitHub adapter and deterministic reducer selected; the provider boundary was underspecified. |
| Initial RED tests | `6f796ab` | Focused missing-capability evidence preceded production implementation, but did not include provider portability. |
| Initial reducer | `9f00e50` | Common code explicitly rejected every provider except GitHub. |
| Adapter and workflow | `ecc1eb8`, `61615f0` | The provider-specific path was composed into a working implementation direction. |
| Architectural correction | `8d9f7e2`, `eef143a` | The reducer contract changed and native translation moved into the adapter. |
| Portability test and design correction | `cf873d3`, `65eb9fc`, `42fa9ee` | Alternative-provider-shaped evidence and corrected Decision/plan were retained after the initial implementation/refactor. |

The chronology proves what was committed, not everything that might have been
tried in an unrecorded local workspace. Do not invent local test chronology,
active developer time, token usage or a precise rework cost from commit times.

### Direct implementation evidence

At `9f00e50`, `_subject` included:

```python
if snapshot.get("provider") != "github":
    raise ReconciliationInputError("provider snapshot must be GitHub")
```

It also required repository `owner/name`, a positive integer `pull_number`,
`head_sha/base_sha/merge_base_sha`, and native `html_url`; constructed a
`https://github.com/` repository URL; and emitted the fixed change kind
`github-pull-request`. Coverage vocabulary included `pull`, `issue_comments`,
`review_comments` and `check_runs`.

This was more than a GitHub adapter implementation. GitHub knowledge was in the
shared reduction layer. A different adapter could not simply supply its own
identity and reuse that core without modification or impersonating GitHub.

The initial plan at `7c4f929` described a normalized snapshot and no provider
network/write effects in the core. L1-A said to keep provider vocabulary
internal. Neither assertion specified that native vocabulary must be translated
**before** reaching the reducer. Its RED list covered pagination, coverage,
subject binding, protected R2A pass-through, stale writes, trusted execution and
bounded rendering, but not the inherited provider-neutral boundary.

## 2. Root-cause analysis

### Direct cause: semantic coupling inside the pure core

The reducer enforced provider-native input and identity assumptions. Separating
HTTP or token handling from pure code did not remove those dependencies.
Purity and portability are different properties: a function can be completely
deterministic and still accept exactly one provider's model.

### Contributing design error: scope minimization narrowed an invariant

The most plausible interpretation of the recorded choices is that
"GitHub-only delivery for now" became "GitHub-shaped private core for now".
That inference explains the design and code, but it is not a claim about the
agent's unobservable motives or internal reasoning.

Implementation-private is a publication/stability boundary, not permission to
violate an existing architecture obligation. Avoiding premature public schemas
is compatible with an explicit private contract. The right minimalism removes
unneeded machinery, not material invariants.

### Verification escape: tests and code shared the same narrowed specification

The original RED receipt was real evidence of missing planned functionality.
It was not evidence that the plan covered every required behavior. The initial
analysis identified six recorded failures covering missing reducer/adapter/
workflow capabilities; none was a portability counterexample.

A GitHub-only implementation could satisfy that selected test set. When the
same interpretation drives design, implementation and test expectations,
internal agreement can reinforce the original omission. Test-first development
is not, by itself, requirement-complete development.

The later identity-substitution test is valuable but addresses a narrower
question: whether the reducer accepts a differently named provider in the same
normalized shape. It is not alone evidence that a materially different native
model can be translated without changing common semantics.

### Process failure: an existing traceability control did not activate fully

`AGENTS.md` already routed applicable self-work to
`bounded-behavioral-traceability.md`. That Requirement already calls for:

- known material obligations linked to exact task/source selectors;
- observable behavior, implementation paths and evidence;
- a map before the first semantic production mutation;
- explicit contradictions, assumptions and unsupported narrowing;
- separate execution, semantic alignment and reviewer dispositions; and
- independent reconciliation before review-ready.

This change satisfies the Requirement's applicability criteria: multiple paths,
a provider boundary and a plausible passing implementation that could preserve
prohibited behavior. In the initial design/plan/RED artifacts inspected, the
material provider-neutral obligation was not carried into an effective
requirement-to-falsifier row.

The claim is bounded: no sufficient early map was found in the inspected
records. That does not prove which instructions the agent internally read, or
that no other inaccessible record existed. The direct code contradiction is
independently established even without such a global absence claim.

Therefore, merely adding another generic instruction to `AGENTS.md` would not
address the demonstrated mechanism. First make the existing checkpoint work for
this concrete obligation and test whether it catches the old failure.

### Detection boundary: early review did not test this architecture claim

The initial review record identified useful Sourcery findings concerning the
authority fixture, pagination coverage and workflow permissions/default-branch
execution. The early CodeRabbit review was skipped while the PR was draft.
The inspected early findings did not raise provider neutrality.

This is not evidence of a completed, unanimously approving exact-head cohort
that missed the bug. It shows a coverage gap in the review that had occurred by
then. It also illustrates why reviewer count or vendor diversity cannot replace
an explicit task-to-architecture perspective. A different model can reduce
correlated blind spots without becoming a semantic oracle.

### Causal chain and control that did work

```text
existing provider-neutral obligation
  -> incomplete transfer into local architecture and RED specification
  -> I/O separation mistaken for sufficient provider independence
  -> implementation and tests agree on the narrower GitHub-shaped model
  -> early review does not challenge that omitted dimension
  -> owner reasserts the already-existing requirement
  -> core/adapter/tests/Decision/plan are corrected
```

The owner review and reversible pre-merge development boundary worked. The
purpose of prevention is not to remove human architectural judgment; it is to
avoid requiring the owner to restate already-decided invariants during each
implementation.

## 3. What would have happened without the reminder?

**Continuation with provider-specific implementation was the most plausible
observed trajectory, but is not a provable counterfactual.** The reducer,
adapter and workflow had already been authored around that model, and the
initial declared RED/exit checks did not compel its correction.

A later reviewer or owner gate could still have discovered the issue. The PR
was not merged, and merge required a separate owner event. Do not turn this
retrospective into the stronger unsupported claim that the defect would
certainly have reached protected main.

The intervention was a requirement-restoration event, not an arbitrary style
preference, changed product direction or new demand to build GitLab support.

## 4. Consequences for extension

The first additional provider would have faced three unattractive choices:
refactor the common reducer, make its objects pretend to be GitHub, or duplicate
shared logic in a second implementation. The explicit provider rejection and
identity requirements establish that incompatibility directly.

The broader consequences are engineering inferences, not measured outcomes:

- Later projections, tests and orchestration layers could depend on the wrong
  boundary, increasing the eventual regression and migration surface.
- Duplicated common reduction would create multiple places to repair coverage,
  currentness, R2A composition and interpretation errors.
- Forcing a new native model into undeclared first-provider assumptions could
  silently distort check/lifecycle or capability semantics.
- Changing the core for each adapter would require renewed assurance for shared
  behavior that should remain unchanged when only a translation changes.
- A provider-neutral claim in documentation could create misplaced confidence
  in extension cost and reuse, even while GitHub-only tests remain green.

These were risks, not observed production incidents or quantified technical
debt. Because the contract remained private and the work was unmerged, the
correction was still bounded. No loss of data, deployed outage or irreversible
public API migration was established.

## 5. Re-read disposition at the retained implementation subject

### Structural refactor: materially addressed

At `0743998c0de025f7b92f5b519390481c388cdc41`, the reducer consumes
`gnostoa-review-provider-state/v1`, provider identity and normalized repository/
change-request observations. Native API collection belongs to
`ci/review_github_current_state.py`. Decision 0086 explicitly requires native
translation before the common core.

This supports a real structural correction. It is not a claim that every
possible provider feature, public API or production adapter has been qualified.

### Former equal-time opaque-ID issue: no longer an open defect here

The original report identified `_check_summary` at `fca6d54` choosing a latest
check by `(timestamp, opaque ID)`. Equal-time conflicting observations could
therefore change apparent success/failure when only IDs changed. This was a
diagnostic check-summary problem, not a claim that R2A outcomes were rewritten.

At the re-read subject, `_check_summary` instead accumulates states at the
maximum parsed observation timestamp and reports differing same-time states as
`ambiguous`. `test_equal_timestamp_conflicting_checks_are_ambiguous` checks
that outcome and its reconcile-only next action. Another focused test checks
ordering by observation time rather than native ID.

Disposition: **addressed in inspected source and focused test assertions**.
Those tests were not executed in this documentation session. Historical replay
or an ID-renaming/input-permutation metamorphic test remains useful evidence;
its absence must not be described as proof that the repaired bug still exists.

### Remaining portability assurance gap

`test_reducer_core_is_provider_neutral_and_accepts_second_adapter_shape`
constructs the second-provider case by reusing `_snapshot()` with alternate
provider, repository URL, change kind, change ID and source URL. It also checks
that the reducer source does not contain the word `github`.

That catches hard-coded provider identity and obvious textual coupling. It does
not exercise a distinct native-to-normalized translation, unsupported provider
capability, or common-core invariance under an equivalent observation set
translated from a different native shape. A word blacklist is a guard, not a
semantic portability oracle.

Using vocabulary such as `completed` and `success` is not inherently wrong in
a private common contract simply because one provider uses similar names. What
matters is an explicit owned meaning, documented mapping and failure behavior,
with evidence that another native shape can satisfy it without a core rewrite.
Do not prescribe a vocabulary rewrite merely to look more abstract.

### Remaining traceability gap

The updated plan contains a provider-portability section, but its retained
initial RED list and L1-A wording still do not show how the architectural
obligation was falsified before implementation. A dated addendum can reconcile
the present state and prescribe remaining verification. It cannot repair
historical timing or turn later tests into pre-implementation evidence.

## 6. Bounded interventions and owners

### Apply now within #15 / #285

1. Retain this retrospective and source links, including the corrected
   current-state disposition; keep observation, inference, counterfactual and
   unperformed work distinct.
2. Add a dated architecture-to-evidence map to the existing execution plan,
   applying the already-existing behavioral-traceability Requirement. Preserve
   the initial plan as history and explicitly state that the map is late.
3. Request a small test-only alternative-provider translator, not a second
   production adapter. It should translate materially different lifecycle/check
   input and non-numeric opaque IDs into the private contract, then exercise
   the unchanged core and compare the semantic projection after excluding
   legitimate provider provenance/identity differences.
4. Exercise incomplete/unsupported capabilities and equal-time ambiguity;
   equivalent reordering or opaque-ID renaming must not alter the semantic
   outcome. Reuse existing focused tests and helpers rather than build a
   framework.
5. Demonstrate sensitivity to the historical failure with a bounded
   provider-coupling mutant or historical replay. Rejection must be caused by
   the prohibited coupling, not a missing module or malformed unrelated input.
   Label this post-hoc regression evidence, never retroactive RED compliance.
6. Obtain a task-first architecture review that answers exactly which common
   production files a second adapter would need to change, and why. Runtime
   source, permissions, R2A semantics and merge authority retain their existing
   owners and controls.

Items 3-6 are requested verification/remediation, not completed execution claims
in this retrospective. Their actual results and independent dispositions belong
to the subsequent exact-candidate review record.

### Reuse #263 for broader assurance-method changes

The existing #263 already owns the critical-claim matrix, distinct review
perspectives, first-pass independence, review-reset policy and critical-mutant
method hypothesis. Append this second incident as evidence and propose an
architecture/extension perspective and explicit inherited-invariant transfer
before implementation. Do not create an overlapping assurance work item.

Potential later changes belong in the existing self-only Requirement/runbook
route and its bounded tests, after a separately recorded admission. No automatic
new public schema, mandatory reviewer headcount, always-on architecture gate,
new required CI job or general orchestration system follows from this finding.
Existing review-count and human semantic controls are not weakened or silently
replaced.

### Keep #259 and #14 as learning and navigation consumers

#259 receives the distilled lesson: stored knowledge is not proof of constraint
application. #14 receives a source-linked Ariadne checkpoint that preserves the
selected #15 objective and the L1/L2/L3 boundaries. This retrospective must not
promote #263, reopen L0-lite, replace the #15 Work Item, or make the non-blocking
Decision 0081 assessment lane a new dependency.

## 7. What would count as prevention working?

A passing test suite, a longer checklist or more clean review providers is not
sufficient evidence. The concrete target is earlier detection of this failure
class at proportionate cost.

For the next admitted provider-boundary change, record the inherited obligation
and a meaningful counterexample before production mutation. Retain whether the
counterexample actually rejects the old coupling. At review, independently
reconcile the exact task, private contract, changed paths and verification.

For a later #263 evaluation, a proposed small observational cohort is the next
three applicable boundary-touching changes, selected prospectively on admission.
Record per change: obligation coverage before first mutation; owner reminders
of previously decided invariants; core files changed solely to add a provider;
rework attributable to missed boundaries; time/context cost where directly
measurable; and false-block/ceremony cost. An inapplicable change is not a
success. Missing measurements remain UNKNOWN.

This cohort is a **proposal, not an activated experiment or statistically
established causal claim**. Compare outcomes to the retained incident without
claiming that absence of recurrence in a small sample proves prevention.
Narrow or remove ceremony if its cost exceeds demonstrated detection benefit.

## 8. Verification and residual limits of this record

This session inspected exact source through the connected GitHub tools,
including the original reducer/plan, current reducer/tests, current Decision,
existing traceability and admission contracts, current provider selection and
protected-main identity. Earlier commit chronology and early review findings
are retained from the preceding retrospective and their linked historical
records; this session is not a replay of every PR test or review generation.

The local environment had no Docker executable, and a GitHub checkout attempt
failed DNS resolution. No container suite, full native repository suite,
production GitLab adapter, portability mutant or blind independent review was
executed here. Documentation capture must not inherit earlier-head CI results
as fresh verification of the new documentation candidate. The final receipt
records actual provider read-back and available checks separately.

The author of this record is not an independent approver of its own proposed
plan addendum. Owner authorization to record it is not owner endorsement of its
causal conclusions. All generated knowledge remains draft pending the existing
semantic review and integration process.

## Conclusion

The project had the right architectural intent but did not reliably carry it
into the local implementation contract and falsifiers. The owner supplied the
missing constraint application. The smallest credible improvement is to make
that transfer visible and falsifiable using the existing workflow, then measure
whether it reduces repeat intervention. More documentation alone is not the
outcome.
