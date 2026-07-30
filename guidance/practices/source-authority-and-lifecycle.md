---
type: Practice
title: Source authority and knowledge lifecycle
description: Preserve evidence, uncertainty and supersession instead of allowing generated summaries to become accidental truth.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.practice.source-authority-and-lifecycle
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/adopt-existing-project.md
    - kind: guides
      target: /workflows/daily-change-loop.md
    - kind: applies-to
      target: /guardrails/non-negotiable.md
---

# Source authority and knowledge lifecycle

## Intent

Make it mechanically and socially difficult for stale, inferred or generated
claims to appear authoritative.

## Rule

- Inventory sources before synthesis.
- Define project-specific source precedence.
- Start generated or inferred concepts as `draft`.
- Require human verification for `stable`.
- Use `stale_after` for volatile facts.
- Represent contradictions explicitly.
- Deprecate and link superseded concepts instead of deleting history.
- Keep current state, target state and proposals distinct.

## Application

Prefer accepted standards and decisions, executable contracts and verified
implementation evidence over meeting records and generated summaries. The
project profile documents justified variations in precedence. Team ownership
belongs in `x-project-knowledge.owners`; individual actors belong in
`generated` and `verified`.

## Verification

For any stable claim, a reviewer can identify its verifier, source or decision,
freshness and replacement history. An agent encountering conflicting evidence
reports the conflict rather than inventing a resolution.
