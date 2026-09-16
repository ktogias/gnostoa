---
type: Decision
title: Promote the protected R2A outer-consumer authority from OCI(B1.6) to OCI(P2b)
description: Bind the independently materialized integrated P2b runtime as the protected prior-effective outer consumer before the final subsequent-candidate negative read-back.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-09-16T19:44:32Z"
sources:
  - id: outer-authority-separation
    resource: ./0070-protect-r2a-b1-outer-consumer-authority-separately.md
    title: Decision 0070
  - id: b16-authority-promotion
    resource: ./0076-promote-r2a-b16-outer-consumer-authority.md
    title: Decision 0076
  - id: b2-activation
    resource: ./0077-activate-r2a-p2b-b2-through-prior-effective-b16.md
    title: Decision 0077
  - id: p2b-materialization
    resource: ./0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    title: Decision 0078
  - id: p2b-materialization-receipt
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5703489461
    title: Successful immutable OCI(P2b) materialization receipt
  - id: rolling-trust-exit
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5680382022
    title: P2b rolling-trust exit boundary
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
x-project-knowledge:
  id: kit.decision.0079.promote-r2a-p2b-outer-consumer-authority
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0070-protect-r2a-b1-outer-consumer-authority-separately.md
    - kind: governed-by
      target: /decisions/0076-promote-r2a-b16-outer-consumer-authority.md
    - kind: governed-by
      target: /decisions/0077-activate-r2a-p2b-b2-through-prior-effective-b16.md
    - kind: governed-by
      target: /decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Promote the protected R2A outer-consumer authority from OCI(B1.6) to OCI(P2b)

## Context

Decision 0070 keeps the protected **outer consumer** authority separate from the
closed v1 **inner semantic authority**. Decision 0076 promoted OCI(B1.6) as the
prior-effective outer consumer. Decision 0077 then activated P2b-B2 through that
already protected runtime, so candidate-controlled bytes supplied only bounded
transport and orchestration rather than the final current-advisory provenance.

PR #265 integrated P2b-B2 on protected `main` as exact source commit
`2aa1ed3217c42819155b8ff36385b000720ba4f8`, tree
`4cda4e4a704cb518f56201423e313d4dd9db5e24`. Decision 0078 subsequently
authorized one immutable post-B2 materialization of that exact integrated P2b
source. PR #267 landed the materializer on protected `main` at
`8feeb816d01ebda267e79ef57d5da7c0ccf61207`.

The one-shot workflow completed successfully as run `35136892751`, attempt `1`.
It independently fenced the effect-capable job, verified the exact source and
tree, built and self-checked the runtime before authentication, published by
digest without a mutable tag, read the manifest back, attested it, reacquired it
anonymously under fresh Docker state, repeated source/public-surface/runtime
proofs and completed final fail-closed reconciliation and cleanup.

The accepted public-surface digest is
`sha256:b69f11e1efe181f959a14310fed0a35d3533114d734de584790a85cba7bdb565`.
The independently reacquirable integrated P2b runtime is exactly:

`ghcr.io/ktogias/gnostoa@sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281`

GitHub attestation `47999464`, Rekor transparency-log index `2866053656` and
the registry attestation artifact are durably reconciled in issue #11 comment
`5703489461`. No rerun, mutable OCI tag, Git tag, release or deployment was
created.

The protected outer-consumer authority still selects OCI(B1.6). That identity
was the correct prior-effective runtime for evaluating the P2b-B2 candidate,
but retaining it after independent OCI(P2b) materialization leaves the rolling
trust exit incomplete. A subsequent candidate cannot prove that it resolves
the new prior-effective P2b runtime until the protected authority moves first.

## Prior-art and reuse disposition

The bounded need and implementation shape already exist locally in Decisions
0070, 0073 and 0076 and in the integrated PR #260 authority promotion. Reuse the
same closed authority schema, dedicated R2A exact-head workflow, focused
contract and semantic guardrail. No external service, dependency, library or
copied material is needed; no new licence, attribution, distribution or NOTICE
obligation is introduced. The only residual custom work is the project-specific
immutable identity/provenance update and its structural verification.

Republishing OCI(P2b) is unnecessary and violates the one-shot boundary.
Changing the closed inner semantic authority would cross the wrong trust domain.
Combining promotion with the subsequent negative read-back would collapse the
prior-effective integration step into the later candidate observation that must
consume it.

## Decision

Promote only the protected outer-consumer authority from exact OCI(B1.6) to
exact OCI(P2b).

1. Keep `tasks/issue-11-r2a-current-advisory.json` unchanged as the closed v1
   **inner semantic authority**. Its OCI(P2a) judge, policy and qualification
   snapshot remain separate from the outer consumer.
2. Update `tasks/issue-11-r2a-current-advisory-consumer.json` so both
   `expected_consumer` and `acquired_consumer` bind source revision
   `2aa1ed3217c42819155b8ff36385b000720ba4f8`, source tree
   `4cda4e4a704cb518f56201423e313d4dd9db5e24`, public-surface digest
   `sha256:b69f11e1efe181f959a14310fed0a35d3533114d734de584790a85cba7bdb565`,
   runtime revision `2aa1ed3217c42819155b8ff36385b000720ba4f8`, and OCI identity
   `ghcr.io/ktogias/gnostoa@sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281`.
3. Bind the authority record's materialization provenance to protected-main
   revision `8feeb816d01ebda267e79ef57d5da7c0ccf61207`, workflow run
   `35136892751`, GitHub attestation `47999464`, Rekor index `2866053656`, and
   materialization receipt `5703489461`.
4. Preserve the existing closed outer-consumer authority schema. This
   transition changes the selected immutable identity, not the authority shape
   or the closed v1 inner semantic contract.
5. Keep the dedicated R2A exact-head workflow and the
   `semantic-review-assurance` guardrail responsible for the protected record,
   this Decision and the focused authority contract. This authority-promotion
   slice performs no OCI publication or other registry write.
6. Treat `knowledge/index.md` as **navigation-only** discoverability and
   **index-only** projection. It remains outside the protected semantic
   authority and outside the dedicated R2A path filter; general knowledge
   validation owns index integrity.
7. Once this authority update is integrated into protected `main`, OCI(P2b)
   becomes the prior-effective protected outer consumer for the next candidate.
8. Keep the P2b rolling-trust exit open until a **subsequent candidate** performs
   a separate read-back/negative check proving that it resolves this exact
   protected OCI(P2b) identity and refuses candidate-controlled runtime and
   stale B1.x authority.

This Decision does **not** claim that the subsequent negative read-back has
already occurred. It establishes the prior-effective prerequisite that makes
that later observation meaningful.

## Trust boundary preserved

The protected inner semantic authority continues to select OCI(P2a). The
protected outer-consumer authority now selects OCI(P2b), which contains the
integrated B2 orchestration but became trusted only after protected integration,
independent digest-only materialization, attestation and anonymous
reacquisition. Candidate bytes remain unable to choose another protected
runtime or become the provenance source for the final current-advisory result.

The chain after this promotion is:

`protected inner semantic authority -> OCI(P2a) judge`

`protected outer-consumer authority -> OCI(P2b) outer consumer -> isolated nested daemon -> OCI(P2a)`

## Consequences

- OCI(P2b) becomes the independently selected prior-effective outer consumer.
- OCI(B1.6), Decision 0076 and its evidence remain historical trust-chain
  provenance but are no longer the selected protected outer-consumer identity.
- The inner semantic authority remains unchanged and closed v1.
- No OCI publication occurs in this authority-promotion slice; it consumes the
  already verified Decision 0078 materialization identity.
- The final Ariadne exit condition remains the separate subsequent-candidate
  negative read-back required by issue #11 comment `5680382022`.

## Non-goals

This is not a release, deployment or registry publication. It creates no
mutable OCI tag, Git tag, release object, new registry write, provider-setting
mutation, #15 workflow effect, host Docker-socket authority, semantic PASS,
qualified reviewer domain or merge authority. It does not alter the closed
inner semantic authority and does not claim completion of the later negative
read-back.
