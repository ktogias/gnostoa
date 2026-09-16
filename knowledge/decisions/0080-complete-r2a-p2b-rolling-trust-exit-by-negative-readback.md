---
type: Decision
title: Complete the R2A P2b rolling-trust exit through a subsequent-candidate negative read-back
description: Require the first candidate after OCI(P2b) authority promotion to bind protected-main read-back to its provider base and prove that neither candidate-controlled nor stale B1.x runtime can become the selected outer consumer.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-09-16T21:26:00Z"
sources:
  - id: p2b-authority-promotion
    resource: ./0079-promote-r2a-p2b-outer-consumer-authority.md
    title: Decision 0079
  - id: rolling-trust-exit
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5680382022
    title: P2b rolling-trust exit boundary
  - id: promotion-owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5704650601
    title: Human owner authorization for exact PR 268 promotion
  - id: integrated-promotion-and-readback
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5704761785
    title: Integrated promotion reconciliation and final read-back admission
  - id: pre-implementation-red
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5704810584
    title: Final P2b-exit pre-implementation RED
x-project-knowledge:
  id: kit.decision.0080.complete-r2a-p2b-rolling-trust-exit-by-negative-readback
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0079-promote-r2a-p2b-outer-consumer-authority.md
    - kind: governed-by
      target: /decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md
---

# Complete the R2A P2b rolling-trust exit through a subsequent-candidate negative read-back

## Context

Decision 0077 activated P2b-B2 through the already prior-effective OCI(B1.6)
outer consumer. Decision 0078 then materialized exact integrated P2b as a
digest-only OCI identity. Decision 0079 promoted that immutable identity into
the protected outer-consumer authority, separately from both materialization
and the later observation that must consume the promoted record.

PR #268 integrated the promotion on protected `main` as commit
`21e4ada5e849b70d5349029f1fa3424fe9fa2fd0`, with the exact reviewed tree
`7f65b7c08a352f696eef3b8a7d6352e8a621e7bf`. Protected read-back now binds:

- source and runtime revision
  `2aa1ed3217c42819155b8ff36385b000720ba4f8`;
- source tree `4cda4e4a704cb518f56201423e313d4dd9db5e24`;
- public-surface digest
  `sha256:b69f11e1efe181f959a14310fed0a35d3533114d734de584790a85cba7bdb565`;
- OCI runtime
  `ghcr.io/ktogias/gnostoa@sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281`.

[Integrated-main workflow run `35151620363`](https://github.com/ktogias/gnostoa/actions/runs/35151620363),
attempt 1, succeeded after that landing. Provider logs have provider-defined
retention and may later become unavailable; the durable claim remains bounded
by the protected promotion commit and tree, the authority record, Decision
0079, and the issue #11 receipts cited above. The exit boundary in issue #11
comment `5680382022` still requires a **subsequent candidate** to prove that
this promoted identity, rather than a candidate-controlled runtime or stale
B1.x authority, is the effective outer consumer.

The historical stale identity used for the negative control is exact OCI(B1.6):

`ghcr.io/ktogias/gnostoa@sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867`

## Prior-art and reuse disposition

The residual proof needs no new selector, runtime, dependency, service or
artifact. `tools/review_protected.py` already acquires the protected record from
the fixed public Gnostoa repository, fixed `main` ref and fixed authority path.
`tools/review_outer.py` already validates that record, reacquires its digest,
checks runtime and public-surface identity, constructs the isolated nested-daemon
plan and executes the selected outer runtime. `ci/review_outer_smoke.py` already
exercises that real path in the dedicated provider workflow.

Compose those mechanisms. Bind the live acquisition to the provider-supplied
Pull Request base SHA, place candidate-local B1.6 authority bytes and the
candidate runtime selector in scope as negative controls, instrument the
existing plan builder without replacing it, and retain the selected immutable
identity in provider logs. Python standard-library mocking is sufficient for
the bounded instrumentation. No external implementation is copied and no new
licence, attribution, distribution or NOTICE obligation is introduced.

Republishing P2b would violate the one-shot boundary and would not prove
selection. Changing the authority record again would destroy the required
temporal separation. Teaching the closed schema that every historical B1.x
record is intrinsically invalid would conflate protected current selection with
historical provenance and is not selected.

## Decision

Complete the rolling-trust proof with one separate, read-only candidate.

1. Acquire `tasks/issue-11-r2a-current-advisory-consumer.json` through the
   existing fixed protected-main Git route. Require the acquired protected-main
   revision to equal the exact base SHA supplied by the provider Pull Request
   event. Drift is a blocker, not an implicit retarget.
2. Require `expected_consumer == acquired_consumer` and require the complete
   selected source/tree/public-surface/runtime tuple to equal exact promoted
   OCI(P2b).
3. Before acquisition, expose candidate-local authority bytes selecting exact
   historical OCI(B1.6) and expose the ordinary candidate runtime selector.
   The protected acquisition must still return the exact promoted P2b record.
4. Reuse the acquired immutable record for the real live smoke, avoiding a
   second time-of-check/time-of-use fetch. Instrument the existing isolated
   execution-plan builder and require its actual outer image to be exact
   OCI(P2b), with neither the candidate image nor OCI(B1.6) present in the
   selected plan.
5. Preserve the existing runtime proof: exact digest reacquisition, OCI label,
   uid/gid and public-surface checks, isolated nested daemon, canonical live
   result, protected OCI provenance diagnostic, cleanup and fail-closed error
   handling all continue to execute.
6. Emit a bounded machine-readable provider-log receipt containing the acquired
   protected revision, exact selected P2b identity and explicit candidate/stale
   rejection results. The receipt is evidence for this exact candidate, not a
   new authority surface.
7. Route the focused contract, this Decision and the live proof through the
   dedicated R2A exact-head workflow and the existing
   `semantic-review-assurance` guardrail. Only a Pull Request targeting `main`
   may emit the subsequent-candidate receipt; manual dispatch remains a
   non-evidentiary compatibility run and skips that receipt-producing step.
8. Leave the closed OCI(P2a) inner semantic authority and the promoted outer
   authority record unchanged. Perform **no registry write**, publication,
   rerun, tag, release, deployment or provider-setting mutation.

## Negative-proof semantics

The negative claim is selection-scoped. A historical B1.x authority document
can remain well-formed evidence. It is refused for this candidate because
candidate bytes cannot supply the repository, protected branch, authority path
or outer runtime accepted by the public execution entry point. Protected
`main` supplies the only effective record, and that record selects exact P2b.

The public runner continues to accept only the untrusted review input. The
candidate runtime remains useful for candidate self-checks and inherited
capability smoke tests, but it never becomes the prior-effective outer runtime
for the protected current-advisory result.

## Consequences

- Successful exact-head provider execution proves the complete rolling
  invariant from prior-effective OCI(B1.6), through integrated P2b, to promoted
  prior-effective OCI(P2b) consumed by the next candidate.
- No further bootstrap artifact or authority hop is required unless this proof
  exposes a concrete correctness defect.
- The resulting evidence completes the P2b rolling-trust detour but does not close issue #11.
  The broader Work Item, its remaining semantic-capture scope
  and the owner-directed #15/#14 handoff retain their own provider lifecycle and
  authority.
- The final candidate still requires exact-head CI, review convergence and
  explicit human merge authority; this Decision supplies none of those effects.

## Non-goals

This is not a new trust selector, schema version, semantic judge, OCI artifact,
release, deployment, provider adapter, generic consumer feature or #15 effect.
It does not verify attestation on every consumption, rewrite historical B1.x
evidence, expose the host Docker socket, make candidate bytes authoritative,
close issue #11, merge its own candidate or authorize any registry mutation.
