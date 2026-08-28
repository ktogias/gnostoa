---
type: Decision
title: Require lightweight Work Item micro-retrospection
description: Add a five-question close-out reflection and a resume-before-create check to ordinary Gnostoa-self delivery without requiring a formal retrospective artifact for every slice.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-28T17:39:00+03:00"
sources:
  - id: retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/153
    title: Retrospect the v0.2.0 release series and staged-evidence transition
  - id: release-retrospective
    resource: ../assessments/v0-2-0-release-series-and-staged-evidence-retrospective.md
    title: v0.2.0 release-series and staged-evidence transition retrospective
  - id: duplicate-retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/155
    title: Duplicate v0.2.0 retrospective Work Item
  - id: duplicate-retrospective-pr
    resource: https://github.com/ktogias/gnostoa/pull/156
    title: Superseded duplicate retrospective candidate
x-project-knowledge:
  id: kit.decision.0053.require-lightweight-work-item-micro-retrospection
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: derived-from
      target: /assessments/v0-2-0-release-series-and-staged-evidence-retrospective.md
    - kind: updates
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Require lightweight Work Item micro-retrospection

## Context

The `v0.2.0` release series produced useful negative and corrective evidence, but
several findings arrived late and required repeated candidate replacement and
re-verification. During the retrospective itself, Work Item #153 and PR #154
already owned the outcome when duplicate Work Item #155 and PR #156 were created.
The duplicate path was later closed without merge.

That incident is evidence of the same failure family: current provider state was
not re-read before creating another coordination record, so reflection itself
amplified the evidence and review surface.

## Decision

### A. End every bounded Work Item with a micro-retrospective

At close-last reconciliation, record concise answers to five questions:

1. What was expected?
2. What actually happened?
3. What was surprising or detected late?
4. Which existing control worked or failed to activate?
5. Is there one concrete improvement worth considering for a later cycle?

The answers normally live in the Work Item close-out comment. They do **not**
require a new assessment, Decision, PR or formal RCA.

A micro-retrospective records learning; it does not automatically admit the
suggested improvement. Any implementation still follows the ordinary evidence,
selection, classification and admission route.

### B. Resume before creating a competing work record

Before creating a new Gnostoa-self Work Item or PR for an outcome, read provider
state for an existing open same-purpose Work Item or candidate. When one already
owns the outcome, resume or update it. If a materially different path is needed,
explicitly supersede or separate the existing path before creating a competing
canonical candidate.

This is a routing/read-back rule, not a duplicate-detection engine. No new bot,
checker, provider adapter or state machine is selected.

### C. Keep formal retrospectives separately admitted

This Decision does not require a canonical retrospective document for each Work
Item and does not define a universal P0/P1/P2 taxonomy or mandatory formal-RCA
trigger set. A deeper retrospective remains a separate owner-selected activity
when the release, incident, repeated rework or unresolved learning warrants it.

## Consequences

- Small slices gain a durable learning loop with negligible document overhead.
- The provider is re-read before creating another coordination object for the
  same outcome.
- Retrospective findings remain evidence, not automatic implementation scope.
- The duplicate #155/#156 incident is retained as the falsification that motivated
  the resume-before-create clarification.
- No owner-led trial, Mail mutation, upstream outreach, release effect or backlog
  implementation is authorized by this Decision.
