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

One bounded experiment is active:
[#33 — deterministic read-only `READY` predicate](https://github.com/ktogias/gnostoa/issues/33),
testing the C4-v0 control selected by the closed research Work Item
[#31](https://github.com/ktogias/gnostoa/issues/31).
[Decision 0017](../knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md)
places that experiment in Gnostoa self-hosting, outside the public inherited
surface.

B2/P1 and B2/P2 are both complete. [Issue #24](https://github.com/ktogias/gnostoa/issues/24)
was integrated through [PR #28](https://github.com/ktogias/gnostoa/pull/28) and
closed as completed; its integration and closure are done, not pending. The
post-effect reconciliation ([#29](https://github.com/ktogias/gnostoa/issues/29),
[PR #30](https://github.com/ktogias/gnostoa/pull/30)) and the control-selection
research ([#31](https://github.com/ktogias/gnostoa/issues/31),
[PR #32](https://github.com/ktogias/gnostoa/pull/32)) are likewise closed.
**Provider state is authoritative for every Work Item lifecycle**; this page
asserts none.

Selecting a control is not admitting an implementation, a measured experimental
result is not success, and success would not be adoption. A negative result is a
valid outcome of #33. Nothing here promotes C4-v0 to the public inherited
surface, which would require a separate owner Decision.

This static projection cannot atomically observe its own future merge or
Work Item closure. It therefore describes the state that exists when it is
written, and defers to the provider for anything a later effect will change.

Later directions, including the P2 candidate directions and Decision 0016
increment 2, remain recorded and **not activated**.

## Completed boundary

[Issue #1](https://github.com/ktogias/gnostoa/issues/1) and cumulative PR #23
completed the protected public source baseline on 2026-08-16 at
`cda51dad6a719da43d8465a3f0f270021c357d96`. No package, image, documentation
site or hosted service was released by that effect.

## Next

B2/P1 completed 2026-08-16 ([PR #25–26](https://github.com/ktogias/gnostoa/pull/26)) with one validated task envelope and deterministic current projection delivered. B2/P2 completed 2026-08-17 under the closed [B2 experiment Work Item](https://github.com/ktogias/gnostoa/issues/24): a fresh actor resumed from the envelope alone, and the owner accepted the result while narrowing the product claim. That Work Item is the completed evidence base, not the container for later slices. Its named failed property is that critical workflow constraints are advisory rather than mechanically enforced. B2 reduced foreground evidence and provider-comment amplification, and orientation and final semantic review fit their bounded budgets in the measured cases; a total owner-effort improvement over B1 was **not** established. That framing is recorded, not activated. C4-v0 is now the selected control and is under bounded experiment in [#33](https://github.com/ktogias/gnostoa/issues/33). Once B2 is comprehensible, B3 tests transfer into an independently owned project. See [Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).

| Work Items | Problem addressed | Completion signal | Non-goal |
|---|---|---|---|
| [#33](https://github.com/ktogias/gnostoa/issues/33) | Critical workflow constraints remain advisory rather than mechanically enforced. The most recurrent observed path is readiness asserted while required preconditions are false. | The selected C4-v0 control is under bounded experiment: a deterministic, read-only `READY` predicate over existing evidence, scoped by [Decision 0017](../knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md) to Gnostoa self-hosting. The experiment reports whether the predicate refuses the recorded false-ready states without unacceptable false blocks, maintenance surface or human-attention cost. A negative result is a valid outcome and is not a failure of the Work Item. | Treating an experimental result as adoption, promoting C4-v0 to the public inherited surface without a separate owner Decision, expanding it into a state machine, workflow engine, capability broker or provider adapter layer, or nominating further controls before the experiment reports. |
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
[Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).
Issue #24 is the completed B2 evidence base rather than the current route; the
active bounded route is [Issue #33](https://github.com/ktogias/gnostoa/issues/33).

The work in PR #4 is retained here as an exact research input for #3. It is not
discarded, accepted or part of the first-publication baseline while its review
findings and merge conflicts remain unresolved.
