---
type: Source
title: v0.2.0 source and OCI publication result
description: Durable reconciliation of the immutable v0.2.0 source identity, public linux/amd64 OCI digest, provenance, publication-time freshness, runtime verification and bounded delivery-efficiency evidence.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-27T23:53:49Z"
sources:
  - id: v0-2-0-publication-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: v0-2-0-source-release
    resource: https://github.com/ktogias/gnostoa/releases/tag/v0.2.0
    title: Gnostoa v0.2.0
  - id: v0-2-0-publication-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/33124503631
    title: Publish Gnostoa v0.2.0 OCI image
  - id: v0-2-0-provenance
    resource: https://github.com/ktogias/gnostoa/attestations/43531953
    title: Gnostoa v0.2.0 OCI build provenance
x-project-knowledge:
  id: kit.assessment.v0-2-0-source-and-oci-publication-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: references
      target: /assessments/v0-2-0-release-candidate-and-source-boundary-result.md
    - kind: references
      target: /assessments/v0-1-2-source-and-oci-publication-result.md
    - kind: references
      target: /runbooks/publish-version-bound-source-and-oci-release.md
---

# v0.2.0 source and OCI publication result

## Immutable result

| Authority | Exact identity |
|---|---|
| Source release | annotated tag `v0.2.0` |
| Tag object | `6d0357e075744ee316c725554d2e2c920b19a4dc` |
| Source commit | `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` |
| Source tree | `866c8c489c9052c566bd65b6e798567d4a284f16` |
| Source public-surface digest | `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` |
| Published version tag | `ghcr.io/ktogias/gnostoa:0.2.0` |
| Immutable OCI artifact | `ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4` |
| OCI config | `sha256:eb62d68ec4d9298ef204bbb442fee46b7849bba6a2fe2d1e9fe6673d675816b6` |
| Platform | exactly `linux/amd64` |
| Immutable base | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| GitHub Release | `378065344`, prerelease, zero curated assets |

The public-surface digest corroborates a bounded public source projection; it
is not the complete Git source identity. The version tag is a human-facing,
workflow-enforced write-once reference. The registry manifest digest is the
immutable OCI consumer identity. No `latest` or additional image tag exists.
The immutable v0.1.x source and image identities remain historical results.

### Public-surface subject boundary

The immutable v0.2.0 released artifact contains public-surface digest
`sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1`.
Later documentation and verification-control changes on `main` have a distinct
derived current-main public digest. They do not rewrite, replace or re-bind the
tagged v0.2.0 source or the published OCI artifact. The final current-main
digest must be measured from the accepted and integrated tree and recorded in
close-out evidence; this repository record does not predict or embed that
changing digest.

### Executable-subject preservation boundary

The preservation claim is limited to the published OCI runtime and its exact
14-file SB2 executable subject remaining byte-identical. This reconciliation
changes the repository-side executable `ci/verify`; it therefore makes no claim
that every executable file in the repository is unchanged.

## Provider execution and source binding

One manual, input-free workflow dispatch created
[run `33124503631`, attempt 1](https://github.com/ktogias/gnostoa/actions/runs/33124503631)
from workflow source SHA
`b932ed0529087458e6d6406b83b17def23760cb0`. Both `actor` and
`triggering_actor` were `ktogias`. The job checked out annotated tag `v0.2.0`
and asserted the tag object, application commit, tree, version, immutable base
and clean tracked state before building. It then checked tag absence again
immediately before its single push, read the manifest digest back from GHCR,
pulled by that digest and repeated the runtime verification.

The GitHub provenance subject is the exact image name and manifest digest. Its
signer is
`ktogias/gnostoa/.github/workflows/publish-oci.yml@refs/heads/main`; its workflow
and resolved Git dependency identify
`b932ed0529087458e6d6406b83b17def23760cb0`, event `workflow_dispatch`, and
invocation `33124503631/attempts/1`. That is publication-workflow provenance,
not the application-source commit. Application-source binding to `v0.2.0` and
`39aa4f25bdf46811600d4a0f6f9c0da52b73c542` additionally rests on the exact
checkout assertions, source/revision image metadata and digest-pulled runtime,
public-surface, SB2 and notice verification.

[Attestation `43531953`](https://github.com/ktogias/gnostoa/attestations/43531953)
was verified for the immutable subject. The registry-stored attestation object
was
`sha256:8acee8391bf85f86d653b93a54efb4854f3ea4d21d4de722d482c3b04a26c229`;
it is not a substitute for the subject artifact digest.

## Runtime and public read-back

The registry-read-back artifact and a credentials-isolated anonymous digest
pull verified:

- exactly `linux/amd64`, version `0.2.0` and source revision
  `39aa4f25bdf46811600d4a0f6f9c0da52b73c542`;
- CPython 3.12.14 with bundled Expat 2.8.3;
- 118 Debian packages and 8 Python distributions;
- UID/GID 10001, non-root execution, and pip and ensurepip absent;
- no `org.opencontainers.image.licenses` annotation;
- public digest
  `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1`;
- all 14 expected SB2 paths and exact per-file digests, including
  `tools/adoption_check.py` and `tools/adoption_assurance.py`;
- `/opt/gnostoa/THIRD_PARTY_NOTICES` digest
  `sha256:68978e9fc1875f275c0dfb9bd71ed19d025b01f66409bb31d785d86165ee691c`;
  and
- the runtime self-check.

After attestation, `0.2.0` still resolved to the same registry digest and
`latest` remained absent. The dated 2026-08-27 provider read-back found the
package anonymously readable, and anonymous digest pull succeeded. Visibility,
linkage presentation, permissions and access settings remain mutable
provider-authoritative state, not timeless guarantees in this record.

The source Release read-back identified a non-draft prerelease targeting
`39aa4f25bdf46811600d4a0f6f9c0da52b73c542`, with zero curated assets. Release
presentation is mutable provider state; its post-reconciliation body and live
settings must be read from the provider rather than inferred from this source
record.

## Publication-time freshness

The mandatory read immediately before dispatch found no material source/base
preemption. Python 3.12.14 remained the current supported 3.12 security release.
The selected `python:3.12-slim` digest remained retrievable and immutable, and
the exact supported Debian package updates required by the Dockerfile remained
available. The mutable upstream tag had advanced, but it did not change the
selected build subject; the Dockerfile applied the relevant updates explicitly
and failed closed if their exact versions were unavailable. This is the dated
verdict for the 2026-08-27 effect; every future release needs a new freshness
decision.

## Digest-bound release verification

The post-publication reconciliation changes `ci/verify release` from the
historical v0.1.2 digest to the immutable v0.2.0 digest above. It pulls by
digest—not by `0.2.0`—and fails closed on platform, version, source revision,
runtime inventory, public digest, complete 14-file SB2, notices and self-check.
The existing `deployable_artifact=true` capability then denotes verified public
artifact availability for this exact digest only. It does not authorize
deployment or claim production readiness, reproducibility, general security or
qualified legal clearance. v0.1.2 remains a valid historical artifact but is no
longer the current verifier target after this reconciliation is integrated and
read back.

## Bounded process-efficiency result

Publication used one dispatch, one attempt, zero publication failures or
retries, and the workflow completed in 1 minute 6 seconds. The build, push,
digest read-back, digest-pulled verification, provenance and anonymous-access
checks all completed in that single run.

A post-publication review found that GitHub permits a workflow rerun under a
different `triggering_actor` while retaining the original `actor`. PR #149
added exact `GITHUB_RUN_ATTEMPT=1` and triggering-actor guards for future runs.
The completed publication remains bounded to an owner-triggered first attempt:
both identities were `ktogias`, no rerun occurred and exactly one publication
workflow run exists. That corrective current-main control does not rewrite the
published workflow provenance or image subject.

Owner checkpoints remain intentional before integration, immutable source-tag
creation, source Release creation, the write-once OCI dispatch, final
post-publication reconciliation and the later B3 freeze. Those checkpoints
authorize irreversible or public provider effects; their presence is not
evidence for automatic release or a generic publication framework.

## Limits and non-claims

- Exact-digest rebuild repeatability was not tested for v0.2.0 and is not
  claimed. Any rebuild requires a later release identity.
- No `latest`, multi-architecture image, cosign signature, OCI-attached SBOM,
  Python package, documentation-site publication or deployment was selected.
- Artifact availability and digest-bound verification do not establish
  production readiness, deployment authorization, general security, qualified
  legal clearance, compatibility with arbitrary projects or absence of unknown
  defects.
- No population-level release reliability, productivity or adoption claim is
  derived from one successful publication.
- The exact B3 rerun contract has not yet been frozen and the rerun has not
  begun. This source/OCI result is Gnostoa-self delivery evidence, not
  independent-adopter transfer evidence.
