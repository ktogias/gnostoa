---
type: Decision
title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
description: Define a provider-neutral deterministic current-state reconciliation core with a first protected-source GitHub adapter, consuming existing R2A evidence without acquiring semantic or candidate-mutation authority.
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
  - id: l0-baseline
    resource: /assessments/15-l0-lite-observed-workflow-baseline.md
    title: WI-DET-01 L0-lite observed workflow baseline
  - id: r2a
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Evaluate semantic review assurance through bound evidence and an advisory deterministic gate
  - id: restored-runtime
    resource: ./0085-promote-current-advisory-restoration-runtime.md
    title: Promote the exact restoration runtime into protected current-advisory transport authority
  - id: github-workflow-events
    resource: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
    title: GitHub Actions workflow events
  - id: github-token-permissions
    resource: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions
    title: GitHub Actions GITHUB_TOKEN permissions
  - id: github-pagination
    resource: https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
    title: GitHub REST pagination
  - id: github-reviews
    resource: https://docs.github.com/en/rest/pulls/reviews
    title: GitHub Pull Request review endpoints
  - id: github-review-comments
    resource: https://docs.github.com/en/rest/pulls/comments
    title: GitHub Pull Request review-comment endpoints
x-project-knowledge:
  id: kit.decision.0086.implement-useful-l1-as-protected-source-github-current-state-reconciler
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
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: references
      target: /decisions/0085-promote-current-advisory-restoration-runtime.md
---

# Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter

## Context

Issue #15 L0-lite is integrated at protected main
`0129244780a56bfbb6736dc96343c782f68861a3`. Its measured baseline shows that
exact-head churn, manual liveness wake-ups and provider-capability gaps are
observable, while active owner effort and historical context cost cannot be
reconstructed honestly.

The owner has now separately admitted the bounded useful-L1 slice. The needed
capability is not a new semantic reviewer. It is a small current-state
reconciler that can reacquire live provider facts, bind them to the exact Pull
Request subject, translate the retained review observations into the existing
R2A input model, consume the already protected current-advisory route and
publish a disposable projection that a fresh client can use without the
original conversation.

## Decision

Implement useful L1 as **one provider-neutral deterministic reconciliation core plus provider adapters**. The first concrete adapter is Gnostoa-self GitHub, but provider identity, repository/change-request identity, review observations, review-thread observations, check observations and coverage are normalized before they reach the core. The internal contract stays implementation-private until repeated evidence justifies a public contract.

### Provider abstraction boundary

The core `tools/review_reconcile.py` must not contain GitHub-specific endpoint,
event, Pull Request field, URL-shape or object-ID semantics. It consumes one
provider-neutral internal snapshot with these normalized concepts:

- provider identity;
- repository identity;
- change-request `kind + id`;
- open/closed lifecycle state;
- exact head/base/merge-base commits;
- conversation coverage;
- semantic-review observations;
- review-thread observations;
- exact-head check observations with explicit observation timestamps.

Provider-native IDs are opaque identities, not ordering primitives. Adapters must
normalize freshness/order evidence explicitly; the core chooses current check
state by observation time rather than assuming GitHub-, GitLab- or other
provider-specific ID ordering.

Each provider adapter owns translation from its native API into that internal
shape and owns any provider-specific projection write. Adding another provider
therefore means implementing another adapter against the same internal contract,
not refactoring R2A, the reducer, projection semantics or current-state logic.

The GitHub adapter remains self-only and implementation-private in this slice.
No GitHub vocabulary is promoted into R2A or a generic public Gnostoa schema.

### Trusted execution/source boundary

Use a dedicated GitHub Actions workflow whose executable implementation is
checked out from **protected default-branch source**, not from Pull Request
candidate code.

The primary automatic wake-up is completion of the existing
`Gnostoa verification` workflow through `workflow_run`. Add a bounded hourly
reconciliation wake-up for open Pull Requests and an explicit
`repository_dispatch` recovery path. Do not use a write-capable
`workflow_dispatch` route: a manual dispatch may target a non-default ref, so
this slice keeps effect-capable recovery bound to default-branch workflow
source.

The workflow must not use `pull_request_target` to execute candidate code. It
must never check out an untrusted PR head into a job holding write-capable
credentials.

### Provider collection

The GitHub adapter uses the versioned REST API with complete pagination and
retains independent source coverage for:

- Pull Request metadata and exact head/base;
- issue/conversation comments;
- formal Pull Request reviews;
- inline Pull Request review comments/threads;
- exact-head check runs/status needed by the current diagnostic view.

Events are wake-ups only. Every execution reacquires current provider state.
Missing pages, API failures or ambiguous currentness remain explicit
`PARTIAL|UNAVAILABLE|ERROR`; they never mean clean.

### Reducer and R2A composition

The deterministic reducer:

1. validates the normalized provider snapshot and exact PR subject;
2. computes a bounded observation cut and source coverage;
3. maps collected review evidence into the **existing**
   `review-check-input.schema.json` envelope;
4. acquires the protected current-advisory authority bundle and copies only the
   contract-required authority, judge and qualification values into the
   caller envelope;
5. calls the existing protected prior-effective current-advisory route;
6. consumes the resulting R2A
   `PASS|BLOCKED|INCOMPLETE|CONFLICTING` without redefining any of them;
7. emits one implementation-private current-state projection.

The reducer may describe collection/currentness and the next mechanically
permitted action. It cannot create qualification, quorum, semantic
sufficiency, owner approval or merge eligibility.

### Projection

Publish one replaceable PR conversation comment and the Actions job summary.

The projection is non-canonical and must visibly declare:

- exact repository, PR, head, base and merge-base;
- provider observation cut and per-source coverage;
- protected-main revision and protected outer-runtime identity;
- R2A outcome, reason and `binding:false`;
- currentness/freshness;
- next permitted action or explicit wait/block;
- workflow execution generation.

Before any comment create/update, reacquire the change-request head and re-read
the prior provider projection. Refuse publication when:

- the head changed since collection;
- the change request is closed/merged when the projection expects open work;
- a retained projection names a later observation cut/execution generation; or
- more than one valid marker-owned projection exists, because the single-comment
  ownership invariant is then ambiguous.

This rejects stale writes that are already observable at the pre-write
read-back. It does **not** claim an atomic or exactly-once publication fence:
a concurrent provider race can still occur between the final read and comment
write. Global workflow concurrency reduces that window, and every projection
remains self-describing by exact head and execution generation so a stale write
cannot masquerade as a different subject. A hard effect fence belongs to the
separately admitted L2 boundary.

### Permissions

Use least privilege. Collection runs read-only. The publication step may use
only the minimum issue/Pull Request write permission required for the single
projection comment; it gets no contents write, workflow write, package write,
review-approval or branch mutation authority.

## Change classification

`critical`.

Although the resulting projection is advisory and non-binding, the change adds
a write-capable provider workflow that consumes protected review authority and
can shape owner-facing current-state decisions. It therefore receives
failing-evidence-first verification, security review and exact-head fresh review
convergence.

## Reuse disposition

Reuse:

- existing GitHub Actions rather than an always-on service;
- existing REST provider primitives and explicit pagination;
- existing protected-main acquisition;
- existing R2A schemas, policy, qualification and result semantics;
- ordinary PR issue comments plus Actions summary rather than a custom Check Run
  or GitHub App.

Do not add a database, event bus, queue service, generic DAG, custom GitHub App,
provider simulator or new semantic policy.

## Consequences

- Gnostoa gains one self-only current-state reconciliation surface that can reduce
  manual provider reconstruction without moving semantic authority out of R2A.
- The owner-facing projection remains disposable and non-canonical; deleting it
  cannot corrupt repository truth.
- A write-capable workflow is introduced, so least-privilege permissions,
  protected-source execution and stale-write refusal become part of the
  verification boundary.
- GitHub is the first concrete provider adapter; provider-neutrality is preserved
  by keeping provider observations separate from the deterministic reducer and
  by avoiding GitHub-specific semantics in R2A itself.
- A truthful incomplete or unavailable result may become more visible and more
  frequent than an optimistic green status; this is intentional fail-closed
  behavior.
- After integration, the first useful end-to-end dogfood must be a naturally
  occurring subsequent Pull Request. This candidate cannot establish its own
  operational value.

## Non-goals

This Decision does not:

- select reviewers or determine reviewer qualification;
- trigger coding workers or mutate PR candidate content;
- create PASS/quorum/approval semantics;
- authorize merge/release/publication;
- implement L2 WorkLease or execution fencing;
- implement L3 semantic orchestration;
- require paid inference;
- make the GitHub-specific normalized provider snapshot a public cross-provider
  schema.

## Failure behavior

Provider incompleteness, current-head drift, missing protected authority,
unavailable protected runtime or R2A incompleteness must produce truthful
diagnostic state and no positive-permission claim. When the provider subject is
known but protected authority/runtime acquisition is unavailable, the projection
retains that subject and explicitly reports protected status `UNAVAILABLE`
rather than aborting the whole reconciliation or inventing identities.

A workflow can complete successfully while the semantic result is
`INCOMPLETE`, `BLOCKED`, `CONFLICTING` or a clearly labelled
`UNAVAILABLE/NOT_RUN` diagnostic. Job success means the reconciler itself
executed its contract correctly, not that semantic review passed.

## Verification

Before production implementation mutation:

- establish focused failing tests for complete pagination, exact-head binding,
  source-coverage accounting, currentness-safe publication and R2A
  pass-through;
- prove the workflow cannot execute PR candidate code with write credentials;
- prove older same-head execution cannot overwrite a later projection;
- prove provider failure remains explicit rather than clean;
- prove R2A semantic fields are consumed unchanged.

Before integration, require the normal critical-change suites, exact-head
provider checks and fresh review convergence.

The first end-to-end semantic dogfood is a naturally occurring eligible
subsequent PR after this slice is integrated. This implementation must not
self-certify its own semantic value.
