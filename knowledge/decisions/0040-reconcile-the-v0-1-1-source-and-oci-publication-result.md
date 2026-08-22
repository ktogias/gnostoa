---
type: Decision
title: Reconcile the v0.1.1 source and OCI publication result
description: Select one durable result record for the completed v0.1.1 source and OCI effects, correct public projections and retain the exercised source-release procedure with an evidence-driven revisit trigger.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T20:27:02Z"
sources:
  - id: publication-result-reconciliation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/89
    title: Reconcile the v0.1.1 source and OCI publication result
x-project-knowledge:
  id: kit.decision.0040.reconcile-the-v0-1-1-source-and-oci-publication-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: references
      target: /decisions/0021-adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance.md
    - kind: references
      target: /decisions/0038-establish-v0-1-1-as-a-source-only-patch-release-identity.md
    - kind: references
      target: /decisions/0039-publish-v0-1-1-as-the-first-public-ghcr-image.md
    - kind: governs
      target: /assessments/v0-1-1-source-and-oci-publication-result.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
---

# Reconcile the v0.1.1 source and OCI publication result

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
selection of durable authority and the runbook revisit semantics are the
maintainer's; this record is faithful transcription.

## Context

The `v0.1.1` source release and first public `linux/amd64` OCI publication have
completed. Their immutable identities and bounded provider evidence are
distributed across Decisions, provider records and Work Items, while public
repository projections still describe `v0.1.0` as current and say that no image
exists. One bounded reconciliation is needed; no release or artifact is being
rebuilt, changed or republished.

## Decision

**A. Durable result authority.** Select
[v0.1.1 source and OCI publication result](../assessments/v0-1-1-source-and-oci-publication-result.md)
as the authoritative durable result record for the immutable `v0.1.1` source
identity, the published OCI digest, the bounded repeatability and freshness
evidence, provenance, and the two-phase publication reconciliation. Immutable
provider objects remain authoritative for their own identities; mutable live
provider state remains provider-authoritative.

**B. Public projections.** Correct `README.md`, `docs/status.md` and
`docs/compatibility.md` to identify `v0.1.1` and the public, digest-pinned
`linux/amd64` GHCR artifact. Artifact availability is not production readiness,
deployment authorization, reproducibility, general security or legal clearance.

**C. Source-release procedure.** The
[source-only release runbook](../runbooks/publish-source-only-release.md)
operated successfully for `v0.1.1`: it preserved exact candidate binding,
separated repository preparation from provider authority, required tag and
Release read-back, and kept the Work Item open through reconciliation. Retain
the procedure without expansion.

**D. Revisit trigger.** Decision 0021's and the runbook's now-fired “next
completed source-only release” revisit condition is replaced only by this
evidence-driven trigger: revisit the procedure when an observed release failure
or a material provider or release-semantics change challenges it. A passage of
time or another successful release does not by itself require procedural
expansion.

**E. Identity preservation.** Knowledge and documentation commits after the
release do not alter or replace the immutable `v0.1.1` tag, commit, tree or OCI
manifest digest. The public-surface digest, Git source identity and registry
manifest digest remain distinct authorities.

**F. Scope.** This is a normal Gnostoa-self knowledge/documentation change. It
creates no workflow, policy, guardrail, test, runtime, tag, Release, GHCR or
attestation mutation; it does not implement Issue #11 or introduce a generic
release or licence mechanism.

## Consequences

- Future readers have one durable result authority plus links rather than
  synchronized summaries of the provider history.
- The source-only procedure remains specialized Gnostoa-self knowledge, not
  adopter guidance or a promise that future provider behaviour is unchanged.
- Raw repeatability outputs that were not retained are not reconstructed or
  amplified into stronger evidence.

### Non-claims

- This Decision does not claim reproducibility, production readiness, general
  security, qualified legal clearance or authorization for another release,
  publication or deployment.
