---
type: Decision
title: Add authenticated provider-neutral analyzer readback before critical Q0 activation
description: Normalize authenticated DeepSource and Codacy readback behind one exact-subject, completeness and secret-hygiene contract without granting analyzer write, review or merge authority.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-23T13:05:00Z"
sources:
  - id: deepsource-work-item
    resource: https://github.com/ktogias/gnostoa/issues/309
    title: Add authenticated DeepSource full-report readback before the next critical Q0 activation
  - id: codacy-work-item
    resource: https://github.com/ktogias/gnostoa/issues/313
    title: Add authenticated read-only Codacy PR readback
  - id: owner-paired-scope
    resource: https://github.com/ktogias/gnostoa/issues/309#issuecomment-5779900386
    title: Owner sequencing update — implement Codacy readback together with this DeepSource lane
  - id: active-claim
    resource: https://github.com/ktogias/gnostoa/issues/309#issuecomment-5795242246
    title: Active implementation claim — paired analyzer readback from protected main
  - id: provider-neutral-l1
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
  - id: candidate-preparation
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: Require pre-candidate preparation receipts for non-hook authoring
  - id: deepsource-api
    resource: https://docs.deepsource.com/docs/product/api-and-webhooks
    title: DeepSource API and webhooks
  - id: codacy-api
    resource: https://docs.codacy.com/codacy-api/using-the-codacy-api/
    title: Using the Codacy API
  - id: codacy-cloud-cli
    resource: https://docs.codacy.com/codacy-cloud-cli/
    title: Codacy Cloud CLI
x-project-knowledge:
  id: kit.decision.0091.add-authenticated-provider-neutral-analyzer-readback
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: governed-by
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: governed-by
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
---

# Add authenticated provider-neutral analyzer readback before critical Q0 activation

## Context

GitHub-native check summaries and annotations prove that an analyzer ran, but they
do not reliably expose the complete provider report needed for finding-level
disposition. PR #312 reproduced that visibility gap for both DeepSource and
Codacy while repository CI and GitHub-native checks were otherwise observable.

The owner paired #309 and #313 into one bounded implementation slice. The goal is
one read-only evidence boundary with thin provider adapters, not two analyzer-
specific subsystems and not a new semantic reviewer.

## Prior-art and reuse disposition

Reuse Decision 0086's separation of concerns:

- provider adapters own network/API vocabulary and authentication;
- a common core validates normalized evidence and exact subject identity;
- deterministic reducers and semantic review code receive no provider token.

Do not put analyzer HTTP/GraphQL calls in `tools/review_reconcile.py` or
`tools/review_evaluate.py`. Do not add a provider SDK or the Codacy CLI as a
runtime dependency in this first slice; bounded direct HTTPS clients are enough
for the admitted read-only endpoints.

## Decision

### 1. One implementation-private normalized model

Add an implementation-private `gnostoa-analyzer-readback/v1` model. A retained
readback contains:

- provider and adapter identity;
- repository and change-request identity;
- requested exact 40-character head commit;
- observed exact provider subject and native run/analysis identity;
- normalized scope `DIFF` or `FULL`;
- explicit completeness: `DIFF_LOCAL`, `FULL_RUN`, `AUTH_UNAVAILABLE`,
  `READBACK_UNAVAILABLE` or `AMBIGUOUS`;
- provider-native mode as provenance;
- observation timestamp and run state;
- explicit coverage status, page count and retained count;
- bounded normalized findings with stable provider-native references.

The model does not rank analyzers, infer semantic correctness, approve a
candidate or decide merge readiness.

### 2. Exact-subject binding fails closed

A readback is usable only when the adapter proves that the provider report is for
the requested exact candidate.

For DeepSource, authenticated `FULL_RUN` acquisition selects the run for the
requested exact commit and requires the returned commit identity to equal it.
Run UID, base commit, status and report/check identity remain native provenance.
Missing, mismatched or ambiguous run identity is top-level `AMBIGUOUS` with
`INCOMPLETE` exact-subject coverage, never a clean report.

For Codacy, the adapter reads the requested repository and pull request and must
establish that the provider's PR analysis is bound to the requested exact head.
If the available Codacy response cannot prove that exact binding, the top-level
result is `AMBIGUOUS` with `INCOMPLETE` exact-subject coverage; matching PR
number, repository name or GitHub check state does not substitute for exact-head
proof.

### 3. Preserve DeepSource mode semantics

DeepSource retains the owner-selected distinction:

- `DIFF_LOCAL`: diff-scoped/local evidence, never represented as authenticated
  complete provider-run evidence;
- `FULL_RUN`: authenticated provider readback for the exact DeepSource run.

The common model normalizes scope while preserving the native mode. Consumers
must not silently promote `DIFF_LOCAL` to `FULL_RUN`.

### 4. Completeness and collection coverage are separate, closed dimensions

The top-level `completeness` field preserves the #309 evidence boundary:

- `DIFF_LOCAL` — a bounded GitHub-native/diff projection only;
- `FULL_RUN` — authenticated provider readback whose exact subject and complete
  required pagination are established;
- `AUTH_UNAVAILABLE` — the required credential is missing or rejected;
- `READBACK_UNAVAILABLE` — authenticated/full readback cannot be completed
  because the provider/network/protocol surface is unavailable;
- `AMBIGUOUS` — repository, Pull Request, head, run or analysis association
  cannot be established exactly.

Every retained collection separately records `status`, `pages` and `count`.
Supported collection statuses are `COMPLETE`, `INCOMPLETE`, `PARTIAL`,
`RATE_LIMITED`, `UNAVAILABLE` and `ERROR`, where `INCOMPLETE` denotes an
unproven or mismatched exact-subject collection.

These dimensions are not aliases. In particular:

- `FULL_RUN` requires every required collection to be `COMPLETE`;
- `DIFF_LOCAL` may be `COMPLETE` for the bounded GitHub projection while still
  not claiming complete provider evidence;
- `AUTH_UNAVAILABLE` maps the affected authenticated collection to
  `UNAVAILABLE`;
- `READBACK_UNAVAILABLE` maps to `UNAVAILABLE`, `RATE_LIMITED`, `PARTIAL`
  or `ERROR` according to the measured failure;
- `AMBIGUOUS` requires `INCOMPLETE` exact-subject coverage.

`COMPLETE` collection coverage is valid only when pagination termination and
retained cardinality are both established. Truncation, server pagination that
cannot be completed, rate limiting, malformed payloads, unsupported provider
state or subject ambiguity cannot be represented as zero findings.

The adapters retain provider-reported totals when available and the common core
rejects contradictions between totals, retained findings and coverage claims.

### 5. Findings remain evidence, not semantic verdicts

Normalize only fields needed for bounded disposition:

- stable provider-native finding identity;
- severity/category when supplied;
- rule/check identity and short message;
- repository-relative location/range when supplied;
- current/open/resolved state when supplied;
- provider-native URL/reference;
- exact subject binding inherited from the readback envelope.

Unknown provider fields are not promoted into generic semantics merely because a
provider exposes them. Analyzer-specific metadata stays inside a bounded native
provenance object.

### 6. Authentication and secret hygiene are adapter-local

Tokens enter only through explicit environment variables at execution time.
They are never accepted as CLI arguments, serialized into retained evidence,
included in exception text, request URLs or debug output. The GitHub-hosted live
route stores the provider token values only as secrets of the
`analyzer-readback` GitHub Environment, not as repository or organization
secrets available to arbitrary same-repository workflow refs. That Environment
must admit only the `main` branch through its deployment branch policy before
the live route is enabled.

Adapters use fixed HTTPS origins and reject credential-bearing redirects outside
the admitted provider origin. Authorization headers are attached only after URL
validation. Error bodies are bounded and scrubbed before retention or display.

The first implementation uses the established token names for the provider
accounts already selected by the owner, including `CODACY_API_TOKEN`; the
DeepSource token variable is adapter-private and documented without persisting
its value.

### 7. Read-only authority boundary

This slice may perform authenticated reads only. It does not trigger analysis,
request reviews, post comments, change provider configuration, dismiss findings,
modify Pull Requests, write Git refs or grant lifecycle/merge authority.

Any later provider mutation requires separate admission and Decision coverage.

### 8. One bounded read-only execution surface

The repository-secret-backed live path is one implementation-private runner and
one manual GitHub Actions workflow, not provider-specific workflows.

The runner:

- accepts repository, Pull Request number and exact requested head as ordinary
  non-secret inputs;
- re-reads the GitHub Pull Request before and after provider acquisition and
  refuses to attribute evidence when its head changes;
- reads exact-head GitHub commit statuses, check runs/annotations and inline
  review comments through a read-only GitHub token, retaining DeepSource GitHub
  evidence only when the provider subject and inline `commit_id` bind to the
  requested head;
- uses the uniquely discovered DeepSource run UUID for authenticated
  `FULL_RUN` acquisition;
- invokes the Codacy adapter for the same Pull Request/head and requires a
  stable Codacy subject across issue pagination;
- emits one bounded non-secret bundle of normalized readbacks and checks that
  none of the injected credential values occur in the serialized output before
  it can be retained.

The workflow is `workflow_dispatch` only and grants at most
`contents: read`, `pull-requests: read`, `statuses: read` and `checks: read`.
The credential-bearing job references the `analyzer-readback` GitHub
Environment. Provider configuration must restrict that Environment to the
`main` branch and store `DEEPSOURCE_API_TOKEN` and `CODACY_API_TOKEN` only as
Environment secrets. The job also admits only dispatch ref `refs/heads/main`;
checkout is pinned to that dispatch event's exact `github.sha`, and a
secret-free binding step verifies both the main ref and `HEAD == github.sha`
before any analyzer credential is injected. The provider-level Environment
policy is the non-bypassable secret-admission boundary; the in-workflow checks
are defense in depth because a workflow dispatched from another ref can use the
workflow bytes from that ref. Provider credentials are injected only into the
acquisition step; the GitHub token is likewise read-only. The workflow may
upload only the already validated non-secret readback bundle as an evidence
artifact. It has no provider mutation command, Git write permission or automatic
Pull Request trigger.

This dedicated manual surface is preferred to adding analyzer secrets to the
ordinary verification workflow: analyzer availability must not become a
candidate correctness gate, and fork/PR secret semantics must not alter the
meaning of repository CI.

### 9. Dogfood and Q0 handoff

The first dogfood target is PR #312 because it exercised both analyzer visibility
gaps and has a known exact-head history.

Before the next critical Q0 activation, retain one exact-head readback showing
either:

- complete authenticated provider evidence; or
- an explicit fail-closed limitation that identifies which exact-subject or
  completeness property could not be established.

No Q0 qualification is inferred merely from analyzer availability.

### 10. Candidate preparation remains mandatory

Any Python-affecting implementation candidate under this Decision must pass the
integrated Decision 0090 exact-parent preparation boundary before publication.
The analyzer-readback implementation may consume prepared source, but it cannot
weaken, bypass or replace that boundary.

## Consequences

This adds a small provider-neutral read model and two thin read-only adapters.
It improves finding-level visibility without coupling semantic review to
DeepSource or Codacy and without turning analyzer output into authority.

The cost is explicit provider API maintenance and bounded token handling. Provider
API drift therefore fails closed as incomplete acquisition rather than silently
changing evidence semantics.
