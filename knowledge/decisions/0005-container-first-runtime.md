---
type: Decision
title: Use a container-first but not container-only runtime
description: Hide validator implementation dependencies from consumers without making a container daemon the only recovery path.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: oci
    resource: https://opencontainers.org/
    title: Open Container Initiative
  - id: dev-containers
    resource: https://containers.dev/
    title: Development Containers
x-project-knowledge:
  id: kit.decision.0005.container-first-runtime
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /contracts/public-inheritance-surface.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
---

# Use a container-first but not container-only runtime

## Context

Requiring the toolkit's implementation language in every adopting project leaks
an internal choice into an otherwise technology-neutral public contract.
Making containers the only execution path would instead impose a heavier
runtime, exclude restricted environments and weaken debugging and recovery.

## Decision

Make a pinned OCI-compatible runtime image the primary consumer and CI
interface. Provide a Development Container as the primary maintainer
environment. Continue supporting an isolated native CLI as a fallback.

Couple the runtime image and toolkit source/profile revision through a validated
project lock that also records the deterministic toolkit public-surface digest.
Recompute that digest from the mounted source and compare it with both the lock
and the surface embedded in the executing image. Pin release and CI images by
digest. Keep project knowledge and profiles portable plain files outside the
image.

Concrete application frameworks and contract-testing products are not part of
the generic tool selection; they belong in project or module specializations.

## Consequences

- Consuming projects do not need the toolkit's implementation language.
- Local and CI execution share an immutable environment.
- The project must maintain images, security rebuilds and multi-architecture
  publication.
- Bind mounts, user identity and restricted container environments require
  documented handling.
- Native execution remains supported and must produce equivalent validation.
- Native execution still verifies the locked public-source content even though
  no independent container filesystem is present.
