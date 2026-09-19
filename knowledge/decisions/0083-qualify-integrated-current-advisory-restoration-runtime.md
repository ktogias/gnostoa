---
type: Decision
title: Qualify the integrated transport-safe current-advisory runtime before publication
description: Verify the exact post-278 integrated runtime and its layered stdin/tmpfs transport without publishing or promoting it, before any immutable restoration artifact is authorized.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-19T07:28:00Z"
sources:
  - id: restoration-work-item
    resource: https://github.com/ktogias/gnostoa/issues/275
    title: Eliminate protected review payload persistence and gate secret regressions
  - id: containment-decision
    resource: ./0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    title: Eliminate host persistence for protected review payloads and route bounded security gates
  - id: prior-p2b-materialization
    resource: ./0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    title: Materialize the integrated R2A P2b runtime as a prior-effective digest-only OCI identity
x-project-knowledge:
  id: kit.decision.0083.qualify-integrated-current-advisory-restoration-runtime
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    - kind: references
      target: /decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    - kind: references
      target: /decisions/0079-promote-r2a-p2b-outer-consumer-authority.md
---

# Qualify the integrated transport-safe current-advisory runtime before publication

## Context

PR #278 was owner-authorized and integrated on protected `main` as
`315487e7a67635ebf3ec3f70f666ef41646102e1`, tree
`ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`. Decision 0082 deliberately
contains the still-promoted outer consumer because its immutable runtime predates
the repaired transport. Production therefore remains
`current_advisory=UNAVAILABLE` until a separately materialized and promoted
transport-compatible runtime exists.

The protected outer-consumer authority still names source/runtime
`2aa1ed3217c42819155b8ff36385b000720ba4f8` and OCI digest
`sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281`.
That immutable artifact is historical and is not overwritten. The protected
inner semantic judge identity remains unchanged by this Decision.

## Classification and authority boundary

This is a **critical** Gnostoa-self restoration slice under #275. The owner
selected continuation of the recorded R1-R7 restoration sequence after merging
#278. This Decision admits **R2 qualification only**:

- build the exact integrated post-#278 source as a local candidate runtime;
- bind the result to source revision, source tree, local image content ID and
  measured public-surface digest;
- exercise the actual outer stdin/container-tmpfs bridge and the repaired inner
  stdin/container-tmpfs path through the isolated-daemon topology;
- verify that the host-backed shared outer `/tmp` volume does not retain a
  unique protected-input sentinel; and
- retain existing negative containment behavior in production.

This Decision does **not** authorize GHCR authentication, publication,
attestation, release creation, protected-authority mutation, compatibility
catalog admission, provider required-check mutation or #275 closure. R3 and R4
remain separate exact-effect decisions.

## Prior art and reuse

The bounded need is already mostly implemented. Reuse:

- `ci/build-runtime` for a Git-filtered exact-source runtime build;
- Decisions 0078-0080 for identity separation, immutable publication and
  promotion ordering;
- the current protected-consumer workflow and historical live smokes for
  container/runtime checks;
- Decision 0082's outer and inner bridges, isolated Docker daemon, log-disabled
  payload containers and fail-closed lifecycle handling.

No new runtime framework, scanner, registry, dependency or release mechanism is
introduced. A local registry was considered but rejected for R2: it would add
another service and supply-chain surface merely to manufacture a registry
manifest before publication is authorized. R2 instead records Docker's local
content-addressed image ID; R3 is where an immutable registry manifest digest
can legitimately come into existence.

The qualification smoke may substitute a **test-only local candidate identity**
for protected outer-consumer acquisition and image-pull proof so the exact
locally built image can exercise the real transport and nested execution layers.
It must not patch the transport implementation, semantic evaluator or inner
protected judge, and it cannot populate the production compatibility catalog.

## Prospective behavior map

| ID | Observable requirement | Pre-implementation evidence | Candidate evidence |
|---|---|---|---|
| R2-A | Exact integrated source builds and binds revision/tree/image ID/public surface | no R2-specific qualification workflow exists | provider qualification receipt |
| R2-B | Candidate executes outer and inner repaired transport through real runtime layers | active public smoke stops at containment; historical live smoke selects old OCI(P2b) | candidate restoration smoke returns a genuine semantic result |
| R2-C | Protected-input sentinel is absent from the host-backed shared outer `/tmp` volume | old immutable outer runtime can persist delegated documents there | pre-cleanup volume inspection |
| R2-D | Production remains unavailable before promotion | production compatibility catalog is empty | existing containment tests plus no authority/catalog diff |
| R2-E | Qualification cannot publish by construction | historical materializer has effect-capable permissions | read-only workflow permissions and no registry-effect commands |

The RED contract is committed before the verification workflow/smoke exists and
must fail for their absence. A later implementation rebinds each row to the
exact candidate and actual provider evidence.

## Decision

Create one verification-only provider route for R2. It checks out the candidate
orchestration code and the exact integrated source separately, verifies the
fixed source revision/tree, builds the exact source locally, records its local
content-addressed image ID and public-surface digest, and runs focused transport
contracts plus the candidate restoration smoke.

The smoke uses the exact locally built runtime. Test-only substitution is
limited to the outer authority/image-selection boundary needed because the image
has not been published yet. The production outer/inner bridges, nested daemon,
inner protected authority and semantic evaluator execute normally. Before the
shared outer `/tmp` volume is removed, the smoke checks that a unique
protected-input sentinel is absent. Cleanup then proceeds through the ordinary
production path.

A semantic result such as `INCOMPLETE / QUORUM_UNMET` is acceptable R2 proof;
`TOOL_ERROR`, `current_advisory=UNAVAILABLE` or
`live_evaluation=NOT_RUN` is not. The receipt must never print the sentinel or
raw protected input.

Successful R2 qualification establishes only that one exact integrated source
can be built and exercises the selected transport safely under provider CI. It
does not create an immutable public identity and cannot restore the production
route by itself.

## Stop and successor

After exact-candidate verification and independent review, human semantic review
remains required before this critical slice can integrate. Once R2 is integrated
and read back, R3 requires separate owner authorization for the exact immutable
OCI publication/attestation effect. No preparation result silently grants that
authority.
