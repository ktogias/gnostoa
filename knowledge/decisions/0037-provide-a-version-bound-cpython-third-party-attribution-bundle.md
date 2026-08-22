---
type: Decision
title: Provide a version-bound CPython third-party attribution bundle
description: Add a conservative CPython-3.12.14-bound third-party notice surface to the measured Gnostoa runtime without changing the composite OCI licence annotation or making a legal-clearance claim.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T11:32:38Z"
sources:
  - id: third-party-attribution-work-item
    resource: https://github.com/ktogias/gnostoa/issues/82
    title: Provide a version-bound CPython third-party attribution bundle
x-project-knowledge:
  id: kit.decision.0037.provide-a-version-bound-cpython-third-party-attribution-bundle
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: supersedes
      target: /decisions/0032-omit-composite-oci-licence-annotation-until-an-image-wide-expression-is-selected.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
    - kind: references
      target: /assessments/oci-licence-metadata-and-cpython-attribution-result.md
---

# Provide a version-bound CPython third-party attribution bundle

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
semantic choice is the maintainer's; this record is faithful transcription and
not legal advice or legal clearance.

Scope: **Gnostoa-self first `linux/amd64` OCI publication candidate using
CPython 3.12.14.**

## Context

Decision 0032 kept CPython's incorporated-software attribution as a qualified
review residual and deliberately selected no third-party notice aggregator. A
subsequent bounded evidence packet identified the exact upstream licence stack,
the installed runtime evidence, and HACL-derived notices not represented in the
CPython incorporated-software appendix. The owner now selects a conservative
version-bound distribution surface without changing the executable subject or
the composite-image annotation choice.

## Decision

**A.** Add one checked-in `THIRD_PARTY_NOTICES` file and install that exact file
at `/opt/gnostoa/THIRD_PARTY_NOTICES` through the existing candidate-source
packaging route.

**B.** Bind the bundle to CPython 3.12.14. It contains the exact CPython 3.12.14
licence stack and incorporated-software notices from `Doc/license.rst`, plus the
confirmed provenance and licence notices for the HACL-derived files shipped in
that CPython source but absent from that appendix.

**C.** A Python or base upgrade requires refreshing and re-verifying the notice
bundle against the newly selected source. The current bundle must not be
silently transferred to a different CPython version.

**D.** Preserve the Gnostoa `LICENSE` and `NOTICE`, installed package-specific
licence evidence and the official image's existing CPython licence file.

**E.** The optional `org.opencontainers.image.licenses` annotation remains
absent. No aggregate SPDX expression is selected or inferred.

**F.** This Decision supersedes **only** Decision 0032 clause J, which selected
no third-party notice aggregator. Decision 0032's image-annotation choice,
evidence distinctions, non-claims and every other clause remain in force.

**G.** The notice bundle is conservative distribution metadata. It does not
assert legal compliance, legal sufficiency, licence compatibility, or qualified
legal clearance, and it creates no generic licence-management mechanism.

**H.** The change must preserve the 12-file first-party SB2 byte-for-byte. G3
may be proportionally re-bound only after runtime/base behaviour and SB2
equality are read back; no deep G3 replay is implied by the attribution-only
bytes.

**I.** This Decision authorizes no source identity, tag, release, OCI or package
publication, registry mutation, or deployment. `deployable_artifact` remains
`false`.

## Consequences

- Consumers of the measured runtime can read the checked-in attribution bundle
  at a stable installed path without replacing any component-specific evidence.
- Base freshness and attribution freshness become explicitly coupled: a base
  upgrade cannot reuse the CPython-3.12.14-bound bundle without read-back.
- The repository and runtime gain non-executable attribution bytes. The public
  inheritance digest and first-party executable SB2 are expected to remain
  unchanged and must be measured rather than assumed.
- Source identity and every outward publication effect remain paused for their
  separately governed gates.
