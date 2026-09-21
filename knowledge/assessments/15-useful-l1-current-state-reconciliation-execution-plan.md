---
type: Source
title: Issue 15 useful L1 current-state reconciliation execution plan
description: Bounded critical-change plan for provider-neutral current-state reconciliation with a first protected-source GitHub adapter, consuming existing R2A semantics and publishing one stale-safe non-canonical projection.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-19T16:36:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5743533633
    title: Owner admission — bounded useful L1 slice
  - id: decision
    resource: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
  - id: provider-abstraction-retrospective
    resource: ./15-provider-abstraction-retrospective.md
    title: Provider-abstraction retrospective and root-cause analysis
x-project-knowledge:
  id: kit.assessment.15-useful-l1-current-state-reconciliation-execution-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: derived-from
      target: /assessments/15-l0-lite-observed-workflow-baseline.md
    - kind: references
      target: /assessments/15-provider-abstraction-retrospective.md
---

# Issue 15 useful L1 current-state reconciliation execution plan

## Bound subject

- Work Item: #15 / WI-DET-01.
- Owner admission: issue comment `5743533633`.
- Starting protected main:
  `0129244780a56bfbb6736dc96343c782f68861a3`.
- Change class: **critical**.
- Semantic kernel: existing #11/R2A only.
- Implementation surface is Gnostoa-self; no public adopter contract changes.

## Smallest outcome

A trusted default-branch workflow can inspect one real open Pull Request,
collect the declared provider evidence completely or explicitly partially,
invoke the protected current-advisory path with the resulting existing R2A
input, and update one non-canonical PR projection without mutating candidate
code or inventing semantic authority.

## Planned implementation surface

1. `tools/review_reconcile.py`
   - **provider-neutral** internal snapshot validation;
   - normalized provider/repository/change-request/review/thread/check vocabulary;
   - exact subject and source-coverage reduction;
   - R2A input assembly using the protected authority bundle;
   - bounded provider-neutral projection model/rendering;
   - literal HTML/Markdown-safe rendering of provider-controlled titles;
   - no provider endpoint, network, credential or write effects.

2. `ci/review_github_current_state.py`
   - first concrete GitHub REST + GraphQL adapter;
   - translation from GitHub-native Pull Request/review/comment/thread/check
     objects into the provider-neutral internal snapshot;
   - complete Link-header pagination for REST surfaces and bounded cursor
     pagination for GraphQL review threads;
   - inline REST review comments retained as metadata used to bind each GraphQL
     thread root to its review observation and exact commit;
   - GraphQL `reviewThreads.isResolved` normalized to provider-neutral
     `resolved|unresolved`; unmapped roots, GraphQL errors, missing cursors or
     partial REST metadata remain explicitly incomplete;
   - RFC3339 timestamp validation and explicit per-source errors;
   - queued checks without provider start/completion timestamps use the stable collection cut and remain pending;
   - at most three bounded passes to confirm the retained observation cut;
   - continued change or a future cut remains explicitly PARTIAL, not clean;
   - subject acquisition failures produce non-publishable per-PR diagnostics without aborting other selected PRs;
   - normalized provider snapshot;
   - immediate pre-write head/currentness re-read;
   - one marker-owned issue-comment create/update path;
   - no candidate checkout or source mutation.

3. `.github/workflows/review-current-state.yml`
   - protected-source `workflow_run`, hourly schedule and default-branch `repository_dispatch` recovery;
   - minimum token permissions;
   - repository-root imports configured for both collect and publish entrypoints;
   - bounded collect→publish transfer through a one-day Actions artifact;
   - at most 8 Pull Requests per execution so 8 × 32,768-byte projections plus
     envelope overhead remain below the 300,000-byte raw transfer bound;
   - repository-scoped serialization with `cancel-in-progress: false` and `queue: max`;
   - finite queue of at most 100 pending runs, with possible overflow and scheduling delay;
   - hourly open-PR recovery, not an immediate or lossless wake-up guarantee;
   - Actions summary plus bounded projection publication.

4. Focused tests and workflow-policy contracts only. Do not introduce a public
   schema unless implementation evidence proves an existing internal typed
   structure is insufficient.

## Provider portability contract

The implementation is accepted only if the pure reducer can consume a second
synthetic provider using different repository URL and change-request
vocabulary, without any GitHub branch in the reducer. A future GitLab or other
adapter may translate its native merge-request/review/check objects into the
same internal shape and reuse the reducer, R2A composition and projection core
unchanged.

The internal adapter contract also requires explicit observation timestamps for
check state; opaque provider IDs never define freshness, and same-timestamp
conflicts are explicit ambiguity. Every source coverage record also requires a
non-negative retained `count`; the subject count is exactly one and retained
array counts must equal their normalized payload lengths. Missing cardinality is
invalid input even when an adapter labels the source `COMPLETE`.

Review recommendation effectiveness does not own thread lifetime. The latest
provider-effective opinion remains the only active opinionated recommendation
per reviewer, while an unresolved thread rooted in a superseded review is
retained as derived `COMMENT_ONLY` thread evidence. This preserves existing
R2A unresolved-thread policy without reviving the superseded recommendation.

Shared projection execution identity is also
opaque: the core accepts a non-empty `execution_id` and does not derive
freshness from its type or lexical order. Provider-specific publication ordering
stays in the adapter; the GitHub adapter alone interprets
`github-actions:<run-id>:<attempt>`. Positive next actions require complete/open
provider state plus AVAILABLE protected capability. When provider state is not
current, the exact consumed R2A result is retained only as observed diagnostic
evidence; the current projection state is non-current/unavailable and does not
render an incomplete-evidence `PASS` as its present result. Duplicate
workflow-owned projection comments are an explicit fail-closed provider-write
condition rather than an invitation to guess which comment owns the projection;
marker text from an arbitrary participant does not establish ownership.

Bounded stable read-back is not atomic provider history or an L2 effect fence.
The confirming pass starts after the retained cut and repeats all required
reads; inability to confirm within three passes preserves incomplete coverage.
Per-source counts describe the retained pass, not total API requests.

## RED evidence

Before adding production files, focused tests must fail for at least these
missing capabilities:

- complete multi-page provider collection;
- source-by-source coverage and explicit partial/error status;
- exact head/base/merge-base binding;
- protected authority/R2A pass-through with `binding:false`;
- stale-head publication refusal;
- later-projection overwrite refusal on unchanged SHA;
- candidate-controlled workflow execution/write credential rejection;
- bounded rendering that excludes raw review payload bodies from the projection.

Characterization evidence may additionally pin existing R2A and protected-main
behavior, but it does not replace the required RED cases.

Historical qualification: the original list above omitted a provider-portability
falsifier. The dated corrective addendum below records that gap; later tests or
this plan correction cannot retroactively satisfy a before-implementation gate.

## Implementation sequence

### L1-A — pure reducer

Implement snapshot normalization/reduction and R2A envelope construction with
network/write effects injected or absent. Define the implementation-private
normalized meanings before extending the core; keep provider-native vocabulary,
identity rules and API translation in the adapter, not merely inside a private
core module. A private contract does not require a public schema or framework.

Exit: focused pure tests green; R2A outcomes/reasons are unchanged; reconcile the
provider-boundary evidence in the dated addendum rather than infer portability
from I/O separation or provider-name substitution alone.

### L1-B — GitHub read adapter

Add bounded REST acquisition with explicit pagination/coverage and size/page
limits. The adapter preserves IDs, timestamps and exact head association needed
for currentness without copying unnecessary raw payloads into the projection.

Exit: complete/partial/error fixtures green; no provider writes.

### L1-C — stale-safe projection effect

Add exactly one marker-owned conversation comment effect with read-before-write
currentness. Re-read the current PR and existing projection immediately before
the effect, and require the candidate projection to match the exact GitHub
provider/repository/PR/head target before any create/update. No other write
endpoint is permitted.

Exit: old-head and later-generation negative tests green.

### L1-D — trusted workflow

Add the default-branch workflow. It must:

- never use `pull_request_target` to execute candidate source;
- check out protected/default branch source only;
- declare minimal token permissions;
- pass the PR identity to the integrated adapter;
- keep workflow success distinct from R2A semantic outcome.

Exit: workflow contract tests plus normal CI green.

## Verification

Focused:
- reducer unit/property-style permutations;
- provider REST/GraphQL pagination, thread-resolution and currentness tests;
- projection effect tests with mocked provider transport;
- per-PR collect/publish failure-isolation tests so one provider failure cannot
  abort the remaining bounded batch;
- workflow YAML structural/security tests;
- executable collect/publish import checks with inherited PYTHONPATH removed;
- Markdown-rendered adversarial title checks;
- existing R2A current-advisory regressions.

Repository:
- `./ci/style --check`;
- policy, security-fast, fast;
- Python 3.11/3.12;
- extended;
- regression;
- smoke;
- CodeQL/provider security checks.

Review:
- exact candidate sealing under Decision 0081 operating rule;
- fresh external review;
- all actionable findings reconciled;
- merge remains a separate owner event.

## Rollback and compatibility

Rollback is removal/disabling of the new self-only workflow and helper surface.
No canonical project state, schema version, provider rule, release identity or
R2A semantic policy depends on the projection.

Existing comments remain non-canonical evidence and may be deleted manually
without corrupting canonical state.

## Stop conditions

Stop and return to the owner only if:

- the bounded design needs broader provider-write authority;
- provider semantics require a custom App/service or credential expansion;
- a material conflict requires changing #10/#11/#12/R2A semantics;
- implementation needs L2 execution-generation/effect fencing to be safe;
- paid inference or a worker becomes necessary;
- merge/integration authority is due after convergence.

Ordinary queued/running checks or reviewer latency are not stop conditions.

## Provider-boundary corrective addendum — 2026-09-19 UTC

Author: ChatGPT / GPT-6 Astra Pro. Owner-directed capture scope is recorded in
[#15 comment 5745552200](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5745552200).
The [full retrospective](15-provider-abstraction-retrospective.md) retains the
original implementation, causal analysis, counterfactual limits and current
corrections. This is a late reconciliation of Decision 0086 and the existing
[behavioral-traceability Requirement](../requirements/bounded-behavioral-traceability.md),
not a claim that an adequate map existed before the initial implementation.

Architecture inspection was bound to implementation
`0743998c0de025f7b92f5b519390481c388cdc41`. Documentation preparation was re-read
at `9ec4a2e1554b046e3879f4a27d8b073e9fdb9289`; intervening queued-check timestamp
and transfer-budget clarifications are preserved. Before disposition, re-bind
each affected row to the actual review head and executable evidence. The
inspection below is not full-suite execution or independent approval.

### Inherited obligation to evidence map

| ID | Exact obligation / source selector | Expected observable behavior | Implementation and evidence path | Observed state at inspection / remaining evidence | Execution; alignment; independent disposition |
|---|---|---|---|---|---|
| PN-01 | #15 Scope / Included: provider-neutral contract and shared semantics in thin adapters; Decision 0086 / Provider abstraction boundary | Another provider supplies its own repository and opaque change-request identity without a core provider branch | `tools/review_reconcile.py::_subject`; `tests/test_review_reconcile_l1.py::test_reducer_core_is_provider_neutral_and_accepts_second_adapter_shape` | GitHub-only restriction removed; identity substitution asserted. This establishes a narrower claim than native semantic portability | Static source inspection only; execution NOT RUN here; SUPPORTS structural correction only; reviewer PENDING |
| PN-02 | Decision 0086 / Each provider adapter owns translation; #15 provider-neutral scope | A materially different native lifecycle/check model translates into the private contract and yields equivalent common behavior without common production changes | Existing GitHub adapter plus test-only native translator in `tests/test_review_reconcile_l1_followups.py::test_materially_different_native_translator_reuses_core_unchanged`; common reducer and projection | Commits `59ebc8432170091af995b895bcb578c47dd7922d` and `06725ff42f0fb84a675296c707f03ec4e0de6461` add distinct native lifecycle/check/verdict vocabulary, opaque subject/review/execution identities and missing checks capability while reusing the core unchanged; the strengthened test maps native `accept`/`note` at the adapter boundary and proves identical normalized R2A recommendations through the existing review adapter | Source evidence IMPLEMENTED; exact-head execution/reviewer disposition PENDING |
| PN-03 | Decision 0086 / opaque IDs and explicit freshness; same-time conflicts | Renaming opaque IDs or permuting equivalent observations cannot select a different semantic result; conflicting latest equal-time checks remain ambiguous | `_check_summary`; existing equal-time and observation-time tests; `test_native_id_ordering_mutant_is_rejected_by_ambiguity_semantics` | Commit `59ebc8432170091af995b895bcb578c47dd7922d` replays conflicting same-time opaque IDs in both input orders; production still reports ambiguity instead of choosing by ID | Source evidence IMPLEMENTED; exact-head execution/reviewer disposition PENDING |
| PN-04 | Decision 0086 / Provider collection and Failure behavior | Missing or unsupported required evidence remains incomplete/unavailable, never complete or a positive permission claim | `_coverage`, `build_projection`, adapter normalization; existing partial/closed/protected-capability tests plus alternative-provider missing-capability case | Existing fail-closed assertions inspected. Verify the alternative translator does not fabricate absent capability evidence | NOT RUN here; UNKNOWN for cross-provider claim; reviewer PENDING |
| PN-05 | Decision 0086 / Reducer and R2A composition, Permissions and Non-goals | Adapter changes preserve existing R2A authority/outcomes and do not introduce source mutation, approval, merge or L2/L3 authority | `build_review_input`, existing R2A regressions, adapter/workflow security contracts | Existing assertions are inputs to review, not this author's fresh execution or approval; retain all current security and exact-head checks | NOT RUN here; UNKNOWN for final candidate; reviewer PENDING |
| PN-06 | Decision 0086 / execution identity ownership | Shared core accepts opaque execution identity while publication ordering remains provider-owned; a second provider does not need numeric coercion or a common sequence service | `build_projection`; GitHub `_projection_key`; opaque execution case in the native-translator test | Commits `400c0a117c2779a45d85dc8294b0999e1892e40c` and `788605982f216aab5913e8c4de2873aedfabd028` remove integer run/attempt requirements from the core and keep GitHub run ordering in the adapter | Source evidence IMPLEMENTED; exact-head execution/reviewer disposition PENDING |

The existing #15 multipart record and its acceptance criteria remain unchanged.
These rows instantiate the admitted L1 boundary; they do not claim completion of
#15's full future cross-provider operational scope.

### Bounded requested verification

Use the current focused test surface, not a new framework. A test-only
synthetic adapter may map genuinely different native fields and lifecycle/check
states, non-numeric opaque IDs and unavailable capabilities into the existing
private contract. Exercise `build_review_input` and `build_projection` unchanged.
Compare semantic fields while explicitly excluding legitimate provider identity,
source URL and observation-provenance differences; do not compare by dropping
fields that carry the property being tested.

Names such as `completed` or `success` may be owned normalized vocabulary.
Similar spelling to a native provider is not itself a defect. Document the
mapping and unknown/unsupported behavior; do not require a cosmetic vocabulary
rewrite or silently reinterpret existing R2A recommendation semantics.

Prove that a focused portability case rejects the known failure: for example,
introduce a temporary GitHub-only acceptance mutant at the private boundary in
an isolated test execution, or replay the compatible historical boundary. A
failure caused only by a missing module, an unsupported unrelated schema or a
broken fixture is not portability evidence. Preserve this as post-hoc
regression sensitivity, not historical pre-implementation RED compliance.

For any corrective production mutation, establish the affected failing or
characterization evidence first, then run formatting and the applicable focused
and repository suites under the existing policy. Do not widen production scope
to a second provider, public schema, generic engine or new required CI gate.

### Architecture review handoff

The next architecture reviewer starts from #15's provider-neutral scope and
Decision 0086, then the exact candidate, before using this author's conclusions
as an answer key. It must answer:

- Which common production files must change solely to add a second adapter, and
  why? An unavoidable common change requires explicit contract-gap disposition,
  not a blanket claim of already-proven portability.
- Are native lifecycle/check/capability assumptions normalized at the adapter
  boundary, and are missing information and equal-time conflicts preserved?
- Does the portability counterexample reject the prohibited old coupling for
  the intended reason, rather than only pass a renamed fixture?

Retain the reviewer's own conclusion and each finding separately from executor
responses. An unclosed material portability finding remains for explicit
resolution before architectural acceptance; this addendum is not its closure.
Existing review-count, independence, exact-head CI and owner-merge controls are
unchanged. Broad future assurance-method changes belong to #263 under its
separate admission boundary, not to this L1 patch.


## Thread-state completion addendum — 2026-09-20 UTC

Owner direction after the first convergence pass admitted completion of real
review-thread state inside this same useful-L1 slice before merge. This closes
the previously honest-but-low-utility REST-only degradation without widening
the semantic authority boundary.

Acceptance criteria:

- **TS-01 — real identity/state:** acquire GitHub review-thread IDs and
  `isResolved` through GraphQL; do not infer resolution from REST comments.
- **TS-02 — bounded pagination:** follow GraphQL cursors under the existing page
  and item bounds; missing cursors and page failures remain partial/error.
- **TS-03 — exact bridge:** join each GraphQL thread to retained REST
  review-comment metadata by the provider database identity of the root comment.
  An unmapped root is incomplete evidence, never silently dropped as complete.
- **TS-04 — provider-neutral core:** normalize the adapter result to
  `resolved|unresolved` before the common reducer. No GitHub endpoint, GraphQL
  field name or token rule enters `tools/review_reconcile.py`.
- **TS-05 — existing R2A only:** aggregate a review's thread state as
  `unresolved` when any associated normalized thread is unresolved, otherwise
  `resolved`; pass that through the existing R2A input. Do not redefine
  unresolved-thread policy.
- **TS-06 — read failure semantics:** GraphQL uses POST transport but is a
  provider read; HTTP/transport/GraphQL failures must therefore become
  `ProviderReadError` and source incompleteness, not write failures.
- **TS-07 — executable evidence:** retain RED evidence for the prior REST-only
  behavior, then require focused thread pagination/state/error regressions,
  normal style/compatibility/repository verification and fresh exact-head
  review.
- **TS-08 — normalized referential integrity:** every retained normalized
  review thread must reference a collected review observation. Orphan thread
  references are invalid input and fail closed in the provider-neutral reducer;
  they are never silently dropped from otherwise COMPLETE evidence.
- **TS-09 — confirming-read evaluation cut:** after a stable confirming pass,
  advance the retained provider observation / R2A `as_of` cut to that pass's
  completion time. Thread state read during the pass must never be attributed
  to an earlier cut; backward-clock or unstable cases remain incomplete.
- **TS-10 — explicit GraphQL rate limits:** classify both HTTP rate-limit
  responses and HTTP-200 GraphQL error documents carrying primary/secondary
  rate-limit evidence as provider `RATE_LIMITED`, not generic `ERROR`.
- **TS-11 — projection-side referential integrity:** apply normalized
  review-thread validation before owner-facing projection construction as well
  as before R2A-input composition. Malformed/orphan thread evidence cannot be
  reported as `CURRENT_AT_OBSERVATION` merely because source coverage fields
  say COMPLETE.
- **TS-12 — exact GitHub API transport boundary:** accept only HTTPS
  `api.github.com` continuation/request URLs on the default HTTPS port
  (implicit or explicit 443), with no userinfo or fragments. Reject malformed
  and non-default explicit ports before any provider read follows them.

A fresh review also exposed a bounded-batch availability defect: an exception
while collecting or publishing one Pull Request could abort the remaining
entries. The same corrective generation therefore requires per-entry isolation:
the affected subject degrades to an explicit non-published diagnostic while
subsequent subjects are still attempted. This changes availability/blast radius,
not stale-write or merge authority semantics.


## Independent full-review remediation addendum — 2026-09-20 UTC

Owner admission after the exact-head independent review selects FR-01 through
FR-05 for same-purpose remediation before merge. The RED candidate
`49d9c997728aca8d3c08c4a8f3ea63acdc812232` changes tests only and runs 1,118
source tests with six expected failures plus one expected pre-provider-I/O
error, proving the following gaps before production mutation:

- **FR-01 / certified cut:** a later full pass must cover the retained cut; the
  cut cannot advance to the end of the confirming pass.
- **FR-02 / complete status-check model:** GitHub Check Runs and commit statuses
  are both normalized; logical check identity is adapter-owned and distinct
  from display name/integration collisions.
- **FR-03 / effective review state:** retained review history stays available for
  thread identity, but only the provider-effective latest opinionated review per
  reviewer enters semantic R2A observations. Equal-time conflicting latest
  opinions make review coverage partial rather than selecting by opaque ID.
- **FR-04 / protected authority currentness:** an AVAILABLE protected-main
  generation is reacquired immediately before provider write; a superseded
  generation is non-publishable.
- **FR-05 / traceability:** the Useful-L1 guardrail names thread-state,
  render-compatibility and independent-full-review regression suites.

The same generation also hardens the already-captured GitHub execution-ID
boundary: a publication candidate must be GitHub-orderable before provider I/O,
and an exact-subject workflow-owned retained projection with an unorderable
generation fails closed instead of being ignored. Direct collect mode requires a
positive run/attempt and per-entry publication summaries surface retained error
types.

These corrections do not add L2 effect fencing, merge/approval authority, a
public provider schema or a second production provider. Final read→write TOCTOU
remains the explicitly admitted L1 residual.

## Post-convergence review hardening addendum — 2026-09-21 UTC

A later exact-head review reopened two normalized-contract gaps after the prior
FR-01..FR-05 convergence. Both are same-purpose L1 fail-closed corrections, not
new authority or scope.

The tests-only RED candidate
`1e83c72576aa2928cb7a448688a24f5afd95f829` adds the regressions before
production mutation. Its rerun on Python 3.12 completed the source compatibility
suite with **1,119 tests, 6 failures, 2 skips**:

- **RC-01 / coverage cardinality:** five failures prove that omitting `count`
  from subject, conversation, reviews, review_threads or checks was accepted by
  the common reducer instead of failing closed.
- **RC-02 / superseded unresolved thread:** one failure proves that a newer
  opinion from the same reviewer removed an unresolved thread rooted in the
  older review from R2A evidence.

The implementation candidate
`8b921fb9a055b8c24d9efeb9fded48ecb3673d2d` makes `count` mandatory and
preserves unresolved superseded-review threads as derived `COMMENT_ONLY`
thread-only observations. The same Python 3.12 source compatibility route then
completed **1,119 tests PASS, 2 skips**; the Python 3.11 compatibility job also
completed successfully.

The thread-only observation deliberately does **not** restore the superseded
`APPROVED|CHANGES_REQUESTED` recommendation. Quorum, conflict and
recommendation-blocker semantics therefore remain owned by existing R2A, while
an R2A policy that blocks unresolved threads can still see the retained
discussion.

A fresh exact-head CodeRabbit pass then exposed a narrower follow-up in that
remediation:

- **RC-03 / current subject binding for old-head thread state:** the derived
  `COMMENT_ONLY` observation still inherited the superseded review's old commit
  as its subject binding. R2A therefore excluded it as `subject_not_exact` when
  the Pull Request had advanced to a newer head, so an
  `unresolved_threads: block` policy still could not see the retained thread.

The style-clean tests-only RED candidate
`8a752666dc1299d2739429a86eecea378ba13e28` completed the Python 3.11 source
suite with **1,119 tests, 1 failure, 2 skips**; the sole failure was the derived
thread observation being `partial` instead of `exact`. The regression also
requires the existing evaluator to return `BLOCKED / BLOCKER_PRESENT` under an
`unresolved_threads: block` policy without restoring the superseded
`REQUEST_CHANGES` recommendation.

Implementation candidate
`46129457da4ac9fd7e6df83c1d3ee4752b06a30c` binds only the derived current
thread-state observation to the current target head while retaining the older
review commit in native provenance. Python 3.11 and 3.12 compatibility are GREEN;
the Python 3.12 source suite completed **1,119 tests PASS, 2 skips**.

A subsequent independent deep pass reopened three narrower invariants:

- **RC-04 / effective old-head thread survival:** an unresolved thread could
  still disappear when its owning review remained effective but was bound to an
  older head, because the whole review observation was excluded as
  `subject_not_exact`.
- **RC-05 / certified-cut thread freshness:** derived current thread-state
  evidence still used the root-comment metadata timestamp, so a valid
  age-sensitive observation policy could discard freshly reacquired unresolved
  state as stale.
- **RC-06 / normalized temporal integrity:** the common reducer accepted
  review/review-thread/check observations later than the snapshot cut; a
  future-dated success could therefore override an earlier failure in a buggy
  second adapter.

The tests-only RED candidate
`8efe64c6fa7b1d92d85fa15d77ac7a7606bacf51` completed the Python 3.11
source suite with **1,122 tests, 3 failures, 2 skips**, one failure per RC-04,
RC-05 and RC-06. Style and type-check passed before the source suite.

The implementation lineage beginning at
`60008ea5d596508c8e195e897b9743e981a08251` separates unresolved current
thread state into a dedicated exact-current `COMMENT_ONLY` observation,
timestamps that state at the certified snapshot cut while retaining origin
timestamps/commits as native provenance, and rejects normalized semantic
observations later than the snapshot cut before both R2A-input composition and
projection reduction. Follow-up test alignment through
`519c6753a2cc512588fec4f4c1665188f3bc3112` updates pre-existing expectations
to the new separated representation without changing R2A policy semantics.

These corrections leave the admitted L1 boundaries unchanged: no reviewer
selection, merge/approval authority, L2 effect fence, L3 orchestration, public
provider schema or second production provider is introduced.

