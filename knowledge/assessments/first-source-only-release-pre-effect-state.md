---
type: Source
title: First source-only release pre-effect state
description: Falsifiable record of the provider and repository state before the v0.1.0 source-only release effect, and the verification contract the release candidate must satisfy.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-18T15:15:00Z"
sources:
  - id: release-identity-work-item
    resource: https://github.com/ktogias/gnostoa/issues/43
    title: Establish the first immutable source-only release identity
x-project-knowledge:
  id: kit.assessment.first-source-only-release-pre-effect-state
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# First source-only release pre-effect state

## Evidence form

The `v0.1.0` release is a **non-executable provider effect**. Under
`guidance/workflows/develop-verification-first.md`, pre-change evidence for
non-executable work is "an unmet structural criterion plus planned human
review", and evidence is to be mapped through CI policy "rather than embedding
provider events in test commands".

The unmet structural criterion is recorded below. The planned human review is the
explicit owner authorization gate that must precede the effect. No executable
test was manufactured for the provider event.

## Unmet structural criterion, observed before any preparation mutation

Observed on protected main `85766e8df2add27dc2234792547e6ce078228d04`:

| Observation | Value |
|---|---|
| Local tags matching `v0.1.0` | 0 |
| Remote tags matching `refs/tags/v0.1.0` | 0 |
| Remote tags of any name | 0 |
| GitHub Releases | 0 |
| `gh release view v0.1.0` | `release not found` |
| `docs/status.md` states no release/package/image/site | present |
| `docs/compatibility.md` states none released | present |
| `policy/verification.yaml` `deployable_artifact` | `false` |

**The selected source-only release effect has therefore not occurred.** This is
the falsifiable pre-effect state; if any row above were already satisfied, the
effect would be redundant or already partly performed.

## Expected post-effect state

Recorded as the criterion the later effect must satisfy, not as a prediction that
it will occur:

- exactly one annotated `v0.1.0` tag exists;
- it resolves to the exact owner-authorized protected-main candidate;
- exactly one GitHub Release uses that tag;
- release notes identify the exact source revision and public-surface digest;
- no curated wheel, source distribution, image or site artifact is attached or
  claimed;
- provider read-back matches the authorized effect exactly.

## Release-candidate verification contract

The release candidate is **the exact protected-main commit after the preparation
Change Request integrates**, not the research base. Before any provider effect
that exact candidate must show:

`policy` PASS, `fast` PASS, `regression` PASS, `smoke` PASS, `extended` PASS,
runtime `self-check` PASS, a clean repository state, and a recomputed and
recorded deterministic public-surface digest.

## Bounds on what is claimed

The package release smoke is **not** claimed to pass end-to-end; an attempted run
did not complete, and `ci/release_smoke.py` is not wired into any `ci/verify`
route. It is not a requirement of this source-only effect, which publishes no
package artifact.

No signing, attestation or provenance guarantee is claimed. `deployable_artifact`
remains `false` and delivery policy remains inactive.
