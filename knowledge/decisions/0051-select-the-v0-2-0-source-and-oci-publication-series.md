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
---

# Select the v0.2.0 source and OCI publication series

## Context

The current immutable release is `v0.1.2`. It predates the public
`knowledge adoption-check` command and the `gnostoa-adoption-check/v2` result
contract now integrated on protected `main`. Decisions 0047 and 0050 classify
that command and result as additive public capabilities that require a later
source/runtime release before general reliance.

The accountable owner selected source publication, OCI publication and a
subsequent exact-subject freeze for the already chosen Nextcloud Mail transfer
experiment. Effective versioning classifies the additive capability as MINOR,
so the next release identity is `v0.2.0`, not a patch rewrite of `v0.1.2`.

Operational B3 work already began in Nextcloud Mail through the attempts
recorded under Work Items #117, #122 and #125. Those attempts were rejected
without passing the initial-adoption gate and produced no final utility or
durable-adoption result. Their exact records intentionally remain classified as
controlled pre-B3 evidence because the pre-registration's strict
independent-owner eligibility was not satisfied. That bounded evidentiary
classification does not erase the operational chronology. This release and
freeze prepare a new exact-subject rerun; that rerun has not begun.

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

## Consequences

- General B3 reliance can use an immutable released v2-capable subject instead
  of a development-branch candidate.
- The source, workflow and registry identities remain distinct and are created
  in that order.
- The new executable paths enter the bounded release review surface rather than
  inheriting the historical 12-file manifest silently.
- Publication remains a multi-phase Work Item and closes only after immutable
  read-back, digest-bound reconciliation and the separate B3 freeze.
