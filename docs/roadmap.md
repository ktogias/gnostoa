# Product and delivery roadmap

This MkDocs page is a derived navigation projection. Canonical lifecycle
principles remain in [Toolkit evolution](../knowledge/lifecycles/toolkit-evolution.md),
while this page presents the current delivery order for Gnostoa itself.

The categories are priorities, not acceptance or effectiveness states. Open
Work Items remain open until their own lifecycle completes. Closed historical
records are labelled explicitly, and none is a first-publication blocker unless
a concrete security, legal, correctness or exposure finding demonstrates that
dependency.

The strict
[B3 independent-adoption methodology](../knowledge/assessments/b3-independent-adoption-experiment-design.md)
remains pre-registered as a later maturity-stage `INDEPENDENT` evidence
method. Four autonomous Nextcloud Mail adoption attempts remain historical
controlled pre-B3 evidence, with their original `REJECT` / `UNKNOWN` / `NO`
dispositions unchanged.

[Decision 0052](../knowledge/decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md)
now governs early-product evidence through staged classes. The `v0.2.0`
source and OCI artifact are published and their digest-bound release
reconciliation is complete. For
[Work Item #146](https://github.com/ktogias/gnostoa/issues/146), the final
release-series experiment boundary is integration and provider read-back of
the
[Nextcloud Mail `OWNER-LED` baseline](../knowledge/assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md).
The concrete owner-led task run, preliminary assessment and retrospective are
later separate work; upstream feedback is additive, and strict
`INDEPENDENT` evidence is deferred to a separately admitted maturity-stage
activity. `ktogias/mail` remains the local mutation workspace and
`nextcloud/mail` retains Issue and final Change Request authority. Live
lifecycle remains provider-authoritative.

## Now

**Which Work Item is currently selected, if any, is provider state — not a
statement on this page.** Read it from the provider: the open Work Item carrying
the `roadmap:now` label, of which there may be none. This page records what each
completed slice established; it never asserts that a Work Item is active, open or
pending.

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
primitive was selected.** The owner instead selected a **smaller precursor
experiment**: test whether Gnostoa can reliably route its already-existing
deterministic declared-identity consistency check before owner review, with no new
evidence primitive and no new validation semantics. That precursor was **never
admitted for implementation**, and no implementation Work Item was ever created.
Its public-surface impact was never determined, because it was **refuted at its
entrance gate** before it identified a concrete routing location — see below. That
#35 selection is therefore spent: it authorizes nothing further, and no successor
may proceed under it.

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

[Work Item #50](https://github.com/ktogias/gnostoa/issues/50) established the
first OCI runtime security and residual-risk publication boundary through
[Decision 0022](../knowledge/decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md),
which **authorizes no OCI publication and granted no security exception**.
[Work Item #54](https://github.com/ktogias/gnostoa/issues/54) subsequently
completed the bounded util-linux remediation under
[Decision 0023](../knowledge/decisions/0023-apply-the-supported-debian-util-linux-security-update-to-the-oci-runtime.md).
Its candidate-bound
[remediation result](../knowledge/assessments/util-linux-security-remediation-result.md)
records that the demonstrated vendor-fixed util-linux blocker **was cleared for
the measured `linux/amd64` candidate**. That measured result establishes **no**
complete OCI readiness or image security, and Decision 0023 authorizes **no OCI
publication**. Every other OCI gate named in Decision 0022 remains untouched.
Provider state remains authoritative for Work Item lifecycle.

Under [Work Item #58](https://github.com/ktogias/gnostoa/issues/58),
[Decision 0025](../knowledge/decisions/0025-define-supported-update-channel-semantics-for-base-bundled-oci-components.md)
supplemented Decision 0022 for a fact pattern it did not resolve explicitly: a
non-dpkg component delivered through an official base bundle whose maintainer
offers a different, also officially supported, fixing route. It selects the
**component-maintainer supported-update reading** under seven qualifying criteria,
and records that the measured `pip 25.0.1` fact pattern **triggers Decision
0022/D**, so that measured candidate is not admitted for first publication absent
remediation or a separately authorized explicit exception. Its candidate-bound
[evidence record](../knowledge/assessments/pip-security-provenance-and-update-channel-evidence.md)
holds the provenance, advisory and channel observations. **Decision 0025 selects no
remediation shape, grants no security exception and authorizes no OCI
publication.** Provider state remains authoritative for Work Item lifecycle.

Under [Work Item #60](https://github.com/ktogias/gnostoa/issues/60),
[Decision 0026](../knowledge/decisions/0026-define-effective-runtime-component-presence-for-layered-oci-publication.md)
supplemented Decisions 0022 and 0025 with the layered-image component-presence
semantics they left implicit. It selects **effective merged-runtime component
state**: a component counts as shipped when its affected code is present in the
merged filesystem of the published runtime image after normal OCI layer
application. Bytes retained only in ancestor layers are recorded separately as an
**OCI layer-history residual** — neither claimed absent nor claimed safe, and not
by itself a component-presence blocker. Its
[evidence record](../knowledge/assessments/oci-layer-history-and-component-presence-evidence.md)
holds the measured divergence between the two states. **Decision 0026 selects no
remediation shape, grants no security exception, authorizes no OCI publication,
and adds no flattening stage.**

[Work Item #62](https://github.com/ktogias/gnostoa/issues/62) then completed the
bounded pip and `ensurepip` runtime removal under
[Decision 0027](../knowledge/decisions/0027-remove-pip-and-ensurepip-from-the-published-gnostoa-oci-runtime.md),
which changes the published `runtime` target only and introduces no replacement
package channel. Its candidate-bound
[remediation result](../knowledge/assessments/pip-runtime-removal-remediation-result.md)
records that the established pip Decision 0022/D blocker **was cleared for the
measured `linux/amd64` effective runtime**, that the documented runtime contract
and the separate development target were preserved, and that historical affected
bytes retained in inherited layers remain an **OCI layer-history residual** under
Decision 0026 — neither claimed absent nor claimed safe. That result establishes
**neither complete OCI readiness nor artifact-byte hygiene**, and Decision 0027
authorizes **no publication**. Before any eventual publication, a public security
statement must distinguish effective-runtime component hygiene from
layer-history hygiene. Provider state remains authoritative for Work Item
lifecycle.

Under [Work Item #64](https://github.com/ktogias/gnostoa/issues/64),
[Decision 0028](../knowledge/decisions/0028-bind-the-published-oci-runtime-source-to-the-git-candidate.md)
bound the measured first-party runtime source payload and packaged candidate to
the authoritative Git candidate. Its candidate-bound
[binding result](../knowledge/assessments/oci-git-candidate-source-binding-result.md)
records that the packaged manifest and the runtime's Gnostoa source are both
derived from `git ls-files`, using current tracked working-tree contents, so
measured untracked or ignored host-local files cannot enter the runtime source and
import surface. **The development image keeps the ordinary local build context and
is deliberately outside that guarantee.** Decision 0028 authorizes **no OCI
publication**.

[Decision 0029](../knowledge/decisions/0029-define-authoritative-source-membership-for-the-public-surface-digest.md)
then resolved the deterministic public-surface-digest input that Decision 0028
left open. Its
[source-authority result](../knowledge/assessments/deterministic-public-surface-digest-source-authority-result.md)
records that a Git-backed or manifest-backed toolkit root now takes public-surface
membership from its declared candidate, so ignored or untracked host-local files no
longer move the contract identity, while a **metadata-free vendored source presents
its physical public surface** and a non-ignored extra public file there is a source
modification by design. A declared authority that cannot be read fails rather than
falling back.

The measured official Python 3.12 base refresh moved the first-party runtime from
CPython 3.12.13 to the released supported 3.12.14 security base under
[Decision 0030](../knowledge/decisions/0030-refresh-the-official-python-312-base-for-cpython-security-fixes.md).
Its
[refresh result](../knowledge/assessments/cpython-312-security-base-refresh-result.md)
records the exact candidate, the bundled-Expat move from 2.7.4 to 2.8.3, the
unchanged Debian package inventory, and the remaining post-release CPython
residuals that have no released supported 3.12 fix.

A bounded Debian materiality triage then classified the shipped source packages
that carry no Debian Security Tracker vulnerability rows, and
[Decision 0031](../knowledge/decisions/0031-accept-bounded-material-debian-security-uncertainty-for-the-first-oci-candidate.md)
dispositioned the five material unknowns for the measured `linux/amd64`
first-publication boundary. Its
[triage result](../knowledge/assessments/debian-material-unknown-triage-and-disposition-result.md)
records the corrected tracker measurement, the runtime materiality evidence and
the accepted bounded residual. The result does not call those components safe or
unaffected and remains candidate-time evidence subject to Decision 0022/J
freshness.

A bounded licence and attribution measurement then compared the image's
standardized licence annotation against the software the image actually contains.
[Decision 0032](../knowledge/decisions/0032-omit-composite-oci-licence-annotation-until-an-image-wide-expression-is-selected.md)
omitted the optional composite `org.opencontainers.image.licenses` annotation
rather than retain a partial image-wide claim or fabricate an aggregate SPDX
expression, while Gnostoa first-party source and package metadata continue to
declare Apache-2.0. Its
[metadata and attribution result](../knowledge/assessments/oci-licence-metadata-and-cpython-attribution-result.md)
records the measured evidence coverage and retains the CPython
incorporated-software attribution gap as a qualified legal-review residual. No
legal clearance is claimed.

A bounded read-only
[current-state drift retrospective](../knowledge/assessments/current-state-drift-retrospective.md)
then reconstructed the observed drift incidents, near-misses, triggers and
controls across the durable repository and provider record. Its measured result is
that **lifecycle and outcome projection drift recur**, while identity, resume,
verification-expectation and observation drift are **separate families** that one
mechanism should not try to unify.
[Decision 0024](../knowledge/decisions/0024-separate-stable-navigation-from-volatile-state.md)
records the resulting Gnostoa-self authoring discipline: stable navigation is kept
separate from volatile lifecycle and unbound current-outcome state. **Decision 0024
selects no checker, freshness engine, audit script, projection engine or
enforcement route**, and the read-only audit the retrospective proposed was **not
admitted with it**; that remains a separate owner disposition.

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

B2/P1 and B2/P2 are completed evidence. C4-v0 was rejected and no successor
control is selected. Nextcloud Mail is selected for an `OWNER-LED`
early-product evidence stream under Decision 0052. The published `v0.2.0`
release and digest-bound reconciliation are complete; the release Work
Item's final experiment-boundary requirement is the integrated and
provider-read-back owner-led baseline. The concrete task run and
retrospective are later separate work, while strict `INDEPENDENT` B3
evidence is deferred to a separately admitted maturity-stage activity.
Provider state remains authoritative for its live lifecycle.

| Work Items | Problem addressed | Completion signal | Non-goal |
|---|---|---|---|
| [#146](https://github.com/ktogias/gnostoa/issues/146) | The immutable `v0.2.0` source and OCI artifact are published and reconciled; the release series still needs its bounded early-product experiment boundary represented durably. | Source, OCI digest, provenance, integrated release verification and public records agree, and the Nextcloud Mail `OWNER-LED` baseline is integrated and provider-read back before lifecycle completion. | Executing or scoring the owner-led task; upstream feedback or strict `INDEPENDENT` evidence; `latest`, extra tags, multi-architecture, reproducibility claims, deployment or a new release framework. |

## Research

These items contain useful designs and evidence. Their underlying capability
need may be demonstrated, but their minimum implementation and sequencing remain
experimental. They stay outside current delivery until a later owner selection
and candidate-specific admission.

| Work Items | Research question | Promotion condition |
|---|---|---|
| [#3](https://github.com/ktogias/gnostoa/issues/3), [#5](https://github.com/ktogias/gnostoa/issues/5), [#8](https://github.com/ktogias/gnostoa/issues/8) | What is the smallest durable task-context, crash-recovery and asynchronous-waiting slice that addresses the already observed B1 failures? | A later owner selection names one repeated unsolved failure and a bounded candidate that existing B2 evidence does not already cover. |
| [#6](https://github.com/ktogias/gnostoa/issues/6), [#9](https://github.com/ktogias/gnostoa/issues/9), [#13](https://github.com/ktogias/gnostoa/issues/13) | Which admission, orientation and canonical-language controls address a newly observed repeated failure without turning the full research backlog into prerequisites? | One concrete failure, routing location and smallest enforceable contract are selected and admitted independently. |
| [#7](https://github.com/ktogias/gnostoa/issues/7) | What workspace ownership or hermetic-execution boundary is needed beyond the already bounded public evaluation route? | A real task demonstrates an unresolved host-data or ownership risk and admits one falsifiable boundary without claiming general isolation. |
| [#10](https://github.com/ktogias/gnostoa/issues/10), [#11](https://github.com/ktogias/gnostoa/issues/11), [#14](https://github.com/ktogias/gnostoa/issues/14) | Which role, semantic-capture and goal-alignment projections improve decisions without becoming a second authority? | A bounded experiment demonstrates measurable orientation or reconciliation benefit with deterministic regeneration. |
| [#15](https://github.com/ktogias/gnostoa/issues/15) | Which workflow mechanics can be automated without automating evidence amplification or weakening review? | A later measured task identifies stable repeated mechanics, explicit effect boundaries and a falsifiable reduction target. |

[Issue #12](https://github.com/ktogias/gnostoa/issues/12) is a closed historical
B1 design and dogfood ledger. Its 342 comments remain inspectable evidence of
both defect discovery and excessive amplification; the broad guided-review
platform is deferred to Research and is not the contributor interface or an
active publication prerequisite. The capability direction remains planned by
[Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).
Issue #24 is the completed B2 evidence base, and [Issue #33](https://github.com/ktogias/gnostoa/issues/33)
is the completed C4-v0 experiment whose control was rejected. The strict B3 methodology remains pre-registered for later
`INDEPENDENT` evidence. The rejected Nextcloud Mail attempts remain
historical controlled pre-B3 records and produced no accepted or durable
adoption result. Decision 0052 selects the current stream as `OWNER-LED`.
Work Item #146 governs only the published release reconciliation and the
integrated/provider-read-back owner-led baseline; the concrete task run,
preliminary assessment and retrospective are later work, and a strict
independent experiment requires separate future admission.

The work in PR #4 is retained here as an exact research input for #3. It is not
discarded, accepted or part of the first-publication baseline while its review
findings and merge conflicts remain unresolved.
