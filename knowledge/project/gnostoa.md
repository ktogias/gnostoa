---
type: Project
title: Gnostoa
description: Self-description of Gnostoa, the generic project knowledge toolkit.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.project
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: contains
      target: /architecture/knowledge-surfaces.md
    - kind: governed-by
      target: /contracts/public-inheritance-surface.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
    - kind: implements
      target: /requirements/reviewed-change-control.md
    - kind: implements
      target: /requirements/verification-precedes-implementation.md
    - kind: implements
      target: /requirements/centralized-ci-verifies-integration-candidates.md
    - kind: contains
      target: /lifecycles/toolkit-evolution.md
---

# Gnostoa

Gnostoa provides a technology-neutral profile, validation tools, reusable
operating guidance and anonymous examples for Git-native project knowledge.

Gnostoa's public value is its complete reusable public surface: normative
profiles, policies and schemas; supporting validation tools and runtime
behavior; operating guidance, workflows and patterns; anonymous templates and
examples; and documented CI integration. The public contract binds these
artifacts into a coherent inheritance surface and versions that surface as a
unit. It defines what consumers may rely on, inherit or consult, while
preserving each artifact's distinct authority rather than making every artifact
equally normative.

Its internal design history and maintenance procedures stay in this
self-knowledge bundle so consumers do not pay for irrelevant context.
