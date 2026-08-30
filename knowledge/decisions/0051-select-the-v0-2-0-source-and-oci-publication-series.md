---
type: Decision
title: Select the v0.2.0 source and OCI publication series
description: Select one immutable v0.2.0 source prerelease, one write-once linux/amd64 OCI artifact and an exact-subject freeze for the Nextcloud Mail B3 rerun.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-27T10:01:02Z"
sources:
  - id: v0-2-0-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: v0-1-2-publication-decision
    resource: 0044-select-the-v0-1-2-source-and-oci-publication-series.md
    title: Select the v0.1.2 source and OCI publication series
  - id: adoption-check-decision
    resource: 0047-select-a-bounded-adoption-completion-check.md
    title: Select a bounded adoption-completion check
  - id: adoption-assurance-decision
    resource: 0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    title: Separate adoption observations from readiness and owner disposition
  - id: v0-2-0-publication-result
    resource: ../assessments/v0-2-0-source-and-oci-publication-result.md
    title: v0.2.0 source and OCI publication result
x-project-knowledge:
  id: kit.decision.0051.select-the-v0-2-0-source-and-oci-publication-series
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0047-select-a-bounded-adoption-completion-check.md
    - kind: governed-by
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /decisions/0044-select-the-v0-1-2-source-and-oci-publication-series.md
    - kind: references
      target: /runbooks/publish-version-bound-source-and-oci-release.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
---

# Select the v0.2.0 source and OCI publication series

## Context

At selection time the current immutable release was `v0.1.2`. It predates the
public `knowledge adoption-check` command and the `gnostoa-adoption-check/v2`
result contract now integrated on protected `main`. Decisions 0047 and 0050
classify that command and result as additive public capabilities that require a
later source/runtime release before general reliance.

The accountable owner selected source publication, OCI publication and a
subsequent exact-subject freeze for the already chosen Nextcloud Mail transfer
experiment. Effective versioning classifies the additive capability as MINOR,
so the next release identity is `v0.2.0`, not a patch rewrite of `v0.1.2`.

Operational work toward B3 has begun in Nextcloud Mail. Four autonomous
adoption attempts are recorded: the baseline attempt and later frozen
fresh-agent rerun under Work Item #117, the route-activation diagnostic under
#122, and the post-remediation rerun under #125. All four ended with owner
acceptance `REJECT`, measured utility `UNKNOWN` and durable adoption `NO`; none
established accepted or durable adoption. Their exact records intentionally
remain classified as controlled pre-B3 evidence because the pre-registration's
strict independent-owner eligibility was not satisfied. That bounded
evidentiary classification does not erase the operational chronology. This
release and freeze prepare a new exact-subject rerun. The `v0.2.0` exact-subject
rerun has not begun.

At selection time protected `main` is
`6714d70772f021bd3e174510f16bcfc5230f168b`, tree
`42d0f1dd323c6ae99c9bbe01f54b346f937ab7a2`. These are the Phase-1 starting
subjects, not the future release identity. Provider-created tag, Release,
workflow and registry identities must be recorded only after they exist.

## Decision

### A. Select one pre-stable minor release

Select `v0.2.0` as the next immutable source and runtime release identity. The
source candidate carries package/runtime version `0.2.0`; it does not rewrite,
move or rebuild any `v0.1.x` identity.

### B. Bind the source to an exact accepted tree

The source subject is the exact tree of the accountable-owner-accepted Phase-1
Pull Request. A squash integration may become the tagged commit only when its
tree is mechanically equal to the accepted tree and protected-main read-back is
clean. No later or approximate revision may be substituted.

Create exactly one annotated tag `v0.2.0` and one non-draft GitHub prerelease
against the already verified tag. The Release contains zero curated assets;
provider-generated source archives remain projections of the tag.

### C. Re-admit the executable source boundary

The new adoption command expands the first-party executable surface beyond the
12-file boundary used by `v0.1.2`. Before source publication, re-derive that
boundary from the unified CLI and transitively used first-party modules,
perform the affected assurance replay and bind one complete candidate manifest.

The proposed boundary adds `tools/adoption_check.py` and
`tools/adoption_assurance.py`, for 14 members. This count becomes accepted only
after focused RED-to-GREEN evidence, exact three-way source/runtime/vendored
equality, complete candidate verification and accountable-owner review. The
result is bounded release evidence, not a claim that the source is generally
secure or that the boundary is permanently complete.

### D. Publish one write-once OCI subject

After the source identity exists, re-bind the existing input-free publication
workflow to the exact source tag object, commit, tree, base, deterministic
public-surface digest, notice digest and admitted 14-member source-boundary
manifest.

Publish only `ghcr.io/ktogias/gnostoa:0.2.0`, exactly `linux/amd64`. Create no
`latest`, additional alias or multi-architecture manifest. The version tag is a
human-facing write-once reference; the registry-read-back manifest digest is
the immutable consumer identity. Any rebuild requires a later release identity.

### E. Preserve freshness and fail-closed publication

Immediately before the source effect and again before OCI dispatch, re-read
protected source, tag/Release/tag-absence state, supported base/runtime status
and the effective release-security boundaries. Ambiguity, an existing target,
material subject drift or a newly blocking condition stops the next effect.

Never auto-retry, delete, overwrite or compensate for an ambiguous immutable
provider effect. Read back authoritative state before any dependent action.

### F. Verify registry identity and provenance

After the single push, read the manifest digest from the registry, pull and
verify by digest, and confirm platform, non-root runtime, version, source
revision, public digest, complete source-boundary manifest, notices and runtime
self-check. Create and verify GitHub build provenance against that registry
digest and confirm anonymous digest access. Push success alone is not release
evidence.

### G. Reconcile only after immutable identities exist

After OCI publication, use one bounded reconciliation slice to bind
`ci/verify release`, public release projections and a durable result assessment
to the registry-read-back digest. Keep the historical `v0.1.2` verifier and
public claims truthful until the new effect has occurred; do not predict a
registry digest into the source candidate.

### H. Freeze the later B3 contract separately

Only after source, OCI, provenance, release verification and integrated/provider
reconciliation agree, freeze the exact subjects for the Nextcloud Mail rerun:

- released Gnostoa documentation/source revision and public-surface digest;
- immutable Gnostoa execution subject;
- target-project repository commit and tree;
- exact experiment prompt, real task, ground-truth matrix and permissions; and
- environment and tool identities.

`ktogias/mail` remains the mutation workspace; upstream `nextcloud/mail`
remains issue, semantic-authority and final Change Request authority. Release
completion does not itself execute B3 or supply upstream maintainer disposition.

### I. Preserve explicit non-claims

The release does not establish production readiness, deployment authority,
general security, legal clearance, exact-digest rebuild reproducibility,
multi-platform support, independent adoption, product-market fit or owner
acceptance of any Nextcloud Mail change. It publishes no package-index artifact
or documentation site and selects no generic release or attestation framework.

### J. Keep effect authority exact

The owner's direction selects the complete release series and admits Phase-1
preparation. Repository preparation and green checks do not by themselves
authorize a moved subject. Each irreversible effect is executed only after
fresh read-back confirms the exact accepted subject, selected metadata,
declared effect envelope and stop conditions in this Decision.

### K. Record the observed source and OCI result

Separate owner-authorized effects created annotated tag `v0.2.0` at tag object
`6d0357e075744ee316c725554d2e2c920b19a4dc`, commit
`39aa4f25bdf46811600d4a0f6f9c0da52b73c542` and tree
`866c8c489c9052c566bd65b6e798567d4a284f16`, then published exactly
`ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`
for `linux/amd64`. Workflow run `33124503631`, attempt 1, read the digest back,
pulled and verified it, created attestation `43531953`, verified provenance and
anonymous access, and left `latest` absent. The durable result and evidence
limits live in the linked v0.2.0 publication assessment.

The publication used workflow source
`b932ed0529087458e6d6406b83b17def23760cb0`. A later bounded correction on
protected `main` added fail-closed first-attempt and triggering-actor guards for
future workflow runs. The completed run itself was already attempt 1 with both
`actor` and `triggering_actor` equal to the accountable owner; no rerun or
republish occurred.

### L. Transition the current release verifier

Bind `ci/verify release` to the immutable v0.2.0 registry digest, never the
version tag. Preserve fail-closed platform, version, source-revision,
runtime-inventory, public-digest, complete 14-file SB2, notice and self-check
controls. `deployable_artifact=true` means verified public artifact availability
for that exact digest only; it does not mean deployment authorization,
production readiness, reproducibility, general security or qualified legal
clearance. v0.1.2 remains an immutable historical artifact but ceases to be the
current verifier target once this reconciliation is integrated and read back.

### M. Reconcile the result authority and public projection

Preserve one authoritative v0.2.0 result assessment and route current public
status to the immutable digest. Do not freeze mutable package permissions,
visibility, linkage or Release presentation as timeless source truth. Do not
claim exact-digest rebuild repeatability: it was not tested, is not required for
this release and any rebuild requires a later release identity. Keep the exact
B3 freeze separate until this reconciliation is integrated and provider-read
back; release reconciliation itself is not transfer evidence.

## Consequences

- `v0.2.0` is now an immutable source identity and one public write-once
  `linux/amd64` OCI digest; final repository reconciliation remains subject to
  exact-candidate owner acceptance and integrated/provider read-back.
- General B3 reliance can use that immutable released v2-capable subject after
  the separate exact-subject contract is frozen.
- The source, workflow and registry identities remain distinct and are created
  in that order.
- The new executable paths enter the bounded release review surface rather than
  inheriting the historical 12-file manifest silently.
- Work Item #146 remains open through digest-bound reconciliation and the
  separate B3 freeze; the exact-subject rerun has not begun.

## Later staged-evidence amendment

[Decision 0052](0052-use-staged-evidence-maturity-for-early-adoption-trials.md)
later established a general staged-evidence policy for Gnostoa's early product
phase. It partially supersedes this Decision only where sections H and M and the
final consequence above make a strict `INDEPENDENT` B3 contract a prerequisite
for completion of the v0.2.0 release Work Item.

For that release series, an integrated and provider-read-back `OWNER-LED`
baseline now satisfies the experiment-boundary requirement. The task run,
initial assessment, retrospective, later upstream feedback and any future
`COLLABORATIVE` or `INDEPENDENT` evidence are separate work and are not release
completion gates.

This amendment does not change the source, tag, Release, OCI, provenance,
verification, reconciliation, effect-authority or non-claim rules recorded
above. Where the earlier B3-dependent completion language conflicts with this
amendment, Decision 0052 and this section govern.
