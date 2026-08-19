---
type: Decision
title: Define effective-runtime component presence for layered OCI publication
description: Owner semantics selecting effective merged-runtime component state as the component-presence criterion for Decisions 0022 and 0025, with layer-history bytes classified separately.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T14:15:00Z"
sources:
  - id: component-presence-work-item
    resource: https://github.com/ktogias/gnostoa/issues/60
    title: Define layered-image component presence for OCI security publication
  - id: oci-security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
x-project-knowledge:
  id: kit.decision.0026.define-effective-runtime-component-presence-for-layered-oci-publication
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /decisions/0025-define-supported-update-channel-semantics-for-base-bundled-oci-components.md
    - kind: references
      target: /assessments/oci-layer-history-and-component-presence-evidence.md
---

# Define effective-runtime component presence for layered OCI publication

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **Gnostoa-self, first-party OCI security and publication only.**

## Context

Decision 0022 remains the governing first-OCI security and residual-risk
authority, and Decision 0025 supplements it for base-bundled components. This
Decision **supplements both prospectively** and **does not rewrite or reinterpret
their historical text**, nor that of Decisions 0023 or 0024.

Those Decisions use terms equivalent to *installed shipped component*, *component
present*, and *no affected code copy remains shipped*. They do not state which of
two meanings governs in a layered image:

- **A — effective merged-runtime component state**: what exists in the root
  filesystem after normal layer application;
- **B — bytes present in distributed layer history**: what remains recoverable
  from ancestor layer blobs the image references.

A completed bounded experiment measured both remediation shapes for the current
pip finding and found that **the two meanings diverge for the same image**. Its
evidence is recorded in
[OCI layer-history and component-presence evidence](../assessments/oci-layer-history-and-component-presence-evidence.md);
the candidate-time observations live there rather than here.

Because the divergence is now demonstrated, the ambiguity determines whether
ordinary upper-layer remediation can ever clear a Decision 0022/D blocker. **No
further measurement can decide it.** What was missing is meaning.

## Decision

**A. Effective merged-runtime component semantics are selected.** For Decisions
0022/**D**, 0022/**G** and Decision 0025, a component is considered **PRESENT /
SHIPPED** for component-vulnerability publication-hygiene evaluation when affected
component code or artifacts are present in the **effective merged filesystem of the
exact published runtime image after normal OCI layer application**.

**B. What is not presence.** A component that is absent from the effective merged
runtime, hidden or superseded solely through OCI layer changes, and not restored or
materialized by the supported runtime path, is **not** a present shipped component
for the Decision 0022/D blocker **solely because historical bytes remain inside an
ancestor layer blob**.

**C. Rationale — this makes an existing boundary explicit rather than new.**
Decision 0022's component evidence and Decision 0023's remediation were both
measured against installed and effective runtime state: package inventory,
installed versions, shipped runtime components and default-runtime applicability.
Neither defined an all-layer-byte criterion. This Decision states that previously
implicit measurement boundary; it does not rewrite the historical measurements.

**D. Rationale — it preserves runtime component semantics.** A whiteouted file is
not part of the effective root filesystem presented to the supported container
runtime. Decision 0022's supported boundary is the **documented default runtime**,
not arbitrary manual extraction of image-layer blobs.

**E. Rationale — it avoids a silent retroactive rule change.** Defining *shipped*
today as *any byte present in any historical distributed layer* would materially
change the meaning under which the util-linux remediation was evaluated and
accepted. The evidence record shows that remediation has the same layer-history
shape. **That broader rule is not adopted implicitly.**

**F. Rationale — presence and reachability stay distinct.** This Decision does
**not** weaken Decision 0022/**C**. A vulnerable component that **exists** in the
merged runtime remains subject to shipment hygiene even where its vulnerable
execution path is unreachable. This rule defines **component presence** across
layered-image representation only; it **does not replace reachability analysis**
and creates no reachability waiver.

**G. Layer-history residual.** Affected bytes retained only in lower layers are
classified an **OCI LAYER-HISTORY RESIDUAL**. This means: the bytes still exist in
the distributed artifact's historical layer set; they are **not** claimed absent;
they are **not** claimed safe; and they are **not by themselves** a Decision 0022/D
component-presence blocker under the semantics selected here. They may still matter
for disclosure, forensic visibility, artifact minimization, future supply-chain
hardening and any future stronger publication policy.

**H. A residual is not an UNKNOWN.** Do not classify a layer-history residual as a
Decision 0022/**H** UNKNOWN merely because it exists. Its presence is **known**. What
is not selected is its security significance under a broader artifact-history
policy, which is a different question from unresolved applicability.

**I. Extraction boundary, stated plainly.** It is **not** claimed that lower-layer
affected bytes cannot be recovered. They can remain present in the distributed
layer blobs. This Decision says only that manual or raw layer extraction lies
outside the component-presence criterion Decision 0022/D uses. A stronger
artifact-byte hygiene guarantee would be a separate owner Decision.

**J. Consequence for util-linux.** Decision 0023 remains valid exactly as recorded:
the demonstrated vendor-fixed util-linux blocker was remediated for the measured
`linux/amd64` effective candidate. Historical lower-layer pre-remediation bytes do
**not** reopen that blocker under this Decision, and Decision 0023 and its result
record are **not** edited to restate this. This Decision supplies the missing
prospective semantics instead.

**K. Consequence for the pip finding.** Under these semantics, the completed
disposable true-removal experiment demonstrated a remediation shape capable of
satisfying the current Decision 0022/D and Decision 0025 blocker: no affected pip
component copy in the merged runtime, no affected bundled copy, the documented
runtime contract preserved, and no unrelated runtime-state delta. **That shape is
therefore eligible for a separately admitted implementation slice.** This Decision
does **not** implement or admit it.

**L. The alternative remains valid.** The fixed-active-component control also
satisfied the merged-runtime property experimentally and remains a valid
alternative. **No remediation shape is selected by this Decision.** The completed
experiment's preference for removal — it takes away a component the documented
runtime does not require and adds no new component update channel — remains
**evidence**, not authority.

**M. Flattening is not required and not selected.** Under the semantics selected
here a flattened final stage is unnecessary. It remains recorded as feasibility
evidence for a possible future artifact-layer-byte hygiene requirement. **No
flattening stage is added.**

**N. No exception is granted**, **no publication is authorized**,
`deployable_artifact` remains `false`, and no registry is selected.

**O. Explicit non-goals.** This Decision establishes nothing about: layer-history
bytes being harmless; vulnerable historical layer bytes being absent; byte-level
artifact hygiene; reproducible image digests; image flattening as best practice;
registry garbage-collection semantics; provenance, signing or attestation policy;
or multi-architecture semantics. It defines the component-presence boundary for
Decisions 0022 and 0025, and nothing else.

**P. Gnostoa-self only.** This is first-party release governance. It is not copied
into adopter guidance, and consumers inherit no threat model from it.

## Consequences

- Ordinary upper-layer remediation can now clear a Decision 0022/D blocker, which
  is what makes any bounded pip remediation shape actionable at all. Without this
  choice, no shape short of rebuilding or flattening the base could have qualified.
- The choice is deliberately the **narrower** of the two available guarantees. It
  buys decidability and consistency with existing measurements, and it pays for
  that by explicitly declining to promise artifact-byte hygiene. Clause **I**
  exists so that limitation is stated rather than implied.
- Clause **G** is what keeps the declined guarantee visible. A residual is recorded
  as a known, unresolved property of the artifact, not quietly discharged.
- Because the same layer-history shape already exists under Decision 0023's
  accepted clearance, this Decision keeps one consistent rule across past and
  future remediations rather than two.
- Decisions 0020–0025 are unchanged, as are `v0.1.0`, the source-release runbook,
  the util-linux remediation result and the pip update-channel assessment. B3 stays
  deferred, drift Half 2 stays not admitted, and no successor workflow, control or
  capability is selected.
- The rule is expected to need revisiting if Gnostoa later adopts an
  artifact-layer-byte hygiene requirement, publishes to a registry whose retention
  behaviour matters, or measures a second platform.
