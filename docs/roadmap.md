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
| [#1 — First public source baseline](https://github.com/ktogias/gnostoa/issues/1) | A new evaluator needs one trustworthy repository rather than a stacked internal review ledger. | One protected public `main` exposes the bounded source candidate, a working five-minute path, truthful status and a current disclosure record. | Publication cleanup, exact cumulative review, name-risk disposition, provider-surface GO and protection before merge. | Publishing packages, images or a hosted service. |

## Next

The next experiment is B2: use one small Gnostoa change to preserve the current
assurance while materially reducing owner time, review rounds and evidence
amplification. B1 has already demonstrated the need for guided review, durable
task context, bounded plans, explicit handoffs and safe resume. These are
planned post-publication capabilities; B2 selects the minimum sufficient
implementation rather than asking whether the need exists. Only after B2 is
comprehensible does B3 test transfer into an independently owned project. See
[Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).

| Work Items | Problem addressed | Completion signal | Non-goal |
|---|---|---|---|
| [#24 — B2 streamlined self-hosting](https://github.com/ktogias/gnostoa/issues/24) | B1 found real defects and demonstrated workflow/recovery needs, but required 407 comments across its two main ledger threads. | One small predeclared Gnostoa change dogfoods the smallest task-envelope/current-projection/checkpoint slice and completes with exact recovery and no escaped defect while owner actions, review rounds and evidence amplification fall materially below B1. | Automating the historical ledger or building the complete workflow platform. |
| [#6](https://github.com/ktogias/gnostoa/issues/6), [#9](https://github.com/ktogias/gnostoa/issues/9), [#13](https://github.com/ktogias/gnostoa/issues/13) | Admission, context selection and canonical-language handling need bounded contracts only where B2 demonstrates actual need. | B2 identifies a concrete repeated failure or dependency and a smallest enforceable contract. | Making every proposed contract an implementation prerequisite for B2. |
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
