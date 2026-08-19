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

The bounded C4-v0 experiment
([#33](https://github.com/ktogias/gnostoa/issues/33)) has **completed with a
negative result**, and the owner has **rejected C4-v0 as a readiness predicate**.
The strict hypothesis was refuted: 3 of 8 reconstructed false-ready states were
mechanically rejected, none was wrongly called ready, and all 4 owner-accepted
positive controls failed to reach READY. **Provider state remains authoritative
for #33's lifecycle**; this page does not assert or predict it.

One narrower result is retained as evidence: deterministic consistency checks
over existing evidence can detect some important state and identity defects
before human review. It is **recorded and not activated**, and it is not a
replacement control. The rejected implementation is not retained;
[Decision 0017](../knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md),
which kept the whole experiment outside the public inherited surface, remains in
force.

**No successor control experiment or mitigation is selected.**

Post-C4 evidence-boundary selection research
([#35](https://github.com/ktogias/gnostoa/issues/35)) has reported. **No evidence
primitive was selected.** The owner selected a **smaller precursor experiment**:
test whether Gnostoa can reliably route its already-existing deterministic
declared-identity consistency check before owner review, with no new evidence
primitive and no new validation semantics. **Implementation is not admitted**,
and no implementation Work Item exists. That precursor's public-surface impact is
**unknown** until it identifies its concrete routing location and reclassifies
the actual diff; if reliable routing requires a public CI, policy, schema or
supported-tool change, it stops before implementation for a separate owner
disposition.

The three researched evidence primitives — an exact-candidate verification
receipt, a reproducible external-dependency witness, and bounded obligation
completeness — remain **recorded and not activated**.

The operating method itself was then canonicalized
([#37](https://github.com/ktogias/gnostoa/issues/37),
[PR #38](https://github.com/ktogias/gnostoa/pull/38)) so a fresh agent can find
it through the ordinary entry route, and the fresh-agent dogfood test attached to
it **has now been run**.

Bounded result: the canonical route **supports** discovery, bounded orientation,
selection-versus-admission reconstruction, entrance-gate discovery and
stop-before-implementation behaviour; it does **not** establish autonomous
semantic correctness, and bounded owner semantic review remained materially
necessary. Both agents ran against Gnostoa itself, so no transfer to an
independently owned project is established.

In the same experiment the **routing precursor was refuted at its entrance gate,
before implementation**, and is **rejected as posed**. The existing checker
consumes caller-supplied observations whose authoritative derivation and binding
are undefined, and no existing non-public review boundary makes the check
unavoidable. No precursor implementation Work Item was ever created and no
executable precursor was retained.

One new failed property is recorded, with its two boundaries kept apart:
observation acquisition and binding, and review-boundary routing and enforcement.
**No successor mechanism is selected or activated**, and naming the boundaries
selects nothing.

Separately,
[Decision 0020](../knowledge/decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md)
selected **`v0.1.0` as the source-only pre-stable release identity**, and it was
executed through the authorized provider effect under
[Work Item #43](https://github.com/ktogias/gnostoa/issues/43): `v0.1.0` names the
immutable commit `ee808572d3930ec3dc50d350ae1ed25a0236bb6b`. Mutable provider
Release metadata stays authoritative at the provider and is intentionally not
restated in this static roadmap. **No package, OCI-image or documentation-site
publication accompanied it**, and each remains a separate unperformed effect. See
the [release result](../knowledge/assessments/first-source-only-release-result.md).

That lifecycle is now captured as a bounded Gnostoa-self procedure
([#48](https://github.com/ktogias/gnostoa/issues/48)):
[Decision 0021](../knowledge/decisions/0021-adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance.md)
adopts it as the **draft default for future source-only releases**, encoded in
[Publish a source-only release](../knowledge/runbooks/publish-source-only-release.md).
It is self-only, promotes nothing to adopter guidance, selects no mechanism, and
authorizes no further release or artifact publication.

[Work Item #50](https://github.com/ktogias/gnostoa/issues/50) completed the first
OCI runtime security and residual-risk publication boundary through
[Decision 0022](../knowledge/decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md),
which **authorizes no OCI publication and granted no security exception**. Under
its vendor-fixed-component rule the current measured OCI candidate is **not
admitted** for publication until the demonstrated blocker is remediated or a
separate explicit exception is authorized. Bounded remediation of that
blocker is tracked by [Work Item #54](https://github.com/ktogias/gnostoa/issues/54)
under [Decision 0023](../knowledge/decisions/0023-apply-the-supported-debian-util-linux-security-update-to-the-oci-runtime.md),
which authorizes **no OCI publication**. Provider state remains authoritative for
that Work Item's lifecycle.

B2/P1 and B2/P2 are both complete. [Issue #24](https://github.com/ktogias/gnostoa/issues/24)
was integrated through [PR #28](https://github.com/ktogias/gnostoa/pull/28) and
closed as completed; its integration and closure are done, not pending. The
post-effect reconciliation ([#29](https://github.com/ktogias/gnostoa/issues/29),
[PR #30](https://github.com/ktogias/gnostoa/pull/30)) and the control-selection
research ([#31](https://github.com/ktogias/gnostoa/issues/31),
[PR #32](https://github.com/ktogias/gnostoa/pull/32)) are likewise closed.
**Provider state is authoritative for every Work Item lifecycle**; this page
asserts none.

Selecting a control was not admitting an implementation, and the measured result
was not success. A negative result is a valid outcome, and #33 is not reopened,
rescued or expanded because of it. Nothing here promotes anything to the public
inherited surface, which would require a separate owner Decision.

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

B2/P1 completed 2026-08-16 ([PR #25–26](https://github.com/ktogias/gnostoa/pull/26)) with one validated task envelope and deterministic current projection delivered. B2/P2 completed 2026-08-17 under the closed [B2 experiment Work Item](https://github.com/ktogias/gnostoa/issues/24): a fresh actor resumed from the envelope alone, and the owner accepted the result while narrowing the product claim. That Work Item is the completed evidence base, not the container for later slices. Its named failed property is that critical workflow constraints are advisory rather than mechanically enforced. B2 reduced foreground evidence and provider-comment amplification, and orientation and final semantic review fit their bounded budgets in the measured cases; a total owner-effort improvement over B1 was **not** established. That framing is recorded, not activated. C4-v0 was experimented with under [#33](https://github.com/ktogias/gnostoa/issues/33) and rejected as a readiness predicate; no successor control is selected. Once B2 is comprehensible, B3 tests transfer into an independently owned project. See [Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).

| Work Items | Problem addressed | Completion signal | Non-goal |
|---|---|---|---|
| [#35](https://github.com/ktogias/gnostoa/issues/35) | The C4-v0 falsification left open whether any small missing evidence primitive would convert one materially important observed undecidability into reproducible, candidate-bound evidence. | **Reported.** Eight evidence boundaries reconstructed and separated from fundamental oracle limits; three candidate primitives compared, none demonstrated at its own boundary. The owner selected **none of them**, choosing instead a smaller precursor experiment that routes an existing check. That precursor was later **refuted at its entrance gate before implementation** and is rejected as posed; see [#39](https://github.com/ktogias/gnostoa/issues/39). | Implementing any evidence primitive, rescuing the refuted precursor with an ID-to-path convention, automatic reference resolution, a schema change, an observation binding, public CI or tool changes, or a test presented as review-boundary enforcement; or activating E1, E2, E3, C2, C3 or Decision 0016 increment 2. |
| [#33](https://github.com/ktogias/gnostoa/issues/33) | Critical workflow constraints remain advisory rather than mechanically enforced. The most recurrent observed path is readiness asserted while required preconditions are false. | **Reported.** The C4-v0 experiment ran under [Decision 0017](../knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md) and its strict hypothesis was refuted; the owner accepted the experimental result and **rejected C4-v0 as a readiness predicate**. Retained as evidence only: deterministic consistency checks over existing evidence can detect some state and identity defects before human review — recorded, not activated. The failed property itself is unmitigated and no successor is selected. | Treating an experimental result as adoption, promoting C4-v0 to the public inherited surface without a separate owner Decision, expanding it into a state machine, workflow engine, capability broker or provider adapter layer, or nominating further controls before the experiment reports. |
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
Issue #24 is the completed B2 evidence base, and [Issue #33](https://github.com/ktogias/gnostoa/issues/33)
is the completed C4-v0 experiment whose control was rejected. No bounded route is
currently selected.

The work in PR #4 is retained here as an exact research input for #3. It is not
discarded, accepted or part of the first-publication baseline while its review
findings and merge conflicts remain unresolved.
