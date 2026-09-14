---
type: Decision
title: Add a pinned Docker client to the dormant R2A B1 runtime before B2 activation
description: Add only a version-pinned Docker CLI client to the dormant prior-integrated R2A outer-consumer runtime, then materialize and protect that capability before P2b-B2 activation.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-14T16:15:00Z"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: b1-materialization
    resource: ./0069-materialize-integrated-r2a-p2b-b1-consumer-by-digest.md
    title: Decision 0069
  - id: b1-authority
    resource: ./0070-protect-r2a-b1-outer-consumer-authority-separately.md
    title: Decision 0070
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: precursor-finding
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5666856896
    title: B2 Docker-client precursor finding
  - id: debian-docker-cli
    resource: https://packages.debian.org/trixie/docker-cli
    title: Debian 13 trixie docker-cli package
  - id: docker-cli-license
    resource: https://github.com/docker/cli
    title: Docker CLI upstream source and Apache-2.0 license
x-project-knowledge:
  id: kit.decision.0071.add-docker-client-to-r2a-b1-runtime
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
      target: /decisions/0070-protect-r2a-b1-outer-consumer-authority-separately.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Add a pinned Docker client to the dormant R2A B1 runtime before B2 activation

## Context

Decision 0070 made the immutable OCI(B1) outer-consumer identity prior-effective through a separate protected authority record. After that authority landed on protected `main`, the next P2b-B2 design check exposed a runtime-capability mismatch before any activation code was accepted.

OCI(B1) already contains `git`, `tools/review_live.py`, and `tools/review_current.py`. It can therefore reacquire the closed v1 inner semantic authority from protected `main`. But `tools/review_current.py` deliberately resolves a `docker` executable through a fixed system path before it can reacquire and execute the authority-bound OCI(P2a) judge. The materialized B1 runtime does not contain that executable.

A nested Docker daemon alone therefore cannot make exact OCI(B1) operational. Injecting a candidate- or host-selected Docker client into the trusted outer consumer would make B2-controlled transport participate in the executable path whose result the prior-effective consumer relies on. Mounting the host Docker socket would additionally make the host daemon part of the trusted execution substrate without an R2A authority binding. Both approaches would weaken the anti-self-reference boundary established by Decisions 0067, 0069 and 0070.

Debian 13/trixie provides a separate client-only package, `docker-cli`, distinct from the full `docker.io` daemon package. The selected package version for this bounded precursor is exactly `docker-cli=26.1.5+dfsg1-9+deb13u1`. Upstream Docker CLI is Apache-2.0 licensed; the Debian package retains the distribution-provided copyright/license metadata.

## Decision

Introduce one bounded **B1.5** precursor before P2b-B2:

1. Add exactly the version-pinned Debian package `docker-cli=26.1.5+dfsg1-9+deb13u1` to the Gnostoa base/runtime image.
2. Do not install the `docker.io` daemon package, `dockerd`, containerd, or any other daemon solely for this precursor.
3. Keep `knowledge review-check` current-advisory prior-integrated routing dormant. This slice **does not activate P2b-B2**.
4. Verify the exact candidate runtime in centralized CI: it must run as the existing non-root `kit` user, contain the exact selected `docker-cli` package and executable, and contain no `dockerd` executable.
5. Do not mount or otherwise expose the host Docker socket to the dormant runtime. A later B2 activation must use a separately bounded execution substrate and must not treat the host Docker socket as implicit authority.
6. After this B1.5 source is integrated, independently materialize that exact integrated source as a new digest-only OCI outer-consumer identity using the rolling Decision-0068/0069 pattern.
7. Update the protected outer-consumer authority to the exact materialized B1.5 identity before any B2 candidate may use the new client capability.

The client package is capability, not authority. Candidate B1.5 bytes cannot become the live result provenance source merely because they contain `docker`.

## Why a precursor instead of adding the client in B2?

B2 is the transition where candidate-side routing starts consuming the prior-effective outer runtime. If the same B2 candidate also supplied a Docker executable absent from that prior-effective runtime, the candidate would influence the execution mechanism used by the supposedly prior-effective evaluator. Landing, materializing, and authority-binding the client capability first removes that circularity.

The rolling chain becomes:

`OCI(B1) authority -> B1.5 source candidate -> protected B1.5 integration -> OCI(B1.5) -> protected B1.5 consumer authority -> P2b-B2 activation candidate`.

## Verification boundary

The B1.5 CI smoke checks only runtime capability and absence of daemon authority. It may use the CI host Docker daemon to start the exact candidate image for inspection, but it passes no Docker socket into that image and performs no live R2A semantic activation.

A later B2 slice must separately verify its daemon/transport boundary. In particular, this Decision grants no permission to use the **host Docker socket** for live current-advisory evaluation.

## Consequences

- The future prior-effective outer consumer can carry the Docker client required by its already-integrated inner-judge orchestration code.
- The Docker client version becomes part of the integrated source/runtime identity before live use rather than a candidate-supplied helper.
- No daemon or host-container-control authority is added to B1.5.
- B2 remains blocked until B1.5 is integrated, materialized and promoted through protected consumer authority.
- The Issue #10 qualification state remains empty, so this precursor creates no qualified independence domain, semantic PASS, or merge authority.
- All eventual R2A semantic results remain advisory and `binding:false`.

## Non-goals

This Decision does not activate P2b-B2, does not change the inner OCI(P2a) judge, the closed v1 semantic authority, review policy or qualification snapshot, and does not create a release, deployment, mutable OCI tag, provider-setting mutation, #15 workflow effect, Docker daemon authority, host Docker socket authority, semantic PASS or merge authority.
