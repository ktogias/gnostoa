---
type: Failure Mode
title: Reverse-centaur review overload
description: Failure mode in which agents amplify evidence and frame decisions faster than an accountable human can understand and control them.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-16T00:00:00Z"
sources:
  - id: historical-guided-review-ledger
    resource: https://github.com/ktogias/gnostoa/issues/12
    title: Historical B1 guided-review design and dogfood ledger
  - id: streamlined-self-hosting-experiment
    resource: https://github.com/ktogias/gnostoa/issues/24
    title: Run one bounded B2 streamlined self-hosting experiment
x-project-knowledge:
  id: kit.failure-mode.reverse-centaur-review-overload
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /assessments/human-agent-governance-scope-and-evolution.md
    - kind: conflicts-with
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
---

# Reverse-centaur review overload

## Resume card

| Field | Current state |
|---|---|
| Pattern | Agents preserve and expand evidence while the human becomes a confirmer of agent-framed meaning rather than an effective controller. |
| Observed signal | B1 found material defects but required 407 comments across its two main ledger threads and repeated approval-shaped recording steps. |
| Safety response | Present one bounded delta, consequence and uncertainty; ask once per semantic choice; pause when the owner cannot explain the effect. |
| B2 test | One canonical task envelope, one derived current projection, an explicit attention budget and exact stale-state failure. |

## Detection signals

- The reviewer cannot restate the exact choice and its principal consequence.
- The same semantic choice is presented through repeated approval prompts.
- Evidence volume grows faster than the normative or executable delta.
- Resuming requires replay of raw conversations rather than one current state.
- Agent summaries blend analysis, authority and acceptance.
- A nominal approval occurs after the declared review budget is exhausted.

## Root causes and effects

Append-only durability was optimized without an equally strong current-view,
attention or stop constraint. Deterministic recording was coupled to semantic
approval, and correlated agents kept adding assurance cases after the
owner-facing decision stopped becoming clearer. The resulting ledger improved
local traceability but delayed delivery, increased token and attention cost and
made false-ready approval through non-understanding more likely.

## Prevention and recovery

1. Keep one canonical bounded task state and one replaceable current
   projection. Link detailed evidence instead of copying its body.
2. Foreground the exact delta, intended effect, strongest uncertainty and one
   next action. Use progressive disclosure for mechanics.
3. Ask for one human decision per genuine semantic choice. Validation,
   recording, read-back and deterministic reconstruction of that effect are
   not additional approvals.
4. Declare a review-surface and owner-attention budget before review. When the
   owner cannot explain the effect inside it, record `blocked`, clarify or split
   the change; do not infer consent.
5. On interruption or drift, verify the bound base and dependencies and
   regenerate the current projection. Never replay the whole ledger by default.

## Measures

B2 records approval prompts per semantic decision, active owner review time,
review rounds, evidence words per changed normative line, recovery time,
corrections caused by misunderstood scope and false-ready/false-block results.
A smaller ledger is not sufficient if it hides evidence or weakens defect
detection; a larger ledger is not success when the owner loses comprehension.

## Claim and authority boundary

This agent-authored failure-mode record does not diagnose an individual or
replace human semantic review. It does not prove that the B2 remedy is
sufficient, make an approval effective or authorize an external effect. It is
a falsifiable product and process risk routed through Issue #24.
