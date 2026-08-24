---
type: Source
title: v0.1.2 source and OCI publication result
description: Durable reconciliation of the immutable v0.1.2 source identity, public linux/amd64 OCI digest, provenance, publication-time freshness, runtime verification and bounded delivery-efficiency evidence.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-24T19:04:22Z"
sources:
  - id: v0-1-2-publication-work-item
    resource: https://github.com/ktogias/gnostoa/issues/111
    title: Publish Gnostoa v0.1.2 source and OCI release series
  - id: v0-1-2-source-release
    resource: https://github.com/ktogias/gnostoa/releases/tag/v0.1.2
    title: Gnostoa v0.1.2
  - id: v0-1-2-publication-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/32763848257
    title: Publish Gnostoa v0.1.2 OCI image
  - id: v0-1-2-provenance
    resource: https://github.com/ktogias/gnostoa/attestations/42664371
    title: Gnostoa v0.1.2 OCI build provenance
x-project-knowledge:
  id: kit.assessment.v0-1-2-source-and-oci-publication-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0044-select-the-v0-1-2-source-and-oci-publication-series.md
    - kind: references
      target: /assessments/v0-1-1-source-and-oci-publication-result.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
---

# v0.1.2 source and OCI publication result

## Immutable result

| Authority | Exact identity |
|---|---|
| Source release | annotated tag `v0.1.2` |
| Tag object | `d9ea04ea649132e74bd3d9b8b089b86ea7e0d6a7` |
| Source commit | `56f6c5ede9ff1d6585404d102aba8413994a2697` |
| Source tree | `6db26c9ce2eeaa82882bac82312f675ee19e6d0a` |
| Source public-surface digest | `sha256:bd8078467b0189d535f222072253e1ef9e8f5fb780f55b56269738cb8f4ef095` |
| Published version tag | `ghcr.io/ktogias/gnostoa:0.1.2` |
| Immutable OCI artifact | `ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80` |
| Platform | exactly `linux/amd64` |
| Immutable base | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| GitHub Release | `375865825`, prerelease, zero curated assets |

The public-surface digest corroborates a bounded public source projection; it
is not the complete Git source identity. The version tag is a human-facing,
workflow-enforced write-once reference. The registry manifest digest is the
immutable OCI consumer identity. No `latest` or additional image tag exists.
The immutable `v0.1.1` source and artifact remain valid historical results.

## Provider execution and source binding

One manual, input-free workflow dispatch created
[run `32763848257`, attempt 1](https://github.com/ktogias/gnostoa/actions/runs/32763848257)
from workflow source SHA
`778646eb13ecc450e0fc55f4fd937ef68cfaee90`. The job checked out annotated tag
`v0.1.2` and asserted the tag object, application commit, tree, version,
immutable base and clean tracked state before building. It then checked tag
absence again immediately before its single push, read the manifest digest back
from GHCR, pulled by that digest and repeated the runtime verification.

The GitHub provenance subject is the exact image name and manifest digest. Its
signer is
`ktogias/gnostoa/.github/workflows/publish-oci.yml@refs/heads/main`; its workflow
and resolved Git dependency identify `778646eb13ecc450e0fc55f4fd937ef68cfaee90`
and invocation `32763848257/attempts/1`. That is publication-workflow provenance,
not the application-source commit. Application-source binding to `v0.1.2` and
`56f6c5ede9ff1d6585404d102aba8413994a2697` additionally rests on the exact
checkout assertions, source/revision image metadata and digest-pulled runtime,
public-surface, SB2 and notice verification.

[Attestation `42664371`](https://github.com/ktogias/gnostoa/attestations/42664371)
was verified for the immutable subject. The registry-stored attestation object
was
`sha256:cfab595a08746739d64d400790d64b9a2b93566337c06200d62beb9753a38c0c`;
it is not a substitute for the subject artifact digest.

## Runtime and public read-back

The registry-read-back artifact and a credentials-isolated anonymous digest
pull verified:

- exactly `linux/amd64`, version `0.1.2` and source revision
  `56f6c5ede9ff1d6585404d102aba8413994a2697`;
- CPython 3.12.14 with bundled Expat 2.8.3;
- 118 Debian packages and 8 Python distributions;
- UID/GID 10001, non-root execution, and pip and ensurepip absent;
- no `org.opencontainers.image.licenses` annotation;
- public digest
  `sha256:bd8078467b0189d535f222072253e1ef9e8f5fb780f55b56269738cb8f4ef095`;
- all 12 expected SB2 paths and exact per-file digests;
- `/opt/gnostoa/THIRD_PARTY_NOTICES` digest
  `sha256:68978e9fc1875f275c0dfb9bd71ed19d025b01f66409bb31d785d86165ee691c`;
  and
- the runtime self-check.

After attestation, `0.1.2` still resolved to the same registry digest and
`latest` remained absent. The dated 2026-08-24 provider read-back found the
package public and linked to `ktogias/gnostoa`, and anonymous pull succeeded.
Visibility, linkage presentation, permissions and access settings remain
mutable provider-authoritative state, not timeless guarantees in this record.

The existing GitHub Release was updated after publication and read back as
prerelease `true`, draft `false`, target
`56f6c5ede9ff1d6585404d102aba8413994a2697`, with zero curated assets. Its body
records the immutable pull and provenance-verification commands and keeps the
source identity distinct from the workflow provenance identity.

## Publication-time freshness

The mandatory read immediately before dispatch found no material source/base
preemption. Python 3.12.14 remained the latest supported 3.12 release. The
selected `python:3.12-slim` index digest remained the immutable base above, its
`linux/amd64` manifest remained
`sha256:876416ecde9aca2bcc90e1fb0c7a9500bbf749f5788b70f82d4c5a5c2357f8b4`,
and docker-library/python remained at revision
`f2c5d1b8a6adecb5b00b3c9331d4f863beade6b3` for that image state.
CVE-2026-19672 and CVE-2026-15806 retained 3.12 backports that were merged but
unreleased; no 3.12 backport was observed for CVE-2026-17084. A merged fix was
not represented as released remediation. This is the dated verdict for the
2026-08-24 effect; every future release needs a new freshness decision.

## Digest-bound release verification

The post-publication reconciliation changes `ci/verify release` from the
historical v0.1.1 digest to the immutable v0.1.2 digest above. It pulls by
digest—not by `0.1.2`—and fails closed on platform, version, source revision,
runtime inventory, public digest, 12-file SB2, notices and self-check. The
existing `deployable_artifact=true` capability then denotes verified public
artifact availability for this exact digest only. It does not authorize
deployment or claim production readiness, reproducibility, general security or
qualified legal clearance. v0.1.1 remains a valid historical artifact but is no
longer the current verifier target after this reconciliation is integrated and
read back.

## Bounded process-efficiency result

Publication used one dispatch, had zero publication failures or retries, and
the workflow completed in 1 minute 16 seconds. Centralizing the release version,
source identities, image, base, public digest and notice digest in one named
workflow constant block reduced duplicate version-bound literals without
weakening authorization or verification.

Earlier Phase-1 provider run `32739639579` supplied one avoidable failure from
stale assertions tied to the historical `0.1.1` to `0.1.2` candidate delta and
required replacement exact-head verification after correction. The permanent
candidate binding is now candidate-generic; the publication workflow remains
deliberately version-bound.

Owner checkpoints remain intentional before integration, immutable source-tag
creation, source Release creation, the write-once OCI dispatch and final
post-publication reconciliation. Those checkpoints authorize irreversible or
public provider effects; their presence is not evidence for automatic release
or a generic publication framework.

## Limits and non-claims

- Exact-digest rebuild repeatability was not tested for v0.1.2 and is not
  claimed. Any rebuild requires a later patch version.
- No `latest`, multi-architecture image, cosign signature, OCI-attached SBOM,
  Python package, documentation-site publication or deployment was selected.
- Artifact availability and digest-bound verification do not establish
  production readiness, deployment authorization, general security, qualified
  legal clearance, compatibility with arbitrary projects or absence of unknown
  defects.
- No population-level release reliability, productivity or adoption claim is
  derived from one successful publication.
- B3 has not begun. This source/OCI result is Gnostoa-self delivery evidence,
  not independent-adopter transfer evidence.
