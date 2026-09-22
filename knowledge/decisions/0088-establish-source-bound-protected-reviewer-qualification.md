---
type: Decision
title: Establish a source-bound protected reviewer qualification baseline
description: Replace Gnostoa-self's intentionally empty R2A qualification snapshot with a bounded, evidence-backed source-principal qualification baseline without weakening semantic quorum.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-22T07:33:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/10
    title: Define provider-neutral work phases, actor roles and capability profiles
  - id: negative-snapshot
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5659481721
    title: Empty protected qualification snapshot
  - id: q0-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5706402207
    title: Q0 reviewer qualification and currentness checkpoint
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5773362664
    title: Owner admission for Q0 protected reviewer qualification
  - id: qodo-evidence
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765884271
    title: Qodo semantic review evidence
  - id: coderabbit-evidence
    resource: https://github.com/ktogias/gnostoa/pull/297#issuecomment-5765178931
    title: CodeRabbit semantic review evidence
---

# Decision 0088 — Establish a source-bound protected reviewer qualification baseline

## Context

The protected R2A authority intentionally landed with an empty qualification snapshot. That was correct when no source-bound reviewer capability or independence facts existed, but it makes every required-review change remain `INCOMPLETE / QUORUM_UNMET` regardless of how many external reviews are collected.

Q0 now has explicit owner admission to establish the smallest evidence-backed qualification baseline. This decision does not treat provider count, provider brand, model labels, agreement, or a role name as independence.

## Decision

1. Establish exactly two initial repository-scoped qualification entries:
   - `coderabbitai[bot]` through `retained-review-evidence`;
   - `qodo-code-review[bot]` through `retained-review-evidence`.
2. Each entry carries capability `semantic-review`, `owner_relation=non_owner`, explicit provenance and one distinct source-principal independence domain.
3. The independence claim is deliberately narrow: the two entries are independent at the authenticated external source-principal/provider-operated review boundary. It does **not** assert distinct underlying models, hidden contexts, methods, or orthogonal semantic perspectives.
4. Qualification remains separate from recommendation semantics. A qualified `COMMENTED` observation does not become `APPROVE`; the effective policy continues to require acceptable recommendation `APPROVE`.
5. Gnostoa-self's protected qualification assertion is durable until superseded or revoked. Project policy therefore changes qualification `snapshot_freshness` to `not_age_sensitive`. This does not relax subject freshness, review-collection freshness, provider availability, exact-head binding, or evidence freshness.
6. The protected authority-bundle validation is widened only from an empty qualification array to the already existing R2A v1 qualification-entry shape. The R2A input schema remains `1.0`, the protected authority subject remains `tasks/issue-11-r2a-current-advisory.json:v1`, and the prior-integrated judge/runtime contract is not version-skipped.
7. Qualification is fail-closed: duplicate reviewer/source identities, missing fields, malformed timestamps, wrong capability/scope/owner relation, digest mismatch, revoked/unestablished entries, or insufficient distinct domains remain non-qualifying under the existing evaluator.
8. This change grants no provider-write, reviewer-trigger, approval, integration, release or merge authority.

## Consequences

The empty-snapshot blocker can be removed for evidence emitted by the two exact reviewer/source identities. R2A may still truthfully remain `INCOMPLETE / QUORUM_UNMET` when current exact-head evidence lacks acceptable recommendations. Q0 does not parse provider prose into semantic approval and does not guarantee PR #297 will become merge-ready.

Future Q0 work may add or revoke entries only through another source-bound protected-authority change. Perspective-specific qualification, if required by future risk policy, is a separate semantic expansion.
