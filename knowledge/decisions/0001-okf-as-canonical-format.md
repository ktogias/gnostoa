---
type: Decision
title: Use OKF v0.2 as the canonical knowledge format
description: Keep project knowledge portable, reviewable and service-independent.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format specification
x-project-knowledge:
  id: kit.decision.0001.okf-canonical
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /contracts/public-inheritance-surface.md
---

# Use OKF v0.2 as the canonical knowledge format

## Context

Project knowledge must be readable by developers and agents, reviewable in Git,
portable between tools and usable without a running service.

## Decision

Use OKF v0.2: Markdown concepts with YAML frontmatter, directory indexes,
cross-links, provenance, verification and lifecycle metadata.

## Consequences

- Knowledge can be reviewed with normal source-control workflows.
- Project profiles add domain constraints because OKF is minimally opinionated.
- Search engines, graph databases and enterprise catalogs remain projections.
- The kit tracks future OKF revisions explicitly.
