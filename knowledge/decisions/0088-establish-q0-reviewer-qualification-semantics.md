---
type: Decision
title: Establish Q0 reviewer qualification semantics and stage protected activation behind a prior-integrated runtime
description: Define the first Gnostoa-self reviewer qualification and independence-domain baseline, while keeping the live protected qualification snapshot empty until a prior-integrated current-advisory runtime can validate non-empty entries.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-22T05:57:03Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/10
    title: Define provider-neutral work phases, actor roles and capability profiles
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5771806967
    title: Owner admission — Q0 reviewer qualification and independence baseline
  - id: negative-snapshot
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5659481721
    title: Protected empty qualification snapshot checkpoint
  - id: q0-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5706402207
    title: Q0 reviewer qualification, perspective coverage and currentness checkpoint
  - id: r2a
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Evaluate semantic review assurance through bound evidence and an advisory deterministic gate
  - id: protected-runtime
    resource: ./0085-promote-current-advisory-restoration-runtime.md
    title: Promote the exact restoration runtime into protected current-advisory transport authority
  - id: q0-baseline
    resource: ../assessments/10-q0-reviewer-qualification-baseline.json
    title: Q0 reviewer qualification candidate baseline
  - id: pr297-coderabbit
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765178931
    title: CodeRabbit exact-head semantic review activity
  - id: pr297-gitar
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5771584848
    title: Gitar semantic review activity
x-project-knowledge:
  id: kit.decision.0088.establish-q0-reviewer-qualification-semantics
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: references
      target: /decisions/0085-promote-current-advisory-restoration-runtime.md
    - kind: references
      target: /assessments/10-q0-reviewer-qualification-baseline.md
---

# Establish Q0 reviewer qualification semantics and stage protected activation behind a prior-integrated runtime

## Context

Protected R2A already evaluates qualification entries, but Gnostoa-self deliberately
landed an empty protected snapshot. That was correct while no reviewer/source had
an authority-backed `semantic-review` capability and independence domain.

PR #297 exposed the operational consequence: many useful external reviews can
exist while protected assurance remains `INCOMPLETE / QUORUM_UNMET`. Counting
reviewers, provider brands, model names or agreement would manufacture quorum and
is therefore forbidden.

Q0 is now explicitly admitted by the accountable owner. The first implementation
must establish auditable qualification meaning without weakening the existing R2A
gate or allowing candidate-controlled authority bootstrap.

## Decision

### 1. Qualification and availability remain separate

A qualification assertion answers whether a reviewer/source identity is established
for a capability and an independence domain within a declared scope. It does not
say that the provider is currently available, within quota, eligible for one
candidate, or able to produce an acceptable recommendation now.

Volatile availability, quota, subject eligibility and route activation remain #15
current-readback concerns.

### 2. Gnostoa-self independence domains use an authenticated reviewer-execution boundary

For this initial repository profile, one independence domain is established only
when all of these are source-bound:

- a distinct authenticated non-owner reviewer principal;
- provider-controlled review execution separate from the accountable owner;
- a read-only semantic-review role for the qualifying evidence;
- attributable exact-head review behavior.

The domain identifies the reviewer execution/source boundary. It does **not** claim
that internal model families, prompts, training data or runtime implementations are
different. Unknown model/runtime diversity is retained as an explicit limitation.

A provider name or model label alone grants no domain. If later evidence shows that
two qualified identities are controlled by one authority/execution boundary in a
way that defeats the selected independence property, their qualification must be
superseded or revoked.

### 3. Initial candidate cohort

The first candidate repository-scoped cohort is:

- `coderabbitai[bot]` / `retained-review-evidence` /
  `github-app:coderabbitai`;
- `gitar-bot[bot]` / `retained-review-evidence` /
  `github-app:gitar-bot`.

Both are `non_owner`, require `semantic-review`, and retain source evidence plus
the limitation `model-runtime-diversity-unestablished`.

A later source read-back found that both current formal GitHub review surfaces are
`COMMENTED`, which R2A correctly normalizes to `COMMENT_ONLY`. Bito has repeatedly
emitted actual GitHub `APPROVED` reviews and is therefore retained as approval-capable
source evidence, but it is **not added to this admitted qualification snapshot**.
Qualification and recommendation eligibility are conjunctive: CodeRabbit/Gitar are
candidate-qualified but their observed recommendation is not quorum-acceptable, while
Bito's observed recommendation is quorum-acceptable but Bito is not candidate-qualified.
None of those observed surfaces therefore advances protected quorum at this stage.
Qualification authority must not expand merely because a useful provider was
discovered during implementation. A separate admitted update is required before Bito
or another reviewer/source becomes an established qualification entry.

This is a qualification candidate, not yet active protected R2A authority.

### 4. Qualification currentness is explicit, not a daily rewrite requirement

The selected Q0 semantics are that repository qualification assertions are slowly
changing authority facts. Once activated, their target freshness mode is
`not_age_sensitive`; currentness is instead changed by explicit supersession,
revocation or contradiction.

This does not make provider availability timeless. Current provider availability
and exact-subject eligibility still require the applicable #15 read-back.

Revocation or supersession is required when, for example:

- the authenticated reviewer/source identity changes materially;
- owner relation changes;
- the review path becomes candidate-writing for the evidence being counted;
- the selected independence boundary is contradicted;
- the source can no longer provide the declared semantic-review capability;
- the repository scope no longer applies.

### 5. Owner reviews remain excluded and quorum semantics are unchanged

Q0 does not change:

- `owner_reviews_count: false`;
- required capability `semantic-review`;
- `minimum_distinct_domains: 2`;
- acceptable recommendation `APPROVE`;
- R2A recommendation normalization;
- merge, provider-write or approval authority.

A qualified reviewer that produces `COMMENT_ONLY`, `ABSTAIN`, stale evidence or
a non-exact subject still does not advance quorum.

### 6. Protected activation is staged behind prior-integrated runtime support

The currently promoted outer current-advisory runtime is the revision named by
the protected bundle's `authority.expected_judge.source_revision`. Its embedded
protected-bundle schema requires `qualification_snapshot.entries.maxItems = 0`.
Q0a records that authority path instead of copying the current Git revision into
candidate-owned data.

Therefore this Q0a source slice must **not** mutate the live protected qualification
snapshot. Doing so would make the prior-integrated runtime reject protected
authority before R2A evaluation.

The safe sequence is:

1. Q0a adds the closed non-empty qualification-entry shape, candidate baseline,
   semantics and tests while leaving the live protected bundle empty.
2. Q0a is integrated only after exact-head verification/review and owner merge
   authorization.
3. A separately authorized publication/qualification/promotion sequence creates a
   new prior-integrated outer runtime containing Q0a support.
4. Q0b updates the protected bundle and critical qualification-currentness policy
   to the admitted snapshot and re-runs protected R2A.
5. PR #297 then reconciles against the new protected main and collects acceptable
   exact-head review evidence.

Candidate bytes never select themselves as the protected consumer that legitimizes
their own authority change.

### 7. Route bindings are prepared but not activated

The candidate baseline records planned bindings from the stable PR #297 route
identities to the two Q0 reviewer/source identities. They remain
`pending_pr297_registry_integration` until both the reviewer registry and the
protected qualification authority are integrated.

The planner may not treat these candidate bindings as protected facts.

## Consequences

- The current live protected snapshot remains truthfully empty during Q0a.
- The source tree becomes capable of validating the normalized non-empty protected
  qualification shape for a future prior-integrated runtime.
- Q0 obtains an explicit, auditable independence definition without claiming model
  diversity.
- Qualification does not become an availability cache.
- PR #297 remains blocked until the later protected activation and acceptable
  exact-head R2A evidence exist.
- Runtime publication/promotion and Q0b protected-authority mutation remain separate
  effect/authority boundaries.

## Rejected alternatives

### Count provider brands or review agreement

Rejected. Brand diversity and agreement do not establish the selected independence
property.

### Mark the accountable owner as a quorum reviewer

Rejected. The existing policy explicitly excludes owner reviews from automated
domain quorum.

### Change acceptable recommendations to include COMMENTED/COMMENT_ONLY

Rejected. That would weaken review assurance to fit current bot behavior instead of
qualifying evidence under the existing semantics.

### Update the live protected bundle in Q0a

Rejected. The currently promoted prior-integrated runtime cannot validate non-empty
qualification entries and would fail closed.

### Let the candidate runtime validate its own protected authority

Rejected as a trust bootstrap. Protected authority must be consumed by a
prior-integrated runtime.

## Verification

Q0a must demonstrate:

- the protected-bundle source schema accepts a normalized non-empty qualification
  snapshot and rejects malformed/unknown qualification fields;
- the live protected bundle remains empty and byte/semantic-compatible with the
  currently promoted outer runtime;
- the candidate baseline contains exactly the admitted two-domain cohort and
  source-bound limitations;
- existing P2b protected-main acquisition and R2A semantics remain unchanged;
- repository verification and fresh exact-head review converge before any
  integration decision.

Q0b and runtime promotion require their own separately admitted verification and
effect receipts.
