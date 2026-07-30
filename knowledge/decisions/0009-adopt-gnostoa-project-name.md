---
type: Decision
title: Adopt Gnostoa as the project name
description: Give the generic knowledge architecture foundation a distinctive project identity without leaking branded vocabulary into consuming projects.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.decision.0009.adopt-gnostoa-project-name
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /project/gnostoa.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Adopt Gnostoa as the project name

## Context

The unpublished project needs a distinctive identity for its source repository,
runtime image, package metadata and future public site. Its working name,
Knowledge Architecture Kit, accurately describes the project but is generic,
hard to distinguish and difficult to own as a product identity.

Names derived from `Nous` have material conflicts in the knowledge-management,
software and AI markets. `Gnostoa` combines the knowledge root `gnosis` with the
place metaphor `stoa`: a shared, sheltered place for teaching, discussion and
exchange. The metaphor describes an environment in which governed knowledge is
made usable, rather than a proprietary knowledge object that consuming projects
must adopt.

This repository has no baseline commit, remote, published package or released
runtime image. The rename therefore occurs within the bootstrap exception
defined by Decision 0006 and does not require a compatibility alias for a
released artifact.

## Decision

Adopt **Gnostoa** as the project, distribution, runtime-image and site identity.
Use `gnostoa` for publishable artifact coordinates and self-policy identifiers.

Keep consumer-facing role vocabulary technology- and product-neutral. In
particular, retain the `knowledge` command, `KNOWLEDGE_KIT_*` integration
variables, generic profile vocabulary and anonymous examples. Consuming
projects must not need to introduce a `Gnostoa`-specific domain concept.

Keep stable internal concept IDs under the existing `kit.*` namespace; a
project rename does not justify changing persistent knowledge identities.
Coordinate any unpublished downstream checkout or specialization migration in
its owning repository when the public repository location is created.

## Consequences

- The project gains a short, distinctive identity suitable for a repository,
  package, OCI image and site.
- Generic guidance and adopting-project knowledge remain free of branded domain
  vocabulary.
- Package and image coordinates change before the first release, so no
  compatibility shim is required.
- Existing unpublished downstream paths may retain their bootstrap locations
  until their owners perform a coordinated repository migration.
- Publication still requires human review of the complete baseline, repository
  protection and independent trademark clearance.
