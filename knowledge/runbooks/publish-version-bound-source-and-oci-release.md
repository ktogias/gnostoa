---
type: Runbook
title: Publish a version-bound source and OCI release
description: Coordinate one Gnostoa-self source identity and write-once OCI publication series while keeping identities, effect authority and reconciliation distinct.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-24T22:58:43Z"
sources:
  - id: version-bound-release-route-work-item
    resource: https://github.com/ktogias/gnostoa/issues/115
    title: Canonicalize the version-bound source and OCI release route
  - id: v0-1-2-publication-result
    resource: ../assessments/v0-1-2-source-and-oci-publication-result.md
    title: v0.1.2 source and OCI publication result
  - id: v0-1-2-publication-work-item
    resource: https://github.com/ktogias/gnostoa/issues/111
    title: Publish Gnostoa v0.1.2 source and OCI release series
x-project-knowledge:
  id: kit.runbook.publish-version-bound-source-and-oci-release
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0044-select-the-v0-1-2-source-and-oci-publication-series.md
    - kind: depends-on
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: depends-on
      target: /runbooks/publish-source-only-release.md
    - kind: references
      target: /assessments/v0-1-2-source-and-oci-publication-result.md
---

# Publish a version-bound source and OCI release

## Scope and authority

Use this runbook only for a Gnostoa-self release series that combines an
immutable source release with one owner-selected, write-once OCI publication.
It coordinates existing authorities; it does not replace the
[ordinary delivery route](deliver-bounded-self-hosted-slice.md), the
[source-only release procedure](publish-source-only-release.md), or the
candidate-specific owner Decision.

Authority remains separated:

- the Decision selects the release subject, boundaries and authorized effects;
- this runbook supplies the reusable ordering and reconciliation procedure;
- the result assessment records measured immutable results and limitations;
- provider records remain authoritative for run identities and mutable provider
  state.

## Preconditions

- An accountable owner has selected the exact release subject, boundaries and
  authorized effects in a candidate-specific Decision.
- One Work Item owns the complete source-and-OCI series and remains open through
  post-publication reconciliation.
- The ordinary repository candidate, source-release route and version-bound OCI
  mechanism are available without inventing a new release system.
- Mutable source, upstream and provider state can be read immediately before
  each authorized effect; ambiguity stops the effect.

## Procedure

### Ordinary sequence

1. **Admit the source and create its immutable identity.** Follow the
   [ordinary delivery route](deliver-bounded-self-hosted-slice.md) for the
   repository candidate and the
   [source-only release procedure](publish-source-only-release.md) for the
   annotated tag and source Release. Obtain accountable-owner authorization
   before each irreversible source-provider effect.
2. **Prepare the version-bound OCI publication.** Bind the selected version,
   source tag and tree, image, platform, base and verification subjects in one
   clearly named constant block. Keep exact-candidate checks generic: compare
   the current complete subjects rather than asserting one historical release
   delta. Batch semantic review before requesting exact-head provider evidence.
3. **Dispatch only with accountable-owner effect authority.** Re-read mutable
   freshness, provider and tag-absence state immediately before the authorized
   input-free dispatch. A preparation merge does not authorize publication.
4. **Read back the registry and provenance effects.** Treat push success as an
   intermediate observation. Read the manifest digest from the registry, pull
   by digest, verify the published subject, verify provenance against that
   digest and read back public access and the human-facing Release.
5. **Reconcile by immutable digest.** In one post-publication slice, bind release
   verification and current public projections to the registry-read-back
   digest. Integrate, read back provider state and measure the resulting current
   main. Preserve one result assessment rather than one record per observation.
6. **Close last.** Keep the release Work Item open until source, registry,
   provenance, Release, integrated-main and digest-bound verification evidence
   agree. Then reconcile once and close it before selecting the next owner
   subject.

Future prompts should reference this runbook and carry only the exact
task-specific subject, owner choices, exclusions, stop conditions, authorized
effects and required result evidence.

### Keep identities distinct

Never substitute one of these subjects for another:

| Subject | Authority |
|---|---|
| Application source tag, commit and tree | Git tag and dereference read-back |
| Publication-workflow SHA | Provider execution provenance |
| OCI manifest digest | Registry read-back; immutable consumer identity |
| Final post-publication main | Integrated repository read-back |
| Released-artifact public digest | Verification of the digest-pulled artifact |
| Later current-main derived digest | Measurement of that later exact tree |

The workflow SHA identifies the publication execution, not the application
source. The registry digest does not exist before the push and must never be
predicted. A later current-main digest is measured only after the corresponding
tree exists; do not embed that transient value in authored public-surface
knowledge. Record final derived measurements in the result assessment or
close-out evidence.

### Efficiency without weaker assurance

- Centralize version-bound constants while retaining exact, input-free owner
  authorization for the selected release.
- Bind the complete current candidate generically; remove release-history,
  changed-path and incident-specific assertions from permanent verification.
- Batch semantic review before the provider run so wording corrections do not
  create avoidable exact-head replacement runs.
- Consolidate post-effect evidence once instead of opening one reconciliation
  for every observation.
- Retain manual authorization before immutable tags and registry writes.

## Verification

- Bind repository and provider checks to each exact candidate and inspect the
  intended jobs individually; `SKIPPED` is not `PASS`.
- Before an irreversible effect, repeat only the freshness and provider reads
  whose authorities can have changed since preparation.
- After source publication, dereference the annotated tag and read back the
  source Release. After OCI publication, read the registry digest, pull and
  verify by digest, and verify the provenance subject.
- After reconciliation, require exact integrated-tree and provider read-back,
  digest-bound release verification, and truthful public projections before
  closing the Work Item.

## Recovery

If a publication partly succeeds or its state is ambiguous, preserve the
observed state and read the provider before acting. Never auto-retry, delete or
overwrite the version. Any rebuild requires a separately admitted later
identity; a failed reconciliation leaves the Work Item open.

## Non-goals

This procedure creates no generic release engine, arbitrary version input,
mutable `latest` tag, generator, new DSL or raw prompt transcript. It does not
require every future release to reproduce the exact path observed for v0.1.2.
Candidate-specific Decisions and evidence continue to select the smallest
applicable sequence and controls.
