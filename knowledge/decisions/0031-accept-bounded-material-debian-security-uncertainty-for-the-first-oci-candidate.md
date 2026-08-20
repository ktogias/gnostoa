---
type: Decision
title: Accept bounded material Debian security uncertainty for the first OCI candidate
description: Disposition the five material Decision-0022/H unknown source packages in the measured linux/amd64 OCI candidate as bounded residual uncertainty, without declaring any component safe and without creating a Decision-0022/D or /F exception.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-20T16:45:00Z"
sources:
  - id: debian-unknown-disposition-work-item
    resource: https://github.com/ktogias/gnostoa/issues/70
    title: Disposition the remaining material Debian security unknowns
x-project-knowledge:
  id: kit.decision.0031.accept-bounded-material-debian-security-uncertainty-for-the-first-oci-candidate
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /assessments/debian-material-unknown-triage-and-disposition-result.md
---

# Accept bounded material Debian security uncertainty for the first OCI candidate

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **Gnostoa-self first-party OCI `linux/amd64` publication preparation only.**

## Context

Decision 0022/H states that an UNKNOWN remains UNKNOWN, is never converted into
"safe" because evidence could not be obtained, and that **a material UNKNOWN may
itself require owner disposition before publication**. A bounded read-only triage
classified the shipped Debian packages that carry no Debian Security Tracker
vulnerability rows. The candidate-time measurements live in the
[triage and disposition result](../assessments/debian-material-unknown-triage-and-disposition-result.md).

## Decision

**A.** Decision 0022/H governs this disposition. Decision 0022 itself is
unchanged.

**B.** The subject is the exact measured candidate: source
`b7c39b5ea8f9d8b40b527cc0832e769f4bf8cc00`, public digest
`sha256:90f3c4d8…`, base `python:3.12-slim@sha256:2c941e86…`, CPython 3.12.14,
bundled Expat 2.8.3, `linux/amd64`.

**C.** 27 shipped source packages expose no Debian Security Tracker
vulnerability rows at the measured timestamp, out of 82 source packages behind
118 binary packages.

**D. Five are H1 material UNKNOWN:** `gcc-14`, `ca-certificates`, `libselinux`,
`libcap-ng`, `libmd`.

**E.** 22 are H2 bounded low-material residual UNKNOWN.

**F.** 0 are H3 incomplete-observation cases. No classification remains blocked
on an obtainable observation.

**G.** The fixed-known sweep remains **0 below-fixed**: the image's own
configured supported channel offers no upgrade for any installed package.

**H.** All 27 had **normal** Debian security-support status at the measured
timestamp; only one shipped package appears on the trixie support list at all,
and it is marked `supported`.

**I.** The H1 uncertainty is **accepted as bounded residual uncertainty** for
this exact first-publication boundary.

**J. No H1 component is declared safe, unaffected or vulnerability-free.** The
only permitted wording remains: the Debian Security Tracker exposes no
source-package vulnerability entry at the measured timestamp.

**K.** No Decision-0022/D exception is created. **L.** No Decision-0022/F
exception is created.

**M.** No general rule is created. Future tracker-less packages are **not**
automatically accepted; this disposition covers exactly the named subjects on
exactly this candidate.

**N.** H1 relevance is recorded by kind rather than flattened:
**runtime-linked** (`gcc-14`), **trust-material** (`ca-certificates`), and
**privilege-adjacent** (`libselinux`, `libcap-ng`, `libmd`).

**O.** Absence of demonstrated supported-entrypoint reachability **does not erase
shipment or residual relevance**. Decision 0022/C keeps reachability and
shipment hygiene separate, and that separation holds here.

**P.** Publication-time Decision-0022/J freshness re-reading remains
**mandatory**. This acceptance is candidate-time evidence, not a certificate.

**Q.** The acceptance is invalidated, or must be re-read, under the conditions
recorded below.

**R.** `linux/amd64` remains the only security-evidence platform.

**S.** No runtime or source remediation is selected. **T.** No OCI publication is
authorized. **U.** `deployable_artifact` remains `false`. **V.** Source identity
remains paused.

## Invalidation and revisit conditions

The disposition is candidate-bound and must be re-read if any of these occur:

1. the Debian Security Tracker gains a vulnerability entry for an H1 subject;
2. Debian publishes a supported fixed version above an installed version;
3. Debian security-support status changes from NORMAL for a shipped package;
4. an H1 package or source version changes;
5. a Python or Debian base refresh changes the package inventory or versions;
6. the supported runtime begins to invoke, load, expose, or pass
   untrusted/project-controlled input to one of these components in a materially
   new way;
7. the SUID/SGID or file-capability inventory changes materially;
8. platform scope expands beyond `linux/amd64`;
9. another authoritative vendor observation materially changes the known state;
10. the final Decision-0022/J publication-time freshness read.

## Consequences

- The publication boundary now carries an explicit, named residual rather than an
  unenumerated one. That is the whole value: five packages are on the record as
  material unknowns, not quietly absorbed into a green count.
- Two of the three privilege-adjacent subjects are material only because their
  libraries execute inside setuid-root processes the supported runtime never
  invokes. That is a real distinction and the Decision keeps it visible rather
  than resolving it in either direction.
- `ca-certificates` is accepted while the runtime has no supported network-I/O
  entrypoint. If one is ever added, condition 6 fires and this disposition must
  be re-read before it ships.
- Nothing here reduces the work still required for publication. The three CPython
  residuals, the licence and legal boundary, first-party source-security
  sufficiency, registry identity and the public claim all remain open.
