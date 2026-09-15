---
type: Decision
title: Add an input-only executable live entrypoint before R2A P2b-B2 activation
description: Give the integrated outer runtime a fixed executable adapter to its existing protected live evaluator without activating candidate current-advisory or adding Docker-daemon authority.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-15T06:08:00Z"
sources:
  - id: outer-authority-promotion
    resource: ./0073-promote-r2a-b15-outer-consumer-authority.md
    title: Decision 0073
  - id: b16-entrypoint-finding
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5675540419
    title: P2b-B2 executable-entrypoint prerequisite finding
  - id: owner-authorization
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5671332574
    title: Owner authorization through full P2b activation completion
x-project-knowledge:
  id: kit.decision.0074.add-input-only-live-entrypoint-before-r2a-b2
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: governed-by
      target: /decisions/0073-promote-r2a-b15-outer-consumer-authority.md
    - kind: implements
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
---

# Add an input-only executable live entrypoint before R2A P2b-B2 activation

## Context

Decision 0073 promoted the independently materialized OCI(B1.5) outer-consumer identity and that promotion is now protected on `main` at `2b2cb1777196788ccd6b7e4d00d085e5f65ccc47`. OCI(B1.5) therefore supplies the prior-effective outer-consumer authority needed by a later P2b-B2 activation candidate.

The B1.5 runtime already contains two capabilities required by the intended trust chain: the exact pinned Docker client and the complete `tools.review_live.evaluate_gnostoa_current_advisory` implementation. Its public `knowledge review-check` command intentionally remains dormant for protected `current_advisory`, however, and `tools.review_live` has no executable input adapter.

A B2 candidate must not fill that gap with candidate-controlled `python -c`, an injected script, a bind-mounted launcher or another executable shim. Doing so would make candidate bytes execute inside the trusted outer result-projection path, violating the prior-effective boundary established by Decisions 0070 and 0073.

## Decision

Land one final dormant outer-runtime precursor before B2.

1. Add `tools.review_live_entrypoint`, an integrated module entrypoint invoked as `python -m tools.review_live_entrypoint --input <path>`.
2. The entrypoint accepts only an untrusted input document. It exposes no caller-selected policy, change class, repository, protected branch, consumer image, Docker host, Docker context, daemon endpoint or evaluation cut.
3. Reuse the already bounded review-input JSON loader so duplicate object fields, non-finite values, excessive size and excessive nesting fail closed before live evaluation.
4. Delegate the decoded input directly to `tools.review_live.evaluate_gnostoa_current_advisory`, preserve the returned semantic exit code and emit only its canonical JSON payload. The adapter adds no semantic projection of its own.
5. Do not add this route to the public `knowledge` command table. The existing candidate `knowledge review-check` current-advisory dormancy remains unchanged. Candidate/source execution of the private module is non-authoritative evidence only; it cannot become trusted result provenance merely because the module exists.
6. Add exact-runtime smoke verification proving that the candidate image contains and can execute the adapter while no Docker daemon or socket is injected into that runtime. With no nested daemon available, the live route must remain truthful `INCOMPLETE / PRIOR_INTEGRATED_JUDGE_UNAVAILABLE` with `binding:false`.
7. Protect this Decision, the entrypoint, its focused contract and its exact-runtime smoke in the dedicated R2A workflow and semantic-review-assurance guardrail.
8. After this precursor is integrated, independently materialize the exact integrated runtime as a new digest-only immutable outer-consumer identity (B1.6), then promote the separate protected outer-consumer authority to that exact identity before any B2 activation.

This Decision does **not activate P2b-B2** and does not mutate the already published OCI(B1.5) artifact.

## B2 boundary preserved

The later activation candidate may orchestrate the exact prior-effective B1.6 outer container and supply an untrusted input file, but it must not inject executable code into that container. The protected outer runtime itself must perform protected-main acquisition, trusted-cut selection, inner semantic execution and final live-context projection.

The later nested Docker daemon must remain isolated from the host Docker authority. In particular, B2 must not expose or bind-mount the host Docker socket. The intended shape is an ephemeral daemon-owned Unix socket shared only between the isolated nested daemon and the prior-effective outer container, with bounded lifecycle and cleanup. Candidate orchestration may create that isolated transport but may not select or rewrite the trusted outer runtime or inner semantic judge identities.

## Consequences

- The executable adapter becomes part of a separately integratable and materializable outer runtime rather than candidate-injected code.
- The public `knowledge review-check` CLI remains dormant for protected current-advisory until the separate B2 activation slice.
- The precursor has no Docker daemon capability and no host-socket dependency.
- The immutable OCI(B1.5) remains valid historical materialization evidence; a later independently published B1.6 digest will carry the new executable surface.
- B2 activation remains a separate verification-first change after the B1.6 identity is prior-effective.

## Non-goals

This change creates no release, deployment, mutable OCI tag, Docker daemon, host Docker-socket authority, B2 activation, semantic PASS, qualified reviewer state, merge authority or provider-setting mutation. It does not republish OCI(B1.5), does not extend the closed-v1 inner semantic authority, and does not let candidate bytes select protected trust inputs.
