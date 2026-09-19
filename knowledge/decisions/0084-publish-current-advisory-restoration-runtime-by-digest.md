---
type: Decision
title: Publish the qualified current-advisory restoration runtime as a digest-only OCI identity
description: Materialize the exact post-278 transport-safe runtime once by immutable GHCR digest, attest and anonymously reacquire it, and prove the restored layered path before any protected-authority promotion.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-19T09:16:00Z"
sources:
  - id: restoration-work-item
    resource: https://github.com/ktogias/gnostoa/issues/275
    title: Eliminate protected review payload persistence and gate secret regressions
  - id: transport-containment
    resource: ./0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    title: Decision 0082
  - id: r2-qualification
    resource: ./0083-qualify-integrated-current-advisory-restoration-runtime.md
    title: Decision 0083
  - id: prior-materialization-pattern
    resource: ./0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
    title: Decision 0078
  - id: r2-integration
    resource: https://github.com/ktogias/gnostoa/commit/b80a4d8246e48d1e922c1732c37201e3e2b92c47
    title: Integrated R2 qualification mechanism
x-project-knowledge:
  id: kit.decision.0084.publish-current-advisory-restoration-runtime-by-digest
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    - kind: governed-by
      target: /decisions/0083-qualify-integrated-current-advisory-restoration-runtime.md
    - kind: governed-by
      target: /decisions/0078-materialize-integrated-r2a-p2b-runtime-by-digest.md
---

# Publish the qualified current-advisory restoration runtime as a digest-only OCI identity

## Context

PR #278 integrated the transport-safe runtime source on protected `main` as
exact commit `315487e7a67635ebf3ec3f70f666ef41646102e1`, tree
`ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`. PR #279 subsequently
integrated the verification-only R2 qualification mechanism as
`b80a4d8246e48d1e922c1732c37201e3e2b92c47`.

R2 qualified **the runtime source at `315487e7...`**, not the later
qualification-mechanism commit. Exact-head provider evidence proved that source
builds locally, has public-surface digest
`sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2`,
executes the repaired outer/inner stdin+tmpfs transport through the isolated
daemon, returns the truthful advisory semantic result
`INCOMPLETE / QUORUM_UNMET`, and leaves the protected-input sentinel absent
from the host-backed shared outer `/tmp` volume.

Production nevertheless remains contained because the protected outer-consumer
authority still selects the historical immutable runtime at
`ghcr.io/ktogias/gnostoa@sha256:a657bb69c2cd1c117831558bf9794aa07caa74ac8adaff8d05b5650165b0d281`,
whose source/runtime revision
`2aa1ed3217c42819155b8ff36385b000720ba4f8` predates the repair. That image is
immutable and must not be overwritten or reinterpreted.

R3 therefore needs one new immutable registry identity for the **already
qualified source**. Publication is a provider write and is deliberately
separate from R2 integration and from the later R4 protected-authority and
compatibility admission.

## Classification and authority boundary

This is a **critical** restoration slice under #275.

The owner authorized continued preparation through the restoration sequence,
with a stop whenever a new human authorization is actually required. This
Decision therefore admits preparation, verification and review of the exact R3
candidate.

It does **not** by itself authorize the registry write. The R3 Pull Request will
contain a one-shot protected-main workflow whose merge triggers the publication
effect. **Merging that exact candidate is the publication authorization point
and requires a separate owner decision after the exact PR head, effect and
review evidence are available.**

No R3 preparation authorizes:

- GHCR publication before that merge;
- a mutable OCI tag;
- Git tag, GitHub Release or deployment;
- protected-authority or compatibility-catalog mutation;
- provider ruleset / required-check mutation;
- alert dismissal; or
- #275 closure.

## Prior-art and reuse checkpoint

Reuse Decision 0078's proven one-shot materialization pattern instead of
inventing a new release mechanism:

- exact predecessor, PR number, branch and protected-main landing binding;
- independent `GITHUB_RUN_ATTEMPT == 1` fences in authorization and
  effect-capable jobs;
- separate checkout of the exact source being materialized;
- deterministic `BUILD_DATE` from the source commit;
- `ci/build-runtime --push-by-digest` with no mutable remote tag;
- local source/runtime/public-surface verification before authentication;
- bounded BuildKit metadata parsing for the manifest digest;
- digest-qualified reacquisition and self-check;
- pinned GitHub artifact attestation;
- authenticated-state removal followed by anonymous reacquisition;
- final read-only reconciliation and fail-closed recovery after an ambiguous
  effect; and
- bounded provider summary carrying exact identities.

The restoration-specific residual need is to bind those mechanics to the R2
qualified runtime source and replay the layered current-advisory qualification
against the **published digest**, not merely against a local tag.

No new dependency, third-party runtime, registry, license obligation or NOTICE
obligation is introduced.

## Exact publication subject

The only runtime source eligible for R3 is:

- source commit:
  `315487e7a67635ebf3ec3f70f666ef41646102e1`;
- source tree:
  `ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`;
- expected public-surface digest:
  `sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2`;
- registry name: `ghcr.io/ktogias/gnostoa`;
- platform: `linux/amd64`;
- runtime uid/gid: `10001/10001`.

The R2 local image ID was candidate-local evidence only. It is **not** the R3
registry manifest identity and must not be copied into protected authority.

## Prospective behavior map

| ID | Observable requirement | Pre-effect state | Required R3 evidence |
|---|---|---|---|
| R3-A | Only the exact admitted landing can obtain package-write authority | no R3 publisher exists | exact predecessor/PR/head/ref/attempt authorization |
| R3-B | Exact qualified source is reverified before authentication | R2 qualified local build only | source/tree/version/runtime metadata + expected public-surface digest |
| R3-C | Publication creates no mutable tag | no restoration artifact exists | BuildKit digest-only metadata + registry read-back |
| R3-D | Published artifact is independently reacquirable | NOT RUN | authenticated read-back, attestation, logout/cache removal, anonymous pull |
| R3-E | Published digest executes the repaired layered path | local R2 candidate only | restoration smoke against the digest-qualified image |
| R3-F | Protected input remains absent from host-backed shared outer tmp | proved only for local R2 image | post-publication layered smoke sentinel absence |
| R3-G | Publication does not promote production trust | old authority/catalog unchanged | no authority/catalog diff; receipt says promotion NOT PERFORMED |
| R3-H | Ambiguous write cannot be converted into blind rerun authority | historical pattern only | attempt-1 fence + read-only reconciliation |

## Decision

Prepare one dedicated protected-main workflow that can materialize the exact R3
subject **once**, only after the exact candidate receives separate merge/effect
authorization.

The workflow SHALL:

1. run only on a protected-main push that changes the R3 workflow itself;
2. bind `GITHUB_EVENT_BEFORE` to the exact protected-main predecessor from
   which the authorized R3 PR was cut;
3. bind the landing commit through the GitHub Pull Request record to one exact
   PR number, head branch, repository and merged commit;
4. require `GITHUB_RUN_ATTEMPT == 1` independently in both the authorization
   job and the effect-capable publication job;
5. check out the exact publisher landing and, separately, source
   `315487e7...`; verify source commit/tree, clean state, package version,
   runtime lock and deterministic build date before authentication;
6. build the exact source locally before any registry effect and verify
   linux/amd64, uid/gid 10001, OCI revision/created labels, full runtime
   self-check and **exact expected public-surface digest**;
7. verify the source contains the repaired current-advisory transport surfaces,
   including `tools/review_current.py`, `tools/review_outer.py`,
   `tools/review_live.py` and their required entrypoints;
8. authenticate only inside the effect-capable job after all pre-write checks
   succeed;
9. publish with `ci/build-runtime --push-by-digest`, create no mutable remote
   tag, and derive one exact `sha256:...` registry manifest digest from
   bounded BuildKit metadata;
10. pull/read back that exact digest and repeat platform, runtime revision,
    uid/gid, expected public-surface digest and self-check verification;
11. attest that exact manifest using a pinned provider action, verify the
    attestation, remove authenticated Docker state and local cached image, then
    anonymously reacquire the same digest through a fresh Docker configuration
    and repeat the identity/runtime proofs;
12. execute the R2 restoration layered smoke against the exact digest-qualified
    image after anonymous reacquisition. It must again establish
    `INCOMPLETE / QUORUM_UNMET`, `binding:false`, the exact protected source
    identity and absence of the protected-input sentinel from the host-backed
    shared outer `/tmp` volume;
13. leave the production compatibility catalog and protected
    outer-consumer authority unchanged;
14. perform final read-only registry + attestation reconciliation and fail
    closed if the exact immutable state cannot be established; and
15. emit a bounded receipt containing source commit/tree, public-surface digest,
    OCI manifest digest, workflow run, attestation identity and explicit
    `authority promotion: NOT PERFORMED`.

## One-shot failure and recovery contract

The registry write is not retry-safe by assumption.

If attempt 1 reaches authentication or package-write territory and later fails,
times out, disconnects or returns ambiguous metadata, the workflow must not
create automatic rerun authority. Recovery starts with **read-only** provider,
registry and attestation reconciliation. If the exact digest and attestation can
be established, they are recorded as the effect result. If they cannot, the
slice returns to an explicit owner decision with the ambiguity preserved.

A new commit merely to rerun an ambiguous publication is prohibited unless the
new verification-first disposition explicitly establishes why that later effect
is safe.

## Verification contract before publication authorization

Before asking the owner to authorize the merge/effect:

- Decision 0084, the one-shot workflow and focused contract tests exist on one
  exact sealed PR head;
- the general policy/security/fast/compatibility/extended/regression/smoke suites
  pass;
- structural tests prove exact source/predecessor/PR/head/attempt fences;
- structural tests prove effect-capable permissions exist only on the publish
  job and that the authorization job is read-only;
- structural tests prove digest-only publication, bounded metadata parsing,
  attestation, authenticated cleanup, anonymous reacquisition and
  post-publication layered restoration smoke are mandatory and cannot be
  suppressed with `if` / `continue-on-error`;
- the workflow cannot create a mutable tag, Git tag, Release, deployment or
  authority/catalog mutation;
- independent review reconciles the candidate against this Decision and the
  R3 effect boundary; and
- the exact PR head, exact predecessor and exact provider effect are shown to the
  owner before merge.

## Consequences

- The exact transport-safe runtime source obtains a path to one independently
  reacquirable, digest-pinned OCI identity without changing production trust in
  the same transition.
- Publication evidence becomes separable from R4 authority/compatibility
  promotion, preserving the prior-effective trust boundary and making rollback
  and audit attribution explicit.
- The one-shot authorization fence deliberately trades convenience for safety:
  an ambiguous provider write cannot be converted into blind rerun authority.
- R2 local qualification remains valid historical evidence for the qualified
  source, while R3 adds registry-manifest, attestation and anonymous
  reacquisition evidence for that same source.
- Production `current_advisory` remains unavailable after R3 alone; availability
  changes only after a separately admitted R4 promotion and subsequent R5
  public-route proof.

## Stop and successor

**Stop before merge/publication for a separate owner authorization.**

After an authorized R3 merge, read back the protected-main landing, one-shot
workflow run, immutable digest, attestation, anonymous reacquisition and
restoration smoke. Only then may R3 be marked complete.

R4 is separate again: it will admit the resulting exact immutable identity into
the production compatibility catalog and protected outer-consumer authority.
R3 success supplies evidence for R4 but does not authorize or perform it.

#275 remains open until R4 promotion, R5 real public-route evaluation, R6
provider-security read-back and R7 final reconciliation complete.
