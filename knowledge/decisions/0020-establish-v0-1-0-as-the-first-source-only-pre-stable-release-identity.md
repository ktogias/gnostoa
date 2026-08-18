---
type: Decision
title: Establish v0.1.0 as the first source-only pre-stable release identity
description: Select v0.1.0 as Gnostoa's first named immutable source-only pre-stable release identity, binding one exact commit and its public-surface digest while publishing no package, image or documentation site.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-18T15:10:00Z"
sources:
  - id: release-identity-work-item
    resource: https://github.com/ktogias/gnostoa/issues/43
    title: Establish the first immutable source-only release identity
x-project-knowledge:
  id: kit.decision.0020.establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0012-use-versioned-public-schema-identifiers.md
    - kind: references
      target: /decisions/0010-license-gnostoa-under-apache-2.0.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: references
      target: /assessments/first-source-only-release-pre-effect-state.md
---

# Establish v0.1.0 as the first source-only pre-stable release identity

Recorded by `agent:claude-opus-5` from the accountable maintainer's disposition.
The semantic choice is the maintainer's; this record is faithful transcription.

## Context

Gnostoa's source repository is already public and identifies itself as `0.1.0`,
but nothing has ever been named as a release. No package, OCI image or
documentation site has been published, and no compatibility matrix, support
lifetime or cross-version promise exists.

The absence of any named identity is a real adoption friction: the documented
upgrade route in `guidance/reference/versioning-and-upgrades.md` begins "Fetch
the target released tag", and `docs/compatibility.md` requires pinning the exact
source revision together with the deterministic public-surface digest. Today
there is no tag to fetch and no named identity to pin.

A source-only release answers that without creating any distribution trust
surface: it names a commit that already exists, adds no artifact, and requires
no new capability. Package, image and documentation-site publication were
evaluated separately and are not selected here.

## Decision

**A.** Select **`v0.1.0`** as the first named Gnostoa source release identity.

**B.** The tag identifies **one exact Git commit and its deterministic
public-surface digest**.

**C.** The release is **SOURCE-ONLY**.

**D.** It publishes **no curated wheel, source distribution, OCI image or
documentation site**.

**E.** `v0.1.0` does **not** establish cross-version compatibility, migration
support, support lifetime, LTS, production readiness or independent assurance.

**F.** The public surface continues to require **exact source and digest
binding**; a version label alone is not sufficient identity.

**G.** Future package, OCI image and documentation-site publication remain
**separate effects with separate admission and evidence**.

**H.** **B3 transfer remains deferred** and is neither satisfied nor activated by
this release.

**I.** **No workflow or control successor is selected.**

**J.** The release does **not** flip `deployable_artifact` and does **not**
activate delivery policy.

**K.** **No signing, attestation, SLSA or provenance guarantee is claimed**,
because the current repository contract requires none for this source-only
effect.

`v0.1.0` is a pre-stable identity. It is deliberately not described as a stable
release, a production release or a compatibility baseline.

## Consequences

- The release candidate is defined as **the exact protected-main commit after
  the preparation Change Request integrates** — not the research base
  `85766e8df2add27dc2234792547e6ce078228d04`. That candidate must have `policy`,
  `fast`, `regression`, `smoke`, `extended` and the runtime `self-check` passing,
  a clean repository state, and its public-surface digest recomputed and
  recorded, before any provider effect.
- The aggregate provider effect is **`critical`** under
  `guidance/reference/change-classification-and-approval.md`, which places
  *release* in critical scope. It therefore keeps its own owner authorization,
  and integrating the preparation records does not authorize it.
- Pre-effect evidence takes the form permitted for non-executable work by
  `guidance/workflows/develop-verification-first.md`: an unmet structural
  criterion plus planned human review. No executable test is manufactured for a
  provider event, which that guidance explicitly discourages.
- `ci/release_smoke.py` is **not** made a requirement of this effect. It covers
  package artifacts, which this release does not publish, and no effective
  policy requires it here.
- Provider-generated source archives may exist as projections of the tag. They
  are **not** Gnostoa package releases and must not be described as such.
- Naming an identity creates a durability obligation: `v0.1.0` must not later be
  moved or reused for a different commit.
- What this Decision deliberately leaves open: whether any artifact is ever
  published, and what a subsequent version would promise.
