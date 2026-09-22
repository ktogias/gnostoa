---
type: Source
title: Q0 protected reviewer qualification execution plan
description: Verification-first plan for replacing the empty protected R2A qualification snapshot with two source-bound reviewer/source entries.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-22T07:33:00Z"
sources:
  - id: decision
    resource: ../decisions/0088-establish-source-bound-protected-reviewer-qualification.md
    title: Decision 0088
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5773362664
    title: Q0 owner admission
---

# Q0 protected reviewer qualification execution plan

## Bounded target

Produce one protected qualification snapshot with two established repository-scoped entries and preserve every existing R2A recommendation/quorum rule.

## Behavior map

| ID | Required behavior | RED/GREEN evidence |
| --- | --- | --- |
| Q0-01 | Protected authority accepts non-empty v1 qualification entries with the same shape already accepted by `review-check`. | Schema/bundle test fails before widening the empty-only protected schema and passes after. |
| Q0-02 | Only exact `(reviewer_id, source_id)` identities can qualify. | Existing evaluator duplicate/forged-claim regressions remain green; protected bundle pins exact identities. |
| Q0-03 | Two source-principal domains are distinct without claiming perspective/model independence. | Snapshot entry assertions plus provenance/limitation checks. |
| Q0-04 | Durable protected qualification is not forced to expire every 24h. | Effective project critical policy resolves `snapshot_freshness=not_age_sensitive`; subject/collection freshness remain unchanged. |
| Q0-05 | Policy and qualification are cryptographically bound. | Canonical policy and qualification digests equal the authority fields. |
| Q0-06 | Qualification does not manufacture approval. | Policy still requires `APPROVE`; no adapter/provider-prose normalization changes. |
| Q0-07 | Revoked/unestablished, malformed or duplicate qualification state remains fail-closed. | Existing R2A regressions plus focused protected-bundle schema mutations. |

## Sequence

1. Add focused RED tests against the current empty-only protected bundle.
2. Widen the protected bundle schema to the existing qualification-entry contract.
3. Specialize Gnostoa project qualification snapshot freshness as durable, without changing quorum or acceptable recommendations.
4. Replace the empty snapshot with exactly the two admitted entries and update canonical digests.
5. Reconcile the existing P2b authority tests to the new Q0 source-bound baseline.
6. Run policy, focused review-assurance tests, fast/regression/extended/smoke and protected-current-advisory verification.
7. Obtain fresh semantic review on the exact Q0 candidate.
8. Merge only through a separate accountable-owner authorization.
9. After integration, rebind PR #297 to protected main and read back R2A. Do not assume qualification alone creates PASS.
