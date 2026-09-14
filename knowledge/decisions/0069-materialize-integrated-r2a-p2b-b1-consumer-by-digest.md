---
type: Decision
title: Materialize the integrated R2A P2b-B1 outer consumer as a prior-effective digest-only OCI identity
description: Materialize exact integrated P2b-B1 as a one-shot digest-only OCI outer-consumer identity before any P2b-B2 activation.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-14T11:36:00Z"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: bootstrap-pattern
    resource: ./0068-materialize-r2a-p2a-as-a-one-shot-digest-only-oci-judge.md
    title: Decision 0068
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: b1-integration
    resource: https://github.com/ktogias/gnostoa/pull/248
    title: Integrated dormant P2b-B1 outer consumer
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5663169718
    title: Owner authorization for intermediate B1 materialization and B2 convergence steps
  - id: prewrite-failure-reconciliation
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5663773822
    title: Pre-write B1 materialization failure and bounded repair record
x-project-knowledge:
  id: kit.decision.0069.materialize-integrated-r2a-p2b-b1-consumer-by-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0068-materialize-r2a-p2a-as-a-one-shot-digest-only-oci-judge.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Materialize the integrated R2A P2b-B1 outer consumer as a prior-effective digest-only OCI identity

## Context

Decision 0067 requires current-advisory trust to come from previously accepted evidence rather than candidate-controlled bytes. Decision 0068 established the first rolling bootstrap step by materializing exact integrated P2a as a one-shot, digest-only OCI judge.

PR #248 has now integrated the dormant P2b-B1 outer current-advisory consumer into protected `main` at exact source revision `0dfd7e5e28e8ccb87e687e0be9dfe846b644c9c3` and tree `23a5f083f26f40a8287bc2a724bcd5282a9afa5e`. The B1 CLI remains dormant by design. Issue #11 comment `5661521818` records the anti-self-reference refinement: before P2b-B2 may activate the protected route, the outer consumer itself must become independently selected and prior-effective.

The owner authorized the complete intermediate transition through B1 materialization, protected authority update, and B2 convergence in issue #11 comment `5663169718`. The final B2 activation merge remains separately owner-gated.

## Decision

Reuse the Decision 0068 rolling prior-integrated OCI pattern for the exact integrated B1 outer consumer.

After the observed pre-write failure described below, the dedicated protected-main workflow SHALL:

1. admit only the verification-first repair `push` whose protected-main predecessor is `8d1ac1812509a2f6beb220b4989ec9b472ff441b`, while the materialized B1 source remains exact commit `0dfd7e5e28e8ccb87e687e0be9dfe846b644c9c3` and tree `23a5f083f26f40a8287bc2a724bcd5282a9afa5e`;
2. refuse manual dispatch, retries and any context whose `event.before`, actor, branch, repository, run attempt, workflow identity, source commit or source tree differs from the selected repair transition;
3. check out the exact integrated B1 source separately, build that exact runtime locally, and derive its public-surface digest from the containerized exact source before any registry authentication or write;
4. verify that exact runtime locally before authentication, including non-root identity, OCI source labels, public-surface digest, candidate source manifest, the protected acquisition module, the dormant outer consumer (`tools/review_live.py`), the protected Docker runner (`tools/review_current.py`), and `knowledge self-check`;
5. perform one digest-only GHCR publication using the existing hardened `ci/build-runtime --push-by-digest` path, creating no remote tag;
6. obtain the authoritative registry manifest digest from bounded BuildKit metadata and reacquire the image by that digest;
7. verify the exact source revision and public-surface digest from the reacquired runtime;
8. attest that exact registry manifest, verify the attestation, log out, and prove anonymous digest reacquisition with the same runtime checks; and
9. emit a bounded receipt carrying the source commit, source tree, derived public-surface digest, OCI digest and workflow-run identity.

The resulting `ghcr.io/ktogias/gnostoa@sha256:...` reference is the immutable B1 outer-consumer identity eligible for a subsequent protected authority update. Materialization alone does not activate P2b-B2 and does not establish semantic PASS or reviewer qualification.

## Observed pre-write failure and bounded repair

The first protected-main materialization attempt ran as workflow `34842626132` after publisher commit `8d1ac1812509a2f6beb220b4989ec9b472ff441b`. Its authorization job succeeded, but the publish job failed while deriving source metadata because the bare checkout executed `python -m tools.cli surface-digest --root .` without the runtime dependency `referencing` installed.

That failure occurred **before GHCR authentication**, local publication, registry push, attestation, or any other registry effect; every write-capable step was skipped. Issue #11 comment `5663773822` records the exact failure and effect boundary. Therefore this is the pre-write repair case allowed by this decision, not a post-write ambiguity and not permission to rerun workflow `34842626132`.

The repair keeps the exact B1 source commit and tree unchanged. It changes only the selected protected-main transition and moves public-surface digest derivation into the exact locally built B1 container, matching the established container-first P2a pattern. The repair workflow remains run-attempt-one only and remains incapable of manual dispatch.

## Failure and rerun rule

There is **no blind rerun** after a workflow attempt reaches the registry write boundary. A failure before the write effect may be repaired through a new verification-first change. An ambiguous or post-write failure must first reconcile read-only GHCR and attestation state against the exact source revision, source tree and derived public-surface digest. Existing matching immutable state is evidence to be retained, not permission to publish again.

## Relationship to P2b-B2

The intended trust chain is:

`OCI(P2a) -> B1 candidate -> protected B1 integration -> OCI(B1) -> protected consumer-authority update -> P2b-B2 candidate`.

P2b-B2 may consume only the independently materialized, protected-authority-bound B1 outer consumer. Candidate B2 bytes remain untrusted input/transport and must not become the provenance source for the final current-advisory result.

After final P2b integration, the rolling invariant still requires materializing/promoting OCI(P2b) for the next transition.

## Consequences

- The exact integrated B1 outer consumer can obtain a durable, independently reacquirable identity without making candidate bytes authoritative.
- The protected authority update for B2 can bind a digest-only OCI identity and exact public-surface digest rather than a mutable tag or branch state.
- The materialization workflow is intentionally single-use and fail-closed; ambiguous post-write failures require read-only reconciliation instead of a blind retry.
- The failed first materialization attempt is retained as evidence and cannot be converted into retry authority; only the separately verified pre-write repair transition is admitted.
- P2b-B2 remains blocked until the resulting B1 identity is recorded through a separately protected, prior-effective authority update.
- The truthful empty #10 qualification state is unchanged, so this transition does not manufacture semantic PASS or qualified independence.

## Non-goals

This is not a release. It creates no mutable tag, release object, deployment, package version, #15 workflow effect, qualified reviewer domain, semantic PASS, or B2 activation. It does not weaken the truthful empty #10 qualification state; `INCOMPLETE / QUORUM_UNMET` and `binding:false` remain legitimate outcomes.
