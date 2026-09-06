---
type: Source
title: Work Item 197 preflight authority consumption plan
description: Bounded critical-change plan for making fresh preflight authority single-transaction within one retained workspace without changing the public v2 authority or candidate schemas.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-05T18:45:00Z"
sources:
  - id: replay-work-item
    resource: https://github.com/ktogias/gnostoa/issues/197
    title: Prevent replay of consumed preflight authority across effect-bearing qualification
  - id: owner-gate
    resource: https://github.com/ktogias/gnostoa/issues/197#issuecomment-5553930881
    title: Decision 0059 addendum and focused RED gate
  - id: capsule-decision
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    title: Compile declarative Experiment Capsules over the owner-led runner
x-project-knowledge:
  id: kit.assessment.197.preflight-authority-consumption-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
---

# Work Item 197 preflight authority consumption plan

Starting revision: `8534808e41337b4d1672ac5f991017ff4b7cce78`, tree
`50f1a018c657f6ed40b9d3d1ab5353922dfb6fde`. Branch
`agent/prevent-preflight-authority-replay`.

Classification: `critical`. This document is a plan only. Production implementation
is not admitted by the gate that created it.

## Problem to close

`gnostoa-preflight-authority/v2` binds one exact experiment, scope and
`preflight_candidate_sha256`, but `PreflightAuthority.covers()` is intentionally
stateless. Re-supplying the same authority for the same fresh candidate can therefore
open `qualify_subjects()` again, including after a previous invocation aborted after
its effect path had begun.

The candidate already binds the per-task disposition (`qualification_mode: fresh` or
`reuse`). This plan uses that existing information and does not change the public
preflight-authority or candidate schema.

## Selected durable record

For a candidate with at least one `qualification_mode: fresh`, the retained workspace
owns a separate create-only effect claim:

```text
<workspace>/preflight-effects/<preflight_candidate_sha256>.json
```

Proposed schema discriminator:

```text
gnostoa-preflight-effect-claim/v1
```

The record binds, at minimum:

- schema;
- experiment id;
- scope (`base-reference-qualification`);
- exact `preflight_candidate_sha256`;
- exact authority payload as canonical public-safe data;
- digest of that canonical authority payload;
- candidate disposition summary proving that at least one ordered task is `fresh`.

The filename is keyed by candidate, not authority id. Issuing a second authority for
the same already-consumed candidate therefore cannot reopen it. A legitimate
replacement attempt must produce a new prospective experiment identity and candidate.

The record is independent of `StageLedger`. Stage invalidation, incomplete stage
re-entry or downstream recomputation must never erase or reinterpret an effect claim.

## Atomic create-only write

The later implementation should:

1. recompute the candidate and pass exact `PreflightAuthority.covers()` as today;
2. determine from the already-bound candidate tasks whether any disposition is
   `fresh`;
3. for an all-`reuse` candidate, skip the claim entirely and continue through the
   existing zero-effect receipt-consumption path;
4. for a fresh candidate, create the `preflight-effects` directory if absent, then
   create the exact candidate record with exclusive/create-only semantics;
5. write canonical bytes, flush the file and `fsync` it before returning from the
   claim operation; where supported by the existing portability boundary, sync the
   containing directory so a successful claim is retained across process restart;
6. only after the claim operation has completed successfully may the compiler enter
   any `qualify_subjects()` / runner / hidden-oracle effect.

No overwrite, truncate, rename-over-existing or silent repair is permitted.

A pre-existing non-regular path, malformed record, digest mismatch or I/O ambiguity
fails closed. It is never interpreted as permission to retry.

## Replay refusal codes

Proposed stable blockers:

- `preflight-candidate-already-consumed` — a valid create-only claim already exists
  for the exact fresh candidate;
- `preflight-effect-claim-invalid` — the candidate claim path exists but is malformed,
  non-regular, mismatched or otherwise cannot be trusted;
- `preflight-effect-claim-write-failed` — the compiler cannot establish and durably
  retain the claim before effect.

All three refuse before `qualify_subjects()`, runner/container start or hidden-oracle
execution.

## Exact crash boundary

The safety boundary is deliberately conservative:

```text
exact authority match
→ durable fresh-candidate claim COMPLETE
→ first qualify_subjects() effect may begin
```

A crash after the durable claim but before the hidden oracle actually starts still
consumes that prospective candidate. This may lose an unused attempt, but it cannot
create an unauthorised retry. The slice optimises for fail-closed authority semantics,
not attempt salvage.

A crash/exception after BASE starts likewise leaves the candidate consumed. A later
process must not resume REFERENCE or rerun BASE under the same candidate/authority.
The uninterrupted invocation may execute its preregistered ordered BASE→REFERENCE
sequence and any additional ordered fresh tasks as the one transaction.

This is retained-workspace durability only. Copying the workspace before consumption
or coordinating independent workspaces is outside the claim; no distributed
exactly-once guarantee is asserted.

## Required RED and later GREEN evidence

The focused synthetic characterization must show, before implementation:

1. same exact fresh candidate + same authority currently reaches `qualify_subjects()`
   on two invocations in one retained workspace;
2. an exception after the first effect entry currently permits a later replay;
3. authority-less preparation stays effect-free and replayable;
4. all-`reuse` is a distinct candidate and reaches zero fresh qualification calls.

A later implementation gate must turn only the first two RED cases green while
keeping the two guards green, then add restart/create-only corruption tests around
the retained claim.

## Verification after a later implementation gate

Focused #197 tests first, then the existing candidate-binding, prior-receipt reuse,
stage/resume and experiment-capsule suites; ruff and mypy for the Capsule trust
domain; repository policy/fast/regression/smoke/extended verification according to
the existing network envelope.

## Out of scope

No changes to `gnostoa-preflight-authority/v2`, `gnostoa-preflight-candidate/v1`,
launch authority, Phase-D material, hidden oracle semantics, runner/isolation,
backend equivalence, D0 reuse ordering (#194), distributed locking, release,
publication or deployment.
