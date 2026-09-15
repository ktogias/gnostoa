---
type: Decision
title: Promote the protected R2A outer-consumer authority from OCI(B1) to OCI(B1.5)
description: Bind the independently materialized B1.5 client-capable outer consumer as the prior-effective protected consumer before any P2b-B2 activation.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-15T00:53:00Z"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: outer-authority-separation
    resource: ./0070-protect-r2a-b1-outer-consumer-authority-separately.md
    title: Decision 0070
  - id: b15-runtime
    resource: ./0071-add-docker-client-to-r2a-b1-runtime.md
    title: Decision 0071
  - id: b15-materialization
    resource: ./0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md
    title: Decision 0072
  - id: b15-materialization-receipt
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671868333
    title: Successful immutable OCI(B1.5) materialization receipt
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
x-project-knowledge:
  id: kit.decision.0073.promote-r2a-b15-outer-consumer-authority
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0070-protect-r2a-b1-outer-consumer-authority-separately.md
    - kind: governed-by
      target: /decisions/0071-add-docker-client-to-r2a-b1-runtime.md
    - kind: governed-by
      target: /decisions/0072-materialize-integrated-r2a-p2b-b15-consumer-by-digest.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Promote the protected R2A outer-consumer authority from OCI(B1) to OCI(B1.5)

## Context

Decision 0070 keeps the protected outer current-advisory consumer authority separate from the closed v1 inner semantic authority. Decision 0071 then added only the pinned Docker client capability required by the dormant outer consumer, without adding a daemon or activating P2b-B2. Decision 0072 materialized the exact integrated B1.5 source through the established digest-only rolling trust pattern.

That protected-main materialization completed successfully. The accepted B1.5 source is commit `7093fd043f2269e09da74b03ce9d35fb6aece5da`, tree `e7a4f2142e72efd52133f4719d8acf9b2dccb89d`, with public-surface digest `sha256:b07aec4907919c0c9a92e4382524db4f7981bd346a5a1292f5ac48e4a1e6238e`.

The independently reacquirable outer-consumer runtime is exactly:

`ghcr.io/ktogias/gnostoa@sha256:821b523d2ebe80d0194cfc366ff70c59e90b99c5524dd82df8e866ccfa00e1c3`

The successful materialization ran from protected-main publisher revision `8b189f66c92859b4ef75a91d962f4aec38b30408` as workflow run `34905764252`, produced GitHub attestation `47472753`, was recorded at Rekor log index `2835934017`, and is durably reconciled in issue #11 comment `5671868333`. Verification included local pre-write runtime validation, digest-only registry publication/readback, attestation verification, anonymous digest reacquisition, and repeated B1.5 client-only runtime smoke verification.

The current protected outer-consumer record still selects the older OCI(B1). That identity is no longer sufficient for B2 because it lacks the Docker client required by the already-integrated nested semantic judge path. Candidate B2 bytes must not fill that gap themselves. The protected authority must therefore move first to the independently materialized B1.5 identity.

## Decision

Promote only the protected outer-consumer authority to exact OCI(B1.5).

1. Keep `tasks/issue-11-r2a-current-advisory.json` unchanged as the closed v1 **inner semantic authority**. Its prior-integrated OCI(P2a) semantic judge, policy and qualification snapshot remain separate from outer-consumer authority.
2. Update `tasks/issue-11-r2a-current-advisory-consumer.json` so both `expected_consumer` and `acquired_consumer` bind the exact B1.5 source revision, source tree, public-surface digest, runtime revision and digest-only OCI identity above.
3. Bind the record's materialization provenance to protected-main revision `8b189f66c92859b4ef75a91d962f4aec38b30408`, workflow run `34905764252`, attestation `47472753`, Rekor index `2835934017`, and receipt comment `5671868333`.
4. Preserve the existing closed outer-consumer authority schema. This transition changes the selected immutable identity, not the authority shape.
5. Keep the dedicated R2A exact-head workflow and `semantic-review-assurance` guardrail responsible for this protected record and its focused contract. This Decision becomes a declared governed implementation surface as well.
6. Treat `knowledge/index.md` as navigation-only discoverability, not as protected semantic authority. It is intentionally outside the `semantic-review-assurance` implementation surface and the dedicated R2A path filter. An index-only change can alter navigation to this Decision, but cannot alter the protected consumer record, selected runtime, materialization provenance, inner semantic authority or P2b-B2 activation state; general knowledge validation remains responsible for index integrity.
7. Once this authority update is integrated into protected `main`, OCI(B1.5) becomes the prior-effective outer current-advisory consumer eligible to evaluate a separately verified P2b-B2 activation candidate.

This Decision **does not activate P2b-B2**. It creates the prerequisite prior-effective authority only.

## B2 boundary preserved

The next activation slice must not expose `/var/run/docker.sock`, bind-mount a host-selected Docker executable, or let candidate bytes select the trusted outer runtime. OCI(B1.5) already contains the exact pinned Docker client. A later B2 candidate must route untrusted current-advisory input through this protected digest-only outer identity and a separately bounded isolated Docker daemon substrate.

The trusted chain remains explicit:

`protected inner semantic authority -> OCI(P2a) judge`

`protected outer-consumer authority -> OCI(B1.5) outer consumer -> isolated nested daemon -> OCI(P2a)`

Candidate B2 code may transport input/output and provide bounded orchestration, but it may not become the provenance source for the final current-advisory result.

## Consequences

- The client-capable B1.5 outer consumer becomes independently selected and prior-effective before B2 activation.
- The older OCI(B1) remains historical evidence but is no longer the selected protected outer-consumer identity.
- The inner semantic authority remains backward-compatible and unchanged.
- No OCI publication occurs in this authority-update slice; it consumes the already verified immutable materialization receipt.
- P2b-B2 remains dormant until a separate activation candidate passes exact-head verification and fresh review convergence.
- The truthful empty Issue #10 qualification state is unchanged. `INCOMPLETE / QUORUM_UNMET` and `binding:false` remain legitimate semantic outcomes.

## Non-goals

This is not a release or deployment. It creates no mutable OCI tag, Git tag, release object, new registry write, provider-setting mutation, #15 workflow effect, Docker daemon capability, host Docker-socket authority, semantic PASS, qualified reviewer domain or merge authority. It does not activate P2b-B2.
