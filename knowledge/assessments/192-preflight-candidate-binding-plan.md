---
type: Source
title: Work Item 192 preflight candidate authority binding plan
description: Bounded plan for binding preflight authority to one exact prepared qualification candidate, introducing the v2 authority contract and making the candidate identity observable before any hidden-oracle effect.
status: draft
generated:
  by: claude/opus-5
  at: "2026-09-05T08:40:00Z"
sources:
  - id: binding-work-item
    resource: https://github.com/ktogias/gnostoa/issues/192
    title: Bind preflight authority to an exact prepared qualification candidate
  - id: capsule-decision
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    title: Compile declarative Experiment Capsules over the owner-led runner
x-project-knowledge:
  id: kit.assessment.192-preflight-candidate-binding-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
---

# Work Item 192 preflight candidate authority binding plan

Starting revision: `4e9e08b1e317836b01c97b67843c7580cc5523c0`, tree
`5405d5b9d72479516742175d3f8b60d66dfc9359`. Branch
`agent/bind-preflight-authority-candidate`. Governed by Decision 0059; the change
narrows an existing authority contract rather than widening the experiment model,
so no new Decision is required.

## Why

A preflight authority currently binds an experiment name. `PreflightAuthority`
carries only `id`, `experiment_id` and `scope`, and `covers()` compares only the
last two, immediately before `BASE_REFERENCE_QUALIFIED`. By that point the
compiler already knows the exact qualification backend and the exact prepared
`capsule_identity` of every task, so an authority approved for one prepared
candidate would equally admit a materially different one under the same
experiment id, or the same candidate through a different backend. `LaunchAuthority`
already demonstrates the stricter pattern by binding an exact `lock_sha256`.

## A. Synthetic RED

Two prepared candidates sharing an experiment id but differing in one
qualification-critical input; the same request under both backends; and the
absence of any canonical pre-authority digest an owner could approve. Synthetic
fixtures only, stopping at `STATIC_QUALIFIED`, with no oracle executed.

## B. Preflight candidate identity

A canonical digest over implementation-owned data available once static
qualification is complete: a schema discriminator, experiment id, scope,
qualification backend, and the ordered task to `capsule_identity` mapping. The
order is the actual qualification order, which is spec order, because that is the
request being authorised; #192 does not change execution order to simplify
hashing. Nothing caller-supplied and no oracle, key or credential material enters
the payload.

## C. Authority v2

`gnostoa-preflight-authority/v2` additionally binds `preflight_candidate_sha256`,
and `covers()` compares the implementation-computed identity exactly. Per
repository compatibility guidance a breaking contract takes a new major path, so
v1 is not reinterpreted: it stays readable where historical evidence needs it, and
is refused as authority for a new preflight effect. No auto-upgrade, no derived
digest on a legacy object's behalf, and a missing digest is never a wildcard.

## D. Observability before authority

An authority-less `prepare` that reaches `STATIC_QUALIFIED` computes and exposes
the candidate digest in public-safe state and status output before returning
`base-reference-qualification-requires-preflight-authority`, so the owner approves
an exact prepared candidate rather than reconstructing a hash. It is emitted only
when a well-defined candidate exists, never as a placeholder behind earlier
blockers.

## E. Stage evidence

`BASE_REFERENCE_QUALIFIED` retains the implementation-computed candidate identity,
the authority object, the backend and the capsule identities, so evidence can later
show what was authorised against what executed. The stage records the computed
digest independently and proves equality rather than trusting the authority's copy.

## F. Verification

Focused #192 tests plus the full capsule and integration-repair suites, launch
authority, prior-qualification reuse and stage/resume tests, ruff, mypy, and the
repository verification suites. A mismatched authority must reach zero calls to
any hidden-oracle execution path, refused at `STATIC_QUALIFIED`. D0-style receipt
reuse must remain possible with zero fresh executions, proven synthetically.

## G. One draft PR

Then stop. Merge is not authorised by this slice.

## Out of scope

Any Phase-D hidden material or execution; D1 and D3 attempt accounting is
unchanged. Launch authority semantics, runner authority, network authority and
capability certificates are untouched, and no general authorisation framework is
introduced. #189 keeps the unrelated OCI adapter/backend documentation gap.
