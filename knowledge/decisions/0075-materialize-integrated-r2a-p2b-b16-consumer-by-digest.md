---
type: Decision
title: Materialize the integrated R2A P2b-B1.6 outer consumer as a prior-effective digest-only OCI identity
description: Materialize exact integrated P2b-B1.6 as a one-shot digest-only OCI outer-consumer identity before any P2b-B2 activation.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-15T09:55:00Z"
sources:
  - id: b15-materialization
    resource: ./0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md
    title: Decision 0072
  - id: b15-authority
    resource: ./0073-promote-r2a-b15-outer-consumer-authority.md
    title: Decision 0073
  - id: b16-entrypoint
    resource: ./0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
    title: Decision 0074
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
  - id: b16-integration
    resource: https://github.com/ktogias/gnostoa/pull/256
    title: Integrated dormant P2b-B1.6 input-only entrypoint precursor
x-project-knowledge:
  id: kit.decision.0075.materialize-integrated-r2a-p2b-b16-consumer-by-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md
    - kind: governed-by
      target: /decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
    - kind: implements
      target: /decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
---

# Materialize the integrated R2A P2b-B1.6 outer consumer as a prior-effective digest-only OCI identity

## Context

Decision 0072 established the hardened one-shot digest-only materialization pattern for OCI(B1.5), and Decision 0074 requires one additional rolling-trust step before B2: after the private input-only entrypoint is integrated, the exact integrated runtime must be independently materialized as OCI(B1.6) and separately promoted as protected outer-consumer authority.

PR #256 integrated B1.6 on protected `main` at exact source revision `f29499286bac9859364d45da0f6c59396518b749` and exact source tree `ff38abe5718ebc550054ea6af18a73d0aef8e514`. That runtime preserves the B1.5 pinned Docker-client capability, adds the fixed private `python -m tools.review_live_entrypoint --input <path>` route, keeps the public current-advisory CLI dormant, and remains daemonless. It neither exposes nor depends on the host Docker socket.

Owner authorization `5671332574` continues to cover the rolling trust sequence through full P2b activation, subject to the existing verification-first and fail-closed boundaries.

## Decision

Reuse the Decision 0072 materialization pattern for exact integrated B1.6.

A dedicated protected-main workflow SHALL:

1. admit only the first `push` to protected `main` that lands the B1.6 materialization workflow when the protected-main predecessor is exact integrated B1.6 commit `f29499286bac9859364d45da0f6c59396518b749`;
2. refuse manual dispatch, retries, actor drift, branch drift, repository drift, workflow-identity drift, source-commit drift and source-tree drift;
3. check out exact B1.6 source revision `f29499286bac9859364d45da0f6c59396518b749` and tree `ff38abe5718ebc550054ea6af18a73d0aef8e514` separately from the publisher source;
4. before any registry authentication or write, build that exact runtime locally and verify its non-root identity, OCI revision labels, public-surface digest, source manifest, self-check, retained B1.5 Docker-client capability and B1.6 input-only exact-module/daemonless capability;
5. perform one digest-only GHCR publication through the hardened `ci/build-runtime --push-by-digest` path, creating no remote tag;
6. derive the authoritative registry digest only from bounded BuildKit metadata and reacquire the artifact by that digest;
7. re-prove the same source identity, public-surface digest, B1.5 capability and B1.6 capability on the authenticated digest-qualified read-back;
8. attest that exact manifest, verify the attestation, log out, anonymously reacquire the same digest, and re-prove the same identity and capabilities a third time; and
9. emit a bounded receipt carrying source commit, source tree, public-surface digest, OCI digest and workflow-run identity.

The B1.6 capability proof must exercise the packaged fixed module entrypoint itself, not an injected launcher, and must preserve the hermetic `--network none` daemonless proof. No host Docker socket is mounted or exposed. Publication introduces no Docker daemon authority into the artifact.

The resulting `ghcr.io/ktogias/gnostoa@sha256:...` reference becomes the immutable OCI(B1.6) identity eligible for the next separate protected outer-consumer authority update. It is prior-effective materialization evidence only; it does not activate P2b-B2 and does not establish semantic PASS or reviewer qualification.

## Failure and rerun rule

There is **no blind rerun** after a workflow attempt reaches the registry write boundary. A failure proven to have occurred before authentication or any registry effect may be repaired only through a new verification-first protected change with an exact replacement transition. An ambiguous or post-write failure must first reconcile read-only GHCR and attestation state against the selected source revision, source tree and public-surface digest. Matching immutable state is evidence to retain, not permission to publish again.

## Relationship to protected outer-consumer authority and P2b-B2

The required sequence is now:

`protected B1.6 integration -> OCI(B1.6) materialization -> protected B1.6 outer-consumer authority -> P2b-B2 activation candidate`.

The authority-promotion change must bind the independently materialized OCI(B1.6) digest and exact source/public-surface identities before candidate B2 bytes may route current-advisory execution through it. Candidate B2 bytes remain untrusted input/transport and may not select the trusted outer runtime, inner semantic judge or protected policy identities.

## This is not a release

This materialization is **not a release**. It creates no Git tag, release object, version bump, deployment, mutable OCI tag, `latest` tag, provider-setting mutation, semantic PASS, qualified reviewer domain or merge authority. It does not mount, expose or authorize the host Docker socket.

## Consequences

- Exact protected B1.6 gains an independently reacquirable digest-only OCI identity.
- The inherited B1.5 Docker-client boundary and the new input-only B1.6 executable boundary are proven on the artifact at all three materialization cuts.
- The next protected authority update can bind OCI(B1.6) without relying on candidate-injected executable code.
- P2b-B2 remains blocked until that authority promotion is integrated and prior-effective.
- Ambiguous external effects remain fail closed; a publication attempt never grants itself retry authority.
