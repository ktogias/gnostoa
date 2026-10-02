---
type: Decision
title: Route the architecture-inheritance entrance gate from source
description: Carry the owner's fail-closed architecture-inheritance gate into the agent router and the delivery runbook's prior-art checkpoint now, with a guardrail and conformance tests, instead of waiting for the rest of MA0.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-03T00:00:00Z"
sources:
  - id: gate
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5919462524
    title: Mandatory implementation entrance gate, architecture inheritance (2026-09-30)
  - id: checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5919281149
    title: Ariadne v9 cross-cutting addendum, architecture inheritance checkpoint
  - id: ma0-guard
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5919463947
    title: MA0 exit includes source activation of architecture inheritance
  - id: incident
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5961727761
    title: Ariadne incident addendum, review pipeline built coupled again
  - id: proposal
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5961728051
    title: Proposal P2, activate the gate's routing independently of VF0
  - id: admission
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5961974820
    title: Owner admits P2
x-project-knowledge:
  id: kit.decision.0099.route-the-architecture-inheritance-gate-from-source
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# Route the architecture-inheritance entrance gate from source

## Context

On 2026-09-30 the owner made architecture inheritance a mandatory, fail-closed
entrance gate for every Gnostoa-self implementation slice
([#15 5919462524](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5919462524)).
Before the first semantic production mutation, the slice must dispose every material
responsibility against its existing owner. The guard that followed
([#14 5919463947](https://github.com/ktogias/gnostoa/issues/14#issuecomment-5919463947))
placed the gate's source activation inside MA0, behind VF0 and PR #319.

PR #319 is still open, so the gate lived only in provider comments. An agent whose
route reads source and the comments it is pointed to never met it. PRs #340 and #353
proceeded without the table. The Claude review pipeline, about 4,150 lines on `main`,
was built GitHub- and Claude-coupled. The owner had to restate an invariant that was
already decided, for the second time after #285.
[Incident addendum](https://github.com/ktogias/gnostoa/issues/14#issuecomment-5961727761).

The owner admitted proposal P2 on 2026-10-03: activate the gate's routing now,
independently of VF0.

## Prior-art and reuse disposition

This slice's own lineage table:

| responsibility | existing owner | existing implementation/contract | disposition | proof/falsifier |
|---|---|---|---|---|
| decide reuse before custom work | the delivery runbook | its prior-art and reuse checkpoint | **extend**: the gate is a subsection of it, not a second lifecycle | the runbook test checks that the gate sits inside the checkpoint |
| make a self-only obligation discoverable and owned | the `bounded-behavioral-traceability` guardrail pattern | an `AGENTS.md` route, a runbook step, a guardrail entry and route tests | **consume** the pattern: the same guardrail shape, `hybrid` enforcement and route tests | `test_guardrail_binds_the_gate` |
| the gate's rule text | the owner's gate (5919462524) | provider comment | **consume**: carried in substance, with its source linked | the runbook test checks the table, each disposition, the fail-closed stop and the source |
| check that a slice actually applied the gate | the reviewer, under the existing checkpoint | review enforcement | **unchanged**: no software gate | none claimed |

No external tool was adopted. The need is routing an existing rule to where agents
act. An architecture-rule engine, a registry or a Pull Request parser would be the
"separate architecture-governance engine" that the 2026-09-30 addendum rules out.

## Decision

1. `AGENTS.md` routes the gate to the delivery runbook. It is stated before the first
   semantic production mutation of any Gnostoa-self implementation slice, with its
   fail-closed stop.
2. The delivery runbook carries the gate as a subsection of the existing prior-art and
   reuse checkpoint. It holds the table, each disposition's meaning, the fail-closed
   rule, the trust-boundary exception and the owner's source.
3. **Incremental orientation.** Before the first semantic production mutation, and
   before writing to #14 or #15, the agent reads every entry posted to them since the
   one it last read. Owner gates reach those threads before source, and reading only
   pointed-to comments is how this gate was missed.
4. **Revisit triggers.** The table is redone when a slice's responsibilities change.
   The runbook names these as triggers:
   - a third hardening round on one file;
   - decision logic accumulating under a provider-specific directory;
   - a question about where a responsibility belongs.
5. The guardrail `architecture-inheritance-gate` binds the router, the runbook, this
   Decision and the index, and five conformance tests.
6. **Scope boundary.** This activates only the routing part of MA0's
   architecture-inheritance item. The merge-admission and close-last fence, the
   roadmap and orientation refresh, and the integrated-main read-back stay in MA0 as
   the guard placed them. No CI gate parses Pull Requests for the table.

## Consequences

- An agent following `AGENTS.md` now meets the gate before it mutates code, and it is
  told to read the governing threads incrementally.
- The conformance tests prove that the gate is routed, not that a slice applied it.
  Application remains review enforcement. That is the boundary the first retrospective
  drew: a word check is a guard, not an oracle.
- The router grows by one paragraph.

## Verification

`tests/test_architecture_inheritance_gate.py` failed first: five tests, with no route,
no subsection, no guardrail and no Decision. It now passes. The tests pin:
- the router's route and its fail-closed wording;
- the subsection's place inside the prior-art checkpoint;
- the table, the six dispositions and the source;
- the incremental-orientation and revisit rules;
- the guardrail's exact implementation and test set;
- this Decision's draft status and index entry.
