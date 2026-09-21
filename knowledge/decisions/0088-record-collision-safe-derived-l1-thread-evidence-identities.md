---
type: Decision
title: Record collision-safe derived L1 thread-evidence identities
description: Preserve opaque provider review IDs and legacy non-colliding derived IDs while using a bounded SHA-256 fallback with occupied-ID probing for real collisions.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-21T21:24:03Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/300
    title: Prevent synthetic L1 thread-evidence IDs from colliding with provider review IDs
  - id: implementation
    resource: https://github.com/ktogias/gnostoa/pull/301
    title: Fix provider-neutral L1 observation-ID collisions
  - id: originating-review
    resource: https://github.com/ktogias/gnostoa/pull/292#discussion_r4065373410
    title: Provider-neutral observation-ID collision finding
  - id: useful-l1
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Implement useful L1 as provider-neutral current-state reconciliation with a GitHub adapter
x-project-knowledge:
  id: kit.decision.0088.record-collision-safe-derived-l1-thread-evidence-identities
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
---

# Record collision-safe derived L1 thread-evidence identities

## Context

Decision 0086 treats provider-native identities as opaque inside the
provider-neutral reducer. Useful L1 represents unresolved review-thread state
through a derived COMMENT_ONLY observation. Historically its identity was:

`gnostoa-thread-evidence::<provider-review-observation-id>`

A valid opaque provider review ID can itself equal that generated string for
another review. Before #301, the reducer failed closed in that case even though
the provider evidence was otherwise valid.

PR #292 intentionally retained that pre-existing behavior because its admitted
scope was behavior-preserving refactoring. Issue #300 isolated the semantic
repair, and PR #301 integrated the final implementation on protected main.

This record documents the implementation that actually shipped. It supersedes
the earlier pre-implementation proposal that would have copied an injective
encoding of the full opaque origin ID into the fallback identity.

## Decision

Keep the existing string observation_id contract and allocate each derived
thread-evidence identity against the set of identities that will actually be
emitted.

For a review with unresolved thread evidence:

1. Provider review observation IDs remain opaque and unchanged.
2. The initial occupied set contains provider review IDs whose review
   observations are emitted. A review marked effective:false does not reserve
   provider-observation identity space because its provider review observation
   is not emitted.
3. Try the compatibility identity
   `gnostoa-thread-evidence::<origin-id>`.
4. If that value is occupied, derive
   `sha256(origin-id.encode("utf-8")).hexdigest()` and use
   `gnostoa-thread-evidence:v2:sha256:<64-hex-digest>`.
5. If that candidate is occupied, append `:<n>`, starting at `:1`, until
   the first free candidate is found.
6. Add each emitted derived identity to the occupied set before allocating the
   next derived observation.
7. Preserve the full opaque origin separately in
   `native.origin_review_observation_id`.

The reducer does not parse, rank, truncate, or otherwise reinterpret the
provider-owned review ID.

## Compatibility

The compatibility path is intentionally conservative.

- Non-colliding legacy derived identities stay exactly unchanged.
- A v2 fallback appears only where the old identity would collide and the old
  reducer would fail closed.
- Provider review IDs are never rewritten.
- R2A input schema, recommendation/quorum semantics, and projection format are
  unchanged.
- Existing unresolved-thread currentness semantics are unchanged.
- No GitHub-specific identity rule enters the provider-neutral reducer.

Because ineffective provider review observations are not emitted, their IDs do
not force unnecessary fallback identities. Their unresolved thread state still
remains independently representable through the derived COMMENT_ONLY
observation required by Decision 0086.

## Boundedness and provenance

The fallback must not copy an arbitrarily large provider ID into the generated
identity. The SHA-256 stem has fixed size while complete origin provenance stays
available in native.origin_review_observation_id.

The current GitHub collector admits at most 5,000 retained review items.
At most one derived thread-evidence observation is emitted per review, so the
occupied set remains below roughly 10,000 provider plus derived identities. The
fixed fallback stem is 98 ASCII bytes; even a five-digit sequential probe stays
well below 128 bytes. The focused regression therefore uses a conservative
128-byte bound for the collision fallback.

That regression bound is not a public schema ceiling. The current review-input
schema requires a non-empty observation_id string and does not define a
128-byte maximum.

## Determinism and collision handling

For a given normalized snapshot, digest derivation and first-free occupied-set
probing are deterministic. Focused regression coverage also proves that the
ordinary provider-ID collision case produces the same fallback identity when
provider review order is reversed.

SHA-256 is used as bounded deterministic name derivation, not as a claim of
mathematical injectivity. If a digest-derived candidate is already occupied,
the allocator still guarantees unique emitted identities by probing the
occupied set. In the cryptographically exceptional case where distinct origins
share the same digest family, sequential probing still prevents duplicate
emitted identities; assignment follows normalized review iteration order.

## Alternatives considered

### Reserve a provider-independent prefix

Rejected. Provider IDs are opaque, so the reducer cannot reserve syntax inside
a provider-owned string namespace.

### Copy or Base64URL-encode the full origin ID

Rejected after review. It preserves injectivity but lets an arbitrarily large
provider ID amplify bounded downstream review input.

### Hash-only identity without occupied-set probing

Rejected. A digest alone cannot prove that the generated candidate is absent
from provider-supplied or already-generated identities.

### Random UUID

Rejected because it weakens deterministic reconciliation.

### Introduce a typed public identity object

Deferred because it expands public schemas and compatibility surface beyond the
focused #300 repair.

## Verification evidence

PR #301 covers:

- a provider review ID colliding with another review's legacy derived ID;
- preservation of provider IDs and full origin provenance;
- preservation of the legacy identity on non-colliding input;
- ineffective review IDs not displacing emitted legacy identities;
- probing when the digest stem is itself occupied;
- provider-order reversal for the ordinary collision case;
- a 16 KiB opaque origin ID without fallback identity amplification;
- validation of the resulting R2A input against the existing schema;
- full policy, security-fast, fast, Python 3.11/3.12, extended, regression and
  smoke verification.

The exact merged implementation is protected-main commit
`b22f87865ee3d9eae65709284b89fcb015daec45`.

## Change classification

The implementation in #301 was critical because normalized semantic evidence
can affect R2A input, projection currentness, and the next permitted workflow
action.

This follow-up record is documentation-only. It does not change executable
behavior, schemas, provider permissions, workflow execution, review
qualification, quorum, or merge authority.

## Non-goals

This decision does not define a global identity service, reinterpret provider
IDs, change reviewer identity semantics, alter recommendation effectiveness,
add provider-write authority, or migrate successful historical non-colliding
observation identities.
