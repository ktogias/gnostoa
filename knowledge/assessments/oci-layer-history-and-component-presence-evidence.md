---
type: Source
title: OCI layer-history and component-presence evidence
description: Candidate-bound evidence that effective merged-runtime component state and distributed OCI layer-history bytes can diverge, measured across baseline, two remediation shapes and a flattening probe.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T14:15:00Z"
sources:
  - id: component-presence-work-item
    resource: https://github.com/ktogias/gnostoa/issues/60
    title: Define layered-image component presence for OCI security publication
  - id: update-channel-work-item
    resource: https://github.com/ktogias/gnostoa/issues/58
    title: Define the supported update-channel rule for base-bundled OCI components
x-project-knowledge:
  id: kit.assessment.oci-layer-history-and-component-presence-evidence
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0026-define-effective-runtime-component-presence-for-layered-oci-publication.md
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /assessments/pip-security-provenance-and-update-channel-evidence.md
---

# OCI layer-history and component-presence evidence

**Candidate-time evidence, not a standing certification.** Base images, advisory
feeds and upstream bundles change independently of this repository. Re-observe
before any publication or remediation.

## Measured subject

| | |
|---|---|
| Source revision | `76c3bb97cd555c2b45053727a840e6e468cf90c8` |
| Publication target | the Docker **`runtime`** target; `development` is a separate target |
| Platform | Debian 13 trixie, **`linux/amd64` only** |
| Interpreter | CPython 3.12.13 |
| Component under study | pip 25.0.1 |

The public-surface digest at that revision is recomputable with
`knowledge surface-digest` and is deliberately not restated here. Candidates were
disposable local images, built and removed; no repository or provider state was
mutated to obtain this evidence.

## What was measured

Four images: the exact current runtime baseline; a **true-removal** candidate; a
**fixed-active-component** control; and a **flattening** feasibility probe. Each
was inspected twice — once for what a running container sees, and once for what the
distributed layer blobs contain.

## Effective merged-runtime component state

Both remediation shapes cleared the affected component from the filesystem a
container actually presents.

| Check | True removal | Fixed active component |
|---|---|---|
| Installed affected package | absent | replaced by the fixed version |
| Affected distribution metadata | absent | absent |
| Component console entry points | absent | present, fixed version |
| Interpreter bootstrap component | absent | absent |
| Bundled affected artifact | absent | absent |
| Content-hash match for the affected artifact anywhere on the root filesystem | **none** | **none** |
| Any other affected code copy | **none** | **none** |

Both preserved the documented runtime contract: every documented runtime command
succeeded, and the command outputs were **byte-identical** to the baseline. Neither
changed unrelated runtime state — the OS package inventory, runtime user, entrypoint,
capability sets and privileged-file set were identical to the baseline in each case,
and the only file-system differences were the admitted component paths themselves.

## Distributed OCI layer-history state

Scanning every distributed layer blob of each saved image, both by member path and
by content hash of the affected artifact:

| Image | Affected bytes in distributed layers |
|---|---|
| Baseline | **present**, in the inherited interpreter layer |
| True removal | **present**, same inherited layer |
| Fixed active component | **present**, same inherited layer |
| Flattening probe | **absent** — zero path members, zero content-hash matches |

The layer carrying those bytes is inherited from the base image. Upper-layer
removal cannot alter an ancestor layer blob; it can only hide the path once the
layers are applied.

> **The two states therefore diverge for the same image.** That divergence is the
> whole finding of this record.

## The same shape already exists under an accepted clearance

Scanning the baseline image's layers for the previously remediated OS component
showed its **pre-remediation files still present in the distributed base rootfs
layer**, while the project's own later layer carries the fixed versions and the
merged runtime presents the fixed package state.

This matters for scope rather than for security: the completed and accepted OS
remediation has **exactly the same layer-history property** as either pip shape
would. Any definition of *shipped* that counted historical layer bytes would
therefore reach backwards into an already-recorded result.

## Flattening feasibility

A disposable probe rebuilt the cleaned root filesystem into a single flattened
layer.

| Property | Result |
|---|---|
| Affected bytes in distributed layers | **none** |
| Merged root-filesystem path set versus the removal candidate | **identical** |
| Type, mode and owner on every path | **identical** |
| OS package inventory, runtime user, privileged-file set, capability bounds | **identical** |
| Documented runtime behaviour | passed; validation output byte-identical to baseline |
| Remaining differences | directory-entry sizes only, on a small set of directories — a repacking artifact with no type, mode or owner change |
| Image size | smaller than the baseline |

**But** it required explicitly reconstructing the entire image configuration —
environment, labels, user, working directory and entrypoint — because a flattened
stage inherits none of it. That is a durable image-definition and maintenance
surface, and a place where a future omission would silently change runtime
identity.

**This is feasibility evidence only. It is not a selected shape.**

## OCI representation, from the specification

Recorded from the OCI Image Specification as representation, **not** as a security
conclusion:

- an image references an **ordered set of filesystem layers**, base first, each a
  content-addressed descriptor;
- **the final filesystem layout is defined as the result of applying those layers
  to an empty directory**; layer changesets are *applied*, not merely extracted;
- deletion is represented by a **whiteout** entry, which applies only to resources
  in lower or parent layers, and which is itself hidden once applied;
- the image configuration carries an ordered array of layer content hashes.

The specification defines how removal is represented. It does not decide what
Gnostoa means by a shipped vulnerable component.

## Limits

- `linux/amd64` only; no other platform was measured.
- Component-presence measurement only. No exploitability, reachability or
  applicability analysis was performed or implied here.
- Registry-side behaviour — deduplication, garbage collection, what a registry
  retains or serves — was not measured.
- The flattening probe establishes feasibility on one candidate; it establishes
  nothing about long-term maintainability.
- No claim is made that lower-layer bytes are unrecoverable. They can remain
  present in the distributed blobs.

## The question this evidence leaves open

Nothing further is measurable that would decide it. Existing authority does not
state whether component presence means the **effective merged runtime** or **any
byte retained in distributed layer history**, and the two demonstrably differ. That
is an owner-semantic choice, recorded in
[Decision 0026](../decisions/0026-define-effective-runtime-component-presence-for-layered-oci-publication.md).
