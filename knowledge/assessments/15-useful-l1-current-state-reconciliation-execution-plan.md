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
   - first concrete GitHub REST adapter;
   - translation from GitHub-native Pull Request/review/comment/check objects into the provider-neutral internal snapshot;
   - complete Link-header pagination;
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
   - bounded collect→publish transfer sized below the provider job-output limit after encoding;
   - at most 8 Pull Requests per execution so 8 × 32,768-byte projections plus envelope overhead remain below the 300,000-byte raw transfer bound;
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
conflicts are explicit ambiguity. Shared projection execution identity is also
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
- provider pagination/currentness tests;
- projection effect tests with mocked provider transport;
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
| PN-02 | Decision 0086 / Each provider adapter owns translation; #15 provider-neutral scope | A materially different native lifecycle/check model translates into the private contract and yields equivalent common behavior without common production changes | Existing GitHub adapter plus test-only native translator in `tests/test_review_reconcile_l1_followups.py::test_materially_different_native_translator_reuses_core_unchanged`; common reducer and projection | Commit `59ebc8432170091af995b895bcb578c47dd7922d` adds distinct native vocabulary, opaque subject/review identities and missing checks capability while reusing the core unchanged | Source evidence IMPLEMENTED; exact-head execution/reviewer disposition PENDING |
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
