---
type: Pattern
title: Separate policy, reusable guidance and self knowledge
description: Prevent drift without injecting toolkit implementation details into consuming project context.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.pattern.policy-guidance-self-separation
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: applies-to
      target: /guardrails/non-negotiable.md
    - kind: guides
      target: /workflows/bootstrap-new-project.md
    - kind: guides
      target: /workflows/adopt-existing-project.md
---

# Separate policy, reusable guidance and self knowledge

## Context

Projects need consistent rules and reusable workflows, but loading the internal
architecture and maintenance history of the toolkit increases token use and
distracts from project work. Prose-only rules also drift because they depend on
memory and voluntary reading.

## Pattern

Maintain three surfaces with one-way dependencies:

1. **Core policy:** profiles, schemas, validators, tests and CI gates. Projects
   inherit this surface.
2. **Reusable guidance:** generic task-oriented OKF concepts. Developers and
   agents load one route on demand.
3. **Self knowledge:** implementation architecture, decisions and maintainer
   runbooks for the toolkit. Only toolkit maintainers load this surface.

Each important rule has:

- a canonical guidance statement;
- an enforcement classification;
- automated enforcement where mechanically possible;
- a test or review owner;
- a minimal router entry rather than a large injected prompt.

## Consequences

- Projects receive consistent validation without carrying toolkit internals in
  their active context.
- Generic practices remain discoverable and versioned.
- Some semantic rules still require review; the coverage manifest makes that
  boundary explicit.
- Maintainers must keep guidance, enforcement and tests linked through CI.
