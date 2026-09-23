---
type: Decision
title: Normalize authenticated analyzer readback behind one provider-neutral evidence contract
description: Add exact-subject, completeness-aware, read-only analyzer evidence with thin DeepSource and Codacy adapters while keeping analyzer findings outside semantic-review authority.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-23T13:12:39Z"
sources:
  - id: deepsource-work-item
    resource: https://github.com/ktogias/gnostoa/issues/309
    title: Add authenticated DeepSource full-report readback before the next critical Q0 activation
  - id: codacy-work-item
    resource: https://github.com/ktogias/gnostoa/issues/313
    title: Add authenticated read-only Codacy PR readback
  - id: paired-admission
    resource: https://github.com/ktogias/gnostoa/issues/309#issuecomment-5779900386
    title: Owner sequencing update — implement Codacy readback together with this DeepSource lane
  - id: active-claim
    resource: https://github.com/ktogias/gnostoa/issues/309#issuecomment-5795242246
    title: Active implementation claim — paired analyzer readback from protected main
  - id: deepsource-api
    resource: https://docs.deepsource.com/docs/developers/api
    title: DeepSource GraphQL API
  - id: codacy-api
    resource: https://docs.codacy.com/codacy-api/using-the-codacy-api/
    title: Codacy API v3
  - id: sarif
    resource: https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html
    title: SARIF 2.1.0
x-project-knowledge:
  id: kit.decision.0091.normalize-authenticated-analyzer-readback
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: governed-by
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
---

# Normalize authenticated analyzer readback behind one provider-neutral evidence contract

## Context

Gnostoa currently sees only provider projections of static-analysis results. For
DeepSource, GitHub commit statuses expose analyzer state and a run UUID, while
inline review comments expose only findings that the provider can project into
the Pull Request diff. DeepSource documents a GraphQL API that can read
repositories, analysis runs and issues with PAT authentication. For Codacy, the
GitHub projection can contain check annotations whose bodies are not available
through the current GitHub connector; Codacy documents API v3 and cursor-based
pagination, plus Pull Request analysis and annotated-diff surfaces.

The two gaps are the same architectural problem: a Git-provider projection is
useful partial evidence but cannot by itself establish that the analyzer's
complete result set was read. Treating a green status, visible inline comments,
or an annotation count as a complete report would collapse observation
availability into semantic success.

The owner therefore paired #309 and #313 into one implementation slice after
PR #312 / #262. This Decision governs that shared slice.

## Prior-art and reuse disposition

Three established mechanisms were evaluated.

1. **Provider-native APIs.** DeepSource's supported GraphQL API is the authority
   for authenticated DeepSource run/issues readback. Codacy API v3 is the
   preferred Codacy authority and already defines token authentication and
   cursor pagination. Reuse these supported read surfaces rather than scrape Web
   UI HTML.
2. **SARIF 2.1.0.** SARIF provides useful analyzer-result vocabulary such as
   stable rule identity, locations and fingerprints. It does not define this
   workflow's exact repository/PR/head binding, provider-analysis identity,
   authentication availability or the distinction between a GitHub-local
   projection and a fully paginated provider read. Gnostoa therefore reuses
   SARIF concepts where useful but does not make SARIF the control envelope.
3. **Existing Gnostoa review evidence.** The review-assurance model has stronger
   semantic-review and qualification semantics than static analyzers require.
   Reusing it directly would incorrectly grant analyzer observations reviewer
   meaning. The new model remains a separate analyzer-evidence lane that later
   planners may consume as repair evidence only.

No new third-party Python dependency is selected. The bounded implementation
should prefer Python's standard HTTP/JSON facilities and provider-specific
parsers behind one small provider-neutral model. A provider CLI may be used only
as an execution alternative when its exact version and read-only command surface
are separately bound; it is not required by this Decision.

## Decision

### 1. One closed provider-neutral read model

Introduce one implementation-private analyzer-readback model with a versioned
schema identifier. A readback binds:

- provider;
- repository identity;
- Pull Request number when applicable;
- exact 40-character head commit;
- provider analysis/run identity when the provider exposes one;
- analyzer/tool identity and analyzer state;
- explicit completeness/availability state;
- observed/readback timestamp;
- normalized issues.

Each normalized issue retains the provider-native issue identity whenever one
exists, severity/category, path/range when available, title/message, source
identity/URL and the provenance surface that observed it.

Provider-native identity is the deduplication authority. Path/message similarity
must never merge distinct provider issues.

### 2. Completeness is explicit and closed

The common vocabulary is:

- `DIFF_LOCAL`: bounded GitHub-native projection only;
- `FULL_RUN`: the authenticated provider read completed all required surfaces
  and pagination for the exact subject;
- `READBACK_UNAVAILABLE`: the provider route was requested but could not be
  completed for a non-authentication reason;
- `AUTH_UNAVAILABLE`: required credential material is absent or authentication
  is rejected;
- `AMBIGUOUS`: exact repository/PR/head/run association cannot be established.

A partial or failed route cannot default to an empty successful result. An empty
issue list is meaningful only when its completeness state truthfully describes
how that list was obtained.

### 3. Exact-subject binding precedes issue acceptance

Every accepted result must bind the requested repository and exact head. When a
provider exposes a run/analysis identity, that identity must be reconciled to the
same subject before its issues enter the normalized model.

Stale predecessor data, mutable Pull Request summaries, or a provider result
whose head cannot be proved exact is `AMBIGUOUS`, not evidence for a successor
candidate.

Historical observations remain historical. In particular, PR #312's Codacy
projection changed across heads (eight annotations at initial capture, four at
an intermediate head, and zero new issues at the final accepted head). The
implementation must not relabel earlier findings as current; live dogfood either
reads a retained historical exact subject or uses the exact current subject and
records its actual result.

### 4. DeepSource adapter

The DeepSource adapter:

1. obtains GitHub-native `DeepSource: *` statuses for the exact head and parses
   the common run UUID plus analyzer identities;
2. can normalize visible DeepSource bot/inline observations as
   `DIFF_LOCAL`;
3. for authenticated readback, receives `DEEPSOURCE_API_TOKEN` only through the
   execution environment and sends it as a Bearer header to the supported
   GraphQL endpoint;
4. uses the GitHub-discovered run UUID as the preferred join identity;
5. follows provider pagination to completion for every required analyzer/issue
   surface;
6. emits `FULL_RUN` only after exact-subject association and complete pagination
   are established.

The reader exposes no mutation, Autofix, review-dispatch or lifecycle operation.

### 5. Codacy adapter

The Codacy adapter:

1. receives `CODACY_API_TOKEN` only through the execution environment and uses
   the documented account-token header;
2. reads the supported Codacy API v3 Pull Request/analysis and issue surfaces for
   the repository and PR;
3. validates the provider-reported head/commit association before accepting
   issue evidence;
4. exhausts cursor pagination when the selected endpoint is paginated;
5. normalizes issue details through the same common model;
6. emits a complete state only for the exact subject actually read.

The implementation must use read-only endpoints/commands. Ignore, reanalysis,
Autofix, configuration and other mutation capabilities are outside this
adapter even when the provider API or CLI offers them.

### 6. Secret and transport boundary

Credential values are never accepted as CLI arguments, serialized into receipts,
fixtures, comments, logs or artifacts, or returned in exception text. Adapters
read only the stable environment-variable names selected by the Work Items.

HTTP failures retain bounded non-secret diagnostics. Request construction,
headers and response parsing stay provider-specific; generic model/reducer code
never branches on provider brand.

No GitHub write permission is required by the analyzer reader itself.

### 7. Analyzer evidence is not semantic-review authority

Analyzer readback can inform repair planning and quality evidence. It does not
create reviewer qualification, independence, R2A quorum, semantic convergence,
owner approval, review recommendation or merge authority.

The generic #15 orchestration layer may later consume this model, but it must not
reinterpret `FULL_RUN` as semantic acceptance.

### 8. Verification-first implementation

Before production Python is changed, retain a RED/characterization record that
demonstrates:

- exact-head DeepSource status/run discovery exists while full issue
  completeness is not derivable from GitHub alone;
- Codacy Pull Request projections can report issue/annotation state not available
  as issue bodies through the current GitHub read surface;
- stale-head evidence is distinguishable from the requested exact head.

Then add focused tests for:

- provider-neutral model validation;
- `DIFF_LOCAL` versus `FULL_RUN` non-promotion;
- DeepSource exact run joining and pagination;
- Codacy exact PR/head joining and cursor pagination;
- duplicate collapse by provider-native identity with provenance retention;
- explicit auth/network/ambiguous states;
- secret redaction/non-serialization;
- synthetic third-provider normalization proving no provider branch exists in
  generic semantics.

Any Python-affecting candidate must pass Decision 0090 preparation against its
exact parent before a Git ref is updated.

## Consequences

- Gnostoa can distinguish a complete authenticated analyzer observation from the
  subset visible through GitHub.
- DeepSource and Codacy share one control contract without sharing
  provider-specific request/response parsing.
- Static-analyzer evidence remains deliberately weaker than semantic-review
  evidence.
- Provider API evolution is isolated to adapters.
- Service or credential outages remain truthful unavailable states instead of
  false clean reports.
- The first live dogfood may show fewer findings than historical #312 captures;
  exact-subject truth takes precedence over reproducing an old count.

## Non-goals

- analyzer Autofix, ignore or reanalysis;
- semantic review or reviewer qualification;
- provider write authority;
- a generic secret manager;
- Web-UI scraping;
- a general workflow engine;
- replacing SARIF or provider-native identities with message-based heuristics.
