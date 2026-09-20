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
  - id: github-concurrency
    resource: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
    title: GitHub Actions bounded concurrency queues
  - id: github-pagination
    resource: https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api
    title: GitHub REST pagination
  - id: github-reviews
    resource: https://docs.github.com/en/rest/pulls/reviews
    title: GitHub Pull Request review endpoints
  - id: github-review-comments
    resource: https://docs.github.com/en/rest/pulls/comments
    title: GitHub Pull Request review-comment endpoints
  - id: pygithub
    resource: https://github.com/PyGithub/PyGithub
    title: PyGithub — GitHub REST SDK for Python, LGPL-3.0-or-later
  - id: githubkit
    resource: https://github.com/yanyongyu/githubkit
    title: githubkit — typed GitHub SDK for Python, MIT
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
- exact-head check observations with an adapter-defined opaque logical key,
  human display name and explicit observation timestamps.

Provider-native IDs are opaque identities, not ordering primitives. Adapters must
normalize a logical check identity separately from the human display name and
normalize freshness/order evidence explicitly; the core chooses current check
state by logical key and observation time rather than assuming GitHub-, GitLab-
or other provider-specific ID ordering. If multiple latest observations for the
same logical check share an observation timestamp but disagree on
name/status/conclusion, the state is explicitly ambiguous and cannot be
tie-broken by opaque IDs.

Each provider adapter owns translation from its native API into that internal
shape and owns any provider-specific projection write. Adding another provider
therefore means implementing another adapter against the same internal contract,
not refactoring R2A, the reducer, projection semantics or current-state logic.

The GitHub adapter remains self-only and implementation-private in this slice.
No GitHub vocabulary is promoted into R2A or a generic public Gnostoa schema.
The common snapshot boundary validates normalized review-thread state and
referential integrity before both R2A-input composition and owner-facing
projection construction. A thread that references an unknown review observation
is invalid normalized evidence and cannot be silently omitted from a
`CURRENT_AT_OBSERVATION` projection.

Execution identity follows the same boundary. The shared projection core carries
one opaque, non-empty `execution_id`; it does not parse, order or coerce that
identity. Any provider/runtime-specific freshness ordering belongs to the
adapter that owns publication. The GitHub adapter therefore encodes its native
generation as `github-actions:<run-id>:<attempt>` and interprets that value only
inside its stale/supersession comparator. A future adapter may use a completely
different opaque execution token and ordering rule without changing the core.
This is diagnostic generation identity only; it is not an L2 WorkLease,
sequence service or exactly-once effect fence.

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

The GitHub adapter uses the versioned REST API plus the GraphQL
`PullRequest.reviewThreads` connection, with bounded complete pagination and
independent source coverage for:

- Pull Request metadata and exact head/base;
- issue/conversation comments;
- formal Pull Request review history, with provider-effective/latest
  opinionated state marked explicitly per reviewer before common reduction;
- inline Pull Request review comments as the metadata bridge that binds a
  GraphQL thread root to its review observation, reviewer, commit and retained
  body;
- GraphQL review-thread identity plus `isResolved` state, normalized to
  provider-neutral `resolved|unresolved` thread observations;
- exact-head GitHub Check Runs **and** commit-status contexts needed by the
  current diagnostic view; Check Run logical identity includes its integration
  identity so same-name signals from different integrations cannot overwrite one
  another, while commit statuses retain their provider context identity.

Events are wake-ups only. Every execution reacquires current provider state.
Missing pages, API failures, unavailable thread-resolution state, an unmapped
GraphQL thread root or ambiguous currentness remain explicit
`PARTIAL|RATE_LIMITED|UNAVAILABLE|ERROR`; they never mean clean. GraphQL POSTs
are classified as provider reads, not writes. HTTP-level limits and HTTP-200
GraphQL error documents carrying primary/secondary rate-limit evidence are
classified as `RATE_LIMITED`, not generic provider errors. The adapter does not
infer resolution from REST comments: it joins each GraphQL thread to the
retained REST root-comment metadata and marks coverage partial if that identity
bridge cannot be established. GraphQL supplies the current resolved/unresolved
state while the normalized per-thread timestamp remains the retained REST root
comment metadata timestamp; the certified snapshot cut, not that per-thread
timestamp, proves that the state was reacquired. The provider-neutral core
receives only normalized thread observations and contains no GitHub GraphQL
vocabulary.

REST pagination links and GraphQL requests stay inside the admitted GitHub API
transport boundary: HTTPS, exact host `api.github.com`, and only the default
HTTPS port (implicit or explicit 443), with no userinfo or fragments.
Malformed or non-default explicit ports are provider-read failures rather than
accepted continuation targets.

Timestamp fields are validated as RFC3339 during provider normalization. A
malformed timestamp yields source ERROR on the first page or PARTIAL after
retained pages; it cannot escape as an uncaught date parser error. A valid
queued/waiting check that has not yet received provider `started_at` or
`completed_at` uses the retained collection cut as its observation timestamp
and remains an explicit pending check rather than turning the whole check source
into ERROR.

A single sequential sweep cannot prove that early sources cover a later
observation cut. The adapter therefore performs at most three complete bounded
collection passes, including subject/merge-base reads. Completion of one full
pass establishes a **candidate cut** no earlier than both that pass completion
and every retained provider evidence timestamp. A later confirming pass must
start at or after that candidate cut and reproduce the preceding normalized
snapshot. The retained observation/R2A cut is then the candidate cut covered by
that later full reread — **not** the end of the confirming pass. State that
arrives after an early source was read during the confirming pass is therefore
after the certified cut, rather than silently preceding a completion-time cut
the snapshot did not cover. A backward local clock, continued provider change
or future candidate cut prevents a stable claim and leaves otherwise COMPLETE
sources PARTIAL. Existing source errors are not upgraded. Page and item counts
describe the retained pass, not aggregate API calls.

This bounded stable read-back is not an atomic historical snapshot: provider
history, transient changes between reads, and changes after the retained cut are
not reconstructed. It does not create a transactional provider or L2 effect
fence. Repeated reads may cost up to three times a single bounded sweep.

The scheduled open-PR sweep admits at most **8** Pull Requests per execution.
Combined with the 32,768-byte per-projection renderer cap, this keeps the
worst-case JSON transfer below the 300,000-byte raw collect→publish bound. The
bounded JSON is transferred through a one-day GitHub Actions artifact rather
than a job output. When more than eight open Pull Requests exist, scheduled
recovery rotates deterministic bounded batches across later hourly wake-ups
instead of silently truncating the population. An explicitly selected event
population above the bound still fails closed.

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
sufficiency, owner approval or merge eligibility. A positive next action is
available only when the change request is open, every required provider source
is COMPLETE, protected capability is AVAILABLE, and exact-head check state is
non-ambiguous. Any weaker prerequisite state remains wait/reconcile-only even if
the consumed R2A result itself is PASS.

### Projection

Publish one replaceable PR conversation comment and the Actions job summary.
Provider-controlled title text is rendered literally with HTML and Markdown
escaping; it cannot supply formatting that looks like the advisory's verdict.

The projection is non-canonical and must visibly declare:

- exact repository, PR, head, base and merge-base;
- provider observation cut and per-source coverage;
- protected-main revision and protected outer-runtime identity;
- R2A outcome, reason and `binding:false`;
- currentness/freshness;
- next permitted action or explicit wait/block;
- opaque workflow execution identity.

Before any comment create/update, reacquire the change-request head, re-read
the prior provider projection, and — for a projection that used AVAILABLE
protected authority — reacquire the protected-main authority generation. A
candidate collected under a superseded protected-main revision is stale and is
not written. The candidate projection must also name the exact
target provider, repository, change-request kind/id and collected head; a
same-head projection for another change request is not publishable. Refuse
publication when:

- the head changed since collection;
- the change request is closed/merged when the projection expects open work;
- the provider adapter establishes that a retained projection names a later observation cut/native execution generation; or
- more than one valid **workflow-owned** marker projection exists, because the
  single-comment ownership invariant is then ambiguous.

For the GitHub adapter, workflow ownership means the provider comment author is
`github-actions[bot]` and the decoded projection names the exact GitHub
repository and Pull Request identity being reconciled. Marker text alone is not
ownership evidence and must not make an arbitrary participant comment writable.

For a retained workflow-owned comment, the embedded same-schema projection is
the durable machine-readable identity and ordering evidence; its visible
Markdown is a disposable presentation. Existing-comment discovery therefore
validates the decoded projection semantically but does not require the retained
body to byte-match the current renderer. A presentation-only renderer change is
self-healing: the next admissible publication patches the same owned comment
with the current canonical rendering. In contrast, every **new candidate body**
to be written must still byte-match the current renderer before any provider
effect. A semantic/schema-version change remains a separate compatibility and
migration boundary; presentation evolution alone does not require manual comment
deletion or a schema-version bump.

This rejects PR-subject, projection-generation and protected-authority staleness
already observable at the pre-write read-back. It does **not** claim an atomic
or exactly-once publication fence:
a concurrent provider race can still occur between the final read and comment
write. Repository-scoped serialization uses `cancel-in-progress: false` and
`queue: max`, allowing one running and at most 100 pending executions. Without
`queue: max`, a new pending execution replaces the preceding pending execution;
non-cancellation alone does not preserve wake-ups. The queue is finite: excess
runs can be canceled, and scheduling or provider delays can postpone execution.
There is no immediate, lossless, or unbounded liveness guarantee. The hourly
open-PR sweep and default-branch recovery path reacquire current state after
missed wake-ups; they do not reconstruct a lost event history or guarantee an
execution deadline.

Every projection remains self-describing by exact head and execution generation
so a stale write cannot masquerade as a different subject. A hard effect fence
belongs to the separately admitted L2 boundary.

### Permissions

Use least privilege. Collection runs read-only. The publication step may use
only the minimum issue/Pull Request write permission required for the single
projection comment; it gets no contents write, workflow write, package write,
review-approval or branch mutation authority.

### Verification routing boundary

Useful L1 consumes protected R2A outputs but does not mutate the R2A trust kernel,
protected consumer authority, transport compatibility catalog or historical
promotion path. Therefore this slice is verified as a critical current-state
reconciliation change through the normal policy/security/fast/extended/regression/
smoke suites plus its focused L1 contracts. It must not expand the historical
`semantic-review-assurance` promotion guardrail merely to gain coverage; doing
so would route unrelated provider-reconciliation changes through P2b/R4 promotion
smokes and blur the trust-domain boundary.

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
- existing REST provider primitives plus GitHub GraphQL review-thread reads,
  with explicit pagination;
- existing protected-main acquisition;
- existing R2A schemas, policy, qualification and result semantics;
- ordinary PR issue comments plus Actions summary rather than a custom Check Run
  or GitHub App.

### Prior-art / license assessment

Two concrete Python GitHub SDKs were evaluated before retaining the bounded
stdlib REST/GraphQL adapter:

1. **PyGithub** — LGPL-3.0-or-later. It is mature and covers GitHub REST
   resources, but adopting it would add a substantial GitHub-specific object
   model and an additional LGPL compliance surface while still requiring our
   provider-neutral normalization, exact coverage accounting, protected-source
   workflow split and stale-safe projection rules. It therefore replaces HTTP
   plumbing, not the custom reconciliation semantics.
2. **githubkit** — MIT. Its permissive license is compatible with the project's
   Apache-2.0 distribution model, and its typed REST/pagination support is a
   technically viable GitHub adapter implementation. It was not selected for
   this L1 slice because the admitted surface needs only a small bounded subset
   of endpoints; introducing a new runtime dependency would increase supply-chain
   and lockfile scope without removing the provider-neutral reducer or
   currentness/write-fencing work.

The custom code is therefore limited to the irreducible boundary: provider
normalization, exact coverage/currentness semantics, protected R2A composition
and the single bounded projection effect. A future adapter may use either an SDK
or raw provider primitives as long as it satisfies the same internal contract.

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
diagnostic state and no positive-permission claim. A consumed R2A semantic result
is retained as **observed evidence**, but it is not presented as the current
projection result when the provider subject is closed or any required provider
coverage is incomplete. In that state the current projection reports
`NON_CURRENT / UNAVAILABLE / PROVIDER_STATE_INCOMPLETE`; an observed
`PASS|BLOCKED|INCOMPLETE|CONFLICTING` remains nested diagnostic provenance,
not a present semantic verdict.

When the provider subject is known but protected authority/runtime acquisition is
unavailable, the projection retains that subject and explicitly reports
protected status `UNAVAILABLE` rather than aborting the whole reconciliation
or inventing identities.

When PR metadata or comparison acquisition cannot establish the exact subject,
retain an explicit per-PR `UNAVAILABLE / PROVIDER_SUBJECT_UNAVAILABLE` diagnostic
in the bounded payload and job summaries. Do not invent a head SHA or publish a
subjectless advisory. Other selected PRs are still collected, and publication
skips the unavailable entry without making a provider call.

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
