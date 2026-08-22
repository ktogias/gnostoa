---
type: Decision
title: Publish v0.1.1 as the first public GHCR image
description: Publish one linux/amd64 OCI image from the exact immutable v0.1.1 source identity, binding the artifact to the GHCR-read-back manifest digest and one GitHub build-provenance attestation without claiming reproducibility.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T16:50:35Z"
sources:
  - id: ghcr-publication-work-item
    resource: https://github.com/ktogias/gnostoa/issues/86
    title: Publish Gnostoa v0.1.1 to GHCR
x-project-knowledge:
  id: kit.decision.0039.publish-v0-1-1-as-the-first-public-ghcr-image
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /decisions/0028-bind-the-published-oci-runtime-source-to-the-git-candidate.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
    - kind: references
      target: /decisions/0037-provide-a-version-bound-cpython-third-party-attribution-bundle.md
    - kind: supersedes
      target: /decisions/0038-establish-v0-1-1-as-a-source-only-patch-release-identity.md
---

# Publish v0.1.1 as the first public GHCR image

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
artifact selection and conditional provider-effect authority are the
maintainer's; this record is faithful transcription.

## Context

The immutable `v0.1.1` source-only prerelease is already bound to commit
`84cc4959d9fb0b315084cc49a5381c13166b6554`, tree
`938a789f807b898797d2e634b7bfbaaedfe29a63` and annotated tag object
`ac7faf520bad82edd13ed41c6f9a9c8e686e019e`. Its measured `linux/amd64`
runtime uses the pinned `python:3.12-slim` index digest
`sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a`,
CPython 3.12.14 and Expat 2.8.3. Decisions 0035 and 0037 retain their bounded
security and attribution meanings.

The owner accepts that exact-digest rebuild repeatability is not required for
this first image. One authorized CI build and the manifest digest read back
from GHCR define the immutable artifact. This is not a reproducibility claim.

## Decision

**A. Exact artifact.** Publish only
`ghcr.io/ktogias/gnostoa:0.1.1`, for exactly `linux/amd64`, from the immutable
`v0.1.1` source identity above. Do not create `latest` or another tag.

**B. Canonical identity.** The OCI artifact identity is
`ghcr.io/ktogias/gnostoa@sha256:<registry-read-back-manifest-digest>`. The
Decision does not predict that digest or a workflow run identity. Record both
only after the provider effect.

**C. Write once.** The `0.1.1` tag must be absent before publication and must
never be overwritten. The workflow fails closed on an existing tag and on an
authorization, network or ambiguous lookup failure. Any rebuild requires a new
patch version. Failure after push does not authorize deletion or overwrite.

**D. Publication route.** One input-free, hard-coded `workflow_dispatch`
workflow uses the canonical `ci/build-runtime` source-binding route, one
ephemeral BuildKit builder, the pinned source/base inputs and Docker CLI. It
uses only pinned GitHub-owned checkout and attestation actions.

**E. Permissions.** The publication job receives only `contents: read`,
`packages: write`, `id-token: write` and `attestations: write`. No personal
access token, Docker-maintained action or additional provider permission is
selected.

**F. Verification before and after push.** Before push, verify the local image
against the accepted platform, runtime inventory, non-root configuration,
public-surface digest, exact 12-file SB2 and version-bound
`THIRD_PARTY_NOTICES`. After push, read the manifest digest from GHCR, pull by
that digest and repeat the same bounded verification. Command success alone is
not registry truth.

**G. Provenance.** Generate one GitHub build-provenance attestation whose
subject name is `ghcr.io/ktogias/gnostoa` and whose subject digest is the exact
registry-read-back manifest digest. Push it to GHCR, create no linked-artifact
storage record, and verify it with GitHub CLI. No cosign signature or SBOM is
selected.

**H. Public provider state.** After the first push, make the user-scoped GHCR
package public, read back its visibility, repository linkage and access, then
verify an anonymous pull by immutable digest. The package remains linked to
`ktogias/gnostoa`. No post-publication withdrawal of Actions package access is
required by this Decision.

**I. Release projection.** Preserve the existing GitHub Release as a
prerelease. After publication, add the image tag, immutable digest, platform,
pull-by-digest command, provenance-verification command and bounded non-claims
to its body. The Release remains a provider projection and does not redefine
the immutable source identity.

**J. Deployable artifact state.** Only after the public digest, anonymous pull,
attestation and runtime read-backs succeed may that exact digest be recorded as
`deployable_artifact: true` current state. This means that one verified artifact
is available for consumption; it is not deployment authorization or a
production-readiness claim.

**K. Freshness.** Immediately before dispatch, re-read the supported Python
3.12 release, the `python:3.12-slim` index and `linux/amd64` manifest,
docker-library revision and the three recorded CPython CVE/backport states. A
material source/base/security drift stops publication and requires a new patch
source identity.

**L. Supersession boundary.** This Decision supersedes only Decision 0038's
prohibition on OCI publication and its corresponding non-deployable state for
the exact successfully verified digest. The `v0.1.1` source identity,
prerelease status, security/legal non-claims and every other source-only
boundary remain unchanged.

## Consequences

- The first public OCI artifact is a registry object produced once by one
  authorized workflow run; its GHCR manifest digest, not the mutable-looking
  version tag or a local build result, is the consumer identity.
- Provider publication state, the attestation and the Release projection must
  be read back and reconciled before Work Item #86 can close.
- A later source or runtime rebuild cannot reuse `0.1.1`; it requires a new
  patch source identity and the smallest affected security, attribution and
  freshness re-binding.
- The lack of exact-digest rebuild repeatability remains explicit and does not
  weaken the write-once tag rule.

## Non-claims and exclusions

- The image is not claimed reproducible, generally secure, legally cleared,
  certified, production-ready or safe for arbitrary deployment.
- No source tag, GitHub-generated source archive, Dockerfile, runtime,
  dependency, licence, notice or first-party SB2 byte changes in this slice.
- No `latest`, multi-architecture image, package/site publication, deployment,
  cosign signature, SBOM or `org.opencontainers.image.licenses` annotation is
  created.
- Work Item #86 remains open through integration, provider effects, public
  read-back and reconciliation, and closes last.
