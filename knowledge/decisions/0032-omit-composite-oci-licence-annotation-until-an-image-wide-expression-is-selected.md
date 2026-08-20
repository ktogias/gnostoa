---
type: Decision
title: Omit composite OCI licence annotation until an image-wide expression is selected
description: Remove the optional org.opencontainers.image.licenses annotation from the composite runtime image because a single Apache-2.0 value does not describe the measured multi-licence contained software, without fabricating a replacement SPDX expression.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T22:00:00Z"
sources:
  - id: oci-licence-metadata-work-item
    resource: https://github.com/ktogias/gnostoa/issues/72
    title: Reconcile OCI licence metadata with the composite runtime
x-project-knowledge:
  id: kit.decision.0032.omit-composite-oci-licence-annotation-until-an-image-wide-expression-is-selected
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0010-license-gnostoa-under-apache-2.0.md
    - kind: references
      target: /decisions/0011-record-initial-copyright-ownership.md
    - kind: references
      target: /assessments/oci-licence-metadata-and-cpython-attribution-result.md
---

# Omit composite OCI licence annotation until an image-wide expression is selected

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **Gnostoa-self first-party `linux/amd64` OCI publication preparation.**

## Context

A bounded read-only G4 measurement compared the image's standardized licence
annotation against the software the image actually contains. The candidate-time
measurements live in the
[metadata and attribution result](../assessments/oci-licence-metadata-and-cpython-attribution-result.md).

## Decision

**A.** Decision 0010 remains authoritative for Gnostoa first-party Apache-2.0
licensing. It is not rewritten.

**B.** Decision 0011 remains authoritative for the Gnostoa `NOTICE` and initial
attribution.

**C.** The standardized `org.opencontainers.image.licenses` field describes
**the licence(s) under which contained software is distributed**, as an SPDX
License Expression.

**D.** The measured image contains software under multiple licence families:
CPython under the PSF licence, six MIT-licensed Python distributions,
`typing_extensions` under PSF-2.0, and 118 Debian packages declaring 22+ distinct
licence short-names, 104 of which declare more than one.

**E.** The current `Apache-2.0` value was intended to reflect Gnostoa's
first-party licence. It does not establish an image-wide contained-software SPDX
expression, so as a standardized claim it is not supported by the evidence.

**F.** Do **not** fabricate an aggregate SPDX expression from observed
identifiers. SPDX expressions encode legal relationships, not a list of strings.

**G.** Select **omission** of the optional standardized annotation for the
composite image. Omitting an optional field is truthful where a partial value
would not be.

**H.** Preserve unchanged: `pyproject` `license = "Apache-2.0"`, `license-files`,
the root `LICENSE` and `NOTICE`, the installed `License-Expression`, and the
scope of Gnostoa first-party licensing.

**I.** No replacement OCI licence label is selected. **J.** No third-party NOTICE
aggregator is selected.

**K.** The CPython incorporated-software attribution gap remains a **qualified
legal review residual**.

**L.** The incidental Debian `libexpat1` attribution copy is **not** treated as
proof that the obligation for CPython's *bundled* Expat is satisfied. CPython
uses its own bundled copy; the Debian package is a different artefact.

**M.** No legal violation is asserted. **N.** No legal clearance is asserted.

**O.** If qualified legal review later establishes additional attribution
requirements, satisfying them is a separately admitted source-changing slice.

**P.** Source identity remains paused. **Q.** OCI publication remains
unauthorized. **R.** `deployable_artifact` remains `false`.

## What this narrows, exactly

Decision 0010 instructed publishing the SPDX identifier `Apache-2.0` in package
**and OCI-image** metadata. That instruction predates the measurement showing the
standardized field's contained-software semantics are broader than the
first-party scope Decision 0010 was expressing.

This Decision narrows **only** that OCI-metadata consequence. Package metadata is
untouched, the first-party licence choice is untouched, and Decision 0010 remains
valid for everything else it says.

## Consequences

- The published image now carries **no** licence annotation. That absence is not
  a statement that the image has no licensing obligations; dependency and system
  component licences remain independently applicable, and every shipped component
  keeps its own licence evidence.
- Consumers who relied on reading `org.opencontainers.image.licenses` will find
  nothing. That is the intended outcome: a field that answered a broader question
  than the project could truthfully answer has been withdrawn rather than left
  partially wrong.
- Re-adding the annotation later is a small change, but choosing its value is
  not. It needs a real image-wide expression, which needs legal input this
  project has not obtained.
- `Dockerfile` is public surface, so the public-contract digest changes. That is
  a source-bytes consequence; image licence metadata is not a new digest input
  category and P4 remains unselected.
- The CPython attribution residual is now on the record as a named publication
  gate rather than an unexamined assumption. It is not resolved by this slice.
