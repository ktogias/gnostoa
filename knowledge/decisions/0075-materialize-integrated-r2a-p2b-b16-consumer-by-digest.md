---
type: Decision
title: Materialize the integrated R2A P2b-B1.6 outer consumer as a prior-effective digest-only OCI identity
description: Materialize exact integrated P2b-B1.6 as a one-shot digest-only OCI outer-consumer identity before any P2b-B2 activation.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-15T11:31:00+03:00"
sources:
  - id: b15-materialization
    resource: ./0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md
    title: Decision 0072
  - id: b15-authority-promotion
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
    title: Owner authorization to continue through full P2b activation completion
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
      target: /decisions/0073-promote-r2a-b15-outer-consumer-authority.md
    - kind: governed-by
      target: /decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
    - kind: implements
      target: /decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
---

# Materialize the integrated R2A P2b-B1.6 outer consumer as a prior-effective digest-only OCI identity

## Context

Decision 0072 independently materialized the dormant B1.5 outer consumer as a digest-only prior-effective OCI identity, and Decision 0073 then promoted the protected outer-consumer authority to that exact immutable B1.5 artifact. Decision 0074 subsequently identified one remaining trust-boundary prerequisite before P2b-B2: the trusted outer runtime needed its own non-injectable executable adapter to the already integrated live evaluator.

PR #256 integrated that B1.6 precursor on protected `main` at exact source revision `f29499286bac9859364d45da0f6c59396518b749` and exact source tree `ff38abe5718ebc550054ea6af18a73d0aef8e514`. The integrated runtime retains the exact pinned Docker client from B1.5 without a Docker daemon, containerd runtime or host Docker-socket dependency, and now contains the private fixed `tools.review_live_entrypoint` module plus the hermetic `ci/review_b16_entrypoint_smoke.py` proof.

The private adapter is deliberately not a public candidate authority surface. It accepts only an untrusted input document and delegates to the already integrated protected live evaluator. A later B2 candidate therefore has no need to inject `python -c`, a bind-mounted launcher or any other candidate-injected executable into the prior-effective outer runtime.

Owner authorization `5671332574` directs the project to continue through the remaining rolling trust sequence until full P2b activation completes, subject to the established verification-first, immutable-identity and fail-closed boundaries.

## Decision

Reuse the rolling digest-only materialization pattern established by Decisions 0068, 0069 and 0072 for the exact integrated B1.6 outer consumer.

A dedicated protected-main workflow SHALL:

1. admit only the first `push` to protected `main` that lands the B1.6 materialization workflow when the protected-main predecessor is exact integrated B1.6 commit `f29499286bac9859364d45da0f6c59396518b749`;
2. refuse manual dispatch, retries and any context whose `event.before`, actor, triggering actor, repository, branch, workflow identity, source commit or source tree differs from the selected transition;
3. check out exact B1.6 source revision `f29499286bac9859364d45da0f6c59396518b749` and tree `ff38abe5718ebc550054ea6af18a73d0aef8e514` separately from the publisher source;
4. build and verify that exact runtime locally before any registry authentication or write, including non-root identity, OCI source labels, public-surface digest, source manifest, self-check, the inherited B1.5 Docker-client/no-daemon capability and the B1.6 input-only executable/daemonless capability;
5. prove that the exact image contains `tools/review_live_entrypoint.py`, `ci/review_b15_runtime_smoke.py` and `ci/review_b16_entrypoint_smoke.py` as tracked runtime source members;
6. perform one digest-only GHCR publication through the hardened `ci/build-runtime --push-by-digest` path, creating no remote tag;
7. obtain the authoritative registry manifest digest from bounded BuildKit metadata and reacquire the image by that digest;
8. repeat both the B1.5 runtime smoke and the B1.6 entrypoint smoke against the authenticated digest-qualified artifact;
9. attest that exact manifest, verify the attestation, log out, anonymously reacquire the same digest and repeat both runtime smokes a third time; and
10. emit a bounded receipt carrying source commit, source tree, public-surface digest, OCI digest and workflow-run identity.

The capability checks are intentionally repeated at all three materialization cuts: before authentication, after authenticated digest readback and after anonymous digest reacquisition. B1.6 is valid only if it retains the selected client-only Docker capability while also packaging the fixed input-only module entrypoint and its hermetic no-network/no-daemon proof.

The resulting `ghcr.io/ktogias/gnostoa@sha256:...` reference becomes the immutable OCI(B1.6) identity eligible for the next protected outer-consumer authority update. Materialization itself does not activate P2b-B2 and does not establish semantic PASS, reviewer qualification or merge authority.

## Failure and rerun rule

There is **no blind rerun** after a workflow attempt reaches registry authentication or any registry write boundary. A failure proven to have occurred before authentication or any registry effect may be repaired only through a new verification-first protected change with an exact replacement transition. An ambiguous or post-write failure must first reconcile read-only GHCR and attestation state against the exact source revision, source tree and derived public-surface digest. Matching immutable state is evidence to retain, not permission to publish again.

## Relationship to protected outer-consumer authority and P2b-B2

The rolling trust sequence after this Decision is:

`protected OCI(B1.5) authority -> protected B1.6 integration -> OCI(B1.6) -> protected B1.6 consumer authority -> P2b-B2 activation candidate`.

The next change after successful materialization must separately promote the protected outer-consumer authority to the exact OCI(B1.6) digest and its exact source/public-surface identities. P2b-B2 remains blocked until that promotion is integrated and prior-effective.

Only after that authority transition may a B2 candidate orchestrate the exact prior-effective B1.6 outer container. Candidate bytes remain untrusted input and transport. They may not replace the trusted outer runtime, select the inner semantic judge identity, or inject executable code into the trusted outer result path.

The later isolated nested Docker daemon must not expose or bind-mount the host Docker socket. Its daemon-owned ephemeral Unix socket may be shared only with the exact prior-effective outer container, with bounded lifecycle and cleanup.

## This is not a release

This materialization is **not a release**. It creates no Git tag, release object, version bump, deployment, mutable or `latest` OCI tag, provider-setting mutation, semantic PASS, qualified reviewer state or merge authority. It does not expose the host Docker socket and does not activate P2b-B2.

## Consequences

- The exact integrated B1.6 outer consumer gains a durable, independently reacquirable digest-only OCI identity.
- The inherited B1.5 Docker-client/no-daemon property and the new B1.6 fixed executable entrypoint are proven on the actual immutable artifact at all three materialization cuts.
- Candidate-injected executable shims remain unnecessary and forbidden in the later trusted outer path.
- The next protected authority update can bind OCI(B1.6) rather than the now-obsolete OCI(B1.5) outer-consumer identity.
- B2 activation remains a separate verification-first change after that authority promotion.
- Ambiguous external-effect recovery remains fail closed and never creates retry authority by itself.
