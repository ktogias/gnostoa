---
type: Decision
title: Remove pip and ensurepip from the published Gnostoa OCI runtime
description: Select true removal of the pip component and its ensurepip bundled copy from the published runtime target as the remediation for the established Decision 0022/D pip blocker, without introducing a replacement update channel.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T15:05:00Z"
sources:
  - id: pip-removal-work-item
    resource: https://github.com/ktogias/gnostoa/issues/62
    title: Remove pip and ensurepip from the published OCI runtime
  - id: oci-security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
x-project-knowledge:
  id: kit.decision.0027.remove-pip-and-ensurepip-from-the-published-gnostoa-oci-runtime
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
      target: /decisions/0026-define-effective-runtime-component-presence-for-layered-oci-publication.md
    - kind: references
      target: /assessments/pip-runtime-removal-remediation-result.md
---

# Remove pip and ensurepip from the published Gnostoa OCI runtime

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **Gnostoa-self, first-party OCI runtime only.**

## Context

Decision 0022/**D** forbids knowingly publishing a vendor-designated vulnerable
shipped component when a supported update exists. Decision 0025 established that
the shipped pip fact pattern triggers that rule. Decision 0026 then fixed the
component-presence criterion as the **effective merged runtime**, which is what
makes an ordinary upper-layer removal capable of clearing the blocker at all.

A completed disposable experiment compared two bounded shapes against the exact
candidate: removing the component from the published runtime, and retaining it at
a fixed version. Both cleared the merged runtime. They differ in what they leave
behind.

This Decision selects the removal shape and admits one bounded implementation.
Candidate-time facts live in the
[remediation result](../assessments/pip-runtime-removal-remediation-result.md),
not here.

### Why removal, on its own evidence

The selection rests on the measured properties of the shape itself, **not** on
consistency with any earlier remediation:

- **the documented published runtime does not require it.** Every pip, venv and
  ensurepip mention in consumer-facing material is host-native, development-image,
  build-time or incidental; the contract surfaces mention none of them; and the
  documented `knowledge` entrypoint loads no pip module;
- **complete merged-runtime removal was demonstrated**, by name and by content
  hash, with no affected copy remaining;
- **the runtime contract was preserved**, with deterministic outputs identical to
  the baseline;
- **zero unrelated runtime state moved**;
- **it introduces no new component-native package fetch or update channel**;
- **it leaves less persistent component and vulnerability-maintenance surface**
  than retaining a component that would need re-evaluating and re-pinning on every
  future candidate;
- **maintainers lose nothing**, because the development target branches from the
  shared base rather than from the cleaned runtime.

Decision 0023 is historical supporting consistency evidence only. **It is not the
reason this shape is selected**, and no part of this Decision depends on it.

## Decision

**A.** Decisions 0022, 0025 and 0026 govern. None of them is rewritten here.

**B.** Select **true removal**: the pip component and its `ensurepip` bundled copy
are removed from the published **`runtime`** target only.

**C.** The **`base`** stage continues to use pip at build time, to install the
runtime lock and the editable source. That use is unchanged.

**D.** The **`development`** target remains separate and retains its development
pip and tooling semantics.

**E.** **No new pip or package-index update channel is introduced** as the
remediation.

**F.** The effective merged runtime must not contain: the active pip package; pip
distribution metadata; pip console entry points; the `ensurepip` package; the
bundled pip wheel; or any other vendor-designated affected pip component copy
found by the admitted inventory.

**G.** Success is the **absence of vendor-designated affected pip component code
or artifacts in the effective merged runtime**, under the component-presence
criterion Decision 0026 selected.

**H.** Historical affected bytes retained only in lower layers remain an
**OCI LAYER-HISTORY RESIDUAL**. They are **not** claimed absent and **not** claimed
safe.

**I.** This Decision **does not establish artifact-byte hygiene.**

**J.** This Decision **does not authorize** language claiming that the distributed
OCI artifact contains no affected historical pip bytes.

**K.** Before actual OCI publication, a public security or runtime statement
**must distinguish** effective runtime component hygiene from layer-history and
artifact-byte hygiene, and must not collapse the first into the second. That
wording is **not drafted here**, and this requirement creates **no** artifact-byte
publication blocker under Decision 0026.

**L.** **No flattening.** **M.** **No base-image change.** **N.** **No CPython
version or minor-line change.** **O.** **No exception is granted.** **P.** **No OCI
publication is authorized.** **Q.** `deployable_artifact` remains `false`.

**R.** The image definition changes, so the source state changes. A **new immutable
source identity remains required before eventual publication**, and **no version,
tag or release is selected** here.

**S.** On measured success this clears **only** the established pip blocker.

**T.** Complete OCI readiness, image security and legal state remain
**unestablished**.

**U.** **No mechanism is selected** — no scanner, updater, provider adapter,
CI-security framework, monitoring service or dependency bot.

**V.** This selection rests on the bounded removal evidence, **not** on preserving
the convenience of any earlier remediation result.

## Consequences

- The remediation removes a component rather than maintaining it. That is the
  point of the choice: a component absent from the published runtime cannot
  generate a future shipment-hygiene blocker, and needs no future version
  re-evaluation.
- The cost is real and stated rather than hidden: the published runtime loses
  generic Python package-management behaviour. Nothing documented depends on it,
  and maintainers keep it in the development target, but a consumer who expected an
  ordinary Python base image to behave like one will find it does not.
- **The image does not get smaller.** Removal adds a layer of whiteouts on top of
  an inherited layer that still carries the bytes. Anyone reasoning about this
  change from image size alone will reach the wrong conclusion, which is precisely
  why Decision 0026's residual classification and clause **J** exist.
- The `PIP_*` environment variables set in the shared base remain, because they
  are still meaningful for the base stage's build-time pip use. They are inert in
  the published runtime.
- Decisions 0020–0026 are unchanged, as are `v0.1.0`, the source-release runbook,
  the util-linux remediation result, the pip provenance assessment and the
  layer-history assessment. B3 stays deferred, drift Half 2 stays not admitted, and
  no successor workflow, control or capability is selected.
- Every other OCI gate named in Decision 0022/K remains open and untouched.
