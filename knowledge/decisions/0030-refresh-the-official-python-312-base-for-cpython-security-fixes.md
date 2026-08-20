---
type: Decision
title: Refresh the official Python 3.12 base for CPython security fixes
description: Select the official Python 3.12 security-base refresh for the first-party OCI runtime, moving CPython from 3.12.13 to the released 3.12.14 through the existing supported Docker Official Image channel, and defer three post-release CPython findings as bounded residuals.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T17:00:00Z"
sources:
  - id: cpython-base-refresh-work-item
    resource: https://github.com/ktogias/gnostoa/issues/68
    title: Refresh the official Python 3.12 OCI base for security fixes
  - id: oci-security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
x-project-knowledge:
  id: kit.decision.0030.refresh-the-official-python-312-base-for-cpython-security-fixes
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
      target: /assessments/cpython-312-security-base-refresh-result.md
---

# Refresh the official Python 3.12 base for CPython security fixes

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **Gnostoa-self first-party OCI `linux/amd64` publication preparation only.**

## Context

A bounded read-only study bound the shipped interpreter to authoritative upstream
CPython security evidence. The candidate-time measurements live in the
[refresh result](../assessments/cpython-312-security-base-refresh-result.md).

## Decision

**A.** The installed baseline is **CPython 3.12.13**.

**B.** The study establishes **Decision 0022/D** for the current candidate: 31 of
the 32 security entries in the released 3.12.14 bind to the 3.12.13 state, the
affected code and components are present in the measured runtime, and a fixed
release is available through the existing supported channel.

**C. Decision 0022/F is not established.** No finding was demonstrated reachable
through the documented supported default runtime. This is a statement about what
was demonstrated, **not** a claim that CPython findings are harmless or
unreachable in all deployments.

**D.** The existing supported component channel is the **Docker Official Image
`python:3.12-slim`**, per Decision 0025's component-maintainer supported-update
reading.

**E.** Select **R1 — official Python 3.12 security-base refresh.**

**F.** Selected fixed release: **CPython 3.12.14**, subject to candidate-time
freshness.

**G.** Preserve the existing pin semantic: an **immutable Docker Official Image
index digest**, never a mutable tag.

**H.** Selected index digest
`sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a`.

**I.** Measured `linux/amd64` platform digest
`sha256:876416ecde9aca2bcc90e1fb0c7a9500bbf749f5788b70f82d4c5a5c2357f8b4`.

**J.** Do **not** switch from index-digest to platform-digest pinning in this
slice. The index pin keeps the multi-platform reference the current build
consumes; narrowing it is a separate question.

**K.** CPython moves **3.12.13 → 3.12.14**.

**L.** CPython-**bundled** Expat moves **2.7.4 → 2.8.3**. This is the bundled
copy: `pyexpat` links no system `libexpat`, and Debian's `libexpat1` was already
2.8.3 and unused by Python.

**M.** The Debian dpkg inventory and version set are experimentally **unchanged**.

**N.** The existing util-linux security pins remain valid. **O.** The existing Git
pin remains valid.

**P.** The Decision 0027 pip/`ensurepip` removal remains required and is
preserved. **Q.** Decision 0026 lower-layer residual semantics are unchanged; no
claim is made that historical-layer bytes disappear.

**R.** X3 P2/P5 source binding is unchanged. **S.** D-A public-contract digest
authority is unchanged.

**T.** The public source digest changes because **`Dockerfile` content changed**,
not because base-image bytes are part of digest semantics. P4 remains unselected
and image bytes remain outside `public_surface_digest` membership.

**U.** Three CPython security findings disclosed after 3.12.14 remain bounded
**Decision-0022/E residuals**: CVE-2026-19672 (gh-155999), CVE-2026-15806
(gh-155694), CVE-2026-17084 (gh-155292).

**V.** Those residuals are **DEFERRED — not accepted, not waived**. No security
exception is created and no claim of absence or applicability safety is made.

**W.** Their authoritative status **must be re-read** before any later
immutable-source or publication candidate. If a released supported 3.12 fix
appears, Decision 0022/D must be re-evaluated against that later candidate.

**X.** No custom CPython build and no cherry-pick channel. **Y.** No Python
3.13/3.14 upgrade. **Z.** No exception to remain on 3.12.13.

**AA.** No source identity, version, tag or release is created here.
**AB.** OCI publication remains unauthorized. **AC.** `deployable_artifact`
remains `false`. **AD.** `linux/amd64` remains the only security-evidence
platform.

## Consequences

- The image-defining remediation is exactly **one** `Dockerfile` base-digest
  change. The disposable experiment needed no compatibility adjustment, so R2 was
  not required and nothing else moved.
- Because `Dockerfile` is public surface, the clean public-contract digest
  changes. That is a source-content consequence, not evidence that base bytes
  entered digest semantics.
- The refresh moves **only** CPython and its bundled Expat. All 118 Debian
  package versions are identical, so this carries no hidden distribution delta —
  which is also why the util-linux and Git pins survive as no-ops rather than
  needing revision.
- The resulting image is **not** free of CPython security findings. Three
  disclosed after 3.12.14 have no released supported 3.12 fix at the measured
  timestamp, and two of the three have open — not merged — 3.12 backports. A
  second refresh is the expected consequence once they land.
- The historical `v0.1.0` release remains immutable and unrelated to this image
  candidate. Current source must not be described as `v0.1.0`, and
  source-identity preparation stays paused.
