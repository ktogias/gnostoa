---
type: System
title: Knowledge surfaces
description: Separation of enforceable policy, reusable guidance and toolkit self-knowledge.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.system.knowledge-surfaces
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /contracts/public-inheritance-surface.md
    - kind: derived-from
      target: /decisions/0004-self-host-policy-guidance-and-knowledge.md
---

# Knowledge surfaces

The repository exposes three independently loadable surfaces:

1. `core/`, schemas, tools and CI implement enforceable generic profile and
   change-control plus continuous-integration policy.
2. `guidance/` contains reusable patterns and workflows selected by task.
3. `knowledge/` describes this toolkit and is loaded only for toolkit work.

Anonymous examples and templates demonstrate the contract without introducing
a real project's names, taxonomy or architecture.
