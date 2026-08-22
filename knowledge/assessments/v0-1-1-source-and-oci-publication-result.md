---
type: Source
title: v0.1.1 source and OCI publication result
description: Durable reconciliation of the immutable v0.1.1 source identity, first public linux/amd64 OCI digest, provenance, bounded repeatability and freshness evidence, and digest-bound post-publication verification.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T20:27:02Z"
sources:
  - id: publication-result-reconciliation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/89
    title: Reconcile the v0.1.1 source and OCI publication result
x-project-knowledge:
  id: kit.assessment.v0-1-1-source-and-oci-publication-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0040-reconcile-the-v0-1-1-source-and-oci-publication-result.md
    - kind: references
      target: /decisions/0037-provide-a-version-bound-cpython-third-party-attribution-bundle.md
    - kind: references
      target: /decisions/0038-establish-v0-1-1-as-a-source-only-patch-release-identity.md
    - kind: references
      target: /decisions/0039-publish-v0-1-1-as-the-first-public-ghcr-image.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
---

# v0.1.1 source and OCI publication result

## Immutable result

| Authority | Exact identity |
|---|---|
| Source release | annotated tag `v0.1.1` |
| Tag object | `ac7faf520bad82edd13ed41c6f9a9c8e686e019e` |
| Source commit | `84cc4959d9fb0b315084cc49a5381c13166b6554` |
| Source tree | `938a789f807b898797d2e634b7bfbaaedfe29a63` |
| Source public-surface digest | `sha256:33792909555029c1b2879d78f112ba0e3227d73abac0b89652781554fee1af74` |
| Published tag | `ghcr.io/ktogias/gnostoa:0.1.1` |
| Immutable OCI artifact | `ghcr.io/ktogias/gnostoa@sha256:73e5bd55fb4fed4accc836294a97b144d8b7060d68b19c3631ab7c05b5cd1455` |
| Platform | exactly `linux/amd64` |
| Immutable base | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |

The source tag was created and read back through Work Item
[#84](https://github.com/ktogias/gnostoa/issues/84) and PR
[#85](https://github.com/ktogias/gnostoa/pull/85). It names the exact commit and
tree above. The public-surface digest corroborates that source but is not a
complete source identity. The OCI consumer identity is the registry manifest
digest, not the version tag.

## Bounded repeatability result

Before publication, the exact `v0.1.1` tag was built twice through the existing
canonical `ci/build-runtime` route for `linux/amd64`, using isolated clean
ephemeral builders, empty build caches, identical explicit inputs and arguments,
the immutable base above, and no source substitution. The comparison covered
manifest, config, layers and DiffIDs, image history, runtime inventory, public
digest, the 12-file SB2 and `THIRD_PARTY_NOTICES`.

Result: **NOT EXACT-DIGEST REPEATABLE** for that bounded envelope. The first
evidenced divergence was wall-clock-sensitive image metadata followed by
APT/DPKG-derived filesystem state in the differing image objects. The measured
runtime inventory, public surface, SB2 and notice content remained equivalent;
that semantic equivalence is not exact-image reproducibility.

The owner consciously selected one authorized CI build plus its registry-read-
back digest as the first artifact identity. No rebuild-reproducibility claim is
made, and `0.1.1` may not be overwritten; a rebuild requires a new patch
version.

The disposable OCI layouts, build logs, complete per-object digest maps and
builder-version transcripts from the experiment were not retained in canonical
repository or provider evidence. This record preserves the declared envelope,
accepted negative result and earliest evidenced cause; it does not manufacture
missing raw artifacts or make the experiment independently reproducible.

## Publication-time freshness result

The accepted pre-source-identity packet and the mandatory read immediately
before publication both found no material source, base or released-security
drift: the latest supported Python/docker-library 3.12 release remained
CPython 3.12.14 and the selected `python:3.12-slim` base remained bound to the
immutable digest above. CVE-2026-19672 and CVE-2026-15806 had 3.12 fixes merged
but unreleased; CVE-2026-17084 had no observed 3.12 backport. A merged fix was
not represented as released remediation. The owner accepted those specific
bounded residuals for `v0.1.1` and publication proceeded without a source or
runtime refresh.

The original upstream retrieval transcript, platform-manifest response and
standalone freshness packet were not retained as canonical artifacts. This is
the dated verdict used for the 2026-08-22 effect, not a claim about current
Python or CVE state. Every later release still requires its own publication-time
freshness read.

## GHCR contract and provider result

The dated 2026-08-22 preflight found no existing personal `gnostoa` package and
no selected native GHCR guarantee that made the version tag immutable. Decision
0039 therefore selected workflow-enforced write-once behaviour: unambiguous tag
absence was checked before push and again immediately before push, and any
rebuild requires another patch version. This dated provider-capability finding
is not a timeless claim that GHCR features or account policy cannot change.

Publication workflow run
[`32587462246`, attempt 1](https://github.com/ktogias/gnostoa/actions/runs/32587462246)
executed at workflow/source revision
`c377d11611b958a31276eff9514f2297a073ea18`. It published only tag `0.1.1`,
read the manifest digest back from GHCR, pulled by that digest, and verified the
selected runtime: CPython 3.12.14, bundled Expat 2.8.3, 118 Debian packages,
8 Python distributions, non-root execution, pip and ensurepip absent, the exact
public digest, 12/12 SB2 and `/opt/gnostoa/THIRD_PARTY_NOTICES` digest
`sha256:68978e9fc1875f275c0dfb9bd71ed19d025b01f66409bb31d785d86165ee691c`.
The OCI standard licence annotation remained absent.

The GitHub SLSA provenance subject is the exact image name and manifest digest.
Its workflow identity and resolved Git dependency bind execution to
`c377d11611b958a31276eff9514f2297a073ea18`; that SHA is the publication
workflow revision, not the immutable application-source commit. Binding the
image contents to `v0.1.1` and
`84cc4959d9fb0b315084cc49a5381c13166b6554` additionally relies on the
workflow's checked-out-tag/commit/tree assertions, immutable-base assertion,
image source/revision metadata and the digest-pulled runtime, public-surface,
SB2 and notice verification. Provenance does not collapse those distinct
identities into one.

## Two-phase post-effect reconciliation

Work Item [#86](https://github.com/ktogias/gnostoa/issues/86) deliberately kept
`deployable_artifact=false` during its first phase. PR
[#87](https://github.com/ktogias/gnostoa/pull/87) integrated the publication
contract; the provider effect then created the digest and attestation, made the
package public, confirmed repository linkage and an anonymous pull, and updated
the existing source prerelease.

Only after the immutable digest existed did PR
[#88](https://github.com/ktogias/gnostoa/pull/88) bind `ci/verify release` to
that digest. Exact integrated-main run
[`32588681360`](https://github.com/ktogias/gnostoa/actions/runs/32588681360)
executed the digest-bound release verification. The post-effect result then set
`deployable_artifact=true` only for the verified immutable digest and closed
Work Item #86 last. This state means verified public artifact availability; it
does not authorize deployment or claim production readiness.

The [v0.1.1 GitHub prerelease](https://github.com/ktogias/gnostoa/releases/tag/v0.1.1)
remains a source Release with provider-generated archives and no curated assets.
Its body projects the immutable OCI digest and verification commands without
redefining the source tag.

## Bounded result and limits

- One public `linux/amd64` image is available by immutable digest. No `latest`,
  multi-architecture image, package/site publication or deployment was selected.
- No cosign signature or OCI SBOM was selected. The GitHub provenance described
  above is the only selected attestation.
- No exact rebuild reproducibility, general security, qualified legal clearance,
  production readiness, security certification or safety for arbitrary consumer
  deployment is claimed.
- Mutable package visibility, permissions, linkage presentation and provider UI
  remain live provider state. Their successful 2026-08-22 read-back is evidence
  of the completed effect, not a promise that those fields can never change.
- Knowledge and documentation commits after publication do not modify the
  immutable `v0.1.1` source or OCI artifact.
