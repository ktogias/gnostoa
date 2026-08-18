---
type: Source
title: First source-only release result
description: Durable result of the authorized v0.1.0 source-only provider effect, with the coupled-effect evidence observed during Work Item 43.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T09:40:00Z"
sources:
  - id: release-identity-work-item
    resource: https://github.com/ktogias/gnostoa/issues/43
    title: Establish the first immutable source-only release identity
x-project-knowledge:
  id: kit.assessment.first-source-only-release-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
    - kind: derived-from
      target: /assessments/first-source-only-release-pre-effect-state.md
---

# First source-only release result

Decision 0020 was executed through the authorized source-only provider effect.
The pre-effect record is preserved unchanged as historical evidence; this record
is additive.

## Durable outcome

| | |
|---|---|
| Release identity | `v0.1.0` |
| Tag type | annotated Git tag object |
| Names exactly | `ee808572d3930ec3dc50d350ae1ed25a0236bb6b` |
| Public-surface digest | `sha256:021f18107feb93be2d4c6e5d8dca7d73bf2247871fc100859ba576089f55772b` |
| Kind | source-only, pre-stable |

The tag was created annotated and pushed first; the GitHub Release was created
afterwards against the **existing** tag with `--verify-tag`, so the provider
could not silently create or move a tag. Mutable Release metadata remains
provider-authoritative and is deliberately not restated here.

**Not established by this release:** package, OCI-image or documentation-site
publication, which remain separate unperformed effects; installability;
cross-version compatibility; migration; support lifetime; LTS; production
readiness; independent assurance; easy adoption; signing, attestation or
provenance. B3 independent transfer remains deferred. No successor workflow,
control or capability was selected, and `deployable_artifact` remains `false`.

A version label alone remains insufficient identity: exact source revision plus
deterministic public-surface digest are still required.

## Coupled-effect evidence

Two concrete observations from this Work Item. Both are **evidence**, not a
selected mechanism.

### 1. Auto-close keyword in a Change Request body (unexpected at the time)

During preparation, the body of [PR #44](https://github.com/ktogias/gnostoa/pull/44)
contained `Closes #43`. When that Change Request merged, GitHub automatically
closed Work Item #43. The closure was not independently intended: the release
effect and its reconciliation were still incomplete, so the Work Item had to be
reopened.

The durable finding:

> **The provider mutation surface is not the same as the single command or API
> action that initiated it.**

For provider mutations, bounded reconciliation must consider known or observed
coupled effects, not only the explicitly requested write. This slice therefore
used `Refs #43` rather than an auto-closing keyword, and closed the Work Item
explicitly after reconciliation.

This is not generalized beyond the evidence. It is **not** a claim that every
provider action has unknown side effects, and **no** generic effect mediator,
provider adapter, routing mechanism or workflow engine is selected as a result.

### 2. Tag push triggering the existing verification workflow (expected)

Pushing `refs/tags/v0.1.0` created a workflow run, because the existing
verification workflow has an unfiltered `push` trigger.

| | |
|---|---|
| Intended mutation | push one annotated tag |
| Expected coupled effect | one provider workflow run for the tag ref |
| Run conclusion | `success` |
| Jobs that ran | `policy`, `fast` |
| Jobs skipped | `regression`, `extended`, `smoke` |

This is expected and read-only, so it is not a defect. It is recorded exactly:
**the run concluded `success` while three of five jobs were skipped**, which is
the documented behaviour of the provider mechanism rather than evidence that
those suites passed on the tag ref. The release gate remains the accepted
exact-candidate verification, which was run in-container on
`ee808572d3930ec3dc50d350ae1ed25a0236bb6b` before the effect. This run is not
promoted to release evidence.

## Verification limit

User-level container-package listing could not be read with the available token
scope (`403`, `read:packages` absent). No publication action was taken, only the
verification workflow exists, the repository package listing returns Not Found
and the PyPI project name returns HTTP 404. The limit is recorded rather than
reported as a completed check.
