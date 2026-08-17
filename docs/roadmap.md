# Product and delivery roadmap

This MkDocs page is a derived navigation projection. Canonical lifecycle
principles remain in [Toolkit evolution](../knowledge/lifecycles/toolkit-evolution.md),
while this page presents the current delivery order for Gnostoa itself.

The categories are priorities, not acceptance or effectiveness states. Open
Work Items remain open until their own lifecycle completes. Closed historical
records are labelled explicitly, and none is a first-publication blocker unless
a concrete security, legal, correctness or exposure finding demonstrates that
dependency.

## Now

| Work | User and problem | Falsifiable outcome | Dependencies | Explicit non-goal |
|---|---|---|---|---|
| [#24 — B2/P2 stale-state reconciliation](https://github.com/ktogias/gnostoa/issues/24) | A fresh session or agent must resume P2 work without task state loss or context drift after P1 completion. | Decision 0016 resume card, docs/roadmap.md Now/Next sections and docs/status.md Current direction reconciled to reflect P1 completion at commit 7390976; Issue 24 roadmap:next label assessed for accuracy. Complete reconciliation fits 300–500 changed lines, verifying fresh-actor resume from task envelope alone. | P1 completed at commit 7390976 ([PR #25–26](https://github.com/ktogias/gnostoa/pull/26)); Task envelope `tasks/issue-24-b2-p2.yaml` at declared interruption point. | B2 increment 2 implementation, task-envelope schema redesign, provider metadata mutation. |

## Completed boundary

[Issue #1](https://github.com/ktogias/gnostoa/issues/1) and cumulative PR #23
completed the protected public source baseline on 2026-08-16 at
`cda51dad6a719da43d8465a3f0f270021c357d96`. No package, image, documentation
site or hosted service was released by that effect.

## Next

B2/P1 completed 2026-08-16 ([PR #25–26](https://github.com/ktogias/gnostoa/pull/26)) with one validated task envelope and deterministic current projection delivered. P2 reconciles stale current-state and resume surfaces, measuring whether a fresh actor can resume from the envelope alone. Following P2, only a measured bottleneck may activate a later B2 slice. Once B2 is comprehensible, B3 tests transfer into an independently owned project. See [Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).

| Work Items | Problem addressed | Completion signal | Non-goal |
|---|---|---|---|
| [Later B2 slices](https://github.com/ktogias/gnostoa/issues/24) | Handoff, bounded execution plans and invalidation need implementation only where P1 demonstrates a measurable bottleneck. | P1 retains defect detection and recovery while reducing owner effort; the next slice has one named failed property. | Expanding the complete workflow roadmap by default. |
| [#6](https://github.com/ktogias/gnostoa/issues/6), [#9](https://github.com/ktogias/gnostoa/issues/9), [#13](https://github.com/ktogias/gnostoa/issues/13) | Admission, effect gating, context selection and canonical-language handling need bounded contracts only where B2 demonstrates actual need. | B2 identifies a concrete repeated failure or dependency and a smallest enforceable contract. | Making every proposed contract an implementation prerequisite for B2. |
| [#7](https://github.com/ktogias/gnostoa/issues/7) | External evaluation needs a safe, reproducible workspace boundary. | One anonymous adoption fixture runs with declared ownership, hermetic inputs and no host-data leakage. | Claiming broad external adoption or production isolation from a single fixture. |

## Research

These items contain useful designs and evidence. Their underlying capability
need is demonstrated, but their minimum implementation and sequencing remain
experimental. They stay outside the first-publication critical path while B2
selects the smallest safe slices.

| Work Items | Research question | Promotion condition |
|---|---|---|
| [#3](https://github.com/ktogias/gnostoa/issues/3), [#5](https://github.com/ktogias/gnostoa/issues/5), [#8](https://github.com/ktogias/gnostoa/issues/8) | What is the smallest durable task-context, crash-recovery and asynchronous-waiting slice that addresses the already observed B1 failures? | Publication is complete and B2 isolates one bounded contract with interruption, stale-state and recovery evidence. |
| [#10](https://github.com/ktogias/gnostoa/issues/10), [#11](https://github.com/ktogias/gnostoa/issues/11), [#14](https://github.com/ktogias/gnostoa/issues/14) | Which role, semantic-capture and goal-alignment projections improve decisions without becoming a second authority? | A bounded experiment demonstrates measurable orientation or reconciliation benefit with deterministic regeneration. |
| [#15](https://github.com/ktogias/gnostoa/issues/15) | Which workflow mechanics can be automated without automating evidence amplification or weakening review? | B2 identifies stable repeated mechanics, explicit effect boundaries and a falsifiable reduction target. |

[Issue #12](https://github.com/ktogias/gnostoa/issues/12) is a closed historical
B1 design and dogfood ledger. Its 342 comments remain inspectable evidence of
both defect discovery and excessive amplification; the broad guided-review
platform is deferred to Research and is not the contributor interface or an
active publication prerequisite. The capability direction remains planned by
[Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md),
and Issue #24 is the bounded implementation route.

The work in PR #4 is retained here as an exact research input for #3. It is not
discarded, accepted or part of the first-publication baseline while its review
findings and merge conflicts remain unresolved.
