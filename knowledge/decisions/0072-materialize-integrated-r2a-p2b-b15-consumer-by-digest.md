---
type: Decision
title: Materialize the integrated R2A P2b-B1.5 outer consumer as a prior-effective digest-only OCI identity
description: Materialize exact integrated P2b-B1.5 as a one-shot digest-only OCI outer-consumer identity before any P2b-B2 activation.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-15T01:15:00+03:00"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: bootstrap-pattern
    resource: ./0068-materialize-r2a-p2a-as-a-one-shot-digest-only-oci-judge.md
    title: Decision 0068
  - id: b1-materialization
    resource: ./0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md
    title: Decision 0069
  - id: b15-runtime
    resource: ./0071-add-docker-client-to-r2a-b1-runtime.md
    title: Decision 0071
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization to continue through full P2b activation completion
  - id: b15-integration
    resource: https://github.com/ktogias/gnostoa/pull/253
    title: Integrated dormant P2b-B1.5 Docker-client precursor
x-project-knowledge:
  id: kit.decision.0072.materialize-integrated-r2a-p2b-b15-consumer-by-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0068-materialize-r2a-p2a-as-a-one-shot-digest-only-oci-judge.md
    - kind: governed-by
      target: /decisions/0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md
    - kind: governed-by
      target: /decisions/0071-add-docker-client-to-r2a-b1-runtime.md
    - kind: implements
      target: /decisions/0071-add-docker-client-to-r2a-b1-runtime.md
---

# Materialize the integrated R2A P2b-B1.5 outer consumer as a prior-effective digest-only OCI identity

## Context

Decision 0067 requires current-advisory authority and final result provenance to come from already accepted evidence rather than candidate-controlled bytes. Decision 0068 established the rolling prior-integrated OCI bootstrap pattern, and Decision 0069 applied that pattern to the dormant P2b-B1 outer consumer.

Decision 0071 then inserted a bounded B1.5 precursor because immutable OCI(B1) could reacquire protected `main` but could not execute its already-integrated inner OCI(P2a) judge path: the runtime lacked a Docker client. PR #253 integrated the client-only precursor on protected `main` at exact source revision `7093fd043f2269e09da74b03ce9d35fb6aece5da` and exact tree `e7a4f2142e72efd52133f4719d8acf9b2dccb89d`.

That integrated source contains the exact selected Debian package `docker-cli=26.1.5+dfsg1-9+deb13u1`, rejects caller override of the selected build argument, contains no Docker daemon or containerd package/executable, and exposes no host Docker socket. P2b-B2 remains dormant.

Owner authorization `5671332574` directs the project to continue through the remaining rolling trust sequence until full P2b activation completes, subject to the existing verification-first and fail-closed boundaries.

## Decision

Reuse the Decisions 0068/0069 rolling prior-integrated OCI pattern for the exact integrated B1.5 outer consumer.

A dedicated protected-main workflow SHALL:

1. admit only the first `push` to protected `main` that lands the B1.5 materialization workflow when the protected-main predecessor is exact integrated B1.5 commit `7093fd043f2269e09da74b03ce9d35fb6aece5da`;
2. refuse manual dispatch, retries and any context whose `event.before`, actor, branch, repository, run attempt, workflow identity, source commit or source tree differs from the selected transition;
3. check out exact B1.5 source revision `7093fd043f2269e09da74b03ce9d35fb6aece5da` and tree `e7a4f2142e72efd52133f4719d8acf9b2dccb89d` separately from the publisher source;
4. build and verify that exact runtime locally before any registry authentication or write, including non-root identity, OCI source labels, public-surface digest, source manifest, dormant outer-consumer files, self-check, and the exact B1.5 client-only capability through `ci/review_b15_runtime_smoke.py`;
5. perform one digest-only GHCR publication through the existing hardened `ci/build-runtime --push-by-digest` path, creating no remote tag;
6. obtain the authoritative registry manifest digest from bounded BuildKit metadata and reacquire the image by that digest;
7. verify the exact source revision, public-surface digest and B1.5 client-only capability again on the digest-qualified registry artifact;
8. attest that exact manifest, verify the attestation, log out, anonymously reacquire the same digest and revalidate the exact runtime identity and B1.5 capability a third time; and
9. emit a bounded receipt carrying source commit, source tree, public-surface digest, OCI digest and workflow-run identity.

The B1.5 capability check is intentionally repeated at all three materialization cuts: before authentication, after authenticated digest readback, and after anonymous digest reacquisition. A valid artifact must contain the exact selected `docker-cli=26.1.5+dfsg1-9+deb13u1`, run as the established non-root `kit` user, contain no `dockerd` or `containerd` executables, contain no `docker.io` or `containerd` packages, and require no host Docker socket.

The resulting `ghcr.io/ktogias/gnostoa@sha256:...` reference becomes the immutable OCI(B1.5) identity eligible for the next protected outer-consumer authority update. Materialization itself does not activate P2b-B2 and does not establish semantic PASS or reviewer qualification.

## Failure and rerun rule

There is **no blind rerun** after a workflow attempt reaches the registry write boundary. A failure proven to have occurred before authentication or any registry effect may be repaired only through a new verification-first protected change with an exact replacement transition. An ambiguous or post-write failure must first reconcile read-only GHCR and attestation state against the exact source revision, source tree and derived public-surface digest. Matching immutable state is evidence to retain, not permission to publish again.

## Relationship to protected outer-consumer authority and P2b-B2

The rolling trust sequence after this Decision is:

`OCI(B1) authority -> protected B1.5 integration -> OCI(B1.5) -> protected B1.5 consumer authority -> P2b-B2 activation candidate`.

The protected B1.5 authority update must bind the independently materialized OCI(B1.5) digest and exact source/public-surface identities before candidate B2 bytes may route current-advisory execution through it. Candidate B2 bytes remain untrusted input/transport and may not become the provenance source for the live result.

After P2b is integrated, the rolling invariant still requires materializing/promoting OCI(P2b) for the next transition.

## This is not a release

This materialization is **not a release**. It creates no Git tag, release object, version bump, deployment, mutable or `latest` OCI tag, provider-setting mutation, #15 workflow effect, semantic PASS, qualified reviewer domain or merge authority. It does not mount, expose or authorize the host Docker socket.

## Consequences

- The exact integrated B1.5 outer consumer gains a durable, independently reacquirable digest-only OCI identity.
- The selected Docker-client capability is re-proved on the actual artifact before and after the single registry effect rather than inferred only from source text.
- The next protected authority update can bind OCI(B1.5) rather than the obsolete OCI(B1) consumer.
- B2 activation remains blocked until that new authority is integrated and prior-effective.
- External-effect recovery remains fail closed: ambiguous publication does not create retry authority.
