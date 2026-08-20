---
type: Source
title: OCI licence metadata and CPython attribution disposition result
description: Candidate-bound result recording the measured licence and attribution evidence for the first-party OCI runtime, the omission of the composite image-wide licence annotation, and the CPython incorporated-software attribution residual.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T22:00:00Z"
sources:
  - id: oci-licence-metadata-work-item
    resource: https://github.com/ktogias/gnostoa/issues/72
    title: Reconcile OCI licence metadata with the composite runtime
x-project-knowledge:
  id: kit.assessment.oci-licence-metadata-and-cpython-attribution-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0032-omit-composite-oci-licence-annotation-until-an-image-wide-expression-is-selected.md
    - kind: references
      target: /decisions/0010-license-gnostoa-under-apache-2.0.md
---

# OCI licence metadata and CPython attribution disposition result

**Candidate-time evidence.** Measured on `linux/amd64` only. Re-observe before any
publication. **This record contains no legal advice and asserts no legal
conclusion.**

## Subject

| | |
|---|---|
| Pre-change source | `335641c3b20337a165322b1fef59a3c653309b43` |
| Pre-change public digest | `sha256:90f3c4d8724e8749662cbd4fdeeade3b3b3a0de8d8d2815c375cdbc5a1a127f5` |
| Base | `python:3.12-slim@sha256:2c941e86…` |
| CPython / bundled Expat | 3.12.14 / 2.8.3 |
| Inventory | 118 Debian binary, 82 source, 8 Python distributions |

## First-party licence evidence — complete for the measured subject

`LICENSE` (11,358 bytes) and `NOTICE` (43 bytes, `Gnostoa` /
`Copyright 2026 Konstantinos Togias`) are tracked in source, present at
`/opt/gnostoa/` in the runtime, and installed under
`gnostoa-0.1.0.dist-info/licenses/`. `pyproject` declares
`license = "Apache-2.0"` and `license-files = ["LICENSE", "NOTICE"]`; installed
metadata carries `License-Expression: Apache-2.0` and both `License-File`
entries. Source-to-runtime parity is exact. Decision 0011's attribution matches
the OCI `authors` label.

## Third-party evidence coverage

| family | result |
|---|---|
| Python distributions | **8 / 8** ship a licence file |
| Debian binary packages | **118 / 118** carry copyright evidence; 0 missing, 0 unreadable, 0 broken |
| Explicit third-party `NOTICE` candidate set | **empty** — the only `NOTICE` files image-wide are Gnostoa's own two copies |

Of the 8 Debian packages whose copyright names Apache-2.0 — `git`, `git-man`,
`libcom-err2`, `libgnutls30t64`, `libp11-kit0`, `libssl3t64`, `openssl`,
`openssl-provider-legacy` — **none ships a `NOTICE` file**, so no third-party
notice retention is mechanically omitted.

## Why the annotation was omitted

The OCI Image Specification defines `org.opencontainers.image.licenses` as
*"License(s) under which contained software is distributed as an SPDX License
Expression"*. The measured contained software spans CPython/PSF, six MIT
distributions, `typing_extensions` under PSF-2.0, and Debian packages declaring
22+ distinct licence short-names — with **104 of 118** declaring more than one.

A single `Apache-2.0` value therefore describes the first-party project, not the
contained software. Building a replacement expression mechanically was rejected:
concatenating observed identifiers would encode legal relationships that were not
determined. The field is optional, so the smallest truthful action is to omit it.

## Exact changes

**Dockerfile** — one line removed from the `LABEL` group:
`org.opencontainers.image.licenses="Apache-2.0"`. All other labels — `title`,
`description`, `authors`, `version`, `revision`, `created` — are unchanged.

**Test** — `LicensePolicyTests` keeps its `LICENSE` digest, `pyproject` licence
and `license-files` assertions. The Dockerfile-label assertion moved into a new
test asserting the composite image publishes **no** image-wide licence
expression, documented as the current selection rather than a permanent rule.

Nothing else changed: no replacement SPDX expression, no custom licence label, no
`THIRD_PARTY_NOTICES`, no copied CPython or Expat attribution, no root `NOTICE`
additions.

## CPython incorporated-software attribution — qualified legal review residual

Measured: `/usr/local/lib/python3.12/LICENSE.txt` (13,936 bytes) is present and
contains exactly two sections — **A. HISTORY OF THE SOFTWARE** and
**B. TERMS AND CONDITIONS**. Upstream CPython's `Doc/license.rst` carries a
distinct *Licenses and Acknowledgements for Incorporated Software* section
including the full Expat licence and the copyright holders *Thai Open Source
Software Center Ltd and Clark Cooper*. The official Python image does **not**
install that appendix. `pyexpat` links no system `libexpat`, so CPython uses its
**bundled** Expat 2.8.3. Image-wide, that attribution text appears in exactly one
file: `/usr/share/doc/libexpat1/copyright` — Debian's system package, which
CPython does not use.

The incidental Debian copy is **not** treated as satisfying the obligation for
CPython's bundled copy, and the appendix's absence is **not** treated as proof of
a violation. The exact unresolved question, requiring **qualified legal review**:

> For distribution of the measured CPython 3.12.14 binary runtime containing its
> bundled third-party components, must the incorporated-software licence and
> acknowledgement material represented by CPython `Doc/license.rst`, or an
> equivalent subset, accompany the OCI distribution beyond the currently shipped
> `/usr/local/lib/python3.12/LICENSE.txt` and package-specific evidence?

No agent answer constitutes legal clearance. The omission originates in the
official `docker-library/python` image, not in Gnostoa's build definition.

## CPython freshness at disposition time

`python:3.12-slim` index unmoved; docker-library declares 3.12 → 3.12.14. The
3.12 backports for CVE-2026-19672 (`#156043`) and CVE-2026-15806 (`#155971`) are
**merged but unreleased**; CVE-2026-17084 has **no 3.12 backport**. No preemption.

## Non-claims

Not claimed: that the image is legally compliant; that all licences are
compatible; that the current redistribution satisfies every third-party
obligation; that CPython attribution is sufficient; that no third-party notice is
needed; that omitting the annotation clears legal review; OCI readiness; or
publication authorization.

## Source-identity consequence

`Dockerfile` is public surface, so the public-contract digest changes — a
source-bytes consequence, not evidence that image licence metadata is a digest
input category. P4 remains unselected. Source-identity preparation remains
paused, `deployable_artifact` remains `false`, and `v0.1.0` remains immutable at
`ee808572d3930ec3dc50d350ae1ed25a0236bb6b` and unrelated to this candidate.
