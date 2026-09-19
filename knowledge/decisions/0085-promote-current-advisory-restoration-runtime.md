---
type: Decision
title: Promote the exact restoration runtime into protected current-advisory transport authority
description: Admit the complete independently materialized transport-compatible runtime identity into the restriction-only catalog and protected outer-consumer authority, without changing the closed inner semantic authority.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-19T10:05:00Z"
sources:
  - id: restoration-work-item
    resource: https://github.com/ktogias/gnostoa/issues/275
    title: Eliminate protected review payload persistence and gate secret regressions
  - id: containment-decision
    resource: ./0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    title: Decision 0082
  - id: qualification-decision
    resource: ./0083-qualify-integrated-current-advisory-restoration-runtime.md
    title: Decision 0083
  - id: publication-decision
    resource: ./0084-publish-current-advisory-restoration-runtime-by-digest.md
    title: Decision 0084
  - id: r3-receipt
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5741025232
    title: Successful immutable R3 restoration materialization receipt
x-project-knowledge:
  id: kit.decision.0085.promote-current-advisory-restoration-runtime
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
      target: /decisions/0084-publish-current-advisory-restoration-runtime-by-digest.md
---

# Promote the exact restoration runtime into protected current-advisory transport authority

## Context

Decision 0082 deliberately contained `current_advisory` by leaving the
restriction-only host-persistence-free consumer catalog empty. PR #278 integrated
the repaired stdin + container-tmpfs transport while refusing to execute any
historical protected outer consumer that had not independently proved the new
transport contract.

Decision 0083 and PR #279 then qualified exact integrated runtime source
`315487e7a67635ebf3ec3f70f666ef41646102e1`, tree
`ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`. The verification-only R2 path
proved the real layered outer/inner execution, truthful
`INCOMPLETE / QUORUM_UNMET`, `binding:false`, and absence of the protected
input sentinel from the host-backed shared outer `/tmp` boundary.

Decision 0084 and owner-authorized PR #281 then materialized that already
qualified source once as an immutable, attested OCI identity. Protected-main
publisher landing `d097f166a2a6a43e7c963b27aeadd91217e19ac7`, workflow run
`35436003854`, attempt 1, produced and fully reconciled:

- source revision:
  `315487e7a67635ebf3ec3f70f666ef41646102e1`;
- source tree:
  `ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`;
- public-surface digest:
  `sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2`;
- immutable OCI image:
  `ghcr.io/ktogias/gnostoa@sha256:6bf4b876987fa4a5db8e3ae6bcc420e306666d8ee81ca40b934a6570a45b2b0f`;
- GitHub attestation `48625673`;
- Rekor transparency-log index `2892075330`; and
- durable R3 authority-compatible receipt issue #11 comment `5741025232`.

The R3 job verified the exact digest before and after authentication-state
removal, reacquired it anonymously, replayed the layered restoration smoke and
completed final read-only reconciliation and cleanup. No mutable tag, release,
deployment, protected-authority mutation or compatibility admission occurred.

Production `current_advisory` therefore remains contained for exactly one
reason: protected authority still names the historical P2b runtime and the
restriction-only
`_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES` catalog still admits no runtime.

## Prior-art and reuse disposition

Reuse the protected outer-consumer authority pattern from Decisions 0070, 0073,
0076 and 0079:

- the closed
  `schemas/review-protected-consumer-authority.schema.json`;
- equal `expected_consumer` and `acquired_consumer` identities;
- digest-pinned OCI runtime, exact source/runtime revision and source tree;
- immutable materialization provenance;
- the dedicated R2A exact-head verification workflow; and
- the `semantic-review-assurance` guardrail.

Decision 0082 adds one new restriction to that historical promotion shape: the
same complete **nine-field canonical consumer identity** must also be admitted
to the static host-persistence-free transport catalog. The catalog is not an
authority selector. It can only restrict an already protected, schema-valid,
expected/acquired-equal consumer identity.

Do not reuse the old P2b identity merely because it is already protected. That
artifact predates the repaired transport. Do not admit only a digest, revision,
or image string: partial admission would weaken Decision 0082's complete
identity binding.

No new dependency, third-party service, copied implementation, license or
NOTICE obligation is introduced.

## Exact promoted identity

Both the protected authority and restriction-only catalog shall bind exactly:

- `role = current_advisory_outer_consumer`;
- `acquisition = oci`;
- `source_revision = 315487e7a67635ebf3ec3f70f666ef41646102e1`;
- `source_tree = ea3fdebc6afa9bf5a4c2d0691199beca4dcece81`;
- `public_surface_digest = sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2`;
- `runtime_image = ghcr.io/ktogias/gnostoa@sha256:6bf4b876987fa4a5db8e3ae6bcc420e306666d8ee81ca40b934a6570a45b2b0f`;
- `runtime_revision = 315487e7a67635ebf3ec3f70f666ef41646102e1`;
- `supported_input_schema_versions = ["1.0"]`; and
- `status = accepted`.

Its exact canonical JSON string is:

`{"acquisition":"oci","public_surface_digest":"sha256:45bc59ce177ab53ddb5925279166b5ede91bbb6c43ef31fb056de56b6ddabca2","role":"current_advisory_outer_consumer","runtime_image":"ghcr.io/ktogias/gnostoa@sha256:6bf4b876987fa4a5db8e3ae6bcc420e306666d8ee81ca40b934a6570a45b2b0f","runtime_revision":"315487e7a67635ebf3ec3f70f666ef41646102e1","source_revision":"315487e7a67635ebf3ec3f70f666ef41646102e1","source_tree":"ea3fdebc6afa9bf5a4c2d0691199beca4dcece81","status":"accepted","supported_input_schema_versions":["1.0"]}` <!-- pragma: allowlist secret -- reviewed public R4 consumer identity -->

## Decision

Promote the independently materialized R3 identity into the protected outer
consumer and restriction-only transport compatibility boundary in one protected
main transition.

1. Update
   `tasks/issue-11-r2a-current-advisory-consumer.json` so
   `expected_consumer` and `acquired_consumer` are exactly the nine-field
   identity above.
2. Bind the authority record's materialization provenance to:
   - protected-main publisher revision
     `d097f166a2a6a43e7c963b27aeadd91217e19ac7`;
   - workflow run `35436003854`;
   - GitHub attestation `48625673`;
   - Rekor log index `2892075330`; and
   - receipt
     `https://github.com/ktogias/gnostoa/issues/11#issuecomment-5741025232`.
3. Add **only** the exact canonical nine-field identity above to
   `_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES`. Keep the catalog static,
   private and caller/environment independent.
4. Preserve `_require_transport_compatible_consumer` as a restriction after
   protected acquisition, closed-schema validation and expected/acquired
   equality. Do not let the catalog select, repair or substitute authority.
5. Keep
   `tasks/issue-11-r2a-current-advisory.json` unchanged. The closed v1 inner
   semantic authority remains independent and continues to select the existing
   protected semantic judge.
6. Add focused contracts proving:
   - the production catalog contains exactly one admitted canonical identity;
   - every one of the nine identity fields is binding;
   - historical P2b/B1.x, unknown and candidate-selected identities remain
     rejected;
   - the protected authority binds the exact R3 digest and provenance;
   - malformed/mismatched protected authority still fails before transport
     admission;
   - the actual protected route can pass the compatibility gate only for the
     exact promoted identity and still performs the mandatory image/source/
     public-surface proofs before outer execution.
7. Keep Decision 0085, the authority record, the catalog implementation and
   focused tests under the dedicated R2A workflow and semantic-review guardrail.
8. Perform no OCI publication, attestation, tag, release, deployment or provider
   setting mutation in this slice.

## Verification contract before merge

Before asking for human semantic/effect authorization:

- the R4 candidate is sealed to one exact PR head;
- general policy/security/fast/Python compatibility/extended/regression/smoke
  verification is green;
- the dedicated protected-current-advisory consumer verification is green;
- focused tests prove the exact authority and complete canonical catalog
  admission described above;
- a candidate-side live proof may exercise the promoted identity only through
  test-local protected-main acquisition control and must show a genuine semantic
  current-advisory result rather than `UNAVAILABLE` or `TOOL_ERROR`;
- independent supplied-agent review finds no unresolved actionable defect; and
- the owner is shown that merge changes production protected trust selection,
  but performs no registry write.

## Effect boundary

R4 merge is a **protected trust-promotion effect**. It changes which immutable
outer consumer production may execute and ends Decision 0082's intentional
transport containment for that exact identity.

Therefore preparation and verification may proceed under #275, but **merge
requires a separate human semantic/effect authorization** on the exact sealed
candidate.

R4 authorization does not authorize later provider alert dismissal or any
unrelated trust expansion.

## Consequences

- The exact R3 immutable runtime becomes the sole admitted host-persistence-free
  protected outer consumer.
- Historical P2b/B1.x runtime identities remain durable provenance but are no
  longer eligible for transport execution.
- The closed inner semantic authority remains unchanged.
- The public route can proceed past transport containment only when protected
  authority resolves exactly the promoted identity and all existing image/source
  proofs succeed.
- R5 must separately demonstrate a real protected-main public
  `current_advisory` evaluation after R4 integration.
- #275 remains open through R5 live proof, R6 provider-security read-back and R7
  final reconciliation.

## Non-goals

This slice does not republish the runtime, create any mutable artifact, change
the inner judge/policy, dismiss provider alerts, change required checks, modify
branch protection, or close #275.
