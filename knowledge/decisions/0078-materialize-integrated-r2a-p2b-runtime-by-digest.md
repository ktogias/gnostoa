---
type: Decision
title: Materialize the integrated R2A P2b runtime as a prior-effective digest-only OCI identity
description: Complete the post-B2 materialization leg of the rolling-trust exit by publishing exact integrated P2b once by immutable digest, attesting it, and independently reacquiring it before any authority promotion.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-16T21:12:00+03:00"
sources:
  - id: b2-activation
    resource: ./0077-activate-r2a-p2b-b2-through-prior-effective-b16.md
    title: Decision 0077
  - id: b16-materialization
    resource: ./0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md
    title: Decision 0075
  - id: rolling-trust-exit
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5680382022
    title: P2b rolling-trust exit boundary
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
  - id: b2-integration
    resource: https://github.com/ktogias/gnostoa/pull/265
    title: Integrated P2b-B2 activation
x-project-knowledge:
  id: kit.decision.0078.materialize-integrated-r2a-p2b-runtime-by-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md
    - kind: governed-by
      target: /decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md
    - kind: implements
      target: /decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md
---

# Materialize the integrated R2A P2b runtime as a prior-effective digest-only OCI identity

## Context

Decision 0077 activated P2b-B2 through the already protected prior-effective OCI(B1.6) outer consumer and an isolated nested Docker daemon. PR #265 then integrated that activation on protected `main` as exact commit `2aa1ed3217c42819155b8ff36385b000720ba4f8`, exact tree `4cda4e4a704cb518f56201423e313d4dd9db5e24`.

That integration satisfies only the first item of the recorded P2b exit boundary. Issue #11 comment `5680382022` requires the exact integrated P2b runtime to be independently materialized as immutable digest-only OCI, attested and independently reacquired, then separately promoted as the next protected prior-effective identity and negatively read back by a subsequent candidate.

Owner authorization `5671332574` already covers the bounded sequence through full P2b activation completion. The existing boundaries remain unchanged: no mutable OCI tag or release, no deployment, no host Docker-socket authority, no blind retry after an ambiguous registry effect, and no unrelated #15/provider-setting expansion.

## Decision

Materialize exact integrated P2b source commit `2aa1ed3217c42819155b8ff36385b000720ba4f8` and source tree `4cda4e4a704cb518f56201423e313d4dd9db5e24` through one dedicated protected-main workflow.

The workflow SHALL:

1. admit only the first protected-main push that lands PR #267 from `r2a-p2b-materialization` directly on predecessor `2aa1ed3217c42819155b8ff36385b000720ba4f8`, binding the landing commit back to the provider PR record;
2. fence `GITHUB_RUN_ATTEMPT == 1` both in the authorization job and independently inside the effect-capable publication job, so a job-level rerun cannot regain package-write authority;
3. check out the exact integrated P2b source separately and verify source commit, source tree, version, runtime lock and deterministic build metadata before authentication;
4. build and verify the exact runtime locally before any registry effect, including non-root identity, OCI revision/created labels, deterministic public-surface digest, tracked source membership and a full runtime `self-check`;
5. retain the B1.6 input-only entrypoint proof and the integrated P2b/B2 source surface, including `tools/review_outer.py`, `ci/review_outer_smoke.py` and Decision 0077;
6. publish only through `ci/build-runtime --push-by-digest`, deriving the exact registry digest from bounded BuildKit metadata and creating no mutable remote tag;
7. reacquire that exact digest, re-prove runtime/source/public-surface identity and execute the full self-check against the digest-qualified image;
8. attest that exact OCI manifest with the pinned provider action, verify the attestation, remove authenticated local state, independently reacquire the same digest under a fresh anonymous Docker configuration and re-prove the runtime again;
9. execute a final read-only post-write reconciliation against the exact digest and attestation, failing closed if the registry outcome cannot be bound to an exact digest; and
10. emit a bounded workflow summary carrying source commit, source tree, public-surface digest, OCI digest and workflow-run identity.

The publication workflow itself is a one-shot effect. If an attempt reaches authentication or package-write territory and its outcome is ambiguous, that ambiguity creates **no rerun authority**. Recovery begins with read-only provider/attestation reconciliation and a new explicit verification-first disposition if the exact immutable state cannot be established.

## Why this is a new OCI identity

OCI(B1.6) remains the prior-effective consumer that judged and executed the B2 activation candidate without self-trust. After #265 integrated, the repository now contains the accepted B2 orchestration and its tests. The rolling invariant therefore requires a new independently materialized artifact from the integrated P2b state rather than reusing OCI(B1.6) indefinitely.

The resulting `ghcr.io/ktogias/gnostoa@sha256:...` is OCI(P2b). It is eligible for a **separate** protected prior-effective authority promotion only after the materialization workflow succeeds and its exact evidence is reconciled. This Decision does not perform that promotion.

## This is not a release or promotion

This change creates no Git tag, GitHub release, mutable OCI tag, version bump, deployment, provider-setting mutation, semantic PASS, reviewer qualification or merge authority. It does not expose the host Docker socket and does not alter the closed inner semantic authority. It also does not itself change the protected outer-consumer authority from OCI(B1.6) to OCI(P2b).

## Consequences

- Exact integrated P2b obtains an independently reacquirable, content-addressed OCI identity.
- The B2 implementation is frozen behind the same source/tree/public-surface/runtime binding used for prior rolling-trust materializations.
- Historical B1.6 rerun-authority containment is carried forward by independently fencing the effect-capable job.
- The next bounded slice can promote protected prior-effective authority to OCI(P2b) without republishing it.
- The Ariadne exit remains open until that promotion and the required subsequent negative read-back both succeed.
