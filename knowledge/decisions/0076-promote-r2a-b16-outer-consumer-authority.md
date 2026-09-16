---
type: Decision
title: Promote the protected R2A outer-consumer authority from OCI(B1.5) to OCI(B1.6)
description: Bind the independently materialized B1.6 input-capable outer consumer as the prior-effective protected consumer before the separately verified P2b-B2 activation slice.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-16T05:33:00Z"
sources:
  - id: outer-authority-separation
    resource: ./0070-protect-r2a-b1-outer-consumer-authority-separately.md
    title: Decision 0070
  - id: b15-authority-promotion
    resource: ./0073-promote-r2a-b15-outer-consumer-authority.md
    title: Decision 0073
  - id: b16-entrypoint
    resource: ./0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
    title: Decision 0074
  - id: b16-materialization
    resource: ./0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md
    title: Decision 0075
  - id: b16-materialization-receipt
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5692487663
    title: Successful immutable OCI(B1.6) materialization receipt
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
x-project-knowledge:
  id: kit.decision.0076.promote-r2a-b16-outer-consumer-authority
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0070-protect-r2a-b1-outer-consumer-authority-separately.md
    - kind: governed-by
      target: /decisions/0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
    - kind: governed-by
      target: /decisions/0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Promote the protected R2A outer-consumer authority from OCI(B1.5) to OCI(B1.6)

## Context

Decision 0070 keeps the protected **outer consumer** authority separate from the closed v1 **inner semantic** authority. Decision 0073 promoted the independently materialized OCI(B1.5) identity so the protected outer consumer, rather than candidate bytes, owned the Docker-client capability required by the rolling-trust path. Decision 0074 then integrated an input-only live entrypoint while explicitly keeping P2b-B2 dormant. Decision 0075 materialized that exact integrated B1.6 source as an immutable, digest-only outer-consumer artifact before any activation change.

The B1.6 materialization completed successfully from protected-main revision `f8aac5159c36a0ff8cb9a22dcc933285c6b52b81`. The accepted source is commit `f29499286bac9859364d45da0f6c59396518b749`, tree `ff38abe5718ebc550054ea6af18a73d0aef8e514`, with public-surface digest `sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57`.

The independently reacquirable B1.6 outer-consumer runtime is exactly:

`ghcr.io/ktogias/gnostoa@sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867`

The one-shot materialization ran as workflow run `35058782405`, produced GitHub attestation `47823269`, was recorded at Rekor log index `2855771710`, and is durably reconciled in issue #11 comment `5692487663`. The run proved exact source/tree identity, local pre-write runtime behavior, digest-only registry publication and readback, attestation, fresh anonymous digest reacquisition, B1.5 client-only smoke, B1.6 input-only live smoke, and final fail-closed reconciliation and cleanup. No mutable OCI tag, release or deployment was created.

The protected outer-consumer authority still selects OCI(B1.5). That older identity intentionally lacks the integrated B1.6 input-only live entrypoint. The next P2b-B2 activation candidate must not smuggle that capability into the trust chain itself. Rolling trust therefore requires the protected authority to move first to the already materialized B1.6 identity.

## Decision

Promote only the protected outer-consumer authority from exact OCI(B1.5) to exact OCI(B1.6).

1. Keep `tasks/issue-11-r2a-current-advisory.json` unchanged as the closed v1 **inner semantic authority**. Its OCI(P2a) judge, policy and qualification snapshot remain separate from the outer consumer.
2. Update `tasks/issue-11-r2a-current-advisory-consumer.json` so both `expected_consumer` and `acquired_consumer` bind source revision `f29499286bac9859364d45da0f6c59396518b749`, source tree `ff38abe5718ebc550054ea6af18a73d0aef8e514`, public-surface digest `sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57`, runtime revision `f29499286bac9859364d45da0f6c59396518b749`, and OCI identity `ghcr.io/ktogias/gnostoa@sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867`.
3. Bind the authority record's materialization provenance to protected-main revision `f8aac5159c36a0ff8cb9a22dcc933285c6b52b81`, workflow run `35058782405`, GitHub attestation `47823269`, Rekor index `2855771710`, and receipt comment `5692487663`.
4. Preserve the existing closed outer-consumer authority schema. This rolling-trust transition changes the selected immutable identity, not the authority shape or the closed v1 inner semantic contract.
5. Keep the dedicated R2A exact-head workflow and the `semantic-review-assurance` guardrail responsible for the protected record, this Decision and the focused authority contract. This authority-promotion slice performs no OCI publication or other registry write.
6. Treat `knowledge/index.md` as **navigation-only** discoverability and **index-only** projection. It remains outside the protected semantic authority and outside the dedicated R2A path filter; general knowledge validation owns index integrity.
7. Once this authority update is integrated into protected `main`, OCI(B1.6) becomes the prior-effective protected outer consumer eligible to evaluate the separately verified P2b-B2 activation candidate.

This Decision **does not activate P2b-B2**. It establishes the final prior-effective outer-consumer prerequisite only.

## B2 boundary preserved

The separately verified activation slice must preserve the same trust boundary: candidate bytes cannot choose the trusted outer runtime, inject another protected consumer identity, expose `/var/run/docker.sock`, or bind-mount a host-selected Docker executable into the trusted runtime. The selected B1.6 image contains the exact pinned Docker client and the bounded input-only live entrypoint while remaining daemonless.

The trusted chain after this promotion is:

`protected inner semantic authority -> OCI(P2a) judge`

`protected outer-consumer authority -> OCI(B1.6) outer consumer -> isolated nested daemon -> OCI(P2a)`

The later P2b-B2 candidate may provide bounded orchestration and transport input/output, but it may not become the provenance source for the protected final current-advisory result.

## Consequences

- B1.6 becomes the independently selected prior-effective outer-consumer authority before P2b-B2 activation.
- OCI(B1.5), Decision 0073 and its materialization receipt remain historical evidence but are no longer the selected protected outer-consumer identity.
- The inner semantic authority remains unchanged and closed v1.
- No OCI publication occurs in this authority-promotion slice; it consumes the already verified Decision 0075 materialization receipt.
- P2b-B2 remains dormant until the next activation candidate passes verification-first RED/GREEN evidence, exact-head CI and fresh review convergence.
- The truthful empty Issue #10 qualification state remains unchanged; `INCOMPLETE / QUORUM_UNMET` and `binding:false` remain legitimate semantic outcomes.

## Non-goals

This is not a release, deployment or registry publication. It creates no mutable OCI tag, Git tag, release object, new registry write, provider-setting mutation, #15 workflow effect, Docker daemon capability, host Docker-socket authority, semantic PASS, qualified reviewer domain or merge authority. It does not activate P2b-B2.
