---
type: Decision
title: Protect the R2A B1 outer-consumer authority separately from the inner semantic authority
description: Bind the immutable R2A P2b-B1 outer consumer through a separate protected authority record while preserving the closed v1 inner semantic authority consumed by prior-effective B1.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-14T14:18:00Z"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: b1-materialization
    resource: ./0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md
    title: Decision 0069
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: b1-materialization-receipt
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5664611991
    title: Successful immutable OCI(B1) materialization receipt
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5663169718
    title: Owner authorization for intermediate protected authority and B2 convergence steps
x-project-knowledge:
  id: kit.decision.0070.protect-r2a-b1-outer-consumer-authority-separately
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Protect the R2A B1 outer-consumer authority separately from the inner semantic authority

## Context

Decision 0067 requires current-advisory trust and final result provenance to come from prior-effective evidence rather than candidate-controlled bytes. Decision 0069 therefore materialized the already integrated dormant P2b-B1 outer consumer as an immutable digest-only OCI identity before any live activation.

That materialization completed successfully. The selected outer consumer is exactly:

`ghcr.io/ktogias/gnostoa@sha256:fcefee5af6deb089e4b1cbe09e1a0d2f4820a56ac0a6be18faa4dd11b2ab01b0`

Its source revision is `0dfd7e5e28e8ccb87e687e0be9dfe846b644c9c3`, its source tree is `23a5f083f26f40a8287bc2a724bcd5282a9afa5e`, and its public-surface digest is `sha256:72df7bfe999db7c84c199ff26424a434197865aaf95b3a5ae9e4e1026d8f5d45`.

The immutable B1 runtime was built while the existing protected semantic authority had a closed v1 shape. B1 reacquires `tasks/issue-11-r2a-current-advisory.json` from protected `main` and validates that inner semantic authority according to the v1 implementation it already contains. Adding outer-consumer fields to that existing record would make the selected prior-effective B1 runtime reject its own protected input. It would also collapse two different trust roles: the inner semantic judge and the outer consumer that acquires authority, selects the trusted cut, invokes semantic evaluation and projects the final live result.

## Decision

Keep the two authorities separate.

1. The existing `tasks/issue-11-r2a-current-advisory.json` remains the **inner semantic authority**. Its closed v1 shape remains consumer-free and continues to bind the prior-integrated OCI(P2a) semantic judge, policy and qualification snapshot.
2. Add a distinct protected outer-consumer record at `tasks/issue-11-r2a-current-advisory-consumer.json`, validated by the closed schema `schemas/review-protected-consumer-authority.schema.json`.
3. The outer record SHALL bind both `expected_consumer` and `acquired_consumer` to the exact immutable OCI(B1) identity above, including source revision, source tree, public-surface digest, runtime revision and the successful materialization provenance.
4. The dedicated R2A exact-head workflow SHALL trigger on changes to the protected outer-consumer record and SHALL execute the focused consumer-authority contract so that protected identity changes cannot bypass the trust-domain verification lane.
5. The `semantic-review-assurance` guardrail SHALL declare the outer-consumer schema, protected record, this Decision and the focused contract test as governed implementation/evidence surfaces.
6. P2b-B2 may later consume this outer-consumer authority only after this record itself has become protected/prior-effective on `main`.

This Decision **does not activate P2b-B2**. The candidate CLI remains dormant until a separately verified activation slice routes untrusted current-advisory input through the prior-effective outer consumer.

## Why not extend the existing authority bundle?

The closed v1 inner semantic bundle is part of the contract that OCI(B1) already knows how to read. Mutating its shape at the same time as selecting B1 would create an incompatibility between the selected prior-effective runtime and its own protected authority input. More importantly, inner semantic authority and outer result-provenance authority answer different questions and should not be conflated merely to avoid a second record.

The separate record therefore preserves backward compatibility with the prior-effective B1 runtime and keeps the trust chain explicit:

`protected inner semantic authority -> OCI(P2a) judge`

`protected outer-consumer authority -> OCI(B1) outer consumer`

The later P2b-B2 activation can require both relationships without letting candidate-controlled bytes invent either one.

## Consequences

- OCI(B1) can become prior-effective without changing the closed v1 semantic authority it already validates.
- Reviewers can inspect inner semantic judge authority and outer final-result provenance authority independently.
- Changes to the outer protected identity receive dedicated exact-head workflow coverage and declared policy traceability.
- The immutable B1 materialization receipt remains evidence; this authority landing does not republish or mutate that OCI artifact.
- The truthful Issue #10 qualification state remains empty. This Decision creates no qualified reviewer domain and does not turn `INCOMPLETE / QUORUM_UNMET` into PASS.
- All R2A results remain advisory and `binding:false`; merge authority remains human/accountable-owner controlled.

## Non-goals

This Decision does not activate P2b-B2, does not change the inner OCI(P2a) judge, semantic policy, qualification snapshot or closed v1 semantic authority, and creates no release, deployment, mutable OCI tag, provider-setting mutation, #15 workflow effect, semantic PASS or merge authority.
