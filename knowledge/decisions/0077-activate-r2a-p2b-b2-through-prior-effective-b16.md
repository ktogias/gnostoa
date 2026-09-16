---
type: Decision
title: Activate R2A P2b-B2 through prior-effective OCI(B1.6)
description: Activate protected current-advisory execution only through the protected-main-selected prior-effective B1.6 outer consumer and an isolated nested Docker daemon while preserving candidate semantic dormancy.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-16T09:35:00Z"
sources:
  - id: r2a-architecture
    resource: ./0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: outer-authority-separation
    resource: ./0070-protect-r2a-b1-outer-consumer-authority-separately.md
    title: Decision 0070
  - id: b16-entrypoint
    resource: ./0074-add-input-only-live-entrypoint-to-r2a-b15-runtime.md
    title: Decision 0074
  - id: b16-materialization
    resource: ./0075-materialize-integrated-r2a-p2b-b16-consumer-by-digest.md
    title: Decision 0075
  - id: b16-authority-promotion
    resource: ./0076-promote-r2a-b16-outer-consumer-authority.md
    title: Decision 0076
  - id: b16-promotion-integration-receipt
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5694550281
    title: Integrated B1.6 outer-consumer authority receipt
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
  - id: rolling-trust-exit-boundary
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5680382022
    title: P2b rolling-trust Ariadne exit boundary
x-project-knowledge:
  id: kit.decision.0077.activate-r2a-p2b-b2-through-prior-effective-b16
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
    - kind: governed-by
      target: /decisions/0076-promote-r2a-b16-outer-consumer-authority.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Activate R2A P2b-B2 through prior-effective OCI(B1.6)

## Context

Decision 0070 separated the protected **outer-consumer authority** from the closed v1 **inner semantic authority**. Decision 0074 integrated the bounded input-only live entrypoint while intentionally keeping P2b-B2 dormant. Decision 0075 then independently materialized that exact integrated B1.6 source as a digest-only OCI runtime, and Decision 0076 promoted the protected outer-consumer authority to that independently materialized and post-containment-revalidated B1.6 identity before any activation change.

The prior-effective outer consumer selected from protected `main` is exactly:

- source revision `f29499286bac9859364d45da0f6c59396518b749`;
- source tree `ff38abe5718ebc550054ea6af18a73d0aef8e514`;
- public-surface digest `sha256:c8536ac1f726f1d04f331c95f85a9df128b7cdb818213785cbd6b0b0940f9c57`;
- OCI `ghcr.io/ktogias/gnostoa@sha256:d4cc72b0ed7342f533dd3bcf32ddf9888203f85408154f4066883ba9d33fe867`.

The canonical verification-first RED for B2 is commit `fd44941433cbb5a09bd58808c2c5101caf3f8e06`. Its exact candidate-image `self-check` ran 860 tests with exactly four intended B2 failures and three skips while Ruff, type, golden and policy pre-gates remained clean. The failures were limited to protected outer-consumer acquisition, candidate CLI delegation/raw-byte forwarding, the prior-effective outer runner and the isolated nested-daemon execution plan.

The activation candidate must not make candidate bytes the semantic judge of the same candidate. The trusted result must still come from the protected prior-effective outer consumer selected from protected `main`, and that outer consumer must retain its own pinned Docker client rather than receiving a host-selected executable or the host Docker socket.

## Decision

Activate P2b-B2 only through the prior-effective OCI(B1.6) outer consumer selected by the protected outer-consumer authority.

1. The public `current_advisory` CLI route may delegate to a new candidate-side orchestration helper, but candidate `review_live` / `review_evaluate` semantics remain non-authoritative for the protected current-advisory result.
2. The candidate orchestration helper accepts only the untrusted review input. It acquires the outer-consumer record from protected Gnostoa `main`; callers cannot select the trusted runtime, protected authority document, policy, change class, Docker daemon image or Docker executable.
3. Before execution, the candidate revalidates the protected record's exact digest-pinned OCI identity, source/runtime revision, platform/user label and public-surface digest. Any mismatch or unavailable protected acquisition is a controlled fail-closed tool error, never a semantic PASS.
4. Run the exact prior-effective OCI(B1.6) against an **isolated nested Docker daemon**. The nested daemon image is fixed to `docker.io/library/docker@sha256:76cd6bbc3ab600fced21a7e1bea77ac00cb7c545eb95d5767e4ec4ffbcb242dc`.
5. Never expose host `/var/run/docker.sock` or a host-selected Docker executable to OCI(B1.6). The candidate creates ephemeral internal `/var/run` and `/tmp` volumes shared only by the isolated daemon and the protected outer runtime. The bounded input is mounted read-only.
6. Privilege is confined to the isolated daemon substrate. OCI(B1.6) remains non-privileged, read-only, capability-dropped and `no-new-privileges` while using its own pinned Docker client through the isolated Unix socket.
7. Validate the prior-effective runtime result as bounded canonical JSON and require semantic exit-code/result coherence plus `binding:false`. Forward the validated prior-effective result bytes byte-for-byte; do not project, repair or reinterpret them through candidate semantic code.
8. Own Docker lifecycle by daemon-returned container/volume identities only. Cleanup failures are part of the operation and fail closed; guessed generated names do not confer cleanup authority.
9. Preserve the truthful empty Issue #10 qualification state. A successful live execution is therefore expected to remain advisory `INCOMPLETE / QUORUM_UNMET` with `binding:false`; the prior-effective runtime, not the caller, owns the live evaluation cut.
10. Keep the dedicated R2A exact-head workflow responsible for the activation contract, the prior B1.5/B1.6 runtime contracts and a real isolated nested-daemon smoke before integration.

This activation slice performs **no OCI publication, release, deployment, mutable tag creation, provider-setting mutation or #15 effect**.

## Trust chain after activation

The protected trust direction remains one-way:

`protected inner semantic authority -> OCI(P2a) judge`

`protected outer-consumer authority -> OCI(B1.6) outer consumer -> isolated nested daemon -> OCI(P2a)`

`candidate B2 orchestration -> transports bounded input/result only`

Candidate B2 bytes therefore arrange the execution substrate but do not become the provenance source for the protected final current-advisory result.

## Verification boundary

The candidate is eligible for human review only after all of the following are true on one exact head:

- the canonical RED remains preserved as historical evidence;
- the five focused B2 contracts are green;
- normal Gnostoa `policy`, `fast`, Python compatibility, `regression` and `smoke` gates are green;
- the dedicated R2A workflow is green, including the real isolated nested-daemon smoke;
- material independent-review findings are resolved and fresh exact-head review convergence is obtained.

The live smoke must establish the currently truthful advisory result: exit 3, `INCOMPLETE`, `QUORUM_UNMET`, `binding:false`, replacement of caller-selected evaluation time and protected-OCI provenance diagnostics.

## Ariadne exit boundary remains open

Integrating B2 is not the end of the rolling-trust detour. After B2 integration, issue #11 comment `5680382022` still requires the exact integrated P2b runtime to be independently materialized and attested as immutable digest-only OCI, reacquired and re-proved, promoted as the next protected prior-effective identity, and then negatively read back from a subsequent candidate to prove resolution to that promoted OCI(P2b) rather than candidate-controlled or stale B1.x runtime.

This Decision does not authorize those later publication or promotion effects by itself; it records the B2 activation boundary that must be integrated first.

## Consequences

- `current_advisory` can become live without violating the anti-self-reference requirement.
- The protected B1.6 identity remains independently selected from protected `main` and owns the Docker-client/live-entrypoint capability used for this candidate.
- The host Docker daemon is lifecycle authority for candidate-owned isolated resources only; it is not the semantic execution endpoint presented to B1.6.
- Exact result bytes and exit semantics remain attributable to the prior-effective runtime.
- Cleanup is fail-closed and object-identity-based.
- Human approval remains mandatory before integration because this is a critical Gnostoa-self change.

## Non-goals

This Decision does not merge the candidate, publish or republish an OCI artifact, create a release or deployment, change provider settings, establish semantic PASS, fabricate reviewer qualification, expose the host Docker socket to the protected runtime, authorize candidate semantic self-judgment, or declare the Ariadne rolling-trust detour complete.
