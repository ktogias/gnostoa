---
type: Decision
title: Select the v0.1.2 source and OCI publication series
description: Admit one exact-candidate v0.1.2 source-only prerelease and one write-once linux/amd64 GHCR publication series, with digest-bound provenance and post-publication reconciliation but no effect in this Phase-1 slice.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-24T14:24:39Z"
sources:
  - id: v0-1-2-publication-work-item
    resource: https://github.com/ktogias/gnostoa/issues/111
    title: Publish Gnostoa v0.1.2 source and OCI release series
  - id: v0-1-1-publication-result
    resource: ../assessments/v0-1-1-source-and-oci-publication-result.md
    title: v0.1.1 source and OCI publication result
  - id: v0-1-2-publication-result
    resource: ../assessments/v0-1-2-source-and-oci-publication-result.md
    title: v0.1.2 source and OCI publication result
x-project-knowledge:
  id: kit.decision.0044.select-the-v0-1-2-source-and-oci-publication-series
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0038-establish-v0-1-1-as-a-source-only-patch-release-identity.md
    - kind: references
      target: /decisions/0039-publish-v0-1-1-as-the-first-public-ghcr-image.md
    - kind: references
      target: /decisions/0040-reconcile-the-v0-1-1-source-and-oci-publication-result.md
    - kind: references
      target: /decisions/0043-prepare-a-bounded-v0-1-2-b3-readiness-candidate.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
    - kind: references
      target: /assessments/v0-1-1-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/v0-1-2-source-and-oci-publication-result.md
---

# Select the v0.1.2 source and OCI publication series

Recorded by `codex/gpt-5` from the accountable maintainer's selection. The
publication contract and the stop before every outward effect are the
maintainer's semantic choices; this record is faithful transcription.

## Context

Decision 0043 produced the integrated `v0.1.2` readiness candidate at commit
`908edf87fb280c2f778123d7b39d93a3370da188`, tree
`d5ec63552f4ed466405db8c322d3d3bd2a7924f6`. At Phase-1 admission,
distribution metadata and the default local OCI version were `0.1.2`, while the
immutable public source and OCI consumer identities still remained `v0.1.1`
and its registry digest.

Phase-1 preflight found no `v0.1.2` Git tag, GitHub Release or GHCR tag and no
released Python/base change that preempts this candidate. That observation
admits an exact reviewable publication Decision; it is not publication-time
freshness and it creates no provider effect.

The initially admitted Phase-1 repository change was `normal`: it recorded
candidate-bound governance and corrected stable navigation without changing
executable source, release verification or a publication mechanism. Exact-head
provider run `32739639579` then supplied valid RED evidence that the permanent
candidate-binding step still encoded task-specific assertions from the
historical `0.1.1` to `0.1.2` change. The owner re-admitted a bounded
`normative` correction in the same Work Item, Decision and Pull Request because
the correction changes the authoritative provider-verification contract. A
tag, GitHub Release, GHCR push and provenance record remain later `critical`
effects.

## Decision

**A. Exact proposed source subject.** The proposed `v0.1.2` source bytes are the
exact Git tree of the accountable-owner-accepted Phase-1 Pull Request head.
Provider read-back must record that head and tree. Because this Decision is
itself a member of that tree, it does not predict or embed its own future tree
identity. After separate merge authorization, the integrated squash commit may
be selected as the immutable source commit only when its tree is mechanically
equal to the accepted PR tree. The annotated tag must dereference to that exact
integrated commit and tree; no later or approximate subject may be substituted.

**B. Source release.** Create exactly one annotated tag, `v0.1.2`, and one
source-only GitHub **prerelease** targeted at it. The Release contains only the
provider-generated source archives: no curated assets, package or site
publication. The established source-only release runbook remains the procedure
authority.

**C. OCI publication.** Publish only
`ghcr.io/ktogias/gnostoa:0.1.2`, for exactly `linux/amd64`, by re-binding the
existing hard-coded v0.1.1 publication mechanism after the source identity
exists. Create no `latest` or other mutable tag, multi-architecture manifest,
cosign signature or OCI SBOM. Consumers are directed to the immutable
registry-read-back digest, not the version tag.

**D. Write once.** `0.1.2` is write-once. The workflow must fail closed unless
the exact tag is absent, repeat that check immediately before push and never
overwrite the tag. Authorization, network or ambiguous lookup failure is not
absence. Any rebuild requires a later patch version.

**E. Exact verification.** Before and after the provider effect, bind and verify
the exact source commit/tree, immutable base, public-surface digest, all 12 SB2
files and digests, `THIRD_PARTY_NOTICES`, platform and measured runtime
inventory. Read the manifest digest back from GHCR, pull by that digest and run
the existing runtime, public-digest, SB2 and notice controls against the pulled
artifact. Push success or tag resolution alone is not artifact identity.

**F. Provenance and public access.** Create one GitHub build-provenance
attestation whose subject is the registry-read-back image digest. Verify the
attestation and then confirm that the version tag still resolves to the same
digest. Read back public package visibility, repository linkage and anonymous
pull by immutable digest. The publication-workflow revision is provenance for
the provider execution; the checkout assertions, image metadata and
verification bind the application source separately.

**G. Digest-bound reconciliation.** Do not move the current digest-bound
release verifier or version-bound publication workflow using predicted
identities. After the exact tag object and OCI digest exist, perform one later
post-effect reconciliation under Work Item #111. That phase binds the existing
release-verification support to the immutable `v0.1.2` digest and makes
`ci/verify release` execute successfully before the publication series is
complete.

**H. Freshness boundary.** Immediately before tag/Release creation and again
immediately before OCI dispatch, read back the latest supported Python 3.12
release, the `python:3.12-slim` index and `linux/amd64` manifest,
docker-library revision and the three recorded CPython CVE/backport states. A
materially newer supported base or changed security disposition stops the
effect for a new source candidate; it must not silently replace `v0.1.2`.

**I. Distinct identities.** Keep distinct the immutable Git source commit and
tree, annotated tag object, public-surface digest, publication-workflow commit
and run, and registry manifest digest. The canonical OCI artifact identity is
the registry digest. None is a substitute for another.

**J. Preserve v0.1.1.** The `v0.1.1` tag, Release, source commit/tree and OCI
digest remain immutable historical identities. Do not modify, overwrite or
rebuild them while publishing `v0.1.2`.

**K. Claims and boundaries.** Exact-digest rebuild repeatability is not required
and no reproducibility claim is made. Publication does not establish production
readiness, deployment authority, general security, legal clearance or absence
of unknown defects. No package/site publication, multi-architecture scope,
registry-signing system or new release framework is selected.

**L. B3 ordering.** The first real B3 experiment remains unstarted. Candidate
selection or execution must wait until source/OCI publication, digest-bound
release verification and integrated/provider reconciliation have completed.

**M. Phase-1 effect boundary.** This Decision admits one Work Item, one branch,
this Decision, minimal navigation/projection, one exact reviewable Pull Request
and the bounded correction of its permanent PR candidate-binding verification.
That binding must retain exact checked-out commit/tree assertion, three-way
source/runtime/metadata-free-vendored public-surface equality, runtime
self-check and changed-path reporting. It must compare the complete current
12-file SB2 membership generically across the same three subjects and emit the
resulting exact manifests. It must not contain a version, Pull Request,
incident, changed-path or knowledge-only bypass; hard-code an earlier
candidate's file digests; or claim that equality alone proves X3 or G3 transfer
sufficiency. The required check executes even when the proposed change is
knowledge-only. Provider RED run `32739639579` is the characterization evidence;
a fresh run must bind the corrected final exact PR head and report every job,
with `SKIPPED` distinct from `PASS`.

This re-admission authorizes **no Phase-1 PR merge, tag, Release, workflow
dispatch, GHCR mutation, attestation, release-verifier re-binding, B3 selection
or Work Item closure**. Those effects require accountable-owner review of the
new exact PR head and the later freshness and reconciliation gates above.
That historical boundary governed Phase 1 and did not itself authorize the
later separately admitted source, publication or reconciliation effects.

**N. Observed source and OCI result.** Separate owner effects created annotated
tag `v0.1.2` at tag object
`d9ea04ea649132e74bd3d9b8b089b86ea7e0d6a7`, commit
`56f6c5ede9ff1d6585404d102aba8413994a2697` and tree
`6db26c9ce2eeaa82882bac82312f675ee19e6d0a`, then published exactly
`ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80`
for `linux/amd64`. Workflow run `32763848257`, attempt 1, read the digest back,
pulled and verified it, created attestation `42664371`, verified provenance and
anonymous access, and left `latest` absent. The durable result and evidence
limits live in the linked v0.1.2 publication assessment.

**O. Current release-verifier transition.** Bind `ci/verify release` to the
immutable v0.1.2 registry digest, never the version tag. Preserve fail-closed
platform, version, source-revision, runtime-inventory, public-digest, complete
12-file SB2, notice and self-check controls. `deployable_artifact=true` means
verified public artifact availability for that exact digest only; it does not
mean deployment authorization, production readiness, reproducibility, general
security or qualified legal clearance. v0.1.1 remains an immutable historical
artifact but ceases to be the current verifier target once this reconciliation
is integrated and read back.

**P. Publication-result authority and public projection.** Preserve one
authoritative v0.1.2 result assessment and route public status to the immutable
digest. Do not freeze mutable package permissions, visibility or linkage as
timeless source truth. Do not claim exact-digest rebuild repeatability for
v0.1.2: it was not tested, is not required for this release and any rebuild
requires a later patch version. B3 remains unstarted until this Work Item's
post-publication integration and provider reconciliation are complete.

## Consequences

- `v0.1.2` is now an immutable source identity and one public write-once
  `linux/amd64` OCI digest; the final repository reconciliation remains subject
  to exact-candidate owner acceptance and integrated read-back.
- Provider-created identities are recorded only after they exist; none is
  predicted in this Decision.
- The existing v0.1.1 mechanisms are reused in bounded version-specific phases,
  rather than generalized into a new release system.
- Permanent exact-candidate verification reports current evidence generically;
  it does not preserve assertions about one historical release delta or infer
  owner sufficiency from byte equality.
- Work Item #111 stays open through this post-publication reconciliation and is
  closed only after integrated/provider read-back; B3 stays paused.
