---
type: Decision
title: Self-host with separate policy, guidance and self-knowledge
description: Keep reusable controls and advice separate from toolkit-internal knowledge.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.decision.0004.self-hosting-surfaces
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /architecture/knowledge-surfaces.md
    - kind: implements
      target: /requirements/prevent-policy-drift.md
---

# Self-host with separate policy, guidance and self-knowledge

## Context

The toolkit must retain its own rationale and maintenance knowledge while
giving consuming projects generic rules and practices. Copying all toolkit
documentation into every project increases context size, leaks implementation
details and creates multiple drifting copies.

## Decision

Use the toolkit on itself, but divide knowledge into three surfaces:
machine-enforceable policy, reusable task-routed guidance and a separate
toolkit-only OKF bundle. Connect guardrails to their guidance, implementation
and tests through a coverage manifest checked by CI.

Consuming projects inherit the public policy, consult relevant guidance and
maintain their own project bundle. They do not inherit toolkit self-knowledge.

## Consequences

Toolkit knowledge is validated with the same mechanisms it promotes. Consumer
context remains bounded. Changes require explicit classification: generic
policy, reusable guidance, toolkit-internal knowledge or project
specialization. The repository must maintain routing and coverage checks as
part of its public contract.
