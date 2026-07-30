---
type: Decision
title: Keep processing behind a stable boundary
description: Consumers depend on a stable contract rather than implementation details.
status: stable
generated:
  by: human:example-maintainer
  at: "2026-07-29T12:00:00Z"
verified:
  by: human:example-reviewer
  at: "2026-07-29T12:30:00Z"
x-project-knowledge:
  id: example.decision.processing-boundary
  owners:
    - team:example
  relations:
    - kind: governs
      target: /systems/processing-system.md
---

# Keep processing behind a stable boundary

## Context

Consumers should not need to understand internal processing choices.

## Decision

Expose processing through a stable, versioned contract.

## Consequences

Internal implementations may change independently, while contract evolution
requires compatibility review.

