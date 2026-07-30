---
type: Decision
title: Keep retrieval and agent-memory layers derived
description: Preserve canonical knowledge independently from optional retrieval systems.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.decision.0003.derived-retrieval
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /architecture/knowledge-surfaces.md
---

# Keep retrieval and agent-memory layers derived

## Context

Generated wikis, semantic indexes, temporal graphs and prompt caches can improve
navigation but can also become stale, opaque or expensive to synchronize.

## Decision

Generated wiki output, static sites, context packs, temporal graphs and
enterprise catalog ingestions are rebuildable projections of canonical
concepts and source artifacts.

## Consequences

- Replacing a retrieval system does not lose architectural knowledge.
- Generated facts require review before promotion.
- Pipelines need stable IDs and provenance to rebuild projections.
- Advanced retrieval is adopted only after workload-based measurement.
