---
type: Decision
title: Establish v0.1.1 as a source-only patch release identity
description: Select v0.1.1 as Gnostoa's next immutable source-only pre-stable identity, bound to the exact integrated Git commit and tree with no OCI, package, site or deployment effect.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T13:00:07Z"
sources:
  - id: v0-1-1-source-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/84
    title: Publish Gnostoa v0.1.1 as a source-only release
x-project-knowledge:
  id: kit.decision.0038.establish-v0-1-1-as-a-source-only-patch-release-identity
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
    - kind: references
      target: /decisions/0021-adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance.md
    - kind: references
      target: /decisions/0030-refresh-the-official-python-312-base-for-cpython-security-fixes.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
    - kind: references
      target: /decisions/0037-provide-a-version-bound-cpython-third-party-attribution-bundle.md
---

# Establish v0.1.1 as a source-only patch release identity

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
semantic choice and conditional provider-effect authorization are the
maintainer's; this record is faithful transcription.

## Context

Gnostoa's only existing immutable source identity is the historical `v0.1.0`
release. The current cumulative candidate now includes the bounded OCI/security
preparation, final G3 disposition and the CPython-3.12.14-bound third-party
attribution bundle. The owner accepts its recorded runtime residuals and selects
the smallest patch identity without authorizing any binary publication.

## Decision

**A.** Select **`v0.1.1`** as Gnostoa's next source-only pre-stable patch
release identity.

**B.** The immutable identity is the exact protected-main Git commit and Git
tree after the bounded release preparation is integrated and reconciled. The
deterministic public-surface digest remains corroborating evidence; it is not a
complete source identity and cannot replace the commit-and-tree binding.

**C.** Align only release-version metadata needed for `v0.1.1`: the Python
distribution version and the default OCI version label. Profile, policy,
schema and OKF versions are independent public contracts and remain unchanged.
No functional executable behaviour is selected.

**D.** The release effect consists only of one annotated `v0.1.1` Git tag, one
source-only GitHub pre-release bound to that existing tag, and the provider's
generated source archives. No curated release asset is selected.

**E.** Accept the measured CPython 3.12.14 runtime candidate. The three recorded
post-release residuals remain bounded and non-blocking for this source identity:
CVE-2026-19672 and CVE-2026-15806 have merged but unreleased 3.12 backports;
CVE-2026-17084 has no observed 3.12 backport. A merged fix is not represented as
a released remediation, and publication-time freshness remains mandatory under
Decision 0022.

**F.** Decision 0035's bounded G3 result may be proportionally re-bound only
after the exact candidate proves unchanged SB2 bytes and unchanged measured
runtime/security behaviour. This Decision makes no general security claim.

**G.** Decision 0037's CPython-3.12.14-bound `THIRD_PARTY_NOTICES` must remain
tracked and installed at `/opt/gnostoa/THIRD_PARTY_NOTICES`. That practical
attribution surface is preserved without claiming qualified legal clearance.

**H.** The repository-preparation change is `normal`. The tag and Release are a
separate `critical` provider effect, authorized by the owner only after exact
integrated-candidate verification and freshness read-back.

**I.** Keep Work Item #84 open through merge, tag, Release, provider read-back
and reconciliation. Provider-generated source archives are projections of the
tag, not curated Gnostoa package artifacts.

**J.** This Decision authorizes no OCI build or push, package or site
publication, registry mutation, provenance, signing, attestation, deployment,
or `org.opencontainers.image.licenses` annotation.

**K.** The release does not claim that Gnostoa is deployable, generally secure,
legally cleared or certified. `deployable_artifact` remains `false`.

## Consequences

- `v0.1.1` must never be moved or reused for a different Git object.
- If source, base, security or attribution state materially drifts before the
  provider effect, the release stops for owner re-binding.
- OCI reproducibility and image digest evidence, registry identity and
  permissions, provenance, signing, attestation, any later architecture scope,
  the public OCI claim and OCI publication remain separate gates.
- The source-only release creates no OCI/package/site publication authority and
  does not make Gnostoa a deployable artifact.
