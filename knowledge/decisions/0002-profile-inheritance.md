---
type: Decision
title: Extend profiles instead of copying the core
description: Use monotonic inheritance to scope vocabulary and reduce upgrade drift.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.decision.0002.profile-inheritance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /contracts/public-inheritance-surface.md
---

# Extend profiles instead of copying the core

## Context

Different projects and modules need their own vocabulary, but copied schemas and
templates drift and make upgrades expensive.

## Decision

Use monotonic profile inheritance: generic core, project extension and optional
project-area or module specialization.

## Consequences

- Generic improvements propagate through reviewed profile upgrades.
- Project and module rules remain visibly scoped.
- Children may become stricter but may not silently remove parent rules.
- Parent changes require validation of representative descendants.
