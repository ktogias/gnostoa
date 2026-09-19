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
conflicts are explicit ambiguity. Positive next actions require complete/open
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

## Implementation sequence

### L1-A — pure reducer

Implement snapshot normalization/reduction and R2A envelope construction with
network/write effects injected or absent. Keep provider vocabulary internal.

Exit: focused pure tests green; R2A outcomes/reasons are unchanged.

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
