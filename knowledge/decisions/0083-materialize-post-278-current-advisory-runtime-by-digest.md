---
type: Decision
title: Materialize the integrated post-#278 current-advisory runtime as a digest-only OCI identity
description: Materialize the exact integrated #278 source as a new immutable outer-consumer runtime, verify the repaired protected transport through the real runtime layers, and stop before protected-authority promotion.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-19T07:28:00Z"
sources:
  - id: restoration-work-item
    resource: https://github.com/ktogias/gnostoa/issues/275
    title: Eliminate protected review payload persistence and gate secret regressions
  - id: restoration-checklist
    resource: https://github.com/ktogias/gnostoa/issues/275#issuecomment-5734815516
    title: Required follow-through R1-R7
  - id: r1-r2-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/275#issuecomment-5740262089
    title: R1 complete; R2 admitted preparation and RED
  - id: transport-containment
    resource: ./0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    title: Decision 0082
  - id: prior-materialization-pattern
    resource: ./0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    title: Decision 0078
  - id: integrated-source
    resource: https://github.com/ktogias/gnostoa/commit/315487e7a67635ebf3ec3f70f666ef41646102e1
    title: Integrated #278 source
x-project-knowledge:
  id: kit.decision.0083.materialize-post-278-current-advisory-runtime-by-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    - kind: governed-by
      target: /decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    - kind: implements
      target: /decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
---

# Materialize the integrated post-#278 current-advisory runtime as a digest-only OCI identity

## Context

PR #278 integrated the protected-review transport remediation on protected
`main` as exact source commit
`315487e7a67635ebf3ec3f70f666ef41646102e1` and exact source tree
`ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`.

Default-branch verification on that integrated subject completed successfully for
`policy`, `security-fast`, `fast`, `extended-route`, `extended`,
Python 3.11/3.12 compatibility, `regression`, `smoke`, and GitHub CodeQL's
Python/actions analyses. Decision 0082 nevertheless leaves
`current_advisory` deliberately unavailable because the protected
outer-consumer authority still selects the historical immutable OCI(P2b)
runtime built from source
`2aa1ed3217c42819155b8ff36385b000720ba4f8`. That artifact predates the
host-persistence repair and cannot be changed retroactively.

The historical one-shot P2b materializer is intentionally unusable for the new
integrated source. On the #278 protected-main push, its exact authorization fence
failed and the package-writing job was skipped. Re-running or weakening that
historical fence would violate the one-shot effect boundary.

The owner instructed that restoration continue after #278 until a real human
intervention is required. Issue #275 comment `5740262089` therefore admits
preparation and verification of the smallest R2 materialization slice. It does
not grant blanket authority for an irreversible registry write, protected
authority promotion, provider-setting mutation, or alert dismissal before the
exact effect and candidate are known.

## Prior-art and reuse disposition

Reuse Decision 0078's existing one-shot materialization pattern:

- exact predecessor/source/tree and merged-PR binding;
- independent `GITHUB_RUN_ATTEMPT == 1` fences in authorization and
  effect-capable jobs;
- existing `ci/build-runtime` with deterministic source metadata;
- local non-root/runtime/self-check verification before registry authentication;
- digest-only GHCR publication with no mutable tag;
- exact manifest read-back, attestation, authenticated-state removal,
  anonymous reacquisition and repeated source/public-surface/runtime proof; and
- read-only post-write reconciliation with no blind retry after an ambiguous
  registry effect.

Do not generalize the old workflow into a caller-parameterized release engine,
reuse an old immutable digest, mutate historical authority records, or make
candidate code a protected runtime selector.

The residual custom need is bounded: bind the new integrated source identity and
add a restoration-specific smoke that can prove the newly immutable digest
executes the repaired outer and inner transport layers under a **test-local exact
compatibility admission**, while leaving the production compatibility catalog
and protected authority unchanged.

No new external dependency, copied implementation, licence, attribution or
NOTICE obligation is introduced.

## Decision

Prepare one dedicated, one-shot protected-main materializer for exact source
commit `315487e7a67635ebf3ec3f70f666ef41646102e1` and tree
`ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`.

The candidate SHALL:

1. bind the eventual materializer landing to one exact PR number, branch and
   predecessor `315487e7a67635ebf3ec3f70f666ef41646102e1`;
2. refuse every event other than the first protected-main push of that admitted
   landing and independently fence the package-writing job against reruns;
3. check out the exact integrated source separately and verify source commit,
   source tree, version and clean tree before authentication;
4. build the exact source and prove Linux/amd64, non-root uid/gid 10001,
   OCI revision metadata, deterministic public-surface digest and runtime
   `self-check` before any registry effect;
5. prove the integrated runtime contains the #278 transport implementation and
   its protected-review entrypoints;
6. if and only if the later exact-effect authorization permits publication,
   publish by immutable manifest digest with no mutable remote tag, read back the
   digest, attest it, remove authenticated local state, anonymously reacquire the
   exact digest and repeat the runtime/source/public-surface proofs;
7. after a digest exists, execute a restoration-specific full-path smoke against
   that exact immutable image. The smoke may inject the exact candidate consumer
   identity and compatibility admission **only inside the smoke process**; it
   must use the real outer isolation/nested-daemon path and must not mutate the
   protected authority document or production compatibility catalog;
8. require that the full-path smoke reaches a genuine advisory evaluation result
   such as `INCOMPLETE / QUORUM_UNMET`, rather than
   `TOOL_ERROR`, `UNAVAILABLE` or `NOT_RUN`, while retaining non-binding
   semantics and protected inner authority;
9. reconcile the exact digest and attestation after the write; if publication
   state is ambiguous and no exact digest can be established, fail closed and
   create no rerun authority; and
10. emit a bounded receipt carrying source commit, source tree,
    public-surface digest, OCI digest, workflow run and the restoration-smoke
    result.

## Effect boundary

This Decision prepares and verifies the exact R2 candidate. **The registry write
remains a separate exact effect.** Merging a workflow that automatically performs
that write is itself part of the publication effect and must not occur until the
owner has been shown the exact candidate/effect and has authorized it.

Successful materialization does not restore `current_advisory`. It creates an
eligible immutable identity for the separate R4 trust/compatibility promotion.
The protected consumer authority and production
`_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES` remain unchanged by R2/R3.

## Verification contract

Before the effect-authorizing merge:

- repository policy/style/type and focused workflow-contract tests pass;
- the one-shot workflow's exact source, predecessor, PR/head-ref and
  attempt-1 fences are mechanically asserted;
- the protected R2A workflow routes changes to the new materializer,
  Decision, smoke and contracts;
- the restoration smoke has negative/structural tests proving it cannot accept a
  malformed, mismatched or non-digest consumer identity and that its test-local
  admission does not alter production state; and
- independent review reconciles the exact candidate against this Decision and
  #275 R2/R3 boundaries.

After an authorized registry effect, provider evidence must additionally show
the exact digest, attestation, anonymous reacquisition and full-path restoration
smoke. Only then may R2/R3 be marked complete and R4 prepared.

## Non-goals

This slice does not:

- update `tasks/issue-11-r2a-current-advisory-consumer.json`;
- populate the production compatibility catalog;
- restore the public route by itself;
- modify the closed inner semantic authority;
- create a mutable OCI tag, Git tag, GitHub Release, deployment or version bump;
- mutate branch protection, required checks or CodeQL alert state; or
- close #275.

#275 remains open through actual public-route restoration and provider-security
read-back.
