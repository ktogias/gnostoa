---
type: Decision
title: Materialize R2A P2a as a one-shot digest-only OCI bootstrap judge
description: Authorize one bounded protected-main publication of the already-integrated P2a source as a digest-pinned OCI bootstrap trust anchor for P2b.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-14T02:05:44Z"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5658009912
    title: Owner authorization 5658009912 for bounded bootstrap OCI materialization
  - id: bootstrap-pr
    resource: https://github.com/ktogias/gnostoa/pull/246
    title: P2b bootstrap OCI materialization candidate
x-project-knowledge:
  id: kit.decision.0068.materialize-r2a-p2a-as-a-one-shot-digest-only-oci-judge
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Materialize R2A P2a as a one-shot digest-only OCI bootstrap judge

## Context

Decision 0067 requires `current_advisory` to use an accepted `prior_integrated` judge and explicitly rejects candidate self-authorization. P2a is now integrated on protected `main` at source revision `d66d1830d724d759db6ec87e1f8d5dcc0847f221`, tree `384df86fec31208a02371b63722f903e63404134`, with public-surface digest `sha256:ee2418fccd7e8907b8b8f60b0e0c7663e93c3e9abb66d9496efd1c3666ca1845`.

The post-merge P2a CI build proved that this source builds as the ordinary Gnostoa runtime, but its runner-local image ID was not a durable, independently reacquirable OCI identity. P2b therefore needs one persistent digest-pinned OCI materialization of the already-integrated P2a judge before protected authority may bind it.

Owner authorization `5658009912` admits exactly that bounded effect. GHCR is the concrete bootstrap registry route, but R2A semantics remain registry-neutral.

## Decision

### A. Reuse the ordinary Gnostoa executable and container runtime

Do not create an R2A-specific executable, service, Dockerfile or runtime target. Build the exact P2a source with the existing `ci/build-runtime`, existing `Dockerfile`, existing `runtime` target and the ordinary `knowledge` executable entry point. The bootstrap artifact differs only in its immutable OCI identity and publication purpose.

### B. Publish the already-integrated P2a source by digest only

The one-shot protected-main workflow may materialize only source revision `d66d1830d724d759db6ec87e1f8d5dcc0847f221`, its exact tree and its exact public-surface digest. Publication is digest-only: no remote mutable tag, `latest`, release tag or version-selection alias is created. BuildKit metadata must yield a valid registry manifest SHA-256, and subsequent verification must use `repository@sha256:...`.

The publication workflow itself must first be integrated through the normal protected change path. Its effect is admitted only for the exact protected-main transition whose previous revision is the integrated P2a source. Candidate/PR execution has no package-write effect.

### C. Verify before and after the single registry effect

Before publication, locally build and verify the exact P2a runtime, including source revision, tree-derived runtime content, public-surface digest, platform, non-root identity and self-check.

After publication, read the BuildKit-reported manifest digest, reacquire the same digest from the registry, revalidate the runtime identity, attest that exact digest, verify the attestation, then log out and prove anonymous reacquisition and revalidation of the same digest. Only that verified digest-qualified identity may be used by the next protected P2b authority-binding slice.

### D. No blind rerun after an ambiguous effect

This authorization permits one publication attempt and **no blind rerun**. A transient failure before any registry effect leaves P2b blocked but does not expand authority. If a run may have written registry state but fails before a complete verified digest receipt exists, a new write attempt is not automatically authorized. Recovery first requires separately accountable **read-only provider-state reconciliation** to determine whether a valid digest-bound artifact exists and whether it satisfies the admitted source, surface and attestation identities.

This fail-closed recovery rule deliberately does not turn a partial/ambiguous external effect into retry authority.

### E. This is not a release

The bootstrap materialization is **not a release**. It creates no Git release, Git tag, version bump, deployment, mutable/latest OCI tag, provider-setting mutation, semantic R2A policy change, `current_advisory` activation by itself, or #15 review-loop mechanics.

### F. The P2a OCI is a bootstrap anchor, not the steady-state judge

The resulting `OCI(P2a)` exists only to break the P2b self-reference safely. It is the prior-integrated bootstrap trust anchor against which the P2b activation candidate can be verified.

P2b is not complete merely when `current_advisory` first becomes evaluatable. After P2b is integrated, the project must materialize and verify a digest-pinned `OCI(P2b)` and promote that artifact as the new active prior-integrated judge. Future judge upgrades follow the same rolling invariant:

```text
integrated N-1 -> OCI(N-1) judges/binds N -> N integrates -> OCI(N) -> OCI(N) becomes the next active judge
```

This prevents permanent dependence on the bootstrap P2a artifact and preserves prior-integrated trust across later upgrades.

## Consequences

- P2b gains a durable prior-integrated runtime identity without trusting candidate bytes.
- The existing Gnostoa executable/container architecture remains single-surface; no parallel R2A runtime is introduced.
- Digest-only publication removes mutable-tag overwrite and check-then-push races from this bootstrap route.
- External-effect recovery stays fail closed and accountable rather than silently retryable.
- P2b exit criteria include post-merge `OCI(P2b)` promotion, not only first live `current_advisory` execution.
