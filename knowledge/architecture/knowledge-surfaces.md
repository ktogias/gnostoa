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
    - kind: derived-from
      target: /decisions/0015-adopt-bounded-execution-plans-and-explicit-handoffs.md
---

# Knowledge surfaces

The repository exposes three independently loadable surfaces:

1. `core/`, schemas, tools, CI adapters and templates implement the enforceable
   generic profile plus change-control and continuous-integration policy.
2. `guidance/` contains reusable patterns and workflows selected by task.
3. `knowledge/` describes this toolkit and `policy/` specializes its own
   operation. Both are loaded only for toolkit work.

Anonymous examples and templates demonstrate the contract without introducing
a real project's names, taxonomy or architecture.

`plans/` is bounded operational state for active Gnostoa changes. It is neither
a fourth canonical knowledge bundle nor a consumer inheritance surface. A plan
links the three surfaces and repository evidence only for the lifetime of a
change.
